import json
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from api.main import app


def _zip_root(payload: bytes) -> tuple[zipfile.ZipFile, str]:
    zf = zipfile.ZipFile(BytesIO(payload))
    roots = {name.split("/", 1)[0] for name in zf.namelist() if "/" in name}
    assert len(roots) == 1
    return zf, roots.pop()


def _authenticated_client() -> TestClient:
    """Return a TestClient logged in as the bootstrap clinician.

    The harmonize router now requires an authenticated session for every
    endpoint, so workspace-export tests log in before exercising the route.
    """
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200, response.text
    return client


def test_export_workspace_downloads_synthea_package():
    client = _authenticated_client()

    response = client.get("/api/harmonize/synthea-demo/export-workspace")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "synthea-demo.zip" in response.headers.get("content-disposition", "")

    zf, root = _zip_root(response.content)
    with zf:
        names = set(zf.namelist())
        assert f"{root}/MANIFEST.json" in names
        assert f"{root}/AGENT-INSTRUCTIONS.md" in names
        assert f"{root}/evidence/canonical-facts.json" in names
        manifest = json.loads(zf.read(f"{root}/MANIFEST.json"))
        assert manifest["workspace_id"] == "synthea-demo"
        assert manifest["canonical_fact_count"] > 0


def test_export_workspace_unknown_collection_404s():
    client = _authenticated_client()

    response = client.get("/api/harmonize/does-not-exist/export-workspace")

    assert response.status_code == 404


def test_export_workspace_audience_marks_primary_packet_and_filename():
    client = _authenticated_client()

    response = client.get(
        "/api/harmonize/synthea-demo/export-workspace?audience=preop-review"
    )
    assert response.status_code == 200
    assert "synthea-demo-preop-review.zip" in response.headers.get("content-disposition", "")

    zf, root = _zip_root(response.content)
    with zf:
        preop = json.loads(zf.read(f"{root}/packets/preop-review.context.json"))
        assert preop.get("primary") is True
        # Sibling packets should NOT be primary.
        for purpose in ("patient-summary", "clinician-handoff", "second-opinion"):
            sibling = json.loads(zf.read(f"{root}/packets/{purpose}.context.json"))
            assert sibling.get("primary") in (False, None)


def test_export_workspace_unknown_audience_400s():
    client = _authenticated_client()

    response = client.get(
        "/api/harmonize/synthea-demo/export-workspace?audience=not-a-real-audience"
    )
    assert response.status_code == 400


def test_export_workspace_unknown_snapshot_404s():
    client = _authenticated_client()

    response = client.get(
        "/api/harmonize/synthea-demo/export-workspace?snapshot=does-not-exist"
    )
    assert response.status_code == 404
