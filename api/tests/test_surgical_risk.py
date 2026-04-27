from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class SurgicalRiskApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_showcase_patient_has_deterministic_high_risk_score(self) -> None:
        response = self.client.get(
            "/api/patients/92c9a4f3-162d-4979-96fa-d81bf4641125/surgical-risk"
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "Louis204 Wiza601")
        self.assertEqual(body["tier"], "HIGH")
        self.assertEqual(body["disposition"], "HOLD")
        self.assertEqual(body["rule_version"], "preop-rules-v1")
        self.assertGreaterEqual(body["score"], 50)

        components = {component["key"]: component for component in body["components"]}
        self.assertEqual(set(components), {"medications", "conditions", "labs", "allergies", "interactions"})
        self.assertEqual(components["medications"]["status"], "FLAGGED")
        self.assertEqual(components["conditions"]["status"], "FLAGGED")
        self.assertTrue(components["medications"]["evidence"])
        self.assertTrue(components["conditions"]["evidence"])


if __name__ == "__main__":
    unittest.main()
