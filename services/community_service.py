"""
================================================================================
MÓDULO: services/community_service.py
PRINCIPIO SOLID:
  - SRP  → orquesta la capa COMUNITARIA (misiones, insignias, ranking)
  - DIP  → depende de abstracciones (repositorios) y de GamificationService
TEMA DEL CURSO: Refactorización + Principio de Inversión de Control
================================================================================
ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Este servicio es el "pegamento" de la gamificación y las jornadas de limpieza
  (CleanupMission). Recibe sus dependencias por constructor (IoC) y no conoce ni
  Flask ni el almacenamiento concreto.

Responsabilidades:
  - Crear/listar/unirse/completar misiones de limpieza.
  - Calcular estadísticas de actividad del usuario.
  - Otorgar puntos e insignias a través de GamificationService.
  - Construir el perfil y el ranking comunitario.
================================================================================
"""
from typing import Dict, List, Optional

from models.user import User
from models.mission import CleanupMission
from repositories.base import ReportRepository, MissionRepository, UserRepository
from services.gamification_service import GamificationService


class CommunityService:
    def __init__(
        self,
        report_repo: ReportRepository,
        mission_repo: MissionRepository,
        user_repo: UserRepository,
        gamification: GamificationService,
    ):
        self.report_repo = report_repo
        self.mission_repo = mission_repo
        self.user_repo = user_repo
        self.gamification = gamification

    # --- Estadísticas --------------------------------------------------------
    def stats_for(self, user: User) -> dict:
        return self.gamification.compute_stats(
            user, self.report_repo.list_all(), self.mission_repo.list_all()
        )

    # --- Hooks de gamificación (invitados desde las rutas) -------------------
    def on_report_created(self, user: Optional[User]) -> dict:
        return self._reward(user, "create_report")

    def on_report_in_process(self, user: Optional[User]) -> dict:
        return self._reward(user, "report_in_process")

    def on_report_resolved(self, user: Optional[User]) -> dict:
        return self._reward(user, "report_resolved")

    def on_upvote_received(self, owner_username: Optional[str]) -> dict:
        if not owner_username:
            return {"points": 0, "unlocked": []}
        owner = self.user_repo.get_by_username(owner_username)
        return self._reward(owner, "upvote_received")

    def _reward(self, user: Optional[User], action: str) -> dict:
        if user is None:
            return {"points": 0, "unlocked": []}
        points = self.gamification.award(user, action)
        unlocked = self.gamification.evaluate_badges(user, self.stats_for(user))
        return {"points": points, "unlocked": unlocked}

    # --- Misiones de limpieza ------------------------------------------------
    def list_missions(self) -> List[CleanupMission]:
        return sorted(self.mission_repo.list_all(), key=lambda m: m.date, reverse=True)

    def create_mission(
        self,
        report_id: int,
        title: str,
        zone: str,
        lat: float,
        lng: float,
        date: Optional[str],
        created_by: Optional[str],
    ) -> CleanupMission:
        if not title or not title.strip():
            raise ValueError("El título de la misión es obligatorio.")
        mission = CleanupMission(
            report_id=int(report_id),
            title=title.strip(),
            zone=zone or "Centro",
            lat=float(lat or 0.0),
            lng=float(lng or 0.0),
            created_by=created_by,
        )
        if date:
            mission.date = date
        return self.mission_repo.add(mission)

    def join_mission(self, mission_id: int, user: User) -> CleanupMission:
        mission = self.mission_repo.get(mission_id)
        if mission is None:
            raise ValueError("La misión no existe.")
        if user.username in mission.participants:
            raise ValueError("Ya estás inscrito en esta misión.")

        mission.participants.append(user.username)
        if mission.status == "PENDIENTE":
            mission.status = "EN_CURSO"
        self.mission_repo.update(mission)
        self._reward(user, "mission_join")
        return mission

    def complete_mission(self, mission_id: int) -> CleanupMission:
        mission = self.mission_repo.get(mission_id)
        if mission is None:
            raise ValueError("La misión no existe.")
        if mission.status == "COMPLETADA":
            return mission

        mission.status = "COMPLETADA"
        self.mission_repo.update(mission)

        # Recompensa a todos los participantes.
        for username in mission.participants:
            participant = self.user_repo.get_by_username(username)
            if participant:
                self._reward(participant, "mission_complete")
        return mission

    # --- Perfil / ranking ----------------------------------------------------
    def profile(self, username: str) -> Optional[dict]:
        user = self.user_repo.get_by_username(username)
        if user is None:
            return None
        stats = self.stats_for(user)
        return {
            "user": user.to_dict(),
            "stats": stats,
            "badges": self.gamification.describe_badges(user.active_badges),
            "progress": self.gamification.next_level_progress(user.eco_points),
        }

    def leaderboard(self, limit: int = 10) -> List[dict]:
        users = sorted(self.user_repo.list_all(), key=lambda u: (u.eco_points or 0), reverse=True)
        return [
            {
                "username": u.username,
                "name": u.name or u.username,
                "role": u.role,
                "eco_points": u.eco_points or 0,
                "user_score": u.user_score or 0,
                "badges": len(u.active_badges or []),
            }
            for u in users[:limit]
        ]
