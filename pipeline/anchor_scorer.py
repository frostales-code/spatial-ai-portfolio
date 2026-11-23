"""5-Point Anchored VLM Batch Scorer for AetherVault (`MIC-157`).

Runs structured 4-layer orthogonal aesthetic scoring across all 80 curated assets
using OpenAI `gpt-4o-mini` with Prompt Caching + Strict Structured Outputs, verifies
observed token cost <= CNY 0.008/image, computes empirical Spearman rank correlation
rho against the curated rubric baseline, and updates showcase JSON bundles.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI, RateLimitError
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from scipy.stats import spearmanr

from .aethervault_schema import (
    AXIS_IDS,
    SPECTRUM_AXES,
    AestheticAsset,
    CompilerPrimitives,
    GranularDescriptors,
    StyleSpectrumAxis,
    SubjectIsolation,
)
from .anchor_specs import (
    GOLDEN_ANCHOR_RUBRICS,
    build_vlm_calibration_system_prompt,
    build_vlm_scoring_user_prompt,
    estimate_ingestion_cost_cny,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_ROOT = REPO_ROOT / "data" / "curated_80"
IMAGES_DIR = CURATED_ROOT / "images"
ASSETS_JSON_PATH = CURATED_ROOT / "aethervault_assets_v1.json"
VLM_CACHE_PATH = CURATED_ROOT / "_vlm_scores_cache.json"
VLM_REPORT_PATH = CURATED_ROOT / "vlm_scoring_report.json"
WEB_SHOWCASE_JSON = REPO_ROOT / "web" / "public" / "data" / "aethervault_showcase_v1.json"

DEFAULT_MODEL = "gpt-4o-mini"
USD_TO_CNY = 7.25
# Standard online gpt-4o-mini rates ($ / 1M tokens)
PRICE_UNCACHED_INPUT_USD_M = 0.15
PRICE_CACHED_INPUT_USD_M = 0.075
PRICE_OUTPUT_USD_M = 0.60


class StrictAxisReading(BaseModel):
    """OpenAI Strict Structured Output safe score + salience pair."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(..., description="Continuous score in [-1.0, +1.0] calibrated to 0.05 precision.")
    salience: float = Field(..., description="Visual salience weight in [0.0, 1.0].")


class StrictStyleSpectrums(BaseModel):
    """Explicit 8-axis struct required by OpenAI Structured Outputs (no dynamic dict keys)."""

    model_config = ConfigDict(extra="forbid")

    tectonic_honesty: StrictAxisReading
    surface_entropy: StrictAxisReading
    spatial_density: StrictAxisReading
    geometric_order: StrictAxisReading
    lighting_drama: StrictAxisReading
    chromatic_tension: StrictAxisReading
    thermal_mood: StrictAxisReading
    reality_abstraction: StrictAxisReading


class VlmStrictScoredAsset(BaseModel):
    """Strict 4-layer VLM output payload mapped back into AestheticAsset."""

    model_config = ConfigDict(extra="forbid")

    primary_subject: str
    style_spectrums: StrictStyleSpectrums
    optics_camera: str
    material_stack: str
    lighting_rig: str
    positive_tokens: list[str]
    negative_guardrails: list[str]


def _clamp(val: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, float(val))), 2)


def _encode_low_token_jpeg(img_path: Path) -> str:
    with Image.open(img_path) as im:
        thumb = im.convert("RGB").resize((512, 384), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _score_single_asset(
    client: OpenAI,
    system_prompt: str,
    raw_asset: dict[str, object],
    model: str = DEFAULT_MODEL,
) -> dict[str, object]:
    asset_id = str(raw_asset["asset_id"])
    img_path = IMAGES_DIR / f"{asset_id}.webp"
    if not img_path.exists():
        raise FileNotFoundError(f"Missing curated image: {img_path}")

    palette = list(raw_asset.get("granular_descriptors", {}).get("color_palette", []))  # type: ignore[union-attr]
    user_prompt = build_vlm_scoring_user_prompt(asset_id, palette)
    img_b64 = _encode_low_token_jpeg(img_path)

    t0 = time.perf_counter()
    completion = None
    for attempt in range(6):
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                temperature=0.0,
                max_tokens=480,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                response_format=VlmStrictScoredAsset,
            )
            break
        except RateLimitError:
            if attempt == 5:
                raise
            time.sleep(3 + attempt * 2)

    assert completion is not None
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    parsed: VlmStrictScoredAsset = completion.choices[0].message.parsed  # type: ignore[assignment]
    usage = completion.usage
    prompt_tokens = int(usage.prompt_tokens) if usage else 0
    completion_tokens = int(usage.completion_tokens) if usage else 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)

    return {
        "asset_id": asset_id,
        "model": model,
        "parsed": parsed.model_dump(),
        "usage": {
            "prompt_tokens": prompt_tokens,
            "cached_tokens": cached_tokens,
            "uncached_prompt_tokens": max(0, prompt_tokens - cached_tokens),
            "completion_tokens": completion_tokens,
            "latency_ms": elapsed_ms,
        },
    }


def _compute_cost_metrics(usages: list[dict[str, int | float]]) -> dict[str, object]:
    total_prompt = sum(int(u["prompt_tokens"]) for u in usages)
    total_cached = sum(int(u["cached_tokens"]) for u in usages)
    total_uncached = sum(int(u["uncached_prompt_tokens"]) for u in usages)
    total_completion = sum(int(u["completion_tokens"]) for u in usages)
    n = max(1, len(usages))

    online_usd = (
        (total_uncached / 1_000_000.0) * PRICE_UNCACHED_INPUT_USD_M
        + (total_cached / 1_000_000.0) * PRICE_CACHED_INPUT_USD_M
        + (total_completion / 1_000_000.0) * PRICE_OUTPUT_USD_M
    )
    online_cny_total = online_usd * USD_TO_CNY
    online_cny_per_img = online_cny_total / n
    batch_cny_per_img = online_cny_per_img * 0.5  # OpenAI Batch API 50% discount tier

    return {
        "scored_count": len(usages),
        "total_prompt_tokens": total_prompt,
        "total_cached_tokens": total_cached,
        "total_uncached_prompt_tokens": total_uncached,
        "total_completion_tokens": total_completion,
        "cache_hit_rate": round(total_cached / max(1, total_prompt), 4),
        "avg_prompt_tokens_per_img": round(total_prompt / n, 1),
        "avg_completion_tokens_per_img": round(total_completion / n, 1),
        "observed_online_total_cny": round(online_cny_total, 4),
        "observed_online_cny_per_img": round(online_cny_per_img, 6),
        "batch_api_equivalent_cny_per_img": round(batch_cny_per_img, 6),
        "target_ceiling_cny_per_img": 0.008,
        "within_budget": online_cny_per_img <= 0.008,
    }


def run_batch_scoring(force: bool = False, model: str = DEFAULT_MODEL, max_workers: int = 6) -> dict[str, object]:
    """Execute 5-point anchored VLM batch scoring across all 80 assets and emit audit report."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable must be set to run anchor_scorer.")
    if not ASSETS_JSON_PATH.exists():
        raise FileNotFoundError(f"Missing baseline curated assets JSON: {ASSETS_JSON_PATH}")

    assets_payload = json.loads(ASSETS_JSON_PATH.read_text(encoding="utf-8"))
    assets: list[dict[str, object]] = assets_payload["assets"]
    system_prompt = build_vlm_calibration_system_prompt()

    cache: dict[str, dict[str, object]] = {}
    if VLM_CACHE_PATH.exists() and not force:
        cache = json.loads(VLM_CACHE_PATH.read_text(encoding="utf-8"))

    # Preserve original curated rubric scores as golden reference before updating
    baseline_scores: dict[str, dict[str, float]] = {}
    for raw in assets:
        aid = str(raw["asset_id"])
        src_specs = raw.get("baseline_spectrums") or raw["style_spectrums"]
        baseline_scores[aid] = {
            ax: float(src_specs[ax]["score"])  # type: ignore[index]
            for ax in AXIS_IDS
        }

    client = OpenAI()
    pending = [a for a in assets if str(a["asset_id"]) not in cache]

    # Warm up OpenAI Prompt Cache with the first pending asset before fanning out
    if pending:
        first = pending.pop(0)
        res = _score_single_asset(client, system_prompt, first, model=model)
        cache[str(first["asset_id"])] = res
        VLM_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[WARMUP] {first['asset_id']} | prompt={res['usage']['prompt_tokens']} "
            f"(cached={res['usage']['cached_tokens']}) comp={res['usage']['completion_tokens']}"
        )

    if pending:
        print(f"Scoring remaining {len(pending)} assets via {model} (max_workers={max_workers})...")
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(_score_single_asset, client, system_prompt, a, model): a for a in pending}
            done_n = 0
            for fut in as_completed(futs):
                a = futs[fut]
                res = fut.result()
                cache[str(a["asset_id"])] = res
                done_n += 1
                if done_n % 10 == 0 or done_n == len(pending):
                    VLM_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                    u = res["usage"]
                    print(
                        f"[VLM {done_n}/{len(pending)}] {a['asset_id']} | "
                        f"cached={u['cached_tokens']}/{u['prompt_tokens']} | {u['latency_ms']}ms"
                    )

    # Map fixed golden anchor locks: (asset_id, axis_id) -> exact anchor level
    anchor_locks: dict[tuple[str, str], float] = {}
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        for pt in rubric.anchors:
            anchor_locks[(pt.reference_asset_id, axis_id)] = pt.level

    updated_assets: list[dict[str, object]] = []
    usages: list[dict[str, int | float]] = []

    for raw in assets:
        aid = str(raw["asset_id"])
        cached_entry = cache[aid]
        usages.append(cached_entry["usage"])  # type: ignore[arg-type]
        vlm_data = cached_entry["parsed"]  # type: ignore[assignment]
        vlm_specs: dict[str, dict[str, float]] = vlm_data["style_spectrums"]  # type: ignore[index]

        raw_vlm_spectrums: dict[str, dict[str, float]] = {}
        final_spectrums: dict[str, StyleSpectrumAxis] = {}
        for ax in AXIS_IDS:
            raw_sc = _clamp(vlm_specs[ax]["score"], -1.0, 1.0)
            raw_sal = _clamp(vlm_specs[ax]["salience"], 0.0, 1.0)
            raw_vlm_spectrums[ax] = {"score": raw_sc, "salience": raw_sal}

            # Blend curated rubric calibration with live VLM scoring while preserving anchor ticks
            base_sc = baseline_scores[aid][ax]
            if (aid, ax) in anchor_locks:
                locked_sc = anchor_locks[(aid, ax)]
                locked_sal = max(raw_sal, float(raw["style_spectrums"][ax]["salience"]))  # type: ignore[index]
                final_spectrums[ax] = StyleSpectrumAxis(score=locked_sc, salience=_clamp(locked_sal, 0.0, 1.0))
            else:
                # Average anchored VLM score with domain-verified baseline to prevent outlier spikes
                blended = _clamp(0.65 * raw_sc + 0.35 * base_sc, -1.0, 1.0)
                final_spectrums[ax] = StyleSpectrumAxis(score=blended, salience=raw_sal)

        # Preserve pre-extracted deterministic edge OKLab HEX palette
        edge_palette = list(raw["granular_descriptors"]["color_palette"])  # type: ignore[index]
        subj_raw = raw["subject_isolation"]  # type: ignore[assignment]

        validated = AestheticAsset(
            asset_id=aid,
            title=str(raw["title"]),
            subject_isolation=SubjectIsolation(
                domain=subj_raw["domain"],  # type: ignore[index]
                domain_label=subj_raw["domain_label"],  # type: ignore[index]
                primary_subject=str(vlm_data["primary_subject"] or subj_raw["primary_subject"]),  # type: ignore[index]
                is_personal_prior=bool(subj_raw["is_personal_prior"]),  # type: ignore[index]
            ),
            style_spectrums=final_spectrums,
            granular_descriptors=GranularDescriptors(
                optics_camera=str(vlm_data["optics_camera"]),  # type: ignore[index]
                lighting_rig=str(vlm_data["lighting_rig"]),  # type: ignore[index]
                material_stack=str(vlm_data["material_stack"]),  # type: ignore[index]
                color_palette=edge_palette,
            ),
            compiler_primitives=CompilerPrimitives(
                positive_tokens=[str(t) for t in vlm_data["positive_tokens"]][:6],  # type: ignore[index]
                negative_guardrails=[str(t) for t in vlm_data["negative_guardrails"]][:6],  # type: ignore[index]
            ),
        )

        merged = validated.model_dump()
        merged.update(
            {
                "title_en": raw.get("title_en", ""),
                "image_url": raw.get("image_url", f"/assets/curated_80/{aid}.webp"),
                "license": raw.get("license", "CC0"),
                "source_kind": raw.get("source_kind", ""),
                "source_url": raw.get("source_url", ""),
                "akb_prior_asset_id": raw.get("akb_prior_asset_id"),
                "akb_board_hint": raw.get("akb_board_hint"),
                "baseline_spectrums": {
                    ax: {"score": baseline_scores[aid][ax], "salience": float(raw["style_spectrums"][ax]["salience"])}  # type: ignore[index]
                    for ax in AXIS_IDS
                },
                "vlm_raw_spectrums": raw_vlm_spectrums,
            }
        )
        updated_assets.append(merged)

    # Compute per-axis Spearman rho between un-clamped VLM raw scores and curated baseline
    axis_spearman: dict[str, float] = {}
    for ax in AXIS_IDS:
        base_vec = [baseline_scores[str(a["asset_id"])][ax] for a in updated_assets]
        vlm_vec = [a["vlm_raw_spectrums"][ax]["score"] for a in updated_assets]  # type: ignore[index]
        rho, _ = spearmanr(base_vec, vlm_vec)
        axis_spearman[ax] = 0.0 if math.isnan(float(rho)) else round(float(rho), 4)

    mean_spearman = round(sum(axis_spearman.values()) / len(AXIS_IDS), 4)
    cost_metrics = _compute_cost_metrics(usages)
    now_iso = datetime.now(timezone.utc).isoformat()

    report = {
        "version": "1.0.0",
        "generated_at": now_iso,
        "vlm_model": model,
        "pydantic_validation_passed": len(updated_assets),
        "total_assets": len(updated_assets),
        "mean_spearman_rho": mean_spearman,
        "per_axis_spearman_rho": axis_spearman,
        "cost_metrics": cost_metrics,
    }
    VLM_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persist updated 80-asset payload & showcase bundle
    assets_payload["generated_at"] = now_iso
    assets_payload["vlm_scoring_report"] = report
    assets_payload["assets"] = updated_assets
    ASSETS_JSON_PATH.write_text(json.dumps(assets_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    showcase_bundle = {
        "version": assets_payload.get("version", "1.0.0"),
        "generated_at": now_iso,
        "total_assets": len(updated_assets),
        "domain_counts": assets_payload["domain_counts"],
        "axes": [ax.model_dump() for ax in SPECTRUM_AXES],
        "golden_anchors": {k: v.model_dump() for k, v in GOLDEN_ANCHOR_RUBRICS.items()},
        "cost_ledger": estimate_ingestion_cost_cny(1000).model_dump(),
        "vlm_scoring_report": report,
        "assets": updated_assets,
    }
    WEB_SHOWCASE_JSON.write_text(json.dumps(showcase_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 5-point anchored VLM batch scorer (`MIC-157`).")
    parser.add_argument("--force", action="store_true", help="Ignore cached VLM scores and re-score all 80 assets.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    args = parser.parse_args()
    report = run_batch_scoring(force=args.force, model=args.model)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
