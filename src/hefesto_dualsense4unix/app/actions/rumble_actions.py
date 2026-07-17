"""Aba Rumble: intensidade global (Economia/Balanceado/Máximo/Auto) + Testar motores.

FEAT-RUMBLE-POLICY-01: aba reestruturada em 2 cards:
  1. "Intensidade da vibração" — 4 GtkToggleButton agrupados + slider + label Auto.
  2. "Testar motores" — sliders de vibração leve/forte + botões Testar/Aplicar/Parar.

LEIGO-06: "política", "rumble", "weak"/"strong" e "throttle" saíram da TELA —
continuam sendo os nomes do IPC e do schema (`rumble.policy`, `policy="max"`),
que este módulo traduz na fronteira.

Política define multiplicador global aplicado pelo daemon sobre todo rumble,
inclusive passthrough de jogo (XInput virtual). Slider de intensidade ajusta
"custom" em 0-200% (mapeamento valor/100 nos dois sentidos).

HARM-19: o teto tem UM dono — ``profiles.schema.RUMBLE_CUSTOM_MULT_MAX``. Eram
três (2.0 no schema, 1.0 no handler ``rumble.policy_custom``, 200% no slider), e
de 101% em diante a usuária levava um erro de validação que esta aba nem
mostrava. Mexeu no teto? Mexa no schema — este slider é ``mult * 100``.

FEAT-RUMBLE-POLICY-PROFILE-01: cada escolha de política da usuária também é
gravada em ``self.draft.rumble`` — o "Salvar Perfil" do rodapé persiste no
perfil exatamente o que a aba mostra (aplicada de volta na ativação).
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import STATE_IPC_TIMEOUT_S
from hefesto_dualsense4unix.app.ipc_bridge import (
    call_async,
    rumble_passthrough,
    rumble_policy_custom,
    rumble_policy_set_checked,
    rumble_set,
    rumble_stop,
)

# Mapeamento política -> mult canônico (para mover slider ao clicar preset).
_POLICY_MULT: dict[str, float] = {
    "economia": 0.3,
    "balanceado": 0.7,
    "max": 1.0,
    "auto": 1.0,  # Slider vai para 100% no auto (indicativo; não é custom).
}

#: LEIGO-06: o toast ecoava a CHAVE interna ("max", "economia") — palavra
#: diferente da que a usuária acabou de clicar no botão ("Máximo"). Os rótulos
#: são os do glade (main.glade, card "Intensidade da vibração").
_POLICY_LABEL: dict[str, str] = {
    "economia": "Economia",
    "balanceado": "Balanceado",
    "max": "Máximo",
    "auto": "Auto",
}

_LABEL_AUTO = (
    "Modo Auto: ajusta intensidade conforme a bateria do controle.\n"
    "Bateria >50%: 100% (Máximo).  20-50%: 70% (Balanceado).  <20%: 30% (Economia).\n"
    "Transições com debounce de 5 segundos para evitar oscilação."
)

#: RUM-01: o texto dos toasts/estado mandava clicar "Devolver ao jogo" — botão
#: que NÃO existe. O botão real (main.glade) tem este rótulo; um único dono aqui
#: impede a dessincronia de voltar. Ao mexer no rótulo do glade, mexa aqui.
_BTN_GIVE_BACK_TO_GAME = "Deixar o jogo controlar a vibração"

#: JARG-01/LB-02: "daemon offline?" vaza jargão + palpite. O resto do app já
#: fala "ligue na aba Sistema" — a fronteira da GUI traduz aqui também.
_MSG_HEFESTO_OFF = "não consegui — o Hefesto pode estar desligado (ligue na aba Sistema)."


class RumbleActionsMixin(WidgetAccessMixin):
    """Controla a aba Rumble."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _rumble_guard_refresh: bool = False
    # Política corrente (espelhada localmente para guard de toggle).
    _rumble_policy: str = "balanceado"

    # --- instalação ---

    def install_rumble_tab(self) -> None:
        """Inicializa estado da aba Rumble a partir de state_full ou defaults.

        Configura o toggle ativo conforme política e atualiza slider.
        """
        self._sync_policy_from_state()

    def _sync_policy_from_state(self, *, indicar_sem_opiniao: bool = False) -> None:
        """Lê política atual via state_full e sincroniza widgets.

        BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01: o estado do daemon é SÓ exibição —
        nunca é gravado no draft (senão todo perfil ganharia opinião de
        política só de abrir a aba). Com ``indicar_sem_opiniao``, avisa na
        statusbar que o perfil não tem opinião (o "Salvar Perfil" do rodapé
        não vai persistir política até a usuária escolher uma).
        """
        def _on_state(result: Any) -> bool:
            if isinstance(result, dict):
                policy = result.get("rumble_policy", "balanceado")
                custom_mult = result.get("rumble_policy_custom_mult", 0.7)
            else:
                policy = "balanceado"
                custom_mult = 0.7
            self._apply_policy_to_widgets(str(policy), float(custom_mult))
            # Feature #4 (auditoria): consome rumble_passthrough / rumble_active /
            # rumble_ff do state_full — antes nada na GUI mostrava se a vibração
            # estava DEVOLVIDA ao jogo ou FIXA, nem se o jogo pediu FF.
            self._update_rumble_state_label(result if isinstance(result, dict) else {})
            if indicar_sem_opiniao:
                self._toast_rumble(
                    "Política exibida = estado atual do daemon; o perfil não "
                    "tem opinião (escolha uma política para salvá-la no perfil)."
                )
            return False

        def _on_err(_exc: Exception) -> bool:
            # Sem resposta, a aba NÃO SABE a política — e afirmar uma é mentir.
            # Pintava "Balanceado / 70%" por cima da política real (repro: daemon
            # em "max", state_full passando dos 250ms durante um hotplug), e o
            # que ela via passava a divergir do que o controle faz.
            return False

        call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=_on_err,
            # HARM-15: o daemon monta o state_full varrendo os controles; sob
            # carga (hotplug, co-op subindo) não cabe nos 0.25s default.
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    def _apply_policy_to_widgets(self, policy: str, custom_mult: float) -> None:
        """Reflete política e mult nos widgets sem disparar callbacks de sinal."""
        if self._rumble_guard_refresh:
            return
        self._rumble_guard_refresh = True
        self._rumble_policy = policy
        try:
            # Ativa o toggle correto.
            btn_id = {
                "economia": "rumble_policy_economia",
                "balanceado": "rumble_policy_balanceado",
                "max": "rumble_policy_max",
                "auto": "rumble_policy_auto",
                "custom": None,
            }.get(policy)

            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(pid == btn_id)

            # Slider de intensidade.
            slider: Gtk.Scale = self._get("rumble_policy_slider")
            if slider is not None:
                if policy == "custom":
                    slider.set_value(custom_mult * 100.0)
                elif policy in _POLICY_MULT:
                    slider.set_value(_POLICY_MULT[policy] * 100.0)

            # Label Auto: visível só em modo auto.
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(policy == "auto")
        finally:
            self._rumble_guard_refresh = False

    # --- handlers dos toggles de política ---

    def on_rumble_policy_economia(self, _btn: Gtk.ToggleButton) -> None:
        # A1: NÃO curto-circuitar em get_active()==False. Os 4 toggles são
        # GtkToggleButton independentes: clicar num já-ativo o desmarca
        # (get_active()==False), e o antigo `not btn.get_active(): return`
        # virava clique morto (nenhuma política afundada + IPC não reenviado).
        # Agora todo clique cai em _set_policy, que re-afirma o botão certo
        # (desmarcando os irmãos) e reenvia o IPC — sempre exatamente 1 afundado.
        if self._rumble_guard_refresh:
            return
        self._set_policy("economia")

    def on_rumble_policy_balanceado(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("balanceado")

    def on_rumble_policy_max(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("max")

    def on_rumble_policy_auto(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("auto")

    def _set_policy(self, policy: str) -> None:
        """Envia política ao daemon e atualiza slider para valor canônico."""
        self._rumble_policy = policy
        slider: Gtk.Scale = self._get("rumble_policy_slider")
        # A1: exclusão mútua ANTES do IPC — desmarca os irmãos e re-afirma o
        # botão certo (mesmo quando o clique num já-ativo o desmarcou), sob guard
        # para os "toggled" reentrantes dos irmãos não reentrarem nos handlers de
        # política. Junto, move o slider para o valor canônico (feedback visual).
        self._rumble_guard_refresh = True
        try:
            self._activate_policy_toggle(policy)
            if slider is not None:
                pct = int(_POLICY_MULT.get(policy, 0.7) * 100)
                slider.set_value(float(pct))
        finally:
            self._rumble_guard_refresh = False

        # Label Auto.
        lbl: Gtk.Label = self._get("rumble_policy_auto_label")
        if lbl is not None:
            lbl.set_visible(policy == "auto")

        # FEAT-RUMBLE-POLICY-PROFILE-01: além do daemon vivo, grava a escolha
        # no draft — o "Salvar Perfil" do rodapé persiste a política que a
        # usuária vê. Preset zera custom_mult (o valor só faz sentido em
        # policy="custom"; o schema do perfil rejeita a combinação).
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_rumble = draft.rumble.model_copy(
                update={"policy": policy, "custom_mult": None}
            )
            self.draft = draft.model_copy(update={"rumble": new_rumble})

        # HARM-19: recusa do daemon VIVO (motivo preenchido) não pode virar
        # acusação de daemon morto — é o tratamento que os gatilhos já têm.
        ok, motivo = rumble_policy_set_checked(policy, timeout=STATE_IPC_TIMEOUT_S)
        if ok:
            texto = f"Intensidade da vibração: {_POLICY_LABEL.get(policy, policy)}"
        elif motivo:
            texto = f"O Hefesto não aceitou essa intensidade: {motivo}"
        else:
            texto = "O Hefesto não está rodando — ligue na aba Sistema."
        self._toast_rumble(texto)

    # --- handler do slider de intensidade ---

    def on_rumble_policy_slider_changed(self, slider: Gtk.Scale) -> None:
        """Slider movido: política vira "custom" com mult = valor/100."""
        if self._rumble_guard_refresh:
            return
        mult = slider.get_value() / 100.0
        # Se o mult coincide exatamente com um preset, escolhê-lo.
        for policy, canon_mult in _POLICY_MULT.items():
            if policy == "auto":
                continue
            if abs(mult - canon_mult) < 0.005:
                if self._rumble_policy != policy:
                    self._rumble_guard_refresh = True
                    try:
                        self._activate_policy_toggle(policy)
                    finally:
                        self._rumble_guard_refresh = False
                    self._set_policy(policy)
                return

        # Mult não é preset: modo custom.
        self._rumble_guard_refresh = True
        try:
            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(False)
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(False)
        finally:
            self._rumble_guard_refresh = False

        self._rumble_policy = "custom"
        # FEAT-RUMBLE-POLICY-PROFILE-01: persiste o custom no draft (mesma
        # razão do preset em `_set_policy` — o rodapé salva o que ela vê).
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_rumble = draft.rumble.model_copy(
                update={"policy": "custom", "custom_mult": mult}
            )
            self.draft = draft.model_copy(update={"rumble": new_rumble})
        rumble_policy_custom(mult)

    def _activate_policy_toggle(self, policy: str) -> None:
        """Ativa o toggle correspondente à política (sem guard)."""
        btn_map = {
            "economia": "rumble_policy_economia",
            "balanceado": "rumble_policy_balanceado",
            "max": "rumble_policy_max",
            "auto": "rumble_policy_auto",
        }
        target_id = btn_map.get(policy)
        for pid in btn_map.values():
            btn: Gtk.ToggleButton = self._get(pid)
            if btn is not None:
                btn.set_active(pid == target_id)

    # --- handlers de teste de motores ---

    # M6 (auditoria): id do timer do teste de 500ms em curso (GLib source), para
    # cancelá-lo se a usuária clicar Parar/Aplicar/Devolver ou testar de novo
    # dentro da janela — senão o `_rumble_test_stop` pendente desfazia a ação.
    _rumble_test_source: int | None = None

    def _cancel_rumble_test_timer(self) -> None:
        src = self._rumble_test_source
        if src is not None:
            with contextlib.suppress(Exception):
                GLib.source_remove(src)
            self._rumble_test_source = None

    def on_rumble_apply(self, _btn: Gtk.Button) -> None:
        self._cancel_rumble_test_timer()
        weak, strong = self._read_scales()
        # Persiste no draft antes de enviar via IPC.
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_rumble = draft.rumble.model_copy(update={"weak": weak, "strong": strong})
            self.draft = draft.model_copy(update={"rumble": new_rumble})
        ok = rumble_set(weak, strong)
        self._toast_rumble(
            f"Vibração travada (fraca={weak}, forte={strong}) — enquanto travada o "
            f"jogo NÃO controla a vibração; clique “{_BTN_GIVE_BACK_TO_GAME}” "
            "para jogar"
            if ok
            else f"Vibração {_MSG_HEFESTO_OFF}"
        )

    def on_rumble_test_500ms(self, _btn: Gtk.Button) -> None:
        # Cancela um teste anterior ainda em curso antes de armar o novo.
        self._cancel_rumble_test_timer()
        weak, strong = self._read_scales()
        if weak == 0 and strong == 0:
            weak = 160
            strong = 220
            self._set_scales(weak, strong)
        ok = rumble_set(weak, strong)
        if not ok:
            self._toast_rumble(f"Teste {_MSG_HEFESTO_OFF}")
            return
        self._toast_rumble(f"Testando por meio segundo (fraca={weak}, forte={strong})")
        self._rumble_test_source = GLib.timeout_add(500, self._rumble_test_stop)

    def on_rumble_stop(self, _btn: Gtk.Button) -> None:
        """Para rumble via rumble.stop (BUG-RUMBLE-APPLY-IGNORED-01).

        Usa rumble_stop() em vez de rumble_set(0, 0) para que o daemon
        persista (0, 0) e o poll loop re-afirme silêncio continuamente,
        evitando que write HID residual reative os motores.
        """
        self._cancel_rumble_test_timer()
        self._set_scales(0, 0)
        rumble_stop()
        self._toast_rumble(
            f"Vibração parada (travada em silêncio) — clique "
            f"“{_BTN_GIVE_BACK_TO_GAME}” para o jogo voltar a controlar a vibração"
        )

    def on_rumble_passthrough(self, _btn: Gtk.Button) -> None:
        """Devolve o controle da vibração ao JOGO (FEAT-RUMBLE-PASSTHROUGH-GUI-01).

        Chama rumble.passthrough(True): o daemon zera rumble_active (None) e o poll
        loop PARA de re-afirmar (0,0), deixando o jogo controlar os motores. É o
        antídoto do 'Parar' (que fixa silêncio). Sem este botão, depois de 'Parar'
        só dava pra devolver o rumble pela CLI — a auditoria flagou a lacuna de
        auto-suficiência.
        """
        self._cancel_rumble_test_timer()
        self._set_scales(0, 0)
        ok = rumble_passthrough(True)
        self._toast_rumble(
            "Pronto — agora o jogo controla a vibração"
            if ok
            else f"Vibração {_MSG_HEFESTO_OFF}"
        )

    # --- refresh do draft ---

    def _refresh_rumble_from_draft(self) -> None:
        """Popula widgets da aba Rumble a partir de self.draft.rumble e state_full.

        Protegido por _rumble_guard_refresh para não disparar handlers de sinal
        durante a atualização programática dos sliders.
        """
        if self._rumble_guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._rumble_guard_refresh = True
        try:
            rumble = draft.rumble
            weak_scale: Gtk.Scale = self._get("rumble_weak_scale")
            strong_scale: Gtk.Scale = self._get("rumble_strong_scale")
            if weak_scale is not None:
                weak_scale.set_value(float(rumble.weak))
            if strong_scale is not None:
                strong_scale.set_value(float(rumble.strong))
        finally:
            self._rumble_guard_refresh = False
        # BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01: a política destacada na tela tem
        # de ser a MESMA que o "Salvar Perfil" do rodapé grava (draft.policy).
        if rumble.policy is not None:
            # Perfil tem opinião (ou a usuária já tocou): widgets refletem o
            # DRAFT — não o daemon, que pode estar noutra política (CLI/applet).
            mult = (
                rumble.custom_mult
                if rumble.custom_mult is not None
                else _POLICY_MULT.get(rumble.policy, 0.7)
            )
            self._apply_policy_to_widgets(rumble.policy, mult)
            # Feature #4: mesmo com política do perfil, o indicador de estado da
            # vibração (jogo controla / fixo + FF do jogo) vem do daemon VIVO.
            self._refresh_rumble_state_label_async()
        else:
            # Perfil SEM opinião: exibe o estado vivo do daemon como referência
            # (async — não bloqueia GTK), com indicação na statusbar e SEM
            # gravar o valor do daemon no draft. (Já atualiza o indicador.)
            self._sync_policy_from_state(indicar_sem_opiniao=True)

    def _refresh_rumble_state_label_async(self) -> None:
        """Atualiza só o indicador de estado da vibração via state_full (async)."""
        def _on_state(result: Any) -> bool:
            self._update_rumble_state_label(result if isinstance(result, dict) else {})
            return False

        call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=lambda _e: False,
            # HARM-15: mesma leitura, mesma folga (o indicador some por um tick
            # em vez de mostrar estado inventado).
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    # --- helpers ---

    def _read_scales(self) -> tuple[int, int]:
        # B1-rumble: None-guard — _get pode devolver None se o widget não existe
        # no builder (evita AttributeError ao desreferenciar).
        w = self._get("rumble_weak_scale")
        s = self._get("rumble_strong_scale")
        weak = int(w.get_value()) if w is not None else 0
        strong = int(s.get_value()) if s is not None else 0
        return weak, strong

    def _set_scales(self, weak: int, strong: int) -> None:
        # B1-rumble: None-guard antes de desreferenciar cada scale.
        w = self._get("rumble_weak_scale")
        if w is not None:
            w.set_value(weak)
        s = self._get("rumble_strong_scale")
        if s is not None:
            s.set_value(strong)

    def _rumble_test_stop(self) -> bool:
        # SPRINT-GAME-RUMBLE-01: fim do teste = zera os motores E DEVOLVE o
        # rumble ao jogo (passthrough). Antes fixava (0, 0), o que deixava o
        # rumble "travado em silêncio" e o FF do jogo IGNORADO (apply_game_rumble
        # só passa com rumble_active is None) até a usuária clicar "Devolver ao
        # jogo" na mão — era a origem do "testei os motores e aí o jogo não
        # vibra mais". rumble_stop() zera o motor primeiro; passthrough solta.
        self._rumble_test_source = None  # o timer disparou; não há o que cancelar
        rumble_stop()
        rumble_passthrough(True)
        self._set_scales(0, 0)
        self._toast_rumble("Teste encerrado — vibração devolvida ao jogo")
        return False

    def _update_rumble_state_label(self, state: dict[str, Any]) -> None:
        """Feature #4: mostra o estado vivo da vibração na aba Rumble.

        `rumble_passthrough` True = o JOGO controla (o esperado para jogar);
        False = FIXO pela GUI (o FF do jogo é ignorado). `rumble_ff.plays` = quantas
        vezes o jogo pediu vibração no gamepad virtual — em 0 durante o jogo indica
        que o jogo não está enxergando o vpad (ex.: máscara errada)."""
        label = self._get("rumble_state_label")
        if label is None:
            return
        passthrough = state.get("rumble_passthrough")
        active = state.get("rumble_active")
        ff = state.get("rumble_ff") if isinstance(state.get("rumble_ff"), dict) else {}
        plays = ff.get("plays", 0) if isinstance(ff, dict) else 0
        if passthrough is True:
            estado = '<span foreground="#2d8">o JOGO controla a vibração</span>'
        elif isinstance(active, list) and len(active) == 2:
            if active == [0, 0]:
                estado = (
                    '<span foreground="#e0a020">travada em silêncio '
                    f'(clique “{_BTN_GIVE_BACK_TO_GAME}”)</span>'
                )
            else:
                estado = (
                    f'<span foreground="#e0a020">travada em fraca={active[0]}, '
                    f'forte={active[1]} (clique “{_BTN_GIVE_BACK_TO_GAME}” '
                    "para jogar)</span>"
                )
        else:
            estado = "—"
        plays_txt = ""
        if isinstance(plays, int) and not isinstance(plays, bool) and plays > 0:
            plays_txt = f"  ·  o jogo pediu vibração {plays}x"
        label.set_markup(f"Estado da vibração: {estado}{plays_txt}")

    def _toast_rumble(self, msg: str) -> None:
        self._status_toast("rumble", msg)
