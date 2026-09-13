"""Linea de comandos: `kb index | search | ask | serve | digest`.

Es el mismo conjunto de funciones que expone el servidor MCP, pero para usar
a mano desde la terminal.
"""

from __future__ import annotations

import argparse
import sys

from kb.config import load_config
from kb.digest import generar_digest
from kb.embeddings import get_embedder
from kb.indexer import reindex
from kb.rag import answer, retrieve
from kb.store import Store


def _cmd_index(args: argparse.Namespace) -> int:
    cfg = load_config()
    with Store(cfg.settings.kb_db_path) as store:
        r = reindex(cfg, store, get_embedder(cfg), rebuild=args.rebuild)
    print(
        f"vistos={r.archivos_vistos} reindexados={r.archivos_reindexados} "
        f"borrados={r.archivos_borrados} chunks={r.chunks_totales}"
    )
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    cfg = load_config()
    with Store(cfg.settings.kb_db_path) as store:
        hits = retrieve(store, get_embedder(cfg), args.query, k=args.k)
    if not hits:
        print("sin resultados (¿corriste `kb index`?)")
        return 1
    for h in hits:
        print(f"\n[{h.score:.3f}] {h.path} (fragmento {h.ord})")
        print(h.text[:500] + ("…" if len(h.text) > 500 else ""))
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    cfg = load_config()
    try:
        with Store(cfg.settings.kb_db_path) as store:
            resp = answer(cfg, store, get_embedder(cfg), args.question, k=args.k)
    except RuntimeError as e:  # config o API caida: mensaje, no traceback
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(resp.text)
    print("\nFuentes:")
    for s in resp.sources:
        print(f"  - {s}")
    return 0


def _cmd_serve(_args: argparse.Namespace) -> int:
    from kb.mcp_server import main as serve_main

    serve_main()
    return 0


def _cmd_digest(_args: argparse.Namespace) -> int:
    cfg = load_config()
    try:
        with Store(cfg.settings.kb_db_path) as store:
            destino = generar_digest(cfg, store, get_embedder(cfg))
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(destino)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kb", description="Base de conocimiento personal (RAG + MCP).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="indexar / re-indexar (incremental)")
    pi.add_argument("--rebuild", action="store_true", help="borrar y reconstruir todo")
    pi.set_defaults(func=_cmd_index)

    ps = sub.add_parser("search", help="busqueda semantica (sin LLM)")
    ps.add_argument("query")
    ps.add_argument("-k", type=int, default=5)
    ps.set_defaults(func=_cmd_search)

    pa = sub.add_parser("ask", help="pregunta con RAG (usa Gemini)")
    pa.add_argument("question")
    pa.add_argument("-k", type=int, default=6)
    pa.set_defaults(func=_cmd_ask)

    pv = sub.add_parser("serve", help="arrancar el servidor MCP (stdio)")
    pv.set_defaults(func=_cmd_serve)

    pd = sub.add_parser("digest", help="re-indexar y responder las preguntas del digest")
    pd.set_defaults(func=_cmd_digest)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
