"""MAPA-SN30-01: o SN30 nunca alimenta o HotkeyManager — nem PS+R3, nem nada.

Origem: `docs/data/mapa-controles.csv`, linha `entrada.combo.ponte@sn30`. A
nota daquela célula (19/08/2026, FEAT-HOTKEY-PONTE-CYCLE-01) deixava a
pergunta EXPLICITAMENTE aberta: "ninguém verificou se o event bus que
alimenta o HotkeyManager é servido pelos controles externos". Este teste
fecha essa pergunta, com endereço.

O CAMINHO, medido lendo o código (nenhum aparelho tocado):

    HotkeyManager.observe(buttons_pressed)          integrations/hotkey_daemon.py
        chamado com  <-  self._evdev_buttons_once()  daemon/lifecycle.py:4662,4803
        que delega a  <- evdev_buttons_once(daemon)   daemon/subsystems/poll.py:53
        que lê         <- daemon.controller._evdev.snapshot()
        onde  controller._evdev  é um  EvdevReader()  retargetado por
        `self._evdev.retarget(self.primary_uniq)` (core/backend_pydualsense.py:2639)
        e  `primary_uniq`  só resolve identidade de um handle DualSense
        (core/backend_pydualsense.py:1719-1734 — o backend inteiro só abre
        hardware Sony via hidapi; não existe handle de SN30 aqui).

    Sem alvo (`_target_uniq is None`), `EvdevReader._locate()` cai em
    `find_dualsense_evdev()` -> `discover_dualsense_evdevs()`, que é
    FECHADA em `DUALSENSE_VENDOR` (0x054C) + `DUALSENSE_PIDS`
    ({0x0CE6, 0x0DF2}) — o SN30 em modo Switch é 057e:2009 e não casa em
    transporte nenhum (o mesmo vale para os outros disfarces dele: 2dc8:600x
    D-input, 045e:02xx X-input, e mesmo o 054c:05c4 do modo macOS, cujo VID
    bate mas o PID não está em `DUALSENSE_PIDS`).

    Com alvo, `_locate()` usaria `localizar_node_por_identidade`, que SABE
    enxergar externo — mas só é chamada com um `_target_uniq` vindo de
    `primary_uniq`, e este nunca é a identidade de um externo (a adoção
    deliberada de externo, a `E3`, está EXPLICITAMENTE não-entregue:
    core/evdev_reader.py:692-695, "O que ela NÃO faz: adotar ninguém (...)
    o veto de 19/07 segue de pé; quem o derruba é a E3, e ela é dela").

A MORDIDA: se alguém alargar `DUALSENSE_PIDS`/`DUALSENSE_VENDOR` para
incluir o SN30 (em qualquer dos quatro disfarces), ou se a classificação de
espécie em `discover_gamepads` parar de mandar VID/PID do SN30 para
`ESPECIE_EXTERNAL`, este teste reprova.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    ESPECIE_DUALSENSE,
    ESPECIE_EXTERNAL,
    discover_dualsense_evdevs,
    discover_gamepads,
)

# Os quatro VID:PID que o SN30 desta bancada veste, medidos/documentados em
# docs/protocol/externos-firmware-e-modos.md §2.2 — Switch (o modo em uso
# nesta mesa), D-input, X-input, macOS. Nenhum é DualSense.
_DISFARCES_DO_SN30 = [
    ("switch", 0x057E, 0x2009),
    ("d-input", 0x2DC8, 0x6001),
    ("x-input-cabo", 0x045E, 0x028E),
    ("macos", 0x054C, 0x05C4),  # mesmo VENDOR do DualSense; PID não é o dele
]


class _FakeSN30Dev:
    """Um evdev de gamepad físico com o VID:PID de um dos modos do SN30."""

    def __init__(self, path: str, vendor: int, product: int) -> None:
        self.path = path
        self.info = SimpleNamespace(vendor=vendor, product=product)
        self.uniq = "e4:17:d8:00:00:1a"  # OUI real da 8BitDo, medido em 11/08
        self.name = "8BitDo Pro Controller"

    def capabilities(self, *, verbose: bool = False, absinfo: bool = True):
        from evdev import ecodes

        return {ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_GAMEPAD]}

    def close(self) -> None: ...


@pytest.mark.parametrize("nome,vendor,product", _DISFARCES_DO_SN30)
def test_discover_dualsense_evdevs_nao_ve_o_sn30_em_modo_nenhum(
    monkeypatch: pytest.MonkeyPatch, nome: str, vendor: int, product: int
) -> None:
    """A descoberta que alimenta o `primary_uniq`/HotkeyManager por padrão
    (sem alvo) é fechada em DualSense — o SN30 fica de fora nos quatro
    disfarces, incluindo o macOS (mesmo vendor 0x054C do DualSense)."""
    dev = _FakeSN30Dev("/dev/input/event30", vendor, product)

    monkeypatch.setattr("evdev.list_devices", lambda: ["/dev/input/event30"])
    monkeypatch.setattr("evdev.InputDevice", lambda *_a, **_kw: dev)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader._is_virtual_evdev",
        lambda _p: False,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader._external_device_sysfs",
        lambda _p: (None, None),
    )

    found = discover_dualsense_evdevs()

    assert found == {}, (
        f"o SN30 em modo {nome} ({vendor:04x}:{product:04x}) entrou na "
        "descoberta que alimenta o HotkeyManager — PS+R3 (e qualquer outro "
        "combo) passaria a nascer de um controle externo"
    )


@pytest.mark.parametrize("nome,vendor,product", _DISFARCES_DO_SN30)
def test_discover_gamepads_classifica_o_sn30_como_externo(
    monkeypatch: pytest.MonkeyPatch, nome: str, vendor: int, product: int
) -> None:
    """A descoberta ÚNICA (usada quando HÁ alvo, via
    `localizar_node_por_identidade`) rotula o SN30 como ESPECIE_EXTERNAL —
    nunca ESPECIE_DUALSENSE. É essa espécie que os consumidores (co-op,
    inventário de externos) usam para recusar dar vpad/hotkey a ele."""
    dev = _FakeSN30Dev("/dev/input/event30", vendor, product)

    monkeypatch.setattr("evdev.list_devices", lambda: ["/dev/input/event30"])
    monkeypatch.setattr("evdev.InputDevice", lambda *_a, **_kw: dev)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader._is_virtual_evdev",
        lambda _p: False,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader._external_device_sysfs",
        lambda _p: (None, None),
    )

    achados = discover_gamepads(com_sysfs=False)

    assert len(achados) == 1, f"o fake do modo {nome} não foi enumerado"
    assert achados[0].especie == ESPECIE_EXTERNAL, (
        f"SN30 em modo {nome} ({vendor:04x}:{product:04x}) caiu em "
        f"'{achados[0].especie}' — se virar '{ESPECIE_DUALSENSE}' por engano, "
        "ele herda todo caminho que hoje só o DualSense físico anda"
    )


def test_dualsense_pids_nao_contem_nenhum_vidpid_do_sn30() -> None:
    """Cinturão-e-suspensório: o domínio fechado de PIDs do DualSense não
    ganhou, por acidente, o PID de nenhum disfarce do SN30. Vendor sozinho
    não bastaria — o modo macOS do SN30 REUSA o vendor 0x054C da Sony."""
    assert DUALSENSE_VENDOR == 0x054C
    for nome, vendor, product in _DISFARCES_DO_SN30:
        if vendor == DUALSENSE_VENDOR:
            assert product not in DUALSENSE_PIDS, (
                f"modo {nome} do SN30 partilha o vendor do DualSense E o PID "
                f"{product:04x} entrou em DUALSENSE_PIDS — o filtro por "
                "vendor+PID deixou de separar os dois aparelhos"
            )
