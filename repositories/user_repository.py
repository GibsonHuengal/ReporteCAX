"""
================================================================================
MÓDULO: repositories/user_repository.py
PRINCIPIO SOLID: Single Responsibility (SRP)
================================================================================
Su ÚNICA responsabilidad es persistir/leer usuarios. No sabe de hashing,
no sabe de Flask, no sabe de reglas de negocio.

ADAPTACIÓN: se añaden `get_by_id`, `update` y `list_all` para soportar la
gamificación (eco_points, badges) que pedía el prompt de la app Android.
================================================================================
"""
import json
import os
import threading
from typing import Optional, List

from models.user import User
from repositories.base import UserRepository

_lock = threading.Lock()


class JsonUserRepository(UserRepository):
    """Implementación concreta: usuarios en un JSON plano."""

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

    # --- API pública (contrato UserRepository) ---
    def get_by_username(self, username: str) -> Optional[User]:
        with _lock:
            for row in self._read():
                if row["username"] == username:
                    return User.from_dict(row)
        return None

    def get_by_id(self, user_id: int) -> Optional[User]:
        with _lock:
            for row in self._read():
                if row.get("id") == user_id:
                    return User.from_dict(row)
        return None

    def create(self, user: User) -> User:
        with _lock:
            data = self._read()
            user.id = (max((r.get("id", 0) for r in data), default=0)) + 1
            data.append(user.to_dict())
            self._write(data)
        return user

    def update(self, user: User) -> User:
        with _lock:
            data = self._read()
            for i, row in enumerate(data):
                if row.get("id") == user.id:
                    data[i] = user.to_dict()
                    break
            else:
                data.append(user.to_dict())
            self._write(data)
        return user

    def list_all(self) -> List[User]:
        with _lock:
            return [User.from_dict(r) for r in self._read()]
