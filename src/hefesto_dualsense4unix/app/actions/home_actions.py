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
3. "Como desligo o hefesto DE VERDADE?" — botão dedicado que para o daemon e
   NÃO o religa ao reabrir/atualizar a GUI (diferente do "Desligar o Hefesto"
   da aba Sistema, que o `ensure_daemon_running` ressuscitava sem avisar).

Todo widget é montado em código dentro de `tab_home_box` (Glade só reserva o
container) — padrão dos widgets dinâmicos, imune ao bug de popup do cosmic-comp
(botões sempre visíveis, sem dropdown).
"""
from __future__ import annotations

import contextlib
import time
from typing import Any, Final

from hefesto_dualsense4unix.app.actions.base import (
    WidgetAccessMixin,
    numero_do_controle,
)
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_GAMEPAD,
    MODE_IPC_TIMEOUT_S,
    MODES,
    STATE_IPC_TIMEOUT_S,
    apply_coop_prep,
    apply_mode,
    mode_of_state,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Intervalo do poller da aba Início (só age com a aba visível).
HOME_POLL_INTERVAL_MS = 2000

#: AVISO-VIVO-01: prazo de validade do latch `_home_inflight` — três ticks do
#: poller. O latch existe para não empilhar chamadas de estado, mas sem prazo
#: uma chamada que NUNCA volta (daemon morto no meio do `state_full`) o prendia
#: para sempre e a aba congelava em silêncio: sem erro, sem banner, só parada.
#: Passado o prazo a chamada em voo é dada como perdida e uma nova sai. O prazo
#: é conferido no próprio tick, por carimbo de tempo — sem thread nem timer novo.
HOME_INFLIGHT_TIMEOUT_S = 3 * HOME_POLL_INTERVAL_MS / 1000.0

#: Id do Glade da aba Início. É por ele que o poller pergunta se está à vista —
#: nunca pelo número da página (EST-10).
ABA_INICIO = "tab_home_box"


def id_da_pagina(pagina: Any) -> str | None:
    """Id do Glade de uma página do notebook, desembrulhando o rolador.

    ``_wrap_notebook_pages_in_scroll`` envolve oito das nove páginas num
    ``GtkScrolledWindow``, que por sua vez pode inserir um ``GtkViewport`` entre
    ele e a página — então o widget que o notebook devolve NÃO é a página do
    Glade, e sem desembrulhar nenhuma aba seria reconhecida.

    Devolve ``None`` para o que não é ``Gtk.Buildable`` (dublê de teste), em vez
    de levantar.

    Mora neste módulo por causa do grafo de import: ``status_actions`` importa
    ``home_actions`` (nunca o contrário) e ``app.py`` importa os dois — é o
    único ponto onde os três chegam sem ciclo.
    """
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
    """Id do Glade da página à vista — o que os pollers têm de perguntar.

    EST-10: identificar a aba pelo ÍNDICE passa a apontar para a aba errada, em
    silêncio, no dia em que alguém inserir, remover ou reordenar uma página no
    Glade — sem exceção, sem log, só o relógio errado rodando na aba errada. O
    id do Glade não muda quando a ordem ou o rótulo mudam.
    """
    if notebook is None:
        return None
    indice = notebook.get_current_page()
    if not isinstance(indice, int) or indice < 0:
        return None
    return id_da_pagina(notebook.get_nth_page(indice))


#: HARM-01: a folga da troca de modo mora em `mode_transition` (dono único) —
#: aqui ela vale também para o co-op e a máscara, que criam/desmontam os mesmos
#: uinput e não cabem nos 0.25s default do call_async.
_MODE_IPC_TIMEOUT_S = MODE_IPC_TIMEOUT_S

#: HARM-15: o refresh também não cabe nos 0.25s default do call_async — sem folga
#: o `_fail` pintava a aba inteira de "Daemon desligado" com o daemon VIVO. Vem de
#: `mode_transition` (dono único): a aba Mouse lê o MESMO state_full para saber o
#: modo e precisa exatamente da mesma folga.
_STATE_IPC_TIMEOUT_S = STATE_IPC_TIMEOUT_S

# UX-MODE-TERMS-01: rótulos pela AÇÃO da usuária ("o que o controle faz
# agora"), não pela tecnologia — "gamepad virtual"/"nativo" viravam jargão.
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Jogar direto (Sony)"),
]

# LEIGO-02: "(vibra)"/"(sem vibrar)" eram verdade enquanto a máscara DualSense
# não vibrava; com o vpad uhid (SPRINT-UHID-VPAD-01) as duas vibram, então o
# rótulo antigo virou MENTIRA. O que resta de diferença é o que a usuária vê na
# tela do jogo: os desenhos dos botões. Xbox segue na lista porque há jogos que
# só entendem XInput.
_FLAVOR_ITEMS = [
    ("xbox", "Xbox 360"),
    ("dualsense", "DualSense (botões PlayStation)"),
]

_MODE_DESCRIPTIONS = {
    "desktop": (
        "O controle vira mouse/teclado do computador (ajustes nas abas "
        "Mouse e Teclado)."
    ),
    # LEIGO-02: a recomendação de 3 linhas ("use a máscara Xbox 360 e cole as
    # opções da Steam") existia só para contornar a máscara DualSense que não
    # vibrava. O SPRINT-UHID-VPAD-01 curou isso (o gamepad virtual é um
    # DualSense de verdade via /dev/uhid, e vibra) — o trade-off morreu com ele,
    # e a frase que o explicava morre junto.
    "gamepad": (
        "Escolha certa para quase todos os jogos: o Hefesto acende as luzes, "
        "faz o controle vibrar e dá um jogador para cada controle."
    ),
    # SPRINT-GAME-RUMBLE-01: sem o Hefesto no meio, o jogo fala direto com o
    # DualSense — inclusive pelo canal de áudio (haptics do PS5), que é o que
    # dispara o travamento/desconexão em alguns títulos.
    "native": (
        "Só para jogos feitos para o PlayStation 5: os gatilhos ficam duros de "
        "apertar, como no PS5. Alguns jogos derrubam o controle no meio da "
        "partida neste modo — se acontecer, volte para \"Jogar pelo Hefesto\"."
    ),
}

# LEIGO-02: o glossário enfileirava 4 conceitos, dois deles mortos — "Pausar"
# não é mais botão de lugar nenhum e "Jogar direto" já é um dos três botões
# logo acima (com descrição própria). Sobram os dois que a aba NÃO explica por
# si: o "Modo jogo" (que mora em outra aba) e o desligar de verdade.
# ONDA-U (U1): o "ligar de novo" deixou de mandar pra aba Sistema — o mesmo
# botão vira "Ligar o Hefesto" nesta própria aba (toggle in-place).
_GLOSSARY = (
    "Modo jogo (aba Emulação): pausa só o mouse/teclado, sem soltar o "
    "controle.  ·  "
    'Desligar Hefesto: para tudo até você clicar em "Ligar o Hefesto" aqui '
    "mesmo, nesta aba."
)

# ONDA-U (U1): rótulos do botão único de energia da aba Início — ele TROCA de
# texto/ação conforme o daemon está online ou offline (nunca dois botões).
_BTN_LABEL_ONLINE = "Desligar Hefesto (voltar ao Linux puro)"
_BTN_LABEL_OFFLINE = "Ligar o Hefesto"


def autoswitch_lock_text(state: dict[str, Any] | None) -> str:
    """Frase do cadeado da troca de perfil — função PURA (UX-05).

    Vazia quando destravado (nada a explicar: é o comportamento normal). Com o
    cadeado ligado, diz as duas metades da política LOCK-CEDE-01, porque as
    duas surpreendem quem só vê o efeito:

    1. o que ela pediu — o perfil escolhido FICA, nada troca por janela;
    2. o que continua valendo — o jogo que TEM perfil próprio ainda entra
       (senão "o modo jogo não ativa" volta a ser um mistério sem causa).

    O nome do perfil ativo entra quando o daemon o reporta: "o perfil não troca
    sozinho" sem dizer QUAL perfil ficou é meia informação.
    """
    if not state or not state.get("autoswitch_locked"):
        return ""
    ativo = state.get("active_profile")
    alvo = f" — vale o perfil “{ativo}”" if isinstance(ativo, str) and ativo else ""
    return (
        f"Cadeado ligado: o perfil não troca sozinho{alvo}. "
        "Jogos com perfil próprio ainda entram; qualquer outra janela é ignorada."
    )


def _mode_label(mode_id: object) -> str:
    """Rótulo do modo como a usuária o lê no botão (LEIGO-02) — função pura.

    Os toasts ecoavam o id interno ("gamepad", "native"): palavras que não
    aparecem em lugar nenhum da interface. O fallback devolve o próprio id para
    um modo desconhecido (payload de daemon mais novo) ser visível em vez de
    virar texto vazio.
    """
    return dict(_MODE_ITEMS).get(str(mode_id), str(mode_id))


#: MASCARA-CUSTO-01 (01/08) — o que cada máscara CUSTA, em uma frase.
#:
#: Função pura, no padrão de `vpad_degradation_text`, para que a aba Início e
#: a aba Emulação nunca digam coisas diferentes sobre o mesmo fato.
#:
#: O fato, medido pela auditoria de 01/08: com a máscara Xbox o gamepad virtual
#: é uinput, que declara 8 eixos e 11 botões — **não há onde pôr giroscópio nem
#: touchpad**, e `integrations/virtual_pad.py` recusa o uhid para qualquer
#: sabor que não seja `dualsense`. Não é bug, é a API do Xbox 360; o que faltava
#: era a tela dizer isso.
#:
#: Vibração, microfone e alto-falante NÃO estão na lista de perdas de propósito:
#: a vibração funciona nas duas máscaras, e microfone e alto-falante nem passam
#: pelo gamepad (são PipeWire, e seguem valendo em qualquer máscara).
TEXTO_CUSTO_MASCARA_XBOX: Final[str] = (
    "Nesta máscara o jogo não recebe giroscópio nem touchpad — o controle de "
    "Xbox não tem esses dois, então não há onde eles caberem. Vibração, "
    "microfone e alto-falante continuam funcionando. Escolha DualSense se o "
    "jogo usa mira por movimento ou o touchpad como botão."
)


def texto_do_custo_da_mascara(flavor: object) -> str:
    """A frase de preço da máscara; ``""`` quando não há preço a dizer.

    Devolve vazio para `dualsense` (nada se perde) e para valor desconhecido
    ou ausente — inventar um aviso a partir de payload incompleto seria a
    mesma família de erro que o `or "xbox"` que esta casa já removeu daqui.
    """
    return TEXTO_CUSTO_MASCARA_XBOX if flavor == "xbox" else ""


def _flavor_label(flavor_id: object) -> str:
    """Idem para a aparência do controle no jogo ("xbox" → "Xbox 360")."""
    return dict(_FLAVOR_ITEMS).get(str(flavor_id), str(flavor_id))


# UX-03 (SPRINT-UX-AUTOSWITCH-01): texto do banner de degradação do vpad.
# "Reconecte o controle" foi REFUTADO pela revisão adversarial — a promoção
# uinput→uhid só acontece no boot do daemon (único call site do
# `upgrade_primary_vpad_to_uhid` é o connect, `lifecycle.py`), então reconectar
# NÃO cura nada; o conselho honesto é reiniciar o Hefesto pela aba Sistema.
VPAD_DEGRADED_TEXT = (
    "O gamepad virtual subiu no modo simples: a vibração e a separação do "
    "controle físico não estão garantidas. Reinicie o Hefesto na aba Sistema."
)

# DEDUP-06: um jogador do co-op degradado em uinput com o jogo aberto sob o
# IGNORE congelado é AQUELE jogador com zero controle — o banner do primário
# não o cobria (a dedup quebrada voltava a ser silenciosa, o que o item P0
# proíbe). Sempre banner inline, nunca popover (cosmic-epoch#2497).
VPAD_COOP_DEGRADED_TEXT = (
    "O gamepad virtual de um dos jogadores do co-op subiu no modo simples: "
    "aquele jogador pode ficar sem vibração — e sem controle, se o jogo foi "
    "aberto com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

# DEDUP-06 (achado novo da revisão): Modo Nativo com o físico em Bluetooth é
# estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem sem
# launch option (o backend evdev deferencia ao HIDAPI, que não lê o hidraw BT).
NATIVE_BT_FRAGIL_TEXT = (
    "Modo Nativo com o controle em Bluetooth: alguns jogos não enxergam o "
    "DualSense por BT (limite do SDL). Se o jogo não vir o controle, use o "
    "cabo USB ou volte para a emulação de gamepad."
)


# GUI-05 item 3 (honestidade do dedup): texto do banner "jogo sem wrapper".
# Discreto e pro leigo — diz a consequência (duplicar) e o caminho (aba
# Sistema), sem jargão de env/vdf.
WRAPPER_MISSING_TEXT = (
    "O jogo está rodando sem o hefesto-launch — controles podem duplicar. "
    "Copie as opções na aba Sistema."
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
    (`native_bt_fragil` do state_full), que tem aviso próprio.

    Sem alarme falso: backend ausente/"" é transitório real (vpad subindo, o
    `_gamepad_device` ainda None — o `ipc_handlers` só emite a chave com device
    vivo) e NÃO acende o banner; `dedup_motivo="vpad_ausente"` idem (mesmo
    transitório visto pelo guard); máscara xbox em uinput é o desenho normal;
    fora do modo gamepad não há vpad a avaliar.
    """
    if not isinstance(state, dict):
        return None
    if state.get("native_bt_fragil") is True:
        return NATIVE_BT_FRAGIL_TEXT
    if mode_of_state(state) != MODE_GAMEPAD:
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("flavor") != "dualsense":
        return None
    if gamepad.get("backend") == "uinput":
        return VPAD_DEGRADED_TEXT
    motivo = gamepad.get("dedup_motivo")
    if (
        gamepad.get("dedup_ok") is False
        and isinstance(motivo, str)
        and "jogador" in motivo
    ):
        return VPAD_COOP_DEGRADED_TEXT
    return None


# ONDA-U (U2/U10): texto do "Renumerar agora" quando bloqueado por sessão de
# jogo aberta — mesmo gate do IPC (`identity.renumber`), pra usuária ver o
# "porquê" ANTES de clicar, em vez de levar um {ok: false} sem explicação.
RENUMBER_GAME_OPEN_TEXT = (
    "Feche o jogo para renumerar — evita repintar o controle em uso no meio "
    "da partida."
)


def _renumber_gate_text(state: dict[str, Any] | None) -> str | None:
    """Aviso do "Renumerar agora" bloqueado; ``None`` = liberado — função pura
    (padrão ``vpad_degradation_text``/``wrapper_banner_text``).

    Espelha o MESMO critério do handler de ``identity.renumber``
    (``display_authority == 'game'`` via ``state_full.game_signal.
    authority``) — nunca uma segunda fonte da verdade; se o daemon ainda não
    fiou o sinal (``game_signal`` ausente/authority desconhecida), o botão
    fica liberado (sem alarme falso).
    """
    if not isinstance(state, dict):
        return None
    game_signal = state.get("game_signal")
    if not isinstance(game_signal, dict):
        return None
    if game_signal.get("authority") == "game":
        return RENUMBER_GAME_OPEN_TEXT
    return None


def _format_controller_subtitle(
    transport: object, *, is_primary: bool, battery_pct: object
) -> str:
    """Linha secundária do card de controle (função pura — testável sem GTK).

    FEAT-STATE-PER-CONTROLLER-01: acrescenta a bateria ("· 87%") quando o
    daemon a reportou para ESTE controle; None/ausente fica de fora (nada de
    "0%" falso em controle recém-plugado). `bool` é rejeitado (subclasse de
    int) por blindagem contra payload malformado.
    """
    parts = [str(transport or "?").upper()]
    if is_primary:
        parts.append("primário")
    if isinstance(battery_pct, int) and not isinstance(battery_pct, bool):
        parts.append(f"{battery_pct}%")
    return "  ·  ".join(parts)


def _format_players_hint(controllers: list[dict[str, Any]]) -> str:
    """Frase que substituiu o checkbox de co-op (LEIGO-01) — função pura.

    Só fala quando há o que dizer: com um controle só não existe pergunta a
    responder. E só afirma "N jogadores" quando o daemon de fato numerou N
    jogadores distintos (campo `player`) — enquanto o segundo jogador não subiu,
    o jogo ainda vê um gamepad só e a frase seria mentira.
    """
    if len(controllers) < 2:
        return ""
    players = {
        c.get("player")
        for c in controllers
        if isinstance(c.get("player"), int) and not isinstance(c.get("player"), bool)
    }
    if len(players) < 2:
        return ""
    return f"{len(controllers)} controles = {len(players)} jogadores"


# AUTO-01.2: rótulo base do botão de co-op. Sem contagem enquanto não há dois
# controles — prometer "(2 jogadores)" com um controle na mesa seria a interface
# afirmando o que o jogo não vai confirmar (mesma regra do `_format_players_hint`).
COOP_PREP_LABEL_BASE = "Preparar co-op"

# AUTO-01.2: as três frases do botão. Elas existem porque o co-op tinha efeito
# visível e caminho invisível: a única forma de ligá-lo era `coop on` no
# terminal. Cada uma responde "o que acontece se eu clicar agora?".
COOP_PREP_HINT_UM_CONTROLE = (
    "Ligue o segundo controle (cabo ou Bluetooth) para jogar acompanhada — "
    "cada controle vira um jogador."
)
COOP_PREP_HINT_PRONTO = (
    "Tudo pronto: cada controle já é um jogador. Clique de novo se algum "
    "controle entrou depois."
)
COOP_PREP_HINT_CONVITE = (
    "Um clique faz tudo: entra no modo de jogo, dá um jogador para cada "
    "controle e arruma a numeração."
)


def coop_prep_label(controllers: list[dict[str, Any]]) -> str:
    """Rótulo do botão "Preparar co-op" — função pura (AUTO-01.2).

    A contagem sai dos controles CONECTADOS (é quantos jogadores o co-op vai
    criar), não dos jogadores que já existem: o botão promete o depois, não
    descreve o agora. Com menos de dois, some a contagem — ver
    `COOP_PREP_LABEL_BASE`.
    """
    n = len(controllers)
    if n < 2:
        return COOP_PREP_LABEL_BASE
    return f"{COOP_PREP_LABEL_BASE} ({n} jogadores)"


def coop_prep_hint(state: dict[str, Any] | None, controllers: list[dict[str, Any]]) -> str:
    """Frase abaixo do botão de co-op — função pura (AUTO-01.2).

    Três estados, na ordem em que a usuária os encontra: falta um segundo
    controle; já está tudo de pé (o botão vira "conferir/reaplicar", que é o
    gesto certo quando alguém entra no meio da partida); e o convite, que é o
    caso da instalação nova. Offline devolve vazio — sem daemon não há nada a
    afirmar (mesma regra do `autoswitch_lock_text`).
    """
    if not isinstance(state, dict):
        return ""
    if len(controllers) < 2:
        return COOP_PREP_HINT_UM_CONTROLE
    coop = state.get("coop")
    jogadores = coop.get("players") if isinstance(coop, dict) else None
    ligado = bool(coop.get("enabled")) if isinstance(coop, dict) else False
    if (
        ligado
        and mode_of_state(state) == MODE_GAMEPAD
        and isinstance(jogadores, int)
        and not isinstance(jogadores, bool)
        and jogadores >= 2
    ):
        return COOP_PREP_HINT_PRONTO
    return COOP_PREP_HINT_CONVITE


def _format_controller_title(entry: dict[str, Any]) -> str:
    """Título do card: "Controle 2 — P3" (função pura).

    Recebe a ENTRY inteira, não o número já resolvido: o defeito que isto
    corrige não estava na formatação e sim em quem chamava — o call site
    passava a posição no loop (`idx + 1`), e com um controle só a aba Início
    dizia "Controle 1" enquanto o cabeçalho dizia "Sony 3" sobre esse mesmo
    controle. Com a entry aqui dentro, a origem do número entra no contrato da
    função e o teste cobre os dois.

    LEIGO-01b: o número do JOGADOR vem do daemon e pode divergir do número do
    controle (índices são reusados quando alguém sai e outro entra). Sem número
    de jogador (modo desktop/nativo, jogador ainda subindo) o card só se
    identifica, em vez de inventar um "P" que o jogo não confirma.
    """
    name = f"Controle {numero_do_controle(entry)}"
    player = entry.get("player")
    if isinstance(player, int) and not isinstance(player, bool):
        return f"{name} — P{player}"
    return name


# --- PERFIL-SALVA-TUDO-01/E3: o gesto de MODO chega ao RASCUNHO --------------
#
# A queixa dela, 29/07: *"temos o perfil do jogo tipo pragmata, aí em todas as
# abas fiz alterações e salvei o perfil, aí essas configs de outras abas não
# ficam salvas"*. A onda 2 construiu o lugar de guardar
# (`DraftConfig.with_mode`/`with_suppress`) e deixou escrito que não havia UM
# escritor: `grep -c 'self\.draft'` valia 0 nas abas Início e Emulação. Modo,
# máscara, co-op e "modo jogo" iam só para o estado VIVO do daemon, e o
# "Salvar Perfil" gravava `mode: null` em cima do trabalho dela
# (`pragmata2.json`, medido no disco dela).
#
# A LINHA QUE NÃO PODE SER CRUZADA (HARM-05, e é a razão pela qual a onda 2
# parou aqui de propósito): REGISTRAR não é APLICAR. Quem aplica o modo ao vivo
# é `mode_transition.apply_mode` (e a supressão, `daemon.emulation.suppress`),
# pelo gesto dela e só por ele. O miolo (`_coop_do_rascunho`, `rascunho_com_modo`)
# é função PURA — não toca IPC nem widget — e o único ponto de escrita
# (`registrar_modo_no_rascunho`) não faz nada além de trocar o rascunho da janela:
# eles só anotam o que JÁ está de pé, para o "Salvar Perfil" do rodapé persistir.
# Se um escritor destes disparar aplicação, um toque num gatilho (que também mexe
# no rascunho) passa a poder recriar o vpad ou suspender a emulação no meio da
# partida — exatamente o estrago que o HARM-05 documenta na seção `mouse` do
# "Aplicar". O portão que tranca isso é
# `tests/unit/test_perfil_salva_tudo_registrar_nao_e_aplicar.py`, por AST, para
# valer também onde não há GTK.
#
# Por que aqui, e não na aba Emulação: a Início é a dona do MODO desde o HARM-01
# (`mode_transition`); a Emulação importa daqui em vez de ter cópia própria.


def _coop_do_rascunho(draft: DraftConfig | None) -> bool | None:
    """O ``coop`` que o perfil de origem já dizia, ou ``None`` se ele não diz.

    Sem isto, registrar o modo por causa de uma troca de MÁSCARA carimbaria o
    default do esquema (``coop=True``) num perfil que dizia ``coop: false`` — a
    aba não tem seletor de co-op, então ela nunca pediu essa mudança. É a mesma
    disciplina do passthrough de ``controllers`` no ``to_profile``: o que a
    janela não edita, ela não reescreve.
    """
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
    coop: bool | None = None,
) -> DraftConfig | None:
    """Rascunho com o MODO dela registrado. Pura: NÃO aplica nada (E3).

    ``kind`` é um dos ``mode_transition.MODES`` — os mesmos três ids dos botões
    da Início, que por construção já são o vocabulário de
    ``ProfileModeConfig.kind``. Id desconhecido devolve o rascunho INTACTO em vez
    de levantar: um modo novo tem de passar por `plan_mode_transition` (que
    levanta) antes de existir aqui, e registrar lixo no rascunho seria pior que
    não registrar.

    ``flavor`` só vale no modo gamepad e atravessa `normalizar_gamepad_flavor`
    (MODO-01): máscara desconhecida vira ``None``, que no applier significa
    "mantém a atual" — nunca recriar o vpad por causa de um id que ninguém
    reconhece. ``coop=None`` preserva o que o perfil de origem dizia.
    """
    if draft is None or kind not in MODES:
        return draft
    from hefesto_dualsense4unix.profiles.schema import (
        ProfileModeConfig,
        normalizar_gamepad_flavor,
    )

    secao: dict[str, Any] = {"kind": kind}
    if kind == MODE_GAMEPAD:
        secao["gamepad_flavor"] = normalizar_gamepad_flavor(flavor)
    efetivo = coop if coop is not None else _coop_do_rascunho(draft)
    if efetivo is not None:
        secao["coop"] = efetivo
    return draft.with_mode(ProfileModeConfig.model_validate(secao))


def registrar_modo_no_rascunho(
    janela: Any, kind: str, flavor: object = None, *, coop: bool | None = None
) -> None:
    """Anota na janela o modo que ela acabou de aplicar. Único ponto de escrita.

    Função de MÓDULO, e não método de mixin, por duas medições desta base:

    1. as duas abas precisam do MESMO escritor, e um método em cada mixin seria
       dois donos — com os dois mixins na MESMA classe (`HefestoApp`), nomes
       iguais se sombreariam pela MRO em silêncio;
    2. chamada entre mixins quebra dublê PARCIAL de teste: a onda 2 pagou esse
       preço e o `_HomeStub` de `test_auto01_um_clique_em_vez_de_dez` copia
       handlers avulsos da Início, sem o resto da classe. Uma função não depende
       da montagem do dublê.

    ``getattr`` no rascunho pelo mesmo motivo dos outros escritores
    (`mouse_actions`, `triggers_actions`): janela sem `draft` (dublê, bootstrap
    ainda em voo) não pode virar `AttributeError` dentro do callback do IPC.
    """
    draft = getattr(janela, "draft", None)
    if draft is None:
        return
    novo = rascunho_com_modo(draft, kind=kind, flavor=flavor, coop=coop)
    if novo is not None:
        janela.draft = novo


class HomeActionsMixin(WidgetAccessMixin):
    """Mixin da aba Início (página 0 do notebook)."""

    def install_home_tab(self) -> None:
        """Monta o conteúdo dinâmico da aba Início. Idempotente."""
        from gi.repository import GLib, Gtk

        box = self._get("tab_home_box")
        if box is None or getattr(self, "_home_installed", False):
            return
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False
        # AVISO-VIVO-01: quando a chamada em voo saiu (relógio monotônico) —
        # é o que dá prazo de validade ao latch acima.
        self._home_inflight_since = 0.0
        # AVISO-VIVO-01: última frase de ESTADO que o rodapé recebeu desta aba.
        # `None` = ainda não escrevemos nenhuma (não há afirmação nossa a
        # desfazer); `""` = escrevemos e depois limpamos.
        self._home_lock_toast: str | None = None

        # --- Banner: degradação do vpad (UX-03) -----------------------------
        # Rótulo simples e sempre inline no topo da aba — nada de popup nem
        # popover (cosmic-epoch#2497 fecha qualquer popup no COSMIC). Invisível
        # por padrão; o `_render_home` liga/desliga a partir do
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

        # --- Banner: jogo aberto SEM o wrapper (GUI-05 item 3) --------------
        # Mesmo desenho do banner do vpad: label inline, invisível por padrão;
        # o `_render_home` liga/desliga a partir do
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

        # --- AUTO-01.2: "Preparar co-op" (o único widget vindo do Glade) ----
        # O co-op local — quatro jogadores, a funcionalidade central do projeto
        # — só existia por linha de comando. O botão vive no `main.glade` (é
        # conteúdo fixo, não um card gerado por controle) e aqui ele é
        # RE-POSICIONADO: no arquivo ele precede tudo, mas na tela tem de ficar
        # abaixo dos dois banners (aviso primeiro, ação depois). Tolerante a
        # ausência: Glade antigo/dublê de teste sem os widgets não quebra a aba.
        self._home_coop_prep_btn = self._get("home_coop_prep_btn")
        self._home_coop_prep_hint = self._get("home_coop_prep_hint")
        coop_frame = self._get("home_coop_frame")
        if self._home_coop_prep_btn is not None:
            self._home_coop_prep_btn.connect(
                "clicked", self._on_home_coop_prep_clicked
            )
        if coop_frame is not None:
            with contextlib.suppress(Exception):
                box.reorder_child(coop_frame, 2)

        # --- Frame: modo do sistema ---------------------------------------
        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        frame_mode = Gtk.Frame(label="O que o controle faz agora")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_box.set_margin_top(10)
        mode_box.set_margin_bottom(10)
        mode_box.set_margin_start(12)
        mode_box.set_margin_end(12)

        # wrap=True: FlowBox — lado a lado em janela larga, empilha na estreita
        # (sem estourar o frame sob tiling do COSMIC).
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

        # BUG-HOME-MASK-CLIP-01: co-op e máscara em LINHAS separadas — na mesma
        # HBox o seletor de máscara estourava a largura do frame e era cortado
        # na borda direita (visto ao vivo 2026-07-13). A linha própria dá ao
        # seletor a largura toda para os 2 botões.
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # LEIGO-01: onde havia um checkbox de co-op agora só há INFORMAÇÃO.
        # Ninguém pluga dois controles esperando que os dois movam o MESMO
        # personagem, então não existe escolha a oferecer — cada controle é um
        # jogador, sempre. O texto é preenchido no _render_home a partir dos
        # jogadores que o daemon reporta; com um controle só, fica vazio.
        players_hint = Gtk.Label(label="")
        players_hint.set_xalign(0.0)
        players_hint.set_line_wrap(True)
        players_hint.get_style_context().add_class("dim-label")
        self._home_players_hint = players_hint
        opts.pack_start(players_hint, False, False, 0)

        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # UX (auditoria): rotula pela CONSEQUÊNCIA, não pela tecnologia.
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor = SegmentedSelector(wrap=True)
        flavor.set_items(_FLAVOR_ITEMS)
        flavor.connect("changed", self._on_home_flavor_changed)
        self._home_flavor_selector = flavor
        mask_row.pack_start(flavor, True, True, 0)
        opts.pack_start(mask_row, False, False, 0)

        # MASCARA-CUSTO-01 (01/08): o preço da máscara, dito ANTES do clique.
        #
        # A pergunta dela, literal: *"não sei se o alto-falante, giroscópio,
        # microfone e touchpad na hora de jogar um jogo na Steam vão estar
        # funcionando. Elas precisam funcionar."* A auditoria respondeu com
        # número: com a máscara Xbox o giroscópio e o touchpad **não existem
        # na API** — o gamepad virtual vira uinput, que declara 8 eixos e 11
        # botões e não tem onde pôr IMU nem dedo
        # (`integrations/uinput_gamepad.py`; `virtual_pad.py` recusa o uhid
        # para qualquer sabor que não seja `dualsense`).
        #
        # Isso não era um defeito escondido: era uma escolha sem etiqueta de
        # preço. Seis dos oito perfis de jogo desta casa pediam Xbox, e nada na
        # tela dizia o que se perdia. Agora diz, e diz no lugar do gesto.
        custo = Gtk.Label(label="")
        custo.set_xalign(0.0)
        custo.set_line_wrap(True)
        custo.set_max_width_chars(100)
        custo.get_style_context().add_class("dim-label")
        self._home_flavor_custo = custo
        opts.pack_start(custo, False, False, 0)

        self._home_gamepad_opts = opts
        mode_box.pack_start(opts, False, False, 0)

        origin = Gtk.Label(label="")
        origin.set_xalign(0.0)
        origin.get_style_context().add_class("dim-label")
        self._home_origin_label = origin
        mode_box.pack_start(origin, False, False, 0)

        # FEAT-AUTOSWITCH-LOCK-01 (pedido da mantenedora, 23/07): o cadeado da
        # troca automática de perfil. Marcado = "usa o perfil que EU escolhi,
        # não troca sozinho quando eu abrir um jogo" — vale para qualquer
        # app. Diferente do Modo Nativo (que solta
        # o controle) e do pause (que para tudo): aqui só a DECISÃO de perfil
        # congela; gamepad/co-op/rumble seguem. O estado vem do daemon no
        # _render_home; o toggle persiste e vale na hora.
        lock_check = Gtk.CheckButton(
            label="Não trocar de perfil sozinho ao abrir um jogo"
        )
        lock_check.set_tooltip_text(
            "Congela a troca automática: o perfil que você deixou ativo continua "
            "valendo mesmo ao abrir qualquer jogo. "
            "Desmarque para o Hefesto voltar a escolher o perfil por você."
        )
        lock_check.connect("toggled", self._on_home_autoswitch_lock_toggled)
        self._home_autoswitch_lock = lock_check
        mode_box.pack_start(lock_check, False, False, 0)

        # UX-05 (auditoria 24/07): o cadeado tinha EFEITO visível e CAUSA
        # invisível. Na máquina dela a flag estava ligada desde 24/07 20:42 e o
        # que ela via era "o modo jogo não ativa" — o marcador do checkbox é uma
        # caixinha de 16 px que ninguém relê depois de marcar. Esta linha diz,
        # em texto, o que está acontecendo AGORA e o que continua acontecendo
        # (a exceção da regra de jogo, LOCK-CEDE-01), preenchida no
        # `_render_home` a partir do estado do daemon; some quando destravado.
        lock_hint = Gtk.Label(label="")
        lock_hint.set_xalign(0.0)
        lock_hint.set_line_wrap(True)
        lock_hint.get_style_context().add_class("dim-label")
        # Mesmo desenho dos banners de vpad/wrapper: `no_show_all` para o
        # `show_all()` do build não desfazer o estado que o `_render_home` manda.
        lock_hint.set_no_show_all(True)
        lock_hint.set_visible(False)
        self._home_autoswitch_lock_hint = lock_hint
        mode_box.pack_start(lock_hint, False, False, 0)

        frame_mode.add(mode_box)
        box.pack_start(frame_mode, False, False, 0)

        # --- Frame: controles conectados -----------------------------------
        frame_ctrl = Gtk.Frame(label="Controles")
        ctrl_frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # Cards de tamanho IGUAL (homogeneous): sem isso o card do primário
        # (linha extra "primário") ficava mais largo que o dos demais.
        ctrl_box.set_homogeneous(True)
        ctrl_box.set_margin_top(10)
        ctrl_box.set_margin_start(12)
        ctrl_box.set_margin_end(12)
        self._home_controllers_box = ctrl_box
        ctrl_frame_box.pack_start(ctrl_box, False, False, 0)

        # ONDA-U (U2/U10): "Renumerar agora" — compacta a numeração de
        # exibição (DualSense + externos, IPC `identity.renumber`) para 1..N
        # preservando a ordem relativa. Fica junto dos cards: é aqui que a
        # numeração aparece ("sony 1 / sony 4" com só 2 controles).
        renumber_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        renumber_row.set_margin_start(12)
        renumber_row.set_margin_end(12)
        renumber_row.set_margin_bottom(10)
        renumber_btn = Gtk.Button(label="Renumerar agora")
        renumber_btn.connect("clicked", self._on_home_renumber_clicked)
        self._home_renumber_btn = renumber_btn
        renumber_row.pack_start(renumber_btn, False, False, 0)
        renumber_hint = Gtk.Label(label="")
        renumber_hint.set_xalign(0.0)
        renumber_hint.set_line_wrap(True)
        renumber_hint.get_style_context().add_class("dim-label")
        self._home_renumber_hint = renumber_hint
        renumber_row.pack_start(renumber_hint, False, False, 0)
        ctrl_frame_box.pack_start(renumber_row, False, False, 0)

        frame_ctrl.add(ctrl_frame_box)
        box.pack_start(frame_ctrl, False, False, 0)

        # --- Frame: sessão (desligar de verdade) ---------------------------
        frame_sess = Gtk.Frame(label="Sessão")
        sess_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sess_box.set_margin_top(10)
        sess_box.set_margin_bottom(10)
        sess_box.set_margin_start(12)
        sess_box.set_margin_end(12)

        shutdown_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        # ONDA-U (U1): botão ÚNICO — o `_render_home` troca rótulo/estilo
        # entre "Desligar"/"Ligar" conforme o daemon está online/offline; o
        # clique sempre passa por `_on_home_power_clicked` (dispatcher).
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

        # Poller: só age com a aba Início à vista (identificada pelo id do Glade).
        GLib.timeout_add(HOME_POLL_INTERVAL_MS, self._tick_home_state)

    # --- refresh ----------------------------------------------------------

    def _tick_home_state(self) -> bool:
        notebook = self._get("main_notebook")
        if notebook is not None and id_da_pagina_corrente(notebook) == ABA_INICIO:
            self._refresh_home_tab()
        return True  # timer permanente

    def _refresh_home_tab(self) -> None:
        """Reconcilia o comutador/cards com o estado VIVO do daemon.

        AVISO-VIVO-01: o latch `_home_inflight` tem PRAZO. Sem prazo, uma
        chamada que nunca voltou o deixava ligado para sempre e a aba parava de
        reconciliar em silêncio — foi o que fez uma reconciliação de 2 s levar
        78 s na tela. Passado `HOME_INFLIGHT_TIMEOUT_S` a chamada anterior é
        dada como perdida e uma nova sai; o relógio é lido aqui mesmo, no tick.

        A resposta atrasada da chamada abandonada só desliga o latch de novo
        (`_ok`/`_fail`), o que no pior caso adianta um refresh — nunca trava.
        """
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
        # AVISO-VIVO-01: o rodapé passa a descrever o ESTADO, não o último
        # clique. O toast do cadeado era o registro de "o que eu pedi uma vez" e
        # sobrevivia ao estado: com o cadeado religado por fora da janela, o
        # rodapé seguiu minutos escrito "Troca automática de perfil LIBERADA"
        # enquanto o texto de causa, logo acima, dizia o contrário.
        #
        # Contexto "home" DE PROPÓSITO (e não um contexto próprio): é nele que
        # o handler do cadeado deixa a frase, e na Gtk.Statusbar o `pop` de um
        # contexto meu não apagaria a dele — apenas faria a mensagem antiga
        # RESSURGIR de baixo da pilha. Para não comer o toast das outras ações
        # ("Numeração compactada...", "Co-op pronto."), a escrita é por BORDA:
        # só quando a frase de estado MUDA de valor — e nesse instante o que
        # estava escrito ali já está velho de qualquer jeito.
        aviso_estado = autoswitch_lock_text(state)
        anterior = getattr(self, "_home_lock_toast", None)
        if aviso_estado != anterior:
            self._home_lock_toast = aviso_estado
            # `getattr` defensivo pelo mesmo motivo do cadeado/co-op: os dublês
            # de teste do `_render_home` não montam a statusbar inteira.
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
                # BUG-HOME-OFFLINE-STALE-01: sem limpar, descrição/origem/
                # opções do gamepad ficavam do último estado online.
                self._home_mode_desc.set_text("")
                self._home_origin_label.set_text("")
                self._home_gamepad_opts.set_visible(False)
                # UX-03: offline não é degradação do vpad — o banner some junto.
                self._home_vpad_banner.set_visible(False)
                # GUI-05: idem para o aviso "jogo sem wrapper".
                self._home_wrapper_banner.set_visible(False)
                self._render_home_controllers([])
                # ONDA-U (U1): toggle in-place — o botão de "Desligar" vira
                # "Ligar o Hefesto" bem aqui, nada de mandar pra aba Sistema.
                self._home_offline = True
                self._home_shutdown_btn.set_label(_BTN_LABEL_OFFLINE)
                self._home_shutdown_btn.get_style_context().remove_class(
                    "destructive-action"
                )
                self._home_shutdown_btn.get_style_context().add_class(
                    "suggested-action"
                )
                # ONDA-U (U2/U10): sem daemon, "Renumerar agora" não tem quem
                # atenda o IPC.
                self._home_renumber_btn.set_sensitive(False)
                self._home_renumber_hint.set_text("")
                # AUTO-01.2: idem para "Preparar co-op" — os três passos são
                # IPC, e sem daemon nenhum deles chega a lugar nenhum.
                self._render_coop_prep(None, [])
                # FEAT-AUTOSWITCH-LOCK-01: sem daemon, o cadeado não tem estado.
                _lock = getattr(self, "_home_autoswitch_lock", None)
                if _lock is not None:
                    _lock.set_sensitive(False)
                # UX-05: idem para a frase — offline não é "destravado", é
                # "não sei"; afirmar qualquer das duas coisas seria mentira.
                _lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)
                if _lock_hint is not None:
                    _lock_hint.set_text("")
                    _lock_hint.set_visible(False)
                return
            assert state is not None
            selector.set_sensitive(True)
            self._home_flavor_selector.set_sensitive(True)
            # FEAT-AUTOSWITCH-LOCK-01: reflete o cadeado do daemon (sob guard —
            # set_active emite "toggled", que reenviaria o IPC em loop).
            _lock = getattr(self, "_home_autoswitch_lock", None)
            if _lock is not None:
                _lock.set_sensitive(True)
                _lock.set_active(bool(state.get("autoswitch_locked", False)))
            # UX-05: a CAUSA fica visível junto do efeito, em texto.
            _lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)
            if _lock_hint is not None:
                aviso_lock = autoswitch_lock_text(state)
                _lock_hint.set_text(aviso_lock)
                _lock_hint.set_visible(bool(aviso_lock))
            self._home_session_label.set_text("")
            # ONDA-U (U1): online devolve o botão único ao estado "Desligar".
            self._home_offline = False
            self._home_shutdown_btn.set_label(_BTN_LABEL_ONLINE)
            self._home_shutdown_btn.get_style_context().remove_class(
                "suggested-action"
            )
            self._home_shutdown_btn.get_style_context().add_class(
                "destructive-action"
            )
            # ONDA-U (U2/U10): gate do botão espelha o do IPC — jogo aberto
            # desabilita e explica o porquê ANTES do clique.
            aviso_renumerar = _renumber_gate_text(state)
            self._home_renumber_btn.set_sensitive(aviso_renumerar is None)
            self._home_renumber_hint.set_text(aviso_renumerar or "")

            gamepad = state.get("gamepad_emulation") or {}
            # HARM-01: a leitura do modo também tem um dono só — a Emulação
            # deriva do MESMO payload pela MESMA regra, então as duas abas não
            # podem mais discordar sobre em que modo o sistema está.
            mode = mode_of_state(state) or "desktop"
            selector.set_active_id(mode)
            self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode, ""))
            self._home_gamepad_opts.set_visible(mode == "gamepad")
            self._home_gamepad_opts.set_no_show_all(mode != "gamepad")

            # AUTO-01.3: o dono da máscara é o DAEMON — a GUI só ECOA o que ele
            # reporta (`gamepad_emulation.flavor`, presente sempre que o daemon
            # está vivo). O `or "xbox"` que estava aqui era um segundo dono do
            # valor: com o campo ausente a aba mostrava Xbox e, no clique
            # seguinte, MANDAVA Xbox — trocando a máscara do daemon por causa de
            # um payload incompleto. Sem valor conhecido, o seletor fica como
            # está e o plano de transição sai sem o campo (ver
            # `plan_mode_transition`), preservando a máscara vigente.
            flavor = gamepad.get("flavor")
            if isinstance(flavor, str) and flavor:
                self._home_flavor_selector.set_active_id(flavor)
            # MASCARA-CUSTO-01: o preço da máscara vigente, embaixo do seletor.
            custo = getattr(self, "_home_flavor_custo", None)
            if custo is not None:
                texto = texto_do_custo_da_mascara(flavor)
                custo.set_text(texto)
                custo.set_visible(bool(texto))
                custo.set_no_show_all(not texto)

            # UX-03: banner de degradação do vpad — visível SÓ quando a máscara
            # DualSense caiu no backend uinput (função pura decide; backend
            # ausente/"" é transitório e não acende nada).
            aviso_vpad = vpad_degradation_text(state)
            if aviso_vpad:
                self._home_vpad_banner.set_text(aviso_vpad)
            self._home_vpad_banner.set_visible(bool(aviso_vpad))

            # GUI-05 item 3: banner "jogo sem wrapper" — só o False LITERAL de
            # `gamepad_emulation.wrapper_used` acende (função pura decide).
            aviso_wrapper = wrapper_banner_text(state)
            if aviso_wrapper:
                self._home_wrapper_banner.set_text(aviso_wrapper)
            self._home_wrapper_banner.set_visible(bool(aviso_wrapper))

            origin_bits: list[str] = []
            if state.get("native_mode") and state.get("native_mode_origin") == "profile":
                origin_bits.append("nativo ligado pelo perfil ativo")
            if state.get("mode_from_profile") == "gamepad":
                origin_bits.append("gamepad ligado pelo perfil ativo")
            # LEIGO-01: a contagem de jogadores saiu daqui — dizia "co-op: N
            # jogador(es)" (jargão) e agora mora na frase do próprio bloco do
            # gamepad, contada a partir dos jogadores que o daemon numerou.
            self._home_origin_label.set_text(" · ".join(origin_bits))

            # HARM-CARD-FANTASMA-01: `describe_controllers` devolve UMA entrada
            # com connected=False quando não há nenhum controle — sem filtrar, a
            # aba inventava um card "Controle 1 — P1 · ?" com o cabo na mesa. A
            # aba Status (_connected_controllers) e o applet já filtravam; a
            # Início era a única que não.
            connected = [
                c
                for c in (state.get("controllers") or [])
                if isinstance(c, dict) and c.get("connected")
            ]
            self._home_players_hint.set_text(_format_players_hint(connected))
            # AUTO-01.2: o botão de co-op fala a partir dos MESMOS controles
            # conectados que os cards mostram — uma fonte só para a contagem.
            self._render_coop_prep(state, connected)
            self._render_home_controllers(
                connected,
                grab_state=state.get("primary_grab_state"),
                gamepad_on=bool(gamepad.get("enabled")),
            )
            # Gtk referenciado para manter o import local óbvio (sem uso direto
            # neste ramo; os cards usam via _render_home_controllers).
            _ = Gtk
        finally:
            self._home_guard = False

    def _render_coop_prep(
        self, state: dict[str, Any] | None, controllers: list[dict[str, Any]]
    ) -> None:
        """Reconcilia o botão "Preparar co-op" com o estado vivo (AUTO-01.2).

        Rótulo e frase saem das funções puras (`coop_prep_label`/
        `coop_prep_hint`); aqui só há widget. `getattr` defensivo pelo mesmo
        motivo do cadeado de autoswitch: os dublês de teste do `_render_home` e
        um Glade sem os widgets novos não podem derrubar a aba inteira.
        """
        btn = getattr(self, "_home_coop_prep_btn", None)
        hint = getattr(self, "_home_coop_prep_hint", None)
        if btn is not None:
            btn.set_label(coop_prep_label(controllers))
            btn.set_sensitive(state is not None)
        if hint is not None:
            hint.set_text(coop_prep_hint(state, controllers))

    def _render_home_controllers(
        self,
        controllers: list[dict[str, Any]],
        *,
        grab_state: str | None = None,
        gamepad_on: bool = False,
    ) -> None:
        from gi.repository import Gtk

        box = self._home_controllers_box
        for child in box.get_children():
            box.remove(child)
        if not controllers:
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
            # LEIGO-01b: nem o número do jogador nem o do controle saem da
            # posição na lista — o primeiro vem do daemon, o segundo do slot de
            # sessão, o mesmo que o resto da GUI mostra.
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
            # LEIGO-02: aqui saía o fim do MAC ("…c311f0"). Ele não serve a
            # nenhuma tarefa dela: o número não está gravado no controle
            # físico, então não há como casar card com aparelho por ele. Quem
            # distingue os controles na mesa é a COR da lightbar e o LED de
            # jogador — o card já mostra o número do jogador.
            if is_primary and gamepad_on and grab_state == "failed":
                warn = Gtk.Label(label="grab falhou — input pode dobrar no jogo")
                warn.set_xalign(0.0)
                warn.get_style_context().add_class("hefesto-dualsense4unix-status-err")
                card.pack_start(warn, False, False, 0)
            box.pack_start(card, True, True, 0)
        box.show_all()

    # --- handlers -----------------------------------------------------------

    def _on_home_mode_changed(self, selector: Any) -> None:
        # "changed" do SegmentedSelector é sem argumentos (como GtkComboBox);
        # o id ativo vem de get_active_id() — BUG-HOME-SEGMENTED-SIGNATURE-01.
        mode_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not mode_id:
            return
        self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode_id, ""))

        def _done(_result: Any) -> bool:
            # PERFIL-SALVA-TUDO-01/E3: o modo que ela acabou de escolher entra no
            # rascunho AQUI — depois de o daemon confirmar, e nunca antes: o
            # rascunho descreve o que ficou de pé, não uma intenção que pode ter
            # falhado. Registrar não aplica nada (ver `rascunho_com_modo`).
            registrar_modo_no_rascunho(
                self, mode_id, self._home_flavor_selector.get_active_id()
            )
            # LEIGO-02: o toast dizia "Modo aplicado: gamepad" — o id interno,
            # uma palavra que não existe em botão nenhum. Ecoa o rótulo que ela
            # acabou de clicar.
            self._status_toast("home", f"Pronto — agora: {_mode_label(mode_id)}")
            self._refresh_home_tab()
            return False

        def _fail(exc: Exception) -> bool:
            self._status_toast("home", f"Falha ao mudar o modo ({exc})")
            self._refresh_home_tab()
            return False

        # HARM-01: a sequência (sair do nativo antes de ligar o gamepad, com a
        # folga de 2s) mora em `mode_transition` — a Início é a dona do modo,
        # não da mecânica; a Emulação chama exatamente o mesmo caminho.
        apply_mode(
            mode_id,
            flavor=self._home_flavor_selector.get_active_id(),
            on_done=_done,
            on_fail=_fail,
        )

    def _on_home_flavor_changed(self, selector: Any) -> None:
        flavor_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not flavor_id:
            return
        mode = self._home_mode_selector.get_active_id()
        if mode != "gamepad":
            return

        def _done(_result: Any) -> bool:
            # PERFIL-SALVA-TUDO-01/E3: a máscara é a segunda metade da seção
            # `mode` do perfil — o `kind` aqui é necessariamente "gamepad" (o
            # gate logo acima já devolveu em qualquer outro modo).
            registrar_modo_no_rascunho(self, MODE_GAMEPAD, flavor_id)
            # LEIGO-02: era "Máscara do gamepad: xbox" — jargão + id cru.
            self._status_toast(
                "home", f"O jogo agora vê: {_flavor_label(flavor_id)}"
            )
            return False

        def _fail(_exc: Exception) -> bool:
            # EMU-06: sem callback de falha, a troca podia falhar em silêncio e
            # o botão "pulava" de volta ~2s depois (o poller reconcilia) sem
            # nenhuma explicação. Avisa e reconcilia agora, como o seletor de
            # modo.
            self._status_toast(
                "home",
                "Não consegui trocar o que o jogo vê — o Hefesto pode estar "
                "desligado.",
            )
            self._refresh_home_tab()
            return False

        call_async(
            "gamepad.emulation.set",
            {"enabled": True, "flavor": flavor_id},
            _done,
            _fail,
            timeout_s=_MODE_IPC_TIMEOUT_S,
        )

    def _on_home_coop_prep_clicked(self, _button: object) -> None:
        """AUTO-01.2: um clique prepara o co-op inteiro.

        O que ela fazia até aqui para jogar acompanhada: escolher "Jogar pelo
        Hefesto" na Início, abrir um terminal para `coop on` (o co-op não tinha
        botão nenhum) e voltar para renumerar os controles. Agora é um botão, e
        a sequência tem dono único (`mode_transition.plan_coop_prep`) — a mesma
        regra do HARM-01 para a troca de modo.

        Só o passo do co-op reporta (ver `apply_coop_prep`): a renumeração é
        recusada pelo daemon com jogo aberto e não pode virar "falha ao
        preparar o co-op" quando os jogadores já subiram. O refresh no fim é o
        que faz os cards e a frase contarem a verdade sem esperar o poller.
        """

        def _done(resultado: Any) -> bool:
            # PERFIL-SALVA-TUDO-01/E3: "Preparar co-op" é o ÚNICO gesto da janela
            # que diz `coop` — os outros preservam o que o perfil já dizia. Aqui
            # ela pediu co-op na mão, então o `True` é dela, não default do
            # esquema (a distinção que o LEIGO-01 pagou para aprender).
            registrar_modo_no_rascunho(
                self,
                MODE_GAMEPAD,
                self._home_flavor_selector.get_active_id(),
                coop=True,
            )
            jogadores = (
                resultado.get("players") if isinstance(resultado, dict) else None
            )
            if isinstance(jogadores, int) and not isinstance(jogadores, bool):
                self._status_toast(
                    "home", f"Co-op pronto — {jogadores} jogador(es)."
                )
            else:
                self._status_toast("home", "Co-op pronto.")
            self._refresh_home_tab()
            return False

        def _fail(_exc: Exception) -> bool:
            self._status_toast(
                "home",
                "Não consegui preparar o co-op — o Hefesto pode estar desligado.",
            )
            self._refresh_home_tab()
            return False

        apply_coop_prep(
            flavor=self._home_flavor_selector.get_active_id(),
            on_done=_done,
            on_fail=_fail,
        )

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
            # O daemon devolve o estado efetivo; se veio None (offline), a
            # próxima renderização reconverge com o estado real.
            if resultado is None:
                self._status_toast(
                    "home", "O Hefesto está desligado — o cadeado não foi aplicado."
                )
            else:
                self._status_toast(
                    "home",
                    "Troca automática de perfil CONGELADA — o perfil que você "
                    "escolheu fica." if resultado else
                    "Troca automática de perfil LIBERADA — o Hefesto volta a "
                    "escolher o perfil ao abrir cada jogo.",
                )
            return False

        ipc_bridge.run_in_thread(
            lambda: ipc_bridge.autoswitch_lock_set(desejado), on_success=_fim
        )

    def _on_home_renumber_clicked(self, _button: object) -> None:
        """U2/U10: dispara ``identity.renumber`` e traduz o resultado em toast.

        Contrato fixado com o daemon (sprint ONDA-U): método
        ``identity.renumber``, args ``{}``. Retorno
        ``{ok: true, renumbered: {uniq: slot}}`` ou ``{ok: false, reason}``.
        O gate visual (``_render_home``/``_renumber_gate_text``) já desabilita
        o botão com jogo aberto, mas o handler NÃO confia só nisso — o
        daemon decide de verdade (o estado do poll pode estar defasado em
        até ``HOME_POLL_INTERVAL_MS``); aqui só se traduz a resposta.
        """

        def _ok(result: Any) -> bool:
            if not isinstance(result, dict) or not result.get("ok"):
                reason = result.get("reason") if isinstance(result, dict) else None
                if reason == "sessao_de_jogo_aberta":
                    msg = "Feche o jogo antes de renumerar."
                else:
                    msg = "Não consegui renumerar — tente de novo."
                self._status_toast("home", msg)
                return False
            renumerados = result.get("renumbered")
            n = len(renumerados) if isinstance(renumerados, dict) else 0
            if n:
                self._status_toast(
                    "home",
                    f"Numeração compactada — {n} controle(s) renumerado(s).",
                )
            else:
                self._status_toast("home", "Numeração já estava compacta.")
            self._refresh_home_tab()
            return False

        def _fail(_exc: Exception) -> bool:
            self._status_toast(
                "home",
                "Não consegui renumerar — o Hefesto pode estar desligado.",
            )
            return False

        call_async("identity.renumber", {}, _ok, _fail, timeout_s=_MODE_IPC_TIMEOUT_S)

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
        # GUI-05/P5: sem a classe de tema o diálogo herdava o claro do sistema
        # (precedente: gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
        dialog.format_secondary_text(
            "O controle continua funcionando nos jogos, mas sem luzes, sem "
            "gatilhos e sem os seus ajustes.\n"
            "Esta janela continua aberta e NÃO liga o Hefesto de novo sozinha "
            # ONDA-U (U1): "Ligar o Hefesto" agora é o MESMO botão desta aba
            # (toggle in-place) — o aviso não manda mais pra aba Sistema.
            "— para ligar de novo, clique em \"Ligar o Hefesto\" aqui mesmo, "
            "nesta aba."
        )

        def _on_response(dlg: Any, response: int) -> None:
            dlg.destroy()
            if response != Gtk.ResponseType.YES:
                return
            # FEAT-GUI-HOME-TAB-01: o ensure_daemon_running respeita este flag —
            # sem ele, reabrir/atualizar a GUI ressuscitava o daemon parado.
            self._user_stopped_daemon = True

            def _worker_ok(result: Any) -> bool:
                # BUG-HOME-SHUTDOWN-FALSE-OK-01: systemctl com rc!=0 (sem
                # sessão systemd, daemon avulso) NÃO desligou nada — o toast
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
        dialog.show()


__all__ = [
    "ABA_INICIO",
    "COOP_PREP_HINT_CONVITE",
    "COOP_PREP_HINT_PRONTO",
    "COOP_PREP_HINT_UM_CONTROLE",
    "COOP_PREP_LABEL_BASE",
    "HOME_POLL_INTERVAL_MS",
    "RENUMBER_GAME_OPEN_TEXT",
    "VPAD_DEGRADED_TEXT",
    "WRAPPER_MISSING_TEXT",
    "HomeActionsMixin",
    "coop_prep_hint",
    "coop_prep_label",
    "id_da_pagina",
    "id_da_pagina_corrente",
    "vpad_degradation_text",
    "wrapper_banner_text",
]
