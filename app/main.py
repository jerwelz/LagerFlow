"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""

from fastapi import FastAPI

from app.errors import register_exception_handlers

app = FastAPI(
    title="LagerFlow",
    version="0.1.0",
    description="REST API for managing inventory in a small business.",
)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
