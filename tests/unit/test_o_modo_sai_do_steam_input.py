#!/usr/bin/env python3
"""O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01 — a fileira do Modo é um grupo de rádio.

A QUEIXA DELA, 22/09/2026:
*"pq eu nao posso trocar os modos de conexão pela interface?"*  # noqa-acento: citação dela
*"eu saio clicando mas não muda de fato."* A foto: dois DualSense no
rádio, ninguém jogando, «Steam Input» aceso; ela clica «Sony DualSense» e
«Xbox», e o «Steam Input» continua aceso.

A REGRA DELA, 23/09/2026, e é ela que decide o que esta régua cobra: *"fez
errado a idea é eu poder escolher qualquer que seja o modo independnete da
ordem."* A primeira cura desta sprint consertou a foto e deixou a fileira
DEPENDENTE DA ORDEM — o «Steam Input» clicado vindo do «Xbox» só mexia na lista,
o «Xbox» só tirava o jogo da lista se o Steam Input estava aceso, o jogo da
Steam aberto recusava o clique, e com o jogo fechado o «Steam Input» gravava e
não acendia.

O QUE ESTA RÉGUA MEDE, em cinco seções:

1. A TABELA — os quatro chips cravados como a §3 da sprint os escreveu, contra
   `a01_jogar.o_que_o_chip_faz`. É o único número que não sai da função medida.
2. O GRUPO DE RÁDIO — as 16 transições (de cada chip para cada chip), com o
   jogo aberto e fechado, com a Steam aberta e fechada: 64 pares de cliques.
   Depois de cada um o tique acende o chip CLICADO, a lista diz o que a tabela
   diz, o `localconfig.vdf` concorda ou espera, e o clique não recusou.
3. O QUE FICA: a escada do jogo, a única recusa (`sem_jogo`), a mesa vazia, e
   o «Sony DualSense» que tira o jogo da foto dela.
4. O PRAZO ESTOURADO, que diz a falha em vez de piscar verde.
5. A VIGIA com geração: o tique logo depois do clique pinta o disco novo.

Cada teste diz a sua MORDIDA no docstring; as cinco que a sprint pede estão no
da seção 2.

O DAEMON É DE MENTIRA E NÃO É MAIS FROUXO QUE O DE VERDADE — ver
:class:`DaemonDeMentira`: o plano do clique CHEGA ao `state`, pelas mesmas
regras do daemon, e é o `state` que o tique lê. Um dublê que só anotasse os
métodos deixaria a régua medir a lista de chamadas em vez do chip aceso.

O LAR É O DA RÉGUA DA STEAM-INPUT-01, reusado — uma Steam de mentira com
`localconfig.vdf` sintético e appid que não é jogo de ninguém. Os dois fixtures
de guarda (`_steam_fechada`, que também proíbe fechar a Steam, e `_vigia_limpa`)
vêm de lá com o `lar`, e são automáticos aqui também.
"""
from __future__ import annotations

import itertools
import pathlib
import re
import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.daemon import ipc_server, launch_env
from hefesto_dualsense4unix.daemon.ipc_handlers import origem_do_pedido
from hefesto_dualsense4unix.daemon.subsystems.gamepad import ORIGENS_GESTO_DELA
from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho
from hefesto_dualsense4unix.interface import pacotes
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

#: OS MÉTODOS QUE O DAEMON ATENDE — lidos da tabela do servidor de verdade
#: (`daemon/ipc_server.py`), não digitados. Um plano que chamasse um método que
#: não existe passaria verde num dublê que aceita tudo.
_ATENDIDOS = frozenset(re.findall(
    r'"([a-z_.]+)":\s*self\._handle_',
    pathlib.Path(ipc_server.__file__).read_text(encoding="utf-8")))


class DaemonDeMentira:
    """O `p` do gesto E o daemon atrás dele — o plano CHEGA ao `state`.

    NÃO É MAIS FROUXO QUE O DE VERDADE, e cada regra tem o endereço da real:

    * `pacotes/ponte.chamar` devolve `bool`: `False` no prazo estourado, que é
      o `[daemon mudo] timed out` do diário dela (os métodos em `mudo`);
    * método fora da tabela do servidor (`ipc_server`) devolve `False`;
    * `native.mode.set` e `gamepad.emulation.set` exigem `enabled` booleano, e
      um `caminho` que `virtual_pad.normalizar_caminho` não reconhece é
      recusado — nunca vira caminho por default
      (`ipc_handlers._handle_gamepad_emulation_set`);
    * o caminho só é PUBLICADO quando o vpad o alcança
      (`gamepad._guardar_o_caminho`), logo só com `enabled=True`;
    * com o jogo aberto, o pedido que não é gesto dela é segurado e não muda
      nada (`gamepad._recriacao_bloqueada_por_jogo`); a origem é lida pela
      função do daemon (`origem_do_pedido`: sem `origin`, é `profile`). O RPC
      vai bem, e por isso o `chamar` devolve `True` sem mexer no estado.
    """

    def __init__(self, state: dict[str, Any], *mudo: str,
                 jogo_aberto: bool = False) -> None:
        self.state = state
        self.mudo = set(mudo)
        self.jogo_aberto = jogo_aberto
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        self.chamadas.append(metodo)
        if metodo in self.mudo or metodo not in _ATENDIDOS:
            return False
        if metodo == "native.mode.set":
            if not isinstance(params.get("enabled"), bool):
                return False
            self.state["native_mode"] = params["enabled"]
            return True
        if metodo == "gamepad.emulation.set":
            return self._emulacao(params)
        return True

    def _emulacao(self, params: dict[str, Any]) -> bool:
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            return False
        caminho = params.get("caminho")
        if caminho is not None and normalizar_caminho(caminho) is None:
            return False
        if self.jogo_aberto and origem_do_pedido(params) not in ORIGENS_GESTO_DELA:
            return True
        vpad = self.state.setdefault("gamepad_emulation", {})
        vpad["enabled"] = enabled
        if enabled and caminho is not None:
            vpad["caminho"] = normalizar_caminho(caminho)
        return True


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


def _o_marker_do_ultimo_jogo(monkeypatch) -> None:
    """O TERCEIRO DEGRAU da escada: o marker `last_run` do último jogo lançado.

    A escada (`a07_lancadores.a_escada_do_jogo`) é a de verdade; o que se
    dubla são os dois leitores de marker, como a régua da aba 07 faz.
    """
    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (int(APPID), 1))


@pytest.fixture
def jogo_fechado(monkeypatch):
    """O jogo da vez por marker, e nenhum jogo na frente."""
    _o_marker_do_ultimo_jogo(monkeypatch)


def _a_maquina(monkeypatch, *, jogo_aberto: bool, steam_aberta: bool) -> None:
    """A Steam e o jogo, nos DOIS donos — e sem um estado que a máquina não tem.

    `steam_input_ponte` guarda a própria referência de `steam_running` e
    `steam_game_running` (*"from-import copia a referência"*), e um dublê só em
    `steam_launch_options` deixaria o `garantir_ponte` perguntando ao `/proc`.

    `steam_game_running` é o `reaper SteamLaunch` — só existe com a Steam de
    pé. Com a Steam fechada e o jogo ABERTO, o jogo é o de um lançador que se
    anuncia como Steam (o `umu` do Heroic e do Lutris dá `steam_app_<N>`): a
    escada o vê em foco, e o portão da Steam não vê jogo nenhum.
    """
    da_steam = jogo_aberto and steam_aberta
    for dono in (slo, ponte):
        monkeypatch.setattr(dono, "steam_running", lambda: steam_aberta)
        monkeypatch.setattr(dono, "steam_game_running", lambda: da_steam)
    # O marker existe nos dois casos — ela já lançou o jogo antes. Com ele
    # aberto, quem responde primeiro é o degrau da janela em foco.
    _o_marker_do_ultimo_jogo(monkeypatch)


def _ponte_de_pe() -> None:
    """O jogo na lista dela E o vdf dizendo Steam Input — o chip pode acender."""
    slo.add_appid_to_steam_input_allowlist(APPID)
    ponte.garantir_ponte(allowlist=[APPID])
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()


def _parar_a_vigia(monkeypatch) -> None:
    """A vigia leu o disco antes do clique, como a thread do tique faz — e para.

    Depois disto ela NÃO relê sozinha: o tique só vê o que o gesto deixou
    guardado, que é o que o primeiro tique depois do clique vê de verdade. E
    nenhuma thread de leitura sobra para cruzar com o lar do teste seguinte.
    """
    aba.VIGIA_DO_STEAM_INPUT.ler()
    monkeypatch.setattr(aba.VIGIA_DO_STEAM_INPUT, "_disparar", lambda: None)


def _tela(ctx: Contexto) -> dict[str, str]:
    """O que o tique pinta na fileira, com a vigia relida do disco."""
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    fora = aba.pacote(ctx)
    return {"modo": fora["modo-aceso"], "steam": fora["steam-input-aceso"]}


def _aceso(ctx: Contexto) -> str:
    """O chip aceso no TIQUE — o `pacote` inteiro, com o que a vigia TEM.

    Sem reler o disco: o tique de verdade só lê o que a vigia guarda, e o que
    se mede é o que o gesto deixou guardado. E UM ACESO SÓ (a D-2 dela, 21/09):
    dois acesos juntos reprovam aqui, antes de qualquer comparação.
    """
    fora = aba.pacote(ctx)
    acesos = [c for c in (fora["modo-aceso"], fora["steam-input-aceso"]) if c]
    assert len(acesos) <= 1, f"dois chips acesos juntos: {acesos}"
    return acesos[0] if acesos else ""


def _clicar(chave: str, ctx: Contexto, daemon: DaemonDeMentira) -> Any:
    """O clique no chip, pela porta do piloto — o gesto REGISTRADO, não a função.

    `aba01._chip_do_modo` escreve `data-gesto="modo-<chave>"`, e o piloto acha
    o gesto por `pacotes.gesto_da_pagina`. O rótulo vai no `texto`, como o
    piloto manda, e sai do dono dele (`painel.CHIPS_DA_ESCADA`).
    """
    gesto = pacotes.gesto_da_pagina(aba.PAGINA, f"modo-{chave}")
    assert gesto is not None, f"o chip «{chave}» não tem gesto registrado"
    rotulo = aba._rotulo_do_chip(chave)
    try:
        return gesto(ctx, {"texto": rotulo}, daemon)
    except RuntimeError as recusa:
        pytest.fail(f"o clique em «{rotulo}» RECUSOU: {recusa}")


# ---------------------------------------------------------------------------
# 1. A TABELA
# ---------------------------------------------------------------------------
#: A TABELA DA §3 DA SPRINT, cravada — `(modo, caminho, o jogo entra na lista)`.
#: É o único número desta régua que não sai da função medida: derivá-lo de
#: `o_que_o_chip_faz` faria a régua conferir a função contra ela mesma.
TABELA_DA_SPRINT = {
    "dualsense": ("gamepad", "dualsense", False),
    "xbox": ("gamepad", "xbox", False),
    "steam": ("gamepad", "dualsense", True),
    "navegacao": ("desktop", None, False),
}
CHIPS = tuple(TABELA_DA_SPRINT)


def test_a_tabela_e_a_da_sprint() -> None:
    """Uma tabela, um dono — e os quatro chips dela são os quatro da fileira.

    A MORDIDA: faça `o_que_o_chip_faz` devolver `caminho=None` para o
    «Steam Input» (o chip sem caminho da primeira cura) e a primeira asserção
    reprova nomeando a linha.
    """
    lida = {c: tuple(aba.o_que_o_chip_faz(c)) for c in CHIPS}
    assert lida == TABELA_DA_SPRINT, (
        f"a tabela da fileira divergiu da sprint:\n  lida     {lida}\n"
        f"  esperada {TABELA_DA_SPRINT}")
    assert {str(c.chave) for c in painel.CHIPS_DA_ESCADA} == set(CHIPS), (
        "a fileira tem chips que a tabela da sprint não cobre")


# ---------------------------------------------------------------------------
# 2. O GRUPO DE RÁDIO — as 16 transições, com o jogo e com a Steam
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("steam_aberta", [False, True],
                         ids=["steam-fechada", "steam-aberta"])
@pytest.mark.parametrize("jogo_aberto", [False, True],
                         ids=["jogo-fechado", "jogo-aberto"])
@pytest.mark.parametrize(("de", "para"), list(itertools.product(CHIPS, CHIPS)),
                         ids=[f"{a}->{b}" for a, b in itertools.product(CHIPS, CHIPS)])
def test_o_chip_clicado_e_o_que_acende(vdf, monkeypatch, de, para, jogo_aberto,
                                       steam_aberta) -> None:
    """Clicar em qualquer um deixa AQUELE aceso, vindo de qualquer outro.

    A regra dela, §3 item 1: *"com ou sem jogo aberto, com ou sem a Steam
    aberta. Nenhum clique recusa por causa do chip anterior."* Cada caso clica
    a ORIGEM e depois o DESTINO, pela porta do piloto, com o daemon de mentira
    aplicando o plano ao `state`. Depois do clique:

    * o tique acende o chip clicado, e só ele;
    * o jogo da vez está na lista do Steam Input SE E SÓ SE o clicado é o
      «Steam Input» — a terceira coluna da tabela;
    * com a Steam fechada o `localconfig.vdf` concorda; com ela aberta ele não
      é tocado (a Steam regrava o arquivo ao sair) — e o «Steam Input» acende
      mesmo assim, PENDENTE: a faixa diz «Liga quando a Steam fechar» (a frase
      dela, D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE) e o diário leva a do dono;
    * o clique responde com a piscada verde (`None`): nem recusa, nem recado.
      A EXCEÇÃO É A ESCOLHA DELA (24/09/2026): o «Steam Input» com a Steam
      aberta e nenhum jogo ARMA — o rótulo vira «Fechar a Steam?», e o segundo
      clique fecha. Com jogo aberto nada arma: fecharia o jogo.

    AS CINCO MORDIDAS DA SPRINT, e cada uma reprova aqui pela razão dela:

    (a) o «Xbox» sem tirar o jogo da lista → `steam->xbox` reprova na lista;
    (b) o «Steam Input» sem `caminho=dualsense` → `xbox->steam` e
        `navegacao->steam` reprovam no chip aceso (o «Xbox»/nada continua);
    (c) o portão do jogo aberto de volta → todo `jogo-aberto-steam-aberta`
        reprova no clique que RECUSOU;
    (d) o «Steam Input» como interruptor de volta → `steam->steam` apaga;
    (e) o aceso só para jogo aberto de volta → `*->steam` com o jogo fechado
        não acende.
    """
    _a_maquina(monkeypatch, jogo_aberto=jogo_aberto, steam_aberta=steam_aberta)
    ctx = _ctx(aberto=jogo_aberto)
    daemon = DaemonDeMentira(ctx.state, jogo_aberto=jogo_aberto)
    _parar_a_vigia(monkeypatch)

    _clicar(de, ctx, daemon)
    assert _aceso(ctx) == de, (
        f"a ORIGEM «{de}» não acendeu depois do próprio clique "
        f"(jogo aberto={jogo_aberto}, Steam aberta={steam_aberta})")
    antes = _valor(vdf, APPID)

    resposta = _clicar(para, ctx, daemon)

    aceso = _aceso(ctx)
    assert aceso == para, (
        f"de «{de}» para «{para}» (jogo aberto={jogo_aberto}, Steam "
        f"aberta={steam_aberta}): o tique acendeu {aceso!r}")
    na_lista = APPID in ponte.ler_allowlist()
    quer = TABELA_DA_SPRINT[para][2]
    assert na_lista == quer, (
        f"de «{de}» para «{para}»: o jogo da vez {'ficou na' if na_lista else 'saiu da'} "
        f"lista do Steam Input, e a tabela diz que ele "
        f"{'entra' if quer else 'sai'}."
        + (" Com ele na lista a Steam pegaria o controle por baixo do chip aceso"
           if na_lista else " Sem ele na lista o «Steam Input» não tem o que ligar"))
    arma = quer and steam_aberta and not jogo_aberto
    esperada = ({"blocos": {f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]':
                            aba.STEAM_INPUT_ARMADO}} if arma else None)
    assert resposta == esperada, (
        f"de «{de}» para «{para}» (jogo aberto={jogo_aberto}, Steam "
        f"aberta={steam_aberta}): o clique respondeu {resposta!r}, e esperava "
        f"{esperada!r}")

    if steam_aberta:
        assert _valor(vdf, APPID) == antes, (
            f"houve escrita no vdf com a Steam VIVA ({antes!r} -> "
            f"{_valor(vdf, APPID)!r}), e ela regrava o arquivo ao sair")
    else:
        esperado = ponte.LIGADO if quer else ponte.DESLIGADO
        assert _valor(vdf, APPID) == esperado, (
            f"com a Steam fechada o vdf ficou {_valor(vdf, APPID)!r} depois "
            f"de «{para}»; a tabela pede {esperado!r}")

    falta = aba._a_ponte_que_falta(ctx.state)
    if quer and steam_aberta:
        dono = ponte.estado_da_ponte(allowlist=[APPID]).frase()
        assert falta == dono, (
            f"o «Steam Input» PENDENTE não levou a frase do dono à faixa:\n"
            f"  faixa {falta!r}\n  dono  {dono!r}")
        assert dono in aba._faixa_do_pendente(ctx.state)[0]
        assert aba.pacote(ctx)["pendente"] == f"● {aba.STEAM_INPUT_ESPERA}", (
            "o «Steam Input» PENDENTE não disse, na faixa, a frase dela")
    else:
        assert falta == "", f"sobrou pendência do Steam Input depois de «{para}»: {falta!r}"
        assert aba.pacote(ctx)["pendente"] == "", (
            f"a faixa falou depois de «{para}» sem o Steam Input esperando")


@pytest.mark.parametrize("para", CHIPS)
@pytest.mark.parametrize("origem", ["xbox", "navegacao"])
def test_a_origem_que_a_primeira_cura_deixava(vdf, monkeypatch, origem, para) -> None:
    """O «Xbox» ou a «Navegação» COM o jogo na lista e a ponte de pé no vdf.

    É o estado que a fileira dependente da ordem produzia (o «Xbox» não tirava o
    jogo que não via aceso), e o que o «Este jogo não funciona» da aba 07 ainda
    produz — ele marca o jogo sem olhar o Modo. O jogo da Steam está aberto:
    nenhum dos quatro recusa, o clicado acende, e a lista diz o que a tabela diz.

    O «DESLIGAR» ADIADO É O ÚNICO RECADO, e é o de antes
    (:data:`a01_jogar.STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA`): o jogo saiu da
    lista, o vdf ainda diz Steam Input, e a Steam só sai do comando dele quando
    fechar. O dono não tem frase para isso — o `Estado.frase` só fala dos
    PENDENTES —, e a tela diz o que ela faz a seguir. A MORDIDA: devolva `""`
    nesse ramo de `_reconciliar_o_vdf` e o clique pisca verde sobre um jogo que
    a Steam ainda comanda.
    """
    _ponte_de_pe()
    _a_maquina(monkeypatch, jogo_aberto=True, steam_aberta=True)
    ctx = _ctx(aberto=True, caminho="xbox",
               modo="desktop" if origem == "navegacao" else "gamepad")
    daemon = DaemonDeMentira(ctx.state, jogo_aberto=True)
    _parar_a_vigia(monkeypatch)
    assert _aceso(ctx) == origem

    resposta = _clicar(para, ctx, daemon)

    aceso = _aceso(ctx)
    assert aceso == para, f"de «{origem}» (com o jogo na lista) para «{para}»: acendeu {aceso!r}"
    na_lista = APPID in ponte.ler_allowlist()
    assert na_lista == TABELA_DA_SPRINT[para][2], (
        f"de «{origem}» para «{para}»: o jogo {'ficou na' if na_lista else 'saiu da'} "
        f"lista do Steam Input, contra a tabela da sprint")
    assert _valor(vdf, APPID) == ponte.LIGADO, "houve escrita no vdf com a Steam viva"
    if para == aba.CHIP_DO_STEAM_INPUT:
        assert resposta is None
    else:
        assert resposta == {"recado": aba.STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA}, (
            f"«{para}» tirou o jogo da lista com a Steam aberta e respondeu "
            f"{resposta!r}")


def test_o_gesto_dos_quatro_chips_passa_pelo_mesmo_clique() -> None:
    """Os quatro gestos chamam `_o_clique_da_fileira` — UM dono do clique.

    Um quinto caminho de escrita (um gesto que decidisse a lista por conta
    própria) é como a fileira voltaria a depender da ordem sem ninguém ver.
    Lido na ÁRVORE do fonte, não por `grep`: a docstring que explica o dono
    não pode contar como chamada.
    """
    import ast
    import inspect
    import textwrap

    for chave in CHIPS:
        gesto = pacotes.gesto_da_pagina(aba.PAGINA, f"modo-{chave}")
        arvore = ast.parse(textwrap.dedent(inspect.getsource(gesto)))
        chamados = {no.func.id for no in ast.walk(arvore)
                    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)}
        assert "_o_clique_da_fileira" in chamados, (
            f"o gesto de «{chave}» não passa por `_o_clique_da_fileira`")
        assert not chamados & {"add_appid_to_steam_input_allowlist",
                               "remove_appid_from_steam_input_allowlist"}, (
            f"o gesto de «{chave}» escreve a lista por conta própria")


# ---------------------------------------------------------------------------
# 3. O QUE FICA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("aberto", [False, True], ids=["fechado", "aberto"])
def test_um_alvo_so_o_jogo_da_vez_aberto_ou_fechado(vdf, jogo_fechado, aberto) -> None:
    """O jogo da vez acende o «Steam Input» ABERTO OU FECHADO — §3 item 4.

    FATO SUBSTITUÍDO: a primeira cura desta sprint só acendia para o jogo aberto
    e gravava para o fechado, e era a assimetria do «cliquei e nada acendeu».
    Esta régua cobrava o contrário (`test_jogo_fechado_nao_acende_o_steam_input`)
    e foi invertida pela regra dela de 23/09.

    A MORDIDA: devolva a condição `quando != ABERTO` a `_o_jogo_na_lista` e o
    caso `fechado` reprova com o «Sony DualSense» aceso.
    """
    _ponte_de_pe()
    assert _tela(_ctx(aberto=aberto)) == {"modo": "", "steam": "steam"}


def test_a_escada_do_jogo_continua_devolvendo_o_fechado(jogo_fechado) -> None:
    """A escada fica como está — o «Este jogo não funciona» precisa do terceiro degrau.

    Se alguém «curar» tirando o degrau do marker de `a_escada_do_jogo`, esta
    linha reprova: o botão da aba 07 volta a responder "não achei jogo nenhum" a
    quem fechou o jogo e veio reclamar — e o Modo perde o alvo do clique.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    assert a07.a_escada_do_jogo({}) == (int(APPID), a07.FECHADO)


def test_a_unica_recusa_e_o_steam_input_sem_jogo(vdf, monkeypatch) -> None:
    """Sem jogo NENHUM conhecido, só o «Steam Input» recusa — e nada muda.

    A frase é a do dono (`format_game_broken_result(status="sem_jogo")`), e ela
    vem ANTES do plano: nem a lista, nem o vdf, nem o caminho são tocados. Os
    outros três trocam o caminho do mesmo jeito, porque não há jogo a tirar.

    A MORDIDA: mova a guarda para depois de `_aplicar` e o daemon recebe o
    caminho de uma recusa — `daemon.chamadas` deixa de ser vazio.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )

    ctx = _ctx(aberto=False, caminho="xbox")
    daemon = DaemonDeMentira(ctx.state)
    _parar_a_vigia(monkeypatch)
    antes = vdf.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(ctx, {"texto": "Steam Input"}, daemon)
    assert str(erro.value) == format_game_broken_result(status="sem_jogo")
    assert daemon.chamadas == [], f"a recusa mandou o plano ao daemon: {daemon.chamadas}"
    assert ctx.state["gamepad_emulation"]["caminho"] == "xbox"
    assert not slo.steam_input_allowlist_path().exists()
    assert vdf.read_text(encoding="utf-8") == antes

    for chave in ("dualsense", "navegacao", "xbox"):
        _clicar(chave, ctx, daemon)
        assert _aceso(ctx) == chave


@pytest.mark.parametrize("chave", CHIPS)
def test_sem_controle_na_mesa_o_clique_vale_e_nada_acende(
        vdf, jogo_fechado, monkeypatch, chave) -> None:
    """Mesa vazia: o clique chega ao daemon e à lista, e o Modo continua apagado.

    Ordem dela de 22/09 (*"ligado mesmo sem controle"*): o Modo é o caminho de
    UM CONTROLE até o jogo. O grupo de rádio não muda isso — e a escolha feita
    sem controle vale quando ele chegar, que é a segunda metade.
    """
    ctx = _ctx(aberto=False, mesa=False)
    daemon = DaemonDeMentira(ctx.state)
    _parar_a_vigia(monkeypatch)
    _clicar(chave, ctx, daemon)
    assert _aceso(ctx) == ""
    ctx.mesa.append(dict(UM_CONTROLE))
    assert _aceso(ctx) == chave


def test_a_pendencia_do_steam_input_nomeia_o_chip_clicado() -> None:
    """O «Steam Input» pede o caminho do «Sony DualSense» — e a faixa nomeia o clicado.

    O caminho anotado é `dualsense` (a linha dele na tabela), e a rede de
    `_rotulo_de` traduz caminho em rótulo pelo `Chip.caminho` — que só o
    «Sony DualSense» tem. Sem o rótulo do CHIP, um clique sem `texto` poria
    «Vai mudar para: Sony DualSense» sob o botão que ela apertou.

    A MORDIDA: tire o `or _rotulo_do_chip(chave)` de `_lembrar_do_chip` e a
    asserção reprova com «Sony DualSense».
    """
    aba._lembrar_do_chip(aba.CHIP_DO_STEAM_INPUT, {})
    assert aba._ESCOLHA == {"caminho": "dualsense"}
    assert aba._ROTULO == {"caminho": "Steam Input"}, aba._ROTULO


def test_o_sony_dualsense_tira_o_jogo_do_steam_input(vdf) -> None:
    """Steam Input aceso, clique no «Sony DualSense»: o tique seguinte acende ele.

    É o caso da foto dela. O RAMO É O MESMO do «Steam Input»: a mesma recarga
    (`METODO_DA_RECARGA`) e o mesmo veredito relido do vdf.
    """
    _ponte_de_pe()
    ctx = _ctx(aberto=True)
    assert _tela(ctx) == {"modo": "", "steam": "steam"}

    daemon = DaemonDeMentira(ctx.state)
    assert aba.modo_dualsense(ctx, {"texto": "Sony DualSense"}, daemon) is None

    assert APPID not in ponte.ler_allowlist(), (
        "o «Sony DualSense» não tirou o jogo da lista do Steam Input")
    assert _valor(vdf, APPID) == ponte.DESLIGADO, (
        f"a lista saiu e o vdf ficou em {_valor(vdf, APPID)!r}")
    assert _tela(ctx) == {"modo": "dualsense", "steam": ""}, (
        f"depois do clique o Modo pinta {_tela(ctx)}")
    assert METODO_DA_RECARGA in daemon.chamadas
    assert "gamepad.emulation.set" in daemon.chamadas


def test_o_sony_dualsense_alcanca_o_jogo_fechado(vdf, jogo_fechado) -> None:
    """Com o jogo fechado o clique tira o jogo da vez — o mesmo alvo que acende.

    Sem isto ela clicaria no «Sony DualSense» com o jogo fechado, e o «Steam
    Input» voltaria na próxima partida.
    """
    _ponte_de_pe()
    ctx = _ctx(aberto=False)
    aba.modo_dualsense(ctx, {"texto": "Sony DualSense"}, DaemonDeMentira(ctx.state))
    assert APPID not in ponte.ler_allowlist(), (
        "o «Sony DualSense» com o jogo fechado deixou o jogo na lista — ele "
        "volta a acender o «Steam Input» quando ela abrir o jogo")


# ---------------------------------------------------------------------------
# 4. O PRAZO ESTOURADO DIZ A FALHA
# ---------------------------------------------------------------------------
def test_o_xbox_sem_resposta_do_daemon_diz_a_falha(
        vdf, _sem_pendencia_e_sem_perfil) -> None:
    """`[daemon mudo] timed out` não pisca mais verde.

    A pendência é anotada ANTES da recusa — ela some sozinha se o daemon
    alcançar tarde — e o perfil NÃO é gravado sobre um pedido não confirmado.

    A MORDIDA: faça `_aplicar` devolver `True` sempre e o gesto volta sem
    levantar; a primeira asserção reprova.
    """
    ctx = _ctx(aberto=False)
    daemon = DaemonDeMentira(ctx.state, "gamepad.emulation.set")
    with pytest.raises(RuntimeError) as erro:
        aba.modo_xbox(ctx, {"texto": "Xbox"}, daemon)

    assert str(erro.value) == aba.MODO_SEM_CONFIRMACAO
    assert aba._ESCOLHA.get("caminho") == "xbox", (
        f"a pendência não foi anotada: {aba._ESCOLHA}")
    assert _sem_pendencia_e_sem_perfil == [], (
        "o perfil gravou um caminho que o daemon não confirmou")


def test_o_interruptor_sem_resposta_do_daemon_diz_a_falha() -> None:
    """A MESMA CURA NOS DOIS CHAMADORES de `_aplicar` — o interruptor também."""
    ctx = _ctx(aberto=False)
    daemon = DaemonDeMentira(ctx.state, "native.mode.set")
    with pytest.raises(RuntimeError) as erro:
        aba.hefesto(ctx, {"modo": "native", "texto": "Desligado"}, daemon)
    assert str(erro.value) == aba.MODO_SEM_CONFIRMACAO


def test_a_pendencia_do_prazo_estourado_some_quando_o_daemon_alcanca() -> None:
    """Um `False` pode vir com o caminho aplicado — e a pendência some sozinha.

    É o que a frase promete ao dizer *pode não ter acontecido*: se o caminho
    vivo chegar ao «Xbox», nada fica pendurado.
    """
    ctx = _ctx(aberto=False)
    with pytest.raises(RuntimeError):
        aba.modo_xbox(ctx, {"texto": "Xbox"},
                      DaemonDeMentira(ctx.state, "gamepad.emulation.set"))
    assert aba._pendencia(_ctx(aberto=False, caminho="dualsense").state) == {
        "caminho": "xbox"}
    assert aba._pendencia(_ctx(aberto=False, caminho="xbox").state) == {}


# ---------------------------------------------------------------------------
# 5. A VIGIA — o tique depois do clique pinta o disco novo
# ---------------------------------------------------------------------------
def test_o_tique_logo_depois_do_clique_ja_pinta_a_lista_nova(vdf, monkeypatch) -> None:
    """O primeiro tique depois do clique pinta o disco NOVO, sem esperar a vigia.

    O tique só lê o que a vigia guarda (`agora()`), e a releitura dela roda numa
    thread que o tique não espera. Se o gesto só invalidasse o cache, o tique
    seguinte pintaria a leitura de ANTES da escrita, com o «Steam Input» ainda
    aceso. Aqui a thread é desligada: o que se mede é o que está guardado
    quando o gesto volta.

    A MORDIDA: troque a releitura de `_o_clique_da_fileira`
    (`VIGIA_DO_STEAM_INPUT.renovar()`) por `VIGIA_DO_STEAM_INPUT.esquecer()` e o
    tique pinta o «Steam Input».
    """
    _ponte_de_pe()
    ctx = _ctx(aberto=True)
    monkeypatch.setattr(aba.VIGIA_DO_STEAM_INPUT, "_disparar", lambda: None)
    antes = aba.pacote(ctx)
    assert (antes["modo-aceso"], antes["steam-input-aceso"]) == ("", "steam")

    aba.modo_dualsense(ctx, {"texto": "Sony DualSense"}, DaemonDeMentira(ctx.state))

    depois = aba.pacote(ctx)
    assert (depois["modo-aceso"], depois["steam-input-aceso"]) == ("dualsense", ""), (
        f"o tique depois do clique pintou {depois['modo-aceso']!r} / "
        f"{depois['steam-input-aceso']!r}: a leitura guardada era a de antes")


def test_a_leitura_do_tique_em_curso_nao_desfaz_o_clique(vdf, monkeypatch) -> None:
    """A thread da vigia que leu ANTES da escrita e termina DEPOIS não guarda nada.

    O tique dispara a releitura quando o TTL vence, e ela pode estar no meio do
    `localconfig.vdf` quando o gesto escreve. Sem a geração, ela termina depois
    do `renovar()` e guarda o disco de antes por um TTL inteiro (20 s): o
    «Steam Input» que ela desligou volta a acender.

    A MORDIDA: em `_VigiaDoSteamInput.ler`, guarde sem comparar a geração e a
    última asserção reprova com o «Steam Input» aceso.
    """
    _ponte_de_pe()
    ctx = _ctx(aberto=True)
    real = ponte.estado_da_ponte
    leu, solta = threading.Event(), threading.Event()

    def _lenta(*a: Any, **kw: Any) -> Any:
        estado = real(*a, **kw)
        if threading.current_thread().name == "hefesto-steam-input":
            leu.set()
            solta.wait(5)
        return estado

    monkeypatch.setattr(ponte, "estado_da_ponte", _lenta)
    vigia = aba.VIGIA_DO_STEAM_INPUT
    vigia._disparar()
    assert leu.wait(5), "a thread da vigia não chegou a ler"

    aba.modo_dualsense(ctx, {"texto": "Sony DualSense"}, DaemonDeMentira(ctx.state))
    solta.set()
    for fio in threading.enumerate():
        if fio.name == "hefesto-steam-input":
            fio.join(5)

    monkeypatch.setattr(vigia, "_disparar", lambda: None)
    depois = aba.pacote(ctx)
    assert (depois["modo-aceso"], depois["steam-input-aceso"]) == ("dualsense", ""), (
        f"a leitura de antes da escrita terminou por último e pintou "
        f"{depois['modo-aceso']!r} / {depois['steam-input-aceso']!r}")
