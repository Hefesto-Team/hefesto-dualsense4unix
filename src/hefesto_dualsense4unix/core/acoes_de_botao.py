#!/usr/bin/env python3
"""O QUE CADA BOTÃO DO CONTROLE FAZ — a lista única, e o padrão DERIVADO.

DECISÃO, 01/09/2026, ao ler a medição de que 12 das 21 linhas da tela
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

from collections.abc import Iterable, Mapping

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
    EIXO_DIREITO,
    EIXO_ESQUERDO,
    TOKEN_CURSOR,
    TOKEN_ROLAGEM,
)

BOTAO_PS = "ps"

BOTOES: tuple[str, ...] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", EIXO_ESQUERDO, "r3", EIXO_DIREITO,
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create", BOTAO_PS,
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
)

TOKEN_STEAM = "__STEAM__"
TOKEN_SAIR_DO_JOGO = "__SAIR_DO_JOGO__"
TOKEN_PROGRAMA = "__PROGRAMA__"
TOKEN_NADA = "__NADA__"
TOKEN_SEM_TECLA = "__SEM_TECLA__"
TOKEN_WASD = "__WASD__"
TOKEN_SETAS = "__SETAS__"
TECLAS_DO_ANALOGICO: dict[str, tuple[str, str, str, str]] = {
    TOKEN_WASD: ("KEY_A", "KEY_D", "KEY_W", "KEY_S"),
    TOKEN_SETAS: ("KEY_LEFT", "KEY_RIGHT", "KEY_UP", "KEY_DOWN"),
}

LINHAS_DA_ACAO_DE_EIXO: dict[str, frozenset[str]] = {
    TOKEN_CURSOR: frozenset({EIXO_ESQUERDO}),
    TOKEN_ROLAGEM: frozenset({EIXO_DIREITO}),
    TOKEN_WASD: frozenset({EIXO_ESQUERDO, EIXO_DIREITO}),
    TOKEN_SETAS: frozenset({EIXO_ESQUERDO, EIXO_DIREITO}),
}

LIMIAR_DO_ANALOGICO = 0.5
CENTRO_DO_ANALOGICO = 128
DIRECOES_DO_ANALOGICO = ("esquerda", "direita", "cima", "baixo")

GRUPO_MOUSE = "Mouse"
GRUPO_TECLADO = "Função do teclado"
GRUPO_COMANDO = "Executar Comando"
GRUPO_NENHUM = ""

ACOES: dict[str, tuple[str, str]] = {
    "BTN_LEFT": (GRUPO_MOUSE, "Botão esquerdo"),
    "BTN_RIGHT": (GRUPO_MOUSE, "Botão direito"),
    "BTN_MIDDLE": (GRUPO_MOUSE, "Botão do meio"),
    TOKEN_CURSOR: (GRUPO_MOUSE, "Movimento do cursor"),
    TOKEN_ROLAGEM: (GRUPO_MOUSE, "Rolagem"),

    "KEY_E": (GRUPO_TECLADO, "E"),
    "KEY_UP": (GRUPO_TECLADO, "Seta para cima"),
    "KEY_DOWN": (GRUPO_TECLADO, "Seta para baixo"),
    "KEY_LEFT": (GRUPO_TECLADO, "Seta para a esquerda"),
    "KEY_RIGHT": (GRUPO_TECLADO, "Seta para a direita"),
    "KEY_ENTER": (GRUPO_TECLADO, "Enter"),
    "KEY_ESC": (GRUPO_TECLADO, "Esc"),
    "KEY_SPACE": (GRUPO_TECLADO, "Espaço"),
    "KEY_PAGEUP": (GRUPO_TECLADO, "Page Up"),
    "KEY_PAGEDOWN": (GRUPO_TECLADO, "Page Down"),
    "KEY_LEFTCTRL": (GRUPO_TECLADO, "Ctrl"),
    "KEY_TAB": (GRUPO_TECLADO, "Tab"),
    "KEY_H": (GRUPO_TECLADO, "H"),
    "KEY_BACKSPACE": (GRUPO_TECLADO, "Backspace"),
    "KEY_DELETE": (GRUPO_TECLADO, "Delete"),
    "KEY_LEFTALT+KEY_TAB": (GRUPO_TECLADO, "Alt + Tab"),
    "KEY_LEFTALT+KEY_LEFTSHIFT+KEY_TAB": (GRUPO_TECLADO, "Alt + Shift + Tab"),
    "KEY_LEFTMETA": (GRUPO_TECLADO, "Super (tecla Windows)"),
    "KEY_SYSRQ": (GRUPO_TECLADO, "PrintScreen"),
    "KEY_F11": (GRUPO_TECLADO, "F11"),
    TOKEN_WASD: (GRUPO_TECLADO, "Teclas WASD"),
    TOKEN_SETAS: (GRUPO_TECLADO, "Setas"),

    TOKEN_TOGGLE_OSK: (GRUPO_COMANDO, "Teclado na tela"),
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

SEM_ATENDENTE: frozenset[str] = frozenset(
    {TOKEN_STEAM, TOKEN_SAIR_DO_JOGO, TOKEN_PROGRAMA})


ORDEM_DOS_GRUPOS: tuple[str, ...] = (
    GRUPO_MOUSE, GRUPO_TECLADO, GRUPO_COMANDO, GRUPO_NENHUM)


def por_grupo(botao: str | None = None) -> list[tuple[str, list[str]]]:
    """`[(grupo, [rótulo, …]), …]` — exatamente o que a tela desenha (uma lista só).

    Com ``botao=BOTAO_PS``, só o que ele digita (:func:`o_ps_aceita`); as outras linhas não
    oferecem o «— Sem tecla —». Cada ação de eixo (:data:`LINHAS_DA_ACAO_DE_EIXO`) só aparece
    na linha que a atende, e a linha de botão não oferece nenhuma. Sem ``botao``, a geral.
    """
    def cabe(token: str) -> bool:
        if botao == BOTAO_PS:
            return o_ps_aceita(token)
        if token == TOKEN_SEM_TECLA:
            return False
        if token == TOKEN_NADA:
            return True
        linhas = LINHAS_DA_ACAO_DE_EIXO.get(token)
        if linhas is not None:
            return botao is None or botao in linhas
        return botao is None or botao not in _TOKEN_DO_EIXO

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
if len(_POR_ROTULO) != len(ACOES):  # pragma: no cover
    _repetidos = sorted({r for r in (v[1] for v in ACOES.values())
                         if list(v[1] for v in ACOES.values()).count(r) > 1})
    raise SystemExit(
        f"ERRO em acoes_de_botao: dois tokens têm o mesmo rótulo ({_repetidos}). "
        f"A tela devolve o TEXTO da opção, então rótulo repetido faz o caminho "
        f"de volta escolher ao acaso.")


def _do_teclado(botao: str) -> str | None:
    """O token que `DEFAULT_BUTTON_BINDINGS` dá àquele botão, já colado.

    O produto guarda combos como TUPLA (`("KEY_LEFTALT", "KEY_TAB")`); aqui eles
    viram a forma com `+`, a que o perfil guarda em `button_actions` e o «Gravar
    tecla» do mapa do controle captura. Uma grafia só.
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
    que a pessoa vê acontecer com o cursor na frente do usuário.

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
    fora[EIXO_ESQUERDO] = TOKEN_CURSOR
    fora[EIXO_DIREITO] = TOKEN_ROLAGEM
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
        2. `key_bindings`      o que o usuário escreveu na janela ANTIGA
        3. `button_actions`    o que o usuário escolheu na tela NOVA

    A CAMADA DO MEIO NASCEU EM 06/09/2026 (ONDA3-MOTOR-01) e ela cura uma perda
    silenciosa de escolha do usuário: `apply_button_actions` roda DEPOIS do
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
    `resolve_key_bindings` (`profiles/manager.py:2324`) devolve só as chaves do
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
    """Os botões que o usuário mandou CALAR — a quinta porta, e ela existe por medida.

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


_TOKEN_DO_EIXO: dict[str, str] = {
    EIXO_ESQUERDO: TOKEN_CURSOR,
    EIXO_DIREITO: TOKEN_ROLAGEM,
}


def resolver(
    escolhas: dict[str, str] | None,
    key_bindings: dict[str, list[str]] | None = None,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], list[str]]:
    """As escolhas do perfil separadas por quem as atende: `(do_mouse, do_teclado, sem_dono)`.

    `do_mouse` vai ao `UinputMouseDevice`, `do_teclado` ao teclado virtual e `sem_dono` guarda
    os botões que ninguém atende hoje. O PS e os botões calados ficam de fora (:func:`acao_do_ps`,
    :func:`botoes_calados`). `escolhas=None` devolve o de fábrica; `key_bindings` é a do meio.
    As teclas do analógico (:data:`TECLAS_DO_ANALOGICO`) têm dois donos, os dois em
    `daemon/subsystems/mouse.py`: a `TabelaNoJogo` (com o jogo aberto) e o laço do desktop.
    """
    tabela = tabela_efetiva(escolhas, key_bindings)

    do_mouse: dict[str, str] = {}
    do_teclado: dict[str, tuple[str, ...]] = {}
    sem_dono: list[str] = []

    tabela.pop(BOTAO_PS, None)

    for botao, token in tabela.items():
        if botao in _TOKEN_DO_EIXO:
            if token not in (TOKEN_NADA, _TOKEN_DO_EIXO[botao]):
                do_mouse[botao] = token
                if botao not in LINHAS_DA_ACAO_DE_EIXO.get(token, frozenset()):
                    sem_dono.append(botao)
            continue
        if token == TOKEN_NADA:
            continue
        if token in SEM_ATENDENTE:
            sem_dono.append(botao)
        elif token.startswith("BTN_"):
            do_mouse[botao] = token
        elif token in LINHAS_DA_ACAO_DE_EIXO:
            sem_dono.append(botao)
        else:
            do_teclado[botao] = tuple(token.split("+"))
    return do_mouse, do_teclado, sorted(sem_dono)


def nome_da_direcao(eixo: str, direcao: str) -> str:
    """O nome de botão de mentira que leva a direção de um analógico até o teclado."""
    return f"{eixo}:{direcao}"


def teclas_dos_analogicos(do_mouse: Mapping[str, str]) -> dict[str, str]:
    """`{nome da direção: tecla}` das linhas de analógico que escolheram teclas.

    `do_mouse` é a primeira sacola do :func:`resolver`. O nome é o de
    :func:`nome_da_direcao`, e quem emite (a tabela com o jogo aberto, o laço do desktop)
    registra `nome -> (tecla,)` no teclado virtual.
    """
    fora: dict[str, str] = {}
    for eixo in (EIXO_ESQUERDO, EIXO_DIREITO):
        teclas = TECLAS_DO_ANALOGICO.get(do_mouse.get(eixo, ""))
        if teclas is None:
            continue
        for direcao, tecla in zip(DIRECOES_DO_ANALOGICO, teclas, strict=True):
            fora[nome_da_direcao(eixo, direcao)] = tecla
    return fora


def direcoes_apertadas(
    teclas: Mapping[str, str], eixos: Iterable[tuple[int, int, int, int]]
) -> frozenset[str]:
    """Os nomes de direção (de `teclas`) que algum controle passa de meia deflexão AGORA.

    `eixos` traz um `(lx, ly, rx, ry)` por controle, cada eixo de 0 a 255. A diagonal são
    DUAS direções, e a tecla é a união dos controles: dois controles na mesma direção contam
    como um, e o nome só some quando o último volta ao centro. Fonte única do limiar: a
    tabela com o jogo aberto e o laço do desktop chamam esta função.
    """
    if not teclas:
        return frozenset()
    apertadas: set[str] = set()
    for lx, ly, rx, ry in eixos:
        for eixo, x, y in ((EIXO_ESQUERDO, lx, ly), (EIXO_DIREITO, rx, ry)):
            dx = (int(x) - CENTRO_DO_ANALOGICO) / CENTRO_DO_ANALOGICO
            dy = (int(y) - CENTRO_DO_ANALOGICO) / CENTRO_DO_ANALOGICO
            for direcao, passou in (
                ("esquerda", dx <= -LIMIAR_DO_ANALOGICO),
                ("direita", dx >= LIMIAR_DO_ANALOGICO),
                ("cima", dy <= -LIMIAR_DO_ANALOGICO),
                ("baixo", dy >= LIMIAR_DO_ANALOGICO),
            ):
                nome = nome_da_direcao(eixo, direcao)
                if passou and nome in teclas:
                    apertadas.add(nome)
    return frozenset(apertadas)


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
    "LIMIAR_DO_ANALOGICO",
    "LINHAS_DA_ACAO_DE_EIXO",
    "ORDEM_DOS_GRUPOS",
    "SEM_ATENDENTE",
    "TECLAS_DO_ANALOGICO",
    "TOKEN_CURSOR",
    "TOKEN_NADA",
    "TOKEN_PROGRAMA",
    "TOKEN_ROLAGEM",
    "TOKEN_SAIR_DO_JOGO",
    "TOKEN_SEM_TECLA",
    "TOKEN_SETAS",
    "TOKEN_STEAM",
    "TOKEN_WASD",
    "acao_do_ps",
    "botoes_calados",
    "direcoes_apertadas",
    "nome_da_direcao",
    "o_ps_aceita",
    "padrao",  # (noqa-acento)
    "por_grupo",
    "resolver",
    "rotulo",
    "tabela_efetiva",
    "teclas_dos_analogicos",
    "token_do_rotulo",
]
