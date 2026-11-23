"""Verification suite for MIC-156 curated 80 assets, 40 golden anchors, and cost ledger."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

from pipeline.aethervault_schema import AestheticAsset
from pipeline.anchor_specs import ANCHOR_LEVELS, GOLDEN_ANCHOR_RUBRICS, estimate_ingestion_cost_cny

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_ROOT = REPO_ROOT / "data" / "curated_80"
ASSETS_JSON = CURATED_ROOT / "aethervault_assets_v1.json"
MANIFEST_JSON = CURATED_ROOT / "curation_manifest.json"
WEB_SHOWCASE_JSON = REPO_ROOT / "web" / "public" / "data" / "aethervault_showcase_v1.json"
WEB_IMAGES_DIR = REPO_ROOT / "web" / "public" / "assets" / "curated_80"


def test_golden_anchor_rubrics_complete_and_unique() -> None:
    assert len(GOLDEN_ANCHOR_RUBRICS) == 8
    referenced_ids: list[str] = []
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        assert rubric.axis_id == axis_id
        levels = tuple(pt.level for pt in rubric.anchors)
        assert levels == ANCHOR_LEVELS
        referenced_ids.extend(pt.reference_asset_id for pt in rubric.anchors)
    assert len(referenced_ids) == 40
    assert len(set(referenced_ids)) == 40


def test_cold_start_cost_ledger_within_budget() -> None:
    ledger = estimate_ingestion_cost_cny(1000)
    assert ledger.within_budget is True
    assert ledger.effective_cost_cny_per_img <= 0.008


def test_curated_80_bundle_integrity_and_distribution() -> None:
    payload = json.loads(ASSETS_JSON.read_text(encoding="utf-8"))
    assets = payload["assets"]
    assert payload["total_assets"] == 80
    assert len(assets) == 80

    domain_counts: dict[str, int] = {}
    by_id: dict[str, dict] = {}
    for raw in assets:
        # Strict Pydantic Layer 1-4 schema validation
        parsed = AestheticAsset.model_validate(
            {
                "asset_id": raw["asset_id"],
                "title": raw["title"],
                "subject_isolation": raw["subject_isolation"],
                "style_spectrums": raw["style_spectrums"],
                "granular_descriptors": raw["granular_descriptors"],
                "compiler_primitives": raw["compiler_primitives"],
            }
        )
        assert len(parsed.granular_descriptors.color_palette) >= 3
        dom = parsed.subject_isolation.domain
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        by_id[parsed.asset_id] = raw

        # Check both data/ and web/public/ WebP files exist and decode cleanly
        for img_path in [
            CURATED_ROOT / "images" / f"{parsed.asset_id}.webp",
            WEB_IMAGES_DIR / f"{parsed.asset_id}.webp",
        ]:
            assert img_path.exists(), f"Missing image {img_path}"
            with Image.open(img_path) as im:
                assert im.size == (800, 600)

    assert len(domain_counts) == 5
    assert all(count == 16 for count in domain_counts.values()), f"Imbalanced domains: {domain_counts}"

    # Verify all 40 golden anchor references resolve to matching axis score in curated assets
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        for pt in rubric.anchors:
            rec = by_id[pt.reference_asset_id]
            assert rec["style_spectrums"][axis_id]["score"] == pt.level
            assert rec["style_spectrums"][axis_id]["salience"] >= 0.85

    # Verify manifest and showcase JSON sync
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    assert manifest["total_assets"] == 80
    assert all(r["redistribution_safe"] is True for r in manifest["records"])
    assert WEB_SHOWCASE_JSON.exists()
    showcase = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8"))
    assert showcase["total_assets"] == 80
    assert len(showcase["golden_anchors"]) == 8


def test_no_secrets_leaked_in_curated_outputs() -> None:
    secret_pattern = re.compile(r"(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{20,})")
    for path in [ASSETS_JSON, MANIFEST_JSON, WEB_SHOWCASE_JSON]:
        text = path.read_text(encoding="utf-8")
        assert not secret_pattern.search(text), f"Potential secret found in {path}"


if __name__ == "__main__":
    test_golden_anchor_rubrics_complete_and_unique()
    test_cold_start_cost_ledger_within_budget()
    test_curated_80_bundle_integrity_and_distribution()
    test_no_secrets_leaked_in_curated_outputs()
    print("[PASS] All MIC-156 curation & golden anchor checks passed!")
