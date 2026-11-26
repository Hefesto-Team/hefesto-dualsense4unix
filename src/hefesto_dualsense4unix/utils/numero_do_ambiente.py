"""O leitor único de número das variáveis de ambiente do serviço.

Ausente, vale o padrão; ilegível (vazia, ``abc``, ``5s``, ``nan``) ou fora da faixa, vale o padrão
e sai um ``warning`` com a chave e o valor. Nunca levanta: um número torto no ambiente não
derruba a subida.
"""
from __future__ import annotations

import math
import os
from typing import overload

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


@overload
def numero_do_ambiente(
    chave: str, normal: int, *, piso: int | None = None, teto: int | None = None,
) -> int: ...


@overload
def numero_do_ambiente(
    chave: str, normal: float, *, piso: float | None = None, teto: float | None = None,
) -> float: ...


def numero_do_ambiente(
    chave: str,
    normal: int | float,
    *,
    piso: int | float | None = None,
    teto: int | float | None = None,
) -> int | float:
    """O número em ``chave``, do tipo de ``normal`` (inteiro ou real), entre ``piso`` e ``teto``."""
    bruto = os.environ.get(chave)
    if bruto is None:
        return normal
    inteiro = isinstance(normal, int) and not isinstance(normal, bool)
    try:
        valor: int | float = int(bruto.strip()) if inteiro else float(bruto.strip())
    except ValueError:
        valor = math.nan
    if isinstance(valor, float) and not math.isfinite(valor):
        logger.warning("variavel_numerica_ilegivel", chave=chave, valor=bruto, usando=normal)
        return normal
    if (piso is not None and valor < piso) or (teto is not None and valor > teto):
        logger.warning(
            "variavel_numerica_fora_da_faixa", chave=chave, valor=bruto, usando=normal,
            piso=piso, teto=teto)
        return normal
    return valor


__all__ = ["numero_do_ambiente"]
