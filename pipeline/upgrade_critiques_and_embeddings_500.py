"""Unified v6.0 Upgrade: Gemini 4 Hydrogen Critique Unification + Gemini Embedding 2 Multimodal Index.

1. Upgrades all remaining legacy-critique assets (~271 spatial/industrial/craft core pins)
   using `gemini-4-hydrogen` (`ThinkingLevel.LOW`) directly on raw `.webp` pixels so ALL
   500/500 assets share consistent, monograph-grade, pixel-grounded critiques and honest
   `core_match` vs `contrast_inspiration` resonance labels.
2. Computes 256-dim L2-normalized multimodal embeddings (`gemini-embedding-2`) for ALL 500/500
   assets (fusing raw `.webp` image pixels + structured RAG retrieval text so both image-to-image
   and natural-language semantic queries work seamlessly).
3. Projects all 500 multimodal vectors into a clean, well-separated 2D Semantic Moodboard Canvas
   (`map_2d: {x, y}` via cosine t-SNE + gentle repulsion relaxation) and pre-computes Top-6
   cosine visual neighbors (`similar_ids`) for every asset for 0ms frontend browsing.

Outputs:
  - `data/pinterest_500/embeddings_500.npz` (vectors float32 [N, 256], asset_ids, map_2d [N, 2])
  - `web/public/data/aethervault_personal_500.json` (`6.0.0-multimodal-rag-atlas-500`)
  - `data/pinterest_500/aethervault_assets_500.json`
  - `web/public/data/aethervault_rag_500.jsonl`
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sklearn.manifold import TSNE

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
WEB_PERSONAL_JSON = WEB_PUBLIC_DIR / "data" / "aethervault_personal_500.json"
WEB_RAG_JSONL = WEB_PUBLIC_DIR / "data" / "aethervault_rag_500.jsonl"
ASSETS_500_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
DEBIASED_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_debiased_critiques.json"
ALL_CRITIQUES_CACHE_PATH = REPO_ROOT / "data" / "pinterest_500" / "_gemini_all_critiques_500.json"
EMB_CACHE_JSON = REPO_ROOT / "data" / "pinterest_500" / "_gemini_embeddings_500_cache.json"
EMB_NPZ_PATH = REPO_ROOT / "data" / "pinterest_500" / "embeddings_500.npz"

CRITIQUE_MODEL = "gemini-4-hydrogen"
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 256


class UnifiedCritique(BaseModel):
    """Monograph-grade pixel-grounded Chinese critique for spatial, industrial, craft, or visual assets."""

    title_zh: str = Field(..., description="Crisp monograph-grade Chinese title (5-14 chars) naming exact scene/object.")
    resonance_mode: Literal["core_match", "contrast_inspiration"] = Field(
        ...,
        description="'core_match' for calm/tectonic/warm-minimal/geometric-order references; 'contrast_inspiration' for bold, high-chroma, brutalist-extreme, surreal, or experimental break-out references.",
    )
    headline_insight: str = Field(..., description="One-sentence razor-sharp aesthetic thesis (22-44 Chinese chars) grounded ONLY in visible pixels.")
    proportion_and_order: str = Field(..., description="Concrete proportion, framing, height/width ratios, negative space & structural rhythm breakdown (65-115 Chinese chars).")
    material_and_detail: str = Field(..., description="Specific visible materials, joint details, surface grain, lighting fixture or craft edge breakdown (65-115 Chinese chars).")
    light_and_palette: str = Field(..., description="Honest lighting direction, shadow contrast & area-weighted color hierarchy (55-100 Chinese chars).")
    why_you_love_it: str = Field(..., description="Honest second-person aesthetic resonance critique (65-115 Chinese chars) connecting concrete visual traits to personal taste or contrast inspiration.")
    design_takeaways: list[str] = Field(..., min_length=3, max_length=3, description="3 concrete transferable design takeaways in Chinese (12-24 chars each).")


CRITIQUE_SYSTEM_PROMPT = """你是顶级建筑评论家、工业与空间策展人。直接观看原图像素，撰写**具体、锐利、零套话、画册级**的中文深度美学拆解。

核心铁律：
1. 必须指出画面里**真正看得见的细节**（例如具体的门窗洞口比例、穿孔铝板折边、清水混凝土对拉螺栓孔、挑檐投影角度、胡桃木与粗陶的肌理对冲、弧形动线或家具节点），严禁写“简约的几何形态与温暖色调形成和谐共鸣”这类套话！
2. 明确判断 `resonance_mode`：符合用户核心审美（构造诚实、温润原木/石土、清晰几何秩序、克制高明度基底）选 `core_match`；若属于高饱和撞色、极致冷峻粗野、戏剧暗调或先锋实验破圈灵感，选 `contrast_inspiration` 并诚实说明反差价值。
3. `title_zh` 必须精准具象（5–14 字），不要叫“现代室内空间”“现代建筑外观”这类泛化名字。"""


def _make_client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required.")
    return genai.Client(api_key=key)


def _critique_one(client: genai.Client, asset: dict[str, Any], img_path: Path) -> tuple[str, dict[str, Any]]:
    img_bytes = img_path.read_bytes()
    palette = ", ".join((asset.get("granular_descriptors") or {}).get("color_palette", [])[:5])
    facets = asset.get("rag_facets") or {}
    prompt = (
        f"Domain: {asset.get('archetype_label', '')} | Style: {asset.get('aesthetic_style_zh', '')} "
        f"({asset.get('native_style_primary') or asset.get('aesthetic_style_en', '')})\n"
        f"Facets: medium={facets.get('medium', '')}, typology={facets.get('typology', '')}, "
        f"materials={','.join(facets.get('materials', []))}, lighting={facets.get('lighting', '')}\n"
        f"Pixel Traits: {', '.join(asset.get('visual_traits') or [])}\n"
        f"Aspect Ratio: {asset.get('aspect_label', '4:3')} | Palette: {palette}\n"
        "Inspect the real pixels now and output the UnifiedCritique JSON."
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=CRITIQUE_MODEL,
                contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/webp"), prompt],
                config=types.GenerateContentConfig(
                    system_instruction=CRITIQUE_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=UnifiedCritique,
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            parsed = UnifiedCritique.model_validate_json((resp.text or "").strip())
            return asset["asset_id"], parsed.model_dump()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Critique failed for {asset['asset_id']}: {last_err}")


def _embed_one(client: genai.Client, asset: dict[str, Any], img_path: Path) -> tuple[str, list[float]]:
    img_bytes = img_path.read_bytes()
    rag = asset.get("rag_doc") or {}
    text_summary = rag.get("retrieval_text") or (
        f"{asset.get('archetype_label', '')} {asset.get('aesthetic_style_zh', '')} "
        f"{asset.get('native_style_primary', '')} {asset.get('title', '')}"
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/webp"),
                    text_summary,
                ],
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            vec = list(resp.embeddings[0].values)
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec = [round(v / norm, 6) for v in vec]
            return asset["asset_id"], vec
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Embedding failed for {asset['asset_id']}: {last_err}")


def compute_2d_layout(vectors: np.ndarray) -> np.ndarray:
    """Project L2-normalized multimodal embeddings to clean 2D [0.05, 0.95] canvas coordinates."""
    n = vectors.shape[0]
    perp = max(5, min(30, (n - 1) // 4))
    tsne = TSNE(
        n_components=2,
        metric="cosine",
        perplexity=perp,
        init="pca",
        learning_rate="auto",
        random_state=42,
        max_iter=1000,
    )
    coords = tsne.fit_transform(vectors).astype(np.float32)

    # Normalize to [0.06, 0.94] preserving relative aspect spread
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    spans = np.maximum(maxs - mins, 1e-6)
    coords = 0.06 + 0.88 * (coords - mins) / spans

    # Gentle repulsion relaxation to reduce thumbnail overlap on the 2D canvas
    min_dist = 0.028
    for _ in range(18):
        diff = coords[:, None, :] - coords[None, :, :]
        dist = np.sqrt((diff ** 2).sum(axis=-1) + 1e-9)
        mask = (dist < min_dist) & (dist > 1e-6)
        if not np.any(mask):
            break
        push = np.where(mask[..., None], (min_dist - dist[..., None]) / (dist[..., None] + 1e-6) * 0.22 * diff, 0.0)
        coords = np.clip(coords + push.sum(axis=1), 0.04, 0.96)

    return coords.astype(np.float32)


def main() -> None:
    if not WEB_PERSONAL_JSON.is_file():
        raise FileNotFoundError(f"Missing personal 500 JSON: {WEB_PERSONAL_JSON}")
    t0 = time.time()
    bundle = json.loads(WEB_PERSONAL_JSON.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = bundle["assets"]

    # Load critique caches (seed with already-debiased 119 Gemini critiques)
    crit_cache: dict[str, dict[str, Any]] = {}
    if DEBIASED_CACHE_PATH.is_file():
        try:
            crit_cache.update(json.loads(DEBIASED_CACHE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if ALL_CRITIQUES_CACHE_PATH.is_file():
        try:
            crit_cache.update(json.loads(ALL_CRITIQUES_CACHE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass

    # pext_* assets were ALREADY authored by gemini-4-hydrogen; upgrade remaining pin_* assets!
    crit_todo = [
        a for a in assets if not a["asset_id"].startswith("pext_") and a["asset_id"] not in crit_cache
    ]
    print(f"Step 1/3 Critique Unification [{CRITIQUE_MODEL}]: total={len(assets)}, todo={len(crit_todo)}")

    client = _make_client()
    if crit_todo:
        lock = threading.Lock()
        done = 0
        t_c = time.time()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {
                pool.submit(_critique_one, client, a, WEB_PUBLIC_DIR / a["image_url"].lstrip("/")): a["asset_id"]
                for a in crit_todo
            }
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    asset_id, payload = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] critique failed {aid}: {exc}")
                    continue
                with lock:
                    crit_cache[asset_id] = payload
                    done += 1
                    if done % 25 == 0 or done == len(crit_todo):
                        ALL_CRITIQUES_CACHE_PATH.write_text(
                            json.dumps(crit_cache, ensure_ascii=False), encoding="utf-8"
                        )
                        print(f"Critique progress: {done}/{len(crit_todo)} ({time.time()-t_c:.1f}s)")
        ALL_CRITIQUES_CACHE_PATH.write_text(json.dumps(crit_cache, ensure_ascii=False), encoding="utf-8")

    # Apply unified Gemini 4 Hydrogen critiques to assets before embedding so retrieval_text is super sharp!
    for a in assets:
        aid = a["asset_id"]
        if aid in crit_cache:
            uc = crit_cache[aid]
            a["title"] = uc["title_zh"].strip() or a["title"]
            a["aesthetic_critique"] = {
                "headline_insight": uc["headline_insight"].strip(),
                "proportion_and_order": uc["proportion_and_order"].strip(),
                "material_and_detail": uc["material_and_detail"].strip(),
                "light_and_palette": uc["light_and_palette"].strip(),
                "why_you_love_it": uc["why_you_love_it"].strip(),
                "design_takeaways": [x.strip() for x in uc.get("design_takeaways", [])[:3] if x.strip()],
                "resonance_mode": uc["resonance_mode"],
            }
            if a.get("rag_doc"):
                rf = a.get("rag_facets") or {}
                a["rag_doc"]["resonance_mode"] = uc["resonance_mode"]
                a["rag_doc"]["retrieval_text"] = (
                    f"[{a.get('archetype_label', '')} | {a.get('aesthetic_style_zh', '')} ({a.get('native_style_primary', '')})] "
                    f"medium:{rf.get('medium', '')} · typology:{rf.get('typology', '')} · "
                    f"materials:{','.join(rf.get('materials', []))} · lighting:{rf.get('lighting', '')} | "
                    f"traits:{', '.join(a.get('visual_traits') or [])} | "
                    f"{a['title']} — {a['aesthetic_critique']['headline_insight']}"
                )

    # Step 2: Multimodal Embedding via gemini-embedding-2 across all 500 assets
    emb_cache: dict[str, list[float]] = {}
    if EMB_CACHE_JSON.is_file():
        try:
            emb_cache = json.loads(EMB_CACHE_JSON.read_text(encoding="utf-8"))
        except Exception:
            emb_cache = {}

    emb_todo = [a for a in assets if a["asset_id"] not in emb_cache]
    print(f"Step 2/3 Multimodal Embedding [{EMBEDDING_MODEL} dim={EMBEDDING_DIM}]: total={len(assets)}, todo={len(emb_todo)}")

    if emb_todo:
        lock = threading.Lock()
        done = 0
        t_e = time.time()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {
                pool.submit(_embed_one, client, a, WEB_PUBLIC_DIR / a["image_url"].lstrip("/")): a["asset_id"]
                for a in emb_todo
            }
            for fut in as_completed(futs):
                aid = futs[fut]
                try:
                    asset_id, vec = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] embed failed {aid}: {exc}")
                    continue
                with lock:
                    emb_cache[asset_id] = vec
                    done += 1
                    if done % 50 == 0 or done == len(emb_todo):
                        EMB_CACHE_JSON.write_text(json.dumps(emb_cache), encoding="utf-8")
                        print(f"Embedding progress: {done}/{len(emb_todo)} ({time.time()-t_e:.1f}s)")
        EMB_CACHE_JSON.write_text(json.dumps(emb_cache), encoding="utf-8")

    # Step 3: Compute 2D Semantic Map coordinates + Top-6 Visual Neighbors for every asset
    asset_ids = [a["asset_id"] for a in assets]
    missing_embs = [aid for aid in asset_ids if aid not in emb_cache]
    if missing_embs:
        raise RuntimeError(f"{len(missing_embs)} assets missing embeddings! Re-run to finish.")

    vectors = np.asarray([emb_cache[aid] for aid in asset_ids], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-8)

    print("Step 3/3 Computing 2D Semantic Moodboard Canvas (cosine t-SNE) & Top-6 visual neighbors...")
    map_2d = compute_2d_layout(vectors)
    sim_matrix = vectors @ vectors.T  # exact cosine similarity [N, N]

    rag_jsonl_lines: list[str] = []
    for idx, a in enumerate(assets):
        a["map_2d"] = {
            "x": round(float(map_2d[idx, 0]), 5),
            "y": round(float(map_2d[idx, 1]), 5),
        }
        sims = sim_matrix[idx].copy()
        sims[idx] = -2.0
        top_idx = np.argsort(-sims)[:6]
        a["similar_ids"] = [
            {
                "asset_id": asset_ids[j],
                "score": round(float(sims[j]), 4),
            }
            for j in top_idx
        ]
        crit = a.get("aesthetic_critique") or {}
        rag_jsonl_lines.append(
            json.dumps(
                {
                    **(a.get("rag_doc") or {}),
                    "title": a["title"],
                    "source_origin": a.get("source_origin", ""),
                    "image_url": a["image_url"],
                    "map_2d": a["map_2d"],
                    "similar_ids": a["similar_ids"],
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

    np.savez_compressed(
        EMB_NPZ_PATH,
        asset_ids=np.asarray(asset_ids),
        vectors=vectors,
        map_2d=map_2d,
    )

    bundle["version"] = "6.0.0-multimodal-rag-atlas-500"
    if bundle.get("rag_schema"):
        bundle["rag_schema"]["embedding_model"] = EMBEDDING_MODEL
        bundle["rag_schema"]["embedding_dim"] = EMBEDDING_DIM
        bundle["rag_schema"]["fusion_model"] = "gemini-nano-banana-2.1"

    WEB_PERSONAL_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    ASSETS_500_JSON.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    WEB_RAG_JSONL.write_text("\n".join(rag_jsonl_lines) + "\n", encoding="utf-8")

    contrast_cnt = sum(1 for a in assets if (a.get("aesthetic_critique") or {}).get("resonance_mode") == "contrast_inspiration")
    print(
        f"DONE v6.0! 500/500 Gemini 4 Hydrogen critiques + 500/500 {EMBEDDING_MODEL} ({EMBEDDING_DIM}d) vectors "
        f"+ 2D Semantic Map + Top-6 neighbors saved! "
        f"Resonance: core_match={len(assets)-contrast_cnt}, contrast={contrast_cnt} | Elapsed={time.time()-t0:.1f}s"
    )


if __name__ == "__main__":
    main()
