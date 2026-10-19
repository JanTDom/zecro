from backend.app.engine import osint


def test_feed_parser_keeps_provenance_and_normalizes_items():
    payload = b'''<?xml version="1.0"?><rss><channel><item><title>Awaria tramwajow we Wroclawiu</title><link>https://example.com/a</link><description><![CDATA[Komunikacja miejska stoi.]]></description><pubDate>Mon, 14 Apr 2025 10:14:00 +0000</pubDate></item></channel></rss>'''
    result = osint._feed_entries(payload, {"id": "rmf", "label": "RMF", "url": "https://example.com/feed", "kind": "competitor", "region": "Wrocław"})
    assert len(result) == 1
    assert result[0]["source_id"] == "rmf"
    assert result[0]["title"] == "Awaria tramwajow we Wroclawiu"
    assert result[0]["published_at"].startswith("2025-04-14T10:14")


def test_findings_flag_topic_absent_from_publisher():
    base = {"status": "live", "error": None, "latency_ms": 1, "source_type": "feed"}
    sources = [
        {**base, "id": "own", "label": "Nasza redakcja", "kind": "publisher", "region": "Wrocław", "items": []},
        {**base, "id": "a", "label": "Konkurent A", "kind": "competitor", "region": "Wrocław", "items": [{"id": "a1", "title": "Awaria tramwajow na rondzie Mogilskim", "url": "https://a.test/a", "summary": "Ruch wstrzymany", "published_at": "2025-04-14T10:00:00+00:00", "source_id": "a", "source_label": "Konkurent A", "kind": "competitor", "region": "Wrocław"}]},
        {**base, "id": "b", "label": "Konkurent B", "kind": "competitor", "region": "Wrocław", "items": [{"id": "b1", "title": "Tramwaje stoją przez awarię na rondzie Mogilskim", "url": "https://b.test/a", "summary": "Utrudnienia", "published_at": "2025-04-14T10:05:00+00:00", "source_id": "b", "source_label": "Konkurent B", "kind": "competitor", "region": "Wrocław"}]},
    ]
    findings = osint.build_findings(sources, "own")
    assert findings["blindspots"]
    assert findings["blindspots"][0]["source_count"] == 2


def test_html_parser_marks_public_popularity_box():
    payload = b'''<html><body><section class="najpopularniejsze"><article><h2><a href="/popularny">Popularny tekst lokalny</a></h2><time datetime="2025-04-14T10:00:00Z"></time></article></section><article><h2><a href="/hero">Pierwszy tekst dnia lokalnie</a></h2></article></body></html>'''
    result = osint._html_entries(payload, {"id": "own", "label": "Wydawca", "url": "https://example.com", "kind": "publisher", "region": "Wrocław"})
    assert result[0]["is_popular"] is True


def test_scan_does_not_abort_when_one_source_fails(monkeypatch):
    def fake_fetch(source):
        return {**source, "status": "error", "items": [], "error": "timeout", "latency_ms": 10}

    monkeypatch.setattr(osint, "fetch_source", fake_fetch)
    result = osint.scan([{**osint.DEFAULT_SOURCES[0]}], None)
    assert result["summary"]["status"] == "degraded"
    assert result["sources"][0]["error"] == "timeout"
