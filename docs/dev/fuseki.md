# Optional Apache Jena Fuseki (SPARQL) backend for development

This project can optionally use Apache Jena Fuseki as a SPARQL backend for schedule queries in development and for integration tests.

When to use it
- Default reads use PostgreSQL with Redis caching.
- Fuseki is useful for experimenting with SPARQL-based data access and for the provided integration test that validates our DAL against a live SPARQL endpoint.

What the dev setup provides
- A dataset named "dataset" exposed at:
  - Query (SPARQL): http://localhost:3030/dataset/sparql
  - Graph store (read/write): http://localhost:3030/dataset/data
- A permissive shiro.ini for tests, allowing anonymous access to SPARQL query and data upload endpoints (admin endpoints are still protected).

Files in this repo
- docker/fuseki/configuration/dataset.ttl
  - Declares a Fuseki server with a single TDB2 dataset named "dataset" and the services: sparql, update, upload, data.
- docker/fuseki/shiro.ini
  - Dev/test-friendly auth rules: anon access for /dataset/sparql and /dataset/data; admin areas require auth.

Start and verify Fuseki
- Start the service:
  - docker-compose up -d fuseki
- Check logs:
  - docker-compose logs --tail=200 fuseki
- Verify readiness (expect 200):
  - GET: curl "http://localhost:3030/dataset/sparql?query=ASK%20%7B%7D"
  - POST: curl -X POST -H 'Content-Type: application/sparql-query' --data 'ASK {}' http://localhost:3030/dataset/sparql

Admin UI and credentials
- UI: http://localhost:3030/#/
- By default, our mounted shiro.ini does not define users. If you need to log in to the UI, add a user under [users] in docker/fuseki/shiro.ini, e.g.:

  [users]
  admin = admin,admin

  [roles]
  admin = *

  Then restart Fuseki: docker-compose up -d --force-recreate fuseki

Resetting the dataset
- The dataset is persisted to the fuseki_data Docker volume. To reset:
  - docker-compose stop fuseki
  - docker volume rm infobus_fuseki_data (volume name may vary; list with docker volume ls)
  - docker-compose up -d fuseki

Using Fuseki from Django (optional)
- You can force the application to use the Fuseki-backed repository by setting in .env.local:

  FUSEKI_ENABLED=true
  FUSEKI_ENDPOINT=http://fuseki:3030/dataset/sparql

- Note: the integration test overrides these settings automatically; .env.local is not required for that test.

Integration test
- The test api/tests/test_fuseki_schedule.py:
  - Waits for the SPARQL endpoint to be ready using ASK {}
  - Uploads a tiny TTL into the default graph
  - Calls /api/schedule/departures/ and asserts the enriched fields

Troubleshooting
- 404 on /dataset or /dataset/sparql
  - Ensure docker/fuseki/configuration/dataset.ttl is mounted at /fuseki/configuration and the volume fuseki_data is cleanly initialized (docker-compose down -v; docker-compose up -d fuseki).
- 405 on SPARQL POST
  - Try a GET ASK first (as above). If only GET works, your shiro.ini or services configuration may be missing update/upload permissions or the endpoint is still starting.
- Fuseki logs show "Not writable: /fuseki/configuration"
  - Make sure the /fuseki/configuration mount is writable by the container user. In dev, making the host directory writable (chmod -R 777 docker/fuseki/configuration) is acceptable.
- Random admin password printed in logs
  - That occurs when the image initializes with its own config (no mounted shiro.ini). When using our mounted shiro.ini, define users there instead, or set the image-specific admin envs and avoid mounting shiro.ini.
