from __future__ import annotations

from pathlib import Path

import numpy as np

from kb.store import Store


def _chunks(n: int) -> list[tuple[str, np.ndarray]]:
    return [(f"chunk {i}", np.ones(4, dtype=np.float32) * i) for i in range(n)]


def test_replace_file_guarda_version_y_chunks(tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        store.replace_file("/docs/a.md", "sha-a", 111.0, _chunks(3))

        assert store.indexed_version("/docs/a.md") == ("sha-a", 111.0)
        assert store.count_chunks() == 3
        assert store.indexed_paths() == {"/docs/a.md"}

        filas = sorted(store.iter_chunks(), key=lambda r: r.ord)
        assert [f.text for f in filas] == ["chunk 0", "chunk 1", "chunk 2"]
        assert filas[2].embedding.tolist() == [2.0, 2.0, 2.0, 2.0]


def test_replace_file_reemplaza_los_chunks_previos(tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        store.replace_file("/docs/a.md", "sha-1", 1.0, _chunks(5))
        store.replace_file("/docs/a.md", "sha-2", 2.0, _chunks(2))

        assert store.count_chunks() == 2
        assert store.indexed_version("/docs/a.md") == ("sha-2", 2.0)


def test_delete_paths_borra_en_cascada(tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        store.replace_file("/docs/a.md", "sha-a", 1.0, _chunks(3))
        store.replace_file("/docs/b.md", "sha-b", 1.0, _chunks(2))

        borrados = store.delete_paths({"/docs/a.md"})

        assert borrados == 1
        assert store.indexed_paths() == {"/docs/b.md"}
        assert store.count_chunks() == 2


def test_indexed_version_inexistente_es_none(tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        assert store.indexed_version("/nope.md") is None
