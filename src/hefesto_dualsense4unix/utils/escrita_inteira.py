"""O dono da escrita de estado: o arquivo novo inteiro no lugar, ou o de antes intacto."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def escrever_inteiro(alvo: Path | str, dados: bytes | str) -> None:
    """Grava ``dados`` em ``alvo`` por troca atômica (o texto vai em UTF-8).

    Temporário na mesma pasta, escrita repetida até o último byte, ``fsync`` e
    ``os.replace``. Falha levanta ``OSError`` com o ``alvo`` de antes byte a byte
    igual e sem temporário na pasta; quem lê vê o arquivo velho ou o novo, nunca a metade.
    """
    alvo = Path(alvo)
    bruto = dados.encode("utf-8") if isinstance(dados, str) else dados
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=f".{alvo.name}.", suffix=".tmp", dir=alvo.parent)
    try:
        try:
            resto = memoryview(bruto)
            while resto:
                resto = resto[os.write(fd, resto):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporario, alvo)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
