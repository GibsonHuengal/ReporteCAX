"""
================================================================================
MÓDULO: repositories/report_repository.py
PRINCIPIO SOLID: Single Responsibility (SRP)
================================================================================
Persistencia de reportes en JSON. Intercambiable por SQL/Mongo/Firestore sin
tocar los servicios que la usan.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  - Todas las escrituras pasan por un `threading.Lock`, que actúa como la
    TRANSACCIÓN que el prompt pedía en Firestore (incremento de votos y cambio
    de estado son atómicos a nivel de fichero).
  - `list_nearby` implementa la consulta por radio geográfico (geofencing).
================================================================================
"""
import json
import os
import threading
from typing import List, Optional

from models.report import Report
from repositories.base import ReportRepository
from utils.geo import haversine_km, bounding_box

_lock = threading.Lock()


class JsonReportRepository(ReportRepository):

    def __init__(self, filepath: str):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump([], f)

    # --- Métodos privados (DRY) ---
    def _read(self) -> list:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data: list) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- API pública (contrato ReportRepository) ---
    def add(self, report: Report) -> Report:
        with _lock:
            data = self._read()
            report.id = (max((r.get("id", 0) for r in data), default=0)) + 1
            data.append(report.to_dict())
            self._write(data)
        return report

    def get(self, report_id: int) -> Optional[Report]:
        with _lock:
            for row in self._read():
                if row.get("id") == report_id:
                    return Report.from_dict(row)
        return None

    def update(self, report: Report) -> Report:
        with _lock:
            data = self._read()
            for i, row in enumerate(data):
                if row.get("id") == report.id:
                    data[i] = report.to_dict()
                    break
            else:
                data.append(report.to_dict())
            self._write(data)
        return report

    def list_all(self) -> List[Report]:
        with _lock:
            return [Report.from_dict(r) for r in self._read()]

    def list_nearby(self, lat: float, lng: float, radius_km: float) -> List[Report]:
        """Reportes dentro del radio geográfico (haversine + prefiltro bbox)."""
        lat_min, lat_max, lng_min, lng_max = bounding_box(lat, lng, radius_km)
        result: List[Report] = []
        with _lock:
            rows = self._read()
        for row in rows:
            r_lat = row.get("lat")
            r_lng = row.get("lng")
            if r_lat is None or r_lng is None:
                continue
            if not (lat_min <= r_lat <= lat_max and lng_min <= r_lng <= lng_max):
                continue
            if haversine_km(lat, lng, r_lat, r_lng) <= radius_km:
                result.append(Report.from_dict(row))
        return result

    def upvote(self, report_id: int) -> Optional[Report]:
        """Incremento atómico de votos (equivalente a FieldValue.increment)."""
        with _lock:
            data = self._read()
            updated = None
            for row in data:
                if row.get("id") == report_id:
                    row["upvotes"] = int(row.get("upvotes", 0) or 0) + 1
                    updated = row
                    break
            if updated is not None:
                self._write(data)
                return Report.from_dict(updated)
        return None

    def count(self) -> int:
        return len(self._read())
