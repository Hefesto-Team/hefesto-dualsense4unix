"""Aba Início — comutador de MODO do sistema + controles + desligar de verdade.

FEAT-GUI-HOME-TAB-01. A primeira aba responde as três perguntas que a interface
antiga espalhava por quatro lugares:

1. "Em que modo o sistema está?" — comutador Desktop / Jogo (gamepad) / Jogo
   nativo, com a máscara (DualSense/Xbox) quando faz sentido. Reflete também o
   modo ligado POR PERFIL (FEAT-PROFILE-MODE-01). LEIGO-01: não há mais toggle
   de co-op — cada controle é um jogador, sempre; a aba só INFORMA quantos.
2. "Quais controles estão conectados?" — um card por controle físico, com
   transporte, jogador (P1/P2…, o número que o JOGO vê — LEIGO-01b), bateria e o
   aviso de grab degradado (input dobrado). LEIGO-02: o fim do MAC saiu do card
   — ela distingue os controles pela COR da luz e pelo LED de jogador, não por
   um hash que não está escrito em lugar nenhum do aparelho.
2b. "Por onde o jogo está recebendo o controle, e a minha escolha chegou?" —
   PONTE-NA-TELA-01, a linha "Ponte com o jogo" e o aviso de divergência de
   máscara, os dois logo abaixo de "O jogo vê o controle como:".
3. "Como desligo o hefesto DE VERDADE?" — botão dedicado que para o daemon e
   NÃO o religa ao reabrir/atualizar a GUI (diferente do "Desligar o Hefesto"
   da aba Sistema, que o `ensure_daemon_running` ressuscitava sem avisar).

Todo widget é montado em código dentro de `tab_home_box` (Glade só reserva o
container) — padrão dos widgets dinâmicos, imune ao bug de popup do cosmic-comp
(botões sempre visíveis, sem dropdown).
"""
from __future__ import annotations

import contextlib
import re
import time
from collections.abc import Sequence
from typing import Any, Final

from hefesto_dualsense4unix.app.actions.base import (
    WidgetAccessMixin,
    numero_do_controle,
)
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_IPC_TIMEOUT_S,
    MODES,
    STATE_IPC_TIMEOUT_S,
    mode_of_state,
)
from hefesto_dualsense4unix.app.actions.relancar import (
    TOAST_ESCOLHA_ANOTADA,
    TOAST_ESCOLHA_DESFEITA,
    texto_do_pendente,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.integrations.steam_launch_options import juntar_rotulos
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

HOME_POLL_INTERVAL_MS = 2000

#: uma chamada que NUNCA volta (daemon morto no meio do `state_full`) o prendia
HOME_INFLIGHT_TIMEOUT_S = 3 * HOME_POLL_INTERVAL_MS / 1000.0

ABA_INICIO = "tab_home_box"


def id_da_pagina(pagina: Any) -> str | None:
    """Id do Glade de uma página do notebook, desembrulhando o rolador."""
    from gi.repository import Gtk

    alvo = pagina
    if isinstance(alvo, Gtk.ScrolledWindow):
        filho = alvo.get_child()
        if isinstance(filho, Gtk.Viewport):
            filho = filho.get_child()
        if filho is not None:
            alvo = filho
    if not isinstance(alvo, Gtk.Buildable):
        return None
    nome = Gtk.Buildable.get_name(alvo)
    return str(nome) if nome is not None else None


def id_da_pagina_corrente(notebook: Any) -> str | None:
    """Id do Glade da página à vista — o que os pollers têm de perguntar."""
    if notebook is None:
        return None
    indice = notebook.get_current_page()
    if not isinstance(indice, int) or indice < 0:
        return None
    return id_da_pagina(notebook.get_nth_page(indice))


_MODE_IPC_TIMEOUT_S = MODE_IPC_TIMEOUT_S

#: `mode_transition` (dono único): a aba Mouse lê o MESMO state_full para saber o
_STATE_IPC_TIMEOUT_S = STATE_IPC_TIMEOUT_S

# DualSense físico, sem intermediário (docs/usage/modos.md).
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Conexão Nativa (Sony)"),
]

# LEIGO-02: "(vibra)"/"(sem vibrar)" eram verdade enquanto a máscara DualSense
_FLAVOR_ITEMS = [
    ("xbox", "Xbox 360"),
    ("dualsense", "DualSense (botões PlayStation)"),
    ("nintendo", "Nintendo Pro (botões da Nintendo)"),
]

_MODE_DESCRIPTIONS = {
    "desktop": (
        "O controle vira mouse/teclado do computador (ajustes na aba "
        "Navegação)."
    ),
    # opções da Steam") existia só para contornar a máscara DualSense que não
    # DualSense de verdade via /dev/uhid, e vibra) — o trade-off morreu com ele,
    "gamepad": (
        "Escolha certa para quase todos os jogos: o Hefesto acende as luzes, "
        "faz o controle vibrar e dá um jogador para cada controle."
    ),
    "native": (
        "Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o "
        "controle."
    ),
}

TEXTO_EM_PAUSA: Final[str] = (
    "O Hefesto está em pausa: nada disto está acontecendo agora — sem luzes, "
    "sem vibração e sem os seus ajustes. O controle segue funcionando nos "
    "jogos como um controle comum. Para voltar, use o atalho do controle "
    "(PS + Options) ou o botão “Retomar”, na aba Sistema."
)


def texto_da_pausa(state: dict[str, Any] | None) -> str | None:
    """O produto está PARADO? — função pura (I4, 25/08/2026)."""
    if not isinstance(state, dict):
        return None
    return TEXTO_EM_PAUSA if state.get("paused") is True else None


_GLOSSARY = (
    "Modo jogo (aba Emulação): pausa só o mouse/teclado, sem soltar o "
    "controle.  ·  "
    'Desligar Hefesto: para tudo até você clicar em "Ligar o Hefesto" aqui '
    "mesmo, nesta aba."
)

_BTN_LABEL_ONLINE = "Desligar Hefesto (voltar ao Linux puro)"
_BTN_LABEL_OFFLINE = "Ligar o Hefesto"


def autoswitch_lock_text(state: dict[str, Any] | None) -> str:
    """Frase do Modo Freestyle ligado — função PURA (UX-05)."""
    if not state or not state.get("freestyle_ligado"):
        return ""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )

    ativo = perfil_que_esta_valendo(state).nome
    alvo = f" — vale o perfil “{ativo}”" if ativo else ""
    return f"Modo Freestyle ligado: o perfil não troca sozinho, nem no jogo{alvo}."


TEXTO_DETECTOR_CEGO: Final[str] = (
    "O Hefesto não está conseguindo ver qual programa está na frente, então o "
    "perfil não vai trocar sozinho de qualquer jeito — isto não é escolha sua. "
    "A aba Sistema diz por quê."
)


def texto_do_cadeado_cego(state: dict[str, Any] | None) -> str:
    """O mecanismo do cadeado está cego? — função PURA (I11, 25/08/2026)."""
    if not isinstance(state, dict) or "window_detect_seeing" not in state:
        return ""
    return "" if state.get("window_detect_seeing") else TEXTO_DETECTOR_CEGO


def _mode_label(mode_id: object) -> str:
    """Rótulo do modo como a usuária o lê no botão (LEIGO-02) — função pura."""
    return dict(_MODE_ITEMS).get(str(mode_id), str(mode_id))


#: Função pura, no padrão de `vpad_degradation_text`, para que a aba Início e
TEXTO_CUSTO_MASCARA_XBOX: Final[str] = (
    "Nesta máscara o jogo não recebe giroscópio, acelerômetro nem touchpad — o "
    "controle de Xbox não tem esses três, então não há onde eles caberem. "
    "Vibração, microfone e alto-falante continuam funcionando. Escolha "
    "DualSense se o jogo usa mira por movimento ou o touchpad como botão."
)


#: dependência**: Xbox e DualSense entregam o mesmo mapa com ou sem a env.
TEXTO_CUSTO_MASCARA_NINTENDO: Final[str] = (
    "Nesta máscara o jogo não recebe giroscópio, acelerômetro nem touchpad, e "
    "os gatilhos L2/R2 chegam como botão — apertado ou solto, sem meio-termo: "
    "o controle da Nintendo não tem gatilho analógico. Abra o jogo pelo "
    "Hefesto: aberto por fora, os quatro botões da frente chegam trocados aos "
    "pares — o X (Cruz) vira Cancelar e o Círculo vira Confirmar —, porque no "
    "controle da Nintendo o confirmar fica à direita, e esta é a única "
    "máscara em que isso acontece. Vibração, microfone e alto-falante "
    "continuam funcionando. Escolha DualSense se o jogo usa mira por "
    "movimento, o touchpad como botão ou aceleração pelo gatilho."
)


def texto_do_custo_da_mascara(flavor: object) -> str:
    """A frase de preço da máscara; ``""`` quando não há preço a dizer."""
    if flavor == "xbox":
        return TEXTO_CUSTO_MASCARA_XBOX
    if flavor == "nintendo":
        return TEXTO_CUSTO_MASCARA_NINTENDO
    return ""


def _flavor_label(flavor_id: object) -> str:
    """Idem para a aparência do controle no jogo ("xbox" → "Xbox 360")."""
    return dict(_FLAVOR_ITEMS).get(str(flavor_id), str(flavor_id))


VPAD_DEGRADED_TEXT = (
    "O gamepad virtual subiu no modo simples: a vibração e a separação do "
    "controle físico não estão garantidas. Reinicie o Hefesto na aba Sistema."
)

VPAD_COOP_DEGRADED_TEXT = (
    "O gamepad virtual de um dos jogadores do co-op subiu no modo simples: "
    "aquele jogador pode ficar sem vibração — e sem controle, se o jogo foi "
    "aberto com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

_COOP_DEGRADED_UM = (
    "O gamepad virtual do Jogador {quem} subiu no modo simples: esse jogador "
    "pode ficar sem vibração — e sem controle, se o jogo foi aberto com a "
    "desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)
_COOP_DEGRADED_VARIOS = (
    "Os gamepads virtuais dos Jogadores {quem} subiram no modo simples: esses "
    "jogadores podem ficar sem vibração — e sem controle, se o jogo foi aberto "
    "com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

_JOGADOR_DEGRADADO_RE = re.compile(r"\bjogador_(\d+)_uinput\b")


def jogadores_degradados(motivo: object) -> list[int]:
    """Números dos jogadores citados no ``dedup_motivo`` — função pura."""
    if not isinstance(motivo, str):
        return []
    vistos: set[int] = set()
    for achado in _JOGADOR_DEGRADADO_RE.finditer(motivo):
        vistos.add(int(achado.group(1)))
    return sorted(vistos)


def texto_coop_degradado(jogadores: Sequence[int]) -> str:
    """Banner do co-op NOMEANDO quem caiu; genérico quando não há número.

    MESA-CHEIA-11/E2 — a entrega mais barata da onda: o dado já viajava no
    `state_full`, e a janela dizia "um dos jogadores" para uma mesa de quatro.
    """
    numeros = [n for n in jogadores if isinstance(n, int) and not isinstance(n, bool)]
    if not numeros:
        return VPAD_COOP_DEGRADED_TEXT
    quem = juntar_rotulos([str(n) for n in numeros])
    molde = _COOP_DEGRADED_UM if len(numeros) == 1 else _COOP_DEGRADED_VARIOS
    return molde.format(quem=quem)


# estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem sem
NATIVE_BT_FRAGIL_TEXT = (
    "Modo Nativo com o controle em Bluetooth: alguns jogos não enxergam o "
    "DualSense por BT (limite do SDL). Se o jogo não vir o controle, use o "
    "cabo USB ou volte para a emulação de gamepad."
)

_NATIVE_BT_FRAGIL_UM = (
    "Modo Nativo com o Controle {quem} em Bluetooth: alguns jogos não o "
    "enxergam (limite do SDL). Se o jogo não vir esse controle, ligue-o no "
    "cabo USB ou volte para a emulação de gamepad."
)
_NATIVE_BT_FRAGIL_VARIOS = (
    "Modo Nativo com os Controles {quem} em Bluetooth: alguns jogos não os "
    "enxergam (limite do SDL). Se o jogo não vir esses controles, ligue-os no "
    "cabo USB ou volte para a emulação de gamepad."
)


def controles_bt_frageis(state: dict[str, Any] | None) -> list[int]:
    """Números dos controles frágeis por BT no Modo Nativo, do ``state_full``.

    MESA-CHEIA-11/E1. Quem decide QUAIS é o daemon
    (`daemon/ipc_handlers.controles_bt_frageis`), porque é ele que enxerga a
    mesa inteira; aqui só se lê a lista publicada, com a mesma defesa dos
    outros leitores de payload.

    **Lista vazia não quer dizer "nenhum frágil"** — quer dizer "não sei quais",
    e é o que um daemon antigo (sem a chave) ou um backend sem
    `describe_controllers` devolve. Por isso quem chama continua olhando também
    o booleano `native_bt_fragil`: o aviso acende, só que sem nomes.

    Ordena de novo o que o daemon já ordenou (`sorted(numeros)`, no fim do
    `daemon/ipc_handlers.controles_bt_frageis`). Não é desconfiança do daemon: é
    que esta é a ÚLTIMA parada antes do olho dela, e a regra "os números saem
    crescentes" tem de valer mesmo quando quem publicou o payload for um daemon
    diferente do que está no fonte de hoje (install editable: o daemon vivo é
    mais velho que o código). Custo: uma ordenação de no máximo quatro números.
    """
    if not isinstance(state, dict):
        return []
    numeros = state.get("native_bt_fragil_controles")
    if not isinstance(numeros, list):
        return []
    return sorted(n for n in numeros if isinstance(n, int) and not isinstance(n, bool))


def texto_native_bt_fragil(numeros: Sequence[int]) -> str:
    """Banner do BT frágil NOMEANDO os controles; genérico sem número."""
    validos = [n for n in numeros if isinstance(n, int) and not isinstance(n, bool)]
    if not validos:
        return NATIVE_BT_FRAGIL_TEXT
    quem = juntar_rotulos([str(n) for n in validos])
    molde = _NATIVE_BT_FRAGIL_UM if len(validos) == 1 else _NATIVE_BT_FRAGIL_VARIOS
    return molde.format(quem=quem)


# `interface/pacotes/perfil.com_a_carona`, que o rodapé das dez abas chama no
WRAPPER_MISSING_TEXT = (
    "O jogo está rodando sem o atalho de inicialização — controles podem "
    "duplicar. Reponho o atalho no próximo Aplicar ou Salvar Perfil, com a "
    "Steam fechada."
)


def wrapper_banner_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner "jogo sem wrapper"; ``None`` quando não há aviso.

    Contrato do `state_full.gamepad_emulation.wrapper_used` (produzido pelo
    daemon cruzando o marker do `hefesto-launch` com a janela steam_app):

    - ``False`` = há jogo aberto E ele NÃO passou pelo wrapper → banner;
    - ``True`` = o jogo abriu pelo wrapper → sem banner;
    - ``None``/ausente = sem jogo aberto, ou daemon antigo sem o campo →
      sem banner (nunca alarme falso por payload incompleto).

    Só o ``False`` LITERAL acende — função pura, consumida pelas abas Início
    e Status (mesmo desenho do `vpad_degradation_text`).
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("wrapper_used") is False:
        return WRAPPER_MISSING_TEXT
    return None


def appid_do_jogo_em_foco(state: dict[str, Any] | None) -> str:
    """O appid da Steam do jogo que está na frente, ou "" — função pura."""
    if not isinstance(state, dict):
        return ""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as _lwd

    classe = state.get("window_detect_current_class") or state.get(
        "window_detect_last_class"
    )
    return _lwd.extract_steam_appid(classe) or ""


def ela_ja_respondeu_sobre(appid: str) -> bool:
    """Ela já disse "eu sei, deixa assim" sobre este jogo? — as DUAS recusas.

    São duas listas e as duas contam, porque as duas são ela dizendo a mesma
    coisa: `launch_dialog_dismissed.json` ("Não perguntar para este jogo") e
    `jogos_sem_wrapper.txt` ("Tirar daqui").

    Best-effort de propósito: qualquer falha de disco devolve ``False`` — na
    dúvida, o aviso aparece. Esconder um aviso por causa de um erro de leitura
    é pior que mostrá-lo duas vezes.

    ELA TOCA O DISCO, E O CUSTO ESTÁ MEDIDO — 06/09/2026, ONDA5-07-03. Duas
    leituras de arquivo por chamada, e quem chama é a pintura da aba Jogar, dez
    vezes por segundo (`jogar/painel.AVISOS_DA_TELA`). A
    `a07_lancadores.calados` avisa, por escrito, que reler duas listas a cada
    tique é *"disco na thread da janela"* — e o número diz que este caminho não
    o sente: **0,050 ms por tique** com os dois arquivos existindo e povoados,
    contra 2,85 ms de mediana do tique inteiro. Duas razões, e as duas são de
    desenho: `aviso_do_wrapper` só chega aqui quando há **jogo aberto sem o
    atalho** (o caso raro), e sem appid a função devolve na primeira linha, sem
    abrir nada. Trocar isto por uma vigia em segundo plano custaria uma thread e
    um TTL para poupar 0,05 ms — e deixaria a Início e a Status, que não têm
    tique, dependendo de um relógio da janela.
    """
    if not appid:
        return False
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as _lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as _slo

    alvo = str(appid)
    with contextlib.suppress(Exception):
        if alvo in {str(a) for a in _lwd.load_dismissed_appids()}:
            return True
    with contextlib.suppress(Exception):
        if alvo in {str(a) for a in _slo.ler_jogos_sem_wrapper()}:
            return True
    return False


def aviso_do_wrapper(state: dict[str, Any] | None) -> str | None:
    """O banner "jogo sem wrapper", CALADO quando ela já respondeu. **UM dono.**

    Nasceu em 05/09/2026, e a razão é um defeito medido: ela dispensava o aviso
    na aba Lançadores e **três outras telas continuavam acusando** — a Início, a
    Status e a coluna Atenção da aba Jogar
    (`app/actions/jogar/painel.py:358`), porque as três chamavam
    `wrapper_banner_text` direto, sem consultar lista nenhuma.

    A decisão dela, 05/09/2026 (pergunta `07-Q3`): *"as duas recusas calam
    tudo"*. E a `a07_lancadores.calados` já dizia, por escrito, que a conta
    precisava de um dono para a outra metade não a redigitar.

    `wrapper_banner_text` continua puro e continua existindo: ele responde
    *"há jogo sem wrapper agora?"*. Esta função responde a pergunta que as telas
    de fato fazem — *"há algo a dizer a ela sobre isso?"* — e é ela que as
    telas chamam.

    O SILÊNCIO MORA AQUI, E NÃO NO PACOTE DA ABA — ONDA5-07-03, 06/09/2026. A
    sprint desenhava a cura como um parâmetro nomeado em
    `jogar/painel.avisos_do_estado`, com a aba Jogar entregando a lista lida
    pela vigia da aba Lançadores. **O caminho que ficou é melhor por uma razão
    medida:** com a conta dentro da função dona, a BANCADA
    (`interface/jogar_vivo.py`, que chama `avisos_do_estado` em dois pontos)
    mede exatamente o que o produto mostra, sem ninguém ter de lembrar de
    passar a lista. Um dublê mais frouxo que a função real já envenenou outro
    arquivo por ordem de teste, em 04/09; um parâmetro que a bancada esquece de
    passar seria a mesma família de defeito.
    """
    texto = wrapper_banner_text(state)
    if texto is None:
        return None
    if ela_ja_respondeu_sobre(appid_do_jogo_em_foco(state)):
        return None
    return texto


def texto_do_radio_fragil(state: dict[str, Any] | None) -> str | None:
    """O aviso de rádio frágil no Modo Nativo, ou ``None``. **UM dono.**

    Extraído de `vpad_degradation_text` em 25/08/2026
    (PERFIS-ABRE-O-QUE-GUARDA-01/§P8) porque ganhou a **segunda** aba: a Perfis
    é quem OFERECE o Modo Nativo (um dos quatro botões do editor) e não dizia
    uma palavra sobre a fragilidade — `native_bt_fragil` tinha leitor num
    arquivo só, medido com `grep -rln` em 24/08. Duas leitoras e uma frase
    escrita duas vezes é exatamente como esta casa ganhou os oito pares da F5;
    então a decisão virou função com nome, e as duas a chamam.

    O comportamento é o mesmo, byte a byte: a LISTA manda quando existe (nomeia
    quem está frágil) e o booleano continua acendendo o aviso genérico, que é o
    que um daemon mais VELHO que esta janela sabe dizer — install editable
    deixa os dois convivendo até o próximo start (MESA-CHEIA-11/E1).
    """
    if not isinstance(state, dict):
        return None
    frageis = controles_bt_frageis(state)
    if frageis or state.get("native_bt_fragil") is True:
        return texto_native_bt_fragil(frageis)
    return None


def vpad_degradation_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner de degradação do vpad; ``None`` quando não há aviso.

    UX-03: o `state_full.gamepad_emulation` expõe `backend` ("uhid" = DualSense
    Edge real com hidraw; "uinput" = fallback sem hidraw). Máscara DualSense no
    backend uinput significa vibração in-game morta e separação do controle
    físico não garantida — sem o banner, a usuária conclui que "o hefesto não
    funciona". Função pura (padrão `_flavor_label`), consumida pelas abas
    Início e Status.

    DEDUP-06 (o guard anti-veneno): o banner também fala pelos jogadores do
    co-op — `dedup_ok=False` com motivo `jogador_N_uinput` acende o aviso
    mesmo com o vpad primário saudável — e pelo estado BT+Nativo
    (`native_bt_fragil` do state_full, hoje acompanhado da lista
    `native_bt_fragil_controles`), que tem aviso próprio e NOMEIA quais.

    Sem alarme falso: backend ausente/"" é transitório real (vpad subindo, o
    `_gamepad_device` ainda None — o `ipc_handlers` só emite a chave com device
    vivo) e NÃO acende o banner; `dedup_motivo="vpad_ausente"` idem (mesmo
    transitório visto pelo guard); máscara xbox em uinput é o desenho normal;
    fora do modo gamepad não há vpad a avaliar.
    """
    if not isinstance(state, dict):
        return None
    do_radio = texto_do_radio_fragil(state)
    if do_radio is not None:
        return do_radio
    if mode_of_state(state) != MODE_GAMEPAD:
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("flavor") != "dualsense":
        return None
    if gamepad.get("degraded") is True:
        return VPAD_DEGRADED_TEXT
    motivo = gamepad.get("dedup_motivo")
    if (
        gamepad.get("dedup_ok") is False
        and isinstance(motivo, str)
        and "jogador" in motivo
    ):
        return texto_coop_degradado(jogadores_degradados(motivo))
    return None


RECONCILIAR_LABEL = "Reconciliar jogadores"

# explicação do que NÃO vai acontecer, com o botão de pé.
RECONCILIAR_JOGO_ABERTO_TEXT = (
    "Com o jogo aberto os jogadores voltam, mas a numeração não muda — "
    "evita repintar o controle em uso no meio da partida."
)


def jogo_com_autoridade(state: dict[str, Any] | None) -> bool:
    """O jogo está com a autoridade de exibição AGORA? — função pura.

    Uma fonte só (``state_full.game_signal.authority == "game"``) para as três
    coisas desta aba que dependem dela: o aviso do "Reconciliar jogadores", o
    motivo da divergência de máscara (PONTE-NA-TELA-01) e o ``_jogo_aberto``
    que a aba Perfis lê. É o MESMO critério que o daemon usa no gate R-04
    (`subsystems/gamepad._recriacao_bloqueada_por_jogo` → `_autoridade_do_jogo`)
    e no handler de ``identity.renumber``: nunca uma segunda fonte da verdade.

    Sinal ausente/desconhecido devolve ``False`` — sem alarme falso.
    """
    if not isinstance(state, dict):
        return False
    game_signal = state.get("game_signal")
    if not isinstance(game_signal, dict):
        return False
    return bool(game_signal.get("authority") == "game")


def _reconciliar_gate_text(state: dict[str, Any] | None) -> str | None:
    """Aviso do "Reconciliar jogadores"; ``None`` = nada a dizer — função pura
    (padrão ``vpad_degradation_text``/``wrapper_banner_text``).

    Espelha o MESMO critério do handler de ``identity.renumber``
    (``display_authority == 'game'`` via ``state_full.game_signal.
    authority``, lido por `jogo_com_autoridade`) — nunca uma segunda fonte da
    verdade; se o daemon ainda não fiou o sinal (``game_signal`` ausente/
    authority desconhecida), não há aviso (sem alarme falso).
    """
    if not isinstance(state, dict):
        return None
    return RECONCILIAR_JOGO_ABERTO_TEXT if jogo_com_autoridade(state) else None


# O daemon fez o certo, e continua fazendo: `mouse.emulation.restore` RESTAURA a
TEXTO_DESKTOP_SEM_MOUSE: Final[str] = (
    "Você está em \"Controlar o PC\", mas o mouse emulado está desligado — o "
    "controle não move o cursor. Ligue \"Emular mouse\" na aba Navegação."
)

TEXTO_DESKTOP_SEM_TECLADO: Final[str] = (
    "Você está em \"Controlar o PC\", mas o teclado emulado está desligado — o "
    "controle não digita. Ligue \"Emular teclado\" na aba Navegação."
)

TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO: Final[str] = (
    "Você está em \"Controlar o PC\", mas o mouse e o teclado emulados estão "
    "desligados — o controle não move o cursor nem digita. Ligue os dois na "
    "aba Navegação."
)


def texto_do_desktop_sem_emulacao(
    state: dict[str, Any] | None,
    *,
    modo_exibido: object = None,
    modo_mudou_agora: bool = False,
) -> str | None:
    """Aviso do "Controlar o PC" calado; ``None`` = nada a dizer — função pura.

    MODO-QUE-NAO-CONTROLA-01. Mesmo desenho de `vpad_degradation_text` e
    `wrapper_banner_text`: quem decide é uma função sem GTK e sem daemon, e a
    aba só escreve o que ela devolve.

    As três condições, e cada uma existe para não acender alarme falso:

    1. **o modo VIGENTE é desktop** (`mode_of_state`) — em "Jogar pelo Hefesto"
       e no Modo Nativo o mouse está desligado pela exclusão mútua do daemon, o
       que é o desenho normal e não tem nada de errado;
    2. **o modo EXIBIDO também é desktop** — com uma escolha pendente de SAIR do
       desktop, avisar sobre o modo que ela está deixando responderia a pergunta
       errada (a caixa mostra a escolha dela, não o vigente: AGORA-E-DEPOIS-01);
    3. **o modo não mudou NESTE tique** — a transição para desktop dispara três
       IPCs e o `mouse.emulation.restore` é o ÚLTIMO deles. Julgar a emulação no
       mesmo tique em que o modo mudou acenderia o aviso enquanto a cura ainda
       está em voo, e ele sumiria sozinho 2 s depois. Um aviso que pisca é
       ruído; este espera um tique e só fala do que ficou de pé.

    Só o ``False`` LITERAL acende, para mouse e teclado: bloco ausente (daemon
    antigo, payload incompleto) ou chave ausente não viram aviso — a mesma
    disciplina do ``wrapper_used``.

    O teclado entra aqui pela mesma razão que o mouse: "Controlar o PC" promete
    mouse E teclado (`_MODE_DESCRIPTIONS["desktop"]`), e o teclado emulado tem
    interruptor próprio na mesma aba Navegação desde a EMULACAO-NO-JOGO-01. A
    diferença é que o "off" do teclado é SEMPRE gesto dela — nenhum caminho
    automático escreve `keyboard_emulation_enabled` (só o boot, lendo o flag
    dela, e o `keyboard.emulation.set`) —, então aqui não há nem a dúvida que o
    mouse tem.
    """
    if not isinstance(state, dict):
        return None
    if modo_mudou_agora:
        return None
    if mode_of_state(state) != MODE_DESKTOP:
        return None
    if modo_exibido is not None and modo_exibido != MODE_DESKTOP:
        return None
    mouse = state.get("mouse_emulation")
    teclado = state.get("keyboard_emulation")
    mouse_off = isinstance(mouse, dict) and mouse.get("enabled") is False
    teclado_off = isinstance(teclado, dict) and teclado.get("enabled") is False
    if mouse_off and teclado_off:
        return TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO
    if mouse_off:
        return TEXTO_DESKTOP_SEM_MOUSE
    if teclado_off:
        return TEXTO_DESKTOP_SEM_TECLADO
    return None


def reconciliar_toast(jogadores: object, resultado_renumber: object) -> str:
    """Frase única do "Reconciliar jogadores" — função pura (06/08/2026)."""
    n = jogadores if isinstance(jogadores, int) and not isinstance(jogadores, bool) else None
    cabeca = (
        f"Jogadores reconciliados — {n} jogador(es)."
        if n is not None
        else "Jogadores reconciliados."
    )
    if not isinstance(resultado_renumber, dict):
        return f"{cabeca} Não consegui conferir a numeração."
    if not resultado_renumber.get("ok"):
        if resultado_renumber.get("reason") == "sessao_de_jogo_aberta":
            return f"{cabeca} A numeração só muda com o jogo fechado."
        return f"{cabeca} Não consegui compactar a numeração."
    renumerados = resultado_renumber.get("renumbered")
    quantos = len(renumerados) if isinstance(renumerados, dict) else 0
    if quantos:
        return f"{cabeca} Numeração compactada em {quantos} controle(s)."
    return f"{cabeca} A numeração já estava compacta."


#    DualSense. O gate R-04 do daemon (`_recriacao_bloqueada_por_jogo`) tinha
#    cai para False e `mode_of_state` chama isso de Controlar o PC — a aba

_COR_OK = "#50fa7b"
_COR_AVISO = "#ffb86c"

#: features do DualSense".
PONTE_PREFIXO = "Ponte com o jogo: "

#: explicação") do `PONTE_PREFIXO` e do detector de janela da aba Sistema.
DIVERGENCIA_PREFIXO = "Sua escolha: "


def _escapar(texto: object) -> str:
    """Escapa markup Pango. Os rótulos de máscara são literais, mas o"""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def mascara_viva(state: dict[str, Any] | None) -> str | None:
    """A máscara que o gamepad virtual VIVO está usando; ``None`` = não sei.

    Duas fontes, nesta ordem:

    1. um campo explícito do daemon, se ele existir. A leitura é por
       ``getattr``/``get`` tolerante porque a lane do daemon publica esse campo
       em paralelo a esta: com um daemon que ainda não o traz, a função
       simplesmente cai no item 2 em vez de estourar;
    2. o ``backend``, que já existe e já é publicado. ``backend == "uhid"``
       implica máscara DualSense e não pode ser outra coisa: o
       `virtual_pad._try_uhid` recusa o uhid para Xbox de saída ("Xbox não é
       trabalho do uhid" — o `hid_playstation` só faz bind em produto Sony).

    ``backend == "uinput"`` é AMBÍGUO de propósito (Xbox normal ou DualSense
    degradado usam o mesmo backend) e devolve ``None``: dizer "não sei" é o
    comportamento honesto, e quem chama trata o ``None`` como "sem divergência
    a afirmar". Enquanto o campo explícito não existir, a divergência é medida
    contra `gamepad_emulation.flavor` — que serve, porque o daemon só grava
    `config.gamepad_flavor` DEPOIS de o vpad novo nascer
    (`subsystems/gamepad.py:1679`); uma troca recusada pelo gate volta com a
    máscara antiga no payload.
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    for chave in ("flavor_vivo", "live_flavor", "flavor_ativo"):
        valor = gamepad.get(chave)
        if isinstance(valor, str) and valor:
            return valor
    if gamepad.get("backend") == "uhid":
        return "dualsense"
    return None


def mascara_do_aparelho(state: dict[str, Any] | None) -> str | None:
    """A máscara que o JOGO vê agora; ``None`` = não sei (offline/sem vpad)."""
    viva = mascara_viva(state)
    if viva:
        return viva
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    valor = gamepad.get("flavor")
    return valor if isinstance(valor, str) and valor else None


FONTE_GESTO_DELA: Final[str] = "gesto"
FONTE_PERFIL: Final[str] = "perfil"

DIVERGENCIA_DO_PERFIL_PREFIXO: Final[str] = "O perfil ativo: "


def mascara_divergente_do_daemon(
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """A divergência que o daemon apontou para o jogo EM CENA; ``None`` se não há."""
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    alarme = gamepad.get("mascara_divergente")
    return alarme if isinstance(alarme, dict) and alarme else None


def texto_da_divergencia(
    escolhida: object,
    no_aparelho: object,
    *,
    jogo_aberto: bool,
    fonte: object = FONTE_GESTO_DELA,
    perfil: object = None,
) -> str | None:
    """A frase da divergência entre o que ela escolheu e o que o jogo vê."""
    if not isinstance(escolhida, str) or not escolhida:
        return None
    if not isinstance(no_aparelho, str) or not no_aparelho:
        return None
    if escolhida == no_aparelho:
        return None
    quero = _escapar(_flavor_label(escolhida))
    tenho = _escapar(_flavor_label(no_aparelho))
    if fonte == FONTE_PERFIL:
        nome = _escapar(perfil) if isinstance(perfil, str) and perfil else None
        quem = f"o perfil “{nome}” pede" if nome else "o perfil ativo pede"
        prefixo = DIVERGENCIA_DO_PERFIL_PREFIXO
    else:
        quem = "você escolheu"
        prefixo = DIVERGENCIA_PREFIXO
    if jogo_aberto:
        return (
            prefixo
            + f'<span foreground="{_COR_AVISO}">ainda não chegou ao '
            f"aparelho</span> — {quem} {quero}; o jogo aberto ainda vê "
            f"{tenho}. Trocar agora arrancaria o controle do jogo no meio da "
            "partida, então a escolha vale quando o jogo fechar e abrir "
            "de novo."
        )
    return (
        prefixo
        + f'<span foreground="{_COR_AVISO}">não chegou ao aparelho</span> — '
        f"{quem} {quero}; o Hefesto está com {tenho}. Escolha de novo."
    )


def controles_na_mesa(state: dict[str, Any] | None) -> int:
    """Quantos controles CONECTADOS o daemon reporta — função pura."""
    if not isinstance(state, dict):
        return 0
    entradas = state.get("controllers") or []
    return len(
        [c for c in entradas if isinstance(c, dict) and c.get("connected")]
    )


def texto_da_ponte(state: dict[str, Any] | None) -> str:
    """Markup da linha "Ponte com o jogo" — função pura, voz da aba Sistema.

    Responde a pergunta que a janela inteira não respondia: **por onde o jogo
    está recebendo o controle agora?** A ordem das perguntas é a ordem em que
    uma resposta invalida a seguinte:

    1. sem daemon não há o que afirmar (mesma disciplina do `autoswitch_lock_
       text`: offline é "não sei", nunca "nenhuma");
    2. Modo Nativo — o físico vai para o jogo e o Hefesto não está no caminho;
    3. gamepad do Hefesto, dizendo QUAL máscara o jogo vê — e, com a mesa
       vazia, dizendo que a ponte está de pé e sem quem a atravesse;
    4. nenhuma — e aí a frase aponta o botão que constrói uma.

    ERAM CINCO, e a segunda saiu — I6, ramo 2, 25/08/2026
    -----------------------------------------------------

    A pergunta que saiu era *"exceção de Steam Input com o vpad suspenso"*, e a
    frase dela dizia: *"pelo Steam Input — neste jogo a Steam entrega os botões,
    e o Hefesto segue cuidando dos gatilhos, da cor e da vibração."* Ela nunca
    apareceu na tela, e não pode voltar como estava. Três medições, nesta ordem:

    1. **A condição é inalcançável** — `VPAD-SUSPENSO-MORTO-01`/E1, MEDIDO em
       25/08/2026: `daemon._steam_input_vpad_suspenso` só anda para `False`
       desde o commit `d8022ea` (09/08/2026), e esta era uma das CINCO leituras
       de produção de um valor impossível. O portão que guarda o achado é
       `tests/unit/test_portao_o_par_com_metade_ligada.py`.
    2. **Trocar a condição por `excecao_ativa` sozinho — a saída recomendada
       para o PAR — publicaria aqui uma frase que a medição derruba.** Desde a
       `ESCONDER-EM-VEZ-DE-SAIR-01` (09/08/2026, decisão dela: *a allowlist do
       Steam Input NÃO tira o Hefesto da frente*), a exceção **esconde o
       físico** (`esconder_o_fisico_para_o_jogo`) e **mantém o vpad de pé**. Ou
       seja: na exceção quem alimenta o jogo continua sendo o gamepad do
       Hefesto — o oposto do que a frase dizia.
    3. **E há medição em jogo, não só leitura de código** —
       `docs/protocol/pilha-steam-input-xpad-sdl.md`, §2.4-bis, MEDIDO em
       11/08/2026 com um appid da allowlist DELA em sessão: **zero espelhos**
       da Steam no sistema, os dois vpads do Hefesto de pé, quatro controles
       com jogador e vibração, e o aceite dela. A Steam não estava entregando
       botão nenhum.

    Logo, com a exceção ativa, a resposta verdadeira é a da terceira pergunta —
    que é a que a aba já dá. **Silêncio aqui não é buraco:** quem tem a fita da
    exceção de Steam Input é a aba Emulação (`markup_status_steam_input`), e é
    lá que ela é nomeada.

    O que fica em aberto, e é DELA: se a Início deve NOMEAR a exceção (algo
    como "…e a Steam está no meio neste jogo"). É texto novo na primeira tela,
    e texto de tela é palavra dela — PROVA-DE-TELA-01.
    """
    if not isinstance(state, dict):
        return PONTE_PREFIXO + "não sei — o Hefesto está desligado."
    if state.get("native_mode"):
        return (
            PONTE_PREFIXO
            + f'<span foreground="{_COR_OK}">direto (Sony)</span> — o jogo fala '
            "com o DualSense sem o Hefesto no meio."
        )
    gamepad = state.get("gamepad_emulation")
    if isinstance(gamepad, dict) and gamepad.get("enabled"):
        # atravesse. MEDIDO na bancada de 23/08 com ZERO DualSense na casa: o
        if not controles_na_mesa(state):
            return (
                PONTE_PREFIXO
                + f'<span foreground="{_COR_AVISO}">de pé, e vazia</span> — o '
                "gamepad do Hefesto está montado, e não há nenhum controle "
                "ligado para alimentá-lo. Ligue um controle para o jogo "
                "receber alguma coisa."
            )
        no_aparelho = mascara_do_aparelho(state)
        visto = (
            _escapar(_flavor_label(no_aparelho)) if no_aparelho else "um controle"
        )
        return (
            PONTE_PREFIXO
            + f'<span foreground="{_COR_OK}">pelo Hefesto</span> — o jogo '
            f"recebe o controle do gamepad do Hefesto, e o vê como {visto}."
        )
    return (
        PONTE_PREFIXO
        + f'<span foreground="{_COR_AVISO}">nenhuma</span> — nenhum jogo está '
        'recebendo controle do Hefesto. Escolha "Jogar pelo Hefesto" para o '
        "jogo ver um controle."
    )


DESFECHO_APLICADO = "aplicado"
DESFECHO_JA_ESTAVA = "ja_estava"
DESFECHO_BLOQUEADO = "bloqueado_por_jogo"
DESFECHO_FALHOU = "falhou"
DESFECHO_INCERTO = "incerto"

_ALIASES_DE_DESFECHO = {
    "aplicado": DESFECHO_APLICADO,
    "applied": DESFECHO_APLICADO,
    "ja_estava": DESFECHO_JA_ESTAVA,
    "já_estava": DESFECHO_JA_ESTAVA,
    "already": DESFECHO_JA_ESTAVA,
    "no_op": DESFECHO_JA_ESTAVA,
    "bloqueado_por_jogo": DESFECHO_BLOQUEADO,
    "blocked_by_game": DESFECHO_BLOQUEADO,
    "recusado_por_jogo": DESFECHO_BLOQUEADO,
    "adiado_jogo_aberto": DESFECHO_BLOQUEADO,
    "falhou": DESFECHO_FALHOU,
    "failed": DESFECHO_FALHOU,
}


def desfecho_da_troca(resultado: Any, *, pedida: object = None) -> str:
    """Desfecho de um ``gamepad.emulation.set`` — função pura.

    A raiz do defeito 1 é que `set_gamepad_emulation` devolve **True** para
    três desfechos diferentes (apliquei / já estava / recusei pelo gate R-04) e
    o handler traduz isso em ``status: "ok"``. Quem chamava lia o "ok" e
    anunciava sucesso sobre uma recusa.

    A leitura tem duas camadas, e a segunda é o que faz esta cura valer HOJE,
    sem esperar o daemon:

    1. o campo distinguível, quando o payload o traz (``desfecho``/``outcome``,
       nos aliases acima). É o contrato que a outra lane está montando; aqui
       ele é consumido defensivamente — chave ausente não é erro;
    2. a **máscara devolvida**. O handler já responde ``flavor: config.
       gamepad_flavor``, e o daemon só grava esse campo DEPOIS de o vpad novo
       nascer: uma troca recusada volta com a máscara ANTIGA. Comparar o que
       voltou com o que foi pedido separa "aplicou" de "não aplicou" com o
       payload que já existe. Era só ninguém olhar para o campo.

    ``incerto`` é devolvido quando nada disso está disponível — e quem chama
    tem de escolher uma frase que não afirme sucesso.
    """
    if not isinstance(resultado, dict):
        return DESFECHO_INCERTO
    for chave in ("desfecho", "outcome"):
        bruto = resultado.get(chave)
        if isinstance(bruto, str) and bruto:
            conhecido = _ALIASES_DE_DESFECHO.get(bruto.strip().lower())
            if conhecido is not None:
                return conhecido
    if resultado.get("status") == "failed":
        return DESFECHO_FALHOU
    devolvida = resultado.get("flavor")
    if isinstance(pedida, str) and pedida and isinstance(devolvida, str) and devolvida:
        return DESFECHO_APLICADO if devolvida == pedida else DESFECHO_BLOQUEADO
    return DESFECHO_INCERTO


def toast_da_troca_de_mascara(desfecho: str, pedida: object) -> str:
    """A frase do rodapé para cada desfecho — função pura."""
    alvo = _flavor_label(pedida)
    if desfecho == DESFECHO_BLOQUEADO:
        return (
            f"Ainda não: o jogo aberto está com o controle. {alvo} vale quando "
            "o jogo fechar e abrir de novo."
        )
    if desfecho == DESFECHO_JA_ESTAVA:
        return f"Nada a mudar — o jogo já via: {alvo}"
    if desfecho == DESFECHO_FALHOU:
        return f"Não consegui trocar para {alvo} — o jogo continua como estava."
    if desfecho == DESFECHO_INCERTO:
        return f"Pedi a troca para {alvo} — confira em “Ponte com o jogo”."
    return f"O jogo agora vê: {alvo}"


#: minúsculo. Escreva: Cabo ou BT"*; <!-- noqa-acento: citação literal dela -->
#: existia para escolher uma. Ela escolheu.
_PALAVRA_DO_TRANSPORTE: Final[dict[str, str]] = {
    "usb": "USB",
    "cabo": "USB",
    "bt": "BT",
    "bluetooth": "BT",
    "radio": "BT",
    "rádio": "BT",
}

PALAVRA_DE_TRANSPORTE_DESCONHECIDO: Final[str] = "não sei por onde"


def palavra_do_transporte(transporte: object) -> str:
    """O transporte na língua do mapa de canais — função pura (I9)."""
    if transporte is None or transporte == "":
        return PALAVRA_DE_TRANSPORTE_DESCONHECIDO
    bruto = str(transporte).strip()
    return _PALAVRA_DO_TRANSPORTE.get(bruto.lower(), bruto)


#:    bancada em 25/08/2026: o `hide` do broker age em UMA superfície
#: CLASSE DE TELA: ESTRUTURAL — frase reescrita, e um hover onde não havia.
AVISO_DE_GRAB_LINHA: Final[str] = "O jogo pode receber cada botão duas vezes"

AVISO_DE_GRAB_PORQUE: Final[str] = (
    "Outro programa pegou este controle antes e não solta, então o Hefesto não "
    "conseguiu ficar com ele só para si. Enquanto isso durar, o jogo pode "
    "enxergar o controle físico E o do Hefesto ao mesmo tempo. O Hefesto tenta "
    "de novo sozinho a cada 2 segundos; se o aviso não sair, feche os outros "
    "programas que usam controle e ligue o Hefesto de novo."
)


def aviso_de_grab(
    grab_state: object, *, is_primary: bool, gamepad_on: bool
) -> tuple[str, str] | None:
    """A linha e o porquê do aviso de duplicação — função pura (I9).

    Devolve ``(linha, porquê)`` ou ``None`` quando não há o que avisar. A
    CONDIÇÃO mora aqui junto do texto de propósito: ela é a parte que já estava
    certa (`is_primary and gamepad_on and grab_state == "failed"`) e tirá-la do
    meio do montador de widgets é o que torna a frase testável sem GTK.

    Só ``"failed"`` acende. ``"pending"`` é o estado de quem ainda não abriu o
    dispositivo — acender ali seria alarme na partida inteira de quem acabou de
    ligar o controle. E o aviso é do PRIMÁRIO com o gamepad de pé: sem gamepad
    do Hefesto no caminho não há segundo dispositivo para dobrar com o físico.
    """
    if not is_primary or not gamepad_on:
        return None
    if grab_state != "failed":
        return None
    return AVISO_DE_GRAB_LINHA, AVISO_DE_GRAB_PORQUE


def _format_controller_subtitle(
    transport: object, *, is_primary: bool, battery_pct: object
) -> str:
    """Linha secundária do card de controle (função pura — testável sem GTK).

    FEAT-STATE-PER-CONTROLLER-01: acrescenta a bateria ("· 87%") quando o
    daemon a reportou para ESTE controle; None/ausente fica de fora (nada de
    "0%" falso em controle recém-plugado). `bool` é rejeitado (subclasse de
    int) por blindagem contra payload malformado.
    """
    parts = [palavra_do_transporte(transport)]
    if is_primary:
        parts.append("primário")
    if isinstance(battery_pct, int) and not isinstance(battery_pct, bool):
        parts.append(f"{battery_pct}%")
    return "  ·  ".join(parts)


def _format_external_title(entry: dict[str, Any]) -> str:
    """Título do card de um externo — "Controle 3 — 8BitDo" (I5, 25/08/2026)."""
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        brand_of,
        slot_label,
        slot_of,
    )

    slot = slot_of(entry, 0, 0)
    marca = brand_of(entry)
    return f"Controle {slot_label(slot)} — {marca}"


def _format_external_subtitle(entry: dict[str, Any]) -> str:
    """Linha secundária do card de um externo, no MESMO formato do adotado.

    Mesma pontuação e mesmo vocabulário de transporte do card do DualSense — é
    o mesmo frame, e dois dialetos lado a lado é o defeito de forma que a I9
    fecha. A segunda metade diz o que o Hefesto NÃO faz com este aparelho, que
    é a informação que a pessoa procura ao ver um controle que não acende.

    PROVISÓRIO — decisão dela.
    """
    bus = entry.get("bus")
    return "  ·  ".join([palavra_do_transporte(bus), "o Hefesto só vê"])


def externos_na_mesa(
    state: dict[str, Any] | None, cache: Sequence[dict[str, Any]] = ()
) -> list[dict[str, Any]]:
    """Os controles que o Hefesto VÊ e não adota — I5 (25/08/2026).

    Duas fontes, nesta ordem, e a primeira é a que a foto usa:

    1. ``state_full["external"]``, quando o payload o trouxer. **Medido por
       leitura de código em 25/08/2026: o `daemon.state_full` de HOJE não
       publica essa chave** — ela existe só na resposta de ``controller.list
       {"external": true}``. Isto resolve a hipótese 3 do §2.5 da sprint ("o
       daemon publica `external` quando há um externo na mesa?"): **não
       publica**, e o `external=null` medido na bancada não distinguia as duas
       coisas porque a chave nunca existiu ali. O ramo fica porque é por ele
       que o dublê da foto alimenta a aba, e porque um daemon mais novo que
       passe a publicá-la é atendido sem uma linha a mais;
    2. o inventário que a própria aba pediu ao daemon no tique lento
       (``_maybe_fetch_externos``), que é como a aba Configurações e a aba
       Status já fazem — a enumeração de evdev mais a sonda de holders custa
       10-40 ms e um subprocess, e não pode entrar no caminho quente.

    Lista vazia é "não há" **ou** "ainda não perguntei", e quem chama trata as
    duas do mesmo jeito: não desenha card nenhum. A diferença só importaria
    para acusar ausência, e esta aba não acusa.
    """
    if isinstance(state, dict):
        do_payload = state.get("external")
        if isinstance(do_payload, list):
            return [e for e in do_payload if isinstance(e, dict)]
    return [e for e in (cache or ()) if isinstance(e, dict)]


def _format_players_hint(
    controllers: list[dict[str, Any]],
    externos: Sequence[dict[str, Any]] = (),
) -> str:
    """Frase que substituiu o checkbox de co-op (LEIGO-01) — função pura.

    Só fala quando há o que dizer: com um controle só não existe pergunta a
    responder. E só afirma "N jogadores" quando o daemon de fato numerou N
    jogadores distintos (campo `player`) — enquanto o segundo jogador não subiu,
    o jogo ainda vê um gamepad só e a frase seria mentira.

    I5 (25/08/2026) — A CONTA PASSOU A CONTAR QUEM ESTÁ NA MESA
    ------------------------------------------------------------

    A Início não lia ``external`` e não desenhava um único controle externo
    (§2.2g da sprint). Com dois DualSense e um 8BitDo na mesa, esta aba dizia
    "2 controles = 2 jogadores" enquanto a aba Configurações mostrava TRÊS
    cards. Era a pergunta dela — *"o produto funciona com 4 controles ao mesmo
    tempo?"* — respondida com **não, a primeira tela nem os enxerga**.

    A frase distingue os dois grupos, e a distinção NÃO é cosmética: o §6 desta
    sprint proíbe somar o externo na conta de jogadores sem qualificar,
    porque ``plataforma.vpad@sn30`` está em ``existe: desconhecido`` no mapa de
    canais. O que se afirma é o que se mediu — quantos estão na mesa, e quais
    o Hefesto adotou.

    PROVISÓRIO — decisão dela: o texto exato é palavra dela (PROVA-DE-TELA-01).
    """
    validos = [e for e in externos if isinstance(e, dict)]
    players = {
        c.get("player")
        for c in controllers
        if isinstance(c.get("player"), int) and not isinstance(c.get("player"), bool)
    }
    if validos:
        total = len(controllers) + len(validos)
        if total < 2:
            return ""
        quantos_veem = (
            f"{len(validos)} que ele só vê"
            if len(validos) > 1
            else "1 que ele só vê"
        )
        pelo_hefesto = (
            f"{len(controllers)} pelo Hefesto ({len(players)} jogadores)"
            if len(players) >= 2
            else f"{len(controllers)} pelo Hefesto"
        )
        return f"{total} controles ligados: {pelo_hefesto} e {quantos_veem}"
    if len(controllers) < 2:
        return ""
    if len(players) < 2:
        return ""
    return f"{len(controllers)} controles = {len(players)} jogadores"


# acima, e a contagem vem do `daemon.state_full` (campo `player` por controle,


def _format_controller_title(entry: dict[str, Any]) -> str:
    """Título do card: "Controle 2 — P3" (função pura)."""
    name = f"Controle {numero_do_controle(entry)}"
    player = entry.get("player")
    if isinstance(player, int) and not isinstance(player, bool):
        return f"{name} — P{player}"
    return name


# `tests/unit/test_perfil_salva_tudo_registrar_nao_e_aplicar.py`, por AST, para


def _coop_do_rascunho(draft: DraftConfig | None) -> bool | None:
    """O ``coop`` que o perfil de origem já dizia, ou ``None`` se ele não diz."""
    if draft is None:
        return None
    origem = draft.source_mode
    if origem is None:
        return None
    valor = (
        origem.get("coop")
        if isinstance(origem, dict)
        else getattr(origem, "coop", None)
    )
    return bool(valor) if isinstance(valor, bool) else None


def rascunho_com_modo(
    draft: DraftConfig | None,
    *,
    kind: str,
    flavor: object = None,
) -> DraftConfig | None:
    """Rascunho com o MODO dela registrado. Pura: NÃO aplica nada (E3)."""
    if draft is None or kind not in MODES:
        return draft
    from hefesto_dualsense4unix.profiles.schema import (
        ProfileModeConfig,
        normalizar_gamepad_flavor,
    )

    secao: dict[str, Any] = {"kind": kind}
    if kind == MODE_GAMEPAD:
        secao["gamepad_flavor"] = normalizar_gamepad_flavor(flavor)
    efetivo = _coop_do_rascunho(draft)
    if efetivo is not None:
        secao["coop"] = efetivo
    return draft.with_mode(ProfileModeConfig.model_validate(secao))


def reconciliar_pendente(janela: Any) -> dict[str, str]:
    """A escolha dela MENOS o que o daemon já alcançou. Devolve o que sobra."""
    pendente = dict(getattr(janela, "_escolha_pendente", None) or {})
    if "modo" in pendente and pendente["modo"] == getattr(
        janela, "_modo_vigente_do_daemon", None
    ):
        pendente.pop("modo")
    # máscara, o chip «Xbox» com o cartão em DualSense deixava na linha um
    if "caminho" in pendente and pendente["caminho"] == getattr(
        janela, "_caminho_vigente_do_daemon", None
    ):
        pendente.pop("caminho")
    if "mascara" in pendente and pendente["mascara"] == getattr(
        janela, "_mascara_vigente_do_daemon", None
    ):
        pendente.pop("mascara")
    janela._escolha_pendente = pendente or None
    return pendente


def render_pendente(janela: Any, *, visivel: bool = True) -> None:
    """Escreve (ou apaga) a linha do que ela escolheu e ainda não aplicou."""
    pendente = reconciliar_pendente(janela)
    label = getattr(janela, "_home_pendente_label", None)
    if label is None:
        return
    texto = texto_do_pendente(
        modo=_mode_label(pendente["modo"]) if "modo" in pendente else None,
        mascara=(
            _flavor_label(pendente["mascara"]) if "mascara" in pendente else None
        ),
    )
    if texto:
        label.set_text(texto)
    label.set_visible(visivel and bool(texto))


def marcar_escolha(janela: Any, campo: str, valor: str) -> None:
    """Grava a escolha dela — e **não aplica nada**.

    AGORA-E-DEPOIS-01. Este é o passo 2 do plano, e a coisa que ela NÃO faz é a
    entrega: nenhum IPC sai daqui. Quem aplica é o "Aplicar" do rodapé, que é
    onde a mudança sai — e é lá que o diálogo de relançamento pergunta UMA vez,
    em vez de a cada clique de seletor.
    """
    pendente = dict(getattr(janela, "_escolha_pendente", None) or {})
    pendente[campo] = valor
    janela._escolha_pendente = pendente
    render_pendente(janela)
    ficou = bool(getattr(janela, "_escolha_pendente", None))
    toast = getattr(janela, "_status_toast", None)
    if callable(toast):
        toast("home", TOAST_ESCOLHA_ANOTADA if ficou else TOAST_ESCOLHA_DESFEITA)


def registrar_modo_no_rascunho(
    janela: Any, kind: str, flavor: object = None
) -> None:
    """Anota na janela o modo que ela acabou de aplicar. Único ponto de escrita."""
    draft = getattr(janela, "draft", None)
    if draft is None:
        return
    novo = rascunho_com_modo(draft, kind=kind, flavor=flavor)
    if novo is not None:
        janela.draft = novo


def lembrar_mascara_recusada(janela: Any, mascara: object) -> None:
    """Guarda a máscara que ela pediu e o daemon NÃO entregou. Escritor único.

    INÍCIO NÃO MENTE-01 / I2 (25/08/2026). O campo ``_home_flavor_pedido``
    existe desde a PONTE-NA-TELA-01 e é a ÚNICA memória de um pedido que o
    daemon recusou — e, medido no §2.2c da sprint, **ninguém o escrevia com
    valor**: em ``src/`` havia só o nascimento (``= None``) e a limpeza
    (``= None``), e os únicos escritores de verdade eram quatro linhas de
    teste.

    O preço na tela era exato: o ``_render_home`` reescreve o seletor com o
    valor do daemon a cada 2 s, então a escolha recusada dela sumia da tela em
    dois segundos, sem uma palavra — e a linha de divergência, que é quem a
    contaria, não tinha o que ler.

    Função de MÓDULO, e não método de mixin, pelas três razões já pagas por
    esta base em ``registrar_modo_no_rascunho`` e
    ``recolher_escolha_pendente_no_rascunho``: dois mixins da mesma classe se
    sombreariam pela MRO; chamada entre mixins quebra dublê PARCIAL de teste; e
    quem chama é o RODAPÉ, que não é a aba dona do campo — se ele o escrevesse
    por conta própria seria o segundo escritor.

    Só grava máscara de verdade: ``None``, ``""`` ou não-texto não viram
    pedido. Um pedido vazio acenderia a divergência contra nada.
    """
    if not isinstance(mascara, str) or not mascara:
        return
    janela._home_flavor_pedido = mascara
    logger.info("home_lembrou_mascara_recusada", mascara=mascara)


def recolher_escolha_pendente_no_rascunho(janela: Any) -> dict[str, str] | None:
    """Leva ao rascunho o que ela marcou na Início e ainda não aplicou.

    A-INICIO-TAMBEM-SALVA-01 (10/08/2026), pedido dela, literal:

        *"eu ir de uma aba pra outra depois de alterar todas as anteriores mas
        eu clicar em salvar somente na última. ele vai salvar na última aba
        todas as informações passadas."*

    MEDIDO na bancada em 10/08: com UM "Salvar Perfil" no fim, sete das oito
    abas chegavam ao arquivo. Falhava só a Início. A razão é a AGORA-E-DEPOIS-01
    (08/08): clicar no seletor de modo deixou de aplicar e passou a só MARCAR a
    escolha em ``_escolha_pendente``, e o único caminho de lá até o rascunho era
    o callback de sucesso do botão VERDE
    (``footer_actions._aplicar_escolha_pendente``). Quem salvasse sem o verde
    gravava ``mode: null`` em cima do que acabara de escolher — a queixa do
    ``pragmata2.json``, pela última porta que ainda estava aberta.

    **REGISTRAR NÃO É APLICAR** (HARM-05), e aqui a linha é mais fina do que de
    costume, então fica escrita: daqui não sai IPC nenhum. Este recolhimento
    prepara o que vai para o DISCO; quem muda a máquina continua sendo o verde,
    e só ele. Pela mesma razão a pendência **não é limpa**: ela descreve o que o
    daemon ainda não alcançou, e depois de um Salvar isso continua verdadeiro.

    O DEGRAU DE TRÁS do ``kind`` é a MESMA expressão do "Aplicar"
    (``footer_actions._aplicar_escolha_pendente``): a escolha dela, ou o vigente
    do daemon quando ela mexeu só na máscara. Duas leituras do mesmo fato não
    podem discordar. E **sem nenhum dos dois não se escreve nada**: o esquema não
    aceita máscara sem ``kind`` (``profiles/schema.ProfileModeConfig``), mas
    carimbar um default nosso aqui criaria um SEGUNDO dono do valor — o defeito
    que a AUTO-01.3 enterrou. Falha para o lado de não inventar.

    Função de MÓDULO e delegando ao escritor único pelas duas razões já pagas
    por esta base (ver ``registrar_modo_no_rascunho``): dois mixins na mesma
    classe se sombreariam pela MRO, e chamada entre mixins quebra dublê PARCIAL
    de teste. Aqui vale uma terceira: quem chama é o RODAPÉ, que não é a aba
    dona do modo — se ele escrevesse o rascunho por conta própria seria o
    segundo escritor que o portão de AST existe para impedir.

    Devolve o que FOI registrado — ``{"modo": ...}`` mais ``"mascara"`` quando
    há —, ou ``None`` quando não havia nada a recolher. O rodapé usa isso para
    o toast dizer a verdade sobre o que acabou de acontecer; e o que se devolve
    é lido **de volta do rascunho**, nunca do que se pediu, porque só o rascunho
    sabe o que sobreviveu à normalização (máscara fora do modo gamepad, por
    exemplo, é descartada por ``rascunho_com_modo``).
    """
    pendente = dict(getattr(janela, "_escolha_pendente", None) or {})
    if not pendente:
        return None
    kind = pendente.get("modo") or getattr(janela, "_modo_vigente_do_daemon", None)
    if not kind:
        logger.info("salvar_recolhe_pendencia_sem_modo_conhecido")
        return None
    flavor = pendente.get("mascara") or getattr(
        janela, "_mascara_vigente_do_daemon", None
    )
    antes = getattr(janela, "draft", None)
    registrar_modo_no_rascunho(janela, kind, flavor)
    depois = getattr(janela, "draft", None)
    if depois is antes:
        return None
    secao = getattr(depois, "source_mode", None)
    registrado: dict[str, str] = {"modo": str(getattr(secao, "kind", "") or "")}
    sabor = getattr(secao, "gamepad_flavor", None)
    if sabor:
        registrado["mascara"] = str(sabor)
    logger.info("salvar_recolheu_pendencia", **registrado)
    return registrado


class HomeActionsMixin(WidgetAccessMixin):
    """Mixin da aba Início (página 0 do notebook)."""

    _home_opt_out_cache: bool = False

    def install_home_tab(self) -> None:
        """Monta o conteúdo dinâmico da aba Início. Idempotente."""
        from gi.repository import GLib, Gtk

        box = self._get("tab_home_box")
        if box is None or getattr(self, "_home_installed", False):
            return
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False
        self._escolha_pendente = None
        # `_modo_vigente_do_daemon`, que a aba Perfis já usava.
        self._mascara_vigente_do_daemon: str | None = None
        self._home_inflight_since = 0.0
        # AVISO-VIVO-01: última frase de ESTADO que o rodapé recebeu desta aba.
        self._home_lock_toast: str | None = None
        self._home_externos = []
        self._home_externos_ts = 0.0
        self._home_externos_inflight = False

        # `gamepad_emulation.backend` do state_full (`vpad_degradation_text`).
        vpad_banner = Gtk.Label(label="")
        vpad_banner.set_xalign(0.0)
        vpad_banner.set_line_wrap(True)
        vpad_banner.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        vpad_banner.set_no_show_all(True)
        vpad_banner.set_visible(False)
        self._home_vpad_banner = vpad_banner
        box.pack_start(vpad_banner, False, False, 0)

        # `aviso_de_opt_out_antigo`.
        opt_out_banner = Gtk.Label(label="")
        opt_out_banner.set_xalign(0.0)
        opt_out_banner.set_line_wrap(True)
        opt_out_banner.set_max_width_chars(96)
        opt_out_banner.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        opt_out_banner.set_no_show_all(True)
        opt_out_banner.set_visible(False)
        self._home_opt_out_banner = opt_out_banner
        box.pack_start(opt_out_banner, False, False, 0)

        # `gamepad_emulation.wrapper_used` do state_full (`wrapper_banner_text`).
        wrapper_banner = Gtk.Label(label="")
        wrapper_banner.set_xalign(0.0)
        wrapper_banner.set_line_wrap(True)
        wrapper_banner.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        wrapper_banner.set_no_show_all(True)
        wrapper_banner.set_visible(False)
        self._home_wrapper_banner = wrapper_banner
        box.pack_start(wrapper_banner, False, False, 0)


        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        frame_mode = Gtk.Frame(label="Quando o jogo abrir")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_box.set_margin_top(10)
        mode_box.set_margin_bottom(10)
        mode_box.set_margin_start(12)
        mode_box.set_margin_end(12)

        # Perdê-la deixaria as quatro órfãs; aqui ela continua nomeando
        modo_label = Gtk.Label(label="O que o controle faz agora:")
        modo_label.set_xalign(0.0)
        mode_box.pack_start(modo_label, False, False, 0)

        selector = SegmentedSelector(wrap=True)
        selector.set_items(_MODE_ITEMS)
        selector.connect("changed", self._on_home_mode_changed)
        self._home_mode_selector = selector
        mode_box.pack_start(selector, False, False, 0)

        desc = Gtk.Label(label="")
        desc.set_xalign(0.0)
        desc.set_line_wrap(True)
        desc.get_style_context().add_class("dim-label")
        self._home_mode_desc = desc
        mode_box.pack_start(desc, False, False, 0)

        desktop_aviso = Gtk.Label(label="")
        desktop_aviso.set_xalign(0.0)
        desktop_aviso.set_line_wrap(True)
        desktop_aviso.set_max_width_chars(100)
        desktop_aviso.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        desktop_aviso.set_no_show_all(True)
        desktop_aviso.set_visible(False)
        self._home_desktop_aviso = desktop_aviso
        mode_box.pack_start(desktop_aviso, False, False, 0)

        # seletor a largura toda para os 2 botões.
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # personagem, então não existe escolha a oferecer — cada controle é um
        players_hint = Gtk.Label(label="")
        players_hint.set_xalign(0.0)
        players_hint.set_line_wrap(True)
        players_hint.get_style_context().add_class("dim-label")
        self._home_players_hint = players_hint
        opts.pack_start(players_hint, False, False, 0)

        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor = SegmentedSelector(wrap=True)
        flavor.set_items(_FLAVOR_ITEMS)
        flavor.connect("changed", self._on_home_flavor_changed)
        self._home_flavor_selector = flavor
        mask_row.pack_start(flavor, True, True, 0)
        opts.pack_start(mask_row, False, False, 0)

        # MASCARA-CUSTO-01 (01/08): o preço da máscara, dito ANTES do clique.
        custo = Gtk.Label(label="")
        custo.set_xalign(0.0)
        custo.set_line_wrap(True)
        custo.set_max_width_chars(100)
        custo.get_style_context().add_class("dim-label")
        self._home_flavor_custo = custo
        opts.pack_start(custo, False, False, 0)

        self._home_gamepad_opts = opts
        mode_box.pack_start(opts, False, False, 0)

        ponte = Gtk.Label(label="")
        ponte.set_xalign(0.0)
        ponte.set_line_wrap(True)
        self._home_ponte_label = ponte
        mode_box.pack_start(ponte, False, False, 0)

        divergencia = Gtk.Label(label="")
        divergencia.set_xalign(0.0)
        divergencia.set_line_wrap(True)
        divergencia.set_no_show_all(True)
        divergencia.set_visible(False)
        self._home_divergencia_banner = divergencia
        mode_box.pack_start(divergencia, False, False, 0)

        self._home_flavor_pedido: str | None = None

        pendente = Gtk.Label(label="")
        pendente.set_xalign(0.0)
        pendente.set_line_wrap(True)
        pendente.set_no_show_all(True)
        pendente.set_visible(False)
        pendente.get_style_context().add_class(
            "hefesto-dualsense4unix-status-warn"
        )
        self._home_pendente_label = pendente
        mode_box.pack_start(pendente, False, False, 0)

        origin = Gtk.Label(label="")
        origin.set_xalign(0.0)
        origin.get_style_context().add_class("dim-label")
        self._home_origin_label = origin
        mode_box.pack_start(origin, False, False, 0)

        lock_check = Gtk.CheckButton(
            label="Modo Freestyle"
        )
        lock_check.set_tooltip_text(
            "O perfil ativo continua valendo mesmo quando você abre outro "
            "jogo. Desligue para o Hefesto voltar a escolher sozinho."
        )
        lock_check.connect("toggled", self._on_home_autoswitch_lock_toggled)
        self._home_autoswitch_lock = lock_check
        mode_box.pack_start(lock_check, False, False, 0)

        lock_hint = Gtk.Label(label="")
        lock_hint.set_xalign(0.0)
        lock_hint.set_line_wrap(True)
        lock_hint.get_style_context().add_class("dim-label")
        lock_hint.set_no_show_all(True)
        lock_hint.set_visible(False)
        self._home_autoswitch_lock_hint = lock_hint
        mode_box.pack_start(lock_hint, False, False, 0)

        frame_mode.add(mode_box)
        box.pack_start(frame_mode, False, False, 0)

        frame_ctrl = Gtk.Frame(label="Controles")
        ctrl_frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctrl_box.set_homogeneous(True)
        ctrl_box.set_margin_top(10)
        ctrl_box.set_margin_start(12)
        ctrl_box.set_margin_end(12)
        self._home_controllers_box = ctrl_box
        ctrl_frame_box.pack_start(ctrl_box, False, False, 0)

        # compacta a numeração de exibição (DualSense + externos,
        reconciliar_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        reconciliar_row.set_margin_start(12)
        reconciliar_row.set_margin_end(12)
        reconciliar_row.set_margin_bottom(10)
        reconciliar_btn = Gtk.Button(label=RECONCILIAR_LABEL)
        reconciliar_btn.set_tooltip_text(
            "Confere os jogadores do co-op e traz de volta quem caiu (grab "
            "recusado, controle re-enumerado), e depois arruma a numeração "
            "1..N. Pode clicar com o jogo aberto: só a numeração espera."
        )
        reconciliar_btn.connect("clicked", self._on_home_reconciliar_clicked)
        self._home_reconciliar_btn = reconciliar_btn
        reconciliar_row.pack_start(reconciliar_btn, False, False, 0)
        reconciliar_hint = Gtk.Label(label="")
        reconciliar_hint.set_xalign(0.0)
        reconciliar_hint.set_line_wrap(True)
        reconciliar_hint.get_style_context().add_class("dim-label")
        self._home_reconciliar_hint = reconciliar_hint
        reconciliar_row.pack_start(reconciliar_hint, False, False, 0)
        ctrl_frame_box.pack_start(reconciliar_row, False, False, 0)

        frame_ctrl.add(ctrl_frame_box)
        box.pack_start(frame_ctrl, False, False, 0)

        frame_sess = Gtk.Frame(label="Sessão")
        sess_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sess_box.set_margin_top(10)
        sess_box.set_margin_bottom(10)
        sess_box.set_margin_start(12)
        sess_box.set_margin_end(12)

        shutdown_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        shutdown_btn = Gtk.Button(label=_BTN_LABEL_ONLINE)
        shutdown_btn.get_style_context().add_class("destructive-action")
        shutdown_btn.connect("clicked", self._on_home_power_clicked)
        self._home_shutdown_btn = shutdown_btn
        self._home_offline = False
        shutdown_row.pack_start(shutdown_btn, False, False, 0)
        sess_status = Gtk.Label(label="")
        sess_status.set_xalign(0.0)
        self._home_session_label = sess_status
        shutdown_row.pack_start(sess_status, False, False, 0)
        sess_box.pack_start(shutdown_row, False, False, 0)

        hint = Gtk.Label(label=_GLOSSARY)
        hint.set_xalign(0.0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dim-label")
        sess_box.pack_start(hint, False, False, 0)

        frame_sess.add(sess_box)
        box.pack_start(frame_sess, False, False, 0)
        box.show_all()

        GLib.timeout_add(HOME_POLL_INTERVAL_MS, self._tick_home_state)


    def _tick_home_state(self) -> bool:
        notebook = self._get("main_notebook")
        if notebook is not None and id_da_pagina_corrente(notebook) == ABA_INICIO:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import (
                    load_gamepad_preference,
                )

                preferencia, _flavor = load_gamepad_preference()
                self._home_opt_out_cache = preferencia is False
            self._maybe_fetch_externos()
            self._refresh_home_tab()
        return True

    #: é afirmação de ausência, e por isso ninguém acusa nada com ela.
    _home_externos: list[dict[str, Any]]

    _home_externos_ts: float
    _home_externos_inflight: bool

    EXTERNOS_THROTTLE_S = 4.0

    def _maybe_fetch_externos(self) -> None:
        """Pede o inventário de externos ao daemon, com teto. I5 (25/08/2026).

        Por que um IPC a mais, e não uma chave a mais no ``state_full``:
        **medido por leitura de código** — o ``daemon.state_full`` não publica
        ``external`` (só ``coop.externals``, que é uma CONTAGEM e não diz
        quem), e o ``state_full`` roda a 10-20 Hz. Enfiar a enumeração de evdev
        ali dentro poria um subprocess no caminho quente do input, que é o
        oposto do que esta casa aceita. A aba Configurações e a aba Status já
        resolvem isso do mesmo jeito, pelo mesmo motivo.

        Falha em silêncio: sem resposta a aba desenha o que já tinha, que é o
        comportamento de antes desta cura e nunca pior que ele.
        """
        agora = time.monotonic()
        if getattr(self, "_home_externos_inflight", False):
            return
        if agora - getattr(self, "_home_externos_ts", 0.0) < self.EXTERNOS_THROTTLE_S:
            return
        self._home_externos_ts = agora
        self._home_externos_inflight = True

        def _ok(resultado: Any) -> bool:
            self._home_externos_inflight = False
            bruto = resultado.get("external") if isinstance(resultado, dict) else None
            self._home_externos = (
                [e for e in bruto if isinstance(e, dict)]
                if isinstance(bruto, list)
                else []
            )
            return False

        def _fail(_exc: Exception) -> bool:
            self._home_externos_inflight = False
            return False

        call_async(
            "controller.list",
            {"external": True},
            _ok,
            _fail,
            timeout_s=3.0,
        )

    def _refresh_home_tab(self) -> None:
        """Reconcilia o comutador/cards com o estado VIVO do daemon."""
        if not getattr(self, "_home_installed", False):
            return
        agora = time.monotonic()
        if getattr(self, "_home_inflight", False):
            desde = getattr(self, "_home_inflight_since", 0.0)
            if agora - desde < HOME_INFLIGHT_TIMEOUT_S:
                return
            logger.warning(
                "aba Início: a leitura de estado não voltou em %.1fs — "
                "soltando a trava e tentando de novo",
                agora - desde,
            )
        self._home_inflight = True
        self._home_inflight_since = agora

        def _ok(state: Any) -> bool:
            self._home_inflight = False
            if isinstance(state, dict):
                self._render_home(state)
            return False

        def _fail(_exc: Exception) -> bool:
            self._home_inflight = False
            self._render_home(None)
            return False

        call_async("daemon.state_full", None, _ok, _fail,
                   timeout_s=_STATE_IPC_TIMEOUT_S)

    def _render_home(self, state: dict[str, Any] | None) -> None:
        from gi.repository import Gtk

        offline = state is None
        # rodapé seguiu minutos escrito "Troca automática de perfil LIBERADA"
        # só quando a frase de estado MUDA de valor — e nesse instante o que
        aviso_estado = autoswitch_lock_text(state)
        anterior = getattr(self, "_home_lock_toast", None)
        if aviso_estado != anterior:
            self._home_lock_toast = aviso_estado
            toast = getattr(self, "_status_toast", None)
            if toast is not None and (aviso_estado or anterior):
                toast("home", aviso_estado)
        selector = self._home_mode_selector
        self._home_guard = True
        try:
            if offline:
                self._home_session_label.set_text("O Hefesto está desligado.")
                selector.set_sensitive(False)
                self._home_players_hint.set_text("")
                self._home_flavor_selector.set_sensitive(False)
                self._home_mode_desc.set_text("")
                self._home_origin_label.set_text("")
                self._home_gamepad_opts.set_visible(False)
                render_pendente(self, visivel=False)
                self._home_vpad_banner.set_visible(False)
                self._home_wrapper_banner.set_visible(False)
                _desktop_aviso = getattr(self, "_home_desktop_aviso", None)
                if _desktop_aviso is not None:
                    _desktop_aviso.set_visible(False)
                _ponte = getattr(self, "_render_ponte_e_divergencia", None)
                if _ponte is not None:
                    _ponte(None)
                self._render_home_controllers([])
                self._home_offline = True
                self._home_shutdown_btn.set_label(_BTN_LABEL_OFFLINE)
                self._home_shutdown_btn.get_style_context().remove_class(
                    "destructive-action"
                )
                self._home_shutdown_btn.get_style_context().add_class(
                    "suggested-action"
                )
                self._home_reconciliar_btn.set_sensitive(False)
                self._home_reconciliar_hint.set_text("")
                _lock = getattr(self, "_home_autoswitch_lock", None)
                if _lock is not None:
                    _lock.set_sensitive(False)
                _lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)
                if _lock_hint is not None:
                    _lock_hint.set_text("")
                    _lock_hint.set_visible(False)
                return
            assert state is not None
            selector.set_sensitive(True)
            self._home_flavor_selector.set_sensitive(True)
            # set_active emite "toggled", que reenviaria o IPC em loop).
            _lock = getattr(self, "_home_autoswitch_lock", None)
            if _lock is not None:
                _lock.set_sensitive(True)
                _lock.set_active(bool(state.get("freestyle_ligado", False)))
            _lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)
            if _lock_hint is not None:
                aviso_lock = " ".join(
                    parte
                    for parte in (
                        autoswitch_lock_text(state),
                        texto_do_cadeado_cego(state),
                    )
                    if parte
                )
                _lock_hint.set_text(aviso_lock)
                _lock_hint.set_visible(bool(aviso_lock))
            self._home_session_label.set_text("")
            self._home_offline = False
            self._home_shutdown_btn.set_label(_BTN_LABEL_ONLINE)
            self._home_shutdown_btn.get_style_context().remove_class(
                "suggested-action"
            )
            self._home_shutdown_btn.get_style_context().add_class(
                "destructive-action"
            )
            aviso_reconciliar = _reconciliar_gate_text(state)
            self._home_reconciliar_btn.set_sensitive(True)
            self._home_reconciliar_hint.set_text(aviso_reconciliar or "")

            gamepad = state.get("gamepad_emulation") or {}
            mode = mode_of_state(state) or "desktop"
            flavor = gamepad.get("flavor")
            if isinstance(flavor, str) and flavor:
                self._mascara_vigente_do_daemon = flavor
            # `mouse.emulation.restore` — o ÚLTIMO dos três IPCs do plano —
            modo_anterior = getattr(self, "_modo_vigente_do_daemon", None)
            self._modo_vigente_do_daemon = mode
            # espelham o daemon, como sempre; com pendência eles mostram a
            # ESCOLHA DELA, e este tique não a sobrescreve. Sem isto o desenho
            pendente = reconciliar_pendente(self)
            modo_exibido = pendente.get("modo") or mode
            selector.set_active_id(modo_exibido)
            aviso_pausa = texto_da_pausa(state)
            self._home_mode_desc.set_text(
                aviso_pausa or _MODE_DESCRIPTIONS.get(modo_exibido, "")
            )
            aviso_desktop = texto_do_desktop_sem_emulacao(
                state,
                modo_exibido=modo_exibido,
                modo_mudou_agora=modo_anterior != mode,
            )
            _desktop_aviso = getattr(self, "_home_desktop_aviso", None)
            if _desktop_aviso is not None:
                if aviso_desktop:
                    _desktop_aviso.set_text(aviso_desktop)
                _desktop_aviso.set_visible(bool(aviso_desktop))
            #   *"a máscara volta ao que era. Não temos que burocratizar aí.
            # aqui" exige saber que o modo é pendente; o que se lê é "a máscara
            # sumiu", que é outra coisa.
            #
            # Agora a caixa segue a ESCOLHA: um "Aplicar" só, com modo e máscara
            # decididos juntos — que é como ela usa a janela.
            self._home_gamepad_opts.set_visible(modo_exibido == "gamepad")
            self._home_gamepad_opts.set_no_show_all(modo_exibido != "gamepad")

            # AUTO-01.3: o dono da máscara é o DAEMON — a GUI só ECOA o que ele
            # está e o plano de transição sai sem o campo (ver
            mascara_exibida = pendente.get("mascara") or (
                flavor if isinstance(flavor, str) and flavor else None
            )
            if mascara_exibida:
                self._home_flavor_selector.set_active_id(mascara_exibida)
            # MASCARA-CUSTO-01: o preço da máscara, embaixo do seletor — e é o
            custo = getattr(self, "_home_flavor_custo", None)
            if custo is not None:
                texto = texto_do_custo_da_mascara(mascara_exibida)
                custo.set_text(texto)
                custo.set_visible(bool(texto))
                custo.set_no_show_all(not texto)

            # DualSense caiu no backend uinput (função pura decide; backend
            aviso_vpad = vpad_degradation_text(state)
            if aviso_vpad:
                self._home_vpad_banner.set_text(aviso_vpad)
            self._home_vpad_banner.set_visible(bool(aviso_vpad))

            # `gamepad_emulation.wrapper_used` acende (função pura decide).
            aviso_wrapper = aviso_do_wrapper(state)
            if aviso_wrapper:
                self._home_wrapper_banner.set_text(aviso_wrapper)
            self._home_wrapper_banner.set_visible(bool(aviso_wrapper))

            aviso_opt_out = aviso_de_opt_out_antigo(
                state,
                opt_out=bool(getattr(self, "_home_opt_out_cache", False)),
                conectados=len(
                    [
                        c
                        for c in (state.get("controllers") or [])
                        if isinstance(c, dict) and c.get("connected")
                    ]
                ),
            )
            # um pedágio em arquivos que não têm nada a ver com ele.
            banner_opt_out = getattr(self, "_home_opt_out_banner", None)
            if banner_opt_out is not None:
                if aviso_opt_out:
                    banner_opt_out.set_text(aviso_opt_out)
                banner_opt_out.set_visible(bool(aviso_opt_out))

            _ponte = getattr(self, "_render_ponte_e_divergencia", None)
            if _ponte is not None:
                _ponte(state)

            origin_bits: list[str] = []
            if state.get("native_mode") and state.get("native_mode_origin") == "profile":
                origin_bits.append("Nativo ligado pelo perfil ativo")
            if state.get("mode_from_profile") == "gamepad":
                origin_bits.append("Gamepad ligado pelo perfil ativo")
            self._home_origin_label.set_text(" · ".join(origin_bits))

            # aba inventava um card "Controle 1 — P1 · ?" com o cabo na mesa. A
            connected = [
                c
                for c in (state.get("controllers") or [])
                if isinstance(c, dict) and c.get("connected")
            ]
            # controles conectados que os cards mostram (`state_full`), uma
            externos = externos_na_mesa(state, getattr(self, "_home_externos", ()))
            self._home_players_hint.set_text(
                _format_players_hint(connected, externos)
            )
            self._controles_conectados = len(connected)
            # derivá-lo de novo. Duas chamadas de `mode_of_state` no mesmo tique
            # a pendência agora depende deste valor para saber se a escolha dela
            self._modo_vigente_do_daemon = mode
            self._jogo_aberto = jogo_com_autoridade(state)
            self._render_home_controllers(
                connected,
                grab_state=state.get("primary_grab_state"),
                gamepad_on=bool(gamepad.get("enabled")),
                externos=externos,
            )
            render_pendente(self)
            _ = Gtk
        finally:
            self._home_guard = False

    def _mascara_escolhida_por_ela(self) -> str | None:
        """A máscara que ELA pediu, sem perguntar ao daemon (PONTE-NA-TELA-01)."""
        mascara, _fonte = self._mascara_escolhida_com_fonte()
        return mascara

    def _mascara_escolhida_com_fonte(self) -> tuple[str | None, str]:
        """A mesma máscara da função acima, e DE ONDE ela veio (I3, 25/08/2026)."""
        pedido = getattr(self, "_home_flavor_pedido", None)
        if isinstance(pedido, str) and pedido:
            return pedido, FONTE_GESTO_DELA
        draft = getattr(self, "draft", None)
        origem = getattr(draft, "source_mode", None) if draft is not None else None
        if origem is None:
            return None, FONTE_GESTO_DELA
        valor = (
            origem.get("gamepad_flavor")
            if isinstance(origem, dict)
            else getattr(origem, "gamepad_flavor", None)
        )
        if isinstance(valor, str) and valor:
            return valor, FONTE_PERFIL
        return None, FONTE_GESTO_DELA

    def _render_ponte_e_divergencia(self, state: dict[str, Any] | None) -> None:
        """Pinta a linha da ponte e o aviso de divergência (PONTE-NA-TELA-01)."""
        ponte = getattr(self, "_home_ponte_label", None)
        if ponte is not None:
            ponte.set_markup(texto_da_ponte(state))
        banner = getattr(self, "_home_divergencia_banner", None)
        if banner is None:
            return
        no_aparelho = mascara_do_aparelho(state)
        # lugar (a aba Perfis, o autoswitch) — a aba passaria a mentir para o
        pedido = getattr(self, "_home_flavor_pedido", None)
        if pedido and no_aparelho and pedido == no_aparelho:
            self._home_flavor_pedido = None
        # `vpad_degradation_text`.
        # `mode_of_state`, e é ele que continua decidindo.
        escolhida, fonte = self._mascara_escolhida_com_fonte()
        alarme = mascara_divergente_do_daemon(state)
        perfil = None
        if alarme is not None:
            do_perfil = alarme.get("mascara_perfil")
            if isinstance(do_perfil, str) and do_perfil:
                escolhida, fonte = do_perfil, FONTE_PERFIL
                perfil = alarme.get("profile")
        aviso = (
            texto_da_divergencia(
                escolhida,
                no_aparelho,
                jogo_aberto=jogo_com_autoridade(state),
                fonte=fonte,
                perfil=perfil,
            )
            if mode_of_state(state) == MODE_GAMEPAD
            else None
        )
        if aviso:
            banner.set_markup(aviso)
        banner.set_visible(bool(aviso))

    def _render_home_controllers(
        self,
        controllers: list[dict[str, Any]],
        *,
        grab_state: str | None = None,
        gamepad_on: bool = False,
        externos: Sequence[dict[str, Any]] = (),
    ) -> None:
        from gi.repository import Gtk

        box = self._home_controllers_box
        for child in box.get_children():
            box.remove(child)
        # os externos continuam a fila), e é a mesma que o LED de player mostra
        # seletor de modo que ESCREVEM, e trazê-lo para cá daria à primeira
        # que a regra "aba nova copia a gramática visual das antigas" evita. O
        validos = [e for e in externos if isinstance(e, dict)]
        if not controllers and not validos:
            empty = Gtk.Label(label="Nenhum controle conectado.")
            empty.get_style_context().add_class("dim-label")
            box.pack_start(empty, False, False, 0)
            box.show_all()
            return
        for ctrl in controllers:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.get_style_context().add_class("hefesto-dualsense4unix-card")
            card.set_margin_end(6)
            is_primary = bool(ctrl.get("is_primary"))
            title = Gtk.Label()
            name = _format_controller_title(ctrl)
            title.set_markup(f"<b>{name}</b>" if is_primary else name)
            title.set_xalign(0.0)
            card.pack_start(title, False, False, 0)
            sub = Gtk.Label(
                label=_format_controller_subtitle(
                    ctrl.get("transport"),
                    is_primary=is_primary,
                    battery_pct=ctrl.get("battery_pct"),
                )
            )
            sub.set_xalign(0.0)
            sub.get_style_context().add_class("dim-label")
            card.pack_start(sub, False, False, 0)
            # "Grab falhou — input pode dobrar no jogo", que é o que aconteceu
            aviso = aviso_de_grab(
                grab_state, is_primary=is_primary, gamepad_on=gamepad_on
            )
            if aviso is not None:
                linha, porque = aviso
                warn = Gtk.Label(label=linha)
                warn.set_xalign(0.0)
                warn.set_tooltip_text(porque)
                warn.get_style_context().add_class("hefesto-dualsense4unix-status-err")
                card.pack_start(warn, False, False, 0)
            box.pack_start(card, True, True, 0)
        for ext in validos:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.get_style_context().add_class("hefesto-dualsense4unix-card")
            card.set_margin_end(6)
            title = Gtk.Label()
            title.set_markup(_escapar(_format_external_title(ext)))
            title.set_xalign(0.0)
            card.pack_start(title, False, False, 0)
            sub = Gtk.Label(label=_format_external_subtitle(ext))
            sub.set_xalign(0.0)
            sub.get_style_context().add_class("dim-label")
            card.pack_start(sub, False, False, 0)
            box.pack_start(card, True, True, 0)
        box.show_all()


    def _on_home_mode_changed(self, selector: Any) -> None:
        mode_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not mode_id:
            return
        self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode_id, ""))
        #   *"talvez fosse interessante isso aparecer somente quando clicarmos
        marcar_escolha(self, "modo", mode_id)

    def _on_home_flavor_changed(self, selector: Any) -> None:
        flavor_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not flavor_id:
            return
        mode = self._home_mode_selector.get_active_id()
        if mode != "gamepad":
            return
        # para o "Aplicar" (`footer_actions._aplicar_escolha_pendente`), onde a
        # decisão dela está COMPLETA — modo e máscara escolhidos — em vez de
        #
        marcar_escolha(self, "mascara", flavor_id)

    def _on_home_autoswitch_lock_toggled(self, check: Any) -> None:
        """FEAT-AUTOSWITCH-LOCK-01: liga/desliga o cadeado da troca automática.

        Guard `_home_guard`: o `_render_home` chama `set_active` para refletir o
        daemon, e isso emite "toggled" — sem o guard, cada tick reenviaria o IPC.
        """
        if getattr(self, "_home_guard", False):
            return
        from hefesto_dualsense4unix.app import ipc_bridge

        desejado = bool(check.get_active())

        def _fim(resultado: Any) -> bool:
            if resultado is None:
                self._status_toast(
                    "home", "O Hefesto está desligado: a trava não foi aplicada."
                )
            else:
                self._status_toast(
                    "home",
                    "Modo Freestyle ligado — o Freestyle vale em todo jogo."
                    if resultado else
                    "Modo Freestyle desligado — o Hefesto volta a escolher o "
                    "perfil ao abrir cada jogo.",
                )
            return False

        ipc_bridge.run_in_thread(
            lambda: ipc_bridge.freestyle_set(desejado), on_success=_fim
        )

    def _on_home_reconciliar_clicked(self, _button: object) -> None:
        """"Reconciliar jogadores": ``coop.sync`` e, em seguida, ``identity.renumber``."""

        def _sync_ok(resultado_sync: Any) -> bool:
            jogadores = (
                resultado_sync.get("players")
                if isinstance(resultado_sync, dict)
                else None
            )

            def _renumber_ok(resultado: Any) -> bool:
                self._status_toast("home", reconciliar_toast(jogadores, resultado))
                self._refresh_home_tab()
                return False

            def _renumber_fail(_exc: Exception) -> bool:
                self._status_toast("home", reconciliar_toast(jogadores, None))
                self._refresh_home_tab()
                return False

            call_async(
                "identity.renumber",
                {},
                _renumber_ok,
                _renumber_fail,
                timeout_s=_MODE_IPC_TIMEOUT_S,
            )
            return False

        def _sync_fail(_exc: Exception) -> bool:
            self._status_toast(
                "home",
                "Não consegui reconciliar — o Hefesto pode estar desligado.",
            )
            return False

        call_async("coop.sync", {}, _sync_ok, _sync_fail, timeout_s=_MODE_IPC_TIMEOUT_S)

    def _on_home_power_clicked(self, button: object) -> None:
        """Dispatcher do botão único de energia da aba Início (ONDA-U, U1).

        Offline: reusa o MESMO caminho de ``on_daemon_start``
        (``DaemonActionsMixin`` — ``systemctl --user start`` em thread
        worker, com toast e reset do flag ``_user_stopped_daemon``) — nada de
        duplicar a lógica de subir o daemon. ``getattr`` defensivo (mesmo
        padrão de ``_edit_uniq`` em ``lightbar_actions``): os dois mixins só
        convivem de fato na instância composta (``HefestoApp``), nunca
        isolados nos testes. Online: mantém o fluxo de confirmação existente
        (``_on_home_shutdown_clicked``). O estado vem de ``self._home_offline``,
        mantido pelo ``_render_home``.
        """
        if getattr(self, "_home_offline", False):
            start = getattr(self, "on_daemon_start", None)
            if callable(start):
                start(button)
            return
        self._on_home_shutdown_clicked(button)

    def _on_home_shutdown_clicked(self, _button: object) -> None:
        """Desliga o daemon DE VERDADE (com confirmação não-bloqueante)."""
        from gi.repository import Gtk

        window = self._get("main_window")
        dialog = Gtk.MessageDialog(
            transient_for=window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Desligar o Hefesto?",
        )
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
        dialog.format_secondary_text(
            "O controle continua funcionando nos jogos, mas sem luzes, sem "
            "gatilhos e sem os seus ajustes.\n"
            "Esta janela continua aberta e NÃO liga o Hefesto de novo sozinha "
            "— para ligar de novo, clique em \"Ligar o Hefesto\" aqui mesmo, "
            "nesta aba."
        )

        def _on_response(dlg: Any, response: int) -> None:
            dlg.destroy()
            if response != Gtk.ResponseType.YES:
                return
            self._user_stopped_daemon = True

            def _worker_ok(result: Any) -> bool:
                # não pode mentir nem armar o _user_stopped_daemon à toa.
                rc = getattr(result, "returncode", 1)
                if rc == 0:
                    self._status_toast(
                        "home", "Hefesto desligado — controle no modo puro do Linux"
                    )
                else:
                    self._user_stopped_daemon = False
                    err = (getattr(result, "stderr", b"") or b"").decode(
                        "utf-8", "replace"
                    ).strip()
                    logger.warning("home_shutdown_falhou", erro=err)
                    self._status_toast(
                        "home",
                        "Não consegui desligar o Hefesto — tente pela aba "
                        "Sistema.",
                    )
                self._refresh_home_tab()
                return False

            from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread

            def _stop() -> Any:
                import subprocess

                return subprocess.run(
                    ["systemctl", "--user", "stop", "hefesto-dualsense4unix.service"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )

            run_in_thread(_stop, _worker_ok, lambda _e: False)

        dialog.connect("response", _on_response)
        from hefesto_dualsense4unix.app import gui_dialogs as _gd

        _gd.mostrar_dialogo_assincrono(dialog, nome="home_desligar_hefesto")


__all__ = [
    "ABA_INICIO",
    "DESFECHO_APLICADO",
    "DESFECHO_BLOQUEADO",
    "DESFECHO_FALHOU",
    "DESFECHO_INCERTO",
    "DESFECHO_JA_ESTAVA",
    "DIVERGENCIA_DO_PERFIL_PREFIXO",
    "DIVERGENCIA_PREFIXO",
    "FONTE_GESTO_DELA",
    "FONTE_PERFIL",
    "HOME_POLL_INTERVAL_MS",
    "PALAVRA_DE_TRANSPORTE_DESCONHECIDO",
    "PONTE_PREFIXO",
    "RECONCILIAR_JOGO_ABERTO_TEXT",
    "RECONCILIAR_LABEL",
    "TEXTO_DESKTOP_SEM_MOUSE",
    "TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO",
    "TEXTO_DESKTOP_SEM_TECLADO",
    "TEXTO_DETECTOR_CEGO",
    "TEXTO_EM_PAUSA",
    "VPAD_DEGRADED_TEXT",
    "WRAPPER_MISSING_TEXT",
    "HomeActionsMixin",
    "appid_do_jogo_em_foco",
    "aviso_do_wrapper",
    "controles_bt_frageis",
    "controles_na_mesa",
    "desfecho_da_troca",
    "ela_ja_respondeu_sobre",
    "externos_na_mesa",
    "id_da_pagina",
    "id_da_pagina_corrente",
    "jogadores_degradados",
    "jogo_com_autoridade",
    "lembrar_mascara_recusada",
    "mascara_divergente_do_daemon",
    "mascara_do_aparelho",
    "mascara_viva",
    "palavra_do_transporte",
    "reconciliar_toast",
    "texto_coop_degradado",
    "texto_da_divergencia",
    "texto_da_pausa",
    "texto_da_ponte",
    "texto_do_cadeado_cego",
    "texto_do_desktop_sem_emulacao",
    "texto_do_radio_fragil",
    "texto_native_bt_fragil",
    "toast_da_troca_de_mascara",
    "vpad_degradation_text",
    "wrapper_banner_text",
]


def aviso_de_opt_out_antigo(
    state: dict[str, Any] | None, *, opt_out: bool, conectados: int
) -> str | None:
    """O produto está inerte por uma escolha ANTIGA dela. ``None`` = nada a dizer."""
    if not isinstance(state, dict) or not opt_out or conectados < 1:
        return None
    if state.get("native_mode"):
        return None
    gamepad = state.get("gamepad_emulation")
    if isinstance(gamepad, dict) and gamepad.get("enabled"):
        return None
    return (
        "O controle está em “Controlar o PC” porque a emulação foi desligada "
        "numa sessão anterior, e essa escolha vale até você mudá-la. Enquanto "
        "estiver assim, o giroscópio e a vibração não chegam a jogo nenhum — "
        "escolha “Jogar pelo Hefesto” ou “Conexão Nativa (Sony)” aqui em cima."
    )
