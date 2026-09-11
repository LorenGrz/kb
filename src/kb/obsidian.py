"""Limpieza de sintaxis propia de Obsidian antes de trocear/embeber una nota.

No hace falta marcar una fuente como "vault de Obsidian": esto es un no-op
sobre markdown comun (no hay `---` inicial ni `[[...]]`), asi que se aplica
siempre que el archivo es `.md`. Tres cosas:

  - Frontmatter YAML (`--- ... ---` al inicio) se saca del cuerpo: son
    metadatos de Obsidian, no prosa, y meten ruido en el embedding.
  - `[[Nota]]`, `[[Nota|alias]]`, `[[Nota#seccion]]` se aplanan a su texto
    visible (el alias, o el nombre de la nota) sin los corchetes.
  - `![[archivo]]` (embed/transclusion) se reemplaza por una referencia corta;
    no se sigue el link (evita ciclos y duplicar contenido de otra nota).

Ademas se antepone el nombre del archivo como titulo: muchas notas (ej. las
que salen de una plantilla) tienen casi todo el contenido especifico en el
*nombre* del archivo y el cuerpo es generico.
"""

from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def limpiar_nota(texto: str) -> str:
    sin_frontmatter = _FRONTMATTER_RE.sub("", texto, count=1)
    sin_embeds = _EMBED_RE.sub(lambda m: f"[adjunto: {m.group(1)}]", sin_frontmatter)
    return _WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), sin_embeds).strip()


def preparar_texto(archivo_stem: str, contenido_crudo: str) -> str:
    """Limpieza + titulo. Lo que efectivamente se trocea y se embebe."""
    cuerpo = limpiar_nota(contenido_crudo)
    if not cuerpo:
        return ""
    if cuerpo.lstrip().startswith("#"):
        return cuerpo
    return f"# {archivo_stem}\n\n{cuerpo}"
