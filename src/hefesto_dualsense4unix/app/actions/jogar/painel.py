"""O que a aba **Jogar** pode dizer hoje — e, com o mesmo peso, o que não pode.

29/08/2026. A aba Jogar é a que ABRE o aplicativo, e no desenho aprovado
(``novo-layout/01-jogar.html``) ela tem quatro grupos de valor: a **fileira de
modos**, a **escada de pontes**, os **cartões da mesa** e a coluna **Atenção**.
Três deles o produto já responde por inteiro. Um não, e este módulo é onde isso
está escrito.

**A REGRA QUE ESTE ARQUIVO EXISTE PARA CUMPRIR:** um número plausível e falso é
pior que um traço honesto, porque ela confia nele. Toda linha de tela desta aba
que não tem leitor no produto sai daqui com :data:`SEM_LEITOR` no lugar do
valor, e o motivo junto — nunca apagada, nunca inventada.

O que NÃO mora aqui, de propósito
---------------------------------

* **A montagem da mesa** (um item por controle, com cor, transporte e número do
  jogador) é de ``novo-layout/_ferramentas/mesa_viva.mesa_do_estado``, que já é
  o dono dela para a aba Controles e para a fita. Reescrevê-la aqui criaria o
  segundo dono do mesmo valor — o defeito que a fita viva de 27/08 pagou.
* **A janela e as duas pontes** são de
  :mod:`hefesto_dualsense4unix.gui.ponte_da_tela`, e são de todas as dez abas.
* **A pintura** é do piloto: quem escreve no DOM escreve por TIPO, e isso é
  código de tela.

Os três buracos, medidos em 29/08/2026
--------------------------------------

1. **O quarto botão de modo, "Desligado".** :func:`mode_of_state
   <hefesto_dualsense4unix.app.actions.mode_transition.mode_of_state>` é o
   **ponto único de leitura do modo vivo** nesta casa (o docstring dela o diz
   com todas as letras: *"a Início e a Emulação derivavam o modo do mesmo
   payload com regras próprias e podiam discordar"*), e ela devolve **três**
   valores — ``desktop``, ``gamepad``, ``native``. Nunca um quarto. O
   ``state_full`` tem ``paused``, mas pausa é outra coisa: é o PS+Options, e ela
   tem texto próprio (``home_actions.texto_da_pausa``). Chamar pausa de
   "Desligado" seria esta tela inventando um estado. **É a MIGRA-JOGAR-06, e a
   pergunta é dela.**

2. **A escada tem cinco degraus no desenho e quatro no código** — e a relação
   entre os dois conjuntos não é "sobra um": ver :data:`DEGRAUS_DA_TELA` e
   :func:`degraus_sem_chip`. Um degrau real não tem chip na tela, e um chip da
   tela não tem degrau real. **É a MIGRA-JOGAR-07.**

3. **O "Automático" da escada não tem leitor.** Ele é o mecanismo inteiro de
   ``integrations/ponte_escada`` (*tenta em ordem, para quando acerta*), não um
   degrau; e nada no ``state_full`` nem no perfil diz se ele está ligado ou se
   ela fixou um degrau à mão. O que EXISTE é a memória por jogo — o carimbo que
   :func:`degrau_vivo` lê.
"""
from __future__ import annotations

from typing import Any, Callable, NamedTuple

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations import ponte_escada

#: O que se escreve no lugar de um valor que o produto não tem como responder.
#: É um traço, e não um zero: zero é uma medida, e esta tela não mediu nada.
SEM_LEITOR = "—"

#: O identificador do quarto botão de modo, que não é um modo do
#: :mod:`~hefesto_dualsense4unix.app.actions.mode_transition`.
MODO_DESLIGADO = "desligado"


class Modo(NamedTuple):
    """Um botão da fileira "O que o controle faz agora"."""

    #: o ``data-modo`` do botão na página
    chave: str
    #: o rótulo aprovado por ela, no desenho
    rotulo: str
    #: o valor que ``mode_of_state`` devolve para este botão — ``None`` quando
    #: **nenhum** valor dela corresponde a ele, e é o caso do "Desligado"
    lido_como: str | None
    #: por que este botão não tem leitor (vazio quando tem)
    porque_nao: str = ""

    @property
    def tem_leitor(self) -> bool:
        return self.lido_como is not None


#: A FILEIRA DE MODOS, NA ORDEM DO DESENHO. Os rótulos são os do mockup
#: aprovado; os três primeiros ids são os de
#: ``mode_transition.MODES``, e o quarto **não existe lá** — que é o ponto.
#:
#: Os rótulos dos três com leitor NÃO são digitados aqui: saem de
#: ``home_actions.ITENS_DE_MODO``/``_MODE_ITEMS``, que é o léxico desta casa
#: (``app/actions/contrato_da_mascara.py`` o republica, e o
#: ``app/widgets/painel_no_jogo.py`` o consome). Digitá-los seria a segunda
#: cópia da palavra dela.
_ROTULO_DO_MODO: dict[str, str] = dict(home_actions._MODE_ITEMS)

MODOS_DA_TELA: tuple[Modo, ...] = (
    Modo(
        MODO_DESLIGADO,
        "Desligado",
        None,
        "`mode_transition.mode_of_state` é o ponto único de leitura do modo "
        "vivo e devolve TRÊS valores (desktop, gamepad, native); não existe um "
        "quarto. O `state_full.paused` é a pausa do PS+Options, que tem texto "
        "próprio em `home_actions.texto_da_pausa` — chamá-la de 'Desligado' "
        "seria a tela inventando um estado. MIGRA-JOGAR-06, e a pergunta é dela.",
    ),
    Modo(MODE_DESKTOP, _ROTULO_DO_MODO[MODE_DESKTOP], MODE_DESKTOP),
    Modo(MODE_GAMEPAD, _ROTULO_DO_MODO[MODE_GAMEPAD], MODE_GAMEPAD),
    Modo(MODE_NATIVE, _ROTULO_DO_MODO[MODE_NATIVE], MODE_NATIVE),
)


def modo_vivo(state: dict[str, Any] | None) -> str | None:
    """Qual botão da fileira está aceso — ``None`` com o daemon calado.

    Delega, sem uma linha de regra própria. O valor devolvido é a ``chave`` de
    um :class:`Modo` de :data:`MODOS_DA_TELA`, ou ``None``.
    """
    return mode_of_state(state)


# ---------------------------------------------------------------------------
# A escada — cinco chips no desenho, quatro degraus no código
# ---------------------------------------------------------------------------
class Chip(NamedTuple):
    """Um chip da escada "Modo de conexão", no desenho aprovado."""

    #: o ``data-degrau`` do chip na página
    chave: str
    #: o algarismo que o desenho põe no círculo ("A", "1", "2", "3", "4")
    algarismo: str
    #: o rótulo aprovado por ela
    rotulo: str
    #: a ponte que este chip NOMEIA — ``None`` para o "Automático", que não é
    #: um degrau e sim o mecanismo inteiro
    ponte: ponte_escada.Ponte | None


#: OS CINCO CHIPS DO DESENHO, com a ponte que cada um nomeia. Os rótulos são
#: dela (``novo-layout/01-jogar.html``); a ponte é a tradução para o
#: vocabulário de ``integrations/ponte_escada``.
#:
#: **A tradução é declarada aqui e o ÍNDICE é calculado** — nunca digitado.
#: :func:`indice_do_chip` pergunta a ``ponte_escada.indice_do_degrau``, então
#: acrescentar ou tirar um degrau da ``ESCADA`` muda esta tela sozinho, e
#: :func:`degraus_sem_chip` denuncia quem ficar sem chip.
CHIPS_DA_ESCADA: tuple[Chip, ...] = (
    Chip("automatico", "A", "Automático", None),
    Chip(
        "hefesto",
        "1",
        "Hefesto",
        ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, ponte_escada.MASCARA_DUALSENSE),
    ),
    Chip("sony", "2", "Sony (nativo)", ponte_escada.Ponte(ponte_escada.KIND_NATIVE)),
    Chip(
        "steam",
        "3",
        "Steam Input",
        ponte_escada.Ponte(
            ponte_escada.KIND_GAMEPAD,
            ponte_escada.MASCARA_DUALSENSE,
            steam_input=True,
        ),
    ),
    # O QUINTO. Ele nomeia `KIND_DESKTOP`, que EXISTE como constante
    # (`ponte_escada.py:169`) e é aceito por `ponte_do_perfil` e
    # `ponte_do_carimbo` (`:375`, `:395`) — mas NÃO É DEGRAU: a `ESCADA` não
    # tem uma linha com ele, e por isso `indice_do_degrau` devolve -1. A escada
    # nunca sobe até aqui.
    Chip("desktop", "4", "Teclado + Mouse", ponte_escada.Ponte(ponte_escada.KIND_DESKTOP)),
)

#: Compatibilidade de nome com o gerador do mockup, que chama a mesma coisa de
#: "degraus". São os chips do desenho, não os degraus do código — e a diferença
#: entre os dois é o assunto deste bloco.
DEGRAUS_DA_TELA = CHIPS_DA_ESCADA


def indice_do_chip(chip: Chip) -> int:
    """Posição do chip na ``ponte_escada.ESCADA``, ou ``-1`` se ele não é degrau.

    ``-1`` não é erro: é o valor honesto para o "Automático" (que é o mecanismo,
    não um degrau) e para o "Teclado + Mouse" (que o desenho promete e a escada
    não tem).
    """
    if chip.ponte is None:
        return -1
    return ponte_escada.indice_do_degrau(chip.ponte)


def chips_sem_degrau() -> tuple[Chip, ...]:
    """Os chips que o desenho mostra e a ``ESCADA`` não tem — a tela devendo.

    Clicar num deles não pode fazer nada, e a tela tem de dizer isso em vez de
    oferecer um botão morto.
    """
    return tuple(c for c in CHIPS_DA_ESCADA if c.ponte is not None and indice_do_chip(c) < 0)


def degraus_sem_chip() -> tuple[ponte_escada.Degrau, ...]:
    """Os degraus da ``ESCADA`` que NENHUM chip do desenho nomeia — o código
    devendo à tela.

    Medido em 29/08/2026: é o segundo degrau, ``gamepad`` com a máscara
    ``xbox`` — *"o piso mais largo que existe"*, diz o ``porque`` dele. A escada
    automática passa por ele e a tela dela não tem onde mostrá-lo. **Isto não se
    conserta aqui**: acrescentar um chip é desenhar tela, e tela é palavra dela
    (PROVA-DE-TELA-01). O que se faz aqui é não deixar o buraco calado.
    """
    nomeadas = {c.ponte for c in CHIPS_DA_ESCADA if c.ponte is not None}
    return tuple(d for d in ponte_escada.ESCADA if d.ponte not in nomeadas)


def degrau_vivo(
    state: dict[str, Any] | None,
    pontes: dict[str, Any] | None,
) -> str | None:
    """A ``chave`` do chip aceso, ou ``None`` — e ``None`` é o caso comum.

    A ÚNICA memória viva da escada é **por jogo**: o carimbo que
    ``integrations/prontuario_dos_jogos.pontes_confirmadas`` lê dos perfis do
    disco (``{appid: Ponte}``). Sem jogo aberto — ``state_full.jogo_steam.appid``
    ausente — não há o que acender, e acender o "Automático" por padrão seria
    afirmar uma escolha que ninguém fez.

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
    Aviso("JOGO", home_actions.wrapper_banner_text, "home_actions.wrapper_banner_text"),
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
        except Exception as erro:  # noqa: BLE001 — ver o docstring
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
    "MODOS_DA_TELA",
    "MODO_DESLIGADO",
    "SEM_LEITOR",
    "Aviso",
    "Chip",
    "Modo",
    "avisos_do_estado",
    "chips_sem_degrau",
    "degrau_vivo",
    "degraus_sem_chip",
    "indice_do_chip",
    "modo_vivo",
    "nome_do_perfil",
    "texto_da_conta",
]
