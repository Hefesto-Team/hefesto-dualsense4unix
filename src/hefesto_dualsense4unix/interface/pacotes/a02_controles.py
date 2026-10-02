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
que resta é o comentário que registra a saída — o do parâmetro `estado_alto`
na assinatura de `aba02.bloco`. O número que estava aqui apontava para uma
linha em branco desde a primeira edição que empurrou o gerador — citação de
linha que sobrevive ao código que citava é endereço morto, e esta casa mede
isso (`citacoes-no-codigo`).

**E O ENDEREÇO NOVO NÃO TEM NÚMERO, de propósito — 11/09/2026 (LINGUA-A3).**
A troca dos nomes das rotas do som empurrou o `aba02.py` e a âncora `:1939`
caiu em linha vazia; o portão pegou. Um endereço por SÍMBOLO não envelhece com
o arquivo, que é a única forma de esta nota sobreviver à próxima edição.

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

import contextlib
import re
import threading
from collections.abc import Callable, Iterator, Sequence
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
    CANAL_NADA_NO_CONTROLE,
    CANAL_SONS_DO_JOGO,
    CANAL_TODO_O_PC,
    DICA_AUDIO_SEM_ENDERECO,
    L2_R2_THRESHOLD,
    ROTA_DO_CANAL,
    TEXTO_SELO_SAIDA_MUDA,
    _markup_xy,
    acao_mic,
    acao_speaker_mudo,
    accel_do_inputs,
    dedos_do_inputs,
    dica_do_titulo,
    frase_do_alvo_do_mic,
    gyro_do_inputs,
    rotulo_lightbar,
    saida_muda_do_entry,
    speaker_do_entry,
    texto_motion,
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
from hefesto_dualsense4unix.integrations import (
    ganho_do_microfone as _ganho_no_aparelho,
)
from hefesto_dualsense4unix.interface.monta import luzinhas

from . import (
    LUGAR_VAZIO,
    NOME_SEM_LEITURA,
    TRAVESSAO,
    Contexto,
    identidade_de,
    poda,
    registrar,
)

# provou —, e a interface nova alcançava **duas** (`rotulo_lightbar`, pela aba
#   `rotulo_lightbar`    cor de fonte DESCONHECIDA não é `#000000`.
#   `touchpad_do_inputs` os TRÊS estados do touchpad numa função só, e a
#   `acao_mic`           sem leitura de `audio` o botão do 🎙 CHUTAVA:
# O IMPORT É POR SÍMBOLO, e isso importa para o `portao_a_casa_sabe_e_o_produto_

# medição, não por gosto: o `portao_a_casa_sabe_e_o_produto_nao_faz` PODA os

# ---------------------------------------------------------------------------
#     dados = touchpad_do_inputs(inputs)
# aqui era que `touchpad_do_inputs` *"exige `bloco['x']` e `bloco['y']`: um
# controles dela na mesa (um `usb`, um `bt`), 60 leituras de `daemon.state_full`
#     touchpad presente ......... 36 amostras
#     `inputs` SEM a chave ...... 24 (o aquecimento: o reader do touchpad nasce
#     `inputs` não-dict ......... 60 (o controle que não é `is_primary`)
# `touchpad_do_inputs` é o dono de `fx`/`fy` — a POSIÇÃO do dedo, normalizada
# "2 TOQUES" NÃO SE INVENTA AQUI: `texto_toques` conta DEDOS e o `state_full`


def dedos_do_controle(
    inputs: Any,
) -> tuple[str, tuple[tuple[str, tuple[float, float] | None], ...]]:
    """`(palavra, ((ponto, onde), …))` do touchpad — MULTITOQUE-01.

    A versão de DOIS dedos de `toque_do_controle`, e ela substitui aquela na
    pintura desta aba. O DualSense tem dois pontos de toque no hardware
    (`ABS_MT_SLOT 0..1`, medido no controle dela em 18/09/2026), e até esta
    data a tela mostrava um: não por erro de desenho, mas porque o payload
    trazia um — a queixa dela foi *"SÓ MOSTRA UM TOQUE NO DESENHO DO SVG
    APESAR DO TOUCH SER MULTITOQUE"*.  <!-- noqa-acento: citação literal dela -->

    A tupla tem SEMPRE `MAX_DEDOS` entradas, uma por bolinha do desenho, na
    ordem dos slots do kernel. Um slot sem dedo devolve `("", None)`: a
    bolinha apaga e a posição não é escrita — nunca uma coordenada inventada
    para um dedo que não está lá.

    A palavra é a do produto (`texto_toques`), agora com a contagem de
    verdade: *Sem toque* · *1 toque* · *2 toques*.
    """
    dedos = dedos_do_inputs(inputs)
    if dedos is None:
        import mesa_viva

        return (str(mesa_viva.SEM_LEITOR),
                tuple(("", None) for _ in range(MAX_DEDOS)))
    saida: list[tuple[str, tuple[float, float] | None]] = []
    for indice in range(MAX_DEDOS):
        if indice < len(dedos):
            fx, fy = dedos[indice]
            saida.append(("sim", (round(fx * 100, 1), round(fy * 100, 1))))
        else:
            saida.append(("", None))
    return (texto_toques(len(dedos)), tuple(saida))


# PARADO (`daemon.state_full`, 03/09/2026):
# `inputs` (o daemon só publica leitura para o `is_primary`), e mostrava os
#   `ALL_BUTTONS` + `L2_R2_THRESHOLD`  os 16 nomes e o limiar de L2/R2, do
#   `_markup_xy`                       os dois eixos do analógico
# O `_markup_xy` COMEÇA COM UNDERSCORE E MESMO ASSIM SE IMPORTA: ele é função de


def meias_da_barra(estilo: Any) -> tuple[str, str, str]:
    """`(negativa%, positiva%, cor)` de uma barrinha de eixo."""
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


# A QUEIXA, com dois DualSense na mesa (um no cabo, um no rádio): *"não funciona
# `touchpad_do_inputs` devolve `(tocando, fx, fy)` em 0..1, e
# para ACENDER (`data-hef-alvo="classe"`) e os dois `<span class="p">` dos

#: DualSense dela (`ABS_X/ABS_Y/ABS_RX/ABS_RY min=0 max=255`), o mesmo 255 que
#: os gatilhos já escrevem em `leitura_viva`.
CURSO_DO_ANALOGICO = 255
REPOUSO_DO_ANALOGICO = 128


def pos_do_analogico(v: Any) -> float:
    """0-255 -> posição em % dentro do círculo. 128 é o centro."""
    return round(int(v) / CURSO_DO_ANALOGICO * 100, 1)


#: DualSense declara `ABS_MT_SLOT min=0 max=1` — medido nos quatro controles
MAX_DEDOS: int = 2

CAMPOS_DA_POSICAO: dict[str, str] = {
    "touch": "pos-touch",
    "touch2": "pos-touch-2",
    "ana-e": "pos-ana-e",
    "ana-d": "pos-ana-d",
}

REPOUSO_DA_POSICAO = pos_do_analogico(REPOUSO_DO_ANALOGICO)

REGRA_DAS_POSICOES = (
    f".ctl .touch .ponto,.ctl .stick .p"
    f"{{left:var(--hef-x,{REPOUSO_DA_POSICAO}%);"
    f"top:var(--hef-y,{REPOUSO_DA_POSICAO}%)}}"
)


def texto_da_posicao(xy: tuple[float, float] | None) -> str:
    """`(x, y)` → `"x,y"`, a língua do alvo `posicao`; `""` quando não se leu."""
    if xy is None:
        return ""
    return f"{xy[0]},{xy[1]}"


def posicoes_do_controle(
    inputs: Any,
    tem_leitor: bool,
    onde_o_dedo: tuple[float, float] | None,
    onde_o_dedo2: tuple[float, float] | None = None,
) -> dict[str, tuple[float, float] | None]:
    """Os QUATRO pontinhos de um controle, em % — `None` no que não se leu."""
    import mesa_viva

    e: dict[str, Any] = inputs if isinstance(inputs, dict) else {}
    return {
        "touch": onde_o_dedo,
        "touch2": onde_o_dedo2,
        **{
            alvo: (
                (pos_do_analogico(mesa_viva._eixo_do_analogico(e, cx)),
                 pos_do_analogico(mesa_viva._eixo_do_analogico(e, cy)))
                if tem_leitor else None
            )
            for alvo, (cx, cy) in (("ana-e", ("lx", "ly")), ("ana-d", ("rx", "ry")))
        },
    }


def _eixos_do_sensor(
    familia: str, lido: tuple[float, float, float] | None, escala: float, grafia: Any
) -> dict[str, Any]:
    """Os quatro campos de cada eixo de um sensor — número, duas metades e cor."""
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
    o `_reset_inputs_render` da GTK (`controller_card.py:3440`), linha por
    linha: gatilhos em `0 / 255` com a barra vazia, analógicos no centro, os
    dezesseis glifos apagados e os sensores no travessão. Vale para METADE da
    mesa dela agora: o daemon só publica `inputs` para o `is_primary`.
    """
    lido = entrada.get("inputs")
    e: dict[str, Any] = lido if isinstance(lido, dict) else {}
    apertados = {str(b) for b in (e.get("buttons") or ())}
    l2 = int(e.get("l2_raw") or 0)
    r2 = int(e.get("r2_raw") or 0)
    aceso = {n: n in apertados for n in ALL_BUTTONS}
    aceso["share"] = ("share" in apertados) or ("create" in apertados)
    aceso["l2"] = l2 > L2_R2_THRESHOLD
    aceso["r2"] = r2 > L2_R2_THRESHOLD

    campos: dict[str, Any] = {f"glifo-{n}": ("sim" if aceso[n] else "") for n in aceso}
    for nome, cru in (("l2", l2), ("r2", r2)):
        campos[f"{nome}-num"] = f"{cru} / 255"
        campos[f"{nome}-barra"] = cru * 100 // 255
    for lado, (cx, cy) in (("l", ("lx", "ly")), ("r", ("rx", "ry"))):
        x, y = e.get(cx), e.get(cy)
        campos[f"xy-{lado}"] = texto_do_xy(128 if x is None else x, 128 if y is None else y)
    campos.update(_eixos_do_sensor("giro", gyro_do_inputs(e), ESCALA_GYRO_GRAUS_S, texto_eixo))
    campos.update(
        _eixos_do_sensor("accel", accel_do_inputs(e), ESCALA_ACCEL_G, texto_eixo_g)
    )
    return campos


#   `portao_a_casa_sabe_e_o_produto_nao_faz` fecha VERDE (42 passed) — medido
# A CHAVE PASSA A SER O SLUG, e não o nome. `mesa_viva.mesa_do_estado` já põe
# serve de peneira: um `url(#hachura-sem-hex)` sai como `""`.

BORDA_SEM_COR = "var(--border-forte)"

#: E ELE NÃO PODE SER AUSÊNCIA: `.ctl{border:2px solid var(--plastico)}`, e uma
PISO_DA_FOLHA = ".ctl[data-controle],.fita .chip[for]{--plastico:var(--border-forte)}"


def _monta() -> Any:
    """O `monta`, importado TARDE. O `pacotes/__init__` põe `interface/` no path."""
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


ROTULO_DO_CLIQUE = {"l": "L3", "r": "R3"}
CLICADO = "[%s]"

# `rotulo_lightbar` devolve `(rótulo, base_do_accent)`, e O DISCRIMINADOR É O
#   (sem rótulo) — conhecida e acesa   a cor   #0000FF         #0000FF
# NA DA STEAM A BASE É O `rgb` CRU (`controller_card.rotulo_lightbar`), e com a
# E O ÚLTIMO É UM FATO, NÃO UMA AUSÊNCIA: `lightbar_on` falso com fonte NOSSA é

#: Das quatro frases que `rotulo_lightbar` devolve, só uma é constante exportada
#: que a LEI 0 proíbe, e uma cópia MUDA: no dia em que o motor trocasse a frase,
ROTULO_DA_LUZ_APAGADA = rotulo_lightbar(
    {"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs", "lightbar_on": False}, {}
)[0]

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
    return str(mesa_viva.SEM_LEITOR)


def _cor_da_barra(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """A cor do RETÂNGULO, do mesmo par que decide o `luz_hex`. `""` = apague."""
    hex_ = luz_hex(rotulo, base)
    return hex_ if hex_.startswith("#") else ""


# frase não — e é por isso que a frase mora no `title`, que não paga pixel.
# que `rotulo_lightbar` trocar uma frase, a tabela abaixo deixa de casar e a

ROTULO_DA_LUZ_SEGURADA = rotulo_lightbar({"lightbar_disputada": True}, {})[0]

ROTULO_DA_LUZ_DESCONHECIDA = rotulo_lightbar({}, {})[0]

PALAVRA_DA_LUZ: dict[str | None, str] = {
    ROTULO_DA_LUZ_SEGURADA: "Steam",
    ROTULO_DA_LUZ_DESCONHECIDA: NOME_SEM_LEITURA,
    ROTULO_DA_LUZ_APAGADA: "Apagada",
}

DICA_DA_LUZ = ("Este é o código da cor do jogador, não a cor do controle. "
               "Quem a escolhe é o Hefesto, pela mesma tabela que acende as "
               "cinco lâmpadas.")


def luz_palavra(rotulo: str | None, base: tuple[int, ...] | None) -> str:
    """O que o campo MOSTRA: o código de cor, ou a palavra curta do estado.

    A cor conhecida continua sendo o hexadecimal — ela é a informação, e
    trocá-la por palavra perderia o que a pessoa foi ali ver. O que muda são os
    "não sei" e a "apagada", que dividiam um travessão só.

    RÓTULO QUE O MOTOR PASSE A DEVOLVER E ESTA TABELA NÃO CONHEÇA cai no
    travessão de antes, e não numa palavra chutada: o `luz_hex` é o dono do
    desfecho, e esta função só traduz o que ele já decidiu ser "não sei".

    **A TABELA VEM ANTES DO `luz_hex`, e a ordem foi medida.** A "apagada" é o
    único dos estados com palavra em que o `luz_hex` devolve um CÓDIGO
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
    (:data:`DICA_DA_LUZ`); nos outros estados é a frase que o MOTOR
    devolve, palavra por palavra — é ela que diz por que o código não aparece.

    O `base` entra sem ser lido de propósito: a assinatura é a mesma do
    `luz_palavra` e do `_cor_da_barra`, e os três são chamados lado a lado com
    o par inteiro. Uma assinatura diferente aqui convidaria alguém a passar só
    o rótulo num dos três — que é exatamente o defeito que o `luz_hex` existe
    para fechar.
    """
    return DICA_DA_LUZ if rotulo is None and base is not None else str(rotulo or "")


# que o `state_full` não ecoa de propósito — ver `SEM_ECO`).


def _bloco_do_speaker(entry: Any) -> dict[str, Any] | None:
    """O bloco `speaker` cru do controle, nas DUAS posições em que ele chega.

    ELE É A SEGUNDA LEITURA DA MESMA REGRA, e isso está declarado em vez de
    escondido: o dono é `speaker_do_entry` (`controller_card.py:1162`), que
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


#: `core/ds_output_report.py:106-107`. Digitar `2` e `3` aqui seria a régua que
NOME_DO_BOTAO_DA_ROTA: dict[int, str] = {
    ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]: "jogo",
    ROTA_DO_CANAL[CANAL_TODO_O_PC]: "pc",
    ROTA_DO_CANAL[CANAL_NADA_NO_CONTROLE]: "nada",
}


def rota_na_tela(entry: Any) -> str:
    """O que a CAMADA 2 (o byte do firmware) diz: `"jogo"`, `"pc"` ou `""`."""
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


CAMADA_1_S = 2.0

_CAMADA_1: dict[str, Any] = {}
_CAMADA_1_QUANDO = [0.0]
_CAMADA_1_EM_VOO = [False]

_CAMADA_1_SELO = [0]


_MEMORIA_DA_VOLTA = threading.local()


@contextlib.contextmanager
def _uma_leitura_por_volta() -> Iterator[None]:
    """Neste fio, e só enquanto durar, cada `argv` roda uma vez por dono."""
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone

    antes = getattr(_MEMORIA_DA_VOLTA, "lidos", None)
    _MEMORIA_DA_VOLTA.lidos = {}
    try:
        with eleicao_de_microfone.uma_leitura_por_volta():
            yield
    finally:
        _MEMORIA_DA_VOLTA.lidos = antes


def _ler_pelo_dono(argv: list[str]) -> str:
    """`audio_saida.rodar_leitura`, com a memória da volta quando ligada.

    O DONO É LIDO NA HORA DA CHAMADA, e nunca trocado: as réguas que dublam
    `audio_saida.rodar_leitura` continuam alcançando o produto, e a eleição
    tem a memória dela, que embrulha o `_rodar` dela.
    """
    lidos: dict[tuple[str, ...], str] | None = getattr(_MEMORIA_DA_VOLTA, "lidos", None)
    if lidos is None:
        return audio_saida.rodar_leitura(argv)
    chave = tuple(argv)
    if chave not in lidos:
        lidos[chave] = audio_saida.rodar_leitura(argv)
    return lidos[chave]


def _ler_a_camada_1(entradas: tuple[tuple[str, int | None], ...],
                    na_mesa: tuple[str, ...]) -> dict[str, Any]:
    """A camada 1 de cada controle da mesa. BLOQUEANTE — roda `pactl`."""
    lido: dict[str, Any] = {}
    for uniq, byte in entradas:
        if not uniq:
            continue
        try:
            lido[uniq] = audio_saida.ler_as_duas_camadas(
                uniq, byte, list(na_mesa), runner=_ler_pelo_dono)
        except Exception:
            continue
    return lido


#: DualSense não publica placa ALSA nenhuma (medido em 15/08/2026 — a placa
_SONO: dict[str, str] = {}

_REGRA_DO_SONO: list[bool | None] = [None]

_MIC_NATIVO: dict[str, bool | None] = {}


def _ler_o_nativo(na_mesa: tuple[str, ...]) -> dict[str, bool | None]:
    """`{uniq: há fonte nativa?}` da mesa inteira. BLOQUEANTE — roda `pactl`.

    Uma pergunta por controle porque a resposta É por controle: com dois
    DualSense no cabo há duas fontes nativas, e quem sabe casar cada uma com o
    seu aparelho é o dono (`escolher_fonte`, pelo nome e pelo casamento USB).
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone

    fora: dict[str, bool | None] = {}
    for uniq in na_mesa:
        if not uniq:
            continue
        try:
            fora[uniq] = eleicao_de_microfone.microfone_nativo_no_ar(
                uniq, list(na_mesa))
        except Exception:
            continue
    return fora


_GANHO: dict[str, tuple[int, float] | None] = {}


#: **O GANHO MUDOU DE CASA EM 21/09/2026, e a mudança é de CAMADA.** O leitor,
GANHO_PADRAO_PCT = _ganho_no_aparelho.GANHO_PADRAO_PCT
_CAPACIDADE_DE_GANHO = _ganho_no_aparelho._CAPACIDADE_DE_GANHO
_nome_do_scontrol = _ganho_no_aparelho._nome_do_scontrol
_ganho_do_scontents = _ganho_no_aparelho.ganho_do_scontents
_elemento_e_ganho_do_scontents = _ganho_no_aparelho.elemento_e_ganho_do_scontents
_placa_de_cada_fonte = _ganho_no_aparelho.placa_de_cada_fonte
placa_alsa_do_controle = _ganho_no_aparelho.placa_do_controle


def _ler_o_ganho(na_mesa: tuple[str, ...]) -> dict[str, tuple[int, float] | None]:
    """`{uniq: (por cento, dB) | None}` da mesa. BLOQUEANTE — roda comando.

    SÃO TRÊS RESPOSTAS, e a CHAVE é a terceira: a tupla quando há elemento de
    ganho; `None` quando *perguntei e não há onde esse ganho exista* — o do
    rádio, que é nó da nossa ponte e não tem placa ALSA (medido em 15/08: a
    placa segue o transporte), e a máquina sem `amixer`; e a chave **AUSENTE**
    quando a resposta é *não sei* — o `pactl` mudo, o censo de USB que não
    montou, a primeira volta que ainda não deu.

    **ESCREVER `None` É O PONTO**, e não um detalhe de implementação: sem ele a
    aba não distingue *"ainda não perguntei"* de *"perguntei e não há"*, e o
    cinza do trilho acenderia nos dois segundos da primeira volta. **E NÃO
    ESCREVER NADA É O OUTRO PONTO:** com o servidor de som mudo, escrever
    `None` acenderia o cinza com a razão *«ligue o cabo»* sobre uma ignorância
    nossa — dizer "não há" quando a verdade é "não consegui perguntar".

    A PERGUNTA NÃO É AO `canal_fonte` DO DAEMON, e a primeira redação desta
    função era — **medido na mesa dela em 20/09/2026, com um DualSense no FIO e
    três no ar: os quatro responderam `hefesto_mic_<hex6>`**, o nó da nossa
    ponte, que não tem placa ALSA nenhuma. O ganho ficava cinza no controle que
    estava no cabo, com a razão mandando ligar o cabo. O `canal_fonte` é o nó
    que o produto ELEGEU (regra 0 de `escolher_fonte`), e a pergunta daqui é
    outra: *qual nó deste controle o KERNEL publica*. Quem responde é o dono —
    :func:`eleicao_de_microfone.fonte_nativa_do_controle`, a irmã de corpo
    único da que o «Nativo» já usa uma leitura acima.

    O QUE ELA CUSTA, medido na mesa de quatro dela em 20/09/2026: **~70 ms**,
    dentro de uma thread que acorda a cada :data:`CAMADA_1_S` (2 s) — a mesma
    ordem de grandeza do `_ler_o_nativo` logo acima (~55 ms), que faz a mesma
    pergunta por controle. A leitura LONGA do `pactl` é uma só para a mesa
    inteira (é dela que sai a placa de cada nó), e a do `amixer` é POR PLACA e
    nunca por controle: com quatro DualSense no cabo são quatro placas
    distintas, e a mesma placa nunca é lida duas vezes na mesma volta.
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone

    mesa = [u for u in na_mesa if u]
    if not mesa:
        return {}
    fora: dict[str, tuple[int, float] | None] = {}
    alvos: dict[str, str] = {}
    for uniq in mesa:
        try:
            no = eleicao_de_microfone.fonte_nativa_do_controle(uniq, mesa)
        except Exception:
            no = None
        if no is None:
            continue
        fora[uniq] = None
        if no:
            alvos[uniq] = no
    if not alvos:
        return fora
    try:
        lista = _ler_pelo_dono(["pactl", "list", "sources"])
    except Exception:
        return {}
    placa_da_fonte = _placa_de_cada_fonte(lista)
    por_placa: dict[str, tuple[int, float] | None] = {}
    for uniq, no in alvos.items():
        placa = placa_da_fonte.get(no, "")
        if not placa:
            continue
        if placa not in por_placa:
            try:
                por_placa[placa] = _ganho_do_scontents(
                    _ler_pelo_dono(["amixer", "-c", placa, "scontents"]))
            except Exception:
                por_placa[placa] = None
        fora[uniq] = por_placa[placa]
    return fora


def definir_ganho_do_microfone(
    uniq: str, por_cento: int, na_mesa: Sequence[str]
) -> tuple[int, float] | None:
    """Escreve o ganho no aparelho, ATUALIZA O CACHE DA TELA e devolve o que ficou.

    O corpo mora em `integrations.ganho_do_microfone.definir` desde 21/09/2026.
    O que fica aqui é a única parte que é da INTERFACE: o cache.

    **O CACHE APRENDE NA HORA.** Sem isto a tela volta ao valor velho no tique
    seguinte — a thread da camada 1 só acorda a cada 2 s, e nesses dois segundos
    o deslizante «pula para trás» sozinho. É o mesmo desacordo que
    `_lembrar_do_som` cura para o volume, e é por isso que o cache não desceu
    junto com o escritor: o `profiles/manager.py` escreve o mesmo ganho e não
    tem tela nenhuma para manter em dia.
    """
    ficou = _ganho_no_aparelho.definir(uniq, por_cento, na_mesa)
    if ficou is not None:
        _GANHO[uniq] = ficou
    return ficou


def ganho_do_microfone(uniq: str) -> tuple[int, float] | None:
    """`(por cento, dB)` do ganho de entrada deste controle, ou `None`."""
    return _GANHO.get(uniq) if uniq else None


RAZAO_DO_GANHO_FORA = (
    "O ganho de entrada é do aparelho, e só o cabo alcança o controle dele: "
    "pelo rádio o microfone chega como som já digitalizado, sem placa de som "
    "onde esse controle exista. Ligue o cabo e ele acende."
)


def ganho_fora_de_alcance(uniq: str) -> str:
    """A razão quando o ganho não alcança este controle; `""` quando alcança."""
    if not uniq or uniq not in _GANHO:
        return ""
    return "" if _GANHO[uniq] is not None else RAZAO_DO_GANHO_FORA


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
        saida = _ler_pelo_dono(["pactl", "list", "sinks", "short"])
    except Exception:
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


def _camada_1(entradas: tuple[tuple[str, int | None], ...],
              na_mesa: tuple[str, ...]) -> dict[str, Any]:
    """O cache da camada 1, renovado em THREAD a cada :data:`CAMADA_1_S`."""
    import threading
    import time

    if not na_mesa or _CAMADA_1_EM_VOO[0]:
        return _CAMADA_1
    agora = time.monotonic()
    if _CAMADA_1_QUANDO[0] and agora - _CAMADA_1_QUANDO[0] < CAMADA_1_S:
        return _CAMADA_1
    _CAMADA_1_EM_VOO[0] = True
    _CAMADA_1_QUANDO[0] = agora
    selo = _CAMADA_1_SELO[0]

    def renovar() -> None:
        try:
            with _uma_leitura_por_volta():
                novo, sono, regra, nativo, ganho = _ler_a_volta()
            if _CAMADA_1_SELO[0] != selo:
                return
            _CAMADA_1.clear()
            _CAMADA_1.update(novo)
            _SONO.clear()
            _SONO.update(sono)
            _MIC_NATIVO.clear()
            _MIC_NATIVO.update(nativo)
            _GANHO.clear()
            _GANHO.update(ganho)
            _REGRA_DO_SONO[0] = regra
        finally:
            _CAMADA_1_EM_VOO[0] = False

    def _ler_a_volta() -> tuple[dict[str, Any], dict[str, str], bool | None,
                                dict[str, bool | None],
                                dict[str, tuple[int, float] | None]]:
        novo = _ler_a_camada_1(entradas, na_mesa)
        sono = _ler_o_sono(novo)
        try:
            regra = audio_saida.regra_nunca_dorme_instalada()
        except Exception:
            regra = None
        nativo = _ler_o_nativo(na_mesa)
        ganho = _ler_o_ganho(na_mesa)
        return novo, sono, regra, nativo, ganho

    threading.Thread(target=renovar, name="hefesto-rota-camada-1",
                     daemon=True).start()
    return _CAMADA_1


_POR_CONTROLE: tuple[dict[str, Any], ...] = (
    _CAMADA_1, _SONO, _MIC_NATIVO, _GANHO)


@poda
def _esquecer_o_som_de_quem_saiu(na_mesa: frozenset[str]) -> None:
    """Tira das três leituras por controle tudo o que não está mais na mesa."""
    for cache in _POR_CONTROLE:
        for uniq in [u for u in cache if u not in na_mesa]:
            cache.pop(uniq, None)
    _CAMADA_1_QUANDO[0] = 0.0
    _CAMADA_1_SELO[0] += 1


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


MIC_SEM_ALVO = "sem-alvo"
MIC_SEM_FONTE = "sem-fonte"


def microfone_apagado(entry: Any) -> str:
    """O cinza da moldura do MICROFONE deste controle, ou ``""`` quando ela acende."""
    if uniq_do_entry(entry) is None:
        return MIC_SEM_ALVO
    if no_do_microfone(entry):
        return ""
    blocos = (entry.get("audio") if isinstance(entry, dict) else None,
              _bloco_do_speaker(entry))
    disse = any(isinstance(b, dict) and "canal_fonte" in b for b in blocos)
    return MIC_SEM_FONTE if disse else ""


def sink_do_cache(uniq: str) -> str:
    """O sink de SAÍDA deste controle, do cache da camada 1. ``""`` = não sei."""
    lida = _CAMADA_1.get(uniq)
    return str(getattr(lida, "sink_do_controle", "") or "") if lida else ""


def volume_do_microfone(audio: Any) -> int | None:
    """O volume da captura deste controle, 0 a 100, ou ``None`` — *não sei*.

    **UM DONO PARA O NÚMERO E PARA A BARRA**, que é o mesmo arranjo do
    `alto-num`/`alto-barra`: dois arredondamentos para o mesmo fato é o defeito
    que faz dois campos do mesmo bloco discordarem na tela.

    O VALOR VEM DO ESTADO, NUNCA DO `pactl`. `audio.volume_captura` é escrito
    por `canal_do_microfone_loop`, numa thread, a cada dois segundos; quem
    perguntasse aqui rodaria um subprocesso por controle a cada tique da
    pintura. A regra está escrita no daemon, no bloco do `audio`, e vale igual
    deste lado.

    ``None`` É DE PRIMEIRA CLASSE e sai em três casos honestos: o laço ainda
    não perguntou (a chave nem aparece), este controle não tem fonte de captura
    (o do rádio antes de a ponte subir), ou o `pactl` não respondeu. Chutar zero
    pintaria "microfone no mínimo" sobre um microfone que ninguém leu.

    OS DOIS ALVOS NUM ENDEREÇO SÓ (`largura` na barra pintada, `valor` no
    deslizante) são o arranjo que o `alto-barra` já usa logo abaixo: os dois
    mostram o MESMO volume, um como largura e o outro como posição do polegar.
    Dois `data-campo` para o mesmo número seriam duas verdades a sincronizar.

    O TETO É 100 PORQUE O TRILHO VAI DE ZERO A CEM: o `pactl` devolve por cento
    e admite passar de 100 (super-amplificação), e o `<input type="range" max="100">`
    desta tela não tem como representar nem produzir isso. Um número acima do
    que a barra alcança faria o texto e o polegar dizerem coisas diferentes
    sobre o mesmo volume — que é exatamente o que este dono único existe para
    impedir.
    """
    if not isinstance(audio, dict):
        return None
    lido = audio.get("volume_captura")
    if not isinstance(lido, int) or isinstance(lido, bool):
        return None
    return max(0, min(100, lido))


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
    """Diz ao medidor quais nós seguir neste tique. Nunca levanta."""
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


def campo_da_onda_calada(lado: str) -> str:
    """O endereço do cinza da onda de `lado` (`aba02.onda`, o invólucro)."""
    return f"{lado}-onda-calada"


def campos_da_onda(lado: str, alturas: tuple[int, ...] | None,
                   *, mudo: bool = False) -> dict[str, Any]:
    """Os quinze campos de um medidor: catorze alturas e o selo da leitura."""
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
    """Qual botão de rota a tela pode ACENDER, lendo as DUAS camadas."""
    lida = _CAMADA_1.get(uniq)
    if lida is None:
        return rota_na_tela(entry)
    return str(lida.botao_aceso)


ROTA_OUVIR_JUNTO = "junto"

ROTA_NADA_NO_CONTROLE = "nada"

#: *"Mas fazer isso certo com mockup antes."* É o `"pc"` de sempre — a rota 3
ROTA_TUDO_NO_CONTROLE = "pc"

BOTOES_DA_FILEIRA_DO_SOM = ("jogo", ROTA_OUVIR_JUNTO, ROTA_NADA_NO_CONTROLE,
                            ROTA_TUDO_NO_CONTROLE)


def fonte_do_controle(entry: Any) -> str:
    """`mix`/`sfx` deste controle, do `state_full` — `""` = ninguém sabe dizer.

    Quem publica é o daemon (`ipc_handlers`, bloco `speaker`), que pergunta ao
    `AltoFalanteSubsystem`, que lê o perfil ativo com cache por `(nome, mtime)`.
    A aba **não abre perfil**: um segundo leitor da mesma escolha dela é a
    família de defeito que esta casa persegue por escrito.

    `""` não vira `sfx`: sem resposta, nenhum dos três botões acende — é o
    mesmo contrato do `""` de `aceso_da_rota`.
    """
    bloco = _bloco_do_speaker(entry) or {}
    fonte = bloco.get("fonte")
    return str(fonte) if fonte in ("mix", "sfx") else ""


def _a_pagina_tem_o_ouvir_junto() -> bool:
    """A página PUBLICADA já tem o terceiro botão? Lido uma vez, do arquivo."""
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # pragma: no cover - defensivo
        return False
    return 'data-hef-quando="junto"' in doc


def aceso_da_fileira(uniq: str, entry: Any) -> str:
    """Qual dos QUATRO botões da fileira do som acende — 10/09/2026, A3."""
    aceso = aceso_da_rota(uniq, entry)
    if aceso in (ROTA_TUDO_NO_CONTROLE, ROTA_NADA_NO_CONTROLE) or not A_FILEIRA_TEM_TRES:
        return aceso
    return ROTA_OUVIR_JUNTO if fonte_do_controle(entry) == "mix" else aceso


# AS QUATRO FACES, e cada uma tem chave própria no `state_full.audio` desde a
# com o canal trocado por fora (`pactl set-default-source`), o `state_full`

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
        nao_sei = True
    else:
        nao_sei = True

    return calado, nao_sei


def selo_composto(a: dict[str, Any]) -> str:
    """ATIVO · MUDO · — pelas QUATRO faces, e ATIVO só quando elas concordam."""
    import mesa_viva

    calado, nao_sei = _faces_do_microfone(a)
    if calado:
        return str(mesa_viva.selo_do_mic(True, True))
    if nao_sei:
        return str(mesa_viva.selo_do_mic(False, False))
    return str(mesa_viva.selo_do_mic(False, True))


# ---------------------------------------------------------------------------
# levantar, e é do motor: `acao_mic` e `acao_speaker_mudo`


DICA_ALTO_SEM_POSSE = ("O ♪ só funciona depois de o volume ser ajustado uma "
                       "vez. Arraste o volume ao lado.")

#: `portao_a_casa_sabe_e_o_produto_nao_faz` já reprovou exatamente isso em
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
    if uniq_do_entry(entry) is None:
        return {"mic-porque": DICA_AUDIO_SEM_ENDERECO,
                "alto-porque": DICA_AUDIO_SEM_ENDERECO}
    do_mic = acao_mic(entry)
    do_alto = acao_speaker_mudo(entry)
    return {
        "mic-porque": "" if do_mic.sensivel else str(do_mic.dica),
        "alto-porque": "" if do_alto.sensivel else DICA_ALTO_SEM_POSSE,
    }


# sob demanda da RADIO-AFOGADO-01 não o lê parado): era um alarme aceso em todo


def selo_do_som(saida_muda: bool | None) -> str:
    """O alarme do bloco: `Saída muda`, ou nada.

    SÓ `True` ACENDE. `False` (a saída está aberta) e `None` (não sabemos)
    mostram a mesma coisa — nada —, porque um selo "saída viva" seria ruído em
    cima do que a barra já diz.

    E O SELO SÓ EXISTE NO ESTADO RUIM: um selo dizendo que está tudo bem em toda
    sessão normal gastaria pixel para não informar nada.

    FATO ERRADO, SUBSTITUÍDO EM 23/09/2026: ele acendia também `Canal dormindo`
    quando o canal estava parado. Canal parado não é estado ruim — ver o bloco
    acima.
    """
    return TEXTO_SELO_SAIDA_MUDA if saida_muda is True else ""


# <!-- noqa-acento: citação literal dela --> Quem responde agora é


# DualSense, lado do rádio, e a função que a lia do mapa e a devolvia ao campo


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

    **A REGRA É A DA INVERSÃO DE 18/09/2026**, ordem dela: *"todos os controles
    tem que nascer com tudo mic, giroscopio e afins"*. Quem responde no daemon
    é `bt_mic.uniqs_recusados`, e a tabela dele é de três valores: ausência
    LIGA, `True` liga, e só `False` desliga. Então só o `False` é Nativo.

    AQUI ESTAVA A REGRA DE ANTES — `microfone is True` é Virtual, ausência é
    Nativo —, que era a da GTK e valia enquanto o default fosse o silêncio.
    Com ela, o segundo, o terceiro e o quarto controle da mesa dela nasciam com
    a ponte de pé e o cartão acendia «Nativo»: a tela dizendo o contrário do
    que o daemon faz, medido em 22/09/2026 com dois DualSense no rádio.

    SEM ENDEREÇO NÃO SE AFIRMA NADA: um controle sem `uniq` normalizado não tem
    linha no `maquina.json`, e escrever "Nativo" ali seria afirmar uma escolha
    que ninguém fez. `""` apaga os dois botões, como na rota.
    """
    if not endereco:
        return ""
    meu = _controles_declarados().get(endereco)
    return "nativo" if getattr(meu, "microfone", None) is False else "virtual"


#:
#: DualSense — nenhum perfil de áudio. Isso é do aparelho, não da nossa fila, e
RAZAO_DO_NATIVO_FORA = ("Pelo rádio o controle fala só a língua dos comandos: "
                        "o som do microfone passa pelo Hefesto.")


def nativo_fora_de_alcance(uniq: str) -> str:
    """A razão quando o «Nativo» não alcança este controle; `""` quando alcança.

    UM CAMPO SÓ alimenta os dois lados — o cinza do botão (alvo `classe` no
    container) e o texto do `?` (alvo `html` na dica) —, que é o contrato da
    peça das dez (`monta.botao_cinza`): com dois campos seria possível pintar
    cinza sem razão, ou razão sem cinza.

    **"NÃO SEI" NÃO APAGA BOTÃO.** `None` (servidor de som mudo, leitura ainda
    não feita) devolve `""`, e o botão fica como está. Apagar uma escolha dela
    por falta de resposta seria a tela decidindo no escuro — a mesma disciplina
    de `eleicao_de_microfone.canal_publicado`, que nunca transforma silêncio em
    "saiu do ar".

    E A PERGUNTA É AO APARELHO, nunca ao transporte: quem responde é
    `microfone_nativo_no_ar`, que procura uma fonte de captura deste controle
    que **não** seja nossa. No dia em que o BlueZ publicar um perfil de áudio
    para o DualSense, o botão volta ao alcance sozinho.
    """
    if not uniq:
        return ""
    return "" if _MIC_NATIVO.get(uniq) is not False else RAZAO_DO_NATIVO_FORA


PAGINA = "02-controles.html"

A_FILEIRA_TEM_TRES = _a_pagina_tem_o_ouvir_junto()


def _a_pagina_tem_o_alcance_do_nativo() -> bool:
    """A página PUBLICADA já sabe apagar o «Nativo»? Lido uma vez, do arquivo."""
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # pragma: no cover - defensivo
        return False
    return 'data-hef-classe="sem-nativo"' in doc


A_PAGINA_APAGA_O_NATIVO = _a_pagina_tem_o_alcance_do_nativo()


def _a_pagina_tem_o_ganho() -> bool:
    """A página PUBLICADA já tem o trilho do ganho? Lido uma vez, do arquivo."""
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # pragma: no cover - defensivo
        return False
    return 'data-campo="mic-ganho-barra"' in doc


A_PAGINA_TEM_O_GANHO = _a_pagina_tem_o_ganho()


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


#     "icone mas no radio ele pode tá carregando tambem."  # noqa-acento: citação literal dela
#
# coisa do cabo e o rádio fosse sempre descarregar. **Não é**: um DualSense
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
    """Dos `campos`, só os que a página publicada tem onde pôr."""
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
    na_mesa = tuple(str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq"))
    _camada_1(
        tuple((str(c.get("uniq") or ""), _byte_da_rota(c)) for c in ctx.conectados),
        na_mesa,
    )
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
        # `is_primary` traz `inputs`; o outro vem `None`
        tem_leitor = isinstance(c.get("inputs"), dict)
        e = c.get("inputs") or {}
        a = c.get("audio") or {}
        mic_volume = volume_do_microfone(a)
        mic_ganho = ganho_do_microfone(uniq)
        #      de onde o dado mora"* (`controller_card.py:1121`). Medido na mesa
        sp_lido = speaker_do_entry(c)
        # `# type: ignore[arg-type]` na chamada). Sem esta guarda, a primeira
        # `rotulo_lightbar` já trata.
        rotulo_da_luz, base_da_luz = rotulo_lightbar(c, getattr(ctx, "state", None) or {})
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})

        # E TEM UMA QUARTA, QUE É "NÃO SEI" (MIC-DA-MESA-ELEICAO-01). O byte de
        # morre, o novo nasce sem leitura e a chave `audio` SOME do `state_full`.
        # o selo sem montar um `state_full` inteiro.
        pct = c.get("battery_pct")
        # do dono na GTK (`app/widgets/controller_card.py:3275`, `"l3" in
        apertados = set(e.get("buttons") or ())
        # dentro de `touchpad_do_inputs`, e a razão de a recusa anterior ter
        toque_txt, dedos = dedos_do_controle(e)
        toque_ponto, onde_o_dedo = dedos[0]
        toque_ponto2, onde_o_dedo2 = dedos[1]
        posicoes = posicoes_do_controle(e, tem_leitor, onde_o_dedo, onde_o_dedo2)
        # `identidade_de`, e a tradução do transporte é a MESMA que a mesa usa.
        # Esta linha era `VIA_DO_TRANSPORTE.get(…)`, a SIGLA DE MÁQUINA, e o
        # transporte DUAS VEZES no mesmo cabeçalho. Hoje `identidade_de` passou a
        #   transport='bt'   identidade_de='rádio'   via_na_tela='BT'
        # O comentário do bloco do `peca` já nomeava o defeito — *"o cabeçalho
        # A PERGUNTA É AO PRÓPRIO `identidade_de`, e não a uma palavra escrita:
        via_na_tela = palavra_do_transporte(c.get("transport"))
        nome_na_tela = identidade_de(c, ctx.mesa)
        ultimo_degrau = identidade_de({"transport": c.get("transport")})
        cards[uniq] = {
            # `texto_da_bateria`, que PERGUNTA à GTK as duas frases.
            "bateria": texto_da_bateria(pct),
            # `data-hef-alvo="largura"` monta `width: <t>%`, e um "95%" ali
            "bateria-barra": int(pct) if isinstance(pct, int) and not isinstance(pct, bool)
                             else 0,
            # Não é perda de dado: os três continuam a UM `.get` do `state_full`
            #
            # um mapa: *"`backend == "uhid"` implica máscara DualSense e não
            # uhid para saída Xbox (`home_actions.mascara_viva:914`). E `uinput`
            # é AMBÍGUO de propósito — Xbox normal e DualSense degradado usam o
            "mascara": casa.get("mascara") or mesa_viva.NOME_DA_MASCARA.get(
                mascara_viva({"gamepad_emulation": {"backend": c.get("vpad_backend")}})
                or "", "—"),
            # base do accent. As cinco situações e o que cada uma mostra estão
            # quatro estados que dividiam um `—` só. Ver `luz_palavra`, e a
            "luz-hex": luz_palavra(rotulo_da_luz, base_da_luz),
            "mic-selo": selo_composto(a),
            "mic-retorno": (mesa_viva.BOTAO_MIC_RETORNO
                            if monitor_do_microfone.esta_ligado(uniq) else ""),
            # leigo)"*.  # noqa-acento: citação literal dela
            "mic-num": (
                mic_volume if mic_volume is not None else mesa_viva.SEM_LEITOR
            ),
            "mic-barra": mic_volume if mic_volume is not None else 0,
            **({
                "mic-ganho-num": (
                    f"{mic_ganho[1]:+.0f}" if mic_ganho is not None
                    else mesa_viva.SEM_LEITOR
                ),
                "mic-ganho-barra": mic_ganho[0] if mic_ganho is not None else 0,
                "mic-ganho-fora": ganho_fora_de_alcance(uniq),
            } if A_PAGINA_TEM_O_GANHO else {}),
            "touch-estado": toque_txt,
            **{
                campo: (
                    (CLICADO % rot if campo in apertados else rot)
                    if tem_leitor else mesa_viva.SEM_LEITOR
                )
                for campo, rot in (("l3", ROTULO_DO_CLIQUE["l"]),
                                   ("r3", ROTULO_DO_CLIQUE["r"]))
            },
            **_so_se_a_pagina_tiver({
                "mic-ressalva": (
                    mesa_viva.frase_de_quem_te_ouve(a.get("ouvintes_do_mic"))
                    or NADA_A_DIZER
                ),
                # 06/09/2026. O dado chegou à tela na BATERIA-PARADA-01 (o
                # `battery_state` viaja no mesmo dicionário do `battery_pct`,
                # tá carregando tambem"*.  # noqa-acento: citação literal dela
                "bateria-carga": carga_na_tela(c.get("battery_state")),
                "touch-ponto": toque_ponto,
                "touch-ponto-2": toque_ponto2,
                **_so_se_a_pagina_tiver({
                    CAMPOS_DA_POSICAO[alvo]: texto_da_posicao(xy)
                    for alvo, xy in posicoes.items()
                }),
                # class="mudo" data-campo="alto-estado" hidden>` que o piloto
                "alto-estado": (
                    texto_volume(*sp_lido) if sp_lido is not None
                    else mesa_viva.SEM_LEITOR
                ),
                "alto-mudo": mesa_viva.selo_do_mic(
                    bool(sp_lido and sp_lido[1]),
                    sp_lido is not None and sp_lido[1] is not None,
                ),
                "alto-num": (
                    percentual_do_volume(sp_lido[0]) if sp_lido is not None
                    else mesa_viva.SEM_LEITOR
                ),
                "alto-barra": (
                    percentual_do_volume(sp_lido[0]) if sp_lido is not None else 0
                ),
                **campos_da_onda(LADO_MIC, alturas_do_no(no_do_microfone(c))),
                **_so_se_a_pagina_tiver({
                    campo_da_onda_calada(LADO_MIC): (
                        "sim" if _faces_do_microfone(a)[0] else "nao"  # noqa-acento: valor de atributo
                    ),
                }),
                **campos_da_onda(
                    LADO_ALTO,
                    alturas_do_no(no_do_alto_falante(uniq)),
                    mudo=bool(sp_lido is not None and sp_lido[1] is True),
                ),
                **{
                    campo: _selo_do_sensor(_sensor_ligado(c, qual_do_campo))
                    for campo, qual_do_campo in (("giro-ligado", "giroscopio"),
                                                 ("accel-ligado", "acelerometro"))
                },
                # `mira` que o `daemon.state_full` publica por controle
                "mira-ligada": _selo_do_sensor(_mira_ligada(c)),
                "giro-dica": dica_do_giro(c, _nativo(ctx), _na_navegacao(ctx)),
                "mira-fora": mira_fora(_nativo(ctx)),
                # OS CHIPS DO TOQUE E DA INCLINAÇÃO — 29/09/2026, NO-MODO-XBOX-
                **_so_se_a_pagina_tiver({
                    "inclinacao-destino": _chip_da_mira(c, "inclinacao"),
                    "toque-modo": _chip_da_mira(c, "toque"),
                }),
                # dizia `#0000FF` (a cor viva do P1) e o retângulo logo abaixo
                # return 1 }`, e o CSSOM NORMALIZA na atribuição (`#0000FF`
                "luz-cor": _cor_da_barra(rotulo_da_luz, base_da_luz),
                # (`mesa_viva.mesa_do_estado` → `daemon.subsystems.identity`), e
                # não uma leitura do aparelho. O `state_full` publica o
                # `player_slot` e não os `player_leds`; um perfil que escreva as
                "lampadas": luzinhas(int(casa.get("jogador") or 0) or 1),
                # O NOME É DE `identidade_de`, que é o dono da ordem das quatro
                "peca": "" if nome_na_tela == ultimo_degrau else nome_na_tela,
                "via": via_na_tela,
                # dos quatro degraus da Vibração, e é ela que faz "ligar um
                # [09].** Era `rota_na_tela(c)`, o byte e mais nada, e foi
                "alto-rota": aceso_da_fileira(uniq, c),
                "mic-modo-aceso": modo_do_mic(norm_mac(uniq) or ""),
                **({"mic-nativo-fora": nativo_fora_de_alcance(uniq)}
                   if A_PAGINA_APAGA_O_NATIVO else {}),
                # O `getattr` É O MESMO DO `rotulo_lightbar` VINTE LINHAS ACIMA,
                "giro-no-jogo": texto_motion(
                    c, getattr(ctx, "state", None) or {}) or "",
                # endereço até 03/09/2026. Ver `leitura_viva`, que traz a mesa
                **leitura_viva(c),
                # devolve. Ver `luz_porque`: com a cor conhecida ele volta a
                "luz-porque": luz_porque(rotulo_da_luz, base_da_luz),
                # o clique chega assim mesmo: `acao_mic` e `acao_speaker_mudo`
                **porques_do_som(c),
                # ELE NÃO REUSA `alto-porque`, e a diferença é medida: aquele
                "alto-apagado": (
                    "" if uniq_do_entry(c) is not None else MIC_SEM_ALVO
                ),
                "mic-apagado": microfone_apagado(c),
                "card-vpad": dica_do_titulo(c, getattr(ctx, "state", None) or {}) or "",
                "alto-selo": selo_do_som(saida_muda_do_entry(c)) or NADA_A_DIZER,
                # seria melhor que dormindo?"*  <!-- noqa-acento: dela -->
                "alto-canal": (mesa_viva.selo_do_alto_falante(
                    bool(sp_lido and sp_lido[1]),
                    True,
                ) if sono_do_canal(uniq) else NADA_A_DIZER),
                "alto-canal-porque": "",
            }),
        }
    da_pagina = _so_se_a_pagina_tiver({
        "plastico-css": folha_do_plastico(ctx.mesa),
        "fita-peca": [
            "" if str(m.get("nome") or "") == NOME_SEM_LEITURA else str(m.get("nome") or "")
            for m in ctx.mesa
        ],
        "fita-via": [str(m.get("via") or "") for m in ctx.mesa],
    })
    return {"cards": cards, "mesa": da_pagina, "sem_dono": {},
            LUGAR_VAZIO: {"alto-canal": TRAVESSAO},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()) + len(da_pagina),
                          "sem_dono": 0}}


# ---------------------------------------------------------------------------
#                               `sensor.*`, `gyro.*` nem `motion.*`). O
#   Só no controle              **GANHOU DONO** — `audio_saida.mandar_o_som_do_pc`,
# `common[7]`) e tem dono nomeado em `core/ds_output_report.py:106`, que é
# `dica_do_microfone` são funções de MÓDULO, puras, sobre um objeto de dados.
from hefesto_dualsense4unix.app import audio_saida  # noqa: E402
from hefesto_dualsense4unix.app.actions.config import (  # noqa: E402
    secao_controles as _mic_do_produto,
)
from hefesto_dualsense4unix.core.ds_output_report import (  # noqa: E402
    SAIDA_L_FONE_R_ALTO_FALANTE,
)
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402
from hefesto_dualsense4unix.integrations import (  # noqa: E402
    monitor_do_microfone,
    som_do_controle_na_tv,
    teste_do_microfone,
)

from . import gesto  # noqa: E402
from . import perfil as _perfil  # noqa: E402
from . import ponte as _ponte  # noqa: E402


def _corpo(r: Any) -> dict[str, Any] | None:
    """A resposta do daemon como CORPO, tolerando ponte que devolva só `bool`."""
    if isinstance(r, dict):
        return r
    return {"status": "ok"} if r else None


def _selo_do_sensor(ligado: bool | None) -> str:
    """`LIGADO` · `DESLIGADO` · travessão — as três respostas do interruptor."""
    import mesa_viva

    if ligado is None:
        return str(mesa_viva.SEM_LEITOR)
    return SENSOR_LIGADO if ligado else SENSOR_DESLIGADO


def _sensor_ligado(dele: dict[str, Any], qual: str) -> bool | None:
    """`True`/`False` do interruptor daquele sensor; `None` = o daemon não disse."""
    bloco = dele.get("sensores")
    if not isinstance(bloco, dict):
        return None
    valor = bloco.get(f"{qual}_ligado")
    return valor if isinstance(valor, bool) else None


def _mira_ligada(dele: dict[str, Any]) -> bool | None:
    """`True`/`False` do chip «Mira Virtual» deste controle; `None` = ninguém leu."""
    bloco = dele.get("mira")
    if not isinstance(bloco, dict):
        return None
    valor = bloco.get("ligada")
    return valor if isinstance(valor, bool) else None


def _destino_da_mira(dele: dict[str, Any], chave: str) -> str | None:
    """O destino da `inclinacao` ou do `toque` deste controle; `None` = ninguém leu."""
    bloco = dele.get("mira")
    if not isinstance(bloco, dict):
        return None
    valor = bloco.get(chave)
    return valor if isinstance(valor, str) and valor else None


def _chip_da_mira(dele: dict[str, Any], chave: str) -> str:
    """O valor pintado no grupo de chips: o destino, ou o travessão sem leitura."""
    import mesa_viva

    destino = _destino_da_mira(dele, chave)
    return destino if destino is not None else str(mesa_viva.SEM_LEITOR)


DICA_DO_GIRO = "Ligado: o jogo recebe o giro deste controle."

DICA_DO_GIRO_COM_A_MIRA = ("Com a Mira Virtual acesa, o giro deste controle vai "
                           "ao jogo pelo analógico direito.")
#: grava o analógico direito; o esquerdo e o cursor só vêm do perfil escrito à
DICA_DO_GIRO_NO_ESQUERDO = ("Com a Mira Virtual acesa, o giro deste controle vai "
                            "ao jogo pelo analógico esquerdo.")
DICA_DO_GIRO_NO_CURSOR = "Com a Mira Virtual acesa, o giro deste controle move o cursor."


def _nativo(ctx: Contexto) -> bool:
    """O Modo Nativo está ligado? É GLOBAL no daemon (`state_full.native_mode`).

    O `getattr` é o mesmo do `rotulo_lightbar` do `pacote`: há régua que monta
    um `Contexto` parcial, sem `state`, e para ela a resposta é "não".
    """
    estado = getattr(ctx, "state", None) or {}
    return estado.get("native_mode") is True


def _na_navegacao(ctx: Contexto) -> bool:
    """O modo vivo é a Navegação? Pelo dono da leitura (`mode_of_state`).

    SEM ESTADO, NÃO: `mode_of_state({})` devolve a Navegação, e a dica
    afirmaria o cursor sobre um tique sem resposta (a porta da `a01_jogar`).
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import (
        MODE_DESKTOP,
        mode_of_state,
    )

    estado = getattr(ctx, "state", None) or {}
    return bool(estado) and mode_of_state(estado) == MODE_DESKTOP


def dica_do_giro(dele: dict[str, Any], nativo: bool, navegacao: bool = False) -> str:
    """A dica do chip Giroscópio DESTE controle — muda só com a Mira acesa."""
    if _mira_ligada(dele) is not True or nativo:
        return DICA_DO_GIRO
    destino = (dele.get("mira") or {}).get("destino")
    if navegacao or destino == "mouse":
        return DICA_DO_GIRO_NO_CURSOR
    if destino == "analogico_esquerdo":
        return DICA_DO_GIRO_NO_ESQUERDO
    return DICA_DO_GIRO_COM_A_MIRA


MIRA_NO_NATIVO = "NATIVO"


def mira_fora(nativo: bool) -> str:
    """`NATIVO` quando o chip da Mira fica cinza, `""` quando não fica."""
    return MIRA_NO_NATIVO if nativo else ""


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa."""
    return str(o.get("uniq") or "")


def _volume_conhecido(dele: dict[str, Any]) -> dict[str, Any]:
    """`{"volume": N}` quando o daemon sabe o número, `{}` quando não sabe.

    ELE NÃO SE INVENTA, e a razão é do aparelho: o DualSense **não devolve** o
    registrador de volume, então `daemon.state_full` só publica a chave
    `speaker` depois do primeiro `speaker.set` (`ipc_handlers.py:3099`). Mandar
    um número de palpite tomaria a posse com o valor errado.

    E MANDÁ-LO QUANDO SE SABE É O QUE A GUI ESTÁVEL FAZ, pela cura de
    04/08/2026 (`controller_card.py:2467`): *"reafirmá-lo aqui é dizer ao
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


_NAO_GRAVA_POR_PECA = ("button_toggles_system",)

#: cartão daquele controle (`Piloto._recusou_dizendo`, 30 s).
_PERFIL_E_ESTADO_NAO_E_AVISO = "Perfil ativo"

#: em que a primeira mudar.
SOM_SEM_ENDERECO = (
    "o ajuste chegou ao controle, mas o perfil não consegue guardá-lo só "
    "para este controle: "
)

SOM_SEM_VOLUME_PARA_GUARDAR = (
    "A escolha chegou ao controle, mas o perfil só a lembra junto com o "
    "volume. Arraste o volume deste alto-falante uma vez."
)


# O MOTOR É DO PRODUTO E NÃO SE REESCREVE: `app/audio_saida.tocar_confirmacao`


def _sink_para_o_som(uniq: str, na_mesa: tuple[str, ...]) -> str:
    """O sink deste controle: o cache da camada 1 primeiro, o dono depois."""
    do_cache = sink_do_cache(uniq)
    if do_cache:
        return do_cache
    return str(audio_saida.sink_do_controle(uniq, list(na_mesa)) or "")


def _fora_do_voo(fn: Callable[[], None]) -> None:
    """Roda `fn` numa linha própria, sem segurar o botão que está em voo.

    **O GESTO JÁ NÃO RODA NO TIQUE** — medido em 06/09/2026 no piloto: ele
    despacha cada gesto numa thread (`interface/hefesto_vivo.py:2206`), porque
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
            return

    _fora_do_voo(tocar)


def _lembrar_do_som(
    ctx: Contexto,
    uniq: str,
    *,
    mic: dict[str, Any] | None = None,
    speaker: dict[str, Any] | None = None,
) -> None:
    """Grava o som que ficou de pé NESTE controle onde a marca do cartão diz.

    ESCRITOR ÚNICO DO SOM POR PEÇA nesta aba, e ser um só é a regra da casa:
    a classe de defeito que ela persegue é *"três escritores do perfil sem
    dono"*. Os gestos de som desta aba chamam ESTA função, e nenhum
    monta `controllers[...]` à mão.

    **QUEM CHAMA É O CALLBACK DE SUCESSO, nunca o gesto em si** — a mesma
    disciplina de `registrar_alto_falante_no_rascunho`: o perfil descreve o que
    FICOU DE PÉ, não a intenção. Um pedido recusado pelo daemon que fosse ao
    disco seria a tela decidindo por ela: o número no arquivo passaria a
    contradizer o aparelho, e a ativação seguinte reimporia o que nunca pegou.

    `mic` e `speaker` são os campos que ESTE gesto fez ficar de pé, e só eles:
    `{"volume": 42}`, `{"gain": 30}`, `{"rota": 2}`. O MUDO DO MICROFONE não
    passa por aqui: ele é do controle (O-MUDO-E-DO-CONTROLE-01), e o ato o
    grava no daemon. Campo ausente é campo
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
    `load_profile(name)` a CADA ativação (`profiles/manager.py:208`) — não há
    cópia do `Profile` em memória atravessando ativações, então a próxima
    (hotplug, troca de jogo, boot) lê o que esta função escreveu.

    O que se evita com isso é caro para ela: um `profile.switch` reaplica o
    perfil INTEIRO — luz, gatilhos, vibração — a cada clique no mudo, no meio
    de uma partida, para reafirmar um byte que já estava escrito.

    O `launch_env.refresh` do mesmo dono também fica de fora, e pelo mesmo
    critério: o que ele rematerializa é a antecipação de MODO/emulação por
    `appid` (`ipc_handlers._handle_launch_env_refresh`), e nenhum dos campos
    daqui — `mic.volume`, `mic.gain`, `speaker.volume/.muted/.rota` — entra
    nessa conta. Um dia em que este arquivo passar a gravar `mode`,
    `match` ou emulação, ele volta.

    O CAMINHO DE DISCO É O DA ABA PERFIS até o penúltimo passo: `load_profile`
    → `DraftConfig.from_profile` → os escritores por peça → `to_profile(nome,
    priority=…)` → `loader.save_profile`. A `priority` vai junto porque
    `to_profile` a recebe de fora; sem ela o perfil dela perderia a ordem de
    casamento (`BUG-FOOTER-SAVE-DROPS-SECTIONS-01`, nomeado no próprio
    `to_profile`).
    """
    if not mic and not speaker:
        return
    nome = _perfil.nome_do_ativo(getattr(ctx, "state", None)).strip()
    if not nome:
        # publica um `active_profile` (medido no `state_full` vivo:
        return
    chave = norm_mac(str(uniq or "").strip()) or ""

    loader = _perfil._com_o_src()
    try:
        loader.load_profile(nome)
    except Exception as erro:
        raise RuntimeError(
            f"o ajuste chegou ao controle, mas não consegui ler o perfil "
            f"{nome!r} para guardá-lo: {erro}") from erro
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto("som", nome,
                      lambda prof: _o_som_lembrado(ctx, uniq, chave, prof, mic, speaker),
                      uniq=chave or uniq, origem="interface-nova")


def _o_som_lembrado(ctx: Contexto, uniq: str, chave: str, prof: Any,
                    mic: dict[str, Any] | None,
                    speaker: dict[str, Any] | None) -> Any:
    """O perfil com o som que ficou de pé neste controle, ou `None` (nada mudou).

    O corpo de :func:`_lembrar_do_som`, que roda sobre o perfil ou sobre o que
    vale (o perfil com o computador por baixo) — ver `gravar_pelo_gesto`.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

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
            return None
        adiante = novo.to_profile(prof.name, priority=prof.priority)
    except RuntimeError:
        raise
    except Exception as erro:
        raise RuntimeError(f"{SOM_SEM_ENDERECO}{erro}") from erro
    # SÓ O DISCO — ver a docstring de `_lembrar_do_som`. O aparelho já está no
    return adiante


@gesto("02-controles.html", "mic-retorno")
def mic_retorno(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O 🎙 — **um interruptor**: aceso, você se ouve; apagado, silêncio."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mic-retorno: o clique não disse em qual controle")

    if monitor_do_microfone.esta_ligado(uniq):
        monitor_do_microfone.desligar(uniq)
        return

    calado, _nao_sei = _faces_do_microfone(
        (ctx.por_uniq(uniq) or {}).get("audio") or {})
    if calado:
        raise RuntimeError(
            "o microfone deste controle está desligado — aperte o botão de "
            "microfone no próprio controle para ligá-lo, e tente de novo")

    fonte = teste_do_microfone.fonte_do_controle(uniq)
    if not fonte:
        raise RuntimeError(
            "não consegui achar o microfone deste controle para ligar o "
            "retorno")
    if not monitor_do_microfone.ligar(uniq, fonte):
        raise RuntimeError(
            "não consegui ligar o retorno do microfone deste controle")


@gesto("02-controles.html", "mudo", grava="gravar_pelo_gesto")
def mudo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O 🎙 e o ♪ — os dois botões de calar, e eles ALTERNAM o que a tela mostra.

    UM GESTO PARA OS DOIS porque a página os marca com o mesmo `data-mudo`, e o
    valor dele diz qual. Separá-los em dois nomes inventaria um vocabulário que
    o desenho não tem.

    **São métodos diferentes, e não é detalhe.** O `mic.set` é o MUDO NO
    FIRMWARE (camada 3, `ipc_handlers.py:4795`): é o único que apaga a luz
    vermelha do plástico, e a partir dele o botão físico do controle deixa de
    valer — é o que o `title` do desenho já promete. O `speaker.set` manda ZERO
    ao alto-falante guardando o volume preferido (`ipc_handlers._handle_speaker_set`).
    Trocar um pelo outro calaria a coisa errada.

    ALTERNAR EXIGE LER O ESTADO, e ele vem do daemon, nunca de memória nossa:
    `audio.mic_mudo` é LEITURA do byte que vem em todo report de input, e
    `speaker.muted` é o que nós mandamos (o aparelho não devolve). Guardar o
    valor enviado como se fosse leitura é o hábito que o `ipc_bridge.py:888-889`
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
        # qual é o oposto"* (`controller_card.acao_mic`). Sem a chave `audio`
        # A FRASE É A DO PRODUTO, e a condição também: `acao_mic(...)` é o dono
        acao = acao_mic(dele)
        if not acao.sensivel:
            raise RuntimeError(acao.dica)
        agora = bool((dele.get("audio") or {}).get("mic_mudo"))
        corpo = _corpo(p.mic_canal_set_detalhado(agora, uniq=uniq))
        if corpo is None:
            # o mapa, não o cartão dela.
            raise RuntimeError(
                "o Hefesto não confirmou o mudo do microfone: ou ele parou, "
                "ou este controle se desligou")
        frase = frase_do_ato_do_microfone(corpo)
        if frase:
            raise RuntimeError(frase)
        # sprint existir HOJE, com quatro DualSense na mesa.
        # A FRASE É DO PRODUTO, e nenhuma nasce aqui: `frase_do_alvo_do_mic`
        confissao = frase_do_alvo_do_mic(alvo_honrado(corpo))
        if confissao:
            raise RuntimeError(confissao)
        return

    if qual == "alto-falante":
        if not acao_speaker_mudo(dele).sensivel:
            raise RuntimeError(
                "o volume deste alto-falante ainda é desconhecido, e calar "
                "antes de saber o volume tranca-o em zero — nem o próprio "
                "botão o solta depois. O daemon só publica o volume depois de "
                "o Hefesto escrever um.")
        lido = speaker_do_entry(dele)
        pedido_mudo = not bool(lido and lido[1])
        if not p.speaker_set(muted=pedido_mudo, uniq=uniq,
                             **_volume_conhecido(dele)):
            raise RuntimeError(
                "o Hefesto não confirmou o mudo do alto-falante. Se o volume "
                "deste controle ainda é desconhecido, ele recusa de propósito: "
                "calar antes de saber o volume tranca o alto-falante em zero")
        _confirmar_com_som(ctx, uniq)
        # quem o preenche é o `_lembrar_do_som`, com a leitura viva — a mesma
        _lembrar_do_som(ctx, uniq, speaker={"muted": pedido_mudo})
        return

    raise ValueError(f"mudo: não sei calar {qual!r} — a página manda 'microfone' "
                     f"ou 'alto-falante'")


def _dizer_a_fonte_ao_daemon(p: Any, uniq: str, fonte: str) -> None:
    """Manda a camada 1 ao daemon AGORA, além de gravá-la no perfil.

    **A METADE QUE FALTAVA, e o preço dela foi medido com o ouvido dela** —
    20/09/2026, 04:30. Os quatro DualSense estavam com o botão do meio aceso e
    o som do PC saiu **só na TV**: *"so saiu na tv."* A escolha ia ao PERFIL, e
    o único leitor dela no daemon era `_fontes_do_perfil`, que lê o perfil
    ATIVO. Sem perfil ativo — ou antes de o "Salvar" acontecer — a resposta é
    `{}`, o nó fica no padrão, e o clique dela não move uma nota de som.

    O PERFIL CONTINUA SENDO ONDE A ESCOLHA DURA. Este caminho é o que a faz
    valer AGORA; os dois juntos são o que o botão prometia desde 10/09.

    **NÃO LEVANTA.** Um daemon sem o subsystem do som de pé responde
    `sem_controle`, e isso não é razão para derrubar o gesto: a gravação no
    perfil vale igual, e a recusa apareceria como um erro vermelho sobre um
    clique que funcionou pela metade. Quem denuncia a metade que faltou é o
    selo da própria coluna, que lê o nó vivo.
    """
    with contextlib.suppress(Exception):
        p.speaker_set(uniq=uniq, fonte=fonte)


@gesto("02-controles.html", "rota", grava="gravar_pelo_gesto")
def rota(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Onde o som do controle sai — os QUATRO botões da fileira, um gesto só.

    O TÍTULO DE 04/09 DIZIA *"«Sons do jogo» tem dono; «Só no controle» não"*,
    e os dois nomes caducaram: hoje os botões dizem «Efeitos do Jogo no
    Controle, Áudio do PC no PC» (`jogo`), «Efeitos do Jogo e Áudio do PC no
    Controle» (`junto`), «Tudo no PC e Nada no Controle» (`nada`) e «Tudo no
    Controle e Nada no PC» (`pc`, de volta em 24/09). Os quatro têm dono, e é
    este gesto. O resto desta docstring é o registro de 04/09, com os nomes
    daquele dia.

    "SONS DO JOGO" É UM BYTE, e ele é o caso que ela descreveu com o Zelda —
    *"o speaker do controle faz os barulhos da espada do Link enquanto na tela
    tem o som normal do jogo"*. É o `OUTPUT_PATH_SEL` = 2: canal esquerdo para o
    fone/TV, direito para o alto-falante do controle. O `speaker.set` leva a
    `rota` (`ipc_handlers.py:4589`) e a GUI estável manda exatamente isto
    (`controller_card.py:2474`).

    "TODO O SOM DO PC" SÃO DUAS CAMADAS, E A SEGUNDA NÃO É IPC. O
    `profiles/schema.py:531` já escreve o limite com todas as letras:

        LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o
        som do PC" da janela também mexe na CAMADA 1 (o *default sink* do
        PipeWire), que é um fato GLOBAL do sistema (…)

    E `controller_card.py:2449` diz quem vence: *"A camada 1 vence a camada 2:
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
    (`controller_card.py:2449`). Se o sink não existe (o RÁDIO, em que o
    DualSense não publica placa de som), este gesto recusa ANTES de escrever o
    byte, dizendo por quê — em vez de deixar o firmware roteado para um canal
    que o sistema não alimenta.

    ELE MANDA AS DUAS, e o "Sons do jogo" também: a janela antiga chama
    `pedir_rota_do_sistema(canal == CANAL_TODO_O_PC)` nos DOIS estados
    (`controller_card.py:2366`) — voltar para "Sons do jogo" DEVOLVE a saída
    padrão do sistema. Fazer só a ida deixaria o som do PC preso no controle sem
    botão nenhum que o soltasse.
    """
    uniq, qual = _uniq(o), str(o.get("rota") or "")
    if not uniq:
        raise ValueError("rota: o clique não disse em qual controle")
    if qual not in BOTOES_DA_FILEIRA_DO_SOM:
        raise ValueError(f"rota: não conheço a rota {qual!r} — a página manda "
                         f"'jogo', 'junto', 'nada' ou 'pc'")
    # (com dois DualSense no cabo, sem a lista o `escolher_sink` não tem como),
    na_mesa = [str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq")]

    if qual == ROTA_NADA_NO_CONTROLE:
        audio_saida.devolver_o_som_do_pc(de=uniq, uniqs_na_mesa=na_mesa)
        if fonte_do_controle(ctx.por_uniq(uniq)) == "mix":
            _dizer_a_fonte_ao_daemon(p, uniq, "sfx")
        som_do_controle_na_tv.ligar(uniq)
        byte_calado = ROTA_DO_CANAL[CANAL_NADA_NO_CONTROLE]
        if not p.speaker_set(rota=byte_calado, uniq=uniq,
                             **_volume_conhecido(ctx.por_uniq(uniq))):
            raise RuntimeError(
                "o Hefesto não confirmou a rota do alto-falante: ou ele "
                "parou, ou este controle se desligou")
        _lembrar_do_som(ctx, uniq, speaker={"fonte": "sfx",
                                            "rota": byte_calado})
        return

    if qual == ROTA_OUVIR_JUNTO:
        audio_saida.devolver_o_som_do_pc(de=uniq, uniqs_na_mesa=na_mesa)
        som_do_controle_na_tv.desligar(uniq)
        _dizer_a_fonte_ao_daemon(p, uniq, "mix")
        lembrar: dict[str, Any] = {"fonte": "mix"}
        if _byte_da_rota(ctx.por_uniq(uniq)) == ROTA_DO_CANAL[CANAL_TODO_O_PC]:
            de_volta = ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]
            if not p.speaker_set(rota=de_volta, uniq=uniq,
                                 **_volume_conhecido(ctx.por_uniq(uniq))):
                raise RuntimeError(
                    "o Hefesto não confirmou a volta da rota do alto-falante: "
                    "ou ele parou, ou este controle se desligou")
            lembrar["rota"] = de_volta
        _lembrar_do_som(ctx, uniq, speaker=lembrar)
        _confirmar_com_som(ctx, uniq)
        return

    if fonte_do_controle(ctx.por_uniq(uniq)) == "mix":
        _dizer_a_fonte_ao_daemon(p, uniq, "sfx")
        _lembrar_do_som(ctx, uniq, speaker={"fonte": "sfx"})

    som_do_controle_na_tv.desligar(uniq)

    desfecho = (
        audio_saida.mandar_o_som_do_pc(uniq, na_mesa)
        if qual == ROTA_TUDO_NO_CONTROLE
        else audio_saida.devolver_o_som_do_pc(de=uniq, uniqs_na_mesa=na_mesa)
    )
    if qual == ROTA_TUDO_NO_CONTROLE and not desfecho.ok:
        raise RuntimeError(desfecho.motivo)

    byte_da_rota = ROTA_DO_CANAL[
        CANAL_TODO_O_PC if qual == ROTA_TUDO_NO_CONTROLE else CANAL_SONS_DO_JOGO]
    if not p.speaker_set(rota=byte_da_rota, uniq=uniq,
                         **_volume_conhecido(ctx.por_uniq(uniq))):
        raise RuntimeError(
            "o Hefesto não confirmou a rota do alto-falante: ou ele parou, ou "
            "este controle se desligou")
    _confirmar_com_som(ctx, uniq)
    _lembrar_do_som(ctx, uniq, speaker={"rota": byte_da_rota})


VOLUME_MIN, VOLUME_MAX = 0, 100

#: fonte de DualSense nenhuma. **Com a queda fechada ele passa a ser a resposta
TEXTO_MIC_SEM_FONTE = (
    "O sistema não vê um microfone neste controle. Nada foi mudado."
)

SENSOR_LIGADO, SENSOR_DESLIGADO = "LIGADO", "DESLIGADO"

SEM_LEITURA_DE_SENSOR = (
    "o Hefesto ainda não disse se este sensor está ligado, e o interruptor "
    "não sabe para que lado ir."
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
    corpo = _corpo(p.sensor_set_detalhado(**{qual: not agora}, uniq=uniq))
    if corpo is None:
        raise RuntimeError(
            "o Hefesto não confirmou o interruptor do sensor: ou ele parou, "
            "ou este controle se desligou")
    frase = frase_do_interruptor_de_sensor(corpo)
    if frase:
        raise RuntimeError(frase)


SEM_LEITURA_DA_MIRA = (
    "a leitura ainda não chegou deste controle, e o botão da mira não sabe "
    "para que lado ir."
)

MIRA_SEM_O_CONTROLE = (
    "este controle não respondeu à mira: conecte-o de novo e tente outra vez."
)

#: (`hefesto_vivo.Piloto._recusou_dizendo`); na tela não entra recado nenhum.
MIRA_CINZA_NO_NATIVO = (
    "Em Modo Nativo o jogo lê este controle direto, e a Mira Virtual não grava."
)


@gesto("02-controles.html", "mira", grava="mira_set_detalhado")
def mira(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O chip «Mira Virtual» — o movimento DESTE controle vira o analógico R dele.

    Palavra dela, 23/09/2026: *"Cria um botão virtual ao lado de giroscopio e
    acelerometro chamado Mira Virtual"*.  <!-- noqa-acento: citação literal dela -->

    O QUE ESTE GESTO FAZ, na ordem do interruptor de sensor (`sensor`, acima):

    1. **LÊ o estado** do bloco `mira` do `daemon.state_full` — o que o tique
       deste controle está usando agora. Sem ele, RECUSA
       (:data:`SEM_LEITURA_DA_MIRA`) em vez de chutar;
    2. **CHAMA `mira.set` com UM campo só**, o `ligada`. A sensibilidade e o
       «Ignorar tremor até» são da tela Calibrar sensores, e mandar os três
       aqui reafirmaria os números dela a cada clique;
    3. **NO MODO NATIVO NÃO PEDE NADA** — A-MIRA-POR-MOVIMENTO-NA-TELA-02,
       palavra dela de 24/09/2026: *"fica cinza no Nativo, sem gravar"*. O
       chip está cinza (`mira-fora`), e o clique recusa ANTES da ponte com
       :data:`MIRA_CINZA_NO_NATIVO`. O daemon tem a MESMA guarda
       (`status: "nativo"`), porque o estado que esta tela leu é de um tique
       atrás: a recusa dele volta pela mesma frase.

    ELE GRAVA NO PERFIL DELA, e por isso declara `grava=`: o chip é a opinião
    DESTE controle (`ControllerOverrides.movimento`), e `mira.set` a leva ao
    disco no mesmo pedido em que ela passa a valer no tique.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira: o clique não disse em qual controle")
    if _nativo(ctx):
        raise RuntimeError(MIRA_CINZA_NO_NATIVO)
    agora = _mira_ligada(ctx.por_uniq(uniq))
    if agora is None:
        raise RuntimeError(SEM_LEITURA_DA_MIRA)
    corpo = _corpo(p.mira_set_detalhado(ligada=not agora, uniq=uniq))
    if corpo is None:
        raise RuntimeError(
            "o Hefesto não confirmou a mira: ou ele parou, ou este controle se "
            "desligou")
    if corpo.get("status") == "nativo":
        raise RuntimeError(MIRA_CINZA_NO_NATIVO)
    if corpo.get("status") != "ok":
        raise RuntimeError(MIRA_SEM_O_CONTROLE)


INCLINACAO_CINZA_NO_NATIVO = (
    "Em Modo Nativo o jogo lê este controle direto, e a Inclinação não grava."
)
TOQUE_CINZA_NO_NATIVO = (
    "Em Modo Nativo o jogo lê este controle direto, e o Cursor e os Botões do "
    "touchpad não gravam."
)

SEM_LEITURA_DO_CHIP = (
    "a leitura ainda não chegou deste controle, e o botão não sabe se apaga "
    "ou acende."
)

CHIP_SEM_O_CONTROLE = (
    "este controle não respondeu: conecte-o de novo e tente outra vez."
)


def _o_que_a_tela_oferece(todos: tuple[str, ...]) -> tuple[str, ...]:
    """Os destinos que um chip pode pedir: os do daemon, menos o `nenhum`."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    return tuple(d for d in todos if d != rot.DESTINO_NENHUM)


def _o_clique_do_chip(o: dict[str, Any], nome: str, pedido: str,
                      todos: tuple[str, ...]) -> str:
    """O `uniq` do cartão clicado, depois de conferir o destino que o botão diz."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError(f"{nome}: o clique não disse em qual controle")
    if pedido not in _o_que_a_tela_oferece(todos):
        raise ValueError(f"{nome}: não conheço o destino {pedido!r}")
    return uniq


def _alternar_o_chip(ctx: Contexto, p: Any, uniq: str, chave: str,
                     pedido: str) -> str:
    """O corpo comum dos dois chips: o clique no apagado acende, no aceso apaga.

    `chave` é a do bloco `mira` do `state_full` e o nome do campo do `mira.set`
    (os dois são `inclinacao` e `toque`). O grupo é um só por controle: acender
    o Cursor com os Botões acesos troca, não soma. Devolve o `status` do daemon
    quando ele é `ok` ou `nativo` (a recusa do Nativo tem a frase de cada chip,
    e quem a levanta é o gesto); o resto levanta aqui.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    agora = _destino_da_mira(ctx.por_uniq(uniq), chave)
    if agora is None:
        raise RuntimeError(SEM_LEITURA_DO_CHIP)
    novo = rot.DESTINO_NENHUM if agora == pedido else pedido
    corpo = _corpo(p.mira_set_detalhado(**{chave: novo}, uniq=uniq))
    if corpo is None:
        raise RuntimeError(
            "o Hefesto não confirmou o botão: ou ele parou, ou este controle "
            "se desligou")
    status = corpo.get("status")
    if status not in ("ok", "nativo"):
        raise RuntimeError(CHIP_SEM_O_CONTROLE)
    return str(status)


@gesto("02-controles.html", "inclinacao", grava="mira_set_detalhado")
def inclinacao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O chip «Inclinação» de um analógico: inclinar o controle move aquele analógico."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    pedido = str(o.get("destino") or "")
    uniq = _o_clique_do_chip(o, "inclinacao", pedido, rot.DESTINOS_DA_INCLINACAO)
    if _nativo(ctx):
        raise RuntimeError(INCLINACAO_CINZA_NO_NATIVO)
    if _alternar_o_chip(ctx, p, uniq, "inclinacao", pedido) == "nativo":
        raise RuntimeError(INCLINACAO_CINZA_NO_NATIVO)


@gesto("02-controles.html", "toque", grava="mira_set_detalhado")
def toque(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O «Cursor | Botões» do touchpad: o dedo move o cursor, ou toca em zonas."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    pedido = str(o.get("toque") or "")
    uniq = _o_clique_do_chip(o, "toque", pedido, rot.TOQUES)
    if _nativo(ctx):
        raise RuntimeError(TOQUE_CINZA_NO_NATIVO)
    if _alternar_o_chip(ctx, p, uniq, "toque", pedido) == "nativo":
        raise RuntimeError(TOQUE_CINZA_NO_NATIVO)


@gesto("02-controles.html", "ganho-mic", grava="gravar_pelo_gesto")
def ganho_mic(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O deslizante do ganho de entrada — **o ato que faltava ao número**.

    Ordem dela, 20/09/2026, olhando a tela instalada:

        "o slicer tá diferente da posição de onde ficaria o slicer da
         versao  # noqa-acento: citação literal dela, e a digitação dela
                não se limpa
         original que eu havia aprovado. além disso não tá funcionando"

    As duas metades da queixa são a mesma falta. O ganho nasceu naquela manhã
    com leitor, barra, número, cinza e razão — e com um `<span class="cheio">`
    no lugar do deslizante. Um `span` PINTA; ele não recebe arrasto. A barra
    mostrava o ganho certo e não havia onde pegá-la.

    **ELE NÃO PASSA PELO DAEMON, e é por desenho.** O ganho de entrada é da
    PLACA (`Headset Capture Volume`, o elemento de captura do `amixer`), não do
    firmware do DualSense: não há método de IPC para ele, e inventar um faria o
    daemon virar intermediário de um valor que o `alsa-lib` já expõe. Quem
    escreve é :func:`definir_ganho_do_microfone`, e quem confirma é a releitura.

    **A RECUSA TEM RAZÃO E ELA JÁ EXISTIA:** :data:`RAZAO_DO_GANHO_FORA` é o
    mesmo texto que pinta o trilho de cinza quando o controle está no rádio.
    Uma segunda frase aqui faria a tela explicar o mesmo fato de duas maneiras.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("ganho-mic: o clique não disse em qual controle")
    if (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click"):
        return
    crua = o.get("valor")
    if crua is None:
        raise ValueError("ganho-mic: o deslizante não mandou valor nenhum")
    try:
        pedido = int(float(crua))
    except (TypeError, ValueError):
        raise ValueError(
            "ganho-mic: o deslizante não mandou um número") from None

    na_mesa = [str(c.get("uniq") or "") for c in ctx.conectados if c.get("uniq")]
    ficou = definir_ganho_do_microfone(uniq, pedido, na_mesa)
    if ficou is None:
        raise RuntimeError(RAZAO_DO_GANHO_FORA)
    # `_lembrar_do_som`: o perfil descreve o que FICOU DE PÉ, não a intenção.
    _lembrar_do_som(ctx, uniq, mic={"gain": ficou[0]})


@gesto("02-controles.html", "volume", grava="gravar_pelo_gesto")
def volume(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Os DOIS deslizantes — o do microfone e o do alto-falante (D-08).

    DECISÃO DELA: *"Deslizante nos dois."* Até 04/09/2026 os dois volumes eram
    PINTURA: `type="range"` aparecia zero vez nas dez páginas, e o que havia era
    `<span class="trilho"><span class="cheio" style="width:N%">`.

    **E A FALTA DELES TRANCAVA O ♪.** O DualSense não devolve o volume do
    alto-falante, então o daemon só publica a chave `speaker` **depois** de
    alguém ESCREVER um (`ipc_handlers.py:3099`); sem escritor nesta tela, o ♪
    recusava para sempre num controle cujo volume nunca foi ajustado por outro
    caminho — e a frase de recusa original mandava *"use o controle deslizante
    primeiro"*, sobre um deslizante que não existia. Este gesto é o escritor que
    faltava: o primeiro arrasto no trilho do alto-falante destrava o ♪.

    **SÃO DOIS MÉTODOS, E NÃO É DETALHE** — é a metade medida da D-12. O
    `mic.volume.set` mexe no ganho da FONTE no PipeWire (é literalmente *"o
    canal específico dele"*) e, desde 12/09/2026 (MIC-VOLUME-02), também no
    registrador `common[6]` do aparelho — mas **não no mudo do firmware**: não
    apaga a luz vermelha e não tira o botão físico do controle.

    **ESTE PARÁGRAFO JÁ DISSE "não toca no firmware", E ERA VERDADE ATÉ 12/09.**
    O fato foi SUBSTITUÍDO, não anotado ao lado: manter as duas versões vivas
    obrigaria a próxima pessoa a escolher entre elas. O que a frase queria
    dizer continua de pé, e é a metade que sobrou. O `speaker.set {volume}`
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
    if (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click"):
        return
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
        corpo = _corpo(p.mic_volume_set_detalhado(pedido, uniq=uniq))
        if corpo is not None and corpo.get("status") == "sem_fonte":
            raise RuntimeError(TEXTO_MIC_SEM_FONTE)
        if corpo is None or corpo.get("status") != "ok":
            raise RuntimeError(
                "o Hefesto não confirmou o volume do microfone: ou ele parou, "
                "ou este controle se desligou")
        # A CONFISSÃO, NA FRASE DO PRODUTO. `frase_do_alvo_do_mic` é a dona dos
        confissao = frase_do_alvo_do_mic(alvo_honrado(corpo))
        if confissao:
            raise RuntimeError(confissao)
        _lembrar_do_som(ctx, uniq, mic={"volume": pedido})
        return

    if qual == "alto-falante":
        registrador = volume_do_percentual(pedido)
        if not p.speaker_set(volume=registrador, uniq=uniq):
            raise RuntimeError(
                "o Hefesto não confirmou o volume do alto-falante: ou ele "
                "parou, ou este controle se desligou")
        _confirmar_com_som(ctx, uniq)
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
      (`ipc_handlers.py:1962`), e cada entrada traz `lightbar_rgb`,
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
    o daemon; o `_ao_alternar_o_microfone` de `secao_controles.py:807` diz por quê: *"o
    processo da janela não pode ter esse gesto ao alcance de um clique enquanto
    a posse do hidraw não for arbitrada — o susto de 16/08/2026"*. Aqui é igual:
    este gesto DECLARA, e o `bt_mic` do daemon reconcilia sozinho — a fonte dele
    é **chamável**, relida a cada varredura, e por isso a escolha vale **sem
    reiniciar o daemon** (`daemon/subsystems/bt_mic.py:60`).

    **O "NATIVO" GRAVA `False` — MUDOU EM 22/09/2026, e é a inversão chegando
    aqui.** Ele gravava `None`, e a razão era boa enquanto o default fosse o
    silêncio: *"'nunca pedi' e 'não quero' deixam a ponte no chão do mesmo
    jeito"*. A ordem dela de 18/09 — *"todos os controles tem que nascer com
    tudo mic, giroscopio e afins"* — inverteu o default, e a ausência passou a
    LIGAR: o `None` virou o botão que não desliga, e a ponte subia no
    hotplug seguinte ao clique. O `False` é o único registro de que ela disse
    não (`bt_mic.uniqs_recusados`), e é o mesmo que o «Desligado» da aba
    Conexões grava desde 18/09 — o gêmeo deste gesto, que foi curado sozinho.

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
    if not _mic_do_produto.pode_ligar_o_mic(dados):
        raise RuntimeError(_mic_do_produto.dica_do_microfone(dados))
    if qual == "nativo" and nativo_fora_de_alcance(uniq):
        raise RuntimeError(RAZAO_DO_NATIVO_FORA)

    ok, motivo = _resposta(p.machine_declare(
        {"controles": {dados.endereco: {
            "microfone": qual == "virtual"}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o modo do microfone")
    _controles_declarados(recarregar=True)


PONTE = {"mic_canal_set_detalhado", "speaker_set", "machine_declare",
         "mic_volume_set_detalhado", "sensor_set_detalhado",
         "mira_set_detalhado"}
METODOS: set[str] = set()

#: O `machine.declare` está **fora do `daemon.state_full` de propósito**, e o
#: botões precisam de `data-campo`/`data-hef-alvo="classe"`/`data-hef-quando`,
SEM_ECO = ("mic-modo",)


PISO_DA_ABA = 8
#: estado o motor manda o botão ficar INSENSÍVEL (`acao_mic`,
PROVAS = [
    {"pagina": PAGINA, "gesto": "rota", "clique": {"rota": "jogo"},  # (noqa-acento) id
     "chama": [("speaker_set", [],
                {"rota": SAIDA_L_FONE_R_ALTO_FALANTE, "uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "nativo"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": False}}}], {})]},
    # agora `machine_declare` é CHAMADO. Se alguém devolver o `not no_cabo` a
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "virtual"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": True}}}], {})]},
    {"pagina": PAGINA, "gesto": "volume",  # (noqa-acento) id
     "clique": {"volume": "microfone", "v": "80"},
     "chama": [("mic_volume_set_detalhado", [80], {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "volume",  # (noqa-acento) id
     "clique": {"volume": "alto-falante", "v": "80"},
     "chama": [("speaker_set", [],
                {"volume": volume_do_percentual(80),
                 "uniq": "aa:bb:cc:00:00:01"})]},
]

SEM_CHAMADA = ("sensor", "mira", "inclinacao", "toque")
