"""O-NO-DO-DUALSENSE-SE-CLASSIFICA-PELO-SYSFS-01 — a descoberta não pede o gamepad ao broker.

Depois da A-DESCOBERTA-LE-O-SYSFS-E-NAO-ABRE-O-NO-01 (onda 1 de 28/09), a
descoberta ainda abria o nó de GAMEPAD de cada DualSense, pelo broker quando
ele nasce fechado, a cada hotplug: o `backend_hotplug_reconcile`, o
`coop.sync` e a busca do leitor ausente. Na saída de um controle, os outros
três pediam uma rajada ao broker. Vendor, produto, barramento, nome, endereço
e botão de gamepad estão no sysfs: o nó entra na lista sem abrir.

A mesa é a da O-INVENTARIO (`test_o_inventario_dos_externos_nao_abre_o_dualsense`):
o `/dev/input` e o sysfs de mentira em tmp, o `InputDevice` da biblioteca com
o `__init__` de verdade, e um broker Unix de verdade que conta cada linha,
falando com o `HidrawBrokerClient` real, que escreve
`hidraw_broker_fd_recebido state=entrada` no diário. É essa linha que a prova
no aparelho conta.
"""
from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("evdev")

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from tests.unit.test_o_inventario_dos_externos_nao_abre_o_dualsense import (
    MESAS,
    Mesa,
    _montar,
    mac_ds,
)

_ESCONDIDOS = pytest.mark.parametrize(
    "escondidos", [True, False], ids=["escondidos", "abertos"]
)


@pytest.fixture
def montar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    abertas: list[Iterator[Mesa]] = []

    def _uma(escondidos: bool) -> Mesa:
        gerador = _montar(monkeypatch, tmp_path, MESAS["4-misto"],
                          escondidos=escondidos, externos=True)
        abertas.append(gerador)
        return next(gerador)

    yield _uma
    for gerador in abertas:
        with contextlib.suppress(StopIteration):
            next(gerador)


def _eventos_do(mesa: Mesa, k: int) -> list[str]:
    """Os `eventN` do DualSense físico k: gamepad, movimento e touchpad."""
    return [e for e, no in mesa.nos.items()
            if no.dualsense and not no.virtual and no.uniq == mac_ds(k)]


def _sai(mesa: Mesa, k: int, guarda: Path) -> None:
    """O controle k sai da mesa: os nós somem do `/dev/input` e do sysfs."""
    guarda.mkdir(exist_ok=True)
    for evento in _eventos_do(mesa, k):
        shutil.move(mesa.caminho[evento], guarda / f"dev-{evento}")
        shutil.move(str(mesa.sys_class / evento), guarda / f"sys-{evento}")


def _volta(mesa: Mesa, k: int, guarda: Path) -> None:
    for evento in _eventos_do(mesa, k):
        shutil.move(guarda / f"dev-{evento}", mesa.caminho[evento])
        shutil.move(guarda / f"sys-{evento}", str(mesa.sys_class / evento))


def _o_leitor_ausente_procura(k: int) -> Path | None:
    """A busca do leitor do jogador k que perdeu o nó (`EvdevReader._locate`)."""
    leitor = er.EvdevReader(target_uniq=norm_mac(mac_ds(k)))
    try:
        return leitor._locate()
    finally:
        leitor._close_wake_pipe()


def _todos_os_chamadores() -> dict[str, Any]:
    """O que o daemon pergunta num hotplug, por todas as portas públicas."""
    return {
        "discover_gamepads": [gp.evdev_path for gp in er.discover_gamepads()
                              if gp.especie == er.ESPECIE_DUALSENSE],
        "discover_dualsense_evdevs": er.discover_dualsense_evdevs(),
        "find_all_dualsense_evdevs": er.find_all_dualsense_evdevs(),
        "find_dualsense_evdev": er.find_dualsense_evdev(),
        "externos": [e["vid"] + ":" + e["pid"] for e in er.discover_external_gamepads()],
        "localizar": {
            k: er.localizar_node_por_identidade(norm_mac(mac_ds(k)) or "")
            for k in range(1, 5)
        },
        "leitor_ausente": {k: _o_leitor_ausente_procura(k) for k in range(1, 5)},
    }


@_ESCONDIDOS
def test_quatro_dualsense_saem_e_voltam_sem_um_pedido_ao_broker(
    montar: Any, tmp_path: Path, escondidos: bool
) -> None:
    """A prova da bancada, na mesa de mentira: os quatro na mesa, o P2 sai
    pelo rádio e volta. Em cada passo, todas as portas da descoberta acham
    quem está e não acham quem saiu, com ZERO pedidos no socket, zero linhas
    `hidraw_broker_fd_recebido state=entrada` e zero `InputDevice` em nó de
    DualSense. A MORDIDA: abra o nó do DualSense na descoberta (para ler a
    faixa dos eixos) e o primeiro passo já pede quatro fds.
    """
    mesa = montar(escondidos)
    guarda = tmp_path / "fora-da-mesa"
    sujos: list[tuple[str, int, int, int]] = []

    def _passo(rotulo: str, presentes: list[int]) -> None:
        vistos = _todos_os_chamadores()
        gamepads = [mesa.de(k) for k in presentes]
        assert vistos["discover_gamepads"] == gamepads, rotulo
        assert vistos["discover_dualsense_evdevs"] == {
            norm_mac(mac_ds(k)): Path(mesa.de(k)) for k in presentes
        }, rotulo
        assert vistos["find_all_dualsense_evdevs"] == [Path(c) for c in gamepads], rotulo
        assert vistos["find_dualsense_evdev"] == Path(gamepads[0]), rotulo
        assert sorted(vistos["externos"]) == ["054c:05c4", "057e:2009"], rotulo
        for porta in ("localizar", "leitor_ausente"):
            assert vistos[porta] == {
                k: (Path(mesa.de(k)) if k in presentes else None) for k in range(1, 5)
            }, (rotulo, porta)
        foto = (rotulo, len(mesa.pedidos), len(mesa.fd_recebidos()),
                len(mesa.tentativas_em_dualsense()))
        if any(foto[1:]):
            sujos.append(foto)

    _passo("os quatro na mesa", [1, 2, 3, 4])
    _sai(mesa, 2, guarda)
    _passo("o P2 saiu", [1, 3, 4])
    _volta(mesa, 2, guarda)
    _passo("o P2 voltou", [1, 2, 3, 4])

    assert not sujos, (
        f"o primeiro passo sujo: {sujos[0][0]} (pedidos, linhas state=entrada, "
        f"InputDevice em DualSense = {sujos[0][1:]})"
    )


@_ESCONDIDOS
def test_o_registro_do_sysfs_e_o_que_o_fd_diria(montar: Any, escondidos: bool) -> None:
    """Os campos que o fd dava (nome, vendor, produto, barramento, endereço)
    saem iguais pelo sysfs. O `eixos` fica vazio no DualSense: nenhum código
    do produto o lê da descoberta, e o leitor lê a faixa do nó que abre
    (`EvdevReader._on_device_opened`). O externo continua abrindo e trazendo a
    faixa, que é dele."""
    mesa = montar(escondidos)

    por_caminho = {gp.evdev_path: gp for gp in er.discover_gamepads()}

    for k in range(1, 5):
        gp = por_caminho[mesa.de(k)]
        no = next(no for e, no in mesa.nos.items() if mesa.caminho[e] == mesa.de(k))
        assert gp.especie == er.ESPECIE_DUALSENSE
        assert (gp.identidade, gp.name, gp.vid, gp.pid, gp.bus, gp.uniq) == (
            norm_mac(no.uniq), no.name, f"{no.vendor:04x}", f"{no.product:04x}",
            "bluetooth" if no.bus == 0x05 else "usb", no.uniq,
        )
        assert gp.eixos == {}
    pro = next(gp for gp in por_caminho.values() if gp.vid == "057e")
    assert pro.eixos, "o externo segue trazendo a faixa declarada"


#: Cada arquivo do sysfs que classifica o nó. Sem qualquer um deles, o nó
#: segue pelo caminho de antes: abre (pelo broker, se escondido) e lê pelo fd.
_ILEGIVEIS = ["uniq", "name", "id/bustype", "capabilities/key"]


@pytest.mark.parametrize("arquivo", _ILEGIVEIS)
@_ESCONDIDOS
def test_o_sysfs_ilegivel_segue_o_caminho_de_hoje(
    montar: Any, arquivo: str, escondidos: bool
) -> None:
    """O P3 (no cabo) com um arquivo do sysfs ilegível é achado pelo caminho de
    antes, e só ele: os outros três continuam sem pedido. A MORDIDA: pule o
    nó que o sysfs não classifica e o P3 some da descoberta.

    No cabo, e não no rádio, de propósito: o nó do rádio mora sob
    `/devices/virtual/misc/uhid/`, e sem o `uniq` legível o `_is_virtual_evdev`
    já o tratava como o vpad do daemon antes desta sprint. É o caminho de
    hoje também, e não é desta sprint mudá-lo."""
    mesa = montar(escondidos)
    p3 = mesa.de(3)
    alvo = Path(os.path.realpath(mesa.sys_class / Path(p3).name / "device")) / arquivo
    alvo.unlink()

    mapa = er.discover_dualsense_evdevs()

    assert mapa == {norm_mac(mac_ds(k)): Path(mesa.de(k)) for k in range(1, 5)}
    if escondidos:
        assert mesa.pedidos_de_open() == [p3], "o P3 pelo broker, e só ele"
        assert [kw["node"] for kw in mesa.fd_recebidos()] == [p3]
    else:
        assert mesa.pedidos == []
        assert mesa.tentativas_em_dualsense() == [p3]


def test_o_vendor_ilegivel_no_no_aberto_segue_o_caminho_de_hoje(montar: Any) -> None:
    """Sem `id/`, o sysfs nem diz que o nó é de DualSense: o nó aberto (Modo
    Nativo, ou máquina sem a cura) é lido pelo fd, como antes. A MORDIDA: pule
    o nó de sysfs ilegível e o P3 some."""
    mesa = montar(False)
    p3 = mesa.de(3)
    mesa.sysfs_ilegivel(p3)

    assert er.discover_dualsense_evdevs() == {
        norm_mac(mac_ds(k)): Path(mesa.de(k)) for k in range(1, 5)
    }
    assert mesa.tentativas_em_dualsense() == [p3]
    assert mesa.pedidos == []
