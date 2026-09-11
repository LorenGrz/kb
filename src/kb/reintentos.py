"""Reintentos con backoff exponencial para llamadas de red / API.

Mismo patron que se usaria en cualquier automatizacion: N intentos, espera
creciente, y si igual falla se propaga la excepcion (nada de loops infinitos).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# A stderr: el servidor MCP usa stdout como canal de protocolo.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

log = logging.getLogger("kb.reintentos")

T = TypeVar("T")
INTENTOS = 3


def con_reintentos(
    *errores: type[BaseException],
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    tipos = errores or (Exception,)
    return retry(
        retry=retry_if_exception_type(tipos),
        stop=stop_after_attempt(INTENTOS),
        wait=wait_exponential(multiplier=1, max=10),
        before_sleep=lambda estado: log.warning(
            "reintento %s/%s tras error: %s",
            estado.attempt_number,
            INTENTOS,
            estado.outcome.exception() if estado.outcome else "?",
        ),
        reraise=True,
    )
