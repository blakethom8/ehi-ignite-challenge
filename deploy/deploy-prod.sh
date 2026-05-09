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

"${COMPOSE[@]}" -f "$COMPOSE_FILE" pull fhir-converter || true
"${COMPOSE[@]}" -f "$COMPOSE_FILE" build

# Hetzner currently runs docker-compose v1.29, which can fail during in-place
# recreate with KeyError: ContainerConfig. Removing only service containers is
# safe because patient/workspace data lives in the bind-mounted ../data volume.
"${COMPOSE[@]}" -f "$COMPOSE_FILE" rm -fsv api app cursor-sidecar fhir-converter
"${COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --no-build

converter_ready=0
for _ in {1..90}; do
  converter_container="$("${COMPOSE[@]}" -f "$COMPOSE_FILE" ps -q fhir-converter 2>/dev/null || true)"
  converter_ip=""
  if [[ -n "$converter_container" ]]; then
    converter_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$converter_container" 2>/dev/null || true)"
  fi
  if [[ -n "$converter_ip" ]] && curl -fsS "http://${converter_ip}:8080/health/check" >/dev/null 2>&1; then
    converter_ready=1
    break
  fi
  sleep 1
done

if [[ "$converter_ready" != "1" ]]; then
  echo "FHIR converter did not become healthy after deploy." >&2
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs --tail=120 fhir-converter >&2 || true
  exit 1
fi

api_ready=0
for _ in {1..90}; do
  api_container="$("${COMPOSE[@]}" -f "$COMPOSE_FILE" ps -q api 2>/dev/null || true)"
  api_ip=""
  if [[ -n "$api_container" ]]; then
    api_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$api_container" 2>/dev/null || true)"
  fi
  if [[ -n "$api_ip" ]] && curl -fsS -H 'Host: ehi.healthcaredataai.com' "http://${api_ip}:8000/api/health" >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 1
done

if [[ "$api_ready" != "1" ]]; then
  echo "API did not become healthy after deploy." >&2
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs --tail=120 api >&2 || true
  exit 1
fi

if docker ps --format '{{.Names}}' | grep -qx 'personal-website_nginx_1'; then
  docker exec personal-website_nginx_1 nginx -s reload
fi

"${COMPOSE[@]}" -f "$COMPOSE_FILE" ps
