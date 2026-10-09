import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { NewspaperFormat, Project } from '../../types/project';
import { useProject } from '../../context/ProjectContext';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const FORMAT_PRESETS: Record<
  NewspaperFormat,
  { name: string; desc: string; widthMm: number; heightMm: number; cols: number; gutter: number; bleed: number }
> = {
  broadsheet: {
    name: 'Broadsheet Classic',
    desc: '375 × 560 mm • 6 columns • High-density traditional broadsheet',
    widthMm: 375,
    heightMm: 560,
    cols: 6,
    gutter: 4.0,
    bleed: 5,
  },
  berliner: {
    name: 'Berliner Standard',
    desc: '315 × 470 mm • 5 columns • Modern European standard format',
    widthMm: 315,
    heightMm: 470,
    cols: 5,
    gutter: 4.5,
    bleed: 3,
  },
  tabloid: {
    name: 'Tabloid / Compact',
    desc: '280 × 400 mm • 4 columns • Fast-paced urban tabloid layout',
    widthMm: 280,
    heightMm: 400,
    cols: 4,
    gutter: 5.0,
    bleed: 3,
  },
  compact: {
    name: 'Nordic Compact',
    desc: '290 × 410 mm • 4-5 columns • Generous Scandinavian whitespace',
    widthMm: 290,
    heightMm: 410,
    cols: 5,
    gutter: 4.0,
    bleed: 3,
  },
  custom: {
    name: 'Custom Editorial Trim',
    desc: 'Configure bespoke dimensions, gutters, and column subdivisions',
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
  const [accentFont, setAccentFont] = useState('Fraunces');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    try {
      const preset = FORMAT_PRESETS[format];
      await createProject({
        name,
        newspaperTitle: newspaperTitle.trim() || name.toUpperCase(),
        editionCode,
        format,
        themeColor,
        accentFont,
        description: description || `Editorial publishing workspace for ${name}.`,
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
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Nowy tytuł prasowy"
      subtitle="Każdy tytuł ma własny korpus, DNA gramatyki i model preferencji."
      maxWidth="xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Project Name & Masthead Title */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Nazwa projektu *
            </label>
            <input
              type="text"
              required
              placeholder="np. Gazeta Codzienna"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!newspaperTitle) setNewspaperTitle(e.target.value.toUpperCase());
              }}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-sm text-ink-100 placeholder:text-ink-600 focus:outline-none focus:border-editorial-crimson"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Nazwa winiety
            </label>
            <input
              type="text"
              placeholder="e.g. THE DAILY CHRONICLE"
              value={newspaperTitle}
              onChange={(e) => setNewspaperTitle(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-sm text-ink-100 font-headline placeholder:text-ink-600 focus:outline-none focus:border-editorial-crimson uppercase"
            />
          </div>
        </div>

        {/* Format Presets */}
        <div>
          <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-2">
            Format gazety i siatka modularna
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {(Object.keys(FORMAT_PRESETS) as NewspaperFormat[]).slice(0, 3).map((fmtKey) => {
              const p = FORMAT_PRESETS[fmtKey];
              const isSelected = format === fmtKey;
              return (
                <div
                  key={fmtKey}
                  onClick={() => setFormat(fmtKey)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson'
                      : 'bg-ink-950/60 border-ink-800 hover:border-ink-700'
                  }`}
                >
                  <p className="text-xs font-bold text-ink-100 mb-0.5">{p.name}</p>
                  <p className="text-[10px] text-ink-400 font-mono leading-tight">{p.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

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
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs font-mono text-ink-100 focus:outline-none focus:border-editorial-crimson uppercase"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase font-mono text-ink-300 mb-1">
              Font nagłówków
            </label>
            <select
              value={accentFont}
              onChange={(e) => setAccentFont(e.target.value)}
              className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-100 focus:outline-none focus:border-editorial-crimson"
            >
              <option value="Fraunces">Fraunces (Modern Editorial Serif)</option>
              <option value="Playfair Display">Playfair Display (Classic Serif)</option>
              <option value="Barlow Semi Condensed">Barlow Condensed (Dynamic Sans)</option>
              <option value="Inter">Inter (Clean Modernist Sans)</option>
            </select>
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
            placeholder="Briefly describe the editorial style, tone, and visual goals..."
            className="w-full px-3 py-2 bg-ink-950 border border-ink-700 rounded-lg text-xs text-ink-100 placeholder:text-ink-600 focus:outline-none focus:border-editorial-crimson resize-none"
          />
        </div>

        {/* Footer buttons */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-ink-800">
          <Button variant="ghost" type="button" onClick={onClose}>
            Anuluj
          </Button>
          <Button variant="editorial" type="submit" isLoading={isSubmitting}>
            Utwórz projekt tytułu
          </Button>
        </div>
      </form>
    </Modal>
  );
};
