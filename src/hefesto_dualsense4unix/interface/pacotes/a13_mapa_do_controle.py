#!/usr/bin/env python3
"""O mapa do controle é a tela de configurar os botões de um perfil.

`mapa-do-controle.html`, A-ABA-MAPA-DO-CONTROLE-DO-TODO-01 (15/10/2026). O desenho do
todo (rodadas 2 a 4): o perfil em cima, o DualSense no meio, os botões dos dois lados,
e um seletor por botão que diz no que ele vira (outro botão, mouse ou tecla).

O QUE A TELA É, e de quem é cada coisa:

* **o perfil** (`#perfil`): `nav` é o perfil que está valendo agora, o mesmo que a
  Navegação lê e grava (`Profile.button_actions`); `molde:<chave>` são os quatro
  moldes de `profiles.loader.MOLDES_DE_PERFIL` (o dono dos quatro nomes, iguais aqui e
  na Navegação); `perfil:<nome>` é um perfil do disco que já configura botão; `novo` é
  o perfil em branco. O molde e o novo só viram arquivo no «Guardar», e viram um perfil
  NOVO em «Meus perfis» (o molde é código, não arquivo).
* **o valor de cada botão**: uma de duas coisas, e escolher uma limpa a outra naquele
  botão. «Troca» é `Profile.remapeamento` (o que o jogo recebe, o motor é
  `core/remapeamento_de_botao`); «ação» é `Profile.button_actions` (o que o botão faz
  no computador, o motor é `core/acoes_de_botao`). Os botões que o motor recusa (as
  direções dos analógicos, o toque no touchpad, o PS) aparecem, mas não se trocam.
* **a edição** mora em `_EDITANDO` e só vai ao disco no «Guardar». Some sozinha se o
  tique parar por mais de `PAUSA_DE_OUTRA_ABA` (a mesma regra da Navegação).

O que a página lê do aparelho é o botão sob o dedo (`aceso-<peça>`, a leitura do pisca
da Controles), a barra de luz (`luz-cor`) e os chips: um por controle, na cor do
plástico. Os sensores, as luzes e o áudio saíram desta página (moram nas abas
Controles e Iluminação), e os chips «Todos» e «Nenhum» também.

Funções privadas de outras abas usadas aqui, declaradas: a troca de botões e o nome do
botão (`a06_navegacao`), o nome livre e a prioridade do perfil novo (`a10_perfis`). A
alternativa seria a segunda verdade de cada uma, que esta casa persegue.
"""
from __future__ import annotations

import html
import itertools
import sys
import threading
import time
from typing import Any, NamedTuple

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import ativacao_de_botao
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.integrations.uinput_mouse import EIXO_DIREITO, EIXO_ESQUERDO
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    ALL_BUTTONS,
    rotulo_lightbar,
)
from hefesto_dualsense4unix.profiles import estilos_de_jogo
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

from . import Contexto, fios, gesto, perfil, registrar
from . import a02_controles as a02
from . import a06_navegacao as a06
from . import em_fundo as fundo

PAGINA = "mapa-do-controle.html"

BLOCO_DOS_CONTROLES = '[data-bloco="controles-do-mapa"]'
BLOCO_DO_PERFIL = "#perfil"

ACESO = "aceso-"
LUZ = "luz-cor"

PAUSA_DE_OUTRA_ABA = 5.0

NAV, NOVO = "nav", "novo"
ACAO = "acao"  # (noqa-acento)
MOLDE, PERFIL = "molde:", "perfil:"

ROTULO_DO_TIPO = {"nav": "Navegação", "pac": "Point and click", "troca": "Trocar os botões"}

NOME_DA_NAVEGACAO = "Navegar no computador"

FORA_DO_JOGO = "Fora do jogo"


class Botao(NamedTuple):
    """Uma linha da tela: o botão que o usuário vê e o que o motor chama de botão."""

    b: str
    peca: str
    nome: str
    lado: str
    motor: str | None
    fixo: bool = False


BOTOES_DA_PAGINA: tuple[Botao, ...] = (
    Botao("l2", "l2", "L2", "esq", "l2"),
    Botao("l1", "l1", "L1", "esq", "l1"),
    Botao("dpad_up", "dpad_up", "Cima", "esq", "dpad_up"),
    Botao("dpad_left", "dpad_left", "Esquerda", "esq", "dpad_left"),
    Botao("dpad_down", "dpad_down", "Baixo", "esq", "dpad_down"),
    Botao("dpad_right", "dpad_right", "Direita", "esq", "dpad_right"),
    Botao("l3", "stick_l", "L3 clique", "esq", "l3"),
    Botao("l3_direcao", "stick_l", "L3 direção", "esq", EIXO_ESQUERDO),
    Botao("create", "share", "Share", "esq", "create"),
    Botao("r2", "r2", "R2", "dir", "r2"),
    Botao("r1", "r1", "R1", "dir", "r1"),
    Botao("triangle", "triangle", "Triângulo", "dir", "triangle"),
    Botao("circle", "circle", "Círculo", "dir", "circle"),
    Botao("cross", "cross", "Cruz", "dir", "cross"),
    Botao("square", "square", "Quadrado", "dir", "square"),
    Botao("r3", "stick_r", "R3 clique", "dir", "r3"),
    Botao("r3_direcao", "stick_r", "R3 direção", "dir", EIXO_DIREITO),
    Botao("options", "options", "Options", "dir", "options"),
    Botao("tp_toque", "touchpad", "Toque", "baixo", None, fixo=True),
    Botao("tp_esq", "touchpad", "Esquerda", "baixo", "touchpad_left_press"),
    Botao("tp_meio", "touchpad", "Meio", "baixo", "touchpad_middle_press"),
    Botao("tp_dir", "touchpad", "Direita", "baixo", "touchpad_right_press"),
    Botao("ps", "ps", "PS", "baixo", "ps", fixo=True),
)

POR_BOTAO: dict[str, Botao] = {x.b: x for x in BOTOES_DA_PAGINA}

TOQUE = "tp_toque"

PODE_TROCAR: frozenset[str] = frozenset(
    x.b for x in BOTOES_DA_PAGINA if x.motor in remap.REMAPEAVEIS)

OPCOES_DE_CONTROLE: tuple[tuple[str, str, str], ...] = (
    ("cross", "Cruz", "cross"), ("circle", "Círculo", "circle"),
    ("square", "Quadrado", "square"), ("triangle", "Triângulo", "triangle"),
    ("dpad_up", "Cima", "dpad_up"), ("dpad_down", "Baixo", "dpad_down"),
    ("dpad_left", "Esquerda", "dpad_left"), ("dpad_right", "Direita", "dpad_right"),
    ("l1", "L1", "l1"), ("r1", "R1", "r1"), ("l2", "L2", "l2"), ("r2", "R2", "r2"),
    ("l3", "L3", "stick_l"), ("r3", "R3", "stick_r"),
    ("options", "Options", "options"), ("create", "Share", "share"),
)

ROTULO_DO_DESTINO: dict[str, str] = {d: r for d, r, _ in OPCOES_DE_CONTROLE}

OPCOES_DE_MOUSE: tuple[tuple[str, str], ...] = (
    ("BTN_LEFT", "Botão esquerdo"), ("BTN_RIGHT", "Botão direito"),
    ("BTN_MIDDLE", "Botão do meio"), ("__CURSOR__", "Movimento do cursor"),
    ("__ROLAGEM__", "Rolagem"),
)

OPCOES_DE_TECLADO: tuple[tuple[str, str], ...] = (
    ("KEY_ENTER", "Enter"), ("KEY_ESC", "Esc"), ("KEY_SPACE", "Espaço"),
    ("KEY_BACKSPACE", "Backspace"), ("KEY_DELETE", "Delete"), ("KEY_TAB", "Tab"),
    ("KEY_LEFTCTRL", "Ctrl"), ("KEY_LEFTSHIFT", "Shift"),
    ("KEY_LEFTALT+KEY_TAB", "Alt + Tab"), ("KEY_LEFTMETA", "Super"),
    ("KEY_SYSRQ", "PrintScreen"), ("KEY_F11", "F11"),
)

ROTULO_DA_ACAO: dict[str, str] = dict(OPCOES_DE_MOUSE + OPCOES_DE_TECLADO)

SEQUENCIA = "sequencia"
ATIVACAO = "ativacao"  # (noqa-acento)

JEITOS_DA_SEQUENCIA: tuple[tuple[str, str], ...] = (
    ("uma_vez", "Toca uma vez"), ("repete", "Repete enquanto eu segurar"),
    ("alterna", "Liga e desliga"))

RITMOS_DA_SEQUENCIA: tuple[tuple[str, str], ...] = (
    ("gravado", "O gravado"), ("rapido", "Mais rápido"), ("devagar", "Mais devagar"))

FICHAS_DO_MOUSE: frozenset[str] = frozenset(t for t, _ in OPCOES_DE_MOUSE)

NOME_NO_LEITOR = {"stick_l": "l3", "stick_r": "r3"}
PISCAM: tuple[str, ...] = (*ALL_BUTTONS, *NOME_NO_LEITOR)

DESTINO_DA_PECA = {"stick_l": "l3", "stick_r": "r3", "share": "create"}

_EDITANDO: dict[str, Any] = {}
_VISTO: list[float] = [0.0]


def _estado() -> dict[str, Any]:
    """A edição em curso, ou a de partida; some se o tique parou."""
    agora = time.monotonic()
    if _EDITANDO and _VISTO[0] and agora - _VISTO[0] > PAUSA_DE_OUTRA_ABA:
        _EDITANDO.clear()
    if not _EDITANDO:
        _EDITANDO.update({"chave": NAV, "edicoes": {}, "nome": None,
                          "usar_em": None, "botao": None, "peca": None,
                          "seq": {}, "gravando": None})
    return _EDITANDO


def _largar() -> None:
    _EDITANDO.clear()


def _estilo_de_clicar(cru: dict[str, Any]) -> bool:
    """O perfil é de um estilo de jogo de clicar: a receita do catálogo liga o modo `desktop`.

    Uma leitura só, a do catálogo (`profiles/estilos_de_jogo`): o Point and click e o Visual novel
    entram, e um estilo novo de clicar também, sem lista de chaves aqui.
    """
    estilo = estilos_de_jogo.POR_CHAVE.get(str(cru.get("estilo") or ""))
    receita = estilo.receita_invisivel if estilo else None
    return bool(receita and receita.modo == "desktop")


def _perfis_do_disco(ctx: Contexto) -> list[dict[str, Any]]:
    """Os perfis do disco que configuram botão: «Meus perfis»."""
    meus = []
    for linha in perfil.lista():
        nome = str(linha.get("nome") or "")
        cru = perfil.ativo(nome)
        if not cru:
            continue
        if (cru.get("remapeamento") or cru.get("button_actions")
                or _sequencias_do_cru(cru, None) or _estilo_de_clicar(cru)
                or (cru.get("mouse") or {}).get("enabled")):
            meus.append(cru)
    return meus


def _nome_do_ativo(ctx: Contexto) -> str:
    return perfil.nome_do_ativo(ctx.state).strip()


def _peca_do_vale_para(ctx: Contexto) -> str | None:
    """O controle (MAC de 12 hex) que o «Vale para» escolheu, ou `None` quando o perfil é o dono.

    Com um controle só ninguém escolhe: a troca é do perfil. Com dois ou mais, o chip aceso é o
    dono. O molde e o perfil novo ainda não têm controle: o chamador só pergunta nos outros.
    """
    chave = str(_estado()["chave"])
    if len(ctx.mesa or ()) < 2 or not (chave == NAV or chave.startswith(PERFIL)):
        return None
    _, itens = _escolhidos(ctx)
    if len(itens) != 1:
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    mac = norm_mac(str(itens[0].get("uniq") or ""))
    return mac if mac and len(mac) == 12 else None


def _troca_da_peca(cru: dict[str, Any], mac: str | None) -> dict[str, str]:
    """A troca própria do controle `mac` no perfil cru, ou `{}`."""
    if not mac:
        return {}
    cfg = (cru.get("controllers") or {}).get(mac) or {}
    return dict(cfg.get("remapeamento") or {})


def _sequencias_do_cru(cru: dict[str, Any], mac: str | None) -> dict[str, Any]:
    """As sequências do perfil cru, ou as do controle `mac` quando ele tem as dele."""
    if mac:
        dela = ((cru.get("controllers") or {}).get(mac) or {}).get(ATIVACAO) or {}
        if "sequencia" in dela:
            return dict(dela["sequencia"] or {})
    return dict((cru.get(ATIVACAO) or {}).get("sequencia") or {})


def _cru_da_chave(ctx: Contexto, chave: str) -> dict[str, Any]:
    """O perfil cru que a chave nomeia: o ativo, ou o do disco. `{}` para molde e novo."""
    if chave == NAV:
        return perfil.ativo(_nome_do_ativo(ctx))
    if chave.startswith(PERFIL):
        return perfil.ativo(chave.removeprefix(PERFIL))
    return {}


def _molde_da_chave(chave: str) -> Any:
    loader = perfil._com_o_src()
    return loader.MOLDE_POR_CHAVE.get(chave.removeprefix(MOLDE))


def _base(ctx: Contexto, chave: str) -> dict[str, tuple[str, str]]:
    """O que a tela mostra ANTES de qualquer edição: `{botão: (ficha, valor)}`."""
    base: dict[str, tuple[str, str]] = {}
    if chave.startswith(MOLDE):
        molde = _molde_da_chave(chave)
        for motor, token in (molde.button_actions if molde else {}).items():
            base[motor] = (ACAO, token)
        return _por_botao(base)
    cru = _cru_da_chave(ctx, chave)
    if chave == NAV:
        tabela = acoes.tabela_efetiva(cru.get("button_actions") or None,
                                      cru.get("key_bindings") or None)
    else:
        tabela = dict(cru.get("button_actions") or {})
    por_motor = {m: (ACAO, str(t)) for m, t in tabela.items() if t}
    mac = _peca_do_vale_para(ctx)
    juntas = remap.juntar(cru.get("remapeamento") or {}, _troca_da_peca(cru, mac))
    for motor, destino in juntas.items():
        por_motor[motor] = ("troca", str(destino))
    for motor, seq in _sequencias_do_cru(cru, mac).items():
        por_motor[motor] = (SEQUENCIA, ativacao_de_botao.sequencia_em_texto(seq))
    return _por_botao(por_motor)


def _por_botao(por_motor: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """O mesmo dicionário, com a chave que a tela usa (a linha) em vez da do motor."""
    return {x.b: por_motor[x.motor] for x in BOTOES_DA_PAGINA
            if x.motor in por_motor}


def _padrao_da_chave(ctx: Contexto, chave: str) -> dict[str, tuple[str, str]]:
    """O que «Sem mudança» devolve a cada botão: o de fábrica da Navegação, ou nada."""
    if chave != NAV:
        return {}
    cru = _cru_da_chave(ctx, chave)
    tabela = acoes.tabela_efetiva(None, cru.get("key_bindings") or None)
    return _por_botao({m: (ACAO, str(t)) for m, t in tabela.items() if t})


def _valores(ctx: Contexto, estado: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Base + edições: o que a tela mostra agora. Linha ausente = sem valor."""
    chave = estado["chave"]
    valores = dict(_base(ctx, chave))
    padrao = _padrao_da_chave(ctx, chave)
    for b, (tipo, valor) in estado["edicoes"].items():
        if tipo == "sem":
            valores.pop(b, None)
            if b in padrao:
                valores[b] = padrao[b]
        else:
            valores[b] = (tipo, valor)
    return valores


def _texto_do_valor(par: tuple[str, str] | None, b: str) -> str:
    """O que a linha escreve: «—» sem valor, o destino da troca, ou a ação em palavras."""
    if b == TOQUE:
        return ROTULO_DA_ACAO[acoes.TOKEN_CURSOR]
    if par is None:
        return "—"
    tipo, valor = par
    if tipo == SEQUENCIA:
        return "Sequência"
    if tipo == "troca":
        return ROTULO_DO_DESTINO.get(valor, a06._rotulo_do_destino(valor))
    if b == "ps" and valor == acoes.TOKEN_SEM_TECLA:
        return "—"
    if valor in ROTULO_DA_ACAO:
        return ROTULO_DA_ACAO[valor]
    texto = acoes.rotulo(valor)
    return a06._atalho_em_palavras(valor) if texto == valor else texto


def _tipo_de(ctx: Contexto, estado: dict[str, Any], valores: dict[str, tuple[str, str]]) -> str:
    """`nav`, `pac` ou `troca`: a cor do perfil que a tela mostra."""
    chave = estado["chave"]
    if chave == NAV:
        return "nav"
    if chave.startswith(MOLDE):
        return "pac"
    tipos = {t for t, _ in valores.values()}
    fichas = {v for t, v in valores.values() if t == ACAO}
    if fichas & FICHAS_DO_MOUSE or _estilo_de_clicar(_cru_da_chave(ctx, chave)):
        return "pac"
    return "troca" if tipos & {"troca", SEQUENCIA} else "nav"


def _escolhidos(ctx: Contexto) -> tuple[str, list[dict[str, Any]]]:
    """Quem a fita escolheu, e os itens da mesa que isso alcança."""
    import monta

    escolhido = ctx.escolhido or (str(ctx.mesa[0].get("pref") or "") if ctx.mesa else "")
    _, ativo = monta.escolha_da_fita(escolhido or "todos", ctx.mesa)
    if ativo == "todos":
        return ativo, list(ctx.mesa)
    return ativo, [m for m in ctx.mesa if str(m.get("pref") or "") == ativo]


def _acesos(ctx: Contexto, itens: list[dict[str, Any]]) -> set[str]:
    """As peças cujo botão físico está sob o dedo, em qualquer dos controles alcançados."""
    acesas: set[str] = set()
    for item in itens:
        entrada = ctx.por_uniq(str(item.get("uniq") or ""))
        glifos = a02.leitura_viva(entrada)
        lido = entrada.get("inputs")
        apertados = {str(b) for b in ((lido or {}).get("buttons") or ())} \
            if isinstance(lido, dict) else set()
        for peca in PISCAM:
            if peca in NOME_NO_LEITOR:
                if NOME_NO_LEITOR[peca] in apertados:
                    acesas.add(peca)
            elif glifos.get(f"glifo-{peca}") == "sim":
                acesas.add(peca)
    return acesas


def _estado_da_linha(x: Botao, valores: dict[str, tuple[str, str]], botao: str | None,
                     acesas: set[str]) -> str:
    """As palavras que a CSS lê na linha: `muda`, `on` (a escolhida) e `pisca`."""
    palavras = []
    if x.b in valores:
        palavras.append("muda")
    if x.b == botao:
        palavras.append("on")
    if x.b in PODE_TROCAR and x.peca in acesas:
        palavras.append("pisca")
    return " ".join(palavras)


def _usar_em(ctx: Contexto, estado: dict[str, Any]) -> str:
    """Os chips de «Usar em»: onde o perfil vale, e o «+ Jogo» quando se pode mudar."""
    chave = estado["chave"]
    if chave == NAV:
        pelo_ativo = _nome_do_ativo(ctx)
        from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

        quem = FORA_DO_JOGO if (not pelo_ativo or opc.e_o_freestyle(pelo_ativo)) else pelo_ativo
        return f'<span class="jogo">{html.escape(quem)}</span>'
    texto = estado.get("usar_em")
    if texto is None and chave.startswith(PERFIL):
        loader = perfil._com_o_src()
        try:
            from hefesto_dualsense4unix.profiles.schema import Profile

            prof = Profile.model_validate(_cru_da_chave(ctx, chave))
            from hefesto_dualsense4unix.profiles.simple_match import simple_extra

            texto = simple_extra(prof.match)
        except Exception:
            texto = ""
        del loader
    chips = [f'<span class="jogo">{html.escape(texto)}</span>'] if texto else []
    chips.append('<button class="jogo mais" data-gesto="mapa-usar-em" '
                 'data-dica="Usa o jogo que está em foco agora">+ Jogo</button>')
    return "".join(chips)


def _opcoes_do_perfil(ctx: Contexto) -> str:
    """O conteúdo de `#perfil`: Navegação, Moldes, Meus perfis e o «+ Novo perfil…»."""
    loader = perfil._com_o_src()
    moldes = "".join(
        f'<option value="{MOLDE}{m.chave}">{html.escape(m.nome)}</option>'
        for m in loader.MOLDES_DE_PERFIL)
    meus = "".join(
        f'<option value="{PERFIL}{html.escape(str(c.get("name") or ""), quote=True)}">'
        f'{html.escape(str(c.get("name") or ""))}</option>'
        for c in _perfis_do_disco(ctx))
    nav = f'<option value="{NAV}">{NOME_DA_NAVEGACAO}</option>'
    return (f'<optgroup label="Navegação">{nav}</optgroup>'
            f'<optgroup label="Moldes">{moldes}</optgroup>'
            + (f'<optgroup label="Meus perfis">{meus}</optgroup>' if meus else "")
            + f'<option value="{NOVO}">+ Novo perfil…</option>')


def _nome_mostrado(ctx: Contexto, estado: dict[str, Any]) -> str:
    chave = estado["chave"]
    if estado.get("nome") is not None:
        return str(estado["nome"])
    if chave == NAV:
        return NOME_DA_NAVEGACAO
    if chave == NOVO:
        return "Novo perfil"
    if chave.startswith(MOLDE):
        molde = _molde_da_chave(chave)
        return str(molde.nome) if molde else ""
    return str(chave.removeprefix(PERFIL))


def _cursor(valores: dict[str, tuple[str, str]]) -> str:
    """Com qual analógico se move o cursor: `esq` ou `dir`."""
    if valores.get("r3_direcao") == (ACAO, "__CURSOR__"):
        return "dir"
    return "esq"


def _chave_do_point_and_click(ctx: Contexto) -> str:
    """O perfil que a aba Navegação escolheu para o point and click, na chave do seletor.

    A escolha é lida pela MESMA função da aba Navegação (`a06._o_point_and_click_de_hoje`): sem
    segunda leitura do campo. Escolha que não existe mais (perfil apagado) abre em Navegar.
    """
    escolha = a06._o_point_and_click_de_hoje()
    return escolha if _chave_valida(ctx, escolha) else NAV


def _chave_das_trocas(ctx: Contexto) -> str:
    """O perfil ativo, se tem lugar no seletor (troca ou ação própria de botão); senão Navegar."""
    nome = _nome_do_ativo(ctx)
    meus = {str(c.get("name") or "") for c in _perfis_do_disco(ctx)}
    return PERFIL + nome if nome and nome in meus else NAV


def _mesa_da_edicao(ctx: Contexto) -> dict[str, Any]:
    """Tudo o que a tela mostra do perfil em edição, num só dicionário."""
    estado = _estado()
    valores = _valores(ctx, estado)
    tipo = _tipo_de(ctx, estado, valores)
    chave = estado["chave"]
    mesa: dict[str, Any] = {
        "mc-tipo": tipo,
        "mc-fixo": "" if chave in (NOVO,) or chave.startswith(MOLDE) else "sim",
        "etiqueta": ROTULO_DO_TIPO[tipo],
        "perfil": chave,
        "nome": _nome_mostrado(ctx, estado),
        "usar-em": _usar_em(ctx, estado),
        "cursor-mover": _cursor(valores),
        "ancora-pac": _chave_do_point_and_click(ctx),
        "ancora-trocar": _chave_das_trocas(ctx),
    }
    return mesa


def _linhas(ctx: Contexto, acesas: set[str]) -> dict[str, Any]:
    estado = _estado()
    valores = _valores(ctx, estado)
    mesa: dict[str, Any] = {}
    for x in BOTOES_DA_PAGINA:
        par = valores.get(x.b)
        if x.b == "ps":
            par = _o_ps(ctx, estado, par)
        mesa[f"val-{x.b}"] = _texto_do_valor(par, x.b)
        mesa[f"estado-{x.b}"] = _estado_da_linha(x, valores, estado["botao"], acesas)
        mesa[f"atual-{x.b}"] = f"{par[0]}:{par[1]}" if par and not x.fixo else ""
    return mesa


def _o_ps(ctx: Contexto, estado: dict[str, Any],
          par: tuple[str, str] | None) -> tuple[str, str] | None:
    """O PS só mostra o toque dele, e nunca se troca aqui: abre os gestos da Navegação."""
    if par is None or par[1] == acoes.TOKEN_SEM_TECLA:
        return None
    return par


def _luz(ctx: Contexto, ativo: str, itens: list[dict[str, Any]]) -> str:
    """A cor da barra de luz do controle escolhido, a do cartão da Controles."""
    if not itens:
        return ""
    dele = ctx.por_uniq(str(itens[0].get("uniq") or ""))
    rotulo, base = rotulo_lightbar(dele, ctx.state or {})
    return str(a02._cor_da_barra(rotulo, base))


def chips_do_controle(mesa: list[dict[str, Any]], ativo: str, *, vivo: bool = True) -> str:
    """Os quatro controles pela cor do plástico: um chip cada, sem «Todos» nem «Nenhum»."""
    import monta

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    _, ativo = monta.escolha_da_fita(ativo, mesa)
    chips = []
    for c in mesa:
        pref = str(c.get("pref") or "")
        jogador = int(c.get("jogador") or 0)
        cru = str(c.get("cor") or "")
        slug = a06.colorway_do_aparelho(cru) if vivo else cru
        luz = ("#{:02x}{:02x}{:02x}".format(*player_slot_color(jogador))
               if (jogador and not vivo) else "")
        conhece = bool(slug) and monta.o_desenho_conhece(slug)
        cor = f' style="--plastico:{monta.cor_da_zona(slug)}"' if conhece else ""
        attrs = (f' data-jogador="{jogador}"' if jogador else "") \
            + f' data-colorway="{html.escape(slug)}"' + (f' data-luz="{luz}"' if luz else "")
        nome = html.escape(str(c.get("nome") or ""))
        via = html.escape(str(c.get("via") or ""))
        texto = f'{nome} <span class="pt">•</span> {via}' if via else nome
        chips.append(f'<button class="chip plastico{" on" if ativo == pref else ""}"{cor}{attrs}'
                     f'{monta._endereco_do_chip(pref, False)}>{texto}</button>')
    return "".join(chips)


@registrar(PAGINA)
def pacote(ctx: Contexto) -> dict[str, Any]:
    """O que o tique escreve na tela: a edição, o botão sob o dedo, a luz e os chips."""
    _VISTO[0] = time.monotonic()
    ativo, itens = _escolhidos(ctx)
    _largar_se_outro_controle(ctx, no_tique=True)
    acesas = _acesos(ctx, itens)
    _acompanha_a_gravacao()
    mesa: dict[str, Any] = {**_mesa_da_edicao(ctx), **_linhas(ctx, acesas),
                            **_campos_da_sequencia(ctx), LUZ: _luz(ctx, ativo, itens)}
    return {
        "mesa": mesa,
        "blocos": {BLOCO_DOS_CONTROLES: chips_do_controle(ctx.mesa, ativo),
                   BLOCO_DO_PERFIL: _opcoes_do_perfil(ctx)},
        "cobertura": {"pintados": len(mesa) + 2, "sem_dono": 0},
        "sem_dono": {},
    }


def _largar_se_outro_controle(ctx: Contexto, *, no_tique: bool = False) -> None:
    """O «Vale para» mudou de controle: o que não se guardou era do anterior e fica para trás.

    No tique a parada vai a um fio: o tique não espera o serviço.
    """
    estado = _estado()
    peca = _peca_do_vale_para(ctx)
    if estado.get("peca") != peca:
        if no_tique:
            _soltar_em_fundo(estado)
        else:
            _parar_de_ouvir(estado)
        estado["peca"] = peca
        estado["edicoes"] = {}
        estado["seq"] = {}


def _repinta(ctx: Contexto) -> dict[str, Any]:
    """A resposta de um gesto: a tela inteira de agora, sem esperar o próximo tique."""
    _VISTO[0] = time.monotonic()
    _largar_se_outro_controle(ctx)
    _, itens = _escolhidos(ctx)
    return {"mesa": {**_mesa_da_edicao(ctx), **_linhas(ctx, _acesos(ctx, itens)),
                     **_campos_da_sequencia(ctx)}}


def _chave_valida(ctx: Contexto, chave: str) -> bool:
    if chave in (NAV, NOVO):
        return True
    if chave.startswith(MOLDE):
        return _molde_da_chave(chave) is not None
    return chave.startswith(PERFIL) and bool(_cru_da_chave(ctx, chave))


@gesto(PAGINA, "mapa-perfil")
def mapa_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O usuário escolheu outro perfil na lista. Larga o que não guardou do anterior."""
    chave = str(o.get("valor") or "").strip()
    if not _chave_valida(ctx, chave):
        raise RuntimeError(f"não conheço o perfil «{chave}» — escolha um da lista.")
    _largar()
    _estado()["chave"] = chave
    return _repinta(ctx)


@gesto(PAGINA, "mapa-nome")
def mapa_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O nome do perfil novo. Perfil que já existe se renomeia na aba Perfis."""
    estado = _estado()
    chave = estado["chave"]
    if chave == NAV or chave.startswith(PERFIL):
        raise RuntimeError("o nome deste perfil se muda na aba Perfis.")
    estado["nome"] = str(o.get("valor") or "").strip()
    return _repinta(ctx)


@gesto(PAGINA, "mapa-usar-em")
def mapa_usar_em(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«+ Jogo»: o perfil passa a valer no jogo que está em foco agora."""
    estado = _estado()
    if estado["chave"] == NAV:
        raise RuntimeError(
            "a Navegação vale fora do jogo; para um jogo, escolha ou crie outro perfil.")
    classe = a10._classe_de_outro_app(ctx)
    if not classe:
        raise RuntimeError(
            "não achei janela de jogo em foco. Abra o jogo, deixe-o em foco por um instante "
            "e clique de novo.")
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    appid = steam_appid_from_wm_class(classe)
    estado["usar_em"] = str(appid) if appid is not None else classe
    estado["usar_em_forma"] = "steam_game" if appid is not None else "janela"
    return _repinta(ctx)


@gesto(PAGINA, "mapa-botao")
def mapa_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O usuário clicou numa linha: ela vira a escolhida.

    Sem `b`, o seletor fechou e nada fica aceso.
    """
    b = str(o.get("b") or "").strip()
    if not b:
        _parar_de_ouvir(_estado())
        _estado()["botao"] = None
        return _repinta(ctx)
    if b not in POR_BOTAO:
        raise ValueError(f"mapa-botao: o clique não disse qual botão (veio {b!r}).")
    _estado()["botao"] = b
    return _repinta(ctx)


def _tentativa_de_troca(ctx: Contexto, estado: dict[str, Any], b: str, destino: str) -> None:
    """Recusa, com a frase da Navegação, a troca que o motor não aceita."""
    valores = _valores(ctx, estado)
    declarado = {POR_BOTAO[x].motor or x: v for x, (t, v) in valores.items()
                 if t == "troca" and x != b}
    declarado[POR_BOTAO[b].motor or b] = destino
    try:
        remap.resolver({k: v for k, v in declarado.items() if k in remap.REMAPEAVEIS})
    except remap.RemapeamentoRecusadoError as exc:
        raise RuntimeError(a06._frase_da_troca(exc)) from None


def _grava_na_edicao(ctx: Contexto, tipo: str, valor: str) -> None:
    _largar_se_outro_controle(ctx)
    estado = _estado()
    b = estado["botao"]
    if b is None:
        raise RuntimeError("escolha antes, na lista, o botão que vai mudar.")
    linha = POR_BOTAO[b]
    if linha.fixo:
        raise RuntimeError(
            "o PS não se troca: os gestos dele ficam na aba Navegação." if b == "ps"
            else "o toque no touchpad não se troca aqui.")
    if tipo == "troca":
        if b not in PODE_TROCAR:
            raise RuntimeError(
                f"{linha.nome} não se troca por outro botão — a direção dos analógicos "
                "e o toque no touchpad ficam fora da troca.")
        _tentativa_de_troca(ctx, estado, b, valor)
    elif tipo == ACAO:
        if valor not in acoes.ACOES and not _e_combinacao(valor):
            raise ValueError(f"mapa-escolher: a ação {valor!r} não existe no motor.")
    elif tipo != "sem":
        raise ValueError(f"mapa-escolher: tipo {tipo!r} desconhecido.")
    estado["edicoes"][b] = (tipo, valor)
    estado["seq"].pop(b, None)


def _e_combinacao(valor: str) -> bool:
    from hefesto_dualsense4unix.profiles.schema import _e_combinacao_de_teclas

    return bool(_e_combinacao_de_teclas(valor))


@gesto(PAGINA, "mapa-escolher")
def mapa_escolher(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O usuário escolheu no que o botão vira: ficha `ACAO` e token, `troca:<destino>` ou `sem`."""
    bruto = str(o.get("v") or "").strip()
    tipo, _, valor = bruto.partition(":")
    _grava_na_edicao(ctx, tipo, valor)
    return _repinta(ctx)


@gesto(PAGINA, "mapa-gravar-tecla")
def mapa_gravar_tecla(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A captura: a tecla (`tecla`) ou o botão do controle (`troca`) que o usuário apertou."""
    destino = str(o.get("troca") or "").strip()
    if destino:
        _grava_na_edicao(ctx, "troca", destino)
        return _repinta(ctx)
    tecla = str(o.get("tecla") or "").strip()
    if not tecla:
        raise RuntimeError("não ouvi tecla nenhuma. Clique em «Gravar tecla» e aperte uma.")
    if tecla.startswith("BTN_"):
        if tecla not in FICHAS_DO_MOUSE:
            raise RuntimeError("esse botão do mouse não tem como virar um botão do controle.")
        _grava_na_edicao(ctx, ACAO, tecla)
        return _repinta(ctx)
    if not _e_combinacao(tecla):
        raise RuntimeError(
            f"A tecla {tecla.removeprefix('KEY_').title()} não está entre as do teclado virtual: "
            "escolha outra.")
    _grava_na_edicao(ctx, ACAO, tecla)
    return _repinta(ctx)


@gesto(PAGINA, "mapa-mover-com")
def mapa_mover_com(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Qual analógico move o cursor: o outro passa a rolar."""
    lado = str(o.get("valor") or "").strip()
    if lado not in ("esq", "dir"):
        raise ValueError(f"mapa-mover-com: lado {lado!r} desconhecido.")
    cursor, rolagem = (("l3_direcao", "r3_direcao") if lado == "esq"
                       else ("r3_direcao", "l3_direcao"))
    _largar_se_outro_controle(ctx)
    edicoes = _estado()["edicoes"]
    edicoes[cursor] = (ACAO, "__CURSOR__")
    edicoes[rolagem] = (ACAO, "__ROLAGEM__")
    return _repinta(ctx)


@gesto(PAGINA, "mapa-padrao")
def mapa_padrao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Voltar ao padrão»: cada botão volta ao de fábrica (o molde, ao que o molde traz).
    Só vale no «Guardar»."""
    _largar_se_outro_controle(ctx)
    estado = _estado()
    _parar_de_ouvir(estado)
    estado["seq"] = {}
    if str(estado["chave"]).startswith(MOLDE):
        estado["edicoes"] = {}
        return _repinta(ctx)
    base = _base(ctx, estado["chave"])
    estado["edicoes"] = {b: ("sem", "") for b in base}
    return _repinta(ctx)


@gesto(PAGINA, "mapa-cancelar")
def mapa_cancelar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Cancelar»: larga o que não foi guardado. A volta à Navegação é do link."""
    _largar()


def passos_em_html(passos: Any) -> str:
    """Os botões da sequência e o intervalo entre eles, como a faixa do desenho os mostra."""
    lista = list(passos)
    partes = []
    for i, (botao, ms) in enumerate(lista):
        nome = html.escape(ROTULO_DO_DESTINO.get(botao, botao))
        partes.append(f'<span class="seq-p">{nome}</span>')
        if i + 1 < len(lista):
            partes.append(f'<span class="seq-t">{int(ms)} ms</span>')
    return "".join(partes)


def _rascunho(ctx: Contexto, estado: dict[str, Any], b: str) -> dict[str, Any]:
    """A sequência do botão `b` em edição: a já escolhida na tela, ou uma sem passo ainda."""
    seq: dict[str, Any] | None = estado["seq"].get(b)
    if seq is None:
        par = _valores(ctx, estado).get(b)
        seq = (ativacao_de_botao.sequencia_do_texto(par[1])
               if par and par[0] == SEQUENCIA
               else {"passos": [], "jeito": "uma_vez", "ritmo": "gravado"})
        estado["seq"][b] = seq
    return seq


def _guarda_o_rascunho(estado: dict[str, Any], b: str) -> None:
    """Sequência com ao menos um botão vira a edição da linha; sem botão, a linha segue igual."""
    seq = estado["seq"][b]
    if seq["passos"]:
        estado["edicoes"][b] = (SEQUENCIA, ativacao_de_botao.sequencia_em_texto(seq))
    elif estado["edicoes"].get(b, ("", ""))[0] == SEQUENCIA:
        del estado["edicoes"][b]


ESCUTA_EM_FUNDO = "a13-sequencia-gravar"
_VEZES = itertools.count(1)
_UMA_ESCUTA_POR_VEZ = threading.Lock()


def _ouvido_agora(vez: int) -> tuple[int, Any]:
    """BLOQUEIA: pergunta ao serviço. Só do fio do ``em_fundo``, nunca do tique."""
    from . import ponte

    return vez, ponte.resultado("sequencia.gravar", acao="estado")


def _acompanha_a_gravacao() -> None:
    """Enquanto o daemon ouve, o que ele ouviu entra na faixa; se parou sozinho, fecha.

    O tique lê a última resposta que chegou e pede a próxima num fio. Sem resposta desta
    gravação (o serviço lento ou fora), a faixa fica como estava e o «Parar de gravar» fecha.
    """
    estado = _estado()
    b = estado.get("gravando")
    if b is None:
        return
    vez = int(estado.get("vez") or 0)
    lida = fundo.em_fundo(ESCUTA_EM_FUNDO, lambda: _ouvido_agora(vez), 0.0)
    if not (isinstance(lida, tuple) and lida[0] == vez and isinstance(lida[1], dict)):
        return
    if estado.get("gravando") != b or int(estado.get("vez") or 0) != vez:
        return
    r = lida[1]
    estado["seq"].setdefault(b, {"passos": [], "jeito": "uma_vez", "ritmo": "gravado"})
    estado["seq"][b]["passos"] = list(r.get("passos") or [])
    if not r.get("gravando"):
        _parar_de_ouvir(estado, ja_parou=True)


def _soltar_em_fundo(estado: dict[str, Any]) -> None:
    """Larga a gravação sem esperar: o daemon para num fio, e o que ele ouviu fica para trás."""
    if estado.get("gravando") is None:
        return
    estado["gravando"] = None

    def parar() -> None:
        from . import ponte

        with _UMA_ESCUTA_POR_VEZ:
            try:
                ponte.resultado("sequencia.gravar", acao="parar")
            except Exception as erro:
                print(f"[sequência] a parada não chegou ao serviço: {erro}", file=sys.stderr)

    fios.soltar("a13-parar-de-ouvir", parar)


def _parar_de_ouvir(estado: dict[str, Any], *, ja_parou: bool = False) -> None:
    """Para a gravação, se há uma, e guarda o que o daemon ouviu.

    BLOQUEIA quando pergunta: só de gesto. Com ``ja_parou`` (o daemon parou sozinho e o tique
    já trouxe os passos) não pergunta nada.
    """
    b = estado.get("gravando")
    if b is None:
        return
    estado["gravando"] = None
    r: Any = None
    if not ja_parou:
        from . import ponte

        try:
            r = ponte.resultado("sequencia.gravar", acao="parar")
        except Exception:
            r = None
    seq = estado["seq"].setdefault(b, {"passos": [], "jeito": "uma_vez", "ritmo": "gravado"})
    if isinstance(r, dict):
        seq["passos"] = list(r.get("passos") or [])
    _guarda_o_rascunho(estado, b)


def _campos_da_sequencia(ctx: Contexto) -> dict[str, Any]:
    """O que a aba Sequência escreve: os passos do botão escolhido, o jeito, o ritmo e o gravar."""
    estado = _estado()
    b = estado["botao"]
    seq = None
    if b in PODE_TROCAR:
        par = _valores(ctx, estado).get(b)
        seq = estado["seq"].get(b) or (
            ativacao_de_botao.sequencia_do_texto(par[1]) if par and par[0] == SEQUENCIA else None)
    gravando = estado.get("gravando") is not None
    return {
        "seq-passos": passos_em_html(
            (p["botao"], p["ms"]) for p in (seq["passos"] if seq else ())),
        "seq-jeito": seq["jeito"] if seq else JEITOS_DA_SEQUENCIA[0][0],
        "seq-ritmo": seq["ritmo"] if seq else RITMOS_DA_SEQUENCIA[0][0],
        "seq-gravando": "sim" if gravando else "",
        "seq-rotulo": "Parar de gravar" if gravando else "Gravar a sequência",
    }


def _botao_da_sequencia(ctx: Contexto, gesto_: str) -> tuple[dict[str, Any], str]:
    _largar_se_outro_controle(ctx)
    estado = _estado()
    b = estado["botao"]
    if b is None:
        raise RuntimeError("escolha antes, na lista, o botão que vai tocar a sequência.")
    if b not in PODE_TROCAR:
        raise RuntimeError(
            f"{POR_BOTAO[b].nome} não toca sequência: ele não se troca por outro botão.")
    return estado, str(b)


def _quem_ouve(ctx: Contexto) -> dict[str, str]:
    mac = _peca_do_vale_para(ctx)
    return {"uniq": mac} if mac else {}


@gesto(PAGINA, "mapa-sequencia-gravar")
def mapa_sequencia_gravar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Gravar a sequência»: o controle passa a ouvir; de novo, para e guarda o que ouviu."""
    estado = _estado()
    if estado.get("gravando") is not None:
        _parar_de_ouvir(estado)
        return _repinta(ctx)
    estado, b = _botao_da_sequencia(ctx, "mapa-sequencia-gravar")
    with _UMA_ESCUTA_POR_VEZ:
        r = p.resultado("sequencia.gravar", acao="iniciar", **_quem_ouve(ctx))
    if not isinstance(r, dict) or r.get("status") != "ok":
        raise RuntimeError("o Hefesto não confirmou a gravação: o serviço precisa estar ligado.")
    _rascunho(ctx, estado, b)["passos"] = []
    estado["vez"] = next(_VEZES)
    estado["gravando"] = b
    _guarda_o_rascunho(estado, b)
    return _repinta(ctx)


def _muda_da_sequencia(ctx: Contexto, o: dict[str, Any], campo: str,
                       validos: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    estado, b = _botao_da_sequencia(ctx, campo)
    valor = str(o.get("valor") or o.get("v") or "").strip()
    if valor not in {v for v, _ in validos}:
        raise ValueError(f"mapa-sequencia: {valor!r} não é um {campo} que o motor conhece.")
    _rascunho(ctx, estado, b)[campo] = valor
    _guarda_o_rascunho(estado, b)
    return _repinta(ctx)


@gesto(PAGINA, "mapa-sequencia-jeito")
def mapa_sequencia_jeito(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Ao apertar»: toca uma vez, repete enquanto segura, ou liga e desliga."""
    return _muda_da_sequencia(ctx, o, "jeito", JEITOS_DA_SEQUENCIA)


@gesto(PAGINA, "mapa-sequencia-ritmo")
def mapa_sequencia_ritmo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Ritmo»: o gravado, mais rápido ou mais devagar."""
    return _muda_da_sequencia(ctx, o, "ritmo", RITMOS_DA_SEQUENCIA)


@gesto(PAGINA, "mapa-sequencia-tocar")
def mapa_sequencia_tocar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Tocar para ouvir»: o controle toca a sequência de agora uma vez, sem guardar nada."""
    estado, b = _botao_da_sequencia(ctx, "mapa-sequencia-tocar")
    _parar_de_ouvir(estado)
    seq = _rascunho(ctx, estado, b)
    if not seq["passos"]:
        raise RuntimeError("grave antes a sequência: nenhum botão foi apertado.")
    r = p.resultado("sequencia.tocar", passos=seq["passos"], ritmo=seq["ritmo"],
                    **_quem_ouve(ctx))
    if not isinstance(r, dict) or r.get("status") != "ok":
        raise RuntimeError("a sequência não tocou: o serviço precisa estar ligado.")
    return _repinta(ctx)


def _aplicar_as_edicoes(prof: Any, edicoes: dict[str, tuple[str, str]],
                        padrao_de_base: dict[str, str], mac: str | None = None) -> Any:
    """O perfil com as edições: troca limpa a ação do botão e a ação limpa a troca.

    Com `mac`, a troca é a DESSE controle (`ControllerOverrides.remapeamento`): o botão que o
    perfil já troca e que a pessoa solta aqui fica `botão: botão` (cancela só nesta peça), e a ação
    de mouse e de teclado segue do perfil, que é o único dono dela.
    """
    acoes_do_perfil = dict(prof.button_actions or {})
    sequencias = _sequencias_do_perfil(prof, mac)
    antes_das_sequencias = dict(sequencias)
    do_perfil = dict(prof.remapeamento or {})
    dela = (prof.controllers or {}).get(mac) if mac else None
    trocas = dict(dela.remapeamento or {}) if dela else {}
    if not mac:
        trocas = do_perfil

    def solta(motor: str) -> None:
        if mac and motor in do_perfil:
            trocas[motor] = motor
        else:
            trocas.pop(motor, None)

    for b, (tipo, valor) in edicoes.items():
        motor = POR_BOTAO[b].motor
        if motor is None:
            continue
        if tipo != SEQUENCIA:
            sequencias.pop(motor, None)
        if tipo == SEQUENCIA:
            solta(motor)
            sequencias[motor] = ativacao_de_botao.sequencia_do_texto(valor)
            if not mac:
                acoes_do_perfil.pop(motor, None)
        elif tipo == "troca":
            trocas[motor] = valor
            if not mac:
                acoes_do_perfil.pop(motor, None)
        elif tipo == ACAO:
            solta(motor)
            if padrao_de_base.get(motor) == valor:
                acoes_do_perfil.pop(motor, None)
            else:
                acoes_do_perfil[motor] = valor
        else:
            solta(motor)
            acoes_do_perfil.pop(motor, None)
    try:
        if mac:
            propria = remap.resolver_da_peca(trocas) or None
            remap.resolver(remap.juntar(do_perfil, propria))
            novo = _com_a_troca_da_peca(prof, mac, propria, acoes_do_perfil)
        else:
            remapeamento = remap.resolver(trocas) or None
            novo = prof.model_copy(update={"button_actions": acoes_do_perfil or None,
                                           "remapeamento": remapeamento})
    except remap.RemapeamentoRecusadoError as exc:
        raise RuntimeError(a06._frase_da_troca(exc)) from None
    if sequencias == antes_das_sequencias:
        return novo
    return _com_as_sequencias(novo, mac, sequencias)


def _sequencias_do_perfil(prof: Any, mac: str | None) -> dict[str, Any]:
    """As sequências do perfil, ou as do controle `mac` quando ele tem as dele (campo a campo)."""
    dela = (prof.controllers or {}).get(mac) if mac else None
    secao = getattr(dela, ATIVACAO, None)
    propria = getattr(secao, "sequencia", None)
    if propria is not None and secao is not None and "sequencia" in secao.model_fields_set:
        return {b: v.model_dump() for b, v in propria.items()}
    return {b: v.model_dump() for b, v in ((prof.ativacao.sequencia if prof.ativacao else {})
                                           or {}).items()}


def _com_as_sequencias(prof: Any, mac: str | None, sequencias: dict[str, Any]) -> Any:
    """O perfil com as sequências no lugar: as do perfil, ou as do controle `mac` por cima.

    O controle que acaba com as mesmas do perfil deixa de ter as dele; a seção que fica sem
    nenhum campo sai. O que o motor recusa (um botão com dois modos) volta como frase.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileAtivacaoConfig

    def refeita(secao: Any, seqs: dict[str, Any] | None) -> Any:
        campos = dict(secao.model_dump(exclude_unset=True)) if secao is not None else {}
        campos.pop("sequencia", None)
        if seqs is not None:
            campos["sequencia"] = seqs
        return ProfileAtivacaoConfig.model_validate(campos) if campos else None

    try:
        if not mac:
            return prof.model_copy(update={ATIVACAO: refeita(prof.ativacao, sequencias or None)})
        do_perfil = _sequencias_do_perfil(prof.model_copy(update={"controllers": None}), None)
        todos = dict(prof.controllers or {})
        dela = todos.get(mac) or ControllerOverrides()
        propria = None if sequencias == do_perfil else sequencias
        dela = dela.model_copy(update={ATIVACAO: refeita(dela.ativacao, propria)})
        if all(getattr(dela, campo) is None for campo in ControllerOverrides.model_fields):
            todos.pop(mac, None)
        else:
            todos[mac] = dela
        return prof.model_copy(update={"controllers": todos or None})
    except ValueError as exc:
        frase = str(exc).split("Value error, ")[-1].split(" [type=")[0]
        raise RuntimeError(frase) from None


def _com_a_troca_da_peca(prof: Any, mac: str, propria: dict[str, str] | None,
                         acoes_do_perfil: dict[str, str]) -> Any:
    """O perfil com a troca do controle `mac` no lugar; a peça que fica sem nada sai do mapa."""
    todos = dict(prof.controllers or {})
    dela = todos.get(mac)
    if dela is None and propria is None:
        return prof.model_copy(update={"button_actions": acoes_do_perfil or None})
    dela = (dela or ControllerOverrides()).model_copy(update={"remapeamento": propria})
    if all(getattr(dela, campo) is None for campo in ControllerOverrides.model_fields):
        todos.pop(mac, None)
    else:
        todos[mac] = dela
    return prof.model_copy(update={"button_actions": acoes_do_perfil or None,
                                   "controllers": todos or None})


def _perfil_novo(ctx: Contexto, estado: dict[str, Any]) -> Any:
    """O perfil que o molde ou o «Novo perfil» vira: nome livre, prioridade acima dos catch-all."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    loader = perfil._com_o_src()
    todos = list(load_all_profiles())
    chave = estado["chave"]
    pedido = _nome_mostrado(ctx, estado).strip() or "Novo perfil"
    nome = a10._nome_livre(pedido, todos)
    so_o_cache: Any = SimpleNamespace(_profiles_cache=todos)
    prioridade = ProfilesActionsMixin._prioridade_acima_dos_catch_all(so_o_cache)
    if chave.startswith(MOLDE):
        prof = loader.perfil_do_molde(chave.removeprefix(MOLDE), nome, prioridade=prioridade)
    else:
        prof = Profile(name=nome, match=MatchManual(), priority=prioridade)
    if estado.get("usar_em"):
        prof = prof.model_copy(update={"match": from_simple_choice(
            estado.get("usar_em_forma") or "janela", str(estado["usar_em"]))})
    return prof


def _o_que_se_guarda(prof: Any) -> tuple[Any, ...]:
    """O que esta tela escreve num perfil: ações, troca do perfil e troca de cada controle."""
    por_peca = {mac: dict(cfg.remapeamento or {})
                for mac, cfg in (prof.controllers or {}).items() if cfg.remapeamento}
    sequencias = {mac: _sequencias_do_perfil(prof, mac)
                  for mac in (prof.controllers or {})
                  if _sequencias_do_perfil(prof, mac) != _sequencias_do_perfil(prof, None)}
    return (prof.button_actions, prof.remapeamento, por_peca, _sequencias_do_perfil(prof, None),
            sequencias)


@gesto(PAGINA, "mapa-guardar", grava="gravar_e_reaplicar")
def mapa_guardar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Guardar»: grava o perfil em edição. O molde e o novo viram perfil em «Meus perfis»."""
    estado = _estado()
    chave = estado["chave"]
    edicoes = dict(estado["edicoes"])
    loader = perfil._com_o_src()
    if chave == NAV or chave.startswith(PERFIL):
        nome = _nome_do_ativo(ctx) if chave == NAV else chave.removeprefix(PERFIL)
        if not nome:
            raise RuntimeError(
                "não há perfil ativo agora, e o que cada botão faz é do perfil. "
                "Escolha um perfil na aba Perfis e tente de novo.")
        prof = loader.load_profile(nome)
        fabrica = acoes.tabela_efetiva(None, getattr(prof, "key_bindings", None) or None) \
            if chave == NAV else {}
        _largar_se_outro_controle(ctx)
        edicoes = dict(_estado()["edicoes"])
        novo = _aplicar_as_edicoes(prof, edicoes, fabrica, _peca_do_vale_para(ctx))
        if _o_que_se_guarda(novo) == _o_que_se_guarda(prof):
            raise RuntimeError(f"não havia o que guardar: o perfil “{nome}” já faz isto.")
        perfil.gravar_e_reaplicar(novo, ctx, p)
        estado["edicoes"] = {}
        return _repinta(ctx)
    if not edicoes and chave == NOVO:
        raise RuntimeError("Nada a guardar: escolha o que ao menos um botão do perfil novo vira.")
    prof = _perfil_novo(ctx, estado)
    fabrica_do_molde: dict[str, str] = {}
    novo = _aplicar_as_edicoes(prof, edicoes, fabrica_do_molde)
    if novo.button_actions and any(t in FICHAS_DO_MOUSE for t in novo.button_actions.values()):
        molde = _molde_da_chave(chave)
        mouse = prof.mouse or loader.ProfileMouseConfig(
            enabled=True, speed=getattr(molde, "velocidade", 8),
            scroll_speed=getattr(molde, "rolagem", 1))
        novo = novo.model_copy(update={"mouse": mouse})
    perfil.gravar_e_reaplicar(novo, ctx, p)
    _largar()
    _estado()["chave"] = f"{PERFIL}{novo.name}"
    return _repinta(ctx)


from . import a10_perfis as a10  # noqa: E402
