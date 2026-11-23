"""M4 Regression Suite: EDD 4-Benchmark Integrity & FastAPI Live Engine (`MIC-164`, `MIC-165`, `MIC-166`)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eval.run_all_evals import run_all
from server.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
EDD_REPORT_JSON = REPO_ROOT / "eval" / "reports" / "edd_benchmark_v1.json"
WEB_EDD_JSON = REPO_ROOT / "web" / "public" / "data" / "edd_benchmark_v1.json"
EDD_MD = REPO_ROOT / "eval" / "reports" / "EDD_BENCHMARK_REPORT.md"


class TestM4EddAndLiveEngine(unittest.TestCase):
    def test_m4_four_evals_and_bad_cases_reproducible(self) -> None:
        bundle = run_all()
        self.assertTrue(EDD_REPORT_JSON.is_file())
        self.assertTrue(WEB_EDD_JSON.is_file())
        self.assertTrue(EDD_MD.is_file())

        # Eval 01
        e1 = bundle["eval_01_spearman"]
        self.assertGreater(e1["raw_vlm_first_pass_rho"], 0.60)
        self.assertGreater(e1["observed_mean_spearman_rho"], 0.80)
        self.assertGreaterEqual(e1["top5_salience_alignment_rate"], 0.85)
        self.assertLess(e1["rerank_latency_p50_ms"], 20.0)

        # Eval 02
        e2 = bundle["eval_02_decouple"]
        self.assertEqual(e2["tasks_evaluated"], 20)
        self.assertGreaterEqual(e2["ast_composite_decoupling_rate"], 0.85)
        self.assertEqual(e2["zero_foreign_entity_leak_rate"], 1.0)

        # Eval 03
        e3 = bundle["eval_03_homography"]
        self.assertLess(e3["max_vanishing_deviation_deg"], 1.5)
        self.assertGreaterEqual(e3["min_non_mask_psnr_db"], 38.0)
        self.assertTrue(e3["all_cases_passed_gate"])

        # Eval 04 & Bad Case #3 UNKNOWN_PRICE_MISSING
        e4 = bundle["eval_04_cost_backtest"]
        self.assertEqual(e4["settlements_evaluated"], 15)
        self.assertGreaterEqual(e4["interval_hit_rate"], 0.80)
        self.assertEqual(e4["bad_case_trace"]["cost_status_returned"], "UNKNOWN_PRICE_MISSING")
        self.assertTrue(e4["bad_case_trace"]["fabricated_zero_blocked"])

    def test_fastapi_m4_live_intent_and_homography_endpoints(self) -> None:
        client = TestClient(app)

        # 1. Fuzzy intent parsing (works gracefully even without external API keys)
        intent_res = client.post(
            "/api/aethervault/parse-intent",
            json={"query": "粗犷外露耐候钢 极地冷灰 留白克制", "use_llm": True},
        )
        self.assertEqual(intent_res.status_code, 200)
        intent_body = intent_res.json()
        self.assertGreaterEqual(len(intent_body["matched_tokens"]), 2)
        self.assertIn("tectonic_honesty", intent_body["target_scores"])

        # 2. Live 4-point homography projection + extreme tilt guardrail flag
        normal_quad = [
            {"x": 110, "y": 110},
            {"x": 690, "y": 110},
            {"x": 690, "y": 510},
            {"x": 110, "y": 510},
        ]
        proj_res = client.post(
            "/api/tectonic/project-seams",
            json={
                "image_quad": normal_quad,
                "facade_width_mm": 7200,
                "facade_height_mm": 3600,
                "panel_width_mm": 1200,
                "panel_height_mm": 2400,
            },
        )
        self.assertEqual(proj_res.status_code, 200)
        proj_body = proj_res.json()
        self.assertLess(proj_body["vertical_vanishing_deviation_deg"], 1.5)
        self.assertFalse(proj_body["extreme_tilt_warning"])

        extreme_quad = [
            {"x": 280, "y": 130},
            {"x": 520, "y": 140},
            {"x": 720, "y": 520},
            {"x": 80, "y": 520},
        ]
        tilt_res = client.post(
            "/api/tectonic/project-seams",
            json={"image_quad": extreme_quad},
        )
        self.assertEqual(tilt_res.status_code, 200)
        self.assertTrue(tilt_res.json()["extreme_tilt_warning"])

        # 3. Live EDD benchmark JSON endpoint
        bench_res = client.get("/api/eval/benchmark")
        self.assertEqual(bench_res.status_code, 200)
        self.assertEqual(bench_res.json()["eval_04_cost_backtest"]["settlements_evaluated"], 15)


if __name__ == "__main__":
    unittest.main()
