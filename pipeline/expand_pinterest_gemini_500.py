"""Replace 110 Museum Archive Images with 110 Curated Contemporary Pinterest Aesthetic Extensions.

Pipeline:
  1. Downloads all 273 fresh Pinterest pin candidates (`pinterest_extension_candidates_273.json`),
     enforcing resolution >= 320px and converting to clean WebP.
  2. Computes 64-bit dHash perceptual fingerprints against all 390 existing personal Pinterest
     assets AND intra-candidate to guarantee zero visual duplicates.
  3. Runs `gemini-4-hydrogen` (`ThinkingLevel.LOW`) directly on candidate pixels for unified:
     - Editorial quality gating (1-10)
     - Unbiased 8-domain + model-native open style discovery (admitting newly emerging styles)
     - 8-axis orthogonal aesthetic spectrums & saliences
     - Pixel-grounded honest Chinese aesthetic critique (`core_match` vs `contrast_inspiration`)
  4. Selects the top 110 highest-quality contemporary Pinterest extensions proportionally across
     all 8 visual domains, removes old museum `exp_*.webp` assets, saves fresh `pext_*.webp`,
     and rebuilds:
     - `web/public/data/aethervault_personal_500.json` (`5.1.0-pinterest-ext-rag-500`)
     - `data/pinterest_500/aethervault_assets_500.json`
     - `web/public/data/aethervault_rag_500.jsonl`
     - `data/pinterest_500/contact_sheet_ext_110.jpg`
"""

from __future__ import annotations

import io
import json
import math
import os
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field

from .analyze_aesthetic_500 import _compute_aspect_info
from .converge_gemini_rag_500 import (
    ARCHETYPE_META,
    ARCHETYPE_ORDER,
    STYLE_CATALOG,
    _map_lighting,
    _map_materials,
    _map_medium,
    _map_style_bucket,
    _map_typology,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_ASSETS_DIR = WEB_PUBLIC_DIR / "assets" / "pinterest_500"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
CANDIDATES_JSON = REPO_ROOT / "data" / "pinterest_500" / "pinterest_extension_candidates_273.json"
CANDIDATES_IMG_DIR = REPO_ROOT / "data" / "pinterest_500" / "pinterest_ext_candidates"
EXT_GEMINI_CACHE = REPO_ROOT / "data" / "pinterest_500" / "_pinterest_ext_gemini_cache.json"
EXT_CONTACT_SHEET = REPO_ROOT / "data" / "pinterest_500" / "contact_sheet_ext_110.jpg"
DISCOVERY_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_open_discovery_500.json"

GEMINI_MODEL = "gemini-4-hydrogen"

# Newly admitted model-native style terms beyond the initial catalog
ADMITTED_NEW_STYLES: dict[str, dict[str, Any]] = {
    "brutalism": {"zh": "粗野主义", "en": "Brutalism", "is_movement": True},
    "japandi": {"zh": "侘寂日式", "en": "Japandi", "is_movement": True},
    "minimalist_lighting": {"zh": "建筑光影美学", "en": "Architectural Light & Shadow", "is_movement": False},
    "cyber_techwear": {"zh": "赛博机能", "en": "Cyberpunk Techwear", "is_movement": False},
}

EXTENDED_STYLE_CATALOG: dict[str, dict[str, Any]] = {
    **STYLE_CATALOG,
    **ADMITTED_NEW_STYLES,
}

# Target proportional extension quotas summing to exactly 110
TARGET_QUOTAS: dict[str, int] = {
    "interior": 24,
    "architecture": 22,
    "graphic_typography": 18,
    "landscape": 12,
    "illustration_character": 12,
    "fashion_photography": 8,
    "craft": 7,
    "industrial": 7,
}

DomainLiteral = Literal[
    "interior",
    "architecture",
    "graphic_typography",
    "craft",
    "industrial",
    "landscape",
    "illustration_character",
    "fashion_photography",
]

DOMAIN_TO_LEGACY_5: dict[str, tuple[str, str]] = {
    "architecture": ("architecture", "建筑与空间"),
    "interior": ("architecture", "建筑与空间"),
    "landscape": ("architecture", "建筑与空间"),
    "industrial": ("industrial", "工业与构造"),
    "craft": ("craft", "器物与肌理"),
    "graphic_typography": ("graphic", "平面与界面"),
    "illustration_character": ("graphic", "平面与界面"),
    "fashion_photography": ("editorial", "光影与影像"),
}


class AxisScore(BaseModel):
    score: float = Field(..., ge=-1.0, le=1.0)
    salience: float = Field(..., ge=0.0, le=1.0)


class Spectrum8(BaseModel):
    tectonic_honesty: AxisScore
    surface_entropy: AxisScore
    spatial_density: AxisScore
    geometric_order: AxisScore
    lighting_drama: AxisScore
    chromatic_tension: AxisScore
    thermal_mood: AxisScore
    reality_abstraction: AxisScore


class PinterestExtVlmEval(BaseModel):
    """Unified Gemini 4 Hydrogen visual evaluation, style discovery & critique for a Pinterest pin."""

    keep_quality_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Editorial/monograph design quality 1-10. Reject watermarks, blurry/tiny images, cluttered ads, stock mockups with ugly text overlays (<=5).",
    )
    visual_domain: DomainLiteral
    medium: str = Field(..., description="Concise canonical English medium (2-4 words).")
    free_style_primary: str = Field(
        ...,
        description="Most accurate canonical model-native English art/design/illustration style term (2-4 words, Title Case). Admit authentic terms like 'Brutalism', 'Japandi', 'High-Tech', 'Braun Functionalism', 'Experimental Typography', 'Anime Techwear', 'Minimalist Wayfinding', 'Swiss Style', 'Avant-Garde Fashion', etc.",
    )
    free_style_secondary: str = Field(default="")
    is_canonical_ism: bool
    content_typology_zh: str = Field(..., description="Concise Chinese subject label (2-6 chars).")
    visual_traits: list[str] = Field(..., min_length=2, max_length=4)
    confidence: float = Field(..., ge=0.0, le=1.0)
    style_spectrums: Spectrum8
    title_zh: str = Field(..., description="Crisp monograph-grade Chinese title (5-14 chars).")
    primary_subject_en: str = Field(..., description="Concise English physical/visual subject (3-6 words).")
    optics_camera: str = Field(..., description="Concise English framing/camera/rendering note.")
    lighting_rig: str = Field(..., description="Concise English lighting description.")
    material_stack: str = Field(..., description="Concise Chinese/English material or visual medium summary.")
    resonance_mode: Literal["core_match", "contrast_inspiration"]
    headline_insight: str = Field(..., description="One-sentence aesthetic thesis (22-44 Chinese chars).")
    proportion_and_order: str = Field(..., description="Concrete proportion, layout & spatial/grid breakdown (60-110 Chinese chars).")
    material_and_detail: str = Field(..., description="Concrete visible materials, joints, typography or linework craft (60-110 Chinese chars).")
    light_and_palette: str = Field(..., description="Honest lighting & color area ratio breakdown (50-95 Chinese chars).")
    why_you_love_it: str = Field(
        ...,
        description="Honest second-person aesthetic resonance critique (65-115 Chinese chars). Explicitly explain contrast inspiration if high-energy/experimental/anime.",
    )
    design_takeaways: list[str] = Field(..., min_length=3, max_length=3)


SYSTEM_PROMPT = """You are a world-class architectural, industrial, graphic, and illustration curator extending a designer's personal Pinterest visual atlas.
Inspect ONLY the provided Pinterest image pixels objectively.

1. Score `keep_quality_score` (1-10) strictly:
   - 8-10: publication/monograph-grade photography, typography, illustration, or design reference with clean framing.
   - <=5: cluttered e-commerce mockups, watermarked images, blurry/low-res screenshots, meme/text spam, or generic template ads.
2. Classify `visual_domain`, `medium`, `free_style_primary` (canonical English style models natively understand, e.g., Minimalism, Modernism, Brutalism, Japandi, Wabi-Sabi, High-Tech, Parametricism, Industrial Minimalism, Biophilic, Braun Functionalism, Experimental Typography, Swiss Style, Minimalist Wayfinding, Anime Techwear, Ink Wash Illustration, Avant-Garde Fashion).
3. Score all 8 orthogonal axes (`-1.0` to `+1.0`) and saliences (`0.0` to `1.0`):
   - tectonic_honesty: Monolithic (-1) <-> Exposed Tectonic (+1)
   - surface_entropy: Pristine Precision (-1) <-> Weathered Patina (+1)
   - spatial_density: Austere Negative Space (-1) <-> Layered Dense (+1)
   - geometric_order: Biomorphic Organic (-1) <-> Strict Orthogonal Grid (+1)
   - lighting_drama: Soft Diffused (-1) <-> Chiaroscuro Hard Shadow (+1)
   - chromatic_tension: Muted Neutral (-1) <-> High-Chroma Contrast (+1)
   - thermal_mood: Clinical Cool (-1) <-> Intimate Warm (+1)
   - reality_abstraction: Photorealistic (-1) <-> Graphic/Stylized (+1)
4. Write a razor-sharp, zero-fluff Chinese aesthetic critique grounded strictly in actual pixels. Set `resonance_mode='contrast_inspiration'` for bold/pop/anime/experimental pieces that break out of a calm architectural baseline, and `core_match` for serene/tectonic/minimal/warm-material pieces."""


def _dhash64(img_path: Path) -> int:
    with Image.open(img_path) as im:
        gray = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        arr = np.asarray(gray, dtype=np.int16)
    diff = arr[:, 1:] > arr[:, :-1]
    val = 0
    for bit in diff.flatten():
        val = (val << 1) | int(bool(bit))
    return val


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _extract_palette_hex(img_path: Path, k: int = 5) -> list[str]:
    with Image.open(img_path) as im:
        small = im.convert("RGB")
        small.thumbnail((160, 160), Image.Resampling.LANCZOS)
        pal = small.quantize(colors=k, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = Counter(pal.getdata())
        top = [rgb for rgb, _ in counts.most_common(k)]
    hexes = [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in top]
    while len(hexes) < k:
        hexes.append(hexes[-1] if hexes else "#CCCCCC")
    return hexes[:k]


def _download_one(idx: int, cand: dict[str, Any]) -> dict[str, Any] | None:
    CANDIDATES_IMG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CANDIDATES_IMG_DIR / f"cand_{idx:03d}.webp"
    url = cand["image_url"]

    if out_path.is_file() and out_path.stat().st_size > 4000:
        return {**cand, "cand_id": f"cand_{idx:03d}", "local_path": str(out_path)}

    urls_to_try = [url]
    if "/originals/" in url:
        urls_to_try.append(url.replace("/originals/", "/736x/"))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
        "Referer": "https://www.pinterest.com/",
    }
    for u in urls_to_try:
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            with Image.open(io.BytesIO(raw)) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                if min(w, h) < 280 or max(w, h) < 420:
                    return None
                rgb.thumbnail((960, 960), Image.Resampling.LANCZOS)
                rgb.save(out_path, format="WEBP", quality=84, method=4)
            return {**cand, "cand_id": f"cand_{idx:03d}", "local_path": str(out_path)}
        except Exception:
            continue
    return None


def _map_style_with_admissions(domain: str, rec: dict[str, Any]) -> str:
    """Admit newly emerging high-signal model-native styles while keeping bounded discipline."""
    p = (rec.get("free_style_primary") or "").lower()
    s = (rec.get("free_style_secondary") or "").lower()
    combo = f"{p} {s}"

    if domain in ("architecture", "interior"):
        if "brutal" in combo:
            return "brutalism"
        if "japandi" in combo:
            return "japandi"
    if domain == "illustration_character":
        if "cyber" in combo and "techwear" in combo:
            return "cyber_techwear"
    return _map_style_bucket(domain, rec)


def _eval_one_candidate(
    client: genai.Client,
    cand: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    img_path = Path(cand["local_path"])
    img_bytes = img_path.read_bytes()
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/webp"),
                    "Inspect this Pinterest image strictly from its pixels and return the PinterestExtVlmEval JSON.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=PinterestExtVlmEval,
                    temperature=0.15,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            parsed = PinterestExtVlmEval.model_validate_json((resp.text or "").strip())
            return cand["cand_id"], parsed.model_dump()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Gemini eval failed for {cand['cand_id']}: {last_err}")


def _build_contact_sheet(paths: list[Path], out_path: Path) -> None:
    cols = 11
    rows = math.ceil(len(paths) / cols)
    cell_w, cell_h = 160, 160
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (18, 20, 26))
    for i, p in enumerate(paths):
        r, c = divmod(i, cols)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                # Center crop square
                w, h = im.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                im = im.crop((left, top, left + side, top + side)).resize(
                    (cell_w - 4, cell_h - 4), Image.Resampling.LANCZOS
                )
                sheet.paste(im, (c * cell_w + 2, r * cell_h + 2))
        except Exception:
            continue
    sheet.save(out_path, format="JPEG", quality=86, optimize=True)


def main() -> None:
    if not CANDIDATES_JSON.is_file():
        raise FileNotFoundError(f"Missing Pinterest candidates JSON: {CANDIDATES_JSON}")
    if not WEB_PERSONAL_JSON.is_file():
        raise FileNotFoundError(f"Missing personal 500 JSON: {WEB_PERSONAL_JSON}")

    t0 = time.time()
    candidates = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    discovery_old = json.loads(DISCOVERY_CACHE_PATH.read_text(encoding="utf-8")) if DISCOVERY_CACHE_PATH.is_file() else {}

    personal_390 = [a for a in bundle["assets"] if a.get("source_origin") == "pinterest_personal"]
    assert len(personal_390) == 390, f"Expected 390 personal Pinterest pins, found {len(personal_390)}"
    print(f"Loaded {len(personal_390)} core Pinterest pins and {len(candidates)} fresh Pinterest candidates.")

    # Step 1: Download candidates concurrently
    downloaded: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(_download_one, i, c): i for i, c in enumerate(candidates)}
        for fut in as_completed(futs):
            res = fut.result()
            if res is not None:
                downloaded.append(res)
    downloaded.sort(key=lambda x: x["cand_id"])
    print(f"Downloaded {len(downloaded)} / {len(candidates)} valid high-res Pinterest WebPs ({time.time()-t0:.1f}s)")

    # Step 2: Perceptual dHash deduplication against all 390 core pins + intra-candidates
    existing_hashes: list[int] = []
    for a in personal_390:
        p = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
        if p.is_file():
            existing_hashes.append(_dhash64(p))

    deduped: list[dict[str, Any]] = []
    seen_cand_hashes: list[int] = []
    dup_vs_core = 0
    dup_intra = 0
    for c in downloaded:
        h = _dhash64(Path(c["local_path"]))
        if any(_hamming(h, eh) <= 6 for eh in existing_hashes):
            dup_vs_core += 1
            continue
        if any(_hamming(h, sh) <= 6 for sh in seen_cand_hashes):
            dup_intra += 1
            continue
        seen_cand_hashes.append(h)
        deduped.append(c)
    print(
        f"After pHash dedup: {len(deduped)} unique candidates "
        f"(skipped {dup_vs_core} matching core 390, {dup_intra} intra-duplicates)"
    )

    # Step 3: Gemini 4 Hydrogen visual curation + style discovery + critique
    cache: dict[str, dict[str, Any]] = {}
    if EXT_GEMINI_CACHE.is_file():
        try:
            cache = json.loads(EXT_GEMINI_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [c for c in deduped if c["cand_id"] not in cache]
    print(f"Gemini 4 Hydrogen Evaluation: total={len(deduped)}, cached={len(cache)}, todo={len(todo)}")
    if todo:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY required.")
        client = genai.Client(api_key=key)
        lock = threading.Lock()
        done = 0
        t_vlm = time.time()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {pool.submit(_eval_one_candidate, client, c): c["cand_id"] for c in todo}
            for fut in as_completed(futs):
                cid = futs[fut]
                try:
                    cand_id, payload = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] eval failed {cid}: {exc}")
                    continue
                with lock:
                    cache[cand_id] = payload
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        EXT_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        print(f"VLM progress: {done}/{len(todo)} ({time.time()-t_vlm:.1f}s)")
        EXT_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Step 4: Select top 110 proportionally by domain & quality score
    scored_by_dom: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for c in deduped:
        ev = cache.get(c["cand_id"])
        if not ev:
            continue
        q = int(ev.get("keep_quality_score", 0))
        if q < 6:
            continue
        conf = float(ev.get("confidence", 0.8))
        rank_score = q + conf * 0.5
        scored_by_dom[ev["visual_domain"]].append((rank_score, c, ev))

    for dom in scored_by_dom:
        scored_by_dom[dom].sort(key=lambda x: -x[0])

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    selected_ids: set[str] = set()

    for dom, quota in TARGET_QUOTAS.items():
        picks = scored_by_dom.get(dom, [])[:quota]
        for _, c, ev in picks:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    # Backfill to exact 110 from highest-scoring remaining candidates
    if len(selected) < 110:
        remainder = [
            (score, c, ev)
            for dom_list in scored_by_dom.values()
            for (score, c, ev) in dom_list
            if c["cand_id"] not in selected_ids
        ]
        remainder.sort(key=lambda x: -x[0])
        for _, c, ev in remainder[: 110 - len(selected)]:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    assert len(selected) == 110, f"Expected 110 selected Pinterest extensions, got {len(selected)}"
    print("Selected 110 Pinterest extensions by domain:", dict(Counter(ev["visual_domain"] for _, ev in selected)))

    # Step 5: Remove old museum `exp_*.webp` and copy fresh 110 `pext_*.webp`
    removed_old = 0
    for old_f in WEB_ASSETS_DIR.glob("exp_*.webp"):
        old_f.unlink()
        removed_old += 1
    for old_p in WEB_ASSETS_DIR.glob("pext_*.webp"):
        old_p.unlink()
    print(f"Removed {removed_old} old museum exp_*.webp images from {WEB_ASSETS_DIR}")

    new_ext_assets: list[dict[str, Any]] = []
    new_ext_paths: list[Path] = []
    admitted_raw_styles: Counter[str] = Counter()

    for idx, (cand, ev) in enumerate(selected, start=1):
        dom = ev["visual_domain"]
        dmeta = ARCHETYPE_META[dom]
        aid = f"pext_{dom[:4]}_{idx:03d}"
        dst_path = WEB_ASSETS_DIR / f"{aid}.webp"
        dst_path.write_bytes(Path(cand["local_path"]).read_bytes())
        new_ext_paths.append(dst_path)

        w, h, aspect_lbl = _compute_aspect_info(dst_path)
        palette = _extract_palette_hex(dst_path, k=5)

        style_id = _map_style_with_admissions(dom, ev)
        smeta = EXTENDED_STYLE_CATALOG[style_id]
        native_primary = " ".join(ev["free_style_primary"].strip().split())
        native_secondary = " ".join((ev.get("free_style_secondary") or "").strip().split())
        visual_traits = [t.strip() for t in ev.get("visual_traits", [])[:4] if t.strip()]
        admitted_raw_styles[native_primary] += 1

        medium_zh = _map_medium(dom, ev)
        typology_zh = _map_typology(dom, ev)
        materials_zh = _map_materials(dom, ev, [])

        # Build asset dict matching full CuratedShowcaseAsset schema
        legacy_dom, legacy_dom_zh = DOMAIN_TO_LEGACY_5[dom]
        spec = ev["style_spectrums"]
        tmp_asset = {"style_spectrums": spec, "archetype": dom}
        # Derive lighting from real 8-axis spectrums & pixel traits
        drama = float(spec["lighting_drama"]["score"])
        warmth = float(spec["thermal_mood"]["score"])
        default_lgt = "戏剧硬影" if drama >= 0.4 else ("暖调氛围" if warmth >= 0.35 else ("漫射柔光" if drama <= -0.2 else "自然天光"))
        lighting_zh = _map_lighting(dom, tmp_asset, ev, default_lgt)

        rag_facets = {
            "medium": medium_zh,
            "typology": typology_zh,
            "materials": materials_zh,
            "lighting": lighting_zh,
        }
        model_prompt_tokens = list(
            dict.fromkeys(
                [
                    native_primary,
                    *([native_secondary] if native_secondary else []),
                    smeta["en"],
                    ev["medium"].strip(),
                    dmeta["en"],
                    *visual_traits,
                ]
            )
        )
        retrieval_text = (
            f"[{dmeta['zh']} | {smeta['zh']} ({native_primary})] "
            f"medium:{medium_zh} · typology:{typology_zh} · "
            f"materials:{','.join(materials_zh)} · lighting:{lighting_zh} | "
            f"traits:{', '.join(visual_traits)} | "
            f"{ev['title_zh'].strip()} — {ev['headline_insight'].strip()}"
        )

        asset_obj: dict[str, Any] = {
            "asset_id": aid,
            "title": ev["title_zh"].strip(),
            "title_en": ev["primary_subject_en"].strip(),
            "image_url": f"/assets/pinterest_500/{aid}.webp",
            "width": w,
            "height": h,
            "aspect_label": aspect_lbl,
            "license": "Pinterest Aesthetic Extension",
            "source_kind": "pinterest_extension",
            "source_origin": "profile_expansion",
            "source_url": cand.get("pin_url", ""),
            "board_name": f"Pinterest 延展 · {cand.get('query', '')[:28]}",
            "archetype": dom,
            "archetype_label": dmeta["zh"],
            "aesthetic_style": style_id,
            "aesthetic_style_zh": smeta["zh"],
            "aesthetic_style_en": smeta["en"],
            "is_canonical_ism": bool(ev["is_canonical_ism"]),
            "native_style_primary": native_primary,
            "native_style_secondary": native_secondary,
            "visual_traits": visual_traits,
            "discovery_confidence": round(float(ev["confidence"]), 3),
            "sub_style": smeta["zh"],
            "sub_category": smeta["zh"],
            "aesthetic_quality_score": int(ev["keep_quality_score"]),
            "subject_isolation": {
                "domain": legacy_dom,
                "domain_label": legacy_dom_zh,
                "primary_subject": ev["primary_subject_en"].strip(),
                "is_personal_prior": False,
            },
            "style_spectrums": spec,
            "granular_descriptors": {
                "optics_camera": ev["optics_camera"].strip(),
                "lighting_rig": ev["lighting_rig"].strip(),
                "material_stack": ev["material_stack"].strip(),
                "color_palette": palette,
            },
            "compiler_primitives": {
                "positive_tokens": model_prompt_tokens[:6],
                "negative_guardrails": ["watermark", "cluttered background", "low resolution"],
            },
            "aesthetic_critique": {
                "headline_insight": ev["headline_insight"].strip(),
                "proportion_and_order": ev["proportion_and_order"].strip(),
                "material_and_detail": ev["material_and_detail"].strip(),
                "light_and_palette": ev["light_and_palette"].strip(),
                "why_you_love_it": ev["why_you_love_it"].strip(),
                "design_takeaways": [x.strip() for x in ev["design_takeaways"][:3] if x.strip()],
                "resonance_mode": ev["resonance_mode"],
            },
            "rag_facets": rag_facets,
            "rag_doc": {
                "doc_id": aid,
                "archetype": dom,
                "archetype_en": dmeta["en"],
                "style_id": style_id,
                "style_zh": smeta["zh"],
                "style_en": smeta["en"],
                "native_style_primary": native_primary,
                "native_style_secondary": native_secondary,
                "is_canonical_ism": bool(ev["is_canonical_ism"]),
                "facets": rag_facets,
                "visual_traits": visual_traits,
                "model_prompt_tokens": model_prompt_tokens,
                "palette": palette,
                "aspect_ratio": aspect_lbl,
                "resonance_mode": ev["resonance_mode"],
                "retrieval_text": retrieval_text,
            },
        }
        new_ext_assets.append(asset_obj)

    # Also re-map personal 390 against EXTENDED_STYLE_CATALOG so newly admitted styles (Brutalism, Japandi) apply uniformly!
    for a in personal_390:
        disc = discovery_old.get(a["asset_id"])
        if not disc:
            continue
        dom = a["archetype"]
        new_sid = _map_style_with_admissions(dom, disc)
        if new_sid != a.get("aesthetic_style"):
            smeta = EXTENDED_STYLE_CATALOG[new_sid]
            a["aesthetic_style"] = new_sid
            a["aesthetic_style_zh"] = smeta["zh"]
            a["aesthetic_style_en"] = smeta["en"]
            a["sub_style"] = smeta["zh"]
            a["sub_category"] = smeta["zh"]
            if a.get("rag_doc"):
                a["rag_doc"]["style_id"] = new_sid
                a["rag_doc"]["style_zh"] = smeta["zh"]
                a["rag_doc"]["style_en"] = smeta["en"]

    all_500 = personal_390 + new_ext_assets
    assert len(all_500) == 500

    # Rebuild counts, taxonomy, schema & RAG JSONL
    arch_counts: Counter[str] = Counter()
    domain_counts_5: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    arch_style_counts: dict[str, Counter[str]] = defaultdict(Counter)
    facet_counts: dict[str, Counter[str]] = {
        "medium": Counter(),
        "typology": Counter(),
        "materials": Counter(),
        "lighting": Counter(),
    }
    rag_jsonl_lines: list[str] = []

    for a in all_500:
        dom = a["archetype"]
        sid = a["aesthetic_style"]
        arch_counts[dom] += 1
        domain_counts_5[a["subject_isolation"]["domain"]] += 1
        style_counts[sid] += 1
        arch_style_counts[dom][sid] += 1
        rf = a["rag_facets"]
        facet_counts["medium"][rf["medium"]] += 1
        facet_counts["typology"][rf["typology"]] += 1
        for m in rf["materials"]:
            facet_counts["materials"][m] += 1
        facet_counts["lighting"][rf["lighting"]] += 1

        crit = a["aesthetic_critique"]
        rag_jsonl_lines.append(
            json.dumps(
                {
                    **a["rag_doc"],
                    "title": a["title"],
                    "source_origin": a.get("source_origin", ""),
                    "image_url": a["image_url"],
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
                        "sub_style": EXTENDED_STYLE_CATALOG[sid]["zh"],
                        "style_id": sid,
                        "style_en": EXTENDED_STYLE_CATALOG[sid]["en"],
                        "is_movement": EXTENDED_STYLE_CATALOG[sid]["is_movement"],
                        "count": c,
                    }
                    for sid, c in sc.most_common()
                ],
            }
        )

    bundle["version"] = "5.1.0-pinterest-ext-rag-500"
    bundle["total_assets"] = 500
    bundle["domain_counts"] = dict(domain_counts_5)
    bundle["origin_counts"] = {"pinterest_personal": 390, "profile_expansion": 110}
    bundle["archetype_taxonomy"] = archetype_taxonomy
    bundle["archetype_counts"] = dict(arch_counts)
    bundle["assets"] = all_500
    bundle["rag_schema"] = {
        "schema_version": "2.1.0-pinterest-ext-domain-scoped",
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
                "zh": EXTENDED_STYLE_CATALOG[sid]["zh"],
                "en": EXTENDED_STYLE_CATALOG[sid]["en"],
                "is_movement": EXTENDED_STYLE_CATALOG[sid]["is_movement"],
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
    _build_contact_sheet(new_ext_paths, EXT_CONTACT_SHEET)

    print("\n=== v5.1 Final 500-Asset Atlas (390 Core Pinterest + 110 Fresh Pinterest Extensions) ===")
    for node in archetype_taxonomy:
        st_str = ", ".join(f"{s['sub_style']}({s['style_en']}:{s['count']})" for s in node["sub_styles"])
        print(f"  {node['label']} [{node['archetype']}]: {node['count']} -> {st_str}")
    print("\nTop Admitted Native Styles in New 110 Pinterest Extensions:")
    print(" ", ", ".join(f"{k}({v})" for k, v in admitted_raw_styles.most_common(15)))
    print(f"Contact Sheet: {EXT_CONTACT_SHEET} | Total Elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
