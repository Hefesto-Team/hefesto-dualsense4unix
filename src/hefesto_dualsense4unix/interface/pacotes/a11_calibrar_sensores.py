#!/usr/bin/env python3
"""A calibração mostra quem está na mão de quem abre — `calibrar-sensores.html`.

F3-CALIBRAR, 11/09/2026. Nasce da §1 da `A-FILA-QUE-A-ONDA-ABRIU`, e o defeito
estava medido antes desta sprint (`PAGINAS-ESPECIAIS-B1`, §2.4):

    `calibrar-sensores.html` tem 0 `data-campo` e 0 `data-gesto`, e o piloto
    confirma: `página trocada no meio do tique: calibrar-sensores.html 1`, com
    **zero pinturas**.

O QUE A TELA DIZIA E O QUE O APARELHO RESPONDIA, medido no daemon do usuário em
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

import functools
from typing import Any

import calibrar
import mesa_viva

from hefesto_dualsense4unix.interface.cartao_do_controle import (
    accel_do_inputs,
    gyro_do_inputs,
)
from hefesto_dualsense4unix.interface.monta import quem_joga_com_o_numero
from hefesto_dualsense4unix.interface.sensores import (
    ESCALA_ACCEL_G,
    ESCALA_GYRO_GRAUS_S,
    texto_eixo,
    texto_eixo_g,
)

from . import Contexto, gesto, registrar
from .a02_controles import (
    MIRA_SEM_O_CONTROLE,
    SEM_LEITURA_DA_MIRA,
    _corpo,
    _selo_do_sensor,
    _uniq,
    meias_da_barra,
    nomes_de_quem_joga,
)

PAGINA = "calibrar-sensores.html"

BLOCO_DOS_CONTROLES = '[data-bloco="controles"]'

SENSORES = (
    ("giro", gyro_do_inputs, ESCALA_GYRO_GRAUS_S, texto_eixo),
    ("accel", accel_do_inputs, ESCALA_ACCEL_G, texto_eixo_g),
)

BLOCO_DAS_MIRAS = '[data-bloco="miras"]'

#: O separador de uma frase só, o da casa («BT • Navega o PC»).
PONTO = " • "

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
    if "gatilho" in b:
        gatilho = b.get("gatilho")
        if gatilho is None:
            campos["mira-segurar"] = calibrar.SEMPRE
        elif gatilho in calibrar.REMAPEAVEIS:
            campos["mira-segurar"] = str(gatilho)
    for qual, _rotulo, chave in calibrar.INVERTER:
        valor = b.get(chave)
        campos[f"mira-inverter-{qual}"] = _selo_do_sensor(
            valor if isinstance(valor, bool) else None)
    return campos


#: O QUE O DAEMON DIZ DA MIRA, em cinco chaves (`ipc_handlers._merge_mira`): se nenhuma vem, o bloco
#: não é o da mira e o resumo não existe.
CHAVES_DOS_AJUSTES = ("sensibilidade", "zona_morta_graus_s", "gatilho",
                      "inverter_horizontal", "inverter_vertical")

#: O bloco que a CENA dos geradores (06, 08 e 10) carrega: os números de nascença da Calibrar
#: (`calibrar.SENSIBILIDADE`, `calibrar.TREMOR`), o «Sempre» e nenhum lado invertido. A cena não
#: digita número: lê o mesmo dono que o produto.
def bloco_de_nascenca(ligada: bool = True) -> dict[str, Any]:
    """O bloco `mira` de um controle com os ajustes de nascença; `ligada` é só o chip."""
    return {"ligada": ligada, "sensibilidade": calibrar.SENSIBILIDADE[2],
            "zona_morta_graus_s": calibrar.TREMOR[2], "gatilho": None,
            "inverter_horizontal": False, "inverter_vertical": False}


@functools.lru_cache(maxsize=1)
def _pecas_do_mapa() -> dict[str, Any]:
    """O mapa das peças, lido UMA vez (o nome do botão do «segurar» sai dele)."""
    return dict(calibrar._pecas())


def _numero(valor: Any) -> str:
    ok = isinstance(valor, (int, float)) and not isinstance(valor, bool)
    return str(round(valor)) if ok else str(calibrar.SEM_LEITURA)


def _o_segurar(b: dict[str, Any]) -> str:
    """O texto do «Só enquanto eu segurar»: «Sempre», o botão, ou o travessão sem leitura."""
    if "gatilho" not in b:
        return str(calibrar.SEM_LEITURA)
    gatilho = b["gatilho"]
    if gatilho is None:
        return str(calibrar.ROTULO_SEMPRE)
    if gatilho in calibrar.REMAPEAVEIS:
        return str(calibrar.nome_do_botao(gatilho, _pecas_do_mapa()))
    return str(calibrar.SEM_LEITURA)


def resumo_da_mira(bloco: Any, curto: bool = False) -> str | None:
    """Os quatro ajustes da Mira de UM controle numa frase, pelo bloco `mira` do daemon.

    É o irmão de leitura do `_campos_da_mira`: o MESMO bloco, os mesmos cinco campos, e as
    palavras são as da Calibrar (`calibrar.ROTULO_*`, `calibrar.nome_do_botao`) — nenhuma nasce
    aqui. As abas Navegação, Conexões e Perfis dizem os números por esta função, e a Calibrar
    segue sendo o lugar de MUDAR.

    `curto` é o que cabe num cartão estreito: só os valores, na ordem da Calibrar
    (`6 • 3 graus/s • Sempre`). O inteiro leva o rótulo de cada um e os lados invertidos
    (`dica` de quem tem a frase de sobra). Sem o bloco, `None`: a tela não inventa número.
    """
    if not isinstance(bloco, dict) or not any(k in bloco for k in CHAVES_DOS_AJUSTES):
        return None
    anda = _numero(bloco.get("sensibilidade"))
    tremor = f"{_numero(bloco.get('zona_morta_graus_s'))} {calibrar.UNIDADE_DO_TREMOR}"
    segurar = _o_segurar(bloco)
    if curto:
        return f"{anda}{PONTO}{tremor}{PONTO}{segurar}"
    partes = [f"{calibrar.ROTULO_SENSIBILIDADE}: {anda}",
              f"{calibrar.ROTULO_TREMOR}: {tremor}",
              f"{calibrar.ROTULO_SEGURAR}: {segurar}"]
    lados = [rotulo[0].lower() + rotulo[1:] for qual, rotulo, chave in calibrar.INVERTER
             if bloco.get(chave) is True]
    if lados:
        partes.append(f"{calibrar.ROTULO_INVERTER}: {', '.join(lados)}")
    return PONTO.join(partes)


SEM_DONO = ("calibrar", )


def _eixos_do_controle(entrada: dict[str, Any]) -> dict[str, Any]:
    """Os doze campos de leitura de um controle: quatro por eixo, seis eixos."""
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
    índice inverte os dois controles do usuário na primeira execução, e a razão inteira
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
    # QUEM JOGA, pela regra única de `monta` e pelo leitor da 08: o cartão e a coluna da mira
    # dizem `<nome> • P<n>`, ou só `P<n>` sem nome. O número é o vivo (`item["jogador"]`).
    nomes = nomes_de_quem_joga()
    com_quem = [{**item, "quem": quem_joga_com_o_numero(
        nomes, str(item.get("uniq") or ""), item.get("jogador"))} for item in ctx.mesa]
    blocos = {BLOCO_DOS_CONTROLES: calibrar.controles(com_quem)}
    if tem_a_mira:
        blocos[BLOCO_DAS_MIRAS] = calibrar.miras(com_quem)
    return {
        "blocos": blocos,
        "quantos": calibrar.contagem(len(ctx.mesa)),
        "colunas": colunas,
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()) + 1,
                      "sem_dono": len(SEM_DONO)},
        "sem_dono": {chave: "" for chave in SEM_DONO},
    }


def _pedir_a_mira(p: Any, uniq: str, **campo: Any) -> None:
    """Manda UM campo da mira ao daemon e recusa quando ele não confirma."""
    corpo = _corpo(p.mira_set_detalhado(uniq=uniq, **campo))
    if corpo is None:
        raise RuntimeError(
            "o Hefesto não confirmou a mira: ou ele parou, ou este controle se "
            "desligou")
    if corpo.get("status") != "ok":
        raise RuntimeError(MIRA_SEM_O_CONTROLE)


def _numero_do_deslizante(o: dict[str, Any], nome: str, faixa: tuple[int, int, int]) -> int | None:
    """O número que o polegar marca, ou `None` quando o evento é o `click` repetido."""
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
    """«O quanto um gesto anda» — a sensibilidade da mira DESTE controle."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-sensibilidade: o clique não disse em qual controle")
    n = _numero_do_deslizante(o, "mira-sensibilidade", calibrar.SENSIBILIDADE)
    if n is not None:
        _pedir_a_mira(p, uniq, sensibilidade=n)


@gesto(PAGINA, "mira-tremor", grava="mira_set_detalhado")
def mira_tremor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Ignorar tremor até» — o giro abaixo disto não move a mira, em graus/s."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-tremor: o clique não disse em qual controle")
    n = _numero_do_deslizante(o, "mira-tremor", calibrar.TREMOR)
    if n is not None:
        _pedir_a_mira(p, uniq, zona_morta_graus_s=float(n))


@gesto(PAGINA, "mira-segurar", grava="mira_set_detalhado")
def mira_segurar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Só enquanto eu segurar» — a mira DESTE controle só anda com o botão"""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-segurar: o clique não disse em qual controle")
    if str(o.get("evento") or "").lower() == "click":
        return {"armou": True}
    escolha = str(o.get("valor") or "").strip()
    if escolha == calibrar.SEMPRE:
        _pedir_a_mira(p, uniq, gatilho="")
        return None
    if escolha not in calibrar.REMAPEAVEIS:
        raise ValueError(f"mira-segurar: {escolha!r} não é um botão da lista")
    _pedir_a_mira(p, uniq, gatilho=escolha)
    return None


@gesto(PAGINA, "mira-inverter", grava="mira_set_detalhado")
def mira_inverter(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Inverter» — um lado de cada vez: o `data-inverter` diz qual.

    LÊ o estado do bloco `mira` do `state_full`, como o chip da aba Controles:
    sem a leitura, alternar é chutar o oposto, e o gesto recusa
    (:data:`a02_controles.SEM_LEITURA_DA_MIRA`) em vez de chutar.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mira-inverter: o clique não disse em qual controle")
    qual = str(o.get("inverter") or "")
    chave = next((c for q, _r, c in calibrar.INVERTER if q == qual), None)
    if chave is None:
        raise ValueError(f"mira-inverter: não conheço o lado {qual!r} — a página "
                         f"manda 'lado' ou 'cima-baixo'")
    bloco = ctx.por_uniq(uniq).get("mira")
    agora = bloco.get(chave) if isinstance(bloco, dict) else None
    if not isinstance(agora, bool):
        raise RuntimeError(SEM_LEITURA_DA_MIRA)
    _pedir_a_mira(p, uniq, **{chave: not agora})
