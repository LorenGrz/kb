"""Configuracion en dos capas:

  1. `Settings` (variables de entorno / `.env`): secretos y rutas de maquina.
  2. `kb.toml` (versionable): que carpetas indexar y las preguntas del digest.

`load_config()` junta las dos en un unico objeto `Config`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "kb" / "index.db"


class Settings(BaseSettings):
    """Parametros de maquina. Todo tiene default salvo, opcionalmente, la API key."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Donde vive el indice y el archivo de fuentes/preguntas.
    kb_db_path: Path = DEFAULT_DB_PATH
    kb_config_path: Path = Path("kb.toml")
    kb_digest_out_dir: Path = Path("digests")

    # Embeddings: "local" (offline, sin costo) o "gemini" (API).
    embeddings_backend: str = "local"
    embed_model_local: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embed_model_gemini: str = "text-embedding-004"

    # Generacion de respuestas (solo `ask` / `digest` la necesitan).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = Field(default=900, ge=1)


@dataclass(frozen=True)
class Source:
    """Un arbol de archivos a indexar y los patrones que se leen dentro."""

    root: Path
    globs: tuple[str, ...] = ("**/*.md", "**/*.txt")


@dataclass(frozen=True)
class Config:
    settings: Settings
    sources: tuple[Source, ...]
    digest_questions: tuple[str, ...] = field(default=())


def _load_toml(path: Path) -> tuple[tuple[Source, ...], tuple[str, ...]]:
    if not path.exists():
        return (), ()
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    fuentes: list[Source] = []
    for entrada in data.get("sources", []):
        root = Path(entrada["path"]).expanduser()
        globs = tuple(entrada.get("globs", ("**/*.md", "**/*.txt")))
        fuentes.append(Source(root=root, globs=globs))

    preguntas = tuple(data.get("digest", {}).get("questions", []))
    return tuple(fuentes), preguntas


@lru_cache(maxsize=1)
def load_config() -> Config:
    settings = Settings()
    sources, preguntas = _load_toml(settings.kb_config_path)
    return Config(settings=settings, sources=sources, digest_questions=preguntas)
