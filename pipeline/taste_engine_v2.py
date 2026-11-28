"""AetherVault Taste & Anti-Homogenization Engine v2.1 (Codex-Hardened Stratified + Pixel Contrast).

Upgrades v2.0 -> v2.1 based on empirical calibration audit:
1. Pixel-Verifiable Multi-Axis Contrast (`visual_features_v2.py`):
   - Replaces noisy VLM single-scalar darkness triggers (`inv_lighting_chiaroscuro`) with
     deterministic OKLab color contrast (chroma P90, high-chroma ratio, chromatic circular hue,
     lightness span — never darkening monochrome alone) + 4x4 spatial edge/orientation/negative-space
     contrast + residual embedding distance `e - E[e | domain, typology]`.
   - Converts each axis distance to nearest-3 familiar personal items into leave-one-out
     domain percentiles `q_color`, `q_comp`, `q_resid`, enforcing `q_primary >= 0.90` + visible delta.
2. Stratified 4-Type Q1 Pairwise Experimental Design (25% / 35% / 20% / 20%):
   - T1 `同门类 · 比风格方向` (25%): same domain & medium, different aesthetic_style.
   - T2 `同风格 · 比具体作品` (35%): same domain + aesthetic_style (+ typology), different instances.
   - T3 `同对象 · 换色彩/光线处理` (20%): same domain + typology, close composition/lightness, top-25% color/lighting diff.
   - T4 `同构图 · 换材质/主体（近似对照）` (20%): close 4x4 layout & aspect, different material/subject.
   - Splits skip into `tie_like` ("同样喜欢") vs `cannot_compare` ("无法比较").
3. 7-Parameter Hierarchical Bradley-Terry Preference Model:
   - `U_i = b_{dom,style} + alpha^T g_{dom,style} + beta^T z_i` (2 macro residual PCA coeffs +
     5 within-(domain,style)-centered execution coeffs; macro terms cancel identically on T2 pairs!).
   - Uses 10 PinnerSage Ward Medoids for multi-interest retrieval/bridging; separates legacy
     cross-domain votes as diagnostic-only.
4. Dual Confirmation for 「完成度标准」 (`craft_confirmed` + `contrast_confirmed`), preserving
   all historical user confirmations cleanly.

Never modifies the public 80-asset showcase (`web/public/data/aethervault_showcase_v1.json`).
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.optimize import minimize
from scipy.spatial.distance import pdist, squareform

from .visual_features_v2 import build_visual_features_cache

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "pinterest_500"
WEB_PERSONAL_JSON = REPO_ROOT / "web" / "public" / "data" / "aethervault_personal_500.json"
EMB_NPZ_PATH = DATA_DIR / "embeddings_500.npz"

TASTE_PROFILE_V2_PATH = DATA_DIR / "taste_profile_v2.json"
CALIBRATION_LOG_PATH = DATA_DIR / "taste_calibration_pairs.jsonl"
CRAFT_ANCHORS_V2_PATH = DATA_DIR / "craft_anchors_v2.json"
CRAFT_VERDICTS_V2_PATH = DATA_DIR / "craft_verdicts_v2.json"
PERSONAL_390_AESTHETIC_PATH = DATA_DIR / "personal_390_aesthetic_v2.json"

REASON_ATTRACTOR_CHIPS: list[dict[str, str]] = [
    {"key": "light", "label": "光影与明暗塑形"},
    {"key": "silence", "label": "留白与静谧克制"},
    {"key": "order", "label": "秩序、网格与韵律"},
    {"key": "punctum", "label": "破格刺点与尺度张力"},
    {"key": "color", "label": "色彩情绪与冷暖对冲"},
    {"key": "material", "label": "材质肌理与触觉温度"},
    {"key": "gesture", "label": "笔触势能与即兴生命"},
    {"key": "form", "label": "造型轮廓与结构美"},
    {"key": "depth", "label": "层次纵深与框景透视"},
    {"key": "mood", "label": "诗意隐喻与情绪画外音"},
]


def _detect_species_and_structure(
    asset: dict[str, Any],
    enrich_assets: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    """Return (image_species, subject_structure) using audited 390-pin data or deterministic metadata."""
    aid = asset.get("asset_id", "")
    if aid in enrich_assets:
        e = enrich_assets[aid]
        return str(e.get("image_species", "spatial_photography")), str(
            e.get("subject_structure", "single_unified")
        )
    facets = asset.get("rag_facets") or {}
    text = " ".join(
        [
            str(asset.get("title", "")),
            str(asset.get("sub_category", "")),
            str(facets.get("medium", "")),
            str(facets.get("typology", "")),
        ]
    ).lower()
    if any(k in text for k in ("collage", "contact sheet", "moodboard", "multi-panel", "拼贴", "四宫格", "九宫格", "合集", "展板")):
        return "multi_subject_sheet", "multi_subject_composite"
    if any(k in text for k in ("palette", "swatch", "色卡", "色板", "配色")):
        return "color_material_specimen", "specimen_or_system"
    if any(k in text for k in ("sketch", "drawing", "ink", "草图", "速写", "线稿", "手绘")):
        return "sketch_process_diagram", "single_unified"
    if any(k in text for k in ("ui", "interface", "webpage", "dashboard", "网页", "界面")):
        return "ui_digital_interface", "specimen_or_system"
    arch = str(asset.get("archetype", ""))
    if arch in {"craft", "industrial"}:
        return "product_craft_object", "single_unified"
    if arch == "graphic_typography":
        return "graphic_poster_identity", "single_unified"
    if arch == "illustration_character":
        return "fine_art_illustration", "single_unified"
    if arch == "fashion_photography":
        return "editorial_fashion_still", "single_unified"
    return "spatial_photography", "single_unified"

DEFAULT_MEDOID_K = 10
AXIS_NAMES = (
    "tectonic_honesty",
    "surface_entropy",
    "spatial_density",
    "geometric_order",
    "lighting_drama",
    "chromatic_tension",
    "thermal_mood",
    "reality_abstraction",
)
DOMAINS_8 = (
    "interior",
    "architecture",
    "graphic_typography",
    "craft",
    "industrial",
    "landscape",
    "illustration_character",
    "fashion_photography",
)

STRATUM_SPECS: dict[str, dict[str, Any]] = {
    "T1_macro_style": {
        "ratio": 0.25,
        "badge_zh": "T1 · 同门类 · 比风格方向",
        "question_zh": "同门类下，哪种大风格方向更合你口味？",
        "hint_zh": "固定门类与完成度、切换不同风格流派，用于学习宏观风格倾向",
    },
    "T2_same_style_instance": {
        "ratio": 0.35,
        "badge_zh": "T2 · 同风格 · 比具体作品",
        "question_zh": "同一风格下，哪件作品的色彩、构图与完成度更打动你？",
        "hint_zh": "锁定同门类同风格（宏观项自动相消），纯粹教模型细粒度执行品味",
    },
    "T3_same_subject_treatment": {
        "ratio": 0.20,
        "badge_zh": "T3 · 同对象 · 换色彩/光线处理",
        "question_zh": "相近题材与构图下，哪种配色或光影处理更合你口味？",
        "hint_zh": "控制构图与明度相近，放大色系或光影跨度差异（自然样本近似对照）",
    },
    "T4_same_comp_material_or_subject": {
        "ratio": 0.20,
        "badge_zh": "T4 · 同构图 · 换材质/主体（近似对照）",
        "question_zh": "相近构图与画幅下，哪件的材质语言或主体表达更戳你？",
        "hint_zh": "按 4×4 空间亮度与边缘布局找构图近邻，切换材质或主体（近似对照）",
    },
}

_STATE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_color_dist_matrix(cv_a: np.ndarray, cv_b: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute human-verifiable OKLab color contrast distance (excludes plain darkness L_med!).
    color_vec layout: [0:L_med, 1:L_span, 2:C_med, 3:C_p90, 4:highC, 5:chrom_ratio, 6:hue_cos, 7:hue_sin].
    Returns (d_color, c_p90_diff, highc_diff, hue_deg_diff) of shape (len(a), len(b)).
    """
    c_p90_diff = np.abs(cv_a[:, 3:4] - cv_b[None, :, 3])
    highc_diff = np.abs(cv_a[:, 4:5] - cv_b[None, :, 4])
    l_span_diff = np.abs(cv_a[:, 1:2] - cv_b[None, :, 1])

    # Circular chromatic hue distance ONLY when both images have chromatic pixels
    dot_h = cv_a[:, 6:7] * cv_b[None, :, 6] + cv_a[:, 7:8] * cv_b[None, :, 7]
    norm_a = np.hypot(cv_a[:, 6:7], cv_a[:, 7:8])
    norm_b = np.hypot(cv_b[None, :, 6], cv_b[None, :, 7])
    cos_h = np.clip(dot_h / np.maximum(norm_a * norm_b, 1e-6), -1.0, 1.0)
    hue_rad = np.arccos(cos_h)
    hue_deg = np.degrees(hue_rad)
    min_chrom = np.minimum(cv_a[:, 5:6], cv_b[None, :, 5])
    hue_term = min_chrom * (hue_rad / math.pi)

    d_color = 4.5 * c_p90_diff + 2.2 * highc_diff + 1.4 * hue_term + 0.45 * l_span_diff
    return d_color.astype(np.float32), c_p90_diff.astype(np.float32), highc_diff.astype(np.float32), (hue_deg * (min_chrom >= 0.22)).astype(np.float32)


def _compute_comp_dist_matrix(
    ge_a: np.ndarray,
    cs_a: np.ndarray,
    ge_b: np.ndarray,
    cs_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute 4x4 composition/edge/entropy contrast distance.
    comp_scalars: [0:edge_density, 1:orient_entropy, 2:neg_space_ratio, 3:aspect_log].
    Returns (d_comp, grid_edge_l2, edge_density_diff, neg_space_diff).
    """
    diff_ge = ge_a[:, None, :] - ge_b[None, :, :]
    grid_edge_l2 = np.linalg.norm(diff_ge, axis=2)
    edge_diff = np.abs(cs_a[:, 0:1] - cs_b[None, :, 0])
    orient_diff = np.abs(cs_a[:, 1:2] - cs_b[None, :, 1])
    neg_diff = np.abs(cs_a[:, 2:3] - cs_b[None, :, 2])
    d_comp = 3.0 * grid_edge_l2 + 6.0 * edge_diff + 1.5 * orient_diff + 0.9 * neg_diff
    return d_comp.astype(np.float32), grid_edge_l2.astype(np.float32), edge_diff.astype(np.float32), neg_diff.astype(np.float32)


def _load_corpus(force_reload: bool = False) -> dict[str, Any]:
    """Load personal 1500-asset bundle, 256d embeddings, OKLab+4x4 CV features, residualized styles & contrast table."""
    p_mtime = WEB_PERSONAL_JSON.stat().st_mtime if WEB_PERSONAL_JSON.is_file() else 0.0
    e_mtime = EMB_NPZ_PATH.stat().st_mtime if EMB_NPZ_PATH.is_file() else 0.0
    if (
        not force_reload
        and _CACHE.get("p_mtime") == p_mtime
        and _CACHE.get("e_mtime") == e_mtime
        and "assets" in _CACHE
    ):
        return _CACHE

    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    emb = np.load(EMB_NPZ_PATH, allow_pickle=False)
    assets: list[dict[str, Any]] = bundle["assets"]
    emb_ids = [str(x) for x in emb["asset_ids"].tolist()]
    emb_vecs = emb["vectors"].astype(np.float32)
    id_to_emb_idx = {aid: i for i, aid in enumerate(emb_ids)}

    n = len(assets)
    aligned_vecs = np.zeros((n, emb_vecs.shape[1]), dtype=np.float32)
    for i, a in enumerate(assets):
        idx = id_to_emb_idx.get(a["asset_id"])
        if idx is not None:
            aligned_vecs[i] = emb_vecs[idx]
    aligned_vecs = aligned_vecs / np.maximum(np.linalg.norm(aligned_vecs, axis=1, keepdims=True), 1e-8)

    # Load deterministic OKLab + 4x4 CV visual features
    vfeat = build_visual_features_cache(force=False)
    color_vec = vfeat["color_vec"].astype(np.float32)
    grid_luma = vfeat["grid_luma"].astype(np.float32)
    grid_edge = vfeat["grid_edge"].astype(np.float32)
    comp_scalars = vfeat["comp_scalars"].astype(np.float32)
    z_raw = vfeat["z_raw"].astype(np.float32)

    id_to_idx = {a["asset_id"]: i for i, a in enumerate(assets)}
    personal_indices = [i for i, a in enumerate(assets) if a.get("source_origin") == "pinterest_personal"]
    expansion_indices = [i for i, a in enumerate(assets) if a.get("source_origin") != "pinterest_personal"]

    # Load audited 390 personal Pinterest 7-family & multi-species aesthetic enrichments
    personal_390_enrich: dict[str, Any] = {"families": [], "assets": {}}
    if PERSONAL_390_AESTHETIC_PATH.is_file():
        try:
            personal_390_enrich = json.loads(PERSONAL_390_AESTHETIC_PATH.read_text(encoding="utf-8"))
        except Exception:
            personal_390_enrich = {"families": [], "assets": {}}
    enrich_assets: dict[str, dict[str, Any]] = personal_390_enrich.get("assets", {})
    species_map: list[tuple[str, str]] = [
        _detect_species_and_structure(a, enrich_assets) for a in assets
    ]

    # 8-axis VLM matrix (retained for diagnostics)
    mat8 = np.zeros((n, len(AXIS_NAMES)), dtype=np.float32)
    for i, a in enumerate(assets):
        spec = a.get("style_spectrums") or {}
        for j, ax in enumerate(AXIS_NAMES):
            mat8[i, j] = float((spec.get(ax) or {}).get("score", 0.0))

    # Core centroid (legacy baseline)
    core_centroid = aligned_vecs[personal_indices].mean(axis=0)
    core_centroid = core_centroid / max(1e-8, float(np.linalg.norm(core_centroid)))

    # --- 1. Residual embedding `e - E[e | domain, typology]` ---
    dt_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    dom_groups: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(assets):
        dom = a.get("archetype", "unknown")
        typ = (a.get("rag_facets") or {}).get("typology", "")
        dt_groups[(dom, typ)].append(i)
        dom_groups[dom].append(i)

    dom_means = {d: aligned_vecs[idxs].mean(axis=0) for d, idxs in dom_groups.items()}
    dt_means = {k: aligned_vecs[idxs].mean(axis=0) for k, idxs in dt_groups.items() if len(idxs) >= 4}
    resid_vecs = np.zeros_like(aligned_vecs)
    for i, a in enumerate(assets):
        dom = a.get("archetype", "unknown")
        typ = (a.get("rag_facets") or {}).get("typology", "")
        base = dt_means.get((dom, typ), dom_means[dom])
        r = aligned_vecs[i] - base
        resid_vecs[i] = r / max(1e-8, float(np.linalg.norm(r)))

    # --- 2. Hierarchical 7-Param BT Fixed Features: b_{dom,style}, g_{dom,style} (R^2), z_centered (R^5) ---
    ds_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    pers_dom_counts = Counter()
    pers_ds_counts = Counter()
    all_dom_counts = Counter()
    all_ds_counts = Counter()
    for i, a in enumerate(assets):
        dom = a.get("archetype", "unknown")
        st = a.get("aesthetic_style", "unknown")
        ds_groups[(dom, st)].append(i)
        all_dom_counts[dom] += 1
        all_ds_counts[(dom, st)] += 1
        if a.get("source_origin") == "pinterest_personal":
            pers_dom_counts[dom] += 1
            pers_ds_counts[(dom, st)] += 1

    # Smoothed weak prior b_{dom,style}
    b_prior = np.zeros(n, dtype=np.float32)
    dom_style_counts = Counter(d for (d, _s) in ds_groups.keys())
    for (dom, st), idxs in ds_groups.items():
        n_s = max(1, dom_style_counts[dom])
        p_pers = (pers_ds_counts[(dom, st)] + 0.5) / (pers_dom_counts[dom] + 0.5 * n_s)
        p_all = (all_ds_counts[(dom, st)] + 0.5) / (all_dom_counts[dom] + 0.5 * n_s)
        prior_val = 0.25 * math.log(max(1e-6, p_pers) / max(1e-6, p_all))
        for i in idxs:
            b_prior[i] = prior_val

    # Macro 2-dim style prototype PCA `g_{dom,style}` on residualized prototypes
    proto_keys = sorted(ds_groups.keys())
    proto_mat = np.stack([resid_vecs[ds_groups[k]].mean(axis=0) for k in proto_keys], axis=0)
    proto_centered = proto_mat - proto_mat.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(proto_centered, full_matrices=False)
    g_proj = proto_centered @ vt[:2].T  # (n_styles, 2)
    g_std = np.maximum(g_proj.std(axis=0, keepdims=True), 1e-6)
    g_proj = (g_proj / g_std).astype(np.float32)
    g_by_key = {k: g_proj[idx] for idx, k in enumerate(proto_keys)}
    g_macro = np.zeros((n, 2), dtype=np.float32)
    for i, a in enumerate(assets):
        g_macro[i] = g_by_key[(a.get("archetype", "unknown"), a.get("aesthetic_style", "unknown"))]

    # Micro 5-dim execution vector `z_i` centered strictly within each (domain, style) group!
    z_centered = np.zeros_like(z_raw)
    global_z_std = np.maximum(z_raw.std(axis=0, keepdims=True), 1e-6)
    for (_dom, _st), idxs in ds_groups.items():
        sub = z_raw[idxs]
        mu = sub.mean(axis=0, keepdims=True)
        sd = sub.std(axis=0, keepdims=True) if len(idxs) >= 5 else global_z_std
        sd = np.maximum(sd, global_z_std * 0.25)
        z_centered[idxs] = np.clip((sub - mu) / sd, -3.0, 3.0)

    # --- 3. Pixel-Verifiable Multi-Axis Contrast Table (per domain, leave-one-out percentile) ---
    contrast_table: list[dict[str, Any]] = [{} for _ in range(n)]
    low_personal_domains: set[str] = set()

    for dom in DOMAINS_8:
        dom_idx = dom_groups.get(dom, [])
        if not dom_idx:
            continue
        fam_idx = [i for i in dom_idx if assets[i].get("source_origin") == "pinterest_personal"]
        if len(fam_idx) < 8:
            low_personal_domains.add(dom)
        if len(fam_idx) < 4:
            # Fallback to highest-quality assets in domain if personal count is tiny
            fam_idx = sorted(dom_idx, key=lambda i: -int(assets[i].get("aesthetic_quality_score", 0)))[:12]

        f_arr = np.asarray(fam_idx, dtype=np.int32)
        d_arr = np.asarray(dom_idx, dtype=np.int32)
        k_nn = min(3, max(1, len(fam_idx) - 1))

        # Familiar-to-familiar leave-one-out baseline distributions
        fc_d, _, _, _ = _compute_color_dist_matrix(color_vec[f_arr], color_vec[f_arr])
        np.fill_diagonal(fc_d, 1e9)
        fam_color_base = np.sort(fc_d, axis=1)[:, :k_nn].mean(axis=1)  # median/mean of nearest-3

        fcomp_d, _, _, _ = _compute_comp_dist_matrix(grid_edge[f_arr], comp_scalars[f_arr], grid_edge[f_arr], comp_scalars[f_arr])
        np.fill_diagonal(fcomp_d, 1e9)
        fam_comp_base = np.sort(fcomp_d, axis=1)[:, :k_nn].mean(axis=1)

        fres_d = 1.0 - (resid_vecs[f_arr] @ resid_vecs[f_arr].T)
        np.fill_diagonal(fres_d, 1e9)
        fam_resid_base = np.sort(fres_d, axis=1)[:, :k_nn].mean(axis=1)

        # Candidate-to-familiar distances for every asset in domain
        cc_d, c_p90_diff, highc_diff, hue_deg = _compute_color_dist_matrix(color_vec[d_arr], color_vec[f_arr])
        ccomp_d, ge_l2, edge_diff, neg_diff = _compute_comp_dist_matrix(grid_edge[d_arr], comp_scalars[d_arr], grid_edge[f_arr], comp_scalars[f_arr])
        cres_d = 1.0 - (resid_vecs[d_arr] @ resid_vecs[f_arr].T)

        for local_pos, gi in enumerate(dom_idx):
            # Exclude self if gi is in fam_idx
            row_c = cc_d[local_pos].copy()
            row_cp = ccomp_d[local_pos].copy()
            row_r = cres_d[local_pos].copy()
            if gi in fam_idx:
                self_pos = fam_idx.index(gi)
                row_c[self_pos] = 1e9
                row_cp[self_pos] = 1e9
                row_r[self_pos] = 1e9

            nn_c_idx = np.argsort(row_c)[:k_nn]
            nn_cp_idx = np.argsort(row_cp)[:k_nn]
            nn_r_idx = np.argsort(row_r)[:k_nn]

            dc_val = float(np.median(row_c[nn_c_idx]))
            dcp_val = float(np.median(row_cp[nn_cp_idx]))
            dr_val = float(np.median(row_r[nn_r_idx]))

            q_color = float(np.mean(fam_color_base <= dc_val))
            q_comp = float(np.mean(fam_comp_base <= dcp_val))
            q_resid = float(np.mean(fam_resid_base <= dr_val))

            # Visible delta checks against nearest-3 familiar peers on that axis
            med_cp90 = float(np.median(c_p90_diff[local_pos, nn_c_idx]))
            med_highc = float(np.median(highc_diff[local_pos, nn_c_idx]))
            med_hue = float(np.median(hue_deg[local_pos, nn_c_idx]))
            color_visible = (med_cp90 >= 0.035) or (med_highc >= 0.08) or (med_hue >= 55.0)

            med_gel2 = float(np.median(ge_l2[local_pos, nn_cp_idx]))
            med_ed = float(np.median(edge_diff[local_pos, nn_cp_idx]))
            med_neg = float(np.median(neg_diff[local_pos, nn_cp_idx]))
            comp_visible = (med_ed >= 0.035) or (med_gel2 >= 0.22) or (med_neg >= 0.35)

            sp_gi, st_gi = species_map[gi]
            gutter_guarded = (st_gi == "multi_subject_composite") or (
                sp_gi in {"multi_subject_sheet", "color_material_specimen"}
            )
            color_pass = (q_color >= 0.90) and color_visible
            # Guard multi-panel sheets/swatches so white panel gutters never trigger fake 4x4 composition contrast
            comp_pass = (q_comp >= 0.90) and comp_visible and (not gutter_guarded)

            primary_axis: str | None = None
            primary_q = 0.0
            reason_zh = "未达反差主轴门槛（P90+可见差值）"
            if color_pass and (not comp_pass or q_color >= q_comp):
                primary_axis = "color_oklab"
                primary_q = q_color
                reason_zh = f"色彩反差 P{int(round(q_color*100))}（彩度差 {med_cp90:.2f} · 高彩占比差 {med_highc:.2f}）"
            elif comp_pass:
                primary_axis = "composition_4x4"
                primary_q = q_comp
                reason_zh = f"构图密度反差 P{int(round(q_comp*100))}（边缘布局差 {med_gel2:.2f} · 留白差 {med_neg:.2f}）"
            elif gutter_guarded and (q_comp >= 0.90) and comp_visible:
                reason_zh = "多主体/色卡拼版已屏蔽白缝假构图反差"

            contrast_score = round(0.8 * primary_q + 0.2 * q_resid, 4) if primary_axis else 0.0
            contrast_table[gi] = {
                "passes_contrast": primary_axis is not None,
                "primary_axis": primary_axis,
                "q_color": round(q_color, 4),
                "q_comp": round(q_comp, 4),
                "q_resid": round(q_resid, 4),
                "contrast_score": contrast_score,
                "color_visible": color_visible,
                "comp_visible": comp_visible,
                "gutter_guarded": gutter_guarded,
                "image_species": sp_gi,
                "subject_structure": st_gi,
                "reason_zh": reason_zh,
                "low_personal_prior": dom in low_personal_domains,
            }

    _CACHE.clear()
    _CACHE.update(
        {
            "p_mtime": p_mtime,
            "e_mtime": e_mtime,
            "assets": assets,
            "vecs": aligned_vecs,
            "resid_vecs": resid_vecs,
            "mat8": mat8,
            "color_vec": color_vec,
            "grid_luma": grid_luma,
            "grid_edge": grid_edge,
            "comp_scalars": comp_scalars,
            "z_raw": z_raw,
            "b_prior": b_prior,
            "g_macro": g_macro,
            "z_centered": z_centered,
            "contrast_table": contrast_table,
            "id_to_idx": id_to_idx,
            "personal_indices": personal_indices,
            "expansion_indices": expansion_indices,
            "core_centroid": core_centroid,
            "personal_390_enrich": personal_390_enrich,
            "species_map": species_map,
        }
    )
    return _CACHE


def build_medoid_profile(k: int = DEFAULT_MEDOID_K, persist: bool = True) -> dict[str, Any]:
    """Compute PinnerSage-style K Ward Medoids on 390 personal origins (used for retrieval & bridging)."""
    ctx = _load_corpus()
    assets = ctx["assets"]
    vecs = ctx["vecs"]
    mat8 = ctx["mat8"]
    p_idx = ctx["personal_indices"]

    p_vecs = vecs[p_idx]
    Z = linkage(p_vecs, method="ward")
    labels = fcluster(Z, t=k, criterion="maxclust")
    dist_mat = squareform(pdist(p_vecs, metric="euclidean"))

    medoids: list[dict[str, Any]] = []
    for cid in range(1, k + 1):
        members = np.where(labels == cid)[0]
        sub_d = dist_mat[np.ix_(members, members)].sum(axis=1)
        m_local = int(members[int(np.argmin(sub_d))])
        m_global = p_idx[m_local]
        m_asset = assets[m_global]
        dom_counts = Counter(assets[p_idx[m]].get("archetype", "unknown") for m in members)
        dom_zh_counts = Counter(assets[p_idx[m]].get("archetype_label", "") for m in members)
        medoids.append(
            {
                "medoid_id": f"M{cid:02d}",
                "asset_id": m_asset["asset_id"],
                "title": m_asset["title"],
                "image_url": m_asset["image_url"],
                "archetype": m_asset.get("archetype", ""),
                "archetype_label": m_asset.get("archetype_label", ""),
                "aesthetic_style_zh": m_asset.get("aesthetic_style_zh", ""),
                "cluster_size": int(len(members)),
                "cluster_weight": round(float(len(members) / max(1, len(p_idx))), 4),
                "top_domains": [{"domain": d, "count": int(c)} for d, c in dom_counts.most_common(3)],
                "top_domains_zh": [{"label": d, "count": int(c)} for d, c in dom_zh_counts.most_common(2)],
            }
        )

    medoids.sort(key=lambda m: -m["cluster_size"])
    for rank, m in enumerate(medoids, start=1):
        m["medoid_id"] = f"M{rank:02d}"

    corr = np.corrcoef(mat8, rowvar=False)
    coupled_pairs = []
    for i in range(len(AXIS_NAMES)):
        for j in range(i + 1, len(AXIS_NAMES)):
            r = float(corr[i, j])
            if abs(r) >= 0.35:
                coupled_pairs.append({"axis_a": AXIS_NAMES[i], "axis_b": AXIS_NAMES[j], "r": round(r, 3)})
    coupled_pairs.sort(key=lambda x: -abs(x["r"]))

    profile = {
        "version": "2.1.0-stratified-taste-medoids",
        "generated_at": _utc_now(),
        "personal_count": len(p_idx),
        "total_atlas_count": len(assets),
        "k_medoids": k,
        "medoids": medoids,
        "personal_axis_means": {ax: round(float(mat8[p_idx, i].mean()), 3) for i, ax in enumerate(AXIS_NAMES)},
        "coupled_axis_pairs_gt_035": coupled_pairs,
    }
    if persist:
        TASTE_PROFILE_V2_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def load_or_build_medoid_profile() -> dict[str, Any]:
    if TASTE_PROFILE_V2_PATH.is_file():
        try:
            prof = json.loads(TASTE_PROFILE_V2_PATH.read_text(encoding="utf-8"))
            ctx = _load_corpus()
            if (
                prof.get("version", "").startswith("2.1")
                and prof.get("personal_count") == len(ctx["personal_indices"])
                and len(prof.get("medoids", [])) == DEFAULT_MEDOID_K
            ):
                return prof
        except Exception:
            pass
    return build_medoid_profile(k=DEFAULT_MEDOID_K, persist=True)


def _medoid_matrix(profile: dict[str, Any], ctx: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    medoids = profile["medoids"]
    vecs = ctx["vecs"]
    id_to_idx = ctx["id_to_idx"]
    rows = [vecs[id_to_idx[m["asset_id"]]] for m in medoids]
    weights = [float(m["cluster_weight"]) for m in medoids]
    M = np.stack(rows, axis=0).astype(np.float32)
    prior_w = np.asarray(weights, dtype=np.float32)
    prior_w = prior_w / max(1e-8, float(prior_w.sum())) * len(medoids)
    return M, prior_w, medoids


def load_calibration_votes() -> list[dict[str, Any]]:
    if not CALIBRATION_LOG_PATH.is_file():
        return []
    out: list[dict[str, Any]] = []
    for ln in CALIBRATION_LOG_PATH.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def append_calibration_vote(
    signal: str,
    asset_a: str,
    asset_b: str,
    choice: str,
    meta: dict[str, Any] | None = None,
    chosen_reasons: list[str] | None = None,
    reason_note: str | None = None,
) -> dict[str, Any]:
    if signal not in {"core_taste", "serendipity_save"}:
        raise ValueError("signal must be 'core_taste' or 'serendipity_save'")
    if choice not in {"a", "b", "tie_like", "cannot_compare", "skip", "both", "neither"}:
        raise ValueError("Invalid calibration choice.")
    ctx = _load_corpus()
    if asset_a not in ctx["id_to_idx"] or asset_b not in ctx["id_to_idx"]:
        raise ValueError("Unknown asset_id in calibration vote.")

    clean_reasons = [str(r).strip() for r in (chosen_reasons or []) if str(r).strip()][:6]
    clean_note = (reason_note or "").strip()[:240]
    merged_meta = dict(meta or {})
    if clean_reasons:
        merged_meta["chosen_reasons"] = clean_reasons
    if clean_note:
        merged_meta["reason_note"] = clean_note

    rec = {
        "ts": _utc_now(),
        "signal": signal,
        "asset_a": asset_a,
        "asset_b": asset_b,
        "choice": choice,
        "chosen_reasons": clean_reasons,
        "reason_note": clean_note,
        "meta": merged_meta,
    }
    with _STATE_LOCK:
        CALIBRATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CALIBRATION_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def fit_bt_medoid_head(
    votes: list[dict[str, Any]],
    phi_all: np.ndarray,
    id_to_idx: dict[str, int],
    prior_w: np.ndarray,
    l2_reg: float = 1.5,
) -> dict[str, Any]:
    """Legacy 10-Medoid BT head (retained as benchmark baseline & unit-test compatibility)."""
    pairs: list[tuple[int, int]] = []
    for v in votes:
        if v.get("signal") != "core_taste":
            continue
        ch = v.get("choice")
        if ch not in {"a", "b"}:
            continue
        ia = id_to_idx.get(v.get("asset_a", ""))
        ib = id_to_idx.get(v.get("asset_b", ""))
        if ia is None or ib is None or ia == ib:
            continue
        pairs.append((ia, ib) if ch == "a" else (ib, ia))

    if len(pairs) < 3:
        return {
            "fitted": False,
            "n_core_pairs": len(pairs),
            "weights": prior_w.astype(np.float32),
            "train_acc": None,
            "cv_acc": None,
            "max_medoid_acc": None,
            "single_centroid_acc": None,
        }

    diffs = np.stack([phi_all[w_i] - phi_all[l_i] for w_i, l_i in pairs], axis=0).astype(np.float64)
    w0 = prior_w.astype(np.float64)

    def _fit_subset(sub_diffs: np.ndarray) -> np.ndarray:
        def loss_and_grad(w: np.ndarray) -> tuple[float, np.ndarray]:
            z = sub_diffs @ w
            loss = float(np.sum(np.logaddexp(0.0, -z)) + 0.5 * l2_reg * np.sum((w - w0) ** 2))
            sig = 1.0 / (1.0 + np.exp(np.clip(z, -30.0, 30.0)))
            grad = -(sub_diffs.T @ sig) + l2_reg * (w - w0)
            return loss, grad

        res = minimize(loss_and_grad, x0=w0.copy(), jac=True, method="L-BFGS-B")
        return res.x.astype(np.float32)

    w_full = _fit_subset(diffs)
    train_acc = float(np.mean((diffs @ w_full) > 0))
    cv_acc: float | None = None
    if len(pairs) >= 10:
        n_folds = min(5, len(pairs))
        correct = 0
        for f in range(n_folds):
            val_mask = np.arange(len(pairs)) % n_folds == f
            wf = _fit_subset(diffs[~val_mask])
            correct += int(np.sum((diffs[val_mask] @ wf) > 0))
        cv_acc = round(correct / len(pairs), 4)

    max_med = phi_all.max(axis=1)
    max_med_acc = round(float(np.mean([max_med[w_i] > max_med[l_i] for w_i, l_i in pairs])), 4)
    ctx = _load_corpus()
    sc_scores = ctx["vecs"] @ ctx["core_centroid"]
    sc_acc = round(float(np.mean([sc_scores[w_i] > sc_scores[l_i] for w_i, l_i in pairs])), 4)
    return {
        "fitted": True,
        "n_core_pairs": len(pairs),
        "weights": w_full,
        "train_acc": round(train_acc, 4),
        "cv_acc": cv_acc,
        "max_medoid_acc": max_med_acc,
        "single_centroid_acc": sc_acc,
    }


def fit_hierarchical_bt_v21(
    votes: list[dict[str, Any]],
    ctx: dict[str, Any],
    phi_all: np.ndarray,
    l2_reg: float = 2.0,
) -> dict[str, Any]:
    """Fit 7-parameter Hierarchical Bradley-Terry strictly on same-domain/stratified Q1 pairs.

    U_i = b_{dom,style} + alpha^T g_{dom,style} (2 params) + beta^T z_i (5 within-style-centered params).
    On T2 same-style pairs, macro terms cancel identically so beta learns pure execution taste!
    Legacy cross-domain votes are tracked separately for diagnostics and NEVER pollute training.
    """
    assets = ctx["assets"]
    id_to_idx = ctx["id_to_idx"]
    b_prior = ctx["b_prior"]
    g_macro = ctx["g_macro"]
    z_cent = ctx["z_centered"]
    X7 = np.concatenate([g_macro, z_cent], axis=1).astype(np.float64)  # (N, 7)

    train_pairs: list[tuple[int, int, str]] = []
    stratum_counts = Counter()
    legacy_cross_count = 0
    tie_like_count = 0
    cannot_compare_count = 0

    for v in votes:
        if v.get("signal") != "core_taste":
            continue
        ch = v.get("choice")
        if ch == "tie_like":
            tie_like_count += 1
            continue
        if ch in {"cannot_compare", "skip"}:
            cannot_compare_count += 1
            continue
        if ch not in {"a", "b"}:
            continue
        ia = id_to_idx.get(v.get("asset_a", ""))
        ib = id_to_idx.get(v.get("asset_b", ""))
        if ia is None or ib is None or ia == ib:
            continue
        stratum = (v.get("meta") or {}).get("stratum")
        same_dom = assets[ia].get("archetype") == assets[ib].get("archetype")
        if not stratum and not same_dom:
            legacy_cross_count += 1
            continue
        if not stratum:
            stratum = "T2_same_style_instance" if assets[ia].get("aesthetic_style") == assets[ib].get("aesthetic_style") else "T1_macro_style"
        stratum_counts[stratum] += 1
        train_pairs.append((ia, ib, stratum) if ch == "a" else (ib, ia, stratum))

    if len(train_pairs) < 5:
        return {
            "fitted": False,
            "n_stratified_pairs": len(train_pairs),
            "legacy_cross_domain_diagnostic": legacy_cross_count,
            "tie_like_count": tie_like_count,
            "cannot_compare_count": cannot_compare_count,
            "stratum_counts": {k: int(stratum_counts.get(k, 0)) for k in STRATUM_SPECS},
            "theta7": [0.0] * 7,
            "alpha_macro2": [0.0, 0.0],
            "beta_micro5": [0.0] * 5,
            "train_acc": None,
            "cv_acc": None,
            "cv_logloss": None,
            "macro_only_acc": None,
            "max_medoid_acc": None,
            "single_centroid_acc": None,
        }

    diffs = np.stack([X7[w_i] - X7[l_i] for w_i, l_i, _ in train_pairs], axis=0)
    b_diffs = np.asarray([float(b_prior[w_i] - b_prior[l_i]) for w_i, l_i, _ in train_pairs], dtype=np.float64)

    def _fit(sub_X: np.ndarray, sub_b: np.ndarray) -> np.ndarray:
        def loss_and_grad(theta: np.ndarray) -> tuple[float, np.ndarray]:
            logits = sub_b + sub_X @ theta
            loss = float(np.sum(np.logaddexp(0.0, -logits)) + 0.5 * l2_reg * np.sum(theta * theta))
            sig = 1.0 / (1.0 + np.exp(np.clip(logits, -30.0, 30.0)))
            grad = -(sub_X.T @ sig) + l2_reg * theta
            return loss, grad

        res = minimize(loss_and_grad, x0=np.zeros(7, dtype=np.float64), jac=True, method="L-BFGS-B")
        return res.x

    theta_full = _fit(diffs, b_diffs)
    train_logits = b_diffs + diffs @ theta_full
    train_acc = float(np.mean(train_logits > 0))

    # 5-fold CV (stratified sequential folds) + log-loss
    n_folds = min(5, len(train_pairs))
    cv_logits = np.zeros(len(train_pairs), dtype=np.float64)
    for f in range(n_folds):
        val_mask = np.arange(len(train_pairs)) % n_folds == f
        tf = _fit(diffs[~val_mask], b_diffs[~val_mask])
        cv_logits[val_mask] = b_diffs[val_mask] + diffs[val_mask] @ tf

    cv_acc = float(np.mean(cv_logits > 0))
    cv_logloss = float(np.mean(np.logaddexp(0.0, -cv_logits)))

    # Same-pair baselines: Macro-only (b + alpha*g), Max-Medoid, Single-Centroid
    macro_only_acc = float(np.mean((b_diffs + diffs[:, :2] @ theta_full[:2]) > 0))
    max_med = phi_all.max(axis=1)
    max_med_acc = float(np.mean([max_med[w_i] > max_med[l_i] for w_i, l_i, _ in train_pairs]))
    sc_scores = ctx["vecs"] @ ctx["core_centroid"]
    sc_acc = float(np.mean([sc_scores[w_i] > sc_scores[l_i] for w_i, l_i, _ in train_pairs]))

    return {
        "fitted": True,
        "n_stratified_pairs": len(train_pairs),
        "legacy_cross_domain_diagnostic": legacy_cross_count,
        "tie_like_count": tie_like_count,
        "cannot_compare_count": cannot_compare_count,
        "stratum_counts": {k: int(stratum_counts.get(k, 0)) for k in STRATUM_SPECS},
        "theta7": [round(float(x), 4) for x in theta_full.tolist()],
        "alpha_macro2": [round(float(x), 4) for x in theta_full[:2].tolist()],
        "beta_micro5": [round(float(x), 4) for x in theta_full[2:].tolist()],
        "beta_labels": ["色彩丰富度", "色温暖度", "明暗跨度", "构图留白", "纹理边缘复杂度"],
        "train_acc": round(train_acc, 4),
        "cv_acc": round(cv_acc, 4),
        "cv_logloss": round(cv_logloss, 4),
        "macro_only_acc": round(macro_only_acc, 4),
        "max_medoid_acc": round(max_med_acc, 4),
        "single_centroid_acc": round(sc_acc, 4),
    }


def _mmr_select(
    candidate_indices: list[int],
    relevance_scores: np.ndarray,
    vecs: np.ndarray,
    limit: int,
    lambda_div: float = 0.72,
) -> list[int]:
    if limit <= 0 or not candidate_indices:
        return []
    cands = list(candidate_indices)
    if len(cands) <= limit:
        cands.sort(key=lambda i: -float(relevance_scores[i]))
        return cands

    cands.sort(key=lambda i: -float(relevance_scores[i]))
    pool = cands[: min(len(cands), max(limit * 3, 180))]
    pool_vecs = vecs[pool]
    rel = relevance_scores[pool].astype(np.float32)
    r_min, r_max = float(rel.min()), float(rel.max())
    rel_norm = (rel - r_min) / max(1e-6, r_max - r_min)

    selected_local: list[int] = [0]
    selected_mask = np.zeros(len(pool), dtype=bool)
    selected_mask[0] = True
    max_sim_to_sel = pool_vecs @ pool_vecs[0]

    for _ in range(1, limit):
        mmr_scores = lambda_div * rel_norm - (1.0 - lambda_div) * max_sim_to_sel
        mmr_scores[selected_mask] = -1e9
        best = int(np.argmax(mmr_scores))
        selected_local.append(best)
        selected_mask[best] = True
        sim_new = pool_vecs @ pool_vecs[best]
        max_sim_to_sel = np.maximum(max_sim_to_sel, sim_new)

    return [pool[i] for i in selected_local]


def load_craft_verdicts() -> dict[str, dict[str, Any]]:
    if not CRAFT_VERDICTS_V2_PATH.is_file():
        return {}
    try:
        return json.loads(CRAFT_VERDICTS_V2_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rerank_three_lanes(
    target_total: int = 1110,
    core_ratio: float = 0.60,
    bridge_ratio: float = 0.25,
    exploration_cap_ratio: float = 0.15,
    mmr_lambda: float = 0.72,
) -> dict[str, Any]:
    """Execute <20ms Zero-LLM 3-Lane Portfolio Slotting + Intra-Lane MMR (v2.1 Pixel Contrast + 7-param BT)."""
    t0 = time.perf_counter()
    ctx = _load_corpus()
    profile = load_or_build_medoid_profile()
    M, _prior_w, medoids = _medoid_matrix(profile, ctx)
    assets = ctx["assets"]
    vecs = ctx["vecs"]
    exp_idx = ctx["expansion_indices"]
    contrast_table = ctx["contrast_table"]

    phi_all = vecs @ M.T
    max_med_sim = phi_all.max(axis=1)
    top_med_idx = phi_all.argmax(axis=1)

    votes = load_calibration_votes()
    hbt = fit_hierarchical_bt_v21(votes, ctx, phi_all)

    if hbt["fitted"]:
        theta = np.asarray(hbt["theta7"], dtype=np.float32)
        X7 = np.concatenate([ctx["g_macro"], ctx["z_centered"]], axis=1)
        raw_u = ctx["b_prior"] + X7 @ theta
        u_z = (raw_u - raw_u.mean()) / max(1e-6, float(raw_u.std()))
        mm_z = (max_med_sim - max_med_sim.mean()) / max(1e-6, float(max_med_sim.std()))
        core_score = 0.65 * u_z + 0.35 * mm_z
    else:
        core_score = max_med_sim.copy()

    verdicts = load_craft_verdicts()

    def _passes_craft_floor(i: int, strict_for_exploration: bool = False) -> bool:
        a = assets[i]
        v = verdicts.get(a["asset_id"])
        if v is not None:
            return bool(v.get("meets_floor", False))
        q = int(a.get("aesthetic_quality_score", 0))
        return q >= 9 if strict_for_exploration else q >= 8

    # Exploration BYPASS LANE: strictly pixel-verifiable contrast (q_primary >= 0.90 + visible delta), NEVER Core Taste gated!
    expl_pool: list[int] = []
    expl_rel = np.zeros(len(assets), dtype=np.float32)
    for i in exp_idx:
        if not _passes_craft_floor(i, strict_for_exploration=True):
            continue
        ct = contrast_table[i]
        if ct.get("passes_contrast"):
            expl_pool.append(i)
            expl_rel[i] = float(ct["contrast_score"])

    expl_cap = int(round(target_total * exploration_cap_ratio))
    expl_selected = _mmr_select(expl_pool, expl_rel, vecs, limit=min(expl_cap, len(expl_pool)), lambda_div=mmr_lambda)
    expl_set = set(expl_selected)

    bridge_pool: list[int] = []
    core_pool: list[int] = []
    for i in exp_idx:
        if i in expl_set or not _passes_craft_floor(i, strict_for_exploration=False):
            continue
        nearest_m = medoids[int(top_med_idx[i])]
        if assets[i].get("archetype") != nearest_m.get("archetype"):
            bridge_pool.append(i)
        else:
            core_pool.append(i)

    bridge_target = int(round(target_total * bridge_ratio))
    bridge_selected = _mmr_select(bridge_pool, core_score, vecs, limit=min(bridge_target, len(bridge_pool)), lambda_div=mmr_lambda)
    bridge_set = set(bridge_selected)

    core_target = max(0, target_total - len(expl_selected) - len(bridge_selected))
    core_remaining = [i for i in core_pool if i not in bridge_set]
    core_selected = _mmr_select(core_remaining, core_score, vecs, limit=min(core_target, len(core_remaining)), lambda_div=mmr_lambda)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    serend_votes = [v for v in votes if v.get("signal") == "serendipity_save"]
    serend_saved = sum(1 for v in serend_votes if v.get("choice") in {"a", "b", "both"})

    return {
        "latency_ms": elapsed_ms,
        "target_total": target_total,
        "selected_total": len(core_selected) + len(bridge_selected) + len(expl_selected),
        "lane_counts": {
            "core_resonance": len(core_selected),
            "cross_domain_bridge": len(bridge_selected),
            "adversarial_exploration": len(expl_selected),
            "exploration_qualified_pool": len(expl_pool),
            "exploration_cap": expl_cap,
            "exploration_underfilled_honestly": len(expl_selected) < expl_cap,
        },
        "bt_model": hbt,
        "serendipity_eval": {
            "n_votes": len(serend_votes),
            "n_saved": serend_saved,
            "save_rate": round(serend_saved / len(serend_votes), 4) if serend_votes else None,
        },
    }


def _ranked_contrast_candidates_for_domain(dom: str, exclude_id: str, familiar_style: str) -> list[int]:
    """Return domain candidate indices ranked by deterministic OKLab + 4x4 CV + residual contrast."""
    ctx = _load_corpus()
    assets = ctx["assets"]
    ct = ctx["contrast_table"]

    # Prefer non-personal, pixel-verified contrast items with distinct style & high craft score >= 8
    strict_pool = [
        i
        for i, a in enumerate(assets)
        if a.get("archetype") == dom
        and a["asset_id"] != exclude_id
        and a.get("source_origin") != "pinterest_personal"
        and ct[i].get("passes_contrast")
        and int(a.get("aesthetic_quality_score", 0)) >= 8
    ]
    if not strict_pool:
        strict_pool = [
            i
            for i, a in enumerate(assets)
            if a.get("archetype") == dom
            and a["asset_id"] != exclude_id
            and ct[i].get("passes_contrast")
            and int(a.get("aesthetic_quality_score", 0)) >= 8
        ]
    if not strict_pool:
        # Honest fallback sorted by max(q_color, q_comp) * 0.8 + q_resid * 0.2
        strict_pool = [
            i
            for i, a in enumerate(assets)
            if a.get("archetype") == dom
            and a["asset_id"] != exclude_id
            and int(a.get("aesthetic_quality_score", 0)) >= 8
        ]

    def _sort_key(i: int) -> tuple[int, float]:
        style_diff = 1 if assets[i].get("aesthetic_style") != familiar_style else 0
        c = ct[i]
        score = float(c["contrast_score"]) if c["passes_contrast"] else (0.8 * max(c["q_color"], c["q_comp"]) + 0.2 * c["q_resid"])
        return (style_diff, score)

    strict_pool.sort(key=_sort_key, reverse=True)
    return strict_pool


def load_or_init_craft_anchors() -> dict[str, Any]:
    """Load or upgrade 8 domains x 2 完成度标准参考 (常选风格参考 + 反差风格参考), preserving prior confirmations."""
    ctx = _load_corpus()
    profile = load_or_build_medoid_profile()
    M, _, _ = _medoid_matrix(profile, ctx)
    assets = ctx["assets"]
    vecs = ctx["vecs"]
    ct = ctx["contrast_table"]
    max_med_sim = (vecs @ M.T).max(axis=1)

    existing: dict[str, Any] | None = None
    if CRAFT_ANCHORS_V2_PATH.is_file():
        try:
            existing = json.loads(CRAFT_ANCHORS_V2_PATH.read_text(encoding="utf-8"))
            if existing.get("version") == "2.1.0-completion-standards":
                return existing
        except Exception:
            existing = None

    old_domains = (existing or {}).get("domains", {})
    anchors_by_domain: dict[str, dict[str, Any]] = {}

    def _pack(idx: int, role: str, craft_ok: bool, contrast_ok: bool | None) -> dict[str, Any]:
        a = assets[idx]
        c = ct[idx]
        return {
            "asset_id": a["asset_id"],
            "title": a["title"],
            "image_url": a["image_url"],
            "archetype": a["archetype"],
            "archetype_label": a["archetype_label"],
            "aesthetic_style_zh": a["aesthetic_style_zh"],
            "role": role,
            "max_medoid_sim": round(float(max_med_sim[idx]), 4),
            "contrast_axis": c.get("primary_axis"),
            "contrast_reason_zh": c.get("reason_zh", ""),
            "contrast_score": c.get("contrast_score", 0.0),
            "passes_pixel_contrast": bool(c.get("passes_contrast", False)),
            "low_personal_prior": bool(c.get("low_personal_prior", False)),
            "craft_confirmed": bool(craft_ok),
            "contrast_confirmed": contrast_ok,
            "user_confirmed": bool(craft_ok),  # backward-compat alias
        }

    for dom in DOMAINS_8:
        dom_indices = [i for i, a in enumerate(assets) if a.get("archetype") == dom]
        if not dom_indices:
            continue
        old_d = old_domains.get(dom, {})
        old_fam = old_d.get("familiar_anchor") or {}
        old_con = old_d.get("contrast_anchor") or {}

        # Preserve familiar anchor & its user confirmation
        fam_id = old_fam.get("asset_id")
        if fam_id and fam_id in ctx["id_to_idx"]:
            fam_idx = ctx["id_to_idx"][fam_id]
            fam_craft_ok = bool(old_fam.get("craft_confirmed", old_fam.get("user_confirmed", False)))
        else:
            pers = [i for i in dom_indices if assets[i].get("source_origin") == "pinterest_personal"]
            fam_pool = pers if pers else dom_indices
            fam_idx = max(fam_pool, key=lambda i: (int(assets[i].get("aesthetic_quality_score", 8)), float(max_med_sim[i])))
            fam_craft_ok = False

        # Re-select contrast anchor using v2.1 Pixel-Verifiable OKLab + 4x4 CV contrast!
        # Keep old contrast anchor ONLY if it actually passes pixel contrast AND was confirmed.
        old_con_id = old_con.get("asset_id")
        old_con_idx = ctx["id_to_idx"].get(old_con_id) if old_con_id else None
        old_con_confirmed = bool(old_con.get("craft_confirmed", old_con.get("user_confirmed", False)))
        if old_con_idx is not None and ct[old_con_idx].get("passes_contrast") and old_con_confirmed:
            con_idx = old_con_idx
            con_craft_ok = True
            con_contrast_ok = bool(old_con.get("contrast_confirmed", False))
        else:
            ranked_con = _ranked_contrast_candidates_for_domain(
                dom, assets[fam_idx]["asset_id"], assets[fam_idx].get("aesthetic_style", "")
            )
            con_idx = ranked_con[0] if ranked_con else fam_idx
            # Preserve prior confirmation status ONLY if same asset_id
            con_craft_ok = old_con_confirmed if (old_con_idx == con_idx) else False
            con_contrast_ok = False

        anchors_by_domain[dom] = {
            "domain": dom,
            "domain_label": assets[fam_idx].get("archetype_label", dom),
            "familiar_anchor": _pack(fam_idx, "familiar_reference", fam_craft_ok, None),
            "contrast_anchor": _pack(con_idx, "contrast_reference", con_craft_ok, con_contrast_ok),
        }

    payload = {
        "version": "2.1.0-completion-standards",
        "updated_at": _utc_now(),
        "domains": anchors_by_domain,
    }
    CRAFT_ANCHORS_V2_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def update_craft_anchor(
    domain: str,
    role: str,
    asset_id: str | None = None,
    confirmed: bool | None = None,
    craft_confirmed: bool | None = None,
    contrast_confirmed: bool | None = None,
    cycle_next: bool = False,
) -> dict[str, Any]:
    if domain not in DOMAINS_8:
        raise ValueError(f"Unknown domain: {domain}")
    if role not in {"familiar_anchor", "contrast_anchor"}:
        raise ValueError("role must be 'familiar_anchor' or 'contrast_anchor'")

    anchors = load_or_init_craft_anchors()
    dom_entry = anchors["domains"].get(domain)
    if not dom_entry:
        raise ValueError(f"Domain entry missing: {domain}")

    ctx = _load_corpus()
    profile = load_or_build_medoid_profile()
    M, _, _ = _medoid_matrix(profile, ctx)
    ct = ctx["contrast_table"]

    if cycle_next and role == "contrast_anchor":
        fam_id = dom_entry["familiar_anchor"]["asset_id"]
        fam_style = ctx["assets"][ctx["id_to_idx"][fam_id]].get("aesthetic_style", "")
        ranked = _ranked_contrast_candidates_for_domain(domain, fam_id, fam_style)[:12]
        if ranked:
            cur_id = dom_entry["contrast_anchor"]["asset_id"]
            cur_ids = [ctx["assets"][i]["asset_id"] for i in ranked]
            next_pos = (cur_ids.index(cur_id) + 1) % len(ranked) if cur_id in cur_ids else 0
            asset_id = cur_ids[next_pos]
            craft_confirmed = False
            contrast_confirmed = False

    if asset_id:
        idx = ctx["id_to_idx"].get(asset_id)
        if idx is None:
            raise ValueError(f"Unknown asset_id: {asset_id}")
        a = ctx["assets"][idx]
        c = ct[idx]
        sim = float((ctx["vecs"][idx] @ M.T).max())
        dom_entry[role] = {
            "asset_id": a["asset_id"],
            "title": a["title"],
            "image_url": a["image_url"],
            "archetype": a["archetype"],
            "archetype_label": a["archetype_label"],
            "aesthetic_style_zh": a["aesthetic_style_zh"],
            "role": "familiar_reference" if role == "familiar_anchor" else "contrast_reference",
            "max_medoid_sim": round(sim, 4),
            "contrast_axis": c.get("primary_axis"),
            "contrast_reason_zh": c.get("reason_zh", ""),
            "contrast_score": c.get("contrast_score", 0.0),
            "passes_pixel_contrast": bool(c.get("passes_contrast", False)),
            "low_personal_prior": bool(c.get("low_personal_prior", False)),
            "craft_confirmed": bool(craft_confirmed if craft_confirmed is not None else (confirmed or False)),
            "contrast_confirmed": (bool(contrast_confirmed) if contrast_confirmed is not None else False) if role == "contrast_anchor" else None,
            "user_confirmed": bool(craft_confirmed if craft_confirmed is not None else (confirmed or False)),
        }
    else:
        entry = dom_entry[role]
        if craft_confirmed is not None:
            entry["craft_confirmed"] = bool(craft_confirmed)
            entry["user_confirmed"] = bool(craft_confirmed)
        elif confirmed is not None:
            entry["craft_confirmed"] = bool(confirmed)
            entry["user_confirmed"] = bool(confirmed)
        if role == "contrast_anchor" and contrast_confirmed is not None:
            entry["contrast_confirmed"] = bool(contrast_confirmed)

    anchors["updated_at"] = _utc_now()
    with _STATE_LOCK:
        CRAFT_ANCHORS_V2_PATH.write_text(json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8")
    return anchors


def _pick_next_stratum(votes: list[dict[str, Any]], requested: str | None) -> str:
    if requested and requested in STRATUM_SPECS:
        return requested
    counts = Counter()
    for v in votes:
        if v.get("signal") != "core_taste":
            continue
        st = (v.get("meta") or {}).get("stratum")
        if st in STRATUM_SPECS:
            counts[st] += 1
    total = sum(counts.values()) + 1
    # Pick stratum with largest deficit (target_ratio - actual_ratio)
    return max(
        STRATUM_SPECS.keys(),
        key=lambda k: STRATUM_SPECS[k]["ratio"] - (counts[k] / total),
    )


def sample_next_calibration_pair(
    signal: str = "core_taste",
    stratum: str | None = None,
) -> dict[str, Any] | None:
    """Stratified 4-Type Q1 pair sampler (T1 25% / T2 35% / T3 20% / T4 20%) + Pixel-Contrast Q2 sampler."""
    ctx = _load_corpus()
    profile = load_or_build_medoid_profile()
    M, _, medoids = _medoid_matrix(profile, ctx)
    assets = ctx["assets"]
    vecs = ctx["vecs"]
    color_vec = ctx["color_vec"]
    grid_luma = ctx["grid_luma"]
    grid_edge = ctx["grid_edge"]
    comp_scalars = ctx["comp_scalars"]
    ct = ctx["contrast_table"]
    exp_idx = ctx["expansion_indices"]

    phi_all = vecs @ M.T
    max_med_sim = phi_all.max(axis=1)
    top_med_idx = phi_all.argmax(axis=1)

    votes = load_calibration_votes()
    seen_pairs = {
        tuple(sorted((v.get("asset_a", ""), v.get("asset_b", ""))))
        for v in votes
        if v.get("signal") == signal
    }
    rng = random.Random(int(time.time() * 1000) ^ (len(votes) * 31))

    enrich_assets = (ctx.get("personal_390_enrich") or {}).get("assets", {})
    species_map = ctx.get("species_map") or []

    def _pack_card(i: int, show_contrast_tag: bool = False) -> dict[str, Any]:
        a = assets[i]
        c = ct[i]
        en = enrich_assets.get(a["asset_id"], {})
        sp_i, st_i = species_map[i] if i < len(species_map) else ("spatial_photography", "single_unified")
        return {
            "asset_id": a["asset_id"],
            "title": a["title"],
            "image_url": a["image_url"],
            "source_origin": a.get("source_origin", ""),
            "archetype": a["archetype"],
            "archetype_label": a["archetype_label"],
            "aesthetic_style_zh": a["aesthetic_style_zh"],
            "typology": (a.get("rag_facets") or {}).get("typology", ""),
            "max_medoid_sim": round(float(max_med_sim[i]), 4),
            "nearest_medoid_id": medoids[int(top_med_idx[i])]["medoid_id"],
            "contrast_axis": c.get("primary_axis") if show_contrast_tag else None,
            "contrast_reason_zh": c.get("reason_zh", "") if show_contrast_tag else "",
            "image_species": sp_i,
            "subject_structure": st_i,
            "primary_family_zh": en.get("primary_family_zh", ""),
            "secondary_family_zh": en.get("secondary_family_zh", ""),
            "overarching_principle": en.get("overarching_principle", ""),
            "candidate_reasons": en.get("candidate_reasons", [])[:4],
        }

    if signal == "core_taste":
        chosen_stratum = _pick_next_stratum(votes, stratum)
        spec = STRATUM_SPECS[chosen_stratum]
        dom_order = list(DOMAINS_8)
        rng.shuffle(dom_order)

        def _valid_pair(ia: int, ib: int, avoid_both_personal: bool = True) -> bool:
            if ia == ib:
                return False
            # Respect 390 personal pins as already-liked prior: avoid needlessly re-voting two personal pins against each other
            if (
                avoid_both_personal
                and assets[ia].get("source_origin") == "pinterest_personal"
                and assets[ib].get("source_origin") == "pinterest_personal"
            ):
                return False
            key = tuple(sorted((assets[ia]["asset_id"], assets[ib]["asset_id"])))
            if key in seen_pairs:
                return False
            # Exclude near-duplicates
            if float(vecs[ia] @ vecs[ib]) > 0.89:
                return False
            return True

        found: tuple[int, int, str] | None = None

        for dom in dom_order:
            pool = [i for i, a in enumerate(assets) if a.get("archetype") == dom and int(a.get("aesthetic_quality_score", 0)) >= 8]
            if len(pool) < 6:
                continue
            rng.shuffle(pool)

            if chosen_stratum == "T1_macro_style":
                # Same domain, matched quality & medium (when possible), DIFFERENT aesthetic_style
                for ia in pool[:35]:
                    a1 = assets[ia]
                    m1 = (a1.get("rag_facets") or {}).get("medium", "")
                    q1 = int(a1.get("aesthetic_quality_score", 8))
                    cands = [
                        ib
                        for ib in pool[:80]
                        if _valid_pair(ia, ib)
                        and assets[ib].get("aesthetic_style") != a1.get("aesthetic_style")
                        and abs(int(assets[ib].get("aesthetic_quality_score", 8)) - q1) <= 1
                    ]
                    same_med = [ib for ib in cands if (assets[ib].get("rag_facets") or {}).get("medium", "") == m1]
                    picks = same_med if same_med else cands
                    if picks:
                        ib = rng.choice(picks[:10])
                        found = (ia, ib, f"固定门类「{a1['archetype_label']}」，对比风格：{a1['aesthetic_style_zh']} vs {assets[ib]['aesthetic_style_zh']}")
                        break

            elif chosen_stratum == "T2_same_style_instance":
                # Same domain + SAME aesthetic_style (+ prefer same typology), distinct instances
                by_style: dict[str, list[int]] = defaultdict(list)
                for i in pool:
                    by_style[assets[i].get("aesthetic_style", "")].append(i)
                styles = [s for s, idxs in by_style.items() if len(idxs) >= 2]
                rng.shuffle(styles)
                for st in styles:
                    idxs = by_style[st]
                    for ia in idxs[:20]:
                        t1 = (assets[ia].get("rag_facets") or {}).get("typology", "")
                        cands = [ib for ib in idxs if _valid_pair(ia, ib)]
                        same_typ = [ib for ib in cands if (assets[ib].get("rag_facets") or {}).get("typology", "") == t1]
                        picks = same_typ if same_typ else cands
                        if picks:
                            ib = rng.choice(picks[:10])
                            found = (ia, ib, f"锁定「{assets[ia]['archetype_label']} · {assets[ia]['aesthetic_style_zh']}」，比较两件实例的执行细节")
                            break
                    if found:
                        break

            elif chosen_stratum == "T3_same_subject_treatment":
                # Same domain + typology: close composition/lightness (bottom 30%), top-25% color/lighting treatment diff
                by_typ: dict[str, list[int]] = defaultdict(list)
                for i in pool:
                    typ = (assets[i].get("rag_facets") or {}).get("typology", "")
                    if typ:
                        by_typ[typ].append(i)
                typs = [t for t, idxs in by_typ.items() if len(idxs) >= 6]
                rng.shuffle(typs)
                for typ in typs[:8]:
                    idxs = by_typ[typ][:40]
                    arr = np.asarray(idxs, dtype=np.int32)
                    gl_d = np.linalg.norm(grid_luma[arr][:, None, :] - grid_luma[arr][None, :, :], axis=2)
                    lm_d = np.abs(color_vec[arr, 0:1] - color_vec[arr][None, :, 0])
                    base_d = gl_d + 1.5 * lm_d
                    col_d, _, _, _ = _compute_color_dist_matrix(color_vec[arr], color_vec[arr])
                    lspan_d = np.abs(color_vec[arr, 1:2] - color_vec[arr][None, :, 1])
                    treat_d = col_d + 2.0 * lspan_d

                    tri = np.triu_indices(len(arr), k=1)
                    b_cut = float(np.percentile(base_d[tri], 30))
                    t_cut = float(np.percentile(treat_d[tri], 75))
                    matches = []
                    for r_i, c_i in zip(tri[0].tolist(), tri[1].tolist()):
                        if base_d[r_i, c_i] <= b_cut and treat_d[r_i, c_i] >= t_cut:
                            ia, ib = idxs[r_i], idxs[c_i]
                            if _valid_pair(ia, ib):
                                matches.append((float(treat_d[r_i, c_i]), ia, ib))
                    if matches:
                        matches.sort(key=lambda x: -x[0])
                        _, ia, ib = rng.choice(matches[:6])
                        found = (ia, ib, f"同品类「{typ}」· 相近构图明度，放大配色/光影处理差异（近似对照）")
                        break

            elif chosen_stratum == "T4_same_comp_material_or_subject":
                # Same domain: 4x4 layout (grid_luma + grid_edge + aspect) in bottom 25%, materials/typology different!
                sub = pool[:55]
                arr = np.asarray(sub, dtype=np.int32)
                gl_d = np.linalg.norm(grid_luma[arr][:, None, :] - grid_luma[arr][None, :, :], axis=2)
                ge_d = np.linalg.norm(grid_edge[arr][:, None, :] - grid_edge[arr][None, :, :], axis=2)
                asp_d = np.abs(comp_scalars[arr, 3:4] - comp_scalars[arr][None, :, 3])
                comp_prox = gl_d + 2.5 * ge_d + 0.8 * asp_d
                tri = np.triu_indices(len(arr), k=1)
                c_cut = float(np.percentile(comp_prox[tri], 25))
                matches = []
                for r_i, c_i in zip(tri[0].tolist(), tri[1].tolist()):
                    if comp_prox[r_i, c_i] > c_cut:
                        continue
                    ia, ib = sub[r_i], sub[c_i]
                    if not _valid_pair(ia, ib):
                        continue
                    mat_a = set((assets[ia].get("rag_facets") or {}).get("materials") or [])
                    mat_b = set((assets[ib].get("rag_facets") or {}).get("materials") or [])
                    typ_a = (assets[ia].get("rag_facets") or {}).get("typology", "")
                    typ_b = (assets[ib].get("rag_facets") or {}).get("typology", "")
                    mat_overlap = len(mat_a & mat_b) / max(1, len(mat_a | mat_b))
                    if mat_overlap <= 0.25 or typ_a != typ_b:
                        matches.append((float(comp_prox[r_i, c_i]), ia, ib))
                if matches:
                    matches.sort(key=lambda x: x[0])
                    _, ia, ib = rng.choice(matches[:8])
                    found = (ia, ib, f"同门类「{assets[ia]['archetype_label']}」· 4×4 构图与画幅近邻，切换材质/主体（近似对照）")
                    break

            if found:
                break

        if found is None:
            return None
        ia, ib, control_note = found
        if rng.random() < 0.5:
            ia, ib = ib, ia
        return {
            "signal": "core_taste",
            "stratum": chosen_stratum,
            "stratum_badge_zh": spec["badge_zh"],
            "question_zh": spec["question_zh"],
            "hint_zh": control_note,
            "a": _pack_card(ia, show_contrast_tag=False),
            "b": _pack_card(ib, show_contrast_tag=False),
        }

    # Q2: `serendipity_save` — strictly pixel-verified contrast pairs within SAME domain!
    dom_order = list(DOMAINS_8)
    rng.shuffle(dom_order)
    for dom in dom_order:
        c_pool = [
            i
            for i in exp_idx
            if assets[i].get("archetype") == dom
            and ct[i].get("passes_contrast")
            and int(assets[i].get("aesthetic_quality_score", 0)) >= 8
        ]
        if len(c_pool) < 2:
            continue
        rng.shuffle(c_pool)
        for idx_a in range(min(20, len(c_pool))):
            ia = c_pool[idx_a]
            for idx_b in range(idx_a + 1, min(30, len(c_pool))):
                ib = c_pool[idx_b]
                key = tuple(sorted((assets[ia]["asset_id"], assets[ib]["asset_id"])))
                if key in seen_pairs or float(vecs[ia] @ vecs[ib]) > 0.85:
                    continue
                if rng.random() < 0.5:
                    ia, ib = ib, ia
                return {
                    "signal": "serendipity_save",
                    "stratum": "Q2_pixel_contrast",
                    "stratum_badge_zh": f"破圈探索 · {assets[ia]['archetype_label']}像素反差候选",
                    "question_zh": "哪张虽然风格陌生/有反差，但你仍愿意收藏？",
                    "hint_zh": "仅从 OKLab 色彩/4×4 构图反差 ≥P90 池中同域抽样；独立记录，绝不污染核心口味模型",
                    "a": _pack_card(ia, show_contrast_tag=True),
                    "b": _pack_card(ib, show_contrast_tag=True),
                }
    return None


def _build_aesthetic_families_summary(
    ctx: dict[str, Any],
    votes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build 7 cross-board Personal Aesthetic Families summary + live user reason convergence (retaining tie_like!)."""
    enrich = ctx.get("personal_390_enrich") or {}
    fams_meta: list[dict[str, Any]] = enrich.get("families", [])
    enrich_assets: dict[str, dict[str, Any]] = enrich.get("assets", {})
    assets = ctx["assets"]
    id_to_idx = ctx["id_to_idx"]

    fam_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tension_counts: Counter[tuple[str, str]] = Counter()
    noise_count = 0

    for aid, info in enrich_assets.items():
        if info.get("is_pragmatic_noise"):
            noise_count += 1
        pf = str(info.get("primary_family", ""))
        sf = str(info.get("secondary_family", ""))
        if pf and aid in id_to_idx:
            a = assets[id_to_idx[aid]]
            fam_buckets[pf].append(
                {
                    "asset_id": aid,
                    "title": a.get("title", aid),
                    "image_url": a.get("image_url", ""),
                    "board_name": a.get("board_name", ""),
                    "secondary_family_zh": info.get("secondary_family_zh", ""),
                    "verdict_why": info.get("verdict_why", ""),
                    "overarching_principle": info.get("overarching_principle", ""),
                    "res_score": float(info.get("aesthetic_resonance_score", 0.0)),
                }
            )
        if pf and sf:
            pair = tuple(sorted((pf, sf)))
            tension_counts[pair] += 1

    fam_by_key = {f["k"]: f for f in fams_meta}
    total_pins = max(1, len(enrich_assets))
    family_cards: list[dict[str, Any]] = []
    for f in fams_meta:
        k = f["k"]
        items = sorted(fam_buckets.get(k, []), key=lambda x: -x["res_score"])
        family_cards.append(
            {
                "key": k,
                "num": f.get("num", ""),
                "name": f.get("name", k),
                "short": f.get("short", k),
                "desc": f.get("desc", ""),
                "count": len(items),
                "pct": round(len(items) / total_pins * 100.0, 1),
                "samples": items[:4],
            }
        )
    family_cards.sort(key=lambda x: -x["count"])

    top_tensions = [
        {
            "pair": f"{fam_by_key[a]['short']} × {fam_by_key[b]['short']}",
            "count": c,
        }
        for (a, b), c in tension_counts.most_common(6)
        if a in fam_by_key and b in fam_by_key
    ]

    # Aggregate user-chosen reasons across Q1 (a/b AND tie_like!) + Q2 (a/b/both)
    reason_counts: Counter[str] = Counter()
    tie_like_reason_votes = 0
    total_reason_votes = 0
    recent_notes: list[dict[str, str]] = []
    for v in votes:
        ch = v.get("choice", "")
        if ch in {"cannot_compare", "skip", "neither"}:
            continue
        reasons = v.get("chosen_reasons") or (v.get("meta") or {}).get("chosen_reasons") or []
        note = v.get("reason_note") or (v.get("meta") or {}).get("reason_note") or ""
        if reasons:
            total_reason_votes += 1
            if ch in {"tie_like", "both"}:
                tie_like_reason_votes += 1
            for r in reasons:
                reason_counts[str(r)] += 1
        if note:
            recent_notes.append(
                {
                    "asset_a": str(v.get("asset_a", "")),
                    "asset_b": str(v.get("asset_b", "")),
                    "choice": str(ch),
                    "note": str(note),
                }
            )

    return {
        "total_personal_pins": len(enrich_assets),
        "pragmatic_noise_count": noise_count,
        "families": family_cards,
        "top_tensions": top_tensions,
        "reason_chips": REASON_ATTRACTOR_CHIPS,
        "reason_attribution": {
            "total_votes_with_reasons": total_reason_votes,
            "tie_like_votes_with_reasons": tie_like_reason_votes,
            "top_reasons": [{"label": k, "count": c} for k, c in reason_counts.most_common(10)],
            "recent_notes": recent_notes[-6:][::-1],
        },
    }


def get_calibration_state(requested_stratum: str | None = None) -> dict[str, Any]:
    """Return full v2.1 live state for the local Taste Calibration Bench UI."""
    ctx = _load_corpus()
    profile = load_or_build_medoid_profile()
    anchors = load_or_init_craft_anchors()
    rerank = rerank_three_lanes(target_total=1110)
    votes = load_calibration_votes()
    core_votes = [v for v in votes if v.get("signal") == "core_taste"]
    serend_votes = [v for v in votes if v.get("signal") == "serendipity_save"]
    bt = rerank["bt_model"]

    confirmed_craft = sum(
        int(bool(d["familiar_anchor"].get("craft_confirmed")))
        + int(bool(d["contrast_anchor"].get("craft_confirmed")))
        for d in anchors.get("domains", {}).values()
    )
    confirmed_contrast = sum(
        int(bool(d["contrast_anchor"].get("contrast_confirmed")))
        for d in anchors.get("domains", {}).values()
    )
    total_anchors = len(anchors.get("domains", {})) * 2
    return {
        "version": "2.1.0",
        "profile": profile,
        "anchors": anchors,
        "confirmed_anchors": confirmed_craft,
        "confirmed_contrast": confirmed_contrast,
        "total_anchors": total_anchors,
        "total_contrast_anchors": len(anchors.get("domains", {})),
        "stratum_specs": STRATUM_SPECS,
        "aesthetic_families": _build_aesthetic_families_summary(ctx, votes),
        "vote_counts": {
            "core_taste_total": len(core_votes),
            "core_taste_stratified": bt["n_stratified_pairs"],
            "legacy_cross_domain_diagnostic": bt["legacy_cross_domain_diagnostic"],
            "tie_like_count": bt["tie_like_count"],
            "cannot_compare_count": bt["cannot_compare_count"],
            "stratum_counts": bt["stratum_counts"],
            "serendipity_total": len(serend_votes),
            "serendipity_saved": sum(1 for v in serend_votes if v.get("choice") in {"a", "b", "both"}),
            "trial_budget_target": 60,
        },
        "rerank_summary": rerank,
        "next_core_pair": sample_next_calibration_pair("core_taste", stratum=requested_stratum),
        "next_serendipity_pair": sample_next_calibration_pair("serendipity_save"),
    }


if __name__ == "__main__":
    prof = build_medoid_profile(k=DEFAULT_MEDOID_K, persist=True)
    anc = load_or_init_craft_anchors()
    rr = rerank_three_lanes(target_total=1110)
    print(f"v2.1 Medoids K={prof['k_medoids']} | Rerank latency={rr['latency_ms']}ms | lanes={rr['lane_counts']}")
    for dom, d in anc["domains"].items():
        c = d["contrast_anchor"]
        print(f"  [{d['domain_label']}] CON: {c['asset_id']} | {c['title']} | {c['contrast_reason_zh']} (pass={c['passes_pixel_contrast']})")
