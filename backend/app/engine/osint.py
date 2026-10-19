"""Small, dependency-light OSINT engine for public publisher signals.

The engine intentionally works on public RSS/Atom/HTML only.  It never claims
to know page views or CMS state: popularity and hero-slot findings are marked
as unavailable unless the public source exposes the corresponding evidence.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup


USER_AGENT = "Zecro-Live-OSINT/0.1 (+https://zecro.pl; public newsroom monitoring)"
MAX_RESPONSE_BYTES = 1_500_000
MAX_ITEMS_PER_SOURCE = 40
REQUEST_TIMEOUT_SECONDS = 10

DEFAULT_SOURCES: list[dict[str, Any]] = [
    {"id": "wroclaw-city", "label": "Wrocław.pl — urząd", "url": "https://www.wroclaw.pl/dla-mieszkanca/rss", "kind": "institution", "region": "Wrocław"},
    {"id": "policja", "label": "Policja — komunikaty", "url": "https://www.policja.pl/pol/rss/", "kind": "institution", "region": "Polska"},
    {"id": "rmf24", "label": "RMF24 — konkurencja", "url": "https://www.rmf24.pl/feed", "kind": "competitor", "region": "Polska"},
    {"id": "onet", "label": "Onet — konkurencja", "url": "https://wiadomosci.onet.pl/.feed", "kind": "competitor", "region": "Polska"},
]

STOPWORDS = {
    "i", "w", "z", "na", "do", "od", "po", "o", "a", "że", "to", "jest", "dla", "nie", "się", "oraz", "czy", "jak",
    "the", "and", "of", "to", "in", "for", "on", "a", "an", "with", "is", "at", "by", "this", "that",
}


def _clean(value: Any) -> str:
    text = BeautifulSoup(html.unescape(str(value or "")), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_text(element: ElementTree.Element, names: set[str]) -> str:
    for child in element.iter():
        if _local_name(child.tag) in names and child.text:
            return _clean(child.text)
    return ""


def _first_link(element: ElementTree.Element) -> str:
    for child in element.iter():
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href") or (child.text or "")
        if href.strip():
            return href.strip()
    return ""


def _parse_datetime(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _stem_token(token: str) -> str:
    """A deliberately conservative Polish-friendly suffix normalizer.

    This is not a linguistic lemmatizer. It only makes obvious inflections
    such as ``tramwaje``/``tramwajów`` comparable without pulling an NLP model
    into the live request path.
    """
    normalized = token.translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    for suffix in ("ami", "ach", "owie", "owi", "emu", "iem", "om", "em", "ie", "ię", "ą", "a", "y", "e", "i", "u"):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            return normalized[:-len(suffix)]
    return normalized


def _tokens(text: str) -> set[str]:
    return {
        _stem_token(token) for token in re.findall(r"[\wąćęłńóśźż]{3,}", text.lower(), flags=re.UNICODE)
        if token not in STOPWORDS and not token.isdigit()
    }


def _similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = _tokens(left), _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    jaccard = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    sequence = SequenceMatcher(None, left.lower(), right.lower()).ratio()
    return round((jaccard * 0.7) + (sequence * 0.3), 4)


def _safe_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Źródło musi być publicznym adresem http(s).")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("Adres lokalny nie może być źródłem skanu.")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        # The request layer will return a useful source-level error.
        addresses = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Źródło wskazuje na prywatny lub lokalny adres sieciowy.")
    return url


def _feed_entries(payload: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(payload)
    root_name = _local_name(root.tag)
    item_names = {"entry"} if root_name == "feed" else {"item", "entry"}
    entries: list[dict[str, Any]] = []
    for item in root.iter():
        if _local_name(item.tag) not in item_names:
            continue
        title = _first_text(item, {"title"})
        link = urljoin(source["url"], _first_link(item))
        summary = _first_text(item, {"description", "summary", "content", "encoded"})
        published = _parse_datetime(_first_text(item, {"pubdate", "published", "updated", "date"}))
        if not title or not link:
            continue
        entries.append({
            "id": hashlib.sha1(link.encode("utf-8")).hexdigest()[:12],
            "title": title,
            "url": link,
            "summary": summary[:1000],
            "published_at": published,
            "author": _first_text(item, {"author", "creator"}),
            "source_id": source["id"],
            "source_label": source["label"],
            "kind": source["kind"],
            "region": source.get("region", "Nieznany"),
        })
        if len(entries) >= MAX_ITEMS_PER_SOURCE:
            break
    return entries


def _html_entries(payload: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(payload, "html.parser")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in soup.select("article, [itemtype*='Article'], main h1, main h2, main h3"):
        heading = node.select_one("h1, h2, h3") if node.name == "article" else node
        title = _clean(heading.get_text(" ", strip=True) if heading else "")
        anchor = node.select_one("a[href]") if hasattr(node, "select_one") else None
        if not anchor or not title or len(title) < 18:
            continue
        link = urljoin(source["url"], anchor.get("href", ""))
        if link in seen or not urlparse(link).scheme:
            continue
        seen.add(link)
        parent = node.find_parent(["section", "aside", "div"])
        marker = " ".join(parent.get("class", [])) if parent else ""
        marker = f"{marker} {_clean(parent.get_text(' ', strip=True)[:180]) if parent else ''}".lower()
        is_popular = any(label in marker for label in ("popular", "najczęściej czytane", "najpopularniejsze", "trending"))
        time_node = node.select_one("time[datetime]")
        entries.append({
            "id": hashlib.sha1(link.encode("utf-8")).hexdigest()[:12],
            "title": title[:280], "url": link,
            "summary": _clean(node.get_text(" ", strip=True))[:1000],
            "published_at": _parse_datetime(time_node.get("datetime", "")) if time_node else None,
            "author": "", "source_id": source["id"], "source_label": source["label"],
            "kind": source["kind"], "region": source.get("region", "Nieznany"), "is_popular": is_popular,
        })
        if len(entries) >= MAX_ITEMS_PER_SOURCE:
            break
    return entries


def fetch_source(source: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    result = {**source, "status": "error", "items": [], "error": None, "latency_ms": 0}
    try:
        _safe_public_url(source["url"])
        response = requests.get(source["url"], timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/html;q=0.9"}, stream=True)
        response.raise_for_status()
        content = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("Odpowiedź źródła przekracza limit 1.5 MB.")
        try:
            items = _feed_entries(content, source)
            source_type = "feed"
        except (ElementTree.ParseError, ValueError):
            items = _html_entries(content, source)
            source_type = "html"
        result.update({"status": "live", "source_type": source_type, "items": items})
    except Exception as exc:  # source failures must not abort the whole scan
        result["error"] = str(exc)[:240]
    result["latency_ms"] = round((time.monotonic() - started) * 1000)
    return result


def _groups(items: Iterable[dict[str, Any]], threshold: float = 0.35) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for item in items:
        best: list[dict[str, Any]] | None = None
        best_score = 0.0
        for group in groups:
            score = max(_similarity(item["title"], existing["title"]) for existing in group)
            if score > best_score:
                best, best_score = group, score
        if best is not None and best_score >= threshold:
            best.append(item)
        else:
            groups.append([item])
    return groups


def _topic_time(item: dict[str, Any]) -> str:
    return item.get("published_at") or ""


def build_findings(source_results: list[dict[str, Any]], publisher_source_id: str | None) -> dict[str, Any]:
    live = [source for source in source_results if source["status"] == "live"]
    all_items = [item for source in live for item in source["items"]]
    blindspots: list[dict[str, Any]] = []
    copy_matches: list[dict[str, Any]] = []
    dead_heroes: list[dict[str, Any]] = []
    publisher = next((source for source in live if source["id"] == publisher_source_id), None)
    publisher_items = publisher["items"] if publisher else []

    for group in _groups(all_items):
        source_ids = {item["source_id"] for item in group}
        competitor_items = [item for item in group if item["kind"] in {"competitor", "wire", "institution"}]
        if len(source_ids) >= 2 and len(competitor_items) >= 2 and publisher_source_id and publisher_source_id not in source_ids:
            lead = max(group, key=lambda item: len(_tokens(item["title"])))
            blindspots.append({
                "id": f"blindspot-{lead['id']}", "title": lead["title"], "region": lead.get("region", "Polska"),
                "sources": [{"label": item["source_label"], "url": item["url"], "published_at": item.get("published_at")} for item in group],
                "source_count": len(source_ids), "severity": "high" if len(source_ids) >= 3 else "medium",
                "first_seen_at": min((_topic_time(item) for item in group if _topic_time(item)), default=None),
                "explanation": "Ten sam temat pojawia się w niezależnych publicznych źródłach, ale nie ma go w źródle własnym.",
            })

    if publisher and publisher_items:
        hero = publisher_items[0]
        popular = [item for item in publisher_items if item.get("is_popular")]
        if popular and hero["id"] not in {item["id"] for item in popular}:
            dead_heroes.append({
                "id": f"hero-{hero['id']}", "title": hero["title"], "url": hero["url"],
                "hero_source": publisher["label"], "popular_count": len(popular),
                "explanation": "Pierwszy publicznie wykryty materiał nie występuje w publicznym boksie popularności.",
                "evidence_level": "public_html",
            })

    if publisher_items:
        institution_items = [item for source in live if source["kind"] == "institution" for item in source["items"]]
        for article in publisher_items[:20]:
            for release in institution_items:
                score = _similarity(f"{article['title']} {article.get('summary', '')}", f"{release['title']} {release.get('summary', '')}")
                if score >= 0.52:
                    copy_matches.append({
                        "id": f"copy-{article['id']}-{release['id']}", "title": article["title"],
                        "publisher_url": article["url"], "source_url": release["url"],
                        "source_label": release["source_label"], "score": round(score * 100),
                        "explanation": "Podobieństwo tytułu i publicznego streszczenia; to sygnał do ręcznej weryfikacji, nie wyrok plagiatu.",
                    })
                    break

    timeline = sorted([
        {"id": item["id"], "time": item.get("published_at"), "title": item["title"], "source": item["source_label"], "region": item.get("region", "Polska"), "kind": item["kind"]}
        for item in all_items if item.get("published_at")
    ], key=lambda item: item["time"] or "", reverse=True)[:12]
    region_heat: dict[str, int] = {}
    for item in all_items:
        region = item.get("region") or "Polska"
        region_heat[region] = region_heat.get(region, 0) + 1
    return {
        "blindspots": blindspots[:20], "dead_heroes": dead_heroes[:10], "copy_matches": copy_matches[:20],
        "timeline": timeline, "region_heat": [{"region": region, "count": count} for region, count in sorted(region_heat.items(), key=lambda pair: pair[1], reverse=True)[:12]],
        "items": all_items[:120],
    }


def scan(sources: list[dict[str, Any]], publisher_source_id: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    unique_sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for source in sources[:12]:
        url = str(source.get("url", "")).strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_sources.append({
            "id": str(source.get("id") or hashlib.sha1(url.encode()).hexdigest()[:10]),
            "label": str(source.get("label") or urlparse(url).netloc), "url": url,
            "kind": str(source.get("kind") or "competitor"), "region": str(source.get("region") or "Polska"),
        })
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(unique_sources)))) as pool:
        futures = [pool.submit(fetch_source, source) for source in unique_sources]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda source: source["label"])
    findings = build_findings(results, publisher_source_id)
    live_count = sum(source["status"] == "live" for source in results)
    return {
        "scan_id": hashlib.sha1(f"{time.time_ns()}".encode()).hexdigest()[:16],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "sources": [{key: value for key, value in source.items() if key != "items"} | {"item_count": len(source["items"])} for source in results],
        "summary": {
            "source_count": len(results), "live_sources": live_count, "items": len(findings["items"]),
            "blindspots": len(findings["blindspots"]), "dead_heroes": len(findings["dead_heroes"]),
            "copy_matches": len(findings["copy_matches"]), "status": "live" if live_count else "degraded",
        },
        **findings,
    }
