"""A-FORCA-DA-VIBRACAO-DE-CADA-CONTROLE-SAI-DE-UM-FUNIL-SO-COM-A-BATERIA-DELE-E-O-TETO-01.

A força com que um controle vibra é uma pergunta por controle: a bateria dele
(no `auto`), o fator da peça dele e o teto do orçamento da mesa. Até 09/10/2026
três cópias da conta liam a bateria do estado publicado, que é a do P1, e o
fator da peça era multiplicado no backend DEPOIS do teto, por um caminho que a
háptica fina do modo Xbox não atravessava.

O backend e o servidor IPC são os do produto. Os quatro handles são dublês que
anotam o que os motores receberam e carregam a bateria no `battery.Level`, o
mesmo campo que o laço do report do pydualsense atualiza.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.rumble import fixar_par, reassert_rumble
from hefesto_dualsense4unix.profiles.manager import ProfileManager

MACS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
BATERIAS = (90, 40, 10, 90)
FORCAS_DO_AUTO = (1.0, 0.7, 0.3, 1.0)
PEDIDO = 200


class _Handle:
    """Os motores viram lista; a bateria é a que o report deixou no handle."""

    def __init__(self, bateria: int, transporte: str) -> None:
        self.connected = True
        self.conType = type("CT", (), {"name": transporte})()
        self.battery = SimpleNamespace(Level=bateria, State=None)
        self.motores: list[tuple[str, int]] = []

    def setLeftMotor(self, intensidade: int) -> None:  # noqa: N802 — API pydualsense
        self.motores.append(("forte", intensidade))

    def setRightMotor(self, intensidade: int) -> None:  # noqa: N802 — API pydualsense
        self.motores.append(("fraco", intensidade))

    def par(self) -> tuple[int, int]:
        """O último ``(fraco, forte)`` que chegou."""
        ultimos = dict(self.motores[-2:])
        return ultimos["fraco"], ultimos["forte"]


class _Mesa:
    def __init__(self, tmp_path: Path, politica: Any = "auto") -> None:
        reader = EvdevReader(device_path=None)
        reader._device_path = None
        self.backend = PyDualSenseController(evdev_reader=reader)
        self.handles = [
            _Handle(b, t) for b, t in zip(BATERIAS, ("USB", "USB", "BT", "BT"), strict=True)
        ]
        self.backend._handles = dict(zip(MACS, self.handles, strict=True))
        self.backend._primary_key = MACS[0]
        self.store = StateStore()
        # O estado publicado é o do P1, e é o que as três cópias liam para os quatro.
        self.store.update_controller_state(
            ControllerState(battery_pct=BATERIAS[0], l2_raw=0, r2_raw=0,
                            connected=True, transport="usb")
        )
        self.config = DaemonConfig()
        self.config.rumble_policy = politica
        self.daemon = SimpleNamespace(
            config=self.config,
            store=self.store,
            controller=self.backend,
            _rumble_engine=None,
            _last_auto_mult=0.7,
            _last_auto_change_at=0.0,
        )
        self.server = IpcServer(
            controller=self.backend,
            store=self.store,
            profile_manager=ProfileManager(controller=self.backend, store=self.store),
            socket_path=tmp_path / "funil.sock",
            daemon=self.daemon,
        )

    def com_orcamento(self, orcamento: str) -> None:
        self.config.orcamento_da_mesa = lambda: orcamento

    def limpar(self) -> None:
        for h in self.handles:
            h.motores.clear()


def _esperado(forca: float) -> tuple[int, int]:
    v = max(0, min(255, round(PEDIDO * forca)))
    return v, v


# 1. O `auto` de cada um, nos três caminhos.

def test_o_jogo_mirado_em_cada_um_sai_com_a_bateria_dele(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)

    pares = [
        gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=u)
        for u in UNIQS
    ]

    assert pares == [_esperado(f) for f in FORCAS_DO_AUTO]
    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO], (
        "a bateria do P1 decidiu a força dos quatro"
    )


@pytest.mark.asyncio
async def test_o_gesto_da_aba_em_cada_um_sai_com_a_bateria_dele(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)

    for u in UNIQS:
        resposta = await mesa.server._handle_rumble_set(
            {"weak": PEDIDO, "strong": PEDIDO, "uniq": u}
        )
        assert resposta["status"] == "ok"

    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO]


def test_o_par_fixado_de_cada_um_no_reassert_sai_com_a_bateria_dele(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    for u in UNIQS:
        fixar_par(mesa.config, u, PEDIDO, PEDIDO, 0.0, so_este=True)

    reassert_rumble(mesa.daemon, 0.1)

    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO]


@pytest.mark.asyncio
async def test_sem_endereco_cada_um_recebe_a_sua_forca(tmp_path: Path) -> None:
    """O «mesa inteira» (o `rumble.set` sem alvo, o reassert dele e o jogo sem
    endereço) escreve controle a controle, e não a força do P1 nos quatro."""
    mesa = _Mesa(tmp_path)

    assert (await mesa.server._handle_rumble_set(
        {"weak": PEDIDO, "strong": PEDIDO}))["status"] == "ok"
    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO]

    mesa.limpar()
    reassert_rumble(mesa.daemon, 0.1)
    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO]

    mesa.config.rumble_active = None
    mesa.limpar()
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO)
    assert [h.par() for h in mesa.handles] == [_esperado(f) for f in FORCAS_DO_AUTO]


@pytest.mark.asyncio
async def test_sem_endereco_o_conectado_sem_mac_nao_fica_calado(tmp_path: Path) -> None:
    """Um conectado guardado pelo caminho (sem MAC) recebe o «mesa inteira».

    Controle a controle só vale quando todos têm MAC: com um sem, a escrita
    volta ao ``set_rumble`` de sempre, que alcança os cinco com a força do P1.
    """
    mesa = _Mesa(tmp_path)
    sem_mac = _Handle(90, "USB")
    mesa.backend._handles["/dev/hidraw-de-teste-9"] = sem_mac

    assert (await mesa.server._handle_rumble_set(
        {"weak": PEDIDO, "strong": PEDIDO}))["status"] == "ok"

    assert sem_mac.par() == _esperado(FORCAS_DO_AUTO[0]), (
        "o controle sem MAC ficou calado no «mesa inteira»"
    )
    assert [h.par() for h in mesa.handles] == [_esperado(FORCAS_DO_AUTO[0])] * 4


def test_o_debounce_e_de_cada_um(tmp_path: Path) -> None:
    """A bateria do P3 caindo não arrasta a âncora do P1, nem o contrário."""
    mesa = _Mesa(tmp_path)
    forca = gp._game_rumble_mult
    assert [forca(mesa.daemon, 0.5, u) for u in UNIQS] == list(FORCAS_DO_AUTO)
    mesa.handles[0].battery.Level = 15

    assert forca(mesa.daemon, 2.0, UNIQS[0]) == 1.0, (
        "o P1 trocou de degrau antes do debounce dele"
    )
    assert gp._game_rumble_mult(mesa.daemon, 2.0, UNIQS[2]) == 0.3
    assert gp._game_rumble_mult(mesa.daemon, 7.0, UNIQS[0]) == 0.3
    assert mesa.daemon._last_auto_mult == 0.3, (
        "o `rumble_mult_applied` do `state_full` deixou de dizer o do primário"
    )


# 2. O teto do orçamento vence a peça.

@pytest.mark.parametrize("global_do_perfil", ["balanceado", "economia"])
def test_a_peca_em_maximo_nao_fura_o_teto(tmp_path: Path, global_do_perfil: str,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales
    from hefesto_dualsense4unix.profiles.schema import Profile

    perfil = Profile.model_validate({
        "name": "Funil", "match": {"type": "criteria"},
        "rumble": {"policy": global_do_perfil},
        "controllers": {UNIQS[1]: {"rumble": {"policy": "max"}}},
    })
    escalas = _controllers_to_rumble_scales(perfil.controllers, perfil.rumble)
    mesa = _Mesa(tmp_path, politica=global_do_perfil)
    mesa.com_orcamento("economia")
    mesa.backend.set_rumble_scales(escalas)
    teto = round(PEDIDO * RUMBLE_POLICY_MULT["economia"])
    na_haptica: list[tuple[int, int]] = []

    def _haptica(_d: Any, _vpad: Any, _u: Any, weak: int, strong: int, **_: Any) -> bool:
        na_haptica.append((weak, strong))
        return True

    par = gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    assert par is not None and max(par) <= teto
    assert max(mesa.handles[1].par()) <= teto, (
        f"o motor do P2 recebeu {mesa.handles[1].par()}, acima do teto de {teto}"
    )

    monkeypatch.setattr(gp, "_levar_a_haptica_fina", _haptica)
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1],
                         vpad=object())
    assert na_haptica and max(na_haptica[-1]) <= teto, (
        f"a háptica fina recebeu {na_haptica[-1]}, acima do teto de {teto}"
    )


# 3. No modo Xbox, a háptica fina recebe o par com a peça.

def test_a_haptica_fina_recebe_o_par_com_a_forca_da_peca(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales
    from hefesto_dualsense4unix.profiles.schema import Profile

    perfil = Profile.model_validate({
        "name": "Funil", "match": {"type": "criteria"},
        "rumble": {"policy": "balanceado"},
        "controllers": {UNIQS[2]: {"rumble": {"policy": "economia"}}},
    })
    mesa = _Mesa(tmp_path, politica="balanceado")
    mesa.backend.set_rumble_scales(
        _controllers_to_rumble_scales(perfil.controllers, perfil.rumble))
    na_haptica: list[tuple[int, int]] = []

    def _haptica(_d: Any, _vpad: Any, _u: Any, weak: int, strong: int, **_: Any) -> bool:
        na_haptica.append((weak, strong))
        return True

    monkeypatch.setattr(gp, "_levar_a_haptica_fina", _haptica)

    par = gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[2],
                               vpad=object())

    assert na_haptica == [_esperado(0.3)], (
        "a háptica fina recebeu o par antes do «30% da força» do cartão"
    )
    assert par == _esperado(0.3)
    assert mesa.handles[2].par() == (0, 0), "com a háptica levando, os motores do HID calam"


# 4. Sem peça nem orçamento, nada muda.

@pytest.mark.asyncio
async def test_em_balanceado_o_par_e_o_de_antes(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path, politica="balanceado")

    for u in UNIQS[:3]:
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220, "uniq": u})
    # O P4 fica sem par fixado: o par fixado vence o jogo, e aqui a régua é o jogo.
    gp.apply_game_rumble(mesa.daemon, 33, 7, target_uniq=UNIQS[3])

    assert [h.par() for h in mesa.handles[:3]] == [(160, 220)] * 3
    assert mesa.handles[3].par() == (33, 7)
