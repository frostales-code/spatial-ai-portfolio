"""Reproducible Benchmark for Taste & Anti-Homogenization Engine v2.

Measures:
1. Local Zero-LLM 3-Lane Rerank + Intra-Lane MMR latency across 30 runs (p50 / p95 / max; gate: p95 < 20ms).
2. PinnerSage K=10 Ward Medoids vs Single-Centroid alignment across 390 personal origins & 1110 expansions.
3. Empirical 8-axis correlation matrix & single-axis controlled inversion pool size.
4. Dual-signal calibration evaluation (Core BT head vs Max-Medoid vs Single-Centroid; Serendipity save rate).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from pipeline.taste_engine_v2 import (
    REPO_ROOT,
    load_or_build_medoid_profile,
    rerank_three_lanes,
)

REPORT_OUT = REPO_ROOT / "eval" / "reports" / "taste_engine_v2_bench.json"


def main() -> None:
    profile = load_or_build_medoid_profile()
    # Warm-up 1 call to load npz/json into cache
    _ = rerank_three_lanes(target_total=1110)

    latencies: list[float] = []
    last_res = None
    for _ in range(30):
        t0 = time.perf_counter()
        last_res = rerank_three_lanes(target_total=1110)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    arr = np.asarray(latencies, dtype=np.float64)
    p50 = round(float(np.percentile(arr, 50)), 2)
    p95 = round(float(np.percentile(arr, 95)), 2)
    pmax = round(float(arr.max()), 2)

    report = {
        "version": "2.0.0-taste-bench",
        "k_medoids": profile["k_medoids"],
        "personal_count": profile["personal_count"],
        "total_atlas_count": profile["total_atlas_count"],
        "rerank_latency_ms": {
            "runs": len(latencies),
            "p50_ms": p50,
            "p95_ms": p95,
            "max_ms": pmax,
            "pass_under_20ms": p95 < 20.0,
        },
        "lane_counts": last_res["lane_counts"] if last_res else {},
        "bt_model": last_res["bt_model"] if last_res else {},
        "serendipity_eval": last_res["serendipity_eval"] if last_res else {},
        "coupled_axis_pairs_gt_035": profile["coupled_axis_pairs_gt_035"],
    }
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Taste Engine v2 Benchmark ===")
    print(f"Medoids: K={profile['k_medoids']} on {profile['personal_count']} personal pins | Total Atlas: {profile['total_atlas_count']}")
    print(f"Zero-LLM 3-Lane + MMR Latency (30 runs): p50={p50}ms, p95={p95}ms, max={pmax}ms | PASS(<20ms)={p95 < 20.0}")
    print(f"Lane Counts: {report['lane_counts']}")
    print(f"BT Model: {report['bt_model']} | Serendipity: {report['serendipity_eval']}")
    print(f"Report saved -> {REPORT_OUT}")


if __name__ == "__main__":
    main()
