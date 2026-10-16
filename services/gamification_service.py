"""
================================================================================
MÓDULO: services/gamification_service.py
PRINCIPIO SOLID: Single Responsibility (SRP)
TEMA: Sistema de gamificación comunitaria (EcoEco / BarrioVivo)
================================================================================
ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Convierte acciones ciudadanas en puntos ("eco_points"), calcula la reputación
  ("user_score") y desbloquea insignias ("active_badges").

  No conoce Flask ni la persistencia: recibe un UserRepository por constructor
  (IoC) y persiste los cambios a través de la abstracción.

Reglas (configurables en config.py):
  - Puntos por crear reporte, recibir votos, resolver, unirse/completar misión.
  - Insignias desbloqueables por umbrales.
================================================================================
"""
from dataclasses import dataclass
from typing import Dict, List, Callable

from models.user import User
from repositories.base import UserRepository


# ------------------------------------------------------------------
# Definición declarativa de insignias (OCP: añadir una insignia es añadir
# un elemento a esta lista, sin tocar la lógica).
# ------------------------------------------------------------------
@dataclass(frozen=True)
class Badge:
    id: str
    name: str
    description: str
    predicate: Callable[[dict], bool]


BADGES: List[Badge] = [
    Badge("primer_reporte", "Primer Reporte", "Enviaste tu primer reporte urbano.",
          lambda s: s.get("reports_created", 0) >= 1),
    Badge("reportero_activo", "Reportero Activo", "5 reportes enviados.",
          lambda s: s.get("reports_created", 0) >= 5),
    Badge("voz_de_barrio", "Voz de Barrio", "10 votos recibidos en tus reportes.",
          lambda s: s.get("upvotes_received", 0) >= 10),
    Badge("resolutor", "Resolutor", "Un reporte tuyo fue marcado como resuelto.",
          lambda s: s.get("reports_resolved", 0) >= 1),
    Badge("ecoguardian", "Ecoguardian", "500 eco-puntos acumulados.",
          lambda s: s.get("eco_points", 0) >= 500),
    Badge("voluntario", "Voluntario Verde", "Te uniste a una jornada de limpieza.",
          lambda s: s.get("missions_joined", 0) >= 1),
    Badge("heroe_comunitario", "Héroe Comunitario", "Completaste una jornada de limpieza.",
          lambda s: s.get("missions_completed", 0) >= 1),
]

BADGES_BY_ID: Dict[str, Badge] = {b.id: b for b in BADGES}


class GamificationService:
    def __init__(self, user_repo: UserRepository, points: dict):
        self.user_repo = user_repo
        self.points = points

    # --- Puntos --------------------------------------------------------------
    def award(self, user: User, action: str) -> int:
        """Suma los puntos de `action` al usuario y recalcula su reputación."""
        delta = int(self.points.get(action, 0))
        if delta:
            user.eco_points = int(user.eco_points or 0) + delta
        user.user_score = self._compute_score(user)
        self.user_repo.update(user)
        return delta

    @staticmethod
    def _compute_score(user: User) -> int:
        """Reputación = eco_puntos + bonus por insignias desbloqueadas."""
        return int(user.eco_points or 0) + 25 * len(user.active_badges or [])

    # --- Estadísticas de actividad ------------------------------------------
    @staticmethod
    def compute_stats(user: User, reports: list, missions: list) -> dict:
        """
        Agrega la actividad del usuario a partir de listas ya cargadas.
        Se mantiene puro (sin repos) para poder testearlo sin infraestructura.
        """
        mine = [
            r for r in reports
            if (r.user_id is not None and r.user_id == user.id) or (r.user == user.username)
        ]
        joined = [m for m in missions if user.username in (m.participants or [])]
        completed = [m for m in joined if m.status == "COMPLETADA"]
        return {
            "reports_created": len(mine),
            "upvotes_received": sum(int(r.upvotes or 0) for r in mine),
            "reports_resolved": sum(1 for r in mine if r.status == "RESUELTO"),
            "missions_joined": len(joined),
            "missions_completed": len(completed),
        }

    # --- Insignias -----------------------------------------------------------
    def evaluate_badges(self, user: User, stats: dict) -> List[str]:
        """
        Revisa las insignias contra las estadísticas del usuario y persiste las
        nuevas. Devuelve la lista de insignias recién desbloqueadas.
        """
        earned = list(user.active_badges or [])
        unlocked: List[str] = []
        stats = {**stats, "eco_points": user.eco_points}

        for badge in BADGES:
            try:
                if badge.id not in earned and badge.predicate(stats):
                    earned.append(badge.id)
                    unlocked.append(badge.id)
            except Exception:
                # Una regla defectuosa nunca debe romper el flujo del usuario.
                continue

        if unlocked:
            user.active_badges = earned
            user.user_score = self._compute_score(user)
            self.user_repo.update(user)

        return unlocked

    # --- Presentación --------------------------------------------------------
    @staticmethod
    def describe_badges(badge_ids: List[str]) -> List[dict]:
        result = []
        for bid in badge_ids or []:
            badge = BADGES_BY_ID.get(bid)
            if badge:
                result.append({"id": badge.id, "name": badge.name, "description": badge.description})
        return result

    @staticmethod
    def next_level_progress(eco_points: int) -> dict:
        """Progreso hacia el siguiente nivel (cada 100 puntos = 1 nivel)."""
        eco_points = int(eco_points or 0)
        level = eco_points // 100 + 1
        current = eco_points % 100
        return {"level": level, "current": current, "target": 100, "pct": current}
