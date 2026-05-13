"""Patient voice adapter: turn the guided Patient Context session into FHIR.

This module is the bridge from the Atlas Patient Context intake (which
captures patient-reported turns as Markdown + JSON) to FHIR-shaped
resources that the cross-source harmonizer (``lib.harmonize``) can ingest
as just another source.

The single public entry point is :func:`session_to_fhir_bundle`. It takes
a dumped Patient Context session (the ``PatientContextSessionResponse``
shape from ``api.models``, exported via ``.model_dump(mode='json')``) and
returns a FHIR R4 ``Bundle`` (``type='collection'``) of:

- ``MedicationStatement`` for medication claims
- ``Condition`` for diagnosis claims (always ``verificationStatus=unconfirmed``)
- ``Goal`` for care-goal statements
- ``Observation`` (``code.system=atlas:patient-voice``) as the fallback

See ``docs/architecture/context/LLM-CONTEXT-AUGMENTATION-PLAN.md`` §3.1 for the
worked JSON examples and §T1 for acceptance criteria.
"""

from .classifier import (
    FakeTurnClassifier,
    HaikuTurnClassifier,
    TurnClassification,
    TurnClassifier,
)
from .ingest import PATIENT_VOICE_LABEL, patient_voice_source_bundles
from .summarize import (
    FakeVoiceSummarizer,
    HaikuVoiceSummarizer,
    PatientVoiceSummary,
    VoiceSummarizer,
    load_summary,
    regenerate_voice_summary,
    summary_path_for,
    write_summary,
)
from .to_fhir import session_to_fhir_bundle

__all__ = [
    "FakeTurnClassifier",
    "FakeVoiceSummarizer",
    "HaikuTurnClassifier",
    "HaikuVoiceSummarizer",
    "PATIENT_VOICE_LABEL",
    "PatientVoiceSummary",
    "TurnClassification",
    "TurnClassifier",
    "VoiceSummarizer",
    "load_summary",
    "patient_voice_source_bundles",
    "regenerate_voice_summary",
    "session_to_fhir_bundle",
    "summary_path_for",
    "write_summary",
]
