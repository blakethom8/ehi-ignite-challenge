from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from api.core import ccda

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_ccda(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Ada</given><family>Converter</family></name>
        <administrativeGenderCode code="F"/>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Continuity of Care Document</title>
</ClinicalDocument>
""",
        encoding="utf-8",
    )


def _write_problems_and_medications_ccda(path: Path) -> None:
    """Minimal C-CDA fixture with a Problem List and Medications section.

    Mirrors the structure of the Cerner ``problems-and-medications.xml`` sample
    that lives in ``ehi-atlas/corpus/_sources/josh-ccdas/raw/`` after the
    corpus repo is cloned. That corpus is gitignored, so the test inlines
    a small equivalent here: 5 problem entries (each with a nested ``Status``
    observation whose displayName the fallback parser must NOT promote to a
    Condition) plus 6 ``substanceAdministration`` entries.
    """

    def _problem_entry(code: str, display: str) -> str:
        return f"""
      <entry>
        <act classCode="ACT" moodCode="EVN">
          <code code="CONC" displayName="Concern"/>
          <statusCode code="active"/>
          <entryRelationship typeCode="SUBJ">
            <observation classCode="OBS" moodCode="EVN">
              <code code="55607006" displayName="Problem" codeSystem="2.16.840.1.113883.6.96"/>
              <statusCode code="completed"/>
              <value xsi:type="CD" code="{code}" displayName="{display}" codeSystem="2.16.840.1.113883.6.96"/>
              <entryRelationship typeCode="REFR">
                <observation classCode="OBS" moodCode="EVN">
                  <code code="33999-4" displayName="Status" codeSystem="2.16.840.1.113883.6.1"/>
                  <statusCode code="completed"/>
                  <value xsi:type="CD" code="55561003" displayName="Active" codeSystem="2.16.840.1.113883.6.96"/>
                </observation>
              </entryRelationship>
            </observation>
          </entryRelationship>
        </act>
      </entry>"""

    def _medication_entry(code: str, display: str) -> str:
        return f"""
      <entry>
        <substanceAdministration classCode="SBADM" moodCode="EVN">
          <statusCode code="active"/>
          <consumable>
            <manufacturedProduct>
              <manufacturedMaterial>
                <code code="{code}" displayName="{display}" codeSystem="2.16.840.1.113883.6.88"/>
              </manufacturedMaterial>
            </manufacturedProduct>
          </consumable>
        </substanceAdministration>
      </entry>"""

    problems = "".join(
        _problem_entry(code, display)
        for code, display in (
            ("59621000", "Essential hypertension"),
            ("44054006", "Diabetes mellitus type 2"),
            ("13644009", "Hypercholesterolemia"),
            ("194828000", "Angina"),
            ("195967001", "Asthma"),
        )
    )
    medications = "".join(
        _medication_entry(code, display)
        for code, display in (
            ("617314", "Lipitor 20 mg oral tablet"),
            ("310965", "Aspirin 81 mg oral tablet"),
            ("197361", "Metformin 500 mg oral tablet"),
            ("314076", "Lisinopril 10 mg oral tablet"),
            ("198211", "Albuterol 90 mcg/actuation inhaler"),
            ("204384", "Atorvastatin 40 mg oral tablet"),
        )
    )

    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Cerner</given><family>Sample</family></name>
        <administrativeGenderCode code="F"/>
        <birthTime value="19500101"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Problems and Medications</title>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4" displayName="Problem List" codeSystem="2.16.840.1.113883.6.1"/>
          <title>Problems</title>{problems}
        </section>
      </component>
      <component>
        <section>
          <code code="10160-0" displayName="History of Medication Use" codeSystem="2.16.840.1.113883.6.1"/>
          <title>Medications</title>{medications}
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
""",
        encoding="utf-8",
    )


def _bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "batch",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "ms-patient",
                    "name": [{"given": ["Ada"], "family": "Converter"}],
                    "gender": "female",
                    "birthDate": "1980-01-02",
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "ms-condition",
                    "code": {"text": "Converted condition"},
                }
            },
        ],
    }


class CcdaConverterTests(unittest.TestCase):
    def test_uses_microsoft_api_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.xml"
            _write_ccda(path)
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=None)
            response.read.return_value = json.dumps({"result": _bundle()}).encode("utf-8")

            with (
                patch.dict("os.environ", {"FHIR_CONVERTER_URL": "http://converter"}, clear=False),
                patch("urllib.request.urlopen", return_value=response) as urlopen,
            ):
                bundle = ccda.convert_ccda_to_fhir_bundle(str(path), "ccda-summary")

        self.assertEqual(bundle["entry"][0]["resource"]["id"], "ms-patient")
        self.assertEqual(bundle["entry"][1]["resource"]["code"]["text"], "Converted condition")
        self.assertTrue(any(entry["resource"]["resourceType"] == "DocumentReference" for entry in bundle["entry"]))
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["InputDataFormat"], "Ccda")
        self.assertEqual(body["RootTemplateName"], "CCD")

    def test_falls_back_when_converter_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.xml"
            _write_ccda(path)
            with patch.dict("os.environ", {}, clear=True):
                bundle = ccda.convert_ccda_to_fhir_bundle(str(path), "ccda-summary")

        resources = [entry["resource"] for entry in bundle["entry"]]
        self.assertTrue(any(resource["resourceType"] == "Patient" for resource in resources))
        self.assertTrue(any(resource["resourceType"] == "DocumentReference" for resource in resources))

    def test_required_converter_mode_raises_instead_of_falling_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.xml"
            _write_ccda(path)

            with (
                patch.dict(
                    "os.environ",
                    {"FHIR_CONVERTER_URL": "http://converter", "FHIR_CONVERTER_REQUIRED": "true"},
                    clear=False,
                ),
                patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
                self.assertRaises(urllib.error.URLError),
            ):
                ccda.convert_ccda_to_fhir_bundle(str(path), "ccda-summary")

    def test_fallback_does_not_turn_problem_statuses_into_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "problems-and-medications.xml"
            _write_problems_and_medications_ccda(path)

            with patch.dict("os.environ", {}, clear=True):
                bundle = ccda.convert_ccda_to_fhir_bundle(str(path), "ccda-cerner", mode="fallback")

        resources = [entry["resource"] for entry in bundle["entry"]]
        conditions = [resource for resource in resources if resource["resourceType"] == "Condition"]
        medications = [resource for resource in resources if resource["resourceType"] == "MedicationRequest"]
        condition_displays = [condition["code"]["text"] for condition in conditions]
        medication_displays = [med["medicationCodeableConcept"]["text"] for med in medications]

        self.assertEqual(len(conditions), 5)
        self.assertNotIn("Active", condition_displays)
        self.assertEqual(len(medications), 6)
        self.assertIn("Lipitor 20 mg oral tablet", medication_displays)


if __name__ == "__main__":
    unittest.main()
