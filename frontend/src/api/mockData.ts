import { Project } from '../types/project';
import { TitleDNA } from '../types/dna';
import { CorpusPage } from '../types/corpus';
import { GenerationRun, Candidate } from '../types/generation';
import { TasteModelMetrics, PreferenceSignal } from '../types/taste';
import { SceneGraph } from '../types/sceneGraph';

export const INITIAL_PROJECTS: Project[] = [
  {
    id: 'proj-gazeta-codzienna',
    name: 'Gazeta Codzienna',
    slug: 'gazeta-codzienna',
    newspaperTitle: 'GAZETA CODZIENNA',
    editionCode: 'WARSAW-ED01',
    format: 'berliner',
    dimensions: {
      widthMm: 315,
      heightMm: 470,
      columnsCount: 5,
      gutterMm: 4.5,
      marginTopMm: 16,
      marginBottomMm: 20,
      marginLeftMm: 14,
      marginRightMm: 14,
      bleedMm: 3,
    },
    description: 'National daily broadsheet-berliner format with dynamic editorial lead stories, expressive kickers and cut-out product/photo anchors.',
    status: 'ready',
    corpusCount: 6,
    generationRunsCount: 14,
    tasteSignalsCount: 42,
    tasteModelWinRate: 0.89,
    avgTimeToApproveSec: 18.4,
    dnaVersion: 4,
    createdAt: '2026-08-15T08:00:00Z',
    updatedAt: '2026-09-01T10:30:00Z',
    themeColor: '#c1121f',
    accentFont: 'Fraunces',
  },
  {
    id: 'proj-metropolitan-chronicle',
    name: 'The Metropolitan Chronicle',
    slug: 'the-metropolitan-chronicle',
    newspaperTitle: 'THE METROPOLITAN CHRONICLE',
    editionCode: 'NY-MAIN-04',
    format: 'broadsheet',
    dimensions: {
      widthMm: 375,
      heightMm: 560,
      columnsCount: 6,
      gutterMm: 4.0,
      marginTopMm: 20,
      marginBottomMm: 24,
      marginLeftMm: 18,
      marginRightMm: 18,
      bleedMm: 5,
    },
    description: 'High-density international broadsheet with classical typography hierarchy, multi-deck headlines and asymmetrical grid tension.',
    status: 'ready',
    corpusCount: 8,
    generationRunsCount: 9,
    tasteSignalsCount: 28,
    tasteModelWinRate: 0.84,
    avgTimeToApproveSec: 24.1,
    dnaVersion: 3,
    createdAt: '2026-08-20T11:00:00Z',
    updatedAt: '2026-08-30T14:15:00Z',
    themeColor: '#003049',
    accentFont: 'Playfair Display',
  },
  {
    id: 'proj-nordic-dispatch',
    name: 'Nordic Morning Dispatch',
    slug: 'nordic-morning-dispatch',
    newspaperTitle: 'NORDIC MORNING DISPATCH',
    editionCode: 'CPH-TAB-01',
    format: 'tabloid',
    dimensions: {
      widthMm: 280,
      heightMm: 400,
      columnsCount: 4,
      gutterMm: 5.0,
      marginTopMm: 14,
      marginBottomMm: 16,
      marginLeftMm: 12,
      marginRightMm: 12,
      bleedMm: 3,
    },
    description: 'Clean Scandinavian editorial design with airy margins, heavy sans kickers, and bold photographic silhouettes.',
    status: 'ready',
    corpusCount: 4,
    generationRunsCount: 5,
    tasteSignalsCount: 15,
    tasteModelWinRate: 0.92,
    avgTimeToApproveSec: 14.8,
    dnaVersion: 2,
    createdAt: '2026-08-26T09:00:00Z',
    updatedAt: '2026-08-31T16:00:00Z',
    themeColor: '#2d6a4f',
    accentFont: 'Barlow Semi Condensed',
  }
];

export const INITIAL_DNA_MAP: Record<string, TitleDNA> = {
  'proj-gazeta-codzienna': {
    id: 'dna-gazeta-01',
    projectId: 'proj-gazeta-codzienna',
    version: 4,
    updatedAt: '2026-08-31T18:20:00Z',
    grid: {
      columns: 5,
      columnWidthMm: 53.8,
      gutterMm: 4.5,
      baselineGridPt: 11,
      marginTopMm: 16,
      marginBottomMm: 20,
      marginLeftMm: 14,
      marginRightMm: 14,
      subdivision: 2,
    },
    typography: {
      superHeadline: { fontFamily: 'Fraunces', weight: 800, sizePt: 54, lineHeightPt: 52, color: '#0b0f14' },
      headlinePrimary: { fontFamily: 'Fraunces', weight: 700, sizePt: 40, lineHeightPt: 39, color: '#0b0f14' },
      headlineSecondary: { fontFamily: 'Playfair Display', weight: 700, sizePt: 26, lineHeightPt: 27, color: '#151b22' },
      kicker: { fontFamily: 'Barlow Semi Condensed', weight: 800, sizePt: 12, lineHeightPt: 13, letterSpacingPt: 1.5, textTransform: 'uppercase', color: '#c1121f' },
      deck: { fontFamily: 'Inter', weight: 500, sizePt: 14, lineHeightPt: 18, color: '#343e49' },
      lead: { fontFamily: 'Playfair Display', weight: 600, sizePt: 11.5, lineHeightPt: 15, color: '#151b22' },
      body: { fontFamily: 'Inter', weight: 400, sizePt: 9.2, lineHeightPt: 12.2, color: '#232b34' },
      byline: { fontFamily: 'Inter', weight: 600, sizePt: 8.5, lineHeightPt: 10, textTransform: 'uppercase', color: '#5a6979' },
      caption: { fontFamily: 'Inter', weight: 400, sizePt: 8.0, lineHeightPt: 10.5, color: '#5a6979' },
      pullQuote: { fontFamily: 'Fraunces', weight: 700, sizePt: 22, lineHeightPt: 26, color: '#c1121f' },
      folio: { fontFamily: 'Barlow Semi Condensed', weight: 700, sizePt: 9.0, lineHeightPt: 10, letterSpacingPt: 1, textTransform: 'uppercase', color: '#7e8e9e' },
    },
    palette: {
      colors: [
        { name: 'Pitch Black Ink', hex: '#0b0f14', cmyk: '0/0/0/100', role: 'ink' },
        { name: 'Editorial Vermilion', hex: '#c1121f', cmyk: '0/98/95/15', role: 'accent' },
        { name: 'Ochre Tint Box', hex: '#fdf7ee', cmyk: '0/2/7/1', role: 'tint' },
        { name: 'Warm Newsprint Paper', hex: '#f9f6ef', cmyk: '0/1/4/2', role: 'paper' },
        { name: 'Hairline Rule Gray', hex: '#232b34', cmyk: '0/0/0/85', role: 'rule' },
      ],
      backgroundTone: '#f9f6ef',
      ruleColor: '#232b34',
      dominantInk: '#0b0f14',
    },
    photos: {
      allowedCutouts: true,
      minAspectRatio: 0.6,
      maxAspectRatio: 2.2,
      preferredPlacements: ['lead-hero', 'top-banner', 'floating-island'],
      wrapPaddingMm: 4.0,
      borderRulePt: 0.5,
      duotoneAccent: false,
    },
    transgressionCatalog: [
      {
        id: 'transgression-col-bleed',
        name: 'Column Span Break (1.5x / 2.5x cols)',
        description: 'Allows headlines and photos to break standard grid boundaries by fractional increments.',
        allowed: true,
        cost: 2.0,
        maxPerSpread: 3,
        triggerCondition: 'Story importance >= 4',
      },
      {
        id: 'transgression-photo-overlap',
        name: 'Silhouette Cutout Text Wrap Overlap',
        description: 'Photo cutout silhouette protrudes into adjacent text column with dynamic contour wrap.',
        allowed: true,
        cost: 3.5,
        maxPerSpread: 2,
        triggerCondition: 'Photo marked with autoCutout=true',
      },
      {
        id: 'transgression-deck-reversal',
        name: 'Dark Inversion Box / Lead Tint Anchor',
        description: 'Sidebar story enclosed in high-contrast shaded background with inverted kicker.',
        allowed: true,
        cost: 1.5,
        maxPerSpread: 1,
        triggerCondition: 'Sidebar story present',
      },
      {
        id: 'transgression-kicker-overhang',
        name: 'Overhanging Kicker Top Bleed',
        description: 'Kicker tab hangs above top margin rule for immediate visual punch.',
        allowed: true,
        cost: 1.0,
        maxPerSpread: 2,
        triggerCondition: 'Lead story only',
      }
    ],
    pageEnergyBudget: {
      maxTensionScore: 12.0,
      targetTensionScore: 7.0,
      punishExceeding: true,
    },
    corpusMetrics: {
      pagesAnalyzed: 6,
      avgDensity: 0.76,
      dominantColumnUsage: [5, 4, 3, 2],
      avgHeadlineToBodyRatio: 0.28,
      detectedBleedRate: 0.33,
    },
  },
  'proj-metropolitan-chronicle': {
    id: 'dna-metro-01',
    projectId: 'proj-metropolitan-chronicle',
    version: 3,
    updatedAt: '2026-08-29T15:00:00Z',
    grid: {
      columns: 6,
      columnWidthMm: 53.0,
      gutterMm: 4.0,
      baselineGridPt: 10,
      marginTopMm: 20,
      marginBottomMm: 24,
      marginLeftMm: 18,
      marginRightMm: 18,
      subdivision: 2,
    },
    typography: {
      superHeadline: { fontFamily: 'Playfair Display', weight: 900, sizePt: 60, lineHeightPt: 58, color: '#0b0f14' },
      headlinePrimary: { fontFamily: 'Playfair Display', weight: 700, sizePt: 44, lineHeightPt: 42, color: '#0b0f14' },
      headlineSecondary: { fontFamily: 'Playfair Display', weight: 600, sizePt: 28, lineHeightPt: 30, color: '#151b22' },
      kicker: { fontFamily: 'Inter', weight: 700, sizePt: 11, lineHeightPt: 12, letterSpacingPt: 2.0, textTransform: 'uppercase', color: '#003049' },
      deck: { fontFamily: 'Georgia', weight: 400, sizePt: 15, lineHeightPt: 20, color: '#343e49' },
      lead: { fontFamily: 'Playfair Display', weight: 500, sizePt: 12, lineHeightPt: 16, color: '#151b22' },
      body: { fontFamily: 'Georgia', weight: 400, sizePt: 9.5, lineHeightPt: 12.5, color: '#232b34' },
      byline: { fontFamily: 'Inter', weight: 600, sizePt: 8.5, lineHeightPt: 11, textTransform: 'uppercase', color: '#5a6979' },
      caption: { fontFamily: 'Inter', weight: 400, sizePt: 8.0, lineHeightPt: 10.5, color: '#5a6979' },
      pullQuote: { fontFamily: 'Playfair Display', weight: 700, sizePt: 24, lineHeightPt: 28, color: '#003049' },
      folio: { fontFamily: 'Inter', weight: 600, sizePt: 9.0, lineHeightPt: 11, letterSpacingPt: 1.2, textTransform: 'uppercase', color: '#7e8e9e' },
    },
    palette: {
      colors: [
        { name: 'Rich Black Ink', hex: '#0a0d10', cmyk: '0/0/0/100', role: 'ink' },
        { name: 'Deep Heraldic Navy', hex: '#003049', cmyk: '100/60/20/40', role: 'accent' },
        { name: 'Linen Parchment', hex: '#fbf8f2', cmyk: '0/1/3/1', role: 'paper' },
        { name: 'Classic Column Rule', hex: '#1e242c', cmyk: '0/0/0/80', role: 'rule' },
      ],
      backgroundTone: '#fbf8f2',
      ruleColor: '#1e242c',
      dominantInk: '#0a0d10',
    },
    photos: {
      allowedCutouts: false,
      minAspectRatio: 0.7,
      maxAspectRatio: 2.0,
      preferredPlacements: ['lead-hero', 'sidebar'],
      wrapPaddingMm: 3.5,
      borderRulePt: 0.75,
      duotoneAccent: false,
    },
    transgressionCatalog: [
      {
        id: 'transgression-asym-drop',
        name: 'Asymmetric 3-to-2 Column Drop',
        description: 'Headline stretches over 3 columns while body resolves neatly into 2 wider columns below.',
        allowed: true,
        cost: 2.0,
        maxPerSpread: 2,
        triggerCondition: 'Story importance >= 4',
      }
    ],
    pageEnergyBudget: {
      maxTensionScore: 8.0,
      targetTensionScore: 4.0,
      punishExceeding: true,
    },
    corpusMetrics: {
      pagesAnalyzed: 8,
      avgDensity: 0.82,
      dominantColumnUsage: [6, 3, 2],
      avgHeadlineToBodyRatio: 0.22,
      detectedBleedRate: 0.12,
    },
  },
  'proj-nordic-dispatch': {
    id: 'dna-nordic-01',
    projectId: 'proj-nordic-dispatch',
    version: 2,
    updatedAt: '2026-08-31T12:00:00Z',
    grid: {
      columns: 4,
      columnWidthMm: 60.0,
      gutterMm: 5.0,
      baselineGridPt: 11,
      marginTopMm: 14,
      marginBottomMm: 16,
      marginLeftMm: 12,
      marginRightMm: 12,
      subdivision: 2,
    },
    typography: {
      superHeadline: { fontFamily: 'Barlow Semi Condensed', weight: 800, sizePt: 48, lineHeightPt: 46, color: '#0b0f14' },
      headlinePrimary: { fontFamily: 'Barlow Semi Condensed', weight: 700, sizePt: 36, lineHeightPt: 35, color: '#0b0f14' },
      headlineSecondary: { fontFamily: 'Inter', weight: 700, sizePt: 22, lineHeightPt: 24, color: '#151b22' },
      kicker: { fontFamily: 'Inter', weight: 800, sizePt: 10, lineHeightPt: 11, letterSpacingPt: 1.8, textTransform: 'uppercase', color: '#2d6a4f' },
      deck: { fontFamily: 'Inter', weight: 500, sizePt: 13, lineHeightPt: 17, color: '#343e49' },
      lead: { fontFamily: 'Inter', weight: 600, sizePt: 11, lineHeightPt: 15, color: '#151b22' },
      body: { fontFamily: 'Inter', weight: 400, sizePt: 9.0, lineHeightPt: 12.0, color: '#232b34' },
      byline: { fontFamily: 'Inter', weight: 600, sizePt: 8.0, lineHeightPt: 10, textTransform: 'uppercase', color: '#5a6979' },
      caption: { fontFamily: 'Inter', weight: 400, sizePt: 8.0, lineHeightPt: 10.0, color: '#5a6979' },
      pullQuote: { fontFamily: 'Barlow Semi Condensed', weight: 800, sizePt: 22, lineHeightPt: 25, color: '#2d6a4f' },
      folio: { fontFamily: 'Inter', weight: 600, sizePt: 8.5, lineHeightPt: 10, letterSpacingPt: 1.0, textTransform: 'uppercase', color: '#7e8e9e' },
    },
    palette: {
      colors: [
        { name: 'Nordic Charcoal', hex: '#111519', cmyk: '0/0/0/95', role: 'ink' },
        { name: 'Pine Forest Green', hex: '#2d6a4f', cmyk: '80/30/70/30', role: 'accent' },
        { name: 'Pure White Newsprint', hex: '#fdfdfd', cmyk: '0/0/0/0', role: 'paper' },
        { name: 'Minimal Border Line', hex: '#d7dce0', cmyk: '0/0/0/15', role: 'rule' },
      ],
      backgroundTone: '#fdfdfd',
      ruleColor: '#d7dce0',
      dominantInk: '#111519',
    },
    photos: {
      allowedCutouts: true,
      minAspectRatio: 0.8,
      maxAspectRatio: 2.4,
      preferredPlacements: ['top-banner', 'lead-hero'],
      wrapPaddingMm: 5.0,
      borderRulePt: 0.0,
      duotoneAccent: true,
    },
    transgressionCatalog: [
      {
        id: 'transgression-full-width-kicker',
        name: 'Full Bleed Contrast Kicker Bar',
        description: 'Solid accent color band running across the top header of the spread.',
        allowed: true,
        cost: 1.0,
        maxPerSpread: 1,
        triggerCondition: 'Breaking news tag',
      }
    ],
    pageEnergyBudget: {
      maxTensionScore: 10.0,
      targetTensionScore: 5.0,
      punishExceeding: true,
    },
    corpusMetrics: {
      pagesAnalyzed: 4,
      avgDensity: 0.68,
      dominantColumnUsage: [4, 2],
      avgHeadlineToBodyRatio: 0.32,
      detectedBleedRate: 0.5,
    },
  }
};

export const INITIAL_CORPUS_MAP: Record<string, CorpusPage[]> = {
  'proj-gazeta-codzienna': [
    {
      id: 'corpus-gc-01',
      projectId: 'proj-gazeta-codzienna',
      fileName: 'gazeta_codzienna_2026_08_01_p01.pdf',
      fileType: 'pdf',
      fileSize: 4200100,
      pageNumber: 1,
      editionDate: '2026-08-01',
      thumbnailUrl: '/editions/gazeta-codzienna/thumb-01.jpg',
      previewUrl: '/editions/gazeta-codzienna/preview-01.jpg',
      status: 'analyzed',
      widthMm: 315,
      heightMm: 470,
      boundingBoxes: [
        { x: 14, y: 16, width: 287, height: 28, role: 'masthead', confidence: 0.99 },
        { x: 14, y: 48, width: 287, height: 10, role: 'kicker', confidence: 0.98 },
        { x: 14, y: 60, width: 200, height: 42, role: 'headline', confidence: 0.97 },
        { x: 14, y: 104, width: 172, height: 18, role: 'deck', confidence: 0.95 },
        { x: 190, y: 60, width: 111, height: 120, role: 'image', confidence: 0.99 },
        { x: 14, y: 124, width: 172, height: 160, role: 'body', confidence: 0.96 },
        { x: 14, y: 290, width: 287, height: 160, role: 'body', confidence: 0.94 },
      ],
      features: {
        detectedColumns: 5,
        detectedGutterMm: 4.5,
        dominantFontFamilies: ['Fraunces', 'Inter', 'Barlow Semi Condensed'],
        maxHeadlineSizePt: 54,
        bodyFontSizePt: 9.2,
        photoRatio: 0.28,
        whiteSpaceRatio: 0.16,
        transgressionDetected: ['Column Span Break', 'Silhouette Cutout Text Wrap'],
        colorPaletteExtracted: ['#0b0f14', '#c1121f', '#f9f6ef'],
        noveltyVector: [0.34, 0.78, 0.45, 0.92, 0.11, 0.65],
      },
      createdAt: '2026-08-15T08:15:00Z',
    },
    {
      id: 'corpus-gc-02',
      projectId: 'proj-gazeta-codzienna',
      fileName: 'gazeta_codzienna_2026_08_02_p03.pdf',
      fileType: 'pdf',
      fileSize: 3890000,
      pageNumber: 3,
      editionDate: '2026-08-02',
      thumbnailUrl: '/editions/gazeta-codzienna/thumb-02.jpg',
      previewUrl: '/editions/gazeta-codzienna/preview-02.jpg',
      status: 'analyzed',
      widthMm: 315,
      heightMm: 470,
      features: {
        detectedColumns: 5,
        detectedGutterMm: 4.5,
        dominantFontFamilies: ['Fraunces', 'Playfair Display', 'Inter'],
        maxHeadlineSizePt: 42,
        bodyFontSizePt: 9.2,
        photoRatio: 0.22,
        whiteSpaceRatio: 0.18,
        transgressionDetected: ['Dark Inversion Box'],
        colorPaletteExtracted: ['#0b0f14', '#c1121f', '#fdf7ee'],
        noveltyVector: [0.41, 0.65, 0.52, 0.81, 0.24, 0.70],
      },
      boundingBoxes: [
        { x: 14, y: 16, width: 287, height: 12, role: 'folio', confidence: 0.99 },
        { x: 14, y: 32, width: 172, height: 35, role: 'headline', confidence: 0.96 },
        { x: 190, y: 32, width: 111, height: 90, role: 'image', confidence: 0.98 },
        { x: 14, y: 70, width: 172, height: 180, role: 'body', confidence: 0.95 },
      ],
      createdAt: '2026-08-15T08:30:00Z',
    },
  ]
};

export const INITIAL_TASTE_METRICS: Record<string, TasteModelMetrics> = {
  'proj-gazeta-codzienna': {
    modelVersion: 'v2.4-dpo-ranker',
    lastTrainedAt: '2026-09-01T09:45:00Z',
    totalComparisons: 42,
    preferenceWinRate: 0.89,
    avgTimeToApproveSec: 18.4,
    heldOutWinRate: 0.78,
    evaluatedSampleCount: 9,
    feedbackCount: 42,
    featureWeights: {
      tensionTolerance: 0.78,
      cutoutAffinity: 0.92,
      whitespaceGenerosity: 0.65,
      headlineDominance: 0.88,
      asymmetryPreference: 0.74,
    },
    learningHistory: [
      { date: '2026-08-18', winRate: 0.62, approvalsCount: 5 },
      { date: '2026-08-22', winRate: 0.71, approvalsCount: 12 },
      { date: '2026-08-26', winRate: 0.80, approvalsCount: 24 },
      { date: '2026-08-29', winRate: 0.85, approvalsCount: 33 },
      { date: '2026-09-01', winRate: 0.89, approvalsCount: 42 },
    ]
  },
  'proj-metropolitan-chronicle': {
    modelVersion: 'v1.8-dpo-ranker',
    lastTrainedAt: '2026-08-30T14:15:00Z',
    totalComparisons: 28,
    preferenceWinRate: 0.84,
    avgTimeToApproveSec: 24.1,
    heldOutWinRate: 0.71,
    evaluatedSampleCount: 6,
    feedbackCount: 28,
    featureWeights: {
      tensionTolerance: 0.45,
      cutoutAffinity: 0.20,
      whitespaceGenerosity: 0.85,
      headlineDominance: 0.90,
      asymmetryPreference: 0.50,
    },
    learningHistory: [
      { date: '2026-08-21', winRate: 0.58, approvalsCount: 4 },
      { date: '2026-08-25', winRate: 0.72, approvalsCount: 14 },
      { date: '2026-08-30', winRate: 0.84, approvalsCount: 28 },
    ]
  },
  'proj-nordic-dispatch': {
    modelVersion: 'v1.2-dpo-ranker',
    lastTrainedAt: '2026-08-31T16:00:00Z',
    totalComparisons: 15,
    preferenceWinRate: 0.92,
    avgTimeToApproveSec: 14.8,
    heldOutWinRate: 0.75,
    evaluatedSampleCount: 4,
    feedbackCount: 15,
    featureWeights: {
      tensionTolerance: 0.60,
      cutoutAffinity: 0.85,
      whitespaceGenerosity: 0.95,
      headlineDominance: 0.75,
      asymmetryPreference: 0.80,
    },
    learningHistory: [
      { date: '2026-08-27', winRate: 0.75, approvalsCount: 6 },
      { date: '2026-08-31', winRate: 0.92, approvalsCount: 15 },
    ]
  }
};

export function createMockSceneGraph(
  format: 'berliner' | 'broadsheet' | 'tabloid',
  variantIndex: number,
  headlineText: string = 'Wielki Zwrot w Polityce Energetycznej: Nowy Plan Redakcji'
): SceneGraph {
  const isBerliner = format === 'berliner';
  const widthMm = isBerliner ? 315 : format === 'broadsheet' ? 375 : 280;
  const heightMm = isBerliner ? 470 : format === 'broadsheet' ? 560 : 400;
  const cols = isBerliner ? 5 : format === 'broadsheet' ? 6 : 4;
  const gutter = 4.5;
  const mTop = 16;
  const mLeft = 14;
  const colW = (widthMm - mLeft * 2 - (cols - 1) * gutter) / cols;

  const elements: SceneGraph['elements'] = [];

  // 1. Folio / Header
  elements.push({
    id: `elem-folio-${variantIndex}`,
    role: 'folio',
    frame: { x: mLeft, y: 10, width: widthMm - mLeft * 2, height: 5 },
    zIndex: 1,
    content: 'GAZETA CODZIENNA • WYDANIE GŁÓWNE • WTOREK, 1 WRZEŚNIA 2026 • NR 204 (11 820) • CENA 4,90 ZŁ (W TYM 8% VAT)',
    style: {
      fontFamily: 'Barlow Semi Condensed',
      fontSizePt: 8.5,
      lineHeightPt: 10,
      fontWeight: 700,
      color: '#7e8e9e',
      textAlign: 'center',
    },
    transgressionsApplied: [],
    tensionCost: 0,
    readingOrderIndex: 0,
  });

  // 2. Masthead
  elements.push({
    id: `elem-masthead-${variantIndex}`,
    role: 'masthead',
    frame: { x: mLeft, y: 16, width: widthMm - mLeft * 2, height: 26 },
    zIndex: 2,
    content: 'GAZETA CODZIENNA',
    style: {
      fontFamily: 'Fraunces',
      fontSizePt: 42,
      lineHeightPt: 42,
      fontWeight: 900,
      color: '#0b0f14',
      textAlign: 'center',
    },
    transgressionsApplied: [],
    tensionCost: 0,
    readingOrderIndex: 1,
  });

  // 3. Rule line under masthead
  elements.push({
    id: `elem-rule-top-${variantIndex}`,
    role: 'rule-line',
    frame: { x: mLeft, y: 43, width: widthMm - mLeft * 2, height: 1.0 },
    zIndex: 1,
    content: '',
    style: {
      backgroundColor: '#0b0f14',
    },
    transgressionsApplied: [],
    tensionCost: 0,
    readingOrderIndex: 2,
  });

  // Depending on variantIndex, create varied layout topologies:
  if (variantIndex % 3 === 0) {
    // VARIANT A: Dynamic 3-column lead on left, Hero Photo cutout spanning 2 cols on right with text wrap
    elements.push({
      id: `elem-kicker-${variantIndex}`,
      role: 'kicker',
      frame: { x: mLeft, y: 47, width: colW * 3 + gutter * 2, height: 7 },
      zIndex: 3,
      content: 'RAPORT SPECJALNY • PRZEŁOMOWE DECYZJE',
      style: {
        fontFamily: 'Barlow Semi Condensed',
        fontSizePt: 11.5,
        lineHeightPt: 13,
        fontWeight: 800,
        color: '#c1121f',
        textTransform: 'uppercase',
      },
      transgressionsApplied: ['kicker-highlight'],
      tensionCost: 1.0,
      readingOrderIndex: 3,
    });

    elements.push({
      id: `elem-headline-${variantIndex}`,
      role: 'headline',
      frame: { x: mLeft, y: 55, width: colW * 3 + gutter * 2, height: 42 },
      zIndex: 4,
      content: headlineText,
      style: {
        fontFamily: 'Fraunces',
        fontSizePt: 36,
        lineHeightPt: 36,
        fontWeight: 800,
        color: '#0b0f14',
      },
      transgressionsApplied: ['column-span-break'],
      tensionCost: 2.0,
      readingOrderIndex: 4,
    });

    elements.push({
      id: `elem-deck-${variantIndex}`,
      role: 'deck',
      frame: { x: mLeft, y: 99, width: colW * 3 + gutter * 2, height: 18 },
      zIndex: 3,
      content: 'Rząd przedstawia kompleksową reformę sieci przesyłowych i wsparcia dla mikroinstalacji. Inwestycje sięgną 45 mld złotych w ciągu najbliższych czterech lat.',
      style: {
        fontFamily: 'Inter',
        fontSizePt: 12.5,
        lineHeightPt: 16.5,
        fontWeight: 500,
        color: '#343e49',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 5,
    });

    // Hero Cutout Image
    const imgX = mLeft + (colW + gutter) * 3;
    const imgW = colW * 2 + gutter;
    elements.push({
      id: `elem-photo-lead-${variantIndex}`,
      role: 'image',
      frame: { x: imgX - 6, y: 47, width: imgW + 6, height: 110 },
      zIndex: 5,
      content: 'https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80',
      treatment: {
        isCutout: true,
        hasTextWrap: true,
        wrapContour: {
          points: [[0, 0], [1, 0], [1, 1], [0.15, 0.9], [0, 0.4]],
          offsetMm: 4.0,
          mode: 'contour',
        }
      },
      style: {},
      transgressionsApplied: ['photo-cutout-wrap', 'gutter-intrusion'],
      tensionCost: 3.5,
      readingOrderIndex: 6,
    });

    // Photo Caption & Credit
    elements.push({
      id: `elem-caption-${variantIndex}`,
      role: 'caption',
      frame: { x: imgX, y: 159, width: imgW, height: 12 },
      zIndex: 3,
      content: 'Fot. Adam Nowicki / Gazeta Codzienna. Turbiny wiatrowe na Pomorzu Zachodnim w świetle porannej mgły.',
      style: {
        fontFamily: 'Inter',
        fontSizePt: 7.8,
        lineHeightPt: 10.0,
        color: '#7e8e9e',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 7,
    });

    // Body text in 3 columns
    for (let c = 0; c < 3; c++) {
      const curX = mLeft + (colW + gutter) * c;
      elements.push({
        id: `elem-body-col-${c}-${variantIndex}`,
        role: 'body',
        frame: { x: curX, y: 120, width: colW, height: 155 },
        zIndex: 2,
        content: c === 0 
          ? 'Warszawa, 1 września. Zgromadzeni na posiedzeniu Rady Ministrów eksperci i ministrowie jednogłośnie przyjęli założenia nowej polityki surowcowej. To największa zmiana w polskim miksie energetycznym od dekad. Według wstępnych szacunków projekt pozwoli na obniżenie rachunków dla gospodarstw domowych nawet o dwadzieścia procent w perspektywie kolejnych trzech sezonów grzewczych.' 
          : c === 1
          ? 'Kluczowym elementem planu jest budowa nowoczesnych magazynów energii oraz odblokowanie lądowych farm wiatrowych. Ustawa ma trafić do laski marszałkowskiej już w nadchodzącym tygodniu. Opozycja zapowiada wnikliwą analizę kosztów, wskazując na konieczność zabezpieczenia stabilności sieci w okresach zimowego szczytu zapotrzebowania.'
          : '— To krok milowy, na który czekaliśmy od lat — podkreśla prof. Marek Zawadzki z Instytutu Energetyki Odnawialnej. — Stabilność dostaw energii oraz uniezależnienie od importu paliw kopalnych to fundament nowoczesnej gospodarki i gwarancja bezpieczeństwa narodowego.',
        style: {
          fontFamily: 'Inter',
          fontSizePt: 9.2,
          lineHeightPt: 12.5,
          fontWeight: 400,
          color: '#232b34',
          textAlign: 'justify',
        },
        transgressionsApplied: [],
        tensionCost: 0,
        readingOrderIndex: 8 + c,
      });
    }

    // Secondary Story Bottom Section (Dividing Rule + 2 cols + sidebar)
    elements.push({
      id: `elem-rule-mid-${variantIndex}`,
      role: 'rule-line',
      frame: { x: mLeft, y: 282, width: widthMm - mLeft * 2, height: 0.5 },
      zIndex: 1,
      content: '',
      style: { backgroundColor: '#232b34' },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 11,
    });

    elements.push({
      id: `elem-kicker-sec-${variantIndex}`,
      role: 'kicker',
      frame: { x: mLeft, y: 286, width: colW * 3 + gutter * 2, height: 6 },
      zIndex: 2,
      content: 'KULTURA I CYWILIZACJA',
      style: {
        fontFamily: 'Barlow Semi Condensed',
        fontSizePt: 10,
        lineHeightPt: 11,
        fontWeight: 700,
        color: '#c1121f',
        textTransform: 'uppercase',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 12,
    });

    elements.push({
      id: `elem-head-sec-${variantIndex}`,
      role: 'headline',
      frame: { x: mLeft, y: 293, width: colW * 3 + gutter * 2, height: 22 },
      zIndex: 3,
      content: 'Architektura Przyszłości: Jak Drewniane Wieżowce Zmieniają Centra Miast',
      style: {
        fontFamily: 'Fraunces',
        fontSizePt: 22,
        lineHeightPt: 24,
        fontWeight: 700,
        color: '#0b0f14',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 13,
    });

    // Sidebar box on bottom right
    const sbX = mLeft + (colW + gutter) * 3;
    const sbW = colW * 2 + gutter;
    elements.push({
      id: `elem-box-sidebar-${variantIndex}`,
      role: 'box-panel',
      frame: { x: sbX, y: 286, width: sbW, height: 160 },
      zIndex: 1,
      content: '',
      style: {
        backgroundColor: '#f5eee3',
        borderColor: '#c1121f',
        borderWidthPt: 1.5,
        paddingMm: { top: 6, right: 6, bottom: 6, left: 6 },
      },
      transgressionsApplied: ['shaded-panel-anchor'],
      tensionCost: 1.5,
      readingOrderIndex: 14,
    });

    elements.push({
      id: `elem-sidebar-head-${variantIndex}`,
      role: 'headline',
      frame: { x: sbX + 4, y: 292, width: sbW - 8, height: 16 },
      zIndex: 3,
      content: 'FELIETON DNIA • GŁOS REDAKCJI',
      style: {
        fontFamily: 'Barlow Semi Condensed',
        fontSizePt: 12,
        lineHeightPt: 14,
        fontWeight: 800,
        color: '#c1121f',
        textTransform: 'uppercase',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 15,
    });

    elements.push({
      id: `elem-sidebar-body-${variantIndex}`,
      role: 'body',
      frame: { x: sbX + 4, y: 310, width: sbW - 8, height: 130 },
      zIndex: 3,
      content: 'Kiedy technologia spotyka się z tradycją dziennikarską, rodzi się nowa jakość. Nasze zaangażowanie w przejrzystość, bezstronność i najwyższy kunszt redakcyjny pozostaje niezmienne od ponad trzech dekad. Odrzucamy powierzchowność na rzecz rzetelnego dochodzenia do prawdy.',
      style: {
        fontFamily: 'Inter',
        fontSizePt: 9.0,
        lineHeightPt: 13.0,
        fontWeight: 400,
        color: '#232b34',
        textAlign: 'left',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 16,
    });
  } else if (variantIndex % 3 === 1) {
    // VARIANT B: Massive 5-column Full Span Super Headline with 2 Hero photos side-by-side
    elements.push({
      id: `elem-kicker-${variantIndex}`,
      role: 'kicker',
      frame: { x: mLeft, y: 47, width: widthMm - mLeft * 2, height: 7 },
      zIndex: 3,
      content: 'WYDANIE SPECJALNE • STRATEGIA ROZWOJU',
      style: {
        fontFamily: 'Barlow Semi Condensed',
        fontSizePt: 12,
        lineHeightPt: 13,
        fontWeight: 800,
        color: '#c1121f',
        textTransform: 'uppercase',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 3,
    });

    elements.push({
      id: `elem-headline-${variantIndex}`,
      role: 'headline',
      frame: { x: mLeft, y: 55, width: widthMm - mLeft * 2, height: 48 },
      zIndex: 4,
      content: headlineText.toUpperCase(),
      style: {
        fontFamily: 'Fraunces',
        fontSizePt: 42,
        lineHeightPt: 41,
        fontWeight: 900,
        color: '#0b0f14',
      },
      transgressionsApplied: ['super-headline-span'],
      tensionCost: 2.5,
      readingOrderIndex: 4,
    });

    elements.push({
      id: `elem-deck-${variantIndex}`,
      role: 'deck',
      frame: { x: mLeft, y: 105, width: (widthMm - mLeft * 2) * 0.7, height: 16 },
      zIndex: 3,
      content: 'Ponad 45 miliardów złotych na modernizację infrastruktury. Sejm rozpoczyna debatę nad pakietem ustaw energetycznych.',
      style: {
        fontFamily: 'Playfair Display',
        fontSizePt: 13.5,
        lineHeightPt: 18,
        fontWeight: 600,
        color: '#343e49',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 5,
    });

    // 5 equal body columns below
    for (let c = 0; c < 5; c++) {
      const curX = mLeft + (colW + gutter) * c;
      elements.push({
        id: `elem-body-col-${c}-${variantIndex}`,
        role: 'body',
        frame: { x: curX, y: 125, width: colW, height: 320 },
        zIndex: 2,
        content: `Kolumna ${c + 1}. Dyskusja w parlamencie skupia się na kluczowych gwarancjach cenowych dla odbiorców indywidualnych oraz małych i średnich przedsiębiorstw. Zgodnie z rządowym harmonogramem pierwsze środki z funduszy transformacyjnych zostaną uruchomione już w czwartym kwartale bieżącego roku. Równolegle trwają konsultacje z samorządami w sprawie lokalizacji nowych węzłów przesyłowych.`,
        style: {
          fontFamily: 'Inter',
          fontSizePt: 9.0,
          lineHeightPt: 12.2,
          fontWeight: 400,
          color: '#232b34',
          textAlign: 'justify',
        },
        transgressionsApplied: [],
        tensionCost: 0,
        readingOrderIndex: 6 + c,
      });
    }
  } else {
    // VARIANT C: Asymmetrical Editorial with Tilted Pull-Quote & High Tension Silhouette
    elements.push({
      id: `elem-kicker-${variantIndex}`,
      role: 'kicker',
      frame: { x: mLeft, y: 47, width: colW * 4 + gutter * 3, height: 7 },
      zIndex: 3,
      content: 'EKSKLUZYWNY WYWIAD • DECYZJE',
      style: {
        fontFamily: 'Barlow Semi Condensed',
        fontSizePt: 11,
        lineHeightPt: 12,
        fontWeight: 800,
        color: '#c1121f',
        textTransform: 'uppercase',
      },
      transgressionsApplied: [],
      tensionCost: 0,
      readingOrderIndex: 3,
    });

    elements.push({
      id: `elem-headline-${variantIndex}`,
      role: 'headline',
      frame: { x: mLeft, y: 55, width: colW * 4 + gutter * 3, height: 38 },
      zIndex: 4,
      content: headlineText,
      style: {
        fontFamily: 'Playfair Display',
        fontSizePt: 34,
        lineHeightPt: 35,
        fontWeight: 700,
        color: '#0b0f14',
      },
      transgressionsApplied: ['asymmetric-width'],
      tensionCost: 2.0,
      readingOrderIndex: 4,
    });

    // Pull quote with crimson highlight
    elements.push({
      id: `elem-pullquote-${variantIndex}`,
      role: 'pullquote',
      frame: { x: mLeft + (colW + gutter) * 2, y: 150, width: colW * 2 + gutter, height: 44 },
      zIndex: 5,
      content: '„To nie jest kwestia wyboru politycznego, lecz historycznej konieczności technologicznej”',
      style: {
        fontFamily: 'Fraunces',
        fontSizePt: 18,
        lineHeightPt: 22,
        fontWeight: 700,
        color: '#c1121f',
        textAlign: 'center',
        borderColor: '#c1121f',
        borderWidthPt: 1.0,
        paddingMm: { top: 4, right: 4, bottom: 4, left: 4 },
      },
      transgressionsApplied: ['pullquote-border-box', 'column-break'],
      tensionCost: 3.0,
      readingOrderIndex: 6,
    });
  }

  return {
    id: `sg-candidate-${variantIndex}`,
    version: 1,
    pageFormat: {
      widthMm,
      heightMm,
      columns: cols,
      gutterMm: gutter,
      margins: { top: mTop, bottom: 20, left: mLeft, right: mLeft },
    },
    elements,
    metadata: {
      totalTension: 5.5 + (variantIndex * 1.2) % 6,
      densityRatio: 0.74,
      collisionsCount: 0,
      readingOrderFlowValid: true,
      estimatedCopyfitPercentage: 98.4,
    }
  };
}

export function createMockCandidates(runId: string, count: number = 8): Candidate[] {
  const titles = [
    'Wielki Zwrot w Polityce Energetycznej: 45 Mld Złotych na Nową Sieć',
    'Zielona Transformacja Przyspiesza: Rząd Odblokowuje Farmy Wiatrowe',
    'Koniec Ery Paliw Kopalnych: Sejm Przyjmuje Historyczną Ustawę',
    'Nowy Ład w Energetyce: Prąd Tańszy o 20 Procent dla Gospodarstw',
    'Inwestycje Stulecia: Polska Liderem Innowacji wodorowych w Europie',
    'Przełom w Brukseli: Miliardy Euro z Funduszu Spójności Odblokowane',
    'Gospodarka na Fali: Eksport Przemysłowy Osiąga Rekordowe Wyniki',
    'Cyfrowy Skok Administracji: Sztuczna Inteligencja Usprawni Urzędy'
  ];

  const rationales = [
    'Doskonała hierarchia typograficzna; szparowane zdjęcie z dynamicznym oblewaniem na 3. kolumnie nadaje stronie energii; zero kolizji.',
    'Wysoka czytelność i klasyczny układ 5-kolumnowy; zbalansowane proporcje tytułu głównego do leadu; idealny copyfit.',
    'Ekspresyjny super-headline przyciąga uwagę; transgresja w granicach budżetu napięcia (6.5/12); wysoka zgodność z DNA.',
    'Asymetryczna kompozycja z wyrazistą ramką felietonu na dole; wyśmienita dynamika czytania; anty-kopiowanie: 0.88 od korpusu.',
    'Mocny nagłówek z oblewaniem konturowym; wzorowy przepływ tekstu; minimalny overset (0 linii).',
    'Czysty, minimalistyczny wariant z dominującym leadem i przemyślaną przestrzenią światła;',
    'Odważna kompozycja z wyciągniętym cytatem w kolorze cynobrowym; wysoki score czytelności;',
    'Zrównoważona struktura 6-kolumnowa, wzorcowe proporcje światła do kolumny tekstu.'
  ];

  return Array.from({ length: count }, (_, i) => {
    const criticScore = +(0.88 + Math.sin(i * 1.5) * 0.09).toFixed(2);
    const tasteScore = +(0.85 + Math.cos(i * 1.2) * 0.12).toFixed(2);
    const noveltyDistance = +(0.75 + ((i * 17) % 20) / 100).toFixed(2);
    const tensionEnergyConsumed = +(4.0 + (i * 1.3) % 7.5).toFixed(1);
    const sg = createMockSceneGraph('berliner', i, titles[i % titles.length]);

    return {
      id: `cand-${runId}-${i + 1}`,
      runId,
      candidateNumber: i + 1,
      sceneGraph: sg,
      criticScore,
      tasteScore,
      passHardGates: i !== 6, // simulate one gate issue for realism
      hardGatesReport: {
        passed: i !== 6,
        collisionsFound: 0,
        readabilityScore: i === 6 ? 68 : 96,
        prepressOversetLines: 0,
        hierarchyViolations: i === 6 ? 1 : 0,
        marginViolations: 0,
        details: i === 6 
          ? ['Drobne przekroczenie minimalnej wielkości kegla w stopce'] 
          : ['Brak kolizji ramek', 'Wzorowy kontrast typograficzny', 'Poprawny prepress'],
      },
      criticRationale: rationales[i % rationales.length],
      noveltyDistance,
      tensionEnergyConsumed,
      transgressionsCount: 2 + (i % 3),
      tags: i === 0 ? ['Top Pick', 'High Dynamic', 'Cutout Wrap'] : i === 1 ? ['Editor Choice', 'High Readability'] : ['Creative Variant'],
      isBookmarked: i === 0,
      createdAt: new Date(Date.now() - (8 - i) * 60000).toISOString(),
    };
  });
}

export const INITIAL_GENERATION_RUNS: GenerationRun[] = [
  {
    id: 'run-gc-latest',
    projectId: 'proj-gazeta-codzienna',
    timestamp: '2026-09-01T10:15:00Z',
    status: 'completed',
    requestedCandidateCount: 8,
    candidates: createMockCandidates('run-gc-latest', 8),
    bestCandidateId: 'cand-run-gc-latest-1',
    targetTension: 7.0,
    noveltyMean: 0.82,
    elapsedMs: 2450,
  }
];
