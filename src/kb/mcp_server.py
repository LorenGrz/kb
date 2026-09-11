"""Servidor MCP: expone la base de conocimiento como herramientas.

MCP (Model Context Protocol) es un estandar para que un cliente LLM
(Claude Code, Claude Desktop, tu propio agente) descubra y llame herramientas
que corren en OTRO proceso. Este archivo es un adaptador delgado: cada `@tool`
envuelve una funcion de `rag`/`indexer` que ya existe y funciona sola.

Transporte: stdio (el cliente arranca este proceso y le habla por stdin/stdout).
Por eso todo el logging va a stderr (ver `kb.reintentos`).

Registrarlo en Claude Code:
    claude mcp add kb -- uv run --project /home/loren/projects/kb kb serve
o copiar `.mcp.json.example` a `.mcp.json` en el repo donde quieras usarlo.
"""

from __future__ import annotations

import logging

# En mcp 1.x esta clase se llamaba `FastMCP` (mcp.server.fastmcp). El API
# (decorador `.tool()`, `.run("stdio")`) es el mismo.
from mcp.server.mcpserver import MCPServer

from kb.config import load_config
from kb.embeddings import get_embedder
from kb.indexer import reindex
from kb.rag import answer, retrieve
from kb.store import Store

log = logging.getLogger("kb.mcp")

server = MCPServer(name="kb", instructions="Base de conocimiento personal con RAG.")


@server.tool()
def search_knowledge_base(query: str, k: int = 5) -> str:
    """Busqueda semantica en la base local. Devuelve los fragmentos mas
    relevantes con su ruta de archivo y un score de similitud (0-1). No usa LLM."""
    cfg = load_config()
    with Store(cfg.settings.kb_db_path) as store:
        hits = retrieve(store, get_embedder(cfg), query, k=k)
    if not hits:
        return "Sin resultados (¿corriste `kb index`?)."
    return "\n\n".join(f"[{h.score:.2f}] {h.path} (fragmento {h.ord})\n{h.text}" for h in hits)


@server.tool()
def ask_knowledge_base(question: str) -> str:
    """Responde una pregunta con RAG sobre la base local: recupera contexto y
    genera una respuesta con Gemini, citando los archivos fuente. Necesita
    GEMINI_API_KEY configurada."""
    cfg = load_config()
    with Store(cfg.settings.kb_db_path) as store:
        resp = answer(cfg, store, get_embedder(cfg), question)
    fuentes = "\n".join(f"- {s}" for s in resp.sources)
    return f"{resp.text}\n\nFuentes:\n{fuentes}"


@server.tool()
def reindex_knowledge_base() -> str:
    """Re-indexa (incremental) las carpetas configuradas en kb.toml. Solo
    procesa lo que cambio desde la ultima corrida."""
    cfg = load_config()
    with Store(cfg.settings.kb_db_path) as store:
        r = reindex(cfg, store, get_embedder(cfg))
    return (
        f"archivos vistos: {r.archivos_vistos}, reindexados: {r.archivos_reindexados}, "
        f"borrados: {r.archivos_borrados}, chunks en indice: {r.chunks_totales}"
    )


def main() -> None:
    log.info("kb MCP server (stdio) — listo")
    server.run("stdio")


if __name__ == "__main__":
    main()
