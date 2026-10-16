from backend.app.models.database import db


def test_font_boolean_flags_are_stored_as_integer_columns(monkeypatch):
    captured = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, query, values):
            captured["query"] = query
            captured["values"] = values

        def commit(self):
            pass

    monkeypatch.setattr(db, "get_connection", lambda: Connection())
    monkeypatch.setattr(db, "get_font_by_sha", lambda _: None)
    db.save_font({"family": "Inter", "storage_ref": "supabase://fonts/inter.ttf", "sha256": "test",
                  "italic": False, "has_kerning": True, "is_variable": False, "missing_chars": []})
    columns = captured["query"].split("INSERT INTO fonts(", 1)[1].split(")", 1)[0].split(",")
    values = dict(zip(columns, captured["values"]))
    assert values["italic"] == 0
    assert values["has_kerning"] == 1
    assert values["is_variable"] == 0
    assert values["missing_chars"] == "[]"
