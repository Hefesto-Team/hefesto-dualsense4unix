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
  :mod:`hefesto_dualsense4unix.interface.janela`, e são de todas as dez abas.
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
   virou o interruptor, e nenhum degrau da escada ficou sem lugar na tela. Quem
   confere isso é a régua da suíte
   (``tests/unit/test_o_botao_de_ligar_funciona_e_se_lembra.py``), e não uma
   função daqui: a pergunta é de quem desenvolve, e a tela nunca a fez.

3. **O "Automático" da escada não tinha leitor nem escritor.** **FECHADO por
   palavra dela**, 31/08: *"na aba jogar o Botão Automático não existe"*. O
   MECANISMO ficou inteiro — *tentar em ordem e parar quando acerta* é o que
   ``integrations/ponte_tentativa`` faz sozinho, sempre; o que saiu foi o botão
   que fingia comandá-lo.

O QUE CONTINUA EM ABERTO, e é honesto dizer
-------------------------------------------

* **Point And Click FECHOU** — POINT-AND-CLICK-01, 17/09/2026, pela ordem dela:
  *"o modo point and click é o modo navegação e o modo que nós mesmos podemos
  usar e configurar na aba navegação. Ele ativa o modo configurado lá."* Ele
  nunca foi um botão órfão: é o ``kind="desktop"`` do perfil, com chip na tela
  chamado **Navegação**, gesto no terceiro degrau do PS + R3 e uma aba inteira
  configurando-o. **O que faltava era o fio** entre o que ela configura e o que
  o chip ativa, e no lugar dele havia uma flag global de sessão. A linha
  fantasma da tabela saiu, e nenhum chip ficou sem quem o atenda (a régua é
  ``tests/unit/test_a_fileira_nao_tem_linha_fantasma.py``).
* **Navegação tem escritor e não é degrau** — ``apply_mode('desktop')``
  funciona hoje, e desde 17/09 ele CARREGA O PERFIL
  (``Daemon.aplicar_o_arranjo_do_desktop``). O que ela não tem é degrau na
  ``ESCADA`` automática: "não é degrau" e "não tem dono" são perguntas
  diferentes, e a Navegação responde sim à primeira e não à segunda.
  O **PS + R3** para nela desde 13/09 (``hotkey.CICLO_DE_PONTES``), que é outro
  objeto e não a ``ESCADA``.
* **Steam Input não se fixa pela tela**: não há método de IPC que o ligue, e o
  degrau só sobrevive com a Steam fechada. **Sony DualSense** e **Xbox** se
  fixam, e cada um é um CAMINHO (MODO-DE-CONEXAO-01, 13/09/2026): o chip manda
  `gamepad.emulation.set {caminho}` e o **PS + R3** é o mesmo modo pelo
  controle.
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
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_DUALSENSE,
    CAMINHO_XBOX,
    normalizar_caminho,
)

SEM_LEITOR = "—"

SEM_ALGARISMO = "\N{EN DASH}"


class Modo(NamedTuple):
    """Um botão da fileira "O que o controle faz agora"."""

    chave: str
    rotulo: str
    #: o valor que ``mode_of_state`` devolve para este botão — ``None`` quando
    lido_como: str | None
    porque_nao: str = ""

    @property
    def tem_leitor(self) -> bool:
        return self.lido_como is not None


#:     e não do lado desligado, porque **quem emula teclado e mouse é o próprio
_ROTULO_DO_MODO: dict[str, str] = dict(home_actions._MODE_ITEMS)

MODOS_DA_TELA: tuple[Modo, ...] = (
    Modo(MODE_GAMEPAD, _ROTULO_DO_MODO[MODE_GAMEPAD], MODE_GAMEPAD),
    Modo(MODE_NATIVE, _ROTULO_DO_MODO[MODE_NATIVE], MODE_NATIVE),
    Modo(MODE_DESKTOP, _ROTULO_DO_MODO[MODE_DESKTOP], MODE_DESKTOP),
)

MODOS_LIGADOS: tuple[str, ...] = (MODE_GAMEPAD, MODE_DESKTOP)


def modo_vivo(state: dict[str, Any] | None) -> str | None:
    """Qual botão da fileira está aceso — ``None`` com o daemon calado."""
    return mode_of_state(state)


def ligado_por_modo(chave: str | None) -> bool | None:
    """O interruptor, a partir de uma chave de modo — ``None`` quando não se sabe."""
    if not chave:
        return None
    return chave in MODOS_LIGADOS


def hefesto_ligado(state: dict[str, Any] | None) -> bool | None:
    """A POSIÇÃO DO INTERRUPTOR agora: ``True`` Ligado · ``False`` Desligado ·"""
    return ligado_por_modo(modo_vivo(state))


def caminho_vivo(state: dict[str, Any] | None) -> str | None:
    """O CAMINHO de pé agora — ``None`` quando não se sabe. MODO-DE-CONEXAO-01.

    É o leitor que acende o chip de modo da fileira, e ele não lê a máscara: até
    13/09/2026 a tela acendia o chip por `home_actions.mascara_do_aparelho`, que
    no `uinput` cai no `flavor` da sessão — e com o cartão do P1 em Xbox 360 o
    chip «Sony DualSense» ficava aceso com o jogo vendo Xbox 360.

    O dono do valor é o daemon (`gamepad_emulation.caminho` do `state_full`). Um
    daemon de antes da cura não publica o campo: aí só o `backend` `uhid` responde
    por si, e o `uinput` sozinho não separa o Xbox escolhido do DualSense que
    degradou — ``None``, e a tela não acende nada que ninguém leu.
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    publicado = normalizar_caminho(gamepad.get("caminho"))
    if publicado is not None:
        return publicado
    if gamepad.get("backend") == "uhid":
        return CAMINHO_DUALSENSE
    return None


# pelo Hefesto" enquanto o `mode_of_state` do daemon dizia `desktop` — o F7

#: nenhum e escritor nenhum, e a **Navegação** é o caso do meio ao contrário —
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
    """Quem APLICA este botão, ou o porquê de ninguém aplicar."""
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
    """Vazio quando o botão TEM escritor; a recusa do dono, quando não tem."""
    if chave in ESCRITOR_DOS_MODOS:
        return ""
    return escritor_do_modo(chave)


def plano_do_modo(
    chave: str, mascara: str | None = None, caminho: str | None = None
) -> list[tuple[str, dict[str, Any]]] | None:
    """A sequência de IPC do clique — DELEGADA, sem uma linha de regra própria."""
    if chave not in ESCRITOR_DOS_MODOS:
        return None
    return plan_mode_transition(chave, mascara, caminho)


class Lembranca(NamedTuple):
    """O que ELA DECIDIU sobre o gamepad virtual, lido do DISCO.

    É a metade que o daemon calado não responde. ``modo_vivo`` pergunta ao
    ``state_full``: com o daemon fora do ar ele devolve ``None``, e a tela
    ficaria sem ter o que dizer justamente na hora em que a pergunta dela — *"não
    sei se segue desativado"* — é mais aflita.
    """

    #: decidiu. Os três são estados diferentes, e o do meio é o que a automação
    ligado: bool | None
    mascara: str | None
    frase: str


def modo_lembrado() -> Lembranca:
    """O opt-out persistido do gamepad virtual, com a frase da tela."""
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


class Chip(NamedTuple):
    """Um chip da fileira "Modo", do lado Ligado do interruptor."""

    chave: str
    rotulo: str
    ponte: ponte_escada.Ponte | None
    modo: str | None = None
    #: «Sony DualSense» e o «Xbox» têm: são os dois degraus ao vivo da escada, e
    caminho: str | None = None

    @property
    def indice(self) -> int:
        """Posição na ``ponte_escada.ESCADA``, ou ``-1`` se não é degrau."""
        if self.ponte is None:
            return -1
        return ponte_escada.indice_do_degrau(self.ponte)

    @property
    def algarismo(self) -> str:
        """O que iria no círculo — **derivado, nunca digitado**."""
        indice = self.indice
        return SEM_ALGARISMO if indice < 0 else str(indice + 1)


#:   * o chip chamado **"Hefesto"** virou **Sony DualSense** — ele sempre foi
CHIPS_DA_ESCADA: tuple[Chip, ...] = (
    Chip(
        "dualsense",
        "Sony DualSense",
        ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, ponte_escada.MASCARA_DUALSENSE),
        caminho=CAMINHO_DUALSENSE,
    ),
    Chip(
        "xbox",
        "Xbox",
        ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, ponte_escada.MASCARA_XBOX),
        caminho=CAMINHO_XBOX,
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
    Chip(
        "navegacao",
        "Navegação",
        ponte_escada.Ponte(ponte_escada.KIND_DESKTOP),
        modo=MODE_DESKTOP,
    ),
)


class Aviso(NamedTuple):
    """Uma linha da coluna Atenção: o selo, e quem sabe dizer o texto."""

    selo: str
    fonte: Callable[[dict[str, Any] | None], str | None]
    nome: str


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
#: **ELA ENCOLHEU COM A IRMÃ — 11/09/2026, proposta A3-007, aprovada por ela.**
#: A oração de quem conta é a mesma de ``aba01.NATIVO_E_OS_JOGADORES``, e as
#: duas mudaram na mesma linha porque a régua cobra a mesma oração nas duas.
FRASE_DO_MODO_NATIVO = (
    "Conexão Nativa com {quantos} controles ligados: quem conta os jogadores "
    "passa a ser o jogo."
)

#: O SELO DA LINHA ACIMA. ``MODO`` é a palavra do glossário
#: (``docs/A-LINGUA-DESTA-CASA``, §2: *"**Modo**: Jogar pelo Hefesto · Conexão
#: Nativa (Sony) · Controlar o PC"*), e a escada de gravidade que o ordena é
#: ``a01_jogar.ORDEM_DA_GRAVIDADE``.
SELO_DO_MODO = "MODO"


def aviso_do_modo_nativo(state: dict[str, Any] | None) -> str | None:
    """A linha da Conexão Nativa quando há mais de um controle, ou ``None``.

    **SÓ COM DOIS OU MAIS, e o teto é o ponto.** Com um controle só não existe
    pergunta de co-op — a linha seria ruído numa lista de avisos (hoje, a do
    exame da aba Sistema), e um aviso que fala sempre enterra os que falam
    quando dói.

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


def aviso_do_grab_dobrado(state: dict[str, Any] | None) -> str | None:
    """O jogo pode estar recebendo cada botão duas vezes; ``None`` quando não.

    **A CONDIÇÃO NÃO SE REESCREVE:** ela é de `home_actions.aviso_de_grab`, que
    a I9 já tirou do meio do montador de widgets exatamente para ser chamada de
    fora da GTK — ``is_primary and gamepad_on and grab_state == "failed"``. O
    que esta função faz é o que faltava: **ler do ``state`` os três termos** que
    a janela antiga lia dos widgets dela (`home_actions.py:1892` passa
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


FRASE_DA_ORIGEM_DO_MODO = "Quem ligou {modo} foi o perfil ativo, e não um gesto seu."

SEPARADOR_DA_ORIGEM = " · "


def aviso_da_origem_do_modo(state: dict[str, Any] | None) -> str | None:
    """O modo em vigor foi ligado pelo PERFIL, e não por ela; ``None`` se não."""
    if not isinstance(state, dict):
        return None
    partes: list[str] = []
    if state.get("native_mode") and state.get("native_mode_origin") == "profile":
        partes.append(FRASE_DA_ORIGEM_DO_MODO.format(modo=_ROTULO_DO_MODO[MODE_NATIVE]))
    if state.get("mode_from_profile") == "gamepad":
        partes.append(FRASE_DA_ORIGEM_DO_MODO.format(modo=_ROTULO_DO_MODO[MODE_GAMEPAD]))
    return SEPARADOR_DA_ORIGEM.join(partes) if partes else None


RECONECTAR_SEM_SERVICO = (
    "Não consegui falar com o serviço para reconectar os controles — o Hefesto "
    "pode estar desligado."
)


def recibo_do_reconectar(jogadores: object, resultado: object) -> str:
    """O que o passo 2 do "Reconectar Controles" tem a dizer — ou `""`."""
    return _na_lingua_da_tela(resultado)


_NAO_CONFERIU = "Não consegui conferir a numeração dos controles."
_NAO_COMPACTOU = "Não consegui ajustar a numeração dos controles."


#: fora."* <!-- noqa-acento: citação literal dela -->
#: `integrations/gesto_de_reconexao.reconectar`.
_VOLTARAM_PELO_RADIO = "{quantos} controle(s) voltaram pelo rádio."
_ESPERAM_O_PS = (
    "Aperte PS em {quantos} controle(s): o rádio dizia que estavam aqui e o "
    "sistema não os via, e eu derrubei esse elo morto."
)


def recado_do_radio(voltaram: int, esperam_o_ps: int) -> str:
    """O que o passo do rádio conseguiu, em palavras da tela. `""` = nada a dizer.

    **SEM NOTÍCIA, SEM FRASE** — a mesma regra do `recibo_do_reconectar` acima,
    e pela razão dela de 09/09, na grafia dela: *"remover essa frase que
    aparece tambem ao clciar em reconectar controles"*.  # (noqa-acento): dela
    """
    partes = []
    if voltaram > 0:
        partes.append(_VOLTARAM_PELO_RADIO.format(quantos=voltaram))
    if esperam_o_ps > 0:
        partes.append(_ESPERAM_O_PS.format(quantos=esperam_o_ps))
    return " ".join(partes)


def _na_lingua_da_tela(resultado: object) -> str:
    """O desfecho do `identity.renumber` em palavras da tela — só a FALHA fala."""
    if _sem_noticia(resultado):
        return ""
    if not isinstance(resultado, dict):
        return _NAO_CONFERIU
    return _NAO_COMPACTOU


def _sem_noticia(resultado: object) -> bool:
    """Este desfecho do `identity.renumber` fica calado? `True` = nada a contar."""
    if not isinstance(resultado, dict):
        return False
    if not resultado.get("ok"):
        return resultado.get("reason") == "sessao_de_jogo_aberta"
    return True


#: aba Conexões, e o ``state_full`` não publica contagem nem texto de aviso.
AVISOS_DA_TELA: tuple[Aviso, ...] = (
    Aviso("PAUSA", home_actions.texto_da_pausa, "home_actions.texto_da_pausa"),
    Aviso("GAMEPAD", home_actions.vpad_degradation_text, "home_actions.vpad_degradation_text"),
    Aviso("RÁDIO", home_actions.texto_do_radio_fragil, "home_actions.texto_do_radio_fragil"),
    # `aviso_do_wrapper`, e não `wrapper_banner_text`: o segundo responde "há
    Aviso("JOGO", home_actions.aviso_do_wrapper, "home_actions.aviso_do_wrapper"),
    Aviso("PERFIL", home_actions.autoswitch_lock_text, "home_actions.autoswitch_lock_text"),
    Aviso("PERFIL", home_actions.texto_do_cadeado_cego, "home_actions.texto_do_cadeado_cego"),
    Aviso(SELO_DO_MODO, aviso_do_modo_nativo, "painel.aviso_do_modo_nativo"),
    # `mouse.emulation.restore` é o ÚLTIMO dos três IPCs). Uma fonte desta
    Aviso("MODO", home_actions.texto_do_desktop_sem_emulacao,
          "home_actions.texto_do_desktop_sem_emulacao"),
    Aviso("GAMEPAD", aviso_do_grab_dobrado, "painel.aviso_do_grab_dobrado"),
    Aviso("JOGO", home_actions._reconciliar_gate_text,
          "home_actions._reconciliar_gate_text"),
    Aviso("PERFIL", aviso_da_origem_do_modo, "painel.aviso_da_origem_do_modo"),
)


def avisos_do_estado(state: dict[str, Any] | None) -> list[dict[str, str]]:
    """A coluna Atenção de agora: ``[{"selo", "texto", "fonte"}, …]``."""
    fora: list[dict[str, str]] = []
    for aviso in AVISOS_DA_TELA:
        try:
            texto = aviso.fonte(state)
        except Exception as erro:
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


# nome_do_ativo`, que `pacotes.topo()` já chama. Dois leitores do perfil ativo


__all__ = [
    "AVISOS_DA_TELA",
    "CHIPS_DA_ESCADA",
    "ESCRITOR_DOS_MODOS",
    "FRASE_DA_ORIGEM_DO_MODO",
    "FRASE_DO_MODO_NATIVO",
    "MODOS_DA_TELA",
    "MODOS_LIGADOS",
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
    "caminho_vivo",
    "escritor_do_modo",
    "hefesto_ligado",
    "ligado_por_modo",
    "modo_lembrado",
    "modo_vivo",
    "plano_do_modo",
    "porque_nao_aplica",
    "recibo_do_reconectar",
]
