"""Fill the font library.

  python3 scripts/install_fonts.py --google            # default Google Fonts (OFL, Polish)
  python3 scripts/install_fonts.py --google "Lora" "Oswald"
  python3 scripts/install_fonts.py --mac               # every font on this Mac (except fsType Restricted)
  python3 scripts/install_fonts.py --dir /path/to/fonts
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.engine import fonts  # noqa: E402

MAC_DIRS = [Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]


def ingest_dir(root: Path, source: str) -> None:
    added = rejected = dup = failed = 0
    done_log = fonts.FONT_DIR / ".ingested_files.txt"  # resumable: skip files already processed
    done = set(done_log.read_text(encoding="utf-8").splitlines()) if done_log.exists() else set()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in fonts.FONT_EXT | {".dfont"}):
        key = f"{path.name}|{path.stat().st_size}|{int(path.stat().st_mtime)}"
        if key in done:
            dup += 1
            continue
        if path.stat().st_size == 0:  # cloud placeholder / empty file
            failed += 1
            print(f"pominięty {path.name}: pusty plik (niepobrany z chmury?)")
            continue
        import signal
        def _too_slow(*_):
            raise TimeoutError("analiza > 45 s (zwykle wielka kolekcja CJK) — pominięty")
        signal.signal(signal.SIGALRM, _too_slow)
        signal.alarm(45)
        try:
            for rec in fonts.ingest_path(path, source=source):
                st = rec.get("status")
                added += st == "added"; dup += st == "duplicate"; rejected += st == "rejected"
                if st in {"added", "rejected"}:
                    print(f"{st:9s} {rec.get('family')} {rec.get('subfamily')}  PL={rec.get('polish')} {''.join(rec.get('missing_chars') or [])}  {rec.get('embedding')}")
            with done_log.open("a", encoding="utf-8") as fh:
                fh.write(key + "\n")
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                with done_log.open("a", encoding="utf-8") as fh:
                    fh.write(key + "\n")
            failed += 1
            print(f"pominięty {path.name}: {exc}")
        finally:
            signal.alarm(0)
    print(f"{root}: dodane {added}, duplikaty {dup}, odrzucone (Restricted) {rejected}, nieobsługiwane {failed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--google", nargs="*")
    ap.add_argument("--mac", action="store_true")
    ap.add_argument("--dir")
    a = ap.parse_args()
    if a.google is not None:
        for fam in (a.google or fonts.DEFAULT_GOOGLE):
            try:
                res = fonts.install_google_font(fam, weights=(400, 700), italics=True)
                print(fam, [f"{r.get('subfamily')}:{r.get('status')}" for r in res])
            except Exception as exc:
                print(fam, "błąd:", exc)
    if a.mac:
        for d in MAC_DIRS:
            if d.exists():
                ingest_dir(d, "mac_system" if str(d).startswith("/System") else "mac_user")
    if a.dir:
        ingest_dir(Path(a.dir).expanduser(), "upload")
