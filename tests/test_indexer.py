from __future__ import annotations

from pathlib import Path

from kb.config import Config, Settings, Source
from kb.indexer import reindex
from kb.store import Store
from tests.conftest import FakeEmbedder


def _cfg(tmp_path: Path, docs: Path) -> Config:
    return Config(
        settings=Settings(kb_db_path=tmp_path / "db.sqlite"),
        sources=(Source(root=docs, globs=("**/*.md",)),),
    )


def test_reindex_es_incremental(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("contenido inicial de a\n\nsegundo parrafo", encoding="utf-8")
    (docs / "b.md").write_text("contenido de b", encoding="utf-8")
    cfg = _cfg(tmp_path, docs)

    with Store(cfg.settings.kb_db_path) as store:
        r1 = reindex(cfg, store, fake_embedder)
        assert (r1.archivos_vistos, r1.archivos_reindexados) == (2, 2)

        # segunda corrida sin cambios: no reindexa nada
        r2 = reindex(cfg, store, fake_embedder)
        assert r2.archivos_reindexados == 0

        # cambio un archivo -> solo ese se reindexa
        (docs / "a.md").write_text("contenido MODIFICADO de a", encoding="utf-8")
        r3 = reindex(cfg, store, fake_embedder)
        assert r3.archivos_reindexados == 1

        # borro un archivo -> se limpia del indice
        (docs / "b.md").unlink()
        r4 = reindex(cfg, store, fake_embedder)
        assert r4.archivos_borrados == 1
        assert store.indexed_paths() == {str((docs / "a.md").resolve())}


def test_rebuild_reindexa_todo(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("hola", encoding="utf-8")
    cfg = _cfg(tmp_path, docs)

    with Store(cfg.settings.kb_db_path) as store:
        reindex(cfg, store, fake_embedder)
        r = reindex(cfg, store, fake_embedder, rebuild=True)
        assert r.archivos_reindexados == 1
