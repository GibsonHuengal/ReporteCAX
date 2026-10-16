"""
================================================================================
MÓDULO: services/storage_service.py
PRINCIPIO SOLID: SRP + DIP (abstracción StorageService)
================================================================================
ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  En Android las fotos se subían a Firebase Storage. Aquí, para mantener el
  proyecto autocontenido y sin credenciales, se guardan en disco (carpeta
  `static/uploads`) a través de una abstracción `StorageService`.

  Mañana se puede crear `FirebaseStorageService` o `S3StorageService`
  implementando el mismo contrato, sin tocar las rutas ni los servicios.
================================================================================
"""
import os
import uuid
from typing import Optional, Protocol

from werkzeug.datastructures import FileStorage


class StorageService(Protocol):
    def save_image(self, file: FileStorage) -> Optional[str]:
        """Guarda la imagen y devuelve su URL pública relativa (o None)."""
        ...


class LocalStorageService:
    """Implementación concreta: guarda en el sistema de ficheros local."""

    def __init__(self, upload_dir: str, allowed_extensions: set[str],
                 static_folder: str, static_url: str = "/static"):
        """
        `upload_dir` DEBE estar dentro de `static_folder` (que Flask sirve como
        `/static/...`). Así la URL pública que devolvemos siempre resuelve.
        Si alguien lo configura fuera, fallamos al arrancar en lugar de guardar
        imágenes que luego den 404.
        """
        self.upload_dir = upload_dir
        self.allowed_extensions = {e.lower().lstrip(".") for e in allowed_extensions}

        rel = os.path.relpath(upload_dir, static_folder)
        if rel.startswith("..") or os.path.isabs(rel):
            raise ValueError(
                f"UPLOAD_DIR ({upload_dir}) debe estar dentro de {static_folder}."
            )
        self.url_prefix = (static_url.rstrip("/") + "/" + rel.replace(os.sep, "/")).rstrip("/")

        os.makedirs(self.upload_dir, exist_ok=True)

    @staticmethod
    def _extension(filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def is_allowed(self, filename: str) -> bool:
        return self._extension(filename) in self.allowed_extensions

    def save_image(self, file: FileStorage) -> Optional[str]:
        if file is None or not getattr(file, "filename", ""):
            return None
        if not self.is_allowed(file.filename):
            raise ValueError("Formato de imagen no permitido (usa PNG, JPG, WEBP).")

        ext = self._extension(file.filename)
        name = f"{uuid.uuid4().hex}.{ext}"
        destination = os.path.join(self.upload_dir, name)

        try:
            file.save(destination)
        except OSError as exc:
            raise ValueError(f"No se pudo guardar la imagen: {exc}") from exc

        return f"{self.url_prefix}/{name}"
