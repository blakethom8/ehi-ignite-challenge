"""
EHI Ignite Challenge — FastAPI backend.

Run: uv run uvicorn api.main:app --reload --port 8000
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load local .env from project root before anything else reads os.getenv().
# Keep override=False so real environment variables (e.g., production secrets)
# always win over values from .env.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.core.loader import warm_patient_indexes
from api.core.sof_materialize import materialize_from_env
from api.middleware.tracing import TracingMiddleware
from api.routers import patients
from api.routers import corpus
from api.routers import assistant
from api.routers import traces
from api.routers import classifications
from api.routers import patient_context
from api.routers import aggregation
from api.routers import cursor_internal_tools

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_IS_PRODUCTION = _ENVIRONMENT in {"prod", "production"}

app = FastAPI(
    title="EHI Ignite API",
    description="Clinical intelligence layer over FHIR patient data",
    version="0.1.0",
    docs_url=None if _IS_PRODUCTION else "/docs",
    redoc_url=None if _IS_PRODUCTION else "/redoc",
    openapi_url=None if _IS_PRODUCTION else "/openapi.json",
)


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@app.on_event("startup")
def _materialize_sof_db() -> None:
    """Rebuild data/sof.db on boot if any ViewDefinition or bundle is newer.

    Idempotent — a fresh DB triggers no work. Controlled by the
    ``SOF_AUTO_MATERIALIZE``/``SOF_PATIENT_LIMIT``/``SOF_DB_PATH`` env vars;
    never raises (see ``sof_materialize.materialize_from_env``).
    """
    materialize_from_env()
    # The first app interaction needs /api/patients. Build that lightweight
    # index during startup so production users do not pay the corpus-cache
    # rebuild cost on the first page load after deploy.
    warm_patient_indexes()
    patients.list_patients()

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_csv_env(
        "ALLOWED_HOSTS",
        [
            "ehi.healthcaredataai.com",
            "localhost",
            "127.0.0.1",
            "testserver",
        ],
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_csv_env(
        "CORS_ALLOWED_ORIGINS",
        [
            "http://localhost:5173",
            "http://localhost:3000",
            "https://ehi.healthcaredataai.com",
        ],
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)

app.add_middleware(TracingMiddleware)

app.include_router(patients.router, prefix="/api")
app.include_router(corpus.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(traces.router, prefix="/api")
app.include_router(classifications.router, prefix="/api")
app.include_router(patient_context.router, prefix="/api")
app.include_router(aggregation.router, prefix="/api")
app.include_router(cursor_internal_tools.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
