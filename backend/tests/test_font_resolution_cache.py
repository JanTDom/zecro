from pathlib import Path

from backend.app.engine import fonts


def test_font_face_lookup_reuses_remote_rows_within_generation(monkeypatch):
    calls = []

    def list_fonts(name):
        calls.append(name)
        return [{"family": name, "missing_chars": [], "italic": False,
                 "weight": 400, "width": 5, "storage_ref": "unit-test"}]

    monkeypatch.setattr(fonts.db, "list_fonts", list_fonts)
    monkeypatch.setattr(fonts, "local_file", lambda _face: Path("/tmp/unit-font.ttf"))
    monkeypatch.setattr(fonts.time, "monotonic", lambda: 100.0)
    fonts._cached_faces.cache_clear()
    for _ in range(10):
        assert fonts.resolve_face("Unit Test Font")["family"] == "Unit Test Font"
    assert calls == ["Unit Test Font"]
    fonts._cached_faces.cache_clear()
