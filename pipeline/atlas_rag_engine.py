"""Multimodal RAG Engine: Semantic & Image Search, Nano Banana 2.1 Fusion, and Drop-In Ingest.

Shared core logic used by both FastAPI (`server/main.py`) and the CLI (`pipeline/ingest_dropin.py`):
  - `semantic_search`: `gemini-embedding-2` (256-dim) cosine search over text, uploaded image, or both,
    plus kNN-weighted 2D map projection (`query_map_2d`) for live visualization on the 2D Moodboard Canvas.
  - `fuse_with_nano_banana`: `gemini-nano-banana-2.1` multi-reference concept synthesis driven by
    1-3 selected atlas references and their controlled RAG tokens.
  - `ingest_images`: Drop-in incremental ingestion with 64-bit dHash dedup, `gemini-4-hydrogen`
    visual classification & critique, `gemini-embedding-2` vectorization, kNN 2D placement, and
    atomic persistence across personal JSON, RAG JSONL, and `embeddings_500.npz`.
"""

from __future__ import annotations

import base64
import io
import json
import os
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from google import genai
from google.genai import types
from PIL import Image

from .analyze_aesthetic_500 import _compute_aspect_info
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
    SYSTEM_PROMPT as EXT_EVAL_SYSTEM_PROMPT,
    PinterestExtVlmEval,
    _dhash64,
    _extract_palette_hex,
    _hamming,
    _map_style_with_admissions,
)
from .upgrade_critiques_and_embeddings_500 import EMBEDDING_DIM, EMBEDDING_MODEL

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_ASSETS_DIR = WEB_PUBLIC_DIR / "assets" / "pinterest_500"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
EMB_NPZ_PATH = REPO_ROOT / "data" / "pinterest_500" / "embeddings_500.npz"

CRITIQUE_MODEL = "gemini-4-hydrogen"
FUSION_MODEL = "gemini-nano-banana-2.1"

_LOCK = threading.Lock()


def _make_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required.")
    return genai.Client(api_key=key)


def _load_embeddings() -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
    if not EMB_NPZ_PATH.is_file():
        raise FileNotFoundError(
            f"Multimodal embeddings not ready yet ({EMB_NPZ_PATH}). "
            "Run `python -m pipeline.upgrade_critiques_and_embeddings_500` first."
        )
    data = np.load(EMB_NPZ_PATH, allow_pickle=False)
    asset_ids = [str(x) for x in data["asset_ids"].tolist()]
    vectors = data["vectors"].astype(np.float32)
    map_2d = data["map_2d"].astype(np.float32)
    if "map_3d" in data:
        map_3d = data["map_3d"].astype(np.float32)
    else:
        map_3d = np.column_stack([(map_2d[:, 0] - 0.5) * 2.0, np.zeros(len(asset_ids), dtype=np.float32), (map_2d[:, 1] - 0.5) * 2.0])
    core_centroid = data["core_centroid"].astype(np.float32) if "core_centroid" in data else None
    core_distances = data["core_distances"].astype(np.float32) if "core_distances" in data else None
    return asset_ids, vectors, map_2d, map_3d, core_centroid, core_distances


def _load_bundle() -> dict[str, Any]:
    src = WEB_PERSONAL_JSON if WEB_PERSONAL_JSON.is_file() else ASSETS_500_JSON
    if not src.is_file():
        raise FileNotFoundError(f"Personal atlas JSON missing: {src}")
    return json.loads(src.read_text(encoding="utf-8"))


def _project_knn_2d(query_vec: np.ndarray, vectors: np.ndarray, map_2d: np.ndarray, k: int = 8) -> tuple[float, float]:
    sims = vectors @ query_vec
    top_idx = np.argsort(-sims)[: min(k, len(sims))]
    top_sims = sims[top_idx]
    weights = np.exp((top_sims - top_sims.max()) * 14.0)
    weights = weights / np.maximum(weights.sum(), 1e-8)
    xy = (weights[:, None] * map_2d[top_idx]).sum(axis=0)
    return (round(float(np.clip(xy[0], 0.04, 0.96)), 5), round(float(np.clip(xy[1], 0.04, 0.96)), 5))


def _project_knn_3d(
    query_vec: np.ndarray, vectors: np.ndarray, map_3d: np.ndarray, k: int = 8
) -> tuple[float, float, float]:
    sims = vectors @ query_vec
    top_idx = np.argsort(-sims)[: min(k, len(sims))]
    top_sims = sims[top_idx]
    weights = np.exp((top_sims - top_sims.max()) * 14.0)
    weights = weights / np.maximum(weights.sum(), 1e-8)
    xyz = (weights[:, None] * map_3d[top_idx]).sum(axis=0)
    return (
        round(float(np.clip(xyz[0], -1.0, 1.0)), 5),
        round(float(np.clip(xyz[1], -1.0, 1.0)), 5),
        round(float(np.clip(xyz[2], -1.0, 1.0)), 5),
    )


def _normalize_image_bytes(raw_bytes: bytes, max_side: int = 960, fmt: str = "WEBP") -> tuple[bytes, str]:
    with Image.open(io.BytesIO(raw_bytes)) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if fmt == "JPEG":
            rgb.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue(), "image/jpeg"
        rgb.save(buf, format="WEBP", quality=85, method=4)
        return buf.getvalue(), "image/webp"


def get_atlas_rag_status() -> dict[str, Any]:
    has_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    emb_ready = EMB_NPZ_PATH.is_file()
    emb_count = 0
    if emb_ready:
        try:
            d = np.load(EMB_NPZ_PATH, allow_pickle=False)
            emb_count = int(len(d["asset_ids"]))
        except Exception:
            emb_ready = False
    return {
        "ready": has_key and emb_ready,
        "has_gemini_key": has_key,
        "embeddings_ready": emb_ready,
        "indexed_count": emb_count,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
        "critique_model": CRITIQUE_MODEL,
        "fusion_model": FUSION_MODEL,
    }


def semantic_search(
    query: str | None = None,
    image_bytes: bytes | None = None,
    top_k: int = 16,
) -> dict[str, Any]:
    """Multimodal semantic search over text, uploaded reference image, or both."""
    t0 = time.perf_counter()
    clean_q = (query or "").strip()
    if not clean_q and not image_bytes:
        raise ValueError("Provide either a text query or an uploaded reference image.")

    asset_ids, vectors, map_2d, map_3d, _core_centroid, _core_distances = _load_embeddings()
    bundle = _load_bundle()
    by_id = {a["asset_id"]: a for a in bundle["assets"]}

    contents: list[Any] = []
    mode = "text"
    if image_bytes:
        norm_bytes, mime = _normalize_image_bytes(image_bytes, max_side=768, fmt="WEBP")
        contents.append(types.Part.from_bytes(data=norm_bytes, mime_type=mime))
        mode = "multimodal" if clean_q else "image"
    if clean_q:
        contents.append(clean_q)

    client = _make_client()
    resp = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=contents if len(contents) > 1 else contents[0],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    q_vec = np.asarray(resp.embeddings[0].values, dtype=np.float32)
    q_norm = float(np.linalg.norm(q_vec))
    if q_norm > 0:
        q_vec = q_vec / q_norm

    sims = vectors @ q_vec
    k = max(1, min(int(top_k), len(asset_ids)))
    top_idx = np.argsort(-sims)[:k]
    qx, qy = _project_knn_2d(q_vec, vectors, map_2d, k=8)
    qx3, qy3, qz3 = _project_knn_3d(q_vec, vectors, map_3d, k=8)

    results = []
    for idx in top_idx:
        aid = asset_ids[idx]
        a = by_id.get(aid)
        if not a:
            continue
        results.append(
            {
                "asset_id": aid,
                "score": round(float(sims[idx]), 4),
                "title": a.get("title", ""),
                "archetype": a.get("archetype", ""),
                "archetype_label": a.get("archetype_label", ""),
                "aesthetic_style_zh": a.get("aesthetic_style_zh", ""),
                "native_style_primary": a.get("native_style_primary", ""),
                "image_url": a.get("image_url", ""),
                "map_2d": a.get("map_2d", {"x": float(map_2d[idx, 0]), "y": float(map_2d[idx, 1])}),
                "map_3d": a.get(
                    "map_3d",
                    {"x": float(map_3d[idx, 0]), "y": float(map_3d[idx, 1]), "z": float(map_3d[idx, 2])},
                ),
            }
        )

    return {
        "mode": mode,
        "query": clean_q,
        "embedding_model": EMBEDDING_MODEL,
        "query_map_2d": {"x": qx, "y": qy},
        "query_map_3d": {"x": qx3, "y": qy3, "z": qz3},
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
        "total_indexed": len(asset_ids),
        "results": results,
    }


def fuse_with_nano_banana(
    asset_ids: list[str],
    prompt: str,
    aspect_ratio: str = "4:3",
) -> dict[str, Any]:
    """Cross-domain aesthetic fusion using Gemini Nano Banana 2.1 + controlled RAG tokens."""
    t0 = time.perf_counter()
    clean_ids = [aid.strip() for aid in asset_ids if aid.strip()][:3]
    clean_prompt = (prompt or "").strip()
    if not clean_ids and not clean_prompt:
        raise ValueError("Select at least 1 reference asset or enter a concept prompt.")
    if aspect_ratio not in ("1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"):
        aspect_ratio = "4:3"

    bundle = _load_bundle()
    by_id = {a["asset_id"]: a for a in bundle["assets"]}

    ref_assets = [by_id[aid] for aid in clean_ids if aid in by_id]
    if clean_ids and not ref_assets:
        raise ValueError("None of the requested asset_ids exist in the personal atlas.")

    # Compile controlled RAG token brief from selected references
    ref_lines: list[str] = []
    merged_tokens: list[str] = []
    merged_palette: list[str] = []
    input_parts: list[dict[str, Any]] = []

    for i, a in enumerate(ref_assets, start=1):
        rag = a.get("rag_doc") or {}
        toks = rag.get("model_prompt_tokens") or []
        merged_tokens.extend(toks[:5])
        merged_palette.extend((a.get("granular_descriptors") or {}).get("color_palette", [])[:2])
        ref_lines.append(
            f"- Reference {i} ({a.get('archetype_label', '')} · {a.get('native_style_primary') or a.get('aesthetic_style_en', '')}): "
            f"{', '.join(toks[:5])}"
        )

    merged_tokens = list(dict.fromkeys(merged_tokens))[:12]
    merged_palette = list(dict.fromkeys(merged_palette))[:6]

    compiled_prompt = (
        f"Create a cohesive, publication-grade design concept image.\n"
        f"User creative direction: {clean_prompt or 'Synthesize the spatial proportions, material craft, and visual mood of the attached references into a unified original design.'}\n"
    )
    if ref_lines:
        compiled_prompt += (
            "Synthesize orthogonally from these attached reference plates (preserve material honesty, lighting discipline, and proportion without copying collages or watermarks):\n"
            + "\n".join(ref_lines)
            + f"\nControlled Aesthetic Tokens: {', '.join(merged_tokens)}"
            + (f"\nColor Restraint Anchor: {', '.join(merged_palette)}" if merged_palette else "")
        )

    input_parts.append({"type": "text", "text": compiled_prompt})
    for a in ref_assets:
        img_path = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
        if img_path.is_file():
            jpeg_bytes, mime = _normalize_image_bytes(img_path.read_bytes(), max_side=768, fmt="JPEG")
            input_parts.append(
                {
                    "type": "image",
                    "data": base64.b64encode(jpeg_bytes).decode("ascii"),
                    "mime_type": mime,
                }
            )

    client = _make_client()
    interaction = client.interactions.create(
        model=FUSION_MODEL,
        input=input_parts,
        response_format={
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": aspect_ratio,
        },
    )
    out_img = getattr(interaction, "output_image", None)
    if not out_img or not getattr(out_img, "data", None):
        raise RuntimeError("Nano Banana 2.1 did not return an output image.")

    img_bytes = base64.b64decode(out_img.data)
    WEB_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"fused_{int(time.time() * 1000)}.jpg"
    out_path = WEB_ASSETS_DIR / fname
    out_path.write_bytes(img_bytes)

    return {
        "model": FUSION_MODEL,
        "image_url": f"/assets/pinterest_500/{fname}",
        "aspect_ratio": aspect_ratio,
        "reference_ids": [a["asset_id"] for a in ref_assets],
        "reference_titles": [a["title"] for a in ref_assets],
        "compiled_tokens": merged_tokens,
        "compiled_prompt": compiled_prompt,
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }


def _rebuild_bundle_aggregates(bundle: dict[str, Any]) -> list[str]:
    assets = bundle["assets"]
    arch_counts: Counter[str] = Counter()
    domain_counts_5: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    arch_style_counts: dict[str, Counter[str]] = defaultdict(Counter)
    origin_counts: Counter[str] = Counter()
    facet_counts: dict[str, Counter[str]] = {
        "medium": Counter(),
        "typology": Counter(),
        "materials": Counter(),
        "lighting": Counter(),
    }
    rag_jsonl_lines: list[str] = []

    for a in assets:
        dom = a["archetype"]
        sid = a["aesthetic_style"]
        arch_counts[dom] += 1
        domain_counts_5[a["subject_isolation"]["domain"]] += 1
        origin_counts[a.get("source_origin", "pinterest_personal")] += 1
        style_counts[sid] += 1
        arch_style_counts[dom][sid] += 1
        rf = a["rag_facets"]
        facet_counts["medium"][rf["medium"]] += 1
        facet_counts["typology"][rf["typology"]] += 1
        for m in rf["materials"]:
            facet_counts["materials"][m] += 1
        facet_counts["lighting"][rf["lighting"]] += 1

        crit = a.get("aesthetic_critique") or {}
        rag_jsonl_lines.append(
            json.dumps(
                {
                    **(a.get("rag_doc") or {}),
                    "title": a["title"],
                    "source_origin": a.get("source_origin", ""),
                    "image_url": a["image_url"],
                    "map_2d": a.get("map_2d"),
                    "similar_ids": a.get("similar_ids"),
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

    bundle["total_assets"] = len(assets)
    bundle["domain_counts"] = dict(domain_counts_5)
    bundle["origin_counts"] = dict(origin_counts)
    bundle["archetype_taxonomy"] = archetype_taxonomy
    bundle["archetype_counts"] = dict(arch_counts)
    if bundle.get("rag_schema"):
        bundle["rag_schema"]["max_styles"] = len(style_counts)
        bundle["rag_schema"]["styles"] = [
            {
                "style_id": sid,
                "zh": EXTENDED_STYLE_CATALOG[sid]["zh"],
                "en": EXTENDED_STYLE_CATALOG[sid]["en"],
                "is_movement": EXTENDED_STYLE_CATALOG[sid]["is_movement"],
                "count": c,
            }
            for sid, c in style_counts.most_common()
        ]
        bundle["rag_schema"]["facet_counts"] = {
            k: [{"value": val, "count": cnt} for val, cnt in counter.most_common()]
            for k, counter in facet_counts.items()
        }
    return rag_jsonl_lines


def ingest_images(
    items: list[tuple[str, bytes]],
    source_label: str = "Drop-In 本地导入",
) -> dict[str, Any]:
    """Drop-in incremental ingestion: dHash dedup -> Gemini 4 Hydrogen -> Gemini Embedding 2 -> persist."""
    if not items:
        raise ValueError("No images provided for ingestion.")

    with _LOCK:
        t0 = time.perf_counter()
        bundle = _load_bundle()
        assets: list[dict[str, Any]] = bundle["assets"]
        asset_ids, vectors, map_2d, map_3d, core_centroid, core_distances = _load_embeddings()
        client = _make_client()

        # Build existing perceptual hashes
        existing_hashes: list[tuple[str, int]] = []
        for a in assets:
            p = WEB_PUBLIC_DIR / a["image_url"].lstrip("/")
            if p.is_file():
                try:
                    existing_hashes.append((a["asset_id"], _dhash64(p)))
                except Exception:
                    continue

        existing_drop_nums = [
            int(a["asset_id"].rsplit("_", 1)[-1])
            for a in assets
            if a["asset_id"].startswith("drop_") and a["asset_id"].rsplit("_", 1)[-1].isdigit()
        ]
        next_seq = (max(existing_drop_nums) + 1) if existing_drop_nums else 1

        report: list[dict[str, Any]] = []
        added_assets: list[dict[str, Any]] = []
        new_ids: list[str] = []
        new_vecs: list[np.ndarray] = []
        new_coords: list[np.ndarray] = []
        new_coords_3d: list[np.ndarray] = []
        new_core_dists: list[float] = []

        WEB_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        for fname, raw_bytes in items:
            try:
                with Image.open(io.BytesIO(raw_bytes)) as im:
                    rgb = im.convert("RGB")
                    if min(rgb.size) < 160:
                        report.append({"filename": fname, "status": "rejected", "reason": "分辨率过低 (<160px)"})
                        continue
                    rgb.thumbnail((960, 960), Image.Resampling.LANCZOS)
                    tmp_buf = io.BytesIO()
                    rgb.save(tmp_buf, format="WEBP", quality=85, method=4)
                    webp_bytes = tmp_buf.getvalue()
            except Exception as exc:
                report.append({"filename": fname, "status": "error", "reason": f"无法解码图片: {exc}"})
                continue

            # Temporary write to compute dHash cleanly
            tmp_path = WEB_ASSETS_DIR / f"_tmp_ingest_{next_seq}.webp"
            tmp_path.write_bytes(webp_bytes)
            h_new = _dhash64(tmp_path)

            dup_match = next((aid for aid, eh in existing_hashes if _hamming(h_new, eh) <= 6), None)
            if dup_match:
                tmp_path.unlink(missing_ok=True)
                report.append(
                    {
                        "filename": fname,
                        "status": "duplicate",
                        "matched_asset_id": dup_match,
                        "reason": f"感知哈希去重命中已有档案 {dup_match}",
                    }
                )
                continue

            # 1) Gemini 4 Hydrogen full visual evaluation
            resp = client.models.generate_content(
                model=CRITIQUE_MODEL,
                contents=[
                    types.Part.from_bytes(data=webp_bytes, mime_type="image/webp"),
                    "Inspect this newly dropped personal reference image strictly from its pixels and return the PinterestExtVlmEval JSON.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=EXT_EVAL_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=PinterestExtVlmEval,
                    temperature=0.15,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            ev = PinterestExtVlmEval.model_validate_json((resp.text or "").strip()).model_dump()

            dom = ev["visual_domain"]
            dmeta = ARCHETYPE_META[dom]
            aid = f"drop_{dom[:4]}_{next_seq:03d}"
            next_seq += 1

            dst_path = WEB_ASSETS_DIR / f"{aid}.webp"
            tmp_path.replace(dst_path)
            existing_hashes.append((aid, h_new))

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

            # 2) Gemini Embedding 2 multimodal vector + kNN 2D placement + Top-6 neighbors
            emb_resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[types.Part.from_bytes(data=webp_bytes, mime_type="image/webp"), retrieval_text],
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            vec = np.asarray(emb_resp.embeddings[0].values, dtype=np.float32)
            v_norm = float(np.linalg.norm(vec))
            if v_norm > 0:
                vec = vec / v_norm

            all_vecs_cur = np.vstack([vectors, *new_vecs]) if new_vecs else vectors
            all_ids_cur = asset_ids + new_ids
            all_map_cur = np.vstack([map_2d, *new_coords]) if new_coords else map_2d
            all_map3d_cur = np.vstack([map_3d, *new_coords_3d]) if new_coords_3d else map_3d

            nx, ny = _project_knn_2d(vec, all_vecs_cur, all_map_cur, k=8)
            nx3, ny3, nz3 = _project_knn_3d(vec, all_vecs_cur, all_map3d_cur, k=8)
            cdist = (
                round(float(np.clip(1.0 - float(vec @ core_centroid), 0.0, 1.0)), 4)
                if core_centroid is not None
                else 0.35
            )
            sims = all_vecs_cur @ vec
            top10_idx = np.argsort(-sims)[:10]
            similar_ids = [
                {"asset_id": all_ids_cur[j], "score": round(float(sims[j]), 4)}
                for j in top10_idx
            ]

            legacy_dom, legacy_dom_zh = DOMAIN_TO_LEGACY_5[dom]
            asset_obj: dict[str, Any] = {
                "asset_id": aid,
                "title": ev["title_zh"].strip(),
                "title_en": ev["primary_subject_en"].strip(),
                "image_url": f"/assets/pinterest_500/{aid}.webp",
                "width": w,
                "height": h,
                "aspect_label": aspect_lbl,
                "license": "Personal Drop-In Reference",
                "source_kind": "personal_dropin",
                "source_origin": "pinterest_personal",
                "board_name": source_label,
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
                "map_2d": {"x": nx, "y": ny},
                "map_3d": {"x": nx3, "y": ny3, "z": nz3},
                "core_distance": cdist,
                "similar_ids": similar_ids,
                "subject_isolation": {
                    "domain": legacy_dom,
                    "domain_label": legacy_dom_zh,
                    "primary_subject": ev["primary_subject_en"].strip(),
                    "is_personal_prior": True,
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
                    "negative_guardrails": ["watermark", "cluttered background"],
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

            added_assets.append(asset_obj)
            new_ids.append(aid)
            new_vecs.append(vec[None, :])
            new_coords.append(np.asarray([[nx, ny]], dtype=np.float32))
            new_coords_3d.append(np.asarray([[nx3, ny3, nz3]], dtype=np.float32))
            new_core_dists.append(cdist)
            report.append(
                {
                    "filename": fname,
                    "status": "added",
                    "asset_id": aid,
                    "title": asset_obj["title"],
                    "archetype_label": dmeta["zh"],
                    "aesthetic_style_zh": smeta["zh"],
                    "native_style_primary": native_primary,
                    "resonance_mode": ev["resonance_mode"],
                    "image_url": asset_obj["image_url"],
                }
            )

        if added_assets:
            # Prepend newly dropped assets so they appear immediately at the top of the gallery!
            bundle["assets"] = added_assets + assets
            rag_jsonl_lines = _rebuild_bundle_aggregates(bundle)

            final_ids = asset_ids + new_ids
            final_vecs = np.vstack([vectors, *new_vecs]).astype(np.float32)
            final_map = np.vstack([map_2d, *new_coords]).astype(np.float32)
            final_map3d = np.vstack([map_3d, *new_coords_3d]).astype(np.float32)
            save_kwargs: dict[str, Any] = {
                "asset_ids": np.asarray(final_ids),
                "vectors": final_vecs,
                "map_2d": final_map,
                "map_3d": final_map3d,
            }
            if core_centroid is not None:
                save_kwargs["core_centroid"] = core_centroid
            if core_distances is not None:
                save_kwargs["core_distances"] = np.concatenate(
                    [core_distances, np.asarray(new_core_dists, dtype=np.float32)]
                )
            np.savez_compressed(EMB_NPZ_PATH, **save_kwargs)

            WEB_PERSONAL_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            ASSETS_500_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")

        return {
            "added_count": len(added_assets),
            "skipped_count": len(items) - len(added_assets),
            "total_assets": len(bundle["assets"]),
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "items": report,
            "added_assets": added_assets,
        }
