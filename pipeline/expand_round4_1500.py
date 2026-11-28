"""Round-4 Balanced Multi-Domain Pinterest Expansion (750 -> 1500 3D Constellation Atlas).

Keeps all 750 existing curated assets intact (390 personal + 360 R1/R2/R3 extensions),
merges fresh Round-4 Pinterest candidates (814 scraped pins focused on landscape,
illustration, craft, fashion, industrial, and graphic) with the high-scoring (>=8)
unused R1-R3 on-disk cached pool (555 pins, zero redundant VLM cost), enforces strict
URL + 64-bit dHash perceptual deduplication, curates the top +750 assets balanced
across all 8 visual domains (170-210 per domain, total 1500), embeds them with
`gemini-embedding-2` (256d) with incremental JSON checkpointing, recomputes the full
1500-asset 2D + 3D Cosine t-SNE (`map_2d`, `map_3d`), personal-core `core_distance`,
and Top-10 connected visual neighbors, and round-robin interleaves all 1110 extensions.

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
DATA_DIR = REPO_ROOT / "data" / "pinterest_500"
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_ASSETS_DIR = WEB_PUBLIC_DIR / "assets" / "pinterest_500"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = DATA_DIR / "aethervault_assets_500.json"
EMB_NPZ_PATH = DATA_DIR / "embeddings_500.npz"

CANDIDATES_R4_JSON = DATA_DIR / "pinterest_extension_round4_candidates.json"
CANDIDATES_R4_DIR = DATA_DIR / "pinterest_ext_r4_candidates"
R4_GEMINI_CACHE = DATA_DIR / "_pinterest_ext_r4_gemini_cache.json"
R4_EMB_CACHE = DATA_DIR / "_pinterest_ext_r4_embeddings_cache.json"
R4_CONTACT_SHEET = DATA_DIR / "contact_sheet_ext_round4_750.jpg"

TARGET_NEW_COUNT = 750

# Balanced 8-domain quotas (+750 -> exact 1500: every domain 170-210)
# Base 750: interior 166, architecture 128, graphic 104, landscape 79,
#           illustration 75, craft 67, industrial 66, fashion 65
R4_QUOTAS: dict[str, int] = {
    "architecture": 82,           # 128 -> 210
    "interior": 39,               # 166 -> 205
    "graphic_typography": 91,     # 104 -> 195
    "industrial": 119,            # 66  -> 185
    "fashion_photography": 120,   # 65  -> 185
    "craft": 108,                 # 67  -> 175
    "illustration_character": 100,  # 75 -> 175
    "landscape": 91,              # 79  -> 170
}

PRIOR_POOLS = [
    ("R1", "pinterest_extension_candidates_273.json", "_pinterest_ext_gemini_cache.json", "cand", "pinterest_ext_candidates"),
    ("R2", "pinterest_extension_round2_321.json", "_pinterest_ext_r2_gemini_cache.json", "r2", "pinterest_ext_r2_candidates"),
    ("R3", "pinterest_extension_round3_candidates.json", "_pinterest_ext_r3_gemini_cache.json", "r3", "pinterest_ext_r3_candidates"),
]


def _download_one(idx: int, cand: dict[str, Any]) -> dict[str, Any] | None:
    CANDIDATES_R4_DIR.mkdir(parents=True, exist_ok=True)
    cid = f"r4_{idx:03d}"
    out_path = CANDIDATES_R4_DIR / f"{cid}.webp"
    url = cand["image_url"]

    if out_path.is_file() and out_path.stat().st_size > 4000:
        return {**cand, "cand_id": cid, "local_path": str(out_path), "pool_tag": "R4"}

    urls_to_try = [url]
    if "/originals/" in url:
        urls_to_try.append(url.replace("/originals/", "/736x/"))
        urls_to_try.append(url.replace("/originals/", "/564x/"))
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
            return {**cand, "cand_id": cid, "local_path": str(out_path), "pool_tag": "R4"}
        except Exception:
            continue
    return None


def _embed_one_resilient(
    client: genai.Client, aid: str, img_path: Path, text_summary: str
) -> tuple[str, np.ndarray]:
    img_bytes = img_path.read_bytes()
    last_err: Exception | None = None
    for attempt in range(8):
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
            time.sleep(0.08)
            return aid, vec
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait_s = min(90.0, 15.0 * (attempt + 1))
            else:
                wait_s = min(15.0, 2.0 * (attempt + 1))
            time.sleep(wait_s)
    raise RuntimeError(f"Embed R4 failed for {aid}: {last_err}")


def main() -> None:
    t0 = time.time()
    if not CANDIDATES_R4_JSON.is_file():
        raise FileNotFoundError(f"Missing Round-4 candidates JSON: {CANDIDATES_R4_JSON}")

    raw_cands = json.loads(CANDIDATES_R4_JSON.read_text(encoding="utf-8"))
    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    # Idempotent: keep existing non-pext4 base assets (750)
    base_assets = [a for a in bundle["assets"] if not a["asset_id"].startswith("pext4_")]
    emb_data = np.load(EMB_NPZ_PATH, allow_pickle=False)
    emb_ids = [str(x) for x in emb_data["asset_ids"].tolist()]
    emb_vecs = emb_data["vectors"].astype(np.float32)
    vec_by_id = {aid: emb_vecs[i] for i, aid in enumerate(emb_ids)}

    existing_source_urls = {a.get("source_url", "") for a in base_assets if a.get("source_url")}
    seen_pin_urls: set[str] = set(existing_source_urls)
    seen_img_urls: set[str] = set()

    # Dedup raw R4 candidate URLs against existing 750 and intra-list
    cands: list[dict[str, Any]] = []
    for c in raw_cands:
        iu = str(c.get("image_url", "")).strip()
        pu = str(c.get("pin_url", "")).strip()
        if not iu or iu in seen_img_urls or (pu and pu in seen_pin_urls):
            continue
        seen_img_urls.add(iu)
        if pu:
            seen_pin_urls.add(pu)
        cands.append(c)

    print(f"Base Atlas: {len(base_assets)} assets | Fresh unique R4 candidates: {len(cands)}")

    # Step 1: Parallel download of fresh Round-4 Pinterest candidates
    downloaded_r4: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_download_one, i, c) for i, c in enumerate(cands)]
        for fut in as_completed(futs):
            res = fut.result()
            if res:
                downloaded_r4.append(res)
    downloaded_r4.sort(key=lambda x: x["cand_id"])
    print(f"Downloaded valid high-res R4 candidates: {len(downloaded_r4)}/{len(cands)} ({time.time()-t0:.1f}s)")

    # Step 2: 64-bit dHash perceptual deduplication against all 750 base assets + intra-batch
    base_hashes: list[int] = []
    for a in base_assets:
        p = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
        if p.is_file():
            try:
                base_hashes.append(_dhash64(p))
            except Exception:
                pass

    deduped_r4: list[dict[str, Any]] = []
    seen_hashes: list[int] = []
    dup_base = 0
    dup_intra = 0
    for c in downloaded_r4:
        h = _dhash64(Path(c["local_path"]))
        if any(_hamming(h, bh) <= 7 for bh in base_hashes):
            dup_base += 1
            continue
        if any(_hamming(h, sh) <= 6 for sh in seen_hashes):
            dup_intra += 1
            continue
        seen_hashes.append(h)
        deduped_r4.append(c)
    print(f"R4 after dHash dedup: {len(deduped_r4)} unique (skipped {dup_base} base-dup, {dup_intra} intra-dup)")

    # Step 3: Gemini 4 Hydrogen visual evaluation on fresh R4 candidates
    r4_cache: dict[str, dict[str, Any]] = {}
    if R4_GEMINI_CACHE.is_file():
        try:
            r4_cache = json.loads(R4_GEMINI_CACHE.read_text(encoding="utf-8"))
        except Exception:
            r4_cache = {}

    todo = [c for c in deduped_r4 if c["cand_id"] not in r4_cache]
    if len(r4_cache) >= 650:
        print(f"Gemini 4 Hydrogen R4 Eval: cached={len(r4_cache)} (>=650 sufficient pool); skipping {len(todo)} extra calls to preserve spend rate.")
        todo = []
    else:
        print(f"Gemini 4 Hydrogen R4 Eval: total={len(deduped_r4)}, cached={len(r4_cache)}, todo={len(todo)}")
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
                    print(f"[WARN] R4 eval failed {cid}: {exc}")
                    continue
                with lock:
                    r4_cache[cand_id] = payload
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        R4_GEMINI_CACHE.write_text(json.dumps(r4_cache, ensure_ascii=False), encoding="utf-8")
                        print(f"R4 VLM progress: {done}/{len(todo)} ({time.time()-t_vlm:.1f}s)")
        R4_GEMINI_CACHE.write_text(json.dumps(r4_cache, ensure_ascii=False), encoding="utf-8")

    # Step 4: Merge unused cached R1-R3 candidates (zero extra VLM cost) with fresh R4 pool
    scored_by_dom: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = defaultdict(list)

    # 4a) Add evaluated fresh R4 candidates first
    r4_usable = 0
    for c in deduped_r4:
        ev = r4_cache.get(c["cand_id"])
        if not isinstance(ev, dict):
            continue
        dom = ev.get("visual_domain", "")
        if dom not in ARCHETYPE_META:
            continue
        q = int(ev.get("keep_quality_score", 0))
        if q < 7:
            continue
        # Slight +0.05 freshness tie-breaker for newly scraped R4 pins
        rank_score = q + float(ev.get("confidence", 0.8)) * 0.5 + 0.05
        scored_by_dom[dom].append((rank_score, c, ev))
        r4_usable += 1

    # 4b) Add unused, already-evaluated R1-R3 on-disk candidates (dHash & URL clean)
    prior_usable = 0
    for tag, cand_fn, cache_fn, prefix, cdir in PRIOR_POOLS:
        cand_file = DATA_DIR / cand_fn
        cache_file = DATA_DIR / cache_fn
        if not cand_file.is_file() or not cache_file.is_file():
            continue
        p_cands = json.loads(cand_file.read_text(encoding="utf-8"))
        p_cache = json.loads(cache_file.read_text(encoding="utf-8"))
        for idx, item in enumerate(p_cands):
            ck = f"{prefix}_{idx:03d}"
            ev = p_cache.get(ck)
            if not isinstance(ev, dict):
                continue
            dom = ev.get("visual_domain", "")
            if dom not in ARCHETYPE_META:
                continue
            q = int(ev.get("keep_quality_score", 0))
            if q < 7:
                continue
            pu = str(item.get("pin_url", "")).strip()
            iu = str(item.get("image_url", "")).strip()
            if (pu and pu in seen_pin_urls) or (iu and iu in seen_img_urls):
                continue
            fp = DATA_DIR / cdir / f"{ck}.webp"
            if not fp.is_file() or fp.stat().st_size < 4000:
                continue
            h = _dhash64(fp)
            if any(_hamming(h, bh) <= 7 for bh in base_hashes):
                continue
            if any(_hamming(h, sh) <= 6 for sh in seen_hashes):
                continue
            seen_hashes.append(h)
            if pu:
                seen_pin_urls.add(pu)
            if iu:
                seen_img_urls.add(iu)
            cand_rec = {
                **item,
                "cand_id": f"{tag.lower()}_{ck}",
                "local_path": str(fp),
                "pool_tag": tag,
            }
            rank_score = q + float(ev.get("confidence", 0.8)) * 0.5
            scored_by_dom[dom].append((rank_score, cand_rec, ev))
            prior_usable += 1

    for dom in scored_by_dom:
        scored_by_dom[dom].sort(key=lambda x: -x[0])

    print(f"Unified eligible pool: R4={r4_usable} + Prior(R1-R3)={prior_usable} = {r4_usable + prior_usable}")
    print("Eligible per domain:", {k: len(v) for k, v in scored_by_dom.items()})

    # Step 5: Curate exact TARGET_NEW_COUNT (750) across all 8 domains
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    selected_ids: set[str] = set()
    for dom, quota in R4_QUOTAS.items():
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

    if len(selected) != TARGET_NEW_COUNT:
        raise RuntimeError(f"Expected {TARGET_NEW_COUNT} selected assets, got {len(selected)}")

    pool_mix = Counter(c.get("pool_tag", "R4") for c, _ in selected)
    score_mix = Counter(int(ev.get("keep_quality_score", 0)) for _, ev in selected)
    print(f"Selected Round-4 batch ({len(selected)}): domains={dict(Counter(ev['visual_domain'] for _, ev in selected))}")
    print(f"  pool_mix={dict(pool_mix)} | quality_scores={dict(sorted(score_mix.items()))}")

    # Step 6: Write pext4_*.webp files & build Asset dicts
    for old_f in WEB_ASSETS_DIR.glob("pext4_*.webp"):
        old_f.unlink()

    r4_assets: list[dict[str, Any]] = []
    r4_paths: list[Path] = []
    cand_id_by_aid: dict[str, str] = {}
    for idx, (cand, ev) in enumerate(selected, start=1):
        dom = ev["visual_domain"]
        dmeta = ARCHETYPE_META[dom]
        aid = f"pext4_{dom[:4]}_{idx:03d}"
        dst_path = WEB_ASSETS_DIR / f"{aid}.webp"
        dst_path.write_bytes(Path(cand["local_path"]).read_bytes())
        r4_paths.append(dst_path)
        cand_id_by_aid[aid] = cand["cand_id"]

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
        q_lbl = (cand.get("query") or "").strip()[:28] or dmeta["en"]
        pool_tag = cand.get("pool_tag", "R4")

        r4_assets.append(
            {
                "asset_id": aid,
                "title": ev["title_zh"].strip(),
                "title_en": ev["primary_subject_en"].strip(),
                "image_url": f"/assets/pinterest_500/{aid}.webp",
                "width": w,
                "height": h,
                "aspect_label": aspect_lbl,
                "license": f"Pinterest Aesthetic Extension (R4/{pool_tag})",
                "source_kind": "pinterest_extension",
                "source_origin": "profile_expansion",
                "source_url": cand.get("pin_url", ""),
                "board_name": f"Pinterest 深度扩展 R4 · {q_lbl}",
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

    # Step 7: Embed all 750 new R4 assets via Gemini Embedding 2 (dim=256) with JSON checkpoint
    emb_cache: dict[str, list[float]] = {}
    if R4_EMB_CACHE.is_file():
        try:
            emb_cache = json.loads(R4_EMB_CACHE.read_text(encoding="utf-8"))
        except Exception:
            emb_cache = {}

    emb_todo = [a for a in r4_assets if cand_id_by_aid[a["asset_id"]] not in emb_cache]
    for a in r4_assets:
        ck = cand_id_by_aid[a["asset_id"]]
        if ck in emb_cache:
            vec_by_id[a["asset_id"]] = np.asarray(emb_cache[ck], dtype=np.float32)

    t_e = time.time()
    print(f"Embedding R4 assets via {EMBEDDING_MODEL} ({EMBEDDING_DIM}d): cached={len(r4_assets)-len(emb_todo)}, todo={len(emb_todo)}")
    if emb_todo:
        elock = threading.Lock()
        edone = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {
                pool.submit(
                    _embed_one_resilient,
                    client,
                    a["asset_id"],
                    WEB_PUBLIC_DIR / a["image_url"].lstrip("/"),
                    a["rag_doc"]["retrieval_text"],
                ): a["asset_id"]
                for a in emb_todo
            }
            for fut in as_completed(futs):
                aid, vec = fut.result()
                ck = cand_id_by_aid[aid]
                with elock:
                    vec_by_id[aid] = vec
                    emb_cache[ck] = [round(float(x), 6) for x in vec.tolist()]
                    edone += 1
                    if edone % 25 == 0 or edone == len(emb_todo):
                        R4_EMB_CACHE.write_text(json.dumps(emb_cache), encoding="utf-8")
                        print(f"R4 Embedding progress: {edone}/{len(emb_todo)} ({time.time()-t_e:.1f}s)")
        R4_EMB_CACHE.write_text(json.dumps(emb_cache), encoding="utf-8")
    print(f"All {len(r4_assets)} R4 embeddings ready ({time.time()-t_e:.1f}s)")

    # Step 8: Interleave ALL extensions across all 8 domains (R4 fresh pins first!)
    personal_core = [a for a in base_assets if a.get("source_origin") == "pinterest_personal"]
    old_ext = [a for a in base_assets if a.get("source_origin") != "pinterest_personal"]
    interleaved_ext = _interleave_by_domain(r4_assets + old_ext)
    all_assets = personal_core + interleaved_ext
    n = len(all_assets)
    print(f"Final Atlas total: {n} (personal={len(personal_core)}, interleaved_ext={len(interleaved_ext)})")

    # Step 9: Recompute 2D + 3D Cosine t-SNE, Personal Core Distance, and Top-10 Connected Neighbors
    final_ids = [a["asset_id"] for a in all_assets]
    final_vecs = np.asarray([vec_by_id[aid] for aid in final_ids], dtype=np.float32)
    final_vecs = final_vecs / np.maximum(np.linalg.norm(final_vecs, axis=1, keepdims=True), 1e-8)

    print(f"Computing 2D cosine t-SNE layout for {n} assets...")
    map_2d = compute_2d_layout(final_vecs)

    print(f"Computing 3D cosine t-SNE for {n} assets...")
    tsne_3d = TSNE(
        n_components=3,
        metric="cosine",
        perplexity=min(38, max(12, n // 30)),
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

    bundle["version"] = f"6.4.0-constellation-3d-atlas-{n}"
    bundle["schema_version"] = f"6.4.0-constellation-3d-atlas-{n}"
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
    # Compact JSON for fast browser fetch at 1500 items (~28% smaller than indented)
    serialized_compact = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    WEB_PERSONAL_JSON.write_text(serialized_compact, encoding="utf-8")
    ASSETS_500_JSON.write_text(serialized_compact, encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")
    # Build a clean 150-tile contact sheet sampling evenly across all 750 new assets
    step = max(1, len(r4_paths) // 150)
    _build_contact_sheet(r4_paths[::step][:150], R4_CONTACT_SHEET)

    print(f"\n=== v6.4 Final {n}-Asset Balanced 3D Atlas ({len(personal_core)} Personal + {len(interleaved_ext)} Extensions) ===")
    ext_by_dom = Counter(a["archetype_label"] for a in interleaved_ext)
    all_by_dom = Counter(a["archetype_label"] for a in all_assets)
    for dom in ARCHETYPE_ORDER:
        lbl = ARCHETYPE_META[dom]["zh"]
        print(f"  {lbl}: total={all_by_dom[lbl]} (extensions={ext_by_dom[lbl]})")
    print("First 12 cards of 同频扩展:", [a["archetype_label"] for a in interleaved_ext[:12]])
    print(
        f"Bundle size: {WEB_PERSONAL_JSON.stat().st_size / (1024*1024):.2f} MB | "
        f"Contact Sheet: {R4_CONTACT_SHEET} | Total Elapsed: {time.time()-t0:.1f}s"
    )


if __name__ == "__main__":
    main()
