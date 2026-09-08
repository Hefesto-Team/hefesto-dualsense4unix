#!/usr/bin/env python3
"""O pacote da aba `02` Controles — a mais servida das dez, e o MOLDE.

Ela já pintava antes deste despachante: o `controles_vivos.py` monta o pacote
dela desde 30/08, e é de lá que este arquivo tira o que sabe. O que muda é o
ENDEREÇO do conhecimento — ele sai do piloto e vira uma função com contrato, do
mesmo formato das outras nove.

TUDO O QUE ESTA ABA MOSTRA TEM DONO, e é por isso que ela foi a primeira a
viver: `inputs` (os dois analógicos, os gatilhos, os botões), `audio` (o
microfone e o alto-falante, com posse e mudo), `lightbar_rgb`, `player`,
`battery_pct`, `transport` e `vpad_backend`. Zero `sem_dono`.

E EM 02/09/2026 O CASAMENTO FECHOU — os dois lados, medidos pelo
`casamento.medir("02-controles.html")`:

    ANTES (ponta de `dev`, 2b219284)      DEPOIS
    casam :  10                           casam : 12
    órfãos: ['l2', 'r2', 'via']           órfãos: []
    vazios: ['l3', 'r3']                  vazios: []

Os dois lados eram o MESMO defeito de forma, em espelho: três valores emitidos
a cada tique para endereços que a página não tem, e dois endereços na página
que ninguém pintava. Nenhum dos cinco dava erro — `querySelector` de endereço
inexistente devolve `null`, e o pacote contava os três órfãos em
`cobertura.pintados`, reportando 13 onde pintava 10.

TER DONO NÃO É DIZER A VERDADE, e é o que a tarde de 02/09/2026 mediu. Todos os
campos acima tinham dono, o casamento fechava, e a **régua do mockup dava
`produto 16 · mockup 0`** — "nenhum campo ainda mostra o desenho", que se lê
como aba pronta. Com os DOIS controles dela na mesa, este pacote EMITIA
**"102%"** para o `alto-estado`: `speaker.volume` é o registrador do protocolo,
0-255, e a linha colava um `%` no número CRU. A régua conta se o valor MUDOU em
relação ao desenho — ela não sabe se ele está certo, e contou a mentira como
PRODUTO. Depois da cura o número dela é o MESMO: `produto 16 · mockup 0 ·
indecidível 7`. O bloco do REUSO, logo abaixo dos imports, tem as cinco regras
que saíram daqui e voltaram para o motor.

**E "EMITIA" NÃO É "MOSTRAVA" — a diferença foi medida em 02/09/2026 e a
primeira redação desta linha errava.** O `alto-estado` é
`<span class="mudo" data-campo="alto-estado" hidden>` na página publicada
(`paginas/02-controles.html:1678` e `:2009`), e o `hidden` era LITERAL no
gerador, sem condição; o `escrever` do piloto não toca o atributo `hidden` em
nenhum dos seus alvos. O "102%" ia para um vão invisível.

**O ENDEREÇO DAQUELA LINHA DO GERADOR MORREU, e o número foi retirado em
06/09/2026:** o `<span hidden>` saiu do desenho em 04/09 (decisão [09]) e o
que resta é o comentário que registra a saída (`aba02.py:1939`). O número que
estava aqui apontava para uma linha em branco desde a primeira edição que
empurrou o gerador — citação de linha que sobrevive ao código que citava é
endereço morto, e esta casa mede isso (`citacoes-no-codigo`).

**O QUE ELA VÊ NO BLOCO DO ALTO-FALANTE JÁ TEM ENDEREÇO — 02/09/2026, decisão
dela (item 16).** Eram o `<span class="n">100</span>` e a `.cheio` de
`width:100%` do desenho, sem `data-campo` nenhum: o volume na tela dela era
**100 cravado, para todo controle**. O gerador passou a endereçá-los
(`alto-num` e `alto-barra`), e o pacote os emite quando a página publicada os
tiver — a bancada é dela, e publicar também.

**E O DESENHO AO LADO DO CAMPO CONTRADIZIA O CAMPO, em dois lugares.**
Fotografado nesta aba em 02/09/2026 às 19h, com os dois controles dela na mesa:

    o campo dizia          o desenho ao lado mostrava
    luz-hex  = #0000FF     um retângulo #7EB8D4 (a cor do mockup)
    touch-estado = Sem toque   o pontinho ciano ACESO, em left:62%;top:44%

**A régua do mockup é estruturalmente cega aos dois**: ela conta `data-campo`, e
nem o retângulo nem o pontinho tinham um — `02-controles` dava `23 campos · 23
PRODUTO · 0 MOCKUP` nas duas fotos. Só o olho pega, e é por isso que a foto é
obrigatória nesta casa. Os dois ganharam endereço no gerador (`luz-cor` e
`touch-ponto`) e dono aqui.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.actions.home_actions import (
    mascara_viva,
    palavra_do_transporte,
)
from hefesto_dualsense4unix.app.ipc_bridge import (
    alvo_honrado,
    frase_do_ato_do_microfone,
    frase_do_interruptor_de_sensor,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ALL_BUTTONS,
    CANAL_SONS_DO_JOGO,
    CANAL_TODO_O_PC,
    DICA_AUDIO_SEM_ENDERECO,
    DICA_CANAL_ACORDADO,
    DICA_CANAL_DORMINDO,
    DICA_CANAL_E_PADRAO,
    DICA_CANAL_SEM_A_REGRA,
    L2_R2_THRESHOLD,
    ROTA_DO_CANAL,
    TEXTO_AUDIO_SEM_ENDERECO,
    TEXTO_SELO_CANAL_DORMINDO,
    TEXTO_SELO_SAIDA_MUDA,
    _markup_xy,
    acao_mic,
    acao_speaker_mudo,
    accel_do_inputs,
    dica_do_titulo,
    frase_do_alvo_do_mic,
    gyro_do_inputs,
    rotulo_lightbar,
    saida_muda_do_entry,
    speaker_do_entry,
    texto_motion,
    touchpad_do_inputs,
    uniq_do_entry,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    ESCALA_ACCEL_G,
    ESCALA_GYRO_GRAUS_S,
    texto_eixo,
    texto_eixo_g,
    texto_toques,
    texto_volume,
)
from hefesto_dualsense4unix.core.speaker_scale import (
    percentual_do_volume,
    volume_do_percentual,
)

from . import (
    NOME_SEM_LEITURA,
    Contexto,
    degradacao_de,
    identidade_de,
    registrar,
)

# ---------------------------------------------------------------------------
# O MOTOR ACIMA, e por que ele entrou — 02/09/2026
# ---------------------------------------------------------------------------
# LEI 0 desta migração, palavra dela: *"no gtk eu já deixei praticamente tudo
# pronto… Não temos que recriar nada."* Medido no dia: `controller_card.py` tem
# **26 funções públicas de módulo** — 5.951 linhas de texto de tela que a GTK já
# provou —, e a interface nova alcançava **duas** (`rotulo_lightbar`, pela aba
# Iluminação, e `texto_degradacao`, pelo `pacotes/__init__.py`). Esta aba, que é
# a mais servida das dez, chamava **zero**.
#
# CADA UM DOS CINCO NOMES ACIMA SUBSTITUI UMA REGRA REESCRITA AQUI, e três delas
# estavam ERRADAS. O que cada um cura está escrito no ponto de uso; o resumo:
#
#   `speaker_do_entry`   o bloco do alto-falante mora em DUAS posições
#                        (`entry.speaker` e `entry.inputs.speaker`), e este
#                        arquivo lia só a primeira — em TRÊS lugares.
#   `texto_volume`       o registrador é 0-255 e não por cento. Esta aba
#                        escrevia o número CRU com um `%` colado.
#   `texto_toques`       "Sem toque" estava redigitado aqui, com um comentário
#                        dizendo que era "o do produto".
#   `rotulo_lightbar`    cor de fonte DESCONHECIDA não é `#000000`.
#   `mascara_viva`       `uhid` é BACKEND, e a tabela de nomes é de MÁSCARA.
#
# E EM 02/09/2026 À NOITE ENTRARAM MAIS QUATRO, com o que cada um curou:
#
#   `touchpad_do_inputs` os TRÊS estados do touchpad numa função só, e a
#                        POSIÇÃO do dedo, que esta aba nunca pediu a ninguém.
#                        Ele tinha sido RECUSADO aqui, e a recusa caiu: ela era
#                        sobre um bloco que o daemon não publica. Ver o bloco
#                        `O TOUCHPAD`, com as 60 leituras.
#   `percentual_do_volume`  a curva medida no hardware, para o número e a barra
#                        do volume — os mesmos 0-100 que `texto_volume` usa.
#   `acao_mic`           sem leitura de `audio` o botão do 🎙 CHUTAVA:
#                        `bool(None)` → `False` → `mic_set(True)`.
#   `acao_speaker_mudo`  o ♪ sem volume conhecido travava no daemon, e não
#                        aqui. Recusa de longe depende do outro lado recusar.
#
# O IMPORT É POR SÍMBOLO, e isso importa para o `portao_a_casa_sabe_e_o_produto_
# nao_faz`: ele resolve o nome ao MÓDULO DE ORIGEM (`from x.y import f` conta
# para `x.y::f`, *"e para mais nada"*). Importar `home_actions` não declara
# alcançadas as outras 34 funções dele.
#
# E ELE NÃO PUXA JANELA: medido em 02/09/2026 num processo sem `DISPLAY`, os
# cinco importam e respondem. A regra desta casa que autoriza é a mesma que o
# bloco do microfone já invoca mais abaixo — o aviso contra `app/actions/*` é
# sobre os MIXINS GTK (`self._get`, `self._toast_light`), e `mascara_viva` é
# função de MÓDULO, pura, sobre um dicionário.

# ---------------------------------------------------------------------------
# O TEXTO DE TELA DESTA ABA — e ele mora AQUI, não no gerador
# ---------------------------------------------------------------------------
# Quem escreve estas palavras na tela é o produto, a cada tique; o gerador as
# desenha uma vez e as lê daqui (`aba02.py`, no topo). A seta aponta para cá por
# medição, não por gosto: o `portao_a_casa_sabe_e_o_produto_nao_faz` PODA os
# `abaNN.py` da conta por serem BANCADA, e importar o gerador de dentro do
# pacote arrastaria a bancada para o fecho de produção — medido em 02/09/2026,
# três lápides de `interface/monta.py` (`monta`, `luzinhas`, `tom_da_casa`)
# viraram alcançáveis e o portão reprovou nomeando as três.

# ---------------------------------------------------------------------------
# O TOUCHPAD — UM DONO SÓ, e ele é o do produto
# ---------------------------------------------------------------------------
# A GTK PINTA O TOUCHPAD EM QUATRO LINHAS, e elas são o contrato inteiro
# (`app/widgets/controller_card.py:5068-5080`):
#
#     dados = touchpad_do_inputs(inputs)
#     if dados is None: ...esconde o bloco...
#     tocando, fx, fy = dados
#     self._touch_view.set_toque((fx, fy) if tocando else None)   ← O PONTO
#     self._touch_label.set_text(texto_toques(1 if tocando else 0))  ← A PALAVRA
#
# ESTA ABA RECUSOU O DONO EM 02/09/2026, E A RECUSA CAIU. O argumento escrito
# aqui era que `touchpad_do_inputs` *"exige `bloco['x']` e `bloco['y']`: um
# bloco com `{"touching": True}` e sem coordenada cai no `except KeyError` e
# volta `None`"* — e que trocá-lo faria a tela dizer "não sei" sobre um dedo que
# o daemon ESTÁ vendo.
#
# **O DAEMON NÃO PUBLICA ESSE BLOCO.** Quem monta a chave `touchpad` é
# `daemon/sensor_hub.py:155-161`, e ela é UM literal com as CINCO chaves juntas
# (`touching`, `x`, `y`, `width`, `height`) — não há caminho no código que
# escreva `touching` sem escrever `x`. Medido em 02/09/2026 às 19h, com os dois
# controles dela na mesa (um `usb`, um `bt`), 60 leituras de `daemon.state_full`
# de LEITURA pura:
#
#     touchpad presente ......... 36 amostras
#     chaves de cada bloco ...... "height,touching,width,x,y"  em 36 de 36
#     `touching` verdadeiro ..... 0 de 36
#     `inputs` SEM a chave ...... 24 (o aquecimento: o reader do touchpad nasce
#                                    sob demanda, `sensor_hub.leitura:113`)
#     `inputs` não-dict ......... 60 (o controle que não é `is_primary`)
#
# O ESTADO QUE A RECUSA PROTEGIA NÃO EXISTE, E O QUE ELA CUSTOU É MAIOR: o
# `touchpad_do_inputs` é o dono de `fx`/`fy` — a POSIÇÃO do dedo, normalizada
# pelos limites que o próprio payload declara —, e sem ele esta aba nunca pediu
# a posição a ninguém. Fotografado em 02/09/2026: com `touching` FALSO nos dois
# controles, o ponto ciano estava aceso no card do P1, parado em `left:62%;
# top:44%`, que é onde o mockup o cravou. A dica do próprio campo promete o
# contrário — *"Sem toque não há ponto"*.
#
# DECISÃO DELA, 02/09/2026 (item 15): *"o touchpad usa a palavra do produto:
# '1 toque', '2 toques', 'Sem toque' (…) E o pontinho do touchpad só aparece
# quando há toque"*. As duas metades são as duas linhas da GTK acima.
#
# "2 TOQUES" NÃO SE INVENTA AQUI: `texto_toques` conta DEDOS e o `state_full`
# publica UM booleano, então a conta que esta aba pode passar é `1 if tocando
# else 0` — a MESMA da GTK, na mesma linha. No dia em que o daemon publicar o
# segundo dedo, a palavra sai daqui sem ninguém tocar nesta aba.


def toque_do_controle(inputs: Any) -> tuple[str, str, tuple[float, float] | None]:
    """`(palavra, ponto, onde)` do touchpad — as TRÊS linhas da GTK, num terno.

    `palavra` é o `touch-estado`; `ponto` é o `touch-ponto`, que o desenho lê
    como CLASSE (`data-hef-alvo="classe"`): `""` apaga o pontinho e qualquer
    outra coisa o acende (`hefesto_vivo.BOOTSTRAP::ligado`); `onde` é a POSIÇÃO
    do dedo em POR CENTO da superfície, ou `None` quando não houve leitura.

    O TERCEIRO ERA JOGADO FORA, e ele é a queixa dela — *"não funciona o touch,
    analogicos"*. `touchpad_do_inputs` devolve `(tocando, fx, fy)` com os dois
    últimos já normalizados 0..1 pelos limites que o PRÓPRIO payload declara
    (`sensor_widgets.posicao_normalizada`), e esta função lia só `lido[0]`: o
    pontinho acendia e apagava certo, e ficava parado onde o mockup o cravou —
    `left:62%;top:44%`. Acender no lugar errado é a mesma família de defeito que
    esta aba já pagou duas vezes: **ter dono não é dizer a verdade**.

    A POSIÇÃO VEM MESMO SEM TOQUE, e é de propósito: o pontinho está invisível
    (`opacity:0` sem a classe `on`, decisão dela de 02/09 item 15), então
    escrevê-la não afirma nada na tela — e quando o dedo pousa ele já nasce no
    lugar certo, em vez de piscar um quadro na posição anterior.

    Sem leitura, os TRÊS dizem "não sei": a palavra vira o travessão, o ponto
    apaga e a posição some. Apagar aqui não é afirmar "ninguém está tocando" — é
    a mesma recusa que a GTK faz escondendo o bloco inteiro, e é a única coisa
    que esta tela pode fazer sem inventar uma posição.
    """
    lido = touchpad_do_inputs(inputs)
    if lido is None:
        import mesa_viva

        return (str(mesa_viva.SEM_LEITOR), "", None)
    tocando = bool(lido[0])
    return (texto_toques(1 if tocando else 0), "sim" if tocando else "",
            (round(lido[1] * 100, 1), round(lido[2] * 100, 1)))


# ---------------------------------------------------------------------------
# A LEITURA VIVA — o nome desta aba, e o que ela NÃO fazia até 03/09/2026
# ---------------------------------------------------------------------------
# O QUE ESTAVA NA TELA DELA, medido com os dois controles na mesa e o aparelho
# PARADO (`daemon.state_full`, 03/09/2026):
#
#   na tela (o desenho)              no aparelho (o daemon)
#   cross · dpad_up · l2 acesos      buttons = []
#   L2 200 / 255 · R2 40 / 255       l2_raw = 0 · r2_raw = 0
#   giro +143.2 / -412.0 / +22.8     gyro  x=-0.24 y=-0.61 z=-0.3
#   accel +0.105 / +0.976 / +0.170   accel x=0.116 y=0.948 z=0.204
#   X:  60 · Y: 200                  lx=125 ly=121
#
# NÃO É TELA VAZIA, É TELA QUE MENTE — e no card do P2 é pior: ele NÃO TEM
# `inputs` (o daemon só publica leitura para o `is_primary`), e mostrava os
# mesmos números como se estivesse medindo.
#
# NADA AQUI É REGRA NOVA. Os cinco donos já existiam na GTK, e é o que a LEI 0
# manda: achar a função e CHAMAR.
#
#   `ALL_BUTTONS` + `L2_R2_THRESHOLD`  os 16 nomes e o limiar de L2/R2, do
#                                      `_refresh_glyphs` (controller_card:5425)
#   `gyro_do_inputs` / `accel_do_inputs`  os três eixos, ou `None` quando o
#                                      bloco não veio — os DOIS já eram públicos
#   `texto_eixo` / `texto_eixo_g`      a grafia de largura fixa (+7.1f e +7.2f),
#                                      que existe para o painel não "respirar"
#   `_markup_xy`                       os dois eixos do analógico
#   `mesa_viva._barra_bipolar`         a geometria e a cor da barrinha
#
# O `_markup_xy` COMEÇA COM UNDERSCORE E MESMO ASSIM SE IMPORTA: ele é função de
# MÓDULO, pura, e é o dono da frase — redigitar `f"X:{x:>3}"` aqui seria a
# segunda cópia que a LEI 0 proíbe, e uma cópia que já divergiu (o desenho
# escrevia `X: {x:>3}`, com um espaço a mais).


def meias_da_barra(estilo: Any) -> tuple[str, str, str]:
    """`(negativa%, positiva%, cor)` de uma barrinha de eixo.

    RECEBE O QUE `mesa_viva._barra_bipolar` DEVOLVE — o dono da geometria e da
    cor —, e só o RE-EXPRESSA na gramática que o piloto alcança: duas metades
    ancoradas no centro, cada uma com a sua largura. Aceita o dicionário dele e
    também a string `left:…;width:…;background:…` que o desenho carrega, porque
    o gerador tem as duas formas na cena fixa do mockup.

    O SINAL SAI DO `left`, e isso é conta do dono: `_barra_bipolar` devolve
    `esquerda = 50 - largura` para todo valor negativo, então `left < 50%` é
    exatamente "esta barra desce para a esquerda". Só uma das metades tem
    largura por vez.

    A LARGURA VOLTA COMO VEIO, em texto: `"22"`, `"0.4"`, `"0"`. Convertê-la
    para `float` e reimprimi-la trocaria `0%` por `0.0%` no desenho — um diff
    em cada eixo de cada card, sem um pixel de diferença.
    """
    if isinstance(estilo, str):
        estilo = dict(
            p.split(":", 1) for p in estilo.split(";") if ":" in p  # noqa-acento (CSS)
        )
    largura = str(estilo.get("width", "0%")).strip().removesuffix("%")
    esquerda = str(estilo.get("left", "50%")).strip().removesuffix("%")
    cor = str(estilo.get("background", ""))
    negativa = float(esquerda or 50) < 50.0
    return (largura if negativa else "0", "0" if negativa else largura, cor)


def texto_do_xy(x: Any, y: Any) -> str:
    """Os dois eixos de um analógico, na frase do produto e com quebra de HTML.

    `_markup_xy` devolve `"X:125\\nY:121"`; a tela dela quebra com `<br>`, e o
    alvo `html` do piloto é o que escreve marcação (`hefesto_vivo.py`, ramo
    `html`) — o alvo padrão escreveria o `<br>` como texto literal.
    """
    return _markup_xy(int(x), int(y)).replace("\n", "<br>")


# ---------------------------------------------------------------------------
# A POSIÇÃO DOS PONTINHOS — a queixa dela, e por que ela não era alcançável
# ---------------------------------------------------------------------------
# A QUEIXA, com dois DualSense na mesa (um no cabo, um no rádio): *"não funciona
# o touch, analogicos"*. Ela está certa nos dois, e os dois são o MESMO defeito
# em dois lugares.
#
# O DADO CHEGA INTEIRO. `daemon/sensor_hub.py` publica o bloco `touchpad` com as
# cinco chaves (`touching`, `x`, `y`, `width`, `height`) e o `inputs` com
# `lx`/`ly`/`rx`/`ry`; `docs/data/mapa-controles.csv` diz `toque.touchpad = sim`
# nos DOIS transportes. Quem o normaliza também já existe e é do produto:
# `touchpad_do_inputs` devolve `(tocando, fx, fy)` em 0..1, e
# `mesa_viva._eixo_do_analogico` devolve o eixo cru com o zero PRESERVADO (num
# analógico o zero é o EXTREMO, não o centro — defeito medido e curado em 29/08).
#
# O QUE FALTAVA ERA O CANAL. Na página, o `.ponto` do touchpad tem endereço só
# para ACENDER (`data-hef-alvo="classe"`) e os dois `<span class="p">` dos
# analógicos não tinham endereço nenhum: o `left`/`top` dos três era `style=` de
# LINHA, escrito pelo desenho. **Estilo de linha vence folha de estilo**, e
# `escrever()` do piloto não tem alvo que escreva `style` — o alvo `atributo` o
# RECUSA por nome (`hefesto_vivo.atributo_escrevivel`, que exige `data-`/`aria-`
# ou `title`). Fotografado em 02/09 e ainda de pé em 04/09: o pontinho ciano do
# P1 parado em `left:62%;top:44%`, que é onde o mockup o cravou.
#
# A CURA É A DA COR DO PLÁSTICO, e não precisa de alvo novo: a posição sai do
# `style=` e vira REGRA numa folha endereçada que o produto TROCA INTEIRA
# (`data-campo="posicao-css"`, alvo `html`). É a mesma forma que
# `folha_do_plastico` já usa, e o gerador faz a mesma mudança do lado do desenho
# (`aba02.posicao_por_regra`).
#
# POR QUE UMA FOLHA IRMÃ, E NÃO A MESMA DO PLÁSTICO — a escolha é de DONO e de
# CADÊNCIA, e a razão é estrutural: uma folha endereçada é substituída INTEIRA.
# O plástico sai da MESA (identidade: muda quando um controle entra ou sai) e a
# posição sai da LEITURA (muda a cada tique). Numa folha só, um tique que
# soubesse a identidade e não a leitura teria de reemitir a posição para não
# apagá-la — e vice-versa: os dois "não sei" ficariam amarrados um no outro, que
# é justamente o que a regra dela (*campo sem informação não mostra nada*) exige
# separar. Duas folhas não têm o buraco das DUAS FOLHAS de 03/09, que era outro:
# lá as duas escreviam a MESMA propriedade (`--plastico`) e só se sobrepunham no
# assento que a segunda nomeava. Aqui as propriedades são disjuntas.

#: O CURSO DE UM EIXO DE ANALÓGICO, cru. É o `max` do `absinfo` dos dois
#: DualSense dela (`ABS_X/ABS_Y/ABS_RX/ABS_RY min=0 max=255`), o mesmo 255 que
#: os gatilhos já escrevem em `leitura_viva`.
CURSO_DO_ANALOGICO = 255
#: O REPOUSO, e ele é também a AUSÊNCIA — é o que a GTK faz
#: (`int(inputs.get("lx", 128))`) e o que `mesa_viva._eixo_do_analogico`
#: devolve quando a chave não veio.
REPOUSO_DO_ANALOGICO = 128


def pos_do_analogico(v: Any) -> float:
    """0-255 -> posição em % dentro do círculo. 128 é o centro.

    ESTA CONTA MORAVA NO GERADOR (`aba02.pos`) e mudou de lado — a seta aponta
    para o produto, como já apontam `ROTULO_DO_CLIQUE` e `texto_do_xy`. Duas
    cópias dela seriam duas geometrias: a do desenho e a da tela viva, divergindo
    calada no dia em que uma das duas fosse ajustada.

    A CONTA DA GTK NÃO SERVE AQUI, E ISSO NÃO É REESCREVER O MOTOR. O
    `StickPreviewGtk` põe o ponto em `centro + (v-128)/128 * raio * 0,85`
    (`gui/widgets/stick_preview_gtk.py`), confinando-o a 85% do raio porque quem
    desenha é o Cairo e o ponto de 6px vazaria o anel. Na página o ponto é
    centrado pelo CSS (`transform:translate(-50%,-50%)` no `.stick .p`) e 100% é
    a borda do círculo — copiar o 0,85 encolheria em 15% o curso que ela
    aprovou, sem a palavra dela. O que se reusa da GTK é a LEITURA do eixo
    (`mesa_viva._eixo_do_analogico`, com o zero preservado), que é onde estava o
    defeito de verdade.
    """
    return round(int(v) / CURSO_DO_ANALOGICO * 100, 1)


#: ONDE MORA CADA PONTINHO, dentro do card de um controle. Os três seletores em
#: um lugar só: o gerador os importa daqui para escrever a folha do DESENHO, e
#: `folha_das_posicoes` os usa para a folha VIVA. Duas gramáticas para a mesma
#: regra é o que faz as duas folhas divergirem sem ninguém ver — foi a lição do
#: `seletor_do_plastico`.
ALVOS_DA_POSICAO: dict[str, str] = {
    "touch": ".touch .ponto",
    "ana-e": '.stick[data-stick="l"] .p',
    "ana-d": '.stick[data-stick="r"] .p',
}


def seletor_da_posicao(pref: str, alvo: str) -> str:
    """O seletor de UM pontinho de UM assento. `pref` é `p1`… (o `data-controle`)."""
    return f'.ctl[data-controle="{pref}"] {ALVOS_DA_POSICAO[alvo]}'


def regra_da_posicao(pref: str, alvo: str, x: Any, y: Any) -> str:
    """A regra CSS de um pontinho: seletor + `left`/`top` em por cento."""
    return f"{seletor_da_posicao(pref, alvo)}{{left:{x}%;top:{y}%}}"


#: O PISO DA FOLHA, e ele existe pela mesma razão que o `PISO_DA_FOLHA` do
#: plástico: a folha é trocada INTEIRA, então o assento que a mesa viva não
#: nomeia tem de cair num neutro — e não sobrar com a posição que o desenho
#: deixou ali. O neutro é o REPOUSO (128 nos dois eixos), que é o que o `xy-l`
#: /`xy-r` ao lado já dizem quando não há leitura, e onde o pontinho do touchpad
#: fica invisível de qualquer modo.
#:
#: A ESPECIFICIDADE É O QUE FAZ ISTO FUNCIONAR, e ela foi contada: o piso é
#: `.ctl .touch .ponto` (0,3,0) e a regra de um assento é
#: `.ctl[data-controle="p1"] .touch .ponto` (0,4,0) — a específica vence
#: independentemente da ordem em que as duas apareçam na folha.
PISO_DAS_POSICOES = (
    f".ctl .touch .ponto,.ctl .stick .p"
    f"{{left:{pos_do_analogico(REPOUSO_DO_ANALOGICO)}%;"
    f"top:{pos_do_analogico(REPOUSO_DO_ANALOGICO)}%}}"
)


def posicoes_do_controle(
    inputs: Any, tem_leitor: bool, onde_o_dedo: tuple[float, float] | None
) -> dict[str, tuple[float, float] | None]:
    """Os TRÊS pontinhos de um controle, em % — `None` no que não se leu.

    `onde_o_dedo` vem de :func:`toque_do_controle`, que já perguntou ao dono
    (`touchpad_do_inputs`); pedi-lo de novo aqui seria ler o mesmo bloco duas
    vezes por tique e abrir a porta para as duas leituras discordarem.

    OS ANALÓGICOS SÓ SAEM COM LEITOR. `tem_leitor` é o mesmo `isinstance(...,
    dict)` que o `pacote()` usa para os outros 46 campos: sem ele o repouso (128)
    seria indistinguível de "o daemon não publica `inputs` para este controle" —
    e é justamente o card do P2 da mesa dela, que mostrava os números do P1 como
    se estivesse medindo. Sem regra, o pontinho cai no piso, que é o centro.
    """
    import mesa_viva

    e: dict[str, Any] = inputs if isinstance(inputs, dict) else {}
    return {
        "touch": onde_o_dedo,
        **{
            alvo: (
                (pos_do_analogico(mesa_viva._eixo_do_analogico(e, cx)),
                 pos_do_analogico(mesa_viva._eixo_do_analogico(e, cy)))
                if tem_leitor else None
            )
            for alvo, (cx, cy) in (("ana-e", ("lx", "ly")), ("ana-d", ("rx", "ry")))
        },
    }


def folha_das_posicoes(
    posicoes: dict[str, dict[str, tuple[float, float] | None]],
) -> str:
    """A folha de posição INTEIRA, montada da leitura VIVA.

    `posicoes` é `{pref: {alvo: (x, y) | None}}`. Assento sem `pref` e alvo sem
    leitura não viram regra — quem não tem o que dizer não escreve, e o piso
    responde por ele.
    """
    return "\n".join([PISO_DAS_POSICOES] + [
        regra_da_posicao(pref, alvo, x, y)
        for pref, alvos in posicoes.items()
        if pref
        for alvo, xy in alvos.items()
        if xy is not None
        for x, y in (xy,)
    ])


def _eixos_do_sensor(
    familia: str, lido: tuple[float, float, float] | None, escala: float, grafia: Any
) -> dict[str, Any]:
    """Os quatro campos de cada eixo de um sensor — número, duas metades e cor.

    `lido is None` é "a leitura não chegou", e é o estado que a GTK trata
    escondendo a moldura (`_update_gyro`). Esta tela não tem alvo que esconda,
    então ela diz o que sobra de honesto: travessão no número e barra a zero,
    que é o mesmo desfecho da `bateria-barra` e do `alto-barra`.
    """
    import mesa_viva

    campos: dict[str, Any] = {}
    for i, eixo in enumerate(("x", "y", "z")):
        valor = lido[i] if lido is not None else None
        chave = f"{familia}-{eixo}"
        neg, pos, cor = meias_da_barra(mesa_viva._barra_bipolar(valor, escala))
        campos[chave] = grafia(valor) if valor is not None else str(mesa_viva.SEM_LEITOR)
        campos[f"{chave}-neg"] = neg
        campos[f"{chave}-pos"] = pos
        campos[f"{chave}-cor"] = cor
    return campos


def leitura_viva(entrada: dict[str, Any]) -> dict[str, Any]:
    """Tudo o que o card LÊ do aparelho: glifos, gatilhos, analógicos, sensores.

    SEM LEITOR, TUDO VOLTA AO REPOUSO — e não ao último valor nem ao desenho. É
    o `_reset_inputs_render` da GTK (`controller_card.py:5489`), linha por
    linha: gatilhos em `0 / 255` com a barra vazia, analógicos no centro, os
    dezesseis glifos apagados e os sensores no travessão. Vale para METADE da
    mesa dela agora: o daemon só publica `inputs` para o `is_primary`.
    """
    # `inputs` TEM TRÊS ESTADOS e o `or {}` só enxerga dois — é o mesmo cuidado
    # que o `tem_leitor` do `pacote()` já toma. Aqui o desfecho é o mesmo para
    # `None` e para `{}` (tudo ao repouso), mas a leitura passa por uma variável
    # DECLARADA `dict`: sem ela o `mypy`, que é portão, acusa `Item "None" …
    # has no attribute "get"` em quatro linhas.
    lido = entrada.get("inputs")
    e: dict[str, Any] = lido if isinstance(lido, dict) else {}
    apertados = {str(b) for b in (e.get("buttons") or ())}
    l2 = int(e.get("l2_raw") or 0)
    r2 = int(e.get("r2_raw") or 0)
    # O REMENDO DO NOME É DO PRODUTO, e ele carrega número de defeito:
    # BUG-GLYPH-SHARE-NAME-MISMATCH-01 — *"o daemon emite `create`
    # (BTN_SELECT), mas o glyph/asset chama-se `share`"*. Sem ele o glifo do
    # `share` fica morto e ninguém vê.
    aceso = {n: n in apertados for n in ALL_BUTTONS}
    aceso["share"] = ("share" in apertados) or ("create" in apertados)
    aceso["l2"] = l2 > L2_R2_THRESHOLD
    aceso["r2"] = r2 > L2_R2_THRESHOLD

    campos: dict[str, Any] = {f"glifo-{n}": ("sim" if aceso[n] else "") for n in aceso}
    # A FRASE DOS GATILHOS É A DA GTK, palavra por palavra (`f"{l2} / 255"`,
    # `controller_card.py:5393`), e a barra é a mesma fração — `set_fraction(l2
    # / 255)` ali, `width` em por cento aqui. `//` porque o desenho já escreve
    # inteiro e um `22.35%` seria um dígito a mais no `style` a cada tique.
    for nome, cru in (("l2", l2), ("r2", r2)):
        campos[f"{nome}-num"] = f"{cru} / 255"
        campos[f"{nome}-barra"] = cru * 100 // 255
    # OS ANALÓGICOS. O centro é 128 e a AUSÊNCIA também é 128 — é o que a GTK
    # faz (`int(inputs.get("lx", 128))`), e é o repouso do
    # `_reset_inputs_render`. Aqui não se usa `or 128`: `0` é o EXTREMO do
    # curso, e o `or` o transformaria no centro (o defeito que
    # `mesa_viva._eixo_do_analogico` mediu e curou em 29/08).
    for lado, (cx, cy) in (("l", ("lx", "ly")), ("r", ("rx", "ry"))):
        x, y = e.get(cx), e.get(cy)
        campos[f"xy-{lado}"] = texto_do_xy(128 if x is None else x, 128 if y is None else y)
    campos.update(_eixos_do_sensor("giro", gyro_do_inputs(e), ESCALA_GYRO_GRAUS_S, texto_eixo))
    campos.update(
        _eixos_do_sensor("accel", accel_do_inputs(e), ESCALA_ACCEL_G, texto_eixo_g)
    )
    return campos


# ---------------------------------------------------------------------------
# A IDENTIDADE VEM DA FITA, NUNCA DO MOCKUP — 03/09/2026
# ---------------------------------------------------------------------------
# A LEI É DELA: *"se no topo tá mostrando controle white player 1, então cada aba
# vai usar os controles lá de cima. Não mistura com a info dos mockups. (…) Por
# isso temos o mapa pra servir como variável de identificação"* — e, sobre a cor:
# *"se identificou o controle
# como modelo White a cor do card em volta tem que ser branco. Temos isso no
# mapa."*
#
# O QUE ELA VIU, com os dois controles dela na mesa e três centímetros entre uma
# coisa e outra: a fita dizia `P1 · White · USB` e o cabeçalho do card logo
# abaixo dizia `Cosmic Red · USB`. Nenhuma das cores do card era do aparelho
# dela.
#
# O DONO DO HEXA É O MAPA DELA — `docs/data/cores-do-dualsense.csv`, 28 modelos
# e 10 zonas —, e quem o lê é `interface/monta.cor_da_zona()`, que tira a cor da
# folha que `scripts/gerar_cores_do_dualsense.py` pintou dentro do SVG. É a MESMA
# porta que a `a01_jogar._cor_do_plastico` e a `a06_navegacao.cor_do_plastico`
# usam, e é o que faz o chip da fita e a borda do card três centímetros abaixo
# não poderem discordar.
#
# FATO SUBSTITUÍDO — 03/09/2026. Aqui estava escrito que importar `monta` daqui
# *"arrastaria a bancada para o fecho de produção — três lápides de monta.py
# virando alcançáveis"*, e que o dono do hexa era
# `integrations/cor_do_plastico.cor_do_nome` + `TONS`. As duas metades caíram no
# mesmo dia:
#
# * a lápide: a `a01_jogar` importa `monta` por dentro de função desde 03/09 e o
#   `portao_a_casa_sabe_e_o_produto_nao_faz` fecha VERDE (42 passed) — medido
#   nesta árvore antes e depois desta cura;
# * a tabela: `TONS` tem VINTE E UMA linhas contra as 28 dela, e **vinte das
#   vinte e uma são aproximadas** (o próprio cabeçalho daquele módulo o diz; só
#   a `05` foi medida). O mapa dela é amostragem do aparelho.
#
# O QUE ISSO CUSTAVA, MEDIDO NOS 28 MODELOS DELA (03/09/2026): o chip da fita
# (`monta.cor_da_zona`, mapa dela) e a borda do card (`TONS`) devolviam cores
# DIFERENTES em **28 de 28** — Cosmic Red `#ae335a` contra `#da244b`, White
# `#e4e0d8` contra `#edeef0` —, e em **DEZ dos 28** a borda não saía cor
# nenhuma. Sete porque o código de fábrica não está nas 21 linhas
# (HyperPop Techno Red, Remix Green, Rhythm Blue, Ghost of Yōtei, Marathon,
# Genshin Impact, 007 First Light) e TRÊS porque o nome que a mesa entrega vem
# do CSV dela e não bate com o digitado: `God of War Ragnarök` (com trema),
# `Marvel's Spider-Man 2` e `Icon Blue Special Edition`.
#
# A CHAVE PASSA A SER O SLUG, e não o nome. `mesa_viva.mesa_do_estado` já põe
# `cor` no item da mesa — o `id` da linha dela (`white`, `nova-pink`) —, e casar
# por identificador em vez de por texto de tela mata as três divergências de
# nome de uma vez. O `nome` continua sendo o que se ESCREVE; o `cor` é o que se
# PINTA.
#
# O QUE `integrations/cor_do_plastico` continua respondendo, e é a metade que
# não caiu: `tom_para_a_borda` — o piso de contraste de 2,2:1 sobre o fundo do
# card, com a mistura com branco que impede o Midnight Black de virar ausência
# de borda. Ele é o MESMO que o `legivel()` do gerador de cores já aplica, então
# reaplicá-lo aqui passa as 22 cores medidas INTACTAS (conferido nos 28) e ainda
# serve de peneira: um `url(#hachura-sem-hex)` sai como `""`.

#: A BORDA DE QUEM NÃO TEM COR LIDA. É o token que o lugar VAZIO desta aba já
#: usa (`aba02.py`, `.ctl.off{border:1px solid var(--border-forte)}`), e não uma
#: cor nova: pelo rádio a cor do plástico não é lida — o mapa de canais diz
#: `identidade.cor_do_aparelho`, `radio_aciona = não` — e a regra dela é que
#: campo sem informação não mostra nada. Deixar o card na cor do DESENHO seria
#: exatamente a mentira que esta seção veio matar.
BORDA_SEM_COR = "var(--border-forte)"

#: O PISO DA FOLHA — a cor do assento que a mesa VIVA não nomeia, e ele é o que
#: torna a troca inteira honesta.
#:
#: A PÁGINA TEM QUATRO ASSENTOS e a mesa viva tem os controles que estiverem
#: ligados AGORA. Sem este piso, o assento sem controle ficava com a cor que o
#: DESENHO deixou na folha: com um White no cabo e mais nada, o `p2` seguia
#: `#7eb8d4` — Starlight Blue num lugar vazio, medido no WebKitGTK em
#: 03/09/2026 (`borderTopColor` → `rgb(126, 184, 212)`).
#:
#: E ELE NÃO PODE SER AUSÊNCIA: `.ctl{border:2px solid var(--plastico)}`, e uma
#: `var()` sem valor invalida a declaração inteira — a borda não fica neutra,
#: ela some. A lição está medida no `.ctl.off` do `aba02.py`.
#:
#: A CÓPIA É DELIBERADA. O gêmeo deste texto é `aba02.PISO_DO_PLASTICO`, e os
#: dois não podem se importar: o gerador é dono da BANCADA e o pacote é dono do
#: PRODUTO — importar um do outro arrastaria a bancada para o fecho de produção
#: (medido em 02/09, três lápides de `monta.py` virando alcançáveis). Quem
#: impede a divergência é o teste, que compara os dois byte a byte.
PISO_DA_FOLHA = ".ctl[data-controle],.fita .chip[for]{--plastico:var(--border-forte)}"


def _monta() -> Any:
    """O `monta`, importado TARDE. O `pacotes/__init__` põe `interface/` no path.

    Tarde e não no topo pela razão que a `a06_navegacao._monta` já mediu: `monta`
    lê o `topo.html`, o `fim.html` e o SVG dos 28 modelos no import, e um pacote
    é importado por teste sem janela nenhuma. Pagar 4,7 MB de leitura para
    responder *"qual é o hexa do plástico"* é o desperdício que o import tardio
    evita — e é o mesmo caminho da `a01_jogar._cor_do_plastico`.
    """
    import monta

    return monta


def cor_da_borda(slug: str) -> str:
    """O hexa da borda daquele plástico, ou o neutro quando não se leu.

    `slug` é o `id` da linha dela em `docs/data/cores-do-dualsense.csv` —
    `white`, `nova-pink`, `astro-bot` —, e é o campo `cor` que
    `mesa_viva.mesa_do_estado` já põe no item da mesa. **Não é o nome de tela**:
    o nome é o que se escreve, o slug é o que se pinta, e casar por
    identificador em vez de por texto foi o que matou as três divergências de
    nome que o bloco acima lista.

    O DONO DO HEXA É `monta.cor_da_zona`, e ele não se digita: ele lê a folha
    que `scripts/gerar_cores_do_dualsense.py` escreveu no SVG a partir do mapa
    dela. Digitar aqui uma tabela de cor seria a segunda verdade que o
    `check_cores_do_dualsense.py` existe para matar — e foi exatamente o que
    esta função fazia até 03/09/2026.

    OS TRÊS CAMINHOS PARA O NEUTRO, e os três são a regra dela (*campo sem
    informação não mostra nada*):

    * **slug vazio** — a cor não foi lida (o leitor não respondeu, ou o código
      de fábrica está fora da tabela de 21 do produto);
    * **slug que o SVG não tem** — modelo que o mapa ganhou e o gerador de cores
      ainda não emitiu. `cor_da_zona` levanta `SystemExit`, que **não** herda de
      `Exception`: por isso o `except` nomeia os dois. A gêmea da `a04` escreve
      só `except Exception` e por isso não segura nada — está anotado lá;
    * **casca sem hexa medido** — OITO dos 28 modelos dela não têm amostra da
      casca (Grey Camouflage, os três Chroma, Ghost of Yōtei, Marathon, Genshin
      Impact e 007 First Light), e a folha os pinta com o pattern
      `url(#hachura-sem-hex)`. **Um `url()` numa borda não é uma cor
      hachurada: é uma declaração INVÁLIDA, e a borda inteira some** — a mesma
      lição que o `.ctl.off` do `aba02.py` já carrega para a `var()` sem valor.
      Quem o peneira é o `tom_para_a_borda`, que devolve `""` para tudo que não
      começa em `#`.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_para_a_borda

    if not slug:
        return BORDA_SEM_COR
    try:
        do_mapa = str(_monta().cor_da_zona(slug))
    except (Exception, SystemExit):
        return BORDA_SEM_COR
    return tom_para_a_borda(do_mapa) or BORDA_SEM_COR


def folha_do_plastico(mesa: list[dict[str, Any]]) -> str:
    """A folha de `--plastico` INTEIRA, montada da mesa VIVA.

    POR QUE UMA FOLHA E NÃO UM CAMPO POR CARD: `--plastico` é propriedade
    personalizada de CSS, e o `escrever` do piloto não tem alvo que a escreva —
    os oito são texto · largura · fundo · valor · html · classe · cor ·
    plástico (`hefesto_vivo.py`), e o `plastico` escreve estilo de LINHA, num
    elemento. Aqui a cor precisa alcançar a caixa E o chip do mesmo assento, que
    é o que um seletor faz e um estilo de linha não.

    ELA SUBSTITUI A FOLHA, não se soma a ela: o `<style data-campo="plastico-css"
    data-hef-alvo="html">` da página nasce com o desenho e o produto troca o
    `innerHTML` inteiro. Por isso o :data:`PISO_DA_FOLHA` vem PRIMEIRO — o
    assento que esta mesa não nomeia tem de cair no neutro, e não sobrar com a
    cor que o desenho deixou ali.

    O ENDEREÇO É O `pref` (`p1`…), e não o `uniq`: é o que o `data-controle` das
    páginas traz, e é a mesma tradução que o piloto faz para as colunas.

    A COR SAI DE `cor`, E NÃO DE `nome` — 03/09/2026. O `cor` é o `id` da linha
    dela (`white`, `galactic-purple`), o mesmo que o chip da fita usa três
    centímetros acima; o `nome` é texto de tela, e casar por texto deixava dez
    dos 28 modelos dela sem borda nenhuma. Ver :func:`cor_da_borda`.
    """
    return "\n".join([PISO_DA_FOLHA] + [
        f'.ctl[data-controle="{c.get("pref")}"],'
        f'.fita .chip[for="c-{c.get("pref")}"]'
        f'{{--plastico:{cor_da_borda(str(c.get("cor") or ""))}}}'
        for c in mesa
        if c.get("pref")
    ])


#: O CLIQUE DO ANALÓGICO — o rótulo dentro do círculo, e ele é ENDEREÇO, não
#: enfeite: `data-campo="l3"` e `data-campo="r3"` estão na página desde o
#: primeiro desenho e, até 02/09/2026, NINGUÉM os pintava.
#:
#: O CLICADO É O RÓTULO ENTRE COLCHETES, e esta é a única escolha de TEXTO DE
#: TELA desta cura — logo, dela. É uma edição de uma linha trocá-la. A razão de
#: ser colchete e não palavra é de medida: o `.rotl` é JetBrains Mono 26px
#: dentro de um círculo de 100px — cabem quatro caracteres (4 x ~15,6px = 62px),
#: e não cabe "Clicado".
#:
#: POR QUE NÃO A COR, que é o que o produto faz: o dono na GTK
#: (`app/widgets/controller_card.py:5453-5461`) e o piloto antigo desta aba
#: (`interface/controles_vivos.py:388`) mostram o clique MUDANDO A COR do
#: rótulo.
#:
#: **FATO SUBSTITUÍDO — O PILOTO PASSOU A SABER.** Aqui estava escrito que *"o
#: `escrever` tem cinco alvos — texto, largura, fundo, valor e html — e nenhum
#: é `color`"*. São SETE desde 02/09/2026: `classe` e `cor` entraram
#: (`hefesto_vivo.py:499` e `:537`), e o comentário do `cor` cita exatamente
#: esta linha como a dívida que ele veio pagar. Guardar a frase antiga ao lado
#: da certa obrigaria a próxima pessoa a escolher entre duas afirmações.
#:
#: **A PALAVRA VEIO, E É PARA NÃO MEXER — 02-Q10, 05/09/2026:** *"Continua com
#: colchetes"*. Aqui estava escrito que faltava a decisão dela para trocar o
#: `[L3]` por uma mudança de cor. Não falta mais, e a resposta foi manter o que
#: já está de pé e publicado (`:1956-1963` e `paginas/02-controles.html:1965`).
#: **Zero linha de código muda** — o que mudou foi esta nota, que registra a
#: decisão datada em vez de guardar uma pergunta já respondida. Pergunta viva
#: num arquivo é como a próxima pessoa refaz um trabalho que ninguém pediu.
ROTULO_DO_CLIQUE = {"l": "L3", "r": "R3"}
CLICADO = "[%s]"

# ---------------------------------------------------------------------------
# A BARRA DE LUZ — as CINCO situações do motor, e o valor que cada uma mostra
# ---------------------------------------------------------------------------
# `rotulo_lightbar` devolve `(rótulo, base_do_accent)`, e O DISCRIMINADOR É O
# PRIMEIRO. O segundo responde outra pergunta, e a docstring dele a escreve:
# *"a cor devolvida é a BASE do accent (crua); `None` = usar o neutro"*
# (`controller_card.py:1178`).
#
# TOMAR O SEGUNDO POR "há cor conhecida a mostrar?" COLAPSA DOIS PARES, e a
# auditoria de 02/09/2026 mediu os dois com sonda, sem tocar o aparelho:
#
#   o motor DIZ                        base    o campo dizia   e devia dizer
#   (sem rótulo) — conhecida e acesa   a cor   #0000FF         #0000FF
#   Em Nativo o jogo é dono do LED     CRUA    #000000         não sei
#   A Steam tem este controle aberto   CRUA    #000000         não sei
#   Lightbar: cor desconhecida         None    —               não sei
#   Lightbar: apagada                  None    —               apagada
#
# NOS DOIS DO MEIO A BASE É O `rgb` CRU (linhas 1183 e 1185 do motor), e com a
# fonte desconhecida esse cru é `[0,0,0]` — exatamente a mentira que o motor
# nomeia: *"o 0,0,0 do sysfs sem escrita nossa pode ser o azul-kernel brilhando
# neste exato momento"*. A GTK mostra a cor COM a ressalva ao lado; aqui a
# ressalva não tem endereço, então mostrar a cor sozinha é afirmar o que
# ninguém mediu. Dizer "não sei" é o que sobra de honesto.
#
# E O ÚLTIMO É UM FATO, NÃO UMA AUSÊNCIA: `lightbar_on` falso com fonte NOSSA é
# um estado que o motor AFIRMA, com frase positiva. Ele recebia o mesmo
# `SEM_LEITOR` que o piloto usa para null/undefined (`hefesto_vivo.py:118`) —
# "não medi" sobre a única coisa aqui que se mediu.

#: O RÓTULO DA BARRA APAGADA — **perguntado ao motor, nunca digitado**.
#:
#: Das quatro frases que `rotulo_lightbar` devolve, só uma é constante exportada
#: (`ROTULO_LIGHTBAR_SEGURADA`). Digitar as outras aqui seria a segunda cópia
#: que a LEI 0 proíbe, e uma cópia MUDA: no dia em que o motor trocasse a frase,
#: esta aba voltaria a colapsar os dois estados sem régua nenhuma reprovar.
#:
#: Então ela se PERGUNTA, com a entrada mínima que só o ramo "apagada" atende —
#: fonte nossa, cor conhecida e não-preta, barra desligada. Quem tranca a
#: pergunta é `test_o_rotulo_da_apagada_e_perguntado_ao_motor`, que cobra que
#: ela seja diferente das outras três.
ROTULO_DA_LUZ_APAGADA = rotulo_lightbar(
    {"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs", "lightbar_on": False}, {}
)[0]

#: O CÓDIGO DE COR DE UMA BARRA DESLIGADA, e ele não é uma opinião: sem corrente
#: nos três canais o que a barra emite é zero em todos eles. O motor devolve
#: `None` como base porque `None` ali quer dizer *"use o neutro no traço do
#: card"* — é resposta de ACCENT, e este campo é o CÓDIGO DA COR.
#:
#: DEPOIS DESTA CURA, `#000000` APARECE AQUI SE E SOMENTE SE A BARRA ESTÁ
#: APAGADA: o ramo da cor conhecida nunca o produz (o motor manda `rgb ==
#: (0,0,0)` para "apagada", linha 1189), e os três ramos de "não sei" mostram o
#: travessão. Antes ele aparecia justamente onde a cor era DESCONHECIDA.
HEX_DA_LUZ_APAGADA = "#000000"


def luz_hex(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """O `luz-hex` a partir do que o motor RESPONDEU — as cinco situações.

    Recebe o par inteiro de `rotulo_lightbar` de propósito: a decisão é do
    rótulo, e passar só a base é o defeito que esta função existe para fechar.
    """
    import mesa_viva

    if rotulo is None and base is not None:
        return "#{:02X}{:02X}{:02X}".format(*base[:3])
    if rotulo == ROTULO_DA_LUZ_APAGADA:
        return HEX_DA_LUZ_APAGADA
    # O `str` é para o `mypy`, que é portão: `mesa_viva` entra por `sys.path` e
    # sem tipagem, então tudo o que vem dele é `Any` — devolver `Any` de uma
    # função declarada `str` reprova com `no-any-return`.
    return str(mesa_viva.SEM_LEITOR)


def _cor_da_barra(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """A cor do RETÂNGULO, do mesmo par que decide o `luz_hex`. `""` = apague.

    O CAMPO E O DESENHO PASSAM A DIZER A MESMA COISA, e é por isso que os dois
    saem da mesma resposta do motor: enquanto o retângulo era pintura do
    gerador, ele afirmava a cor do mockup enquanto o campo ao lado dizia a cor
    viva — ou o travessão.

    "Apagada" mostra PRETO, que é o que uma barra sem corrente emite; os três
    "não sei" mandam vazio, e o vazio devolve o retângulo à folha de estilo em
    vez de inventar uma cor.
    """
    hex_ = luz_hex(rotulo, base)
    return hex_ if hex_.startswith("#") else ""


# ---------------------------------------------------------------------------
# O TRAVESSÃO DA BARRA DE LUZ VIRA PALAVRA — decisão [02], 04/09/2026
# ---------------------------------------------------------------------------
# ATÉ HOJE OS TRÊS "NÃO SEI" DO `luz_hex` COLAPSAVAM NUM TRAVESSÃO SÓ, e os
# três dizem coisas diferentes: em Modo Nativo o LED é do JOGO, com a Steam
# aberta o valor é o que nós PEDIMOS (não o que a barra emite), e a cor
# desconhecida é o sysfs sem escrita nossa. Um `—` para os três apaga a única
# pergunta que a pessoa faz olhando ali: *"por que não vejo a cor?"*.
#
# A DECISÃO DELA: **palavra curta no lugar do travessão, frase inteira no
# hover** — as quatro palavras são dela, e estão no
# `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`, §2, `02-controles`
# [02]: `Jogo` · `Steam` · `Não sei` · `Apagada`.
#
# A FRASE INTEIRA NÃO CABE NO CAMPO, e isso está MEDIDO (ver o comentário do
# `luz-hex` no pintor): a linha que contém o `<span class="de-quem">` mede
# 148px, e "Lightbar: apagada" ocupa 86,7px QUEBRANDO a linha. Palavra cabe,
# frase não — e é por isso que a frase mora no `title`, que não paga pixel.
#
# OS QUATRO RÓTULOS SÃO PERGUNTADOS AO MOTOR, NENHUM DIGITADO. É a mesma
# disciplina do `ROTULO_DA_LUZ_APAGADA` logo acima, e a mesma razão: no dia em
# que `rotulo_lightbar` trocar uma frase, a tabela abaixo deixa de casar e a
# palavra volta a ser o travessão — barulhento, e não calado.

#: "Em Nativo o jogo é dono do LED" — a entrada mínima que só este ramo atende.
ROTULO_DA_LUZ_EM_NATIVO = rotulo_lightbar({}, {"native_mode": True})[0]

#: "A Steam tem este controle aberto" — `lightbar_disputada`, sem Nativo.
ROTULO_DA_LUZ_SEGURADA = rotulo_lightbar({"lightbar_disputada": True}, {})[0]

#: "Lightbar: cor desconhecida" — sem fonte e sem rgb, que é o ramo padrão.
ROTULO_DA_LUZ_DESCONHECIDA = rotulo_lightbar({}, {})[0]

#: A PALAVRA CURTA DE CADA RÓTULO — decisão dela, [02].
#:
#: `Não sei` NÃO É DIGITADO: é `pacotes.NOME_SEM_LEITURA`, a mesma palavra que a
#: fita do topo já usa para um controle sem nome lido. Duas grafias de "não sei"
#: na mesma tela seriam duas traduções do mesmo fato — o que esta casa persegue.
PALAVRA_DA_LUZ: dict[str | None, str] = {
    ROTULO_DA_LUZ_EM_NATIVO: "Jogo",
    ROTULO_DA_LUZ_SEGURADA: "Steam",
    ROTULO_DA_LUZ_DESCONHECIDA: NOME_SEM_LEITURA,
    ROTULO_DA_LUZ_APAGADA: "Apagada",
}

#: A FRASE DO HOVER QUANDO A COR É CONHECIDA — e ela é a do desenho de hoje,
#: movida para cá porque **o texto de tela desta aba mora no pacote** (o
#: cabeçalho do `interface/aba02.py` escreve a lei, e a seta aponta para cá).
#: Ela era um literal do gerador, e o `title` do campo passou a ser PINTADO:
#: com duas cópias, a viva e a do desenho divergiriam na primeira edição.
DICA_DA_LUZ = ("Este é o código da cor do JOGADOR, não a do plástico — quem "
               "escolhe é o produto, pela mesma tabela que acende as cinco "
               "lâmpadas (core/led_control.py::player_slot_color). Ele não é "
               "digitado aqui: sai da tabela, e muda no dia em que ela mudar.")


def luz_palavra(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """O que o campo MOSTRA: o código de cor, ou a palavra curta do estado.

    A cor conhecida continua sendo o hexadecimal — ela é a informação, e
    trocá-la por palavra perderia o que a pessoa foi ali ver. O que muda são os
    três "não sei" e a "apagada", que dividiam um travessão só.

    RÓTULO QUE O MOTOR PASSE A DEVOLVER E ESTA TABELA NÃO CONHEÇA cai no
    travessão de antes, e não numa palavra chutada: o `luz_hex` é o dono do
    desfecho, e esta função só traduz o que ele já decidiu ser "não sei".

    **A TABELA VEM ANTES DO `luz_hex`, e a ordem foi medida.** A "apagada" é o
    único dos quatro estados em que o `luz_hex` devolve um CÓDIGO
    (`HEX_DA_LUZ_APAGADA`, o preto que uma barra sem corrente emite) — decidir
    pelo `#` deixaria justamente ela sem a palavra dela, e ela é uma das quatro
    que o PO nomeou. O preto continua indo para o RETÂNGULO, que é onde ele
    quer dizer alguma coisa: `_cor_da_barra` lê o `luz_hex`, não esta função.
    """
    if rotulo in PALAVRA_DA_LUZ:
        return PALAVRA_DA_LUZ[rotulo]
    return luz_hex(rotulo, base)


def luz_porque(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """A frase inteira, para o `title` da linha da Barra de luz.

    Com a cor conhecida ela é a explicação de quem escolhe a cor
    (:data:`DICA_DA_LUZ`); nos outros quatro estados é a frase que o MOTOR
    devolve, palavra por palavra — é ela que diz por que o código não aparece.

    O `base` entra sem ser lido de propósito: a assinatura é a mesma do
    `luz_palavra` e do `_cor_da_barra`, e os três são chamados lado a lado com
    o par inteiro. Uma assinatura diferente aqui convidaria alguém a passar só
    o rótulo num dos três — que é exatamente o defeito que o `luz_hex` existe
    para fechar.
    """
    return DICA_DA_LUZ if rotulo is None and base is not None else str(rotulo or "")


# ---------------------------------------------------------------------------
# OS DOIS ACESOS QUE A TELA AFIRMAVA SEM LER — 03/09/2026
# ---------------------------------------------------------------------------
# ESTA ABA TEM QUATRO BOTÕES QUE DIZEM "ESTE É O ESCOLHIDO" — os dois da rota
# do alto-falante e os dois do modo do microfone —, e nenhum deles era leitura.
# O aceso era a classe `on` que o GERADOR desenhou, uma vez, no dia em que
# escreveu o arquivo. Medido na mesa dela em 03/09/2026:
#
#   na tela (o desenho)                    no aparelho / no disco
#   card 2: "Todo o som do PC" aceso       speaker.rota = 2  (Sons do jogo)
#   card 1: "Virtual" aceso                maquina.json sem `microfone` (Nativo)
#
# E NO CARD 2 O DESENHO NÃO É NEUTRO: ele afirma que o som INTEIRO do PC está
# saindo naquele controle. Se ela olhar a tela para responder *"por que o som
# não está vindo pelo controle?"*, a tela responde errado.
#
# OS DOIS PARES SÃO O MESMO DEFEITO E TÊM CURAS DIFERENTES, porque os donos são
# diferentes: a rota é do APARELHO (o daemon publica `speaker.rota` a cada
# tique) e o modo do microfone é do DISCO (a declaração dela no `maquina.json`,
# que o `state_full` não ecoa de propósito — ver `SEM_ECO`).


def _bloco_do_speaker(entry: Any) -> dict[str, Any] | None:
    """O bloco `speaker` cru do controle, nas DUAS posições em que ele chega.

    ELE É A SEGUNDA LEITURA DA MESMA REGRA, e isso está declarado em vez de
    escondido: o dono é `speaker_do_entry` (`controller_card.py:1936`), que
    conhece as duas posições — `entry["speaker"]` e `entry["inputs"]["speaker"]`
    — mas devolve só `(volume, muted)`. A ROTA não passa por ele, e alargar a
    assinatura do widget da GTK a partir daqui não é trabalho desta aba.

    O QUE IMPEDE AS DUAS DE DIVERGIREM é régua, não disciplina:
    `test_a_rota_sai_do_mesmo_bloco_que_o_volume` pergunta aos DOIS sobre as
    mesmas entradas e cobra que achem o mesmo bloco — se o daemon mudar de
    posição e só um dos leitores acompanhar, ela reprova nomeando o caso.
    """
    if not isinstance(entry, dict):
        return None
    bloco = entry.get("speaker")
    if not isinstance(bloco, dict):
        dentro = entry.get("inputs")
        bloco = dentro.get("speaker") if isinstance(dentro, dict) else None
    return bloco if isinstance(bloco, dict) else None


#: O BYTE DA ROTA → O NOME DO BOTÃO NA PÁGINA. **Os bytes são perguntados**, e
#: o dono deles é o mesmo par que a GTK usa para estes dois botões:
#: `ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]` e `ROTA_DO_CANAL[CANAL_TODO_O_PC]`
#: (`controller_card.py:716`), que por sua vez saem de
#: `core/ds_output_report.py:136-137`. Digitar `2` e `3` aqui seria a régua que
#: envelhece no dia em que o protocolo mudar de número.
#:
#: O QUE SE TRADUZ É SÓ O NOME: a GTK chama o segundo canal de `"tudo"` e o
#: `data-rota` da página o chama de `"pc"` — a página é mais velha que a
#: constante, e o gesto `rota` desta mesma aba já fala `'jogo'`/`'pc'`. Trocar o
#: vocabulário da página é desenho, logo decisão dela.
NOME_DO_BOTAO_DA_ROTA: dict[int, str] = {
    ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]: "jogo",
    ROTA_DO_CANAL[CANAL_TODO_O_PC]: "pc",
}


def rota_na_tela(entry: Any) -> str:
    """O que a CAMADA 2 (o byte do firmware) diz: `"jogo"`, `"pc"` ou `""`.

    **ELA É METADE DA RESPOSTA, e a outra metade decide** — 04/09/2026,
    decisão [09] desta aba. O que a tela ACENDE sai de :func:`aceso_da_rota`,
    que junta esta leitura com a camada 1 (a saída padrão do PipeWire). Esta
    função continua existindo porque o byte é um fato próprio, com dono
    próprio, e quem compõe as duas precisa de cada uma separada — foi assim
    que a ONDA1-D1 escreveu `audio_saida.botao_da_rota_aceso`, que é o dono da
    composição.

    `""` É "NÃO SEI", E ELE APAGA OS DOIS. O piloto escreve o travessão para
    valor vazio, e no alvo `classe` com `data-hef-quando` nenhum dos dois casa
    com `—`: os dois botões ficam apagados, que é o que a tela pode afirmar
    quando o daemon nunca publicou `speaker` para este controle — o estado real
    de quem nunca recebeu um `speaker.set` (`ipc_handlers.py:4659`).

    ELE TAMBÉM APAGA OS DOIS NAS ROTAS 0 E 1 (tudo no fone, mono no fone), e
    isso é de propósito: são rotas legítimas do protocolo que estes dois botões
    não representam. Acender um deles ali seria arredondar o byte para o botão
    mais parecido.
    """
    bloco = _bloco_do_speaker(entry)
    if bloco is None:
        return ""
    rota = bloco.get("rota")
    if isinstance(rota, bool) or not isinstance(rota, int):
        return ""
    return NOME_DO_BOTAO_DA_ROTA.get(rota, "")


def _byte_da_rota(entry: Any) -> int | None:
    """O `speaker.rota` cru — `None` quando o daemon nunca o publicou."""
    bloco = _bloco_do_speaker(entry)
    if bloco is None:
        return None
    rota = bloco.get("rota")
    return None if isinstance(rota, bool) or not isinstance(rota, int) else rota


# ---------------------------------------------------------------------------
# A CAMADA 1 DA ROTA — o que o PipeWire diz, num relógio próprio
# ---------------------------------------------------------------------------
# O CARD 2 DELA ACENDIA "TODO O SOM DO PC" COM O SOM NA TV, medido em
# 03/09/2026. A causa está escrita no motor: *"a camada 1 vence a camada 2 —
# volume e rota perfeitos num sink mudo é trabalho invisível"*
# (`controller_card.py:4218`). O byte é a camada 2; quem decide ONDE o som sai
# é a saída padrão do sistema.
#
# POR QUE NÃO NO TIQUE: `audio_saida.ler_as_duas_camadas` roda `pactl` — dois
# subprocessos por controle. A dez tiques por segundo, com quatro controles na
# mesa, seriam 80 subprocessos por segundo na máquina dela. A leitura vive num
# CACHE com relógio próprio e uma thread que o renova, que é a mesma forma da
# `a09_sistema._faixa_lenta` (e a mesma razão: *"a primeira leva 18 ms"* lá,
# aqui bem mais).
#
# E A PRIMEIRA LEITURA É SÍNCRONA de propósito. Devolver "não sei" até uma
# thread voltar faria os dois botões apagarem no primeiro tique e acenderem no
# segundo — a tela piscando sobre um fato que não mudou. Quem paga é a primeira
# pintura da aba, uma vez por abertura.

#: De quanto em quanto tempo a camada 1 se relê. Dois segundos é o mesmo ciclo
#: que o `canal_do_microfone_loop` do daemon usa para a mesma família de
#: pergunta (o PipeWire), e pela mesma razão: é leitura de sistema, não de
#: quadro.
CAMADA_1_S = 2.0

#: `{uniq: RotaDasDuasCamadas}` — o que a última leitura disse, por controle.
_CAMADA_1: dict[str, Any] = {}
_CAMADA_1_QUANDO = [0.0]
_CAMADA_1_EM_VOO = [False]


def _ler_a_camada_1(entradas: tuple[tuple[str, int | None], ...],
                    na_mesa: tuple[str, ...]) -> dict[str, Any]:
    """A camada 1 de cada controle da mesa. BLOQUEANTE — roda `pactl`.

    `entradas` é `(uniq, byte)` porque o byte **não se relê aqui**: quem o
    publica é o daemon, e uma segunda leitura seria a segunda verdade. É o
    contrato que `audio_saida.ler_as_duas_camadas` escreve com todas as letras.
    """
    lido: dict[str, Any] = {}
    for uniq, byte in entradas:
        if not uniq:
            continue
        try:
            lido[uniq] = audio_saida.ler_as_duas_camadas(uniq, byte, list(na_mesa))
        except Exception:
            # UMA LEITURA QUE FALHA NÃO APAGA AS OUTRAS, e não vira `False`:
            # a chave simplesmente não entra, e quem pergunta recebe "não sei".
            continue
    return lido


# ---------------------------------------------------------------------------
# A TERCEIRA LEITURA DA MESMA VOLTA — o SONO do canal (linha 90 da paridade)
# ---------------------------------------------------------------------------
# O DONO NA JANELA GTK é o método do card que recebe o estado do canal de FORA
# (`controller_card`, o par `estado` + `regra_instalada`), e ele NÃO vai ao
# sistema por conta própria: quem lê o PipeWire lá é a `status_actions`, uma vez
# por ciclo, para todos os cards. Aqui a disciplina é a mesma e o lugar já existia — o
# `renovar` da `_camada_1`, que já paga um `pactl` a cada dois segundos. Uma
# thread nova para a mesma família de pergunta seria o segundo leitor de
# PipeWire desta aba, que é a classe de defeito que a `_camada_1` inteira existe
# para não cometer.
#
# SÃO DOIS FATOS, e a diferença é a metade que importa (SOM-ACORDADO-01): o
# ESTADO diz se o nó está acordado AGORA; a REGRA (o drop-in 54 do WirePlumber)
# diz se ele está acordado POR PADRÃO. Um nó pode estar acordado por acaso —
# alguém acabou de tocar algo — com a cura fora do lugar, e chamar isso de "é o
# padrão" seria a tela dando por curado o que só está momentaneamente de pé.

#: `{uniq: acordado|dormindo}` — o que a última volta disse, por controle. `""`
#: e a chave AUSENTE são a mesma coisa: **não sei**. É o caso do rádio, em que o
#: DualSense não publica placa ALSA nenhuma (medido em 15/08/2026 — a placa
#: segue o transporte), e o do controle desligado no cabo.
_SONO: dict[str, str] = {}

#: O drop-in 54 está no lugar? `None` = ninguém perguntou ainda, e `None` é o
#: que faz a dica não afirmar nem um nem outro.
_REGRA_DO_SONO: list[bool | None] = [None]


def _ler_o_sono(lido: dict[str, Any]) -> dict[str, str]:
    """`{uniq: acordado|dormindo}` de quem tem sink. BLOQUEANTE — roda `pactl`.

    UM `pactl` PARA A MESA INTEIRA, e não um por controle: a lista curta traz
    todos os sinks de uma vez, e quem separa "este sink é de um DualSense" já
    tem dono (`audio_saida`, por `mic_monitor.sinks_dualsense`). O que se
    pergunta aqui é o ESTADO de um sink que a camada 1 já resolveu.

    QUEM DECIDE A PALAVRA É `audio_saida.estado_do_canal` — o dono do parser da
    coluna e da tradução `RUNNING`/`IDLE`/`SUSPENDED`. Reescrever a leitura aqui
    seria o segundo vocabulário para o mesmo fato, na mesma tela.

    SEM SINK NÃO ENTRA CHAVE. Um `""` gravado para o controle do rádio seria
    indistinguível de "li e não reconheci"; a ausência é o "não sei" honesto.
    """
    if not lido:
        return {}
    try:
        saida = audio_saida.rodar_leitura(["pactl", "list", "sinks", "short"])
    except Exception:
        # UMA LEITURA QUE FALHA NÃO INVENTA ESTADO: o cache fica vazio e a tela
        # cala, que é a mesma regra do `_ler_a_camada_1` logo acima.
        return {}
    fora: dict[str, str] = {}
    for uniq, rota in lido.items():
        sink = getattr(rota, "sink_do_controle", "")
        if sink:
            fora[uniq] = audio_saida.estado_do_canal(saida, sink)
    return fora


def sono_do_canal(uniq: str) -> str:
    """`"acordado"`, `"dormindo"` ou `""` para UM controle — do cache."""
    return _SONO.get(uniq, "") if uniq else ""


def regra_do_sono() -> bool | None:
    """O drop-in 54 está instalado? `None` enquanto ninguém tiver perguntado."""
    return _REGRA_DO_SONO[0]


def _camada_1(entradas: tuple[tuple[str, int | None], ...],
              na_mesa: tuple[str, ...]) -> dict[str, Any]:
    """O cache da camada 1, renovado em THREAD a cada :data:`CAMADA_1_S`.

    **NUNCA SÍNCRONO, nem na primeira vez** — e a primeira redação desta função
    era, o que estava errado por dois motivos que apontam para o mesmo lado:

    * quem chama é o pintor, e o pintor roda no laço principal da GTK a 10 Hz.
      Um `subprocess` ali TRAVA a janela dela — é exatamente por isso que o
      `ipc_bridge.run_in_thread` existe, e a ONDA1-D1 escreveu com todas as
      letras que esta leitura *"é bloqueante: quem chama é `run_in_thread`"*;
    * numa suíte de teste, uma primeira leitura síncrona faria toda régua que
      chama `pacote()` conversar com o PipeWire da máquina dela.

    O QUE ISSO CUSTA, e o preço está declarado: nos primeiros tiques o cache
    está vazio e `aceso_da_rota` cai no BYTE — a resposta de antes desta cura,
    por ~2 s. É menos honesto que a resposta inteira e é mais honesto que
    apagar os dois botões afirmando uma ignorância que dura dois segundos.

    **ELE É O PONTO DE INJEÇÃO DAS RÉGUAS**, como o `_LENTO` da `a09_sistema`:
    quem quiser medir o desacordo das duas camadas escreve em `_CAMADA_1` e não
    espera thread nenhuma — uma régua que dependesse de um relógio seria uma
    corrida, e corrida na suíte é vermelho que aparece uma vez em dez.
    """
    import threading
    import time

    if not na_mesa or _CAMADA_1_EM_VOO[0]:
        return _CAMADA_1
    agora = time.monotonic()
    if _CAMADA_1_QUANDO[0] and agora - _CAMADA_1_QUANDO[0] < CAMADA_1_S:
        return _CAMADA_1
    _CAMADA_1_EM_VOO[0] = True
    # O RELÓGIO ANDA AGORA, e não quando a thread voltar: com a leitura levando
    # mais que o intervalo, marcar no fim faria o pintor disparar uma thread por
    # tique — dez `pactl` por segundo, que é o oposto do que esta função existe
    # para evitar. O `_CAMADA_1_EM_VOO` já impede a segunda; isto impede que a
    # primeira volte a ser "devida" antes de a próxima janela abrir.
    _CAMADA_1_QUANDO[0] = agora

    def renovar() -> None:
        try:
            novo = _ler_a_camada_1(entradas, na_mesa)
            # O SONO VEM NA MESMA VOLTA, e depois da camada 1 porque é dela que
            # sai o sink de cada controle. A regra do WirePlumber é um `isfile`
            # e mora aqui pela mesma razão que o resto: o pintor roda a 10 Hz, e
            # quatro `stat` por tique é trabalho de disco por nada.
            sono = _ler_o_sono(novo)
            try:
                regra = audio_saida.regra_nunca_dorme_instalada()
            except Exception:
                regra = None
            _CAMADA_1.clear()
            _CAMADA_1.update(novo)
            _SONO.clear()
            _SONO.update(sono)
            _REGRA_DO_SONO[0] = regra
        finally:
            _CAMADA_1_EM_VOO[0] = False

    threading.Thread(target=renovar, name="hefesto-rota-camada-1",
                     daemon=True).start()
    return _CAMADA_1


# ---------------------------------------------------------------------------
# AS ONDAS SONORAS — o que ENTRA e o que SAI, medido
# ---------------------------------------------------------------------------
# Pedido dela, 05/09/2026: *"ondas sonoras do auto falante e do microfone devem
# ser reais na aba controle. sobre o audio que entra e o que sai"*.
#
# QUEM MEDE É `integrations/ondas_de_som.py`, e ele tem relógio próprio pela
# mesma razão da `_camada_1` logo acima: a leitura é de SISTEMA, não de quadro.
# A diferença é que ali a thread refaz um `pactl` a cada dois segundos e aqui um
# fluxo fica ABERTO entregando 100 bytes por segundo — o custo no tique é copiar
# catorze inteiros.
#
# ESTE ARQUIVO NÃO ESCOLHE NÓ NENHUM. Os dois endereços já têm dono, e nenhum
# custa uma leitura nova:
#
#   entra -> `entry["audio"]["canal_fonte"]`, publicado pelo daemon;
#   sai   -> `_CAMADA_1[uniq].sink_do_controle` + `.monitor`, que a camada 1
#            desta mesma aba já renova a cada dois segundos.

#: Os dois lados, com o prefixo que o gerador usa nos `data-campo`.
LADO_MIC = "mic"
LADO_ALTO = "alto"


def no_do_microfone(entry: Any) -> str:
    """A source do microfone deste controle, ou ``""`` quando não há.

    `""` é a resposta CERTA para o controle no rádio: a ponte BT publica o mic
    como Opus tunelado em HID e o PipeWire não tem nó nenhum para ele até a
    ponte subir. Inventar um nome faria o medidor abrir `parec` numa fonte de
    outra pessoa.

    **O `audio` VEM PRIMEIRO, e a ordem foi medida.** O daemon publica
    `canal_fonte` em TRÊS posições no mesmo controle — `audio`, `speaker` e
    `inputs.speaker` (conferido no `state_full` da mesa dela em 05/09/2026) —, e
    `audio` é a casa dele: é o bloco do MICROFONE, que é de quem esta fonte é.
    As outras duas ficam como recuo, pela mesma razão que `_bloco_do_speaker`
    aceita duas: *"quem publica é o daemon, e o widget não pode quebrar por
    causa de onde o dado mora"*.
    """
    if isinstance(entry, dict):
        bloco = entry.get("audio")
        if isinstance(bloco, dict):
            fonte = bloco.get("canal_fonte")
            if isinstance(fonte, str) and fonte:
                return fonte
    recuo = _bloco_do_speaker(entry) or {}
    fonte = recuo.get("canal_fonte")
    return str(fonte) if isinstance(fonte, str) and fonte else ""


def sink_do_cache(uniq: str) -> str:
    """O sink de SAÍDA deste controle, do cache da camada 1. ``""`` = não sei.

    **NUNCA LÊ O SISTEMA**, e é por isso que ela pode ser chamada do tique: o
    `pactl` que preenche o cache roda na thread de :func:`_camada_1`, a cada
    dois segundos. Quem precisa da resposta mesmo com o cache frio, e pode
    pagar por ela, é o som de confirmação — ver :func:`_sink_para_o_som`.
    """
    lida = _CAMADA_1.get(uniq)
    return str(getattr(lida, "sink_do_controle", "") or "") if lida else ""


def no_do_alto_falante(uniq: str) -> str:
    """O ``.monitor`` do sink deste controle, ou ``""`` quando não se sabe.

    **O MONITOR É O ÚNICO LUGAR ONDE "O QUE SAI" EXISTE.** Um sink não tem
    nível; o monitor dele é uma source que entrega exatamente o que o servidor
    mandou para o aparelho. Medido em 05/09/2026: abrir o monitor do sink do
    DualSense dela **não** tira o sink do `IDLE` — não custa isócrono nem
    bateria.

    Sai `""` nos primeiros ~2 s de aba (o cache da camada 1 ainda vazio) e numa
    máquina sem `pactl`. Os dois são "não sei", e a tela mostra sem leitura.
    """
    sink = sink_do_cache(uniq)
    return f"{sink}.monitor" if sink else ""


def _seguir_as_ondas(alvos: dict[str, str]) -> None:
    """Diz ao medidor quais nós seguir neste tique. Nunca levanta.

    Uma falha aqui não pode derrubar a pintura da aba: sem medidor as barras
    ficam sem leitura, que é o estado honesto.
    """
    try:
        from hefesto_dualsense4unix.integrations import ondas_de_som

        ondas_de_som.o_de_sempre().seguir(alvos)
    except Exception:  # pragma: no cover - defensivo
        return


def alturas_do_no(no: str) -> tuple[int, ...] | None:
    """As catorze alturas daquele nó, ou ``None`` — *não sei*. Nunca levanta."""
    if not no:
        return None
    try:
        from hefesto_dualsense4unix.integrations import ondas_de_som

        return ondas_de_som.o_de_sempre().alturas(no)
    except Exception:  # pragma: no cover - defensivo
        return None


def campos_da_onda(lado: str, alturas: tuple[int, ...] | None,
                   *, mudo: bool = False) -> dict[str, Any]:
    """Os quinze campos de um medidor: catorze alturas e o selo da leitura.

    O selo (`{lado}-onda-lida`) vale `"sim"` ou o contrário, e o gerador casa
    o contrário com `data-hef-quando` — a classe `sem-leitura` acende nele.
    Os dois são VALORES de atributo, na mesma língua sem acento em que o
    piloto já escreve o `data-conectado`.

    **COM `alturas=None` AS CATORZE SAEM NO PISO, E NÃO VAZIAS.** A primeira
    versão emitia `""`, e a régua do mockup pegou o defeito no mesmo dia: o
    `escrever` leva o vazio a `style.height = '—%'`, **CSS inválido que o CSSOM
    descarta calado** — a altura do DESENHO fica no atributo. A folha ainda
    achatava o pixel pelo selo, mas o arquivo continuava dizendo `95%`, e
    `--prova-de-mockup` acusou as 56 barrinhas como ENDEREÇO MORTO. É
    exatamente o defeito que a barra de bateria do lugar vazio custou a esta aba
    em 03/09, repetido por mim.

    O piso não afirma silêncio: quem diz "não medi" é o selo, e a folha pinta
    essas barras de CINZA. O que o número faz é garantir que a onda do desenho
    saia do atributo — nenhum pixel do arquivo sobrevive à primeira pintura.

    `mudo` ACHATA A ONDA SEM APAGAR A LEITURA, e ele existe por um desacordo
    real entre dois lugares: o `.monitor` do sink mede o que o SERVIDOR mandou
    ao aparelho, e o mudo do alto-falante é um byte de FIRMWARE aplicado depois
    disso. Com o alto-falante mudo o monitor continua entregando a onda do jogo
    — e desenhá-la seria a tela dizendo que sai som de um alto-falante calado.
    O piso continua sendo uma afirmação medida ("nada sai"), e por isso o selo
    permanece `"sim"`: nós SABEMOS, e o que sabemos é que está silencioso.
    """
    if mudo and alturas is not None:
        alturas = tuple([_piso_da_onda()] * len(alturas))
    piso = _piso_da_onda()
    fora: dict[str, Any] = {
        f"{lado}-onda-lida": "sim" if alturas else "nao"}  # (noqa-acento) valor
    for i in range(ondas_barras()):
        fora[f"{lado}-onda-{i}"] = (
            alturas[i] if alturas and i < len(alturas) else piso
        )
    return fora


def _piso_da_onda() -> int:
    """A altura de uma barra em silêncio. O dono do número é `ondas_de_som`."""
    try:
        from hefesto_dualsense4unix.integrations import ondas_de_som

        return int(ondas_de_som.PISO_PCT)
    except Exception:  # pragma: no cover - defensivo
        return 16


def ondas_barras() -> int:
    """Quantas barrinhas um medidor tem. O dono do número é `ondas_de_som`."""
    try:
        from hefesto_dualsense4unix.integrations import ondas_de_som

        return int(ondas_de_som.BARRAS)
    except Exception:  # pragma: no cover - defensivo
        return 14


def aceso_da_rota(uniq: str, entry: Any) -> str:
    """Qual botão de rota a tela pode ACENDER, lendo as DUAS camadas.

    O dono da tabela é `audio_saida.botao_da_rota_aceso`, e ela está escrita
    lá: byte 3 com a saída padrão NESTE controle acende `"pc"`; byte 3 com a
    saída padrão em outro lugar **apaga os dois** e vira recado; byte 2 acende
    `"jogo"`; 0, 1 e ausente apagam os dois.

    SEM A CAMADA 1 LIDA, o que sobra é o byte — e é o que esta função devolve.
    É o estado dos primeiros milissegundos da aba (o cache ainda vazio para
    aquele controle) e o de uma máquina sem `pactl`: melhor mostrar a metade
    que se sabe do que apagar os dois botões afirmando ignorância que não há.
    """
    lida = _CAMADA_1.get(uniq)
    if lida is None:
        return rota_na_tela(entry)
    return str(lida.botao_aceso)


def recado_da_rota(uniq: str) -> str:
    """A frase do cartão quando as duas camadas discordam; `""` quando não.

    Só há UM desacordo que precisa de palavras, e o dono dele é
    `audio_saida.recado_da_rota`: o firmware roteado para "todo o som do PC"
    com a saída padrão do sistema em outro lugar — o estado exato que ela viu
    em 03/09, com o botão aceso e o som na TV.
    """
    lida = _CAMADA_1.get(uniq)
    return "" if lida is None else str(lida.recado)


# ---------------------------------------------------------------------------
# O SELO DO MICROFONE DIZ O ESTADO COMPOSTO — decisão [03], conflito C-2
# ---------------------------------------------------------------------------
# A D-12 DELA, verbatim: *"o botão é pra ligar o microfone e ele ser ouvido no
# canal específico dele"*. Sob esse conceito não há duas camadas a conciliar: o
# microfone deste controle está no ar quando o firmware NÃO o cala **e** o som
# dele chega ao PC pelo canal dele. Um selo que dissesse ATIVO só pelo bit do
# firmware afirmaria captura sobre um controle cujo som não sai em lugar
# nenhum — e foi o que ele fez até hoje.
#
# AS QUATRO FACES, e cada uma tem chave própria no `state_full.audio` desde a
# ONDA1-D1:
#
#   mic_mudo             o PLÁSTICO. O bit que vem em todo report de entrada.
#   mic_mudo_desejado    o que NÓS pedimos. `None` = a posse é do kernel, e
#                        aí o desejo não existe — não é "não sei".
#   canal_ativo          a fonte deste controle é a fonte ATIVA do sistema.
#   canal_mudo           essa fonte está muda no PipeWire.
#
# `mic_da_mesa.eleito` **NÃO ENTRA**, e a razão é medida: a D1 o viu MENTINDO —
# com o canal trocado por fora (`pactl set-default-source`), o `state_full`
# seguiu dizendo `eleito: <uniq>` com o ativo sendo a webcam, porque o
# `EleitorDeMicrofone` só se corrige em gesto. `canal_ativo` é LEITURA; `eleito`
# é memória. Onde os dois divergem, a leitura ganha.
#
# AUSÊNCIA NÃO É `False`. As três chaves de canal são novas e o laço que as
# preenche tem ciclo de 2 s: enquanto ele não perguntou, elas não aparecem.
# `bool(None)` é `False`, e um `False` ali pintaria MUDO sobre um microfone que
# ninguém leu — o gêmeo exato do "Sem toque" e do "0%" que esta aba já matou.

# QUEM DIZ "CALADO" GANHA DE QUEM DIZ "NÃO SEI", e a ordem é essa porque um
# FATO vence uma ausência: com o firmware calado e o canal ainda não lido, a
# resposta é MUDO — não "não sei". O contrário (ausência vencendo fato)
# apagaria o único estado desta tela que se mede sem perguntar ao PipeWire.
def _faces_do_microfone(a: dict[str, Any]) -> tuple[bool, bool]:
    """`(alguma_diz_calado, alguma_nao_foi_lida)` das quatro faces.

    Ela é uma função à parte para poder ser MEDIDA face a face: a régua desta
    aba passa os dezesseis arranjos e cobra o par, o que uma expressão dentro
    do pintor não deixaria fazer sem montar um `state_full` inteiro.
    """
    calado = False
    nao_sei = False

    firmware = a.get("mic_mudo")
    if isinstance(firmware, bool):
        calado = calado or firmware
    else:
        nao_sei = True

    # O DESEJO SÓ FALA QUANDO EXISTE: `None` é "a posse é do kernel", que é um
    # fato sobre QUEM MANDA e não sobre o mudo. Tratá-lo como ausência faria a
    # mesa dela inteira dizer `—`, porque `mic_mudo_desejado: null` é o estado
    # dos dois controles dela agora.
    desejado = a.get("mic_mudo_desejado")
    if isinstance(desejado, bool):
        calado = calado or desejado

    canal = a.get("canal_ativo")
    if isinstance(canal, bool):
        calado = calado or not canal
    else:
        nao_sei = True

    mudo_do_canal = a.get("canal_mudo")
    if isinstance(mudo_do_canal, bool):
        calado = calado or mudo_do_canal
    elif "canal_mudo" in a:
        # `None` DENTRO da chave é o que o daemon devolve quando não há fonte
        # para perguntar (`hotkey.py:929`) — "não consegui ler", e não "está no
        # ar". A chave AUSENTE é o mesmo desfecho por outro caminho.
        nao_sei = True
    else:
        nao_sei = True

    return calado, nao_sei


def selo_composto(a: dict[str, Any]) -> str:
    """ATIVO · MUDO · — pelas QUATRO faces, e ATIVO só quando elas concordam.

    A palavra é do MESMO dono de sempre — `mesa_viva.selo_do_mic` —, e é ele
    que escreve as três; o que esta função faz é decidir QUAL. Escrever
    "ATIVO" aqui seria a segunda gramática para o par de palavras que a tela
    inteira já usa, a dois blocos de distância.
    """
    import mesa_viva

    calado, nao_sei = _faces_do_microfone(a)
    if calado:
        return str(mesa_viva.selo_do_mic(True, True))
    if nao_sei:
        return str(mesa_viva.selo_do_mic(False, False))
    return str(mesa_viva.selo_do_mic(False, True))


# ---------------------------------------------------------------------------
# O BOTÃO AVISA ANTES DO CLIQUE — decisão [04] (D-03), 04/09/2026
# ---------------------------------------------------------------------------
# ELA DESCOBRIA A RECUSA DEPOIS DE CLICAR, e essa é a queixa inteira: o 🎙 e o
# ♪ ficavam da mesma cor de sempre, ela clicava, e só então a frase caía no
# cartão. A D-03: *"Cinza antes, com a razão na dica."*
#
# A CONDIÇÃO **NÃO SE ESCREVE AQUI** — ela é a mesma que o GESTO usa para
# levantar, e é do motor: `acao_mic` e `acao_speaker_mudo`
# (`app/widgets/controller_card.py`) são os donos dos estados destes dois
# botões, e `sensivel=False` é exatamente o estado em que a GTK os deixa
# cinza. Uma cópia da pergunta faria a tela apagar um botão que o gesto aceita
# — ou pior, deixar aceso um que ele recusa, que é a doença de origem.
#
# MEDIDO NESTA LEVA, e é por isso que a régua morde nos DOIS lados: com a
# condição copiada, arrancar a cura do gesto passava VERDE. É a mesma cicatriz
# que o `mic-modo` desta aba já carrega, escrita no gesto dele.


#: POR QUE O ♪ ESTÁ CINZA, na frase que aponta para a saída. Ela mora no
#: PACOTE porque **o texto de tela desta aba mora no pacote** — a lei está no
#: cabeçalho do `interface/aba02.py`, e o gerador a importa daqui para o
#: `title`. Enquanto ela era literal do gerador, o botão apagado dizia uma
#: coisa no desenho e o `?` diria outra na tela viva.
DICA_ALTO_SEM_POSSE = ("Apagado porque o volume deste alto-falante ainda é "
                       "desconhecido: o DualSense não o publica, e o daemon "
                       "recusa calar sem ele. Arraste o volume ao lado uma vez "
                       "e ele destrava.")

#: "NÃO HÁ O QUE DIZER", dito de um jeito que a folha da casa sabe APAGAR.
#:
#: **É CÓPIA DECLARADA de `interface/monta.NADA_A_DIZER`**, e a cópia existe
#: por uma razão estrutural, não por descuido: `monta.py` é BANCADA — importá-lo
#: de dentro de um pacote arrasta o gerador para o fecho de produção, e o
#: `portao_a_casa_sabe_e_o_produto_nao_faz` já reprovou exatamente isso em
#: 02/09/2026, nomeando três lápides daquele arquivo que viraram alcançáveis.
#:
#: QUEM IMPEDE AS DUAS DE DIVERGIREM É RÉGUA, e é a mesma disciplina que a
#: ONDA0-F já aplicou à terceira cópia (`a06_navegacao.py`): o teste desta aba
#: importa `monta` — que ele PODE, porque teste não é fecho de produção — e
#: compara os dois literais.
#:
#: E O MARCADOR É NECESSÁRIO: `escrever()` troca valor vazio por travessão para
#: TODOS os alvos, o `html` incluído (`hefesto_vivo.py:245`), então mandar `""`
#: numa ressalva escreve um `—` solto onde não há nada a dizer.
NADA_A_DIZER = '<i class="nada"></i>'


def porques_do_som(entry: Any) -> dict[str, str]:
    """`{"mic-porque": …, "alto-porque": …}` — vazio quando o botão está vivo.

    **A do ♪ NÃO é a do motor, e a diferença está medida.** O
    `DICA_SPEAKER_SEM_DADO` da GTK manda *"use o controle deslizante primeiro"*,
    e até 04/09/2026 esta janela não tinha deslizante nenhum — mandar alguém a
    um controle que não está na tela é pior que não dizer nada. **Hoje ele
    existe** (D-08, o `<input type="range">` dos dois blocos), então a frase
    daqui aponta para ELE, que é o que destrava o botão: é a mesma frase que o
    gerador já escrevia no `title` desde 03/09 (`DICA_ALTO_SEM_POSSE`), e
    escrevê-la nos dois lugares seria a segunda cópia — o gerador passa a
    importá-la daqui.

    **O "DEVOLVER" FICA FORA, E É A DICA QUE DIZ O PREÇO — decisão [06].** É a
    decisão dela de 31/08 sobre o gêmeo (o "Liberar" do microfone): *"o botão
    do Controle sempre controla a interface, por isso não faz sentido o liberar
    ali"*. O preço do ♪ é menor que o do 🎙 e continua sendo um preço — quem
    diz isso é o `title` do botão, e ele mora no gerador, ao lado do rótulo que
    explica.
    """
    # SEM ENDEREÇO, A RAZÃO É OUTRA, E ELA VEM PRIMEIRO — linha 57 da paridade.
    # `uniq_do_entry` é o dono da regra de identidade na GTK (`""` e `"   "`
    # valem `None` de propósito: um endereço em branco viaja no IPC como "sem
    # alvo" e o daemon cai no PRIMÁRIO). Perguntar aqui, e não escrever um
    # `entry.get("uniq")` novo, é o que impede a terceira cópia da mesma regra.
    #
    # POR QUE ELA GANHA DA RAZÃO DA POSSE: sem endereço, o deslizante que a
    # frase da posse manda arrastar aplicaria no controle errado. Dizer "arraste
    # o volume ao lado" nesse estado é mandar alguém fazer o estrago.
    if uniq_do_entry(entry) is None:
        return {"mic-porque": DICA_AUDIO_SEM_ENDERECO,
                "alto-porque": DICA_AUDIO_SEM_ENDERECO}
    do_mic = acao_mic(entry)
    do_alto = acao_speaker_mudo(entry)
    return {
        "mic-porque": "" if do_mic.sensivel else str(do_mic.dica),
        "alto-porque": "" if do_alto.sensivel else DICA_ALTO_SEM_POSSE,
    }


# ---------------------------------------------------------------------------
# OS TRÊS SELOS DO SOM — linhas 57, 89 e 90 da paridade
# ---------------------------------------------------------------------------
# Todos LIDOS de estado que já existe, e nenhum reescreve a regra do dono:
#
#   `selo_do_som`         a prioridade de `_aplicar_selo_do_som` na GTK
#   `sufixo_do_canal`     o sufixo de `_titulo_do_speaker`
#   `dica_do_canal`       as frases de `_frases_do_canal`
#
# HOUVE UM QUARTO, e ele saiu da tela em 07/09/2026 — ver o bloco "O QUARTO
# SELO SAIU DA TELA", algumas telas abaixo. Os três que ficam falam de ESTADO
# (a saída muda, o canal dormindo, a rota em desacordo); o que saiu falava de
# uma capacidade que ainda devemos, e é a linha que ela traçou.


def selo_do_som(saida_muda: bool | None, sono: str) -> str:
    """O selo do bloco: a camada 1 primeiro, o canal depois, nada por fim.

    A PRIORIDADE NÃO É ARBITRÁRIA, e é a mesma da GTK: ganha o fato que explica
    o silêncio ANTES do outro. **Uma saída muda cala o som venha o canal de onde
    vier; um canal dormindo só come o começo.** Dizer as duas coisas na mesma
    linha seria trocar um alarme por dois avisos.

    SÓ `True` ACENDE O PRIMEIRO. `False` (a saída está aberta) e `None` (não
    sabemos) mostram a mesma coisa — nada —, porque um selo "saída viva" seria
    ruído em cima do que a barra já diz.

    E O SELO SÓ EXISTE NO ESTADO RUIM, ao contrário do sufixo: um selo dizendo
    "acordado" em toda sessão normal gastaria pixel para não informar nada.
    """
    if saida_muda is True:
        return TEXTO_SELO_SAIDA_MUDA
    if sono == audio_saida.CANAL_DORMINDO:
        return TEXTO_SELO_CANAL_DORMINDO
    return ""


def sufixo_do_canal(sono: str) -> str:
    """`"· acordado"`, `"· dormindo"` ou `""` — o sufixo do rótulo da moldura.

    A PALAVRA NÃO SE DIGITA: ela é a que `audio_saida.estado_do_canal` devolveu,
    e é a mesma que a moldura da GTK escreve. O separador é o `·` que o rótulo
    do card já usa entre nome e valor.

    `""` É "NÃO SEI", E NÃO "ACORDADO". Sem placa de som — o caso do rádio — a
    tela não tem o que afirmar, e escrever "acordado" a partir de ausência seria
    prometer que o som sai inteiro num controle que não tem por onde tocá-lo.
    """
    return f"· {sono}" if sono else ""


def dica_do_canal(sono: str, regra: bool | None) -> str:
    """O porquê do canal: o estado, e se ele é o PADRÃO. `""` sem leitura.

    A frase do padrão é condicionada à regra estar instalada, e a condição é a
    metade que importa — ver o bloco `A TERCEIRA LEITURA DA MESMA VOLTA`.
    `None` não afirma nem um nem outro: ninguém perguntou ainda.

    A QUEBRA É `<br><br>` E NÃO `\\n\\n` porque o destino é `innerHTML` — o alvo
    `html` do piloto. A GTK usa `\\n\\n` no `set_tooltip_text`, que é outro
    meio; a frase é a mesma, e as duas vêm do mesmo dono.
    """
    if not sono:
        return ""
    frases = [DICA_CANAL_DORMINDO if sono == audio_saida.CANAL_DORMINDO
              else DICA_CANAL_ACORDADO]
    if regra is True:
        frases.append(DICA_CANAL_E_PADRAO)
    elif regra is False:
        frases.append(DICA_CANAL_SEM_A_REGRA)
    return "<br><br>".join(frases)


# ---------------------------------------------------------------------------
# O QUARTO SELO SAIU DA TELA — 07/09/2026, e a dívida FICOU no mapa
# ---------------------------------------------------------------------------
# ORDEM DELA, e ela vale para a tela inteira, não só para este selo:
#
#     *"O app tem que funcionar e não mostrar na tela que o app não presta. Se
#      não tem como, ok. Testamos e criamos o canal. até lá tudo bem, o layout
#      não informa os nossos defeitos."*
#
# O QUE MORAVA AQUI: uma `Fala` declarada sobre a célula do alto-falante do
# DualSense, lado do rádio, e a função que a lia do mapa e a devolvia ao campo
# `alto-ressalva` do cartão. A frase dizia, na tela dela, que pelo rádio o
# Hefesto ainda não faz o som sair naquele alto-falante — uma CAPACIDADE que
# devemos, confessada no cartão de um controle que funciona.
#
# **A CÉLULA NÃO FOI VIRADA, e virá-la seria mentir ao contrário.** O canal
# continua fechado: `audio.alto_falante@dualsense` segue com `radio_aciona=não`
# e causa `divida`, e é ali que a dívida mora — no mapa, que é de quem
# desenvolve, e não na tela, que é de quem joga. Quem fechar a
# `SOM-QUE-SAI-01` vira a célula; nada aqui precisa mudar junto, porque não há
# mais nada aqui.
#
# O QUE SE PERDE, dito por inteiro: o selo era o exemplo vivo de *"quando a
# célula virar, a tela muda sozinha"* — a leitura do mapa chegando à tela sem
# ninguém tocar em código. O mecanismo continua de pé nos outros três selos
# deste arquivo; o que saiu foi o único que apontava para uma dívida NOSSA, e
# é exatamente essa a linha que ela traçou.
#
# E O QUE FICA NO CAMPO: `recado_da_rota`, que fala do DESACORDO das duas
# camadas de som — um fato de AGORA, que ela desfaz trocando a saída do
# sistema. Estado presente é o que a tela pode dizer; capacidade por entregar,
# não.
#
# O portão que guarda os dois casos é `scripts/check_a_tela_nao_confessa.py`.
# ---------------------------------------------------------------------------


#: A DECLARAÇÃO DELA, do `maquina.json`, lida UMA VEZ e renovada pelo gesto que
#: a muda. É o mesmo padrão — e a mesma razão — do `_DECLARACAO` da
#: `a08_conexoes.py:83`: ler o disco duas vezes por segundo para pintar dois
#: botões é desperdício com nome, e o arquivo só muda por gesto dela.
_DECLARADOS: dict[str, Any] | None = None


def _controles_declarados(recarregar: bool = False) -> dict[str, Any]:
    """O bloco `controles` do `maquina.json`, por endereço normalizado.

    `carregar_maquina` **nunca levanta** — no pior caso devolve o documento
    inteiro em "não sei" —, então o `except` daqui só alcança árvore sem `src`.
    """
    global _DECLARADOS
    if _DECLARADOS is None or recarregar:
        try:
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            _DECLARADOS = dict(carregar_maquina().controles or {})
        except Exception:
            _DECLARADOS = {}
    return _DECLARADOS


def modo_do_mic(endereco: str) -> str:
    """Qual dos dois botões do modo do microfone está aceso.

    A REGRA É A DA GTK, e é uma linha só lá: `meu.get("microfone") is True`
    (`app/actions/config/secao_controles.py:876`), que alimenta o
    `set_active(bool(ligado))` do interruptor (`:584`). `True` e só `True` é
    Virtual; ausência e `False` deixam a ponte no chão do mesmo jeito, e as duas
    são Nativo — que é por que desligar grava `None` e não `False`.

    SEM ENDEREÇO NÃO SE AFIRMA NADA: um controle sem `uniq` normalizado não tem
    linha no `maquina.json`, e escrever "Nativo" ali seria afirmar uma escolha
    que ninguém fez. `""` apaga os dois botões, como na rota.
    """
    if not endereco:
        return ""
    meu = _controles_declarados().get(endereco)
    return "virtual" if getattr(meu, "microfone", None) is True else "nativo"


# ---------------------------------------------------------------------------
# O QUE A PÁGINA PUBLICADA TEM — e por que o pacote precisa perguntar
# ---------------------------------------------------------------------------
# QUATRO ENDEREÇOS DESTA ABA NASCERAM NA BANCADA, e a bancada é dela: o gerador
# (`interface/aba02.py`) escreve em `mockup/`, e o produto só recebe pelo
# `scripts/check_o_desenho_aprovado.py --publicar 02`, que é ATO DELA.
#
# EMITIR ANTES DE ELA PUBLICAR NÃO É INOFENSIVO, e o preço está medido: o
# `casamento.medir("02-controles.html")` compara o que o pacote emite com os
# `data-campo` da página PUBLICADA, e toda chave a mais entra em `orfaos`.
# **QUEM REPROVA É `test_o_clique_do_analogico_tem_dono::test_a_aba_controles_
# nao_emite_para_endereco_que_a_pagina_nao_tem`** — medido na mordida de
# 02/09/2026, e a primeira redação desta linha dizia `test_o_casamento_das_dez`,
# que é FALSO: aquele só cobra `casam >= piso` e `casam != 0`, e passou verde
# com os quatro órfãos na mesa. Pior que a régua: o pacote contaria os quatro em
# `cobertura.pintados` e se reportaria pintando o que não pinta, que é
# exatamente o defeito que o casamento nasceu para pegar (13 relatados, 10
# pintados, em 01/09/2026).
#
# ENTÃO ELE PERGUNTA À PÁGINA, uma vez, e o dia em que ela publicar liga os quatro
# sem ninguém tocar em código. É o mesmo padrão que a `03-gatilhos` já usa
# (`a03_gatilhos._enderecos_da_pagina`), e `publicado=True` é deliberado: o
# piloto abre SEMPRE o publicado (`hefesto_vivo.py:2010`, `:2766`, `:2963`), e
# contar as casas da bancada endereçaria o que o `WebView` não tem.
#: O NOME DA PÁGINA, e ele é UM só neste arquivo: a régua dos gestos o lê lá
#: embaixo, o `_enderecos_da_pagina` o lê aqui, e o `@registrar` o repete porque
#: o decorador roda antes de qualquer coisa que este módulo defina.
PAGINA = "02-controles.html"

def texto_da_bateria(pct: int | None) -> str:
    """A carga na grafia da GTK, PERGUNTADA a ela — as duas frases.

    DECISÃO DELA, 03/09/2026, sobre a bateria desconhecida: **"— %", como a
    janela antiga** — paridade literal com a GTK.

    O QUE CADUCOU, e é decisão medida, por isso fica escrito: em 02/09 esta
    linha passou a devolver o travessão SECO (`mesa_viva.SEM_LEITOR`), pela
    regra de *campo sem informação não mostra nada* e para casar com o
    `alto-estado` e o `touch-estado`, ao lado. Ela decidiu o contrário — a
    paridade com a janela que ela usa vence a harmonia interna do card —, e a
    decisão é dela.

    FATO SUBSTITUÍDO — o comentário que morava aqui dizia *"NÃO HÁ FUNÇÃO DONA
    PARA IMPORTAR … os dois lugares da GTK são literais dentro de métodos de
    widget"*. É falso: `StatusActionsMixin._bateria_da_mesa` é `@staticmethod`,
    devolve `(fração, texto)` e não toca em `self` nem em widget nenhum —
    importá-la não puxa janela. Medido em 03/09: `_bateria_da_mesa({})` dá
    `(0.0, "— %")` e `_bateria_da_mesa({"battery_pct": 85})` dá `(0.85, "85 %")`.

    E É POR ISSO QUE ELA É CHAMADA, E NÃO COPIADA — regra da casa: quando um
    valor tem dono, a régua PERGUNTA ao dono. Uma cópia da `f-string` daqui
    envelhece na primeira vez que a GTK mudar a grafia, e o card volta a mostrar
    duas gramáticas — que é exatamente o defeito que 03/09 curou de manhã.

    O ESTADO SINTÉTICO É DE PROPÓSITO: passar `{"battery_pct": pct}` sem a chave
    `controllers` deixa `mesa_publicada` falso, então a guarda de "quem está na
    mesa" (que é da aba Status, sobre o estado GLOBAL) não corre. Quem decide se
    ESTE controle está na mesa, aqui, é `mesa_viva.mesa_do_estado` — o card só
    existe porque o controle está nela. O que se pede à GTK é a GRAFIA.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    return StatusActionsMixin._bateria_da_mesa(
        {} if pct is None else {"battery_pct": pct})[1]


# ---------------------------------------------------------------------------
# O ESTADO DE CARGA AO LADO DO PERCENTUAL — BATERIA-ICONE-01, 06/09/2026.
#
# DECISÃO DELA, verbatim, e ela é DUAS coisas numa frase:
#
#     "icone mas no radio ele pode tá carregando tambem."  # noqa-acento: citação literal dela
#
# A primeira é a forma: **ícone, não palavra** — o card já tem o número, e uma
# palavra ao lado dele custaria largura que a linha fechada não tem.
#
# A SEGUNDA É UMA CORREÇÃO DE PREMISSA, e é a razão desta sprint existir. As
# três opções que lhe foram oferecidas estavam escritas como se CARREGAR fosse
# coisa do cabo e o rádio fosse sempre descarregar. **Não é**: um DualSense
# falando por rádio pode estar num cabo de energia — o transporte diz por onde
# ele CONVERSA, e a carga diz por onde entra ENERGIA. São dois fatos, e o
# aparelho os publica separados: o transporte sai de `_detect_transport` e a
# carga sai do nibble alto de `states[53]`, o MESMO byte do percentual, que a
# `pydualsense` já corrige de offset no rádio (`readInput`, `states =
# inReport[1:]` quando BT). Nada aqui pode inferir um do outro.
#
#: A PALAVRA DE TELA DE CADA ESTADO, e as chaves NÃO se digitam: `carga_na_tela`
#: as confere contra `backend_pydualsense.ESTADO_DE_CARGA`, que é o dono. Um
#: sexto estado que o kernel publique e esta tabela não conheça reprova a régua
#: `test_a_bateria_diz_carregando_no_radio` em vez de sumir calado da tela.
#:
#: **`descarregando` NÃO GANHA ÍCONE, e a ausência é a decisão**: o número ao
#: lado já diz a carga caindo, e um ícone em todo card o tempo todo é ruído
#: crônico — é a mesma razão pela qual o `giro-no-jogo` desta aba se APAGA sem
#: frase, em vez de acusar "sem giroscópio" nos quatro.
#:
#: **`fora_de_faixa` E `erro` GANHAM, e ganham o MESMO ícone** — o de atenção.
#: A razão é medida, não simétrica: o `hid-playstation` zera a capacidade nos
#: dois casos (`0xa`, `0xb`, `0xf` → `capacity = 0`) enquanto a `pydualsense`
#: continua calculando `nibble*10+5` do mesmo byte. **O percentual que o card
#: mostra nesses dois estados é um número que o driver já descartou** — calar
#: ali deixaria a tela afirmando uma carga que ninguém sustenta, que é o defeito
#: exato que a BATERIA-PARADA-01 curou do outro lado. Dois estados, um ícone,
#: porque para quem olha o card a consequência é uma só: *não confie no número,
#: a carga não está acontecendo*. O que os separa é a palavra.
_NA_TELA_POR_CARGA: dict[str, str] = {
    "descarregando": "",
    "carregando": "Carregando",
    "cheio": "Cheio",
    "fora_de_faixa": "Fora de faixa",
    "erro": "Erro de carga",
}

_ESTADOS_DO_DONO: frozenset[str] | None = None


def estados_de_carga() -> frozenset[str]:
    """As palavras que o DAEMON publica em `battery_state` — lidas do dono.

    `backend_pydualsense.ESTADO_DE_CARGA` é a tradução do nibble alto do byte de
    bateria, e ela é a lista inteira. Digitá-la aqui seria a segunda cópia da
    mesma tabela, e a segunda divergiria no dia em que o kernel ganhasse um
    sexto valor — que é o defeito que esta casa chama de *régua que mede o mundo
    de ontem*.

    IMPORT TARDIO, e não é gosto: `backend_pydualsense` importa `pydualsense` no
    topo (dependência dura do projeto, mas cara), e a interface é um processo
    separado do daemon. Pagar o import na primeira carga da aba, uma vez, é o
    mesmo arranjo do `texto_da_bateria` logo acima.
    """
    global _ESTADOS_DO_DONO
    if _ESTADOS_DO_DONO is None:
        from hefesto_dualsense4unix.core.backend_pydualsense import ESTADO_DE_CARGA

        _ESTADOS_DO_DONO = frozenset(ESTADO_DE_CARGA.values())
    return _ESTADOS_DO_DONO


def carga_na_tela(estado: object) -> str:
    """A palavra do estado de carga, ou `""` quando a tela não diz nada.

    `""` é o que APAGA o ícone: o alvo `atributo` do piloto remove o atributo
    quando o valor é vazio ou travessão (`hefesto_vivo.py`, ramo `atributo`), e
    a folha esconde o elemento sem `data-carga`. Três coisas caem no `""`:
    `descarregando` (decisão), `None` (*ninguém reportou ainda*) e qualquer
    palavra que não seja do dono.

    **O TRANSPORTE NÃO ENTRA AQUI, e não é esquecimento** — não há parâmetro por
    onde ele entrasse. É a decisão dela de 06/09 escrita na assinatura: quem
    quiser acoplar carga a cabo/rádio tem de mudar a forma da função, e a régua
    `test_a_bateria_diz_carregando_no_radio` reprova quando alguém tenta.
    """
    if not isinstance(estado, str):
        return ""
    if estado not in estados_de_carga():
        return ""
    return _NA_TELA_POR_CARGA.get(estado, "")


_ENDERECOS: frozenset[str] | None = None


def _enderecos_da_pagina() -> frozenset[str]:
    """Todo `data-campo` da página PUBLICADA. Vazio quando ela não abre."""
    global _ENDERECOS
    if _ENDERECOS is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            doc = ""
        _ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', doc))
    return _ENDERECOS


def _so_se_a_pagina_tiver(campos: dict[str, Any]) -> dict[str, Any]:
    """Dos `campos`, só os que a página publicada tem onde pôr.

    MORDE: devolver `campos` inteiro põe os quatro endereços da bancada em
    `casamento.medir(...)["orfaos"]` e reprova
    `test_a_aba_controles_nao_emite_para_endereco_que_a_pagina_nao_tem`.
    """
    tem = _enderecos_da_pagina()
    return {k: v for k, v in campos.items() if k in tem}


@registrar("02-controles.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Os valores da aba Controles, com os nomes que a página tem.

    O DESENCONTRO ERA DE PONTUAÇÃO E DE SENTIDO. O pacote emitia `mic_mudo` com
    underscore e a página tem `mic-selo` com hífen; emitia `mascara` valendo
    `uhid` — o BACKEND — e a página mostra "DualSense", que é o nome da máscara.
    Dez chaves emitidas, uma casando. Medido em 01/09/2026.
    """
    import mesa_viva

    cards = {}
    # A CAMADA 1 DA ROTA, uma vez por tique e para a mesa inteira — ver
    # `_camada_1`. Ela é BLOQUEANTE (roda `pactl`), então tem relógio próprio:
    # a leitura fica em cache e uma thread a renova a cada dois segundos. Sem
    # isto o "Todo o som do PC" continuaria acendendo pelo byte, que é como o
    # card 2 dela ficou aceso com o som saindo na TV, em 03/09.
    na_mesa = tuple(str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq"))
    _camada_1(
        tuple((str(c.get("uniq") or ""), _byte_da_rota(c)) for c in ctx.conectados),
        na_mesa,
    )
    # ONDE CADA PONTINHO ESTÁ, por assento — ver `folha_das_posicoes`. Ele se
    # junta AQUI, e não dentro de `cards`, porque o destino é a folha da PÁGINA:
    # `left`/`top` não são campo de um elemento, são regra de um seletor.
    posicoes: dict[str, dict[str, tuple[float, float] | None]] = {}
    # OS NÓS DAS ONDAS, uma vez por tique e para a mesa inteira — ver o bloco
    # `AS ONDAS SONORAS`. Passa-se a lista COMPLETA: o medidor fecha o que saiu
    # dela no mesmo instante, e é isso que faz o controle desligado parar de
    # segurar um `parec`. Vem DEPOIS do `_camada_1` porque é dele que sai o sink
    # do alto-falante.
    nos_das_ondas: dict[str, str] = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        if not uniq:
            continue
        for no in (no_do_microfone(c), no_do_alto_falante(uniq)):
            if no:
                nos_das_ondas[no] = uniq
    _seguir_as_ondas(nos_das_ondas)
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # `inputs` TEM TRÊS ESTADOS, E O PRODUTO SÓ ENXERGAVA DOIS. O `or {}`
        # abaixo continua servindo para LER campo por campo; o que ele NÃO pode
        # decidir é se houve leitura — `None` e `{}` viram o mesmo dicionário
        # vazio, e daí em diante "não sei" é indistinguível de "solto".
        # Medido em 02/09/2026, com os dois controles dela ligados: só o
        # `is_primary` traz `inputs`; o outro vem `None`
        # (`daemon/ipc_handlers.py:3572-3516`).
        tem_leitor = isinstance(c.get("inputs"), dict)
        e = c.get("inputs") or {}
        a = c.get("audio") or {}
        # O ALTO-FALANTE TEM UM DONO SÓ, e ele mora no motor. Esta linha era
        # `sp = c.get("speaker") or {}`, e o `or {}` escondia DOIS defeitos:
        #
        #   1. o bloco chega em DUAS posições. `speaker_do_entry` aceita
        #      `entry["speaker"]` **e** `entry["inputs"]["speaker"]` porque
        #      *"quem publica é o daemon, e o widget não pode quebrar por causa
        #      de onde o dado mora"* (`controller_card.py:1936`). Medido na mesa
        #      dela em 02/09/2026 às 16h: o daemon publica nas DUAS. No dia em
        #      que ele publicar só na de dentro, esta aba ficava cega e a de
        #      cima continuava dizendo um número;
        #   2. ausência virava `{}`, e `{}` virava zero. Ver `alto-estado`.
        #
        # `None` = o daemon nunca publicou `speaker` para este controle, que é o
        # estado real de quem nunca recebeu um `speaker.set` — o registrador não
        # se lê, só se escreve (`ipc_handlers.py:4659`).
        sp_lido = speaker_do_entry(c)
        # A COR DA BARRA DE LUZ, pelo dono das CINCO situações. **Os DOIS
        # valores são usados**: o rótulo é o discriminador e a base é a cor.
        # Descartar o rótulo — que é o que esta linha fazia — jogava fora a
        # única coisa que separa "apagada" de "não sei". Ver `luz_hex`.
        #
        # O `getattr` É POR CAUSA DE UM DUBLÊ, e ele está declarado para não
        # virar hábito: `Contexto.state` é campo do dataclass e o piloto sempre
        # o traz, mas a régua do microfone monta um `Contexto` PARCIAL — uma
        # classe com `conectados` e `mesa` e nada mais
        # (`tests/unit/test_mic_da_mesa_o_ipc_a_tela_e_o_gesto.py:114`, com
        # `# type: ignore[arg-type]` na chamada). Sem esta guarda, a primeira
        # aba a ler o estado GLOBAL derruba a régua de outra. O dublê é que
        # precisa crescer; enquanto ele não cresce, `{}` é o que
        # `rotulo_lightbar` já trata (`state_global.get("native_mode")`).
        rotulo_da_luz, base_da_luz = rotulo_lightbar(c, getattr(ctx, "state", None) or {})
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})

        # O MUDO TEM TRÊS CARAS, e o selo da tela diz qual: mudo pelo aparelho,
        # mudo pedido pelo Hefesto, e sem posse (o kernel manda).
        #
        # E TEM UMA QUARTA, QUE É "NÃO SEI" (MIC-DA-MESA-ELEICAO-01). O byte de
        # áudio é atributo de INSTÂNCIA do handle: no hotplug-out o handle
        # morre, o novo nasce sem leitura e a chave `audio` SOME do `state_full`.
        # `bool(None)` é `False`, que este selo pintava como **ATIVO** — ou
        # seja, o controle que acabou de cair anunciava que estava capturando.
        # Com a inversão da luz (aceso = no ar), isso vira mentira no plástico
        # de quatro pessoas ao mesmo tempo.
        #
        # **AS DUAS LEITURAS QUE MORAVAM AQUI DESCERAM PARA `selo_composto` —
        # 04/09/2026, decisão [03].** Eram `sabemos = isinstance(a["mic_mudo"],
        # bool)` e `mudo = bool(a["mic_mudo"])`, as duas do MESMO bit, e o selo
        # se decidia só com elas. As quatro faces da D-12 não cabem em duas
        # variáveis locais, e escrevê-las aqui deixaria a régua sem como medir
        # o selo sem montar um `state_full` inteiro.
        pct = c.get("battery_pct")
        # OS BOTÕES APERTADOS, com o nome que o daemon publica. É a MESMA leitura
        # do dono na GTK (`app/widgets/controller_card.py:5453`, `"l3" in
        # buttons_pressed`) e a mesma que `mesa_viva.estado_do_card:451` faz para
        # os glifos — `inputs["buttons"]` é uma lista de nomes, e `l3`/`r3`
        # entram nela crus (o `TRADUZ_GLIFO` só reescreve `create` → `share`).
        apertados = set(e.get("buttons") or ())
        # O TOQUE, LIDO — e ele era uma CONSTANTE. Esta linha dizia
        # `"touch-estado": "Sem toque"`, literal: a tela afirmava, sem ler nada,
        # que ninguém estava encostando no touchpad. Um dedo na superfície não
        # mudava um pixel.
        #
        # HOJE ELE TEM UM DONO SÓ, e é o do produto. A conta dos três estados
        # (`inputs` ausente · `inputs` sem a chave · o bloco lido) mora inteira
        # dentro de `touchpad_do_inputs`, e a razão de a recusa anterior ter
        # caído está no bloco `O TOUCHPAD` no topo deste arquivo, com as 60
        # leituras que a mediram.
        toque_txt, toque_ponto, onde_o_dedo = toque_do_controle(e)
        # A POSIÇÃO DOS TRÊS PONTINHOS, pelo `pref` do assento — que é o que o
        # `data-controle` das páginas traz, e o mesmo endereço que a
        # `folha_do_plastico` usa. Sem `pref` na mesa não há seletor a escrever.
        posicoes[str(casa.get("pref") or "")] = posicoes_do_controle(
            e, tem_leitor, onde_o_dedo)
        # A IDENTIDADE DO CABEÇALHO, pelos donos: a ordem das quatro fontes é de
        # `identidade_de`, e a tradução do transporte é a MESMA que a mesa usa.
        #
        # A PALAVRA VEM DO DONO — CONTROLES-VERDADE-01, 06/09/2026, e ela cura
        # um DEFEITO VIVO que a costura da ONDA B abriu hoje, calado.
        #
        # Esta linha era `VIA_DO_TRANSPORTE.get(…)`, a SIGLA DE MÁQUINA, e o
        # cabeçalho do card dizia `USB`/`BT` — que o glossário de hoje proíbe em
        # texto de tela (`docs/A-LINGUA-DESTA-CASA`, §1: na tela é **cabo** e
        # **rádio**; a contagem do topo é a única exceção, e é dela).
        #
        # MAS O ESTRAGO ERA MAIOR QUE A PALAVRA, e ele está DUAS LINHAS ABAIXO:
        # o `peca` compara `nome_na_tela == via_na_tela` para não escrever o
        # transporte DUAS VEZES no mesmo cabeçalho. Hoje `identidade_de` passou a
        # cair na palavra da tela no último degrau — e a comparação passou a ser
        # entre `"rádio"` e `"BT"`, que nunca casam. MEDIDO nesta árvore, com um
        # controle sem cor lida (a mesa dela pelo rádio é exatamente este caso):
        #
        #   transport='bt'   identidade_de='rádio'   via_na_tela='BT'
        #   → o cabeçalho lia  `P2 • rádio • BT`
        #
        # O comentário do bloco do `peca` já nomeava o defeito — *"o cabeçalho
        # leria `BT • BT`"* — e a guarda que ele descrevia tinha deixado de
        # valer no mesmo dia em que foi lida.
        #
        # A PERGUNTA É AO PRÓPRIO `identidade_de`, e não a uma palavra escrita:
        # é a forma que a `a09_sistema` adotou na ONDA4-S10 e a razão dela vale
        # aqui inteira — *"um conjunto de palavras é uma cópia da tradução"*, e
        # a cópia descasa calada na próxima troca de língua. O que o dono
        # devolve para um controle que SÓ tem o transporte **é** o último degrau,
        # neste transporte, na língua que ele fale hoje.
        via_na_tela = palavra_do_transporte(c.get("transport"))
        nome_na_tela = identidade_de(c, ctx.mesa)
        ultimo_degrau = identidade_de({"transport": c.get("transport")})
        cards[uniq] = {
            # A GRAFIA DA CARGA NÃO É MAIS REDIGITADA AQUI — ver
            # `texto_da_bateria`, que PERGUNTA à GTK as duas frases.
            "bateria": texto_da_bateria(pct),
            # A BARRA, e ela precisa do NÚMERO CRU: o `escrever` do piloto com
            # `data-hef-alvo="largura"` monta `width: <t>%`, e um "95%" ali
            # viraria `width: 95%%`. Zero quando o daemon não sabe — deixar a
            # barra na largura que o gerador desenhou seria a tela afirmando uma
            # carga que ninguém mediu.
            "bateria-barra": int(pct) if isinstance(pct, int) and not isinstance(pct, bool)
                             else 0,
            # O `via` SAIU DAQUI EM 02/09/2026, e a saída é uma MEDIÇÃO, não
            # arrumação: `casamento.medir("02-controles.html")` na ponta de `dev`
            # (2b219284) dava `orfaos: ['l2', 'r2', 'via']` — três valores
            # emitidos a cada tique para endereços que a página publicada NÃO
            # TEM. O piloto único procura por `data-campo`, `data-papel` e
            # `data-hef` (`hefesto_vivo.py:631`), e nenhum dos três existe para
            # estes nomes. Eles não escreviam nada, e ainda assim entravam na
            # conta de `cobertura.pintados` — o pacote se reportava 13 e pintava
            # 10.
            #
            # O QUE CADA UM QUERIA DIZER, e onde a tela ainda mente por não ter
            # onde pô-lo:
            #
            #   `via`      o transporte. O cabeçalho do card é
            #              `<span class="card-nome">P1 • Cosmic Red • USB</span>`
            #              (`paginas/02-controles.html:1430`), texto do desenho,
            #              SEM endereço nenhum. Medido em 02/09 às 04:23: a mesa
            #              viva dá `p1 → BT` e `p2 → USB`, e os dois cabeçalhos
            #              na tela diziam o CONTRÁRIO, congelados desde o mockup.
            #              Dar-lhe endereço é partir aquele `<span>` em três, que
            #              é desenho — logo, decisão dela.
            #   `l2`/`r2`  os gatilhos crus. A linha existe e é
            #              `.gat-linha[data-gatilho="l2"]`, com `.n` e `.cheio`
            #              dentro — `data-gatilho` é o quinto vocabulário, e o
            #              piloto único não o lê.
            #
            # Não é perda de dado: os três continuam a UM `.get` do `state_full`
            # no dia em que a página ganhar onde pô-los.
            # A MÁSCARA É O NOME QUE O JOGO VÊ, e a tradução já tem dono em
            # `mesa_viva.NOME_DA_MASCARA`. `uhid` é o backend, e é outra coisa.
            #
            # E O SEGUNDO RAMO ESTAVA NO ESPAÇO DE CHAVES ERRADO, medido em
            # 02/09/2026: ele era
            # `NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—")`, e
            # `NOME_DA_MASCARA` só tem `dualsense` e `xbox` — que são MÁSCARAS.
            # `vpad_backend` vale `uhid`, `uinput` ou `None`, e NENHUM dos três
            # está na tabela: o ramo inteiro só sabia devolver `—`. Um `.get`
            # com padrão não estoura, e por isso o defeito era mudo.
            #
            # QUEM CONVERTE BACKEND EM MÁSCARA É O MOTOR, e a regra dele não é
            # um mapa: *"`backend == "uhid"` implica máscara DualSense e não
            # pode ser outra coisa"*, porque o `virtual_pad._try_uhid` recusa o
            # uhid para saída Xbox (`home_actions.mascara_viva:914`). E `uinput`
            # é AMBÍGUO de propósito — Xbox normal e DualSense degradado usam o
            # mesmo backend —, então ele devolve `None`, que aqui vira o
            # travessão. Dizer "não sei" é o comportamento honesto.
            "mascara": casa.get("mascara") or mesa_viva.NOME_DA_MASCARA.get(
                mascara_viva({"gamepad_emulation": {"backend": c.get("vpad_backend")}})
                or "", "—"),
            # A COR DA BARRA, PELO RÓTULO — o discriminador do motor, e não a
            # base do accent. As cinco situações e o que cada uma mostra estão
            # na tabela do `luz_hex`, no topo deste arquivo, com a sonda que as
            # mediu; aqui fica só o que o campo NÃO pode fazer, que é decidir
            # sozinho: esta linha já leu `lightbar_rgb` cru (afirmava `#000000`
            # sobre cor desconhecida) e já leu só a base (colapsava "apagada"
            # em "não sei"). Os dois defeitos são o mesmo — inventar o
            # discriminador em vez de usar o que o dono devolve.
            #
            # A FRASE INTEIRA DO RÓTULO NÃO CABE, e agora está MEDIDO em vez de
            # afirmado: o `<span class="de-quem">` não tem largura fixa (o CSS
            # é `margin-left:auto;font-size:10.5px`, `02-controles.html:1015`) e
            # a linha que o contém mede **148px**. No Chrome, com a fonte da
            # página: `#7EB8D4` ocupa 45,3px, "A Steam segura" 78,8px numa linha
            # só, e "Lightbar: apagada" 86,7px — este QUEBRA a linha (14px para
            # 28px de altura). Ou seja: PALAVRA CABE aqui, frase não. Qual
            # palavra é decisão dela; até ela dizer, o campo mostra código de
            # cor ou travessão, que é o vocabulário que ele já tem.
            # A PALAVRA CURTA NO LUGAR DO TRAVESSÃO — decisão [02], 04/09/2026.
            # O código de cor continua saindo quando há cor; o que muda são os
            # quatro estados que dividiam um `—` só. Ver `luz_palavra`, e a
            # frase inteira vai para o `title` da linha (`luz-porque`).
            "luz-hex": luz_palavra(rotulo_da_luz, base_da_luz),
            # UM DONO SÓ para o selo, nos dois pintores (auditoria 02/09/2026):
            # `mesa_viva.selo_do_mic`. O ternário estava escrito duas vezes, e
            # a régua do outro lado olhava o TEXTO — a cura de lá caía calada.
            #
            # **E ELE PASSOU A DIZER O ESTADO COMPOSTO — 04/09/2026, decisão
            # [03] (conflito C-2), pela D-12 dela.** Esta linha era
            # `selo_do_mic(mudo, sabemos)`, e `mudo` é SÓ o bit do firmware: a
            # tela dizia ATIVO sobre um microfone cujo som não chegava a canal
            # nenhum. As quatro faces e a razão de cada uma estão em
            # `selo_composto`, logo acima; o `sabemos`/`mudo` daqui continuam
            # vivos porque o `resumo_fechado` da linha fechada os usa.
            "mic-selo": selo_composto(a),
            # O `mic-modo` SAIU DAQUI EM 01/09/2026, e ele APAGAVA DOIS BOTÕES.
            # O endereço `data-campo="mic-modo"` não era uma folha: era o
            # `<span class="rota mic-modo">` que ENVOLVE o Virtual e o Nativo. O
            # `escrever` do piloto faz `el.textContent = t`, e `t` de um valor
            # vazio é `—` (`hefesto_vivo.py:100-116`) — o primeiro tique trocava
            # os dois botões por um travessão.
            # MEDIDO no Chrome headless, sobre a página publicada, com os dois
            # valores que esta linha emitia (`''` e `'sem posse'`):
            # `[data-mic-modo]` antes **4**, depois **0**, nos dois casos.
            # ERA A CAUSA DE ELES NÃO TEREM DONO: a primeira leva os deixou de
            # fora por "não há método", e a segunda mediu que, além disso, eles
            # nem existiam quando ela clicava. O `data-campo` saiu do gerador
            # junto com esta linha, e há régua nos dois lados.
            # O QUE SE PERDEU: o "sem posse" (`mic_mudo_desejado is None`, o
            # estado em que o botão do plástico ainda manda no mudo). Ele não
            # tinha lugar no desenho — estava sendo escrito por cima dos botões,
            # não num campo dela. Dar-lhe um lugar é decisão dela, não daqui.
            # O ALTO-FALANTE — E ESTA LINHA ESCREVIA O REGISTRADOR CRU COM UM
            # SINAL DE PORCENTAGEM. Ela era:
            #
            #     "Mudo" if sp.get("muted") else f"{sp.get('volume', 0)}%"
            #
            # DOIS DEFEITOS, e os dois medidos na mesa dela em 02/09/2026, 16h:
            #
            #   1. `speaker.volume` é **0-255**, o registrador do protocolo
            #      (`ipc_handlers.py:3723`, `:4799`). Com o valor vivo de hoje —
            #      **102** — este pacote emitia **"102%"** (para o vão
            #      `hidden`, ver o cabeçalho: não chegou aos olhos dela). Uma
            #      porcentagem acima de cem, e ela subiria a "255%" no talo, no
            #      dia em que o campo saísse do vão. E não é só o `%`
            #      sobrando: a conta certa NÃO é `bruto / 255`. O
            #      `core/speaker_scale.py` existe por isso e traz a curva
            #      MEDIDA no hardware (tom de 1 kHz, o microfone do próprio
            #      controle como instrumento): abaixo de 38 tudo é mudo, acima
            #      de 102 tudo é o mesmo volume — *"`bruto / 255` desenhava
            #      50 % para um registrador em 128 que soa exatamente igual a
            #      255"*. `texto_volume` é o rótulo que a GTK escreve
            #      (`sensor_widgets.py:215`, e é a mesma régua da linha de
            #      comando): `texto_volume(102, False)` = **"100 %"**;
            #   2. `sp.get('volume', 0)` transformava AUSÊNCIA em **zero**. O
            #      daemon só publica `speaker` depois do primeiro `speaker.set`
            #      (`ipc_handlers.py:4659`) — antes dele a tela afirmava "0%"
            #      sobre um alto-falante que ninguém mediu, que é o gêmeo exato
            #      do "Sem toque" logo abaixo. `speaker_do_entry` devolve `None`
            #      nesse caso, e `None` é o travessão.
            #
            # **ELE SAIU DAQUI EM 04/09/2026, e desceu para o bloco da bancada.**
            # A razão é a decisão [09] resolvida: o valor ia para um `<span
            # hidden>` desde sempre, e o desenho novo não tem mais esse vão — o
            # que MOSTRA o mudo agora é o próprio ♪, pelo alvo `classe`. Emitir
            # para um endereço que a página não tem é o que
            # `_so_se_a_pagina_tiver` existe para impedir; enquanto o publicado
            # ainda tiver o `alto-estado`, ele continua sendo pintado, e no dia
            # em que ela publicar a bancada ele para sozinho.
            # SEM BLOCO `touchpad` NÃO É "SEM TOQUE" — e quem separa os três
            # estados é o dono, não um `isinstance` escrito aqui.
            "touch-estado": toque_txt,
            # O CLIQUE DOS DOIS ANALÓGICOS — os dois endereços que a página tinha
            # e ninguém pintava. O rótulo e a marca do clicado são do GERADOR
            # (`ROTULO_DO_CLIQUE` e `CLICADO`, no topo deste arquivo), e o
            # GERADOR os lê daqui — a seta aponta para o produto, e a razão
            # medida está escrita lá em cima.
            **{
                campo: (
                    (CLICADO % rot if campo in apertados else rot)
                    if tem_leitor else mesa_viva.SEM_LEITOR
                )
                for campo, rot in (("l3", ROTULO_DO_CLIQUE["l"]),
                                   ("r3", ROTULO_DO_CLIQUE["r"]))
            },
            # OS QUATRO DA BANCADA. Eles só entram quando a página publicada tem
            # onde pô-los — ver `_so_se_a_pagina_tiver`, logo acima.
            **_so_se_a_pagina_tiver({
                # O PONTINHO DO TOUCHPAD, decisão dela de 02/09 (item 15): *"o
                # pontinho do touchpad só aparece quando há toque — hoje ele
                # aparece com `touching` falso, contra o que a própria dica
                # promete"*. É o `set_toque((fx, fy) if tocando else None)` da
                # GTK, sem o `(fx, fy)`: o piloto único não tem alvo de POSIÇÃO
                # (os sete são texto·largura·fundo·valor·html·classe·cor), então
                # o que esta aba alcança é acender e apagar. Ver
                # `espera_o_pintor` — a posição já está calculada e sem
                # endereço.
                # O ESTADO DE CARGA AO LADO DO NÚMERO — BATERIA-ICONE-01,
                # 06/09/2026. O dado chegou à tela na BATERIA-PARADA-01 (o
                # `battery_state` viaja no mesmo dicionário do `battery_pct`,
                # cru do `describe_controllers`) e não tinha onde pousar.
                #
                # ELE LÊ `c`, QUE É A ENTRADA DO DAEMON, e não o `transport` que
                # está DUAS variáveis acima nesta mesma função. A tentação de
                # cruzar os dois é o defeito que ela nomeou: *"no radio ele pode
                # tá carregando tambem"*.  # noqa-acento: citação literal dela
                "bateria-carga": carga_na_tela(c.get("battery_state")),
                "touch-ponto": toque_ponto,
                # O `alto-estado` DESCEU PARA CÁ — 04/09/2026, decisão [09]
                # resolvida. Ele era emitido SEMPRE, para um `<span
                # class="mudo" data-campo="alto-estado" hidden>` que o piloto
                # nunca desesconde: valor vivo escrito a cada tique num vão
                # invisível, e foi assim que o "102%" viveu meses sem ninguém
                # ver. A bancada não tem mais o vão; enquanto o PUBLICADO tiver,
                # ele continua sendo pintado — e no dia da publicação para
                # sozinho, sem virar órfão.
                "alto-estado": (
                    texto_volume(*sp_lido) if sp_lido is not None
                    else mesa_viva.SEM_LEITOR
                ),
                # **ONDE A TELA MOSTRA QUE O ALTO-FALANTE ESTÁ MUDO** — em lugar
                # nenhum, até hoje. O ♪ nunca acendeu por leitura: o `on` dele
                # era classe do desenho. Agora ele acende como os quatro botões
                # que a leva de 03/09 endereçou, pelo alvo `classe`.
                #
                # SÃO TRÊS ESTADOS E NÃO DOIS, e o terceiro é a razão de este
                # campo não ser um `bool`: `speaker_do_entry` devolve `None`
                # quando o daemon nunca publicou `speaker` para este controle, e
                # `muted` pode ser `None` dentro de um bloco que traz volume.
                # Um `False` nos dois casos acenderia "não está mudo" sobre um
                # alto-falante que ninguém leu.
                # A PALAVRA É A DO MESMO DONO QUE O SELO DO MICROFONE usa —
                # `mesa_viva.selo_do_mic`, que já sabe os TRÊS estados e já
                # escreve `MUDO` / `ATIVO` / `—`. Escrever os literais aqui
                # seria a segunda gramática para o mesmo par de palavras, na
                # mesma tela, a dois blocos de distância.
                "alto-mudo": mesa_viva.selo_do_mic(
                    bool(sp_lido and sp_lido[1]),
                    sp_lido is not None and sp_lido[1] is not None,
                ),
                # O VOLUME DO ALTO-FALANTE GANHA ENDEREÇO, decisão dela de
                # 02/09 (item 16): *"o número E a barra. Hoje os dois estão
                # congelados no desenho: com o volume em 40, a tela continua
                # mostrando 100"*. Medido na foto de 02/09 às 19h: o bloco
                # mostra `100` e a barra cheia para os DOIS controles, e nem o
                # `<span class="n">` nem o `.cheio` tinham `data-campo`.
                #
                # A CONTA É DO MOTOR: `percentual_do_volume` é a curva MEDIDA no
                # hardware (`core/speaker_scale.py`), a mesma que
                # `texto_volume` usa para o `alto-estado` — dois campos do mesmo
                # bloco divergirem por causa de dois arredondamentos é o defeito
                # que aquele módulo existe para não cometer.
                "alto-num": (
                    percentual_do_volume(sp_lido[0]) if sp_lido is not None
                    else mesa_viva.SEM_LEITOR
                ),
                # A BARRA VAI A ZERO QUANDO NÃO SE SABE, e é o mesmo desfecho
                # que a `bateria-barra` já tem duas dúzias de linhas acima, pela
                # mesma razão: `largura` é um dos ALVOS_QUE_O_TRAVESSAO_NAO_
                # ATENDE (`pacotes/__init__.py:391`) — `width: "—%"` o CSSOM
                # recusa e o contador de pintura soma +1 por tique para sempre.
                # Deixá-la na largura do desenho seria a tela afirmando um
                # volume que ninguém mediu; o número ao lado diz `—`, que é o
                # que separa "zero" de "não sei".
                "alto-barra": (
                    percentual_do_volume(sp_lido[0]) if sp_lido is not None else 0
                ),
                # AS DUAS ONDAS SONORAS — o pedido dela de 05/09/2026, e as
                # catorze barrinhas de cada uma deixam de ser desenho. Ver o
                # bloco `AS ONDAS SONORAS` para os dois endereços e o custo.
                #
                # O MICROFONE NÃO PRECISA DO `mudo=`: com o mic calado no
                # firmware a source entrega zeros de verdade — medido em
                # 05/09/2026 na mesa dela, 146 amostras seguidas em `0.000000`
                # com `mic_mudo: true`. A física responde, e o produto não
                # precisa inferir.
                **campos_da_onda(LADO_MIC, alturas_do_no(no_do_microfone(c))),
                **campos_da_onda(
                    LADO_ALTO,
                    alturas_do_no(no_do_alto_falante(uniq)),
                    mudo=bool(sp_lido is not None and sp_lido[1] is True),
                ),
                # OS DOIS INTERRUPTORES DE SENSOR — 04/09/2026, e eles acendem
                # pelo que o daemon diz, não pelo que o gerador desenhou.
                #
                # O `.sw` do desenho era classe FIXA: os quatro botões nasciam
                # acesos e ficavam acesos, mesmo depois de a ONDA1-D3 pôr o
                # interruptor de verdade no daemon. `sensores.<qual>_ligado` é a
                # chave nova do payload (irmã de `inputs`), e o alvo `classe`
                # acende `off` quando o valor for `DESLIGADO`.
                #
                # TRÊS ESTADOS, PELA MESMA RAZÃO DO `alto-mudo`: sem o bloco
                # `sensores` a resposta é o travessão, e não `DESLIGADO` — um
                # `bool()` cru aqui apagaria o botão de todo controle que ainda
                # não tem leitor de entradas.
                **{
                    campo: _selo_do_sensor(_sensor_ligado(c, qual_do_campo))
                    for campo, qual_do_campo in (("giro-ligado", "giroscopio"),
                                                 ("accel-ligado", "acelerometro"))
                },
                # O RETÂNGULO DA BARRA DE LUZ — o desenho que CONTRADIZ o campo
                # ao lado dele. Fotografado em 02/09/2026 às 19h: o `luz-hex`
                # dizia `#0000FF` (a cor viva do P1) e o retângulo logo abaixo
                # estava no `#7EB8D4` que o mockup cravou. A régua do mockup é
                # cega a isso — ela conta `data-campo`, e o retângulo não tinha
                # nenhum —, então só o olho pega.
                #
                # O ALVO É `cor`, E NÃO `fundo`, e a escolha é medida: o ramo do
                # `fundo` no piloto é `if(el.style.background !== t){ ...
                # return 1 }`, e o CSSOM NORMALIZA na atribuição (`#0000FF`
                # volta `rgb(0, 0, 255)`) — a comparação nunca casa e o contador
                # soma +1 por tique, para sempre. O ramo do `cor` ESCREVE e
                # depois COMPARA (`hefesto_vivo.py:246-250`), então é idempotente
                # por construção. O gerador pinta o retângulo com
                # `background:currentColor`, e escrever a cor de linha muda o
                # fundo.
                #
                # VAZIO APAGA A COR DE LINHA e o retângulo volta ao `--panel` da
                # folha de estilo — que é "nada", e é o que ela decidiu para
                # todo campo sem informação. Os três "não sei" do `luz_hex`
                # mandam vazio pela mesma razão que ele manda travessão.
                "luz-cor": _cor_da_barra(rotulo_da_luz, base_da_luz),
                # O CABEÇALHO DO CARD — o que ela viu mentindo em 03/09/2026.
                #
                # O `via` JÁ SAÍRA DAQUI em 02/09 por não ter onde pousar, e a
                # linha que o tirou dizia: *"Dar-lhe endereço é partir aquele
                # `<span>` em três, que é desenho — logo, decisão dela."* A
                # decisão veio (`IDENTIDADE-VEM-DE-CIMA-01`), o gerador partiu o
                # `<span>`, e ele volta pela mesma porta por onde saiu.
                #
                # O NOME É DE `identidade_de`, que é o dono da ordem das quatro
                # fontes (o que ELA nomeou > o modelo decodificado > a mesa > o
                # transporte). O ÚLTIMO RAMO DELE NÃO SERVE AQUI: ele cai no
                # transporte quando não há nome, e o desenho já mostra o
                # transporte ao lado — o cabeçalho leria `BT • BT`. Quando o que
                # sobrou foi o transporte, esta aba manda VAZIO, e o piloto
                # escreve o travessão: `P2 • — • BT` é a verdade da mesa dela
                # hoje, com a cor do rádio ainda não lida.
                "peca": "" if nome_na_tela == ultimo_degrau else nome_na_tela,
                "via": via_na_tela,
                # OS DOIS ACESOS QUE ERAM DESENHO — 03/09/2026. Cada um vai
                # para os DOIS botões do seu par: eles compartilham o mesmo
                # `data-campo`, e cada um decide por si pelo `data-hef-quando`
                # (`hefesto_vivo.escrever`, ramo `classe`). É a mesma gramática
                # dos quatro degraus da Vibração, e é ela que faz "ligar um
                # desligar a irmã" acontecer sem lista de irmãs.
                # **ELE PASSOU A LER AS DUAS CAMADAS — 04/09/2026, decisão
                # [09].** Era `rota_na_tela(c)`, o byte e mais nada, e foi
                # assim que o card 2 dela acendeu "Todo o som do PC" com o som
                # saindo na TV. Ver `aceso_da_rota`, e a ressalva logo abaixo,
                # que é onde o desacordo entre as duas vira palavra.
                "alto-rota": aceso_da_rota(uniq, c),
                # A RESSALVA DO ALTO-FALANTE — a peça da ONDA0-F (D-02), e o
                # texto é do motor (`audio_saida.MOTIVO_ROTA_SO_NO_BYTE`). Ela
                # **nasce e morre com o desacordo**: sem ele, o campo vai com
                # `monta.NADA_A_DIZER` e a linha some sem cobrar um pixel.
                #
                # E A CHAVE VAI EM TODO TIQUE, que é a instrução da folha com
                # todas as letras: omiti-la deixaria a frase velha na tela para
                # sempre — o defeito oposto, e pior.
                #
                # **ELA PASSOU A TER DOIS INFORMANTES — 06/09/2026, o QUARTO
                # selo.** O desacordo das duas camadas vem primeiro porque é um
                # fato de AGORA, que ela pode desfazer trocando a saída do
                # sistema; a ressalva do transporte é uma dívida NOSSA, que
                # nenhum clique dela resolve. Dizer as duas na mesma linha
                # trocaria o alarme por dois avisos — a mesma regra do
                # `selo_do_som`.
                # UM INFORMANTE SÓ, DESDE 07/09/2026 — ver o bloco "O QUARTO
                # SELO SAIU DA TELA". Eram dois: o desacordo das camadas de som
                # (que fica, porque é um fato de AGORA que ela desfaz) e a
                # ressalva do transporte (que saiu, porque era dívida NOSSA).
                "alto-ressalva": recado_da_rota(uniq) or NADA_A_DIZER,
                "mic-modo-aceso": modo_do_mic(norm_mac(uniq) or ""),
                # A DEGRADAÇÃO DA MÁSCARA — decisão [07], 04/09/2026: *"uma
                # marca na palavra e o motivo no hover"*.
                #
                # O AJUDANTE JÁ EXISTIA E NENHUM DOS DEZ PACOTES O CHAMAVA:
                # `pacotes.degradacao_de` delega a `controller_card.
                # texto_degradacao`, que é o dono da regra na GTK e o dono da
                # tradução do motivo técnico para frase leiga
                # (`MOTIVOS_DEGRADACAO_LEIGOS`). Não faltava código — faltava
                # onde pousar a frase.
                #
                # UM CAMPO SÓ FAZ AS DUAS COISAS, e é por isso que o alvo é
                # `atributo` e não `classe`: o `<sup>` do gerador nasce
                # `display:none` e a folha o mostra por `[title]`. Com a marca
                # numa classe e o motivo noutro campo, seria possível pintar
                # uma marca sem motivo — e uma marca sem explicação é ruído com
                # cara de dado, que é o que o `?` da ONDA0-F já recusa.
                "mascara-degradou": degradacao_de(c),
                # A LINHA DA VERDADE — "o que chega ao jogo".
                # CONTROLES-VERDADE-01, 06/09/2026, e é a entrega central desta
                # sprint: *"numa mesa de quatro, o cartão é o único lugar onde
                # se descobre por que um controle não está fazendo nada"*.
                #
                # O DONO MONTA A FRASE INTEIRA, incluindo as DUAS EXCEÇÕES —
                # Modo Nativo (*"o jogo fala direto com o controle — tudo
                # chega"*) e a máscara Xbox 360. Omitir a exceção seria a tela
                # dizer que nada chega justamente quando muita coisa chega, e o
                # `state_global` é obrigatório por isso: as duas exceções são
                # perguntas ao estado GLOBAL, não ao controle.
                #
                # O `getattr` É O MESMO DO `rotulo_lightbar` VINTE LINHAS ACIMA,
                # e pela mesma razão declarada lá: há régua que monta um
                # `Contexto` PARCIAL, sem `state`. Um `{}` faz o dono devolver
                # `None` (sem gamepad virtual não há o que dizer), que é
                # exatamente o desfecho certo para "não perguntei".
                #
                # `None` VIRA VAZIO, E O VAZIO ESCONDE A LINHA: o alvo
                # `atributo` do elemento de fora remove o `title` e a folha o
                # apaga por `:not([title])`. Ver o bloco `A LINHA DA VERDADE` no
                # `interface/aba02.py`. Uma linha vazia num card de quatro é
                # ruído, e este card não tem pixel para ruído.
                "giro-no-jogo": texto_motion(
                    c, getattr(ctx, "state", None) or {}) or "",
                # A LEITURA VIVA — 46 campos por card, e nenhum deles tinha
                # endereço até 03/09/2026. Ver `leitura_viva`, que traz a mesa
                # do que a tela dizia contra o que o aparelho publicava no
                # mesmo instante.
                **leitura_viva(c),
                # A FRASE INTEIRA DA BARRA DE LUZ, no `title` da linha —
                # decisão [02]. O campo ao lado mostra a PALAVRA (`Jogo`,
                # `Steam`, `Não sei`, `Apagada`) e este diz a frase que o motor
                # devolve. Ver `luz_porque`: com a cor conhecida ele volta a
                # ser a explicação de quem escolhe a cor, que era literal do
                # gerador até hoje.
                "luz-porque": luz_porque(rotulo_da_luz, base_da_luz),
                # OS DOIS BOTÕES DE SOM QUE VÃO RECUSAR — decisão [04] (D-03),
                # com a peça da ONDA0-F. **UM CAMPO SÓ ALIMENTA O BOTÃO E A
                # DICA**: o botão pelo alvo `classe` (acende `apagado` quando o
                # valor não é vazio) e o `?` pelo alvo `html`. Com dois campos
                # seria possível pintar um botão cinza sem razão.
                #
                # A RAZÃO É A DO MOTOR, e é a MESMA que o gesto levanta quando
                # o clique chega assim mesmo: `acao_mic` e `acao_speaker_mudo`
                # são os donos dos estados destes dois botões na GTK. A tela
                # deixa de descobrir a recusa DEPOIS do clique — que é a
                # queixa inteira da D-03.
                **porques_do_som(c),
                # A METADE VISÍVEL DA GUARDA SEM ENDEREÇO — linha 57. Os dois
                # `?` acima já dizem POR QUÊ; o que falta é o que a GTK faz
                # ANTES do clique: apagar as peças que MANDAM som. Um campo só,
                # nos DOIS blocos (o `achar()` do piloto visita os dois com o
                # mesmo valor), e o alvo `atributo` REMOVE o atributo quando o
                # endereço aparece — a volta acontece sozinha, sem a guarda ter
                # de lembrar quem ela apagou.
                #
                # ELE NÃO REUSA `alto-porque`, e a diferença é medida: aquele
                # campo também acende no estado SEM POSSE, e ali o deslizante é
                # justamente o que ela tem de arrastar para destravar o ♪.
                # Apagá-lo naquele estado seria trancar a única saída.
                #
                # A LEITURA FICA LIGADA DE PROPÓSITO — a barra, o medidor de
                # ondas e os rótulos contam o que o daemon publicou sobre ESTE
                # controle, e continuam verdadeiros sem endereço nenhum. Quem
                # mente sem endereço é o COMANDO.
                "som-sem-endereco": (
                    "" if uniq_do_entry(c) is not None else TEXTO_AUDIO_SEM_ENDERECO
                ),
                # QUAL GAMEPAD VIRTUAL ESTE CONTROLE ALIMENTA — linha 45, e a
                # frase inteira é do dono (`dica_do_titulo`), inclusive o "ainda
                # não alimenta gamepad virtual nenhum" e o nome REAL do vpad
                # quando ele diverge do número da fila.
                #
                # É DICA E NÃO LINHA, pela mesma razão que na GTK: o endereço é
                # diagnóstico, não vocabulário de interface, e o cabeçalho do
                # card não tem largura sobrando. `None` (sem endereço, daemon
                # velho sem a lista, controle fora da mesa) vira `""`, e o alvo
                # `atributo` some com o `title` em vez de inventar um par.
                "card-vpad": dica_do_titulo(c, getattr(ctx, "state", None) or {}) or "",
                # O SELO, O SUFIXO E O PORQUÊ DO CANAL — linhas 89 e 90. Os três
                # saem do mesmo par de fatos (`saida_muda` da camada 1 e o sono
                # do sink), e os três são LEITURA: nenhum deles oferece botão.
                "alto-selo": (selo_do_som(saida_muda_do_entry(c), sono_do_canal(uniq))
                              or NADA_A_DIZER),
                "alto-canal": sufixo_do_canal(sono_do_canal(uniq)) or NADA_A_DIZER,
                "alto-canal-porque": (dica_do_canal(sono_do_canal(uniq), regra_do_sono())
                                      or NADA_A_DIZER),
            }),
        }
    # OS VALORES QUE VALEM PARA A PÁGINA INTEIRA, e não por card. Os três nasceram
    # da mesma lei de 03/09 e todos passam pelo `_so_se_a_pagina_tiver`: a bancada
    # já os tem, o publicado só no minuto em que ela mandar publicar.
    #
    # A FITA SE TROCA INTEIRA a cada tique (`hefesto_vivo._fita`) e, quando isso
    # acontece, estes dois endereços nem existem no DOM — o `achar()` devolve zero
    # elementos e ninguém escreve. ELES SÃO PARA QUANDO A TROCA NÃO ACONTECE:
    # `_fita` devolve `""` se UM controle da mesa vier sem cor, e pelo rádio a cor
    # não é lida. Com um controle no cabo e outro no rádio — a mesa dela — a fita
    # FICAVA COM O DESENHO inteiro, `Cosmic Red` e `Starlight Blue`.
    #
    # SÃO LISTAS porque o número de chips é o da mesa, e o piloto já as distribui
    # pelos elementos de mesmo `data-campo`, na ordem (`hefesto_vivo.BOOTSTRAP`,
    # o ramo `Array.isArray`). Chip a mais recebe vazio e vira travessão.
    da_pagina = _so_se_a_pagina_tiver({
        "plastico-css": folha_do_plastico(ctx.mesa),
        # ONDE O DEDO E OS DOIS POLEGARES ESTÃO — a queixa dela de 04/09. Ver o
        # bloco `A POSIÇÃO DOS PONTINHOS` no topo: `left`/`top` viravam `style=`
        # de linha, que folha de estilo nenhuma vence e o piloto não sabe
        # escrever. Ela entra pelo `_so_se_a_pagina_tiver` como os outros da
        # bancada: acende no minuto em que ela mandar publicar.
        "posicao-css": folha_das_posicoes(posicoes),
        "fita-peca": [
            "" if str(m.get("nome") or "") == NOME_SEM_LEITURA else str(m.get("nome") or "")
            for m in ctx.mesa
        ],
        "fita-via": [str(m.get("via") or "") for m in ctx.mesa],
    })
    return {"cards": cards, "mesa": da_pagina, "sem_dono": {},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()) + len(da_pagina),
                          "sem_dono": 0}}


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao aparelho
# ---------------------------------------------------------------------------
# ESTA ABA TEM OITO BOTÕES POR CONTROLE. Eram TRÊS com dono depois da primeira
# leva; são CINCO desde 01/09/2026 — o Virtual e o Nativo entraram. O resto
# desta seção é sobre os três que continuam sem, porque é aí que uma tela mente:
# o botão que responde calado deixa quem clicou concluir que funcionou.
#
# O QUE TEM DONO, medido nos 39 métodos do `ipc_server` em 01/09/2026:
#
#   🎙  data-mudo="microfone"      `mic.set`      (ipc_handlers.py:4814)
#   ♪   data-mudo="alto-falante"   `speaker.set`  (ipc_handlers.py:4648)
#   Sons do jogo  data-rota="jogo" `speaker.set`  com `rota`, o mesmo :4589
#   Virtual / Nativo  data-mic-modo  `machine.declare` (ipc_handlers.py:5258)
#
# O "VIRTUAL / NATIVO" GANHOU DONO EM 01/09/2026, E A AFIRMAÇÃO ANTERIOR CAIU.
# Aqui estava escrito, e é uma frase minha, da primeira leva:
#
#     "Virtual / Nativo — o modo do microfone é a `ONDA-CONEXOES-06`, e ela não
#      virou código: `grep` por mic virtual em `src/` devolve ZERO — só a sprint."
#
# A SEGUNDA METADE CONTINUA VERDADEIRA: `integrations/microfone_do_dualsense.py`
# não existe, e a `ONDA-CONEXOES-06` não virou código. A CONCLUSÃO é que estava
# errada — eu procurei pela PALAVRA "virtual", que é vocabulário do desenho, e
# não pela COISA que os dois botões descrevem. A coisa tem dono desde 22/08/2026
# e é a ponte de microfone por Bluetooth (`QUATRO-MICROFONES-01`, decisão dela:
# *"por controle"*), com o gesto vivo na GUI estável
# (`app/actions/config/secao_controles.py:1113`). Ver o gesto `mic-modo`.
#
# O QUE NÃO TEM, e o motivo de cada um está no `sem_dono` do gesto que o recusa
# ou na conferência abaixo:
#
#   Giroscópio / Acelerômetro   não há método de sensor nos 39 (medido de novo
#                               em 01/09: `daemon.metodos()` não traz um único
#                               `sensor.*`, `gyro.*` nem `motion.*`). O
#                               `sensor_hub` só LÊ — as suas 15 funções são
#                               `leitura`, `reconciliar`, `_abrir_*`, e nenhuma
#                               liga ou desliga nada. `profiles/schema.py:902`
#                               diz que os dois estão "FORA POR AUSÊNCIA, NÃO
#                               POR DECISÃO", com dona declarada
#                               (`ONDA-CONTROLES-07`, que traria a
#                               `ProfileSensorsConfig` — `grep` por ela em
#                               `src/` devolve UMA linha, e é aquele comentário).
#                               O rascunho também não os conhece:
#                               `ipc_draft_applier.py` não tem uma ocorrência de
#                               giro, sensor ou accel.
#   Calibrar / Mapa do Controle são `<a href>`, navegação — não IPC.
#
# O QUE SAIU DESTA LISTA EM 04/09/2026:
#
#   Todo o som do PC            **GANHOU DONO** — `audio_saida.mandar_o_som_do_pc`,
#                               que é a camada 1 sem GTK. Ver o gesto `rota`.
#   Os dois deslizantes de volume   **GANHARAM PEÇA E DONO** (D-08 dela:
#                               *"Deslizante nos dois"*). Aqui estava escrito que
#                               eles *"NÃO EXISTEM como elemento clicável"* e que
#                               *"o que falta é do lado do DESENHO, e desenho é
#                               dela"* — ela decidiu, e o gerador passou a emitir
#                               `<input type="range" data-gesto="volume">` nos
#                               dois blocos. Ver o gesto `volume`.
#
# GIROSCÓPIO E ACELERÔMETRO CONTINUAM SEM MÉTODO, e agora têm DONO MESMO ASSIM —
# ver o gesto `sensor`, que é o que separa as duas coisas: *ter dono* não é *ter
# método*. O que ele faz é recusar DIZENDO, no cartão daquele controle, em vez de
# a página emitir um gesto chamado `clique` que aba nenhuma registra.
#
# NADA SE REESCREVE: o `p` é `pacotes/ponte.py`, que expõe o `app/ipc_bridge.py`
# — a mesma camada que a GUI estável usa, com o payload montado e a recusa do
# daemon traduzida.
#
# O NÚMERO DA ROTA NÃO SE DIGITA. Ele é o `OUTPUT_PATH_SEL` (bits 4-5 do
# `common[7]`) e tem dono nomeado em `core/ds_output_report.py:136`, que é
# módulo puro — o outro lugar onde ele aparece com nome é
# `app/widgets/controller_card.py:716`, e aquele importa GTK.
#
# `secao_controles` É A REGRA DO MICROFONE E AS TRÊS FRASES DELA, do produto
# estável. O guia manda desconfiar de `app/actions/*` — mas o aviso de lá é
# sobre os MIXINS GTK (`self._get`, `self._toast_light`), e `pode_ligar_o_mic` e
# `dica_do_microfone` são funções de MÓDULO, puras, sobre um objeto de dados.
# Medido em 01/09/2026: o import roda sem display e sem `gi` (o `from
# gi.repository import Gtk` daquele arquivo mora DENTRO dos construtores de
# widget). Reescrevê-las seria a segunda verdade: a condição e a frase que a
# explica já existem, com dono, e são exatamente o que este botão precisa dizer
# quando recusa. **A condição NÃO é mais "só no rádio" — 04/09/2026, D-12**: é
# `tem_canal_de_captura`, e o transporte saiu dela. Ver o gesto `mic-modo`.
#
# `norm_mac` é o dono da CHAVE do `maquina.json` — doze hex minúsculos. O daemon
# publica o `uniq` ora com dois-pontos, ora sem, e montar a chave à mão aqui
# gravaria a declaração num controle que não existe.
#
# A ORDEM DESTE BLOCO É A DO `ruff --select I`, não a da leitura: um bloco fora
# de ordem reprova o portão de lint, e é ele que decide a integração.
from hefesto_dualsense4unix.app import audio_saida  # noqa: E402
from hefesto_dualsense4unix.app.actions.config import (  # noqa: E402
    secao_controles as _mic_do_produto,
)
from hefesto_dualsense4unix.core.ds_output_report import (  # noqa: E402
    SAIDA_L_FONE_R_ALTO_FALANTE,
)
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402

from . import gesto  # noqa: E402
from . import perfil as _perfil  # noqa: E402
from . import ponte as _ponte  # noqa: E402


def _corpo(r: Any) -> dict[str, Any] | None:
    """A resposta do daemon como CORPO, tolerando ponte que devolva só `bool`.

    As duas funções `_detalhado` da ponte devolvem `dict | None`, e é o corpo
    que carrega o que o `bool` apagava — QUAL metade do ato do microfone
    faltou, e se o volume caiu no controle de outra pessoa. Este guarda existe
    pela MESMA razão que o `_resposta` daqui de baixo, e ela é do instrumento:
    o dublê da régua compartilhada (`test_os_botoes_tem_dono.PonteDeMentira`)
    responde `True` a todo nome que ele não conhece, e um `.get` às cegas
    levantaria `AttributeError` DENTRO do teste — o instrumento reprovando a si
    mesmo em vez de medir o botão.

    **E ELE NÃO INVENTA A NOTÍCIA QUE O `bool` NÃO TEM.** `True` vira
    `{"status": "ok"}` e mais nada: sem `motivo` e sem `por_uniq`, os dois
    caminhos que dizem alguma coisa a mais ficam CALADOS — que é a verdade
    sobre um `bool`. É por isso que a régua desta aba usa um dublê ESTRITO, que
    devolve o corpo de verdade: **um dublê mais frouxo que a ponte real é a
    cicatriz de 04/09**, e ela custou duas máscaras que nunca gravaram um byte.
    """
    if isinstance(r, dict):
        return r
    return {"status": "ok"} if r else None


def _selo_do_sensor(ligado: bool | None) -> str:
    """`LIGADO` · `DESLIGADO` · travessão — as três respostas do interruptor.

    Irmã de `mesa_viva.selo_do_mic`, e escrita aqui pela mesma razão que aquela
    mora lá: um lugar só para o par de palavras. `None` é o travessão de
    `mesa_viva.SEM_LEITOR`, que é o que a casa inteira usa para "ninguém leu".
    """
    import mesa_viva

    if ligado is None:
        return str(mesa_viva.SEM_LEITOR)
    return SENSOR_LIGADO if ligado else SENSOR_DESLIGADO


def _sensor_ligado(dele: dict[str, Any], qual: str) -> bool | None:
    """`True`/`False` do interruptor daquele sensor; `None` = o daemon não disse.

    A CHAVE É `sensores`, IRMÃ DE `inputs`, e ela é NOVA em 04/09/2026
    (`daemon/ipc_handlers._merge_sensores`). O bloco traz
    `giroscopio_ligado`/`acelerometro_ligado` — o INTERRUPTOR — ao lado dos
    valores vivos que a moldura Giroscópio mostra. São coisas diferentes: o
    Hefesto continua LENDO o sensor desligado, quem deixa de recebê-lo é o jogo.
    Adivinhar o interruptor pelo valor faria um controle parado na mesa desenhar
    "desligado" com o sensor ligado.

    `None` E NÃO `True`: a ausência aqui não é o default dela (esse mora no
    `RegistroDeSensores.estado`, do lado do daemon) — é a falta de LEITURA, e os
    dois desfechos são opostos. Ver `SEM_LEITURA_DE_SENSOR`.
    """
    bloco = dele.get("sensores")
    if not isinstance(bloco, dict):
        return None
    valor = bloco.get(f"{qual}_ligado")
    return valor if isinstance(valor, bool) else None


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": um mudo sem dono calaria os quatro controles da mesa
    em vez de um. É o mesmo cuidado que a cura de 04/08/2026 pôs no seletor de
    canal da GUI estável, e a razão está escrita lá — *"com dois cards na tela,
    clicar no card do Controle 2 escrevia no Controle 1"*.
    """
    return str(o.get("uniq") or "")


def _volume_conhecido(dele: dict[str, Any]) -> dict[str, Any]:
    """`{"volume": N}` quando o daemon sabe o número, `{}` quando não sabe.

    ELE NÃO SE INVENTA, e a razão é do aparelho: o DualSense **não devolve** o
    registrador de volume, então `daemon.state_full` só publica a chave
    `speaker` depois do primeiro `speaker.set` (`ipc_handlers.py:4659`). Mandar
    um número de palpite tomaria a posse com o valor errado.

    E MANDÁ-LO QUANDO SE SABE É O QUE A GUI ESTÁVEL FAZ, pela cura de
    04/08/2026 (`controller_card.py:4265`): *"reafirmá-lo aqui é dizer ao
    firmware o mesmo que a tela mostra, em vez de deixá-lo adivinhar"*.

    QUEM LÊ É `speaker_do_entry`, E NÃO ESTA FUNÇÃO. Ela fazia
    `(dele.get("speaker") or {}).get("volume")` — uma das TRÊS leituras à mão
    que este arquivo tinha do mesmo bloco, e todas as três conheciam só UMA das
    duas posições em que ele chega. Com o daemon publicando `speaker` dentro de
    `inputs`, o botão do ♪ recusava dizendo "o volume ainda é desconhecido"
    sobre um volume que estava no payload, duas chaves ao lado.
    """
    lido = speaker_do_entry(dele)
    return {"volume": lido[0]} if lido is not None else {}


# ---------------------------------------------------------------------------
# O SOM DESTE CONTROLE VAI PARA O PERFIL — 05/09/2026
# ---------------------------------------------------------------------------
# PEDIDO DELA, e ele é sobre AMANHÃ: *"aplicar aplica todas as configs naquele
# perfil e salvar se lembra disso quando eu for jogar o jogo e no dia seguinte e
# por diante. pra cada perfil e dentro dele cada config pra cada comtrole"*.
#
# O QUE FALTAVA, medido nesta árvore com o ciclo inteiro (perfil no disco → os
# cinco gestos de som desta aba → reler o arquivo): os cinco chegavam ao
# aparelho e o perfil ficava com `controllers: None`. Ela mexia no volume do
# microfone do P2, e no dia seguinte o número era o de ontem.
#
# É PERSISTÊNCIA NO CLIQUE, e é a decisão D2 de 05/09
# (`docs/process/2026-09-05-AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas.md`):
# o requisito dela é DURABILIDADE, não o gesto de salvar — e só a escrita no
# clique sobrevive a fechar a janela sem clicar em nada. O rodapé continua
# valendo como rede de segurança.
#
# QUEM DECIDE O QUE VIRA OVERRIDE NÃO É ESTE ARQUIVO, e a regra é a COR-04 que
# `with_controller_leds` escreveu primeiro: valor igual ao global NÃO vira
# override — `with_controller_mic` e `with_controller_speaker` já a aplicam
# sozinhos, e um `if` de igualdade aqui seria a segunda cópia dela.

#: O QUE ESTE ARQUIVO **NÃO** GRAVA, e a razão é do daemon, não da tela.
#:
#: `mic.button_toggles_system` é UM por MÁQUINA: quem o lê é
#: `hotkey.mic_button_loop`, em `daemon.config.mic_button_toggles_system`, sem
#: consultar `uniq` nenhum (`daemon/subsystems/hotkey.py:1234`). O esquema o
#: RECUSA por peça (`ControllerMicOverride._o_que_ainda_nao_tem_caminho_por_peca`)
#: — e a régua da casa é `test_perfil_por_controle_o_campo_espera_o_caminho.py`,
#: nos dois sentidos. Guardá-lo por controle faria quatro controles gravarem
#: quatro opiniões sobre um interruptor só.
#:
#: Os SENSORES também não entram por aqui: `with_controller_sensores` existe e o
#: gesto `sensor` é o dono deles, mas ele é de outra frente (a que liga o
#: giroscópio ao perfil). Uma escrita aqui seria um segundo dono do mesmo campo.
_NAO_GRAVA_POR_PECA = ("button_toggles_system",)

#: A ESCOLHA CHEGOU AO APARELHO E NÃO TEM ONDE MORAR. As frases abaixo dizem,
#: nesta ordem, O QUE PEGOU e o que não vai sobreviver ao dia seguinte — e é
#: isso que as separa de uma recusa: aqui o gesto FUNCIONOU.
#:
#: Elas sobem como `RuntimeError` porque esse é o canal que deposita frase no
#: cartão daquele controle (`Piloto._recusou_dizendo`, 30 s).
#:
#: **E "NÃO HÁ PERFIL ATIVO" NÃO ESTÁ ENTRE ELAS — a razão é a regra dela,
#: 02/09/2026: *"é aviso, não estado"*.** A primeira versão desta cura
#: levantava também nesse caso, e OITO réguas já escritas desta aba reprovaram
#: (`test_a_aba_02_controles_fecha_as_linhas.py` e
#: `test_a02_som_e_sensor_falam_quando_recusam.py`) — todas modelando um mundo
#: com daemon e controle e sem perfil, e todas medindo que o gesto que dá certo
#: NÃO levanta. Elas estavam certas: "não há perfil ativo" é ESTADO PARADO, e
#: ele já está na tela — o chip `Perfil ativo` do cabeçalho o mostra o tempo
#: todo. Repeti-lo como recado de 30 s a cada clique de som é estado disfarçado
#: de aviso, e o preço é o oposto do pretendido: quem recebe a mesma frase em
#: todo clique para de ler os recados.
#:
#: O que sobra de aviso é EVENTO, e não estado: havia perfil, ela mexeu, e a
#: escrita falhou NAQUELE clique.
_PERFIL_E_ESTADO_NAO_E_AVISO = "Perfil ativo"

#: A ABERTURA DA FRASE QUE A BORDA COMPLETA — e ela é uma só de propósito.
#:
#: QUEM DIZ SE A CHAVE SERVE É O ESQUEMA, e não este arquivo:
#: `Profile._validate_controllers_keys` exige doze dígitos hex e recusa o
#: `path:…`, o OUI degenerado `00:00:00` e o broadcast, cada um com a razão
#: escrita. Repetir a regra aqui seria a TERCEIRA cópia dela (a segunda é
#: `ipc_handlers._chave_de_peca_que_grava`), e a cópia é o que envelhece no dia
#: em que a primeira mudar.
#:
#: **E `norm_mac` sozinho NÃO SERVE PARA GRAVAR — medido em 04/09/2026:**
#: `norm_mac("path:/dev/hidraw3")` devolve `"adeda3"`, uma chave que parece boa
#: e que aparelho nenhum reivindica. Esta régua pegou o buraco na primeira
#: execução, com o `if not chave` que eu tinha escrito aqui deixando passar.
SOM_SEM_ENDERECO = (
    "o ajuste chegou ao controle agora, mas o perfil recusou guardá-lo só "
    "para esta peça: "
)

SOM_SEM_VOLUME_PARA_GUARDAR = (
    "a rota deste alto-falante foi escrita no controle, mas o perfil ainda "
    "não sabe o volume dele — e o Hefesto não guarda alto-falante sem volume, "
    "porque uma seção sem número manda ZERO ao firmware e tranca o "
    "alto-falante. Arraste o volume deste alto-falante uma vez e a rota passa "
    "a ser lembrada junto."
)


# ---------------------------------------------------------------------------
# O SOM QUE CONFIRMA — o alto-falante dizendo que o gesto pegou
# ---------------------------------------------------------------------------
# IDEIA DELA, e ela é sobre entender o produto pelo ouvido: *"ao clicar em cada
# botão ele emite o som (…) tem que ajudar a entender o conceito"*. A janela GTK
# faz isso desde a SOM-04 em QUATRO gestos do bloco do alto-falante
# (`app/widgets/controller_card.py:4599`); esta aba fazia em zero, e o custo
# subiu quando o DESLIZANTE do alto-falante nasceu — ela passou a arrastar um
# número e a não ter como saber que a mudança valeu, porque **não há leitura de
# volta hoje**: o número que a tela mostra é o que NÓS mandamos.
#
# «NÃO HÁ LEITURA DE VOLTA HOJE» É O QUE SE SABE, e a frase forte que estava
# aqui — *"o registrador não tem leitura"* — não se sustenta: o
# `docs/data/mapa-controles.csv` põe `audio.leitura_de_volta` como
# `existe=desconhecido`, e *"ninguém achou"* não é *"não existe"*.
#
# O MOTOR É DO PRODUTO E NÃO SE REESCREVE: `app/audio_saida.tocar_confirmacao`
# tem os sete degraus de recusa, a trava de um som por vez, a guarda-mãe (um
# `paplay` com `--device` inexistente sai com ZERO e toca no sink PADRÃO — sem
# ela a confirmação sairia pela televisão dela) e o acordar do nó suspenso.
# O que esta seção constrói é o CAMINHO até ele: quem sabe o sink daquele
# controle, e onde a chamada entra sem segurar a tela.


def _sink_para_o_som(uniq: str, na_mesa: tuple[str, ...]) -> str:
    """O sink deste controle: o cache da camada 1 primeiro, o dono depois.

    **BLOQUEANTE NO SEGUNDO CAMINHO** — `audio_saida.sink_do_controle` roda dois
    `pactl`. Por isso ela só é chamada de dentro de :func:`_fora_do_voo`, nunca
    do tique nem do corpo do gesto.

    O CACHE VEM PRIMEIRO porque a aba 02 é a mais pintada da casa e ele está
    quente depois de ~2 s de tela; o dono entra no caso frio (o primeiro clique
    de uma aba recém-aberta), e é o MESMO dono que o cache consulta — não é uma
    segunda regra de atribuição. Escrever outra aqui daria ao alto-falante do
    controle errado o som deste, que é o defeito que `escolher_sink` existe
    para não cometer.

    `""` é resposta honesta e frequente: é o controle sem placa de som atribuída
    — e com `""` o motor não toca, em vez de tocar no sink padrão.
    """
    do_cache = sink_do_cache(uniq)
    if do_cache:
        return do_cache
    return str(audio_saida.sink_do_controle(uniq, list(na_mesa)) or "")


def _fora_do_voo(fn: Callable[[], None]) -> None:
    """Roda `fn` numa linha própria, sem segurar o botão que está em voo.

    **O GESTO JÁ NÃO RODA NO TIQUE** — medido em 06/09/2026 no piloto: ele
    despacha cada gesto numa thread (`interface/hefesto_vivo.py:2239`), porque
    *"`daemon.reload` leva 9,5 segundos"*. Logo a tela não congela nem se o som
    for chamado direto, e o `TIQUE_MS` de 100 ms segue livre.

    O QUE ESTA FUNÇÃO EVITA É OUTRA COISA, e ela é visível: o `finally` do
    piloto só devolve o botão do voo — e só faz o campo piscar verde (03-Q4) —
    quando o gesto retorna. `tocar_confirmacao` custa 0,35 s medidos de ponta a
    ponta e tem teto de 5 s; segurá-lo no corpo do gesto atrasaria a resposta
    VISUAL do clique pelo tempo do som. A confirmação sonora não pode pagar-se
    com a confirmação visual.

    É a mesma forma da :func:`_camada_1` logo acima, e pela mesma razão: o que
    fala com o PipeWire vive na sua própria linha.

    **ELA É O PONTO DE INJEÇÃO DAS RÉGUAS.** A régua a troca por uma chamada
    direta e mede o som sem esperar relógio nenhum — corrida na suíte é vermelho
    que aparece uma vez em dez.

    **E ELA É A GUARDA DA MÁQUINA DELA — 06/09/2026, e o defeito era meu.** Sem
    a janela de pé ninguém clicou, e o som não nasce. Medido na bancada: com o
    `pactl` DUBLADO de uma régua vizinha, o sink do DualSense casa pela regra do
    um-para-um, o motor o encontra "na lista viva" e chega ao `paplay`, que não
    está dublado — a suíte tocava som no alto-falante do controle dela. A
    guarda-mãe do `audio_saida` não alcança isso de propósito: ela confere o
    sink contra a lista viva, e numa régua a lista viva é de mentira. Quem sabe
    que ninguém clicou é `ponte.dentro_da_janela`, e a régua que QUER medir o
    som troca esta função — que é o contrato acima.

    **A PERGUNTA VAI AO MÓDULO `ponte`, e não ao `p` que o gesto recebe**: o `p`
    é DUBLADO nas réguas, e um dublê responde `True` a todo nome que não conhece
    — perguntar a ele se a janela está de pé receberia sempre "sim", que é o
    instrumento respondendo por si mesmo.
    """
    import threading

    if not _ponte.dentro_da_janela():
        return
    threading.Thread(target=fn, name="hefesto-som-de-confirmacao",
                     daemon=True).start()


def _confirmar_com_som(ctx: Contexto, uniq: str) -> None:
    """O som curto no alto-falante DESTE controle. Escritor único desta aba.

    **QUEM CHAMA É O DESFECHO DO ATO NO APARELHO, nunca o pedido.** Emiti-lo
    antes de o daemon responder confirmaria uma coisa que pode não ter
    acontecido — é o que a GTK escreve no `_confirmar_com_som` dela, que só toca
    com o `ok` do IPC na mão.

    **E ELE VEM ANTES DO `_lembrar_do_som`, de propósito:** o som responde por
    *"o aparelho recebeu"*, e a gravação responde por *"o perfil guardou"* — as
    duas metades que esta casa aprendeu a dizer separadas. `_lembrar_do_som`
    pode recusar (perfil sem volume para guardar, controle sem endereço), e
    nesse caso o volume ESTÁ no aparelho: calar o som ali faria a confirmação
    do aparelho depender de um fato do disco.

    A CHAVE DELA JÁ ESTÁ RESPEITADA, e não se inventa uma segunda: quem lê
    `som_ligado()` é o motor, no primeiro dos sete degraus, e desligada ele sai
    calado — sem recusa e sem recado.

    O `saida_muda` VEM DO DONO (`saida_muda_do_entry`): com a saída do sistema
    muda, tocar gastaria um processo para produzir silêncio, e ela leria o
    silêncio como defeito do controle — que é o contrário do que a confirmação
    existe para dizer. `None` é *não sei*, e não impede o som.
    """
    na_mesa = tuple(
        str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq")
    )
    muda = saida_muda_do_entry(ctx.por_uniq(uniq))

    def tocar() -> None:
        try:
            audio_saida.tocar_confirmacao(
                _sink_para_o_som(uniq, na_mesa), saida_muda=muda)
        except Exception:
            # O SOM É CONFIRMAÇÃO, NÃO PRÉ-REQUISITO. Um alto-falante que
            # impedisse o volume de mudar seria o defeito trocado de lugar — e
            # aqui ele roda noutra linha, onde uma exceção solta viraria
            # traceback no terminal de quem lançou a janela, que ninguém lê.
            return

    _fora_do_voo(tocar)


def _lembrar_do_som(
    ctx: Contexto,
    uniq: str,
    *,
    mic: dict[str, Any] | None = None,
    speaker: dict[str, Any] | None = None,
) -> None:
    """Grava no PERFIL ATIVO o som que ficou de pé NESTE controle.

    ESCRITOR ÚNICO DO SOM POR PEÇA nesta aba, e ser um só é a regra da casa:
    a classe de defeito que ela persegue é *"três escritores do perfil sem
    dono"*. Os cinco gestos de som desta aba chamam ESTA função, e nenhum
    monta `controllers[...]` à mão.

    **QUEM CHAMA É O CALLBACK DE SUCESSO, nunca o gesto em si** — a mesma
    disciplina de `registrar_alto_falante_no_rascunho`: o perfil descreve o que
    FICOU DE PÉ, não a intenção. Um pedido recusado pelo daemon que fosse ao
    disco seria a tela decidindo por ela: o número no arquivo passaria a
    contradizer o aparelho, e a ativação seguinte reimporia o que nunca pegou.

    `mic` e `speaker` são os campos que ESTE gesto fez ficar de pé, e só eles:
    `{"muted": True}`, `{"volume": 42}`, `{"rota": 2}`. Campo ausente é campo
    não tocado, e o que já estava no perfil sobrevive — é a mesma regra do
    `rota` do `SpeakerDraft` (*"mexer no volume não pode apagar o mudo que ela
    acabou de escolher, nem o contrário"*).

    **A BASE É O EFETIVO, e não um `MicDraft`/`SpeakerDraft` nu.** Medido: os
    dois escritores do produto substituem a SEÇÃO inteira, então mandar só o
    campo mexido apagaria o irmão dele — um clique no mudo derrubaria o volume
    próprio que ela tinha escolhido. `effective_mic_for`/`effective_speaker_for`
    devolvem o que vale hoje para esta peça (override, ou o global herdado), e
    é sobre isso que o campo novo entra.

    **A LEITURA VIVA SÓ PREENCHE O QUE O PERFIL NÃO SABE**, e a ordem foi
    MEDIDA nesta árvore, em 05/09/2026. `ProfileSpeakerConfig` exige `volume`
    (uma seção sem número manda ZERO e tranca o alto-falante — SOM-02,
    armadilha 1), então o clique no mudo ou na rota precisa de um volume vindo
    de algum lugar. A primeira versão desta função tirava esse número do tique
    do daemon, e a medição mostrou o estrago: com o perfil em 62 e o tique
    ainda em 100, o clique na rota devolvia o disco a 100 e a escolha dela
    sumia sem uma palavra — a mesma família do *"o Salvar destruía o que o
    produto gravou"* que esta leva fecha. O tique é bom para SABER quando o
    perfil não sabe; nunca para corrigir o que ela escolheu.

    NADA MUDOU = NADA GRAVA, e não é economia: regravar um perfil idêntico
    troca a data do arquivo por nada. É a mesma guarda do `_gravar_a_forca` da
    aba Vibração, e é ela que torna inócuo o clique DOBRADO do deslizante.

    **ELE GRAVA E NÃO MANDA REAPLICAR, e a diferença com a aba Vibração é
    MEDIDA — não é descuido.** Lá, `perfil.gravar_e_reaplicar` é obrigatório: a
    força por peça só chega ao motor PELA ativação do perfil, então gravar sem
    reaplicar deixaria a tela dizendo uma coisa e o aparelho fazendo outra —
    que é exatamente a razão escrita naquele dono. **Aqui o aparelho JÁ está no
    valor**: o gesto acabou de mandá-lo por `mic.canal.set`/`speaker.set` e o
    daemon confirmou. O perfil é o REGISTRO do que já está de pé.

    E o disco não fica para trás: `ProfileManager.activate` faz
    `load_profile(name)` a CADA ativação (`profiles/manager.py:297`) — não há
    cópia do `Profile` em memória atravessando ativações, então a próxima
    (hotplug, troca de jogo, boot) lê o que esta função escreveu.

    O que se evita com isso é caro para ela: um `profile.switch` reaplica o
    perfil INTEIRO — luz, gatilhos, vibração — a cada clique no mudo, no meio
    de uma partida, para reafirmar um byte que já estava escrito.

    O `launch_env.refresh` do mesmo dono também fica de fora, e pelo mesmo
    critério: o que ele rematerializa é a antecipação de MODO/emulação por
    `appid` (`ipc_handlers._handle_launch_env_refresh`), e nenhum dos cinco
    campos daqui — `mic.muted`, `mic.volume`, `speaker.volume/.muted/.rota` —
    entra nessa conta. Um dia em que este arquivo passar a gravar `mode`,
    `match` ou emulação, ele volta.

    O CAMINHO DE DISCO É O DA ABA PERFIS até o penúltimo passo: `load_profile`
    → `DraftConfig.from_profile` → os escritores por peça → `to_profile(nome,
    priority=…)` → `loader.save_profile`. A `priority` vai junto porque
    `to_profile` a recebe de fora; sem ela o perfil dela perderia a ordem de
    casamento (`BUG-FOOTER-SAVE-DROPS-SECTIONS-01`, nomeado no próprio
    `to_profile`).
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    if not mic and not speaker:
        return
    nome = str((getattr(ctx, "state", None) or {}).get("active_profile") or "").strip()
    if not nome:
        # SEM PERFIL ATIVO NÃO HÁ ONDE GUARDAR, e a saída é CALADA de propósito
        # — ver `_PERFIL_E_ESTADO_NAO_E_AVISO`. Na máquina dela o daemon SEMPRE
        # publica um `active_profile` (medido no `state_full` vivo:
        # `'meu_perfil'`); este ramo é o do daemon parado ou do estado ainda não
        # lido, e nos dois o chip do cabeçalho já diz.
        return
    # A GRAFIA É A DO PERFIL, e o dono dela é `norm_mac` — o MESMO que
    # `Profile._validate_controllers_keys` usa ao carregar. Montar a grafia à
    # mão criaria uma SEGUNDA chave para o mesmo aparelho, e a borda do esquema
    # rejeita o perfil INTEIRO com "chaves duplicadas após normalização": a
    # escolha dela sumiria, e o arquivo junto.
    #
    # `norm_mac` NORMALIZA, mas não JULGA — quem julga é a borda, no `to_profile`
    # lá embaixo. Ver `SOM_SEM_ENDERECO`.
    chave = norm_mac(str(uniq or "").strip()) or ""

    loader = _perfil._com_o_src()
    try:
        prof = loader.load_profile(nome)
    except Exception as erro:
        raise RuntimeError(
            f"o ajuste chegou ao controle, mas não consegui ler o perfil "
            f"{nome!r} para guardá-lo: {erro}") from erro

    draft = DraftConfig.from_profile(prof)
    novo = draft
    adiante: Any = None
    try:
        if mic:
            novo = novo.with_controller_mic(
                chave, novo.effective_mic_for(chave).model_copy(update=mic))
        if speaker:
            base = novo.effective_speaker_for(chave)
            if base.volume is None:
                # A LEITURA VIVA SÓ PREENCHE O QUE O PERFIL NÃO SABE, e essa
                # ordem foi MEDIDA — a primeira versão desta função preferia o
                # vivo, e a medição mostrou o estrago: com o perfil em 62 e o
                # tique do daemon ainda em 100, o clique na rota devolvia o
                # volume a 100 e a escolha dela sumia do disco sem uma palavra.
                # É a mesma família do "o Salvar destruía o que o produto
                # gravou" que esta leva fecha.
                lido = speaker_do_entry(ctx.por_uniq(uniq))
                if lido is not None:
                    vivo: dict[str, Any] = {"volume": lido[0]}
                    if lido[1] is not None:
                        vivo["muted"] = lido[1]
                    base = base.model_copy(update=vivo)
            alvo = base.model_copy(update=speaker)
            if alvo.volume is None:
                raise RuntimeError(SOM_SEM_VOLUME_PARA_GUARDAR)
            novo = novo.with_controller_speaker(chave, alvo)
        if novo.source_controllers == draft.source_controllers:
            return
        # A BORDA JULGA A CHAVE AQUI, e é por isso que o `to_profile` mora
        # DENTRO do `try`: é ele que monta o `Profile` e dispara
        # `_validate_controllers_keys`. Fora do `try`, o `path:/dev/hidraw3`
        # subia como traço cru de pydantic — medido pela régua desta cura.
        adiante = novo.to_profile(nome, priority=prof.priority)
    except RuntimeError:
        raise
    except Exception as erro:
        raise RuntimeError(f"{SOM_SEM_ENDERECO}{erro}") from erro

    # SÓ O DISCO — ver a docstring. O aparelho já está no valor, e a próxima
    # ativação relê o arquivo.
    loader.save_profile(adiante, origem="interface-nova")


@gesto("02-controles.html", "mudo", grava="save_profile")
def mudo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O 🎙 e o ♪ — os dois botões de calar, e eles ALTERNAM o que a tela mostra.

    UM GESTO PARA OS DOIS porque a página os marca com o mesmo `data-mudo`, e o
    valor dele diz qual. Separá-los em dois nomes inventaria um vocabulário que
    o desenho não tem.

    **São métodos diferentes, e não é detalhe.** O `mic.set` é o MUDO NO
    FIRMWARE (camada 3, `ipc_handlers.py:4814`): é o único que apaga a luz
    vermelha do plástico, e a partir dele o botão físico do controle deixa de
    valer — é o que o `title` do desenho já promete. O `speaker.set` manda ZERO
    ao alto-falante guardando o volume preferido (`ipc_handlers.py:4648`).
    Trocar um pelo outro calaria a coisa errada.

    ALTERNAR EXIGE LER O ESTADO, e ele vem do daemon, nunca de memória nossa:
    `audio.mic_mudo` é LEITURA do byte que vem em todo report de input, e
    `speaker.muted` é o que nós mandamos (o aparelho não devolve). Guardar o
    valor enviado como se fosse leitura é o hábito que o `ipc_bridge.py:1141`
    nomeia como o que *"fez a tela parecer mentirosa quando ela nunca mentiu"*.

    `mic_set(False)` NÃO devolve a posse ao `hid-playstation` — isso é
    `mic_set(None)`, que era o botão "Liberar" que ela mandou tirar em 30/08
    (*"o botão do Controle sempre controla a interface"*). Aqui só se alterna
    entre calado e ativo, que é o que os dois estados do selo dizem.

    ONDE AS RECUSAS DESTE GESTO POUSAM, e a resposta mudou em 02/09/2026: no
    CARTÃO daquele controle, por `Piloto._recusou_dizendo`, que deposita todo
    `RuntimeError` em `_recados` e o repinta na hora; a frase vence em 30 s
    (decisão dela: *"é aviso, não estado"*). Até esse dia ela saía no `stderr`
    do processo, e quem clica na janela não lê o terminal de quem a lançou —
    então "recusar dizendo" era verdade no código e mentira na tela. Medido
    aqui com o P1 SEM a chave `audio`: o clique no 🎙 não chamou `mic.set`, e a
    frase de `acao_mic` apareceu dentro do card do `p1` e sobreviveu à
    repintura. A régua da casa é `tests/unit/test_a_recusa_chega_ao_cartao.py`,
    e ela usa justamente este gesto.
    """
    uniq, qual = _uniq(o), str(o.get("mudo") or "")
    if not uniq:
        raise ValueError("mudo: o clique não disse em qual controle")
    dele = ctx.por_uniq(uniq)

    if qual == "microfone":
        # SEM LEITURA, O BOTÃO NÃO CHUTA — e a regra é do motor, palavra por
        # palavra: *"mandar um pedido sem saber o estado atual seria chutar
        # qual é o oposto"* (`controller_card.acao_mic`). Sem a chave `audio`
        # (o instante seguinte a um hotplug-out, quando o handle novo ainda não
        # leu um report íntegro) a linha abaixo fazia `bool(None)` → `False` →
        # `mic_set(True)`: o clique CALAVA um microfone que ninguém sabia se
        # estava calado, e a tela acendia como se soubesse.
        #
        # A FRASE É A DO PRODUTO, e a condição também: `acao_mic(...)` é o dono
        # dos quatro estados deste botão, e `sensivel=False` é exatamente o
        # estado em que a GTK deixa o botão CINZA. Só o `valor` dele não serve
        # aqui — ele inclui a devolução da posse (`None`, o botão "Liberar"),
        # que ela mandou tirar em 30/08 (*"o botão do Controle sempre controla
        # a interface"*). Reusar a regra e não a ação é deliberado, e está
        # escrito para não parecer descuido.
        acao = acao_mic(dele)
        if not acao.sensivel:
            raise RuntimeError(acao.dica)
        # A LEITURA DO FIRMWARE, não o desejo: `mic_mudo` é o que está valendo
        # no plástico agora, e é o que o selo ATIVO/MUDO mostra ao lado.
        agora = bool((dele.get("audio") or {}).get("mic_mudo"))
        # **O BOTÃO É UM ATO SÓ — S-05, e a D-12 dela por extenso:** *"o botão
        # é pra ligar o microfone e ele ser ouvido no canal específico dele"*.
        #
        # O ATO JÁ RODAVA HOJE, e é por isso que esta troca não muda o que o
        # aparelho faz: `ipc_bridge.mic_set_detalhado` passou a DELEGAR ao
        # `mic.canal.set` na ONDA1-D1. O que faltava era a FRASE — aquele
        # embrulho reescreve `status` para `"ok"` assim que o firmware foi
        # pedido, e com isso a metade do CANAL some da resposta. Chamando o ato
        # direto, o `status` só é `"ok"` com as DUAS metades feitas.
        #
        # `ligado` É `agora`, E NÃO `not agora` — a inversão é real e vale a
        # linha: `agora` é *"está mudo"*, então o clique LIGA o microfone
        # exatamente quando ele está mudo. O `mic_set` recebia `muted=not
        # agora`, que é o mesmo pedido dito ao contrário.
        corpo = _corpo(p.mic_canal_set_detalhado(agora, uniq=uniq))
        if corpo is None:
            # A TERCEIRA CAUSA ENTROU NA FRASE PORQUE ELA ACONTECEU — medida na
            # máquina dela em 04/09/2026, com o clique de verdade nesta tela: o
            # daemon INSTALADO é mais velho que esta janela e não conhece
            # `mic.canal.set` (o método é da ONDA1-D1, e o `install.sh` não
            # rodou desde então). A resposta some, o `_corpo` devolve `None`, e
            # a frase que ela leu no cartão listava duas causas — nenhuma delas
            # a verdadeira. Uma frase de recusa que não contém o caso que
            # acontece manda a pessoa procurar o defeito no lugar errado.
            raise RuntimeError(
                "o daemon não confirmou o mudo do microfone — ou o Hefesto "
                "está parado, ou este controle se desligou, ou o Hefesto "
                "instalado é mais velho que esta janela e ainda não sabe "
                "ligar o microfone e o canal dele num ato só")
        # QUAL METADE FALTOU, na frase do dono. `frase_do_ato_do_microfone`
        # devolve `None` quando as duas aconteceram, e o motivo do daemon
        # quando não — é ele que separa *"o canal foi eleito e o firmware ficou
        # represado"* (Modo Nativo) de *"o firmware obedeceu e não há canal"*
        # (o rádio sem a ponte). Um `RuntimeError` genérico aqui devolveria o
        # "não deu" que a D1 mediu não dizendo nada a quem está com o controle
        # na mão.
        frase = frase_do_ato_do_microfone(corpo)
        if frase:
            raise RuntimeError(frase)
        # DE QUEM ERA O MICROFONE — a outra pergunta, e ela é a razão de esta
        # sprint existir HOJE, com quatro DualSense na mesa.
        # `frase_do_ato_do_microfone`, logo acima, responde QUAL METADE faltou;
        # ela não responde em QUE controle o daemon mexeu. Até 06/09/2026 este
        # botão fazia só a primeira pergunta, e um mudo que caísse na rota
        # global calaria o microfone de OUTRA pessoa com a tela pintando o selo
        # do cartão certo — *aparece como sucesso*. É o mesmo par de perguntas
        # que o deslizante do volume já faz, e a resposta vem do MESMO dono.
        #
        # A FRASE É DO PRODUTO, e nenhuma nasce aqui: `frase_do_alvo_do_mic`
        # (`app/widgets/controller_card.py:2191`) é a dona dos três estados, e
        # `alvo_honrado` (`app/ipc_bridge.py:1098`) é quem os lê do corpo. Os
        # dois devolvem "nada a dizer" para `True` e para `None` de propósito —
        # *"não sei" não é "não honrei"*, e inventar a confissão por ausência de
        # notícia acusaria o produto de um erro que ninguém mediu.
        #
        # O QUE O DAEMON DESTA ÁRVORE RESPONDE, medido em 06/09/2026: o corpo
        # de `mic.canal.set` NÃO traz `por_uniq` — quem o traz é o
        # `mic.volume.set` (`daemon/ipc_handlers.py:6164`). O ato do microfone
        # monta a resposta em `AtoDoMicrofone.como_corpo`
        # (`daemon/subsystems/hotkey.py:1388`), e lá o campo não existe. Então
        # `alvo_honrado` devolve `None` aqui, esta linha fica CALADA contra o
        # daemon de hoje, e o silêncio é o certo: quem cobre o alvo errado
        # neste caminho é a metade do CANAL, que recusa dizendo quando a
        # eleição não é deste controle (`_eleger_ou_devolver`) — e essa recusa
        # sobe na `frase` acima. Esta linha é a trava do dia em que o campo
        # existir, e ela é o que impede a terceira causa de 04/09 de se repetir
        # com outro nome: um daemon INSTALADO mais velho que esta janela.
        #
        # **PROVISÓRIO — DECISÃO DELA, E O CONFLITO É DE PALAVRA.** A única
        # frase que o dono tem para este estado é `TEXTO_MIC_ALVO_NAO_HONRADO`,
        # e ela começa por *"O volume foi para o microfone de OUTRO
        # controle"* — foi escrita para o DESLIZANTE, e já nasceu marcada
        # `PROVISÓRIO — decisão dela` no próprio dono
        # (`app/widgets/controller_card.py:613`). Dita depois de um clique no
        # 🎙, ela nomeia um gesto que ela não fez. Escrever uma frase nova aqui
        # é o que esta casa proíbe (texto de tela é dela, e há régua), e mexer
        # no dono é território do motor. Enquanto o daemon não disser
        # `por_uniq` neste caminho, a linha é inerte e ninguém lê a frase
        # errada; no dia em que disser, a palavra é dela — e há régua-estopim
        # cobrando isso antes de a frase chegar à tela
        # (`tests/unit/test_a02_o_botao_confessa_o_alvo_e_o_som_confirma.py`).
        #
        # ELA VEM ANTES DA GRAVAÇÃO pelo motivo que o `volume` já escreve:
        # gravar antes da confissão poria no `controllers[este]` um estado que
        # este controle nunca teve.
        confissao = frase_do_alvo_do_mic(alvo_honrado(corpo))
        if confissao:
            raise RuntimeError(confissao)
        # O PERFIL LEMBRA — e só agora, depois das DUAS metades. A frase acima
        # é a que separa *"o canal foi eleito e o firmware ficou represado"* de
        # *"o firmware obedeceu e não há canal"*: gravar antes dela poria no
        # disco um mudo que o plástico não tem.
        #
        # `not agora` É O QUE FICOU DE PÉ, e a inversão vale a linha: `agora` é
        # *"está mudo"*, e o ato acima LIGA o microfone exatamente quando ele
        # está mudo — logo depois dele o mudo é o oposto do que era.
        _lembrar_do_som(ctx, uniq, mic={"muted": not agora})
        return

    if qual == "alto-falante":
        # A MESMA TRAVA, DO MESMO DONO. `acao_speaker_mudo` devolve
        # `sensivel=False` quando não há volume conhecido, e a razão dele é
        # dura: *"um `muted=True` faria o backend assumir a posse com
        # preferência ZERO, e o `muted=False` seguinte 'restauraria' essa
        # preferência — o par tranca o alto-falante em `{'volume': 0, 'muted':
        # True}` e o próprio botão não tem como soltá-lo (armadilha 2 da
        # SOM-02, executada contra o backend real)"*.
        #
        # ISTO ERA DELEGADO AO DAEMON, e delegar não é travar: a linha abaixo
        # mandava `muted=True` sem volume e contava com a recusa do
        # `ipc_handlers.py:5647` para não estragar nada. Recusa de longe é
        # recusa que depende do outro lado continuar recusando.
        #
        # A FRASE NÃO É A DO MOTOR, e a diferença está medida: `DICA_SPEAKER_
        # SEM_DADO` manda *"use o controle deslizante primeiro"*, e nesta
        # janela ele NÃO EXISTE — `type="range"` aparece zero vez nas dez
        # páginas publicadas (medido em 01/09/2026, e o desenho põe uma barra
        # de pintura no lugar). Mandar alguém a um controle que não está na
        # tela é pior que não dizer nada.
        if not acao_speaker_mudo(dele).sensivel:
            raise RuntimeError(
                "o volume deste alto-falante ainda é desconhecido, e calar "
                "antes de saber o volume tranca-o em zero — nem o próprio "
                "botão o solta depois. O daemon só publica o volume depois de "
                "o Hefesto escrever um.")
        # O MUDO DE AGORA, pelo mesmo dono que a pintura usa. Esta linha era
        # `alto = dele.get("speaker") or {}` seguida de `alto.get("muted")`, e
        # ela era cega à segunda posição do bloco (`entry.inputs.speaker`) —
        # `speaker_do_entry` aceita as duas, e devolve `None` quando não há
        # nenhuma. `muted` é `None` quando o payload traz volume e não traz o
        # mudo: `not None` é `True`, que é o pedido certo (ainda não calamos).
        lido = speaker_do_entry(dele)
        # O VOLUME VAI JUNTO QUANDO SE SABE, e a razão é uma recusa do daemon,
        # não zelo: `speaker.set {muted}` sem volume conhecido é ERRO
        # (`ipc_handlers.py:5647`), porque mudo como primeira escrita tranca o
        # alto-falante em zero e o próprio mudo não o solta. O desenho já apaga
        # o botão nesse estado (`alto_pode` do `aba02.py`); esta linha é a
        # segunda trava, para o clique que chegar mesmo assim.
        pedido_mudo = not bool(lido and lido[1])
        if not p.speaker_set(muted=pedido_mudo, uniq=uniq,
                             **_volume_conhecido(dele)):
            raise RuntimeError(
                "o daemon não confirmou o mudo do alto-falante. Se o volume "
                "deste controle ainda é desconhecido, ele recusa de propósito: "
                "calar antes de saber o volume tranca o alto-falante em zero")
        # O SOM CONFIRMA, e o ♪ é um dos quatro em que a GTK o toca. Calar
        # justamente aqui seria a tela ficando muda no gesto que MEXE no som.
        _confirmar_com_som(ctx, uniq)
        # O PERFIL LEMBRA. O volume não vai nesta chamada porque ele não mudou:
        # quem o preenche é o `_lembrar_do_som`, com a leitura viva — a mesma
        # que a linha acima acabou de reafirmar ao daemon.
        _lembrar_do_som(ctx, uniq, speaker={"muted": pedido_mudo})
        return

    raise ValueError(f"mudo: não sei calar {qual!r} — a página manda 'microfone' "
                     f"ou 'alto-falante'")


@gesto("02-controles.html", "rota", grava="save_profile")
def rota(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Onde o som do controle sai. **"Sons do jogo" tem dono; "Todo o som do PC" não.**

    "SONS DO JOGO" É UM BYTE, e ele é o caso que ela descreveu com o Zelda —
    *"o speaker do controle faz os barulhos da espada do Link enquanto na tela
    tem o som normal do jogo"*. É o `OUTPUT_PATH_SEL` = 2: canal esquerdo para o
    fone/TV, direito para o alto-falante do controle. O `speaker.set` leva a
    `rota` (`ipc_handlers.py:5591`) e a GUI estável manda exatamente isto
    (`controller_card.py:4273`).

    "TODO O SOM DO PC" SÃO DUAS CAMADAS, E A SEGUNDA NÃO É IPC. O
    `profiles/schema.py:523` já escreve o limite com todas as letras:

        LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o
        som do PC" da janela também mexe na CAMADA 1 (o *default sink* do
        PipeWire), que é um fato GLOBAL do sistema (…)

    E `controller_card.py:4218` diz quem vence: *"A camada 1 vence a camada 2:
    volume e rota perfeitos num sink mudo é trabalho invisível."* Quem executa a
    camada 1 é `app/audio_saida.RotaDeSaida.mandar_para_o_controle` (`:820`),
    que roda `pactl set-default-sink` — não há método no daemon para isso, e não
    poderia haver sem inventá-lo.

    **"TODO O SOM DO PC" GANHOU DONO — 04/09/2026, queixa 7 dela.** Ele recusava
    SEMPRE, e a recusa era honesta: mandar `rota=3` sozinho escreveria o byte
    certo e não moveria uma nota de som — o PC continuaria tocando na TV e a
    tela teria acendido o botão. O que estava escrito aqui, e agora está feito:

        O que falta para ligá-lo NÃO é código novo de protocolo: é dar à janela
        nova o dono da camada 1 que a janela velha injeta no card
        (`controller_card.definir_pedido_de_rota`, `:4310`).

    O dono novo é `app/audio_saida.mandar_o_som_do_pc`, e ele NÃO é uma segunda
    implementação: junta a mesma `RotaDeSaida` que a janela antiga usa com a
    mesma resolução de sink (`fontes_de_captura.escolher_sink` mais o casamento
    por dispositivo USB) que o `MicMonitor` faz por dentro — as duas metades que
    a janela nova tinha sem cola.

    **A ORDEM É CAMADA 1 PRIMEIRO, e ela é medida:** *"a camada 1 vence a camada
    2 — volume e rota perfeitos num sink mudo é trabalho invisível"*
    (`controller_card.py:4218`). Se o sink não existe (o RÁDIO, em que o
    DualSense não publica placa de som), este gesto recusa ANTES de escrever o
    byte, dizendo por quê — em vez de deixar o firmware roteado para um canal
    que o sistema não alimenta.

    ELE MANDA AS DUAS, e o "Sons do jogo" também: a janela antiga chama
    `pedir_rota_do_sistema(canal == CANAL_TODO_O_PC)` nos DOIS estados
    (`controller_card.py:4285`) — voltar para "Sons do jogo" DEVOLVE a saída
    padrão do sistema. Fazer só a ida deixaria o som do PC preso no controle sem
    botão nenhum que o soltasse.
    """
    uniq, qual = _uniq(o), str(o.get("rota") or "")
    if not uniq:
        raise ValueError("rota: o clique não disse em qual controle")
    if qual not in ("jogo", "pc"):
        raise ValueError(f"rota: não conheço a rota {qual!r} — a página manda "
                         f"'jogo' ou 'pc'")

    # A CAMADA 1 VEM PRIMEIRO — ver a docstring. `uniqs_na_mesa` é a mesa
    # inteira porque o casamento por dispositivo USB precisa saber de QUEM são
    # as outras placas: com dois DualSense no cabo, sem a lista o `escolher_sink`
    # não tem como vetar a placa do vizinho.
    na_mesa = [str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq")]
    desfecho = (
        audio_saida.mandar_o_som_do_pc(uniq, na_mesa)
        if qual == "pc"
        else audio_saida.devolver_o_som_do_pc()
    )
    # DEVOLVER PODE NÃO TER PARA ONDE, E ISSO NÃO INVALIDA O CLIQUE: se o som
    # nunca esteve no controle, "Sons do jogo" continua sendo só o byte da
    # camada 2, que é o que ele sempre foi. O caminho de IDA é diferente — sem
    # sink não há som a mover, e aí a recusa é a resposta certa.
    if qual == "pc" and not desfecho.ok:
        raise RuntimeError(desfecho.motivo)

    byte_da_rota = ROTA_DO_CANAL[
        CANAL_TODO_O_PC if qual == "pc" else CANAL_SONS_DO_JOGO]
    if not p.speaker_set(rota=byte_da_rota, uniq=uniq,
                         **_volume_conhecido(ctx.por_uniq(uniq))):
        raise RuntimeError(
            "o daemon não confirmou a rota do alto-falante — ou o Hefesto está "
            "parado, ou este controle se desligou")
    # O SOM CONFIRMA A ROTA NOVA, e é o gesto em que ele diz mais: os dois
    # estados prometem som no controle, e o som é o que responde *"por onde ele
    # sai agora"* sem uma palavra na tela. A GTK o toca nos dois estados
    # (`app/widgets/controller_card.py:4286`), e não só na ida.
    _confirmar_com_som(ctx, uniq)
    # O PERFIL LEMBRA A ROTA — e ela é a CAMADA 2, o byte do firmware. A camada
    # 1 (a saída padrão do PipeWire) é um fato GLOBAL do sistema e não cabe num
    # perfil por controle: quem a guarda é a memória do próprio
    # `audio_saida.RotaDeSaida`, que sabe o caminho de volta.
    _lembrar_do_som(ctx, uniq, speaker={"rota": byte_da_rota})


#: O QUE O 🎙 E O ♪ ACEITAM DE VOLUME. O mic é 0-100 por contrato do daemon
#: (`mic.volume.set`, `ipc_handlers.py:5319-5324`); o alto-falante também sai
#: daqui em 0-100 e quem converte para o registrador 0-255 é o dono da curva
#: (`core/speaker_scale.volume_do_percentual`), a MESMA que pinta o `alto-num`.
#: Digitar 255 aqui seria a segunda escala.
VOLUME_MIN, VOLUME_MAX = 0, 100

#: A RECUSA DO `sem_fonte`, e ela nasceu porque o caso ficou FREQUENTE
#: (ONDA5-02-01, 06/09/2026).
#:
#: Até 06/09 o `mic.volume.set` caía na rota global quando o endereço não
#: resolvia, e `sem_fonte` só acontecia quando a máquina inteira não tinha
#: fonte de DualSense nenhuma. **Com a queda fechada ele passa a ser a resposta
#: normal** do controle no rádio sem o canal de microfone de pé.
#:
#: A FRASE DE ANTES MANDAVA PROCURAR NOS DOIS LUGARES ERRADOS: *"ou o Hefesto
#: está parado, ou este controle saiu"*. Nem uma coisa nem outra — o serviço
#: respondeu, o controle está aqui, e o que falta é o microfone existir no
#: sistema. **É o mesmo defeito que o 🎙 já pagou uma vez** (a frase do mudo
#: listava duas causas e nenhuma era a verdadeira, `:2734`), e é a razão de ele
#: não se pagar duas.
#:
#: O QUE ELA NÃO DIZ, e é escolha: nenhum comando, nenhum nome de nó, nenhuma
#: janela para procurar. São três das proibições da língua desta casa, e a
#: quarta é a palavra que descreveria o conjunto dos controles — que sai da
#: tela por decisão dela.
TEXTO_MIC_SEM_FONTE = (
    "O sistema não publica um microfone para este controle: no rádio, é o "
    "canal do microfone que ainda não está de pé; no cabo, é a placa de som "
    "que não apareceu. Nada foi mudado."
)

#: O ESTADO DE CADA INTERRUPTOR DE SENSOR, na língua da TELA.
#:
#: `LIGADO` é o default dela (`D-AUDIO-E-GIRO-NASCEM-LIGADOS`, 25/08/2026) e não
#: acende classe nenhuma — o desenho aprovado já mostra o botão aceso.
#: `DESLIGADO` é o que acende o `.sw.off` que a folha desta aba já tem. O
#: terceiro estado é o travessão de `mesa_viva.SEM_LEITOR`, e ele existe pela
#: mesma razão do `alto-mudo`: um `False` sobre "o daemon não disse" pintaria
#: "desligado" sobre um sensor que ninguém leu.
SENSOR_LIGADO, SENSOR_DESLIGADO = "LIGADO", "DESLIGADO"

#: A ÚNICA RECUSA QUE SOBROU NESTE BOTÃO — e ela é sobre LEITURA, não sobre
#: capacidade.
#:
#: **A FRASE ANTERIOR MORREU EM 04/09/2026, e ela dizia o contrário do que hoje
#: é verdade:** *"não existe método de sensor entre os do Hefesto. Este botão é
#: leitura, não interruptor."* A premissa caiu no mesmo dia, pela decisão dela
#: (*"ele tem que funcionar de verdade. ambos independente do modo e da
#: mascara."*): a ONDA1-D3 pôs `sensor.set` no daemon
#: (`daemon/ipc_handlers._handle_sensor_set`), o registro vivo em
#: `core/virtual_motion.REGISTRO` e o `EVIOCGRAB` do `SensorHub`. Quem mediu a
#: queda foi a régua que a própria recusa deixou armada —
#: `test_o_daemon_continua_sem_metodo_de_sensor` —, e ela previu o desfecho: *"o
#: gesto passa a ter o que chamar"*.
#:
#: O QUE SOBRA DE RECUSA é o mesmo cuidado do 🎙: **sem leitura o botão não
#: chuta.** O daemon publica `sensores.giroscopio_ligado` ao lado de `inputs`
#: (`ipc_handlers._merge_sensores`); sem essa chave, alternar seria adivinhar
#: qual é o oposto — e adivinhar errado deixa o clique dela sem efeito visível
#: nenhum, que é o silêncio que a queixa 8 nomeia.
SEM_LEITURA_DE_SENSOR = (
    "o Hefesto ainda não disse se este sensor está ligado ou desligado, e "
    "alternar sem saber o estado atual seria chutar qual é o oposto. O "
    "interruptor lê `sensores.giroscopio_ligado` do daemon, publicado ao lado "
    "do bloco de entradas deste controle — sem ele, ou o Hefesto está parado, "
    "ou este controle ainda não tem leitor de entradas."
)


@gesto("02-controles.html", "sensor")
def sensor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Giroscópio e Acelerômetro — **os quatro botões que respondiam calados**.

    QUEIXA 8 DELA: *"nem giroscopio e acelerometro"*.  <!-- noqa-acento: citação literal dela -->

    O QUE ACONTECIA, medido: `<button class="sw" data-sensor="giroscopio">` não
    tinha `data-gesto`, e o ouvinte monta o nome como `d.gesto || d.hefGesto ||
    d.papel || doRodape || 'clique'` (`hefesto_vivo.py`). Chegava `"clique"`,
    que aba nenhuma registra, e saía `[gesto sem dono]` **no stderr** — que ela
    nunca vê, porque quem clica na janela não lê o terminal de quem a lançou. É
    a mesma forma que a `mudo` desta aba curou em 02/09, e ela sobreviveu em
    QUATRO botões (dois por card).

    **E ELE DEIXOU DE RECUSAR EM 04/09/2026 — a premissa da recusa MORREU no
    mesmo dia em que a recusa nasceu.** Aqui estava escrito, e era verdade
    quando foi medido de manhã:

        "NÃO HÁ MÉTODO DE SENSOR (…) `daemon.metodos()` não traz um `sensor.*`,
         um `gyro.*` nem um `motion.*`. O `sensor_hub` só LÊ. (…) o fim honesto
         deste botão é virar leitura ou sair da tela."

    A ONDA1-D3 fechou essa ausência à tarde, por decisão dela e contra a
    recomendação de virar leitura: *"ele tem que funcionar de verdade. ambos
    independente do modo e da mascara."*  <!-- noqa-acento: citação literal dela -->
    O daemon ganhou `sensor.set`, o registro vivo (`core/virtual_motion`) e o
    `EVIOCGRAB` do nó "Motion Sensors". **Quem mediu a queda foi a régua que a
    própria recusa deixou armada** — `test_o_daemon_continua_sem_metodo_de_sensor`
    reprovou dizendo *"o botão deixou de precisar recusar, e a frase de recusa
    virou mentira"*, que é o desfecho que ela previa por escrito.

    O QUE ESTE GESTO FAZ AGORA, e por que nesta ordem:

    1. **LÊ o estado**, de `sensores.<qual>_ligado` — a chave que o
       `_merge_sensores` publica ao lado de `inputs`. Sem ela o gesto RECUSA
       (`SEM_LEITURA_DE_SENSOR`) em vez de chutar o oposto: é a mesma
       disciplina do 🎙 três blocos acima, e a razão é a mesma — *"mandar um
       pedido sem saber o estado atual seria chutar qual é o oposto"*;
    2. **CHAMA `sensor.set` com UM campo só.** Campo omitido não mexe naquele
       sensor (contrato do daemon), e é isso que impede o clique no Giroscópio
       de religar o Acelerômetro pelas costas dela;
    3. **DIZ QUAL METADE PEGOU.** `frase_do_interruptor_de_sensor` devolve
       `None` quando o interruptor pegou inteiro e a ressalva do daemon quando
       não: em Modo Nativo o jogo lê o movimento pelo `hidraw` do controle
       FÍSICO, onde o daemon não escreve byte nenhum, e responder "aplicado"
       ali seria o verde falso que a ONDA1-D3 existe para não cometer. A frase
       vai ao cartão daquele controle por 30 s, pelo canal que ela aprovou em
       02/09 (*"é aviso, não estado"*).

    O BOTÃO PINTA PELO QUE O APARELHO DIZ, e não mais pelo desenho: `giro-ligado`
    e `accel-ligado` saem do `pacote` pelo alvo `classe`, acendendo o `.sw.off`
    que a folha desta aba já tinha. Enquanto a página PUBLICADA não tiver os dois
    endereços, o `_so_se_a_pagina_tiver` os segura — e eles acendem sozinhos no
    dia em que ela publicar a bancada.
    """
    uniq, qual = _uniq(o), str(o.get("sensor") or "")
    if not uniq:
        raise ValueError("sensor: o clique não disse em qual controle")
    if qual not in ("giroscopio", "acelerometro"):
        raise ValueError(f"sensor: não conheço o sensor {qual!r} — a página "
                         f"manda 'giroscopio' ou 'acelerometro'")
    agora = _sensor_ligado(ctx.por_uniq(uniq), qual)
    if agora is None:
        raise RuntimeError(SEM_LEITURA_DE_SENSOR)
    # UM CAMPO SÓ, e o nome dele é o que a página mandou. `sensor.set` não mexe
    # no sensor cujo campo veio omitido — mandar os dois faria o clique no
    # Giroscópio reafirmar o Acelerômetro a cada vez.
    corpo = _corpo(p.sensor_set_detalhado(**{qual: not agora}, uniq=uniq))
    if corpo is None:
        raise RuntimeError(
            "o daemon não confirmou o interruptor do sensor — ou o Hefesto "
            "está parado, ou este controle se desligou, ou o Hefesto "
            "instalado é mais velho que esta janela e ainda não conhece "
            "`sensor.set`")
    frase = frase_do_interruptor_de_sensor(corpo)
    if frase:
        raise RuntimeError(frase)


@gesto("02-controles.html", "volume", grava="save_profile")
def volume(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Os DOIS deslizantes — o do microfone e o do alto-falante (D-08).

    DECISÃO DELA: *"Deslizante nos dois."* Até 04/09/2026 os dois volumes eram
    PINTURA: `type="range"` aparecia zero vez nas dez páginas, e o que havia era
    `<span class="trilho"><span class="cheio" style="width:N%">`.

    **E A FALTA DELES TRANCAVA O ♪.** O DualSense não devolve o volume do
    alto-falante, então o daemon só publica a chave `speaker` **depois** de
    alguém ESCREVER um (`ipc_handlers.py:4659`); sem escritor nesta tela, o ♪
    recusava para sempre num controle cujo volume nunca foi ajustado por outro
    caminho — e a frase de recusa original mandava *"use o controle deslizante
    primeiro"*, sobre um deslizante que não existia. Este gesto é o escritor que
    faltava: o primeiro arrasto no trilho do alto-falante destrava o ♪.

    **SÃO DOIS MÉTODOS, E NÃO É DETALHE** — é a metade medida da D-12. O
    `mic.volume.set` mexe no ganho da FONTE no PipeWire (é literalmente *"o
    canal específico dele"*) e **não toca no firmware**: não apaga a luz
    vermelha e não tira o botão físico do controle. O `speaker.set {volume}`
    escreve no registrador do aparelho. Somar os dois num método só *"faria a
    interface prometer uma coisa e entregar outra"* — a docstring do daemon.

    A ESCALA DO ALTO-FALANTE NÃO SE DIGITA: a tela fala 0-100 e o registrador é
    0-255, com uma curva MEDIDA no hardware (`core/speaker_scale.py`, tom de
    1 kHz). É a mesma curva que pinta o `alto-num` e o `alto-barra` ao lado —
    converter à mão aqui faria o número que ela arrasta e o número que ela lê
    discordarem.
    """
    uniq, qual = _uniq(o), str(o.get("volume") or "")
    if not uniq:
        raise ValueError("volume: o clique não disse em qual controle")
    # O `click` QUE VEM DEPOIS DO `change` NÃO É UM SEGUNDO PEDIDO, e o guarda é
    # o mesmo que a aba Iluminação já pôs no trilho de brilho em 03/09: um
    # `<input type="range">` clicado na pista dispara `input`, `change` e
    # `click`, nesta ordem, e o bootstrap escuta os dois últimos. Sem ele, cada
    # clique na pista manda DUAS escritas ao aparelho.
    if (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click"):
        return
    # `valor` É A PORTA: é o que o bootstrap manda de todo elemento que tem
    # `value` (`hefesto_vivo.py:772`), e num `type="range"` é a posição do
    # polegar, como string. O `v` fica como segunda leitura porque é o que a
    # régua compartilhada sabe mandar.
    cru = str(o.get("valor") or o.get("v") or "").strip()
    try:
        pedido = int(float(cru))
    except (TypeError, ValueError):
        raise ValueError(
            f"volume: o deslizante mandou {cru!r}, que não é um número") from None
    if not VOLUME_MIN <= pedido <= VOLUME_MAX:
        raise ValueError(f"volume: {pedido} está fora de "
                         f"{VOLUME_MIN}-{VOLUME_MAX}")

    if qual == "microfone":
        # **A RESPOSTA TEM TRÊS ESTADOS, E O `bool` GUARDAVA DOIS — decisão
        # [08], 04/09/2026.** Na mesa cheia há duas placas de som e a rota
        # global devolve a PRIMEIRA: o daemon atende, responde `ok`, e o
        # microfone que mudou foi o de outra pessoa. O `mic_volume_set`
        # colapsa isso no mesmo `True` de um pedido honrado, e a tela pintava
        # o selo do card certo sobre um número que aquele controle nunca teve.
        #
        # O CAMPO EXISTE DESDE 20/08 (`por_uniq`, `ipc_handlers.py:5595`) e a
        # janela ANTIGA já o lê (`controller_card:4443`). Quem não lia era esta.
        corpo = _corpo(p.mic_volume_set_detalhado(pedido, uniq=uniq))
        # `sem_fonte` TEM FRASE PRÓPRIA, e SÓ ele: os outros `status` continuam
        # com a de sempre. Uma frase nova para cada resposta que o daemon não
        # deu seria inventar recado sobre estado que ninguém mediu.
        if corpo is not None and corpo.get("status") == "sem_fonte":
            raise RuntimeError(TEXTO_MIC_SEM_FONTE)
        if corpo is None or corpo.get("status") != "ok":
            raise RuntimeError(
                "o daemon não confirmou o volume do microfone — ou o Hefesto "
                "está parado, ou este controle se desligou")
        # A CONFISSÃO, NA FRASE DO PRODUTO. `frase_do_alvo_do_mic` é a dona dos
        # três estados e devolve `""` para `True` e para `None` — *"não sei"
        # não é "não honrei", e inventar a confissão por ausência de notícia
        # acusaria o produto de um erro que ninguém mediu*.
        #
        # ELA VAI PELO CANAL DA RECUSA, e é a decisão [08] com todas as
        # letras: *"vira aviso no cartão, como as recusas"*. O `RuntimeError`
        # é o único caminho que deposita frase no cartão daquele controle, e o
        # que ele diz é verdade — este controle não teve o volume mexido. Que
        # OUTRO teve é o que a frase do produto conta.
        confissao = frase_do_alvo_do_mic(alvo_honrado(corpo))
        if confissao:
            raise RuntimeError(confissao)
        # O PERFIL LEMBRA — e SÓ DEPOIS da confissão. O `alvo_honrado` é o que
        # separa *"o ganho deste controle mudou"* de *"o daemon atendeu pela
        # rota global e quem mudou foi o microfone do vizinho"*: gravar antes
        # dela poria no `controllers[este]` um número que este controle nunca
        # teve. A escala é 0-100, a da FONTE de captura — a mesma do
        # `ProfileMicConfig.volume`, e NÃO a 0-255 do alto-falante.
        _lembrar_do_som(ctx, uniq, mic={"volume": pedido})
        return

    if qual == "alto-falante":
        registrador = volume_do_percentual(pedido)
        if not p.speaker_set(volume=registrador, uniq=uniq):
            raise RuntimeError(
                "o daemon não confirmou o volume do alto-falante — ou o Hefesto "
                "está parado, ou este controle se desligou")
        # O SOM CONFIRMA — e ESTE é o arrasto que o pedia. O número que ela
        # acabou de escolher é o que NÓS mandamos: não há leitura de volta hoje,
        # e sem o som ela arrasta sem ter como saber que a mudança valeu.
        _confirmar_com_som(ctx, uniq)
        # O PERFIL LEMBRA O NÚMERO DO PROTOCOLO, e não o da tela: quem guarda
        # 0-255 é `ProfileSpeakerConfig.volume`, e é o mesmo número que acabou
        # de chegar ao aparelho. Converter de novo aqui seria a segunda escala.
        _lembrar_do_som(ctx, uniq, speaker={"volume": registrador})
        return

    raise ValueError(f"volume: não sei ajustar {qual!r} — a página manda "
                     f"'microfone' ou 'alto-falante'")


def _resposta(r: Any) -> tuple[bool, str]:
    """`(ok, motivo)` do `machine_declare`, tolerando ponte que devolva só `bool`.

    `ipc_bridge.machine_declare:861` devolve `(ok, motivo)`, com o motivo já
    traduzido para frase de tela (`_MOTIVOS_MAQUINA`) — é ele que faz o botão
    RECUSAR DIZENDO em vez de gravar calado.

    O guarda existe porque o dublê da régua devolve `True` para todo nome que
    não seja `identity…_set`: desempacotar às cegas levantaria `TypeError`
    DENTRO do teste, e o instrumento reprovaria a si mesmo em vez de medir o
    botão. É o mesmo `_resposta` que a Conexões e a Sistema já têm — três
    cópias de sete linhas, e a única alternativa seria pôr a função no
    `pacotes/ponte.py`, que é território de ninguém nesta leva.
    """
    if isinstance(r, tuple):
        ok, motivo = [*r, None, None][:2]
        return bool(ok), str(motivo or "")
    return bool(r), ""


def _como_o_produto_ve(ctx: Contexto, uniq: str) -> Any:
    """O controle na forma que `pode_ligar_o_mic` e `dica_do_microfone` leem.

    Os quatro campos são os do `DadosDoControle` da GUI estável, e cada um sai
    de uma medição, não de um palpite:

    * `no_cabo` — `transport` do `daemon.state_full` (`"usb"` / `"bt"`), a mesma
      chave que o `mesa_viva.mesa_do_estado:316` já usa nesta janela;
    * `endereco` — o `uniq` normalizado por `core/sysfs_leds.norm_mac`, que é
      **a chave do `maquina.json`** ("doze hex minúsculos por schema",
      `bt_mic.uniqs_declarados`). Ela não se monta à mão: o daemon publica o
      `uniq` ora com os dois-pontos, ora sem, e as duas formas têm de cair na
      mesma chave;
    * `adotado` — `True`, e é afirmação medida: o `state_full["controllers"]`
      sai do `describe_controllers` do controlador de DualSense
      (`ipc_handlers.py:2626`), e cada entrada traz `lightbar_rgb`,
      `player_slot` e `vpad_backend`. Controle externo (8BitDo, Pro) não entra
      por essa porta — ele vem por `controller.list`, que esta aba não lê.
    """
    from types import SimpleNamespace

    dele = ctx.por_uniq(uniq)
    return SimpleNamespace(
        adotado=True,
        no_cabo=str(dele.get("transport") or "").lower() == "usb",
        uniq=uniq,
        endereco=norm_mac(uniq) or "",
    )


@gesto("02-controles.html", "mic-modo")
def mic_modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Virtual" e "Nativo": por onde o som do microfone deste controle chega ao PC.

    O QUE OS DOIS BOTÕES SÃO, e a resposta não estava na palavra "virtual" — a
    primeira leva procurou por ela em `src/`, achou zero, e concluiu que não
    havia dono. A coisa que os `title` do desenho descrevem é a **ponte de
    microfone por Bluetooth**, e ela existe e é dela desde 22/08/2026:

        Virtual  "O Hefesto cria uma fonte de áudio própria e entrega o
                 microfone do controle ao PC por ela."
                 → `integrations/dualsense_bt_audio.py`, que é exatamente isso:
                   Opus tunelado no HID, virando uma fonte do PipeWire.
        Nativo   "O microfone entra como o kernel o expõe, sem o Hefesto no
                 meio."
                 → a ponte no chão. Pelo cabo é o que já acontece: *"por USB o
                   microfone do DualSense é um dispositivo de áudio USB comum e
                   o PipeWire o publica sozinho"* (o cabeçalho daquele módulo).

    QUEM LIGA NÃO É A JANELA, e isso é uma cicatriz, não um detalhe de desenho.
    A GUI estável escreve a DECLARAÇÃO (`machine.declare`) e quem sobe a ponte é
    o daemon; o comentário de `secao_controles.py:1107` diz por quê: *"o
    processo da janela não pode ter esse gesto ao alcance de um clique enquanto
    a posse do hidraw não for arbitrada — o susto de 16/08/2026"*. Aqui é igual:
    este gesto DECLARA, e o `bt_mic` do daemon reconcilia sozinho — a fonte dele
    é **chamável**, relida a cada varredura, e por isso a escolha vale **sem
    reiniciar o daemon** (`daemon/subsystems/bt_mic.py:60`).

    DESLIGAR GRAVA `None`, NUNCA `False`, e a razão é do `utils/maquina.py`:
    *"'nunca pedi' e 'não quero' deixam a ponte no chão do mesmo jeito — e um
    `false` gravado seria um valor de catálogo para o silêncio"*. O `None`
    **sobrescreve** de propósito: `fundir_declaracao:650` declara que *"`None`
    presente na declaração é uma escolha e SOBRESCREVE; só a AUSÊNCIA da chave
    preserva o que havia"*. Sem isso, "Nativo" seria um botão calado.

    **O "VIRTUAL" NÃO RECUSA MAIS NO CABO — 04/09/2026, queixa 15 dela.** O que
    estava escrito aqui, e caiu inteiro:

        NO CABO O "VIRTUAL" RECUSA, e a frase é a do produto —
        `DICA_MIC_NO_CABO`, palavra por palavra. A condição é
        `pode_ligar_o_mic`, também do produto: *"pelo cabo o microfone deste
        controle é uma placa de som USB e não passa por esta ponte — ele já
        funciona sem ela"*. Deixá-lo gravar ali acenderia o botão sem mover uma
        nota de som, que é o defeito que o gesto `rota` desta mesma aba recusa
        pela mesma razão.

    A palavra dela sobre esta recusa: *"esse aviso nao devia aparecer  # (dela) noqa-acento
    pq era pra funcionar em ambos ne"*. <!-- noqa-acento: citação literal dela -->
    E ela tem razão em duas medições independentes:

    * o CSV desta casa diz o CONTRÁRIO da frase — `audio.microfone` é
      `cabo_aciona=sim` / `radio_aciona=parcial`. Quem é parcial é o rádio;
    * ~~a **mesma tela** já promete a simetria que este gesto recusava: o
      `title` do próprio botão "Virtual"~~ — **ESTE ARGUMENTO CAIU em
      08/09/2026, e a razão é a armadilha da prosa numa forma nova: A FRASE DA
      TELA VIROU O ARGUMENTO.** Um `title` que ninguém tinha medido foi usado
      como PROVA para mudar comportamento. Medido, ele prometia três coisas e
      as três descreviam OUTRO botão: *"cria uma fonte de áudio própria"* só
      acontece no rádio (no cabo o filtro de `nos_dualsense_bluetooth` descarta
      o nó e este gesto só grava a chave), *"entrega o microfone ao PC"* é o
      🎙, pelo gesto `mudo`, e a simetria é contradita pela linha
      `audio.microfone.mudo@dualsense` do mapa (`radio_aciona=parcial`, com a
      assimetria declarada desde 03/08/2026, MIC-BT-DONO-01).
      A CONCLUSÃO DO GESTO NÃO DEPENDIA DISTO e fica de pé pelos dois motivos
      abaixo, que são sobre o que o código FAZ.
      **A FRASE SAIU DA TELA na segunda volta** (`aba02.DICA_MIC_VIRTUAL`): o
      texto novo diz o que ESTE botão faz e manda para o 🎙, que faz a outra
      metade. Ele não confessa dívida — o que falta mora no mapa, nunca na
      página. A régua é
      `tests/unit/test_a02_o_tooltip_do_virtual_diz_o_que_o_botao_faz.py`.

    O paralelo com o gesto `rota` também não se sustentava: lá o botão promete
    MOVER SOM AGORA e só metade do caminho existe; aqui a declaração é DURÁVEL,
    e o `bt_mic.alvos()` — que só enxerga nós de Bluetooth — garante que ela não
    acende nada no cabo. Declarar pelo cabo não mente sobre som nenhum.

    A PERGUNTA QUE ESTE GESTO FAZ AGORA é `tem_canal_de_captura`, e não "é
    cabo?" — a D-12 dela: *"o botão é pra ligar o microfone e ele ser ouvido no
    canal específico dele"*. O dono da resposta já existia e já sabia os dois
    transportes (`eleicao_de_microfone._canal_no_ar`: *"o caso do CABO, que
    publica sozinho"*).

    O "NATIVO" GRAVA NOS DOIS TRANSPORTES, e agora o "Virtual" também: no cabo
    ele afirma o que já é verdade E deixa escrito o que vale quando este
    controle for para o rádio. É declaração durável, não gesto de momento — o
    `maquina.json` é o que o daemon lê no próximo boot.
    """
    uniq, qual = _uniq(o), str(o.get("micModo") or "")
    if not uniq:
        raise ValueError("mic-modo: o clique não disse em qual controle")
    if qual not in ("virtual", "nativo"):
        raise ValueError(f"mic-modo: não conheço o modo {qual!r} — a página "
                         f"manda 'virtual' ou 'nativo'")

    dados = _como_o_produto_ve(ctx, uniq)
    # A ÚNICA RECUSA QUE SOBROU, e ela não é sobre transporte: sem canal de
    # captura não há microfone a ligar, e sem endereço não há onde gravar a
    # escolha. As duas juntas SÃO o `pode_ligar_o_mic` do produto — a mesma
    # condição que a GTK usa para acender o interruptor no card, e é ele que se
    # chama aqui, não uma cópia das duas perguntas. **A diferença não é de
    # estilo: com a cópia, devolver o `not no_cabo` ao produto deixaria a janela
    # antiga recusando e esta aceitando, e nenhuma régua desta casa veria.**
    # Medido nesta leva, arrancando a cura: com a cópia, a MORDIDA passou verde.
    #
    # Vale para os DOIS botões: declarar "Nativo" sem endereço também não tem
    # onde pousar.
    if not _mic_do_produto.pode_ligar_o_mic(dados):
        raise RuntimeError(_mic_do_produto.dica_do_microfone(dados))

    ok, motivo = _resposta(p.machine_declare(
        {"controles": {dados.endereco: {
            "microfone": True if qual == "virtual" else None}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o modo do microfone")
    # O DISCO MUDOU, ENTÃO A LEITURA EM CACHE MORREU — e ela morre AQUI, não no
    # tique seguinte por acaso. `_controles_declarados` guarda o `maquina.json`
    # porque ele só muda por gesto dela; este É o gesto. Sem esta linha, o botão
    # aceso continuaria sendo o de antes do clique até alguém reabrir a janela —
    # que é o mesmo "botão que grava e não diz nada" que esta leva veio matar.
    _controles_declarados(recarregar=True)


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
#: **`mic_set` SAIU E `mic_canal_set_detalhado` ENTROU — 04/09/2026, S-05.** O
#: 🎙 chama o ATO inteiro (a D-12 dela), e o `mic_volume_set` virou
#: `mic_volume_set_detalhado` pela decisão [08] — o `bool` daquele guardava o
#: `por_uniq`, que é a diferença entre mexer no microfone dela e no de outra
#: pessoa.
#: **`sensor_set_detalhado` ENTROU — 04/09/2026.** O interruptor de giroscópio
#: e acelerômetro deixou de recusar e passou a chamar: a ONDA1-D3 pôs
#: `sensor.set` no daemon no mesmo dia, e a variante `_detalhado` é a que
#: carrega o `alcance` e a `ressalva` — o `bool` da irmã estreita apagaria
#: justamente a metade que diz que em Modo Nativo o giro continua chegando ao
#: jogo pelo `hidraw` do físico.
PONTE = {"mic_canal_set_detalhado", "speaker_set", "machine_declare",
         "mic_volume_set_detalhado", "sensor_set_detalhado"}
#: VAZIO, e o vazio é uma AFIRMAÇÃO: os TRÊS métodos desta aba têm função no
#: `ipc_bridge`, então nenhum gesto precisa do degrau cru do `p.chamar`.
METODOS: set[str] = set()

#: O QUE O DAEMON NÃO PUBLICA DE VOLTA — e por isso a tela não pode confirmar
#: sozinha que o gesto pegou.
#:
#: O `machine.declare` está **fora do `daemon.state_full` de propósito**, e o
#: handler diz a razão (`ipc_handlers.py:5588`): *"aquilo é o tique de 20 Hz, e
#: a declaração muda por gesto dela, não por quadro"*. Ele grava em disco
#: (`maquina.json`), e a única confirmação é o `(ok, motivo)` da chamada — que é
#: exatamente por que o gesto levanta com o motivo em vez de voltar calado.
#:
#: CONSEQUÊNCIA NA TELA, e ela é dívida DECLARADA: o botão aceso continua sendo
#: o que o gerador desenhou. **A RAZÃO ESCRITA AQUI CAIU** — dizia que *"a
#: pintura do piloto só sabe escrever texto, largura, fundo e `value` — não
#: sabe acender uma classe"*, e o piloto ganhou o alvo `classe` em 02/09/2026
#: (`hefesto_vivo.py:499-515`), com `data-hef-quando` para escolher qual do
#: grupo acende. O que falta agora é do GERADOR e da publicação dela: os dois
#: botões precisam de `data-campo`/`data-hef-alvo="classe"`/`data-hef-quando`,
#: e a página publicada precisa recebê-los. Depois de clicar "Nativo", o
#: "Virtual" segue aceso até o gerador rodar de novo.
#:
#: NÃO FOI FEITO NESTA LEVA de propósito: `mic-modo` é o laço do microfone, e o
#: `data-campo` naquele container já APAGOU os dois botões uma vez (01/09/2026,
#: `[data-mic-modo]` de 4 para 0, medido no Chrome) — endereçá-lo nas pressas é
#: repetir o defeito que o comentário do `mic-modo` lá em cima guarda.
#: TUPLA, e não dicionário com o motivo: as outras cinco abas ligadas declaram
#: assim (`a03`, `a05`, `a08`, `a09`, `a10`) e o piloto faz
#: `set(getattr(mod, "SEM_ECO", ()))` — um dicionário passaria, e seria a sexta
#: gramática para a mesma lista. O motivo fica no comentário, que é onde ele
#: cabe inteiro.
SEM_ECO = ("mic-modo",)


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso e as provas moram AQUI, e não no
#: arquivo de teste, para que ligar uma aba não exija editar um arquivo que oito
#: pessoas editariam ao mesmo tempo. O `PAGINA` que elas leem é o do topo — ele
#: era redigitado aqui, e duas cópias do mesmo nome de arquivo é a segunda
#: verdade que esta casa não guarda.
#: **CINCO GESTOS, NOVE PEÇAS POR CARD — 04/09/2026.** Eram três gestos e cinco
#: botões; entraram o `sensor` (o Giroscópio e o Acelerômetro, que emitiam um
#: gesto chamado `clique` e morriam no stderr) e o `volume` (os dois deslizantes
#: da D-08). O piso conta GESTOS porque é o que o despachante registra — a
#: cobertura por peça está nas PROVAS abaixo.
#:
#: O `mudo` atende o 🎙 e o ♪ (mesmo `data-mudo`), o `mic-modo` atende o Virtual
#: e o Nativo, o `rota` atende os dois do alto-falante, o `sensor` atende os dois
#: interruptores e o `volume` atende os dois deslizantes.
PISO_DA_ABA = 5
#: OS DOIS BOTÕES DE CALAR SAÍRAM DESTA LISTA EM 02/09/2026, e a razão é da
#: FIXTURE, não deles. O controle da régua compartilhada é
#: `test_os_botoes_tem_dono.FALSO`, e ele traz `audio: {}` e `speaker: {}` — um
#: controle cujo mudo do microfone e cujo volume são DESCONHECIDOS. Nesse
#: estado o motor manda o botão ficar INSENSÍVEL (`acao_mic`,
#: `acao_speaker_mudo`), e as duas provas cobravam a chamada — isto é, cobravam
#: o CHUTE como comportamento esperado:
#:
#:     mic_set(not bool(None))    → mic_set(True)   calava sem saber se calado
#:     speaker_set(muted=True)    sem volume        o par tranca o alto-falante
#:                                                  em zero, e nem ele o solta
#:
#: A COBERTURA NÃO SUMIU, ela MUDOU DE CASA e DOBROU:
#: `tests/unit/test_a_aba_controles_reusa_o_motor.py` prova os dois botões nas
#: DUAS pernas — a recusa (com a frase do produto) e a ação (com a leitura no
#: payload, `mic_set(True)` e `speaker_set(muted=True, volume=102)`). É mais do
#: que esta lista alcançava, porque lá o controle da régua pode ter estado.
#:
#: O QUE FALTA, e é de outro território: o `FALSO` da régua compartilhada
#: precisa crescer (`"audio": {"mic_mudo": False}` e `"speaker": {"volume":
#: 102, "muted": False}`). Enquanto ele descrever um controle sem leitura
#: nenhuma, aba alguma pode provar ali um botão que recusa com honestidade — e
#: o arquivo é de todas as dez, editado por oito frentes em paralelo.
PROVAS = [
    # "Sons do jogo" — a rota sai da constante, nunca do número digitado.
    {"pagina": PAGINA, "gesto": "rota", "clique": {"rota": "jogo"},  # (noqa-acento) id
     "chama": [("speaker_set", [],
                {"rota": SAIDA_L_FONE_R_ALTO_FALANTE, "uniq": "aa:bb:cc:00:00:01"})]},
    # "NATIVO". O controle da régua está no CABO (`transport: "usb"`,
    # `test_os_botoes_tem_dono.FALSO`).
    #
    # O `None` É O VALOR, E NÃO A AUSÊNCIA: um `{}` aqui passaria com o gesto
    # mandando qualquer coisa. E a CHAVE é o `uniq` sem os dois-pontos — é o que
    # o `norm_mac` devolve, e é a chave que o `maquina.json` tem.
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "nativo"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": None}}}], {})]},
    # "VIRTUAL" NO CABO — A PROVA DA QUEIXA 15, e ela é NOVA em 04/09/2026.
    # Aqui estava escrito que uma prova assim *"estaria pedindo ao botão que
    # mentisse"*, porque o "Virtual" recusava no cabo. A recusa caiu com a D-12
    # e é ESTA linha que a mede: o mesmo controle no cabo, o mesmo `uniq`, e
    # agora `machine_declare` é CHAMADO. Se alguém devolver o `not no_cabo` a
    # `pode_ligar_o_mic`, esta prova reprova na hora — que é o que a régua
    # compartilhada faltava fazer.
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "virtual"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": True}}}], {})]},
    # OS DOIS DESLIZANTES (D-08). O do microfone manda o número CRU (0-100 é o
    # contrato do `mic.volume.set`); o do alto-falante passa pela curva medida no
    # hardware — 80 % vira 187 no registrador, e é `volume_do_percentual` quem
    # diz isso, nunca uma regra de três escrita aqui.
    # O DO MICROFONE CHAMA A VARIANTE `_detalhado` — decisão [08], 04/09/2026.
    # O `bool` do `mic_volume_set` colapsava o `por_uniq` do daemon, que é a
    # diferença entre mexer no microfone deste controle e no de outra pessoa.
    {"pagina": PAGINA, "gesto": "volume",  # (noqa-acento) id
     "clique": {"volume": "microfone", "v": "80"},
     "chama": [("mic_volume_set_detalhado", [80], {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "volume",  # (noqa-acento) id
     "clique": {"volume": "alto-falante", "v": "80"},
     "chama": [("speaker_set", [],
                {"volume": volume_do_percentual(80),
                 "uniq": "aa:bb:cc:00:00:01"})]},
]

#: O QUE ESTA ABA PROVA PELA RECUSA, e não pela chamada — 04/09/2026.
#:
#: **A RAZÃO DO `sensor` AQUI MUDOU NO MESMO DIA, e a antiga era esta:** *"o
#: `sensor` não tem o que chamar: não há método de sensor no daemon"*. Tinha, à
#: tarde: a ONDA1-D3 pôs `sensor.set`, e o gesto passou a chamá-lo.
#:
#: ELE CONTINUA FORA DAS `PROVAS`, e agora pela MESMA razão que tirou os dois
#: botões de calar em 02/09 — **é da FIXTURE, não do botão**. O controle da
#: régua compartilhada (`test_os_botoes_tem_dono.FALSO`) não traz o bloco
#: `sensores`, que é a chave nova do payload; nesse estado o gesto RECUSA em vez
#: de chutar o oposto (ver `SEM_LEITURA_DE_SENSOR`), e uma entrada em `PROVAS`
#: aqui cobraria o CHUTE como comportamento esperado.
#:
#: A COBERTURA MORA EM `tests/unit/test_a02_som_e_sensor_falam_quando_recusam.py`,
#: que monta o controle COM o bloco e prova as duas pernas: a chamada de um
#: campo só (`sensor_set_detalhado(giroscopio=False, uniq=…)`) e a ressalva do
#: Modo Nativo virando aviso no cartão.
#:
#: Esta lista existe para que a próxima pessoa não leia a ausência do `sensor`
#: em `PROVAS` como "botão sem dono" — foi assim que os quatro passaram uma leva
#: inteira despercebidos.
SEM_CHAMADA = ("sensor",)
