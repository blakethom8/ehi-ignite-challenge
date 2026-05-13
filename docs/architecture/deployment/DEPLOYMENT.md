# Deployment Guide

*Mirrors the provider-search deployment pattern. Last updated: May 4, 2026.*

---

## Target Environment

**Provider:** Hetzner Cloud  
**Server:** CX21 (2 vCPU, 4GB RAM, 40GB SSD) — ~€4.85/mo  
**Stack:** Docker Compose + nginx + Let's Encrypt SSL

Current production host:

- URL: `https://ehi.healthcaredataai.com`
- Server alias: `hetzner2`
- Repo path: `/opt/ehi-ignite`
- Compose file: `deploy/docker-compose.prod.yml`
- Runtime data: `/opt/ehi-ignite/data`, bind-mounted into the API container at `/app/data`
- Private converter: Microsoft FHIR Converter sidecar, reachable by the API at `http://fhir-converter:8080`
- Local dev tunnel: `ssh -L 18080:127.0.0.1:18080 hetzner2`

Deploy with:

```bash
ssh hetzner2 'cd /opt/ehi-ignite && ./deploy/deploy-prod.sh'
```

The script detects `docker compose` vs `docker-compose`. Hetzner currently
has Compose v1.29 installed, so the script removes/recreates only service
containers after build to avoid the v1 `ContainerConfig` recreate bug. Patient
profiles and uploaded files are preserved because they live in the bind-mounted
`data/` directory, not in containers. The script waits for the recreated API
container to answer `/api/health`, then reloads the outer
`personal-website_nginx_1` container so host-level nginx re-resolves the
recreated Docker service names instead of returning stale-upstream `502`s.
It also waits for the FHIR converter `/health/check` endpoint before accepting
the deployment.

---

## Deploy artifacts

All Docker / nginx configs live in [`deploy/`](../../../deploy/) and are the
source of truth. This doc deliberately links rather than inlining them so
they can't drift.

| File | Purpose |
|---|---|
| [`deploy/docker-compose.prod.yml`](../../../deploy/docker-compose.prod.yml) | Production compose — four app-owned services: `api`, `app`, `cursor-sidecar`, `fhir-converter`. Joins the external `personal-website_default` network so the host-level nginx (run by the personal-website stack) can reach the containers. |
| [`deploy/Dockerfile.api`](../../../deploy/Dockerfile.api) | Python 3.13 + uv. Copies `lib/`, `api/`, `scripts/`, and the active `ehi-atlas/ehi_atlas/` namespace + reference vocab slices. |
| [`deploy/Dockerfile.app`](../../../deploy/Dockerfile.app) | Node build → nginx-alpine static serve. Uses [`deploy/nginx-app.conf`](../../../deploy/nginx-app.conf) for SPA routing inside the app container. |
| [`deploy/Dockerfile.cursor-sidecar`](../../../deploy/Dockerfile.cursor-sidecar) | Cursor Agent sidecar — node service consumed by `api` via `CURSOR_SIDECAR_URL`. |
| [`deploy/nginx-host.conf`](../../../deploy/nginx-host.conf) | Hetzner 2 host nginx (the `personal-website_nginx_1` container that terminates TLS for `ehi.healthcaredataai.com` and proxies to `api` / `app`). Not loaded automatically — copied into place during initial server setup. |
| [`deploy/deploy-prod.sh`](../../../deploy/deploy-prod.sh) | The deploy entrypoint — handles compose v1/v2 detection, container recreation, health checks against `/api/health` and the FHIR converter, and reloads the host nginx so it re-resolves the recreated service names. |

The FHIR converter is intentionally **not** proxied by nginx. It is exposed
only on the Docker network and on Hetzner localhost port `18080` for
SSH-tunneled development (`ssh -L 18080:127.0.0.1:18080 hetzner2`).

---

## Initial Server Setup

```bash
# SSH to server
ssh root@<hetzner-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone repo
git clone https://github.com/blakethom8/ehi-ignite-challenge.git
cd ehi-ignite-challenge

# Set environment
cp .env.example .env
nano .env

# Minimum production keys in .env:
# - ANTHROPIC_API_KEY
# - EHI_SESSION_SECRET
# - GUEST_HARMONIZATION_SECRET
# - ATLAS_SIGNING_KEY
#
# Optional but recommended when you want those APIs enabled in production:
# - AUDIT_API_TOKEN
# - TRACES_API_TOKEN

# Get SSL cert
docker run --rm -v ./certbot/conf:/etc/letsencrypt \
  -v ./certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d your-domain.com

# Launch
./deploy/deploy-prod.sh
```

---

## Useful Commands

```bash
# View logs
ssh hetzner2 'cd /opt/ehi-ignite && docker-compose -f deploy/docker-compose.prod.yml logs -f api'

# Restart after deploy
ssh hetzner2 'cd /opt/ehi-ignite && ./deploy/deploy-prod.sh'

# Check status
ssh hetzner2 'cd /opt/ehi-ignite && docker-compose -f deploy/docker-compose.prod.yml ps'

# Check private converter health on Hetzner
ssh hetzner2 'curl -fsS http://127.0.0.1:18080/health/check'

# Use the Hetzner converter from local development
ssh -L 18080:127.0.0.1:18080 hetzner2
export FHIR_CONVERTER_URL=http://127.0.0.1:18080
```

---

## Local Development

```bash
# Backend
uv run uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd app && npm run dev  # runs on :5173
```

API base URL in dev: `http://localhost:8000`  
API base URL in prod: `https://your-domain.com/api`

Configure via `VITE_API_URL` env var in `app/.env.local`.

## Production env checklist

The production compose file injects some runtime config directly, but the
following secrets still need to exist in `/opt/ehi-ignite/.env` before deploy:

```bash
ANTHROPIC_API_KEY=...
EHI_SESSION_SECRET=...
GUEST_HARMONIZATION_SECRET=...
ATLAS_SIGNING_KEY=...
```

Why these matter:

- `EHI_SESSION_SECRET`: required for signed auth/demo session cookies in production
- `GUEST_HARMONIZATION_SECRET`: required for signed guest workspace cookies in production
- `ATLAS_SIGNING_KEY`: required for the plugin trust chain and signed runtime artifacts

Feature-gated production tokens:

```bash
AUDIT_API_TOKEN=...
TRACES_API_TOKEN=...
```

- `/api/audit/*` returns `503` in production until `AUDIT_API_TOKEN` is set
- `/api/traces/*` also requires `TRACES_API_ENABLED=true`; if enabled in production, it must have `TRACES_API_TOKEN`
