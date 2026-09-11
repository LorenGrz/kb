"""Utilidades de test. Embedder falso -> toda la suite corre offline y sin API."""

from __future__ import annotations

import zlib

import numpy as np
import pytest


class FakeEmbedder:
    """Embedding determinista tipo bag-of-words: cada palabra suma 1 en un
    bucket fijo. Sirve para que el coseno tenga sentido en los tests sin
    depender de un modelo real."""

    dim = 64

    def _vec(self, texto: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in texto.lower().split():
            v[zlib.crc32(tok.encode()) % self.dim] += 1.0
        norma = float(np.linalg.norm(v))
        return v / norma if norma else v

    def embed_documents(self, textos: list[str]) -> list[np.ndarray]:
        return [self._vec(t) for t in textos]

    def embed_query(self, texto: str) -> np.ndarray:
        return self._vec(texto)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
