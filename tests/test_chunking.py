from __future__ import annotations

from kb.chunking import chunk_text


def test_texto_vacio_da_lista_vacia() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_texto_corto_es_un_solo_chunk() -> None:
    assert chunk_text("una nota breve") == ["una nota breve"]


def test_texto_largo_se_parte_en_varios() -> None:
    parrafo = "palabra " * 60  # ~480 chars
    texto = "\n\n".join([parrafo] * 6)  # ~2900 chars
    chunks = chunk_text(texto, target_chars=1000, overlap_chars=100)
    assert len(chunks) >= 3
    assert all(len(c) <= 1000 * 1.5 for c in chunks)


def test_hay_solapamiento_entre_chunks_consecutivos() -> None:
    texto = "\n\n".join(f"parrafo numero {i} " + "x " * 80 for i in range(8))
    chunks = chunk_text(texto, target_chars=800, overlap_chars=120)
    assert len(chunks) >= 2
    cola = chunks[0][-80:]
    assert cola[:20] in chunks[1]


def test_un_parrafo_gigante_se_corta_igual() -> None:
    texto = "z" * 5000
    chunks = chunk_text(texto, target_chars=1000, overlap_chars=100)
    assert len(chunks) > 1
