# Métricas de aplicación

Esta es una lista de las métricas implementadas con el [cliente de Python](https://prometheus.github.io/client_python/) de Prometheus para monitorear la aplicación del sistema, específicamente los datos de GTFS de transporte público, junto con cualquier otra variable de interés, como datos del tiempo, tráfico, etc.

Consideraciones:

- Utilizamos las [recomendaciones de nomenclatura](https://prometheus.io/docs/practices/naming/) de Prometheus.

## Datos GTFS

- Todas las métricas derivadas de datos GTFS tienen la raíz `gtfs_`
- La descripción y las opciones vienen, preferentemente y si existen, directamente de la [especificación de GTFS Realtime](https://gtfs.org/documentation/realtime/reference/), en inglés.
- Otras métricas creadas deben ser consistentes con los modelos del proyecto.

### Entidad `VehiclePositions`

#### `gtfs_trips_in_progress`

> Runs in progress.

```python title="feed/tasks.py: def get_vehicle_positions"

from prometheus_client import Gauge

g = Gauge(
    "gtfs_trips_in_progress",
    "Runs in progress",
    ["route_id", "direction_id", "trip_id"],
)

# Example
g.set_function(lambda: len(entities))

```

#### `gtfs_occupancy_status`

> The state of passenger occupancy for the vehicle or carriage.

```python title="feed/tasks.py: def get_vehicle_positions"
from prometheus_client import Enum

e = Enum(
    "gtfs_occupancy_status",
    "The state of passenger occupancy for the vehicle or carriage.",
    states=[
        "EMPTY",
        "MANY_SEATS_AVAILABLE",
        "FEW_SEATS_AVAILABLE",
        "STANDING_ROOM_ONLY",
        "CRUSHED_STANDING_ROOM_ONLY",
        "FULL",
        "NOT_ACCEPTING_PASSENGERS",
    ],
)

# Example
e.state("MANY_SEATS_AVAILABLE")

```

### Entidad `TripUpdates`

### Entidad `Alerts`

## Datos externos

### Datos climáticos