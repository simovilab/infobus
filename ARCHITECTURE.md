# Infobús Architecture

`core` is a folder with the codebase for `backend`, `engine` and `scheduler`. It contains the Django project and the Celery Worker and Celery Beat apps. This way, `engine` has access to the Django models and utilities.

```mermaid
flowchart LR
    subgraph GTFS
        schedule([Schedule])
        realtime([Realtime])
    end
    subgraph Structured Data
        api([REST API])
        graphql([GraphQL API])
    end
    subgraph Real-Time Data
        ws([WebSocket])
        sse([SSE])
    end
    subgraph Contextual Data
        mcp([MCP])
        sparql([SPARQL])
    end
    subgraph Computational Services
        eta([ETA])
        tp([Trip Planning])
    end
    
    backend(("backend<br/>(Django)"))
    engine(("engine<br/>(Celery)"))
    broker(("broker<br/>(RabbitMQ)"))
    scheduler(("scheduler<br/>(Celery Beat)"))
    memory(("memory<br/>(Redis)"))
    database@{ shape: db, label: "database<br/>(PostgreSQL)" }
    context(("context<br/>(FastMCP)"))
    knowledge(("knowledge<br/>(Jena Fuseki)"))
    trips(("trips<br/>(OTP)"))

    lake@{ shape: docs, label: "Data Lake" }

    schedule --"HTTP polling"--> engine
    realtime --"HTTP polling"--> engine
    engine <-."receives commands /<br/> publishes events".-> broker
    engine <-."reads state / writes state".-> memory
    engine <-."reads / writes".-> database
    engine -."saves".-> lake
    backend <-."receives events /<br/> sends commands".-> broker
    backend <-."reads state / writes state".-> memory
    backend <-."reads / writes".-> database
    backend -."saves".-> lake
    scheduler -."schedules commands".-> broker
    backend -."queries".-> trips
    context -."queries".-> knowledge
    context -."queries".-> backend
    mcp --> context
    sparql --> knowledge
    api --> backend
    graphql --> backend
    ws --> backend
    sse --> backend
    tp --> backend
    eta --> backend
```