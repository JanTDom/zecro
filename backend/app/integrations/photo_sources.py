"""Tor A — licensed photo search adapters.

Built-in: Openverse and Wikimedia Commons (no key), Unsplash / Pexels / Pixabay
(key stored in the integrations panel).  Agencies (PAP, Reuters, Getty, AP …)
are listed as ``unconfigured`` until a contract-specific custom API is added
through the universal connector.  Every result is a normalised
``photo_source`` record with licence and credit; nothing is invented.
"""
from __future__ import annotations
import html, re
from typing import Any, Callable, Optional

from ..models.database import db
from ..ai.secrets_store import decrypt
from .connector import execute

UA = {"User-Agent": "Zecro/1.0 (editorial layout engine; contact: redakcja@zecro.pl)"}
AGENCIES = ["getty", "reuters", "ap", "pap", "east_news", "forum", "agencja_gazeta", "adobe_stock", "shutterstock"]


def _strip_html(value: Optional[str]) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def openverse(query: str, limit: int = 10, **_: Any) -> list[dict]:
    import requests
    r = requests.get("https://api.openverse.org/v1/images/", params={"q": query, "page_size": min(limit, 20), "mature": "false"}, headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        out.append({"provider": "openverse", "url": it.get("url"), "thumb_url": it.get("thumbnail"), "title": it.get("title"),
                    "rights_owner": it.get("creator"), "license": f"{it.get('license', '').upper()} {it.get('license_version') or ''}".strip(),
                    "license_url": it.get("license_url"), "width_px": it.get("width"), "height_px": it.get("height"),
                    "source_page": it.get("foreign_landing_url"), "credit_line": f"Fot. {it.get('creator') or 'autor nieznany'} / {it.get('source') or 'Openverse'}, {it.get('license', '').upper()}"})
    return out


def wikimedia(query: str, limit: int = 10, **_: Any) -> list[dict]:
    import requests
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=20, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": min(limit, 20), "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 640})
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    out = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime", "")).startswith("image/") or "svg" in str(info.get("mime")):
            continue
        meta = info.get("extmetadata") or {}
        artist = _strip_html((meta.get("Artist") or {}).get("value"))
        lic = (meta.get("LicenseShortName") or {}).get("value")
        out.append({"provider": "wikimedia", "url": info.get("url"), "thumb_url": info.get("thumburl"), "title": page.get("title", "").replace("File:", ""),
                    "rights_owner": artist, "license": lic, "license_url": (meta.get("LicenseUrl") or {}).get("value"),
                    "width_px": info.get("width"), "height_px": info.get("height"), "source_page": info.get("descriptionurl"),
                    "captured_at": (meta.get("DateTimeOriginal") or {}).get("value"),
                    "description": _strip_html((meta.get("ImageDescription") or {}).get("value"))[:400],
                    "credit_line": f"Fot. {artist or 'autor nieznany'} / Wikimedia Commons, {lic or 'licencja do sprawdzenia'}"})
    return out


def _keyed(provider: str) -> Optional[str]:
    for item in db.list_integrations():
        if item.get("provider") == provider and item.get("enabled") and item.get("secret_ref"):
            return decrypt(item["secret_ref"])
    return None


def unsplash(query: str, limit: int = 10, **_: Any) -> list[dict]:
    import requests
    key = _keyed("unsplash")
    if not key:
        raise LookupError("unconfigured")
    r = requests.get("https://api.unsplash.com/search/photos", params={"query": query, "per_page": min(limit, 30)}, headers={**UA, "Authorization": f"Client-ID {key}"}, timeout=20)
    r.raise_for_status()
    return [{"provider": "unsplash", "url": it["urls"]["full"], "thumb_url": it["urls"]["small"], "title": it.get("alt_description"),
             "rights_owner": it["user"]["name"], "license": "Unsplash License", "license_url": "https://unsplash.com/license",
             "width_px": it.get("width"), "height_px": it.get("height"), "source_page": it["links"]["html"],
             "credit_line": f"Fot. {it['user']['name']} / Unsplash"} for it in r.json().get("results", [])]


def pexels(query: str, limit: int = 10, **_: Any) -> list[dict]:
    import requests
    key = _keyed("pexels")
    if not key:
        raise LookupError("unconfigured")
    r = requests.get("https://api.pexels.com/v1/search", params={"query": query, "per_page": min(limit, 40)}, headers={**UA, "Authorization": key}, timeout=20)
    r.raise_for_status()
    return [{"provider": "pexels", "url": it["src"]["original"], "thumb_url": it["src"]["medium"], "title": it.get("alt"),
             "rights_owner": it.get("photographer"), "license": "Pexels License", "license_url": "https://www.pexels.com/license/",
             "width_px": it.get("width"), "height_px": it.get("height"), "source_page": it.get("url"),
             "credit_line": f"Fot. {it.get('photographer')} / Pexels"} for it in r.json().get("photos", [])]


def pixabay(query: str, limit: int = 10, **_: Any) -> list[dict]:
    import requests
    key = _keyed("pixabay")
    if not key:
        raise LookupError("unconfigured")
    r = requests.get("https://pixabay.com/api/", params={"key": key, "q": query, "per_page": max(3, min(limit, 50)), "image_type": "photo", "lang": "pl"}, headers=UA, timeout=20)
    r.raise_for_status()
    return [{"provider": "pixabay", "url": it.get("largeImageURL"), "thumb_url": it.get("previewURL"), "title": it.get("tags"),
             "rights_owner": it.get("user"), "license": "Pixabay Content License", "license_url": "https://pixabay.com/service/license-summary/",
             "width_px": it.get("imageWidth"), "height_px": it.get("imageHeight"), "source_page": it.get("pageURL"),
             "credit_line": f"Fot. {it.get('user')} / Pixabay"} for it in r.json().get("hits", [])]


BUILTIN: dict[str, Callable[..., list[dict]]] = {"openverse": openverse, "wikimedia": wikimedia, "unsplash": unsplash, "pexels": pexels, "pixabay": pixabay}


def source_status() -> list[dict]:
    rows = [{"provider": p, "status": "ready" if p in {"openverse", "wikimedia"} or _keyed(p) else "unconfigured"} for p in BUILTIN]
    rows += [{"provider": p, "status": "unconfigured", "reason": "wymaga umowy i własnego API (konektor uniwersalny)"} for p in AGENCIES]
    for item in db.list_integrations():
        if item.get("kind") in {"photo_source", "agency"} and (item.get("config_json") or {}).get("request"):
            rows.append({"provider": item.get("label") or item["id"], "integration_id": item["id"], "status": item.get("status") or "configured"})
    return rows


def search(queries: list[str], *, providers: Optional[list[str]] = None, limit: int = 8, project_id: Optional[str] = None) -> dict[str, Any]:
    """Search all enabled sources; returns de-duplicated results + per-source status."""
    providers = providers or ["wikimedia", "openverse", "unsplash", "pexels", "pixabay", "custom"]
    results, status = [], []
    seen: set[str] = set()
    for query in [q for q in queries if q][:4]:
        for provider in providers:
            try:
                if provider == "custom":
                    rows = []
                    for item in db.list_integrations(project_id=project_id):
                        cfg = item.get("config_json") or {}
                        if item.get("enabled") and cfg.get("role") == "photo_source" and cfg.get("request"):
                            got = execute(item, {"query": query, "limit": limit})
                            rows += [{**r, "provider": item.get("label") or "custom", "integration_id": item["id"]} for r in got["items"]]
                else:
                    rows = BUILTIN[provider](query, limit)
                status.append({"provider": provider, "query": query, "status": "ok", "count": len(rows)})
            except LookupError:
                status.append({"provider": provider, "query": query, "status": "unconfigured"})
                continue
            except Exception as exc:
                status.append({"provider": provider, "query": query, "status": "error", "reason": str(exc)[:200]})
                continue
            for row in rows:
                if row.get("url") and row["url"] not in seen:
                    seen.add(row["url"])
                    results.append({**row, "query": query})
    return {"results": results, "sources": status}
