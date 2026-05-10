import pytest

from api.trust.signatures import (
    SignatureError,
    canonical_json,
    fingerprint,
    generate_keypair,
    private_key_from_b64,
    private_key_to_b64,
    public_key_from_b64,
    public_key_to_b64,
    sign_bytes,
    sign_object,
    verify_bytes,
    verify_object,
)


def test_canonical_json_sorts_keys():
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b == b'{"a":1,"b":2}'


def test_canonical_json_no_whitespace():
    out = canonical_json({"x": [1, 2, {"y": "z"}]})
    assert b" " not in out


def test_canonical_json_nfc_normalization():
    composed = "é"      # é (single codepoint)
    decomposed = "é"  # e + combining acute
    assert canonical_json({"k": composed}) == canonical_json({"k": decomposed})


def test_canonical_json_exclude_field():
    out = canonical_json({"a": 1, "b": 2, "signature": "xyz"}, exclude_field="signature")
    assert out == b'{"a":1,"b":2}'


def test_sign_and_verify_roundtrip():
    sk, pk = generate_keypair()
    payload = b"hello world"
    sig = sign_bytes(sk, payload)
    verify_bytes(pk, payload, sig)


def test_verify_bad_signature_raises():
    sk, pk = generate_keypair()
    sig = sign_bytes(sk, b"hello")
    with pytest.raises(SignatureError):
        verify_bytes(pk, b"tampered", sig)


def test_verify_malformed_signature_raises():
    _, pk = generate_keypair()
    with pytest.raises(SignatureError):
        verify_bytes(pk, b"x", "not-an-ed25519-sig")


def test_sign_object_then_tamper_breaks_verify():
    sk, pk = generate_keypair()
    obj = {"a": 1, "b": 2}
    sig = sign_object(sk, obj)
    obj["a"] = 99
    with pytest.raises(SignatureError):
        verify_object(pk, obj, sig)


def test_signature_excludes_signature_field_by_default():
    sk, pk = generate_keypair()
    obj = {"id": "trial-finder", "version": "2.4.1"}
    sig = sign_object(sk, obj)
    obj["signature"] = sig
    verify_object(pk, obj, sig)


def test_key_roundtrip_b64():
    sk, pk = generate_keypair()
    sk2 = private_key_from_b64(private_key_to_b64(sk))
    pk2 = public_key_from_b64(public_key_to_b64(pk))
    payload = b"test"
    sig = sign_bytes(sk2, payload)
    verify_bytes(pk2, payload, sig)


def test_fingerprint_stable():
    _, pk = generate_keypair()
    assert fingerprint(pk) == fingerprint(pk)
    assert fingerprint(pk).startswith("ed25519:")
