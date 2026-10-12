from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .api import projects, corpus, dna, generate, preferences, export, assets, archetypes, editorial, editorial_model, production, ai, settings_integrations, logo, page_plan, studio
from .models.database import db
from .storage.asset_store import storage_configured

app = FastAPI(
    title="Zecro Generative Layout Engine",
    description="Computational layout engine for editorial art direction with Title DNA, constraint solver, evolutionary exploration, two-layer critic, taste loop, and IDML/PDF production rendering.",
    version=settings.app_version
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(projects.router)
app.include_router(corpus.router)
app.include_router(dna.router)
app.include_router(generate.router)
app.include_router(preferences.router)
app.include_router(export.router)
app.include_router(assets.router)
app.include_router(archetypes.router)
app.include_router(editorial.router)
app.include_router(editorial_model.router)
app.include_router(production.router)
app.include_router(ai.router)
app.include_router(settings_integrations.router)
app.include_router(logo.router)
app.include_router(page_plan.router)
app.include_router(studio.router)

# Mount local storage for assets
app.mount("/static/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")
app.mount("/static/exports", StaticFiles(directory=str(settings.EXPORTS_DIR)), name="exports")

@app.get("/")
def root():
    return {
        "status": "online",
        "app": settings.app_name,
        "brand": "Zecro.pl",
        "product": "Zecro Generative Layout Engine",
        "version": settings.app_version,
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    database_ok = False
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        database_ok = True
    except Exception:
        database_ok = False
    return {
        "status": "healthy" if database_ok else "degraded",
        "db": "connected" if database_ok else "unavailable",
        "db_backend": db.backend_name,
        "persistent_db": db.is_remote,
        "storage_backend": "supabase" if storage_configured() else "local",
        "persistent_storage": storage_configured(),
        "storage": str(settings.DATA_DIR)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
