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

**Este módulo não importa NADA do produto.** É desenho puro: entra dado, sai
marcação. Ele é importado pelo gerador (que roda como script solto) e pelo
pacote (que roda dentro da janela), e uma dependência aqui atravessaria para os
dois.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

#: O selo é o resumo de UMA palavra do corpo do cartão.
#:
#: `nao_sei` NASCEU DA MEDIÇÃO, e não do desenho: o produto tem `zero` função
#: que examine Heroic, Lutris, RetroArch, Dolphin ou mGBA — as cinco só aparecem
#: em COMENTÁRIO (`daemon/subsystems/hotkey.py:56`, `daemon/lifecycle.py:2271`,
#: `profiles/schema.py:1336`). Sem este selo, o cartão do Heroic teria de
#: escolher entre `CHEGAM` e `NÃO CHEGAM`, e as duas seriam afirmação sobre um
#: lançador que o produto nunca olhou. **"Não sei" é resposta; palpite não é.**
SELOS = {
    "ok": "CHEGAM",
    "warn": "NÃO CHEGAM",
    "off": "NÃO ACHEI",
    "nao_sei": "NÃO SEI",
}

#: A classe da MOLDURA do cartão, por selo. `nao_sei` divide a moldura apagada
#: com `off` de propósito: as duas dizem "não há o que agir aqui", e um terceiro
#: tom só acrescentaria uma cor para ela decodificar.
MOLDURA = {"ok": "chega", "warn": "impede", "off": "ausente", "nao_sei": "ausente"}


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


def _e(txt: object) -> str:
    """Escapa para HTML. O nome do jogo vem do DISCO dela, nunca daqui.

    Um `appmanifest` com `&` ou `<` no nome quebraria a marcação do cartão, e um
    nome de jogo é conteúdo de terceiro — a mesma razão pela qual
    `gui/aba_conexoes` escapa o rótulo do aparelho antes de o pôr na tela.
    """
    return html.escape(str(txt if txt is not None else ""), quote=True)


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
    endereco = f' data-gesto="{_e(a.gesto)}"' if a.gesto else ""
    valor = f' data-v="{_e(a.v)}"' if a.v else ""
    return f'<button class="{classe}"{endereco}{valor}>{_e(a.rotulo)}</button>'


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
    """
    botoes = "\n".join(f"          {acao_html(a)}" for a in lanc.acoes)
    carimbo = carimbo_html(lanc.carimbo)
    return f"{botoes}\n          {carimbo}" if carimbo else botoes


def um_cartao(lanc: Lancador) -> str:
    """O cartão inteiro, com os endereços que o pacote pinta.

    QUATRO ENDEREÇOS POR CARTÃO, e o quinto só onde há lista. Todos com o prefixo
    da `chave` porque a página tem seis cartões e um `data-campo="selo"` sozinho
    seria pintado nos seis com o mesmo valor — o defeito que a distribuição de
    lista do piloto faz de propósito, e que aqui seria acidente.
    """
    k = _e(lanc.chave)
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
        <div class="acoes" data-campo="{k}-acoes" data-hef-alvo="html">
{acoes_html(lanc)}
        </div>{lista}
      </div>'''


def cartoes_html(lancadores: list[Lancador]) -> str:
    """A grade inteira. Usada pelo gerador; o pacote pinta campo a campo."""
    return "\n".join(um_cartao(x) for x in lancadores)


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
            f'<button class="btn mini" data-gesto="{_e(j.gesto)}" '
            f'data-v="{_e(j.appid)}">{_e(j.botao)}</button>'
            if j.gesto else ""
        )
        linhas.append(
            f'<div class="lanc-jogo"><span class="lanc-jogo-nome">{_e(j.rotulo)}</span>'
            f'<span class="lanc-jogo-porque">{_e(j.porque)}</span>{botao}</div>'
        )
    return "".join(linhas)


def conta_html(achados: int, impedidos: int) -> str:
    """A contagem do quadro: `N encontrados · M com impedimento`.

    ELA JÁ ERA DERIVADA no gerador (a aba dizia "6 encontrados" contando o
    cartão que ela mesma carimba `NÃO ACHEI`), e continua sendo — o que muda é
    de ONDE: da lista de cartões que o produto montou, e não da que ele digitou.
    """
    return (f'{_plural(achados, "encontrado", "encontrados")} '
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

#: OS LANÇADORES QUE O PRODUTO NÃO OLHA. A lista é dado, e não `if`: no dia em
#: que alguém escrever o censo do Heroic, ele SAI daqui e ganha cartão próprio.
#:
#: A PROVA DE QUE NENHUM É OLHADO, medida em 02/09/2026:
#:     grep -rniE "heroic|lutris|retroarch|dolphin|mgba" src --include="*.py"
#: devolve CINCO linhas, e as cinco são COMENTÁRIO
#: (`daemon/subsystems/hotkey.py:56`, `daemon/lifecycle.py:2271`,
#:  `daemon/subsystems/game_signal.py:97`, `daemon/lifecycle.py:4169`,
#:  `profiles/schema.py:1336`). Zero função, zero chamada.
SEM_FONTE: tuple[tuple[str, str], ...] = (
    ("heroic", "Heroic (Epic · GOG)"),
    ("lutris", "Lutris"),
    ("flatpak", "Flatpak"),
    ("retroarch", "RetroArch"),
    ("emuladores", "Dolphin · mGBA"),
)

#: A frase dos cinco. Ela diz as TRÊS coisas que quem lê precisa: que o produto
#: não olhou, que o perfil casa por processo e janela (logo um jogo aberto de lá
#: pode funcionar), e o que falta para o cartão virar medição.
DIZ_SEM_FONTE = (
    "<b>Ainda não sei olhar este lançador.</b> O Hefesto casa o perfil pelo "
    "nome do processo e pela janela, então um jogo aberto por aqui pode "
    "funcionar — o que falta é o produto <i>medir</i>, e nenhuma linha dele "
    "olha para cá hoje."
)

#: O que o cartão da Steam mostra enquanto a primeira leitura não voltou.
#: **Nunca um número** — um número que ainda não foi lido é um número inventado.
AINDA_LENDO = "…"

#: A chave do único cartão com fonte.
STEAM = "steam"


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
    #: quantos jogos estão INSTALADOS — o vdf guarda linha de jogo desinstalado.
    instalados: int = 0
    #: a frase da sentinela, que já nomeia o jogo e já diz o que vai acontecer.
    frase: str = ""
    erros: tuple[str, ...] = ()


def _plural(n: int, um: str, muitos: str) -> str:
    return f"{n} {um if n == 1 else muitos}"


def lista_de_jogos(lida: Leitura) -> str:
    """As linhas dentro do cartão da Steam: quem falta, e quem ELA tirou.

    OS INTOCÁVEIS APARECEM SEM BOTÃO, de propósito: o produto não os repõe (o
    `apply_wrapper_vdf_text` os pula por construção) e "tirar daqui" um jogo que
    já está fora do reparo não mudaria nada — um botão que não muda nada é o que
    esta casa chama de botão que finge.
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
    return linhas_de_jogos(itens)


def cartao_da_steam(lida: Leitura | None) -> Lancador:
    """O ÚNICO cartão com fonte, e cada palavra dele sai de uma medição.

    O SELO SEGUE `reparaveis`, e não a soma dos faltantes: um jogo com a lista
    de IGNORE estendida à mão está sem o wrapper e **não deve ser tocado** —
    remover só o trecho do Hefesto deixaria um fragmento-comando que impede o
    jogo de abrir. Contá-lo como "não chega" acenderia um `Consertar` que não
    conserta aquele jogo.
    """
    # A FILEIRA É A QUE ELA APROVOU, botão por botão: o cartão `CHEGAM` do
    # desenho tem `Abrir o lançador` + `Criar perfil para um jogo`, e o
    # `NÃO CHEGAM` tem `Consertar` + `Ver o que impede` + `Abrir o lançador`.
    # NÃO acrescentei um `Procurar de novo` aqui: ele já está no topo do quadro,
    # e um segundo botão com o mesmo texto na mesma tela é a quebra de "mesma
    # família, mesma coisa" que esta aba já pagou uma vez (o `.lanc .btn` que
    # encolhia). A exceção é o cartão em ERRO, o único estado em que ele
    # responde uma pergunta que o cartão fez.
    abrir = Acao("Abrir o lançador", "", "", "")
    criar = Acao("Criar perfil para um jogo", "", "", "")
    if lida is None:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos=AINDA_LENDO,
            diz="Estou lendo a sua biblioteca da Steam…",
            acoes=(abrir, criar), tem_lista=True)
    if lida.erros:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos="—",
            diz=("<b>Não consegui ler a biblioteca da Steam</b> — "
                 f"{_e(lida.erros[0])}. Nada foi alterado."),
            acoes=(Acao("Procurar de novo", "", "procurar", STEAM), abrir, criar),
            tem_lista=True)

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
        diz = ("Os controles chegam. O atalho de inicialização está no lugar em "
               f"{_plural(len(lida.com_wrapper), 'jogo', 'jogos')} da sua "
               "biblioteca.")
        acoes = (abrir, criar)
        selo = "ok"

    # O CARIMBO NÃO É SÓ BOA NOTÍCIA. Ele é o único lugar que sobra no cartão, e
    # calar sobre um jogo que o produto DECIDIU não tocar é como ele fica sem o
    # atalho para sempre sem ninguém saber.
    carimbo = (f"{_plural(len(lida.intocaveis), 'jogo', 'jogos')} com a linha "
               "intocável — só reparo manual") if lida.intocaveis else ""
    return Lancador(
        chave=STEAM, nome="Steam", selo=selo,
        jogos=_plural(lida.instalados, "jogo instalado", "jogos instalados"),
        diz=diz, acoes=acoes, carimbo=carimbo,
        fora=lista_de_jogos(lida), tem_lista=True)


def cartoes(lida: Leitura | None) -> list[Lancador]:
    """Os seis cartões: o que tem fonte, e os cinco que dizem que não têm."""
    fora = [cartao_da_steam(lida)]
    for chave, nome in SEM_FONTE:
        fora.append(Lancador(chave=chave, nome=nome, selo="nao_sei", jogos="—",
                             diz=DIZ_SEM_FONTE,
                             acoes=(Acao("Abrir o lançador", "", "", ""),)))
    return fora


@dataclass
class Quadro:
    """Tudo o que a aba mostra: os cartões e a contagem do topo."""

    lancadores: list[Lancador] = field(default_factory=list)

    @property
    def achados(self) -> int:
        """Quantos lançadores o produto ACHOU nesta máquina.

        `off` (não achei) e `nao_sei` (não sei olhar) ficam de fora pelo mesmo
        motivo: nos dois casos a aba não pode afirmar que o lançador está aqui.
        """
        return sum(1 for x in self.lancadores if x.selo in ("ok", "warn"))

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
    "AINDA_LENDO",
    "DIZ_SEM_FONTE",
    "MOLDURA",
    "SELOS",
    "SEM_FONTE",
    "STEAM",
    "SUFIXOS",
    "SUFIXO_DA_LISTA",
    "Acao",  # (noqa-acento) nome de CLASSE — identificador Python não leva acento
    "JogoNaLista",
    "Lancador",
    "Leitura",
    "Quadro",
    "acao_html",
    "acoes_html",
    "carimbo_html",
    "cartao_da_steam",
    "cartoes",
    "cartoes_html",
    "conta_html",
    "linhas_de_jogos",
    "lista_de_jogos",
    "selo_html",
    "um_cartao",
    "valores_do_cartao",
]
