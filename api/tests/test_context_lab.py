from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


def test_context_lab_preview_accepts_fhir_bundle() -> None:
    client = TestClient(app)
    path = Path(
        "data/synthea-samples/synthea-r4-individual/fhir/"
        "Robert854_Botsford977_148ad83c-4dbc-4cb6-9334-44e6886f1e42.json"
    )

    with path.open("rb") as fh:
        response = client.post(
            "/api/context-lab/preview",
            files={"file": (path.name, fh, "application/json")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["entry_count"] == 303
    assert body["context_token_estimate"] > 0
    assert body["compression_ratio"] > 1
    assert body["fact_count"] > 0
    assert "# Patient:" in body["markdown"]
    assert body["resource_type_counts"]["Observation"] > 0
