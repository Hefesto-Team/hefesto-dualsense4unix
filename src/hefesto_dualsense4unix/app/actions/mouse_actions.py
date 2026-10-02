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
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

logger = get_logger(__name__)

UINPUT_DEV = "/dev/uinput"

MODE_GATE_HINT = (
    "Só dá para ligar o mouse em \"Controlar o PC\" (aba Início): jogando, o "
    "controle é do jogo — ligar o mouse aqui derrubaria o controle virtual e "
    "os jogadores do co-op no meio da partida."
)

MODO_DESCONHECIDO_HINT = (
    "Não consegui falar com o Hefesto agora, então não sei se ligar o mouse "
    "derrubaria um jogo em andamento — por isso o interruptor está apagado. "
    "Veja como está o Hefesto na aba Sistema."
)

#: Mesmo vocabulário do bloco `keyboard_emulation` do daemon
#: (`ipc_handlers._keyboard_emulation_payload`), porque é a MESMA conjunção: a
#: **Alcançada desde 25/08/2026 (BG-02):** `mouse.emulation.set` devolve
BLOQUEIO_DO_MOUSE_EM_PORTUGUES: dict[str, str] = {
    "desligada": "a emulação de mouse está desligada no Hefesto",
    # o `disable_steam_input.sh` e o `fix_wireplumber_default_source.sh` — nem
    # `{gesto}` é trocado em `frase_da_recusa_do_mouse` pela frase única de
    "sem_device": "o mouse virtual não subiu — {gesto}",
    "modo_jogo": "o modo jogo está suspendendo mouse e teclado",
    "vpad_suspenso_pelo_steam_input": (
        "neste jogo quem entrega o controle é a Steam, e o controle virtual foi "
        "recolhido"
    ),
}

RECUSA_SEM_MOTIVO = (
    "O Hefesto recusou o pedido e não disse por quê. O mouse emulado não foi "
    "alterado."
)

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
        return (
            f"O Hefesto recusou o pedido (motivo: {bloqueio}). O mouse emulado "
            "não foi alterado."
        )
    motivo = motivo.replace("{gesto}", como_atualizar_esta_instalacao())
    return f"O Hefesto recusou: {motivo}. O mouse emulado não foi alterado."


class MouseActionsMixin(WidgetAccessMixin):
    """Controla a aba Mouse."""

    _mouse_guard_refresh: bool = False

    _mouse_inflight: dict[str, bool] | None = None
    _mouse_pending: dict[str, int] | None = None

    #: `state_full`. TRI-ESTADO de propósito: `None` é "ainda não sei", e ele
    _osk_disponivel: bool | None = None

    #: `state_full`). TRI-ESTADO, e os três casos são diferentes de verdade:
    _mouse_virtual_no_ar: bool | None = None

    def _anotar_mouse_virtual(self, state: Any) -> None:
        """Lê `mouse_emulation.device_ativo`/`bloqueio` e repinta o rótulo."""
        bloco = state.get("mouse_emulation") if isinstance(state, dict) else None
        novo: bool | None
        if not isinstance(bloco, dict):
            novo = None
        elif bloco.get("device_ativo") is True:
            novo = True
        elif bloco.get("bloqueio") == "sem_device":
            novo = False
        else:
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
        """Popula widgets da aba Mouse a partir de self.draft.mouse."""
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
        self._refresh_mouse_view()
        self._refresh_mouse_from_draft()


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
        """Sincroniza a aba Mouse com o bloco ``mouse_emulation`` vivo do daemon."""
        def _on_state(state: Any) -> bool:
            self._sync_mouse_mode_gate(
                mode_of_state(state if isinstance(state, dict) else None)
            )
            self._anotar_teclado_na_tela(state)
            self._anotar_mouse_virtual(state)
            me = state.get("mouse_emulation") if isinstance(state, dict) else None
            if not isinstance(me, dict):
                return False
            draft = getattr(self, "draft", None)
            if draft is None:
                return False
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
            self._sync_mouse_mode_gate(None)
            self._anotar_teclado_na_tela(None)
            self._anotar_mouse_virtual(None)
            return False

        ipc_bridge.call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=_on_err,
            # HARM-15: o state_full não cabe nos 0.25s default sob carga
            timeout_s=STATE_IPC_TIMEOUT_S,
        )


    def on_mouse_toggle_set(self, switch: Gtk.Switch, _state: Any) -> bool:
        if self._mouse_guard_refresh:
            return False
        enabled = bool(switch.get_active())
        speed = self._read_speed("mouse_speed_scale", DEFAULT_MOUSE_SPEED)
        scroll = self._read_speed("mouse_scroll_speed_scale", DEFAULT_SCROLL_SPEED)

        def _on_ok(result: Any) -> bool:
            if isinstance(result, dict) and result.get("status") != "ok":
                return _on_recusa(result)
            draft = getattr(self, "draft", None)
            if draft is not None:
                # do rodapé re-enviava `mouse.emulation.set` — religando o mouse e
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
            {
                "enabled": enabled,
                "speed": speed,
                "scroll_speed": scroll,
                "origin": "manual",
            },
            on_success=_on_ok,
            on_failure=_on_err,
        )
        return False

    def _revert_mouse_toggle(self, active: bool) -> None:
        """Reverte o switch sem reentrar no handler (BUG-MOUSE-GUI-SYNC-01 A3)."""
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
        """Envia UM parâmetro de velocidade via IPC, SEM ``enabled`` (A4)."""
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
            {param: int(value), "origin": "manual"},
            on_success=_on_ok,
            on_failure=_on_err,
        )


    def _read_speed(self, widget_id: str, default: int) -> int:
        w = self._get(widget_id)
        if w is None:
            return default
        return int(w.get_value())

    def _mouse_is_enabled(self) -> bool:
        toggle = self._get("mouse_emulation_toggle")
        return bool(toggle and toggle.get_active())

    def _refresh_mouse_view(self) -> None:
        """Pinta "o mouse virtual está pronto?" — o daemon manda, a sonda ajuda."""
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
                f'{como_atualizar_esta_instalacao()}</span>'
            )
        elif dev_exists and not dev_writable:
            # `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`. Agora dão o mesmo gesto do ramo
            label.set_markup(
                '<span foreground="#ff5555">O mouse virtual está sem permissão — '
                f'{como_atualizar_esta_instalacao()}</span>'
            )
        elif no_ar is False or not dev_exists:
            label.set_markup(
                '<span foreground="#ffb86c">O mouse virtual ainda não está pronto — '
                f'{como_atualizar_esta_instalacao()}</span>'
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

