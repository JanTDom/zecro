export interface BoundingBox {
  x: number; // 0..1 relative or mm
  y: number;
  width: number;
  height: number;
  role: 'masthead' | 'headline' | 'kicker' | 'deck' | 'body' | 'image' | 'caption' | 'advert' | 'rule' | 'folio';
  confidence: number;
}

export interface ExtractedFeatureSummary {
  detectedColumns: number;
  detectedGutterMm: number;
  dominantFontFamilies: string[];
  maxHeadlineSizePt: number;
  bodyFontSizePt: number;
  photoRatio: number;
  whiteSpaceRatio: number;
  transgressionDetected: string[];
  colorPaletteExtracted: string[];
  noveltyVector: number[];
}

export interface CorpusPage {
  id: string;
  projectId: string;
  fileName: string;
  fileType: 'pdf' | 'png' | 'jpg' | 'idml';
  fileSize: number;
  pageNumber: number;
  editionDate: string;
  thumbnailUrl: string;
  previewUrl: string;
  status: 'analyzed' | 'processing' | 'error';
  widthMm: number;
  heightMm: number;
  boundingBoxes: BoundingBox[];
  features: ExtractedFeatureSummary;
  createdAt: string;
  extractionDetails?: Record<string, any>;
}
