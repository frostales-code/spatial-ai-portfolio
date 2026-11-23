# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Primary: Senior AI Product Manager Hiring Directors, Design Directors, and Engineering Leads evaluating visual taste, AI-vs-deterministic system boundaries, and quantitative verification within a 45–90 second desktop or mobile review.
- Secondary: Spatial/architectural designers and creative technologists exploring 8-axis aesthetic spectrum retrieval and orthogonal 3-slot AST prompt compilation.

## Product Purpose

Spatial AI Dual-Engine Monograph & Compiler showcasing two complementary systems:
1. `AetherVault` (`0 -> 1` Aesthetic Prior & Orthogonal Style Compiler): decouples visual aesthetic grammar from photographic subjects across 8 continuous bipolar axes (`[-1.0, +1.0]`), calibrates fuzzy intent in 2 visual binary clicks, recalls cross-domain references in sub-millisecond client-side latency, and compiles conflict-free 3-slot AST prompts (`Optics` / `Material` / `Lighting`).
2. `TectonicLoop` (`1 -> N` Constructability Linter & Value-Engineering Loop): bridges conceptual design intent and physical execution through architectural orthographic geometry projection (`H/H^-1`) and deterministic `Decimal` cost/constructability verification.

## Positioning

Replaces black-box trial-and-error text prompting and unconstrained generative renders with salience-gated `<20ms` 8-axis vector ranking, 5-point visual anchor rubrics, scoped 3-slot AST isolation, and deterministic architectural constructability and BOM pricing rules (`UNKNOWN_PRICE_MISSING` on unpriced items, never silently coerced to zero).

## Operating Context

Isomorphic dual-mode web showcase (`web/` React + TypeScript + Tailwind frontend):
- Default public mode (`Instant Showcase`): loads pre-baked static bundles (`aethervault_showcase_v1.json`, `ast_comparisons_v1.json`) and curated `800x600` WebP assets with zero cold-start latency.
- Optional local mode (`Live Engine`): connects automatically when the local FastAPI backend (`127.0.0.1:8780`) responds on `/api/health`, enabling live backend `/api/aethervault/compile-ast` verification.

## Capabilities and Constraints

- Curated 80 balanced 4:3 WebP specimens (`16` per domain across `architecture`, `industrial`, `editorial`, `craft`, `graphic`) with real OKLab 5-color palettes and read-only prior links.
- 8 continuous bipolar axes × 5 golden visual calibration anchors (`40` rubric points) + salience gating (`s_i`).
- 6 paired multi-image naive vs scoped-AST before/after generated comparisons (`CMP_01`–`CMP_06`).
- Deterministic client-side keyword-to-spectrum intent parser + salience-gated distance re-ranker + scope/domain filters + state persistence across navigation tabs.
- Zero internal sprint ticket IDs (`MIC-*`, `P-MIC-*`, `M1`/`M2`), zero candidate interview cheat-sheets, zero exposed secrets/tokens, and strict Zero-LLM `Decimal` math rules on cost ledgers.

## Brand Commitments

- User-locked visual world: **Concept A (`Architectural Monograph & Specimen Index · 白纸信号蓝`)**.
- Colors: `#FFFFFF` crisp open gallery canvas, `#F4F5F7` secondary tonal ground, `#E2E5EA` 1px Swiss hairlines, `#0E1015` obsidian ink, `#525866` slate secondary text, `#153CE8` Signal Cobalt single primary accent, `#0F766E` verified teal, `#C62828` alert crimson.
- Aesthetic refusal: explicitly forbids dark charcoal SaaS dashboards, warm-cream/terracotta templates, muted sage greens, rounded nested cards, `.bg-tech-grid` global backgrounds, colored `border-left` side-tabs, eyebrow kickers, image overlays/watermarks, `Inter`/`Space Grotesk`/`Playfair`/`IBM Plex` display defaults, `<12px` micro-text, and raw emojis (`⚡`, `🧪`).

## Evidence on Hand

- `web/public/data/aethervault_showcase_v1.json`: 80 curated assets, 8 axis metadata specs, 40 golden anchor rubrics, cold-start cost ledger (`¥0.0008/img` modeled at 1,000-img Batch scale), and empirical `gpt-4o-mini` VLM scoring report (`80/80` Pydantic schema pass, `49.25%` prompt cache hit, `¥0.00596/img` online / `¥0.00298/img` batch equivalent, `mean_spearman_rho = 0.6107`).
- `web/public/data/ast_comparisons_v1.json`: 6 paired generated comparisons (`cmp_01`–`cmp_06`) in `web/public/assets/ast_comparisons/`.
- `web/public/data/tectonic_showcase_v1.json`: 30 commercial facade & interior assembly SKUs (`12 wall_cladding`, `8 glazing_portal`, `5 edge_weatherproofing`, `5 interior_threshold`), 8 physical constructability lint rules, 8 light-archival CAD cross-section SVGs, and 3 complete renovation case studies × 3 VE tiers (`9` `800×600` WebP renders in `web/public/assets/tectonic_cases/`) generated via `pipeline/relight_inpaint.py` with doorway-locked LAB shadow transfer (`vertical_vanishing_deviation_deg = 0.000° < 1.5°`, strict outside-mask pixel preservation `>= 38 dB`, and live `UNKNOWN_PRICE_MISSING` propagation).

## Product Principles

1. Proof before explanation: lead with interactive visual Before/After AST evidence and real curated specimens rather than explanatory pitch walls.
2. Image sovereignty: photography renders cleanly at 4:3 with zero corner badges or watermarks on an uncast neutral paper canvas.
3. Disciplined AI vs deterministic boundary: LLM/VLM handles ontology routing and semantic compilation; math, ranking, projection, and BOM arithmetic remain deterministic.
4. Progressive disclosure: keep default surfaces calm (`<=4` options per visible decision cluster), placing 8-axis deep tuning and full AST prompt inspection in structured drawers.
5. Radical honesty: surface exact empirical telemetry (`ρ = 0.611`, observed API costs, explicit `UNKNOWN_PRICE_MISSING` rule) without inflated claims.

## Accessibility & Inclusion

- WCAG 2.1 AA minimum contrast (`>= 4.5:1` normal text & button labels, `>= 3:1` display/large text).
- Visible `:focus-visible` focus rings on all interactive elements including range sliders, swatches, and orthographic elevation pins.
- Semantic ARIA support (`role="tablist"`/`tab`, `role="dialog"` + `aria-modal` + backdrop & `Escape` dismiss, associated `<label>` for inputs/selects), minimum `12px` text, `prefers-reduced-motion` support, and `390×844` mobile responsiveness with zero horizontal overflow.
