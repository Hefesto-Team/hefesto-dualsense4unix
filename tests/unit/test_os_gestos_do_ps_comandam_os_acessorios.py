"""OS-GESTOS-DO-PS-COMANDAM-OS-ACESSORIOS-01 — o PS com os gatilhos comanda os acessórios.

Relógio injetado e pad virtual de mentira. A máquina (``GestosDosAcessorios``) é lida pelo
``HotkeyManager`` de verdade; o pad é o ``UinputGamepad`` do produto com o nó trocado por um
gravador dos eixos e das teclas que o jogo leria; o supervisor roda um processo filho real.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import textwrap
import time
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    dizer_o_gesto_dos_acessorios,
    gestos_dos_acessorios_valem,
)
from hefesto_dualsense4unix.daemon.subsystems.poll import observar_os_atalhos
from hefesto_dualsense4unix.integrations.gestos_dos_acessorios import Opcoes
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from hefesto_dualsense4unix.mods.supervisor import Supervisor, _Vigiada

P1 = "aabbcc000001"
P2 = "aabbcc000002"
PS_R2 = ("ps", "r2_btn")
FUNDO = 242
META = 102
PADRAO = Opcoes()


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class Cena:
    """Um ``HotkeyManager`` com os gestos ligados (ou não) e o relógio na mão do teste."""

    def __init__(self, opcoes: Opcoes | None = PADRAO) -> None:
        self.relogio = Relogio()
        self.opcoes = opcoes
        self.saiu: list[tuple[str | None, str, float]] = []
        self.steam = 0
        self.mgr = HotkeyManager(
            on_ps_solo=self._steam,
            gestos_valem=lambda de: self.opcoes,
            on_gesto=lambda de, gesto, valor: self.saiu.append((de, gesto, valor)),
            relogio=self.relogio,
        )

    def _steam(self) -> None:
        self.steam += 1

    def tique(
        self, botoes: tuple[str, ...] = (), l2: int = 0, r2: int = 0, *, de: str = P1,
        dt: float = 1 / 60,
    ) -> str | None:
        self.relogio.t += dt
        return self.mgr.observe(botoes, now=self.relogio.t, de=de, gatilhos=(l2, r2))

    def segura(
        self, segundos: float, botoes: tuple[str, ...] = (), l2: int = 0, r2: int = 0,
        *, de: str = P1,
    ) -> None:
        for _ in range(max(1, round(segundos * 60))):
            self.tique(botoes, l2, r2, de=de)

    def solta(self, segundos: float = 0.1, *, de: str = P1) -> None:
        self.segura(segundos, de=de)

    @property
    def gestos(self) -> list[str]:
        return [g for _de, g, _v in self.saiu]


def test_ps_mais_r2_de_80_ms_publica_um_sobe() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.08, PS_R2, r2=255)
    cena.solta()
    assert cena.gestos == ["sobe"]
    assert cena.saiu[0][0] == P1


def test_r2_segurado_repete_o_sobe_a_cada_300_ms_depois_de_500() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(2.0, PS_R2, r2=255)
    cena.solta()
    assert set(cena.gestos) == {"sobe"}
    assert 6 <= len(cena.gestos) <= 8, f"o primeiro e uma repetição a cada 0,3 s: {cena.gestos}"
    cena2 = Cena()
    cena2.solta()
    instantes: list[float] = []
    for _ in range(round(2.0 * 60)):
        antes = len(cena2.saiu)
        cena2.tique(PS_R2, r2=255)
        if len(cena2.saiu) > antes:
            instantes.append(cena2.relogio.t)
    folgas = [b - a for a, b in pairwise(instantes)]
    assert folgas[0] >= 0.49, "a primeira repetição só depois de 0,5 s"
    assert all(0.28 <= f <= 0.36 for f in folgas[1:]), folgas


def test_o_l2_que_vai_ao_fundo_para_na_hora_e_nenhum_desce_sai() -> None:
    cena = Cena()
    cena.solta()
    for cru in (60, 120, 200, 229):
        cena.tique(("ps", "l2_btn"), l2=cru)
        assert cena.gestos == [], "abaixo do limiar nada saiu ainda"
    cena.tique(("ps", "l2_btn"), l2=FUNDO)
    assert cena.gestos == ["para"], "o para sai ao cruzar, sem esperar soltar"
    cena.segura(0.3, ("ps", "l2_btn"), l2=255)
    cena.solta()
    assert cena.gestos == ["para"], "soltar depois do fundo não desce nada"


def test_o_l2_leve_solto_desce_um_degrau() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.2, ("ps", "l2_btn"), l2=META)
    assert cena.gestos == [], "o desce só sai ao soltar: o freio do fundo ainda pode vir"
    cena.solta()
    assert cena.gestos == ["desce"]


def test_o_limiar_do_fundo_e_configuravel() -> None:
    cena = Cena(Opcoes.de({"limiar_fundo": 60}))
    cena.solta()
    cena.segura(0.1, ("ps", "l2_btn"), l2=170)
    assert cena.gestos == ["para"]


def test_o_segundo_ps_r2_em_350_ms_vira_surto_e_depois_volta_ao_sobe() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.05, PS_R2, r2=255)
    cena.solta(0.1)
    cena.segura(0.05, PS_R2, r2=255)
    cena.solta(0.1)
    assert cena.gestos == ["sobe", "surto"]
    cena.solta(1.0)
    cena.segura(0.05, PS_R2, r2=255)
    assert cena.gestos == ["sobe", "surto", "sobe"]


def test_r1_e_l1_trocam_o_perfil() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.1, ("ps", "r1"))
    cena.solta()
    cena.segura(0.1, ("ps", "l1"))
    assert cena.gestos == ["perfil_seguinte", "perfil_anterior"]


def test_sem_o_ps_o_r2_e_o_do_jogo() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(1.0, ("r2_btn",), r2=255)
    assert cena.gestos == []
    assert cena.mgr.combo_buttons_active({"r2_btn"}, de=P1, gatilhos=(0, 255)) == frozenset()
    assert cena.mgr.eixos_do_gesto({"r2_btn"}, (0, 255), de=P1) == frozenset()


def test_o_r2_apertado_muito_antes_do_ps_nao_entra_no_gesto() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.5, ("r2_btn",), r2=255)
    cena.tique(PS_R2, r2=255)
    assert cena.gestos == []
    assert cena.mgr.eixos_do_gesto(PS_R2, (0, 255), de=P1) == frozenset()


def test_o_r2_um_instante_antes_do_ps_ainda_e_o_gesto() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.03, ("r2_btn",), r2=255)
    cena.tique(PS_R2, r2=255)
    assert cena.gestos == ["sobe"]


def test_o_r2_lido_pelo_eixo_nao_vira_rajada_quando_o_calar_dos_botoes_le_sem_a_pressao() -> None:
    """O tique do pad lê o mesmo instante três vezes: o poll e o eixo com a pressão, o calar dos
    botões sem ela. Com o R2 a meio curso e sem o bit digital, a leitura sem pressão soltava o
    membro e a seguinte o reapertava: um «sobe» (ou um surto) a cada tique.

    Prova da D-1610-A-PRESSAO-DO-GATILHO-FICA-NA-MAO-DO-CONTROLE.
    """
    cena = Cena()
    cena.solta()
    for _ in range(round(1.0 * 60)):
        cena.relogio.t += 1 / 60
        t = cena.relogio.t
        cena.mgr.observe(("ps",), now=t, de=P1, gatilhos=(0, 100))
        cena.mgr.combo_buttons_active({"ps"}, de=P1, now=t)
        cena.mgr.eixos_do_gesto({"ps"}, (0, 100), de=P1, now=t)
    assert set(cena.gestos) == {"sobe"}, cena.gestos
    assert len(cena.gestos) == 3, f"o primeiro e as repetições de 0,5 s e 0,8 s: {cena.gestos}"


def test_modificacao_desligada_nao_publica_nada_e_o_r2_chega_como_hoje() -> None:
    cena = Cena(opcoes=None)
    cena.solta()
    cena.segura(1.0, PS_R2, r2=255)
    assert cena.gestos == []
    assert "r2_btn" not in cena.mgr.combo_buttons_active(set(PS_R2), de=P1, gatilhos=(0, 255))
    assert cena.mgr.eixos_do_gesto(PS_R2, (0, 255), de=P1) == frozenset()


def test_o_gesto_do_p2_sai_com_o_uniq_do_p2_e_nao_cala_o_p1() -> None:
    cena = Cena()
    cena.solta(de=P1)
    cena.solta(de=P2)
    cena.segura(0.1, PS_R2, r2=255, de=P2)
    assert [(de, g) for de, g, _v in cena.saiu] == [(P2, "sobe")]
    assert cena.mgr.eixos_do_gesto({"r2_btn"}, (0, 255), de=P1) == frozenset()
    assert cena.mgr.eixos_do_gesto(PS_R2, (0, 255), de=P2) == {"r2"}


def test_o_acelerador_publica_a_pressao_do_r2_ate_20_por_segundo() -> None:
    cena = Cena(Opcoes(acelerador=True))
    cena.solta()
    for passo in range(120):
        cena.tique(PS_R2, r2=min(255, 20 + passo * 2))
    ao_vivo = [v for _de, g, v in cena.saiu if g == "nivel_ao_vivo"]
    assert "sobe" not in cena.gestos
    assert 20 <= len(ao_vivo) <= 41, f"no máximo 20 por segundo: {len(ao_vivo)}"
    assert ao_vivo == sorted(ao_vivo) and ao_vivo[-1] > 0.9
    cena.solta()
    assert cena.saiu[-1][1:] == ("nivel_ao_vivo", 0.0), "soltar zera o nível"


def _toque_do_ps(cena: Cena, segundos: float = 0.05) -> None:
    cena.segura(segundos, ("ps",))
    cena.solta(0.05)


def test_camada_desligada_o_ps_sozinho_abre_a_steam_sem_atraso() -> None:
    cena = Cena(Opcoes(camada=False))
    cena.solta()
    cena.segura(0.1, ("ps",))
    assert cena.steam == 0
    cena.tique(())
    assert cena.steam == 1


def test_camada_ligada_o_ps_sozinho_espera_400_ms_antes_de_abrir_a_steam() -> None:
    cena = Cena(Opcoes(camada=True))
    cena.solta()
    cena.segura(0.1, ("ps",))
    cena.solta(0.3)
    assert cena.steam == 0, "ainda esperando um segundo toque"
    cena.solta(0.2)
    assert cena.steam == 1
    assert cena.gestos == []


def test_o_ps_duplo_liga_a_camada_e_nao_abre_a_steam() -> None:
    cena = Cena(Opcoes(camada=True))
    cena.solta()
    _toque_do_ps(cena)
    _toque_do_ps(cena)
    cena.solta(1.0)
    assert cena.steam == 0
    assert cena.saiu[-1][1:] == ("camada", 1)
    assert cena.mgr._gestos is not None and cena.mgr._gestos.camada_ligada(P1)


def test_na_camada_o_r2_sozinho_sobe_e_nao_chega_ao_jogo() -> None:
    cena = Cena(Opcoes(camada=True))
    cena.solta()
    _toque_do_ps(cena)
    _toque_do_ps(cena)
    cena.solta(0.2)
    cena.segura(0.1, ("r2_btn",), r2=255)
    assert cena.gestos[-1] == "sobe"
    assert "r2_btn" in cena.mgr.combo_buttons_active({"r2_btn"}, de=P1, gatilhos=(0, 255))
    assert cena.mgr.eixos_do_gesto({"r2_btn"}, (0, 255), de=P1) == {"r2"}
    cena.segura(0.1, ("r1",))
    assert cena.gestos[-1] == "perfil_seguinte"


def test_a_camada_desliga_com_outro_ps_duplo() -> None:
    cena = Cena(Opcoes(camada=True))
    cena.solta()
    for _ in range(2):
        _toque_do_ps(cena)
    cena.solta(0.5)
    for _ in range(2):
        _toque_do_ps(cena)
    cena.solta(1.0)
    assert [(g, v) for _de, g, v in cena.saiu] == [("camada", 1), ("camada", 0)]
    assert cena.steam == 0
    cena.segura(0.1, ("r2_btn",), r2=255)
    assert cena.gestos == ["camada", "camada"], "desligada, o R2 volta ao jogo"


def test_a_camada_desliga_sozinha_em_6_s_sem_gesto_e_o_ate_eu_desligar_fica() -> None:
    curta = Cena(Opcoes(camada=True, camada_s=6))
    longa = Cena(Opcoes(camada=True, camada_s=0))
    for cena in (curta, longa):
        cena.solta()
        _toque_do_ps(cena)
        _toque_do_ps(cena)
        cena.solta(7.0)
        cena.segura(0.1, ("r2_btn",), r2=255)
    assert curta.gestos == ["camada"], "passados 6 s sem gesto, o R2 sozinho é do jogo"
    assert longa.gestos == ["camada", "sobe"], "«até eu desligar» não vence por tempo"


def test_a_camada_do_p1_nao_muda_os_botoes_do_p2() -> None:
    cena = Cena(Opcoes(camada=True))
    cena.solta(de=P1)
    cena.solta(de=P2)
    for _ in range(2):
        cena.segura(0.05, ("ps",), de=P1)
        cena.solta(0.05, de=P1)
    cena.segura(0.1, ("r1", "r2_btn"), r2=255, de=P2)
    assert cena.mgr.combo_buttons_active({"r1"}, de=P2, gatilhos=(0, 0)) == frozenset()
    assert "r1" in cena.mgr.combo_buttons_active({"r1"}, de=P1, gatilhos=(0, 0))
    assert [g for de, g, _v in cena.saiu if de == P2] == []


def test_lado_unico_r2_sobe_r1_desce_e_segurado_para() -> None:
    cena = Cena(Opcoes(lado_unico=True))
    cena.solta()
    cena.segura(0.1, PS_R2, r2=255)
    cena.solta()
    cena.segura(0.2, ("ps", "r1"))
    cena.solta()
    assert cena.gestos == ["sobe", "desce"]
    cena.segura(0.9, ("ps", "r1"))
    cena.solta()
    assert cena.gestos == ["sobe", "desce", "para"], "R1 segurado 0,6 s para e não desce"


def test_lado_unico_troca_o_perfil_no_direcional() -> None:
    cena = Cena(Opcoes(lado_unico=True))
    cena.solta()
    cena.segura(0.1, ("ps", "dpad_right"))
    cena.solta()
    cena.segura(0.1, ("ps", "dpad_left"))
    assert cena.gestos == ["perfil_seguinte", "perfil_anterior"]
    assert "dpad_left" in cena.mgr.combo_buttons_active(
        {"ps", "dpad_left"}, de=P1, gatilhos=(0, 0))


def test_o_ps_que_fez_gesto_nao_abre_a_steam_ao_soltar() -> None:
    cena = Cena()
    cena.solta()
    cena.segura(0.1, PS_R2, r2=255)
    cena.solta(0.5)
    assert cena.steam == 0
    cena.segura(0.1, ("ps",))
    cena.solta(0.1)
    assert cena.steam == 1


class _No:
    """O nó do uinput de mentira: os eixos e as teclas que o jogo leria."""

    def __init__(self) -> None:
        self.teclas: dict[int, int] = {}
        self.eixos: dict[int, list[int]] = {}

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_KEY:
            self.teclas[codigo] = valor
        elif tipo == ecodes.EV_ABS:
            self.eixos.setdefault(codigo, []).append(valor)

    def syn(self) -> None:
        pass


def _pad() -> tuple[UinputGamepad, _No]:
    no = _No()
    pad = UinputGamepad(flavor="dualsense")
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


class _Leitor:
    grab_state = "held"

    def __init__(self) -> None:
        self.botoes: frozenset[str] = frozenset()
        self.l2 = 0
        self.r2 = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=self.l2, r2_raw=self.r2,
            buttons_pressed=self.botoes,
        )


class _Mesa:
    """O P1 pelo ``dispatch_gamepad`` e o P2 pelo ``forward_all``, um gerente de atalhos só."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, opcoes: Opcoes | None = PADRAO) -> None:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        self.cena = Cena(opcoes)
        self.pad_p1, self.no_p1 = _pad()
        self.pad_p2, self.no_p2 = _pad()
        self.daemon = SimpleNamespace(
            store=SimpleNamespace(),
            controller=SimpleNamespace(primary_uniq=P1),
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            identity_registry=None,
            _gamepad_device=self.pad_p1,
            _coop_manager=None,
            _hotkey_manager=self.cena.mgr,
        )
        self.coop = CoopManager(self.daemon)
        self.leitor_p2 = _Leitor()
        self.coop._players[P2] = _SecondaryPlayer(
            identity=P2, evdev_path="/dev/input/event9", reader=cast(Any, self.leitor_p2),
            player_index=2, vpad=self.pad_p2,
        )

    def p1(self, *botoes: str, r2: int = 0, l2: int = 0) -> None:
        self.cena.relogio.t += 1 / 60
        estado = SimpleNamespace(
            raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=l2, r2_raw=r2)
        gp.dispatch_gamepad(self.daemon, estado, frozenset(botoes))

    def p2(self, *botoes: str, r2: int = 0, l2: int = 0) -> None:
        self.cena.relogio.t += 1 / 60
        self.leitor_p2.botoes, self.leitor_p2.l2, self.leitor_p2.r2 = frozenset(botoes), l2, r2
        self.coop.forward_all()

    @staticmethod
    def r2_do_jogo(no: _No) -> int:
        return max(no.eixos.get(ecodes.ABS_RZ, [0]))


def _tecla(pad: UinputGamepad, no: _No, botao: str) -> bool:
    codigo = pad._resolve_evdev(botao, ecodes)
    assert codigo is not None, botao
    return no.teclas.get(codigo, 0) == 1


def test_durante_ps_r2_o_eixo_e_o_botao_nao_chegam_ao_pad_do_p1_nem_do_p2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.p1()
    mesa.p2()
    for _ in range(10):
        mesa.p1("ps", "r2_btn", r2=255)
        mesa.p2("ps", "r2_btn", r2=255)
    assert mesa.r2_do_jogo(mesa.no_p1) == 0, "o R2 do gesto atirou no P1"
    assert mesa.r2_do_jogo(mesa.no_p2) == 0, "o R2 do gesto atirou no P2"
    assert "r2_btn" not in mesa.pad_p1._last_buttons, "o botão digital do gesto chegou ao P1"
    assert "r2_btn" not in mesa.pad_p2._last_buttons, "o botão digital do gesto chegou ao P2"
    assert _tecla(mesa.pad_p1, mesa.no_p1, "ps"), "o PS sozinho segue como hoje"
    assert mesa.cena.gestos.count("sobe") >= 2, "um sobe por jogador"


def test_o_r2_depois_do_gesto_volta_ao_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.p1()
    for _ in range(5):
        mesa.p1("ps", "r2_btn", r2=255)
    mesa.p1()
    for _ in range(5):
        mesa.p1("r2_btn", r2=255)
    assert mesa.r2_do_jogo(mesa.no_p1) == 255
    assert "r2_btn" in mesa.pad_p1._last_buttons


def test_modificacao_desligada_o_r2_chega_ao_pad_como_hoje(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, opcoes=None)
    mesa.p1()
    mesa.p2()
    for _ in range(5):
        mesa.p1("ps", "r2_btn", r2=255)
        mesa.p2("ps", "r2_btn", r2=255)
    assert mesa.r2_do_jogo(mesa.no_p1) == 255
    assert mesa.r2_do_jogo(mesa.no_p2) == 255
    assert mesa.cena.gestos == []


def test_o_gesto_do_p2_nao_cala_o_r2_do_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.p1()
    mesa.p2()
    for _ in range(5):
        mesa.p2("ps", "r2_btn", r2=255)
        mesa.p1("r2_btn", r2=255)
    assert mesa.r2_do_jogo(mesa.no_p1) == 255
    assert mesa.r2_do_jogo(mesa.no_p2) == 0


def test_os_atalhos_leem_a_pressao_do_posto_e_dos_outros() -> None:
    cena = Cena()
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=P1), _hotkey_manager=cena.mgr)
    for _ in range(3):
        cena.relogio.t += 1 / 60
        observar_os_atalhos(daemon, frozenset(), now=cena.relogio.t, gatilhos_do_posto=(0, 0))
    for _ in range(3):
        cena.relogio.t += 1 / 60
        observar_os_atalhos(
            daemon, frozenset(PS_R2), now=cena.relogio.t, gatilhos_do_posto=(0, 255))
    assert cena.gestos == ["sobe"]


def _daemon_com_bus(*, nativo: bool = False) -> Any:
    return SimpleNamespace(bus=EventBus(), _native_mode=nativo, identity_registry=None)


def _estado(**mais: Any) -> dict[str, Any]:
    estado: dict[str, Any] = {
        "mod": "brinquedos", "ligado": False, "nivel": 0, "perfil": None,
        "aparelhos": ["Brinquedo"], "ajustes": {},
    }
    estado.update(mais)
    return estado


def test_os_gestos_valem_so_com_a_modificacao_e_um_aparelho() -> None:
    daemon = _daemon_com_bus()
    valem = gestos_dos_acessorios_valem(daemon)
    assert valem(P1) is None, "sem a modificação, PS + R2 é o que é hoje"
    daemon.bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(aparelhos=[]))
    assert valem(P1) is None, "sem aparelho conectado, também"
    daemon.bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado())
    assert valem(P1) == Opcoes()
    daemon.bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ajustes={"camada": True}))
    assert valem(P1) == Opcoes(camada=True)


def test_no_modo_nativo_os_gestos_nascem_desligados() -> None:
    daemon = _daemon_com_bus(nativo=True)
    daemon.bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado())
    valem = gestos_dos_acessorios_valem(daemon)
    assert valem(P1) is None
    daemon.bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ajustes={"gestos_no_nativo": True}))
    assert valem(P1) is not None


def test_o_gesto_vira_o_evento_com_uniq_jogador_gesto_e_valor_e_nunca_um_botao() -> None:
    daemon = _daemon_com_bus()
    fila = daemon.bus.subscribe(EventTopic.ACESSORIOS_GESTO)
    dizer_o_gesto_dos_acessorios(daemon)(P2, "sobe", 1)
    carga = fila.get_nowait()
    assert set(carga) == {"uniq", "jogador", "gesto", "valor"}
    assert (carga["uniq"], carga["gesto"], carga["valor"]) == (P2, "sobe", 1)


@pytest.fixture
def curto() -> Iterator[Path]:
    base = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None
    pasta = Path(tempfile.mkdtemp(prefix="hg", dir=base))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


async def _porta(curto: Path, bus: EventBus, permissoes: list[str]) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(
        curto / "mods.sock", bus, escritor=escritor,
        o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1)
    await porta.iniciar()
    porta.registrar("ficha", "brinquedos", os.getpid(), permissoes)
    return porta


def test_a_porta_recebe_o_estado_dos_acessorios_e_apaga_quando_a_conexao_cai(
    curto: Path,
) -> None:
    async def corrida() -> None:
        bus = EventBus()
        porta = await _porta(curto, bus, ["ler:acessorios.gesto"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            ok = await asyncio.to_thread(cliente.pedir, "acessorios.estado", {
                "ligado": True, "nivel": 4, "perfil": "suave", "aparelhos": ["Um"],
                "ajustes": {"camada": True, "segredo": 1}})
            assert ok["result"] == {"recebido": True}
            estado = bus.ultimo(EventTopic.ACESSORIOS_ESTADO)
            assert estado is not None
            assert estado["mod"] == "brinquedos" and estado["nivel"] == 4
            assert estado["ajustes"] == {"camada": True}, "só as opções que o Hefesto lê"
            ruim = await asyncio.to_thread(
                cliente.pedir, "acessorios.estado", {"ligado": True, "nivel": 99})
            assert ruim["error"]["code"] == CODE_INVALID_PARAMS
        finally:
            cliente.fechar()
        for _ in range(100):
            if (bus.ultimo(EventTopic.ACESSORIOS_ESTADO) or {}).get("aparelhos") == []:
                break
            await asyncio.sleep(0.02)
        assert (bus.ultimo(EventTopic.ACESSORIOS_ESTADO) or {}).get("aparelhos") == [], (
            "a conexão caiu: os gestos voltam a ser os de sempre")
        await porta.parar()

    asyncio.run(corrida())


def test_o_estado_sem_a_permissao_e_recusado_nomeando_a_permissao(curto: Path) -> None:
    async def corrida() -> None:
        bus = EventBus()
        porta = await _porta(curto, bus, ["ler:estado"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            recusa = await asyncio.to_thread(
                cliente.pedir, "acessorios.estado", {"ligado": True, "aparelhos": ["Um"]})
            assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
            assert "ler:acessorios.gesto" in recusa["error"]["message"]
            assert bus.ultimo(EventTopic.ACESSORIOS_ESTADO) is None
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())


_FILHO = textwrap.dedent("""
    import os, signal, sys, time
    marca = sys.argv[1]
    def termina(_n, _f):
        open(marca, "w").write(repr(time.time()))
        os._exit(0)
    signal.signal(signal.SIGTERM, termina)
    open(marca + ".vivo", "w").write("1")
    while True:
        time.sleep(0.01)
""")


def _supervisor(bus: EventBus, curto: Path) -> Supervisor:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return None

    return Supervisor(
        bus, escritor=escritor, o_jogo_escreve=lambda u, c: False, uniq_do_posto=lambda: P1,
        porta=curto / "p.sock", procurar_bwrap=False)


async def _filho(curto: Path) -> tuple[asyncio.subprocess.Process, Path]:
    marca = curto / "sigterm"
    processo = await asyncio.create_subprocess_exec(
        sys.executable, "-c", _FILHO, str(marca), start_new_session=True)
    for _ in range(200):
        if (curto / "sigterm.vivo").exists():
            break
        await asyncio.sleep(0.02)
    return processo, marca


def test_o_para_sem_ligado_false_em_300_ms_encerra_a_modificacao_pelo_pid(curto: Path) -> None:
    async def corrida() -> tuple[bool, float, float]:
        bus = EventBus()
        sup = _supervisor(bus, curto)
        processo, marca = await _filho(curto)
        sup._vigiadas["brinquedos"] = _Vigiada("brinquedos", processo=processo)
        bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ligado=True))
        fila = bus.subscribe(EventTopic.ACESSORIOS_GESTO)
        ouvinte = asyncio.create_task(sup._ouvir_o_parar(fila))
        pedido_em = time.time()
        bus.publish(EventTopic.ACESSORIOS_GESTO, {"uniq": P1, "gesto": "para", "valor": 1})
        for _ in range(100):
            if marca.exists():
                break
            await asyncio.sleep(0.01)
        ouvinte.cancel()
        try:
            recebido_em = float(marca.read_text())
        finally:
            if processo.returncode is None:
                processo.kill()
        return marca.exists(), recebido_em - pedido_em, pedido_em

    existe, atraso, _ = asyncio.run(corrida())
    assert existe, "o SIGTERM não chegou"
    assert 0.25 <= atraso <= 0.45, f"o SIGTERM veio {atraso:.3f} s depois do para"


def test_o_para_com_ligado_false_a_tempo_deixa_a_modificacao_viva(curto: Path) -> None:
    async def corrida() -> tuple[bool, bool]:
        bus = EventBus()
        sup = _supervisor(bus, curto)
        processo, _marca = await _filho(curto)
        sup._vigiadas["brinquedos"] = _Vigiada("brinquedos", processo=processo)
        bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ligado=True))
        conferencia = asyncio.create_task(sup.conferir_o_parar())
        await asyncio.sleep(0.1)
        bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ligado=False))
        encerrou = await conferencia
        viva = processo.returncode is None
        processo.kill()
        await processo.wait()
        return encerrou, viva

    encerrou, viva = asyncio.run(corrida())
    assert not encerrou and viva


def test_o_para_de_quem_ja_estava_desligada_nao_mata_ninguem(curto: Path) -> None:
    async def corrida() -> bool:
        bus = EventBus()
        sup = _supervisor(bus, curto)
        bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(ligado=False))
        return await sup.conferir_o_parar()

    assert asyncio.run(corrida()) is False


def test_o_sinal_do_filho_e_o_sigterm(curto: Path) -> None:
    """A prova acima só vale se o filho de mentira grava no SIGTERM: ele grava."""
    async def corrida() -> bool:
        processo, marca = await _filho(curto)
        os.killpg(processo.pid, signal.SIGTERM)
        await processo.wait()
        return marca.exists()

    assert asyncio.run(corrida())
