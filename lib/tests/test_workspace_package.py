import json
import zipfile
from pathlib import Path

from scripts.export_workspace_package import build_package
from scripts.validate_workspace_package import validate


def _package_root(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1
    return roots.pop()


def _read_json(zip_path: Path, rel_path: str):
    root = _package_root(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(zf.read(f"{root}/{rel_path}"))


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


def test_export_smoke_pdf_workspace_package_with_original(tmp_path):
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
