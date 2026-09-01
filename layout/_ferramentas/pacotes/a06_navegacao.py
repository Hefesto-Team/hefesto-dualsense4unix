#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

O QUE NÃO TEM: os cinco gestos (PS+Options, PS+↑…) e as velocidades de cursor e
rolagem. Eles moram no PERFIL, não no `state_full` — e o perfil só chega à tela
por outro caminho de IPC, que esta aba ainda não tem.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estava escrito que a velocidade do cursor e da
#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
#: `mouse_emulation`, junto com se a emulação está ligada e por que está
#: bloqueada — medido no daemon dela: `{"enabled": false, "speed": 6,
#: "scroll_speed": 1, "bloqueio": "desligada"}`.
#:
#: Os gestos vêm do perfil (`key_bindings`), que também tem dono. Sobra nada.
SEM_DONO: dict[str, str] = {}


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        primario = bool(c.get("is_primary"))
        cards[str(c.get("uniq") or "")] = {
            "navega": "Navega o PC" if primario else "Só a janela",
            "via": (c.get("transport") or "").upper(),
        }
    return {
        "colunas": cards,
        "mesa": {
            # AS DUAS VELOCIDADES, do daemon — não do perfil. O perfil guarda o
            # que ela SALVOU; o daemon diz o que está VALENDO agora, e é o
            # segundo que a tela mostra.
            "vel-cursor": rato.get("speed"),
            "vel-rolagem": rato.get("scroll_speed"),
            "rato-ligado": bool(rato.get("enabled")),
            "rato-bloqueio": rato.get("bloqueio") or "",
            "rato-despachando": bool(rato.get("despachando")),
            "teclado-ligado": bool(tecla.get("enabled")),
            "teclado-osk": bool(tecla.get("osk_disponivel")),
            "gestos": len(atalhos),
            "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
        },
        "sem_dono": {},
        "cobertura": {"pintados": len(cards) * 2 + 9, "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
#
# ESTA ABA NÃO ENDEREÇA POR CONTROLE, e é decisão do desenho: o `title` da fita
# diz, com todas as letras, *"Não se aplica: mouse, teclado e gestos saem de um
# controle só"* — o primário. Nenhum gesto daqui pede `uniq`, e nenhum dos três
# métodos do daemon aceita um: `mouse.emulation.set`, `mouse.emulation.restore`
# e `keyboard.emulation.set` valem para a MÁQUINA.
#
# DE ONDE VEM O NÚMERO QUE O GESTO SOMA: do `ctx`, que é o estado do ÚLTIMO
# TIQUE (500 ms, `hefesto_vivo.TIQUE_MS`). Dois cliques dentro do mesmo tique
# leem o mesmo `atual` e mandam o mesmo alvo — o segundo não anda. Ler o daemon
# a cada clique custaria um `daemon.state_full` por clique (57 ms medidos, e
# HARM-15 já registra que ele passa dos 0,25 s sob carga), e ainda assim a tela
# só repinta no tique. Fica declarado aqui porque é o que alguém vai medir.
# ---------------------------------------------------------------------------
from hefesto_dualsense4unix.app.actions.mode_transition import (  # noqa: E402
    MODE_DESKTOP,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
)

from . import gesto  # noqa: E402

#: A ORIGEM É `manual` PORQUE É A MÃO DELA. `origem_do_pedido`
#: (`daemon/ipc_handlers.py:46`) lê a AUSÊNCIA como `"profile"`, e a assimetria é
#: de propósito — foi um cliente que só reconciliava estado, promovido a gesto
#: humano, que devolveu o gamepad virtual com o grab pulado e pôs um "Jogador 3"
#: fantasma na tela dela (JOGADOR-3-FANTASMA-01). Aqui é clique, logo é manual.
MANUAL = "manual"


def _rato(ctx: Contexto) -> dict:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora.

    Ele é o do DAEMON, e não o do perfil: o perfil guarda o que ela salvou, e a
    tela mexe no que está ligado. É a mesma escolha que a função de pintura
    acima já fazia.
    """
    return ctx.state.get("mouse_emulation") or {}


def _passo(o: dict) -> int:
    """`+1` ou `-1`, lido do NOME do gesto que chegou.

    O piloto manda `o["gesto"]` com o `data-gesto` do botão clicado
    (`hefesto_vivo.py:202`), e os dois botões de um `bignum` são
    `<nome>-menos` e `<nome>-mais`. Assim a direção não precisa de um atributo
    novo — e `data-v`, que seria o candidato, é o único da lista do piloto que
    o portão do desenho NÃO ignora (`check_o_desenho_aprovado.INVISIVEIS`), o
    que faria toda marcação virar divergência de desenho.
    """
    nome = str(o.get("gesto") or "")
    if nome.endswith("-mais"):
        return 1
    if nome.endswith("-menos"):
        return -1
    raise ValueError(f"velocidade: o clique não disse a direção (veio {nome!r})")


def _mandar(p, **params) -> None:
    """`mouse.emulation.set`, e RECLAMA quando ninguém respondeu.

    `p.chamar` devolve `False` só em falha de TRANSPORTE — o `_safe_call`
    (`app/ipc_bridge.py:103`) não olha o corpo. Um `{"status": "failed",
    "bloqueio": "sem_device"}` volta como `True` daqui, e o gesto **não tem como
    saber**: a ponte não expõe o `_call_checked_detalhado`, que é o único que
    entrega o corpo. Está no relato como achado; enquanto isso, o que dá para
    dizer com verdade é "ninguém respondeu", e é o que se diz.
    """
    if not p.chamar("mouse.emulation.set", **params):
        raise RuntimeError("o Hefesto não respondeu — a velocidade não mudou")


@gesto("06-navegacao.html", "modo")
def modo(ctx: Contexto, o: dict, p) -> None:
    """"Status do Modo": o interruptor que liga mouse E teclado.

    POR QUE OS DOIS, e não só o mouse: este interruptor é o que ela pediu em
    27/08 no lugar de dois botões — *"Suspender Mouse e Teclado, Sair do Modo
    Jogo, deixam de existir devido ao botão status na parte superior"* —, e a
    dica dele diz o alcance: *"nada desta aba chega ao PC"*. Teclado é desta
    aba. São duas chamadas porque o daemon tem dois interruptores separados
    (`mouse.emulation.set` e `keyboard.emulation.set`), e o segundo nasceu
    justamente porque desligar o mouse deixava o teclado emitindo Alt+Tab dentro
    da partida (`daemon/ipc_handlers.py:5032`).

    O MOUSE VAI PRIMEIRO de propósito: é ele que tem exclusão mútua com o
    gamepad virtual (`daemon/lifecycle.py:1359` — ligar o mouse PARA o vpad). Se
    a primeira falhar, a segunda não chega a rodar e o teclado não fica ligado
    sozinho num modo que não é dele.

    O LADO PARA ONDE IR SAI DO DAEMON, nunca da caixinha: o piloto não sabe
    escrever `checked` (o `escrever()` dele cobre texto, largura, fundo e
    `value`), então o desenho nasce `checked` e o daemon dela nasce
    `enabled=false` — ler a tela inverteria o gesto no primeiro clique.

    O PORTÃO DO MODO É DO PRODUTO, e está copiado dele: `_sync_mouse_mode_gate`
    (`app/actions/mouse_actions.py:299`) faz `blocked = mode != MODE_DESKTOP` e
    desliga o interruptor nos DOIS sentidos, inclusive com o modo desconhecido.
    A razão está escrita lá e é o que este gesto herda: *"Ligar o switch durante
    'Jogar pelo Hefesto' derrubava o vpad e os jogadores do co-op SEM AVISO (a
    exclusão mútua do daemon é silenciosa)"*.

    A FRASE É OUTRA, e tem de ser: a do produto (`MODE_GATE_HINT`) manda ir à
    **aba Início**, que não existe no desenho das dez abas — o modo mudou para a
    aba **Jogar**. Reusá-la mandaria ela a uma aba que não está lá. Reusar o
    módulo também não dá: `mouse_actions.py` importa GTK no topo, e os pacotes
    são puros de propósito.
    """
    if not ctx.state:
        raise RuntimeError(
            "não consegui falar com o Hefesto agora, então não sei se ligar o "
            "mouse derrubaria um jogo em andamento. Tente de novo em instantes.")
    atual = mode_of_state(ctx.state)
    if atual != MODE_DESKTOP:
        raise RuntimeError(
            "só dá para mexer no mouse e no teclado fora do jogo: jogando, o "
            "controle é do jogo, e ligar o mouse aqui derrubaria o controle "
            "virtual e os jogadores do co-op no meio da partida. O degrau se "
            "troca na aba Jogar.")

    novo = not bool(_rato(ctx).get("enabled"))
    if not p.chamar("mouse.emulation.set", enabled=novo, origin=MANUAL):
        raise RuntimeError("o Hefesto não respondeu — o mouse ficou como estava")
    if not p.chamar("keyboard.emulation.set", enabled=novo):
        raise RuntimeError("o mouse mudou e o teclado não — o Hefesto não respondeu")


@gesto("06-navegacao.html", "vel-cursor-mais")
@gesto("06-navegacao.html", "vel-cursor-menos")
def vel_cursor(ctx: Contexto, o: dict, p) -> None:
    """O menos e o mais do "Analógico" da Velocidade de cursor. `mouse_emulation.speed`.

    SEM `enabled` DE PROPÓSITO, e é a rota que o produto criou para isto: o
    handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py:4970`), que atualiza a config e o device vivo **sem
    start/stop e sem gravar o flag**. É o que impede um passo de velocidade de
    RELIGAR a emulação e matar o gamepad virtual — a regressão que o
    BUG-MOUSE-GUI-SYNC-01 (A4) fechou. O `_send_mouse_param_async` da GUI
    estável (`app/actions/mouse_actions.py:559`) manda exatamente este payload.

    NÃO SE APARA O NÚMERO AQUI. O teto e o piso têm dono e é o daemon:
    `max(1, min(12, int(speed)))` em `daemon/lifecycle.py:1429` e de novo em
    `UinputMouseDevice.set_speed` (`integrations/uinput_mouse.py:260`). Repetir
    `1..12` neste arquivo seria a segunda verdade que esta casa persegue — e ela
    envelheceria calada no dia em que a faixa mudasse. Um `13` chega, vira 12, e
    o tique seguinte repinta 12 na tela.

    O CHÃO É O DO PRODUTO: sem `speed` no estado (daemon sem responder ainda), o
    passo parte de `DEFAULT_MOUSE_SPEED`, que é o mesmo 6 que o desenho mostra.
    """
    atual = _rato(ctx).get("speed")
    atual = DEFAULT_MOUSE_SPEED if atual is None else int(atual)
    _mandar(p, speed=atual + _passo(o), origin=MANUAL)


@gesto("06-navegacao.html", "rolagem-mais")
@gesto("06-navegacao.html", "rolagem-menos")
def vel_rolagem(ctx: Contexto, o: dict, p) -> None:
    """O menos e o mais do "Analógico" da Velocidade da rolagem. `scroll_speed`.

    Mesma rota speed-only do vizinho, e o mesmo motivo. O que muda é o alcance:
    `scroll_speed` multiplica o passo do analógico DIREITO em `_emit_scroll`
    (`integrations/uinput_mouse.py:426`) e nada mais — o touchpad não rola.

    A FAIXA DELE É OUTRA, e o daemon é quem a impõe: `max(1, min(5, …))`
    (`daemon/lifecycle.py:1431`), contra os 12 do cursor. A dica da tela diz "De
    1 a 10" nas duas linhas, e nas duas está errada — está no relato.
    """
    atual = _rato(ctx).get("scroll_speed")
    atual = DEFAULT_SCROLL_SPEED if atual is None else int(atual)
    _mandar(p, scroll_speed=atual + _passo(o), origin=MANUAL)


#: OS QUATORZE QUE FICARAM SEM DONO, com o motivo de cada um — o inventário
#: honesto do que falta, no lugar de um botão que responde calado. O piloto os
#: recusa PELO NOME (`[gesto sem dono] 06-navegacao.html · <nome>`), e por isso
#: as chaves aqui são os nomes que ele vai imprimir, um por um: os dois `bignum`
#: sem dono viram quatro linhas (`-menos` e `-mais`), porque são quatro botões.
#:
#: `mouse.emulation.restore` NÃO virou botão, e é o terceiro método que esta aba
#: tinha à mão. O handler dele diz por quê, com todas as letras: *"entra na
#: transição de modo (`app/actions/mode_transition.py`), **nunca em um botão
#: solto**"* (`daemon/ipc_handlers.py:5011`). Ele devolve a preferência
#: PERSISTIDA, que não é "o de fábrica" nem "o que a tela mostra" — pendurá-lo
#: no "Voltar ao padrão" faria o botão prometer uma coisa e fazer outra.
SEM_GESTO = {
    "teclado": "três estados na tela ('Ligada', 'Só fora do jogo', 'Desligada') "
               "e um bool no daemon (`keyboard.emulation.set` só lê `enabled`); "
               "e `<select>` não liga por clique",
    "navegacao-interna": "navegar a janela do Hefesto com o controle não tem "
                         "método no daemon — nenhum dos 39",
    "modo-steam": "não há método de Modo Steam no daemon — nenhum dos 39",
    "vel-touch-menos": "o cursor do touchpad SAI do mesmo `mouse_speed` "
                       "(`uinput_mouse.py:446`); não há segundo número a ajustar",
    "vel-touch-mais": "idem",
    "rolagem-dedos-menos": "rolagem por dois dedos no touchpad não existe no "
                           "produto: `_emit_scroll` lê só o analógico direito",
    "rolagem-dedos-mais": "idem",
    "acao-do-gesto": "os cinco combos moram em `key_bindings` do perfil, e não "
                     "há método de IPC que escreva key_bindings",
    "padrao-da-aba": "devolver a aba ao de fábrica mexe em `key_bindings` e nas "
                     "opções do perfil — sem método de IPC",
    "guardar-definicoes": "gravar as 21 linhas é escrever `key_bindings` — "
                          "sem método de IPC",
    "padrao-definicoes": "idem, ao contrário",
    "guardar-remapeamento": "o remapeamento botão-por-botão não tem sequer campo "
                            "no perfil, quanto mais método de IPC",
    "padrao-remapeamento": "idem, ao contrário",
    "guardar-ponto": "o Estilo Point-and-click é um estilo de jogo do perfil; "
                     "gravá-lo não tem método de IPC",
}


PONTE = {"chamar"}
METODOS = {"mouse.emulation.set", "keyboard.emulation.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 5


def _prova(nome: str, clique: dict, chama: list) -> dict:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez.

    Cinco dicionários escritos por extenso repetiam a chave da página cinco
    vezes — e cada repetição custava um marcador `# noqa-acento` (a chave é do
    contrato da régua, não texto em português) e um aviso do ruff sobre ele. Um
    construtor paga o preço uma vez só.
    """
    return {"pagina": PAGINA, "gesto": nome, "clique": clique, "chama": chama}  # noqa-acento  (a chave que a régua lê)


#: O `ctx` da régua não tem `mouse_emulation`, então cada gesto parte do padrão
#: do produto: 6 no cursor e 1 na rolagem. É de propósito — é o mesmo chão que a
#: tela mostra enquanto o daemon ainda não falou.
#:
#: O `rolagem-menos` manda `0`, e não `1`: a faixa tem UM dono e é o daemon
#: (`max(1, min(5, …))`, `daemon/lifecycle.py:1431`). Apará-la aqui seria a
#: segunda verdade, e é ela que envelhece calada no dia em que a faixa mudar.
_MOUSE = "mouse.emulation.set"
PROVAS = [
    _prova("modo", {},
           [("chamar", [_MOUSE], {"enabled": True, "origin": "manual"}),
            ("chamar", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("vel-cursor-mais", {"gesto": "vel-cursor-mais"},
           [("chamar", [_MOUSE], {"speed": 7, "origin": "manual"})]),
    _prova("vel-cursor-menos", {"gesto": "vel-cursor-menos"},
           [("chamar", [_MOUSE], {"speed": 5, "origin": "manual"})]),
    _prova("rolagem-mais", {"gesto": "rolagem-mais"},
           [("chamar", [_MOUSE], {"scroll_speed": 2, "origin": "manual"})]),
    _prova("rolagem-menos", {"gesto": "rolagem-menos"},
           [("chamar", [_MOUSE], {"scroll_speed": 0, "origin": "manual"})]),
]
