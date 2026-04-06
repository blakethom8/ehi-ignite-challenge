"""
EHI Ignite Challenge — FastAPI backend.

Run: uv run uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import patients
from api.routers import corpus
from api.routers import assistant

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

app.include_router(patients.router, prefix="/api")
app.include_router(corpus.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
