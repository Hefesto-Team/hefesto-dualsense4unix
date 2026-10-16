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
import time
from typing import Any, NamedTuple

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.integrations.uinput_mouse import EIXO_DIREITO, EIXO_ESQUERDO
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    ALL_BUTTONS,
    rotulo_lightbar,
)
from hefesto_dualsense4unix.profiles import estilos_de_jogo

from . import Contexto, gesto, perfil, registrar
from . import a02_controles as a02
from . import a06_navegacao as a06

PAGINA = "mapa-do-controle.html"

BLOCO_DOS_CONTROLES = '[data-bloco="controles-do-mapa"]'
BLOCO_DO_PERFIL = "#perfil"

ACESO = "aceso-"  # (noqa-acento) prefixo de endereço, não é prosa
LUZ = "luz-cor"

#: o mesmo prazo da Navegação: se o tique para (outra aba, janela fechada), a edição some.
PAUSA_DE_OUTRA_ABA = 5.0

NAV, NOVO = "nav", "novo"
ACAO = "acao"  # (noqa-acento): a ficha do desenho (`data-v="acao:<token>"`), não é texto da tela
MOLDE, PERFIL = "molde:", "perfil:"

ROTULO_DO_TIPO = {"nav": "Navegação", "pac": "Point and click", "troca": "Trocar os botões"}

NOME_DA_NAVEGACAO = "Navegar no computador"

#: o que a tela diz de quem usa o perfil que não é de jogo nenhum.
FORA_DO_JOGO = "Fora do jogo"


class Botao(NamedTuple):
    """Uma linha da tela: o botão que o usuário vê e o que o motor chama de botão."""

    b: str
    #: a peça do desenho que acende com ele (`#mp-<peça>`)
    peca: str
    nome: str
    lado: str
    #: o id no motor de ações (`acoes.BOTOES`); `None` onde o motor não tem linha
    motor: str | None
    #: `True` onde nada se escolhe: o PS e o toque no touchpad
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

#: o toque no touchpad move o cursor e não se troca: a linha diz o que ele faz, como na Navegação.
TOQUE = "tp_toque"

#: o botão que a troca de botões conhece por este mesmo nome (o motor da troca só tem os 16).
PODE_TROCAR: frozenset[str] = frozenset(
    x.b for x in BOTOES_DA_PAGINA if x.motor in remap.REMAPEAVEIS)

#: o destino de uma troca, com o texto da tela e a peça cujo glifo a ilustra. O PS e o touchpad
#: ficam de fora: o motor os recusa (`remap.MOTIVO_PS`, `remap.MOTIVO_FORA`).
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

#: só o que o motor executa: não há «Rolagem para cima», «Voltar» nem «Avançar».
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

#: o que é do mouse, para o tipo «Point and click» de um perfil do disco.
FICHAS_DO_MOUSE: frozenset[str] = frozenset(t for t, _ in OPCOES_DE_MOUSE)

#: a peça do desenho → o botão físico que ela é, para o pisca. Só os botões que se apertam.
NOME_NO_LEITOR = {"stick_l": "l3", "stick_r": "r3"}
PISCAM: tuple[str, ...] = (*ALL_BUTTONS, *NOME_NO_LEITOR)

#: o botão físico (peça do leitor) → o destino que a captura grava quando ele é apertado.
DESTINO_DA_PECA = {"stick_l": "l3", "stick_r": "r3", "share": "create"}

_EDITANDO: dict[str, Any] = {}
_VISTO: list[float] = [0.0]


# ---------------------------------------------------------------------------
# A edição: o que a pessoa já mexeu e ainda não guardou
# ---------------------------------------------------------------------------

def _estado() -> dict[str, Any]:
    """A edição em curso, ou a de partida; some se o tique parou."""
    agora = time.monotonic()
    if _EDITANDO and _VISTO[0] and agora - _VISTO[0] > PAUSA_DE_OUTRA_ABA:
        _EDITANDO.clear()
    if not _EDITANDO:
        _EDITANDO.update({"chave": NAV, "edicoes": {}, "nome": None,
                          "usar_em": None, "botao": "cross"})
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
                or _estilo_de_clicar(cru)
                or (cru.get("mouse") or {}).get("enabled")):
            meus.append(cru)
    return meus


def _nome_do_ativo(ctx: Contexto) -> str:
    return perfil.nome_do_ativo(ctx.state).strip()


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
    for motor, destino in (cru.get("remapeamento") or {}).items():
        por_motor[motor] = ("troca", str(destino))
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
    return "troca" if "troca" in tipos else "nav"


# ---------------------------------------------------------------------------
# A pintura
# ---------------------------------------------------------------------------

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


def _estado_da_linha(x: Botao, valores: dict[str, tuple[str, str]], botao: str,
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
        # o que as âncoras `#point-and-click` e `#trocar` pedem: a página abre o seletor nelas
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
    acesas = _acesos(ctx, itens)
    mesa: dict[str, Any] = {**_mesa_da_edicao(ctx), **_linhas(ctx, acesas),
                            LUZ: _luz(ctx, ativo, itens)}
    return {
        "mesa": mesa,
        "blocos": {BLOCO_DOS_CONTROLES: chips_do_controle(ctx.mesa, ativo),
                   BLOCO_DO_PERFIL: _opcoes_do_perfil(ctx)},
        "cobertura": {"pintados": len(mesa) + 2, "sem_dono": 0},
        "sem_dono": {},
    }


def _repinta(ctx: Contexto) -> dict[str, Any]:
    """A resposta de um gesto: a tela inteira de agora, sem esperar o próximo tique."""
    _VISTO[0] = time.monotonic()
    _, itens = _escolhidos(ctx)
    return {"mesa": {**_mesa_da_edicao(ctx), **_linhas(ctx, _acesos(ctx, itens))}}


# ---------------------------------------------------------------------------
# Os gestos: a edição
# ---------------------------------------------------------------------------

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
    """O usuário clicou numa linha: ela vira a escolhida, no desenho e na lista."""
    b = str(o.get("b") or "").strip()
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
    estado = _estado()
    b = estado["botao"]
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
    edicoes = _estado()["edicoes"]
    edicoes[cursor] = (ACAO, "__CURSOR__")
    edicoes[rolagem] = (ACAO, "__ROLAGEM__")
    return _repinta(ctx)


@gesto(PAGINA, "mapa-padrao")
def mapa_padrao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Voltar ao padrão»: cada botão volta ao de fábrica (o molde, ao que o molde traz).
    Só vale no «Guardar»."""
    estado = _estado()
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


# ---------------------------------------------------------------------------
# Guardar
# ---------------------------------------------------------------------------

def _aplicar_as_edicoes(prof: Any, edicoes: dict[str, tuple[str, str]],
                        padrao_de_base: dict[str, str]) -> Any:
    """O perfil com as edições: troca limpa a ação do botão e a ação limpa a troca."""
    acoes_do_perfil = dict(prof.button_actions or {})
    trocas = dict(prof.remapeamento or {})
    for b, (tipo, valor) in edicoes.items():
        motor = POR_BOTAO[b].motor
        if motor is None:
            continue
        if tipo == "troca":
            trocas[motor] = valor
            acoes_do_perfil.pop(motor, None)
        elif tipo == ACAO:
            trocas.pop(motor, None)
            if padrao_de_base.get(motor) == valor:
                acoes_do_perfil.pop(motor, None)
            else:
                acoes_do_perfil[motor] = valor
        else:
            trocas.pop(motor, None)
            acoes_do_perfil.pop(motor, None)
    try:
        remapeamento = remap.resolver(trocas) or None
    except remap.RemapeamentoRecusadoError as exc:
        raise RuntimeError(a06._frase_da_troca(exc)) from None
    return prof.model_copy(update={"button_actions": acoes_do_perfil or None,
                                   "remapeamento": remapeamento})


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
        novo = _aplicar_as_edicoes(prof, edicoes, fabrica)
        if (novo.button_actions, novo.remapeamento) == (prof.button_actions, prof.remapeamento):
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


from . import a10_perfis as a10  # noqa: E402  (depois dos gestos: a10 não importa a13)
