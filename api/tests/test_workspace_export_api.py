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


def test_export_workspace_downloads_synthea_package():
    client = TestClient(app)

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
    client = TestClient(app)

    response = client.get("/api/harmonize/does-not-exist/export-workspace")

    assert response.status_code == 404
