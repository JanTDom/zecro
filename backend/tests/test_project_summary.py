"""A created newspaper keeps its selected category and size after reload."""

from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.models.database import Database
from backend.app.models.schemas import Project


def test_project_list_derives_editorial_choices_from_persisted_dna(tmp_path):
    database = Database(tmp_path / "projects.db")
    project = database.create_project(Project(name="Miasto dziś"))
    dna = create_archetype_dnas()["tabloid"]
    database.save_title_dna(project.id, dna)

    listed = next(row for row in database.list_projects() if row.id == project.id)
    reopened = database.get_project(project.id)
    assert listed.editorial_character == reopened.editorial_character == "tabloid"
    assert listed.format_name == reopened.format_name == "tabloid"
    assert listed.dimensions["widthMm"] == 280
    assert listed.dimensions["heightMm"] == 390
