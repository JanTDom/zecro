from __future__ import annotations
from typing import List, Dict, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------
# Title DNA Models (Contracts & Grammar)
# ---------------------------------------------------------

class FormatDNA(BaseModel):
    trim_w_mm: float = Field(default=280.0, description="Trim width in mm")
    trim_h_mm: float = Field(default=400.0, description="Trim height in mm")
    bleed_mm: float = Field(default=3.0, description="Bleed in mm")
    margin_top_mm: float = Field(default=15.0, description="Top margin in mm")
    margin_bottom_mm: float = Field(default=15.0, description="Bottom margin in mm")
    margin_left_mm: float = Field(default=12.0, description="Left margin in mm")
    margin_right_mm: float = Field(default=12.0, description="Right margin in mm")
    slug_mm: float = Field(default=0.0, description="Slug area in mm")

class GridDNA(BaseModel):
    columns: int = Field(default=6, ge=1, le=24, description="Number of columns")
    gutter_mm: float = Field(default=4.5, ge=0.5, description="Gutter between columns in mm")
    baseline_grid_pt: float = Field(default=10.5, ge=3.0, description="Baseline grid step in points")
    rows: int = Field(default=12, ge=1, description="Number of modular rows")
    row_gutter_mm: float = Field(default=4.0, ge=0.0, description="Row gutter in mm")

class TypographyScaleDNA(BaseModel):
    mega: float = Field(default=72.0, description="Headline Mega pt")
    headline_xl: float = Field(default=48.0, description="Headline XL pt")
    headline_l: float = Field(default=36.0, description="Headline L pt")
    headline_m: float = Field(default=28.0, description="Headline M pt")
    headline_s: float = Field(default=22.0, description="Headline S pt")
    lead: float = Field(default=13.0, description="Lead paragraph pt")
    body: float = Field(default=9.5, description="Body copy pt")
    caption: float = Field(default=7.5, description="Caption pt")
    kicker: float = Field(default=9.0, description="Kicker/Overline pt")
    byline: float = Field(default=8.5, description="Byline pt")
    pullquote: float = Field(default=18.0, description="Pullquote pt")

class TypographyDNA(BaseModel):
    fonts: Dict[str, str] = Field(default_factory=lambda: {
        "headline": "Playfair Display, Georgia, serif",
        "body": "PT Serif, Times New Roman, serif",
        "sans": "Inter, Helvetica Neue, sans-serif"
    })
    scales: TypographyScaleDNA = Field(default_factory=TypographyScaleDNA)
    roles: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "headline": {"font": "headline", "weight": "bold", "line_height_multiplier": 1.05},
        "lead": {"font": "body", "weight": "500", "line_height_multiplier": 1.25},
        "body": {"font": "body", "weight": "normal", "line_height_multiplier": 1.20},
        "kicker": {"font": "sans", "weight": "bold", "case": "upper", "line_height_multiplier": 1.1},
        "caption": {"font": "sans", "weight": "normal", "line_height_multiplier": 1.15},
        "byline": {"font": "sans", "weight": "600", "case": "upper", "line_height_multiplier": 1.1},
        "pullquote": {"font": "headline", "weight": "italic", "line_height_multiplier": 1.2}
    })

class PaletteDNA(BaseModel):
    primary: str = Field(default="#111111", description="Main text & dominant rules")
    secondary: str = Field(default="#c91818", description="Accent color / kicker")
    accent: str = Field(default="#f39c12", description="Highlight accent")
    background: str = Field(default="#fdfdf9", description="Newsprint page background")
    text: str = Field(default="#1a1a1a", description="Body text color")
    tint_bg: str = Field(default="#f2ede4", description="Tinted box background")
    scrim: str = Field(default="rgba(0,0,0,0.65)", description="Scrim for text on image")

class PhotoRulesDNA(BaseModel):
    allow_cutout: bool = Field(default=True)
    allow_full_bleed: bool = Field(default=True)
    default_treatment: str = Field(default="crop")
    min_dpi: int = Field(default=200)
    max_photos_per_page: int = Field(default=3)
    text_wrap_offset_mm: float = Field(default=3.5)


class StyleBlend(BaseModel):
    """Continuous style controls shared by the generator and the UI.

    Values are normalised to 0..1.  They describe a direction in the global
    style space rather than selecting a newspaper template, so the same DNA
    can produce many valid publications.
    """

    opinion_to_tabloid: float = Field(default=0.35, ge=0.0, le=1.0)
    classical_to_avantgarde: float = Field(default=0.35, ge=0.0, le=1.0)
    dense_to_photo: float = Field(default=0.50, ge=0.0, le=1.0)

    @property
    def tabloidness(self) -> float:
        return self.opinion_to_tabloid

    @property
    def photo_dominance(self) -> float:
        return self.dense_to_photo

class TransgressionDef(BaseModel):
    id: str
    name: str
    applies_to: List[str]
    effect: str
    cost: float
    max_per_page: int = 1
    precondition: Optional[str] = None
    range: Optional[List[Any]] = None

class LogoProfile(BaseModel):
    """Measured logo geometry and brand-safe production constraints."""
    asset_ref: Optional[str] = None
    variant: Literal["primary", "compact", "monochrome", "negative", "horizontal", "vertical"] = "primary"
    aspect_ratio: Optional[float] = Field(default=None, gt=0)
    content_bbox: Optional[List[float]] = None
    dominant_colors: List[str] = Field(default_factory=list)
    optical_weight: Optional[float] = Field(default=None, ge=0, le=1)
    min_width_mm: Optional[float] = Field(default=None, gt=0)
    clear_space_mm: float = Field(default=3.0, ge=0)
    layout_mode: Literal["horizontal", "ears", "side"] = "horizontal"
    vector: bool = False
    approved: bool = False


class TitleDNA(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Standard Broad/Tabloid DNA"
    version: int = 1
    format: FormatDNA = Field(default_factory=FormatDNA)
    grid: GridDNA = Field(default_factory=GridDNA)
    typography: TypographyDNA = Field(default_factory=TypographyDNA)
    palette: PaletteDNA = Field(default_factory=PaletteDNA)
    photo_rules: PhotoRulesDNA = Field(default_factory=PhotoRulesDNA)
    transgressions: List[TransgressionDef] = Field(default_factory=list)
    page_energy_budget: float = Field(default=0.8, ge=0.0, description="Max transgression energy per page")
    archetype: Optional[str] = Field(default=None, description="One of the five global style archetypes")
    style_blend: StyleBlend = Field(default_factory=StyleBlend)
    corpus_stats: Dict[str, Any] = Field(default_factory=dict)
    logo_profile: Optional[LogoProfile] = None

# ---------------------------------------------------------
# Scene Graph Models (Contracts)
# ---------------------------------------------------------

class Frame(BaseModel):
    x: float = Field(..., description="X coordinate in mm (from trim origin)")
    y: float = Field(..., description="Y coordinate in mm (from trim origin)")
    w: float = Field(..., description="Width in mm")
    h: float = Field(..., description="Height in mm")
    unit: Literal["mm", "grid"] = "mm"
    rotation_deg: float = 0.0

class ElementStyle(BaseModel):
    type_scale: Optional[str] = None
    font_family: Optional[str] = None
    font_size_pt: Optional[float] = None
    line_height_pt: Optional[float] = None
    font_weight: Optional[str] = None
    case: Optional[Literal["normal", "upper", "lower", "title"]] = "normal"
    align: Optional[Literal["left", "center", "right", "justify"]] = "left"
    color: Optional[str] = None
    bg_color: Optional[str] = None
    border_width_mm: Optional[float] = None
    border_color: Optional[str] = None
    padding_mm: Optional[float] = None
    columns: Optional[int] = 1

class TextWrap(BaseModel):
    mode: Literal["none", "bounding_box", "contour", "jump"] = "none"
    offset_mm: float = 3.0

class Element(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: Literal[
        "headline", "deck", "lead", "body", "photo", "caption",
        "kicker", "rule", "band", "logo", "pullquote", "infobox",
        "byline", "folio", "brief_column", "jump_line", "teaser_band",
        "column", "masthead"
    ]
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    content_ref: Optional[str] = None
    text_content: Optional[str] = None
    frame: Frame
    z: int = 1
    style: Optional[ElementStyle] = Field(default_factory=ElementStyle)
    treatment: Literal["crop", "cutout", "full-bleed", "framed", "tinted"] = "crop"
    mask_ref: Optional[str] = None
    image_url: Optional[str] = None
    contour_points: Optional[List[List[float]]] = None  # [[x,y], ...] relative to frame in mm
    contour_holes: Optional[List[List[List[float]]]] = None  # enclosed background rings (evenodd)
    crop_box: Optional[List[float]] = None  # normalised source crop [l,t,r,b] shared by all renderers
    text_wrap: Optional[TextWrap] = None
    focal_point: Optional[List[float]] = None  # [u, v] normalized 0..1
    source_dpi: Optional[float] = None
    # Pixel dimensions are required to calculate the *effective* print DPI at
    # the placed frame size.  Image metadata often contains a nominal 72 DPI
    # default even when the raster has enough pixels for press output.
    source_width_px: Optional[int] = Field(default=None, gt=0)
    source_height_px: Optional[int] = Field(default=None, gt=0)
    constraints: Optional[List[str]] = Field(default_factory=list)
    transgressions: Optional[List[str]] = Field(default_factory=list)
    # Content provenance travels with geometry into SVG/HTML/IDML and preflight.
    story_ref: Optional[str] = None
    content_revision_ref: Optional[str] = None
    text_plan_ref: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)
    fit_status: Optional[Literal["PASS", "FAIL", "WARN", "unknown"]] = "unknown"
    locked: bool = False
    approval_status: Optional[str] = None
    flow_group: Optional[str] = None
    continuation_ref: Optional[str] = None
    claim_refs: List[str] = Field(default_factory=list)

class PageMeta(BaseModel):
    trim: List[float] = Field(..., description="[w_mm, h_mm]")
    bleed_mm: float = 3.0
    safe_margin_mm: float = 8.0
    grid: Dict[str, Any] = Field(default_factory=lambda: {"cols": 6, "gutter_mm": 4.5, "baseline_mm": 4.2, "rows": 12})
    title_dna_ref: Optional[str] = None
    page_zone: Literal["front_page", "spread", "back_page"] = "front_page"
    issue_ref: Optional[str] = None
    page_number: Optional[int] = None
    page_role: Optional[str] = None
    spread_ref: Optional[str] = None
    production_profile_ref: Optional[str] = None

class Relation(BaseModel):
    type: Literal["belongs_to_story", "caption_for", "scrim_under", "subhead_under"]
    members: List[str]
    story: Optional[str] = None

class SceneGraph(BaseModel):
    schema_version: str = "2.0"
    page: PageMeta
    elements: List[Element]
    reading_order: List[str] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------
# Content Material & Story Inputs
# ---------------------------------------------------------

class StoryImageInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # Compatibility fields used by imported editorial manifests and the
    # original prompt.  They are retained alongside the canonical fields so
    # old projects can be opened without a migration.
    image_id: Optional[str] = None
    url: str
    caption: Optional[str] = None
    credit: Optional[str] = None
    importance: float = 0.8
    focal_point: Optional[List[float]] = [0.5, 0.5]
    alpha_mask_url: Optional[str] = None
    is_cutout_candidate: bool = False
    aspect_ratio: Optional[float] = Field(default=None, gt=0.0)
    treatment: Optional[Literal["crop", "cutout", "full-bleed", "framed", "tinted"]] = None
    has_alpha_mask: bool = False
    contour_polygon: Optional[List[List[float]]] = None  # normalised image space 0..100
    contour_holes: Optional[List[List[List[float]]]] = None
    width_px: Optional[int] = Field(default=None, gt=0)
    height_px: Optional[int] = Field(default=None, gt=0)
    dpi: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def normalise_legacy_image_fields(self):
        if self.image_id and "id" not in self.model_fields_set:
            self.id = self.image_id
        if self.treatment == "cutout":
            self.is_cutout_candidate = True
        if self.alpha_mask_url or self.contour_polygon:
            self.has_alpha_mask = True
        if self.contour_polygon and not self.alpha_mask_url:
            self.alpha_mask_url = f"inline:{self.id}:alpha"
        return self

class StoryInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(default_factory=lambda: f"story-{uuid.uuid4().hex[:6]}")
    kicker: Optional[str] = None
    headline: str
    deck: Optional[str] = None
    byline: Optional[str] = None
    lead: Optional[str] = None
    body: str
    pullquote: Optional[str] = None
    importance: float = 0.9  # 1.0 = Lead story, 0.5 = secondary
    rank: Literal["lead", "second", "third", "short", "brief", "teaser", "box", "column"] = "second"
    span_cols: Optional[int] = Field(default=None, ge=1)
    depth_hint: Optional[Literal["S", "M", "L", "XL"]] = None
    target_words: Optional[int] = Field(default=None, ge=1)
    pin_zone: Optional[Literal["top", "under_masthead", "left_rail", "right_rail", "center", "bottom", "anywhere"]] = None
    pin_page: Optional[int] = Field(default=None, ge=1)
    teaser_only: bool = False
    continue_to_page: Optional[int] = Field(default=None, ge=1)
    group: Optional[str] = None
    images: List[StoryImageInput] = Field(default_factory=list)
    image: Optional[StoryImageInput] = None
    infobox: Optional[Dict[str, str]] = None
    pull_quote: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)
    claim_refs: List[str] = Field(default_factory=list)
    content_revision_ref: Optional[str] = None
    text_plan_refs: Dict[str, str] = Field(default_factory=dict)
    locked_passages: List[str] = Field(default_factory=list)
    approval_status: Optional[str] = None

    @model_validator(mode="after")
    def normalise_legacy_story_fields(self):
        if self.image is not None:
            # Keep the canonical plural representation used by the generator.
            if not any(existing.id == self.image.id for existing in self.images):
                self.images.insert(0, self.image)
        if self.pull_quote and not self.pullquote:
            self.pullquote = self.pull_quote
        return self

class PagePlanSlot(BaseModel):
    slot_id: str
    story_ref: str
    rank: Literal["lead", "second", "third", "short", "brief", "teaser", "box", "column"]
    col_start: int = Field(ge=0)
    col_span: int = Field(ge=1)
    row_start: int = Field(ge=0)
    row_span: int = Field(ge=1)
    module_type: Literal["lead", "article", "brief_column", "pullquote", "infobox", "jump_line", "teaser_band", "column", "masthead"] = "article"
    page_number: int = Field(default=1, ge=1)
    teaser_only: bool = False
    continuation_page: Optional[int] = None


class PagePlan(BaseModel):
    schema_version: str = "1.0"
    page_zone: Literal["front_page", "spread", "back_page"] = "front_page"
    columns: int = Field(default=6, ge=1)
    rows: int = Field(default=12, ge=1)
    masthead_rows: int = Field(default=1, ge=0)
    slots: List[PagePlanSlot] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    status: Literal["valid", "invalid"] = "valid"

    @property
    def story_refs(self) -> List[str]:
        return [slot.story_ref for slot in self.slots if not slot.teaser_only]


class PageInputMaterial(BaseModel):
    issue_date: Optional[str] = "September 1, 2026"
    issue_number: Optional[str] = "No. 14,892"
    section_name: Optional[str] = "FRONT PAGE"
    masthead_title: Optional[str] = "THE DAILY CHRONICLE"
    stories: List[StoryInput] = Field(default_factory=list)
    page_plan: Optional[PagePlan] = None
    page_zone: Literal["front_page", "spread", "back_page"] = "front_page"
    # Human-facing aliases accepted by the API and import manifests.
    page_type: Optional[Literal["front", "front_page", "spread", "back", "back_page"]] = None
    style_blend: StyleBlend = Field(default_factory=StyleBlend)

    @model_validator(mode="after")
    def normalise_page_zone(self):
        if self.page_type:
            self.page_zone = {
                "front": "front_page",
                "front_page": "front_page",
                "spread": "spread",
                "back": "back_page",
                "back_page": "back_page",
            }[self.page_type]
        return self


# ---------------------------------------------------------
# Art-direction and page-copy planning contracts
# ---------------------------------------------------------

class CopySlotPlan(BaseModel):
    """Writing brief bound to one concrete frame in a candidate page."""

    element_ref: str
    story_ref: Optional[str] = None
    role: str
    editorial_job: str
    writing_instruction: str
    source_words: int = 0
    source_characters: int = 0
    target_words: int = 0
    min_words: int = 0
    max_words: int = 0
    target_lines: int = 0
    capacity_lines: int = 0
    target_characters: int = 0
    columns: int = 1
    width_mm: float = 0.0
    height_mm: float = 0.0
    fit_status: Literal["PASS", "SHORTEN", "EXPAND", "MANUAL"] = "PASS"
    delta_words: int = 0
    recommendations: List[str] = Field(default_factory=list)


class ArtDirectionPlan(BaseModel):
    """Explainable editorial decision for one generated candidate.

    It is deliberately stored next to, but separately from, the scene graph.
    Geometry can change while the editorial thesis and writing jobs remain
    reviewable and versionable.
    """

    architecture: str
    page_thesis: str
    hierarchy: List[str] = Field(default_factory=list)
    reading_path: List[str] = Field(default_factory=list)
    photo_strategy: str = "text-led"
    copy_strategy: str = "balanced"
    allowed_transgressions: List[str] = Field(default_factory=list)
    hard_constraints: List[str] = Field(default_factory=list)
    corpus_evidence: Dict[str, Any] = Field(default_factory=dict)
    content_diagnosis: Dict[str, Any] = Field(default_factory=dict)
    decision_trace: List[str] = Field(default_factory=list)
    copy_slots: List[CopySlotPlan] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

# ---------------------------------------------------------
# Critic, Candidate & Generation Run Models
# ---------------------------------------------------------

class CriticHardGateResult(BaseModel):
    passed: bool
    violations: List[str] = Field(default_factory=list)

class CriticHeuristics(BaseModel):
    visual_balance_score: float = 0.0      # 0..1
    reading_gravity_score: float = 0.0     # 0..1
    rhythm_and_scale_score: float = 0.0    # 0..1
    breathing_space_score: float = 0.0     # 0..1
    tension_adherence_score: float = 0.0   # 0..1
    corpus_alignment_score: float = 0.0    # 0..1 — fit to measured DNA priors
    composite_soft_score: float = 0.0      # 0..1

class CriticResult(BaseModel):
    hard_gate: CriticHardGateResult
    heuristics: CriticHeuristics
    vlm_score: Optional[float] = None
    vlm_reasoning: Optional[str] = None
    preference_score: Optional[float] = None
    novelty_vs_corpus: float = 0.0
    diversity_in_run: float = 0.0
    total_fitness: float = 0.0
    explanation: str = ""

class AIProvenance(BaseModel):
    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    input_sha256: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    raw_response: Optional[Any] = None
    status: Literal["draft", "approved", "unavailable", "failed"] = "draft"
    fallback_from: Optional[str] = None


class Candidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    scene_graph: SceneGraph
    critic: CriticResult
    svg_thumbnail: Optional[str] = None
    html_preview_url: Optional[str] = None
    rank: int = 0
    selected: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class GenerationRequest(BaseModel):
    material: PageInputMaterial
    page_plan: Optional[PagePlan] = None
    num_candidates: int = Field(default=8, ge=1, le=24)
    population_size: int = Field(default=30, ge=10, le=100)
    generations: int = Field(default=15, ge=1, le=50)
    allow_transgressions: bool = True
    energy_budget_override: Optional[float] = None
    style_blend: Optional[StyleBlend] = None
    page_zone: Optional[Literal["front_page", "spread", "back_page"]] = None
    seed: Optional[int] = Field(default=None, description="Optional deterministic seed for reproducible variants")

class GenerationRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    material: PageInputMaterial
    status: Literal["pending", "running", "completed", "failed"] = "completed"
    candidates: List[Candidate] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------
# Preference Learning & Taste Models
# ---------------------------------------------------------

class PreferenceSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    signal_type: Literal["selection", "pairwise_comparison", "manual_edit_delta"]
    winner_candidate_id: str
    loser_candidate_id: Optional[str] = None
    delta_features: Optional[Dict[str, float]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None

class TasteModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    version: int = 1
    feature_weights: Dict[str, float] = Field(default_factory=dict)
    sample_count: int = 0
    human_preference_win_rate: float = 0.0
    time_to_approve_avg_iterations: float = 0.0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ---------------------------------------------------------
# Project & Corpus Models
# ---------------------------------------------------------

class CorpusPage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    title: str
    file_path: str
    file_type: Literal["pdf", "image", "idml"]
    extracted_features: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = ""
    status: Literal["draft", "ready", "learning", "active"] = "ready"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ExportArtifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    candidate_id: str
    format: Literal["svg", "html", "pdf", "idml"]
    file_path: str
    file_size_bytes: int
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ---------------------------------------------------------
# Editorial / Content Studio Contracts
# ---------------------------------------------------------

class RevisionedModel(BaseModel):
    """Shared provenance fields for editable editorial objects."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = Field(default=1, ge=1)
    parent_revision_id: Optional[str] = None
    status: str = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    author_id: Optional[str] = None
    content_hash: Optional[str] = None


class Issue(RevisionedModel):
    project_id: str
    issue_number: str
    publication_date: str
    deadline: Optional[str] = None
    page_count: int = Field(default=1, ge=1)
    sections: List[str] = Field(default_factory=list)
    format_name: str = "custom"
    printer: Optional[str] = None
    color_profile: Optional[str] = None
    status: str = "draft"


class IssuePlanPage(BaseModel):
    page_number: int = Field(..., ge=1)
    page_role: Literal["front", "inside", "spread", "back"] = "inside"
    section: Optional[str] = None
    story_refs: List[str] = Field(default_factory=list)
    # Stable references to the editorial copy budgets created before geometry
    # generation.  Frames are resolved later by the layout generator.
    text_plan_refs: List[str] = Field(default_factory=list)
    asset_refs: List[str] = Field(default_factory=list)
    spread_ref: Optional[str] = None
    ad_slots: List[Dict[str, Any]] = Field(default_factory=list)
    reserved_house_ads: List[str] = Field(default_factory=list)
    masthead: bool = True
    folio: bool = True
    continuation_links: List[Dict[str, Any]] = Field(default_factory=list)
    surface_budget: Dict[str, float] = Field(default_factory=dict)


class IssuePlan(RevisionedModel):
    issue_ref: str
    pages: List[IssuePlanPage] = Field(default_factory=list)
    variant: Literal["dense", "standard", "breathing", "poster"] = "standard"
    conflicts: List[str] = Field(default_factory=list)


class Source(RevisionedModel):
    issue_ref: str
    source_type: Literal["file", "url", "wire", "cms", "docx", "pdf", "ocr", "transcript", "spreadsheet", "statement"] = "file"
    title: str = "Untitled source"
    uri: Optional[str] = None
    excerpt: Optional[str] = None
    author: Optional[str] = None
    acquired_at: Optional[str] = None
    license: Optional[str] = None
    embargo_until: Optional[str] = None
    language: str = "pl"
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    sha256: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EditorialBrief(RevisionedModel):
    issue_ref: str
    assignment_id: Optional[str] = None
    topic: str
    angle: str
    audience: Optional[str] = None
    language: str = "pl"
    tone: str = "informacyjny"
    deadline: Optional[str] = None
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    required_facts: List[str] = Field(default_factory=list)
    legal_constraints: List[str] = Field(default_factory=list)
    forbidden_words: List[str] = Field(default_factory=list)
    required_materials: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    claim_type: Literal["fact", "date", "number", "person", "place", "quote", "thesis"] = "fact"
    source_refs: List[str] = Field(default_factory=list)
    evidence_excerpt: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["unverified", "partially_verified", "verified", "contradicted", "needs_editor"] = "unverified"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Asset(RevisionedModel):
    project_id: Optional[str] = None
    issue_ref: Optional[str] = None
    asset_type: Literal["photo", "illustration", "chart", "logo", "ad", "font", "other"] = "photo"
    uri: str
    sha256: Optional[str] = None
    provider: Optional[str] = None
    license: Optional[str] = None
    rights_owner: Optional[str] = None
    usage_scope: Optional[str] = None
    license_expires_at: Optional[str] = None
    credit_line: Optional[str] = None
    model_release: Optional[bool] = None
    ai_generated: bool = False
    prompt_provenance: Optional[str] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    focal_point: List[float] = Field(default_factory=lambda: [0.5, 0.5])
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    dpi: Optional[float] = None
    icc_profile: Optional[str] = None
    status: Literal["available", "embargoed", "expired", "missing", "approved"] = "available"


class CopyVariant(RevisionedModel):
    story_ref: str
    role: Literal["kicker", "headline", "deck", "lead", "body", "caption", "byline", "dateline", "pullquote", "factbox", "teaser"]
    variant_kind: Literal["micro", "short", "medium", "long", "exact_fit"] = "medium"
    text: str
    target_words: Optional[int] = None
    target_chars: Optional[int] = None
    target_lines: Optional[int] = None
    claim_refs: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    locked_passages: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    approval: Dict[str, str] = Field(default_factory=lambda: {"editorial": "pending", "fact_check": "pending"})


class Story(RevisionedModel):
    issue_ref: str
    brief_ref: Optional[str] = None
    slug: str
    language: str = "pl"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    rank: Literal["lead", "second", "third", "short", "brief", "teaser", "box", "column"] = "second"
    span_cols: Optional[int] = Field(default=None, ge=1)
    depth_hint: Optional[Literal["S", "M", "L", "XL"]] = None
    target_words: Optional[int] = Field(default=None, ge=1)
    pin_zone: Optional[Literal["top", "under_masthead", "left_rail", "right_rail", "center", "bottom", "anywhere"]] = None
    pin_page: Optional[int] = Field(default=None, ge=1)
    teaser_only: bool = False
    continue_to_page: Optional[int] = Field(default=None, ge=1)
    group: Optional[str] = None
    headline: str = ""
    deck: Optional[str] = None
    lead: Optional[str] = None
    body: str = ""
    byline: Optional[str] = None
    dateline: Optional[str] = None
    caption: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)
    asset_refs: List[str] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    active_variants: Dict[str, str] = Field(default_factory=dict)
    locked_passages: List[str] = Field(default_factory=list)
    editorial_status: str = "brief"
    fact_checked: bool = False
    editor_approved: bool = False


class TextPlan(RevisionedModel):
    story_ref: str
    issue_ref: str
    page_ref: Optional[str] = None
    frame_ref: Optional[str] = None
    role: str = "body"
    flow_group: Optional[str] = None
    target_words: int = Field(default=0, ge=0)
    min_words: int = Field(default=0, ge=0)
    max_words: int = Field(default=0, ge=0)
    target_chars: int = Field(default=0, ge=0)
    target_lines: int = Field(default=0, ge=0)
    columns: int = Field(default=1, ge=1)
    width_mm: float = Field(default=40.0, gt=0)
    height_mm: float = Field(default=100.0, gt=0)
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    required: bool = True
    keep_with_next: bool = False
    widow_lines: int = Field(default=2, ge=0)
    orphan_lines: int = Field(default=2, ge=0)
    no_break_tokens: List[str] = Field(default_factory=list)
    overflow_policy: Literal["shorten", "alternate", "continue", "reflow", "manual"] = "alternate"
    continuation_policy: Literal["none", "jump_if_needed"] = "jump_if_needed"
    max_tracking: float = 10.0
    max_leading_adjustment_pt: float = 0.5
    min_font_size_pt: float = 9.0
    locked: bool = False
    approval: Dict[str, str] = Field(default_factory=lambda: {"editorial": "pending", "fact_check": "pending"})


class TextFitResult(RevisionedModel):
    text_plan_ref: str
    copy_variant_ref: Optional[str] = None
    status: Literal["PASS", "FAIL"] = "FAIL"
    words: int = 0
    lines: int = 0
    capacity_lines: int = 0
    overflow_mm: float = 0.0
    free_space_mm: float = 0.0
    widows: int = 0
    orphans: int = 0
    target_words: int = 0
    target_lines: int = 0
    target_deviation_words: int = 0
    target_deviation_lines: int = 0
    font_size_pt: float = 0.0
    leading_pt: float = 0.0
    tracking_em: float = 0.0
    too_narrow: bool = False
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    measured_by: str = "zecro-copyfit-estimator"


class ProductionProfile(RevisionedModel):
    project_id: str
    output_intent: str = "ISOnewspaper26v4.icc"
    pdf_standard: Literal["PDF/X-4:2010", "PDF/X-1a:2001", "PDF"] = "PDF/X-4:2010"
    color_space: Literal["CMYK", "RGB", "Gray"] = "CMYK"
    tac_limit_percent: float = 240.0
    bleed_mm: float = 3.0
    safe_margin_mm: float = 8.0
    gripper_margin_mm: float = 12.0
    trim_box_mm: List[float] = Field(default_factory=lambda: [280.0, 430.0])
    paper: str = "newsprint_coldset"
    spot_colors: List[str] = Field(default_factory=list)
    imposition: Dict[str, Any] = Field(default_factory=lambda: {"scheme": "web_offset", "signature": 16, "creep_mm": 0})


class PreflightReport(RevisionedModel):
    candidate_ref: Optional[str] = None
    export_ref: Optional[str] = None
    status: Literal["PASS", "WARN", "FAIL"] = "WARN"
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    repairs: List[Dict[str, Any]] = Field(default_factory=list)
    profile_ref: Optional[str] = None
