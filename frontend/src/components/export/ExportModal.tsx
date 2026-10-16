import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { ExportFormat, ExportOptions, ExportArtifact } from '../../types/export';
import { api } from '../../api/client';
import { styleReviewState } from '../../styleReview';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
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

  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportedArtifact, setExportedArtifact] = useState<ExportArtifact | null>(null);

  if (!selectedCandidate || !activeProject) return null;
  const reviewState = styleReviewState(selectedCandidate);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const options: ExportOptions = {
        format,
        includeBleed: true,
        includeCropMarks: true,
        colorProfile: 'CMYK_Newspaper_WAN_IFRA',
        embedFonts: true,
        preserveTextFrames: true,
        exportClippingPaths: true,
        dpi: 300,
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
        title: 'Nie udało się przygotować pliku',
        message: 'Spróbuj ponownie lub wybierz inny format.',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleInstantBrowserPrint = () => {
    if (!selectedCandidate || !activeProject) return;
    const pageW = selectedCandidate.sceneGraph.pageFormat.widthMm;
    const pageH = selectedCandidate.sceneGraph.pageFormat.heightMm;
    const svgContent = selectedCandidate.thumbnailSvg;

    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      addToast({
        type: 'error',
        title: 'Zablokowane okno podglądu',
        message: 'Zezwól przeglądarce na otwieranie nowych okien.',
      });
      return;
    }

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>${activeProject.name} - Wariant ${selectedCandidate.candidateNumber}</title>
          <style>
            @page {
              size: ${pageW}mm ${pageH}mm;
              margin: 0;
            }
            html, body {
              margin: 0;
              padding: 0;
              width: ${pageW}mm;
              height: ${pageH}mm;
              overflow: hidden;
              background: #ffffff;
            }
            svg {
              width: ${pageW}mm;
              height: ${pageH}mm;
              display: block;
            }
            @media print {
              body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            }
          </style>
        </head>
        <body>
          ${svgContent || ''}
          <script>
            window.onload = function() {
              setTimeout(function() {
                window.print();
              }, 200);
            };
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        setExportedArtifact(null);
        onClose();
      }}
      title="Pobierz projekt strony"
      subtitle={`Wybierz format pliku dla wariantu ${selectedCandidate.candidateNumber}.`}
      maxWidth="xl"
    >
      <div className="space-y-6">
        {reviewState !== 'candidate_for_editor' && (
          <p className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900">
            <strong>To plik próbny, nie gotowa strona do wydania.</strong>{' '}
            {reviewState === 'unreviewed'
              ? 'Wygląd strony nie został oceniony przez krytyka wizualnego.'
              : 'Ocena wizualna wykazała, że strona nie oddaje jeszcze przekonująco wybranego rodzaju gazety.'}{' '}
            Możesz pobrać plik do dalszej pracy.
          </p>
        )}
        {reviewState === 'candidate_for_editor' && (
          <p className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900">
            Krytyk wizualny uznał styl za obiecujący. Przed wydaniem stronę musi jeszcze ocenić redaktor.
          </p>
        )}
        {/* Format Selector */}
        <div>
          <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-2">
            Format pliku
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {/* PDF */}
            <button type="button" aria-pressed={format === 'pdf'}
              onClick={() => setFormat('pdf')}
              className={`p-3 rounded-lg border cursor-pointer transition-all text-left ${
                format === 'pdf'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <Printer className="w-5 h-5 text-editorial-crimson mb-1.5" />
              <p className="text-xs font-bold text-ink-100">PDF do kontroli druku</p>
              <p className="text-[10px] text-ink-400 font-mono">Tekst i fonty osadzone</p>
            </button>

            {/* IDML */}
            <button type="button" aria-pressed={format === 'idml'}
              onClick={() => setFormat('idml')}
              className={`p-3 rounded-lg border cursor-pointer transition-all text-left ${
                format === 'idml'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileSpreadsheet className="w-5 h-5 text-purple-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">Adobe IDML</p>
              <p className="text-[10px] text-ink-400 font-mono">Do dalszej edycji w InDesign</p>
            </button>

            {/* SVG */}
            <button type="button" aria-pressed={format === 'svg'}
              onClick={() => setFormat('svg')}
              className={`p-3 rounded-lg border cursor-pointer transition-all text-left ${
                format === 'svg'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileType className="w-5 h-5 text-blue-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">SVG</p>
              <p className="text-[10px] text-ink-400 font-mono">Grafika wektorowa</p>
            </button>

            {/* HTML */}
            <button type="button" aria-pressed={format === 'html'}
              onClick={() => setFormat('html')}
              className={`p-3 rounded-lg border cursor-pointer transition-all text-left ${
                format === 'html'
                  ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                  : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
              }`}
            >
              <FileCode className="w-5 h-5 text-emerald-400 mb-1.5" />
              <p className="text-xs font-bold text-ink-100">Strona internetowa</p>
              <p className="text-[10px] text-ink-400 font-mono">Plik HTML</p>
            </button>
          </div>
        </div>

        {format === 'pdf' && (
          <p className="rounded-xl border border-ink-800 bg-ink-950 p-4 text-xs leading-relaxed text-ink-300">
            PDF zawiera tekst, osadzone fonty, spad 3 mm i znaczniki cięcia. Przed wysłaniem do drukarni sprawdź wynik i wymagany profil kolorów; plik nie ma certyfikatu PDF/X.
          </p>
        )}

        {/* Export Success Result */}
        {exportedArtifact && (
          <div className="p-4 bg-emerald-950/70 border border-emerald-800/80 rounded-xl flex items-center justify-between animate-fade-in">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <div>
                <p className="text-xs font-bold text-ink-100">{exportedArtifact.fileName}</p>
                <p className="text-[10px] font-mono text-emerald-300">
                  Plik gotowy • {(exportedArtifact.fileSizeBytes / 1024 / 1024).toFixed(2)} MB
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
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-ink-800">
          <Button
            variant="outline"
            leftIcon={<Printer className="w-4 h-4 text-editorial-ochre" />}
            onClick={handleInstantBrowserPrint}
            className="border-editorial-ochre/40 text-editorial-ochre hover:bg-editorial-ochre/10"
          >
            Błyskawiczny PDF z przeglądarki
          </Button>

          <div className="flex items-center justify-end gap-3">
            <Button variant="ghost" onClick={onClose}>
              Zamknij
            </Button>
            <Button
              variant="editorial"
              isLoading={isExporting}
              leftIcon={<Download className="w-4 h-4" />}
              onClick={handleExport}
            >
              Generuj plik serwerowy ({format.toUpperCase()})
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
