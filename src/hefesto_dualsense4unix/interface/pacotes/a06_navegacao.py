#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

O QUE NÃO TEM: os cinco gestos (PS+Options, PS+↑…). Eles NÃO são configuráveis —
`daemon/subsystems/hotkey.py` monta um callback por combo, em código, e o único
pedaço ajustável é o `ps_button_action` da config, que método de IPC nenhum
escreve. A tabela da tela oferece trocar o que cada combo faz; o produto não tem
onde guardar essa troca.

FATO SUBSTITUÍDO (01/09/2026, segunda leva): esta linha dizia que os cinco
gestos "moram no PERFIL". Não moram — o perfil guarda `key_bindings`, que são
os BOTÕES (options, create, l1, r1, l3, r3 e as três regiões do touchpad), e
combo nenhum. A frase sobre as velocidades de cursor e rolagem, que estava na
mesma linha, já tinha caído na primeira leva (ver o `SEM_DONO` logo abaixo).

FATO SUBSTITUÍDO (02/09/2026): **"esta aba MENCIONA 7 campos e PINTA 3"** —
escrito a partir do `--passear`, que imprime `06-navegacao.html  1  3`. Ela
pinta os OITO elementos endereçados. O `3` é contagem de MUDANÇA: o `escrever()`
do piloto devolve `1` só quando o valor novo difere do que a tela já mostra, e
cinco dos oito já coincidiam com o daemon dela (`2 controles:`, `1 USB · 1 BT`,
`6`, `1`, `Ligada — atalhos e teclado na tela`). Ler "mudança" como "pintura" é
a mesma confusão entre a PALAVRA e o ATO que produziu o "77%" falso, com o sinal
trocado — e aqui ela escondia os defeitos REAIS da aba, que a medição achou:
metade da linha do cartão indo para a tela (`_linha_do_cartao`), 8 chaves de 14
emitidas para o vazio (`SEM_ENDERECO`) e um "Guardar" que apagava o perfil
(`guardar_definicoes`).
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estava escrito que a velocidade do cursor e da
#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
#: `mouse_emulation`, junto com se a emulação está ligada e por que está
#: bloqueada — medido no daemon dela: `{"enabled": false, "speed": 6,
#: "scroll_speed": 1, "bloqueio": "desligada"}`.
#:
#: Os atalhos de BOTÃO vêm do perfil (`key_bindings`), que também tem dono.
#: Sobra nada.
SEM_DONO: dict[str, str] = {}

#: O QUE O PACOTE SABE E A PÁGINA NÃO TEM ONDE PÔR — medido em 02/09/2026, com
#: `casamento.py 06-navegacao.html`. É o INVERSO do `SEM_DONO`: lá o produto não
#: sabe responder; aqui ele sabe, e o desenho não tem lugar para a resposta.
#:
#: POR QUE ISTO PRECISOU EXISTIR: `casamento.py` já imprimia os órfãos e
#: **reprovava só o zero**. Esta aba emitia oito chaves para o vazio com o
#: portão verde — e uma delas, `via`, não era falta de lugar: era o pacote
#: mandando METADE de uma linha cujo endereço cobre a linha inteira. Órfão
#: silencioso e defeito real ficavam na mesma pilha, sem ninguém para separá-los.
#: `test_a_06_nao_manda_para_o_vazio.py` passou a cobrar que toda chave órfã
#: esteja AQUI, com a razão.
#:
#: `via` SAIU: virou parte do `navega` (ver `_linha_do_cartao`).
#: `teclado-ligado` SAIU: era o mesmo bit de `teclado-estado`, que tem endereço.
SEM_ENDERECO: dict[str, str] = {
    # OS TRÊS DO MOUSE — o desenho TEM onde: o interruptor "Status do Modo". O
    # que falta é o piloto poder escrevê-lo. O widget é um
    # `<input type="checkbox" checked>` cujo estado a CSS lê (`.tog-in:checked
    # + .tog`), e a palavra "Ligado"/"Desligado" sai de um `content:` — não há
    # nó de texto para pintar, e `escrever()` não sabe marcar uma caixa nem pôr
    # uma classe. Medido em 02/09: o daemon dela tinha `mouse_emulation.enabled
    # = False` e a tela dizia **Ligado**. É a maior mentira desta aba, e a cura
    # é no piloto (um alvo que escreva atributo/classe), não aqui.
    "rato-ligado": "o 'Status do Modo' é um <input checkbox> e o piloto não sabe "
                   "marcar caixa nem trocar classe — hoje ele diz 'Ligado' com a "
                   "emulação desligada",
    "rato-bloqueio": "o motivo do bloqueio não tem linha no desenho; a frase do "
                     "produto é `app/actions/mouse_actions.frase_da_recusa_do_mouse`",
    "rato-despachando": "idem — quem despacha o cursor não aparece no desenho",
    # O TECLADO NA TELA: o produto TEM a frase pronta e humana em
    # `app/actions/input_actions.frase_do_teclado_na_tela(osk_disponivel)`, que a
    # GTK mostra. O desenho desta aba não tem onde pô-la.
    "teclado-osk": "o desenho não tem linha para 'há teclado na tela nesta "
                   "máquina'; a frase existe em "
                   "`app/actions/input_actions.frase_do_teclado_na_tela`",
    # OS ATALHOS DO PERFIL: a tabela da tela é a dos cinco COMBOS (PS+Options…),
    # que não são `key_bindings`. Não há onde mostrar a contagem, e mostrá-la na
    # tabela dos combos seria pôr um número ao lado de outra coisa.
    "gestos": "a tabela da tela é a dos cinco COMBOS, e `key_bindings` são os "
              "nove BOTÕES — não é o mesmo dado, e não há linha para ele",
    "gestos-lista": "idem; e a lista é estrutura, que o piloto pula",
}

#: AS DUAS FRASES DA LISTA "Função do teclado" QUE O DAEMON SABE DIZER, e elas
#: são o outro lado do contrato que `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`
#: desenha. A repetição é declarada, e os dois lados falham de jeitos diferentes
#: de propósito:
#:
#: * o GESTO casa pela primeira palavra (`_ESCOLHA`), então reescrever o que vem
#:   depois do travessão não desliga o botão;
#: * a PINTURA usa a frase inteira, porque `escrever()` do piloto faz
#:   `el.value = texto` e o `<select>` só aceita o texto exato de uma `<option>`
#:   (as opções não têm `value` — ver a nota no gerador sobre o portão do
#:   desenho).
#:
#: A terceira opção do desenho, "Só fora do jogo", NÃO está aqui porque o daemon
#: não tem esse estado — ver `SEM_GESTO` e o corpo de `teclado()`.
TECLADO_LIGADA = "Ligada — atalhos e teclado na tela"
TECLADO_DESLIGADA = "Desligada"

#: O SEPARADOR DO CARTÃO — o mesmo `•` que o desenho põe entre o transporte e o
#: papel (`aba06.controle`: `{via} <span class="pt">•</span> {papel}`). Ele é
#: texto porque o endereço `data-campo="navega"` cobre a LINHA INTEIRA: o piloto
#: escreve `textContent`, e o que não vier na string some da tela.
PONTO = " • "

#: O PREFIXO DAS VINTE E UMA LINHAS de *o que cada botão faz*. Um por botão de
#: `core/acoes_de_botao.BOTOES` — a lista é do produto, e não se digita aqui.
PREFIXO_DA_ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa


def _linha_do_cartao(c: dict[str, Any], primario: bool) -> str:
    """A linha inteira do cartão: `"BT • Navega o PC"`.

    ELA ERA METADE, e a metade que faltava era o TRANSPORTE — medido em
    02/09/2026, com a foto ao lado. O desenho escreve
    `{via} <span class="pt">•</span> {papel}` e põe o `data-campo="navega"` na
    `<div>` que os contém; o pacote mandava só o papel. Como o piloto escreve
    `textContent`, o primeiro tique APAGAVA o "USB •" do cartão — a tela nascia
    dizendo por onde o controle está ligado e parava de dizer meio segundo
    depois, sem que nada acusasse.

    O `via` NÃO SE CALCULA AQUI. `mesa_viva` é o dono da regra
    (`"USB" if transporte == "usb" else "BT"`), e ela já vem mastigada na mesa
    que o piloto monta — repeti-la seria a segunda verdade que envelhece calada.
    O `ctx.conectados` é a resposta CRUA do daemon e traz `transport`; a mesa
    traz `via`. Quem entra na tela é o da mesa.
    """
    papel = "Navega o PC" if primario else "Só a janela"
    return PONTO.join(x for x in (str(c.get("via") or ""), papel) if x)


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O VOCABULÁRIO É O DO MOTOR, inteiro: `acoes.BOTOES` diz quais linhas
    existem, `acoes.padrao()` diz o que cada uma faz de fábrica e
    `acoes.rotulo()` traduz o token no texto da `<option>`. O gerador monta as
    mesmas listas do mesmo lugar (`aba06.ACOES_UNI = por_grupo()`), e é por isso
    que o valor emitido aqui SEMPRE existe como opção — condição do
    `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa.

    O PERFIL VENCE O DE FÁBRICA linha a linha, e não em bloco: `button_actions`
    guarda DIFERENÇA (`None` quer dizer "herda"), então uma linha ausente não é
    "nada" — é o de fábrica.
    """
    escolhas = (p.get("button_actions") or {}) if p else {}
    de_fabrica = acoes.padrao()
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(
            str(escolhas.get(botao) or de_fabrica.get(botao) or ""))
        for botao in acoes.BOTOES
    }


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A MESA É QUEM TEM O `via`. `ctx.conectados` é a resposta crua do
        # daemon (`transport`), e a tradução para "USB"/"BT" tem dono em
        # `mesa_viva.mesa_do_estado`. Sem casa na mesa (um controle que entrou
        # entre a montagem da mesa e este tique), a linha sai só com o papel —
        # meia verdade, nunca um transporte inventado.
        na_mesa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        cards[uniq] = {"navega": _linha_do_cartao(na_mesa, bool(c.get("is_primary")))}
    mesa = {
        # AS DUAS VELOCIDADES, do daemon — não do perfil. O perfil guarda o
        # que ela SALVOU; o daemon diz o que está VALENDO agora, e é o
        # segundo que a tela mostra.
        "vel-cursor": rato.get("speed"),
        "vel-rolagem": rato.get("scroll_speed"),
        "rato-ligado": bool(rato.get("enabled")),
        "rato-bloqueio": rato.get("bloqueio") or "",
        "rato-despachando": bool(rato.get("despachando")),
        "teclado-osk": bool(tecla.get("osk_disponivel")),
        "gestos": len(atalhos),
        "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
    }
    # AS VINTE E UMA LINHAS DE *O QUE CADA BOTÃO FAZ*, do perfil dela — e elas
    # não existiam aqui até 02/09/2026. O botão "Guardar" LIA essas linhas
    # (`data-hef-forma`) e nada as ESCREVIA, então a tela mostrava para sempre o
    # que o desenho escolheu. Ver `guardar_definicoes` para o que isso custava.
    mesa.update(_linhas_dos_botoes(p))
    # A LISTA "Função do teclado" SÓ É REESCRITA QUANDO O DAEMON FALOU, e a
    # ausência da chave é o que impede a mentira: sem o bloco
    # `keyboard_emulation` (daemon mudo, ou config inacessível — o `state_full`
    # OMITE o bloco nesse caso) escrever "Desligada" afirmaria um estado que
    # ninguém mediu. Chave ausente = a pintura não toca no `<select>`.
    #
    # E ela é o ÚNICO canal de recusa VISÍVEL desta aba: um gesto que levanta só
    # imprime no terminal (`hefesto_vivo.py:519`). Escolher "Só fora do jogo",
    # que não tem dono, deixa a lista parada na opção errada até o tique
    # seguinte reescrevê-la com o que o daemon diz.
    if "keyboard_emulation" in st:
        mesa["teclado-estado"] = (
            TECLADO_LIGADA if tecla.get("enabled") else TECLADO_DESLIGADA)
    return {
        "colunas": cards,
        "mesa": mesa,
        "sem_dono": {},
        # O NÚMERO SAI DOS DICIONÁRIOS, e não de uma constante escrita à mão:
        # foi uma soma digitada (`len(cards) * 2 + 9`) que deixou a curva da aba
        # Gatilhos fora da cobertura, e aqui ela erraria no tique em que a lista
        # do teclado entra — o valor é condicional.
        #
        # E ELE DESCONTA O QUE NÃO TEM ONDE CAIR — 02/09/2026. Contar chave
        # EMITIDA como "pintado" é a mesma confusão entre a PALAVRA e o ATO que
        # produziu o "77%" falso desta casa: medido no mesmo dia, esta aba
        # emitia 14 chaves e a página tinha endereço para 6. O instrumento dizia
        # 14. Um contador que mente é pior que um campo parado.
        "cobertura": {"pintados": (sum(len(v) for v in cards.values())
                                   + len(set(mesa) - set(SEM_ENDERECO))),
                      "sem_dono": len(SEM_DONO)},
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


def _rato(ctx: Contexto) -> dict[str, Any]:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora.

    Ele é o do DAEMON, e não o do perfil: o perfil guarda o que ela salvou, e a
    tela mexe no que está ligado. É a mesma escolha que a função de pintura
    acima já fazia.
    """
    return ctx.state.get("mouse_emulation") or {}


def _passo(o: dict[str, Any]) -> int:
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


def _mandar(p: Any, **params: Any) -> None:
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
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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


#: O QUE CADA PALAVRA DA LISTA MANDA FAZER. A chave é a PRIMEIRA palavra da
#: opção, em minúsculas — e as três se distinguem por ela ("ligada", "só",
#: "desligada"), o que deixa o gesto sobreviver a uma reescrita do que vem
#: depois do travessão. Casar a frase inteira quebraria no dia em que alguém
#: melhorasse o texto da tela, e quebraria CALADO: um `<select>` cujo valor não
#: casa com nada simplesmente não faria nada.
#:
#: `None` é a opção que a tela oferece e o daemon NÃO tem. Ela não vira `False`
#: por conveniência: ver `teclado()`.
_ESCOLHA: dict[str, bool | None] = {"ligada": True, "desligada": False, "só": None}


@gesto("06-navegacao.html", "teclado")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A lista "Função do teclado". `keyboard.emulation.set`.

    O VALOR VEM EM `valor`, E ISSO É O QUE MUDOU DESDE A PRIMEIRA LEVA: o
    ouvinte do piloto passou a escutar `change` além de `click` e a mandar o
    `value` do alvo (`hefesto_vivo.py:196` e `:230`). Antes só chegava `texto`,
    que num `<select>` é a lista INTEIRA de opções concatenada — foi por isso
    que esta lista ficou sem dono na primeira leva, e não por falta de método.

    O `rotulo` É O SEGUNDO CAMINHO, não um enfeite: as `<option>` desta lista
    não têm atributo `value` (`value` não está entre os que o portão do desenho
    ignora), então `select.value` **é** o texto — mas um `<option value=…>` que
    nasça amanhã mandaria a chave em `valor` e a frase em `rotulo`, e é o
    `rotulo` que continuaria casando com o desenho.

    DUAS DAS TRÊS OPÇÕES TÊM DONO, e a terceira RECUSA DIZENDO — que é a regra
    da casa, não uma falha desta ligação:

    * "Ligada…" → `enabled=True`; "Desligada" → `enabled=False`. O handler
      (`daemon/ipc_handlers.py:5038`) só lê `enabled`, e ele é bool.
    * "Só fora do jogo" **não existe do outro lado**. O que mais se parece com
      ela é o "modo jogo" (`daemon.emulation.suppress`), e ele é o contrário do
      que o rótulo promete: suspende mouse E teclado **agora**, no desktop,
      independentemente de haver jogo — `set_emulation_suppressed`
      (`daemon/lifecycle.py:1876`) só inverte um bool. O único caminho que
      liga a supressão SOZINHO quando um jogo começa é o perfil
      (`apply_profile_suppression`, a partir de `suppress_desktop_emulation`),
      e método de IPC nenhum grava perfil. Pendurar a opção no
      `emulation.suppress` faria a tela dizer "só fora do jogo" e o teclado
      morrer DENTRO do desktop, no mesmo clique.

    SEM PORTÃO DE MODO, ao contrário do gesto `modo` logo acima, e é medido: o
    portão de lá existe porque ligar o MOUSE derruba o gamepad virtual — o
    `set_mouse_emulation` (`daemon/lifecycle.py:1336`).

    Do outro lado, o teclado não mexe no gamepad virtual em momento nenhum.
    Quem o liga e desliga é o
    `set_keyboard_emulation` (`daemon/lifecycle.py:1469`): ele cria ou destrói o
    teclado virtual e nada mais.

    E COM O GAMEPAD DESPACHANDO, o teclado nem chega a ser consultado — a
    guarda está em `lifecycle.py:2240`, no `if not gamepad_dispatched`. Copiar o
    portão daqui bloquearia, dentro do jogo, o único interruptor que existe
    para calar o Alt+Tab do R1 — que é o defeito que este método nasceu para
    curar (queixa dela, 29/07).

    O QUE ESTE BOTÃO AINDA NÃO DIZ, e está no relato: desligar tira também o
    teclado na tela do L3/R3 e as três regiões do touchpad (o handler manda a
    interface repassar isso). O piloto não tem canal de aviso — um gesto só
    imprime no terminal —, então o recado não tem onde aparecer.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    chave = escolhido.split()[0].lower() if escolhido else ""
    if chave not in _ESCOLHA:
        raise ValueError(
            f"teclado: não reconheci a opção escolhida ({escolhido!r}). As três "
            f"do desenho estão em `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`.")
    ligar = _ESCOLHA[chave]
    if ligar is None:
        raise RuntimeError(
            "\"Só fora do jogo\" ainda não tem dono: o Hefesto liga e desliga o "
            "teclado, mas não sabe fazê-lo só durante o jogo — isso mora no "
            "perfil (`suppress_desktop_emulation`), e não há comando que grave "
            "perfil. A lista volta sozinha para o que está valendo.")
    if not p.chamar("keyboard.emulation.set", enabled=ligar):
        raise RuntimeError("o Hefesto não respondeu — o teclado ficou como estava")


@gesto("06-navegacao.html", "vel-cursor-mais")
@gesto("06-navegacao.html", "vel-cursor-menos")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O menos e o mais do "Analógico" da Velocidade de cursor. `mouse_emulation.speed`.

    SEM `enabled` DE PROPÓSITO, e é a rota que o produto criou para isto: o
    handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py:4970`), que atualiza a config e o device vivo **sem
    start/stop e sem gravar o flag**. É o que impede um passo de velocidade de
    RELIGAR a emulação e matar o gamepad virtual — a regressão que o
    BUG-MOUSE-GUI-SYNC-01 (A4) fechou. O `_send_mouse_param_async` da GUI
    estável (`app/actions/mouse_actions.py:559`) manda exatamente este payload.

    NÃO SE APARA O NÚMERO AQUI. O teto e o piso têm dono e é o daemon:
    A faixa tem dono desde 01/09/2026 —
    `MOUSE_SPEED_MIN`/`MAX` em `integrations/uinput_mouse.py:78`, lidos
    pelo `set_speed` (`integrations/uinput_mouse.py:279`). Repetir
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
def vel_rolagem(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O menos e o mais do "Analógico" da Velocidade da rolagem. `scroll_speed`.

    Mesma rota speed-only do vizinho, e o mesmo motivo. O que muda é o alcance:
    `scroll_speed` multiplica o passo do analógico DIREITO em `_emit_scroll`
    (`integrations/uinput_mouse.py:466`) e nada mais — o touchpad não rola.

    A FAIXA DELE É OUTRA, e o daemon é quem a impõe: `max(1, min(5, …))`
    (`daemon/lifecycle.py:1449` e `:1452`), contra os 12 do cursor. A dica da tela
    1 a 10" nas duas linhas, e nas duas está errada — está no relato.
    """
    atual = _rato(ctx).get("scroll_speed")
    atual = DEFAULT_SCROLL_SPEED if atual is None else int(atual)
    _mandar(p, scroll_speed=atual + _passo(o), origin=MANUAL)


def _perfil_ativo_ou_recusa(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou a recusa com o motivo.

    OS ATALHOS SÃO DO PERFIL, não da máquina (`profiles/schema.py`), e essa é a
    frase que a recusa precisa carregar: sem ela, "não deu" vira mistério.
    """
    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o que cada botão faz é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis e tente de novo.")
    return nome


@gesto("06-navegacao.html", "guardar-definicoes")
def guardar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" das 21 linhas de *o que cada botão faz*. `Profile.button_actions`.

    ELE PASSOU A TER DONO EM 01/09/2026, por decisão dela: *"ganha campo. essa é
    a parte das features que precisam ou serem ajustadas ou desenvolvidas."* O
    que o segurava era medido e verdadeiro — a tela deixava escolher 21 linhas e
    o perfil alcançava 9 —, e a cura foi o campo nascer, não o botão fingir.

    DE ONDE VEM O QUE ELE GRAVA: da `forma`, que o piloto recolhe quando o botão
    traz `data-hef-forma`. O ouvinte manda o valor do elemento CLICADO, e o
    Guardar é outro elemento — sem a forma, ele não teria como saber o que está
    escolhido em cada linha, e era por isso que só podia recusar.

    SÓ O QUE MUDOU VAI PARA O DISCO. Gravar as 21 sempre encheria o perfil de
    linhas iguais ao padrão, e no dia em que o padrão do produto mudasse o perfil
    congelaria o padrão VELHO sem ninguém ter escolhido isso. `button_actions`
    guarda diferença, e é o que o `None` do campo quer dizer: herda.

    E QUANDO NADA MUDOU, ele grava `None` — que apaga o campo. É o mesmo estado
    de um perfil que nunca foi editado, e não um `{}`, que seria "nenhum botão
    faz nada".

    ELE ERA UM APAGADOR COM RÓTULO DE "GUARDAR", e isso foi medido em
    02/09/2026, contra a página PUBLICADA: as 21 `<select>` da tela de pop-up
    têm `data-linha` (que o Guardar LÊ) e nenhum `data-campo` (que a pintura
    ESCREVERIA), então nada nunca as pintou com o perfil dela — elas mostram o
    que o gerador cravou. Medido linha a linha: as 21 opções cravadas são
    **exatamente** `acoes.padrao()`, logo `diferentes` saía `{}` e o gesto
    gravava `button_actions = None` — apagando, em silêncio, qualquer escolha
    que o perfil dela guardasse. O botão dizia "Guardar" e fazia o contrário.

    A CURA TEM DUAS METADES, e só a primeira é deste arquivo:

    * o pacote passa a EMITIR as 21 linhas (`_linhas_dos_botoes`), e o gerador a
      marcá-las com `data-campo` — quando o desenho for publicado, a tela mostra
      o perfil e o Guardar volta a ser verdade;
    * até lá, o gesto RECUSA em vez de apagar (a trava logo abaixo).

    O QUE A TELA OFERECE E O PRODUTO NÃO ATENDE **é dito, não engolido**: os
    comandos "Abrir a Steam", "Sair do modo jogo" e "Escolher um programa…", os
    dois papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho
    do cross e do triangle (`uinput_mouse._resolve_emulated_set`). O gesto GRAVA
    o resto e LEVANTA nomeando o que não pousou — quem clicou fica sabendo, em
    vez de descobrir pelo botão que não responde.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")

    escolhas: dict[str, str] = {}
    nao_reconhecidas: list[str] = []
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        token = acoes.token_do_rotulo(str(rotulo))
        if token is None:
            nao_reconhecidas.append(f"{botao}={rotulo!r}")
            continue
        escolhas[botao] = token
    if nao_reconhecidas:
        raise ValueError(
            "estas linhas trazem uma opção que o produto não conhece: "
            + ", ".join(nao_reconhecidas)
            + ". A lista da tela e a do produto saem do mesmo lugar "
              "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
              "andou sem o gerador.")

    de_fabrica = acoes.padrao()
    diferentes = {b: a for b, a in escolhas.items() if de_fabrica.get(b) != a}

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = diferentes or None
    if prof.button_actions == novo:
        return
    # A TRAVA CONTRA O APAGADOR — 02/09/2026, e ela vale enquanto a tela não
    # mostrar o perfil. "Nada diferente do de fábrica" só quer dizer "ela zerou
    # as 21 linhas" se as 21 linhas tiverem chegado a MOSTRAR o que o perfil
    # guarda; com a página publicada de hoje elas nunca mostram, e então esta
    # forma quer dizer outra coisa: *o piloto releu o desenho*.
    #
    # E ZERAR TEM BOTÃO PRÓPRIO, a dois centímetros: "Voltar ao padrão"
    # (`padrao-definicoes`), que zera dizendo e ainda pede confirmação. Um
    # "Guardar" que apaga em silêncio é o botão que responde calado — o defeito
    # que esta casa mais persegue.
    if novo is None and prof.button_actions:
        raise RuntimeError(
            "não guardei: as 21 linhas da tela estão todas no de fábrica, e o "
            f"perfil “{nome}” guarda "
            f"{len(prof.button_actions)} escolha(s) sua(s). Gravar isto as "
            "apagaria. Enquanto a tela não mostrar o que o perfil guarda, o "
            "Guardar não pode ler o desenho como se fosse a sua escolha — para "
            "voltar tudo ao de fábrica de propósito, use o “Voltar ao padrão” "
            "ao lado.")
    perfil.gravar_e_reaplicar(prof.model_copy(update={"button_actions": novo}), ctx, p)

    _, _, sem_dono = acoes.resolver(novo)
    if sem_dono:
        raise RuntimeError(
            "guardei o que o produto sabe fazer, e estas linhas ficaram sem "
            "quem as atenda: " + ", ".join(sem_dono) + ". Elas estão no perfil e "
            "não acendem nada hoje — é feature que falta, não erro seu.")


@gesto("06-navegacao.html", "padrao-definicoes")
def padrao_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Voltar ao padrão" das 21 linhas de *o que cada botão faz*.

    O QUE ELE FAZ: grava `key_bindings = None` no perfil ATIVO e manda o daemon
    reaplicá-lo. `None` não é "vazio" — o esquema o define como *"herda
    `DEFAULT_BUTTON_BINDINGS` do core"* (`profiles/schema.py:985`), e `{}` é
    outra coisa (teclado silencioso). Escrever `{}` aqui devolveria um controle
    MUDO com o botão dizendo "de fábrica".

    E ELE DEVOLVE AS VINTE E UMA, ao contrário do que parece. Contadas na tela e
    no fonte, em 01/09/2026:

        9 linhas   `key_bindings` as alcança — l1, r1, l3, r3, options, create
                   e as três regiões do touchpad (`core/keyboard_mappings.py:41`)
        12 linhas  mapas FIXOS do produto — `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e
                   `EDGE_KEY_MAP` (`integrations/uinput_mouse.py:93,99,105`),
                   mais o L2/R2 e a DIREÇÃO dos analógicos, que binding nenhum
                   alcança

    As 12 não têm onde ser mudadas — logo estão **sempre** de fábrica, e zerar as
    9 devolve a tabela inteira ao de fábrica. É por isso que este botão fecha
    inteiro, enquanto o "Guardar" ao lado dele não fecha: guardar 9 de 21
    escolhas e perder 12 caladas é o botão que responde calado.

    ELE ZERA OS DOIS CAMPOS desde 01/09/2026: o `key_bindings` (as nove teclas)
    e o `button_actions` (as vinte e uma linhas da tela, que nasceu no mesmo
    dia). Zerar só um deixaria a tabela metade de fábrica, com o botão dizendo
    o contrário.

    O ALVO É O PERFIL ATIVO, e ele é dito: os dois são campo de perfil
    (`profiles/schema.py`), não da máquina. Sem perfil ativo o botão RECUSA —
    devolver ao padrão "o perfil nenhum" não quer dizer nada.

    A GRAVAÇÃO É A DA CASA: `perfil.gravar_e_reaplicar`, a mesma que a aba
    Perfis usa. O `save_profile` grava em disco e o `profile.switch` reaplica se
    for o ativo.

    FATO SUBSTITUÍDO, e é o que destravou este botão: o `SEM_GESTO` abaixo dizia
    que "gravar perfil não tem método". Tem — `profiles/loader.save_profile`, e
    o `a10_perfis` já o usava desde a mesma leva que escreveu a frase.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    # OS DOIS CAMPOS, e não só um — 01/09/2026, quando o `button_actions`
    # nasceu. O perfil passou a guardar o que cada botão faz em DOIS lugares:
    # o `key_bindings` (as nove teclas, da FEAT-KEYBOARD-PERSISTENCE-01) e o
    # `button_actions` (as vinte e uma linhas da tela). Um "Voltar ao padrão"
    # que zerasse só o primeiro deixaria a tabela metade de fábrica e metade
    # não — e o botão diria "de fábrica" sobre isso.
    if prof.key_bindings is None and prof.button_actions is None:
        # JÁ ESTÁ DE FÁBRICA. Gravar de novo trocaria a data do arquivo e faria
        # o daemon reaplicar um perfil idêntico — barulho sem efeito, e um
        # `profile.switch` no meio de uma partida não é de graça.
        return
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"key_bindings": None, "button_actions": None}), ctx, p)


#: OS OITO QUE CONTINUAM SEM DONO, com o motivo MEDIDO de cada um — o
#: inventário honesto do que falta, no lugar de um botão que responde calado. O
#: piloto os recusa PELO NOME (`[gesto sem dono] 06-navegacao.html · <nome>`), e
#: por isso as chaves aqui são os nomes que ele vai imprimir, um por um: os dois
#: `bignum` sem dono viram quatro linhas (`-menos` e `-mais`), porque são quatro
#: botões.
#:
#: ERAM QUATORZE, depois TREZE. O `teclado` saiu na segunda leva — o que o
#: segurava não era falta de método, era o piloto não mandar o valor de um
#: `<select>`. O `padrao-definicoes` saiu na TERCEIRA, e o que o segurava era
#: um FATO ERRADO escrito aqui: que gravar perfil não tinha método. Tinha, e o
#: `a10_perfis` já o usava. As duas saídas têm a mesma forma — o que prendia o
#: botão não era o produto, era o que estava escrito sobre ele.
#:
#: -------------------------------------------------------------------------
#: `mouse.emulation.restore` NÃO virou botão, e a segunda leva reconfirmou a
#: recusa com uma razão MAIOR que a da primeira. Três coisas, e a terceira é a
#: que fecha a porta:
#:
#: 1. o handler diz o lugar dele com todas as letras — *"entra na transição de
#:    modo (`app/actions/mode_transition.py`), **nunca em um botão solto**"*
#:    (`daemon/ipc_handlers.py:5011`);
#: 2. ele devolve a preferência PERSISTIDA — não "o de fábrica" nem "o que a
#:    tela mostra" —, então pendurá-lo num "Voltar ao padrão" faria o botão
#:    prometer uma coisa e fazer outra;
#: 3. **ele LIGA o mouse.** `restore_mouse_preference`
#:    (`daemon/lifecycle.py:1402`) chama `set_mouse_emulation(pref, …)` e, com a
#:    preferência nunca gravada, `pref` vira `True` por default (`:1403`) — o
#:    cursor DELA passa a andar pelo controle, e o gamepad virtual cai junto
#:    (`:1359`). Isso o põe na mesma prateleira do gesto `modo`, que já está em
#:    `hefesto_vivo.PERIGOSOS` justamente para a prova botão a botão não o
#:    clicar. Ligá-lo aqui criaria um gesto perigoso NOVO **fora** daquela
#:    lista, e a lista mora num arquivo que esta aba não pode tocar.
SEM_GESTO = {
    "navegacao-interna": "navegar a janela do Hefesto com o controle não tem "
                         "método no daemon — nenhum dos 39, e o "
                         "`core/disputa_de_botao.py` que as sprints citam não "
                         "existe no disco",
    "modo-steam": "não há método de Modo Steam no daemon — nenhum dos 39",
    # OS QUATRO DE VELOCIDADE SAÍRAM DAQUI porque saíram da TELA — 01/09/2026,
    # decisão dela ao ler a medição: *"só ajustar o texto e deixar rolagem,
    # ajustar ali pra deixar um só se for o caso pra ambos"*.
    #
    # O que estava escrito aqui era: o cursor do touchpad sai do MESMO
    # `mouse_speed` (`uinput_mouse.py:446`), e rolagem por dois dedos não existe
    # (`_emit_scroll` lê só o analógico direito). As duas linhas do desenho
    # ofereciam DOIS números onde o produto tem UM — e a cura foi no desenho, não
    # num gesto que fingisse o segundo. As dicas passaram a ler a faixa do
    # produto, que também estava errada nas duas ("De 1 a 10", quando o cursor
    # vai a 12 e a rolagem a 5).
    # FATO SUBSTITUÍDO (segunda leva): dizia "os cinco combos moram em
    # `key_bindings` do perfil". Não moram — `key_bindings` são os nove BOTÕES
    # do `DEFAULT_BUTTON_BINDINGS`, e combo nenhum aparece lá.
    # FATO AFINADO (terceira leva, 01/09/2026): esta entrada dizia que "método
    # de IPC nenhum escreve" o `ps_button_action`. Escreve — `daemon.reload`
    # aceita `config_overrides` com qualquer campo do `DaemonConfig`
    # (`ipc_handlers.py:4556`). O que ele NÃO faz é gravar: o handler roda
    # `replace(config, **overrides)` e `reload_config(...)` e para aí (`:4567`),
    # então a escolha morre no próximo start do daemon. E o `ps_button_action` é
    # do PS SOLO, não dos combos — a tabela desta tela é dos cinco COMBOS.
    "acao-do-gesto": "os cinco combos são callbacks montados em código "
                     "(`daemon/subsystems/hotkey.py:86,414`), não dado. O "
                     "vizinho deles, o `config.ps_button_action` do PS solo, "
                     "tem escritor VIVO (`daemon.reload` com `config_overrides`) "
                     "e nenhum que grave em disco — e ele nem é o que esta "
                     "tabela oferece trocar",
    "padrao-da-aba": "a frase do botão promete a aba INTEIRA — as opções de "
                     "ativação, os 5 gestos e as 21 linhas das duas telas. Só as "
                     "duas velocidades têm rota (`mouse.emulation.set` "
                     "speed-only); as outras três promessas não têm nenhuma, e "
                     "um 'Voltar ao padrão' que devolve dois números de cinco "
                     "coisas é um botão que responde calado sobre as outras três",
    # `guardar-definicoes` SAIU DAQUI em 01/09/2026, e não porque a medição
    # estivesse errada: ela estava certa. A tela deixava escolher 21 linhas e o
    # perfil alcançava 9, e guardar 9 de 21 caladas seria o botão que responde
    # calado. O que mudou foi o PRODUTO — decisão dela ao ler a medição:
    # *"ganha campo. essa é a parte das features que precisam ou serem ajustadas
    # ou desenvolvidas."* `Profile.button_actions` nasceu, o
    # `core/acoes_de_botao` virou o dono do vocabulário e do padrão, e o device
    # de mouse passou a obedecer.
    #
    # O QUE AINDA NÃO PousA está DITO, não engolido: os três comandos
    # ("Abrir a Steam", "Sair do modo jogo", "Escolher um programa…"), os dois
    # papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho do
    # cross e do triangle. O gesto grava o resto e LEVANTA nomeando esses.
    "guardar-remapeamento": "o remapeamento botão-por-botão não tem sequer campo "
                            "no perfil, quanto mais método de IPC",
    "padrao-remapeamento": "idem, ao contrário",
    "guardar-ponto": "'Estilo de Jogo' não existe em campo, widget ou preset "
                     "nenhum do produto — está escrito em "
                     "`app/actions/perfis_web.py`, que já mediu isto para a aba "
                     "Perfis. O `point_and_click` que existe é um PERFIL em "
                     "disco, não um estilo, e gravar perfil não tem método",
}


PONTE = {"chamar"}
METODOS = {"mouse.emulation.set", "keyboard.emulation.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 8


def _prova(nome: str, clique: dict[str, Any], chama: list[Any]) -> dict[str, Any]:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez.

    Cinco dicionários escritos por extenso repetiam a chave da página cinco
    vezes — e cada repetição custava um marcador `# (noqa-acento)` (a chave é do
    contrato da régua, não texto em português) e um aviso do ruff sobre ele. Um
    construtor paga o preço uma vez só.
    """
    # A primeira chave é o NOME do contrato da régua, não texto em português —
    # por isso a linha leva o marcador de isenção, e uma vez só. (Escrever a
    # palavra AQUI, no comentário, também acusava: a régua de acentuação não
    # distingue prosa de identificador nem quando o identificador é o assunto.)
    return {"pagina": PAGINA, "gesto": nome,  # (noqa-acento) chave do contrato
            "clique": clique, "chama": chama}


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
    # AS DUAS PONTAS DA LISTA DO TECLADO, e as duas provam a mesma coisa por
    # lados opostos: que o `valor` do `<select>` decide o bool. O `clique` traz
    # `valor` porque é ele que o piloto manda desde 01/09 — `texto`, num
    # `<select>`, é a lista inteira concatenada, e foi essa confusão que deixou
    # esta lista sem dono na primeira leva.
    #
    # A OPÇÃO DO MEIO NÃO TEM PROVA AQUI de propósito: `PROVAS` só sabe cobrar
    # chamada, e o certo para "Só fora do jogo" é NÃO chamar nada. Ela é provada
    # pela mordida, no relato.
    _prova("teclado", {"valor": TECLADO_LIGADA},
           [("chamar", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("teclado", {"valor": TECLADO_DESLIGADA},
           [("chamar", ["keyboard.emulation.set"], {"enabled": False})]),
]
