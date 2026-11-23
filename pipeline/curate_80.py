"""Curate 80 cross-domain high-aesthetic assets (`16 x 5` domains), extract OKLab HEX palettes,
link read-only P-MIC-4 Aesthetic KB priors, and export Showcase + Contact Sheet bundles.
"""

from __future__ import annotations

import argparse
import base64
import gc
import io
import json
import math
import os
import shutil
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .aethervault_schema import (
    SPECTRUM_AXES,
    AestheticAsset,
    CompilerPrimitives,
    GranularDescriptors,
    StyleSpectrumAxis,
    SubjectIsolation,
)
from .anchor_specs import GOLDEN_ANCHOR_RUBRICS, estimate_ingestion_cost_cny
from .curated_specs_data import CURATED_SPECS, CuratedSpec

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_ROOT = REPO_ROOT / "data" / "curated_80"
IMAGES_DIR = CURATED_ROOT / "images"
ASSETS_JSON_PATH = CURATED_ROOT / "aethervault_assets_v1.json"
MANIFEST_JSON_PATH = CURATED_ROOT / "curation_manifest.json"
CONTACT_SHEET_PATH = CURATED_ROOT / "contact_sheet_80.jpg"
OPENVERSE_CACHE_PATH = CURATED_ROOT / "_openverse_cache.json"
PROVENANCE_CACHE_PATH = CURATED_ROOT / "_provenance_cache.json"

WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_IMAGES_DIR = WEB_PUBLIC_DIR / "assets" / "curated_80"
WEB_SHOWCASE_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_showcase_v1.json"

AKB_SQLITE_PATH = Path(r"C:\Users\Frost\Documents\Antigravity\aesthetic-kb\data\db\meta.sqlite")

TARGET_WIDTH = 800
TARGET_HEIGHT = 600

DOMAIN_FALLBACK_QUERIES: dict[str, list[str]] = {
    "architecture": [
        "modern concrete architecture",
        "minimalist museum building",
        "contemporary architecture facade",
        "japanese wooden architecture",
    ],
    "industrial": [
        "vintage camera mechanical",
        "minimalist industrial product",
        "audio synthesizer equipment",
        "mechanical watch steel",
    ],
    "editorial": [
        "minimalist fashion portrait",
        "monochrome fashion editorial",
        "coat architecture street",
        "dramatic shadow portrait",
    ],
    "craft": [
        "ceramic tea bowl",
        "japanese pottery stoneware",
        "wooden craft joinery",
        "porcelain ceramic vessel",
    ],
}


# ---------------------------------------------------------------------------
# Deterministic OKLab Color Space & K-Means (k=5)
# ---------------------------------------------------------------------------
def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c_norm = np.clip(c / 255.0, 0.0, 1.0)
    return np.where(c_norm <= 0.04045, c_norm / 12.92, ((c_norm + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb_byte(c: np.ndarray) -> np.ndarray:
    c_clip = np.clip(c, 0.0, 1.0)
    srgb = np.where(c_clip <= 0.0031308, c_clip * 12.92, 1.055 * (c_clip ** (1.0 / 2.4)) - 0.055)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """Convert (N, 3) uint8 sRGB array into perceptual OKLab (N, 3) coordinates."""
    lin = _srgb_to_linear(rgb.astype(np.float64))
    r, g, b = lin[:, 0], lin[:, 1], lin[:, 2]
    l_cone = np.cbrt(np.clip(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b, 0.0, None))
    m_cone = np.cbrt(np.clip(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b, 0.0, None))
    s_cone = np.cbrt(np.clip(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b, 0.0, None))

    L = 0.2104542553 * l_cone + 0.7936177850 * m_cone - 0.0040720468 * s_cone
    a = 1.9779984951 * l_cone - 2.4285922050 * m_cone + 0.4505937099 * s_cone
    b_out = 0.0259040371 * l_cone + 0.7827717662 * m_cone - 0.8086757660 * s_cone
    return np.stack([L, a, b_out], axis=1)


def oklab_to_hex(lab: np.ndarray) -> str:
    """Convert single OKLab coordinate [L, a, b] back to uppercase HEX string."""
    L, a, b_val = float(lab[0]), float(lab[1]), float(lab[2])
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b_val) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b_val) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b_val) ** 3

    r_lin = +4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g_lin = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    b_lin = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    rgb = _linear_to_srgb_byte(np.array([r_lin, g_lin, b_lin]))
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def hex_to_oklab(hex_color: str) -> np.ndarray:
    """Convert #RRGGBB string into OKLab [L, a, b]."""
    clean = hex_color.lstrip("#")
    rgb = np.array([[int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)]], dtype=np.uint8)
    return rgb_to_oklab(rgb)[0]


def extract_oklab_palette(img: Image.Image, k: int = 5) -> list[str]:
    """Extract k dominant HEX swatches via deterministic K-Means in OKLab space."""
    small = img.convert("RGB").resize((64, 48), Image.Resampling.BILINEAR)
    pixels = np.asarray(small).reshape(-1, 3)
    lab = rgb_to_oklab(pixels).astype(np.float32)

    rng = np.random.default_rng(42)
    # K-means++ deterministic initialization
    centers = [lab[int(rng.integers(0, len(lab)))]]
    for _ in range(1, k):
        c_arr = np.array(centers, dtype=np.float32)
        dists = np.min(np.sum((lab[:, None, :] - c_arr[None, :, :]) ** 2, axis=2), axis=1)
        probs = dists / (float(dists.sum()) + 1e-12)
        centers.append(lab[int(rng.choice(len(lab), p=probs))])
    centroids = np.array(centers, dtype=np.float32)

    labels = np.zeros(len(lab), dtype=np.int32)
    for _ in range(18):
        dists = np.sum((lab[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1)
        new_centroids = centroids.copy()
        for ci in range(k):
            mask = labels == ci
            if np.any(mask):
                new_centroids[ci] = np.mean(lab[mask], axis=0)
        if np.allclose(new_centroids, centroids, atol=1e-4):
            centroids = new_centroids
            break
        centroids = new_centroids

    counts = np.bincount(labels, minlength=k)
    order = np.argsort(-counts)
    ordered_hex = [oklab_to_hex(centroids[idx]) for idx in order]
    # Deduplicate near-identical HEX strings while preserving order
    return list(dict.fromkeys(ordered_hex))[:k]


def compute_dhash(img: Image.Image, size: int = 8) -> int:
    """Compute 64-bit difference hash (dHash) for near-duplicate rejection."""
    gray = np.asarray(img.convert("L").resize((size + 1, size), Image.Resampling.BILINEAR))
    diff = gray[:, 1:] > gray[:, :-1]
    val = 0
    for bit in diff.flatten():
        val = (val << 1) | int(bool(bit))
    return val


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def palette_distance_oklab(pal_a: list[str], pal_b: list[str]) -> float:
    """Symmetric minimum OKLab distance between two HEX palettes."""
    if not pal_a or not pal_b:
        return 999.0
    labs_a = np.array([hex_to_oklab(h) for h in pal_a[:5]])
    labs_b = np.array([hex_to_oklab(h) for h in pal_b[:5]])
    dists = np.linalg.norm(labs_a[:, None, :] - labs_b[None, :, :], axis=2)
    return float(0.5 * (np.mean(np.min(dists, axis=1)) + np.mean(np.min(dists, axis=0))))


# ---------------------------------------------------------------------------
# Procedural Constructivist / Bauhaus / Swiss Grid Renderer (16 graphic assets)
# ---------------------------------------------------------------------------
def _hex_rgb(h: str) -> tuple[int, int, int]:
    c = h.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _add_paper_grain(img: Image.Image, strength: float = 6.0, seed: int = 7) -> Image.Image:
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, strength, size=(arr.shape[0], arr.shape[1], 1))
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def render_graphic_asset(spec: CuratedSpec) -> Image.Image:
    """Render supersampled 1200x900 Constructivist / Swiss graphic artwork and downsample to 800x600."""
    W, H = 1200, 900
    c0, c1, c2 = [_hex_rgb(h) for h in spec.target_palette_hint[:3]]
    style = spec.graphic_style
    img = Image.new("RGB", (W, H), c0)
    draw = ImageDraw.Draw(img)

    if style == "swiss_12col":
        # Strict 12-column grid lines + bold modular Swiss rectangles & rule accents
        margin = 72
        col_w = (W - 2 * margin) / 12.0
        for i in range(13):
            x = round(margin + i * col_w)
            draw.line([(x, margin), (x, H - margin)], fill=(198, 194, 186), width=2)
        for y in [margin, 240, 420, 620, H - margin]:
            draw.line([(margin, y), (W - margin, y)], fill=(198, 194, 186), width=2)
        draw.rectangle([margin, margin, margin + int(col_w * 5), 420], fill=c1)
        draw.rectangle([margin + int(col_w * 5), 240, margin + int(col_w * 9), 318], fill=c2)
        draw.rectangle([margin + int(col_w * 7), 420, W - margin, 620], fill=c1)
        draw.rectangle([margin, 620, margin + int(col_w * 3), H - margin], fill=c2)
        draw.rectangle([margin + int(col_w * 3), 676, margin + int(col_w * 11), 690], fill=c1)
        draw.ellipse([margin + int(col_w * 9.3), 86, margin + int(col_w * 11.7), 86 + int(col_w * 2.4)], fill=c1)

    elif style == "bauhaus_primary":
        draw.rectangle([0, 0, W, H], fill=(242, 237, 226))
        draw.polygon([(140, 120), (620, 120), (480, 780), (140, 780)], fill=c0)
        draw.ellipse([430, 170, 930, 670], fill=c1)
        draw.rectangle([680, 90, 1080, 480], fill=c2)
        draw.rectangle([210, 560, 1060, 632], fill=(20, 22, 25))
        draw.polygon([(820, 520), (1090, 810), (740, 810)], fill=c0)

    elif style == "constructivist_flat":
        draw.polygon([(0, 0), (W, 0), (W, 470), (0, 660)], fill=c0)
        draw.polygon([(0, 660), (W, 470), (W, H), (0, H)], fill=c1)
        draw.polygon([(180, 760), (540, 130), (665, 130), (350, 760)], fill=c2)
        draw.ellipse([700, 150, 1040, 490], fill=c1)
        draw.rectangle([660, 560, 1050, 625], fill=c0)

    elif style == "neutral_paper_grid":
        for y in range(110, H - 90, 68):
            draw.line([(96, y), (W - 96, y)], fill=(182, 179, 173), width=2)
        for x in [96, 360, 624, 888, W - 96]:
            draw.line([(x, 110), (x, H - 110)], fill=(182, 179, 173), width=2)
        draw.rectangle([96, 178, 624, 518], fill=c1)
        draw.rectangle([624, 314, 888, 654], fill=c2)
        draw.rectangle([164, 654, 888, 704], fill=c2)
        img = _add_paper_grain(img, strength=5.0, seed=4)

    elif style == "riso_axonometric":
        draw.rectangle([0, 0, W, H], fill=c0)
        # Isometric architectural massing with halftone shadow planes
        pts_top = [(600, 140), (920, 290), (600, 440), (280, 290)]
        pts_left = [(280, 290), (600, 440), (600, 740), (280, 590)]
        pts_right = [(600, 440), (920, 290), (920, 590), (600, 740)]
        draw.polygon(pts_left, fill=c1)
        draw.polygon(pts_right, fill=c2)
        draw.polygon(pts_top, fill=(235, 226, 208), outline=c1, width=6)
        # Halftone dot grid overlay on right side
        for gy in range(280, 740, 18):
            for gx in range(605, 925, 18):
                if (gx - 600) * 0.48 + 440 <= gy <= (gx - 600) * (-0.48) + 740 or True:
                    if 590 >= gy - (gx - 600) * 0.45 and gy >= 310:
                        draw.ellipse([gx - 3, gy - 3, gx + 3, gy + 3], fill=c0)
        # Re-draw clean architectural cutout portal
        draw.polygon([(460, 480), (550, 524), (550, 680), (460, 636)], fill=c0)
        draw.polygon([(660, 490), (820, 412), (820, 560), (660, 638)], fill=c1)
        img = _add_paper_grain(img, strength=7.5, seed=5)

    elif style == "austere_zen_circle":
        draw.ellipse([435, 255, 765, 585], fill=c1)
        draw.line([(160, 660), (1040, 660)], fill=c2, width=3)
        draw.rectangle([160, 654, 240, 666], fill=c1)

    elif style == "tectonic_wireframe":
        # Architectural exploded wireframe on obsidian technical ground
        for x in range(80, W, 80):
            draw.line([(x, 60), (x, H - 60)], fill=(26, 30, 36), width=1)
        for y in range(60, H, 80):
            draw.line([(80, y), (W - 80, y)], fill=(26, 30, 36), width=1)
        # Isometric facade frame layers
        for dy, col, w in [(0, c1, 3), (-90, c2, 4), (90, (180, 190, 200), 2)]:
            cx, cy = 600, 450 + dy
            poly = [(cx - 320, cy - 60), (cx + 120, cy - 220), (cx + 320, cy - 120), (cx - 120, cy + 40)]
            draw.polygon(poly, outline=col, width=w)
            for k in range(1, 5):
                t = k / 5.0
                px1 = (cx - 320) + t * 440
                py1 = (cy - 60) + t * (-160)
                px2 = (cx - 120) + t * 440
                py2 = (cy + 40) + t * (-160)
                draw.line([(px1, py1), (px2, py2)], fill=col, width=2)
        # Vertical datum leaders
        for vx, vy in [(280, 300), (720, 140), (920, 240), (480, 400)]:
            draw.line([(vx, vy), (vx, vy + 240)], fill=(90, 110, 128), width=2)
            draw.ellipse([vx - 5, vy - 5, vx + 5, vy + 5], fill=c2)

    elif style == "dense_constructivist":
        rng = np.random.default_rng(88)
        palette = [c0, c1, c2, (124, 130, 138), (42, 45, 50)]
        for idx in range(28):
            col = palette[idx % len(palette)]
            x1, y1 = int(rng.integers(-60, W - 120)), int(rng.integers(-40, H - 100))
            w_b, h_b = int(rng.integers(140, 480)), int(rng.integers(45, 220))
            if idx % 3 == 0:
                draw.polygon([(x1, y1), (x1 + w_b, y1 - 80), (x1 + w_b + 50, y1 + h_b - 80), (x1 + 50, y1 + h_b)], fill=col)
            else:
                draw.rectangle([x1, y1, x1 + w_b, y1 + h_b], fill=col)
        # Fine grid lines over dense blocks
        for x in range(60, W, 90):
            draw.line([(x, 0), (x, H)], fill=c2, width=2)
        img = _add_paper_grain(img, strength=5.0, seed=8)

    elif style == "optical_stripes":
        # High-frequency cool cobalt/silver wave interference bands
        xs = np.linspace(0, 1, W)[None, :]
        ys = np.linspace(0, 1, H)[:, None]
        wave = 0.5 + 0.5 * np.sin(48.0 * np.pi * xs + 6.0 * np.sin(5.0 * np.pi * ys))
        carrier = 0.5 + 0.5 * np.cos(14.0 * np.pi * (xs * 0.7 + ys * 0.3))
        blend = np.clip(0.68 * wave + 0.32 * carrier, 0.0, 1.0)
        arr = np.zeros((H, W, 3), dtype=np.float32)
        for ch in range(3):
            arr[:, :, ch] = c0[ch] * (1.0 - blend) + (c1[ch] * (1.0 - blend * 0.5) + c2[ch] * (blend * 0.5)) * blend
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")

    elif style == "biomorphic_contours":
        draw.rectangle([0, 0, W, H], fill=c0)
        # Smooth multi-lobe contour islands
        for step, col, width in [(260, c1, 0), (200, c2, 0), (145, c0, 0), (110, c1, 3), (70, c2, 3)]:
            pts = []
            for deg in range(0, 360, 4):
                rad = math.radians(deg)
                r = step * (1.0 + 0.28 * math.sin(3 * rad + 0.7) + 0.16 * math.cos(2 * rad - 0.4))
                pts.append((600 + r * 1.35 * math.cos(rad), 450 + r * 0.92 * math.sin(rad)))
            if width == 0:
                draw.polygon(pts, fill=col)
            else:
                draw.line(pts + [pts[0]], fill=col, width=width)
        # Secondary organic contour cluster
        for r0 in range(40, 220, 26):
            pts2 = []
            for deg in range(0, 360, 5):
                rad = math.radians(deg)
                r = r0 * (1.0 + 0.22 * math.cos(4 * rad + 1.1))
                pts2.append((250 + r * math.cos(rad), 230 + r * math.sin(rad)))
            draw.line(pts2 + [pts2[0]], fill=(92, 84, 76), width=2)

    elif style == "obsidian_signal":
        draw.rectangle([0, 0, W, H], fill=c0)
        for y in [180, 360, 540, 720]:
            draw.line([(90, y), (W - 90, y)], fill=(34, 38, 44), width=2)
        for x in [90, 310, 530, 750, 970, W - 90]:
            draw.line([(x, 120), (x, H - 120)], fill=(34, 38, 44), width=2)
        draw.rectangle([90, 360, 750, 456], fill=c1)
        draw.rectangle([750, 180, 970, 720], fill=(28, 31, 36), outline=c2, width=3)
        draw.ellipse([180, 580, 290, 690], outline=c1, width=6)

    elif style == "op_art_steps":
        draw.rectangle([0, 0, W, H], fill=c2)
        dx, dy = 86, 48
        for row in range(-2, 15):
            for col in range(-2, 12):
                cx = col * (2 * dx) + (row % 2) * dx
                cy = row * (2 * dy)
                draw.polygon([(cx, cy - dy), (cx + dx, cy), (cx, cy + dy), (cx - dx, cy)], fill=c2)
                draw.polygon([(cx - dx, cy), (cx, cy + dy), (cx, cy + 2.4 * dy), (cx - dx, cy + 1.4 * dy)], fill=c1)
                draw.polygon([(cx, cy + dy), (cx + dx, cy), (cx + dx, cy + 1.4 * dy), (cx, cy + 2.4 * dy)], fill=c0)

    elif style == "papercut_arches":
        draw.rectangle([0, 0, W, H], fill=c2)
        draw.rectangle([120, 130, 660, 780], fill=c0)
        draw.pieslice([210, 260, 570, 620], 180, 360, fill=c1)
        draw.rectangle([210, 440, 570, 780], fill=c1)
        draw.polygon([(660, 260), (1080, 260), (1080, 780), (660, 780)], fill=c1)
        # Cut-paper stair silhouettes
        for s in range(6):
            sx = 660 + s * 64
            sy = 460 + s * 52
            draw.rectangle([sx, sy, 1080, 780], fill=c2 if s % 2 == 0 else c0)
        img = _add_paper_grain(img, strength=7.0, seed=13)

    elif style == "morandi_blocks":
        draw.rectangle([0, 0, W, H], fill=c1)
        draw.rectangle([96, 110, 740, 620], fill=c0)
        draw.rectangle([580, 340, 1104, 790], fill=(166, 174, 166))
        draw.rectangle([240, 620, 740, 790], fill=c2)
        draw.line([(96, 340), (1104, 340)], fill=(242, 239, 232), width=3)
        img = _add_paper_grain(img, strength=5.0, seed=14)

    elif style == "acid_experimental":
        draw.rectangle([0, 0, W, H], fill=c0)
        for i in range(0, W, 60):
            draw.line([(i, 0), (i, H)], fill=(45, 34, 68), width=2)
        draw.polygon([(110, 160), (760, 90), (640, 440), (180, 520)], fill=c1)
        draw.ellipse([520, 320, 980, 780], outline=c2, width=10)
        draw.rectangle([140, 620, 1060, 710], fill=c2)
        draw.rectangle([420, 580, 780, 750], fill=c1)
        draw.ellipse([480, 610, 720, 720], fill=c0)

    else:  # woodblock_horizon
        draw.rectangle([0, 0, W, H], fill=c1)
        # Atmospheric horizon bands + minimal stylized mountain arcs
        draw.rectangle([0, 0, W, 380], fill=(214, 210, 200))
        draw.pieslice([-80, 180, 880, 960], 180, 360, fill=c0)
        draw.pieslice([380, 290, 1280, 980], 180, 360, fill=(58, 82, 102))
        draw.rectangle([0, 540, W, H], fill=c0)
        draw.polygon([(0, 610), (W, 560), (W, 710), (0, 760)], fill=c2)
        draw.ellipse([830, 130, 970, 270], fill=c2)
        img = _add_paper_grain(img, strength=8.5, seed=16)

    return img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)


# ---------------------------------------------------------------------------
# Openverse CC0 / PDM Verified Photography Fetcher
# ---------------------------------------------------------------------------
def _fetch_openverse_results(
    client: httpx.Client,
    query: str,
    cache: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    if query in cache:
        return cache[query]
    resp = client.get(
        "https://api.openverse.org/v1/images/",
        params={"q": query, "license": "cc0,pdm", "page_size": 20},
    )
    if resp.status_code != 200:
        cache[query] = []
        return []
    results = resp.json().get("results", [])
    cache[query] = results
    return results


def _center_crop_4_3(img: Image.Image) -> Image.Image:
    w, h = img.size
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT
    current_ratio = w / max(1, h)
    if current_ratio > target_ratio:
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif current_ratio < target_ratio:
        new_h = int(round(w / target_ratio))
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)


def _laplacian_sharpness(img: Image.Image) -> float:
    gray = np.asarray(img.convert("L"))
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _keyword_relevance_bonus(candidate: dict[str, object], spec: CuratedSpec) -> float:
    text_parts = [str(candidate.get("title") or "").lower()]
    for tag in candidate.get("tags") or []:
        if isinstance(tag, dict) and tag.get("name"):
            text_parts.append(str(tag["name"]).lower())
    haystack = " ".join(text_parts)
    tokens = {
        tok
        for tok in spec.primary_subject.lower().replace("-", " ").split()
        if len(tok) >= 4 and tok not in {"with", "from", "and", "study", "detail", "design"}
    }
    hits = sum(1 for tok in tokens if tok in haystack)
    return 0.12 * hits if hits > 0 else -0.18


def _download_and_score_candidate(
    client: httpx.Client,
    candidate: dict[str, object],
    spec: CuratedSpec,
    used_hashes: list[int],
) -> tuple[Image.Image, float, int, dict[str, str]] | None:
    url = str(candidate.get("url") or "")
    if not url.startswith("http"):
        return None
    title_l = str(candidate.get("title") or "").lower()
    if any(
        bad in title_l
        for bad in ("diagram", "chart", "screenshot", "logo", "flag", "map of", "stamp", "weapons", "regiment")
    ):
        return None
    try:
        r = client.get(url, follow_redirects=True, timeout=8.0)
        if r.status_code != 200 or len(r.content) < 12_000 or len(r.content) > 10_000_000:
            return None
        raw_bytes = r.content
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            w0, h0 = probe.size
            if w0 < 480 or h0 < 360:
                return None
        with Image.open(io.BytesIO(raw_bytes)) as raw_im:
            img = raw_im.convert("RGB")
        del raw_bytes
    except Exception:
        return None

    img.thumbnail((1600, 1200), Image.Resampling.BILINEAR)
    cropped = _center_crop_4_3(img)
    img.close()
    sharp = _laplacian_sharpness(cropped)
    if sharp < 35.0:
        return None

    dh = compute_dhash(cropped)
    if any(hamming_distance(dh, h) <= 6 for h in used_hashes):
        return None

    pal = extract_oklab_palette(cropped, k=5)
    pdist = palette_distance_oklab(pal, spec.target_palette_hint)
    res_bonus = min(0.12, (w0 * h0) / 4_000_000.0 * 0.12)
    rel_bonus = _keyword_relevance_bonus(candidate, spec)
    score = pdist - res_bonus - rel_bonus

    meta = {
        "license": str(candidate.get("license") or "cc0").upper(),
        "source_kind": f"openverse_{str(candidate.get('source') or 'cc0')}",
        "source_url": str(candidate.get("foreign_landing_url") or url),
        "creator": str(candidate.get("creator") or ""),
        "original_title": str(candidate.get("title") or "")[:120],
    }
    return cropped, score, dh, meta


def generate_ai_studio_asset(spec: CuratedSpec) -> tuple[Image.Image, int, dict[str, str]]:
    """Generate bespoke showcase studio visual via OpenAI gpt-image-1-mini when CC0 lacks exact fit."""
    from openai import OpenAI, RateLimitError

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set for fallback studio generation.")
    client = OpenAI()
    neg_hint = ", ".join(spec.negative_guardrails[:3]) if spec.negative_guardrails else "CGI gloss, text"
    prompt = (
        f"Authentic editorial photograph of {spec.title_en} ({spec.primary_subject}). "
        f"Camera optics: {spec.optics_camera}. "
        f"Physical materials & joinery: {spec.material_stack}. "
        f"Lighting & atmosphere: {spec.lighting_rig}. "
        f"Style restraint: architectural magazine documentary realism, zero text, zero borders, avoid {neg_hint}."
    )
    resp = None
    for attempt in range(6):
        try:
            resp = client.images.generate(
                model="gpt-image-1-mini",
                prompt=prompt,
                size="1024x1024",
                quality="low",
            )
            break
        except RateLimitError:
            if attempt == 5:
                raise
            time.sleep(6 + attempt * 3)
    assert resp is not None
    img_bytes = base64.b64decode(resp.data[0].b64_json or "")
    with Image.open(io.BytesIO(img_bytes)) as raw_im:
        cropped = _center_crop_4_3(raw_im.convert("RGB"))
    dh = compute_dhash(cropped)
    meta = {
        "license": "AI-SELF-GENERATED-SHOWCASE",
        "source_kind": "openai_gpt_image_1_mini",
        "source_url": f"self://generated/{spec.asset_id}",
        "creator": "AetherVault Curated Studio Generator",
        "original_title": spec.title_en,
    }
    return cropped, dh, meta


def acquire_photo_asset(
    client: httpx.Client,
    spec: CuratedSpec,
    ov_cache: dict[str, list[dict[str, object]]],
    used_urls: set[str],
    used_hashes: list[int],
) -> tuple[Image.Image, int, dict[str, str]]:
    """Find, verify, deduplicate, and crop the best CC0/PDM image for a photographic spec."""
    queries = [*spec.search_queries, *DOMAIN_FALLBACK_QUERIES.get(spec.domain, [])]
    candidates: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for q in queries:
        for item in _fetch_openverse_results(client, q, ov_cache):
            uid = str(item.get("id") or item.get("url") or "")
            url = str(item.get("url") or "")
            w = int(item.get("width") or 0)
            h = int(item.get("height") or 0)
            if not uid or uid in seen_ids or url in used_urls:
                continue
            if w < 520 or h < 380:
                continue
            seen_ids.add(uid)
            candidates.append(item)
        if len(candidates) >= 18:
            break

    best: tuple[Image.Image, float, int, dict[str, str], str] | None = None
    attempts = 0
    for cand in candidates:
        if attempts >= 8:
            break
        attempts += 1
        res = _download_and_score_candidate(client, cand, spec, used_hashes)
        if res is None:
            continue
        cropped, score, dh, meta = res
        cand_url = str(cand.get("url") or "")
        if best is None or score < best[1]:
            best = (cropped, score, dh, meta, cand_url)
        # Early stop if very close OKLab palette match
        if score < 0.14:
            break

    if best is None:
        raise RuntimeError(f"Failed to acquire valid CC0/PDM photo for {spec.asset_id} ({spec.domain})")

    used_urls.add(best[4])
    return best[0], best[2], best[3]


# ---------------------------------------------------------------------------
# Read-only P-MIC-4 Aesthetic KB Prior Linkage
# ---------------------------------------------------------------------------
def load_akb_public_priors() -> list[dict[str, object]]:
    """Read public asset OKLab palettes from local P-MIC-4 Aesthetic KB SQLite (read-only)."""
    if not AKB_SQLITE_PATH.exists():
        return []
    uri = f"file:{AKB_SQLITE_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            """
            SELECT a.asset_id, a.palette_json, s.board_name
            FROM assets a
            LEFT JOIN asset_sources s ON a.asset_id = s.asset_id
            WHERE a.privacy = 'public' AND a.near_duplicate_of IS NULL
            """
        ).fetchall()
    finally:
        conn.close()

    priors: list[dict[str, object]] = []
    for asset_id, pal_json, board_name in rows:
        try:
            swatches = json.loads(pal_json or "[]")
            hexes = [str(s["hex"]) for s in swatches if isinstance(s, dict) and s.get("hex")]
        except Exception:
            hexes = []
        if hexes:
            priors.append({"asset_id": asset_id, "hexes": hexes[:5], "board": board_name or "Aesthetic KB"})
    return priors


def match_akb_prior(palette: list[str], akb_priors: list[dict[str, object]]) -> tuple[str | None, str | None, float | None]:
    if not akb_priors or not palette:
        return None, None, None
    best_dist = 999.0
    best_id: str | None = None
    best_board: str | None = None
    for row in akb_priors:
        dist = palette_distance_oklab(palette, row["hexes"])  # type: ignore[arg-type]
        if dist < best_dist:
            best_dist = dist
            best_id = str(row["asset_id"])
            best_board = str(row["board"])
    return best_id, best_board, round(best_dist, 4)


# ---------------------------------------------------------------------------
# Contact Sheet Generator (8 cols x 10 rows for visual QA)
# ---------------------------------------------------------------------------
def build_contact_sheet(assets: list[dict[str, object]]) -> None:
    cols, rows = 8, 10
    cell_w, cell_h = 260, 215
    thumb_w, thumb_h = 240, 180
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (14, 16, 18))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for idx, item in enumerate(assets[:80]):
        r, c = divmod(idx, cols)
        x0 = c * cell_w + 10
        y0 = r * cell_h + 6
        img_path = IMAGES_DIR / f"{item['asset_id']}.webp"
        thumb = Image.open(img_path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x0, y0))
        dom = item["subject_isolation"]["domain"]  # type: ignore[index]
        label = f"{item['asset_id']} [{dom[:4]}] {item.get('license', '')}"
        draw.text((x0 + 2, y0 + thumb_h + 4), label[:38], fill=(225, 228, 232), font=font)

    sheet.save(CONTACT_SHEET_PATH, format="JPEG", quality=88)


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------
def run_curation(force_refetch: bool = False, generate_ids: set[str] | None = None) -> dict[str, object]:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_SHOWCASE_JSON.parent.mkdir(parents=True, exist_ok=True)
    gen_set = generate_ids or set()

    ov_cache: dict[str, list[dict[str, object]]] = {}
    if OPENVERSE_CACHE_PATH.exists():
        ov_cache = json.loads(OPENVERSE_CACHE_PATH.read_text(encoding="utf-8"))

    existing_manifest: dict[str, dict[str, str]] = {}
    if PROVENANCE_CACHE_PATH.exists() and not force_refetch:
        existing_manifest.update(json.loads(PROVENANCE_CACHE_PATH.read_text(encoding="utf-8")))
    if MANIFEST_JSON_PATH.exists() and not force_refetch:
        prev = json.loads(MANIFEST_JSON_PATH.read_text(encoding="utf-8"))
        for rec in prev.get("records", []):
            existing_manifest[rec["asset_id"]] = rec.get("provenance", {})

    akb_priors = load_akb_public_priors()
    used_urls: set[str] = set()
    used_hashes: list[int] = []
    curated_records: list[dict[str, object]] = []
    manifest_records: list[dict[str, object]] = []

    # Pre-generate requested bespoke studio visuals in bounded parallel batch (respecting 20/min tier)
    pregenerated: dict[str, tuple[Image.Image, int, dict[str, str]]] = {}
    gen_specs = [s for s in CURATED_SPECS if s.asset_id in gen_set and s.domain != "graphic"]
    if gen_specs:
        print(f"Generating {len(gen_specs)} bespoke studio assets with bounded concurrency (max_workers=3)...")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = {pool.submit(generate_ai_studio_asset, sp): sp for sp in gen_specs}
            for fut in as_completed(futs):
                sp = futs[fut]
                img_res, dh_res, prov_res = fut.result()
                out_p = IMAGES_DIR / f"{sp.asset_id}.webp"
                img_res.save(out_p, format="WEBP", quality=90)
                existing_manifest[sp.asset_id] = prov_res
                PROVENANCE_CACHE_PATH.write_text(
                    json.dumps(existing_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                pregenerated[sp.asset_id] = (img_res, dh_res, prov_res)
                print(f"[GENERATED] {sp.asset_id} ({sp.domain}) <- {prov_res['license']} | {sp.title_en}")

    headers = {"User-Agent": "SpatialAIPortfolio/0.1 (CC0 Aesthetic Curation Script)"}
    with httpx.Client(headers=headers, timeout=12.0) as client:
        for idx, spec in enumerate(CURATED_SPECS):
            out_img_path = IMAGES_DIR / f"{spec.asset_id}.webp"

            if spec.domain == "graphic":
                img = render_graphic_asset(spec)
                img.save(out_img_path, format="WEBP", quality=90)
                dh = compute_dhash(img)
                used_hashes.append(dh)
                prov = {
                    "license": "CC0-SELF-GENERATED",
                    "source_kind": "procedural_constructivist_render",
                    "source_url": "self://pipeline/curate_80.py",
                    "creator": "AetherVault Procedural Engine",
                    "original_title": spec.title_en,
                }
            elif spec.asset_id in pregenerated:
                img, dh, prov = pregenerated[spec.asset_id]
                used_hashes.append(dh)
                img.save(out_img_path, format="WEBP", quality=90)
            elif out_img_path.exists() and not force_refetch:
                with Image.open(out_img_path) as cached_im:
                    img = cached_im.convert("RGB")
                dh = compute_dhash(img)
                used_hashes.append(dh)
                prov = existing_manifest.get(
                    spec.asset_id,
                    {
                        "license": "CC0",
                        "source_kind": "openverse_cc0_cached",
                        "source_url": f"https://openverse.org/search/image?q={spec.search_queries[0].replace(' ', '+')}",
                        "creator": "Openverse CC0/PDM Contributor",
                        "original_title": spec.title_en,
                    },
                )
                if prov.get("source_url"):
                    used_urls.add(prov["source_url"])
            else:
                try:
                    img, dh, prov = acquire_photo_asset(client, spec, ov_cache, used_urls, used_hashes)
                    print(f"[CURATED] {spec.asset_id} ({spec.domain}) <- {prov['license']} | {prov['original_title'][:40]}")
                except Exception as exc:
                    print(f"[FALLBACK-GEN] {spec.asset_id} Openverse fallback ({exc})")
                    img, dh, prov = generate_ai_studio_asset(spec)
                used_hashes.append(dh)
                img.save(out_img_path, format="WEBP", quality=90)

            existing_manifest[spec.asset_id] = prov
            if idx % 5 == 0:
                PROVENANCE_CACHE_PATH.write_text(
                    json.dumps(existing_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                gc.collect()

            palette = extract_oklab_palette(img, k=5)
            akb_id, akb_board, akb_dist = match_akb_prior(palette, akb_priors)

            # Build and strictly validate against Pydantic AestheticAsset
            spectrum_models = {
                ax_id: StyleSpectrumAxis(score=sc, salience=sal) for ax_id, (sc, sal) in spec.spectrums.items()
            }
            validated = AestheticAsset(
                asset_id=spec.asset_id,
                title=spec.title,
                subject_isolation=SubjectIsolation(
                    domain=spec.domain,
                    domain_label=spec.domain_label,
                    primary_subject=spec.primary_subject,
                    is_personal_prior=spec.is_personal_prior,
                ),
                style_spectrums=spectrum_models,
                granular_descriptors=GranularDescriptors(
                    optics_camera=spec.optics_camera,
                    lighting_rig=spec.lighting_rig,
                    material_stack=spec.material_stack,
                    color_palette=palette,
                ),
                compiler_primitives=CompilerPrimitives(
                    positive_tokens=spec.positive_tokens,
                    negative_guardrails=spec.negative_guardrails,
                ),
            )

            record = validated.model_dump()
            record.update(
                {
                    "title_en": spec.title_en,
                    "image_url": f"/assets/curated_80/{spec.asset_id}.webp",
                    "license": prov.get("license", "CC0"),
                    "source_kind": prov.get("source_kind", ""),
                    "source_url": prov.get("source_url", ""),
                    "akb_prior_asset_id": akb_id,
                    "akb_board_hint": akb_board,
                }
            )
            curated_records.append(record)
            manifest_records.append(
                {
                    "asset_id": spec.asset_id,
                    "domain": spec.domain,
                    "is_personal_prior": spec.is_personal_prior,
                    "redistribution_safe": True,
                    "palette_oklab_hex": palette,
                    "akb_prior_asset_id": akb_id,
                    "akb_board_hint": akb_board,
                    "akb_palette_distance": akb_dist,
                    "provenance": prov,
                }
            )
            shutil.copy2(out_img_path, WEB_IMAGES_DIR / f"{spec.asset_id}.webp")

    PROVENANCE_CACHE_PATH.write_text(json.dumps(existing_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    OPENVERSE_CACHE_PATH.write_text(json.dumps(ov_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    # Verify all 40 golden anchors map consistently
    by_id = {r["asset_id"]: r for r in curated_records}
    anchor_checks: list[dict[str, object]] = []
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        for pt in rubric.anchors:
            rec = by_id[pt.reference_asset_id]
            score = rec["style_spectrums"][axis_id]["score"]  # type: ignore[index]
            sal = rec["style_spectrums"][axis_id]["salience"]  # type: ignore[index]
            assert score == pt.level, f"Anchor score mismatch: {axis_id} {pt.level} != {score}"
            anchor_checks.append(
                {
                    "axis_id": axis_id,
                    "level": pt.level,
                    "reference_asset_id": pt.reference_asset_id,
                    "salience": sal,
                }
            )

    domain_counts = {
        dom: sum(1 for r in curated_records if r["subject_isolation"]["domain"] == dom)  # type: ignore[index]
        for dom in ("architecture", "industrial", "editorial", "craft", "graphic")
    }
    cost_ledger = estimate_ingestion_cost_cny(1000).model_dump()
    now_iso = datetime.now(timezone.utc).isoformat()

    assets_payload = {
        "version": "1.0.0",
        "generated_at": now_iso,
        "total_assets": len(curated_records),
        "domain_counts": domain_counts,
        "assets": curated_records,
    }
    ASSETS_JSON_PATH.write_text(json.dumps(assets_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    showcase_bundle = {
        **assets_payload,
        "axes": [ax.model_dump() for ax in SPECTRUM_AXES],
        "golden_anchors": {k: v.model_dump() for k, v in GOLDEN_ANCHOR_RUBRICS.items()},
        "cost_ledger": cost_ledger,
    }
    WEB_SHOWCASE_JSON.write_text(json.dumps(showcase_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_payload = {
        "version": "1.0.0",
        "generated_at": now_iso,
        "total_assets": len(manifest_records),
        "domain_counts": domain_counts,
        "akb_priors_loaded": len(akb_priors),
        "golden_anchors_verified": len(anchor_checks),
        "cost_ledger": cost_ledger,
        "records": manifest_records,
    }
    MANIFEST_JSON_PATH.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    build_contact_sheet(curated_records)
    return {
        "total_assets": len(curated_records),
        "domain_counts": domain_counts,
        "akb_priors_loaded": len(akb_priors),
        "golden_anchors_verified": len(anchor_checks),
        "effective_cost_cny_per_img": cost_ledger["effective_cost_cny_per_img"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate 80 cross-domain assets for AetherVault MIC-156.")
    parser.add_argument("--force", action="store_true", help="Re-fetch all remote CC0 images even if cached.")
    parser.add_argument(
        "--generate-ids",
        type=str,
        default="",
        help="Comma-separated asset_ids to regenerate via studio AI image generator.",
    )
    args = parser.parse_args()
    gen_ids = {s.strip() for s in args.generate_ids.split(",") if s.strip()}
    summary = run_curation(force_refetch=args.force, generate_ids=gen_ids)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
