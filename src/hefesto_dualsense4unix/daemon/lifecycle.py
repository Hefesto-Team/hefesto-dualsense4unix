"""Ciclo de vida do daemon: orquestrador slim (ADR-015).

O daemon é composto por:
  - 1 IController (real ou fake) conectado ao dispositivo.
  - 1 EventBus global.
  - 1 StateStore global.
  - Tasks async: poll_loop e subsystems opcionais.

Daemon.run() orquestra connect → subsystems → run_until_stopped → shutdown.
Toda lógica interna foi extraída para src/hefesto_dualsense4unix/daemon/subsystems/.

Backcompat (REFACTOR-LIFECYCLE-01): todos os nomes públicos que existiam antes
do refactor são reexportados aqui para que imports externos continuem funcionando
sem alteração.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import signal
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal, cast, get_args

from hefesto_dualsense4unix.core.controller import ControllerState, IController
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.battery_journal import (
    INTERVALO_SONDA_S,
    diario_da_bateria,
    registrar_queda_da_bateria,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore

# ---------------------------------------------------------------------------
# Reexportações de backcompat — NÃO remover (testes importam diretamente).
# ---------------------------------------------------------------------------
from hefesto_dualsense4unix.daemon.subsystems.poll import (
    BATTERY_DEBOUNCE_SEC,
    BATTERY_DELTA_THRESHOLD_PCT,
    BATTERY_MIN_INTERVAL_SEC,
    BatteryDebouncer,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    AUTO_DEBOUNCE_SEC,
    RUMBLE_POLICY_MULT,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_HZ = 60

#: Período de assentamento (settling/grace) pós-conexão em segundos
#: (BUG-DAEMON-CONNECT-GHOST-INPUT-01). Enquanto ativo, o poll loop continua
#: lendo estado/bateria e publicando STATE_UPDATE, mas NÃO despacha
#: teclado/mouse/hotkey nem publica BUTTON_DOWN/UP. Cobre a janela em que o
#: HID-raw ainda está cru (ex.: micBtn fantasma) e o snapshot evdev ainda
#: popula após o plug — barrando o mute fantasma e os "comandos aleatórios"
#: na origem. ~0.3s é compromisso entre cobrir o settling do firmware e a
#: latência percebida até o input ficar responsivo.
INPUT_GRACE_SEC: float = 0.3

#: FEAT-DSX-EVDEV-WATCHDOG-01: intervalo entre checagens de "node de evdev
#: obsoleto" no poll loop. Cada checagem escaneia /dev/input, então não roda
#: todo tick; 2s é folgado o bastante para não pesar e rápido para recuperar o
#: controle logo após uma re-enumeração (storm -71 / replug).
EVDEV_WATCHDOG_SEC: float = 2.0

#: HANG-01 (Sprint 2026-07-19): teto de espera do tick de LED dos externos
#: (`ExternalLedSync.tick`, executado no pool DEDICADO `hefesto-ext`, ver
#: `_external_executor`). Medido ao vivo (16:08:56, PID 2835): uma
#: "debandada" (mass-unplug) faz `discover_external_gamepads` abrir/fechar
#: TODOS os nodes de /dev/input em rajada, e um wedge de GIL do CPython sob
#: esse churn de threads pode nunca devolver o controle a Python — sem
#: timeout, o poll loop ficava suspenso PARA SEMPRE em
#: `await self._run_blocking(sync.tick)` (zero read_state, zero logs, zero
#: watchdog). A THREAD presa NÃO é recuperável (é um wedge de baixo nível, não
#: uma trava lógica nossa) — o trade-off aceito é vazar o(s) worker(s) do
#: pool `hefesto-ext`.
#: CORREÇÃO PÓS-AUDITORIA (20/07): a 1ª versão deste fix rodava `sync.tick`
#: no MESMO `self._executor` ("hefesto-hid", 2 workers) do qual `read_state`
#: (SEM wait_for), `_gather_game_signal_inputs` e o watchdog evdev também
#: dependem — 2 timeouts consecutivos (o guard de reentrância permite um 2º
#: agendamento porque a task asyncio já retorna "done" ao capturar o
#: TimeoutError, mesmo com a thread ainda presa) vazavam os 2 workers do
#: MESMO pool que o poll loop usa pra ler o controle — reproduzindo o hang
#: original, só que adiado por ~2x este timeout em vez de instantâneo. Agora
#: `sync.tick` roda em `self._external_executor`, um pool PRÓPRIO e ISOLADO —
#: o pior caso vaza só ali, nunca no pool de que `read_state` depende. 10s é
#: folgado para uma enumeração normal (10-40ms) e curto o bastante para o
#: daemon nunca parecer morto por mais que isso.
EXTERNAL_TICK_TIMEOUT_SEC: float = 10.0

#: HANG-01: timeouts CONSECUTIVOS do tick de externos a partir dos quais o
#: daemon PARA de agendar `discover` (inventário congela; `external_led` para
#: de atualizar) até o próximo `input_dir_change` do `InputDirWatch` — evita
#: empilhar uma task nova a cada ~2s em cima de um pool cujo(s) worker(s) já
#: podem estar presos (dobrar/triplicar o vazamento em vez de conter em 1).
EXTERNAL_TICK_MAX_TIMEOUTS: int = 2


# ---------------------------------------------------------------------------
# DaemonConfig
# ---------------------------------------------------------------------------

#: FEAT-RUMBLE-POLICY-PROFILE-01: políticas válidas de intensidade de rumble.
#: Fonte única para `DaemonConfig.rumble_policy` e para a validação defensiva
#: em `Daemon.apply_profile_rumble_policy` (o schema de perfil replica o
#: Literal para não importar o daemon — sem ciclo de import).
RumblePolicy = Literal["economia", "balanceado", "max", "auto", "custom"]
RUMBLE_POLICIES: tuple[str, ...] = get_args(RumblePolicy)


@dataclass
class DaemonConfig:
    poll_hz: int = DEFAULT_POLL_HZ
    auto_reconnect: bool = True
    reconnect_backoff_sec: float = 2.0
    ipc_enabled: bool = True
    udp_enabled: bool = True
    udp_host: str = "127.0.0.1"
    udp_port: int = 6969
    autoswitch_enabled: bool = True
    # FEAT-MOUSE-01
    mouse_emulation_enabled: bool = False
    mouse_speed: int = 6
    mouse_scroll_speed: int = 1
    # FEAT-DSX-GAMEPAD-FLAVOR-01 — gamepad virtual integrado ao daemon (1 leitor
    # → fan-out, sem o conflito de 2 leitores do `emulate xbox360` avulso).
    # Mutuamente exclusivo com mouse_emulation: ligar o gamepad desliga o mouse
    # (jogar = controle vai pro jogo, não pro cursor). flavor: dualsense|xbox.
    gamepad_emulation_enabled: bool = False
    # HARMONIA-MASK-01 (22/07, decisão da mantenedora): default dualsense — o
    # vpad é DualSense Edge por arquitetura (UHID-04) e a máscara dualsense
    # foi validada em jogo real (Sackboy/Mad King/Pragmata). Este default só
    # governa instalação nova/flag ausente: `gamepad_emulation.flag` persiste
    # a escolha da usuária e vence sempre (load_gamepad_emulation, abaixo).
    # (Histórico: era "xbox" desde SPRINT-GAME-RUMBLE-01, de antes da máscara
    # dualsense vibrar — superado pela validação da Onda Harmonia.)
    gamepad_flavor: str = "dualsense"
    # FEAT-DSX-COOP-LOCAL-01 — co-op local: cada controle físico vira um jogador
    # (P1, P2, …) com seu próprio gamepad virtual, em vez do modo "N controles, 1
    # player" (broadcast). Só tem efeito com a emulação de gamepad ligada + 2+
    # controles.
    #
    # COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA. O default era `False`,
    # e o motivo escrito aqui era *"preserva o uso de reserva/troca de
    # controle"*. Esse motivo CADUCOU POR DECISÃO DELA, tomada mais de uma vez:
    # *"todos e tudo no Hefesto tem que tá com o permitir co-op ligado (…) se eu
    # conecto 4 controles no PC eu espero, com 4 pessoas jogando, que cada um
    # controle o próprio personagem. Ninguém esperaria controlar o mesmo
    # personagem com cada controle."* Quem quer um controle de reserva o deixa
    # DESCONECTADO — não precisa de flag para isso, e a flag custava um co-op
    # que não subia sozinho na máquina de quem nunca ouviu falar dela.
    #
    # Este dataclass é o ÚNICO piso desde 06/08: o boot deixou de reler o
    # opt-out (`utils/session.load_coop_enabled` virou lápide) justamente para
    # que arrancar este `True` REPROVE — antes, `run()` forçava `True` logo
    # adiante e um teste de boot passava com a cura arrancada.
    coop_enabled: bool = True
    # FEAT-KEYBOARD-EMULATOR-01 — emula teclado virtual a partir de botões
    # do DualSense.
    #
    # EMULACAO-NO-JOGO-01 (29/07): o campo deixou de ser config MORTA. Até aqui
    # nada o desligava — sem gate de criação no subsystem, sem flag em disco,
    # sem IPC — e o R1 (Alt+Tab no mapa default) trocava de aplicativo dentro da
    # partida dela; 9 de 9 pressionamentos medidos no journal caíram dentro de
    # `steam_input_vpad_suspenso`. Agora: `subsystems/keyboard.py` recusa criar o
    # device com o campo False (molde de `subsystems/mouse.py`),
    # `keyboard_emulation.flag` persiste a escolha dela (lida no boot, abaixo em
    # `run`) e `keyboard.emulation.set` alterna em runtime.
    #
    # O default fica True DE PROPÓSITO (decisão registrada na sprint): desligar o
    # teclado desliga também o teclado virtual do sistema em L3/R3 e as três
    # regiões do touchpad (`core/keyboard_mappings.py`) — quem usa o controle
    # como teclado de acessibilidade perderia tudo isso num upgrade silencioso.
    # A cura do sintoma dela não depende deste default: ela vem do gate de
    # despacho por "jogo com autoridade" (ver `_jogo_no_controle_do_desktop`).
    keyboard_emulation_enabled: bool = True
    # FEAT-HOTKEY-STEAM-01
    ps_button_action: Literal["steam", "none", "custom"] = "steam"
    ps_button_command: list[str] = field(default_factory=list)
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01 — ms de hold do PS para alternar o
    # modo-jogo (supressão da emulação mouse/teclado). 0 = desliga o gesto (PS
    # então só faz a ação solo, ex. abrir Steam). Default 0: o modo jogo é só
    # pelo combo PS+Options; o long-press de 1000ms causava toggle ACIDENTAL
    # quando o toque de "abrir Steam" passava de ~1s.
    ps_long_press_ms: int = 0
    # BUG-RUMBLE-APPLY-IGNORED-01
    rumble_active: tuple[int, int] | None = None
    # FEAT-RUMBLE-POLICY-01
    rumble_policy: RumblePolicy = "balanceado"
    rumble_policy_custom_mult: float = 0.7
    # FEAT-HOTKEY-MIC-01 — o botão de mic do controle alterna o mute do
    # microfone PADRÃO DO SISTEMA (wpctl/pactl) e acompanha o LED do mic.
    # Desligado, o botão vira só um botão (o kernel segue mudando o mic do
    # próprio controle — isso é dele, não nosso).
    mic_button_toggles_system: bool = True
    # BT-MIC-REGISTRY-01 — ponte de microfone por Bluetooth (Opus tunelado em
    # HID). OPT-IN por privacidade e por banda de rádio: ver o cabeçalho de
    # `daemon/subsystems/bt_mic.py`. Também aceita
    # `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` (o subsystem consulta os dois).
    bt_mic_enabled: bool = False
    # FEAT-METRICS-01
    metrics_enabled: bool = False
    metrics_port: int = 9090
    # FEAT-PLUGIN-01 — opt-in: código de usuário arbitrario, desativado por padrao.
    plugins_enabled: bool = False


# ---------------------------------------------------------------------------
# R-03 — resultado de cada seção de perfil e pendência de modo
# ---------------------------------------------------------------------------

#: R-03 (auditoria 23/07): vocabulário ÚNICO devolvido pelos appliers de perfil
#: (`apply_profile_mouse`, `apply_profile_suppression`, `apply_profile_mode`,
#: `apply_profile_rumble_policy`). Até aqui todos devolviam `None` e engoliam a
#: seção em silêncio quando o lock de gesto manual estava ativo — a ativação era
#: commitada, o IPC respondia sucesso e NADA reaplicava depois. O retorno é o
#: canal por onde `ProfileManager.activate` monta o relatório e o
#: `profile.switch` conta a verdade para a GUI.
#:
#:   - ``"aplicado"``            — a seção foi honrada (inclusive o no-op
#:                                 idempotente: o estado pedido já valia);
#:   - ``"adiado_lock_manual"``  — o lock de gesto manual (30 s) barrou AGORA;
#:                                 só a seção `mode` agenda pendência de retry;
#:   - ``"ignorado_catch_all"``  — R-02: catch-all não tem autoridade para
#:                                 reverter (ausência de regra ≠ ordem);
#:   - ``"ignorado_janela_de_jogo"`` — R-02: reverter modo/supressão com jogo em
#:                                 foco é absurdo, seja qual for o perfil;
#:   - ``"falhou"``              — o applier levantou (o manager carimba).
APLICADO = "aplicado"
ADIADO_LOCK_MANUAL = "adiado_lock_manual"
IGNORADO_CATCH_ALL = "ignorado_catch_all"
IGNORADO_JANELA_DE_JOGO = "ignorado_janela_de_jogo"
FALHOU = "falhou"

#: SOM-02/E4: a seção não foi escrita porque NÃO HÁ controle para escrever
#: (nenhum handle para o `uniq` pedido, ou nada conectado). Estado próprio, e
#: não `FALHOU`, porque nada quebrou: o controle está fora da mesa. Distinguir
#: importa no relatório que a GUI mostra — "falhou" mandaria procurar defeito
#: onde só falta o cabo.
IGNORADO_SEM_CONTROLE = "ignorado_sem_controle"


@dataclass
class ModoAdiado:
    """Pendência ÚNICA da seção `mode` adiada pelo lock de gesto manual (R-03).

    Sempre SOBRESCRITA, nunca enfileirada: se dois perfis forem ativados dentro
    da mesma janela de lock, quem vale é o último — enfileirar aplicaria um modo
    que já não corresponde ao perfil ativo.

    A variante "não gravar `_current_profile` no autoswitch para ele tentar de
    novo" foi REJEITADA na consolidação da auditoria: com o poll de 2 Hz ela
    faria `_activate` rodar ~60x em 30 s, reescrevendo gatilhos/LEDs e
    `reset_output_overrides` a cada tick — exatamente o flap que o MISC-08
    removeu. Aqui a ativação é commitada normalmente e só o `mode` fica
    pendente, drenado UMA vez pelo `_poll_loop`.

    Por que SÓ o `mode` tem pendência (e mouse/supressão/política de rumble
    apenas REPORTAM o adiamento): `mode` é o eixo que a usuária sente — máscara
    do vpad e co-op, o que faz o jogo funcionar a 4 — e o único cuja perda dura
    a sessão inteira. Um retry por eixo multiplicaria os caminhos assíncronos
    capazes de mexer no estado do controle sem gesto dela; os outros três voltam
    a ser avaliados na próxima ativação de perfil, que é barata e frequente.

    Campos:
      - `carimbo_manual` — valor de `_emu_manual_ts` na criação. Se o carimbo
        MUDAR, houve gesto manual NOVO (mais recente que o perfil) e a pendência
        é descartada: a última palavra é dela, não do perfil de meia hora atrás.
      - `nao_antes_de` — `carimbo_manual + MANUAL_PROFILE_LOCK_SEC`; antes disso
        o lock ainda protege o gesto dela.
      - `esperando_jogo` — dedupe do log de espera (o dreno roda a ~1 Hz).
    """

    mode: Any
    profile: Any
    profile_name: str | None
    origin: str
    carimbo_manual: float
    nao_antes_de: float
    esperando_jogo: bool = False


#: MODO-01/B3: origem da ativação de modo que veio do SINAL DE JOGO — nenhum
#: perfil mandou, o daemon é que reconheceu o jogo. Vocabulário próprio (e não
#: "autoswitch") porque é isso que aparece no journal e é por ele que se
#: distingue, meses depois, "o perfil do jogo ligou o modo" de "ninguém tinha
#: perfil e o daemon ligou o modo padrão".
ORIGEM_GAME_SIGNAL = "game_signal"

#: MODO-01/B3: dois estados que só o modo jogo PADRÃO produz, no dialeto
#: `IGNORADO_*` do vocabulário acima. Não entram naquele conjunto porque nunca
#: aparecem no relatório de ativação de um perfil — este eixo não tem perfil.
#:
#:   - ``IGNORADO_SEM_JOGO`` — a autoridade de exibição não é `game`. Não é
#:     recusa: é "ainda não" (o sinal leva até ~2 s para virar) ou "não é jogo".
#:   - ``IGNORADO_GESTO_DELA`` — a decisão já é dela e é mais específica que um
#:     default (Modo Nativo manual).
IGNORADO_SEM_JOGO = "ignorado_sem_jogo"
IGNORADO_GESTO_DELA = "ignorado_gesto_dela"

#: AUTO-01.1: o auto-ligar da emulação não agiu porque não há segundo controle
#: na mesa. Estado próprio (e não `IGNORADO_SEM_JOGO`) porque é o caso NORMAL de
#: quem joga sozinho — nada aconteceu de errado, simplesmente não há co-op a
#: preparar. Ver `Daemon.aplicar_gamepad_para_multiplos_controles`.
IGNORADO_UM_CONTROLE_SO = "ignorado_um_controle_so"

#: EMULACAO-NO-JOGO-01: por que a emulação de DESKTOP (mouse/teclado) está calada
#: mesmo sem o modo jogo ligado. Vocabulário PÚBLICO — sai no journal e no bloco
#: `keyboard_emulation.bloqueio` do `daemon.status`/`daemon.state_full`, e é por
#: ele que a aba Emulação explica à usuária o que está acontecendo.
#:
#:   - ``CALADA_VPAD_SUSPENSO`` — a exceção do Steam Input tirou o vpad de cena
#:     para este jogo (`subsystems/gamepad.steam_input_vpad_suspenso`). O jogo
#:     assumiu o controle: emitir Alt+Tab aqui é o defeito medido de 29/07.
CALADA_VPAD_SUSPENSO = "vpad_suspenso_pelo_steam_input"


@dataclass
class ModoJogoPadrao:
    """O modo jogo que o SINAL DE JOGO ligou, sem perfil nenhum (MODO-01/B3).

    Existe para que soltar o modo ao sair do jogo seja EXATO — desligar só o
    que este daemon ligou, e devolver o eixo de modo a quem era dono antes.
    Sem esta memória a cura viraria a próxima queixa: na máquina dela o gamepad
    virtual já vive LIGADO (flag em disco), e um "reverter" ingênuo o desligaria
    ao fechar o jogo, deixando-a sem controle nenhum no desktop.

    Campos:
      - `ligou_gamepad` — o vpad estava DESLIGADO e fomos nós que o ligamos. Só
        neste caso a saída do jogo o desliga de volta.
      - `dono_anterior` — valor de `_mode_from_profile` antes de nós. Aplicar o
        modo jogo padrão carimba `"gamepad"` nesse campo (é o mesmo applier de
        perfil), e deixá-lo carimbado depois daria a um perfil de desktop
        qualquer a autoridade de reverter um modo que nenhum perfil ligou.
      - `wm_class` — a janela que motivou o pedido; só para o journal.
    """

    ligou_gamepad: bool
    dono_anterior: str | None
    wm_class: str


# ---------------------------------------------------------------------------
# Daemon (orquestrador)
# ---------------------------------------------------------------------------


@dataclass
class Daemon:
    """Orquestrador do daemon. API pública preservada (REFACTOR-LIFECYCLE-01).

    Atributos públicos (mantidos para backcompat de testes):
      controller, bus, store, config, _hotkey_manager, _audio, _mouse_device,
      _ipc_server, _udp_server, _autoswitch, _last_auto_mult, _last_auto_change_at.
    """

    controller: IController
    bus: EventBus = field(default_factory=EventBus)
    store: StateStore = field(default_factory=StateStore)
    config: DaemonConfig = field(default_factory=DaemonConfig)

    _stop_event: asyncio.Event | None = None
    _executor: ThreadPoolExecutor | None = None
    # HANG-01 (correção pós-auditoria 20/07): pool DEDICADO e ISOLADO do tick
    # de LED dos externos (`ExternalLedSync.tick`, via `_sync_external_leds`)
    # — nunca compartilhado com `_executor`. Um wedge de GIL travando a única
    # thread deste pool não pode mais esgotar o pool de que `read_state`/
    # `_gather_game_signal_inputs`/o watchdog evdev dependem (ver comentário
    # de `EXTERNAL_TICK_TIMEOUT_SEC`).
    _external_executor: ThreadPoolExecutor | None = None
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _ipc_server: Any = None
    _udp_server: Any = None
    _autoswitch: Any = None
    _mouse_device: Any = None
    _keyboard_device: Any = None
    # FEAT-DSX-GAMEPAD-FLAVOR-01 — UinputGamepad criado em runtime por
    # start_gamepad_emulation; None quando o gamepad virtual está desligado.
    _gamepad_device: Any = None
    # GYRO-01 — PhysicalReportReader do vpad do P1 (espelho de motion: hidraw
    # do físico → forward_motion). Criado/parado por start/stop_motion_reader
    # junto do vpad uhid; None com a emulação desligada ou no fallback uinput.
    _motion_reader: Any = None
    # BROKER-01 — lease-cliente do broker root hide-hidraw
    # (`integrations.hidraw_broker_client.HidrawBrokerClient`). Criado sob
    # demanda por `broker_client_for` (lazy, lock de módulo); a conexão É a
    # lease (EOF restaura tudo). None até o 1º hide/open; o shutdown fecha e
    # zera explicitamente.
    _hidraw_broker_client: Any = None
    # Achados Onda S #5/#6/#10 — executor DEDICADO (1 worker, FIFO) das
    # operações hide/restore do broker (`broker_call_nonblocking`): I/O de
    # socket com timeout de 2 s jamais roda na thread do event loop. Lazy
    # (criado no 1º uso a partir do loop); o shutdown o desliga com
    # `cancel_futures=True` antes de fechar a lease.
    _hidraw_broker_executor: Any = None
    # FEAT-DSX-COOP-LOCAL-01 — CoopManager: jogadores secundários (P2+) do co-op
    # local. Criado sob demanda por `get_coop_manager`; None até o 1º uso.
    _coop_manager: Any = None
    _hotkey_manager: Any = None
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: quando True, o poll loop não despacha
    # mouse/teclado (devices ficam vivos; hotkeys seguem ativos). Alternado pelo
    # long-press do PS. Transitório — não persiste entre boots.
    _emulation_suppressed: bool = False
    # FEAT-POINT-AND-CLICK-01: instante (time.monotonic) do último toggle MANUAL
    # do modo-jogo (hotkey PS+Options, IPC `daemon.emulation.suppress`, GUI).
    # -inf = nunca houve toggle manual (boot). Consultado por
    # `apply_profile_suppression`: perfil não mexe na supressão dentro da
    # janela de MANUAL_PROFILE_LOCK_SEC após um gesto manual.
    _suppress_manual_ts: float = field(default=float("-inf"))
    # FEAT-POINT-AND-CLICK-01: True quando a supressão ATUAL foi ligada (ou
    # adotada) por um perfil com suppress_desktop_emulation=True. Perfis sem o
    # campo só LIBERAM a supressão quando este flag é True — toggle manual da
    # usuária nunca é revertido por autoswitch/troca de perfil.
    _suppress_from_profile: bool = False
    # EMULACAO-NO-JOGO-01: motivo pelo qual a emulação de DESKTOP está calada
    # porque o JOGO tem o controle ("" = não está calada por jogo). É o estado do
    # episódio: serve de dedup do log (o poll loop passa aqui a 60 Hz) e de borda
    # para o flush/prime dos devices virtuais. Ver
    # `_jogo_no_controle_do_desktop`.
    _emu_calada_motivo: str = ""
    # EMULACAO-NO-JOGO-01: já logamos, NESTE episódio, que havia botão
    # pressionado com o jogo no controle. Sem esta dedup a linha sairia a cada
    # tick enquanto ela segurasse R1 dentro da partida.
    _emu_calada_botoes_logados: bool = False
    # BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: instante (time.monotonic) do último
    # toggle MANUAL da EMULAÇÃO (mouse ou gamepad via IPC/GUI/CLI/hotkey). -inf =
    # nunca. Consultado por `apply_profile_mouse`: um perfil não liga/desliga a
    # emulação dentro de MANUAL_PROFILE_LOCK_SEC após um gesto manual — não
    # sequestra um gamepad virtual ligado na mão no meio do jogo.
    _emu_manual_ts: float = field(default=float("-inf"))
    # R-03 (auditoria 23/07): seção `mode` que o lock acima adiou, aguardando o
    # dreno do `_poll_loop` (`_drenar_modo_pendente`). UMA só, sempre
    # sobrescrita — ver `ModoAdiado`. None = nada pendente.
    _mode_pendente: ModoAdiado | None = None
    # MODO-01/B3: o modo jogo que o SINAL DE JOGO ligou, sem perfil nenhum.
    # None = não há modo jogo padrão de pé. Ver `ModoJogoPadrao`.
    _modo_jogo_padrao: ModoJogoPadrao | None = None
    # MODO-01/B3: último estado LOGADO de `aplicar_modo_jogo_padrao`. O
    # autoswitch pede a 2 Hz enquanto o jogo está em foco; sem esta chave, os
    # ~30 s de espera do lock de gesto manual virariam 60 linhas no journal.
    _modo_jogo_padrao_log: str = ""
    # AUTO-01.1: último estado LOGADO de
    # `aplicar_gamepad_para_multiplos_controles` (o tick lento pede a cada 2 s).
    # Mesma dedup, mesma razão do campo acima.
    _gamepad_multi_log: str = ""
    # MODO-01/B5: `ProfileManager` de LEITURA, cacheado. Ver
    # `_manager_de_selecao` — a instância nova a cada tique zerava a dedup do
    # veto R-21 e o journal levava 1 linha a cada 2 s.
    _profile_selector: Any = None
    # FEAT-NATIVE-MODE-01: Modo Nativo ativo ("release total" do controle). Não
    # persiste no dataclass — é restaurado do flag no boot. O poll loop gateia o
    # dispatch por este flag (independente de pause/resume).
    _native_mode: bool = False
    # Estado de emulação (mouse/gamepad) capturado ANTES do Modo Nativo, para
    # restaurar ao desligar (o release apaga os flags próprios).
    _native_emu_stash: dict[str, Any] = field(default_factory=dict)
    # FEAT-PROFILE-MODE-01: qual MODO o perfil ativo ligou ("native"|"gamepad"|
    # None). Perfis sem seção `mode` só revertem modo cuja origem foi PERFIL —
    # gesto manual da usuária nunca é derrubado por autoswitch (mesma semântica
    # do `_suppress_from_profile`).
    _mode_from_profile: str | None = None
    # FEAT-RUMBLE-POLICY-PROFILE-01: True quando a política de rumble VIGENTE
    # foi aplicada por um perfil (`apply_profile_rumble_policy`). Perfis sem
    # opinião (rumble.policy=None) só revertem política cuja origem foi
    # PERFIL — gesto manual da usuária (IPC rumble.policy_set/policy_custom)
    # nunca é derrubado por autoswitch (paridade com `_mode_from_profile`).
    _rumble_policy_from_profile: bool = False
    # Política global vigente ANTES de o 1º perfil-com-opinião mexer, como
    # par (policy, custom_mult) — é para ela que um perfil sem opinião
    # reverte. None = nenhum perfil mexeu na política.
    _rumble_policy_before_profile: tuple[RumblePolicy, float] | None = None
    # BUG-EMU-DEVICE-RACE-01: serializa as transições de device de emulação
    # (start/stop de mouse e gamepad virtuais). A wave passou a chamar
    # set_mouse_emulation também da thread do executor (hotkey de ciclo via
    # _run_blocking(activate)), concorrendo com a thread do event loop (IPC/
    # autoswitch); o check-then-act sem lock em start_mouse_emulation podia criar
    # 2 devices uinput e vazar 1. RLock (reentrante: set_mouse_emulation chama
    # _stop_gamepad_emulation na mesma thread).
    _emu_lock: Any = field(default_factory=threading.RLock)
    _audio: Any = None
    _plugins_subsystem: Any = None
    # FEAT-METRICS-01: MetricsSubsystem (servidor HTTP Prometheus) ou None.
    # Instanciado por `_start_metrics` quando metrics_enabled; None até o 1º uso.
    _metrics_subsystem: Any = None
    # BT-MIC-REGISTRY-01: BtMicSubsystem (ponte de microfone por Bluetooth) ou
    # None. OPT-IN — só é instanciado quando `bt_mic_enabled`/a env var estão
    # ligadas; um microfone que sobe sozinho com o daemon é inaceitável.
    _bt_mic_subsystem: Any = None
    # BUG-DAEMON-NO-DEVICE-FATAL-01 — task de probe de conexão em background
    # (substitui connect_with_retry bloqueante no boot). Cancelada em shutdown.
    _reconnect_task: asyncio.Task[Any] | None = None
    _last_auto_mult: float = field(default=0.7)
    _last_auto_change_at: float = field(default=0.0)
    # VPAD-01/VPAD-02: instante (time.monotonic) da última tentativa de trocar
    # o backend do vpad do P1 (uinput→uhid); -inf = nunca tentou. O cooldown
    # (`gamepad.REBACKEND_COOLDOWN_SEC`) é UM SÓ para a promoção do hotplug
    # (reconnect_loop) e a re-seleção pela GUI: o precheck `uhid_available()`
    # não pega o uhid que aceita o CREATE2 mas nunca faz bind (kernel sem
    # hid_playstation) — sem a trava, cada borda derrubaria e recriaria o vpad
    # uinput que funciona (input drop em loop no meio do jogo).
    _last_rebackend_ts: float = field(default=float("-inf"))
    # BUG-DAEMON-CONNECT-GHOST-INPUT-01 — instante (loop.time()) a partir do
    # qual o input emulado volta a ser despachado após uma (re)conexão. Setado
    # pelo poll loop na borda desconectado→conectado e rearmado em reconexão.
    # Enquanto loop.time() < _input_ready_at, BUTTON_DOWN/UP + dispatch de
    # teclado/mouse/hotkey ficam suprimidos (settling/grace). 0.0 = sem grace
    # pendente (estado inicial, antes da 1ª conexão; o poll loop só arma o
    # grace ao detectar a borda de conexão).
    _input_ready_at: float = field(default=0.0)
    # CLUSTER-IPC-STATE-PROFILE-01 (Bug A) — cache do último estado lido pelo
    # _poll_loop. Permite que `daemon.state_full` reflita o tick atual em vez
    # de só o snapshot do StateStore (que pode estar estagnado em fallback HID
    # se o evdev_reader não conectou). Atualizado 1x por tick em _poll_loop;
    # zerado em shutdown.
    _last_state: ControllerState | None = None
    # FEAT-KEYBOARD-EMULATOR-01: criados em runtime por start_keyboard_emulation
    # (OSK helper + touchpad reader). Declarados aqui para satisfazer mypy
    # strict via DaemonProtocol (PYDANTIC-PROTOCOL-DAEMON-01).
    _osk_controller: Any = None
    _touchpad_reader: Any = None
    # FEAT-DAEMON-PAUSE-RESUME-01: pausado, o poll loop segue lendo estado/
    # bateria e publicando STATE_UPDATE, mas NÃO despacha input (gatilhos/
    # teclado/mouse/hotkey) nem publica BUTTON_DOWN/UP — daemon vivo, sem afetar
    # o sistema. Reusa o gate do grace-period; persistido via utils.session.
    _paused: bool = field(default=False)
    # FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01: subsystems que falharam ao iniciar
    # (nome -> erro). Um subsystem quebrado é isolado aqui em vez de derrubar o
    # daemon (poll/IPC/perfis seguem). Exposto para diagnóstico (doctor/status).
    _failed_subsystems: dict[str, str] = field(default_factory=dict)
    # COR-01/COR-03: registro de identidade MAC→slot de sessão ("Controle N"
    # estável + cor automática por controle). Fiado em `run()` SÓ quando o
    # backend suporta o provider (`set_auto_output_provider`) — com o
    # FakeController fica None e nada de controllers.json é lido/escrito
    # (testes herméticos). O reconcile roda no tick lento do poll loop.
    identity_registry: Any = None
    # EXT-04: registro de identidade dos controles EXTERNOS (uniq→slot global
    # de co-op, namespace `externals` do controllers.json) + aplicador de LED
    # do tick lento. Fiados JUNTO com o identity_registry (backend real) —
    # com o FakeController ficam None: nenhuma enumeração de /dev/input nem
    # escrita de LED em teste/smoke (hermeticidade por construção).
    external_registry: Any = None
    _external_led_sync: Any = None
    # HANG-01: task auxiliar do tick de LED dos externos — `_sync_external_
    # leds` deixou de ser aguardado inline pelo poll loop (ver `_schedule_
    # external_tick`). None = nenhum tick em voo agora.
    _external_tick_task: asyncio.Task[Any] | None = None
    # HANG-01: timeouts CONSECUTIVOS do tick (zerado por um tick que termina
    # dentro do prazo). >= EXTERNAL_TICK_MAX_TIMEOUTS degrada.
    _external_tick_timeouts: int = 0
    # HANG-01: True após degradar (2+ timeouts seguidos) — o poll loop para
    # de chamar `_schedule_external_tick` até o `InputDirWatch` observar
    # mudança real em /dev/input (replug: o inventário pode ter mudado).
    _external_tick_degraded: bool = False
    # HANG-01: ciclos do poll loop que PULARAM o agendamento porque o tick
    # anterior ainda não tinha terminado (guard de reentrância) — só
    # observabilidade, nunca lido por lógica de gate.
    _external_tick_skipped: int = 0
    # PROTOCOLO-QUEDA-01 (07/08): `battery_journal.DiarioDaBateria` — quem
    # escreve a carga no journal. Criado no 1º uso por `diario_da_bateria`
    # (espelho do `get_coop_manager`); None até a primeira sonda.
    _diario_bateria: Any = None
    # HANG-01: watch barato de /dev/input (mesma classe do EVDEV_WATCHDOG)
    # usado só para destravar a degradação; criado sob demanda.
    _external_tick_watch: Any = None
    # NUMA-01: casca do sinal "jogo real ativo" (`game`|`daemon`|`unknown`) —
    # ao contrário de identity/external_registry, SEMPRE nasce (mesmo com
    # FakeController): é ela quem sustenta o contrato público
    # `display_authority`. Só a INJEÇÃO no backend (`set_game_authority_
    # provider`) é gateada por `hasattr` — sem o método, o backend fica
    # byte-idêntico ao HEAD (fail-safe da síntese da Onda N).
    _game_signal: Any = None

    # ------------------------------------------------------------------
    # Ciclo de vida público
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Entry point: subsystems → reconnect_loop em background → wait → shutdown.

        BUG-DAEMON-NO-DEVICE-FATAL-01: a tentativa inicial de conexão deixou
        de ser bloqueante. Subsystems (IPC, UDP, autoswitch, hotkey, plugins)
        sobem ANTES do `reconnect_loop`, garantindo que o socket IPC exista
        em ≤5s mesmo sem hardware plugado. Plug do controle posterior é
        detectado pelo probe e dispara `restore_last_profile` uma única vez.
        """
        from hefesto_dualsense4unix.daemon.connection import (
            reconnect_loop,
            shutdown,
        )
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            start_mic_hotkey,
        )

        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        self._stop_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hefesto-hid")
        # HANG-01: pool próprio p/ o tick de externos — NUNCA o mesmo de cima
        # (ver comentário de `_external_executor` e `EXTERNAL_TICK_TIMEOUT_
        # SEC`; 1 worker basta, o guard de reentrância nunca deixa 2 ticks
        # concorrentes de verdade).
        self._external_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="hefesto-ext"
        )
        self._install_signal_handlers(loop)
        # FEAT-DAEMON-PAUSE-RESUME-01: retoma pausado se a sessão anterior
        # terminou pausada (o poll loop nasce respeitando _paused).
        from hefesto_dualsense4unix.utils.session import load_paused_state
        self._paused = load_paused_state()
        # FEAT-AUTOSWITCH-LOCK-01: retoma congelada se a sessão anterior terminou
        # assim (a escolha DELA de "não troca de perfil sozinho" atravessa reboot).
        from hefesto_dualsense4unix.utils.session import load_autoswitch_locked
        self.store.set_autoswitch_locked(load_autoswitch_locked())
        # FEAT-NATIVE-MODE-01: se a sessão anterior terminou em Modo Nativo, sobe
        # SOLTO — o controle fica com o jogo. Implica pausado e NÃO restaura
        # emulação nem re-aplica perfil (os `not self._native_mode` abaixo e o
        # gate em `restore_last_profile`).
        from hefesto_dualsense4unix.utils.session import load_native_mode
        self._native_mode, self._native_emu_stash = load_native_mode()
        if self._native_mode:
            # O gate de dispatch é o próprio _native_mode (consultado no poll
            # loop); não força _paused (evita conflatar com o pause manual).
            self.store.set_native_mode_active(True)
        # FEAT-MOUSE-PERSIST-01: restaura a emulação de mouse se a sessão anterior
        # a deixou ligada — antes o toggle voltava ao default (off) a cada restart
        # do daemon (reboot, takeover, reload). Só liga; nunca força off.
        # FEAT-MOUSE-CURSOR-FEEL-01 (A5): restaura também speed/scroll do flag
        # JSON, com clamp ao contrato (1-12 / 1-5); flag legado sem velocidades
        # (`"1\n"`) mantém os defaults da config.
        from hefesto_dualsense4unix.utils.session import load_mouse_emulation
        mouse_on, mouse_speed, mouse_scroll = load_mouse_emulation()
        if mouse_on and not self._native_mode:
            self.config.mouse_emulation_enabled = True
            if mouse_speed is not None:
                self.config.mouse_speed = max(1, min(12, int(mouse_speed)))
            if mouse_scroll is not None:
                self.config.mouse_scroll_speed = max(1, min(5, int(mouse_scroll)))
        # FEAT-DSX-GAMEPAD-FLAVOR-01: restaura o gamepad virtual (liga + flavor)
        # se a sessão anterior o deixou ligado. Mútua exclusão: o gamepad tem
        # precedência sobre o mouse (jogar = controle vai pro jogo).
        from hefesto_dualsense4unix.utils.session import load_gamepad_emulation
        gp_enabled, gp_flavor = load_gamepad_emulation()
        if gp_enabled and not self._native_mode:
            self.config.gamepad_emulation_enabled = True
            if gp_flavor:
                self.config.gamepad_flavor = gp_flavor
            self.config.mouse_emulation_enabled = False
        # EMULACAO-NO-JOGO-01: restaura a PREFERÊNCIA de teclado emulado. Ao lado
        # do mouse e do gamepad de propósito — é a superfície que faltava (o
        # teclado era o único dos três sem flag em disco, e por isso o único que
        # não tinha como ser desligado). Três valores: `None` = nunca configurada
        # e o default da config vale (compat: continua ligado); `True`/`False` =
        # decisão DELA e vence o default, inclusive um default vindo do env.
        # Best-effort por construção (o load nunca levanta).
        from hefesto_dualsense4unix.utils.session import load_keyboard_preference
        kbd_pref = load_keyboard_preference()
        if kbd_pref is not None:
            self.config.keyboard_emulation_enabled = kbd_pref
        # FEAT-DSX-COOP-LOCAL-01 / LEIGO-01: apaga o opt-out gravado por versão
        # antiga (`coop_disabled.flag`) — one-shot, com marker próprio.
        #
        # COOP-SEM-INTERRUPTOR-01 (06/08/2026): aqui havia também
        # `if load_coop_enabled(): self.config.coop_enabled = True`. Saiu, e a
        # remoção é a entrega, não faxina: com ela, o piso do co-op passa a ter
        # UM dono só (`DaemonConfig.coop_enabled`, agora `True`). Enquanto o
        # boot forçava `True` aqui, arrancar o default do dataclass não reprovava
        # teste nenhum — a cura tinha um sósia.
        from hefesto_dualsense4unix.utils.session import migrate_coop_optout

        migrate_coop_optout()
        logger.info("daemon_starting", poll_hz=self.config.poll_hz, paused=self._paused)
        try:
            self._tasks = [asyncio.create_task(self._poll_loop(), name="poll_loop")]
            # FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01: cada subsystem sobe isolado —
            # uma falha é registrada em _failed_subsystems e o boot segue
            # (poll/IPC/perfis sobrevivem a um subsystem quebrado).
            if self.config.ipc_enabled:
                await self._safe_start("ipc", self._start_ipc)
            if self.config.udp_enabled:
                await self._safe_start("udp", self._start_udp)
            if self.config.autoswitch_enabled:
                await self._safe_start("autoswitch", self._start_autoswitch)
            if self.config.mouse_emulation_enabled:
                await self._safe_start("mouse", self._start_mouse_emulation)
            if self.config.gamepad_emulation_enabled:
                await self._safe_start("gamepad", self._start_gamepad_emulation)
            if self.config.keyboard_emulation_enabled:
                await self._safe_start("keyboard", self._start_keyboard_emulation)
            await self._safe_start("hotkey", lambda: start_hotkey_manager(self))
            if self.config.mic_button_toggles_system:
                await self._safe_start("mic_hotkey", lambda: start_mic_hotkey(self))
            # BT-MIC-REGISTRY-01: ponte de microfone por Bluetooth. O gate de
            # opt-in vive DENTRO do starter (`is_enabled`) — desligado, ele
            # devolve sem instanciar nada. Sobe aqui, ao lado do resto do
            # mundo de microfone e antes dos plugins (código de usuário).
            await self._safe_start("bt_mic", self._start_bt_mic)
            await self._safe_start("plugins", self._start_plugins)
            # FEAT-METRICS-01: sobe o servidor de métricas Prometheus (gate
            # interno respeita metrics_enabled). Antes nunca era iniciado —
            # metrics_enabled/metrics_port eram config morta.
            await self._safe_start("metrics", self._start_metrics)
            # FEAT-CONFIG-AUDIT-BOOT-01: valida os perfis no boot e avisa se houver
            # corrompidos (em vez de só pulá-los silenciosamente no fallback).
            self._audit_config_on_boot()
            # FEAT-SYSTEM-AUTOREPAIR-BOOT-01: detecta infra quebrada (udev/WirePlumber)
            # e AVISA o comando de reparo — nunca roda sudo sozinho.
            self._check_system_on_boot()
            # COR-01/COR-03: fiação do registro de identidade + provider de
            # cor automática ANTES do connect inicial — o 1º reconcile do
            # backend (`_reapply_desired`) já resolve com o provider e os
            # slots restaurados do disco (a cor nasce certa no mesmo tick de
            # hotplug, D1). Fora do caminho quente (o load é um read único).
            self._wire_identity_registry()
            # EXT-04: identidade + LED dos externos, no MESMO gate de backend
            # real do identity_registry (fake => tudo desligado).
            self._wire_external_registry()
            # NUMA-01: sinal "jogo real ativo" — ATIVA o gate NUMA-02/03
            # (dormente até aqui). Ao contrário dos dois acima, nasce SEMPRE
            # (ver docstring de `_wire_game_signal`).
            self._wire_game_signal()
            # S-5: opener broker-aware da leitura de calibração 0x05 — sem ele
            # o `read_calibration` dá EACCES no hidraw ESCONDIDO (promoção
            # VPAD-02, respawn de coop) e o vpad herda calibração canônica
            # (drift do gyro). Mesmo gate de backend real dos wirings acima.
            self._wire_feature_opener()
            # BUG-DAEMON-NO-DEVICE-FATAL-01: tentativa inicial best-effort.
            # No caminho real, se o controle estiver ausente, o backend
            # PyDualSenseController.connect() trata "No device detected" em
            # silencio (offline-OK). Outros erros (permissão hidraw, USB
            # transitório) sao logados aqui e o reconnect_loop reassume em
            # background. No caminho FAKE, conecta imediatamente.
            try:
                await self._run_blocking(self.controller.connect)
                if self.controller.is_connected():
                    transport = self.controller.get_transport()
                    self.bus.publish(
                        EventTopic.CONTROLLER_CONNECTED, {"transport": transport}
                    )
                    logger.info("controller_connected", transport=transport)
                    # SPRINT-UHID-VPAD-01 + VPAD-03: com o blueprint canônico o
                    # vpad do P1 já nasce uhid no boot (isto aqui é no-op no
                    # caminho feliz). A chamada fica como REDE DE SEGURANÇA:
                    # recupera um vpad que degradou para uinput por razão
                    # transitória (ex.: /dev/uhid sem ACL na 1ª sessão).
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                            upgrade_primary_vpad_to_uhid,
                        )

                        upgrade_primary_vpad_to_uhid(self)
                    # FEAT-COSMIC-NOTIFICATIONS-01: opt-in via env var.
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.integrations.desktop_notifications import (
                            notify_controller_connected,
                        )
                        notify_controller_connected(transport or "usb")
                    from hefesto_dualsense4unix.daemon.connection import (
                        restore_last_profile,
                    )

                    with contextlib.suppress(Exception):
                        await restore_last_profile(self)
            except Exception as exc:
                logger.warning(
                    "controller_initial_connect_failed",
                    err=str(exc),
                    exc_info=True,
                )
            # ENV-VELHA-NO-BOOT-01 (10/08/2026): materializa o launch_env no
            # BOOT, e não só nas transições.
            #
            # Ela perguntou, com o defeito na mão: *"temos soluções que não
            # dependam desse feito manual? Tipo mais automático de fato?"*.
            # Tinha razão, e o buraco era estrutural: TODOS os gatilhos de
            # `materialize_launch_env` eram de TRANSIÇÃO — start/stop do
            # gamepad, Modo Nativo, co-op, os handlers de IPC. Nenhum no start
            # do daemon. Provado no disco dela em 10/08: apaguei o
            # `steam_app_3357650.env`, reiniciei o daemon, e o arquivo NÃO
            # voltou.
            #
            # O preço aparecia exatamente no pior momento — quando a cura acabou
            # de entrar. O daemon subia com o código novo e continuava servindo
            # ao wrapper o arquivo escrito pelo daemon ANTIGO, até ela conectar
            # o controle. É a versão em arquivo do `[[o-daemon-vivo-e-mais-velho-
            # que-o-codigo]]`: quem estava velho não era o processo, era o que
            # ele tinha deixado no disco. Foi assim que a cura do
            # TRES-CONTROLES-01 nasceu inerte na máquina dela.
            #
            # Aqui, no fim do boot, porque é onde o estado já é o real: modo,
            # máscara, backends e perfil restaurado. Antes disto o conteúdo
            # sairia de um estado provisório, e regravar com dado provisório é
            # pior que não regravar. `suppress` porque a regra desta função vale
            # inteira: materialização quebrada nunca derruba o start.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self)
            # Reconnect probe em background — não bloqueia o boot e cobre
            # transicoes onlineoffline em runtime.
            self._reconnect_task = asyncio.create_task(
                reconnect_loop(self), name="reconnect_loop"
            )
            self._tasks.append(self._reconnect_task)
            await self._stop_event.wait()
        finally:
            await shutdown(self)

    def stop(self) -> None:
        """Sinaliza parada; idempotente."""
        if self._stop_event is not None and not self._stop_event.is_set():
            logger.info("daemon_stop_requested")
            self._stop_event.set()

    def pause(self) -> None:
        """Pausa o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01).

        O daemon segue vivo: lê estado/bateria, publica STATE_UPDATE e atende o
        IPC, mas para de despachar gatilhos/teclado/mouse/hotkey e de publicar
        BUTTON_DOWN/UP. Idempotente; persiste para retomar pausado após restart.
        """
        if not self._paused:
            self._paused = True
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(True)
            logger.info("daemon_paused")

    def resume(self) -> None:
        """Retoma o despacho de input. Idempotente.

        O baseline de botões ficou sincronizado durante a pausa (o poll loop
        seguiu primando o edge-tracker e atualizando previous_buttons), então
        botões segurados ao retomar não disparam — só após soltar e
        re-pressionar (mesma garantia do fim do grace-period).
        """
        if self._paused:
            self._paused = False
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(False)
            logger.info("daemon_resumed")

    def is_paused(self) -> bool:
        """True se o despacho de input está pausado."""
        return self._paused

    def is_native_mode(self) -> bool:
        """True se o Modo Nativo está ativo (controle solto para o jogo)."""
        return self._native_mode

    def set_native_mode(
        self,
        enabled: bool,
        *,
        reapply: bool = True,
        restore_stash: bool = False,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga/desliga o Modo Nativo — "release total" do controle.

        FEAT-NATIVE-MODE-01. Para jogar Sackboy & cia com os gatilhos adaptativos
        NATIVOS da Sony (dirigidos pelo jogo), sem o hefesto no meio.

        `enabled=True`: solta o controle — gatilhos Off/Off (o jogo impõe os
        seus), rumble em passthrough (`rumble_active=None`, o hefesto não
        re-asserta), emulação de mouse E gamepad desligada (libera grab/uinput) —
        o ESTADO de emulação é guardado (stash) para restaurar depois. Gate
        `native_mode_active` (autoswitch/hotkey NÃO re-aplicam perfil). O poll
        loop consulta `_native_mode` DIRETAMENTE (não via `pause()`), então o
        dispatch fica congelado independente de pause/resume. Persiste flag+stash.

        `enabled=False`: limpa o gate, zera os motores (o jogo não é mais o dono
        do rumble — HARM-16), re-ativa o último perfil (gatilhos/rumble) e
        restaura a emulação do stash (gamepad tem precedência sobre mouse).
        `reapply=False` quando o chamador NÃO quer o last_profile re-aplicado
        (reversão por perfil: o perfil novo acabou de aplicar triggers/LEDs).
        `restore_stash=True` com `reapply=False` restaura SÓ a emulação do
        stash (BUG-NATIVE-REVERT-DROPS-STASH-01: a reversão por
        perfil-sem-opinião deixava a usuária SEM gamepad ao sair do jogo —
        flagrado ao vivo no Sackboy: alt-tab → nativo off → gamepad nunca
        voltava).

        NOTA (BUG-NATIVE-* da auditoria): o Modo Nativo NÃO usa mais `pause()` —
        gateia o dispatch pelo próprio flag. Assim `daemon.resume` não "des-solta"
        o controle e um pause manual anterior não é pisado.

        Idempotente. Retorna o novo estado.
        """
        from hefesto_dualsense4unix.utils.session import (
            load_gamepad_emulation,
            load_mouse_emulation,
            save_native_mode,
        )

        if origin == "manual":
            # FEAT-PROFILE-MODE-01: gesto manual de Modo Nativo entra na mesma
            # janela de respeito dos toggles de emulação — um perfil (autoswitch)
            # não liga/desliga o nativo por 30s após a usuária mexer na mão.
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: a POSSE do eixo de modo passa para a usuária aqui, ANTES
            # do early-return de idempotência abaixo. A limpeza que já existia
            # no fim da função é inalcançável quando `enabled` não muda — e aí
            # o flag "modo veio de perfil" ficava pendurado: passados os 30 s do
            # carimbo, o primeiro perfil sem `mode` revertia o que ela ligou na
            # mão. Carimbo e posse andam juntos, sempre.
            self._mode_from_profile = None
        if enabled == self._native_mode:
            return self._native_mode
        if enabled:
            # Captura o estado de emulação ANTES do release (o release apaga os
            # flags próprios). BUG-NATIVE-DESTROYS-GAMEPAD-01.
            m_on, m_speed, m_scroll = load_mouse_emulation()
            g_on, g_flavor = load_gamepad_emulation()
            self._native_emu_stash = {
                "mouse": [bool(m_on), m_speed, m_scroll],
                "gamepad": [bool(g_on), g_flavor],
            }
            self._native_mode = True
            self.store.set_native_mode_active(True, origin=origin)
            save_native_mode(True, emu_stash=self._native_emu_stash)
            self._release_controller_to_game()
        else:
            self._native_mode = False
            self.store.set_native_mode_active(False)
            save_native_mode(False)
            # FEAT-NATIVE-OUTPUT-MUTE-01: desmuta ANTES do reapply — o
            # perfil/rumble/LED re-aplicados precisam chegar ao controle.
            unmute = getattr(self.controller, "set_output_mute", None)
            if callable(unmute):
                with contextlib.suppress(Exception):
                    unmute(False)
            # HARM-16: quem estava vibrando era o JOGO (escrevendo direto no
            # hidraw, com o nosso output mutado). Ao sair, ninguém zera esses
            # motores: `rumble_active` está em passthrough (None), então o
            # reassert do poll loop é no-op e a vibração fica FIXA para sempre.
            self._zero_rumble_motors()
            if reapply:
                self._reapply_last_profile()
            if reapply or restore_stash:
                self._restore_emulation_from_stash()
            self._native_emu_stash = {}
        if origin == "manual":
            self._mode_from_profile = None
        # DEDUP-04: o Modo Nativo muda o conteúdo das envs de launch
        # (sem DISABLE/IGNORE — o jogo fala com o hidraw do FÍSICO,
        # GUERRA-01). Os hooks de start/stop do gamepad não cobrem o caso
        # "nativo ligado com emulação já desligada", então regrava aqui, no
        # fim da transição inteira.
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self)
        logger.info("native_mode_changed", native=enabled, origin=origin)
        return self._native_mode

    def _release_controller_to_game(self) -> None:
        """Neutraliza a saída do hefesto no controle (FEAT-NATIVE-MODE-01)."""
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        # Gatilhos Off/Off: o hefesto não impõe resistência; o jogo sobrescreve.
        with contextlib.suppress(Exception):
            off = build_from_name("Off", [])
            self.controller.set_trigger("left", off)
            self.controller.set_trigger("right", off)
        # Rumble passthrough: reassert_rumble pula quando rumble_active é None.
        self.config.rumble_active = None
        # Emulação off: libera grab de evdev / device uinput. origin="profile"
        # de propósito: desligar a emulação no release NÃO é um gesto manual da
        # usuária — se carimbasse `_emu_manual_ts`, o lock de 30s BLOQUEARIA o
        # restore ao desligar (BUG-NATIVE-RELEASE-LOCKS-RESTORE-01).
        with contextlib.suppress(Exception):
            self.set_mouse_emulation(False, origin="profile")
        with contextlib.suppress(Exception):
            self.set_gamepad_emulation(False, origin="profile")
        # FEAT-NATIVE-OUTPUT-MUTE-01: release TOTAL inclui o output HID — sem
        # isto o keepalive do report_thread pisoteava o rumble/gatilhos/LED que
        # o JOGO escrevia no hidraw (rumble morto no Sackboy, ao vivo).
        mute = getattr(self.controller, "set_output_mute", None)
        if callable(mute):
            with contextlib.suppress(Exception):
                mute(True)

    def _reapply_last_profile(self) -> None:
        """Re-ativa o perfil corrente ao sair do Modo Nativo (gatilhos/teclado).

        PERFIL-03: prefere `store.active_profile` (o perfil ATIVO — inclusive
        um escolhido pelo autoswitch pela janela em foco) e só cai no
        session.json quando não há ativo em memória. Com a semântica nova
        (session.json = última escolha MANUAL), a ordem antiga re-aplicaria a
        última escolha manual por cima do perfil que o autoswitch ativou —
        mudança não intencional apontada pela tabela dos 5 call sites. A
        ativação vai com `origin="system"`: sair do nativo não é escolha nova
        de perfil e NÃO regrava a intenção manual.
        """
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.utils.session import load_last_profile

        name = self.store.active_profile or load_last_profile()
        if not name:
            return
        manager = ProfileManager(
            controller=self.controller,
            store=self.store,
            keyboard_device_provider=lambda: getattr(self, "_keyboard_device", None),
            mouse_applier=self.apply_profile_mouse,
            suppression_applier=self.apply_profile_suppression,
            # PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08), item 6: as três
            # seções que faltavam. Esta rota era a única das quatro que montava
            # o manager sem elas, e o efeito é o que ela sente ao desligar o
            # Modo Nativo: gatilhos e LEDs voltam, mas a máscara do vpad, a
            # política de rumble e o volume do alto-falante do perfil ficam
            # como o jogo os deixou.
            #
            # O `mode_applier` vai EMBRULHADO, e o embrulho é a nota datada da
            # decisão que estava aqui: a FEAT-PROFILE-MODE-01 tirou o applier
            # inteiro porque um `last_profile` com `mode.kind=native` seria
            # religado na hora (o `_native_mode` já é False quando chegamos
            # aqui — `set_native_mode` o zera antes do reapply), e sair do
            # nativo viraria um laço. Aquilo continua verdade e continua
            # barrado; o que não se justifica é o preço colateral — perder
            # `gamepad`/`desktop` e a reversão do modo por causa do caso
            # `native`. O embrulho barra SÓ o `native`.
            #
            # `getattr` nos três pelo mesmo motivo das outras rotas
            # (`subsystems/autoswitch.py`, `subsystems/ipc.py`): este método é
            # chamado desligado da instância por dublês da suíte, e um atributo
            # ausente não pode derrubar a saída do Modo Nativo — sem o applier,
            # a seção volta a ser ignorada, que é o comportamento histórico.
            mode_applier=getattr(self, "_mode_applier_ao_sair_do_nativo", None),
            rumble_policy_applier=getattr(self, "apply_profile_rumble_policy", None),
            speaker_applier=getattr(self, "apply_profile_speaker", None),
        )
        with contextlib.suppress(Exception):
            manager.activate(name, origin="system")

    def _mode_applier_ao_sair_do_nativo(
        self,
        mode: Any | None,
        *,
        profile: Any | None = None,
        origin: str = "system",
    ) -> str:
        """`apply_profile_mode` menos o `kind="native"` (item 6 da leva de 05/08).

        Usado SÓ pelo `_reapply_last_profile`, que roda ao DESLIGAR o Modo
        Nativo. Religar o nativo aqui seria desfazer o gesto que acabou de
        acontecer — `set_native_mode(False)` já zerou `_native_mode`, então o
        applier veria "nativo desligado, o perfil pede nativo" e o ligaria de
        volta no mesmo instante. É a razão pela qual a FEAT-PROFILE-MODE-01
        tirou o applier inteiro desta rota; a diferença é que agora só o caso
        `native` paga.

        As demais seções de `mode` seguem: `gamepad` devolve a máscara/co-op do
        perfil, `desktop` limpa, e `mode=None` reverte o que outro perfil tinha
        ligado. `IGNORADO_GESTO_DELA` é o estado certo do vocabulário — a
        decisão já é dela, e é mais específica que o que o perfil pede.
        """
        if getattr(mode, "kind", None) == "native":
            logger.info(
                "profile_mode_skipped_saida_do_nativo",
                profile=getattr(profile, "name", None),
            )
            return IGNORADO_GESTO_DELA
        return self.apply_profile_mode(mode, profile=profile, origin=origin)

    def _zero_rumble_motors(self) -> None:
        """Zera os motores ao SAIR de um modo (HARM-16). Thin wrapper."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            zero_motors_on_mode_exit,
        )

        zero_motors_on_mode_exit(self)

    def _restore_emulation_from_stash(self) -> None:
        """Restaura a emulação capturada antes do Modo Nativo (FEAT-NATIVE-MODE-01).

        Gamepad tem precedência sobre mouse (mesma regra do boot: jogar = controle
        vai pro jogo). Roda DEPOIS de `_reapply_last_profile` para vencer uma seção
        mouse do perfil (o estado pré-nativo da usuária manda).
        BUG-NATIVE-DESTROYS-GAMEPAD-01.
        """
        stash = getattr(self, "_native_emu_stash", None) or {}
        g = stash.get("gamepad") or [False, None]
        m = stash.get("mouse") or [False, None, None]
        if g[0]:
            with contextlib.suppress(Exception):
                self.set_gamepad_emulation(True, g[1], origin="profile")
        elif m[0]:
            with contextlib.suppress(Exception):
                self.set_mouse_emulation(
                    True, m[1], m[2], origin="profile"
                )

    def reload_config(self, new_config: DaemonConfig) -> None:
        """Aplica nova configuração em runtime sem reiniciar o daemon."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            stop_hotkey_manager,
        )

        old = self.config
        self.config = new_config
        stop_hotkey_manager(self)
        start_hotkey_manager(self)
        if old.mouse_emulation_enabled != new_config.mouse_emulation_enabled:
            # ORIGEM-QUE-MENTE-01: aplicar config nova é reconciliação.
            self.set_mouse_emulation(
                new_config.mouse_emulation_enabled,
                speed=new_config.mouse_speed,
                scroll_speed=new_config.mouse_scroll_speed,
                origin="profile",
            )
        if old.keyboard_emulation_enabled != new_config.keyboard_emulation_enabled:
            if new_config.keyboard_emulation_enabled:
                self._start_keyboard_emulation()
            else:
                self._stop_keyboard_emulation()
        keys_changed = [
            k for k in new_config.__dataclass_fields__
            if getattr(old, k, None) != getattr(new_config, k)
        ]
        logger.info("daemon_config_reloaded", keys_changed=keys_changed)

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga/desliga emulação de mouse e atualiza velocidades. Usado pelo IPC.

        BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: `origin` distingue o gesto MANUAL
        (IPC/GUI/CLI/hotkey — default, preserva todos os callers) da aplicação
        por PERFIL (`apply_profile_mouse`). Manual carimba `_emu_manual_ts`,
        travando o applier de perfil por `MANUAL_PROFILE_LOCK_SEC`.
        """
        from hefesto_dualsense4unix.daemon.subsystems.mouse import (
            start_mouse_emulation,
            stop_mouse_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))
        # BUG-EMU-DEVICE-RACE-01: serializa a transição de device (create/destroy)
        # para não colidir com set_gamepad_emulation/outra thread.
        with self._emu_lock:
            if enabled:
                # FEAT-DSX-GAMEPAD-FLAVOR-01: mútua exclusão — ligar o mouse
                # desliga o gamepad virtual (e libera o grab do controle).
                if self._gamepad_device is not None:
                    self._stop_gamepad_emulation()
                ok = start_mouse_emulation(self)
                if ok and self._mouse_device is not None:
                    self._mouse_device.set_speed(
                        mouse_speed=self.config.mouse_speed,
                        scroll_speed=self.config.mouse_scroll_speed,
                    )
                    # FEAT-MOUSE-CURSOR-FEEL-01 (A5): com device JÁ vivo,
                    # start_mouse_emulation retorna cedo sem persistir — re-salva
                    # o flag para que "ligar de novo com speed nova" sobreviva a
                    # restart (no start de verdade a escrita é redundante).
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.utils.session import (
                            save_mouse_emulation,
                        )

                        save_mouse_emulation(
                            True,
                            speed=self.config.mouse_speed,
                            scroll_speed=self.config.mouse_scroll_speed,
                        )
                return ok
            stop_mouse_emulation(self)
            return True

    def restore_mouse_preference(self) -> bool:
        """Aplica a preferência de mouse persistida (HARM-06). Retorna se ligou.

        É o que faz "Controlar o PC" ser um modo de verdade, e não só o
        desligar dos outros dois: entrar nele devolve o cursor conforme a última
        escolha da usuária. Sem isto o controle ficava sem função NENHUMA até
        alguém achar a aba Mouse.

        Nunca configurada (flag ausente) liga por default — a alternativa é o
        controle mudo. "Desligado de propósito" é respeitado, e é por isso que
        `load_mouse_preference` distingue os dois casos.

        A leitura mora aqui, no daemon, porque é ele quem grava a preferência —
        um segundo leitor na GUI seria um segundo dono do mesmo conceito.
        """
        from hefesto_dualsense4unix.utils.session import load_mouse_preference

        pref, speed, scroll_speed = load_mouse_preference()
        if pref is None:
            pref = True
        # ORIGEM-QUE-MENTE-01: restaurar preferência salva é reconciliação.
        ok = self.set_mouse_emulation(pref, speed, scroll_speed, origin="profile")
        logger.info("mouse_preference_restored", enabled=pref, ok=ok)
        return bool(pref and ok)

    def set_mouse_speed(
        self,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Atualiza velocidades da emulação SEM ligar/desligar (speed-only).

        BUG-MOUSE-GUI-SYNC-01 (A4): rota dos sliders da GUI — nunca faz
        start/stop nem CRIA o flag de emulação. Com device vivo aplica na
        hora; sem device só atualiza a config (vale quando ligar). Religar a
        emulação (e matar o gamepad virtual) por slider é impossível aqui.

        FEAT-MOUSE-CURSOR-FEEL-01 (A5): com a emulação JÁ LIGADA, re-persiste
        o flag existente com as velocidades novas — mudança de speed com o
        mouse ligado tem que sobreviver a restart. Com a emulação desligada
        nada é escrito (criar o flag aqui religaria a emulação no boot — a
        regressão exata do A4).
        """
        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))
        if self._mouse_device is not None:
            self._mouse_device.set_speed(
                mouse_speed=self.config.mouse_speed,
                scroll_speed=self.config.mouse_scroll_speed,
            )
        if self.config.mouse_emulation_enabled:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_mouse_emulation

                save_mouse_emulation(
                    True,
                    speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed,
                )
        return True

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        """Liga/desliga a emulação de TECLADO. Usado pelo IPC `keyboard.emulation.set`.

        EMULACAO-NO-JOGO-01. É o interruptor que o teclado nunca teve — e ele
        tem dentes: desligar DESTRÓI o device virtual (via
        `stop_keyboard_emulation`), então o gate do poll loop
        (`_keyboard_device is not None`) fecha por consequência, do mesmo jeito
        que o mouse dela já estava honestamente desligado. Retorna o estado
        efetivo ao final (o pedido pode falhar por /dev/uinput).

        `persist=False` existe para o restore do boot e para os testes: o
        caminho normal (gesto dela) grava `keyboard_emulation.flag` para que a
        escolha atravesse restart/reboot — era exatamente o que faltava, já que
        o default da config é True e voltava a valer a cada boot.

        NÃO carimba `_emu_manual_ts` (diferente de `set_mouse_emulation`): não há
        applier de perfil para o teclado, então o carimbo só serviria para
        congelar por 30 s a aplicação de modo/mouse de perfil por causa de um
        toggle que nada tem a ver com eles.

        Desligar aqui tira também o teclado virtual do sistema (L3/R3) e as três
        regiões do touchpad — quem chama pela interface tem de dizer isso a ela.
        """
        # BUG-EMU-DEVICE-RACE-01: mesma serialização de set_mouse_emulation —
        # o IPC roda no event loop e o boot/reload na thread do executor.
        with self._emu_lock:
            self.config.keyboard_emulation_enabled = bool(enabled)
            if enabled:
                self._start_keyboard_emulation()
            else:
                self._stop_keyboard_emulation()
            if persist:
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.utils.session import (
                        save_keyboard_emulation,
                    )

                    save_keyboard_emulation(bool(enabled))
            ativo = self._keyboard_device is not None
            logger.info(
                "keyboard_emulation_set",
                enabled=bool(enabled),
                device_ativo=ativo,
                persistido=bool(persist),
            )
            # Ligar só é "ok" com device de pé; desligar sempre alcança o estado
            # pedido (`stop_keyboard_emulation` é idempotente e best-effort).
            return ativo if enabled else True

    # ORIGEM-QUE-MENTE-01 (08/08/2026): `origin` NÃO tem default, e é
    # keyword-only. O default antigo era `"manual"`, e isso fazia o daemon
    # ler a AUSÊNCIA de informação como a mão dela — quem esquecesse o
    # parâmetro era promovido a gesto humano.
    #
    # O que isso custou, MEDIDO: com o Sackboy aberto e marcado na allowlist
    # do Steam Input, um cliente reconciliando estado chamou o setter sem
    # `origin`; o portão JOGO-01 (`gamepad.py`, `if origin != "manual"`)
    # deixou passar, o gamepad virtual voltou com o grab e o esconde-esconde
    # pulados, e o jogo passou a ver o físico E o virtual. Ela fotografou um
    # "Jogador 3" fantasma. Ver JOGADOR-3-FANTASMA-01.
    #
    # E o ramo `origin == "manual"` ainda carimba `_emu_manual_ts`, que cala
    # o perfil por 30 s: o cliente distraído não só furava o portão como
    # silenciava o autoswitch depois.
    #
    # Sem default, o `mypy` obriga cada chamador a DECLARAR o que é. Silêncio
    # deixa de ser resposta.
    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara. Usado pelo IPC.

        FEAT-DSX-GAMEPAD-FLAVOR-01. `flavor` em ('dualsense','xbox'); None mantém
        o atual. Ligar desliga a emulação de mouse (mútua exclusão) e SAI do Modo
        Nativo (idem). Retorna True se o estado pedido foi alcançado.

        BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: um `gamepad on` manual carimba
        `_emu_manual_ts` — assim um perfil point-and-click focado logo em seguida
        (autoswitch) NÃO mata o gamepad ligado na mão (lock de 30s).

        HARM-01: sair do nativo antes de ligar o vpad é garantido AQUI porque o
        daemon é o único ponto por onde todas as superfícies passam (GUI, applet,
        CLI, perfil, hotkey, autoswitch) — a CLI não pode importar o
        `app.actions.mode_transition` sem arrastar GTK. Sem isto, um `gamepad on`
        com o nativo ligado deixava os dois ligados juntos: o físico grabado pelo
        vpad e o dispatch congelado pelo gate do nativo = jogo sem controle
        nenhum. O caminho inverso (`native.mode.set True` com o vpad ligado) já
        era coberto pelo `_release_controller_to_game`.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            start_gamepad_emulation,
            stop_gamepad_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: gesto manual toma a POSSE do eixo de modo — paridade com
            # `_suppress_from_profile` (set_emulation_suppressed) e
            # `_rumble_policy_from_profile` (mark_rumble_policy_manual), que já
            # faziam isso. Sem esta linha, o carimbo protegia por só 30 s: depois
            # o primeiro perfil sem seção `mode` — quase todos os dela — chamava
            # `set_gamepad_emulation(False, origin="profile")` sobre um vpad que
            # ela tinha ligado na mão.
            self._mode_from_profile = None
        # BUG-EMU-DEVICE-RACE-01: mesma serialização do set_mouse_emulation.
        with self._emu_lock:
            if enabled:
                # HARM-01: a MESMA saída que a GUI já pede no passo 1 do plano
                # dela (`native.mode.set False`) — não uma segunda semântica de
                # "sair do nativo". Quando a GUI manda o passo, este vira no-op
                # (o setter é idempotente). O restore do stash que ele dispara
                # não reentra aqui: `_native_mode` já é False quando roda.
                if self._native_mode:
                    self.set_native_mode(False, origin=origin)
                # BT-04(b): `origin` segue até o gate da promoção uinput→uhid —
                # só o gesto manual da usuária recria um vpad degradado; o
                # apply de perfil/autoswitch (a cada troca de janela) nunca.
                # MISC-08 item 3 (2026-07-18): assinatura ANTES do apply — um
                # apply IDÊNTICO (mesmo flavor, mesmo device) não pode custar
                # teardown+respawn de vpad nenhum. Ao vivo, recriar os vpads
                # mid-game invalidou os handles do jogo (a Steam nunca reabriu
                # o hidraw do vpad P1). O `start_gamepad_emulation` já é
                # no-op por (flavor, backend); o guard aqui poupa também o
                # ciclo FORÇADO do co-op (que reescreve player-LEDs via sysfs
                # a cada força — ruído de escrita sem mudança nenhuma).
                device_antes = self._gamepad_device
                ok = start_gamepad_emulation(self, flavor=flavor, origin=origin)
                # SPRINT-GAME-RUMBLE-01: repropaga a máscara recém-aplicada aos
                # vpads de co-op já criados. Trocar o flavor não muda /dev/input,
                # então o watch do coop não dispara sozinho — force=True roda o
                # ciclo cheio e o teardown por flavor-mismatch recria cada
                # secundário com a nova máscara (senão P2+ ficam no flavor antigo,
                # com rumble morto e prompts divergentes do P1).
                if ok and self._gamepad_device is not device_antes:
                    from hefesto_dualsense4unix.daemon.subsystems.coop import (
                        get_coop_manager,
                    )

                    with contextlib.suppress(Exception):
                        get_coop_manager(self).sync(force=True)
                elif ok:
                    # Config efetiva não mudou: nenhum vpad foi recriado e o
                    # co-op segue no ciclo normal (~2s) do poll loop.
                    logger.debug("gamepad_apply_identico_sem_recriacao")
                return ok
            # HARM-16: o zero dos motores vem de dentro do stop (parar o vpad é
            # o que deixa o motor sem dono), não de um passo extra aqui.
            # R-07: só gesto manual apaga a preferência em disco. Um perfil sem
            # seção `mode` desligando o gamepad fazia `flag.unlink()` — e no
            # boot seguinte não nascia vpad nenhum, obrigando a religar tudo na
            # mão. O runtime continua desligando; a PREFERÊNCIA sobrevive.
            stop_gamepad_emulation(self, persist=(origin == "manual"))
            return True

    def set_coop_enabled(
        self,
        enabled: bool,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga o co-op local (FEAT-DSX-COOP-LOCAL-01). Usado pelo IPC.

        Reconcilia na hora: ligar sobe os jogadores secundários (se gamepad on +
        2+ controles). Retorna o estado efetivo de `coop_enabled`.

        COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA: o ramo `False` desta
        função ficou INALCANÇÁVEL pelas superfícies de comando. `coop.set` recusa
        `enabled:false` antes de chegar aqui (é lá que mora a política, com a
        razão legível), o perfil parou de governar o campo e a CLI explica em vez
        de desligar. O ramo continua escrito porque o setter é o mecanismo — e
        porque a suspensão legítima do co-op (Steam Input) NÃO passa por ele:
        ela chama `CoopManager.disable()` direto, sem tocar na flag, e é isso que
        faz o co-op voltar sozinho quando o jogo fecha.

        A persistência virou lápide junto: `save_coop_enabled` não grava mais
        opt-out nenhum (só apaga o que versão antiga deixou).
        """
        self.config.coop_enabled = bool(enabled)
        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            # R-02/C6: idem `set_gamepad_emulation` — o co-op é parte do mesmo
            # eixo (`mode.coop`), então ligá-lo na mão também toma a posse.
            self._mode_from_profile = None
            # FEAT-COOP-DEFAULT-ON-01: só gesto MANUAL persiste a escolha —
            # perfil ligando/desligando co-op não pode virar opt-out da usuária.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_coop_enabled

                save_coop_enabled(self.config.coop_enabled)
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self)
        if self.config.coop_enabled:
            coop.sync(force=True)
        else:
            coop.disable()
        logger.info(
            "coop_enabled_set",
            enabled=self.config.coop_enabled,
            players=coop.player_count(),
        )
        return self.config.coop_enabled

    def contar_controles_fisicos(self) -> int:
        """Quantos controles FÍSICOS o backend enxerga conectados agora (AUTO-01.1).

        Fonte: `describe_controllers` do backend — os mesmos getattrs baratos
        (sem HID I/O, sem varrer /dev/input) que o `_sync_identity_registry` já
        consome no tick lento. `discover_dualsense_evdevs` daria a mesma
        resposta e custaria 10-40 ms de enumeração por chamada: é justamente o
        que o PERF-MULTI-CONTROLLER-01 tirou do event loop.

        Controles EXTERNOS (8BitDo, Pro Controller) NÃO entram na conta, e isso
        é decisão: eles já chegam ao jogo como gamepad nativo (8BIT-02) e não
        dependem de gamepad virtual nenhum — a emulação existe para o DualSense,
        que sem ela alimenta o cursor em vez do jogo.

        Backend sem a API (fake/legado) ou payload estranho devolve 0: na
        dúvida, não há segundo controle e nada liga sozinho.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return 0
        try:
            infos = describe()
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("contagem_de_controles_falhou", err=str(exc))
            return 0
        if not isinstance(infos, list):
            return 0
        return sum(
            1
            for info in infos
            if isinstance(info, dict) and bool(info.get("connected"))
        )

    def aplicar_gamepad_para_multiplos_controles(self) -> str:
        """Liga a emulação de gamepad quando há DOIS ou mais controles (AUTO-01.1).

        A queixa que isto cura: numa instalação nova, quatro DualSense plugados
        alimentam **um cursor só**. `DaemonConfig.gamepad_emulation_enabled`
        nasce `False`, o gate do co-op (`CoopManager.should_be_active`) exige o
        vpad do P1 de pé, e por isso o `coop_enabled=True` (o piso do
        `DaemonConfig`, desde 06/08) é decorativo sozinho: sem emulação não
        existe jogador 2. O caminho para os quatro
        jogadores passava por abrir um terminal ou caçar a aba certa.

        Um segundo controle na mesa é a declaração de intenção mais clara que
        existe — ninguém pluga dois DualSense para os dois moverem o mesmo
        cursor. Então o daemon liga a emulação sozinho, UMA vez, e só nas
        condições em que isso não pisa em decisão de ninguém. Na ordem
        (todas as guardas são baratas: isto roda no tick lento, ~2 s):

        1. **já ligada** — idempotente e é a saída do estado normal (um `and`
           por tique depois que a automação agiu ou que ela mesma ligou);
        2. **preferência persistida** — `load_gamepad_preference` distingue
           "nunca decidiu" de "DESLIGOU de propósito" (AUTO-01.1 no
           `utils.session`). Qualquer decisão gravada — ligada ou desligada —
           tira a automação de cena para sempre; ela existe só para quem nunca
           disse nada. Sem essa distinção, o "Controlar o PC" que ela acabou de
           escolher voltaria a ser "Jogar pelo Hefesto" em ~2 s;
        3. **lock de gesto manual (30 s)** — invariante forte do projeto: gesto
           dela cria trava de 30 s e nada reverte nesse período. Aqui o pedido
           apenas ESPERA (o tick lento repete, e ele entra quando o lock
           vencer), como no `aplicar_modo_jogo_padrao`;
        4. **Modo Nativo** — o controle está SOLTO para o jogo de propósito;
        5. **emulação de mouse VIVA** — ela está usando o controle como mouse
           agora (modo desktop, ou perfil com seção `mouse`). Ligar o vpad aqui
           derrubaria o mouse pela exclusão mútua e, no tique seguinte, o perfil
           o religaria: um flap sem fim entre cursor e vpad. Dois controles na
           mesa não são autorização para arrancar o cursor da mão dela;
        6. **um controle só** — nada a fazer.

        Chama com `origin="profile"` de propósito: NÃO é gesto dela, então não
        carimba `_emu_manual_ts` (não trava perfil nenhum por 30 s) e **não
        persiste** preferência (R-07 — só o gesto manual escreve em disco). A
        automação fica fora do disco por construção: se ela desligar depois, o
        opt-out vale para sempre; se nunca mexer, o daemon reavalia a cada boot.

        Retorno: o vocabulário de `APLICADO`/`ADIADO_LOCK_MANUAL`/`IGNORADO_*`,
        com o log deduplicado por estado (`_gamepad_multi_log`) — o pedido chega
        a cada 2 s e não pode virar enxurrada no journal.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        from hefesto_dualsense4unix.utils.session import load_gamepad_preference

        if self.config.gamepad_emulation_enabled and self._gamepad_device is not None:
            return APLICADO
        preferencia, _flavor = load_gamepad_preference()
        if preferencia is not None:
            return self._log_gamepad_multi(
                IGNORADO_GESTO_DELA,
                "ligada" if preferencia else "desligada_de_proposito",
                0,
            )
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            return self._log_gamepad_multi(
                ADIADO_LOCK_MANUAL, "gesto_manual_recente", 0
            )
        if self._native_mode or self.store.native_mode_active:
            return self._log_gamepad_multi(IGNORADO_GESTO_DELA, "modo_nativo", 0)
        if self._mouse_device is not None:
            return self._log_gamepad_multi(IGNORADO_GESTO_DELA, "mouse_em_uso", 0)
        controles = self.contar_controles_fisicos()
        if controles < 2:
            return self._log_gamepad_multi(
                IGNORADO_UM_CONTROLE_SO, "menos_de_dois_controles", controles
            )
        ok = self.set_gamepad_emulation(True, origin="profile")
        if not ok:
            return self._log_gamepad_multi(FALHOU, "start_recusou", controles)
        self._gamepad_multi_log = APLICADO
        logger.info(
            "gamepad_ligado_por_multiplos_controles",
            controles=controles,
            flavor=self.config.gamepad_flavor,
            coop=self.config.coop_enabled,
        )
        return APLICADO

    def _log_gamepad_multi(self, estado: str, motivo: str, controles: int) -> str:
        """Loga o estado do auto-ligar do gamepad 1x por episódio (AUTO-01.1).

        Mesmo padrão — e mesma razão — do `_log_modo_jogo_padrao`: o pedido roda
        no tick lento (~2 s) e, sem a dedup, uma espera de 30 s pelo lock de
        gesto manual viraria 15 linhas no journal, e "ela desligou de propósito"
        viraria uma linha a cada 2 s para sempre.
        """
        if self._gamepad_multi_log != estado:
            self._gamepad_multi_log = estado
            logger.info(
                "gamepad_multiplos_controles_adiado",
                estado=estado,
                motivo=motivo,
                controles=controles,
            )
        return estado

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga a supressão da emulação de mouse/teclado (modo jogo).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. `value=None` faz toggle; caso
        contrário, define explicitamente. Os devices uinput permanecem vivos —
        só o despacho no poll loop é pulado, e os hotkeys continuam ativos.
        Notifica o usuário e retorna o novo estado (True = emulação suprimida).

        FEAT-POINT-AND-CLICK-01: `origin` distingue o gesto MANUAL da usuária
        (hotkey/IPC/GUI — default, preserva todos os callers existentes) da
        aplicação por PERFIL (`apply_profile_suppression`). Toggle manual
        carimba `_suppress_manual_ts` e zera `_suppress_from_profile` — a
        partir daí perfis não revertem a escolha (ver
        `apply_profile_suppression`).
        """
        from hefesto_dualsense4unix.integrations.desktop_notifications import (
            notify_emulation_suppressed,
        )

        new_state = (not self._emulation_suppressed) if value is None else bool(value)
        self._emulation_suppressed = new_state
        if origin == "manual":
            self._suppress_manual_ts = time.monotonic()
            self._suppress_from_profile = False
        if new_state:
            # FEAT-EMULATION-GAMEMODE-FLUSH-01: ao suprimir, solta tudo que estiver
            # pressionado nos devices virtuais — senão um modificador (ex.: Meta de
            # 'options' no PS+Options) fica preso, já que o poll loop para de
            # despachar e nunca envia o release.
            self._flush_emulation_devices()
        logger.info("emulation_suppressed_changed", suppressed=new_state)
        notify_emulation_suppressed(new_state)
        return new_state

    def apply_profile_suppression(
        self,
        desired: bool,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica `suppress_desktop_emulation` de um perfil recém-ativado.

        FEAT-POINT-AND-CLICK-01. Injetado como `suppression_applier` do
        `ProfileManager` — chamado a CADA ativação de perfil (IPC, autoswitch,
        hotkey de ciclo, restore no boot), sempre com o valor do campo
        (inclusive o default False).

        Semântica escolhida (documentada aqui como fonte canônica):

        1. **Lock manual** — se a usuária alternou o modo-jogo manualmente
           (PS+Options, IPC, GUI) há menos de ``MANUAL_PROFILE_LOCK_SEC``
           (30s, mesma constante do lock de perfil manual), o perfil NÃO mexe
           na supressão em NENHUMA direção (nem liga, nem libera). Log
           informativo e retorno.
        2. **desired=True** — liga a supressão (idempotente: só chama o setter
           se o estado muda, evitando flush/notificação repetidos a cada tick
           do autoswitch) e marca origem "perfil". Se a supressão já estava
           ligada por gesto manual ANTIGO (lock expirado), o perfil a ADOTA:
           ao sair do jogo, o perfil do desktop libera — é a UX esperada do
           autoswitch dono do estado após a janela de respeito.
           PERFIL-REESCRITO-NA-PARTIDA-01 (05/08): **catch-all não liga**, pela
           mesma razão pela qual ele não libera (item 3) — ver o comentário no
           corpo. Sem essa metade, um catch-all com `suppress: true` (o
           `sackboy_nativo` do disco dela) criava um estado do qual nenhum
           outro catch-all conseguia sair.
        3. **desired=False** — LIBERA a supressão apenas se ela veio de perfil
           (`_suppress_from_profile`). Supressão de origem manual (lock já
           expirado, sem perfil que a adotasse) permanece intocada: quem ligou
           na mão, desliga na mão.

        R-03 (auditoria 23/07): `origin` é a origem da ATIVAÇÃO do perfil
        (`ProfileManager.activate`), não a do toggle. Com ``origin="manual"``
        (profile.switch pela GUI/CLI ou PS+D-pad) o item 1 é FURADO e o carimbo
        é consumido: escolher um perfil na mão é gesto MAIS NOVO que o modo-jogo
        que ela alternou segundos antes. Retorno: ver o vocabulário em
        `APLICADO`/`ADIADO_LOCK_MANUAL`/`IGNORADO_*`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            if now - self._suppress_manual_ts < MANUAL_PROFILE_LOCK_SEC:
                logger.info(
                    "profile_suppression_lock_furado_por_gesto_manual",
                    desired=desired,
                    profile=getattr(profile, "name", None),
                )
            # Consome o carimbo: sem isto, a supressão que ESTE perfil vai
            # ligar/liberar travaria o perfil seguinte por mais 30 s.
            self._suppress_manual_ts = float("-inf")
        elif now - self._suppress_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_suppression_skipped_manual_lock",
                desired=desired,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._suppress_manual_ts), 1
                ),
            )
            return ADIADO_LOCK_MANUAL
        if desired:
            # PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08), item 2: a
            # supressão era uma armadilha de MÃO ÚNICA. Só o ramo que LIBERA
            # tinha o gate de catch-all (logo abaixo, R-02); o ramo que LIGA
            # aceitava a ordem de qualquer perfil — inclusive de um catch-all,
            # que por definição chegou porque NENHUMA regra casou.
            #
            # O resultado está no disco dela hoje: `sackboy_nativo` é catch-all
            # e tem `suppress_desktop_emulation: true`. Ele LIGA a supressão de
            # mouse/teclado; e como nenhum outro catch-all tem autoridade para
            # liberar, o estado não sai mais — a emulação de desktop fica morta
            # até um gesto manual dela ou um perfil ESPECÍFICO aparecer.
            #
            # A cura é a simetria, e ela vale nas duas leituras: se ausência de
            # regra não é ordem para LIBERAR, também não é ordem para LIGAR.
            #
            # NOTA DATADA — 09/08/2026 (MODO-JOGO-VONTADE-DELA-01). Este gate
            # deixou de ser só a cura do disco de 05/08: ele virou a CONDIÇÃO de
            # uma entrega da janela. Até hoje a aba Emulação RECUSAVA guardar
            # `suppress: true` num perfil catch-all, e a recusa se justificava
            # por escrito com a ausência deste gate — mas ele já existia desde
            # 05/08, e a janela nunca foi avisada. Decisão dela em 09/08 ("a
            # vontade na GUI prevalece sempre"): o gesto dela passa a ser
            # guardado, porque cinco dos perfis dela são catch-all e para ela
            # isso era "liguei e não ficou salvo". Consequência: a partir de
            # hoje há `suppress: true` em catch-all no disco dela DE PROPÓSITO,
            # e quem impede aquilo de virar mouse e teclado suspensos no
            # desktop, em toda ativação (o restauro do boot inclusive), são
            # estas seis linhas. Arrancá-las devolve o alçapão, agora com mais
            # arquivos para abri-lo — a mordida está em
            # `test_modo_jogo_a_vontade_dela_prevalece.py`.
            if self._perfil_e_catch_all(profile):
                logger.info(
                    "profile_suppression_skipped",
                    motivo="catch_all_sem_opiniao",
                    desired=True,
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_CATCH_ALL
            if not self._emulation_suppressed:
                self.set_emulation_suppressed(True, origin="profile")
            self._suppress_from_profile = True
        elif self._emulation_suppressed and self._suppress_from_profile:
            # R-02: mesma regra do modo — LIBERAR a supressão é uma decisão, e
            # um catch-all não tem autoridade para tomá-la. Sem esta guarda, o
            # `vitoria` (suppress=False, o default) soltava a emulação de
            # desktop dentro do jogo: o mouse/teclado emulado voltava a
            # disputar com o jogo enquanto ela jogava.
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_CATCH_ALL
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_JANELA_DE_JOGO
            self.set_emulation_suppressed(False, origin="profile")
            self._suppress_from_profile = False
        return APLICADO

    def _furar_lock_de_emulacao(self, secao: str, *, agora: float) -> None:
        """R-03: consome o carimbo de gesto manual da EMULAÇÃO (`_emu_manual_ts`).

        Chamado pelos appliers quando a ativação veio com ``origin="manual"`` —
        `profile.switch` (GUI/CLI/applet) ou o ciclo por PS+D-pad. A regra é de
        ORDEM, não de hierarquia: o lock existe para o perfil não sequestrar o
        que ela acabou de fazer na mão; quando o gesto mais novo é justamente
        "ative este perfil", o perfil É a vontade dela e furar o lock é o certo.

        Zerar o carimbo (em vez de só ignorá-lo) é a segunda metade da cura: o
        perfil que acabou de entrar mexe na máscara/co-op via
        `set_*(origin="profile")` — que não re-carimba —, mas um carimbo VELHO
        sobrevivente continuaria bloqueando o PRÓXIMO perfil (o autoswitch ao
        abrir o jogo, por exemplo) por até 30 s. Um log por ativação: quem furar
        primeiro zera, os appliers seguintes já veem `-inf`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        restante = MANUAL_PROFILE_LOCK_SEC - (agora - self._emu_manual_ts)
        if restante > 0:
            logger.info(
                "profile_lock_manual_furado",
                secao=secao,
                restante_sec=round(restante, 1),
            )
        self._emu_manual_ts = float("-inf")

    def apply_profile_mouse(
        self,
        enabled: bool,
        speed: int,
        scroll_speed: int,
        *,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a seção `mouse` de um perfil recém-ativado (BUG-PROFILE-MOUSE-
        KILLS-GAMEPAD-01). Injetado como `mouse_applier` nas rotas de ativação
        (IPC switch, autoswitch, hotkey de ciclo). NÃO é usado no restore do
        boot (lá os flags persistidos governam — ver connection.py).

        Semântica (espelha `apply_profile_suppression`):

        1. **Lock manual** — se a usuária mexeu na emulação (mouse OU gamepad)
           manualmente há menos de `MANUAL_PROFILE_LOCK_SEC`, o perfil NÃO toca
           no estado: não sequestra um gamepad virtual ligado na mão no meio do
           jogo (o bug original: focar um ScummVM matava o gamepad).
        2. **Idempotente** — só chama `set_mouse_emulation` quando o estado
           muda; com o mouse já no estado desejado e ligado, atualiza apenas as
           velocidades (evita destruir/recriar o device a cada tick do
           autoswitch e o tear-down repetido do gamepad).
        3. `origin="profile"` — não re-carimba o lock manual. (O `origin` do
           parâmetro é outro eixo: é a origem da ATIVAÇÃO do perfil — R-03.)

        R-03: ativação com ``origin="manual"`` FURA o item 1 e consome o carimbo
        (`_furar_lock_de_emulacao`). Retorno: vocabulário `APLICADO`/
        `ADIADO_LOCK_MANUAL`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("mouse", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_mouse_skipped_manual_lock",
                enabled=enabled,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                ),
            )
            return ADIADO_LOCK_MANUAL
        # BUG-PROFILE-MOUSE-IDEMPOTENT-STALE-CONFIG-01: o estado REAL de "ligado"
        # é config E device vivo. No boot, run() seta config=True do flag ANTES do
        # start; se start_mouse_emulation falha (uinput indisponível no boot),
        # fica config=True/_mouse_device=None. Confiar só na config faria o ramo
        # idempotente pular a (re)criação e o mouse nunca ligaria apesar do perfil
        # pedir. Checar o device restaura a auto-recuperação por ativação de perfil.
        actual_on = self.config.mouse_emulation_enabled and self._mouse_device is not None
        if enabled == actual_on:
            if enabled:
                self.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            return APLICADO
        self.set_mouse_emulation(
            enabled, speed, scroll_speed, origin="profile"
        )
        return APLICADO

    def _perfil_tem_opiniao(self, profile: Any | None) -> bool:
        """False quando o perfil é catch-all (`MatchAny` ou criteria vazio).

        R-02 (auditoria 23/07). Um catch-all não é "o perfil deste app": é o
        que sobra quando NENHUMA regra casou. Tratar a ausência de opinião dele
        como ordem de reverter era o que desligava o vpad no meio da partida do
        Mullet Mad Jack — jogo sem perfil próprio cai no `vitoria`, que tem
        `mode=null`, e o ramo de reversão executava
        `set_gamepad_emulation(False, origin="profile")` com o jogo em foco.

        `getattr` defensivo: os dublês de teste injetam appliers e perfis
        parciais, e a ausência do atributo não pode virar exceção no meio de
        uma ativação. Na dúvida (sem `match` legível) o perfil é tratado como
        SEM opinião — fail-safe: não derruba o modo da usuária.
        """
        if profile is None:
            return False
        e_catch_all = getattr(profile, "e_catch_all", None)
        if e_catch_all is None:
            return False
        return not e_catch_all

    @staticmethod
    def _perfil_e_catch_all(profile: Any | None) -> bool:
        """True SÓ com evidência POSITIVA de que o perfil é catch-all.

        PERFIL-REESCRITO-NA-PARTIDA-01, item 2. É o irmão de
        `_perfil_tem_opiniao`, e a diferença entre os dois É a resposta na
        DÚVIDA — por isso são dois predicados e não uma negação:

        - ao reverter `mode`/supressão, a dúvida vale "sem opinião"
          (`_perfil_tem_opiniao`): aquelas guardas são antigas, todos os seus
          chamadores já passam `profile=`, e não reverter é o fail-safe;
        - aqui a dúvida NÃO bloqueia. Perfil ausente é o chamador direto
          (dublês da suíte, CLI) e `e_catch_all` ausente é um objeto parcial —
          nos dois casos a leitura honesta é "não sei se chegou por acidente",
          e uma guarda NOVA não pode transformar esse silêncio em recusa para
          quem nunca teve guarda nenhuma.

        Para um `Profile` de verdade os dois predicados coincidem, e em
        produção o perfil SEMPRE chega: `ProfileManager.apply_emulation` passa
        `profile=` a cada ativação. Usado ao LIGAR a supressão (item 2 da leva)
        e ao reverter a política de rumble (item 3).
        """
        return getattr(profile, "e_catch_all", None) is True

    def _janela_de_jogo_em_foco(self) -> bool:
        """True quando a janela em foco AGORA é de um jogo Steam.

        R-02, decisão 3 do plano: leitura CRUA da janela, deliberadamente
        diferente do `display_authority` (que é sticky por 30 s). Aqui a
        pergunta é "reverter para desktop agora seria absurdo?", e para isso o
        sinal sticky congelaria a reversão legítima ao sair do jogo. O sinal
        sticky continua sendo o certo para operação DESTRUTIVA (recriar/parar
        vpad), onde fail-safe é não destruir.
        """
        from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

        wm_class = getattr(self.store, "window_detect_current_class", None)
        return steam_appid_from_wm_class(str(wm_class or "")) is not None

    def _jogo_no_controle_do_desktop(self) -> str | None:
        """Motivo para CALAR a emulação de desktop, ou None se ela pode falar.

        EMULACAO-NO-JOGO-01 (a queixa de 29/07: *"inicio o jogo e ele quando
        aperto r1 muda de app ao invés de funcionar no jogo"*).

        Até aqui a exclusão mútua do poll loop era `if not gamepad_dispatched:` —
        a AUSÊNCIA do vpad lida como PERMISSÃO para o mouse/teclado de desktop
        entrar. Mas a exceção do Steam Input derruba o vpad DE PROPÓSITO
        (`subsystems/gamepad.py`, `steam_input_vpad_suspenso`) quando um jogo da
        allowlist abre — logo a proteção virava a porta de entrada do Alt+Tab
        dentro da partida. Medido no journal dela: 9 de 9 pressionamentos de R1
        em 7 dias caíram dentro de uma janela de suspensão, zero fora, com o
        `_gamepad_device` em None por ~97 minutos num único dia.

        A pergunta certa é "há jogo com autoridade?", e este predicado responde.
        Hoje ele tem UM termo, e a escolha do sinal é o coração da sprint:

        - ``steam_input_vpad_suspenso`` — **usado**. Leitura de flag em memória
          (caminho quente), True pelo episódio INTEIRO, encerrada pelo vigia a
          1 Hz. Cobre exatamente o regime medido.
        - ``display_authority == "game"`` — **recusado**, e não por preguiça: o
          sinal é sticky e tem defeito CONHECIDO E NÃO CORRIGIDO (cai de `game`
          para `daemon` ~30 s depois com o jogo ainda aberto — ver
          `reverter_modo_jogo_padrao`). Os R1 dela saíram 4,5 min depois da
          suspensão: a queda religaria o Alt+Tab no meio da partida, isto é, a
          cura falharia justamente no caso que a motivou. E na saída do jogo a
          stickiness deixaria mouse/teclado mudos por até 30 s — ela sentiria
          como "o controle morreu".
        - ``_janela_de_jogo_em_foco`` (leitura CRUA) — **recusado por ora**. Ele
          libera na hora e não decai, mas o ganho marginal é pequeno (com o vpad
          de pé o `gamepad_dispatched` já exclui o desktop) e o custo é real:
          calaria o `point_and_click` DENTRO de jogo Steam — o único perfil dela
          com `key_bindings` próprio e `mouse.enabled: true`, cujo propósito é
          justamente usar o controle como mouse/teclado num jogo. Não há medição
          de que ela não o use assim; a decisão é dela.

        Risco residual declarado: jogo nativo/Lutris/Heroic e jogo Steam FORA da
        allowlist com o vpad desligado continuam descobertos. Nesses casos o vpad
        de pé é o que exclui o desktop, e é o regime normal na máquina dela.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            steam_input_vpad_suspenso,
        )

        if steam_input_vpad_suspenso(self):
            return CALADA_VPAD_SUSPENSO
        return None

    def _calar_emulacao_de_desktop(
        self, motivo: str, buttons_pressed: frozenset[str]
    ) -> None:
        """Fecha o gate do desktop porque o jogo assumiu (EMULACAO-NO-JOGO-01).

        Três coisas, todas de borda (o poll loop passa aqui a 60 Hz):

        1. **Solta o que estiver preso.** Na primeira borda do episódio chama
           `_flush_emulation_devices` — o MESMO motivo do flush de
           `set_emulation_suppressed`: se o gate fechar com R1 segurado, o
           `KEY_LEFTALT` fica preso porque ninguém mais envia o release. No
           journal dela isso durou 18 s numa noite e 33 s na outra, e o que
           soltou a tecla foi ela clicando no modo jogo.
        2. **Drena o touchpad** (B4): sem despacho de mouse ninguém consome o
           `_accum_dx/dy` e o cursor pularia ao religar.
        3. **Deixa rastro NOMEADO** no journal, deduplicado por episódio. Antes
           saía um `key_binding_emit` neutro que não dizia que era dentro do
           jogo; agora sai `emulacao_de_desktop_calada_no_jogo` uma vez, e
           `teclado_no_jogo_bloqueado` na primeira vez em que havia botão
           pressionado de fato (a 60 Hz, sem a dedup, seriam 60 linhas/s).
        """
        if self._emu_calada_motivo != motivo:
            self._emu_calada_motivo = motivo
            self._emu_calada_botoes_logados = False
            self._flush_emulation_devices()
            logger.info(
                "emulacao_de_desktop_calada_no_jogo",
                motivo=motivo,
                teclado_ativo=self._keyboard_device is not None,
                mouse_ativo=self._mouse_device is not None,
                modo_jogo=self._emulation_suppressed,
            )
        if (
            not self._emu_calada_botoes_logados
            and buttons_pressed
            and self._keyboard_device is not None
            and not self._emulation_suppressed
        ):
            self._emu_calada_botoes_logados = True
            logger.info(
                "teclado_no_jogo_bloqueado",
                motivo=motivo,
                botoes=sorted(buttons_pressed),
            )
        if self._touchpad_reader is not None:
            from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                discard_touchpad_motion,
            )

            discard_touchpad_motion(self)

    def _liberar_emulacao_de_desktop(self, buttons_pressed: frozenset[str]) -> None:
        """Reabre o gate do desktop ao fim do episódio (EMULACAO-NO-JOGO-01).

        Semeia o edge-tracker do teclado com o baseline ATUAL (`prime`, zero
        emissão) antes de voltar a despachar: sem isso, um botão que ela já
        estivesse segurando na borda de saída viraria um press NOVO — um Alt+Tab
        fantasma no instante em que o jogo fecha. É a mesma cura do
        BUG-DAEMON-CONNECT-GHOST-INPUT-01, reusada.
        """
        motivo = self._emu_calada_motivo
        self._emu_calada_motivo = ""
        self._emu_calada_botoes_logados = False
        if self._keyboard_device is not None:
            self._prime_keyboard_emulation(buttons_pressed)
        logger.info("emulacao_de_desktop_liberada", motivo_anterior=motivo)

    def apply_profile_mode(
        self,
        mode: Any | None,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a seção `mode` de um perfil recém-ativado (FEAT-PROFILE-MODE-01).

        Injetado como `mode_applier` nas rotas de ativação (IPC switch,
        autoswitch, hotkey de ciclo). NÃO usado no restore do boot (lá os flags
        persistidos governam — ver connection.py). É o que faz as features
        COEXISTIREM: o perfil do jogo em foco decide o modo, em vez de toggles
        globais brigando.

        Semântica (espelha `apply_profile_suppression`/`apply_profile_mouse`):

        1. **Lock manual** — gesto manual (gamepad/mouse/nativo/co-op) há menos
           de `MANUAL_PROFILE_LOCK_SEC` congela: o perfil não mexe no modo.
        2. **mode=None (perfil sem opinião)** — REVERTE apenas modo que outro
           PERFIL ligou (`_mode_from_profile`); estado de origem manual fica.
        3. **kind="native"** — liga o Modo Nativo (release total) com origem
           perfil; sair do foco (outro perfil ativar) reverte pelo item 2.
        4. **kind="gamepad"** — desliga nativo-de-perfil se preciso, liga o
           gamepad com a máscara pedida e sincroniza o co-op ao campo `coop`.
        5. **kind="desktop"** — declaração explícita: desliga nativo/gamepad
           mesmo os de origem manual JÁ EXPIRADA do lock (o perfil está
           dizendo "este app é desktop puro").

        LEIGO-01: a PREFERÊNCIA de co-op nunca é desligada por perfil que sai do
        gamepad (itens 2 e 5) — sem gamepad não há jogadores para desmontar, e
        zerá-la aqui deixaria o co-op morto pelo resto da sessão.

        Idempotente por checagem de estado antes de cada setter (autoswitch
        re-ativa o mesmo perfil sem flap).

        R-03 (auditoria 23/07) — o item 1 deixou de ser um buraco negro:

        - ``origin="manual"`` (profile.switch / PS+D-pad) **fura** o lock e
          consome o carimbo: o gesto mais novo dela é "ative este perfil".
        - Origem automática (autoswitch/system) **adia**: a ativação segue
          commitada normalmente — nada de flap a 2 Hz — e a seção fica numa
          pendência ÚNICA (`ModoAdiado`) que o `_poll_loop` drena UMA vez,
          quando o lock vencer. Era esta a queixa medida: ela mexia na máscara,
          abria o Sackboy em menos de 30 s, o `mode` do perfil era pulado em
          silêncio e a máscara ficava errada a SESSÃO INTEIRA, com a GUI
          mostrando o perfil ativo como se tudo tivesse valido.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        kind = getattr(mode, "kind", None) if mode is not None else None
        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("mode", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if kind is not None:
                logger.info(
                    "profile_mode_skipped_manual_lock",
                    kind=kind,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            self._agendar_modo_adiado(mode, profile, origin, agora=now)
            return ADIADO_LOCK_MANUAL

        # Passou do lock: ESTA aplicação é mais nova que qualquer pendência
        # guardada antes (inclusive a que estamos drenando agora mesmo).
        self._mode_pendente = None
        # MODO-01/B3: um PERFIL mexendo no modo toma a posse do eixo — o modo
        # jogo padrão (que existe só para quando ninguém opina) deixa de ter o
        # que soltar. Sem esta linha, `reverter_modo_jogo_padrao` desfaria mais
        # tarde uma decisão que passou a ser do perfil.
        if origin != ORIGEM_GAME_SIGNAL:
            self._modo_jogo_padrao = None
            self._modo_jogo_padrao_log = ""

        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )

        if kind is None:
            # R-02 (auditoria 23/07): "sem opinião" NÃO é ordem de reverter
            # quando quem chegou é um catch-all. Jogo sem perfil próprio cai no
            # `vitoria` (MatchAny, mode=null) e o ramo abaixo desligava o vpad
            # COM O JOGO EM FOCO — zero controles no meio da partida. Duas
            # guardas independentes, ambas fail-safe:
            #   1. catch-all nunca reverte (ausência de regra ≠ ordem);
            #   2. com janela de jogo em foco, nenhum perfil reverte modo —
            #      cobre o caso em que uma regra específica casa por engano
            #      (ex.: regex solto) enquanto ela joga.
            # Reversão legítima continua acontecendo: perfil `criteria` de
            # desktop (Navegação no Firefox) e `kind="desktop"` explícito.
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return IGNORADO_CATCH_ALL
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return IGNORADO_JANELA_DE_JOGO
            # Perfil sem opinião: reverte só o que veio de perfil.
            if self._mode_from_profile == "native" and self._native_mode:
                # restore_stash: devolve o gamepad/co-op que a usuária tinha
                # ANTES do jogo (sem re-aplicar last_profile — o perfil novo
                # acabou de aplicar os triggers/LEDs dele).
                self.set_native_mode(
                    False, reapply=False, restore_stash=True, origin="profile"
                )
            # LEIGO-01: sair do gamepad NÃO desliga o co-op — desligar o gamepad
            # já desmonta os jogadores (`CoopManager.should_be_active`), e zerar
            # a preferência aqui a deixava desligada pela sessão inteira, sem
            # caminho de volta agora que o checkbox saiu da tela. Mesma decisão
            # do `mode_transition.plan_mode_transition` (desktop).
            elif self._mode_from_profile == "gamepad" and gamepad_on:
                self.set_gamepad_emulation(False, origin="profile")
            self._mode_from_profile = None
            return APLICADO

        if kind == "native":
            if not self._native_mode:
                self.set_native_mode(True, origin="profile")
            self._mode_from_profile = "native"
            return APLICADO

        if kind == "gamepad":
            if self._native_mode:
                # Sem reapply: o perfil ATUAL acabou de aplicar triggers/LEDs;
                # re-aplicar o last_profile/stash desfaria a ativação corrente.
                self.set_native_mode(False, reapply=False, origin="profile")
            flavor = getattr(mode, "gamepad_flavor", None)
            flavor_atual = getattr(self._gamepad_device, "flavor", None)
            if not gamepad_on or (flavor is not None and flavor != flavor_atual):
                self.set_gamepad_emulation(True, flavor, origin="profile")
            # COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA: o campo
            # `mode.coop` do perfil deixou de GOVERNAR. Ele continua sendo LIDO
            # (e o esquema continua aceitando-o — ver `profiles/schema.py`:
            # tirá-lo do modelo faria todo perfil dela que traz `"coop"` falhar
            # na validação, inclusive dois presets de fábrica), mas nenhum perfil
            # liga nem desliga o co-op: cada controle é um jogador, sempre.
            # Antes daqui saía `set_coop_enabled(want_coop, origin="profile")`,
            # e um perfil antigo com `"coop": false` desligava o co-op dela ao
            # ativar — pelas costas de quem nunca pediu isso.
            _coop_do_perfil_ignorado = bool(getattr(mode, "coop", True))
            if not _coop_do_perfil_ignorado:
                logger.info(
                    "perfil_pediu_coop_off_ignorado",
                    motivo="coop_sempre_ligado",
                )
            self._mode_from_profile = "gamepad"
            return APLICADO

        # kind == "desktop": declaração explícita — limpa qualquer modo.
        # LEIGO-01: o co-op fica de fora da limpeza pelo mesmo motivo do ramo
        # `kind is None` — desligar o gamepad abaixo já desmonta os jogadores, e
        # a preferência tem de sobreviver ao app de desktop para o co-op voltar
        # sozinho no próximo jogo.
        if self._native_mode:
            self.set_native_mode(False, reapply=False, origin="profile")
        if gamepad_on:
            self.set_gamepad_emulation(False, origin="profile")
        self._mode_from_profile = None
        return APLICADO

    def aplicar_modo_jogo_padrao(self, *, wm_class: str = "") -> str:
        """Liga o MODO JOGO PADRÃO — é um jogo e nenhum perfil opina (MODO-01/B3).

        A cura do buraco desta sprint. A regra R-21 (`ProfileManager
        .select_for_window`) recusa dar autoridade a um perfil catch-all sobre
        janela de jogo — e tinha razão própria: um genérico de DESKTOP entrando
        num jogo era o ping-pong `vitoria``Navegação` a cada 18-28 s, com
        lightbar/gatilhos/rumble mudando no meio da partida. O que faltava é que
        ela trocou *"o catch-all entra num jogo"* por *"NINGUÉM entra num jogo"*
        e não pôs nada no lugar: o daemon registrava `game_signal_transition
        de=daemon para=game` e não fazia nada com isso. Esta função ACRESCENTA a
        metade que faltava — o veto continua de pé, e o modo jogo liga sozinho
        **sem trocar de perfil**.

        Chamada pelo `AutoSwitcher` a cada tique enquanto o motivo da seleção for
        `MOTIVO_JOGO_SEM_PERFIL_PROPRIO`; por isso todas as guardas são baratas e
        silenciosas, e o log é deduplicado por estado (`_modo_jogo_padrao_log`).
        Na ordem:

        1. **autoridade de exibição** — só com `display_authority == "game"`. É o
           sinal que já correlaciona janela + marker do wrapper + pid vivo
           (NUMA-01); a `wm_class` sozinha não basta para ligar vpad.
        2. **já aplicado** — idempotente: um pedido por episódio de jogo.
        3. **lock de gesto manual (30 s)** — invariante forte do projeto: gesto
           dela cria trava de 30 s e nada reverte nesse período. Aqui o pedido
           só ESPERA (o autoswitch repete a 2 Hz e o modo entra quando o lock
           vencer); deliberadamente NÃO usa a pendência `ModoAdiado`, que é o
           canal do modo de um PERFIL e morre quando o perfil ativo muda.

        O cadeado de autoswitch (`autoswitch_locked`) não é consultado — nem
        aqui nem no chamador — e isso é a decisão, não um esquecimento: ele
        congela a decisão de PERFIL ("não trocar de perfil sozinho ao abrir um
        jogo"), e ela o mantém ligado justamente para o perfil dela ficar de pé.
        Modo é outro eixo.

        Retorno: o vocabulário de `APLICADO`/`ADIADO_LOCK_MANUAL`/`IGNORADO_*`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            ProfileModeConfig,
            normalizar_gamepad_flavor,
        )

        if self.display_authority != "game":
            return self._log_modo_jogo_padrao(
                IGNORADO_SEM_JOGO, "sem_autoridade_de_jogo", wm_class
            )
        if self._modo_jogo_padrao is not None:
            return APLICADO
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            return self._log_modo_jogo_padrao(
                ADIADO_LOCK_MANUAL, "gesto_manual_recente", wm_class
            )
        # Modo Nativo MANUAL ("Conexão Nativa (Sony)") já É a resposta dela para
        # "como quero jogar": o controle está SOLTO para o jogo, de propósito.
        # Sem esta guarda, o modo jogo padrão o derrubaria assim que o lock de
        # 30 s vencesse — trocando a escolha explícita dela por um default. É a
        # mesma exceção, pelo mesmo predicado, que o `AutoSwitcher._activate` já
        # fazia; nativo ligado por PERFIL não conta (aquele é automatismo, não
        # gesto).
        if (
            self.store.native_mode_active
            and getattr(self.store, "native_mode_origin", None) != "profile"
        ):
            return self._log_modo_jogo_padrao(
                IGNORADO_GESTO_DELA, "modo_nativo_manual", wm_class
            )
        gamepad_antes = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        dono_anterior = self._mode_from_profile
        estado = self.apply_profile_mode(
            ProfileModeConfig(
                kind="gamepad",
                gamepad_flavor=normalizar_gamepad_flavor(self.config.gamepad_flavor),
            ),
            origin=ORIGEM_GAME_SIGNAL,
        )
        if estado != APLICADO:
            return self._log_modo_jogo_padrao(estado, "applier_recusou", wm_class)
        gamepad_agora = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        self._modo_jogo_padrao = ModoJogoPadrao(
            ligou_gamepad=(gamepad_agora and not gamepad_antes),
            dono_anterior=dono_anterior,
            wm_class=wm_class,
        )
        self._modo_jogo_padrao_log = APLICADO
        logger.info(
            "profile_mode_aplicado",
            origin=ORIGEM_GAME_SIGNAL,
            kind="gamepad",
            flavor=self.config.gamepad_flavor,
            wm_class=wm_class,
            ligou_gamepad=self._modo_jogo_padrao.ligou_gamepad,
        )
        return APLICADO

    def reverter_modo_jogo_padrao(self, *, wm_class: str = "") -> str:
        """Solta o modo jogo padrão ao sair do jogo (MODO-01/B3).

        Chamada pelo `AutoSwitcher` quando há EVIDÊNCIA POSITIVA de outra janela
        — não quando o sinal sticky decai. A diferença importa: o `game_signal`
        cai de `game` para `daemon` ~30 s depois com o jogo ainda aberto (o gate
        de foco do B4, registrado e não corrigido nesta sprint), e desligar o
        vpad por causa disso seria o pior desfecho possível.

        Desliga o gamepad SÓ se fomos nós que o ligamos (`ligou_gamepad`), e
        devolve `_mode_from_profile` a quem era dono antes. Na máquina dela o
        vpad já vive ligado por flag em disco: reverter "o modo" ali significa
        soltar a POSSE do eixo, não derrubar o controle dela.

        O lock de gesto manual de 30 s vale aqui também — se ela mexeu no modo
        agora, a última palavra é dela e o daemon apenas abre mão da posse.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        padrao = self._modo_jogo_padrao
        if padrao is None:
            return APLICADO
        self._modo_jogo_padrao = None
        self._modo_jogo_padrao_log = ""
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "modo_jogo_padrao_solto",
                motivo="gesto_manual_recente",
                wm_class=wm_class,
            )
            return ADIADO_LOCK_MANUAL
        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        desligou = False
        if padrao.ligou_gamepad and gamepad_on:
            self.set_gamepad_emulation(False, origin="profile")
            desligou = True
        # Devolve o eixo de modo a quem era dono antes de nós: sem isto, o
        # `"gamepad"` que o applier carimbou daria a um perfil de desktop
        # qualquer autoridade para reverter um modo que nenhum perfil ligou.
        if self._mode_from_profile == "gamepad":
            self._mode_from_profile = padrao.dono_anterior
        logger.info(
            "modo_jogo_padrao_solto",
            motivo="janela_fora_do_jogo",
            wm_class=wm_class,
            de=padrao.wm_class,
            desligou_gamepad=desligou,
        )
        return APLICADO

    def _log_modo_jogo_padrao(self, estado: str, motivo: str, wm_class: str) -> str:
        """Loga o estado do pedido de modo jogo padrão 1x por episódio (B3/B5).

        O pedido chega a 2 Hz (poll do autoswitch); só a MUDANÇA de estado vira
        linha no journal. Mesmo padrão — e mesma razão — do
        `AutoSwitcher._log_cadeado_uma_vez` e do veto R-21 no `ProfileManager`.
        """
        if self._modo_jogo_padrao_log != estado:
            self._modo_jogo_padrao_log = estado
            logger.info(
                "modo_jogo_padrao_adiado",
                estado=estado,
                motivo=motivo,
                wm_class=wm_class,
            )
        return estado

    def _agendar_modo_adiado(
        self, mode: Any | None, profile: Any | None, origin: str, *, agora: float
    ) -> None:
        """Guarda a pendência ÚNICA de `mode` adiada pelo lock (R-03).

        Sobrescreve sempre: dentro de uma mesma janela de 30 s o autoswitch pode
        passar por vários perfis (alt-tab), e aplicar os intermediários depois
        seria pior que não aplicar nada. O nome do perfil vem do OBJETO — neste
        ponto `store.active_profile` ainda é o perfil ANTERIOR, porque
        `ProfileManager.activate` só o grava depois de `apply_emulation`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        anterior = self._mode_pendente
        pendencia = ModoAdiado(
            mode=mode,
            profile=profile,
            profile_name=getattr(profile, "name", None),
            origin=origin,
            carimbo_manual=self._emu_manual_ts,
            nao_antes_de=self._emu_manual_ts + MANUAL_PROFILE_LOCK_SEC,
        )
        self._mode_pendente = pendencia
        logger.info(
            "profile_mode_deferred",
            kind=getattr(mode, "kind", None),
            profile=pendencia.profile_name,
            origin=origin,
            expira_em_sec=round(max(0.0, pendencia.nao_antes_de - agora), 1),
            substituiu=(anterior.profile_name if anterior is not None else None),
        )

    def _modo_seria_destrutivo(self, mode: Any | None) -> bool:
        """True se aplicar `mode` AGORA pararia/recriaria o vpad do P1.

        R-03/R-04: recriar vpad com o jogo rodando invalida os handles que ele
        já abriu (medido ao vivo — a Steam nunca reabre o hidraw do vpad P1), e
        é o pior desfecho possível para o dreno da pendência. Por isso o dreno
        usa o sinal STICKY (`display_authority`) e não a janela crua: para
        operação destrutiva, fail-safe é NÃO destruir; para reverter modo ao
        desktop, o sinal certo é a leitura crua (`_janela_de_jogo_em_foco`,
        R-02, decisão 3 do plano).

        Não é destrutivo: ligar o gamepad do zero, re-aplicar o MESMO flavor
        (`start_gamepad_emulation` já é no-op por (flavor, backend)) e mexer só
        no co-op/gatilhos/LEDs.
        """
        kind = getattr(mode, "kind", None) if mode is not None else None
        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        if kind == "gamepad":
            flavor = getattr(mode, "gamepad_flavor", None)
            flavor_atual = getattr(self._gamepad_device, "flavor", None)
            return bool(gamepad_on and flavor is not None and flavor != flavor_atual)
        # kind None (reversão), "desktop" e "native" derrubam o que estiver de pé.
        return bool(gamepad_on or self._native_mode)

    def _drenar_modo_pendente(self) -> None:
        """Aplica — UMA vez — a seção `mode` que o lock manual adiou (R-03).

        Chamado pelo `_poll_loop` a ~1 Hz (uma comparação de float por tick
        quando não há pendência). Quatro guardas, nesta ordem:

          1. o lock ainda protege o gesto dela → espera;
          2. o carimbo MUDOU → houve gesto manual novo, mais recente que o
             perfil: a pendência morre (a última palavra é dela);
          3. o perfil ativo já não é o que originou a pendência → morre
             (aplicar modo de perfil obsoleto é o risco declarado do retry);
          4. o jogo está com a autoridade de exibição e a aplicação seria
             destrutiva → segura a pendência até a primeira borda em que a
             autoridade sair de "game" (log 1x, senão sairiam ~1 linha/s).
        """
        pendencia = self._mode_pendente
        if pendencia is None:
            return
        agora = time.monotonic()
        if agora < pendencia.nao_antes_de:
            return
        if self._emu_manual_ts != pendencia.carimbo_manual:
            self._mode_pendente = None
            logger.info(
                "profile_mode_pendencia_descartada",
                motivo="gesto_manual_novo",
                profile=pendencia.profile_name,
            )
            return
        ativo = self.store.active_profile
        if pendencia.profile_name is not None and ativo != pendencia.profile_name:
            self._mode_pendente = None
            logger.info(
                "profile_mode_pendencia_descartada",
                motivo="perfil_ativo_mudou",
                profile=pendencia.profile_name,
                ativo=ativo,
            )
            return
        if self.display_authority == "game" and self._modo_seria_destrutivo(
            pendencia.mode
        ):
            if not pendencia.esperando_jogo:
                pendencia.esperando_jogo = True
                logger.info(
                    "profile_mode_pendencia_aguardando_jogo",
                    profile=pendencia.profile_name,
                    kind=getattr(pendencia.mode, "kind", None),
                )
            return
        # Limpa ANTES de aplicar: `apply_profile_mode` só re-agenda se o lock
        # estiver ativo de novo (não está — guarda 1), então nada reentra aqui.
        self._mode_pendente = None
        logger.info(
            "profile_mode_pendencia_aplicada",
            profile=pendencia.profile_name,
            kind=getattr(pendencia.mode, "kind", None),
            origin=pendencia.origin,
        )
        self.apply_profile_mode(
            pendencia.mode, profile=pendencia.profile, origin="pendencia"
        )

    def apply_profile_rumble_policy(
        self,
        policy: str | None,
        custom_mult: float | None = None,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a política de rumble de um perfil recém-ativado
        (FEAT-RUMBLE-POLICY-PROFILE-01). Injetado como `rumble_policy_applier`
        nas rotas de ativação (IPC switch, autoswitch, hotkey de ciclo e
        restore do boot — a política não tem flag persistido próprio, então o
        perfil é a única fonte para restaurá-la).

        Semântica (espelha `apply_profile_mode`):

        1. **Lock manual** — gesto manual há menos de `MANUAL_PROFILE_LOCK_SEC`
           congela: o perfil não mexe na política. O gesto manual DA POLÍTICA
           é o IPC `rumble.policy_set`/`rumble.policy_custom`, que carimba o
           mesmo `_emu_manual_ts` dos toggles de emulação (via
           `mark_rumble_policy_manual`).
        2. **policy=None (perfil sem opinião)** — REVERTE apenas política que
           outro PERFIL aplicou: volta ao par (policy, custom_mult) vigente
           ANTES de o 1º perfil-com-opinião mexer. Política de origem manual
           fica intocada.
           PERFIL-REESCRITO-NA-PARTIDA-01 (05/08), item 3: e a reversão passa
           pelas MESMAS DUAS guardas do `mode` e da supressão —
           `catch_all_sem_opiniao` e `janela_de_jogo_em_foco`. Este applier era
           o único irmão sem nenhuma delas, e o preço apareceu no journal dela:
           um `profile_rumble_policy_reverted` DENTRO da sessão de jogo, com a
           vibração do jogo mudando por causa de um perfil que só passou por
           ali. A doutrina R-02 não tem por que valer para dois eixos e não
           para o terceiro: ausência de regra não é ordem, em nenhum deles.
        3. **policy preenchida** — guarda a política anterior (1ª intervenção
           de perfil), grava no `DaemonConfig` e re-aplica o rumble ATIVO via
           `apply_rumble_policy` para efeito imediato. Se a política vigente
           já era a pedida (gesto manual antigo, lock expirado), o perfil a
           ADOTA — mesma UX do `apply_profile_suppression`.

        Idempotente: re-ativação do mesmo perfil (tick do autoswitch) não
        re-aplica nem loga de novo.

        R-03: ativação com ``origin="manual"`` fura o item 1 e consome o carimbo
        (`_furar_lock_de_emulacao`) — mesma regra de ordem dos outros appliers.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("rumble_policy", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if policy is not None:
                logger.info(
                    "profile_rumble_policy_skipped_manual_lock",
                    policy=policy,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            return ADIADO_LOCK_MANUAL

        if policy is None:
            # Perfil sem opinião: reverte só política que veio de perfil.
            if self._rumble_policy_from_profile:
                # PERFIL-REESCRITO-NA-PARTIDA-01, item 3: as duas guardas que o
                # `mode` (`apply_profile_mode`) e a supressão
                # (`apply_profile_suppression`) já tinham, e que faltavam aqui.
                # Ficam DENTRO do `if` de propósito: sem política de perfil de
                # pé não há reversão nenhuma a barrar, e devolver
                # `ignorado_*` para um no-op encheria o relatório da GUI de
                # recusa onde nada seria feito de todo jeito.
                #
                # A guarda de catch-all usa a forma de evidência POSITIVA
                # (`_perfil_e_catch_all`) e não a negação de
                # `_perfil_tem_opiniao`: para um `Profile` de verdade as duas
                # são idênticas — que é o caso de TODA ativação, porque
                # `apply_emulation` sempre passa `profile=` —, e diferem só
                # quando ninguém disse quem mandou. Aqui a guarda é NOVA, e
                # tomar o silêncio de um chamador direto (CLI, dublê) como
                # recusa mudaria o comportamento de quem nunca teve guarda
                # nenhuma, sem uma medição que peça isso.
                if self._perfil_e_catch_all(profile):
                    logger.info(
                        "profile_rumble_policy_revert_skipped",
                        motivo="catch_all_sem_opiniao",
                        profile=getattr(profile, "name", None),
                    )
                    return IGNORADO_CATCH_ALL
                if self._janela_de_jogo_em_foco():
                    logger.info(
                        "profile_rumble_policy_revert_skipped",
                        motivo="janela_de_jogo_em_foco",
                        profile=getattr(profile, "name", None),
                    )
                    return IGNORADO_JANELA_DE_JOGO
                before = self._rumble_policy_before_profile
                if before is not None:
                    self.config.rumble_policy = before[0]
                    self.config.rumble_policy_custom_mult = before[1]
                    logger.info(
                        "profile_rumble_policy_reverted",
                        policy=before[0],
                        mult=before[1],
                    )
                self._rumble_policy_from_profile = False
                self._rumble_policy_before_profile = None
                self._seed_rumble_mult_observability()
                self._reapply_rumble_policy_to_active()
            return APLICADO

        if policy not in RUMBLE_POLICIES:
            # Defensivo: o schema do perfil já rejeita, mas o applier é
            # público — política desconhecida não pode corromper a config.
            logger.warning("profile_rumble_policy_invalida", policy=policy)
            return FALHOU
        policy_lit = cast("RumblePolicy", policy)

        if not self._rumble_policy_from_profile:
            # 1ª intervenção de perfil: guarda a política vigente para o
            # perfil-sem-opinião reverter depois.
            self._rumble_policy_before_profile = (
                self.config.rumble_policy,
                self.config.rumble_policy_custom_mult,
            )
        desired_mult = (
            max(0.0, min(2.0, float(custom_mult)))
            if custom_mult is not None
            else self.config.rumble_policy_custom_mult
        )
        changed = (
            self.config.rumble_policy != policy_lit
            or self.config.rumble_policy_custom_mult != desired_mult
        )
        self.config.rumble_policy = policy_lit
        self.config.rumble_policy_custom_mult = desired_mult
        self._rumble_policy_from_profile = True
        self._seed_rumble_mult_observability()
        if changed:
            # MISC-08 item 1 (2026-07-18): o campo `mult` carregava o
            # custom_mult vigente (0.7 default) mesmo em política fixa —
            # "mult=0.7 policy=max" no journal parecia atenuação real do
            # rumble. Loga o mult EFETIVO da política aplicada (para "auto"
            # não há valor fixo: é resolvido por bateria a cada tick).
            logger.info(
                "profile_rumble_policy_applied",
                policy=policy_lit,
                mult=(
                    desired_mult
                    if policy_lit == "custom"
                    else RUMBLE_POLICY_MULT.get(policy_lit)
                ),
                custom_mult=desired_mult,
            )
            self._reapply_rumble_policy_to_active()
        return APLICADO

    def apply_profile_rumble_passthrough(self, passthrough: bool) -> None:
        """Aplica `rumble.passthrough` de um perfil recém-ativado (SPRINT-GAME-RUMBLE-01).

        passthrough=True (default de TODO perfil) devolve a vibração ao JOGO:
        solta o rumble FIXADO pela GUI (`rumble_active=None`) e zera os motores
        uma vez. Sem isto, um "Aplicar"/"Parar" na aba Rumble deixava o rumble
        travado e `apply_game_rumble` ignorava o FF do jogo mesmo com a máscara
        Xbox correta — a segunda metade do "testei os motores e o jogo não vibra".

        Só age quando há rumble fixado em valor NÃO-ZERO (`rumble_active` com
        weak/strong > 0 — o caso do "Aplicar"/teste que deixou motor ligado). Em
        passthrough já ativo é no-op.

        M2 (auditoria): NÃO desfaz o silêncio DELIBERADO (`rumble_active == (0,0)`,
        o "Parar" da GUI). Antes, como todo perfil tem `passthrough=True`, um
        alt-tab/PS+dpad/reconexão logo após "Parar" religava o passthrough e o
        jogo voltava a sacudir o controle — contrariando o gesto da usuária. O
        silêncio fixo é intencional e sobrevive à troca de perfil; para devolver
        ao jogo, a usuária usa "Devolver ao jogo" (ou aplica um rumble de teste).
        """
        if not passthrough:
            return
        active = self.config.rumble_active
        if active is None:
            return
        if active == (0, 0):
            # Silêncio deliberado (botão "Parar") — preserva; não religa o jogo.
            return
        self.config.rumble_active = None
        with contextlib.suppress(Exception):
            self.controller.set_rumble(weak=0, strong=0)
        logger.info("profile_rumble_passthrough_released")

    def apply_profile_speaker(
        self,
        volume: int,
        muted: bool = False,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
        rota: int | None = None,
    ) -> str:
        """Aplica a seção `speaker` de um perfil recém-ativado (SOM-02/E4).

        Injetado como `speaker_applier` do `ProfileManager` nas rotas de
        ativação (IPC `profile.switch`, autoswitch, ciclo por hotkey e restore
        de boot) e consumido por `ProfileManager.apply_speaker` /
        `reapply_speaker_on_connect`, que já decidiram, ANTES de chegar aqui,
        que há opinião a aplicar: perfil sem a seção não chama este método (sem
        opinião é silêncio, não ordem — tomar a posse dos bytes de áudio por um
        perfil que não pediu nada é a queixa "a config que eu deixo nunca é
        respeitada", do lado do som).

        POR QUE ISTO FALA DIRETO COM O BACKEND, e não pelo `speaker.set` do IPC
        (a armadilha desta entrega, e a razão de a chamada estar aqui e não lá):
        o handler `_handle_speaker_set` arma a categoria manual `"audio"`
        (`_marcar_audio_manual`, decisão da E3) — que é EXATAMENTE a trava que
        `ProfileManager.apply_speaker` consulta para NÃO escrever. Um applier de
        perfil que passasse por aquele caminho armaria a trava na primeira
        ativação e todas as seguintes seriam descartadas em silêncio: o perfil
        pararia de funcionar depois do primeiro uso. A trava é o registro de um
        gesto DELA; perfil reaplicado não é gesto dela e não pode carimbá-la.

        Pelo mesmo eixo, o lock de 30 s de `_emu_manual_ts` (mouse/modo/política
        de rumble) NÃO é consultado aqui: o gesto manual de áudio tem trava
        própria, por categoria, e ela já foi consultada rio acima. Empilhar o
        lock de emulação faria mexer no mouse silenciar o volume do perfil por
        meio minuto, sem que ninguém tivesse tocado no som.

        `volume` é OBRIGATÓRIO e vai sempre junto do `muted` (armadilha 1,
        medida: `set_speaker_volume` sem volume e sem preferência guardada toma
        a posse e manda ZERO, publicando `{'volume': 0, 'muted': True}`). O
        esquema do perfil já recusa a seção sem volume e o manager faz
        `int(secao.volume)`; a guarda abaixo é a terceira cerca, para um dublê
        ou um chamador novo não conseguirem produzir a chamada vazia.

        Vocabulário de retorno (R-03): `APLICADO`, `IGNORADO_SEM_CONTROLE`
        (nenhum handle para o `uniq` — nada foi escrito e ninguém mentiu
        "aplicado") e `FALHOU`.

        `rota` é o CANAL de saída (SOM-ROTA-01) e vem do `speaker.rota` do
        perfil. `None` — o default, e o que todo perfil de antes desta linha
        carrega — quer dizer **não tocar no `common[7]`**: aquele byte guarda a
        rota de saída (bits 4-5) E o caminho do microfone (o resto), e
        escrevê-lo inteiro apagaria o caminho do mic em silêncio. Quem preserva
        os outros bits é o `_byte_da_rota` do backend, que lê o valor vigente
        do handle antes de trocar só os dois bits da rota.
        """
        if volume is None:
            # Nunca um `set_speaker_volume` sem volume — ver a docstring. A
            # anotação diz `int`; a guarda existe para o chamador que não a lê.
            logger.warning("profile_speaker_sem_volume_recusado", origin=origin)
            return FALHOU
        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            logger.debug("profile_speaker_backend_sem_suporte", origin=origin)
            return IGNORADO_SEM_CONTROLE
        alvo = max(0, min(255, int(volume)))
        try:
            ok = bool(setter(alvo, muted=bool(muted), uniq=uniq, rota=rota))
        except Exception as exc:
            logger.warning(
                "profile_speaker_apply_failed",
                volume=alvo,
                muted=bool(muted),
                uniq=uniq,
                rota=rota,
                err=str(exc),
            )
            return FALHOU
        if not ok:
            # Sem handle para este `uniq` (controle ausente/desconectado). Não é
            # falha: é a ausência do controle, dita com esse nome.
            logger.debug(
                "profile_speaker_sem_controle", uniq=uniq, origin=origin
            )
            return IGNORADO_SEM_CONTROLE
        logger.info(
            "profile_speaker_applied",
            volume=alvo,
            muted=bool(muted),
            uniq=uniq,
            rota=rota,
            origin=origin,
        )
        return APLICADO

    def mark_rumble_policy_manual(self) -> None:
        """Registra gesto MANUAL na política de rumble
        (FEAT-RUMBLE-POLICY-PROFILE-01).

        Chamado pelos handlers IPC `rumble.policy_set`/`rumble.policy_custom`:
        carimba `_emu_manual_ts` (lock de 30s — perfis não pisam a escolha
        recente da usuária, paridade com os toggles de emulação) e limpa a
        origem "perfil" (a política vigente passa a ser manual; perfil sem
        opinião não a reverte mais — quem mexeu na mão, desfaz na mão).
        """
        self._emu_manual_ts = time.monotonic()
        self._rumble_policy_from_profile = False
        self._rumble_policy_before_profile = None

    def _seed_rumble_mult_observability(self) -> None:
        """Sincroniza `_last_auto_mult` com o mult efetivo da política vigente.

        MISC-08 item 1 (2026-07-18): `daemon._last_auto_mult` é a fonte do
        `rumble_mult_applied` do state_full, mas só era atualizado quando um
        caminho de rumble de fato COMPUTAVA (`reassert_rumble` exige rumble
        fixado; `_game_rumble_mult` exige FF do jogo). Em passthrough ocioso,
        aplicar um perfil com política fixa deixava o campo preso no default
        0.7 — ao vivo, `policy=max` + `rumble_mult_applied=0.7` no state_full
        parecia atenuação real do rumble do jogo. Política "auto" fica de
        fora de propósito: o valor dela é resolvido por bateria (com
        debounce) no próximo cômputo.
        """
        policy = self.config.rumble_policy
        if policy == "custom":
            self._last_auto_mult = float(self.config.rumble_policy_custom_mult)
        elif policy in RUMBLE_POLICY_MULT:
            self._last_auto_mult = RUMBLE_POLICY_MULT[policy]

    def _reapply_rumble_policy_to_active(self) -> None:
        """Re-aplica a política vigente ao rumble ATIVO (efeito imediato).

        Sem rumble fixado (`rumble_active=None`, passthrough) é no-op — o
        multiplicador da política é aplicado na entrada de cada write
        (`rumble.set`/reassert do poll loop). Best-effort: falha de hardware
        não aborta a ativação do perfil.
        """
        active = self.config.rumble_active
        if active is None:
            return
        from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
            apply_rumble_policy,
        )

        with contextlib.suppress(Exception):
            eff_weak, eff_strong = apply_rumble_policy(self, active[0], active[1])
            self.controller.set_rumble(weak=eff_weak, strong=eff_strong)

    def _flush_emulation_devices(self) -> None:
        """Solta todas as teclas/botões dos devices virtuais (mouse+teclado).

        Idempotente e best-effort. Usado ao ligar a supressão (modo jogo) para
        não deixar modificador/click preso, e disponível p/ limpeza defensiva.
        """
        kbd = self._keyboard_device
        if kbd is not None:
            with contextlib.suppress(Exception):
                kbd.dispatch(frozenset())
        mouse = self._mouse_device
        if mouse is not None:
            with contextlib.suppress(Exception):
                mouse.dispatch(
                    lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset()
                )

    # ------------------------------------------------------------------
    # Métodos privados preservados para backcompat de testes
    # ------------------------------------------------------------------

    def _start_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat para testes que chamam daemon._start_hotkey_manager()."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_hotkey_manager

        start_hotkey_manager(self)

    def _stop_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import stop_hotkey_manager

        stop_hotkey_manager(self)

    def _start_mouse_emulation(self) -> bool:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import start_mouse_emulation

        return start_mouse_emulation(self)

    def _stop_mouse_emulation(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(self)

    def _start_gamepad_emulation(self) -> bool:
        """Thin wrapper — gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01).

        R-07: `origin="profile"` de propósito. Este é o restore do BOOT — ele
        LÊ a flag persistida e a reaplica; não é gesto novo da usuária. Com o
        default "manual" ele regravaria em disco o que acabou de ler (inócuo
        hoje, mas é a mesma confusão de origem que fazia o perfil apagar a
        escolha dela).
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import start_gamepad_emulation

        return start_gamepad_emulation(
            self, flavor=self.config.gamepad_flavor, origin="profile"
        )

    def _stop_gamepad_emulation(self) -> None:
        """Thin wrapper — para o gamepad virtual e libera o grab."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import stop_gamepad_emulation

        stop_gamepad_emulation(self)

    def _dispatch_gamepad_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import dispatch_gamepad

        dispatch_gamepad(self, state, buttons_pressed)

    def _start_keyboard_emulation(self) -> bool:
        """Thin wrapper — wire-up A-07 para FEAT-KEYBOARD-EMULATOR-01."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import start_keyboard_emulation

        return start_keyboard_emulation(self)

    def _stop_keyboard_emulation(self) -> None:
        """Thin wrapper — backcompat e cleanup."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import stop_keyboard_emulation

        stop_keyboard_emulation(self)

    def _dispatch_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import dispatch_keyboard

        dispatch_keyboard(self, buttons_pressed)

    def _prime_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — semeia o edge-tracker do teclado sem emitir.

        Chamado pelo poll loop durante o settling pós-conexão
        (BUG-DAEMON-CONNECT-GHOST-INPUT-01).
        """
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import prime_keyboard

        prime_keyboard(self, buttons_pressed)

    def _reassert_rumble(self, now: float) -> None:
        """Thin wrapper — backcompat e chamado pelo poll loop."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import reassert_rumble

        reassert_rumble(self, now)

    async def _start_ipc(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.ipc import start_ipc

        await start_ipc(self)

    async def _start_udp(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.udp import start_udp

        await start_udp(self)

    async def _start_autoswitch(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import start_autoswitch

        await start_autoswitch(self)

    def _start_mic_hotkey(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_mic_hotkey

        start_mic_hotkey(self)

    async def _start_plugins(self) -> None:
        """Inicializa o PluginsSubsystem se plugins_enabled ou env var ativo."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem

        ps = PluginsSubsystem()
        if not ps.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ps.start(ctx)
        self._plugins_subsystem = ps

    async def _stop_plugins(self) -> None:
        """Para o PluginsSubsystem de forma limpa."""
        if self._plugins_subsystem is not None:
            await self._plugins_subsystem.stop()
            self._plugins_subsystem = None

    async def _start_metrics(self) -> None:
        """Inicializa o MetricsSubsystem se metrics_enabled (FEAT-METRICS-01).

        Espelha `_start_plugins`: o `MetricsSubsystem.start` espera um
        `DaemonContext` (não é um starter sem-arg), então montamos o contexto
        aqui. O gate `is_enabled(config)` é respeitado — o servidor HTTP só
        sobe quando `metrics_enabled=True`.
        """
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem

        ms = MetricsSubsystem()
        if not ms.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ms.start(ctx)
        self._metrics_subsystem = ms

    async def _start_bt_mic(self) -> None:
        """Sobe o BtMicSubsystem se o opt-in estiver ligado (BT-MIC-REGISTRY-01).

        A ponte de microfone por Bluetooth existia inteira
        (`integrations/dualsense_bt_audio.py`, validada ao vivo gravando WAV) e
        o subsystem que a embrulha existia — mas NINGUÉM o iniciava: o
        `SUBSYSTEM_REGISTRY` é declarativo e é este `run()` que sobe as coisas.
        O gate documentado (`HEFESTO_DUALSENSE4UNIX_BT_MIC=1`) portanto não
        ligava nada no daemon, e a ponte só existia pelo CLI `mic bt`.

        Espelha `_start_metrics`/`_start_plugins`: monta o `DaemonContext`,
        respeita `is_enabled(config)` e devolve INERTE (sem thread, sem
        `pactl`, sem importar libopus) quando o opt-in está desligado — que é
        o default. Um erro aqui vira `_failed_subsystems["bt_mic"]` pelo
        `_safe_start` do chamador; o boot segue.
        """
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        bm = BtMicSubsystem()
        if not bm.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await bm.start(ctx)
        self._bt_mic_subsystem = bm

    async def _stop_bt_mic(self) -> None:
        """Para o BtMicSubsystem (DESLIGA o mic de cada controle). Idempotente."""
        if self._bt_mic_subsystem is not None:
            subsystem = self._bt_mic_subsystem
            self._bt_mic_subsystem = None
            await subsystem.stop()

    async def _stop_metrics(self) -> None:
        """Para o MetricsSubsystem de forma limpa. Idempotente."""
        if self._metrics_subsystem is not None:
            await self._metrics_subsystem.stop()
            self._metrics_subsystem = None

    async def _safe_start(self, name: str, starter: Callable[[], Any]) -> None:
        """Inicia um subsystem isolando falhas (FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01).

        Se `starter` levantar (dep nativa ausente, permissão negada, porta em
        uso...), registra o erro em `_failed_subsystems` e segue — um subsystem
        quebrado não derruba o daemon. Aceita starters síncronos e assíncronos.
        """
        try:
            result = starter()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self._failed_subsystems[name] = str(exc)
            logger.error(
                "subsystem_start_failed", subsystem=name, err=str(exc), exc_info=True
            )

    def _audit_config_on_boot(self) -> None:
        """Valida os perfis no boot e avisa o usuário se houver corrompidos
        (FEAT-CONFIG-AUDIT-BOOT-01). Best-effort: nunca derruba o boot.
        """
        try:
            from hefesto_dualsense4unix.profiles.loader import audit_profiles

            invalid = audit_profiles()
            if not invalid:
                return
            logger.warning(
                "config_audit_invalid_profiles",
                count=len(invalid),
                profiles=[name for name, _err in invalid],
            )
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_config_errors,
                )

                notify_config_errors(invalid)
        except Exception as exc:
            logger.debug("config_audit_failed", err=str(exc))

    def _check_system_on_boot(self) -> None:
        """Detecta problemas de infra no boot (udev/WirePlumber) e AVISA o comando
        de reparo (FEAT-SYSTEM-AUTOREPAIR-BOOT-01). Nunca roda sudo/reparo sozinho.
        Best-effort: nunca derruba o boot.

        BUG-SYSTEM-CHECK-BOOT-SPAM-01: a notificação visual é silenciada por
        default (`HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY=0`). O usuário
        reclamava de receber aviso "tem algo não instalado" toda vez que ligava
        o PC (WirePlumber pinava o DualSense como mic padrão — coisa que ele
        já sabia, mas não queria ser lembrado a cada login). O log em `warning`
        permanece — quem quiser pode rodar `journalctl --user -u
        hefesto-dualsense4unix.service | grep system_check_warning` para ver.
        Para reativar a notify, setar a env var para "1".
        """
        try:
            from hefesto_dualsense4unix.core.system_check import system_warnings

            infra_warnings = system_warnings()
            if not infra_warnings:
                return
            for detail in infra_warnings:
                logger.warning("system_check_warning", detail=detail)
            notify_enabled = os.environ.get(
                "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY", ""
            ).strip() in ("1", "true", "yes")
            if not notify_enabled:
                return
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_system_warnings,
                )

                notify_system_warnings(infra_warnings)
        except Exception as exc:
            logger.debug("system_check_failed", err=str(exc))

    def _evdev_buttons_once(self) -> frozenset[str]:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once

        return evdev_buttons_once(self)

    def _dispatch_mouse_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import dispatch_mouse

        dispatch_mouse(self, state, buttons_pressed)

    # ------------------------------------------------------------------
    # Identidade dos controles (COR-01/COR-03)
    # ------------------------------------------------------------------

    def _wire_identity_registry(self) -> None:
        """Cria o registro de identidade e injeta o provider de cor no backend.

        COR-01/COR-03: SÓ quando o backend suporta a injeção
        (`set_auto_output_provider` — o PyDualSenseController real). Com o
        FakeController fica tudo desligado: `identity_registry` permanece
        None, nenhum `controllers.json` é lido/escrito e o reconcile do poll
        loop é no-op — testes/smoke herméticos por construção. Best-effort:
        falha aqui loga warning e o daemon segue (LEDs caem no broadcast
        histórico).
        """
        if not hasattr(self.controller, "set_auto_output_provider"):
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
                make_auto_output_provider,
            )

            registry = get_identity_registry()
            registry.load()
            self.identity_registry = registry
            self.controller.set_auto_output_provider(
                make_auto_output_provider(registry)
            )
            logger.info("identity_registry_wired")
        except Exception as exc:
            logger.warning("identity_registry_wire_failed", err=str(exc))

    def _sync_identity_registry(self) -> None:
        """Reconcilia o registro com os controles conectados (tick lento ~2s).

        COR-01 (D2): marca desconectados (slot vira RESERVA do MAC) — por isso
        roda TAMBÉM offline (o gate de `is_connected` do poll loop não pode
        engolir a transição para zero controles). Fonte do conjunto:
        `describe_controllers` do backend (getattrs baratos, sem HID I/O) —
        nunca no caminho quente por evento. No-op sem registro (backend fake)
        ou sem a API.

        R-24 (auditoria 25/07): a ORDEM importa agora. O `sync_connected`
        passou a ATRIBUIR slot a quem chegou sem número (era só o provider de
        cor que atribuía, e enquanto ele não rodava o piso lido pelos
        EXTERNOS valia 0 — o Pro Nintendo abocanhava o slot 1 e os DualSense
        nasciam 2 e 3). Isto aqui montava um `set`, que numeraria por hash;
        agora entrega a ordem de `describe_controllers` (primário primeiro),
        que é a mesma ordem que a GUI e a CLI listam.
        """
        registry = self.identity_registry
        if registry is None:
            return
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
            uniqs = [
                info["uniq"]
                for info in infos
                if isinstance(info, dict)
                and info.get("connected")
                and isinstance(info.get("uniq"), str)
            ]
            registry.sync_connected(uniqs)
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("identity_sync_falhou", err=str(exc))

    def _amostrar_bateria(self, agora: float) -> None:
        """Sonda a carga de cada controle e deixa no journal o que valer linha.

        PROTOCOLO-QUEDA-01 (07/08/2026), entrega 1: até aqui o daemon LIA a
        bateria a cada tique e não escrevia uma linha — a hipótese mais forte
        para as nove quedas de link (a carga acabando) era indecidível por falta
        de instrumento. Quem decide a cadência e a máscara do endereço é o
        `battery_journal`; aqui só entregamos a leitura barata do backend
        (`describe_controllers`, os mesmos getattrs do tique lento) e o relógio
        do tique.

        Roda ANTES do gate de conexão do poll loop, pelo mesmo motivo do
        `_sync_identity_registry`: é a transição para ZERO controles que mais
        interessa, e depois do gate ela nunca seria vista.

        Nunca derruba o poll loop: leitura de sysfs falha por corrida (o nó some
        entre o `exists` e o `read`) e isso é rotina, não defeito.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
            if not isinstance(infos, list):
                return
            diario_da_bateria(self).observar(infos, agora)
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("bateria_amostra_falhou", err=str(exc))

    # ------------------------------------------------------------------
    # Identidade + LED dos controles EXTERNOS (EXT-04)
    # ------------------------------------------------------------------

    def _wire_external_registry(self) -> None:
        """Cria o registro de externos + o aplicador de LED do tick lento.

        EXT-04: gate = `identity_registry` já fiado (backend real). Com o
        FakeController fica tudo None — nenhuma enumeração de /dev/input,
        nenhuma escrita de LED, nenhum controllers.json em teste/smoke.
        Best-effort: falha loga warning e o daemon segue (externos ficam sem
        número, como um kernel sem a regra udev 79).
        """
        if self.identity_registry is None:
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
                ExternalIdentityRegistry,
                ExternalLedSync,
            )

            registry = ExternalIdentityRegistry()
            registry.load()
            self.external_registry = registry
            self._external_led_sync = ExternalLedSync(self, registry)
            # EXT-04: numeração global ÚNICA — o registro dos DualSense passa a
            # pular os slots já reservados pelos externos ao numerar um
            # DualSense novo (evita duas frentes acenderem o mesmo "Controle
            # N" no co-op misto). Mão dupla do `reserve` que os externos já
            # leem do lado DualSense; ninguém renumera quem já tem slot.
            self.identity_registry.set_external_reserve_provider(
                lambda: set(registry.snapshot().values())
            )
            logger.info("external_registry_wired")
        except Exception as exc:
            logger.warning("external_registry_wire_failed", err=str(exc))

    def _schedule_external_tick(self) -> None:
        """Agenda o tick de LED dos externos como TASK auxiliar (HANG-01).

        Chamado pelo poll loop a cada ~2s; NUNCA aguarda o tick — antes disto
        o `await self._sync_external_leds()` inline suspendia o POLL LOOP
        INTEIRO para sempre se `sync.tick()` travasse no executor (mecanismo
        do incidente 19/07 16:08: zero read_state, zero logs, zero watchdog,
        por 10 minutos). Guard de reentrância: se a task anterior ainda não
        terminou, pula este ciclo (só conta — nunca empilha 2 ticks
        concorrentes brigando pelo mesmo `ExternalLedSync`).

        Degradado (2+ timeouts consecutivos em `_sync_external_leds`): fica
        mudo até o `InputDirWatch` observar uma mudança REAL em /dev/input —
        aí destrava e volta a agendar (o replug pode ter corrigido o que
        travou o worker, ou pelo menos justifica tentar de novo).
        """
        if self._external_led_sync is None:
            return
        if self._external_tick_degraded:
            watch = self._external_tick_watch
            if watch is None:
                from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

                watch = InputDirWatch()
                self._external_tick_watch = watch
                watch.poll()  # baseline — não destrava no MESMO tick que degradou
                return
            if not watch.poll():
                return
            logger.info("external_tick_recuperado", motivo="input_dir_change")
            self._external_tick_degraded = False
            self._external_tick_timeouts = 0
        task = self._external_tick_task
        if task is not None and not task.done():
            self._external_tick_skipped += 1
            return
        self._external_tick_task = asyncio.create_task(
            self._sync_external_leds(), name="external_led_tick"
        )

    async def _sync_external_leds(self) -> None:
        """Corpo da TASK do tick de LED dos externos (HANG-01).

        EXT-04 item 3: o `tick()` enumera /dev/input (10-40 ms) e escreve
        sysfs, então roda no executor DEDICADO (`_run_external_blocking`,
        pool `hefesto-ext`) — NUNCA no `self._executor` ("hefesto-hid") de
        que `read_state`/`_gather_game_signal_inputs`/o watchdog evdev
        dependem — sob `asyncio.wait_for`: a THREAD presa não é recuperável
        (é um wedge de baixo nível do CPython sob churn extremo de threads,
        não uma trava lógica nossa — trade-off aceito do projeto, mesmo
        espírito do `INIT_TIMEOUT_SEC` de `backend_pydualsense.py`: vaza o
        worker do pool `hefesto-ext`, isolado do pool que o poll loop usa
        pra ler o controle). Correção pós-auditoria: a versão anterior
        reusava `self._executor` — 2 timeouts consecutivos (possíveis pelo
        guard de reentrância, que só olha a task asyncio "done", não o
        worker) esgotavam os 2 workers do MESMO pool do `read_state`,
        reproduzindo o hang original de forma adiada. 1º timeout: WARNING;
        2º+ CONSECUTIVO: ERROR + degrada (`_schedule_external_tick` para de
        agendar até o próximo hotplug). Nunca propaga exceção para o
        chamador (`asyncio.create_task` — uma exceção aqui viraria
        "exception never retrieved" silencioso, então capturamos tudo).
        """
        sync = self._external_led_sync
        if sync is None:
            return
        try:
            await asyncio.wait_for(
                self._run_external_blocking(sync.tick),
                timeout=EXTERNAL_TICK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            self._external_tick_timeouts += 1
            log = (
                logger.warning
                if self._external_tick_timeouts == 1
                else logger.error
            )
            log(
                "external_tick_pendurado",
                timeout_sec=EXTERNAL_TICK_TIMEOUT_SEC,
                consecutivos=self._external_tick_timeouts,
            )
            if self._external_tick_timeouts >= EXTERNAL_TICK_MAX_TIMEOUTS:
                self._external_tick_degraded = True
                logger.info(
                    "external_tick_degradado",
                    consecutivos=self._external_tick_timeouts,
                    instrucao=(
                        "inventário de externos congelado até o próximo "
                        "hotplug em /dev/input; ver doctor/reiniciar o serviço"
                    ),
                )
        except Exception as exc:  # nunca derrubar o poll loop
            logger.debug("external_led_sync_falhou", err=str(exc))
        else:
            self._external_tick_timeouts = 0

    # ------------------------------------------------------------------
    # Sinal "jogo real ativo" (NUMA-01)
    # ------------------------------------------------------------------

    @property
    def display_authority(self) -> str:
        """Autoridade de exibição CORRENTE ('game'|'daemon'|'unknown').

        NUMA-01 — contrato PÚBLICO explícito (síntese da Onda N: "sem
        `getattr` de privado no consumidor"). 'unknown' quando o
        `GameSignal` ainda não foi fiado (antes de `run()`, ou backend sem
        `set_game_authority_provider` — mesmo default fail-safe do sinal).
        """
        signal = self._game_signal
        return signal.authority if signal is not None else "unknown"

    def _wire_game_signal(self) -> None:
        """Cria o `GameSignal` (NUMA-01) e injeta a autoridade no backend real.

        Diferente de `_wire_identity_registry`/`_wire_external_registry`: o
        objeto `GameSignal` SEMPRE nasce (mesmo com FakeController) — é ele
        quem sustenta `display_authority`. Só a injeção no controller
        (`set_game_authority_provider`) é gateada por `hasattr` (padrão
        `set_auto_output_provider`, acima): sem o método, o backend fica
        byte-idêntico ao HEAD — fail-safe da síntese ("remover 1 linha
        desliga a onda inteira" — aqui seria remover a chamada abaixo).
        """
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal

        self._game_signal = GameSignal()
        if not hasattr(self.controller, "set_game_authority_provider"):
            return
        try:
            self.controller.set_game_authority_provider(
                lambda: self._game_signal.authority
            )
            logger.info("game_signal_wired")
        except Exception as exc:
            logger.warning("game_signal_wire_failed", err=str(exc))

    def _wire_feature_opener(self) -> None:
        """S-5: injeta o opener broker-aware no backend p/ a calibração 0x05.

        Gate por `hasattr` (FakeController não tem o setter → no-op, testes
        herméticos). `make_broker_opener` tenta o broker (fd root via
        SCM_RIGHTS, funciona com o nó ESCONDIDO) e cai no `os.open` por
        caminho quando o broker está ausente. Best-effort: falha aqui loga e
        o backend segue com `os.open` (comportamento histórico).
        """
        if not hasattr(self.controller, "set_feature_opener"):
            return
        try:
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                make_broker_opener,
            )

            self.controller.set_feature_opener(make_broker_opener(self))
            logger.info("feature_opener_wired")
        except Exception as exc:
            logger.warning("feature_opener_wire_failed", err=str(exc))

    def _any_game_session_open(self) -> bool:
        """Agregado `game_open` de TODOS os vpads (P1 + co-op, NUMA-01).

        Usado SÓ para modular a histerese da queda em `GameSignal.evaluate`
        — veto permanente honrado: sessão uhid JAMAIS alimenta `classify`
        (é o mecanismo do incidente 14:42: o cliente Steam também abre
        sessão). Espelha a varredura de vpads de `launch_env._snapshot`.
        """
        vpads: list[Any] = []
        primary = self._gamepad_device
        if primary is not None:
            vpads.append(primary)
        players = getattr(self._coop_manager, "_players", None)
        if isinstance(players, dict):
            for player in players.values():
                vpad = getattr(player, "vpad", None)
                if vpad is not None:
                    vpads.append(vpad)
        return any(bool(getattr(vpad, "game_open", False)) for vpad in vpads)

    def _manager_de_selecao(self) -> Any:
        """`ProfileManager` de LEITURA do daemon, cacheado (MODO-01/B5).

        Era uma instância NOVA a cada tique do sinal de jogo (~2 s). Como a
        deduplicação do veto R-21 é um campo de INSTÂNCIA
        (`_ultimo_veto_catch_all`), ela nascia zerada toda vez e o
        `profile_select_catch_all_sem_autoridade_em_jogo` saía a 0,5 Hz — 12
        linhas idênticas, exatamente 2,00 s de intervalo, medidas no journal com
        o jogo aberto. A dedup existia e nunca valia.

        Só leitura: nenhum applier é injetado de propósito. Este manager escolhe
        perfil para RESPONDER uma pergunta (`_profile_rule_matches_game`), nunca
        para ativar — quem ativa é o manager do subsystem de autoswitch, com os
        appliers todos fiados.

        EMPATE-01 (27/07): o `store` do daemon vai junto. Ele nascia com um
        `StateStore` próprio e VAZIO, então este seletor não sabia qual perfil
        está ativo — e o desempate por incumbente
        (`ProfileManager._melhor_candidato`) ficaria cego justo no caminho do
        SINAL DE JOGO, que é onde a resposta importa. Passar o store é leitura:
        nada aqui chama `activate()`, que é quem escreve nele.
        """
        if self._profile_selector is None:
            from hefesto_dualsense4unix.profiles.manager import ProfileManager

            self._profile_selector = ProfileManager(
                controller=self.controller, store=self.store
            )
        return self._profile_selector

    def _profile_rule_matches_game(
        self,
        wm_class: str | None,
        wm_name: str | None = None,
        exe_basename: str | None = None,
    ) -> bool:
        """NUMA-01 evidência #2: a janela corrente casa regra de jogo do
        autoswitch (`mode.kind == "gamepad"`, match ESPECÍFICO — não o
        `MatchAny` catch-all do perfil fallback). Cobre GOG/Heroic fora da
        Steam pelo MESMO mecanismo de seleção do autoswitch
        (`ProfileManager.select_for_window`). Best-effort: qualquer falha
        ao carregar perfis do disco devolve False — o chamador
        (`_gather_game_signal_inputs`) já roda protegido por try/except no
        tick.

        SINAL-DE-JOGO-01 (31/07): a pergunta passou a levar a janela INTEIRA.
        Ela chegava aqui com `wm_class` e mais nada, e o `MatchCriteria` é um E
        entre os campos preenchidos com alvo ausente reprovando por decisão
        escrita (`profiles/schema.py`, `_casa_sem_caixa`) — então qualquer perfil
        com `window_title_regex` ou `process_name` devolvia False SEMPRE, sem
        erro nenhum. Medido nos 15 perfis do disco dela: dos seis perfis de jogo,
        um só casava aqui, e por uma `wm_class` `steam_app_*` que a evidência
        nº 1 já pegava sozinha — a evidência nº 2 era letra morta.

        Tradeoff registrado (o mesmo que a AUTOMATISMO-MORTO-01 discute no
        cadeado, por outra porta): com o título valendo, um regex solto de
        título passa a poder declarar "é jogo" a partir de uma janela que não é
        jogo — medido no disco dela, uma aba de navegador chamada "Portal 2"
        casa o `coop_local` (prioridade 75, `mode: gamepad`, só título) e vence
        o `Navegação` (prioridade 50). Aqui o consumidor é o sinal de EXIBIÇÃO,
        não a troca de perfil; quem quiser fechar isso mexe no perfil, não neste
        probe.
        """
        if not (wm_class or wm_name or exe_basename):
            return False
        janela: dict[str, object] = {"wm_class": wm_class or ""}
        if wm_name:
            janela["wm_name"] = wm_name
        if exe_basename:
            janela["exe_basename"] = exe_basename
        profile = self._manager_de_selecao().select_for_window(janela)
        if profile is None:
            return False
        mode = getattr(profile, "mode", None)
        match = getattr(profile, "match", None)
        return (
            mode is not None
            and getattr(mode, "kind", None) == "gamepad"
            and getattr(match, "type", None) == "criteria"
        )

    def _gather_game_signal_inputs(self) -> dict[str, Any]:
        """Reúne TODA evidência de `classify()` (NUMA-01) — roda no executor.

        O I/O de disco (marker do wrapper, perfis) e a sondagem de pid
        moram AQUI, nunca no provider injetado (que precisa ser leitura de
        bool cacheado, zero I/O — contrato de
        `backend_pydualsense.set_game_authority_provider`). Propaga
        qualquer exceção para o chamador (`_sync_game_signal`), que
        degrada para `unknown` (fail-safe).
        """
        from hefesto_dualsense4unix.daemon.launch_env import (
            pid_is_alive,
            read_last_exit_marker,
            read_last_exit_pid,
            read_last_run_marker,
            read_last_run_pid,
        )

        mono_now = time.monotonic()
        window_healthy = self.store.window_detect_healthy
        window_class_current = self.store.window_detect_current_class
        window_name_current = self.store.window_detect_current_name
        window_exe_current = self.store.window_detect_current_exe
        seen_at = self.store.game_window_seen_at
        window_seen_age = (mono_now - seen_at) if seen_at is not None else None
        marker = read_last_run_marker()
        marker_pid = read_last_run_pid()
        exit_marker = read_last_exit_marker()
        # Correção pós-auditoria da Onda N: `marker_pid`/`exit_pid` correlacionam
        # um `last_exit` (arquivo GLOBAL) ao MESMO launch do `last_run` corrente
        # — sem isso, o `last_exit` tardio de um launch concorrente que falhou o
        # próprio `exec` invalidaria um `last_run` legítimo e mais novo (ver
        # `wrapper_game_running`).
        exit_pid = read_last_exit_pid()
        marker_pid_alive = pid_is_alive(marker_pid)
        return {
            "window_healthy": window_healthy,
            "window_class_current": window_class_current,
            "window_seen_age": window_seen_age,
            "profile_rule_match": self._profile_rule_matches_game(
                window_class_current, window_name_current, window_exe_current
            ),
            "marker": marker,
            "marker_pid_alive": marker_pid_alive,
            "marker_pid": marker_pid,
            "exit_marker": exit_marker,
            "exit_pid": exit_pid,
            "session_open": self._any_game_session_open(),
            "now": time.time(),
        }

    async def _sync_game_signal(self) -> None:
        """Tick lento (~2s) do sinal "jogo real ativo" (NUMA-01).

        É esta fiação que ATIVA o gate NUMA-02/03 (dormente sem ela — os
        3684 testes da suíte REPLICA-03 passam byte-idênticos sem
        provider). Todo I/O mora em `_gather_game_signal_inputs` (roda no
        executor); a classificação em si (`classify` + histerese) é pura e
        barata, direto no event loop. Callbacks de transição são
        best-effort (`contextlib.suppress`) — falha de um passo não aborta
        o tick nem o outro callback.
        """
        signal = self._game_signal
        if signal is None:
            return
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify

        anterior = signal.authority
        try:
            inputs = await self._run_blocking(self._gather_game_signal_inputs)
        except Exception as exc:
            logger.warning("game_signal_degradado", motivo=str(exc))
            signal.mark_degraded(str(exc))
        else:
            raw = classify(**inputs)
            signal.evaluate(raw, session_open=bool(inputs["session_open"]))
        novo = signal.authority
        if novo == anterior:
            return
        if novo == "daemon":
            with contextlib.suppress(Exception):
                defend = getattr(self.controller, "defend_display", None)
                if callable(defend):
                    defend()
        elif anterior == "daemon":
            with contextlib.suppress(Exception):
                replay = getattr(self.controller, "replay_retained_game_outputs", None)
                if callable(replay):
                    replay()

    # ------------------------------------------------------------------
    # Poll loop (permanece aqui: testes fazem monkeypatch de daemon._poll_loop)
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        period = 1.0 / max(1, self.config.poll_hz)
        battery = BatteryDebouncer()
        loop = asyncio.get_running_loop()
        next_rumble_assert_at: float = 0.0
        evdev_watchdog_next_at: float = 0.0
        # FEAT-DSX-COOP-LOCAL-01: reconcilia os jogadores secundários (P2+) a cada
        # ~2s (enumerar evdevs todo tick é caro); o forward roda todo tick.
        coop_sync_next_at: float = 0.0
        # COR-01: reconcilia o registro de identidade (slots de sessão) a cada
        # ~2s. ANTES do gate de conexão de propósito: é este reconcile que
        # observa a sessão ESVAZIAR (zero controles → reservas expiram, D2) —
        # depois do gate ele nunca rodaria desconectado. Custo por tick: uma
        # comparação de float; o describe (getattrs) só no tick lento.
        identity_sync_next_at: float = 0.0
        # EXT-04: LED dos EXTERNOS no tick lento do daemon (leitura IPC virou
        # pura). Também ANTES do gate de conexão: o 8BitDo/Pro Controller
        # merece número mesmo sem nenhum DualSense plugado. No-op sem fiação
        # (backend fake) — custo por tick: uma comparação de float.
        external_led_next_at: float = 0.0
        # NUMA-01: sinal "jogo real ativo" no MESMO tick lento (~2s), TAMBÉM
        # antes do gate de conexão — o marker do wrapper e a janela do jogo
        # independem do controle estar plugado neste instante.
        game_signal_next_at: float = 0.0
        # PROTOCOLO-QUEDA-01: sonda da bateria, no MESMO intervalo do diário
        # (`INTERVALO_SONDA_S`, 30 s) — pedir mais vezes não adiantaria nada: o
        # `DiarioDaBateria.observar` se gateia pelo próprio relógio e devolveria
        # sem ler. Custo por tick sem sonda: uma comparação de float.
        battery_journal_next_at: float = 0.0
        # R-03: dreno da pendência de `mode` adiada pelo lock de gesto manual.
        # ~1 Hz (o lock é de 30 s — precisão de segundo basta) e TAMBÉM antes do
        # gate de conexão: um blip de link BT não pode fazer o modo do perfil
        # sumir de vez, que é justamente a queixa que o R-03 cura. Custo por
        # tick sem pendência: uma comparação de float.
        mode_pending_next_at: float = 0.0
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager
        previous_buttons: frozenset[str] = frozenset()
        # BUG-DAEMON-CONNECT-GHOST-INPUT-01: rastreia a borda
        # desconectado→conectado. Começa False (boot pode ser sem hardware);
        # vira True na 1ª leitura bem-sucedida, quando armamos o grace.
        was_connected = False

        while not self._is_stopping():
            tick_started = loop.time()
            if tick_started >= identity_sync_next_at:
                identity_sync_next_at = tick_started + 2.0
                self._sync_identity_registry()
                # AUTO-01.1: dois controles na mesa ligam a emulação sozinhos —
                # sem ela o co-op não existe e os quatro DualSense viram um
                # cursor só. Aqui, no MESMO tique do reconcile de identidade,
                # porque as duas coisas leem a mesma fonte barata
                # (`describe_controllers`) e porque isto TAMBÉM precisa rodar
                # antes do gate de conexão: é o segundo controle que interessa,
                # e a leitura do backend não depende do primário estar lendo
                # estado neste instante. Nunca derruba o poll loop.
                with contextlib.suppress(Exception):
                    self.aplicar_gamepad_para_multiplos_controles()
            if tick_started >= battery_journal_next_at:
                battery_journal_next_at = tick_started + INTERVALO_SONDA_S
                self._amostrar_bateria(tick_started)
            if tick_started >= external_led_next_at:
                external_led_next_at = tick_started + 2.0
                # HANG-01: nunca mais `await` inline — só AGENDA a task (o
                # poll loop segue SEMPRE, mesmo se o tick anterior travar).
                self._schedule_external_tick()
            if tick_started >= game_signal_next_at:
                game_signal_next_at = tick_started + 2.0
                await self._sync_game_signal()
            if tick_started >= mode_pending_next_at:
                mode_pending_next_at = tick_started + 1.0
                # R-03: DEPOIS do `_sync_game_signal` de propósito — a guarda de
                # "jogo com a autoridade" tem de ler a autoridade deste tick, não
                # a de dois segundos atrás.
                with contextlib.suppress(Exception):
                    self._drenar_modo_pendente()
            # BUG-DAEMON-NO-DEVICE-FATAL-01: se o controller ainda não está
            # conectado (boot sem hardware ou pós-unplug), pula o tick
            # silenciosamente. O `reconnect_loop` cuida de retentar; quando
            # conectar, o tick seguinte volta a ler estado normalmente.
            if not self.controller.is_connected():
                # BUG-DAEMON-CONNECT-GHOST-INPUT-01: desconexão detectada via
                # is_connected() (probe/unplug). Zera o baseline e rearma a
                # borda para que a próxima conexão refaça o settling.
                was_connected = False
                previous_buttons = frozenset()
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=period)
                    break
                continue
            try:
                state = await self._run_blocking(self.controller.read_state)
            except Exception as exc:
                logger.warning("poll_read_failed", err=str(exc), exc_info=True)
                # PROTOCOLO-QUEDA-01: a última carga conhecida ANTES de qualquer
                # reconexão. É o dado que transforma o próximo "desligou sozinho"
                # em resposta — e este caminho (erro de leitura) é o irmão do
                # `probe_offline` de `daemon/connection.py`.
                registrar_queda_da_bateria(self, "poll_read_failed", tick_started)
                self.bus.publish(EventTopic.CONTROLLER_DISCONNECTED, {"reason": str(exc)})
                if self.config.auto_reconnect:
                    from hefesto_dualsense4unix.daemon.connection import reconnect

                    previous_buttons = frozenset()
                    was_connected = False
                    await reconnect(self)
                    continue
                break

            # BUG-DAEMON-CONNECT-GHOST-INPUT-01: borda desconectado→conectado.
            # Esta é a 1ª leitura após (re)conectar. Arma o grace-period: até
            # `_input_ready_at`, todo input emulado fica suprimido (ver gate
            # `input_ready` abaixo). O baseline de `previous_buttons` e do
            # edge-tracker do teclado é semeado a cada tick do grace (abaixo),
            # cobrindo o HID-raw cru (ex.: micBtn) e o snapshot evdev ainda
            # populando.
            if not was_connected:
                self._input_ready_at = tick_started + INPUT_GRACE_SEC
                was_connected = True
                logger.info(
                    "input_settling_started",
                    grace_sec=INPUT_GRACE_SEC,
                    transport=state.transport,
                )

            self.store.update_controller_state(state)
            # CLUSTER-IPC-STATE-PROFILE-01 (Bug A): publica o último state
            # no slot `_last_state` para `daemon.state_full` consumir
            # (em paralelo ao store, que mantém snapshot consolidado).
            self._last_state = state
            self.bus.publish(EventTopic.STATE_UPDATE, state)
            self.store.bump("poll.tick")

            if tick_started >= next_rumble_assert_at:
                self._reassert_rumble(tick_started)
                next_rumble_assert_at = tick_started + 0.200

            # FEAT-DSX-EVDEV-WATCHDOG-01: cross-check HID x evdev. Chegamos aqui só
            # com o HID conectado (gate acima) e lendo estado — se o evdev reader
            # ficou preso num node OBSOLETO (re-enumeração pós storm -71 / replug
            # rápido) sem receber ENODEV, o read_loop zumbi não levanta erro e o
            # controle fica "morto" sem sinal. Forçamos reabrir. IDLE-SAFE: só
            # dispara por TROCA real de node, nunca por ociosidade. Throttle p/
            # não escanear /dev/input todo tick; offload via _run_blocking.
            if tick_started >= evdev_watchdog_next_at:
                evdev_watchdog_next_at = tick_started + EVDEV_WATCHDOG_SEC
                heal = getattr(self.controller, "heal_evdev_if_stale", None)
                if heal is not None:
                    with contextlib.suppress(Exception):
                        if await self._run_blocking(heal):
                            self.store.bump("evdev.watchdog.reopen")

            buttons_pressed = self._evdev_buttons_once()
            current_buttons = state.buttons_pressed

            # FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01: o forward pro gamepad virtual é a
            # ROTA do controle pro JOGO — precisa sobreviver TANTO ao 'pause'
            # (daemon.pause) QUANTO ao 'modo jogo' (_emulation_suppressed). Antes
            # o dispatch do gamepad morava DENTRO dos dois gates de emulação de
            # DESKTOP: o `continue` do gate de pausa (abaixo) ocorria antes dele,
            # e ele ainda exigia `emu_active` (não-suprimido). Resultado: entrar
            # em modo jogo, pausar, ou renascer pausado no boot deixava o controle
            # MORTO no jogo — o controle físico fica EVIOCGRAB-grabado (gamepad =
            # fonte única) e o virtual parava de receber input = real escondido +
            # virtual mudo. Agora o gamepad é despachado AQUI, gateado SÓ pelo
            # grace-period (anti-ghost-input), com os botões CRUS: o jogo quer
            # PS/Options/dpad crus; a subtração de combo (abaixo) é proteção
            # contra vazamento pro DESKTOP e não se aplica ao gamepad.
            grace_passed = tick_started >= self._input_ready_at
            gamepad_dispatched = False
            if grace_passed and self._gamepad_device is not None:
                self._dispatch_gamepad_emulation(state, buttons_pressed)
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
                gamepad_dispatched = True

            # FEAT-DSX-COOP-LOCAL-01: co-op local — repassa cada controle
            # SECUNDÁRIO ao SEU gamepad virtual (P2+). Como o P1 acima, sobrevive
            # a pause/modo-jogo (é rota pro jogo) e é gateado só pelo grace. A
            # reconciliação (sync, throttada ~2s) cria/derruba os secundários e
            # também desmonta tudo se o co-op/gamepad for desligado.
            if grace_passed:
                coop = get_coop_manager(self)
                if tick_started >= coop_sync_next_at:
                    coop.sync()
                    coop_sync_next_at = tick_started + 2.0
                coop.forward_all()

            # BUG-DAEMON-CONNECT-GHOST-INPUT-01: gate de assentamento. Enquanto
            # `loop.time() < _input_ready_at`, NÃO despacha teclado/mouse/hotkey
            # nem publica BUTTON_DOWN/UP. Continua lendo estado, atualizando o
            # store e publicando STATE_UPDATE/bateria normalmente. Durante o
            # grace, mantemos `previous_buttons` sincronizado ao estado atual e
            # semeamos o edge-tracker do teclado SEM emitir, de modo que ao fim
            # do settling botões fantasma/segurados na conexão sejam o baseline
            # (só disparam quando soltos e re-pressionados).
            # FEAT-DAEMON-PAUSE-RESUME-01: além do grace, respeita _paused — mas
            # isso gateia mouse/teclado/hotkey/edges; o gamepad já foi despachado
            # acima e NÃO é congelado por pausa/supressão.
            # FEAT-NATIVE-MODE-01: o Modo Nativo congela o mesmo dispatch pelo
            # próprio flag (não via pause), então `daemon.resume` NÃO "des-solta"
            # o controle enquanto o Modo Nativo estiver ativo.
            input_ready = grace_passed and not self._paused and not self._native_mode
            if not input_ready:
                # FEAT-PARITY-REVIEW-01 (touchpad/nativo): enquanto o input está
                # congelado (Modo Nativo, pausa ou grace-period) ninguém drena o
                # touchpad. Sem isto o _accum_dx/dy do TouchpadReader cresce a
                # sessão inteira e vira um SALTO de cursor quando a emulação de
                # mouse volta (a saída do Nativo restaura o mouse do stash). Drena
                # a cada tick — no-op quando não há touchpad reader.
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
                if self._keyboard_device is not None:
                    self._prime_keyboard_emulation(buttons_pressed)
                previous_buttons = current_buttons
                self.store.bump("input.settling.tick")
                if battery.should_emit(state.battery_pct, tick_started):
                    self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                    battery.mark_emitted(state.battery_pct, tick_started)
                    self.store.bump("battery.change.emitted")
                    if self._plugins_subsystem is not None:
                        self._plugins_subsystem.dispatch_battery_change(state.battery_pct)
                elapsed = loop.time() - tick_started
                sleep_for = period - elapsed
                if sleep_for > 0:
                    stop_event = self._stop_event
                    assert stop_event is not None
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                        break
                continue

            # FEAT-HOTKEY-COMBO-NO-LEAK-01: não despacha à emulação de DESKTOP os
            # botões de um combo de hotkey em formação (PS+Options, PS+dpad).
            # Senão 'options'→Meta (e dpad→setas) vazam pro desktop ao usar o
            # combo, e se a supressão ligar no mesmo tick o release nunca é
            # enviado → o modificador trava ("Control/Meta sempre segurado").
            emu_buttons = buttons_pressed
            if self._hotkey_manager is not None:
                blocked = self._hotkey_manager.combo_buttons_active(buttons_pressed)
                if blocked:
                    emu_buttons = buttons_pressed - blocked

            # Mouse/teclado de DESKTOP: gateados por emu_active (modo jogo) e só
            # quando o gamepad NÃO foi despachado (exclusão mútua — com o gamepad
            # ligado, o controle vai pro jogo, não pro cursor/teclado).
            #
            # EMULACAO-NO-JOGO-01: o `not gamepad_dispatched` NÃO basta, e nunca
            # bastou. Ele lê a ausência do vpad como permissão, e a exceção do
            # Steam Input derruba o vpad de propósito com o jogo aberto — a
            # proteção virava a porta de entrada do Alt+Tab do R1 dentro da
            # partida (9/9 episódios medidos no journal dela). O termo novo
            # pergunta "há jogo com autoridade?" em vez de "o vpad despachou?".
            # Ele apenas ESTREITA o predicado (nunca alarga: alargar reabriria o
            # "real escondido + virtual mudo" registrado acima).
            emu_active = not self._emulation_suppressed
            motivo_jogo = (
                self._jogo_no_controle_do_desktop() if not gamepad_dispatched else None
            )
            if motivo_jogo is not None:
                self._calar_emulacao_de_desktop(motivo_jogo, emu_buttons)
            elif self._emu_calada_motivo:
                self._liberar_emulacao_de_desktop(emu_buttons)
            if not gamepad_dispatched and motivo_jogo is None:
                if self._mouse_device is not None and emu_active:
                    self._dispatch_mouse_emulation(state, emu_buttons)
                elif self._touchpad_reader is not None:
                    # B4: emulação off/suprimida → descarta o movimento do
                    # touchpad acumulado, senão o cursor pula ao religar.
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)

                if self._keyboard_device is not None and emu_active:
                    self._dispatch_keyboard_emulation(emu_buttons)

            if self._hotkey_manager is not None:
                self._hotkey_manager.observe(buttons_pressed, now=tick_started)

            if self._plugins_subsystem is not None:
                active_profile = self.store.active_profile
                self._plugins_subsystem.tick(state, active_profile)

            pressed_now = current_buttons - previous_buttons
            released_now = previous_buttons - current_buttons
            for name in sorted(pressed_now):
                self.bus.publish(EventTopic.BUTTON_DOWN, {"button": name, "pressed": True})
                self.store.bump("button.down.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_button_down(name)
            for name in sorted(released_now):
                self.bus.publish(EventTopic.BUTTON_UP, {"button": name, "pressed": False})
                self.store.bump("button.up.emitted")
            previous_buttons = current_buttons

            if battery.should_emit(state.battery_pct, tick_started):
                self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                battery.mark_emitted(state.battery_pct, tick_started)
                self.store.bump("battery.change.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_battery_change(state.battery_pct)

            elapsed = loop.time() - tick_started
            sleep_for = period - elapsed
            if sleep_for > 0:
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                    break

        # HANG-01: ao sair do poll loop (stop pedido ou erro fatal), não
        # deixa a task do tick de externos pendurada — best-effort (só pede
        # o cancelamento; ninguém aqui espera por ela, `shutdown()` já cancela
        # `_tasks` e derruba o executor).
        tick_task = self._external_tick_task
        if tick_task is not None and not tick_task.done():
            tick_task.cancel()

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self.stop)

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        assert self._executor is not None, "executor não inicializado"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    async def _run_external_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Como `_run_blocking`, mas no pool DEDICADO `hefesto-ext` (HANG-01).

        Isola o tick de LED dos externos (`_sync_external_leds`) do pool
        `hefesto-hid` de que `read_state`/`_gather_game_signal_inputs`/o
        watchdog evdev dependem — um wedge aqui vaza no máximo o(s)
        worker(s) deste pool próprio, nunca aquele.
        """
        assert self._external_executor is not None, (
            "external executor não inicializado"
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._external_executor, fn, *args)

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    def _arm_input_grace(self) -> None:
        """Rearma o período de assentamento pós-conexão (BUG-DAEMON-CONNECT-
        GHOST-INPUT-01).

        Usado por `connection.reconnect`/`reconnect_loop` na transição online
        para garantir que o input emulado fique suprimido por `INPUT_GRACE_SEC`
        mesmo quando o poll loop não chega a observar `is_connected() == False`
        entre o unplug e o replug (ex.: reconexão rápida via probe). Encapsula
        a constante e o relógio do event loop para não vazar aritmética de
        tempo para `connection.py`.

        Best-effort fora de um event loop (ex.: chamado em teardown): se não
        houver loop rodando, não há grace a armar.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._input_ready_at = loop.time() + INPUT_GRACE_SEC



__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "DEFAULT_POLL_HZ",
    "RUMBLE_POLICY_MULT",
    "BatteryDebouncer",
    "Daemon",
    "DaemonConfig",
]
