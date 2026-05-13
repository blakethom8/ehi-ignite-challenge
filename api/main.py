"""
EHI Ignite Challenge — FastAPI backend.

Run: uv run uvicorn api.main:app --reload --port 8000
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

# Load local .env from project root before anything else reads env vars.
# Keep override=False so real environment variables (e.g., production secrets)
# always win over values from .env.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.core.auth import init_auth_store
from api.core.demo_aggregate_seed import seed_demo_aggregate_uploads
from api.core.loader import warm_patient_indexes
from api.core.sof_materialize import materialize_from_env
from api.middleware.tracing import TracingMiddleware
from api.routers import admin
from api.routers import audit
from api.routers import auth
from api.routers import patients
from api.routers import corpus
from api.routers import assistant
from api.routers import workflows as caspian_workflows
from api.routers import caspian_files
from api.routers import traces
from api.routers import classifications
from api.routers import patient_context
from api.routers import aggregation
from api.routers import harmonize
from api.routers import guest_harmonization
from api.routers import canonical
from api.routers import cursor_internal_tools
from api.routers import ground_truth_review
from api.routers import pipeline_lab
from api.routers import ccda_lab
from api.routers import skills as skills_router
from api.plugins.routers import plugins as plugins_router
from api.plugins import runtime as plugin_runtime
from api.settings import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
_IS_PRODUCTION = _settings.is_production

app = FastAPI(
    title="EHI Ignite API",
    description="Clinical intelligence layer over FHIR patient data",
    version="0.1.0",
    docs_url=None if _IS_PRODUCTION else "/docs",
    redoc_url=None if _IS_PRODUCTION else "/redoc",
    openapi_url=None if _IS_PRODUCTION else "/openapi.json",
)


@app.on_event("startup")
def _materialize_sof_db() -> None:
    """Rebuild data/sof.db on boot if any ViewDefinition or bundle is newer.

    Idempotent — a fresh DB triggers no work. Controlled by the
    ``SOF_AUTO_MATERIALIZE``/``SOF_PATIENT_LIMIT``/``SOF_DB_PATH`` env vars;
    never raises (see ``sof_materialize.materialize_from_env``).
    """
    materialize_from_env()
    init_auth_store()
    # The first app interaction needs /api/patients. Build that lightweight
    # index during startup so production users do not pay the corpus-cache
    # rebuild cost on the first page load after deploy.
    warm_patient_indexes()
    patients._cached_patient_list()
    # Stage the multi-source demo personas' synthetic documents into the
    # aggregation-uploads store so they appear as pre-uploaded sources on the
    # source intake page. Idempotent — only adds files that aren't already
    # present, never clobbers user edits.
    try:
        seed_demo_aggregate_uploads()
    except Exception:
        # Never let a seeder failure prevent the API from booting.
        logger.exception("startup: seed_demo_aggregate_uploads failed")
    # Cache verified plugin manifests in memory so /api/plugins/installed
    # serves without re-verifying signatures on every request.
    try:
        plugin_runtime.reload_manifests()
    except Exception:
        # Don't crash the API if a manifest is malformed — just log.
        logger.exception("startup: plugin_runtime.reload_manifests failed")
    # Rehydrate revoked-run set from runs.db so consent revocations survive
    # the restart we just performed. Without this, a revoked plugin would
    # silently regain tool access on the next deploy.
    try:
        plugin_runtime.reload_revoked_runs()
    except Exception:
        logger.exception("startup: plugin_runtime.reload_revoked_runs failed")
    # Purge audit events older than EVENTS_RETENTION_DAYS so events.db
    # stays bounded under production traffic. Default 90 days; set to 0
    # to disable. Best-effort — never crash the API on a purge failure.
    try:
        from api.workspace.events import purge_events_older_than

        purge_events_older_than()
    except Exception:
        logger.exception("startup: purge_events_older_than failed")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_settings.allowed_hosts,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)

app.add_middleware(TracingMiddleware)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(patients.router, prefix="/api")
app.include_router(corpus.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(caspian_workflows.router, prefix="/api")
app.include_router(caspian_files.router, prefix="/api")
app.include_router(traces.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(classifications.router, prefix="/api")
app.include_router(patient_context.router, prefix="/api")
app.include_router(aggregation.router, prefix="/api")
app.include_router(harmonize.router, prefix="/api")
app.include_router(guest_harmonization.router, prefix="/api")
app.include_router(canonical.router, prefix="/api")
app.include_router(cursor_internal_tools.router, prefix="/api")
app.include_router(ground_truth_review.router, prefix="/api")
app.include_router(pipeline_lab.router, prefix="/api")
app.include_router(ccda_lab.router, prefix="/api")
app.include_router(skills_router.router, prefix="/api")
app.include_router(plugins_router.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
