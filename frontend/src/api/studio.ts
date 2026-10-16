// Thin typed client for the AI studio, page planning, fonts, logo and
// integration settings endpoints.  Errors surface the server's reason.
import { apiUrl } from './client';

export type Data = Record<string, any>;
let adminToken = '';
export const setAdminToken = (token: string) => { adminToken = token; };

type CallInit = Omit<RequestInit, 'body'> & { body?: any };
export async function call<T = Data>(path: string, init: CallInit = {}): Promise<T> {
  const isForm = typeof FormData !== 'undefined' && init.body instanceof FormData;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> || {}) };
  if (adminToken) headers['X-Zecro-Admin-Token'] = adminToken;
  let body = init.body;
  if (body !== undefined && !isForm && typeof body !== 'string') { body = JSON.stringify(body); headers['Content-Type'] = 'application/json'; }
  let response: Response;
  try { response = await fetch(apiUrl(path), { ...init, headers, body, credentials: 'include' }); }
  catch { throw new Error('Usługa ZECRO API jest niedostępna.'); }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('zecro-session-expired'));
    const d = data?.detail;
    throw new Error(typeof d === 'string' ? d : d?.reason || (Array.isArray(d) ? d.map((x: Data) => x.msg).join('; ') : `Błąd API ${response.status}`));
  }
  return data as T;
}
const post = <T = Data>(path: string, body?: any) => call<T>(path, { method: 'POST', body: body ?? {} });

export type StoryPayload = { id: string; kicker?: string; headline: string; lead?: string; body: string; byline?: string;
  rank?: string; span_cols?: number | null; pin_zone?: string | null; teaser_only?: boolean; continue_to_page?: number | null;
  importance?: number; images?: Data[] };

export const studio = {
  // page plan
  plan: (projectId: string, stories: StoryPayload[], page_zone = 'front_page') => post(`/projects/${projectId}/page-plan`, { stories, page_zone }),
  proposePlans: (projectId: string, stories: StoryPayload[], page_zone = 'front_page') => post(`/projects/${projectId}/page-plan/propose`, { stories, page_zone }),
  // copy
  fit: (story: StoryPayload, role: string, frame: Data, opts: Data = {}) => post('/ai/copy/fit', { story, role, frame, ...opts }),
  headlines: (story: StoryPayload, width_mm: number, font: string, size_pt: number, max_lines = 2, n = 5) =>
    post('/ai/headlines', { story, width_mm, font, size_pt, max_lines, n }),
  writeFromBrief: (brief: Data, sources: Data[], rank: string, target_words: number) => post('/ai/write-from-brief', { brief, sources, rank, target_words }),
  translate: (story: StoryPayload, target_language: string) => post('/ai/translate', { story, target_language }),
  teaser: (story: StoryPayload, page_number: number) => post('/ai/teaser', { story, page_number }),
  pullquotes: (story: StoryPayload) => post('/ai/pullquotes', { story }),
  infobox: (story: StoryPayload) => post('/ai/infobox', { story }),
  factGuard: (output: string, source: string) => post('/ai/fact-guard', { output, source }),
  // photos
  photoSources: () => call('/photos/sources'),
  proposePhotos: (story: StoryPayload, project_id?: string, limit = 6) => post('/photos/propose', { story, project_id, limit }),
  acceptPhoto: (candidate: Data, story?: StoryPayload, project_id?: string) => post('/photos/accept', { candidate, story, project_id }),
  illustrate: (story: StoryPayload, style: string, aspect_ratio = '4:3', n = 2) => post('/photos/illustrate', { story, style, aspect_ratio, n }),
  maskQA: (original: string, mask: string) => post('/assets/mask-qa', { original, mask }),
  critique: (candidateId: string) => post(`/candidates/${candidateId}/critique`),
  // fonts
  fonts: (polish_only = false) => call<Data[]>(`/fonts?polish_only=${polish_only}`),
  googleFonts: (q: string) => call<Data[]>(`/fonts/google?q=${encodeURIComponent(q)}&limit=40`),
  installGoogle: (family: string, weights: number[], italics: boolean) => post('/fonts/google/install', { family, weights, italics }),
  uploadFonts: (files: File[]) => { const f = new FormData(); files.forEach(x => f.append('files', x)); return call<Data[]>('/fonts/upload', { method: 'POST', body: f }); },
  deleteFont: (id: string) => call(`/fonts/${id}`, { method: 'DELETE' }),
  // logo
  uploadLogo: (projectId: string, file: File) => { const f = new FormData(); f.append('file', file); return call(`/projects/${projectId}/dna/logo`, { method: 'POST', body: f }); },
  approveLogo: (projectId: string, body: Data) => post(`/projects/${projectId}/dna/logo/approve`, body),
  dna: (projectId: string) => call(`/projects/${projectId}/dna`),
  // settings
  settingsOverview: () => call<{ integrations: Data[]; tasks: Record<string, Data> }>('/settings/overview'),
  integrations: () => call<Data[]>('/settings/integrations'),
  saveIntegration: (body: Data, id?: string) => call(id ? `/settings/integrations/${id}` : '/settings/integrations', { method: id ? 'PUT' : 'POST', body }),
  deleteIntegration: (id: string) => call(`/settings/integrations/${id}`, { method: 'DELETE' }),
  testIntegration: (id: string, query = 'Warszawa') => post(`/settings/integrations/${id}/test`, { query }),
  importOpenAPI: (body: Data) => post('/settings/integrations/import-openapi', body),
  routing: () => call('/settings/routing'),
  saveRouting: (body: Data) => call('/settings/routing', { method: 'PUT', body }),
  limits: () => call('/settings/limits'),
  saveLimits: (body: Data) => call('/settings/limits', { method: 'PUT', body }),
  audit: () => call<Data[]>('/settings/audit'),
};

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
