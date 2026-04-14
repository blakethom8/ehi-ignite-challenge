"""
EHI Ignite Challenge — FastAPI backend.

Run: uv run uvicorn api.main:app --reload --port 8000
"""

from pathlib import Path

from dotenv import load_dotenv

# Load local .env from project root before anything else reads os.getenv().
# Keep override=False so real environment variables (e.g., production secrets)
# always win over values from .env.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.sof_materialize import materialize_from_env
from api.middleware.tracing import TracingMiddleware
from api.routers import patients
from api.routers import corpus
from api.routers import assistant
from api.routers import traces

app = FastAPI(
    title="EHI Ignite API",
    description="Clinical intelligence layer over FHIR patient data",
    version="0.1.0",
)


@app.on_event("startup")
def _materialize_sof_db() -> None:
    """Rebuild data/sof.db on boot if any ViewDefinition or bundle is newer.

    Idempotent — a fresh DB triggers no work. Controlled by the
    ``SOF_AUTO_MATERIALIZE``/``SOF_PATIENT_LIMIT``/``SOF_DB_PATH`` env vars;
    never raises (see ``sof_materialize.materialize_from_env``).
    """
    materialize_from_env()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://ehi.healthcaredataai.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TracingMiddleware)

app.include_router(patients.router, prefix="/api")
app.include_router(corpus.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(traces.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
