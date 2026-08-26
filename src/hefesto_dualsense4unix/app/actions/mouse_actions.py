"""Aba Mouse: liga/desliga emulação de mouse+teclado via DualSense (FEAT-MOUSE-01)."""
# ruff: noqa: E402
from __future__ import annotations

import os
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    STATE_IPC_TIMEOUT_S,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

UINPUT_DEV = "/dev/uinput"

#: HARM-05: a razão de o switch estar bloqueado, em texto simples. Fala da
#: CONSEQUÊNCIA (o que ela perde), não da regra — e diz onde é o botão certo.
MODE_GATE_HINT = (
    "Só dá para ligar o mouse em \"Controlar o PC\" (aba Início): jogando, o "
    "controle é do jogo — ligar o mouse aqui derrubaria o controle virtual e "
    "os jogadores do co-op no meio da partida."
)

#: INTERRUPTOR-APAGADO-MUDO-01 (25/08/2026, N4) — o interruptor sem estado.
#:
#: `texto = MODE_GATE_HINT if blocked and mode is not None else ""` deixava o
#: caso `mode is None` (Hefesto sem resposta) com o interruptor APAGADO e
#: NENHUMA palavra ao lado. É o que a foto oficial das 18h15 de 23/08 mostra: um
#: interruptor cinza que não diz por quê — e o silêncio é lido como defeito do
#: produto, não como ausência de resposta.
#:
#: A frase é OUTRA, e tem de ser: a do modo jogo afirma o que aqui não se sabe
#: ("o controle é do jogo"). Esta diz só o que é verdade — não sei — e para onde
#: ir. O `blocked` continua igual; o que muda é a tela deixar de emudecer.
MODO_DESCONHECIDO_HINT = (
    "Não consegui falar com o Hefesto agora, então não sei se ligar o mouse "
    "derrubaria um jogo em andamento — por isso o interruptor está apagado. "
    "Veja como está o Hefesto na aba Sistema."
)

#: RECUSA-NAO-E-QUEDA-DE-LINHA-01 (25/08/2026, N6) — os motivos, em português.
#:
#: Mesmo vocabulário do bloco `keyboard_emulation` do daemon
#: (`ipc_handlers._keyboard_emulation_payload`), porque é a MESMA conjunção: a
#: emulação de mouse e a de teclado são suspensas pelo mesmo gate do poll loop.
#: Duplicar as chaves aqui é de propósito — a tabela do teclado descreve um
#: ESTADO ("Ligado, em pausa agora…") e esta descreve o desfecho de um CLIQUE,
#: e um texto que serve para os dois não serve direito para nenhum.
#:
#: **Alcançada desde 25/08/2026 (BG-02):** `mouse.emulation.set` devolve
#: `bloqueio` junto do `failed` (`daemon/ipc_handlers._handle_mouse_emulation_set`)
#: — antes disso a tabela estava commitada e não era chamada por ninguém, e
#: toda recusa caía em `RECUSA_SEM_MOTIVO`. Um daemon mais VELHO que esta
#: janela ainda não manda o campo, e continua caindo lá: `RECUSA_SEM_MOTIVO`
#: DIZ que o motivo faltou, em vez de inventar um.
BLOQUEIO_DO_MOUSE_EM_PORTUGUES: dict[str, str] = {
    "desligada": "a emulação de mouse está desligada no Hefesto",
    "sem_device": (
        "o mouse virtual não subiu — abra a aba Sistema e clique em "
        "“Aplicar correções”"
    ),
    "modo_jogo": "o modo jogo está suspendendo mouse e teclado",
    "vpad_suspenso_pelo_steam_input": (
        "neste jogo quem entrega o controle é a Steam, e o controle virtual foi "
        "recolhido"
    ),
}

#: O Hefesto respondeu, e a resposta foi "não" — sem dizer por quê.
RECUSA_SEM_MOTIVO = (
    "O Hefesto recusou o pedido e não disse por quê. O mouse emulado não foi "
    "alterado."
)

#: Ninguém respondeu. É o único caso em que a comunicação é o assunto.
SEM_RESPOSTA_DO_HEFESTO = (
    "Não obtive resposta do Hefesto. O mouse emulado não foi alterado — veja "
    "como ele está na aba Sistema."
)


def frase_da_recusa_do_mouse(resposta: object) -> str:
    """Texto do toast quando o Hefesto RESPONDE que não vai ligar/desligar.

    N6. `_on_ok` desviava toda resposta `status != "ok"` para o `_on_err` do
    timeout, cujo texto era *"Falha ao comunicar com o daemon"* — a janela
    acusando um defeito de comunicação que não houve. É a
    [ELO-MUDO-01](2026-08-22-ELO-MUDO-01-o-ok-que-nao-sabe-dizer-nao.md) ao
    contrário: em vez de comemorar o que não fez, culpar a rede.

    Pura de propósito — é o miolo do que ela lê, e precisa de teste sem montar
    janela (mesma disciplina de `descrever_teclado_emulado`).
    """
    bloqueio = resposta.get("bloqueio") if isinstance(resposta, dict) else None
    if not isinstance(bloqueio, str) or not bloqueio:
        return RECUSA_SEM_MOTIVO
    motivo = BLOQUEIO_DO_MOUSE_EM_PORTUGUES.get(bloqueio)
    if motivo is None:
        # Motivo NOVO, de um daemon mais novo que esta janela: dizer o código
        # cru é feio, mas é honesto — e é melhor que culpar a rede.
        return (
            f"O Hefesto recusou o pedido (motivo: {bloqueio}). O mouse emulado "
            "não foi alterado."
        )
    return f"O Hefesto recusou: {motivo}. O mouse emulado não foi alterado."



class MouseActionsMixin(WidgetAccessMixin):
    """Controla a aba Mouse."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _mouse_guard_refresh: bool = False

    # Coalescing dos sliders (BUG-MOUSE-GUI-SYNC-01): um RPC em voo por
    # parâmetro; valores emitidos durante o voo guardam só o ÚLTIMO.
    # Lazy-init em _send_mouse_param_async (mixin não tem __init__ próprio).
    _mouse_inflight: dict[str, bool] | None = None
    _mouse_pending: dict[str, int] | None = None

    #: N12 — há teclado na tela instalado NA MÁQUINA, segundo o último
    #: `state_full`. TRI-ESTADO de propósito: `None` é "ainda não sei", e ele
    #: **não** pode virar `False`. A frase de "não tem" manda instalar um
    #: pacote; dizê-la porque ninguém respondeu é a janela afirmando sobre uma
    #: máquina que ela não olhou.
    _osk_disponivel: bool | None = None

    #: BG-02 — o mouse virtual está NO AR, segundo o daemon (o último
    #: `state_full`). TRI-ESTADO, e os três casos são diferentes de verdade:
    #:
    #: - `True`  -- o daemon tem o device aberto (`mouse_emulation.device_ativo`);
    #: - `False` -- o interruptor está LIGADO e o device NÃO subiu
    #:              (`bloqueio == "sem_device"`) — é o defeito que esta frente
    #:              existe para tornar visível: o cursor não anda e a aba calava;
    #: - `None`  -- não sei. Ninguém respondeu, o daemon é mais velho que esta
    #:              janela (sem as chaves novas), **ou a emulação está
    #:              simplesmente desligada** — e este último é o caso que obriga
    #:              o tri-estado: sem device porque ela desligou não é defeito
    #:              nenhum, e mandá-la em "Aplicar correções" por causa de um
    #:              interruptor que ela mesma baixou seria alarme falso.
    _mouse_virtual_no_ar: bool | None = None

    def _anotar_mouse_virtual(self, state: Any) -> None:
        """Lê `mouse_emulation.device_ativo`/`bloqueio` e repinta o rótulo.

        MOUSE-SEM-RAZÃO-01 (BG-02, 25/08/2026). `_refresh_mouse_view` respondia
        "o mouse virtual está pronto?" com uma sonda LOCAL — `import uinput` e
        `os.access("/dev/uinput")` dentro do processo da JANELA. Ela erra nos
        dois sentidos, e os dois foram o caso dela:

        - num Flatpak a janela olha o sandbox e grita "sem permissão" sobre um
          `/dev/uinput` que o daemon abre sem dificuldade nenhuma;
        - com permissão em ordem e o device NÃO no ar (a flag persistida religa
          no boot, `UinputMouseDevice.start()` falha, `_mouse_device` fica
          `None` com o interruptor em pé), a sonda local diz *"Pronto para usar
          como mouse"* enquanto o cursor não anda.

        Quem abre o device é o daemon; a resposta tem de vir de quem executa —
        a mesma disciplina do `osk_disponivel` do vizinho de cima.

        Nenhuma frase nova entra na tela: as quatro do rótulo são as de sempre,
        e o que muda é QUAL delas é a verdadeira.
        """
        bloco = state.get("mouse_emulation") if isinstance(state, dict) else None
        novo: bool | None
        if not isinstance(bloco, dict):
            novo = None
        elif bloco.get("device_ativo") is True:
            novo = True
        elif bloco.get("bloqueio") == "sem_device":
            novo = False
        else:
            # "desligada", "modo_jogo", "vpad_suspenso_pelo_steam_input" e o
            # daemon velho sem as chaves caem aqui: nenhum deles é o rótulo
            # falando. O modo jogo já tem a frase dele em
            # `mouse_mode_hint_label`, e desligada é escolha dela.
            novo = None
        if novo == self._mouse_virtual_no_ar:
            return
        self._mouse_virtual_no_ar = novo
        self._refresh_mouse_view()

    def _anotar_teclado_na_tela(self, state: Any) -> None:
        """Lê `keyboard_emulation.osk_disponivel` do estado vivo e avisa a aba.

        TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01 (25/08/2026, N12). O dado é
        publicado pelo daemon desde 10/08 (`_keyboard_emulation_payload`) e
        `grep -rn "osk_disponivel" src/hefesto_dualsense4unix/app/` devolvia
        VAZIO: a janela nunca o leu. Enquanto isso a legenda da aba recitava
        `onboard` e `wvkbd-mobintl` como texto fixo, sem nunca dizer se algum
        estava instalado — e o L3 é o único caminho do produto para ESCREVER
        texto, porque nenhum atalho de fábrica digita letra.

        Mora aqui, e não na aba de atalhos, porque é aqui que o `state_full`
        chega. A repintura é um gancho opcional (`_repintar_legenda_do_teclado`)
        para o mixin de mouse não depender do de atalhos: quem herda os dois
        (`InputActionsMixin`) o implementa; quem herda só este segue sem ele.

        A janela não faz o `shutil.which` por conta própria de propósito: num
        Flatpak ela olharia dentro do sandbox e responderia sobre uma máquina
        que não é a dela.
        """
        bloco = state.get("keyboard_emulation") if isinstance(state, dict) else None
        bruto = bloco.get("osk_disponivel") if isinstance(bloco, dict) else None
        novo = bruto if isinstance(bruto, bool) else None
        if novo == self._osk_disponivel:
            return
        self._osk_disponivel = novo
        repintar = getattr(self, "_repintar_legenda_do_teclado", None)
        if callable(repintar):
            repintar()

    def _refresh_mouse_from_draft(self) -> None:
        """Popula widgets da aba Mouse a partir de self.draft.mouse.

        Protegido por _mouse_guard_refresh para não disparar handlers de signal
        durante a atualização programatica dos widgets.
        """
        if self._mouse_guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._mouse_guard_refresh = True
        try:
            mouse = draft.mouse
            toggle: Gtk.Switch = self._get("mouse_emulation_toggle")
            if toggle is not None:
                toggle.set_active(mouse.enabled)
            speed_scale: Gtk.Scale = self._get("mouse_speed_scale")
            if speed_scale is not None:
                speed_scale.set_value(float(mouse.speed))
            scroll_scale: Gtk.Scale = self._get("mouse_scroll_speed_scale")
            if scroll_scale is not None:
                scroll_scale.set_value(float(mouse.scroll_speed))
        finally:
            self._mouse_guard_refresh = False

    def install_mouse_tab(self) -> None:
        # A legenda de mapeamento virou um GtkFrame estático no Glade
        # (UI-MOUSE-CLEANUP-01). O `mouse_legend_label` não existe em nenhuma
        # versão do arquivo, então o branch de compatibilidade que vivia aqui
        # nunca era alcançado e mantinha viva uma constante de 16 linhas que
        # duplicava o texto do Glade — duas fontes da verdade para a mesma
        # tabela, uma delas invisível.
        self._refresh_mouse_view()
        # T6: popula os widgets a partir do draft já no bootstrap. Sem isto, se o
        # daemon estiver offline no install, a aba mostra os defaults do glade em
        # vez dos valores do perfil ativo. Idempotente sob _mouse_guard_refresh.
        self._refresh_mouse_from_draft()

    # --- sincronização com o estado vivo do daemon (BUG-MOUSE-GUI-SYNC-01 A1) ---

    def _refresh_mouse_tab(self) -> None:
        """Refresh completo da aba Mouse: draft imediato + estado vivo assíncrono."""
        self._refresh_mouse_from_draft()
        self._refresh_mouse_from_daemon_async()

    def _sync_mouse_mode_gate(self, mode: str | None) -> None:
        """HARM-05: o switch da aba Mouse só existe dentro de "Controlar o PC".

        O dono da emulação de mouse/teclado é o MODO, não esta aba — aqui só se
        ajusta o que o modo desktop liga. Ligar o switch durante "Jogar pelo
        Hefesto" derrubava o vpad e os jogadores do co-op SEM AVISO (a exclusão
        mútua do daemon é silenciosa): a exclusão continua, mas agora é visível
        ANTES do clique, com a razão ao lado.

        Modo desconhecido (Hefesto sem resposta) também bloqueia, e desde
        25/08/2026 (N4) com uma frase PRÓPRIA — ver `MODO_DESCONHECIDO_HINT`.
        Bloquear continua certo: sem estado não dá para saber se ligar o mouse
        derrubaria um jogo em andamento. Emudecer é que não era.
        """
        blocked = mode != MODE_DESKTOP
        toggle = self._get("mouse_emulation_toggle")
        if toggle is not None:
            toggle.set_sensitive(not blocked)
        hint = self._get("mouse_mode_hint_label")
        if hint is None:
            return
        if not blocked:
            texto = ""
        elif mode is None:
            texto = MODO_DESCONHECIDO_HINT
        else:
            texto = MODE_GATE_HINT
        hint.set_text(texto)
        hint.set_visible(bool(texto))

    def _refresh_mouse_from_daemon_async(self) -> None:
        """Sincroniza a aba Mouse com o bloco ``mouse_emulation`` vivo do daemon.

        A1: o draft nasce do PERFIL (que não tem seção mouse) — sem esta rota a
        aba mente quando a emulação foi ligada por CLI/applet/flag de boot.
        Assíncrono (call_async) para não bloquear a thread GTK; widgets são
        atualizados sob ``_mouse_guard_refresh`` via ``_refresh_mouse_from_draft``.
        NÃO marca ``dirty`` — sincronização programática não é toque da usuária.
        """
        def _on_state(state: Any) -> bool:
            # HARM-05: o gate do modo vem ANTES de qualquer return — os ramos
            # abaixo pulam a atualização do draft (edição pendente, seção do
            # perfil), não a exclusão mútua, que vale sempre.
            self._sync_mouse_mode_gate(
                mode_of_state(state if isinstance(state, dict) else None)
            )
            # N12: pela mesma razão, e pelo mesmo motivo de estar ANTES dos
            # returns — o `osk_disponivel` não tem nada a ver com o rascunho do
            # mouse, e perdê-lo porque a seção do perfil está preenchida seria
            # o dado chegar no fio e a tela continuar sem ele.
            self._anotar_teclado_na_tela(state)
            # BG-02: e pelo mesmo motivo ainda — "o mouse virtual subiu?" não
            # tem nada a ver com edição pendente nem com seção de perfil. Sair
            # pelos returns abaixo com o dado na mão deixaria o rótulo mentindo
            # exatamente quando ela está mexendo na aba.
            self._anotar_mouse_virtual(state)
            me = state.get("mouse_emulation") if isinstance(state, dict) else None
            if not isinstance(me, dict):
                return False
            draft = getattr(self, "draft", None)
            if draft is None:
                return False
            # BUG-MOUSE-SLIDER-PREF-LOSS-01: se a usuária tem uma edição pendente
            # (dirty — ex.: arrastou o slider com a emulação OFF, que só atualiza
            # o draft sem IPC), NÃO sobrepor com o estado vivo: sobrescrever
            # apagaria a preferência e ainda persistiria o valor do daemon como
            # se fosse escolha dela. O estado vivo re-sincroniza após Aplicar.
            # BUG-MOUSE-OVERLAY-CLOBBERS-SECTION-01: idem para perfil COM seção
            # mouse (in_profile) — a aba mostra o valor do PERFIL (= o que será
            # salvo); sobrepor o vivo faria o Salvar Perfil clobberar a seção.
            if draft.mouse.dirty or draft.mouse.in_profile:
                return False
            try:
                new_mouse = draft.mouse.model_copy(
                    update={
                        "enabled": bool(me.get("enabled", False)),
                        "speed": int(me.get("speed", draft.mouse.speed)),
                        "scroll_speed": int(
                            me.get("scroll_speed", draft.mouse.scroll_speed)
                        ),
                    }
                )
            except (TypeError, ValueError) as exc:
                logger.warning("mouse_state_full_bloco_invalido", erro=str(exc))
                return False
            self.draft = draft.model_copy(update={"mouse": new_mouse})
            self._refresh_mouse_from_draft()
            return False

        def _on_err(_exc: Exception) -> bool:
            # Daemon offline: mantém o draft atual (defaults seguros). O switch
            # fecha (HARM-05) — sem estado não dá para saber se ligar o mouse
            # derrubaria um jogo em andamento.
            self._sync_mouse_mode_gate(None)
            # N12: sem resposta, a aba volta a "não sei" sobre o teclado na
            # tela. Guardar o último valor conhecido seria afirmar sobre uma
            # máquina que ninguém acabou de olhar.
            self._anotar_teclado_na_tela(None)
            # BG-02: idem para o mouse virtual — sem daemon o rótulo volta à
            # sonda local, que é o melhor palpite que a janela sabe dar sozinha.
            self._anotar_mouse_virtual(None)
            return False

        ipc_bridge.call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=_on_err,
            # HARM-15: o state_full não cabe nos 0.25s default sob carga
            # (hotplug, co-op subindo) — sem folga o `_on_err` fechava o switch
            # com o daemon VIVO e em modo desktop.
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    # --- handlers de UI ---

    def on_mouse_toggle_set(self, switch: Gtk.Switch, _state: Any) -> bool:
        if self._mouse_guard_refresh:
            return False
        enabled = bool(switch.get_active())
        speed = self._read_speed("mouse_speed_scale", DEFAULT_MOUSE_SPEED)
        scroll = self._read_speed("mouse_scroll_speed_scale", DEFAULT_SCROLL_SPEED)

        def _on_ok(result: Any) -> bool:
            # N6: a resposta "não" tem saída PRÓPRIA. Antes ela caía no
            # `_on_err` do timeout e a janela acusava a rede por um defeito que
            # não houve.
            if isinstance(result, dict) and result.get("status") != "ok":
                return _on_recusa(result)
            draft = getattr(self, "draft", None)
            if draft is not None:
                # HARM-05: `dirty=False` — o daemon ACABOU de aplicar, não há nada
                # pendente. Marcar dirty aqui fazia o próprio sucesso do toggle
                # deixar a seção suja pelo resto da sessão, e o "Aplicar" seguinte
                # do rodapé re-enviava `mouse.emulation.set` — religando o mouse e
                # matando o vpad no meio do jogo. `in_profile=True` mantém a seção
                # no "Salvar Perfil" (é o que o dirty garantia de carona).
                new_mouse = draft.mouse.model_copy(
                    update={
                        "enabled": enabled,
                        "speed": speed,
                        "scroll_speed": scroll,
                        "dirty": False,
                        "in_profile": True,
                    }
                )
                self.draft = draft.model_copy(update={"mouse": new_mouse})
            status = "ligado" if enabled else "desligado"
            self._toast_mouse(f"Mouse emulado {status}")
            self._refresh_mouse_view()
            return False

        def _voltar_ao_confirmado() -> None:
            # BUG-MOUSE-TOGGLE-STALE-REVERT-01: reverte para o último estado
            # CONFIRMADO (draft.mouse.enabled só muda no sucesso), não para
            # ``not enabled`` capturado no clique — com dois toggles rápidos e
            # daemon travado, ``not enabled`` do 2º RPC deixava o switch preso
            # ON. Reverter para o confirmado converge ao estado real do daemon.
            # A reversão é IDÊNTICA nas duas saídas de insucesso (N6 separou os
            # TEXTOS, não o comportamento do interruptor).
            draft = getattr(self, "draft", None)
            confirmed = draft.mouse.enabled if draft is not None else not enabled
            self._revert_mouse_toggle(confirmed)

        def _on_recusa(resposta: Any) -> bool:
            """O Hefesto respondeu, e a resposta foi não (N6)."""
            self._toast_mouse(frase_da_recusa_do_mouse(resposta))
            _voltar_ao_confirmado()
            return False

        def _on_err(_exc: Exception) -> bool:
            """Ninguém respondeu — o único caso em que a rede é o assunto."""
            self._toast_mouse(SEM_RESPOSTA_DO_HEFESTO)
            _voltar_ao_confirmado()
            return False

        ipc_bridge.call_async(
            "mouse.emulation.set",
            # ORIGEM-QUE-MENTE-01: clique dela na aba Mouse.
            {
                "enabled": enabled,
                "speed": speed,
                "scroll_speed": scroll,
                "origin": "manual",
            },
            on_success=_on_ok,
            on_failure=_on_err,
        )
        # Otimista: o default handler aplica o estado; falha reverte no callback.
        return False

    def _revert_mouse_toggle(self, active: bool) -> None:
        """Reverte o switch sem reentrar no handler (BUG-MOUSE-GUI-SYNC-01 A3).

        Em GTK3, ``set_active`` reemite ``state-set`` SINCRONAMENTE (``return
        True`` no handler não evita — repro real: 999 reentradas +
        RecursionError). Salva/restaura ``_mouse_guard_refresh`` em vez de zerar
        absoluto: o revert pode disparar dentro de um refresh programático que
        mantém o guard True (padrão do fix ``_update_preset_to_custom``).
        """
        switch = self._get("mouse_emulation_toggle")
        if switch is None:
            return
        prev_guard = self._mouse_guard_refresh
        self._mouse_guard_refresh = True
        try:
            switch.set_active(active)
        finally:
            self._mouse_guard_refresh = prev_guard

    def on_mouse_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._mouse_guard_refresh:
            return
        speed = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_mouse = draft.mouse.model_copy(update={"speed": speed, "dirty": True})
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        self._send_mouse_param_async("speed", speed)

    def on_mouse_scroll_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._mouse_guard_refresh:
            return
        scroll = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_mouse = draft.mouse.model_copy(
                update={"scroll_speed": scroll, "dirty": True}
            )
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        self._send_mouse_param_async("scroll_speed", scroll)

    def _send_mouse_param_async(self, param: str, value: int) -> None:
        """Envia UM parâmetro de velocidade via IPC, SEM ``enabled`` (A4).

        O payload speed-only cai na rota do daemon que atualiza config e device
        (se existir) sem start/stop nem persistir o flag — religar a emulação
        pelo slider é impossível por construção, mesmo com toggle stale-ON.

        Coalescing simples: um RPC em voo por parâmetro; mudanças durante o voo
        guardam só o último valor, reenviado ao terminar. Falha é silenciosa
        (slider é gesto contínuo; toast por tick poluiria a statusbar).
        """
        if self._mouse_inflight is None or self._mouse_pending is None:
            self._mouse_inflight = {}
            self._mouse_pending = {}
        inflight = self._mouse_inflight
        pending = self._mouse_pending
        if inflight.get(param):
            pending[param] = value
            return
        inflight[param] = True

        def _finish() -> None:
            inflight[param] = False
            próximo = pending.pop(param, None)
            if próximo is not None and próximo != value:
                self._send_mouse_param_async(param, próximo)

        def _on_ok(_result: Any) -> bool:
            _finish()
            return False

        def _on_err(exc: Exception) -> bool:
            logger.debug("mouse_param_async_falhou", param=param, erro=str(exc))
            _finish()
            return False

        ipc_bridge.call_async(
            "mouse.emulation.set",
            # ORIGEM-QUE-MENTE-01: ela mexeu no controle deslizante.
            {param: int(value), "origin": "manual"},
            on_success=_on_ok,
            on_failure=_on_err,
        )

    # --- helpers ---

    def _read_speed(self, widget_id: str, default: int) -> int:
        w = self._get(widget_id)
        if w is None:
            return default
        return int(w.get_value())

    def _mouse_is_enabled(self) -> bool:
        toggle = self._get("mouse_emulation_toggle")
        return bool(toggle and toggle.get_active())

    def _refresh_mouse_view(self) -> None:
        """Pinta "o mouse virtual está pronto?" — o daemon manda, a sonda ajuda.

        BG-02. A sonda local (`import uinput` + `os.access`) continua aqui e
        continua útil: ela é a única que sabe QUAL é o defeito (falta o módulo?
        falta permissão no nó?) e é o melhor palpite quando ninguém respondeu.
        O que ela não pode mais fazer é decidir sozinha, porque quem abre o
        device é o daemon — ver `_anotar_mouse_virtual`.

        A ordem abaixo é essa hierarquia, e nenhuma frase mudou:

        - device no ar segundo o daemon → pronto, mesmo que a sonda local
          discorde (o caso do Flatpak, que olha o sandbox);
        - módulo ausente → falta componente (a sonda é a única que vê isso);
        - nó sem permissão para ESTE processo → a frase da permissão;
        - device fora do ar segundo o daemon, ou nó inexistente → "ainda não
          está pronto". É aqui que entra o caso que a aba calava: permissão em
          ordem, interruptor em pé e o cursor parado.
        """
        label = self._get("mouse_uinput_status_label")
        if label is None:
            return
        try:
            import uinput  # noqa: F401
            module_ok = True
        except ImportError:
            module_ok = False

        dev_exists = os.path.exists(UINPUT_DEV)
        dev_writable = os.access(UINPUT_DEV, os.W_OK) if dev_exists else False
        no_ar = self._mouse_virtual_no_ar

        if no_ar is True:
            label.set_markup(
                '<span foreground="#50fa7b">Pronto para usar como mouse</span>'
            )
        elif not module_ok:
            label.set_markup(
                '<span foreground="#ff5555">Falta um componente do mouse virtual — '
                'rode a instalação de novo (./install.sh)</span>'
            )
        elif dev_exists and not dev_writable:
            label.set_markup(
                '<span foreground="#ff5555">O mouse virtual está sem permissão — '
                'abra a aba Sistema e clique em “Aplicar correções”</span>'
            )
        elif no_ar is False or not dev_exists:
            label.set_markup(
                '<span foreground="#ffb86c">O mouse virtual ainda não está pronto — '
                'abra a aba Sistema e clique em “Aplicar correções”</span>'
            )
        else:
            label.set_markup(
                '<span foreground="#50fa7b">Pronto para usar como mouse</span>'
            )

    def _toast_mouse(self, msg: str) -> None:
        self._status_toast("mouse", msg)


__all__ = [
    "BLOQUEIO_DO_MOUSE_EM_PORTUGUES",
    "MODE_GATE_HINT",
    "MODO_DESCONHECIDO_HINT",
    "RECUSA_SEM_MOTIVO",
    "SEM_RESPOSTA_DO_HEFESTO",
    "UINPUT_DEV",
    "MouseActionsMixin",
    "frase_da_recusa_do_mouse",
]

# "Conhece-te a ti mesmo." — Sócrates
