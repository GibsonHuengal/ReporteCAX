"""
================================================================================
MÓDULO: repositories/mission_repository.py
PRINCIPIO SOLID: Single Responsibility (SRP)
================================================================================
Persistencia de misiones de limpieza (CleanupMission) en JSON, con el mismo
patrón transaccional (lock) que el resto de repositorios.
================================================================================
"""
import json
import os
import threading
from typing import List, Optional

from models.mission import CleanupMission
from repositories.base import MissionRepository

_lock = threading.Lock()


class JsonMissionRepository(MissionRepository):

    def __init__(self, filepath: str):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read(self) -> list:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data: list) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(self, mission: CleanupMission) -> CleanupMission:
        with _lock:
            data = self._read()
            mission.id = (max((m.get("id", 0) for m in data), default=0)) + 1
            data.append(mission.to_dict())
            self._write(data)
        return mission

    def get(self, mission_id: int) -> Optional[CleanupMission]:
        with _lock:
            for row in self._read():
                if row.get("id") == mission_id:
                    return CleanupMission.from_dict(row)
        return None

    def update(self, mission: CleanupMission) -> CleanupMission:
        with _lock:
            data = self._read()
            for i, row in enumerate(data):
                if row.get("id") == mission.id:
                    data[i] = mission.to_dict()
                    break
            self._write(data)
        return mission

    def list_all(self) -> List[CleanupMission]:
        with _lock:
            return [CleanupMission.from_dict(m) for m in self._read()]
