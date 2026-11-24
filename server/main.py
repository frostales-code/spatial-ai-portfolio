"""FastAPI Live Engine server for Spatial AI Portfolio (127.0.0.1:8780)."""

from __future__ import annotations

import json
import math
import os
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
PINTEREST_500_ASSETS_JSON = REPO_ROOT / "data" / "pinterest_500" / "aethervault_assets_500.json"
WEB_PINTEREST_500_DIR = REPO_ROOT / "web" / "public" / "assets" / "pinterest_500"
VLM_REPORT_JSON = CURATED_DIR / "vlm_scoring_report.json"
AST_COMPARE_JSON = REPO_ROOT / "data" / "ast_comparisons" / "ast_comparisons_v1.json"
TECTONIC_CATALOG_JSON = REPO_ROOT / "pipeline" / "tectonic_catalog_v1.json"
TECTONIC_CASES_DIR = REPO_ROOT / "data" / "tectonic_cases"
TECTONIC_SHOWCASE_JSON = TECTONIC_CASES_DIR / "tectonic_showcase_v1.json"
EDD_BENCHMARK_JSON = REPO_ROOT / "eval" / "reports" / "edd_benchmark_v1.json"

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


class ParseIntentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=240)
    use_llm: bool = False


_INTENT_LEXICON: list[tuple[tuple[str, ...], dict[str, float]]] = [
    (("构造", "外露", "裸露", "螺栓", "钢架", "铆钉", "tectonic", "exposed", "steel"), {"tectonic_honesty": 0.85, "geometric_order": 0.45}),
    (("消隐", "极简", "整体", "平滑", "monolithic", "minimal", "seamless"), {"tectonic_honesty": -0.75, "spatial_density": -0.7}),
    (("包浆", "风化", "侘寂", "粗粝", "做旧", "耐候", "rust", "weathered", "patina", "wabi"), {"surface_entropy": 0.82, "thermal_mood": 0.35}),
    (("精密", "出厂", "CNC", "阳极", "金属", "工业", "machined", "anodized", "precision"), {"surface_entropy": -0.82, "geometric_order": 0.8, "tectonic_honesty": 0.6}),
    (("留白", "静谧", "空旷", "克制", "禅", "austere", "calm", "quiet", "zen"), {"spatial_density": -0.85, "chromatic_tension": -0.65}),
    (("高密", "层叠", "繁复", "rich", "layered", "dense"), {"spatial_density": 0.8}),
    (("模数", "网格", "正交", "瑞士", "秩序", "grid", "modular", "orthogonal", "swiss"), {"geometric_order": 0.9}),
    (("有机", "曲线", "流动", "雕塑", "organic", "fluid", "curved"), {"geometric_order": -0.85}),
    (("戏剧", "明暗", "切割", "剪影", "dramatic", "chiaroscuro", "contrast"), {"lighting_drama": 0.88}),
    (("漫射", "阴天", "柔光", "极地", "soft", "overcast", "diffused"), {"lighting_drama": -0.78, "thermal_mood": -0.55}),
    (("暖", "木", "暮色", "茶", "陶", "温润", "warm", "timber", "sunset", "ceramic"), {"thermal_mood": 0.82}),
    (("冷", "冰", "灰", "混凝土", "工业冷", "cool", "cold", "concrete", "nordic"), {"thermal_mood": -0.78, "chromatic_tension": -0.5}),
    (("构成主义", "高饱和", "撞色", "包豪斯", "bold", "bauhaus", "vivid", "color"), {"chromatic_tension": 0.85, "reality_abstraction": 0.55}),
    (("抽象", "平面", "构成", "abstract", "graphic", "poster"), {"reality_abstraction": 0.85}),
]


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
    """Return active AetherVault aesthetic assets (prefers local 500 Pinterest-expanded bundle)."""
    active_json = PINTEREST_500_ASSETS_JSON if PINTEREST_500_ASSETS_JSON.exists() else CURATED_ASSETS_JSON
    if not active_json.exists():
        raise HTTPException(status_code=404, detail="AetherVault asset bundle has not been generated yet.")
    payload = json.loads(active_json.read_text(encoding="utf-8"))
    assets = payload.get("assets", [])
    if domain:
        assets = [a for a in assets if a.get("subject_isolation", {}).get("domain") == domain]
    return {
        "version": payload.get("version", "1.0.0"),
        "total": len(assets),
        "domain_counts": payload.get("domain_counts", {}),
        "origin_counts": payload.get("origin_counts", {}),
        "assets": assets,
    }


@app.get("/api/aethervault/images/{asset_id}")
def api_get_asset_image(asset_id: str) -> FileResponse:
    """Serve curated WebP thumbnail image for a given asset_id."""
    safe_id = Path(asset_id).name
    p500_path = WEB_PINTEREST_500_DIR / f"{safe_id}.webp"
    if p500_path.exists():
        return FileResponse(p500_path, media_type="image/webp")
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


@app.post("/api/aethervault/parse-intent")
def api_parse_intent(req: ParseIntentRequest) -> dict[str, object]:
    """Parse arbitrary bilingual fuzzy aesthetic intent into 8-axis target spectrums."""
    text = req.query.strip()
    low = text.lower()
    accum: dict[str, list[float]] = {}
    matched_tokens: list[str] = []

    for keywords, deltas in _INTENT_LEXICON:
        hits = [kw for kw in keywords if kw.lower() in low]
        if hits:
            matched_tokens.append(hits[0])
            for axis_id, val in deltas.items():
                accum.setdefault(axis_id, []).append(val)

    target_scores = {
        axis_id: round(max(-1.0, min(1.0, sum(vals) / len(vals))), 2)
        for axis_id, vals in accum.items()
    }
    attention_weights = {axis_id: 1.6 for axis_id in target_scores}

    has_api_key = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    mode_used = "deterministic_ontology"
    note = (
        "已通过确定性双语审美本体实时解析目标光谱向量（零 Token 损耗）。"
        if matched_tokens
        else "未命中预设高频审美词条，已保留当前基准坐标并可继续细调 8 轴滑块。"
    )
    if req.use_llm and not has_api_key:
        note = "本机未配置外部 LLM API Key，已优雅降级至确定性审美本体解析（零崩溃、零密钥风险）。"

    return {
        "query": text,
        "mode": mode_used,
        "llm_key_configured": has_api_key,
        "matched_tokens": matched_tokens,
        "target_scores": target_scores,
        "attention_weights": attention_weights,
        "note": note,
    }


@app.get("/api/eval/benchmark")
def api_get_edd_benchmark() -> dict[str, object]:
    """Return M4 reproducible EDD benchmark JSON report."""
    if not EDD_BENCHMARK_JSON.exists():
        raise HTTPException(status_code=404, detail="M4 EDD benchmark report not generated yet.")
    return json.loads(EDD_BENCHMARK_JSON.read_text(encoding="utf-8"))


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
    q = req.image_quad
    top_edge = math.hypot(q[1].x - q[0].x, q[1].y - q[0].y)
    bottom_edge = math.hypot(q[2].x - q[3].x, q[2].y - q[3].y)
    stretch_ratio = round(max(bottom_edge, top_edge) / max(1.0, min(bottom_edge, top_edge)), 3)
    payload = result.model_dump()
    payload["edge_stretch_ratio"] = stretch_ratio
    payload["extreme_tilt_warning"] = stretch_ratio >= 1.48
    return payload
