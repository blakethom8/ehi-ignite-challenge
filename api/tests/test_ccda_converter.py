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
        path = REPO_ROOT / "ehi-atlas/corpus/_sources/josh-ccdas/raw/Cerner Samples/problems-and-medications.xml"

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
