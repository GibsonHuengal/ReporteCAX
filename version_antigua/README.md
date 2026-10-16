# Versión antigua (código monolítico) — para comparar

Esta carpeta contiene la **misma aplicación** que la raíz del proyecto, pero
escrita como **un único archivo** (`app.py`): configuración, acceso a datos,
reglas de negocio, IA y rutas **todo mezclado**.

El objetivo es tener una **evidencia "antes vs. después"** de la refactorización
aplicada en la raíz del proyecto (principios SOLID).

---

## Cómo ejecutar

```text
Windows (doble clic)  ->  iniciar.bat
Windows (PowerShell)  ->  .\iniciar.ps1
Linux / macOS         ->  ./iniciar.sh
Manual                ->  python app.py
```

El servidor arranca en **http://127.0.0.1:5001** (puerto 5001 para poder
ejecutarla a la vez que la versión refactorizada, que usa el 5000).

Usuarios de prueba (los mismos que la versión nueva):
`admin/admin123`, `operador/operador123`, `ciudadano/ciudadano123`,
`invitado/invitado123`.

---

## ¿Qué la hace "antigua" (sin SOLID)?

| Aspecto | Versión antigua (esta carpeta) | Versión refactorizada (raíz) |
|---|---|---|
| **Organización** | Todo en `app.py` (~800 líneas) | `models/`, `repositories/`, `services/`, `routes/` |
| **SRP** | Una sola clase/archivo con N responsabilidades | Cada módulo tiene una responsabilidad |
| **OCP** | Añadir un clasificador = editar las rutas | Se inyecta una nueva implementación sin tocar el resto |
| **DIP** | Rutas leen/escriben JSON directamente | Rutas → servicios → repositorios (contratos ABC) |
| **Configuración** | Constantes "hardcoded" en el archivo | Centralizada en `config.py` (+ variables de entorno) |
| **Testabilidad** | Hay que arrancar Flask para probar algo | Servicios testeables sin servidor |
| **Plantillas** | URLs escritas "a mano" (`/login`, `/profile`) | Generadas con `url_for(...)` |

---

## Lo que SÍ es igual

Para que la comparación sea **justa**, ambas versiones:

- Tienen **exactamente la misma interfaz** (mismos HTML, CSS y JS).
- Exponen **los mismos endpoints** y devuelven **las mismas respuestas JSON**.
- Usan la **misma IA local**, la misma geolocalización, el mismo heatmap y el
  mismo sistema de eco-puntos e insignias.

La diferencia es **cómo está organizado el código**, no lo que hace.

---

## Estructura

```
version_antigua/
├── app.py              # TODO el backend en un solo archivo
├── seed_users.py       # Usuarios de prueba
├── requirements.txt    # Dependencias (idénticas)
├── iniciar.bat / .ps1 / .sh
├── templates/          # Vistas (mismas que la versión nueva)
├── static/             # CSS y JS (idénticos)
└── data/               # Persistencia JSON (se genera)
```
