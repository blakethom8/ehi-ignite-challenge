#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.prod.yml"

cd "$ROOT_DIR"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  COMPOSE=(docker-compose)
fi

git pull origin master

"${COMPOSE[@]}" -f "$COMPOSE_FILE" build

# Hetzner currently runs docker-compose v1.29, which can fail during in-place
# recreate with KeyError: ContainerConfig. Removing only service containers is
# safe because patient/workspace data lives in the bind-mounted ../data volume.
"${COMPOSE[@]}" -f "$COMPOSE_FILE" rm -fsv api app cursor-sidecar
"${COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --no-build

api_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' deploy_api_1)"
for _ in {1..30}; do
  if curl -fsS -H 'Host: ehi.healthcaredataai.com' "http://${api_ip}:8000/api/health" >/dev/null; then
    break
  fi
  sleep 1
done

if docker ps --format '{{.Names}}' | grep -qx 'personal-website_nginx_1'; then
  docker exec personal-website_nginx_1 nginx -s reload
fi

"${COMPOSE[@]}" -f "$COMPOSE_FILE" ps
