# Zecro Generative Layout Engine — backend

Marka produktu: **Zecro**, docelowa domena: **Zecro.pl**.

Production FastAPI backend and computational layout engine for editorial art direction, strictly implementing the 4-layer architecture defined in `SKILL.md`:

```
CONTENT ─▶ [1] GRAMMAR ─▶ [2] GENERATOR ─▶ [3] CRITIC ─▶ [4] RENDERER ─▶ PRINT/DIGITAL
          (Title DNA)       (Exploration)     (Selection)     (Production)
                                  ▲                │
                                  └── TASTE LOOP ──┘ (Preference Learning)
```

---

## Architecture & Modules

1. **Contracts (`contracts/`)**
   - `scene_graph.schema.json`: Formal JSON Schema for abstract scene graph (page trim, bleed, modular grid, elements, frames, treatments, contour text-wrap, reading order, story relations).
   - `title_dna.schema.json`: Formal JSON Schema for publication DNA (trim, margins, columns, typographic scales, color palette, photo rules, transgression catalog, and page tension budget).

2. **Grammar & Geometry (`backend/app/engine/grammar.py`)**
   - `LayoutGrammar`: Modular grid coordinate conversions (columns to mm, gutters, baseline snapping, typography scale resolution).
   - Factory presets for **Broadsheet** (`The Daily Chronicle`) and **Tabloid/Expressive** (`Gazeta Codzienna`).

3. **Deterministic Constraint Solver (`backend/app/engine/solver.py`)**
   - Lays out editorial content into a strictly valid, baseline-aligned modular grid with masthead, kicker, headline, dominant cutout/photo, lead text, multi-column body copy, and secondary stories.

4. **Transgression Catalog & Tension Budget (`backend/app/engine/transgressions.py`)**
   - `diagonal-break`: Rotations for dynamic tension.
   - `overlap-scrim`: Headline overlapping image with contrast scrim.
   - `bleed-off`: Bleeding elements over page trim.
   - `extreme-scale`: Enlarged dominant editorial headlines.
   - `cutout-wrap`: Silhouette cutout with organic contour text wrap.
   - `TransgressionManager`: Computes energy consumption and enforces `page_energy_budget`.

5. **Image Processing & Contour Wrap (`backend/app/engine/image_ops.py`)**
   - Alpha mask boundary extraction.
   - Ramer-Douglas-Peucker 2D polygon simplification.
   - Polygon outward dilation for text wrap margins.
   - CSS `shape-outside: polygon(...)`, `clip-path`, and SVG path formatting.

6. **Evolutionary Layout Generator (`backend/app/engine/evolution.py`)**
   - Parameterized genome chromosome representation.
   - Multi-objective Pareto exploration (quality fitness + corpus novelty + candidate diversity).
   - Crossover, mutation, and solver repair.

7. **Two-Layer Critic (`backend/app/engine/critic.py`)**
   - **Hard Gate (Pass/Fail)**: Minimum readable font sizes, single dominant element, safe margins & bleed bounds, non-overlap collisions, and energy budget bounds.
   - **Soft Taste Heuristics**: Optical center of mass visual balance, reading gravity continuity, rhythm & scale contrast, breathing whitespace ratio, and tension adherence.
   - **Novelty Metric**: Euclidean distance to corpus page feature vectors (rejects near-duplicates).
   - **Diversity Metric**: Pairwise distance within the candidate pool.

8. **Taste Loop & Preference Learning (`backend/app/engine/taste_loop.py`)**
   - Bradley-Terry logistic reward model $P(A \succ B) = \sigma(\mathbf{w}^T (\mathbf{x}_A - \mathbf{x}_B))$.
   - Continuous online learning from user choices, pairwise comparisons, and manual edit deltas.
   - Tracks metrics: `human_preference_win_rate` and `time_to_approve_avg_iterations`.

9. **Production & Evaluation Renderers (`backend/app/engine/renderers/`)**
   - `svg_renderer.py`: Fast vector SVG renderer for crisp candidate thumbnails.
   - `html_renderer.py`: HTML5 + CSS Paged Media (`@page`, columns, `clip-path`, `shape-outside`).
   - `pdf_renderer.py`: Print-ready PDF pipeline.
   - `idml_renderer.py`: Valid Adobe InDesign IDML ZIP package (`designmap.xml`, `Resources/`, `Spreads/`, `Stories/`, clipping paths, and contour text wrap).

---

## API Endpoints

- `GET /health` — Health check
- `GET /projects` / `POST /projects` / `GET /projects/{id}` / `DELETE /projects/{id}` — Project CRUD
- `GET /projects/{id}/dna` / `PUT /projects/{id}/dna` — Title DNA view and edit
- `GET /projects/{id}/corpus` / `POST /projects/{id}/corpus` — Ingest corpus pages & extract features
- `DELETE /projects/{id}/corpus/{page_id}` — Remove a corpus page and its cached preview
- `GET /projects/{id}/corpus/{page_id}/thumbnail` — Serve an image/PDF first-page preview
- `POST /projects/{id}/dna:learn` — Learn/calibrate DNA from corpus statistics
- `GET /archetypes` / `GET /archetypes/{id}` — Five editable global TitleDNA archetypes
- `POST /projects/{id}/dna/archetype/{id}` — Apply an archetype as the project's DNA base
- `GET /corpus/index` / `POST /corpus/index` — Inspect or build the local corpus feature index
- `POST /projects/{id}/generate` — Execute evolutionary generation run
- `GET /projects/{id}/runs/{run_id}` — View generation run & candidates
- `GET /candidates/{id}` — Candidate details & scene graph
- `GET /candidates/{id}/preview` — HTML preview
- `POST /projects/{id}/preferences` — Record pairwise comparison / selection / edit delta
- `GET /projects/{id}/taste-model` — Get taste model weights & metrics
- `POST /candidates/{id}/export?format=svg|html|pdf|idml` — Export candidate
- `GET /exports/{export_id}/download` — Download exported artifact

### Editorial workflow

- `POST /projects/{id}/issues` — create an issue and production context
- `POST /issues/{id}/sources` / `POST /issues/{id}/briefs` — ingest provenance and brief
- `POST /issues/{id}/plan/auto` — create a transparent flat plan before geometry
- `POST /issues/{id}/stories` — store a versioned story/content package
- `POST /stories/{id}/generate-variants` / `rewrite` / `shorten` / `translate` / `factcheck` / `approve` / `lock` — source-bound copy variants, claim review and explicit editorial gates
- `POST /issues/{id}/generate-layouts` — map issue stories to the existing generator while retaining issue/page provenance
- `POST /text-plans` / `POST /text-plans/{id}/fit` — copyfit contract and PASS/FAIL result
- `POST /candidates/{id}/preflight` — production gate with scene, copyfit, asset and PDF/X warnings
- `GET /issues/{id}/manifest` / `GET /editorial/{type}/{id}/history` — reproducible issue manifest and immutable revisions

---

## Quickstart

### 1. Run Seed Script
```bash
python3 backend/scripts/seed_data.py
```

### 2. Run Test Suite
```bash
python3 -m pytest backend/tests -v
```

### 3. Start Development Server
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Local-runtime boundaries

The default content and fact-check adapters are deterministic and source-bound;
they do not invent copy and a translation request without a configured provider
is returned as an explicitly unapproved draft. Copyfit uses a conservative local
estimator as a fast gate. Install and register a HarfBuzz/Pango/Skia shaper when
exact font metrics and Knuth–Plass line breaking are required.

The PDF renderer writes a real searchable vector PDF with trim/bleed/crop boxes,
local CMYK image conversion and a `.preflight.json` sidecar. PDF/X output intent,
TAC, ICC separation and Adobe InDesign opening still require the press toolchain;
the preflight report keeps that state as `WARN` instead of claiming certification.
