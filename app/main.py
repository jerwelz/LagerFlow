"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from app.api import inventory, movements, products
from app.config import Settings
from app.config import settings as default_settings
from app.errors import register_exception_handlers

# Compiled React dashboard (npm run build in frontend/). Optional: the API works without it.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app(
    settings: Settings = default_settings,
    engine: Engine | None = None,
    frontend_dir: Path = FRONTEND_DIR,
) -> FastAPI:
    app = FastAPI(
        title="LagerFlow",
        version="1.0.0",
        description="REST API for managing inventory in a small business.",
    )
    register_exception_handlers(app)
    app.include_router(products.router)
    app.include_router(movements.router)
    app.include_router(inventory.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.demo_mode:
        from app.database import engine as default_engine
        from app.demo_guard import install_demo_mode

        install_demo_mode(app, settings, engine or default_engine)

    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        # Only the build output is served: index.html at "/" and the bundled assets.
        # No catch-all route, so unknown API paths keep the JSON 404 error format.
        assets_dir = frontend_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        def dashboard() -> FileResponse:
            return FileResponse(index_file)

    return app


app = create_app()
