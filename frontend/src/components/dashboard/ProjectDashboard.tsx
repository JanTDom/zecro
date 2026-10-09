import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { ArrowUpRight, FileText, FolderOpen, Maximize2, Plus, Sparkles } from 'lucide-react';
import { Button } from '../common/Button';

const proofTitles = [
  { label: 'Strona 01 — Okładka', title: 'Nowa energia dla regionu', accent: '#ff6b4a', image: 'front' },
  { label: 'Strony 02–03 — Rozkładówka', title: 'Miasto, które słucha mieszkańców', accent: '#2451f5', image: 'spread' },
  { label: 'Strona 04 — Tył', title: 'Sztuka bliżej ludzi', accent: '#23c6ac', image: 'back' },
];

function ProofFallback({ type, title, accent }: { type: string; title: string; accent: string }) {
  return (
    <div className={`proof-page proof-${type}`}>
      <div className="h-1.5 w-9 rounded-full mb-3" style={{ background: accent }} />
      <div className="flex items-center justify-between mb-4"><span className="font-headline text-[10px] text-ink-100">Zecro Daily</span><span className="text-[7px] font-mono text-ink-500">12 MAJA 2026</span></div>
      <h3 className="font-headline text-[22px] leading-[0.94] tracking-tight text-ink-100 max-w-[90%]">{title}</h3>
      <div className="proof-photo mt-4" style={{ background: `linear-gradient(135deg, ${accent} 0%, #151821 78%)` }}><span className="text-white/80 text-[8px] font-mono uppercase tracking-[0.18em]">Editorial proof</span></div>
      <div className="grid grid-cols-3 gap-2 mt-3"><i /><i /><i /></div>
      <div className="proof-lines mt-3"><i /><i /><i /><i /><i /></div>
    </div>
  );
}

function CandidateProof({ svg, selected }: { svg: string; selected?: boolean }) {
  const src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  return <div className={`h-full w-full flex items-center justify-center bg-white ${selected ? 'ring-2 ring-editorial-crimson ring-offset-2 ring-offset-white' : ''}`}><img src={src} alt="Wygenerowany proof strony" className="max-h-full max-w-full object-contain" /></div>;
}

export const ProjectDashboard: React.FC = () => {
  const { activeProject, currentRun, setActiveTab } = useProject();

  if (!activeProject) {
    return <div className="min-h-full flex items-center justify-center text-sm text-ink-400">Wybierz projekt, aby otworzyć studio.</div>;
  }

  const candidates = currentRun?.candidates || [];
  const hasProofs = candidates.length > 0;

  return (
    <div className="max-w-[1500px] mx-auto px-5 sm:px-8 lg:px-12 py-10 lg:py-12 space-y-8 animate-fade-in">
      <section className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-500 mb-4">ZECRO / STUDIO REDAKCYJNE</p>
          <h1 className="font-headline text-5xl lg:text-[4.2rem] leading-[0.94] tracking-[-0.045em] text-ink-100">Studio redakcyjne</h1>
          <p className="mt-4 max-w-xl text-[15px] leading-7 text-ink-300">Od materiału do autorskiej strony. Twój warsztat w jednym miejscu.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="md" leftIcon={<FolderOpen className="w-4 h-4" />} onClick={() => setActiveTab('projects')}>Otwórz projekt</Button>
          <Button variant="editorial" size="md" leftIcon={<Sparkles className="w-4 h-4" />} onClick={() => setActiveTab('generate')}>Generuj stronę</Button>
        </div>
      </section>

      <section className="bg-white border border-ink-800 rounded-xl grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-ink-800 shadow-[0_8px_24px_rgba(28,34,49,0.04)]">
        <Metric icon={<FileText className="w-4 h-4" />} accent="bg-blue-50 text-editorial-crimson" value="1 041" label="stron referencyjnych" />
        <Metric icon={<FolderOpen className="w-4 h-4" />} accent="bg-violet-50 text-editorial-violet" value="51" label="tytułów w korpusie" />
        <Metric icon={<Sparkles className="w-4 h-4" />} accent="bg-amber-50 text-editorial-ochre" value="5" label="archetypów stylu" />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_310px] gap-6 items-stretch">
        <div className="bg-white border border-ink-800 rounded-xl overflow-hidden shadow-[0_8px_24px_rgba(28,34,49,0.04)]">
          <div className="px-6 py-5 border-b border-ink-800 flex items-center justify-between gap-4">
            <div><p className="text-[10px] uppercase tracking-[0.18em] font-mono text-ink-500">Ostatnia przestrzeń robocza</p><h2 className="font-headline text-2xl text-ink-100 mt-1">Twoja przestrzeń twórcza</h2></div>
            <div className="flex items-center gap-2"><span className="hidden sm:inline text-[11px] font-mono text-ink-500">{hasProofs ? `${candidates.length} wariantów` : 'widok: strony'}</span><button aria-label="Powiększ przestrzeń roboczą" className="w-8 h-8 rounded-md border border-ink-800 flex items-center justify-center text-ink-400 hover:text-ink-100 hover:bg-ink-950"><Maximize2 className="w-3.5 h-3.5" /></button></div>
          </div>
          <div className="workspace-board p-6 lg:p-8 min-h-[460px] flex items-center justify-center">
            <div className="w-full grid grid-cols-1 md:grid-cols-[0.72fr_1fr_0.72fr] gap-4 lg:gap-6 items-center max-w-[930px]">
              {proofTitles.map((proof, index) => {
                const candidate = candidates[index];
                return <div key={proof.label} className={`space-y-3 ${index === 1 ? 'md:-translate-y-3' : ''}`}><p className={`text-center text-[10px] font-mono ${index === 1 ? 'text-editorial-crimson' : 'text-ink-500'}`}>{candidate ? `Wariant ${String(index + 1).padStart(2, '0')}` : proof.label}</p><div className={`proof-frame ${index === 1 ? 'selected-proof' : ''}`}>{candidate?.thumbnailSvg ? <CandidateProof svg={candidate.thumbnailSvg} selected={index === 1} /> : <ProofFallback type={proof.image} title={proof.title} accent={proof.accent} />}</div><div className="flex items-center justify-between text-[10px] font-mono text-ink-500"><span>{candidate ? `Score ${Math.round(candidate.criticScore * 100)}%` : 'Proof preview'}</span><span>{candidate?.passHardGates ? 'PASS' : candidate ? 'REVIEW' : '—'}</span></div></div>;
              })}
            </div>
          </div>
        </div>

        <aside className="bg-white border border-ink-800 rounded-xl p-6 shadow-[0_8px_24px_rgba(28,34,49,0.04)] flex flex-col">
          <div className="w-9 h-9 rounded-lg bg-blue-50 text-editorial-crimson flex items-center justify-center mb-5"><Plus className="w-5 h-5" /></div>
          <p className="text-[10px] uppercase tracking-[0.18em] font-mono text-ink-500">Nowy kierunek</p>
          <h2 className="font-headline text-2xl text-ink-100 mt-2">Zacznij od tytułu</h2>
          <p className="text-[13px] leading-6 text-ink-300 mt-3">Utwórz projekt i wygeneruj autorskie strony swojego tytułu z pomocą AI. Od materiału po gotowy layout.</p>
          <Button variant="editorial" size="md" className="w-full mt-6" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setActiveTab('projects')}>Nowy projekt</Button>
          <div className="mt-7 border-t border-ink-800 pt-5"><p className="text-[11px] font-semibold text-ink-200 mb-4">Jak to działa?</p><WorkflowStep number="01" label="Materiały" detail="Dodaj teksty, zdjęcia lub linki." color="bg-editorial-cyan" /><WorkflowStep number="02" label="DNA i styl" detail="Dopasuj siatkę i język wizualny." color="bg-editorial-violet" /><WorkflowStep number="03" label="Warianty" detail="Wygeneruj i porównaj propozycje." color="bg-editorial-ochre" /><WorkflowStep number="04" label="Produkcja" detail="Dopracuj w edytorze i eksportuj." color="bg-editorial-vermilion" last /></div>
        </aside>
      </section>

      <section className="bg-white border border-ink-800 rounded-xl overflow-hidden shadow-[0_8px_24px_rgba(28,34,49,0.04)]">
        <div className="px-6 py-5 flex items-center justify-between border-b border-ink-800"><div><p className="text-[10px] uppercase tracking-[0.18em] font-mono text-ink-500">Historia pracy</p><h2 className="font-headline text-2xl text-ink-100 mt-1">Ostatnie generacje</h2></div><button onClick={() => setActiveTab('gallery')} className="flex items-center gap-2 text-[12px] font-semibold text-editorial-crimson hover:text-[#173ed0]">Zobacz galerię <ArrowUpRight className="w-3.5 h-3.5" /></button></div>
        {hasProofs ? <div className="divide-y divide-ink-800">{candidates.slice(0, 4).map((candidate) => <div key={candidate.id} className="grid grid-cols-[1fr_120px_110px_100px] items-center gap-4 px-6 py-4 text-[12px]"><span className="font-semibold text-ink-200">Generacja {candidate.candidateNumber.toString().padStart(2, '0')}</span><span className="text-ink-500 font-mono">{Math.round(candidate.criticScore * 100)}% score</span><span className={candidate.passHardGates ? 'text-emerald-600' : 'text-amber-600'}>{candidate.passHardGates ? 'PASS' : 'REVIEW'}</span><span className="text-right font-mono text-ink-500">{new Date(candidate.createdAt).toLocaleDateString('pl-PL')}</span></div>)}</div> : <div className="py-12 text-center"><div className="w-10 h-10 rounded-lg bg-ink-950 border border-ink-800 mx-auto flex items-center justify-center text-ink-500"><FileText className="w-4 h-4" /></div><p className="mt-4 text-[13px] text-ink-300">Brak generacji. Utwórz projekt, aby rozpocząć.</p><button onClick={() => setActiveTab('generate')} className="mt-2 text-[12px] font-semibold text-editorial-crimson hover:underline">Przejdź do generatora</button></div>}
      </section>
    </div>
  );
};

function Metric({ icon, accent, value, label }: { icon: React.ReactNode; accent: string; value: string; label: string }) {
  return <div className="flex items-center gap-3 px-6 py-5"><span className={`w-9 h-9 rounded-lg flex items-center justify-center ${accent}`}>{icon}</span><div><p className="font-headline text-2xl leading-none text-ink-100">{value}</p><p className="text-[11px] text-ink-500 mt-1">{label}</p></div></div>;
}

function WorkflowStep({ number, label, detail, color, last }: { number: string; label: string; detail: string; color: string; last?: boolean }) {
  return <div className={`flex gap-3 py-3 ${last ? '' : 'border-b border-ink-800'}`}><span className={`w-6 h-6 rounded-md ${color} text-white text-[10px] font-mono flex items-center justify-center shrink-0`}>{number}</span><div><p className="text-[12px] font-semibold text-ink-200">{label}</p><p className="text-[11px] leading-5 text-ink-500 mt-0.5">{detail}</p></div></div>;
}
