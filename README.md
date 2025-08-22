<img width="250" alt="infobus" src="https://github.com/user-attachments/assets/ca800913-19cc-4101-844d-91099510d91c" />

# Infobús

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
<a href="https://github.com/psf/black/blob/main/LICENSE"><img alt="License: MIT" src="https://black.readthedocs.io/en/stable/_static/license.svg"></a>

Implementación de pantallas con información en tiempo real de transporte público a partir de la especificación GTFS

## Equipo de trabajo

### Organización de la información GTFS Realtime

> "La oficina de correos"

Obtener periódicamente la información del _feed_ GTFS Realtime (el servidor del proyecto `gtfs-realtime`), ordenarla según pantallas o servicios y distribuirla.

- David Segura
- Josué Vargas

### Implementación de pantallas y despliegue de información

> "La entrega de los paquetes de correo"

Con la información asignada a cada pantalla y la plantilla para desplegar información, actualizar las pantallas cada $N$ segundos. Además, claramente, la implementación propiamente de las pantallas.

Primera implementación: soda de la Facultad de Ingeniería, porque: 1. ya existe una pantalla ahí, 2. es más fácil pedir permisos, 3. no requiere protección contra la intemperie, 4. es nuestra Facultad.

- José David Murillo
- Mateo Ortigoza
