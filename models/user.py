"""
================================================================================
MÓDULO: models/user.py
PRINCIPIO SOLID: Single Responsibility (SRP)
TEMA DEL CURSO: Refactorización y SRP
================================================================================
La entidad User SOLO representa un usuario y sabe convertirse a/desde dict.
No sabe NADA de hashing, ni de Flask, ni de persistencia.
Esa separación permite cambiar la BD sin tocar el modelo.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Se añaden los campos de gamificación que pedía el prompt de la app Android:
    - name, email
    - eco_points  → puntos acumulados
    - user_score  → puntuación de reputación comunitaria
    - active_badges → insignias desbloqueadas
  Compatibilidad hacia atrás: `from_dict` tolera ficheros antiguos sin estos
  campos.
================================================================================
"""
from dataclasses import dataclass, asdict, field
from typing import Optional, List


@dataclass
class User:
    username: str
    password_hash: str
    id: Optional[int] = None
    role: str = "ciudadano"
    name: str = ""
    email: str = ""
    eco_points: int = 0
    user_score: int = 0
    active_badges: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data.get("id"),
            username=data["username"],
            password_hash=data["password_hash"],
            role=data.get("role", "ciudadano"),
            name=data.get("name", ""),
            email=data.get("email", ""),
            eco_points=int(data.get("eco_points", 0) or 0),
            user_score=int(data.get("user_score", 0) or 0),
            active_badges=list(data.get("active_badges", []) or []),
        )
