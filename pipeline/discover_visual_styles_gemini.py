"""Lightweight Option B: Unbiased Open Visual Style Discovery across all 500 Images via Gemini.

Feeds raw `.webp` image pixels directly to Gemini (`gemini-4-hydrogen` by default,
configurable via `--model` e.g. `gemini-3.5-flash-lite` / `gemma-4-31b-it`) with ZERO
user-profile bias, ZERO board-name leakage, and ZERO forced architectural-ism enum.

Outputs:
  - Incremental raw discovery cache: `data/pinterest_500/_gemini_open_discovery_500.json`
  - Human-readable discovery report: `docs/GEMINI_VISUAL_DISCOVERY_REPORT.md`
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_SHOWCASE_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_open_discovery_500.json"
REPORT_MD_PATH = REPO_ROOT / "docs" / "GEMINI_VISUAL_DISCOVERY_REPORT.md"

DomainLiteral = Literal[
    "architecture",
    "interior",
    "landscape",
    "industrial",
    "craft",
    "graphic_typography",
    "illustration_character",
    "fashion_photography",
]

DOMAIN_ZH: dict[str, str] = {
    "architecture": "建筑设计",
    "interior": "室内设计",
    "landscape": "景观空间",
    "industrial": "工业与家具设计",
    "craft": "器物与材质工艺",
    "graphic_typography": "平面、字体、导视与UI",
    "illustration_character": "插画、角色与艺术图形",
    "fashion_photography": "时尚穿搭与概念摄影",
}


class OpenVisualDiscovery(BaseModel):
    """Unbiased visual discovery schema (free canonical English style, no forced architectural -ism)."""

    visual_domain: DomainLiteral = Field(
        ...,
        description=(
            "Primary visual domain strictly from pixels: "
            "architecture (exterior building/facade/pavilion), "
            "interior (indoor rooms/cafes/offices/galleries), "
            "landscape (parks/courtyards/gardens/urban paths), "
            "industrial (furniture/chairs/appliances/lighting fixtures/hardware), "
            "craft (ceramics/pottery/textiles/material swatches/handcrafted objects), "
            "graphic_typography (posters/typography/signage/wayfinding/UI/color palettes/logos), "
            "illustration_character (anime/character sheets/fashion illustrations/abstract line drawings/digital paintings), "
            "fashion_photography (real clothing/runway/editorial portraits/architectural light photography)."
        ),
    )
    medium: str = Field(
        ...,
        description="Concise canonical English medium (2-4 words), e.g. 'Architectural Photography', 'Experimental Typography Poster', 'Anime Character Sheet', 'UI / Color Palette', 'Wayfinding Signage', 'Watercolor Fashion Illustration', 'Product Photography', 'Ceramic Photography', 'Abstract Line Art'.",
    )
    free_style_primary: str = Field(
        ...,
        description="Most accurate, widely recognized canonical English art/design/illustration style term that vision & diffusion models natively understand (2-4 words, Title Case). Do NOT force 'Minimalism' or 'Swiss Style' on anime, pop art, experimental Chinese typography, or Y2K graphics! Use 'Purely Functional' if there is no distinct art movement.",
    )
    free_style_secondary: str = Field(
        default="",
        description="Optional secondary canonical English style nuance (empty string if none).",
    )
    is_canonical_ism: bool = Field(
        ...,
        description="True ONLY if the image genuinely exemplifies a recognized design/art movement (e.g. Modernism, High-Tech, Brutalism, Wabi-Sabi, Bauhaus, Swiss Style, Pop Art, Art Deco); False if primarily functional, commercial UI/signage, or medium-driven illustration.",
    )
    content_typology_zh: str = Field(
        ...,
        description="Concise Chinese subject/content category (2-6 chars), e.g. '建筑立面', '汉字实验字体', '二次元机能立绘', '水彩时尚插画', '空间导视', '灯具细节', '工业仪器', '粗陶茶器', '配色色卡'.",
    )
    visual_traits: list[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="3 short concrete English visual traits directly visible in the pixels.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0 in the domain and style classification.",
    )


SYSTEM_PROMPT = """You are an objective, encyclopedic art, architecture, industrial design, typography, and illustration historian.
Inspect ONLY the provided image pixels. You have NO prior context about who saved this image.

CRITICAL RULES:
1. NEVER default to "Minimalism" or "Swiss Style" unless the image truly exemplifies those movements.
2. Distinguish real design/architecture movements from illustration/character/typography styles:
   - Anime character turnaround / techwear character -> visual_domain='illustration_character', free_style_primary e.g. 'Anime Techwear' or 'Cel-Shaded Anime'.
   - High-saturation Japanese pop illustration (e.g. Mika Pikazo) -> visual_domain='illustration_character', free_style_primary='Pop Art Anime' or 'Hyper-Color Illustration'.
   - Experimental / pixel / cross-stitch / geometric Chinese character typography -> visual_domain='graphic_typography', free_style_primary='Experimental Typography' / 'Y2K Acid Typography' / 'Neo-Chinese Typography' / 'Geometric Modular Typography' (NOT Swiss Style unless it is genuinely Swiss grid + grotesque typography!).
   - Watercolor / ink fashion sketches or abstract line drawings -> visual_domain='illustration_character', free_style_primary='Watercolor Fashion Illustration' / 'Abstract Line Art' / 'Ink Sketch'.
   - Architecture/Interior/Industrial/Craft -> use precise canonical terms: 'Modernism', 'Minimalism', 'High-Tech', 'Brutalism', 'Wabi-Sabi', 'Scandinavian', 'Japanese Zen', 'Bauhaus', 'Braun Functionalism', 'Mid-Century Modern', 'Organic Modernism', 'Biophilic Architecture', 'Industrial Minimalism', etc.
   - Pure color palette cards, utilitarian wayfinding signs, or neutral UI screens without an art movement -> set is_canonical_ism=False and use an honest label like 'Color Palette System', 'Minimalist Wayfinding', or 'Flat UI Design'.
3. Keep `free_style_primary` clean, standardized Title Case (2-3 words max) so identical styles cluster naturally across 500 images."""


def _make_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required.")
    return genai.Client(api_key=key)


def _discover_one(
    client: genai.Client,
    model: str,
    asset: dict[str, Any],
    img_path: Path,
) -> tuple[str, dict[str, Any], dict[str, int]]:
    img_bytes = img_path.read_bytes()
    mime = "image/webp" if img_path.suffix.lower() == ".webp" else "image/jpeg"

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type=mime),
                    "Inspect this image purely from its pixels and output the objective OpenVisualDiscovery JSON.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=OpenVisualDiscovery,
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW,
                    ),
                ),
            )
            text = (resp.text or "").strip()
            parsed = OpenVisualDiscovery.model_validate_json(text)
            usage = getattr(resp, "usage_metadata", None)
            in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
            out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
            thk_tok = int(getattr(usage, "thoughts_token_count", 0) or 0)
            return (
                asset["asset_id"],
                parsed.model_dump(),
                {"input_tokens": in_tok, "output_tokens": out_tok, "thought_tokens": thk_tok},
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))

    raise RuntimeError(f"Gemini discovery failed for {asset['asset_id']}: {last_err}")


def _write_report(
    model: str,
    assets: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    by_id = {a["asset_id"]: a for a in assets}
    dom_counts: Counter[str] = Counter()
    style_by_dom: dict[str, Counter[str]] = defaultdict(Counter)
    medium_by_dom: dict[str, Counter[str]] = defaultdict(Counter)
    typo_by_dom: dict[str, Counter[str]] = defaultdict(Counter)
    global_styles: Counter[str] = Counter()
    ism_counts: Counter[bool] = Counter()
    confs: list[float] = []

    for a in assets:
        aid = a["asset_id"]
        rec = cache.get(aid)
        if not rec:
            continue
        dom = rec["visual_domain"]
        st = " ".join(rec["free_style_primary"].strip().split())
        med = " ".join(rec["medium"].strip().split())
        typ = rec["content_typology_zh"].strip()
        dom_counts[dom] += 1
        style_by_dom[dom][st] += 1
        medium_by_dom[dom][med] += 1
        typo_by_dom[dom][typ] += 1
        global_styles[st] += 1
        ism_counts[bool(rec["is_canonical_ism"])] += 1
        confs.append(float(rec.get("confidence", 0.0)))

    avg_conf = sum(confs) / max(1, len(confs))

    lines: list[str] = [
        "# 轻量化 B · Gemini 视觉直读开放摸底报告（500 图零偏见实测）",
        "",
        f"- **视觉模型**：`{model}`（Thinking Level: `LOW`，纯原图 `.webp` 直读，零画板/零个人画像偏见）",
        f"- **覆盖规模**：`{len(confs)} / {len(assets)}` 张（平均置信度 `{avg_conf:.3f}`）",
        f"- **是否属于正式艺术/设计主义 (`is_canonical_ism`)**：是 `{ism_counts[True]}` 张（`{ism_counts[True]/max(1,len(confs))*100:.1f}%`） · 否/媒介或功能导向 `{ism_counts[False]}` 张（`{ism_counts[False]/max(1,len(confs))*100:.1f}%`）",
        f"- **自然长出的独立风格词总数**：`{len(global_styles)}` 个（Top 25 覆盖 `{sum(c for _, c in global_styles.most_common(25))}` / `{len(confs)}` 张 = `{sum(c for _, c in global_styles.most_common(25))/max(1,len(confs))*100:.1f}%`）",
        f"- **本次运行统计**：耗时 `{stats['elapsed_s']:.1f}s` · 新请求 `{stats['run_count']}` 张 · Input `{stats['input_tokens']:,}` tok · Output `{stats['output_tokens']:,}` tok · Thought `{stats['thought_tokens']:,}` tok",
        "",
        "---",
        "",
        "## 一、8 大真实视觉域分布（纯看图像素重新划分）",
        "",
        "| 视觉域 (`visual_domain`) | 中文名 | 数量 | 占比 | 该域 Top 自然风格词 |",
        "| :--- | :--- | ---: | ---: | :--- |",
    ]
    for dom, cnt in dom_counts.most_common():
        top_st = " · ".join(f"`{s}` ({c})" for s, c in style_by_dom[dom].most_common(5))
        lines.append(
            f"| `{dom}` | {DOMAIN_ZH.get(dom, dom)} | {cnt} | {cnt/max(1,len(confs))*100:.1f}% | {top_st} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 二、重点争议样本前后对比（你点名的 5 张 + 典型跨界样本）",
        "",
        "| Asset ID | 原标题 | 旧分类（被硬塞） | **Gemini 视觉直读域** | **自然风格词 (`free_style_primary`)** | 主义? | 内容品类 | 像素观察特征 |",
        "| :--- | :--- | :--- | :--- | :--- | :---: | :--- | :--- |",
    ]
    spot_ids = [
        "pin_grap_001",
        "pin_grap_002",
        "pin_grap_003",
        "pin_grap_004",
        "pin_grap_023",
        "pin_grap_006",
        "pin_grap_011",
        "pin_grap_016",
        "pin_grap_026",
        "pin_arch_053",
        "pin_indu_001",
        "pin_craf_001",
    ]
    for aid in spot_ids:
        a = by_id.get(aid)
        rec = cache.get(aid)
        if not a or not rec:
            continue
        old_lbl = f"{a.get('archetype_label', '')} · {a.get('aesthetic_style_zh', '')}"
        traits = ", ".join(rec.get("visual_traits", [])[:3])
        lines.append(
            f"| `{aid}` | {a.get('title', '')} | {old_lbl} | `{DOMAIN_ZH.get(rec['visual_domain'], rec['visual_domain'])}` | "
            f"**{rec['free_style_primary']}**{(' / ' + rec['free_style_secondary']) if rec.get('free_style_secondary') else ''} | "
            f"{'是' if rec['is_canonical_ism'] else '否'} | {rec['content_typology_zh']} | {traits} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 三、各视觉域内部自然风格聚类明细（供收敛受控词表决策）",
        "",
    ]
    for dom, cnt in dom_counts.most_common():
        lines.append(f"### {DOMAIN_ZH.get(dom, dom)} (`{dom}`, {cnt} 张)")
        st_str = "、".join(f"**{s}** (`{c}`)" for s, c in style_by_dom[dom].most_common(12))
        med_str = "、".join(f"{m} (`{c}`)" for m, c in medium_by_dom[dom].most_common(8))
        typ_str = "、".join(f"{t} (`{c}`)" for t, c in typo_by_dom[dom].most_common(10))
        lines.append(f"- **自然风格词 Top 12**：{st_str}")
        lines.append(f"- **视觉媒介 Top 8**：{med_str}")
        lines.append(f"- **内容品类 Top 10**：{typ_str}")
        lines.append("")

    REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight Option B: Gemini Open Visual Discovery on 500 assets.")
    parser.add_argument("--model", default="gemini-4-hydrogen", help="Gemini model ID (default: gemini-4-hydrogen)")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent worker threads")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick tests (0 = all 500)")
    args = parser.parse_args()

    bundle = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]
    if args.limit > 0:
        assets = assets[: args.limit]

    cache: dict[str, dict[str, Any]] = {}
    if CACHE_PATH.is_file():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [a for a in assets if a["asset_id"] not in cache]
    print(f"Gemini Open Discovery [{args.model}]: total={len(assets)}, cached={len(cache)}, todo={len(todo)}")

    t0 = time.time()
    in_tok = 0
    out_tok = 0
    thk_tok = 0
    done = 0
    failed = 0

    if todo:
        client = _make_client()
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {
                pool.submit(
                    _discover_one,
                    client,
                    args.model,
                    a,
                    WEB_PUBLIC_DIR / a["image_url"].lstrip("/"),
                ): a["asset_id"]
                for a in todo
            }
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    asset_id, payload, usage = fut.result()
                except Exception as exc:  # noqa: BLE001
                    with lock:
                        failed += 1
                    print(f"[WARN] {aid}: {exc}")
                    continue
                with lock:
                    cache[asset_id] = payload
                    in_tok += usage["input_tokens"]
                    out_tok += usage["output_tokens"]
                    thk_tok += usage["thought_tokens"]
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        print(f"Progress: {done}/{len(todo)} discovered ({time.time()-t0:.1f}s, failed={failed})")

        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    elapsed = time.time() - t0
    _write_report(
        args.model,
        assets,
        cache,
        {
            "elapsed_s": elapsed,
            "run_count": done,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "thought_tokens": thk_tok,
        },
    )
    print(
        f"DONE! Report written to {REPORT_MD_PATH} | "
        f"Discovered={len(cache)}/{len(assets)}, failed={failed}, elapsed={elapsed:.1f}s, "
        f"tokens(in={in_tok:,}, out={out_tok:,}, thought={thk_tok:,})"
    )


if __name__ == "__main__":
    main()
