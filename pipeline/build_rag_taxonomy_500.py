"""Bounded Model-Native Aesthetic Style & 4-Key RAG Facet Indexing Pipeline (500 Assets).

Separates two orthogonal concerns strictly:
  1. `archetype` (7 bounded disciplines): architecture, interior, landscape, industrial, craft, graphic, editorial
  2. `aesthetic_style` (12 bounded, model-native canonical design movements/styles):
     Minimalism, Modernism, High-Tech, Wabi-Sabi, Brutalism, Bauhaus, Functionalism,
     Scandinavian, Swiss Style, Japanese Zen, Organic Modernism, Deconstructivism.
     Every label is a textbook art/design/architecture movement that VLMs and diffusion
     models natively understand (never self-invented descriptive phrases).
  3. `rag_facets` (strictly 4 bounded facet keys, controlled enum vocabularies):
     - `typology`  (1 item, 16 canonical content/object types, e.g. 灯具照明, 空间导视)
     - `materials` (1-2 items, 12 canonical material tokens)
     - `lighting`  (1 item, 6 canonical lighting tokens)
     - `details`   (1-2 items, 12 canonical composition/craft detail tokens)

Outputs:
  - Enriches `web/public/data/aethervault_showcase_v1.json` (version `4.0.0-rag-aesthetic-atlas-500`)
  - Enriches `data/pinterest_500/aethervault_assets_500.json`
  - Exports machine-ready RAG corpus `web/public/data/aethervault_rag_500.jsonl`
  - Caches per-asset classification to `data/pinterest_500/_rag_taxonomy_500_cache.json`
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from .anchor_scorer import (
    PRICE_CACHED_INPUT_USD_M,
    PRICE_OUTPUT_USD_M,
    PRICE_UNCACHED_INPUT_USD_M,
    USD_TO_CNY,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_SHOWCASE_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
RAG_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_rag_taxonomy_500_cache.json"

DEFAULT_MODEL = "gpt-4o-mini"

StyleIdLiteral = Literal[
    "minimalism",
    "modernism",
    "high_tech",
    "wabi_sabi",
    "brutalism",
    "bauhaus",
    "functionalism",
    "scandinavian",
    "swiss_style",
    "japanese_zen",
    "organic_modernism",
    "deconstructivism",
]

TypologyLiteral = Literal[
    "建筑立面",
    "居住空间",
    "办公公区",
    "茶咖餐饮",
    "展陈空间",
    "公园庭院",
    "家具座椅",
    "精密仪器",
    "灯具照明",
    "陶瓷器皿",
    "时装穿搭",
    "空间导视",
    "海报排版",
    "色彩界面",
    "品牌图形",
    "概念摄影",
]

MaterialLiteral = Literal[
    "清水混凝土",
    "原木",
    "金属铝钢",
    "天然石材",
    "玻璃幕墙",
    "粗陶釉面",
    "夯土灰泥",
    "天然织物",
    "皮革",
    "纸质印刷",
    "绿植水体",
    "纯色数字",
]

LightingLiteral = Literal[
    "自然天光",
    "漫射柔光",
    "戏剧硬影",
    "暖调氛围",
    "棚拍匀光",
    "逆光剪影",
]

DetailLiteral = Literal[
    "明缝节点",
    "模数网格",
    "大面积留白",
    "悬挑挑檐",
    "框景借景",
    "对称秩序",
    "精密旋钮",
    "折纸曲面",
    "岁月包浆",
    "撞色点缀",
    "无衬线字体",
    "雕塑廓形",
]

STYLE_DEFINITIONS: dict[StyleIdLiteral, dict[str, str]] = {
    "minimalism": {
        "zh": "极简主义",
        "en": "Minimalism",
        "desc": "克制几何、大面积留白、纯粹表面与极少装饰元素",
    },
    "modernism": {
        "zh": "现代主义",
        "en": "Modernism",
        "desc": "体块穿插、理性空间秩序、现代梁柱/玻璃与通用当代设计语言",
    },
    "high_tech": {
        "zh": "高技派",
        "en": "High-Tech",
        "desc": "外露钢构/铝板幕墙、模数化装配、工业精密构造与工程表现力",
    },
    "wabi_sabi": {
        "zh": "侘寂风",
        "en": "Wabi-Sabi",
        "desc": "粗陶、夯土、风化原木、不完美手工肌理与岁月包浆",
    },
    "brutalism": {
        "zh": "粗野主义",
        "en": "Brutalism",
        "desc": "厚重清水混凝土体量、雕塑感巨构、深邃阴影与粗粝原始质感",
    },
    "bauhaus": {
        "zh": "包豪斯",
        "en": "Bauhaus",
        "desc": "基本几何构成、弯管钢架家具、红黄蓝原色或清晰结构理性",
    },
    "functionalism": {
        "zh": "功能主义",
        "en": "Functionalism",
        "desc": "Dieter Rams / Braun 式精密工业产品，形式追随功能与克制操控界面",
    },
    "scandinavian": {
        "zh": "北欧极简",
        "en": "Scandinavian",
        "desc": "浅色白橡/桦木、柔和漫射光、人本舒适尺度与温暖中性色调",
    },
    "swiss_style": {
        "zh": "瑞士国际主义",
        "en": "Swiss Style",
        "desc": "严格数学网格、无衬线字体排版、高对比平面秩序与理性导视系统",
    },
    "japanese_zen": {
        "zh": "东方禅意",
        "en": "Japanese Zen",
        "desc": "挑檐灰空间、枯山水庭院、框景借景、东方茶器与静谧木构秩序",
    },
    "organic_modernism": {
        "zh": "有机现代",
        "en": "Organic Modernism",
        "desc": "流畅曲线、仿生曲面、生态地形融合与柔和过渡的现代自然形态",
    },
    "deconstructivism": {
        "zh": "解构主义",
        "en": "Deconstructivism",
        "desc": "非对称解构剪裁、褶皱雕塑廓形、斜向切割与先锋实验张力",
    },
}

TYPOLOGY_EN: dict[str, str] = {
    "建筑立面": "Architectural Facade",
    "居住空间": "Residential Interior",
    "办公公区": "Workspace & Lobby",
    "茶咖餐饮": "Cafe & Hospitality",
    "展陈空间": "Gallery & Exhibition",
    "公园庭院": "Park & Courtyard",
    "家具座椅": "Furniture & Seating",
    "精密仪器": "Precision Instrument",
    "灯具照明": "Lighting Fixture",
    "陶瓷器皿": "Ceramic Vessel",
    "时装穿搭": "Fashion Silhouette",
    "空间导视": "Wayfinding Signage",
    "海报排版": "Editorial Typography",
    "色彩界面": "Color System & UI",
    "品牌图形": "Geometric Graphic",
    "概念摄影": "Conceptual Photography",
}

MATERIAL_EN: dict[str, str] = {
    "清水混凝土": "Board-Formed Concrete",
    "原木": "Natural Timber",
    "金属铝钢": "Anodized Aluminum & Steel",
    "天然石材": "Natural Stone",
    "玻璃幕墙": "Architectural Glass",
    "粗陶釉面": "Stoneware Ceramic",
    "夯土灰泥": "Rammed Earth & Plaster",
    "天然织物": "Woven Textile",
    "皮革": "Leather",
    "纸质印刷": "Print Paper",
    "绿植水体": "Foliage & Water",
    "纯色数字": "Digital Flat Surface",
}

LIGHTING_EN: dict[str, str] = {
    "自然天光": "Natural Daylight",
    "漫射柔光": "Soft Diffused Light",
    "戏剧硬影": "Chiaroscuro Hard Shadow",
    "暖调氛围": "Warm Ambient Glow",
    "棚拍匀光": "Even Studio Lighting",
    "逆光剪影": "Backlit Silhouette",
}

DETAIL_EN: dict[str, str] = {
    "明缝节点": "Shadow-Gap Joint",
    "模数网格": "Modular Grid",
    "大面积留白": "Generous Negative Space",
    "悬挑挑檐": "Cantilevered Eave",
    "框景借景": "Framed Vista",
    "对称秩序": "Axial Symmetry",
    "精密旋钮": "Tactile Control Dial",
    "折纸曲面": "Pleated Curvature",
    "岁月包浆": "Weathered Patina",
    "撞色点缀": "Chromatic Accent",
    "无衬线字体": "Grotesque Sans-Serif",
    "雕塑廓形": "Sculptural Silhouette",
}

ARCHETYPE_EN: dict[str, str] = {
    "architecture": "Architecture",
    "interior": "Interior Design",
    "landscape": "Landscape Architecture",
    "industrial": "Industrial Design",
    "craft": "Craft & Materiality",
    "graphic": "Graphic Design",
    "editorial": "Fashion & Editorial",
}

STYLE_ORDER: tuple[StyleIdLiteral, ...] = tuple(STYLE_DEFINITIONS.keys())  # type: ignore[assignment]


class RagAssetClassification(BaseModel):
    """Strict controlled-vocabulary schema for Model-Native Style + 4-Key RAG Facets."""

    model_config = ConfigDict(extra="forbid")

    aesthetic_style: StyleIdLiteral = Field(
        ...,
        description="Single best-matching canonical model-native aesthetic movement/style.",
    )
    typology: TypologyLiteral = Field(
        ...,
        description="Single primary subject/content typology describing WHAT is shown.",
    )
    materials: list[MaterialLiteral] = Field(
        ...,
        min_length=1,
        max_length=2,
        description="1 to 2 dominant visible material tags from the controlled enum.",
    )
    lighting: LightingLiteral = Field(
        ...,
        description="Single primary lighting mood tag from the controlled enum.",
    )
    details: list[DetailLiteral] = Field(
        ...,
        min_length=1,
        max_length=2,
        description="1 to 2 signature composition/craft detail tags from the controlled enum.",
    )


def _build_system_prompt() -> str:
    style_lines = "\n".join(
        f"- `{sid}` ({meta['zh']} / {meta['en']}): {meta['desc']}"
        for sid, meta in STYLE_DEFINITIONS.items()
    )
    return f"""你是顶级建筑/工业/视觉设计知识库架构师，负责将 500 张设计参考图归入严格受控的「模型原生美学主义 + 4 键 RAG 结构化标签」索引中。

核心原则（极其重要）：
1. **美学风格 (`aesthetic_style`) 必须是模型原生可理解的设计流派/主义**（严禁把物品品类当风格，例如灯具、导视、住宅属于 `typology`，不属于 `aesthetic_style`）。
2. **所有字段严格受控于 JSON Schema 枚举值**，确保整个 500 图 RAG 索引边界清晰、可稳定检索。

=== 12 个模型原生美学主义/风格 (`aesthetic_style`) ===
{style_lines}

分流指引（避免全部堆到 minimalism / modernism）：
- 若以裸露金属结构、玻璃幕墙、模数立面或工程装配为特征 -> `high_tech`
- 若以厚重清水混凝土、雕塑感巨构、强烈明暗切分为特征 -> `brutalism`
- 若以粗陶、夯土、风化原木、微水泥或手作质感为特征 -> `wabi_sabi`
- 若以东方挑檐、禅意庭院、茶器、框景留白为特征 -> `japanese_zen`
- 若以 Dieter Rams / Braun 精密旋钮仪器、功能导向硬件为特征 -> `functionalism`
- 若以弯管钢架椅、基本几何构成、原色几何结构为特征 -> `bauhaus`
- 若以浅色橡木/桦木、柔和采光、舒适人本家居/曲木家具为特征 -> `scandinavian`
- 若以严格网格排版、无衬线字体海报、极简空间导视标牌、规范 UI/色板为特征 -> `swiss_style`
- 若以有机曲线、生态景观步道、仿生自然融合形态为特征 -> `organic_modernism`
- 若以先锋解构时装、褶皱雕塑廓形、非对称张力构成或实验摄影为特征 -> `deconstructivism`
- 若以极度克制留白、纯净单色块面与去装饰性为核心 -> `minimalism`
- 若为典型现代理性建筑/室内空间但无上述更特定流派特征 -> `modernism`

=== 4 个受控 RAG Facet 键 ===
- `typology`（1 项）：画面实际展示的物体/空间/媒介品类（如灯具照明、空间导视、陶瓷器皿、建筑立面、家具座椅等）。
- `materials`（1-2 项，不重复）：画面最主要的真实材质（平面/UI/色卡若无实体材质选 `纯色数字` 或 `纸质印刷`）。
- `lighting`（1 项）：最核心的光影条件。
- `details`（1-2 项，不重复）：最具辨识度的构图或工艺细部特征。
"""


def _classify_one(
    oai: OpenAI,
    system_prompt: str,
    asset: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, int]]:
    crit = asset.get("aesthetic_critique") or {}
    gran = asset.get("granular_descriptors") or {}
    spec = asset.get("style_spectrums") or {}
    spec_str = ", ".join(
        f"{k}={spec[k]['score']:+.2f}"
        for k in (
            "tectonic_honesty",
            "surface_entropy",
            "spatial_density",
            "geometric_order",
            "lighting_drama",
            "chromatic_tension",
            "thermal_mood",
            "reality_abstraction",
        )
        if k in spec
    )
    user_text = (
        f"Asset ID: {asset['asset_id']}\n"
        f"Archetype: {asset.get('archetype', '')} ({asset.get('archetype_label', '')})\n"
        f"Title: {asset.get('title', '')} | Board: {asset.get('board_name', '')}\n"
        f"Prior Sub-Label: {asset.get('sub_style', '')}\n"
        f"Headline: {crit.get('headline_insight', '')}\n"
        f"Proportion: {crit.get('proportion_and_order', '')}\n"
        f"Material & Detail: {crit.get('material_and_detail', '')}\n"
        f"Light & Palette: {crit.get('light_and_palette', '')}\n"
        f"Granular: material_stack={gran.get('material_stack', '')} | lighting_rig={gran.get('lighting_rig', '')} | optics={gran.get('optics_camera', '')}\n"
        f"8-Axis: {spec_str}\n"
        "Output the strict controlled-vocabulary `aesthetic_style` + 4-key `rag_facets` JSON."
    )

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            completion = oai.beta.chat.completions.parse(
                model=DEFAULT_MODEL,
                temperature=0.1,
                max_tokens=260,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format=RagAssetClassification,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Empty parsed response")
            data = parsed.model_dump()
            # Deduplicate list facets while preserving order
            data["materials"] = list(dict.fromkeys(data["materials"]))[:2]
            data["details"] = list(dict.fromkeys(data["details"]))[:2]
            usage = completion.usage
            pt = int(getattr(usage, "prompt_tokens", 0) or 0)
            ct = int(getattr(usage, "completion_tokens", 0) or 0)
            details = getattr(usage, "prompt_tokens_details", None)
            cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
            return (
                asset["asset_id"],
                data,
                {"prompt_tokens": pt, "cached_tokens": cached, "completion_tokens": ct},
            )
        except RateLimitError as exc:
            last_err = exc
            time.sleep(min(15.0, 2.0 * (attempt + 1)))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.0 * (attempt + 1))

    raise RuntimeError(f"RAG classification failed for {asset['asset_id']}: {last_err}")


def _calibrate_lighting(asset: dict[str, Any], raw_lighting: str, typology: str) -> str:
    """Calibrate lighting facet using real 8-axis visual readings when LLM defaulted to 自然天光."""
    if raw_lighting != "自然天光":
        return raw_lighting
    spec = asset.get("style_spectrums") or {}
    drama = float((spec.get("lighting_drama") or {}).get("score", 0.0))
    warmth = float((spec.get("thermal_mood") or {}).get("score", 0.0))
    abstr = float((spec.get("reality_abstraction") or {}).get("score", 0.0))
    arch = asset.get("archetype", "")
    rig = ((asset.get("granular_descriptors") or {}).get("lighting_rig") or "").lower()
    crit_lgt = ((asset.get("aesthetic_critique") or {}).get("light_and_palette") or "")

    if "逆光" in crit_lgt or "剪影" in crit_lgt or "backlight" in rig:
        return "逆光剪影"
    if drama >= 0.45 or "高反差" in crit_lgt or "强烈阴影" in crit_lgt or "chiaroscuro" in rig:
        return "戏剧硬影"
    if typology in ("色彩界面", "海报排版", "品牌图形") or (arch == "graphic" and abstr >= 0.4):
        return "棚拍匀光"
    if arch in ("industrial", "craft", "editorial") and ("棚拍" in crit_lgt or "studio" in rig or drama <= 0.0):
        return "棚拍匀光"
    if warmth >= 0.45 and ("暖" in crit_lgt or "灯光" in crit_lgt or "温馨" in crit_lgt):
        return "暖调氛围"
    if drama <= -0.25 or "漫射" in crit_lgt or "柔光" in crit_lgt or "柔和" in crit_lgt:
        return "漫射柔光"
    return "自然天光"


def main() -> None:
    if not WEB_SHOWCASE_JSON.is_file():
        raise FileNotFoundError(f"Showcase JSON missing: {WEB_SHOWCASE_JSON}")
    bundle = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]

    cache: dict[str, Any] = {}
    if RAG_CACHE_PATH.is_file():
        try:
            cache = json.loads(RAG_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [a for a in assets if a["asset_id"] not in cache]
    print(f"RAG Taxonomy Classification: total={len(assets)}, cached={len(cache)}, todo={len(todo)}")

    tot_pt = 0
    tot_cached = 0
    tot_ct = 0
    t0 = time.time()

    if todo:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY env var is required to run RAG taxonomy classification.")
        oai = OpenAI()
        sys_prompt = _build_system_prompt()
        lock = threading.Lock()
        done = 0
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {pool.submit(_classify_one, oai, sys_prompt, a): a["asset_id"] for a in todo}
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    asset_id, payload, usage = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Failed {aid}: {exc}")
                    continue
                with lock:
                    cache[asset_id] = payload
                    tot_pt += usage["prompt_tokens"]
                    tot_cached += usage["cached_tokens"]
                    tot_ct += usage["completion_tokens"]
                    done += 1
                    if done % 50 == 0 or done == len(todo):
                        RAG_CACHE_PATH.write_text(
                            json.dumps(cache, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        print(f"Progress: {done}/{len(todo)} classified ({time.time() - t0:.1f}s)")

        RAG_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Apply strict bounded Style + 4-Key RAG Facets to every asset & export JSONL
    style_counts: Counter[str] = Counter()
    facet_counts: dict[str, Counter[str]] = {
        "typology": Counter(),
        "materials": Counter(),
        "lighting": Counter(),
        "details": Counter(),
    }
    arch_style_counts: dict[str, Counter[str]] = {}
    rag_jsonl_lines: list[str] = []
    missing = 0

    for a in assets:
        aid = a["asset_id"]
        c = cache.get(aid)
        if not c:
            missing += 1
            continue

        sid: StyleIdLiteral = c["aesthetic_style"]
        smeta = STYLE_DEFINITIONS[sid]
        typ: str = c["typology"]
        mats: list[str] = list(dict.fromkeys(c["materials"]))[:2]
        lgt: str = _calibrate_lighting(a, c["lighting"], typ)
        dets: list[str] = list(dict.fromkeys(c["details"]))[:2]

        arch = a.get("archetype", "architecture")
        arch_zh = a.get("archetype_label", "建筑设计")
        arch_en = ARCHETYPE_EN.get(arch, "Design")

        model_prompt_tokens = list(
            dict.fromkeys(
                [
                    smeta["en"],
                    arch_en,
                    TYPOLOGY_EN.get(typ, typ),
                    *[MATERIAL_EN.get(m, m) for m in mats],
                    LIGHTING_EN.get(lgt, lgt),
                    *[DETAIL_EN.get(d, d) for d in dets],
                ]
            )
        )

        retrieval_text = (
            f"[{arch_zh} | {smeta['zh']} ({smeta['en']})] "
            f"typology:{typ} · materials:{','.join(mats)} · "
            f"lighting:{lgt} · details:{','.join(dets)} | "
            f"{a.get('title', '')} — {(a.get('aesthetic_critique') or {}).get('headline_insight', '')}"
        )

        a["aesthetic_style"] = sid
        a["aesthetic_style_zh"] = smeta["zh"]
        a["aesthetic_style_en"] = smeta["en"]
        # Align legacy sub_style / sub_category fields to the canonical model-native style
        a["sub_style"] = smeta["zh"]
        a["sub_category"] = smeta["zh"]
        a["rag_facets"] = {
            "typology": typ,
            "materials": mats,
            "lighting": lgt,
            "details": dets,
        }
        a["rag_doc"] = {
            "doc_id": aid,
            "archetype": arch,
            "archetype_en": arch_en,
            "style_id": sid,
            "style_zh": smeta["zh"],
            "style_en": smeta["en"],
            "facets": a["rag_facets"],
            "model_prompt_tokens": model_prompt_tokens,
            "palette": (a.get("granular_descriptors") or {}).get("color_palette", [])[:5],
            "aspect_ratio": a.get("aspect_label", "4:3"),
            "retrieval_text": retrieval_text,
        }

        style_counts[sid] += 1
        arch_style_counts.setdefault(arch, Counter())[sid] += 1
        facet_counts["typology"][typ] += 1
        for m in mats:
            facet_counts["materials"][m] += 1
        facet_counts["lighting"][lgt] += 1
        for d in dets:
            facet_counts["details"][d] += 1

        crit = a.get("aesthetic_critique") or {}
        rag_record = {
            **a["rag_doc"],
            "title": a.get("title", ""),
            "source_origin": a.get("source_origin", ""),
            "image_url": a.get("image_url", ""),
            "headline_insight": crit.get("headline_insight", ""),
            "why_you_love_it": crit.get("why_you_love_it", ""),
            "proportion_and_order": crit.get("proportion_and_order", ""),
            "material_and_detail": crit.get("material_and_detail", ""),
            "light_and_palette": crit.get("light_and_palette", ""),
            "design_takeaways": crit.get("design_takeaways", []),
        }
        rag_jsonl_lines.append(json.dumps(rag_record, ensure_ascii=False))

    if missing > 0:
        raise RuntimeError(f"{missing} assets missing RAG classification! Re-run to finish.")

    # Rebuild archetype_taxonomy using canonical model-native styles
    for node in bundle.get("archetype_taxonomy", []):
        arch = node["archetype"]
        sc = arch_style_counts.get(arch, Counter())
        node["sub_styles"] = [
            {
                "sub_style": STYLE_DEFINITIONS[sid]["zh"],
                "style_id": sid,
                "style_en": STYLE_DEFINITIONS[sid]["en"],
                "count": cnt,
            }
            for sid, cnt in sc.most_common()
        ]

    bundle["version"] = "4.0.0-rag-aesthetic-atlas-500"
    bundle["rag_schema"] = {
        "schema_version": "1.0.0",
        "max_styles": len(STYLE_DEFINITIONS),
        "facet_keys": [
            {"key": "typology", "label_zh": "内容品类", "cardinality": "single", "max_vocab": len(TYPOLOGY_EN)},
            {"key": "materials", "label_zh": "核心材质", "cardinality": "1-2", "max_vocab": len(MATERIAL_EN)},
            {"key": "lighting", "label_zh": "光影氛围", "cardinality": "single", "max_vocab": len(LIGHTING_EN)},
            {"key": "details", "label_zh": "构图细部", "cardinality": "1-2", "max_vocab": len(DETAIL_EN)},
        ],
        "styles": [
            {
                "style_id": sid,
                "zh": STYLE_DEFINITIONS[sid]["zh"],
                "en": STYLE_DEFINITIONS[sid]["en"],
                "desc": STYLE_DEFINITIONS[sid]["desc"],
                "count": style_counts.get(sid, 0),
            }
            for sid in STYLE_ORDER
            if style_counts.get(sid, 0) > 0
        ],
        "facet_counts": {
            k: [{"value": val, "count": cnt} for val, cnt in counter.most_common()]
            for k, counter in facet_counts.items()
        },
        "jsonl_url": "/data/aethervault_rag_500.jsonl",
    }

    uncached_pt = max(0, tot_pt - tot_cached)
    cost_usd = (
        (uncached_pt / 1_000_000) * PRICE_UNCACHED_INPUT_USD_M
        + (tot_cached / 1_000_000) * PRICE_CACHED_INPUT_USD_M
        + (tot_ct / 1_000_000) * PRICE_OUTPUT_USD_M
    )
    cost_cny = cost_usd * USD_TO_CNY
    cache_rate = (tot_cached / tot_pt * 100.0) if tot_pt > 0 else 0.0

    WEB_SHOWCASE_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    ASSETS_500_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")

    print("\n=== 12 Canonical Model-Native Aesthetic Styles (500 Assets) ===")
    for sid, cnt in style_counts.most_common():
        print(f"  {STYLE_DEFINITIONS[sid]['zh']} ({STYLE_DEFINITIONS[sid]['en']}): {cnt}")
    print("\n=== 4 Bounded RAG Facet Keys ===")
    for fk, counter in facet_counts.items():
        top_str = ", ".join(f"{v}({c})" for v, c in counter.most_common(8))
        print(f"  {fk} [{len(counter)} unique]: {top_str}")
    print(
        f"\nExported RAG JSONL: {WEB_RAG_JSONL} ({len(rag_jsonl_lines)} docs) | "
        f"Cost: CNY {cost_cny:.4f} (cache={cache_rate:.1f}%) | Elapsed={time.time() - t0:.1f}s"
    )


if __name__ == "__main__":
    main()
