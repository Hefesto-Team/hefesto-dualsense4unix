#!/usr/bin/env python3
"""O mapa do controle pisca, segue a troca de botões e diz qual controle mostra.

`mapa-do-controle.html`, O-MAPA-DO-CONTROLE-PISCA-E-SEGUE-O-REMAPEAMENTO-01. A
fala dela, 29/09/2026, com os quatro DualSense na mesa:

    «Mesmo Sistema que implementamos na aba Controles para cada botão piscar
    quando apertarmos ele no controle fisico deve ser implementado no Mapa do  (noqa-acento: dela)
    Controle. (…) imagina que fulano tenha alterado ele pra refletir o botão X
    por questão de acessibilidade lá devemos mostrar isso (…) Falta um filtro
    pro controle conectado que está sendo visto ali.»

A CAUSA, medida antes: o mapa nasceu como página de REFERÊNCIA do desenho e
nunca foi ligado ao produto (zero `data-campo`, nenhum pacote); o «Jogador»
dele era um simulador local. As quatro queixas são a mesma ausência.

O QUE ELE PINTA, para o controle que a fita escolheu (`Contexto.escolhido`, a
mesma escolha das abas; com «Todos», a mesa inteira). Cada valor sai do dono que
já o calcula para outra tela, e nenhuma regra é copiada:

* ``aceso-<peça>`` (alvo `classe`): o botão FÍSICO sob o dedo, pela leitura do
  pisca da Controles (`a02_controles.leitura_viva`). Com «Todos», a união. A
  troca não muda o pisca: o daemon a aplica só no caminho do JOGO, e o
  `inputs` é o do aparelho (`daemon/subsystems/gamepad.py`, antes do
  `forward_buttons`).
* ``aceso-<sensor>`` (alvo `classe`), O-MAPA-DO-CONTROLE-ACENDE-TODO-SENSOR-01
  (03/10/2026): o toque no touchpad (`aceso-touchpad`, junto do clique), o som
  no mic (`aceso-mic`, junto do botão), o giroscópio e o acelerômetro quando o
  controle se move, os dois motores e a háptica quando vibram. Cada um sai do
  dono que a Controles e a Vibração já usam (`dedos_do_inputs`, `ondas_de_som`,
  `gyro_do_inputs`/`accel_do_inputs`, `rumble_ff.per_vpad`, `haptica_no_ar`).
* ``troca-<peça>`` (alvo `html`): o destino da troca de botões do perfil
  ativo, a mesma linha da tela «Trocar os botões» da Navegação
  (`a06_navegacao._linhas_da_troca`); vazio quando não troca. A troca é global
  no perfil (D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL) e vale para os quatro.
  ``trocada-<peça>`` (alvo `classe`) é a mesma resposta em sim/não: mostra a
  linha «No jogo» e a marca tracejada da peça no desenho.
* ``acao-<peça>`` (alvo `atributo`, o `title`): o que o botão faz na
  Navegação (`a06_navegacao._linhas_dos_botoes`, a tabela que vai ao device).
* ``papel`` (alvo `html`): « · Na Navegação: » e a linha do cartão dele na
  Navegação (`a06_navegacao.linha_do_cartao`), ao lado do rótulo «Controle».
* ``luz-cor`` (alvo `cor`): a barra de luz, com a cor do cartão da Controles
  (`a02_controles._cor_da_barra`).
* o bloco dos chips (`BLOCO_DOS_CONTROLES`, alvo de bloco): um por controle
  da mesa, com o gesto da fita, mais «Todos» e «Nenhum». O desenho (o modelo
  do plástico e as cinco lâmpadas) segue o chip aceso pelo script da página.

Três funções privadas de outras abas são usadas aqui, declaradas: a
alternativa seria a segunda verdade da troca, da tabela de botões e da cor da
barra, que esta casa persegue.
"""
from __future__ import annotations

import html
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.core.led_control import player_slot_color
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    ALL_BUTTONS,
    accel_do_inputs,
    dedos_do_inputs,
    gyro_do_inputs,
    rotulo_lightbar,
)

from . import Contexto, perfil, registrar
from . import a02_controles as a02
from . import a05_vibracao as a05
from . import a06_navegacao as a06

PAGINA = "mapa-do-controle.html"

BLOCO_DOS_CONTROLES = '[data-bloco="controles-do-mapa"]'

ACESO = "aceso-"  # (noqa-acento) prefixo de endereço, não é prosa
TROCA = "troca-"  # (noqa-acento) prefixo de endereço, não é prosa
TROCADA = "trocada-"  # (noqa-acento) prefixo de endereço, não é prosa
ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa
PAPEL = "papel"
LUZ = "luz-cor"

#: as peças que acendem pelo ESTADO do serviço e não por um botão: os cinco
#: marcadores do desenho que o mapa nomeia como sensores, mais a háptica.
SENSORES: tuple[str, ...] = ("feat-giroscopio", "feat-acelerometro",
                             "feat-rumble-esquerdo", "feat-rumble-direito",
                             "feat-haptica")

#: o controle «se move» quando o giroscópio passa disto (graus/s) ou o
#: acelerômetro varia mais que isto (g) entre dois tiques. Abaixo, é o ruído
#: do sensor parado: a zona morta que a Controles já respeita é de 3 graus/s.
GIRO_MIN = 5.0
ACEL_MIN = 0.04

#: o mic «tem som» quando o medidor de ondas passa do piso por esta margem (%).
SOM_ACIMA_DO_PISO = 6

#: a última leitura do acelerômetro por controle, que é o que faz da variação
#: uma medida: o `inputs` traz a aceleração, não a mudança dela.
_ULTIMA_ACEL: dict[str, tuple[float, float, float]] = {}

#: o motor forte é o ESQUERDO (índice 1 do par weak/strong), o leve o direito.
FORTE, LEVE = 1, 0

#: nos dois lados (`ALL_BUTTONS`).
NOME_NO_LEITOR = {"stick_l": "l3", "stick_r": "r3", "mic": "mic_btn"}

PISCAM: tuple[str, ...] = (*ALL_BUTTONS, *NOME_NO_LEITOR)

NOME_NA_TROCA = {"stick_l": "l3", "stick_r": "r3", "share": "create"}

TROCAM: tuple[str, ...] = tuple(
    next((peca for peca, b in NOME_NA_TROCA.items() if b == botao), botao)
    for botao in remap.REMAPEAVEIS)

LINHAS_DA_PECA: dict[str, tuple[tuple[str, str], ...]] = {
    "stick_l": ((acoes.EIXO_ESQUERDO, "direção"), ("l3", "clique")),
    "stick_r": ((acoes.EIXO_DIREITO, "direção"), ("r3", "clique")),
    "share": (("create", ""),),
    "touchpad": (("touchpad_left_press", "clique esquerdo"),
                 ("touchpad_right_press", "clique direito"),
                 ("touchpad_middle_press", "clique central")),
}

NA_NAVEGACAO: tuple[str, ...] = tuple(dict.fromkeys(
    next((peca for peca, linhas in LINHAS_DA_PECA.items()
          if any(b == botao for b, _ in linhas)), botao)
    for botao in acoes.BOTOES))


def _escolhidos(ctx: Contexto) -> tuple[str, list[dict[str, Any]]]:
    """Quem a fita escolheu, e os itens da mesa que isso alcança."""
    import monta

    escolhido = ctx.escolhido or (str(ctx.mesa[0].get("pref") or "") if ctx.mesa else "")
    _, ativo = monta.escolha_da_fita(escolhido or "todos", ctx.mesa)
    if ativo == "todos":
        return ativo, list(ctx.mesa)
    return ativo, [m for m in ctx.mesa if str(m.get("pref") or "") == ativo]


def _acesos(ctx: Contexto, itens: list[dict[str, Any]]) -> dict[str, str]:
    """`aceso-<peça>`: `"sim"` se algum dos controles alcançados aperta a peça."""
    acesos = dict.fromkeys(PISCAM, False)
    nos = {no: str(i.get("uniq") or "") for i in itens
           for no in (a02.no_do_microfone(ctx.por_uniq(str(i.get("uniq") or ""))),) if no}
    a02._seguir_as_ondas(nos)
    for item in itens:
        entrada = ctx.por_uniq(str(item.get("uniq") or ""))
        glifos = a02.leitura_viva(entrada)
        lido = entrada.get("inputs")
        apertados = {str(b) for b in ((lido or {}).get("buttons") or ())} \
            if isinstance(lido, dict) else set()
        for peca in PISCAM:
            if peca in NOME_NO_LEITOR:
                acesos[peca] = acesos[peca] or NOME_NO_LEITOR[peca] in apertados
            else:
                acesos[peca] = acesos[peca] or glifos.get(f"glifo-{peca}") == "sim"
    for peca, ligado in _sensores(ctx, itens).items():
        acesos[peca] = acesos.get(peca, False) or ligado
    return {f"{ACESO}{peca}": ("sim" if aceso else "") for peca, aceso in acesos.items()}


def _se_move(uniq: str, entrada: dict[str, Any]) -> tuple[bool, bool]:
    """`(giroscópio, acelerômetro)` em movimento neste tique. Sem leitura, nenhum."""
    lido = entrada.get("inputs")
    giro = gyro_do_inputs(lido)
    accel = accel_do_inputs(lido)
    gira = giro is not None and max(abs(v) for v in giro) > GIRO_MIN
    antes = _ULTIMA_ACEL.get(uniq)
    if accel is None:
        _ULTIMA_ACEL.pop(uniq, None)
        return gira, False
    _ULTIMA_ACEL[uniq] = accel
    pares = zip(accel, antes, strict=True) if antes is not None else ()
    anda = max((abs(a - b) for a, b in pares), default=0.0) > ACEL_MIN
    return gira, anda


def _som_no_mic(entrada: dict[str, Any]) -> bool:
    """O medidor do mic do controle passou do piso: há som entrando."""
    alturas = a02.alturas_do_no(a02.no_do_microfone(entrada))
    if not alturas:
        return False
    return max(alturas) > a02._piso_da_onda() + SOM_ACIMA_DO_PISO


def _motores(state: dict[str, Any], jogador: int) -> tuple[bool, bool]:
    """`(esquerdo, direito)` com o jogo mandando vibração a este jogador agora."""
    ff = state.get("rumble_ff")
    for vp in (ff.get("per_vpad") or ()) if isinstance(ff, dict) else ():
        if not isinstance(vp, dict) or vp.get("player") != jogador:
            continue
        par = vp.get("rumble_no_fisico")
        idade = vp.get("rumble_no_fisico_ha_s")
        if not (isinstance(par, (list, tuple)) and len(par) == 2):
            return False, False
        if isinstance(idade, (int, float)) and idade > 2.0:
            return False, False
        return bool(par[FORTE]), bool(par[LEVE])
    return False, False


def _sensores(ctx: Contexto, itens: list[dict[str, Any]]) -> dict[str, bool]:
    """O estado de cada sensor: aceso se algum dos controles alcançados o usa."""
    aceso = dict.fromkeys((*SENSORES, "touchpad", "mic"), False)
    for item in itens:
        uniq = str(item.get("uniq") or "")
        entrada = ctx.por_uniq(uniq)
        if not entrada:
            continue
        gira, anda = _se_move(uniq, entrada)
        esq, dir_ = _motores(ctx.state or {}, int(item.get("jogador") or 0))
        # O «Testar» da Vibração acende só o motor que ele faz tremer: o par sai
        # das barras daquele controle, e a barra de um motor em zero o cala.
        leve, forte = (a05._par_das_barras(ctx, uniq) if uniq in a05.em_teste()
                       else (0, 0))
        aceso["feat-giroscopio"] |= gira
        aceso["feat-acelerometro"] |= anda
        aceso["feat-rumble-esquerdo"] |= esq or forte > 0
        aceso["feat-rumble-direito"] |= dir_ or leve > 0
        aceso["feat-haptica"] |= (a05._haptica_no_ar(ctx.state or {}, uniq)
                                  or uniq in a05.em_teste_da_haptica())
        aceso["touchpad"] |= bool(dedos_do_inputs(entrada.get("inputs")))
        aceso["mic"] |= _som_no_mic(entrada)
    return aceso


def _trocas(p: dict[str, Any]) -> dict[str, str]:
    """`troca-<peça>`: o destino que a tela «Trocar os botões» mostra, ou vazio."""
    linhas = a06._linhas_da_troca(p)
    fora = {}
    for peca in TROCAM:
        destino = linhas.get(f"{a06.PREFIXO_DA_TROCA}{NOME_NA_TROCA.get(peca, peca)}", "")
        destino = "" if destino == a06.SEM_TROCA else destino
        fora[f"{TROCA}{peca}"] = destino
        fora[f"{TROCADA}{peca}"] = "sim" if destino else ""
    return fora


def _acoes(p: dict[str, Any]) -> dict[str, str]:
    """`acao-<peça>`: «Na Navegação: …», da tabela que vai ao device."""
    linhas = a06._linhas_dos_botoes(p)
    fora = {}
    for peca in NA_NAVEGACAO:
        partes = []
        for botao, qual in LINHAS_DA_PECA.get(peca, ((peca, ""),)):
            rotulo = linhas.get(f"{a06.PREFIXO_DA_ACAO}{botao}", "")
            if rotulo:
                partes.append(f"{rotulo} ({qual})" if qual else rotulo)
        fora[f"{ACAO}{peca}"] = ("Na Navegação: " + " · ".join(partes)) if partes else ""
    return fora


def _papel_e_luz(ctx: Contexto, ativo: str,
                 itens: list[dict[str, Any]]) -> tuple[str, str]:
    """A linha do cartão na Navegação e a cor da barra de luz do escolhido."""
    if not itens:
        return "", ""
    item = itens[0]
    dele = ctx.por_uniq(str(item.get("uniq") or ""))
    rotulo, base = rotulo_lightbar(dele, ctx.state or {})
    luz = a02._cor_da_barra(rotulo, base)
    if ativo == "todos" or not dele:
        return "", luz
    primario = bool(dele.get("is_primary"))
    linha = a06.linha_do_cartao(str(item.get("via") or ""), primario,
                                a06.move_o_cursor(dele, ctx, primario))
    return f" · Na Navegação: {linha}", luz


def _nome_do_chip(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """O nome do controle no chip, pela mesma regra do chip da fita (`monta.fita`)."""
    import monta

    nome = str(monta.identidade_do_chip(c, mesa))
    if nome in (monta._degrau_do_transporte(c), c.get("via"), monta.TRAVESSAO):
        return ""
    return nome


def chips_do_controle(mesa: list[dict[str, Any]], ativo: str, *,
                      vivo: bool = True) -> str:
    """Os chips do «Controle»: um por controle da mesa, «Todos» e «Nenhum»."""
    import monta

    mostra_todos, ativo = monta.escolha_da_fita(ativo, mesa)
    chips = []
    if mostra_todos:
        chips.append(f'<button class="bt{" on" if ativo == "todos" else ""}"'
                     f'{monta._endereco_do_chip("todos", False)}>Todos</button>')
    for c in mesa:
        pref = str(c.get("pref") or "")
        jogador = int(c.get("jogador") or 0)
        if vivo:
            rotulo = monta.rotulo_do_chip({**c, "nome": _nome_do_chip(c, mesa)})
            colorway = a06.colorway_do_aparelho(str(c.get("cor") or ""))
            luz = ""
        else:
            rotulo = monta.rotulo_do_chip(c)
            colorway = str(c.get("cor") or "")
            luz = "#{:02x}{:02x}{:02x}".format(*player_slot_color(jogador)) if jogador else ""
        attrs = (f' data-jogador="{jogador}"' if jogador else "") \
            + f' data-colorway="{html.escape(colorway)}"' \
            + (f' data-luz="{luz}"' if luz else "")
        chips.append(f'<button class="bt{" on" if ativo == pref else ""}"{attrs}'
                     f'{monta._endereco_do_chip(pref, False)}>{rotulo}</button>')
    chips.append('<button class="bt" data-jogador="0">Nenhum</button>')
    return "".join(chips)


@registrar(PAGINA)
def pacote(ctx: Contexto) -> dict[str, Any]:
    """O que o tique escreve no mapa: o pisca, a troca, a Navegação e os chips."""
    ativo, itens = _escolhidos(ctx)
    p = perfil.ativo((ctx.state or {}).get("active_profile"))
    papel, luz = _papel_e_luz(ctx, ativo, itens)
    mesa: dict[str, Any] = {
        **_acesos(ctx, itens),
        **_trocas(p),
        **_acoes(p),
        PAPEL: papel,
        LUZ: luz,
    }
    return {
        "mesa": mesa,
        "blocos": {BLOCO_DOS_CONTROLES: chips_do_controle(ctx.mesa, ativo)},
        "cobertura": {"pintados": len(mesa) + 1, "sem_dono": 0},
        "sem_dono": {},
    }
