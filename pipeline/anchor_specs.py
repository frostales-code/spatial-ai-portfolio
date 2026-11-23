"""8-Axis x 5-Point Golden Anchor Calibration Specs, VLM Few-Shot Prompts, and Cold-Start Cost Ledger.

Implements the anti-drift calibration layer for AetherVault (`MIC-156`), eliminating VLM
batch scoring drift via pairwise interval bracketing against 40 visually anchored benchmarks
and modeling the <= CNY 0.008/image tiered edge-cloud ingestion budget.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .aethervault_schema import AXIS_IDS, SPECTRUM_AXES

ANCHOR_LEVELS: tuple[float, ...] = (-1.0, -0.5, 0.0, 0.5, 1.0)


class AnchorBenchmarkPoint(BaseModel):
    """Single calibration tick on a bipolar style spectrum axis."""

    level: float = Field(..., ge=-1.0, le=1.0)
    anchor_title_zh: str
    anchor_title_en: str
    physical_visual_criteria: str
    cross_domain_examples: str
    reference_asset_id: str


class AxisCalibrationRubric(BaseModel):
    """Complete 5-point physical rubric and salience gating rule for one spectrum axis."""

    axis_id: str
    label_zh: str
    neg_label: str
    pos_label: str
    salience_gating_rule: str
    anchors: list[AnchorBenchmarkPoint] = Field(..., min_length=5, max_length=5)


GOLDEN_ANCHOR_RUBRICS: dict[str, AxisCalibrationRubric] = {
    "tectonic_honesty": AxisCalibrationRubric(
        axis_id="tectonic_honesty",
        label_zh="构造表现度",
        neg_label="消隐包覆 (Monolithic)",
        pos_label="结构外露 (Tectonic)",
        salience_gating_rule=(
            "Set salience <= 0.25 for pure 2D flat graphics or tight macro surface textures lacking "
            "identifiable structural seams, joints, or load-bearing assemblies; set salience >= 0.80 "
            "when cladding joints, fasteners, framing members, or monolithic skin continuity are prominent."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="极简无缝一体包覆",
                anchor_title_en="Seamless Monolithic Envelope",
                physical_visual_criteria="Zero visible seams, fasteners, or structural hierarchy; continuous sculptural plaster, molded shell, or seamless unibody housing.",
                cross_domain_examples="Seamless curved stucco pavilion; molded unibody matte resin shell; seamless draped cloak.",
                reference_asset_id="arch_06",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="微缝隐框收口",
                anchor_title_en="Flush Shadow-Gap Skin",
                physical_visual_criteria="Predominantly smooth continuous surfaces interrupted only by hairline shadow-gap recesses (<3mm) or concealed clips.",
                cross_domain_examples="Unibody acoustic speaker; flush curtain wall with hidden mullions; slip-cast porcelain vessel.",
                reference_asset_id="ind_04",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="构架与围护半显半隐",
                anchor_title_en="Balanced Frame & Infill",
                physical_visual_criteria="Primary load-bearing posts or structural ribs remain readable while secondary infill panels sit cleanly within the frame.",
                cross_domain_examples="Timber post-and-infill plaster wall; framed leather-and-metal camera body; mortised tea cabinet.",
                reference_asset_id="arch_04",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="明缝干挂与可见节点",
                anchor_title_en="Articulated Dry-Joint Assembly",
                physical_visual_criteria="Deliberate 10–20mm panel reveal joints, expressed sub-frames, bolted base plates, or visibly layered garment seams.",
                cross_domain_examples="Dry-hung Corten steel cladding; modular field rack with bolted rails; taped seam technical shell jacket.",
                reference_asset_id="arch_01",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="完全结构外露与机械咬合",
                anchor_title_en="Hyper-Tectonic Exposed Joinery",
                physical_visual_criteria="Every structural rod, pin clevis, tension wire, hex fastener, and load path is foregrounded as the primary visual rhythm.",
                cross_domain_examples="CNC anodized modular synthesizer; tension-cable truss canopy; raw skeleton watch movement.",
                reference_asset_id="ind_02",
            ),
        ],
    ),
    "surface_entropy": AxisCalibrationRubric(
        axis_id="surface_entropy",
        label_zh="肌理时间熵",
        neg_label="精密出厂 (Pristine)",
        pos_label="风化包浆 (Weathered)",
        salience_gating_rule=(
            "Set salience >= 0.85 whenever surface finish (mirror polish, bead-blasting, concrete pores, "
            "patina, kiln ash glaze) occupies >30% of visual attention; lower to <= 0.25 only for pure vector flat art."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="镜面级精密零瑕疵",
                anchor_title_en="Optical Mirror Pristine",
                physical_visual_criteria="Sub-micron surface uniformity, sharp specular reflections, zero micro-scratches, pores, or organic irregularity.",
                cross_domain_examples="Precision optical lens barrel; electroplated aerospace titanium; gloss ceramic glaze.",
                reference_asset_id="ind_01",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="微喷砂哑光工业精加工",
                anchor_title_en="Machined Satin Tolerance",
                physical_visual_criteria="Uniform bead-blasted, brushed, or matte anodized texture with crisp chamfered edges and intentional industrial regularity.",
                cross_domain_examples="CNC brushed aluminum workstation; matte polycarbonate housing; calendared cotton poplin.",
                reference_asset_id="ind_06",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="自然原生材质微肌理",
                anchor_title_en="Honed Natural Materiality",
                physical_visual_criteria="Natural grain, fine stone honing, or linen weave visible at close range without heavy erosion, rust, or distress.",
                cross_domain_examples="Honed limestone & oiled walnut; natural woven wool editorial suit; unvarnished hinoki joinery.",
                reference_asset_id="craft_04",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="可控粗粝与轻度岁月感",
                anchor_title_en="Controlled Aggregate & Patina",
                physical_visual_criteria="Board-formed concrete air voids, brushed wire-grain timber, oxidized bronze patina, or natural mineral mottling.",
                cross_domain_examples="Board-formed architectural concrete; weathered Corten fascia; raw volcanic basalt coastal terrain.",
                reference_asset_id="arch_02",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="重度风化窑变与手工时间熵",
                anchor_title_en="Heavy Erosion & Kiln Ash Entropy",
                physical_visual_criteria="Deep pitting, crackle glaze, rough hand-gouged chisel marks, heavy rust oxidation, or thick geological stratification.",
                cross_domain_examples="Wood-fired Shigaraki ash-crackle stoneware; heavily weathered rammed-earth ruin; raw cast-iron kettle.",
                reference_asset_id="craft_01",
            ),
        ],
    ),
    "spatial_density": AxisCalibrationRubric(
        axis_id="spatial_density",
        label_zh="信息与留白",
        neg_label="克制负空间 (Austere)",
        pos_label="高密层叠 (Layered)",
        salience_gating_rule=(
            "Salience is globally observable (typically 0.70–0.95) across all 5 domains by measuring "
            "occupied figure area vs. unbroken negative space and foreground/midground/background plane count."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="极高留白与单一视觉孤岛",
                anchor_title_en="Austere >75% Negative Space",
                physical_visual_criteria="More than 75% unbroken void (sky, blank wall, dark backdrop); single isolated focal silhouette with minimal texture.",
                cross_domain_examples="Solitary figure on Icelandic black sand; single tea bowl on empty plinth; minimal Swiss poster.",
                reference_asset_id="edit_01",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="克制疏朗与清晰呼吸感",
                anchor_title_en="Measured Minimal Framing",
                physical_visual_criteria="50–75% calm breathing room around 2–3 cleanly separated planes or geometric elements; zero visual clutter.",
                cross_domain_examples="Quiet concrete courtyard; minimal industrial desk object; wide-margin editorial portrait.",
                reference_asset_id="arch_08",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="主次均衡的日常构成密度",
                anchor_title_en="Balanced Multi-Element Composition",
                physical_visual_criteria="Balanced foreground subject and contextual ground (35–50% open space); 3–4 readable sub-components without crowding.",
                cross_domain_examples="Curated tea alcove arrangement; balanced café storefront elevation; modular typography grid.",
                reference_asset_id="craft_06",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="丰富结构与多层次信息排布",
                anchor_title_en="Dense Structured Layering",
                physical_visual_criteria="Under 30% open void; dense repetition of dials, louvers, bookshelves, or multi-column typographic annotations.",
                cross_domain_examples="Calibrated studio rack console; louvered double-skin facade; layered editorial spread.",
                reference_asset_id="ind_08",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="高信息熵交叠构成",
                anchor_title_en="Hyper-Dense Overlapping Collage",
                physical_visual_criteria="Edge-to-edge overlapping geometric fragments, multi-plane depth stack, intricate filigree, or dense typographic collage.",
                cross_domain_examples="Overlapping Constructivist print collage; hyper-layered cyberpunk bazaar; dense schematic poster.",
                reference_asset_id="graph_08",
            ),
        ],
    ),
    "geometric_order": AxisCalibrationRubric(
        axis_id="geometric_order",
        label_zh="几何形态秩序",
        neg_label="有机流体 (Biomorphic)",
        pos_label="严苛模数 (Orthogonal)",
        salience_gating_rule=(
            "Keep salience >= 0.75 whenever silhouettes, structural grids, or graphic layouts clearly reveal "
            "either organic curvature or rectilinear modular control."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="纯粹有机仿生流线",
                anchor_title_en="Pure Biomorphic Fluidity",
                physical_visual_criteria="Continuous double-curved shells, organic amorphous silhouettes, zero right angles or straight ruler lines.",
                cross_domain_examples="Parametric fluid concrete shell; sculptural melted glass vase; flowing draped silk silhouette.",
                reference_asset_id="arch_10",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="手作微弧与自然非对称",
                anchor_title_en="Soft Organic Asymmetry",
                physical_visual_criteria="Hand-thrown irregular curves or relaxed natural drapery tempered by a gentle horizon or plinth line.",
                cross_domain_examples="Hand-turned stoneware vessel; soft sculpted armchair; botanical shadow study.",
                reference_asset_id="craft_02",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="曲直对位平衡",
                anchor_title_en="Curvilinear vs. Rectilinear Balance",
                physical_visual_criteria="Deliberate tension between soft organic forms (human posture, woven drape, cylindrical cup) and architectural straight lines.",
                cross_domain_examples="Draped coat inside concrete colonnade; circular watch face on chamfered lug case; radial ceramic lid.",
                reference_asset_id="edit_06",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="清晰结构轴网与切分",
                anchor_title_en="Clear Structural Grid & Chamfer",
                physical_visual_criteria="Dominant rectilinear massing, consistent column rhythm or beveled industrial chamfers with restrained radii.",
                cross_domain_examples="Modular timber pergola courtyard; precision camera top-plate; stepped wooden joinery box.",
                reference_asset_id="arch_03",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="严苛正交黄金模数网格",
                anchor_title_en="Strict Orthogonal Modularity",
                physical_visual_criteria="100% ruler-straight 90-degree / 45-degree Constructivist axes, modular subdivisions, and disciplined mathematical proportion.",
                cross_domain_examples="12-column Swiss typographic poster; Miesian steel curtain wall bay; grid-aligned modular desk matrix.",
                reference_asset_id="graph_01",
            ),
        ],
    ),
    "lighting_drama": AxisCalibrationRubric(
        axis_id="lighting_drama",
        label_zh="光影反差度",
        neg_label="全局漫射 (Diffused)",
        pos_label="戏剧切割 (Chiaroscuro)",
        salience_gating_rule=(
            "Set salience <= 0.20 for purely flat 2D graphic vector art that has no simulated illumination, "
            "cast shadows, or tonal shading gradients."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="极柔无影天光漫射",
                anchor_title_en="Shadowless Overcast Diffusion",
                physical_visual_criteria="Omnidirectional softbox or overcast fog light; zero crisp shadow edges; compressed smooth midtone roll-off.",
                cross_domain_examples="Subarctic overcast fashion shoot; large softbox industrial catalog; foggy courtyard elevation.",
                reference_asset_id="edit_02",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="北向柔窗微渐变",
                anchor_title_en="Gentle North-Window Gradient",
                physical_visual_criteria="Soft directional falloff across surfaces with feathered shadow penumbras and readable shadow detail.",
                cross_domain_examples="North-light ceramic still life; diffused shoji screen interior; subtle studio product sweep.",
                reference_asset_id="craft_08",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="自然平衡明暗比",
                anchor_title_en="Balanced Architectural Daylight",
                physical_visual_criteria="Clear directional key light paired with generous sky/bounce fill (~3:1 contrast ratio); crisp yet gentle shadows.",
                cross_domain_examples="Afternoon museum courtyard; daylight street storefront; balanced editorial studio setup.",
                reference_asset_id="arch_05",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="定向轮廓光与局部高光",
                anchor_title_en="Directional Rim & Specular Cut",
                physical_visual_criteria="Strong raking light or tight snooted key carving material relief and bright metallic rim highlights against dim ground.",
                cross_domain_examples="Rim-lit matte black rangefinder camera; raking sunset light on textured plaster; moody editorial profile.",
                reference_asset_id="ind_03",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="高反差戏剧性光刀切割",
                anchor_title_en="High-Contrast Chiaroscuro Beam",
                physical_visual_criteria="Extreme >= 8:1 contrast ratio; razor-sharp sunlight slits, deep crushed shadows, or volumetric Tyndall shafts.",
                cross_domain_examples="Sharp skylight blade across dark concrete hall; dramatic chiaroscuro studio portrait; spotlighted lacquer ware.",
                reference_asset_id="arch_07",
            ),
        ],
    ),
    "chromatic_tension": AxisCalibrationRubric(
        axis_id="chromatic_tension",
        label_zh="色彩能量张力",
        neg_label="消色差灰调 (Muted)",
        pos_label="高纯度对冲 (High-Chroma)",
        salience_gating_rule=(
            "Salience is globally high (0.80–1.0) across every visual medium because OKLab chroma and "
            "hue-angle separation are directly measurable on all pixels."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="纯黑白灰消色差阶调",
                anchor_title_en="Achromatic Silver-Gelatin Monochrome",
                physical_visual_criteria="Zero hue chroma (OKLab C* < 0.015); relies solely on luminance contrast from carbon black to paper white.",
                cross_domain_examples="Black-and-white basalt editorial; raw charcoal concrete study; pure monochrome Swiss typography.",
                reference_asset_id="edit_03",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="莫兰迪低饱和微差",
                anchor_title_en="Low-Chroma Tonal Subtlety",
                physical_visual_criteria="Muted mineral greys, sage, taupe, or pale slate with narrow hue spread and gentle saturation restraint.",
                cross_domain_examples="Muted concrete & sage courtyard; matte titanium gray hardware; soft ash linen editorial.",
                reference_asset_id="arch_09",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="自然材料原生色阶",
                anchor_title_en="Earth & Material Analogous Harmony",
                physical_visual_criteria="Moderate authentic pigment saturation derived from natural terracotta, walnut, brass, or indigo linen without neon pops.",
                cross_domain_examples="Smoked oak & terracotta craft table; warm bronze facade detail; editorial camel wool lookbook.",
                reference_asset_id="craft_05",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="中性基底 + 单点高纯信号色",
                anchor_title_en="Controlled Neutral + Signal Accent",
                physical_visual_criteria="75%+ disciplined dark charcoal or off-white ground punctuated by a razor-sharp high-chroma focal accent (signal orange/cobalt).",
                cross_domain_examples="Graphite audio device with amber encoder; obsidian space with cinnabar wall; Swiss grid + vermilion bar.",
                reference_asset_id="ind_05",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="高饱和互补色强碰撞",
                anchor_title_en="Vivid Complementary Collision",
                physical_visual_criteria="Bold high-chroma fields (ultramarine, vermilion, acid lime, cadmium yellow) colliding across large area ratios.",
                cross_domain_examples="Bauhaus Constructivist triadic poster; vivid cobalt & tangerine architectural installation.",
                reference_asset_id="graph_02",
            ),
        ],
    ),
    "thermal_mood": AxisCalibrationRubric(
        axis_id="thermal_mood",
        label_zh="情绪色温亲疏",
        neg_label="冷峻智性 (Clinical Cool)",
        pos_label="温润松弛 (Intimate Warm)",
        salience_gating_rule=(
            "Keep salience >= 0.70 across color photography, interiors, hardware, and prints; drop to "
            "<= 0.40 only for pure neutral greyscale where thermal cues are intentionally stripped."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="实验室冷峻智性疏离",
                anchor_title_en="Clinical Laboratory Detachment",
                physical_visual_criteria=">= 5800K cool blue-cyan cast, surgical steel/glass materiality, razor-sharp sterile precision and emotional distance.",
                cross_domain_examples="Cleanroom optical bench; icy blue concrete & steel atrium; clinical cyan-silver technical poster.",
                reference_asset_id="ind_07",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="冷灰克制理性感",
                anchor_title_en="Cool Architectural Restraint",
                physical_visual_criteria="Cool slate grey, zinc, and overcast daylight tone conveying composed analytical calm without harsh clinical glare.",
                cross_domain_examples="Nordic slate gallery lobby; matte aluminum camera rig; rainy dusk street lookbook.",
                reference_asset_id="arch_11",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="中性平衡温度",
                anchor_title_en="Neutral Balanced Daylight",
                physical_visual_criteria="Balanced 5000K white point mixing cool mineral stone or metal with subtle warm paper, brass, or skin warmth.",
                cross_domain_examples="Neutral warm-grey print composition; balanced steel-and-oak desk; crisp studio daylight look.",
                reference_asset_id="graph_04",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="手作触觉温润感",
                anchor_title_en="Tactile Timber & Daylight Warmth",
                physical_visual_criteria="Warm timber grain, unbleached linen, honeyed paper, and golden-hour bounce invoking approachable human craft.",
                cross_domain_examples="Hinoki cypress tea vessels; warm sunlit oak bench; tactile cream-paper editorial layout.",
                reference_asset_id="craft_03",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="暖金包裹居心地氛围",
                anchor_title_en="Intimate 2700K Hearth Warmth",
                physical_visual_criteria="Deep amber 2700K–3200K glow, glowing lanterns, terracotta plaster, and cozy tactile embrace.",
                cross_domain_examples="Dusk amber terracotta tea alcove; candlelit bronze tea kettle; golden-hour wool textile study.",
                reference_asset_id="arch_12",
            ),
        ],
    ),
    "reality_abstraction": AxisCalibrationRubric(
        axis_id="reality_abstraction",
        label_zh="写实与抽象度",
        neg_label="光学纪实 (Photorealistic)",
        pos_label="图形构成 (Graphic Stylized)",
        salience_gating_rule=(
            "Salience >= 0.85 across all assets; separates physical lens-captured micro-realism from "
            "stylized illustration, orthographic diagrams, and flat geometric abstraction."
        ),
        anchors=[
            AnchorBenchmarkPoint(
                level=-1.0,
                anchor_title_zh="物理光学全纪实摄影",
                anchor_title_en="Pure Optical Film Realism",
                physical_visual_criteria="Authentic lens bokeh, optical grain, physically accurate surface micro-imperfections, and real-world atmospheric depth.",
                cross_domain_examples="Medium-format editorial portrait; real architectural field documentary; unretouched studio macro shot.",
                reference_asset_id="edit_04",
            ),
            AnchorBenchmarkPoint(
                level=-0.5,
                anchor_title_zh="克制调色纪实摄影",
                anchor_title_en="Art-Directed Architectural Realism",
                physical_visual_criteria="Photographic reality with disciplined perspective correction, unified tonal grading, and minimized environmental clutter.",
                cross_domain_examples="Curated architectural daylight photo; clean editorial product hero shot; minimalist ceramic macro.",
                reference_asset_id="arch_13",
            ),
            AnchorBenchmarkPoint(
                level=0.0,
                anchor_title_zh="图纸级纯正交实景抽离",
                anchor_title_en="Orthographic Technical Study",
                physical_visual_criteria="Zero-distortion elevation/isometric framing, hyper-clean studio backdrop, or fine architectural model photography bridging photo and diagram.",
                cross_domain_examples="Isometric industrial prototype render; monochrome architectural scale model; cyanotype photogram.",
                reference_asset_id="ind_09",
            ),
            AnchorBenchmarkPoint(
                level=0.5,
                anchor_title_zh="版画肌理与半调构成转译",
                anchor_title_en="Risograph & Screenprint Abstraction",
                physical_visual_criteria="Recognizable spatial/object motifs distilled into limited ink plates, halftone dots, woodcut grain, or architectural axonometric flats.",
                cross_domain_examples="Risograph architectural elevation print; layered paper-cut collage; Japanese woodblock abstraction.",
                reference_asset_id="graph_05",
            ),
            AnchorBenchmarkPoint(
                level=1.0,
                anchor_title_zh="纯平涂几何符号构成",
                anchor_title_en="Pure Flat Geometric Constructivism",
                physical_visual_criteria="Zero photographic depth or 3D shading; crisp solid vector planes, typographic blocks, and non-representational rhythm.",
                cross_domain_examples="Pure Constructivist red-black-cream vector composition; minimal Swiss typographic poster.",
                reference_asset_id="graph_03",
            ),
        ],
    ),
}


def build_vlm_calibration_system_prompt() -> str:
    """Build the 5-Point Pairwise Few-Shot VLM Calibration System Prompt (`MIC-156`)."""
    lines = [
        "You are the AetherVault Orthogonal Aesthetic Decoupling Scorer.",
        "CRITICAL RULE: Never guess arbitrary absolute floats in isolation. For EACH of the 8 bipolar axes, "
        "perform pairwise bracketing against the 5 Golden Anchor benchmarks (-1.0, -0.5, 0.0, +0.5, +1.0) below, "
        "then interpolate to 0.05 precision and assign an explicit salience weight [0.0, 1.0].",
        "",
        "### 8-AXIS x 5-POINT GOLDEN CALIBRATION RUBRIC ###",
    ]
    for axis_id in AXIS_IDS:
        rubric = GOLDEN_ANCHOR_RUBRICS[axis_id]
        lines.append(f"\n[{axis_id}] {rubric.label_zh}: {rubric.neg_label} <-> {rubric.pos_label}")
        lines.append(f"  Salience Rule: {rubric.salience_gating_rule}")
        for pt in rubric.anchors:
            lines.append(
                f"  * {pt.level:+.1f} ({pt.anchor_title_en} | ref={pt.reference_asset_id}): "
                f"{pt.physical_visual_criteria}"
            )

    lines.extend(
        [
            "",
            "### STRICT OUTPUT CONTRACT (4-LAYER ORTHOGONAL JSON) ###",
            "Return valid JSON matching AestheticAsset schema:",
            "1. subject_isolation: {domain in [architecture, industrial, editorial, craft, graphic], domain_label, primary_subject}",
            "2. style_spectrums: all 8 axis keys mapping to {score in [-1.0, 1.0], salience in [0.0, 1.0]}",
            "3. granular_descriptors: strictly isolated physical strings:",
            "   - optics_camera: focal length, perspective geometry, DoF ONLY (no material/color adjectives)",
            "   - material_stack: physical materials, surface treatments, joints ONLY (no lighting/weather words)",
            "   - lighting_rig: light direction, diffusion, color temperature, haze ONLY (no object nouns)",
            "   - color_palette: preserve the pre-extracted deterministic OKLab HEX list provided by edge stage",
            "4. compiler_primitives: {positive_tokens: [...], negative_guardrails: [...]}",
        ]
    )
    return "\n".join(lines)


def build_vlm_scoring_user_prompt(asset_id: str, preextracted_hex_palette: list[str]) -> str:
    """Build per-image user prompt injecting deterministic edge OKLab HEX palette."""
    palette_str = ", ".join(preextracted_hex_palette) if preextracted_hex_palette else "[] (extract top 5)"
    return (
        f"Asset ID: {asset_id}\n"
        f"Deterministic Edge OKLab HEX Palette (preserve verbatim in color_palette): [{palette_str}]\n"
        "Compare this image against the 5-point anchors for all 8 axes, apply salience gating where cues are absent, "
        "and emit the strictly decoupled 4-layer AestheticAsset JSON."
    )


class ColdStartCostLedger(BaseModel):
    """Edge-cloud tiered ingestion cost model ensuring <= CNY 0.008 per asset."""

    batch_size: int
    duplicate_skip_rate: float
    effective_vlm_calls: int
    edge_deterministic_cost_cny_per_img: float
    vlm_model_tier: str
    cached_system_prompt_tokens: int
    image_tokens_per_asset: int
    uncached_user_tokens_per_asset: int
    output_tokens_per_asset: int
    usd_to_cny_rate: float
    batch_discount_factor: float
    total_batch_cost_cny: float
    effective_cost_cny_per_img: float
    target_ceiling_cny_per_img: float = 0.008
    within_budget: bool


def estimate_ingestion_cost_cny(
    num_images: int = 1000,
    duplicate_skip_rate: float = 0.12,
    vlm_model_tier: str = "gemini-2.5-flash-lite-batch-cached",
    usd_to_cny_rate: float = 7.25,
) -> ColdStartCostLedger:
    """Compute exact cold-start edge-cloud cost ledger for Eagle / local folder ingestion.

    Architecture split:
    - Tier 0 (Local Edge, CNY 0.0000/img): Pillow WebP thumbnails (512/1024), pHash/dHash
      exact & near-duplicate short-circuiting (skips ~12% duplicate pins before VLM),
      deterministic OKLab k=5 HEX palette, and local RTX SigLIP-2 FP16 vector indexing (<3s search).
    - Tier 1 (Async Cloud Batch VLM with Context Caching): Gemini Flash-Lite Batch API
      (50% Batch discount + 75% Context Caching discount on the 1,850-token 5-point rubric).
      Reference Gemini 2.5 Flash-Lite pricing (per 1M tokens):
      Input $0.10 (Batch $0.05; Cached Batch $0.0125), Output $0.40 (Batch $0.20).
    """
    effective_calls = max(1, round(num_images * (1.0 - duplicate_skip_rate)))
    cached_sys_tokens = 1850
    image_tokens = 258
    user_tokens = 90
    output_tokens = 320

    # Per-call USD pricing under Batch API (50% off standard) + Context Caching on system rubric
    cached_input_usd_per_m = 0.0125
    uncached_input_usd_per_m = 0.05
    output_usd_per_m = 0.20

    per_call_usd = (
        (cached_sys_tokens / 1_000_000.0) * cached_input_usd_per_m
        + ((image_tokens + user_tokens) / 1_000_000.0) * uncached_input_usd_per_m
        + (output_tokens / 1_000_000.0) * output_usd_per_m
    )
    # Include amortized overhead (+15% for JSON repair retries on ~5% malformed outputs)
    per_call_cny_with_retries = per_call_usd * usd_to_cny_rate * 1.15
    total_cny = round(per_call_cny_with_retries * effective_calls, 4)
    effective_per_img_cny = round(total_cny / max(1, num_images), 6)

    return ColdStartCostLedger(
        batch_size=num_images,
        duplicate_skip_rate=duplicate_skip_rate,
        effective_vlm_calls=effective_calls,
        edge_deterministic_cost_cny_per_img=0.0,
        vlm_model_tier=vlm_model_tier,
        cached_system_prompt_tokens=cached_sys_tokens,
        image_tokens_per_asset=image_tokens,
        uncached_user_tokens_per_asset=user_tokens,
        output_tokens_per_asset=output_tokens,
        usd_to_cny_rate=usd_to_cny_rate,
        batch_discount_factor=0.5,
        total_batch_cost_cny=total_cny,
        effective_cost_cny_per_img=effective_per_img_cny,
        target_ceiling_cny_per_img=0.008,
        within_budget=effective_per_img_cny <= 0.008,
    )
