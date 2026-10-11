from backend.app.config import settings
from backend.app.storage.asset_store import legacy_storage_key, materialize_asset, persist_asset
from backend.app.storage.supabase_storage import parse_storage_reference, storage_reference


def test_storage_references_are_portable_and_public_urls_are_parseable():
    reference = storage_reference("uploads/corpus-page.pdf")
    assert reference.startswith("supabase://")
    assert parse_storage_reference(reference) == (settings.supabase_storage_bucket, "uploads/corpus-page.pdf")
    assert parse_storage_reference(
        f"{settings.supabase_url or 'https://example.supabase.co'}/storage/v1/object/public/"
        f"{settings.supabase_storage_bucket}/uploads/corpus-page.pdf"
    ) == (settings.supabase_storage_bucket, "uploads/corpus-page.pdf")
    assert parse_storage_reference("uploads/corpus-page.pdf") == (
        settings.supabase_storage_bucket,
        "uploads/corpus-page.pdf",
    )


def test_legacy_local_paths_resolve_to_known_storage_prefixes():
    assert legacy_storage_key("/old/workstation/corpus_project_page.pdf", "uploads") == "uploads/corpus_project_page.pdf"
    assert legacy_storage_key("/old/workstation/export_candidate.zip", "exports") == "exports/export_candidate.zip"
    assert legacy_storage_key("/old/workstation/random.txt", "uploads") is None


def test_local_assets_remain_available_when_remote_storage_is_not_required(tmp_path, monkeypatch):
    source = tmp_path / "asset.png"
    source.write_bytes(b"png")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    monkeypatch.setattr(settings, "supabase_anon_key", "")
    monkeypatch.setattr(settings, "require_remote_storage", False)

    stored = persist_asset(source, prefix="uploads", key=source.name)
    assert stored == str(source)
    assert source.exists()
    assert materialize_asset(str(source), prefix="uploads", cache_dir=tmp_path / "cache") == source
