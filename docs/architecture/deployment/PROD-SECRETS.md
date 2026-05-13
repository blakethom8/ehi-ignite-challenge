# Production Secrets Runbook

> Last updated 2026-05-12 (H0.12). This is the operational runbook for setting up and rotating the secrets the API requires when `ENVIRONMENT=production`. Pair with `docs/architecture/deployment/DEPLOYMENT.md` for the broader deploy procedure.

H0.2 made several env vars **strictly required in production**: missing values raise at boot rather than silently materializing keys on disk in the data bind mount. This doc explains what each one is, how to generate it, and what fails if it's wrong.

---

## TL;DR — required env vars in production

| Env var | Purpose | Fails at | Generation command |
|---|---|---|---|
| `ENVIRONMENT` | Selects strict prod paths | n/a — must be `production` | n/a, set literal |
| `ATLAS_SIGNING_KEY` | Root of plugin trust chain (signs anchors + provenance) | `atlas_keypair()` first call | `python -c "from api.trust.signatures import generate_keypair, private_key_to_b64; sk, _ = generate_keypair(); print(private_key_to_b64(sk))"` |
| `EHI_SESSION_SECRET` | HMAC key for session cookies | `_session_secret()` first call | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `GUEST_HARMONIZATION_SECRET` | HMAC key for guest harmonization session cookies | `_guest_secret()` first call | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ANTHROPIC_API_KEY` | LLM access for context + agent-SDK + cursor sidecar | First Claude call (per-request) | Issued by Anthropic console |
| `AUDIT_API_TOKEN` | Bearer for `/api/audit/users/{id}` | First admin call | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `TRACES_API_TOKEN` | Bearer for `/api/traces/*` (only if `TRACES_API_ENABLED=true`) | First trace API call | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CURSOR_INTERNAL_TOOL_SECRET` | Bearer for `/internal/cursor-tools/*` | First sidecar tool call | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ALLOWED_HOSTS` | TrustedHost middleware allowlist | First request | n/a — comma-separated host list |
| `CORS_ALLOWED_ORIGINS` | CORS allowlist | First browser request | n/a — comma-separated origin list |

### Strongly recommended (not enforced today)

| Env var | Purpose | Notes |
|---|---|---|
| `EHI_AUTH_BOOTSTRAP_PASSWORD` | First-admin password for the auto-seeded user at boot. If unset in prod, no bootstrap user is seeded. | Set once during initial deploy, then unset. |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Optional LLM trace export. Off by default. | Required only if you want Langfuse mirroring. |
| `EVENTS_REDACTION_PRESET` | Default `events-strict`. Set to `minimal` only in dev. | H0.8 — see "PII redaction in audit log" below. |
| `EVENTS_RETENTION_DAYS` | Default 90 (H0.13). Set to 0 to disable purge in tests. | Only matters once events.db has volume. |
| `TRACING_ENABLED` | Default true in `deploy/docker-compose.prod.yml`. | Disable only with cause; you lose all per-user audit visibility. |
| `TRACING_SAMPLE_RATE` | Default 1.0. Lower (e.g. 0.2) once volume justifies dropping. | Per-user audit accuracy degrades proportionally. |

---

## Generating the trust-chain key

The Atlas signing key is an Ed25519 private key encoded as URL-safe base64. It signs every anchor package and every provenance row. Compromise = forged vendor manifests, so this one rotates rarely and lives only in your secrets store (1Password / Vault / Hetzner secrets — not in `data/`).

```bash
# Generate. Round-trips through the same code that loads the key at boot,
# so if this snippet succeeds, the value will load successfully.
python -c "
from api.trust.signatures import generate_keypair, private_key_to_b64, private_key_from_b64
sk, _ = generate_keypair()
b64 = private_key_to_b64(sk)
# Round-trip check — fails loudly if the key is malformed.
assert private_key_from_b64(b64).private_bytes_raw() == sk.private_bytes_raw()
print(b64)
"
```

Set in your secrets store, then export at boot:

```bash
export ATLAS_SIGNING_KEY="$(read_from_secrets atlas-signing-key)"
```

In `deploy/docker-compose.prod.yml`, source from a `.env` file that is **never committed** and lives only on the production host. Existing convention: `env_file: ../.env`.

### Validating before deploy

```bash
ENVIRONMENT=production ATLAS_SIGNING_KEY="$YOUR_KEY" \
  python -c "from api.trust.keys import atlas_keypair; sk, pk = atlas_keypair(reset=True); print('ok, public fp:', pk.public_bytes_raw().hex()[:16])"
```

If `ATLAS_SIGNING_KEY` is missing or malformed, you'll see:

```
RuntimeError: ATLAS_SIGNING_KEY env var is required when ENVIRONMENT=production. Refusing to fall back to data/atlas-signing.key — the Atlas signing key is the root of the plugin trust chain and must not live as a plaintext file on disk in production.
```

Same shape for `EHI_SESSION_SECRET`.

---

## Rotation

### Atlas signing key

Hot rotation is **not yet supported** (the verifier holds a single public key in memory; multi-key federation is the v2 plan). Until then, rotation requires:

1. Generate a new key (snippet above).
2. Stop the API.
3. Replace `ATLAS_SIGNING_KEY` in your secrets store.
4. Boot the API. New anchors + provenance rows will be signed by the new key.
5. Old provenance rows fail `verify_record()` after rotation. Treat them as historical-only and re-sign on next read if needed.

If you must rotate live, plan a coordinated cutover with downtime. **Do not** ship a rotation while the production server is serving real plugin runs.

### Session secret

Safer to rotate. Replace `EHI_SESSION_SECRET` and restart — every existing session cookie becomes invalid (users sign in again). No backfill needed.

### Audit + traces tokens

Pure bearer tokens — replace and restart. Operators using `/learn/audit` will need the new value.

---

## What each missing var fails at

| Missing | Behavior | Where |
|---|---|---|
| `ENVIRONMENT=production` | Silently falls back to dev paths (file fallbacks, `/docs` exposed, etc.) | `api/main.py:45` and many call sites |
| `ATLAS_SIGNING_KEY` | `RuntimeError` on first plugin run start | `api/trust/keys.py:_load_or_create_atlas_key` |
| `EHI_SESSION_SECRET` | `RuntimeError` on first session cookie sign/verify | `api/core/auth.py:_session_secret` |
| `GUEST_HARMONIZATION_SECRET` | `RuntimeError` on first guest-harmonization cookie sign/verify | `api/core/guest_harmonization.py:_guest_secret` |
| `ANTHROPIC_API_KEY` | `RuntimeError` on first context/agent-SDK call | `api/core/provider_assistant_context.py`, `_agent_sdk.py` |
| `AUDIT_API_TOKEN` | `503` from `/api/audit/users/*` (with explanation) | `api/routers/audit.py:_assert_authorized` |
| `TRACES_API_TOKEN` | `503` from `/api/traces/*` (only if `TRACES_API_ENABLED=true`) | `api/routers/traces.py` |
| `CURSOR_INTERNAL_TOOL_SECRET` | `401` from `/internal/cursor-tools/*` | `api/routers/cursor_internal_tools.py` |
| `ALLOWED_HOSTS` | Default allows `ehi.healthcaredataai.com` only — set explicitly if you change the domain | `api/main.py` |
| `CORS_ALLOWED_ORIGINS` | Default allows the production origin only — set explicitly for additional fronts | `api/main.py` |

---

## Pre-deploy checklist

Run from the production host before flipping traffic over:

```bash
# 1. All required env vars are set + non-empty.
for v in ENVIRONMENT ATLAS_SIGNING_KEY EHI_SESSION_SECRET ANTHROPIC_API_KEY \
         AUDIT_API_TOKEN ALLOWED_HOSTS CORS_ALLOWED_ORIGINS; do
  if [ -z "${!v}" ]; then echo "MISSING: $v"; exit 1; fi
done && echo "all required envs present"

# 2. ENVIRONMENT is the literal "production" (not "prod").
[ "$ENVIRONMENT" = "production" ] && echo "ENVIRONMENT=production ok"

# 3. ATLAS_SIGNING_KEY round-trips.
python -c "from api.trust.keys import atlas_keypair; atlas_keypair(reset=True); print('atlas key loads ok')"

# 4. EHI_SESSION_SECRET round-trips.
python -c "from api.core.auth import _session_secret; print('session secret length:', len(_session_secret()))"

# 5. No plaintext key files left over from a dev-mode boot.
for f in data/atlas-signing.key data/atlas-session.key data/atlas-guest-harmonization.key; do
  [ -f "$f" ] && echo "WARN: $f exists on prod host — delete it"
done
```

If step 5 finds anything, delete it and verify the env var path still works. The `data/` bind mount is a backup hazard.

---

## Known gaps tracked elsewhere

- ~~`atlas-guest-harmonization.key` — same plaintext fallback as the two H0.2 closed.~~ **Closed in H0.14** — production now requires `GUEST_HARMONIZATION_SECRET` env (mirrors the H0.2 pattern).
- Per-org key federation — v2 in `api/trust/keys.py`. Tracked in `BACKEND-REPORT-2026-05-11.html` BR#13.
- WORM provenance storage — moves provenance off SQLite onto S3 + object lock. Tracked in `api/plugins/provenance.py:1`.
