"""DraftApplier — aplica `profile.apply_draft` em ordem canônica."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.controller import OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
    apply_rumble_policy,
    uniq_do_alvo_de_output,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


def _brilho_de(cru: Any) -> float | None:
    """O brilho 0,0-1,0 de um campo do rascunho, ou `None` quando não é número."""
    if cru is None or isinstance(cru, bool):
        return None
    try:
        return max(0.0, min(1.0, float(cru)))
    except (TypeError, ValueError):
        return None


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
        self.failed: dict[str, str] = {}
        self._brilho_do_rascunho: float | None = None
        self._cor_do_rascunho: Any = None
        self._em_economia: frozenset[str] = frozenset()
        self._procedencias_da_economia: dict[str, object] = {}
        self._o_rascunho_tem_o_mapa = False
        self._controles_do_rascunho: Any = None

    def apply(self, params: dict[str, Any]) -> list[str]:
        applied: list[str] = []
        self.failed = {}
        self._o_rascunho_tem_o_mapa = isinstance(params.get("controllers"), dict)
        params = self._com_o_teto_da_economia(params)
        self._controles_do_rascunho = params.get("controllers")
        leds_raw = params.get("leds")
        self._brilho_do_rascunho = (
            _brilho_de(leds_raw.get("lightbar_brightness"))
            if isinstance(leds_raw, dict)
            else None
        )
        self._cor_do_rascunho = (
            leds_raw.get("lightbar_rgb") if isinstance(leds_raw, dict) else None
        )
        self._apply_section(applied, params.get("leds"), "leds", self._apply_leds)
        self._apply_section(applied, params.get("triggers"), "triggers", self._apply_triggers)
        self._apply_section(
            applied, params.get("controllers"), "controllers", self._apply_controllers
        )
        self._apply_section(applied, params.get("rumble"), "rumble", self._apply_rumble)
        self._apply_section(applied, params.get("mouse"), "mouse", self._apply_mouse)
        self._apply_section(
            applied, params.get("keyboard"), "keyboard", self._apply_keyboard
        )
        self._apply_section(applied, params.get("mic"), "mic", self._apply_mic)
        self._apply_section(applied, params.get("speaker"), "speaker", self._apply_speaker)
        return applied

    def _apply_section(
        self,
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
            motivo = str(exc) or type(exc).__name__
            self.failed[section] = motivo[:120]

    @staticmethod
    def _scaled_rgb_from(leds_raw: dict[str, Any]) -> tuple[int, int, int] | None:
        """RGB da seção de leds já escalado pelo brilho (0.0-1.0); None sem cor."""
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
        from hefesto_dualsense4unix.core.led_control import LedSettings

        cru = tuple(max(0, min(255, int(canal))) for canal in rgb_raw)
        return LedSettings(lightbar=(cru[0], cru[1], cru[2])).apply_brightness(
            brightness
        ).lightbar

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
        """Aplica a seção GLOBAL de leds do draft em TODOS os controles."""
        if not isinstance(leds_raw, dict):
            raise ValueError("leds deve ser objeto")
        self._configure_auto_colors(leds_raw)
        rgb = self._scaled_rgb_from(leds_raw)
        bits = self._player_bits_from(leds_raw)
        luzes = self._o_todos_das_luzes(leds_raw)
        if rgb is not None or bits is not None or luzes is not None:
            self.controller.apply_output_defaults(
                OutputSpec(led=rgb, player_leds=bits, player_led_brightness=luzes)
            )
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()

    def _o_todos_das_luzes(self, leds_raw: dict[str, Any]) -> int | None:
        """O degrau do «Todos» das luzes de número, quando ele pode ir a todos."""
        palavra = leds_raw.get("player_led_brightness")
        if palavra is None:
            return None
        from hefesto_dualsense4unix.core.led_control import degrau_do_brilho_das_luzes

        degrau = degrau_do_brilho_das_luzes(str(palavra))
        controles = self._controles_do_rascunho
        for entrada in (controles if isinstance(controles, dict) else {}).values():
            leds = entrada.get("leds") if isinstance(entrada, dict) else None
            propria = leds.get("player_led_brightness") if isinstance(leds, dict) else None
            if propria is not None and str(propria) != str(palavra):
                return None
        return degrau

    @staticmethod
    def _configure_auto_colors(leds_raw: dict[str, Any]) -> None:
        """COR-04: propaga o toggle do automático ao registro de identidade."""
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
        """Aplica a seção GLOBAL de gatilhos em TODOS os controles."""
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

    def _apply_controllers(self, raw: Any) -> None:
        """Aplica os overrides POR CONTROLE do draft (PERFIL-04)."""
        if not isinstance(raw, dict):
            raise ValueError("controllers deve ser objeto")
        specs: dict[str, OutputSpec] = {}
        for uniq, entry in raw.items():
            if not isinstance(entry, dict):
                raise ValueError(f"controllers[{uniq!r}] deve ser objeto")
            spec = self._controller_override_spec(entry, str(uniq))
            if spec is not None:
                specs[str(uniq)] = spec
        da_economia = {u: s for u, s in specs.items() if u in self._em_economia}
        da_mao = {u: s for u, s in specs.items() if u not in da_economia}
        reset = getattr(self.controller, "reset_output_overrides", None)
        if callable(reset) and self._o_rascunho_tem_o_mapa:
            reset(da_mao or None)
        for uniq, spec in da_mao.items():
            self._aplicar_com_o_brilho_da_cor(uniq, spec, raw.get(uniq))
        self._publicar_escalas_de_brilho(raw)
        self._publicar_a_economia(da_economia)
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        self._publicar_escalas_de_vibracao(raw)
        self._escrever_alto_falantes_por_unidade(raw)

    def _aplicar_com_o_brilho_da_cor(
        self, uniq: str, spec: OutputSpec, entrada: Any
    ) -> None:
        """`apply_output_for` com o brilho em que a cor do override foi escalada.

        A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026: o backend guarda o brilho
        ao lado da cor da camada da usuária, e é o que o `state_full` publica
        como `brilho_da_barra` — a aba Iluminação pergunta ao daemon vivo, e a
        cor do «Aplicar» atravessa a troca automática de perfil como a do
        `led.set`. O brilho é o MESMO que `_scaled_rgb_from` usou. Backend sem o
        parâmetro recebe a cor igual, sem o carimbo.
        """
        aplicar: Any = self.controller.apply_output_for
        leds_raw = entrada.get("leds") if isinstance(entrada, dict) else None
        if spec.led is None or not isinstance(leds_raw, dict):
            aplicar(uniq, spec)
            return
        brilho = _brilho_de(leds_raw.get("lightbar_brightness", 1.0))
        try:
            aplicar(uniq, spec, brilho_da_cor=1.0 if brilho is None else brilho)
        except TypeError:
            aplicar(uniq, spec)

    def _publicar_escalas_de_brilho(self, raw: dict[str, Any]) -> None:
        """Publica o brilho por controle como FATOR, como a ativação (R-20 item 2)."""
        escalar = getattr(self.controller, "set_led_scales", None)
        base = self._brilho_do_rascunho
        if not callable(escalar) or base is None or base <= 0.0:
            return
        escalas: dict[str, float] = {}
        for uniq, entry in raw.items():
            leds_raw = entry.get("leds") if isinstance(entry, dict) else None
            if not isinstance(leds_raw, dict):
                continue
            brilho = _brilho_de(leds_raw.get("lightbar_brightness"))
            if brilho is None:
                continue
            fator = brilho / base
            if fator != 1.0:
                escalas[str(uniq)] = fator
        try:
            escalar(
                escalas or None,
                brilho_do_perfil=base,
                cor_do_perfil=self._cor_do_rascunho,
            )
        except TypeError:
            escalar(escalas or None)

    def _publicar_escalas_de_vibracao(self, raw: dict[str, Any]) -> None:
        """Publica a escala de vibração por peça no backend (POR-UNIDADE-01)."""
        from hefesto_dualsense4unix.profiles.manager import _mult_da_politica

        escalar = getattr(self.controller, "set_rumble_scales", None)
        if not callable(escalar):
            return
        base = _mult_da_politica(*self._politica_viva())
        escalas: dict[str, float] = {}
        for uniq, entry in raw.items():
            rumble_raw = entry.get("rumble") if isinstance(entry, dict) else None
            if not isinstance(rumble_raw, dict):
                continue
            mult = _mult_da_politica(
                rumble_raw.get("policy"), rumble_raw.get("custom_mult")
            )
            if mult is None or base is None or base <= 0.0:
                continue
            fator = mult / base
            if fator != 1.0:
                escalas[str(uniq)] = fator
        escalar(escalas or None)

    def _escrever_alto_falantes_por_unidade(self, raw: dict[str, Any]) -> None:
        """Aplica o alto-falante de cada peça (POR-UNIDADE-01)."""
        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            return
        for uniq, entry in raw.items():
            speaker_raw = entry.get("speaker") if isinstance(entry, dict) else None
            if not isinstance(speaker_raw, dict):
                continue
            volume = speaker_raw.get("volume")
            if not isinstance(volume, int) or isinstance(volume, bool):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.volume precisa ser int 0-255"
                )
            if not (0 <= volume <= 255):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.volume fora de 0-255"
                )
            muted = speaker_raw.get("muted", False)
            if not isinstance(muted, bool):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.muted precisa ser booleano"
                )
            rota = speaker_raw.get("rota")
            if rota is not None and (
                not isinstance(rota, int) or isinstance(rota, bool) or not (0 <= rota <= 3)
            ):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.rota precisa ser int 0-3"
                )
            try:
                setter(volume, muted=muted, uniq=str(uniq), rota=rota)
            except Exception as exc:
                logger.warning(
                    "apply_draft_speaker_por_unidade_falhou",
                    uniq=str(uniq),
                    erro=str(exc),
                )

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
        luzes = None
        if isinstance(leds_raw, dict) and leds_raw.get("player_led_brightness") is not None:
            from hefesto_dualsense4unix.core.led_control import degrau_do_brilho_das_luzes

            luzes = degrau_do_brilho_das_luzes(str(leds_raw["player_led_brightness"]))
        if (led is None and player is None and luzes is None
                and trigger_left is None and trigger_right is None):
            return None
        return OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player,
            player_led_brightness=luzes,
        )

    def _apply_rumble(self, rumble_raw: Any) -> None:
        """Aplica a seção rumble do "Aplicar" do RODAPÉ."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            modo_nativo_manda_nos_motores,
        )

        if not isinstance(rumble_raw, dict):
            raise ValueError("rumble deve ser objeto")
        if modo_nativo_manda_nos_motores(self.daemon):
            logger.warning(
                "draft_rumble_recusado_modo_nativo",
                pedido=rumble_raw,
            )
            raise ValueError("Modo Nativo: quem manda nos motores é o jogo")
        weak = rumble_raw.get("weak", 0)
        strong = rumble_raw.get("strong", 0)
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.weak e rumble.strong devem ser inteiros")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if weak == 0 and strong == 0:
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
                daemon_cfg.rumble_active_uniq = None
            self.controller.set_rumble(weak=0, strong=0)
            return
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
            daemon_cfg.rumble_active_uniq = uniq_do_alvo_de_output(self.controller)
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

    def _apply_mic(self, mic_raw: Any) -> None:
        """Aplica a seção mic do draft (MIC-EXPOSE-01).

        Único campo: ``button_toggles_system`` — se o botão de mic do controle
        alterna o mute do microfone PADRÃO DO SISTEMA. Escreve na config VIVA
        do daemon; o laço `mic_button_loop` consulta o flag a cada evento, então
        a mudança vale já no próximo toque do botão, sem restart e sem
        derrubar/recriar task nenhuma (o laço é um assinante de bus barato e
        fica de pé independente do flag).

        `volume` e `muted` chegam na mesma seção (PERFIL-GUARDA-O-MIC-01) e NÃO
        são aplicados aqui: quem os manda ao vivo é o `mic.volume.set`/`mic.set`
        do IPC, disparado pelo card no gesto dela — o rascunho só os carrega
        para o "Salvar Perfil".

        MIC-GATE-POR-CAMPO-01 (22/08/2026): campo ausente **ou nulo** é campo
        NÃO tocado, a mesma régua do `speaker.rota` aqui do lado. Sem o nulo,
        um rascunho sem opinião sobre o botão (o default desde esta data — ver
        `MicDraft`) cairia em `failed` e o rodapé diria que o microfone falhou,
        no gesto mais comum que existe: arrastar o volume e clicar no verde.
        """
        if not isinstance(mic_raw, dict):
            raise ValueError("mic deve ser objeto")
        if mic_raw.get("button_toggles_system") is None:
            return
        valor = mic_raw.get("button_toggles_system")
        if not isinstance(valor, bool):
            raise ValueError("mic.button_toggles_system deve ser booleano")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o botão de mic")
        antes = bool(getattr(self.daemon.config, "mic_button_toggles_system", True))
        self.daemon.config.mic_button_toggles_system = valor
        logger.info("mic_button_toggles_system_aplicado", enabled=valor)
        if antes and not valor:
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
                devolver_a_luz_ao_kernel,
            )

            devolver_a_luz_ao_kernel(self.daemon)

    def _apply_speaker(self, speaker_raw: Any) -> None:
        """Aplica a seção `speaker` do rascunho — O-VERDE-NAO-LEVAVA-O-SOM-01."""
        if not isinstance(speaker_raw, dict):
            raise ValueError("speaker deve ser objeto")
        if "volume" not in speaker_raw:
            return
        volume = speaker_raw.get("volume")
        if not isinstance(volume, int) or isinstance(volume, bool):
            raise ValueError("speaker.volume deve ser inteiro")
        if not 0 <= volume <= 255:
            raise ValueError("speaker.volume fora de 0..255")
        muted = speaker_raw.get("muted", False)
        if not isinstance(muted, bool):
            raise ValueError("speaker.muted deve ser booleano")
        rota = speaker_raw.get("rota")
        if rota is not None and (not isinstance(rota, int) or isinstance(rota, bool)):
            raise ValueError("speaker.rota deve ser inteiro ou nulo")
        applier = getattr(self.daemon, "apply_profile_speaker", None)
        if not callable(applier):
            raise ValueError("daemon não expõe apply_profile_speaker")
        applier(volume, muted, uniq=speaker_raw.get("uniq"), origin="draft", rota=rota)
        logger.info(
            "speaker_do_rascunho_aplicado", volume=volume, muted=muted, rota=rota
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


    def _politica_viva(self) -> tuple[str, float | None]:
        """A política global de vibração do daemon, e o teto dela — o denominador."""
        from hefesto_dualsense4unix.profiles.manager import _RUMBLE_POLICY_PADRAO

        cfg = getattr(self.daemon, "config", None) if self.daemon else None
        politica = getattr(cfg, "rumble_policy", None) or _RUMBLE_POLICY_PADRAO
        return str(politica), getattr(cfg, "rumble_policy_custom_mult", None)

    def _com_o_teto_da_economia(self, params: dict[str, Any]) -> dict[str, Any]:
        """O rascunho com o teto da economia posto — a MESMA vista da ativação.

        A QUEIXA: achada pela O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 e
        medida na mesa de quatro (o `IpcServer` real, o merge do
        `PyDualSenseController`): com a economia ligada só no P2, a ativação o
        deixava na luz a 30% `(76, 38, 0)`, nas luzes de número no Fraco, nos
        gatilhos com metade da força e na vibração a 0,3; o «Aplicar» o levava
        a `(209, 104, 0)`, ao Médio do perfil, à força inteira e à vibração do
        global. O rascunho não sabe da economia, e o «Aplicar» troca o mapa de
        overrides inteiro (`reset_output_overrides`).

        O DONO DO TETO É O DA ATIVAÇÃO, e ele não se reescreve aqui: quem está
        em economia é a declaração da mesa (`schema.economia_da_mesa` e
        `schema.controles_em_economia`, o que o gesto `economia-do-controle`
        grava), e o que ela faz em cada peça é `manager._perfil_na_economia` —
        as mesmas três chamadas de `ProfileManager.apply`. Quem estender a
        economia (outro teto, outro jeito de escolher quem economiza) estende
        lá, e o «Aplicar» segue sozinho. Aqui só se traduz o rascunho para o
        esquema e de volta.

        A TRADUÇÃO NÃO PERDE NADA QUE O TETO USE: o rascunho já chega com o
        brilho de cada cor resolvido (`DraftConfig._controllers_to_ipc`), e o
        teto é um `min` — o do brilho próprio e o do global dão o mesmo número.

        Devolve o rascunho intacto (o MESMO objeto) sem economia nenhuma: o
        «Aplicar» de quem não ligou nada é byte a byte o de antes. Os controles
        em economia ficam em `self._em_economia`, e vão na camada do PERFIL
        (`_publicar_a_economia`).
        """
        from hefesto_dualsense4unix.profiles.schema import (
            controles_em_economia,
            economia_da_mesa,
        )

        mesa, ligados = economia_da_mesa(), controles_em_economia()
        self._em_economia = frozenset()
        self._procedencias_da_economia = {}
        if not mesa and not ligados:
            return params
        try:
            return self._a_vista_da_economia(params, mesa, ligados)
        except Exception as exc:
            logger.warning("apply_draft_economia_falhou", erro=str(exc))
            self.failed["economia"] = (str(exc) or type(exc).__name__)[:120]
            return params

    def _a_vista_da_economia(
        self, params: dict[str, Any], mesa: bool, ligados: frozenset[str]
    ) -> dict[str, Any]:
        """O corpo de `_com_o_teto_da_economia`: rascunho → esquema → teto → rascunho."""
        from hefesto_dualsense4unix.profiles.manager import (
            _controllers_to_procedencias,
            _perfil_na_economia,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            Profile,
            RumbleConfig,
            TriggersConfig,
            economia_vale,
        )

        leds_raw = params.get("leds")
        trig_raw = params.get("triggers")
        ctrl_raw = params.get("controllers")
        leds = _leds_do_rascunho(leds_raw) if isinstance(leds_raw, dict) else None
        gatilhos = _gatilhos_do_rascunho(trig_raw) if isinstance(trig_raw, dict) else None
        politica, custom = self._politica_viva()
        mapa = {str(u): _override_do_rascunho(e) for u, e in (
            ctrl_raw.items() if isinstance(ctrl_raw, dict) else ()) if isinstance(e, dict)}
        vista = _perfil_na_economia(
            Profile.model_construct(
                leds=leds if leds is not None else (LedsConfig() if mesa else None),
                triggers=(gatilhos if gatilhos is not None
                          else (TriggersConfig() if mesa else None)),
                rumble=RumbleConfig.model_construct(policy=politica, custom_mult=custom),
                controllers=mapa or None,
            ),
            mesa,
            ligados,
        )
        novo = dict(params)
        if mesa and isinstance(leds_raw, dict):
            novo["leds"] = {
                **leds_raw,
                "lightbar_brightness": float(vista.leds.lightbar_brightness),
                "player_led_brightness": str(vista.leds.player_led_brightness),
            }
        if mesa and isinstance(trig_raw, dict):
            novo["triggers"] = {
                **trig_raw,
                **{lado: _gatilho_para_o_rascunho(getattr(vista.triggers, lado))
                   for lado in ("left", "right") if isinstance(trig_raw.get(lado), dict)},
            }
        da_vista = vista.controllers or {}
        em_economia = frozenset(
            u for u in da_vista if economia_vale(u in ligados, mesa))
        controles = dict(ctrl_raw) if isinstance(ctrl_raw, dict) else {}
        for uniq in sorted(em_economia):
            controles[uniq] = _entrada_na_economia(controles.get(uniq), da_vista[uniq])
        if controles:
            novo["controllers"] = controles
        self._em_economia = em_economia
        self._procedencias_da_economia = _controllers_to_procedencias(
            {u: da_vista[u] for u in em_economia})
        return novo

    def _publicar_a_economia(self, specs: dict[str, OutputSpec]) -> None:
        """O controle em economia vai na camada do PERFIL, como a ativação o põe.

        Na camada dela (`reset_output_overrides`/`apply_output_for`) o teto
        ficaria PRESO: desligar a economia reaplica o perfil com a origem
        ``system`` (`lifecycle.reaplicar_se_a_economia_mudou`), e a camada da
        usuária atravessa essa ativação — o P2 seguiria a 30% com a economia
        desligada. Na do perfil, a ativação seguinte o republica sem o teto.
        Backend sem camadas recebe o `apply_output_for` de sempre. Nos dois, a
        cor leva o número para o qual foi escolhida, pelas duas portas da
        ativação (`manager._publicar_camada`/`_aplicar_com_procedencia`).
        """
        if not specs:
            return
        from hefesto_dualsense4unix.core.led_control import LEGADO
        from hefesto_dualsense4unix.profiles.manager import (
            _aplicar_com_procedencia,
            _publicar_camada,
        )

        procedencias = self._procedencias_da_economia
        publicar = getattr(self.controller, "reset_profile_overrides", None)
        if callable(publicar):
            _publicar_camada(publicar, specs, procedencias)
            return
        for uniq, spec in specs.items():
            _aplicar_com_procedencia(
                self.controller.apply_output_for, uniq, spec,
                procedencias.get(uniq, LEGADO))


def _leds_do_rascunho(leds_raw: dict[str, Any]) -> Any:
    """A luz de uma seção do rascunho como `LedsConfig`, só com o que ela escreveu."""
    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    campos: dict[str, Any] = {}
    rgb = leds_raw.get("lightbar_rgb")
    if isinstance(rgb, list) and len(rgb) == 3:
        campos["lightbar"] = tuple(int(c) for c in rgb)
    brilho = _brilho_de(leds_raw.get("lightbar_brightness"))
    if brilho is not None:
        campos["lightbar_brightness"] = brilho
    if isinstance(leds_raw.get("player_leds"), list):
        campos["player_leds"] = [bool(b) for b in leds_raw["player_leds"]]
    numero = leds_raw.get("lightbar_para_o_numero")
    if isinstance(numero, int) and not isinstance(numero, bool):
        campos["lightbar_para_o_numero"] = numero
    if leds_raw.get("player_led_brightness") is not None:
        campos["player_led_brightness"] = str(leds_raw["player_led_brightness"])
    return LedsConfig.model_validate(campos) if campos else None


def _gatilhos_do_rascunho(trig_raw: dict[str, Any]) -> Any:
    """Os gatilhos de uma seção do rascunho, só os lados que ela escreveu."""
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig

    lados = {
        lado: TriggerConfig(mode=cru["mode"], params=list(cru.get("params") or []))
        for lado in ("left", "right")
        if isinstance(cru := trig_raw.get(lado), dict) and isinstance(cru.get("mode"), str)
    }
    return TriggersConfig(**lados) if lados else None


def _override_do_rascunho(entrada: dict[str, Any]) -> Any:
    """A entrada de um controle do rascunho como `ControllerOverrides` (luz, gatilhos, vibração)."""
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        ControllerRumbleOverride,
    )

    leds_raw, trig_raw, vib_raw = (
        entrada.get("leds"), entrada.get("triggers"), entrada.get("rumble"))
    vibracao = None
    if isinstance(vib_raw, dict) and vib_raw.get("policy") is not None:
        vibracao = ControllerRumbleOverride.model_validate(
            {k: vib_raw[k] for k in ("policy", "custom_mult") if vib_raw.get(k) is not None})
    return ControllerOverrides(
        leds=_leds_do_rascunho(leds_raw) if isinstance(leds_raw, dict) else None,
        triggers=_gatilhos_do_rascunho(trig_raw) if isinstance(trig_raw, dict) else None,
        rumble=vibracao,
    )


def _gatilho_para_o_rascunho(gatilho: Any) -> dict[str, Any]:
    return {"mode": gatilho.mode, "params": list(gatilho.params)}


def _entrada_na_economia(entrada: Any, dele: Any) -> dict[str, Any]:
    """A entrada de um controle com a luz, os gatilhos e a vibração da vista da economia."""
    saida = {k: v for k, v in (entrada or {}).items()
             if k not in ("leds", "triggers", "rumble")}
    luz = getattr(dele, "leds", None)
    if luz is not None:
        campos = luz.model_fields_set
        leds: dict[str, Any] = {}
        if "lightbar" in campos:
            leds["lightbar_rgb"] = [int(c) for c in luz.lightbar]
        if "lightbar_brightness" in campos:
            leds["lightbar_brightness"] = float(luz.lightbar_brightness)
        if "player_leds" in campos:
            leds["player_leds"] = [bool(b) for b in luz.player_leds]
        if "player_led_brightness" in campos:
            leds["player_led_brightness"] = str(luz.player_led_brightness)
        if leds:
            saida["leds"] = leds
    gatilhos = getattr(dele, "triggers", None)
    if gatilhos is not None:
        lados = {lado: _gatilho_para_o_rascunho(getattr(gatilhos, lado))
                 for lado in ("left", "right") if lado in gatilhos.model_fields_set}
        if lados:
            saida["triggers"] = lados
    vibracao = getattr(dele, "rumble", None)
    if vibracao is not None and getattr(vibracao, "policy", None) is not None:
        saida["rumble"] = {"policy": vibracao.policy}
        if vibracao.custom_mult is not None:
            saida["rumble"]["custom_mult"] = float(vibracao.custom_mult)
    return saida


__all__ = ["DraftApplier"]
