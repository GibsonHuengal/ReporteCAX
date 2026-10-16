# Ciudad Inteligente · Cajamarca

Repositorio: [GitHub](https://github.com/GibsonHuengal/ReporteCAX)

Aplicación web (Flask) para **reportar problemas urbanos** en Cajamarca: basura,
daños estructurales, riesgos, etc. Incluye **clasificación de imágenes con IA
local**, **mapa de calor**, **geofencing**, **votos comunitarios** y un sistema de
**gamificación** (eco-puntos, insignias y jornadas de limpieza).

> Este proyecto es la **versión refactorizada** (arquitectura por capas, principios
> SOLID). Para la comparativa existe la carpeta [`version_antigua/`](version_antigua/)
> con la misma funcionalidad en **un solo archivo** (código monolítico).

---

## 1. Requisitos

- **Python 3.10 o superior** ([descarga](https://www.python.org/downloads/)).
  En Windows, marca la casilla **"Add python.exe to PATH"** durante la instalación.
- Conexión a internet **solo la primera vez** (para instalar las dependencias).

No necesitas instalar Flask ni nada más a mano: el script de arranque lo hace todo.

---

## 2. Cómo ejecutar (cualquier PC)

El script **crea el entorno virtual, instala dependencias, genera los usuarios de
prueba y arranca el servidor**.

### Windows (doble clic)

Haz doble clic en:

```
iniciar.bat
```

### Windows (PowerShell)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\iniciar.ps1
```

### Linux / macOS

```bash
chmod +x iniciar.sh
./iniciar.sh
```

Cuando aparezca este mensaje, abre el navegador en
**[http://127.0.0.1:5000](http://127.0.0.1:5000)** :

```
[4/4] Iniciando servidor en http://127.0.0.1:5000
```

Para detener el servidor: `Ctrl + C`.

### Usuarios de prueba

| Usuario     | Contraseña     | Rol        |
|-------------|----------------|------------|
| `admin`     | `admin123`     | admin      |
| `operador`  | `operador123`  | operador   |
| `ciudadano` | `ciudadano123` | ciudadano  |
| `invitado`  | `invitado123`  | invitado   |

> Solo `admin` y `operador` pueden cambiar el estado de un reporte.

## Publicar en Render

El archivo `render.yaml` configura un servicio web con Gunicorn y genera una
`SECRET_KEY` privada automáticamente. Para publicarlo, sube este repositorio a
GitHub, crea un **Blueprint Instance** en Render conectado al repositorio
`GibsonHuengal/ReporteCAX` y aplica el Blueprint detectado. Render mostrará la
URL pública al terminar.

En la instancia publicada, cada usuario debe registrarse desde la pantalla de
inicio; no se crean las cuentas de prueba con permisos de administrador. El plan
gratuito usa almacenamiento temporal: usuarios, reportes y fotos pueden perderse
cuando Render reinicie o vuelva a desplegar la aplicación. No uses esta demo
para datos reales ni sensibles.

---

## 3. ¿Cómo funciona?

### Flujo principal

1. El ciudadano inicia sesión y entra al **mapa**.
2. Rellena el formulario y (opcional) **adjunta una foto**. El navegador la envía
   a `/api/classify`, donde un **clasificador local** (Pillow + NumPy) decide entre
   `Basura Detectada`, `Daño Estructural` o `No Concluyente`.
3. Al enviar (`/api/reports`), la foto se guarda en `static/uploads/` y el reporte
   se persiste en `data/reports.json`.
4. El mapa pinta los reportes con **severidad por color**, permite **agrupar**
   (clustering), ver el **mapa de calor** (heatmap) y activar **"Mi zona"**
   (geofencing por radio de 3 km).
5. Otros usuarios pueden **votar** (`/api/reports/<id>/upvote`) y el autor gana
   **eco-puntos**. Las acciones desbloquean **insignias**.
6. En **Misiones**, la comunidad crea jornadas de limpieza asociadas a reportes y
   se inscribe; al completarlas todos los participantes ganan puntos.

### Arquitectura (principios SOLID)

```
routes/        → HTTP (traducen peticiones, no tienen reglas de negocio)
services/      → reglas de negocio (ReportService, Gamification, Community, ...)
repositories/  → persistencia (JSON) detrás de CONTRATOS (ABC)
models/        → entidades del dominio (Report, User, CleanupMission)
utils/         → utilidades puras (geo: haversine, bounding box)
config.py      → TODA la configuración (nada "hardcoded")
app.py         → Application Factory + Composition Root (cablea todo)
```

- **S (SRP):** cada módulo tiene una única responsabilidad.
- **O (OCP):** los clasificadores (texto/imagen) son intercambiables sin tocar el resto.
- **L / I (LSP/ISP):** contratos pequeños y específicos por repositorio.
- **D (DIP):** los servicios dependen de **abstracciones**, no de implementaciones.
  Cambiar JSON → SQL/Firestore solo se toca en `app.py` (Composition Root).

### ¿Dónde se guardan los datos?

| Qué                | Dónde                        |
|--------------------|------------------------------|
| Usuarios           | `data/users.json`            |
| Reportes           | `data/reports.json`          |
| Misiones           | `data/missions.json`         |
| Fotos subidas      | `static/uploads/`            |

Todo se genera automáticamente. Puedes borrar `data/` y `static/uploads/` y
volver a ejecutar el script para empezar de cero.

---

## 4. Endpoints (API)

| Método | Ruta                              | Descripción |
|--------|-----------------------------------|-------------|
| POST   | `/api/reports`                    | Crea reporte (multipart: foto opcional) |
| GET    | `/api/reports?lat&lng&radius`     | Lista reportes (o los cercanos → geofencing) |
| POST   | `/api/reports/<id>/upvote`        | Voto comunitario (+2 pts al autor) |
| POST   | `/api/reports/<id>/status`        | Cambia estado (solo admin/operador) |
| GET    | `/api/summary`                    | Zona crítica, conteos y predicción |
| GET    | `/api/heatmap`                    | Puntos del mapa de calor |
| POST   | `/api/classify`                   | Inferencia IA sobre una imagen |
| GET    | `/api/profile` / `/api/leaderboard` | Perfil y ranking comunitario |
| GET/POST | `/api/missions`                 | Lista / crea misiones de limpieza |
| POST   | `/api/missions/<id>/join`         | Unirse a una misión |
| POST   | `/api/missions/<id>/complete`     | Completar misión |

---

## 5. Configuración opcional (variables de entorno)

Crea un archivo `.env` (o define variables) si quieres cambiar valores. Ejemplos:

| Variable               | Por defecto            | Descripción |
|------------------------|------------------------|-------------|
| `SECRET_KEY`           | `cambia-esto-...`      | Clave de sesión (¡cámbiala en producción!) |
| `HOST` / `PORT`        | `127.0.0.1` / `5000`   | Dirección y puerto del servidor |
| `DATA_DIR`             | `./data`               | Carpeta de datos JSON |
| `UPLOAD_DIR`           | `./static/uploads`     | Carpeta de imágenes (debe estar dentro de `static/`) |
| `AI_MIN_CONFIDENCE`    | `0.55`                 | Umbral de confianza de la IA |
| `GEOFENCE_RADIUS_KM`   | `3.0`                  | Radio de "Mi zona" en km |

Para exponerlo en tu red local: `HOST=0.0.0.0` y luego entra desde otro
dispositivo a `http://TU_IP:5000`.

---

## 6. Ejecución manual (opcional)

Si prefieres hacerlo a mano:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe seed_users.py
.venv\Scripts\python.exe app.py
# Linux/macOS:
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python seed_users.py
.venv/bin/python app.py
```

---

## 7. Comparativa: versión antigua vs. refactorizada

- [`version_antigua/`](version_antigua/) → **código monolítico**: rutas, lógica de
  negocio, persistencia e IA **todo en un solo archivo** (`app.py`), sin capas ni
  inyección de dependencias.
- **Raíz del proyecto** (`app.py` + `services/` + `repositories/` + `models/`) →
  **arquitectura por capas** con SOLID.

Ambas versiones tienen **la misma funcionalidad y la misma interfaz** (se pueden
comparar función a función, endpoint a endpoint). Para arrancar la versión antigua:

```
version_antigua\iniciar.bat        (Windows)
version_antigua/iniciar.sh         (Linux/macOS)
```

---

## 8. Estructura del proyecto

```
ReporteCAX/
├── app.py                  # Factory + Composition Root
├── config.py               # Configuración centralizada
├── seed_users.py           # Usuarios de prueba
├── requirements.txt        # Dependencias
├── iniciar.bat / .ps1 / .sh# Scripts de arranque
├── .gitignore
├── models/                 # Report, User, CleanupMission
├── repositories/           # Contratos (ABC) + implementación JSON
├── services/               # Reglas de negocio (report, IA, gamificación, ...)
├── routes/                 # Blueprints HTTP (auth, main, community)
├── utils/geo.py            # Haversine / bounding box
├── templates/              # Vistas (Jinja2)
├── static/                 # CSS, JS, y uploads/ (fotos)
├── data/                   # Persistencia JSON (se genera)
└── version_antigua/        # Versión monolítica (para comparar)
```
