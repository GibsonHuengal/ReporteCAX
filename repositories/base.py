"""
================================================================================
MÓDULO: repositories/base.py
PRINCIPIO SOLID: Dependency Inversion (DIP) + Interface Segregation (ISP)
TEMA DEL CURSO: Refactorización y Principio Inversión de Control (IoC)
================================================================================
Definimos CONTRATOS (ABC) que los servicios consumen. Los servicios NO conocen
la implementación concreta (JSON, SQLAlchemy, MongoDB...). Solo la abstracción.

Así, mañana podemos cambiar JSON por PostgreSQL o Firestore sin tocar un solo
servicio.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Los contratos crecen con las operaciones que el prompt requería:
    - ReportRepository → get, update, upvote (transaccional), change_status,
      list_nearby (radio geográfico ≈ geofencing).
    - UserRepository   → get_by_id, update, list_all (gamificación).
    - MissionRepository (nuevo) → misiones de limpieza comunitarias.
================================================================================
"""
from abc import ABC, abstractmethod
from typing import Optional, List

from models.user import User
from models.report import Report
from models.mission import CleanupMission


class UserRepository(ABC):
    """Contrato: ¿qué necesitamos SABER de un repositorio de usuarios?"""

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]: ...

    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def update(self, user: User) -> User: ...

    @abstractmethod
    def list_all(self) -> List[User]: ...


class ReportRepository(ABC):
    """Contrato: ¿qué necesitamos SABER de un repositorio de reportes?"""

    @abstractmethod
    def add(self, report: Report) -> Report: ...

    @abstractmethod
    def get(self, report_id: int) -> Optional[Report]: ...

    @abstractmethod
    def update(self, report: Report) -> Report: ...

    @abstractmethod
    def list_all(self) -> List[Report]: ...

    @abstractmethod
    def list_nearby(self, lat: float, lng: float, radius_km: float) -> List[Report]: ...

    @abstractmethod
    def upvote(self, report_id: int) -> Optional[Report]: ...

    @abstractmethod
    def count(self) -> int: ...


class MissionRepository(ABC):
    """Contrato: misiones de limpieza comunitarias (CleanupMission)."""

    @abstractmethod
    def add(self, mission: CleanupMission) -> CleanupMission: ...

    @abstractmethod
    def get(self, mission_id: int) -> Optional[CleanupMission]: ...

    @abstractmethod
    def update(self, mission: CleanupMission) -> CleanupMission: ...

    @abstractmethod
    def list_all(self) -> List[CleanupMission]: ...
