import os
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
# The default keeps the local workflow unchanged.  Production deployments can
# point this at a mounted volume (or /tmp on an ephemeral serverless runtime)
# without changing application code.
DATA_DIR = Path(os.getenv("ZECRO_DATA_DIR", str(BASE_DIR / "data"))).expanduser()
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
    cors_origins: list[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv("ZECRO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()
    ])

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
