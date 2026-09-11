"""Corte de texto en fragmentos ("chunks") para indexar.

Un chunk es la unidad que se embebe y se recupera. Ni muy grande (mete ruido
en el prompt y diluye el embedding) ni muy chico (pierde contexto). Se corta
por parrafos y se solapan unos caracteres entre chunks consecutivos para no
partir una idea justo en el limite.
"""

from __future__ import annotations

TARGET_CHARS = 1200
OVERLAP_CHARS = 200


def chunk_text(
    texto: str, *, target_chars: int = TARGET_CHARS, overlap_chars: int = OVERLAP_CHARS
) -> list[str]:
    """Divide `texto` en fragmentos de ~`target_chars`, con `overlap_chars` de
    solapamiento. Respeta limites de parrafo cuando puede."""
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= target_chars:
        return [texto]

    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    chunks: list[str] = []
    actual = ""

    for parrafo in parrafos:
        if actual and len(actual) + len(parrafo) + 2 > target_chars:
            chunks.append(actual)
            cola = actual[-overlap_chars:] if overlap_chars else ""
            actual = f"{cola}\n\n{parrafo}" if cola else parrafo
        else:
            actual = f"{actual}\n\n{parrafo}" if actual else parrafo

        # Un unico parrafo mas largo que el target: se parte a lo bruto.
        while len(actual) > target_chars * 1.5:
            chunks.append(actual[:target_chars])
            actual = actual[target_chars - overlap_chars :]

    if actual:
        chunks.append(actual)
    return chunks
