# Microsoft FHIR Converter Deployment

Status: implementation slice, 2026-05-09

## Decision

Run Microsoft's FHIR Converter preview container as a private sidecar service on the Hetzner host.

The converter is not a public web service. It is reachable in two ways:

1. The production FastAPI container calls it over the private Docker network.
2. Local development can reach it through an SSH tunnel to a localhost-only host binding.

```text
Mac dev API
  -> SSH tunnel
  -> Hetzner 127.0.0.1:18080
  -> fhir-converter container

Production API
  -> http://fhir-converter:8080
  -> fhir-converter container
```

## Compose Service

The service lives in `deploy/docker-compose.prod.yml`:

```yaml
fhir-converter:
  image: mcr.microsoft.com/healthcareapis/fhir-converter:1.0.0-preview@sha256:202c898d9807015a2b6269d3a6fe581cfaecc247ac163cd53d3e69e9cfc3659f
  ports:
    - "127.0.0.1:18080:8080"
  expose:
    - "8080"
```

The localhost-only port supports SSH tunneling without exposing the converter publicly. The API uses Docker DNS:

```bash
FHIR_CONVERTER_URL=http://fhir-converter:8080
FHIR_CONVERTER_API_VERSION=2024-05-01-preview
FHIR_CONVERTER_REQUIRED=true
FHIR_CONVERTER_TIMEOUT_SECONDS=45
```

## Local Development

Open a tunnel:

```bash
ssh -L 18080:127.0.0.1:18080 hetzner2
```

Then run the local API with:

```bash
export FHIR_CONVERTER_URL=http://127.0.0.1:18080
export FHIR_CONVERTER_API_VERSION=2024-05-01-preview
export FHIR_CONVERTER_REQUIRED=true
```

Smoke test the tunnel with the PHI-free fixture in:

```bash
FHIR_CONVERTER_URL=http://127.0.0.1:18080 deploy/smoke-fhir-converter.sh
```

## Internal Playground

The internal UI at `/ccda-lab` uploads a C-CDA XML or PDF and returns the emitted FHIR Bundle, resource counts, sample resources, and bundle-shape metrics.

Back-end endpoints:

```http
GET /api/internal/ccda-lab/processors
POST /api/internal/ccda-lab/convert
```

The C-CDA processors are:

- `ccda-microsoft` — requires the configured Microsoft converter.
- `ccda-auto` — uses Microsoft when available, otherwise falls back.
- `ccda-fallback` — uses the limited local parser.

PDF processors are loaded from the existing `lib.extract.pipelines` registry.

## Security Posture

- Do not add an nginx route to the converter.
- Do not bind the converter to `0.0.0.0`.
- Keep C-CDA XML out of application logs, converter logs, and error responses.
- Keep the converter image pinned to a specific digest. Do not run an unpinned `latest`.
- Use request timeouts and container CPU/memory limits.
- Treat Microsoft default templates as a starting point, not a clinically validated final mapping.
- Keep the original C-CDA as source evidence and require harmonization identity checks before facts merge into a patient workspace.

## Operations

Deployment script behavior:

1. Pulls the converter image.
2. Recreates the converter alongside `api`, `app`, and `cursor-sidecar`.
3. Waits for `/health/check` before accepting the deployment.
4. Reloads nginx after the API is healthy.

Useful commands on Hetzner:

```bash
cd /opt/ehi-ignite
docker compose -f deploy/docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:18080/health/check
FHIR_CONVERTER_URL=http://127.0.0.1:18080 deploy/smoke-fhir-converter.sh
```

## References

- Microsoft FHIR-Converter: https://github.com/microsoft/FHIR-Converter
- Microsoft converter API guide: https://raw.githubusercontent.com/microsoft/FHIR-Converter/main/docs/how-to-guides/use-convert-web-apis.md
- Microsoft container image: https://hub.docker.com/r/microsoft/healthcareapis-fhir-converter
