"""
Crea usuarios de prueba con distintos roles.
Ejecutar UNA VEZ con: python seed_users.py
"""
import json
import hashlib
import os
import sys

# Evita UnicodeEncodeError en consolas Windows (cp1252) al imprimir emojis.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rutas relativas al archivo (no al cwd): así funciona desde cualquier PC
# o directorio de trabajo. Respeta DATA_DIR si el usuario lo define.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
USERS_FILE = os.path.join(DATA_DIR, "users.json")

def _hash(password: str, salt: str = "cajamarca") -> str:
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

os.makedirs(DATA_DIR, exist_ok=True)

# Usuarios a crear (no duplica los existentes)
SEED = [
    {"username": "admin",     "password": "admin123",     "role": "admin"},
    {"username": "operador",  "password": "operador123",  "role": "operador"},
    {"username": "ciudadano", "password": "ciudadano123", "role": "ciudadano"},
    {"username": "invitado",  "password": "invitado123",  "role": "invitado"},
]

existing = {}
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for row in json.load(f):
            existing[row["username"]] = row
else:
    existing = {}

users = []
for seed in SEED:
    prev = existing.get(seed["username"], {})
    users.append({
        "id": (max((u.get("id", 0) for u in users), default=0)) + 1,
        "username": seed["username"],
        "password_hash": _hash(seed["password"]),
        "role": seed["role"],
        # Campos de gamificación: se PRESERVAN al re-sembrar (no se borran
        # eco-puntos ni insignias de usuarios que ya jugaban).
        "name": prev.get("name", ""),
        "email": prev.get("email", ""),
        "eco_points": prev.get("eco_points", 0),
        "user_score": prev.get("user_score", 0),
        "active_badges": prev.get("active_badges", []),
    })

# Conserva usuarios que existan y no estén en la semilla (p. ej. invitados creados).
for username, row in existing.items():
    if username not in {s["username"] for s in SEED}:
        users.append(row)

with open(USERS_FILE, "w", encoding="utf-8") as f:
    json.dump(users, f, indent=2, ensure_ascii=False)

print("✅ Usuarios creados:")
for s in SEED:
    print(f"   • {s['username']:12s} / {s['password']:15s} → rol: {s['role']}")