import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { ExportFormat, ExportOptions, ExportArtifact } from '../../types/export';
import { api } from '../../api/client';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Toggle } from '../common/Toggle';
import {
  Download,
  FileType,
  FileCode,
  FileSpreadsheet,
  CheckCircle2,
  Printer,
} from 'lucide-react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({ isOpen, onClose }) => {
  const { selectedCandidate, activeProject, addToast } = useProject();

  const [format, setFormat] = useState<ExportFormat>('pdf');
  const [includeBleed, setIncludeBleed] = useState<boolean>(true);
  const [includeCropMarks, setIncludeCropMarks] = useState<boolean>(true);
  const [colorProfile, setColorProfile] = useState<ExportOptions['colorProfile']>('CMYK_Newspaper_WAN_IFRA');
  const [embedFonts, setEmbedFonts] = useState<boolean>(true);
  const [preserveTextFrames, setPreserveTextFrames] = useState<boolean>(true);
  const [exportClippingPaths, setExportClippingPaths] = useState<boolean>(true);
  const [dpi, setDpi] = useState<150 | 300 | 600>(300);

  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportedArtifact, setExportedArtifact] = useState<ExportArtifact | null>(null);

  if (!selectedCandidate || !activeProject) return null;

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const options: ExportOptions = {
        format,
        includeBleed,
        includeCropMarks,
        colorProfile,
        embedFonts,
        preserveTextFrames,
        exportClippingPaths,
        dpi,
      };

      const artifact = await api.exportCandidate(selectedCandidate.id, options);
      setExportedArtifact(artifact);

      addToast({
        type: 'success',
        title: 'Eksport gotowy',
        message: `Utworzono ${artifact.fileName} (${(artifact.fileSizeBytes / 1024 / 1024).toFixed(2)} MB).`,
      });
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Export Failed',
        message: 'Could not render production artifact.',
      });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        setExportedArtifact(null);
        onClose();
      }}
      title="Eksport produkcyjny"
      subtitle={`Eksport wariantu #${selectedCandidate.candidateNumber} to print-ready and DTP formats.`}
      maxWidth="xl"
    >
      <div className="space-y-6">
        {/* Format Selector */}
        <div>
          <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-2">
            Format produkcyjny
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {/* PDF */}
            <div
              onClick={() => setFormat('pdf')}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                format === 'pdf'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <Printer className="w-5 h-5 text-editorial-crimson mb-1.5" />
              <p className="text-xs font-bold text-ink-100">PDF Print</p>
              <p className="text-[10px] text-ink-400 font-mono">HTML/CSS Prepress</p>
            </div>

            {/* IDML */}
            <div
              onClick={() => setFormat('idml')}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                format === 'idml'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileSpreadsheet className="w-5 h-5 text-purple-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">Adobe IDML</p>
              <p className="text-[10px] text-ink-400 font-mono">InDesign Package</p>
            </div>

            {/* SVG */}
            <div
              onClick={() => setFormat('svg')}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                format === 'svg'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileType className="w-5 h-5 text-blue-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">Vector SVG</p>
              <p className="text-[10px] text-ink-400 font-mono">Scalable Graphic</p>
            </div>

            {/* HTML */}
            <div
              onClick={() => setFormat('html')}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                format === 'html'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileCode className="w-5 h-5 text-emerald-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">Web HTML</p>
              <p className="text-[10px] text-ink-400 font-mono">Interactive Bundle</p>
            </div>
          </div>
        </div>

        {/* Prepress Specifications */}
        <div className="p-4 bg-ink-950 rounded-xl border border-ink-800 space-y-4">
          <span className="text-xs font-mono uppercase font-bold text-editorial-ochre block">
            Parametry prepress i DTP
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono uppercase text-ink-400 mb-1">
                Color Profile
              </label>
              <select
                value={colorProfile}
                onChange={(e: any) => setColorProfile(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-ink-900 border border-ink-700 rounded text-xs text-ink-100"
              >
                <option value="CMYK_Newspaper_WAN_IFRA">WAN-IFRA Newspaper CMYK</option>
                <option value="CMYK_ISO_Coated_v2">ISO Coated v2 (FOGRA39)</option>
                <option value="sRGB">sRGB (Digital Preview)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-ink-400 mb-1">
                Target Output Resolution
              </label>
              <select
                value={dpi}
                onChange={(e: any) => setDpi(Number(e.target.value) as 150 | 300 | 600)}
                className="w-full px-2.5 py-1.5 bg-ink-900 border border-ink-700 rounded text-xs text-ink-100"
              >
                <option value={150}>150 DPI (Draft Web)</option>
                <option value={300}>300 DPI (Standard Press)</option>
                <option value={600}>600 DPI (High-Resolution CtP)</option>
              </select>
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-ink-800">
            <Toggle
              label="Include 3mm Bleed & Crop Marks"
              checked={includeBleed}
              onChange={setIncludeBleed}
            />
            <Toggle
              label="Include Document Crop & Fold Marks"
              checked={includeCropMarks}
              onChange={setIncludeCropMarks}
            />
            <Toggle
              label="Embed Font Subsets in Artifact"
              checked={embedFonts}
              onChange={setEmbedFonts}
            />
            <Toggle
              label="Preserve Live Text Frames & OpenType Features"
              checked={preserveTextFrames}
              onChange={setPreserveTextFrames}
            />
            <Toggle
              label="Export Vector Clipping Paths for Silhouette Wrap"
              checked={exportClippingPaths}
              onChange={setExportClippingPaths}
            />
          </div>
        </div>

        {/* Export Success Result */}
        {exportedArtifact && (
          <div className="p-4 bg-emerald-950/70 border border-emerald-800/80 rounded-xl flex items-center justify-between animate-fade-in">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <div>
                <p className="text-xs font-bold text-ink-100">{exportedArtifact.fileName}</p>
                <p className="text-[10px] font-mono text-emerald-300">
                  Gotowe do prepress • {(exportedArtifact.fileSizeBytes / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <Button
              variant="editorial"
              size="sm"
              leftIcon={<Download className="w-3.5 h-3.5" />}
              onClick={() => {
                const link = document.createElement('a');
                link.href = exportedArtifact.downloadUrl;
                link.download = exportedArtifact.fileName;
                link.rel = 'noopener';
                document.body.appendChild(link);
                link.click();
                link.remove();
              }}
            >
              Pobierz
            </Button>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-ink-800">
          <Button variant="ghost" onClick={onClose}>
            Zamknij
          </Button>
          <Button
            variant="editorial"
            isLoading={isExporting}
            leftIcon={<Download className="w-4 h-4" />}
            onClick={handleExport}
          >
            Utwórz {format.toUpperCase()} Package
          </Button>
        </div>
      </div>
    </Modal>
  );
};
