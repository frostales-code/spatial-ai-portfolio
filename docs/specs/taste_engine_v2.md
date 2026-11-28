# SPEC · AetherVault Taste & Anti-Homogenization Engine v2 (Option B · Codex-Hardened)

- **Status**: Spec-Locked (Ready for Implementation)
- **Decision Basis**: Antigravity Proposal B + Independent Codex CLI (`gpt-6.2-astra`) Review + Empirical 1,500-Asset Probe
- **Core Constraint**: Preserve public 80-asset showcase (`aethervault_showcase_v1.json`) untouched; local `<20ms` p95 Zero-LLM reranking; full-funnel API cost `<= ¥0.008 / final-admitted asset` (counting rejected candidates, anchor inputs, and retries).

---

## 1. Goal & User Outcome
Replace the current "keyword-only retrieval + single-centroid + blind 1–10 VLM scoring" pipeline (where 85.7% of candidates pile into scores 8–9 and filter-bubble homogenization is unmanaged) with a **3-lane Personal Taste & High-Craft Anti-Homogenization Engine** grounded in PinnerSage multi-interest Medoids, Midjourney-style dual-question pairwise calibration, an exploration-protected inverted funnel, and per-domain craft-anchor judging.

---

## 2. Data & State Shape (Measured on Disk)
1. **Multi-Interest Medoids (`data/pinterest_500/taste_profile_v2.json`)**:
   - Ward hierarchical clustering on `390` personal origins (`pin_*`, 256d L2-normalized) -> **`K = 10` real Medoids** (`C01..C10`, measured cluster sizes `17–81`, covering Brand Swatches, Wayfinding, Ink Illustration, Paper/Craft, Minimalist Living, Organic Office, Retail Display, Minimalist Landscape, High-Tech Facade, Brutalist Concrete).
   - Feature vector for any candidate $x$: `medoid_sims(x) ∈ R^10` (cosine to each of the 10 Medoids) + `max_medoid_sim(x)` + `top_medoid_id`.
2. **Dual-Signal Calibration Log (`data/pinterest_500/taste_calibration_pairs.jsonl`)**:
   - Strictly separates two independent user intents (both allow `skip`):
     - `signal = "core_taste"` (*"哪张更符合你平常的口味？"*): trains the **10-parameter L2-regularized Bradley-Terry Core Taste Head** ($w \in \mathbb{R}^{10}$, zero overfitting vs 256d) and benchmarks against zero-param `max_medoid_sim`.
     - `signal = "serendipity_save"` (*"哪张虽然陌生/跳脱，但你仍愿意收藏？"*): stored **separately** to validate & tune the Adversarial/Exploration lane; **NEVER** fed back into Core Taste weights.
3. **Per-Domain Craft Floor Anchors (`data/pinterest_500/craft_anchors_v2.json`)**:
   - 8 visual domains × 2 user-confirmed reference anchors (1 familiar high-craft + 1 unfamiliar/contrast high-craft) defining the exact visual quality floor per domain.
4. **Asset Slot Metadata (additive fields on private `aethervault_personal_500.json`)**:
   - `curation_lane`: `"personal_origin" | "core_resonance" | "cross_domain_bridge" | "adversarial_exploration"`
   - `craft_verdict`: `{"meets_floor": bool, "margin": "above" | "at" | "below", "anchor_id": str, "pixel_evidence_zh": str}`
   - `taste_scores`: `{"core_bt_score": float, "max_medoid_sim": float, "nearest_medoid_id": str, "inverted_axis": str | None}`

---

## 3. Core System & User Flow (5 Stages)
1. **Stage 1 · Baseline & Medoid Extraction (`pipeline/taste_medoids_v2.py`)**:
   - Compute `K=10` Ward Medoids from 390 personal pins; audit & build local **Option A baseline** over existing ~1,800 local candidate pool first so Option B's visual-recall gain is measured against a real baseline.
2. **Stage 2 · Local Pairwise Calibration Bench (`/api/atlas/calibration/*` + UI Modal)**:
   - Active-learning sampler serves **30–50 pairs** (initial trial budget, skippable) split into Q1 (`core_taste`) and Q2 (`serendipity_save`), plus 1-click confirmation of the 8-domain Craft Floor anchors.
   - Fits `w ∈ R^10` regularized Bradley-Terry head (`<1ms` numpy inference); stores full session log without using the unverified 133 `rejected_or_deferred` pins as taste negatives.
3. **Stage 3 · Protected Dual-Track Retrieval**:
   - **Core Track**: Visual-similar ("More like this") snowballing from high-weight personal Medoid pins -> pre-filtered by `core_bt_score`.
   - **Bridge Track**: Cross-domain candidates sharing a verifiable structural/lighting/material trait with a personal Medoid across a different `visual_domain`.
   - **Exploration / Adversarial Track (BYPASS LANE)**: Completely **bypasses** the Core Taste pre-filter threshold! Retrieves from high-craft contrast seeds using **Single-Axis Controlled Inversion** on empirically independent axes (probe measured `|r| < 0.35` for `lighting_drama` & `geometric_order`, plus `chromatic_tension` within photorealistic domains `reality_abstraction < 0`; never blindly flipping coupled axes or hardcoding `pop/anime = contrast`).
4. **Stage 4 · Shared Reference-Anchored Craft Floor Judge (`pipeline/craft_anchor_judge_v2.py`)**:
   - Replaces blind 1–10 scoring. Feeds `[Domain Craft Floor Anchor Image, Candidate Image]` to `gemini-4-hydrogen` (`temperature=0.1`): returns `{meets_floor, margin, pixel_evidence_zh}` grounded in 1 concrete pixel observation.
   - All 3 tracks must clear the **exact same** Craft Floor gate.
5. **Stage 5 · 3-Tier Portfolio Slotting + Intra-Lane MMR + Blind Eval**:
   - Only Craft-passing candidates enter slotting: **Core ~60% / Cross-Domain Bridge ~25% / Adversarial Exploration up to 15%** (strict rule: **if qualified Exploration candidates < 15%, show fewer rather than padding with sub-floor filler**).
   - Run intra-lane **MMR** (`lambda=0.7`) to prevent clustering within each lane.
   - Run **Blind Holdout Evaluation** (near-duplicate clusters held out together, source/lane labels hidden) comparing Option A baseline vs Option B before scaling retrieval volume.

---

## 4. Non-Goals (Explicitly Out)
- **NO** local PyTorch / CLIP / LoRA / Task-Vector training (Option C rejected).
- **NO** treating the historical 133 `rejected_or_deferred` pins in `pinterest_523_research.json` as negative taste labels (probe confirmed mixed automated/deferred status, not explicit user dislikes).
- **NO** changes to the public 80-asset showcase (`web/public/data/aethervault_showcase_v1.json`) or Git tracking of private assets.
- **NO** multi-axis simultaneous inversion in v1 (start strictly with single-axis inversion and verify empirically).

---

## 5. Pre-Mortem Safeguards (Top 4 Failure Modes Neutralized)
1. **Exploration killed by global taste filter** -> Structural bypass: Exploration track skips Core Taste pre-filter and only merges at the Craft Floor Judge.
2. **256d overfitting on 30–50 pairs** -> Low-dim projection (`w ∈ R^10` Medoid similarities + L2 regularization) benchmarked against zero-param `max_medoid_sim`.
3. **Serendipity poisoning Core Taste** -> Strict dual-table signal isolation (`core_taste` vs `serendipity_save`).
4. **Hidden cost blowup from anchor tokens & rejections** -> Full-funnel Cost Ledger tracks every VLM/Embedding call (including rejected candidates, anchor image tokens, and retries) normalized per *final admitted* asset (`<= ¥0.008/img` target, with automatic batch cap).

---

## 6. Falsifiable Done Predicates (`Prove It Works`)
1. **Latency**: Local Zero-LLM Medoid + Bradley-Terry + MMR rerank over 1,500+ items measures `p95 < 20ms` (`py -3.12 -m eval.bench_taste_engine_v2`).
2. **Blind Eval Gate (A vs B)**: On held-out deduped clusters with hidden source/lane labels, report sample size $N$ & confidence intervals for:
   - Core pairwise win rate (BT head vs `max_medoid_sim` vs single-centroid);
   - Exploration "unfamiliar yet worth saving" rate;
   - Manual craft-pass rate delta (`Exploration - Core`) within preset tolerance (`>= -5%`).
3. **Cost & Efficiency Ledger**: Report qualified saves per 100 recalled candidates at equal retrieval budget + full-funnel RMB cost per admitted asset (`<= ¥0.008` or explicit variance attribution).
4. **Engineering Gates**: `py -3.12 -m unittest discover -s tests -v`, `npx.cmd tsc --noEmit`, `npm.cmd run build`, secret scan `= 0`, public showcase `= 80`, and live browser verification of the Calibration Bench + 3-lane Atlas with 0 console/network errors.
