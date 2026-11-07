"""A leitura do que a caixa de uma extensão pode escrever.

A caixa monta ``<dados>/<id>`` com escrita, então o que mora ali é entrada não confiável: quem lê
não segue link, não espera a outra ponta de um FIFO, só aceita arquivo regular e para no teto.
Recusou, quem chama fica com o padrão, e a recusa vai ao registro uma vez por arquivo e motivo,
porque a janela relê a cada pintura. Arquivo ausente não é recusa.
"""
from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

NAO_ABRIU = "nao_abriu"
NAO_E_COMUM = "nao_e_comum"
GRANDE_DEMAIS = "grande_demais"
_NAO_SAO_ARQUIVO = (errno.ELOOP, errno.EINVAL, errno.ENXIO)

_ditas: set[tuple[str, str]] = set()


class LeituraRecusadaError(OSError):
    """O arquivo não se lê. ``motivo``: :data:`NAO_ABRIU`, :data:`NAO_E_COMUM` ou
    :data:`GRANDE_DEMAIS`."""

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(motivo)


def abrir_sem_seguir(caminho: str, flags: int) -> int:
    """O descritor: sem seguir link, sem esperar a outra ponta de um FIFO, e só de arquivo
    regular. Serve de ``opener`` do ``open``."""
    descritor = os.open(caminho, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    if stat.S_ISREG(os.fstat(descritor).st_mode):
        return descritor
    os.close(descritor)
    raise OSError(errno.EINVAL, "não é um arquivo regular", caminho)


def dizer_a_recusa(caminho: Path, motivo: str) -> None:
    """Põe a recusa no registro, salvo se já foi dita neste arquivo."""
    if (str(caminho), motivo) not in _ditas:
        _ditas.add((str(caminho), motivo))
        logger.warning("leitura_da_caixa_recusada", arquivo=str(caminho), motivo=motivo)


def _recusa(caminho: Path, motivo: str) -> LeituraRecusadaError:
    dizer_a_recusa(caminho, motivo)
    return LeituraRecusadaError(motivo)


def ler_da_caixa(caminho: Path, teto: int) -> bytes:
    """Os bytes de ``caminho``, de até ``teto``. Sem arquivo, :class:`FileNotFoundError`; o resto,
    :class:`LeituraRecusadaError`."""
    try:
        with open(caminho, "rb", opener=abrir_sem_seguir) as arquivo:
            dados = arquivo.read(teto + 1)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise _recusa(caminho, NAO_E_COMUM if exc.errno in _NAO_SAO_ARQUIVO else NAO_ABRIU) from exc
    if len(dados) > teto:
        raise _recusa(caminho, GRANDE_DEMAIS)
    return dados


def ler_ou_vazio(caminho: Path, teto: int) -> bytes:
    """Os bytes de ``caminho``, ou nada para quem trata o ausente e o recusado do mesmo jeito."""
    try:
        return ler_da_caixa(caminho, teto)
    except OSError:
        return b""


__all__ = ["GRANDE_DEMAIS", "NAO_ABRIU", "NAO_E_COMUM", "LeituraRecusadaError", "abrir_sem_seguir",
           "dizer_a_recusa", "ler_da_caixa", "ler_ou_vazio"]
