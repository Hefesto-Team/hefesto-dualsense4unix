"""O que a aba **Jogar** pode dizer hoje — e, com o mesmo peso, o que não pode.

29/08/2026, refeito em 31/08. A aba Jogar é a que ABRE o aplicativo, e no
desenho aprovado (``src/hefesto_dualsense4unix/interface/paginas/01-jogar.html``) ela tem quatro
grupos de valor: o
**interruptor do Hefesto** com os cinco modos que ele abre, os **cartões da
mesa** e a coluna **Atenção**. Desde 31/08 o produto responde pelos quatro — o
que sobra em aberto está no fim deste cabeçalho, e é pouco.

**A REGRA QUE ESTE ARQUIVO EXISTE PARA CUMPRIR:** um número plausível e falso é
pior que um traço honesto, porque ela confia nele. Toda linha de tela desta aba
que não tem leitor no produto sai daqui com :data:`SEM_LEITOR` no lugar do
valor, e o motivo junto — nunca apagada, nunca inventada.

O que NÃO mora aqui, de propósito
---------------------------------

* **A montagem da mesa** (um item por controle, com cor, transporte e número do
  jogador) é de ``src/hefesto_dualsense4unix/interface/mesa_viva.mesa_do_estado``, que já é
  o dono dela para a aba Controles e para a fita. Reescrevê-la aqui criaria o
  segundo dono do mesmo valor — o defeito que a fita viva de 27/08 pagou.
* **A janela e as duas pontes** são de
  :mod:`hefesto_dualsense4unix.gui.ponte_da_tela`, e são de todas as dez abas.
* **A pintura** é do piloto: quem escreve no DOM escreve por TIPO, e isso é
  código de tela.

Os três buracos de 29/08/2026 — e o que os fechou em 31/08/2026
---------------------------------------------------------------

Os três eram perguntas para ELA, e ela as respondeu de uma vez ao redesenhar o
**Modo de conexão** em 31/08/2026, depois de perguntar *"qual a diferença de
nativo pra dualsense?"*. A forma aprovada é o interruptor **HEFESTO
Ligado/Desligado**, com os cinco modos abrindo do lado Ligado.

1. **O quarto botão de modo, "Desligado".** Ele não tinha leitor:
   :func:`mode_of_state
   <hefesto_dualsense4unix.app.actions.mode_transition.mode_of_state>` é o
   **ponto único de leitura do modo vivo** nesta casa e devolve **três**
   valores — ``desktop``, ``gamepad``, ``native``. Nunca um quarto.
   **FECHADO SEM CONSTRUIR NADA:** o botão saiu da fileira e virou a *posição*
   Desligado do interruptor, que **é** o ``MODE_NATIVE`` — e esse lê (o mesmo
   ``mode_of_state``) e escreve (``apply_mode('native')``). A lápide, com a
   data, é :data:`MODO_DESLIGADO`. Parar o Hefesto INTEIRO continua sendo
   "Parar o serviço", na aba Sistema — e a palavra é escolha dela de 31/08:
   "parar" é o que o `systemctl stop` faz e é o par de "Ligado"; "encerrar"
   sugeria fim definitivo, e o serviço volta no próximo login.

2. **A escada tinha cinco chips no desenho e quatro degraus no código**, e um
   degrau REAL — ``Ponte(gamepad, xbox)``, o segundo que o produto tenta —
   nunca tinha chegado à tela. **FECHADO:** o Xbox entrou na fileira e o Nativo
   virou o interruptor, e :func:`degraus_sem_chip` devolve ``()`` **pela
   primeira vez**.

3. **O "Automático" da escada não tinha leitor nem escritor.** **FECHADO por
   palavra dela**, 31/08: *"na aba jogar o Botão Automático não existe"*. O
   MECANISMO ficou inteiro — *tentar em ordem e parar quando acerta* é o que
   ``integrations/ponte_tentativa`` faz sozinho, sempre; o que saiu foi o botão
   que fingia comandá-lo.

O QUE CONTINUA EM ABERTO, e é honesto dizer
-------------------------------------------

* **Point And Click não tem dono nenhum** — nem degrau da ``ESCADA``, nem modo
  do ``mode_transition``. É o único que :func:`chips_sem_dono` devolve, e ele
  está na tela por ordem dela (*manter*), marcado, dizendo isso.
* **Navegação tem escritor e não é degrau** — ``apply_mode('desktop')``
  funciona hoje; o que não existe é o **PS + R3** parar nela. Por isso ela é o
  único item de :func:`chips_sem_degrau`, e por isso :func:`chips_sem_degrau`
  **não serve** para pintar "sem dono".
* **Fixar um degrau pela tela** continua sem método de IPC: clicar em Sony
  DualSense, Xbox ou Steam Input não muda nada no daemon. Quem muda é o PS+R3.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    mode_of_state,
    plan_mode_transition,
)
from hefesto_dualsense4unix.integrations import ponte_escada

#: O que se escreve no lugar de um valor que o produto não tem como responder.
#: É um traço, e não um zero: zero é uma medida, e esta tela não mediu nada.
SEM_LEITOR = "—"

#: O TRAÇO DO CÍRCULO DA ESCADA, para quem não é degrau. **Não é o
#: :data:`SEM_LEITOR`**, e a diferença é de caractere: o desenho escreve um EN
#: DASH (``U+2013``) dentro do ``<i class="tr">``, e o ``SEM_LEITOR`` é um EM
#: DASH (``U+2014``). Escrever o outro aqui faria a tela e o produto dizerem
#: coisas parecidas com bytes diferentes — que é como uma régua de comparação
#: nasce cega.
#: (escrito com o nome do caractere, e não com ele: `ruff` reprova um EN DASH
#: solto como ambíguo — RUF001 — e tem razão, porque ele e o hífen são a mesma
#: mancha na tela de quem revisa.)
SEM_ALGARISMO = "\N{EN DASH}"

# ---------------------------------------------------------------------------
# LÁPIDE — o quarto botão de modo, "Desligado" (29/08/2026 → 31/08/2026)
# ---------------------------------------------------------------------------
# ELE EXISTIU, E O QUE O MATOU FOI UMA DECISÃO DELA, não um conserto.
#
# De 29/08 a 31/08 a fileira tinha QUATRO botões, e o quarto — `desligado` — era
# o único sem leitor no produto: `mode_of_state` devolve três valores e nunca um
# quarto, e chamar de "Desligado" o `state_full.paused` (que é o PS+Options, com
# texto próprio em `home_actions.texto_da_pausa`) seria a tela inventando um
# estado. Estava aberto como MIGRA-JOGAR-06, e a pergunta era dela.
#
# 31/08/2026, ela redesenhou o Modo de conexão e a resposta veio pela forma:
# **Desligado = Modo Nativo**, *"o DualSense da forma como veio ao mundo"*. O
# botão órfão sumiu do desenho e a posição Desligado do interruptor passou a
# endereçar `MODE_NATIVE` (`src/hefesto_dualsense4unix/interface/paginas/01-jogar.html`,
# `data-modo="native"`), que TEM
# leitor e TEM escritor. A MIGRA-JOGAR-06 fecha sem uma linha de produto nova.
#
# A CONSTANTE FICA porque ela é a resposta a uma pergunta que volta: *"e o botão
# Desligado, sumiu por quê?"*. Ela não é usada por nada — `escritor_do_modo` e
# `porque_nao_aplica` respondem por ela pelo caminho do endereço desconhecido,
# que é o mesmo de qualquer DOM adulterado.
MODO_DESLIGADO = "desligado"


class Modo(NamedTuple):
    """Um botão da fileira "O que o controle faz agora"."""

    #: o ``data-modo`` do botão na página
    chave: str
    #: o rótulo aprovado por ela, no desenho
    rotulo: str
    #: o valor que ``mode_of_state`` devolve para este botão — ``None`` quando
    #: **nenhum** valor dela corresponde a ele. Desde 31/08/2026 os três têm
    #: leitor, e o campo fica: ele é o que impede a próxima linha de tela de
    #: nascer sem dono e ninguém notar.
    lido_como: str | None
    #: por que este botão não tem leitor (vazio quando tem)
    porque_nao: str = ""

    @property
    def tem_leitor(self) -> bool:
        return self.lido_como is not None


#: A FILEIRA DE MODOS, NA ORDEM DO DESENHO — e desde 31/08/2026 são **TRÊS**,
#: que é exatamente o que ``mode_transition.MODES`` tem. Pela primeira vez os
#: dois conjuntos são o mesmo conjunto: todo endereço da tela tem leitor E
#: escritor, e nenhum modo do produto ficou sem lugar na tela.
#:
#: Onde cada um mora no desenho (``src/hefesto_dualsense4unix/interface/paginas/01-jogar.html``):
#:
#:   * ``gamepad`` — a posição **Ligado** do interruptor;
#:   * ``native``  — a posição **Desligado** ("Modo Nativo");
#:   * ``desktop`` — o chip **Navegação**, dentro do lado Ligado. Ele mora ali,
#:     e não do lado desligado, porque **quem emula teclado e mouse é o próprio
#:     Hefesto**: com ele fora do meio não existe teclado nem mouse.
#:
#: Os rótulos NÃO são digitados aqui: saem de
#: ``home_actions.ITENS_DE_MODO``/``_MODE_ITEMS``, que é o léxico desta casa
#: (``app/actions/contrato_da_mascara.py`` o republica, e o
#: ``app/widgets/painel_no_jogo.py`` o consome). Digitá-los seria a segunda
#: cópia da palavra dela. **Eles não são as palavras do desenho** ("Ligado",
#: "Desligado", "Navegação"): estas são a tela, e são do gerador do mockup.
_ROTULO_DO_MODO: dict[str, str] = dict(home_actions._MODE_ITEMS)

MODOS_DA_TELA: tuple[Modo, ...] = (
    Modo(MODE_GAMEPAD, _ROTULO_DO_MODO[MODE_GAMEPAD], MODE_GAMEPAD),
    Modo(MODE_NATIVE, _ROTULO_DO_MODO[MODE_NATIVE], MODE_NATIVE),
    Modo(MODE_DESKTOP, _ROTULO_DO_MODO[MODE_DESKTOP], MODE_DESKTOP),
)

#: OS DOIS MODOS QUE SÃO O HEFESTO **LIGADO**. Ele está no meio nos dois: no
#: ``gamepad`` entregando um controle ao jogo, no ``desktop`` entregando teclado
#: e mouse ao computador. Só o ``native`` é ele fora do meio.
MODOS_LIGADOS: tuple[str, ...] = (MODE_GAMEPAD, MODE_DESKTOP)


def modo_vivo(state: dict[str, Any] | None) -> str | None:
    """Qual botão da fileira está aceso — ``None`` com o daemon calado.

    Delega, sem uma linha de regra própria. O valor devolvido é a ``chave`` de
    um :class:`Modo` de :data:`MODOS_DA_TELA`, ou ``None``.
    """
    return mode_of_state(state)


def ligado_por_modo(chave: str | None) -> bool | None:
    """O interruptor, a partir de uma chave de modo — ``None`` quando não se sabe.

    Existe separada de :func:`hefesto_ligado` por um motivo de tela: a aba viva
    tem um **eco** (o clique dela valendo até o daemon alcançar), e o
    interruptor precisa responder pela mesma regra nos dois casos. Uma segunda
    lista de "quais modos são Ligado" escrita em JavaScript seria o segundo dono
    da regra, na linguagem em que ninguém a mede.
    """
    if not chave:
        return None
    return chave in MODOS_LIGADOS


def hefesto_ligado(state: dict[str, Any] | None) -> bool | None:
    """A POSIÇÃO DO INTERRUPTOR agora: ``True`` Ligado · ``False`` Desligado ·
    ``None`` o daemon não respondeu.

    **POR QUE ISTO É DERIVADO, e não a comparação de um botão só.** A pintura
    viva acende ``[data-modo]`` comparando a chave com o modo do daemon, uma a
    uma — e o Hefesto **Ligado** é ``gamepad`` *ou* ``desktop``. Sem esta
    leitura, com o modo vivo em ``desktop`` (a Navegação) o interruptor fica
    **apagado dos dois lados**: a tela não estaria mentindo, estaria muda — e
    mudo é pior, porque parece defeito.

    Foi o que o desenho de 31/08 encomendou ao código com todas as letras, e é
    o estado em que a máquina dela estava quando esta função nasceu:
    ``modo_vivo`` respondendo ``desktop``, com o gamepad desligado por gesto
    dela.
    """
    return ligado_por_modo(modo_vivo(state))


# ---------------------------------------------------------------------------
# O INTERRUPTOR — do clique dela até o disco
# ---------------------------------------------------------------------------
# POR QUE ESTE BLOCO NASCEU (31/08/2026). Pedido dela, literal: *"Não sei se o
# botão de ativar ele na interface tá funcionando viu. não sei se segue
# desativado."* e *"eu quero é que ele funcione na interface e se lembre"*.
#
# MEDIDO na tela nova, antes de uma linha ser escrita: com o `./interface`
# aberto e a tira navegada até a aba Jogar, `[data-modo="gamepad"]` aparecia
# ACESO, `listeners=0` em TODOS os quatro botões, o clique sintético produziu
# ZERO gestos e o `gamepad_disabled.flag` não se moveu. A tela afirmava "Jogar
# pelo Hefesto" enquanto o `mode_of_state` do daemon dizia `desktop` — o F7
# desta casa (*estado velho como padrão*) na pergunta em que ela mais dói.
#
# O QUE FALTAVA NÃO ERA MÉTODO DE IPC. `gamepad.emulation.set` existe
# (`daemon/ipc_server.py:166`), persiste (`utils/session.save_gamepad_emulation`
# grava/apaga o `gamepad_disabled.flag`) e é respeitado depois de reiniciar
# (`gamepad_multiplos_controles_adiado estado=ignorado_gesto_dela`). Faltava a
# metade ESCRITORA desta tela: o módulo dizia qual botão acende e nunca disse
# quem aplica o clique.
#
# Este bloco NÃO reimplementa a sequência: ela continua sendo de
# `mode_transition.plan_mode_transition`, que é o dono declarado desde o HARM-01.
# O que nasce aqui é (a) o mapa `botão → escritor`, que é o par honesto do
# `tem_leitor` já existente, e (b) a leitura do DISCO, que é a única fonte que
# responde "segue desativado?" com o daemon calado.

#: QUEM APLICA CADA BOTÃO DA FILEIRA, num lugar só — o par escritor do
#: :attr:`Modo.tem_leitor`. Ler e escrever são perguntas DIFERENTES, e o fato de
#: hoje os três coincidirem não as junta: o "Automático" da escada tinha leitor
#: nenhum e escritor nenhum, e a **Navegação** é o caso do meio ao contrário —
#: ela tem escritor aqui (``apply_mode('desktop')``) e **não** é degrau da
#: ``ESCADA``, que é justamente o que faz :func:`chips_sem_degrau` ser a régua
#: errada para pintar "sem dono" (ver :func:`chips_sem_dono`).
ESCRITOR_DOS_MODOS: dict[str, str] = {
    MODE_DESKTOP: "`mode_transition.apply_mode('desktop')` — três IPCs em ordem "
    "(`native.mode.set` off, `gamepad.emulation.set` off, "
    "`mouse.emulation.restore`), todos com `origin='manual'`. O desligar do "
    "gamepad com origem manual é o que GRAVA o `gamepad_disabled.flag` "
    "(`utils/session.save_gamepad_emulation`), e é por isso que a escolha dela "
    "sobrevive a reiniciar o daemon e a máquina.",
    MODE_GAMEPAD: "`mode_transition.apply_mode('gamepad')` — sai do Modo Nativo "
    "e liga o gamepad virtual com `origin='manual'`. O ligar APAGA o "
    "`gamepad_disabled.flag`, que é o que devolve à automação o direito de "
    "ligar sozinha com dois controles na mesa.",
    MODE_NATIVE: "`mode_transition.apply_mode('native')` — `native.mode.set` "
    "com `origin='manual'`. Ele NÃO mexe no `gamepad_disabled.flag`: o opt-out "
    "do gamepad é outro eixo, e o daemon guarda os dois separados.",
}


def escritor_do_modo(chave: str) -> str:
    """Quem APLICA este botão, ou o porquê de ninguém aplicar.

    Nunca levanta ``KeyError``: uma chave que o gerador não escreve chega aqui
    quando alguém adultera o DOM (uma régua, por exemplo), e derrubar a tela
    dela para relatar um dono desconhecido é o pior dos dois males.
    """
    escritor = ESCRITOR_DOS_MODOS.get(chave)
    if escritor is not None:
        return escritor
    for modo in MODOS_DA_TELA:
        if modo.chave == chave:
            return (
                "NINGUÉM APLICA este botão. " + modo.porque_nao
                if modo.porque_nao
                else "NINGUÉM APLICA este botão, e o motivo não está declarado."
            )
    return (
        "SEM LINHA na fileira de modos — este gesto chegou de um endereço que o "
        "gerador não escreve. Nada foi aplicado."
    )


def porque_nao_aplica(chave: str) -> str:
    """Vazio quando o botão TEM escritor; o motivo, em português, quando não tem.

    É o texto do ``disabled`` na tela nova. Botão cinza sem explicação manda a
    pessoa procurar defeito onde não há; botão vivo que ninguém atende dispara
    trabalho que não acontece e a tela confirma. Os dois males têm a mesma cura.
    """
    if chave in ESCRITOR_DOS_MODOS:
        return ""
    for modo in MODOS_DA_TELA:
        if modo.chave == chave:
            return (
                f"O botão “{modo.rotulo}” ainda não tem quem o atenda no "
                "Hefesto. Ele está no desenho e a decisão é dela "
                "(MIGRA-JOGAR-06)."
            )
    return "Este botão não existe na fileira de modos."


def plano_do_modo(
    chave: str, mascara: str | None = None
) -> list[tuple[str, dict[str, Any]]] | None:
    """A sequência de IPC do clique — DELEGADA, sem uma linha de regra própria.

    ``None`` quando o botão não tem escritor (hoje, só o "Desligado"). Quem
    define o que cada modo É continua sendo
    :func:`~hefesto_dualsense4unix.app.actions.mode_transition.plan_mode_transition`;
    escrever a ordem das chamadas aqui criaria o segundo dono que o HARM-01
    enterrou.
    """
    if chave not in ESCRITOR_DOS_MODOS:
        return None
    return plan_mode_transition(chave, mascara)


class Lembranca(NamedTuple):
    """O que ELA DECIDIU sobre o gamepad virtual, lido do DISCO.

    É a metade que o daemon calado não responde. ``modo_vivo`` pergunta ao
    ``state_full``: com o daemon fora do ar ele devolve ``None``, e a tela
    ficaria sem ter o que dizer justamente na hora em que a pergunta dela — *"não
    sei se segue desativado"* — é mais aflita.
    """

    #: ``True`` deixou ligado · ``False`` desligou DE PROPÓSITO · ``None`` nunca
    #: decidiu. Os três são estados diferentes, e o do meio é o que a automação
    #: do daemon respeita (``gamepad_multiplos_controles_adiado``).
    ligado: bool | None
    #: a máscara gravada junto, quando ligado
    mascara: str | None
    #: a frase que responde, em português, "e agora, segue desativado?"
    frase: str


def modo_lembrado() -> Lembranca:
    """O opt-out persistido do gamepad virtual, com a frase da tela.

    Delega a :func:`~hefesto_dualsense4unix.utils.session.load_gamepad_preference`,
    que é o dono do arquivo — nenhum caminho de disco é escrito aqui. Ela já é
    à prova de I/O (erro vira "nunca decidiu"), e por isso esta função também é.

    **A lembrança responde por UM eixo só**, e isso está dito na frase: o
    arquivo guarda o gamepad virtual, não o Modo Nativo nem o mouse. Deduzir
    daqui qual dos outros modos está valendo seria a tela inventando um estado.
    """
    from hefesto_dualsense4unix.utils.session import load_gamepad_preference

    ligado, mascara = load_gamepad_preference()
    if ligado is True:
        marca = f" (máscara {mascara})" if mascara else ""
        return Lembranca(
            True,
            mascara,
            f"Está gravado como LIGADO{marca}: “Jogar pelo Hefesto” volta assim "
            "depois de reiniciar o Hefesto ou o computador.",
        )
    if ligado is False:
        return Lembranca(
            False,
            None,
            "Está gravado como DESLIGADO de propósito: “Jogar pelo Hefesto” "
            "continua desligado depois de reiniciar o Hefesto ou o computador, "
            "e o Hefesto não o religa sozinho nem com dois controles na mesa.",
        )
    return Lembranca(
        None,
        None,
        "Ninguém decidiu ainda: o Hefesto pode ligar “Jogar pelo Hefesto” "
        "sozinho quando vir dois controles na mesa.",
    )


# ---------------------------------------------------------------------------
# A escada — os cinco modos de dentro do Hefesto LIGADO
# ---------------------------------------------------------------------------
class Chip(NamedTuple):
    """Um chip da fileira "Modo", do lado Ligado do interruptor."""

    #: o ``data-degrau`` do chip na página
    chave: str
    #: o rótulo aprovado por ela
    rotulo: str
    #: a ponte que este chip NOMEIA — ``None`` quando ele não nomeia ponte
    #: nenhuma, e é o caso do "Point And Click"
    ponte: ponte_escada.Ponte | None
    #: o ``mode_transition`` que este chip aplica, quando aplica algum. Só a
    #: **Navegação** tem: ela não é degrau da escada e mesmo assim tem dono, e
    #: é este campo que separa "não é degrau" de "não tem dono".
    modo: str | None = None

    @property
    def indice(self) -> int:
        """Posição na ``ponte_escada.ESCADA``, ou ``-1`` se não é degrau."""
        if self.ponte is None:
            return -1
        return ponte_escada.indice_do_degrau(self.ponte)

    @property
    def algarismo(self) -> str:
        """O que iria no círculo — **derivado, nunca digitado**.

        **A TELA NÃO MOSTRA MAIS ESTE NÚMERO — 31/08/2026**, e a razão é o que
        esta property existia para evitar: os dois números divergiram. A aba
        escrevia ``③ Steam Input``; daqui sai **4**, porque o terceiro degrau da
        ``ESCADA`` é o Nativo, que a decisão dela do mesmo dia tirou da fileira
        para virar a posição DESLIGADO do interruptor. Havia três saídas —
        numerar ``1 · 2 · 4`` com o buraco, numerar pela posição na tela, ou
        tirar os números; **ela tirou**. A ordem passou a viver na dica de cada
        modo. Ver ``src/hefesto_dualsense4unix/interface/aba01.py``, o comentário do ``MODOS``.

        ELA FICA, e não é código morto por acaso: enquanto a ordem for uma
        afirmação do produto, este é o **único** lugar de onde um número pode
        sair. Se os algarismos voltarem, voltam daqui — digitá-los na tela é o
        que produziu a divergência que os matou.

        O algarismo é a ordem em que o produto TENTA, e o dono dessa ordem é a
        ``ponte_escada.ESCADA``. Digitá-lo criaria o mesmo número em dois
        lugares, e dois números iguais escritos à mão divergem no primeiro dia
        em que alguém mexe num deles.

        Quem não é degrau leva :data:`SEM_ALGARISMO`, nunca um número: um
        algarismo ali diria que o **PS + R3** para naquele modo, e ele não para.
        """
        indice = self.indice
        return SEM_ALGARISMO if indice < 0 else str(indice + 1)


#: OS CINCO MODOS DO LADO **LIGADO**, na ordem do desenho, com a ponte que cada
#: um nomeia. Os rótulos são dela (``src/hefesto_dualsense4unix/interface/paginas/01-jogar.html``);
#: a ponte é a
#: tradução para o vocabulário de ``integrations/ponte_escada``.
#:
#: **A tradução é declarada aqui e o ALGARISMO é calculado** — nunca digitado
#: (:attr:`Chip.algarismo`). Acrescentar ou tirar um degrau da ``ESCADA`` muda
#: esta tela sozinho, e :func:`degraus_sem_chip` denuncia quem ficar sem chip.
#:
#: O QUE MUDOU EM 31/08/2026, contra a fileira plana de quatro:
#:
#:   * o chip chamado **"Hefesto"** virou **Sony DualSense** — ele sempre foi
#:     ``Ponte(gamepad, dualsense)``, e era o nome do PRODUTO no lugar do nome
#:     da máscara, numa fileira em que os outros também são o Hefesto;
#:   * **Xbox** entrou: ``Ponte(gamepad, xbox)`` é o SEGUNDO degrau que o
#:     produto tenta, e nenhum chip o nomeava — era o que
#:     :func:`degraus_sem_chip` denunciava desde 29/08;
#:   * **"Sony (nativo)"** saiu: ele é a posição **Desligado** do interruptor
#:     (ver :data:`PONTES_DO_INTERRUPTOR`);
#:   * **"Teclado + Mouse"** virou **Navegação**, e ganhou o ``modo``:
#:     ``KIND_DESKTOP`` não é degrau da ``ESCADA``, mas ``apply_mode('desktop')``
#:     funciona hoje;
#:   * **Point And Click** nasceu por ordem dela, e é o único sem dono nenhum.
CHIPS_DA_ESCADA: tuple[Chip, ...] = (
    Chip(
        "dualsense",
        "Sony DualSense",
        ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, ponte_escada.MASCARA_DUALSENSE),
    ),
    Chip(
        "xbox",
        "Xbox",
        ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, ponte_escada.MASCARA_XBOX),
    ),
    Chip(
        "steam",
        "Steam Input",
        ponte_escada.Ponte(
            ponte_escada.KIND_GAMEPAD,
            ponte_escada.MASCARA_DUALSENSE,
            steam_input=True,
        ),
    ),
    # SEM PONTE E SEM MODO — o único da tela que não tem dono nenhum. Não é
    # degrau da `ESCADA` nem valor de `mode_transition.MODES`. Está aqui por
    # ordem dela, de 31/08 (*manter* o Point And Click), casada com a regra de
    # 30/08: botão sem dono no produto não vai para a tela COMO SE FUNCIONASSE.
    # As duas convivem de um jeito só, e é o que `chips_sem_dono` serve.
    Chip("pointclick", "Point And Click", None),
    # O CASO DO MEIO, E ELE É BOM: `KIND_DESKTOP` EXISTE como constante
    # (`ponte_escada.KIND_DESKTOP`) e é aceito por `ponte_do_perfil` e
    # `ponte_do_carimbo` — mas NÃO É DEGRAU: a `ESCADA` não tem uma linha com
    # ele, e `indice_do_degrau` devolve -1. O MODO, esse, tem dono e funciona
    # hoje. Por isso ela leva traço no algarismo e NÃO leva a marca de sem dono.
    Chip(
        "navegacao",
        "Navegação",
        ponte_escada.Ponte(ponte_escada.KIND_DESKTOP),
        modo=MODE_DESKTOP,
    ),
)

#: Compatibilidade de nome com o gerador do mockup, que chama a mesma coisa de
#: "degraus". São os chips do desenho, não os degraus do código — e a diferença
#: entre os dois é o assunto deste bloco.
DEGRAUS_DA_TELA = CHIPS_DA_ESCADA

#: AS PONTES QUE TÊM LUGAR NA TELA **FORA** DA FILEIRA. Hoje é uma só, e é a do
#: interruptor: ``Ponte(KIND_NATIVE)`` é a posição **Desligado**.
#:
#: Sem esta linha :func:`degraus_sem_chip` acusaria o Nativo de não ter lugar na
#: tela — e seria **acusação falsa**, do tipo mais caro: a régua reprovando a
#: melhora em vez do defeito. Ela pergunta "este degrau tem onde aparecer?", e a
#: resposta para o Nativo é sim; o que ele não tem é chip na fileira, que é
#: outra pergunta.
PONTES_DO_INTERRUPTOR: frozenset[ponte_escada.Ponte] = frozenset(
    {ponte_escada.Ponte(ponte_escada.KIND_NATIVE)}
)


def indice_do_chip(chip: Chip) -> int:
    """Posição do chip na ``ponte_escada.ESCADA``, ou ``-1`` se ele não é degrau.

    ``-1`` não é erro: é o valor honesto para o "Point And Click" (que não
    nomeia ponte nenhuma) e para a "Navegação" (que nomeia uma ponte que a
    escada não sobe).
    """
    return chip.indice


def chips_sem_degrau() -> tuple[Chip, ...]:
    """Os chips que nomeiam uma ponte que a ``ESCADA`` não tem.

    Hoje: só a **Navegação**. O que falta a ela é o **PS + R3** parar ali — a
    escada não sobe até o ``KIND_DESKTOP``.

    **ISTO NÃO É "SEM DONO", E CONFUNDIR OS DOIS PINTA A TELA ERRADA.** A
    Navegação tem escritor (``ESCRITOR_DOS_MODOS[desktop]`` →
    ``apply_mode('desktop')``) e funciona hoje; marcá-la como órfã seria a tela
    dizendo "não dá" sobre um botão que dá. Quem responde pela marca é
    :func:`chips_sem_dono`.
    """
    return tuple(c for c in CHIPS_DA_ESCADA if c.ponte is not None and c.indice < 0)


def chips_sem_dono() -> tuple[Chip, ...]:
    """Os chips que **ninguém atende**: nem degrau da ``ESCADA``, nem modo do
    produto.

    É a régua que a tela usa para marcar um chip como inerte, e ela é a
    conjunção de duas perguntas que :func:`chips_sem_degrau` sozinha não
    responde — a Navegação reprova a primeira e passa na segunda.

    Hoje devolve **um só**: o "Point And Click".
    """
    return tuple(
        c
        for c in CHIPS_DA_ESCADA
        if c.indice < 0 and (c.modo or "") not in ESCRITOR_DOS_MODOS
    )


def degraus_sem_chip() -> tuple[ponte_escada.Degrau, ...]:
    """Os degraus da ``ESCADA`` que a tela NÃO mostra em lugar nenhum — o código
    devendo à tela.

    Desde 31/08/2026 devolve ``()``, **pela primeira vez**. Os quatro degraus
    têm onde aparecer: três são chip da fileira e o Nativo é a posição Desligado
    do interruptor (:data:`PONTES_DO_INTERRUPTOR`).

    O que ela denunciava até 30/08, e o desenho de 31/08 pagou: o segundo
    degrau, ``gamepad`` com a máscara ``xbox`` — *"o piso mais largo que
    existe"*, diz o ``porque`` dele. A escada automática passava por ele e a
    tela não tinha onde mostrá-lo.
    """
    nomeadas = {c.ponte for c in CHIPS_DA_ESCADA if c.ponte is not None}
    nomeadas |= set(PONTES_DO_INTERRUPTOR)
    return tuple(d for d in ponte_escada.ESCADA if d.ponte not in nomeadas)


def degrau_vivo(
    state: dict[str, Any] | None,
    pontes: dict[str, Any] | None,
) -> str | None:
    """A ``chave`` do chip aceso, ou ``None`` — e ``None`` é o caso comum.

    A ÚNICA memória viva da escada é **por jogo**: o carimbo que
    ``integrations/prontuario_dos_jogos.pontes_confirmadas`` lê dos perfis do
    disco (``{appid: Ponte}``). Sem jogo aberto — ``state_full.jogo_steam.appid``
    ausente — não há o que acender, e acender um chip por padrão seria afirmar
    uma escolha que ninguém fez.

    **O Nativo não acende chip nenhum aqui, de propósito:** a ponte
    ``Ponte(KIND_NATIVE)`` carimbada num perfil é a posição *Desligado* do
    interruptor, e quem responde por ela é :func:`hefesto_ligado`. Procurá-la
    entre os chips devolve ``None``, que é a resposta certa — a fileira do lado
    Ligado não tem onde acendê-la.

    ``pontes`` entra por argumento de propósito: quem lê o disco dela é o
    chamador, e a régua entrega um dicionário próprio em vez de mexer nos
    perfis dela.
    """
    if not isinstance(state, dict) or not pontes:
        return None
    jogo = state.get("jogo_steam")
    appid = jogo.get("appid") if isinstance(jogo, dict) else None
    if appid is None:
        return None
    carimbo = pontes.get(str(appid))
    ponte = ponte_escada.ponte_do_carimbo(carimbo)
    if ponte is None:
        return None
    for chip in CHIPS_DA_ESCADA:
        if chip.ponte == ponte:
            return chip.chave
    return None


# ---------------------------------------------------------------------------
# A coluna Atenção
# ---------------------------------------------------------------------------
class Aviso(NamedTuple):
    """Uma linha da coluna Atenção: o selo, e quem sabe dizer o texto."""

    #: o texto do selo colorido do desenho (`.selo.alerta`)
    selo: str
    #: a função PURA do produto que responde por este aviso
    fonte: Callable[[dict[str, Any] | None], str | None]
    #: o nome da fonte, para o relatório e para a régua
    nome: str


#: AS SEIS FONTES DE AVISO, e todas já são produto — esta aba não escreve uma
#: frase nova. Cada uma é função PURA de ``home_actions`` que devolve o texto ou
#: nada (``None`` ou ``""``, conforme a que estava lá antes; os dois contam como
#: "sem aviso").
#:
#: O aviso do mockup — *"Dois rádios da bancada estão em portas vizinhas"* — é
#: **cena**, e a legenda dele já o declarava (``aba01.AVISOS``): a frase é da
#: aba Conexões, e o ``state_full`` não publica contagem nem texto de aviso.
#: A coluna viva a substitui pelas seis abaixo.
AVISOS_DA_TELA: tuple[Aviso, ...] = (
    Aviso("PAUSA", home_actions.texto_da_pausa, "home_actions.texto_da_pausa"),
    Aviso("GAMEPAD", home_actions.vpad_degradation_text, "home_actions.vpad_degradation_text"),
    Aviso("RÁDIO", home_actions.texto_do_radio_fragil, "home_actions.texto_do_radio_fragil"),
    # `aviso_do_wrapper`, e não `wrapper_banner_text`: o segundo responde "há
    # jogo sem wrapper agora?" e o primeiro responde "há algo a DIZER a ela
    # sobre isso?" — calando quando ela já dispensou o jogo. Trocado em
    # 05/09/2026, decisão dela `07-Q3`: "as duas recusas calam tudo".
    Aviso("JOGO", home_actions.aviso_do_wrapper, "home_actions.aviso_do_wrapper"),
    Aviso("PERFIL", home_actions.autoswitch_lock_text, "home_actions.autoswitch_lock_text"),
    Aviso("PERFIL", home_actions.texto_do_cadeado_cego, "home_actions.texto_do_cadeado_cego"),
)


def avisos_do_estado(state: dict[str, Any] | None) -> list[dict[str, str]]:
    """A coluna Atenção de agora: ``[{"selo", "texto", "fonte"}, …]``.

    Uma fonte que levanta exceção **não derruba a coluna**: as outras cinco
    continuam valendo, e a que falhou vira um aviso com o selo ``ERRO``. Uma
    coluna de avisos que some quando um aviso quebra é a pior das duas falhas —
    ela apaga justamente o que existia para ser visto.
    """
    fora: list[dict[str, str]] = []
    for aviso in AVISOS_DA_TELA:
        try:
            texto = aviso.fonte(state)
        except Exception as erro:  # o `Exception` largo é o ponto — ver o docstring
            fora.append(
                {
                    "selo": "ERRO",
                    "texto": f"{aviso.nome} não respondeu ({type(erro).__name__}).",
                    "fonte": aviso.nome,
                }
            )
            continue
        if texto:
            fora.append({"selo": aviso.selo, "texto": str(texto), "fonte": aviso.nome})
    return fora


def texto_da_conta(quantos: int) -> str:
    """``"1 aviso"`` / ``"3 avisos"`` / ``"nenhum aviso"`` — o canto da coluna.

    O desenho tem ``"1 aviso"`` chumbado; zero avisos é o estado normal de uma
    máquina saudável e o desenho não o tem, então a palavra é escrita aqui e não
    lá.
    """
    if quantos == 0:
        return "nenhum aviso"
    return f"{quantos} aviso" + ("s" if quantos != 1 else "")


# ---------------------------------------------------------------------------
# O cabeçalho e o rodapé
# ---------------------------------------------------------------------------
def nome_do_perfil(state: dict[str, Any] | None) -> str:
    """O perfil ativo, para o crachá do topo E para o recibo do rodapé.

    UM leitor para os dois lugares: a aba Controles mostrou em 29/08 o que
    acontece quando são dois — o topo dizia o perfil vivo e o rodapé continuava
    dizendo "Mortal Kombat", que é o do mockup.
    """
    if not isinstance(state, dict):
        return SEM_LEITOR
    return str(state.get("active_profile") or SEM_LEITOR)


__all__ = [
    "AVISOS_DA_TELA",
    "CHIPS_DA_ESCADA",
    "DEGRAUS_DA_TELA",
    "ESCRITOR_DOS_MODOS",
    "MODOS_DA_TELA",
    "MODOS_LIGADOS",
    "MODO_DESLIGADO",
    "PONTES_DO_INTERRUPTOR",
    "SEM_ALGARISMO",
    "SEM_LEITOR",
    "Aviso",
    "Chip",
    "Lembranca",
    "Modo",
    "avisos_do_estado",
    "chips_sem_degrau",
    "chips_sem_dono",
    "degrau_vivo",
    "degraus_sem_chip",
    "escritor_do_modo",
    "hefesto_ligado",
    "indice_do_chip",
    "ligado_por_modo",
    "modo_lembrado",
    "modo_vivo",
    "nome_do_perfil",
    "plano_do_modo",
    "porque_nao_aplica",
    "texto_da_conta",
]
