"""AetherVault domain ontology, Salience-Gated Metric, and Conflict-Free Prompt AST compiler."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field


class SpectrumAxisSpec(BaseModel):
    """Metadata specification for one bipolar orthogonal style axis."""

    axis_id: str
    label_zh: str
    neg_label: str
    pos_label: str
    cross_domain_definition: str


SPECTRUM_AXES: tuple[SpectrumAxisSpec, ...] = (
    SpectrumAxisSpec(
        axis_id="tectonic_honesty",
        label_zh="构造表现度",
        neg_label="消隐包覆 (Monolithic)",
        pos_label="结构外露 (Tectonic)",
        cross_domain_definition="Joint articulation vs. seamless monolithic skin",
    ),
    SpectrumAxisSpec(
        axis_id="surface_entropy",
        label_zh="肌理时间熵",
        neg_label="精密出厂 (Pristine)",
        pos_label="风化包浆 (Weathered)",
        cross_domain_definition="Machined tolerance vs. weathered patina & erosion",
    ),
    SpectrumAxisSpec(
        axis_id="spatial_density",
        label_zh="信息与留白",
        neg_label="克制负空间 (Austere)",
        pos_label="高密层叠 (Layered)",
        cross_domain_definition="Expansive negative space vs. high-density layering",
    ),
    SpectrumAxisSpec(
        axis_id="geometric_order",
        label_zh="几何形态秩序",
        neg_label="有机流体 (Biomorphic)",
        pos_label="严苛模数 (Orthogonal)",
        cross_domain_definition="Freeform biomorphic curves vs. orthogonal modular grid",
    ),
    SpectrumAxisSpec(
        axis_id="lighting_drama",
        label_zh="光影反差度",
        neg_label="全局漫射 (Diffused)",
        pos_label="戏剧切割 (Chiaroscuro)",
        cross_domain_definition="Overcast softbox diffusion vs. high-contrast chiaroscuro",
    ),
    SpectrumAxisSpec(
        axis_id="chromatic_tension",
        label_zh="色彩能量张力",
        neg_label="消色差灰调 (Muted)",
        pos_label="高纯度对冲 (High-Chroma)",
        cross_domain_definition="Low-saturation tonal minimalism vs. vivid complementary tension",
    ),
    SpectrumAxisSpec(
        axis_id="thermal_mood",
        label_zh="情绪色温亲疏",
        neg_label="冷峻智性 (Clinical Cool)",
        pos_label="温润松弛 (Intimate Warm)",
        cross_domain_definition="Clinical cool detachment vs. tactile warm intimacy",
    ),
    SpectrumAxisSpec(
        axis_id="reality_abstraction",
        label_zh="写实与抽象度",
        neg_label="光学纪实 (Photorealistic)",
        pos_label="图形构成 (Graphic Stylized)",
        cross_domain_definition="Physical optical realism vs. flattened graphic abstraction",
    ),
)

AXIS_IDS: tuple[str, ...] = tuple(ax.axis_id for ax in SPECTRUM_AXES)


class SubjectIsolation(BaseModel):
    """Layer 1: Explicit domain and subject tags to enable cross-domain filtering."""

    domain: Literal["architecture", "industrial", "editorial", "craft", "graphic"]
    domain_label: str
    primary_subject: str
    is_personal_prior: bool = False


class StyleSpectrumAxis(BaseModel):
    """Continuous bipolar score [-1, +1] paired with visual salience [0, 1]."""

    score: float = Field(..., ge=-1.0, le=1.0)
    salience: float = Field(1.0, ge=0.0, le=1.0)


class GranularDescriptors(BaseModel):
    """Layer 3: Orthogonal physical slots isolated at the schema level."""

    optics_camera: str
    lighting_rig: str
    material_stack: str
    color_palette: list[str] = Field(default_factory=list, max_length=6)


class CompilerPrimitives(BaseModel):
    """Layer 4: Pre-curated positive style tokens and conflict guardrails."""

    positive_tokens: list[str] = Field(default_factory=list)
    negative_guardrails: list[str] = Field(default_factory=list)


class AestheticAsset(BaseModel):
    """Four-layer orthogonal schema for every reference asset in AetherVault."""

    asset_id: str
    title: str
    subject_isolation: SubjectIsolation
    style_spectrums: dict[str, StyleSpectrumAxis]
    granular_descriptors: GranularDescriptors
    compiler_primitives: CompilerPrimitives = Field(default_factory=CompilerPrimitives)


def salience_gated_distance(
    query_scores: dict[str, float],
    candidate_spectrums: dict[str, StyleSpectrumAxis],
    attention_weights: dict[str, float] | None = None,
    eps: float = 1e-6,
) -> float:
    """Compute D(q, x) = sum(w_i * s_{x,i} * (q_i - x_i)^2) / (sum(w_i * s_{x,i}) + eps)."""
    weights = attention_weights or {}
    numerator = 0.0
    denominator = 0.0
    for axis_id in AXIS_IDS:
        axis_val = candidate_spectrums.get(axis_id)
        if axis_val is None:
            continue
        w_i = max(0.0, float(weights.get(axis_id, 1.0)))
        s_i = axis_val.salience
        q_i = float(query_scores.get(axis_id, 0.0))
        diff = q_i - axis_val.score
        numerator += w_i * s_i * (diff * diff)
        denominator += w_i * s_i
    return numerator / (denominator + eps)


def similarity_score_from_distance(distance: float) -> int:
    """Convert squared salience-gated distance into an intuitive [0, 99] match percentage."""
    rmse = math.sqrt(max(0.0, distance))
    return max(0, min(99, round((1.0 - rmse / 1.45) * 100)))


_POLARITY_CONFLICTS: tuple[tuple[str, str], ...] = (
    ("seamless monolithic", "exposed fasteners"),
    ("pristine anodized", "heavily eroded"),
    ("diffused overcast", "harsh midday shadows"),
    ("muted morandi", "high-saturation neon"),
)


def compile_conflict_free_ast(
    subject_core: str,
    optics_asset: AestheticAsset,
    material_asset: AestheticAsset,
    lighting_asset: AestheticAsset,
    target_spectrums: dict[str, float] | None = None,
) -> dict[str, object]:
    """Assemble isolated slot tokens into a Conflict-Free Prompt AST and negative guardrails."""
    target = target_spectrums or {}
    entropy = float(target.get("surface_entropy", material_asset.style_spectrums["surface_entropy"].score))
    chroma = float(target.get("chromatic_tension", lighting_asset.style_spectrums["chromatic_tension"].score))
    lighting = float(target.get("lighting_drama", lighting_asset.style_spectrums["lighting_drama"].score))

    if entropy > 0.5:
        entropy_modifier = "pronounced natural weathering patina confined to primary cladding panels"
    elif entropy < -0.3:
        entropy_modifier = "ultra-clean factory-machined surface tolerance"
    else:
        entropy_modifier = "controlled subtle weathering with crisp precision mechanical joints"

    # Scope material descriptors strictly to component/region layer to stop bleed into optics or atmosphere.
    raw_material = material_asset.granular_descriptors.material_stack
    scoped_material = f"localized to primary structural assemblies and joinery: {raw_material}, {entropy_modifier}"

    negatives: list[str] = ["plastic CGI gloss", "floating structural members"]
    if entropy < 0.55:
        negatives.extend(["post-apocalyptic trash", "crumbling ruins", "chaotic rust stains"])
    if chroma < -0.3:
        negatives.extend(["oversaturated neon", "HDR color clipping"])
    if lighting < -0.2:
        negatives.extend(["harsh midday cast shadows", "blown-out highlights"])

    # Detect and neutralize semantic polarity conflicts between cross-referenced assets.
    combined_lower = f"{optics_asset.granular_descriptors.optics_camera} | {scoped_material} | {lighting_asset.granular_descriptors.lighting_rig}".lower()
    conflicts_isolated: list[str] = []
    for lhs, rhs in _POLARITY_CONFLICTS:
        if lhs in combined_lower and rhs in combined_lower:
            conflicts_isolated.append(f"{lhs} <-> {rhs}")

    # Count distinct asset sources separated across slots + detected lexical conflicts.
    distinct_sources = len({optics_asset.asset_id, material_asset.asset_id, lighting_asset.asset_id})
    ast_blocks = {
        "SUBJECT_CORE": subject_core.strip(),
        "OPTICS_LAYER": f"[{optics_asset.asset_id}] {optics_asset.granular_descriptors.optics_camera}",
        "MATERIAL_TECTONICS": f"[{material_asset.asset_id}] {scoped_material}",
        "ATMOSPHERE_LIGHTING": f"[{lighting_asset.asset_id}] {lighting_asset.granular_descriptors.lighting_rig}",
    }
    compiled_prompt = "\n\n".join(f"[{key}]\n{val}" for key, val in ast_blocks.items())

    # Deduplicate negative guardrails while preserving order.
    dedup_negatives = list(dict.fromkeys([*negatives, *material_asset.compiler_primitives.negative_guardrails]))

    return {
        "ast_blocks": ast_blocks,
        "compiled_prompt": compiled_prompt,
        "negative_guardrails": dedup_negatives,
        "distinct_source_slots": distinct_sources,
        "conflicts_isolated_count": len(conflicts_isolated) + max(0, distinct_sources - 1),
        "conflicts_isolated": conflicts_isolated,
    }
