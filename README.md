# kb — base de conocimiento personal (automatización + RAG + MCP)

> Proyecto de aprendizaje (Python). Un flujo realista y chico que combina las
> tres cosas en un solo código, para ver **cómo** y **dónde** encaja cada una:
>
> - **Automatización** → indexado incremental de tus documentos, disparable por timer.
> - **RAG** → recuperación semántica + respuesta con LLM citando fuentes.
> - **MCP** → esas mismas funciones expuestas como herramientas para Claude Code / Desktop.

Caso de uso: apuntás `kb` a tus carpetas de notas (roadmap, skills, memory, READMEs
de proyectos) y después preguntás en lenguaje natural desde la terminal o desde
Claude Code, con respuestas ancladas en *tus* archivos.

## Dónde vive cada concepto

| Concepto | Archivo | Función clave | Qué mirar |
|---|---|---|---|
| **Automatización** (indexado incremental, idempotente) | `src/kb/indexer.py` | `reindex()` | detección de cambios por `sha256`, borrado de huérfanos, `rebuild` |
| Corte de documentos en fragmentos | `src/kb/chunking.py` | `chunk_text()` | tamaño objetivo + solapamiento, por qué importa |
| **RAG · retrieval** | `src/kb/rag.py` | `retrieve()` | embedding de la query + coseno (producto punto) top-k, todo con numpy |
| **RAG · generation** | `src/kb/rag.py` | `answer()` / `_armar_prompt()` | cómo se arma el prompt con el contexto y se pide citar fuentes |
| Vectores → texto comparable | `src/kb/embeddings.py` | `Embedder` (Protocol), `get_embedder()` | backend `local` (fastembed, offline) vs `gemini` (API) detrás de una interfaz |
| Persistencia | `src/kb/store.py` | `Store` | SQLite: tablas `files` / `chunks`, embeddings como BLOB float32 |
| **MCP** (adaptador a herramientas) | `src/kb/mcp_server.py` | `@server.tool()` | cada tool es 4 líneas que llaman a `rag`/`indexer` |
| Automatización programada (entregable) | `src/kb/digest.py` | `generar_digest()` | reindexar + responder preguntas fijas → Markdown datado |
| Timer del SO (en vez de cron) | `systemd/kb-digest.{service,timer}` | — | `OnCalendar`, unidad de usuario |
| CLI | `src/kb/cli.py` | `kb index\|search\|ask\|serve\|digest` | mismo set de funciones que el MCP, para usar a mano |
| Config en dos capas | `src/kb/config.py` | `load_config()` | secretos/rutas por env (`pydantic-settings`) + fuentes/preguntas por `kb.toml` |
| Reintentos con backoff | `src/kb/reintentos.py` | `con_reintentos()` | patrón `tenacity` para toda llamada a API |

## Cómo se conecta (flujo de datos)

```
tus .md/.txt ──> indexer.reindex ──> chunking ──> embeddings ──> store (SQLite)
                     (automatización)                                  │
                                                                       ▼
consulta ──> rag.retrieve (embed query + coseno top-k) ──> chunks relevantes
                                                                       │
                                        rag.answer: prompt = contexto + pregunta
                                                                       ▼
                                              Gemini ──> respuesta + citas

Claude Code ──(protocolo MCP, stdio)──> mcp_server.tool ──> llama a rag/indexer
```

El punto clave: **RAG e indexado no saben que existe MCP**. `mcp_server.py` es solo
un adaptador. Podrías exponer lo mismo por HTTP, por un bot, o dejarlo solo como CLI.

## Instalación

```bash
cd /home/loren/projects/kb
uv sync --extra local     # --extra local = embeddings offline (fastembed)
```

Sin `--extra local` funciona igual pero tenés que usar `EMBEDDINGS_BACKEND=gemini`
(necesita `GEMINI_API_KEY`).

## Configuración

```bash
cp kb.example.toml kb.toml     # qué carpetas indexar + preguntas del digest
cp .env.example .env           # opcional: solo si vas a usar `ask` o el backend gemini
```

`kb.toml` se versiona (no tiene secretos). `.env` no.

| Variable | Default | Para qué |
|---|---|---|
| `EMBEDDINGS_BACKEND` | `local` | `local` (offline, sin costo) o `gemini` |
| `KB_DB_PATH` | `~/.local/share/kb/index.db` | dónde vive el índice |
| `KB_CONFIG_PATH` | `kb.toml` | archivo de fuentes/preguntas |
| `GEMINI_API_KEY` | — | solo `ask` / `digest` / backend gemini |
| `GEMINI_MODEL` | `gemini-2.5-flash` | modelo de generación |

## Uso

```bash
uv run kb index                       # indexa (incremental: solo lo que cambió)
uv run kb index --rebuild             # borra y reconstruye todo
uv run kb search "cómo desplegué X"   # búsqueda semántica, sin LLM (gratis, offline)
uv run kb ask "¿en qué etapa estoy?"  # RAG completo con Gemini + citas
uv run kb digest                      # reindexa + responde las preguntas de kb.toml
uv run kb serve                       # servidor MCP (stdio) — lo arranca el cliente
```

## Conectar a Claude Code (MCP)

```bash
claude mcp add kb -- uv run --project /home/loren/projects/kb kb serve
```

o copiá `.mcp.json.example` a `.mcp.json` en la raíz del repo donde quieras usarlo.
Después, en Claude Code, aparecen las tools `search_knowledge_base`,
`ask_knowledge_base` y `reindex_knowledge_base`.

## Automatizar el digest (systemd user timer, no cron)

```bash
cp systemd/kb-digest.service systemd/kb-digest.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kb-digest.timer     # corre todos los días 20:00
systemctl --user list-timers kb-digest.timer
```

Local, sin depender de GitHub Actions ni de una VM encendida.

## Verificación

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

15 tests, todos offline (usan un `FakeEmbedder`, no bajan modelos ni llaman APIs).

## Decisiones de arquitectura

- **Interfaz `Embedder` (Protocol) con dos backends.** El código no sabe si el
  embedding es local o de API; cambiar es una env var. Mismo patrón que la capa
  determinista vs. LLM del proyecto `automatiza-tu-dia-a-dia`.
- **SQLite + coseno en numpy, sin vector DB.** Para una base personal (miles de
  chunks) el brute-force es instantáneo y se ve toda la matemática de la
  recuperación. Si algún día son millones, ahí sí entra `sqlite-vec` / `qdrant`.
- **Embeddings normalizados al guardar.** Así la búsqueda es un simple producto
  punto (`matriz @ query`), no hay que dividir por normas en cada consulta.
- **Indexado incremental por `sha256`.** Correr `kb index` dos veces seguidas no
  reindexa nada. Requisito de cualquier automatización que corra por timer.
- **MCP como adaptador delgado.** La lógica está en `rag`/`indexer`; `mcp_server`
  solo la envuelve. Desacoplado del transporte.
- **`search` no necesita API key ni red; `ask` sí.** La parte cara (LLM) está
  aislada en una sola función.

## Lecciones

- El `mcp` SDK 2.x renombró `FastMCP` → `MCPServer` (`mcp.server.mcpserver`); el
  API (`@server.tool()`, `server.run("stdio")`) es el mismo.
- Un servidor MCP stdio **no puede escribir en stdout** (es el canal del
  protocolo). Todo el logging va a stderr (`kb/reintentos.py` lo fija).
- fastembed no soporta todos los nombres de modelo de HuggingFace; hay que
  elegir de `TextEmbedding.list_supported_models()`. El multilingüe chico útil es
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims).
- `tomllib` (stdlib) es solo lectura y es estricto: `[[sources]]` no admite un
  `sources = []` antes.

## Próximos pasos

- `kb ask` con historial (multi-turno) manteniendo el contexto recuperado.
- Un segundo servidor MCP que además **escriba** (crear/editar notas) → ya es un
  agente con tools de lectura y escritura.
- Router de modelos: `search` con embeddings locales, `ask` corto con flash,
  `ask` complejo con un modelo más grande — decidido por una función.
- Reranking de los top-k antes de armar el prompt (cross-encoder chico).
