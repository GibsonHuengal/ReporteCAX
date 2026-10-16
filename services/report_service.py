"""
================================================================================
MÓDULO: services/report_service.py
PRINCIPIO SOLID:
  - SRP  → sólo se encarga de orquestar reportes y clasificarlos por texto
  - OCP  → clasificadores intercambiables sin modificar este archivo
  - DIP  → depende de abstracciones (ReportRepository, Classifier)
TEMA DEL CURSO: Refactorización y Principio Abierto/Cerrado
================================================================================
ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  - create_report acepta ahora foto (photo_url) y resultado de IA (ai_label,
    ai_confidence, group). Si el clasificador por texto devuelve "otro" pero la
    IA es concluyente, se enriquece la categoría con la etiqueta de IA.
  - Se añaden upvote(), change_status(), list_nearby() y heatmap_points().
================================================================================
"""
from typing import List, Optional, Protocol

from models.report import Report, CATEGORY_GROUPS, SEVERITY_SCORE, VALID_STATUSES
from repositories.base import ReportRepository

# Etiqueta de IA → categoría detallada / grupo (enriquecimiento del reporte).
AI_LABEL_TO_CATEGORY = {
    "Basura Detectada": ("basura", "BASURA"),
    "Daño Estructural": ("bache", "INFRAESTRUCTURA"),
}


# ------------------------------------------------------------------
# OCP: el clasificador (texto) es un PROTOCOLO. Podemos añadir nuevos
# clasificadores (regex, ML, LLM) SIN modificar ReportService.
# ------------------------------------------------------------------
class Classifier(Protocol):
    """Contrato de un clasificador por texto (categoría detallada)."""

    def classify(self, text: str) -> str: ...


class KeywordClassifier:
    """Implementación simple basada en palabras clave."""

    RULES = {
        "bache":      ["bache", "hueco", "pavimento", "pista rota", "calle rota", "vereda"],
        "alumbrado":  ["luz", "alumbrado", "poste", "lámpara", "lampara"],
        "basura":     ["basura", "desecho", "residuo", "contenedor", "botadero"],
        "fuga":       ["fuga", "agua", "tubería", "tuberia", "alcantarilla"],
        "seguridad":  ["robo", "inseguridad", "delincuencia", "peligro"],
    }

    def classify(self, text: str) -> str:
        text = (text or "").lower()
        for category, keys in self.RULES.items():
            if any(k in text for k in keys):
                return category
        return "otro"


class ReportService:
    def __init__(
        self,
        report_repo: ReportRepository,
        classifier: Classifier | None = None,
    ):
        self.report_repo = report_repo
        # Inyección de dependencia: por defecto usamos KeywordClassifier
        self.classifier = classifier or KeywordClassifier()

    # --- Creación ------------------------------------------------------------
    def create_report(
        self,
        title: str,
        description: str,
        zone: str,
        lat: float,
        lng: float,
        severity: str,
        username: str | None = None,
        photo_url: str | None = None,
        ai_label: str | None = None,
        ai_confidence: float = 0.0,
        group: str | None = None,
    ) -> Report:
        # Validaciones de dominio
        if not title.strip():
            raise ValueError("El título es obligatorio.")
        if not description.strip():
            raise ValueError("La descripción es obligatoria.")
        if severity not in SEVERITY_SCORE:
            raise ValueError("Severidad inválida.")

        category = self.classifier.classify(f"{title} {description}")

        # La IA local solo REFINA la categoría cuando el texto no fue
        # concluyente ("otro") y el usuario no eligió un tipo explícito.
        if ai_label in AI_LABEL_TO_CATEGORY and category == "otro" and not group:
            category, group = AI_LABEL_TO_CATEGORY[ai_label]

        report = Report(
            title=title.strip(),
            description=description.strip(),
            zone=zone,
            lat=float(lat),
            lng=float(lng),
            severity=severity,
            category=category,
            group=group or CATEGORY_GROUPS.get(category, "OTRO"),
            photo_url=photo_url,
            ai_label=ai_label,
            ai_confidence=float(ai_confidence or 0.0),
            user=username,
        )
        return self.report_repo.add(report)

    # --- Consultas -----------------------------------------------------------
    def get(self, report_id: int) -> Optional[Report]:
        return self.report_repo.get(report_id)

    def list_reports(self) -> List[Report]:
        return self.report_repo.list_all()

    def list_nearby(self, lat: float, lng: float, radius_km: float) -> List[Report]:
        return self.report_repo.list_nearby(lat, lng, radius_km)

    def total(self) -> int:
        return self.report_repo.count()

    # --- Mutaciones ----------------------------------------------------------
    def upvote(self, report_id: int) -> Optional[Report]:
        return self.report_repo.upvote(report_id)

    def change_status(self, report_id: int, status: str) -> Optional[Report]:
        if status not in VALID_STATUSES:
            raise ValueError(f"Estado inválido: {status}")
        report = self.report_repo.get(report_id)
        if report is None:
            return None
        report.status = status
        return self.report_repo.update(report)

    # --- Datos para el Heatmap ----------------------------------------------
    def heatmap_points(self) -> List[dict]:
        """
        Puntos (lat, lng, peso) para el mapa de calor. El peso combina la
        severidad numérica con los votos comunitarios, de forma que las zonas
        con incidencias graves y muy votadas brillen más.
        """
        points = []
        for r in self.report_repo.list_all():
            if r.status == "RESUELTO":
                continue
            weight = SEVERITY_SCORE.get(r.severity, 1) + min(int(r.upvotes or 0) * 0.25, 2.0)
            points.append({"lat": r.lat, "lng": r.lng, "weight": round(float(weight), 2)})
        return points
