"""O jogo nativo do Linux, sem appid, também está em cena para o `jogo.estilo` (16/11/2026).

O-JOGO-SEM-APPID-TAMBEM-ESTA-EM-CENA-01. O `perfil.trocou` só conhecia jogo pelo appid, e o
`carga_do_estilo` só levava o estilo com `jogo`: num jogo nativo, com a autoridade do jogo e sem
appid, o modo do controle dizia «há jogo» e o `jogo.estilo` saía nulo. A cura: o anunciador leva o
`em_cena` (geral e por controle) pela mesma pergunta do modo (`ha_jogo_em_cena`), e o estilo sai
por ele; o `jogo` segue sendo `steam_app_<N>` ou `None`.

MORDIDA: tirar o `em_cena` do anunciador reprova o caso nativo.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig, ha_jogo_em_cena
from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AnunciadorDoJogo
from hefesto_dualsense4unix.mods.porta import carga_do_estilo
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController

APPID_FORJADO = 9942231
MACS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
PERFIL = "Jogo de terror"

MESAS = {
    "4 cabos": ("usb", "usb", "usb", "usb"),
    "3 cabos e 1 rádio": ("usb", "usb", "usb", "bt"),
    "2 e 2": ("bt", "usb", "bt", "usb"),
    "1 cabo e 3 rádios": ("bt", "bt", "usb", "bt"),
    "4 rádios": ("bt", "bt", "bt", "bt"),
}

CENAS = {
    "com appid": ("game", APPID_FORJADO),
    "nativo sem appid": ("game", None),
    "sem jogo": ("daemon", None),
}


def _servico(transportes: tuple[str, ...], autoridade: str, appid: int | None) -> Daemon:
    """O serviço de verdade (a autoridade e o appid são os do `Daemon`), com P2 a P4 no co-op."""
    d = Daemon(controller=FakeController(transport=transportes[0]),  # type: ignore[arg-type]
               config=DaemonConfig())
    d.controller.primary_uniq = MACS[0]  # type: ignore[attr-defined]
    d._game_signal = SimpleNamespace(authority=autoridade)  # type: ignore[assignment]
    d._appid_da_evidencia = appid
    d._coop_manager = SimpleNamespace(_players={  # type: ignore[assignment]
        mac: SimpleNamespace(reader=None, vpad=None, motion_reader=None, transport=via)
        for mac, via in zip(MACS[1:], transportes[1:], strict=True)})
    numeros = {mac: n for n, mac in enumerate(MACS, start=1)}
    d.identity_registry = SimpleNamespace(
        numero_da_lampada=lambda uniq, assign=True: numeros[uniq])
    return d


def _ultimo(fila: Any) -> dict[str, Any]:
    vistos = []
    while not fila.empty():
        vistos.append(fila.get_nowait())
    assert vistos, "o anunciador não disse nada"
    return vistos[-1]


@pytest.fixture
def perfil_de_terror() -> str:
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=0, estilo="terror"))
    return PERFIL


@pytest.mark.parametrize("mesa", sorted(MESAS))
@pytest.mark.parametrize("cena", sorted(CENAS))
def test_o_estilo_sai_com_o_jogo_em_cena_e_nulo_sem_ele(
    cena: str, mesa: str, perfil_de_terror: str
) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o jogo nativo também está em cena, nos quatro."""
    autoridade, appid = CENAS[cena]
    d = _servico(MESAS[mesa], autoridade, appid)
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    AnunciadorDoJogo(bus, SimpleNamespace(active_profile=perfil_de_terror), d).ver()

    dito = _ultimo(fila)
    em_cena = ha_jogo_em_cena(d)
    assert em_cena is (cena != "sem jogo"), "premissa: a pergunta do modo"
    assert dito["em_cena"] is em_cena
    assert [c["em_cena"] for c in dito["controles"]] == [em_cena] * 4
    assert dito["jogo"] == (f"steam_app_{appid}" if appid is not None else None)

    carga = carga_do_estilo(dito)
    assert carga is not None
    esperado = "terror" if em_cena else None
    assert carga["estilo"] == esperado
    assert carga["controles"] == [{"jogador": n, "estilo": esperado} for n in (1, 2, 3, 4)]
    assert carga["jogo"] == dito["jogo"]


@pytest.mark.parametrize("mesa", sorted(MESAS))
def test_o_jogo_nativo_que_abre_e_fecha_leva_o_estilo_e_o_tira(
    mesa: str, perfil_de_terror: str
) -> None:
    """Abrir o jogo nativo traz o estilo; o controle que sai e volta segue nele; fechar o tira."""
    d = _servico(MESAS[mesa], "daemon", None)
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    anunciador = AnunciadorDoJogo(bus, SimpleNamespace(active_profile=perfil_de_terror), d)
    anunciador.ver()
    assert carga_do_estilo(_ultimo(fila))["estilo"] is None  # type: ignore[index]

    d._game_signal = SimpleNamespace(authority="game")  # type: ignore[assignment]
    anunciador.ver()
    assert carga_do_estilo(_ultimo(fila))["estilo"] == "terror"  # type: ignore[index]

    jogadores = d._coop_manager._players  # type: ignore[union-attr]
    saiu = jogadores.pop(MACS[2])
    anunciador.ver()
    carga = carga_do_estilo(_ultimo(fila))
    assert carga is not None and [c["estilo"] for c in carga["controles"]] == ["terror"] * 3
    jogadores[MACS[2]] = saiu
    anunciador.ver()
    carga = carga_do_estilo(_ultimo(fila))
    assert carga is not None and [c["estilo"] for c in carga["controles"]] == ["terror"] * 4

    d._game_signal = SimpleNamespace(authority="daemon")  # type: ignore[assignment]
    anunciador.ver()
    carga = carga_do_estilo(_ultimo(fila))
    assert carga is not None and carga["estilo"] is None
    assert [c["estilo"] for c in carga["controles"]] == [None] * 4


def test_o_controle_fora_do_jogo_de_outro_nao_leva_o_estilo(perfil_de_terror: str) -> None:
    """Com o jogo de cada controle (`jogo_de`), quem está fora do jogo com appid fica sem estilo."""
    d = _servico(MESAS["2 e 2"], "game", APPID_FORJADO)
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    jogos = {MACS[0]: APPID_FORJADO, MACS[2]: APPID_FORJADO}
    AnunciadorDoJogo(bus, SimpleNamespace(active_profile=perfil_de_terror), d, jogos.get).ver()

    dito = _ultimo(fila)
    assert [c["em_cena"] for c in dito["controles"]] == [True, False, True, False]
    carga = carga_do_estilo(dito)
    assert carga is not None
    assert [c["estilo"] for c in carga["controles"]] == ["terror", None, "terror", None]
