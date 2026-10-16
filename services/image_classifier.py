"""
================================================================================
MÓDULO: services/image_classifier.py
PRINCIPIO SOLID:
  - SRP  → solo clasifica imágenes (no sabe de HTTP, ni de persistencia)
  - OCP  → el clasificador es un Protocol; se puede reemplazar por un modelo
           real (.tflite / Keras) SIN tocar quien lo consume
  - DIP  → los servicios dependen de la abstracción `ImageClassifier`
TEMA DEL CURSO: Principio Abierto/Cerrado (OCP) aplicado a IA

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  En Android el prompt pedía `util/ImageClassifierHelper.java` con TensorFlow
  Lite "on-device". Aquí la inferencia también es 100% LOCAL (no llama a APIs
  externas): se ejecuta en el propio servidor con Pillow + NumPy.

  `HeuristicImageClassifier` extrae características visuales (proporción de
  verde/marrón/gris, densidad de bordes, textura, saturación) y decide entre:
      "Basura Detectada" | "Daño Estructural" | "No Concluyente"

  ¿Por qué heurístico y no un .tflite real? Porque el proyecto no incluye un
  modelo entrenado. La arquitectura queda lista: basta crear otra clase que
  implemente el mismo Protocol (p. ej. `TFLiteImageClassifier`) y cambiarla en
  el Composition Root (app.py). Eso es EXACTAMENTE el Principio Abierto/Cerrado.
================================================================================
"""
import io
from dataclasses import dataclass, asdict
from typing import Optional, Protocol

import numpy as np
from PIL import Image, UnidentifiedImageError


# ------------------------------------------------------------------
# OCP: contrato del clasificador. Cualquier clasificador (heurístico,
# TFLite, Keras, API) que cumpla esta firma es intercambiable.
# ------------------------------------------------------------------
class ImageClassifier(Protocol):
    def classify(self, image_bytes: bytes) -> "ClassificationResult": ...


# Grupo canónico del dominio al que pertenece cada etiqueta de IA.
LABEL_TO_GROUP = {
    "Basura Detectada": "BASURA",
    "Daño Estructural": "INFRAESTRUCTURA",
    "No Concluyente": "OTRO",
}


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    group: str
    scores: dict
    features: dict

    def to_dict(self) -> dict:
        return asdict(self)


class HeuristicImageClassifier:
    """
    Clasificador local basado en visión por computador clásica.

    Pasos:
      1. Decodifica la imagen (Pillow) y la normaliza a tamaño fijo 96x96.
      2. Calcula la fracción de píxeles verdes / marrones / grises.
      3. Calcula densidad de bordes (gradientes) y textura (desviación).
      4. Puntúa cada etiqueta y devuelve la de mayor puntuación con su
         confianza normalizada.
    """

    SIZE = 96

    def __init__(self, min_confidence: float = 0.55):
        self.min_confidence = min_confidence

    # --- API pública ---------------------------------------------------------
    def classify(self, image_bytes: bytes) -> ClassificationResult:
        try:
            features = self._extract_features(image_bytes)
        except (UnidentifiedImageError, OSError, ValueError, Exception):
            # Nunca propagamos el fallo al request: degradamos a "No Concluyente".
            return self._fallback("Imagen ilegible o formato no soportado.")

        trash, structural = self._score(features)

        if max(trash, structural) < self.min_confidence:
            label = "No Concluyente"
            confidence = round(max(trash, structural), 3)
        elif trash >= structural:
            label = "Basura Detectada"
            confidence = round(trash, 3)
        else:
            label = "Daño Estructural"
            confidence = round(structural, 3)

        return ClassificationResult(
            label=label,
            confidence=confidence,
            group=LABEL_TO_GROUP.get(label, "OTRO"),
            scores={"trash": round(trash, 3), "structural": round(structural, 3)},
            features=features,
        )

    # --- Extracción de características --------------------------------------
    def _extract_features(self, image_bytes: bytes) -> dict:
        if not image_bytes:
            raise ValueError("Imagen vacía.")

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB").resize((self.SIZE, self.SIZE))

        arr = np.asarray(img, dtype=np.float32) / 255.0  # HxWx3 en [0,1]
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        mx = arr.max(axis=2)
        mn = arr.min(axis=2)
        sat = (mx - mn)                     # saturación HSV aproximada
        val = mx                            # brillo HSV aproximado
        gray = arr.mean(axis=2)

        total = float(self.SIZE * self.SIZE)

        # Verde: vegetación / residuos orgánicos alrededor de basura.
        green_mask = (g > r * 1.08) & (g > b * 1.08) & (sat > 0.12)
        # Marrón: tierra, cartón, residuos secos.
        brown_mask = (r > g) & (g >= b) & (sat > 0.10) & (val < 0.85) & (r < 0.95)
        # Gris: hormigón, asfalto, muros (daño estructural).
        gray_mask = sat < 0.10

        green_frac = float(green_mask.sum()) / total
        brown_frac = float(brown_mask.sum()) / total
        gray_frac = float(gray_mask.sum()) / total

        # Densidad de bordes (gradiente medio) y textura (desviación).
        gx = np.abs(np.diff(gray, axis=1)).mean()
        gy = np.abs(np.diff(gray, axis=0)).mean()
        edge = float((gx + gy) / 2.0)
        texture = float(gray.std())

        # Variedad cromática: cuántos "colores distintos" hay (histograma).
        hist, _ = np.histogram(gray, bins=16, range=(0.0, 1.0), density=True)
        color_variety = float(np.count_nonzero(hist)) / 16.0

        return {
            "green_frac": round(green_frac, 4),
            "brown_frac": round(brown_frac, 4),
            "gray_frac": round(gray_frac, 4),
            "edge_density": round(edge, 4),
            "texture": round(texture, 4),
            "saturation_mean": round(float(sat.mean()), 4),
            "brightness_mean": round(float(val.mean()), 4),
            "color_variety": round(color_variety, 4),
        }

    # --- Puntuación ----------------------------------------------------------
    def _score(self, f: dict) -> tuple[float, float]:
        # Normalizaciones suaves a [0,1].
        edge_n = min(f["edge_density"] / 0.18, 1.0)
        texture_n = min(f["texture"] / 0.30, 1.0)

        # Basura: mucha textura, colores variados, verde/marrón presentes.
        trash = (
            0.85 * min(f["green_frac"] * 3.0, 1.0)
            + 0.85 * min(f["brown_frac"] * 3.0, 1.0)
            + 0.55 * edge_n
            + 0.45 * texture_n
            + 0.30 * f["color_variety"]
        ) / 3.0

        # Daño estructural: predominio de gris/hormigón + bordes marcados,
        # poca saturación de color.
        structural = (
            1.30 * min(f["gray_frac"] * 1.6, 1.0)
            + 0.90 * edge_n
            + 0.40 * texture_n
            - 0.35 * min(f["saturation_mean"] * 2.0, 1.0)
        ) / 3.0

        return max(trash, 0.0), max(structural, 0.0)

    def _fallback(self, reason: str) -> ClassificationResult:
        return ClassificationResult(
            label="No Concluyente",
            confidence=0.0,
            group="OTRO",
            scores={"trash": 0.0, "structural": 0.0},
            features={"error": reason},
        )


def get_default_classifier(min_confidence: float = 0.55) -> ImageClassifier:
    """Factory: punto único para cambiar de clasificador (OCP + IoC)."""
    return HeuristicImageClassifier(min_confidence=min_confidence)
