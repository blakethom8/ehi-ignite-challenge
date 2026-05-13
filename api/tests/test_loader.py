from api.core import loader


def test_bare_fhir_patient_id_resolves_to_bundle_path() -> None:
    loader._pid_to_path = None

    path = loader.path_from_patient_id("adccf2c3-9dc4-4067-ba23-98982c4875da")

    assert path is not None
    assert path.name == "Aaron697_Stiedemann542_41166989-975d-4d17-b9de-17f94cb3eec1.json"
    assert loader._pid_to_path is not None


def test_demo_profile_patient_ids_resolve_across_roots() -> None:
    """The four demo-profile personas live outside the Synthea corpus but
    must still resolve through path_from_patient_id so the aggregation
    feature can load their baseline bundles."""
    loader._pid_to_path = None

    # MIMIC patient — UUID Patient.id
    p = loader.path_from_patient_id("cb70e6ae-90b1-562b-8ab0-467c65d18d5e")
    assert p is not None and "demo-profiles/icu-mimic" in str(p)

    # mCODE Jenny M — non-UUID slug Patient.id
    p = loader.path_from_patient_id("cancer-patient-jenny-m")
    assert p is not None and "demo-profiles/oncology-breast-mcode" in str(p)

    # Coherent Brady998 — UUID Patient.id (matches filename suffix)
    p = loader.path_from_patient_id("fec6d99f-1cfd-f397-e740-e3952410ea2a")
    assert p is not None and "demo-profiles/cardiac-coherent" in str(p)

    # Synthea Ester635 — Patient.id differs from the filename's UUID suffix
    p = loader.path_from_patient_id("b0f49c80-b59b-4df6-8292-40ce8b8f8612")
    assert p is not None and "demo-profiles/polypharmacy-synthea" in str(p)
