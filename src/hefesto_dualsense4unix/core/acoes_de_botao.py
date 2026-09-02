#!/usr/bin/env python3
"""O QUE CADA BOTÃO DO CONTROLE FAZ — a lista única, e o padrão DERIVADO.

DECISÃO DELA, 01/09/2026, ao ler a medição de que 12 das 21 linhas da tela
aceitavam escolha e não tinham onde ser guardadas: *"ganha campo. essa é a parte
das features que precisam ou serem ajustadas ou desenvolvidas."*

O PROBLEMA QUE ELE RESOLVE, e ele tinha TRÊS lados:

1. **A tela deixava escolher o que o produto não guardava.** `Profile.key_bindings`
   alcança NOVE botões (`core/keyboard_mappings.DEFAULT_BUTTON_BINDINGS`); os
   outros doze são mapas FIXOS de `integrations/uinput_mouse.py`. Escolher numa
   das doze linhas não ia a lugar nenhum.
2. **O padrão de cada linha era DIGITADO na tela.** O gerador da aba Navegação
   escrevia "Botão esquerdo", "Enter", "F11"… à mão, ao lado dos mapas do
   produto que dizem a mesma coisa. Terceira cópia de um fato.
3. **E as cópias já divergiam.** Medido no dia em que este módulo nasceu: a tela
   dizia que as três regiões do touchpad fazem *Botão esquerdo · Botão direito ·
   F11*, e o produto faz *Backspace · Enter · Delete*
   (`keyboard_mappings.py:60-62`). Três linhas de vinte e uma, erradas desde que
   foram escritas, porque nada as comparava.

O CONTRATO, e ele é de uma linha: **um botão faz UMA ação**, e a ação é um
TOKEN. O `PADRAO` diz o que cada botão faz de fábrica, e o perfil pode trocar
qualquer um (`Profile.button_actions`).

O PADRÃO É DERIVADO, NUNCA DIGITADO. A função que o monta  # (noqa-acento) id
lê os quatro mapas do produto. No dia em que um deles mudar, esta tabela muda
junto — e é justamente o que não acontecia com a cópia na tela.

O QUE ESTE MÓDULO **NÃO** FAZ: ele não emite evento nenhum. Quem emite continua
sendo o `UinputMouseDevice` (mouse e d-pad) e o `UinputKeyboardDevice` (teclas e
tokens virtuais). Aqui mora só o vocabulário e a resolução — e é isso que o
mantém importável sem `uinput`, sem daemon e sem tela.
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    TOKEN_CLOSE_OSK,
    TOKEN_OPEN_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
)

#: OS DOIS EIXOS DOS ANALÓGICOS, que são LINHA na tela e não são botão em lugar
#: nenhum do produto. Eles existem aqui porque a tela oferece trocar o que cada
#: um faz — e porque, sem eles, "L3 · direção" seria a única linha da tabela sem
#: endereço, o que já bastou para uma tela inteira ficar sem dono nesta casa.
EIXO_ESQUERDO = "l3_direcao"
EIXO_DIREITO = "r3_direcao"

#: AS VINTE E UMA LINHAS, na ordem em que a tela as mostra. A ordem é dela
#: (27/08/2026, *"cada linha seria um dos botões do controle"*), e é a mesma nas
#: duas telas de botões da aba Navegação.
BOTOES: tuple[str, ...] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", EIXO_ESQUERDO, "r3", EIXO_DIREITO,
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create",
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
)

#: OS TOKENS QUE NÃO SÃO TECLA NEM BOTÃO DE MOUSE — papéis e comandos. Todos na
#: forma `__NOME__`, a mesma que `keyboard_mappings.is_virtual_token` reconhece,
#: para que nenhum deles possa ser confundido com um `KEY_*` de verdade.
TOKEN_CURSOR = "__CURSOR__"
TOKEN_ROLAGEM = "__ROLAGEM__"
TOKEN_STEAM = "__STEAM__"
TOKEN_SAIR_DO_JOGO = "__SAIR_DO_JOGO__"
TOKEN_PROGRAMA = "__PROGRAMA__"
TOKEN_NADA = "__NADA__"

#: OS GRUPOS SÃO AS PALAVRAS DELA, da fala de 27/08/2026: *"no lado direito
#: teríamos Função do teclado, Executar Comando, Mouse"*. A tela os usa como
#: `<optgroup>`, e a ordem daqui é a ordem de lá.
GRUPO_MOUSE = "Mouse"
GRUPO_TECLADO = "Função do teclado"
GRUPO_COMANDO = "Executar Comando"
GRUPO_NENHUM = ""

#: TOKEN -> (grupo, rótulo). É a lista que a tela oferece em CADA linha, e o
#: rótulo é o texto que ela lê — não há segunda lista do outro lado.
#:
#: `Backspace` e `Delete` entraram em 01/09/2026 por MEDIÇÃO, não por gosto: o
#: produto já os emite nas regiões esquerda e direita do touchpad
#: (`keyboard_mappings.py:60,62`) e a lista da tela não os tinha — logo a tela
#: não conseguia dizer a verdade sobre três das suas vinte e uma linhas.
ACOES: dict[str, tuple[str, str]] = {
    "BTN_LEFT": (GRUPO_MOUSE, "Botão esquerdo"),
    "BTN_RIGHT": (GRUPO_MOUSE, "Botão direito"),
    "BTN_MIDDLE": (GRUPO_MOUSE, "Botão do meio"),
    TOKEN_CURSOR: (GRUPO_MOUSE, "Movimento do cursor"),
    TOKEN_ROLAGEM: (GRUPO_MOUSE, "Rolagem vertical e horizontal"),

    "KEY_UP": (GRUPO_TECLADO, "Seta para cima"),
    "KEY_DOWN": (GRUPO_TECLADO, "Seta para baixo"),
    "KEY_LEFT": (GRUPO_TECLADO, "Seta para a esquerda"),
    "KEY_RIGHT": (GRUPO_TECLADO, "Seta para a direita"),
    "KEY_ENTER": (GRUPO_TECLADO, "Enter"),
    "KEY_ESC": (GRUPO_TECLADO, "Esc"),
    "KEY_SPACE": (GRUPO_TECLADO, "Espaço"),
    "KEY_BACKSPACE": (GRUPO_TECLADO, "Backspace"),
    "KEY_DELETE": (GRUPO_TECLADO, "Delete"),
    "KEY_LEFTALT+KEY_TAB": (GRUPO_TECLADO, "Alt + Tab"),
    "KEY_LEFTALT+KEY_LEFTSHIFT+KEY_TAB": (GRUPO_TECLADO, "Alt + Shift + Tab"),
    "KEY_LEFTMETA": (GRUPO_TECLADO, "Super (tecla Windows)"),
    "KEY_SYSRQ": (GRUPO_TECLADO, "PrintScreen"),
    "KEY_F11": (GRUPO_TECLADO, "F11"),

    # O ALTERNADOR VEM PRIMEIRO porque é o de fábrica do L3 desde 02/09/2026.
    # O rótulo ESPERA A PALAVRA DELA: ela decidiu o comportamento
    # (*"abrir o teclado virtual e fechar o teclado virtual caso apertado
    # novamente"*), não o texto. Este é a leitura direta da frase dela e segue
    # a forma dos dois vizinhos.
    TOKEN_TOGGLE_OSK: (GRUPO_COMANDO, "Abrir e fechar o teclado na tela"),
    TOKEN_OPEN_OSK: (GRUPO_COMANDO, "Abrir o teclado na tela"),
    TOKEN_CLOSE_OSK: (GRUPO_COMANDO, "Fechar o teclado na tela"),
    TOKEN_STEAM: (GRUPO_COMANDO, "Abrir a Steam"),
    TOKEN_SAIR_DO_JOGO: (GRUPO_COMANDO, "Sair do modo jogo"),
    TOKEN_PROGRAMA: (GRUPO_COMANDO, "Escolher um programa…"),

    TOKEN_NADA: (GRUPO_NENHUM, "— Nada —"),
}

#: OS TRÊS QUE A TELA OFERECE E O PRODUTO AINDA NÃO ATENDE. Eles ficam na lista
#: de propósito — tirá-los da tela seria apagar uma promessa que ela aprovou —,
#: mas quem os grava tem de saber que hoje eles não acendem nada. O
#: `resolver()` os devolve na terceira sacola, que é como quem chama fica
#: sabendo em vez de descobrir pelo silêncio.
#:
#: `__PROGRAMA__` é o mais fundo dos três: ele precisa de um CAMINHO junto, e
#: campo para esse caminho não existe em perfil nenhum.
SEM_ATENDENTE: frozenset[str] = frozenset(
    {TOKEN_STEAM, TOKEN_SAIR_DO_JOGO, TOKEN_PROGRAMA})


#: A ORDEM DOS GRUPOS NA TELA, que é a ordem da fala dela. O `<optgroup>` sai
#: daqui, e não de uma segunda lista no gerador.
ORDEM_DOS_GRUPOS: tuple[str, ...] = (
    GRUPO_MOUSE, GRUPO_TECLADO, GRUPO_COMANDO, GRUPO_NENHUM)


def por_grupo() -> list[tuple[str, list[str]]]:
    """`[(grupo, [rótulo, …]), …]` — exatamente o que a tela desenha.

    A TELA NÃO GUARDA MAIS A LISTA. Ela era escrita no gerador da aba Navegação,
    ao lado desta, e as duas já divergiam em três linhas quando este módulo
    nasceu. Aqui há uma, e o gerador a lê.
    """
    fora: list[tuple[str, list[str]]] = []
    for grupo in ORDEM_DOS_GRUPOS:
        rotulos = [r for _t, (g, r) in ACOES.items() if g == grupo]
        if rotulos:
            fora.append((grupo, rotulos))
    return fora


def token_do_rotulo(texto: str) -> str | None:
    """O caminho de VOLTA: o que a tela mandou vira o token do produto.

    Ele é o que faz o "Guardar" das telas de botões funcionar — o `<select>`
    devolve o TEXTO da opção, porque as opções não têm `value` (`value` não está
    entre os atributos que o portão do desenho ignora, então pô-lo faria toda
    marcação virar divergência de desenho).

    `None` quando o texto não é de nenhuma ação: melhor recusar dizendo qual
    linha não casou do que gravar um botão a menos, calado.
    """
    return _POR_ROTULO.get(texto.strip())


#: O REVERSO, montado UMA vez. O `assert` não é zelo: dois tokens com o mesmo
#: rótulo fariam o caminho de volta escolher um deles ao acaso, e o botão
#: gravaria outra coisa que não a que ela leu na tela.
_POR_ROTULO: dict[str, str] = {rotulo: token for token, (_g, rotulo) in ACOES.items()}
if len(_POR_ROTULO) != len(ACOES):  # pragma: no cover — defeito de escrita
    _repetidos = sorted({r for r in (v[1] for v in ACOES.values())
                         if list(v[1] for v in ACOES.values()).count(r) > 1})
    raise SystemExit(
        f"ERRO em acoes_de_botao: dois tokens têm o mesmo rótulo ({_repetidos}). "
        f"A tela devolve o TEXTO da opção, então rótulo repetido faz o caminho "
        f"de volta escolher ao acaso.")


def _do_teclado(botao: str) -> str | None:
    """O token que `DEFAULT_BUTTON_BINDINGS` dá àquele botão, já colado.

    O produto guarda combos como TUPLA (`("KEY_LEFTALT", "KEY_TAB")`); aqui eles
    viram a forma com `+`, que é a que `keyboard_mappings.parse_binding` lê de
    volta. Um round-trip, e não uma segunda grafia.
    """
    ligacao = DEFAULT_BUTTON_BINDINGS.get(botao)
    if not ligacao:
        return None
    return "+".join(ligacao)


def padrao() -> dict[str, str]:
    """O que cada um dos 21 botões faz DE FÁBRICA, lido dos mapas do produto.

    A ORDEM DE PRECEDÊNCIA É A DO PRODUTO, e não uma escolha deste módulo: o
    `UinputMouseDevice` só age quando a emulação de mouse está ligada, e é ele
    quem consulta `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e `EDGE_KEY_MAP`. O teclado
    virtual age em paralelo, com `DEFAULT_BUTTON_BINDINGS`. Quando os dois têm
    opinião sobre o mesmo botão, quem a TELA mostra é o do mouse — porque é o
    que a pessoa vê acontecer com o cursor na frente dela.

    O CASO QUE TORNA ISSO VISÍVEL É O `r3`: o mouse o quer como Botão do meio e
    o teclado como "Fechar o teclado na tela", e o produto faz **os dois**. O
    comentário de `keyboard_mappings.py:47-52` já registrava a colisão e dizia
    que ela é resolvida "por quem habilita mouse+teclado juntos". A tela mostra
    o do mouse; a colisão continua no produto, e continua escrita lá.
    """
    fora: dict[str, str] = {}
    for botao in BOTOES:
        if botao in BUTTON_TO_UINPUT:
            fora[botao] = BUTTON_TO_UINPUT[botao]
        elif botao in DPAD_TO_KEY:
            fora[botao] = DPAD_TO_KEY[botao]
        elif botao in EDGE_KEY_MAP:
            fora[botao] = EDGE_KEY_MAP[botao]
        else:
            do_teclado = _do_teclado(botao)
            fora[botao] = do_teclado if do_teclado else TOKEN_NADA
    # OS DOIS GATILHOS NÃO TÊM MAPA PRÓPRIO — o produto os INJETA como `cross` e
    # `triangle` acima do limiar (`uinput_mouse._resolve_emulated_set`), então o
    # que eles fazem é o que aqueles fazem. Derivar daqui, e não digitar, é o que
    # faz esta tabela acompanhar uma troca lá.
    fora["l2"] = fora["cross"]
    fora["r2"] = fora["triangle"]
    # OS DOIS EIXOS são papel, não tecla: o esquerdo move o cursor e o direito
    # rola. Está em `dispatch()` — `_emit_move(lx, ly)` e `_emit_scroll(rx, ry)`.
    fora[EIXO_ESQUERDO] = TOKEN_CURSOR
    fora[EIXO_DIREITO] = TOKEN_ROLAGEM
    return fora


def resolver(
    escolhas: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], list[str]]:
    """As escolhas do perfil, separadas por QUEM as atende.

    Devolve três sacolas, e a terceira é a que impede o silêncio:

        do_mouse    botão -> `BTN_*`, para o `UinputMouseDevice`
        do_teclado  botão -> tupla de `KEY_*`/`__OSK__`, para o teclado virtual
        sem_dono    os botões cuja escolha ninguém atende HOJE

    `escolhas=None` devolve o de fábrica — é o mesmo contrato de
    `Profile.key_bindings`, e vale a mesma frase do esquema: `None` HERDA, `{}`
    seria "nada em botão nenhum", que é outra coisa.

    OS EIXOS FICAM DE FORA das duas primeiras sacolas: mover o cursor e rolar
    não são evento de botão, e empurrá-los para o device como se fossem faria o
    `_emit_buttons` procurar um `BTN___CURSOR__` que não existe.

    E OS DOIS GATILHOS TAMBÉM, pelo motivo escrito no corpo: eles são espelho do
    `cross` e do `triangle`, não linha própria. É a única das vinte e uma linhas
    que a tela oferece e o produto só pode atender POR TABELA — e dizer isso na
    terceira sacola é melhor que guardar a escolha e não acender nada.
    """
    tabela = padrao()
    if escolhas:
        tabela.update({b: a for b, a in escolhas.items() if b in tabela})

    do_mouse: dict[str, str] = {}
    do_teclado: dict[str, tuple[str, ...]] = {}
    sem_dono: list[str] = []

    # OS DOIS GATILHOS SÃO ESPELHO, e não linha própria — descoberto pela régua
    # em 01/09/2026, no dia em que este módulo nasceu. `_resolve_emulated_set`
    # (`uinput_mouse.py:355`) troca L2 por `cross` e R2 por `triangle` ANTES de
    # qualquer mapa ser consultado: quando o dedo aperta o L2, o que chega ao
    # `_emit_buttons` já se chama `cross`.
    #
    # LOGO: uma escolha para o L2 que seja IGUAL à do cross não precisa de nada
    # — ela já acontece. Uma DIFERENTE não tem como acontecer, e vai para a
    # terceira sacola. Pô-la no mapa faria uma entrada que nunca casa, e a tela
    # mostraria a escolha guardada de um botão que continua fazendo outra coisa.
    for gatilho, espelho in (("l2", "cross"), ("r2", "triangle")):
        if tabela.get(gatilho) != tabela.get(espelho):
            sem_dono.append(gatilho)
        tabela.pop(gatilho, None)

    for botao, token in tabela.items():
        if botao in (EIXO_ESQUERDO, EIXO_DIREITO):
            continue
        if token == TOKEN_NADA:
            continue
        if token in SEM_ATENDENTE:
            sem_dono.append(botao)
        elif token.startswith("BTN_"):
            do_mouse[botao] = token
        elif token in (TOKEN_CURSOR, TOKEN_ROLAGEM):
            # PAPEL PEDIDO A UM BOTÃO. A tela deixa escolher, e o produto não
            # tem como dar movimento de cursor a um botão que só sabe ir e
            # voltar. Vai para a terceira sacola pelo mesmo motivo dos comandos.
            sem_dono.append(botao)
        else:
            do_teclado[botao] = tuple(token.split("+"))
    return do_mouse, do_teclado, sorted(sem_dono)


def rotulo(token: str) -> str:
    """O texto que a tela mostra para aquele token, ou o token cru se ele sumir.

    O CRU É PROPOSITAL: um token que perdeu o rótulo é um defeito a ver, e um
    travessão no lugar dele o esconderia.
    """
    par = ACOES.get(token)
    return par[1] if par else token


__all__ = [
    "ACOES",
    "BOTOES",
    "EIXO_DIREITO",
    "EIXO_ESQUERDO",
    "GRUPO_COMANDO",
    "GRUPO_MOUSE",
    "GRUPO_NENHUM",
    "GRUPO_TECLADO",
    "ORDEM_DOS_GRUPOS",
    "SEM_ATENDENTE",
    "TOKEN_CURSOR",
    "TOKEN_NADA",
    "TOKEN_PROGRAMA",
    "TOKEN_ROLAGEM",
    "TOKEN_SAIR_DO_JOGO",
    "TOKEN_STEAM",
    "padrao",  # (noqa-acento) nome de função
    "por_grupo",
    "resolver",
    "rotulo",
    "token_do_rotulo",
]
