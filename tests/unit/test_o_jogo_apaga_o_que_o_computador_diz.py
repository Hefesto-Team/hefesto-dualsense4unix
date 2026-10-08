"""O jogo apaga uma tecla que o computador define, e o que vale é o que ele disse.

(O-JOGO-PODE-APAGAR-E-IGUALAR-A-FABRICA-O-QUE-O-COMPUTADOR-DIZ-01, a parte «apagar».)

O perfil do jogo só diz o que difere do computador, e a chave ausente quer
dizer «herde». Apagar, dentro de um jogo, uma tecla que o computador define
gravava o dicionário SEM ela, e a junção ``{**computador, **jogo}`` a devolvia.
A cura é a lápide: a lista vazia, o «— Nada —» que o schema aceita e a
resolução já lê, escrita só onde o computador define a tecla.

OS GESTOS SÃO OS DE VERDADE (``guardar_teclas`` e ``padrao_da_tecla``), sobre o
``gravar_pelo_gesto`` de verdade e um disco de teste; só a volta ao serviço
(``reaplicar``) é dublê. As teclas e as ações saem do motor
(``acoes_de_botao``), nunca digitadas aqui.

AS MORDIDAS, uma por caso (cada docstring diz o que arrancar):
  - sem ``_com_a_lapide_do_que_se_apagou`` em ``gravar_pelo_gesto``, o primeiro
    caso reprova (a tecla volta);
  - com a lápide estendida a ``button_actions``, o degrau reprova (o «voltar ao
    padrão» do jogo vira «nada»);
  - com a tecla apagada procurada só na vista (e não no computador), o jogo de
    teclas vazias (``{}``) reprova: a tecla do computador volta.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

JOGO = "Jogo X"
TECLA_A = ["KEY_F5"]
TECLA_B = ["KEY_F6"]


class _PonteMuda:
    """Aceita tudo: a volta ao serviço não é o que esta régua mede."""

    def __getattr__(self, _nome: str) -> Any:
        return lambda *a, **k: True


@pytest.fixture
def gestos(monkeypatch: pytest.MonkeyPatch) -> Any:
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil

    monkeypatch.setattr(perfil, "reaplicar", lambda *a, **k: None, raising=False)
    mod._MEXENDO.clear()
    estado = {"active_profile": JOGO, "controllers": [], "keyboard_emulation": {},
              "mouse_emulation": {}}
    ctx = pacotes.Contexto(state=estado, mesa=[], conectados=[], estados={})
    yield ctx, mod
    mod._MEXENDO.clear()


def _botoes() -> tuple[str, str]:
    dominio = sorted(acoes.DOMINIO_DO_TECLADO)
    return dominio[0], dominio[1]


def _perfil(**campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": JOGO, "match": {"type": "criteria", "window_class": ["jogo x"]}, **campos})


def _computador(documento: dict[str, Any]) -> None:
    assert m.gravar_o_computador(documento)


def _vale() -> Profile:
    return opc.perfil_que_vale(load_profile(JOGO), opc.o_computador())


def _forma_das_teclas(mod: Any, **trocas: str) -> dict[str, str]:
    forma = dict(mod.teclas_dos_botoes(_vale().model_dump()))
    for botao, texto in trocas.items():
        forma[f"{mod.PREFIXO_DA_TECLA}{botao}"] = texto
    return forma


def test_o_jogo_apaga_a_tecla_do_computador_e_ela_nao_volta(gestos: Any) -> None:
    """A tecla que o computador define, apagada no jogo, vale «nada» e a vizinha segue.

    A MORDIDA: tire a chamada de ``_com_a_lapide_do_que_se_apagou`` do
    ``gravar_pelo_gesto`` e a tecla apagada volta a ser a do computador.
    """
    ctx, mod = gestos
    a, b = _botoes()
    _computador({"global": {"key_bindings": {a: TECLA_A, b: TECLA_B}}})
    save_profile(_perfil())

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(mod, **{b: ""})}, _PonteMuda())

    guardado = load_profile(JOGO).key_bindings or {}
    assert guardado.get(b) == [], f"o jogo não gravou a lápide de {b}: {guardado!r}"
    assert guardado.get(a) == TECLA_A
    vale = _vale().key_bindings or {}
    assert vale.get(b) == [], f"a tecla apagada voltou a valer: {vale.get(b)!r}"
    assert vale.get(a) == TECLA_A
    _modo, do_teclado, _s = acoes.resolver(None, vale)
    assert not do_teclado.get(b), f"o botão ainda digita {do_teclado.get(b)!r}"
    assert do_teclado.get(a) == tuple(TECLA_A)


def test_tecla_que_o_computador_nao_define_some_sem_lapide(gestos: Any) -> None:
    """Sem a tecla no computador, apagar é ausência: o jogo não grava lista vazia."""
    ctx, mod = gestos
    a, b = _botoes()
    _computador({"global": {"key_bindings": {a: TECLA_A}}})
    save_profile(_perfil(key_bindings={a: TECLA_A, b: TECLA_B}))

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(mod, **{b: ""})}, _PonteMuda())

    guardado = load_profile(JOGO).key_bindings or {}
    assert b not in guardado, f"gravou {b} sem o computador definir: {guardado!r}"
    assert b not in (_vale().key_bindings or {})


def test_apagar_tudo_continua_sendo_o_tudo_ou_nada(gestos: Any) -> None:
    """Esvaziar todos os campos grava ``{}``, e ``{}`` já ignora o computador inteiro."""
    ctx, mod = gestos
    a, b = _botoes()
    _computador({"global": {"key_bindings": {a: TECLA_A, b: TECLA_B}}})
    save_profile(_perfil())

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(
        mod, **{botao: "" for botao in acoes.DOMINIO_DO_TECLADO})}, _PonteMuda())

    assert load_profile(JOGO).key_bindings == {}
    assert _vale().key_bindings == {}


def test_o_jogo_de_teclas_vazias_apaga_uma_e_a_do_computador_nao_volta(
    gestos: Any,
) -> None:
    """O jogo com ``key_bindings == {}`` (a vista não junta o computador) apaga uma tecla.

    O campo que ela deixou vazio tem de valer «nada», também quando a vista de
    partida não trazia a tecla do computador. A MORDIDA: procure a tecla
    apagada só na VISTA (que é ``{}`` aqui) em vez de no computador, e a tecla
    do computador volta.
    """
    ctx, mod = gestos
    a, b = _botoes()
    _computador({"global": {"key_bindings": {a: TECLA_A, b: TECLA_B}}})
    save_profile(_perfil(key_bindings={}))
    assert _vale().key_bindings == {}

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(mod, **{b: ""})}, _PonteMuda())

    vale = _vale().key_bindings or {}
    assert not vale.get(b), f"a tecla do computador voltou: {vale!r}"
    _modo, do_teclado, _s = acoes.resolver(None, vale)
    assert not do_teclado.get(b), f"o botão voltou a digitar {do_teclado.get(b)!r}"


def test_sem_jogo_o_computador_perde_a_tecla_sem_lapide(gestos: Any) -> None:
    """No computador (sem perfil ativo) apagar é tirar a chave, não gravar ``[]``."""
    ctx, mod = gestos
    ctx.state["active_profile"] = ""
    a, b = _botoes()
    _computador({"global": {"key_bindings": {a: TECLA_A, b: TECLA_B}}})
    vista = opc.perfil_que_vale(opc.perfil_vazio(), opc.o_computador())
    forma = dict(mod.teclas_dos_botoes(vista.model_dump()))
    assert forma[f"{mod.PREFIXO_DA_TECLA}{b}"], "a tela tem de mostrar a tecla antes"
    forma[f"{mod.PREFIXO_DA_TECLA}{b}"] = ""

    mod.guardar_teclas(ctx, {"forma": forma}, _PonteMuda())

    teclas = opc.o_computador().global_.key_bindings or {}
    assert b not in teclas, f"o computador guardou a tecla apagada: {teclas!r}"
    assert teclas.get(a) == TECLA_A
    assert [] not in teclas.values(), f"o computador ganhou lápide: {teclas!r}"


def test_o_degrau_do_voltar_ao_padrao_nao_virou_nada(gestos: Any) -> None:
    """Num jogo, o ↺ da linha tira a escolha do JOGO e vale o computador (D-0110).

    O ↺ tira a chave de ``button_actions`` da vista, e a forma é a mesma de
    «apagar». Por isso a lápide é só de ``key_bindings``, onde ausência já é
    «nada» e o gesto de fábrica ESCREVE o valor.

    A MORDIDA: estenda a lápide a ``button_actions`` (``__NADA__`` no lugar da
    chave tirada) e esta régua reprova: o ↺ passaria a calar o botão.
    """
    ctx, mod = gestos
    botao, vizinho = _botoes()
    fabrica = acoes.padrao()
    tokens = sorted({t for t in fabrica.values() if t != acoes.TOKEN_NADA})
    do_jogo, do_pc, outro = tokens[0], tokens[1], tokens[2]
    assert len({do_jogo, do_pc, outro}) == 3
    _computador({"global": {"button_actions": {botao: do_pc, vizinho: outro}}})
    save_profile(_perfil(button_actions={botao: do_jogo}))
    assert (_vale().button_actions or {}).get(botao) == do_jogo

    mod.padrao_da_tecla(ctx, {"tecla": botao}, _PonteMuda())

    guardado = load_profile(JOGO).button_actions or {}
    assert acoes.TOKEN_NADA not in guardado.values(), f"o ↺ gravou «nada»: {guardado!r}"
    vale = _vale().button_actions or {}
    assert vale.get(botao) == do_pc, f"o ↺ não devolveu ao computador: {vale.get(botao)!r}"
    assert vale.get(vizinho) == outro


def test_o_nada_escolhido_na_tabela_ja_vale_no_jogo() -> None:
    """Em ``button_actions`` o «nada» é o valor ``__NADA__``, e a junção o guarda.

    A MORDIDA: inverta a precedência da junção em ``perfil_que_vale`` (o
    computador por cima do jogo) e o computador devolve a ação dele.
    """
    botao, vizinho = _botoes()
    tokens = sorted({t for t in acoes.padrao().values() if t != acoes.TOKEN_NADA})
    _computador({"global": {"button_actions": {botao: tokens[0], vizinho: tokens[1]}}})
    save_profile(_perfil(button_actions={botao: acoes.TOKEN_NADA}))

    vale = _vale().button_actions or {}
    assert vale.get(botao) == acoes.TOKEN_NADA
    assert vale.get(vizinho) == tokens[1]
