from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from db.session import init_db
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="UP Police Data Analyst Agent", version="0.1.0", lifespan=_lifespan)
    from api import health, datasets, sessions
    app.include_router(health.router)
    app.include_router(datasets.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")

    # Serve the built Next.js static export at /app
    # Run `cd frontend && pnpm build` to generate frontend/out/ before starting.
    # Server starts fine without it (API-only mode when out/ doesn't exist).
    # __file__ = src/api/__init__.py → 3 parents up = repo root
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_out), html=True), name="frontend")

        # Send the bare root to the UI so the base URL lands somewhere useful.
        @app.get("/", include_in_schema=False)
        def _root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/app/")

    return app


app = create_app()
