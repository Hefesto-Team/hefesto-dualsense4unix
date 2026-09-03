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
(`paginas/02-controles.html:1678` e `:2009`), e o `hidden` é LITERAL no gerador
(`aba02.py:1170`), sem condição; o `escrever` do piloto não toca o atributo
`hidden` em nenhum dos seus alvos. O "102%" ia para um vão invisível.

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
from typing import Any

from hefesto_dualsense4unix.app.actions.home_actions import mascara_viva
from hefesto_dualsense4unix.app.widgets.controller_card import (
    acao_mic,
    acao_speaker_mudo,
    rotulo_lightbar,
    speaker_do_entry,
    touchpad_do_inputs,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques, texto_volume
from hefesto_dualsense4unix.core.speaker_scale import percentual_do_volume

from . import Contexto, registrar

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


def toque_do_controle(inputs: Any) -> tuple[str, str]:
    """`(palavra, ponto)` do touchpad — as duas linhas da GTK, num par.

    `palavra` é o `touch-estado`; `ponto` é o `touch-ponto`, que o desenho lê
    como CLASSE (`data-hef-alvo="classe"`): `""` apaga o pontinho e qualquer
    outra coisa o acende (`hefesto_vivo.BOOTSTRAP::ligado`).

    Sem leitura, os DOIS dizem "não sei": a palavra vira o travessão e o ponto
    apaga. Apagar aqui não é afirmar "ninguém está tocando" — é a mesma recusa
    que a GTK faz escondendo o bloco inteiro, e é a única coisa que esta tela
    pode fazer sem inventar uma posição.
    """
    lido = touchpad_do_inputs(inputs)
    if lido is None:
        import mesa_viva

        return (str(mesa_viva.SEM_LEITOR), "")
    tocando = bool(lido[0])
    return (texto_toques(1 if tocando else 0), "sim" if tocando else "")

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
#: (`hefesto_vivo.py:217` e `:246`), e o comentário do `cor` cita exatamente
#: esta linha como a dívida que ele veio pagar. Guardar a frase antiga ao lado
#: da certa obrigaria a próxima pessoa a escolher entre duas afirmações.
#:
#: O QUE FALTA AGORA NÃO É O ALVO, É A PALAVRA DELA: trocar `[L3]` por uma
#: mudança de cor é mudar o que a tela DIZ, e texto de tela é decisão dela. O
#: caminho está aberto e custa duas linhas — o `data-hef-alvo="cor"` no
#: `.rotl` do gerador e a cor emitida aqui.
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
# piloto abre SEMPRE o publicado (`hefesto_vivo.py:1290`, `:1478`, `:1650`), e
# contar as casas da bancada endereçaria o que o `WebView` não tem.
#: O NOME DA PÁGINA, e ele é UM só neste arquivo: a régua dos gestos o lê lá
#: embaixo, o `_enderecos_da_pagina` o lê aqui, e o `@registrar` o repete porque
#: o decorador roda antes de qualquer coisa que este módulo defina.
PAGINA = "02-controles.html"

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
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # `inputs` TEM TRÊS ESTADOS, E O PRODUTO SÓ ENXERGAVA DOIS. O `or {}`
        # abaixo continua servindo para LER campo por campo; o que ele NÃO pode
        # decidir é se houve leitura — `None` e `{}` viram o mesmo dicionário
        # vazio, e daí em diante "não sei" é indistinguível de "solto".
        # Medido em 02/09/2026, com os dois controles dela ligados: só o
        # `is_primary` traz `inputs`; o outro vem `None`
        # (`daemon/ipc_handlers.py:3379-3383`).
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
        # se lê, só se escreve (`ipc_handlers.py:4600`).
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
        sabemos = isinstance(a.get("mic_mudo"), bool)
        mudo = bool(a.get("mic_mudo"))
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
        toque_txt, toque_ponto = toque_do_controle(e)
        cards[uniq] = {
            "bateria": f"{pct}%" if pct is not None else "—",
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
            # `data-hef` (`hefesto_vivo.py:180`), e nenhum dos três existe para
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
            "luz-hex": luz_hex(rotulo_da_luz, base_da_luz),
            # UM DONO SÓ para o selo, nos dois pintores (auditoria 02/09/2026):
            # `mesa_viva.selo_do_mic`. O ternário estava escrito duas vezes, e
            # a régua do outro lado olhava o TEXTO — a cura de lá caía calada.
            "mic-selo": mesa_viva.selo_do_mic(mudo, sabemos),
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
            #      (`ipc_handlers.py:3584`, `:4799`). Com o valor vivo de hoje —
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
            #      (`ipc_handlers.py:4600`) — antes dele a tela afirmava "0%"
            #      sobre um alto-falante que ninguém mediu, que é o gêmeo exato
            #      do "Sem toque" logo abaixo. `speaker_do_entry` devolve `None`
            #      nesse caso, e `None` é o travessão.
            "alto-estado": (
                texto_volume(*sp_lido) if sp_lido is not None else mesa_viva.SEM_LEITOR
            ),
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
                "touch-ponto": toque_ponto,
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
            }),
        }
    return {"cards": cards, "sem_dono": {},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()), "sem_dono": 0}}


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
#   🎙  data-mudo="microfone"      `mic.set`      (ipc_handlers.py:4755)
#   ♪   data-mudo="alto-falante"   `speaker.set`  (ipc_handlers.py:4589)
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
#   Todo o som do PC            metade dele é `pactl set-default-sink`, que não
#                               é IPC. Ver o gesto `rota`.
#   Calibrar / Mapa do Controle são `<a href>`, navegação — não IPC.
#   Os dois deslizantes de volume   NÃO EXISTEM como elemento clicável. Medido
#                               em 01/09/2026: `type="range"` aparece **zero**
#                               vez nos 16 HTML de `layout/`. O que o desenho
#                               tem é `<span class="trilho"><span class="cheio"
#                               style="width:N%">` — pintura, sem `value` e sem
#                               nenhum `data-*`, logo o `closest` do ouvinte
#                               (`hefesto_vivo.py:204`) nem dispara.
#                               O DAEMON ATENDE OS DOIS (`mic.volume.set` e
#                               `speaker.set {volume}`, e a ponte tem
#                               `mic_volume_set`/`speaker_set`): o que falta é
#                               do lado do DESENHO, e desenho é dela.
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
# widget). Reescrevê-las seria a segunda verdade: a condição "só no rádio" e a
# frase que a explica já existem, com dono, e são exatamente o que este botão
# precisa dizer quando recusa.
#
# `norm_mac` é o dono da CHAVE do `maquina.json` — doze hex minúsculos. O daemon
# publica o `uniq` ora com dois-pontos, ora sem, e montar a chave à mão aqui
# gravaria a declaração num controle que não existe.
#
# A ORDEM DESTE BLOCO É A DO `ruff --select I`, não a da leitura: um bloco fora
# de ordem reprova o portão de lint, e é ele que decide a integração.
from hefesto_dualsense4unix.app.actions.config import (  # noqa: E402
    secao_controles as _mic_do_produto,
)
from hefesto_dualsense4unix.core.ds_output_report import (  # noqa: E402
    SAIDA_L_FONE_R_ALTO_FALANTE,
)
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402

from . import gesto  # noqa: E402


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
    `speaker` depois do primeiro `speaker.set` (`ipc_handlers.py:4600`). Mandar
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


@gesto("02-controles.html", "mudo")
def mudo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O 🎙 e o ♪ — os dois botões de calar, e eles ALTERNAM o que a tela mostra.

    UM GESTO PARA OS DOIS porque a página os marca com o mesmo `data-mudo`, e o
    valor dele diz qual. Separá-los em dois nomes inventaria um vocabulário que
    o desenho não tem.

    **São métodos diferentes, e não é detalhe.** O `mic.set` é o MUDO NO
    FIRMWARE (camada 3, `ipc_handlers.py:4755`): é o único que apaga a luz
    vermelha do plástico, e a partir dele o botão físico do controle deixa de
    valer — é o que o `title` do desenho já promete. O `speaker.set` manda ZERO
    ao alto-falante guardando o volume preferido (`ipc_handlers.py:4589`).
    Trocar um pelo outro calaria a coisa errada.

    ALTERNAR EXIGE LER O ESTADO, e ele vem do daemon, nunca de memória nossa:
    `audio.mic_mudo` é LEITURA do byte que vem em todo report de input, e
    `speaker.muted` é o que nós mandamos (o aparelho não devolve). Guardar o
    valor enviado como se fosse leitura é o hábito que o `ipc_bridge.py:1082`
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
        if not p.mic_set(not agora, uniq=uniq):
            raise RuntimeError(
                "o daemon não confirmou o mudo do microfone — ou o Hefesto está "
                "parado, ou este controle saiu da mesa")
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
        # `ipc_handlers.py:4682` para não estragar nada. Recusa de longe é
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
        # (`ipc_handlers.py:4682`), porque mudo como primeira escrita tranca o
        # alto-falante em zero e o próprio mudo não o solta. O desenho já apaga
        # o botão nesse estado (`alto_pode` do `aba02.py`); esta linha é a
        # segunda trava, para o clique que chegar mesmo assim.
        if not p.speaker_set(muted=not bool(lido and lido[1]), uniq=uniq,
                             **_volume_conhecido(dele)):
            raise RuntimeError(
                "o daemon não confirmou o mudo do alto-falante. Se o volume "
                "deste controle ainda é desconhecido, ele recusa de propósito: "
                "calar antes de saber o volume tranca o alto-falante em zero")
        return

    raise ValueError(f"mudo: não sei calar {qual!r} — a página manda 'microfone' "
                     f"ou 'alto-falante'")


@gesto("02-controles.html", "rota")
def rota(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Onde o som do controle sai. **"Sons do jogo" tem dono; "Todo o som do PC" não.**

    "SONS DO JOGO" É UM BYTE, e ele é o caso que ela descreveu com o Zelda —
    *"o speaker do controle faz os barulhos da espada do Link enquanto na tela
    tem o som normal do jogo"*. É o `OUTPUT_PATH_SEL` = 2: canal esquerdo para o
    fone/TV, direito para o alto-falante do controle. O `speaker.set` leva a
    `rota` (`ipc_handlers.py:4626`) e a GUI estável manda exatamente isto
    (`controller_card.py:4271`).

    "TODO O SOM DO PC" SÃO DUAS CAMADAS, E A SEGUNDA NÃO É IPC. O
    `profiles/schema.py:516` já escreve o limite com todas as letras:

        LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o
        som do PC" da janela também mexe na CAMADA 1 (o *default sink* do
        PipeWire), que é um fato GLOBAL do sistema (…)

    E `controller_card.py:4218` diz quem vence: *"A camada 1 vence a camada 2:
    volume e rota perfeitos num sink mudo é trabalho invisível."* Quem executa a
    camada 1 é `app/audio_saida.RotaDeSaida.mandar_para_o_controle` (`:820`),
    que roda `pactl set-default-sink` — não há método no daemon para isso, e não
    poderia haver sem inventá-lo.

    ENTÃO ELE RECUSA DIZENDO, em vez de mandar só a metade que dá. Mandar
    `rota=3` sozinho escreveria o byte certo e não moveria uma nota de som: o PC
    continuaria tocando no alto-falante da TV, e a tela teria acendido o botão.
    É a forma exata do defeito que esta casa chama de *ausência de notícia lida
    como sucesso* — e o `--prova-gesto` daria verde por cima dele.

    O que falta para ligá-lo NÃO é código novo de protocolo: é dar à janela nova
    o dono da camada 1 que a janela velha injeta no card
    (`controller_card.definir_pedido_de_rota`, `:4310`). Enquanto isso não
    existir, este botão é honesto ao recusar.
    """
    uniq, qual = _uniq(o), str(o.get("rota") or "")
    if not uniq:
        raise ValueError("rota: o clique não disse em qual controle")

    if qual == "pc":
        raise RuntimeError(
            "'Todo o som do PC' ainda não tem dono nesta janela: metade dele é "
            "a saída padrão do PipeWire (pactl set-default-sink), que não é IPC "
            "— o daemon só faz a camada 2, o byte do firmware. Mandar só ela "
            "acenderia o botão sem mover som nenhum.")

    if qual != "jogo":
        raise ValueError(f"rota: não conheço a rota {qual!r} — a página manda "
                         f"'jogo' ou 'pc'")

    if not p.speaker_set(rota=SAIDA_L_FONE_R_ALTO_FALANTE, uniq=uniq,
                         **_volume_conhecido(ctx.por_uniq(uniq))):
        raise RuntimeError(
            "o daemon não confirmou a rota do alto-falante — ou o Hefesto está "
            "parado, ou este controle saiu da mesa")


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
      (`ipc_handlers.py:2567`), e cada entrada traz `lightbar_rgb`,
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

    NO CABO O "VIRTUAL" RECUSA, e a frase é a do produto — `DICA_MIC_NO_CABO`,
    palavra por palavra. A condição é `pode_ligar_o_mic`, também do produto:
    *"pelo cabo o microfone deste controle é uma placa de som USB e não passa
    por esta ponte — ele já funciona sem ela"*. Deixá-lo gravar ali acenderia o
    botão sem mover uma nota de som, que é o defeito que o gesto `rota` desta
    mesma aba recusa pela mesma razão.

    O "NATIVO" GRAVA NOS DOIS TRANSPORTES, e é diferente de propósito: no cabo
    ele afirma o que já é verdade E deixa escrito que, quando este controle for
    para o rádio, o Hefesto fica fora. É declaração durável, não gesto de
    momento — o `maquina.json` é o que o daemon lê no próximo boot.
    """
    uniq, qual = _uniq(o), str(o.get("micModo") or "")
    if not uniq:
        raise ValueError("mic-modo: o clique não disse em qual controle")
    if qual not in ("virtual", "nativo"):
        raise ValueError(f"mic-modo: não conheço o modo {qual!r} — a página "
                         f"manda 'virtual' ou 'nativo'")

    dados = _como_o_produto_ve(ctx, uniq)
    if not dados.endereco:
        raise RuntimeError(_mic_do_produto.DICA_MIC_SEM_ENDERECO)
    if qual == "virtual" and not _mic_do_produto.pode_ligar_o_mic(dados):
        raise RuntimeError(_mic_do_produto.dica_do_microfone(dados))

    ok, motivo = _resposta(p.machine_declare(
        {"controles": {dados.endereco: {
            "microfone": True if qual == "virtual" else None}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o modo do microfone")


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"mic_set", "speaker_set", "machine_declare"}
#: VAZIO, e o vazio é uma AFIRMAÇÃO: os TRÊS métodos desta aba têm função no
#: `ipc_bridge`, então nenhum gesto precisa do degrau cru do `p.chamar`.
METODOS: set[str] = set()

#: O QUE O DAEMON NÃO PUBLICA DE VOLTA — e por isso a tela não pode confirmar
#: sozinha que o gesto pegou.
#:
#: O `machine.declare` está **fora do `daemon.state_full` de propósito**, e o
#: handler diz a razão (`ipc_handlers.py:5301`): *"aquilo é o tique de 20 Hz, e
#: a declaração muda por gesto dela, não por quadro"*. Ele grava em disco
#: (`maquina.json`), e a única confirmação é o `(ok, motivo)` da chamada — que é
#: exatamente por que o gesto levanta com o motivo em vez de voltar calado.
#:
#: CONSEQUÊNCIA NA TELA, e ela é dívida DECLARADA: o botão aceso continua sendo
#: o que o gerador desenhou. **A RAZÃO ESCRITA AQUI CAIU** — dizia que *"a
#: pintura do piloto só sabe escrever texto, largura, fundo e `value` — não
#: sabe acender uma classe"*, e o piloto ganhou o alvo `classe` em 02/09/2026
#: (`hefesto_vivo.py:217-224`), com `data-hef-quando` para escolher qual do
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
#: TRÊS GESTOS, CINCO BOTÕES: o `mudo` atende o 🎙 e o ♪ (mesmo `data-mudo`) e o
#: `mic-modo` atende o Virtual e o Nativo (mesmo `data-mic-modo`). O piso conta
#: GESTOS porque é o que o despachante registra — a cobertura por botão está nas
#: PROVAS abaixo, que são quatro.
PISO_DA_ABA = 3
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
    # "NATIVO", e a prova é ele porque o controle da régua está no CABO
    # (`transport: "usb"`, `test_os_botoes_tem_dono.FALSO`). O "Virtual" ali
    # RECUSA — é o `pode_ligar_o_mic` do produto —, e uma prova que exigisse
    # chamada dele estaria pedindo ao botão que mentisse. Quem cobra a recusa é
    # o teste da mordida, e não esta lista.
    #
    # O `None` É O VALOR, E NÃO A AUSÊNCIA: um `{}` aqui passaria com o gesto
    # mandando qualquer coisa. E a CHAVE é o `uniq` sem os dois-pontos — é o que
    # o `norm_mac` devolve, e é a chave que o `maquina.json` tem.
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "nativo"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": None}}}], {})]},
]
