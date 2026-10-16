import React from 'react';
import { studio, setAdminToken, errText, Data } from '../../api/studio';
import { FontLibrary } from './FontLibrary';

// Settings: any AI model or source API can be added, tested (model list +
// probe call, or raw response + mapping), routed per task with fallbacks,
// budgeted and audited.  Secrets go to the server only.
const TABS = ['Modele AI', 'Routing zadań', 'Źródła zdjęć', 'Źródła tekstów', 'Własne API', 'Archiwum', 'Fonty', 'Limity i koszty', 'Dziennik zmian'] as const;
type Tab = typeof TABS[number];
const KIND_FOR: Partial<Record<Tab, string>> = { 'Modele AI': 'ai_provider', 'Źródła zdjęć': 'photo_source', 'Źródła tekstów': 'text_source', 'Archiwum': 'storage', 'Własne API': 'photo_source' };
const PROVIDERS: Record<string, string[]> = {
  ai_provider: ['gemini', 'openai', 'anthropic', 'mistral', 'openai_compatible', 'custom'],
  photo_source: ['wikimedia', 'openverse', 'unsplash', 'pexels', 'pixabay', 'custom'],
  text_source: ['custom'], storage: ['custom'], agency: ['custom'],
};
const TASK_LABEL: Record<string, string> = {
  page_planning: 'Plan strony', copy_fit: 'Dopasowanie tekstu', headline_variants: 'Warianty tytułów', write_from_brief: 'Pisanie z briefu',
  fact_guard: 'Strażnik faktów', translate: 'Tłumaczenie', teaser: 'Zapowiedź', caption: 'Podpis zdjęcia', pullquote: 'Cytat', infobox: 'Ramka faktów',
  photo_brief: 'Brief zdjęciowy', photo_ranking: 'Ranking zdjęć', image_generation: 'Generowanie ilustracji', mask_qa: 'Kontrola maski', subject_segmentation: 'Wycinanie sylwetek ze zdjęć',
  visual_critic: 'Krytyk wizualny', corpus_audit: 'Audyt korpusu', embeddings: 'Wyszukiwanie podobnych treści', logo_analysis: 'Analiza logo', font_pairing: 'Dobór krojów pisma',
};
const CUSTOM_TEMPLATE = JSON.stringify({
  type: 'rest', base_url: 'https://api.example.com',
  auth: { type: 'header', name: 'X-Api-Key' },
  request: { method: 'GET', url: 'https://api.example.com/search', query: { q: '{{ query }}', limit: '{{ limit }}' } },
  mapping: { items: '$.results[*]', fields: { url: '$.image.full', thumb_url: '$.image.thumb', title: '$.title', credit_line: '$.author', license: '$.license', width_px: '$.image.w', height_px: '$.image.h' } },
}, null, 2);

const STATUS_LABEL: Record<string, string> = { ready: 'Gotowe', configured: 'Skonfigurowane', unavailable: 'Niedostępne', unconfigured: 'Nieustawione', warning: 'Wymaga uwagi', error: 'Błąd' };
const Status: React.FC<{ s?: string }> = ({ s }) => <span className={`px-1.5 py-0.5 rounded text-[11px] ${s === 'ready' ? 'bg-green-100 text-green-800' : s === 'error' ? 'bg-red-100 text-red-800' : s === 'warning' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{STATUS_LABEL[s || ''] || s || '—'}</span>;

export const IntegrationsSettings: React.FC = () => {
  const [tab, setTab] = React.useState<Tab>('Modele AI');
  const [token, setToken] = React.useState('');
  const [adminUnlocked, setAdminUnlocked] = React.useState(false);
  const [adminOpen, setAdminOpen] = React.useState(false);
  const [overview, setOverview] = React.useState<{ integrations: Data[]; tasks: Record<string, Data> } | null>(null);
  const [overviewError, setOverviewError] = React.useState('');
  const [items, setItems] = React.useState<Data[]>([]);
  const [status, setStatus] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [tests, setTests] = React.useState<Record<string, Data>>({});
  const [form, setForm] = React.useState<Data>({ provider: 'gemini', label: '', base_url: '', model: '', api_key: '', config: CUSTOM_TEMPLATE });
  const [routing, setRouting] = React.useState<Data>({});
  const [limits, setLimits] = React.useState<Data>({});
  const [pricesText, setPricesText] = React.useState('{}');
  const [audit, setAudit] = React.useState<Data[]>([]);
  const [photoSources, setPhotoSources] = React.useState<Data[] | null>(null);
  const [oa, setOa] = React.useState<{ url: string; result: Data | null }>({ url: '', result: null });

  React.useEffect(() => {
    let active = true;
    studio.settingsOverview().then(data => { if (active) setOverview(data); }).catch(e => { if (active) setOverviewError(errText(e)); });
    return () => { active = false; };
  }, []);

  const guard = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setStatus(`${label}: ${errText(e)}`); } finally { setBusy(false); }
  };
  const reload = React.useCallback(() => guard('Ustawienia niedostępne', async () => {
    setAdminToken(token);
    setItems(await studio.integrations());
    if (tab === 'Routing zadań') setRouting(await studio.routing());
    if (tab === 'Limity i koszty') { const l = await studio.limits(); setLimits(l); setPricesText(JSON.stringify(l.prices || {}, null, 2)); }
    if (tab === 'Dziennik zmian') setAudit(await studio.audit());
    if (tab === 'Źródła zdjęć') setPhotoSources(await studio.photoSources() as unknown as Data[]);
    setStatus('');
  }), [token, tab]);
  React.useEffect(() => { if (adminUnlocked) void reload(); }, [adminUnlocked, reload]);

  const unlock = () => guard('Nie można otworzyć edycji połączeń', async () => {
    setAdminToken(token);
    setItems(await studio.integrations());
    setAdminUnlocked(true);
    setStatus('');
  });

  const kind = KIND_FOR[tab] || 'ai_provider';
  const isCustomTab = tab === 'Własne API';
  const visible = items.filter(i => isCustomTab ? (i.provider === 'custom' || !!i.config?.request) : i.kind === kind && !(i.provider === 'custom' && kind !== 'ai_provider' && i.config?.request));

  const save = () => guard('Nie zapisano', async () => {
    let config: Data = {};
    if (form.provider === 'custom' || isCustomTab) {
      try { config = JSON.parse(form.config); } catch { throw new Error('konfiguracja nie jest poprawnym JSON'); }
    }
    if (form.base_url) config.base_url = form.base_url;
    if (form.model) config.model = form.model;
    if (form.provider === 'openai_compatible') config.type = 'openai_compatible';
    await studio.saveIntegration({ kind: isCustomTab ? (form.kind || 'photo_source') : kind, provider: isCustomTab ? 'custom' : form.provider,
      label: form.label || form.provider, config, api_key: form.api_key || undefined, enabled: true });
    setForm({ ...form, label: '', api_key: '', model: '', base_url: '' }); setStatus('Zapisano.'); await reload();
  });
  const test = (id: string) => guard('Test nieudany', async () => { const r = await studio.testIntegration(id); setTests(t => ({ ...t, [id]: r.test })); await reload(); });
  const toggle = (it: Data) => guard('Nie zmieniono', async () => { await studio.saveIntegration({ ...it, config: it.config, enabled: !it.enabled }, it.id); await reload(); });
  const remove = (id: string) => guard('Nie usunięto', async () => { await studio.deleteIntegration(id); await reload(); });
  const setModel = (it: Data, model: string) => guard('Nie zapisano modelu', async () => { await studio.saveIntegration({ ...it, config: { ...it.config, model } }, it.id); await reload(); });

  const importOA = () => guard('Import OpenAPI nieudany', async () => setOa({ ...oa, result: await studio.importOpenAPI({ url: oa.url, role: form.kind || 'photo_source' }) }));
  const useOperation = (op: Data) => {
    const cfg = { type: 'rest', auth: { type: 'none' }, request: { ...op.suggested_request, query: Object.fromEntries((op.parameters || []).filter((p: Data) => p.in === 'query').map((p: Data) => [p.name, p.name === 'q' || p.name === 'query' ? '{{ query }}' : ''])) },
      mapping: op.suggested_mapping || { items: '$[*]', fields: {} } };
    setForm({ ...form, config: JSON.stringify(cfg, null, 2), label: form.label || op.summary || op.path });
  };

  const routeOf = (task: string) => routing[task]?.config || {};
  const editRoute = (task: string, patch: Data) => setRouting(r => ({ ...r, [task]: { ...r[task], config: { ...routeOf(task), ...patch } } }));
  const saveRouting = () => guard('Routing nie zapisany', async () => {
    const body = Object.fromEntries(Object.entries(routing).map(([t, v]) => [t, v.config || {}]).filter(([, c]) => Object.keys(c as Data).length));
    setRouting(await studio.saveRouting(body)); setStatus('Routing zapisany.');
  });
  const saveLimits = () => guard('Limity nie zapisane', async () => {
    let prices: Data; try { prices = JSON.parse(pricesText); } catch { throw new Error('cennik nie jest poprawnym JSON'); }
    const l = await studio.saveLimits({ monthly_budget_usd: limits.monthly_budget_usd ? Number(limits.monthly_budget_usd) : null, rpm: limits.rpm ? Number(limits.rpm) : null, prices });
    setLimits(l); setStatus('Limity zapisane.');
  });
  const providerChoices = ['gemini', ...items.filter(i => i.kind === 'ai_provider' && i.enabled).map(i => i.id)];
  const providerName = (v: string) => v === 'gemini' ? 'Gemini' : (items.find(i => i.id === v)?.label || v);

  const overviewPanel = <>
    <header><h1 className="text-3xl font-semibold">AI i źródła</h1><p className="mt-2 text-sm text-ink-500">Tu sprawdzisz, co jest podłączone. Klucze są przechowywane na serwerze i nie są pokazywane w przeglądarce.</p></header>
    {overviewError && <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">Nie udało się odczytać stanu połączeń: {overviewError}</p>}
    {!overview && !overviewError && <p className="text-sm text-ink-500">Sprawdzam połączenia…</p>}
    {overview && <>
      <section className="rounded-xl border bg-white p-5 space-y-3">
        <h2 className="text-lg font-semibold">Podłączone modele i źródła</h2>
        {overview.integrations.length ? <ul className="grid gap-3 md:grid-cols-2">{overview.integrations.map((item, index) => <li key={`${item.provider}-${index}`} className="rounded-lg border p-3 flex items-center justify-between gap-3"><span><strong className="block">{item.label}</strong><span className="text-xs text-ink-500">{item.kind === 'ai_provider' ? 'Model AI' : 'Źródło danych'}</span></span><Status s={item.enabled && item.configured ? 'ready' : 'unconfigured'} /></li>)}</ul> : <p className="text-sm text-ink-500">Nie dodano jeszcze żadnego modelu ani źródła.</p>}
      </section>
      <section className="rounded-xl border bg-white p-5 space-y-3">
        <h2 className="text-lg font-semibold">Do czego służy AI</h2>
        <p className="text-sm text-ink-500">Gemini może obsługiwać także ocenę wyglądu strony, jeśli zadanie „Krytyk wizualny” ma stan „Gotowe”. Stan oznacza dostępny klucz i przypisany model; wynik konkretnej oceny zobaczysz przy wygenerowanej stronie.</p>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{Object.entries(overview.tasks).map(([task, route]) => <div key={task} className="rounded-lg border p-3 flex justify-between gap-2 text-sm"><div><strong>{TASK_LABEL[task] || task}</strong><p className="text-xs text-ink-500">{route.provider || '—'} · {route.model || 'bez modelu'}</p></div><Status s={route.status} /></div>)}</div>
      </section>
    </>}
  </>;

  if (!adminUnlocked) return <div className="p-6 max-w-7xl mx-auto space-y-6">{overviewPanel}
    <section className="rounded-xl border bg-white p-5">
      <button type="button" className="text-sm font-semibold text-editorial-crimson" onClick={() => setAdminOpen(!adminOpen)} aria-expanded={adminOpen}>Zmień połączenia i klucze {adminOpen ? '−' : '+'}</button>
      {adminOpen && <div className="mt-4 max-w-xl space-y-3"><p className="text-sm text-ink-500">Aby zmienić modele AI, klucze i źródła, wpisz hasło ustawień. Jest to osobne hasło do zmian na serwerze; nie wpisuj tu klucza Gemini. Do tworzenia gazety ten krok nie jest potrzebny.</p><label className="block text-sm">Hasło ustawień AI<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} className="block border rounded p-2 mt-1 w-full" /></label><button disabled={busy || !token} onClick={() => void unlock()} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Otwórz edycję połączeń</button>{status && <p role="alert" className="text-sm text-red-700">{status}</p>}</div>}
    </section>
  </div>;

  return <div className="p-6 max-w-7xl mx-auto space-y-5">
    {overviewPanel}
    <div className="flex items-center justify-between"><h2 className="text-xl font-semibold">Połączenia i klucze</h2><button onClick={() => { setAdminUnlocked(false); setAdminToken(''); setToken(''); }} className="text-sm underline">Zamknij</button></div>
    {status && <p className="rounded-lg border p-3 text-sm bg-white" role="status">{status}</p>}
    <nav className="flex flex-wrap gap-2">{TABS.map(name => <button key={name} onClick={() => setTab(name)} className={`px-3 py-2 rounded-lg text-sm border ${tab === name ? 'bg-blue-50 text-editorial-crimson border-editorial-crimson' : 'border-ink-800'}`}>{name}</button>)}</nav>

    {tab === 'Fonty' && <FontLibrary />}

    {tab === 'Źródła zdjęć' && photoSources && <section className="rounded-xl border bg-white p-4 text-sm"><h2 className="font-semibold mb-2">Wbudowane źródła</h2>
      <ul className="grid md:grid-cols-3 gap-2">{(photoSources as Data[]).map((v, i) => <li key={i} className="border rounded p-2 flex justify-between gap-2" title={v.reason || ''}><span>{v.provider}</span><Status s={v.status} /></li>)}</ul>
      <p className="text-xs text-ink-500 mt-2">Wikimedia i Openverse działają bez klucza. Unsplash, Pexels i Pixabay wymagają klucza dodanego poniżej. Agencje (PAP, Reuters, AP) podłączasz jako Własne API po podpisaniu umowy.</p></section>}

    {(KIND_FOR[tab] || isCustomTab) && <section className="rounded-xl border bg-white p-5 space-y-3">
      <h2 className="font-semibold">{isCustomTab ? 'Dodaj własne API (REST, GraphQL, RSS)' : 'Dodaj integrację'}</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        {isCustomTab ? <label>Rola<select className="block w-full border rounded p-2" value={form.kind || 'photo_source'} onChange={e => setForm({ ...form, kind: e.target.value })}>
          {['photo_source', 'text_source', 'agency', 'fact_source', 'ai_provider', 'storage', 'export_target'].map(k => <option key={k}>{k}</option>)}</select></label>
          : <label>Dostawca<select className="block w-full border rounded p-2" value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })}>{(PROVIDERS[kind] || ['custom']).map(p => <option key={p}>{p}</option>)}</select></label>}
        <label>Nazwa<input className="block w-full border rounded p-2" value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} /></label>
        {kind === 'ai_provider' && !isCustomTab && <><label>Adres usługi (opcjonalnie)<input className="block w-full border rounded p-2" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} placeholder="https://…/v1" /></label>
          <label>Model<input className="block w-full border rounded p-2" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="po teście wybierzesz z listy" /></label></>}
        <label className="md:col-span-2">Klucz API / sekret<input className="block w-full border rounded p-2" type="password" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} autoComplete="off" /></label>
        {(isCustomTab || form.provider === 'custom') && <>
          <div className="md:col-span-2 flex gap-2"><input className="flex-1 border rounded p-2" placeholder="URL specyfikacji OpenAPI (opcjonalnie)" value={oa.url} onChange={e => setOa({ ...oa, url: e.target.value })} />
            <button disabled={busy || !oa.url} onClick={() => void importOA()} className="border rounded px-3 disabled:opacity-50">Importuj OpenAPI</button></div>
          {oa.result?.operations && <ul className="md:col-span-2 max-h-48 overflow-auto border rounded text-xs divide-y">{oa.result.operations.map((op: Data, i: number) =>
            <li key={i} className="p-2 flex justify-between gap-2"><span><b>{op.method?.toUpperCase()}</b> {op.path} — {op.summary}</span><button className="underline" onClick={() => useOperation(op)}>użyj</button></li>)}</ul>}
          <label className="md:col-span-2">Konfiguracja (JSON: auth none/header/query/bearer/basic/oauth2_cc, request z szablonami Jinja, mapping JSONPath/XPath)
            <textarea className="block w-full border rounded p-2 font-mono text-xs" rows={14} value={form.config} onChange={e => setForm({ ...form, config: e.target.value })} /></label></>}
      </div>
      <button onClick={() => void save()} disabled={busy} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Zapisz</button>
    </section>}

    {(KIND_FOR[tab] || isCustomTab) && <section className="grid gap-3">{visible.map(it => { const t = tests[it.id]; return <article key={it.id} className="rounded-xl border bg-white p-4 space-y-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h3 className="font-semibold">{it.label} <Status s={it.status} /></h3>
          <p className="text-xs text-ink-500">{it.kind} · {it.provider}{it.config?.model ? ` · model ${it.config.model}` : ''} · {it.enabled ? 'włączone' : 'wyłączone'} · sekret: {it.secret_source || 'brak'}{it.config?.api_key_mask ? ` (${it.config.api_key_mask})` : ''}{it.last_test_at ? ` · test ${new Date(it.last_test_at).toLocaleString('pl-PL')}` : ''}</p></div>
        <div className="flex gap-2"><button disabled={busy} onClick={() => void test(it.id)} className="px-3 py-1.5 border rounded">Testuj</button>
          <button disabled={busy} onClick={() => void toggle(it)} className="px-3 py-1.5 border rounded">{it.enabled ? 'Wyłącz' : 'Włącz'}</button>
          <button disabled={busy} onClick={() => void remove(it.id)} className="px-3 py-1.5 border rounded text-red-700">Usuń</button></div>
      </div>
      {t && <div className="text-xs border-t pt-2 space-y-1"><div>Wynik: <Status s={t.status} /> {t.reason} {t.elapsed_ms != null && `· ${t.elapsed_ms} ms`}</div>
        {t.models?.length > 0 && <label className="block">Model: <select className="border rounded p-1" value={it.config?.model || ''} onChange={e => void setModel(it, e.target.value)}><option value="">—</option>{t.models.map((m: string) => <option key={m}>{m}</option>)}</select></label>}
        {t.probe && <div>Próba wywołania: {JSON.stringify(t.probe.response)} · tokeny {t.probe.input_tokens}/{t.probe.output_tokens}</div>}
        {t.items && <details><summary>Zmapowane rekordy ({t.count})</summary><pre className="whitespace-pre-wrap">{JSON.stringify(t.items, null, 2)}</pre></details>}
        {t.mapping_errors?.length > 0 && <div className="text-amber-700">Błędy mapowania: {t.mapping_errors.map((m: Data) => `${m.field}: ${m.error}`).join('; ')}</div>}
        {t.raw_sample && <details><summary>Surowa odpowiedź</summary><pre className="whitespace-pre-wrap max-h-64 overflow-auto">{t.raw_sample}</pre></details>}
      </div>}
    </article>; })}{visible.length === 0 && <p className="text-sm text-ink-500">Brak dodatkowych połączeń w tej sekcji. Stan modeli sprawdzisz u góry strony.</p>}</section>}

    {tab === 'Routing zadań' && <section className="rounded-xl border bg-white p-4 space-y-3 text-sm">
      <p className="text-xs text-ink-500">Każde zadanie ma dostawcę, model i łańcuch zapasowy (gdy pierwszy nie odpowie lub brak klucza). Puste pole = domyślny model Gemini.</p>
      <table className="w-full text-xs"><thead><tr className="text-left"><th>Zadanie</th><th>Dostawca</th><th>Model</th><th>Zapasowe (provider:model, po przecinku)</th><th>Temp.</th><th>Teraz</th></tr></thead>
        <tbody>{Object.entries(routing).map(([task, v]) => { const c = routeOf(task); return <tr key={task} className="border-t align-top">
          <td className="py-1.5 pr-2">{TASK_LABEL[task] || task}</td>
          <td><select className="border rounded p-1" value={c.provider || 'gemini'} onChange={e => editRoute(task, { provider: e.target.value })}>{providerChoices.map(p => <option key={p} value={p}>{providerName(p)}</option>)}</select></td>
          <td><input className="border rounded p-1 w-44" placeholder={v.default_model} value={c.model || ''} onChange={e => editRoute(task, { model: e.target.value || undefined })} /></td>
          <td><input className="border rounded p-1 w-56" value={(c.fallback || []).join(', ')} onChange={e => editRoute(task, { fallback: e.target.value.split(',').map((x: string) => x.trim()).filter(Boolean) })} /></td>
          <td><input type="number" step={0.1} min={0} max={2} className="border rounded p-1 w-16" value={c.temperature ?? ''} onChange={e => editRoute(task, { temperature: e.target.value === '' ? undefined : Number(e.target.value) })} /></td>
          <td><Status s={v.status} /> {(v.chain || []).map((r: Data) => `${r.provider}:${r.model || ''}`).join(' → ')}</td></tr>; })}</tbody></table>
      <button disabled={busy} onClick={() => void saveRouting()} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Zapisz routing</button>
    </section>}

    {tab === 'Limity i koszty' && <section className="rounded-xl border bg-white p-4 space-y-3 text-sm max-w-3xl">
      <p>Wydane w tym miesiącu: <b>{limits.month_spend_usd != null ? `$${Number(limits.month_spend_usd).toFixed(4)}` : '—'}</b>{limits.price_table_complete === false && <span className="text-amber-700"> · cennik niepełny — część wywołań nie jest wyceniona</span>}</p>
      <label className="block">Miesięczny budżet (USD)<input type="number" className="block border rounded p-2" value={limits.monthly_budget_usd ?? ''} onChange={e => setLimits({ ...limits, monthly_budget_usd: e.target.value })} /></label>
      <label className="block">Limit zapytań na minutę<input type="number" className="block border rounded p-2" value={limits.rpm ?? ''} onChange={e => setLimits({ ...limits, rpm: e.target.value })} /></label>
      <label className="block">Cennik (USD za 1M tokenów, wpisz z cennika dostawcy): {'{"gemini-3.8-flash": {"input": 0.3, "output": 2.5}}'}
        <textarea rows={8} className="block w-full border rounded p-2 font-mono text-xs" value={pricesText} onChange={e => setPricesText(e.target.value)} /></label>
      <button disabled={busy} onClick={() => void saveLimits()} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Zapisz limity</button>
    </section>}

    {tab === 'Dziennik zmian' && <section className="rounded-xl border bg-white p-4 text-xs"><table className="w-full"><thead><tr className="text-left"><th>Czas</th><th>Obiekt</th><th>Akcja</th><th>Szczegóły</th></tr></thead>
      <tbody>{audit.map((a, i) => <tr key={i} className="border-t"><td className="py-1">{a.created_at ? new Date(a.created_at).toLocaleString('pl-PL') : ''}</td><td>{a.integration_id}</td><td>{a.action}</td><td className="font-mono">{JSON.stringify(a.metadata || {})}</td></tr>)}</tbody></table>
      {audit.length === 0 && <p>Brak wpisów.</p>}</section>}
  </div>;
};
