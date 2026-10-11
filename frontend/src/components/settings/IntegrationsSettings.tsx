import React from 'react';
import { apiUrl } from '../../api/client';

const tabs = ['Modele AI', 'Routing zadań', 'Źródła zdjęć', 'Źródła tekstów', 'Własne API', 'Archiwum', 'Limity i koszty', 'Dziennik zmian'];
type Integration = { id: string; kind: string; provider: string; label: string; status: string; enabled: boolean; secret_source?: string; config?: Record<string, unknown>; last_test_at?: string };

export const IntegrationsSettings: React.FC = () => {
  const [tab, setTab] = React.useState(tabs[0]);
  const [items, setItems] = React.useState<Integration[]>([]);
  const [status, setStatus] = React.useState('Ładowanie konfiguracji…');
  const [provider, setProvider] = React.useState('gemini');
  const [kind, setKind] = React.useState('ai_provider');
  const [label, setLabel] = React.useState('');
  const [baseUrl, setBaseUrl] = React.useState('');
  const [secret, setSecret] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [adminToken, setAdminToken] = React.useState('');
  const request = async (path: string, init?: RequestInit) => {
    const response = await fetch(apiUrl(path), {...init, headers: {...(init?.headers || {}), 'X-Zecro-Admin-Token': adminToken}});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.reason || `API ${response.status}`);
    return body;
  };
  const reload = React.useCallback(async () => {
    try {
      const response = await fetch(apiUrl('/settings/integrations'), {headers: {'X-Zecro-Admin-Token': adminToken}});
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail?.reason || body.detail || `API ${response.status}`);
      setItems(body);
      setStatus(body.length ? 'Konfiguracja wczytana' : 'Brak integracji w panelu. Domyślny Gemini może działać z .env.local.');
    } catch (error) { setStatus(`Ustawienia niedostępne: ${error instanceof Error ? error.message : String(error)}`); }
  }, [adminToken]);
  React.useEffect(() => { void reload(); }, [reload]);
  const save = async () => {
    setBusy(true);
    try {
      await request('/settings/integrations', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind, provider, label: label || provider, config: baseUrl ? {base_url: baseUrl} : {}, api_key: secret || undefined}) });
      setSecret(''); setLabel(''); setBaseUrl(''); await reload();
    } catch (error) { setStatus(`Nie zapisano integracji: ${error instanceof Error ? error.message : String(error)}`); }
    finally { setBusy(false); }
  };
  const test = async (id: string) => {
    setBusy(true);
    try { const result = await request(`/settings/integrations/${id}/test`, {method:'POST'}); setStatus(`${result.label}: ${result.test?.status || result.status}${result.test?.reason ? ` — ${result.test.reason}` : ''}`); await reload(); }
    catch (error) { setStatus(`Test nieudany: ${error instanceof Error ? error.message : String(error)}`); }
    finally { setBusy(false); }
  };
  const visible = items.filter(item => tab === 'Modele AI' ? item.kind === 'ai_provider' : tab === 'Źródła zdjęć' ? item.kind === 'photo_source' : tab === 'Źródła tekstów' ? item.kind === 'text_source' : tab === 'Własne API' ? item.provider === 'custom' : true);
  return <div className="p-6 max-w-7xl mx-auto space-y-5">
    <header><h1 className="text-2xl font-semibold">AI i źródła</h1><p className="text-sm text-ink-500">Integracje, routing i stan usług. Sekrety są wysyłane tylko do serwera i nie są przechowywane w przeglądarce.</p></header>
    <label className="block text-sm">Token administratora (tylko w pamięci tej karty)<input type="password" autoComplete="off" value={adminToken} onChange={e => setAdminToken(e.target.value)} className="block border rounded p-2 mt-1 w-full max-w-md" /></label>
    <p className="rounded-lg border border-ink-800 p-3 text-sm" role="status">{status}</p>
    <div className="flex flex-wrap gap-2">{tabs.map(name => <button key={name} onClick={() => setTab(name)} className={`px-3 py-2 rounded-lg text-sm border ${tab === name ? 'bg-blue-50 text-editorial-crimson border-editorial-crimson' : 'border-ink-800'}`}>{name}</button>)}</div>
    {['Modele AI','Źródła zdjęć','Źródła tekstów','Własne API','Archiwum'].includes(tab) && <section className="rounded-xl border border-ink-800 bg-white p-5 space-y-4">
      <h2 className="font-semibold">Dodaj integrację</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="text-sm">Rodzaj<select className="block w-full border rounded p-2" value={kind} onChange={e => setKind(e.target.value)}><option value="ai_provider">Model AI</option><option value="photo_source">Źródło zdjęć</option><option value="text_source">Źródło tekstów</option><option value="agency">Agencja</option><option value="storage">Archiwum</option></select></label>
        <label className="text-sm">Dostawca<select className="block w-full border rounded p-2" value={provider} onChange={e => setProvider(e.target.value)}>{['gemini','openai','anthropic','mistral','custom','wikimedia','openverse','unsplash','pexels','pap','reuters','ap'].map(p => <option key={p}>{p}</option>)}</select></label>
        <label className="text-sm">Nazwa<input className="block w-full border rounded p-2" value={label} onChange={e => setLabel(e.target.value)} /></label>
        <label className="text-sm">Base URL<input className="block w-full border rounded p-2" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="https://…" /></label>
        <label className="text-sm md:col-span-2">Klucz API<input className="block w-full border rounded p-2" type="password" value={secret} onChange={e => setSecret(e.target.value)} autoComplete="off" /></label>
      </div><button onClick={() => void save()} disabled={busy} className="px-4 py-2 rounded bg-editorial-crimson text-white disabled:opacity-50">Zapisz integrację</button>
    </section>}
    <section className="grid gap-3">{visible.map(item => <article key={item.id} className="rounded-xl border border-ink-800 bg-white p-4 flex items-center justify-between gap-4"><div><h3 className="font-semibold">{item.label}</h3><p className="text-xs text-ink-500">{item.provider} · {item.status} · {item.enabled ? 'włączone' : 'wyłączone'} · sekret: {item.secret_source || 'brak'}{item.last_test_at ? ` · test ${item.last_test_at}` : ''}</p></div><button disabled={busy} onClick={() => void test(item.id)} className="px-3 py-2 text-sm border rounded">Testuj połączenie</button></article>)}</section>
    {visible.length === 0 && <p className="text-sm text-ink-500">Brak skonfigurowanych integracji w tej sekcji.</p>}
  </div>;
};
