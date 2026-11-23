"""Build unified Instant Showcase manifest (`web/public/showcase-bundle-v1.json`).

Audits all pre-baked JSON bundles (`aethervault_showcase_v1.json`,
`ast_comparisons_v1.json`, `tectonic_showcase_v1.json`) and verifies every
referenced `.webp` asset exists inside `web/public/assets/` before shipping
the static portfolio bundle.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "web" / "public"
DATA_DIR = PUBLIC_DIR / "data"
OUTPUT_MANIFEST = PUBLIC_DIR / "showcase-bundle-v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _assert_asset_exists(raw_url: str, missing: list[str]) -> None:
    rel = raw_url.lstrip("/")
    target = PUBLIC_DIR / rel
    if not target.is_file():
        missing.append(raw_url)


def build_showcase_manifest() -> dict[str, Any]:
    aether = _load_json(DATA_DIR / "aethervault_showcase_v1.json")
    ast_cmp = _load_json(DATA_DIR / "ast_comparisons_v1.json")
    tectonic = _load_json(DATA_DIR / "tectonic_showcase_v1.json")

    missing_assets: list[str] = []

    for asset in aether.get("assets", []):
        if url := asset.get("image_url"):
            _assert_asset_exists(str(url), missing_assets)

    for pair in ast_cmp.get("pairs", []):
        for key in ("naive_image_url", "ast_image_url"):
            if url := pair.get(key):
                _assert_asset_exists(str(url), missing_assets)

    case_list = tectonic.get("cases", [])
    tier_render_count = 0
    for case in case_list:
        for tier in case.get("tiers", []):
            tier_render_count += 1
            if url := tier.get("image_url"):
                _assert_asset_exists(str(url), missing_assets)

    if missing_assets:
        sample = ", ".join(missing_assets[:5])
        raise FileNotFoundError(
            f"Missing {len(missing_assets)} static asset(s) under {PUBLIC_DIR}: {sample}"
        )

    webp_files = list((PUBLIC_DIR / "assets").rglob("*.webp"))
    json_files = list(DATA_DIR.glob("*.json"))
    total_bytes = sum(p.stat().st_size for p in PUBLIC_DIR.rglob("*") if p.is_file())

    vlm_report = aether.get("vlm_scoring_report", {})
    cost_metrics = vlm_report.get("cost_metrics", {})

    manifest: dict[str, Any] = {
        "manifest_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_title": "Spatial AI 双引擎作品集 · AetherVault & TectonicLoop",
        "public_url": "https://frostales-code.github.io/spatial-ai-portfolio/",
        "modes": ["instant_showcase", "live_engine"],
        "data_sources": [
            "/data/aethervault_showcase_v1.json",
            "/data/ast_comparisons_v1.json",
            "/data/tectonic_showcase_v1.json",
            "/data/edd_benchmark_v1.json",
        ],
        "aethervault_summary": {
            "total_assets": aether.get("total_assets", 0),
            "domain_counts": aether.get("domain_counts", {}),
            "axes_count": len(aether.get("axes", [])),
            "golden_anchors_count": len(aether.get("golden_anchors", [])),
            "ast_comparison_pairs": ast_cmp.get("total_pairs", 0),
            "pydantic_validation_passed": vlm_report.get("pydantic_validation_passed", 0),
            "mean_spearman_rho": vlm_report.get("mean_spearman_rho", 0),
            "observed_online_cny_per_img": cost_metrics.get("observed_online_cny_per_img", 0),
            "cache_hit_rate": vlm_report.get("cache_hit_rate", 0),
        },
        "tectonicloop_summary": {
            "total_assemblies": tectonic.get("total_assemblies", 0),
            "benchmark_date": tectonic.get("benchmark_date", ""),
            "category_counts": tectonic.get("category_counts", {}),
            "case_count": len(case_list),
            "tier_count": tier_render_count,
            "cad_svg_count": 8,
            "lint_rules_count": 8,
        },
        "static_assets_audit": {
            "total_webp_files": len(webp_files),
            "total_json_files": len(json_files),
            "public_payload_mb": round(total_bytes / (1024 * 1024), 2),
            "all_referenced_assets_present": True,
        },
    }

    OUTPUT_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    manifest = build_showcase_manifest()
    audit = manifest["static_assets_audit"]
    print(
        f"Built {OUTPUT_MANIFEST} | {audit['total_webp_files']} WebPs, "
        f"{audit['total_json_files']} data JSONs, {audit['public_payload_mb']} MB"
    )


if __name__ == "__main__":
    main()
