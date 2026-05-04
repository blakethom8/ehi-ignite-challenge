"""Layer 2 silver-tier FHIR Bundle validators.

Sits at the bronze → silver boundary. Adapters / standardize code call
``BundleValidator.validate()`` after producing a silver FHIR R4 Bundle dict
before writing it to ``corpus/silver/``. An empty return list means the bundle
is structurally valid FHIR R4, declares recognized profiles, and carries the
required EHI Atlas meta tags and Extensions.

Three layers of checks:
1. Structural  — valid FHIR R4 via ``fhir.resources`` Pydantic models.
2. Profile     — every ``resource.meta.profile[]`` URL is in KNOWN_PROFILES.
3. Provenance  — required meta.tag systems present; extracted resources carry
                 the three required extraction Extensions.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# EHI Atlas custom Extension URLs (from PROVENANCE-SPEC.md)
# ---------------------------------------------------------------------------
_EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition/"

EXTRACTION_MODEL_URL = f"{_EXT_BASE}extraction-model"
EXTRACTION_CONFIDENCE_URL = f"{_EXT_BASE}extraction-confidence"
SOURCE_ATTACHMENT_URL = f"{_EXT_BASE}source-attachment"
SOURCE_LOCATOR_URL = f"{_EXT_BASE}source-locator"
QUALITY_SCORE_URL = f"{_EXT_BASE}quality-score"
CONFLICT_PAIR_URL = f"{_EXT_BASE}conflict-pair"
MERGE_RATIONALE_URL = f"{_EXT_BASE}merge-rationale"
UMLS_CUI_URL = f"{_EXT_BASE}umls-cui"
EXTRACTION_PROMPT_VERSION_URL = f"{_EXT_BASE}extraction-prompt-version"

# Lifecycle tag value that requires the three extraction Extensions
_LIFECYCLE_EXTRACTED = "extracted"

# Tag system URIs (from PROVENANCE-SPEC.md)
_SOURCE_TAG_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/source-tag"
_LIFECYCLE_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/lifecycle"


class BundleValidator:
    """Validates a silver-tier FHIR Bundle.

    Performs three layers of checks:

    1. Structural: valid FHIR R4 (parses as Bundle, all entries are valid FHIR
       resources).
    2. Profile: declared profiles are recognized; resources appear conformant.
    3. Provenance: required ``meta.tag`` entries present; Extension URLs we
       mint are present where expected (e.g. resources with
       ``lifecycle=extracted`` must carry extraction-model,
       extraction-confidence, source-attachment).

    Returns a list of validation error strings; an empty list means valid.

    Args:
        strict: When ``True``, an unknown profile URL is an *error*. When
            ``False`` (default) it is a *warning* prefixed with ``"warning:"``
            and does not block the pipeline.
    """

    # --- Known USCDI / CARIN BB profile URLs --------------------------------
    # US Core 6.x (the USCDI v3 ballot)
    KNOWN_PROFILES: frozenset[str] = frozenset(
        {
            # US Core core resources
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition-encounter-diagnosis",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition-problems-health-concerns",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-medicationrequest",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-procedure",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-immunization",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-allergyintolerance",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-note",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-documentreference",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-organization",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitioner",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitionerrole",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-goal",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-careteam",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-careplan",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-location",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-medication",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-clinical-result",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-screening-assessment",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-provenance",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-relatedperson",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-servicerequest",
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-specimen",
            # CARIN Blue Button (claims/payer)
            "http://hl7.org/fhir/us/carin-bb/StructureDefinition/C4BB-ExplanationOfBenefit",
            "http://hl7.org/fhir/us/carin-bb/StructureDefinition/C4BB-Coverage",
            "http://hl7.org/fhir/us/carin-bb/StructureDefinition/C4BB-Patient",
            "http://hl7.org/fhir/us/carin-bb/StructureDefinition/C4BB-Organization",
            "http://hl7.org/fhir/us/carin-bb/StructureDefinition/C4BB-Practitioner",
        }
    )

    # Required meta.tag systems for every silver-tier resource entry
    REQUIRED_META_TAG_SYSTEMS: tuple[str, ...] = (
        _SOURCE_TAG_SYSTEM,
        _LIFECYCLE_SYSTEM,
    )

    # Extensions required on a resource whose lifecycle tag is "extracted"
    REQUIRED_EXTRACTION_EXTENSION_URLS: frozenset[str] = frozenset(
        {
            EXTRACTION_MODEL_URL,
            EXTRACTION_CONFIDENCE_URL,
            SOURCE_ATTACHMENT_URL,
        }
    )

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def validate(self, bundle: dict) -> list[str]:
        """Validate a silver-tier FHIR Bundle dict.

        Args:
            bundle: A dict representing a FHIR R4 Bundle (as you would get
                from ``json.loads()`` of a silver file).

        Returns:
            A list of human-readable error strings. An empty list means the
            bundle passed all checks. Strings prefixed with ``"warning:"``
            are non-fatal advisory messages (only emitted when
            ``strict=False``).
        """
        errors: list[str] = []

        # ------------------------------------------------------------------
        # 1. Structural check via fhir.resources
        # ------------------------------------------------------------------
        try:
            from fhir.resources.bundle import Bundle  # lazy import

            validated = Bundle.model_validate(bundle)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"structural: {exc}")
            # If structurally broken, downstream checks are noise — bail out.
            return errors

        # ------------------------------------------------------------------
        # 2 & 3. Walk every entry for profile + provenance checks
        # ------------------------------------------------------------------
        entries = validated.entry or []
        for entry in entries:
            resource = entry.resource
            if resource is None:
                # BundleEntry without a resource (link-only entry) is OK per
                # the FHIR spec, so we skip rather than error.
                continue
            resource_label = _resource_label(resource)
            errors.extend(self._check_resource(resource, resource_label))

        return errors

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _check_resource(self, resource: object, label: str) -> list[str]:
        """Run profile + provenance checks on a single resource."""
        errors: list[str] = []
        meta = getattr(resource, "meta", None)

        # -- 2. Profile check ------------------------------------------------
        errors.extend(self._check_profiles(meta, label))

        # -- 3. Provenance tag check -----------------------------------------
        errors.extend(self._check_meta_tags(meta, label))

        # -- 3b. Extraction extension check (lifecycle=extracted) -----------
        errors.extend(self._check_extraction_extensions(meta, label))

        return errors

    def _check_profiles(self, meta: object | None, label: str) -> list[str]:
        """Flag unknown profile URLs."""
        errors: list[str] = []
        if meta is None:
            return errors
        profiles: list[str] = getattr(meta, "profile", None) or []
        for profile_url in profiles:
            if profile_url not in self.KNOWN_PROFILES:
                msg = (
                    f"{label} meta.profile contains unknown URL: {profile_url}"
                )
                if self.strict:
                    errors.append(msg)
                else:
                    errors.append(f"warning: {msg}")
        return errors

    def _check_meta_tags(self, meta: object | None, label: str) -> list[str]:
        """Check that required meta.tag systems are present."""
        errors: list[str] = []
        if meta is None:
            for system in self.REQUIRED_META_TAG_SYSTEMS:
                errors.append(
                    f"{label} meta.tag missing required system: {system}"
                    " (meta is absent)"
                )
            return errors

        tags = getattr(meta, "tag", None) or []
        present_systems = {t.system for t in tags if t.system}
        for required_system in self.REQUIRED_META_TAG_SYSTEMS:
            if required_system not in present_systems:
                errors.append(
                    f"{label} meta.tag missing required system: {required_system}"
                )
        return errors

    def _check_extraction_extensions(
        self, meta: object | None, label: str
    ) -> list[str]:
        """Resources claiming lifecycle=extracted must carry the three
        extraction Extensions: extraction-model, extraction-confidence,
        source-attachment."""
        errors: list[str] = []
        if meta is None:
            return errors

        # Find lifecycle tag value
        tags = getattr(meta, "tag", None) or []
        lifecycle_value: str | None = None
        for tag in tags:
            if tag.system == _LIFECYCLE_SYSTEM:
                lifecycle_value = tag.code
                break

        if lifecycle_value != _LIFECYCLE_EXTRACTED:
            return errors

        # This resource claims lifecycle=extracted — check Extensions
        extensions = getattr(meta, "extension", None) or []
        present_urls = {ext.url for ext in extensions if ext.url}

        for required_url in self.REQUIRED_EXTRACTION_EXTENSION_URLS:
            if required_url not in present_urls:
                ext_name = required_url.split("/")[-1]
                errors.append(
                    f"{label} lifecycle=extracted but missing Extension: "
                    f"{ext_name} ({required_url})"
                )
        return errors


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


def validate_bundle(bundle: dict, strict: bool = False) -> list[str]:
    """Convenience wrapper around ``BundleValidator.validate()``.

    Args:
        bundle: FHIR R4 Bundle as a plain dict.
        strict: If ``True``, unknown profiles are errors; otherwise warnings.

    Returns:
        List of error/warning strings; empty means valid.
    """
    return BundleValidator(strict=strict).validate(bundle)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resource_label(resource: object) -> str:
    """Return a human-readable ``ResourceType/id`` label for error messages."""
    rtype = getattr(resource, "__resource_type__", "UnknownResource")
    rid = getattr(resource, "id", None)
    return f"{rtype}/{rid}" if rid else rtype
