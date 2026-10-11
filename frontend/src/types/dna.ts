export interface TypographyStyle {
  fontFamily: string;
  weight: number | string;
  sizePt: number;
  lineHeightPt: number;
  letterSpacingPt?: number;
  textTransform?: 'uppercase' | 'none' | 'capitalize' | 'lowercase';
  color: string;
}

export interface TypeScale {
  superHeadline: TypographyStyle;
  headlinePrimary: TypographyStyle;
  headlineSecondary: TypographyStyle;
  kicker: TypographyStyle;
  deck: TypographyStyle;
  lead: TypographyStyle;
  body: TypographyStyle;
  byline: TypographyStyle;
  caption: TypographyStyle;
  pullQuote: TypographyStyle;
  folio: TypographyStyle;
}

export interface PaletteColor {
  name: string;
  hex: string;
  cmyk?: string;
  role: 'ink' | 'accent' | 'tint' | 'paper' | 'rule';
}

export interface TransgressionRule {
  id: string;
  name: string;
  description: string;
  allowed: boolean;
  cost: number; // 0 to 10 points
  maxPerSpread: number;
  triggerCondition: string;
}

export type PhotoPlacement = 
  | 'lead-hero' 
  | 'hero-center' 
  | 'top-lead' 
  | 'top-banner' 
  | 'bottom-anchor' 
  | 'sidebar' 
  | 'floating-island';

export interface TitleDNA {
  id: string;
  canonical?: Record<string, any>;
  archetype?: string;
  styleBlend?: StyleBlend;
  projectId: string;
  version: number;
  updatedAt: string;
  // Grid rules
  grid: {
    columns: number;
    columnWidthMm: number;
    gutterMm: number;
    baselineGridPt: number;
    marginTopMm: number;
    marginBottomMm: number;
    marginLeftMm: number;
    marginRightMm: number;
    subdivision: number; // e.g. 1/2 or 1/3 column breaks
  };
  // Typography hierarchy
  typography: TypeScale;
  // Color palette
  palette: {
    colors: PaletteColor[];
    backgroundTone: string;
    ruleColor: string;
    dominantInk: string;
  };
  // Photo & Art direction rules
  photos: {
    allowedCutouts: boolean;
    minAspectRatio: number;
    maxAspectRatio: number;
    preferredPlacements: PhotoPlacement[];
    wrapPaddingMm: number;
    borderRulePt: number;
    duotoneAccent: boolean;
  };
  // Transgression Catalog & Energy Budget
  transgressionCatalog: TransgressionRule[];
  pageEnergyBudget: {
    maxTensionScore: number; // e.g. 15
    targetTensionScore: number; // e.g. 8
    punishExceeding: boolean;
  };
  // Feature extraction statistics from corpus
  corpusMetrics: {
    pagesAnalyzed: number;
    avgDensity: number;
    dominantColumnUsage: number[];
    avgHeadlineToBodyRatio: number;
    detectedBleedRate: number;
  };
}

export interface StyleBlend {
  opinion_to_tabloid: number;
  classical_to_avantgarde: number;
  dense_to_photo: number;
}
