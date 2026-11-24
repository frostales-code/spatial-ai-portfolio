"""Converge Gemini 4 Hydrogen Open Discovery into Domain-Scoped Model-Native RAG Schema (v5.0).

Uses the 500 unbiased pixel classifications from `data/pinterest_500/_gemini_open_discovery_500.json`
to produce:
  1. 8 visual-first domains (`archetype`):
     interior, architecture, graphic_typography, craft, industrial, landscape,
     illustration_character, fashion_photography.
  2. Domain-scoped canonical model-native styles (`aesthetic_style`, strictly bounded 20 buckets,
     3-6 per domain, explicitly tagged `is_movement: bool` so non-ism visual systems like
     Color Palette System, Minimalist Wayfinding, Anime Techwear are NEVER force-labeled as
     classical art movements) WHILE preserving Gemini's exact raw native style & pixel traits.
  3. 4 strictly bounded cross-media RAG facet keys (`rag_facets`):
     - `medium`    (visual medium, e.g. 建筑摄影, 数字插画, 字体海报, 配色色板)
     - `typology`  (content subject, e.g. 建筑立面, 汉字实验字体, 二次元立绘, 空间导视)
     - `materials` (physical material OR visual technique, e.g. 清水混凝土, 赛璐璐平涂, 点阵像素)
     - `lighting`  (lighting & color mood, e.g. 棚拍匀光, 戏剧硬影, 高饱和撞色, 暖调氛围)
  4. Targeted Critique Debiasing via `gemini-4-hydrogen` (raw `.webp` pixels) for all non-spatial
     visual domains (`illustration_character`, `graphic_typography`, `fashion_photography`) so
     every critique honestly describes real pixel craft and distinguishes `core_match` (核心同频)
     vs `contrast_inspiration` (破圈反差灵感).

Updates:
  - `web/public/data/aethervault_showcase_v1.json` (version `5.0.0-gemini-rag-atlas-500`)
  - `data/pinterest_500/aethervault_assets_500.json`
  - `web/public/data/aethervault_rag_500.jsonl`
"""

from __future__ import annotations

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
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
DISCOVERY_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_open_discovery_500.json"
DEBIASED_CRITIQUE_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_debiased_critiques.json"

GEMINI_MODEL = "gemini-4-hydrogen"

ARCHETYPE_ORDER: tuple[str, ...] = (
    "interior",
    "architecture",
    "graphic_typography",
    "craft",
    "industrial",
    "landscape",
    "illustration_character",
    "fashion_photography",
)

ARCHETYPE_META: dict[str, dict[str, str]] = {
    "interior": {"zh": "室内设计", "en": "Interior Design"},
    "architecture": {"zh": "建筑设计", "en": "Architecture"},
    "graphic_typography": {"zh": "平面与字体", "en": "Graphic & Typography"},
    "craft": {"zh": "器物工艺", "en": "Craft & Materiality"},
    "industrial": {"zh": "工业设计", "en": "Industrial Design"},
    "landscape": {"zh": "景观空间", "en": "Landscape & Urban"},
    "illustration_character": {"zh": "插画与角色", "en": "Illustration & Character"},
    "fashion_photography": {"zh": "时尚摄影", "en": "Fashion & Photography"},
}

# Strictly bounded 20 canonical model-native style buckets (domain-scoped!)
STYLE_CATALOG: dict[str, dict[str, Any]] = {
    # Spatial & Architectural
    "minimalism": {"zh": "极简主义", "en": "Minimalism", "is_movement": True},
    "modernism": {"zh": "现代主义", "en": "Modernism", "is_movement": True},
    "organic_modernism": {"zh": "有机现代", "en": "Organic Modernism", "is_movement": True},
    "industrial_minimalism": {"zh": "工业极简", "en": "Industrial Minimalism", "is_movement": True},
    "wabi_sabi": {"zh": "侘寂风", "en": "Wabi-Sabi", "is_movement": True},
    "high_tech_parametric": {"zh": "高技与参数化", "en": "High-Tech & Parametric", "is_movement": True},
    "biophilic": {"zh": "亲生物生态", "en": "Biophilic", "is_movement": True},
    "mid_century_modern": {"zh": "中古现代", "en": "Mid-Century Modern", "is_movement": True},
    "japanese_zen": {"zh": "东方禅意", "en": "Japanese Zen", "is_movement": True},
    # Industrial & Craft
    "braun_functionalism": {"zh": "功能主义", "en": "Braun Functionalism", "is_movement": True},
    "bauhaus": {"zh": "包豪斯", "en": "Bauhaus", "is_movement": True},
    "east_asian_craft": {"zh": "东方器物", "en": "East Asian Craft", "is_movement": False},
    "geometric_craft": {"zh": "几何手作", "en": "Geometric Craft", "is_movement": False},
    # Graphic & Typography
    "color_palette": {"zh": "色彩系统", "en": "Color Palette System", "is_movement": False},
    "minimalist_wayfinding": {"zh": "极简导视", "en": "Minimalist Wayfinding", "is_movement": False},
    "experimental_typography": {"zh": "实验字体", "en": "Experimental Typography", "is_movement": False},
    "swiss_style": {"zh": "瑞士国际主义", "en": "Swiss Style", "is_movement": True},
    "editorial_ui": {"zh": "数字与编辑排版", "en": "Editorial & Web UI", "is_movement": False},
    "art_deco_retro": {"zh": "装饰与复古", "en": "Art Deco & Retro", "is_movement": True},
    # Illustration, Character & Fashion
    "anime_techwear": {"zh": "机能二次元", "en": "Anime Techwear", "is_movement": False},
    "pop_anime": {"zh": "日系与波普插画", "en": "Stylized & Pop Anime", "is_movement": False},
    "watercolor_ink": {"zh": "水彩与水墨", "en": "Watercolor & Ink", "is_movement": False},
    "line_art_sketch": {"zh": "线条与草图", "en": "Abstract Line Art", "is_movement": False},
    "avant_garde_fashion": {"zh": "先锋时装", "en": "Avant-Garde Fashion", "is_movement": True},
    "editorial_photography": {"zh": "纪实与光影摄影", "en": "Editorial Photography", "is_movement": False},
}


def _map_style_bucket(domain: str, rec: dict[str, Any]) -> str:
    p = (rec.get("free_style_primary") or "").lower()
    s = (rec.get("free_style_secondary") or "").lower()
    m = (rec.get("medium") or "").lower()
    t = (rec.get("content_typology_zh") or "").lower()
    combo = f"{p} {s} {m} {t}"

    if domain == "illustration_character":
        if any(k in combo for k in ("techwear", "cyber", "mecha", "tactical", "post-apocalyptic", "机能")):
            return "anime_techwear"
        if any(k in combo for k in ("anime", "manga", "pop art", "cel-shaded", "character", "二次元", "人像", "立绘")):
            return "pop_anime"
        if any(k in combo for k in ("watercolor", "ink", "painterly", "impression", "水彩", "水墨", "淡彩", "国画")):
            return "watercolor_ink"
        return "line_art_sketch"

    if domain == "fashion_photography":
        if any(k in combo for k in ("avant-garde", "sculptural", "tailoring", "fashion", "garment", "workwear", "时装", "服饰", "穿搭", "针织", "剪裁")):
            return "avant_garde_fashion"
        return "editorial_photography"

    if domain == "graphic_typography":
        if any(k in combo for k in ("palette", "swatch", "色卡", "配色")):
            return "color_palette"
        if any(k in combo for k in ("wayfinding", "signage", "sign", "导视", "标识", "标牌", "洗手间")):
            return "minimalist_wayfinding"
        if any(k in combo for k in ("swiss", "international typographic", "瑞士")):
            return "swiss_style"
        if any(k in combo for k in ("art deco", "retro", "vintage", "复古")):
            return "art_deco_retro"
        if any(k in combo for k in ("typography", "type", "letter", "font", "modular", "isometric", "字体", "字形", "汉字", "节气")):
            return "experimental_typography"
        return "editorial_ui"

    if domain == "industrial":
        if any(k in combo for k in ("braun", "functional", "dieter", "仪器", "音响", "收音机", "唱片")):
            return "braun_functionalism"
        if any(k in combo for k in ("bauhaus", "cantilever", "tubular", "包豪斯", "悬臂")):
            return "bauhaus"
        if any(k in combo for k in ("mid-century", "scandinavian", "nordic", "bentwood", "plywood", "曲木", "中古")):
            return "mid_century_modern"
        return "industrial_minimalism"

    if domain == "craft":
        if any(k in combo for k in ("wabi-sabi", "stoneware", "earthenware", "rustic", "侘寂", "粗陶", "茶器")):
            return "wabi_sabi"
        if any(k in combo for k in ("paper", "origami", "tessellation", "geometric", "string", "纸艺", "折纸", "编织", "几何", "绕线")):
            return "geometric_craft"
        if any(k in combo for k in ("celadon", "porcelain", "ceramic", "pottery", "tea", "traditional", "青瓷", "陶瓷", "瓷器", "漆器")):
            return "east_asian_craft"
        return "organic_modernism"

    if domain == "landscape":
        if any(k in combo for k in ("biophilic", "ecological", "urban", "forest", "green", "生态", "屋顶绿化", "绿植", "森林")):
            return "biophilic"
        if any(k in combo for k in ("zen", "japanese", "film", "courtyard", "日系", "禅", "庭院", "枯山水")):
            return "japanese_zen"
        if any(k in combo for k in ("organic", "curved", "natural", "有机", "自然")):
            return "organic_modernism"
        if any(k in combo for k in ("minimal", "industrial", "极简", "工业")):
            return "minimalism"
        return "modernism"

    # architecture & interior
    if any(k in combo for k in ("wabi-sabi", "wabi", "rammed earth", "plaster", "侘寂", "夯土")):
        return "wabi_sabi"
    if any(k in combo for k in ("high-tech", "parametric", "deconstruct", "futur", "高技", "参数化", "金属幕墙", "穿孔")):
        return "high_tech_parametric"
    if any(k in combo for k in ("biophilic", "tropical", "courtyard", "绿植", "亲生物")):
        return "biophilic"
    if any(k in combo for k in ("mid-century", "scandinavian", "nordic", "bohemian", "retro", "中古", "北欧", "波西米亚")):
        return "mid_century_modern"
    if any(k in combo for k in ("japanese", "zen", "oriental", "茶室", "禅意", "东方")):
        return "japanese_zen"
    if any(k in combo for k in ("industrial", "brutal", "raw concrete", "loft", "工业", "粗野", "清水")):
        return "industrial_minimalism"
    if any(k in combo for k in ("organic", "curved", "fluid", "sculptural", "有机")):
        return "organic_modernism"
    if any(k in combo for k in ("minimal", "monochrome", "austere", "极简", "留白")):
        return "minimalism"
    return "modernism"


def _map_medium(domain: str, rec: dict[str, Any]) -> str:
    m = (rec.get("medium") or "").lower()
    if any(k in m for k in ("palette", "swatch")):
        return "配色色板"
    if any(k in m for k in ("wayfinding", "signage")):
        return "导视实拍"
    if any(k in m for k in ("web", "ui")):
        return "网页界面"
    if any(k in m for k in ("poster", "typography", "print", "book")):
        return "字体海报"
    if any(k in m for k in ("watercolor", "ink", "painting")):
        return "水彩手绘"
    if any(k in m for k in ("sketch", "line", "drawing", "diagram")):
        return "线条图纸"
    if any(k in m for k in ("anime", "character", "digital", "illustration")):
        return "数字插画"
    if any(k in m for k in ("ceramic", "paper", "craft", "sculpture", "textile", "installation")):
        return "器物装置"
    if any(k in m for k in ("fashion", "garment", "editorial")):
        return "时尚摄影"
    if any(k in m for k in ("product", "furniture")):
        return "产品摄影"
    if any(k in m for k in ("landscape", "nature", "aerial", "street", "film")):
        return "景观摄影"
    if any(k in m for k in ("interior", "exhibition")):
        return "室内摄影"
    if any(k in m for k in ("architect", "model", "render")):
        return "建筑摄影"
    fallback = {
        "interior": "室内摄影",
        "architecture": "建筑摄影",
        "graphic_typography": "字体海报",
        "craft": "器物装置",
        "industrial": "产品摄影",
        "landscape": "景观摄影",
        "illustration_character": "数字插画",
        "fashion_photography": "时尚摄影",
    }
    return fallback.get(domain, "建筑摄影")


def _map_typology(domain: str, rec: dict[str, Any]) -> str:
    t = (rec.get("content_typology_zh") or "").lower()
    m = (rec.get("medium") or "").lower()
    combo = f"{t} {m}"

    if domain == "illustration_character":
        if any(k in combo for k in ("二次元", "anime", "character", "立绘", "机能", "角色")):
            return "二次元立绘"
        if any(k in combo for k in ("时尚", "fashion", "人像", "portrait")):
            return "时尚插画"
        if any(k in combo for k in ("草图", "图纸", "建筑", "sketch", "diagram")):
            return "概念草图"
        return "艺术插画"

    if domain == "fashion_photography":
        if any(k in combo for k in ("时装", "服", "裙", "针织", "剪裁", "garment", "fashion")):
            return "先锋服饰"
        return "纪实摄影"

    if domain == "graphic_typography":
        if any(k in combo for k in ("色卡", "配色", "palette")):
            return "配色色卡"
        if any(k in combo for k in ("导视", "标识", "标牌", "wayfinding", "signage")):
            return "空间导视"
        if any(k in combo for k in ("字体", "字形", "汉字", "节气", "typography")):
            return "实验字体"
        if any(k in combo for k in ("网页", "ui", "web", "app")):
            return "数字界面"
        return "平面海报"

    if domain == "industrial":
        if any(k in combo for k in ("灯", "light", "lamp")):
            return "灯具照明"
        if any(k in combo for k in ("仪", "音响", "收音", "唱片", "秤", "钟", "器", "braun", "radio")):
            return "工业仪器"
        return "家具座椅"

    if domain == "craft":
        if any(k in combo for k in ("陶", "瓷", "碗", "壶", "花器", "茶", "ceramic")):
            return "陶瓷器皿"
        return "手作材质"

    if domain == "landscape":
        return "公园庭院"

    if domain == "interior":
        if any(k in combo for k in ("展", "画廊", "美术馆", "装置", "文化墙", "exhibition", "gallery")):
            return "展陈空间"
        if any(k in combo for k in ("咖啡", "茶", "餐", "烘焙", "店", "cafe", "bar")):
            return "茶咖餐饮"
        if any(k in combo for k in ("办公", "会议", "大堂", "前台", "教室", "走廊", "office", "lobby")):
            return "办公公区"
        return "居住空间"

    # architecture
    return "建筑立面"


def _map_materials(domain: str, rec: dict[str, Any], old_mats: list[str]) -> list[str]:
    combo = " ".join(
        [
            rec.get("free_style_primary", ""),
            rec.get("free_style_secondary", ""),
            rec.get("medium", ""),
            rec.get("content_typology_zh", ""),
            *rec.get("visual_traits", []),
        ]
    ).lower()

    if domain == "illustration_character":
        out: list[str] = []
        if any(k in combo for k in ("watercolor", "ink", "wash", "painterly", "水彩", "水墨", "淡彩")):
            out.append("水墨水彩")
        if any(k in combo for k in ("anime", "cel-shaded", "digital", "pop", "二次元", "立绘")):
            out.append("赛璐璐平涂")
        if any(k in combo for k in ("line", "sketch", "monochrome", "pen", "线稿", "钢笔", "草图")):
            out.append("锐利线稿")
        return list(dict.fromkeys(out))[:2] or ["数字绘画"]

    if domain == "graphic_typography":
        out = []
        if any(k in combo for k in ("cross-stitch", "pixel", "dot", "halftone", "lattice", "点阵", "像素")):
            out.append("点阵像素")
        if any(k in combo for k in ("metal", "aluminum", "steel", "concrete", "wood", "wayfinding", "导视", "标牌")):
            out.append("金属铝钢")
        if any(k in combo for k in ("poster", "print", "paper", "book", "海报", "印刷")):
            out.append("纸艺印刷")
        if any(k in combo for k in ("palette", "ui", "web", "vector", "digital", "色卡", "界面")):
            out.append("矢量扁平")
        return list(dict.fromkeys(out))[:2] or ["矢量扁平"]

    if domain == "fashion_photography":
        return ["天然织物"]

    # Spatial / industrial / craft: combine pixel traits + existing material extraction
    mapped: list[str] = []
    checks = [
        ("清水混凝土", ("concrete", "brutal", "混凝土", "清水")),
        ("原木", ("wood", "timber", "oak", "bentwood", "plywood", "木", "竹")),
        ("金属铝钢", ("steel", "aluminum", "metal", "brass", "chrome", "金属", "铝", "钢")),
        ("玻璃幕墙", ("glass", "translucent", "glazing", "玻璃")),
        ("天然石材", ("stone", "marble", "granite", "travertine", "石")),
        ("粗陶釉面", ("ceramic", "stoneware", "celadon", "porcelain", "glaze", "clay", "陶", "瓷")),
        ("夯土灰泥", ("plaster", "rammed earth", "stucco", "terra", "夯土", "灰泥", "微水泥")),
        ("纸艺印刷", ("paper", "origami", "纸")),
        ("天然织物", ("fabric", "linen", "textile", "wool", "knit", "织物", "亚麻", "棉")),
        ("绿植水体", ("plant", "foliage", "tree", "water", "garden", "moss", "flower", "绿植", "花", "树", "水")),
    ]
    for zh, kws in checks:
        if any(kw in combo for kw in kws):
            mapped.append(zh)
    for m in old_mats:
        if m not in ("纯色数字", "纸质印刷") and m not in mapped:
            mapped.append(m)
    return list(dict.fromkeys(mapped))[:2] or ["原木"]


def _map_lighting(domain: str, asset: dict[str, Any], rec: dict[str, Any], old_lighting: str) -> str:
    combo = " ".join([rec.get("free_style_primary", ""), *rec.get("visual_traits", [])]).lower()
    spec = asset.get("style_spectrums") or {}
    chroma = float((spec.get("chromatic_tension") or {}).get("score", 0.0))

    if any(k in combo for k in ("vibrant", "hyper-color", "pop art", "colorful", "neon", "red glowing", "high-saturation")) or (
        domain in ("illustration_character", "graphic_typography") and chroma >= 0.45
    ):
        return "高饱和撞色"
    if domain in ("graphic_typography", "illustration_character"):
        return "棚拍匀光"
    return old_lighting or "自然天光"


class DebiasedCritique(BaseModel):
    """Pixel-grounded, zero-BS aesthetic critique that distinguishes core match vs contrast inspiration."""

    title_zh: str = Field(..., description="Crisp accurate Chinese title (4-14 chars) strictly matching what is in the image.")
    resonance_mode: Literal["core_match", "contrast_inspiration"] = Field(
        ...,
        description="'core_match' if this fits the user's calm/minimal/tectonic/warm-neutral baseline; 'contrast_inspiration' if it is an expressive, high-saturation, anime, experimental, or avant-garde break-out reference.",
    )
    headline_insight: str = Field(..., description="One-sentence sharp aesthetic thesis (22-44 Chinese chars) grounded ONLY in actual pixels.")
    proportion_and_order: str = Field(..., description="Concrete layout, silhouette, framing, proportion or typographic grid breakdown (60-110 Chinese chars).")
    material_and_detail: str = Field(..., description="Actual visual craft/technique/detail breakdown: e.g. linework weight, pixel lattice, cel-shading, color swatches, fabric pleating, signage typography (60-110 Chinese chars).")
    light_and_palette: str = Field(..., description="Honest color & contrast hierarchy grounded in actual image colors (50-95 Chinese chars).")
    why_you_love_it: str = Field(
        ...,
        description="Honest second-person aesthetic resonance critique (65-115 Chinese chars). If resonance_mode=='contrast_inspiration', explicitly explain how this breaks out of the user's calm architectural baseline as a high-energy/experimental inspiration! Never pretend anime or pop art is 'austere minimalism'.",
    )
    design_takeaways: list[str] = Field(..., min_length=3, max_length=3, description="3 concrete transferable design takeaways in Chinese (12-24 chars each).")


CRITIQUE_SYSTEM_PROMPT = """你是顶级视觉总监、平面字体与插画策展人。你将直接观看原图像素，为用户撰写**绝对诚实、拒绝套话、拒绝硬夸极简**的中文深度美学拆解。

核心铁律：
1. **严格基于画面真实像素**：如果是二次元机能立绘，就分析它的角色头身比、黑白红三色视觉锚点、绑带机能剪裁与锐利线稿；如果是《春雨》点阵实验字体，就分析它的十字绣点阵肌理、圆形虚线辅助构图与橄榄绿冷调边框；如果是 Mika Pikazo 波普插画，就分析它的高饱和朱红底色、发丝拼贴信息密度与视觉冲击力！
2. **明确区分「核心同频 (`core_match`)」与「破圈反差灵感 (`contrast_inspiration`)」**：
   - 用户平时的空间收藏偏「构造诚实、低饱和暖灰、清晰几何秩序」；
   - 如果眼前这张图（如导视标牌、极简色卡、先锋纯色时装）确实延续了克制秩序 -> `core_match`；
   - 如果眼前这张图是高饱和波普插画、机能二次元角色、实验像素字体、浓烈水墨或先锋解构 -> 必须诚实标为 `contrast_inspiration`，在 `why_you_love_it` 中写明：「这张图打破了你日常偏爱的克制暖灰基调，是一次典型的破圈反差收藏——它用……为你提供了情绪张力/造型语言/色彩突破的灵感补给」。
3. 严禁出现空洞万能词（如不管什么图都写“展现了材质的真实感与空间留白”）。"""


def _debias_one_critique(
    client: genai.Client,
    asset: dict[str, Any],
    disc: dict[str, Any],
    img_path: Path,
) -> tuple[str, dict[str, Any]]:
    img_bytes = img_path.read_bytes()
    mime = "image/webp" if img_path.suffix.lower() == ".webp" else "image/jpeg"
    palette = ", ".join((asset.get("granular_descriptors") or {}).get("color_palette", [])[:5])
    prompt = (
        f"Domain: {ARCHETYPE_META[disc['visual_domain']]['zh']} ({disc['visual_domain']})\n"
        f"Native Style: {disc['free_style_primary']}"
        + (f" / {disc['free_style_secondary']}" if disc.get("free_style_secondary") else "")
        + f"\nMedium: {disc['medium']} | Typology: {disc['content_typology_zh']}\n"
        f"Observed Traits: {', '.join(disc.get('visual_traits', []))}\n"
        f"Aspect Ratio: {asset.get('aspect_label', '4:3')} | Palette: {palette}\n"
        "Inspect the actual image pixels and return the honest, pixel-grounded DebiasedCritique JSON."
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_bytes(data=img_bytes, mime_type=mime), prompt],
                config=types.GenerateContentConfig(
                    system_instruction=CRITIQUE_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=DebiasedCritique,
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            parsed = DebiasedCritique.model_validate_json((resp.text or "").strip())
            return asset["asset_id"], parsed.model_dump()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Debiased critique failed for {asset['asset_id']}: {last_err}")


def main() -> None:
    if not DISCOVERY_CACHE_PATH.is_file():
        raise FileNotFoundError(f"Missing Gemini open discovery cache: {DISCOVERY_CACHE_PATH}")
    src_json = ASSETS_500_JSON if ASSETS_500_JSON.is_file() else WEB_PERSONAL_JSON
    bundle = json.loads(src_json.read_text(encoding="utf-8"))
    discovery: dict[str, dict[str, Any]] = json.loads(DISCOVERY_CACHE_PATH.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]

    critique_cache: dict[str, dict[str, Any]] = {}
    if DEBIASED_CRITIQUE_CACHE_PATH.is_file():
        try:
            critique_cache = json.loads(DEBIASED_CRITIQUE_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            critique_cache = {}

    # Identify all non-spatial visual-art assets for targeted Gemini 4 Hydrogen critique debiasing
    debias_domains = {"illustration_character", "graphic_typography", "fashion_photography"}
    debias_todo = [
        a
        for a in assets
        if discovery.get(a["asset_id"], {}).get("visual_domain") in debias_domains
        and a["asset_id"] not in critique_cache
    ]
    print(
        f"Targeted Critique Debiasing [{GEMINI_MODEL}]: "
        f"total_debias_scope={sum(1 for a in assets if discovery.get(a['asset_id'], {}).get('visual_domain') in debias_domains)}, "
        f"cached={len(critique_cache)}, todo={len(debias_todo)}"
    )

    t0 = time.time()
    if debias_todo:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY required for critique debiasing.")
        client = genai.Client(api_key=key)
        lock = threading.Lock()
        done = 0
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {
                pool.submit(
                    _debias_one_critique,
                    client,
                    a,
                    discovery[a["asset_id"]],
                    WEB_PUBLIC_DIR / a["image_url"].lstrip("/"),
                ): a["asset_id"]
                for a in debias_todo
            }
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    asset_id, payload = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] debias failed {aid}: {exc}")
                    continue
                with lock:
                    critique_cache[asset_id] = payload
                    done += 1
                    if done % 20 == 0 or done == len(debias_todo):
                        DEBIASED_CRITIQUE_CACHE_PATH.write_text(
                            json.dumps(critique_cache, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        print(f"Debias progress: {done}/{len(debias_todo)} ({time.time()-t0:.1f}s)")
        DEBIASED_CRITIQUE_CACHE_PATH.write_text(
            json.dumps(critique_cache, ensure_ascii=False),
            encoding="utf-8",
        )

    # Converge all 500 assets into v5.0 Domain-Scoped Model-Native RAG Schema
    arch_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    arch_style_counts: dict[str, Counter[str]] = defaultdict(Counter)
    facet_counts: dict[str, Counter[str]] = {
        "medium": Counter(),
        "typology": Counter(),
        "materials": Counter(),
        "lighting": Counter(),
    }
    rag_jsonl_lines: list[str] = []

    for a in assets:
        aid = a["asset_id"]
        disc = discovery[aid]
        dom = disc["visual_domain"]
        dmeta = ARCHETYPE_META[dom]
        style_id = _map_style_bucket(dom, disc)
        smeta = STYLE_CATALOG[style_id]

        old_facets = a.get("rag_facets") or {}
        medium_zh = _map_medium(dom, disc)
        typology_zh = _map_typology(dom, disc)
        materials_zh = _map_materials(dom, disc, old_facets.get("materials") or [])
        lighting_zh = _map_lighting(dom, a, disc, old_facets.get("lighting") or "自然天光")

        # Apply debiased Gemini 4 Hydrogen critique if available
        if aid in critique_cache:
            dc = critique_cache[aid]
            a["title"] = dc["title_zh"].strip() or a["title"]
            a["aesthetic_critique"] = {
                "headline_insight": dc["headline_insight"].strip(),
                "proportion_and_order": dc["proportion_and_order"].strip(),
                "material_and_detail": dc["material_and_detail"].strip(),
                "light_and_palette": dc["light_and_palette"].strip(),
                "why_you_love_it": dc["why_you_love_it"].strip(),
                "design_takeaways": [x.strip() for x in dc.get("design_takeaways", [])[:3] if x.strip()],
                "resonance_mode": dc["resonance_mode"],
            }
        else:
            crit = a.get("aesthetic_critique") or {}
            crit.setdefault("resonance_mode", "core_match")
            a["aesthetic_critique"] = crit

        native_primary = " ".join(disc["free_style_primary"].strip().split())
        native_secondary = " ".join((disc.get("free_style_secondary") or "").strip().split())
        visual_traits = [t.strip() for t in disc.get("visual_traits", [])[:4] if t.strip()]

        model_prompt_tokens = list(
            dict.fromkeys(
                [
                    native_primary,
                    *([native_secondary] if native_secondary else []),
                    smeta["en"],
                    disc["medium"].strip(),
                    dmeta["en"],
                    *visual_traits,
                ]
            )
        )

        rag_facets = {
            "medium": medium_zh,
            "typology": typology_zh,
            "materials": materials_zh,
            "lighting": lighting_zh,
        }

        retrieval_text = (
            f"[{dmeta['zh']} | {smeta['zh']} ({native_primary})] "
            f"medium:{medium_zh} · typology:{typology_zh} · "
            f"materials:{','.join(materials_zh)} · lighting:{lighting_zh} | "
            f"traits:{', '.join(visual_traits)} | "
            f"{a.get('title', '')} — {(a.get('aesthetic_critique') or {}).get('headline_insight', '')}"
        )

        a["archetype"] = dom
        a["archetype_label"] = dmeta["zh"]
        a["aesthetic_style"] = style_id
        a["aesthetic_style_zh"] = smeta["zh"]
        a["aesthetic_style_en"] = smeta["en"]
        a["is_canonical_ism"] = bool(disc.get("is_canonical_ism", smeta["is_movement"]))
        a["native_style_primary"] = native_primary
        a["native_style_secondary"] = native_secondary
        a["visual_traits"] = visual_traits
        a["discovery_confidence"] = round(float(disc.get("confidence", 0.9)), 3)
        a["sub_style"] = smeta["zh"]
        a["sub_category"] = smeta["zh"]
        a["rag_facets"] = rag_facets
        a["rag_doc"] = {
            "doc_id": aid,
            "archetype": dom,
            "archetype_en": dmeta["en"],
            "style_id": style_id,
            "style_zh": smeta["zh"],
            "style_en": smeta["en"],
            "native_style_primary": native_primary,
            "native_style_secondary": native_secondary,
            "is_canonical_ism": a["is_canonical_ism"],
            "facets": rag_facets,
            "visual_traits": visual_traits,
            "model_prompt_tokens": model_prompt_tokens,
            "palette": (a.get("granular_descriptors") or {}).get("color_palette", [])[:5],
            "aspect_ratio": a.get("aspect_label", "4:3"),
            "resonance_mode": a["aesthetic_critique"].get("resonance_mode", "core_match"),
            "retrieval_text": retrieval_text,
        }

        arch_counts[dom] += 1
        style_counts[style_id] += 1
        arch_style_counts[dom][style_id] += 1
        facet_counts["medium"][medium_zh] += 1
        facet_counts["typology"][typology_zh] += 1
        for mat in materials_zh:
            facet_counts["materials"][mat] += 1
        facet_counts["lighting"][lighting_zh] += 1

        crit = a["aesthetic_critique"]
        rag_jsonl_lines.append(
            json.dumps(
                {
                    **a["rag_doc"],
                    "title": a["title"],
                    "source_origin": a.get("source_origin", ""),
                    "image_url": a.get("image_url", ""),
                    "headline_insight": crit.get("headline_insight", ""),
                    "why_you_love_it": crit.get("why_you_love_it", ""),
                    "proportion_and_order": crit.get("proportion_and_order", ""),
                    "material_and_detail": crit.get("material_and_detail", ""),
                    "light_and_palette": crit.get("light_and_palette", ""),
                    "design_takeaways": crit.get("design_takeaways", []),
                },
                ensure_ascii=False,
            )
        )

    archetype_taxonomy = []
    for dom in ARCHETYPE_ORDER:
        cnt = arch_counts.get(dom, 0)
        sc = arch_style_counts[dom]
        archetype_taxonomy.append(
            {
                "archetype": dom,
                "label": ARCHETYPE_META[dom]["zh"],
                "count": cnt,
                "sub_styles": [
                    {
                        "sub_style": STYLE_CATALOG[sid]["zh"],
                        "style_id": sid,
                        "style_en": STYLE_CATALOG[sid]["en"],
                        "is_movement": STYLE_CATALOG[sid]["is_movement"],
                        "count": c,
                    }
                    for sid, c in sc.most_common()
                ],
            }
        )

    bundle["version"] = "5.0.0-gemini-rag-atlas-500"
    bundle["archetype_taxonomy"] = archetype_taxonomy
    bundle["archetype_counts"] = dict(arch_counts)
    bundle["rag_schema"] = {
        "schema_version": "2.0.0-gemini-domain-scoped",
        "vision_model": GEMINI_MODEL,
        "max_styles": len(style_counts),
        "facet_keys": [
            {"key": "medium", "label_zh": "视觉媒介", "cardinality": "single", "max_vocab": len(facet_counts["medium"])},
            {"key": "typology", "label_zh": "内容品类", "cardinality": "single", "max_vocab": len(facet_counts["typology"])},
            {"key": "materials", "label_zh": "材质与技法", "cardinality": "1-2", "max_vocab": len(facet_counts["materials"])},
            {"key": "lighting", "label_zh": "光影色域", "cardinality": "single", "max_vocab": len(facet_counts["lighting"])},
        ],
        "styles": [
            {
                "style_id": sid,
                "zh": STYLE_CATALOG[sid]["zh"],
                "en": STYLE_CATALOG[sid]["en"],
                "is_movement": STYLE_CATALOG[sid]["is_movement"],
                "count": c,
            }
            for sid, c in style_counts.most_common()
        ],
        "facet_counts": {
            k: [{"value": val, "count": cnt} for val, cnt in counter.most_common()]
            for k, counter in facet_counts.items()
        },
        "jsonl_url": "/data/aethervault_rag_500.jsonl",
    }

    WEB_PERSONAL_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    ASSETS_500_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")

    print("\n=== v5.0 Domain-Scoped Model-Native Taxonomy (Exact 500 Assets) ===")
    for node in archetype_taxonomy:
        st_str = ", ".join(f"{s['sub_style']}({s['style_en']}:{s['count']})" for s in node["sub_styles"])
        print(f"  {node['label']} [{node['archetype']}]: {node['count']} -> {st_str}")
    print("\n=== 4 Bounded Cross-Media RAG Facets ===")
    for fk, counter in facet_counts.items():
        top_str = ", ".join(f"{v}({c})" for v, c in counter.most_common(10))
        print(f"  {fk} [{len(counter)}]: {top_str}")
    contrast_cnt = sum(1 for a in assets if a["aesthetic_critique"].get("resonance_mode") == "contrast_inspiration")
    print(
        f"\nResonance split: core_match={len(assets)-contrast_cnt}, contrast_inspiration={contrast_cnt} | "
        f"Elapsed={time.time()-t0:.1f}s"
    )


if __name__ == "__main__":
    main()
