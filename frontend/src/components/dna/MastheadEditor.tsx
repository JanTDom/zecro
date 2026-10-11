import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { apiUrl } from '../../api/client';
import { studio, errText, Data } from '../../api/studio';

// Masthead: upload the paper's logo (SVG/PDF/PNG/JPG), see the measured
// geometry, colours (RGB→CMYK, TAC), preflight and the AI reading of the
// lettering; approve palette and font pairing.  The composer then derives
// the masthead band from the logo's proportions.
const publicUrl = (ref?: string) => ref ? (/^(https?:|\/static\/)/.test(ref) ? apiUrl(ref) : apiUrl(`/static/uploads/${ref.split('/').pop()}`)) : '';

export const MastheadEditor: React.FC<{ onApproved?: () => void }> = ({ onApproved }) => {
  const { activeProject } = useProject();
  const [profile, setProfile] = React.useState<Data | null>(null);
  const [status, setStatus] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [pairing, setPairing] = React.useState(0);
  const [useVector, setUseVector] = React.useState(false);
  const [applyPalette, setApplyPalette] = React.useState(true);

  React.useEffect(() => {
    if (!activeProject) return;
    studio.dna(activeProject.id).then(d => setProfile(d.logo_profile || null)).catch(() => setProfile(null));
  }, [activeProject?.id]);
  if (!activeProject) return null;

  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true); setStatus('Analizuję logo: proporcje, kolory, preflight, krój liter (AI)…');
    try { const r = await studio.uploadLogo(activeProject.id, file); setProfile(r.logo_profile); setStatus('Logo przeanalizowane. Sprawdź i zatwierdź.'); }
    catch (e) { setStatus(`Nie przyjęto logo: ${errText(e)}`); } finally { setBusy(false); }
  };
  const approve = async () => {
    setBusy(true);
    try { const r = await studio.approveLogo(activeProject.id, { use_vector: useVector, apply_palette: applyPalette, font_pairing_index: pairing });
      setProfile(r.dna.logo_profile); setStatus('Winieta zatwierdzona. Generator dopasuje do niej pas winiety, paletę i fonty.'); onApproved?.(); }
    catch (e) { setStatus(`Nie zatwierdzono: ${errText(e)}`); } finally { setBusy(false); }
  };
  const ai = profile?.ai_analysis || {};
  const isPdf = /\.pdf$/i.test(profile?.asset_ref || '');
  return <section className="rounded-xl border bg-white p-5 space-y-4 text-sm text-ink-900">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="font-semibold text-base">Winieta i logo gazety</h2><p className="text-xs text-ink-500">SVG lub PDF dają wektor w druku; PNG/JPG można zwektoryzować automatycznie (wymaga akceptacji). EPS/AI zapisz jako PDF.</p></div>
      <label className="px-3 py-2 rounded bg-editorial-crimson text-white cursor-pointer">{busy ? 'Pracuję…' : 'Wgraj logo'}
        <input type="file" className="hidden" accept=".svg,.pdf,.png,.jpg,.jpeg,.webp" disabled={busy} onChange={e => void upload(e.target.files?.[0])} /></label>
    </div>
    {status && <p role="status" className="text-xs border rounded p-2">{status}</p>}
    {profile?.asset_ref ? <div className="grid md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <div className="border rounded p-4 bg-[#faf8f2] flex items-center justify-center min-h-[120px]">
          {isPdf ? <span className="text-xs text-ink-500">Podgląd PDF niedostępny w przeglądarce — logo trafi do PDF i IDML jako wektor.</span>
            : <img src={publicUrl(useVector && profile.vector_ref ? profile.vector_ref : profile.asset_ref)} alt="Logo" className="max-h-28 max-w-full object-contain" />}
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt>Proporcje</dt><dd>{profile.aspect_ratio?.toFixed(2)} : 1</dd>
          <dt>Układ winiety</dt><dd>{profile.layout_mode === 'ears' ? 'z uszami' : profile.layout_mode === 'side' ? 'boczny' : 'poziomy'}</dd>
          <dt>Minimalna szerokość</dt><dd>{profile.min_width_mm ? `${profile.min_width_mm.toFixed(1)} mm` : '—'}</dd>
          <dt>Pole ochronne</dt><dd>{profile.clear_space_mm} mm</dd>
          <dt>Wektor</dt><dd>{profile.vector ? 'tak' : profile.vector_ref ? 'auto-wektor gotowy' : 'nie (raster)'}{profile.raster_px ? ` · ${profile.raster_px.join('×')} px` : ''}</dd>
          <dt>Status</dt><dd>{profile.approved ? 'zatwierdzone' : 'szkic'}</dd>
        </dl>
        <div className="flex flex-wrap gap-2">{(profile.dominant_colors || []).map((c: string, i: number) => <span key={c} className="flex items-center gap-1 text-[11px] border rounded px-1.5 py-0.5">
          <span className="w-4 h-4 rounded border" style={{ background: c }} />{c}{profile.cmyk_colors?.[i] ? ` · CMYK ${profile.cmyk_colors[i].map((v: number) => Math.round(v)).join('/')}` : ''}</span>)}</div>
        {profile.preflight?.length > 0 && <ul className="text-xs list-disc pl-5">{profile.preflight.map((p: Data, i: number) => <li key={i} className={p.level === 'FAIL' ? 'text-red-700' : p.level === 'WARN' ? 'text-amber-700' : ''}>{p.message || p.code}</li>)}</ul>}
      </div>
      <div className="space-y-3">
        {ai.status === 'unavailable' ? <p className="text-xs text-amber-700">Analiza AI niedostępna: {ai.reason}</p> : ai.letter_style ? <>
          <p className="text-xs">Krój liter: <b>{ai.letter_style}</b>{ai.all_caps ? ', wersaliki' : ''}, kontrast {ai.contrast}{ai.character?.length ? ` · ${ai.character.join(', ')}` : ''}</p>
          {ai.masthead_advice && <p className="text-xs bg-blue-50 rounded p-2">{ai.masthead_advice}</p>}
          {ai.font_pairings?.length > 0 && <fieldset className="space-y-1"><legend className="text-xs font-semibold">Dobór fontów do winiety</legend>
            {ai.font_pairings.map((fp: Data, i: number) => <label key={i} className="flex gap-2 items-start text-xs border rounded p-2">
              <input type="radio" name="pairing" checked={pairing === i} onChange={() => setPairing(i)} />
              <span><b style={{ fontFamily: `"${fp.headline_family}"` }}>{fp.headline_family}</b> + <span style={{ fontFamily: `"${fp.body_family}"` }}>{fp.body_family}</span><br /><span className="text-ink-500">{fp.reason}</span></span></label>)}</fieldset>}
          {ai.palette_roles && <p className="text-xs">Paleta z logo: {Object.entries(ai.palette_roles).filter(([, v]) => v).map(([k, v]) => <span key={k} className="inline-flex items-center gap-1 mr-2">{k} <span className="w-3 h-3 inline-block border" style={{ background: v as string }} /></span>)}</p>}
        </> : <p className="text-xs text-ink-500">Brak analizy AI.</p>}
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={applyPalette} onChange={e => setApplyPalette(e.target.checked)} /> zastosuj kolor akcentu z logo</label>
        {profile.vector_ref && !profile.vector && <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={useVector} onChange={e => setUseVector(e.target.checked)} /> użyj automatycznej wektoryzacji (sprawdź podgląd)</label>}
        <button disabled={busy} onClick={() => void approve()} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Zatwierdź winietę</button>
      </div>
    </div> : <p className="text-xs text-ink-500">Brak logo. Bez logo generator składa winietę tekstową z nazwy tytułu.</p>}
  </section>;
};
