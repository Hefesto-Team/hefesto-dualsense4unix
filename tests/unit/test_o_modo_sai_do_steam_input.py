#!/usr/bin/env python3
"""O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01 — ela clica no Modo e a tela muda.

A QUEIXA DELA, 22/09/2026:
*"pq eu nao posso trocar os modos de conexão pela interface?"*  # noqa-acento: citação dela
*"eu saio clicando mas não muda de fato."* A foto: dois DualSense no
rádio, ninguém jogando, «Steam Input» aceso; ela clica «Sony DualSense» e
«Xbox», e o «Steam Input» continua aceso.

AS TRÊS CAUSAS, e cada seção abaixo mede uma:

1. o «Steam Input» acendia por jogo FECHADO — o terceiro degrau da escada do
   jogo responde pelo último lançado, e o Modo diz o caminho EM USO;
2. o «Sony DualSense» mandava só o caminho que já era o caminho — o jogo
   continuava na lista e o tique seguinte pintava o Steam Input de novo;
3. o «Xbox» que estourou o prazo do daemon piscava VERDE, e a pendência dele
   não tem relógio: fica anotada até o caminho vivo alcançá-la.

O LAR É O DA RÉGUA DA STEAM-INPUT-01, reusado — uma Steam de mentira com
`localconfig.vdf` sintético e appid que não é jogo de ninguém. Os dois fixtures
de guarda (`_steam_fechada`, que também proíbe fechar a Steam, e `_vigia_limpa`)
vêm de lá com o `lar`, e são automáticos aqui também.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from hefesto_dualsense4unix.interface.pacotes.a07_lancadores import METODO_DA_RECARGA
from tests.unit.test_steam_input_01_o_chip_que_acende_por_jogo import (  # noqa: F401
    APPID,
    _steam_fechada,
    _valor,
    _vigia_limpa,
    lar,
)


@pytest.fixture
def vdf(lar):  # noqa: F811
    """O `localconfig.vdf` do lar de mentira — o `lar` de lá, com nome daqui."""
    return lar


#: Um controle na mesa — sem ele o Modo inteiro apaga (`_a_fileira_com_a_mesa`).
UM_CONTROLE = {"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01",
               "transporte": "bt", "via": "BT", "cor": "", "nome": ""}


class PonteDeMentira:
    """O `p` do gesto. `mudo` = os métodos cujo IPC estoura o prazo.

    NÃO É MAIS FROUXA QUE A DE VERDADE: `ponte.chamar` devolve `bool` — `False`
    no prazo estourado, que é o `[daemon mudo] timed out` do diário dela.
    """

    def __init__(self, *mudo: str) -> None:
        self.mudo = set(mudo)
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append(metodo)
        return metodo not in self.mudo


@pytest.fixture(autouse=True)
def _sem_pendencia_e_sem_perfil(monkeypatch):
    """A pendência é de MÓDULO, e o perfil ativo não entra na régua.

    O escritor do perfil é trocado por um que ANOTA: é assim que a seção 3 mede
    que um pedido não confirmado não vai para o disco dela.
    """
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    gravados: list[str] = []
    monkeypatch.setattr(aba, "_gravar_o_modo_do_chip",
                        lambda ctx, chave: gravados.append(chave) or "")
    yield gravados
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def _ctx(*, aberto: bool, caminho: str = "dualsense", modo: str = "gamepad",
         mesa: bool = True) -> Contexto:
    """O estado do daemon com o jogo ABERTO (em foco) ou FECHADO (só o marker)."""
    state: dict[str, Any] = {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": modo == "gamepad", "flavor": "dualsense",
                              "caminho": caminho},
    }
    if aberto:
        state["window_detect_last_class"] = f"steam_app_{APPID}"
    return Contexto(state=state, mesa=[dict(UM_CONTROLE)] if mesa else [],
                    conectados=[], estados={})


@pytest.fixture
def jogo_fechado(monkeypatch):
    """O TERCEIRO DEGRAU da escada: o marker `last_run` do último jogo lançado.

    A escada (`a07_lancadores.a_escada_do_jogo`) é a de verdade; o que se
    dubla são os dois leitores de marker, como a régua da aba 07 faz.
    """
    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (int(APPID), 1))


def _ponte_de_pe() -> None:
    """O jogo na lista dela E o vdf dizendo Steam Input — o chip pode acender."""
    slo.add_appid_to_steam_input_allowlist(APPID)
    ponte.garantir_ponte(allowlist=[APPID])
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()


def _tela(ctx: Contexto) -> dict[str, str]:
    """O que o tique pinta na fileira, com a vigia relida do disco."""
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    fora = aba.pacote(ctx)
    return {"modo": fora["modo-aceso"], "steam": fora["steam-input-aceso"]}


# ---------------------------------------------------------------------------
# 1. JOGO FECHADO NÃO ACENDE O STEAM INPUT
# ---------------------------------------------------------------------------
def test_jogo_fechado_nao_acende_o_steam_input(vdf, jogo_fechado) -> None:
    """A foto dela: ninguém jogando, e o Modo afirmando o caminho de um jogo fechado.

    A MORDIDA: em `_o_jogo_no_steam_input`, troque o default `so_aberto=True`
    por `False` (ou apague o `quando != ABERTO`) e a primeira asserção reprova
    com o «Steam Input» aceso sobre o marker de um jogo fechado.

    A SEGUNDA METADE é o que separa a cura de um Steam Input que nunca acende:
    o mesmo jogo, aberto, acende.
    """
    _ponte_de_pe()

    fechado = _tela(_ctx(aberto=False))
    assert fechado == {"modo": "dualsense", "steam": ""}, (
        f"com o jogo FECHADO o Modo acendeu {fechado}: o Modo diz o caminho em "
        f"uso, e um jogo fechado não usa caminho nenhum")

    aberto = _tela(_ctx(aberto=True))
    assert aberto == {"modo": "", "steam": "steam"}, (
        f"o mesmo jogo, ABERTO, não acendeu o Steam Input: {aberto}")


def test_a_escada_do_jogo_continua_devolvendo_o_fechado(jogo_fechado) -> None:
    """A escada fica como está — o «Este jogo não funciona» precisa do terceiro degrau.

    A cura é do MODO, não da escada. Se alguém «curar» tirando o degrau do
    marker de `a_escada_do_jogo`, esta linha reprova: o botão da aba 07 volta a
    responder "não achei jogo nenhum" a quem fechou o jogo e veio reclamar.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    assert a07.a_escada_do_jogo({}) == (int(APPID), a07.FECHADO)


# ---------------------------------------------------------------------------
# 2. CLICAR NO VIZINHO TROCA
# ---------------------------------------------------------------------------
def test_o_sony_dualsense_tira_o_jogo_do_steam_input(vdf) -> None:
    """Steam Input aceso, clique no «Sony DualSense»: o tique seguinte acende ele.

    A MORDIDA: em `modo_dualsense`, troque a última linha por `return None`
    (o gesto de antes) e a primeira asserção reprova — o jogo fica na lista, e
    o tique pinta o «Steam Input» de novo, que é a queixa dela.

    O RAMO É O DE `modo_steam`: a mesma recarga (`METODO_DA_RECARGA`) e o mesmo
    veredito relido do vdf.
    """
    _ponte_de_pe()
    ctx = _ctx(aberto=True)
    assert _tela(ctx) == {"modo": "", "steam": "steam"}

    p = PonteDeMentira()
    assert aba.modo_dualsense(ctx, {"texto": "Sony DualSense"}, p) is None

    assert APPID not in ponte.ler_allowlist(), (
        "o «Sony DualSense» não tirou o jogo da lista do Steam Input")
    assert _valor(vdf, APPID) == ponte.DESLIGADO, (
        f"a lista saiu e o vdf ficou em {_valor(vdf, APPID)!r}")
    assert _tela(ctx) == {"modo": "dualsense", "steam": ""}, (
        f"depois do clique o Modo pinta {_tela(ctx)}")
    assert METODO_DA_RECARGA in p.chamadas and "gamepad.emulation.set" in p.chamadas


def test_o_sony_dualsense_alcanca_o_jogo_fechado(vdf, jogo_fechado) -> None:
    """Com o jogo fechado o «Steam Input» não acende — e o clique ainda o tira.

    É o «clique de novo» da recusa do jogo aberto: sem isto ela fecharia o jogo,
    clicaria no «Sony DualSense», e o «Steam Input» voltaria na próxima partida.

    A MORDIDA: troque o `so_aberto=False` do ramo do «Sony DualSense» em
    `_o_jogo_que_sai_do_steam_input` por `True` e esta régua reprova.
    """
    _ponte_de_pe()
    aba.modo_dualsense(_ctx(aberto=False), {"texto": "Sony DualSense"},
                       PonteDeMentira())
    assert APPID not in ponte.ler_allowlist(), (
        "o «Sony DualSense» com o jogo fechado deixou o jogo na lista — ele "
        "volta a acender o «Steam Input» quando ela abrir o jogo")


@pytest.mark.parametrize(("gesto", "rotulo"), [
    ("modo_xbox", "Xbox"),
    ("modo_navegacao", "Navegação"),
])
def test_xbox_e_navegacao_com_o_steam_input_aceso_tiram_o_jogo(
        vdf, gesto, rotulo) -> None:
    """Saem do degrau 4 E tiram o jogo da lista — senão ele volta com o DualSense.

    A MORDIDA: troque, no ramo do «Xbox»/«Navegação» de
    `_o_jogo_que_sai_do_steam_input`, o `return _o_jogo_no_steam_input(...)`
    por `return ""` e esta régua reprova nas duas pontas.
    """
    _ponte_de_pe()
    getattr(aba, gesto)(_ctx(aberto=True), {"texto": rotulo}, PonteDeMentira())
    assert APPID not in ponte.ler_allowlist(), (
        f"«{rotulo}» saiu do Steam Input aceso e deixou o jogo na lista")


def test_a_navegacao_sem_o_steam_input_aceso_nao_mexe_na_lista(vdf, jogo_fechado) -> None:
    """Entrar na Navegação para usar o mouse não tira o jogo que ela marcou.

    O jogo está fechado, logo o «Steam Input» não está aceso: ela não viu nada
    a desligar. A MORDIDA: passe `so_aberto=False` também no ramo do
    «Xbox»/«Navegação» e o último jogo marcado sai da lista calado.
    """
    _ponte_de_pe()
    aba.modo_navegacao(_ctx(aberto=False), {"texto": "Navegação"}, PonteDeMentira())
    assert APPID in ponte.ler_allowlist(), (
        "a Navegação tirou da lista um jogo fechado — o Steam Input nem estava aceso")


def test_com_o_jogo_da_steam_aberto_o_sony_dualsense_recusa_dizendo(
        vdf, monkeypatch) -> None:
    """O portão é o do dono: jogo aberto, nada muda na lista, e a frase é a dele.

    E o «Xbox», no mesmo estado, NÃO recusa: o caminho mudou, e a recusa diria
    *"Nada foi mudado"* sobre um caminho que mudou.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )

    _ponte_de_pe()
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_game_running", lambda: True)

    with pytest.raises(RuntimeError) as erro:
        aba.modo_dualsense(_ctx(aberto=True), {"texto": "Sony DualSense"},
                           PonteDeMentira())
    assert str(erro.value) == format_steam_janela_recusa("jogo_aberto")
    assert APPID in ponte.ler_allowlist()

    assert aba.modo_xbox(_ctx(aberto=True), {"texto": "Xbox"}, PonteDeMentira()) is None
    assert APPID in ponte.ler_allowlist()


# ---------------------------------------------------------------------------
# 3. O PRAZO ESTOURADO DIZ A FALHA
# ---------------------------------------------------------------------------
def test_o_xbox_sem_resposta_do_daemon_diz_a_falha(
        vdf, _sem_pendencia_e_sem_perfil) -> None:
    """`[daemon mudo] timed out` não pisca mais verde.

    A pendência é anotada ANTES da recusa — ela some sozinha se o daemon
    alcançar tarde — e o perfil NÃO é gravado sobre um pedido não confirmado.

    A MORDIDA: faça `_aplicar` devolver `True` sempre e o gesto volta sem
    levantar; a primeira asserção reprova.
    """
    p = PonteDeMentira("gamepad.emulation.set")
    with pytest.raises(RuntimeError) as erro:
        aba.modo_xbox(_ctx(aberto=False), {"texto": "Xbox"}, p)

    assert str(erro.value) == aba.MODO_SEM_CONFIRMACAO
    assert aba._ESCOLHA.get("caminho") == "xbox", (
        f"a pendência não foi anotada: {aba._ESCOLHA}")
    assert _sem_pendencia_e_sem_perfil == [], (
        "o perfil gravou um caminho que o daemon não confirmou")


def test_o_interruptor_sem_resposta_do_daemon_diz_a_falha() -> None:
    """A MESMA CURA NOS DOIS CHAMADORES de `_aplicar` — o interruptor também."""
    p = PonteDeMentira("native.mode.set")
    with pytest.raises(RuntimeError) as erro:
        aba.hefesto(_ctx(aberto=False), {"modo": "native", "texto": "Desligado"}, p)
    assert str(erro.value) == aba.MODO_SEM_CONFIRMACAO


def test_a_pendencia_do_prazo_estourado_some_quando_o_daemon_alcanca() -> None:
    """Um `False` pode vir com o caminho aplicado — e a pendência some sozinha.

    É o que a frase promete ao dizer *pode não ter acontecido*: se o caminho
    vivo chegar ao «Xbox», nada fica pendurado.
    """
    with pytest.raises(RuntimeError):
        aba.modo_xbox(_ctx(aberto=False), {"texto": "Xbox"},
                      PonteDeMentira("gamepad.emulation.set"))
    assert aba._pendencia(_ctx(aberto=False, caminho="dualsense").state) == {
        "caminho": "xbox"}
    assert aba._pendencia(_ctx(aberto=False, caminho="xbox").state) == {}
