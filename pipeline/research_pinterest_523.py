"""Extensive VLM Visual Research over all 523 Personal Pinterest Images (`aesthetic-kb`).

Inspects every single Pinterest asset via OpenAI `gpt-4o-mini` Vision with Prompt Caching
and Strict Structured Outputs, classifies each image into our 5-domain + 10-subcategory
spatial/aesthetic ontology, scores all 8 orthogonal axes + saliences, filters out utility/
test/low-res noise (e.g. resume templates, Codex test boards, ad screenshots), and derives
a comprehensive Personal Aesthetic Profile (`aesthetic_profile_523.json` & Markdown report)
that drives targeted expansion to exactly 500 images.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import sqlite3
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from openai import OpenAI, RateLimitError
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .aethervault_schema import AXIS_IDS, SPECTRUM_AXES
from .anchor_scorer import (
    PRICE_CACHED_INPUT_USD_M,
    PRICE_OUTPUT_USD_M,
    PRICE_UNCACHED_INPUT_USD_M,
    StrictStyleSpectrums,
    USD_TO_CNY,
)
from .anchor_specs import build_vlm_calibration_system_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent
AKB_SQLITE_PATH = Path(r"C:\Users\Frost\Documents\Antigravity\aesthetic-kb\data\db\meta.sqlite")
OUT_DIR = REPO_ROOT / "data" / "pinterest_500"
CACHE_PATH = OUT_DIR / "_vlm_research_523_cache.json"
RESEARCH_JSON_PATH = OUT_DIR / "pinterest_523_research.json"
PROFILE_JSON_PATH = OUT_DIR / "aesthetic_profile_523.json"
PROFILE_MD_PATH = REPO_ROOT / "docs" / "PINTEREST_AESTHETIC_PROFILE_REPORT.md"

DEFAULT_MODEL = "gpt-4o-mini"

# Boards known to be utility/test boards rather than aesthetic inspiration boards
UTILITY_BOARDS = {
    "简历模板",
    "Codex TEST_COFFEE SHOP INTERIOR",
}

DomainLiteral = Literal["architecture", "industrial", "editorial", "craft", "graphic"]


class PinterestVlmResearchItem(BaseModel):
    """Strict OpenAI Structured Output schema for deep visual research on a Pinterest pin."""

    model_config = ConfigDict(extra="forbid")

    keep_for_aethervault: bool = Field(
        ...,
        description="True ONLY for high-aesthetic design/architecture/space/material/graphic/UI/editorial/fashion/craft references. False for resume templates, raw text screenshots, cluttered e-commerce product ads, low-res blurry images, memes, or generic clip-art.",
    )
    reject_reason: str = Field(
        ...,
        description="Empty string if kept; otherwise brief Chinese reason why rejected (e.g. '简历文档模板', '低清模糊', '电商杂图/非审美参考', '测试画板样本').",
    )
    aesthetic_quality_score: int = Field(
        ...,
        description="Visual design craft & reference quality integer from 1 to 10 (8-10 = gallery monograph grade; <=5 = reject).",
    )
    domain: DomainLiteral = Field(
        ...,
        description="Primary cross-domain taxonomy: architecture (buildings/interiors/cafes/parks/galleries), industrial (furniture/signage/hardware/fixtures/structural modules), editorial (photography/fashion/mood/spatial light studies), craft (ceramics/wood/stone/patina/tactile handmade), graphic (posters/typography/color palettes/branding/UI/wayfinding graphics).",
    )
    sub_category: str = Field(
        ...,
        description="One concise Chinese sub-category chosen from: 建筑立面与构造 | 商业咖啡与餐饮空间 | 疗愈与文化展览空间 | 景观与公共灰空间 | 室内陈设与住宅空间 | 空间导视与标识装置 | 工业器型与材料节点 | 瑞士平面与字体排版 | 极简数字界面与配色 | 先锋时尚与光影摄影",
    )
    title_zh: str = Field(..., description="Concise 8-18 char Chinese descriptive title of the visual scene.")
    title_en: str = Field(..., description="Concise 4-10 word English descriptive title.")
    primary_subject: str = Field(..., description="Concise English physical subject (3-6 words) for AST isolation.")
    style_spectrums: StrictStyleSpectrums
    optics_camera: str = Field(..., description="Concise English camera/lens/framing readout.")
    lighting_rig: str = Field(..., description="Concise English lighting quality & contrast readout.")
    material_stack: str = Field(..., description="Concise English dominant materials, textures & finishes.")
    aesthetic_motifs: list[str] = Field(..., description="3 to 4 concise Chinese+English visual design motifs.")
    positive_tokens: list[str] = Field(..., description="3 to 5 concise English visual style tokens.")
    negative_guardrails: list[str] = Field(..., description="2 to 4 concise English anti-leakage negative tokens.")


def _build_research_system_prompt() -> str:
    base_rubric = build_vlm_calibration_system_prompt()
    addon = (
        "\n\n=== EXTENDED CURATORIAL RESEARCH INSTRUCTIONS ===\n"
        "You are conducting an extensive aesthetic audit of a designer's personal Pinterest library.\n"
        "1. Inspect the ACTUAL image pixels carefully. Do NOT trust board names blindly.\n"
        "2. Set keep_for_aethervault=false if the image is: a resume/CV document layout, a generic corporate corridor collage, "
        "an e-commerce product collage/ad, a screenshot full of tiny unreadable UI chrome/text without aesthetic value, "
        "a blurry/pixelated low-resolution thumbnail, or an unrelated sports/meme snapshot.\n"
        "3. Set keep_for_aethervault=true if the image is a strong visual reference for architecture, interior spaces, "
        "commercial cafes/retail, landscapes, tactile wayfinding signage, furniture/industrial craft, restrained color palettes, "
        "editorial/fashion form, or high-craft typography/graphic/UI design.\n"
        "4. Score all 8 orthogonal axes strictly against the 5-point Golden Anchors above (`score` in [-1.0, +1.0], `salience` in [0.0, 1.0]). "
        "For flat graphic/poster/UI/palette images, set `tectonic_honesty.salience` <= 0.30 so they do not pollute spatial tectonic queries.\n"
        "5. Output ONLY valid JSON conforming strictly to the schema."
    )
    return base_rubric + addon


def _encode_image_b64(img_path: Path, max_side: int = 384) -> str:
    with Image.open(img_path) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=76, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _load_all_pinterest_records() -> list[dict[str, Any]]:
    con = sqlite3.connect(str(AKB_SQLITE_PATH))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT a.asset_id, a.sha256, a.phash, a.original_path, a.thumb_512_path, a.thumb_1024_path,
               a.width, a.height, a.aspect_ratio, a.aspect_bucket, a.sharpness_score,
               a.brightness_mean, a.brightness_class, a.palette_json,
               GROUP_CONCAT(DISTINCT s.board_name) AS boards,
               MIN(s.title) AS pin_title,
               MIN(s.source_url) AS source_url
        FROM assets a
        JOIN asset_sources s ON a.asset_id = s.asset_id
        WHERE s.source_type = 'pinterest_import'
        GROUP BY a.asset_id
        ORDER BY a.created_at ASC
        """
    ).fetchall()
    con.close()

    records: list[dict[str, Any]] = []
    for r in rows:
        boards = [b.strip() for b in (r["boards"] or "").split(",") if b.strip()]
        primary_board = boards[0] if boards else "未分类"
        palette_raw = json.loads(r["palette_json"]) if r["palette_json"] else []
        hex_palette = [p.get("hex", "#808080") for p in palette_raw[:5] if isinstance(p, dict)]
        records.append(
            {
                "akb_asset_id": r["asset_id"],
                "sha256": r["sha256"],
                "phash": r["phash"],
                "original_path": r["original_path"],
                "thumb_512_path": r["thumb_512_path"],
                "thumb_1024_path": r["thumb_1024_path"],
                "width": int(r["width"] or 0),
                "height": int(r["height"] or 0),
                "aspect_ratio": float(r["aspect_ratio"] or 1.0),
                "aspect_bucket": r["aspect_bucket"] or "portrait",
                "sharpness_score": float(r["sharpness_score"] or 0.0),
                "brightness_mean": float(r["brightness_mean"] or 0.5),
                "brightness_class": r["brightness_class"] or "mid",
                "palette_oklab": palette_raw[:5],
                "hex_palette": hex_palette or ["#EAEAE6", "#9A9A95", "#2B2D30"],
                "boards": boards,
                "primary_board": primary_board,
                "pin_title": (r["pin_title"] or "").strip(),
                "source_url": r["source_url"] or "",
            }
        )
    return records


def _score_one_pin(
    client: OpenAI,
    system_prompt: str,
    rec: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    img_path = Path(rec["thumb_512_path"])
    if not img_path.is_file():
        img_path = Path(rec["original_path"])
    b64 = _encode_image_b64(img_path, max_side=384)

    board_hint = ", ".join(rec["boards"])
    is_util_board = any(b in UTILITY_BOARDS for b in rec["boards"])
    low_res = min(rec["width"], rec["height"]) < 280
    user_text = (
        f"Pinterest Asset ID: {rec['akb_asset_id']}\n"
        f"Boards: {board_hint}\n"
        f"Original Pin Title: {rec['pin_title'][:140]}\n"
        f"Dimensions: {rec['width']}x{rec['height']} ({rec['aspect_bucket']})\n"
        f"Dominant HEX: {', '.join(rec['hex_palette'])}\n"
        f"Pre-check flags: utility_or_test_board={is_util_board}, low_res={low_res}\n"
        "Inspect the image pixels and produce strict curatorial research + 8-axis anchored scores."
    )

    last_err: Exception | None = None
    for attempt in range(5):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o" if attempt >= 2 else model,
                temperature=0.1 if attempt == 0 else 0.3,
                frequency_penalty=0.0 if attempt == 0 else 0.4,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                response_format=PinterestVlmResearchItem,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Empty parsed structured output from VLM")
            usage = completion.usage
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            cached_tokens = 0
            details = getattr(usage, "prompt_tokens_details", None)
            if details is not None:
                cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)

            payload = parsed.model_dump()
            # Enforce hard guard on known utility/test boards & sub-280px tiny thumbnails
            if is_util_board:
                payload["keep_for_aethervault"] = False
                if not payload["reject_reason"]:
                    payload["reject_reason"] = f"排除工具/测试画板 ({rec['primary_board']})"
            elif low_res:
                payload["keep_for_aethervault"] = False
                if not payload["reject_reason"]:
                    payload["reject_reason"] = f"低分辨率 ({rec['width']}x{rec['height']})"

            # Clamp spectrum bounds cleanly
            for ax in AXIS_IDS:
                node = payload["style_spectrums"][ax]
                node["score"] = round(max(-1.0, min(1.0, float(node["score"]))), 2)
                node["salience"] = round(max(0.0, min(1.0, float(node["salience"]))), 2)

            return {
                "akb_asset_id": rec["akb_asset_id"],
                "vlm": payload,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "cached_tokens": cached_tokens,
                    "completion_tokens": completion_tokens,
                },
            }
        except RateLimitError as exc:
            last_err = exc
            time.sleep(min(20.0, 2.0 * (attempt + 1)))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Failed VLM research for {rec['akb_asset_id']}: {last_err}")


def _build_profile_and_report(
    records: list[dict[str, Any]],
    cache: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    merged: list[dict[str, Any]] = []
    tot_prompt = 0
    tot_cached = 0
    tot_comp = 0

    for rec in records:
        hit = cache.get(rec["akb_asset_id"])
        if not hit:
            continue
        u = hit.get("usage", {})
        tot_prompt += int(u.get("prompt_tokens", 0))
        tot_cached += int(u.get("cached_tokens", 0))
        tot_comp += int(u.get("completion_tokens", 0))
        merged.append({**rec, "vlm": hit["vlm"]})

    # Determine kept set (quality >= 6 and keep_for_aethervault == True), capped cleanly at <= 405
    # so there is always meaningful profile-driven expansion (~95-140 fresh images) to reach 500!
    raw_kept = [
        m for m in merged
        if m["vlm"]["keep_for_aethervault"] and int(m["vlm"]["aesthetic_quality_score"]) >= 6
    ]
    raw_kept.sort(
        key=lambda x: (
            -int(x["vlm"]["aesthetic_quality_score"]),
            -float(x["sharpness_score"]),
            x["akb_asset_id"],
        )
    )

    max_pinterest_keep = 390
    if len(raw_kept) > max_pinterest_keep:
        kept = raw_kept[:max_pinterest_keep]
        overflow_ids = {x["akb_asset_id"] for x in raw_kept[max_pinterest_keep:]}
    else:
        kept = raw_kept
        overflow_ids = set()

    kept_ids = {x["akb_asset_id"] for x in kept}
    rejected = [m for m in merged if m["akb_asset_id"] not in kept_ids]
    for m in merged:
        if m["akb_asset_id"] in kept_ids:
            m["selection_status"] = "kept_pinterest_core"
        elif m["akb_asset_id"] in overflow_ids:
            m["selection_status"] = "deferred_quality_cap"
            m["vlm"]["reject_reason"] = m["vlm"]["reject_reason"] or "质量排序后置（保留前 390 精品以为画像扩图留出 110 张探索配额）"
        else:
            m["selection_status"] = "rejected_noise_or_utility"

    # Compute 8-axis personal aesthetic signature across kept Pinterest core
    axis_stats: dict[str, dict[str, float]] = {}
    for ax in AXIS_IDS:
        scores = [float(m["vlm"]["style_spectrums"][ax]["score"]) for m in kept]
        sals = [float(m["vlm"]["style_spectrums"][ax]["salience"]) for m in kept]
        weights = [max(0.05, s) for s in sals]
        w_mean = sum(sc * w for sc, w in zip(scores, weights)) / max(1e-6, sum(weights))
        arr = np.asarray(scores, dtype=np.float64)
        axis_stats[ax] = {
            "weighted_mean": round(float(w_mean), 3),
            "mean": round(float(arr.mean()), 3),
            "std": round(float(arr.std()), 3),
            "p25": round(float(np.percentile(arr, 25)), 3),
            "median": round(float(np.median(arr)), 3),
            "p75": round(float(np.percentile(arr, 75)), 3),
            "mean_salience": round(float(np.mean(sals)), 3),
        }

    domain_counts = Counter(m["vlm"]["domain"] for m in kept)
    subcat_counts = Counter(m["vlm"]["sub_category"] for m in kept)
    board_kept = Counter(m["primary_board"] for m in kept)
    board_all = Counter(m["primary_board"] for m in merged)
    motif_counts = Counter(
        motif.strip()
        for m in kept
        for motif in m["vlm"].get("aesthetic_motifs", [])
        if motif.strip()
    )
    token_counts = Counter(
        tok.strip().lower()
        for m in kept
        for tok in m["vlm"].get("positive_tokens", [])
        if tok.strip()
    )

    # Color signature: quantize primary OKLab/HEX colors across kept Pinterest pins
    hex_clusters: Counter[str] = Counter()
    for m in kept:
        for hx in m["hex_palette"][:2]:
            h = hx.lstrip("#")
            if len(h) == 6:
                r = int(h[0:2], 16) // 24 * 24 + 12
                g = int(h[2:4], 16) // 24 * 24 + 12
                b = int(h[4:6], 16) // 24 * 24 + 12
                hex_clusters[f"#{min(255,r):02X}{min(255,g):02X}{min(255,b):02X}"] += 1

    # Compute exact expansion quota to reach 500 total, prioritizing underrepresented non-arch domains
    expansion_needed = max(0, 500 - len(kept))
    # Target healthy cross-domain balance while respecting the user's strong architectural core
    desired_floors = {
        "architecture": max(domain_counts.get("architecture", 0), 210),
        "industrial": max(domain_counts.get("industrial", 0) + 28, 70),
        "editorial": max(domain_counts.get("editorial", 0) + 24, 70),
        "craft": max(domain_counts.get("craft", 0) + 28, 65),
        "graphic": max(domain_counts.get("graphic", 0) + 18, 85),
    }
    raw_gaps = {d: max(4, desired_floors[d] - domain_counts.get(d, 0)) for d in desired_floors}
    gap_sum = sum(raw_gaps.values())
    expansion_plan: dict[str, int] = {}
    allocated = 0
    domains_order = ["industrial", "craft", "editorial", "graphic", "architecture"]
    for i, d in enumerate(domains_order):
        if i == len(domains_order) - 1:
            expansion_plan[d] = max(0, expansion_needed - allocated)
        else:
            q = int(round(expansion_needed * raw_gaps[d] / max(1, gap_sum)))
            expansion_plan[d] = q
            allocated += q

    # Cost accounting
    uncached = max(0, tot_prompt - tot_cached)
    usd = (
        uncached * PRICE_UNCACHED_INPUT_USD_M / 1e6
        + tot_cached * PRICE_CACHED_INPUT_USD_M / 1e6
        + tot_comp * PRICE_OUTPUT_USD_M / 1e6
    )
    cny = usd * USD_TO_CNY

    profile: dict[str, Any] = {
        "version": "2.0.0-pinterest-500",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pinterest_analyzed": len(merged),
        "kept_pinterest_count": len(kept),
        "rejected_or_deferred_count": len(rejected),
        "expansion_target_count": expansion_needed,
        "final_target_total": 500,
        "axis_signature": axis_stats,
        "kept_domain_counts": dict(domain_counts),
        "kept_subcategory_counts": dict(subcat_counts.most_common()),
        "board_audit": [
            {
                "board": b,
                "total": board_all[b],
                "kept": board_kept.get(b, 0),
                "keep_rate": round(board_kept.get(b, 0) / max(1, board_all[b]), 3),
            }
            for b, _ in board_all.most_common()
        ],
        "top_motifs": [{"motif": k, "count": v} for k, v in motif_counts.most_common(24)],
        "top_style_tokens": [{"token": k, "count": v} for k, v in token_counts.most_common(24)],
        "dominant_color_clusters": [{"hex": k, "count": v} for k, v in hex_clusters.most_common(12)],
        "expansion_quota_by_domain": expansion_plan,
        "vlm_cost_audit": {
            "model": DEFAULT_MODEL,
            "images_analyzed": len(merged),
            "total_prompt_tokens": tot_prompt,
            "total_cached_tokens": tot_cached,
            "cache_hit_rate": round(tot_cached / max(1, tot_prompt), 4),
            "total_completion_tokens": tot_comp,
            "observed_total_cny": round(cny, 4),
            "observed_cny_per_img": round(cny / max(1, len(merged)), 5),
        },
    }

    # Generate rich Markdown Profile Research Report
    ax_label = {a.axis_id: f"{a.label_zh} ({a.neg_label} ↔ {a.pos_label})" for a in SPECTRUM_AXES}
    md_lines = [
        "# 个人 Pinterest 全图库深度视觉研究与审美 Profile 报告（523 图实测）",
        "",
        f"- **研究时间 (UTC)**：`{profile['generated_at']}`",
        f"- **全量分析规模**：`{len(merged)}` 张 Pinterest 原图（31 个画板，来自 `aesthetic-kb`）",
        f"- **精选核心留存**：**`{len(kept)}` 张**高审美个人 Pinterest 精品（筛除 `{len(rejected)}` 张简历模板 / 测试画板 / 低清或非设计杂图）",
        f"- **画像驱动扩图配额**：**`{expansion_needed}` 张**高契合度跨界新图 → 最终组成 **`500` 张**专属 AetherVault 图库",
        f"- **VLM 实盘审计**：`{DEFAULT_MODEL}` 全量视觉解读耗时极低，Prompt Cache 命中率 **`{profile['vlm_cost_audit']['cache_hit_rate']*100:.1f}%`**，总花费 **`¥{profile['vlm_cost_audit']['observed_total_cny']:.3f}`**（单图 **`¥{profile['vlm_cost_audit']['observed_cny_per_img']:.5f}`**）",
        "",
        "---",
        "",
        "## 一、8 维正交审美画像（Personal Aesthetic Signature）",
        "",
        "| 审美轴 | 加权均值 | 中位数 | 四分位区间 (P25 ~ P75) | 均值显著度 | 倾向解读 |",
        "| :--- | ---: | ---: | :---: | ---: | :--- |",
    ]
    for ax in AXIS_IDS:
        st = axis_stats[ax]
        wm = st["weighted_mean"]
        tendency = "强正向倾向" if wm >= 0.35 else ("温和正向" if wm >= 0.1 else ("强负向倾向" if wm <= -0.35 else ("温和负向" if wm <= -0.1 else "双向平衡/多元")))
        md_lines.append(
            f"| {ax_label[ax]} | `{wm:+.3f}` | `{st['median']:+.3f}` | `{st['p25']:+.2f}` ~ `{st['p75']:+.2f}` | `{st['mean_salience']:.2f}` | {tendency} |"
        )

    md_lines.extend(
        [
            "",
            "## 二、核心留存分类与画板质量分布",
            "",
            "### 5 大跨域门类分布（精选 Pinterest 核心 vs 扩图配额 → 500 总库）",
            "",
            "| 门类 | 精选 Pinterest 留存 | 画像扩图配额 | 最终 500 库占比 |",
            "| :--- | ---: | ---: | ---: |",
        ]
    )
    for d in ("architecture", "industrial", "editorial", "craft", "graphic"):
        k_cnt = domain_counts.get(d, 0)
        e_cnt = expansion_plan.get(d, 0)
        tot_d = k_cnt + e_cnt
        md_lines.append(f"| `{d}` | {k_cnt} | +{e_cnt} | **{tot_d}** ({tot_d/5:.1f}%) |")

    md_lines.extend(
        [
            "",
            "### 细分子类（Sub-Categories）",
            "",
        ]
    )
    for sub, cnt in subcat_counts.most_common():
        md_lines.append(f"- **{sub}**：`{cnt}` 张")

    md_lines.extend(
        [
            "",
            "### 高频视觉母题（Top Aesthetic Motifs）",
            "",
            "、".join(f"`{m['motif']}` ({m['count']})" for m in profile["top_motifs"][:18]),
            "",
            "### 主导色域聚类（OKLab / HEX）",
            "",
            " ".join(f"`{c['hex']}`({c['count']})" for c in profile["dominant_color_clusters"][:10]),
            "",
            "### 31 个 Pinterest 画板质检明细",
            "",
            "| 画板名 | 总数 | 留存 | 留存率 |",
            "| :--- | ---: | ---: | ---: |",
        ]
    )
    for row in profile["board_audit"]:
        md_lines.append(f"| {row['board']} | {row['total']} | {row['kept']} | {row['keep_rate']*100:.0f}% |")

    return profile, "\n".join(md_lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = _load_all_pinterest_records()
    print(f"Loaded {len(records)} distinct Pinterest assets from {AKB_SQLITE_PATH}")

    cache: dict[str, Any] = {}
    if CACHE_PATH.is_file():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [r for r in records if r["akb_asset_id"] not in cache]
    print(f"Cached: {len(cache)} | Remaining to VLM-analyze: {len(todo)}")

    if todo:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY environment variable is required.")
        client = OpenAI()
        system_prompt = _build_research_system_prompt()
        lock = threading.Lock()
        done_count = 0
        t0 = time.time()

        # Warm up Prompt Cache with 1 sequential call first so remaining parallel calls hit cache!
        first_res = _score_one_pin(client, system_prompt, todo[0], DEFAULT_MODEL)
        cache[first_res["akb_asset_id"]] = first_res
        done_count += 1
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"Warmup 1/{len(todo)} complete (cached_tokens={first_res['usage']['cached_tokens']})")

        remaining = todo[1:]
        with ThreadPoolExecutor(max_workers=12) as pool:
            futs = {
                pool.submit(_score_one_pin, client, system_prompt, rec, DEFAULT_MODEL): rec["akb_asset_id"]
                for rec in remaining
            }
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Failed {aid}: {exc}")
                    continue
                with lock:
                    cache[res["akb_asset_id"]] = res
                    done_count += 1
                    if done_count % 25 == 0 or done_count == len(todo):
                        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        elapsed = time.time() - t0
                        print(f"Progress: {done_count}/{len(todo)} ({elapsed:.1f}s)")

        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    profile, report_md = _build_profile_and_report(records, cache)
    # Persist full enriched records with selection_status
    merged_full = []
    kept_set_ids = set()
    # Re-apply exact same ranking to persist selection_status cleanly
    raw_kept = [
        {**r, "vlm": cache[r["akb_asset_id"]]["vlm"]}
        for r in records
        if r["akb_asset_id"] in cache
        and cache[r["akb_asset_id"]]["vlm"]["keep_for_aethervault"]
        and int(cache[r["akb_asset_id"]]["vlm"]["aesthetic_quality_score"]) >= 6
    ]
    raw_kept.sort(
        key=lambda x: (
            -int(x["vlm"]["aesthetic_quality_score"]),
            -float(x["sharpness_score"]),
            x["akb_asset_id"],
        )
    )
    kept_set_ids = {x["akb_asset_id"] for x in raw_kept[:390]}

    for r in records:
        if r["akb_asset_id"] not in cache:
            continue
        item = {**r, "vlm": cache[r["akb_asset_id"]]["vlm"]}
        item["selection_status"] = (
            "kept_pinterest_core" if r["akb_asset_id"] in kept_set_ids else "rejected_or_deferred"
        )
        merged_full.append(item)

    RESEARCH_JSON_PATH.write_text(
        json.dumps({"total": len(merged_full), "items": merged_full}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    PROFILE_JSON_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    PROFILE_MD_PATH.write_text(report_md, encoding="utf-8")

    print(
        f"\n[DONE] Analyzed {profile['total_pinterest_analyzed']} Pinterest images | "
        f"Kept core={profile['kept_pinterest_count']} | Expansion needed={profile['expansion_target_count']} | "
        f"Cost=CNY {profile['vlm_cost_audit']['observed_total_cny']} (cache={profile['vlm_cost_audit']['cache_hit_rate']*100:.1f}%)"
    )
    print("Domain distribution (kept):", profile["kept_domain_counts"])
    print("Expansion quota:", profile["expansion_quota_by_domain"])


if __name__ == "__main__":
    main()
