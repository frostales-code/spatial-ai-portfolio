"""Deep Aesthetic Analysis & Two-Tier Archetype Taxonomy Pipeline across all 500 Assets.

Classifies every image purely by its visual content into 7 canonical primary archetypes
and 24 controlled sub-styles, extracts exact pixel dimensions & aspect ratios, and generates
publication-grade Chinese aesthetic critiques covering:
  - One-sentence headline insight (`headline_insight`)
  - Proportion, scale & geometric composition (`proportion_and_order`)
  - Materiality & construction/craft details (`material_and_detail`)
  - Lighting hierarchy & color restraint (`light_and_palette`)
  - Why it resonates with the user's personal aesthetic profile (`why_you_love_it`)
  - 3 transferable design takeaways (`design_takeaways`)

Saves incremental cache to `data/pinterest_500/_deep_aesthetic_500_cache.json` and
enriches both `web/public/data/aethervault_showcase_v1.json` and
`data/pinterest_500/aethervault_assets_500.json`.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI, RateLimitError
from PIL import Image
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
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
PROFILE_JSON_PATH = REPO_ROOT / "data" / "pinterest_500" / "aesthetic_profile_523.json"
DEEP_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_deep_aesthetic_500_cache.json"

DEFAULT_MODEL = "gpt-4o-mini"

ArchetypeLiteral = Literal[
    "architecture",
    "interior",
    "landscape",
    "industrial",
    "craft",
    "graphic",
    "editorial",
]

ARCHETYPE_ORDER: tuple[ArchetypeLiteral, ...] = (
    "architecture",
    "interior",
    "landscape",
    "industrial",
    "craft",
    "graphic",
    "editorial",
)

ARCHETYPE_LABELS: dict[ArchetypeLiteral, str] = {
    "architecture": "建筑设计",
    "interior": "室内设计",
    "landscape": "景观空间",
    "industrial": "工业设计",
    "craft": "器物工艺",
    "graphic": "平面视觉",
    "editorial": "时尚影像",
}

CANONICAL_SUB_STYLES: dict[ArchetypeLiteral, tuple[str, ...]] = {
    "architecture": (
        "极简主义",
        "高技建构",
        "地景建筑",
        "东方木构",
    ),
    "interior": (
        "现代静谧",
        "极简公区",
        "展陈空间",
        "侘寂空间",
    ),
    "landscape": (
        "现代景观",
        "禅意庭院",
        "水景地形",
    ),
    "industrial": (
        "现代家具",
        "功能主义",
        "灯具细节",
    ),
    "craft": (
        "东方器物",
        "原生肌理",
        "纤维手作",
    ),
    "graphic": (
        "空间导视",
        "品牌图形",
        "色彩与UI",
        "瑞士网格",
    ),
    "editorial": (
        "先锋时装",
        "光影摄影",
        "概念艺术",
    ),
}

LEGACY_SUB_STYLE_MAP: dict[str, str] = {
    "几何清水与极简块面": "极简主义",
    "高技派金属模数立面": "高技建构",
    "消隐地景与粗粝石土": "地景建筑",
    "东方式挑檐与温润木构": "东方木构",
    "现代静谧居住与软装尺度": "现代静谧",
    "秩序感极简办公与公共大堂": "极简公区",
    "美术馆级留白与光影展陈": "展陈空间",
    "侘寂暖木与茶咖慢空间": "侘寂空间",
    "折线步道与现代生态公园": "现代景观",
    "禅意庭院与框景灰空间": "禅意庭院",
    "静水倒影与微地形介入": "水景地形",
    "包豪斯钢管与现代曲木家具": "现代家具",
    "博朗式功能主义精密仪器": "功能主义",
    "极简建筑感灯具与五金节点": "灯具细节",
    "东方柴烧粗陶与侘寂茶器": "东方器物",
    "天然石木夯土与岁月包浆": "原生肌理",
    "织物褶皱与雕塑感手作器物": "纤维手作",
    "建筑空间导视与极简标牌": "空间导视",
    "几何构成符号与品牌视觉": "品牌图形",
    "低饱和建筑感色彩系统与UI": "色彩与UI",
    "瑞士国际主义网格与字体排版": "瑞士网格",
    "建筑感廓形与解构主义时装": "先锋时装",
    "高反差几何光影建筑摄影": "光影摄影",
    "静谧极简静物与概念艺术": "概念艺术",
}

_SUB_STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "极简主义": ("清水", "混凝土", "块面", "极简", "几何", "体量", "门卫", "立面", "白墙"),
    "东方木构": ("挑檐", "木构", "东方", "斗拱", "榫卯", "坡屋顶", "连廊", "木"),
    "高技建构": ("高技", "金属", "模数", "幕墙", "铝板", "钢架", "张拉", "产业园", "表皮"),
    "地景建筑": ("地景", "消隐", "夯土", "粗粝", "野奢", "礁石", "山地", "洞穴", "毛石"),
    "侘寂空间": ("侘寂", "咖啡", "茶", "慢空间", "餐饮", "烘焙", "店", "原木"),
    "展陈空间": ("美术馆", "展陈", "画廊", "gallery", "疗愈", "展览", "过廊", "留白"),
    "现代静谧": ("居住", "住宅", "家装", "卧室", "客厅", "卫浴", "软装", "酒店"),
    "极简公区": ("办公", "大堂", "商业", "中庭", "走廊", "实验室", "秩序"),
    "禅意庭院": ("庭院", "禅", "框景", "灰空间", "中庭花园", "枯山水", "竹"),
    "现代景观": ("公园", "步道", "折线", "生态", "广场", "滨水", "铺装", "绿地"),
    "水景地形": ("静水", "倒影", "水景", "微地形", "水面", "浅池"),
    "功能主义": ("博朗", "braun", "功能主义", "仪器", "音响", "相机", "收音机", "旋钮", "工业"),
    "现代家具": ("包豪斯", "钢管", "椅", "曲木", "家具", "桌", "凳", "aalto", "stool"),
    "灯具细节": ("灯", "吊灯", "台灯", "五金", "节点", "把手", "螺栓", "金属"),
    "东方器物": ("陶", "瓷", "茶碗", "花器", "柴烧", "釉", "器皿", "壶"),
    "原生肌理": ("石", "夯土", "包浆", "烧杉", "青苔", "肌理", "壁面", "材质样板"),
    "纤维手作": ("织物", "亚麻", "褶皱", "编织", "铜", "雕塑", "手作", "木碗"),
    "空间导视": ("导视", "标牌", "标识", "厕所", "门牌", "指引", "看板", "宣传墙"),
    "瑞士网格": ("字体", "排版", "海报", "瑞士", "印刷", "书籍", "网格", "poster", "typography"),
    "色彩与UI": ("色", "色卡", "ui", "界面", "配色", "palette", "app", "网页"),
    "品牌图形": ("构成", "符号", "logo", "标志", "插画", "图形", "品牌", "插图"),
    "先锋时装": ("时装", "服装", "穿搭", "廓形", "风衣", "连衣裙", "三宅", "fashion"),
    "光影摄影": ("光影", "影子", "阴影", "楼梯", "黑白", "天光", "剪影"),
    "概念艺术": ("静物", "概念", "装置", "雕塑", "情绪", "艺术"),
}


class DeepAestheticItem(BaseModel):
    """Strict Structured Output schema for deep aesthetic criticism of one image."""

    model_config = ConfigDict(extra="forbid")

    title_zh: str = Field(
        ...,
        description="Concise accurate Chinese title (6-16 chars), crisp & monograph-grade without generic fluff.",
    )
    archetype: ArchetypeLiteral = Field(
        ...,
        description="Primary visual archetype strictly based on actual visual content.",
    )
    sub_style: str = Field(
        ...,
        description="Exact canonical Chinese sub-style belonging to the chosen archetype.",
    )
    headline_insight: str = Field(
        ...,
        description="One-sentence aesthetic thesis (24-46 Chinese chars) pinpointing why the composition works.",
    )
    proportion_and_order: str = Field(
        ...,
        description="Detailed proportion, scale, framing & geometric composition analysis (65-115 Chinese chars): height/width splits, 1:3 or 2:8 ratios, negative space breathing room, axis symmetry/asymmetry, visual anchor.",
    )
    material_and_detail: str = Field(
        ...,
        description="Detailed materiality, tactility, surface grain & joint/detail craft analysis (65-115 Chinese chars).",
    )
    light_and_palette: str = Field(
        ...,
        description="Detailed lighting direction, shadow softness/contrast, color temperature & area-weighted palette hierarchy (55-100 Chinese chars).",
    )
    why_you_love_it: str = Field(
        ...,
        description="Personalized resonance critique explaining specifically why this appeals to a designer with +0.40 tectonic honesty, +0.30 warm materiality, +0.26 geometric order, +0.21 shadow drama & neutral-warm palette preference (70-120 Chinese chars).",
    )
    design_takeaways: list[str] = Field(
        ...,
        description="3 concrete, transferable design takeaways in Chinese (12-24 chars each).",
    )


def _normalize_sub_style(archetype: ArchetypeLiteral, raw_sub_style: str, context_text: str = "") -> str:
    options = CANONICAL_SUB_STYLES[archetype]
    cleaned = raw_sub_style.strip()
    mapped = LEGACY_SUB_STYLE_MAP.get(cleaned, cleaned)
    if mapped in options:
        return mapped

    probe = f"{mapped} {cleaned} {context_text}".lower()
    best_opt = options[0]
    best_score = -1.0
    for opt in options:
        score = 0.0
        for kw in _SUB_STYLE_KEYWORDS.get(opt, ()):
            if kw.lower() in probe:
                score += 2.0
        # Character overlap fallback
        overlap = len(set(cleaned) & set(opt))
        score += overlap * 0.25
        if score > best_score:
            best_score = score
            best_opt = opt
    return best_opt


def _compute_aspect_info(img_path: Path) -> tuple[int, int, str]:
    with Image.open(img_path) as im:
        w, h = im.size
    ratio = w / max(1, h)
    known = [
        (1.0, "1:1"),
        (4 / 3, "4:3"),
        (3 / 4, "3:4"),
        (3 / 2, "3:2"),
        (2 / 3, "2:3"),
        (16 / 9, "16:9"),
        (9 / 16, "9:16"),
        (16 / 10, "16:10"),
        (10 / 16, "10:16"),
        (5 / 4, "5:4"),
        (4 / 5, "4:5"),
        (21 / 9, "21:9"),
    ]
    closest_r, closest_lbl = min(known, key=lambda kv: abs(kv[0] - ratio))
    if abs(closest_r - ratio) <= 0.08:
        label = closest_lbl
    elif ratio >= 1.0:
        label = f"{ratio:.2f}:1"
    else:
        label = f"1:{1 / ratio:.2f}"
    return w, h, label


def _build_system_prompt(profile_summary: str) -> str:
    taxonomy_lines = "\n".join(
        f"- archetype=`{arch}` ({ARCHETYPE_LABELS[arch]}): sub_style MUST be one of [{', '.join(CANONICAL_SUB_STYLES[arch])}]"
        for arch in ARCHETYPE_ORDER
    )
    return f"""你是顶级建筑评论家、工业设计策展人与视觉美学顾问（熟悉现代建筑构筑、北欧/东方侘寂材质、Dieter Rams 功能主义、瑞士网格排版与高级时装廓形）。

现在你正在为一位拥有鲜明个人品味的空间与产品设计师（共 500 张精选个人图库），对单张参考图执行【精准一级分类 -> 自动二级风格归类 -> 深度美学与比例拆解】。

=== 1. 用户的个人真实审美画像基准（通过全量 523 张 Pinterest 统计得出） ===
{profile_summary}
核心审美共振点：
1) 构造诚实度极强 (+0.40)：迷恋真实材料交接、结构明缝、机械精度、干法收口与“不伪装的建构美”，排斥塑料感假装饰。
2) 温润触觉情绪 (+0.30) + 高明度克制色底：偏爱高明度矿石白/暖灰 (#E4E4E4 / #FCFCFC) 搭配橡木/夯土/粗陶/古铜暖调 (#B49C84 / #B4B49C) 与深炭压阵 (#242424)。
3) 几何秩序 (+0.26) 与留白克制 (-0.07)：喜欢清晰的黄金/整数分割比例、水平压低或秩序阵列、不拥挤的视觉呼吸区。
4) 光影层次 (+0.21)：着迷自然天光/漫射光斜射切分体量、柔和而不浊的阴影过渡。

=== 2. 严格二级分类词典（必须完全依据画面真实视觉内容，切勿盲信旧相册名字！） ===
{taxonomy_lines}

特别注意纠偏：
- 即使某张图原本保存在“咖啡店/凤南”画板中，如果画面实质是室外建筑立面，选 `architecture`；如果是室内桌椅吧台氛围，选 `interior`；如果是园区绿地道路，选 `landscape`；如果是导视牌/海报/配色卡/UI 截图，选 `graphic`；如果是单件椅子/灯具/电子仪器，选 `industrial`；如果是单独陶瓷茶碗/木石肌理特写，选 `craft`；如果是服装穿搭/纯粹光影建筑摄影构图或概念静物，选 `editorial`。
- `sub_style` 必须精确选自上面对应 `archetype` 括号内的标准中文选项之一。

=== 3. 深度美学拆解要求（全中文、有洞察、拒绝假大空套话） ===
- `proportion_and_order`（65-115字）：一定要指出具体的画面结构与比例关系！例如：天地留白占比、顶檐与门洞高宽比（如约1:3横向舒展/细长竖构图）、三分法或对角线牵引、阵列韵律节奏、视线停驻焦点，以及为何这个比例显得高级、不呆板也不局促。
- `material_and_detail`（65-115字）：精准点名画面中真实可见的材料对比与细部工艺（如阳极氧化铝的哑光倒角与胡桃木温润感对比、微水泥零踢脚阴角收口、粗陶开片釉面的颗粒感、无衬线体字距张力等）。
- `light_and_palette`（55-100字）：分析光线角度、漫射与硬影对比、高光溢出控制，以及色彩面积配比（如 75% 暖灰矿石基底 + 20% 深胡桃木 + 5% 黑钢点睛）。
- `why_you_love_it`（70-120字）：用第二人称（「你之所以会被这张图击中，是因为……」）直接将当前画面特征映射到上述个人审美基因上——点明它究竟满足了你对哪种尺度感、秩序感、材料真实性或情绪松弛感的向往。
- `design_takeaways`（恰好 3 条，每条 12-24 字）：提炼成可复用到未来空间/工业/视觉设计项目中的实战方法论短句。
"""


def _encode_image_b64(img_path: Path, max_side: int = 448) -> str:
    with Image.open(img_path) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=80, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _analyze_one_asset(
    oai: OpenAI,
    system_prompt: str,
    asset: dict[str, Any],
    img_path: Path,
) -> tuple[str, dict[str, Any], dict[str, int]]:
    b64 = _encode_image_b64(img_path, max_side=448)
    w = int(asset.get("width") or 680)
    h = int(asset.get("height") or 510)
    aspect_lbl = asset.get("aspect_label") or f"{w}x{h}"
    palette = ", ".join(asset.get("granular_descriptors", {}).get("color_palette", [])[:5])
    spec = asset.get("style_spectrums", {})
    spec_str = ", ".join(
        f"{k}={spec[k]['score']:+.2f}(s={spec[k]['salience']:.2f})"
        for k in (
            "tectonic_honesty",
            "geometric_order",
            "thermal_mood",
            "lighting_drama",
            "spatial_density",
            "surface_entropy",
            "chromatic_tension",
        )
        if k in spec
    )
    user_text = (
        f"Asset ID: {asset['asset_id']}\n"
        f"Pixel Size & Ratio: {w}x{h} (Aspect {aspect_lbl})\n"
        f"Prior Board / Hint: {asset.get('board_name', '')} | Old Title: {asset.get('title', '')}\n"
        f"Extracted OKLab Palette: {palette}\n"
        f"Pre-measured 8-Axis Spectrums: {spec_str}\n"
        "Inspect the actual image pixels now and produce the precise Archetype, Sub-Style, and Deep Aesthetic Critique JSON."
    )

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            completion = oai.beta.chat.completions.parse(
                model="gpt-4o" if attempt >= 2 else DEFAULT_MODEL,
                temperature=0.15 if attempt == 0 else 0.35,
                frequency_penalty=0.0 if attempt == 0 else 0.35,
                max_tokens=1100,
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
                response_format=DeepAestheticItem,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Empty parsed response")
            payload = parsed.model_dump()
            usage = completion.usage
            pt = int(getattr(usage, "prompt_tokens", 0) or 0)
            ct = int(getattr(usage, "completion_tokens", 0) or 0)
            details = getattr(usage, "prompt_tokens_details", None)
            cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
            return (
                asset["asset_id"],
                payload,
                {"prompt_tokens": pt, "cached_tokens": cached, "completion_tokens": ct},
            )
        except RateLimitError as exc:
            last_err = exc
            time.sleep(min(18.0, 2.5 * (attempt + 1)))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.2 * (attempt + 1))

    raise RuntimeError(f"Deep aesthetic critique failed for {asset['asset_id']}: {last_err}")


def main() -> None:
    if not WEB_SHOWCASE_JSON.is_file():
        raise FileNotFoundError(f"Showcase JSON missing: {WEB_SHOWCASE_JSON}")
    bundle = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]

    profile = json.loads(PROFILE_JSON_PATH.read_text(encoding="utf-8")) if PROFILE_JSON_PATH.is_file() else {}
    sig = profile.get("axis_signature", {})
    profile_summary = " · ".join(
        f"{k}: {v['weighted_mean']:+.3f}" for k, v in sig.items() if "weighted_mean" in v
    )
    sys_prompt = _build_system_prompt(profile_summary)

    # Measure real pixel dimensions & aspect ratios for every asset
    for a in assets:
        rel = a["image_url"].lstrip("/")
        img_path = WEB_PUBLIC_DIR / rel
        if img_path.is_file():
            w, h, lbl = _compute_aspect_info(img_path)
            a["width"] = w
            a["height"] = h
            a["aspect_label"] = lbl
        else:
            a["width"] = 680
            a["height"] = 510
            a["aspect_label"] = "4:3"

    cache: dict[str, Any] = {}
    if DEEP_CACHE_PATH.is_file():
        try:
            cache = json.loads(DEEP_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [a for a in assets if a["asset_id"] not in cache]
    print(f"Deep Aesthetic Critique: total={len(assets)}, cached={len(cache)}, todo={len(todo)}")

    tot_pt = 0
    tot_cached = 0
    tot_ct = 0
    t0 = time.time()

    if todo:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY env var is required to run VLM deep analysis.")
        oai = OpenAI()
        lock = threading.Lock()
        done = 0
        with ThreadPoolExecutor(max_workers=16) as pool:
            futs = {
                pool.submit(
                    _analyze_one_asset,
                    oai,
                    sys_prompt,
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
                    print(f"[WARN] Failed {aid}: {exc}")
                    continue
                with lock:
                    cache[asset_id] = payload
                    tot_pt += usage["prompt_tokens"]
                    tot_cached += usage["cached_tokens"]
                    tot_ct += usage["completion_tokens"]
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        DEEP_CACHE_PATH.write_text(
                            json.dumps(cache, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        print(f"Progress: {done}/{len(todo)} analyzed ({time.time() - t0:.1f}s)")

        DEEP_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Apply normalized taxonomy & deep aesthetic critique to every asset
    arch_counts: Counter[str] = Counter()
    sub_counts_by_arch: dict[str, Counter[str]] = {arch: Counter() for arch in ARCHETYPE_ORDER}
    missing = 0

    for a in assets:
        aid = a["asset_id"]
        c = cache.get(aid)
        if not c:
            missing += 1
            continue
        arch: ArchetypeLiteral = c["archetype"]
        if arch not in ARCHETYPE_LABELS:
            arch = "architecture"
        norm_sub = _normalize_sub_style(
            arch,
            c["sub_style"],
            context_text=f"{c.get('title_zh', '')} {a.get('board_name', '')}",
        )
        arch_label = ARCHETYPE_LABELS[arch]
        a["title"] = c["title_zh"].strip() or a["title"]
        a["archetype"] = arch
        a["archetype_label"] = arch_label
        a["sub_style"] = norm_sub
        a["sub_category"] = norm_sub
        a["aesthetic_critique"] = {
            "headline_insight": c["headline_insight"].strip(),
            "proportion_and_order": c["proportion_and_order"].strip(),
            "material_and_detail": c["material_and_detail"].strip(),
            "light_and_palette": c["light_and_palette"].strip(),
            "why_you_love_it": c["why_you_love_it"].strip(),
            "design_takeaways": [t.strip() for t in c.get("design_takeaways", [])[:3] if t.strip()],
        }
        arch_counts[arch] += 1
        sub_counts_by_arch[arch][norm_sub] += 1

    if missing > 0:
        raise RuntimeError(f"{missing} assets are still missing deep critique! Re-run to finish cached remainder.")

    archetype_taxonomy = []
    for arch in ARCHETYPE_ORDER:
        cnt = arch_counts.get(arch, 0)
        subs = [
            {"sub_style": sub, "count": sub_counts_by_arch[arch].get(sub, 0)}
            for sub in CANONICAL_SUB_STYLES[arch]
            if sub_counts_by_arch[arch].get(sub, 0) > 0
        ]
        # Append any remaining counted sub-styles sorted desc
        subs.sort(key=lambda x: -x["count"])
        archetype_taxonomy.append(
            {
                "archetype": arch,
                "label": ARCHETYPE_LABELS[arch],
                "count": cnt,
                "sub_styles": subs,
            }
        )

    bundle["version"] = "3.0.0-aesthetic-atlas-500"
    bundle["archetype_taxonomy"] = archetype_taxonomy
    bundle["archetype_counts"] = dict(arch_counts)

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

    print("\n=== Archetype Taxonomy (Exact 500 Assets) ===")
    for node in archetype_taxonomy:
        sub_str = ", ".join(f"{s['sub_style']}({s['count']})" for s in node["sub_styles"])
        print(f"  {node['label']} [{node['archetype']}]: {node['count']} -> {sub_str}")
    print(f"Total Cost (this run): CNY {cost_cny:.4f} (cache hit={cache_rate:.1f}%) | Elapsed={time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
