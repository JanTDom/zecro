"""Vercel entrypoint for the Zecro FastAPI service.

The frontend and API are deployed as separate Vercel projects from the same
GitHub repository.  Keeping this tiny adapter in the backend project lets
Vercel discover the existing ASGI application without changing local startup.
"""

from app.main import app

__all__ = ["app"]
