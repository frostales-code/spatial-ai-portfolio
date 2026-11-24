"""Profile-Driven Image Research & Expansion to Exact 500 Assets.

Uses three verified HTTP-200 high-aesthetic open-access APIs:
1. Victoria & Albert Museum (V&A London) API + IIIF (industrial design, Bauhaus/Nordic furniture,
   Swiss/Bauhaus posters, Japanese ceramics, avant-garde fashion & modernist photography)
2. Cleveland Museum of Art Open Access CC0 API (studio-lit ceramics, textiles, modernist photography & craft)
3. Wikimedia Commons MediaWiki API (contemporary tectonic architecture, rammed earth/stone/timber craft,
   architectural daylight/shadow studies, and minimalist wayfinding signage)

Deduplicates via pHash against all 523 personal Pinterest pins, scores every downloaded
candidate with `gpt-4o-mini` Vision + Prompt Caching, and selects the top 110 profile-aligned
images to expand our 390 kept Pinterest core to exactly 500 specimens.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from openai import OpenAI, RateLimitError
from PIL import Image

from .aethervault_schema import AXIS_IDS
from .research_pinterest_523 import (
    DEFAULT_MODEL,
    OUT_DIR,
    PROFILE_JSON_PATH,
    RESEARCH_JSON_PATH,
    PinterestVlmResearchItem,
    _build_research_system_prompt,
    _encode_image_b64,
)

EXPANSION_IMG_DIR = OUT_DIR / "expansion_candidates"
EXPANSION_META_PATH = OUT_DIR / "_expansion_candidates_meta.json"
EXPANSION_VLM_CACHE_PATH = OUT_DIR / "_expansion_vlm_cache.json"
EXPANSION_SELECTED_PATH = OUT_DIR / "expansion_selected.json"

USER_AGENT = "SpatialAIPortfolio/2.0 (https://github.com/frostales-code/spatial-ai-portfolio; research@spatial-ai.local)"

# Profile-tailored queries derived directly from user's 523-pin Pinterest signature:
# (+0.401 tectonic honesty, +0.299 warm materiality, +0.263 geometric order, +0.206 light drama)
WIKIMEDIA_QUERIES: dict[str, list[str]] = {
    "industrial": [
        "Braun Dieter Rams industrial design",
        "Bauhaus tubular steel chair furniture",
        "minimalist pendant lamp architectural lighting",
        "Leica rangefinder camera minimalist",
        "modular analog synthesizer aluminum knobs",
        "modernist architectural wayfinding signage",
        "Japanese wooden stool minimalist furniture",
        "Nordic minimalist lounge chair wood",
    ],
    "craft": [
        "Japanese stoneware ceramic bowl pottery",
        "Japanese wood joinery carpentry",
        "travertine limestone stone wall texture",
        "rammed earth architecture wall",
        "Shou Sugi Ban charred cedar wood",
        "minimalist ceramic vessel glaze",
        "bronze patina sculpture minimal",
    ],
    "editorial": [
        "concrete architecture sunlight shadow minimalist",
        "minimalist museum interior daylight concrete",
        "Japanese zen courtyard architecture light",
        "brutalist concrete geometry shadow photography",
        "Scandinavian minimalist cafe interior wood",
        "contemporary art gallery skylight concrete",
        "minimalist architectural staircase shadow",
    ],
    "graphic": [
        "Swiss style typography poster",
        "Bauhaus poster geometric design",
        "modernist museum exhibition poster",
        "minimalist wayfinding signage typography",
    ],
    "architecture": [
        "Tadao Ando concrete architecture",
        "Kengo Kuma wood pavilion architecture",
        "Peter Zumthor architecture concrete stone",
    ],
}

VAM_QUERIES: dict[str, list[str]] = {
    "industrial": [
        "Braun Dieter Rams",
        "Bauhaus chair tubular steel",
        "modernist chair wood",
        "minimalist lamp metal",
        "Scandinavian furniture chair",
        "industrial design radio camera",
        "Alvar Aalto stool chair",
        "modernist teapot metal vessel",
    ],
    "craft": [
        "Japanese stoneware tea bowl",
        "minimalist stoneware vase ceramic",
        "studio pottery stoneware glaze",
        "Japanese wood vessel craft",
        "woven linen textile minimalist",
        "celadon ceramic bowl",
        "bronze vessel sculpture",
    ],
    "editorial": [
        "architectural photography concrete shadow",
        "modernist architecture photograph",
        "Issey Miyake dress fashion",
        "Yohji Yamamoto fashion coat",
        "minimalist interior photograph",
        "black and white architecture light",
        "contemporary sculpture gallery light",
    ],
    "graphic": [
        "Swiss typography poster",
        "Bauhaus exhibition poster",
        "modernist geometric poster",
        "minimalist graphic design poster",
    ],
    "architecture": [
        "modernist pavilion architecture",
    ],
}

CMA_QUERIES: dict[str, list[str]] = {
    "industrial": [
        "modernist chair furniture",
        "metal lamp vessel",
    ],
    "craft": [
        "Japanese stoneware ceramic",
        "stoneware jar glaze",
        "minimalist wood bowl",
        "woven textile linen",
    ],
    "editorial": [
        "architectural photograph shadow",
        "modernist building photograph",
        "minimalist still life photograph",
        "geometric staircase photograph",
    ],
    "graphic": [
        "Bauhaus geometric print",
        "modernist typography poster",
    ],
    "architecture": [
        "modernist architecture",
    ],
}


def _compute_phash(img: Image.Image) -> str:
    gray = img.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    dct_rows = np.fft.rfft(arr, axis=1).real[:, :8]
    dct_block = np.fft.rfft(dct_rows, axis=0).real[:8, :8]
    med = float(np.median(dct_block[1:, 1:]))
    bits = "".join("1" if v > med else "0" for v in dct_block.flatten())
    return f"{int(bits, 2):016x}"


def _hamming(h1: str, h2: str) -> int:
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except Exception:
        return 64


def _search_wikimedia(client: httpx.Client, query: str, limit: int = 16) -> list[dict[str, Any]]:
    try:
        r1 = client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srnamespace": "6",
                "srsearch": query,
                "srlimit": str(limit),
            },
            timeout=15.0,
        )
        r1.raise_for_status()
        hits = r1.json().get("query", {}).get("search", [])
        titles = [h["title"] for h in hits if h.get("title")]
        if not titles:
            return []

        r2 = client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "titles": "|".join(titles[:20]),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "800",
            },
            timeout=15.0,
        )
        r2.raise_for_status()
        pages = r2.json().get("query", {}).get("pages", {})
    except Exception as exc:  # noqa: BLE001
        print(f"  [wikimedia warn] '{query}': {exc}")
        return []

    results: list[dict[str, Any]] = []
    for p in pages.values():
        infos = p.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = str(info.get("mime", "")).lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        w = int(info.get("width") or 0)
        h = int(info.get("height") or 0)
        if min(w, h) < 420:
            continue
        ratio = w / max(1, h)
        if ratio < 0.48 or ratio > 2.25:
            continue
        thumb_url = info.get("thumburl") or info.get("url")
        if not thumb_url:
            continue
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value") or "Wikimedia Commons"
        title = str(p.get("title", "")).replace("File:", "").rsplit(".", 1)[0]
        results.append(
            {
                "source": "wikimedia_commons",
                "url": thumb_url,
                "source_page": info.get("descriptionurl") or "",
                "title": title[:140],
                "license": str(lic)[:60],
                "orig_w": w,
                "orig_h": h,
                "query": query,
            }
        )
    return results


def _search_vam(client: httpx.Client, query: str, limit: int = 16) -> list[dict[str, Any]]:
    try:
        resp = client.get(
            "https://api.vam.ac.uk/v2/objects/search",
            params={
                "q": query,
                "images_exist": "1",
                "page_size": str(limit),
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
    except Exception as exc:  # noqa: BLE001
        print(f"  [vam warn] '{query}': {exc}")
        return []

    results: list[dict[str, Any]] = []
    for rec in records:
        img_id = rec.get("_primaryImageId")
        if not img_id:
            continue
        url = f"https://framemark.vam.ac.uk/collections/{img_id}/full/!960,960/0/default.jpg"
        title = str(rec.get("_primaryTitle") or rec.get("objectType") or query)[:140]
        sys_num = rec.get("systemNumber", "")
        results.append(
            {
                "source": "vam_museum_iiif",
                "url": url,
                "source_page": f"https://collections.vam.ac.uk/item/{sys_num}",
                "title": title,
                "license": "Victoria and Albert Museum Open Collection",
                "orig_w": 960,
                "orig_h": 960,
                "query": query,
            }
        )
    return results


def _search_cma(client: httpx.Client, query: str, limit: int = 14) -> list[dict[str, Any]]:
    try:
        resp = client.get(
            "https://openaccess-api.clevelandart.org/api/artworks/",
            params={
                "q": query,
                "has_image": "1",
                "cc0": "1",
                "limit": str(limit),
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as exc:  # noqa: BLE001
        print(f"  [cma warn] '{query}': {exc}")
        return []

    results: list[dict[str, Any]] = []
    for it in data:
        web_img = (it.get("images") or {}).get("web") or {}
        url = web_img.get("url")
        if not url:
            continue
        title = str(it.get("title") or query)[:140]
        results.append(
            {
                "source": "cleveland_museum_cc0",
                "url": url,
                "source_page": str(it.get("url") or ""),
                "title": title,
                "license": "Cleveland Museum of Art Open Access (CC0)",
                "orig_w": int(web_img.get("width") or 900),
                "orig_h": int(web_img.get("height") or 900),
                "query": query,
            }
        )
    return results


def _download_candidate(
    client: httpx.Client,
    cand: dict[str, Any],
    domain: str,
    existing_phashes: list[str],
    phash_lock: threading.Lock,
) -> dict[str, Any] | None:
    url = cand["url"]
    uid = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    out_path = EXPANSION_IMG_DIR / f"exp_{domain}_{uid}.webp"
    if out_path.is_file():
        try:
            with Image.open(out_path) as im:
                w, h = im.size
                ph = _compute_phash(im)
            return {
                **cand,
                "cand_id": f"exp_{domain}_{uid}",
                "target_domain": domain,
                "local_path": str(out_path),
                "width": w,
                "height": h,
                "phash": ph,
            }
        except Exception:
            out_path.unlink(missing_ok=True)

    try:
        resp = client.get(url, timeout=16.0, follow_redirects=True)
        if resp.status_code != 200 or len(resp.content) < 8_000:
            return None
        with Image.open(io.BytesIO(resp.content)) as raw:
            rgb = raw.convert("RGB")
            w, h = rgb.size
            if min(w, h) < 360:
                return None
            ratio = w / max(1, h)
            if ratio < 0.45 or ratio > 2.3:
                return None
            ph = _compute_phash(rgb)
            with phash_lock:
                if any(_hamming(ph, old) <= 8 for old in existing_phashes):
                    return None
                existing_phashes.append(ph)
            rgb.thumbnail((960, 960), Image.Resampling.LANCZOS)
            rgb.save(out_path, format="WEBP", quality=82, method=4)
            w2, h2 = rgb.size
        return {
            **cand,
            "cand_id": f"exp_{domain}_{uid}",
            "target_domain": domain,
            "local_path": str(out_path),
            "width": w2,
            "height": h2,
            "phash": ph,
        }
    except Exception:
        return None


def _score_candidate_vlm(
    oai: OpenAI,
    system_prompt: str,
    cand: dict[str, Any],
) -> dict[str, Any]:
    b64 = _encode_image_b64(Path(cand["local_path"]), max_side=384)
    user_text = (
        f"Expansion Candidate ID: {cand['cand_id']}\n"
        f"Intended Domain: {cand['target_domain']}\n"
        f"Search Query: {cand['query']}\n"
        f"Source Title: {cand['title']}\n"
        f"Dimensions: {cand['width']}x{cand['height']}\n"
        "Strictly reject tourist crowds, cluttered backgrounds, blurry images, watermarks, "
        "or off-topic illustrations. Keep ONLY publication-grade high-aesthetic design/architecture/craft/editorial/graphic references."
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            completion = oai.beta.chat.completions.parse(
                model="gpt-4o" if attempt >= 2 else DEFAULT_MODEL,
                temperature=0.1 if attempt == 0 else 0.3,
                frequency_penalty=0.0 if attempt == 0 else 0.4,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                response_format=PinterestVlmResearchItem,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Empty parsed response")
            payload = parsed.model_dump()
            for ax in AXIS_IDS:
                node = payload["style_spectrums"][ax]
                node["score"] = round(max(-1.0, min(1.0, float(node["score"]))), 2)
                node["salience"] = round(max(0.0, min(1.0, float(node["salience"]))), 2)
            return {"cand_id": cand["cand_id"], "vlm": payload}
        except RateLimitError as exc:
            last_err = exc
            time.sleep(min(15.0, 2.5 * (attempt + 1)))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"VLM failed for {cand['cand_id']}: {last_err}")


def _profile_distance(vlm_spectrums: dict[str, dict[str, float]], profile_sig: dict[str, dict[str, float]]) -> float:
    total = 0.0
    wsum = 0.0
    for ax in AXIS_IDS:
        target = float(profile_sig[ax]["weighted_mean"])
        cand_score = float(vlm_spectrums[ax]["score"])
        sal = max(0.15, float(vlm_spectrums[ax]["salience"]))
        total += sal * ((cand_score - target) ** 2)
        wsum += sal
    return math.sqrt(total / max(1e-6, wsum))


def main() -> None:
    EXPANSION_IMG_DIR.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE_JSON_PATH.read_text(encoding="utf-8"))
    research = json.loads(RESEARCH_JSON_PATH.read_text(encoding="utf-8"))
    expansion_quota: dict[str, int] = profile["expansion_quota_by_domain"]
    profile_sig = profile["axis_signature"]
    total_needed = int(profile["expansion_target_count"])

    existing_phashes = [it["phash"] for it in research["items"] if it.get("phash")]
    print(f"Expansion target: {total_needed} images | quota={expansion_quota}")

    candidates_by_domain: dict[str, list[dict[str, Any]]] = {}
    if EXPANSION_META_PATH.is_file():
        cached_meta = json.loads(EXPANSION_META_PATH.read_text(encoding="utf-8"))
        for d, lst in cached_meta.items():
            candidates_by_domain[d] = [c for c in lst if Path(c["local_path"]).is_file()]

    http_client = httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    phash_lock = threading.Lock()
    for c_list in candidates_by_domain.values():
        for c in c_list:
            if c.get("phash"):
                existing_phashes.append(c["phash"])

    for domain, need_n in expansion_quota.items():
        if need_n <= 0:
            continue
        target_pool = max(int(need_n * 1.8) + 6, 12)
        current = candidates_by_domain.setdefault(domain, [])
        if len(current) >= target_pool:
            print(f"[{domain}] Already have {len(current)}/{target_pool} downloaded candidates")
            continue

        raw_urls: list[dict[str, Any]] = []
        seen_urls = {c["url"] for c in current}
        # Interleave V&A Museum, Cleveland Museum of Art (CC0), and Wikimedia Commons
        for q in VAM_QUERIES.get(domain, []):
            for item in _search_vam(http_client, q, limit=14):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    raw_urls.append(item)
        for q in CMA_QUERIES.get(domain, []):
            for item in _search_cma(http_client, q, limit=12):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    raw_urls.append(item)
        for q in WIKIMEDIA_QUERIES.get(domain, []):
            for item in _search_wikimedia(http_client, q, limit=12):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    raw_urls.append(item)

        print(f"[{domain}] Downloading from {len(raw_urls)} hits (target pool={target_pool})...")
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = [
                pool.submit(_download_candidate, http_client, r, domain, existing_phashes, phash_lock)
                for r in raw_urls[: max(target_pool * 2, 100)]
            ]
            for fut in as_completed(futs):
                got = fut.result()
                if got:
                    current.append(got)
                    if len(current) >= target_pool:
                        break
        print(f"[{domain}] Downloaded pool ready: {len(current)} images")
        EXPANSION_META_PATH.write_text(
            json.dumps(candidates_by_domain, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    http_client.close()

    # 2. VLM score all downloaded candidates
    all_cands = [c for lst in candidates_by_domain.values() for c in lst]
    vlm_cache: dict[str, Any] = {}
    if EXPANSION_VLM_CACHE_PATH.is_file():
        try:
            vlm_cache = json.loads(EXPANSION_VLM_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            vlm_cache = {}

    todo = [c for c in all_cands if c["cand_id"] not in vlm_cache]
    print(f"Expansion VLM scoring: total={len(all_cands)}, cached={len(vlm_cache)}, todo={len(todo)}")
    if todo:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY required")
        oai = OpenAI()
        sys_prompt = _build_research_system_prompt()
        lock = threading.Lock()
        done = 0
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=12) as pool:
            futs = {pool.submit(_score_candidate_vlm, oai, sys_prompt, c): c["cand_id"] for c in todo}
            for fut in as_completed(futs):
                cid = futs[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Expansion VLM failed {cid}: {exc}")
                    continue
                with lock:
                    vlm_cache[res["cand_id"]] = res["vlm"]
                    done += 1
                    if done % 20 == 0 or done == len(todo):
                        EXPANSION_VLM_CACHE_PATH.write_text(
                            json.dumps(vlm_cache, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        print(f"Expansion VLM progress: {done}/{len(todo)} ({time.time()-t0:.1f}s)")
        EXPANSION_VLM_CACHE_PATH.write_text(
            json.dumps(vlm_cache, ensure_ascii=False),
            encoding="utf-8",
        )

    # 3. Rank by VLM quality + 8-axis Personal Aesthetic Profile alignment
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    enriched_all: list[dict[str, Any]] = []
    for c in all_cands:
        vlm = vlm_cache.get(c["cand_id"])
        if not vlm:
            continue
        pdist = _profile_distance(vlm["style_spectrums"], profile_sig)
        rank_score = (
            float(vlm["aesthetic_quality_score"]) * 1.25
            - pdist * 2.2
            + (1.5 if vlm["keep_for_aethervault"] else -4.0)
        )
        enriched_all.append(
            {
                **c,
                "vlm": vlm,
                "profile_distance": round(pdist, 4),
                "rank_score": round(rank_score, 4),
            }
        )

    for domain, need_n in expansion_quota.items():
        if need_n <= 0:
            continue
        pool_dom = [
            x
            for x in enriched_all
            if (x["vlm"]["domain"] == domain or x["target_domain"] == domain)
            and x["cand_id"] not in selected_ids
        ]
        pool_dom.sort(key=lambda x: (-x["rank_score"], x["profile_distance"]))
        picked = pool_dom[:need_n]
        for p in picked:
            selected.append(p)
            selected_ids.add(p["cand_id"])
        print(f"[{domain}] Selected {len(picked)}/{need_n} profile-matched expansion images")

    if len(selected) < total_needed:
        leftover = [x for x in enriched_all if x["cand_id"] not in selected_ids]
        leftover.sort(key=lambda x: (-x["rank_score"], x["profile_distance"]))
        for x in leftover[: total_needed - len(selected)]:
            selected.append(x)
            selected_ids.add(x["cand_id"])

    selected = selected[:total_needed]
    EXPANSION_SELECTED_PATH.write_text(
        json.dumps({"total_selected": len(selected), "items": selected}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] Selected exact {len(selected)}/{total_needed} profile-aligned expansion images -> {EXPANSION_SELECTED_PATH}")


if __name__ == "__main__":
    main()
