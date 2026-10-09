export type ExportFormat = 'pdf' | 'idml' | 'svg' | 'html' | 'typst';

export interface ExportOptions {
  format: ExportFormat;
  includeBleed: boolean;
  includeCropMarks: boolean;
  colorProfile: 'CMYK_ISO_Coated_v2' | 'CMYK_Newspaper_WAN_IFRA' | 'sRGB';
  embedFonts: boolean;
  preserveTextFrames: boolean;
  exportClippingPaths: boolean;
  dpi: 150 | 300 | 600;
}

export interface ExportArtifact {
  id: string;
  projectId: string;
  candidateId: string;
  format: ExportFormat;
  downloadUrl: string;
  fileSizeBytes: number;
  fileName: string;
  createdAt: string;
  options: ExportOptions;
}
