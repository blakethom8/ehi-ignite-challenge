from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def _ccda_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Ada</given><family>Lab</family></name>
        <administrativeGenderCode code="F"/>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Continuity of Care Document</title>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4"/>
          <title>Problems</title>
          <entry>
            <act>
              <entryRelationship>
                <observation>
                  <value code="38341003" displayName="Hypertension" codeSystemName="SNOMED CT"/>
                </observation>
              </entryRelationship>
            </act>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
"""


def test_ccda_lab_lists_processors() -> None:
    client = TestClient(app)

    response = client.get("/api/internal/ccda-lab/processors")

    assert response.status_code == 200
    processor_ids = {option["id"] for option in response.json()["options"]}
    assert {"ccda-auto", "ccda-microsoft", "ccda-fallback"} <= processor_ids
    assert "pdfplumber-lab-text" in processor_ids


def test_ccda_lab_converts_ccda_with_fallback() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/internal/ccda-lab/convert",
        data={"processor_id": "ccda-fallback", "skip_cache": "false"},
        files={"file": ("summary.xml", _ccda_xml(), "application/xml")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["input_kind"] == "ccda"
    assert body["processor_id"] == "ccda-fallback"
    assert body["bundle"]["resourceType"] == "Bundle"
    assert body["resource_counts"]["Patient"] == 1
    assert body["resource_counts"]["Condition"] == 1
    assert body["bundle_shape"]["total_entries"] >= 3


def test_ccda_lab_rejects_wrong_processor_for_ccda() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/internal/ccda-lab/convert",
        data={"processor_id": "pdfplumber-lab-text"},
        files={"file": ("summary.xml", _ccda_xml(), "application/xml")},
    )

    assert response.status_code == 400
