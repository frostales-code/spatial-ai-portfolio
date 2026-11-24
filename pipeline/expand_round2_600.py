"""Round-2 Extensive Non-Interior Pinterest Research Expansion (500 -> 600 Balanced Atlas).

Keeps all 500 existing curated assets intact (390 personal + 110 Round-1 Pinterest extensions),
adds +100 top-curated non-interior Pinterest extensions across all 7 underrepresented domains
(industrial, craft, fashion_photography, illustration_character, graphic_typography, landscape,
architecture), embeds them with `gemini-embedding-2`, recomputes the 600-asset 2D Semantic
Moodboard Canvas & Top-6 visual neighbors, and round-robin interleaves all 210 extensions across
all 8 domains so Page 1 immediately showcases every discipline.

Outputs:
  - `web/public/assets/pinterest_500/pext2_*.webp` (100 fresh non-interior WebPs)
  - `data/pinterest_500/contact_sheet_ext_round2_100.jpg`
  - `data/pinterest_500/embeddings_500.npz` (600 x 256 float32 + 600 x 2 map_2d)
  - `web/public/data/aethervault_personal_500.json` (`6.1.0-multimodal-rag-atlas-600`)
  - `data/pinterest_500/aethervault_assets_500.json`
  - `web/public/data/aethervault_rag_500.jsonl` (600 docs)
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
from typing import Any

import numpy as np
from google import genai
from google.genai import types
from PIL import Image

from .analyze_aesthetic_500 import _compute_aspect_info
from .atlas_rag_engine import _rebuild_bundle_aggregates
from .converge_gemini_rag_500 import (
    ARCHETYPE_META,
    ARCHETYPE_ORDER,
    _map_lighting,
    _map_materials,
    _map_medium,
    _map_typology,
)
from .expand_pinterest_gemini_500 import (
    DOMAIN_TO_LEGACY_5,
    EXTENDED_STYLE_CATALOG,
    SYSTEM_PROMPT,
    PinterestExtVlmEval,
    _build_contact_sheet,
    _dhash64,
    _extract_palette_hex,
    _hamming,
    _map_style_with_admissions,
)
from .upgrade_critiques_and_embeddings_500 import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    compute_2d_layout,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_ASSETS_DIR = WEB_PUBLIC_DIR / "assets" / "pinterest_500"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
EMB_NPZ_PATH = REPO_ROOT / "data" / "pinterest_500" / "embeddings_500.npz"

CANDIDATES_R2_JSON = REPO_ROOT / "data" / "pinterest_500" / "pinterest_extension_round2_321.json"
CANDIDATES_R2_DIR = REPO_ROOT / "data" / "pinterest_500" / "pinterest_ext_r2_candidates"
R2_GEMINI_CACHE = REPO_ROOT / "data" / "pinterest_500" / "_pinterest_ext_r2_gemini_cache.json"
R2_CONTACT_SHEET = REPO_ROOT / "data" / "pinterest_500" / "contact_sheet_ext_round2_100.jpg"

GEMINI_MODEL = "gemini-4-hydrogen"

# +100 non-interior extensions balanced across the 7 other visual domains
R2_QUOTAS: dict[str, int] = {
    "industrial": 22,
    "craft": 20,
    "fashion_photography": 14,
    "illustration_character": 14,
    "graphic_typography": 12,
    "landscape": 10,
    "architecture": 8,
}


def _download_one(idx: int, cand: dict[str, Any]) -> dict[str, Any] | None:
    CANDIDATES_R2_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CANDIDATES_R2_DIR / f"r2_{idx:03d}.webp"
    url = cand["image_url"]

    if out_path.is_file() and out_path.stat().st_size > 4000:
        return {**cand, "cand_id": f"r2_{idx:03d}", "local_path": str(out_path)}

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
            return {**cand, "cand_id": f"r2_{idx:03d}", "local_path": str(out_path)}
        except Exception:
            continue
    return None


def _eval_one(client: genai.Client, cand: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    img_bytes = Path(cand["local_path"]).read_bytes()
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
    raise RuntimeError(f"Gemini R2 eval failed for {cand['cand_id']}: {last_err}")


def _embed_one(client: genai.Client, aid: str, img_path: Path, text_summary: str) -> tuple[str, np.ndarray]:
    img_bytes = img_path.read_bytes()
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/webp"), text_summary],
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            vec = np.asarray(resp.embeddings[0].values, dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec = vec / norm
            return aid, vec
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Embed R2 failed for {aid}: {last_err}")


def _interleave_by_domain(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Round-robin interleave assets across all 8 domains so Page 1 shows full diversity."""
    order = (
        "industrial",
        "craft",
        "architecture",
        "graphic_typography",
        "fashion_photography",
        "illustration_character",
        "landscape",
        "interior",
    )
    buckets: dict[str, list[dict[str, Any]]] = {d: [] for d in order}
    for a in items:
        d = a.get("archetype", "interior")
        buckets.setdefault(d, []).append(a)
    out: list[dict[str, Any]] = []
    while True:
        progressed = False
        for d in order:
            if buckets[d]:
                out.append(buckets[d].pop(0))
                progressed = True
        if not progressed:
            break
    return out


def main() -> None:
    if not CANDIDATES_R2_JSON.is_file():
        raise FileNotFoundError(f"Missing Round-2 candidates JSON: {CANDIDATES_R2_JSON}")
    if not WEB_PERSONAL_JSON.is_file() or not EMB_NPZ_PATH.is_file():
        raise FileNotFoundError("Personal 500 JSON and embeddings_500.npz must exist first.")

    t0 = time.time()
    candidates = json.loads(CANDIDATES_R2_JSON.read_text(encoding="utf-8"))
    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    # Strip any previous pext2_* if re-running idempotently
    base_assets = [a for a in bundle["assets"] if not a["asset_id"].startswith("pext2_")]

    emb_data = np.load(EMB_NPZ_PATH, allow_pickle=False)
    old_ids = [str(x) for x in emb_data["asset_ids"].tolist()]
    old_vecs = emb_data["vectors"].astype(np.float32)
    vec_by_id = {aid: old_vecs[i] for i, aid in enumerate(old_ids)}

    print(f"Base atlas: {len(base_assets)} assets | Round-2 candidates: {len(candidates)}")

    # Step 1: Download all 321 candidates
    downloaded: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(_download_one, i, c): i for i, c in enumerate(candidates)}
        for fut in as_completed(futs):
            res = fut.result()
            if res is not None:
                downloaded.append(res)
    downloaded.sort(key=lambda x: x["cand_id"])
    print(f"Downloaded {len(downloaded)}/{len(candidates)} valid high-res WebPs ({time.time()-t0:.1f}s)")

    # Step 2: 64-bit dHash dedup against ALL 500 base assets + intra-candidates
    existing_hashes: list[int] = []
    for a in base_assets:
        p = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
        if p.is_file():
            existing_hashes.append(_dhash64(p))

    deduped: list[dict[str, Any]] = []
    seen_hashes: list[int] = []
    dup_base = 0
    dup_intra = 0
    for c in downloaded:
        h = _dhash64(Path(c["local_path"]))
        if any(_hamming(h, eh) <= 6 for eh in existing_hashes):
            dup_base += 1
            continue
        if any(_hamming(h, sh) <= 6 for sh in seen_hashes):
            dup_intra += 1
            continue
        seen_hashes.append(h)
        deduped.append(c)
    print(f"After pHash dedup: {len(deduped)} unique (skipped {dup_base} matching base 500, {dup_intra} intra-dup)")

    # Step 3: Gemini 4 Hydrogen evaluation
    cache: dict[str, dict[str, Any]] = {}
    if R2_GEMINI_CACHE.is_file():
        try:
            cache = json.loads(R2_GEMINI_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [c for c in deduped if c["cand_id"] not in cache]
    print(f"Gemini 4 Hydrogen R2 Eval: total={len(deduped)}, cached={len(cache)}, todo={len(todo)}")
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY required.")
    client = genai.Client(api_key=key)

    if todo:
        lock = threading.Lock()
        done = 0
        t_vlm = time.time()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {pool.submit(_eval_one, client, c): c["cand_id"] for c in todo}
            for fut in as_completed(futs):
                cid = futs[fut]
                try:
                    cand_id, payload = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] R2 eval failed {cid}: {exc}")
                    continue
                with lock:
                    cache[cand_id] = payload
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        R2_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        print(f"R2 VLM progress: {done}/{len(todo)} ({time.time()-t_vlm:.1f}s)")
        R2_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Step 4: Select top 100 NON-INTERIOR extensions proportionally
    scored_by_dom: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for c in deduped:
        ev = cache.get(c["cand_id"])
        if not ev:
            continue
        dom = ev["visual_domain"]
        if dom == "interior":
            continue  # Round 2 focuses strictly on the 7 non-interior domains!
        q = int(ev.get("keep_quality_score", 0))
        if q < 6:
            continue
        rank_score = q + float(ev.get("confidence", 0.8)) * 0.5
        scored_by_dom[dom].append((rank_score, c, ev))

    for dom in scored_by_dom:
        scored_by_dom[dom].sort(key=lambda x: -x[0])

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    selected_ids: set[str] = set()
    for dom, quota in R2_QUOTAS.items():
        for _, c, ev in scored_by_dom.get(dom, [])[:quota]:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    if len(selected) < 100:
        rem = [
            (score, c, ev)
            for dom_list in scored_by_dom.values()
            for (score, c, ev) in dom_list
            if c["cand_id"] not in selected_ids
        ]
        rem.sort(key=lambda x: -x[0])
        for _, c, ev in rem[: 100 - len(selected)]:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    print("Selected Round-2 non-interior extensions:", dict(Counter(ev["visual_domain"] for _, ev in selected)))

    # Step 5: Write 100 pext2_*.webp files and build Asset dicts
    for old_f in WEB_ASSETS_DIR.glob("pext2_*.webp"):
        old_f.unlink()

    r2_assets: list[dict[str, Any]] = []
    r2_paths: list[Path] = []
    for idx, (cand, ev) in enumerate(selected, start=1):
        dom = ev["visual_domain"]
        dmeta = ARCHETYPE_META[dom]
        aid = f"pext2_{dom[:4]}_{idx:03d}"
        dst_path = WEB_ASSETS_DIR / f"{aid}.webp"
        dst_path.write_bytes(Path(cand["local_path"]).read_bytes())
        r2_paths.append(dst_path)

        w, h, aspect_lbl = _compute_aspect_info(dst_path)
        palette = _extract_palette_hex(dst_path, k=5)
        style_id = _map_style_with_admissions(dom, ev)
        smeta = EXTENDED_STYLE_CATALOG[style_id]
        native_primary = " ".join(ev["free_style_primary"].strip().split())
        native_secondary = " ".join((ev.get("free_style_secondary") or "").strip().split())
        visual_traits = [t.strip() for t in ev.get("visual_traits", [])[:4] if t.strip()]

        medium_zh = _map_medium(dom, ev)
        typology_zh = _map_typology(dom, ev)
        materials_zh = _map_materials(dom, ev, [])
        spec = ev["style_spectrums"]
        drama = float(spec["lighting_drama"]["score"])
        warmth = float(spec["thermal_mood"]["score"])
        default_lgt = "戏剧硬影" if drama >= 0.4 else ("暖调氛围" if warmth >= 0.35 else ("漫射柔光" if drama <= -0.2 else "自然天光"))
        lighting_zh = _map_lighting(dom, {"style_spectrums": spec, "archetype": dom}, ev, default_lgt)

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
        legacy_dom, legacy_dom_zh = DOMAIN_TO_LEGACY_5[dom]

        r2_assets.append(
            {
                "asset_id": aid,
                "title": ev["title_zh"].strip(),
                "title_en": ev["primary_subject_en"].strip(),
                "image_url": f"/assets/pinterest_500/{aid}.webp",
                "width": w,
                "height": h,
                "aspect_label": aspect_lbl,
                "license": "Pinterest Aesthetic Extension (R2)",
                "source_kind": "pinterest_extension",
                "source_origin": "profile_expansion",
                "source_url": cand.get("pin_url", ""),
                "board_name": f"Pinterest 深度研究 · {cand.get('query', '')[:26]}",
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
        )

    # Step 6: Embed all 100 new assets with gemini-embedding-2
    t_e = time.time()
    print(f"Embedding {len(r2_assets)} new Round-2 assets via {EMBEDDING_MODEL} ({EMBEDDING_DIM}d)...")
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {
            pool.submit(
                _embed_one,
                client,
                a["asset_id"],
                WEB_PUBLIC_DIR / a["image_url"].lstrip("/"),
                a["rag_doc"]["retrieval_text"],
            ): a["asset_id"]
            for a in r2_assets
        }
        for fut in as_completed(futs):
            aid, vec = fut.result()
            vec_by_id[aid] = vec
    print(f"Embedded {len(r2_assets)} Round-2 assets in {time.time()-t_e:.1f}s")

    # Step 7: Round-robin interleave ALL 210 profile_expansion assets across the 8 domains!
    personal_core = [a for a in base_assets if a.get("source_origin") == "pinterest_personal"]
    old_ext = [a for a in base_assets if a.get("source_origin") != "pinterest_personal"]
    # Put fresh R2 + R1 extensions interleaved across all 8 domains (starting with non-interior!)
    interleaved_ext = _interleave_by_domain(r2_assets + old_ext)
    all_assets = personal_core + interleaved_ext
    print(f"Final Atlas total: {len(all_assets)} (personal={len(personal_core)}, interleaved_ext={len(interleaved_ext)})")

    # Recompute 600-asset 2D Semantic Moodboard Canvas + Top-6 Visual Neighbors
    final_ids = [a["asset_id"] for a in all_assets]
    final_vecs = np.asarray([vec_by_id[aid] for aid in final_ids], dtype=np.float32)
    final_vecs = final_vecs / np.maximum(np.linalg.norm(final_vecs, axis=1, keepdims=True), 1e-8)

    map_2d = compute_2d_layout(final_vecs)
    sim_matrix = final_vecs @ final_vecs.T

    for idx, a in enumerate(all_assets):
        a["map_2d"] = {
            "x": round(float(map_2d[idx, 0]), 5),
            "y": round(float(map_2d[idx, 1]), 5),
        }
        sims = sim_matrix[idx].copy()
        sims[idx] = -2.0
        top_idx = np.argsort(-sims)[:6]
        a["similar_ids"] = [
            {"asset_id": final_ids[j], "score": round(float(sims[j]), 4)}
            for j in top_idx
        ]

    bundle["version"] = "6.1.0-multimodal-rag-atlas-600"
    bundle["assets"] = all_assets
    rag_jsonl_lines = _rebuild_bundle_aggregates(bundle)

    np.savez_compressed(
        EMB_NPZ_PATH,
        asset_ids=np.asarray(final_ids),
        vectors=final_vecs,
        map_2d=map_2d,
    )
    WEB_PERSONAL_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    ASSETS_500_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")
    _build_contact_sheet(r2_paths, R2_CONTACT_SHEET)

    print("\n=== v6.1 Final 600-Asset Balanced Atlas (390 Personal + 210 Cross-Domain Pinterest Extensions) ===")
    ext_by_dom = Counter(a["archetype_label"] for a in interleaved_ext)
    all_by_dom = Counter(a["archetype_label"] for a in all_assets)
    for dom in ARCHETYPE_ORDER:
        lbl = ARCHETYPE_META[dom]["zh"]
        print(f"  {lbl}: total={all_by_dom[lbl]} (extensions={ext_by_dom[lbl]})")
    print("First 12 cards of 同频扩展 (round-robin interleaved):", [a["archetype_label"] for a in interleaved_ext[:12]])
    print(f"Contact Sheet: {R2_CONTACT_SHEET} | Total Elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
