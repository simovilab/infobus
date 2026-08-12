# Deployment and Operations

## Public services

Production traffic is routed by Traefik to service-specific hosts configured through environment variables.

| Environment variable | Documented host | Service | Internal port |
| --- | --- | --- | ---: |
| `UI_DOMAIN` | `infobus.simovilab.com` | Nuxt user interface | 3000 |
| `ORCHESTRATOR_DOMAIN` | `api.infobus.simovilab.com` | Django/Daphne orchestrator | 8000 |
| `DOCS_DOMAIN` | `docs.infobus.simovilab.com` | Nginx documentation server | 80 |
| `CONTEXT_DOMAIN` | `mcp.infobus.simovilab.com` | FastMCP context service | 3278 |
| `KNOWLEDGE_DOMAIN` | `sparql.infobus.simovilab.com` | Apache Jena Fuseki | 3030 |

Sources: `.env.example:47-53`; `compose.prod.yml:52-57,204-209,231-236,252-257,283-288`.
