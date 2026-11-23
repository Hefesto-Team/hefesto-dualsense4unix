"""A luz e o número do controle não se apagam quando o jogo abre.

A sequência do diário de 23/11/2026 (o Dungeons II aberto, um controle no cabo): o perfil do jogo
tem a seção de base com a barra preta e as cinco lâmpadas falsas, e a seção do controle com a
barra branca e o número 1. O jogo escreveu «nenhuma lâmpada» no pad virtual às 01h47 com a
autoridade dele; a autoridade voltou ao Hefesto às 02h58, o controle saiu e voltou às 04h00 e a
autoridade voltou ao jogo às 04h01. O zero guardado na camada do jogo venceu, e as lâmpadas do
controle apagaram. D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO: o desenho sem lâmpada não é número
e não chega a controle nenhum; o número de verdade que o jogo escreve segue a
D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO.
"""
from __future__ import annotations

import os
import pathlib
import select
import struct
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import evdev_reader, external_leds
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.subsystems import gamepad
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _GAME_REPLICA_GRACE_S,
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_CLOSE,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
    _GadgetDoPad,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile

JOGADORES = (1, 2, 3, 4)
MACS = {n: f"AA:BB:CC:00:00:0{n}" for n in JOGADORES}
UNIQS = {n: f"aabbcc00000{n}" for n in JOGADORES}
CORES = {1: (255, 255, 255), 2: (255, 0, 0), 3: (128, 0, 255), 4: (255, 128, 0)}
NENHUMA = (False, False, False, False, False)
PRODUTO = {"dualsense": 0x0CE6, "edge": 0x0DF2}
VIA_DA_MESA_MISTURADA = {1: "cabo", 2: "radio", 3: "cabo", 4: "radio"}
EXTENSAO = "extensao:imersao"  # (noqa-acento)


class _No:
    """O nó da classe LED de mentira: guarda o que se escreveu."""

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.numeros: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return None


def _handle(via: str, produto: int = PRODUTO["dualsense"]) -> SimpleNamespace:
    handle = SimpleNamespace(
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None,
        is_edge=produto == PRODUTO["edge"], connected=True, escritos=[],
    )
    if via == "radio":
        handle.conType = SimpleNamespace(name="BT")
        handle.writeReport = handle.escritos.append
    return handle


@pytest.fixture(autouse=True)
def _sem_os_nos_de_entrada_da_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evdev_reader, "find_dualsense_evdev", lambda: None)


@pytest.fixture
def registro(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O registro de identidade REAL num disco de mentira, sem ler o plástico pelo cabo."""
    from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
    from hefesto_dualsense4unix.integrations import cor_do_plastico as cp
    from hefesto_dualsense4unix.utils import xdg_paths

    def config_de_mentira(ensure: bool = False) -> pathlib.Path:
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", config_de_mentira)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "boot-da-luz")
    monkeypatch.setattr(
        cp, "ler_identidade_pelo_cabo",
        lambda uniq: cp.IdentidadeDeFabrica(serial="DUBLE01##########", cor=None))
    return id_mod.ControllerIdentityRegistry()


def _perfil_do_diario(jogadores: tuple[int, ...] = (1,), *, modo_da_luz: str = "personalizado"
                      ) -> Profile:
    """O perfil do jogo como estava no disco: a base preta e a seção de cada controle com a cor."""
    return Profile.model_validate({
        "name": "Jogo do diário",
        "match": {"type": "criteria", "window_class": ["steam_app_1"]},
        "priority": 80,
        "triggers": {"left": {"mode": "Rigid", "params": [5, 200]},
                     "right": {"mode": "Rigid", "params": [5, 200]},
                     "modo": EXTENSAO},
        "leds": {"lightbar": [0, 0, 0], "player_leds": [False] * 5,
                 "lightbar_brightness": 1.0, "auto_player_colors": True,
                 "player_led_brightness": "fraco", "modo": modo_da_luz},
        "controllers": {
            UNIQS[n]: {"leds": {"lightbar": list(CORES[n]), "lightbar_para_o_numero": n,
                                "player_led_brightness": "forte"}}
            for n in jogadores
        },
        "controles_modo": "personalizado",
    })


class _Mesa:
    """Controles reais do backend, o registro real e a autoridade na mão do teste."""

    def __init__(self, registro: Any, jogadores: tuple[int, ...] = (1,),
                 vias: dict[int, str] | None = None, produto: int = PRODUTO["dualsense"]) -> None:
        from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod

        self.sinal = SimpleNamespace(valor="daemon")
        self.ctl = bp.PyDualSenseController()
        self.nos = {n: _No() for n in jogadores}
        vias = vias or {}
        self.handles = {n: _handle(vias.get(n, "cabo"), produto) for n in jogadores}
        self.ctl._handles = {MACS[n]: self.handles[n] for n in jogadores}
        self.ctl._sysfs = {MACS[n]: self.nos[n] for n in jogadores}
        self.ctl._primary_key = MACS[jogadores[0]]
        self.ctl.set_game_authority_provider(lambda: self.sinal.valor)
        self.provider: Any = id_mod.make_auto_output_provider(registro)
        registro.sync_connected([UNIQS[n] for n in jogadores])
        registro.liberar_as_lampadas()
        self.ctl.set_auto_output_provider(self.provider)
        self.daemon = SimpleNamespace(
            controller=self.ctl, identity_registry=registro, display_authority="daemon",
            sinal=self.sinal)

    def autoridade(self, para: str) -> None:
        self.sinal.valor = para
        self.daemon.display_authority = para

    def lancar(self, perfil: Profile) -> None:
        ProfileManager(controller=self.ctl).apply(perfil, origin="launch")

    def o_jogo_acende(self, bits: tuple[bool, ...], n: int = 1) -> None:
        gamepad.apply_game_player_leds(self.daemon, bits, target_uniq=MACS[n])  # type: ignore[arg-type]

    def resolvido(self, n: int = 1) -> bp._DesiredOutput:
        with self.ctl._io_lock:
            return self.ctl._merged_desired_for_key(MACS[n])

    def numero(self, n: int = 1) -> tuple[bool, ...]:
        return player_led_pattern(int(self.provider.numero_do_slot(UNIQS[n])))


def _o_que_o_controle_mostra(mesa: _Mesa, n: int = 1) -> tuple[Any, Any]:
    r = mesa.resolvido(n)
    return r.led, r.player_leds


def test_a_sequencia_do_diario_deixa_a_cor_e_o_numero_do_controle(registro: Any) -> None:
    """D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO.

    MORDIDA: tirar o `if not any(bits)` de `gamepad.apply_game_player_leds` e o zero do jogo,
    guardado na camada dele, vence na volta da autoridade: as lâmpadas saem `(False,) * 5`.
    """
    mesa = _Mesa(registro)
    mesa.lancar(_perfil_do_diario())
    assert _o_que_o_controle_mostra(mesa) == (CORES[1], player_led_pattern(1))

    mesa.autoridade("game")
    marca = len(mesa.nos[1].numeros)
    mesa.o_jogo_acende(NENHUMA)
    assert _o_que_o_controle_mostra(mesa) == (CORES[1], player_led_pattern(1))
    mesa.autoridade("daemon")
    mesa.ctl.reassert_resolved_outputs()
    mesa.autoridade("game")
    mesa.ctl.reassert_resolved_outputs()
    assert NENHUMA not in mesa.nos[1].numeros[marca:]
    mesa.lancar(_perfil_do_diario())

    assert _o_que_o_controle_mostra(mesa) == (CORES[1], player_led_pattern(1))
    assert mesa.nos[1].numeros[-1] == player_led_pattern(1)
    assert mesa.nos[1].cores[-1] == CORES[1]
    assert UNIQS[1] not in mesa.ctl._game_output_by_uniq


def test_o_zero_com_o_hefesto_na_autoridade_nao_fica_retido(registro: Any) -> None:
    """D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO: nem retido, para a abertura não o devolver."""
    mesa = _Mesa(registro)
    mesa.lancar(_perfil_do_diario())

    mesa.o_jogo_acende(NENHUMA)

    assert UNIQS[1] not in mesa.ctl._retained_game_outputs
    mesa.autoridade("game")
    mesa.ctl.replay_retained_game_outputs()
    assert _o_que_o_controle_mostra(mesa) == (CORES[1], player_led_pattern(1))


def test_o_numero_que_o_jogo_escreve_vale_e_o_zero_depois_nao_o_apaga(registro: Any) -> None:
    """D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO e D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO."""
    mesa = _Mesa(registro)
    mesa.lancar(_perfil_do_diario())
    mesa.autoridade("game")
    marca = len(mesa.nos[1].numeros)

    mesa.o_jogo_acende(player_led_pattern(2))
    assert mesa.resolvido().player_leds == player_led_pattern(2)
    mesa.o_jogo_acende(NENHUMA)
    mesa.ctl.reassert_resolved_outputs()

    assert mesa.resolvido().player_leds == player_led_pattern(2)
    assert mesa.nos[1].numeros[-1] == player_led_pattern(2)
    assert NENHUMA not in mesa.nos[1].numeros[marca:]


def test_o_modo_da_extensao_sem_a_extensao_acende_a_luz_do_controle(
    registro: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com a seção da luz no modo da extensão e a extensão fora, vale a seção do controle."""
    from hefesto_dualsense4unix.mods import porta

    monkeypatch.setattr(porta, "extensoes_vivas", lambda: frozenset())
    mesa = _Mesa(registro)
    mesa.autoridade("game")
    mesa.lancar(_perfil_do_diario(modo_da_luz=EXTENSAO))

    assert _o_que_o_controle_mostra(mesa) == (CORES[1], player_led_pattern(1))


def test_a_extensao_viva_e_dona_da_luz_pinta_a_barra_e_nunca_o_escuro(
    registro: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A extensão viva e dona da luz pinta a barra; antes de pintar, vale a cor automática."""
    from hefesto_dualsense4unix.mods import porta

    monkeypatch.setattr(porta, "extensoes_vivas", lambda: frozenset({"imersao"}))
    mesa = _Mesa(registro)
    mesa.autoridade("game")
    mesa.lancar(_perfil_do_diario(modo_da_luz=EXTENSAO))

    led, numero = _o_que_o_controle_mostra(mesa)
    assert led not in (None, (0, 0, 0))
    assert numero == player_led_pattern(1)
    mesa.ctl.apply_extension_output_for(MACS[1], OutputSpec(led=(0, 200, 0)))
    assert _o_que_o_controle_mostra(mesa) == ((0, 200, 0), player_led_pattern(1))


def _report_do_jogo(bits: tuple[bool, ...], cor: tuple[int, int, int]) -> bytes:
    """O report 0x02 do jogo com as duas bandeiras: as luzes de jogador e a barra."""
    corpo = bytearray(47)
    corpo[1] = uhid_gamepad._PLAYER_INDICATOR_CONTROL_ENABLE | uhid_gamepad._LIGHTBAR_CONTROL_ENABLE
    corpo[43] = sum(1 << i for i, b in enumerate(bits) if b)
    corpo[44:47] = bytes(cor)
    return bytes([0x02]) + bytes(corpo)


class _Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _pad_em_sessao(mesa: _Mesa, player: int, modo: str, caminho: str) -> UhidDualSense:
    """O pad do jogador com o jogo aberto, pelos ralos do produto (o do P1 ou o do co-op)."""
    relogio = _Relogio()
    ralos = (gamepad.make_primary_replica_sinks(mesa.daemon)
             if player == 1 else CoopManager(mesa.daemon)._make_player_replica_sinks(MACS[player]))
    pad = UhidDualSense(player=player, identity=MACS[player], product=PRODUTO[modo],
                        time_fn=relogio, sleep_fn=lambda _s: None, **ralos)
    if caminho == "gadget":
        pad._gadget = _GadgetDoPad(cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}")
    pad._handle_event(struct.pack("<I", UHID_START))
    pad._handle_event(struct.pack("<I", UHID_OPEN))
    relogio.t = _GAME_REPLICA_GRACE_S + 0.5
    return pad


def _o_jogo_escreve(pad: UhidDualSense, caminho: str, report: bytes) -> None:
    """O report chega como chega no produto: o evento do uhid, ou o `/dev/hidgN` do gadget."""
    if caminho == "uhid":
        pad._handle_event(
            struct.pack("<I", UHID_OUTPUT)
            + report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
            + struct.pack("<HB", len(report), 1))
        return
    leitura, escrita = os.pipe()
    try:
        os.set_blocking(leitura, False)
        os.write(escrita, report)
        uhid_gamepad._drenar_o_gadget(pad, leitura, select.POLLIN)
    finally:
        os.close(leitura)
        os.close(escrita)


@pytest.mark.parametrize("caminho", ["uhid", "gadget"])
@pytest.mark.parametrize("modo", ["dualsense", "edge"])
@pytest.mark.parametrize("aparelho", ["dualsense", "edge"])
def test_quatro_controles_no_cabo_e_no_radio_seguem_cada_um_com_o_seu(
    registro: Any, aparelho: str, modo: str, caminho: str
) -> None:
    """D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO: P1 e P3 no cabo, P2 e P4 no rádio.

    O jogo escreve «nenhuma lâmpada» e a barra preta em cada pad, que é o que o SDL manda antes de
    numerar; cada controle segue com a cor da seção dele e o número dele, sem um decidir pelo outro.
    MORDIDA: sem o `if not any(bits)` os quatro apagam.
    """
    mesa = _Mesa(registro, JOGADORES, VIA_DA_MESA_MISTURADA, PRODUTO[aparelho])
    mesa.lancar(_perfil_do_diario(JOGADORES))
    mesa.autoridade("game")
    pads = {n: _pad_em_sessao(mesa, n, modo, caminho) for n in JOGADORES}
    marcas = {n: len(mesa.nos[n].numeros) for n in JOGADORES}

    for pad in pads.values():
        _o_jogo_escreve(pad, caminho, _report_do_jogo(NENHUMA, (0, 0, 0)))
    mesa.ctl.reassert_resolved_outputs()

    for n in JOGADORES:
        assert _o_que_o_controle_mostra(mesa, n) == (CORES[n], mesa.numero(n)), n
        assert NENHUMA not in mesa.nos[n].numeros[marcas[n]:], n
        if VIA_DA_MESA_MISTURADA[n] == "radio":
            assert mesa.handles[n]._quadro_da_luz[1] == mesa.numero(n), n
    assert len({mesa.numero(n) for n in JOGADORES}) == 4
    for pad in pads.values():
        pad._handle_event(struct.pack("<I", UHID_CLOSE))
    for n in JOGADORES:
        assert _o_que_o_controle_mostra(mesa, n) == (CORES[n], mesa.numero(n)), n


def test_o_controle_sai_e_volta_com_o_jogo_aberto_e_o_jogo_reabre(registro: Any) -> None:
    """O controle que sai e volta, e o jogo que fecha e abre de novo: nunca o escuro por omissão."""
    mesa = _Mesa(registro, (1, 2), {1: "cabo", 2: "radio"})
    mesa.lancar(_perfil_do_diario((1, 2)))
    mesa.autoridade("game")
    marcas = {n: len(mesa.nos[n].numeros) for n in (1, 2)}

    handle, no = mesa.ctl._handles.pop(MACS[2]), mesa.ctl._sysfs.pop(MACS[2])
    mesa.o_jogo_acende(NENHUMA, 2)
    mesa.ctl._handles[MACS[2]], mesa.ctl._sysfs[MACS[2]] = handle, no
    mesa.ctl.reassert_resolved_outputs()
    assert _o_que_o_controle_mostra(mesa, 2) == (CORES[2], mesa.numero(2))

    for _vez in range(2):
        pad = _pad_em_sessao(mesa, 1, "dualsense", "uhid")
        _o_jogo_escreve(pad, "uhid", _report_do_jogo(NENHUMA, (0, 0, 0)))
        assert _o_que_o_controle_mostra(mesa, 1) == (CORES[1], mesa.numero(1))
        pad._handle_event(struct.pack("<I", UHID_CLOSE))
        assert _o_que_o_controle_mostra(mesa, 1) == (CORES[1], mesa.numero(1))
    assert NENHUMA not in mesa.nos[1].numeros[marcas[1]:]
    assert NENHUMA not in mesa.nos[2].numeros[marcas[2]:]


def test_o_controle_de_fora_nao_apaga_com_o_zero_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-2311-O-ZERO-DO-JOGO-NAO-APAGA-O-NUMERO no controle de fora (Pro Controller, 8BitDo).

    MORDIDA: devolver o `if numero is None` em `_o_numero_do_jogo_no_controle_de_fora` e o zero
    chega ao `acender_o_numero_do_jogo`, que apaga as luzes.
    """
    acesos: list[int] = []
    monkeypatch.setattr(external_leds, "hidraw_do_uniq", lambda uniq: "/dev/hidraw99")
    monkeypatch.setattr(external_leds, "luzes_do_externo", lambda hidraw, *a: ["luz"])
    monkeypatch.setattr(external_leds, "retrato_das_luzes", lambda caminhos: {})
    def acender(hidraw: str | None, numero: int, *_resto: Any) -> bool:
        acesos.append(numero)
        return True

    monkeypatch.setattr(external_leds, "acender_o_numero_do_jogo", acender)
    daemon = SimpleNamespace(controller=SimpleNamespace(), display_authority="game")

    gamepad.apply_game_player_leds(daemon, player_led_pattern(2), target_uniq=MACS[2])
    gamepad.apply_game_player_leds(daemon, NENHUMA, target_uniq=MACS[2])

    assert acesos == [2]


def _a_autoridade_cruza_a_borda(mesa: _Mesa, para: str) -> None:
    """A troca de autoridade como o tique do sinal a faz: o valor muda e a borda roda."""
    from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal

    anterior = mesa.sinal.valor
    mesa.autoridade(para)
    GameSignal().na_borda(mesa.daemon, anterior, para)


@pytest.mark.parametrize("vias", [(("cabo", "radio")), (("radio", "cabo"))])
def test_a_barra_preta_do_jogo_que_saiu_nao_vence_no_jogo_seguinte(
    registro: Any, vias: tuple[str, str]
) -> None:
    """D-0410-PERFIL-ATE-O-JOGO-PROVAR: a saída do jogo zera a camada dele.

    O diário de 22 e 23/11: o jogo pintou a barra (o verde de 22/11, 21h42), escreveu a barra
    preta calado (o campo já estava na camada) com a autoridade dele, saiu às 02h58m55s, e o
    jogo seguinte ganhou a autoridade às 04h01m57s: o preto guardado venceu. P1 e P2, cabo e
    rádio nas duas ordens. MORDIDA: tirar o `saida("end_game_sessions_on_exit")` de
    `GameSignal.na_borda` e a barra sai `(0, 0, 0)` na volta da autoridade.
    """
    mesa = _Mesa(registro, (1, 2), {1: vias[0], 2: vias[1]})
    mesa.lancar(_perfil_do_diario((1, 2)))
    _a_autoridade_cruza_a_borda(mesa, "game")
    for n in (1, 2):
        mesa.ctl.set_game_output_for(MACS[n], led=(0, 64, 0))
        mesa.ctl.set_game_output_for(MACS[n], led=(0, 0, 0))
        mesa.o_jogo_acende(NENHUMA, n)
        assert mesa.resolvido(n).led == (0, 0, 0), n

    _a_autoridade_cruza_a_borda(mesa, "daemon")
    _a_autoridade_cruza_a_borda(mesa, "game")
    mesa.lancar(_perfil_do_diario((1, 2)))

    for n in (1, 2):
        assert _o_que_o_controle_mostra(mesa, n) == (CORES[n], mesa.numero(n)), n
        assert mesa.nos[n].cores[-1] == CORES[n], n
        assert UNIQS[n] not in mesa.ctl._game_output_by_uniq, n
        assert UNIQS[n] not in mesa.ctl._jogo_provou_a_luz, n
    mesa.ctl.set_game_output_for(MACS[1], led=(0, 0, 0))
    assert mesa.resolvido(1).led == CORES[1]


def test_o_jogo_aberto_segue_mandando_na_barra_que_pintou(registro: Any) -> None:
    """D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO: sem a saída do jogo, a cor dele segue valendo."""
    mesa = _Mesa(registro)
    mesa.lancar(_perfil_do_diario())
    _a_autoridade_cruza_a_borda(mesa, "game")
    mesa.ctl.set_game_output_for(MACS[1], led=(0, 0, 64))
    mesa.lancar(_perfil_do_diario())

    assert mesa.resolvido().led == (0, 0, 64)
    assert UNIQS[1] in mesa.ctl._jogo_provou_a_luz
