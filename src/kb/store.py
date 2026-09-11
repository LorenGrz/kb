"""Persistencia del indice en SQLite (stdlib, sin motor de vectores externo).

Dos tablas:
  files(path, sha256, mtime, indexed_at)  -> que archivos y en que version estan indexados
  chunks(path, ord, text, embedding)      -> los fragmentos y su vector (float32, normalizado)

Para una base personal (cientos / pocos miles de chunks) alcanza con traer
todos los vectores a memoria y comparar con numpy. Se ve exactamente como
funciona la recuperacion, sin caja negra.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path       TEXT PRIMARY KEY,
    sha256     TEXT NOT NULL,
    mtime      REAL NOT NULL,
    indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY,
    path      TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    ord       INTEGER NOT NULL,
    text      TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
"""


@dataclass(frozen=True)
class ChunkRow:
    path: str
    ord: int
    text: str
    embedding: np.ndarray


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- lectura ----------------------------------------------------------

    def indexed_version(self, path: str) -> tuple[str, float] | None:
        row = self._db.execute("SELECT sha256, mtime FROM files WHERE path = ?", (path,)).fetchone()
        return (row[0], row[1]) if row else None

    def indexed_paths(self) -> set[str]:
        return {r[0] for r in self._db.execute("SELECT path FROM files")}

    def count_chunks(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def iter_chunks(self) -> Iterator[ChunkRow]:
        cur = self._db.execute("SELECT path, ord, text, embedding FROM chunks")
        for path, orden, text, blob in cur:
            yield ChunkRow(path, orden, text, np.frombuffer(blob, dtype=np.float32))

    # -- escritura ------------------------------------------------------

    def replace_file(
        self,
        path: str,
        sha256: str,
        mtime: float,
        chunks: list[tuple[str, np.ndarray]],
    ) -> None:
        """Reemplaza (borra + reinserta) todos los chunks de un archivo."""
        with self._db:  # transaccion
            self._db.execute("DELETE FROM chunks WHERE path = ?", (path,))
            self._db.execute(
                "INSERT INTO files(path, sha256, mtime, indexed_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, "
                "mtime=excluded.mtime, indexed_at=excluded.indexed_at",
                (path, sha256, mtime, datetime.now(UTC).isoformat()),
            )
            self._db.executemany(
                "INSERT INTO chunks(path, ord, text, embedding) VALUES (?, ?, ?, ?)",
                [
                    (path, i, texto, np.asarray(vec, dtype=np.float32).tobytes())
                    for i, (texto, vec) in enumerate(chunks)
                ],
            )

    def delete_paths(self, paths: set[str]) -> int:
        if not paths:
            return 0
        marcas = ",".join("?" * len(paths))
        with self._db:
            cur = self._db.execute(f"DELETE FROM files WHERE path IN ({marcas})", tuple(paths))
        return cur.rowcount
