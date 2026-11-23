"""Generate 6 Cross-Domain Orthogonal AST vs Naive Multi-Image Comparison Pairs (`MIC-157`).

Demonstrates how `compile_conflict_free_ast` isolates Optics, Material & Tectonics, and
Atmosphere & Lighting slots to eliminate subject leakage and semantic bleed compared
to directly blending three raw reference images via `images.edit`.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI, RateLimitError
from PIL import Image, ImageDraw, ImageFont

from .aethervault_schema import AestheticAsset, compile_conflict_free_ast
from .curate_80 import _center_crop_4_3

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_ASSETS_JSON = REPO_ROOT / "data" / "curated_80" / "aethervault_assets_v1.json"
CURATED_IMAGES_DIR = REPO_ROOT / "data" / "curated_80" / "images"

COMPARE_DIR = REPO_ROOT / "data" / "ast_comparisons"
COMPARE_IMAGES_DIR = COMPARE_DIR / "images"
COMPARE_JSON_PATH = COMPARE_DIR / "ast_comparisons_v1.json"
COMPARE_SHEET_PATH = COMPARE_DIR / "comparison_sheet_6x2.jpg"

WEB_COMPARE_IMAGES_DIR = REPO_ROOT / "web" / "public" / "assets" / "ast_comparisons"
WEB_COMPARE_JSON_PATH = REPO_ROOT / "web" / "public" / "data" / "ast_comparisons_v1.json"


@dataclass(frozen=True)
class ComparisonScenario:
    pair_id: str
    title_zh: str
    subtitle_zh: str
    subject_core: str
    optics_id: str
    material_id: str
    lighting_id: str
    target_spectrums: dict[str, float]
    naive_failure_summary: str
    ast_decoupling_summary: str


COMPARISON_SCENARIOS: tuple[ComparisonScenario, ...] = (
    ComparisonScenario(
        pair_id="cmp_01",
        title_zh="荒野孤寂咖啡亭 × CNC 机械节点 × 极地阴天漫射",
        subtitle_zh="Architecture + Industrial + Editorial",
        subject_core="Compact 25sqm outdoor modular pop-up coffee kiosk set in open coastal volcanic basalt terrain",
        optics_id="arch_01",
        material_id="ind_02",
        lighting_id="edit_01",
        target_spectrums={
            "tectonic_honesty": 0.85,
            "surface_entropy": -0.25,
            "spatial_density": -0.75,
            "geometric_order": 0.85,
            "lighting_drama": -0.65,
            "chromatic_tension": -0.75,
            "thermal_mood": -0.60,
            "reality_abstraction": -0.75,
        },
        naive_failure_summary="多图直喂导致合成器旋钮/按键物体实体泄漏进建筑屋面与墙体，且耐候钢锈色与极地冷灰发生泥泞串色。",
        ast_decoupling_summary="严守作用域隔离：仅保留 arch_01 广角构筑骨架，将 ind_02 转化为局部精密 CNC 铝板与外露紧固节点，并锁死 edit_01 阴天漫射冷调。",
    ),
    ComparisonScenario(
        pair_id="cmp_02",
        title_zh="东方静谧茶器展亭 × 柴烧灰釉肌理 × 暖金暮色氛围",
        subtitle_zh="Architecture + Craft + Architecture",
        subject_core="Interior of a quiet 90sqm Kyoto tea and ceramic exhibition pavilion with recessed timber post-and-beam alcove",
        optics_id="arch_04",
        material_id="craft_01",
        lighting_id="arch_12",
        target_spectrums={
            "tectonic_honesty": 0.15,
            "surface_entropy": 0.65,
            "spatial_density": -0.60,
            "geometric_order": 0.50,
            "lighting_drama": 0.25,
            "chromatic_tension": -0.20,
            "thermal_mood": 0.85,
            "reality_abstraction": -0.75,
        },
        naive_failure_summary="直喂混合把巨大茶碗轮廓直接叠拼成建筑体块，同时障子格栅冷白光与暗室暖灯互搏导致空间透视塌陷。",
        ast_decoupling_summary="保留 arch_04 坐姿水平透视与木构架，将 craft_01 的粗陶窑变颗粒精准限定于台面与墙裙饰面，继承 arch_12 2700K 暮色氛围。",
    ),
    ComparisonScenario(
        pair_id="cmp_03",
        title_zh="高技派品牌快闪馆 × 光学镀膜金属 × 5800K 实验室冷光",
        subtitle_zh="Architecture + Industrial + Industrial",
        subject_core="High-tech modular brand pavilion featuring tension steel struts and glazed showcase canopy",
        optics_id="arch_14",
        material_id="ind_01",
        lighting_id="ind_07",
        target_spectrums={
            "tectonic_honesty": 0.90,
            "surface_entropy": -0.85,
            "spatial_density": -0.20,
            "geometric_order": 0.90,
            "lighting_drama": 0.15,
            "chromatic_tension": -0.65,
            "thermal_mood": -0.85,
            "reality_abstraction": -0.80,
        },
        naive_failure_summary="多图直接拼接使巨大相机镜头筒与光学实验台直接穿透建筑屋顶，破坏室外快闪展馆的真实尺度比例。",
        ast_decoupling_summary="仅从 ind_01 继承镜面钛金属与减反镀膜光泽到构件接头处，保持 arch_14 仰视张拉索网透视与 ind_07 5800K 洁净冷光。",
    ),
    ComparisonScenario(
        pair_id="cmp_04",
        title_zh="暗调黑曜石买手店门头 × 信号橙阳极细节 × 雨夜街拍反光",
        subtitle_zh="Architecture + Industrial + Editorial",
        subject_core="Contemporary street-level concept retail facade with matte dark metal rainscreen and recessed glass portal",
        optics_id="arch_15",
        material_id="ind_05",
        lighting_id="edit_11",
        target_spectrums={
            "tectonic_honesty": 0.65,
            "surface_entropy": -0.45,
            "spatial_density": -0.35,
            "geometric_order": 0.90,
            "lighting_drama": 0.55,
            "chromatic_tension": 0.40,
            "thermal_mood": -0.45,
            "reality_abstraction": -0.80,
        },
        naive_failure_summary="直接融合会把巨型橙色旋钮悬浮镶嵌在马路或门头上，且人物倒影与立面几何产生错乱重叠。",
        ast_decoupling_summary="按 35mm 街景透视组装暗调金属挂板立面，将信号橙严格限定在门把手与极窄指示件，并在人行道引入 edit_11 雨夜微湿反光。",
    ),
    ComparisonScenario(
        pair_id="cmp_05",
        title_zh="极简狭缝混凝土展厅 × 南部铁器铸铁肌理 × 戏剧性光刀切割",
        subtitle_zh="Architecture + Craft + Editorial",
        subject_core="Minimalist architectural concrete exhibition gallery interior with austere monolith plinth",
        optics_id="arch_07",
        material_id="craft_07",
        lighting_id="edit_07",
        target_spectrums={
            "tectonic_honesty": 0.15,
            "surface_entropy": 0.50,
            "spatial_density": -0.65,
            "geometric_order": 0.70,
            "lighting_drama": 0.95,
            "chromatic_tension": -0.75,
            "thermal_mood": -0.25,
            "reality_abstraction": -0.75,
        },
        naive_failure_summary="直接融合把铁壶壶嘴/提梁、森林树干与混凝土狭缝硬塞在同一画面，破坏美术馆室内的空间纯度。",
        ast_decoupling_summary="守住 arch_07 24mm 轴线深邃空间，将 craft_07 铸铁霰粒肌理限定于展台与门框饰面，引入 edit_07 强斜向光束氛围。",
    ),
    ComparisonScenario(
        pair_id="cmp_06",
        title_zh="构成主义艺术书店立面 × 包豪斯原色色块 × 高阳几何硬影",
        subtitle_zh="Architecture + Graphic + Editorial",
        subject_core="Modernist art bookstore facade with recessed entry steps and sculptural plastered wall planes",
        optics_id="arch_05",
        material_id="graph_02",
        lighting_id="edit_10",
        target_spectrums={
            "tectonic_honesty": -0.10,
            "surface_entropy": -0.25,
            "spatial_density": -0.40,
            "geometric_order": 0.75,
            "lighting_drama": 0.50,
            "chromatic_tension": 0.85,
            "thermal_mood": 0.15,
            "reality_abstraction": -0.45,
        },
        naive_failure_summary="2D 海报平面与 3D 建筑照片直接混合后产生贴图错位、透视坍缩，人物模特突兀穿插在台阶上。",
        ast_decoupling_summary="将 graph_02 纯正包豪斯红蓝黄几何色块转译为立面粉刷涂装分区，同时锁定 arch_05 实体尺度透视与 edit_10 明快高阳阴影。",
    ),
)


def _to_png_upload_tuple(asset_id: str) -> tuple[str, bytes, str]:
    path = CURATED_IMAGES_DIR / f"{asset_id}.webp"
    with Image.open(path) as im:
        thumb = im.convert("RGB").resize((512, 384), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        thumb.save(buf, format="PNG")
    return (f"{asset_id}.png", buf.getvalue(), "image/png")


def _generate_with_retry(fn, *args, **kwargs):
    for attempt in range(6):
        try:
            return fn(*args, **kwargs)
        except RateLimitError:
            if attempt == 5:
                raise
            time.sleep(6 + attempt * 3)
    raise RuntimeError("Exceeded retry limit")


def _run_naive_blend(client: OpenAI, sc: ComparisonScenario) -> Image.Image:
    uploads = [
        _to_png_upload_tuple(sc.optics_id),
        _to_png_upload_tuple(sc.material_id),
        _to_png_upload_tuple(sc.lighting_id),
    ]
    prompt = (
        f"Directly blend all three reference images together into {sc.subject_core}, "
        "combining their objects, materials, colors, and lighting simultaneously into a single composite photograph."
    )
    resp = _generate_with_retry(
        client.images.edit,
        model="gpt-image-1-mini",
        image=uploads,
        prompt=prompt,
        size="1024x1024",
        quality="low",
    )
    raw = base64.b64decode(resp.data[0].b64_json or "")
    with Image.open(io.BytesIO(raw)) as im:
        return _center_crop_4_3(im.convert("RGB"))


def _run_ast_compiled(
    client: OpenAI,
    sc: ComparisonScenario,
    compiled_prompt: str,
    negative_guardrails: list[str],
    leaked_nouns: list[str],
    material_palette: list[str],
    material_tokens: list[str],
    lighting_palette: list[str],
) -> Image.Image:
    avoid_list = list(dict.fromkeys([*negative_guardrails, *leaked_nouns, "text labels", "watermarks", "floating objects"]))
    prompt = (
        "Photorealistic architectural documentary photograph strictly executing the scoped layer directives below. "
        "Do NOT copy literal standalone objects (synthesizers, bowls, lenses, portraits) from material/lighting cues — "
        "apply only the specified localized finishes, color accents, and illumination.\n\n"
        f"{compiled_prompt}\n\n"
        f"[SCOPED_COLOR_AND_FINISH_TOKENS]\n"
        f"Architectural finish & accent palette from {sc.material_id}: {', '.join(material_palette[:4])}; "
        f"material cues: {', '.join(material_tokens[:4])}.\n"
        f"Ambient lighting tonal palette from {sc.lighting_id}: {', '.join(lighting_palette[:4])}.\n\n"
        f"[STRICT_AVOIDANCE_GUARDRAILS]\nAvoid: {', '.join(avoid_list)}."
    )
    resp = _generate_with_retry(
        client.images.generate,
        model="gpt-image-1-mini",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
    )
    raw = base64.b64decode(resp.data[0].b64_json or "")
    with Image.open(io.BytesIO(raw)) as im:
        return _center_crop_4_3(im.convert("RGB"))


def _build_comparison_sheet(pairs: list[dict[str, object]]) -> None:
    cols, rows = 2, len(pairs)
    cell_w, cell_h = 440, 355
    thumb_w, thumb_h = 416, 312
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (14, 16, 18))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for row_idx, pair in enumerate(pairs):
        pid = str(pair["pair_id"])
        for col_idx, suffix, tag_color in [
            (0, "naive", (239, 68, 68)),
            (1, "ast", (16, 185, 129)),
        ]:
            img_path = COMPARE_IMAGES_DIR / f"{pid}_{suffix}.webp"
            thumb = Image.open(img_path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x0 = col_idx * cell_w + 12
            y0 = row_idx * cell_h + 8
            sheet.paste(thumb, (x0, y0))
            label = f"{pid} [{'NAIVE MULTI-REF BLEND' if suffix == 'naive' else 'AETHERVAULT AST COMPILED'}]"
            draw.text((x0 + 2, y0 + thumb_h + 6), label, fill=tag_color, font=font)

    sheet.save(COMPARE_SHEET_PATH, format="JPEG", quality=90)


def generate_comparisons(force: bool = False) -> dict[str, object]:
    """Generate all 6 Naive vs AST comparison pairs and sync Showcase assets."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to run ast_compare_gen.")
    if not CURATED_ASSETS_JSON.exists():
        raise FileNotFoundError(f"Missing curated assets JSON: {CURATED_ASSETS_JSON}")

    COMPARE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_COMPARE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_COMPARE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(CURATED_ASSETS_JSON.read_text(encoding="utf-8"))
    assets_by_id: dict[str, AestheticAsset] = {}
    for raw in payload["assets"]:
        parsed = AestheticAsset.model_validate(
            {
                "asset_id": raw["asset_id"],
                "title": raw["title"],
                "subject_isolation": raw["subject_isolation"],
                "style_spectrums": raw["style_spectrums"],
                "granular_descriptors": raw["granular_descriptors"],
                "compiler_primitives": raw["compiler_primitives"],
            }
        )
        assets_by_id[parsed.asset_id] = parsed

    client = OpenAI()
    compiled_cache: dict[str, dict[str, object]] = {}
    tasks: list[tuple[str, str, ComparisonScenario]] = []

    for sc in COMPARISON_SCENARIOS:
        opt_a = assets_by_id[sc.optics_id]
        mat_a = assets_by_id[sc.material_id]
        lit_a = assets_by_id[sc.lighting_id]
        ast_out = compile_conflict_free_ast(
            subject_core=sc.subject_core,
            optics_asset=opt_a,
            material_asset=mat_a,
            lighting_asset=lit_a,
            target_spectrums=sc.target_spectrums,
        )
        compiled_cache[sc.pair_id] = ast_out

        naive_path = COMPARE_IMAGES_DIR / f"{sc.pair_id}_naive.webp"
        ast_path = COMPARE_IMAGES_DIR / f"{sc.pair_id}_ast.webp"
        if force or not naive_path.exists():
            tasks.append((sc.pair_id, "naive", sc))
        if force or not ast_path.exists():
            tasks.append((sc.pair_id, "ast", sc))

    if tasks:
        print(f"Generating {len(tasks)} comparison renders (max_workers=3)...")

        def _exec_task(item: tuple[str, str, ComparisonScenario]) -> str:
            pid, kind, sc_item = item
            out_path = COMPARE_IMAGES_DIR / f"{pid}_{kind}.webp"
            if kind == "naive":
                im = _run_naive_blend(client, sc_item)
            else:
                ast_info = compiled_cache[pid]
                mat_asset = assets_by_id[sc_item.material_id]
                lit_asset = assets_by_id[sc_item.lighting_id]
                im = _run_ast_compiled(
                    client,
                    sc_item,
                    str(ast_info["compiled_prompt"]),
                    list(ast_info["negative_guardrails"]),  # type: ignore[arg-type]
                    [mat_asset.subject_isolation.primary_subject, lit_asset.subject_isolation.primary_subject],
                    mat_asset.granular_descriptors.color_palette,
                    mat_asset.compiler_primitives.positive_tokens,
                    lit_asset.granular_descriptors.color_palette,
                )
            im.save(out_path, format="WEBP", quality=90)
            return f"{pid}_{kind}"

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(_exec_task, t) for t in tasks]
            for fut in as_completed(futs):
                tag = fut.result()
                print(f"[COMPARE-READY] {tag}")

    pair_records: list[dict[str, object]] = []
    for sc in COMPARISON_SCENARIOS:
        naive_src = COMPARE_IMAGES_DIR / f"{sc.pair_id}_naive.webp"
        ast_src = COMPARE_IMAGES_DIR / f"{sc.pair_id}_ast.webp"
        shutil.copy2(naive_src, WEB_COMPARE_IMAGES_DIR / f"{sc.pair_id}_naive.webp")
        shutil.copy2(ast_src, WEB_COMPARE_IMAGES_DIR / f"{sc.pair_id}_ast.webp")

        ast_info = compiled_cache[sc.pair_id]
        pair_records.append(
            {
                "pair_id": sc.pair_id,
                "title_zh": sc.title_zh,
                "subtitle_zh": sc.subtitle_zh,
                "subject_core": sc.subject_core,
                "slots": {
                    "optics": sc.optics_id,
                    "material": sc.material_id,
                    "lighting": sc.lighting_id,
                },
                "naive_image_url": f"/assets/ast_comparisons/{sc.pair_id}_naive.webp",
                "ast_image_url": f"/assets/ast_comparisons/{sc.pair_id}_ast.webp",
                "compiled_prompt": ast_info["compiled_prompt"],
                "negative_guardrails": ast_info["negative_guardrails"],
                "conflicts_isolated_count": ast_info["conflicts_isolated_count"],
                "naive_failure_summary": sc.naive_failure_summary,
                "ast_decoupling_summary": sc.ast_decoupling_summary,
            }
        )

    bundle = {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pairs": len(pair_records),
        "pairs": pair_records,
    }
    COMPARE_JSON_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    WEB_COMPARE_JSON_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    _build_comparison_sheet(pair_records)
    return {"total_pairs": len(pair_records), "sheet_path": str(COMPARE_SHEET_PATH)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 6 AST vs Naive multi-image comparisons (`MIC-157`).")
    parser.add_argument("--force", action="store_true", help="Regenerate all 12 comparison renders.")
    args = parser.parse_args()
    summary = generate_comparisons(force=args.force)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
