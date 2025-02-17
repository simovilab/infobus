# Métricas de aplicación

Esta es una lista de las métricas implementadas con el [cliente de Python](https://prometheus.github.io/client_python/) de Prometheus para monitorear la aplicación del sistema, específicamente, los datos de GTFS de transporte público junto con cualquier otra variables de interés, como datos del tiempo, etc.

Consideraciones:

- Utilizamos las [recomendaciones de nomenclatura](https://prometheus.io/docs/practices/naming/) de Prometheus
- Todas las métricas derivadas de datos GTFS tienen la raíz `gtfs_`
- La descripción, preferentemente, viene directamente de la [especificación de GTFS Realtime](https://gtfs.org/documentation/realtime/reference/) y en inglés.

## Datos GTFS

### Entidad `VehiclePositions`

#### `gtfs_trips_in_progress`

- Gráfica: 
- En `feed/tasks.py : def get_vehicle_positions`


#### `gtfs_occupancy_status`

> The state of passenger occupancy for the vehicle or carriage.

```python
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
e.state("MANY_SEATS_AVAILABLE")

```

### Entidad `TripUpdates`

### Entidad `Alerts`

## Datos externos

### Datos climáticos