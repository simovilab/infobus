# Descripción del servidor de aplicaciones para pantallas con información GTFS Realtime

## Tareas esenciales del servidor

1. Periódicamente recopilar los `FeedMessage` de GTFS Realtime (este es el servidor "hermano" `gtfs-realtime`).
2. Organizar la información contenida para cada pantalla, según sea relevante (ejemplo: clasificar los viajes que van a pasar por esa parada (asumiendo que las pantallas están en o cerca de una parada), o anuncios de alertas que sean relevantes para el servicio en esa pantalla, etc.).
3. (Opcional) Cargar la plantilla HTML en el navegador de la pantalla cuando se carga el sitio por primera vez (ejemplo: al prender las pantallas).
4. Actualizar la información desplegada en las pantallas utilizando los WebSockets de Django.

## Aplicaciones y sitios del proyecto de Django

### Django app: `website`

> Manejo de páginas misceláneas del sitio.

- `/`: Página de bienvenida del sistema
- `/sobre/`: Información del proyecto
- `/perfil/`: Perfil de usuario registrado

#### Modelos asociados

- `class User`: Información de usuarios del sistema
  - `type`

### Django app: `alerts`

> Páginas de administración de las pantallas (HTML) y actualización de datos en tiempo real (WebSockets)

- `/pantallas/`: Lista de pantallas del sistema
- `/pantallas/crear/`: Página de creación de nueva pantalla
- `/pantallas/<screen_id>/`: Visualización de la pantalla (**contenido de la pantalla**)
- `/pantallas/<screen_id>/configuracion/`: Sitio de configuración de la pantalla `screen_id`


Nota: las pantallas por ahora asumimos que son Raspberry Pi en [modo kiosko](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/) que utilizan [Chromium](https://www.chromium.org/chromium-projects/) para navegar el sitio.

#### Modelos asociados

- `class Screen`: Información de cada pantalla
  - `screen_id`
  - `name`
  - `address`
  - `location` (ejemplo: 9.93752787687643, -84.04463400265841 con PostGIS y GeoDjango)
  - `size` (ejemplo: 32")
  - `ratio` (ejemplo: 16:9)
  - `orientation` (ejemplo: `VERTICAL`, `HORIZONTAL`)
  - `has_sound` (ejemplo: `True`, `False`, booleano)

### Django app: `gtfs`

## Estrategia de almacenamiento y capa de acceso a datos (DAL)

- PostgreSQL/PostGIS es la fuente de verdad para GTFS Schedule.
- Redis se utiliza como caché de alto desempeño (lecturas read-through/write-through donde aplique) y para mensajería (Channels, Celery).
- Fuseki (Jena) es un backend opcional para consultas SPARQL. Se controla con variables de entorno:
  - FUSEKI_ENABLED (bool)
  - FUSEKI_ENDPOINT (URL)

Se define una capa de acceso a datos (DAL) con interfaces claras:
- ScheduleRepository: obtiene salidas programadas (next departures) por parada.
- CacheProvider: wrapper de caché (implementación en Redis).

Implementaciones actuales:
- PostgresScheduleRepository (Django ORM)
- CachedScheduleRepository (envoltorio con Redis)
- FusekiScheduleRepository (backend opcional habilitable por entorno; utilizado en desarrollo y tests de integración)

Endpoint nuevo (ejemplo):
- GET /api/schedule/departures/?stop_id=STOP_123&limit=5

### Capa de caché (Redis)
- Claves (key):
  - schedule:next_departures:feed={FEED_ID}:stop={STOP_ID}:date={YYYY-MM-DD}:time={HHMMSS}:limit={N}:v1
- TTL por defecto: 60 segundos
- Configuración por entorno: SCHEDULE_CACHE_TTL_SECONDS (entero)

> Páginas de administación de información GTFS Schedule y GTFS Realtime.

- `/gtfs/`:
- `/gtfs/schedule/`: Información y configuración del *feed* GTFS Schedule utilizado
- `/gtfs/realtime/`: Información y configuración del *feed* GTFS Realtime utilizado
- `/gtfs/company/`: Las pantallas pueden desplegar información de uno o más *feeds* provenientes de una o más compañías

 #### Modelos asociados
 
- (Todos los modelos de GTFS Schedule, como `Agency`, `Route`, etc.)
- (Todos los modelos de GTFS Realtime, como `VehiclePosition`, etc.)
- `class Company`
  - `company_id`
  - `name`
  - `address`
  - `phone`
  - `email`
  - `website`
  - `logo`
- `class Schedule`
  - `company_id` (ejemplo: "MBTA")
  - `schedule_url`: *feed* estático
  - `last_updated`
- `class Realtime`
  - `company_id` (ForeignKey) (ejemplo: "MBTA")
  - `alerts_url`: *feed message* de alertas del servicio
  - `trip_updates_url`: *feed message* de actualizaciones de los viajes
  - `vehicle_positions_url`: *feed message* de posición de los vehículos
  - `alerts_last_updated`
