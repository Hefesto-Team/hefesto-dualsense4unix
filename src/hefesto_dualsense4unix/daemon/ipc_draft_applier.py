"""DraftApplier — aplica `profile.apply_draft` em ordem canônica.

Extraído de `_handle_profile_apply_draft` em AUDIT-FINDING-IPC-SERVER-SPLIT-01.
Cada seção (leds, triggers, controllers, rumble, mouse, keyboard) é aplicada
de forma best-effort: falha em uma seção loga warning mas não bloqueia as
demais. A ordem é leds -> triggers -> controllers -> rumble -> mouse ->
keyboard (leds primeiro por ser menos transiente visualmente; controllers
DEPOIS das seções globais para o override por-controle vencer no alvo —
PERFIL-04).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.controller import OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


class DraftApplier:
    """Aplica as seções de `profile.apply_draft` em ordem canônica."""

    def __init__(
        self,
        controller: IController,
        store: StateStore,
        daemon: Any,
    ) -> None:
        self.controller = controller
        self.store = store
        self.daemon = daemon

    def apply(self, params: dict[str, Any]) -> list[str]:
        applied: list[str] = []
        self._apply_section(applied, params.get("leds"), "leds", self._apply_leds)
        self._apply_section(applied, params.get("triggers"), "triggers", self._apply_triggers)
        # PERFIL-04: overrides por-controle DEPOIS das seções globais — o
        # override vence no alvo (mesma precedência da ativação de perfil).
        self._apply_section(
            applied, params.get("controllers"), "controllers", self._apply_controllers
        )
        self._apply_section(applied, params.get("rumble"), "rumble", self._apply_rumble)
        self._apply_section(applied, params.get("mouse"), "mouse", self._apply_mouse)
        self._apply_section(
            applied, params.get("keyboard"), "keyboard", self._apply_keyboard
        )
        return applied

    @staticmethod
    def _apply_section(
        applied: list[str],
        raw: Any,
        section: str,
        fn: Any,
    ) -> None:
        if raw is None:
            return
        try:
            fn(raw)
            applied.append(section)
        except Exception as exc:
            logger.warning(f"apply_draft_{section}_falhou", erro=str(exc))

    @staticmethod
    def _scaled_rgb_from(leds_raw: dict[str, Any]) -> tuple[int, int, int] | None:
        """RGB da seção de leds já escalado pelo brilho (0.0-1.0); None sem cor.

        É O caminho de escala do brilho no apply_draft — os overrides
        por-controle (PERFIL-04) passam por aqui também, em paridade com a
        seção global.
        """
        rgb_raw = leds_raw.get("lightbar_rgb")
        if rgb_raw is None:
            return None
        if not isinstance(rgb_raw, list) or len(rgb_raw) != 3:
            raise ValueError("leds.lightbar_rgb deve ser lista de 3 inteiros")
        brightness_raw = leds_raw.get("lightbar_brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError):
            brightness = 1.0
        brightness = max(0.0, min(1.0, brightness))
        return (
            max(0, min(255, int(rgb_raw[0] * brightness))),
            max(0, min(255, int(rgb_raw[1] * brightness))),
            max(0, min(255, int(rgb_raw[2] * brightness))),
        )

    @staticmethod
    def _player_bits_from(
        leds_raw: dict[str, Any],
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """5 flags de player-LEDs da seção de leds; None quando ausentes."""
        player_leds_raw = leds_raw.get("player_leds")
        if player_leds_raw is None:
            return None
        if not isinstance(player_leds_raw, list) or len(player_leds_raw) != 5:
            raise ValueError("leds.player_leds deve ser lista de 5 booleanos")
        return (
            bool(player_leds_raw[0]),
            bool(player_leds_raw[1]),
            bool(player_leds_raw[2]),
            bool(player_leds_raw[3]),
            bool(player_leds_raw[4]),
        )

    @staticmethod
    def _trigger_effect_from(side_raw: Any, label: str) -> TriggerEffect:
        """Valida um lado de triggers do payload e constrói o efeito."""
        if not isinstance(side_raw, dict):
            raise ValueError(f"{label} deve ser objeto")
        mode = side_raw.get("mode")
        trigger_params = side_raw.get("params", [])
        if not isinstance(mode, str):
            raise ValueError(f"{label}.mode deve ser string")
        if not isinstance(trigger_params, list):
            raise ValueError(f"{label}.params deve ser lista")
        return build_from_name(mode, trigger_params)

    def _apply_leds(self, leds_raw: Any) -> None:
        """Aplica a seção GLOBAL de leds do draft em TODOS os controles.

        Fix do review (2026-07-16, MED): via ``apply_output_defaults`` —
        broadcast REAL que ignora o seletor de alvo e grava o
        ``_desired_default`` (mesma medicina do `ProfileManager.apply`). Os
        setters clássicos respeitavam o seletor: com um alvo selecionado
        (o estado normal do fluxo de edição por-controle), o "Aplicar" do
        rodapé gravava a seção GLOBAL no override do alvo, o default nunca
        era atualizado e o replug de outro controle reassertava estado velho.

        COR-04: ``auto_player_colors`` viaja nesta seção — propagado ao
        registro de identidade ANTES do broadcast (mesma ordem da ativação
        de perfil: ``_configure_auto_player_colors`` primeiro), para os
        reasserts subsequentes já resolverem com o toggle novo. Payload sem
        a chave (GUI antiga) = sem opinião — o estado vigente fica.
        """
        if not isinstance(leds_raw, dict):
            raise ValueError("leds deve ser objeto")
        self._configure_auto_colors(leds_raw)
        rgb = self._scaled_rgb_from(leds_raw)
        bits = self._player_bits_from(leds_raw)
        if rgb is not None or bits is not None:
            self.controller.apply_output_defaults(
                OutputSpec(led=rgb, player_leds=bits)
            )
        # COR-03 (fix de integração, 2026-07-17): converge o estado físico ao
        # RESOLVIDO por-controle após o toggle/broadcast — sem isto, religar
        # as cores automáticas pelo "Aplicar" só surtiria efeito no próximo
        # replug (e o D4 "a cor única aparece em todos" já dependia do
        # broadcast acima). Getattr defensivo (fakes seguem sem o método).
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()

    @staticmethod
    def _configure_auto_colors(leds_raw: dict[str, Any]) -> None:
        """COR-04: propaga o toggle do automático ao registro de identidade.

        Espelho do ``ProfileManager._configure_auto_player_colors`` para o
        caminho ``profile.apply_draft`` (o "Aplicar" do rodapé e o botão
        "Aplicar no controle" em "Todos") — sem isto o toggle editado na GUI
        só valeria na PRÓXIMA ativação de perfil, e a semântica D4 ("a cor
        única aparece em todos") ficaria quebrada ao vivo. O brilho
        acompanha quando presente (a paleta automática respeita o brilho do
        perfil — D11). Best-effort na mesma medida do manager: falha de
        import/configure loga warning e NÃO derruba a aplicação da cor.
        """
        raw = leds_raw.get("auto_player_colors")
        if raw is None:
            return
        if not isinstance(raw, bool):
            raise ValueError("leds.auto_player_colors deve ser booleano")
        brightness: float | None = None
        brightness_raw = leds_raw.get("lightbar_brightness")
        if brightness_raw is not None:
            try:
                brightness = max(0.0, min(1.0, float(brightness_raw)))
            except (TypeError, ValueError):
                brightness = None
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
            )

            get_identity_registry().configure(enabled=raw, brightness=brightness)
        except Exception as exc:
            logger.warning("apply_draft_auto_colors_falhou", erro=str(exc))

    def _apply_triggers(self, triggers_raw: Any) -> None:
        """Aplica a seção GLOBAL de gatilhos em TODOS os controles.

        Broadcast real via ``apply_output_defaults`` — mesma justificativa
        de ``_apply_leds`` (fix do review 2026-07-16, MED).
        """
        if not isinstance(triggers_raw, dict):
            raise ValueError("triggers deve ser objeto")
        effects: dict[str, TriggerEffect] = {}
        for side in ("left", "right"):
            side_raw = triggers_raw.get(side)
            if side_raw is None:
                continue
            effects[side] = self._trigger_effect_from(side_raw, f"triggers.{side}")
        if effects:
            self.controller.apply_output_defaults(
                OutputSpec(
                    trigger_left=effects.get("left"),
                    trigger_right=effects.get("right"),
                )
            )
        self.store.mark_manual_trigger_active()

    def _apply_controllers(self, raw: Any) -> None:
        """Aplica os overrides POR CONTROLE do draft (PERFIL-04).

        Cada entrada ``{uniq: {leds?, triggers?}}`` vira um ``OutputSpec``
        aplicado via ``apply_output_for`` — a API por-uniq do PERFIL-01
        (alvo no parâmetro, nunca o seletor global). O brilho escala o RGB
        pelo MESMO caminho da seção global (``_scaled_rgb_from``). Backend
        sem estado por-controle (FakeController) herda o no-op seguro do
        ``IController``; controle desconectado fica registrado no mapa em
        memória do backend real (o hotplug o aplica quando chegar).

        A seção presente SUBSTITUI o mapa inteiro de overrides
        (``reset_output_overrides``) ANTES de reaplicar — o MESMO ciclo de
        vida da ativação de perfil (``ProfileManager.apply``). Sem isto, um
        ajuste especial que a usuária TIROU de um controle na GUI (ele voltou
        a "Todos" e sumiu do payload) seguiria vivo no controle até a próxima
        troca de perfil, e o "Aplicar" mostraria a cor/gatilho antigo.
        """
        if not isinstance(raw, dict):
            raise ValueError("controllers deve ser objeto")
        specs: dict[str, OutputSpec] = {}
        for uniq, entry in raw.items():
            if not isinstance(entry, dict):
                raise ValueError(f"controllers[{uniq!r}] deve ser objeto")
            spec = self._controller_override_spec(entry, str(uniq))
            if spec is not None:
                specs[str(uniq)] = spec
        # Getattr defensivo: stubs/fakes de teste sem o método seguem (a base
        # ``IController`` e os backends reais o têm — no-op sem estado por-uniq).
        reset = getattr(self.controller, "reset_output_overrides", None)
        if callable(reset):
            reset(specs or None)
        for uniq, spec in specs.items():
            self.controller.apply_output_for(uniq, spec)

    def _controller_override_spec(
        self, entry: dict[str, Any], uniq: str
    ) -> OutputSpec | None:
        """Converte uma entrada de override em ``OutputSpec``; None se vazia."""
        led: tuple[int, int, int] | None = None
        player: tuple[bool, bool, bool, bool, bool] | None = None
        leds_raw = entry.get("leds")
        if leds_raw is not None:
            if not isinstance(leds_raw, dict):
                raise ValueError(f"controllers[{uniq!r}].leds deve ser objeto")
            led = self._scaled_rgb_from(leds_raw)
            player = self._player_bits_from(leds_raw)
        trigger_left: TriggerEffect | None = None
        trigger_right: TriggerEffect | None = None
        triggers_raw = entry.get("triggers")
        if triggers_raw is not None:
            if not isinstance(triggers_raw, dict):
                raise ValueError(f"controllers[{uniq!r}].triggers deve ser objeto")
            base = f"controllers[{uniq!r}].triggers"
            left_raw = triggers_raw.get("left")
            if left_raw is not None:
                trigger_left = self._trigger_effect_from(left_raw, f"{base}.left")
            right_raw = triggers_raw.get("right")
            if right_raw is not None:
                trigger_right = self._trigger_effect_from(right_raw, f"{base}.right")
        if led is None and player is None and trigger_left is None and trigger_right is None:
            return None
        return OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player,
        )

    def _apply_rumble(self, rumble_raw: Any) -> None:
        if not isinstance(rumble_raw, dict):
            raise ValueError("rumble deve ser objeto")
        weak = rumble_raw.get("weak", 0)
        strong = rumble_raw.get("strong", 0)
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.weak e rumble.strong devem ser inteiros")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        # BUG-RUMBLE-APPLY-KILLS-GAME-01: (0,0) num "Aplicar" significa "não force
        # rumble" (passthrough), NÃO "force silêncio". Antes, rumble_active=(0,0)
        # fazia o poll loop (_reassert_rumble) reescrever set_rumble(0,0) a cada
        # tick, SOBRESCREVENDO o rumble do JOGO — qualquer "Aplicar" com sliders em
        # 0 (o default) matava a vibração in-game. Passthrough = rumble_active None
        # (o poll loop deixa o jogo controlar; idêntico a rumble.passthrough);
        # aplica (0,0) uma vez para soltar um rumble contínuo anterior. "Parar"
        # (rumble.stop) continua fixando (0,0) como silêncio deliberado.
        if weak == 0 and strong == 0:
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
            self.controller.set_rumble(weak=0, strong=0)
            return
        # AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01:
        # Persiste valores brutos para que o poll loop (_reassert_rumble)
        # continue reaplicando a política a cada tick. Antes de enviar ao
        # hardware, escala via apply_rumble_policy — mesmo comportamento
        # canônico de _handle_rumble_set.
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)

    def _apply_mouse(self, mouse_raw: Any) -> None:
        """Aplica a seção mouse do draft.

        HARM-05: sem ``enabled`` cai na rota speed-only (``set_mouse_speed``) —
        a mesma que o handler ``mouse.emulation.set`` já oferece (A4): atualiza
        as velocidades sem start/stop e sem persistir o flag. É por aqui que o
        "Aplicar" do rodapé entra, e ele não pode mudar o modo do sistema: o
        dono do liga/desliga é a aba Início. Exigir ``enabled`` aqui não
        protegia nada — só fazia a edição de velocidade morrer em silêncio
        (``_apply_section`` engole a exceção como "seção falhou").
        """
        if not isinstance(mouse_raw, dict):
            raise ValueError("mouse deve ser objeto")
        enabled = mouse_raw.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("mouse.enabled deve ser booleano ou omitido")
        speed = mouse_raw.get("speed")
        scroll_speed = mouse_raw.get("scroll_speed")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")
        if enabled is None:
            self.daemon.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            return
        self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
        )

    def _apply_keyboard(self, keyboard_raw: Any) -> None:
        """Aplica os key_bindings editados ao device de teclado virtual vivo.

        BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: antes o único caminho que empurrava
        bindings ao device era ``profile.switch`` (que recarrega do DISCO); o
        rodapé "Aplicar" (``profile.apply_draft``) ignorava o teclado. Agora a
        seção ``keyboard`` resolve o inner ``key_bindings`` (None →
        DEFAULT_BUTTON_BINDINGS; ``{}`` → silêncio; dict → override) e chama
        ``set_bindings`` no device vivo, sem reativar/regravar o perfil.

        No-op seguro quando não há device de teclado (CLI/headless, emulação de
        teclado desligada, ou gamepad ligado — que assume o ramo do gamepad e o
        teclado nunca despacha): os bindings entram em vigor quando o teclado
        virtual subir.
        """
        if not isinstance(keyboard_raw, dict):
            raise ValueError("keyboard deve ser objeto")
        if "key_bindings" not in keyboard_raw:
            return
        device = getattr(self.daemon, "_keyboard_device", None) if self.daemon else None
        if device is None:
            return
        raw = keyboard_raw.get("key_bindings")
        if raw is not None and not isinstance(raw, dict):
            raise ValueError("keyboard.key_bindings deve ser objeto ou null")
        from hefesto_dualsense4unix.profiles.manager import resolve_key_bindings

        device.set_bindings(resolve_key_bindings(raw))


__all__ = ["DraftApplier"]
