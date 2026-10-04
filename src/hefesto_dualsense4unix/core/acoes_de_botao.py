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
   (`keyboard_mappings.py:50-52`). Três linhas de vinte e uma, erradas desde que
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
EIXO_ESQUERDO = "l3_direcao"
EIXO_DIREITO = "r3_direcao"

BOTAO_PS = "ps"

BOTOES: tuple[str, ...] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", EIXO_ESQUERDO, "r3", EIXO_DIREITO,
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create", BOTAO_PS,
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
)

TOKEN_CURSOR = "__CURSOR__"
TOKEN_ROLAGEM = "__ROLAGEM__"
TOKEN_STEAM = "__STEAM__"
TOKEN_SAIR_DO_JOGO = "__SAIR_DO_JOGO__"
TOKEN_PROGRAMA = "__PROGRAMA__"
TOKEN_NADA = "__NADA__"
TOKEN_SEM_TECLA = "__SEM_TECLA__"

GRUPO_MOUSE = "Mouse"
GRUPO_TECLADO = "Função do teclado"
GRUPO_COMANDO = "Executar Comando"
GRUPO_NENHUM = ""

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

    TOKEN_TOGGLE_OSK: (GRUPO_COMANDO, "Abrir e fechar o teclado na tela"),
    TOKEN_OPEN_OSK: (GRUPO_COMANDO, "Abrir o teclado na tela"),
    TOKEN_CLOSE_OSK: (GRUPO_COMANDO, "Fechar o teclado na tela"),
    TOKEN_STEAM: (GRUPO_COMANDO, "Abrir a Steam"),
    TOKEN_SAIR_DO_JOGO: (GRUPO_COMANDO, "Sair do modo jogo"),
    TOKEN_PROGRAMA: (GRUPO_COMANDO, "Escolher um programa…"),

    TOKEN_NADA: (GRUPO_NENHUM, "— Nada —"),
    TOKEN_SEM_TECLA: (GRUPO_NENHUM, "— Sem tecla —"),
}


def o_ps_aceita(token: str) -> bool:
    """O token cabe na linha do PS? Tecla (combos com ``+``), o teclado na tela, ou nada."""
    if token == TOKEN_SEM_TECLA:
        return True
    teclado_na_tela = {TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK, TOKEN_CLOSE_OSK}
    return all(p.startswith("KEY_") or p in teclado_na_tela for p in token.split("+"))

#: de propósito — tirá-los da tela seria apagar uma promessa que ela aprovou —,
SEM_ATENDENTE: frozenset[str] = frozenset(
    {TOKEN_STEAM, TOKEN_SAIR_DO_JOGO, TOKEN_PROGRAMA})


ORDEM_DOS_GRUPOS: tuple[str, ...] = (
    GRUPO_MOUSE, GRUPO_TECLADO, GRUPO_COMANDO, GRUPO_NENHUM)


def por_grupo(botao: str | None = None) -> list[tuple[str, list[str]]]:
    """`[(grupo, [rótulo, …]), …]` — exatamente o que a tela desenha.

    A TELA NÃO GUARDA MAIS A LISTA. Ela era escrita no gerador da aba Navegação,
    ao lado desta, e as duas já divergiam em três linhas quando este módulo
    nasceu. Aqui há uma, e o gerador a lê.

    Com ``botao=BOTAO_PS``, a lista da linha do PS: só o que ele digita
    (:func:`o_ps_aceita`). As outras linhas não oferecem o «— Sem tecla —».
    """
    def cabe(token: str) -> bool:
        if botao == BOTAO_PS:
            return o_ps_aceita(token)
        return token != TOKEN_SEM_TECLA

    fora: list[tuple[str, list[str]]] = []
    for grupo in ORDEM_DOS_GRUPOS:
        rotulos = [r for t, (g, r) in ACOES.items() if g == grupo and cabe(t)]
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


def acao_do_ps(escolhas: dict[str, str] | None) -> str | None:
    """O token que o PERFIL deu ao botão PS — `None` quando ele não disse nada."""
    if not escolhas:
        return None
    token = escolhas.get(BOTAO_PS)
    return str(token) if token else None


def padrao() -> dict[str, str]:
    """O que cada um dos 22 botões faz DE FÁBRICA, lido dos mapas do produto.

    O PS é o único cujo de fábrica NÃO sai dos quatro mapas: a linha dele só
    digita, e o de fábrica dela é :data:`TOKEN_SEM_TECLA`. O que o toque nele
    faz no computador é o ⑥ da tabela dos gestos, e não esta tabela.

    A ORDEM DE PRECEDÊNCIA É A DO PRODUTO, e não uma escolha deste módulo: o
    `UinputMouseDevice` só age quando a emulação de mouse está ligada, e é ele
    quem consulta `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e `EDGE_KEY_MAP`. O teclado
    virtual age em paralelo, com `DEFAULT_BUTTON_BINDINGS`. Quando os dois têm
    opinião sobre o mesmo botão, quem a TELA mostra é o do mouse — porque é o
    que a pessoa vê acontecer com o cursor na frente dela.

    O CASO QUE TORNA ISSO VISÍVEL É O `r3`: o mouse o quer como Botão do meio e
    o teclado como "Fechar o teclado na tela", e o produto faz **os dois**. O
    comentário de `keyboard_mappings.py:37-42` já registrava a colisão e dizia
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
    fora["l2"] = fora["cross"]
    fora["r2"] = fora["triangle"]
    fora[EIXO_ESQUERDO] = TOKEN_CURSOR
    fora[EIXO_DIREITO] = TOKEN_ROLAGEM
    # nem `DPAD_TO_KEY`, nem `EDGE_KEY_MAP`, nem `DEFAULT_BUTTON_BINDINGS`. A
    fora[BOTAO_PS] = TOKEN_SEM_TECLA
    return fora


def _dominio_do_teclado() -> frozenset[str]:
    """Os botões cujo DE FÁBRICA sai de `DEFAULT_BUTTON_BINDINGS`.

    É o domínio de `Profile.key_bindings` — o conjunto de botões sobre os quais
    o teclado virtual é quem manda, e portanto os únicos que a camada de
    atalhos pode trocar sem contradizer a precedência escrita na função que
    monta o de fábrica.  # (noqa-acento) nome de função

    ELE É DERIVADO, e a derivação é o ponto: perguntar ao de fábrica em vez de
    digitar a lista é o que faz o `r3` ficar de FORA sozinho. O `r3` está nos
    dois lados (`BUTTON_TO_UINPUT` diz `BTN_MIDDLE`, `DEFAULT_BUTTON_BINDINGS`
    diz "fechar o teclado na tela") e o produto faz **os dois** — é a colisão
    que `keyboard_mappings.py:46-52` registra. Digitar a lista aqui faria a
    camada de atalhos apagar o Botão do meio dele, que é regressão em botão que
    ela usa.
    """
    base = padrao()
    return frozenset(
        botao for botao in BOTOES
        if (do_teclado := _do_teclado(botao)) is not None
        and base.get(botao) == do_teclado)


DOMINIO_DO_TECLADO: frozenset[str] = _dominio_do_teclado()


def tabela_efetiva(
    escolhas: dict[str, str] | None,
    key_bindings: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Botão -> token que VALE, com as três camadas na ordem do produto.

    São três, e a ordem é a da precedência:

        1. o de fábrica        derivado dos quatro mapas do produto
        2. `key_bindings`      o que ela escreveu na janela ANTIGA
        3. `button_actions`    o que ela escolheu na tela NOVA

    A CAMADA DO MEIO NASCEU EM 06/09/2026 (ONDA3-MOTOR-01) e ela cura uma perda
    silenciosa de escolha dela: `apply_button_actions` roda DEPOIS do
    `apply_keyboard` e reescreve o conjunto INTEIRO do teclado virtual com o que
    sai daqui. Sem esta camada, um perfil com `button_actions` preenchido
    apagava, a cada ativação, todo atalho que ela tivesse escrito à mão — sem
    uma palavra, e com os dois campos continuando a aparecer no arquivo.

    O `None` É "NÃO OPINOU" E O `{}` É "ESVAZIEI", e a diferença é a mesma do
    esquema (`profiles/schema.py:1212-1214`) e a mesma que
    `profiles/manager.resolve_key_bindings` aplica ao device: `None` herda
    `DEFAULT_BUTTON_BINDINGS` inteiro — que é exatamente o que o de fábrica já
    deriva, logo não há nada a fazer —, e um dict, mesmo vazio, é a lista
    COMPLETA dela: botão do domínio que não está lá foi REMOVIDO, e vira
    `— Nada —`.

    ELA NÃO MESCLA COM O DE FÁBRICA, e isso é medido, não escolhido:
    `resolve_key_bindings` (`profiles/manager.py:1984`) devolve só as chaves do
    dict, e é ele quem alimenta o device no `apply_keyboard`. Mesclar aqui faria
    esta tabela discordar do device que ela mesma vai reescrever um método
    depois — que é o defeito que esta camada existe para fechar.
    """
    tabela = padrao()
    if key_bindings is not None:
        for botao in DOMINIO_DO_TECLADO:
            ligacao = key_bindings.get(botao)
            tabela[botao] = "+".join(ligacao) if ligacao else TOKEN_NADA
    if escolhas:
        tabela.update({b: a for b, a in escolhas.items() if b in tabela})
    return tabela


def botoes_calados(
    escolhas: dict[str, str] | None,
    key_bindings: dict[str, list[str]] | None = None,
) -> frozenset[str]:
    """Os botões que ela mandou CALAR — a quinta porta, e ela existe por medida.

    `do_mouse` NÃO DISTINGUE "não é do mouse" de "foi calado", e é dessa
    indistinção que saía o defeito medido pela frente da aba 06 em 04/09/2026:
    `UinputMouseDevice.set_button_actions` reconstruía `_mapa_dpad` e
    `_mapa_tap` do DE FÁBRICA menos `do_mouse`, e um botão em `— Nada —` nunca
    entra em `do_mouse` — o `resolver()` o pula de propósito. Logo ele não era
    subtraído, e continuava emitindo o que emitia.

    Escapavam SEIS dos vinte e dois: as quatro direções do d-pad
    (`DPAD_TO_KEY`), o Círculo e o Quadrado (`EDGE_KEY_MAP`). Os outros calavam
    porque os dois mapas que os atendem — `_mapa_botoes` e o `set_bindings` do
    teclado virtual — são SUBSTITUÍDOS inteiros, e o que não está na sacola
    simplesmente não está no device.

    PORTA PRÓPRIA, e não uma quarta posição na tupla do :func:`resolver`, pela
    mesma razão medida da :func:`acao_do_ps`: três chamadores desempacotam três
    sacolas, e devolver quatro viraria `ValueError: too many values to unpack`
    na aba que ela abre hoje.

    `__NADA__` E SÓ ELE. Um botão do d-pad posto em "Abrir a Steam" cai em
    `SEM_ATENDENTE`, vai para a terceira sacola do `resolver()` e **continua
    emitindo o de fábrica** — é o gêmeo deste defeito, com a mesma linha de
    código como causa, e está RELATADO em
    `ONDA3-MOTOR-01`. Curá-lo aqui de
    carona seria a segunda cura escondida dentro da primeira.
    """
    tabela = tabela_efetiva(escolhas, key_bindings)
    return frozenset(b for b, token in tabela.items() if token == TOKEN_NADA)


def resolver(
    escolhas: dict[str, str] | None,
    key_bindings: dict[str, list[str]] | None = None,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], list[str]]:
    """As escolhas do perfil, separadas por QUEM as atende.

    Devolve três sacolas, e a terceira é a que impede o silêncio:

        do_mouse    botão -> `BTN_*`, para o `UinputMouseDevice`
        do_teclado  botão -> tupla de `KEY_*`/`__OSK__`, para o teclado virtual
        sem_dono    os botões cuja escolha ninguém atende HOJE

    O PS NÃO ESTÁ EM NENHUMA DAS TRÊS, e tem porta própria: :func:`acao_do_ps`.
    O atendente dele não é device — é o callback do `ps_solo`. E os botões
    CALADOS também não estão em nenhuma: quem os nomeia é :func:`botoes_calados`,
    porque o device de mouse precisa saber quais foram calados de propósito para
    tirá-los dos mapas do d-pad e do tap.

    `escolhas=None` devolve o de fábrica — é o mesmo contrato de
    `Profile.key_bindings`, e vale a mesma frase do esquema: `None` HERDA, `{}`
    seria "nada em botão nenhum", que é outra coisa.

    `key_bindings` É A CAMADA DO MEIO — 06/09/2026, ONDA3-MOTOR-01. Ela existe
    porque o `apply_button_actions` reescreve o conjunto INTEIRO do teclado
    virtual com o que sai daqui, DEPOIS de o `apply_keyboard` ter escrito o que
    ela digitou na janela antiga: sem herdar, todo atalho dela morria na
    ativação seguinte de qualquer perfil que tivesse `button_actions`. As regras
    e a razão de o `r3` ficar fora estão em :func:`tabela_efetiva` e em
    :data:`DOMINIO_DO_TECLADO`. Omitir o parâmetro é o contrato de antes, byte
    a byte — os três chamadores que não o passam não mudam de resposta.

    OS EIXOS FICAM DE FORA das duas primeiras sacolas: mover o cursor e rolar
    não são evento de botão, e empurrá-los para o device como se fossem faria o
    `_emit_buttons` procurar um `BTN___CURSOR__` que não existe.

    E OS DOIS GATILHOS TAMBÉM, pelo motivo escrito no corpo: eles são espelho do
    `cross` e do `triangle`, não linha própria. É a única das vinte e duas linhas
    que a tela oferece e o produto só pode atender POR TABELA — e dizer isso na
    terceira sacola é melhor que guardar a escolha e não acender nada.
    """
    tabela = tabela_efetiva(escolhas, key_bindings)

    do_mouse: dict[str, str] = {}
    do_teclado: dict[str, tuple[str, ...]] = {}
    sem_dono: list[str] = []

    for gatilho, espelho in (("l2", "cross"), ("r2", "triangle")):
        if tabela.get(gatilho) != tabela.get(espelho):
            sem_dono.append(gatilho)
        tabela.pop(gatilho, None)

    # `button_actions_sem_atendente`.
    tabela.pop(BOTAO_PS, None)

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
            sem_dono.append(botao)
        else:
            do_teclado[botao] = tuple(token.split("+"))
    return do_mouse, do_teclado, sorted(sem_dono)


def rotulo(token: str) -> str:
    """O texto que a tela mostra para aquele token, ou o token cru se ele sumir."""
    par = ACOES.get(token)
    return par[1] if par else token


_tabela_efetiva = tabela_efetiva

__all__ = [
    "ACOES",
    "BOTAO_PS",
    "BOTOES",
    "DOMINIO_DO_TECLADO",
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
    "TOKEN_SEM_TECLA",
    "TOKEN_STEAM",
    "acao_do_ps",  # (noqa-acento) nome de função
    "botoes_calados",  # (noqa-acento) nome de função
    "o_ps_aceita",
    "padrao",  # (noqa-acento) nome de função
    "por_grupo",
    "resolver",
    "rotulo",
    "tabela_efetiva",
    "token_do_rotulo",
]
