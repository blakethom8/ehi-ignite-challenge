"""Layer 2 standardizer for Synthea FHIR R4 Bundles.

Synthea bronze records ARE already FHIR R4 Bundles.  Layer 2 is nearly a
passthrough — the only work is annotating each resource's meta with:

  1. ``meta.tag[]`` — source-tag (synthea) + lifecycle (standardized)
  2. ``meta.profile[]`` — USCDI canonical profile URL for known resource types

After annotation the bundle is passed through ``BundleValidator``; if errors
are found in strict mode the result is rejected.

Output: ``corpus/silver/synthea/<patient>/bundle.json``
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .base import Standardizer, StandardizeResult


class SyntheaStandardizer(Standardizer):
    """Layer 2 for Synthea: nearly-passthrough.

    Reads bronze/synthea/<patient>/data.json (FHIR R4 Bundle).
    Annotates each entry's resource with:
      - meta.tag[] adding our source-tag + lifecycle systems
      - meta.profile[] (USCDI profile by resource type)
    Validates via BundleValidator; rejects if strict mode and errors found.
    Writes silver/synthea/<patient>/bundle.json.
    """

    name = "synthea"

    # Resource type → US Core profile URL
    PROFILE_MAP: dict[str, str] = {
        "Patient":             "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
        "Condition":           "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition",
        "Observation":         "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
        "MedicationRequest":   "http://hl7.org/fhir/us/core/StructureDefinition/us-core-medicationrequest",
        "Encounter":           "http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter",
        "AllergyIntolerance":  "http://hl7.org/fhir/us/core/StructureDefinition/us-core-allergyintolerance",
        "Immunization":        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-immunization",
        "Procedure":           "http://hl7.org/fhir/us/core/StructureDefinition/us-core-procedure",
        "DiagnosticReport":    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab",
        "Organization":        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-organization",
        "Practitioner":        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitioner",
        "DocumentReference":   "http://hl7.org/fhir/us/core/StructureDefinition/us-core-documentreference",
        "CarePlan":            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-careplan",
        "Goal":                "http://hl7.org/fhir/us/core/StructureDefinition/us-core-goal",
        "CareTeam":            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-careteam",
    }

    SOURCE_TAG_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/source-tag"
    LIFECYCLE_SYSTEM  = "https://ehi-atlas.example/fhir/CodeSystem/lifecycle"

    def standardize(self, patient_id: str, *, strict: bool = False) -> StandardizeResult:
        """Read bronze bundle, annotate resources, validate, write silver.

        Idempotent: running twice on the same input produces byte-identical
        silver output because annotation is additive-and-deduplicated and
        json.dumps is called with sort_keys=True + indent=2.

        Args:
            patient_id: Human-readable patient handle (e.g. ``"rhett759"``).
            strict:     When True, validation errors raise ``ValueError``.

        Returns:
            :class:`StandardizeResult` with path, hash, errors, and warnings.

        Raises:
            FileNotFoundError: If the bronze data.json does not exist.
            ValueError:        If strict=True and the validator returns errors.
        """
        bronze_path = self.bronze_root / patient_id / "data.json"
        if not bronze_path.exists():
            raise FileNotFoundError(
                f"Bronze bundle not found: {bronze_path}. "
                f"Run 'ehi-atlas ingest --source synthea --patient {patient_id}' first."
            )

        bundle: dict = json.loads(bronze_path.read_text(encoding="utf-8"))

        # Annotate every entry's resource in-place
        for entry in bundle.get("entry", []):
            resource = entry.get("resource")
            if not isinstance(resource, dict):
                continue
            self._annotate_resource(resource)

        # Validate the annotated bundle
        from ehi_atlas.standardize.validators import BundleValidator
        messages = BundleValidator(strict=strict).validate(bundle)
        errors   = [m for m in messages if not m.startswith("warning:")]
        warnings = [m for m in messages if m.startswith("warning:")]

        if strict and errors:
            raise ValueError(
                f"Silver bundle for {self.name}/{patient_id} failed strict validation: "
                f"{errors}"
            )

        # Write silver
        silver_dir = self.silver_root / patient_id
        silver_dir.mkdir(parents=True, exist_ok=True)
        silver_path = silver_dir / "bundle.json"

        silver_text = json.dumps(bundle, indent=2, sort_keys=True)
        silver_path.write_text(silver_text, encoding="utf-8")

        sha256 = hashlib.sha256(silver_text.encode("utf-8")).hexdigest()

        return StandardizeResult(
            source=self.name,
            patient_id=patient_id,
            silver_path=str(silver_path.resolve()),
            sha256=sha256,
            validation_errors=errors,
            validation_warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _annotate_resource(self, resource: dict) -> None:
        """Mutate *resource* in-place to add required meta tags + profile."""
        meta: dict = resource.setdefault("meta", {})

        # --- meta.tag ---
        tags: list[dict] = meta.setdefault("tag", [])
        present_tag_systems = {t.get("system") for t in tags}

        if self.SOURCE_TAG_SYSTEM not in present_tag_systems:
            tags.append({"system": self.SOURCE_TAG_SYSTEM, "code": "synthea"})

        if self.LIFECYCLE_SYSTEM not in present_tag_systems:
            tags.append({"system": self.LIFECYCLE_SYSTEM, "code": "standardized"})

        # --- meta.profile ---
        resource_type: str = resource.get("resourceType", "")
        profile_url = self.PROFILE_MAP.get(resource_type)
        if profile_url is not None:
            profiles: list[str] = meta.setdefault("profile", [])
            if profile_url not in profiles:
                profiles.append(profile_url)
