"""Unit & Regression Tests for Taste & Anti-Homogenization Engine v2.1."""

from __future__ import annotations

import unittest

import numpy as np
from fastapi.testclient import TestClient

from pipeline.taste_engine_v2 import (
    DEFAULT_MEDOID_K,
    STRATUM_SPECS,
    _load_corpus,
    fit_bt_medoid_head,
    fit_hierarchical_bt_v21,
    load_or_build_medoid_profile,
    rerank_three_lanes,
    sample_next_calibration_pair,
)
from server.main import app


class TestTasteEngineV2(unittest.TestCase):
    def test_medoids_and_bt_signal_isolation(self) -> None:
        prof = load_or_build_medoid_profile()
        self.assertEqual(prof["k_medoids"], DEFAULT_MEDOID_K)
        self.assertEqual(len(prof["medoids"]), DEFAULT_MEDOID_K)

        rng = np.random.default_rng(7)
        phi = rng.normal(size=(40, DEFAULT_MEDOID_K)).astype(np.float32)
        id_to_idx = {f"a{i}": i for i in range(40)}
        prior_w = np.ones(DEFAULT_MEDOID_K, dtype=np.float32)

        core_votes = [
            {
                "signal": "core_taste",
                "asset_a": f"a{2 * i}",
                "asset_b": f"a{2 * i + 1}",
                "choice": "a" if phi[2 * i, 0] > phi[2 * i + 1, 0] else "b",
            }
            for i in range(12)
        ]
        serend_votes = [
            {
                "signal": "serendipity_save",
                "asset_a": f"a{2 * i}",
                "asset_b": f"a{2 * i + 1}",
                "choice": "b" if phi[2 * i, 0] > phi[2 * i + 1, 0] else "a",
            }
            for i in range(12)
        ]

        res_core_only = fit_bt_medoid_head(core_votes, phi, id_to_idx, prior_w)
        res_with_serend = fit_bt_medoid_head(core_votes + serend_votes, phi, id_to_idx, prior_w)
        self.assertTrue(res_core_only["fitted"])
        np.testing.assert_allclose(res_core_only["weights"], res_with_serend["weights"], atol=1e-6)

    def test_dark_monochrome_landscape_regression_rejected_as_contrast(self) -> None:
        """Codex pixel regression: darkening monochrome karesansui (`pext4_land_663`) must NOT pass contrast."""
        ctx = _load_corpus()
        idx = ctx["id_to_idx"]["pext4_land_663"]
        ct = ctx["contrast_table"][idx]
        self.assertFalse(ct["passes_contrast"])
        self.assertLess(ct["q_color"], 0.5)

    def test_four_stratified_samplers_and_7param_bt_macro_cancellation(self) -> None:
        ctx = _load_corpus()
        assets = ctx["assets"]
        for st in STRATUM_SPECS:
            pair = sample_next_calibration_pair("core_taste", stratum=st)
            self.assertIsNotNone(pair, f"Failed to sample stratum {st}")
            assert pair is not None
            self.assertEqual(pair["stratum"], st)
            # All 4 Q1 strata MUST be same-domain (never apples-vs-oranges!)
            self.assertEqual(pair["a"]["archetype"], pair["b"]["archetype"])
            if st == "T1_macro_style":
                self.assertNotEqual(pair["a"]["aesthetic_style_zh"], pair["b"]["aesthetic_style_zh"])
            if st == "T2_same_style_instance":
                ia = ctx["id_to_idx"][pair["a"]["asset_id"]]
                ib = ctx["id_to_idx"][pair["b"]["asset_id"]]
                # Macro terms (b_prior & g_macro) MUST cancel identically on T2 pairs!
                self.assertAlmostEqual(float(ctx["b_prior"][ia]), float(ctx["b_prior"][ib]), places=6)
                np.testing.assert_allclose(ctx["g_macro"][ia], ctx["g_macro"][ib], atol=1e-6)

        # Verify 7-param Hierarchical BT learns pure micro beta on synthetic T2 pairs
        phi_dummy = np.zeros((len(assets), DEFAULT_MEDOID_K), dtype=np.float32)
        same_style_pairs = []
        by_ds: dict[tuple[str, str], list[int]] = {}
        for i, a in enumerate(assets):
            by_ds.setdefault((a["archetype"], a["aesthetic_style"]), []).append(i)
        for idxs in by_ds.values():
            if len(idxs) >= 4:
                for k in range(0, min(6, len(idxs) - 1), 2):
                    ia, ib = idxs[k], idxs[k + 1]
                    ch = "a" if ctx["z_centered"][ia, 3] > ctx["z_centered"][ib, 3] else "b"
                    same_style_pairs.append(
                        {
                            "signal": "core_taste",
                            "asset_a": assets[ia]["asset_id"],
                            "asset_b": assets[ib]["asset_id"],
                            "choice": ch,
                            "meta": {"stratum": "T2_same_style_instance"},
                        }
                    )
                    if len(same_style_pairs) >= 24:
                        break
            if len(same_style_pairs) >= 24:
                break
        res = fit_hierarchical_bt_v21(same_style_pairs, ctx, phi_dummy)
        self.assertTrue(res["fitted"])
        self.assertGreaterEqual(res["cv_acc"], 0.85)
        self.assertGreater(res["beta_micro5"][3], 0.3)

    def test_three_lane_rerank_latency_and_honest_exploration_cap(self) -> None:
        _ = rerank_three_lanes(target_total=1110)
        res = rerank_three_lanes(target_total=1110)
        self.assertLess(res["latency_ms"], 20.0)
        lanes = res["lane_counts"]
        self.assertLessEqual(lanes["adversarial_exploration"], lanes["exploration_cap"])
        self.assertEqual(
            lanes["adversarial_exploration"],
            min(lanes["exploration_cap"], lanes["exploration_qualified_pool"]),
        )

    def test_fastapi_calibration_state_and_rerank_endpoints(self) -> None:
        client = TestClient(app)
        r1 = client.get("/api/atlas/calibration/state")
        self.assertEqual(r1.status_code, 200)
        data = r1.json()
        self.assertEqual(data["version"], "2.1.0")
        self.assertEqual(data["profile"]["k_medoids"], DEFAULT_MEDOID_K)
        self.assertEqual(data["total_anchors"], 16)
        self.assertIsNotNone(data["next_core_pair"])
        self.assertIn(data["next_core_pair"]["stratum"], STRATUM_SPECS)

        r2 = client.get("/api/atlas/calibration/rerank")
        self.assertEqual(r2.status_code, 200)
        self.assertLess(r2.json()["latency_ms"], 20.0)
        # Verify 7 aesthetic families + reason chips exposed cleanly
        af = data.get("aesthetic_families", {})
        self.assertEqual(len(af.get("families", [])), 7)
        self.assertEqual(af.get("total_personal_pins"), 390)
        self.assertGreaterEqual(len(af.get("reason_chips", [])), 8)

    def test_multi_subject_gutter_guard_and_species_craft_rubric(self) -> None:
        from pipeline.craft_anchor_judge_v2 import build_species_craft_instruction

        ctx = _load_corpus(force_reload=True)
        ct = ctx["contrast_table"]
        for aid in ("pin_grap_005", "pin_grap_027"):
            idx = ctx["id_to_idx"][aid]
            entry = ct[idx]
            self.assertTrue(entry["gutter_guarded"], f"{aid} should be gutter-guarded")
            self.assertNotEqual(entry["primary_axis"], "composition_4x4")

        sketch_inst = build_species_craft_instruction("sketch_process_diagram", "single_unified")
        self.assertIn("Gestural Sketch", sketch_inst)
        sheet_inst = build_species_craft_instruction("multi_subject_sheet", "multi_subject_composite")
        self.assertIn("Multi-Subject Sheet", sheet_inst)

    def test_q1_avoids_re_voting_two_personal_pins_and_retains_tie_like_reasons(self) -> None:
        from pipeline.taste_engine_v2 import _build_aesthetic_families_summary

        ctx = _load_corpus()
        for stratum in STRATUM_SPECS:
            pair = sample_next_calibration_pair("core_taste", stratum=stratum)
            self.assertIsNotNone(pair)
            both_personal = (
                pair["a"].get("source_origin") == "pinterest_personal"
                and pair["b"].get("source_origin") == "pinterest_personal"
            )
            self.assertFalse(both_personal, f"Q1 {stratum} should not pair two already-liked personal pins")

        synth_votes = [
            {
                "signal": "core_taste",
                "asset_a": "pin_arch_107",
                "asset_b": "pin_arch_128",
                "choice": "tie_like",
                "chosen_reasons": ["光影与明暗塑形", "留白与静谧克制"],
                "reason_note": "两张都很安静克制",
            }
        ]
        summary = _build_aesthetic_families_summary(ctx, synth_votes)
        ra = summary["reason_attribution"]
        self.assertEqual(ra["total_votes_with_reasons"], 1)
        self.assertEqual(ra["tie_like_votes_with_reasons"], 1)
        self.assertEqual(ra["top_reasons"][0]["count"], 1)
        self.assertEqual(len(ra["recent_notes"]), 1)


if __name__ == "__main__":
    unittest.main()
