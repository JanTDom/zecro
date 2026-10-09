import React from 'react';

const PBKDF2_ITERATIONS = 210_000;
const PASSWORD_SALT = 'emVjcm8tcHJpdmF0ZS1wcmV2aWV3LTIwMjY=';
const PASSWORD_DIGEST = 'M6B/U/U/v+nKe9YhkgGuMsVY906vLkpYFJHNptdyR/4=';
const ACCESS_STORAGE_KEY = 'zecro-private-preview-access';

function encodeBase64(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)));
}
async function deriveDigest(password: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: Uint8Array.from(atob(PASSWORD_SALT), (character) => character.charCodeAt(0)),
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    key,
    256,
  );
  return encodeBase64(bits);
}

function hasAccess(): boolean {
  try {
    return sessionStorage.getItem(ACCESS_STORAGE_KEY) === 'granted';
  } catch {
    return false;
  }
}

interface AccessGateProps {
  children: React.ReactNode;
}

export function AccessGate({ children }: AccessGateProps) {
  const [unlocked, setUnlocked] = React.useState(hasAccess);
  const [password, setPassword] = React.useState('');
  const [isChecking, setIsChecking] = React.useState(false);
  const [error, setError] = React.useState('');

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isChecking) return;

    setIsChecking(true);
    setError('');
    try {
      const digest = await deriveDigest(password);
      if (digest !== PASSWORD_DIGEST) {
        setError('Hasło nie pasuje. Spróbuj ponownie.');
        setPassword('');
        return;
      }
      sessionStorage.setItem(ACCESS_STORAGE_KEY, 'granted');
      setUnlocked(true);
      setPassword('');
    } catch {
      setError('Nie udało się zweryfikować dostępu. Odśwież stronę i spróbuj ponownie.');
    } finally {
      setIsChecking(false);
    }
  };

  if (unlocked) return <>{children}</>;

  return (
    <main className="access-gate" aria-labelledby="access-gate-title">
      <div className="access-gate__glow access-gate__glow--top" />
      <div className="access-gate__glow access-gate__glow--bottom" />
      <section className="access-gate__panel">
        <div className="access-gate__logo-lockup">
          <img
            className="access-gate__logo"
            src="/zecro-logo.png"
            alt="Zecro Generative Layout Engine"
          />
        </div>
        <div className="access-gate__eyebrow">Private preview · zecro.pl</div>
        <h1 id="access-gate-title">Generative Layout Engine</h1>
        <p className="access-gate__intro">
          Studio jest dostępne w zamkniętym podglądzie. Wprowadź hasło, aby otworzyć workspace.
        </p>
        <form className="access-gate__form" onSubmit={onSubmit}>
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
            {isChecking ? 'Weryfikuję…' : 'Otwórz workspace'}
            <span aria-hidden="true">→</span>
          </button>
          <p className="access-gate__hint" aria-live="polite">
            {error || 'Dostęp jest ważny do zamknięcia tej sesji przeglądarki.'}
          </p>
        </form>
        <div className="access-gate__footer">
          <span>ZE / 01</span>
          <span>Editorial intelligence system</span>
        </div>
      </section>
    </main>
  );
}
