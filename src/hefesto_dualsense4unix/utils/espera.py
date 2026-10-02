"""A espera por leitura num descritor, sem o teto de 1024 do `select`.

`select.select` só aceita descritor abaixo de `FD_SETSIZE` (1024): acima dele
levanta `ValueError: filedescriptor out of range in select()`. Os leitores do
daemon tratavam esse erro como «o nó morreu», e um processo com mais de mil
descritores abertos ficava com o fio da vibração, o leitor do hidraw e o do
evdev saindo calados. Medido em 27/09/2026 no CI, onde a suíte roda num
processo só e os pipes das réguas passam do 1023.

`poll` não tem esse teto. Esta função tem a forma da pergunta que os leitores
faziam ao `select` e responde o mesmo para os casos de antes:

- descritor negativo levanta `ValueError`;
- descritor fechado levanta `OSError(EBADF)`;
- fim de linha (`POLLHUP`) e erro (`POLLERR`) contam como prontos, como no
  `select`: quem lê recebe o fim ou o erro na leitura.
"""
from __future__ import annotations

import errno
import math
import select
from collections.abc import Sequence
from typing import Any

__all__ = ["prontos_para_ler"]


def _descritor(alvo: Any) -> int:
    return alvo if isinstance(alvo, int) else int(alvo.fileno())


def prontos_para_ler(alvos: Sequence[Any], prazo_s: float | None) -> list[Any]:
    """Os `alvos` prontos para leitura em até `prazo_s` segundos."""
    espera = select.poll()
    por_descritor: dict[int, Any] = {}
    for alvo in alvos:
        fd = _descritor(alvo)
        if fd < 0:
            raise ValueError(f"descritor negativo: {fd}")
        espera.register(fd, select.POLLIN | select.POLLPRI)
        por_descritor[fd] = alvo
    prazo_ms = None if prazo_s is None else max(0, math.ceil(prazo_s * 1000))
    prontos: list[Any] = []
    for fd, evento in espera.poll(prazo_ms):
        if evento & select.POLLNVAL:
            raise OSError(errno.EBADF, f"descritor fechado: {fd}")
        prontos.append(por_descritor[fd])
    return prontos
