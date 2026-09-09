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

#: O BOTÃO PS, e ele é o único desta lista cujo ATENDENTE não é device nenhum:
#: quem o serve é o callback do `ps_solo`
#: (`daemon/subsystems/hotkey.build_ps_solo_callback`). O nome que a tela mostra
#: para ele é "Botão PS", e ele vem do dono
#: (`app/actions/input_actions._BUTTON_LABELS`), não de uma digitação daqui.
BOTAO_PS = "ps"

#: AS VINTE E DUAS LINHAS, na ordem em que a tela as mostra. A ordem é dela
#: (27/08/2026, *"cada linha seria um dos botões do controle"*), e é a mesma nas
#: duas telas de botões da aba Navegação.
#:
#: O PS ENTROU EM 06/09/2026 (ONDA5-06-01), por decisão dela na 06-Q3: *"O PS
#: ganha a mesma lista das outras 21 linhas; se você der uma tecla a ele, ele
#: passa a digitar SEM parar de abrir a Steam"*. Ele fica **depois do `create` e
#: antes das três regiões do touchpad**, que é a ordem do aparelho.
#:
#: ISTO REVERTE a decisão de 04/09 (*"fica fora, e a razão vira dica"*), e a
#: reversão é dela. A régua que guardava a decisão anterior
#: (`tests/unit/test_a_aba_06_navegacao_fecha_as_linhas.py`,
#: `test_a_dica_da_tela_de_botoes_diz_por_que_o_ps_fica_fora`) mede o mundo de
#: ontem a partir deste commit; quem a aposenta é a frente da TELA (ONDA5-06-02),
#: junto com o parágrafo do `?` que ela guarda.
BOTOES: tuple[str, ...] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", EIXO_ESQUERDO, "r3", EIXO_DIREITO,
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create", BOTAO_PS,
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

#: O DEGRAU DA MÁQUINA DO BOTÃO PS, traduzido para o vocabulário da tela.
#:
#: O PS tem DOIS donos, e a precedência entre eles é escrita: o perfil
#: (`Profile.button_actions["ps"]`) vence, e o `DaemonConfig.ps_button_action`
#: é o que vale para o perfil que não diz nada. Este mapa é a tradução de um
#: para o outro — sem ele, a linha do PS na tela mostraria `— Nada —` sobre um
#: botão que abre a Steam há meses.
ACAO_DA_MAQUINA_PARA_TOKEN: dict[str, str] = {
    "steam": TOKEN_STEAM,
    "none": TOKEN_NADA,
    "custom": TOKEN_PROGRAMA,
}

#: O QUE A MÁQUINA FAZ COM O PS QUANDO NINGUÉM MEXEU — o valor de fábrica de
#: `DaemonConfig.ps_button_action` (`daemon/lifecycle.py`).
#:
#: ELE É CÓPIA, E A CÓPIA TEM RÉGUA. Este módulo é importável **sem daemon** por
#: contrato (o docstring do topo o diz, e é o que o mantém no `core/`), então
#: perguntar ao dono aqui dentro arrastaria `daemon/lifecycle.py` para dentro do
#: gerador da tela. Quem pergunta ao dono é a RÉGUA —
#: `tests/unit/test_o_ps_digita_e_continua_sendo_a_saida.py` compara este valor
#: com o default do campo em `DaemonConfig` e reprova a divergência. É a regra
#: da casa: quando um valor tem dono, a régua PERGUNTA ao dono.
PS_DA_MAQUINA_DE_FABRICA = "steam"

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


def token_do_ps_da_maquina(ps_button_action: str | None = None) -> str:
    """O que o degrau da MÁQUINA manda o PS fazer, no vocabulário da tela.

    `None` quer dizer "ninguém informou", e aí vale o de fábrica do dono
    (:data:`PS_DA_MAQUINA_DE_FABRICA`). Um valor que o dono não conhece cai no
    mesmo lugar em vez de virar `KeyError`: a tela mostrando o de fábrica é
    melhor que a aba inteira não gerando.
    """
    escolha = str(ps_button_action or PS_DA_MAQUINA_DE_FABRICA)
    return ACAO_DA_MAQUINA_PARA_TOKEN.get(
        escolha, ACAO_DA_MAQUINA_PARA_TOKEN[PS_DA_MAQUINA_DE_FABRICA])


def acao_do_ps(escolhas: dict[str, str] | None) -> str | None:
    """O token que o PERFIL deu ao botão PS — `None` quando ele não disse nada.

    A QUARTA SAÍDA, e ela é porta PRÓPRIA e não uma quarta posição na tupla do
    :func:`resolver`. A razão é medida: três chamadores desempacotam três
    sacolas (`profiles/manager.py` e duas vezes
    `interface/pacotes/a06_navegacao.py`), e devolver quatro valores viraria
    `ValueError: too many values to unpack` na aba que ela abre — o produto
    quebrado hoje para servir a frente da tela que roda depois. Uma porta nova
    não quebra ninguém e diz a mesma coisa.

    E O DESTINO É OUTRO, que é o que justifica a porta: as três sacolas do
    `resolver()` vão para DEVICES (`UinputMouseDevice`, `UinputKeyboardDevice`);
    o PS não tem device — quem o atende é o callback do `ps_solo`, e o PS nunca
    chega à emulação (`integrations/hotkey_daemon.py`, o latch do combo, subtrai
    o PS de `emu_buttons` enquanto ele estiver pressionado).

    `None` NÃO é `__NADA__`: `None` é "o perfil não opinou, vale o degrau da
    máquina"; `__NADA__` é ela dizendo que este botão não faz nada.
    """
    if not escolhas:
        return None
    token = escolhas.get(BOTAO_PS)
    return str(token) if token else None


def padrao(ps_button_action: str | None = None) -> dict[str, str]:
    """O que cada um dos 22 botões faz DE FÁBRICA, lido dos mapas do produto.

    `ps_button_action` É O DEGRAU DA MÁQUINA, e ele é parâmetro porque o PS é o
    único botão cujo de fábrica NÃO sai dos quatro mapas: ele sai de
    `DaemonConfig.ps_button_action`. Quem tem a config passa; quem não tem
    recebe o de fábrica do dono (:data:`PS_DA_MAQUINA_DE_FABRICA`).

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
    # O PS NÃO ESTÁ EM NENHUM DOS QUATRO MAPAS — medido: nem `BUTTON_TO_UINPUT`,
    # nem `DPAD_TO_KEY`, nem `EDGE_KEY_MAP`, nem `DEFAULT_BUTTON_BINDINGS`. O
    # laço acima o deixaria em `__NADA__`, e a tela diria que o botão que abre a
    # Steam há meses não faz nada. O de fábrica dele é o que ele FAZ, e quem
    # responde é o dono.
    fora[BOTAO_PS] = token_do_ps_da_maquina(ps_button_action)
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
    que `keyboard_mappings.py:56-62` registra. Digitar a lista aqui faria a
    camada de atalhos apagar o Botão do meio dele, que é regressão em botão que
    ela usa.
    """
    base = padrao()
    return frozenset(
        botao for botao in BOTOES
        if (do_teclado := _do_teclado(botao)) is not None
        and base.get(botao) == do_teclado)


#: O domínio de `key_bindings`, montado UMA vez. Hoje ele é
#: `{options, create, l1, r1, l3, touchpad_left_press, touchpad_middle_press,
#: touchpad_right_press}` — oito dos vinte e dois botões.
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
    esquema (`profiles/schema.py:1338-1340`) e a mesma que
    `profiles/manager.resolve_key_bindings` aplica ao device: `None` herda
    `DEFAULT_BUTTON_BINDINGS` inteiro — que é exatamente o que o de fábrica já
    deriva, logo não há nada a fazer —, e um dict, mesmo vazio, é a lista
    COMPLETA dela: botão do domínio que não está lá foi REMOVIDO, e vira
    `— Nada —`.

    ELA NÃO MESCLA COM O DE FÁBRICA, e isso é medido, não escolhido:
    `resolve_key_bindings` (`profiles/manager.py:1989`) devolve só as chaves do
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
    `docs/process/agentes/2026-09-06/ONDA3-MOTOR-01.md`. Curá-lo aqui de
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

    # OS DOIS GATILHOS SÃO ESPELHO, e não linha própria — descoberto pela régua
    # em 01/09/2026, no dia em que este módulo nasceu. `_resolve_emulated_set`
    # (`uinput_mouse.py:377`) troca L2 por `cross` e R2 por `triangle` ANTES de
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

    # O PS SAI DAS TRÊS SACOLAS, e não por falta de dono — por ter um dono que
    # não é device (ONDA5-06-01). Sem esta linha o de fábrica dele (`__STEAM__`,
    # que está em `SEM_ATENDENTE`) o jogaria na TERCEIRA sacola, e a tira da aba
    # escreveria na tela dela que o botão que abre a Steam "não acende nada
    # hoje" — enquanto `profiles/manager.py` registraria o mesmo no journal como
    # `button_actions_sem_atendente`.
    #
    # `SEM_ATENDENTE` CONTINUA VALENDO PARA OS OUTROS VINTE E UM. Para eles nada
    # mudou, e mudar seria a segunda cura escondida dentro da primeira.
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


#: O NOME PRIVADO CONTINUA RESPONDENDO — 06/09/2026, e o alias é a metade
#: barata de uma renomeação. `tabela_efetiva` deixou de ser privada porque tinha
#: chamador de fora havia semanas: `interface/pacotes/a06_navegacao.py:1049` a
#: chama para montar as linhas dos botões, e a alternativa — remontar as três
#: camadas dentro da aba — é a SEGUNDA VERDADE que esta casa persegue. Um
#: privado com chamador de fora não é encapsulamento, é um contrato não
#: declarado. O alias fica enquanto houver prosa e teste citando o nome velho, e
#: sai quando a última citação sair.
_tabela_efetiva = tabela_efetiva

__all__ = [
    "ACAO_DA_MAQUINA_PARA_TOKEN",
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
    "PS_DA_MAQUINA_DE_FABRICA",
    "SEM_ATENDENTE",
    "TOKEN_CURSOR",
    "TOKEN_NADA",
    "TOKEN_PROGRAMA",
    "TOKEN_ROLAGEM",
    "TOKEN_SAIR_DO_JOGO",
    "TOKEN_STEAM",
    "acao_do_ps",  # (noqa-acento) nome de função
    "botoes_calados",  # (noqa-acento) nome de função
    "padrao",  # (noqa-acento) nome de função
    "por_grupo",
    "resolver",
    "rotulo",
    "tabela_efetiva",
    "token_do_ps_da_maquina",
    "token_do_rotulo",
]
