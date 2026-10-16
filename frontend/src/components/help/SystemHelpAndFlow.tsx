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
  Grid,
  BookOpen,
  SlidersHorizontal,
  Type,
  FileText,
  ChevronDown,
  Info,
  ExternalLink,
  Zap,
  Check
} from 'lucide-react';
import { clsx } from 'clsx';

type HelpTab = 'flow' | 'guide' | 'faq' | 'glossary';

export const SystemHelpAndFlow: React.FC = () => {
  const { activeProject, dna, setActiveTab } = useProject();
  const [activeHelpTab, setActiveHelpTab] = useState<HelpTab>('flow');
  const [selectedNode, setSelectedNode] = useState<string>('generator');
  const [expandedFaq, setExpandedFaq] = useState<number | null>(0);

  // Dynamiczne, reaktywne parametry aktywnego stylu i projektu
  const style = editorialStyle(activeProject?.editorialCharacter);
  const archetypeLabel = style.name;
  const columnsCount = dna?.grid.columns || activeProject?.dimensions.columnsCount || 5;
  const gutterMm = dna?.grid.gutterMm || activeProject?.dimensions.gutterMm || 4;
  const baselinePt = dna?.grid.baselineGridPt || 9.5;
  const energyScore = typeof dna?.pageEnergyBudget === 'object' 
    ? (dna.pageEnergyBudget?.maxTensionScore ?? 0.75) 
    : (typeof dna?.pageEnergyBudget === 'number' ? dna.pageEnergyBudget : (style.energy ?? 0.75));

  const faqItems = [
    {
      q: 'Co zrobić, gdy artykuł nie mieści się w wyznaczonej szpalcie?',
      a: 'W Zecro działa moduł Editorial Writer (adiustacja tekstu). System analizuje dostępną powierzchnię i może inteligentnie dopasować długość tekstu lub zaproponować odsyłacz (jump line) na kolejną stronę. Nigdy nie dopisuje zmyślonych informacji (zero halucynacji).'
    },
    {
      q: 'Jak działa automatyczne szparowanie postaci ze zdjęć?',
      a: 'Multimodalny model Google Gemini AI Vision wykrywa postać pierwszoplanową na zdjęciu reporterskim, odcina tło i generuje wektorowy obrys (ścieżkę polygon). Generator makiety wykorzystuje go do oblewania tekstem za pomocą właściwości shape-outside.'
    },
    {
      q: 'Czym jest budżet energii i napięcie makiety?',
      a: 'Każdy archetyp prasowy ma zdefiniowany dopuszczalny poziom dynamiki kompozycji. Konserwatywny dziennik ma niski budżet (spokojna, symetryczna siatka), natomiast nowoczesny magazyn czy tabloid ma wysoki budżet (asymetrie, ukośne linie, wybicia i szparowania przekraczające marginesy).'
    },
    {
      q: 'Dlaczego propozycja układu może zostać odrzucona przez bramkę jakości?',
      a: 'Bramka twarda (Pass/Fail) bezwzględnie weryfikuje inwarianty: czy tekst nie nachodzi na twarz ze zdjęcia, czy zachowano marginesy wewnętrzne, czy nie ma wiszących spójników na końcach wierszy oraz czy suma farb (TAC) nie przekracza dopuszczalnego limitu dla papieru gazetowego. Jeśli układ ma błąd, jest natychmiast odrzucany, a generator układa go od nowa.'
    },
    {
      q: 'Jak otworzyć i edytować stronę w Adobe InDesign?',
      a: 'W zakładce Warianty lub podsumowaniu generowania wybierz opcję Eksport InDesign IDML. Pobrana paczka zawiera czyste ramki ze stylami akapitowymi, połączone wątki tekstowe oraz osadzone ścieżki obcinania zdjęć, gotowe do dalszej pracy grafika.'
    },
    {
      q: 'Jak przygotować gazetę do druku w drukarni offsetowej?',
      a: 'Zecro generuje pliki PDF/X zgodne ze standardami prepress: tekst składany w 100% z czerni (K), profil barwny dla papieru gazetowego (np. ISOnewspaper26v4) oraz automatyczna kontrola limitu farby TAC do 240%.'
    },
    {
      q: 'W jaki sposób system dba o to, by nie kopiować cudzych makiet?',
      a: 'Silnik nie korzysta ze statycznych szablonów. Każda strona jest generowana od zera na podstawie gramatyki TitleDNA, a moduł anty-kopiowania porównuje rozkład ramek z bazą ponad 1000 historycznych wydań, karząc rozwiązania zbyt zbliżone do istniejących stron.'
    }
  ];

  const glossaryItems = [
    { term: 'TitleDNA', desc: 'Sformalizowana gramatyka tytułu prasowego zapisana w formacie danych: modułowa siatka, skala typograficzna, paleta farb, reguły traktowania zdjęć oraz budżet energii.' },
    { term: 'Szparowanie', desc: 'Precyzyjne wycięcie obiektu lub postaci z tła fotografii w celu wtopienia sylwetki w tekst lub wyjścia poza obrys ramki modułowej.' },
    { term: 'Oblewanie (text wrap)', desc: 'Układanie wierszy tekstu wzdłuż zakrzywionego konturu wyciętej postaci z zachowaniem stałego marginesu oddechowego (w Zecro realizowane przez shape-outside).' },
    { term: 'Linia bazowa (baseline grid)', desc: 'Niewidoczna siatka poziomych linii co określoną liczbę punktów (np. 9.5 pt), do której wyrównana jest podstawa liter we wszystkich sąsiadujących szpaltach.' },
    { term: 'Odsyłacz (jump line)', desc: 'Wskazówka na końcu skróconego artykułu (np. „Dokończenie na s. 4”) oraz nagłówek kontynuacji w docelowym miejscu.' },
    { term: 'Żywa pagina', desc: 'Pasek na górze lub dole strony zawierający numer kolumny, datę, nazwę tytułu oraz nazwę rubryki lub działu tematycznego.' },
    { term: 'Limit farby TAC', desc: 'Total Area Coverage – maksymalne sumaryczne nasycenie farb CMYK (w druku gazetowym zazwyczaj do 220–240%), zapobiegające przebijaniu farby przez cienki papier.' },
    { term: 'Graf sceny (Scene Graph)', desc: 'Abstrakcyjna, obiektowa reprezentacja makiety w formacie JSON, określająca dokładne współrzędne [x, y, w, h], warstwy i powiązania między elementami.' }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in text-ink-100">
      
      {/* Nagłówek Działu Pomoc */}
      <div className="bg-white border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <img src="/zecro-logo.png" alt="Zecro" className="h-12 w-auto object-contain" />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-blue-50 text-editorial-crimson border border-editorial-crimson/20">
                  Centrum wiedzy redakcyjnej
                </span>
                <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Stan na żywo
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold font-headline tracking-tight text-ink-100">
                Dział Pomoc i jak działa Zecro
              </h1>
              <p className="text-sm text-ink-500 mt-1 max-w-2xl">
                Wszystko o zasadach generowania gazety, architekturze silnika, eliminacji błędów i przygotowaniu materiałów do druku.
              </p>
            </div>
          </div>

          {/* Aktywny kontekst gazety */}
          <div className="bg-ink-950/80 border border-ink-800 rounded-xl p-4 text-xs font-mono shrink-0 min-w-[260px]">
            <div className="text-ink-400 font-sans font-semibold mb-2 flex items-center justify-between">
              <span>Aktywna gazeta:</span>
              <span className="text-ink-100 font-bold truncate max-w-[140px]">{activeProject?.name || 'Domyślna makieta'}</span>
            </div>
            <div className="space-y-1.5 text-ink-300">
              <div className="flex justify-between">
                <span className="text-ink-400">Styl / archetyp:</span>
                <span className="text-editorial-crimson font-bold">{archetypeLabel}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Siatka strony:</span>
                <span>{columnsCount} szpalt (odstęp {gutterMm} mm)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Linia bazowa:</span>
                <span>{baselinePt} pt</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Budżet energii:</span>
                <span>{energyScore.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Zakładki nawigacyjne Działu Pomoc */}
        <div className="mt-8 pt-6 border-t border-ink-800 flex flex-wrap gap-2">
          <button
            onClick={() => setActiveHelpTab('flow')}
            className={clsx(
              "px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2",
              activeHelpTab === 'flow'
                ? "bg-editorial-crimson text-white shadow-xs"
                : "bg-ink-950 text-ink-300 hover:text-ink-100 hover:bg-ink-950/80 border border-ink-800"
            )}
          >
            <Sparkles className="w-4 h-4" />
            Schemat: jak działa system
          </button>

          <button
            onClick={() => setActiveHelpTab('guide')}
            className={clsx(
              "px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2",
              activeHelpTab === 'guide'
                ? "bg-editorial-crimson text-white shadow-xs"
                : "bg-ink-950 text-ink-300 hover:text-ink-100 hover:bg-ink-950/80 border border-ink-800"
            )}
          >
            <BookOpen className="w-4 h-4" />
            Przewodnik krok po kroku
          </button>

          <button
            onClick={() => setActiveHelpTab('faq')}
            className={clsx(
              "px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2",
              activeHelpTab === 'faq'
                ? "bg-editorial-crimson text-white shadow-xs"
                : "bg-ink-950 text-ink-300 hover:text-ink-100 hover:bg-ink-950/80 border border-ink-800"
            )}
          >
            <HelpCircle className="w-4 h-4" />
            Częste pytania (FAQ)
          </button>

          <button
            onClick={() => setActiveHelpTab('glossary')}
            className={clsx(
              "px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2",
              activeHelpTab === 'glossary'
                ? "bg-editorial-crimson text-white shadow-xs"
                : "bg-ink-950 text-ink-300 hover:text-ink-100 hover:bg-ink-950/80 border border-ink-800"
            )}
          >
            <Type className="w-4 h-4" />
            Słownik pojęć prasowych
          </button>
        </div>
      </div>

      {/* Widok 1: Animowany, czysty schemat przepływu danych bez nakładania się */}
      {activeHelpTab === 'flow' && (
        <div className="space-y-6">
          <div className="bg-white border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-xs">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="text-xl font-bold text-ink-100 font-headline flex items-center gap-2.5">
                  <Sparkles className="w-5 h-5 text-editorial-crimson" />
                  Przepływ danych w silniku Zecro
                </h2>
                <p className="text-xs text-ink-500 mt-1 max-w-3xl">
                  Informacje przepływają sekwencyjnie przez 5 wyspecjalizowanych etapów. Kliknij dowolny moduł, aby sprawdzić jego reguły i parametry na żywo.
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono text-ink-500 bg-ink-950 px-3 py-1.5 rounded-lg border border-ink-800 shrink-0">
                <span className="w-2 h-2 rounded-full bg-editorial-crimson animate-ping" />
                Interaktywny model architektury
              </div>
            </div>

            {/* Pasek przepływu - 5 kolumn z wyraźnymi złączami i animowanymi impulsami */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-stretch">
              
              {/* Etap 1: Wejście redakcyjne */}
              <div className="flex flex-col space-y-3 p-4 rounded-xl bg-ink-950/60 border border-ink-800">
                <div className="flex items-center justify-between pb-2 border-b border-ink-800 text-xs font-mono">
                  <span className="font-bold text-cyan-600">Etap 1: wejście</span>
                  <span className="text-[10px] text-ink-400">Redakcja</span>
                </div>

                <button
                  onClick={() => setSelectedNode('ingest')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'ingest'
                      ? "bg-white border-cyan-500 shadow-xs ring-2 ring-cyan-500/20"
                      : "bg-white border-ink-800 hover:border-cyan-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-cyan-600 font-semibold">1.1 Materiały</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Hierarchia tematów</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Podział na lead, second i krótkie notatki.</div>
                </button>

                <button
                  onClick={() => setSelectedNode('writer')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'writer'
                      ? "bg-white border-cyan-500 shadow-xs ring-2 ring-cyan-500/20"
                      : "bg-white border-ink-800 hover:border-cyan-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-cyan-600 font-semibold">1.2 Adiustacja</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Editorial Writer</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Dopasowanie długości tekstu bez halucynacji.</div>
                </button>

                <button
                  onClick={() => setSelectedNode('gemini')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'gemini'
                      ? "bg-white border-cyan-500 shadow-xs ring-2 ring-cyan-500/20"
                      : "bg-white border-ink-800 hover:border-cyan-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-cyan-600 font-semibold">1.3 Wizja AI</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Szparowanie zdjęć</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Odcinanie tła i wektorowy obrys sylwetki.</div>
                </button>

                <div className="mt-auto pt-2 flex items-center justify-center text-cyan-600 text-xs font-mono font-bold">
                  Dane tekstu i masek <ArrowRight className="w-3.5 h-3.5 ml-1 hidden lg:inline" />
                </div>
              </div>

              {/* Etap 2: Gramatyka TitleDNA */}
              <div className="flex flex-col space-y-3 p-4 rounded-xl bg-ink-950/60 border border-ink-800">
                <div className="flex items-center justify-between pb-2 border-b border-ink-800 text-xs font-mono">
                  <span className="font-bold text-purple-600">Etap 2: reguły</span>
                  <span className="text-[10px] text-ink-400">TitleDNA</span>
                </div>

                <button
                  onClick={() => setSelectedNode('dna')}
                  className={clsx(
                    "text-left p-3.5 rounded-lg border transition-all h-full flex flex-col justify-between",
                    selectedNode === 'dna'
                      ? "bg-white border-purple-500 shadow-xs ring-2 ring-purple-500/20"
                      : "bg-white border-ink-800 hover:border-purple-400"
                  )}
                >
                  <div>
                    <div className="text-[10px] font-mono text-purple-600 font-semibold">Gramatyka tytułu</div>
                    <div className="text-xs font-bold text-ink-100 mt-0.5">Archetyp: {archetypeLabel}</div>
                    <div className="text-[11px] text-ink-500 mt-1.5 leading-snug">
                      Siatka modułowa, linia bazowa, skala krojów pisma i katalog dopuszczalnych transgresji.
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-ink-800 text-[10px] font-mono text-ink-400 space-y-1">
                    <div>• Szpalty: {columnsCount} (odstęp {gutterMm} mm)</div>
                    <div>• Linia bazowa: {baselinePt} pt</div>
                    <div>• Budżet energii: {energyScore.toFixed(2)}</div>
                  </div>
                </button>

                <div className="mt-auto pt-2 flex items-center justify-center text-purple-600 text-xs font-mono font-bold">
                  Więzy i styl <ArrowRight className="w-3.5 h-3.5 ml-1 hidden lg:inline" />
                </div>
              </div>

              {/* Etap 3: Generator makiety i solver */}
              <div className="flex flex-col space-y-3 p-4 rounded-xl bg-blue-50/40 border border-editorial-crimson/30">
                <div className="flex items-center justify-between pb-2 border-b border-editorial-crimson/20 text-xs font-mono">
                  <span className="font-bold text-editorial-crimson">Etap 3: serce</span>
                  <span className="text-[10px] text-editorial-crimson">Solver</span>
                </div>

                <button
                  onClick={() => setSelectedNode('generator')}
                  className={clsx(
                    "text-left p-3.5 rounded-lg border transition-all h-full flex flex-col justify-between",
                    selectedNode === 'generator'
                      ? "bg-white border-editorial-crimson shadow-xs ring-2 ring-editorial-crimson/20"
                      : "bg-white border-editorial-crimson/30 hover:border-editorial-crimson"
                  )}
                >
                  <div>
                    <div className="text-[10px] font-mono text-editorial-crimson font-semibold flex items-center justify-between">
                      <span>Plan Composer</span>
                      <span className="w-2 h-2 rounded-full bg-editorial-crimson animate-pulse" />
                    </div>
                    <div className="text-sm font-bold text-ink-100 mt-0.5">Generator makiety</div>
                    <div className="text-[11px] text-ink-500 mt-1.5 leading-snug">
                      Eksploruje tysiące układów geometrycznych od zera. Oblicza oblewanie postaci tekstem i wstrzykuje infografiki.
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-editorial-crimson/20 text-[10px] text-ink-500 space-y-1">
                    <div>• Oblewanie sylwetki (shape-outside)</div>
                    <div>• Odsyłacze stron (jump lines)</div>
                    <div>• Spacje niełamliwe (brak sierotek)</div>
                  </div>
                </button>

                <div className="mt-auto pt-2 flex items-center justify-center text-editorial-crimson text-xs font-mono font-bold">
                  Graf sceny JSON <ArrowRight className="w-3.5 h-3.5 ml-1 hidden lg:inline" />
                </div>
              </div>

              {/* Etap 4: Dwuwarstwowy krytyk */}
              <div className="flex flex-col space-y-3 p-4 rounded-xl bg-ink-950/60 border border-ink-800">
                <div className="flex items-center justify-between pb-2 border-b border-ink-800 text-xs font-mono">
                  <span className="font-bold text-amber-600">Etap 4: selekcja</span>
                  <span className="text-[10px] text-ink-400">Krytyk</span>
                </div>

                <button
                  onClick={() => setSelectedNode('hardgate')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'hardgate'
                      ? "bg-white border-amber-500 shadow-xs ring-2 ring-amber-500/20"
                      : "bg-white border-ink-800 hover:border-amber-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-amber-600 font-semibold">4.1 Bramka twarda</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Test Pass / Fail</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Zero kolizji, limit farby TAC, poprawność mikroskopowa.</div>
                </button>

                <button
                  onClick={() => setSelectedNode('taste')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'taste'
                      ? "bg-white border-amber-500 shadow-xs ring-2 ring-amber-500/20"
                      : "bg-white border-ink-800 hover:border-amber-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-amber-600 font-semibold">4.2 Miękki gust</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Sędzia VLM & DPO</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Ocena balansu bieli i metryka anty-plagiatowa.</div>
                </button>

                <div className="mt-auto pt-2 flex items-center justify-center text-amber-600 text-xs font-mono font-bold">
                  Zatwierdzony wariant <ArrowRight className="w-3.5 h-3.5 ml-1 hidden lg:inline" />
                </div>
              </div>

              {/* Etap 5: Hybrydowe wyjście */}
              <div className="flex flex-col space-y-3 p-4 rounded-xl bg-ink-950/60 border border-ink-800">
                <div className="flex items-center justify-between pb-2 border-b border-ink-800 text-xs font-mono">
                  <span className="font-bold text-emerald-600">Etap 5: eksport</span>
                  <span className="text-[10px] text-ink-400">Publikacja</span>
                </div>

                <button
                  onClick={() => setSelectedNode('browserpdf')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'browserpdf'
                      ? "bg-white border-emerald-500 shadow-xs ring-2 ring-emerald-500/20"
                      : "bg-white border-ink-800 hover:border-emerald-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-emerald-600 font-semibold">5.1 Szybki podgląd</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">Wektorowy PDF</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Generowany bezpośrednio w przeglądarce bez czekania.</div>
                </button>

                <button
                  onClick={() => setSelectedNode('dtp')}
                  className={clsx(
                    "text-left p-3 rounded-lg border transition-all",
                    selectedNode === 'dtp'
                      ? "bg-white border-emerald-500 shadow-xs ring-2 ring-emerald-500/20"
                      : "bg-white border-ink-800 hover:border-emerald-400"
                  )}
                >
                  <div className="text-[10px] font-mono text-emerald-600 font-semibold">5.2 Produkcja DTP</div>
                  <div className="text-xs font-bold text-ink-100 mt-0.5">InDesign IDML & PDF/X</div>
                  <div className="text-[11px] text-ink-500 mt-1 leading-snug">Plik naświetleniowy do profesjonalnej drukarni offsetowej.</div>
                </button>

                <div className="mt-auto pt-2 flex items-center justify-center text-emerald-600 text-xs font-mono font-bold">
                  Gotowe do druku
                </div>
              </div>

            </div>

            {/* Pętla autokorekty (wyjaśnienie braku kolizji i powrotu do generatora) */}
            <div className="mt-5 p-4 rounded-xl bg-red-50/70 border border-red-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-red-100 text-red-700 flex items-center justify-center shrink-0">
                  <RotateCcw className="w-4 h-4" />
                </div>
                <div>
                  <strong className="text-red-900 font-bold block">Pętla autokorekty (bramka odrzuceń):</strong>
                  <span className="text-red-700">
                    Jeśli twarda bramka (Etap 4.1) wykryje kolizję ramki z grafiką lub błąd techniczny – makieta natychmiast wraca do Generatora (Etap 3) z nowym ziarnem losowania.
                  </span>
                </div>
              </div>
              <span className="font-mono text-[11px] px-2.5 py-1 rounded-md bg-white border border-red-200 text-red-700 font-semibold shrink-0">
                100% gwarancji czytelności
              </span>
            </div>

            {/* Inspektor wybranego węzła */}
            <div className="mt-6 p-5 rounded-xl bg-ink-950/70 border border-ink-800 text-xs">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-ink-900 border border-ink-800 text-ink-400">
                      Inspektor modułu
                    </span>
                    <h3 className="text-sm font-bold text-ink-100">
                      {selectedNode === 'ingest' && 'Wejście redakcyjne i hierarchia materiałów'}
                      {selectedNode === 'writer' && 'Moduł adiustacji tekstu (Editorial Writer)'}
                      {selectedNode === 'gemini' && 'Szparowanie i wektoryzacja konturu w Google Gemini AI Vision'}
                      {selectedNode === 'dna' && `Gramatyka TitleDNA dla stylu: ${archetypeLabel}`}
                      {selectedNode === 'generator' && 'Generator makiety i solver geometryczny (Plan Composer)'}
                      {selectedNode === 'hardgate' && 'Twarda bramka zgodności geometrycznej (Pass / Fail)'}
                      {selectedNode === 'taste' && 'Sędzia wzrokowy VLM i pętla gustu dyrektora artystycznego'}
                      {selectedNode === 'browserpdf' && 'Błyskawiczny wektorowy PDF w oknie przeglądarki'}
                      {selectedNode === 'dtp' && 'Produkcyjny eksport DTP (Adobe InDesign IDML i prepress PDF/X)'}
                    </h3>
                  </div>

                  <p className="text-ink-400 leading-relaxed max-w-3xl">
                    {selectedNode === 'ingest' && 'Redakcja wprowadza artykuł główny (otwarcie/lead), artykuł towarzyszący oraz notatki informacyjne. Każdy materiał ma przypisany stopień ważności, który decyduje o kolejności i skali na stronie.'}
                    {selectedNode === 'writer' && 'Precyzyjnie dopasowuje objętość tekstu do fizycznej siatki szpalt. Obowiązuje bezwzględna reguła: zero halucynacji. Tekst może być skracany, ale zakazane jest dopisywanie nieistniejących faktów.'}
                    {selectedNode === 'gemini' && 'Multimodalny model wizyjny analizuje zdjęcie, precyzyjnie odcina tło i tworzy wektorowy obrys sylwetki. Na tej podstawie silnik automatycznie generuje margines opływania tekstem wokół postaci.'}
                    {selectedNode === 'dna' && `Aktualna gazeta korzysta z archetypu ${archetypeLabel}. Siatka dzieli kolumnę na ${columnsCount} szpalt o odstępie ${gutterMm} mm. Skład tekstu trzyma się linii bazowej co ${baselinePt} pt, a budżet energii wynosi ${energyScore.toFixed(2)}.`}
                    {selectedNode === 'generator' && 'Serce silnika Zecro. Zamiast statycznych szablonów, algorytm układa stronę od zera: dobiera format winiety, zarządza dominantą wizualną, wstrzykuje infografiki SVG i automatycznie usuwa wiszące spójniki na końcach wierszy.'}
                    {selectedNode === 'hardgate' && 'Matematyczny filtr zgodności. Sprawdza brak kolizji ramek, zachowanie marginesów, czytelność tytułów na tle i limit farby drukarskiej TAC. Układ niespełniający któregokolwiek warunku jest natychmiast odrzucany.'}
                    {selectedNode === 'taste' && 'Model z wyuczonym gustem dyrektora artystycznego ocenia kompozycję, hierarchię wzrokową i upewnia się, że wygenerowana makieta nie kopiuje żadnego istniejącego tytułu z bazy wiedzy.'}
                    {selectedNode === 'browserpdf' && 'Dzięki bezpośredniemu renderingowi SVG oraz regułom CSS Paged Media przeglądarka tworzy wektorowy, idealnie ostry plik PDF bez konieczności czekania na serwer.'}
                    {selectedNode === 'dtp' && 'Eksportuje projekt do natywnego formatu Adobe InDesign (.idml) z zachowanymi stylami akapitowymi, połączonymi ramkami tekstowymi i gotowymi profilami CMYK do naświetlarni offsetowej.'}
                  </p>
                </div>

                <div className="shrink-0 flex flex-col gap-2">
                  {(selectedNode === 'ingest' || selectedNode === 'writer' || selectedNode === 'gemini') && (
                    <button
                      onClick={() => setActiveTab('generate')}
                      className="px-3 py-1.5 rounded-lg bg-editorial-crimson text-white font-semibold text-xs inline-flex items-center gap-1.5"
                    >
                      Przejdź do materiałów <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {selectedNode === 'dna' && (
                    <button
                      onClick={() => setActiveTab('dna')}
                      className="px-3 py-1.5 rounded-lg bg-editorial-crimson text-white font-semibold text-xs inline-flex items-center gap-1.5"
                    >
                      Dostosuj styl TitleDNA <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {(selectedNode === 'generator' || selectedNode === 'hardgate' || selectedNode === 'taste' || selectedNode === 'browserpdf' || selectedNode === 'dtp') && (
                    <button
                      onClick={() => setActiveTab('gallery')}
                      className="px-3 py-1.5 rounded-lg bg-editorial-crimson text-white font-semibold text-xs inline-flex items-center gap-1.5"
                    >
                      Zobacz wygenerowane warianty <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Widok 2: Przewodnik krok po kroku */}
      {activeHelpTab === 'guide' && (
        <div className="space-y-6">
          <div className="bg-white border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-xs">
            <h2 className="text-xl font-bold font-headline text-ink-100 flex items-center gap-2.5 mb-2">
              <BookOpen className="w-5 h-5 text-editorial-crimson" />
              Kompletny przewodnik po tworzeniu gazety w Zecro
            </h2>
            <p className="text-xs text-ink-500 mb-6">
              Krok po kroku: od wyboru stylu, przez wprowadzenie materiałów, aż po gotowy plik do drukarni.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Krok 1 */}
              <div className="p-5 rounded-xl border border-ink-800 bg-ink-950/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-editorial-crimson/10 text-editorial-crimson flex items-center justify-center font-bold text-sm">1</span>
                    <h3 className="font-bold text-ink-100 text-base">Wybór nazwy i charakteru</h3>
                  </div>
                  <button onClick={() => setActiveTab('projects')} className="text-xs font-semibold text-editorial-crimson hover:underline">
                    Moje gazety →
                  </button>
                </div>
                <p className="text-xs text-ink-500 leading-relaxed">
                  Podajesz tytuł wydania, format papieru (np. A3 lub dziennik Berliner) oraz wybierasz archetyp z bazy wiedzy. Aktualny styl to <strong className="text-ink-100">{archetypeLabel}</strong>. Archetyp definiuje charakter pisma, liczbę szpalt i dopuszczalną dynamikę strony.
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-400 border-t border-ink-800">
                  <Grid className="w-3.5 h-3.5" /> Siatka bazowa: {columnsCount} szpalt · margines {gutterMm} mm
                </div>
              </div>

              {/* Krok 2 */}
              <div className="p-5 rounded-xl border border-ink-800 bg-ink-950/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-editorial-crimson/10 text-editorial-crimson flex items-center justify-center font-bold text-sm">2</span>
                    <h3 className="font-bold text-ink-100 text-base">Wprowadzenie tekstów i zdjęć</h3>
                  </div>
                  <button onClick={() => setActiveTab('generate')} className="text-xs font-semibold text-editorial-crimson hover:underline">
                    Materiały →
                  </button>
                </div>
                <p className="text-xs text-ink-500 leading-relaxed">
                  Wpisujesz artykuł główny (otwarcie) oraz materiały towarzyszące. Dodajesz fotografie reporterskie. Narzędzie automatycznie bada ich rozdzielczość i sugeruje optymalne kadrowanie lub szparowanie.
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-400 border-t border-ink-800">
                  <Camera className="w-3.5 h-3.5" /> Wizja AI: automatyczne odcinanie tła
                </div>
              </div>

              {/* Krok 3 */}
              <div className="p-5 rounded-xl border border-ink-800 bg-ink-950/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-editorial-crimson/10 text-editorial-crimson flex items-center justify-center font-bold text-sm">3</span>
                    <h3 className="font-bold text-ink-100 text-base">Generowanie makiety</h3>
                  </div>
                  <button onClick={() => setActiveTab('generate')} className="text-xs font-semibold text-editorial-crimson hover:underline">
                    Generuj stronę →
                  </button>
                </div>
                <p className="text-xs text-ink-500 leading-relaxed">
                  Jednym kliknięciem uruchamiasz kompozytor geometryczny. Algorytm sprawdza setki wariantów, dbając o jedną dominantę wizualną, twarde spacje pod spójnikami (i, w, z, o) oraz oblewanie sylwetek tekstem.
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-400 border-t border-ink-800">
                  <Cpu className="w-3.5 h-3.5" /> Silnik: Plan Composer & Modular Grid Solver
                </div>
              </div>

              {/* Krok 4 */}
              <div className="p-5 rounded-xl border border-ink-800 bg-ink-950/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-editorial-crimson/10 text-editorial-crimson flex items-center justify-center font-bold text-sm">4</span>
                    <h3 className="font-bold text-ink-100 text-base">Wybór i drobne poprawki</h3>
                  </div>
                  <button onClick={() => setActiveTab('gallery')} className="text-xs font-semibold text-editorial-crimson hover:underline">
                    Zobacz propozycje →
                  </button>
                </div>
                <p className="text-xs text-ink-500 leading-relaxed">
                  Przeglądasz wygenerowane propozycje. Każdy wariant został sprawdzony przez twardą bramkę. Możesz porównać je obok siebie, a w razie potrzeby dokonać ręcznej korekty w prostym edytorze.
                </p>
                <div className="pt-2 flex items-center gap-2 text-[11px] font-mono text-ink-400 border-t border-ink-800">
                  <ShieldCheck className="w-3.5 h-3.5" /> Bramka jakości: test kolizji zdany
                </div>
              </div>

              {/* Krok 5 */}
              <div className="p-5 rounded-xl border border-ink-800 bg-ink-950/40 space-y-3 md:col-span-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-editorial-crimson/10 text-editorial-crimson flex items-center justify-center font-bold text-sm">5</span>
                    <h3 className="font-bold text-ink-100 text-base">Eksport do druku i PDF</h3>
                  </div>
                  <button onClick={() => setActiveTab('gallery')} className="text-xs font-semibold text-editorial-crimson hover:underline">
                    Pobierz pliki →
                  </button>
                </div>
                <p className="text-xs text-ink-500 leading-relaxed">
                  Gdy makieta jest gotowa, wybierasz format publikacji: błyskawiczny wektorowy plik PDF bezpośrednio z przeglądarki lub pełną paczkę Adobe InDesign (.idml) z profilami prepress i wektorowymi ścieżkami dla profesjonalnej drukarni.
                </p>
                <div className="pt-2 flex items-center gap-4 text-[11px] font-mono text-ink-400 border-t border-ink-800">
                  <span>Wektorowy PDF (przeglądarka)</span>
                  <span>•</span>
                  <span>Adobe InDesign IDML</span>
                  <span>•</span>
                  <span>Prepress PDF/X-1a</span>
                </div>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* Widok 3: FAQ */}
      {activeHelpTab === 'faq' && (
        <div className="space-y-6">
          <div className="bg-white border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-xs">
            <h2 className="text-xl font-bold font-headline text-ink-100 flex items-center gap-2.5 mb-2">
              <HelpCircle className="w-5 h-5 text-editorial-crimson" />
              Często zadawane pytania (FAQ)
            </h2>
            <p className="text-xs text-ink-500 mb-6">
              Odpowiedzi na najczęstsze pytania redaktorów i projektantów pracujących w systemie Zecro.
            </p>

            <div className="space-y-3">
              {faqItems.map((item, index) => {
                const isOpen = expandedFaq === index;
                return (
                  <div key={index} className="border border-ink-800 rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpandedFaq(isOpen ? null : index)}
                      className="w-full p-4 text-left flex items-center justify-between gap-4 bg-ink-950/40 hover:bg-ink-950 transition-colors"
                    >
                      <span className="font-semibold text-sm text-ink-100">{item.q}</span>
                      <ChevronDown className={clsx("w-4 h-4 text-ink-400 transition-transform shrink-0", isOpen && "rotate-180")} />
                    </button>
                    {isOpen && (
                      <div className="p-4 bg-white text-xs text-ink-500 leading-relaxed border-t border-ink-800">
                        {item.a}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Widok 4: Słownik pojęć prasowych */}
      {activeHelpTab === 'glossary' && (
        <div className="space-y-6">
          <div className="bg-white border border-ink-800 rounded-2xl p-6 sm:p-8 shadow-xs">
            <h2 className="text-xl font-bold font-headline text-ink-100 flex items-center gap-2.5 mb-2">
              <Type className="w-5 h-5 text-editorial-crimson" />
              Słownik pojęć prasowych i DTP
            </h2>
            <p className="text-xs text-ink-500 mb-6">
              Przewodnik po terminologii redakcyjnej i technicznej stosowanej w makietach Zecro.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {glossaryItems.map((item, idx) => (
                <div key={idx} className="p-4 rounded-xl border border-ink-800 bg-ink-950/40 space-y-1.5">
                  <div className="font-mono text-xs font-bold text-editorial-crimson">{item.term}</div>
                  <div className="text-xs text-ink-500 leading-relaxed">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
