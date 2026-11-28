"""Reference-Anchored Craft Floor Judge v2 + Full-Funnel Cost Ledger.

Replaces blind 1-10 single-image VLM scoring (which suffered 85.7% inflation in scores 8-9)
with a domain-matched Craft Floor Anchor comparison:
- Feeds `[Domain Craft Floor Anchor Image, Candidate Image]` to `gemini-4-hydrogen` (`temperature=0.1`).
- Returns `{meets_floor: bool, margin: "above"|"at"|"below", pixel_evidence_zh: str}`.
- Shared identically across Core, Cross-Domain Bridge, and Adversarial Exploration lanes.
- Tracks FULL-FUNNEL RMB cost per final admitted asset (including rejected candidates,
  anchor image input tokens, and retries) against the `<= ¥0.008 / admitted asset` discipline.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .taste_engine_v2 import (
    CRAFT_VERDICTS_V2_PATH,
    REPO_ROOT,
    load_or_init_craft_anchors,
)

WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
JUDGE_MODEL = "gemini-4-hydrogen"

# Conservative RMB token pricing estimate for full-funnel cost audit (USD->RMB 7.25)
# Input ~$0.15/1M tokens (~¥1.09/1M), Output ~$0.60/1M tokens (~¥4.35/1M)
RMB_PER_INPUT_TOKEN = 1.09 / 1_000_000.0
RMB_PER_OUTPUT_TOKEN = 4.35 / 1_000_000.0

CRAFT_ANCHOR_SYSTEM_PROMPT = """You are a strict monograph art director performing a relative Craft Floor check.
You will see TWO images:
- IMAGE 1 (ANCHOR): The minimum acceptable Craft Floor reference for this visual domain.
- IMAGE 2 (CANDIDATE): The candidate image being judged.

Ignore whether IMAGE 2's style is familiar or unfamiliar/bold/experimental. Judge ONLY objective craft and visual execution:
composition rigor, lighting/tonal control, material or linework clarity, framing cleanliness, and absence of compression/watermarks/cluttered ad overlays.

Return strict JSON:
- `meets_floor`: true ONLY if IMAGE 2 meets or exceeds IMAGE 1's craft execution standard.
- `margin`: "above" (clearly higher craft than Anchor), "at" (roughly equal to Anchor floor), or "below" (falls short of Anchor floor).
- `pixel_evidence_zh`: One concrete Chinese sentence (18-45 chars) citing a specific visible pixel/framing/lighting/detail difference between IMAGE 2 and IMAGE 1."""


class CraftAnchorVerdict(BaseModel):
    meets_floor: bool
    margin: Literal["above", "at", "below"]
    pixel_evidence_zh: str = Field(..., min_length=8, max_length=90)


def build_species_craft_instruction(
    image_species: str | None = None,
    subject_structure: str | None = None,
) -> str:
    """Adapt Craft Floor evaluation rubric to the candidate's visual species (never judge sketches or multi-panel sheets as single photos)."""
    if subject_structure == "multi_subject_composite" or image_species == "multi_subject_sheet":
        return (
            "SPECIES OVERRIDE (Multi-Subject Sheet / Comparative Board): "
            "Do NOT penalize IMAGE 2 for lacking a single focal point or having panel gutters. "
            "Judge per-panel clarity, visual alignment/shared baseline consistency, typography cleanliness, and absence of watermarks or sloppy typos."
        )
    if image_species == "sketch_process_diagram":
        return (
            "SPECIES OVERRIDE (Gestural Sketch / Process Drawing): "
            "Do NOT penalize IMAGE 2 for loose hand-drawn strokes, monochrome ink, or unfinished edges. "
            "Judge gestural line-weight energy, rhythmic density/negative-space balance, and clean scan presentation without UI overlays or watermarks."
        )
    if image_species in {"color_material_specimen", "ui_digital_interface"}:
        return (
            "SPECIES OVERRIDE (Color/Material Specimen or Digital UI): "
            "Judge swatch/typographic hierarchy, contrast legibility, grid discipline, and absence of typos, fake color codes, or mobile screenshot chrome."
        )
    return (
        "SPECIES CONTEXT (Single Unified Photograph / Artwork): "
        "Judge composition rigor, directional lighting/tonal control, material clarity, framing cleanliness, and absence of watermarks or compression artifacts."
    )


def judge_candidate_against_anchor(
    client: genai.Client,
    anchor_img_path: Path,
    candidate_img_path: Path,
    anchor_id: str,
    candidate_id: str,
    image_species: str | None = None,
    subject_structure: str | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Run one species-aware relative Craft Floor comparison and return (verdict_dict, token_usage)."""
    anchor_bytes = anchor_img_path.read_bytes()
    cand_bytes = candidate_img_path.read_bytes()
    species_clause = build_species_craft_instruction(image_species, subject_structure)
    usage_acc = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "retries": 0}
    last_err: Exception | None = None

    for attempt in range(5):
        usage_acc["calls"] += 1
        if attempt > 0:
            usage_acc["retries"] += 1
        try:
            resp = client.models.generate_content(
                model=JUDGE_MODEL,
                contents=[
                    "IMAGE 1 (CRAFT FLOOR ANCHOR):",
                    types.Part.from_bytes(data=anchor_bytes, mime_type="image/webp"),
                    "IMAGE 2 (CANDIDATE TO JUDGE):",
                    types.Part.from_bytes(data=cand_bytes, mime_type="image/webp"),
                    f"{species_clause}\nDoes IMAGE 2 meet or exceed IMAGE 1's craft floor within its native visual species? Return CraftAnchorVerdict JSON.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=CRAFT_ANCHOR_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=CraftAnchorVerdict,
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            um = getattr(resp, "usage_metadata", None)
            if um is not None:
                usage_acc["input_tokens"] += int(getattr(um, "prompt_token_count", 0) or 0)
                usage_acc["output_tokens"] += int(getattr(um, "candidates_token_count", 0) or 0)
            parsed = CraftAnchorVerdict.model_validate_json((resp.text or "").strip())
            verdict = {
                "asset_id": candidate_id,
                "anchor_id": anchor_id,
                "image_species": image_species or "single_unified",
                "subject_structure": subject_structure or "single_unified",
                "meets_floor": bool(parsed.meets_floor),
                "margin": parsed.margin,
                "pixel_evidence_zh": parsed.pixel_evidence_zh.strip(),
            }
            return verdict, usage_acc
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait_s = min(60.0, 12.0 * (attempt + 1)) if "429" in str(exc) else min(10.0, 2.0 * (attempt + 1))
            time.sleep(wait_s)
    raise RuntimeError(f"Craft Anchor Judge failed for {candidate_id}: {last_err}")


def batch_judge_candidates(
    candidates: list[dict[str, Any]],
    use_contrast_anchor: bool = False,
    max_workers: int = 6,
) -> dict[str, Any]:
    """Batch-judge candidates against domain Craft Floor anchors with incremental cache & full-funnel cost audit."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY required for Craft Anchor Judge.")
    client = genai.Client(api_key=key)

    anchors = load_or_init_craft_anchors()["domains"]
    cache: dict[str, dict[str, Any]] = {}
    if CRAFT_VERDICTS_V2_PATH.is_file():
        try:
            cache = json.loads(CRAFT_VERDICTS_V2_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    todo = [c for c in candidates if c["asset_id"] not in cache]
    total_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "retries": 0}
    lock = threading.Lock()

    def _run_one(c: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        dom = c["archetype"]
        role_key = "contrast_anchor" if use_contrast_anchor else "familiar_anchor"
        anc = anchors[dom][role_key]
        anc_path = WEB_PUBLIC_DIR / anc["image_url"].lstrip("/")
        cand_path = Path(c["local_path"]) if c.get("local_path") else (WEB_PUBLIC_DIR / c["image_url"].lstrip("/"))
        return judge_candidate_against_anchor(client, anc_path, cand_path, anc["asset_id"], c["asset_id"])

    if todo:
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(_run_one, c): c["asset_id"] for c in todo}
            for fut in as_completed(futs):
                verdict, usage = fut.result()
                with lock:
                    cache[verdict["asset_id"]] = verdict
                    for k in total_usage:
                        total_usage[k] += usage[k]
                    done += 1
                    if done % 15 == 0 or done == len(todo):
                        CRAFT_VERDICTS_V2_PATH.write_text(
                            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
        CRAFT_VERDICTS_V2_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    evaluated = [cache[c["asset_id"]] for c in candidates if c["asset_id"] in cache]
    admitted = [v for v in evaluated if v.get("meets_floor")]
    total_rmb = (
        total_usage["input_tokens"] * RMB_PER_INPUT_TOKEN
        + total_usage["output_tokens"] * RMB_PER_OUTPUT_TOKEN
    )
    rmb_per_admitted = round(total_rmb / max(1, len(admitted)), 5) if todo else 0.0

    return {
        "total_candidates": len(candidates),
        "newly_judged": len(todo),
        "admitted_count": len(admitted),
        "pass_rate": round(len(admitted) / max(1, len(evaluated)), 4),
        "full_funnel_cost_ledger": {
            "total_calls": total_usage["calls"],
            "retries": total_usage["retries"],
            "input_tokens": total_usage["input_tokens"],
            "output_tokens": total_usage["output_tokens"],
            "total_rmb": round(total_rmb, 5),
            "rmb_per_admitted_asset": rmb_per_admitted,
            "within_budget_0_008": rmb_per_admitted <= 0.008,
        },
    }
