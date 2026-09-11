"""Indexado incremental: la parte de "automatizacion" del proyecto.

Recorre las carpetas configuradas, y para cada archivo:
  - si no cambio desde la ultima corrida (mismo sha256) -> lo saltea
  - si cambio o es nuevo -> lo re-trocea, re-embebe y reemplaza en el indice
Al final borra del indice los archivos que ya no existen.

Es idempotente: correrlo dos veces seguidas no cambia nada la segunda vez.
Pensado para dispararse con un timer (ver `systemd/`) o a mano con `kb index`.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from kb.chunking import chunk_text
from kb.config import Config, Source
from kb.embeddings import Embedder
from kb.store import Store

log = logging.getLogger("kb.indexer")


@dataclass
class IndexResult:
    archivos_vistos: int = 0
    archivos_reindexados: int = 0
    archivos_borrados: int = 0
    chunks_totales: int = 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descubrir(fuentes: tuple[Source, ...]) -> dict[str, Path]:
    """Mapa {ruta_absoluta_str: Path} de todo lo que matchea las fuentes."""
    encontrados: dict[str, Path] = {}
    for fuente in fuentes:
        raiz = fuente.root.expanduser()
        if not raiz.exists():
            log.warning("fuente inexistente, se ignora: %s", raiz)
            continue
        for patron in fuente.globs:
            for archivo in raiz.glob(patron):
                if archivo.is_file():
                    encontrados[str(archivo.resolve())] = archivo
    return encontrados


def reindex(cfg: Config, store: Store, embedder: Embedder, *, rebuild: bool = False) -> IndexResult:
    resultado = IndexResult()
    actuales = _descubrir(cfg.sources)
    resultado.archivos_vistos = len(actuales)

    if rebuild:
        store.delete_paths(store.indexed_paths())

    for ruta, archivo in sorted(actuales.items()):
        sha = _sha256(archivo)
        previo = store.indexed_version(ruta)
        if previo and previo[0] == sha and not rebuild:
            continue  # sin cambios

        fragmentos = chunk_text(archivo.read_text(encoding="utf-8", errors="replace"))
        if not fragmentos:
            store.replace_file(ruta, sha, archivo.stat().st_mtime, [])
            continue

        vectores = embedder.embed_documents(fragmentos)
        store.replace_file(
            ruta,
            sha,
            archivo.stat().st_mtime,
            list(zip(fragmentos, vectores, strict=True)),
        )
        resultado.archivos_reindexados += 1
        log.info("reindexado (%s chunks): %s", len(fragmentos), ruta)

    huerfanos = store.indexed_paths() - set(actuales)
    resultado.archivos_borrados = store.delete_paths(huerfanos)
    if huerfanos:
        log.info("borrados del indice %s archivos que ya no existen", len(huerfanos))

    resultado.chunks_totales = store.count_chunks()
    return resultado
