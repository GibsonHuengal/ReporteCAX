"""
================================================================================
MÓDULO: services/analytics_service.py
PRINCIPIO SOLID: Single Responsibility (SRP)
TEMA DEL CURSO: Refactorización y SRP
================================================================================
Cálculo de zona crítica, conteos y predicción.

ALGORITMOS APLICADOS
  - Zona crítica     → moda ponderada por severidad (crítico=3, intermedio=2, bajo=1)
  - Conteo           → número total de reportes en la zona ganadora
  - Predicción       → tendencia de los últimos N días extrapolada
                       (regresión lineal simple)
================================================================================
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from models.report import Report


# Pesos por severidad (afectan el cálculo de zona crítica)
SEVERITY_WEIGHT = {"bajo": 1, "intermedio": 2, "critico": 3}


class AnalyticsService:
    def __init__(self, critical_threshold: int = 5, prediction_window_days: int = 7):
        self.critical_threshold = critical_threshold
        self.prediction_window_days = prediction_window_days

    # -----------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------
    def compute_summary(self, reports: List[Report]) -> Dict:
        total = len(reports)
        if total == 0:
            return self._empty_summary()

        zone_name, zone_count, zone_weight = self._critical_zone(reports)
        prediction = self._predict_trend(reports, zone_name)

        return {
            "total": total,
            "criticalZoneName": zone_name,
            "criticalZoneInfo": self._describe_zone(zone_count, zone_weight),
            "criticalZoneCount": zone_count,
            "criticalZonePrediction": prediction,
        }

    # -----------------------------------------------------------------
    # Cálculo de la zona crítica (ponderada por severidad)
    # -----------------------------------------------------------------
    def _critical_zone(self, reports: List[Report]):
        weighted = defaultdict(int)      # zona → peso acumulado
        counts   = Counter()             # zona → nº reportes

        for r in reports:
            weighted[r.zone] += SEVERITY_WEIGHT.get(r.severity, 1)
            counts[r.zone]   += 1

        # La zona crítica es la de mayor peso (no solo la más frecuente)
        zone_name = max(weighted, key=weighted.get)
        return zone_name, counts[zone_name], weighted[zone_name]

    def _describe_zone(self, count: int, weight: int) -> str:
        if count >= self.critical_threshold:
            return f"Alta concentración ({count} reportes, peso {weight})"
        if count >= 3:
            return f"Concentración media ({count} reportes)"
        return f"Actividad leve ({count} reportes)"

    # -----------------------------------------------------------------
    # Predicción: tendencia lineal simple sobre los últimos N días
    # -----------------------------------------------------------------
    def _predict_trend(self, reports: List[Report], zone_name: str) -> str:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.prediction_window_days * 2)

        # Serie temporal: reportes por día (de la zona crítica)
        daily = defaultdict(int)
        for r in reports:
            if r.zone != zone_name:
                continue
            try:
                dt = datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if dt < cutoff:
                continue
            daily[dt.date()] += 1

        if len(daily) < 2:
            # Con pocos datos: usamos proporción simple como fallback
            zone_total = sum(daily.values()) or 1
            share = (zone_total / len(reports)) * 100
            return f"{min(round(share), 99)}%"

        # Regresión lineal simple: y = a + bx
        days = sorted(daily.keys())
        xs = list(range(len(days)))
        ys = [daily[d] for d in days]

        n = len(xs)
        sum_x  = sum(xs);               sum_y  = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denom = (n * sum_x2 - sum_x ** 2) or 1
        slope = (n * sum_xy - sum_x * sum_y) / denom

        # Predicción para el "siguiente día"
        next_x = xs[-1] + 1
        intercept = (sum_y - slope * sum_x) / n
        prediction = max(intercept + slope * next_x, 0)

        # Convertimos a probabilidad (%) con una escala logarítmica suave
        avg = sum(ys) / n
        if avg == 0:
            return "0%"
        ratio = prediction / avg
        prob = min(round(ratio * 100), 99)
        return f"{prob}%"

    def _empty_summary(self) -> Dict:
        return {
            "total": 0,
            "criticalZoneName": "--",
            "criticalZoneInfo": "Sin datos suficientes",
            "criticalZoneCount": 0,
            "criticalZonePrediction": "0%",
        }