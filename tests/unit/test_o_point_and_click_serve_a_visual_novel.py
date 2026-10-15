#!/usr/bin/env python3
"""O-POINT-AND-CLICK-SERVE-A-VISUAL-NOVEL-01 — o estilo traz a tabela de botões do jogo de clicar.

Medido antes de curar (15/10/2026): aplicar o estilo Point-and-click gravava só o modo
(`Receita(modo="desktop")`), e o perfil ficava sem tabela. No de fábrica os ombros são Alt+Shift+Tab
e Alt+Tab e o Options é Super, e num jogo em tela cheia um toque no ombro tira o jogo da frente. A
lista de ações não tinha PageUp, PageDown, Ctrl, Tab nem H, e o analógico só escolhia o cursor ou a
rolagem. O estilo Visual novel não existia.

Os leitores são o perfil gravado (a tabela EFETIVA, com as três camadas) e as teclas que o uinput de
mentira recebe, nunca a constante que a cura usa.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from tests.unit.test_o_gatilho_vira_clique_sem_ligar_o_cursor import (  # noqa: F401
    _daemon_de_mentira,
    _estado,
    _OskDeMentira,
    _saidas,
    _UinputPorDevice,
    dois_devices,
)

QUATRO = [
    {"pref": f"p{n}", "uniq": f"aabbcc00000{n}", "jogador": n, "cor": cor,
     "nome": cor, "via": via.upper(), "transporte": via, "alvo": n == 1}
    for n, cor, via in ((1, "cosmic-red", "usb"), (2, "white", "bt"),
                        (3, "galactic-purple", "usb"), (4, "midnight-black", "bt"))
]


class _Ponte:
    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Maid Life", match=MatchAny(), priority=40)}

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof

    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [guardado["perfil"]])
    monkeypatch.setattr(loader, "load_profile", lambda nome, *a, **k: guardado["perfil"])
    monkeypatch.setattr(loader, "save_profile", _save)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Maid Life", raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    return guardado


def _aplicar(rotulo: str) -> None:
    ctx = Contexto(state={"active_profile": None}, mesa=list(QUATRO),
                   conectados=list(QUATRO), estados={})
    a10_perfis.editor_estilo(ctx, {"valor": rotulo}, _Ponte())


def _efetiva(prof: Profile) -> dict[str, str]:
    return acoes.tabela_efetiva(prof.button_actions, prof.key_bindings)


def _sem_atalho_de_sistema(tabela: dict[str, str]) -> list[str]:
    return [b for b, t in tabela.items()
            if "KEY_LEFTMETA" in t.split("+") or {"KEY_LEFTALT", "KEY_TAB"} <= set(t.split("+"))]


# -- o estilo e os moldes ---------------------------------------------------------------


def test_o_visual_novel_e_estilo_com_a_receita_do_point_and_click() -> None:
    vn = ej.POR_CHAVE["visual_novel"]
    pc = ej.POR_CHAVE["point_and_click"]
    assert vn.rotulo == "Visual novel"
    assert (vn.gatilho, vn.vibracao, vn.familia) == (pc.gatilho, pc.vibracao, pc.familia)
    assert vn.brilho == 0.5
    receita = vn.receita_invisivel
    assert receita is not None
    assert receita.modo == "desktop" and receita.toque_por_tiro and receita.lado_do_som
    assert receita.duracao_da_vibracao_ms == ej.DURACAO_DE_SEMPRE_MS


def test_o_molde_do_estilo_sai_do_estilo_e_nao_da_marca() -> None:
    assert ej.POR_CHAVE["visual_novel"].receita_invisivel.molde == "visual_novel"
    assert ej.POR_CHAVE["point_and_click"].receita_invisivel.molde == "so_mouse"


def test_o_molde_visual_novel_tem_as_quatro_teclas_do_renpy() -> None:
    """MORDIDA: trocar o R1 por PageDown reprova."""
    molde = ej.MOLDES["visual_novel"]
    assert molde == {"l1": "KEY_PAGEUP", "r1": "KEY_LEFTCTRL", "options": "KEY_ESC",
                     "create": "KEY_H"}


@pytest.mark.parametrize("chave", sorted(ej.MOLDES))
def test_todo_molde_e_um_button_actions_que_o_perfil_aceita(chave: str) -> None:
    prof = Profile(name="Jogo", match=MatchAny(), button_actions=dict(ej.MOLDES[chave]))
    assert prof.button_actions == ej.MOLDES[chave]


def test_a_lista_de_acoes_ganha_as_teclas_do_jogo_de_clicar() -> None:
    for token in ("KEY_PAGEUP", "KEY_PAGEDOWN", "KEY_LEFTCTRL", "KEY_TAB", "KEY_H"):
        assert acoes.ACOES[token][0] == acoes.GRUPO_TECLADO, token
    assert acoes.rotulo(acoes.TOKEN_WASD) == "Teclas WASD"
    assert acoes.rotulo(acoes.TOKEN_SETAS) == "Setas"
    do_ps = {t for _g, rotulos in acoes.por_grupo(acoes.BOTAO_PS) for t in rotulos}
    assert "Teclas WASD" not in do_ps and "Setas" not in do_ps, (
        "as teclas do analógico não cabem na linha do PS")


# -- aplicar o estilo grava a tabela -----------------------------------------------------


@pytest.mark.parametrize("rotulo", ["Point-and-click", "Visual novel"])
def test_aplicar_o_estilo_grava_a_tabela_e_liga_o_tambem_no_jogo(
    disco: dict[str, Any], rotulo: str,
) -> None:
    """MORDIDA: aplicar só o modo, como antes, deixa `button_actions` vazio."""
    _aplicar(rotulo)
    prof = disco["perfil"]
    molde = ej.MOLDES[ej.POR_ROTULO[rotulo].receita_invisivel.molde]
    assert prof.button_actions == molde
    assert prof.tabela_no_jogo is True
    assert prof.mode is not None and prof.mode.kind == "desktop"


@pytest.mark.parametrize("rotulo", ["Point-and-click", "Visual novel"])
def test_nenhuma_linha_leva_alt_tab_nem_super(disco: dict[str, Any], rotulo: str) -> None:
    """Nem com a tabela antiga (`key_bindings`) do perfil de partida."""
    disco["perfil"] = disco["perfil"].model_copy(update={"key_bindings": {
        "l1": ["KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"], "r1": ["KEY_LEFTALT", "KEY_TAB"],
        "options": ["KEY_LEFTMETA"]}})
    assert _sem_atalho_de_sistema(_efetiva(disco["perfil"])) != []
    _aplicar(rotulo)
    assert _sem_atalho_de_sistema(_efetiva(disco["perfil"])) == []


def test_o_visual_novel_chega_ao_teclado_como_tecla_segurada(disco: dict[str, Any]) -> None:
    _aplicar("Visual novel")
    prof = disco["perfil"]
    _mouse, teclado, _sem = acoes.resolver(prof.button_actions, prof.key_bindings)
    assert teclado["l1"] == ("KEY_PAGEUP",)
    assert teclado["r1"] == ("KEY_LEFTCTRL",)
    assert teclado["options"] == ("KEY_ESC",)
    assert teclado["create"] == ("KEY_H",)
    assert _efetiva(prof)["cross"] == "BTN_LEFT", "o clique continua o de fábrica"


def test_o_so_mouse_cala_os_ombros_e_deixa_os_cliques(disco: dict[str, Any]) -> None:
    _aplicar("Point-and-click")
    tabela = _efetiva(disco["perfil"])
    assert tabela["l1"] == tabela["r1"] == tabela["options"] == acoes.TOKEN_NADA
    assert tabela["cross"] == tabela["l2"] == "BTN_LEFT"
    assert tabela["triangle"] == tabela["r2"] == "BTN_RIGHT"
    assert tabela["l3_direcao"] == acoes.TOKEN_CURSOR


def test_o_estilo_novo_tira_so_as_linhas_do_molde_anterior(disco: dict[str, Any]) -> None:
    """O PageUp do visual novel não fica num jogo de tiro; a linha dela fica."""
    _aplicar("Visual novel")
    disco["perfil"] = disco["perfil"].model_copy(update={
        "button_actions": {**disco["perfil"].button_actions, "dpad_up": "KEY_W"}})
    _aplicar("FPS")
    prof = disco["perfil"]
    assert prof.button_actions == {"dpad_up": "KEY_W"}
    assert prof.tabela_no_jogo is None


def test_outro_estilo_sem_tabela_nao_inventa_uma(disco: dict[str, Any]) -> None:
    _aplicar("FPS")
    assert disco["perfil"].button_actions is None
    assert disco["perfil"].tabela_no_jogo is None


def test_visual_novel_depois_de_point_and_click_troca_o_molde(disco: dict[str, Any]) -> None:
    _aplicar("Point-and-click")
    _aplicar("Visual novel")
    assert disco["perfil"].button_actions == ej.MOLDES["visual_novel"]


# -- o analógico como teclas -------------------------------------------------------------


def test_o_resolver_da_dono_as_teclas_do_analogico_so_na_linha_dele() -> None:
    do_mouse, _teclado, sem_dono = acoes.resolver({acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD})
    assert do_mouse[acoes.EIXO_ESQUERDO] == acoes.TOKEN_WASD
    assert acoes.EIXO_ESQUERDO not in sem_dono
    _m, _t, sem_dono = acoes.resolver({"cross": acoes.TOKEN_WASD})
    assert "cross" in sem_dono, "WASD num botão não tem quem atenda"


def test_tres_quartos_para_a_esquerda_e_para_cima_emite_a_e_w(
    dois_devices: _UinputPorDevice,  # noqa: F811
) -> None:
    """Meia deflexão é o limiar; as diagonais saem como duas teclas; o centro solta.

    MORDIDA: o token sem emissor (a `TabelaNoJogo` sem as teclas do analógico) não emite nada.
    """
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo({acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}, None, ligada=True)
    tabela.tick(daemon, _estado(raw_lx=32, raw_ly=32, raw_rx=128, raw_ry=128), frozenset())
    mouse, teclado = _saidas(dois_devices)
    assert ("KEY_A", 1) in teclado and ("KEY_W", 1) in teclado, teclado
    assert not [n for n, _v in teclado if n in ("KEY_S", "KEY_D")], teclado
    assert not [n for n, _v in mouse if n in ("REL_X", "REL_Y")], "o cursor andou com WASD"
    tabela.tick(daemon, _estado(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128), frozenset())
    _mouse, teclado = _saidas(dois_devices)
    assert ("KEY_A", 0) in teclado and ("KEY_W", 0) in teclado, teclado


def test_menos_de_meia_deflexao_nao_aperta(dois_devices: _UinputPorDevice) -> None:  # noqa: F811
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo({acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}, None, ligada=True)
    tabela.tick(daemon, _estado(raw_lx=80, raw_ly=176, raw_rx=128, raw_ry=128), frozenset())
    _mouse, teclado = _saidas(dois_devices)
    assert not [n for n, v in teclado if v == 1 and n.startswith("KEY_")], teclado


def test_as_setas_no_analogico_direito(dois_devices: _UinputPorDevice) -> None:  # noqa: F811
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo({acoes.EIXO_DIREITO: acoes.TOKEN_SETAS}, None, ligada=True)
    tabela.tick(daemon, _estado(raw_lx=128, raw_ly=128, raw_rx=230, raw_ry=230), frozenset())
    mouse, teclado = _saidas(dois_devices)
    assert ("KEY_RIGHT", 1) in teclado and ("KEY_DOWN", 1) in teclado, teclado
    assert "REL_WHEEL" not in [n for n, _v in mouse], "a rolagem andou com as setas"


def test_o_molde_teclado_e_mouse_anda_com_wasd_e_o_r2_digita_e(
    dois_devices: _UinputPorDevice,  # noqa: F811
) -> None:
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo(ej.MOLDES["teclado_e_mouse"], None, ligada=True)
    tabela.tick(daemon, _estado(raw_lx=250, raw_ly=128, r2_raw=255), frozenset())
    mouse, teclado = _saidas(dois_devices)
    assert ("KEY_D", 1) in teclado and ("KEY_E", 1) in teclado, teclado
    assert not [n for n, _v in mouse if n in ("REL_X", "REL_Y", "BTN_RIGHT")], mouse
