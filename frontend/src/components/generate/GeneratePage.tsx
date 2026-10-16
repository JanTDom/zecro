import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { IntakeData, StoryMaterial, PhotoMaterial } from '../../types/material';
import { api, ApiError, PhotoCheckResult } from '../../api/client';

const parseTvSchedule = (text: string): NonNullable<IntakeData['tvSchedule']> => text.split('\n')
  .map(line => line.split(';').map(part => part.trim()))
  .filter(parts => parts.length >= 3 && /^\d{1,2}:\d{2}$/.test(parts[1]) && Boolean(parts[0]) && Boolean(parts[2]))
  .map(([station, time, title, genre, mark]) => ({ station, time, title,
    genre: genre && genre !== '*' ? genre : undefined, highlight: mark === '*' || genre === '*' }));
import { EDITORIAL_STYLES, exactStyleForBlend } from '../../editorialStyles';
import { PAGE_TOPICS, PageTopic } from '../../pageTopics';
import { styleReviewState } from '../../styleReview';
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

const emptyLeadStory: StoryMaterial = {
  id: 'story-lead-01', role: 'lead-story', importance: 5,
  kicker: '', headline: '', deck: '', lead: '', body: '', byline: '', dateline: '', pullQuote: '', wordCount: 0,
};

const warianty = (count: number) => `${count} ${count === 4 ? 'warianty' : 'wariantów'}`;

export const GeneratePage: React.FC = () => {
  const { activeProject, dna, setCurrentRun, setSelectedCandidate, setActiveTab, addToast } = useProject();

  const [leadStory, setLeadStory] = useState<StoryMaterial>(emptyLeadStory);

  const [secondaryStories, setSecondaryStories] = useState<StoryMaterial[]>([]);

  const [photos, setPhotos] = useState<PhotoMaterial[]>([]);
  const [photoUrl, setPhotoUrl] = useState('');
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);

  // Generator Exploration Hyperparameters
  const [candidateCount, setCandidateCount] = useState<number>(6);
  const [tensionTarget, setTensionTarget] = useState<number>(dna?.pageEnergyBudget.targetTensionScore ?? 0.8);
  const [explorationTemp, setExplorationTemp] = useState<number>(0.7);
  const [allowCutouts, setAllowCutouts] = useState<boolean>(true);
  const [prioritizeNovelty, setPrioritizeNovelty] = useState<boolean>(true);
  const [visualReview, setVisualReview] = useState<boolean>(true);
  const [copyReview, setCopyReview] = useState<boolean>(true);
  const [placeholderCopy, setPlaceholderCopy] = useState<boolean>(false);
  const [pageZone, setPageZone] = useState<'front_page' | 'spread' | 'back_page'>('front_page');
  const [pageTopic, setPageTopic] = useState<PageTopic>('general');
  const [editorialMood, setEditorialMood] = useState<NonNullable<IntakeData['editorialMood']>>('auto');
  const [styleBlend, setStyleBlend] = useState({
    opinion_to_tabloid: 0.35,
    classical_to_avantgarde: 0.35,
    dense_to_photo: 0.5,
  });
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationProgress, setGenerationProgress] = useState<string>('');
  const [generationError, setGenerationError] = useState<string>('');
  const [photoStop, setPhotoStop] = useState<string | null>(null);
  const [photoReport, setPhotoReport] = useState<PhotoCheckResult | null>(null);
  const [isCheckingPhotos, setIsCheckingPhotos] = useState(false);
  const [tvScheduleText, setTvScheduleText] = useState('');
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [draftSaved, setDraftSaved] = useState<boolean>(false);
  const draftHydrated = React.useRef(false);
  const [loadedDraftKey, setLoadedDraftKey] = useState('');
  const hasRequiredMaterial = Boolean(leadStory.headline.trim() && leadStory.body.trim());

  const goToMainMaterial = () => {
    document.getElementById('lead-story-fields')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const draftKey = activeProject ? `zecro:generator-draft:${activeProject.id}` : '';
  React.useEffect(() => {
    if (!draftKey) return;
    draftHydrated.current = false;
    setLoadedDraftKey('');
    setLeadStory(emptyLeadStory);
    setSecondaryStories([]);
    setPhotos([]);
    setDraftSaved(false);
    try {
      const raw = localStorage.getItem(draftKey);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.leadStory) setLeadStory(draft.leadStory);
        if (draft.secondaryStories) setSecondaryStories(draft.secondaryStories);
        if (draft.photos) setPhotos(draft.photos);
        if (draft.pageZone) setPageZone(draft.pageZone);
        if (draft.pageTopic && PAGE_TOPICS.some(topic => topic.id === draft.pageTopic)) setPageTopic(draft.pageTopic);
        if (draft.editorialMood) setEditorialMood(draft.editorialMood);
        if (draft.styleBlend) setStyleBlend(draft.styleBlend);
        if (draft.candidateCount) setCandidateCount(draft.candidateCount);
        if (typeof draft.copyReview === 'boolean') setCopyReview(draft.copyReview);
        if (typeof draft.visualReview === 'boolean') setVisualReview(draft.visualReview);
        setDraftSaved(true);
      }
    } catch { /* local drafts are an optional convenience */ }
    draftHydrated.current = true;
    setLoadedDraftKey(draftKey);
  }, [draftKey]);
  React.useEffect(() => {
    if (!draftKey || !draftHydrated.current || loadedDraftKey !== draftKey) return;
    try {
      localStorage.setItem(draftKey, JSON.stringify({ leadStory, secondaryStories, photos, pageZone, pageTopic, editorialMood, styleBlend, candidateCount, copyReview, visualReview }));
      setDraftSaved(true);
    } catch { /* storage unavailable */ }
  }, [draftKey, loadedDraftKey, leadStory, secondaryStories, photos, pageZone, pageTopic, editorialMood, styleBlend, candidateCount, copyReview, visualReview]);

  React.useEffect(() => {
    if (dna?.styleBlend) setStyleBlend(dna.styleBlend);
  }, [dna?.styleBlend]);

  const handleAddSecondaryStory = () => {
    const newStory: StoryMaterial = {
      id: `story-sec-${Date.now()}`,
      role: 'sidebar',
      importance: 2,
      kicker: '', headline: '', deck: '', lead: '', body: '', byline: '', dateline: '', wordCount: 0,
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
      storyId: leadStory.id,
      importance: 3, autoCutout: false, hasCutoutMask: false, focalPoint: [0.5, 0.5],
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
      setPhotos((previous) => [...previous, { ...uploaded, storyId: leadStory.id }]);
      addToast({ type: 'success', title: 'Zdjęcie zapisane', message: uploaded.hasCutoutMask ? 'Odczytano maskę alfa i kontur zdjęcia.' : 'Zdjęcie gotowe do składu. Brak maski alfa.' });
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się wysłać zdjęcia', message: error instanceof Error ? error.message : 'Nie udało się wysłać zdjęcia.' });
    } finally {
      event.target.value = '';
      setIsUploadingPhoto(false);
    }
  };

  const buildIntake = (acceptWeakPhotos = false): IntakeData =>
    ({
      projectId: activeProject?.id ?? "",
      editionDate: new Date().toISOString().split('T')[0],
      pageNumber: 1,
      section: PAGE_TOPICS.find(topic => topic.id === pageTopic)?.section || 'Wiadomości',
      leadStory,
      secondaryStories: secondaryStories.filter(story => story.headline.trim() && story.body.trim()),
      photos,
      pageZone,
      pageTopic,
      editorialMood,
      styleBlend,
      tvSchedule: dna?.archetype === 'tv_guide' ? parseTvSchedule(tvScheduleText) : undefined,
      generationConfig: {
        candidateCount,
        tensionTarget,
        explorationTemp,
        allowCutouts,
        prioritizeNovelty,
        visualReview,
        copyReview,
        acceptWeakPhotos,
        placeholderCopy,
      },
    });

  const handleCheckPhotos = async () => {
    if (!activeProject) return;
    setIsCheckingPhotos(true);
    setPhotoReport(null);
    try {
      setPhotoReport(await api.checkPhotos(activeProject.id, buildIntake()));
    } catch (e) {
      addToast({ type: 'error', title: 'Kontrola zdjęć nieudana', message: e instanceof Error ? e.message : 'Spróbuj ponownie.' });
    } finally {
      setIsCheckingPhotos(false);
    }
  };

  const handleRunGenerator = async (acceptWeakPhotos = false) => {
    if (!activeProject) return;
    setPhotoStop(null);
    if (!leadStory.headline.trim() || !leadStory.body.trim()) {
      setGenerationError('Wpisz tytuł i tekst głównego artykułu, aby przygotować stronę.');
      return;
    }

    setIsGenerating(true);
    setGenerationError('');
    setGenerationProgress(visualReview ? 'Generowanie i ocena wizualna…' : 'Generowanie wariantów…');

    try {

      const intake = buildIntake(acceptWeakPhotos);

      const run = await api.generateCandidates(activeProject.id, intake);
      if (run.candidates.length === 0) {
        throw new Error('Nie powstał żaden wariant. Sprawdź tekst materiałów lub zmniejsz siłę ozdobników w ustawieniach.');
      }
      setCurrentRun(run);
      if (run.candidates.length > 0) {
        setSelectedCandidate(run.candidates[0]);
      }

      const reviewReady = run.candidates.some(candidate => styleReviewState(candidate) === 'candidate_for_editor');
      addToast(reviewReady ? {
        type: 'success', title: 'Wariant do oceny redaktora',
        message: `Utworzono ${warianty(run.candidates.length)}. Najlepszy wariant przeszedł wstępną ocenę wyglądu; sprawdź zdjęcia i treść.`,
      } : {
        type: 'warning', title: 'Strona wymaga dopracowania',
        message: `Utworzono ${warianty(run.candidates.length)}, ale ocena wizualna nie potwierdziła jeszcze jakości do wydania. Zobacz konkretne uwagi przy wariantach.`,
      });

      setActiveTab('gallery');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Nie udało się wygenerować wariantów.';
      if (e instanceof ApiError && e.code === 'photo_needed') {
        // Photo editing precedes geometry: show the editor why and let them decide.
        setPhotoStop(message);
        return;
      }
      setGenerationError(message);
      addToast({
        type: 'error',
        title: 'Generowanie nieudane',
        message,
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
              Krok 2 z 5 · Twoje materiały
            </span>
            <Badge variant="accent" size="sm">
              {activeProject.newspaperTitle}
            </Badge>
            {draftSaved && <span className="text-[10px] font-mono text-emerald-400">szkic zapisany</span>}
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Materiały i nowa strona
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Wpisz własny artykuł i dodaj zdjęcia. Program przygotuje kilka różnych propozycji strony. Tytuł i tekst główny są wymagane; pozostałe pola możesz uzupełnić później.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="secondary" size="md" onClick={() => setShowAdvanced((value) => !value)}>
            {showAdvanced ? 'Ukryj ustawienia zaawansowane' : 'Ustawienia zaawansowane'}
          </Button>
          <Button
            variant="editorial"
            size="lg"
            isLoading={isGenerating}
            leftIcon={<Sparkles className="w-5 h-5" />}
            onClick={hasRequiredMaterial ? () => handleRunGenerator() : goToMainMaterial}
            className="shadow-xl"
          >
            {isGenerating ? generationProgress || 'Generowanie wariantów…' : hasRequiredMaterial ? `Generuj ${warianty(candidateCount)}` : 'Wpisz główny materiał'}
          </Button>
        </div>
      </div>

      {photoStop && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 space-y-2">
          <p><strong>Potrzebne inne zdjęcie.</strong> {photoStop.replace(/^Potrzebne inne zdjęcie\s*/, '')}</p>
          <p className="text-xs">Fotoedytor sprawdza zdjęcie, zanim powstanie układ. Słabe zdjęcie główne daje słabą okładkę niezależnie od układu.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => setPhotoStop(null)}>Dodam inne zdjęcie</Button>
            <Button variant="ghost" size="sm" onClick={() => handleRunGenerator(true)}>Generuj mimo to</Button>
          </div>
        </div>
      )}

      {generationError && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          <strong>Generowanie nieudane.</strong> {generationError}
        </div>
      )}

      <section className="rounded-xl border border-ink-800 bg-white p-5 space-y-4" aria-labelledby="page-kind-title">
        <div>
          <h2 id="page-kind-title" className="font-headline text-lg font-bold text-ink-100">Jaką stronę przygotowujesz?</h2>
          <p className="mt-1 text-xs text-ink-400">Wybierz temat i miejsce w gazecie. Program dostosuje układ tej strony, zachowując styl całego tytułu.</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {PAGE_TOPICS.map(topic => <button key={topic.id} type="button" aria-pressed={pageTopic === topic.id}
            onClick={() => setPageTopic(topic.id)}
            className={`rounded-lg border p-2.5 text-left ${pageTopic === topic.id ? 'border-editorial-crimson bg-blue-50' : 'border-ink-800 hover:border-editorial-crimson/50'}`}>
            <span className="block text-xs font-semibold text-ink-100">{topic.name}</span>
            <span className="mt-1 block text-[11px] text-ink-400">{topic.description}</span>
          </button>)}
        </div>
        <div>
          <label htmlFor="page-position" className="mr-3 text-xs font-semibold text-ink-300">Miejsce w gazecie</label>
          <select id="page-position" value={pageZone} onChange={(event) => setPageZone(event.target.value as typeof pageZone)}
            className="rounded border border-ink-700 bg-white px-2 py-1.5 text-xs text-ink-100">
            <option value="front_page">Pierwsza strona</option>
            <option value="spread">Rozkładówka wewnętrzna</option>
            <option value="back_page">Ostatnia strona</option>
          </select>
        </div>
        <div>
          <label htmlFor="editorial-mood" className="block text-xs font-semibold text-ink-300 mb-1">Jaki nastrój powinien mieć główny materiał?</label>
          <select id="editorial-mood" value={editorialMood}
            onChange={(event) => setEditorialMood(event.target.value as NonNullable<IntakeData['editorialMood']>)}
            className="rounded border border-ink-700 bg-white px-2 py-1.5 text-xs text-ink-100">
            <option value="auto">Dobierz z treści automatycznie</option>
            <option value="urgent">Pilny i dynamiczny</option>
            <option value="scandal">Skandal lub afera</option>
            <option value="entertainment">Rozrywka i gwiazdy</option>
            <option value="human">Bliski ludziom</option>
            <option value="solemn">Poważny i pełen szacunku</option>
            <option value="celebratory">Radosny i świąteczny</option>
            <option value="analytical">Spokojny i analityczny</option>
            <option value="practical">Praktyczny i czytelny</option>
          </select>
          <p className="mt-1 text-[11px] text-ink-400">Wpływa na rytm strony, kolor akcentów, liternictwo i sposób pokazania zdjęcia. Nazwa gazety zachowuje własny styl.</p>
        </div>
      </section>

      {/* Main Grid: Stories + Photos + Hyperparameters */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Stories & Editorial Content (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* LEAD STORY CARD */}
          <Card className="space-y-5 border-l-4 border-editorial-crimson" id="lead-story-fields">
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
                Nadtytuł (opcjonalnie)
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
                  Podtytuł
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
                  Wprowadzenie
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
                  {leadStory.body.trim() ? leadStory.body.trim().split(/\s+/).length : 0} słów
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
                    Temat poboczny {idx + 2}
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
          <Card className="space-y-3">
            <h3 className="font-headline font-bold text-base text-ink-100">Styl i pomoc AI</h3>
            <p className="text-xs text-ink-400">Domyślny styl pochodzi z wybranej gazety. Program mierzy tekst w jej fontach i dopasowuje go do miejsca na stronie.</p>
            <details className="rounded-lg border border-ink-800 p-3">
              <summary className="cursor-pointer text-xs font-semibold text-ink-200">Zmień styl tylko tej strony · {exactStyleForBlend(styleBlend)?.name || 'własne ustawienia'}</summary>
              <p className="mt-2 text-[11px] text-ink-400">Możesz nadać jednej stronie inny charakter bez zmiany całej gazety.</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {EDITORIAL_STYLES.map(option => <button key={option.id} type="button"
                aria-pressed={exactStyleForBlend(styleBlend)?.id === option.id}
                onClick={() => setStyleBlend({ ...option.blend })}
                className={`rounded-lg border p-3 text-left ${exactStyleForBlend(styleBlend)?.id === option.id ? 'border-editorial-crimson bg-ink-800 text-ink-100' : 'border-ink-700 text-ink-300'}`}>
                <span className="block text-xs font-semibold">{option.name}</span>
                <span className="block text-[11px] mt-1 opacity-75">{option.description}</span>
              </button>)}
            </div>
            {!exactStyleForBlend(styleBlend) && <p className="text-[11px] text-ink-400">Własne ustawienia charakteru strony. Możesz wybrać jeden z rodzajów powyżej.</p>}
            </details>
            <p className="text-[11px] text-ink-400">Krój nagłówków: {dna?.typography.headlinePrimary.fontFamily || 'dobierany z zasad gazety'} · tekst: {dna?.typography.body.fontFamily || 'dobierany z zasad gazety'}</p>
            <Toggle label="Dopasuj tekst do ramek z pomocą AI" checked={copyReview} onChange={setCopyReview}
              description="Układ ustala ramki, a tekst ma je dokładnie wypełnić. AI skraca za długi tekst i rozpisuje za krótki na podstawie materiału źródłowego. Zmianę przyjmiemy po kontroli faktów i składu." />
            <Toggle label="Próba składu z tekstem markowanym" checked={placeholderCopy} onChange={setPlaceholderCopy}
              description="Ramki tekstu wypełni tekst zastępczy, żeby ocenić sam układ. Takiej strony nie można wysłać do druku." />
            <Toggle label="Oceń wygląd strony przez AI" checked={visualReview} onChange={setVisualReview}
              description="AI obejrzy dwa najlepiej rokujące warianty i oceni, czy wygląd naprawdę pasuje do wybranego rodzaju gazety. Ta kontrola może potrwać dłużej." />
          </Card>
          {/* PHOTO ASSETS & AUTO-CUTOUT TRAY */}
          <Card className="space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-purple-400" />
                <h3 className="font-headline font-bold text-base text-ink-100">
                  Zdjęcia
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
              <Button variant="outline" size="sm" onClick={handleAddPhoto}>Dodaj z adresu</Button>
            </div>
            <Toggle label="Spróbuj wyciąć postać ze zdjęcia" checked={allowCutouts} onChange={setAllowCutouts} description="Po wgraniu sprawdź obrys i kadr. Gdy wycięcie się nie uda, zdjęcie pozostanie prostokątne." />
            {photos.length === 0 && <p className="text-xs text-ink-400">Dodaj własne zdjęcie. Skład tekstowy działa również bez fotografii.</p>}
            {dna?.archetype === 'tv_guide' && (
              <div className="rounded-lg border border-ink-800 p-3 space-y-2">
                <label htmlFor="tv-schedule" className="block text-xs font-semibold text-ink-200">Ramówka programu (jedna pozycja w wierszu)</label>
                <textarea id="tv-schedule" rows={6} value={tvScheduleText} onChange={(event) => setTvScheduleText(event.target.value)}
                  placeholder={'TVP1; 20:00; Wiadomości; informacje\nTVN; 20:15; Film wieczoru; film; *'}
                  className="w-full rounded border border-ink-700 bg-white px-2 py-1.5 font-mono text-xs text-ink-100" />
                <p className="text-[11px] text-ink-400">Format: stacja; godzina; tytuł; gatunek (opcjonalnie). Gwiazdka na końcu oznacza program dnia. Ramówka jest składana na stronie wewnętrznej lub ostatniej. Rozpoznane pozycje: {parseTvSchedule(tvScheduleText).length}.</p>
              </div>
            )}
            {dna?.archetype === 'tabloid' && <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">Okładka bulwarowa wygląda najlepiej z fotografią główną i osobnymi zdjęciami do co najmniej dwóch pozostałych tematów. Po dodaniu każdego zdjęcia wybierz jego materiał.</p>}
            <div className="space-y-4">
              {photos.map((photo, pIdx) => (
                <div
                  key={photo.id}
                  className="p-3.5 bg-ink-950 rounded-xl border border-ink-800 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <img
                      src={photo.previewUrl || photo.url}
                      alt="Miniatura zdjęcia"
                      className="w-20 h-20 object-cover rounded-lg border border-ink-700 shrink-0"
                    />
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" size="sm">Zdjęcie {pIdx + 1}</Badge>
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

                  <label className="block text-xs font-semibold text-ink-300">
                    Zdjęcie do materiału
                    <select
                      value={photo.storyId || leadStory.id}
                      onChange={(event) => setPhotos(previous => previous.map((item, index) => index === pIdx ? { ...item, storyId: event.target.value } : item))}
                      className="mt-1 w-full rounded border border-ink-700 bg-white px-2 py-2 text-xs text-ink-100"
                    >
                      <option value={leadStory.id}>Główny temat{leadStory.headline ? `: ${leadStory.headline.slice(0, 45)}` : ''}</option>
                      {secondaryStories.map((story, index) => <option key={story.id} value={story.id}>Temat {index + 2}{story.headline ? `: ${story.headline.slice(0, 45)}` : ''}</option>)}
                    </select>
                  </label>

                  <div className="rounded-lg border border-ink-800 p-2.5 space-y-2">
                    <p className="text-xs font-semibold text-ink-300">Co musi zostać w kadrze?</p>
                    <p className="text-[11px] text-ink-400">
                      {photo.focalStatus === 'ready'
                        ? `AI odnalazła ${photo.focalSubjectKind === 'person' ? 'najważniejszą osobę' : photo.focalSubjectKind === 'object' ? 'najważniejszy obiekt' : 'centrum wydarzenia'} i ustawiła bezpieczny kadr. Przesuń suwaki tylko wtedy, gdy chcesz wskazać inny punkt.`
                        : 'Wskaż punkt na osobie lub ważnym przedmiocie. Program zachowa go przy każdym wariancie kadrowania.'}
                    </p>
                    {(['poziomo', 'pionowo'] as const).map((axis, index) => (
                      <label key={axis} className="flex items-center gap-2 text-[11px] text-ink-300">
                        <span className="w-16">{axis === 'poziomo' ? 'Lewo–prawo' : 'Góra–dół'}</span>
                        <input type="range" min="5" max="95" value={Math.round((photo.focalPoint?.[index] ?? 0.5) * 100)}
                          onChange={(event) => setPhotos(previous => previous.map((item, itemIndex) => {
                            if (itemIndex !== pIdx) return item;
                            const focal: [number, number] = [...(item.focalPoint || [0.5, 0.5])];
                            focal[index] = Number(event.target.value) / 100;
                            return { ...item, focalPoint: focal };
                          }))} className="flex-1" aria-label={`Ważny punkt zdjęcia ${pIdx + 1}: ${axis}`} />
                        <span className="w-8 text-right">{Math.round((photo.focalPoint?.[index] ?? 0.5) * 100)}%</span>
                      </label>
                    ))}
                  </div>

                  {/* Auto-Cutout Toggle & Text Wrap */}
                  <div className="pt-2 border-t border-ink-800/80 space-y-2">
                    <Toggle
                      label="Usuń tło zdjęcia"
                      checked={photo.autoCutout && !!photo.hasCutoutMask}
                      onChange={(v) => {
                        const updated = [...photos];
                        updated[pIdx].autoCutout = v && !!photo.hasCutoutMask;
                        setPhotos(updated);
                      }}
                      description={photo.hasCutoutMask ? "Tekst może otaczać wyciętą postać." : "Dla tego zdjęcia nie ma jeszcze poprawnego obrysu."}
                    />

                    {photo.hasCutoutMask && (
                      <div className="p-2 bg-purple-950/40 rounded border border-purple-800/50 text-[10px] font-mono text-purple-300 flex items-center gap-2">
                        <Scissors className="w-3.5 h-3.5 shrink-0" />
                        <span>Obrys zdjęcia: {photo.cutoutContourPoints?.length || 0} punktów</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* GENERATOR HYPERPARAMETERS */}
          {showAdvanced && <Card className="space-y-5 bg-gradient-to-b from-ink-900 to-ink-950">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-editorial-ochre" />
                <h3 className="font-headline font-bold text-base text-ink-100">
                  Ustawienia generatora
                </h3>
              </div>
              <Badge variant="score" size="sm">
                Liczba propozycji
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
                      {warianty(num)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Napięcie strony */}
              <Slider
                label="Siła ozdobników i przełamań"
                value={tensionTarget}
                min={0}
                max={1.5}
                step={0.05}
                onChange={setTensionTarget}
                description="Wyższa wartość pozwala na więcej mocnych zabiegów, takich jak przełamanie kolumny."
              />

              {/* Temperatura eksploracji */}
              <Slider
                label="Odwaga układu"
                value={explorationTemp}
                min={0.1}
                max={1.0}
                step={0.05}
                onChange={setExplorationTemp}
                description="Wyższa wartość daje odważniejsze, mniej regularne układy."
              />

              <div className="pt-3 border-t border-ink-800 space-y-4">
                <span className="text-xs font-mono uppercase font-bold text-ink-300 block">Mieszanie stylu</span>
                <Slider label="Dziennik opinii → Tabloid" value={styleBlend.opinion_to_tabloid} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, opinion_to_tabloid: value }))} />
                <Slider label="Siatka klasyczna → Awangarda" value={styleBlend.classical_to_avantgarde} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, classical_to_avantgarde: value }))} />
                <Slider label="Gęsty tekst → Dominanta foto" value={styleBlend.dense_to_photo} min={0} max={1} step={0.01} onChange={(value) => setStyleBlend((prev) => ({ ...prev, dense_to_photo: value }))} />
              </div>

              {/* Anti-Copying Guardrail */}
              <p className="text-xs text-ink-400">Krytyk odrzuca niedopuszczalne kolizje i układy zbyt bliskie korpusowi. Bramka nowości jest zawsze aktywna.</p>
              <p className="pt-3 border-t border-ink-800 text-xs text-ink-500">
                Ustawienia zostaną użyte, gdy przygotujesz propozycje strony.
              </p>
            </div>
          </Card>}
        </div>
      </div>
      <section className="rounded-xl border border-ink-800 bg-white p-5 space-y-3" aria-labelledby="photo-check-title">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 id="photo-check-title" className="font-headline text-lg font-bold text-ink-100">Kontrola zdjęć przed składem</h2>
            <p className="mt-1 text-xs text-ink-400">Fotoedytor AI sprawdza, czy zdjęcia pasują do tytułów, czy są dynamiczne i czy nadają się do druku. Układ strony powstaje dopiero potem.</p>
          </div>
          <Button variant="secondary" size="md" isLoading={isCheckingPhotos} disabled={!photos.length || !hasRequiredMaterial}
            onClick={() => void handleCheckPhotos()}>{photos.length ? 'Sprawdź zdjęcia' : 'Brak zdjęć do sprawdzenia'}</Button>
        </div>
        {photoReport && (
          <div className={`rounded-lg border px-4 py-3 text-sm ${photoReport.ready ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>
            <p className="font-semibold">{photoReport.ready ? 'Zdjęcia nadają się do składu.' : 'Potrzebne inne zdjęcie.'}</p>
            <p className="text-xs mt-1">{photoReport.message}</p>
            <ul className="mt-2 space-y-1 text-xs">
              {photoReport.photo_selection.filter(row => row.status === 'selected').map(row => (
                <li key={row.story_ref}>
                  <strong>{row.lead ? 'Materiał główny' : 'Temat poboczny'}:</strong> ocena {(row.score ?? 0).toFixed(2)}, zgodność z tytułem {(row.headline_match ?? 0).toFixed(2)}
                  {row.emotion && row.emotion !== 'uncertain' ? `, emocja: ${row.emotion}` : ''}. {row.reason}
                  {row.alternatives && row.alternatives.length > 0 && <span className="text-ink-500"> (porównano z {row.alternatives.length} innymi)</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-blue-200 bg-blue-50 p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="font-headline text-lg font-bold text-ink-100">Następny krok: zobacz propozycje strony</h2>
          <p className="mt-1 text-sm text-ink-500">
            {hasRequiredMaterial
              ? `Materiał główny jest gotowy. Dodano ${secondaryStories.filter(story => story.headline.trim() && story.body.trim()).length} tematów pobocznych i ${photos.length} zdjęć.`
              : 'Wpisz nagłówek i tekst głównego materiału. Potem przygotujemy kilka różnych układów.'}
          </p>
        </div>
        <Button variant="editorial" size="lg" isLoading={isGenerating}
          leftIcon={hasRequiredMaterial ? <Sparkles className="w-5 h-5" /> : <ArrowRight className="w-5 h-5" />}
          onClick={hasRequiredMaterial ? () => handleRunGenerator() : goToMainMaterial}>
          {isGenerating ? generationProgress || 'Generowanie wariantów…' : hasRequiredMaterial ? `Generuj ${warianty(candidateCount)}` : 'Przejdź do głównego materiału'}
        </Button>
      </section>
    </div>
  );
};
