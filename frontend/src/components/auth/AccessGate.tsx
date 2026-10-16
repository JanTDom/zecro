import React from 'react';
import { apiUrl } from '../../api/client';

interface AccessGateProps {
  children: React.ReactNode;
}

export function AccessGate({ children }: AccessGateProps) {
  const [unlocked, setUnlocked] = React.useState(false);
  const [checkingSession, setCheckingSession] = React.useState(true);
  const [password, setPassword] = React.useState('');
  const [isChecking, setIsChecking] = React.useState(false);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let active = true;
    fetch(apiUrl('/auth/session'), { credentials: 'include' })
      .then(async response => {
        const result = await response.json().catch(() => null);
        if (active) setUnlocked(response.ok && result?.authenticated === true);
      })
      .catch(() => { if (active) setError('Nie można połączyć się z serwerem. Spróbuj ponownie za chwilę.'); })
      .finally(() => { if (active) setCheckingSession(false); });
    return () => { active = false; };
  }, []);

  React.useEffect(() => {
    const expire = (event: Event) => {
      setUnlocked(false);
      setError(event instanceof CustomEvent && event.detail === 'logout' ? 'Wylogowano.' : 'Sesja wygasła. Wpisz hasło ponownie.');
    };
    window.addEventListener('zecro-session-expired', expire);
    return () => window.removeEventListener('zecro-session-expired', expire);
  }, []);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isChecking) return;

    setIsChecking(true);
    setError('');
    try {
      const response = await fetch(apiUrl('/auth/login'), {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(typeof body?.detail === 'string' ? body.detail : 'Nie udało się zweryfikować hasła.');
        setPassword('');
        return;
      }
      setUnlocked(true);
      setPassword('');
    } catch {
      setError('Nie udało się połączyć z serwerem. Odśwież stronę i spróbuj ponownie.');
    } finally {
      setIsChecking(false);
    }
  };

  if (unlocked) return <>{children}</>;

  if (checkingSession) return <main className="access-gate" aria-live="polite"><p>Sprawdzam dostęp do studia…</p></main>;

  return (
    <main className="access-gate" aria-labelledby="access-gate-title">
      <div className="access-gate__glow access-gate__glow--top" />
      <div className="access-gate__glow access-gate__glow--bottom" />
      <section className="access-gate__panel">
        <div className="access-gate__logo-lockup">
          <img
            className="access-gate__logo"
            src="/zecro-logo.png"
            alt="Zecro — tworzenie gazet"
          />
        </div>
        <div className="access-gate__eyebrow">Podgląd prywatny · zecro.pl</div>
        <h1 id="access-gate-title">Studio tworzenia gazet</h1>
        <p className="access-gate__intro">
          Wpisz hasło dostępu, aby otworzyć studio.
        </p>
        <form className="access-gate__form" onSubmit={onSubmit}>
          <input type="text" name="username" autoComplete="username" value="zecro" readOnly tabIndex={-1} aria-hidden="true" style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none' }} />
          <label htmlFor="access-password">Hasło dostępu</label>
          <div className="access-gate__input-wrap">
            <input
              id="access-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••••"
              autoFocus
              required
            />
            <span className="access-gate__input-status" aria-hidden="true">↗</span>
          </div>
          <button type="submit" disabled={isChecking || password.length === 0}>
            {isChecking ? 'Weryfikuję…' : 'Otwórz studio'}
            <span aria-hidden="true">→</span>
          </button>
          <p className="access-gate__hint" aria-live="polite">
            {error || 'Dostęp jest ważny do zamknięcia tej sesji przeglądarki.'}
          </p>
        </form>
        <div className="access-gate__footer">
          <span>ZE / 01</span>
          <span>Twoja gazeta od pomysłu do wydania</span>
        </div>
      </section>
    </main>
  );
}
