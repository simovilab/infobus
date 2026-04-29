---
icon: lucide/link
---

# URL Directory

The URL directory of Infobús is organized as follows:

- **subdomains**, example: `docs.[domain]`
- **paths**, example: `[domain]/sections`

## Subdomains by service

- `[domain]`: **User interface** (Nuxt at port 3000)
- `api.[domain]`: **API** (Django at port 8000)
- `mqtt.[domain]`: **MQTT broker** (NanoMQ at port TCP 1883) (_not implemented yet_)
- `docs.[domain]`: **Infobús documentation** (`self`) (Zensical at port 4000)
- `flows.[domain]`: **Data workflows** (Prefect at port 4200) (_not implemented yet_)
- `tasks.[domain]`: **Task monitoring** (Flower at port 5555) (_not implemented yet_)
- `mcp.[domain]`: **Model Context Protocol** (FastMCP at port 3278)
- `sparql.[domain]`: **SPARQL endpoint** (Apache Jena Fuseki at port 3030)
