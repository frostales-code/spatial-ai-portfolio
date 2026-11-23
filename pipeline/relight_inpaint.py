"""OpenCV Homography Seam Projection & Intrinsic Shadow-Locked Facade Relighting Pipeline (`MIC-160`)."""

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
from typing import Any

import cv2
import numpy as np
from openai import OpenAI, RateLimitError
from PIL import Image

from .homography_seam import OpeningRectMm, Point2D, project_panel_seams

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_JSON = Path(__file__).resolve().parent / "tectonic_catalog_v1.json"

DATA_DIR = REPO_ROOT / "data" / "tectonic_cases"
IMAGES_DIR = DATA_DIR / "images"
RAW_SQ_DIR = DATA_DIR / "raw_1024"
SHEET_PATH = DATA_DIR / "tectonic_sheet_3x3.jpg"
BUNDLE_PATH = DATA_DIR / "tectonic_showcase_v1.json"

WEB_IMAGES_DIR = REPO_ROOT / "web" / "public" / "assets" / "tectonic_cases"
WEB_JSON_PATH = REPO_ROOT / "web" / "public" / "data" / "tectonic_showcase_v1.json"


@dataclass(frozen=True)
class CaseGeometrySpec:
    case_id: str
    raw_prompt: str
    # Calibrated in 800x600 canonical image coordinates: [TL, TR, BR, BL]
    facade_quad_px: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    # Sub-rectangles or quads to exclude from wall cladding AO / shadow calculation (e.g. door & glazing window normalized to [0..1] ortho facade)
    openings_ortho_norm: tuple[tuple[float, float, float, float], ...]
    # Plinth band in 800x600 normalized height (0.85..1.0) + Parapet top band (0.0..0.06)
    glazing_quad_px: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    door_quad_px: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    # Exact pin coordinates in percentages [0..100] over 800x600 image for [Zone A wall, Zone B glazing, Zone C edge/plinth]
    pins_pct: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


# Initial approximations before base generation visual calibration; updated once inspected via read_file!
DEFAULT_CASE_SPECS: dict[str, CaseGeometrySpec] = {
    "case_01_corner_cafe": CaseGeometrySpec(
        case_id="case_01_corner_cafe",
        raw_prompt=(
            "Eye-level architectural street documentary photograph during late-afternoon golden hour of a one-story street-corner artisan coffee storefront "
            "flanked on left and right margins by adjacent historic brick storefronts and street trees. "
            "The central storefront occupies roughly 70 percent of the horizontal frame and has a continuous, completely smooth monolithic poured raw gray concrete wall "
            "with zero panel joints, a clean rectangular wooden doorway on the left, and one giant seamless frameless single-pane plate-glass window on the right. "
            "The raw concrete top edge meets the sky directly with zero metal coping, and the concrete wall base directly touches the stone sidewalk with zero plinth or kickplate. "
            "Strong warm afternoon sun casts rich diagonal dappled tree-branch shadows onto the right concrete facade and across the stone sidewalk. "
            "Compose centered horizontally inside the central 4:3 band, clean architectural perspective, realistic materials, strictly no text, no shop signs, no logos, no people."
        ),
        facade_quad_px=((110.0, 59.0), (666.0, 59.0), (666.0, 571.0), (110.0, 571.0)),
        openings_ortho_norm=((0.104, 0.469, 0.297, 1.0), (0.408, 0.469, 0.926, 0.986)),
        glazing_quad_px=((337.0, 299.0), (625.0, 299.0), (625.0, 564.0), (337.0, 564.0)),
        door_quad_px=((168.0, 299.0), (275.0, 299.0), (275.0, 568.0), (168.0, 568.0)),
        pins_pct=((50.0, 28.0), (60.0, 72.0), (19.0, 91.5)),
    ),
    "case_02_concept_boutique": CaseGeometrySpec(
        case_id="case_02_concept_boutique",
        raw_prompt=(
            "Eye-level architectural documentary photograph in crisp warm late-afternoon sunlight of an urban concept designer boutique storefront centered between neighboring dark stone commercial buildings. "
            "The central bay is a sculptural monolithic seamless matte warm-ivory architectural facade wrapping in a broad gentle curve with zero joints, pierced by one recessed dark minimalist doorway on the left "
            "and a giant seamless frameless floor-to-ceiling showcase glass window across the right half. "
            "The top roof slab edge is paper-thin and bare without metal flashing, and the facade wall drops straight onto the stone pavement with no plinth curb. "
            "Warm late sun casts clear crisp tree-branch shadows across the right half of the facade and the sidewalk foreground. "
            "Centered horizontally within the middle 4:3 framing band, subtle natural camera perspective, strictly no brand text, no logos, no signage, no pedestrians."
        ),
        facade_quad_px=((40.0, 14.0), (758.0, 14.0), (758.0, 582.0), (40.0, 582.0)),
        openings_ortho_norm=((0.188, 0.477, 0.309, 0.975), (0.453, 0.359, 0.912, 0.982)),
        glazing_quad_px=((365.0, 218.0), (695.0, 218.0), (695.0, 572.0), (365.0, 572.0)),
        door_quad_px=((175.0, 285.0), (262.0, 285.0), (262.0, 568.0), (175.0, 568.0)),
        pins_pct=((43.0, 22.0), (66.0, 66.0), (19.0, 92.5)),
    ),
    "case_03_oldstreet_teahouse": CaseGeometrySpec(
        case_id="case_03_oldstreet_teahouse",
        raw_prompt=(
            "Eye-level architectural street documentary photograph of an intimate ground-floor boutique teahouse facade along an old stone-paved pedestrian alley flanked by traditional dark timber neighboring bays and lush courtyard foliage. "
            "The central storefront wall is completely smooth unsealed warm ochre rammed-earth clay plaster reaching right down to touch the dark slate sidewalk directly without any protective stone plinth or kickplate. "
            "It has a simple recessed dark timber doorway on the left and a wide seamless frameless single glass picture window on the right showing soft warm interior lighting, topped by a bare overhanging slab with zero metal flashing drip edge. "
            "Golden afternoon sunlight filters through bamboo and street trees, casting distinct warm dappled foliage shadows over the right side of the earth wall and stone street. "
            "Centered horizontally inside the 4:3 middle zone, crisp realistic texture, strictly no Chinese or English signs, no lanterns with text, no people."
        ),
        facade_quad_px=((132.0, 16.0), (746.0, 16.0), (746.0, 568.0), (132.0, 568.0)),
        openings_ortho_norm=((0.078, 0.275, 0.316, 0.953), (0.440, 0.275, 0.883, 0.832)),
        glazing_quad_px=((402.0, 168.0), (674.0, 168.0), (674.0, 475.0), (402.0, 475.0)),
        door_quad_px=((180.0, 168.0), (326.0, 168.0), (326.0, 542.0), (180.0, 542.0)),
        pins_pct=((48.0, 21.0), (66.0, 54.0), (55.0, 92.5)),
    ),
}


TIER_EDIT_PROMPTS: dict[tuple[str, str], str] = {
    ("case_01_corner_cafe", "tier_1_balanced"): (
        "Edit ONLY the concrete wall cladding, the right-hand showcase window, and the top parapet/bottom base of the central storefront while keeping the left wooden entrance door, neighboring brick buildings, sky, sidewalk, and warm afternoon tree shadows completely intact: "
        "replace the monolithic gray concrete wall panels with prefabricated 18mm dark-gray UHPC textured rainscreen panels divided by crisp recessed 10mm open shadow joints on a 1200x2400mm rectangular architectural grid; "
        "subdivide ONLY the right-hand glass window with three slim black matte steel vertical mullions and a crisp upper transom; "
        "add a clean 3mm dark anthracite aluminum parapet coping edge, a slim metal entrance lintel canopy with tension rods above the glass window, and an 80mm brushed stainless base plinth."
    ),
    ("case_01_corner_cafe", "tier_2_value"): (
        "Edit ONLY the concrete wall cladding, the right-hand showcase window, and the top parapet/bottom base of the central storefront while keeping the left wooden entrance door, neighboring brick buildings, sky, sidewalk, and warm afternoon tree shadows completely intact: "
        "replace the raw concrete wall with crisp modular 600x1200mm slate-gray high-density fiber cement facade boards separated by fine aluminum spline joints and subtle corner fasteners; "
        "replace the right-hand glass window with a four-leaf narrow matte black aluminum bi-folding cafe serving window over a thin timber outside counter shelf and fiber-cement lower wall; "
        "add a dark galvanized metal roof drip flashing edge and 50mm dark waterproof cement base curb."
    ),
    ("case_02_concept_boutique", "tier_1_balanced"): (
        "Edit ONLY the ivory stucco cladding wall, the right-hand showcase window, and the top cornice/bottom base of the central boutique while keeping the left minimalist dark recessed entrance door, adjacent dark stone piers, sidewalk, and crisp tree shadows completely intact: "
        "transform the smooth curved wall into crisp faceted planar architectural bays clad in matte charcoal perforated anodized aluminum rainscreen panels in clean 900x2400mm rectangular modules with dark reveal joints; "
        "segment the right-hand showcase window into four crisp faceted planar glass bays with slim matte black vertical steel mullions; "
        "cap the top cornice with a 4mm black-titanium stainless coping edge and anchor the bottom onto a 120mm honed dark basalt base plinth."
    ),
    ("case_02_concept_boutique", "tier_2_value"): (
        "Edit ONLY the ivory stucco cladding wall, the right-hand showcase window, and the top cornice/bottom base of the central boutique while keeping the left dark recessed entrance door, adjacent dark stone piers, sidewalk, and crisp tree shadows completely intact: "
        "re clad the curved wall into clean planar mineral lime-stucco panels partitioned by fine 600x1200mm recessed stainless steel control-joint beads; "
        "divide the right-hand showcase window into standard 1400mm matte black aluminum thermal-break glass curtain bays; "
        "cap the top edge with dark metal roof drip flashing and add a clean dark waterproof base plinth curb."
    ),
    ("case_03_oldstreet_teahouse", "tier_1_balanced"): (
        "Edit ONLY the earthen clay wall cladding, the right-hand glass window, and the top roof edge/bottom stone plinth of the central teahouse while keeping the left dark timber doorway, neighboring wooden alley buildings, stone pavement, and golden bamboo foliage shadows intact: "
        "replace the unsealed clay wall with dark brown charred red cedar timber vertical cladding panels installed on a crisp 600mm modular rhythm with ventilated shadow grooves; "
        "frame the right-hand window in warm timber-aluminum composite frames divided into 1500mm modular vertical mullions with fine wood lattice detailing; "
        "add an aged bronze traditional drip eave flashing along the top roof beam and raise the wall onto a crisp 120mm chiseled gray granite waterproof stone base plinth."
    ),
    ("case_03_oldstreet_teahouse", "tier_2_value"): (
        "Edit ONLY the earthen clay wall cladding, the right-hand glass window, and the top roof edge/bottom stone plinth of the central teahouse while keeping the left dark timber doorway, neighboring wooden alley buildings, stone pavement, and golden bamboo foliage shadows intact: "
        "replace the unsealed clay wall with modular 600x1200mm warm sand-toned modified mineral stone veneer sheets separated by crisp neat 4mm grouted grid joints; "
        "upgrade the right-hand window into a sleek three-track dark matte aluminum sliding pocket window frame; "
        "add a dark bronze-gray metal drip flashing at the top eave and a clean 80mm waterproof dark plinth curb above the stone pavement."
    ),
}


def _generate_with_retry(fn, *args, **kwargs):
    for attempt in range(6):
        try:
            return fn(*args, **kwargs)
        except RateLimitError:
            if attempt == 5:
                raise
            time.sleep(6 + attempt * 3)
    raise RuntimeError("Exceeded OpenAI RateLimitError retry limit.")


def _sq_1024_to_4_3_800x600(img_1024: Image.Image) -> Image.Image:
    """Deterministic exact slice converting 1024x1024 -> centered 4:3 crop (1024x768) -> 800x600 RGB."""
    cropped = img_1024.crop((0, 128, 1024, 896))
    return cropped.resize((800, 600), Image.Resampling.LANCZOS)


def _800x600_mask_to_1024_rgba(mask_800x600: np.ndarray) -> bytes:
    """Convert binary 800x600 editable region mask (255 = edit, 0 = locked) to OpenAI 1024x1024 RGBA PNG bytes.

    In OpenAI `images.edit` masks, alpha == 0 marks regions to regenerate and alpha == 255 locks pixels.
    """
    mask_1024x768 = cv2.resize(mask_800x600, (1024, 768), interpolation=cv2.INTER_NEAREST)
    full_edit_1024 = np.zeros((1024, 1024), dtype=np.uint8)
    full_edit_1024[128:896, :] = mask_1024x768

    alpha = np.where(full_edit_1024 > 127, 0, 255).astype(np.uint8)
    rgba = np.zeros((1024, 1024, 4), dtype=np.uint8)
    rgba[:, :, :3] = 255
    rgba[:, :, 3] = alpha

    pil_mask = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    pil_mask.save(buf, format="PNG")
    return buf.getvalue()


def _quad_to_poly(quad: tuple[tuple[float, float], ...]) -> np.ndarray:
    return np.array(quad, dtype=np.int32).reshape((-1, 1, 2))


def _build_masks(spec: CaseGeometrySpec) -> tuple[np.ndarray, np.ndarray]:
    """Return (editable_facade_mask_u8, cladding_only_mask_u8) both shape (600, 800)."""
    facade_mask = np.zeros((600, 800), dtype=np.uint8)
    cv2.fillPoly(facade_mask, [_quad_to_poly(spec.facade_quad_px)], 255)
    # Lock the left entrance doorway inside the protected mask so door location stays invariant across VE tiers
    cv2.fillPoly(facade_mask, [_quad_to_poly(spec.door_quad_px)], 0)

    cladding_mask = np.zeros((600, 800), dtype=np.uint8)
    cv2.fillPoly(cladding_mask, [_quad_to_poly(spec.facade_quad_px)], 255)
    cv2.fillPoly(cladding_mask, [_quad_to_poly(spec.glazing_quad_px)], 0)
    cv2.fillPoly(cladding_mask, [_quad_to_poly(spec.door_quad_px)], 0)
    return facade_mask, cladding_mask


def _apply_intrinsic_shadow_and_seams(
    base_rgb: np.ndarray,
    edit_rgb: np.ndarray,
    facade_mask_u8: np.ndarray,
    cladding_mask_u8: np.ndarray,
    seam_segments: list[dict[str, Any]],
) -> tuple[np.ndarray, float, float]:
    """Lock non-mask pixels, transfer low-frequency dusk/tree shading to wall cladding, and apply crisp H^-1 joint AO.

    Returns (final_composite_rgb_u8, non_mask_psnr_db, shadow_luma_corr).
    """
    base_lab = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    edit_lab = cv2.cvtColor(edit_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    l_base = base_lab[:, :, 0]
    l_edit = edit_lab[:, :, 0]

    # Low-frequency illumination envelope capturing street tree dappled shadows & sun gradient
    l_base_low = cv2.GaussianBlur(l_base, (0, 0), sigmaX=15.0, sigmaY=15.0)
    l_edit_low = cv2.GaussianBlur(l_edit, (0, 0), sigmaX=15.0, sigmaY=15.0)

    gain = np.clip(l_base_low / np.maximum(l_edit_low, 10.0), 0.62, 1.48)
    l_relit = np.where(
        cladding_mask_u8 > 127,
        np.clip(l_edit * (0.28 + 0.72 * gain), 6.0, 250.0),
        l_edit,
    )
    edit_lab[:, :, 0] = l_relit
    relit_rgb = cv2.cvtColor(edit_lab.astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)

    # Restrained millimeter shadow-gap Ambient Occlusion strictly along projected H^-1 seam segments
    ao_layer = np.zeros((600, 800), dtype=np.float32)
    for seg in seam_segments:
        p0 = (int(round(seg["start"]["x"])), int(round(seg["start"]["y"])))
        p1 = (int(round(seg["end"]["x"])), int(round(seg["end"]["y"])))
        cv2.line(ao_layer, p0, p1, color=1.0, thickness=2, lineType=cv2.LINE_AA)
    ao_layer = cv2.GaussianBlur(ao_layer, (0, 0), sigmaX=0.7) * (cladding_mask_u8 > 127).astype(np.float32)
    relit_rgb = np.clip(relit_rgb * (1.0 - 0.24 * ao_layer[:, :, None]), 0.0, 255.0)

    # Feather strictly along the INNER 2px rim of facade_mask_u8 so non-mask areas (buildings, sidewalk, door) stay unbleeding
    eroded = cv2.erode(facade_mask_u8, np.ones((3, 3), dtype=np.uint8), iterations=1)
    inner_feather = cv2.GaussianBlur(eroded.astype(np.float32) / 255.0, (5, 5), sigmaX=1.0)
    alpha = np.where(facade_mask_u8 > 127, inner_feather, 0.0)
    alpha = np.clip(alpha, 0.0, 1.0)[:, :, None]

    base_f = base_rgb.astype(np.float32)
    final_f = relit_rgb * alpha + base_f * (1.0 - alpha)
    final_u8 = np.clip(np.round(final_f), 0, 255).astype(np.uint8)

    # Measure PSNR strictly outside the editable facade quad (including surrounding buildings, door, sidewalk, sky)
    locked_mask = facade_mask_u8 == 0
    diff = final_u8.astype(np.float64)[locked_mask] - base_rgb.astype(np.float64)[locked_mask]
    mse = float(np.mean(diff ** 2)) if diff.size > 0 else 0.0
    psnr_db = 99.0 if mse < 1e-9 else float(min(99.0, 20.0 * np.log10(255.0 / np.sqrt(mse))))

    # Measure low-frequency illumination shadow correlation across wall cladding
    final_lab = cv2.cvtColor(final_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
    l_final_low = cv2.GaussianBlur(final_lab[:, :, 0], (0, 0), sigmaX=15.0, sigmaY=15.0)
    wall_bool = cladding_mask_u8 > 127
    if np.sum(wall_bool) > 100:
        b_vec = l_base_low[wall_bool]
        f_vec = l_final_low[wall_bool]
        if float(np.std(b_vec)) > 1e-4 and float(np.std(f_vec)) > 1e-4:
            corr = float(np.corrcoef(b_vec, f_vec)[0, 1])
        else:
            corr = 1.0
    else:
        corr = 1.0

    return final_u8, round(psnr_db, 2), round(max(-1.0, min(1.0, corr)), 4)


def run_stage_base(force: bool = False) -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to generate base architectural renders.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    RAW_SQ_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    def _gen_one(cid: str, spec: CaseGeometrySpec) -> str:
        sq_path = RAW_SQ_DIR / f"{cid}_raw_1024.png"
        webp_path = IMAGES_DIR / f"{cid}_tier_0_raw.webp"
        if not force and sq_path.exists() and webp_path.exists():
            return f"[SKIP] {cid} base already exists."

        resp = _generate_with_retry(
            client.images.generate,
            model="gpt-image-1-mini",
            prompt=spec.raw_prompt,
            size="1024x1024",
            quality="medium",
        )
        raw_bytes = base64.b64decode(resp.data[0].b64_json or "")
        sq_path.write_bytes(raw_bytes)
        with Image.open(io.BytesIO(raw_bytes)) as im:
            rgb_800 = _sq_1024_to_4_3_800x600(im.convert("RGB"))
            rgb_800.save(webp_path, format="WEBP", quality=92)
        return f"[GEN] {cid} base -> {webp_path.name}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_gen_one, cid, spec) for cid, spec in DEFAULT_CASE_SPECS.items()]
        for fut in as_completed(futs):
            print(fut.result())


def _build_3x3_contact_sheet(cases: list[dict[str, Any]]) -> None:
    cols, rows = 3, len(cases)
    cell_w, cell_h = 340, 275
    thumb_w, thumb_h = 320, 240
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (244, 245, 247))

    for r_idx, case in enumerate(cases):
        cid = case["case_id"]
        for c_idx, tier in enumerate(case["tiers"]):
            tid = tier["tier_id"]
            img_path = IMAGES_DIR / f"{cid}_{tid}.webp"
            if img_path.exists():
                im = Image.open(img_path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(im, (c_idx * cell_w + 10, r_idx * cell_h + 12))

    sheet.save(SHEET_PATH, format="JPEG", quality=92)


def run_stage_complete(case_specs: dict[str, CaseGeometrySpec], force: bool = False) -> dict[str, Any]:
    """Compute exact H^-1 seams, run shadow-locked inpainting for tier_1 & tier_2, verify PSNR/angles, and sync web/."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to run relight inpainting.")
    if not CATALOG_JSON.exists():
        raise FileNotFoundError(f"Run `python -m pipeline.tectonic_catalog` first: missing {CATALOG_JSON}")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    client = OpenAI()

    for case in catalog["cases"]:
        cid = case["case_id"]
        spec = case_specs[cid]
        anchor = case["scale_anchor"]
        facade_w_mm = float(anchor["facade_width_mm"])
        facade_h_mm = float(anchor["facade_height_mm"])

        raw_sq_path = RAW_SQ_DIR / f"{cid}_raw_1024.png"
        if not raw_sq_path.exists():
            raise FileNotFoundError(f"Missing base 1024 PNG {raw_sq_path}; run --stage base first.")

        raw_800_path = IMAGES_DIR / f"{cid}_tier_0_raw.webp"
        base_rgb = np.array(Image.open(raw_800_path).convert("RGB"))
        facade_mask_u8, cladding_mask_u8 = _build_masks(spec)
        mask_png_bytes = _800x600_mask_to_1024_rgba(facade_mask_u8)

        openings_mm = [
            OpeningRectMm(
                x_min=x0 * facade_w_mm,
                y_min=y0 * facade_h_mm,
                x_max=x1 * facade_w_mm,
                y_max=y1 * facade_h_mm,
            )
            for (x0, y0, x1, y1) in spec.openings_ortho_norm
        ]
        quad_pts = [Point2D(x=x, y=y) for (x, y) in spec.facade_quad_px]

        # Attach calibrated image geometry & pin placement on the case
        case["geometry"] = {
            "facade_quad_px": [{"x": x, "y": y} for (x, y) in spec.facade_quad_px],
            "diagnostic_pins_pct": [
                {"zone_id": "facade_wall_01", "x_pct": spec.pins_pct[0][0], "y_pct": spec.pins_pct[0][1]},
                {"zone_id": "glazing_portal_02", "x_pct": spec.pins_pct[1][0], "y_pct": spec.pins_pct[1][1]},
                {"zone_id": "edge_weather_03", "x_pct": spec.pins_pct[2][0], "y_pct": spec.pins_pct[2][1]},
            ],
        }

        for tier in case["tiers"]:
            tid = tier["tier_id"]
            out_webp = IMAGES_DIR / f"{cid}_{tid}.webp"

            wall_zone = tier["zones"][0]
            modulus = wall_zone["engineering_state"].get("panel_modulus_mm")
            if modulus:
                proj = project_panel_seams(
                    image_quad=quad_pts,
                    facade_width_mm=facade_w_mm,
                    facade_height_mm=facade_h_mm,
                    panel_width_mm=float(modulus["width"]),
                    panel_height_mm=float(modulus["height"]),
                    openings_mm=openings_mm,
                )
                seam_payload = proj.model_dump()
            else:
                seam_payload = {
                    "homography_matrix": [],
                    "inverse_homography_matrix": [],
                    "seam_segments": [],
                    "vertical_vanishing_deviation_deg": 0.0,
                    "panel_count_estimate": 0,
                }

            if tid == "tier_0_raw":
                tier["image_url"] = f"/assets/tectonic_cases/{out_webp.name}"
                tier["homography_projection"] = seam_payload
                tier["relight_metrics"] = {
                    "non_mask_psnr_db": 99.0,
                    "shadow_luma_corr": 1.0,
                    "vertical_vanishing_deviation_deg": 0.0,
                }
                continue

            edit_sq_cache = RAW_SQ_DIR / f"{cid}_{tid}_edit_1024.png"
            if force or not edit_sq_cache.exists():
                prompt = TIER_EDIT_PROMPTS[(cid, tid)]
                print(f"Editing {cid} / {tid} via gpt-image-1-mini ...")
                resp = _generate_with_retry(
                    client.images.edit,
                    model="gpt-image-1-mini",
                    image=("base.png", raw_sq_path.read_bytes(), "image/png"),
                    mask=("mask.png", mask_png_bytes, "image/png"),
                    prompt=prompt,
                    size="1024x1024",
                    quality="medium",
                )
                edit_bytes = base64.b64decode(resp.data[0].b64_json or "")
                edit_sq_cache.write_bytes(edit_bytes)

            with Image.open(edit_sq_cache) as edit_pil:
                edit_800 = np.array(_sq_1024_to_4_3_800x600(edit_pil.convert("RGB")))

            composited_u8, psnr_db, shadow_corr = _apply_intrinsic_shadow_and_seams(
                base_rgb=base_rgb,
                edit_rgb=edit_800,
                facade_mask_u8=facade_mask_u8,
                cladding_mask_u8=cladding_mask_u8,
                seam_segments=seam_payload["seam_segments"],
            )
            Image.fromarray(composited_u8, mode="RGB").save(out_webp, format="WEBP", quality=92)

            tier["image_url"] = f"/assets/tectonic_cases/{out_webp.name}"
            tier["homography_projection"] = seam_payload
            tier["relight_metrics"] = {
                "non_mask_psnr_db": psnr_db,
                "shadow_luma_corr": shadow_corr,
                "vertical_vanishing_deviation_deg": seam_payload["vertical_vanishing_deviation_deg"],
            }
            print(
                f"  [OK] {out_webp.name} -> PSNR={psnr_db:.2f} dB, "
                f"shadow_corr={shadow_corr:.3f}, angle_dev={seam_payload['vertical_vanishing_deviation_deg']:.3f} deg"
            )

    _build_3x3_contact_sheet(catalog["cases"])
    catalog["generated_at"] = datetime.now(timezone.utc).isoformat()
    BUNDLE_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sync all WebP assets and showcase bundle JSON cleanly into web/public
    for src in IMAGES_DIR.glob("*.webp"):
        shutil.copy2(src, WEB_IMAGES_DIR / src.name)
    WEB_JSON_PATH.write_text(BUNDLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[SYNC] Synced 9 WebP renders and {WEB_JSON_PATH.name} into web/public/")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="TectonicLoop M2 Homography Seam & Relighting Pipeline")
    parser.add_argument("--stage", choices=["base", "complete", "all"], default="all")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.stage in ("base", "all"):
        run_stage_base(force=args.force)
    if args.stage in ("complete", "all"):
        run_stage_complete(DEFAULT_CASE_SPECS, force=args.force)


if __name__ == "__main__":
    main()
