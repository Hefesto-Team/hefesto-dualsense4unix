#!/usr/bin/env python3
"""O GESTO NOVO DO PS DISPARA, E O REMOVIDO SAI DE VEZ (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, N8).

O pedido de 16/10: *«os gestos do PS falta adicionar botão pra adicionar gesto novo (…) e remover
também fora que essa seção fica de olho pra ver se algum atalho tá proibido. aí ele não deixa se
já tiver sendo usado (…) e remove onde tem só o ps sozinho»*. <!-- noqa-acento: citação literal -->

O que se mede aqui, com o daemon de mentira e o `machine.declare` de verdade (o handler do IPC
grava o `maquina.json` do lar de mentira da suíte):

1. o «+ Gesto» com o Triângulo faz o PS + Triângulo disparar o que a tabela diz, nos dois
   controles da régua (Starlight Blue no cabo, Galactic Purple no rádio), e o Triângulo do gesto
   não chega ao jogo;
2. sem a declaração, o PS + Triângulo é do jogo: nada dispara e nada se cala;
3. o botão de tirar um gesto de fábrica tira o combo do detector: não dispara e não cala o botão;
4. a tela recusa o botão já usado, o proibido e o PS sozinho, e o validador do `maquina.json`
   também;
5. os proibidos são os seis dos gestos dos acessórios, lidos do dono.

MORDIDAS (feitas à mão, 16/10/2026): tirar a chamada a `_com_a_tabela_da_maquina` de
`HotkeyManager._combos_configurados` reprova 1 e 3; tirar o `botao_livre` de `novo_gesto` reprova
4; trocar `BOTOES_PROIBIDOS` por outra lista reprova 5.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core import acoes_do_gesto as ag
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import (
    gestos_dos_acessorios,
    hotkey_daemon,
    steam_launcher,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from hefesto_dualsense4unix.utils import maquina as mq

#: Os dois controles da régua, pela cor do plástico, na faixa sintética da casa.
STARLIGHT_BLUE_NO_CABO = ("aa:bb:cc:00:00:01", "usb", 1)
GALACTIC_PURPLE_NO_RADIO = ("aa:bb:cc:00:00:04", "bt", 2)
DOIS = [STARLIGHT_BLUE_NO_CABO, GALACTIC_PURPLE_NO_RADIO]


class _Controle:
    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"connected": True, "transport": via, "is_primary": n == 1,
                 "uniq": mac.replace(":", ""), "player_slot": n} for mac, via, n in DOIS]


def _daemon() -> Any:
    chamados: list[tuple[str, tuple[Any, ...]]] = []
    d = SimpleNamespace(
        config=SimpleNamespace(ps_button_action="steam", ps_button_command="",
                               ps_long_press_ms=0),
        _emulation_suppressed=False, store=None, controller=_Controle(),
        _keyboard_device=None, display_authority="daemon",
        _maquina=mq.carregar_maquina(), _hotkey_manager=None, chamados=chamados)
    d.set_emulation_suppressed = lambda *a: chamados.append(("suspender", a))
    return d


@pytest.fixture(autouse=True)
def sem_steam(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """O PS que se solta sem gesto pede a Steam: aqui ela é um anotador, nunca a de verdade."""
    pedidos: list[str] = []
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam",
                        lambda *a, **k: pedidos.append("steam") or True)
    return pedidos


@pytest.fixture
def chamou(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """O ato «Próximo perfil» trocado por um anotador de QUEM o pediu."""
    feitos: list[tuple[str, Any]] = []

    def _ciclo(_d: Any, sentido: int) -> Any:
        async def _feito() -> None:
            feitos.append(("perfil+" if sentido > 0 else "perfil-",
                           hotkey_daemon.quem_faz_o_gesto()))
        return _feito

    monkeypatch.setattr(hotkey, "build_profile_cycle_callback", _ciclo)
    return feitos


def _apertar(mgr: HotkeyManager, botoes: tuple[str, ...], *, de: str | None = None) -> None:
    async def _cena() -> None:
        mgr.observe(list(botoes), now=0.0, de=de)
        mgr.observe(list(botoes), now=0.2, de=de)
        mgr.observe([], now=0.3, de=de)
        atual = asyncio.current_task()
        pendentes = [t for t in asyncio.all_tasks() if t is not atual]
        if pendentes:
            await asyncio.gather(*pendentes)

    asyncio.run(_cena())


class _Ponte:
    """A ponte da janela com o `machine.declare` ligado ao handler de VERDADE."""

    def __init__(self, daemon: Any) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Servidor(IpcHandlersMixin):
            pass

        self.servidor = _Servidor()
        self.servidor.daemon = daemon  # type: ignore[assignment]
        self.declarados: list[dict[str, Any]] = []

    def machine_declare(self, maquina: dict[str, Any]) -> tuple[bool, str | None]:
        self.declarados.append(maquina)
        r = asyncio.run(self.servidor._handle_machine_declare({"maquina": maquina}))
        return bool(r.get("ok")), r.get("reason")


def _gesto(nome: str) -> Any:
    import pacotes
    from pacotes import a06_navegacao

    pacotes._carregar_tudo()
    a06_navegacao._A_MAQUINA = None
    fn = pacotes.gesto_da_pagina("06-navegacao.html", nome)
    assert fn is not None, f"o gesto «{nome}» da 06 ficou sem dono"
    return lambda o, ponte: fn(pacotes.Contexto(state={}), o, ponte)


def _sem_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles import autoswitch

    monkeypatch.setattr(autoswitch, "jogo_do_wrapper_vivo", lambda **_k: None)


def test_o_ps_mais_triangulo_dispara_nos_dois_controles(
        chamou: list[tuple[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    _sem_jogo(monkeypatch)
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    ponte = _Ponte(d)
    _gesto("novo-gesto")({"b": "triangle"}, ponte)
    _gesto("acao-do-gesto")(
        {"linha": "ps_triangle", "rotulo": "Próximo perfil", "valor": "Próximo perfil"}, ponte)
    assert ponte.declarados == [{"gestos": {"ps_triangle": {"faz": ag.NADA}}},
                                {"gestos": {"ps_triangle": {"faz": ag.PERFIL_SEGUINTE}}}]
    mgr = d._hotkey_manager
    for mac, via, _n in DOIS:
        chamou.clear()
        _apertar(mgr, ("ps", "triangle"), de=mac)
        assert chamou == [("perfil+", mac)], (via, chamou)
        calados = mgr.combo_buttons_active(["ps", "triangle"], de=mac)
        assert "triangle" in calados, f"o Triângulo do gesto chegou ao jogo ({via})"


def test_sem_declaracao_o_triangulo_e_do_jogo(chamou: list[tuple[str, Any]]) -> None:
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    mgr = d._hotkey_manager
    for mac, _via, _n in DOIS:
        _apertar(mgr, ("ps", "triangle"), de=mac)
        assert "triangle" not in mgr.combo_buttons_active(["ps", "triangle"], de=mac)
    assert chamou == [] and d.chamados == []


def test_o_de_fabrica_removido_nao_dispara_nem_cala(
        chamou: list[tuple[str, Any]]) -> None:
    # D-1610-OS-GESTOS-DO-PS-SE-ACRESCENTAM
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    ponte = _Ponte(d)
    _gesto("remover-gesto")({"linha": "ps_options"}, ponte)
    assert ponte.declarados == [{"gestos": {"ps_options": {
        "faz": ag.SUSPENDER, "removido": True}}}]
    mgr = d._hotkey_manager
    for mac, via, _n in DOIS:
        _apertar(mgr, ("ps", "options"), de=mac)
        assert "options" not in mgr.combo_buttons_active(["ps", "options"], de=mac), via
    assert d.chamados == [], "o PS + Options removido ainda suspendeu"
    _apertar(mgr, ag.GESTOS["ps_cima"].botoes, de=DOIS[1][0])
    assert chamou == [("perfil+", DOIS[1][0])], "tirar um gesto levou os outros junto"
    # O «+ Gesto» com o Options devolve o gesto de fábrica com o que ele fazia.
    _gesto("novo-gesto")({"b": "options"}, ponte)
    _apertar(mgr, ("ps", "options"), de=DOIS[0][0])
    assert d.chamados == [("suspender", ())]


def test_a_tela_e_o_validador_recusam_o_repetido_o_proibido_e_o_ps_sozinho() -> None:
    # D-1610-OS-GESTOS-DO-PS-SE-ACRESCENTAM
    d = _daemon()
    ponte = _Ponte(d)
    for b in ("options", "dpad_up", "l1", "r2", "dpad_left", "ps", "touchpad"):
        with pytest.raises(ValueError):
            _gesto("novo-gesto")({"b": b}, ponte)
    _gesto("novo-gesto")({"b": "square"}, ponte)
    with pytest.raises(ValueError):
        _gesto("novo-gesto")({"b": "square"}, ponte)
    with pytest.raises(ValueError):
        _gesto("remover-gesto")({"linha": "ps"}, ponte)
    assert ponte.declarados == [{"gestos": {"ps_square": {"faz": ag.NADA}}}]
    for chave in ("ps", "ps_square"):
        with pytest.raises(ValueError):
            mq.MaquinaConfig.model_validate({"gestos": {chave: {"faz": "nada", "removido": True}}})
    with pytest.raises(ValueError):
        mq.MaquinaConfig.model_validate({"gestos": {"ps_l1": {"faz": "nada"}}})


def test_os_proibidos_sao_os_dos_gestos_dos_acessorios() -> None:
    assert set(ag.BOTOES_PROIBIDOS) == set(gestos_dos_acessorios.BOTAO_DO_MEMBRO)
    assert not set(ag.BOTOES_PROIBIDOS) & set(ag.BOTOES_DO_GESTO_NOVO)
    for b in ag.BOTOES_PROIBIDOS:
        assert not ag.botao_livre(None, b), b
