import { EditorialRole } from './material';

export interface RectFrame {
  x: number; // in mm
  y: number; // in mm
  width: number; // in mm
  height: number; // in mm
}

export interface WrapContour {
  points: [number, number][]; // normalized [0..1, 0..1]
  offsetMm: number;
  mode: 'contour' | 'bounding-box' | 'jump';
}

export interface SceneGraphElement {
  id: string;
  canonical?: Record<string, any>;
  role: EditorialRole | 'masthead' | 'image' | 'rule-line' | 'box-panel' | 'folio';
  storyId?: string;
  importance?: number;
  frame: RectFrame;
  zIndex: number;
  content: string; // text content or image URL
  style: {
    fontFamily?: string;
    fontSizePt?: number;
    lineHeightPt?: number;
    fontWeight?: string | number;
    color?: string;
    backgroundColor?: string;
    borderColor?: string;
    borderWidthPt?: number;
    paddingMm?: { top: number; right: number; bottom: number; left: number };
    columnCount?: number;
    columnGutterMm?: number;
    textAlign?: 'left' | 'justify' | 'center' | 'right';
    textTransform?: 'uppercase' | 'none' | 'capitalize';
    letterSpacingEm?: number;
  };
  treatment?: {
    isCutout?: boolean;
    maskUrl?: string;
    hasTextWrap?: boolean;
    wrapContour?: WrapContour;
    opacity?: number;
    blendMode?: string;
    rotationDeg?: number;
  };
  transgressionsApplied: string[]; // e.g. ['column-bleed', 'headline-overlap', 'asymmetric-gutter']
  tensionCost: number;
  readingOrderIndex: number;
}

export interface SceneGraph {
  id: string;
  canonical?: Record<string, any>;
  version: number;
  pageFormat: {
    widthMm: number;
    heightMm: number;
    columns: number;
    gutterMm: number;
    margins: { top: number; bottom: number; left: number; right: number };
  };
  elements: SceneGraphElement[];
  metadata: {
    totalTension: number;
    densityRatio: number;
    collisionsCount: number;
    readingOrderFlowValid: boolean;
    estimatedCopyfitPercentage: number;
    artDirection?: import('./generation').ArtDirectionPlan;
    layoutMode?: string;
    [key: string]: any;
  };
}

export interface ElementDelta {
  elementId: string;
  previousFrame: RectFrame;
  newFrame: RectFrame;
  previousStyle?: Partial<SceneGraphElement['style']>;
  newStyle?: Partial<SceneGraphElement['style']>;
  changeType: 'move' | 'resize' | 'reorder' | 'style' | 'delete' | 'add';
  timestamp: string;
}
