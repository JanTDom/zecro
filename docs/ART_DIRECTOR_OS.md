# ZECRO Art Director OS

## Problem to solve

The product must solve two coupled editorial problems:

1. decide what a page is trying to do before placing boxes;
2. produce approved copy packages that fit the chosen frames without a manual
   word-count guessing loop.

The old flow solved neither problem explicitly. It generated geometry from a
single page template and treated copy as strings attached to that geometry.
The corpus was reduced to a few means, which is useful as a prior but is not a
model of editorial practice.

## Operating model

Every generation run has four persistent artefacts:

```text
Corpus Knowledge → Art Direction Plan → Scene Graph → Copy Slot Plans
                         ↑                   ↓
                         └── taste / edits ──┘
```

The **Art Direction Plan** is the decision layer. It records the page thesis,
hierarchy, reading path, photo strategy, copy strategy, hard constraints,
corpus evidence and the reason for selecting an architecture. It is not a
template and it is not a post-hoc caption for a random page.

The **Scene Graph** is the production-neutral geometry. It can be rendered to
SVG/HTML for cheap judgement and to IDML/PDF for production.

The **Copy Slot Plan** is the contract between the page and the writer. It is
bound to one concrete frame and includes the editorial job, writing
instruction, target words/lines, capacity, columns, fit status and a repair
recommendation. A future LLM writer must return variants against these slots;
it is not allowed to rewrite facts outside the claim/source contract.

## Knowledge model

The corpus must be retained at three levels:

### Measured page signatures

For every page store the detected regions, role guesses, normalized geometry,
reading order, typography rhythm, image treatment, whitespace topology and
relations such as `headline-over-photo` or `body-under-deck`.

### Strategy clusters

Cluster signatures by page zone and title archetype. A cluster is a strategy,
not a copied page: dominant-left, split hero, stacked bulletin, visual opener,
modular rail, and future strategies discovered by the data. Store the centroid,
dispersion, prerequisites and anti-patterns.

### Title DNA and taste

DNA stores the editable grammar. Human pairwise choices and geometry edit
deltas update a preference model over the measured signature and strategy
features. The generator samples a Pareto frontier of quality, novelty and
strategy coverage.

The current implementation passes filtered corpus guidance into the run and
records the sample count. It now also assigns each indexed page a transparent
strategy signature (`visual-opener`, `dominant-hero`, `dense-classic`,
`modular-rhythm` or `balanced-grid`) with evidence, relations and confidence.
The generator uses the resulting strategy distribution to bias exploration
without copying a page. The next corpus milestone is richer region detection
and learned strategy clusters rather than rule-inferred signatures alone.

## Generation loop

1. Diagnose the material: number and importance of stories, word volume,
   photos, claims, locked passages and missing editorial fields.
2. Select a portfolio of strategies compatible with the DNA and material.
3. Allocate frames and run the hard gate: hierarchy, collision, readability,
   copyfit, image resolution and prepress.
4. Bind a copy slot plan to every text frame.
5. Rank candidates by taste, novelty and coverage of distinct strategies.
6. Render a cheap preview for human choice.
7. When the human edits a frame or selects a text variant, log the delta and
   feed it back into the preference model.

The key invariant is bidirectionality: moving a frame changes its copy budget;
choosing a longer approved copy variant can request a reflow or a new frame.
The two operations never silently overwrite one another.

## Fast page copy workflow

The intended writer flow is:

1. paste source notes or import a source record;
2. extract claims and mark locked passages;
3. choose or generate a page strategy;
4. receive a package of headline/deck/lead/body/caption variants with exact
   target lines and source provenance;
5. select a variant per slot or ask for a shorter/longer version;
6. re-run copyfit and see the page update immediately;
7. approve the story and only then export to production.

The deterministic local engine already supports provenance, claims, locked
passages, variants and fitting. The new frame-bound plan makes those services
usable while writing the page instead of after a layout failure. A hosted
writer adapter can be added without changing the contracts or the critic.

## Non-negotiable quality gates

- one editorial dominant, with photo and headline treated as one cluster;
- no visible overset, implausible column measure or unresolved widow/orphan;
- effective raster DPI calculated from pixels and placed size;
- no near-copy of a corpus page;
- at least the requested number of materially different strategy candidates;
- every generated text variant carries claim/source provenance;
- every production export comes from the same scene graph that was judged.

## Current delivery

The generator now has explicit architecture genes and strategy coverage. Every
new candidate carries `metadata.art_direction` with an explainable decision and
frame-bound copy slots. The gallery surfaces the architecture, confidence and
the number of slots needing editorial work. Backend tests cover the contract;
production verification confirmed that the active project receives the plan in
all six candidates.

The next high-value implementation is richer region relation extraction and a
learned strategy-cluster index. That is the step that turns “more than a
thousand examples” from transparent signatures into reusable editorial
knowledge with learned dispersion and anti-patterns.
