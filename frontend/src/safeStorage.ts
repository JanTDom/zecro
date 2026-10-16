/** localStorage that never throws (private windows, blocked site data, embedded previews). */
export const safeStorage = {
  get(key: string): string | null {
    try { return window.localStorage.getItem(key); } catch { return null; }
  },
  set(key: string, value: string): void {
    try { window.localStorage.setItem(key, value); } catch { /* per-viewer convenience only */ }
  },
};
