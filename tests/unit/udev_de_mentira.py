"""O que o udev responde, para os testes que não podem perguntar ao udev da máquina.

O produto pergunta à `libudev` (`core/banco_do_udev.py`; o curador de áudio KS
tem a pergunta dele, copiada sozinha pelo install). Aqui moram os dois dublês:
um para a pergunta por `devnum` e por `syspath` do pacote, e um leitor do
`USEC_INITIALIZED` para o curador, montado a partir de uma pasta de mentira.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import banco_do_udev


class BancoDeMentira:
    """Troca as duas perguntas de `banco_do_udev` por tabelas do teste."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.por_devnum: dict[int, dict[str, str]] = {}
        self.por_syspath: dict[str, dict[str, str]] = {}
        self.perguntas: list[tuple[str, object, str]] = []
        monkeypatch.setattr(banco_do_udev, "propriedade_do_devnum", self._devnum)
        monkeypatch.setattr(banco_do_udev, "propriedade_do_syspath", self._syspath)

    def _devnum(self, tipo: str, devnum: int, nome: str) -> str | None:
        self.perguntas.append(("devnum", devnum, nome))
        return self.por_devnum.get(devnum, {}).get(nome)

    def _syspath(self, syspath: str, nome: str) -> str | None:
        self.perguntas.append(("syspath", syspath, nome))
        return self.por_syspath.get(str(syspath), {}).get(nome)


def usec_pela_pasta(banco: Path) -> Callable[[Path], int | None]:
    """O leitor de `USEC_INITIALIZED` do curador, com a resposta numa pasta de mentira.

    ``banco/c<maj>:<min>`` guarda um número (o `USEC_INITIALIZED`); o
    ``<maj>:<min>`` é o do arquivo ``dev`` do ``usb_device`` no sysfs de mentira.
    """

    def ler(dev_sysfs: Path) -> int | None:
        try:
            majmin = (dev_sysfs / "dev").read_text().strip()
            return int((banco / f"c{majmin}").read_text().strip())
        except (OSError, ValueError):
            return None

    return ler
