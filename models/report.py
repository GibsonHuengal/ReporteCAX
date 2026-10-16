"""
================================================================================
MÓDULO: models/report.py
PRINCIPIO SOLID: Single Responsibility (SRP)
TEMA DEL CURSO: Refactorización y SRP / DRY
================================================================================
Representa un reporte urbano (basura o daño). Antes los diccionarios "sueltos"
circulaban por todo app.py (violación de DRY y de SRP). Aquí queda encapsulado.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Se añaden los campos que el prompt de la app Android pedía:
    - category   → categoría detallada (bache, basura, fuga, ...)
    - group      → agrupación canónica (BASURA, INFRAESTRUCTURA, RIESGO)
    - severity_score → severidad numérica (1..3) usada por el heatmap
    - status     → PENDIENTE | EN_PROCESO | RESUELTO
    - upvotes    → votos comunitarios
    - photo_url  → imagen subida a Storage (local)
    - ai_label / ai_confidence → resultado del clasificador local
  Toda la compatibilidad hacia atrás se garantiza con `from_dict`, que ignora
  claves desconocidas y rellena las ausentes con sus valores por defecto.
================================================================================
"""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, List

# --- Dominio -----------------------------------------------------------------
VALID_SEVERITIES = {"bajo", "intermedio", "critico"}
VALID_STATUSES = {"PENDIENTE", "EN_PROCESO", "RESUELTO"}
VALID_GROUPS = {"BASURA", "INFRAESTRUCTURA", "RIESGO", "OTRO"}

# Severidad textual → peso numérico (alimenta el mapa de calor y las métricas).
SEVERITY_SCORE = {"bajo": 1, "intermedio": 2, "critico": 3}

# Categoría detallada → grupo canónico. Mantiene el clasificador por palabras
# clave y a la vez ofrece la agrupación que exige el prompt.
CATEGORY_GROUPS = {
    "bache": "INFRAESTRUCTURA",
    "alumbrado": "INFRAESTRUCTURA",
    "fuga": "INFRAESTRUCTURA",
    "basura": "BASURA",
    "seguridad": "RIESGO",
    "otro": "OTRO",
}


@dataclass
class Report:
    title: str
    description: str
    zone: str
    lat: float
    lng: float
    severity: str = "critico"
    category: str = "otro"
    group: str = "OTRO"
    status: str = "PENDIENTE"
    upvotes: int = 0
    severity_score: int = 0
    photo_url: Optional[str] = None
    ai_label: Optional[str] = None
    ai_confidence: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: Optional[int] = None
    user: Optional[str] = None
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Severidad inválida: {self.severity}")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Estado inválido: {self.status}")
        # El grupo se deriva de la categoría: si vino "OTRO"/ausente (datos
        # antiguos) y la categoría mapea a algo concreto, lo rellenamos.
        derived = CATEGORY_GROUPS.get(self.category, "OTRO")
        if self.group not in VALID_GROUPS:
            self.group = derived
        elif self.group == "OTRO" and derived != "OTRO":
            self.group = derived
        # Si no se pasó un score, se calcula a partir de la severidad.
        if not self.severity_score:
            self.severity_score = SEVERITY_SCORE.get(self.severity, 1)

    @property
    def is_resolved(self) -> bool:
        return self.status == "RESUELTO"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def empty_reports() -> List[Report]:
    """Helper DRY: lista vacía tipada (evita construir listas 'a mano')."""
    return []
