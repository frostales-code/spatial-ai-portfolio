"""Compute real 3D semantic constellation coordinates (`map_3d`) and personal-core
gravitational distances (`core_distance`) from the 256-dim Gemini Embedding 2 vectors.

Updates:
- data/pinterest_500/embeddings_500.npz (adds `map_3d`, `core_centroid`, `core_distances`)
- web/public/data/aethervault_personal_500.json
- data/pinterest_500/aethervault_assets_500.json
- web/public/data/aethervault_rag_500.jsonl

Never touches the public 80-asset showcase (`web/public/data/aethervault_showcase_v1.json`).
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.manifold import TSNE

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "pinterest_500"
EMB_NPZ_PATH = DATA_DIR / "embeddings_500.npz"
ASSETS_500_JSON = DATA_DIR / "aethervault_assets_500.json"
WEB_PERSONAL_JSON = ROOT / "web" / "public" / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = ROOT / "web" / "public" / "data" / "aethervault_rag_500.jsonl"


def _normalize_3d(coords: np.ndarray) -> np.ndarray:
    """Center and scale 3D coordinates robustly to [-1, 1] preserving aspect proportions."""
    centered = coords - np.median(coords, axis=0, keepdims=True)
    # Use 98th percentile radius so extreme outliers don't crush the core
    radii = np.linalg.norm(centered, axis=1)
    scale = float(np.percentile(radii, 98))
    if scale < 1e-6:
        scale = 1.0
    normed = np.clip(centered / scale, -1.15, 1.15)
    # Re-normalize max abs to 1.0
    max_abs = float(np.max(np.abs(normed)))
    if max_abs > 1e-6:
        normed = normed / max_abs
    return normed.astype(np.float32)


def _count_connected_components(adj: dict[int, set[int]], n: int) -> tuple[int, int]:
    visited = [False] * n
    comps = 0
    largest = 0
    for i in range(n):
        if visited[i]:
            continue
        comps += 1
        q = deque([i])
        visited[i] = True
        sz = 0
        while q:
            u = q.popleft()
            sz += 1
            for v in adj[u]:
                if not visited[v]:
                    visited[v] = True
                    q.append(v)
        largest = max(largest, sz)
    return comps, largest


def main() -> None:
    if not EMB_NPZ_PATH.is_file():
        raise FileNotFoundError(f"Missing embeddings file: {EMB_NPZ_PATH}")
    if not WEB_PERSONAL_JSON.is_file():
        raise FileNotFoundError(f"Missing personal atlas JSON: {WEB_PERSONAL_JSON}")

    emb_data = np.load(EMB_NPZ_PATH, allow_pickle=False)
    asset_ids = [str(x) for x in emb_data["asset_ids"].tolist()]
    vectors = emb_data["vectors"].astype(np.float32)
    map_2d = emb_data["map_2d"].astype(np.float32)
    n = len(asset_ids)

    bundle: dict[str, Any] = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]
    id_to_idx = {aid: i for i, aid in enumerate(asset_ids)}

    # 1. Compute real 3D Cosine t-SNE on 256-dim Gemini Embedding 2 vectors
    print(f"[1/4] Computing 3D cosine t-SNE for {n} assets (dim={vectors.shape[1]})...")
    tsne = TSNE(
        n_components=3,
        metric="cosine",
        perplexity=min(32, max(10, n // 18)),
        init="pca",
        learning_rate="auto",
        max_iter=1200,
        random_state=42,
    )
    raw_3d = tsne.fit_transform(vectors)
    map_3d = _normalize_3d(raw_3d)

    # 2. Compute Personal Core Centroid (mean of all personal Pinterest origins)
    personal_indices = [
        id_to_idx[a["asset_id"]]
        for a in assets
        if a["asset_id"] in id_to_idx and a.get("source_origin") != "profile_expansion"
    ]
    core_centroid = vectors[personal_indices].mean(axis=0)
    core_norm = float(np.linalg.norm(core_centroid))
    if core_norm > 1e-8:
        core_centroid = (core_centroid / core_norm).astype(np.float32)

    raw_dists = 1.0 - (vectors @ core_centroid)
    # Percentile rank in [0, 1] for crisp radial orbital stratification
    ranks = np.argsort(np.argsort(raw_dists))
    core_distances = (ranks / max(1, n - 1)).astype(np.float32)

    # 3. Compute Top-10 cosine neighbors for rich cross-domain Dijkstra A->B bridges
    print("[2/4] Computing Top-10 semantic neighbors and verifying graph connectivity...")
    sim_matrix = vectors @ vectors.T
    np.fill_diagonal(sim_matrix, -2.0)

    k_neighbors = 10
    top_neighbors: dict[str, list[dict[str, Any]]] = {}
    undirected_adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i, aid in enumerate(asset_ids):
        top_idx = np.argsort(-sim_matrix[i])[:k_neighbors]
        top_neighbors[aid] = [
            {"asset_id": asset_ids[j], "score": round(float(sim_matrix[i, j]), 4)}
            for j in top_idx
        ]
        for j in top_idx:
            undirected_adj[i].add(int(j))
            undirected_adj[int(j)].add(i)

    comps, largest = _count_connected_components(undirected_adj, n)
    print(f"      k={k_neighbors} neighbor graph: {comps} component(s), largest={largest}/{n}")

    # 4. Patch bundle assets + write npz & JSONs
    print("[3/4] Writing map_3d, core_distance, and Top-10 similar_ids to personal atlas...")
    patched = 0
    for a in assets:
        aid = a["asset_id"]
        idx = id_to_idx.get(aid)
        if idx is None:
            continue
        a["map_3d"] = {
            "x": round(float(map_3d[idx, 0]), 5),
            "y": round(float(map_3d[idx, 1]), 5),
            "z": round(float(map_3d[idx, 2]), 5),
        }
        a["core_distance"] = round(float(core_distances[idx]), 4)
        a["similar_ids"] = top_neighbors[aid]
        patched += 1

    bundle["schema_version"] = "6.2.0-constellation-3d-dotmatrix-600"

    np.savez_compressed(
        EMB_NPZ_PATH,
        asset_ids=np.asarray(asset_ids),
        vectors=vectors,
        map_2d=map_2d,
        map_3d=map_3d,
        core_centroid=core_centroid,
        core_distances=core_distances,
    )

    serialized = json.dumps(bundle, ensure_ascii=False, indent=2)
    WEB_PERSONAL_JSON.write_text(serialized, encoding="utf-8")
    ASSETS_500_JSON.write_text(serialized, encoding="utf-8")

    # Sync RAG JSONL
    rag_lines = [
        json.dumps(a["rag_doc"], ensure_ascii=False)
        for a in assets
        if isinstance(a.get("rag_doc"), dict)
    ]
    WEB_RAG_JSONL.write_text("\n".join(rag_lines) + "\n", encoding="utf-8")

    # Quick domain sanity summary
    print(f"[4/4] Done! Patched {patched}/{len(assets)} assets.")
    print(f"      Personal core count: {len(personal_indices)} | Expansion count: {n - len(personal_indices)}")
    print(f"      map_3d range: min={map_3d.min(axis=0).round(3).tolist()} max={map_3d.max(axis=0).round(3).tolist()}")


if __name__ == "__main__":
    main()
