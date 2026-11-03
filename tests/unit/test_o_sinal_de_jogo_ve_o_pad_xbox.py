"""O sinal de jogo vê o pad Xbox: o jogo que segura o nó dele é o dono, de P1 a P4.

O-SINAL-DE-JOGO-VE-O-PAD-XBOX-01 (03/11/2026). O pad nasce como no produto: o `start()` do
`UinputGamepad`, o `UInput` vestido pelo `_uinput_sem_no_proprio` (o `device` fica nulo, como o
construtor do evdev o deixa) e o `inputN` do `UI_GET_SYSNAME`. Só o lado do kernel é de mentira:
o `/sys/class/input`, o `/dev/input` e o `/proc` moram no `tmp_path`.

A MORDIDA: voltar o `nos_do_pad` a ler `_device.device.path` reprova
`test_o_jogo_que_segura_o_pad_xbox_e_o_dono_dele`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import no_do_vpad
from hefesto_dualsense4unix.integrations import quem_segura_o_pad as qsp
from hefesto_dualsense4unix.integrations import uinput_gamepad as uinput

MEU_PID = 4242
IDENTIDADES = {
    "cabo": ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04"),
    "radio": ("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02", "AA:BB:CC:00:00:03", "AA:BB:CC:00:00:04"),
}
JOGO = ("forja", "/opt/a-forja/forja")


class _UInputComoOEvdev:
    """O construtor do `UInput` do evdev no que a cura toca: o `device` vem do `_find_device`."""

    proximo_fd = 60

    def __init__(self, *_a: Any, **_k: Any) -> None:
        self.fd = _UInputComoOEvdev.proximo_fd
        _UInputComoOEvdev.proximo_fd += 1
        self.device = self._find_device(self.fd)

    def _find_device(self, _fd: int) -> Any:
        return SimpleNamespace(path="/dev/input/event999")

    def close(self) -> None:
        return


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for parte in ("proc", "dev/input", "sys/class/input"):
        (tmp_path / parte).mkdir(parents=True)
    monkeypatch.setattr(no_do_vpad, "RAIZ_CLASS_INPUT", str(tmp_path / "sys/class/input"))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV_INPUT", str(tmp_path / "dev/input"))
    monkeypatch.setattr(qsp, "RAIZ_PROC", str(tmp_path / "proc"))
    monkeypatch.setattr(qsp, "RAIZ_DEV", str(tmp_path / "dev"))
    _UInputComoOEvdev.proximo_fd = 60

    def _fabrica(_self: Any, *, with_ff: bool) -> Any:
        return uinput._uinput_sem_no_proprio(_UInputComoOEvdev)()

    monkeypatch.setattr(uinput.UinputGamepad, "_create_device", _fabrica)
    monkeypatch.setattr(uinput.UinputGamepad, "_iniciar_o_fio_da_vibracao", lambda _self: None)
    monkeypatch.setitem(
        sys.modules, "evdev._uinput", SimpleNamespace(get_sysname=lambda fd: f"input{fd}")
    )
    return tmp_path


def _pad_xbox(raiz: Path) -> tuple[Any, Path]:
    """O pad como o daemon o cria hoje, e o `event` que o kernel publicou para ele."""
    pad = uinput.UinputGamepad.for_flavor("xbox")
    assert pad.start() is True
    assert pad._device.device is None, "o pad não nasceu como no produto"
    assert pad._sysname
    evento = f"event{pad._sysname.removeprefix('input')}"
    (raiz / "sys/class/input" / pad._sysname / evento).mkdir(parents=True)
    no = raiz / "dev/input" / evento
    no.write_bytes(b"")
    return pad, no


def _processo(raiz: Path, pid: int, comm: str, cmdline: str, *nos: Path) -> None:
    pasta = raiz / "proc" / str(pid)
    (pasta / "fd").mkdir(parents=True)
    (pasta / "comm").write_text(comm + "\n")
    (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
    for n, no in enumerate(nos, start=3):
        (pasta / "fd" / str(n)).symlink_to(no)


def _mesa(raiz: Path, jogadores: int, via: str) -> tuple[dict[str, Any], list[Path]]:
    pads: dict[str, Any] = {}
    nos: list[Path] = []
    for indice in range(jogadores):
        pad, no = _pad_xbox(raiz)
        pads[IDENTIDADES[via][indice]] = pad
        nos.append(no)
    return pads, nos


def _parar(pads: dict[str, Any]) -> None:
    for pad in pads.values():
        pad.stop()


@pytest.mark.parametrize("via", sorted(IDENTIDADES))
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_o_jogo_que_segura_o_pad_xbox_e_o_dono_dele(raiz: Path, jogador: int, via: str) -> None:
    """Quatro pads Xbox de pé; o jogo segura o `event` de um: ele é o dono desse, e só dele."""
    pads, nos = _mesa(raiz, 4, via)
    try:
        _processo(raiz, 5000, *JOGO, nos[jogador - 1])
        por_pad = qsp.jogos_por_pad(pads, meu_pid=MEU_PID)
        dono = IDENTIDADES[via][jogador - 1]
        assert set(por_pad) == {dono}, (
            "o jogo que segura o nó do pad Xbox não aparece como dono dele"
        )
        assert por_pad[dono].pid == 5000
        assert por_pad[dono].nome == JOGO[0]
        assert por_pad[dono].no == str(nos[jogador - 1])
    finally:
        _parar(pads)


@pytest.mark.parametrize("via", sorted(IDENTIDADES))
@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_ninguem_no_pad_xbox_e_nenhum_jogo(raiz: Path, jogadores: int, via: str) -> None:
    """Sem processo nos nós, ou só a Steam neles: nenhum pad tem jogo."""
    pads, nos = _mesa(raiz, jogadores, via)
    try:
        assert qsp.jogos_por_pad(pads, meu_pid=MEU_PID) == {}
        _processo(raiz, 5001, "steam", "/home/u/.steam/ubuntu12_32/steam", *nos)
        _processo(raiz, MEU_PID, "hefesto-dualsen", "/venv/bin/python hefesto", *nos)
        assert qsp.jogos_por_pad(pads, meu_pid=MEU_PID) == {}
    finally:
        _parar(pads)


def test_o_jogo_que_segura_todos_os_pads_xbox_e_dono_de_cada_um(raiz: Path) -> None:
    """O co-op de quatro num jogo só: os quatro pads o têm como dono."""
    pads, nos = _mesa(raiz, 4, "cabo")
    try:
        _processo(raiz, 5002, *JOGO, *nos)
        por_pad = qsp.jogos_por_pad(pads, meu_pid=MEU_PID)
        assert set(por_pad) == set(IDENTIDADES["cabo"])
        assert {segurador.pid for segurador in por_pad.values()} == {5002}
    finally:
        _parar(pads)
