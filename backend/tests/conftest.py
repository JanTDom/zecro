import glob
import os

# Tests must never touch the shared Supabase project: AI keys load without
# this flag, the flag only switches the database/storage to the remote env.
if not os.getenv("ZECRO_ALLOW_REMOTE_TESTS"):
    os.environ["ZECRO_LOAD_ENV_FILES"] = "false"
    for _var in ("POSTGRES_URL", "DATABASE_URL", "POSTGRES_PRISMA_URL", "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"):
        os.environ.pop(_var, None)
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def library_fonts():
    """Ingest the repository's own fonts (Wukadka package) into the library."""
    from backend.app.engine import fonts
    seen = set()
    for f in sorted(glob.glob(str(ROOT / "corpus/wukadka/**/Document fonts/*.otf"), recursive=True)):
        name = os.path.basename(f)
        if name in seen:
            continue
        seen.add(name)
        fonts.ingest_path(f, source="corpus_wukadka")
    return fonts
