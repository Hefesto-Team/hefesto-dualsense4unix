#!/usr/bin/env python3
"""O pacote da aba `06` Navegação: «Permitir navegação», o perfil de point and click e os botões.

Os controles aparecem pela cor do plástico (`blocos`); o que o desenho não endereça não se pinta.
As linhas de botão gravam só a diferença do de fábrica em `Profile.button_actions`, e a página
CARREGADA decide as palavras da «Função do teclado» (`_o_que_a_pagina_oferece`). O «Perfil Jogo -
Navegação» e os gestos do PS moram no `maquina.json`; «Permitir navegação» escolhe a Interna, a
Steam (o Big Picture) ou o Uso geral. O PS sozinho é a linha PS de «Os botões no computador».

Recusa na tela: `RuntimeError` e `ValueError` vão ao diário e o botão pisca `hef-recusou`.
"""
from __future__ import annotations

import html
import re
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap

from . import (
    NOME_SEM_LEITURA,
    Contexto,
    perfil,
    registrar,
)

SEM_DONO: dict[str, str] = {}
SEM_ENDERECO: dict[str, str] = {}

TECLADO_SO_FORA = "Só fora do jogo"
TECLADO_DESATIVADO = "Desativado"
TECLADO_SO_DENTRO = "Só dentro do jogo"
TECLADO_SEMPRE = "Sempre"

#: O `data-quem` do quadro (o que esmaece as linhas quando a Steam navega), e o que a Steam faz do
#: lado dela.
QUEM_HEFESTO = "hefesto"
QUEM_STEAM = "steam"

#: «Permitir navegação» (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, N5, 16/10/2026): os três botões que
#: tomaram o lugar de «Quem navega», «Tipo de navegação» e «Navega com». Cada um acende pelas
#: bandeiras que o daemon já guarda (o Big Picture e o tipo da Interna), sem campo novo no perfil.
PERMITIR = "permitir-navegacao"
PERMITIR_INTERNA = "interna"
PERMITIR_STEAM = "steam"
PERMITIR_USO_GERAL = "uso-geral"
DO_PERMITIR: dict[str, tuple[str, str]] = {
    PERMITIR_INTERNA: ("Interna", "O controle navega as abas do Hefesto"),
    PERMITIR_STEAM: ("Steam", "A Steam navega com o controle, no Big Picture"),
    PERMITIR_USO_GERAL: ("Uso geral", "O controle vira mouse e teclado do computador"),
}
#: Os endereços das linhas de gesto que valem e dos botões livres do «+ Gesto».
PREFIXO_DA_VALIDADE = "vale-"
PREFIXO_DA_LIBERDADE = "livre-"
NA_STEAM_BIG_PICTURE = "big-picture"
NA_STEAM_PADRAO = "padrao"  # (noqa-acento) valor de contrato do gesto
#: A recusa do «Steam padrão», só no diário (a tela pisca o botão): o modo não tem quem o aplique.
FRASE_DO_STEAM_PADRAO = "O «Steam padrão» não tem quem o aplique; a navegação segue no Big Picture."
#: Os blocos que a página repinta por inteiro, e os prefixos dos valores do seletor de point and
#: click (os mesmos do mapa: `molde:<chave>` e `perfil:<nome>`).
BLOCO_PARA_QUEM = "para-quem"
BLOCO_DOS_MEUS_PERFIS = "meus-perfis"
PREFIXO_DO_ATALHO = "atalho-"
PREFIXO_DO_MOLDE = "molde:"
PREFIXO_DO_PERFIL = "perfil:"
PADRAO_DO_POINT_AND_CLICK = "molde:point_and_click"

#: O endereço de CADA chip da fita é o do `monta.fita()` e da 09: sem ele o `--plastico` do chip é
#: cor cravada para `check_identidade_vem_de_cima.py`.
CAMPO_DO_CHIP = "fita-chip"

PALAVRAS_DO_TECLADO: dict[bool, tuple[str, ...]] = {
    True: (TECLADO_SO_FORA,),
    False: (TECLADO_DESATIVADO,),
}

#: O tipo que o daemon guarda (`navegacao.interna.set {tipo}`,
#: A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01) e o rótulo dele; «Permitir
#: navegação» grava a Interna pelo botão «Interna» e o computador pelo «Uso geral».
TIPO_INTERNA = "interna"
TIPO_COMPUTADOR = "computador"
ROTULOS_DO_TIPO: dict[str, str] = {
    TIPO_INTERNA: "Interna",
    TIPO_COMPUTADOR: "Mouse e teclado",
}

def _navegacao(estado: dict[str, Any] | None) -> dict[str, Any]:
    """O bloco `navegacao` do `state_full` (o dono é o daemon), ou vazio."""
    bloco = (estado or {}).get("navegacao")
    return bloco if isinstance(bloco, dict) else {}


def big_picture_ligado(estado: dict[str, Any] | None) -> bool | None:
    """O que o daemon diz do Modo Big Picture, ou ``None`` sem o bloco (a tela não afirma)."""
    bloco = _navegacao(estado).get("big_picture")
    ligado = bloco.get("ligado") if isinstance(bloco, dict) else None
    return ligado if isinstance(ligado, bool) else None


def tipo_de_navegacao(estado: dict[str, Any] | None) -> str:
    """O tipo escolhido na lista. Sem o bloco do daemon, só o computador existe."""
    tipo = _navegacao(estado).get("tipo")
    return tipo if tipo in ROTULOS_DO_TIPO else TIPO_COMPUTADOR


def permitir_de_agora(estado: dict[str, Any] | None) -> str:
    """O botão aceso de «Permitir navegação»: a Steam com o Big Picture, senão o tipo guardado."""
    if big_picture_ligado(estado):
        return PERMITIR_STEAM
    return PERMITIR_INTERNA if tipo_de_navegacao(estado) == TIPO_INTERNA else PERMITIR_USO_GERAL


def interna_ligada(estado: dict[str, Any] | None) -> bool:
    """A Navegação Interna está ligada, pelo bloco do daemon; sem ele, não."""
    return _navegacao(estado).get("interna_ligada") is True

#: `core/acoes_de_botao.BOTOES` — a lista é do produto, e não se digita aqui.
CAMPO_DA_COR = "cor-de-quem-navega"  # endereço da cor do chip: o produto a reescreve
CHAVE_PRIMARIA = "primario"  # (noqa-acento) chave do contrato com o resto da tela
PREFIXO_DA_ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa

ROTULOS_DA_TROCA: dict[str, str] = {
    "Triângulo": "triangle",
    "Círculo": "circle",
    "Quadrado": "square",
    "Cruz": "cross",
    "L1": "l1",
    "R1": "r1",
    "L2": "l2",
    "R2": "r2",
    "L3 (clique)": "l3",
    "L3 (direção)": acoes.EIXO_ESQUERDO,
    "R3 (clique)": "r3",
    "R3 (direção)": acoes.EIXO_DIREITO,
    "D-pad cima": "dpad_up",
    "D-pad direita": "dpad_right",
    "D-pad baixo": "dpad_down",
    "D-pad esquerda": "dpad_left",
    "Share": "create",
    "Options": "options",
    "Touchpad (clique)": remap.DESTINO_TOUCHPAD,
    "PS": remap.BOTAO_PS,
}

_SELECT_DO_TECLADO = re.compile(
    r'<select[^>]*data-campo="teclado-estado"[^>]*>(.*?)</select>', re.S)
_OPCAO = re.compile(r"<option[^>]*>(.*?)</option>", re.S)

_OFERTAS: tuple[tuple[int, int], frozenset[str]] | None = None


def _o_que_a_pagina_oferece() -> frozenset[str]:
    """As `<option>` da "Função do teclado" NA PÁGINA QUE O PILOTO CARREGA.

    `publicado=True` é deliberado (a mesma exceção de `a03_gatilhos._pagina_publicada`): o padrão de
    `onde.pagina` é a BANCADA, mas quem pinta pinta no que está no `WebView`, e o piloto abre SEMPRE
    o publicado. Lê uma vez por versão do arquivo, selo `(mtime_ns, tamanho)`: a página tem 385 KB e
    a pintura roda a cada 100 ms (reler a cada tique seria 3,8 MB/s). `frozenset()` quando o arquivo
    não abre: aí `_o_teclado_em_palavras` cai na palavra de produto, o destino correto para produto
    instalado sem a página.

    Janela que isto não fecha, estreita: publicar com o aplicativo ABERTO e sem trocar de aba (o
    arquivo muda, o pacote emite a palavra nova e o DOM carregado ainda é o antigo, então a escrita
    é descartada até o próximo carregamento; trocar de aba ou reabrir recarrega, em
    `hefesto_vivo.Piloto._ir`).
    """
    global _OFERTAS
    from hefesto_dualsense4unix.interface import onde

    try:
        arquivo = onde.pagina(PAGINA, publicado=True)
        st = arquivo.stat()
        selo = (st.st_mtime_ns, st.st_size)
    except OSError:
        return frozenset()
    if _OFERTAS is not None and _OFERTAS[0] == selo:
        return _OFERTAS[1]
    try:
        doc = arquivo.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    bloco = _SELECT_DO_TECLADO.search(doc)
    ofertas = frozenset(_OPCAO.findall(bloco.group(1))) if bloco else frozenset()
    _OFERTAS = (selo, ofertas)
    return ofertas


def _o_teclado_em_palavras(ligado: bool, so_dentro: bool = False, sempre: bool = False) -> str:
    """A palavra daquele estado que a página CARREGADA sabe receber.

    «Sempre» e «Só dentro do jogo» são o teclado LIGADO com um campo do perfil
    (`teclado_sempre`, `teclado_so_no_jogo`): sem eles, ligado é «Só fora».
    """
    if ligado and sempre:
        candidatas: tuple[str, ...] = (TECLADO_SEMPRE,)
    elif ligado and so_dentro:
        candidatas = (TECLADO_SO_DENTRO,)
    else:
        candidatas = PALAVRAS_DO_TECLADO[ligado]
    ofertas = _o_que_a_pagina_oferece()
    for palavra in candidatas:
        if palavra in ofertas:
            return palavra
    return candidatas[0]


def _nome_do_botao(botao: str) -> str:
    """`"l2"` → `"L2 (gatilho esquerdo)"`. O nome que o usuário lê, e é do MOTOR.

    A tabela não se escreve aqui: `app/actions/input_actions.humanize_button` é dona dos vinte nomes
    (KBD-01), e a GTK mostra os mesmos; as frases de recusa do "Guardar" mandavam o id cru (*"…sem
    quem as atenda: touchpad_left_press"*).

    **Os dois eixos continuam crus** (02/09/2026): `_nome_do_botao('r3_direcao')` e `('l3_direcao')`
    devolvem o id, pois são 22 botões em `acoes.BOTOES` e 20 nomes em `_BUTTON_LABELS` (falta a
    DIREÇÃO dos analógicos). A cura mora no MOTOR, não aqui: copiar duas linhas criaria a segunda
    tabela que `test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela` impede (o mesmo botão
    com dois nomes). O dano de hoje é de forma: `acoes.resolver()` pula os eixos, então nunca chegam
    ao `sem_dono`; só o `nao_reconhecidas` do "Guardar" os exporia.

    O import é tardio porque `input_actions` puxa GTK no topo (e `mouse_actions` junto), e os
    pacotes são puros, importáveis sem janela; custa uma vez, no caminho da recusa. Sem GTK no
    ambiente o id cru volta (feio e honesto, como `acoes.rotulo()` para token sem nome).
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    except Exception:
        return botao
    return humanize_button(botao)


SEM_LEITURA = ""


def _monta() -> Any:
    """O `monta`, importado tarde. O `pacotes/__init__` põe `interface/` no path."""
    import monta

    return monta


def cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, LIDO do mapa — ou `""` sem leitura."""
    if not slug:
        return SEM_LEITURA
    try:
        # Os modelos sem hexa amostrado devolvem `url(#hachura-sem-hex)`, que
        return str(_monta().cor_de_css(slug))
    except Exception:
        return SEM_LEITURA
    except SystemExit:
        return SEM_LEITURA


_ZONAS_DE_IDENTIDADE: frozenset[str] | None = None
_FOLHA: dict[str, dict[str, str]] | None = None


def _ler_a_folha() -> dict[str, dict[str, str]]:
    """As zonas de cada modelo, lidas do `ds_limpo.svg` que o gerador pinta."""
    global _FOLHA, _ZONAS_DE_IDENTIDADE
    if _FOLHA is not None:
        return _FOLHA
    folha: dict[str, dict[str, str]] = {}
    for slug, corpo in re.findall(
            r'svg\[data-colorway="([^"]+)"\]\{([^}]*)\}', _monta().DS):
        zonas = {}
        for par in corpo.split(";"):
            chave, _, valor = par.partition(":")
            if chave.strip().startswith("--z-"):
                zonas[chave.strip()] = valor.strip()
        folha[slug] = zonas
    vistos: dict[str, set[str]] = {}
    for zonas in folha.values():
        for chave, valor in zonas.items():
            vistos.setdefault(chave, set()).add(valor)
    _ZONAS_DE_IDENTIDADE = frozenset(k for k, v in vistos.items() if len(v) > 1)
    _FOLHA = folha
    return folha


def colorway_do_aparelho(slug: str) -> str:
    """O `data-colorway` daquele lugar da mesa — o id do modelo, ou `""`."""
    if not slug:
        return SEM_LEITURA
    return slug if slug in _ler_a_folha() else SEM_LEITURA


def folha_do_plastico(mesa: list[dict[str, Any]], caixa: str = ".nav-ctl") -> str:
    """A folha de estilo VIVA que pinta o casco de cada lugar da mesa.

    Ela é o cinto e o alvo `atributo` é o suspensório (03/09/2026): com o alvo, o `data-colorway` de
    cada `<svg>` é um campo (`colorway_do_aparelho`) e a página publica os 28 modelos; a folha fica
    por pintar o casco numa árvore em que o alvo ainda não chegou, e sai quando ele estiver no `dev`
    e provado na tela.

    Por que folha e não campo: as peças do SVG leem `var(--z-casca)`, escrita por regra
    `svg[data-colorway="…"]`, e o piloto (texto, valor, classe, cor, largura, fundo, `innerHTML`,
    atributo) **não alcança variável CSS de elemento**. Reescrever o SVG por `innerHTML` custaria
    370 linhas por cartão a cada meio segundo e nunca sossegaria, pois o navegador NORMALIZA
    marcação e o `escrever()` acusaria mudança em todo tique; o `innerHTML` de um `<style>` é texto
    e volta como foi escrito. Vence a folha de dentro do SVG por especificidade:
    `.nav-ctl[data-controle="p1"] .ds-svg` (0,3,0) contra `svg[data-colorway="cosmic-red"]` (0,1,1).

    Sem leitura, o casco fica NEUTRO (regra de produto): controle no rádio não entrega a cor, e o
    casco do mockup afirmaria aparelho que não está na mesa. As zonas que não são identidade ficam:
    pintá-las apagaria o desenho em vez de calar a cor.

    :param caixa: o seletor da CAIXA de um lugar da mesa, que muda de aba (`.nav-ctl` aqui, `.ctrl`
    na Iluminação). Parâmetro desde 03/09/2026, quando a aba 04 precisou da mesma folha (o desenho
    GRANDE dela mostrava o Cosmic Red e o Starlight Blue do mockup sob um rótulo `P1 • White • USB`,
    `rgb(174,51,90)` no corpo contra `rgb(228,224,216)` na moldura da MESMA célula); duas cópias
    divergiriam no primeiro modelo novo. O seletor precisa vencer o `svg[data-colorway="…"]` de
    dentro do SVG (0,1,1); `.nav-ctl[…] .ds-svg` e `.ctrl[…] .ds-svg` valem (0,3,0).
    """
    folha = _ler_a_folha()
    identidade = _ZONAS_DE_IDENTIDADE or frozenset()
    regras = []
    ocupados: set[str] = set()
    for lugar in mesa:
        pref = str(lugar.get("pref") or "")
        if not pref:
            continue
        ocupados.add(pref)
        zonas = folha.get(str(lugar.get("cor") or ""))
        if zonas:
            corpo = ";".join(f"{k}:{v}" for k, v in zonas.items())
        else:
            corpo = ";".join(f"{k}:var(--border-forte)" for k in sorted(identidade))
        if corpo:
            regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{corpo}}}')
    regras.extend(_apagar_os_lugares_sem_dono(caixa, ocupados, identidade))
    return "".join(regras)


LUGARES_DO_DESENHO = 4


def _apagar_os_lugares_sem_dono(
    caixa: str, ocupados: set[str], identidade: frozenset[str],
) -> list[str]:
    """As regras que APAGAM o aparelho do mockup nos lugares que ficaram vazios.

    Medido no produto em 03/09/2026 com UM controle no cabo e a aba aberta no WebKit (DOM vivo): P1
    White casco `rgb(68,71,90)`; **P2 «—» casco `rgb(126,184,212)` (o Starlight Blue do mockup) e
    lightbar `rgb(255,0,0)` (o `style="--luz:#ff0000"` do `monta.svg()`)**; P3 e P4 desconectados em
    `rgb(83,87,111)`. Lugar SEM controle saía mais colorido e aceso que o único de verdade.

    Causa: P3 e P4 nascem `class="nav-ctl vazia"` e a folha do desenho já desenha lugar vazio
    (`.nav-ctl.vazia .ds-svg …{fill:var(--linha)!important}`); o P2 nasce OCUPADO e fica vazio em
    execução, e quem o esvazia (`pacotes.apagar_os_lugares_sem_dono` + passo `vazios` do piloto)
    escreve a classe **`off`**, que folha nenhuma menciona: duas palavras para o mesmo estado nunca
    se encontraram. É a lei da `folha_do_plastico` onde estava calada: lugar sem dono é, com mais
    razão que sem leitura de cor, lugar sobre o qual a tela nada afirma. O neutro é o `var(--linha)`
    do desenho (o do `.vazia`), não cinza digitado aqui. O `!important` é necessário: a `--luz`
    chega como `style="--luz:#ff0000"` no elemento (`monta.py`), e estilo de linha vence qualquer
    regra de folha que não o traga.
    """
    if not identidade:
        return []
    zonas = ";".join(f"{k}:var(--linha)" for k in sorted(identidade))
    regras = []
    for n in range(1, LUGARES_DO_DESENHO + 1):
        pref = f"p{n}"
        if pref in ocupados:
            continue
        regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{zonas}}}')
        regras.append(f'{caixa}[data-controle="{pref}"] [id$="-lightbar"]'
                      f'{{--luz:var(--linha) !important}}')
    return regras


def chips_da_fita(mesa: list[dict[str, Any]]) -> str:
    """Os chips da fita do topo, para a `06`, com os controles da MESA.

    Por que esta aba tem os seus, e não os de `monta.fita()`: o piloto troca a fita INTEIRA
    (`hefesto_vivo._fita`), mas ela **desiste** quando um controle da mesa não tem cor (`if not mesa
    or any(not c.get("cor") …): return ""`), e pelo rádio a cor não se lê. Medido em 03/09/2026 com
    os dois controles do usuário e o daemon no ar: a fita da `06` mostrava `P1 · Cosmic Red · USB` e
    `P2 · Starlight Blue · BT` (os do mockup) ao lado de um cabeçalho certo. Este endereço salva a
    fita quando o dono dela desiste; quando `_fita` responde, ele troca o bloco antes (primeiro
    passo do `pintar`) e os dois dizem a mesma coisa.

    Acesos e borda (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01, 09/10/2026): a aba não escolhe
    controle e o que mostra vale para todos, então `monta.acesos_da_fita(…, escolhe=False)` acende o
    `Todos` e todos da mesa. O chip leva `--plastico` quando a cor foi lida, pela regra do
    `monta.fita()` (sem cor lida, nem a classe nem o `style`). Cada chip tem endereço próprio,
    `data-campo="fita-chip"`, como no `monta.fita()`, na 03 e na 09: o do bloco não basta para a
    régua da identidade, que lê o `--plastico` no `style` do próprio elemento.
    """
    monta = _monta()
    mostra_todos, _ = monta.escolha_da_fita("todos", mesa)
    acesos = monta.acesos_da_fita("todos", mesa, escolhe=False)
    chips = [f"<span>{monta.ROTULO_DA_FITA}</span>"]
    if mostra_todos:
        chips.append(f'<label class="chip{" on" if "todos" in acesos else ""}">Todos</label>')
    for lugar in mesa:
        nome = str(lugar.get("nome") or "")
        if nome == NOME_SEM_LEITURA:
            nome = SEM_LEITURA
        partes = [f'P{lugar["jogador"]}' if lugar.get("jogador") else "",
                  nome, str(lugar.get("via") or "")]
        rotulo = monta.SEPARADOR.join(p for p in partes if p)
        aceso = " on" if str(lugar.get("pref") or "") in acesos else ""
        slug = str(lugar.get("cor") or "")
        if slug and monta.o_desenho_conhece(slug):
            chips.append(f'<label class="chip plastico{aceso}" data-campo="{CAMPO_DO_CHIP}"'
                         f' style="--plastico:{monta.cor_da_zona(slug)}"'
                         ' title="A borda é a cor do plástico">'
                         f"{rotulo}</label>")
        else:
            chips.append(f'<label class="chip{aceso}" data-campo="{CAMPO_DO_CHIP}">'
                         f"{rotulo}</label>")
    return "".join(chips)


def chips_de_quem_navega(lugares: list[dict[str, Any]], *, so_o_primeiro: bool = False) -> str:
    """Os controles pela cor do plástico: o que navega aceso, os outros só pintados.

    ``lugares`` são os conectados (``cor``, ``nome``); o primário marca quem navega, e sem
    nenhum marcado vale o primeiro. Só pintado: a escolha de quem navega é do daemon.
    """
    monta = _monta()
    if not lugares:
        return ""
    aceso = next((i for i, x in enumerate(lugares) if x.get(CHAVE_PRIMARIA)), 0)
    chips = []
    for i, lugar in enumerate(lugares):
        if so_o_primeiro and i != aceso:
            continue
        nome = html.escape(str(lugar.get("nome") or ""))
        slug = str(lugar.get("cor") or "")
        cor = ""
        if slug and monta.o_desenho_conhece(slug):
            cor = (f' data-campo="{CAMPO_DA_COR}-{i}" data-hef-alvo="plastico"'
                   f' style="--plastico:{monta.cor_da_zona(slug)}"')
        marca = " on" if i == aceso else ""
        move = not (so_o_primeiro or i != aceso)
        # com quatro controles o nome encolhe com reticências, e o `title` o guarda inteiro
        dica = f' data-dica="{nome}: só este controle move o cursor"' if move else ""
        chips.append(f'<span class="chip plastico{marca}"{cor}{dica}>'
                     f'<span class="nm" title="{nome}">{nome}</span></span>')
    return "".join(chips)


def o_mouse_navega(estado: dict[str, Any] | None) -> bool:
    """O primário navega o PC: o mouse não está desligado (sem bloco, o de nascença).

    Um dono, dois leitores: o cartão (a bolinha e «Navega o PC») e a janela da Navegação Interna,
    que não dá seleção a quem navega o PC com o mouse ligado
    (`D-2909-O-CURSOR-DE-QUEM-NAVEGA-O-PC-E-O-DO-PC`).
    """
    rato = (estado or {}).get("mouse_emulation")
    return not (isinstance(rato, dict) and rato.get("enabled") is False)


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O vocabulário é o do motor: `acoes.BOTOES` diz quais linhas existem, `acoes.padrao()` o de
    fábrica, `acoes.rotulo()` o texto da `<option>`; o gerador monta as mesmas listas do mesmo lugar
    (`aba06._celula_da_acao` chama `por_grupo(linha)`), então o valor emitido SEMPRE existe como
    opção (condição do `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa). O
    perfil vence o de fábrica linha a linha: `button_actions` guarda DIFERENÇA (`None` = herda), e
    linha ausente é o de fábrica.

    **São três camadas, não duas** (06/09/2026): o de fábrica, os atalhos da janela antiga
    (`key_bindings`) e a escolha desta tela, nessa ordem, por `acoes.tabela_efetiva` (o
    `resolver()`, a MESMA chamada que alimenta o device). A função montava fábrica +
    `button_actions` e nunca olhava `key_bindings`, a cegueira que o `resolver()` tinha antes da
    ONDA3-MOTOR-01: perfil com `Super` no Options pela janela antiga fazia a tabela mostrar o de
    fábrica sobre botão que digitava outra coisa.

    O que a lista não tem como dizer não é dito AQUI: combinação livre não é `<option>`,
    `acoes.rotulo()` devolve o token cru e o `escrever()` a recusa em silêncio. Quem nomeia essas
    linhas é a TIRA (`linhas_que_a_lista_nao_sabe_dizer`).
    """
    perfil_ = p or {}
    tabela = acoes.tabela_efetiva(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(str(tabela.get(botao) or ""))
        for botao in acoes.BOTOES
    }


def _atalho_em_palavras(colado: str) -> str:
    """`"KEY_LEFTCTRL+KEY_W"` → `"Ctrl + W"`, pelo dono do produto. Import tardio pela razão de
    `_nome_do_botao`; sem GTK volta o token cru."""
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:
        return colado
    return str(humanize_binding(colado))


def _o_ps_digita(token: str | None) -> bool | None:
    """O token escolhido é coisa que o PS sabe entregar? — PERGUNTADO AO DONO."""
    try:
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            _o_ps_digita as do_dono,
        )
    except Exception:
        return None
    return bool(do_dono(token))


#: Quanto a pausa de outra aba vale (segundos); `TIQUE_MS` não se importa daqui: `hefesto_vivo` puxa
#: GTK no topo.
PAUSA_DE_OUTRA_ABA = 5.0


def _rotulo_do_destino(botao: str) -> str:
    """O id de destino → o texto da `<option>`. Sem rótulo, o id cru."""
    for rotulo, alvo in ROTULOS_DA_TROCA.items():
        if alvo == botao:
            return rotulo
    return botao


def _os_atalhos_fora_da_lista(linhas: dict[str, str]) -> dict[str, str]:
    """As linhas cujo atalho a lista não tem como dizer (o mapa grava combinações livres).

    Troca, em `linhas`, o token cru pelo atalho em palavras e devolve `{botão: atalho}`: o
    pacote acrescenta essa opção ao `<select>` da linha, e a tela mostra o que o botão faz de
    verdade em vez de repor o de fábrica sobre ele.
    """
    fora: dict[str, str] = {}
    for campo, rotulo in list(linhas.items()):
        if acoes.token_do_rotulo(rotulo) is not None:
            continue
        em_palavras = _atalho_em_palavras(rotulo)
        linhas[campo] = em_palavras
        fora[campo.removeprefix(PREFIXO_DA_ACAO)] = em_palavras
    return fora


def _quem_navega(ctx: Contexto) -> list[dict[str, Any]]:
    """Os controles que a tela mostra: a mesa, com a marca de primário em quem navega."""
    chefe = next((str(c.get("uniq") or "") for c in ctx.conectados if c.get("is_primary")), "")
    return [{**m, CHAVE_PRIMARIA: bool(chefe) and str(m.get("uniq") or "") == chefe}
            for m in ctx.mesa]


def _o_point_and_click_de_hoje() -> str:
    """A escolha do «Perfil de point and click», que é do computador (`maquina.json`)."""
    maquina = _a_maquina()
    computador = getattr(maquina, "computador", None)
    mouse = getattr(getattr(computador, "global_", None), "mouse", None)
    escolha = getattr(mouse, "point_and_click", None)
    return str(escolha) if escolha else PADRAO_DO_POINT_AND_CLICK


def _opcoes_dos_meus_perfis(ctx: Contexto) -> str:
    """«Meus perfis» do seletor de point and click: os do disco que configuram botão."""
    from . import a13_mapa_do_controle as mapa

    return "".join(
        f'<option value="{PREFIXO_DO_PERFIL}{html.escape(str(c.get("name") or ""), quote=True)}">'
        f'{html.escape(str(c.get("name") or ""))}</option>'
        for c in mapa._perfis_do_disco(ctx))


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """O que o tique escreve na tela: as linhas, as opções, os controles e os gestos do PS.

    Os controles aparecem pela cor do plástico (`blocos`), sem número de jogador. Cada campo
    pintado tem endereço na página; o que o desenho não endereça não se pinta.
    """
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo_que_vale(st.get("active_profile"))
    mesa: dict[str, Any] = {
        "fita-chips": chips_da_fita(ctx.mesa),
        "quem-navega": QUEM_STEAM if big_picture_ligado(st) else QUEM_HEFESTO,
        PERMITIR: permitir_de_agora(st),
        "na-steam": NA_STEAM_BIG_PICTURE,
        "vel-cursor": rato.get("speed"),
        "vel-rolagem": rato.get("scroll_speed"),
        "point-and-click-perfil": _o_point_and_click_de_hoje(),
    }
    if "keyboard_emulation" in st:
        mesa["teclado-estado"] = _o_teclado_em_palavras(
            bool(tecla.get("enabled")), so_dentro=bool((p or {}).get("teclado_so_no_jogo")),
            sempre=bool((p or {}).get("teclado_sempre")))
    linhas = _linhas_dos_botoes(p)
    atalhos = _os_atalhos_fora_da_lista(linhas)
    mesa.update(linhas)
    mesa.update(_o_que_os_gestos_fazem())
    mesa[f"{PREFIXO_DA_ACAO}ps"] = _o_que_o_ps_faz(p, linhas[f"{PREFIXO_DA_ACAO}ps"])
    blocos = {
        f'[data-bloco="{BLOCO_PARA_QUEM}"]': chips_de_quem_navega(
            _quem_navega(ctx), so_o_primeiro=True),
        f'[data-bloco="{BLOCO_DOS_MEUS_PERFIS}"]': _opcoes_dos_meus_perfis(ctx),
        **{f'[data-bloco="{PREFIXO_DO_ATALHO}{b}"]': f"<option>{html.escape(r)}</option>"
           for b, r in atalhos.items()},
    }
    return {
        "mesa": mesa,
        "blocos": blocos,
        "sem_dono": {},
        "cobertura": {"pintados": len(mesa) + len(blocos), "sem_dono": 0},
    }


from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    DEFAULT_MOUSE_SPEED,
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MAX,
    SCROLL_SPEED_MIN,
)

from . import gesto  # noqa: E402

MANUAL = "manual"


def _rato(ctx: Contexto) -> dict[str, Any]:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora."""
    return ctx.state.get("mouse_emulation") or {}


#: DISCO, E SÓ: nunca `perfil.gravar_e_reaplicar`. O aparelho já recebeu a mudança pelo
#: `mouse.emulation.set`; o perfil guarda o que este clique mudou.
_DO_RATO: dict[str, str] = {
    "mouse_speed": "speed",
    "mouse_scroll": "scroll_speed",
    "point_and_click": "point_and_click",
}


def _secao_do_mouse(prof: Any, ctx: Contexto, campos: dict[str, Any]) -> Any:
    """A seção `mouse` do perfil com o que este clique mudou, ou `None`.

    `None` = **não há o que gravar**: o perfil já diz isto (gravar de novo escreveria o mesmo
    arquivo a cada passagem do arraste) ou o daemon ainda não falou. A seção nasce com o que está
    VALENDO: `enabled` é obrigatório no `ProfileMouseConfig`, e a única coisa verdadeira é o estado
    vivo (inventar `False` faria o perfil DESLIGAR, na próxima ativação, emulação que estava
    ligada). Sem o bloco do daemon a seção não nasce: valor chutado valeria para todo jogo que casar
    com o perfil, para sempre.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileMouseConfig

    atual = getattr(prof, "mouse", None)
    if atual is not None:
        base = {"enabled": atual.enabled, "speed": atual.speed,
                "scroll_speed": atual.scroll_speed, "point_and_click": atual.point_and_click}
    else:
        vivo = _rato(ctx)
        if vivo.get("speed") is None and "point_and_click" not in campos:
            return None
        base = {"enabled": bool(vivo.get("enabled")),
                "speed": int(vivo.get("speed") or DEFAULT_MOUSE_SPEED),
                "scroll_speed": int(vivo.get("scroll_speed") or SCROLL_SPEED_MIN)}
    novo = {**base, **campos}
    if atual is not None and novo == base:
        return None
    return ProfileMouseConfig(**novo)


def _o_que_nao_guardou(nome: str) -> str:
    """A frase de quando o aparelho mudou e o perfil não guardou. Um dono."""
    if not nome:
        return ("mudei agora, mas não guardei: não há perfil ativo. "
                "Escolha um na aba Perfis.")
    return (f"mudei agora, mas não guardei: não consegui abrir o "
            f"perfil “{nome}” para gravar.")


def _guardar_no_perfil(ctx: Contexto, **campos: Any) -> str:
    """Grava o que ESTE clique mudou onde a marca do cartão diz. Disco, e nada mais.

    Aceita `teclado_emulado=`, `teclado_so_no_jogo=` e `teclado_sempre=` (lista «Função do
    teclado»), `tabela_no_jogo=` e os do rato (`mouse_speed`, `mouse_scroll`, `point_and_click`,
    ver `_DO_RATO`).

    :return: `""` quando gravou ou não havia o que gravar (o disco já dizia isso); senão a frase do
    que NÃO deu (sem perfil ativo, ou arquivo que não abre).

    Frase e não `RuntimeError`: o aparelho JÁ mudou (a chamada ao daemon vem antes e deu certo);
    levantar pintaria a RECUSA laranja sobre gesto que fez metade do que prometeu. Quem chama
    devolve a frase pelo canal de AVISO (`{"recado": …}`), no mesmo cartão com tom de sucesso.

    **O arraste chega duas vezes e grava uma**: o ouvinte do piloto escuta `change` **e** `click`, e
    soltar o polegar de um `<input type=range>` dispara os dois com o MESMO valor; a segunda
    passagem acha o disco igual, `_secao_do_mouse` devolve `None` e nada é escrito. O guarda é a
    IGUALDADE, não um relógio (mais forte que o `_so_abriu_o_seletor` da aba 04: cobre também
    arrastar e voltar ao valor de origem).
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    loader = perfil._com_o_src()
    if nome:
        try:
            loader.load_profile(nome)
        except Exception:
            return _o_que_nao_guardou(nome)

    def _com_o_que_mudou(prof: Any) -> Any:
        mudanca: dict[str, Any] = {}
        for campo in ("teclado_emulado", "teclado_so_no_jogo", "teclado_sempre", "tabela_no_jogo"):
            if campo in campos:
                quer = bool(campos[campo])
                if getattr(prof, campo, None) is not quer:
                    mudanca[campo] = quer
        do_rato = {_DO_RATO[k]: v for k, v in campos.items() if k in _DO_RATO}
        if do_rato:
            secao = _secao_do_mouse(prof, ctx, do_rato)
            if secao is not None:
                mudanca["mouse"] = secao
        return prof.model_copy(update=mudanca) if mudanca else None

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    cartao = "teclado" if "teclado_emulado" in campos else "mouse"
    try:
        gravar_pelo_gesto(cartao, nome, _com_o_que_mudou, origem="interface-nova")
    except (OSError, ValueError):
        return _o_que_nao_guardou(nome)
    return ""


def _numero_da_barra(o: dict[str, Any], oque: str) -> int:
    """O inteiro que a barra mandou, ou uma frase que chega ao cartão dela.

    O `data-hef-alvo="valor"` do `<input type=range>` faz o ouvinte mandar `valor: alvo.value`; um
    `<div>` não teria `value` e o gesto chegaria com a chave vazia (defeito que a aba Vibração
    nomeou em 03/09/2026 antes de o trilho virar `<input>`). `RuntimeError` e não `ValueError`
    porque o contrato do piloto leva a frase do primeiro ao cartão e deixa o segundo no `stderr`
    (`hefesto_vivo._recusou_dizendo`).
    """
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            f"{oque} ficou como estava. "
            "Arraste o cursor da barra em vez de clicar no rótulo ao lado.")
    try:
        return round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número — {oque} ficou "
            "como estava") from erro


def _recusa_do_mouse(resposta: Any) -> str:
    """A frase da recusa, TRADUZIDA, ou `""` quando o daemon aceitou.

    Traduz `app/actions/mouse_actions.frase_da_recusa_do_mouse` (cinco motivos, fallback honesto
    para motivo novo e recusa sem motivo). **A ponte entrega o corpo desde 01/09/2026**:
    `ponte.resultado` (`interface/pacotes/ponte.py`) devolve o `result` do daemon e levanta quando
    ninguém responde; um `{"status": "failed", "bloqueio": "sem_device"}` voltava como sucesso e a
    tela ficava sem uma palavra. `status` AUSENTE conta como aceito (`set_mouse_speed` responde
    `{"status": "ok", "enabled": …}` e só), senão toda troca de velocidade acusaria um "não" que não
    houve.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        frase_da_recusa_do_mouse,
    )

    if not isinstance(resposta, dict) or resposta.get("status") != "failed":
        return ""
    return frase_da_recusa_do_mouse(resposta)


def _recusa_do_teclado(resposta: Any) -> str:
    """O motivo de o teclado não ter ligado, do bloco que o próprio daemon devolve.

    `keyboard.emulation.set` responde com o bloco `keyboard_emulation` inteiro, *"para a janela não
    precisar de uma segunda chamada só para saber se o device subiu"* (`daemon/ipc_handlers.py`);
    quem o traduz é `emulation_actions.descrever_teclado_emulado`, o dono da linha de estado desta
    aba. Sem bloco e sem frase, diz-se só que ele recusou. A frase de "não sei" da GTK
    (`TECLADO_SEM_ESTADO`, *"o Hefesto pode estar desligado"*) NÃO serve: o Hefesto respondeu, ele é
    que disse não.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    bloco = resposta.get("keyboard_emulation") if isinstance(resposta, dict) else None
    if isinstance(bloco, dict) and isinstance(bloco.get("enabled"), bool):
        _posicao, frase = descrever_teclado_emulado(bloco)
        if frase:
            return frase
    return "o Hefesto recusou e não disse por quê"


def _velocidade(p: Any, o: dict[str, Any], campo: str,
                minimo: int, maximo: int, oque: str) -> int:
    """O corpo comum das duas barras de velocidade. `mouse.emulation.set`.

    Sem `enabled` de propósito: o handler atualiza a config e o device vivo sem start/stop e sem
    gravar o flag, o que impede ajuste de velocidade de RELIGAR a emulação e matar o gamepad virtual
    (BUG-MOUSE-GUI-SYNC-01). A barra manda o número inteiro; a faixa é a de `uinput_mouse`, e o
    daemon apara por último. O arraste chega duas vezes (`change` e `click`) e é inócuo.

    :return: o número que FOI ao daemon, já aparado; quem chama o leva ao perfil, nunca o do `ctx`
    (estado do tique anterior).
    """
    alvo = max(minimo, min(maximo, _numero_da_barra(o, oque)))
    _mandar(p, origin=MANUAL, **{campo: alvo})
    return alvo


def _mandar(p: Any, **params: Any) -> None:
    """`mouse.emulation.set`, e diz POR QUE quando o daemon recusa. `p.chamar` devolve `bool` e joga
    fora o corpo (era ele que trazia a recusa como sucesso); `p.resultado` traz o corpo e levanta
    quando ninguém responde, os dois desfechos a separar: *o Hefesto não falou* e *o Hefesto disse
    não, por isto*.
    """
    try:
        resposta = p.resultado("mouse.emulation.set", **params)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — a velocidade não mudou") from erro
    recusa = _recusa_do_mouse(resposta)
    if recusa:
        raise RuntimeError(recusa)


@gesto("06-navegacao.html", PERMITIR, grava="navegacao.big_picture.set")
def permitir_navegacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Permitir navegação»: Interna, Steam ou Uso geral (N5, 16/10/2026).

    Os três botões tomaram o lugar de «Quem navega» e «Tipo de navegação», e gravam nos MESMOS
    donos, da máquina e nunca do perfil: «Steam» liga o Big Picture; «Interna» e «Uso geral» o
    desligam e guardam o tipo da navegação (`navegacao.interna.set`, a Interna ou o computador).
    O interruptor do topo continua dono de ligar e desligar: nenhum dos três o toca.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip().lower()
    if escolhido not in DO_PERMITIR:
        raise ValueError(
            f"{PERMITIR}: não reconheci a opção escolhida ({escolhido!r}); as três são "
            + ", ".join(f"«{v}»" for v in DO_PERMITIR) + ".")
    _big_picture(p, escolhido == PERMITIR_STEAM)
    if escolhido == PERMITIR_STEAM:
        return None
    tipo = TIPO_INTERNA if escolhido == PERMITIR_INTERNA else TIPO_COMPUTADOR
    try:
        resposta = p.resultado("navegacao.interna.set", tipo=tipo, origin=MANUAL)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o tipo de navegação ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") != "ok":
        raise RuntimeError("o tipo de navegação ficou como estava")
    return None


@gesto("06-navegacao.html", "na-steam", grava="navegacao.big_picture.set")
def na_steam(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Na Steam»: o que a Steam navega. O Big Picture tem dono; o modo padrão da Steam não tem."""
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip().lower()
    if escolhido == NA_STEAM_PADRAO:
        raise RuntimeError(FRASE_DO_STEAM_PADRAO)
    if escolhido != NA_STEAM_BIG_PICTURE:
        raise ValueError(
            f"na-steam: não reconheci a opção escolhida ({escolhido!r}); as duas são "
            f"«{NA_STEAM_BIG_PICTURE}» e «{NA_STEAM_PADRAO}».")
    _big_picture(p, True)
    return None


def _big_picture(p: Any, ligado: bool) -> None:
    """Liga ou desliga o Modo Big Picture no daemon, e diz por que não deu."""
    try:
        resposta = p.resultado("navegacao.big_picture.set", ligado=ligado, origin=MANUAL)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o Big Picture ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") != "ok":
        raise RuntimeError("o Big Picture ficou como estava")


@gesto("06-navegacao.html", "point-and-click-perfil", grava="gravar_pelo_gesto")
def point_and_click_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O «Perfil jogo - navegação»: um molde ou um dos meus perfis, do computador.

    O valor é `molde:<chave>` (um dos moldes de `profiles.loader`) ou `perfil:<nome>`; guarda
    em `mouse.point_and_click`, onde moram as velocidades. O mapa dos botões mostra o que o perfil
    escolhido faz.
    """
    from hefesto_dualsense4unix.profiles import loader

    valor = str(o.get("valor") or o.get("rotulo") or "").strip()
    if valor.startswith(PREFIXO_DO_MOLDE):
        if valor[len(PREFIXO_DO_MOLDE):] not in loader.MOLDE_POR_CHAVE:
            raise ValueError(f"point-and-click-perfil: o molde {valor!r} não existe.")
    elif not (valor.startswith(PREFIXO_DO_PERFIL) and valor[len(PREFIXO_DO_PERFIL):].strip()):
        raise ValueError(
            f"point-and-click-perfil: {valor!r} não é um molde nem um perfil "
            f"(`{PREFIXO_DO_MOLDE}<chave>` ou `{PREFIXO_DO_PERFIL}<nome>`).")
    recado = _guardar_no_perfil(ctx, point_and_click=valor)
    return {"recado": recado} if recado else None


#: (teclado ligado, só dentro do jogo, sempre) de cada palavra da lista.
_ESCOLHA: dict[str, tuple[bool, bool, bool]] = {
    "fora": (True, False, False), "desativado": (False, False, False),
    "dentro": (True, True, False), "sempre": (True, False, True)}


@gesto("06-navegacao.html", "teclado", grava="gravar_pelo_gesto")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista «Função do teclado»: quatro palavras, e a escolha vira o perfil.

    «Só fora do jogo» liga o teclado; «Desativado» o desliga; «Só dentro do jogo» liga com
    `teclado_so_no_jogo`; «Sempre» liga com `teclado_sempre`, e o teclado digita com e sem jogo
    aberto (a supressão do usuário continua calando). O sinal do portão é travado pelo daemon a
    cada ativação, então mudar um dos dois campos manda reaplicar o perfil. Sem portão de modo: o
    teclado nunca derruba o gamepad virtual. Diz por que não deu, em vez de a lista voltar muda.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    palavras = {x.strip(".,;:—-").lower() for x in escolhido.split()}
    chaves = palavras & set(_ESCOLHA)
    if len(chaves) != 1:
        raise ValueError(
            f"teclado: não reconheci a opção escolhida ({escolhido!r}). Cada opção do "
            f"desenho traz exatamente uma destas palavras: {', '.join(sorted(_ESCOLHA))}.")
    ligar, so_dentro, sempre = _ESCOLHA[chaves.pop()]
    nome = perfil.nome_do_ativo(ctx.state).strip()
    antes = perfil.ativo_que_vale(nome) or {}
    mudou_o_portao = (bool(antes.get("teclado_so_no_jogo")) != so_dentro
                      or bool(antes.get("teclado_sempre")) != sempre)
    try:
        resposta = p.resultado("keyboard.emulation.set", enabled=ligar)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o teclado ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") == "failed":
        raise RuntimeError(
            f"o teclado ficou como estava: {_recusa_do_teclado(resposta)}")
    recado = _guardar_no_perfil(ctx, teclado_emulado=ligar, teclado_so_no_jogo=so_dentro,
                                teclado_sempre=sempre)
    if not recado and nome and mudou_o_portao:
        perfil.reaplicar(nome, ctx, p)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-cursor", grava="gravar_pelo_gesto")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade de cursor, arrastada. `mouse_emulation.speed`.

    Decisão de 05/09/2026: *"velocidade do cursor e da rolagem coloca um slicer pra cada"*. Os
    gestos `vel-cursor-menos`/`-mais` somavam ±1 ao número do ÚLTIMO TIQUE e saíram com os botões: a
    barra manda o número INTEIRO, sem de onde partir nem passo engolido a curar. A paridade com a
    janela GTK fechou junto: lá é um `Gtk.Scale` de `mouse_speed_adj` (`gui/main.glade`, 1..12,
    passo 1), a MESMA faixa, pois ambas leem o dono (`integrations/uinput_mouse.py`); ver
    `docs/data/paridade-gtk-html.csv`, linha "Velocidade do cursor".

    O alcance é o de um número só (medido em 01/09): `mouse_speed` move o analógico esquerdo **e** o
    cursor do touchpad (`emit_touchpad_move` escala por `TOUCHPAD_SENSITIVITY * (mouse_speed /
    DEFAULT_MOUSE_SPEED)`). Dura além da janela desde 05/09/2026 (decisão D2): o número ia ao daemon
    e ao `session.json`, e o perfil só o recebia no "Salvar" do rodapé, então fechar depois de
    arrastar perdia a escolha calada (`_guardar_no_perfil`).
    """
    alvo = _velocidade(p, o, "speed", MOUSE_SPEED_MIN, MOUSE_SPEED_MAX,
                       "a velocidade do cursor")
    recado = _guardar_no_perfil(ctx, mouse_speed=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-rolagem", grava="gravar_pelo_gesto")
def vel_rolagem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade da rolagem, arrastada. `scroll_speed`."""
    alvo = _velocidade(p, o, "scroll_speed", SCROLL_SPEED_MIN, SCROLL_SPEED_MAX,
                       "a velocidade da rolagem")
    recado = _guardar_no_perfil(ctx, mouse_scroll=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "linha-de-botao", grava="gravar_pelo_gesto")
def linha_de_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Uma das linhas de *o que cada botão faz*: a escolha é gravada na hora.

    Só a diferença do de fábrica vai a `Profile.button_actions` (o campo zerado é `None`, que
    herda), onde o cartão «Mouse» manda: o perfil quando ele já tem escolhas próprias, senão o
    computador. A recusa é de clique inválido: o rótulo desconhecido só chega se o desenho andou
    sem o gerador. O que o desenho oferece e o motor não atende sobe dito, nunca engolido.
    """
    botao = str(o.get("linha") or o.get("campo") or "").removeprefix(PREFIXO_DA_ACAO)
    if botao not in acoes.BOTOES:
        raise ValueError(
            f"linha-de-botao: o clique não disse qual botão (veio {botao!r}). O "
            "`data-linha` de cada `<select>` é o id do botão, e ele vem do gerador.")
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    if botao == "ps":
        return _a_linha_do_ps(ctx, p, rotulo)
    token = acoes.token_do_rotulo(rotulo)
    if token is None:
        raise ValueError(
            f"{_nome_do_botao(botao)}: a opção {rotulo!r} não é do produto. A lista da tela e "
            "a do produto saem de `core/acoes_de_botao.ACOES`.")
    _gravar_a_linha(ctx, p, botao, token)
    _, _, sem_dono = acoes.resolver({botao: token})
    if botao in sem_dono:
        raise RuntimeError(
            f"guardei, e {_nome_do_botao(botao)} fica sem quem o atenda — escolha outra ação.")
    return {"mesa": {f"{PREFIXO_DA_ACAO}{botao}": rotulo}}


def _gravar_a_linha(ctx: Contexto, p: Any, botao: str, token: str) -> None:
    """Grava no perfil o que a linha faz (só a diferença do de fábrica) e reaplica."""
    nome = perfil.nome_do_ativo(ctx.state).strip()
    de_fabrica = acoes.padrao()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    def _com_a_linha(prof: Any) -> Any:
        atuais = dict(prof.button_actions or {})
        if token == de_fabrica.get(botao):
            atuais.pop(botao, None)
        else:
            atuais[botao] = token
        novo = atuais or None
        if novo == prof.button_actions:
            return None
        return prof.model_copy(update={"button_actions": novo})

    try:
        gravar_pelo_gesto("mouse", nome, _com_a_linha, origem="interface-nova")
    except (OSError, ValueError) as erro:
        raise RuntimeError(
            f"não consegui guardar a linha {_nome_do_botao(botao)}: {erro}") from erro
    perfil.reaplicar(nome, ctx, p)


def _a_linha_do_ps(ctx: Contexto, p: Any, rotulo: str) -> dict[str, Any] | None:
    """A linha PS, o dono único do PS sozinho (N8, 16/10/2026).

    O PS sozinho tem duas camadas no daemon: a tecla do perfil (`button_actions["ps"]`, que vale
    quando o PS digita) e o ato da máquina (o gesto ⑥ do `maquina.json`). A lista junta as duas,
    e cada escolha deixa UMA valendo: o ato da máquina devolve a tecla do perfil ao de fábrica
    («sem tecla»); a tecla declara o ato «Nada»; o «— Nada —» cala as duas.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    ato = ag.token_do_rotulo(rotulo)
    if ato is not None:
        if not _declarar_o_gesto(ag.GESTO_DO_PS, rotulo, p):
            return None
        _gravar_a_linha(ctx, p, "ps", acoes.padrao()["ps"])
        _avisar_se_sem_saida_de_emergencia()
        return None
    token = acoes.token_do_rotulo(rotulo)
    if token is None or not _o_ps_digita(token):
        raise ValueError(
            f"PS: a opção {rotulo!r} não é do produto. A lista junta `core/acoes_do_gesto` e "
            "as teclas que o PS sabe digitar.")
    _gravar_a_linha(ctx, p, "ps", token)
    ok, motivo = _ok_e_motivo(p.machine_declare({"gestos": {ag.GESTO_DO_PS: {"faz": ag.NADA}}}))
    if not ok:
        raise RuntimeError(
            "guardei a tecla, e o ato do PS continua: " + (motivo or "o Hefesto não respondeu"))
    _esquecer_a_maquina()
    _avisar_se_sem_saida_de_emergencia()
    return {"mesa": {f"{PREFIXO_DA_ACAO}ps": rotulo}}


def _nome_do_ativo_ou_nada(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou ``""``."""
    return perfil.nome_do_ativo(ctx.state).strip()


@gesto("06-navegacao.html", "padrao-da-aba", grava="voltar_o_computador_ao_de_fabrica")
def padrao_da_aba(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O «Voltar ao padrão» da aba: o mouse e o teclado voltam UM DEGRAU."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.schema import ProfileMouseConfig

    nome = _nome_do_ativo_ou_nada(ctx)
    loader = perfil._com_o_src()
    cru = None
    if nome:
        try:
            cru = loader.load_profile(nome)
        except Exception:
            cru = None
    no_jogo = cru is not None and not opc.e_o_freestyle(cru.name)
    for cartao in ("mouse", "teclado"):
        if cru is not None and no_jogo and opc.sobrepoe(cru, cartao):
            opc.voltar_ao_do_computador(cartao, None, cru.name)
        else:
            opc.voltar_o_computador_ao_de_fabrica(cartao)
    if not no_jogo:
        ok, motivo = _ok_e_motivo(
            p.machine_declare({"gestos": dict.fromkeys(ag.TODOS_OS_GESTOS)}))
        if not ok:
            raise RuntimeError(
                "o mouse e o teclado voltaram, e os gestos não: "
                + (motivo or "o Hefesto não respondeu"))
        _esquecer_a_maquina()
    vista = opc.carregar_o_que_vale(nome) if no_jogo else None
    mouse = vista.mouse if vista is not None else None
    speed, scroll = opc.velocidades_do_computador()
    if mouse is not None:
        speed, scroll = mouse.speed, mouse.scroll_speed
    campos = ProfileMouseConfig.model_fields
    _mandar(p, origin=MANUAL,
            speed=speed if speed is not None else campos["speed"].default,
            scroll_speed=scroll if scroll is not None else campos["scroll_speed"].default)
    perfil.reaplicar(nome, ctx, p)


def _nome_na_troca(botao: str) -> str:
    """O nome da linha como a tela "Trocar os botões" o escreve."""
    rotulo = _rotulo_do_destino(botao)
    return rotulo if rotulo != botao else _nome_do_botao(botao)


def _frase_da_troca(exc: remap.RemapeamentoRecusadoError) -> str:
    """A recusa do motor, com os nomes que ela lê na tela."""
    if exc.motivo == remap.MOTIVO_COLISAO:
        *origens, destino = exc.botoes
        return (
            "não guardei: " + " e ".join(_nome_na_troca(b) for b in origens)
            + f" passam a ser o mesmo botão, {_nome_na_troca(destino)} — cada "
              "botão do jogo recebe uma linha só.")
    nomes = ", ".join(_nome_na_troca(b) for b in exc.botoes)
    if exc.motivo == remap.MOTIVO_PS:
        return (f"não guardei: o PS não se troca, nem troca outro botão ({nomes})"
                " — os gestos desta aba começam nele, e ele é a saída de "
                "emergência.")
    if exc.motivo == remap.MOTIVO_FORA:
        return (f"não guardei: {nomes} — a direção dos analógicos e o clique do "
                "touchpad ficam fora da troca de botões.")
    return f"não guardei: a troca traz um botão desconhecido ({nomes})."


#: Os gestos cujo efeito o daemon não publica no estado do tique: a linha de botão e o perfil de
#: point and click são do disco (perfil e `maquina.json`), sem eco.
SEM_ECO = ("linha-de-botao", "point-and-click-perfil")

SEM_GESTO: dict[str, str] = {}

PONTE = {"chamar", "machine_declare", "escolher_arquivo", "profile_reaplicar"}
METODOS = {"mouse.emulation.set", "keyboard.emulation.set", "machine.declare",
           "navegacao.interna.set", "navegacao.big_picture.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 8


def _prova(nome: str, clique: dict[str, Any], chama: list[Any]) -> dict[str, Any]:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez."""
    return {"pagina": PAGINA, "gesto": nome,  # (noqa-acento) chave do contrato
            "clique": clique, "chama": chama}


_MOUSE = "mouse.emulation.set"
_BIG_PICTURE = "navegacao.big_picture.set"
PROVAS = [
    _prova(PERMITIR, {"valor": PERMITIR_STEAM},
           [("resultado", [_BIG_PICTURE], {"ligado": True, "origin": "manual"})]),
    _prova(PERMITIR, {"valor": PERMITIR_INTERNA},
           [("resultado", [_BIG_PICTURE], {"ligado": False, "origin": "manual"}),
            ("resultado", ["navegacao.interna.set"],
             {"tipo": TIPO_INTERNA, "origin": "manual"})]),
    _prova(PERMITIR, {"valor": PERMITIR_USO_GERAL},
           [("resultado", [_BIG_PICTURE], {"ligado": False, "origin": "manual"}),
            ("resultado", ["navegacao.interna.set"],
             {"tipo": TIPO_COMPUTADOR, "origin": "manual"})]),
    _prova("na-steam", {"valor": NA_STEAM_BIG_PICTURE},
           [("resultado", [_BIG_PICTURE], {"ligado": True, "origin": "manual"})]),
    _prova("vel-cursor", {"valor": "9"},
           [("resultado", [_MOUSE], {"speed": 9, "origin": "manual"})]),
    _prova("vel-cursor", {"valor": "99"},
           [("resultado", [_MOUSE], {"speed": MOUSE_SPEED_MAX, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "4"},
           [("resultado", [_MOUSE], {"scroll_speed": 4, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "0"},
           [("resultado", [_MOUSE], {"scroll_speed": SCROLL_SPEED_MIN, "origin": "manual"})]),
    _prova("teclado", {"valor": TECLADO_SO_FORA},
           [("resultado", ["keyboard.emulation.set"], {"enabled": True})]),
    # «Sempre» troca o portão do perfil, e o daemon só o lê ao ativar: reaplica.
    _prova("teclado", {"valor": TECLADO_SEMPRE},
           [("resultado", ["keyboard.emulation.set"], {"enabled": True}),
            ("profile_reaplicar", ["regua"], {}),
            ("chamar", ["launch_env.refresh"], {})]),
    _prova("teclado", {"valor": TECLADO_DESATIVADO},
           [("resultado", ["keyboard.emulation.set"], {"enabled": False})]),
    _prova("acao-do-gesto", {"linha": "ps_l3", "rotulo": "— Nada —", "valor": "— Nada —"},
           [("machine_declare", [{"gestos": {"ps_l3": {"faz": "nada"}}}], {})]),
    _prova("novo-gesto", {"b": "triangle"},
           [("machine_declare", [{"gestos": {"ps_triangle": {"faz": "nada"}}}], {})]),
    _prova("remover-gesto", {"linha": "ps_cross"},
           [("machine_declare", [{"gestos": {"ps_cross": None}}], {})]),
]

PREFIXO_DO_GESTO = "faz-"
PREFIXO_DO_SCRIPT = "script-"

TITULO_DO_SELETOR_DO_SCRIPT = "Escolher um script"
FILTRO_DO_SCRIPT = "*.sh"

_A_MAQUINA: Any = None
_SELO_DA_MAQUINA: Any = None


def _selo_da_maquina() -> tuple[int, int, int] | None:
    """`(inode, mtime_ns, tamanho)` do `maquina.json`: a mesma regra da 08."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

        st = caminho_da_maquina().stat()
    except Exception:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def _a_maquina() -> Any:
    """O `maquina.json` validado, RELIDO QUANDO O ARQUIVO MUDA (um `stat` por tique)."""
    global _A_MAQUINA, _SELO_DA_MAQUINA
    selo = _selo_da_maquina()
    if _A_MAQUINA is None or selo != _SELO_DA_MAQUINA:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            _A_MAQUINA, _SELO_DA_MAQUINA = carregar_maquina(), selo
        except Exception:
            return None
    return _A_MAQUINA


def _esquecer_a_maquina() -> None:
    """A próxima pintura relê o `maquina.json` (a declaração acabou de mudá-lo)."""
    global _A_MAQUINA
    _A_MAQUINA = None


def _o_que_os_gestos_fazem() -> dict[str, str]:
    """As listas da tabela, a opção do script de cada uma, as linhas que valem e os botões livres.

    A tabela tem uma linha por gesto com combo, os de fábrica e os novos (`TODOS_OS_GESTOS`): a
    que não vale (o de fábrica removido, o novo não declarado) fica escondida por `vale-<chave>`.
    O PS sozinho não tem linha: só o script dele, que mora na lista da linha PS de «Os botões».
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    maquina = _a_maquina()
    escolhas = ag.tabela(maquina)
    ativos = ag.gestos_ativos(maquina)
    fora: dict[str, str] = {}
    for chave in ag.TODOS_OS_GESTOS:
        escolha = escolhas.get(chave) or ag.EscolhaDoGesto(ag.NADA)
        fora[PREFIXO_DO_SCRIPT + chave] = (
            ag.nome_do_script(escolha.script) if escolha.faz == ag.SCRIPT and escolha.script
            else ag.rotulo(ag.SCRIPT))
        if chave == ag.GESTO_DO_PS:
            continue
        fora[PREFIXO_DO_GESTO + chave] = ag.rotulo_da_escolha(escolha)
        fora[PREFIXO_DA_VALIDADE + chave] = "sim" if chave in ativos else "nao"  # noqa-acento: chave ASCII
    for botao in ag.BOTOES_DA_ESCOLHA:
        if botao in ag.BOTOES_PROIBIDOS:
            continue
        fora[PREFIXO_DA_LIBERDADE + botao] = (
            "sim" if ag.botao_livre(maquina, botao) else "nao")  # (noqa-acento) valor do atributo
    return fora


def _o_que_o_ps_faz(p: dict[str, Any] | None, da_linha: str) -> str:
    """O rótulo da linha PS: a tecla do perfil quando o PS digita, senão o ato da máquina."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    perfil_ = p or {}
    token = acoes.tabela_efetiva(
        perfil_.get("button_actions") or None, perfil_.get("key_bindings") or None).get("ps")
    if token and token != acoes.padrao()["ps"] and _o_ps_digita(str(token)):
        return da_linha
    escolha = ag.tabela(_a_maquina()).get(ag.GESTO_DO_PS) or ag.EscolhaDoGesto(ag.NADA)
    return ag.rotulo_da_escolha(escolha)


def _ok_e_motivo(resposta: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu (a régua usa `bool`)."""
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


def _avisar_se_sem_saida_de_emergencia() -> None:
    """Depois de guardar, diz quando nenhum gesto que vale faz a saída de emergência do PS.

    Suspender mouse e teclado e Próximo modo tiram o computador das mãos do controle; a troca que
    deixa as duas sem gesto é guardada e responde, no desfecho que a linha já tem. O de fábrica
    removido não conta: guarda o que fazia, mas não dispara. O PS sozinho conta.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    maquina = _a_maquina()
    ativos = ag.gestos_ativos(maquina)
    valem = {c: e for c, e in ag.tabela(maquina).items() if c == ag.GESTO_DO_PS or c in ativos}
    faltam = ag.saidas_sem_gesto(valem)
    if len(faltam) == len(ag.SAIDAS_DE_EMERGENCIA):
        nomes = " nem ".join(ag.rotulo(t) for t in faltam)
        raise RuntimeError(
            f"guardei, e nenhum gesto do PS faz {nomes}, a saída de emergência — "
            "escolha um deles em algum gesto.")


@gesto("06-navegacao.html", "acao-do-gesto", grava="machine_declare")
def acao_do_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Uma das seis listas da tabela: grava na MÁQUINA o que o gesto faz.

    `data-linha` diz qual gesto (chaves de `acoes_do_gesto.GESTOS`); a página publicada antes desta
    sprint não o tem, e o clique recusa como antes. O rótulo vira token pelo dono do vocabulário.
    «Escolher um script…» (ou o nome de um já escolhido) abre o seletor do sistema
    (`D-2909-O-SCRIPT-E-UM-ARQUIVO-ESCOLHIDO`): cancelar não grava e a pintura devolve a lista ao
    que era; o arquivo é conferido aqui (`conferir_o_script`) e de novo pelo daemon na hora de
    rodar. A recusa pisca na lista e a frase vai ao diário.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    qual = str(o.get("linha") or "").strip()
    if qual not in ag.TODOS_OS_GESTOS:
        raise ValueError(f"a lista não disse de qual gesto ela é ({qual!r})")
    if _declarar_o_gesto(qual, str(o.get("rotulo") or o.get("valor") or "").strip(), p):
        _avisar_se_sem_saida_de_emergencia()
    return None


def _declarar_o_gesto(qual: str, texto: str, p: Any) -> bool:
    """Declara na máquina o que o gesto faz; ``False`` quando o seletor do script foi cancelado."""
    import os

    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    declarado: dict[str, Any] = {}
    faz = ag.token_do_rotulo(texto)
    if faz is None or faz == ag.SCRIPT:
        caminho = p.escolher_arquivo(TITULO_DO_SELETOR_DO_SCRIPT, padrao=FILTRO_DO_SCRIPT)
        if not caminho:
            return False
        real = os.path.realpath(str(caminho))
        motivo = ag.conferir_o_script(real)
        if motivo is not None:
            raise RuntimeError(f"Não dá para usar {ag.nome_do_script(real)}: {motivo}.")
        declarado = {"faz": ag.SCRIPT, "script": real}
    else:
        declarado = {"faz": faz}
    if qual != ag.GESTO_DO_PS and ag.removido(_a_maquina(), qual):
        declarado["removido"] = True
    ok, motivo_da_recusa = _ok_e_motivo(p.machine_declare({"gestos": {qual: declarado}}))
    if not ok:
        raise RuntimeError(motivo_da_recusa or "Não consegui guardar o que o gesto faz.")
    _esquecer_a_maquina()
    return True


@gesto("06-navegacao.html", "novo-gesto", grava="machine_declare")
def novo_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«+ Gesto»: o PS com o botão escolhido vira uma linha da tabela, fazendo «Nada».

    Só o botão livre se escolhe (`acoes_do_gesto.botao_livre`): o proibido e o já usado chegam
    desligados na tela, sem texto, e a recusa aqui é a do clique que pulou a tela. O botão de um
    gesto de fábrica removido devolve aquele gesto, com o que ele fazia.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    botao = str(o.get("b") or "").strip()
    maquina = _a_maquina()
    chave = ag.gesto_do_botao(botao)
    if chave is None or not ag.botao_livre(maquina, botao):
        raise ValueError(f"o PS + {botao!r} não está livre para virar gesto")
    if chave in ag.GESTOS:
        escolha = ag.tabela(maquina)[chave]
        declarado: dict[str, Any] = {"faz": escolha.faz, "removido": False}
        if escolha.script:
            declarado["script"] = escolha.script
    else:
        declarado = {"faz": ag.NADA}
    ok, motivo = _ok_e_motivo(p.machine_declare({"gestos": {chave: declarado}}))
    if not ok:
        raise RuntimeError(motivo or "Não consegui acrescentar o gesto.")
    _esquecer_a_maquina()
    return None


@gesto("06-navegacao.html", "remover-gesto", grava="machine_declare")
def remover_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O botão de tirar da linha: o gesto sai da tabela e deixa de disparar.

    O de fábrica guarda o que fazia, marcado `removido` (volta pelo «+ Gesto» com o mesmo botão);
    o novo é esquecido. O PS sozinho não tem esse botão: o dono dele é a linha PS de «Os botões».
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    chave = str(o.get("linha") or "").strip()
    if chave not in ag.TODOS_OS_GESTOS or chave == ag.GESTO_DO_PS:
        raise ValueError(f"o botão de tirar não disse qual gesto sai ({chave!r})")
    declarado: dict[str, Any] | None = None
    if chave in ag.GESTOS:
        escolha = ag.tabela(_a_maquina())[chave]
        declarado = {"faz": escolha.faz, "removido": True}
        if escolha.script:
            declarado["script"] = escolha.script
    ok, motivo = _ok_e_motivo(p.machine_declare({"gestos": {chave: declarado}}))
    if not ok:
        raise RuntimeError(motivo or "Não consegui tirar o gesto.")
    _esquecer_a_maquina()
    _avisar_se_sem_saida_de_emergencia()
    return None
