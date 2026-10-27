# Deployment and Operations

## Public services

Production traffic is routed by Traefik to service-specific hosts configured through environment variables.

| Environment variable  | Documented host           | Service                    | Internal port |
| --------------------- | ------------------------- | -------------------------- | ------------: |
| `UI_DOMAIN`           | `infobus.simovi.org`      | Nuxt user interface        |          3000 |
| `ORCHESTRATOR_DOMAIN` | `api.infobus.simovi.org`  | Django/Daphne orchestrator |          8000 |
| `LAKE_DOMAIN`         | `lake.infobus.simovi.org` | MinIO S3-compatible API    |          9000 |

FastMCP, Fuseki, and the documentation site are deployed separately. The
MinIO console remains internal; only its S3-compatible API is routed publicly.
