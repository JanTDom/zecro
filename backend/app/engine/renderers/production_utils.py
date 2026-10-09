"""Local assets and optional runtime support shared by production exporters."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[4]


def optional_package(name: str):
    """Import a backend package, including Codex's bundled desktop runtime."""
    try:
        return importlib.import_module(name)
    except ImportError:
        paths = []
        configured = os.environ.get("ZECRO_PYTHON_PACKAGES")
        if configured:
            paths.append(Path(configured))
        bundle = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python"
        paths.extend(bundle.glob("lib/python*/site-packages"))
        for path in paths:
            if path.is_dir() and str(path) not in sys.path:
                sys.path.append(str(path))
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            raise RuntimeError(f"Production export requires the '{name}' package. Install backend dependencies.") from exc


def local_asset(value: str | None) -> Path | None:
    """Resolve local uploads and file paths; remote URLs remain explicit links."""
    if not value:
        return None
    if value.startswith("file:"):
        path = Path(unquote(urlparse(value).path))
    elif value.startswith("/static/uploads/"):
        path = ROOT / "backend/data/uploads" / Path(value).name
    elif value.startswith("/static/exports/"):
        path = ROOT / "backend/data/exports" / Path(value).name
    elif value.startswith(("http:", "https:", "inline:", "data:")):
        return None
    else:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = ROOT / path
    return path.resolve() if path.is_file() else None


def cmyk_from_hex(value: str | None) -> tuple[float, float, float, float]:
    value = (value or "#000000").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (0, 0, 0, 1)
    k = 1 - max(r, g, b)
    if k > .999:
        return (0, 0, 0, 1)
    return ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)
