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

---

## docker-compose.prod.yml

```yaml
services:
  api:
    build:
      context: .
      dockerfile: deploy/Dockerfile.api
    environment:
      - ENVIRONMENT=production
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DATA_DIR=/data
    volumes:
      - ./data:/data:ro
    restart: unless-stopped

  app:
    build:
      context: .
      dockerfile: deploy/Dockerfile.app
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    depends_on:
      - api
      - app
    restart: unless-stopped
```

---

## deploy/Dockerfile.api

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY fhir_explorer/ ./fhir_explorer/
COPY api/ ./api/
COPY data/ ./data/

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## deploy/Dockerfile.app

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY app/package*.json ./
RUN npm ci

COPY app/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx-app.conf /etc/nginx/conf.d/default.conf
```

---

## deploy/nginx.conf

```nginx
events {}

http {
    upstream api {
        server api:8000;
    }

    upstream app {
        server app:80;
    }

    server {
        listen 80;
        server_name _;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location / {
            proxy_pass http://app/;
            proxy_set_header Host $host;
        }
    }
}
```

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
nano .env  # add ANTHROPIC_API_KEY

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
