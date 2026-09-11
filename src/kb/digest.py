"""Digest programado: junta automatizacion + RAG en un entregable.

Corre por timer (ver `systemd/`), re-indexa lo que cambio y responde una lista
fija de preguntas (definidas en `kb.toml`, seccion `[digest]`). Escribe un
Markdown datado en `KB_DIGEST_OUT_DIR`. Sirve, por ejemplo, para un resumen
diario de "¿en que quedo tal proyecto?" a partir de tus notas.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from kb.config import Config
from kb.embeddings import Embedder
from kb.indexer import reindex
from kb.rag import answer
from kb.store import Store

log = logging.getLogger("kb.digest")


def generar_digest(cfg: Config, store: Store, embedder: Embedder) -> Path:
    r = reindex(cfg, store, embedder)
    log.info("indice al dia: %s chunks", r.chunks_totales)

    lineas = [f"# Digest {date.today().isoformat()}", ""]
    if not cfg.digest_questions:
        lineas.append("_No hay preguntas configuradas en `[digest]` de kb.toml._")
    for pregunta in cfg.digest_questions:
        resp = answer(cfg, store, embedder, pregunta)
        fuentes = ", ".join(f"`{s}`" for s in resp.sources) or "—"
        lineas += [f"## {pregunta}", "", resp.text, "", f"_Fuentes: {fuentes}_", ""]

    salida_dir = cfg.settings.kb_digest_out_dir
    salida_dir.mkdir(parents=True, exist_ok=True)
    destino = salida_dir / f"digest-{date.today().isoformat()}.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    log.info("digest escrito en %s", destino)
    return destino
