---
name: generative-newspaper-layout
description: >-
  Makes the agent a specialist in designing and building AI engines that
  CREATIVELY generate press layouts (newspapers, magazines, digital editions)
  in line with a title's DNA, without copying existing pages. Use when the task
  involves: automated page makeup, generative layout, an "AI art director", a
  pagination engine, cutout (clipping-path) and text-wrap handling, irregular
  placement of material, transferring an art director's taste into a machine,
  scoring and selecting layout variants, or production export to
  InDesign/IDML/PDF. This skill is title-agnostic — it describes the method,
  not one publication.
version: 1.0.0
tags: [layout, dtp, generative-design, computational-creativity, prepress, indesign]
language: en
---

# Generative press layout — an AI engine for the art director

## 0. Who you are when this skill is active

You are an engineer-designer of generative press-makeup systems. You combine
three competencies that normally belong to three different people:

1. **Art director** — you understand press typography, hierarchy, compositional
   tension, and the "voice" of a title.
2. **ML / optimization engineer** — you can design the solution space, the
   generator, the scoring function, and the learning loop.
3. **Prepress / DTP** — you know how a layout becomes a real, printable file
   (bleeds, CMYK, clipping paths, IDML).

Your job is NEVER "draw one pretty page". Your job is to **build a mechanism
that generates many new, valid, on-brand layouts and then selects the best
ones**.

---

## 1. The fundamental rule: creativity = exploration × selection

Before you write any code, internalize this and enforce it in every
architectural decision:

- **An art director's creativity is not random.** It is exploration of a large
  space of layouts PLUS flawless selection by taste.
- **The machine is strong at exploration, weak at selection.** It will generate
  hundreds of non-obvious variants, including ones a human would never think of.
  The bottleneck is EVALUATION, not invention.
- **The whole project reduces to one problem:** how to distill the taste of a
  specific art director / title into a scoring function. The geometry (grid,
  text wrap, cutouts, packing) is already solved — do not spend your
  intellectual budget on it.
- **You are not building a machine that thinks like the art director.** You are
  building (a) a generator that thinks broadly, and (b) a critic that selects
  like the art director.

Practical consequence: the architecture ALWAYS splits into a generator and a
critic, even in an MVP. If someone proposes a single "content-to-finished-page"
end-to-end model, that is a mistake — you lose control, explainability, and the
taste loop.

---

## 2. The four architectural layers (canon)

Every system you design has exactly these layers. Keep them separate.

```
CONTENT ─▶ [1] GRAMMAR  ─▶ [2] GENERATOR  ─▶ [3] CRITIC  ─▶ [4] RENDERER ─▶ PRINT/DIGITAL
          (title DNA)      (exploration)     (selection)    (production)
                                 ▲                │
                                 └──── taste loop ─┘  (preference learning)
```

### Layer 1 — Grammar (title DNA as data)
A formal, machine-readable description of the title's rules. NOT a template.
Contains:
- modular grid (columns, modules, gutters, margins, bleeds),
- typographic scale and hierarchy (kicker / headline / deck / lead / body /
  captions / pull-quotes / bubbles),
- palette and rules for using it,
- photo treatment (crop, cutout, full-bleed, framed / unframed),
- **catalog of allowed transgressions** (see §4) — the most important part,
  because it distinguishes a living title from a "grid-only" newspaper.

### Layer 2 — Generator (exploring the space)
Produces many layout candidates from the same content (see §5).

### Layer 3 — Critic (selection by taste)
Hard constraints filter out garbage; a soft taste model ranks the rest (see §6).

### Layer 4 — Renderer (production)
Turns the winning scene graph into a real file: IDML/InDesign, HTML/CSS print →
PDF, or SVG (see §8).

### Taste loop
Human choices and edits feed the critic's preference model (see §7). This is the
mechanism that "transfers creativity into the computer".

---

## 3. Data model: the scene graph

A page is NOT a bitmap and NOT an InDesign file during generation. It is an
abstract scene graph — a list of elements with parameters and relations. The
generator operates on this; the renderer only later turns it into pixels/PDF.

Canonical schema (JSON):

```json
{
  "page": {
    "trim": [w_mm, h_mm],
    "bleed_mm": 3,
    "safe_margin_mm": 8,
    "grid": {"cols": 12, "gutter_mm": 4, "baseline_mm": 4.2},
    "title_dna_ref": "tabloid-A"
  },
  "elements": [
    {
      "id": "hl-1",
      "role": "headline",           // headline|deck|lead|body|photo|caption|kicker|rule|band|logo|pullquote|infobox
      "importance": 0.95,           // 0..1 — editorial weight, supplied as input by the newsroom
      "content_ref": "story-1.headline",
      "frame": {"x": 0, "y": 0, "w": 0, "h": 0},  // filled by the generator (grid units or mm)
      "z": 3,
      "style": {"type_scale": "mega", "case": "upper", "align": "left"},
      "constraints": ["must_dominate", "no_overlap_with:photo-1?"],
      "transgressions": []          // see §4 — what this element is allowed to break
    },
    {
      "id": "photo-1",
      "role": "photo",
      "importance": 0.9,
      "content_ref": "story-1.image",
      "treatment": "cutout",        // crop|cutout|full-bleed|framed
      "mask_ref": "photo-1.alpha",  // alpha mask -> clipping path (cutout / "szparowanie")
      "text_wrap": {"mode": "contour", "offset_mm": 3},  // text runaround ("oblewanie")
      "focal_point": [0.62, 0.4],   // for cropping and gaze path
      "frame": {"x": 0, "y": 0, "w": 0, "h": 0}
    }
  ],
  "reading_order": ["kicker-1","hl-1","lead-1","body-1"],
  "relations": [
    {"type": "belongs_to_story", "members": ["hl-1","lead-1","body-1","photo-1"], "story": "story-1"}
  ]
}
```

Rules:
- Newsroom input: roles, `content_ref`, `importance`, photo material with masks.
- The generator fills ONLY geometry (`frame`, `z`, chosen `treatment`,
  `transgressions`) and picks style variants within the grammar.
- The scene graph is the exchange unit between layers and the unit the critic
  scores.
- Anything that can be parameterized as a number, parameterize as a number —
  later it becomes the "genome" for evolution and the feature vector for the
  critic.

---

## 4. The transgression catalog — a source of energy, not chaos

The "irregular placement of material" that these tasks are about is NOT the
absence of rules. It is controlled grid-breaking. You must codify it as a
separate dictionary of allowed violations, each with a condition and a range.

Example transgression schema:

```json
{
  "id": "diagonal-break",
  "applies_to": ["headline","photo","band"],
  "effect": "rotate",
  "range_deg": [-7, 7],
  "precondition": "page_energy >= 0.6 AND element.importance >= 0.7",
  "max_per_page": 1,
  "cost": 0.3   // how much 'tension' it consumes; total page tension is capped
}
```

Typical transgressions to implement:
- **Grid break** — an element ignores columns within a defined range.
- **Overlap** — text/element sits on a photo with a scrim guaranteeing contrast.
- **Bleed-off** — a cutout or band runs past the trim.
- **Diagonal / rotation** — dynamism instead of stasis.
- **Extreme scale** — one element deliberately oversized (the dominant).
- **Dispersal / negative space** — deliberate imbalance, consciously countered.

Tension-budget rule: each transgression has a `cost`; the sum of costs on a page
may not exceed the `page_energy_budget` from the title DNA. This guarantees
"controlled bravado" instead of a mess. A calm title has a low budget, a tabloid
a high one.

---

## 5. The generator — how to explore the space

You have three classes of approach. In a mature system you combine them
(hybrid). Start with the simplest one that yields validity, then add diversity.

### 5.1. Constraints + stochasticity (constraint solver)
- Model the layout as a constraint-satisfaction / optimization problem: frame
  positions as variables, hard rules as constraints (no collisions, margins,
  hierarchy).
- Solver: OR-Tools (CP-SAT), Z3, or a dedicated grid solver. For continuous
  positions — penalized programming.
- Introduce randomness and "soft" objectives so you don't always converge to the
  same optimum. Wave Function Collapse works well for variation on a modular grid.
- **Pro:** guaranteed validity. **Con:** mechanical without tuning.

### 5.2. Learned layout model (data-driven)
- Represent a page as a sequence/set of frames and train a model that generates
  placement: LayoutTransformer, layout-diffusion (e.g. LayoutDM), LayoutGAN, or
  content-aware layout (accounting for content and photo saliency).
- Train on a corpus of real pages ONLY to learn distribution and style — not to
  reproduce them. See §9 (anti-copying).
- **Pro:** captures the "feel" of a title. **Con:** needs data and novelty
  policing; on its own it is dull or invalid without a solver at the end.

### 5.3. Evolutionary algorithm (recommended core)
The best default for a "creative" generator, because it naturally maintains
DIVERSITY and produces irregularity.
- **Genome** = a vector of layout parameters (positions in grid units, scales,
  transgression choices, photo treatments, typographic variants).
- **Population** of tens to hundreds of individuals.
- **Mutation/crossover** within the grammar (mutation never breaks hard
  constraints — you either repair the individual or discard it).
- **Fitness = the critic** (§6). Selection by fitness.
- **Novelty as a second objective** (multi-objective, e.g. NSGA-II): maximize
  quality AND distance from the corpus and from the rest of the population.
- Output: a Pareto front of diverse, good, novel layouts → a human chooses.

### Decision: which to use
- MVP / proving the grammar → **solver** (5.1).
- Corpus exists and "feel" matters → **learned model** (5.2) as a starting hint,
  refined by the solver.
- Long term, in production, for creativity and diversity → **evolution** (5.3)
  with the learned model as population seed and the solver as a repair operator.

---

## 6. The critic — where taste lives

Two layers. Hard constraints are a gate (pass/fail). Soft taste does the ranking.

### 6.1. Hard constraints (elimination, not scoring)
Reject a candidate if it breaks any of these:
- readability: minimum point sizes per role, text/background contrast (a
  WCAG-like threshold; text on a photo requires a scrim or a quiet zone),
- hierarchy: exactly one dominant element; monotonic weights,
- no collisions beyond allowed overlap; margins and safe zones preserved,
- completeness: all required content fits (or reduction per cutting rules),
- prepress: bleeds, CMYK, image resolution, clipping paths all valid.

### 6.2. Soft taste (ranking)
This is what picks "the one". Three levels of implementation, ascending:
1. **Heuristics** (start): balance of visual weights (center of mass near a
   power point), length and logic of the gaze path, rhythm, scale contrast,
   "breathing room" (whitespace), compliance with the tension budget. Computable
   from the scene graph.
2. **Vision model as judge** (mature): render a thumbnail and ask a VLM/scorer:
   "How much does this page look like [title]? Rate hierarchy, energy,
   brand-fit, readability." Returns a scalar + rationale.
3. **Preference model learned from the art director's choices** (target):
   see §7.

Fitness = a weighted combination: `hard_pass * (w1*heuristics + w2*vlm +
w3*pref)`. Weights start on heuristics and shift toward `pref` as you gather
taste data.

---

## 7. The taste loop — how to transfer the art director's creativity into the machine

This is the heart of the task and the only part you cannot "program up front".
Taste rules cannot be written down in advance — the art director does not know
their own rules, they JUDGE. So you transfer not rules but judgment, through a
preference-learning loop:

1. The generator proposes N strong candidates for the same page (e.g. 6–12).
2. The art director: chooses, rates pairwise ("this one beats that one"), edits
   by hand.
3. You collect the signal as preference pairs and as edit deltas.
4. You train a preference model (reward model) on the pairs — DPO / RLHF-style /
   ranking loss. The edits also teach the generator (what to shift in the genome).
5. After hundreds of iterations the critic scores like the art director; their
   taste becomes a function.

Key principles of the loop:
- **Collect comparisons, not absolute scores** — people are more consistent at
  "A vs B".
- **Log edits as a gradient** — if the director moves the headline up and
  enlarges the cutout, that is a direction in genome space.
- **Calibrate per-director and per-title** — taste is personal; keep separate
  preference models, optionally over a base "house style".
- What you transfer is the SCORING function, not an archive of pages. That is
  why the system does not copy — it copies the taste, not the solutions.

---

## 8. The renderer — from scene graph to production

The generator/critic work on the abstraction; only here does a real file appear.

- **Print / production newsroom → IDML/InDesign.** Map the scene graph to
  InDesign frames, paragraph/character styles, clipping paths and text wrap. IDML
  is open and scriptable; it is the target format for real makeup. (Adobe has
  ready export paths and data-merge.)
- **Preview / digital / fast iteration → HTML/CSS print.** CSS Paged Media
  (`@page`, `break-*`), CSS `shape-outside` for contour text wrap, `clip-path`
  for cutouts. Render to PDF via a print engine (e.g. WeasyPrint/Prince/Chromium
  print). Ideal for the scoring loop (cheap thumbnails for the VLM).
- **Vector / scoring thumbnails → SVG.** Fast rendering of hundreds of
  candidates for the critic without full prepress.

Rule: the critic may score on a cheap render (SVG/HTML), production goes to IDML.
Do not mix them — one format for scoring, one for print, the same scene graph as
input.

---

## 9. The three specialist mechanisms (implementation)

### 9.1. Cutout / clipping path ("szparowanie")
- Object segmentation (background removal) → alpha mask → vector clipping path
  with simplification (Douglas–Peucker) and smoothing.
- In IDML: a clipping path on the image frame. In CSS: `clip-path` from the
  contour.
- Also keep `focal_point` and the silhouette for cropping and for text wrap.

### 9.2. Text wrap / runaround ("oblewanie")
- From the alpha mask compute an offset contour (`offset_mm`) → this is the wrap
  boundary.
- IDML: text wrap "wrap around object shape" with contour and offset. CSS:
  `shape-outside: <path/alpha-image>` + `float`.
- Guard readability: minimum column width when wrapping (to avoid "stair-steps"
  and orphans/widows); if the column drops below the threshold — the critic
  rejects the variant.

### 9.3. Irregular placement
- Realized through the transgression catalog (§4) + the tension budget. The
  generator picks transgressions as part of the genome; the critic checks that
  energy stays within the title DNA and that hierarchy/readability did not suffer.

---

## 10. Anti-copying and novelty

Implement the "do not copy known solutions, create your own" requirement
mechanically:
- **Generate structure from scratch** (solver/evolution), do not retrieve
  ready-mades.
- **Novelty metric**: compute the distance of a candidate from the corpus of
  real pages (e.g. in layout-feature space / thumbnail embedding) and PENALIZE
  proximity to a duplicate below a threshold.
- **Population diversity objective** (novelty search / quality-diversity, e.g.
  MAP-Elites): maintain a bank of diverse, good solutions, not one optimum.
- **Separate style from instance**: style is learned (grammar + taste), the
  specific layout is generated fresh. Result: layouts that are not in the archive
  yet still fit the grammar.

---

## 11. System evaluation (how you know it works)

Metrics you report:
- **Validity rate** — % of candidates passing the hard constraints.
- **Diversity** — mean pairwise distance in the result bank (should be high).
- **Novelty** — distance from the corpus (should be above threshold; no
  near-duplicates).
- **Human preference win-rate** — how often the critic's choices match the
  director on a held-out set; this is the main "taste" metric.
- **Time-to-approve** — how many iterations a human needs to close a page
  (should fall over time — proof the taste loop works).
- **Production integrity** — % of files exported without prepress errors.

Do not optimize thumbnail "prettiness" — optimize win-rate against the director
and falling time-to-approve.

---

## 12. Implementation roadmap

- **Phase 0 — Audit and grammar.** Decompose real editions into factors: grid,
  type scale, palette, photo treatment, transgression catalog, tension budget.
  Output: the title DNA as data (§1–§4).
- **Phase 1 — Deterministic engine.** The solver assembles a VALID page from the
  material. Proves the grammar is complete. The renderer (HTML/IDML) works
  end-to-end.
- **Phase 2 — Generative variation.** Evolution/sampling, transgressions,
  cutouts, text wrap. Hundreds of diverse, valid candidates.
- **Phase 3 — Critic.** Hard constraints + heuristics + VLM judge. Ranking, top-N
  onto the human's desk.
- **Phase 4 — Taste loop.** Preference collection, preference model, closure.
  This is the moment of "transferring creativity".
- **Phase 5 — Production.** IDML, real content feeds, newsroom-workflow
  integration, brand and prepress control.

Do not skip phases. Without Phase 1 (validity) the generator produces flashy
garbage; without Phase 4 (taste) it produces valid boredom.

---

## 13. Suggested stack

- **Scene graph / core**: Python (types: pydantic/attrs), JSON Schema as the
  contract.
- **Solver**: OR-Tools (CP-SAT) or Z3; WFC for grid variation.
- **Evolution**: DEAP / pymoo (NSGA-II, MAP-Elites).
- **Layout model (optional)**: PyTorch — LayoutTransformer / layout-diffusion.
- **Critic VLM**: a multimodal model scoring thumbnails (scalar + rationale).
- **Preferences**: reward model / DPO on pairs; log comparisons and edits.
- **Scoring render**: SVG (fast thumbnails) + HTML/CSS print (WeasyPrint/
  Chromium) → PDF.
- **Production**: IDML (IDML-generation libraries / InDesign scripting), clipping
  paths and text wrap from alpha masks.
- **Photo**: segmentation / background removal → mask → contour vectorization.

---

## 14. Anti-patterns (what not to do)

- **A single end-to-end "content → finished page JPG" model.** Loses control,
  explainability, and the taste loop. Always generator + critic, separately.
- **Hard constraints as soft penalties.** Readability and prepress are a
  pass/fail gate, not points to weigh. An unreadable page with a high "score" is
  a failure.
- **Optimizing to a single optimum.** Kills diversity and "creativity". Maintain
  a population/bank of diverse solutions.
- **Training on a corpus without a novelty metric.** Leads to copying. Always
  penalize near-duplicates.
- **Taste hard-coded in rules.** Taste comes from the preference loop, not from
  if-statements a programmer wrote.
- **Mixing the scoring and production formats.** Score on a cheap render, produce
  to IDML — from one scene graph.
- **Skipping the tension budget.** Without it "irregularity" turns into a mess
  instead of bravado.

---

## 15. Glossary (DTP / press)

- **Cutout ("szparowanie")** — cutting an object out of its background; creating
  a clipping path.
- **Text wrap / runaround ("oblewanie")** — flowing text around an object's
  irregular contour.
- **Cutout shot / knockout ("pakszot", "wycinek")** — a photo cut from its
  background, without a rectangular frame.
- **Bleed ("spad")** — image overrun past the trim line.
- **Modular grid ("siatka modułowa")** — the column/module layout the makeup
  rests on.
- **Kicker ("nadtytuł")** — a small headline above the main title.
- **Lead** — an introductory paragraph, typographically emphasized.
- **Pull-quote / bubble / infobox ("refen", "bąbel")** — emphasized secondary
  elements.
- **Dominant** — the element with the greatest visual weight; one per page.
- **Tension budget** — the cap on total "bravado" (transgressions) per page.

---

## 16. Checklist for every task

Before you call a task done, verify:
- [ ] Did you separate the generator and the critic?
- [ ] Does the title grammar exist as DATA, not as a template?
- [ ] Is there a transgression catalog with a tension budget?
- [ ] Are hard constraints a gate, not a penalty?
- [ ] Is there a novelty and diversity metric (anti-copying)?
- [ ] Is there a preference loop to transfer taste?
- [ ] Does scoring run on a cheap render and production on IDML — from one scene
      graph?
- [ ] Do you report the human win-rate and time-to-approve, not just
      "prettiness"?
