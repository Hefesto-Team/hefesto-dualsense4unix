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
from dataclasses import dataclass, field
from pathlib import Path

#: O selo é o resumo de UMA palavra do corpo do cartão.
#:
#: `nao_sei` nasceu da medição: antes não havia função que examinasse Heroic, Lutris, RetroArch,
#: Dolphin ou mGBA. Desde 09/09/2026 quem os lê é `integrations.censo_dos_lancadores`
#: (LANCADORES-ZERO-01) e o selo ficou para o que ainda não se leu; sem ele o cartão escolheria
#: entre `CHEGAM` e `NÃO CHEGAM`, ambos palpite. **"Não sei" é resposta; palpite não é.** O `off`
#: diz «NÃO LOCALIZADO» desde 08/09/2026 (palavra de produto, olhando a aba com os quatro DualSense
#: na mesa).
#:
#: O valor mudou e a história ficou: a grafia antiga aparece em comentário e docstring que NARRAM um
#: dia (o selo que nasceu morto, os cinco cartões que o diziam ao lado de uma Steam verde), e o
#: passado não se edita. As réguas leem `SELOS["off"]` em vez de digitar a palavra (*régua que
#: digita o que devia LER reprova a melhora em vez do defeito*, regra das onze réguas de
#: 26/08/2026).
#:
#: O LEITOR DE BIBLIOTECA dos cinco que não são a Steam — o dono do censo
#: (`integrations.censo_dos_lancadores`). Import no topo: não puxa motor (só `json`, `configparser`
#: e `pathlib`), e um import tardio seria pago em todo cartão, a cada tique.
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as _censo

#: A LEITURA DAS CAIXAS DO FLATPAK — LANCADORES-ZERO-01 §5.4.
#:
#: Entra pela razão do censo acima (`pathlib`, `json` e `configparser`). A `cura_por_estrada` saiu
#: daqui em 10/09/2026 (LANCADOR-LOCALIZAR-01): decidia o botão «Consertar» do cartão LOCALIZADO,
#: que saiu por palavra de produto (quem tem tudo instalado e identificado não precisa dele). O
#: módulo FICA, com a dívida declarada em `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: a
#: lacuna que ele curava segue aberta e quem a fecha é a LANCADOR-CARONA-01.
from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa

SELOS = {
    "ok": "CHEGAM",
    #: «COM IMPEDIMENTO» desde 11/09/2026 — A2-007, aprovada pelo usuário.
    #:
    #: Dizia «NÃO CHEGAM» enquanto a contagem do topo (:func:`conta_html`) chamava o mesmo fato de
    #: «N com impedimentos»: duas palavras para uma coisa, a dois centímetros (a mesma cura que em
    #: 09/09 trocou «encontrados» por «localizados»). E sem caminho do produto que produza o
    #: `ok`/`CHEGAM`, «NÃO CHEGAM» era um negativo sem positivo.
    "warn": "COM IMPEDIMENTO",
    "off": "NÃO LOCALIZADO",
    "nao_sei": "NÃO SEI",
    #: O POSITIVO DO PAR — 09/09/2026, LANCADORES-ZERO-01 §5.2; palavra do usuário
    #: (`D-0809-O-SELO-DOS-LANCADORES-DIZ-LOCALIZADO`).
    #:
    #: O par de «Não Localizado» é «Localizado». Matava o defeito de cinco lançadores INSTALADOS
    #: receberem `NÃO SEI` porque o selo respondia «sei ler a biblioteca dele?»: a aba parecia não
    #: identificar nada, e um selo grande e negativo sobre programa instalado não diz outra coisa.
    #: Agora o selo responde UMA pergunta, "está aqui?", e o veredito (`ok`/`warn`) só aparece onde
    #: há censo, como na Steam; o que a biblioteca diz vai para a linha de baixo, onde cabe um
    #: número.
    "localizado": "LOCALIZADO",
}

#: A classe da MOLDURA do cartão, por selo.
#:
#: `nao_sei` divide a moldura apagada com `off` (as duas dizem "não há o que agir aqui") e
#: `localizado` divide a de `ok` ("este está aqui e não há impedimento"): um terceiro e um quarto
#: tom só acrescentariam cor para decodificar.
MOLDURA = {"ok": "chega", "warn": "impede", "off": "ausente",
           "nao_sei": "ausente", "localizado": "chega"}

#: A GRADE QUE SEGURA OS SEIS CARTÕES — constante porque o PACOTE também precisa dela.
#:
#: Medido e fotografado em 02/09/2026: a `MOLDURA` só aparecia em :func:`um_cartao` (o GERADOR). O
#: pacote emitia cinco endereços por cartão (`-selo`, `-jogos`, `-diz`, `-acoes`, `-fora`), nenhum
#: deles a classe do contêiner, e a página nasceu com os seis cartões em `class="lanc ausente"` (o
#: estado `cartoes(None)`) para sempre: o cartão da Steam mostrava o selo verde `CHEGAM` numa
#: moldura cinza de *ausente*, a mesma tela dizendo duas coisas opostas. A pintura do piloto escreve
#: texto, `innerHTML`, largura, fundo e `value`, não CLASSE; ela troca inteiro um BLOCO endereçado
#: por seletor CSS (`p.blocos`), por isso o pacote repinta a grade. Se o piloto ganhar um alvo
#: `classe`, isto vira uma linha por cartão (declarado em `espera_o_pintor`).
CLASSE_DA_GRADE = "lancadores"
SELETOR_DA_GRADE = f".{CLASSE_DA_GRADE}"


@dataclass(frozen=True)
class Acao:
    """Um botão do cartão. `gesto` vazio = botão sem endereço (só desenho)."""

    rotulo: str
    classe: str = ""
    gesto: str = ""
    #: O `data-v` do botão — qual lançador, ou qual appid. Vai cru para o
    #: `o["v"]` do gesto, e é o que separa "Consertar a Steam" de "Consertar o
    #: Heroic" sem o gesto ter de adivinhar pelo texto do botão.
    v: str = ""
    #: O destino do `href`; com ele o botão nasce `<a class="btn">`, sem ele `<button>`.
    #:
    #: Existe para um caso mecânico: a pop-up desta casa abre por `:target` (`monta.CSS_POPUP`,
    #: `.tela-nova:target{display:flex}`) e só uma âncora muda o fragmento. O gesto sai no mesmo
    #: clique: o ouvinte do piloto não chama `preventDefault` (`hefesto_vivo.py`, o
    #: `addEventListener('click', …)`), então o toque abre a tela E manda o gesto, que é como o
    #: registro sabe para QUAL cartão a tela abriu (forma do `aba06.py` nos "Guardar" das telas de
    #: teclas).
    href: str = ""
    #: O `title` do botão. Nasceu com o «Adicionar à lista de exclusão» (21/09/2026), cujo rótulo é
    #: mais curto que a frase de produto e cuja explicação inteira vai aqui (§4.1 da sprint).
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
    #: A lista de jogos DENTRO do cartão (hoje só a Steam a tem). HTML pronto.
    fora: str = ""
    #: O cartão tem lugar para a lista? Se `False`, o gerador nem emite o
    #: contêiner — e um endereço que não existe na página é pintura perdida.
    tem_lista: bool = False
    #: O produto ACHOU este lançador nesta máquina? É o que a contagem do topo
    #: soma, e é um campo próprio de propósito: derivar "encontrado" do SELO
    #: confunde duas perguntas diferentes — «o lançador está aqui?» e «os
    #: controles chegam nele?». Um lançador achado cujo interior o produto não
    #: sabe ler é `presente=True` com selo `nao_sei`, e as duas coisas são
    #: verdade ao mesmo tempo.
    presente: bool = False


#: O ESPAÇO DURO É O QUARTO CARACTERE DA TABELA, e ninguém pensa nele. O DOM
#: devolve `&nbsp;` para um U+00A0 que entrou cru — logo emiti-lo cru é a mesma
#: reescrita eterna que o apóstrofo causa, num caractere que um `appmanifest`
#: bem pode trazer.
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
    reescritas duas vezes por segundo, para sempre, matando o foco e o `:hover`. A régua é
    `test_a_marcacao_volta_igual_do_dom`: reserializa a marcação emitida e exige o mesmo texto, sem
    digitar a tabela.
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


#: Os cartões cujo ambiente entra JOGO A JOGO (a cópia de cada jogo no
#: Heroic). Nos outros a estrada é a caixa do Flatpak, uma para todos.
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
    # A tag segue o `href` (:attr:`Acao.href`): só uma âncora abre a pop-up por `:target`;
    # `<button>` com `href` não navega e `<a>` sem `href` não é clicável pelo teclado.
    dica = f' title="{_a(a.dica)}"' if a.dica else ""
    if a.href:
        return (f'<a class="{classe}" href="{_a(a.href)}"'
                f'{endereco}{valor}{dica}>{_e(a.rotulo)}</a>')
    return f'<button class="{classe}"{endereco}{valor}{dica}>{_e(a.rotulo)}</button>'


#: O que vai no lugar de uma fileira de botões vazia.
#:
#: O `escrever()` do BOOTSTRAP troca vazio por TRAVESSÃO, certo para campo de valor e errado para
#: contêiner de HTML: fotografado em 02/09/2026, os quatro cartões `NÃO ACHEI` nasceram com um traço
#: solto onde os botões estiveram (e já o havia no pé do cartão da Steam com a lista vazia). A cura
#: de raiz é no `escrever()` (alvo `html` vazio = NADA; mora em `hefesto_vivo.py`, fora desta aba).
#: Um COMENTÁRIO HTML é o que o desenho faz sozinho: o valor não é vazio, o navegador o renderiza
#: como nada e a fileira fica com a altura do próprio `padding-top`.
FILEIRA_VAZIA = "<!-- nada a oferecer neste cartão -->"

#: O que vai num contêiner de lista que ainda não tem o que listar — NÃO é uma frase.
#:
#: Fotografado em 02/09/2026: `lista_de_jogos` ganhou :data:`LISTA_VAZIA`, mas as duas saídas
#: antecipadas de :func:`cartao_da_steam` (primeira meia volta, `lida is None`; Steam ilegível,
#: `lida.erros`) devolviam `fora=""`; com `tem_lista=True`, `valores_do_cartao` emitia
#: `steam-fora=""` e o `escrever()` do BOOTSTRAP troca vazio por travessão ANTES de despachar o alvo
#: (`hefesto_vivo.py:61`), inclusive em `html`. **O da Steam ilegível é permanente**, um traço mudo
#: justo onde o usuário precisa ler uma mensagem.
#:
#: Por que comentário e não frase: nos dois estados o produto **não sabe** o que há na lista, e
#: escrever "nenhum jogo com pendência" afirmaria o resultado de uma leitura que não aconteceu (o
#: defeito que esta aba nasceu para matar). O comentário não é vazio, renderiza como NADA e a tela
#: fica igual ao desenho aprovado, de contêiner vazio.
SEM_LISTA = "<!-- ainda não há lista para este cartão -->"

#: O corpo do cartão da Steam enquanto a primeira leitura não voltou — NÃO é uma frase (razão de
#: :data:`SEM_LISTA`).
#:
#: TELA-CALADA-02, 13/09/2026: aqui morava «Estou lendo a sua biblioteca da Steam…», notícia de
#: fundo em primeira pessoa, e a regra de produto para frases de status vale em todas as abas. Quem
#: diz que a leitura está em curso é o canto do cartão (:data:`AINDA_LENDO`, no `steam-jogos`). `""`
#: viraria travessão no `escrever()` do BOOTSTRAP.
SEM_FRASE = "<!-- a primeira leitura da Steam ainda não voltou -->"

#: A lista de jogos vazia do cartão da Steam — comentário, não frase (desde 22/09/2026).
#:
#: Era «Nada pendente, e você não tirou nem dispensou nenhum jogo.»; saiu para nivelar a altura da
#: Steam com os demais (a frase e a linha de cima custavam 28 px que só ela pagava, 156 contra 128
#: da fileira de baixo) e porque a lista «só aparece quando há o que dizer» (comentário da
#: `.lanc-fora`, em `aba07.py`). Comentário pela razão de :data:`SEM_LISTA` (`""` viraria
#: travessão); não conta para o `:empty`, então `.lanc-fora:not(:empty)` fica sem a borda e sem a
#: margem de cima.
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
    # A `chave` só aparece em atributo aqui (`data-lancador`, `data-campo`), então é escapada como
    # atributo (:func:`_a`).
    k = _a(lanc.chave)
    # A fileira sai numa variável para a linha caber nos 100 caracteres do `ruff`; o HTML é o mesmo
    # caractere por caractere e a moldura de espaço vem de dentro de `acoes_html`, onde o valor
    # pintado e o da grade são UM só.
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


#: O que a linha «PARA QUEM» diz quando a tela abriu pelo botão global (nasce vazia).
#:
#: Mora aqui, no DESENHO da tela estática: o gerador a escreve no `data-campo` e o pacote a repinta
#: com o mesmo texto enquanto não houver cartão apontado. Dizia «Um lançador ou emulador que o
#: Hefesto **ainda não** traz de fábrica», apanhada pelo portão no dia em que nasceu: o «ainda não»
#: põe o sujeito em NÓS e vira confissão de dívida (regra de produto de 07/09/2026: o app funciona e
#: não mostra na tela que o app não presta). O sujeito certo é o usuário: quem chega a esta tela já
#: sabe que o lançador não tem cartão, foi por isso que a abriu.
NOVO_SEM_ALVO = "Um lançador ou emulador que você usa"

#: O que a linha diz quando a tela abriu pelo botão de um CARTÃO (:data:`ADICIONAR_ROTULO`).
#:
#: O `{nome}` é o do cartão e responde à pergunta de quem vê dois campos vazios: *para qual?* Perdeu
#: o artigo em 08/09/2026, e foi a FOTO que mostrou: «Onde está **o** {nome} nesta máquina» valia
#: nos cinco cartões (Heroic, Lutris, Flatpak, RetroArch, Dolphin), mas quando o da STEAM ganhou o
#: botão (:func:`acao_de_localizar`) saiu «o Steam», e a casa escreve **a** Steam em toda a aba. Não
#: se conserta com tabela de gênero: o `{nome}` também vem do que o usuário digita num cartão novo,
#: e adivinhar artigo é palpite na tela dele; a frase sem artigo vale para todo nome. O «ele» FICA:
#: é a palavra do rótulo do campo logo abaixo («Onde ele está»), cujo sujeito é *o lançador*; trocar
#: o pronome faria a linha e o campo falarem de coisas diferentes.
NOVO_PARA_O_CARTAO = "{nome} — onde ele está nesta máquina"


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
    era a dica do campo em prosa (o `placeholder` já mostra `ryujinx · /opt/Ryujinx/Ryujinx ·
    org.ryujinx.Ryujinx`) e o de cima descrevia como o produto PROCURA, mecânica dita de novo pela
    recusa de `_achar_o_que_ela_digitou` quando serve. Sobrou o que ela precisa antes de digitar: o
    que vale, e que o produto confere antes de guardar.
    """
    return f'''<div class="tela-nova" id="{TELA_DO_NOVO}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{_e(TELA_DO_NOVO_TITULO)}</span>
      <span class="ajuda">?<span class="dica">
        Diga o comando, o caminho do programa (é assim que entra um AppImage
        solto) ou o nome do atalho — os três exemplos estão no campo. Confiro no
        disco antes de guardar.
      </span></span>
      <a class="tn-x" href="#" title="Fechar">&times;</a>
    </div>
    <div class="tn-corpo">
      <div class="lanc-novo-para" data-campo="{NOVO_PARA_QUEM}">{_e(para_quem)}</div>
      <label class="lanc-novo-campo">
        <span>Como ele se chama</span>
        <input type="text" data-linha="{NOVO_ROTULO}" placeholder="Ryujinx">
      </label>
      <label class="lanc-novo-campo">
        <span>Onde ele está</span>
        <div class="lanc-novo-linha">
          <input type="text" data-linha="{NOVO_ALVO}"
                 placeholder="Ryujinx  ·  /opt/Ryujinx/Ryujinx  ·  org.ryujinx.Ryujinx">
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
    #: O que a linha diz do jogo — "nunca recebeu", "perdeu", "você tirou".
    porque: str
    #: O botão da linha: `("tirar-daqui", "Não usar neste jogo")` ou o inverso.
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


# O endereço `lanc-quantos` e a função `quantos_html` saíram juntos em 11/09/2026 (A2-002, aprovada
# pelo usuário), com o trecho do "?" que os consumia. O "?" dizia «a resposta vale igual para os 2
# (1 no cabo, 1 no rádio)», e até 03/09 aquele `2` vinha de `monta.CONECTADOS`, a mesa do DESENHO
# congelada no HTML ao lado de um cabeçalho que LIA o aparelho (cura:
# `a07_lancadores.quantos_da_mesa`). A frase inteira saiu: repetia o cabeçalho a dois centímetros
# (`2 controles: 1 USB · 1 BT`), o dono do número, e endereço sem consumidor faz o piloto pintar num
# `data-campo` que a página não tem. Os três saem juntos ou nenhum.


def conta_html(achados: int, impedidos: int) -> str:
    """A contagem do quadro: `N encontrados · M com impedimento`.

    Derivada da lista de cartões que o produto montou, não da que o gerador digitou (a aba dizia "6
    encontrados" contando o cartão que ela mesma carimba `NÃO ACHEI`).
    """
    #: **"localizados", não "encontrados"** (09/09/2026, §5.2): a palavra do cabeçalho é a do selo
    #: `LOCALIZADO`; duas palavras para o mesmo fato obrigariam o usuário a traduzir.
    return (f'{_plural(achados, "localizado", "localizados")} '
            f'<span class="sep">·</span> '
            f'{_plural(impedidos, "com impedimento", "com impedimentos")}')


#: Os endereços que um cartão produz, para a régua da aba os cobrar sem reescrever a lista (régua
#: que digita o que devia LER: o defeito nomeado onze vezes em 26/08).
SUFIXOS = ("-selo", "-jogos", "-diz", "-acoes")
SUFIXO_DA_LISTA = "-fora"


# O que o disco responde, e os seis cartões que saem dele.
#
# Mora no desenho e não no pacote por ferramenta: o gerador `aba07.py` roda como SCRIPT SOLTO e não
# pode importar `pacotes/`, que puxa os dez pacotes e o produto inteiro. Com os cartões aqui o
# gerador emite a página de REFERÊNCIA com `cartoes(None)` (o estado da primeira meia volta, antes
# de a leitura voltar) e o pacote emite os mesmos cartões com o dado real: **um dono, dois dados**,
# sem onde digitar o número.

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
    #: O usuário declarou este lançador (ou ensinou onde este embutido está)?
    #:
    #: Decide o botão de tirar e nada mais: cartão declarado tem de poder sair, ou a lista vira lixo
    #: permanente. Num embutido ensinado, tirar desfaz o ensino e devolve a busca de fábrica: o
    #: mesmo ato, o mesmo botão.
    declarado: bool = False
    #: As classes de janela MEDIDAS do lançador (o ``app_id`` que ele anuncia),
    #: para a linha «todos os jogos» de quem tem um processo só para todos.
    janelas: tuple[str, ...] = ()
    #: A forma do pedaço do título que é de um jogo só (``\bPPSA\d{5}\b``),
    #: quando o lançador vem de uma modificação que a declara.
    titulo_do_jogo: str = ""
    #: O leitor da biblioteca que uma modificação declara (o censo o chama).
    leitor: _censo.LeitorPorProcesso | None = None
    #: O ``id`` da modificação que trouxe este lançador; vazio no de fábrica e no que o usuário
    #: declarou. Sem marca no cartão (escolha do usuário de 09/10/2026, ~16h15): sair é desligar a
    #: modificação, não o «Tirar daqui».
    modificacao: str = ""


#: Os lançadores cujo interior o produto NÃO lê. A lista é dado, não `if`: quando alguém escrever o
#: censo do Heroic, ele SAI daqui e ganha cartão próprio.
#:
#: A prova de 02/09/2026 caducou (*"o `grep -rniE "heroic|lutris|…" src` devolve CINCO linhas fora
#: desta aba, todas COMENTÁRIO"*): remedido em 10/09/2026 são 58, e
#: `integrations/cura_por_estrada.py` LÊ e ESCREVE o `config.json` do Heroic (`_ler_heroic`,
#: `_escrever_no_heroic`, `CHAVE_DO_HEROIC`). A lista continua certa: nomeia o lançador cuja
#: BIBLIOTECA (quais jogos existem lá dentro) o produto não lê, e `cura_por_estrada` escreve
#: VARIÁVEIS DE AMBIENTE na estrada, o outro lado do trabalho. O contrato é
#: `test_os_cinco_lancadores_sem_fonte_continuam_sem_fonte`; `grep` de nome próprio conta MENÇÕES,
#: não leituras.
#:
#: Os identificadores são os de verdade, nas duas formas: o `app-id` do Flatpak (como a máquina do
#: usuário os teria, pelos 54 atalhos em `~/.local/share/flatpak/exports/share/applications`) e o
#: nome nativo do pacote da distribuição.
#:
#: **Não há cartão da Epic — decisão de produto, 08/09/2026.** O usuário pediu, viu o cartão feito e
#: o desfez: quem entrega o jogo da Epic nesta máquina é o Heroic, cujo rótulo já diz «Epic · GOG»,
#: e um cartão da Epic teria de procurar o Heroic para não dizer NÃO LOCALIZADO onde os jogos da
#: Epic abrem: **dois cartões da mesma tela procurando o mesmo programa em disco**. Epic e GOG ficam
#: dentro do Heroic, e o rótulo dele não muda: o «(Epic · GOG)» é o ÚNICO lugar da tela onde a Epic
#: aparece.
SEM_FONTE: tuple[SemCenso, ...] = (
    SemCenso("heroic", "Heroic (Epic · GOG)",
             ("com.heroicgameslauncher.hgl", "heroic"), ("heroic",)),
    SemCenso("lutris", "Lutris", ("net.lutris.Lutris", "lutris"), ("lutris",)),
    SemCenso("flatpak", "Flatpak", (), ("flatpak",)),
    SemCenso("retroarch", "RetroArch",
             ("org.libretro.RetroArch", "retroarch"), ("retroarch",),
             janelas=("com.libretro.RetroArch",)),
    SemCenso("emuladores", "Dolphin · mGBA",
             ("org.DolphinEmu.dolphin-emu", "dolphin-emu", "io.mgba.mGBA",
              "mgba-qt", "mgba"),
             ("dolphin-emu", "mgba-qt", "mgba")),
)

#: A Steam também se procura — 02/09/2026, de uma acusação provada.
#:
#: O cartão da Steam era o único com CENSO e o único cuja PRESENÇA ninguém mediu (`presente=True`
#: constante). Medido com o `HOME` desviado para uma casa de mentira, sem Steam e com o `PATH`
#: vazio:
#:
#:     conta_do_topo = '1 encontrado · 0 com impedimentos'
#:     steam: selo 'ok' (CHEGAM), presente True,
#:            'Os controles chegam. O atalho de inicialização está no lugar em
#:             0 jogos da sua biblioteca.'
#:
#: Máquina SEM Steam recebia o selo VERDE e a promessa de que os controles chegam (a
#: `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em verde), enquanto os outros cinco diziam `NÃO ACHEI`. A cura
#: é a medição que já existia: as mesmas pastas de `.desktop` e o mesmo `PATH` respondem por esta.
#: Ela NÃO entra em :data:`SEM_FONTE` (o interior da Steam o produto LÊ): são duas perguntas,
#: separadas.
#:
#: Identificadores: `steam.desktop` é o do pacote da distribuição (medido nesta bancada, em
#: `/usr/share/applications`), `com.valvesoftware.Steam` o da Flathub e `steam-native` o da
#: instalação sem o runtime. O comando entra pelo mesmo motivo dos outros (nesta bancada é
#: `/usr/games/steam`, fora do `/usr/bin`).
A_STEAM = SemCenso("steam", "Steam",
                   ("steam", "com.valvesoftware.Steam", "steam-native"),
                   ("steam", "steam-native"))

#: Os seis que vêm de fábrica.
#:
#: :data:`SEM_FONTE` responde outra coisa («sei ler a biblioteca dele?») e percorrê-la deixaria a
#: Steam fora da única pergunta que o produto responde sobre todos sem inventar. **Não é a lista que
#: se procura**: quem responde é :func:`procurados` (08/09/2026, com o lançador declarado pelo
#: usuário). O nome antigo `PROCURADOS` morreu de propósito: enquanto uma constante respondesse "o
#: que se procura", quem a lesse por hábito procuraria só os de fábrica e o lançador acrescentado
#: seria invisível, calado e só na máquina do usuário.
EMBUTIDOS: tuple[SemCenso, ...] = (A_STEAM, *SEM_FONTE)


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
        # `dict.fromkeys` e não `set`: ordem preservada, repetido descartado.
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

#: A frase de quem AINDA NÃO PROCUROU — a primeira meia volta, antes de a leitura de disco voltar.
#:
#: Dizia o que falta e agora diz o que FUNCIONA (07/09/2026, regra de produto: o app funciona e não
#: mostra na tela que o app não presta). A antiga abria com «Ainda não sei olhar este lançador» e
#: fechava com «nenhuma linha dele olha para cá hoje», duas confissões em volta do único fato que
#: serve: o perfil casa por processo e por janela, então um jogo aberto de lá entra como qualquer
#: outro (a dívida mora no mapa de canais).
#:
#: **A segunda oração saiu em 11/09/2026 — A2-012, aprovada pelo usuário**: repetia a primeira, e a
#: frase aparece em cinco cartões empilhados. 118 → 50 caracteres, cinco vezes.
DIZ_SEM_FONTE = "<b>O perfil casa pelo nome do processo e pela janela.</b>"


# `DIZ_NAO_ACHEI` (a frase de quem procurou e não achou) mudou de lugar em 11/09/2026 por mecânica:
# com a A2-013 passou a CITAR o botão, ou seja a ler :data:`ADICIONAR_ROTULO`, que em Python tem de
# existir antes. Desde 13/09/2026 é rótulo de estado e não cita o botão; ficou onde estava.

#: O que o cartão da Steam mostra enquanto a primeira leitura não voltou. **Nunca um número**:
#: número ainda não lido é inventado.
AINDA_LENDO = "…"

#: A chave do único cartão com fonte.
STEAM = "steam"

#: O nome do gesto do "Abrir o lançador". Mora aqui porque desenho e pacote precisam do MESMO texto
#: (o desenho o escreve no `data-gesto`, o pacote o registra em `@gesto(...)`); digitá-lo duas vezes
#: dá a botão um endereço que ninguém atende, o que
#: `test_todo_gesto_do_html_tem_dono_ou_esta_declarado_sem_dono` cobra.
ABRIR = "abrir-lancador"

#: O «CONSERTAR» dos outros lançadores morreu aqui — LANCADOR-LOCALIZAR-01, 10/09/2026; caiu o VASO,
#: não a cura.
#:
#: `CONSERTAR_LANCADOR` e `CONSERTAR_LANCADOR_ROTULO` moravam aqui desde 09/09. O cartão era lido
#: como pintado (selo `LOCALIZADO`, moldura `chega`, a frase dizendo que *um jogo aberto por aqui
#: entra pelo mesmo caminho de qualquer outro*) e o botão foi recusado: quem tem tudo instalado e
#: identificado não precisa de botão de consertar, e cura onde a tela não declarou defeito lê-se
#: como cura de coisa nenhuma.
#:
#: **A lacuna continua aberta**, por isso `integrations/cura_por_estrada` fica: `hefesto-launch` só
#: age com jogo da Steam e nenhum jogo do Heroic, Lutris, RetroArch, Dolphin ou mGBA tem um. O vaso
#: certo é a CARONA (decisão de 16/08, `app/actions/carona_do_wrapper.py:7`): sem botão na
#: interface, o ajuste se corrige ao aplicar ou salvar o perfil. Quem a constrói é a
#: LANCADOR-CARONA-01.



# Registrar o que o Hefesto não conhece — 08/09/2026, pedido: um botão para adicionar emulador ou
# lançador novo, para usuários mais experimentais.
#
# A porta é uma só, por desenho: o botão do cartão que não localizou e o global mandam o MESMO
# gesto, e muda o que vai preenchido (o do cartão sabe a chave e o rótulo, o global nasce vazio).
# Dois gestos para o mesmo ato seriam duas validações, duas recusas e duas maneiras de gravar a
# mesma coisa, e a segunda envelheceria calada. O nome mora aqui pela razão de :data:`ABRIR`.
#
# O gesto de REGISTRAR tem duas metades no mesmo clique: sem `forma` só ABRE a tela apontando para
# quem; com `forma`, GRAVA.
ADICIONAR = "adicionar-lancador"

#: O rótulo do botão do cartão — DIZ A PALAVRA DO SELO, de propósito.
#:
#: A palavra veio em duas etapas (08/09/2026): o pedido foi que «Abrir o Lançador» virasse
#: «Adicionar Launcher» (nasceu em inglês e igual ao botão global); olhando a aba, veio «Adicionar
#: novo Lançador» com um sinônimo. Estão atendidos: **português**, **"novo" no que é novo** e **os
#: dois botões falando palavras diferentes**. O selo deste cartão diz `NÃO LOCALIZADO`
#: (:data:`SELOS`), então o botão diz «Localizar»: lido de cima para baixo é uma frase só, *não
#: localizado → localizar este lançador*.
#:
#: **Não instala nada**, como diz a frase do estado NÃO LOCALIZADO (termina em «Instalado de outro
#: jeito (um AppImage solto, por exemplo) ele não aparece aqui»): quer dizer **"ele está aqui, eu te
#: mostro onde"**, o usuário aponta o caminho e o cartão acende. No cartão que ACHOU o botão segue
#: «Abrir o lançador»: dois estados, dois botões (trocar os dois faria o cartão aceso oferecer
#: registro que já existe).
#:
#: **A maiúscula decorativa caiu em 11/09/2026 — A2-021, aprovada pelo usuário**: o «L» no meio da
#: frase não era palavra de produto; o título da tela de registro (:data:`TELA_DO_NOVO_TITULO`) já
#: escrevia «Localizar um lançador» em minúscula, e duas grafias para uma palavra é o que o item 4
#: da §2 do índice proíbe.
ADICIONAR_ROTULO = "Localizar este lançador"

#: O rótulo do mesmo botão no cartão JÁ LOCALIZADO — 11/09/2026, **A2-022, aprovada pelo usuário**.
#:
#: O selo dizia `LOCALIZADO` e o botão logo abaixo mandava **localizar**: lidos de cima para baixo,
#: se contradiziam. Mesmo gesto, mesma gravação, **só o rótulo segue o estado** (como «Não usar
#: neste jogo»/«Voltar a usar» e «Voltar a perguntar»/«Não perguntar para este jogo»); o ato aqui é
#: CORRETIVO (o que o produto achou não é o que o usuário quer) e o rótulo o diz.
#:
#: **Encolheu em 21/09/2026**, palavra de produto: os 4 botões em uma linha só (a fileira tem 531 px
#: no WebKit e os quatro somavam ~680); a frase inteira foi para o `title` (:data:`APONTAR_DICA`).
APONTAR_ROTULO = "Outro caminho"
APONTAR_DICA = "Apontar outro caminho para este lançador"

#: A frase de quem PROCUROU E NÃO ACHOU.
#:
#: Diz «não localizei» desde 08/09/2026, pela razão do selo: a palavra de produto é «não localizei»,
#: e a tela dizia a recusada em DOIS lugares (o selo, em maiúsculas, e a primeira oração daqui). **O
#: nome da constante fica**: nomeia o ESTADO ("procurei e não achei"), lido por réguas que perguntam
#: pelo estado.
#:
#: **Encurtada em 11/09/2026 — A2-013, aprovada pelo usuário**: 262 → 112 caracteres que explicavam
#: a MECÂNICA (as duas buscas estão ditas outras DUAS vezes na aba: o `?` da tela de registro e a
#: recusa de :func:`~...a07_lancadores._achar_o_que_ela_digitou`, onde o fato serve). Continua sem
#: afirmar que o lançador não está na máquina («onde sei procurar» guarda o cuidado da frase longa:
#: um AppImage solto, um script no `~/bin`).
#:
#: **Virou rótulo de estado em 13/09/2026 — FRASES-E-DICAS-02, §I.5**: a de 11/09 falava em primeira
#: pessoa e mandava usar o botão; a ordem de 13/09 (índice da terceira lista) tira instrução e
#: narração da tela. O selo já diz NÃO LOCALIZADO e o botão ao lado é a saída; o corpo diz só onde o
#: produto não achou, até seis palavras, sem primeira pessoa nem mando (régua `_e_rotulo_de_estado`
#: de `tests/unit/test_o_cartao_da_steam_nao_narra.py`).
DIZ_NAO_ACHEI = "<b>Fora dos caminhos conhecidos</b>"

#: O corpo do cartão da Steam quando a biblioteca existe e não abriu (mesmo dia e régua de
#: :data:`DIZ_NAO_ACHEI`). Dizia, em primeira pessoa, que não conseguiu ler, o erro cru e que nada
#: foi alterado; o erro segue em `Leitura.erros` e o «Procurar de novo» no cartão.
DIZ_NAO_LI = "<b>Biblioteca da Steam ilegível</b>"

#: O rótulo do botão GLOBAL — o que nasce vazio, para o que o Hefesto não conhece de fábrica.
#:
#: É o outro ato: este diz «tem um que você não conhece», o do cartão «ele está aqui, te mostro
#: onde» (dois botões com a mesma frase fazem quem lê procurar a diferença que a tela não mostra). A
#: palavra «novo» era do usuário e distinguia (o que entra por aqui não tem cartão), e caducou em
#: 11/09/2026; «emulador» saiu do rótulo sem perder o público, pois a dica da tela de registro
#: nomeia os dois casos e o exemplo (`Ryujinx`) é um emulador.
#:
#: **Os dois passaram a dizer o mesmo — 11/09/2026, aprovado pelo usuário**: o botão dizia
#: «Adicionar novo Lançador» e a tela que ele abre «Localizar um lançador» (dois nomes para a mesma
#: tela, e maiúscula decorativa); ambos são «Adicionar um lançador». Duas propostas aprovadas se
#: encontraram: a A2-005 pedia só a minúscula e dava o título da tela por «mantido» (olhou o botão
#: sozinho), a B1 olhou os DOIS endereços e viu o nome duplo; a minúscula da A2 está dentro desta, e
#: vale a regra *quando a cura conhece a causa, ela cobre todos os chamadores*.
ADICIONAR_NOVO_ROTULO = "Adicionar um lançador"

# O seletor do sistema — LANCADOR-LOCALIZAR-01, 10/09/2026, decisão de produto: o usuário abre a
# tela do sistema e procura o `.desktop`.
#
# Ele escolheu a opção (C), **campo + botão que abre o seletor**; o campo FICA, único caminho para
# um AppImage solto, que não tem `.desktop`, e o cartão promete cobrir esse caso. Não é capacidade
# nova: `ponte.escolher_arquivo` é ponto de extensão que o piloto preenche ao subir
# (`hefesto_vivo.py`, `ponte.escolher_arquivo = self._escolher_arquivo`), com precedente no
# «Importar» do rodapé.
#
# O gesto do botão que abre o seletor mora aqui pela razão de :data:`ABRIR`.
PROCURAR_O_ARQUIVO = "procurar-o-arquivo"

#: O rótulo NÃO diz «Procurar…» de propósito (medido nesta aba): «Procurar de novo» é o botão do
#: topo do quadro e quer dizer «varra a máquina outra vez», a busca automática sobre os SEIS
#: cartões; este quer dizer «eu te mostro o arquivo», sobre UM. Duas palavras iguais para atos
#: diferentes na mesma tela quebra "mesma família, mesma coisa" (o `.lanc .btn` que encolhia). É
#: texto de tela, a conferir na bancada: trocar por «procuro o .desktop» é mudar esta linha, o
#: gesto, a recusa e a régua não dependem do rótulo.
PROCURAR_O_ARQUIVO_ROTULO = "Escolher o arquivo…"

#: O título da caixa de registro, que é o rótulo do botão GLOBAL (desde 11/09/2026, aprovado pelo
#: usuário: um nome por tela).
#:
#: Até 11/09 era neutro («Localizar um lançador») para não ser o rótulo de NENHUM dos dois botões. A
#: decisão de 11/09 pesa mais para o global (botão e destino com nomes diferentes fazem duvidar de
#: onde se chegou); o que a medição de 08/09 travava continua travado: a palavra «novo» saiu do
#: título, e é ela que contradizia a linha de baixo.
#:
#: A caixa é UMA e os caminhos são DOIS (ver :func:`tela_do_registro_html`). Com os atos separados
#: pela palavra de produto, aberta pelo botão do cartão do RetroArch (:data:`ADICIONAR_ROTULO`) a
#: caixa mostraria :data:`ADICIONAR_NOVO_ROTULO` («novo») sobre a linha «Onde está o RetroArch nesta
#: máquina»: **duas células da mesma tela dizendo o contrário uma da outra**, o defeito que esta aba
#: existe para matar. O título neutro não é evasiva, é o que o gesto FAZ nos dois caminhos:
#: `a07_lancadores.adicionar_lancador` procura em disco antes de gravar e **recusa o que não acha**.
#: A linha logo abaixo (:data:`NOVO_PARA_QUEM`) diz de qual dos dois se trata.
TELA_DO_NOVO_TITULO = "Adicionar um lançador"

#: O gesto de TIRAR. *O que se acrescenta se tira*: sem ele a lista vira lixo permanente, e cartão
#: que o usuário não remove é pior que a ausência dele.
REMOVER = "esquecer-lancador"

#: O rótulo do TIRAR. «Tirar daqui» é a palavra que esta aba JÁ usa para o mesmo ato na lista de
#: jogos do cartão da Steam; uma segunda seria a terceira maneira de dizer a mesma coisa numa tela
#: só.
REMOVER_ROTULO = "Tirar daqui"

#: O `id` da tela de registro, alvo do `href="#…"` que ABRE a pop-up (`.tela-nova` só aparece em
#: `:target`, sem script; `monta.CSS_POPUP`). `id` e `href` saem daqui para não divergirem: `href`
#: para `id` inexistente abre NADA e o clique some sem uma palavra.
TELA_DO_NOVO = "novo-lancador"

#: Os dois campos que o usuário digita são `data-linha`, **nunca `data-campo`**.
#:
#: O piloto recolhe a forma por `[data-linha],[data-campo]` e chaveia pelo primeiro que existir
#: (`hefesto_vivo.py`, bloco `forma:`), então `data-linha` basta para o valor chegar ao Python. Não
#: pinta: um `data-campo` num `<input>` seria repintado a cada tique (dez vezes por segundo) por
#: cima do que o usuário digita, o samba que a `A-TELA-SAMBA-01` mediu, que num campo de texto apaga
#: a frase no meio.
NOVO_ROTULO = "lanc-novo-rotulo"
NOVO_ALVO = "lanc-novo-alvo"

#: A linha que diz PARA QUEM a tela de registro está aberta. É `data-campo` de verdade: TEXTO do
#: produto, o usuário não digita nela.
NOVO_PARA_QUEM = "lanc-novo-para-quem"


# Os botões do Steam Input e do reparo saíram do cartão — 21/09/2026.
#
# Moravam aqui os nomes e rótulos do «Desligar o Steam Input», do «Deixar tudo pronto» e do «Copiar
# a linha» (e, até a tarde, do «Este jogo não funciona»). Palavra de produto: os mesmos botões para
# todos os lançadores, sempre. O produto faz sozinho o que eles faziam à mão (o guarda desliga o
# Steam Input e o vigia repõe o atalho, `hefesto-steam-input-guard`), e a marca do Steam Input por
# jogo segue no chip da aba Jogar.


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

    #: A linha de baixo de cada cartão, por chave: `(chave, linha)`. Já é a resposta final,
    #: inclusive a do «Flatpak» (outra pergunta, ver :func:`resposta_do_flatpak`). Chave AUSENTE =
    #: nada a dizer, e o cartão fica com o travessão.
    resumos: tuple[tuple[str, str], ...] = ()
    #: Quantos jogos de cada cartão já têm ponte confirmada: `(chave, n)`.
    #: Ver :func:`contador_html`.
    pontes: tuple[tuple[str, int], ...] = ()

    #: O campo `estradas` saiu — LANCADOR-LOCALIZAR-01, 10/09/2026. Guardava as chaves que TÊM por
    #: onde receber o ambiente, só para decidir o botão «Consertar» do cartão LOCALIZADO, que saiu
    #: por palavra de produto. Campo que ninguém lê seria a segunda leitura de disco que a
    #: :class:`DoDisco` existe para não pagar (`estradas_do_cartao` abre o `config.json` do Heroic e
    #: as caixas do Flatpak a cada volta da vigia).

    #: Onde o ambiente do Hefesto falta, por cartão: `(chave, onde)` —
    #: AS-SOLUCOES-NOS-LANCADORES-01, 01/10/2026. No Heroic, os jogos instalados sem ele; nas caixas
    #: do Flatpak, a caixa. Mede o dono da estrada (`cura_por_estrada.onde_falta_o_ambiente`), na
    #: vigia. Chave ausente = está no lugar (ou não há estrada).
    sem_ambiente: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def resumo(self, chave: str) -> str:
        return dict(self.resumos).get(chave, "")

    def pontes_de(self, chave: str) -> int:
        return dict(self.pontes).get(chave, 0)

    def sem_ambiente_de(self, chave: str) -> tuple[str, ...]:
        return dict(self.sem_ambiente).get(chave, ())


#: A resposta vazia: a primeira meia volta e o padrão de toda `Leitura` montada à mão. SINGLETON
#: porque :class:`DoDisco` é congelada (duas instâncias vazias são a mesma coisa) e chamada em
#: argumento padrão o `B008` recusa.
SEM_DISCO = DoDisco()


def medir_no_disco(onde_estao: tuple[tuple[str, str], ...],
                   declarados: tuple[SemCenso, ...] = (),
                   lar: Path | None = None,
                   raiz_sistema: Path | None = None,
                   com_ponte: frozenset[str] = frozenset()) -> DoDisco:
    """BLOQUEIA — abre os arquivos dos lançadores e responde o que o cartão mostra.

    Quem chama é a VIGIA e só ela (`a07_lancadores._Vigia.ler`, thread de fundo); da pintura é o
    defeito medido em :class:`DoDisco`. Só o que foi ACHADO entra: cartão sem caminho em
    `onde_estao` é lançador que a busca não achou (ou não procurou), e perguntar pela biblioteca de
    programa ausente é abrir pastas para ouvir "não existe".

    :param lar: o `HOME` a inspecionar (padrão: o de verdade). A régua passa um lar de mentira,
    junto com `raiz_sistema`, para a medição ficar inteira dentro do `tmp`. :param com_ponte: as
    classes de janela (em `casefold`) com ponte confirmada num perfil
    (`prontuario_dos_jogos.classes_com_ponte`), o que o contador de cada cartão conta
    (:func:`contador_html`).
    """
    onde = dict(onde_estao)
    itens = [x for x in procurados(declarados) if x.chave != STEAM]
    #: Os `app-id` dos lançadores que vieram do Flatpak, de que o cartão «Flatpak» precisa para
    #: mudar de pergunta (§5.4).
    #:
    #: Saem do CAMINHO em que cada `.desktop` foi achado, não do rótulo do cartão: um `io.mgba.mGBA`
    #: publicado por `/usr/share/applications` é o pacote da distribuição, sem caixa a examinar
    #: (:func:`sandbox_dos_lancadores.app_id_do_atalho`). **Um cartão pode ser dois programas**:
    #: `app_ids_do_cartao` completa o `.desktop` da busca com os demais `app-id` do cartão que têm
    #: caixa no disco; sem isso o «Dolphin · mGBA» entrava com UM e o cartão «Flatpak» contou 4 numa
    #: máquina com 5 (medido em 09/09/2026).
    vistos: list[str] = []
    for item in itens:
        # O próprio Flatpak fica de fora: é achado pelo `PATH` (`/usr/bin/flatpak`), não tem caixa,
        # e examinar a si mesmo responderia sobre a coisa errada.
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
        #: A leitura e o resumo são do dono (`integrations/censo_dos_lancadores`): montar a frase
        #: aqui seria a segunda verdade sobre a mesma contagem ("37 jogos" contra "37 na biblioteca"
        #: na mesma tela).
        biblioteca = _censo.biblioteca_do_cartao(item.chave, lar, leitor=item.leitor)
        linha = biblioteca.resumo
        #: **A linha do «Flatpak» é outra pergunta — §5.4, 09/09/2026**: ele não tem biblioteca (o
        #: censo diz `SEM_BIBLIOTECA`, resumo vazio) e a linha dele ficava com travessão.
        if not linha and item.chave == "flatpak":
            linha = caixas
        if linha:
            resumos.append((item.chave, linha))
        # Uma janela conta uma vez: o emulador tem um processo para todas as ROMs e a biblioteca
        # repete a mesma classe em cada linha.
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

    #: appids cuja linha de inicialização JÁ chama o wrapper.
    com_wrapper: tuple[str, ...] = ()
    #: os que não chamam e o produto CONSEGUE repor: `(appid, rótulo, porquê)`.
    reparaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que não chamam e ninguém deve tocar (lista de IGNORE estendida à mão).
    intocaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que o usuário tirou, no `jogos_sem_wrapper.txt`: `(appid, rótulo)`.
    recusados: tuple[tuple[str, str], ...] = ()
    #: os que o usuário dispensou do LEMBRETE, no `launch_dialog_dismissed.json`:
    #: `(appid, rótulo)`. É outra lista e outra pergunta — ver `lista_de_jogos`.
    dispensados: tuple[tuple[str, str], ...] = ()
    #: quantos jogos estão INSTALADOS — o vdf guarda linha de jogo desinstalado.
    instalados: int = 0
    #: Quantos jogos já têm PONTE CONFIRMADA no perfil (`prontuario_dos_jogos.pontes_confirmadas`),
    #: a fonte do carimbo que o desenho prometia (`◆ 3 jogos já sabem por onde entrar`) e que nasceu
    #: digitado: medido em 02/09/2026, o produto respondia ZERO.
    pontes: int = 0
    #: Onde cada lançador PROCURADO foi achado: `(chave, local)`. Local vazio = **procurei e não
    #: achei**; chave AUSENTE = **não procurei**; a distinção vira frases diferentes na tela. A
    #: `steam` entrou no mapa em 02/09 (:data:`A_STEAM`).
    onde_estao: tuple[tuple[str, str], ...] = ()
    #: O que o usuário declarou no `maquina.json` — 08/09/2026: lançador que o Hefesto não conhece
    #: de fábrica, ou o ENSINO de onde um de fábrica está. Vem pela `Leitura` e não por import (o
    #: desenho não importa o produto); `Leitura` montada à mão não declara nada e só os de fábrica
    #: viram cartão.
    declarados: tuple[SemCenso, ...] = ()
    #: O campo `frase` saiu — TELA-CALADA-02, 13/09/2026: trazia a frase da sentinela ao corpo do
    #: cartão, pintada a cada tique sem clique; o corpo passou a dizer só a contagem
    #: (:func:`cartao_da_steam`) e campo que ninguém lê seria a vigia montando frase para ninguém.
    #:
    #: A linha de inicialização do Hefesto (`steam_launch_options.WRAPPER_LAUNCH`) é o que o bloco à
    #: mostra exibe no jogo de linha editada à mão; vem por aqui porque o desenho não importa o
    #: produto. Vazia é resposta: o cartão não mostra o bloco. Os dois campos do Steam Input
    #: (`steam_input`, `steam_input_ligado`) saíram em 21/09/2026 com a linha e os botões dele
    #: (bloco «OS BOTÕES DO STEAM INPUT E DO REPARO SAÍRAM DO CARTÃO»).
    linha: str = ""
    erros: tuple[str, ...] = ()
    #: O que o disco diz dos outros cartões, medido na mesma passada da vigia (:class:`DoDisco`).
    #: Vazio é resposta e é a primeira meia volta: cartão sem linha fica com o travessão e sem o
    #: «Consertar», o que leitura que não aconteceu autoriza a tela a dizer.
    do_disco: DoDisco = SEM_DISCO

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
    "tirar daqui" um jogo já fora do reparo não mudaria nada (botão que finge). Os dispensados TÊM
    botão (02/09/2026, decisão de produto): são o `launch_dialog_dismissed.json`, escrito pelo *"Não
    perguntar para este jogo"* do lembrete da GTK, que nenhuma tela mostrava. Mostrar curou o
    silêncio pela metade, pois a dispensa seguia SEM VOLTA pela tela (o motor só tinha
    `add_dismissed_appid`); agora há o par `remove_dismissed_appid` e a linha ganha *"Voltar a
    perguntar"*, como o "Voltar a usar" ao lado do "Não usar neste jogo" (*gesto que só vai numa
    direção deixa a pessoa presa no estado em que clicou*).

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
        # «Você tirou», não «você tirou este jogo» — A2-029, 11/09/2026: a linha já nomeia o jogo.
        # 20 → 10.
        JogoNaLista(appid=a, rotulo=r, porque="você tirou",
                    gesto="voltar-a-usar", botao="Voltar a usar")
        for a, r in lida.recusados
    ]
    itens += [
        # Idem — A2-029/A2-030: o nome do jogo está na mesma linha. 44 → 30.
        JogoNaLista(appid=a, rotulo=r,
                    porque="você mandou não perguntar mais",
                    gesto="voltar-a-perguntar", botao="Voltar a perguntar")
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


# Os lançadores iguais — OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01.
#
# Pedido de produto de 21/09/2026: todos os lançadores com os mesmos botões e textos da Steam,
# adaptados a eles, e o «Este jogo não funciona» vira «Adicionar jogo a lista de exclusão do Hefesto
# (cujo objetivo é garantir que tal jogo não use nenhuma feature do hefesto)». Desenho APROVADO no
# mesmo dia (fotos «os-lancadores-iguais»). A fileira é de quatro nos oito cartões: abrir, criar
# perfil, apontar outro caminho, excluir. A função do «Este jogo não funciona» (lista do Steam
# Input) não se perde: o chip «Steam Input» da aba Jogar escreve a mesma lista, jogo por jogo.

#: A pop-up da escolha do jogo — UMA para a aba, como a do registro. Chega-se a ela por dois botões
#: (excluir e criar perfil), e o conteúdo inteiro (título, lista, confirmar) é repintado pelo pacote
#: ao abrir, porque a lista é do lançador clicado.
TELA_DA_ESCOLHA = "escolher-jogo"
#: O miolo da pop-up, que o pacote troca por `blocos` (HTML inteiro). É também
#: o recipiente que o `data-hef-forma` do confirmar recolhe.
MIOLO_DA_ESCOLHA = "lanc-escolha"
#: O `data-linha` de cada opção da lista — o `value` é a chave do jogo.
ESCOLHA = "lanc-escolha-jogo"

EXCLUIR = "adicionar-a-exclusao"
#: O rótulo é o nome da LISTA, e o ato é o título da pop-up (:data:`EXCLUIR_TITULO`) — 21/09/2026,
#: os quatro numa linha só. «Excluir» sozinho não entrou: em português, «excluir um jogo» é APAGAR o
#: jogo.
EXCLUIR_ROTULO = "Lista de exclusão"
EXCLUIR_TITULO = "Adicionar à lista de exclusão"
#: A frase do §3 da sprint, no `title` do botão; o rótulo é mais curto por largura (os quatro da
#: fileira cabem numa linha).
DICA_EXCLUIR = (
    "Adicionar jogo à lista de exclusão do Hefesto: o jogo passa a ver o "
    "controle como se o Hefesto não estivesse instalado — sem máscara, sem "
    "perfil, sem luz, sem vibração do Hefesto, sem Proton fixado. «Tirar da "
    "lista» devolve tudo.")
CONFIRMAR_EXCLUSAO = "confirmar-exclusao"
CONFIRMAR_EXCLUSAO_ROTULO = "Adicionar à lista"

CRIAR_PERFIL = "criar-perfil-para-um-jogo"
CRIAR_PERFIL_ROTULO = "Criar perfil"
#: O título da pop-up e o `title` do botão — a frase inteira mora onde cabe.
CRIAR_PERFIL_TITULO = "Criar perfil para um jogo"
CONFIRMAR_PERFIL = "confirmar-perfil"
CONFIRMAR_PERFIL_ROTULO = "Criar o perfil"

TIRAR_DA_EXCLUSAO = "tirar-da-exclusao"
TIRAR_DA_EXCLUSAO_ROTULO = "Tirar da lista"
#: O pé do cartão só existe com jogo excluído — 21/09/2026, palavra de produto: sai o status de uma
#: linha só («nenhum jogo na lista de exclusão»). A frase do vazio saiu daqui e de
#: :func:`rodape_da_exclusao_html`, que devolve nada para a lista vazia.


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


#: A nota dos emuladores — um processo para todas as ROMs (§4.3 da sprint).
NOTA_DO_EMULADOR = (
    "Todos os jogos abrem na mesma janela do emulador, e o Hefesto não sabe "
    "qual deles está aberto. Por isso a exclusão vale para o emulador inteiro.")
NENHUM_JOGO_PARA_ESCOLHER = (
    "Nenhum jogo aqui ainda. Quando houver, eles aparecem nesta lista.")
#: O que a lista diz sobre o jogo da escada (§4.3): o jogo aberto já marcado.
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
        # A linha do emulador nasce marcada por ser a única, não por ter sido aberta.
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
        # O confirmar do perfil é uma âncora para a aba Perfis: o mesmo clique manda o gesto (o
        # ouvinte do piloto não chama `preventDefault`) e troca de aba —
        # D-2109-O-CRIAR-PERFIL-LEVA-A-ABA-PERFIS.
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
      <span class="tn-tit">{_e(titulo)}</span>
      <span class="ajuda">?<span class="dica">{_e(DICA_EXCLUIR if excluir else
        "Um gravador só: o perfil é criado pela aba Perfis.")}</span></span>
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


def tela_da_escolha_html() -> str:
    """A casca da pop-up; o miolo chega pelo pacote (:func:`miolo_da_escolha_html`)."""
    return (f'<div class="tela-nova" id="{TELA_DA_ESCOLHA}">\n'
            f'  <div class="tn-cx" id="{MIOLO_DA_ESCOLHA}">'
            f"{miolo_da_escolha_html(EXCLUIR, '', [])}</div>\n</div>")


#: O CSS das peças novas, o do desenho aprovado, com a `.excl-nota` na letra do corpo da caixa
#: (defeito da página de proposta, §9 da sprint).
CSS_DA_EXCLUSAO = """
  .lanc-excl{font-size:11px;line-height:1.5;color:var(--fg);opacity:.85}
  .lanc-excl b{font-weight:600}
  .lanc-excl a.tirar{color:inherit;text-decoration:underline}
  .excl-lista{max-height:46vh;overflow:auto;display:flex;flex-direction:column;
    gap:4px;margin:10px 0;padding-right:6px}
  .excl-jogo{display:flex;gap:10px;align-items:center;padding:6px 10px;font-size:12px;
    border:1px solid rgba(255,255,255,.08);border-radius:8px;cursor:pointer}
  .excl-jogo:hover{border-color:rgba(255,255,255,.22)}
  .excl-tag{font-size:.78em;opacity:.65;margin-left:8px}
  .excl-tag.ok{opacity:1;color:var(--verde, #3fd98a)}
  .excl-nota{font-size:12px;opacity:.8;margin-top:8px;line-height:1.45}
"""


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
    # A fileira é a que o usuário aprovou, botão por botão: o cartão `CHEGAM` do desenho tem `Abrir
    # o lançador` + `Criar perfil para um jogo`, e o `NÃO CHEGAM` tem `Consertar` + `Ver o que
    # impede` + `Abrir o lançador`. Sem `Procurar de novo` aqui: já está no topo do quadro, e um
    # segundo botão com o mesmo texto na mesma tela quebra "mesma família, mesma coisa" (o `.lanc
    # .btn` que encolhia); a exceção é o cartão em ERRO, o único estado em que responde uma pergunta
    # que o cartão fez. O botão ganhou endereço em 03/09/2026 (decisão 17, gesto isento da prova
    # automática): atende `a07_lancadores.abrir_lancador`, e o `v` diz QUAL lançador, pois o texto é
    # o mesmo nos seis.
    abrir = Acao("Abrir o lançador", "", ABRIR, STEAM)
    # O «Criar perfil» ganhou gesto em 21/09/2026 (era o botão sem endereço que o §2.2 da sprint dos
    # lançadores nomeou, morto na Steam também): ver :func:`acao_de_criar_perfil`.
    criar = acao_de_criar_perfil(STEAM)
    # E o tirar, só onde há o que tirar (regra dos outros cinco, :func:`cartao_sem_censo`): só
    # depois de ensinar onde a Steam está; sem declaração a esquecer o botão fingiria. `Leitura`
    # montada à mão não declara nada, então o ramo sai vazio em toda régua antiga e na página
    # publicada (que nasce de `cartoes(None)`).
    tirar = ((acao_de_tirar(STEAM),)
             if any(x.chave == STEAM for x in (lida.declarados if lida else ()))
             else ())
    # O `fora=SEM_LISTA` dos dois ramos é cura: sem ele o `steam-fora` sai vazio, o `escrever()` do
    # bootstrap o troca por `—` e a tela ganha um traço solto no pé do cartão (:data:`SEM_LISTA`).
    if lida is None:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos=AINDA_LENDO,
            # O corpo cala enquanto lê — TELA-CALADA-02 (:data:`SEM_FRASE`).
            diz=SEM_FRASE,
            acoes=(abrir, criar), fora=SEM_LISTA, tem_lista=True)
    if lida.onde_esta_a_steam == "" and not lida.viu_a_biblioteca:
        # Procurei e não achei, com o rótulo MESMO dos outros cinco (:data:`DIZ_NAO_ACHEI`): segunda
        # redação do mesmo fato seria texto de tela não decidido, duas frases que envelhecem
        # separadas (decisão 14, "uma frase, um dono").
        #
        # O botão é o «Localizar» e não o «Abrir» (08/09/2026, era um BECO): o produto não abre
        # Steam que não achou, e o botão global recusava mandando usar um botão que este cartão não
        # tinha (:func:`acao_de_localizar`).
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
        # O corpo diz o ESTADO, não a história — TELA-CALADA-02, 13/09/2026.
        #
        # Ia a frase inteira da sentinela a cada tique, sem clique («2 jogos nunca receberam as
        # Opções de Inicialização do Hefesto na Steam: … Feche a Steam e eu reponho.»); o pedido foi
        # tirar as frases de status de todas as abas. Nada se perdeu: o NOME de cada jogo está na
        # lista do cartão (`lista_de_jogos`, com o motivo e o «Não usar neste jogo»), o selo `COM
        # IMPEDIMENTO` e o «Consertar» continuam, e a frase da sentinela segue sendo a RECUSA do
        # «Consertar», quando responde a um clique. «Sem o atalho», não «sem o atalho de
        # inicialização do Hefesto»: a régua é de até seis palavras e a linha de cada jogo já diz
        # «nunca recebeu o atalho» (`a07_lancadores._porque`).
        diz = f"<b>{_plural(falta, 'jogo', 'jogos')} sem o atalho</b>"
        # O «Consertar» e o «Ver o que impede» saíram — 21/09/2026, palavra de produto: os mesmos
        # botões para todos os lançadores. O reparo é do vigia (`hefesto-steam-input-guard`, a cada
        # 30 min e a cada escrita da Steam), que na mesma noite repôs o atalho do PRAGMATA sem
        # clique. O motivo de cada jogo está na lista do pé do cartão.
        selo = "warn"
    else:
        # Dois números que se contradiziam a uma linha de distância — achado em 03/09/2026 na foto
        # do produto, decisão de produto (PO, 04/09/2026, `07[04]`): o corpo nomeia o conjunto.
        #
        #     canto do cartão   22 jogos instalados       (`lida.instalados`)
        # corpo do cartão   …está no lugar em 63 jogos da sua biblioteca.
        # (`len(lida.com_wrapper)`)
        #
        # As duas afirmações são VERDADEIRAS ("biblioteca" inclui o que não está instalado) e a tela
        # não dava como saber. Três palavras, zero linha nova, nenhum botão: a frase passa a dizer
        # que contam coisas diferentes. As outras duas opções morreram por medição: contar só
        # instalados apagaria as dezenas de jogos já preparados, e pôr os dois números no canto
        # disputa a linha com o selo em janela estreita.
        #
        # A frase do atalho saiu em 21/09/2026 (todos os cartões iguais): o corpo de todo cartão
        # localizado é o MESMO contador (:func:`contador_html`), e o que o usuário precisa saber
        # quando o atalho falta segue dito no ramo de cima, em laranja.
        diz = ""
        # O selo da Steam é `LOCALIZADO` como o dos outros cinco — 11/09/2026, ordem de produto. O
        # `CHEGAM` era a última sobra de quando o selo respondia DUAS perguntas ao mesmo tempo
        # («está aqui?» e «o controle chega?»); os outros cinco foram separados em 09/09
        # (`D-0809-O-SELO-DOS-LANCADORES-DIZ-LOCALIZADO`) e a Steam ficou com uma palavra só dela. O
        # veredito não se perdeu: o `warn` (`NÃO CHEGAM`) nasce com impedimento e o corpo segue
        # dizendo em quantos jogos o atalho está no lugar.
        selo = "localizado"

    # A linha do Steam Input saiu do cartão — 21/09/2026, com os botões «Desligar o Steam Input» e
    # «Deixar tudo pronto». O guarda desliga o Steam Input (`hefesto-steam-input-guard`) e o que é
    # por jogo mora no chip «Steam Input» da aba Jogar.

    # Linha à mostra, só quando faz falta — PO, 04/09/2026, `07[01]`.
    #
    # O estado é o da linha INTOCÁVEL, não o da recusa do Consertar (essa metade caiu em 03/09,
    # quando a recusa passou a armar uma vigia que repõe sozinha, hoje o
    # `hefesto-steam-input-guard`). Sobram os intocáveis, jogos que o produto decidiu nunca tocar
    # (`apply_wrapper_vdf_text` os pula) e para os quais o carimbo escreve «N jogos com a linha
    # intocável — só reparo manual»: reparo manual prometido sem caminho, e **não existia UM botão
    # de copiar em toda a interface nova**. Cópia e linha, os dois, porque pôr texto na área de
    # transferência pode falhar em SILÊNCIO e a linha à mostra ainda salva (a janela velha faz o
    # mesmo aviso). Sem intocáveis o cartão sai byte a byte como antes. O «Copiar a linha» saiu em
    # 21/09/2026 com os outros botões do estado; a linha fica à mostra.
    if lida.intocaveis and lida.linha:
        diz = diz + linha_do_wrapper_html(lida.linha)

    # O «Localizar» entra nos dois estados bons — LANCADOR-LOCALIZAR-01, 10/09/2026, o MESMO botão
    # dos outros cinco.
    #
    # Já estava no `off` desde 08/09 e faltava aqui: com a Steam ACHADA mas diferente da que o
    # usuário quer, não havia por onde dizer, e a recusa do botão global confessava na tela («hoje o
    # cartão não tem por onde trocar»), o que a decisão de 07/09 proíbe. Regra de 05/09: *quando a
    # cura conhece a causa, ela cobre TODOS os chamadores* (:func:`acao_de_localizar`). Vem depois
    # do que ela FAZ e antes do que ela DESFAZ: localizar de novo é ato corretivo e não disputa a
    # primeira posição com o «Abrir». O rótulo é o do estado localizado (:data:`APONTAR_ROTULO`),
    # pois este ramo só se alcança com a Steam achada ou a biblioteca lida (A2-022).
    #
    # A fileira comum vem PRIMEIRO e INTEIRA (21/09/2026): a Steam compunha a dela peça por peça e o
    # ramo do reparo perdeu o «Criar perfil» sem ninguém ver, pois a régua dos oito cartões só
    # olhava o dia bom. Os quatro vêm do MESMO dono dos outros sete (:func:`fileira_comum`) e os
    # botões do estado saíram na mesma noite.
    acoes = fileira_comum(STEAM)
    # O contador abre o corpo, como nos outros sete (:func:`contador_html`).
    diz = contador_html(lida.pontes) + (f"<br>{diz}" if diz else "")

    # O tirar vai por último nos dois estados bons: o que ela desfaz nunca disputa a primeira
    # posição com o que ela FAZ.
    acoes = (*acoes, *tirar)

    return Lancador(
        chave=STEAM, nome="Steam", selo=selo,
        jogos=_plural(lida.instalados, "jogo instalado", "jogos instalados"),
        diz=diz, acoes=acoes,
        fora=lista_de_jogos(lida), tem_lista=True,
        # Era `True` cravado, o que fazia a conta do topo dizer "1 encontrado" numa máquina sem
        # Steam. Basta UMA das respostas (achei o lançador em disco, ou li a biblioteca dele); o
        # ramo de cima já devolveu quando as duas são negativas, e escrever a conta mesmo assim
        # impede a constante de voltar por descuido.
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
    # «Localizar este lançador» é o botão do estado NÃO LOCALIZADO — 08/09/2026. NÃO abre nada:
    # registra onde o lançador está. Ser FUNÇÃO e não linha é o que evita repetir o esquecimento da
    # Steam (:func:`acao_de_localizar`).
    localizar = (acao_de_localizar(item.chave),)
    # O mesmo botão com o rótulo do outro estado — A2-022, 11/09/2026 (:data:`APONTAR_ROTULO`: mesmo
    # gesto, mesma tela, mesma gravação). O tirar, só onde há o que tirar: o cartão que o usuário
    # ensinou; nos de fábrica não há declaração a esquecer, e botão sem o que fazer é o que finge.
    tirar = (acao_de_tirar(item.chave),) if item.declarado else ()
    if onde is None:
        return Lancador(chave=item.chave, nome=item.nome, selo="nao_sei",
                        jogos="—", diz=DIZ_SEM_FONTE, acoes=abrir + tirar)
    if not onde:
        return Lancador(chave=item.chave, nome=item.nome, selo="off",
                        jogos="—", diz=DIZ_NAO_ACHEI,
                        acoes=localizar + tirar)
    #: **O censo entra aqui — LANCADORES-ZERO-01 §5, 09/09/2026.** Era `selo="nao_sei", jogos="—"`
    #: para todo lançador ACHADO. Agora o selo diz `LOCALIZADO` e a linha de baixo diz o que a
    #: biblioteca tem, ou o que fazer para ela existir.
    #:
    #: **A leitura NÃO acontece aqui**: quem lê é :func:`medir_no_disco`, na vigia; o que chega é a
    #: :class:`DoDisco`, já respondida (chamar `_censo.biblioteca_do_cartao` e `resposta_do_flatpak`
    #: na PINTURA, dez vezes por segundo, foi o defeito medido nela).
    resumo = do_disco.resumo(item.chave)
    #: **O «Consertar» saiu daqui — LANCADOR-LOCALIZAR-01, 10/09/2026.** Pendurado no estado
    #: POSITIVO (selo `LOCALIZADO`, moldura `chega`, a MESMA do `ok`/CHEGAM da Steam), nada no
    #: cartão declarava defeito e o produto oferecia *consertar*. O contraste é a Steam: lá o verbo
    #: tem antecedente (selo `NÃO CHEGAM`, moldura `impede`, a frase acima do botão nomeando o
    #: jogo).
    #:
    #: **O «Localizar» entra no lugar** (:func:`acao_de_localizar`, que o `off` já usava): até então
    #: só o NÃO LOCALIZADO o tinha, e os seis cartões do usuário estão localizados. Vem DEPOIS do
    #: «Abrir» (localizar de novo é o ato corretivo, não disputa a primeira posição), na leitura de
    #: cima para baixo que fez selo e botão falarem a mesma palavra em :data:`ADICIONAR_ROTULO`.
    #: Fecha um beco: a recusa do botão global (`a07_lancadores._recusa_de_quem_ja_tem_cartao`)
    #: dizia «hoje o cartão não tem por onde trocar», dívida nossa que a decisão de 07/09 proíbe.
    #:
    #: **O resumo vai para a linha `jogos`, não para o corpo** (§5.2): «37 jogos na biblioteca · 0
    #: instalados», o lugar em que a Steam imprime «23 jogos instalados». Medido na tela viva em
    #: 09/09/2026: o resumo colado na frente do `diz` estourava a caixa nas colunas da direita (o
    #: caminho do `.desktop` é longo e não quebra).
    #:
    #: A fileira comum (21/09/2026, desenho aprovado): os oito localizados têm os mesmos quatro
    #: botões (:func:`fileira_comum`), e o «Apontar outro caminho» é o terceiro. O ambiente que
    #: falta (AS-SOLUCOES-NOS-LANCADORES-01, 01/10/2026) tem a forma da Steam quando o atalho falta:
    #: contador abre o corpo, a linha vem embaixo e o selo diz `COM IMPEDIMENTO`.
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
    #: **A pintura não abre arquivo — 09/09/2026.** Aqui morava a varredura das caixas do Flatpak e,
    #: em `cartao_sem_censo`, a biblioteca de cada lançador e a pergunta da estrada: 6,4 ms de
    #: mediana por tique, dez vezes por segundo, num orçamento de 100 ms. A resposta chega pronta
    #: pela `Leitura`, medida na vigia (:class:`DoDisco`).
    do_disco = lida.do_disco if lida is not None else SEM_DISCO
    fora = [cartao_da_steam(lida)]
    for item in procurados(lida.declarados if lida is not None else ()):
        # A Steam já saiu acima, com o censo dela. Está em `procurados` porque a PRESENÇA se mede
        # como a dos outros, mas o cartão é outro; desenhá-la duas vezes daria dois
        # `data-lancador="steam"`.
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
    "DIZ_NAO_ACHEI",
    "DIZ_NAO_LI",
    "DIZ_SEM_FONTE",
    "EMBUTIDOS",
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
    "Acao",  # (noqa-acento) nome de CLASSE — identificador Python não leva acento
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
