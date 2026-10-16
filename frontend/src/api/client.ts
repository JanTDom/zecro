import { Project } from '../types/project';
import { TitleDNA, TypographyStyle } from '../types/dna';
import { CorpusPage } from '../types/corpus';
import { GenerationRun, Candidate, FrameCopyFit } from '../types/generation';
import { TasteModelMetrics, PreferenceSignal } from '../types/taste';
import { IntakeData, PhotoMaterial, StoryMaterial } from '../types/material';
import { ExportArtifact, ExportOptions } from '../types/export';
import { ElementDelta, SceneGraph, SceneGraphElement } from '../types/sceneGraph';
import { editorialStyle } from '../editorialStyles';

// The API is the source of truth. A disconnected backend is a visible error,
// never a successful local simulation.
export const BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
type Data = Record<string, any>;
const dnaCache = new Map<string, Data>();

export function apiUrl(path: string): string {
  if (!path || /^(https?:|data:|blob:)/.test(path)) return path;
  if (path.startsWith(`${BASE_URL}/`)) return path;
  return `${BASE_URL}/${path.replace(/^\//, '')}`;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Nie udało się połączyć z usługą ZECRO API.';
}

const API_REQUEST_TIMEOUT_MS = 120_000;

/** API error that keeps a structured backend verdict (e.g. ``photo_needed``). */
export class ApiError extends Error {
  code?: string;
  data?: Data;
  constructor(message: string, code?: string, data?: Data) { super(message); this.code = code; this.data = data; }
}

async function request<T = Data>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), API_REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, credentials: 'include', signal: init?.signal || controller.signal });
  } catch {
    if (controller.signal.aborted) {
      throw new Error('Generowanie trwało zbyt długo. Wyłącz ocenę wizualną AI albo spróbuj z mniejszą liczbą wariantów.');
    }
    throw new Error('Usługa ZECRO API jest niedostępna. Sprawdź połączenie z serwerem.');
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('zecro-session-expired'));
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') {
      throw new ApiError(detail.message, detail.code, detail);
    }
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: Data) => `${item.loc?.join('.')}: ${item.msg}`).join('; ')
      : `Błąd API (${response.status} ${response.statusText})`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

function projectFromApi(raw: Data): Project {
  return {
    id: raw.id, name: raw.name, slug: raw.name.toLowerCase().replace(/\s+/g, '-'),
    newspaperTitle: raw.name.toUpperCase(), editionCode: 'ZECRO', format: raw.format_name || 'custom',
    dimensions: raw.dimensions || { widthMm: 280, heightMm: 400, columnsCount: 6, gutterMm: 4.5,
      marginTopMm: 15, marginBottomMm: 15, marginLeftMm: 12, marginRightMm: 12, bleedMm: 3 },
    description: raw.description || '', status: raw.status === 'active' ? 'ready' : raw.status,
    corpusCount: raw.corpus_count || 0, generationRunsCount: raw.generation_runs_count || 0,
    tasteSignalsCount: raw.taste_signals_count || 0, tasteModelWinRate: raw.taste_model_win_rate || 0,
    avgTimeToApproveSec: raw.avg_time_to_approve_sec || 0, dnaVersion: raw.dna_version || 1,
    createdAt: raw.created_at, updatedAt: raw.updated_at, themeColor: '#2451f5', accentFont: 'Fraunces',
    editorialCharacter: raw.editorial_character || undefined,
  };
}

function dnaFromApi(raw: Data, projectId: string): TitleDNA {
  dnaCache.set(projectId, raw);
  const format = raw.format || {};
  const grid = raw.grid || {};
  const typography = raw.typography || {};
  const palette = raw.palette || {};
  const scales = typography.scales || {};
  const makeType = (role: string, scale: string, fallback: number): TypographyStyle => {
    const spec = typography.roles?.[role] || {};
    const size = scales[scale] || fallback;
    return { fontFamily: typography.fonts?.[spec.font || (role === 'headline' ? 'headline' : 'body')] || 'Georgia',
      weight: spec.weight || 'normal', sizePt: size, lineHeightPt: size * (spec.line_height_multiplier || 1.2),
      textTransform: spec.case === 'upper' ? 'uppercase' : 'none', color: role === 'kicker' ? palette.secondary : palette.text || palette.primary };
  };
  const stats = raw.corpus_stats || {};
  return {
    id: raw.id, projectId, version: raw.version, updatedAt: raw.updated_at || '', canonical: raw,
    archetype: raw.archetype, styleBlend: raw.style_blend,
    logo_profile: raw.logo_profile || raw.canonical?.logo_profile,
    masthead: raw.masthead || raw.canonical?.masthead,
    grid: { columns: grid.columns, columnWidthMm: ((format.trim_w_mm - format.margin_left_mm - format.margin_right_mm) - (grid.columns - 1) * grid.gutter_mm) / grid.columns,
      gutterMm: grid.gutter_mm, baselineGridPt: grid.baseline_grid_pt, marginTopMm: format.margin_top_mm,
      marginBottomMm: format.margin_bottom_mm, marginLeftMm: format.margin_left_mm, marginRightMm: format.margin_right_mm,
      subdivision: 1 },
    typography: { superHeadline: makeType('headline', 'mega', 72), headlinePrimary: makeType('headline', 'headline_xl', 48),
      headlineSecondary: makeType('headline', 'headline_l', 36), kicker: makeType('kicker', 'kicker', 9),
      deck: makeType('lead', 'lead', 13), lead: makeType('lead', 'lead', 13), body: makeType('body', 'body', 9.5),
      byline: makeType('byline', 'byline', 8.5), caption: makeType('caption', 'caption', 7.5),
      pullQuote: makeType('pullquote', 'pullquote', 18), folio: makeType('caption', 'caption', 7.5) },
    palette: { colors: [
      { name: 'Primary', hex: palette.primary, role: 'ink' }, { name: 'Secondary', hex: palette.secondary, role: 'accent' },
      { name: 'Accent', hex: palette.accent, role: 'accent' }, { name: 'Background', hex: palette.background, role: 'paper' },
      { name: 'Tint', hex: palette.tint_bg, role: 'tint' }],
      backgroundTone: palette.background, ruleColor: palette.primary, dominantInk: palette.text },
    photos: { allowedCutouts: raw.photo_rules?.allow_cutout ?? true, minAspectRatio: .3, maxAspectRatio: 3,
      preferredPlacements: ['lead-hero', 'sidebar'], wrapPaddingMm: raw.photo_rules?.text_wrap_offset_mm || 3.5,
      borderRulePt: 0, duotoneAccent: false },
    transgressionCatalog: (raw.transgressions || []).map((rule: Data) => ({ id: rule.id, name: rule.name,
      description: rule.effect, allowed: rule.max_per_page > 0, cost: rule.cost,
      maxPerSpread: rule.max_per_page, triggerCondition: rule.precondition || '' })),
    pageEnergyBudget: { maxTensionScore: raw.page_energy_budget, targetTensionScore: raw.page_energy_budget, punishExceeding: true },
    corpusMetrics: { pagesAnalyzed: stats.pages_analyzed || stats.pages_count || 0, avgDensity: stats.avg_density || 0,
      dominantColumnUsage: stats.dominant_column_usage || [], avgHeadlineToBodyRatio: stats.headline_scale_ratio || 0,
      detectedBleedRate: stats.detected_bleed_rate || 0 },
  };
}

function dnaToApi(dna: TitleDNA): Data {
  const original = dna.canonical || dnaCache.get(dna.projectId) || {};
  const scales = { ...(original.typography?.scales || {}), mega: dna.typography.superHeadline.sizePt,
    headline_xl: dna.typography.headlinePrimary.sizePt, headline_l: dna.typography.headlineSecondary.sizePt,
    lead: dna.typography.lead.sizePt, body: dna.typography.body.sizePt, kicker: dna.typography.kicker.sizePt,
    caption: dna.typography.caption.sizePt, byline: dna.typography.byline.sizePt, pullquote: dna.typography.pullQuote.sizePt };
  const roles = { ...(original.typography?.roles || {}) };
  for (const [role, value] of Object.entries({ headline: dna.typography.headlinePrimary, lead: dna.typography.lead,
    body: dna.typography.body, kicker: dna.typography.kicker, caption: dna.typography.caption, byline: dna.typography.byline,
    pullquote: dna.typography.pullQuote })) {
    roles[role] = { ...roles[role], weight: String(value.weight), line_height_multiplier: value.lineHeightPt / value.sizePt,
      case: value.textTransform === 'uppercase' ? 'upper' : 'normal' };
  }
  return { ...original, version: dna.version + 1,
    format: { ...original.format, margin_top_mm: dna.grid.marginTopMm, margin_bottom_mm: dna.grid.marginBottomMm,
      margin_left_mm: dna.grid.marginLeftMm, margin_right_mm: dna.grid.marginRightMm },
    grid: { ...original.grid, columns: dna.grid.columns, gutter_mm: dna.grid.gutterMm, baseline_grid_pt: dna.grid.baselineGridPt },
    typography: { ...original.typography, fonts: { ...original.typography?.fonts, headline: dna.typography.headlinePrimary.fontFamily,
      body: dna.typography.body.fontFamily, sans: dna.typography.caption.fontFamily }, scales, roles },
    palette: { ...original.palette, primary: dna.palette.ruleColor, text: dna.palette.dominantInk,
      secondary: dna.palette.colors[1]?.hex, accent: dna.palette.colors[2]?.hex,
      background: dna.palette.backgroundTone, tint_bg: dna.palette.colors.find(c => c.role === 'tint')?.hex },
    photo_rules: { ...original.photo_rules, allow_cutout: dna.photos.allowedCutouts, text_wrap_offset_mm: dna.photos.wrapPaddingMm },
    transgressions: dna.transgressionCatalog.map(rule => ({ ...(original.transgressions || []).find((r: Data) => r.id === rule.id),
      id: rule.id, name: rule.name, effect: rule.description, applies_to: (original.transgressions || []).find((r: Data) => r.id === rule.id)?.applies_to || [],
      cost: rule.cost, max_per_page: rule.allowed ? rule.maxPerSpread : 0, precondition: rule.triggerCondition || null })),
    page_energy_budget: dna.pageEnergyBudget.maxTensionScore, archetype: dna.archetype,
    style_blend: dna.styleBlend || original.style_blend };
}

const roleFromApi: Record<string, SceneGraphElement['role']> = { photo: 'image', logo: 'masthead', rule: 'rule-line', band: 'box-panel', infobox: 'infographic' };
const roleToApi: Record<string, string> = { image: 'photo', masthead: 'logo', 'rule-line': 'rule', 'box-panel': 'band', infographic: 'infobox' };
function sceneFromApi(raw: Data, id: string): SceneGraph {
  const page = raw.page;
  const margin = page.safe_margin_mm || 8;
  return { id, version: 1, canonical: raw,
    pageFormat: { widthMm: page.trim[0], heightMm: page.trim[1], columns: page.grid?.cols || 6,
      gutterMm: page.grid?.gutter_mm || 4.5, margins: { top: margin, bottom: margin, left: margin, right: margin } },
    elements: raw.elements.map((element: Data, index: number): SceneGraphElement => ({
      id: element.id, canonical: element, role: roleFromApi[element.role] || element.role,
      storyId: element.content_ref, importance: element.importance,
      frame: { x: element.frame.x, y: element.frame.y, width: element.frame.w, height: element.frame.h },
      zIndex: element.z, content: element.role === 'photo' ? apiUrl(element.image_url || '') : element.text_content || '',
      style: { fontFamily: element.style?.font_family, fontSizePt: element.style?.font_size_pt,
        lineHeightPt: element.style?.line_height_pt, fontWeight: element.style?.font_weight, color: element.style?.color,
        backgroundColor: element.style?.bg_color, borderColor: element.style?.border_color,
        borderWidthPt: (element.style?.border_width_mm || 0) * 72 / 25.4,
        columnCount: element.style?.columns || 1, textAlign: element.style?.align,
        textTransform: element.style?.case === 'upper' ? 'uppercase' : element.style?.case === 'title' ? 'capitalize' : 'none' },
      treatment: { isCutout: element.treatment === 'cutout', maskUrl: apiUrl(element.mask_ref || ''),
        hasTextWrap: element.text_wrap?.mode !== 'none', rotationDeg: element.frame.rotation_deg,
        wrapContour: element.contour_points ? { points: element.contour_points.map((p: number[]) => [p[0] / element.frame.w, p[1] / element.frame.h]),
          offsetMm: element.text_wrap?.offset_mm || 3, mode: 'contour' } : undefined },
      transgressionsApplied: element.transgressions || [], tensionCost: 0,
      readingOrderIndex: raw.reading_order?.indexOf(element.id) ?? index,
    })),
    metadata: { totalTension: raw.metadata?.total_energy ?? raw.metadata?.energy_consumed ?? 0,
      densityRatio: raw.metadata?.density_ratio || 0, collisionsCount: raw.metadata?.collisions_count || 0,
      readingOrderFlowValid: true, estimatedCopyfitPercentage: 100,
      layoutMode: raw.metadata?.layout_mode,
      artDirection: raw.metadata?.art_direction },
  };
}
function sceneToApi(scene: SceneGraph): Data {
  return { ...scene.canonical, page: { ...scene.canonical?.page, trim: [scene.pageFormat.widthMm, scene.pageFormat.heightMm] },
    elements: scene.elements.map(element => ({ ...element.canonical, id: element.id, role: roleToApi[element.role] || element.role,
      importance: element.importance ?? element.canonical?.importance ?? .5, content_ref: element.storyId,
      text_content: element.role === 'image' ? null : element.content,
      image_url: element.role === 'image' ? element.content.replace(/^\/api\//, '/') : element.canonical?.image_url,
      frame: { ...element.canonical?.frame, x: element.frame.x, y: element.frame.y, w: element.frame.width, h: element.frame.height, unit: 'mm' },
      z: element.zIndex,
      style: { ...element.canonical?.style, font_family: element.style.fontFamily,
        font_size_pt: element.style.fontSizePt, line_height_pt: element.style.lineHeightPt,
        font_weight: element.style.fontWeight == null ? undefined : String(element.style.fontWeight),
        color: element.style.color, bg_color: element.style.backgroundColor, border_color: element.style.borderColor,
        border_width_mm: (element.style.borderWidthPt || 0) * 25.4 / 72,
        columns: element.style.columnCount, align: element.style.textAlign,
        case: element.style.textTransform === 'uppercase' ? 'upper' : element.style.textTransform === 'capitalize' ? 'title' : 'normal' },
    })), reading_order: scene.elements.filter(e => e.role !== 'image').sort((a, b) => a.readingOrderIndex - b.readingOrderIndex).map(e => e.id),
  };
}

const MORPHOLOGY_LABELS: Record<string, string> = {
  asymmetric_hero_rail: 'Duże zdjęcie z boczną szyną',
  diagonal_hero_entry: 'Ukośne wejście tytułu w zdjęcie',
  dual_scale_collage: 'Kolaż dwóch zdjęć w różnej skali',
  portrait_cover: 'Okładka portretowa z tekstem w wolnej przestrzeni',
  detail_still_life: 'Detal z przestrzenią negatywną',
  reportage_cover: 'Okładka reportażowa',
  typographic_cover: 'Okładka typograficzna',
  opening_spread: 'Rozkładówka otwierająca',
  listing_pick_top: 'Ramówka z programem dnia na górze',
  listing_pick_bottom: 'Ramówka z programem dnia na dole',
  photo_dominant_strip: 'Dominujące zdjęcie z nieregularnym paskiem',
  directional_tension: 'Kompozycja prowadzona spojrzeniem',
  type_behind_subject: 'Tytuł za wyciętą postacią',
};

export interface PhotoCheckRow {
  story_ref: string; lead?: boolean; status: string; verdict?: string; message?: string; reason?: string;
  score?: number; headline_match?: number; emotion?: string; image_ref?: string;
  alternatives?: { image_ref: string; score: number; reason: string }[];
}
export interface PhotoCheckResult { ready: boolean; message: string; photo_selection: PhotoCheckRow[]; stop: PhotoCheckRow | null }

function buildMaterial(intake: IntakeData, mastheadTitle: string): Data {
  const toStory = (story: IntakeData['leadStory'], lead: boolean) => ({ id: story.id, kicker: story.kicker,
    headline: story.headline, deck: story.deck, lead: story.lead, body: story.body, importance: story.importance / 5,
    images: intake.photos.filter(photo => photo.storyId === story.id || (!photo.storyId && lead)).map(photo => ({
      id: photo.id, url: photo.url.startsWith('/api/') ? photo.url.slice(4) : photo.url, caption: photo.caption,
      credit: photo.credit, focal_point: photo.focalPoint || [0.5, 0.5],
      width_px: photo.widthPx, height_px: photo.heightPx, dpi: photo.dpi })) });
  return { masthead_title: mastheadTitle, page_zone: intake.pageZone || 'front_page',
    editorial_mood: intake.editorialMood || 'auto',
    stories: [toStory(intake.leadStory, true), ...intake.secondaryStories.map(story => toStory(story, false))] };
}

function layoutStoryFromMetadata(meta: Data): Candidate['layoutStory'] {
  const lead = (meta.photo_selection || []).find((row: Data) => row.lead && row.status === 'selected');
  const decisions = (meta.photo_driven_decisions || [])
    .map((row: Data) => row.reason || (row.decision === 'headline_zone' ? `tytuł w strefie: ${row.zone === 'top' ? 'górnej' : 'dolnej'}` : ''))
    .filter(Boolean);
  const morphology = meta.cover_morphology ? MORPHOLOGY_LABELS[meta.cover_morphology] || 'Układ generatywny' : undefined;
  if (!morphology && !lead && !decisions.length) return undefined;
  return { morphology, photoReason: lead?.reason, photoScore: lead?.score, decisions };
}

function candidateFromApi(raw: Data): Candidate {
  const critic = raw.critic;
  const violations: string[] = critic.hard_gate.violations || [];
  const scene = sceneFromApi(raw.scene_graph, raw.id);
  return { id: raw.id, runId: raw.run_id, candidateNumber: raw.rank, sceneGraph: scene,
    thumbnailSvg: raw.svg_thumbnail, previewImageUrl: apiUrl(raw.html_preview_url || `/candidates/${raw.id}/preview`),
    criticScore: critic.total_fitness, tasteScore: critic.preference_score ?? critic.total_fitness,
    visualReview: raw.scene_graph?.metadata?.visual_critique,
    styleReadiness: raw.scene_graph?.metadata?.style_readiness,
    layoutStory: layoutStoryFromMetadata(raw.scene_graph?.metadata || {}),
    passHardGates: critic.hard_gate.passed,
    hardGatesReport: { passed: critic.hard_gate.passed, details: violations,
      collisionsFound: violations.filter(v => /colli|overlap/i.test(v)).length,
      readabilityScore: critic.hard_gate.passed ? 100 : 0,
      prepressOversetLines: violations.filter(v => /overset/i.test(v)).length,
      hierarchyViolations: violations.filter(v => /hierarchy|dominant/i.test(v)).length,
      marginViolations: violations.filter(v => /margin/i.test(v)).length },
    criticRationale: critic.explanation, noveltyDistance: critic.novelty_vs_corpus,
    tensionEnergyConsumed: scene.metadata.totalTension,
    transgressionsCount: scene.elements.reduce((total, element) => total + element.transgressionsApplied.length, 0),
    tags: [], artDirection: raw.scene_graph?.metadata?.art_direction, isBookmarked: raw.selected, createdAt: raw.created_at };
}
function runFromApi(raw: Data): GenerationRun {
  const candidates = raw.candidates.map(candidateFromApi);
  return { id: raw.id, projectId: raw.project_id, timestamp: raw.timestamp,
    status: raw.status === 'pending' ? 'running' : raw.status, candidates,
    requestedCandidateCount: raw.stats?.requested_candidates || raw.stats?.candidates_count || candidates.length,
    bestCandidateId: candidates.find((candidate: Candidate) => candidate.passHardGates)?.id || candidates[0]?.id || '',
    targetTension: raw.stats?.energy_budget_used || 0,
    noveltyMean: candidates.length ? candidates.reduce((sum: number, candidate: Candidate) => sum + candidate.noveltyDistance, 0) / candidates.length : 0,
    elapsedMs: raw.stats?.elapsed_ms || 0 };
}
function corpusFromApi(raw: Data): CorpusPage {
  const features = raw.extracted_features || {};
  const grid = features.grid || {};
  const typography = features.typography || {};
  const path = raw.file_path || '';
  const extension = path.split('.').pop()?.toLowerCase();
  return { id: raw.id, projectId: raw.project_id, fileName: raw.title || path.split('/').pop(),
    fileType: raw.file_type === 'image' ? (extension === 'png' ? 'png' : 'jpg') : raw.file_type,
    fileSize: features.file_size_bytes || 0, pageNumber: features.page_number || 1,
    editionDate: raw.created_at.slice(0, 10),
    thumbnailUrl: apiUrl(raw.thumbnail_url || features.thumbnail_url || `/projects/${raw.project_id}/corpus/${raw.id}/thumbnail`),
    previewUrl: apiUrl(raw.preview_url || features.preview_url || `/projects/${raw.project_id}/corpus/${raw.id}/thumbnail`),
    status: features.error ? 'error' : 'analyzed', widthMm: features.width_mm || features.trim_w_mm || 280,
    heightMm: features.height_mm || features.trim_h_mm || 400,
    boundingBoxes: (features.bounding_boxes || []).map((box: Data) => ({ x: box.x, y: box.y, width: box.w ?? box.width,
      height: box.h ?? box.height, role: box.role, confidence: box.confidence ?? 1 })),
    features: { detectedColumns: features.dominant_columns || features.detected_columns || features.column_count || grid.columns || 0,
      detectedGutterMm: features.gutter_mm || features.detected_gutter_mm || grid.gutter_mm || 0,
      dominantFontFamilies: features.font_families || features.dominant_font_families || typography.font_families || [],
      maxHeadlineSizePt: features.max_headline_pt || features.max_headline_size_pt || typography.max_headline_pt || 0,
      bodyFontSizePt: features.body_font_size_pt || typography.body_size_pt || 0,
      photoRatio: features.photo_coverage_pct != null ? features.photo_coverage_pct / 100 : (features.photo_coverage != null ? features.photo_coverage : features.photo_ratio || 0),
      whiteSpaceRatio: features.whitespace_ratio || features.white_space_ratio || 0,
      transgressionDetected: features.transgressions_detected || [], colorPaletteExtracted: features.color_palette || [],
      noveltyVector: features.vector || [] }, createdAt: raw.created_at, extractionDetails: features };
}
function tasteFromApi(raw: Data): TasteModelMetrics {
  const weights = raw.feature_weights || {};
  return { modelVersion: `v${raw.version}`, lastTrainedAt: raw.updated_at, totalComparisons: raw.sample_count,
    preferenceWinRate: raw.human_preference_win_rate, avgTimeToApproveSec: raw.time_to_approve_avg_iterations,
    heldOutWinRate: raw.held_out_win_rate || 0, evaluatedSampleCount: raw.evaluated_sample_count || 0,
    feedbackCount: raw.feedback_count || raw.sample_count || 0,
    featureWeights: { tensionTolerance: weights.tension_adherence || 0, cutoutAffinity: weights.cutout_affinity || 0,
      whitespaceGenerosity: weights.breathing_space || 0, headlineDominance: weights.rhythm_and_scale || 0,
      asymmetryPreference: weights.visual_balance || 0 }, learningHistory: [] };
}

export const api = {
  async getProjects(): Promise<Project[]> { return (await request<Data[]>('/projects')).map(projectFromApi); },
  async getProject(id: string): Promise<Project> { return projectFromApi(await request(`/projects/${id}`)); },
  async getAIDirectorContract(projectId: string): Promise<Data> { return request(`/projects/${projectId}/ai-director`); },
  async createProject(data: Partial<Project>): Promise<Project> {
    const project = projectFromApi(await request('/projects', json('POST', { name: data.newspaperTitle || data.name,
      description: data.description || '', status: 'ready' })));
    const style = data.editorialCharacter ? editorialStyle(data.editorialCharacter) : undefined;
    if (data.dimensions || data.editorialCharacter) {
      if (style) {
        // Use measured, editable corpus DNA as the base. A local style record
        // below remains a safe fallback if the profile endpoint is unavailable.
        try { await request(`/projects/${project.id}/dna/archetype/${style.archetype}`, { method: 'POST' }); }
        catch { /* the explicit style values below still define the newspaper */ }
      }
      const dna = await this.getTitleDNA(project.id);
      if (data.dimensions) {
        dna.canonical = { ...dna.canonical, format: { ...dna.canonical?.format,
          trim_w_mm: data.dimensions.widthMm, trim_h_mm: data.dimensions.heightMm, bleed_mm: data.dimensions.bleedMm } };
        dna.grid = { ...dna.grid, columns: data.dimensions.columnsCount, gutterMm: data.dimensions.gutterMm,
          marginTopMm: data.dimensions.marginTopMm, marginBottomMm: data.dimensions.marginBottomMm,
          marginLeftMm: data.dimensions.marginLeftMm, marginRightMm: data.dimensions.marginRightMm };
      }
      if (style) {
        dna.archetype = style.archetype;
        dna.styleBlend = { ...style.blend };
        dna.typography.headlinePrimary.fontFamily = style.headlineFont;
        dna.typography.superHeadline.fontFamily = style.headlineFont;
        dna.typography.headlineSecondary.fontFamily = style.headlineFont;
        dna.typography.body.fontFamily = style.bodyFont;
        dna.pageEnergyBudget.maxTensionScore = style.energy;
        dna.pageEnergyBudget.targetTensionScore = style.energy;
      }
      if (data.accentFont) {
        const family = `${data.accentFont}, ${style?.headlineFont || 'Georgia, serif'}`;
        dna.typography.headlinePrimary.fontFamily = family;
        dna.typography.headlineSecondary.fontFamily = family;
        dna.typography.superHeadline.fontFamily = family;
      }
      await this.updateTitleDNA(project.id, dna);
    }
    return { ...project, editorialCharacter: style?.id, accentFont: data.accentFont || '' };
  },
  async deleteProject(id: string): Promise<boolean> { await request(`/projects/${id}`, { method: 'DELETE' }); return true; },
  async getTitleDNA(projectId: string): Promise<TitleDNA> { return dnaFromApi(await request(`/projects/${projectId}/dna`), projectId); },
  async updateTitleDNA(projectId: string, dna: TitleDNA): Promise<TitleDNA> { return dnaFromApi(await request(`/projects/${projectId}/dna`, json('PUT', dnaToApi(dna))), projectId); },
  async learnDNAFromCorpus(projectId: string): Promise<TitleDNA> { return dnaFromApi(await request(`/projects/${projectId}/dna:learn`, { method: 'POST' }), projectId); },
  async getCorpusPages(projectId: string): Promise<CorpusPage[]> { return (await request<Data[]>(`/projects/${projectId}/corpus`)).map(corpusFromApi); },
  async uploadCorpusPage(projectId: string, file: File): Promise<CorpusPage> {
    const form = new FormData(); form.append('file', file); form.append('title', file.name);
    return corpusFromApi(await request(`/projects/${projectId}/corpus`, { method: 'POST', body: form }));
  },
  async importCorpusDirectory(projectId: string, directoryPath: string): Promise<CorpusPage[]> {
    return (await request<Data[]>(`/projects/${projectId}/corpus/directory`, json('POST', { directory_path: directoryPath, recursive: true }))).map(corpusFromApi);
  },
  async deleteCorpusPage(projectId: string, pageId: string): Promise<boolean> { await request(`/projects/${projectId}/corpus/${pageId}`, { method: 'DELETE' }); return true; },
  async getArchetypes(): Promise<Data[]> { return request('/archetypes'); },
  async getArchetype(id: string): Promise<Data> { return request(`/archetypes/${encodeURIComponent(id)}`); },
  async getCorpusIndex(options?: { rebuild?: boolean; root?: string }): Promise<Data> {
    const query = new URLSearchParams();
    if (options?.rebuild) query.set('rebuild', 'true');
    if (options?.root) query.set('root', options.root);
    return request(`/corpus/index${query.toString() ? `?${query}` : ''}`);
  },
  async rebuildCorpusIndex(root?: string, persistPath?: string): Promise<Data> {
    return request('/corpus/index', json('POST', { root, persist_path: persistPath }));
  },
  async getProjectArchetypes(projectId: string): Promise<Data> { return request(`/projects/${projectId}/corpus/archetypes`); },
  async applyArchetype(projectId: string, archetype: string): Promise<TitleDNA> {
    return dnaFromApi(await request(`/projects/${projectId}/dna/archetype/${encodeURIComponent(archetype)}`, { method: 'POST' }), projectId);
  },
  async uploadPhoto(file: File, autoCutout: boolean): Promise<PhotoMaterial> {
    const form = new FormData(); form.append('file', file); form.append('auto_cutout', String(autoCutout));
    const raw = await request('/assets/image', { method: 'POST', body: form });
    return { id: raw.id, url: apiUrl(raw.url), previewUrl: apiUrl(raw.alpha_mask_url || raw.url), caption: '', credit: file.name,
      importance: 5, autoCutout: !!raw.is_cutout_candidate, hasCutoutMask: !!raw.alpha_mask_url, alphaMaskUrl: raw.alpha_mask_url,
      cutoutContourPoints: raw.contour_polygon, aspectRatio: raw.width_px && raw.height_px ? raw.width_px / raw.height_px : undefined,
      placementHint: 'lead-hero', allowTextWrap: true, sourceFile: file, widthPx: raw.width_px ?? undefined,
      heightPx: raw.height_px ?? undefined, dpi: raw.dpi ?? undefined, focalPoint: raw.focal_point || [0.5, 0.5],
      focalStatus: raw.focal_status || 'unavailable', focalSubjectKind: raw.subject_kind || 'uncertain' };
  },
  async ingestUrl(url: string, autoCutout = true, projectId?: string): Promise<{ leadStory: StoryMaterial; photos: PhotoMaterial[]; source: any }> {
    const raw = await request('/editorial/ingest-url', json('POST', { url, auto_cutout: autoCutout, project_id: projectId }));
    return {
      leadStory: raw.leadStory,
      photos: (raw.photos || []).map((p: any) => ({
        ...p,
        url: apiUrl(p.url),
        previewUrl: apiUrl(p.previewUrl || p.url),
        alphaMaskUrl: p.alphaMaskUrl ? apiUrl(p.alphaMaskUrl) : undefined,
      })),
      source: raw.source,
    };
  },
  async ingestFile(file: File, autoCutout = true, projectId?: string): Promise<{ leadStory: StoryMaterial; photos: PhotoMaterial[]; source: any }> {
    const form = new FormData();
    form.append('file', file);
    form.append('auto_cutout', String(autoCutout));
    if (projectId) form.append('project_id', projectId);
    const raw = await request('/editorial/ingest-file', { method: 'POST', body: form });
    return {
      leadStory: raw.leadStory,
      photos: (raw.photos || []).map((p: any) => ({
        ...p,
        url: apiUrl(p.url),
        previewUrl: apiUrl(p.previewUrl || p.url),
        alphaMaskUrl: p.alphaMaskUrl ? apiUrl(p.alphaMaskUrl) : undefined,
      })),
      source: raw.source,
    };
  },
  async redactText(text: string, title?: string, projectId?: string): Promise<{ leadStory: StoryMaterial }> {
    const raw = await request('/editorial/redact-text', json('POST', { text, title, project_id: projectId }));
    return {
      leadStory: raw.leadStory,
    };
  },
  async checkPhotos(projectId: string, intake: IntakeData): Promise<PhotoCheckResult> {
    const project = await this.getProject(projectId);
    return request(`/projects/${projectId}/photo-check`, json('POST', { material: buildMaterial(intake, project.newspaperTitle) }));
  },
  async generateCandidates(projectId: string, intake: IntakeData): Promise<GenerationRun> {
    const toStory = (story: IntakeData['leadStory'], lead: boolean) => ({ id: story.id, kicker: story.kicker,
      headline: story.headline, deck: story.deck, lead: story.lead, body: story.body, byline: story.byline,
      pullquote: story.pullQuote, importance: story.importance / 5,
      images: intake.photos.filter(photo => photo.storyId === story.id || (!photo.storyId && lead)).map(photo => ({
        id: photo.id, url: photo.url.startsWith('/api/') ? photo.url.slice(4) : photo.url, caption: photo.caption, credit: photo.credit, importance: photo.importance / 5,
        is_cutout_candidate: intake.generationConfig.allowCutouts && photo.autoCutout,
        alpha_mask_url: photo.alphaMaskUrl, has_alpha_mask: photo.hasCutoutMask || false,
        contour_polygon: photo.cutoutContourPoints, aspect_ratio: photo.aspectRatio, focal_point: photo.focalPoint || [0.5, 0.5],
        width_px: photo.widthPx, height_px: photo.heightPx, dpi: photo.dpi })) });
    const project = await this.getProject(projectId);
    return runFromApi(await request(`/projects/${projectId}/generate`, json('POST', {
      material: { issue_date: intake.editionDate, issue_number: String(intake.pageNumber), section_name: intake.section,
        masthead_title: project.newspaperTitle, stories: [toStory(intake.leadStory, true), ...intake.secondaryStories.map(story => toStory(story, false))],
        page_zone: intake.pageZone || 'front_page', page_topic: intake.pageTopic || 'general',
        editorial_mood: intake.editorialMood || 'auto', style_blend: intake.styleBlend,
        tv_schedule: intake.tvSchedule || [],
        copy_mode: intake.generationConfig.placeholderCopy ? 'placeholder' : 'source' },
      num_candidates: intake.generationConfig.candidateCount, energy_budget_override: intake.generationConfig.tensionTarget,
      population_size: Math.round(12 + intake.generationConfig.explorationTemp * 14), generations: 3,
      allow_transgressions: intake.generationConfig.tensionTarget > 0,
      prioritize_novelty: intake.generationConfig.prioritizeNovelty,
      // The editor can turn off the external visual review in the form.
      visual_review: intake.generationConfig.visualReview ?? false,
      copy_review: intake.generationConfig.copyReview ?? true,
      accept_weak_photos: intake.generationConfig.acceptWeakPhotos ?? false,
      style_blend: intake.styleBlend, page_zone: intake.pageZone || 'front_page', seed: intake.seed,
    })));
  },
  async generateFromPlan(projectId: string, payload: { stories: Data[]; pagePlan: Data | null; issueDate: string; issueNumber: string;
    section: string; candidates?: number; pageZone?: string }): Promise<GenerationRun> {
    const project = await this.getProject(projectId);
    return runFromApi(await request(`/projects/${projectId}/generate`, json('POST', {
      material: { issue_date: payload.issueDate, issue_number: payload.issueNumber, section_name: payload.section,
        masthead_title: project.newspaperTitle, stories: payload.stories, page_zone: payload.pageZone || 'front_page',
        page_plan: payload.pagePlan },
      page_plan: payload.pagePlan, num_candidates: payload.candidates || 4, population_size: 20, generations: 6,
      page_zone: payload.pageZone || 'front_page', visual_review: false,
    })));
  },
  async generateFramedCover(projectId: string, options: { kitName?: string; genes?: Data; material?: Data } = {}): Promise<Candidate> {
    const raw = await request(`/projects/${projectId}/framed-cover`, json('POST', {
      kit_name: options.kitName || 'wukadka', genes: options.genes, material: options.material,
    }));
    return candidateFromApi(raw);
  },
  async executeArtDirect(projectId: string, options: { composer?: string; rounds?: number; resume?: boolean; step?: number; genes?: Data; material?: Data } = {}): Promise<GenerationRun> {
    const raw = await request(`/projects/${projectId}/art-direct`, json('POST', options));
    return runFromApi(raw);
  },
  async applyArtDirectFixes(projectId: string, fixes: string[], genes: Data, composer = 'framed_cover:wukadka'): Promise<Candidate> {
    const raw = await request(`/projects/${projectId}/art-direct/apply-fixes`, json('POST', { fixes, genes, composer }));
    return candidateFromApi(raw);
  },
  async getGenerationRuns(projectId: string): Promise<GenerationRun[]> { return (await request<Data[]>(`/projects/${projectId}/runs`)).map(runFromApi); },
  async getCandidate(id: string): Promise<Candidate> { return candidateFromApi(await request(`/candidates/${id}`)); },
  async saveCandidate(id: string, scene: SceneGraph): Promise<Candidate> { return candidateFromApi(await request(`/candidates/${id}`, json('PUT', sceneToApi(scene)))); },
  async fitCandidateCopy(candidateId: string, elementRef: string, options: { text?: string; targetWords?: number; lockedPassages?: string[] } = {}): Promise<FrameCopyFit> {
    return request(`/candidates/${candidateId}/copy/fit`, json('POST', {
      element_ref: elementRef, text: options.text, target_words: options.targetWords,
      locked_passages: options.lockedPassages || [],
    }));
  },
  async submitPreference(signal: PreferenceSignal): Promise<{ ok: boolean; updatedMetrics: TasteModelMetrics }> {
    const deltas = signal.userDeltaEdits || [];
    const deltaFeatures = deltas.reduce<Record<string, number>>((result, delta) => {
      result.move_mm = (result.move_mm || 0) + Math.hypot(delta.newFrame.x - delta.previousFrame.x, delta.newFrame.y - delta.previousFrame.y);
      result.resize_mm = (result.resize_mm || 0) + Math.abs(delta.newFrame.width - delta.previousFrame.width) + Math.abs(delta.newFrame.height - delta.previousFrame.height);
      if (delta.changeType === 'style') result.style_edits = (result.style_edits || 0) + 1;
      return result;
    }, {});
    await request(`/projects/${signal.projectId}/preferences`, json('POST', { project_id: signal.projectId,
      signal_type: signal.type === 'pairwise_choice' ? 'pairwise_comparison' : signal.type === 'manual_delta' ? 'manual_edit_delta' : 'selection',
      winner_candidate_id: signal.winnerCandidateId,
      loser_candidate_id: signal.type === 'pairwise_choice' ? (signal.candidateAId === signal.winnerCandidateId ? signal.candidateBId : signal.candidateAId) : null,
      delta_features: deltas.length ? deltaFeatures : null, notes: signal.feedbackNotes,
      review_duration_sec: signal.reviewDurationSec,
    }));
    return { ok: true, updatedMetrics: await this.getTasteMetrics(signal.projectId) };
  },
  async logEditDelta(projectId: string, candidateId: string, deltas: ElementDelta[]): Promise<boolean> {
    await this.submitPreference({ id: '', projectId, type: 'manual_delta', candidateAId: candidateId, winnerCandidateId: candidateId,
      userDeltaEdits: deltas, timestamp: new Date().toISOString() }); return true;
  },
  async getPairwiseCandidates(projectId: string, composer = 'framed_cover:wukadka'): Promise<{
    pair_id: string;
    composer: string;
    archetype: string;
    candidate_a: Candidate;
    candidate_b: Candidate;
    features_a: Record<string, number>;
    features_b: Record<string, number>;
  }> {
    const raw = await request<Data>(`/projects/${projectId}/pairs?composer=${encodeURIComponent(composer)}`);
    return {
      pair_id: raw.pair_id,
      composer: raw.composer,
      archetype: raw.archetype,
      candidate_a: candidateFromApi(raw.candidate_a),
      candidate_b: candidateFromApi(raw.candidate_b),
      features_a: raw.features_a || {},
      features_b: raw.features_b || {},
    };
  },
  async submitPairwiseVote(projectId: string, payload: {
    pair_id: string;
    candidate_a_id: string;
    candidate_b_id: string;
    winner: 'A' | 'B' | 'tie';
    notes?: string;
    features_a?: Record<string, number>;
    features_b?: Record<string, number>;
    archetype?: string;
  }): Promise<Data> {
    return request(`/projects/${projectId}/pairs/vote`, json('POST', payload));
  },
  async getPairwiseCalibrationStatus(projectId: string): Promise<Data> {
    return request(`/projects/${projectId}/pairs/status`);
  },
  async forceRecalibrateTaste(projectId: string): Promise<Data> {
    return request(`/projects/${projectId}/pairs/calibrate`, { method: 'POST' });
  },
  async cutoutPhoto(projectId: string, fileOrUrl: { file?: File; imageUrl?: string; assetId?: string }): Promise<Data> {
    if (fileOrUrl.file) {
      const form = new FormData();
      form.append('file', fileOrUrl.file);
      return request(`/projects/${projectId}/cutout`, { method: 'POST', body: form });
    }
    return request(`/projects/${projectId}/cutout`, json('POST', {
      image_url: fileOrUrl.imageUrl,
      asset_id: fileOrUrl.assetId,
    }));
  },
  async getTasteMetrics(projectId: string): Promise<TasteModelMetrics> { return tasteFromApi(await request(`/projects/${projectId}/taste-model`)); },
  async exportCandidate(id: string, options: ExportOptions): Promise<ExportArtifact> {
    const raw = await request(`/candidates/${id}/export?format=${options.format}`, json('POST', options));
    return { id: raw.id, projectId: raw.project_id, candidateId: raw.candidate_id, format: raw.format,
      fileName: raw.file_path.split('/').pop(), downloadUrl: apiUrl(`/exports/${raw.id}/download`),
      fileSizeBytes: raw.file_size_bytes, createdAt: raw.created_at, options };
  },
  // Editorial/content contracts.  These methods deliberately return the
  // structured server records so a future Content Studio can render claims,
  // approvals, copy variants and revision history without a second API layer.
  async createIssue(projectId: string, issue: Data): Promise<Data> { return request(`/projects/${projectId}/issues`, json('POST', issue)); },
  async createSource(issueId: string, source: Data): Promise<Data> { return request(`/issues/${issueId}/sources`, json('POST', source)); },
  async createBrief(issueId: string, brief: Data): Promise<Data> { return request(`/issues/${issueId}/briefs`, json('POST', brief)); },
  async autoPlanIssue(issueId: string, variant = 'standard'): Promise<Data> { return request(`/issues/${issueId}/plan/auto`, json('POST', { variant })); },
  async generateIssueLayouts(issueId: string, options: Data = {}): Promise<GenerationRun> {
    return runFromApi(await request(`/issues/${issueId}/generate-layouts`, json('POST', options)));
  },
  async createStory(issueId: string, story: Data): Promise<Data> { return request(`/issues/${issueId}/stories`, json('POST', story)); },
  async generateCopyVariants(storyId: string, roles?: string[]): Promise<Data[]> { return request(`/stories/${storyId}/generate-variants`, json('POST', { roles })); },
  async approveStory(storyId: string): Promise<Data> { return request(`/stories/${storyId}/approve`, { method: 'POST' }); },
  async lockStoryPassage(storyId: string, passage: string, locked = true): Promise<Data> {
    return request(`/stories/${storyId}/lock`, json('POST', { passage, locked }));
  },
  async translateStory(storyId: string, targetLanguage: string, role = 'body', text?: string): Promise<Data> {
    return request(`/stories/${storyId}/translate`, json('POST', { target_language: targetLanguage, role, text }));
  },
  async factcheckStory(storyId: string): Promise<Data> { return request(`/stories/${storyId}/factcheck`, { method: 'POST' }); },
  async createTextPlan(plan: Data): Promise<Data> { return request('/text-plans', json('POST', plan)); },
  async fitTextPlan(planId: string, textValue: string, variantRef?: string): Promise<Data> { return request(`/text-plans/${planId}/fit`, json('POST', { text: textValue, variant_ref: variantRef })); },
  async getIssueManifest(issueId: string): Promise<Data> { return request(`/issues/${issueId}/manifest`); },
  async createEditorialEdition(pages = 16, imposition = 8, issueDate?: string): Promise<Data> {
    return request('/editorial-model/editions', json('POST', { pages, imposition, issue_date: issueDate }));
  },
  async getProjectEditorialEdition(projectId: string): Promise<Data> {
    return request(`/editorial-model/projects/${encodeURIComponent(projectId)}/edition`);
  },
  async saveProjectEditorialEdition(projectId: string, edition: Data): Promise<Data> {
    return request(`/editorial-model/projects/${encodeURIComponent(projectId)}/edition`, json('POST', { edition }));
  },
  async addEditorialAds(projectId: string, pageNo: number, ads: Data[] = [], csv?: string, removed: string[] = []): Promise<Data> {
    return request(`/editorial-model/projects/${encodeURIComponent(projectId)}/edition/ads`, json('POST', { page_no: pageNo, ads, csv, removed }));
  },
  async addEditionShort(projectId: string, pageNo: number, item: Data, waiting = false): Promise<Data> {
    return request(`/editorial-model/projects/${encodeURIComponent(projectId)}/edition/shorts`, json('POST', { page_no: pageNo, item, waiting }));
  },
  async validateEditorialEdition(payload: Data): Promise<Data> {
    return request('/editorial-model/editions/validate', json('POST', payload));
  },
  async preflightCandidate(candidateId: string): Promise<Data> { return request(`/candidates/${candidateId}/preflight`, { method: 'POST' }); },
};
