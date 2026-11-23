"""M2 Regression & Empirical Verification Suite for TectonicLoop (`MIC-159`, `MIC-160`, `MIC-161`)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from pipeline.tectonic_catalog import _zone_from_sku
from pipeline.tectonic_state import calculate_zone_cost, summarize_project_ve
from server.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "pipeline" / "tectonic_catalog_v1.json"
SHOWCASE_PATH = REPO_ROOT / "data" / "tectonic_cases" / "tectonic_showcase_v1.json"
WEB_SHOWCASE_PATH = REPO_ROOT / "web" / "public" / "data" / "tectonic_showcase_v1.json"
WEB_IMAGES_DIR = REPO_ROOT / "web" / "public" / "assets" / "tectonic_cases"


class TestM2TectonicPipeline(unittest.TestCase):
    def test_catalog_30_skus_and_unknown_price_missing_rule(self) -> None:
        self.assertTrue(CATALOG_PATH.exists(), f"Missing {CATALOG_PATH}")
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(catalog["total_assemblies"], 30)
        self.assertEqual(len(catalog["assemblies"]), 30)
        self.assertGreaterEqual(len(catalog["lint_rules"]), 8)
        self.assertGreaterEqual(len(catalog["cad_details"]), 8)

        # Strict honesty rule: unpriced SKU must return UNKNOWN_PRICE_MISSING and never coerce to 0
        z_unpriced = _zone_from_sku(
            "facade_wall_01",
            "Zone A",
            "mask.png",
            (0.0, 1.0, 0.0),
            24.0,
            1.8,
            "bespoke_bronze_patina_unpriced",
        )
        z_glass = _zone_from_sku(
            "glazing_portal_02",
            "Zone B",
            "mask.png",
            (0.0, 1.0, 0.0),
            10.5,
            1.7,
            "mullion_steel_1700",
        )
        bd = calculate_zone_cost(z_unpriced)
        self.assertEqual(bd.status, "UNKNOWN_PRICE_MISSING")
        self.assertIsNone(bd.material_and_substructure_cny)
        self.assertIsNone(bd.low_estimate_cny)

        summary = summarize_project_ve([z_unpriced, z_glass])
        self.assertTrue(summary.has_missing_prices)
        self.assertEqual(summary.cost_status, "PARTIAL_UNKNOWN_PRICE_MISSING")
        self.assertIn("facade_wall_01", summary.missing_price_zone_ids)

    def test_three_cases_tiers_psnr_and_homography_bounds(self) -> None:
        self.assertTrue(SHOWCASE_PATH.exists(), f"Missing {SHOWCASE_PATH}")
        self.assertTrue(WEB_SHOWCASE_PATH.exists(), f"Missing {WEB_SHOWCASE_PATH}")
        bundle = json.loads(WEB_SHOWCASE_PATH.read_text(encoding="utf-8"))
        cases = bundle["cases"]
        self.assertEqual(len(cases), 3)

        for case in cases:
            self.assertEqual(len(case["tiers"]), 3)
            for tier in case["tiers"]:
                img_filename = Path(tier["image_url"]).name
                web_img = WEB_IMAGES_DIR / img_filename
                self.assertTrue(web_img.exists(), f"Missing synced image {web_img}")
                with Image.open(web_img) as im:
                    self.assertEqual(im.size, (800, 600))

                if tier["tier_id"] == "tier_0_raw":
                    self.assertGreaterEqual(tier["summary"]["blocking_alerts_count"], 2)
                else:
                    self.assertEqual(tier["summary"]["blocking_alerts_count"], 0)
                    self.assertLess(
                        tier["homography_projection"]["vertical_vanishing_deviation_deg"],
                        1.5,
                    )
                    self.assertGreaterEqual(
                        tier["relight_metrics"]["non_mask_psnr_db"],
                        38.0,
                    )
                    self.assertGreater(
                        len(tier["homography_projection"]["seam_segments"]),
                        0,
                    )

    def test_fastapi_tectonic_endpoints(self) -> None:
        client = TestClient(app)
        res_cat = client.get("/api/tectonic/catalog")
        self.assertEqual(res_cat.status_code, 200)
        self.assertEqual(res_cat.json()["total_assemblies"], 30)

        res_cases = client.get("/api/tectonic/cases")
        self.assertEqual(res_cases.status_code, 200)
        self.assertEqual(len(res_cases.json()["cases"]), 3)

        res_img = client.get("/api/tectonic/images/case_01_corner_cafe_tier_1_balanced.webp")
        self.assertEqual(res_img.status_code, 200)
        self.assertEqual(res_img.headers["content-type"], "image/webp")

        sample_zones = res_cases.json()["cases"][0]["tiers"][1]["zones"]
        res_ve = client.post("/api/tectonic/calc-ve", json=sample_zones)
        self.assertEqual(res_ve.status_code, 200)
        body = res_ve.json()
        self.assertEqual(body["blocking_alerts_count"], 0)
        self.assertEqual(body["summary"]["cost_status"], "CALCULATED")

        res_seams = client.post(
            "/api/tectonic/project-seams",
            json={
                "image_quad": [
                    {"x": 110, "y": 59},
                    {"x": 666, "y": 59},
                    {"x": 666, "y": 571},
                    {"x": 110, "y": 571},
                ],
                "facade_width_mm": 7200.0,
                "facade_height_mm": 3400.0,
                "panel_width_mm": 1200.0,
                "panel_height_mm": 2400.0,
                "openings_mm": [],
            },
        )
        self.assertEqual(res_seams.status_code, 200)
        self.assertLess(res_seams.json()["vertical_vanishing_deviation_deg"], 1.5)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestM2TectonicPipeline)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("[PASS] All M2 TectonicLoop catalog, relight, and FastAPI checks passed!")
