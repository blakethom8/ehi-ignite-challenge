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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
