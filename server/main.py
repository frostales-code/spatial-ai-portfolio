"""FastAPI Live Engine server for Spatial AI Portfolio (127.0.0.1:8780)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pipeline import (
    GOLDEN_ANCHOR_RUBRICS,
    SPECTRUM_AXES,
    AestheticAsset,
    OpeningRectMm,
    Point2D,
    VisualTectonicZone,
    calculate_zone_cost,
    compile_conflict_free_ast,
    estimate_ingestion_cost_cny,
    lint_constructability,
    project_panel_seams,
    summarize_project_ve,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_DIR = REPO_ROOT / "data" / "curated_80"
CURATED_ASSETS_JSON = CURATED_DIR / "aethervault_assets_v1.json"
VLM_REPORT_JSON = CURATED_DIR / "vlm_scoring_report.json"
AST_COMPARE_JSON = REPO_ROOT / "data" / "ast_comparisons" / "ast_comparisons_v1.json"
TECTONIC_CATALOG_JSON = REPO_ROOT / "pipeline" / "tectonic_catalog_v1.json"
TECTONIC_CASES_DIR = REPO_ROOT / "data" / "tectonic_cases"
TECTONIC_SHOWCASE_JSON = TECTONIC_CASES_DIR / "tectonic_showcase_v1.json"

app = FastAPI(
    title="Spatial AI Dual-Engine Live Server",
    version="0.1.0",
    description="Deterministic pipelines + Live Engine endpoints for AetherVault & TectonicLoop.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompileAstRequest(BaseModel):
    subject_core: str
    optics_asset: AestheticAsset
    material_asset: AestheticAsset
    lighting_asset: AestheticAsset
    target_spectrums: dict[str, float] = Field(default_factory=dict)


class ProjectSeamsRequest(BaseModel):
    image_quad: list[Point2D]
    facade_width_mm: float = 7200.0
    facade_height_mm: float = 3600.0
    panel_width_mm: float = 1200.0
    panel_height_mm: float = 2400.0
    openings_mm: list[OpeningRectMm] = Field(default_factory=list)


@app.get("/api/health")
def health_check() -> dict[str, object]:
    """Readiness probe reporting loaded spectrum ontology count and server status."""
    return {
        "status": "ok",
        "mode": "live_engine",
        "spectrum_axes_count": len(SPECTRUM_AXES),
        "golden_anchors_count": sum(len(r.anchors) for r in GOLDEN_ANCHOR_RUBRICS.values()),
        "curated_bundle_ready": CURATED_ASSETS_JSON.exists(),
    }


@app.get("/api/aethervault/anchors")
def api_get_anchors() -> dict[str, object]:
    """Return 8-axis x 5-point golden calibration rubrics and cold-start cost ledger."""
    return {
        "axes": [ax.model_dump() for ax in SPECTRUM_AXES],
        "golden_anchors": {k: v.model_dump() for k, v in GOLDEN_ANCHOR_RUBRICS.items()},
        "cost_ledger": estimate_ingestion_cost_cny(1000).model_dump(),
    }


@app.get("/api/aethervault/assets")
def api_get_assets(domain: str | None = Query(default=None)) -> dict[str, object]:
    """Return curated 80 cross-domain aesthetic assets, optionally filtered by domain."""
    if not CURATED_ASSETS_JSON.exists():
        raise HTTPException(status_code=404, detail="Curated 80 asset bundle has not been generated yet.")
    payload = json.loads(CURATED_ASSETS_JSON.read_text(encoding="utf-8"))
    assets = payload.get("assets", [])
    if domain:
        assets = [a for a in assets if a.get("subject_isolation", {}).get("domain") == domain]
    return {
        "version": payload.get("version", "1.0.0"),
        "total": len(assets),
        "domain_counts": payload.get("domain_counts", {}),
        "assets": assets,
    }


@app.get("/api/aethervault/images/{asset_id}")
def api_get_asset_image(asset_id: str) -> FileResponse:
    """Serve curated WebP thumbnail image for a given asset_id."""
    safe_id = Path(asset_id).name
    img_path = CURATED_DIR / "images" / f"{safe_id}.webp"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image for asset_id={safe_id} not found.")
    return FileResponse(img_path, media_type="image/webp")


@app.get("/api/aethervault/scoring-report")
def api_get_scoring_report() -> dict[str, object]:
    """Return observed MIC-157 5-point anchored VLM batch scoring telemetry."""
    if not VLM_REPORT_JSON.exists():
        raise HTTPException(status_code=404, detail="VLM scoring report not generated yet.")
    return json.loads(VLM_REPORT_JSON.read_text(encoding="utf-8"))


@app.get("/api/aethervault/comparisons")
def api_get_ast_comparisons() -> dict[str, object]:
    """Return 6 cross-domain Naive multi-image vs Orthogonal AST comparison pairs."""
    if not AST_COMPARE_JSON.exists():
        raise HTTPException(status_code=404, detail="AST comparisons bundle not generated yet.")
    return json.loads(AST_COMPARE_JSON.read_text(encoding="utf-8"))


@app.post("/api/aethervault/compile-ast")
def api_compile_ast(req: CompileAstRequest) -> dict[str, object]:
    """Compile three orthogonal slot assets into a Conflict-Free Prompt AST."""
    return compile_conflict_free_ast(
        subject_core=req.subject_core,
        optics_asset=req.optics_asset,
        material_asset=req.material_asset,
        lighting_asset=req.lighting_asset,
        target_spectrums=req.target_spectrums,
    )


@app.get("/api/tectonic/catalog")
def api_get_tectonic_catalog() -> dict[str, object]:
    """Return 30-SKU facade/interior assemblies, 8 constructability rules, and CAD detail SVGs."""
    if not TECTONIC_CATALOG_JSON.exists():
        raise HTTPException(status_code=404, detail="Tectonic catalog has not been built yet.")
    return json.loads(TECTONIC_CATALOG_JSON.read_text(encoding="utf-8"))


@app.get("/api/tectonic/cases")
def api_get_tectonic_cases() -> dict[str, object]:
    """Return full M2 TectonicLoop cases bundle with homography seams and relit renders."""
    target = TECTONIC_SHOWCASE_JSON if TECTONIC_SHOWCASE_JSON.exists() else TECTONIC_CATALOG_JSON
    if not target.exists():
        raise HTTPException(status_code=404, detail="Tectonic showcase bundle not generated yet.")
    return json.loads(target.read_text(encoding="utf-8"))


@app.get("/api/tectonic/images/{filename}")
def api_get_tectonic_image(filename: str) -> FileResponse:
    """Serve rendered WebP facade comparison plate safely."""
    safe_name = Path(filename).name
    img_path = TECTONIC_CASES_DIR / "images" / safe_name
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Tectonic case image '{safe_name}' not found.")
    return FileResponse(img_path, media_type="image/webp")


@app.post("/api/tectonic/calc-ve")
def api_calc_ve(zones: list[VisualTectonicZone]) -> dict[str, object]:
    """Run deterministic Constructability Linter and Zero-LLM Decimal VE cost calculation."""
    alerts = [alert for z in zones for alert in lint_constructability(z)]
    breakdowns = [calculate_zone_cost(z) for z in zones]
    summary = summarize_project_ve(zones)
    return {
        "zones_count": len(zones),
        "blocking_alerts_count": sum(1 for a in alerts if a.severity == "BLOCKING"),
        "warning_alerts_count": sum(1 for a in alerts if a.severity == "WARNING"),
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "cost_breakdowns": [b.model_dump(mode="json") for b in breakdowns],
        "summary": summary.model_dump(mode="json"),
    }


@app.post("/api/tectonic/project-seams")
def api_project_seams(req: ProjectSeamsRequest) -> dict[str, object]:
    """Project orthographic millimeter panel seams back into perspective image coordinates."""
    result = project_panel_seams(
        image_quad=req.image_quad,
        facade_width_mm=req.facade_width_mm,
        facade_height_mm=req.facade_height_mm,
        panel_width_mm=req.panel_width_mm,
        panel_height_mm=req.panel_height_mm,
        openings_mm=req.openings_mm,
    )
    return result.model_dump()
