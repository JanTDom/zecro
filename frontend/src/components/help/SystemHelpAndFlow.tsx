import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { editorialStyle } from '../../editorialStyles';
import { 
  HelpCircle, 
  Sparkles, 
  Layers, 
  ShieldCheck, 
  Eye, 
  Download, 
  Cpu, 
  RotateCcw, 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle, 
  FileCode,
  Palette,
  Camera,
  Grid
} from 'lucide-react';

export const SystemHelpAndFlow: React.FC = () => {
  const { activeProject, dna, setActiveTab } = useProject();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Dynamiczne, samokorygujące się dane aktywnego stylu i projektu
  const style = editorialStyle(activeProject?.editorialCharacter);
  const archetypeLabel = style.name;
  const columnsCount = dna?.grid.columns || activeProject?.dimensions.columnsCount || 5;
  const gutterMm = dna?.grid.gutterMm || activeProject?.dimensions.gutterMm || 4;
  const baselinePt = dna?.grid.baselineGridPt || 9.5;
  const energyScore = typeof dna?.pageEnergyBudget === 'object' 
    ? (dna.pageEnergyBudget?.maxTensionScore ?? 0.75) 
    : (typeof dna?.pageEnergyBudget === 'number' ? dna.pageEnergyBudget : (style.energy ?? 0.75));
  const primaryColor = dna?.palette?.dominantInk || '#17212b';
  const accentColor = dna?.palette?.colors?.[0]?.hex || '#e1262f';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10 animate-fade-in text-ink-100">
      
      {/* Nagłówek stacyjny z logo */}
      <div className="bg-gradient-to-r from-ink-950 via-ink-900 to-ink-950 border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-page-elevated relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-editorial-crimson/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative z-10">
          <div className="flex items-center gap-5">
            <img src="/zecro-logo.png" alt="Zecro" className="h-14 w-auto object-contain drop-shadow" />
            <div>
              <div className="flex items-center gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-editorial-crimson/20 text-editorial-crimson border border-editorial-crimson/30">
                  Przewodnik interaktywny
                </span>
                <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Stan na żywo
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold font-headline tracking-tight text-white mt-1">
                Jak działa system Zecro
              </h1>
              <p className="text-sm text-ink-400 mt-1 max-w-2xl">
                Dynamiczny schemat przepływu danych i mechanizmów generatywnego składu prasowego. Pomoc koryguje się automatycznie przy każdej zmianie parametrów gazety.
              </p>
            </div>
          </div>

          {/* Aktywny kontekst projektu (korygujący się na żywo) */}
          <div className="bg-ink-950/80 border border-ink-800 rounded-xl p-4 text-xs font-mono shrink-0 min-w-[260px]">
            <div className="text-ink-400 font-sans font-semibold mb-2 flex items-center justify-between">
              <span>Aktywna gazeta:</span>
              <span className="text-ink-100">{activeProject?.name || 'Domyślna makieta'}</span>
            </div>
            <div className="space-y-1.5 text-ink-300">
              <div className="flex justify-between">
                <span className="text-ink-500">Styl / archetyp:</span>
                <span className="text-editorial-crimson font-bold">{archetypeLabel}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Siatka strony:</span>
                <span>{columnsCount} szpalt (odstęp {gutterMm} mm)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Linia bazowa:</span>
                <span>{baselinePt} pt</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Budżet energii:</span>
                <span>{energyScore.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Żywa, animowana infografika SVG (pokazuje jak wszystko biega ze strzałkami i ruchem) */}
      <div className="bg-ink-950 border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-page-elevated">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-white font-headline flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-editorial-crimson" />
              Animowany przepływ danych w systemie
            </h2>
            <p className="text-xs text-ink-400 mt-1">
              Świecące impulsy pokazują rzeczywistą drogę informacji: od surowego materiału, przez generator i twardego krytyka, aż po podwójne wyjście hybrydowe.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono text-ink-400 bg-ink-900 px-3 py-1.5 rounded-lg border border-ink-800">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
            Kliknij dowolny węzeł, aby poznać jego mechanizm
          </div>
        </div>

        {/* Interaktywny kontener diagramu z CSS animations */}
        <div className="w-full overflow-x-auto pb-4">
          <div className="min-w-[980px] bg-[#07090e] border border-ink-800/80 rounded-xl p-6 relative select-none">
            
            <style>{`
              @keyframes dashFlow {
                to { stroke-dashoffset: -40; }
              }
              @keyframes pulseFail {
                0%, 100% { opacity: 0.3; }
                50% { opacity: 1; }
              }
              .pulse-line-cyan {
                stroke-dasharray: 8 6;
                animation: dashFlow 1.8s linear infinite;
              }
              .pulse-line-crimson {
                stroke-dasharray: 8 6;
                animation: dashFlow 1.5s linear infinite;
              }
              .pulse-line-gold {
                stroke-dasharray: 8 6;
                animation: dashFlow 2s linear infinite;
              }
              .pulse-line-green {
                stroke-dasharray: 8 6;
                animation: dashFlow 1.6s linear infinite;
              }
              .fail-return-line {
                stroke-dasharray: 6 6;
                animation: dashFlow 2.5s linear infinite reverse, pulseFail 2s ease-in-out infinite;
              }
            `}</style>

            <svg viewBox="0 0 1100 480" className="w-full h-auto">
              <defs>
                <marker id="arr-c" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#38bdf8" /></marker>
                <marker id="arr-r" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#e1262f" /></marker>
                <marker id="arr-g" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#eab308" /></marker>
                <marker id="arr-e" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#34d399" /></marker>
              </defs>

              {/* Ścieżki przepływu */}
              {/* Redakcja -> Adiustacja & Gemini */}
              <path d="M 150 140 L 220 140" stroke="#38bdf8" strokeWidth="2.5" fill="none" className="pulse-line-cyan" markerEnd="url(#arr-c)" />
              <path d="M 150 160 L 180 160 L 180 260 L 220 260" stroke="#38bdf8" strokeWidth="2.5" fill="none" className="pulse-line-cyan" markerEnd="url(#arr-c)" />

              {/* Adiustacja & Gemini -> Generator */}
              <path d="M 370 140 L 440 140 L 440 190 L 470 190" stroke="#38bdf8" strokeWidth="2.5" fill="none" className="pulse-line-cyan" markerEnd="url(#arr-c)" />
              <path d="M 370 260 L 440 260 L 440 220 L 470 220" stroke="#38bdf8" strokeWidth="2.5" fill="none" className="pulse-line-cyan" markerEnd="url(#arr-c)" />

              {/* DNA tytułu -> Generator */}
              <path d="M 440 370 L 440 240 L 470 240" stroke="#c084fc" strokeWidth="2.5" fill="none" markerEnd="url(#arr-r)" />

              {/* Generator -> Graf sceny */}
              <path d="M 620 210 L 670 210" stroke="#e1262f" strokeWidth="3" fill="none" className="pulse-line-crimson" markerEnd="url(#arr-r)" />

              {/* Graf sceny -> Twarda bramka */}
              <path d="M 800 210 L 850 210" stroke="#eab308" strokeWidth="2.5" fill="none" className="pulse-line-gold" markerEnd="url(#arr-g)" />

              {/* Twarda bramka ZDANA -> Sędzia VLM */}
              <path d="M 920 260 L 920 330" stroke="#eab308" strokeWidth="2.5" fill="none" className="pulse-line-gold" markerEnd="url(#arr-g)" />

              {/* Pętla odrzucenia (Bramka FAIL -> zwrot do generatora) */}
              <path d="M 920 160 L 920 70 L 545 70 L 545 160" stroke="#ef4444" strokeWidth="2" fill="none" className="fail-return-line" markerEnd="url(#arr-r)" />

              {/* Sędzia VLM -> Wyjścia A i B */}
              <path d="M 980 370 L 1020 370 L 1020 310 L 1040 310" stroke="#34d399" strokeWidth="2.5" fill="none" className="pulse-line-green" markerEnd="url(#arr-e)" />
              <path d="M 980 390 L 1020 390 L 1020 440 L 1040 440" stroke="#34d399" strokeWidth="2.5" fill="none" className="pulse-line-green" markerEnd="url(#arr-e)" />

              {/* Etykieta pętli zwrotnej */}
              <rect x="610" y="52" width="240" height="26" rx="6" fill="#180c10" stroke="#ef4444" strokeWidth="1" />
              <text x="730" y="69" fill="#f87171" fontSize="10.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
                Błąd geometrii: ponowne ułożenie
              </text>
            </svg>

            {/* Wizualne kafelki węzłów rozmieszczone w siatce */}
            <div className="grid grid-cols-5 gap-5 relative z-10 mt-[-460px]">
              
              {/* Kolumna 1: Redakcja */}
              <div className="space-y-4">
                <button 
                  onClick={() => setSelectedNode('ingest')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'ingest' ? 'bg-cyan-950/80 border-cyan-400 ring-2 ring-cyan-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-cyan-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-cyan-400 font-bold mb-1">Krok 1: wejście</div>
                  <div className="text-sm font-bold text-white">Redakcja i materiały</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Teksty, hierarchia tematów (lead, second, briefs) i zdjęcia.</div>
                </button>

                <button 
                  onClick={() => setSelectedNode('writer')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'writer' ? 'bg-cyan-950/80 border-cyan-400 ring-2 ring-cyan-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-cyan-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-cyan-400 font-bold mb-1">Moduł 1A</div>
                  <div className="text-sm font-bold text-white">Moduł adiustacji tekstu</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Dopasowanie słów do ramy makiety bez halucynacji.</div>
                </button>

                <button 
                  onClick={() => setSelectedNode('gemini')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'gemini' ? 'bg-cyan-950/80 border-cyan-400 ring-2 ring-cyan-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-cyan-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-cyan-400 font-bold mb-1">Moduł 1B: wizja AI</div>
                  <div className="text-sm font-bold text-white">Google Gemini AI</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Automatyczne wycinanie tła i wektoryzacja konturu postaci.</div>
                </button>
              </div>

              {/* Kolumna 2: Sterowanie TitleDNA */}
              <div className="flex flex-col justify-end">
                <button 
                  onClick={() => setSelectedNode('dna')}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${selectedNode === 'dna' ? 'bg-purple-950/80 border-purple-400 ring-2 ring-purple-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-purple-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-purple-400 font-bold mb-1">Krok 2: gramatyka tytułu</div>
                  <div className="text-sm font-bold text-white">Archetyp i siatka TitleDNA</div>
                  <div className="text-[11px] text-ink-300 mt-1 font-mono">
                    Aktywny: <strong className="text-purple-300">{archetypeLabel}</strong>
                  </div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">
                    Siatka {columnsCount} kolumn, linia bazowa {baselinePt} pt, reguły foto i budżet napięcia.
                  </div>
                </button>
              </div>

              {/* Kolumna 3: Generator makiety i solver */}
              <div className="flex flex-col justify-center">
                <button 
                  onClick={() => setSelectedNode('generator')}
                  className={`w-full text-left p-4 rounded-xl border transition-all shadow-lg ${selectedNode === 'generator' ? 'bg-red-950/90 border-editorial-crimson ring-2 ring-editorial-crimson/40' : 'bg-ink-900/95 border-editorial-crimson/50 hover:border-editorial-crimson'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-editorial-crimson font-bold mb-1 flex items-center justify-between">
                    <span>Krok 3: serce silnika</span>
                    <span className="w-2 h-2 rounded-full bg-editorial-crimson animate-ping" />
                  </div>
                  <div className="text-base font-bold text-white">Generator makiety i solver</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">
                    Eksploruje układ strony od zera. Oblewa kontury postaci, tworzy pasy zapowiedzi i boczne notatki.
                  </div>
                  <div className="mt-2.5 pt-2 border-t border-ink-800 text-[10px] text-ink-400 space-y-0.5">
                    <div>• Infografiki prasowe SVG</div>
                    <div>• Odsyłacze stron (jump lines)</div>
                    <div>• Polska mikrotypografia (niełamliwe spacje)</div>
                  </div>
                </button>
              </div>

              {/* Kolumna 4: Graf sceny i dwuwarstwowy krytyk */}
              <div className="space-y-4">
                <button 
                  onClick={() => setSelectedNode('scenegraph')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'scenegraph' ? 'bg-amber-950/80 border-amber-400 ring-2 ring-amber-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-amber-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-amber-400 font-bold mb-1">Krok 4: model sceny</div>
                  <div className="text-sm font-bold text-white">Graf sceny (JSON)</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Obiektowy zapis pozycji [x, y, w, h], warstw i stylów.</div>
                </button>

                <button 
                  onClick={() => setSelectedNode('hardgate')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'hardgate' ? 'bg-amber-950/80 border-amber-400 ring-2 ring-amber-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-amber-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-amber-400 font-bold mb-1">Krok 5A: bramka twarda</div>
                  <div className="text-sm font-bold text-white">Bramka Pass / Fail</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Bezwzględny test: brak kolizji, zero wiszących spójników, limit farby TAC.</div>
                </button>

                <button 
                  onClick={() => setSelectedNode('taste')}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${selectedNode === 'taste' ? 'bg-amber-950/80 border-amber-400 ring-2 ring-amber-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-amber-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-amber-400 font-bold mb-1">Krok 5B: miękki gust</div>
                  <div className="text-sm font-bold text-white">Sędzia VLM i pętla gustu</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Ocena estetyki, nauka preferencji dyrektora i anty-kopiowanie.</div>
                </button>
              </div>

              {/* Kolumna 5: Podwójne wyjście hybrydowe */}
              <div className="space-y-4">
                <button 
                  onClick={() => setSelectedNode('browserpdf')}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${selectedNode === 'browserpdf' ? 'bg-emerald-950/80 border-emerald-400 ring-2 ring-emerald-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-emerald-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-emerald-400 font-bold mb-1">Ścieżka szybka</div>
                  <div className="text-sm font-bold text-white">Błyskawiczny PDF</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Wektorowy SVG generowany bezpośrednio w przeglądarce bez czekania.</div>
                </button>

                <button 
                  onClick={() => setSelectedNode('dtp')}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${selectedNode === 'dtp' ? 'bg-emerald-950/80 border-emerald-400 ring-2 ring-emerald-400/30' : 'bg-ink-900/90 border-ink-800 hover:border-emerald-500/50'}`}
                >
                  <div className="text-[10px] font-mono uppercase text-emerald-400 font-bold mb-1">Ścieżka DTP</div>
                  <div className="text-sm font-bold text-white">InDesign IDML & PDF/X</div>
                  <div className="text-[11px] text-ink-400 mt-1 leading-tight">Produkcyjny plik naświetleniowy do profesjonalnej drukarni.</div>
                </button>
              </div>

            </div>
          </div>
        </div>

        {/* Szczegółowy opis klikniętego węzła */}
        {selectedNode && (
          <div className="mt-5 p-4 rounded-xl bg-ink-900/80 border border-ink-700 animate-fade-in text-xs text-ink-200 flex items-start justify-between gap-4">
            <div>
              <strong className="text-white block text-sm mb-1">
                {selectedNode === 'ingest' && 'Wejście i redakcja materiałów:'}
                {selectedNode === 'writer' && 'Moduł adiustacji tekstu (Editorial Writer):'}
                {selectedNode === 'gemini' && 'Szparowanie w Google Gemini AI Vision:'}
                {selectedNode === 'dna' && `Gramatyka TitleDNA dla stylu ${archetypeLabel}:`}
                {selectedNode === 'generator' && 'Generator makiety i solver geometryczny:'}
                {selectedNode === 'scenegraph' && 'Abstrakcyjny graf sceny (Scene Graph JSON):'}
                {selectedNode === 'hardgate' && 'Twarda bramka zgodności (Pass/Fail):'}
                {selectedNode === 'taste' && 'Sędzia wzrokowy VLM i pętla gustu dyrektora artystycznego:'}
                {selectedNode === 'browserpdf' && 'Błyskawiczny PDF wektorowy w przeglądarce:'}
                {selectedNode === 'dtp' && 'Produkcyjny eksport DTP (Adobe InDesign IDML i PDF/X):'}
              </strong>
              <span className="text-ink-400 leading-relaxed">
                {selectedNode === 'ingest' && 'W tym kroku redaktor wprowadza materiały do wydania. Silnik przypisuje wagę otwarcie (lead), materiały drugorzędne (second) oraz krótkie notatki (briefs).'}
                {selectedNode === 'writer' && 'Dopasowuje długość tekstów do fizycznej siatki. Bezwzględna reguła: zero halucynacji. Tekst może być skracany, ale zakazane jest dopisywanie nieistniejących faktów.'}
                {selectedNode === 'gemini' && 'Multimodalny model AI analizuje zdjęcie, odcina tło i tworzy wektorowy kontur postaci, wokół którego tekst w gazecie opływa z naturalnym marginesem.'}
                {selectedNode === 'dna' && `Aktualna gazeta używa profilu ${archetypeLabel}. Siatka dzieli stronę na ${columnsCount} szpalt z odstępem ${gutterMm} mm. Tekst trzyma się linii bazowej co ${baselinePt} pt, a budżet napięcia wynosi ${energyScore.toFixed(2)}.`}
                {selectedNode === 'generator' && 'Silnik nigdy nie używa sztywnych szablonów. Eksploruje tysiące wariantów geometrycznych, wstrzykując infografiki SVG, odsyłacze stron (jump lines) i twarde spacje pod spójnikami.'}
                {selectedNode === 'scenegraph' && 'Uniwersalna reprezentacja matematyczna strony. Wszystkie ramki mają precyzyjne współrzędne w milimetrach [x, y, w, h] oraz zdefiniowane warstwy Z.'}
                {selectedNode === 'hardgate' && 'Matematyczny filtr. Jeśli tekst nachodzi na zdjęcie, brakuje dominanty lub występuje wiszący spójnik – propozycja jest natychmiast odrzucana i generator układa ją ponownie.'}
                {selectedNode === 'taste' && 'Sztuczna inteligencja z wyuczonym gustem człowieka ocenia balans bieli, czytelność i upewnia się, że strona nie kopiuje żadnego istniejącego tytułu z korpusu 1041 stron.'}
                {selectedNode === 'browserpdf' && 'Dzięki renderingowi SVG i stylom @page przeglądarka tworzy idealnie ostry, wektorowy plik PDF bez obciążania serwera i bez opóźnień sieciowych.'}
                {selectedNode === 'dtp' && 'Eksportuje projekt do pliku .idml z zachowanymi stylami akapitowymi, połączonymi ramkami tekstowymi oraz ścieżkami obcinającymi dla naświetlarni offsetowej.'}
              </span>
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-ink-500 hover:text-ink-100 text-xs font-mono shrink-0">
              [zamknij]
            </button>
          </div>
        )}
      </div>

      {/* Przewodnik krok po kroku z reaktywnymi danymi */}
      <div className="space-y-6">
        <h2 className="text-xl font-bold font-headline text-white flex items-center gap-2.5">
          <HelpCircle className="w-5 h-5 text-editorial-crimson" />
          Kompletny przewodnik po tworzeniu gazety
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Krok 1 */}
          <div className="bg-ink-950 border border-ink-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-lg bg-editorial-crimson/20 text-editorial-crimson flex items-center justify-center font-bold text-sm">1</span>
              <h3 className="font-bold text-white text-base">Wybór charakteru i stylu</h3>
            </div>
            <p className="text-xs text-ink-400 leading-relaxed">
              Zamiast sztywnego szablonu wybierasz archetyp z bazy wiedzy Zecro. Dla Twojej aktualnej gazety wybrany jest styl <strong className="text-white">{archetypeLabel}</strong>. 
              Możesz w każdej chwili przejść do zakładki <strong className="text-editorial-crimson cursor-pointer" onClick={() => setActiveTab('dna')}>Styl i zasady gazety</strong>, aby dostosować proporcje, kolorystykę i krój pisma.
            </p>
            <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-500">
              <Grid className="w-3.5 h-3.5" /> Aktualna siatka: {columnsCount} kolumny · odstęp {gutterMm} mm
            </div>
          </div>

          {/* Krok 2 */}
          <div className="bg-ink-950 border border-ink-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-lg bg-editorial-crimson/20 text-editorial-crimson flex items-center justify-center font-bold text-sm">2</span>
              <h3 className="font-bold text-white text-base">Wprowadzenie tekstów i zdjęć</h3>
            </div>
            <p className="text-xs text-ink-400 leading-relaxed">
              W zakładce <strong className="text-editorial-crimson cursor-pointer" onClick={() => setActiveTab('generate')}>Materiały i strona</strong> wpisujesz artykuł główny (otwarcie) oraz materiały towarzyszące. 
              Dodajesz fotografie reporterskie — system automatycznie bada ich rozdzielczość i sugeruje optymalne kadrowanie.
            </p>
            <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-500">
              <Camera className="w-3.5 h-3.5" /> Silnik wizyjny: Google Gemini AI Vision (automatyczne wycinanie)
            </div>
          </div>

          {/* Krok 3 */}
          <div className="bg-ink-950 border border-ink-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-lg bg-editorial-crimson/20 text-editorial-crimson flex items-center justify-center font-bold text-sm">3</span>
              <h3 className="font-bold text-white text-base">Generowanie i eksploracja</h3>
            </div>
            <p className="text-xs text-ink-400 leading-relaxed">
              Klikasz przycisk generowania. Silnik matematyczny układa stronę od zera, testując dziesiątki kombinacji. 
              Automatycznie wstrzykuje infografiki SVG, odsyłacze stron (jump lines) i usuwa wiszące spójniki na końcach wierszy.
            </p>
            <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-500">
              <Cpu className="w-3.5 h-3.5" /> Algorytm: Plan Composer & Modular Grid Solver
            </div>
          </div>

          {/* Krok 4 */}
          <div className="bg-ink-950 border border-ink-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-lg bg-editorial-crimson/20 text-editorial-crimson flex items-center justify-center font-bold text-sm">4</span>
              <h3 className="font-bold text-white text-base">Selekcja i eksport</h3>
            </div>
            <p className="text-xs text-ink-400 leading-relaxed">
              W zakładce <strong className="text-editorial-crimson cursor-pointer" onClick={() => setActiveTab('gallery')}>Warianty</strong> oglądasz propozycje, które przeszły twardego krytyka. 
              Wybierasz najlepszą i pobierasz natychmiastowy plik PDF bezpośrednio z przeglądarki lub generujesz produkcyjny pakiet Adobe InDesign IDML.
            </p>
            <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-500">
              <Download className="w-3.5 h-3.5" /> Formaty: Wektorowy PDF (przeglądarka) + IDML + Prepress PDF/X
            </div>
          </div>

        </div>
      </div>

    </div>
  );
};
