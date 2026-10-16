"""Only pages with verified identity and zone may train a genre grammar."""

import json

from PIL import Image

from backend.app.engine.corpus_indexer import CorpusIndexer, build_generation_guidance
from backend.app.engine.corpus_knowledge import _bundled_index, ensure_bundled_index


def test_corpus_scan_excludes_misattributed_and_wrong_zone_pages(tmp_path):
    folder = tmp_path / "4_tabloidy_bulwarowe" / "sample" / "1_pierwsza_strona"
    folder.mkdir(parents=True)
    rows = []
    cases = [
        ("real.jpg", "accepted", "yes", "front", "2020s"),
        ("wrong-title.jpg", "accepted", "no", "front", "2020s"),
        ("inside.jpg", "accepted", "yes", "inside", "2020s"),
        ("historical.jpg", "accepted", "yes", "front", "1910s"),
    ]
    for name, verdict, title_match, zone, era in cases:
        Image.new("RGB", (100, 140), "white").save(folder / name)
        rows.append({"path": f"4_tabloidy_bulwarowe/sample/1_pierwsza_strona/{name}",
                     "verdict": verdict, "title_matches_folder": title_match,
                     "page_zone_guess": zone, "era": era, "reason": "Pierwsza strona gazety."})
    (tmp_path / "CORPUS_AUDIT.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    pages = CorpusIndexer(tmp_path).scan()
    assert {page["file_name"] for page in pages} == {"real.jpg", "historical.jpg"}
    assert {page["file_name"] for page in pages if page["style_eligible"]} == {"real.jpg"}
    guidance = build_generation_guidance(pages, archetype="tabloid", zone="front_page")
    assert guidance["sample_count"] == 1


def test_bundled_index_replaces_stale_production_corpus():
    bundled = _bundled_index()
    assert bundled is not None
    assert bundled["version"] == "3.0.0"
    assert bundled["source_digest"]
    assert bundled["page_count"] == len(bundled["pages"]) == 281
    assert sum(bool(page.get("style_eligible")) for page in bundled["pages"]) == 140
    assert all(not page["path"].startswith("/") for page in bundled["pages"])

    class DatabaseStub:
        saved = {"version": "2.0.0", "source_digest": "stale"}
        writes = 0

        def get_global_corpus_index(self, *, include_pages=False):
            return self.saved

        def save_global_corpus_index(self, index):
            self.writes += 1
            self.saved = index

    database = DatabaseStub()
    assert ensure_bundled_index(database)
    assert database.writes == 1
    assert database.saved["source_digest"] == bundled["source_digest"]
    assert not ensure_bundled_index(database)
