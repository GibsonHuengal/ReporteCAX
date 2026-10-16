"""
================================================================================
MÓDULO: services/auth_service.py
PRINCIPIO SOLID: Single Responsibility (SRP) + Dependency Inversion (DIP)
TEMA DEL CURSO: Refactorización y SRP / Refactorización y Principio Inversión de Control
================================================================================
Contiene LAS REGLAS DE NEGOCIO de autenticación:
  - Validar formato de usuario/contraseña
  - Hashear contraseñas
  - Verificar credenciales

NO conoce Flask ni la sesión HTTP. Recibe un UserRepository por constructor
(IoC): quien lo instancie decide qué implementación usar.
================================================================================
"""
import hashlib
import hmac
import re
from typing import Tuple, Optional

from models.user import User
from repositories.base import UserRepository

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LEN = 6


class AuthError(Exception):
    """Error de dominio (no de infraestructura)."""


class AuthService:
    def __init__(self, user_repo: UserRepository):
        # Inyección de dependencia por constructor (IoC)
        self.user_repo = user_repo

    # --- Utilidades privadas (DRY + SRP de bajo nivel) ---
    @staticmethod
    def _hash(password: str, salt: str = "cajamarca") -> str:
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    @staticmethod
    def _validate(username: str, password: str) -> None:
        if not USERNAME_RE.match(username):
            raise AuthError("El usuario debe tener 3-32 caracteres alfanuméricos.")
        if len(password) < MIN_PASSWORD_LEN:
            raise AuthError(f"La contraseña debe tener al menos {MIN_PASSWORD_LEN} caracteres.")

    # --- API pública ---
    def register(self, username: str, password: str) -> User:
        self._validate(username, password)
        if self.user_repo.get_by_username(username):
            raise AuthError("El usuario ya existe.")
        user = User(username=username, password_hash=self._hash(password))
        return self.user_repo.create(user)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.user_repo.get_by_username(username)
        if not user:
            return None
        # Comparación en tiempo constante (seguridad)
        if hmac.compare_digest(user.password_hash, self._hash(password)):
            return user
        return None