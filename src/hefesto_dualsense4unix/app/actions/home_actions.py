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
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_IPC_TIMEOUT_S,
    MODES,
    STATE_IPC_TIMEOUT_S,
    mode_of_state,
)

# AGORA-E-DEPOIS-01: os textos do "depois" moram no módulo puro — a aba Início e
# o diálogo do rodapé dizem as mesmas palavras porque leem a mesma fonte, e o
# teste os alcança sem abrir janela nenhuma. (O `apply_mode` saiu deste import
# junto com o IPC dos cliques: quem aplica agora é o rodapé.)
from hefesto_dualsense4unix.app.actions.relancar import (
    TOAST_ESCOLHA_ANOTADA,
    TOAST_ESCOLHA_DESFEITA,
    texto_do_pendente,
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
#
# UX-MODE-TERMS-02 (06/08/2026, decisão dela, literal: *"Jogar direto é péssimo
# também. Já tinha pedido pra deixarmos: Conexão Nativa (Sony)"*): o terceiro
# rótulo era "Jogar direto (Sony)" e CADUCOU. Ele dizia o gesto ("jogar") e não
# a coisa — os outros dois já dizem para ONDE o controle fala ("o PC", "o
# Hefesto"), e "direto" não completava a frase. "Conexão Nativa (Sony)" nomeia
# o que de fato acontece: o Hefesto solta o controle e o jogo fala com o
# DualSense físico, sem intermediário (docs/usage/modos.md).
#
# É SÓ o rótulo: o id `native` continua sendo chave de perfil, do IPC e da CLI
# (`native on`) — renomeá-lo quebraria perfil salvo em disco. Esta lista é a
# frase-dona; a aba Perfis (`profiles_actions._MODE_KIND_ITEMS`) e o applet
# COSMIC (`packaging/cosmic-applet/src/app.rs`, `let entries`) repetem os mesmos
# rótulos, e o `test_vocabulario_das_quatro_superficies.py` reprova quem mudar
# um lado só.
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Conexão Nativa (Sony)"),
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
    # NOTA DATADA (MODO-QUE-NAO-CONTROLA-01, 09/08/2026): esta frase mandava
    # para "as abas Mouse e Teclado", e essas duas abas NÃO EXISTEM desde a
    # PALAVRA-01 (28/07, pedido dela: o nome curto) — as duas colunas moram numa
    # aba só, "Navegação" (`tab_navegacao_dsx` no glade, com `tab_mouse` e
    # `tab_keyboard` como os boxes de dentro). Caducou naquele dia e ficou
    # apontando para um lugar que a janela não tem — o que só apareceu agora,
    # porque a linha logo abaixo passou a dizer ONDE ligar o mouse e as duas
    # não podiam divergir.
    "desktop": (
        "O controle vira mouse/teclado do computador (ajustes na aba "
        "Navegação)."
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
# não é mais botão de lugar nenhum e "Conexão Nativa (Sony)" já é um dos botões
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


#: COOP-SEM-INTERRUPTOR-01 (06/08/2026): rótulo do botão que era "Renumerar
#: agora". Ele deixou de ser só faxina de numeração: agora RECONCILIA os
#: jogadores primeiro (`coop.sync`) e compacta a numeração depois
#: (`identity.renumber`). A troca de nome é a entrega 5 do roteiro — sem ela,
#: tirar "Preparar co-op" da tela tiraria dela o único gesto capaz de trazer de
#: volta o jogador que nasce e morre em dois segundos.
RECONCILIAR_LABEL = "Reconciliar jogadores"

# ONDA-U (U2/U10) + COOP-SEM-INTERRUPTOR-01 (06/08): texto exibido quando há
# jogo aberto. NOTA DATADA — até 06/08/2026 este aviso DESABILITAVA o botão,
# porque o gesto era só `identity.renumber` e o daemon o recusa com jogo aberto
# (repintar o LED do controle em uso no meio da partida é o erro que a NUMA-03
# fechou). Com a reconciliação dos jogadores no mesmo botão, desabilitar
# passaria a esconder o gesto EXATAMENTE quando ela mais precisa dele — o P2 cai
# DURANTE a partida. Então o aviso vira o que sempre deveria ter sido: uma
# explicação do que NÃO vai acontecer, com o botão de pé.
RECONCILIAR_JOGO_ABERTO_TEXT = (
    "Com o jogo aberto os jogadores voltam, mas a numeração não muda — "
    "evita repintar o controle em uso no meio da partida."
)


def _reconciliar_gate_text(state: dict[str, Any] | None) -> str | None:
    """Aviso do "Reconciliar jogadores"; ``None`` = nada a dizer — função pura
    (padrão ``vpad_degradation_text``/``wrapper_banner_text``).

    Espelha o MESMO critério do handler de ``identity.renumber``
    (``display_authority == 'game'`` via ``state_full.game_signal.
    authority``) — nunca uma segunda fonte da verdade; se o daemon ainda não
    fiou o sinal (``game_signal`` ausente/authority desconhecida), não há aviso
    (sem alarme falso).
    """
    if not isinstance(state, dict):
        return None
    game_signal = state.get("game_signal")
    if not isinstance(game_signal, dict):
        return None
    if game_signal.get("authority") == "game":
        return RECONCILIAR_JOGO_ABERTO_TEXT
    return None


# MODO-QUE-NAO-CONTROLA-01 (09/08/2026) — medido com ela ao vivo, às 23h50.
#
# Ela escolheu "Controlar o PC", clicou no "Aplicar" e relatou: *"cliquei em
# aplicar e nada"*. O modo ENTROU (o journal prova: `native_mode_changed
# native=False`, `gamepad_controller_grab state=off`, `mouse_preference_restored
# enabled=False ok=True`) — e o controle não movia o cursor, porque a
# preferência de mouse persistida dela estava desligada.
#
# O daemon fez o certo, e continua fazendo: `mouse.emulation.restore` RESTAURA a
# preferência dela (HARM-06), não impõe uma. Ligar o mouse por conta própria
# atropelaria o interruptor que ela mesma desligou na aba Navegação — e "a
# vontade na GUI prevalece sempre" (decisão dela, 09/08) vale para o gesto do
# interruptor tanto quanto para o gesto do modo.
#
# O que estava errado era o SILÊNCIO: o modo cujo nome promete controlar o PC
# entrava sem controlar nada e nenhuma superfície dizia por quê. Ela só
# descobriu quando alguém leu o journal por ela.
#
# Estas frases são o mesmo padrão do `_reconciliar_gate_text` logo acima: dizem
# o que NÃO vai acontecer e onde é o botão — sem impedir gesto nenhum. E são o
# espelho do `mouse_actions.MODE_GATE_HINT`, que já mandava a usuária de lá para
# cá ("Só dá para ligar o mouse em \"Controlar o PC\" (aba Início)"); faltava a
# volta.
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
    """Frase única do "Reconciliar jogadores" — função pura (06/08/2026).

    Um clique, dois passos, UM toast: anunciar duas vezes o mesmo gesto seria
    ruído, e anunciar só um deles esconderia metade do que aconteceu. A ordem
    da frase é a ordem dos passos — jogadores primeiro (é o que ela veio
    buscar), numeração depois (é acabamento).

    ``resultado_renumber`` é o retorno cru do ``identity.renumber`` (ou ``None``
    quando o IPC do acabamento falhou): a recusa por jogo aberto NÃO vira falha
    do gesto, pela mesma razão do ``reported_step_index`` — com os jogadores já de
    pé, um toast de erro seria a interface mentindo.
    """
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


# LÁPIDE — COOP-SEM-INTERRUPTOR-01 (06/08/2026). Aqui moravam o rótulo
# (`COOP_PREP_LABEL_BASE`), as três frases (`COOP_PREP_HINT_*`) e as duas
# funções puras (`coop_prep_label`/`coop_prep_hint`) do botão "Preparar co-op"
# da AUTO-01.2. Todas descreviam a mesma pergunta — *"o que acontece se eu
# clicar agora?"* — e a pergunta deixou de existir: cada controle conectado já
# é um jogador, sempre. Quem conta os jogadores hoje é `_format_players_hint`,
# acima, e a contagem vem do `daemon.state_full` (campo `player` por controle,
# resolvido por `subsystems/coop.resolve_player_numbers`) — nunca de um cache
# de outra aba.


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
    O ``coop`` do perfil de origem é SEMPRE preservado (`_coop_do_rascunho`) —
    a janela nunca o edita. COOP-SEM-INTERRUPTOR-01 (06/08/2026): havia aqui um
    parâmetro ``coop`` para o único gesto que o escrevia na mão, o botão
    "Preparar co-op". O botão saiu (o co-op deixou de ser opção) e o parâmetro
    foi junto: um argumento que ninguém mais passa é a mesma dívida que esta
    casa persegue — código que ficou depois de o motivo morrer.
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
    efetivo = _coop_do_rascunho(draft)
    if efetivo is not None:
        secao["coop"] = efetivo
    return draft.with_mode(ProfileModeConfig.model_validate(secao))


def reconciliar_pendente(janela: Any) -> dict[str, str]:
    """A escolha dela MENOS o que o daemon já alcançou. Devolve o que sobra.

    AGORA-E-DEPOIS-01 (08/08/2026). Uma pendência só existe enquanto DIVERGE do
    vigente: se o daemon chegou ao que ela escolheu — por esta janela, pela CLI,
    pelo applet ou por uma troca de perfil —, não há mais nada a aplicar, e
    manter a linha "vai mudar para:" na tela seria a janela prometendo uma
    mudança que já aconteceu.

    Roda no `_render_home` (a cada tique) e no clique, com a MESMA regra nos
    dois lugares porque é a MESMA pergunta. Escreve em ``_escolha_pendente`` de
    propósito: a limpeza tem de sobreviver ao retorno, senão a próxima leitura
    ressuscita o que este tique acabou de dar por resolvido.

    Função de MÓDULO pelas duas razões já pagas por esta base em
    `registrar_modo_no_rascunho`: o rodapé precisa do MESMO reconciliador que a
    Início (um método em cada mixin seriam dois donos, sombreados em silêncio
    pela MRO da `HefestoApp`), e chamada entre mixins quebra dublê PARCIAL de
    teste — o `_HomeStub` copia handlers avulsos, sem o resto da classe.
    """
    pendente = dict(getattr(janela, "_escolha_pendente", None) or {})
    if "modo" in pendente and pendente["modo"] == getattr(
        janela, "_modo_vigente_do_daemon", None
    ):
        pendente.pop("modo")
    if "mascara" in pendente and pendente["mascara"] == getattr(
        janela, "_mascara_vigente_do_daemon", None
    ):
        pendente.pop("mascara")
    janela._escolha_pendente = pendente or None
    return pendente


def render_pendente(janela: Any, *, visivel: bool = True) -> None:
    """Escreve (ou apaga) a linha do que ela escolheu e ainda não aplicou.

    ``visivel=False`` esconde a linha SEM tocar na escolha — é o que o ramo
    offline usa: sem daemon não há como aplicar, mas o que ela decidiu não pode
    evaporar por causa de um engasgo de IPC.

    Sem o rótulo montado (dublê de teste, aba nunca instalada) reconcilia
    assim mesmo e volta: o estado da escolha é verdade do modelo, não do widget.
    """
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
    # Depois da reconciliação: se ela voltou ao que já está valendo, a pendência
    # se desfez sozinha e o rodapé tem de dizer ISSO.
    ficou = bool(getattr(janela, "_escolha_pendente", None))
    toast = getattr(janela, "_status_toast", None)
    if callable(toast):
        toast("home", TOAST_ESCOLHA_ANOTADA if ficou else TOAST_ESCOLHA_DESFEITA)


def registrar_modo_no_rascunho(
    janela: Any, kind: str, flavor: object = None
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
    novo = rascunho_com_modo(draft, kind=kind, flavor=flavor)
    if novo is not None:
        janela.draft = novo


class HomeActionsMixin(WidgetAccessMixin):
    """Mixin da aba Início (página 0 do notebook)."""

    #: O-DESLIGADO-DE-ONTEM-01: última leitura do opt-out de gamepad no disco.
    #: Ele é um arquivo-flag (`gamepad_disabled.flag`) e muda por GESTO dela, o
    #: que é raro; o `_render_home` roda junto do estado, a cada tique. Ler o
    #: disco ali dentro seria um `stat()` por repintura para responder uma
    #: pergunta que muda uma vez por sessão — o poller cego que esta casa já
    #: pagou uma vez (104 % de um núcleo). Quem atualiza é o tique lento.
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
        # AGORA-E-DEPOIS-01 (08/08/2026): o que ELA escolheu e ainda não
        # aplicou. `None` = nada pendente, e a caixa espelha o vigente do
        # daemon, exatamente como sempre fez. Chaves possíveis: "modo" e
        # "mascara" — os dois campos cujo efeito só chega ao jogo na ABERTURA.
        #
        # Isto NÃO revoga a AUTO-01.3 ("o dono da máscara é o DAEMON, a GUI só
        # ECOA"): não há dois donos do MESMO valor. Há o valor VIGENTE (do
        # daemon, que a caixa continua ecoando quando não há pendência) e o
        # valor ESCOLHIDO (dela, que mora aqui até o "Aplicar" do rodapé).
        #
        # A declaração de tipo mora em `base.WidgetAccessMixin` (o rodapé também
        # toca este campo, e dois mixins da mesma classe não podem declará-lo
        # cada um do seu jeito); aqui é só a partida de cada sessão da aba.
        self._escolha_pendente = None
        # O vigente do daemon, guardado no mesmo tique do `_render_home` —
        # é contra ele que uma escolha se cancela sozinha (escolher o que já
        # está valendo não é pendência nenhuma). O do modo mora em
        # `_modo_vigente_do_daemon`, que a aba Perfis já usava.
        self._mascara_vigente_do_daemon: str | None = None
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

        # --- Banner: a emulação está desligada por escolha ANTERIOR ---------
        # O-DESLIGADO-DE-ONTEM-01 (10/08/2026). Mesmo desenho dos dois vizinhos.
        # Ele existe porque o estado mais confuso deste produto não é o
        # quebrado — é o inerte por decisão antiga: nada falha, nada avisa, e o
        # giroscópio simplesmente não chega ao jogo. Ver
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

        # LÁPIDE — COOP-SEM-INTERRUPTOR-01 (06/08/2026): aqui morava a fiação do
        # "Preparar co-op" (o único widget que vinha do Glade nesta aba, e que
        # este trecho re-posicionava abaixo dos banners). Ver a lápide do
        # `main.glade`: preparar o co-op deixou de ser gesto porque o co-op
        # deixou de ser opção. Com isto a aba Início passa a ser 100% código.

        # --- Frame: modo do sistema ---------------------------------------
        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        # AGORA-E-DEPOIS-01 (08/08/2026): a caixa se chamava "O que o controle
        # faz agora" — e era MENTIRA, no defeito 8 da OITO-DEFEITOS-01. Nada do
        # que está aqui dentro vale agora: o jogo lê a configuração UMA VEZ, na
        # abertura (`assets/hefesto-launch.sh:320`, `exec env "$@"`), então modo
        # e máscara só o alcançam quando ele abre. Cor, brilho, gatilho,
        # vibração e microfone — esses sim mudam na hora — moram em outras abas.
        #
        # O nome sai do desenho que ela aprovou em 08/08, e deriva do produto:
        # ela recusa vocabulário novo que não venha do que já existe.
        frame_mode = Gtk.Frame(label="Quando o jogo abrir")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_box.set_margin_top(10)
        mode_box.set_margin_bottom(10)
        mode_box.set_margin_start(12)
        mode_box.set_margin_end(12)

        # O rótulo do CAMPO desceu do frame para cá, e isso não é cosmética: a
        # frase "O que o controle faz agora" é o nome do seletor em três páginas
        # da documentação (`docs/usage/modos.md`, `interface.md`, `quickstart.md`)
        # e no texto do diálogo de relançamento (`relancar.frase_da_mudanca`).
        # Perdê-la deixaria as quatro órfãs; aqui ela continua nomeando
        # exatamente o que sempre nomeou — o seletor logo abaixo.
        modo_label = Gtk.Label(label="O que o controle faz agora:")
        modo_label.set_xalign(0.0)
        mode_box.pack_start(modo_label, False, False, 0)

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

        # MODO-QUE-NAO-CONTROLA-01 (09/08/2026): logo ABAIXO da descrição do
        # modo, porque é a continuação dela — a descrição promete "o controle
        # vira mouse/teclado do computador" e esta linha diz quando essa
        # promessa não está de pé. Mesmo desenho dos banners de vpad/wrapper
        # (label inline, `no_show_all` para o `show_all()` do build não desfazer
        # o que o `_render_home` mandou), e a mesma classe de aviso da linha do
        # pendente: é ressalva, não erro — o modo entrou.
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

        # AGORA-E-DEPOIS-01: a linha do que ela escolheu e ainda não aplicou.
        # Fica FORA do `opts` de propósito: uma pendência de modo ("Controlar o
        # PC") existe quando a caixa da máscara está escondida, e dentro do
        # `opts` ela sumiria junto — a pessoa clicaria e não veria prova nenhuma
        # de que o clique registrou, que é o defeito que esta linha existe para
        # não criar. Texto pela função pura `relancar.texto_do_pendente`.
        pendente = Gtk.Label(label="")
        pendente.set_xalign(0.0)
        pendente.set_line_wrap(True)
        # Mesmo desenho dos banners de vpad/wrapper: `no_show_all` para o
        # `show_all()` do build não desfazer o que o `_render_home` mandou.
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

        # ONDA-U (U2/U10) + COOP-SEM-INTERRUPTOR-01 (06/08): "Reconciliar
        # jogadores" — reconcilia o co-op (`coop.sync`, ciclo cheio) e depois
        # compacta a numeração de exibição (DualSense + externos,
        # `identity.renumber`) para 1..N preservando a ordem relativa. Fica
        # junto dos cards: é aqui que jogador e numeração aparecem ("sony 1 /
        # sony 4" com só 2 controles, ou o P2 que sumiu no meio da partida).
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
            # O-DESLIGADO-DE-ONTEM-01: o opt-out sai do disco AQUI, no tique, e
            # não no `_render_home` — uma leitura por ciclo, e só com a aba à
            # vista. `suppress` porque um flag ilegível não pode derrubar a aba:
            # sem leitura, não há aviso, que é o mesmo silêncio de antes e nunca
            # pior que ele.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import (
                    load_gamepad_preference,
                )

                preferencia, _flavor = load_gamepad_preference()
                self._home_opt_out_cache = preferencia is False
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
                # AGORA-E-DEPOIS-01: sem daemon não há como aplicar, então a
                # linha do pendente sai da tela — mas a ESCOLHA fica guardada
                # em `_escolha_pendente`: o daemon volta e ela reaparece
                # inteira. Apagar a escolha aqui perderia, num engasgo de IPC,
                # o que a pessoa acabou de decidir.
                render_pendente(self, visivel=False)
                # UX-03: offline não é degradação do vpad — o banner some junto.
                self._home_vpad_banner.set_visible(False)
                # GUI-05: idem para o aviso "jogo sem wrapper".
                self._home_wrapper_banner.set_visible(False)
                # MODO-QUE-NAO-CONTROLA-01: sem daemon não há modo nem emulação
                # a julgar — "não sei" não pode virar "o mouse está desligado".
                _desktop_aviso = getattr(self, "_home_desktop_aviso", None)
                if _desktop_aviso is not None:
                    _desktop_aviso.set_visible(False)
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
                # ONDA-U (U2/U10): sem daemon, "Reconciliar jogadores" não tem
                # quem atenda o IPC.
                self._home_reconciliar_btn.set_sensitive(False)
                self._home_reconciliar_hint.set_text("")
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
            # COOP-SEM-INTERRUPTOR-01 (06/08): com daemon vivo o botão fica
            # SEMPRE de pé — jogo aberto só ganha a frase que diz o que não vai
            # acontecer (a numeração). Ver `RECONCILIAR_JOGO_ABERTO_TEXT`: o
            # gesto de trazer o jogador de volta é justamente o de partida
            # aberta, e desabilitá-lo ali o esconderia na hora exata do defeito.
            aviso_reconciliar = _reconciliar_gate_text(state)
            self._home_reconciliar_btn.set_sensitive(True)
            self._home_reconciliar_hint.set_text(aviso_reconciliar or "")

            gamepad = state.get("gamepad_emulation") or {}
            # HARM-01: a leitura do modo também tem um dono só — a Emulação
            # deriva do MESMO payload pela MESMA regra, então as duas abas não
            # podem mais discordar sobre em que modo o sistema está.
            mode = mode_of_state(state) or "desktop"
            # AGORA-E-DEPOIS-01: os dois vigentes do daemon são gravados AQUI,
            # antes de qualquer coisa que os leia. A máscara vem do mesmo
            # payload, umas linhas abaixo — subi-la para cá é o que permite
            # reconciliar a pendência no MESMO tique em que o daemon mudou, em
            # vez de um tique depois (2 s de tela mostrando escolha vencida).
            flavor = gamepad.get("flavor")
            if isinstance(flavor, str) and flavor:
                self._mascara_vigente_do_daemon = flavor
            # MODO-QUE-NAO-CONTROLA-01: o modo do tique ANTERIOR, lido antes de
            # ser sobrescrito na linha seguinte. É com ele que o aviso do
            # desktop calado sabe que a transição acabou de acontecer e que o
            # `mouse.emulation.restore` — o ÚLTIMO dos três IPCs do plano —
            # ainda pode estar em voo. Ver `texto_do_desktop_sem_emulacao`.
            modo_anterior = getattr(self, "_modo_vigente_do_daemon", None)
            self._modo_vigente_do_daemon = mode
            # A guarda do valor. Enquanto não há pendência os seletores
            # espelham o daemon, como sempre; com pendência eles mostram a
            # ESCOLHA DELA, e este tique não a sobrescreve. Sem isto o desenho
            # inteiro cai: `_render_home` roda a cada 2 s, e a escolha dela
            # voltaria sozinha antes de ela alcançar o botão "Aplicar".
            pendente = reconciliar_pendente(self)
            modo_exibido = pendente.get("modo") or mode
            selector.set_active_id(modo_exibido)
            self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(modo_exibido, ""))
            # MODO-QUE-NAO-CONTROLA-01: e, logo abaixo da descrição, a ressalva
            # — "Controlar o PC" de pé com o mouse (ou o teclado) emulado
            # desligado. Quem decide é a função pura; a aba só escreve.
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
            # E a VISIBILIDADE junto. AGORA-E-DEPOIS-01 §9, decisão 2 —
            # REVISTA por ela em 08/08 à noite, VENDO a tela:
            #
            #   *"a máscara volta ao que era. Não temos que burocratizar aí.
            #    Clico hefesto, a máscara aparece, clico em jogar xbox ou
            #    dualsense e ao clicar em aplicar lá embaixo o efeito aplica de
            #    fato. só isso"*
            #
            # A primeira versão fazia esta linha ler `mode` (o do daemon), e o
            # efeito na tela dela foi o pior possível: clicou em "Jogar pelo
            # Hefesto", o botão acendeu e a caixa da máscara **sumiu** — porque
            # o daemon ainda estava em desktop. Ler "a máscara ainda não cabe
            # aqui" exige saber que o modo é pendente; o que se lê é "a máscara
            # sumiu", que é outra coisa.
            #
            # Agora a caixa segue a ESCOLHA: um "Aplicar" só, com modo e máscara
            # decididos juntos — que é como ela usa a janela.
            self._home_gamepad_opts.set_visible(modo_exibido == "gamepad")
            self._home_gamepad_opts.set_no_show_all(modo_exibido != "gamepad")

            # AUTO-01.3: o dono da máscara é o DAEMON — a GUI só ECOA o que ele
            # reporta (`gamepad_emulation.flavor`, presente sempre que o daemon
            # está vivo). O `or "xbox"` que estava aqui era um segundo dono do
            # valor: com o campo ausente a aba mostrava Xbox e, no clique
            # seguinte, MANDAVA Xbox — trocando a máscara do daemon por causa de
            # um payload incompleto. Sem valor conhecido, o seletor fica como
            # está e o plano de transição sai sem o campo (ver
            # `plan_mode_transition`), preservando a máscara vigente.
            # (o `flavor` foi lido acima, junto do modo — AGORA-E-DEPOIS-01.)
            # A mesma guarda do modo, para o mesmo defeito: sem ela a máscara
            # escolhida voltaria à do daemon no tique seguinte.
            mascara_exibida = pendente.get("mascara") or (
                flavor if isinstance(flavor, str) and flavor else None
            )
            if mascara_exibida:
                self._home_flavor_selector.set_active_id(mascara_exibida)
            # MASCARA-CUSTO-01: o preço da máscara, embaixo do seletor — e é o
            # preço do que a caixa MOSTRA. Com uma máscara pendente, mostrar o
            # custo da vigente responderia a pergunta errada: ela está decidindo
            # sobre a nova, e é o preço DELA que precisa estar na mesa.
            custo = getattr(self, "_home_flavor_custo", None)
            if custo is not None:
                texto = texto_do_custo_da_mascara(mascara_exibida)
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

            # O-DESLIGADO-DE-ONTEM-01: a leitura do flag é I/O, e por isso vem
            # do cache do tique lento (`_home_opt_out_cache`), nunca a cada
            # repintura — o `_render_home` roda junto do estado e não pode virar
            # um `stat()` por quadro.
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
            # `getattr` e não acesso direto: os dublês de teste desta aba montam
            # só os widgets que o caso deles precisa, e um atributo novo aqui
            # derrubou 51 testes de cinco arquivos na primeira versão desta cura.
            # É a lição já escrita para `registrar_modo_no_rascunho` — código de
            # aba tem de sobreviver a dublê parcial, senão cada widget novo cobra
            # um pedágio em arquivos que não têm nada a ver com ele.
            banner_opt_out = getattr(self, "_home_opt_out_banner", None)
            if banner_opt_out is not None:
                if aviso_opt_out:
                    banner_opt_out.set_text(aviso_opt_out)
                banner_opt_out.set_visible(bool(aviso_opt_out))

            origin_bits: list[str] = []
            if state.get("native_mode") and state.get("native_mode_origin") == "profile":
                origin_bits.append("Nativo ligado pelo perfil ativo")
            if state.get("mode_from_profile") == "gamepad":
                origin_bits.append("Gamepad ligado pelo perfil ativo")
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
            # COOP-SEM-INTERRUPTOR-01 (06/08): esta frase é o que ficou no
            # lugar do botão "Preparar co-op" — e a contagem sai dos MESMOS
            # controles conectados que os cards mostram (`state_full`), uma
            # fonte só, nunca o cache assíncrono de outra aba.
            self._home_players_hint.set_text(_format_players_hint(connected))
            # QUEM-DÁ-O-JOGADOR-2-01 (08/08/2026): a caixinha do Steam Input, na
            # aba Perfis, precisa saber quantos controles há para avisar que a
            # marca troca o dono do jogador 2 — e o toast dela é SÍNCRONO, sem
            # tempo de perguntar ao daemon. Guardar aqui é de graça: esta função
            # já recebe o estado, já filtrou os conectados, e roda a cada tique.
            # Uma contagem só, num lugar só, para as duas abas não divergirem.
            self._controles_conectados = len(connected)
            # RELANCAR-01 (08/08/2026): a aba Perfis precisa saber se há jogo
            # aberto para decidir se pergunta antes de mudar a entrada — e o
            # toast dela é SÍNCRONO. Guardar aqui usa o MESMO critério que
            # `reconciliar_aviso` já usa (`game_signal.authority == "game"`),
            # em vez de sondar processo com dois `pgrep` de 5 s que
            # congelariam a janela. Uma fonte da verdade, não duas.
            sinal = state.get("game_signal") if isinstance(state, dict) else None
            # RELANCAR-NO-BOTAO-01: o modo vigente, para o "Salvar este
            # perfil" saber se o perfil salvo MUDA o que o jogo vê. Mesma
            # fonte da aba Início — nunca uma segunda verdade.
            # AGORA-E-DEPOIS-01: reusa o `mode` já derivado acima em vez de
            # derivá-lo de novo. Duas chamadas de `mode_of_state` no mesmo tique
            # não podem discordar hoje, mas são duas leituras onde cabe uma — e
            # a pendência agora depende deste valor para saber se a escolha dela
            # ainda diverge do que está valendo.
            self._modo_vigente_do_daemon = mode
            self._jogo_aberto = (
                isinstance(sinal, dict) and sinal.get("authority") == "game"
            )
            self._render_home_controllers(
                connected,
                grab_state=state.get("primary_grab_state"),
                gamepad_on=bool(gamepad.get("enabled")),
            )
            # AGORA-E-DEPOIS-01: a linha do pendente é reescrita a cada tique,
            # como todo o resto desta aba. Isso não é desperdício — é o que faz
            # a pendência SUMIR sozinha quando o daemon alcança a escolha dela
            # por outro caminho (a CLI, o applet, a troca de perfil).
            render_pendente(self)
            # Gtk referenciado para manter o import local óbvio (sem uso direto
            # neste ramo; os cards usam via _render_home_controllers).
            _ = Gtk
        finally:
            self._home_guard = False

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
                warn = Gtk.Label(label="Grab falhou — input pode dobrar no jogo")
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
        # A descrição acompanha o botão que ela acabou de clicar — ela descreve
        # o que ESTÁ ESCOLHIDO, não o que está valendo, e é o único retorno
        # imediato junto da linha do pendente.
        self._home_mode_desc.set_text(_MODE_DESCRIPTIONS.get(mode_id, ""))
        # AGORA-E-DEPOIS-01 (08/08/2026): aqui saíam `apply_mode(...)` e o
        # registro no rascunho. Os dois foram para o "Aplicar" do rodapé — o
        # botão verde, que é o gesto que ela usa para fechar a edição:
        #
        #   *"talvez fosse interessante isso aparecer somente quando clicarmos
        #    no botão final em aplicar, o botão verde — dessa forma eu posso
        #    passar em todas as abas e isso entra na alteração do perfil ativo"*
        #
        # O clique só MARCA. É o que desfaz o defeito 2 da OITO-DEFEITOS-01 (a
        # máscara perguntando a cada clique): sem aplicação não há o que
        # perguntar, e a pergunta passa a existir uma vez só, onde a mudança
        # sai. E é o que desfaz o 8: a caixa deixa de misturar o que É com o que
        # VAI SER.
        #
        # O `_home_guard` continua indispensável e não foi substituído por isto:
        # ele impede que o `set_active_id` do próprio `_render_home` entre aqui
        # como se fosse clique dela — o que gravaria uma "pendência" igual ao
        # vigente a cada 2 segundos.
        marcar_escolha(self, "modo", mode_id)

    def _on_home_flavor_changed(self, selector: Any) -> None:
        flavor_id = selector.get_active_id()
        if getattr(self, "_home_guard", False) or not flavor_id:
            return
        # O gate lê o seletor de MODO, que com pendência mostra a escolha dela:
        # quem marcou "Controlar o PC" e ainda não aplicou não está escolhendo
        # máscara nenhuma — a máscara só existe dentro de "Jogar pelo Hefesto".
        mode = self._home_mode_selector.get_active_id()
        if mode != "gamepad":
            return
        # AGORA-E-DEPOIS-01: idem ao modo — aqui saíam o `gamepad.emulation.set`
        # e o `_perguntar_antes_de_relancar`. A pergunta não sumiu: ela migrou
        # para o "Aplicar" (`footer_actions._aplicar_escolha_pendente`), onde a
        # decisão dela está COMPLETA — modo e máscara escolhidos — em vez de
        # interromper no meio da escolha.
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

    def _on_home_reconciliar_clicked(self, _button: object) -> None:
        """"Reconciliar jogadores": ``coop.sync`` e, em seguida, ``identity.renumber``.

        COOP-SEM-INTERRUPTOR-01, entrega 5 (06/08/2026). NOTA DATADA: até aqui
        este botão se chamava "Renumerar agora" e disparava um método só. Ele
        herdou o gesto de recuperação que morreu com o botão "Preparar co-op" —
        o ciclo FORÇADO do co-op, que é o único capaz de trazer de volta o
        jogador cujo grab foi recusado ou cujo vpad morreu sem que /dev/input
        mudasse (COOP-QUE-NÃO-DESMONTA-01).

        Os dois passos são ENCADEADOS, não paralelos, e a ordem é a entrega:
        renumerar antes de reconciliar compactaria uma mesa que ainda não está
        completa. O `coop.sync` é quem reporta a falha de IPC (é o passo que
        responde "meus jogadores voltaram?"); a recusa do `identity.renumber`
        com jogo aberto NÃO vira erro — com os jogadores já de pé seria a
        interface mentindo, a mesma regra do ``reported_step_index``.

        Contrato fixado com o daemon: ``coop.sync {}`` ->
        ``{status, players, active}``; ``identity.renumber {}`` ->
        ``{ok: true, renumbered: {uniq: slot}}`` | ``{ok: false, reason}``.
        """

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
                # O acabamento falhou, a reconciliação não: o toast diz os dois.
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
        # DIALOGO-QUE-MATA-A-JANELA-01, segunda metade (06/08/2026): um
        # `dialog.show()` cru num diálogo `modal=True` instala o grab do GTK e,
        # se a janela não chegar ao servidor, prende a janela dela inteira —
        # clique, tecla e o "X" do gerenciador, os três. MEDIDO por verificação
        # adversarial (0/0/0 contra 2/1/1 no controle). Não bloquear NÃO salva:
        # quem prende é a modalidade, não o laço.
        from hefesto_dualsense4unix.app import gui_dialogs as _gd

        _gd.mostrar_dialogo_assincrono(dialog, nome="home_desligar_hefesto")


__all__ = [
    "ABA_INICIO",
    "HOME_POLL_INTERVAL_MS",
    "RECONCILIAR_JOGO_ABERTO_TEXT",
    "RECONCILIAR_LABEL",
    "TEXTO_DESKTOP_SEM_MOUSE",
    "TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO",
    "TEXTO_DESKTOP_SEM_TECLADO",
    "VPAD_DEGRADED_TEXT",
    "WRAPPER_MISSING_TEXT",
    "HomeActionsMixin",
    "id_da_pagina",
    "id_da_pagina_corrente",
    "reconciliar_toast",
    "texto_do_desktop_sem_emulacao",
    "vpad_degradation_text",
    "wrapper_banner_text",
]


def aviso_de_opt_out_antigo(
    state: dict[str, Any] | None, *, opt_out: bool, conectados: int
) -> str | None:
    """O produto está inerte por uma escolha ANTIGA dela. ``None`` = nada a dizer.

    O-DESLIGADO-DE-ONTEM-01 (10/08/2026). Ela: *"o touchpad não tá funcionando e
    o giroscópio não funciona também e se tão no modo nativo ou hefesto dualsense,
    deveriam funcionar por default"*.

    O QUE FOI MEDIDO na máquina dela, com o controle no cabo e 85 % de bateria:

        native_mode: False | emulacao: False | vpads vivos: 0 | perfil: nenhum
        ~/.config/hefesto-dualsense4unix/gamepad_disabled.flag  ->  09/08 23:50

    O flag é opt-out **explícito e permanente** — o daemon o respeita a cada
    boot e diz por quê a cada dois segundos no journal
    (``motivo=desligada_de_proposito``). É a regra R-07, e ela está certa: só o
    gesto manual escreve preferência em disco, e uma automação não pode desfazer
    o que a dona mandou.

    O QUE ESTAVA ERRADO era o silêncio, e o preço dele foi grande: sem gamepad
    virtual não há por onde o giroscópio chegar ao jogo, e ela passou a noite
    concluindo que o **produto** estava quebrado. O que a tela mostrava —
    "Controlar o PC" — é a verdade, e é insuficiente: diz o QUE está valendo e
    não que isso veio de uma decisão de ontem que continua valendo hoje.

    Some no instante em que ela troca de modo, e não reaparece enquanto o gesto
    novo estiver de pé: é aviso de estado, nunca um pedido repetido.

    Sem controle na mesa devolve ``None``: aí não há nada para atravessar, e o
    aviso seria ruído sobre um problema que não existe agora.
    """
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
