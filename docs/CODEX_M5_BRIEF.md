# Milestone M5 Task Brief for Codex CLI (`MIC-167` & `MIC-168`)

You are taking over Milestone **M5** of `D:\Projects\spatial-ai-portfolio` (`Spatial AI 双引擎作品集 · AetherVault & TectonicLoop`).
Milestones M0–M4 (`MIC-154`~`MIC-166`) are already complete, tested, and deployed live to:
- **Live Showcase**: `https://frostales-code.github.io/spatial-ai-portfolio/`
- **GitHub Repo**: `https://github.com/frostales-code/spatial-ai-portfolio`

## Verified Project Facts & Numbers (cite ONLY these verified values)
- **AetherVault [0→1]**:
  - 80 curated cross-domain specimens (16 × 5 domains: `architecture`, `industrial`, `editorial`, `craft`, `graphic`), 8 orthogonal axes × 5-point Golden Anchors (`40` calibrated anchor criteria).
  - First-pass VLM (`gpt-4o-mini`) Spearman `ρ = 0.6107` (`+13.1%` vs blind baseline `0.540`), post-calibration anchored catalog `ρ = 0.8577`; 20 cross-domain queries Top-5 alignment `100.0%`; client-side vector rerank `p50 = 0.107 ms` (`< 20 ms`).
  - VLM cold-start observed online cost `¥0.00596/图` (Batch equivalent `¥0.00298/图`, Prompt Cache hit rate `49.25%`, Pydantic schema pass `80/80`).
  - Scope-isolated Prompt AST compiler: 20 cross-domain 3-slot mixing tasks `100.0%` composite decoupling & `0` foreign entity leaks (vs naive IP-Adapter baseline `45.0%`), with 6 controlled Before/After visual comparison pairs (`web/public/assets/ast_comparisons/cmp_01..06_*.webp`).
- **TectonicLoop [1→N]**:
  - 30 real commercial construction SKUs, 8 physical constructability lint rules (`BLOCKING`/`WARNING`), 8 CAD SVG detail diagrams, 3 real commercial renovation cases × 3 budget tiers (`9` `800×600` WebP plates in `web/public/assets/tectonic_cases/`).
  - `H/H⁻¹` planar homography seam projection: max vertical vanishing deviation `0.000°` (`< 1.5°`), roundtrip RMSE `0.0 px`, non-mask relight PSNR `>= 38 dB` (observed `99.0 dB`).
  - Zero-LLM `Decimal` costing engine: 15 historical commercial storefront settlement backtest hit rate **`86.7%` (`13/15`)** within `±15%` interval (vs manual `2–3 days`); unpriced SKU `bespoke_bronze_patina_unpriced` strictly returns `UNKNOWN_PRICE_MISSING` (never fabricates `0`).
- **Frontend Stack**: Next.js 15 App Router (static export) + shadcn/ui (Radix + Light/Dark themes) + Dual Three.js 3D scenes (AetherVault 80-specimen 3D Aesthetic Manifold & TectonicLoop 3D Homography Plane) + Recharts EDD Evaluation & Bad Case Workbench + FastAPI Live Engine (`127.0.0.1:8780`).
- **Three Documented Bad Cases**:
  1. `BC-01-EXTREME-TILT-FORESHORTENING` (stretch ratio `>= 1.48x` / tilt `>= 32°` triggers manual 4-point fallback)
  2. `BC-02-ABSTRACT-SALIENCE-NOISE` (salience gating suppresses graphic-domain noise on `tectonic_honesty`)
  3. `BC-03-UNPRICED-BESPOKE-SKU` (`UNKNOWN_PRICE_MISSING` zero-hallucination cost block)

## Strict Constraints
- Windows + PowerShell environment; Python 3.12 already has `PIL` (Pillow), `cv2`, `numpy`, `imageio`, and `imageio_ffmpeg` (`imageio_ffmpeg.get_ffmpeg_exe()`).
- NEVER write any API keys, tokens, or fabricated personal PII into any file.
- Do NOT break any existing M1–M4 Python tests or Next.js build.

---

## Deliverable 1 (`MIC-167`): 90s High-Density Showreel MP4 + GitHub Hero GIF
1. Create `scripts/render_showreel_and_gif.py` that programmatically synthesizes high-craft, crisp-typography motion graphics directly from our real workspace WebP assets (`web/public/assets/curated_80/*.webp`, `web/public/assets/ast_comparisons/*.webp`, `web/public/assets/tectonic_cases/*.webp`) and real JSON data (`web/public/data/*.json`). Use Windows CJK fonts (`C:\Windows\Fonts\msyhbd.ttc` / `msyh.ttc` / `simhei.ttf` with graceful fallback) for razor-sharp, readable large Chinese + English subtitles (silent-playback friendly!).
2. Render `docs/media/showreel_90s.mp4`:
   - Exact duration: **88–92 seconds** (target `90.0s`), **1920×1080**, `24` or `30 fps`, H.264 `yuv420p`, kept under `12 MB` via clean CRF encoding (`crf=24` or `25`, `pix_fmt=yuv420p`, `movflags=+faststart`) using `imageio_ffmpeg.get_ffmpeg_exe()`.
   - Strictly follow the 4-beat storyboard:
     - `0–12s`: Pain-point hook — multi-image prompt leakage & commercial facade budget blowout (`¥18.6w → ¥7.0w`), visually immediate within first 5 seconds.
     - `12–45s`: **AetherVault `[0→1]`** — 80-specimen cross-domain montage, animated 8-axis spectrum readout, animated Before/After curtain wipes on `cmp_01`, `cmp_02`, `cmp_03` (`Naive Multi-Image` vs `Scoped AST`), key telemetry (`<20ms` rerank, `¥0.00596/图`, `100%` zero entity leak).
     - `45–80s`: **TectonicLoop `[1→N]`** — animated Before/After commercial facade wipes across `Case 01` (`Tier 0 → Tier 1 → Tier 2`), `Case 02`, `Case 03` with animated `H/H⁻¹` perspective seam overlays drawn from real `tectonic_showcase_v1.json` coordinates, `30 SKU × 8 Lint Rules`, `86.7%` 15-settlement backtest, and `UNKNOWN_PRICE_MISSING` callout.
     - `80–90s`: Product philosophy finale (`AI vs Non-AI Discipline`) + live public URL (`frostales-code.github.io/spatial-ai-portfolio`) + GitHub repo card.
3. Render `docs/media/hero_showcase.gif`:
   - Clean looping animated GIF (`960×540`, ~`10–12s` loop, optimized palette, target `<= 3.8 MB` for crisp fast GitHub README playback) showcasing AetherVault AST curtain wipe → TectonicLoop facade budget-cut & `H/H⁻¹` seam wipe!
4. Run the script and verify output file existence, exact video duration (`85–95s`), resolution (`1920×1080`), and file sizes.

---

## Deliverable 2 (`MIC-168`): Bilingual GitHub Open-Source Front Door + Build-in-Public Articles
1. Upgrade root `README.md` into a high-impact **Chinese + English bilingual open-source showcase**:
   - Crisp shields/badges (Live Instant Showcase, Next.js 15, Three.js, FastAPI, Python EDD Suite).
   - Embedded hero GIF: `![Spatial AI Dual-Engine Showcase](docs/media/hero_showcase.gif)` + link to `docs/media/showreel_90s.mp4` and Live URL `https://frostales-code.github.io/spatial-ai-portfolio/`.
   - Clean Mermaid architecture flowchart (`flowchart LR`) showing Dual-Mode (`Instant Showcase` + `Live Engine`) & AI vs Non-AI boundary.
   - Complete M1–M4 verified EDD Benchmark & Bad Case summary table linking to `eval/reports/EDD_BENCHMARK_REPORT.md` and `docs/THREE_MINUTE_DEMO_SCRIPT.md`.
   - Clear Local Quick Start & Verification commands + English Executive Summary section at the bottom (or cleanly paired bilingual headers).
2. Create two ready-to-publish community launch drafts under `docs/publish/`:
   - `docs/publish/XIAOHONGSHU_POST.md`: 《当甲方把 18 万清水混凝土门头预算砍到 7 万，我用自研 AI 10 秒重画了干挂板拼缝和节点表》 — complete with cover visual hook, 6-slide carousel copy plan referencing our real Case 01–03 & AST comparison images, punchy main post body, comment-section engagement hooks, and hashtags.
   - `docs/publish/ZHIHU_ARCHITECTURE_ARTICLE.md`: 《拒绝套壳聊天框：如何用“领域本体 + 单应性几何 + 零幻觉算账”设计空间 AI 双引擎》 — deep AI PM & systems architecture long-form article covering pain points, AI vs Non-AI boundaries, 8-axis golden anchors, Scoped Prompt AST, `H/H⁻¹` 80/20 homography vs heavy BIM, Zero-LLM `Decimal` + `UNKNOWN_PRICE_MISSING`, real M4 EDD results & 3 Bad Cases, and Live Showcase CTA.
3. Also create `docs/publish/BUILD_IN_PUBLIC_TRACKER.md` — a lightweight template for recording actual post views/likes/GitHub stars and 3+ real peer/designer feedback quotes to feed back into future resume iterations (with honest `[待发布后回填]` fields — never fabricate engagement stats!).

---

## Verification Before Finishing
1. Run `python -m unittest tests/test_m2_tectonic_pipeline.py tests/test_m4_edd_and_live_engine.py -v` and `PYTHONPATH=. python tests/test_m1_curation_and_anchors.py` + `PYTHONPATH=. python tests/test_m1_scorer_and_comparisons.py` to confirm zero regressions.
2. Run a quick secret scan over newly created/edited files confirming 0 leaked keys.
3. Print a concise summary of created/updated files, exact MP4 duration/resolution/size, GIF dimensions/size, and test exit codes. Do NOT run `git push` (caller will inspect outputs, commit, push, and update Linear).
