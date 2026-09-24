#!/usr/bin/env python3
"""A calibração mostra quem está na mão de quem abre — `calibrar-sensores.html`.

F3-CALIBRAR, 11/09/2026. Nasce da §1 da `A-FILA-QUE-A-ONDA-ABRIU`, e o defeito
estava medido antes desta sprint (`PAGINAS-ESPECIAIS-B1`, §2.4):

    `calibrar-sensores.html` tem 0 `data-campo` e 0 `data-gesto`, e o piloto
    confirma: `página trocada no meio do tique: calibrar-sensores.html 1`, com
    **zero pinturas**.

O QUE A TELA DIZIA E O QUE O APARELHO RESPONDIA, medido no daemon dela em
11/09/2026 com os dois DualSense na bancada::

    a tela                          o `daemon.state_full`
    P1 · Cosmic Red · USB           P1 · Starlight Blue · USB
    P2 · Starlight Blue · BT        P2 · Cosmic Red · BT
    giro  +0.2 / -0.1 / +0.0        `inputs` sem chave `gyro`
    accel +0.105 / +0.976 / +0.170  `inputs` sem chave `accel`

**Os dois controles trocados e as doze leituras inventadas** — e com quatro na
bancada ela veria dois, porque a lista era `monta.CONECTADOS`, o DESENHO.

ESTE PACOTE É A METADE QUE FALTAVA. Ele faz três coisas, e só três:

1. **remonta o bloco dos cartões** com quem está conectado AGORA, pelo próprio
   gerador (`calibrar.controles`) — nunca por HTML escrito aqui;
2. **escreve a leitura de cada eixo** de cada controle, por `data-campo`, com o
   travessão onde não há leitura;
3. **diz quantos são**, com a concordância do dono (`calibrar.contagem`).

POR QUE O NOME COMEÇA COM `a11_` E ISTO NÃO É A ABA 11. A calibração é página
AVULSA — abre por fora das dez, por um botão da Controles. O prefixo existe
porque é o que as réguas desta casa VARREM: `test_a_palavra_mesa_nao_chega_a_
tela.py` e `test_os_botoes_tem_dono.py` fazem `glob("a??_*.py")` e
`glob("a[0-9][0-9]_*.py")`, e o `_carregar_tudo()` do despachante usa o mesmo
molde. Um arquivo fora dele nasceria **invisível para o portão da língua** e
teria de ser importado à mão em `__init__.py` — duas cópias do mesmo fato.

O QUE ELE NÃO FAZ, e é escolha: **não liga o botão «Começar»**. O daemon não tem
método de calibração (não há `gyro.*`, `motion.*` nem `sensor.*` em
`daemon/ipc_handlers.py` que zere o repouso), e um botão que responde calado é
pior que um que recusa — regra da casa, e a razão pela qual sete gestos da aba
Sistema seguem sem dono de propósito. O botão fica sem gesto, e o piloto o
recusa dizendo o nome.

DE ONDE VEM CADA IMPORT, porque dois deles surpreendem:

* `calibrar` e `mesa_viva` são importados PLANOS, sem caminho montado aqui: o
  `sys.path` já tem a pasta `interface/` quando este módulo carrega — quem a põe
  é o `pacotes/__init__.py`, no topo — e assim os dois são os MESMOS objetos que
  o piloto e os geradores usam, em vez de uma segunda cópia de cada;
* `meias_da_barra` é PÚBLICA e tem um dono só. Ela re-expressa o que
  `mesa_viva._barra_bipolar` devolve na gramática que o produto alcança (duas
  metades ancoradas no centro), e redigitá-la aqui seria a segunda cópia que a
  LEI 0 desta casa proíbe. A aba Controles é onde ela mora porque foi lá que
  nasceu; nada nela é da aba.
"""
from __future__ import annotations

from typing import Any

import calibrar
import mesa_viva

from hefesto_dualsense4unix.app.widgets.controller_card import (
    accel_do_inputs,
    gyro_do_inputs,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    ESCALA_ACCEL_G,
    ESCALA_GYRO_GRAUS_S,
    texto_eixo,
    texto_eixo_g,
)

from . import Contexto, gesto, registrar
from .a02_controles import (
    MIRA_SEM_O_CONTROLE,
    _corpo,
    _uniq,
    meias_da_barra,
)

#: A PÁGINA, escrita uma vez. É o nome do arquivo, que é o que o `load-changed`
#: do WebView entrega ao despachante.
PAGINA = "calibrar-sensores.html"

#: O SELETOR DO BLOCO QUE O PRODUTO TROCA. Ele vive escrito em DOIS lugares — o
#: `data-bloco="controles"` do gerador e este — e não há como ser um só: um é
#: atributo de HTML e o outro é chave de um dicionário Python. A régua
#: `test_a_calibracao_mostra_quem_esta_na_mao.py` mede os dois um contra o outro.
BLOCO_DOS_CONTROLES = '[data-bloco="controles"]'

#: AS DUAS FAMÍLIAS DE EIXO E QUEM RESPONDE POR CADA UMA — o leitor do `inputs`,
#: a escala da barra e a grafia do número. **Nada disto é regra nova**: os seis
#: donos são os do produto, os mesmos que a aba Controles chama
#: (`controller_card.gyro_do_inputs`, `sensor_widgets.texto_eixo`…). O que este
#: arquivo escreve é só o ENDEREÇO, que é dele.
SENSORES = (
    ("giro", gyro_do_inputs, ESCALA_GYRO_GRAUS_S, texto_eixo),
    ("accel", accel_do_inputs, ESCALA_ACCEL_G, texto_eixo_g),
)

#: O BLOCO DA MIRA VIRTUAL — 24/09/2026, A-MIRA-POR-MOVIMENTO-NA-TELA-01. É o
#: `data-bloco="miras"` do gerador, e ele só é remontado (e só se pinta dentro
#: dele) quando a página PUBLICADA o tiver: o desenho novo espera o OK dela, e
#: emitir para um endereço que a página não tem é pintar no vazio.
BLOCO_DAS_MIRAS = '[data-bloco="miras"]'

_TEM_A_MIRA: bool | None = None


def _a_pagina_tem_a_mira() -> bool:
    """A página PUBLICADA já tem o bloco da mira? Lido uma vez por processo."""
    global _TEM_A_MIRA
    if _TEM_A_MIRA is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            doc = ""
        _TEM_A_MIRA = BLOCO_DAS_MIRAS.strip("[]") in doc
    return _TEM_A_MIRA


def _campos_da_mira(entrada: dict[str, Any]) -> dict[str, Any]:
    """A posição dos dois deslizantes e os dois números, pelo bloco `mira`.

    O bloco é o que o `daemon.state_full` publica por controle
    (`ipc_handlers._merge_mira`) — os números que o tique DESTE controle usa.
    Sem ele, travessão nos números e o trilho onde está: escrever uma posição
    de palpite moveria o polegar dela para um valor que ninguém leu.
    """
    bloco = entrada.get("mira")
    b: dict[str, Any] = bloco if isinstance(bloco, dict) else {}
    campos: dict[str, Any] = {}
    for campo, chave in (("mira-sensibilidade", "sensibilidade"),
                         ("mira-tremor", "zona_morta_graus_s")):
        valor = b.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            campos[campo] = str(round(valor))
            campos[f"{campo}-num"] = str(round(valor))
        else:
            campos[f"{campo}-num"] = calibrar.SEM_LEITURA
    return campos


#: O QUE A PÁGINA OFERECE E O PRODUTO NÃO FAZ — e ele é declarado aqui para que
#: a `cobertura` não passe por completa. Ver a última seção da docstring.
SEM_DONO = ("calibrar", )


def _eixos_do_controle(entrada: dict[str, Any]) -> dict[str, Any]:
    """Os doze campos de leitura de um controle: quatro por eixo, seis eixos.

    `lido is None` é *"a leitura não chegou"*, e é o desfecho honesto: travessão
    no número e barra a zero. **Ele é o caso comum na bancada dela hoje** —
    medido em 11/09: `sensores.grab_do_movimento = "sem_reader"` nos dois
    controles, e por isso `inputs` sai sem a chave `gyro`. Desenhar zero ali
    seria repouso mentiroso, que é a lição que o `_merge_sensores` do daemon já
    escreve do lado dele.
    """
    lido = entrada.get("inputs")
    e: dict[str, Any] = lido if isinstance(lido, dict) else {}
    campos: dict[str, Any] = {}
    for familia, leitor, escala, grafia in SENSORES:
        valores = leitor(e)
        for i, eixo in enumerate("xyz"):
            valor = valores[i] if valores is not None else None
            chave = f"{familia}-{eixo}"
            neg, pos, cor = meias_da_barra(mesa_viva._barra_bipolar(valor, escala))
            campos[chave] = grafia(valor) if valor is not None else calibrar.SEM_LEITURA
            campos[f"{chave}-neg"] = neg
            campos[f"{chave}-pos"] = pos
            campos[f"{chave}-cor"] = cor
    return campos


@registrar(PAGINA)
def pacote(ctx: Contexto) -> dict[str, Any]:
    """O que o tique escreve nesta página: os cartões, as leituras e a conta.

    A ORDEM DOS CARTÕES É A DA BANCADA (`ctx.mesa`), que é a ordem do PRODUTO —
    por `player_slot`, não pela posição no `controllers` do IPC. Desenhar por
    índice inverte os dois controles dela na primeira execução, e a razão inteira
    está em `mesa_viva`, disciplina 1.

    A CHAVE DA COLUNA É O `pref` DA BANCADA, e não o endereço do aparelho: é o
    `pref` que o gerador acaba de escrever no `data-controle` de cada cartão,
    duas linhas acima. Mandar o endereço obrigaria a tradução do despachante a
    casar de volta o que este mesmo pacote já sabe.
    """
    colunas: dict[str, dict[str, Any]] = {}
    tem_a_mira = _a_pagina_tem_a_mira()
    for item in ctx.mesa:
        pref = str(item.get("pref") or "")
        if not pref:
            continue
        dele = ctx.por_uniq(str(item.get("uniq") or ""))
        colunas[pref] = _eixos_do_controle(dele)
        if tem_a_mira:
            colunas[pref].update(_campos_da_mira(dele))
    blocos = {BLOCO_DOS_CONTROLES: calibrar.controles(ctx.mesa)}
    if tem_a_mira:
        blocos[BLOCO_DAS_MIRAS] = calibrar.miras(ctx.mesa)
    return {
        "blocos": blocos,
        "quantos": calibrar.contagem(len(ctx.mesa)),
        "colunas": colunas,
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()) + 1,
                      "sem_dono": len(SEM_DONO)},
        # O NOME do órfão, e não só a contagem — 11/09/2026. A `cobertura`
        # dizia *quantos*, e `test_o_perfil_chega_na_tela` pergunta *quais*:
        # sem esta chave a página entrava na régua com a contagem cheia e a
        # lista vazia, que é uma dívida sem endereço. Os outros dez pacotes já
        # devolvem as duas coisas.
        "sem_dono": {chave: "" for chave in SEM_DONO},
    }


# ---------------------------------------------------------------------------
# OS DOIS DESLIZANTES DA MIRA — 24/09/2026, A-MIRA-POR-MOVIMENTO-NA-TELA-01
# ---------------------------------------------------------------------------
def _pedir_a_mira(p: Any, uniq: str, **campo: Any) -> None:
    """Manda UM campo da mira ao daemon e recusa quando ele não confirma.

    AS FRASES SÃO AS DO CHIP da aba Controles (`a02_controles.mira`), que é o
    mesmo pedido: duas redações para a mesma recusa seriam a tela explicando o
    mesmo fato de duas maneiras.

    NO MODO NATIVO O AJUSTE GRAVA E NÃO RECUSA — A-MIRA-POR-MOVIMENTO-NA-TELA-02.
    Até aqui o `alcance.tique = "nao_se_aplica"` virava recusa com a frase do
    Nativo; ela escolheu *"fica cinza no Nativo, sem gravar"* para o CHIP, e o
    ajuste daqui não acende mira nenhuma: ele grava e vale quando o modo voltar,
    calado, como qualquer ajuste que deu certo.
    """
    corpo = _corpo(p.mira_set_detalhado(uniq=uniq, **campo))
    if corpo is None:
        raise RuntimeError(
            "o Hefesto não confirmou a mira: ou ele parou, ou este controle se "
            "desligou")
    if corpo.get("status") != "ok":
        raise RuntimeError(MIRA_SEM_O_CONTROLE)


def _numero_do_deslizante(o: dict[str, Any], nome: str, faixa: tuple[int, int, int]) -> int | None:
    """O número que o polegar marca, ou `None` quando o evento é o `click` repetido.

    O `click` QUE VEM DEPOIS DO `change` NÃO É UM SEGUNDO PEDIDO — a mesma
    guarda do deslizante de volume da aba Controles, e pela mesma razão: um
    `<input type="range">` clicado na pista dispara `change` e `click`.
    """
    if (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click"):
        return None
    cru = str(o.get("valor") or o.get("v") or "").strip()
    try:
        n = int(float(cru))
    except (TypeError, ValueError):
        raise ValueError(f"{nome}: o deslizante mandou {cru!r}, que não é um "
                         f"número") from None
    minimo, maximo, _ = faixa
    if not minimo <= n <= maximo:
        raise ValueError(f"{nome}: {n} está fora de {minimo}-{maximo}")
    return n


@gesto(PAGINA, "mira-sensibilidade", grava="mira_set_detalhado")
def mira_sensibilidade(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«O quanto um gesto anda» — a sensibilidade da mira DESTE controle.

    UM CAMPO SÓ: mexer aqui não acende nem apaga o chip, e não mexe no tremor.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-sensibilidade: o clique não disse em qual controle")
    n = _numero_do_deslizante(o, "mira-sensibilidade", calibrar.SENSIBILIDADE)
    if n is not None:
        _pedir_a_mira(p, uniq, sensibilidade=n)


@gesto(PAGINA, "mira-tremor", grava="mira_set_detalhado")
def mira_tremor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Ignorar tremor até» — o giro abaixo disto não move a mira, em graus/s.

    É o campo de acessibilidade desta tela: um tremor essencial mora em 15 a 30
    graus/s, muito acima do que a curva da mira corta sozinha (§3 da sprint).
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-tremor: o clique não disse em qual controle")
    n = _numero_do_deslizante(o, "mira-tremor", calibrar.TREMOR)
    if n is not None:
        _pedir_a_mira(p, uniq, zona_morta_graus_s=float(n))
