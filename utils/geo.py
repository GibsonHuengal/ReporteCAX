"""
================================================================================
MÓDULO: utils/geo.py
PRINCIPIO SOLID: Single Responsibility (SRP)
================================================================================
Utilidades geográficas puras (sin estado y sin dependencias externas). Las usan
los repositorios (consulta por radio ≈ geofencing) y los servicios de analítica.

Contiene:
  - haversine_km()   → distancia entre dos coordenadas en kilómetros.
  - bounding_box()   → caja envolvente para prefiltrado rápido O(n).
================================================================================
"""
import math
from typing import Tuple

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia ortodrómica (great-circle) en kilómetros entre dos puntos."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lng: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Devuelve (lat_min, lat_max, lng_min, lng_max) que encierran un círculo de
    `radius_km`. Sirve para descartar rápido puntos lejanos antes de calcular
    el haversine completo (optimización).
    """
    lat_delta = radius_km / 111.32
    # Evita división por cero cerca de los polos.
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lng_delta = radius_km / (111.32 * cos_lat)
    return (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta)
