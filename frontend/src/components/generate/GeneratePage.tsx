import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { IntakeData, StoryMaterial, PhotoMaterial } from '../../types/material';
import { api } from '../../api/client';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Slider } from '../common/Slider';
import { Toggle } from '../common/Toggle';
import {
  Sparkles,
  Plus,
  Trash2,
  Image as ImageIcon,
  Scissors,
  Flame,
  FileText,
  Sliders,
  CheckCircle2,
  Layers,
  ArrowRight,
} from 'lucide-react';

export const GeneratePage: React.FC = () => {
  const { activeProject, dna, setCurrentRun, setSelectedCandidate, setActiveTab, addToast } = useProject();

  const [leadStory, setLeadStory] = useState<StoryMaterial>({
    id: 'story-lead-01',
    role: 'lead-story',
    importance: 5,
    kicker: 'RAPORT SPECJALNY • PRZEŁOMOWE DECYZJE',
    headline: 'Wielki Zwrot w Polityce Energetycznej: Nowy Plan Redakcji',
    deck: 'Rząd przedstawia kompleksową reformę sieci przesyłowych i wsparcia dla mikroinstalacji. Inwestycje sięgną 45 mld złotych.',
    lead: 'Warszawa, 1 września. Zgromadzeni na posiedzeniu Rady Ministrów eksperci jednogłośnie przyjęli założenia nowej polityki surowcowej.',
    body: 'Kluczowym elementem planu jest budowa nowoczesnych magazynów energii oraz odblokowanie lądowych farm wiatrowych. Ustawa ma trafić do laski marszałkowskiej już w nadchodzącym tygodniu. Opozycja zapowiada wnikliwą analizę kosztów, wskazując na konieczność zabezpieczenia stabilności sieci w okresach zimowego szczytu zapotrzebowania.\n\n— To krok milowy, na który czekaliśmy od lat — podkreśla prof. Marek Zawadzki z Instytutu Energetyki Odnawialnej. — Stabilność dostaw energii oraz uniezależnienie od importu paliw kopalnych to fundament nowoczesnej gospodarki.',
    byline: 'Adam Nowicki, Redaktor Działu Krajowego',
    dateline: 'WARSZAWA',
    pullQuote: '„To nie jest kwestia wyboru politycznego, lecz historycznej konieczności technologicznej”',
    wordCount: 184,
  });

  const [secondaryStories, setSecondaryStories] = useState<StoryMaterial[]>([
    {
      id: 'story-sec-01',
      role: 'secondary',
      importance: 3,
      kicker: 'KULTURA I CYWILIZACJA',
      headline: 'Architektura Przyszłości: Jak Drewniane Wieżowce Zmieniają Centra Miast',
      deck: 'Ekologiczne drapacze chmur stają się standardem w stolicach Skandynawii.',
      lead: 'Nowe technologie prasowanego drewna CLT pozwalają na wznoszenie bezpiecznych konstrukcji o wysokości ponad 30 pięter.',
      body: 'Projektanci podkreślają nie tylko walory estetyczne i organiczny mikroklimat wnętrz, ale przede wszystkim ujemny ślad węglowy takich inwestycji.',
      byline: 'Marta Kowalska',
      dateline: 'OSLO',
      wordCount: 95,
    },
  ]);

  const [photos, setPhotos] = useState<PhotoMaterial[]>([]);
  const [photoUrl, setPhotoUrl] = useState('');
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);

  // Generator Exploration Hyperparameters
  const [candidateCount, setCandidateCount] = useState<number>(6);
  const [tensionTarget, setTensionTarget] = useState<number>(dna?.pageEnergyBudget.targetTensionScore ?? 0.8);
  const [explorationTemp, setExplorationTemp] = useState<number>(0.7);
  const [allowCutouts, setAllowCutouts] = useState<boolean>(true);
  const [prioritizeNovelty, setPrioritizeNovelty] = useState<boolean>(true);
  const [pageZone, setPageZone] = useState<'front_page' | 'spread' | 'back_page'>('front_page');
  const [styleBlend, setStyleBlend] = useState({
    opinion_to_tabloid: 0.35,
    classical_to_avantgarde: 0.35,
    dense_to_photo: 0.5,
  });
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationProgress, setGenerationProgress] = useState<string>('');

  React.useEffect(() => {
    if (dna?.styleBlend) setStyleBlend(dna.styleBlend);
  }, [dna?.styleBlend]);

  const handleAddSecondaryStory = () => {
    const newStory: StoryMaterial = {
      id: `story-sec-${Date.now()}`,
      role: 'sidebar',
      importance: 2,
      kicker: 'KRÓTKO Z KRAJU',
      headline: 'Nowe Inwestycje w Regionach',
      deck: 'Samorządy podpisały porozumienie o współpracy.',
      lead: 'Wspólne projekty infrastrukturalne otrzymają dofinansowanie.',
      body: 'Program obejmie ponad 40 gmin w trzech województwach.',
      byline: 'PAP',
      dateline: 'KRAKÓW',
      wordCount: 45,
    };
    setSecondaryStories([...secondaryStories, newStory]);
  };

  const handleAddPhoto = () => {
    const url = photoUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      addToast({ type: 'error', title: 'Nieprawidłowy adres', message: 'Wklej pełny adres zdjęcia zaczynający się od https://.' });
      return;
    }
    setPhotos((previous) => [...previous, {
      id: `photo-${Date.now()}`, url, previewUrl: url, caption: '', credit: '',
      importance: 3, autoCutout: false, hasCutoutMask: false,
      placementHint: 'lead-hero', allowTextWrap: false,
    }]);
    setPhotoUrl('');
  };

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploadingPhoto(true);
    try {
      const uploaded = await api.uploadPhoto(file, allowCutouts);
      setPhotos((previous) => [...previous, uploaded]);
      addToast({ type: 'success', title: 'Zdjęcie zapisane', message: uploaded.hasCutoutMask ? 'Odczytano maskę alfa i kontur zdjęcia.' : 'Zdjęcie gotowe do składu. Brak maski alfa.' });
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się wysłać zdjęcia', message: error instanceof Error ? error.message : 'Nie udało się wysłać zdjęcia.' });
    } finally {
      event.target.value = '';
      setIsUploadingPhoto(false);
    }
  };

  const handleRunGenerator = async () => {
    if (!activeProject) return;

    setIsGenerating(true);
    setGenerationProgress('Generowanie i ocena wariantów…');

    try {

      const intake: IntakeData = {
        projectId: activeProject.id,
        editionDate: new Date().toISOString().split('T')[0],
        pageNumber: 1,
        section: 'Strona Główna / Raport',
        leadStory,
        secondaryStories,
        photos,
        pageZone,
        styleBlend,
        generationConfig: {
          candidateCount,
          tensionTarget,
          explorationTemp,
          allowCutouts,
          prioritizeNovelty,
        },
      };

      const run = await api.generateCandidates(activeProject.id, intake);
      setCurrentRun(run);
      if (run.candidates.length > 0) {
        setSelectedCandidate(run.candidates[0]);
      }

      addToast({
        type: 'success',
        title: 'Generowanie zakończone',
        message: `Utworzono ${run.candidates.length} wariantów zgodnych z gramatyką DNA tytułu.`,
      });

      setActiveTab('gallery');
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Generowanie nieudane',
        message: e instanceof Error ? e.message : 'Nie udało się wygenerować wariantów.',
      });
    } finally {
      setIsGenerating(false);
      setGenerationProgress('');
    }
  };

  if (!activeProject) return null;

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-editorial-crimson font-bold">
              Materiały redakcyjne i generator ewolucyjny
            </span>
            <Badge variant="accent" size="sm">
              {activeProject.newspaperTitle}
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Materiały i generator makiety
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Input headlines, body text, kickers, and photos with importance weights. The generative engine produces <strong className="text-ink-100">N diverse layout candidates</strong> obeying TitleDNA with dynamic cutout wrapping.
          </p>
        </div>

        <Button
          variant="editorial"
          size="lg"
          isLoading={isGenerating}
          leftIcon={<Sparkles className="w-5 h-5" />}
          onClick={handleRunGenerator}
          className="shadow-xl"
        >
          {isGenerating ? generationProgress || 'Generowanie wariantów…' : `Generuj ${candidateCount} wariantów`}
        </Button>
      </div>

      {/* Main Grid: Stories + Photos + Hyperparameters */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Stories & Editorial Content (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* LEAD STORY CARD */}
          <Card className="space-y-5 border-l-4 border-editorial-crimson">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-editorial-crimson" />
                <h3 className="font-headline font-bold text-base text-ink-100">
                  Główny materiał (czołówka)
                </h3>
              </div>
              <Badge variant="accent" size="sm">
                Priorytet: 5 / 5 ★
              </Badge>
            </div>

            {/* Nadtytuł */}
            <div>
              <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-1">
                Nadtytuł Tag / Надзаголовок
              </label>
              <input
                type="text"
                value={leadStory.kicker}
                onChange={(e) => setLeadStory({ ...leadStory, kicker: e.target.value })}
                className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs font-mono text-editorial-crimson font-bold focus:outline-hidden focus:border-editorial-crimson uppercase"
              />
            </div>

            {/* Nagłówek */}
            <div>
              <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-1">
                Nagłówek główny
              </label>
              <textarea
                rows={2}
                value={leadStory.headline}
                onChange={(e) => setLeadStory({ ...leadStory, headline: e.target.value })}
                className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-base font-headline font-black text-ink-100 focus:outline-hidden focus:border-editorial-crimson resize-none"
              />
            </div>

            {/* Deck / Lead */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-1">
                  Deck / podtytuł
                </label>
                <textarea
                  rows={3}
                  value={leadStory.deck}
                  onChange={(e) => setLeadStory({ ...leadStory, deck: e.target.value })}
                  className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-200 focus:outline-hidden focus:border-editorial-crimson resize-none"
                />
              </div>
              <div>
                <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-1">
                  Lead
                </label>
                <textarea
                  rows={3}
                  value={leadStory.lead}
                  onChange={(e) => setLeadStory({ ...leadStory, lead: e.target.value })}
                  className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-200 focus:outline-hidden focus:border-editorial-crimson resize-none"
                />
              </div>
            </div>

            {/* Body text & Byline */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-mono uppercase font-bold text-ink-300">
                  Tekst główny (wielokolumnowy)
                </label>
                <span className="text-[11px] font-mono text-ink-400">
                  ~{leadStory.body.split(/\s+/).length} words
                </span>
              </div>
              <textarea
                rows={6}
                value={leadStory.body}
                onChange={(e) => setLeadStory({ ...leadStory, body: e.target.value })}
                className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-300 focus:outline-hidden focus:border-editorial-crimson font-sans leading-relaxed"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-ink-800">
              <div>
                <label className="block text-[11px] font-mono uppercase text-ink-400 mb-1">
                  Autor / podpis
                </label>
                <input
                  type="text"
                  value={leadStory.byline}
                  onChange={(e) => setLeadStory({ ...leadStory, byline: e.target.value })}
                  className="w-full px-3 py-1.5 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-200 focus:outline-hidden focus:border-editorial-crimson"
                />
              </div>
              <div>
                <label className="block text-[11px] font-mono uppercase text-ink-400 mb-1">
                  Cytat wyróżniony
                </label>
                <input
                  type="text"
                  value={leadStory.pullQuote || ''}
                  onChange={(e) => setLeadStory({ ...leadStory, pullQuote: e.target.value })}
                  className="w-full px-3 py-1.5 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-200 focus:outline-hidden focus:border-editorial-crimson"
                />
              </div>
            </div>
          </Card>

          {/* SECONDARY STORIES */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase text-ink-400 font-semibold">
                Materiały poboczne i boksy ({secondaryStories.length})
              </span>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Plus className="w-3.5 h-3.5" />}
                onClick={handleAddSecondaryStory}
              >
                Dodaj materiał
              </Button>
            </div>

            {secondaryStories.map((sec, idx) => (
              <Card key={sec.id} className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-ink-800">
                  <span className="text-xs font-mono font-bold text-ink-200">
                    Materiał #{idx + 2} • {sec.role.toUpperCase()}
                  </span>
                  <button
                    onClick={() =>
                      setSecondaryStories(secondaryStories.filter((s) => s.id !== sec.id))
                    }
                    className="p-1 text-ink-500 hover:text-red-400 rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-mono uppercase text-ink-400 mb-1">
                      Nadtytuł
                    </label>
                    <input
                      type="text"
                      value={sec.kicker}
                      onChange={(e) => {
                        const updated = [...secondaryStories];
                        updated[idx].kicker = e.target.value;
                        setSecondaryStories(updated);
                      }}
                      className="w-full px-2.5 py-1.5 bg-ink-950 border border-ink-700 rounded text-xs text-ink-100 uppercase font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-mono uppercase text-ink-400 mb-1">
                      Nagłówek
                    </label>
                    <input
                      type="text"
                      value={sec.headline}
                      onChange={(e) => {
                        const updated = [...secondaryStories];
                        updated[idx].headline = e.target.value;
                        setSecondaryStories(updated);
                      }}
                      className="w-full px-2.5 py-1.5 bg-ink-950 border border-ink-700 rounded text-xs font-bold text-ink-100 font-headline"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[10px] font-mono uppercase text-ink-400 mb-1">
                    Tekst główny
                  </label>
                  <textarea
                    rows={2}
                    value={sec.body}
                    onChange={(e) => {
                      const updated = [...secondaryStories];
                      updated[idx].body = e.target.value;
                      setSecondaryStories(updated);
                    }}
                    className="w-full px-2.5 py-1.5 bg-ink-950 border border-ink-700 rounded text-xs text-ink-300"
                  />
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Right Column: Photos + Auto-Cutout + Generator Solver Parameters (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* PHOTO ASSETS & AUTO-CUTOUT TRAY */}
          <Card className="space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-purple-400" />
                <h3 className="font-headline font-bold text-base text-ink-100">
                  Zdjęcia i szparowanie
                </h3>
              </div>
              <label className="cursor-pointer">
                <input type="file" accept="image/*" className="hidden" disabled={isUploadingPhoto} onChange={handlePhotoUpload} />
                <span className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-ink-200 border border-ink-700 hover:border-ink-500 hover:bg-ink-800 transition-colors">
                  {isUploadingPhoto ? 'Wysyłanie…' : 'Dodaj plik'}
                </span>
              </label>
            </div>

            <div className="flex gap-2">
              <input type="url" aria-label="Adres zdjęcia" placeholder="https://… / adres zdjęcia" value={photoUrl} onChange={(event) => setPhotoUrl(event.target.value)} className="flex-1 min-w-0 px-2 py-2 bg-ink-950 border border-ink-700 rounded text-xs text-ink-100" />
              <Button variant="outline" size="sm" onClick={handleAddPhoto}>Dodaj URL</Button>
            </div>
            <Toggle label="Odczytaj kontur maski alfa podczas wysyłania PNG" checked={allowCutouts} onChange={setAllowCutouts} description="Obsługuje PNG z przezroczystym tłem. Opaque zdjęcie pozostaje prostokątne." />
            {photos.length === 0 && <p className="text-xs text-ink-400">Dodaj własne zdjęcie. Skład tekstowy działa również bez fotografii.</p>}
            <div className="space-y-4">
              {photos.map((photo, pIdx) => (
                <div
                  key={photo.id}
                  className="p-3.5 bg-ink-950 rounded-xl border border-ink-800 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <img
                      src={photo.previewUrl || photo.url}
                      alt="Thumbnail"
                      className="w-20 h-20 object-cover rounded-lg border border-ink-700 shrink-0"
                    />
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" size="sm">
                          {photo.placementHint.toUpperCase()}
                        </Badge>
                        <button
                          onClick={() => setPhotos(photos.filter((p) => p.id !== photo.id))}
                          className="text-ink-500 hover:text-red-400 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <input
                        type="text"
                        placeholder="Podpis zdjęcia…"
                        value={photo.caption}
                        onChange={(e) => {
                          const updated = [...photos];
                          updated[pIdx].caption = e.target.value;
                          setPhotos(updated);
                        }}
                        className="w-full px-2 py-1 bg-ink-900 border border-ink-800 rounded text-[11px] text-ink-200"
                      />
                    </div>
                  </div>

                  {/* Auto-Cutout Toggle & Text Wrap */}
                  <div className="pt-2 border-t border-ink-800/80 space-y-2">
                    <Toggle
                      label="Szparowanie zdjęcia"
                      checked={photo.autoCutout && !!photo.hasCutoutMask}
                      onChange={(v) => {
                        const updated = [...photos];
                        updated[pIdx].autoCutout = v && !!photo.hasCutoutMask;
                        setPhotos(updated);
                      }}
                      description={photo.hasCutoutMask ? "Użyj odczytanej maski do oblewania konturu." : "Brak maski alfa — wgraj PNG z przezroczystym tłem."}
                    />

                    {photo.hasCutoutMask && (
                      <div className="p-2 bg-purple-950/40 rounded border border-purple-800/50 text-[10px] font-mono text-purple-300 flex items-center gap-2">
                        <Scissors className="w-3.5 h-3.5 shrink-0" />
                        <span>Maska alfa: {photo.cutoutContourPoints?.length || 0} punktów konturu</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* GENERATOR HYPERPARAMETERS */}
          <Card className="space-y-5 bg-gradient-to-b from-ink-900 to-ink-950">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-editorial-ochre" />
                <h3 className="font-headline font-bold text-base text-ink-100">
                  Ustawienia generatora
                </h3>
              </div>
              <Badge variant="score" size="sm">
                Generator ewolucyjny
              </Badge>
            </div>

            <div className="space-y-4">
              {/* Candidate Count N */}
              <div>
                <label className="block text-xs font-mono uppercase font-bold text-ink-300 mb-2">
                  Liczba wariantów
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[4, 6, 8, 12].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setCandidateCount(num)}
                      className={`py-2 rounded-lg text-xs font-mono font-bold border transition-all ${
                        candidateCount === num
                          ? 'bg-editorial-crimson text-ink-100 border-editorial-crimson shadow-md'
                          : 'bg-ink-950 text-ink-300 border-ink-800 hover:border-ink-700'
                      }`}
                    >
                      {num} wariantów
                    </button>
                  ))}
                </div>
              </div>

              {/* Napięcie strony */}
              <Slider
                label="Docelowe napięcie strony"
                value={tensionTarget}
                min={0}
                max={1.5}
                step={0.05}
                unit=" pts"
                onChange={setTensionTarget}
                description="Controls how aggressively transgressions (column breaks, overlaps) are sampled."
              />

              {/* Temperatura eksploracji */}
              <Slider
                label="Temperatura eksploracji"
                value={explorationTemp}
                min={0.1}
                max={1.0}
                step={0.05}
                onChange={setExplorationTemp}
                description="Higher values generate bolder, more experimental topological arrangements."
              />

              <div className="pt-3 border-t border-ink-800 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase font-bold text-ink-300">Strefa strony</span>
                  <select
                    aria-label="Strefa strony"
                    value={pageZone}
                    onChange={(e) => setPageZone(e.target.value as typeof pageZone)}
                    className="bg-ink-950 border border-ink-700 rounded px-2 py-1.5 text-xs text-ink-100"
                  >
                    <option value="front_page">Front page / czołówka</option>
                    <option value="spread">Inside spread / rozkładówka</option>
                    <option value="back_page">Back page / ostatnia</option>
                  </select>
                </div>
                <span className="text-xs font-mono uppercase font-bold text-ink-300 block">Mieszanie stylu</span>
                <Slider label="Dziennik opinii → Tabloid" value={styleBlend.opinion_to_tabloid} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, opinion_to_tabloid: value }))} />
                <Slider label="Siatka klasyczna → Awangarda" value={styleBlend.classical_to_avantgarde} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, classical_to_avantgarde: value }))} />
                <Slider label="Gęsty tekst → Dominanta foto" value={styleBlend.dense_to_photo} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, dense_to_photo: value }))} />
              </div>

              {/* Anti-Copying Guardrail */}
<p className="text-xs text-ink-400">Krytyk odrzuca niedopuszczalne kolizje i układy zbyt bliskie korpusowi. Bramka nowości jest zawsze aktywna.</p>
            </div>

            <div className="pt-3 border-t border-ink-800">
              <Button
                variant="editorial"
                size="lg"
                className="w-full shadow-2xl"
                isLoading={isGenerating}
                leftIcon={<Sparkles className="w-5 h-5" />}
                onClick={handleRunGenerator}
              >
                {isGenerating ? generationProgress || 'Praca silnika…' : `Uruchom generowanie (${candidateCount} wariantów)`}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
