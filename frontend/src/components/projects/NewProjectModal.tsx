import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { EditorialCharacter, NewspaperFormat } from '../../types/project';
import { useProject } from '../../context/ProjectContext';
import { studio } from '../../api/studio';
import { EDITORIAL_STYLES } from '../../editorialStyles';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const FORMAT_PRESETS: Record<
  NewspaperFormat,
  { name: string; desc: string; widthMm: number; heightMm: number; cols: number; gutter: number; bleed: number }
> = {
  broadsheet: {
    name: 'Duża gazeta',
    desc: '375 × 560 mm · tradycyjny duży format',
    widthMm: 375,
    heightMm: 560,
    cols: 6,
    gutter: 4.0,
    bleed: 5,
  },
  berliner: {
    name: 'Średnia gazeta',
    desc: '315 × 470 mm · wygodny format codzienny',
    widthMm: 315,
    heightMm: 470,
    cols: 5,
    gutter: 4.5,
    bleed: 3,
  },
  tabloid: {
    name: 'Mała gazeta',
    desc: '280 × 400 mm · poręczny format',
    widthMm: 280,
    heightMm: 400,
    cols: 4,
    gutter: 5.0,
    bleed: 3,
  },
  compact: {
    name: 'Kompaktowa gazeta',
    desc: '290 × 410 mm · więcej wolnej przestrzeni',
    widthMm: 290,
    heightMm: 410,
    cols: 5,
    gutter: 4.0,
    bleed: 3,
  },
  custom: {
    name: 'Własny rozmiar',
    desc: 'Ustaw własne wymiary i podział strony',
    widthMm: 310,
    heightMm: 450,
    cols: 5,
    gutter: 4.0,
    bleed: 3,
  },
};

export const NewProjectModal: React.FC<NewProjectModalProps> = ({ isOpen, onClose }) => {
  const { createProject, setActiveTab } = useProject();
  const [name, setName] = useState('');
  const [newspaperTitle, setNewspaperTitle] = useState('');
  const [editionCode, setEditionCode] = useState('ED-01');
  const [format, setFormat] = useState<NewspaperFormat>('berliner');
  const [description, setDescription] = useState('');
  const [themeColor, setThemeColor] = useState('#2451f5');
  const [accentFont, setAccentFont] = useState('');
  const [editorialCharacter, setEditorialCharacter] = useState<EditorialCharacter>('analysis');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [availableFonts, setAvailableFonts] = useState<string[]>([]);

  React.useEffect(() => {
    if (!isOpen) return;
    let active = true;
    void studio.fonts(true).then(rows => {
      if (active) setAvailableFonts(rows
        .filter(row => !String(row.family).startsWith('.') && row.faces?.some((face: { polish?: string }) => face.polish === 'full'))
        .map(row => String(row.family)));
    }).catch(() => { if (active) setAvailableFonts([]); });
    return () => { active = false; };
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setSubmitError('');
    try {
      const preset = FORMAT_PRESETS[format];
      await createProject({
        name,
        newspaperTitle: newspaperTitle.trim() || name.toUpperCase(),
        editionCode,
        format,
        themeColor,
        accentFont,
        editorialCharacter,
        description: description || `Gazeta ${name}.`,
        dimensions: {
          widthMm: preset.widthMm,
          heightMm: preset.heightMm,
          columnsCount: preset.cols,
          gutterMm: preset.gutter,
          marginTopMm: 16,
          marginBottomMm: 20,
          marginLeftMm: 14,
          marginRightMm: 14,
          bleedMm: preset.bleed,
        },
      });
      onClose();
      setActiveTab('dashboard');
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Nie udało się utworzyć gazety. Spróbuj ponownie.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Nowa gazeta"
      subtitle="Podaj nazwę, wybierz rodzaj gazety i rozmiar papieru. Program zaproponuje krój pisma i układ."
      maxWidth="xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Project Name & Masthead Title */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Nazwa gazety *
            </label>
            <input
              type="text"
              required
              placeholder="np. Gazeta Codzienna"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-sm text-ink-100 placeholder:text-ink-600 focus:outline-hidden focus:border-editorial-crimson"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Napis na górze pierwszej strony (opcjonalnie)
            </label>
            <input
              type="text"
              placeholder={name.trim() ? name.trim().toUpperCase() : 'np. GAZETA CODZIENNA'}
              value={newspaperTitle}
              onChange={(e) => setNewspaperTitle(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-sm text-ink-100 font-headline placeholder:text-ink-600 focus:outline-hidden focus:border-editorial-crimson uppercase"
            />
          </div>
        </div>

        <fieldset>
          <legend className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-2">Jaką gazetę chcesz zrobić?</legend>
          {(['ogólne', 'tematyczne'] as const).map(group => <div key={group} className="mt-3">
            <p className="mb-2 text-xs font-semibold text-ink-300">{group === 'ogólne' ? 'Gazety i magazyny ogólne' : 'Gazety o wybranym temacie'}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {EDITORIAL_STYLES.filter(option => option.group === group).map((option) => <button key={option.id} type="button" aria-pressed={editorialCharacter === option.id}
              onClick={() => setEditorialCharacter(option.id)}
              className={`p-3 rounded-lg border text-left ${editorialCharacter === option.id ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson' : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'}`}>
              <span className="block text-xs font-bold text-ink-100">{option.name}</span>
              <span className="block text-[11px] text-ink-400 mt-1">{option.description}</span>
            </button>)}
            </div>
          </div>)}
          <p className="text-[11px] text-ink-400 mt-2">To punkt wyjścia, który możesz później zmienić. Rozmiar papieru wybierzesz osobno.</p>
        </fieldset>

        {/* Format Presets */}
        <div>
          <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-2">
            Rozmiar strony
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {(Object.keys(FORMAT_PRESETS) as NewspaperFormat[]).slice(0, 3).map((fmtKey) => {
              const p = FORMAT_PRESETS[fmtKey];
              const isSelected = format === fmtKey;
              return (
                <button type="button"
                  key={fmtKey}
                  onClick={() => setFormat(fmtKey)}
                  aria-pressed={isSelected}
                  className={`p-3 rounded-lg border cursor-pointer transition-all text-left ${
                    isSelected
                      ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                      : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
                  }`}
                >
                  <p className="text-xs font-bold text-ink-100 mb-0.5">{p.name}</p>
                  <p className="text-[10px] text-ink-400 font-mono leading-tight">{p.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        <details className="rounded-lg border border-ink-800 p-3"><summary className="cursor-pointer text-sm font-semibold text-ink-200">Dodatkowe ustawienia (opcjonalnie)</summary>
        {/* Kod wydania & Brand Accent */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Kod wydania
            </label>
            <input
              type="text"
              value={editionCode}
              onChange={(e) => setEditionCode(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs font-mono text-ink-100 focus:outline-hidden focus:border-editorial-crimson uppercase"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Krój pisma nagłówków
            </label>
            <select
              value={accentFont}
              onChange={(e) => setAccentFont(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-100 focus:outline-hidden focus:border-editorial-crimson"
            >
              <option value="">Dobierz automatycznie do charakteru gazety</option>
              {availableFonts.map(family => <option key={family} value={family}>{family}</option>)}
            </select>
            <p className="mt-1 text-[11px] text-ink-400">{availableFonts.length ? `${availableFonts.length} krojów z pełnymi polskimi znakami w bibliotece.` : 'Trwa sprawdzanie biblioteki krojów. Automatyczny dobór działa bez tego kroku.'}</p>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Kolor akcentu
            </label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={themeColor}
                onChange={(e) => setThemeColor(e.target.value)}
                className="w-8 h-8 rounded border border-ink-700 bg-transparent cursor-pointer"
              />
              <span className="text-xs font-mono text-ink-300">{themeColor}</span>
            </div>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
            Opis i zasady redakcyjne
          </label>
          <textarea
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Np. spokojna gazeta lokalna z dużymi zdjęciami i krótkimi tekstami"
            className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-100 placeholder:text-ink-600 focus:outline-hidden focus:border-editorial-crimson resize-none"
          />
        </div></details>

        {/* Footer buttons */}
        {submitError && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{submitError}</p>}
        <div className="sticky bottom-0 z-10 -mx-6 -mb-6 flex items-center justify-end gap-3 border-t border-ink-800 bg-white/95 px-6 py-3 shadow-[0_-8px_20px_rgba(0,0,0,0.08)] backdrop-blur-sm">
          <Button variant="ghost" type="button" onClick={onClose}>
            Anuluj
          </Button>
          <Button variant="editorial" type="submit" isLoading={isSubmitting}>
            Utwórz gazetę
          </Button>
        </div>
      </form>
    </Modal>
  );
};
