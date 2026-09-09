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
            "e o Hefesto não o religa sozinho nem com dois controles ligados.",
        )
    return Lembranca(
        None,
        None,
        "Ninguém decidiu ainda: o Hefesto pode ligar “Jogar pelo Hefesto” "
        "sozinho quando vir dois controles ligados.",
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


#: A FRASE DO MODO NATIVO — **PROVISÓRIO, decisão dela** (PROVA-DE-TELA-01).
#:
#: COOP-NA-CONEXAO-NATIVA-01, Caminho A (06/09/2026). O que ela substitui está
#: medido na §2.4 da sprint: a tela do modo mais fiel ao aparelho dizia, sobre
#: dois controles na mesma sala, que *"não há aqui o que medir"* — verdadeiro
#: sobre movimento, toque, vibração e som, e **mudo sobre a única coisa que
#: muda de comportamento: quantos jogadores existem**.
#:
#: ELA DIZ O MECANISMO, NÃO A RETIRADA, e isso é cicatriz: a primeira redação
#: do ``TEXTO_NATIVO`` foi reprovada por um portão
#: (``tests/unit/test_a_frase_refutada_da_allowlist.py``) por começar com *"O
#: Hefesto saiu da frente"* — a construção que a medição dela derrubou em
#: 06/08. Aqui não há verbo de afastamento nenhum: há o que o produto NÃO monta
#: e quem, em vez dele, conta.
#:
#: E ELA NÃO AFIRMA O QUE NINGUÉM MEDIU. *"O jogo vê dois jogadores"* seria
#: afirmação forte sem régua — a §4.2 da sprint é **inferido do código**, e a
#: medição que a fecharia (dois DualSense num jogo de co-op local, no cabo e no
#: rádio) é bancada dela, na MESA-DE-QUATRO-01. A frase diz de quem é a conta,
#: que é o que se sabe.
FRASE_DO_MODO_NATIVO = (
    "Conexão Nativa com {quantos} controles ligados: neste modo o Hefesto não "
    "cria um controle para cada pessoa — quem conta os jogadores é o jogo, "
    "pelos controles que ele enxerga."
)

#: O SELO DA LINHA ACIMA. ``MODO`` é a palavra do glossário
#: (``docs/A-LINGUA-DESTA-CASA``, §2: *"**Modo**: Jogar pelo Hefesto · Conexão
#: Nativa (Sony) · Controlar o PC"*), e a escada de gravidade que o ordena é
#: ``a01_jogar.ORDEM_DA_GRAVIDADE``.
SELO_DO_MODO = "MODO"


def aviso_do_modo_nativo(state: dict[str, Any] | None) -> str | None:
    """A linha da Conexão Nativa quando há mais de um controle, ou ``None``.

    **SÓ COM DOIS OU MAIS, e o teto é o ponto.** Com um controle só não existe
    pergunta de co-op — a linha seria ruído numa coluna que se chama Atenção, e
    a coluna mostra três de cada vez (``a01_jogar.AVISOS_NA_COLUNA``): um aviso
    que fala sempre empurra para o ``+N`` os que falam quando dói.

    **É A ÚNICA DAS SETE QUE NÃO MORA EM ``home_actions``**, e é escolha, não
    descuido. A frase nasceu nesta leva e o dono dela é esta aba; pô-la lá
    criaria um segundo dono para um assunto que a janela GTK não tem mais —
    ela saiu inteira em 06/09 (``D-0609-GTK-LEVA-INTEIRA``). O contrato é o
    mesmo das outras seis: função PURA de ``state``, ``None`` = sem aviso.

    A CONTAGEM É DE CONECTADOS, não do tamanho da lista: o ``state_full``
    publica também os que já estiveram na sala (``connected: false``), e contar
    a lista acenderia o aviso com um controle na mão.
    """
    if not isinstance(state, dict) or state.get("native_mode") is not True:
        return None
    entradas = state.get("controllers")
    if not isinstance(entradas, list):
        return None
    quantos = sum(
        1 for e in entradas if isinstance(e, dict) and e.get("connected") is True
    )
    if quantos < 2:
        return None
    return FRASE_DO_MODO_NATIVO.format(quantos=quantos)


# ---------------------------------------------------------------------------
# AS CINCO QUE A COLUNA NÃO LIA — JOGAR-OS-SEIS-AVISOS-01 (06/09/2026)
# ---------------------------------------------------------------------------
# TODAS TÊM A MESMA FORMA, e é a forma que o enunciado da sprint nomeia: **o
# daemon publica a chave, ou `home_actions` já tem a função pura, e o pacote da
# aba não lê.** Nada de regra nova: o que nasce aqui é o LEITOR — uma função de
# ``state`` que devolve texto ou ``None``, que é o contrato de :class:`Aviso`.
#
# POR QUE ELAS MORAM AQUI, E NÃO EM ``interface/pacotes/a01_jogar.py``: a sprint
# diz com todas as letras que *"os avisos entram na coluna Atenção por
# `painel.AVISOS_DA_TELA` e `ORDEM_DA_GRAVIDADE` — não invente um segundo
# lugar"*. É a mesma razão que pôs :func:`aviso_do_modo_nativo` aqui em 06/09: o
# pacote da aba PINTA, e quem responde pelo assunto é o motor.
def aviso_do_grab_dobrado(state: dict[str, Any] | None) -> str | None:
    """O jogo pode estar recebendo cada botão duas vezes; ``None`` quando não.

    **A CONDIÇÃO NÃO SE REESCREVE:** ela é de `home_actions.aviso_de_grab`, que
    a I9 já tirou do meio do montador de widgets exatamente para ser chamada de
    fora da GTK — ``is_primary and gamepad_on and grab_state == "failed"``. O
    que esta função faz é o que faltava: **ler do ``state`` os três termos** que
    a janela antiga lia dos widgets dela (`home_actions.py:2943` passa
    ``state.get("primary_grab_state")`` e o ``is_primary`` de cada cartão).

    ``aviso_de_grab`` devolve ``(linha, porquê)`` — a linha era o rótulo e o
    porquê o ``tooltip``. **A coluna Atenção tem um campo de texto por aviso**,
    não um `hover` por linha (`a01_jogar.POR_PAGINA`), então as duas viajam
    juntas numa frase só. Cortar o porquê deixaria na tela o alarme mais
    confuso desta aba sem o que fazer a respeito, que é o defeito que o próprio
    ``AVISO_DE_GRAB_PORQUE`` nasceu para curar.

    **SÓ O PRIMÁRIO CONECTADO CONTA.** ``describe_controllers`` devolve UMA
    entrada com ``connected=False`` quando a mesa está vazia (HARM-CARD-
    FANTASMA-01), e sem o filtro um controle que já saiu da sala acenderia o
    aviso de duplicação de um jogo que ninguém está jogando.
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    gamepad_on = bool(gamepad.get("enabled")) if isinstance(gamepad, dict) else False
    entradas = state.get("controllers")
    if not isinstance(entradas, list):
        return None
    primario = any(
        isinstance(e, dict) and e.get("connected") is True and bool(e.get("is_primary"))
        for e in entradas
    )
    aviso = home_actions.aviso_de_grab(
        state.get("primary_grab_state"), is_primary=primario, gamepad_on=gamepad_on
    )
    if aviso is None:
        return None
    linha, porque = aviso
    return f"{linha}. {porque}"


#: A FRASE DA LINHA DE ORIGEM — **PROVISÓRIO, decisão dela** (PROVA-DE-TELA-01).
#:
#: Ela responde a UMA pergunta, e a sprint a escreve assim: *"por que o modo
#: mudou sem eu mexer"*. A janela antiga respondia com ``"Nativo ligado pelo
#: perfil ativo"`` / ``"Gamepad ligado pelo perfil ativo"``
#: (`home_actions.py:2884-2888`), duas frases montadas dentro do render e
#: juntadas por ``" · "``.
#:
#: **O QUE MUDA AQUI É O NOME DO MODO, e é o glossário que manda.** ``Nativo`` e
#: ``Gamepad`` são palavras da casa; na tela os modos chamam-se *Conexão Nativa
#: (Sony)* e *Jogar pelo Hefesto* (`docs/A-LINGUA-DESTA-CASA`, §2), e os rótulos
#: saem de :data:`_ROTULO_DO_MODO`, que é `home_actions._MODE_ITEMS` — o léxico
#: que as quatro superfícies desta casa compartilham. Digitá-los seria a segunda
#: cópia da palavra dela.
#:
#: **A REGÊNCIA É "QUEM LIGOU … FOI", e não "… foi ligado", por causa do
#: GÊNERO.** Os dois rótulos que entram aqui têm gêneros diferentes — *a*
#: Conexão Nativa e *o* Jogar pelo Hefesto —, e um particípio concordaria com um
#: e erraria o outro em toda tela que mostrasse o primeiro. Uma frase que exige
#: um `if` de gênero para não sair errada é uma frase mal escolhida; esta não
#: flexiona nada.
FRASE_DA_ORIGEM_DO_MODO = "Quem ligou {modo} foi o perfil ativo, e não um gesto seu."

#: O QUE SEPARA AS DUAS ORIGENS quando as duas falam. É o mesmo ``" · "`` da
#: janela antiga (`home_actions.py:2892`), e não um "e": as duas são fatos
#: independentes, não uma frase composta.
SEPARADOR_DA_ORIGEM = " · "


def aviso_da_origem_do_modo(state: dict[str, Any] | None) -> str | None:
    """O modo em vigor foi ligado pelo PERFIL, e não por ela; ``None`` se não.

    **É A SEGUNDA DAS SETE QUE NÃO MORA EM ``home_actions``, e pela mesma razão
    da primeira** (:func:`aviso_do_modo_nativo`): lá ela nunca foi função. A
    regra vivia SOLTA dentro de ``HomeActionsMixin._render_home``, montando uma
    lista de pedaços entre dois `set_text` — não havia o que importar. A janela
    GTK saiu inteira em 06/09 (``D-0609-GTK-LEVA-INTEIRA``), então pôr isto lá
    criaria um dono novo num arquivo que está de saída.

    AS DUAS CHAVES SÃO DO DAEMON, e cada uma tem escritor próprio:
    ``native_mode_origin`` (`daemon/state_store.py:734`) e ``mode_from_profile``
    (`daemon/lifecycle.py:2490`). O ``native_mode`` entra na conta junto com a
    origem porque a origem SOBREVIVE ao modo no store — sem ele a tela diria
    que o perfil ligou um Nativo que já não está de pé.

    ``== "profile"`` e ``== "gamepad"`` LITERAIS, e não "qualquer coisa que não
    seja vazio": os dois campos têm outros valores (origem manual, e o
    ``native`` do ``mode_from_profile``, que o ramo de cima já cobre), e um
    ``truthy`` transformaria *"você mesma ligou"* em *"o perfil ligou"*.
    """
    if not isinstance(state, dict):
        return None
    partes: list[str] = []
    if state.get("native_mode") and state.get("native_mode_origin") == "profile":
        partes.append(FRASE_DA_ORIGEM_DO_MODO.format(modo=_ROTULO_DO_MODO[MODE_NATIVE]))
    if state.get("mode_from_profile") == "gamepad":
        partes.append(FRASE_DA_ORIGEM_DO_MODO.format(modo=_ROTULO_DO_MODO[MODE_GAMEPAD]))
    return SEPARADOR_DA_ORIGEM.join(partes) if partes else None


#: O QUE O "Reconectar Controles" DIZ QUANDO NEM O PRIMEIRO PASSO SAIU.
#:
#: PROVISÓRIO — texto de tela é palavra dela (PROVA-DE-TELA-01). A janela antiga
#: dizia *"Não consegui reconciliar — o Hefesto pode estar desligado."*, um
#: literal solto dentro do ``_sync_fail`` do handler
#: (`home_actions.py:3348-3351`) — sem constante, e portanto sem como ser
#: importado por quem não é aquela janela.
#:
#: **O VERBO MUDOU PORQUE O BOTÃO MUDOU.** A legenda desta aba registra a troca:
#: *"'Reconciliar jogadores' virou 'Reconectar Controles'"* (`aba01.py:1673`).
#: Uma recusa que usa o verbo de um botão que não existe mais manda a pessoa
#: procurar o que não está lá, que é o que o glossário proíbe.
#:
#: E ELA NÃO AFIRMA QUE NADA ACONTECEU: ``chamar``/``resultado`` devolvem falha
#: também no timeout, e o daemon pode ter feito o trabalho sem a resposta
#: chegar — é a mesma cicatriz que a `a09_sistema.SEM_RESPOSTA_DO_SERVICO`
#: escreve por extenso. O que ela afirma é o que se sabe: não deu para falar.
RECONECTAR_SEM_SERVICO = (
    "Não consegui falar com o serviço para reconectar os controles — o Hefesto "
    "pode estar desligado."
)


def recibo_do_reconectar(jogadores: object, resultado: object) -> str:
    """A frase única do "Reconectar Controles" — quem escreve é `home_actions`.

    **NADA SE MONTA AQUI.** `home_actions.reconciliar_toast` é a dona das quatro
    desfechos que o gesto tem, e ela já os separa: quantos jogadores voltaram; a
    numeração compactada em N controles; a numeração que já estava compacta; e a
    recusa por jogo aberto, que **não é falha** — com os jogadores de pé, um
    recado de erro seria a interface mentindo.

    Esta função existe por UM motivo, e ele é de posição: `reconciliar_toast`
    vive em `home_actions`, que é a camada da janela antiga, e o gesto da aba
    vive em `interface/pacotes/`. Um `import` direto de lá para cá poria o nome
    do dono dentro do lado HTML — e é este módulo, e não o pacote da aba, que a
    casa elegeu como a ponte entre os dois (é o que `AVISOS_DA_TELA` já faz com
    as outras sete).

    **E ELA PASSOU A CALAR QUANDO NÃO HÁ NOTÍCIA — JOGAR-02, 09/09/2026.**
    Pedido dela, com um print da aba Jogar: *"remover essa frase que aparece
    tambem ao clciar em reconectar controles"*.  # noqa-acento: citação dela
    A frase era::

        Jogadores reconciliados — 2 jogador(es). A numeração já estava compacta.

    e ela está errada por três razões que não são uma:

    1. **é a língua de dentro** — *reconciliados* e *numeração compacta* são
       palavras do daemon (`CoopManager.sync`, `identity.compact`), e a
       LÍNGUA DESTA CASA §3 já decidiu que "deu certo" se responde com a
       piscada verde, sem palavra nova;
    2. **"já estava compacta" não é notícia** — é a ausência dela. Um recibo
       que diz "não mudou nada" é o piloto falando sem ter o que dizer;
    3. **o recado pousa no CARTÃO do controle escolhido e cobre a identidade
       dele por seis segundos** — o desenho, o nome, o plástico, o transporte
       e a bateria somem. *Um recado que apaga a identidade tira a resposta da
       pergunta que ele veio responder.*

    :return: a frase, ou **`""`** quando não houve o que contar — e o gesto
        traduz o vazio em "sem recado", que é a piscada verde do botão.
    """
    if _sem_noticia(resultado):
        return ""
    return _na_lingua_da_tela(resultado)


#: A FRASE DO RECONECTAR, NA LÍNGUA DA TELA — JOGAR-02 §2, 09/09/2026.
#:
#: **ELA NÃO VEM MAIS DE `home_actions.reconciliar_toast`**, e são duas razões
#: somadas: aquela frase é a da JANELA GTK, que está saindo inteira
#: (`D-0609-GTK-LEVA-INTEIRA`) e sai com ela; e ela fala a língua de dentro —
#: *"Jogadores reconciliados"*, *"numeração compactada"* são
#: `CoopManager.sync` e `identity.compact` escritos na tela dela.
#:
#: O QUE ENTRA NO LUGAR nomeia o ASSENTO, que é a palavra que esta tela já usa
#: em toda parte: `P1`, `P2`. A LÍNGUA DESTA CASA §1 diz isso para `mesa`, e
#: vale igual aqui.
#:
#: A FRASE DE FALHA CONTINUA SENDO FALHA: *"não consegui"* não é língua de
#: dentro, é o produto dizendo que não fez — e silêncio sobre isso é a mentira
#: que esta casa persegue.
_RENUMEROU = "Os controles foram renumerados: {quais}."
_NAO_CONFERIU = "Não consegui conferir a numeração dos controles."
_NAO_COMPACTOU = "Não consegui ajustar a numeração dos controles."


def _na_lingua_da_tela(resultado: object) -> str:
    """O desfecho do `identity.renumber` em palavras da tela.

    OS NÚMEROS SAEM DO PRÓPRIO `renumbered`, e não de uma contagem: dizer
    *"2 controle(s)"* obriga ela a descobrir QUAIS; dizer `P1, P2` responde.
    """
    if not isinstance(resultado, dict):
        return _NAO_CONFERIU
    if not resultado.get("ok"):
        return _NAO_COMPACTOU
    renumerados = resultado.get("renumbered")
    if not isinstance(renumerados, dict) or not renumerados:
        return ""
    #: A ORDEM É A DO NÚMERO, e não a do dicionário: a tela lê da esquerda
    #: para a direita, e `P2, P1` faria ela conferir duas vezes.
    quais = sorted({f"P{v}" for v in renumerados.values()
                    if isinstance(v, int) and not isinstance(v, bool)})
    return _RENUMEROU.format(quais=", ".join(quais)) if quais else ""


#: OS DESFECHOS QUE NÃO SÃO NOTÍCIA — e a lista é curta de propósito.
#:
#: `renumbered` VAZIO é "a numeração já estava compacta", e
#: `sessao_de_jogo_aberta` é a recusa do passo 2 com o jogo aberto — que **não
#: é falha**: os jogadores já voltaram no passo 1, e um recado de erro ali
#: seria a interface mentindo (é a mesma regra do `reported_step_index`).
#:
#: O QUE CONTINUA SENDO NOTÍCIA: a numeração que MUDOU (`renumbered` com
#: entradas) e as duas falhas de leitura ("não consegui conferir", "não
#: consegui compactar") — as duas dizem que o produto não fez, e silêncio
#: sobre isso é a mentira que esta casa persegue.
def _sem_noticia(resultado: object) -> bool:
    """Este desfecho do `identity.renumber` tem alguma coisa a contar?"""
    if not isinstance(resultado, dict):
        return False
    if not resultado.get("ok"):
        return resultado.get("reason") == "sessao_de_jogo_aberta"
    renumerados = resultado.get("renumbered")
    return not (isinstance(renumerados, dict) and renumerados)


#: AS DOZE FONTES DE AVISO. Dez são função PURA de ``home_actions`` que devolve
#: o texto ou nada (``None`` ou ``""``, conforme a que estava lá antes; os dois
#: contam como "sem aviso"); as outras duas — :func:`aviso_do_modo_nativo` e
#: :func:`aviso_da_origem_do_modo` — nasceram aqui, e cada uma diz por quê no
#: próprio docstring.
#:
#: **NÃO CONTE ESTA LISTA NUM NÚMERO ESCRITO EM OUTRO LUGAR.** A docstring de
#: `a01_jogar._avisos` já errou o próprio três vezes em três dias; o que fica
#: escrito é a LISTA, que se conta sozinha. Quem acrescentar uma fonte
#: acrescenta uma linha aqui — e nada mais.
#:
#: O aviso do mockup — *"Dois rádios da bancada estão em portas vizinhas"* — é
#: **cena**, e a legenda dele já o declarava (``aba01.AVISOS``): a frase é da
#: aba Conexões, e o ``state_full`` não publica contagem nem texto de aviso.
#: A coluna viva a substitui pelas de baixo.
AVISOS_DA_TELA: tuple[Aviso, ...] = (
    Aviso("PAUSA", home_actions.texto_da_pausa, "home_actions.texto_da_pausa"),
    Aviso("GAMEPAD", home_actions.vpad_degradation_text, "home_actions.vpad_degradation_text"),
    Aviso("RÁDIO", home_actions.texto_do_radio_fragil, "home_actions.texto_do_radio_fragil"),
    # `aviso_do_wrapper`, e não `wrapper_banner_text`: o segundo responde "há
    # jogo sem wrapper agora?" e o primeiro responde "há algo a DIZER a ela
    # sobre isso?" — calando quando ela já dispensou o jogo. Trocado em
    # 05/09/2026, decisão dela `07-Q3`: "as duas recusas calam tudo".
    #
    # É A ÚNICA DAS SEIS QUE TOCA O DISCO, e só no caso raro: com jogo aberto
    # sem o atalho ela lê as duas listas de recusa. Medido em 06/09/2026
    # (ONDA5-07-03): **0,050 ms por tique** com os dois arquivos povoados,
    # contra 2,85 ms de mediana do tique inteiro da aba Jogar. O número está no
    # docstring de `home_actions.ela_ja_respondeu_sobre`, com a razão de não
    # haver vigia em segundo plano aqui.
    Aviso("JOGO", home_actions.aviso_do_wrapper, "home_actions.aviso_do_wrapper"),
    Aviso("PERFIL", home_actions.autoswitch_lock_text, "home_actions.autoswitch_lock_text"),
    Aviso("PERFIL", home_actions.texto_do_cadeado_cego, "home_actions.texto_do_cadeado_cego"),
    # COOP-NA-CONEXAO-NATIVA-01, Caminho A: o modo mais fiel ao aparelho era o
    # único que não dizia quantos jogadores existem nele. Entra por ÚLTIMO na
    # declaração e por ORDEM na tela — quem ordena é `ORDEM_DA_GRAVIDADE`.
    Aviso(SELO_DO_MODO, aviso_do_modo_nativo, "painel.aviso_do_modo_nativo"),
    # --- JOGAR-OS-SEIS-AVISOS-01, 06/09/2026: as cinco que faltavam ---------
    #
    # NENHUM SELO NOVO, e é escolha medida. `a01_jogar.ORDEM_DA_GRAVIDADE` diz
    # que o que não está na tupla dela cai DEPOIS DE TUDO — e com a coluna
    # mostrando três de cada vez (`AVISOS_NA_COLUNA`), um selo fora da escada é
    # um selo que a máquina cheia esconde atrás do `+N`. As cinco entram nos
    # degraus que já existem, pelo assunto de cada uma.
    #
    # `MODO` — a tela promete "Controlar o PC" e o controle não move o cursor.
    # É o MODO-QUE-NAO-CONTROLA-01, medido com ela ao vivo (*"cliquei em
    # aplicar e nada"*), e é a MESMA pergunta do `aviso_do_modo_nativo` vizinho:
    # o modo em vigor faz o que o nome dele promete? Os dois nunca disputam a
    # linha — um só fala no Nativo, o outro só no desktop.
    #
    # **O TERCEIRO ARGUMENTO DELA NÃO SE PASSA AQUI, e o custo está medido no
    # relato:** `texto_do_desktop_sem_emulacao` aceita `modo_mudou_agora=` para
    # não julgar a emulação no mesmo tique em que o modo mudou (o
    # `mouse.emulation.restore` é o ÚLTIMO dos três IPCs). Uma fonte desta
    # coluna é função PURA de `state`, e o tique da interface nova não tem
    # memória do tique anterior — então o aviso pode piscar durante a transição
    # para o desktop. `modo_exibido=` também fica de fora, e por medição: nesta
    # interface o clique aplica na hora, então exibido e vigente são o mesmo
    # valor e o argumento não muda desfecho nenhum.
    Aviso("MODO", home_actions.texto_do_desktop_sem_emulacao,
          "home_actions.texto_do_desktop_sem_emulacao"),
    # `GAMEPAD` — os dois falam de como o JOGO vê os controles, que é o critério
    # que o degrau declara. O vpad degradado é o jogo recebendo MENOS do que ela
    # pediu; o grab dobrado é o jogo recebendo DUAS VEZES o mesmo botão.
    #
    # A TERCEIRA FORMA DESSE MESMO ASSUNTO — a divergência de máscara — **não
    # entra nesta tupla**, e a razão é de ENDEREÇO, não de conteúdo:
    # `home_actions.texto_da_divergencia` devolve markup do Pango, e quem sabe
    # tirá-lo é uma função da JANELA GTK. Apontar deste arquivo para lá seria
    # uma citação NOVA para a janela que está saindo (`D-0609-GTK-LEVA-INTEIRA`),
    # e há portão que reprova — `scripts/check_nada_aponta_para_a_janela.py`,
    # que reprovou a primeira versão desta cura em 06/09/2026 nomeando arquivo e
    # linha. Ela mora em `a01_jogar._aviso_da_divergencia_de_mascara`, ao lado
    # do `_aviso_da_ponte`, que é a outra fonte desta coluna que volta em markup
    # e que já tem a única citação DECLARADA daquele arquivo.
    #
    # E O NOME DAQUELA FUNÇÃO NÃO SE ESCREVE AQUI, nem em prosa: o portão varre
    # o texto do arquivo, não os imports — um comentário que a soletrasse seria
    # a citação que ele proíbe. É a mesma lição do `BOOTSTRAP` em 05/09, quando
    # um aviso citou literalmente o padrão que descrevia e virou o defeito.
    Aviso("GAMEPAD", aviso_do_grab_dobrado, "painel.aviso_do_grab_dobrado"),
    # `JOGO` — o degrau é "há jogo aberto", e é exatamente o que esta linha diz:
    # com a partida de pé o "Reconectar Controles" traz os jogadores de volta e
    # a numeração espera. A FRASE É DO DONO, sem prefixo nosso: pôr o nome do
    # botão na frente seria a segunda cópia de um rótulo cujo dono é o gerador
    # da página.
    Aviso("JOGO", home_actions._reconciliar_gate_text,
          "home_actions._reconciliar_gate_text"),
    # `PERFIL` — o mesmo degrau do cadeado da troca automática e do detector
    # cego, e o mesmo assunto: o perfil agindo sozinho. Esta é a resposta a "por
    # que o modo mudou sem eu mexer".
    Aviso("PERFIL", aviso_da_origem_do_modo, "painel.aviso_da_origem_do_modo"),
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
    "FRASE_DA_ORIGEM_DO_MODO",
    "FRASE_DO_MODO_NATIVO",
    "MODOS_DA_TELA",
    "MODOS_LIGADOS",
    "MODO_DESLIGADO",
    "PONTES_DO_INTERRUPTOR",
    "RECONECTAR_SEM_SERVICO",
    "SELO_DO_MODO",
    "SEM_ALGARISMO",
    "SEM_LEITOR",
    "SEPARADOR_DA_ORIGEM",
    "Aviso",
    "Chip",
    "Lembranca",
    "Modo",
    "aviso_da_origem_do_modo",
    "aviso_do_grab_dobrado",
    "aviso_do_modo_nativo",
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
    "recibo_do_reconectar",
    "texto_da_conta",
]
