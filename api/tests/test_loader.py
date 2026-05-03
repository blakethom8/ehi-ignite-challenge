from api.core import loader


def test_bare_fhir_patient_id_resolves_to_bundle_path() -> None:
    loader._uuid_to_stem = None

    path = loader.path_from_patient_id("adccf2c3-9dc4-4067-ba23-98982c4875da")

    assert path is not None
    assert path.name == "Aaron697_Stiedemann542_41166989-975d-4d17-b9de-17f94cb3eec1.json"
    assert loader._uuid_to_stem is not None
