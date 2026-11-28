"""Deterministic Pixel Visual Feature Extractor v2.1 (OKLab Color + 4x4 CV Composition).

Extracts fast, zero-LLM, human-verifiable visual descriptors for all 1,500 personal atlas
images and caches them into `data/pinterest_500/visual_features_1500.npz`:
- OKLab color descriptors: L_median, L_span (P90-P10), C_p90, high_chroma_ratio (C>0.10),
  a_mean, b_mean, chromatic circular hue vector (cos_h, sin_h, chromatic_ratio for C>0.04).
- 4x4 spatial composition descriptors: 16-dim normalized luminance grid, 16-dim Sobel edge
  density grid, global edge_density, 8-bin gradient orientation_entropy, negative_space_ratio,
  and log(aspect_ratio).
- 5-dim micro execution vector `z_raw`: [color_richness, color_warmth, luma_span,
  negative_space, texture_edge_complexity] used by the 7-parameter Hierarchical Bradley-Terry head.
"""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "pinterest_500"
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
VISUAL_FEAT_NPZ = DATA_DIR / "visual_features_1500.npz"


def _srgb_to_oklab(rgb01: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact Björn Ottosson sRGB [0,1] -> OKLab (L, a, b)."""
    lin = np.where(
        rgb01 <= 0.04045,
        rgb01 / 12.92,
        np.power(np.clip((rgb01 + 0.055) / 1.055, 0.0, 1.0), 2.4),
    )
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_c = np.cbrt(np.maximum(l_, 0.0))
    m_c = np.cbrt(np.maximum(m_, 0.0))
    s_c = np.cbrt(np.maximum(s_, 0.0))

    L = 0.2104542553 * l_c + 0.7936177850 * m_c - 0.0040720468 * s_c
    a = 1.9779984951 * l_c - 2.4285922050 * m_c + 0.4505937099 * s_c
    b_ok = 0.0259040371 * l_c + 0.7827717662 * m_c - 0.8086757660 * s_c
    return L, a, b_ok


def extract_one_image_features(img_path: Path) -> dict[str, Any]:
    """Extract deterministic OKLab + 4x4 composition features from a single image."""
    with Image.open(img_path) as im:
        w, h = im.size
        rgb_small = im.convert("RGB").resize((128, 128), Image.Resampling.BILINEAR)
    arr = np.asarray(rgb_small, dtype=np.float32) / 255.0
    L, a, b = _srgb_to_oklab(arr)
    C = np.sqrt(a * a + b * b)

    l_med = float(np.median(L))
    l_p10 = float(np.percentile(L, 10))
    l_p90 = float(np.percentile(L, 90))
    l_span = l_p90 - l_p10
    c_p90 = float(np.percentile(C, 90))
    c_med = float(np.median(C))
    high_chroma_ratio = float(np.mean(C > 0.10))
    a_mean = float(np.mean(a))
    b_mean = float(np.mean(b))

    # Circular chromatic hue vector computed ONLY on chromatic pixels (C > 0.04)
    chroma_mask = C > 0.04
    chromatic_ratio = float(np.mean(chroma_mask))
    if np.any(chroma_mask):
        weights = C[chroma_mask]
        hues = np.arctan2(b[chroma_mask], a[chroma_mask])
        w_sum = float(np.sum(weights)) + 1e-8
        hue_cos = float(np.sum(weights * np.cos(hues)) / w_sum)
        hue_sin = float(np.sum(weights * np.sin(hues)) / w_sum)
    else:
        hue_cos, hue_sin = 0.0, 0.0

    # 4x4 luminance grid & Sobel edge density/orientation on L channel (128x128)
    gx = np.zeros_like(L)
    gy = np.zeros_like(L)
    gx[:, 1:-1] = (L[:, 2:] - L[:, :-2]) * 0.5
    gy[1:-1, :] = (L[2:, :] - L[:-2, :]) * 0.5
    mag = np.sqrt(gx * gx + gy * gy)

    edge_density = float(np.mean(mag))
    # 8-bin gradient orientation entropy (in [0, 1]) over active edge pixels
    edge_mask = mag > max(0.02, float(np.percentile(mag, 65)))
    if np.any(edge_mask):
        ang = (np.arctan2(gy[edge_mask], gx[edge_mask]) + math.pi) % math.pi  # undirected [0, pi)
        hist, _ = np.histogram(ang, bins=8, range=(0.0, math.pi), weights=mag[edge_mask])
        p = hist / (float(hist.sum()) + 1e-8)
        p_nz = p[p > 0]
        orient_entropy = float(-np.sum(p_nz * np.log(p_nz)) / math.log(8.0))
    else:
        orient_entropy = 0.0

    # 4x4 spatial blocks (each 32x32)
    L_blocks = L.reshape(4, 32, 4, 32).transpose(0, 2, 1, 3)  # (4, 4, 32, 32)
    M_blocks = mag.reshape(4, 32, 4, 32).transpose(0, 2, 1, 3)
    grid_luma = L_blocks.mean(axis=(2, 3)).reshape(16).astype(np.float32)
    grid_edge = M_blocks.mean(axis=(2, 3)).reshape(16).astype(np.float32)
    # Negative space ratio: fraction of 16 spatial tiles that are calm/low-edge
    neg_space_ratio = float(np.mean(grid_edge < 0.025))
    aspect_log = float(math.log(max(1.0, float(w)) / max(1.0, float(h))))

    # Color vector (8-dim) for deterministic OKLab contrast calculation
    color_vec = np.asarray(
        [l_med, l_span, c_med, c_p90, high_chroma_ratio, chromatic_ratio, hue_cos, hue_sin],
        dtype=np.float32,
    )
    # 5-dim micro execution vector (raw, to be centered within (domain, style) in BT)
    z_raw = np.asarray(
        [
            c_p90 + 0.5 * high_chroma_ratio,          # z0: color saturation / chromatic richness
            a_mean + 0.7 * b_mean,                    # z1: color warmth polarity
            l_span,                                   # z2: luminance dynamic range
            neg_space_ratio,                          # z3: composition negative space / breathing room
            edge_density + 0.25 * orient_entropy,     # z4: local texture & edge complexity
        ],
        dtype=np.float32,
    )
    return {
        "color_vec": color_vec,
        "grid_luma": grid_luma,
        "grid_edge": grid_edge,
        "comp_scalars": np.asarray([edge_density, orient_entropy, neg_space_ratio, aspect_log], dtype=np.float32),
        "z_raw": z_raw,
    }


def build_visual_features_cache(force: bool = False) -> dict[str, np.ndarray]:
    """Compute or load cached OKLab + 4x4 CV features for all assets in `aethervault_personal_500.json`."""
    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]
    asset_ids = [a["asset_id"] for a in assets]

    if not force and VISUAL_FEAT_NPZ.is_file():
        data = np.load(VISUAL_FEAT_NPZ, allow_pickle=False)
        cached_ids = [str(x) for x in data["asset_ids"].tolist()]
        if cached_ids == asset_ids:
            return {k: data[k] for k in data.files}

    t0 = time.perf_counter()
    paths = [WEB_PUBLIC_DIR / a["image_url"].lstrip("/") for a in assets]
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(extract_one_image_features, paths))

    out = {
        "asset_ids": np.asarray(asset_ids),
        "color_vec": np.stack([r["color_vec"] for r in results], axis=0).astype(np.float32),
        "grid_luma": np.stack([r["grid_luma"] for r in results], axis=0).astype(np.float32),
        "grid_edge": np.stack([r["grid_edge"] for r in results], axis=0).astype(np.float32),
        "comp_scalars": np.stack([r["comp_scalars"] for r in results], axis=0).astype(np.float32),
        "z_raw": np.stack([r["z_raw"] for r in results], axis=0).astype(np.float32),
    }
    np.savez_compressed(VISUAL_FEAT_NPZ, **out)
    print(f"Extracted OKLab + 4x4 CV features for {len(asset_ids)} images in {time.perf_counter()-t0:.2f}s -> {VISUAL_FEAT_NPZ}")
    return out


if __name__ == "__main__":
    feats = build_visual_features_cache(force=True)
    print("Shapes:", {k: v.shape for k, v in feats.items()})
    # Verify landscape regression pair: pin_arch_027 vs pext4_land_663
    ids = [str(x) for x in feats["asset_ids"].tolist()]
    if "pin_arch_027" in ids and "pext4_land_663" in ids:
        i1, i2 = ids.index("pin_arch_027"), ids.index("pext4_land_663")
        c1, c2 = feats["color_vec"][i1], feats["color_vec"][i2]
        print(f"pin_arch_027  : L_med={c1[0]:.3f} L_span={c1[1]:.3f} C_p90={c1[3]:.4f} highC={c1[4]:.3f}")
        print(f"pext4_land_663: L_med={c2[0]:.3f} L_span={c2[1]:.3f} C_p90={c2[3]:.4f} highC={c2[4]:.3f}")
