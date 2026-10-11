import os
import re
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

def _load_environment_files() -> None:
    """Load the project's env files even when python-dotenv is unavailable.

    Vercel injects environment variables itself, while local development often
    runs the backend directly from a minimal Python environment.  Falling back
    to a tiny parser prevents that second case from silently selecting SQLite
    just because an optional convenience package was not installed.
    """
    # Vercel injects these values itself.  Outside Vercel, loading the checked
    # out `.env.local` implicitly would make the test suite and a developer's
    # default run write into a shared remote project.  Opt in explicitly when
    # a local process is meant to use the remote environment.
    # Provider credentials are safe to load for local AI discovery regardless
    # of the remote database opt-in.  The flag below only gates database and
    # Supabase settings.
    ai_keys = {"GEMINI_API_KEY", "GEMINI_MODEL_TEXT_PRO", "GEMINI_MODEL_TEXT_FAST", "GEMINI_MODEL_IMAGE", "GEMINI_MODEL_EMBED", "GEMINI_TIMEOUT_S", "GEMINI_MAX_RETRIES", "AI_MONTHLY_BUDGET_USD", "ZECRO_SECRETS_KEY", "ZECRO_ADMIN_TOKEN"}
    # `.env.supabase` is intentionally opt-in through ZECRO_LOAD_ENV_FILES;
    # it is useful for an explicit remote smoke test, while the ordinary test
    # and local-development path must keep using SQLite unless requested.
    env_files = [
        BASE_DIR / ".env.local",
        BASE_DIR / ".env.supabase",
        BASE_DIR / ".env",
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / ".env",
    ]
    assignment = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
    for env_file in env_files:
        if not env_file.exists():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = assignment.match(line)
            if not match:
                continue
            key, value = match.groups()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key in ai_keys or os.getenv("ZECRO_LOAD_ENV_FILES", "").lower() in {"1", "true", "yes", "on"} or os.getenv("VERCEL"):
                os.environ.setdefault(key, value)


_load_environment_files()
# The default keeps the local workflow unchanged. Vercel's filesystem is
# ephemeral and only /tmp is writable, so remote-only deployments use a cache
# directory there while PostgreSQL and Storage remain the source of truth.
_vercel_runtime = os.getenv("VERCEL", "").lower() in {"1", "true", "yes", "on"}
_default_data_dir = Path("/tmp/zecro-backend") if _vercel_runtime else BASE_DIR / "data"
DATA_DIR = Path(os.getenv("ZECRO_DATA_DIR", str(_default_data_dir))).expanduser()
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
DB_PATH = DATA_DIR / "layout_studio.db"

# Ensure runtime directories exist
for path in [DATA_DIR, UPLOADS_DIR, EXPORTS_DIR, THUMBNAILS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    app_name: str = "Zecro Generative Layout Engine"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("ZECRO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    uploads_dir: Path = UPLOADS_DIR
    exports_dir: Path = EXPORTS_DIR
    thumbnails_dir: Path = THUMBNAILS_DIR
    db_path: Path = DB_PATH
    default_energy_budget: float = 0.8
    vlm_endpoint: str = os.getenv("VLM_ENDPOINT", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model_text_pro: str = os.getenv("GEMINI_MODEL_TEXT_PRO", "gemini-3.1-pro-preview")
    gemini_model_text_fast: str = os.getenv("GEMINI_MODEL_TEXT_FAST", "gemini-3.8-flash")
    gemini_model_image: str = os.getenv("GEMINI_MODEL_IMAGE", "gemini-3-pro-image")
    gemini_model_embed: str = os.getenv("GEMINI_MODEL_EMBED", "gemini-embedding-2")
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "90"))
    gemini_max_retries: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    ai_monthly_budget_usd: float | None = (float(os.getenv("AI_MONTHLY_BUDGET_USD")) if os.getenv("AI_MONTHLY_BUDGET_USD") else None)
    secrets_key: str = os.getenv("ZECRO_SECRETS_KEY", "")
    admin_token: str = os.getenv("ZECRO_ADMIN_TOKEN", "")
    postgres_url: str = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", os.getenv("POSTGRES_PRISMA_URL", "")))
    supabase_url: str = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))
    supabase_storage_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET", "zecro-storage")
    # Production can opt out of the local fallback explicitly.  Vercel is
    # treated as remote-only by default because its filesystem is ephemeral.
    require_remote_db: bool = os.getenv(
        "ZECRO_REQUIRE_REMOTE_DB",
        "true" if os.getenv("VERCEL", "").lower() in {"1", "true", "yes", "on"} else "false",
    ).lower() in {"1", "true", "yes", "on"}
    require_remote_storage: bool = os.getenv(
        "ZECRO_REQUIRE_REMOTE_STORAGE",
        "true" if os.getenv("VERCEL", "").lower() in {"1", "true", "yes", "on"} else "false",
    ).lower() in {"1", "true", "yes", "on"}
    cors_origins: list[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv("ZECRO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://zecro.pl,https://www.zecro.pl,https://zecro-frontend.vercel.app").split(",") if origin.strip()
    ])

    @property
    def clean_postgres_url(self) -> str:
        if not self.postgres_url:
            return ""
        import urllib.parse
        parsed = urllib.parse.urlparse(self.postgres_url)
        # Filter out unsupported query parameters like supa=base-pooler.x
        query_params = urllib.parse.parse_qsl(parsed.query)
        allowed_params = ["sslmode", "connect_timeout", "application_name", "target_session_attrs"]
        filtered = [(k, v) for k, v in query_params if k in allowed_params]
        if not any(k == "sslmode" for k, _ in filtered):
            filtered.append(("sslmode", "require"))
        if not any(k == "connect_timeout" for k, _ in filtered):
            filtered.append(("connect_timeout", "10"))
        new_query = urllib.parse.urlencode(filtered)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", new_query, ""))

    @property
    def UPLOADS_DIR(self) -> Path:
        return self.uploads_dir

    @property
    def EXPORTS_DIR(self) -> Path:
        return self.exports_dir

    @property
    def DATA_DIR(self) -> Path:
        return self.data_dir

settings = Settings()

if settings.require_remote_db and not settings.clean_postgres_url:
    raise RuntimeError(
        "Remote database is required but POSTGRES_URL/DATABASE_URL is not configured. "
        "Set ZECRO_REQUIRE_REMOTE_DB=false only for an intentional local SQLite run."
    )
