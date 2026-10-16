"""
================================================================================
 VERSIÓN ANTIGUA  ·  Ciudad Inteligente - Cajamarca          (código monolítico)
================================================================================
 Este archivo es la versión "ANTES de refactorizar": TODA la aplicación vive
 aquí. Es funcionalmente idéntica a la versión de la carpeta raíz, pero NO
 aplica los principios SOLID.

 Sirve como EVIDENCIA / PUNTO DE COMPARACIÓN para el curso.

 ------------------------------------------------------------------------------
 VIOLACIONES INTENCIONALES (lo que la versión refactorizada corrige)
 ------------------------------------------------------------------------------
   1. SRP (Responsabilidad Única):
      Este archivo hace de TODO a la vez: configuración, acceso a datos,
      reglas de negocio, IA, gamificación y rutas HTTP.

   2. OCP (Abierto/Cerrado):
      La IA y el clasificador de texto están HARDCODEADOS dentro de las rutas.
      Añadir un nuevo clasificador obliga a MODIFICAR este archivo.

   3. DIP (Inversión de Dependencias):
      No hay abstracciones ni inyección de dependencias. Las rutas leen y
      escriben ficheros JSON directamente.

   4. Gestión de la configuración:
      Los parámetros (rutas, umbrales, puntos) son CONSTANTES "hardcoded",
      no vienen de config.py ni de variables de entorno.

   5. Testabilidad:
      No se puede probar la lógica sin arrancar Flask (todo está acoplado).

 ------------------------------------------------------------------------------
 PARA EJECUTAR:
   Windows        ->  iniciar.bat   (o  .\\iniciar.ps1)
   Linux / macOS  ->  ./iniciar.sh
   Manual         ->  python app.py     (después de instalar requirements.txt)
================================================================================
"""
import hashlib
import hmac
import io
import json
import math
import os
import re
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image, UnidentifiedImageError
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for,
)

# ============================================================================
# 1. CONFIGURACIÓN "HARDCODED"  (en la versión refactorizada vive en config.py)
# ============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REPORTS_FILE = os.path.join(DATA_DIR, "reports.json")
MISSIONS_FILE = os.path.join(DATA_DIR, "missions.json")

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
UPLOAD_URL = "/static/uploads"

SECRET_KEY = "cambia-esto-en-produccion"
DEFAULT_LAT = -7.1638
DEFAULT_LNG = -78.5008
GEOFENCE_RADIUS_KM = 3.0
AI_MIN_CONFIDENCE = 0.55
CRITICAL_ZONE_THRESHOLD = 5
PREDICTION_WINDOW_DAYS = 7

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
SEVERITY_SCORE = {"bajo": 1, "intermedio": 2, "critico": 3}
VALID_STATUSES = {"PENDIENTE", "EN_PROCESO", "RESUELTO"}
VALID_GROUPS = {"BASURA", "INFRAESTRUCTURA", "RIESGO", "OTRO"}
CATEGORY_GROUPS = {
    "bache": "INFRAESTRUCTURA",
    "alumbrado": "INFRAESTRUCTURA",
    "fuga": "INFRAESTRUCTURA",
    "basura": "BASURA",
    "seguridad": "RIESGO",
    "otro": "OTRO",
}
STATUS_ROLES = {"admin", "operador"}

# Gamificación (en la versión refactorizada va a config.py / servicio propio)
ECO_POINTS = {
    "create_report": 10,
    "upvote_received": 2,
    "report_in_process": 5,
    "report_resolved": 25,
    "mission_join": 15,
    "mission_complete": 40,
}

# Umbrales de insignias (todo mezclado en este archivo)
BADGES = [
    ("primer_reporte", "Primer Reporte", "Enviaste tu primer reporte urbano.",
     lambda s: s.get("reports_created", 0) >= 1),
    ("reportero_activo", "Reportero Activo", "5 reportes enviados.",
     lambda s: s.get("reports_created", 0) >= 5),
    ("voz_de_barrio", "Voz de Barrio", "10 votos recibidos en tus reportes.",
     lambda s: s.get("upvotes_received", 0) >= 10),
    ("resolutor", "Resolutor", "Un reporte tuyo fue marcado como resuelto.",
     lambda s: s.get("reports_resolved", 0) >= 1),
    ("ecoguardian", "Ecoguardian", "500 eco-puntos acumulados.",
     lambda s: s.get("eco_points", 0) >= 500),
    ("voluntario", "Voluntario Verde", "Te uniste a una jornada de limpieza.",
     lambda s: s.get("missions_joined", 0) >= 1),
    ("heroe_comunitario", "Héroe Comunitario", "Completaste una jornada de limpieza.",
     lambda s: s.get("missions_completed", 0) >= 1),
]
BADGES_BY_ID = {b[0]: b for b in BADGES}

_lock = threading.Lock()


# ============================================================================
# 2. PERSISTENCIA (antes: acceso directo a JSON; en la versión refactorizada:
#    repositorios detrás de contratos ABC).
# ============================================================================
def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _init_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for path in (USERS_FILE, REPORTS_FILE, MISSIONS_FILE):
        if not os.path.exists(path):
            _write_json(path, [])


# ============================================================================
# 3. AUTENTICACIÓN (hash directo aquí; en la versión refactorizada: AuthService)
# ============================================================================
def _hash_password(password, salt="cajamarca"):
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def find_user(username):
    for row in _read_json(USERS_FILE):
        if row.get("username") == username:
            return row
    return None


def authenticate(username, password):
    user = find_user(username)
    if not user:
        return None
    if hmac.compare_digest(user.get("password_hash", ""), _hash_password(password)):
        return user
    return None


def register_user(username, password):
    if not re.match(r"^[A-Za-z0-9_.-]{3,32}$", username or ""):
        raise ValueError("El usuario debe tener 3-32 caracteres alfanuméricos.")
    if len(password or "") < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    with _lock:
        users = _read_json(USERS_FILE)
        if any(u.get("username") == username for u in users):
            raise ValueError("El usuario ya existe.")
        user = {
            "id": (max((u.get("id", 0) for u in users), default=0)) + 1,
            "username": username,
            "password_hash": _hash_password(password),
            "role": "ciudadano",
            "name": "",
            "email": "",
            "eco_points": 0,
            "user_score": 0,
            "active_badges": [],
        }
        users.append(user)
        _write_json(USERS_FILE, users)
    return user


def save_user(user):
    with _lock:
        users = _read_json(USERS_FILE)
        for i, row in enumerate(users):
            if row.get("id") == user.get("id"):
                users[i] = user
                break
        else:
            users.append(user)
        _write_json(USERS_FILE, users)


def all_users():
    return _read_json(USERS_FILE)


# ============================================================================
# 4. CLASIFICADOR DE TEXTO  (hardcodeado → viola OCP)
# ============================================================================
KEYWORD_RULES = {
    "bache": ["bache", "hueco", "pavimento", "pista rota", "calle rota", "vereda"],
    "alumbrado": ["luz", "alumbrado", "poste", "lámpara", "lampara"],
    "basura": ["basura", "desecho", "residuo", "contenedor", "botadero"],
    "fuga": ["fuga", "agua", "tubería", "tuberia", "alcantarilla"],
    "seguridad": ["robo", "inseguridad", "delincuencia", "peligro"],
}


def classify_text(text):
    text = (text or "").lower()
    for category, keys in KEYWORD_RULES.items():
        if any(k in text for k in keys):
            return category
    return "otro"


# ============================================================================
# 5. IA DE IMÁGENES  (heurística local, hardcodeada → viola OCP)
#    Equivalente a la clase HeuristicImageClassifier de la versión refactorizada.
# ============================================================================
LABEL_TO_GROUP = {
    "Basura Detectada": "BASURA",
    "Daño Estructural": "INFRAESTRUCTURA",
    "No Concluyente": "OTRO",
}
AI_LABEL_TO_CATEGORY = {
    "Basura Detectada": ("basura", "BASURA"),
    "Daño Estructural": ("bache", "INFRAESTRUCTURA"),
}
IMG_SIZE = 96


def classify_image(image_bytes):
    """Devuelve el mismo dict que ClassificationResult.to_dict()."""
    try:
        feats = _extract_features(image_bytes)
    except (UnidentifiedImageError, OSError, ValueError, Exception):
        return {
            "label": "No Concluyente", "confidence": 0.0, "group": "OTRO",
            "scores": {"trash": 0.0, "structural": 0.0},
            "features": {"error": "Imagen ilegible o formato no soportado."},
        }

    trash, structural = _score_features(feats)
    if max(trash, structural) < AI_MIN_CONFIDENCE:
        label, confidence = "No Concluyente", round(max(trash, structural), 3)
    elif trash >= structural:
        label, confidence = "Basura Detectada", round(trash, 3)
    else:
        label, confidence = "Daño Estructural", round(structural, 3)

    return {
        "label": label,
        "confidence": confidence,
        "group": LABEL_TO_GROUP.get(label, "OTRO"),
        "scores": {"trash": round(trash, 3), "structural": round(structural, 3)},
        "features": feats,
    }


def _extract_features(image_bytes):
    if not image_bytes:
        raise ValueError("Imagen vacía.")
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx, mn = arr.max(axis=2), arr.min(axis=2)
    sat = mx - mn
    val = mx
    gray = arr.mean(axis=2)
    total = float(IMG_SIZE * IMG_SIZE)

    green_mask = (g > r * 1.08) & (g > b * 1.08) & (sat > 0.12)
    brown_mask = (r > g) & (g >= b) & (sat > 0.10) & (val < 0.85) & (r < 0.95)
    gray_mask = sat < 0.10

    green_frac = float(green_mask.sum()) / total
    brown_frac = float(brown_mask.sum()) / total
    gray_frac = float(gray_mask.sum()) / total

    gx = np.abs(np.diff(gray, axis=1)).mean()
    gy = np.abs(np.diff(gray, axis=0)).mean()
    edge = float((gx + gy) / 2.0)
    texture = float(gray.std())

    hist, _ = np.histogram(gray, bins=16, range=(0.0, 1.0), density=True)
    color_variety = float(np.count_nonzero(hist)) / 16.0

    return {
        "green_frac": round(green_frac, 4),
        "brown_frac": round(brown_frac, 4),
        "gray_frac": round(gray_frac, 4),
        "edge_density": round(edge, 4),
        "texture": round(texture, 4),
        "saturation_mean": round(float(sat.mean()), 4),
        "brightness_mean": round(float(val.mean()), 4),
        "color_variety": round(color_variety, 4),
    }


def _score_features(f):
    edge_n = min(f["edge_density"] / 0.18, 1.0)
    texture_n = min(f["texture"] / 0.30, 1.0)
    trash = (
        0.85 * min(f["green_frac"] * 3.0, 1.0)
        + 0.85 * min(f["brown_frac"] * 3.0, 1.0)
        + 0.55 * edge_n
        + 0.45 * texture_n
        + 0.30 * f["color_variety"]
    ) / 3.0
    structural = (
        1.30 * min(f["gray_frac"] * 1.6, 1.0)
        + 0.90 * edge_n
        + 0.40 * texture_n
        - 0.35 * min(f["saturation_mean"] * 2.0, 1.0)
    ) / 3.0
    return max(trash, 0.0), max(structural, 0.0)


def save_uploaded_image(file_storage):
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return None
    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato de imagen no permitido (usa PNG, JPG, WEBP).")
    name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, name))
    return f"{UPLOAD_URL}/{name}"


# ============================================================================
# 6. GEOGRAFÍA (en la versión refactorizada vive en utils/geo.py)
# ============================================================================
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lng1, lat2, lng2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat, lng, radius_km):
    lat_delta = radius_km / 111.32
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lng_delta = radius_km / (111.32 * cos_lat)
    return (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta)


# ============================================================================
# 7. REPORTES (persistencia + reglas, todo mezclado aquí)
# ============================================================================
def list_reports():
    return _read_json(REPORTS_FILE)


def get_report(report_id):
    for row in _read_json(REPORTS_FILE):
        if row.get("id") == report_id:
            return row
    return None


def add_report(report):
    with _lock:
        reports = _read_json(REPORTS_FILE)
        report["id"] = (max((r.get("id", 0) for r in reports), default=0)) + 1
        reports.append(report)
        _write_json(REPORTS_FILE, reports)
    return report


def update_report(report):
    with _lock:
        reports = _read_json(REPORTS_FILE)
        for i, row in enumerate(reports):
            if row.get("id") == report.get("id"):
                reports[i] = report
                break
        else:
            reports.append(report)
        _write_json(REPORTS_FILE, reports)
    return report


def upvote_report(report_id):
    with _lock:
        reports = _read_json(REPORTS_FILE)
        updated = None
        for row in reports:
            if row.get("id") == report_id:
                row["upvotes"] = int(row.get("upvotes", 0) or 0) + 1
                updated = row
                break
        if updated is not None:
            _write_json(REPORTS_FILE, reports)
        return updated


def list_nearby(lat, lng, radius_km):
    lat_min, lat_max, lng_min, lng_max = bounding_box(lat, lng, radius_km)
    result = []
    for row in _read_json(REPORTS_FILE):
        r_lat, r_lng = row.get("lat"), row.get("lng")
        if r_lat is None or r_lng is None:
            continue
        if not (lat_min <= r_lat <= lat_max and lng_min <= r_lng <= lng_max):
            continue
        if haversine_km(lat, lng, r_lat, r_lng) <= radius_km:
            result.append(row)
    return result


def heatmap_points():
    points = []
    for r in _read_json(REPORTS_FILE):
        if r.get("status") == "RESUELTO":
            continue
        weight = SEVERITY_SCORE.get(r.get("severity"), 1) + min(int(r.get("upvotes", 0) or 0) * 0.25, 2.0)
        points.append({"lat": r.get("lat"), "lng": r.get("lng"), "weight": round(float(weight), 2)})
    return points


# ============================================================================
# 8. ANALÍTICA (en la versión refactorizada vive en AnalyticsService)
# ============================================================================
SEVERITY_WEIGHT = {"bajo": 1, "intermedio": 2, "critico": 3}


def compute_summary(reports):
    total = len(reports)
    if total == 0:
        return {
            "total": 0, "criticalZoneName": "--",
            "criticalZoneInfo": "Sin datos suficientes",
            "criticalZoneCount": 0, "criticalZonePrediction": "0%",
        }

    weighted, counts = defaultdict(int), Counter()
    for r in reports:
        weighted[r.get("zone", "Centro")] += SEVERITY_WEIGHT.get(r.get("severity"), 1)
        counts[r.get("zone", "Centro")] += 1

    zone_name = max(weighted, key=weighted.get)
    zone_count, zone_weight = counts[zone_name], weighted[zone_name]

    if zone_count >= CRITICAL_ZONE_THRESHOLD:
        zone_info = f"Alta concentración ({zone_count} reportes, peso {zone_weight})"
    elif zone_count >= 3:
        zone_info = f"Concentración media ({zone_count} reportes)"
    else:
        zone_info = f"Actividad leve ({zone_count} reportes)"

    return {
        "total": total,
        "criticalZoneName": zone_name,
        "criticalZoneInfo": zone_info,
        "criticalZoneCount": zone_count,
        "criticalZonePrediction": _predict_trend(reports, zone_name),
    }


def _predict_trend(reports, zone_name):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=PREDICTION_WINDOW_DAYS * 2)
    daily = defaultdict(int)
    for r in reports:
        if r.get("zone") != zone_name:
            continue
        try:
            dt = datetime.fromisoformat(str(r.get("created_at", "")).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if dt < cutoff:
            continue
        daily[dt.date()] += 1

    if len(daily) < 2:
        zone_total = sum(daily.values()) or 1
        share = (zone_total / len(reports)) * 100
        return f"{min(round(share), 99)}%"

    days = sorted(daily.keys())
    xs = list(range(len(days)))
    ys = [daily[d] for d in days]
    n = len(xs)
    sum_x, sum_y = sum(xs), sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    denom = (n * sum_x2 - sum_x ** 2) or 1
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    prediction = max(intercept + slope * (xs[-1] + 1), 0)
    avg = sum(ys) / n
    if avg == 0:
        return "0%"
    return f"{min(round((prediction / avg) * 100), 99)}%"


# ============================================================================
# 9. GAMIFICACIÓN (en la versión refactorizada vive en GamificationService)
# ============================================================================
def compute_stats(user, reports, missions):
    mine = [r for r in reports
            if (r.get("user_id") is not None and r.get("user_id") == user.get("id"))
            or (r.get("user") == user.get("username"))]
    joined = [m for m in missions if user.get("username") in (m.get("participants") or [])]
    completed = [m for m in joined if m.get("status") == "COMPLETADA"]
    return {
        "reports_created": len(mine),
        "upvotes_received": sum(int(r.get("upvotes", 0) or 0) for r in mine),
        "reports_resolved": sum(1 for r in mine if r.get("status") == "RESUELTO"),
        "missions_joined": len(joined),
        "missions_completed": len(completed),
    }


def _compute_score(user):
    return int(user.get("eco_points", 0) or 0) + 25 * len(user.get("active_badges") or [])


def award_points(user, action):
    delta = int(ECO_POINTS.get(action, 0))
    if delta:
        user["eco_points"] = int(user.get("eco_points", 0) or 0) + delta
    user["user_score"] = _compute_score(user)
    save_user(user)
    return delta


def evaluate_badges(user, stats):
    earned = list(user.get("active_badges") or [])
    unlocked = []
    stats = {**stats, "eco_points": user.get("eco_points", 0)}
    for badge_id, _name, _desc, predicate in BADGES:
        try:
            if badge_id not in earned and predicate(stats):
                earned.append(badge_id)
                unlocked.append(badge_id)
        except Exception:
            continue
    if unlocked:
        user["active_badges"] = earned
        user["user_score"] = _compute_score(user)
        save_user(user)
    return unlocked


def reward(user, action):
    if user is None:
        return {"points": 0, "unlocked": []}
    points = award_points(user, action)
    stats = compute_stats(user, list_reports(), _read_json(MISSIONS_FILE))
    unlocked = evaluate_badges(user, stats)
    return {"points": points, "unlocked": unlocked}


def describe_badges(badge_ids):
    out = []
    for bid in badge_ids or []:
        badge = BADGES_BY_ID.get(bid)
        if badge:
            out.append({"id": badge[0], "name": badge[1], "description": badge[2]})
    return out


def build_profile(username):
    user = find_user(username)
    if user is None:
        return None
    stats = compute_stats(user, list_reports(), _read_json(MISSIONS_FILE))
    eco = int(user.get("eco_points", 0) or 0)
    return {
        "user": user,
        "stats": stats,
        "badges": describe_badges(user.get("active_badges")),
        "progress": {
            "level": eco // 100 + 1,
            "current": eco % 100,
            "target": 100,
            "pct": eco % 100,
        },
    }


def leaderboard(limit=10):
    users = sorted(all_users(), key=lambda u: (u.get("eco_points", 0) or 0), reverse=True)
    return [
        {
            "username": u.get("username"),
            "name": u.get("name") or u.get("username"),
            "role": u.get("role"),
            "eco_points": u.get("eco_points", 0) or 0,
            "user_score": u.get("user_score", 0) or 0,
            "badges": len(u.get("active_badges") or []),
        }
        for u in users[:limit]
    ]


# ============================================================================
# 10. MISIONES (en la versión refactorizada: CommunityService + MissionRepo)
# ============================================================================
def list_missions():
    return sorted(_read_json(MISSIONS_FILE), key=lambda m: m.get("date", ""), reverse=True)


def get_mission(mission_id):
    for m in _read_json(MISSIONS_FILE):
        if m.get("id") == mission_id:
            return m
    return None


def add_mission(mission):
    with _lock:
        missions = _read_json(MISSIONS_FILE)
        mission["id"] = (max((m.get("id", 0) for m in missions), default=0)) + 1
        missions.append(mission)
        _write_json(MISSIONS_FILE, missions)
    return mission


def update_mission(mission):
    with _lock:
        missions = _read_json(MISSIONS_FILE)
        for i, row in enumerate(missions):
            if row.get("id") == mission.get("id"):
                missions[i] = mission
                break
        _write_json(MISSIONS_FILE, missions)
    return mission


# ============================================================================
# 11. APLICACIÓN FLASK + RUTAS (todo en el mismo lugar)
# ============================================================================
app = Flask(__name__)
app.secret_key = SECRET_KEY
_init_storage()


def _current_user():
    username = session.get("user")
    if not username:
        return None
    return find_user(username)


def _require_login():
    if "user" not in session:
        return redirect(url_for("login"))
    return None


# --- Autenticación ----------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate(username, password)
        if user:
            session["user"] = user["username"]
            return redirect(url_for("index"))
        error = "Usuario o contraseña incorrectos."
    return render_template("auth.html", is_register=False, error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            user = register_user(username, password)
            session["user"] = user["username"]
            return redirect(url_for("index"))
        except ValueError as exc:
            error = str(exc)
    return render_template("auth.html", is_register=True, error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# --- Vistas -----------------------------------------------------------------
@app.route("/")
def index():
    guard = _require_login()
    if guard:
        return guard
    reports = list_reports()
    user = _current_user()
    return render_template(
        "index.html",
        user=session.get("user"),
        summary=compute_summary(reports),
        profile=build_profile(user["username"]) if user else None,
        leaderboard=leaderboard(limit=5),
        default_lat=DEFAULT_LAT,
        default_lng=DEFAULT_LNG,
        geofence_km=GEOFENCE_RADIUS_KM,
    )


@app.route("/profile")
def profile_page():
    guard = _require_login()
    if guard:
        return guard
    return render_template(
        "profile.html",
        user=session.get("user"),
        profile=build_profile(session.get("user")),
        leaderboard=leaderboard(limit=10),
    )


@app.route("/missions")
def missions_page():
    guard = _require_login()
    if guard:
        return guard
    reports_by_id = {r.get("id"): r for r in list_reports()}
    return render_template(
        "missions.html",
        user=session.get("user"),
        missions=list_missions(),
        reports_by_id=reports_by_id,
    )


# --- API de reportes --------------------------------------------------------
@app.route("/api/reports", methods=["GET"])
def api_reports():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", type=float)
    if lat is not None and lng is not None and radius is not None:
        return jsonify(list_nearby(lat, lng, radius))
    return jsonify(list_reports())


@app.route("/api/reports", methods=["POST"])
def api_create_report():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or request.form.to_dict()

    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    if not title:
        return jsonify({"error": "El título es obligatorio."}), 400
    if not description:
        return jsonify({"error": "La descripción es obligatoria."}), 400

    severity = payload.get("severity_level") or payload.get("severity") or "critico"
    if severity not in SEVERITY_SCORE:
        return jsonify({"error": "Severidad inválida."}), 400

    try:
        lat = float(payload.get("lat", DEFAULT_LAT))
        lng = float(payload.get("lng", DEFAULT_LNG))
    except (TypeError, ValueError):
        return jsonify({"error": "Coordenadas inválidas."}), 400

    photo_url = None
    ai_label = None
    ai_confidence = 0.0
    group = payload.get("group") or None

    photo = request.files.get("photo")
    if photo and getattr(photo, "filename", ""):
        raw = photo.read()
        result = classify_image(raw)
        ai_label = result["label"]
        ai_confidence = result["confidence"]
        try:
            photo_url = save_uploaded_image(photo)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    category = classify_text(f"{title} {description}")
    if ai_label in AI_LABEL_TO_CATEGORY and category == "otro" and not group:
        category, group = AI_LABEL_TO_CATEGORY[ai_label]

    report = {
        "title": title,
        "description": description,
        "zone": payload.get("zone", "Centro"),
        "lat": lat,
        "lng": lng,
        "severity": severity,
        "category": category,
        "group": group or CATEGORY_GROUPS.get(category, "OTRO"),
        "status": "PENDIENTE",
        "upvotes": 0,
        "severity_score": SEVERITY_SCORE.get(severity, 1),
        "photo_url": photo_url,
        "ai_label": ai_label,
        "ai_confidence": float(ai_confidence or 0.0),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user": session.get("user"),
        "user_id": (_current_user() or {}).get("id"),
    }
    if report["group"] not in VALID_GROUPS:
        report["group"] = CATEGORY_GROUPS.get(category, "OTRO")
    report = add_report(report)

    reward_result = reward(_current_user(), "create_report")
    body = dict(report)
    body["reward"] = reward_result
    return jsonify(body), 201


@app.route("/api/reports/<int:report_id>/upvote", methods=["POST"])
def api_upvote(report_id):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    report = upvote_report(report_id)
    if report is None:
        return jsonify({"error": "Reporte no encontrado."}), 404
    owner = find_user(report.get("user")) if report.get("user") else None
    return jsonify({"report": report, "owner_reward": reward(owner, "upvote_received")})


@app.route("/api/reports/<int:report_id>/status", methods=["POST"])
def api_change_status(report_id):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    user = _current_user()
    if user is None or user.get("role") not in STATUS_ROLES:
        return jsonify({"error": "Solo admin/operador pueden cambiar el estado."}), 403

    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").upper()
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Estado inválido: {status}"}), 400

    report = get_report(report_id)
    if report is None:
        return jsonify({"error": "Reporte no encontrado."}), 404

    report["status"] = status
    update_report(report)

    owner = find_user(report.get("user")) if report.get("user") else None
    if status == "RESUELTO":
        reward_result = reward(owner, "report_resolved")
    elif status == "EN_PROCESO":
        reward_result = reward(owner, "report_in_process")
    else:
        reward_result = {"points": 0, "unlocked": []}
    return jsonify({"report": report, "owner_reward": reward_result})


@app.route("/api/summary", methods=["GET"])
def api_summary():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(compute_summary(list_reports()))


@app.route("/api/heatmap", methods=["GET"])
def api_heatmap():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(heatmap_points())


@app.route("/api/classify", methods=["POST"])
def api_classify():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    photo = request.files.get("photo")
    if not photo or not getattr(photo, "filename", ""):
        return jsonify({"error": "Falta la imagen."}), 400
    try:
        return jsonify(classify_image(photo.read()))
    except Exception as exc:
        return jsonify({"error": f"No se pudo procesar la imagen: {exc}"}), 400


# --- API comunitaria --------------------------------------------------------
@app.route("/api/profile", methods=["GET"])
def api_profile():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(build_profile(session.get("user")))


@app.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(leaderboard(limit=10))


@app.route("/api/missions", methods=["GET"])
def api_missions():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(list_missions())


@app.route("/api/missions", methods=["POST"])
def api_create_mission():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or request.form.to_dict()
    report_id = payload.get("report_id")
    title = payload.get("title")
    zone = payload.get("zone", "Centro")
    lat = payload.get("lat", DEFAULT_LAT)
    lng = payload.get("lng", DEFAULT_LNG)

    if report_id:
        report = get_report(int(report_id))
        if report is None:
            return jsonify({"error": "El reporte asociado no existe."}), 404
        title = title or f"Limpieza: {report.get('title')}"
        zone = payload.get("zone") or report.get("zone")
        lat = payload.get("lat", report.get("lat"))
        lng = payload.get("lng", report.get("lng"))

    if not title or not str(title).strip():
        return jsonify({"error": "El título de la misión es obligatorio."}), 400

    mission = {
        "report_id": int(report_id or 0),
        "title": str(title).strip(),
        "zone": zone or "Centro",
        "lat": float(lat or 0.0),
        "lng": float(lng or 0.0),
        "date": payload.get("date") or datetime.now(timezone.utc).isoformat(),
        "participants": [],
        "status": "PENDIENTE",
        "created_by": session.get("user"),
        "eco_reward": 40,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(add_mission(mission)), 201


@app.route("/api/missions/<int:mission_id>/join", methods=["POST"])
def api_join_mission(mission_id):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    user = _current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401

    mission = get_mission(mission_id)
    if mission is None:
        return jsonify({"error": "La misión no existe."}), 400
    if user["username"] in mission.get("participants", []):
        return jsonify({"error": "Ya estás inscrito en esta misión."}), 400

    mission.setdefault("participants", []).append(user["username"])
    if mission.get("status") == "PENDIENTE":
        mission["status"] = "EN_CURSO"
    update_mission(mission)
    reward(user, "mission_join")
    return jsonify({"mission": mission, "profile": build_profile(user["username"])})


@app.route("/api/missions/<int:mission_id>/complete", methods=["POST"])
def api_complete_mission(mission_id):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    mission = get_mission(mission_id)
    if mission is None:
        return jsonify({"error": "La misión no existe."}), 400
    if mission.get("status") == "COMPLETADA":
        return jsonify(mission)

    mission["status"] = "COMPLETADA"
    update_mission(mission)
    for username in mission.get("participants", []):
        participant = find_user(username)
        if participant:
            reward(participant, "mission_complete")
    return jsonify(mission)


# ============================================================================
# 12. PUNTO DE ENTRADA
# ============================================================================
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=True)
