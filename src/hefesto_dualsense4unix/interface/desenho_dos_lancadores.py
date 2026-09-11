#!/usr/bin/env python3
"""O DESENHO dos cartões da aba Lançadores — um só, para o gerador e o pacote.

POR QUE ELE EXISTE, e a razão é a cicatriz mais cara desta casa: o gerador
`aba07.py` escrevia os seis cartões com os números DIGITADOS (`412 jogos`,
`28 jogos`, `3 jogos já sabem por onde entrar`) e o produto não tinha por onde
contradizê-los. Medido em 02/09/2026 na máquina dela, com o `censo_do_wrapper`:

    o HTML afirmava   Steam · 412 jogos · 3 já sabem por onde entrar
    o produto responde  63 appids com o wrapper no vdf, 23 jogos instalados,
                        0 faltantes, 0 com ponte confirmada

Quatro números, quatro contradições. É a forma exata do defeito que ela mediu
ao abrir o produto: *"basicamente todas as telas são mockups e estão com
informações incorretas ou desatualizadas ou não integradas de fato."*
<!-- noqa-acento: citação literal dela -->

A CURA NÃO É APAGAR O DESENHO — é dar-lhe UMA fonte. Este módulo é o desenho;
quem passa o dado é que muda:

    aba07.py (gerador)  →  a lista de REFERÊNCIA, que ela aprovou  →  mockup/
    a07_lancadores.py   →  o que o produto MEDE, a cada tique      →  a tela

É o mesmo arranjo que a aba Conexões já provou (`gui/aba_conexoes.html_do_mapa`
serve o gerador e o pacote, e a página regerada saiu byte a byte igual à que ela
aprovou). Sem ele, o desenho e o produto seriam dois donos do mesmo cartão — e o
segundo dono envelhece calado.

**Este módulo não importa MOTOR nenhum.** Ele é importado pelo gerador (que
roda como script solto, `python3 aba07.py`) e pelo pacote (que roda dentro da
janela), e uma dependência pesada aqui atravessaria para os dois.

**A LINHA MUDOU EM 09/09/2026, e o fato antigo dizia MAIS do que era verdade.**
Ela dizia *"não importa NADA do produto"*, e desde o censo (`7dc8af8f`) isso
deixou de ser exato: ele importa DOIS módulos de `integrations/` — o censo e a
leitura das caixas do Flatpak. Os dois são `pathlib`, `json` e `configparser`, e
os dois respondem o que o CARTÃO mostra; nenhum puxa daemon, GTK ou IPC.

**ERAM TRÊS ATÉ 10/09/2026**: a `cura_por_estrada` saiu com o botão «Consertar»
do cartão LOCALIZADO (LANCADOR-LOCALIZAR-01, palavra dela). O número está
corrigido aqui e não guardado ao lado do certo — é fato, não decisão medida.

**A regra que fica é a que importa:** o gerador tem de continuar rodando SOLTO.
Se um import novo aqui quebrar `python3 aba07.py`, ele não pertence a este
arquivo.

**E O DISCO NÃO SE ABRE NA PINTURA — 09/09/2026.** Os três de `integrations/`
são chamados por :func:`medir_no_disco`, que BLOQUEIA e é da vigia do pacote;
:func:`cartoes` recebe a resposta fria (:class:`DoDisco`) e não abre arquivo
nenhum. O `pathlib` do topo é ANOTAÇÃO — o `lar` de mentira que a régua passa é
um `Path`, e nada neste módulo o usa para ler.
"""
from __future__ import annotations

import dataclasses
import html
from dataclasses import dataclass, field
from pathlib import Path

#: O selo é o resumo de UMA palavra do corpo do cartão.
#:
#: `nao_sei` NASCEU DA MEDIÇÃO, e não do desenho: o produto tem `zero` função
#: que examine Heroic, Lutris, RetroArch, Dolphin ou mGBA — as cinco só aparecem
#: em COMENTÁRIO (`daemon/subsystems/hotkey.py:56`, `daemon/lifecycle.py:2271`,
#: `profiles/schema.py:1509`). Sem este selo, o cartão do Heroic teria de
#: escolher entre `CHEGAM` e `NÃO CHEGAM`, e as duas seriam afirmação sobre um
#: lançador que o produto nunca olhou. **"Não sei" é resposta; palpite não é.**
#: O `off` DIZ «NÃO LOCALIZADO» DESDE 08/09/2026 — palavra dela, olhando a aba
#: com os quatro DualSense na mesa: *"ao invés de não achei. Deveria ter Não
#: Localizado"*.
#:
#: **O VALOR MUDOU; A HISTÓRIA FICOU.** A grafia antiga aparece dezenas de vezes
#: neste arquivo e nos vizinhos, em comentário e docstring que NARRAM o que
#: aconteceu num dia — o selo que nasceu morto, os cinco cartões que o diziam ao
#: lado de uma Steam verde. Trocar aquilo reescreveria o registro do passado, e
#: o passado não se edita para combinar com a tela de hoje.
#:
#: **E QUEM MEDE PASSOU A LER.** As réguas que digitavam a palavra agora leem
#: `SELOS["off"]` — é a regra que as onze réguas de 26/08/2026 deixaram: *régua
#: que digita o que devia LER reprova a melhora em vez do defeito*.
#: O LEITOR DE BIBLIOTECA dos cinco que não são a Steam — o dono do censo.
#: Import no topo e não tardio: ele não puxa motor nenhum (só `json`,
#: `configparser` e `pathlib`), e um import dentro da função seria pago em
#: todo cartão, a cada tique.
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as _censo

#: A LEITURA DAS CAIXAS DO FLATPAK — LANCADORES-ZERO-01 §5.4. Entra aqui pela
#: mesma razão do censo acima: é `pathlib`, `json` e `configparser`, e o desenho
#: já o chama para responder o que o cartão mostra.
#:
#: **A `cura_por_estrada` SAIU DAQUI — LANCADOR-LOCALIZAR-01, 10/09/2026.** Ela
#: era importada para uma pergunta só: *quem tem por onde receber o ambiente?*,
#: que decidia o botão «Consertar» do cartão LOCALIZADO. O botão saiu por
#: palavra dela — *"se tenho tudo instalado e tá pra ser identificado não tem
#: pq ter o botão de consertar"* — e com ele a pergunta.  # noqa-acento: citação literal dela
#: O módulo FICA, com a dívida declarada em
#: `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: a lacuna que ele
#: curava continua aberta, e quem a fecha é a LANCADOR-CARONA-01.
from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa

SELOS = {
    "ok": "CHEGAM",
    "warn": "NÃO CHEGAM",
    "off": "NÃO LOCALIZADO",
    "nao_sei": "NÃO SEI",
    #: **O POSITIVO DO PAR — 09/09/2026, LANCADORES-ZERO-01 §5.2**, e a palavra
    #: é dela (`D-0809-O-SELO-DOS-LANCADORES-DIZ-LOCALIZADO`): *"Deveria ter
    #: Não Localizado"*.  # noqa-acento: citação literal dela
    #:
    #: O DEFEITO QUE ELE MATA: cinco lançadores INSTALADOS recebiam `NÃO SEI`,
    #: porque o selo respondia *"sei ler a biblioteca dele?"*. Ela leu isso
    #: como *"a aba lançadores tá identificando nada"* — e estava  # noqa-acento: citação dela
    #: certa: um selo grande e negativo sobre um programa instalado não diz
    #: outra coisa.
    #:
    #: **AGORA O SELO RESPONDE UMA PERGUNTA SÓ — "está aqui?"** — e o
    #: veredito (`ok`/`warn`) só aparece onde há censo, como na Steam. O que a
    #: biblioteca diz vai para a linha de baixo, que é onde cabe um número.
    "localizado": "LOCALIZADO",
}

#: A classe da MOLDURA do cartão, por selo. `nao_sei` divide a moldura apagada
#: com `off` de propósito: as duas dizem "não há o que agir aqui", e um terceiro
#: tom só acrescentaria uma cor para ela decodificar.
#: `localizado` divide a moldura de `ok`: as duas dizem "este está aqui e não
#: há impedimento a agir". Um quarto tom só acrescentaria cor para decodificar.
MOLDURA = {"ok": "chega", "warn": "impede", "off": "ausente",
           "nao_sei": "ausente", "localizado": "chega"}

#: A GRADE QUE SEGURA OS SEIS CARTÕES — e ela é constante porque o PACOTE
#: precisa dela, não só o gerador.
#:
#: MEDIDO EM 02/09/2026, e fotografado: a `MOLDURA` só aparecia em
#: :func:`um_cartao`, que é o GERADOR. O pacote emitia cinco endereços por
#: cartão (`-selo`, `-jogos`, `-diz`, `-acoes`, `-fora`) e **nenhum deles é a
#: classe do contêiner** — a página publicada nasceu com os seis cartões em
#: `class="lanc ausente"` (o estado `cartoes(None)`) e a classe ficava lá para
#: sempre. O cartão da Steam mostrava o selo verde `CHEGAM` dentro de uma
#: moldura cinza de *ausente*: **a mesma tela dizendo duas coisas opostas.**
#:
#: A pintura do piloto escreve texto, `innerHTML`, largura, fundo e `value` —
#: não escreve CLASSE. O que ela sabe trocar inteiro é um BLOCO endereçado por
#: seletor CSS (`p.blocos`), e é por isso que o pacote repinta a grade: a classe
#: do contêiner só volta a ser dado junto com o contêiner.
#:
#: O DIA EM QUE O PILOTO GANHAR UM ALVO `classe`, isto vira uma linha por
#: cartão e a grade para de se trocar inteira — está declarado no relato desta
#: frente, em `espera_o_pintor`.
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
    #: O destino do `href`, e um `href` troca a TAG: com ele o botão nasce
    #: `<a class="btn">`, sem ele `<button>`. Ele existe para UM caso e ele é
    #: mecânico: a pop-up desta casa abre por `:target` (`monta.CSS_POPUP`,
    #: `.tela-nova:target{display:flex}`), e **só uma âncora muda o fragmento**.
    #:
    #: O GESTO CONTINUA SAINDO NO MESMO CLIQUE: o ouvinte do piloto não chama
    #: `preventDefault` (`hefesto_vivo.py`, o `addEventListener('click', …)`),
    #: então o mesmo toque abre a tela E manda o gesto — que é como o registro
    #: sabe para QUAL cartão a tela abriu. É a forma que o `aba06.py` já usa nos
    #: "Guardar" das telas de teclas.
    href: str = ""


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
    #: confunde duas perguntas diferentes — *"o lançador está aqui?"* e *"os
    #: controles chegam nele?"*. Um lançador achado cujo interior o produto não
    #: sabe ler é `presente=True` com selo `nao_sei`, e as duas coisas são
    #: verdade ao mesmo tempo.
    presente: bool = False


#: O ESPAÇO DURO É O QUARTO CARACTERE DA TABELA, e ninguém pensa nele. O DOM
#: devolve `&nbsp;` para um U+00A0 que entrou cru — logo emiti-lo cru é a mesma
#: reescrita eterna que o apóstrofo causa, num caractere que um `appmanifest`
#: bem pode trazer.
_DURO = "\u00a0"


def _e(txt: object) -> str:
    """Escapa para HTML **em posição de TEXTO**. O nome do jogo vem do DISCO dela.

    Um `appmanifest` com `&` ou `<` no nome quebraria a marcação do cartão, e um
    nome de jogo é conteúdo de terceiro — a mesma razão pela qual
    `gui/aba_conexoes` escapa o rótulo do aparelho antes de o pôr na tela.

    O `quote=False` NÃO É RELAXAMENTO — é o que impede um LAÇO INFINITO na
    máquina dela, e a razão é o piloto: ele só reescreve quando
    `innerHTML !== valor` (`hefesto_vivo.py:441` no campo, `:944` no bloco). As
    duas comparações são de TEXTO LITERAL, e o lado esquerdo é o que o DOM
    **devolve**, não o que se escreveu. Se a grafia emitida não for a que o DOM
    devolve, a comparação nunca casa e a reescrita não para nunca.

    MEDIDO NO WEBKIT DA JANELA DELA em 02/09/2026 (`<div>` solto, `innerHTML`
    de ida e de volta, os seis caracteres nas duas grafias — 28 casos):

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

    `html.escape(quote=True)` emite `&#x27;` para o apóstrofo e `&quot;` para a
    aspa — e o DOM devolve os dois CRUS no texto. Bastava **um** jogo com
    apóstrofo no nome (a biblioteca dela tem 63) para a lista do cartão e a
    grade inteira serem reescritas **duas vezes por segundo, para sempre**,
    matando o foco e o `:hover` de quem estivesse com o mouse num botão.

    A régua que segura isto é `test_a_marcacao_volta_igual_do_dom`, e ela não
    digita a tabela acima: reserializa a marcação emitida pelas regras medidas e
    exige que o texto volte idêntico.
    """
    return html.escape(str(txt if txt is not None else ""),
                       quote=False).replace(_DURO, "&nbsp;")


def _a(txt: object) -> str:
    """Escapa para HTML **em posição de ATRIBUTO** — o `_e` mais a aspa.

    A DIFERENÇA É UMA LINHA e ela é obrigatória nos dois sentidos: dentro de um
    atributo entre aspas duplas, uma aspa crua FECHA o atributo (foi medido:
    `data-v="a"b"` volta do DOM como dois atributos), e um `&#x27;` volta cru.
    Um único escape para os dois lugares erra sempre num dos dois.

    TODO ATRIBUTO DESTE MÓDULO USA ASPAS DUPLAS — é o que torna a tabela acima o
    contrato inteiro. O `<` e o `>` continuam escapados porque o WebKit os
    devolve escapados **também no atributo**, e não porque a marcação precise.
    """
    return _e(txt).replace('"', "&quot;")


def selo_html(selo: str) -> str:
    """O selo com a CLASSE certa — e é por isso que ele é pintado como `html`.

    A pintura do piloto escreve `textContent` por padrão, e o `textContent` não
    troca a cor: um cartão que passasse de `CHEGAM` (verde) para `NÃO SEI`
    ficaria com a palavra nova e o verde velho. O `data-hef-alvo="html"` do
    esqueleto existe para exatamente isto, e o alvo é o INVÓLUCRO — o `<span>`
    com a classe entra no innerHTML, e não ao redor dele.
    """
    if selo not in SELOS:
        raise KeyError(
            f"selo {selo!r} não existe. Os que existem estão em `SELOS`, e "
            f"inventar um aqui deixaria o cartão sem cor — a única coisa que "
            f"esta aba mostra sem ler.")
    return f'<span class="lanc-selo {selo}">{SELOS[selo]}</span>'


def carimbo_html(texto: str) -> str:
    """O carimbo verde, ou VAZIO. Vazio some do cartão, e é o certo.

    Um carimbo que dissesse "0 jogos já sabem por onde entrar" ocuparia a linha
    para não dizer nada — e o desenho o pôs na fileira dos botões justamente
    para não custar altura quando não há notícia.
    """
    return f'<span class="carimbo">◆ {_e(texto)}</span>' if texto else ""


def acao_html(a: Acao) -> str:
    """Um botão. Sem `gesto`, ele nasce SEM endereço — e é decisão, não esquecimento.

    A regra da casa: *"o que NÃO tem dono não vira botão que finge"*. Um
    `data-gesto` num botão que ninguém atende faz o piloto recusar dizendo o
    nome, o que é honesto; mas um `data-gesto` num botão que o produto não sabe
    fazer seria pior — a recusa aparece só no terminal, e na tela o clique some.
    """
    classe = f"btn {a.classe}".strip()
    endereco = f' data-gesto="{_a(a.gesto)}"' if a.gesto else ""
    valor = f' data-v="{_a(a.v)}"' if a.v else ""
    # A TAG SEGUE O `href`, e a razão está em :attr:`Acao.href`: só uma âncora
    # abre a pop-up por `:target`. Um `<button>` com `href` não navega, e um
    # `<a>` sem `href` não é clicável pelo teclado — por isso os dois casos são
    # tags diferentes, e não um atributo opcional numa tag só.
    if a.href:
        return (f'<a class="{classe}" href="{_a(a.href)}"'
                f'{endereco}{valor}>{_e(a.rotulo)}</a>')
    return f'<button class="{classe}"{endereco}{valor}>{_e(a.rotulo)}</button>'


#: O QUE VAI NO LUGAR DE UMA FILEIRA DE BOTÕES VAZIA — e ele não é enfeite.
#:
#: O `escrever()` do BOOTSTRAP troca o vazio pelo TRAVESSÃO, e para um campo de
#: VALOR isso é o certo: "não há valor" se lê `—`. Para um contêiner de HTML é
#: errado, e foi fotografado em 02/09/2026: os quatro cartões `NÃO ACHEI`
#: nasceram com um traço solto pendurado onde os botões tinham estado, dizendo
#: nada. O mesmo traço já estava, desde antes, no pé do cartão da Steam com a
#: lista vazia.
#:
#: **O conserto de raiz é no `escrever()`**, que precisa separar alvo `html`
#: (vazio = NADA) de alvo de texto (vazio = travessão) — está no relato desta
#: frente, e mora em `hefesto_vivo.py`, que não é território desta aba.
#:
#: Um COMENTÁRIO HTML é o que o desenho pode fazer sozinho: o valor não é
#: vazio (logo o travessão não entra), o navegador o renderiza como nada, e a
#: fileira fica com a altura do seu próprio `padding-top` — que é o que ela
#: teria se o produto pudesse escrever vazio de verdade.
FILEIRA_VAZIA = "<!-- nada a oferecer neste cartão -->"

#: O QUE VAI NUM CONTÊINER DE LISTA QUE AINDA NÃO TEM O QUE LISTAR — e ele NÃO
#: É UMA FRASE, de propósito.
#:
#: FOTOGRAFADO EM 02/09/2026, e a cura anterior alcançou só um dos três estados:
#: `lista_de_jogos` ganhou :data:`LISTA_VAZIA`, mas os DOIS ramos de saída
#: antecipada de :func:`cartao_da_steam` — a primeira meia volta (`lida is
#: None`) e a Steam ilegível (`lida.erros`) — devolviam o cartão com `fora` no
#: padrão `""`. Como `tem_lista=True`, `valores_do_cartao` emitia
#: `steam-fora=""`, e o `escrever()` do BOOTSTRAP troca vazio por travessão
#: ANTES de despachar o alvo (`hefesto_vivo.py:118`), inclusive para
#: `alvo === 'html'`. **O da Steam ilegível é permanente** — justo a tela em que
#: ela precisa ler uma mensagem, com um traço mudo pendurado embaixo.
#:
#: POR QUE UM COMENTÁRIO E NÃO UMA FRASE: nos dois estados o produto **não sabe**
#: o que há na lista. Escrever "nenhum jogo com pendência" ali seria afirmar o
#: resultado de uma leitura que não aconteceu — a forma exata do defeito que
#: esta aba nasceu para matar. O comentário não é vazio (logo o travessão não
#: entra), o navegador o renderiza como NADA, e a tela fica igual ao desenho que
#: ela aprovou, onde o contêiner nasce vazio.
SEM_LISTA = "<!-- ainda não há lista para este cartão -->"

#: A frase da lista de jogos VAZIA do cartão da Steam. Ela existe pela mesma
#: razão do de cima, e diz o que o travessão não dizia: a lista tem QUATRO
#: origens (falta o atalho · linha intocável · você tirou · você dispensou), e
#: vazia significa que nenhuma delas tem item — não que ninguém olhou.
LISTA_VAZIA = ("Nenhum jogo com pendência, e nenhum que você tenha tirado ou "
               "dispensado.")


def acoes_html(lanc: Lancador) -> str:
    """A fileira de botões DO CARTÃO, com o carimbo no fim dela.

    ELA É PINTADA INTEIRA, e a razão é medida: no cartão da Steam os botões
    MUDAM com o estado — `Consertar` só existe quando há o que consertar. Se a
    fileira fosse estática, ou o `Consertar` ficaria aceso sobre uma biblioteca
    inteira em ordem (um clique que não conserta nada), ou não existiria no dia
    em que a Steam comesse a linha — e o botão que a aba existe para oferecer
    nunca apareceria.

    O CARIMBO VAI AQUI DENTRO porque o desenho o pôs aqui: como linha própria
    ele custava 21px que SÓ o cartão da Steam pagava, e a fileira dele nascia
    21px abaixo da do cartão vizinho.

    A QUEBRA DE LINHA E O RECUO SÃO PARTE DO VALOR, e isso é cura — medida na
    tela em 02/09/2026, com o piloto rodando 40 segundos. O gerador escrevia
    ``<div class="acoes">\\n{acoes_html}\\n        </div>`` e o pacote pintava
    ``acoes_html`` **sem** a moldura de espaço; as duas grafias do MESMO valor
    ficavam eternamente diferentes, e com a grade sendo repintada como bloco
    isso virou um PING-PONG: o bloco reescrevia a fileira com o espaço, o campo
    a reescrevia sem, e o piloto contava pintura em **81 de 81 voltas** — 2 por
    segundo, para sempre, destruindo o foco e o `:hover` de quem estivesse com o
    mouse em cima de um botão.

    Com o espaço DENTRO do valor, a página sai byte a byte igual à de antes e as
    duas grafias passam a ser uma só. Quem segura isto é
    `test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa`.
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

    QUATRO ENDEREÇOS POR CARTÃO, e o quinto só onde há lista. Todos com o prefixo
    da `chave` porque a página tem seis cartões e um `data-campo="selo"` sozinho
    seria pintado nos seis com o mesmo valor — o defeito que a distribuição de
    lista do piloto faz de propósito, e que aqui seria acidente.
    """
    # A `chave` SÓ APARECE EM ATRIBUTO nesta função (`data-lancador`,
    # `data-campo`), então ela é escapada como atributo — ver :func:`_a`.
    k = _a(lanc.chave)
    # A FILEIRA SAI NUMA VARIÁVEL para a linha caber nos 100 caracteres do
    # `ruff` — o HTML emitido é o mesmo caractere por caractere, e a moldura de
    # espaço continua vindo de dentro de `acoes_html`, que é onde ela tem de
    # estar para o valor pintado e o da grade serem UM só.
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


#: O QUE A LINHA «PARA QUEM» DIZ QUANDO A TELA ABRIU PELO BOTÃO GLOBAL — o
#: estado em que ela nasce vazia. Ele mora aqui, e não no pacote, porque é o
#: DESENHO da tela estática: o gerador o escreve dentro do `data-campo`, e o
#: pacote o repinta com o mesmo texto enquanto não houver cartão apontado.
#: ELA DIZIA O QUE NÓS NÃO TEMOS, e foi apanhada pelo portão no mesmo dia em que
#: nasceu: *"Um lançador ou emulador que o Hefesto **ainda não** traz de
#: fábrica"* — o «ainda não» põe o sujeito em NÓS e transforma a linha numa
#: confissão de dívida. A ordem dela, 07/09/2026: *"O app tem que funcionar e não
#: mostrar na tela que o app não presta."*
#:
#: O SUJEITO CERTO É ELA, e a frase fica melhor: quem está para ser acrescentado
#: é um lançador que ELA usa. O fato não se perdeu — quem chega a esta tela já
#: sabe que o lançador não tem cartão, porque foi por isso que ela a abriu.
NOVO_SEM_ALVO = "Um lançador ou emulador que você usa"

#: O que a linha diz quando a tela abriu pelo botão de um CARTÃO
#: (:data:`ADICIONAR_ROTULO`). O `{nome}` é o nome daquele cartão, e é o que
#: responde à única pergunta que ela faria olhando dois campos vazios: *para
#: qual?*
#:
#: **A FRASE PERDEU O ARTIGO EM 08/09/2026, e foi a FOTO que mostrou.** Ela
#: dizia *"Onde está **o** {nome} nesta máquina"*, e o artigo masculino estava
#: certo nos cinco cartões que chegavam aqui — o Heroic, o Lutris, o Flatpak, o
#: RetroArch, o Dolphin. No dia em que o cartão da STEAM ganhou o botão
#: (:func:`acao_de_localizar`), a tela passou a dizer *"o Steam"* — e esta casa
#: escreve **a** Steam em toda a aba, do corpo do cartão à frase da sentinela.
#:
#: NÃO SE CONSERTA COM UMA TABELA DE GÊNERO: o `{nome}` também vem do que ELA
#: digitou ao acrescentar um cartão novo, e adivinhar o artigo de um nome que
#: ainda não existe é palpite na tela dela. A frase sem artigo é verdadeira para
#: todo nome — inclusive os que ainda não foram inventados.
#:
#: O «ele» FICA, e ele não é descuido: é a MESMA palavra do rótulo do campo logo
#: abaixo (*"Onde ele está"*), que já vale para os seis cartões. O sujeito ali é
#: *o lançador*, e não o nome próprio — trocar o pronome aqui deixaria a linha e
#: o campo que ela responde falando de coisas diferentes.
NOVO_PARA_O_CARTAO = "{nome} — onde ele está nesta máquina"


def tela_do_registro_html(para_quem: str = NOVO_SEM_ALVO) -> str:
    """A pop-up em que ela diz onde o lançador está. Sem uma linha de script.

    ELA ABRE POR `:target` (`monta.CSS_POPUP`), que é o mecanismo que esta casa
    já usa nas cinco pop-ups das abas 06 e 08 — o botão é uma âncora para o
    `id` daqui, e o fechar e o `Cancelar` são âncoras para `#`. Um segundo
    mecanismo de abrir tela seria o segundo vocabulário que o `CSS_POPUP` subiu
    para o `monta.py` justamente para não existir.

    **DOIS CAMPOS, E O SEGUNDO É O MÍNIMO.** O nome é o rótulo do cartão; o que
    o produto precisa é do outro — o comando ou o caminho. Quem chega pelo botão
    de um cartão não precisa nem do primeiro: o cartão já tem nome.

    **E O SEGUNDO TEM DUAS PORTAS — 10/09/2026, decisão dela (a opção C).** Ao
    lado do campo há o :data:`PROCURAR_O_ARQUIVO_ROTULO`, que abre o seletor do
    sistema e ela aponta o `.desktop` com o mouse. **O campo FICA**, e é ela
    quem diz por quê: um AppImage solto não tem `.desktop` para apontar, e é
    justamente o caso que a frase do cartão promete cobrir.

    O `href` DO BOTÃO É O `id` DESTA CAIXA, e não `#`: um `#` mudaria o
    `:target` e FECHARIA a pop-up no mesmo clique que abre o seletor — a tela
    sumindo debaixo do diálogo que ela pediu. Apontar para si mesma deixa o
    `:target` onde está.

    O GLIFO DE FECHAR VAI COMO ENTIDADE (`&times;`) e não como caractere, e a
    razão é de LINT, não de gosto: os `aba*.py` têm isenção de `RUF001`/`RUF002`
    no `pyproject.toml` (eles são HTML dentro de Python por natureza) e **este
    módulo não tem** — ele é o desenho compartilhado, e a régua estrita nele é o
    que impede um caractere ambíguo de entrar num valor que o produto compara.
    A entidade renderiza igual e não pede exceção nenhuma.

    A CAIXA DE TEXTO NÃO TEM `data-campo`, e isso é cura de defeito conhecido —
    ver :data:`NOVO_ALVO`. O que o piloto recolhe é `data-linha`, e o que ele
    pinta é só a linha de cima, que é texto do produto.

    O TÍTULO NÃO É O RÓTULO DE NENHUM DOS DOIS BOTÕES, e isso é cura — ver
    :data:`TELA_DO_NOVO_TITULO`. Esta caixa é UMA, e chega-se a ela por dois
    caminhos; titulá-la com a palavra de um deles faria a metade das aberturas
    mostrar um título que contradiz a linha logo abaixo.
    """
    return f'''<div class="tela-nova" id="{TELA_DO_NOVO}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{_e(TELA_DO_NOVO_TITULO)}</span>
      <span class="ajuda">?<span class="dica">
        O Hefesto procura cada lançador de dois jeitos: o atalho
        <code>.desktop</code> nas pastas de aplicativos e o comando no
        <code>PATH</code>. Diga qualquer um dos dois e ele passa a procurar
        também o seu.<br><br>
        Vale o <b>comando</b> (<code>ryujinx</code>), o <b>caminho inteiro</b> de
        um programa (<code>/opt/Ryujinx/Ryujinx</code>, e é assim que entra um
        AppImage solto) ou o <b>nome do atalho</b>
        (<code>org.ryujinx.Ryujinx</code>).<br><br>
        O que você escrever é conferido no disco antes de ser guardado.
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
                 placeholder="ryujinx  ·  /opt/Ryujinx/Ryujinx  ·  org.ryujinx.Ryujinx">
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

    ESCRITO AQUI, e não no pacote, para que os dois lados não possam divergir:
    quem acrescentar um endereço em `um_cartao` e esquecer daqui deixa um campo
    com o valor do desenho para sempre, e é isso que a régua da aba cobra.
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


def linhas_de_jogos(itens: list[JogoNaLista], vazio: str = "") -> str:
    """A lista de jogos do cartão, ou a frase de lista vazia.

    O `data-v` DE CADA LINHA É O APPID, e não o rótulo: dois jogos podem ter o
    mesmo nome na biblioteca (uma demo e o jogo), e `rotulo_do_jogo` cai para
    `appid NNNN` quando o manifesto sumiu. Clicar por nome tiraria o wrapper do
    jogo errado — é a mesma razão pela qual a aba Conexões endereça o aparelho
    pelo `nome_do_kernel` e não pelo rótulo.
    """
    if not itens:
        return f'<div class="lanc-vazio">{_e(vazio)}</div>' if vazio else ""
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


#: O ENDEREÇO DA FRASE DO "?" QUE CONTA CONTROLE. Ele mora aqui pela mesma
#: razão de :data:`ABRIR`: o gerador o escreve no `data-campo` e o pacote o
#: emite na carga — digitá-lo duas vezes é como um endereço fica órfão.
QUANTOS = "lanc-quantos"


def quantos_html(n_ctrl: int, n_usb: int, n_bt: int) -> str:
    """*"os **2** (1 no cabo, 1 no rádio)"* — o trecho do "?" que conta controle.

    POR QUE ELE EXISTE, e é a última bolsa de mockup desta aba. Os CARTÕES
    pararam de contar controle em 02/09/2026 (*"Contar controle aqui era
    responder com um número que a pergunta não tem"*), e a régua do gerador
    passou a reprovar um cartão que prometesse para um número. **O texto do
    `?` ficou de fora da cura** — e o próprio `aba07.py` deixou dito, no
    import: *"`CONECTADOS` fica — ele ainda responde pelo texto do '?'"*.

    O QUE ISSO PÔS NA TELA DELA, medido em 03/09/2026 no WebKit da janela, com
    UM DualSense no cabo:

        cabeçalho (lido do aparelho)   ``● 1 controle: 1 USB · 0 BT``
        o "?" logo abaixo, no mesmo quadro
                                       ``…vale igual para os 2 (1 no cabo,
                                         1 no rádio)…``

    O `2` não vinha do aparelho: vinha de `monta.CONECTADOS`, a mesa do
    DESENHO, derivada no import do gerador e congelada no HTML. É a mesma forma
    da fita que dizia `P1 · Cosmic Red · USB` sobre um White — e a lei dela é a
    mesma: *"se no topo tá mostrando controle white player 1, então cada aba
    vai usar os controles lá de cima. Não mistura com a info dos mockups."*

    AS PALAVRAS SÃO AS DELA, e só o ARTIGO se dobra ao número: com um controle
    na mesa, *"para os 1"* seria trocar uma mentira por um erro de português.
    Nada mais mudou de redação — o que mudou é de onde saem os três números.
    """
    artigo = "o" if n_ctrl == 1 else "os"
    return (f"{artigo} <b>{n_ctrl}</b> ({n_usb} no cabo, "
            f"{n_bt} no rádio)")


def conta_html(achados: int, impedidos: int) -> str:
    """A contagem do quadro: `N encontrados · M com impedimento`.

    ELA JÁ ERA DERIVADA no gerador (a aba dizia "6 encontrados" contando o
    cartão que ela mesma carimba `NÃO ACHEI`), e continua sendo — o que muda é
    de ONDE: da lista de cartões que o produto montou, e não da que ele digitou.
    """
    #: **"localizados", E NÃO "encontrados" — 09/09/2026, §5.2.** A palavra do
    #: cabeçalho passa a ser a MESMA do selo: com `LOCALIZADO` no cartão e
    #: "encontrados" no topo, a tela diria duas palavras para o mesmo fato, e
    #: ela teria de traduzir uma na outra ao ler.
    return (f'{_plural(achados, "localizado", "localizados")} '
            f'<span class="sep">·</span> '
            f'{_plural(impedidos, "com impedimento", "com impedimentos")}')


#: OS ENDEREÇOS QUE UM CARTÃO PRODUZ, para a régua da aba os cobrar sem
#: reescrever a lista. Régua que digita o que devia LER é o defeito que esta
#: casa nomeou onze vezes em 26/08.
SUFIXOS = ("-selo", "-jogos", "-diz", "-acoes")
SUFIXO_DA_LISTA = "-fora"


# ---------------------------------------------------------------------------
# O QUE O DISCO RESPONDE, e os seis cartões que saem dele
#
# ISTO MORA NO DESENHO, e não no pacote, por uma razão de ferramenta: o gerador
# `aba07.py` roda como SCRIPT SOLTO (`python3 aba07.py`) e não pode importar
# `pacotes/`, que puxa os dez pacotes e o produto inteiro. Com os cartões aqui,
# o gerador emite a página de REFERÊNCIA chamando `cartoes(None)` — o mesmo
# estado que a tela mostra na primeira meia volta, antes de a leitura voltar —
# e o pacote emite os mesmos cartões com o dado real. **Um dono, dois dados.**
#
# É o que impede o número digitado de voltar: não há onde digitá-lo.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemCenso:
    """Um lançador cujo INTERIOR o produto não sabe ler — e onde procurá-lo.

    OS DOIS SABERES SÃO SEPARADOS, e confundi-los foi o defeito que este
    arquivo nasceu para curar. *"Sei ler a biblioteca dele"* e *"ele está
    instalado aqui"* são perguntas diferentes, e o produto responde a SEGUNDA
    hoje, de graça: um lançador instalado publica um `.desktop` nas pastas que
    a spec XDG declara, ou põe o executável no `PATH`.

    Enquanto só a primeira existia, os cinco cartões diziam `NÃO SEI` por
    CONSTANTE — o pacote escrevia sempre a mesma palavra, e a tela não tinha
    como diferir *"o produto mediu e não sabe"* de *"ninguém pintou"*. É a
    forma exata do defeito desta casa: **o desenho fingindo ser produto.**

    :param atalhos: os `stem` de `.desktop` que denunciam o lançador. Sem
        glob e sem casamento por prefixo: `dolphin-emu` é o emulador e
        `dolphin` é o gerenciador de arquivos do KDE — casar por prefixo
        acusaria o Dolphin em toda máquina com KDE instalado.
    :param comandos: o que procurar no `PATH` quando não há `.desktop`. É o
        caso do Flatpak, que é PACOTE e não aplicativo: ele não publica
        atalho próprio, só o comando.
    """

    chave: str
    nome: str
    atalhos: tuple[str, ...] = ()
    comandos: tuple[str, ...] = ()
    #: ELA declarou este lançador (ou ensinou onde este embutido está)?
    #:
    #: É O QUE DECIDE O BOTÃO DE TIRAR, e nada mais: um cartão declarado tem de
    #: poder sair, senão a lista dela vira lixo permanente. Num embutido que ela
    #: ensinou, tirar desfaz o ensino e devolve a busca de fábrica — as duas
    #: coisas são o mesmo ato, e por isso é o mesmo botão.
    declarado: bool = False


#: OS LANÇADORES CUJO INTERIOR O PRODUTO NÃO LÊ. A lista é dado, e não `if`: no
#: dia em que alguém escrever o censo do Heroic, ele SAI daqui e ganha cartão
#: próprio.
#:
#: A PROVA DE 02/09/2026 CADUCOU, e o número que ela citava era este:
#: *"o `grep -rniE "heroic|lutris|…" src` devolve CINCO linhas fora desta aba,
#: e as cinco são COMENTÁRIO"*. **Remedido em 10/09/2026: são 58 linhas**, e
#: `integrations/cura_por_estrada.py` LÊ e ESCREVE o `config.json` do Heroic
#: (`_ler_heroic`, `_escrever_no_heroic`, `CHAVE_DO_HEROIC`).
#:
#: **A LISTA CONTINUA CERTA, e a distinção é a razão:** o que ela nomeia é o
#: lançador cuja BIBLIOTECA o produto não lê — quais jogos existem lá dentro.
#: `cura_por_estrada` não lê biblioteca nenhuma: ela escreve VARIÁVEIS DE
#: AMBIENTE na estrada daquele lançador, o que é o outro lado do trabalho.
#: Quem segura o contrato desta lista continua sendo o
#: `test_os_cinco_lancadores_sem_fonte_continuam_sem_fonte`, e um `grep` de
#: nome próprio nunca foi régua boa: ele conta MENÇÕES, não leituras.
#:
#: OS IDENTIFICADORES SÃO OS DE VERDADE, e as duas formas de cada um entram: o
#: `app-id` do Flatpak (que é como a máquina dela os teria, pelos 54 atalhos em
#: `~/.local/share/flatpak/exports/share/applications`) e o nome nativo do
#: pacote da distribuição.
#:
#: **NÃO HÁ CARTÃO DA EPIC, E A DECISÃO É DELA — 08/09/2026.** Ela pediu um
#: (*"Seria interessante termos o da Epic Games Aqui também não?"*), ele foi
#: feito, ela viu e desfez — a grafia é a dela, e fica:
#: *"melhor deixar só heróic e tirar epic games não?"*  # noqa-acento: dela
#:
#: A SEGUNDA PALAVRA É A QUE VALE, e o argumento dela fecha o caso melhor que o
#: cartão fechava: **quem entrega o jogo da Epic nesta máquina é o Heroic**, e o
#: rótulo do cartão dele já diz «Epic · GOG» desde que ele nasceu. Um cartão da
#: Epic ao lado teria de procurar o Heroic para não dizer NÃO LOCALIZADO numa
#: máquina onde os jogos da Epic abrem — ou seja, **dois cartões da mesma tela
#: procurando o mesmo programa em disco**, e o segundo existindo só para repetir
#: a resposta do primeiro.
#: Ela: *"Epic e gog ficam dentro do heróic. Melhor mesmo seu ponto"*.  # noqa-acento: dela
#:
#: **O RÓTULO DO HEROIC NÃO MUDA**, e agora ele carrega mais do que carregava:
#: com o cartão fora, o «(Epic · GOG)» é o ÚNICO lugar da tela onde a Epic
#: aparece. Tirar as duas lojas dali deixaria quem procura a Epic sem nada.
SEM_FONTE: tuple[SemCenso, ...] = (
    SemCenso("heroic", "Heroic (Epic · GOG)",
             ("com.heroicgameslauncher.hgl", "heroic"), ("heroic",)),
    SemCenso("lutris", "Lutris", ("net.lutris.Lutris", "lutris"), ("lutris",)),
    SemCenso("flatpak", "Flatpak", (), ("flatpak",)),
    SemCenso("retroarch", "RetroArch",
             ("org.libretro.RetroArch", "retroarch"), ("retroarch",)),
    SemCenso("emuladores", "Dolphin · mGBA",
             ("org.DolphinEmu.dolphin-emu", "dolphin-emu", "io.mgba.mGBA",
              "mgba-qt", "mgba"),
             ("dolphin-emu", "mgba-qt", "mgba")),
)

#: A STEAM TAMBÉM SE PROCURA — 02/09/2026, e ela nasceu de uma acusação provada.
#:
#: O cartão da Steam era o único com CENSO, e por isso o único cuja PRESENÇA
#: ninguém mediu: `presente=True` era constante. Medido com o `HOME` desviado
#: para uma casa de mentira, sem Steam nenhuma e com o `PATH` vazio:
#:
#:     conta_do_topo = '1 encontrado · 0 com impedimentos'
#:     steam: selo 'ok' (CHEGAM), presente True,
#:            'Os controles chegam. O atalho de inicialização está no lugar em
#:             0 jogos da sua biblioteca.'
#:
#: Uma máquina SEM Steam recebia o selo VERDE e a promessa de que os controles
#: chegam — a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor verde, que é a frase com
#: que esta aba nasceu. Os outros cinco cartões diziam `NÃO ACHEI` na mesma tela.
#:
#: A CURA É A MEDIÇÃO QUE JÁ EXISTIA, aplicada ao sexto: as mesmas pastas de
#: `.desktop` e o mesmo `PATH` que respondem pelos cinco respondem por esta.
#: Ela NÃO entra em :data:`SEM_FONTE` — o interior da Steam o produto LÊ, e é
#: essa a pergunta daquela lista. São duas perguntas, e continuam separadas.
#:
#: OS IDENTIFICADORES: `steam.desktop` é o do pacote da distribuição (medido
#: nesta bancada, em `/usr/share/applications`), `com.valvesoftware.Steam` é o
#: da Flathub e `steam-native` é o da instalação sem o runtime. O comando entra
#: pelo mesmo motivo dos outros — nesta bancada ele é `/usr/games/steam`, que
#: nem sequer está no `/usr/bin`.
A_STEAM = SemCenso("steam", "Steam",
                   ("steam", "com.valvesoftware.Steam", "steam-native"),
                   ("steam", "steam-native"))

#: OS SEIS QUE VÊM DE FÁBRICA. :data:`SEM_FONTE` responde outra coisa (*"sei ler
#: a biblioteca dele?"*) e percorrê-la para procurar deixava a Steam de fora da
#: única pergunta que o produto sabe responder sobre todos sem inventar.
#:
#: **ELE NÃO É A LISTA QUE SE PROCURA — quem responde isso é :func:`procurados`,
#: e a diferença nasceu em 08/09/2026 com o lançador declarado por ELA.** O
#: nome antigo (`PROCURADOS`) morreu de propósito: enquanto uma constante
#: respondesse "o que se procura", quem a lesse por hábito procuraria só os de
#: fábrica e o lançador que ela acrescentou seria invisível — calado, e só na
#: máquina dela. Um nome que mente é pior que um nome comprido.
EMBUTIDOS: tuple[SemCenso, ...] = (A_STEAM, *SEM_FONTE)


def procurados(declarados: tuple[SemCenso, ...] = ()) -> tuple[SemCenso, ...]:
    """Os :data:`EMBUTIDOS` **mais** o que ELA declarou — a lista única.

    É esta que se procura em disco, esta que se ordena e esta que vira cartão.
    Um segundo caminho de busca para o declarado seria a assimetria que esta
    casa passou o dia arrancando: o embutido e o declarado passam pelo MESMO
    procurador, com os mesmos três campos (`atalhos`, `comandos`, `nome`).

    **CHAVE REPETIDA NÃO VIRA SEGUNDO CARTÃO — ela ENSINA o primeiro.** Se ela
    declarar `retroarch` (o botão de localizar do cartão que não achou
    manda a chave do cartão), o que entra são os `atalhos` e `comandos` dela
    SOMADOS aos de fábrica, no mesmo cartão. É o sentido literal do botão: *"ele
    está aqui, eu te mostro onde"* — não *"faça um cartão novo com o mesmo
    nome"*. Dois cartões com a mesma `chave` seriam pior que inútil: os
    endereços do desenho levam a chave como prefixo (`data-campo="retroarch-selo"`),
    e o piloto pintaria o valor de um nos DOIS.

    O NOME DE FÁBRICA VENCE no cartão ensinado, e é o mesmo raciocínio: o rótulo
    daquele cartão é desenho que ela aprovou. O que ela acrescentou foi ONDE
    procurar, não como se chama.

    A ORDEM É ESTÁVEL: os de fábrica na ordem do desenho, os novos no fim, na
    ordem em que o disco os devolveu. Um cartão que troca de lugar entre dois
    tiques é a grade inteira piscando.
    """
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
    return tuple(fora)

#: A frase de quem AINDA NÃO PROCUROU — a primeira meia volta, antes de a
#: leitura de disco voltar.
#:
#: ELA DIZIA O QUE FALTA, e agora diz o que FUNCIONA. Ordem dela, 07/09/2026:
#: *"O app tem que funcionar e não mostrar na tela que o app não presta. (…) o
#: layout não informa os nossos defeitos."* A frase antiga abria com *"Ainda
#: não sei olhar este lançador"* e fechava com *"nenhuma linha dele olha para
#: cá hoje"* — duas confissões em volta do único fato que serve a quem lê.
#:
#: O FATO SOBREVIVEU INTEIRO, e é o do meio: o perfil casa por processo e por
#: janela, então um jogo aberto de lá entra pelo mesmo caminho de qualquer
#: outro. Quem precisa da dívida a encontra no mapa de canais, que é onde ela
#: mora.
DIZ_SEM_FONTE = (
    "<b>O perfil casa pelo nome do processo e pela janela.</b> Um jogo aberto "
    "por aqui entra pelo mesmo caminho de qualquer outro."
)

#: A frase de quem PROCUROU E ACHOU — **VAZIA DESDE 11/09/2026, ordem dela**:
#: *"remove as frases do achei esse lançador aqui"*.  <!-- noqa-acento: citação literal dela -->
#:
#: O CARTÃO JÁ DIZ AS DUAS COISAS SEM ELA. O selo `LOCALIZADO` responde *"o
#: produto achou este lançador"*, e a linha de cima responde quantos jogos ele
#: tem — a frase repetia o selo em prosa, no plural, em cinco cartões
#: empilhados. Ela viu os cinco de uma vez e recusou os cinco.
#:
#: **O CAMINHO NÃO SE PERDEU, mudou de lugar**: ele continua sendo lido e
#: continua sendo o que o `presente=True` afirma; o que saiu foi pintá-lo na
#: tela. Quem precisa conferir por onde o produto achou o lançador tem o
#: `doctor`, que imprime o atalho e o comando de cada um.
#:
#: A CONSTANTE FICA, e vazia de propósito — ela é o LUGAR da frase deste
#: estado, e apagá-la faria o cartão do achado e o do não-achado deixarem de
#: ser simétricos no código. As réguas que perguntam pelo estado continuam
#: tendo a quem perguntar.
DIZ_ACHEI = ""

#: A frase de quem PROCUROU E NÃO ACHOU.
#:
#: **ELA DIZ «NÃO LOCALIZEI» DESDE 08/09/2026**, e a razão é a mesma do selo: a
#: palavra dela foi *"ao invés de não achei"*, e a tela dizia a frase que ela
#: recusou em DOIS lugares — o selo, em maiúsculas, e a primeira oração daqui.
#: Trocar só o selo deixaria a mesma tela com as duas grafias, uma ao lado da
#: outra. **O NOME DA CONSTANTE FICA**: ele nomeia o ESTADO ("procurei e não
#: achei"), que não mudou, e é lido por réguas que perguntam pelo estado.
#:
#: Ela nomeia as duas buscas, porque uma
#: instalação fora das duas (um AppImage solto, um script no `~/bin`) existe e
#: esta frase não pode afirmar que o lançador não está na máquina — só que o
#: produto não o achou por onde sabe procurar.
DIZ_NAO_ACHEI = (
    "<b>Não localizei este lançador nesta máquina.</b> Procurei o atalho "
    "<code>.desktop</code> nas pastas de aplicativos e o comando no "
    "<code>PATH</code>. Instalado de outro jeito (um AppImage solto, por "
    "exemplo) ele não aparece aqui — e o perfil continua casando pelo nome do "
    "processo e pela janela."
)

#: O que o cartão da Steam mostra enquanto a primeira leitura não voltou.
#: **Nunca um número** — um número que ainda não foi lido é um número inventado.
AINDA_LENDO = "…"

#: A chave do único cartão com fonte.
STEAM = "steam"

#: O NOME DO GESTO DO "Abrir o lançador", e ele mora aqui porque o desenho e o
#: pacote precisam do MESMO texto: o desenho o escreve no `data-gesto` e o
#: pacote o registra em `@gesto(...)`. Digitá-lo duas vezes é como um botão
#: ganha endereço que ninguém atende — a forma de defeito que
#: `test_todo_gesto_do_html_tem_dono_ou_esta_declarado_sem_dono` cobra.
ABRIR = "abrir-lancador"

#: O «CONSERTAR» DOS OUTROS LANÇADORES MORREU AQUI — LANCADOR-LOCALIZAR-01,
#: 10/09/2026, e o que caiu foi o VASO, não a cura.
#:
#: `CONSERTAR_LANCADOR` e `CONSERTAR_LANCADOR_ROTULO` moravam nesta linha desde
#: 09/09. Ela leu o cartão como ele estava pintado — selo `LOCALIZADO`, moldura
#: `chega`, e a frase dizendo que *um jogo aberto por aqui entra pelo mesmo
#: caminho de qualquer outro* — e recusou o botão: *"na real não faz sentido.
#: Digo se tenho tudo instalado e tá pra ser identificado não tem pq ter o botão
#: de consertar."*  Uma cura oferecida onde a tela não declarou defeito nenhum
#: lê-se como cura de coisa nenhuma.
#:
#: **A LACUNA CONTINUA ABERTA**, e é por isso que `integrations/cura_por_estrada`
#: fica: `hefesto-launch` só age com jogo da Steam, e nenhum jogo do Heroic, do
#: Lutris, do RetroArch, do Dolphin ou do mGBA tem um. O vaso certo é a CARONA
#: — palavra dela de 16/08, em `app/actions/carona_do_wrapper.py:7`: *"nem
#: precisa ter um botão na gui, mas ele se auto corrigir ao clicarmos em aplicar
#: ou salvar o perfil"*. Quem o constrói é a LANCADOR-CARONA-01.

#: O NOME DO GESTO DO "Copiar a linha", pela mesma razão do :data:`ABRIR`.
#: DECISÃO DELA (PO, 04/09/2026, `07[01]`): *"Os dois, só quando faz falta"* —
#: o botão E a linha à mostra, e **só** no estado em que o cartão já diz
#: «linha intocável».
COPIAR = "copiar-a-linha"

#: O RÓTULO DO BOTÃO, palavra por palavra da decisão. Ele mora aqui e não no
#: pacote porque quem o escreve é o desenho; o pacote só atende o gesto.
COPIAR_ROTULO = "Copiar a linha"

# ---------------------------------------------------------------------------
# REGISTRAR O QUE O HEFESTO NÃO CONHECE — 08/09/2026, pedido dela
#
#     "Pensei em outro botão pra Adicc ionar novo Emulador Ou novo lançador
#      algo assim, pra devs mais experiementais e poermitir que o user
#      adicione algo novo"  # (noqa-acento): citação literal dela, como ela
#                           # escreveu — a versão anterior deste comentário
#                           # corrigia a digitação dela, que é falsificar a
#                           # citação. Nesta casa a fala dela não se limpa.
#
# A PORTA É UMA SÓ, e isso é desenho, não economia. O botão do cartão que não
# localizou e o botão global mandam o MESMO gesto; o que muda é o que vai
# preenchido — o do cartão já sabe a chave e o rótulo, o global nasce vazio.
# Dois gestos para o mesmo ato seriam duas validações, duas recusas e duas
# maneiras de gravar a mesma coisa, e a segunda envelheceria calada.
#
# O NOME MORA AQUI pela razão de sempre (:data:`ABRIR`): o desenho o escreve no
# `data-gesto` e o pacote o registra em `@gesto(...)`. Digitá-lo duas vezes é
# como um botão ganha endereço que ninguém atende.
# ---------------------------------------------------------------------------
#: O gesto de REGISTRAR. Ele tem duas metades, e as duas são o mesmo clique:
#: sem `forma`, ele só ABRE a tela apontando para quem; com `forma`, ele GRAVA.
ADICIONAR = "adicionar-lancador"

#: O RÓTULO DO BOTÃO DO CARTÃO — e ele DIZ A PALAVRA DO SELO, de propósito.
#:
#: A PALAVRA DELA VEIO EM DUAS ETAPAS, e a segunda corrigiu a primeira. Em
#: 08/09/2026 ela disse *"o Botão Abrir o Lançador deveria ser o Adicionar
#: Launcher"*, e o rótulo nasceu em inglês e igual ao do botão global. Olhando a
#: aba, ela voltou: *"Adicionar novo Lançador? Seria legal um sinônimo né?"* —
#: três pedidos numa frase, e os três estão atendidos aqui: **português**,
#: **"novo" no que é novo**, e **os dois botões falando palavras diferentes**.
#:
#: O SINÔNIMO SE ESCREVE SOZINHO: o selo deste cartão diz `NÃO LOCALIZADO`
#: (:data:`SELOS`), então o botão dele diz «Localizar». Selo e botão passam a
#: falar a MESMA palavra, e quem lê o cartão de cima para baixo lê uma frase só:
#: *não localizado → localizar este lançador*.
#:
#: **ELE NÃO INSTALA NADA, e é o próprio cartão que diz por quê:** a frase do
#: estado NÃO LOCALIZADO termina em *"Instalado de outro jeito (um AppImage
#: solto, por exemplo) ele não aparece aqui"*. Então «Localizar este Lançador»
#: quer dizer **"ele está aqui, eu te mostro onde"** — ela aponta o caminho e o
#: cartão passa a acender. O botão do cartão que ACHOU continua sendo «Abrir o
#: lançador»: são dois estados, dois botões, e trocar o rótulo dos dois faria o
#: cartão aceso oferecer um registro que já existe.
ADICIONAR_ROTULO = "Localizar este Lançador"

#: O RÓTULO DO BOTÃO GLOBAL — o que nasce vazio, para o que o Hefesto não
#: conhece de fábrica.
#:
#: **ELE É O OUTRO ATO, e a palavra dela separa os dois:** este diz *"tem um que
#: você não conhece"*, o do cartão diz *"ele está aqui, te mostro onde"*. Foi
#: para isso que ela pediu o sinônimo — dois botões com a mesma frase na mesma
#: tela fazem quem lê procurar a diferença que a tela não mostra.
#:
#: A PALAVRA «NOVO» É DELA, e ela é o que distingue: o que entra por aqui não
#: tem cartão nenhum na aba. E «emulador» saiu do rótulo sem perder o público
#: que ela nomeou — a dica da tela de registro nomeia os dois casos, e o exemplo
#: que ela mostra (`Ryujinx`) é justamente um emulador.
ADICIONAR_NOVO_ROTULO = "Adicionar novo Lançador"

# ---------------------------------------------------------------------------
# O SELETOR DO SISTEMA — LANCADOR-LOCALIZAR-01, 10/09/2026, decisão dela
#
#     "aí eu mesmo abro a tela e procuro o .desktop"   # noqa-acento: citação
#                                                      # literal dela
#
# Ela escolheu a opção (C) — **campo + botão que abre o seletor**, e o campo de
# texto FICA: ele é o único caminho para um AppImage solto, que não tem
# `.desktop`, e o próprio cartão promete cobrir esse caso.
#
# NÃO É CAPACIDADE NOVA, é ligar o que já está no produto: `ponte.escolher_
# arquivo` é um ponto de extensão que o piloto preenche ao subir
# (`hefesto_vivo.py`, `ponte.escolher_arquivo = self._escolher_arquivo`), com
# precedente vivo no «Importar» do rodapé.
# ---------------------------------------------------------------------------
#: O gesto do botão que abre o seletor do sistema. Ele mora aqui pela razão de
#: sempre (:data:`ABRIR`): o desenho o escreve no `data-gesto` e o pacote o
#: registra em `@gesto(...)`.
PROCURAR_O_ARQUIVO = "procurar-o-arquivo"

#: O RÓTULO, e ele NÃO diz «Procurar…» de propósito — foi medido nesta aba.
#: «Procurar de novo» já é o botão do topo do quadro, e ele quer dizer *"varra a
#: máquina outra vez"*: é a busca automática, sobre os SEIS cartões. Este quer
#: dizer *"eu te mostro o arquivo"*, sobre UM. Duas palavras iguais para dois
#: atos diferentes na mesma tela é a quebra de "mesma família, mesma coisa" que
#: esta aba já pagou uma vez (o `.lanc .btn` que encolhia).
#:
#: **É TEXTO DE TELA, e por isso está escrito para ela conferir na bancada.**
#: Se ela preferir a palavra dela — *"procuro o .desktop"* —, é trocar esta
#: linha: o gesto, a recusa e a régua não dependem do rótulo.
PROCURAR_O_ARQUIVO_ROTULO = "Escolher o arquivo…"

#: O TÍTULO DA CAIXA DE REGISTRO, e ele não é o rótulo de nenhum dos dois
#: botões — de propósito.
#:
#: A CAIXA É UMA E OS CAMINHOS SÃO DOIS (ver :func:`tela_do_registro_html`).
#: Enquanto os dois botões diziam a mesma frase, dar o rótulo de um deles ao
#: título era inofensivo; com a palavra dela separando os atos, deixou de ser:
#: aberta pelo botão do cartão do RetroArch (:data:`ADICIONAR_ROTULO`), a caixa
#: mostraria :data:`ADICIONAR_NOVO_ROTULO` — *"novo"* — em cima da linha que diz
#: *"Onde está o RetroArch nesta máquina"*. **Duas células da mesma tela dizendo
#: o contrário uma da outra** é o defeito que esta aba inteira existe para
#: matar.
#:
#: E O TÍTULO NEUTRO NÃO É EVASIVA — ele é o que o gesto FAZ nos dois caminhos,
#: e o gesto prova: `a07_lancadores.adicionar_lancador` procura em disco antes
#: de gravar e **recusa o que não acha**. Nada entra aqui sem ser localizado,
#: venha do botão do cartão ou do botão global. A linha logo abaixo do título
#: (:data:`NOVO_PARA_QUEM`) é quem diz de qual dos dois se trata.
TELA_DO_NOVO_TITULO = "Localizar um lançador"

#: O gesto de TIRAR. *O que se acrescenta se tira* — sem ele a lista dela vira
#: lixo permanente, e um cartão que ela não consegue remover é pior que a
#: ausência dele.
REMOVER = "esquecer-lancador"

#: O RÓTULO DO TIRAR. «Tirar daqui» é a palavra que esta aba JÁ usa para o mesmo
#: ato na lista de jogos do cartão da Steam — uma segunda palavra para o mesmo
#: gesto seria a terceira maneira de dizer a mesma coisa numa tela só.
REMOVER_ROTULO = "Tirar daqui"

#: O `id` da tela de registro. Ele é o alvo do `href="#…"` que ABRE a pop-up:
#: `.tela-nova` só aparece em `:target`, sem uma linha de script (`monta.
#: CSS_POPUP`). O desenho escreve o `id` e o `href`, e os dois saem daqui para
#: não poderem divergir — um `href` para um `id` que não existe abre NADA, e o
#: clique some sem uma palavra.
TELA_DO_NOVO = "novo-lancador"

#: OS DOIS CAMPOS QUE ELA DIGITA, e eles são `data-linha` — **nunca
#: `data-campo`**, e a diferença aqui é a diferença entre funcionar e brigar
#: com ela.
#:
#: O piloto recolhe a forma por `[data-linha],[data-campo]` e chaveia pelo
#: primeiro que existir (`hefesto_vivo.py`, o bloco `forma:`), então `data-linha`
#: basta para o valor chegar ao Python. O que ele NÃO faz é pintar: um
#: `data-campo` num `<input>` seria repintado a cada tique — dez vezes por
#: segundo, por cima do que ela está digitando. É o samba que a `A-TELA-SAMBA-01`
#: mediu, e num campo de texto ele não é cosmético: apaga a frase no meio.
NOVO_ROTULO = "lanc-novo-rotulo"
NOVO_ALVO = "lanc-novo-alvo"

#: O endereço da linha que diz PARA QUEM a tela de registro está aberta. Este é
#: `data-campo` de verdade — é TEXTO, o produto é o dono, e ela não digita nele.
NOVO_PARA_QUEM = "lanc-novo-para-quem"

# ---------------------------------------------------------------------------
# O STEAM INPUT — o que a Steam põe ENTRE o controle e o jogo
#
# DECISÃO DELA, 06/09/2026 (`D-0609-STEAM-DIVIDIDO`): **o Steam Input e a lista
# de exceções ficam na aba 07**; "Consertar", "Restaurar de fábrica" e "Aplicar
# aos jogos" ficam na 09.
#
# OS TRÊS NOMES MORAM AQUI pela mesma razão de :data:`ABRIR` e :data:`COPIAR`: o
# desenho os escreve no `data-gesto` e o pacote os registra em `@gesto(...)`.
# Digitá-los duas vezes é como um botão ganha endereço que ninguém atende.
#
# **"Steam Input" É PALAVRA DE TELA**, e está no glossário
# (`docs/A-LINGUA-DESTA-CASA-…`, §2) com o dono. `vdf`, `env` e `appid` NÃO
# são — nenhuma frase daqui os pronuncia.
# ---------------------------------------------------------------------------
#: "Desligar o Steam Input" — o gesto que tira a Steam do meio.
DESLIGAR_STEAM_INPUT = "desligar-steam-input"

#: "Este jogo não funciona" — marca o jogo na lista de exceções do Steam Input.
JOGO_NAO_FUNCIONA = "este-jogo-nao-funciona"

#: "Deixar tudo pronto" — os DOIS trabalhos com UM consentimento só.
TUDO_PRONTO = "deixar-tudo-pronto"

#: OS RÓTULOS, e os três vêm do MOTOR — nunca da minha redação. O primeiro é o
#: do botão que `emulation_actions.on_emulation_steam_input_disable` atende; os
#: dois últimos são os do modo simples de `daemon_actions` (o bloco
#: "FEAT-STEAM-SIMPLES-01", que traz `_STEAM_READY_CORPO` e
#: `format_game_broken_result`), e nasceram da frase dela — *"tem jogos que
#: precisamos ativar entrada steam, outros que temos que colocar comandos de
#: inicialização — é uma confusão real"*.
#:
#: O ENDEREÇO É O DO MOTOR, e não o da janela que está saindo
#: (`D-0609-GTK-LEVA-INTEIRA`): o que se reusa é a função dona da palavra, que
#: sobrevive à aposentadoria da janela — apontar para o arquivo dela seria
#: deixar um ponteiro que morre com ela.
DESLIGAR_STEAM_INPUT_ROTULO = "Desligar o Steam Input"
JOGO_NAO_FUNCIONA_ROTULO = "Este jogo não funciona"
TUDO_PRONTO_ROTULO = "Deixar tudo pronto"


def steam_input_html(frase: str) -> str:
    """A linha do Steam Input dentro do cartão da Steam, ou NADA.

    ELA NÃO É INVENTADA AQUI, e é o mesmo contrato frio de
    :func:`linha_do_wrapper_html`: este módulo não importa o produto (é o que
    deixa o gerador rodar como script solto), então a frase chega pronta em
    `Leitura.steam_input` — e quem a enche pergunta ao DONO dela
    (`emulation_actions.markup_status_steam_input`, a mesma que escreve a linha
    da janela velha).

    VAZIA É RESPOSTA: uma `Leitura` que não fala de Steam Input não põe linha
    nenhuma no cartão. É o estado da primeira meia volta e o de toda régua que
    monte uma `Leitura` à mão — e escrever "Desligado" ali seria a tela
    afirmando o resultado de uma medição que não aconteceu.

    UM `<br>` E NENHUMA CLASSE NOVA, e a escolha é de ALCANCE: a página que o
    produto renderiza é a publicada, e publicar é ato DELA — uma classe nova
    aqui só ganharia folha de estilo no dia em que ela aprovasse o desenho, e
    até lá a linha nasceria sem regra nenhuma. O `<br>` é a forma que o próprio
    cartão já usa para o aviso do jogo aberto (`a07_lancadores.
    aviso_do_jogo_aberto`), e ela chega à tela dela HOJE, pelo `blocos`, sem
    mexer num pixel do que ela aprovou. **A cor não se perde**: `.lanc-diz b` já
    é laranja no CSS da aba, e é por isso que quem enche a frase põe o `<b>` só
    no estado LIGADO.
    """
    return f"<br>{frase}" if frase else ""


def linha_do_wrapper_html(linha: str) -> str:
    """A linha de inicialização À MOSTRA, para ela selecionar e copiar à mão.

    A SEGUNDA SAÍDA DA DECISÃO [01], e ela existe porque a primeira pode
    falhar CALADA: pôr texto na área de transferência não devolve resposta, e
    a janela velha já resolve isso do mesmo jeito — o texto do aviso dela
    *"continua selecionável"* quando a cópia não vai
    (`docs/data/paridade-gtk-html.csv`, linha 237). Com a linha na tela, um
    `Ctrl+C` salva o dia sem o produto ter de acertar a seleção.

    ESTE MÓDULO NÃO COPIA NADA, e o parágrafo acima é prosa: quem fala com a
    área de transferência é `a07_lancadores.para_a_area_de_transferencia`, e
    nomear a classe do GTK aqui daria à régua da paridade um endereço onde não
    há um ato. É o defeito que esta casa nomeia como *a régua confundindo a
    PALAVRA com o ATO*.

    ELA NÃO É INVENTADA AQUI. Este módulo **não importa nada do produto** (é o
    que deixa o gerador rodar como script solto), então a linha chega pelo
    contrato frio: `Leitura.linha`, que o pacote enche de
    `steam_launch_options.WRAPPER_LAUNCH`. Sem ela não há o que mostrar — e o
    desenho cala em vez de escrever uma linha de mentira, que é a doença que
    esta aba inteira nasceu para curar.

    `<code>` E NÃO `<pre>`: são 143 caracteres numa coluna de cartão, e o
    `<pre>` não quebra — ele empurraria uma barra de rolagem lateral para
    dentro do cartão. Quem quebra é o CSS (`.linha-do-wrapper`, em `aba07.py`),
    com `word-break:break-all`, porque a linha não tem espaço onde caiba.
    MEDIDO no Chrome, 1920x1080: o bloco fica com 523 px dentro da coluna do
    cartão e a janela continua em 1180x777, sem rolagem lateral.
    """
    return (f'<div class="linha-do-wrapper"><code>{_e(linha)}</code></div>'
            if linha else "")


@dataclass(frozen=True)
class DoDisco:
    """O que o DISCO diz sobre os cartões que não são a Steam — já respondido.

    **ELE EXISTE PORQUE A PINTURA NÃO PODE PERGUNTAR — 09/09/2026, e é uma
    recaída medida.** As três respostas de baixo (a biblioteca de cada
    lançador, a linha do «Flatpak» e quem tem estrada para a cura) nasceram
    dentro de :func:`cartao_sem_censo`, chamadas na hora de desenhar o cartão —
    isto é, DEZ VEZES POR SEGUNDO, dentro do tique.

    **O CUSTO FOI MEDIDO NESTA BANCADA, com os cinco lançadores dela no
    disco:** `cartoes()` levava **6,4 ms de mediana** (30 voltas, máximo 18,6
    ms) num orçamento de 100 ms para a janela inteira, e agora leva **0,03
    ms** — o disco saiu do tique e voltou para a :class:`a07_lancadores._Vigia`,
    que é onde o próprio arquivo já escrevia que ele tem de viver: *"a pintura
    NUNCA bloqueia"*.

    É FRIO como a :class:`Leitura` e pela mesma razão: quem lê é o pacote, na
    thread da vigia; o desenho recebe texto pronto e não abre arquivo nenhum.
    """

    #: A linha de baixo de cada cartão, por chave: `(chave, linha)`. Já é a
    #: resposta final — inclusive a do «Flatpak», que é outra pergunta (ver
    #: :func:`resposta_do_flatpak`). Chave AUSENTE = nada a dizer, e o cartão
    #: fica com o travessão.
    resumos: tuple[tuple[str, str], ...] = ()

    #: **O CAMPO `estradas` SAIU — LANCADOR-LOCALIZAR-01, 10/09/2026.** Ele
    #: guardava as chaves que TÊM por onde receber o ambiente, e existia para
    #: UMA coisa: decidir o botão «Consertar» do cartão LOCALIZADO. O botão saiu
    #: por palavra dela, e um campo que ninguém lê é a segunda leitura de disco
    #: que a :class:`DoDisco` inteira existe para não pagar — `tem_estrada` abre
    #: o `config.json` do Heroic e as caixas do Flatpak a cada volta da vigia.

    def resumo(self, chave: str) -> str:
        return dict(self.resumos).get(chave, "")


#: A RESPOSTA VAZIA — a primeira meia volta, e o padrão de toda `Leitura`
#: montada à mão. Ela é um SINGLETON porque :class:`DoDisco` é congelada: duas
#: instâncias vazias são a mesma coisa ocupando dois lugares, e uma chamada em
#: argumento padrão é o que o `B008` recusa.
SEM_DISCO = DoDisco()


def medir_no_disco(onde_estao: tuple[tuple[str, str], ...],
                   declarados: tuple[SemCenso, ...] = (),
                   lar: Path | None = None,
                   raiz_sistema: Path | None = None) -> DoDisco:
    """BLOQUEIA — abre os arquivos dos lançadores e responde o que o cartão mostra.

    **QUEM CHAMA É A VIGIA, e só ela** (`a07_lancadores._Vigia.ler`, na thread
    de fundo). Chamar isto de dentro da pintura é o defeito que a
    :class:`DoDisco` documenta, com o número medido.

    SÓ O QUE FOI ACHADO ENTRA. Um cartão sem caminho em `onde_estao` é um
    lançador que a busca não achou (ou não procurou), e perguntar pela
    biblioteca de um programa ausente é abrir pastas para ouvir "não existe".

    :param lar: o `HOME` a inspecionar; o padrão é o de verdade. A régua passa
        um lar de mentira, e por isso ele viaja junto com `raiz_sistema` — os
        dois formam o par que faz uma medição ficar inteira dentro do `tmp`.
    """
    onde = dict(onde_estao)
    itens = [x for x in procurados(declarados) if x.chave != STEAM]
    #: OS `app-id` DOS LANÇADORES QUE VIERAM DO FLATPAK — a lista de que o
    #: cartão «Flatpak» precisa para mudar de pergunta (§5.4). Ela sai do
    #: CAMINHO em que cada `.desktop` foi achado, e não do rótulo do cartão:
    #: um `io.mgba.mGBA` publicado por `/usr/share/applications` é o pacote da
    #: distribuição, que não tem caixa a examinar. Ver
    #: :func:`sandbox_dos_lancadores.app_id_do_atalho`.
    #:
    #: **UM CARTÃO PODE SER DOIS PROGRAMAS**, e por isso a lista não sai só do
    #: caminho achado: `app_ids_do_cartao` completa o `.desktop` da busca com
    #: os demais `app-id` do cartão que têm caixa no disco. Sem isso o
    #: «Dolphin · mGBA» entrava com UM, e o cartão «Flatpak» contou 4 numa
    #: máquina com 5 (medido em 09/09/2026).
    vistos: list[str] = []
    for item in itens:
        # O PRÓPRIO FLATPAK FICA DE FORA: ele é achado pelo `PATH`
        # (`/usr/bin/flatpak`), não tem caixa, e um cartão que se examinasse a
        # si mesmo responderia sobre a coisa errada.
        if item.chave == "flatpak" or not onde.get(item.chave):
            continue
        for app_id in _caixa.app_ids_do_cartao(item.atalhos,
                                               onde.get(item.chave), lar,
                                               raiz_sistema):
            if app_id not in vistos:
                vistos.append(app_id)
    caixas = resposta_do_flatpak(tuple(vistos), lar, raiz_sistema)

    resumos: list[tuple[str, str]] = []
    for item in itens:
        if not onde.get(item.chave):
            continue
        #: A LEITURA É DO DONO (`integrations/censo_dos_lancadores`), e o
        #: resumo também: montar a frase aqui seria a segunda verdade sobre a
        #: mesma contagem, e "37 jogos" contra "37 na biblioteca" na mesma tela
        #: é a cara de uma janela montada em dois lugares que não se falam.
        linha = _censo.biblioteca_do_cartao(item.chave, lar).resumo
        #: **A LINHA DO «FLATPAK» É OUTRA PERGUNTA — §5.4, 09/09/2026.** Ele
        #: não tem biblioteca (o censo diz `SEM_BIBLIOTECA`, e o resumo sai
        #: vazio), e até hoje a linha dele ficava com um travessão.
        if not linha and item.chave == "flatpak":
            linha = caixas
        if linha:
            resumos.append((item.chave, linha))
    return DoDisco(tuple(resumos))


@dataclass(frozen=True)
class Leitura:
    """O que o disco respondeu sobre a Steam. É o contrato pacote → desenho.

    Ele é FRIO de propósito — só tuplas de texto, nenhum objeto do motor. Assim
    o desenho não importa `sentinela_do_wrapper` (e o gerador continua rodando
    sem o produto), e a régua da aba monta uma `Leitura` à mão para provar cada
    estado do cartão sem tocar no disco.
    """

    #: appids cuja linha de inicialização JÁ chama o wrapper.
    com_wrapper: tuple[str, ...] = ()
    #: os que não chamam e o produto CONSEGUE repor: `(appid, rótulo, porquê)`.
    reparaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que não chamam e ninguém deve tocar (lista de IGNORE estendida à mão).
    intocaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que ELA tirou, no `jogos_sem_wrapper.txt`: `(appid, rótulo)`.
    recusados: tuple[tuple[str, str], ...] = ()
    #: os que ELA dispensou do LEMBRETE, no `launch_dialog_dismissed.json`:
    #: `(appid, rótulo)`. É outra lista e outra pergunta — ver `lista_de_jogos`.
    dispensados: tuple[tuple[str, str], ...] = ()
    #: quantos jogos estão INSTALADOS — o vdf guarda linha de jogo desinstalado.
    instalados: int = 0
    #: quantos jogos já têm PONTE CONFIRMADA no perfil, de
    #: `prontuario_dos_jogos.pontes_confirmadas`. É a fonte do carimbo que o
    #: desenho prometia (`◆ 3 jogos já sabem por onde entrar`) e que nasceu
    #: digitado — medido em 02/09/2026, o produto respondia ZERO.
    pontes: int = 0
    #: Onde cada lançador PROCURADO foi achado: `(chave, local)`. Local vazio =
    #: **procurei e não achei**; chave AUSENTE do mapa = **não procurei**. A
    #: distinção é o ponto inteiro: as duas viram frases diferentes na tela.
    #: A `steam` entrou no mapa em 02/09 — ver :data:`A_STEAM`.
    onde_estao: tuple[tuple[str, str], ...] = ()
    #: O QUE ELA DECLAROU no `maquina.json` — 08/09/2026. Um lançador que o
    #: Hefesto não conhece de fábrica, ou o ENSINO de onde um de fábrica está.
    #:
    #: ELE VEM PELA `Leitura` e não por import, e é a mesma razão de tudo neste
    #: arquivo: o desenho não importa o produto (é o que deixa o gerador rodar
    #: como script solto), então quem lê o disco é o pacote e o que chega aqui é
    #: dado frio. Uma `Leitura` montada à mão — e a régua desta aba monta várias
    #: — não declara nada, e aí só os de fábrica viram cartão.
    declarados: tuple[SemCenso, ...] = ()
    #: a frase da sentinela, que já nomeia o jogo e já diz o que vai acontecer.
    frase: str = ""
    #: A LINHA DE INICIALIZAÇÃO do Hefesto — o que o botão «Copiar a linha»
    #: copia e o que o bloco à mostra exibe. Ela é `steam_launch_options.
    #: WRAPPER_LAUNCH`, e vem por aqui porque o desenho não importa o produto.
    #:
    #: VAZIA É RESPOSTA, e não descuido: sem linha o cartão não oferece o botão
    #: nem o bloco. Um botão de copiar sobre uma linha que o desenho não tem
    #: copiaria o vazio e diria "Copiado!".
    linha: str = ""
    #: A FRASE DO STEAM INPUT, já pronta para a tela — vinda do dono dela
    #: (`emulation_actions.markup_status_steam_input`). Ver
    #: :func:`steam_input_html`.
    #:
    #: VAZIA É RESPOSTA: a leitura não falou de Steam Input, e o cartão cala.
    steam_input: str = ""
    #: O Steam Input está LIGADO fora da lista de exceções? `None` = não sei
    #: (não medi, ou não achei a Steam). **É ele que decide o botão**, e não a
    #: frase: uma frase presente com `None` diz "não achei a Steam", e oferecer
    #: "Desligar" ali seria oferecer uma recusa.
    steam_input_ligado: bool | None = None
    erros: tuple[str, ...] = ()
    #: O QUE O DISCO DIZ DOS OUTROS CARTÕES, medido na MESMA passada da vigia:
    #: a linha de cada um e quem tem estrada para a cura. Ver :class:`DoDisco`.
    #:
    #: VAZIO É RESPOSTA, e é o estado da primeira meia volta: cartão sem linha
    #: fica com o travessão e sem o «Consertar» — que é o que uma leitura que
    #: ainda não aconteceu autoriza a tela a dizer.
    do_disco: DoDisco = SEM_DISCO

    @property
    def onde_esta_a_steam(self) -> str | None:
        """Onde a Steam foi achada; `''` = procurei e não achei; `None` = não procurei.

        A TERCEIRA RESPOSTA É A QUE IMPORTA. Uma `Leitura` montada à mão (a
        régua desta aba monta várias) não tem a `steam` no mapa, e ali `None`
        quer dizer *"esta leitura não fala de presença"* — o cartão então segue
        só o censo, que era todo o comportamento anterior. Colapsar `None` em
        `''` faria toda régua antiga passar a ver `NÃO ACHEI`.
        """
        return dict(self.onde_estao).get(STEAM)

    @property
    def viu_a_biblioteca(self) -> bool:
        """A leitura ALCANÇOU a biblioteca da Steam de algum jeito?

        POR QUE ELA EXISTE, e não basta olhar `onde_esta_a_steam`: as duas
        buscas respondem coisas diferentes e podem discordar sem que nenhuma
        esteja errada. Uma Steam instalada por um caminho que os três `.desktop`
        conhecidos não cobrem (um AppImage, um script no `~/bin`) não aparece na
        procura — e ainda assim o `localconfig.vdf` dela está lá, com a
        biblioteca inteira. Dizer `NÃO ACHEI` sobre uma biblioteca que o produto
        acabou de ler seria trocar um erro por outro.

        O `erros` ENTRA na conta: um vdf ilegível é um vdf que EXISTE.
        """
        return bool(self.erros or self.com_wrapper or self.reparaveis
                    or self.intocaveis or self.recusados or self.instalados)


def _plural(n: int, um: str, muitos: str) -> str:
    return f"{n} {um if n == 1 else muitos}"


def lista_de_jogos(lida: Leitura) -> str:
    """As linhas dentro do cartão da Steam: quem falta, quem ELA tirou, e quem
    ELA mandou não perguntar mais.

    OS INTOCÁVEIS APARECEM SEM BOTÃO, de propósito: o produto não os repõe (o
    `apply_wrapper_vdf_text` os pula por construção) e "tirar daqui" um jogo que
    já está fora do reparo não mudaria nada — um botão que não muda nada é o que
    esta casa chama de botão que finge.

    OS DISPENSADOS TÊM BOTÃO, e ele nasceu em 02/09/2026 por decisão dela. Eles
    são o `launch_dialog_dismissed.json`, escrito pelo botão *"Não perguntar
    para este jogo"* do lembrete da GTK — e até hoje de manhã **nenhuma tela
    desta casa os mostrava**. Mostrar curou o silêncio pela metade: a dispensa
    continuava sendo um gesto SEM VOLTA pela tela, porque o motor só tinha
    `add_dismissed_appid`. Agora tem o par (`remove_dismissed_appid`), e a linha
    ganha *"Voltar a perguntar"* — pelo mesmo motivo que o "Voltar a usar"
    existe ao lado do "Não usar neste jogo": *um gesto que só vai numa direção
    deixa a pessoa presa no estado em que clicou.*

    OS INTOCÁVEIS CONTINUAM SEM BOTÃO, e a diferença é a que separa as duas
    listas: ali não há gesto que mude nada; aqui há.

    A LISTA É OUTRA, e não a mesma dos recusados: `jogos_sem_wrapper.txt` diz
    *"não ponha o atalho neste jogo"* e o dispensado diz *"não me lembre deste
    jogo"*. Um jogo pode estar num, no outro, ou nos dois — juntá-las numa só
    apagaria a diferença que faz a pessoa entender o que ela mesma pediu.
    """
    itens = [
        JogoNaLista(appid=a, rotulo=r, porque=p,
                    gesto="tirar-daqui", botao="Não usar neste jogo")
        for a, r, p in lida.reparaveis
    ]
    itens += [JogoNaLista(appid=a, rotulo=r, porque=p)
              for a, r, p in lida.intocaveis]
    itens += [
        JogoNaLista(appid=a, rotulo=r, porque="você tirou este jogo",
                    gesto="voltar-a-usar", botao="Voltar a usar")
        for a, r in lida.recusados
    ]
    itens += [
        JogoNaLista(appid=a, rotulo=r,
                    porque="você mandou não perguntar mais por este jogo",
                    gesto="voltar-a-perguntar", botao="Voltar a perguntar")
        for a, r in lida.dispensados
    ]
    return linhas_de_jogos(itens, vazio=LISTA_VAZIA)


def acao_de_localizar(chave: str) -> Acao:
    """O botão «Localizar este Lançador» de UM cartão — e ele é o MESMO nos SEIS.

    ELE NASCEU EM DOIS LUGARES E FALTOU NUM DELES. Em 08/09/2026 o botão do
    estado NÃO LOCALIZADO foi escrito dentro de :func:`cartao_sem_censo`, que
    responde por CINCO cartões — e o sexto, a Steam, tem função própria
    (:func:`cartao_da_steam`) e ficou com o botão velho. Numa máquina sem Steam
    o cartão dela saía com o selo `NÃO LOCALIZADO`, a frase :data:`DIZ_NAO_ACHEI`
    e um «Abrir o lançador» que só sabe abrir a Steam que não está lá.

    **E O BURACO FECHAVA POR CIMA:** a outra porta é o botão global, e ele
    RECUSA um nome que já tem cartão de fábrica mandando usar o botão do cartão
    — que naquele cartão não existia. A tela mandava clicar onde não havia nada,
    e não havia como dizer ao produto onde a Steam está.

    A CURA É ESTA FUNÇÃO, e não uma segunda cópia da linha: enquanto o botão for
    escrito nos dois lugares, o próximo cartão com desenho próprio repete o
    mesmo esquecimento. É a regra de 05/09 desta casa — *quando a cura conhece a
    causa, ela cobre TODOS os chamadores.*

    O `href` É O QUE ABRE A TELA, e ele é mecânico: a `.tela-nova` aparece por
    `:target` (`monta.CSS_POPUP`), e **só uma âncora muda o fragmento** — ver
    :attr:`Acao.href`.
    """
    return Acao(ADICIONAR_ROTULO, "", ADICIONAR, chave, href=f"#{TELA_DO_NOVO}")


def acao_de_tirar(chave: str) -> Acao:
    """O «Tirar daqui» de UM cartão, pela mesma razão de :func:`acao_de_localizar`.

    *O QUE SE ACRESCENTA SE TIRA*, e isso vale para os SEIS: um cartão que ela
    ensinou e não consegue desensinar deixa o caminho errado gravado para
    sempre. Quem decide se ele aparece é o chamador, que sabe se há declaração.
    """
    return Acao(REMOVER_ROTULO, "", REMOVER, chave)


def cartao_da_steam(lida: Leitura | None) -> Lancador:
    """O ÚNICO cartão com fonte, e cada palavra dele sai de uma medição.

    O SELO SEGUE `reparaveis`, e não a soma dos faltantes: um jogo com a lista
    de IGNORE estendida à mão está sem o wrapper e **não deve ser tocado** —
    remover só o trecho do Hefesto deixaria um fragmento-comando que impede o
    jogo de abrir. Contá-lo como "não chega" acenderia um `Consertar` que não
    conserta aquele jogo.

    A PRESENÇA DEIXOU DE SER CONSTANTE — 02/09/2026, e a acusação foi provada
    antes de curada. Com o `HOME` desviado para uma casa de mentira e o `PATH`
    vazio (nenhuma Steam, nenhum vdf, nenhum jogo), este cartão respondia:

        selo 'ok' (**CHEGAM**) · presente True · "1 encontrado" no topo
        "Os controles chegam. O atalho de inicialização está no lugar em 0
         jogos da sua biblioteca."

    Uma máquina sem Steam recebia o selo VERDE e a promessa — enquanto os cinco
    cartões vizinhos, na mesma tela, diziam `NÃO ACHEI`. Era o único cartão cuja
    presença ninguém mediu, porque era o único com censo: ter fonte para o
    INTERIOR não responde se o lançador está aqui.

    AS DUAS PERGUNTAS CONTINUAM SEPARADAS, e é por isso que o `NÃO ACHEI` exige
    as DUAS respostas negativas (:meth:`Leitura.viu_a_biblioteca`): uma Steam
    instalada por um caminho que os três `.desktop` conhecidos não cobrem não
    aparece na procura, e ainda assim a biblioteca dela foi lida. Dizer "não
    achei" sobre uma biblioteca recém-lida seria trocar um erro por outro.

    O ESTADO NÃO LOCALIZADO OFERECE O «LOCALIZAR», e a razão inteira está em
    :func:`acao_de_localizar` — ele faltava aqui, e o cartão da Steam era o
    único da aba sem saída nenhuma numa máquina onde a Steam não está pelos
    caminhos de fábrica.
    """
    # A FILEIRA É A QUE ELA APROVOU, botão por botão: o cartão `CHEGAM` do
    # desenho tem `Abrir o lançador` + `Criar perfil para um jogo`, e o
    # `NÃO CHEGAM` tem `Consertar` + `Ver o que impede` + `Abrir o lançador`.
    # NÃO acrescentei um `Procurar de novo` aqui: ele já está no topo do quadro,
    # e um segundo botão com o mesmo texto na mesma tela é a quebra de "mesma
    # família, mesma coisa" que esta aba já pagou uma vez (o `.lanc .btn` que
    # encolhia). A exceção é o cartão em ERRO, o único estado em que ele
    # responde uma pergunta que o cartão fez.
    # O BOTÃO GANHOU ENDEREÇO — 03/09/2026, decisão 17 dela (ligar o botão, com
    # o gesto isento da prova automática). Quem atende é
    # `a07_lancadores.abrir_lancador`, e o `v` diz QUAL lançador — sem ele o
    # gesto teria de adivinhar pelo texto do botão, que é o mesmo nos seis.
    abrir = Acao("Abrir o lançador", "", ABRIR, STEAM)
    criar = Acao("Criar perfil para um jogo", "", "", "")
    # E O TIRAR, SÓ ONDE HÁ O QUE TIRAR — a mesma regra dos outros cinco
    # (:func:`cartao_sem_censo`). Ela só ganha o botão depois de ensinar onde a
    # Steam está; sem isso não há declaração a esquecer, e o botão fingiria.
    # UMA `Leitura` MONTADA À MÃO não declara nada, então este ramo sai vazio
    # em toda régua antiga e na página publicada — que nasce de `cartoes(None)`.
    tirar = ((acao_de_tirar(STEAM),)
             if any(x.chave == STEAM for x in (lida.declarados if lida else ()))
             else ())
    # O `fora=SEM_LISTA` DOS DOIS RAMOS É CURA, e não enfeite: sem ele o
    # `steam-fora` sai vazio, o `escrever()` do bootstrap o troca por `—` e a
    # tela ganha um traço solto no pé do cartão. Ver :data:`SEM_LISTA`.
    if lida is None:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos=AINDA_LENDO,
            diz="Estou lendo a sua biblioteca da Steam…",
            acoes=(abrir, criar), fora=SEM_LISTA, tem_lista=True)
    if lida.onde_esta_a_steam == "" and not lida.viu_a_biblioteca:
        # PROCUREI E NÃO ACHEI, e a frase é a MESMA dos outros cinco
        # (:data:`DIZ_NAO_ACHEI`) de propósito: ela já nomeia as duas buscas e
        # já ressalva a instalação fora delas. Uma segunda redação para o mesmo
        # fato seria texto de tela que ela não decidiu, e duas frases que
        # envelhecem separadas — o defeito que a decisão 14 dela nomeou
        # ("uma frase, um dono").
        #
        # O BOTÃO É O «LOCALIZAR», E NÃO O «ABRIR» — 08/09/2026, e era um BECO:
        # o produto não sabe abrir uma Steam que não achou, e o botão global
        # recusava mandando usar um botão que este cartão não tinha. Ver
        # :func:`acao_de_localizar`.
        return Lancador(
            chave=STEAM, nome="Steam", selo="off", jogos="—",
            diz=DIZ_NAO_ACHEI, acoes=(acao_de_localizar(STEAM), *tirar),
            fora=SEM_LISTA, tem_lista=True)
    if lida.erros:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos="—",
            diz=("<b>Não consegui ler a biblioteca da Steam</b> — "
                 f"{_e(lida.erros[0])}. Nada foi alterado."),
            acoes=(Acao("Procurar de novo", "", "procurar", STEAM), abrir, criar,
                   *tirar),
            fora=SEM_LISTA, tem_lista=True)

    falta = len(lida.reparaveis)
    if falta:
        # A FRASE É DA SENTINELA, e não minha: ela já nomeia o jogo, já diz o
        # que ele perdeu e já diz o que vai acontecer. "1 jogo com problema" é
        # exatamente o texto que deixou o Pragmata quebrado a noite inteira.
        diz = _e(lida.frase) or (
            f"<b>Sem wrapper</b> — {_plural(falta, 'jogo', 'jogos')} sem o "
            "atalho de inicialização do Hefesto na linha de comando.")
        acoes: tuple[Acao, ...] = (
            Acao("Consertar", "verde", "consertar", STEAM),
            Acao("Ver o que impede", "", "ver-o-que-impede", STEAM), abrir)
        selo = "warn"
    else:
        # DOIS NÚMEROS QUE SE CONTRADIZEM A UMA LINHA DE DISTÂNCIA — achado em
        # 03/09/2026, na foto do produto, e é DECISÃO DELA como resolver:
        #
        #     canto do cartão   22 jogos instalados       (`lida.instalados`)
        #     corpo do cartão   …está no lugar em 63 jogos da sua biblioteca.
        #                                               (`len(lida.com_wrapper)`)
        #
        # As duas afirmações são VERDADEIRAS — "biblioteca" inclui o que não
        # está instalado, "instalados" não —, e a tela não dava como saber
        # disso. Quem lê vê 63 > 22 e conclui que um dos dois está errado.
        #
        # DECIDIDO — PO, 04/09/2026, `07[04]`: *"O corpo nomeia o conjunto"*.
        # Três palavras, zero linha nova, nenhum botão: as duas contagens
        # continuam as que o produto mediu, e a frase passa a dizer que elas
        # contam coisas diferentes. As outras duas opções morreram por medição:
        # contar só instalados apagaria as dezenas de jogos já preparados, e pôr
        # os dois números no canto disputa a linha com o selo em janela estreita.
        diz = ("Os controles chegam. O atalho de inicialização está no lugar em "
               f"{_plural(len(lida.com_wrapper), 'jogo', 'jogos')} da sua "
               "biblioteca (instalados ou não).")
        acoes = (abrir, criar)
        # O SELO DA STEAM É `LOCALIZADO` COMO OS OUTROS CINCO — 11/09/2026,
        # ordem dela: *"troca o chegam da steam por localizado como os  (noqa-acento) citação
        # demais"*.
        #
        # A `CHEGAM` era a última sobra de quando o selo respondia DUAS
        # perguntas ao mesmo tempo — *"está aqui?"* e *"o controle chega?"*. Os
        # outros cinco cartões já tinham sido separados em 09/09
        # (`D-0809-O-SELO-DOS-LANCADORES-DIZ-LOCALIZADO`), e a Steam ficou para
        # trás com uma palavra só dela: seis cartões lado a lado, cinco dizendo
        # a mesma coisa e um dizendo outra, sem que a diferença significasse
        # nada para quem lê.
        #
        # O VEREDITO NÃO SE PERDEU, e é o que impede esta troca de apagar
        # informação: o `warn` (`NÃO CHEGAM`) continua nascendo quando há
        # impedimento, e o corpo do cartão continua dizendo em quantos jogos o
        # atalho está no lugar. O que sai é a palavra que dizia «está tudo bem»
        # num lugar em que as outras cinco dizem «achei».
        selo = "localizado"

    # A LINHA DO STEAM INPUT — `D-0609-STEAM-DIVIDIDO`, decisão dela.
    #
    # ELA VEM DEPOIS DO CORPO E ANTES DA LINHA À MOSTRA, e a ordem é de assunto:
    # o corpo fala do ATALHO de inicialização, esta fala de quem ENTREGA o
    # controle ao jogo, e o bloco de baixo é a saída manual do primeiro.
    #
    # E ELA SÓ OCUPA A TELA QUANDO HÁ MEDIÇÃO. Uma `Leitura` sem
    # `steam_input` — a primeira meia volta, e toda régua que monte uma à mão —
    # sai daqui byte a byte como saía antes; é a mesma regra do carimbo, da
    # lista de jogos e do bloco da linha.
    diz = diz + steam_input_html(lida.steam_input)

    # OS DOIS, SÓ QUANDO FAZ FALTA — PO, 04/09/2026, `07[01]`.
    #
    # O ESTADO É O DA LINHA INTOCÁVEL, e não o da recusa do Consertar: essa
    # metade CAIU em 03/09, quando a recusa passou a armar a `_VigiaDaSteam`,
    # que repõe sozinha assim que o jogo e a Steam fecham. O buraco que sobra é
    # só o dos intocáveis — os jogos que o produto DECIDIU nunca tocar
    # (`apply_wrapper_vdf_text` os pula por construção), e para os quais o
    # carimbo já escreve *"N jogos com a linha intocável — só reparo manual"*.
    # Era uma tela prometendo um reparo manual sem oferecer um caminho para
    # fazê-lo: **não existia UM botão de copiar em toda a interface nova.**
    #
    # E OS DOIS, e não um: a cópia pode falhar em SILÊNCIO — pôr texto na área
    # de transferência não devolve resposta nenhuma —, e aí a linha à mostra
    # ainda salva. É o que a janela velha faz no mesmo aviso desde sempre.
    #
    # NO DIA BOM NADA DISSO OCUPA A TELA: sem intocáveis, o cartão sai daqui
    # byte a byte como saía antes.
    if lida.intocaveis and lida.linha:
        acoes = (*acoes, Acao(COPIAR_ROTULO, "", COPIAR, STEAM))
        diz = diz + linha_do_wrapper_html(lida.linha)

    # O «LOCALIZAR» ENTRA NOS DOIS ESTADOS BONS — LANCADOR-LOCALIZAR-01,
    # 10/09/2026, e ele é o MESMO botão dos outros cinco cartões.
    #
    # ELE JÁ ESTAVA NO `off` DESDE 08/09 e faltava aqui, que é a metade do
    # buraco que ninguém tinha medido: quando a Steam ESTÁ achada e o que o
    # Hefesto achou não é o que ela quer, não havia por onde dizer — e a recusa
    # do botão global confessava isso na tela (*"hoje o cartão não tem por onde
    # trocar"*), que é o que a decisão dela de 07/09 proíbe.
    #
    # E É A REGRA DE 05/09 DESTA CASA: *quando a cura conhece a causa, ela cobre
    # TODOS os chamadores.* Pôr o botão só nos cinco `cartao_sem_censo` deixaria
    # o sexto repetindo, em outro estado, exatamente o esquecimento de 08/09 —
    # que foi a Steam ficar de fora por o botão ser LINHA e não função. Ver
    # :func:`acao_de_localizar`.
    #
    # DEPOIS DO QUE ELA FAZ, ANTES DO QUE ELA DESFAZ: localizar de novo é ato
    # CORRETIVO, e ato corretivo não disputa a primeira posição com o «Abrir».
    acoes = (*acoes, acao_de_localizar(STEAM))

    # O TIRAR VAI POR ÚLTIMO nos dois estados bons, e por último de propósito: o
    # que ela desfaz nunca disputa a primeira posição com o que ela FAZ.
    acoes = (*acoes, *tirar)

    return Lancador(
        chave=STEAM, nome="Steam", selo=selo,
        jogos=_plural(lida.instalados, "jogo instalado", "jogos instalados"),
        diz=diz, acoes=acoes, carimbo=carimbo_da_steam(lida),
        fora=lista_de_jogos(lida), tem_lista=True,
        # ERA `True` CRAVADO, e o `True` cravado é o que fazia a conta do topo
        # dizer "1 encontrado" numa máquina sem Steam nenhuma. As duas respostas
        # entram porque **ou uma ou outra** basta: achei o lançador em disco, ou
        # li a biblioteca dele. O ramo de cima já devolveu quando as duas são
        # negativas, então aqui pelo menos uma é verdadeira — escrever a conta
        # mesmo assim é o que impede a constante de voltar por descuido.
        presente=bool(lida.onde_esta_a_steam) or lida.viu_a_biblioteca)


def carimbo_da_steam(lida: Leitura) -> str:
    """As duas notícias do carimbo, na ordem em que ela precisa lê-las.

    O CARIMBO NÃO É SÓ BOA NOTÍCIA. Ele é o único lugar que sobra no cartão, e
    calar sobre um jogo que o produto DECIDIU não tocar é como ele fica sem o
    atalho para sempre sem ninguém saber.

    A PONTE CONFIRMADA VOLTA AO CARTÃO, e ela é a promessa que o desenho fazia
    e o produto tinha largado: o HTML de 02/09 dizia ``◆ 3 jogos já sabem por
    onde entrar`` com o número DIGITADO, e `prontuario_dos_jogos` já respondia a
    mesma pergunta desde sempre, sem um chamador. Agora responde daqui — e no
    dia em que ela confirmar a primeira ponte, o carimbo acende sozinho.

    ZERO SOME, e é o mesmo critério que `carimbo_html` já aplicava: *"0 jogos
    já sabem por onde entrar"* ocuparia a linha para não dizer nada.
    """
    partes: list[str] = []
    if lida.pontes:
        partes.append(f"{_plural(lida.pontes, 'jogo já sabe', 'jogos já sabem')} "
                      "por onde entrar")
    if lida.intocaveis:
        partes.append(f"{_plural(len(lida.intocaveis), 'jogo', 'jogos')} com a "
                      "linha intocável — só reparo manual")
    return " · ".join(partes)


def resposta_do_flatpak(vizinhos: tuple[str, ...], lar: Path | None = None,
                        raiz_sistema: Path | None = None) -> str:
    """A linha do cartão «Flatpak» — §5.4 da sprint, e ele MUDA DE PERGUNTA.

    ELE NÃO É LANÇADOR: é o runtime dos outros cinco, e por isso o censo lhe
    devolve `SEM_BIBLIOTECA` e a linha ficava com um travessão. A pergunta que
    só ele responde é a da §4: **o controle entra na caixa em que o jogo roda?**

    QUEM MEDE É :mod:`sandbox_dos_lancadores`, e a lista de quem examinar vem de
    fora — são os lançadores que a aba ACHOU e que vieram do Flatpak, um
    `app-id` cada. Perguntar pela caixa de um lançador nativo devolveria "não
    instalado" e baixaria a conta por um motivo que não é dela.

    **ELA BLOQUEIA**, e por isso quem a chama é :func:`medir_no_disco`, na
    vigia — nunca a pintura.
    """
    return _caixa.resposta_do_flatpak(vizinhos, lar, raiz_sistema).resumo


def cartao_sem_censo(item: SemCenso, onde: str | None,
                     do_disco: DoDisco = SEM_DISCO) -> Lancador:
    """Um dos cinco cartões cujo INTERIOR o produto não lê — em três estados.

    E OS TRÊS SÃO DIFERENTES, que é a razão de esta função existir:

    ==============  ============  =========================================
    ``onde``        selo          o que a tela passa a dizer
    ==============  ============  =========================================
    ``None``        ``nao_sei``   ainda não procurei (a primeira meia volta)
    ``""``          ``off``       procurei e NÃO ACHEI nesta máquina
    um caminho      ``nao_sei``   achei AQUI, e ainda não sei olhar dentro
    ==============  ============  =========================================

    O SELO ``off`` ESTAVA MORTO ATÉ HOJE. `SELOS["off"] = "NÃO ACHEI"` existia
    no desenho desde que ele nasceu e NENHUM caminho o produzia — os seis
    cartões saíam `ok`, `warn` ou `nao_sei`. Ele era a palavra que faltava para
    a tela poder dizer o que o produto mediu.

    O BOTÃO FICA NOS TRÊS ESTADOS — decisão dela, 02/09/2026, e ela DESFAZ uma
    mudança que ninguém tinha submetido a ela. O estado `off` nasceu (na tarde
    de 02/09) com `acoes=()`, pelo argumento de que "Abrir o lançador" sobre um
    lançador ausente seria botão que finge. O argumento tem mérito e **não é
    desta frente decidi-lo**: o desenho que ela aprovou tem o botão nos CINCO
    cartões, e a tela dela não pode perder um botão por conta de um raciocínio
    que ela não viu. Se ele deve sumir quando o lançador não está aqui, quem
    diz é ela — está em `espera_a_palavra_dela`, junto com as três frases.

    O BOTÃO GANHOU ENDEREÇO NOS SEIS — 03/09/2026, e a linha que estava aqui
    ("ele continua sem dono, `SEM_DONO['abrir-lancador']`") caducou com a
    decisão 17 dela. **O produto só sabe abrir a Steam**
    (`steam_launch_options.reopen_steam`), e nos outros cinco o gesto RECUSA
    dizendo — que é o contrário de fingir, e é melhor que o silêncio que havia:
    um botão sem `data-gesto` não chega ao Python, o clique some, e quem clica
    conclui que funcionou. Ver `a07_lancadores.abrir_lancador`.
    """
    abrir = (Acao("Abrir o lançador", "", ABRIR, item.chave),)
    # «LOCALIZAR ESTE LANÇADOR» É O BOTÃO DO ESTADO NÃO LOCALIZADO — 08/09/2026,
    # palavra dela. Ele NÃO abre nada: ele registra onde o lançador está. A
    # razão inteira, e a razão de ele ser uma FUNÇÃO e não uma linha aqui, está
    # em :func:`acao_de_localizar` — foi por ser linha que ele faltou na Steam.
    localizar = (acao_de_localizar(item.chave),)
    # E O TIRAR, SÓ ONDE HÁ O QUE TIRAR: o cartão que ELA ensinou. Nos de
    # fábrica que ela nunca tocou não há declaração a esquecer, e um botão que
    # não tem o que fazer é o botão que finge.
    tirar = (acao_de_tirar(item.chave),) if item.declarado else ()
    if onde is None:
        return Lancador(chave=item.chave, nome=item.nome, selo="nao_sei",
                        jogos="—", diz=DIZ_SEM_FONTE, acoes=abrir + tirar)
    if not onde:
        return Lancador(chave=item.chave, nome=item.nome, selo="off",
                        jogos="—", diz=DIZ_NAO_ACHEI,
                        acoes=localizar + tirar)
    #: **O CENSO ENTRA AQUI — LANCADORES-ZERO-01 §5, 09/09/2026.** Era
    #: `selo="nao_sei", jogos="—"` para todo lançador ACHADO, e é o que ela
    #: viu. Agora o selo diz `LOCALIZADO` (está aqui) e a linha de baixo diz o
    #: que a biblioteca tem — ou o que fazer para ela existir.
    #:
    #: **A LEITURA NÃO ACONTECE AQUI, e a linha que dizia o contrário caducou
    #: no mesmo dia:** ela chamava `_censo.biblioteca_do_cartao` e
    #: `resposta_do_flatpak` dentro da PINTURA, dez vezes por segundo. Quem lê é
    #: :func:`medir_no_disco`, na vigia; o que chega aqui é a :class:`DoDisco`,
    #: já respondida — com o custo medido escrito nela.
    resumo = do_disco.resumo(item.chave)
    #: **O «CONSERTAR» SAIU DAQUI — LANCADOR-LOCALIZAR-01, 10/09/2026.** Ele
    #: nascera pendurado no estado POSITIVO: selo `LOCALIZADO`, moldura `chega`
    #: — a MESMA do `ok`/CHEGAM da Steam — e a frase do corpo terminando em *"um
    #: jogo aberto por aqui entra pelo mesmo caminho de qualquer outro"*. Nada
    #: no cartão declarava defeito, e embaixo disso o produto oferecia
    #: *consertar*. O contraste que prova é o cartão da Steam: lá o mesmo verbo
    #: tem antecedente — selo `NÃO CHEGAM`, moldura `impede`, e a frase logo
    #: acima do botão nomeando o jogo que perdeu o atalho.
    #:
    #: **O «LOCALIZAR» ENTRA NO LUGAR, e ele não é botão novo** — é o
    #: :func:`acao_de_localizar` que o estado `off` já usava. O que mudou é o
    #: ESTADO em que ele aparece: até hoje só o cartão NÃO LOCALIZADO o tinha,
    #: e os seis cartões dela estão localizados — o botão que ela pediu *"no
    #: Máximo"* estava no produto e não alcançava um cartão sequer dela.
    #:
    #: **ELE VEM DEPOIS DO «ABRIR», e a ordem é o que cada um responde:** o
    #: cartão está localizado, então o ato normal é abrir; localizar de novo é o
    #: ato CORRETIVO — *"o que ele achou não é o que eu quero"* —, e ato
    #: corretivo não disputa a primeira posição com o ato normal. É a mesma
    #: leitura de cima para baixo que fez o selo e o botão falarem a mesma
    #: palavra em :data:`ADICIONAR_ROTULO`.
    #:
    #: **E ISSO FECHA UM BECO NA TELA:** a recusa do botão global
    #: (`a07_lancadores._recusa_de_quem_ja_tem_cartao`) dizia, para o cartão já
    #: achado, *"hoje o cartão não tem por onde trocar"* — o produto confessando
    #: dívida nossa, que a decisão dela de 07/09 proíbe. Com o «Localizar» aqui,
    #: o buraco some e a frase perde a razão de existir.
    #: **O RESUMO VAI PARA A LINHA `jogos`, e não para o corpo** — §5.2 da
    #: sprint: *"a linha de baixo diz «37 jogos na biblioteca · 0 instalados»"*.
    #: É o mesmo lugar em que a Steam imprime *"23 jogos instalados"*, e ele é
    #: uma linha própria no cartão.
    #:
    #: **MEDIDO NA TELA VIVA, 09/09/2026:** com o resumo colado na frente do
    #: `diz`, o corpo do cartão passou a estourar a caixa nas colunas da
    #: direita — o caminho do `.desktop` já é longo e não quebra. Fotografado
    #: antes de a linha existir.
    return Lancador(
        chave=item.chave, nome=item.nome, selo="localizado",
        jogos=resumo or "—",
        diz=DIZ_ACHEI,
        acoes=abrir + localizar + tirar, presente=True)


def cartoes(lida: Leitura | None) -> list[Lancador]:
    """Os cartões: o que tem censo, e os que só têm presença.

    O NÚMERO SAIU DAQUI EM 08/09/2026, e a razão continua valendo depois de a
    conta voltar ao que era: são os SEIS de fábrica **mais o que ELA declarou**,
    e o segundo grupo só existe na máquina dela — a página publicada nasce com
    os seis, e os declarados chegam pela troca da grade inteira (`_pintura`, no
    pacote). Cravar um número aqui faria a régua reprovar a máquina dela.

    A EPIC PASSOU POR AQUI E SAIU no mesmo dia, por decisão dela — a razão
    inteira está em :data:`SEM_FONTE`.
    """
    onde_estao = dict(lida.onde_estao) if lida is not None else {}
    #: **A PINTURA NÃO ABRE ARQUIVO** — 09/09/2026. Aqui morava a varredura das
    #: caixas do Flatpak, e dentro de `cartao_sem_censo` a biblioteca de cada
    #: lançador e a pergunta da estrada: **6,4 ms de mediana por tique**, dez
    #: vezes por segundo, num orçamento de 100 ms para a janela inteira. A
    #: resposta chega pronta pela `Leitura`, medida na vigia — ver
    #: :class:`DoDisco`.
    do_disco = lida.do_disco if lida is not None else SEM_DISCO
    fora = [cartao_da_steam(lida)]
    for item in procurados(lida.declarados if lida is not None else ()):
        # A STEAM JÁ SAIU ACIMA, com o censo dela. Ela está em `procurados`
        # porque a PRESENÇA dela se mede como a dos outros — mas o cartão é
        # outro, e desenhá-la duas vezes daria dois `data-lancador="steam"`.
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

        LIA O SELO, E O SELO É OUTRA PERGUNTA. Até 02/09 esta conta somava
        `ok` e `warn` — o que respondia *"em quantos lançadores eu sei dizer se
        os controles chegam?"*, e não *"quantos lançadores estão aqui?"*, que é
        o que a palavra **encontrados** promete a quem lê a tela. Enquanto o
        produto não olhava a presença, as duas contas davam o mesmo número e a
        diferença ficou escondida; assim que ele passou a olhar, um lançador
        instalado cujo interior ele não lê passaria a ser "não encontrado" com
        o cartão dizendo *"achei este lançador aqui"*, na mesma tela.

        Agora ela soma `presente`, que é a resposta da pergunta que o rótulo faz.
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
    "A_STEAM",
    "CLASSE_DA_GRADE",
    "COPIAR",
    "COPIAR_ROTULO",
    "DESLIGAR_STEAM_INPUT",
    "DESLIGAR_STEAM_INPUT_ROTULO",
    "DIZ_ACHEI",
    "DIZ_NAO_ACHEI",
    "DIZ_SEM_FONTE",
    "EMBUTIDOS",
    "JOGO_NAO_FUNCIONA",
    "JOGO_NAO_FUNCIONA_ROTULO",
    "MOLDURA",
    "NOVO_ALVO",
    "NOVO_PARA_O_CARTAO",
    "NOVO_PARA_QUEM",
    "NOVO_ROTULO",
    "NOVO_SEM_ALVO",
    "PROCURAR_O_ARQUIVO",
    "PROCURAR_O_ARQUIVO_ROTULO",
    "QUANTOS",
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
    "TUDO_PRONTO",
    "TUDO_PRONTO_ROTULO",
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
    "carimbo_da_steam",
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
    "quantos_html",
    "resposta_do_flatpak",
    "selo_html",
    "steam_input_html",
    "tela_do_registro_html",
    "um_cartao",
    "valores_do_cartao",
]
