"""Estado atual do daemon, compartilhado entre threads (poll) e loop (consumers).

`StateStore` guarda uma snapshot consistente do controle + perfil ativo +
contadores runtime. Todas as leituras retornam cópias imutáveis
(`ControllerState` já é `frozen=True`, dicionários são copiados rasos);
escrita usa `threading.RLock` para evitar write-tearing entre poll
(executor) e reload (CLI/IPC).

Consumo típico:
    store = StateStore()
    store.update_controller_state(state)       # chamado do executor
    snap = store.snapshot()                    # chamado do loop ou CLI
    active = store.active_profile              # propriedade read-only
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

# CLUSTER-IPC-STATE-PROFILE-01 (Bug C): janela de supressão do autoswitch após
# escolha manual via IPC `profile.switch`. Quando o usuário ativa um perfil
# explicitamente (CLI/GUI/IPC), o autoswitch deve respeitar a escolha por
# `MANUAL_PROFILE_LOCK_SEC` segundos antes de voltar a aplicar perfil pelo
# wm_class da janela ativa. Valor canônico fixo: 30s — curto o bastante para
# não frustrar troca legítima de janela, longo o bastante para a UX "ativei
# manualmente, ele respeitou". Não-objetivo desta sprint torná-lo configurável.
MANUAL_PROFILE_LOCK_SEC: float = 30.0

# JANELA-CEGA-01 (28/07): tempo SEM NENHUMA leitura útil a partir do qual o
# detector de janela passa a se declarar CEGO (`window_detect_seeing` cai; volta
# a subir na primeira leitura útil seguinte). Cinco minutos, e não uma contagem
# de leituras, porque a contagem mentiria: o poll é de 2 Hz e nesta máquina
# (COSMIC/Wayland) o backend é sempre o `xlib`, que só enxerga XWayland — ficar
# minutos com um app Wayland NATIVO em foco produz "unknown" honesto, não
# defeito. 300 s = 600 ticks seguidos sem ver NADA: nem jogo Proton, nem Steam,
# nem a própria GUI. Isso não acontece em uso normal; acontece quando o detector
# está de fato cego. Escolhido curto o bastante para a cegueira aparecer no
# estado dentro de um café, e longo o bastante para não piscar a cada leitura.
WINDOW_DETECT_BLIND_AFTER_SEC: float = 300.0

# ONDA-U F1/F2 (auditoria 21/07): categorias válidas do override manual —
# a trava deixou de ser um booleano único para que limpar uma categoria
# (ex.: fim do "Testar motores" → "rumble") não apague as demais.
#
# SOM-02 (E3/E4, 29-31/07): entra a QUARTA categoria, `audio` — armada pelo
# `speaker.set` (volume, mudo e devolução da posse). A razão, escrita aqui
# porque é aqui que ela vale: é o padrão da casa contra o autoswitch pisar o
# ajuste manual dela na troca de janela. A alternativa considerada — deixar o
# áudio fora da trava e fazer o aplicador de perfil rodar SÓ em troca explícita
# de perfil — deixaria o furo aberto em todo caminho que reaplica o perfil ativo
# sem ser troca explícita, que é justamente a classe de defeito de "a config que
# eu deixo nunca é respeitada". A trava é o mecanismo que já existe para isso, e
# volume é ajuste manual como qualquer outro.
MANUAL_OVERRIDE_CATEGORIES: frozenset[str] = frozenset(
    {"trigger", "led", "rumble", "audio"}
)


@dataclass(frozen=True)
class StoreSnapshot:
    """Snapshot consistente do estado do daemon num instante."""

    controller: ControllerState | None
    active_profile: str | None
    last_battery_pct: int | None
    counters: dict[str, int]
    manual_trigger_active: bool = False


class StateStore:
    """Repositório thread-safe do estado do daemon.

    Escritas usam `RLock`; leituras retornam cópias. RLock (reentrante)
    evita deadlock se um callback dentro de `with self._lock` chamar
    outro método que também adquire o lock (ex: logging).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._controller_state: ControllerState | None = None
        self._active_profile: str | None = None
        self._last_battery_pct: int | None = None
        self._counters: dict[str, int] = {}
        # BUG-MOUSE-TRIGGERS-01 + ONDA-U F1/F2 (auditoria 21/07): quando o
        # usuário aplica um efeito manualmente (trigger.set, led.set,
        # led.player_set, rumble.set/stop, apply_draft), marcamos override
        # ativo POR CATEGORIA ("trigger" | "led" | "rumble"). Enquanto houver
        # categoria armada, o AutoSwitcher NÃO reaplica o perfil ATIVO por
        # mudança de janela — evita que o fallback pise na edição manual.
        # Era um booleano único: o fim do "Testar motores" (passthrough)
        # limpava a trava INTEIRA e apagava overrides de LED/gatilho (F1).
        # Limpeza: profile.switch explícito limpa TUDO; rumble.passthrough
        # limpa SÓ "rumble"; trigger.reset limpa SÓ "trigger" (ABAS-05, 25/07 —
        # limpava tudo, então desligar UM gatilho reabria a troca automática
        # para reescrever a cor que a aba Lightbar acabara de aplicar); jogo com
        # perfil próprio (steam_app_*) limpa tudo ao ativar (F2, ver
        # AutoSwitcher._activate).
        self._manual_override_categories: set[str] = set()
        # FEAT-AUTOSWITCH-LOCK-01 (pedido da mantenedora, 23/07): cadeado
        # explícito da troca automática de perfil. Diferente do lock manual de
        # 30 s acima (que expira) e do pause do daemon (que para toda a
        # emulação): enquanto True, o AutoSwitcher NÃO troca de perfil por foco
        # de janela — a escolha DELA fica —, mas gamepad/co-op/rumble seguem
        # vivos. Persistido no disco pelo handler IPC (sobrevive a reboot).
        self._autoswitch_locked: bool = False
        # CLUSTER-IPC-STATE-PROFILE-01 (Bug C): timestamp absoluto
        # (`time.monotonic`) até quando o autoswitch deve suspender por
        # escolha manual de perfil. 0.0 → lock inativo. Setado pelo handler
        # IPC `profile.switch`; consultado em `AutoSwitcher._activate`.
        self._manual_profile_lock_until: float = 0.0
        # FEAT-NATIVE-MODE-01: Modo Nativo ("release total" do controle). Enquanto
        # ativo, o AutoSwitcher NÃO ativa perfil por foco de janela e o hotkey de
        # ciclo NÃO troca de perfil — nada re-escreve gatilhos/rumble por cima do
        # jogo nativo (Sackboy & cia). Setado por `Daemon.set_native_mode`.
        self._native_mode_active: bool = False
        # FEAT-PROFILE-MODE-01: origem do nativo ativo ("manual" congela o
        # autoswitch; "profile" o mantém observando para reverter ao sair).
        self._native_mode_origin: str | None = None
        # FEAT-WINDOW-DETECT-DIAG-01: diagnóstico do detector de janela do
        # autoswitch. `backend` é o nome do backend efetivamente ativo
        # ("xlib" | "portal" | "wlrctl" | "null"); `healthy` segue a semântica
        # documentada em `record_window_detect_read`; `last_class` é a última
        # wm_class ÚTIL (!= "unknown") vista — permite capturar o wm_class de
        # um jogo direto do estado do daemon, sem garimpar o journal.
        self._window_detect_backend: str | None = None
        self._window_detect_healthy: bool = False
        self._window_detect_last_class: str | None = None
        # NUMA-01: leitura CRUA do tick corrente (inclusive "unknown"/None —
        # ao contrário de `_window_detect_last_class`, que só guarda a
        # última classe ÚTIL e por isso é vetada como evidência de jogo: ela
        # NUNCA decai, prenderia a autoridade em `game` para sempre após o
        # jogo fechar). `_window_detect_read_monotonic` é o relógio dessa
        # leitura; `_game_window_seen_at` é o carimbo (mesmo relógio) da
        # ÚLTIMA vez que a classe casou `steam_app_\d+` — usado pelo
        # `game_signal` para computar uma idade que DECAI.
        self._window_detect_current_class: str | None = None
        self._window_detect_read_monotonic: float | None = None
        self._game_window_seen_at: float | None = None
        # SINAL-DE-JOGO-01 (31/07): os outros dois campos da MESMA leitura de
        # janela. O detector já os entrega (`WindowInfo.as_dict` devolve
        # `wm_class`/`wm_name`/`pid`/`exe_basename`) e o matcher de perfil já os
        # aceita (`MatchCriteria.matches`), mas o store só guardava a classe —
        # então a evidência nº 2 do `game_signal` (regra de perfil) nascia
        # SEMPRE falsa para todo perfil que casa por título ou por processo.
        # Crus e regravados a CADA leitura, como o `current_class` e pelo mesmo
        # motivo: precisam DECAIR junto com ela (sticky é vetado como evidência).
        self._window_detect_current_name: str | None = None
        self._window_detect_current_exe: str | None = None
        # JANELA-CEGA-01: carimbo (`time.monotonic`) da ÚLTIMA leitura ÚTIL e
        # motivo da última leitura NÃO-útil. São eles que permitem a
        # `window_detect_seeing` CAIR — a `window_detect_healthy` é um trinco de
        # mão única por contrato (ver a property) e por isso não serve para
        # dizer se o detector enxerga AGORA.
        self._window_detect_last_useful_monotonic: float | None = None
        self._window_detect_reason: str | None = None
        # UDP-TRIGGER-THRESHOLD-01: limiar (deadzone) do gatilho analógico
        # pedido por mod DSX pela instrução UDP `TriggerThreshold`, por lado.
        # 0 = sem deadzone, que é o padrão e o que valia antes desta sprint.
        # Mora aqui — e não no `UdpHandler` — porque quem escreve (a porta
        # 6969) e quem lê (o dispatch do gamepad virtual, a cada tick) são
        # dois mundos que só se encontram pelo store.
        self._udp_trigger_thresholds: dict[str, int] = {"left": 0, "right": 0}
        # PERFIL-ADIADO-POR-JANELA-01 (09/08/2026): nome do perfil que o restore
        # de boot RECUSOU restaurar de propósito por ser escopado a uma janela
        # (RESTORE-ESCOPO-01, ver `daemon/connection.py`). None = nenhuma recusa
        # pendente.
        #
        # Existe porque `active_profile=None` respondia a DUAS perguntas muito
        # diferentes com a mesma palavra: "nenhum perfil foi configurado" e "o
        # perfil dela existe, é válido, mas está esperando a janela do jogo".
        # Medido na máquina dela: em TODO boot desde 31/07 o journal registra
        # `last_profile_restore_pulado_perfil_de_janela` (name=Pragmata2, depois
        # name=Sackboy) e o `daemon.state_full` responde `active_profile: None` —
        # a recusa fica só no journal, e a janela não tem como contar a diferença.
        # O perfil volta sozinho quando o jogo abre (16 `profile_autoswitch` para
        # `Sackboy` medidos em 08/08), então NÃO se force o restore: o que falta
        # é dizer a verdade enquanto a espera dura.
        self._perfil_adiado_por_janela: str | None = None

    # --- escritas ------------------------------------------------------

    def update_controller_state(self, state: ControllerState) -> None:
        with self._lock:
            self._controller_state = state
            if state.battery_pct != self._last_battery_pct:
                self._last_battery_pct = state.battery_pct

    def set_active_profile(self, name: str | None) -> None:
        """Publica o perfil ativo — e ENCERRA a espera do perfil adiado.

        PERFIL-ADIADO-POR-JANELA-01: a limpeza mora aqui, e não no autoswitch,
        porque este é o ponto de estrangulamento ÚNICO por onde toda ativação
        passa (`ProfileManager.activate`, de qualquer origem: manual, autoswitch,
        system). A espera termina quando um perfil entra de verdade — foi
        exatamente o que aconteceu na máquina dela às 00:04:58, quando o
        `profile.switch` manual para `Sackboy` apagou a pergunta.

        Limpa também no `None` (o `delete()` do perfil ativo, `manager.py:188`):
        preferimos perder a dica a exibi-la velha. O journal guarda o fato
        original de qualquer jeito.
        """
        with self._lock:
            self._active_profile = name
            self._perfil_adiado_por_janela = None

    def set_perfil_adiado_por_janela(self, name: str | None) -> None:
        """Registra que o restore de boot adiou `name` por ser de janela.

        PERFIL-ADIADO-POR-JANELA-01. Chamado por `restore_last_profile`
        (`daemon/connection.py`) nos dois pontos em que ele desiste por escopo —
        o nome resolvido e o fallback do session.json. `None` limpa.
        """
        with self._lock:
            self._perfil_adiado_por_janela = name or None

    def bump(self, counter: str, delta: int = 1) -> int:
        with self._lock:
            value = self._counters.get(counter, 0) + delta
            self._counters[counter] = value
            return value

    def reset_counters(self) -> None:
        with self._lock:
            self._counters.clear()

    # --- deadzone dos gatilhos pedida por mod DSX (UDP-TRIGGER-THRESHOLD-01) --

    def set_udp_trigger_threshold(self, side: str, value: int) -> None:
        """Grava o limiar do lado `side` ("left"|"right"), clampado em 0-255.

        Semântica do DSX, preservada byte a byte: o valor bruto do gatilho só
        chega ao gamepad virtual quando é **maior ou igual** ao limiar; abaixo
        dele o jogo lê zero. Corte seco, sem reescala.
        """
        if side not in ("left", "right"):
            raise ValueError(f"lado de gatilho desconhecido: {side!r}")
        with self._lock:
            self._udp_trigger_thresholds[side] = max(0, min(255, int(value)))

    def clear_udp_trigger_thresholds(self) -> None:
        """Volta os dois lados ao padrão "sem deadzone".

        Chamado pelo `ResetToUserSettings` da porta 6969: a deadzone é parte do
        que o mod mudou, e "voltar às configurações do usuário" a inclui.
        """
        with self._lock:
            self._udp_trigger_thresholds = {"left": 0, "right": 0}

    @property
    def udp_trigger_thresholds(self) -> tuple[int, int]:
        """Par `(esquerdo, direito)` dos limiares vigentes. Lido a cada tick."""
        with self._lock:
            atual = self._udp_trigger_thresholds
            return (atual["left"], atual["right"])

    def mark_manual_trigger_active(self, category: str = "trigger") -> None:
        """Arma o override manual (`"trigger"` | `"led"` | `"rumble"` | `"audio"`).

        Usado pelo `IpcServer` nos IPCs de aplicação (trigger.set → "trigger",
        led.set/led.player_set → "led", rumble.set/stop → "rumble",
        speaker.set → "audio") e pelo `DraftApplier` (categorias das seções
        aplicadas). Enquanto QUALQUER categoria estiver armada, o `AutoSwitcher`
        NÃO reaplica o perfil ativo por mudança de janela (respeita override do
        usuário).
        """
        if category not in MANUAL_OVERRIDE_CATEGORIES:
            raise ValueError(f"categoria de override desconhecida: {category!r}")
        with self._lock:
            self._manual_override_categories.add(category)

    def clear_manual_trigger_active(self, category: str | None = None) -> None:
        """Limpa o override manual — tudo (None) ou SÓ a `category` dada.

        Tudo: `profile.switch` explícito, hotkey de ciclo e a ativação de
        perfil de JOGO pelo autoswitch (F2) — os três são "troquei de perfil",
        onde soltar as três categorias é o que a usuária pediu.

        Categoria única: `rumble.passthrough` limpa só "rumble" (F1 — o fim do
        "Testar motores" não pode apagar um LED/gatilho deliberado de outra
        aba) e, desde o ABAS-05 (25/07), `trigger.reset` limpa só "trigger"
        pela MESMA razão: desligar um gatilho apagava a trava de LED e de
        vibração e reabria a troca automática para reescrever a cor que a aba
        Lightbar tinha acabado de aplicar.
        """
        with self._lock:
            if category is None:
                self._manual_override_categories.clear()
            else:
                self._manual_override_categories.discard(category)

    def set_native_mode_active(
        self, active: bool, origin: str | None = None
    ) -> None:
        """Liga/desliga o gate do Modo Nativo (FEAT-NATIVE-MODE-01).

        Enquanto ativo com origem MANUAL, autoswitch e hotkey de ciclo NÃO
        re-aplicam perfil — o controle fica "solto" para o jogo nativo até a
        usuária desligar. Com origem "profile" (FEAT-PROFILE-MODE-01) o
        autoswitch CONTINUA observando a janela: ao focar outro app, o perfil
        seguinte reverte o nativo (senão o modo por-perfil nunca sairia).
        Setado por `Daemon.set_native_mode`.
        """
        with self._lock:
            self._native_mode_active = bool(active)
            self._native_mode_origin = origin if active else None

    # --- diagnóstico do detector de janela (FEAT-WINDOW-DETECT-DIAG-01) --

    def set_window_detect_backend(self, backend: str | None, healthy: bool) -> None:
        """Semeia o diagnóstico do detector na partida do autoswitch.

        `backend` é o nome do backend escolhido ("xlib" | "portal" | "wlrctl"
        | "null"). `healthy` inicial usa a presunção do chamador (subsystem
        autoswitch): backend "xlib" nasce saudável — ele só é escolhido com
        DISPLAY presente e cobre XWayland/Proton, o caso de uso principal;
        os demais nascem não-saudáveis até a primeira leitura útil (ver
        `record_window_detect_read`). Zera `last_class` (novo boot do
        detector = novo episódio de observação) e, junto (NUMA-01), zera
        também a classe CRUA/monotonic/`game_window_seen_at` — um boot novo
        do detector não pode herdar o carimbo de jogo do episódio anterior.

        JANELA-CEGA-01: zera igualmente o carimbo da última leitura útil e o
        motivo da última leitura não-útil — episódio novo, contabilidade nova.
        Detector recém-semeado ainda NÃO enxergou nada, então
        `window_detect_seeing` nasce False mesmo com `healthy=True` (que é
        presunção, não medição).
        """
        with self._lock:
            self._window_detect_backend = backend
            self._window_detect_healthy = healthy
            self._window_detect_last_class = None
            self._window_detect_current_class = None
            self._window_detect_current_name = None
            self._window_detect_current_exe = None
            self._window_detect_read_monotonic = None
            self._game_window_seen_at = None
            self._window_detect_last_useful_monotonic = None
            self._window_detect_reason = None

    def record_window_detect_read(
        self,
        backend: str | None,
        wm_class: str | None,
        *,
        now: float | None = None,
        reason: str | None = None,
        wm_name: str | None = None,
        exe_basename: str | None = None,
    ) -> None:
        """Registra uma leitura do detector de janela (poll do autoswitch).

        JANELA-CEGA-01: `reason` é o MOTIVO de a leitura não ter sido útil,
        vindo do backend (`XlibBackend.last_failure_reason` e irmãos, via
        `WindowReaderDiag.last_reason`) — "sem conexão X" e "sem foco X" param
        de colapsar no mesmo `None`. Guardado ao lado da leitura crua e
        publicado em `window_detect_reason`; leitura ÚTIL o zera. Só é gravado
        quando a leitura NÃO é útil: o motivo descreve a cegueira, não o
        acerto.

        Semântica de `window_detect_healthy` (documentada de propósito):
        saudável = houve ao menos UMA leitura útil (wm_class != "unknown" e
        não-vazia) desde o boot do autoswitch, OU a presunção inicial do
        backend xlib (ver `set_window_detect_backend`). Leitura "unknown"
        NÃO derruba a flag: desktop vazio também produz "unknown", então
        unknown persistente não distingue "detector cego" de "nenhuma janela
        focada" — o veredito fino de ambiente fica no doctor.sh. `backend` é
        re-gravado a cada leitura porque a cascata Wayland pode migrar em
        runtime (portal -> wlrctl -> null).

        NUMA-01: `window_detect_current_class` grava a leitura CRUA desta
        chamada a CADA vez (inclusive "unknown"/None) — ao contrário do
        `last_class` sticky acima, este é o valor que `game_signal.classify`
        consome (o sticky é VETADO como evidência: nunca decai, prenderia a
        autoridade em `game` para sempre). Quando a classe casa
        `steam_app_\\d+`, carimba `game_window_seen_at` com `now`
        (`time.monotonic()` por default, injetável para teste) — é dessa
        marca que `game_signal` deriva uma idade que DECAI.

        SINAL-DE-JOGO-01 (31/07): `wm_name` e `exe_basename` são os outros dois
        campos da MESMA leitura, guardados crus ao lado da classe para o probe
        de perfil do `game_signal` (`Daemon._profile_rule_matches_game`) poder
        perguntar ao matcher a pergunta inteira — o `MatchCriteria` é um E entre
        os campos preenchidos e alvo ausente NUNCA casa, então um perfil que
        declara `window_title_regex` ou `process_name` devolvia False sempre,
        sem erro nenhum. Eles NÃO participam de `healthy`/`last_class`/
        `game_window_seen_at`: quem define "leitura útil" continua sendo só a
        `wm_class`, porque é ela que a JANELA-CEGA-01 mediu e é ela que a
        evidência nº 1 consome. Opcionais para o chamador antigo continuar
        válido — sem eles o comportamento é byte-idêntico ao de antes.
        """
        moment = now if now is not None else time.monotonic()
        useful = bool(wm_class) and wm_class != "unknown"
        with self._lock:
            self._window_detect_backend = backend
            self._window_detect_current_class = (
                wm_class if isinstance(wm_class, str) else None
            )
            self._window_detect_current_name = (
                wm_name if isinstance(wm_name, str) and wm_name else None
            )
            self._window_detect_current_exe = (
                exe_basename
                if isinstance(exe_basename, str) and exe_basename
                else None
            )
            self._window_detect_read_monotonic = moment
            if useful:
                self._window_detect_healthy = True
                self._window_detect_last_class = wm_class
                self._window_detect_last_useful_monotonic = moment
                self._window_detect_reason = None
            else:
                self._window_detect_reason = reason
            if steam_appid_from_wm_class(
                wm_class if isinstance(wm_class, str) else None
            ) is not None:
                self._game_window_seen_at = moment

    # --- lock manual de profile.switch (Bug C) ------------------------

    def mark_manual_profile_lock(self, until: float) -> None:
        """Arma o lock de supressão do autoswitch até `until` (monotonic).

        Setado pelo handler IPC `profile.switch` com
        `time.monotonic() + MANUAL_PROFILE_LOCK_SEC`. Renovado a cada chamada
        (escolha mais recente vence; não acumula). NÃO é setado por
        autoswitch interno (recursão evitada), `daemon.reload`, nem
        `restore_last_profile` no boot — apenas entrada manual do usuário.
        """
        with self._lock:
            self._manual_profile_lock_until = until

    def manual_profile_lock_active(self, now: float) -> bool:
        """Retorna True se o lock manual ainda está ativo em `now`.

        `now` deve ser obtido via `time.monotonic()` (mesmo relógio usado em
        `mark_manual_profile_lock`). Após o instante de expiração, o
        autoswitch volta a operar normalmente sem precisar de reset.
        """
        with self._lock:
            return now < self._manual_profile_lock_until

    # --- leituras ------------------------------------------------------

    @property
    def controller_state(self) -> ControllerState | None:
        with self._lock:
            return self._controller_state

    @property
    def active_profile(self) -> str | None:
        with self._lock:
            return self._active_profile

    @property
    def perfil_adiado_por_janela(self) -> str | None:
        """Perfil que o boot recusou restaurar por ser escopado a uma janela.

        PERFIL-ADIADO-POR-JANELA-01. Só tem valor enquanto `active_profile` é
        `None`: é o par dos dois que carrega a informação inteira —

          - `active_profile=None`, adiado=`None`   → não há perfil nenhum;
          - `active_profile=None`, adiado=`"Sackboy"` → o perfil dela existe e
            está esperando a janela do jogo (o autoswitch o ativa quando ela
            abrir o Sackboy);
          - `active_profile="Sackboy"`             → entrou; nada pendente.

        Nunca é "erro": a recusa é o desenho do RESTORE-ESCOPO-01 (um perfil de
        jogo que voltasse no boot pintaria a lightbar e suprimiria a paleta
        automática com o jogo fechado). O que era defeito é ela não ter como
        saber disso.
        """
        with self._lock:
            return self._perfil_adiado_por_janela

    @property
    def last_battery_pct(self) -> int | None:
        with self._lock:
            return self._last_battery_pct

    @property
    def manual_trigger_active(self) -> bool:
        """True se QUALQUER categoria de override manual está armada."""
        with self._lock:
            return bool(self._manual_override_categories)

    @property
    def autoswitch_locked(self) -> bool:
        """True quando a troca automática de perfil está congelada (FEAT-AUTOSWITCH-LOCK-01)."""
        with self._lock:
            return self._autoswitch_locked

    def set_autoswitch_locked(self, locked: bool) -> None:
        """Liga/desliga o cadeado da troca automática de perfil."""
        with self._lock:
            self._autoswitch_locked = bool(locked)

    @property
    def manual_override_categories(self) -> frozenset[str]:
        """Snapshot das categorias armadas (telemetria/decisões finas)."""
        with self._lock:
            return frozenset(self._manual_override_categories)

    @property
    def native_mode_active(self) -> bool:
        with self._lock:
            return self._native_mode_active

    @property
    def native_mode_origin(self) -> str | None:
        """Origem do Modo Nativo ativo: "manual" | "profile" | None (inativo)."""
        with self._lock:
            return self._native_mode_origin

    @property
    def window_detect_backend(self) -> str | None:
        """Backend ativo do detector de janela (FEAT-WINDOW-DETECT-DIAG-01).

        "xlib" | "portal" | "wlrctl" | "null"; None = autoswitch nunca subiu.
        """
        with self._lock:
            return self._window_detect_backend

    @property
    def window_detect_healthy(self) -> bool:
        """Detecção de janela saudável? (FEAT-WINDOW-DETECT-DIAG-01).

        True = ao menos 1 leitura útil desde o boot do autoswitch OU presunção
        do backend xlib (semântica completa em `record_window_detect_read`).

        JANELA-CEGA-01 (28/07), AVISO EXPLÍCITO: esta flag é um TRINCO DE MÃO
        ÚNICA — sobe e não desce dentro do mesmo episódio do detector. Isso
        NÃO é descuido, é contrato: o único consumidor de decisão é
        `game_signal.classify` (via `Daemon._gather_game_signal_inputs`), onde
        `healthy=False` sem evidência de jogo classifica a autoridade de
        exibição como `unknown` em vez de `daemon` — e a transição
        `daemon -> unknown` dispara `replay_retained_game_outputs()`, que
        REPINTA a lightbar com o que o jogo deixou retido. Fazer esta flag
        decair aqui mudaria, em silêncio, a cor do controle dela no desktop.
        Quem responde "o detector enxerga AGORA?" é `window_detect_seeing()`,
        que decai e não decide nada. Trocar o consumidor do `game_signal` de
        `healthy` para `seeing` é uma leva própria, com ela vendo.
        """
        with self._lock:
            return self._window_detect_healthy

    def window_detect_useful_age(self, now: float | None = None) -> float | None:
        """Idade, em segundos, da última leitura ÚTIL — None se nunca houve.

        JANELA-CEGA-01. É o número que denuncia a cegueira: um detector que
        nunca mais viu janela nenhuma tem idade que só cresce, enquanto
        `window_detect_last_class` continua exibindo a classe sticky de
        minutos atrás como se fosse notícia fresca. `now` injetável (monotonic)
        para teste.
        """
        with self._lock:
            carimbo = self._window_detect_last_useful_monotonic
        if carimbo is None:
            return None
        momento = now if now is not None else time.monotonic()
        return max(0.0, momento - carimbo)

    def window_detect_seeing(self, now: float | None = None) -> bool:
        """O detector enxergou janela nos últimos `WINDOW_DETECT_BLIND_AFTER_SEC`?

        JANELA-CEGA-01: a resposta que `window_detect_healthy` não pode dar
        (ver o aviso naquela property). CAI depois de
        `WINDOW_DETECT_BLIND_AFTER_SEC` sem nenhuma leitura útil e VOLTA na
        primeira leitura útil seguinte. Nasce False: detector recém-semeado
        ainda não enxergou nada, e presunção não é medição. Puramente
        observável — nenhuma decisão do daemon pende deste valor.
        """
        idade = self.window_detect_useful_age(now)
        if idade is None:
            return False
        return idade < WINDOW_DETECT_BLIND_AFTER_SEC

    @property
    def window_detect_reason(self) -> str | None:
        """Motivo da última leitura NÃO-útil do detector (JANELA-CEGA-01).

        Vem do backend (ex.: "sem_conexao_x" x "sem_foco_x" x
        "foco_discorda_do_net_active"): as seis causas distintas que viravam um
        `None` só, indistinguíveis, param de se perder. None = leitura útil, ou
        nenhum motivo registrado (chamador que ainda não repassa o `reason`).
        """
        with self._lock:
            return self._window_detect_reason

    @property
    def window_detect_last_class(self) -> str | None:
        """Última wm_class ÚTIL vista pelo detector (FEAT-WINDOW-DETECT-DIAG-01).

        None = nenhuma leitura útil ainda. Serve para capturar o wm_class de
        um jogo (ex.: Sackboy) direto do estado, sem ler o journal.
        """
        with self._lock:
            return self._window_detect_last_class

    @property
    def window_detect_current_class(self) -> str | None:
        """wm_class CRUA da ÚLTIMA leitura (NUMA-01) — inclusive "unknown"/None.

        Diferente de `window_detect_last_class` (sticky, só guarda a última
        classe ÚTIL): este é regravado a CADA leitura e é o que
        `game_signal.classify` consome — o sticky é VETADO como evidência
        de jogo (nunca decai, prenderia a autoridade em `game` para sempre).
        """
        with self._lock:
            return self._window_detect_current_class

    @property
    def window_detect_current_name(self) -> str | None:
        """Título CRU da última leitura (SINAL-DE-JOGO-01) — None se vazio.

        O par de `window_detect_current_class`, pela mesma regra: regravado a
        cada leitura, sem sticky, para o probe de perfil do `game_signal` casar
        os perfis que declaram `window_title_regex` (o `coop_local` dela é o
        caso medido: prioridade 75, `mode: gamepad`, e casa SÓ por título).
        """
        with self._lock:
            return self._window_detect_current_name

    @property
    def window_detect_current_exe(self) -> str | None:
        """Basename do executável da última leitura (SINAL-DE-JOGO-01).

        O terceiro campo do matcher (`process_name`). Sem ele, um perfil que
        declara título E processo — cinco dos seis perfis de jogo dela — segue
        falso mesmo com o título casando, porque `MatchCriteria` é um E entre os
        campos preenchidos. Vem de `/proc/<pid>/exe` no backend `xlib`; vazio
        nos backends Wayland, onde vira None e simplesmente não arma nada.
        """
        with self._lock:
            return self._window_detect_current_exe

    @property
    def game_window_seen_at(self) -> float | None:
        """Monotonic da ÚLTIMA leitura cuja classe casou `steam_app_\\d+`.

        NUMA-01: None = nunca visto (ou zerado por `set_window_detect_backend`
        — novo boot do detector). `game_signal` deriva daqui uma IDADE que
        decai — ao contrário do sticky, este carimbo permite ao sinal
        "esquecer" um jogo fechado.
        """
        with self._lock:
            return self._game_window_seen_at

    def counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def snapshot(self) -> StoreSnapshot:
        with self._lock:
            return StoreSnapshot(
                controller=self._controller_state,
                active_profile=self._active_profile,
                last_battery_pct=self._last_battery_pct,
                counters=dict(self._counters),
                manual_trigger_active=bool(self._manual_override_categories),
            )


__all__ = [
    "MANUAL_OVERRIDE_CATEGORIES",
    "MANUAL_PROFILE_LOCK_SEC",
    "WINDOW_DETECT_BLIND_AFTER_SEC",
    "StateStore",
    "StoreSnapshot",
]
