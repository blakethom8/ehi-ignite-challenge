import json
import zipfile
from pathlib import Path

import pytest

from scripts.export_workspace_package import build_package
from scripts.validate_workspace_package import validate

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_PACKAGE = _REPO_ROOT / "data" / "workspace-packages" / "smoke-codex-upload-2026.zip"
_SMOKE_PDF_NAME = "9ae6d3aee5a7-corrected-lab-report.pdf"


def _package_root(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1
    return roots.pop()


def _read_json(zip_path: Path, rel_path: str):
    root = _package_root(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(zf.read(f"{root}/{rel_path}"))


@pytest.fixture
def smoke_codex_upload_session(tmp_path, monkeypatch):
    """Stage the smoke PDF + cached extraction in a temp UPLOADS_ROOT.

    The pre-built ``data/workspace-packages/smoke-codex-upload-2026.zip`` is
    committed and carries both the original PDF and its multipass-fhir
    extraction. We unpack those two files into a temp upload-session directory
    shaped like a real aggregation upload (``UPLOADS_ROOT/<patient>/<pdf>``
    plus ``<pdf>.extracted.json``), then redirect ``harmonize_service``'s
    ``UPLOADS_ROOT`` at that staging dir so ``patient_workspace_collection``
    can discover the source without depending on developer-local state.
    """
    from api.core import harmonize_service

    uploads_root = tmp_path / "aggregation-uploads"
    session_dir = uploads_root / "smoke-codex-upload-2026"
    session_dir.mkdir(parents=True)
    pdf_member = (
        "ehi-atlas-workspace-smoke-codex-upload-2026-20260508/"
        f"sources/original/{_SMOKE_PDF_NAME}"
    )
    extracted_member = (
        "ehi-atlas-workspace-smoke-codex-upload-2026-20260508/"
        f"sources/prepared/{_SMOKE_PDF_NAME}.extracted.json"
    )
    with zipfile.ZipFile(_SMOKE_PACKAGE) as zf:
        (session_dir / _SMOKE_PDF_NAME).write_bytes(zf.read(pdf_member))
        (session_dir / f"{_SMOKE_PDF_NAME}.extracted.json").write_bytes(
            zf.read(extracted_member)
        )

    monkeypatch.setattr(harmonize_service, "UPLOADS_ROOT", uploads_root)
    harmonize_service._cached_load.cache_clear()
    yield uploads_root
    harmonize_service._cached_load.cache_clear()


def test_export_synthea_demo_workspace_package(tmp_path):
    out = tmp_path / "synthea-demo.zip"

    build_package("synthea-demo", out, include_originals=False)

    assert out.exists()
    assert validate(out) == []

    manifest = _read_json(out, "MANIFEST.json")
    assert manifest["package_version"] == "atlas-workspace.v1"
    assert manifest["workspace_id"] == "synthea-demo"
    assert manifest["privacy"]["demo_data"] is True
    assert manifest["privacy"]["contains_phi"] is False
    assert manifest["canonical_fact_count"] > 0

    facts = _read_json(out, "evidence/canonical-facts.json")["facts"]
    assert any(fact["resource_type"] == "Observation" for fact in facts)
    assert any(fact.get("provenance_refs") or fact.get("source_refs") for fact in facts)

    packet = _read_json(out, "packets/second-opinion.context.json")
    assert packet["packet_version"] == "atlas-context.v1"
    assert packet["instructions"]


def test_export_smoke_pdf_workspace_package_with_original(tmp_path, smoke_codex_upload_session):
    out = tmp_path / "smoke-codex-upload-2026.zip"

    build_package("smoke-codex-upload-2026", out, include_originals=True)

    assert validate(out) == []

    root = _package_root(out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert f"{root}/sources/original/9ae6d3aee5a7-corrected-lab-report.pdf" in names
    assert f"{root}/sources/prepared/9ae6d3aee5a7-corrected-lab-report.pdf.extracted.json" in names

    facts = _read_json(out, "evidence/canonical-facts.json")["facts"]
    assert len(facts) >= 6
    assert {fact["resource_type"] for fact in facts} == {"Observation"}
