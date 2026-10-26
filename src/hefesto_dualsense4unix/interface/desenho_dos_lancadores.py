#!/usr/bin/env python3
"""O DESENHO dos cartões da aba Lançadores — um só, para o gerador e o pacote.

Existe porque o gerador `aba07.py` escrevia os seis cartões com os números DIGITADOS (`412 jogos`,
`28 jogos`, `3 jogos já sabem por onde entrar`) e o produto não tinha por onde contradizê-los.
Medido em 02/09/2026 com o `censo_do_wrapper`:

    o HTML afirmava   Steam · 412 jogos · 3 já sabem por onde entrar
    o produto responde  63 appids com o wrapper no vdf, 23 jogos instalados,
                        0 faltantes, 0 com ponte confirmada

É o defeito que ela mediu ao abrir o produto: *"basicamente todas as telas são mockups e estão com
informações incorretas ou desatualizadas ou não integradas de fato."*
<!-- noqa-acento: citação literal -->

A cura é dar ao desenho UMA fonte (o mesmo arranjo de `interface/conexoes.html_do_mapa`, cuja página
regerada saiu byte a byte igual à aprovada); dois donos do mesmo cartão e o segundo envelhece
calado:

    aba07.py (gerador)  →  a lista de REFERÊNCIA, que o usuário aprovou  →  mockup/
    a07_lancadores.py   →  o que o produto MEDE, a cada tique      →  a tela

**Não importa MOTOR nenhum**: é importado pelo gerador (script solto, `python3 aba07.py`) e pelo
pacote (dentro da janela), e dependência pesada atravessaria para os dois. Importa só DOIS módulos
de `integrations/` (o censo e a leitura das caixas do Flatpak; eram três até 10/09/2026, a
`cura_por_estrada` saiu com o botão «Consertar» do cartão LOCALIZADO, LANCADOR-LOCALIZAR-01):
`pathlib`, `json` e `configparser`, que respondem o que o CARTÃO mostra, sem daemon, GTK nem IPC. A
regra que fica: o gerador roda SOLTO, e import novo que quebre `python3 aba07.py` não pertence aqui.

**O disco não se abre na pintura** (09/09/2026): os três de `integrations/` são chamados por
:func:`medir_no_disco`, que BLOQUEIA e é da vigia do pacote; :func:`cartoes` recebe a resposta fria
(:class:`DoDisco`) e não abre arquivo. O `pathlib` do topo é ANOTAÇÃO (o `lar` de mentira da régua é
um `Path`).
"""
from __future__ import annotations

import dataclasses
import html
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as _censo
from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa

SELOS = {
    "ok": "CHEGAM",
    "warn": "COM IMPEDIMENTO",
    "off": "NÃO LOCALIZADO",
    "nao_sei": "NÃO SEI",
    "localizado": "LOCALIZADO",
}

MOLDURA = {"ok": "chega", "warn": "impede", "off": "ausente",
           "nao_sei": "ausente", "localizado": "chega"}

CLASSE_DA_GRADE = "lancadores"
SELETOR_DA_GRADE = f".{CLASSE_DA_GRADE}"


@dataclass(frozen=True)
class Acao:
    """Um botão do cartão. `gesto` vazio = botão sem endereço (só desenho)."""

    rotulo: str
    classe: str = ""
    gesto: str = ""
    v: str = ""
    href: str = ""
    dica: str = ""


@dataclass(frozen=True)
class Lancador:
    """UM cartão. É o contrato entre o gerador e o pacote."""

    chave: str
    nome: str
    selo: str
    jogos: str
    diz: str
    acoes: tuple[Acao, ...] = ()
    carimbo: str = ""
    fora: str = ""
    tem_lista: bool = False
    presente: bool = False


_DURO = "\u00a0"


def _e(txt: object) -> str:
    """Escapa para HTML **em posição de TEXTO**. O nome do jogo vem do DISCO do usuário.

    `appmanifest` com `&` ou `<` quebraria a marcação (conteúdo de terceiro, como o rótulo do
    aparelho em `interface/conexoes`).

    O `quote=False` impede um LAÇO INFINITO: o piloto só reescreve quando `innerHTML !== valor`
    (`hefesto_vivo.py:263` no campo, `:944` no bloco), comparações de TEXTO LITERAL cujo lado
    esquerdo é o que o DOM **devolve**; se a grafia emitida não for a que o DOM devolve, a
    comparação nunca casa. Medido no WebKit da janela do usuário em 02/09/2026 (`<div>` solto,
    `innerHTML` de ida e volta, seis caracteres nas duas grafias, 28 casos):

        ==========  ==================  ==================
        caractere   em TEXTO            em ATRIBUTO
        ==========  ==================  ==================
        ``&``       ``&amp;``           ``&amp;``
        ``<``       ``&lt;``            ``&lt;``
        ``>``       ``&gt;``            ``&gt;``
        U+00A0      ``&nbsp;``          ``&nbsp;``
        ``"``       **cru**             ``&quot;``
        ``'``       **cru**             **cru**
        ==========  ==================  ==================

    `html.escape(quote=True)` emite `&#x27;` e `&quot;`, e o DOM devolve os dois CRUS no texto: um
    jogo com apóstrofo no nome (a biblioteca do usuário tem 63) faria a lista e a grade serem
    reescritas duas vezes por segundo, para sempre, matando o foco e o `:hover`. A régua dela saiu
    com a grade da 07 antiga em 18/10/2026; desde 06/09/2026 (A-TELA-SAMBA-01) o piloto compara
    o bloco com o que ele mesmo escreveu, e não com o `innerHTML`.
    """
    return html.escape(str(txt if txt is not None else ""),
                       quote=False).replace(_DURO, "&nbsp;")


def _a(txt: object) -> str:
    """Escapa para HTML **em posição de ATRIBUTO** — o `_e` mais a aspa.

    Obrigatória nos dois sentidos: dentro de atributo com aspas duplas a aspa crua FECHA o atributo
    (medido: `data-v="a"b"` volta do DOM como dois atributos) e um `&#x27;` volta cru. Todo atributo
    deste módulo usa aspas duplas, o que faz a tabela de :func:`_e` o contrato inteiro; `<` e `>`
    seguem escapados porque o WebKit os devolve escapados também no atributo.
    """
    return _e(txt).replace('"', "&quot;")


def selo_html(selo: str) -> str:
    """O selo com a CLASSE certa — por isso é pintado como `html`.

    A pintura do piloto escreve `textContent`, que não troca a cor: de `CHEGAM` (verde) para `NÃO
    SEI` ficaria a palavra nova com o verde velho. O `data-hef-alvo="html"` do esqueleto existe para
    isso, e o alvo é o INVÓLUCRO (o `<span>` com a classe entra no innerHTML).
    """
    if selo not in SELOS:
        raise KeyError(
            f"selo {selo!r} não existe. Os que existem estão em `SELOS`, e "
            f"inventar um aqui deixaria o cartão sem cor — a única coisa que "
            f"esta aba mostra sem ler.")
    return f'<span class="lanc-selo {selo}">{SELOS[selo]}</span>'


def carimbo_html(texto: str) -> str:
    """O carimbo verde, ou VAZIO. Vazio some do cartão, e é o certo."""
    return f'<span class="carimbo">◆ {_e(texto)}</span>' if texto else ""


POR_JOGO = ("heroic",)


def sem_o_ambiente_html(chave: str, onde: tuple[str, ...]) -> str:
    """A linha do cartão em que o ambiente do Hefesto falta — vazia quando não.

    Mesma forma do «N jogos sem o atalho» da Steam, pela estrada dela: o selo vira `COM IMPEDIMENTO`
    e quem aplica é o «Aplicar soluções nos lançadores» da aba Sistema (ou a próxima troca de
    controle).
    """
    if not onde:
        return ""
    if chave in POR_JOGO:
        return f"<b>{_plural(len(onde), 'jogo', 'jogos')} sem o ambiente do Hefesto</b>"
    return "<b>Sem o ambiente do Hefesto</b>"


def contador_html(pontes: int) -> str:
    """O contador do corpo do cartão — o MESMO nos oito, zero inclusive.

    21/09/2026, palavra de produto: *"falta o mesmo textinho de contador da steam pros demais. (…)
    todos tem que serem iguais."* Era o carimbo da fileira da Steam; agora abre o corpo de todo
    cartão LOCALIZADO, onde os outros sete tinham espaço vazio (sem custo de altura). O zero aparece
    (a regra *"zero some"* caiu com o pedido).

    `pontes` é quantos jogos DAQUELE lançador já têm ponte confirmada num perfil
    (`prontuario_dos_jogos`): a Steam pelo appid, os outros pela classe da janela de cada jogo da
    biblioteca (:meth:`DoDisco.pontes_de`).
    """
    return carimbo_html(
        f"{_plural(pontes, 'jogo já sabe', 'jogos já sabem')} por onde entrar")


def acao_html(a: Acao) -> str:
    """Um botão. Sem `gesto`, nasce SEM endereço, por decisão.

    Regra da casa: *"o que NÃO tem dono não vira botão que finge"*. `data-gesto` num botão que
    ninguém atende faz o piloto recusar dizendo o nome (honesto); num botão que o produto não sabe
    fazer seria pior, com a recusa só no terminal e o clique sumindo na tela.
    """
    classe = f"btn {a.classe}".strip()
    endereco = f' data-gesto="{_a(a.gesto)}"' if a.gesto else ""
    valor = f' data-v="{_a(a.v)}"' if a.v else ""
    dica = f' title="{_a(a.dica)}"' if a.dica else ""
    if a.href:
        return (f'<a class="{classe}" href="{_a(a.href)}"'
                f'{endereco}{valor}{dica}>{_e(a.rotulo)}</a>')
    return f'<button class="{classe}"{endereco}{valor}{dica}>{_e(a.rotulo)}</button>'


FILEIRA_VAZIA = "<!-- nada a oferecer neste cartão -->"

SEM_LISTA = "<!-- ainda não há lista para este cartão -->"

SEM_FRASE = "<!-- a primeira leitura da Steam ainda não voltou -->"

LISTA_VAZIA = "<!-- nenhum jogo pendente, tirado ou dispensado na Steam -->"


def acoes_html(lanc: Lancador) -> str:
    """A fileira de botões DO CARTÃO, com o carimbo no fim dela.

    É pintada INTEIRA: no cartão da Steam os botões MUDAM com o estado (`Consertar` só existe quando
    há o que consertar); estática, ou o `Consertar` ficaria aceso sobre biblioteca em ordem, ou não
    existiria no dia em que a Steam comesse a linha. O carimbo vai aqui dentro porque, como linha
    própria, custava 21 px que só a Steam pagava.

    A quebra de linha e o recuo são PARTE DO VALOR (medido na tela em 02/09/2026, piloto por 40 s):
    o gerador escrevia ``<div class="acoes">\\n{acoes_html}\\n        </div>`` e o pacote pintava
    ``acoes_html`` **sem** a moldura de espaço; as duas grafias do mesmo valor divergiam e, com a
    grade repintada como bloco, viraram PING-PONG (o bloco reescrevia com o espaço, o campo sem;
    **81 de 81 voltas**, 2 por segundo, destruindo foco e `:hover`). Com o espaço DENTRO do valor a
    página sai byte a byte igual à de antes e as grafias são uma só
    (`test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa`).
    """
    botoes = "\n".join(f"          {acao_html(a)}" for a in lanc.acoes)
    carimbo = carimbo_html(lanc.carimbo)
    if not botoes and not carimbo:
        miolo = FILEIRA_VAZIA
    else:
        miolo = f"{botoes}\n          {carimbo}" if carimbo else botoes
    return f"\n{miolo}\n        "


def um_cartao(lanc: Lancador) -> str:
    """O cartão inteiro, com os endereços que o pacote pinta.

    Quatro endereços por cartão, e o quinto só onde há lista. Todos com o prefixo da `chave`: a
    página tem seis cartões e um `data-campo="selo"` sozinho seria pintado nos seis com o mesmo
    valor (o que a distribuição de lista do piloto faz de propósito).
    """
    k = _a(lanc.chave)
    acoes = (f'<div class="acoes" data-campo="{k}-acoes" '
             f'data-hef-alvo="html">{acoes_html(lanc)}</div>')
    lista = (
        f'\n        <div class="lanc-fora" data-campo="{k}-fora" '
        f'data-hef-alvo="html">{lanc.fora}</div>'
        if lanc.tem_lista else ""
    )
    return f'''      <div class="lanc {MOLDURA[lanc.selo]}" data-lancador="{k}">
        <div class="lanc-topo">
          <span class="lanc-nome">{_e(lanc.nome)}</span>
          <span data-campo="{k}-selo" data-hef-alvo="html">{selo_html(lanc.selo)}</span>
          <span class="lanc-jogos" data-campo="{k}-jogos">{_e(lanc.jogos)}</span>
        </div>
        <div class="lanc-diz" data-campo="{k}-diz" data-hef-alvo="html">{lanc.diz}</div>
        {acoes}{lista}
      </div>'''


def cartoes_html(lancadores: list[Lancador]) -> str:
    """A grade inteira. Usada pelo gerador; o pacote pinta campo a campo."""
    return "\n".join(um_cartao(x) for x in lancadores)


NOVO_SEM_ALVO = "Um lançador ou emulador que você usa"

NOVO_PARA_O_CARTAO = "{nome} — onde ele está nesta máquina"


DICA_DO_NOVO = (
    "Diga o comando, o caminho do programa (é assim que entra um AppImage solto) ou o nome do "
    "atalho — os três exemplos estão no campo. Confiro no disco antes de guardar.")


def tela_do_registro_html(para_quem: str = NOVO_SEM_ALVO) -> str:
    """A pop-up em que ela diz onde o lançador está. Sem uma linha de script.

    Abre por `:target` (`monta.CSS_POPUP`, o mecanismo das cinco pop-ups das abas 06 e 08): o botão
    é uma âncora para o `id` daqui, e o fechar e o `Cancelar` são âncoras para `#`; um segundo
    mecanismo seria o vocabulário que o `CSS_POPUP` subiu para o `monta.py` para não existir.

    **Dois campos, e o segundo é o mínimo**: o nome é o rótulo do cartão; o produto precisa do
    comando ou caminho, e quem chega pelo botão de um cartão não precisa nem do primeiro. **O
    segundo tem duas portas** (10/09/2026, decisão de produto, opção C): ao lado do campo está
    :data:`PROCURAR_O_ARQUIVO_ROTULO`, que abre o seletor do sistema para apontar o `.desktop`; **o
    campo FICA** porque um AppImage solto não tem `.desktop` e é o caso que a frase do cartão
    promete cobrir.

    O `href` do botão é o `id` desta caixa, não `#`: um `#` mudaria o `:target` e FECHARIA a pop-up
    no clique que abre o seletor. O glifo de fechar vai como entidade (`&times;`) por LINT: os
    `aba*.py` têm isenção de `RUF001`/`RUF002` no `pyproject.toml` e este módulo, o desenho
    compartilhado, não; a régua estrita impede caractere ambíguo num valor que o produto compara.

    A caixa de texto não tem `data-campo` (ver :data:`NOVO_ALVO`): o piloto recolhe `data-linha` e
    pinta só a linha de cima, texto do produto. O título não é o rótulo de nenhum dos dois botões
    (ver :data:`TELA_DO_NOVO_TITULO`): a caixa é UMA com dois caminhos, e titulá-la pela palavra de
    um faria metade das aberturas contradizer a linha abaixo.

    **O «?» encurtou em 11/09/2026 — A2-033, aprovada pelo usuário: 403 → 165.** O parágrafo do meio
    era a dica do campo em prosa (o `placeholder` já mostra `emulador · /opt/Emulador/emulador ·
    org.exemplo.Emulador`) e o de cima descrevia como o produto PROCURA, mecânica dita de novo pela
    recusa de `_achar_o_que_ela_digitou` quando serve. Sobrou o que ela precisa antes de digitar: o
    que vale, e que o produto confere antes de guardar.
    """
    return f'''<div class="tela-nova" id="{TELA_DO_NOVO}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit" data-dica="{_a(DICA_DO_NOVO)}">{_e(TELA_DO_NOVO_TITULO)}</span>
      <a class="tn-x" href="#" title="Fechar">&times;</a>
    </div>
    <div class="tn-corpo">
      <div class="lanc-novo-para" data-campo="{NOVO_PARA_QUEM}">{_e(para_quem)}</div>
      <label class="lanc-novo-campo">
        <span>Como ele se chama</span>
        <input type="text" data-linha="{NOVO_ROTULO}" placeholder="Meu emulador">
      </label>
      <label class="lanc-novo-campo">
        <span>Onde ele está</span>
        <div class="lanc-novo-linha">
          <input type="text" data-linha="{NOVO_ALVO}"
                 placeholder="Emulador  ·  /opt/emulador/emulador  ·  org.exemplo.emulador">
          <a class="btn" href="#{TELA_DO_NOVO}"
             data-gesto="{_a(PROCURAR_O_ARQUIVO)}"
             data-hef-forma="{_a(TELA_DO_NOVO)}"
             >{_e(PROCURAR_O_ARQUIVO_ROTULO)}</a>
        </div>
      </label>
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="{_a(ADICIONAR)}"
         data-hef-forma="{_a(TELA_DO_NOVO)}">Adicionar</a>
    </div>
  </div>
</div>'''


def valores_do_cartao(lanc: Lancador) -> dict[str, str]:
    """O que o PACOTE emite para aquele cartão — os mesmos endereços de cima.

    Escrito aqui, não no pacote, para que os dois lados não divirjam: endereço acrescentado em
    `um_cartao` e esquecido daqui deixa um campo com o valor do desenho para sempre (a régua da aba
    cobra).
    """
    fora = {
        f"{lanc.chave}-selo": selo_html(lanc.selo),
        f"{lanc.chave}-jogos": lanc.jogos,
        f"{lanc.chave}-diz": lanc.diz,
        f"{lanc.chave}-acoes": acoes_html(lanc),
    }
    if lanc.tem_lista:
        fora[f"{lanc.chave}-fora"] = lanc.fora
    return fora


@dataclass(frozen=True)
class JogoNaLista:
    """Uma linha da lista de jogos dentro do cartão."""

    appid: str
    rotulo: str
    porque: str
    gesto: str = ""
    botao: str = ""


def linhas_de_jogos(itens: list[JogoNaLista]) -> str:
    """A lista de jogos do cartão, ou `""` sem jogo nenhum.

    O `data-v` de cada linha é o APPID, não o rótulo: dois jogos podem ter o mesmo nome (demo e
    jogo) e `rotulo_do_jogo` cai para `appid NNNN` quando o manifesto sumiu; clicar por nome tiraria
    o wrapper do jogo errado (como a Conexões, que endereça pelo `nome_do_kernel`).
    """
    if not itens:
        return ""
    linhas = []
    for j in itens:
        botao = (
            f'<button class="btn mini" data-gesto="{_a(j.gesto)}" '
            f'data-v="{_a(j.appid)}">{_e(j.botao)}</button>'
            if j.gesto else ""
        )
        linhas.append(
            f'<div class="lanc-jogo"><span class="lanc-jogo-nome">{_e(j.rotulo)}</span>'
            f'<span class="lanc-jogo-porque">{_e(j.porque)}</span>{botao}</div>'
        )
    return "".join(linhas)


def conta_html(achados: int, impedidos: int) -> str:
    """A contagem do quadro: `N encontrados · M com impedimento`.

    Derivada da lista de cartões que o produto montou, não da que o gerador digitou (a aba dizia "6
    encontrados" contando o cartão que ela mesma carimba `NÃO ACHEI`).
    """
    return (f'{_plural(achados, "localizado", "localizados")} '
            f'<span class="sep">·</span> '
            f'{_plural(impedidos, "com impedimento", "com impedimentos")}')


SUFIXOS = ("-selo", "-jogos", "-diz", "-acoes")
SUFIXO_DA_LISTA = "-fora"


@dataclass(frozen=True)
class SemCenso:
    """Um lançador cujo INTERIOR o produto não sabe ler — e onde procurá-lo.

    Dois saberes separados (confundi-los é o defeito que este arquivo nasceu para curar): *"sei ler
    a biblioteca dele"* e *"ele está instalado aqui"*. O produto responde a SEGUNDA de graça: um
    lançador instalado publica `.desktop` nas pastas da spec XDG ou põe o executável no `PATH`.
    Enquanto só a primeira existia, os cinco cartões diziam `NÃO SEI` por CONSTANTE, sem diferir *"o
    produto mediu e não sabe"* de *"ninguém pintou"* (**o desenho fingindo ser produto**).

    :param atalhos: os `stem` de `.desktop` que denunciam o lançador. Sem glob nem prefixo:
    `dolphin-emu` é o emulador e `dolphin` o gerenciador de arquivos do KDE, e casar por prefixo
    acusaria o Dolphin em toda máquina com KDE. :param comandos: o que procurar no `PATH` sem
    `.desktop` (o Flatpak é PACOTE, sem atalho próprio, só o comando).
    """

    chave: str
    nome: str
    atalhos: tuple[str, ...] = ()
    comandos: tuple[str, ...] = ()
    declarado: bool = False
    janelas: tuple[str, ...] = ()
    titulo_do_jogo: str = ""
    leitor: _censo.LeitorPorProcesso | None = None
    modificacao: str = ""
    pela_porta: bool = False


def _de_fabrica(item: _censo.LancadorDeFabrica) -> SemCenso:
    """O cartão de um lançador de fábrica: o que o manifesto dele diz (`mods/de_fabrica/`)."""
    bloco = item.bloco
    return SemCenso(bloco.chave, bloco.rotulo, bloco.atalhos, bloco.comandos, janelas=bloco.janelas)


SEM_FONTE: tuple[SemCenso, ...] = tuple(
    _de_fabrica(f) for f in _censo.DE_FABRICA if not f.interior_lido)

A_STEAM = next((_de_fabrica(f) for f in _censo.DE_FABRICA if f.interior_lido), None)
if A_STEAM is None:  # pragma: no cover
    raise RuntimeError("o pacote não traz o lançador da Steam (mods/de_fabrica/steam)")

EMBUTIDOS: tuple[SemCenso, ...] = tuple(_de_fabrica(f) for f in _censo.DE_FABRICA)


def procurados(declarados: tuple[SemCenso, ...] = ()) -> tuple[SemCenso, ...]:
    """Os :data:`EMBUTIDOS` **mais** o que o usuário declarou — a lista única.

    É a que se procura em disco, se ordena e vira cartão: embutido e declarado passam pelo MESMO
    procurador, com os mesmos três campos (`atalhos`, `comandos`, `nome`).

    **Chave repetida não vira segundo cartão, ENSINA o primeiro.** Se ela declarar `retroarch` (o
    botão de localizar do cartão que não achou manda a chave do cartão), os `atalhos` e `comandos`
    dela se SOMAM aos de fábrica no mesmo cartão, o sentido literal do botão (mostrar onde ele já
    está). Dois cartões com a mesma `chave` seriam pior que inútil: os endereços levam a chave como
    prefixo (`data-campo="retroarch-selo"`) e o piloto pintaria o valor de um nos DOIS. O nome de
    fábrica vence no cartão ensinado (o rótulo é desenho aprovado; o que ela acrescentou foi ONDE
    procurar).

    A ordem é estável: os de fábrica na ordem do desenho, os novos no fim na ordem em que o disco os
    devolveu (cartão que troca de lugar entre dois tiques é a grade inteira piscando). A terceira
    fonte são as modificações ligadas (campo da modificação cheio), por último: a de chave nova vira
    cartão no fim; a de chave que já tem cartão o ensina (soma onde procurar e as janelas, e traz o
    leitor e a forma do título que ele não tinha) sem lhe dar o «Tirar daqui», porque desfazer o que
    veio da modificação é desligá-la. Sem modificação, a lista é a de antes.
    """
    das_modificacoes = tuple(x for x in declarados if x.modificacao)
    declarados = tuple(x for x in declarados if not x.modificacao)
    novos = {x.chave: x for x in declarados}
    fora: list[SemCenso] = []
    for item in EMBUTIDOS:
        ensino = novos.pop(item.chave, None)
        if ensino is None:
            fora.append(item)
            continue
        fora.append(dataclasses.replace(
            item,
            atalhos=tuple(dict.fromkeys(item.atalhos + ensino.atalhos)),
            comandos=tuple(dict.fromkeys(item.comandos + ensino.comandos)),
            declarado=True))
    fora.extend(novos.values())
    for mod in das_modificacoes:
        onde = next((i for i, x in enumerate(fora) if x.chave == mod.chave), None)
        if onde is None:
            fora.append(mod)
            continue
        ja = fora[onde]
        fora[onde] = dataclasses.replace(
            ja,
            atalhos=tuple(dict.fromkeys(ja.atalhos + mod.atalhos)),
            comandos=tuple(dict.fromkeys(ja.comandos + mod.comandos)),
            janelas=tuple(dict.fromkeys(ja.janelas + mod.janelas)),
            titulo_do_jogo=ja.titulo_do_jogo or mod.titulo_do_jogo,
            leitor=ja.leitor or mod.leitor)
    return tuple(fora)

DIZ_SEM_FONTE = "<b>O perfil casa pelo nome do processo e pela janela.</b>"


AINDA_LENDO = "…"

STEAM = "steam"

ABRIR = "abrir-lancador"



ADICIONAR = "adicionar-lancador"

ADICIONAR_ROTULO = "Localizar este lançador"

APONTAR_ROTULO = "Outro caminho"
APONTAR_DICA = "Apontar outro caminho para este lançador"

CONFIGURAR_ROTULO = "Configurar"
IDENTIFICAR_ROTULO = "Identificar"

DIZ_NAO_ACHEI = "<b>Fora dos caminhos conhecidos</b>"

DIZ_NAO_LI = "<b>Biblioteca da Steam ilegível</b>"

ADICIONAR_NOVO_ROTULO = "Adicionar um lançador"

PROCURAR_O_ARQUIVO = "procurar-o-arquivo"

PROCURAR_O_ARQUIVO_ROTULO = "Escolher o arquivo…"

TELA_DO_NOVO_TITULO = "Adicionar um lançador"

REMOVER = "esquecer-lancador"

REMOVER_ROTULO = "Tirar daqui"

TELA_DO_NOVO = "novo-lancador"

NOVO_ROTULO = "lanc-novo-rotulo"
NOVO_ALVO = "lanc-novo-alvo"

NOVO_PARA_QUEM = "lanc-novo-para-quem"


def linha_do_wrapper_html(linha: str) -> str:
    """A linha de inicialização À MOSTRA, para ela selecionar e copiar à mão.

    É a segunda saída da decisão [01]: pôr texto na área de transferência não devolve resposta e
    pode falhar CALADO; a janela velha resolve igual (o aviso *"continua selecionável"* quando a
    cópia não vai, `docs/data/paridade-gtk-html.csv`, linha 237), e com a linha na tela um `Ctrl+C`
    salva o dia. Desde 21/09/2026 ninguém na aba copia («Copiar a linha» saiu), e a linha à mostra é
    a saída que sobra.

    Não é inventada aqui: o módulo **não importa nada do produto** (para o gerador rodar solto),
    então a linha chega pelo contrato frio `Leitura.linha`, que o pacote enche de
    `steam_launch_options.WRAPPER_LAUNCH`. Sem ela o desenho cala em vez de escrever linha de
    mentira.

    `<code>` e não `<pre>`: são 143 caracteres numa coluna de cartão e o `<pre>` não quebra,
    empurraria barra de rolagem lateral para dentro do cartão. Quebra o CSS (`.linha-do-wrapper`, em
    `aba07.py`, `word-break:break-all`, pois a linha não tem espaço onde caiba). Medido no Chrome,
    1920x1080: 523 px dentro da coluna e a janela segue em 1180x777, sem rolagem lateral.
    """
    return (f'<div class="linha-do-wrapper"><code>{_e(linha)}</code></div>'
            if linha else "")


@dataclass(frozen=True)
class DoDisco:
    """O que o DISCO diz sobre os cartões que não são a Steam — já respondido.

    **Existe porque a pintura não pode perguntar** (09/09/2026, recaída medida): a biblioteca de
    cada lançador, a linha do «Flatpak» e quem tem estrada para a cura nasceram dentro de
    :func:`cartao_sem_censo`, chamadas ao desenhar o cartão, DEZ VEZES POR SEGUNDO no tique. Medido
    nesta bancada com os cinco lançadores do usuário no disco: `cartoes()` levava **6,4 ms de
    mediana** (30 voltas, máximo 18,6 ms) num orçamento de 100 ms para a janela inteira, e agora
    **0,03 ms**; o disco voltou para a :class:`a07_lancadores._Vigia` (*"a pintura NUNCA
    bloqueia"*).

    É FRIO como a :class:`Leitura`: quem lê é o pacote, na thread da vigia; o desenho recebe texto
    pronto e não abre arquivo.
    """

    resumos: tuple[tuple[str, str], ...] = ()
    pontes: tuple[tuple[str, int], ...] = ()

    sem_ambiente: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def resumo(self, chave: str) -> str:
        return dict(self.resumos).get(chave, "")

    def pontes_de(self, chave: str) -> int:
        return dict(self.pontes).get(chave, 0)

    def sem_ambiente_de(self, chave: str) -> tuple[str, ...]:
        return dict(self.sem_ambiente).get(chave, ())


SEM_DISCO = DoDisco()


def medir_no_disco(onde_estao: tuple[tuple[str, str], ...],
                   declarados: tuple[SemCenso, ...] = (),
                   lar: Path | None = None,
                   raiz_sistema: Path | None = None,
                   com_ponte: frozenset[str] = frozenset(),
                   da_porta: Mapping[str, object] | None = None) -> DoDisco:
    """BLOQUEIA — abre os arquivos dos lançadores e responde o que o cartão mostra.

    Quem chama é só a vigia (`a07_lancadores._Vigia.ler`, thread de fundo; ver :class:`DoDisco`).
    Só entra o cartão com caminho em `onde_estao`. `lar` e `raiz_sistema` desviam a medição para o
    `tmp`; `com_ponte` são as classes de janela (em `casefold`) com ponte num perfil, o que
    :func:`contador_html` conta; `da_porta` são os jogos que cada extensão de lançador entregou pela
    porta (o ``mods.jogos``), por chave de cartão, lidos por
    :func:`censo_dos_lancadores.biblioteca_da_porta` quando o cartão não tem leitor.
    """
    onde = dict(onde_estao)
    itens = [x for x in procurados(declarados) if x.chave != STEAM]
    vistos: list[str] = []
    for item in itens:
        if item.chave == "flatpak" or not onde.get(item.chave):
            continue
        for app_id in _caixa.app_ids_do_cartao(item.atalhos,
                                               onde.get(item.chave), lar,
                                               raiz_sistema):
            if app_id not in vistos:
                vistos.append(app_id)
    caixas = resposta_do_flatpak(tuple(vistos), lar, raiz_sistema)

    resumos: list[tuple[str, str]] = []
    pontes: list[tuple[str, int]] = []
    for item in itens:
        if not onde.get(item.chave):
            continue
        if item.leitor is None and da_porta is not None and item.chave in da_porta:
            biblioteca = _censo.biblioteca_da_porta(item.nome, da_porta[item.chave])
        else:
            biblioteca = _censo.biblioteca_do_cartao(item.chave, lar, leitor=item.leitor)
        linha = biblioteca.resumo
        if not linha and item.chave == "flatpak":
            linha = caixas
        if linha:
            resumos.append((item.chave, linha))
        classes = {j.classe_de_janela.casefold() for j in biblioteca.jogos
                   if j.classe_de_janela}
        pontes.append((item.chave, len(classes & com_ponte)))
    return DoDisco(tuple(resumos), tuple(pontes))


@dataclass(frozen=True)
class Leitura:
    """O que o disco respondeu sobre a Steam. É o contrato pacote → desenho.

    FRIO de propósito: só tuplas de texto, nenhum objeto do motor. O desenho não importa
    `sentinela_do_wrapper` (o gerador roda sem o produto) e a régua da aba monta uma `Leitura` à mão
    para provar cada estado do cartão sem tocar no disco.
    """

    com_wrapper: tuple[str, ...] = ()
    reparaveis: tuple[tuple[str, str, str], ...] = ()
    intocaveis: tuple[tuple[str, str, str], ...] = ()
    recusados: tuple[tuple[str, str], ...] = ()
    dispensados: tuple[tuple[str, str], ...] = ()
    instalados: int = 0
    pontes: int = 0
    onde_estao: tuple[tuple[str, str], ...] = ()
    declarados: tuple[SemCenso, ...] = ()
    linha: str = ""
    erros: tuple[str, ...] = ()
    do_disco: DoDisco = SEM_DISCO
    viraram_extensao: tuple[tuple[str, str, str], ...] = ()

    @property
    def onde_esta_a_steam(self) -> str | None:
        """Onde a Steam foi achada; `''` = procurei e não achei; `None` = não procurei.

        A terceira resposta é a que importa: `Leitura` montada à mão (a régua monta várias) não tem
        a `steam` no mapa, e `None` quer dizer *"esta leitura não fala de presença"*, o cartão
        seguindo só o censo (o comportamento anterior). Colapsar `None` em `''` faria toda régua
        antiga passar a ver `NÃO ACHEI`.
        """
        return dict(self.onde_estao).get(STEAM)

    @property
    def viu_a_biblioteca(self) -> bool:
        """A leitura ALCANÇOU a biblioteca da Steam de algum jeito?

        Não basta `onde_esta_a_steam`: as duas buscas respondem coisas diferentes e podem discordar
        sem erro. Steam instalada por caminho que os três `.desktop` conhecidos não cobrem
        (AppImage, script no `~/bin`) não aparece na procura, e o `localconfig.vdf` dela está lá com
        a biblioteca inteira; dizer `NÃO ACHEI` sobre biblioteca recém-lida trocaria um erro por
        outro. O `erros` entra na conta: vdf ilegível EXISTE.
        """
        return bool(self.erros or self.com_wrapper or self.reparaveis
                    or self.intocaveis or self.recusados or self.instalados)


def _plural(n: int, um: str, muitos: str) -> str:
    return f"{n} {um if n == 1 else muitos}"


def lista_de_jogos(lida: Leitura) -> str:
    """As linhas dentro do cartão da Steam: quem falta, quem ELA tirou e quem mandou não perguntar
    mais.

    Os intocáveis aparecem SEM botão: o produto não os repõe (`apply_wrapper_vdf_text` os pula) e
    "tirar daqui" um jogo já fora do reparo não mudaria nada (botão que finge). Os dispensados
    são o `launch_dialog_dismissed.json`, escrito pelo *"Não perguntar para este jogo"* do lembrete
    da GTK: aparecem SEM botão desde 19/10/2026, quando o «Voltar a perguntar» saiu do produto com o
    lembrete (`O-QUE-A-07-ANTIGA-FAZIA-SEM-TELA-VOLTA-OU-SAI-01`). A dispensa de antes continua
    valendo, e a linha diz qual é.

    A lista é outra, não a dos recusados: `jogos_sem_wrapper.txt` diz *"não ponha o atalho neste
    jogo"* e o dispensado *"não me lembre deste jogo"*; um jogo pode estar num, no outro ou nos
    dois, e juntá-las apagaria a diferença do que ela mesma pediu.
    """
    itens = [
        JogoNaLista(appid=a, rotulo=r, porque=p,
                    gesto="tirar-daqui", botao="Não usar neste jogo")
        for a, r, p in lida.reparaveis
    ]
    itens += [JogoNaLista(appid=a, rotulo=r, porque=p)
              for a, r, p in lida.intocaveis]
    itens += [
        JogoNaLista(appid=a, rotulo=r, porque="você tirou",
                    gesto="voltar-a-usar", botao="Voltar a usar")
        for a, r in lida.recusados
    ]
    itens += [
        JogoNaLista(appid=a, rotulo=r, porque="você mandou não perguntar mais")
        for a, r in lida.dispensados
    ]
    return linhas_de_jogos(itens) or LISTA_VAZIA


def acao_de_localizar(chave: str, rotulo: str = ADICIONAR_ROTULO) -> Acao:
    """O botão de apontar o caminho de UM cartão — o MESMO nos SEIS.

    Nasceu em dois lugares e faltou num (08/09/2026): o botão do estado NÃO LOCALIZADO foi escrito
    dentro de :func:`cartao_sem_censo` (cinco cartões) e a Steam, com função própria
    (:func:`cartao_da_steam`), ficou com o botão velho: sem Steam, selo `NÃO LOCALIZADO`, a frase
    :data:`DIZ_NAO_ACHEI` e um «Abrir o lançador» que só abre a Steam que não está lá. E o buraco
    fechava por cima: o botão global RECUSA nome que já tem cartão de fábrica mandando usar o botão
    do cartão, que ali não existia (clicar onde não havia nada, sem como dizer onde a Steam está).

    A cura é esta função e não uma segunda cópia da linha (regra de 05/09: *quando a cura conhece a
    causa, ela cobre TODOS os chamadores*). O `href` abre a tela (`.tela-nova` por `:target`,
    `monta.CSS_POPUP`; só uma âncora muda o fragmento: :attr:`Acao.href`).

    **O rótulo é parâmetro desde 11/09/2026 — A2-022, o gesto não**: o localizado diz
    :data:`APONTAR_ROTULO`, o não localizado :data:`ADICIONAR_ROTULO`, mas mandam o mesmo
    `data-gesto` para a mesma tela e gravam no mesmo lugar (um segundo gesto seria um segundo
    caminho para o mesmo disco).
    """
    dica = APONTAR_DICA if rotulo == APONTAR_ROTULO else ""
    return Acao(rotulo, "", ADICIONAR, chave, href=f"#{TELA_DO_NOVO}", dica=dica)


def acao_de_tirar(chave: str) -> Acao:
    """O «Tirar daqui» de UM cartão, pela razão de :func:`acao_de_localizar`.

    *O que se acrescenta se tira*, nos SEIS: cartão ensinado que não se desensina deixa o caminho
    errado gravado para sempre. Quem decide se aparece é o chamador, que sabe se há declaração.
    """
    return Acao(REMOVER_ROTULO, "", REMOVER, chave)


TELA_DA_ESCOLHA = "escolher-jogo"
MIOLO_DA_ESCOLHA = "lanc-escolha"
ESCOLHA = "lanc-escolha-jogo"

EXCLUIR = "adicionar-a-exclusao"
EXCLUIR_ROTULO = "Lista de exclusão"
EXCLUIR_TITULO = "Adicionar à lista de exclusão"
DICA_EXCLUIR = (
    "Adicionar jogo à lista de exclusão do Hefesto: o jogo passa a ver o "
    "controle como se o Hefesto não estivesse instalado — sem máscara, sem "
    "perfil, sem luz, sem vibração do Hefesto, sem Proton fixado. «Tirar da "
    "lista» devolve tudo.")
CONFIRMAR_EXCLUSAO = "confirmar-exclusao"
CONFIRMAR_EXCLUSAO_ROTULO = "Adicionar à lista"

CRIAR_PERFIL = "criar-perfil-para-um-jogo"
CRIAR_PERFIL_ROTULO = "Criar perfil"
CRIAR_PERFIL_TITULO = "Criar perfil para um jogo"
CONFIRMAR_PERFIL = "confirmar-perfil"
CONFIRMAR_PERFIL_ROTULO = "Criar o perfil"

TIRAR_DA_EXCLUSAO = "tirar-da-exclusao"
TIRAR_DA_EXCLUSAO_ROTULO = "Tirar da lista"


def acao_de_excluir(chave: str) -> Acao:
    """O «Adicionar à lista de exclusão» de um cartão — abre a escolha do jogo."""
    return Acao(EXCLUIR_ROTULO, "", EXCLUIR, chave,
                href=f"#{TELA_DA_ESCOLHA}", dica=DICA_EXCLUIR)


def acao_de_criar_perfil(chave: str) -> Acao:
    """O «Criar perfil para um jogo» — abre a MESMA escolha, no modo do perfil.

    D-2109-O-CRIAR-PERFIL-LEVA-A-ABA-PERFIS: o perfil nasce pelo dono da aba Perfis (um gravador,
    dois caminhos) e a tela vai para lá.
    """
    return Acao(CRIAR_PERFIL_ROTULO, "", CRIAR_PERFIL, chave,
                href=f"#{TELA_DA_ESCOLHA}", dica=CRIAR_PERFIL_TITULO)


def fileira_comum(chave: str) -> tuple[Acao, ...]:
    """Os quatro botões que os oito cartões têm quando o lançador está LOCALIZADO."""
    return (Acao("Abrir o lançador", "", ABRIR, chave),
            acao_de_criar_perfil(chave),
            acao_de_localizar(chave, APONTAR_ROTULO),
            acao_de_excluir(chave))


def rodape_da_exclusao_html(excluidos: list[tuple[str, str]]) -> str:
    """O pé do cartão: os jogos DESTE lançador na lista, cada um com o seu «Tirar».

    `excluidos` é ``[(chave, nome)]``. Sem nenhum, NADA — o pé do cartão não
    diz a lista vazia (palavra, 21/09/2026).
    """
    if not excluidos:
        return ""
    partes = [
        f"<b>{_e(nome)}</b> · <a class=\"tirar\" href=\"#\" "
        f'data-gesto="{_a(TIRAR_DA_EXCLUSAO)}" data-v="{_a(chave)}">'
        f"{_e(TIRAR_DA_EXCLUSAO_ROTULO)}</a>"
        for chave, nome in excluidos
    ]
    return ('<div class="lanc-excl">Na lista de exclusão: '
            + " — ".join(partes) + "</div>")


@dataclass(frozen=True)
class JogoParaEscolher:
    """Uma linha da escolha: a chave é a classe da janela, o que o daemon vê."""

    chave: str
    nome: str
    instalado: bool = True
    marcado: bool = False


NOTA_DO_EMULADOR = (
    "Todos os jogos abrem na mesma janela do emulador, e o Hefesto não sabe "
    "qual deles está aberto. Por isso a exclusão vale para o emulador inteiro.")
NENHUM_JOGO_PARA_ESCOLHER = (
    "Nenhum jogo aqui ainda. Quando houver, eles aparecem nesta lista.")
O_ULTIMO_QUE_ABRIU = "o último que você abriu"


def miolo_da_escolha_html(modo: str, nome_do_lancador: str,
                          jogos: list[JogoParaEscolher],
                          *, emulador: bool = False) -> str:
    """O conteúdo inteiro da pop-up, para o lançador clicado e o modo pedido.

    `modo` é :data:`EXCLUIR` ou :data:`CRIAR_PERFIL`. O confirmar leva `data-hef-forma` =
    :data:`MIOLO_DA_ESCOLHA` e o piloto recolhe a opção MARCADA (`ESCOLHA`).
    """
    excluir = modo == EXCLUIR
    titulo = (f"{EXCLUIR_TITULO} — {nome_do_lancador}" if excluir
              else f"{CRIAR_PERFIL_TITULO} — {nome_do_lancador}")
    if excluir:
        para = ('O jogo que você escolher vai ver o controle <b>como se o '
                'Hefesto não estivesse instalado</b>: sem máscara, sem perfil, '
                'sem luz e sem vibração do Hefesto. «Tirar da lista» devolve tudo.')
    else:
        para = ('O perfil nasce na aba Perfis, já apontado para o jogo que você '
                'escolher, e a tela vai para lá.')
    linhas: list[str] = []
    for jogo in jogos:
        marca = " checked" if jogo.marcado else ""
        tags = ""
        if jogo.marcado and not emulador:
            tags += f' <span class="excl-tag ok">{_e(O_ULTIMO_QUE_ABRIU)}</span>'
        if not jogo.instalado:
            tags += ' <span class="excl-tag">não instalado</span>'
        linhas.append(
            f'<label class="excl-jogo"><input type="radio" name="{ESCOLHA}" '
            f'data-linha="{ESCOLHA}" value="{_a(jogo.chave)}"{marca}>'
            f"<span>{_e(jogo.nome)}{tags}</span></label>")
    if linhas:
        corpo = '<div class="excl-lista">' + "".join(linhas) + "</div>"
        if emulador:
            corpo += f'<div class="excl-nota">{_e(NOTA_DO_EMULADOR)}</div>'
        destino = "#" if excluir else "10-perfis.html"
        confirmar = (
            f'<a class="btn roxo" href="{destino}" '
            f'data-gesto="{_a(CONFIRMAR_EXCLUSAO if excluir else CONFIRMAR_PERFIL)}" '
            f'data-hef-forma="{_a(MIOLO_DA_ESCOLHA)}">'
            f"{_e(CONFIRMAR_EXCLUSAO_ROTULO if excluir else CONFIRMAR_PERFIL_ROTULO)}</a>")
    else:
        corpo = f'<div class="excl-nota">{_e(NENHUM_JOGO_PARA_ESCOLHER)}</div>'
        confirmar = ""
    return f"""<div class="tn-topo">
      <span class="tn-tit" data-dica="{_a(DICA_EXCLUIR if excluir else
        "Um gravador só: o perfil é criado pela aba Perfis.")}">{_e(titulo)}</span>
      <a class="tn-x" href="#" title="Fechar">&times;</a>
    </div>
    <div class="tn-corpo">
      <div class="lanc-novo-para">{para}</div>
      {corpo}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      {confirmar}
    </div>"""


def cartao_da_steam(lida: Leitura | None) -> Lancador:
    """O ÚNICO cartão com fonte, e cada palavra dele sai de uma medição.

    O selo segue `reparaveis`, não a soma dos faltantes: jogo com a lista de IGNORE estendida à mão
    está sem o wrapper e **não deve ser tocado** (remover só o trecho do Hefesto deixaria um
    fragmento-comando que impede o jogo de abrir); contá-lo como "não chega" acenderia um
    `Consertar` que não conserta aquele jogo.

    **A presença deixou de ser constante — 02/09/2026**, acusação provada antes de curada. Com o
    `HOME` desviado para uma casa de mentira e o `PATH` vazio (nenhuma Steam, vdf ou jogo),
    respondia:

        selo 'ok' (**CHEGAM**) · presente True · "1 encontrado" no topo
        "Os controles chegam. O atalho de inicialização está no lugar em 0
         jogos da sua biblioteca."

    Selo VERDE e promessa para máquina sem Steam, enquanto os cinco vizinhos diziam `NÃO ACHEI`: era
    o único cartão cuja presença ninguém mediu, porque ter fonte para o INTERIOR não responde se o
    lançador está aqui. As duas perguntas continuam separadas, e o `NÃO ACHEI` exige as DUAS
    respostas negativas (:meth:`Leitura.viu_a_biblioteca`): Steam instalada por caminho que os três
    `.desktop` não cobrem não aparece na procura e a biblioteca foi lida. O estado NÃO LOCALIZADO
    oferece o «LOCALIZAR» (razão em :func:`acao_de_localizar`); faltava aqui, e o cartão da Steam
    era o único sem saída onde a Steam não está pelos caminhos de fábrica.
    """
    abrir = Acao("Abrir o lançador", "", ABRIR, STEAM)
    criar = acao_de_criar_perfil(STEAM)
    tirar = ((acao_de_tirar(STEAM),)
             if any(x.chave == STEAM for x in (lida.declarados if lida else ()))
             else ())
    if lida is None:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos=AINDA_LENDO,
            diz=SEM_FRASE,
            acoes=(abrir, criar), fora=SEM_LISTA, tem_lista=True)
    if lida.onde_esta_a_steam == "" and not lida.viu_a_biblioteca:
        return Lancador(
            chave=STEAM, nome="Steam", selo="off", jogos="—",
            diz=DIZ_NAO_ACHEI, acoes=(acao_de_localizar(STEAM), *tirar),
            fora=SEM_LISTA, tem_lista=True)
    if lida.erros:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos="—",
            diz=DIZ_NAO_LI,
            acoes=(Acao("Procurar de novo", "", "procurar", STEAM), abrir, criar,
                   *tirar),
            fora=SEM_LISTA, tem_lista=True)

    falta = len(lida.reparaveis)
    if falta:
        diz = f"<b>{_plural(falta, 'jogo', 'jogos')} sem o atalho</b>"
        selo = "warn"
    else:
        diz = ""
        selo = "localizado"

    if lida.intocaveis and lida.linha:
        diz = diz + linha_do_wrapper_html(lida.linha)

    acoes = fileira_comum(STEAM)
    diz = contador_html(lida.pontes) + (f"<br>{diz}" if diz else "")

    acoes = (*acoes, *tirar)

    return Lancador(
        chave=STEAM, nome="Steam", selo=selo,
        jogos=_plural(lida.instalados, "jogo instalado", "jogos instalados"),
        diz=diz, acoes=acoes,
        fora=lista_de_jogos(lida), tem_lista=True,
        presente=bool(lida.onde_esta_a_steam) or lida.viu_a_biblioteca)


def resposta_do_flatpak(vizinhos: tuple[str, ...], lar: Path | None = None,
                        raiz_sistema: Path | None = None) -> str:
    """A linha do cartão «Flatpak» — §5.4 da sprint: ele MUDA DE PERGUNTA.

    Não é lançador, é o runtime dos outros cinco: o censo lhe devolve `SEM_BIBLIOTECA` e a linha
    ficava com travessão. A pergunta só dele é a da §4: **o controle entra na caixa em que o jogo
    roda?** Quem mede é :mod:`sandbox_dos_lancadores`, e a lista vem de fora: os lançadores que a
    aba ACHOU e vieram do Flatpak, um `app-id` cada (perguntar pela caixa de nativo devolveria "não
    instalado" e baixaria a conta por motivo que não é do usuário).

    BLOQUEIA: quem chama é :func:`medir_no_disco`, na vigia, nunca a pintura.
    """
    return _caixa.resposta_do_flatpak(vizinhos, lar, raiz_sistema).resumo


def cartao_sem_censo(item: SemCenso, onde: str | None,
                     do_disco: DoDisco = SEM_DISCO) -> Lancador:
    """Um dos cinco cartões cujo INTERIOR o produto não lê — em três estados.

    ==============  ============  =========================================
    ``onde``        selo          o que a tela passa a dizer
    ==============  ============  =========================================
    ``None``        ``nao_sei``   ainda não procurei (a primeira meia volta)
    ``""``          ``off``       procurei e NÃO ACHEI nesta máquina
    um caminho      ``nao_sei``   achei AQUI, e ainda não sei olhar dentro
    ==============  ============  =========================================

    O selo ``off`` estava morto até 02/09: `SELOS["off"] = "NÃO ACHEI"` existia desde o desenho e
    nenhum caminho o produzia.

    **O botão fica nos três estados** — decisão de 02/09/2026, que DESFAZ uma mudança nunca
    submetida a ela: o `off` nasceu com `acoes=()` pelo argumento de que "Abrir o lançador" sobre
    lançador ausente seria botão que finge. O argumento tem mérito e **não é desta frente
    decidi-lo**: o desenho aprovado tem o botão nos CINCO cartões; se deve sumir com o lançador
    ausente, quem diz é ela (`espera_a_palavra_dela`, com as três frases).

    O botão ganhou endereço nos SEIS em 03/09/2026 (decisão 17). **O produto só sabe abrir a Steam**
    (`steam_launch_options.reopen_steam`); nos outros cinco o gesto RECUSA dizendo, melhor que o
    silêncio de antes (botão sem `data-gesto` não chega ao Python, o clique some e quem clica
    conclui que funcionou). Ver `a07_lancadores.abrir_lancador`.
    """
    abrir = (Acao("Abrir o lançador", "", ABRIR, item.chave),)
    localizar = (acao_de_localizar(item.chave),)
    tirar = (acao_de_tirar(item.chave),) if item.declarado else ()
    if onde is None:
        return Lancador(chave=item.chave, nome=item.nome, selo="nao_sei",
                        jogos="—", diz=DIZ_SEM_FONTE, acoes=abrir + tirar)
    if not onde:
        return Lancador(chave=item.chave, nome=item.nome, selo="off",
                        jogos="—", diz=DIZ_NAO_ACHEI,
                        acoes=localizar + tirar)
    resumo = do_disco.resumo(item.chave)
    falta = sem_o_ambiente_html(item.chave, do_disco.sem_ambiente_de(item.chave))
    return Lancador(
        chave=item.chave, nome=item.nome, selo="warn" if falta else "localizado",
        jogos=resumo or "—",
        diz=contador_html(do_disco.pontes_de(item.chave)) + (f"<br>{falta}" if falta else ""),
        acoes=fileira_comum(item.chave) + tirar, presente=True)


def cartoes(lida: Leitura | None) -> list[Lancador]:
    """Os cartões: o que tem censo e os que só têm presença.

    O número saiu daqui em 08/09/2026: são os SEIS de fábrica **mais os declarados pelo usuário**, e
    estes só existem na máquina dele (a página publicada nasce com os seis; os declarados chegam
    pela troca da grade inteira, `_pintura`, no pacote). Cravar número aqui faria a régua reprovar a
    máquina do usuário. A Epic passou e saiu no mesmo dia, por decisão de produto (razão em
    :data:`SEM_FONTE`).
    """
    onde_estao = dict(lida.onde_estao) if lida is not None else {}
    do_disco = lida.do_disco if lida is not None else SEM_DISCO
    fora = [cartao_da_steam(lida)]
    for item in procurados(lida.declarados if lida is not None else ()):
        if item.chave == STEAM:
            continue
        fora.append(cartao_sem_censo(item, onde_estao.get(item.chave), do_disco))
    return fora


@dataclass
class Quadro:
    """Tudo o que a aba mostra: os cartões e a contagem do topo."""

    lancadores: list[Lancador] = field(default_factory=list)

    @property
    def achados(self) -> int:
        """Quantos lançadores o produto ACHOU nesta máquina.

        Soma `presente`, a resposta da pergunta que o rótulo **encontrados** faz. Até 02/09 somava
        `ok` e `warn` ("em quantos sei dizer se os controles chegam?"), e as duas contas só
        coincidiam enquanto o produto não olhava a presença; depois, lançador instalado de interior
        ilegível viraria "não encontrado" com o cartão dizendo *"achei este lançador aqui"* na mesma
        tela.
        """
        return sum(1 for x in self.lancadores if x.presente)

    @property
    def impedidos(self) -> int:
        return sum(1 for x in self.lancadores if x.selo == "warn")

    def valores(self) -> dict[str, str]:
        """O pacote inteiro de valores da aba."""
        fora: dict[str, str] = {"lanc-conta": conta_html(self.achados, self.impedidos)}
        for lanc in self.lancadores:
            fora.update(valores_do_cartao(lanc))
        return fora


__all__ = [
    "ABRIR",
    "ADICIONAR",
    "ADICIONAR_NOVO_ROTULO",
    "ADICIONAR_ROTULO",
    "AINDA_LENDO",
    "APONTAR_ROTULO",
    "A_STEAM",
    "CLASSE_DA_GRADE",
    "CONFIGURAR_ROTULO",
    "DIZ_NAO_ACHEI",
    "DIZ_NAO_LI",
    "DIZ_SEM_FONTE",
    "EMBUTIDOS",
    "IDENTIFICAR_ROTULO",
    "MOLDURA",
    "NOVO_ALVO",
    "NOVO_PARA_O_CARTAO",
    "NOVO_PARA_QUEM",
    "NOVO_ROTULO",
    "NOVO_SEM_ALVO",
    "PROCURAR_O_ARQUIVO",
    "PROCURAR_O_ARQUIVO_ROTULO",
    "REMOVER",
    "REMOVER_ROTULO",
    "SELETOR_DA_GRADE",
    "SELOS",
    "SEM_DISCO",
    "SEM_FONTE",
    "SEM_LISTA",
    "STEAM",
    "SUFIXOS",
    "SUFIXO_DA_LISTA",
    "TELA_DO_NOVO",
    "TELA_DO_NOVO_TITULO",
    "Acao",  # (noqa-acento)
    "DoDisco",
    "JogoNaLista",
    "Lancador",
    "Leitura",
    "Quadro",
    "SemCenso",
    "acao_de_localizar",
    "acao_de_tirar",
    "acao_html",
    "acoes_html",
    "carimbo_html",
    "cartao_da_steam",
    "cartao_sem_censo",
    "cartoes",
    "cartoes_html",
    "conta_html",
    "linha_do_wrapper_html",
    "linhas_de_jogos",
    "lista_de_jogos",
    "medir_no_disco",
    "procurados",
    "resposta_do_flatpak",
    "selo_html",
    "tela_do_registro_html",
    "um_cartao",
    "valores_do_cartao",
]
