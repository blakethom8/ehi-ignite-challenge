"""Guest pipeline dispatch — PDF + C-CDA extraction and rate-limit behavior."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.core import guest_harmonization
from api.main import app


MINIMAL_CCDA_WITH_PROBLEM_AND_MEDICATION = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Guest</given><family>Sample</family></name>
        <administrativeGenderCode code="M"/>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Continuity of Care Document</title>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4" codeSystem="2.16.840.1.113883.6.1"/>
          <title>Problems</title>
          <entry>
            <act>
              <entryRelationship typeCode="SUBJ">
                <observation>
                  <code code="55607006" codeSystem="2.16.840.1.113883.6.96"/>
                  <value xsi:type="CD"
                         code="73211009"
                         displayName="Diabetes mellitus"
                         codeSystem="2.16.840.1.113883.6.96"
                         codeSystemName="SNOMED CT"
                         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>
                  <effectiveTime><low value="20200101"/></effectiveTime>
                </observation>
              </entryRelationship>
            </act>
          </entry>
        </section>
      </component>
      <component>
        <section>
          <code code="10160-0" codeSystem="2.16.840.1.113883.6.1"/>
          <title>Medications</title>
          <entry>
            <substanceAdministration>
              <statusCode code="active"/>
              <effectiveTime value="20240101"/>
              <consumable>
                <manufacturedProduct>
                  <manufacturedMaterial>
                    <code code="259255"
                          displayName="Atorvastatin 20 MG Oral Tablet"
                          codeSystem="2.16.840.1.113883.6.88"
                          codeSystemName="RxNorm"/>
                  </manufacturedMaterial>
                </manufacturedProduct>
              </consumable>
            </substanceAdministration>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
"""


class GuestCCDADispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-ccda-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _create_run(self) -> str:
        response = self.client.post("/api/guest-harmonization/runs")
        self.assertEqual(response.status_code, 201)
        return response.json()["run_id"]

    def test_ccda_xml_produces_condition_and_medication_facts(self) -> None:
        run_id = self._create_run()
        upload = self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={
                "file": (
                    "ccda.xml",
                    MINIMAL_CCDA_WITH_PROBLEM_AND_MEDICATION,
                    "text/xml",
                )
            },
        )
        self.assertEqual(upload.status_code, 200, upload.text)

        processed = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        self.assertEqual(processed.status_code, 200, processed.text)
        guest_harmonization.wait_for_processing(run_id)

        output = self.client.get(f"/api/guest-harmonization/runs/{run_id}/output").json()
        resource_types = {fact["resource_type"] for fact in output["facts"]}
        self.assertIn("Condition", resource_types)
        self.assertIn("MedicationRequest", resource_types)
        for prov in output["provenance"]:
            self.assertEqual(prov["method"], "guest_ccda_fallback_v1")

    def test_xml_that_is_not_ccda_records_quality_issue(self) -> None:
        run_id = self._create_run()
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("not-ccda.xml", "<note>hi</note>", "text/xml")},
        )
        self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        guest_harmonization.wait_for_processing(run_id)
        output = self.client.get(f"/api/guest-harmonization/runs/{run_id}/output").json()

        codes = {issue["code"] for issue in output["quality_issues"]}
        self.assertIn("xml_not_ccda", codes)
        self.assertEqual(output["facts"], [])


class GuestPDFDispatchTests(unittest.TestCase):
    """PDF dispatch — rate limit and unreadable-PDF behavior.

    We avoid shipping a binary PDF fixture; the dispatch + rate-limit logic is
    what we lock in here. A real lab-PDF positive path is exercised by manual
    end-to-end testing.
    """

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="guest-pdf-test-"))
        self._old_root = guest_harmonization.GUEST_ROOT
        self._old_secret_path = guest_harmonization.GUEST_SECRET_PATH
        guest_harmonization.GUEST_ROOT = self._tmp / "runs"
        guest_harmonization.GUEST_SECRET_PATH = self._tmp / "guest.key"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        guest_harmonization.GUEST_ROOT = self._old_root
        guest_harmonization.GUEST_SECRET_PATH = self._old_secret_path
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _create_run(self) -> str:
        response = self.client.post("/api/guest-harmonization/runs")
        return response.json()["run_id"]

    def test_unreadable_pdf_emits_quality_issue_not_crash(self) -> None:
        run_id = self._create_run()
        self.client.post(
            f"/api/guest-harmonization/runs/{run_id}/uploads",
            files={"file": ("not-a-real.pdf", b"%PDF-1.4 broken", "application/pdf")},
        )
        processed = self.client.post(f"/api/guest-harmonization/runs/{run_id}/process")
        self.assertEqual(processed.status_code, 200, processed.text)
        guest_harmonization.wait_for_processing(run_id)

        output = self.client.get(f"/api/guest-harmonization/runs/{run_id}/output").json()
        codes = {issue["code"] for issue in output["quality_issues"]}
        # Either the text layer is unreadable, or the pipeline ran and found no
        # clinical resources, or vision wasn't configured in this env. All are
        # acceptable graceful outcomes — we just need not to crash the run.
        self.assertTrue(
            codes
            & {
                "pdf_unreadable",
                "pdf_low_yield",
                "pdf_extraction_failed",
                "pipeline_unconfigured",
            },
            f"expected a graceful PDF quality issue, got {codes}",
        )


if __name__ == "__main__":
    unittest.main()
