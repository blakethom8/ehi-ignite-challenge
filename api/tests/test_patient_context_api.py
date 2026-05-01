from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
FHIR_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


@contextmanager
def patched_env(updates: dict[str, str | None]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class PatientContextApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        files = sorted(FHIR_DIR.glob("*.json"))
        if not files:
            raise RuntimeError(f"No patient bundles found in {FHIR_DIR}")
        cls.patient_id = files[0].stem
        cls.client = TestClient(app)

    def _create_session(self, tmpdir: str) -> dict:
        with patch("api.core.patient_context.STORE_ROOT", Path(tmpdir)):
            response = self.client.post(
                "/api/patient-context/sessions",
                json={"patient_id": self.patient_id, "source_mode": "synthetic"},
            )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_session_creation_persists_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            body = self._create_session(tmpdir)
            root = Path(tmpdir) / self.patient_id / body["session_id"]

            self.assertTrue((root / "session.json").exists())
            self.assertTrue((root / "gap_cards.json").exists())
            self.assertTrue((root / "answers.jsonl").exists())
            self.assertGreaterEqual(len(body["gap_cards"]), 5)
            self.assertEqual(body["gap_cards"][0]["category"], "missing_sources")

    def test_missing_llm_key_returns_clear_503_for_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session = self._create_session(tmpdir)
            with patched_env({"ANTHROPIC_API_KEY": None}):
                with patch("api.core.patient_context.STORE_ROOT", Path(tmpdir)):
                    with patch("api.core.patient_context.REPO_ENV_PATH", Path("/tmp/nonexistent.env")):
                        response = self.client.post(
                            f"/api/patient-context/sessions/{session['session_id']}/turn",
                            json={
                                "message": "I also see a cardiologist at another clinic.",
                                "selected_gap_id": "sources-missing",
                            },
                        )

            self.assertEqual(response.status_code, 503)
            self.assertIn("ANTHROPIC_API_KEY", response.json().get("detail", ""))

    def test_patient_answer_appends_fact_and_updates_session(self) -> None:
        fake_response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    text=(
                        '{"assistant_message":"Thanks. Are there any medication changes your chart might miss?",'
                        '"captured_summary":"Patient reports seeing a cardiologist at another clinic.",'
                        '"confidence":"high","next_gap_id":"medication-reality"}'
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: fake_response))

        with tempfile.TemporaryDirectory() as tmpdir:
            session = self._create_session(tmpdir)
            with patched_env({"ANTHROPIC_API_KEY": "sk-ant-test"}):
                with patch("api.core.patient_context.STORE_ROOT", Path(tmpdir)):
                    with patch("anthropic.Anthropic", return_value=fake_client):
                        response = self.client.post(
                            f"/api/patient-context/sessions/{session['session_id']}/turn",
                            json={
                                "message": "I also see a cardiologist at another clinic.",
                                "selected_gap_id": "sources-missing",
                            },
                        )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(len(body["facts"]), 1)
            self.assertEqual(body["facts"][0]["source"], "patient-reported")
            self.assertEqual(body["facts"][0]["confidence"], "high")
            answered = {gap["id"]: gap["status"] for gap in body["gap_cards"]}
            self.assertEqual(answered["sources-missing"], "answered")

            answer_log = Path(tmpdir) / self.patient_id / session["session_id"] / "answers.jsonl"
            self.assertIn("cardiologist", answer_log.read_text(encoding="utf-8"))

    def test_export_writes_four_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session = self._create_session(tmpdir)
            with patch("api.core.patient_context.STORE_ROOT", Path(tmpdir)):
                response = self.client.post(
                    f"/api/patient-context/sessions/{session['session_id']}/export"
                )

            self.assertEqual(response.status_code, 200)
            root = Path(tmpdir) / self.patient_id / session["session_id"]
            for name in ("PATIENT_CONTEXT.md", "QUESTIONS.md", "SOURCES.md", "AGENT.md"):
                self.assertTrue((root / name).exists(), name)
                self.assertGreater(len((root / name).read_text(encoding="utf-8")), 50)
            self.assertIn("Patient Context", response.json()["preview"])


if __name__ == "__main__":
    unittest.main()
