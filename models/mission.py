"""
================================================================================
MÓDULO: models/mission.py
PRINCIPIO SOLID: Single Responsibility (SRP)
================================================================================
Nuevo modelo del dominio incorporado desde el prompt de "EcoEco / BarrioVivo":

    CleanupMission → jornada comunitaria de limpieza/reparación asociada a un
    reporte. Tiene participantes, fecha y estado (PENDIENTE, EN_CURSO,
    COMPLETADA).

Igual que el resto de entidades, NO sabe de persistencia ni de HTTP: solo se
convierte a/desde dict.
================================================================================
"""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, List

VALID_MISSION_STATUSES = {"PENDIENTE", "EN_CURSO", "COMPLETADA"}


@dataclass
class CleanupMission:
    report_id: int
    title: str = "Jornada de limpieza comunitaria"
    zone: str = "Centro"
    lat: float = 0.0
    lng: float = 0.0
    date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    participants: List[str] = field(default_factory=list)
    status: str = "PENDIENTE"
    created_by: Optional[str] = None
    eco_reward: int = 40
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: Optional[int] = None

    def __post_init__(self):
        if self.status not in VALID_MISSION_STATUSES:
            raise ValueError(f"Estado de misión inválido: {self.status}")

    @property
    def participant_count(self) -> int:
        return len(self.participants)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CleanupMission":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
