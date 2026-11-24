#!/usr/bin/env python3
"""Deterministic Antigravity session context & prompt-cache auditor.

Reads <appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript_full.jsonl
(or transcript.jsonl) in UTF-8 without feeding raw logs into the LLM context window.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import os
import sys
from typing import Any


HANDOFF_SWEET_SPOT = 150_000
HANDOFF_HARD_LINE = 180_000
LONG_CONTEXT_TIER = 200_000


def parse_iso(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    clean = ts.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return None


def resolve_transcript(conv_id: str | None, explicit_path: str | None) -> tuple[str, Path]:
    if explicit_path:
        p = Path(explicit_path)
        return (conv_id or p.parent.parent.parent.name, p)

    brain_root = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".gemini" / "antigravity" / "brain"
    if conv_id:
        base = brain_root / conv_id / ".system_generated" / "logs"
        for name in ("transcript_full.jsonl", "transcript.jsonl"):
            cand = base / name
            if cand.is_file():
                return (conv_id, cand)
        raise FileNotFoundError(f"Transcript not found for conversation: {conv_id}")

    candidates: list[tuple[float, str, Path]] = []
    if brain_root.is_dir():
        for child in brain_root.iterdir():
            if not child.is_dir():
                continue
            logs_dir = child / ".system_generated" / "logs"
            cand = logs_dir / "transcript_full.jsonl"
            if not cand.is_file():
                cand = logs_dir / "transcript.jsonl"
            if cand.is_file():
                candidates.append((cand.stat().st_mtime, child.name, cand))
    if not candidates:
        raise FileNotFoundError(f"No conversation transcripts found under {brain_root}")
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, cid, best = candidates[0]
    return (cid, best)


def summarize_tool_target(tc: dict[str, Any]) -> str:
    name = str(tc.get("name") or "tool")
    args = tc.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    if not isinstance(args, dict):
        args = {}
    for key in ("Path", "CommandLine", "query", "Role", "focus"):
        val = args.get(key)
        if val:
            text = str(val).strip().strip('"').replace("\n", " ")
            if len(text) > 72:
                text = text[:69] + "..."
            return f"{name}({text})"
    return name


def audit(conv_id: str, path: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    planner_calls: list[dict[str, Any]] = []
    models_seen: dict[str, dict[str, int]] = {}
    cold_events: list[dict[str, Any]] = []
    heavy_results: list[dict[str, Any]] = []
    slow_gaps: list[dict[str, Any]] = []

    prev_planner_ts: datetime | None = None
    prev_model: str | None = None
    pending_tools: list[str] = []
    pending_tool_cursor = 0
    pending_planner_ts: datetime | None = None

    for st in steps:
        stype = st.get("type")
        ts = parse_iso(st.get("created_at"))
        idx = st.get("step_index")

        if stype == "PLANNER_RESPONSE":
            model = str(st.get("model") or "unknown")
            fresh_in = int(st.get("input_tokens") or 0)
            cache_read = int(st.get("cache_read_tokens") or 0)
            out_tok = int(st.get("output_tokens") or 0)
            total_prompt = fresh_in + cache_read
            hit_pct = (cache_read / total_prompt * 100.0) if total_prompt > 0 else 0.0

            idle_sec = (ts - prev_planner_ts).total_seconds() if (ts and prev_planner_ts) else None
            if len(planner_calls) > 0 and total_prompt > 0 and hit_pct < 10.0:
                if prev_model and model != prev_model:
                    cause = f"模型/角色切换 ({prev_model} -> {model})"
                elif idle_sec is not None and idle_sec >= 210:
                    cause = f"闲置超时触发隐式缓存驱逐 (间隔 {int(idle_sec)}s >= 3.5m)"
                else:
                    cause = "系统提示词前缀变更（如 Orchestrator 轮切）或集群缓存驱逐"
                cold_events.append({
                    "step_index": idx,
                    "model": model,
                    "fresh_input_tokens": fresh_in,
                    "hit_pct": round(hit_pct, 1),
                    "idle_seconds": int(idle_sec) if idle_sec is not None else None,
                    "cause": cause,
                })

            bucket = models_seen.setdefault(model, {
                "calls": 0,
                "fresh_input": 0,
                "cache_read": 0,
                "output": 0,
            })
            bucket["calls"] += 1
            bucket["fresh_input"] += fresh_in
            bucket["cache_read"] += cache_read
            bucket["output"] += out_tok

            tcalls = st.get("tool_calls") or []
            pending_tools = [summarize_tool_target(tc) for tc in tcalls if isinstance(tc, dict)]
            pending_tool_cursor = 0
            pending_planner_ts = ts

            planner_calls.append({
                "step_index": idx,
                "model": model,
                "total_prompt": total_prompt,
                "fresh_input": fresh_in,
                "cache_read": cache_read,
                "output": out_tok,
                "hit_pct": round(hit_pct, 1),
                "tools": pending_tools,
            })
            prev_planner_ts = ts
            prev_model = model

        elif stype == "GENERIC":
            content = str(st.get("content") or "")
            chars = len(content)
            line_count = content.count("\n") + 1 if content else 0
            if pending_tool_cursor < len(pending_tools):
                label = pending_tools[pending_tool_cursor]
                pending_tool_cursor += 1
            elif pending_tools:
                label = pending_tools[-1]
            else:
                label = f"step #{idx}"
            if chars >= 1500:
                est_tokens = max(1, chars // 4)
                should_subagent = (
                    chars >= 12_000
                    or line_count > 320
                    or ("read_file(" in label and line_count > 300)
                )
                heavy_results.append({
                    "step_index": idx,
                    "tool": label,
                    "chars": chars,
                    "lines": line_count,
                    "est_tokens": est_tokens,
                    "should_subagent": should_subagent,
                })
            if ts and pending_planner_ts:
                dur = (ts - pending_planner_ts).total_seconds()
                if dur >= 1.5:
                    slow_gaps.append({
                        "step_index": idx,
                        "tool": label,
                        "seconds": round(dur, 2),
                    })

    heavy_results.sort(key=lambda x: x["chars"], reverse=True)
    slow_gaps.sort(key=lambda x: x["seconds"], reverse=True)

    latest_prompt = planner_calls[-1]["total_prompt"] if planner_calls else 0
    latest_hit = planner_calls[-1]["hit_pct"] if planner_calls else 0.0
    latest_model = planner_calls[-1]["model"] if planner_calls else "unknown"
    peak_prompt = max((c["total_prompt"] for c in planner_calls), default=0)

    sum_fresh = sum(c["fresh_input"] for c in planner_calls)
    sum_cache = sum(c["cache_read"] for c in planner_calls)
    sum_prompt = sum_fresh + sum_cache
    weighted_hit = round((sum_cache / sum_prompt * 100.0), 1) if sum_prompt > 0 else 0.0

    # Determine action verdict
    distinct_models = list(models_seen.keys())
    if latest_prompt >= HANDOFF_SWEET_SPOT:
        verdict = "立即执行 handoff 切新会话"
        verdict_reason = (
            f"当前上下文已达 {latest_prompt:,} tokens（超过 {HANDOFF_SWEET_SPOT:,} 换仓甜点线，"
            f"逼近 {LONG_CONTEXT_TIER:,} 长上下文阈值），继续堆叠一旦掉缓存将承受高额重算。"
        )
    elif len(distinct_models) > 1 or len(cold_events) >= 2:
        verdict = "锁定 Direct 单模型（或执行 handoff 重置干净前缀）"
        verdict_reason = (
            f"本会话发生 {len(cold_events)} 次中途冷启动重算 / 涉及 {len(distinct_models)} 个模型标识 "
            f"({', '.join(distinct_models)})，建议保持单模型 Direct 直连。"
        )
    else:
        verdict = "继续当前会话"
        verdict_reason = (
            f"当前上下文 {latest_prompt:,} tokens 处于 {HANDOFF_SWEET_SPOT:,} 安全甜点区内，"
            f"累计加权缓存命中率 {weighted_hit}%，前缀健康。"
        )

    quota_notes: list[str] = []
    if "carbon" in latest_model.lower():
        quota_notes.append(
            "当前使用 Gemini 4 Carbon：首发半价将于 2026-12-01 UTC 结束并翻倍至 $4/$20 标准重型权重；"
            "Ultra 订阅下日常全栈建议切 Gemini 4 Neon (High/Medium)，批量跑量建议切 Hydrogen (High)。"
        )
    if "xhigh" in latest_model.lower():
        quota_notes.append(
            "当前开启 XHigh 超高思考档：思考输出权重是热缓存读取的 100 倍，非疑难攻坚建议降回 High/Medium。"
        )
    if not quota_notes:
        quota_notes.append("当前模型档位与直连模式匹配良好，注意闲置勿超 4 分钟以保住 95% 热缓存减免。")

    return {
        "conversation_id": conv_id,
        "transcript_path": str(path),
        "user_turns": sum(1 for s in steps if s.get("type") == "USER_INPUT"),
        "model_calls": len(planner_calls),
        "latest_model": latest_model,
        "latest_prompt_tokens": latest_prompt,
        "peak_prompt_tokens": peak_prompt,
        "latest_cache_hit_pct": latest_hit,
        "weighted_cache_hit_pct": weighted_hit,
        "models_breakdown": models_seen,
        "cold_cache_events": cold_events,
        "top_heavy_tool_results": heavy_results[:5],
        "top_slow_tool_steps": slow_gaps[:5],
        "quota_notes": quota_notes,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Antigravity session transcript telemetry.")
    parser.add_argument("--conversation-id", default="", help="Conversation UUID")
    parser.add_argument("--transcript", default="", help="Explicit path to transcript.jsonl")
    args = parser.parse_args()

    conv_id, path = resolve_transcript(
        args.conversation_id.strip() or None,
        args.transcript.strip() or None,
    )
    result = audit(conv_id, path)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
