"""
================================================================================
MÓDULO: config.py
TEMA DEL CURSO: Introducción a la gestión de la configuración
================================================================================
Este archivo centraliza TODA la configuración de la aplicación (credenciales,
rutas, parámetros de negocio). Ningún otro módulo debe tener valores "hardcoded".

BENEFICIOS:
  - Cambiar de entorno (dev/prod) NO requiere tocar la lógica de negocio.
  - Los secretos se leen de variables de entorno (.env).
  - Los valores por defecto quedan documentados en un único lugar.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Los parámetros que en Android vivían en `build.gradle.kts` (permisos, APIs,
  dependencias) y en constantes de la app, aquí viven en este único archivo:
  umbrales de IA, radio de geofencing, almacenamiento de imágenes y reglas de
  gamificación.
================================================================================
"""
import os
from datetime import timedelta


class Config:
    """Configuración base compartida por todos los entornos."""

    # --- Seguridad / Sesión ---
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # --- Parámetros de negocio (antes estaban dispersos en app.py) ---
    DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "-7.1638"))   # Cajamarca
    DEFAULT_LNG = float(os.getenv("DEFAULT_LNG", "-78.5008"))
    CRITICAL_ZONE_THRESHOLD = int(os.getenv("CRITICAL_ZONE_THRESHOLD", "5"))
    PREDICTION_WINDOW_DAYS = int(os.getenv("PREDICTION_WINDOW_DAYS", "7"))

    # --- Ubicación del almacenamiento (JSON plano o BD) ---
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    USERS_FILE = os.path.join(DATA_DIR, "users.json")
    REPORTS_FILE = os.path.join(DATA_DIR, "reports.json")
    MISSIONS_FILE = os.path.join(DATA_DIR, "missions.json")

    # --- Almacenamiento de imágenes (equivalente a Firebase Storage) ---
    UPLOAD_DIR = os.getenv(
        "UPLOAD_DIR",
        os.path.join(os.path.dirname(__file__), "static", "uploads"),
    )
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(8 * 1024 * 1024)))  # 8 MB

    # --- IA local (equivalente a TensorFlow Lite on-device) ---
    # Etiquetas que devuelve el clasificador de imágenes local.
    AI_LABELS = ("Basura Detectada", "Daño Estructural", "No Concluyente")
    AI_MIN_CONFIDENCE = float(os.getenv("AI_MIN_CONFIDENCE", "0.55"))

    # --- Geolocalización / Geofencing (equivalente a FusedLocation + Geofencing) ---
    GEOFENCE_RADIUS_KM = float(os.getenv("GEOFENCE_RADIUS_KM", "3.0"))

    # --- Gamificación comunitaria ---
    # Puntos "EcoEco" que otorga cada acción relevante.
    ECO_POINTS = {
        "create_report": int(os.getenv("POINTS_CREATE_REPORT", "10")),
        "upvote_received": int(os.getenv("POINTS_UPVOTE_RECEIVED", "2")),
        "report_in_process": int(os.getenv("POINTS_REPORT_IN_PROCESS", "5")),
        "report_resolved": int(os.getenv("POINTS_REPORT_RESOLVED", "25")),
        "mission_join": int(os.getenv("POINTS_MISSION_JOIN", "15")),
        "mission_complete": int(os.getenv("POINTS_MISSION_COMPLETE", "40")),
    }


class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"


class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"
    SESSION_COOKIE_SECURE = True   # solo HTTPS


# Registro de entornos disponibles → Open/Closed: para añadir "testing"
# o "staging" solo se agrega una clase nueva, sin modificar las existentes.
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config(env: str | None = None):
    """
    PATRÓN: Factory Method.
    Devuelve la clase de configuración adecuada según el entorno.
    """
    env = env or os.getenv("FLASK_ENV", "development")
    return CONFIG_MAP.get(env, DevelopmentConfig)
