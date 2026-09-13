from __future__ import annotations

from pathlib import Path

import pytest

from kb import rag
from kb.config import Config, Settings
from kb.store import Store
from tests.conftest import FakeEmbedder


def _store_con_docs(tmp_path: Path, emb: FakeEmbedder) -> Store:
    store = Store(tmp_path / "db.sqlite")
    docs = {
        "/n/gatos.md": "el gato negro duerme sobre la alfombra",
        "/n/finanzas.md": "el presupuesto mensual y los gastos de la empresa",
        "/n/viaje.md": "reserva de vuelo y hotel para el viaje a japon",
    }
    for path, texto in docs.items():
        vec = emb.embed_documents([texto])
        store.replace_file(path, "sha", 1.0, list(zip([texto], vec, strict=True)))
    return store


def test_retrieve_ordena_por_similitud(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    with _store_con_docs(tmp_path, fake_embedder) as store:
        hits = rag.retrieve(store, fake_embedder, "donde duerme el gato", k=3)

    assert hits[0].path == "/n/gatos.md"
    assert hits[0].score > hits[-1].score


def test_retrieve_sin_indice_devuelve_vacio(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        assert rag.retrieve(store, fake_embedder, "algo", k=5) == []


def test_answer_sin_indice_no_llama_al_llm(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    cfg = Config(settings=Settings(kb_db_path=tmp_path / "db.sqlite"), sources=())
    with Store(tmp_path / "db.sqlite") as store:
        resp = rag.answer(cfg, store, fake_embedder, "hola?")
    assert "kb index" in resp.text
    assert resp.sources == []


def test_answer_arma_contexto_y_cita_fuentes(
    tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    capturado: dict[str, str] = {}

    def fake_generar(_cfg: Config, prompt: str) -> str:
        capturado["prompt"] = prompt
        return "respuesta breve basada en el contexto"

    monkeypatch.setattr(rag, "_generar", fake_generar)
    cfg = Config(settings=Settings(kb_db_path=tmp_path / "db.sqlite"), sources=())

    with _store_con_docs(tmp_path, fake_embedder) as store:
        resp = rag.answer(cfg, store, fake_embedder, "donde duerme el gato", k=2)

    assert resp.text == "respuesta breve basada en el contexto"
    assert "/n/gatos.md" in resp.sources
    assert "CONTEXTO:" in capturado["prompt"]
    assert "PREGUNTA: donde duerme el gato" in capturado["prompt"]
    assert len(resp.sources) == len(set(resp.sources))  # sin duplicados


def test_generar_sin_api_key_no_reintenta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falta de API key es config, no una falla transitoria: debe fallar de una."""
    llamadas = 0

    def fake_llamar(_cfg: Config, _prompt: str) -> str:
        nonlocal llamadas
        llamadas += 1
        return ""

    monkeypatch.setattr(rag, "_llamar_gemini", fake_llamar)
    cfg = Config(settings=Settings(gemini_api_key=None), sources=())

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        rag._generar(cfg, "un prompt")

    assert llamadas == 0  # ni siquiera se intento la llamada
