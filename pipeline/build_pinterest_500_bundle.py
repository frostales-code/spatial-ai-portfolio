"""Pack Exact 500-Asset Personal AetherVault Showcase Bundle (390 Pinterest Core + 110 Profile Expansion).

Replaces the old generic 80-image gallery in `web/public/data/aethervault_showcase_v1.json`
with 500 personal-profile-curated assets stored under `web/public/assets/pinterest_500/`
(gitignored so private Pinterest photos remain strictly local).
"""

from __future__ import annotations

import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .aethervault_schema import (
    AXIS_IDS,
    SPECTRUM_AXES,
    AestheticAsset,
    CompilerPrimitives,
    GranularDescriptors,
    StyleSpectrumAxis,
    SubjectIsolation,
)
from .anchor_specs import GOLDEN_ANCHOR_RUBRICS, estimate_ingestion_cost_cny
from .research_pinterest_523 import OUT_DIR, PROFILE_JSON_PATH, RESEARCH_JSON_PATH
from .expand_to_500 import EXPANSION_SELECTED_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_PINTEREST_500_DIR = WEB_PUBLIC_DIR / "assets" / "pinterest_500"
WEB_SHOWCASE_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
ASSETS_500_JSON = OUT_DIR / "aethervault_assets_500.json"
CONTACT_SHEET_500 = OUT_DIR / "contact_sheet_500.jpg"

DOMAIN_LABELS = {
    "architecture": "建筑与空间",
    "industrial": "工业与构造",
    "editorial": "光影与影像",
    "craft": "器物与肌理",
    "graphic": "平面与界面",
}

CANONICAL_SUBCATEGORIES = (
    "建筑立面与构造",
    "商业咖啡与餐饮空间",
    "疗愈与文化展览空间",
    "景观与公共灰空间",
    "室内陈设与住宅空间",
    "空间导视与标识装置",
    "工业器型与材料节点",
    "瑞士平面与字体排版",
    "极简数字界面与配色",
    "先锋时尚与光影摄影",
)


def _canonicalize_subcategory(raw: str, domain: str, board: str = "") -> str:
    txt = f"{raw} {board}".lower()
    if any(k in txt for k in ("咖啡", "茶", "餐饮", "naichadian", "cafe", "bakery", "食")):
        return "商业咖啡与餐饮空间"
    if any(k in txt for k in ("标识", "标志", "导视", "signage", "wayfinding", "宣传")):
        return "空间导视与标识装置"
    if any(k in txt for k in ("界面", "ui", "配色", "palette", "色彩")):
        return "极简数字界面与配色"
    if any(k in txt for k in ("字体", "排版", "平面", "poster", "typography", "graphic", "构成")):
        return "瑞士平面与字体排版"
    if any(k in txt for k in ("时尚", "服装", "fashion", "摄影", "光影", "editorial")):
        return "先锋时尚与光影摄影"
    if any(k in txt for k in ("公园", "景观", "灰空", "庭院", "园")):
        return "景观与公共灰空间"
    if any(k in txt for k in ("疗愈", "展览", "画廊", "gallery", "文化", "艺术", "博物馆", "过廊")):
        return "疗愈与文化展览空间"
    if any(k in txt for k in ("住宅", "居住", "家装", "室内", "办公", "酒店", "卫生间")):
        return "室内陈设与住宅空间"
    if any(k in txt for k in ("立面", "建筑", "门卫", "产业园", "凤南", "学校")):
        return "建筑立面与构造"
    if any(k in txt for k in ("陶", "瓷", "木", "石", "器物", "工艺", "手作", "craft", "纹理", "肌理")):
        return "工业器型与材料节点"

    fallback = {
        "architecture": "建筑立面与构造",
        "industrial": "工业器型与材料节点",
        "editorial": "先锋时尚与光影摄影",
        "craft": "工业器型与材料节点",
        "graphic": "瑞士平面与字体排版",
    }
    return fallback.get(domain, "建筑立面与构造")


def _extract_hex_palette(img: Image.Image, n_colors: int = 5) -> list[str]:
    small = img.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
    quant = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette() or []
    counts = Counter(quant.getdata())
    hexes: list[str] = []
    for idx, _ in counts.most_common(n_colors):
        if idx * 3 + 2 < len(pal):
            r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
            hexes.append(f"#{r:02X}{g:02X}{b:02X}")
    return hexes or ["#EAEAE6", "#9A9A95", "#2B2D30"]


def _save_web_webp(src_path: Path, dst_path: Path, max_side: int = 680) -> list[str]:
    with Image.open(src_path) as im:
        rgb = im.convert("RGB")
        hexes = _extract_hex_palette(rgb, 5)
        rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        rgb.save(dst_path, format="WEBP", quality=78, method=4)
    return hexes


def _build_contact_sheet(asset_entries: list[dict[str, Any]], out_path: Path) -> None:
    cols = 25
    rows = math.ceil(len(asset_entries) / cols)
    cw, ch = 120, 90
    sheet = Image.new("RGB", (cols * cw, rows * ch), (14, 16, 21))
    for i, a in enumerate(asset_entries):
        rel = a["image_url"].lstrip("/")
        p = WEB_PUBLIC_DIR / rel
        if not p.is_file():
            continue
        try:
            with Image.open(p) as im:
                rgb = im.convert("RGB")
                rgb.thumbnail((cw, ch), Image.Resampling.BILINEAR)
                x = (i % cols) * cw + (cw - rgb.width) // 2
                y = (i // cols) * ch + (ch - rgb.height) // 2
                sheet.paste(rgb, (x, y))
        except Exception:
            continue
    sheet.save(out_path, format="JPEG", quality=82, optimize=True)


def main() -> None:
    research = json.loads(RESEARCH_JSON_PATH.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE_JSON_PATH.read_text(encoding="utf-8"))
    expansion = json.loads(EXPANSION_SELECTED_PATH.read_text(encoding="utf-8"))

    kept_pinterest = [
        it for it in research["items"] if it.get("selection_status") == "kept_pinterest_core"
    ]
    exp_items = expansion["items"]

    # Ensure exact 500 total
    target_total = 500
    if len(kept_pinterest) + len(exp_items) > target_total:
        exp_items = exp_items[: max(0, target_total - len(kept_pinterest))]

    print(
        f"Packing exact {len(kept_pinterest)} Pinterest core + {len(exp_items)} profile expansion "
        f"= {len(kept_pinterest) + len(exp_items)} total assets"
    )

    # Clean output web directory so ZERO stale files remain
    if WEB_PINTEREST_500_DIR.exists():
        shutil.rmtree(WEB_PINTEREST_500_DIR)
    WEB_PINTEREST_500_DIR.mkdir(parents=True, exist_ok=True)

    packed_assets: list[dict[str, Any]] = []
    domain_seq: Counter[str] = Counter()

    # 1. Pack kept Pinterest core assets (is_personal_prior = True)
    for rec in kept_pinterest:
        vlm = rec["vlm"]
        dom = vlm["domain"]
        domain_seq[dom] += 1
        asset_id = f"pin_{dom[:4]}_{domain_seq[dom]:03d}"
        src_img = Path(rec["thumb_1024_path"]) if rec.get("thumb_1024_path") and Path(rec["thumb_1024_path"]).is_file() else Path(rec["thumb_512_path"])
        if not src_img.is_file():
            src_img = Path(rec["original_path"])
        dst_webp = WEB_PINTEREST_500_DIR / f"{asset_id}.webp"
        fallback_hexes = _save_web_webp(src_img, dst_webp, max_side=680)
        hex_palette = rec.get("hex_palette") or fallback_hexes

        sub_cat = _canonicalize_subcategory(vlm.get("sub_category", ""), dom, rec.get("primary_board", ""))
        spectrums = {
            ax: StyleSpectrumAxis(
                score=round(max(-1.0, min(1.0, float(vlm["style_spectrums"][ax]["score"]))), 2),
                salience=round(max(0.0, min(1.0, float(vlm["style_spectrums"][ax]["salience"]))), 2),
            )
            for ax in AXIS_IDS
        }
        contract = AestheticAsset(
            asset_id=asset_id,
            title=vlm["title_zh"].strip() or rec.get("pin_title") or asset_id,
            subject_isolation=SubjectIsolation(
                domain=dom,
                domain_label=f"Pinterest · {rec.get('primary_board', DOMAIN_LABELS[dom])}",
                primary_subject=vlm["primary_subject"].strip() or "architectural reference",
                is_personal_prior=True,
            ),
            style_spectrums=spectrums,
            granular_descriptors=GranularDescriptors(
                optics_camera=vlm["optics_camera"].strip() or "balanced architectural framing",
                lighting_rig=vlm["lighting_rig"].strip() or "natural ambient daylight",
                material_stack=vlm["material_stack"].strip() or "tactile stone, timber and matte surfaces",
                color_palette=hex_palette[:5],
            ),
            compiler_primitives=CompilerPrimitives(
                positive_tokens=[t.strip() for t in vlm.get("positive_tokens", [])[:5] if t.strip()] or ["minimalist", "tectonic"],
                negative_guardrails=[t.strip() for t in vlm.get("negative_guardrails", [])[:4] if t.strip()] or ["cluttered", "plastic CGI"],
            ),
        )
        dumped = contract.model_dump()
        dumped.update(
            {
                "title_en": vlm.get("title_en", ""),
                "image_url": f"/assets/pinterest_500/{asset_id}.webp",
                "license": "Personal Pinterest Reference (Local Only)",
                "source_kind": "pinterest_personal",
                "source_origin": "pinterest_personal",
                "source_url": rec.get("source_url", ""),
                "board_name": rec.get("primary_board", "未分类"),
                "sub_category": sub_cat,
                "aesthetic_motifs": vlm.get("aesthetic_motifs", [])[:4],
                "aesthetic_quality_score": int(vlm.get("aesthetic_quality_score", 8)),
                "akb_prior_asset_id": rec.get("akb_asset_id"),
                "akb_board_hint": rec.get("primary_board"),
            }
        )
        packed_assets.append(dumped)

    # 2. Pack Profile-Matched Expansion assets (is_personal_prior = False)
    for rec in exp_items:
        vlm = rec["vlm"]
        dom = vlm["domain"]
        domain_seq[dom] += 1
        asset_id = f"exp_{dom[:4]}_{domain_seq[dom]:03d}"
        src_img = Path(rec["local_path"])
        dst_webp = WEB_PINTEREST_500_DIR / f"{asset_id}.webp"
        hex_palette = _save_web_webp(src_img, dst_webp, max_side=680)

        sub_cat = _canonicalize_subcategory(vlm.get("sub_category", ""), dom, rec.get("query", ""))
        spectrums = {
            ax: StyleSpectrumAxis(
                score=round(max(-1.0, min(1.0, float(vlm["style_spectrums"][ax]["score"]))), 2),
                salience=round(max(0.0, min(1.0, float(vlm["style_spectrums"][ax]["salience"]))), 2),
            )
            for ax in AXIS_IDS
        }
        contract = AestheticAsset(
            asset_id=asset_id,
            title=vlm["title_zh"].strip() or rec.get("title") or asset_id,
            subject_isolation=SubjectIsolation(
                domain=dom,
                domain_label=f"画像扩展 · {DOMAIN_LABELS[dom]}",
                primary_subject=vlm["primary_subject"].strip() or "design study",
                is_personal_prior=False,
            ),
            style_spectrums=spectrums,
            granular_descriptors=GranularDescriptors(
                optics_camera=vlm["optics_camera"].strip() or "crisp architectural study framing",
                lighting_rig=vlm["lighting_rig"].strip() or "directional daylight",
                material_stack=vlm["material_stack"].strip() or "natural mineral and crafted materials",
                color_palette=hex_palette[:5],
            ),
            compiler_primitives=CompilerPrimitives(
                positive_tokens=[t.strip() for t in vlm.get("positive_tokens", [])[:5] if t.strip()] or ["tectonic", "refined"],
                negative_guardrails=[t.strip() for t in vlm.get("negative_guardrails", [])[:4] if t.strip()] or ["cluttered", "oversaturated"],
            ),
        )
        dumped = contract.model_dump()
        dumped.update(
            {
                "title_en": vlm.get("title_en", ""),
                "image_url": f"/assets/pinterest_500/{asset_id}.webp",
                "license": rec.get("license", "Open License"),
                "source_kind": rec.get("source", "open_research"),
                "source_origin": "profile_expansion",
                "source_url": rec.get("source_page", ""),
                "board_name": f"画像扩展 · {DOMAIN_LABELS[dom]}",
                "sub_category": sub_cat,
                "aesthetic_motifs": vlm.get("aesthetic_motifs", [])[:4],
                "aesthetic_quality_score": int(vlm.get("aesthetic_quality_score", 8)),
                "profile_distance": rec.get("profile_distance", 0.0),
                "akb_prior_asset_id": None,
                "akb_board_hint": None,
            }
        )
        packed_assets.append(dumped)

    # Preserve existing vlm_scoring_report for TechEvalOverview continuity
    prev_vlm_report = None
    if WEB_SHOWCASE_JSON.is_file():
        try:
            prev_vlm_report = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8")).get("vlm_scoring_report")
        except Exception:
            prev_vlm_report = None

    domain_counts = dict(Counter(a["subject_isolation"]["domain"] for a in packed_assets))
    subcat_counts = dict(Counter(a["sub_category"] for a in packed_assets).most_common())
    origin_counts = dict(Counter(a["source_origin"] for a in packed_assets))
    top_boards = [
        {"board": b, "count": cnt}
        for b, cnt in Counter(
            a["board_name"] for a in packed_assets if a["source_origin"] == "pinterest_personal"
        ).most_common(12)
    ]

    # Dynamically remap 40 golden_anchors reference_asset_id to best real assets in our 500 library
    remapped_anchors: dict[str, Any] = {}
    used_anchor_ids: set[str] = set()
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        rubric_dict = rubric.model_dump()
        for pt in rubric_dict["anchors"]:
            lvl = float(pt["level"])
            best_asset = min(
                packed_assets,
                key=lambda a: (
                    abs(float(a["style_spectrums"][axis_id]["score"]) - lvl)
                    + (0.25 if float(a["style_spectrums"][axis_id]["salience"]) < 0.5 else 0.0)
                    + (0.12 if a["asset_id"] in used_anchor_ids else 0.0)
                    - float(a.get("aesthetic_quality_score", 7)) * 0.02
                ),
            )
            pt["reference_asset_id"] = best_asset["asset_id"]
            used_anchor_ids.add(best_asset["asset_id"])
        remapped_anchors[axis_id] = rubric_dict

    showcase_bundle: dict[str, Any] = {
        "version": "2.0.0-pinterest-500",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_assets": len(packed_assets),
        "domain_counts": domain_counts,
        "origin_counts": origin_counts,
        "sub_category_counts": subcat_counts,
        "axes": [ax.model_dump() for ax in SPECTRUM_AXES],
        "golden_anchors": remapped_anchors,
        "cost_ledger": estimate_ingestion_cost_cny(1000).model_dump(),
        "vlm_scoring_report": prev_vlm_report,
        "aesthetic_profile": {
            "total_pinterest_analyzed": profile["total_pinterest_analyzed"],
            "kept_pinterest_count": origin_counts.get("pinterest_personal", 0),
            "expansion_count": origin_counts.get("profile_expansion", 0),
            "axis_signature": profile["axis_signature"],
            "dominant_color_clusters": profile["dominant_color_clusters"][:10],
            "top_motifs": profile["top_motifs"][:12],
            "top_boards": top_boards,
            "vlm_cost_audit": profile["vlm_cost_audit"],
        },
        "assets": packed_assets,
    }

    WEB_SHOWCASE_JSON.write_text(
        json.dumps(showcase_bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ASSETS_500_JSON.write_text(
        json.dumps(showcase_bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _build_contact_sheet(packed_assets, CONTACT_SHEET_500)

    total_mb = sum(p.stat().st_size for p in WEB_PINTEREST_500_DIR.glob("*.webp")) / (1024 * 1024)
    print(
        f"[DONE] Packed {len(packed_assets)} assets -> {WEB_SHOWCASE_JSON} | "
        f"WebP folder={total_mb:.2f} MB | Origins={origin_counts} | Domains={domain_counts}"
    )
    print("Canonical Sub-Categories:", subcat_counts)


if __name__ == "__main__":
    main()
