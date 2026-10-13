"""O `evdev` que o `constraints.txt` trava aceita a cura do pad virtual.

O pad uinput do Hefesto sobrescreve `UInput._find_device` (`_uinput_sem_no_proprio`) para o
python-evdev não abrir o `/dev/input/eventN` que acabou de criar: aberto, ele é um leitor a mais
do nó e o pedido de vibração do jogo (`EV_UINPUT`) atrasa. A cura depende de um fato do FONTE do
python-evdev, o de que o construtor chama `self._find_device(self.fd)`.

O `test_o_pad_virtual_atende_a_vibracao_desde_que_nasce` usa um evdev de mentira que imita isso.
Este roda o `UInput.__init__` DE VERDADE, o da versão instalada, com o lado C trocado por um dublê
que não toca `/dev/uinput` nem nó nenhum, e por isso é ele que pega o dia em que uma versão nova
do evdev trocar o gancho.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest

evdev = pytest.importorskip("evdev")
uinput_mod = pytest.importorskip("evdev.uinput")

from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    _uinput_sem_no_proprio,
)
from tests.conftest import vigia_da_sessao


def _uinput_cru() -> type:
    """A classe REAL do evdev: a vigia da suíte troca `evdev.UInput` por uma porta que recusa."""
    vigia = vigia_da_sessao()
    classe = vigia.originais.get("evdev.UInput") if vigia is not None else None
    classe = classe or evdev.UInput
    assert isinstance(classe, type), "o UInput cru do evdev tem de ser uma classe"
    return classe


class _LadoCDeMentira:
    """O `_uinput` (a extensão C) sem tocar o kernel: cada chamada é aceita e nenhuma faz nada."""

    maxnamelen = 80

    def __init__(self, arquivo_real: str) -> None:
        self.__file__ = arquivo_real
        self.fechados: list[int] = []

    def open(self, _devnode: str) -> int:
        return os.open(os.devnull, os.O_WRONLY)

    def close(self, fd: int) -> None:
        self.fechados.append(fd)
        os.close(fd)

    def get_sysname(self, _fd: int) -> str:
        raise OSError("sem UI_GET_SYSNAME: o caminho do fallback")

    def __getattr__(self, _nome: str) -> Any:
        return lambda *_a, **_k: 0


class _NoDeMentira:
    """O `InputDevice` que o python-evdev abriria: só conta quantas vezes foi aberto."""

    abertos: ClassVar[list[str]] = []

    def __init__(self, caminho: str) -> None:
        type(self).abertos.append(caminho)
        self.name = "pad-de-teste"

    def close(self) -> None:
        return


@pytest.fixture
def lado_c(monkeypatch: pytest.MonkeyPatch) -> Iterator[_LadoCDeMentira]:
    falso = _LadoCDeMentira(uinput_mod._uinput.__file__)
    monkeypatch.setattr(uinput_mod, "_uinput", falso)
    # O 1.7 chama `device.InputDevice(...)`; do 1.8 em diante o `uinput` importa o nome: as duas.
    monkeypatch.setattr(evdev.device, "InputDevice", _NoDeMentira)
    monkeypatch.setattr(uinput_mod, "InputDevice", _NoDeMentira, raising=False)
    monkeypatch.setattr(uinput_mod.util, "list_devices", lambda *_a, **_k: ["/dev/input/event999"])
    monkeypatch.setattr(uinput_mod.time, "sleep", lambda *_a, **_k: None)
    _NoDeMentira.abertos = []
    yield falso


def _criar(classe: type) -> Any:
    return classe(
        {evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_SOUTH]},
        name="pad-de-teste",
        devnode=os.devnull,
    )


def test_sem_a_cura_o_python_evdev_abre_o_proprio_no(lado_c: _LadoCDeMentira) -> None:
    """Controle do instrumento: no `UInput` cru o dublê VÊ a abertura, então o verde abaixo mede."""
    pad = _criar(_uinput_cru())
    try:
        assert _NoDeMentira.abertos == ["/dev/input/event999"], (
            "o dublê não enxerga o python-evdev abrindo o nó: a medida abaixo seria cega"
        )
        assert isinstance(pad.device, _NoDeMentira)
    finally:
        pad.close()


def test_com_a_cura_o_uinput_real_nao_abre_o_proprio_no(lado_c: _LadoCDeMentira) -> None:
    """A classe do Hefesto, sobre o construtor REAL do evdev instalado: nó nenhum, `device` nulo."""
    pad = _criar(_uinput_sem_no_proprio(_uinput_cru()))
    try:
        assert _NoDeMentira.abertos == [], (
            "a versão do evdev que roda não chama `self._find_device(self.fd)` como a cura "
            "espera: o pad abriria o próprio nó e o pedido de vibração do jogo atrasaria"
        )
        assert pad.device is None
    finally:
        pad.close()
    assert lado_c.fechados, "o close do evdev não devolveu o fd ao kernel"


def test_o_gancho_que_a_cura_sobrescreve_existe_no_evdev_instalado() -> None:
    """Se o python-evdev renomear o gancho, a cura sobrescreve um método que ninguém chama."""
    assert callable(getattr(_uinput_cru(), "_find_device", None))
