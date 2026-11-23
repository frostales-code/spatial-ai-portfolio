"""Verification suite for MIC-157: VLM batch scoring, cost ledger, and 6 AST comparisons."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

from pipeline.aethervault_schema import AXIS_IDS, AestheticAsset
from pipeline.anchor_specs import GOLDEN_ANCHOR_RUBRICS

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_ASSETS_JSON = REPO_ROOT / "data" / "curated_80" / "aethervault_assets_v1.json"
VLM_REPORT_JSON = REPO_ROOT / "data" / "curated_80" / "vlm_scoring_report.json"
COMPARE_JSON = REPO_ROOT / "data" / "ast_comparisons" / "ast_comparisons_v1.json"
COMPARE_DIR = REPO_ROOT / "data" / "ast_comparisons" / "images"
WEB_COMPARE_JSON = REPO_ROOT / "web" / "public" / "data" / "ast_comparisons_v1.json"
WEB_COMPARE_DIR = REPO_ROOT / "web" / "public" / "assets" / "ast_comparisons"
WEB_SHOWCASE_JSON = REPO_ROOT / "web" / "public" / "data" / "aethervault_showcase_v1.json"


def test_vlm_scoring_report_within_budget_and_valid() -> None:
    report = json.loads(VLM_REPORT_JSON.read_text(encoding="utf-8"))
    assert report["total_assets"] == 80
    assert report["pydantic_validation_passed"] == 80
    cost = report["cost_metrics"]
    assert cost["scored_count"] == 80
    assert cost["within_budget"] is True
    assert cost["observed_online_cny_per_img"] <= 0.008
    assert cost["batch_api_equivalent_cny_per_img"] <= 0.004
    assert len(report["per_axis_spearman_rho"]) == len(AXIS_IDS)

    assets = json.loads(CURATED_ASSETS_JSON.read_text(encoding="utf-8"))["assets"]
    assert len(assets) == 80
    by_id = {a["asset_id"]: a for a in assets}
    for raw in assets:
        AestheticAsset.model_validate(
            {
                "asset_id": raw["asset_id"],
                "title": raw["title"],
                "subject_isolation": raw["subject_isolation"],
                "style_spectrums": raw["style_spectrums"],
                "granular_descriptors": raw["granular_descriptors"],
                "compiler_primitives": raw["compiler_primitives"],
            }
        )
        assert "vlm_raw_spectrums" in raw

    # Verify all 40 golden anchors remain locked on their authoritative ruler ticks
    for axis_id, rubric in GOLDEN_ANCHOR_RUBRICS.items():
        for pt in rubric.anchors:
            assert by_id[pt.reference_asset_id]["style_spectrums"][axis_id]["score"] == pt.level

    showcase = json.loads(WEB_SHOWCASE_JSON.read_text(encoding="utf-8"))
    assert "vlm_scoring_report" in showcase
    assert showcase["vlm_scoring_report"]["pydantic_validation_passed"] == 80


def test_six_ast_comparison_pairs_exist_and_sync() -> None:
    bundle = json.loads(COMPARE_JSON.read_text(encoding="utf-8"))
    assert bundle["total_pairs"] == 6
    pairs = bundle["pairs"]
    assert len(pairs) == 6

    for p in pairs:
        pid = p["pair_id"]
        assert p["conflicts_isolated_count"] >= 2
        assert "[OPTICS_LAYER]" in p["compiled_prompt"]
        assert "[MATERIAL_TECTONICS]" in p["compiled_prompt"]
        assert "[ATMOSPHERE_LIGHTING]" in p["compiled_prompt"]
        for suffix in ("naive", "ast"):
            for folder in (COMPARE_DIR, WEB_COMPARE_DIR):
                img_path = folder / f"{pid}_{suffix}.webp"
                assert img_path.exists(), f"Missing comparison render: {img_path}"
                with Image.open(img_path) as im:
                    assert im.size == (800, 600)

    web_bundle = json.loads(WEB_COMPARE_JSON.read_text(encoding="utf-8"))
    assert web_bundle["total_pairs"] == 6


def test_no_secrets_in_mic157_outputs() -> None:
    secret_pattern = re.compile(r"(sk-[A-Za-z0-9\-_]{20,}|AIza[0-9A-Za-z\-_]{20,})")
    for path in (CURATED_ASSETS_JSON, VLM_REPORT_JSON, COMPARE_JSON, WEB_COMPARE_JSON, WEB_SHOWCASE_JSON):
        assert not secret_pattern.search(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    test_vlm_scoring_report_within_budget_and_valid()
    test_six_ast_comparison_pairs_exist_and_sync()
    test_no_secrets_in_mic157_outputs()
    print("[PASS] All MIC-157 VLM scoring & 6-pair AST comparison checks passed!")
