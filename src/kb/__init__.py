"""kb: base de conocimiento personal.

Tres piezas, un solo proyecto:
  - indexado incremental de tus documentos  -> `indexer` (automatizacion)
  - recuperacion semantica + respuesta con LLM -> `rag` (RAG)
  - exposicion de esas funciones como herramientas -> `mcp_server` (MCP)

Entrypoint de linea de comandos: `kb.cli:main` (`kb index|search|ask|serve|digest`).
"""
