from __future__ import annotations

from kb.obsidian import limpiar_nota, preparar_texto


def test_saca_el_frontmatter() -> None:
    texto = "---\nfecha: 2026-08-10\ntags: [python]\n---\n\n# Clase\n\ncontenido real"
    assert limpiar_nota(texto) == "# Clase\n\ncontenido real"


def test_wikilink_simple_se_aplana_al_nombre() -> None:
    assert limpiar_nota("ver [[Otra Nota]] para mas detalle") == "ver Otra Nota para mas detalle"


def test_wikilink_con_alias_usa_el_alias() -> None:
    assert limpiar_nota("segun [[Nota Larga|este resumen]]") == "segun este resumen"


def test_wikilink_con_seccion_ignora_el_ancla() -> None:
    assert limpiar_nota("ver [[Nota#Introduccion]]") == "ver Nota"


def test_embed_se_reemplaza_por_referencia_corta() -> None:
    resultado = limpiar_nota("diagrama: ![[arquitectura.png]]")
    assert resultado == "diagrama: [adjunto: arquitectura.png]"


def test_texto_sin_sintaxis_obsidian_no_cambia() -> None:
    texto = "un parrafo comun, sin nada raro."
    assert limpiar_nota(texto) == texto


def test_preparar_texto_antepone_titulo_si_no_hay_heading() -> None:
    resultado = preparar_texto("Clase 2026-08-10", "---\ntags: []\n---\n\nnotas sueltas")
    assert resultado == "# Clase 2026-08-10\n\nnotas sueltas"


def test_preparar_texto_no_duplica_titulo_si_ya_hay_heading() -> None:
    resultado = preparar_texto("Clase", "# Encabezado propio\n\ntexto")
    assert resultado == "# Encabezado propio\n\ntexto"


def test_preparar_texto_nota_vacia_da_string_vacio() -> None:
    assert preparar_texto("Vacia", "---\ntags: []\n---\n") == ""
