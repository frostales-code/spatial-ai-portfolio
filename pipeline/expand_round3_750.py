"""Round-3 Extensive Multi-Domain Pinterest Expansion (600 -> 750 Balanced 3D Atlas).

Keeps all 600 existing curated assets intact (390 personal + 210 R1/R2 Pinterest extensions),
adds +150 top-curated Pinterest extensions concentrated in the 6 thinner domains
(industrial +35, fashion_photography +35, craft +30, illustration_character +18,
landscape +18, graphic_typography +14), embeds them with `gemini-embedding-2` (256d),
recomputes the full 750-asset 2D + 3D Cosine t-SNE (`map_2d`, `map_3d`), real personal-core
gravitational `core_distance`, and Top-10 connected visual neighbors, and round-robin
interleaves all 360 extensions across all 8 domains.

Never modifies the public 80-asset showcase (`web/public/data/aethervault_showcase_v1.json`).
"""

from __future__ import annotations

import io
import json
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
from sklearn.manifold import TSNE

from .analyze_aesthetic_500 import _compute_aspect_info
from .atlas_rag_engine import _rebuild_bundle_aggregates
from .compute_constellation_3d import _count_connected_components, _normalize_3d
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
from .expand_round2_600 import _embed_one, _eval_one, _interleave_by_domain
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

CANDIDATES_R3_JSON = REPO_ROOT / "data" / "pinterest_500" / "pinterest_extension_round3_candidates.json"
CANDIDATES_R3_DIR = REPO_ROOT / "data" / "pinterest_500" / "pinterest_ext_r3_candidates"
R3_GEMINI_CACHE = REPO_ROOT / "data" / "pinterest_500" / "_pinterest_ext_r3_gemini_cache.json"
R3_CONTACT_SHEET = REPO_ROOT / "data" / "pinterest_500" / "contact_sheet_ext_round3_150.jpg"

TARGET_NEW_COUNT = 150

# +150 fresh extensions concentrated in the 6 thinner visual domains
R3_QUOTAS: dict[str, int] = {
    "industrial": 35,
    "fashion_photography": 35,
    "craft": 30,
    "illustration_character": 18,
    "landscape": 18,
    "graphic_typography": 14,
}


def _download_one(idx: int, cand: dict[str, Any]) -> dict[str, Any] | None:
    CANDIDATES_R3_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CANDIDATES_R3_DIR / f"r3_{idx:03d}.webp"
    url = cand["image_url"]

    if out_path.is_file() and out_path.stat().st_size > 4000:
        return {**cand, "cand_id": f"r3_{idx:03d}", "local_path": str(out_path)}

    urls_to_try = [url]
    if "/originals/" in url:
        urls_to_try.append(url.replace("/originals/", "/736x/"))
    elif "/736x/" in url:
        urls_to_try.append(url.replace("/736x/", "/564x/"))

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
            return {**cand, "cand_id": f"r3_{idx:03d}", "local_path": str(out_path)}
        except Exception:
            continue
    return None


def main() -> None:
    t0 = time.time()
    if not CANDIDATES_R3_JSON.is_file():
        raise FileNotFoundError(f"Missing Round-3 candidates JSON: {CANDIDATES_R3_JSON}")

    raw_cands = json.loads(CANDIDATES_R3_JSON.read_text(encoding="utf-8"))
    # Dedup raw candidate URLs first
    seen_urls: set[str] = set()
    cands: list[dict[str, Any]] = []
    for c in raw_cands:
        u = str(c.get("image_url", "")).strip()
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        cands.append(c)

    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    # Idempotent: keep existing non-pext3 base assets (600)
    base_assets = [a for a in bundle["assets"] if not a["asset_id"].startswith("pext3_")]
    emb_data = np.load(EMB_NPZ_PATH, allow_pickle=False)
    emb_ids = [str(x) for x in emb_data["asset_ids"].tolist()]
    emb_vecs = emb_data["vectors"].astype(np.float32)
    vec_by_id = {aid: emb_vecs[i] for i, aid in enumerate(emb_ids)}

    print(f"Base Atlas: {len(base_assets)} assets | Raw unique Round-3 candidates: {len(cands)}")

    # Step 1: Parallel download of Round-3 Pinterest candidates
    downloaded: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(_download_one, i, c) for i, c in enumerate(cands)]
        for fut in as_completed(futs):
            res = fut.result()
            if res:
                downloaded.append(res)
    downloaded.sort(key=lambda x: x["cand_id"])
    print(f"Downloaded valid high-res Round-3 candidates: {len(downloaded)}/{len(cands)} ({time.time()-t0:.1f}s)")

    # Step 2: 64-bit dHash perceptual deduplication against all 600 existing assets + intra-batch
    base_hashes: list[int] = []
    for a in base_assets:
        p = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
        if p.is_file():
            try:
                base_hashes.append(_dhash64(p))
            except Exception:
                pass

    deduped: list[dict[str, Any]] = []
    seen_hashes: list[int] = []
    dup_base = 0
    dup_intra = 0
    for c in downloaded:
        h = _dhash64(Path(c["local_path"]))
        if any(_hamming(h, bh) <= 7 for bh in base_hashes):
            dup_base += 1
            continue
        if any(_hamming(h, sh) <= 6 for sh in seen_hashes):
            dup_intra += 1
            continue
        seen_hashes.append(h)
        deduped.append(c)
    print(f"After pHash dedup: {len(deduped)} unique (skipped {dup_base} matching base 600, {dup_intra} intra-dup)")

    # Step 3: Gemini 4 Hydrogen visual evaluation
    cache: dict[str, dict[str, Any]] = {}
    if R3_GEMINI_CACHE.is_file():
        try:
            cache = json.loads(R3_GEMINI_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [c for c in deduped if c["cand_id"] not in cache]
    print(f"Gemini 4 Hydrogen R3 Eval: total={len(deduped)}, cached={len(cache)}, todo={len(todo)}")
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
                    print(f"[WARN] R3 eval failed {cid}: {exc}")
                    continue
                with lock:
                    cache[cand_id] = payload
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        R3_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        print(f"R3 VLM progress: {done}/{len(todo)} ({time.time()-t_vlm:.1f}s)")
        R3_GEMINI_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Step 4: Curate top TARGET_NEW_COUNT (150) across the 6 targeted thinner domains
    scored_by_dom: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for c in deduped:
        ev = cache.get(c["cand_id"])
        if not ev:
            continue
        dom = ev["visual_domain"]
        if dom in {"interior", "architecture"}:
            continue  # Round 3 focuses exclusively on the 6 thinner domains!
        q = int(ev.get("keep_quality_score", 0))
        if q < 6:
            continue
        rank_score = q + float(ev.get("confidence", 0.8)) * 0.5
        scored_by_dom[dom].append((rank_score, c, ev))

    for dom in scored_by_dom:
        scored_by_dom[dom].sort(key=lambda x: -x[0])

    print("Eligible R3 pool per domain:", {k: len(v) for k, v in scored_by_dom.items()})

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    selected_ids: set[str] = set()
    for dom, quota in R3_QUOTAS.items():
        for _, c, ev in scored_by_dom.get(dom, [])[:quota]:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    if len(selected) < TARGET_NEW_COUNT:
        rem = [
            (score, c, ev)
            for dom_list in scored_by_dom.values()
            for (score, c, ev) in dom_list
            if c["cand_id"] not in selected_ids
        ]
        rem.sort(key=lambda x: -x[0])
        for _, c, ev in rem[: TARGET_NEW_COUNT - len(selected)]:
            selected.append((c, ev))
            selected_ids.add(c["cand_id"])

    print(f"Selected Round-3 extensions ({len(selected)}):", dict(Counter(ev["visual_domain"] for _, ev in selected)))

    # Step 5: Write pext3_*.webp files & build Asset dicts
    for old_f in WEB_ASSETS_DIR.glob("pext3_*.webp"):
        old_f.unlink()

    r3_assets: list[dict[str, Any]] = []
    r3_paths: list[Path] = []
    for idx, (cand, ev) in enumerate(selected, start=1):
        dom = ev["visual_domain"]
        dmeta = ARCHETYPE_META[dom]
        aid = f"pext3_{dom[:4]}_{idx:03d}"
        dst_path = WEB_ASSETS_DIR / f"{aid}.webp"
        dst_path.write_bytes(Path(cand["local_path"]).read_bytes())
        r3_paths.append(dst_path)

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
        default_lgt = (
            "戏剧硬影"
            if drama >= 0.4
            else ("暖调氛围" if warmth >= 0.35 else ("漫射柔光" if drama <= -0.2 else "自然天光"))
        )
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

        r3_assets.append(
            {
                "asset_id": aid,
                "title": ev["title_zh"].strip(),
                "title_en": ev["primary_subject_en"].strip(),
                "image_url": f"/assets/pinterest_500/{aid}.webp",
                "width": w,
                "height": h,
                "aspect_label": aspect_lbl,
                "license": "Pinterest Aesthetic Extension (R3)",
                "source_kind": "pinterest_extension",
                "source_origin": "profile_expansion",
                "source_url": cand.get("pin_url", ""),
                "board_name": f"Pinterest 深度扩展 R3 · {cand.get('query', '')[:24]}",
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

    # Step 6: Embed all new R3 assets via Gemini Embedding 2 (dim=256)
    t_e = time.time()
    print(f"Embedding {len(r3_assets)} Round-3 assets via {EMBEDDING_MODEL} ({EMBEDDING_DIM}d)...")
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {
            pool.submit(
                _embed_one,
                client,
                a["asset_id"],
                WEB_PUBLIC_DIR / a["image_url"].lstrip("/"),
                a["rag_doc"]["retrieval_text"],
            ): a["asset_id"]
            for a in r3_assets
        }
        for fut in as_completed(futs):
            aid, vec = fut.result()
            vec_by_id[aid] = vec
    print(f"Embedded {len(r3_assets)} Round-3 assets in {time.time()-t_e:.1f}s")

    # Step 7: Interleave ALL extensions across all 8 domains (R3 fresh pins first!)
    personal_core = [a for a in base_assets if a.get("source_origin") == "pinterest_personal"]
    old_ext = [a for a in base_assets if a.get("source_origin") != "pinterest_personal"]
    interleaved_ext = _interleave_by_domain(r3_assets + old_ext)
    all_assets = personal_core + interleaved_ext
    n = len(all_assets)
    print(f"Final Atlas total: {n} (personal={len(personal_core)}, interleaved_ext={len(interleaved_ext)})")

    # Step 8: Recompute 2D + 3D Cosine t-SNE, Personal Core Distance, and Top-10 Connected Neighbors
    final_ids = [a["asset_id"] for a in all_assets]
    final_vecs = np.asarray([vec_by_id[aid] for aid in final_ids], dtype=np.float32)
    final_vecs = final_vecs / np.maximum(np.linalg.norm(final_vecs, axis=1, keepdims=True), 1e-8)

    map_2d = compute_2d_layout(final_vecs)

    print(f"Computing 3D cosine t-SNE for {n} assets...")
    tsne_3d = TSNE(
        n_components=3,
        metric="cosine",
        perplexity=min(34, max(10, n // 20)),
        init="pca",
        learning_rate="auto",
        max_iter=1200,
        random_state=42,
    )
    map_3d = _normalize_3d(tsne_3d.fit_transform(final_vecs))

    personal_indices = [
        i for i, a in enumerate(all_assets) if a.get("source_origin") != "profile_expansion"
    ]
    core_centroid = final_vecs[personal_indices].mean(axis=0)
    core_norm = float(np.linalg.norm(core_centroid))
    if core_norm > 1e-8:
        core_centroid = (core_centroid / core_norm).astype(np.float32)
    raw_dists = 1.0 - (final_vecs @ core_centroid)
    ranks = np.argsort(np.argsort(raw_dists))
    core_distances = (ranks / max(1, n - 1)).astype(np.float32)

    sim_matrix = final_vecs @ final_vecs.T
    np.fill_diagonal(sim_matrix, -2.0)

    k_neighbors = 10
    undirected_adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for idx, a in enumerate(all_assets):
        a["map_2d"] = {
            "x": round(float(map_2d[idx, 0]), 5),
            "y": round(float(map_2d[idx, 1]), 5),
        }
        a["map_3d"] = {
            "x": round(float(map_3d[idx, 0]), 5),
            "y": round(float(map_3d[idx, 1]), 5),
            "z": round(float(map_3d[idx, 2]), 5),
        }
        a["core_distance"] = round(float(core_distances[idx]), 4)
        top_idx = np.argsort(-sim_matrix[idx])[:k_neighbors]
        a["similar_ids"] = [
            {"asset_id": final_ids[j], "score": round(float(sim_matrix[idx, j]), 4)}
            for j in top_idx
        ]
        for j in top_idx:
            undirected_adj[idx].add(int(j))
            undirected_adj[int(j)].add(idx)

    comps, largest = _count_connected_components(undirected_adj, n)
    print(f"k={k_neighbors} neighbor graph connectivity: {comps} component(s), largest={largest}/{n}")

    bundle["version"] = f"6.3.0-constellation-3d-atlas-{n}"
    bundle["schema_version"] = f"6.3.0-constellation-3d-atlas-{n}"
    bundle["assets"] = all_assets
    rag_jsonl_lines = _rebuild_bundle_aggregates(bundle)

    np.savez_compressed(
        EMB_NPZ_PATH,
        asset_ids=np.asarray(final_ids),
        vectors=final_vecs,
        map_2d=map_2d,
        map_3d=map_3d,
        core_centroid=core_centroid,
        core_distances=core_distances,
    )
    serialized = json.dumps(bundle, ensure_ascii=False, indent=2)
    WEB_PERSONAL_JSON.write_text(serialized, encoding="utf-8")
    ASSETS_500_JSON.write_text(serialized, encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")
    _build_contact_sheet(r3_paths, R3_CONTACT_SHEET)

    print(f"\n=== v6.3 Final {n}-Asset Balanced 3D Atlas ({len(personal_core)} Personal + {len(interleaved_ext)} Extensions) ===")
    ext_by_dom = Counter(a["archetype_label"] for a in interleaved_ext)
    all_by_dom = Counter(a["archetype_label"] for a in all_assets)
    for dom in ARCHETYPE_ORDER:
        lbl = ARCHETYPE_META[dom]["zh"]
        print(f"  {lbl}: total={all_by_dom[lbl]} (extensions={ext_by_dom[lbl]})")
    print("First 12 cards of 同频扩展:", [a["archetype_label"] for a in interleaved_ext[:12]])
    print(f"Contact Sheet: {R3_CONTACT_SHEET} | Total Elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
