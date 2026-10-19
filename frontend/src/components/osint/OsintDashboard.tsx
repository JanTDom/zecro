import React from 'react';
import { Activity, AlertTriangle, ArrowUpRight, Check, ChevronDown, Clock3, CopyCheck, ExternalLink, Globe2, MapPin, Plus, Radar, RefreshCw, ScanSearch, Settings2, ShieldAlert, X } from 'lucide-react';
import { api } from '../../api/client';
import { safeStorage } from '../../safeStorage';

type Source = { id: string; label: string; url: string; kind: 'publisher' | 'competitor' | 'institution' | 'wire'; region: string };
type Scan = Record<string, any>;

const SOURCE_KEY = 'zecro_osint_sources_v1';
const KIND_LABEL: Record<Source['kind'], string> = { publisher: 'Nasza redakcja', competitor: 'Konkurencja', institution: 'Instytucja', wire: 'Agencja / depesza' };
const KIND_COLOR: Record<Source['kind'], string> = { publisher: '#5e81ff', competitor: '#ff6b5f', institution: '#f3b94e', wire: '#9e8bff' };

const starterSources: Source[] = [
  { id: 'wroclaw-city', label: 'Wrocław.pl — urząd', url: 'https://www.wroclaw.pl/dla-mieszkanca/rss', kind: 'institution', region: 'Wrocław' },
  { id: 'policja', label: 'Policja — komunikaty', url: 'https://www.policja.pl/pol/rss/', kind: 'institution', region: 'Polska' },
  { id: 'rmf24', label: 'RMF24 — konkurencja', url: 'https://www.rmf24.pl/feed', kind: 'competitor', region: 'Polska' },
  { id: 'onet', label: 'Onet — konkurencja', url: 'https://wiadomosci.onet.pl/.feed', kind: 'competitor', region: 'Polska' },
];

export const OsintDashboard: React.FC = () => {
  const [sources, setSources] = React.useState<Source[]>(() => {
    try { return JSON.parse(safeStorage.get(SOURCE_KEY) || 'null') || starterSources; } catch { return starterSources; }
  });
  const [publisherId, setPublisherId] = React.useState('');
  const [scan, setScan] = React.useState<Scan | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [showSources, setShowSources] = React.useState(false);
  const [draft, setDraft] = React.useState<Source>({ id: '', label: '', url: '', kind: 'competitor', region: 'Polska' });

  const runScan = async () => {
    setLoading(true); setError('');
    try { setScan(await api.scanOsint(sources, publisherId || undefined)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się wykonać skanu.'); }
    finally { setLoading(false); }
  };

  const updateSource = (id: string, patch: Partial<Source>) => setSources((current) => current.map((source) => source.id === id ? { ...source, ...patch } : source));
  const removeSource = (id: string) => { setSources((current) => current.filter((source) => source.id !== id)); if (publisherId === id) setPublisherId(''); };
  const addSource = () => {
    if (!draft.label.trim() || !draft.url.trim()) return;
    const id = draft.id.trim() || `source-${Date.now()}`;
    setSources((current) => [...current, { ...draft, id }]);
    setDraft({ id: '', label: '', url: '', kind: 'competitor', region: 'Polska' });
  };
  React.useEffect(() => { safeStorage.set(SOURCE_KEY, JSON.stringify(sources)); }, [sources]);

  const summary = scan?.summary || {};
  const blindspots = scan?.blindspots || [];
  const deadHeroes = scan?.dead_heroes || [];
  const copyMatches = scan?.copy_matches || [];
  const timeline = scan?.timeline || [];
  const heat = scan?.region_heat || [];

  return <div className="osint-shell">
    <div className="osint-topline"><div className="osint-brand"><span className="osint-brand-mark"><Radar size={18} /></span><span><strong>SZYBA ŚLEDCZA</strong><small>OSINT DLA REDAKCJI REGIONALNYCH</small></span></div><div className="osint-live"><span /> LIVE OSINT</div><div className="osint-scan-state">{loading ? 'SKANOWANIE ŹRÓDEŁ PUBLICZNYCH…' : scan ? `OSTATNI SKAN ${new Date(scan.scanned_at).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}` : 'GOTOWE DO SKANU'}</div><div className="osint-top-stats"><span>Źródła: <b>{summary.source_count || sources.length}</b></span><span>Live: <b>{summary.live_sources || 0}</b></span><span>Alerty: <b className={summary.blindspots ? 'is-alert' : ''}>{summary.blindspots || 0}</b></span></div></div>

    <div className="osint-body">
      <aside className="osint-rail"><div className="osint-rail-item active"><ScanSearch size={17} /> Pulpit</div><div className="osint-rail-item"><ShieldAlert size={17} /> Alerty <b>{summary.blindspots || 0}</b></div><div className="osint-rail-item" onClick={() => setShowSources((value) => !value)}><Globe2 size={17} /> Źródła <ChevronDown size={13} className={showSources ? 'rotate-180' : ''} /></div><div className="osint-rail-item"><MapPin size={17} /> Region</div><div className="osint-rail-item"><CopyCheck size={17} /> Dowody</div><div className="osint-rail-item"><Clock3 size={17} /> Archiwum</div><div className="osint-rail-bottom"><span>TRYB</span><strong><i /> LIVE OSINT</strong><p>Monitorujemy publiczne źródła. Wskazujemy to, co inni przegapili.</p></div></aside>

      <main className="osint-main">
        <div className="osint-heading"><div><p className="osint-kicker">PUBLICZNE ŹRÓDŁA · DOWODY · TEMPO</p><h1>Co przegapiliśmy dzisiaj?</h1><p>Porównaj to, co dzieje się w regionie, z tym, o czym informujemy. Każdy sygnał ma źródło, czas i link do ręcznej weryfikacji.</p></div><button className="osint-scan-button" onClick={() => void runScan()} disabled={loading}><RefreshCw size={16} className={loading ? 'spin' : ''} />{loading ? 'Skanuję…' : 'Skanuj teraz'}</button></div>

        {error && <div className="osint-error"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError('')} aria-label="Zamknij komunikat"><X size={15} /></button></div>}
        {!publisherId && <div className="osint-setup-note"><Settings2 size={17} /><span><b>Dodaj źródło własnej redakcji</b>, aby odblokować radar „brakuje u nas”, martwą jedynkę i porównanie przepisywania.</span><button onClick={() => setShowSources(true)}>Skonfiguruj źródła <ArrowUpRight size={14} /></button></div>}

        <section className="osint-heat"><div className="osint-section-head"><div><span>AKTYWNOŚĆ W REGIONIE</span><small>ostatni skan publicznych kanałów</small></div><span className="osint-muted">{scan ? `${summary.items || 0} materiałów` : 'brak skanu'}</span></div><div className="osint-heat-grid">{Array.from({ length: Math.max(12, heat.length * 4 || 36) }, (_, index) => <i key={index} style={{ opacity: heat.length ? 0.35 + (((index * 7) % 10) / 14) : 0.22, background: index % 11 === 0 ? '#ff6b5f' : index % 7 === 0 ? '#f3b94e' : '#4d6fff' }} />)}</div><div className="osint-heat-labels">{(heat.length ? heat.slice(0, 8) : [{ region: 'Dodaj źródła regionalne', count: 0 }]).map((item: any) => <span key={item.region}>{item.region}</span>)}</div></section>

        <div className="osint-grid">
          <section className="osint-panel osint-panel-alerts"><div className="osint-section-head"><div><span>PRZESPANE TEMATY</span><b className="osint-count coral">{blindspots.length}</b></div><span className="osint-muted">wiele źródeł · brak u nas</span></div>{blindspots.length === 0 ? <EmptyState text={scan ? 'Brak potwierdzonego blindspotu w tym skanie.' : 'Uruchom skan, aby porównać publiczne kanały.'} /> : <div className="osint-alert-list">{blindspots.slice(0, 6).map((item: any) => <article className="osint-alert-row" key={item.id}><div className="osint-alert-time">{item.first_seen_at ? new Date(item.first_seen_at).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '—'}<MapPin size={12} />{item.region}</div><div className="osint-alert-copy"><h3>{item.title}</h3><p>{item.explanation}</p><div>{item.sources.slice(0, 3).map((source: any) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.label}<ExternalLink size={11} /></a>)}</div></div><strong className="osint-source-count">{item.source_count}<small>źródła</small></strong></article>)}</div>}</section>

          <section className="osint-panel osint-panel-hero"><div className="osint-section-head"><div><span>JEDYNKA <em>vs</em> TOP CZYTANE</span></div><span className="osint-select">Publiczne dane <ChevronDown size={13} /></span></div>{deadHeroes.length === 0 ? <EmptyState text={publisherId ? (scan ? 'Nie znaleziono publicznego boksu popularności lub martwej jedynki.' : 'Uruchom skan źródła własnego.') : 'Wybierz źródło własnej redakcji w konfiguracji.'} /> : deadHeroes.slice(0, 1).map((item: any) => <div className="osint-hero-evidence" key={item.id}><div><span className="osint-blue-label">NASZA JEDYNKA</span><h3>{item.title}</h3><a href={item.url} target="_blank" rel="noreferrer">Otwórz publiczny materiał <ExternalLink size={12} /></a></div><div className="osint-dead-alert"><AlertTriangle size={20} /><strong>MARTWA JEDYNKA</strong><small>Brak w boksie popularności · {item.popular_count} wykrytych pozycji</small></div></div>)}</section>
        </div>

        <div className="osint-grid osint-grid-bottom"><section className="osint-panel"><div className="osint-section-head"><div><span>OŚ CZASU ALERTÓW</span><small>ostatnie 12 sygnałów</small></div><Activity size={16} className="osint-blue" /></div>{timeline.length === 0 ? <EmptyState text="Po skanie pojawi się chronologia publikacji i źródeł." /> : <div className="osint-timeline">{timeline.map((item: any) => <div key={item.id}><i className={item.kind === 'institution' ? 'amber' : 'blue'} /><time>{item.time ? new Date(item.time).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '—'}</time><b>{item.region}</b><span>{item.title}</span><small>{item.source}</small></div>)}</div>}</section><section className="osint-panel osint-proof"><div className="osint-section-head"><div><span>DOWODY</span><b className="osint-count amber">{copyMatches.length}</b></div><span className="osint-muted">do ręcznej weryfikacji</span></div>{copyMatches.length === 0 ? <EmptyState text={publisherId ? 'Brak mocnego podobieństwa do komunikatu w tym skanie.' : 'Ustaw źródło własnej redakcji, aby porównać teksty z komunikatami.'} /> : <div className="osint-proof-list">{copyMatches.slice(0, 5).map((item: any) => <div key={item.id}><div><span className="osint-proof-score">KOPIA KOMUNIKATU {item.score}%</span><h3>{item.title}</h3><small>{item.source_label}</small></div><a href={item.source_url} target="_blank" rel="noreferrer" aria-label="Otwórz źródło"><ExternalLink size={16} /></a></div>)}</div>}</section></div>

        {showSources && <section className="osint-sources"><div className="osint-section-head"><div><span>ŹRÓDŁA PUBLICZNE</span><small>RSS, Atom lub strona HTML · maks. 12 · skan wyłącznie po kliknięciu</small></div><button className="osint-close" onClick={() => setShowSources(false)}><X size={15} /></button></div><div className="osint-source-table">{sources.map((source) => <div className="osint-source-row" key={source.id}><span className="osint-source-dot" style={{ background: KIND_COLOR[source.kind] }} /><input value={source.label} onChange={(event) => updateSource(source.id, { label: event.target.value })} aria-label={`Nazwa źródła ${source.label}`} /><select value={source.kind} onChange={(event) => updateSource(source.id, { kind: event.target.value as Source['kind'] })} aria-label={`Typ źródła ${source.label}`}>{Object.entries(KIND_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input value={source.region} onChange={(event) => updateSource(source.id, { region: event.target.value })} aria-label={`Region źródła ${source.label}`} /><code title={source.url}>{source.url}</code><button onClick={() => removeSource(source.id)} aria-label={`Usuń ${source.label}`}><X size={14} /></button></div>)}</div><div className="osint-add-source"><input placeholder="Nazwa źródła" value={draft.label} onChange={(event) => setDraft({ ...draft, label: event.target.value })} /><input placeholder="https://…/rss" value={draft.url} onChange={(event) => setDraft({ ...draft, url: event.target.value })} /><select value={draft.kind} onChange={(event) => setDraft({ ...draft, kind: event.target.value as Source['kind'] })}>{Object.entries(KIND_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input placeholder="Region" value={draft.region} onChange={(event) => setDraft({ ...draft, region: event.target.value })} /><button onClick={addSource}><Plus size={14} /> Dodaj</button></div><label className="osint-publisher-select"><span>Źródło własnej redakcji</span><select value={publisherId} onChange={(event) => setPublisherId(event.target.value)}><option value="">Nie ustawiono</option>{sources.filter((source) => source.kind === 'publisher').map((source) => <option key={source.id} value={source.id}>{source.label}</option>)}</select><small>To źródło jest punktem odniesienia dla „brakuje u nas”.</small></label><p className="osint-source-footnote"><Check size={13} /> Zecro zapisuje tylko konfigurację w tej przeglądarce. Wyniki są liczone z publicznych odpowiedzi HTTP w chwili skanu.</p></section>}
      </main>
    </div>
  </div>;
};

const EmptyState: React.FC<{ text: string }> = ({ text }) => <div className="osint-empty"><Radar size={21} /><span>{text}</span></div>;
