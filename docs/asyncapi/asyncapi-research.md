# Investigación AsyncAPI para WebSockets GTFS

**Autor:** Brandon Trigueros Lara  
**Proyecto:** TCU - SIMOVI Lab  
**Fecha:** 19 de enero, 2026  

---

## Resumen Ejecutivo

Este documento presenta la investigación y diseño de la especificación AsyncAPI para los canales WebSocket de Infobus, específicamente para las entidades **Trip** y **Route** del estándar GTFS-Realtime.

### Entregables:
1. Especificación AsyncAPI 3.0 completa ([asyncapi-websocket-spec.yaml](asyncapi-websocket-spec.yaml))
2. Documentación de investigación (este documento)
3. Diagrama de arquitectura
4. Mapeo GTFS-Realtime → WebSocket

---

## Objetivos del Sistema

### Problema a Resolver:
Actualmente Infobus ofrece APIs REST (OpenAPI) para consultar datos GTFS estáticos y GTFS-Realtime. Sin embargo, para aplicaciones que requieren actualizaciones en tiempo real (ej: mapas de seguimiento de buses), el polling constante a las APIs REST es ineficiente:

- Latencia alta (varios segundos entre requests)
- Sobrecarga del servidor (miles de requests/segundo)
- Desperdicio de ancho de banda (datos duplicados)
- Mala experiencia de usuario (actualizaciones lentas)

### Solución: WebSockets
Los WebSockets permiten:
- Conexión persistente bidireccional
- Push de datos del servidor al cliente
- Latencia mínima (<100ms)
- Eficiencia en recursos
- Escalabilidad con Redis/Celery

---

## AsyncAPI 3.0: Conceptos Clave

### ¿Qué es AsyncAPI?
AsyncAPI es el equivalente de OpenAPI (Swagger) pero para APIs asíncronas:
- WebSockets
- MQTT
- AMQP
- Kafka
- Server-Sent Events

### Diferencias con OpenAPI (REST):

| Aspecto | OpenAPI (REST) | AsyncAPI (WebSocket) |
|---------|---------------|----------------------|
| **Paradigma** | Request-Response | Publish-Subscribe |
| **Conexión** | Stateless (nueva cada vez) | Stateful (persistente) |
| **Operaciones** | GET, POST, PUT, DELETE | Subscribe, Publish |
| **Canales** | Endpoints (/api/trips) | Channels (ws/trip/{id}) |
| **Datos** | Cliente solicita → Servidor responde | Servidor push → Cliente recibe |

### Componentes AsyncAPI:

```yaml
asyncapi: 3.0.0           # Versión de la especificación
info:                     # Metadata del API
servers:                  # Servidores WebSocket disponibles
channels:                 # Canales de comunicación (topics)
operations:               # Operaciones (subscribe/publish)
components:
  messages:               # Tipos de mensajes
  schemas:                # Estructuras de datos (payloads)
  securitySchemes:        # Autenticación
```

---

## GTFS-Realtime: Análisis de Entidades

### Entidades Principales:

#### 1. **Trip Update** (Actualización de Viaje)
- **Descripción:** Estado actualizado de un viaje programado
- **Datos:**
  - `trip_id`, `route_id`, `direction_id`
  - Horarios de llegada/salida en paradas
  - Retrasos/adelantos
  - Cancelaciones
- **Frecuencia:** ~30 segundos por viaje
- **Uso:** Apps de horarios, ETA (tiempo estimado de llegada)

#### 2. **Vehicle Position** (Posición de Vehículo)
- **Descripción:** Ubicación GPS actual del vehículo
- **Datos:**
  - Latitud, longitud, bearing, velocidad
  - Trip/Route asociados
  - Parada actual
  - Nivel de congestión
  - Ocupación (crowding)
- **Frecuencia:** ~5-10 segundos por vehículo
- **Uso:** Mapas en tiempo real, tracking

#### 3. **Service Alert** (Alerta de Servicio)
- **Descripción:** Notificaciones sobre interrupciones
- **Datos:**
  - Causa (construcción, accidente, clima)
  - Efecto (desvío, cancelación, retraso)
  - Entidades afectadas (rutas, viajes, paradas)
  - Período de actividad
- **Frecuencia:** On-demand (cuando ocurre evento)
- **Uso:** Notificaciones push, alertas en UI

---

## Arquitectura WebSocket Propuesta

### Diagrama de Canales:

```
WebSocket Server (wss://infobus.ucr.ac.cr)
│
├── /ws/trip/{trip_id}
│   ├── → TripUpdate messages
│   ├── → VehiclePosition messages
│   └── → Alert messages (si afecta al trip)
│
├── /ws/route/{route_id}
│   ├── → RouteVehicles messages (todos los vehículos)
│   └── → Alert messages (si afecta a la ruta)
│
└── /ws/route/{route_id}/direction/{direction_id}
    ├── → RouteVehicles messages (filtrado por dirección)
    └── → Alert messages
```

### Flujo de Datos:

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│ GPS Device  │────────▶│ GTFS-RT Feed │────────▶│ Databús API │
└─────────────┘         └──────────────┘         └─────────────┘
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │ Celery Task │
                                                  │ (Processor) │
                                                  └─────────────┘
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │ Redis Pub/  │◀─┐
                                                  │ Sub Channel │  │
                                                  └─────────────┘  │
                                                         │         │
                                                         ▼         │
┌─────────────┐         ┌──────────────┐         ┌─────────────┐ │
│ Web Client  │◀────────│ Django       │◀────────│ Channels    │─┘
│ (Browser)   │         │ Channels     │         │ Layer       │
└─────────────┘         │ Consumer     │         │ (Redis)     │
                        └──────────────┘         └─────────────┘
```

### Componentes:

1. **GTFS-RT Feed**: Fuente de datos en tiempo real
2. **Celery Task**: Procesa y normaliza datos
3. **Redis Pub/Sub**: Broadcasting a múltiples consumers
4. **Django Channels Consumer**: Maneja conexiones WebSocket
5. **Channels Layer**: Distribuye mensajes entre workers

---

## Mapeo GTFS-Realtime → AsyncAPI

### Tabla de Correspondencia:

| GTFS-RT Entity | AsyncAPI Message | WebSocket Channel | Frecuencia |
|----------------|------------------|-------------------|------------|
| `TripUpdate` | `TripUpdate` | `ws/trip/{trip_id}` | ~30s |
| `VehiclePosition` | `VehiclePosition` | `ws/trip/{trip_id}` | ~10s |
| `VehiclePosition` (multiple) | `RouteVehicles` | `ws/route/{route_id}` | ~10s |
| `Alert` | `Alert` | Todos los canales afectados | On-demand |

### Payload Examples:

#### TripUpdate Message:
```json
{
  "type": "trip_update",
  "timestamp": "2026-01-19T10:30:00-06:00",
  "trip": {
    "trip_id": "TRIP_001",
    "route_id": "ROUTE_001",
    "direction_id": 0
  },
  "vehicle": {
    "id": "BUS_123",
    "label": "Unidad 123"
  },
  "stop_time_updates": [
    {
      "stop_sequence": 5,
      "stop_id": "STOP_001",
      "arrival": {
        "delay": 120,
        "time": "2026-01-19T10:32:00-06:00"
      }
    }
  ]
}
```

#### RouteVehicles Message:
```json
{
  "type": "route_vehicles",
  "timestamp": "2026-01-19T10:30:00-06:00",
  "route_id": "ROUTE_001",
  "direction_id": 0,
  "vehicles": [
    {
      "vehicle_id": "BUS_123",
      "trip_id": "TRIP_001",
      "position": {
        "latitude": 9.9355,
        "longitude": -84.0783,
        "bearing": 45.5
      },
      "current_stop_sequence": 5,
      "delay": 120
    }
  ]
}
```

---

## Decisiones de Diseño

### 1. Canales Separados por Entidad
**Decisión:** Crear canales separados para `trip` y `route`  
**Razón:**
- Permite a clientes suscribirse solo a lo que necesitan
- Reduce tráfico de red innecesario
- Mejor performance (menos mensajes por conexión)

**Alternativa rechazada:** Canal único `/ws/gtfs` con filtros
- Todos los clientes recibirían todos los mensajes
- Filtrado en cliente (ineficiente)

### 2. Parámetros en URL vs Query String
**Decisión:** `ws/trip/{trip_id}` (path parameters)  
**Razón:**
- Más semántico y RESTful
- Compatible con routing de Django Channels
- Mejor caché y debugging

**Alternativa rechazada:** `ws/subscribe?trip_id=123`
- Menos intuitivo
- Más complejo de enrutar

### 3. Formato de Mensajes: JSON vs Protocol Buffers
**Decisión:** JSON (por ahora)  
**Razón:**
- Fácil de debuggear
- Compatible con cualquier cliente
- No requiere compilación

**Futuro:** Migrar a Protocol Buffers para producción
- Menor tamaño (~40% reducción)
- Mayor velocidad de serialización
- Requiere generación de código cliente

### 4. Dirección como Sub-canal vs Query Param
**Decisión:** Ofrecer ambos:
- `ws/route/{route_id}` → Todas las direcciones
- `ws/route/{route_id}/direction/{direction_id}` → Solo una dirección
- `ws/route/{route_id}?direction_id=0` → Query parameter (opcional)

**Razón:** Flexibilidad para diferentes use cases

---

## Herramientas y Tecnologías

### AsyncAPI Ecosystem:

1. **AsyncAPI Studio** (Editor Visual)
   - URL: https://studio.asyncapi.com/
   - Valida sintaxis en tiempo real
   - Preview de documentación

2. **AsyncAPI Generator** (Generador de Código)
   ```bash
   npm install -g @asyncapi/generator
   asyncapi generate fromTemplate asyncapi-websocket-spec.yaml @asyncapi/html-template -o docs/
   ```
   - Genera documentación HTML/Markdown
   - Genera código cliente (JavaScript, Python, Java, etc.)

3. **AsyncAPI CLI**
   ```bash
   npm install -g @asyncapi/cli
   asyncapi validate asyncapi-websocket-spec.yaml
   ```

### Django Channels Stack:

1. **channels** (Core)
   - WebSocket support para Django
   - ASGI application server
   
2. **channels-redis** (Layer)
   - Redis como backend de channel layer
   - Permite comunicación entre workers

3. **daphne** (ASGI Server)
   - Servidor ASGI production-ready
   - Maneja WebSocket y HTTP

4. **django-channels** (Integración)
   - Routing de WebSocket
   - Consumers (equivalente a Views)

---

## Casos de Uso

### Use Case 1: App de Tracking en Tiempo Real
**Cliente:** App móvil que muestra buses en mapa

**Conexiones:**
```javascript
// Suscribirse a ruta completa
const ws = new WebSocket('wss://infobus.ucr.ac.cr/ws/route/ROUTE_001');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'route_vehicles') {
    // Actualizar marcadores en mapa
    updateMapMarkers(data.vehicles);
  }
};
```

**Beneficios:**
- Actualizaciones cada 5-10s automáticamente
- No polling
- Múltiples vehículos en un solo stream

---

### Use Case 2: Pantalla de Llegadas en Parada
**Cliente:** Display en parada de bus

**Conexiones:**
```javascript
// Suscribirse a 3 trips que pasan por esta parada
const trips = ['TRIP_001', 'TRIP_002', 'TRIP_003'];
const connections = trips.map(id => 
  new WebSocket(`wss://infobus.ucr.ac.cr/ws/trip/${id}`)
);

connections.forEach(ws => {
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'trip_update') {
      // Actualizar ETA en pantalla
      updateArrivalTime(data.trip.trip_id, data.stop_time_updates);
    }
  };
});
```

**Beneficios:**
- ETAs actualizadas automáticamente
- Muestra retrasos en tiempo real
- Múltiples rutas simultáneas

---

### Use Case 3: Sistema de Alertas
**Cliente:** App de notificaciones

**Conexión:**
```javascript
const ws = new WebSocket('wss://infobus.ucr.ac.cr/ws/route/ROUTE_001');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'alert' && data.severity_level === 'SEVERE') {
    // Mostrar notificación push
    showNotification(data.header_text, data.description_text);
  }
};
```

**Beneficios:**
- Alertas instantáneas (no esperar polling)
- Filtrado por severidad
- Push notifications nativas

---

## Seguridad y Autenticación

### Fase 1: Sin Autenticación (MVP)
- WebSocket público
- Rate limiting por IP
- Firewall básico

### Fase 2: API Key (Futuro)
```yaml
securitySchemes:
  apiKey:
    type: httpApiKey
    name: X-API-Key
    in: header
```

**Flujo:**
```
Cliente → Conecta con header: X-API-Key: abc123
Servidor → Valida key en database
Servidor → Acepta/Rechaza conexión
```

### Fase 3: OAuth2/JWT (Producción)
- OAuth2 authorization flow
- JWT token en header o query string
- Refresh token automático

---

## Performance y Escalabilidad

### Estimaciones:

**Escenario:** 1000 usuarios concurrentes en app móvil

| Métrica | Estimación |
|---------|-----------|
| Conexiones simultáneas | 1,000 WS connections |
| Mensajes/segundo | ~2,000 msg/s (2 msg/s/user) |
| Ancho de banda | ~500 KB/s (~500 bytes/msg) |
| Memoria Redis | ~100 MB (channel layer buffer) |
| CPU Django Workers | ~30% (4 workers) |

**Bottlenecks:**
1. Redis Pub/Sub (max ~50k msg/s por instancia)
2. Network I/O (limitado por NIC)
3. Django worker pool (max connections)

**Soluciones:**
- Redis Cluster (sharding por route_id)
- Load balancer (múltiples servers ASGI)
- Connection pooling y keepalive
- Compression (gzip para payloads >1KB)

---

## Plan de Testing

### Unit Tests:
```python
from channels.testing import WebsocketCommunicator

async def test_trip_consumer():
    communicator = WebsocketCommunicator(
        TripConsumer.as_asgi(),
        "/ws/trip/TRIP_001/"
    )
    connected, _ = await communicator.connect()
    assert connected
    
    # Simular broadcast
    await channel_layer.group_send(
        "trip_TRIP_001",
        {"type": "trip_update", "data": {...}}
    )
    
    response = await communicator.receive_json_from()
    assert response["type"] == "trip_update"
```

### Integration Tests:
- Conectar cliente real WebSocket
- Simular datos GTFS-RT
- Verificar recepción de mensajes
- Medir latencia end-to-end

### Load Tests:
```bash
# Usar websocket-bench
npm install -g websocket-bench
ws-bench -c 1000 -m 100 wss://infobus.ucr.ac.cr/ws/route/ROUTE_001
```

---

## Referencias

### Especificaciones:
- [AsyncAPI 3.0 Specification](https://www.asyncapi.com/docs/reference/specification/v3.0.0)
- [GTFS-Realtime Reference](https://gtfs.org/realtime/reference/)
- [WebSocket Protocol RFC 6455](https://datatracker.ietf.org/doc/html/rfc6455)

### Django Channels:
- [Channels Documentation](https://channels.readthedocs.io/)
- [Channels Tutorial](https://channels.readthedocs.io/en/stable/tutorial/)
- [ASGI Specification](https://asgi.readthedocs.io/)

### Tools:
- [AsyncAPI Studio](https://studio.asyncapi.com/)
- [AsyncAPI Generator](https://github.com/asyncapi/generator)
- [Postman WebSocket Testing](https://www.postman.com/features/websocket-client/)

---

## Conclusiones

1. **AsyncAPI 3.0 es ideal** para documentar APIs WebSocket de forma estándar
2. **Separación de canales** (trip/route) proporciona mejor UX y performance
3. **GTFS-Realtime** mapea naturalmente a mensajes WebSocket
4. **Django Channels + Redis** es stack probado para Python
5. **MVP sin autenticación** permite validar funcionalidad rápidamente

---

## Próximos Pasos

1. Especificación AsyncAPI completada
2. Validar spec con AsyncAPI CLI
3. ⏳ Generar documentación HTML
4. ⏳ Implementar TripConsumer y RouteConsumer
5. ⏳ Setup Redis channel layer
6. ⏳ Crear cliente de prueba HTML/JS
7. ⏳ Integrar con Celery tasks existentes
8. ⏳ Deploy en staging
9. ⏳ Load testing
10. ⏳ Documentación de uso

---
