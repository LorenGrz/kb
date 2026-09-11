"""Embeddings: convertir texto en vectores para poder compararlo por significado.

Dos backends detras de la misma interfaz (`Embedder`):
  - `LocalEmbedder`  : modelo local via fastembed. Offline, sin costo, multilingue.
  - `GeminiEmbedder` : API de Gemini. Sin modelo local, pero pide API key y red.

El resto del codigo depende de `Embedder`, no de un backend concreto: cambiar de
uno a otro es una linea en la config.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

import numpy as np
import numpy.typing as npt

from kb.config import Config
from kb.reintentos import con_reintentos

Vector = np.ndarray  # 1-D float32, siempre normalizado (norma L2 = 1)


def _normalizar(vec: npt.ArrayLike) -> Vector:
    v = np.asarray(vec, dtype=np.float32)
    norma = float(np.linalg.norm(v))
    return v / norma if norma else v


class Embedder(Protocol):
    """Contrato minimo que necesita el indexador y el recuperador."""

    dim: int

    def embed_documents(self, textos: list[str]) -> list[Vector]: ...

    def embed_query(self, texto: str) -> Vector: ...


class LocalEmbedder:
    """Modelo local (fastembed). Descarga el modelo la primera vez y lo cachea."""

    def __init__(self, modelo: str) -> None:
        import warnings

        from fastembed import TextEmbedding

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # fastembed avisa sobre el pooling; no aplica
            self._modelo = TextEmbedding(model_name=modelo)
        self.dim = int(self._modelo.embedding_size)

    def embed_documents(self, textos: list[str]) -> list[Vector]:
        return [_normalizar(v) for v in self._modelo.embed(textos)]

    def embed_query(self, texto: str) -> Vector:
        return next(iter(self.embed_documents([texto])))


class GeminiEmbedder:
    """Embeddings via la API de Gemini (`text-embedding-004` por defecto)."""

    _LOTE = 100

    def __init__(self, api_key: str, modelo: str) -> None:
        from google import genai

        self._cliente = genai.Client(api_key=api_key)
        self._modelo = modelo
        self.dim = 768  # text-embedding-004

    @con_reintentos(Exception)
    def _embed(self, textos: list[str], task_type: str) -> list[Vector]:
        from google.genai import types

        salida: list[Vector] = []
        for i in range(0, len(textos), self._LOTE):
            lote = textos[i : i + self._LOTE]
            resp = self._cliente.models.embed_content(
                model=self._modelo,
                contents=cast("Any", lote),
                config=types.EmbedContentConfig(task_type=task_type),
            )
            if not resp.embeddings:
                raise RuntimeError("Gemini no devolvio embeddings.")
            for e in resp.embeddings:
                if not e.values:
                    raise RuntimeError("Gemini devolvio un embedding vacio.")
                salida.append(_normalizar(e.values))
        return salida

    def embed_documents(self, textos: list[str]) -> list[Vector]:
        return self._embed(textos, "RETRIEVAL_DOCUMENT")

    def embed_query(self, texto: str) -> Vector:
        return self._embed([texto], "RETRIEVAL_QUERY")[0]


def get_embedder(cfg: Config) -> Embedder:
    """Devuelve el backend elegido en la config (`EMBEDDINGS_BACKEND`)."""
    s = cfg.settings
    if s.embeddings_backend == "local":
        return LocalEmbedder(s.embed_model_local)
    if s.embeddings_backend == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("EMBEDDINGS_BACKEND=gemini pero falta GEMINI_API_KEY.")
        return GeminiEmbedder(s.gemini_api_key, s.embed_model_gemini)
    raise ValueError(f"Backend de embeddings desconocido: {s.embeddings_backend!r}")
