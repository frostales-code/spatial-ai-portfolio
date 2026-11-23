---
name: "AetherVault & TectonicLoop — Spatial AI Monograph"
description: "Swiss architectural monograph and precision specimen instrument for orthogonal aesthetic compiling and constructability verification."
colors:
  primary: "#153CE8"
  primary-deep: "#0E2BB5"
  primary-tint: "#EEF2FF"
  paper: "#FFFFFF"
  cool-surface: "#F4F5F7"
  drafting-plate: "#FAFBFD"
  obsidian-ink: "#0E1015"
  slate-muted: "#525866"
  hairline: "#E2E5EA"
  hairline-strong: "#CBD0D8"
  teal-verified: "#0F766E"
  crimson-alert: "#C62828"
typography:
  display:
    fontFamily: "Archivo, Noto Sans SC, system-ui, sans-serif"
    fontSize: "clamp(1.875rem, 3.2vw, 2.625rem)"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Archivo, Noto Sans SC, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.22
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Manrope, Noto Sans SC, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "Manrope, Noto Sans SC, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "normal"
  label:
    fontFamily: "Chivo Mono, ui-monospace, SFMono-Regular, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  none: "0px"
  pin: "9999px"
spacing:
  xs: "6px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.obsidian-ink}"
    rounded: "{rounded.none}"
    padding: "10px 20px"
  input-search:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.obsidian-ink}"
    rounded: "{rounded.none}"
    padding: "10px 12px"
  nav-tab:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-muted}"
    rounded: "{rounded.none}"
    padding: "0 2px"
---

# Design System: AetherVault & TectonicLoop — Spatial AI Monograph

## Overview

**Creative North Star: "The Architectural Monograph & Specimen Index"**

This visual system frames spatial AI tooling as an authored Swiss architectural publication and precision drafting instrument rather than a dark software telemetry panel. Every structural surface relies on pure paper whiteness, measured 1px orthogonal rules, and generous spatial cadence so photography and material color palettes carry 100% of the chromatic expression without environmental UI tinting.

The interface avoids rounded card nesting, blurred atmospheric blobs, colored left-stripe borders, eyebrow kickers, overlaid corner badges on photographs, and sub-12px micro-copy. Primary navigation, comparison curtains, and specimen plates read cleanly across both 1440px studio displays and 390px handheld screens.

**Key Characteristics:**
- Uncast gallery paper canvas (`paper`) paired with 1px structural Swiss hairlines (`hairline`) instead of bordered card clusters.
- Single committed Signal Cobalt focal accent (`primary`) reserved exclusively for active selections, focus states, primary conversions, and curtain manipulation handles.
- Complete image sovereignty on 4:3 photography plates with all metadata, OKLab swatches, and 3-slot assignment actions cleanly anchored outside the photographic frame.
- Progressive disclosure: headline proof and borderless curation plates lead; 8-axis deep calibration and structured AST compilation live in focused slide-over dialogs.

## Colors

An uncast gallery paper and ink monochrome foundation anchored by one razor-sharp architectural blue focal signal and strict functional verification tones.

### Primary
- **Signal Cobalt** (`primary`): Reserved for primary actions, active 3-slot mixer states, range slider thumbs, Before/After curtain handles, and focused interactive borders. Maintains a 7.2:1 contrast ratio with white labels.
- **Cobalt Deep** (`primary-deep`): Pressed and hover state for primary solid buttons, deepening tonal commitment without changing hue family.
- **Cobalt Paper Tint** (`primary-tint`): Subtle wash used exclusively for selected comparison indices and toggled filter states paired with Signal Cobalt ink.

### Neutral
- **Gallery Paper** (`paper`): Default viewport background and unframed specimen matrix ground so photographic color casts and OKLab swatches read neutrally.
- **Cool Paper Surface** (`cool-surface`): Secondary tonal backing behind 4:3 specimen mats, drafting code blocks, radar charts, and sticky/dialog footers.
- **Drafting Plate** (`drafting-plate`): Crisp archival tint inside the TectonicLoop orthographic architectural elevation SVG canvas.
- **Obsidian Ink** (`obsidian-ink`): Primary headings, body emphasis, primary structural rules (`1px` modal and dock outlines), and dark action buttons.
- **Slate Muted** (`slate-muted`): Secondary descriptions, axis bipolar labels, and quiet metadata; passes WCAG AA/AAA against both Gallery Paper and Cool Paper Surface.
- **Swiss Hairline** (`hairline`) & **Control Track** (`hairline-strong`): `1px` cell/section dividers (`gap-px` grids and table rules) and slider rail tracks.

### Semantic Verification
- **Verified Teal** (`teal-verified`): Positive constructability compliance checks, live engine health indicator, and benchmark acceptance targets.
- **Alert Crimson** (`crimson-alert`): Constructability hazard markers, negative prompt guardrails, and offline engine error banners.

### Named Rules
**The One-Signal Restraint Rule.** Signal Cobalt (`primary`) appears on less than 10% of the viewport so active AST slots, the diff curtain handle, and primary CTAs read immediately without competing against the photography.
**The Uncast Neutral Plate Rule.** Curated images and OKLab swatches sit strictly on `#FFFFFF` or `#F4F5F7` neutral grounds—never tinted dark panels—preventing optical white-balance distortion.
**The Honest Semantic Contrast Rule.** Every foreground label and button state meets or exceeds WCAG AA (`>= 4.5:1`), placing pure white ink over Signal Cobalt (`7.2:1`) and Obsidian Ink (`19.0:1`), and Verified Teal or Alert Crimson cleanly on Gallery Paper (`>= 5.4:1`).

## Typography

**Display Font:** `Archivo` (weights 600–800, paired with `Noto Sans SC` for Chinese architectural clarity)
**Body Font:** `Manrope` (weights 400–700, paired with `Noto Sans SC`)
**Label/Mono Font:** `Chivo Mono` (tabular numerals for latencies, prices, Spearman correlation, and structural node indices)

**Character:** Heavy geometric industrial grotesk display headlines anchored with tight tracking against crisp neo-grotesque prose and monospace numeric telemetry, eliminating generic UI defaults such as `Inter` and `JetBrains Mono`.

### Hierarchy
- **Display** (`800`, `clamp(1.875rem, 3.2vw, 2.625rem)`, `1.12` line-height, `-0.03em` tracking): Page thesis statements on `AetherVault` and `双引擎方法论`.
- **Headline** (`700`, `1.5rem`, `1.22` line-height, `-0.02em` tracking): Major section headers across the gallery, benchmark, and elevation sandboxes.
- **Title** (`700`, `1.125rem`, `1.35` line-height): Modal dialog titles and architectural system sub-columns.
- **Body** (`400`, `0.9375rem`, `1.65` line-height, max `46ch–70ch`): Technical architecture rationale and concise workspace guidance.
- **Label & Telemetry** (`500`, `0.75rem` / `12px` strict floor, `tabular-nums`): Metadata, slot selectors, cost figures, and table cells.

### Named Rules
**The 12px Floor Rule.** No user-facing text drops below `12px` (`0.75rem`); sub-12px eyebrow tags and `9px–11px` micro-badges are permanently prohibited.
**The Heading Self-Sufficiency Rule.** Headings never carry ALL-CAPS decorative eyebrow kickers above them; strong weight (`700–800`) and generous top margin establish hierarchy alone.

## Layout

A `max-w-7xl` (`1280px`) centered monograph canvas with `16px–24px` outer gutters. On `1440×900` desktop, the `57px` single-row masthead opens directly into a 12-column asymmetric Proof Hero (5-col thesis + 3 hairline-divided tabular benchmarks + 2 CTAs paired with a 7-col live Before/After AST Curtain and 01–06 index strip), followed cleanly below by a natural-scrolling 4-column photography gallery (`gap-x: 24px`, `gap-y: 40px`) and a fixed `64px` bottom Specimen Compiler Dock. Nested scroll boxes inside columns are avoided; tables wrap in clean `overflow-x-auto` containers on `390px` mobile viewports with zero document horizontal overflow.

## Elevation & Depth

Surfaces are architecturally flat by default. Separation is achieved through hairline structure (`1px solid #E2E5EA` or `gap-px` matrix grids), sharp contrast ink rules (`1px solid #0E1015` on active dialogs and the sticky bottom dock), and gentle tonal stepping (`#FFFFFF` to `#F4F5F7`). Soft backdrop dimming (`#0E1015` at 60–70% opacity with `2px` blur) elevates slide-over drawers, the calibration dialog, and the specimen lightbox without heavy drop-shadow chrome.

### Named Rules
**The Hairline-Over-Shadow Rule.** Never rely on ambient gray drop-shadows or bordered rounded cards to separate panels; structure density with clean `1px` Swiss grid lines and whitespace.

## Shapes

Sharp rectangular geometry (`0px` corner radius on buttons, inputs, dialogs, plates, and range thumbs) echoes physical architectural drafting sheets and anodized metal specimens. The sole circular silhouette (`9999px`) is strictly reserved for the live engine status dot and numbered orthographic hazard/check pins on the TectonicLoop elevation sheet so diagnostic targets read immediately as spatial markers against crisp architectural elevation lines.

## Components

### Buttons
- **Shape:** Sharp rectangular edges (`0px` radius), minimum height `36px–44px` for desktop and thumb reachability.
- **Primary:** Solid Signal Cobalt (`#153CE8`) fill with `#FFFFFF` label (`10px 20px`), darkening to `#0E2BB5` on hover.
- **Secondary / Hairline:** Pure `#FFFFFF` ground with `1px solid #0E1015` outline (`10px 20px`), shifting to `#F4F5F7` on hover; visible `2px solid #153CE8` offset outline on `:focus-visible`.

### Inputs / Fields
- **Style:** Full-width `#FFFFFF` input framed by `1px solid #E2E5EA` with sharp `0px` corners and integrated icon + action button (`min-h-[42px]`).
- **Focus:** Border shifts cleanly to `#153CE8` while global `:focus-visible` maintains clear keyboard ring affordance; custom `<input type="range">` renders a `2px` neutral track and square `14px` Signal Cobalt thumb.

### Navigation
- **Style:** Single-row `56px` desktop masthead over `1px solid #E2E5EA`; tabs carry zero numerical prefixes and indicate active selection solely via `#0E1015` semibold ink and a flush `2px solid #153CE8` bottom rule. On mobile (`< 768px`), tabs align cleanly in a single horizontal scrollable rail (`40px` height) directly beneath a compact `48px` brand bar.

### Specimen Plate & Signature Interactions
- **Specimen Plate:** Borderless `aspect-[4/3]` photograph on `#F4F5F7` mat with subtle `scale-[1.02]` hover zoom, paired cleanly beneath the frame with title, tabular match %, domain/prior indicator, continuous 5-swatch interactive OKLab color bar, and a flush 3-cell hairline selector (`镜头` / `材质` / `光影`).
- **Before/After Orthogonal AST Curtain:** `aspect-[4/3]` clipped dual-image comparator with pointer drag, `ArrowLeft`/`ArrowRight` + `Home`/`End` keyboard step, accessible range scrub bar, and high-contrast Cobalt square drag handle.
- **Orthographic Elevation Pins:** Keyboard-focusable circular `32×32px` HTML overlay buttons (`#C62828` active hazard / `#0F766E` verified resolved) mounted directly over a technical CAD-grade light `<svg>` elevation.

## Do's and Don'ts

### Do:
- **Do** keep all gallery photography 100% free of floating badges, source tags, or watermarks—place provenance and match telemetry cleanly below the frame or inside `SpecimenLightbox`.
- **Do** separate dense multi-metric rows with `gap-px bg-[#E2E5EA]` matrices or `border-t-2 border-[#0E1015]` monograph rules so breakpoints wrap cleanly.
- **Do** maintain `:focus-visible` rings on every custom control including `<input type="range">` sliders and closeable `role="dialog"` modals (`Escape` + backdrop click).
- **Do** wrap data tables in `overflow-x-auto` containers and preserve workspace state across tab switches.

### Don't:
- **Don't** place colored vertical stripes (`border-l-2` / `border-l-4`) on the left edge of cards, pillars, or alerts.
- **Don't** introduce two-axis background grid lines (`.bg-tech-grid`) behind prose or page shells; keep technical drafting grids strictly inside the TectonicLoop orthographic `<svg>` plate.
- **Don't** use `Inter`, `JetBrains Mono`, `Space Grotesk`, `Playfair Display`, or `<12px` typography classes anywhere in the interface.
- **Don't** render raw emojis (`⚡`, `🧪`), internal sprint IDs (`MIC-*`, `P-MIC-*`), or candidate interview coaching prompts in user-facing copy.
