"""DraftApplier — aplica `profile.apply_draft` em ordem canônica.

Extraído de `_handle_profile_apply_draft` em AUDIT-FINDING-IPC-SERVER-SPLIT-01.
Cada seção (leds, triggers, controllers, rumble, mouse, keyboard, mic, speaker)
é aplicada de forma best-effort: falha em uma seção loga warning, fica registrada
em ``failed`` (APLICAR-VERDADE-01) e não bloqueia as demais. A ordem é leds
-> triggers -> controllers -> rumble -> mouse -> keyboard -> mic -> speaker
(leds primeiro por ser menos transiente visualmente; controllers DEPOIS das
seções globais para o override por-controle vencer no alvo — PERFIL-04).

ESTA LISTA É A PROMESSA DO BOTÃO VERDE, e ela ficou desatualizada duas vezes
antes de alguém notar: o `mic` entrou pela MIC-EXPOSE-01 sem ser citado aqui, e
o `speaker` faltava por inteiro até 10/08/2026 — `grep -c speaker` neste arquivo
devolvia ZERO, e o volume que ela ajustava no card só chegava ao controle na
próxima troca de perfil. Há portão que compara esta lista com o que o rascunho
emite; se as duas divergirem, ele reprova
(`tests/unit/test_o_verde_leva_tudo_01.py`).
"""
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
        # APLICAR-VERDADE-01: seção -> motivo curto das que NÃO entraram. O
        # best-effort continua igual (uma seção que falha não bloqueia as
        # outras), mas a falha para de morrer no warning do log: sobe junto
        # com `applied` para quem chamou poder dizer a verdade na tela.
        self.failed: dict[str, str] = {}

    def apply(self, params: dict[str, Any]) -> list[str]:
        # ONDA-U (Causa A): trava manual INCONDICIONAL, no topo — antes vivia
        # só dentro de `_apply_triggers` (BUG-MOUSE-TRIGGERS-01), então um
        # "Aplicar no controle" sem a seção `triggers` (ex.: só `leds`, o
        # botão da aba Lightbar) não armava a trava; o `AutoSwitcher`
        # reativava o perfil salvo no próximo tick com troca de foco de
        # janela e apagava a edição recém-aplicada ("perfil eterno", U3/U4/
        # U9/U11). `apply_draft` É sempre edição manual explícita — arma
        # ANTES de aplicar, POR CATEGORIA das seções presentes (F1, auditoria
        # 21/07); payload sem seção mapeável (ex.: só `mouse`) arma as três,
        # preservando o incondicional da cura original.
        secoes_para_categorias = {
            "leds": {"led"},
            "triggers": {"trigger"},
            "rumble": {"rumble"},
            # Overrides por-controle podem carregar cor/gatilho/rumble.
            "controllers": {"led", "trigger", "rumble"},
        }
        categorias: set[str] = set()
        for secao, cats in secoes_para_categorias.items():
            if params.get(secao) is not None:
                categorias |= cats
        for categoria in sorted(categorias or {"led", "trigger", "rumble"}):
            self.store.mark_manual_trigger_active(categoria)
        applied: list[str] = []
        # Cada `apply` conta a história dele: zera o registro de falhas antes
        # de começar (o mesmo applier pode ser reusado).
        self.failed = {}
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
        # MIC-EXPOSE-01: seção `mic` (botão de mic  mute do sistema).
        self._apply_section(applied, params.get("mic"), "mic", self._apply_mic)
        # O-VERDE-NAO-LEVAVA-O-SOM-01 (10/08/2026): a seção `speaker` faltava
        # aqui, e a palavra é literal — `grep -c speaker` neste arquivo devolvia
        # ZERO. O botão verde "Aplicar" carregava gatilho, luz, rumble, mouse,
        # teclado e mic, e deixava o alto-falante do controle para trás.
        #
        # O volume, o mudo e o canal chegavam ao PERFIL (`to_profile`) e ao
        # hardware na ATIVAÇÃO do perfil (`apply_profile_speaker`, pela rota do
        # autoswitch), mas não no AGORA: ela mexia no card, clicava no verde, e
        # o som não mudava até trocar de perfil. É metade exata da queixa dela —
        # *"literalmente nenhuma feature ficou lá"*.
        #
        # Por último de propósito, como o mic: é a seção mais barata de refazer
        # se falhar, e nenhuma outra depende dela.
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
            # APLICAR-VERDADE-01: além do warning (que só a gente lê), a seção
            # entra em `self.failed`. Sem isto a resposta do handler dizia
            # apenas o que deu certo, e a GUI, sem nada que contradissesse o
            # `status: "ok"`, anunciava "Perfil aplicado ao controle." mesmo
            # com todas as seções fora. Motivo curto e cortado: serve de
            # diagnóstico, não é o texto que a usuária lê.
            motivo = str(exc) or type(exc).__name__
            self.failed[section] = motivo[:120]

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
        # POR-UNIDADE-01 (10/08/2026): vibração e som da PEÇA. Ficam FORA do
        # `OutputSpec` de propósito — não são output persistente do controle
        # (o rumble é transitório; o áudio tem posse própria), e empurrá-los
        # para dentro do spec faria o reassert de hotplug re-vibrar o que já
        # passou. Cada um segue a sua rota por-uniq, que já existia.
        self._publicar_escalas_de_vibracao(raw)
        self._escrever_alto_falantes_por_unidade(raw)

    def _publicar_escalas_de_vibracao(self, raw: dict[str, Any]) -> None:
        """Publica a escala de vibração por peça no backend (POR-UNIDADE-01).

        SUBSTITUI o mapa inteiro, como o ``reset_output_overrides`` acima e
        pela mesma razão: intensidade que ela TIROU de um controle na janela
        (a peça voltou ao global e sumiu do payload) tem de sumir do backend
        no mesmo "Aplicar", senão continuaria valendo até a próxima troca de
        perfil e a tela mentiria.

        O fator é RELATIVO à política global vigente no daemon — o mesmo
        denominador que ``_controllers_to_rumble_scales`` usa na ativação,
        porque o valor que chega ao ``set_rumble`` já vem escalado por ela
        (``apply_rumble_policy``). Sem daemon (CLI/testes), o denominador é o
        ``balanceado`` padrão.
        """
        from hefesto_dualsense4unix.profiles.manager import (
            _RUMBLE_POLICY_PADRAO,
            _mult_da_politica,
        )

        escalar = getattr(self.controller, "set_rumble_scales", None)
        if not callable(escalar):
            return
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        policy_global = (
            getattr(daemon_cfg, "rumble_policy", None) or _RUMBLE_POLICY_PADRAO
        )
        base = _mult_da_politica(
            policy_global, getattr(daemon_cfg, "rumble_policy_custom_mult", None)
        )
        escalas: dict[str, float] = {}
        for uniq, entry in raw.items():
            rumble_raw = entry.get("rumble") if isinstance(entry, dict) else None
            if not isinstance(rumble_raw, dict):
                continue
            mult = _mult_da_politica(
                rumble_raw.get("policy"), rumble_raw.get("custom_mult")
            )
            if mult is None or base is None or base <= 0.0:
                # Global em `auto` (denominador móvel) ou política que não vira
                # número: a peça fica com o global. Ver a docstring do irmão em
                # `profiles/manager.py` — prometer um fator contra denominador
                # móvel seria pior do que não entregar.
                continue
            fator = mult / base
            if fator != 1.0:
                escalas[str(uniq)] = fator
        escalar(escalas or None)

    def _escrever_alto_falantes_por_unidade(self, raw: dict[str, Any]) -> None:
        """Aplica o alto-falante de cada peça (POR-UNIDADE-01).

        Rota por-``uniq`` que já existia e nunca fora ligada pelo perfil:
        ``set_speaker_volume(volume, muted=..., uniq=..., rota=...)``. Fala
        DIRETO com o backend, e não pelo ``speaker.set`` do IPC, pela mesma
        razão de ``lifecycle.apply_profile_speaker``: aquele handler arma a
        trava manual da categoria ``"audio"``, e um "Aplicar" que a armasse
        faria todo "Aplicar" seguinte ser descartado em silêncio.

        Sem broadcast e sem ``None``: seção ausente é ausência de opinião, e
        nunca escrever é o que impede tomar a posse dos bytes de áudio de uma
        peça que ninguém pediu (SOM-02, armadilha 1).
        """
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
                # MESA-CHEIA-05 (E0): sem par fixado não há dono a lembrar.
                daemon_cfg.rumble_active_uniq = None
            self.controller.set_rumble(weak=0, strong=0)
            return
        # AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01:
        # Persiste valores brutos para que o poll loop (_reassert_rumble)
        # continue reaplicando a política a cada tick. Antes de enviar ao
        # hardware, escala via apply_rumble_policy — mesmo comportamento
        # canônico de _handle_rumble_set.
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
            # MESA-CHEIA-05 (E0): o "Aplicar" do rodapé mira o alvo do seletor
            # tanto quanto a aba Rumble — então congela o dono junto do par,
            # senão o valor migra para quem entrar no seletor depois.
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
        """
        if not isinstance(mic_raw, dict):
            raise ValueError("mic deve ser objeto")
        if "button_toggles_system" not in mic_raw:
            return
        valor = mic_raw.get("button_toggles_system")
        if not isinstance(valor, bool):
            raise ValueError("mic.button_toggles_system deve ser booleano")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o botão de mic")
        self.daemon.config.mic_button_toggles_system = valor
        logger.info("mic_button_toggles_system_aplicado", enabled=valor)

    def _apply_speaker(self, speaker_raw: Any) -> None:
        """Aplica a seção `speaker` do rascunho — O-VERDE-NAO-LEVAVA-O-SOM-01.

        Três campos, os MESMOS do `ProfileSpeakerConfig` e do `SpeakerDraft`:
        ``volume`` (0 a 255, byte do registrador), ``muted`` e ``rota`` (o canal de saída). Um nome
        diferente aqui criaria um terceiro vocabulário para o mesmo fato.

        **Reusa a porta que já existe**, `Daemon.apply_profile_speaker`, e isso
        é requisito, não conveniência: ela é a mesma que a ativação de perfil
        usa, já sabe conversar por-`uniq` e já carrega a política de silêncio da
        SOM-02/E4. Um caminho novo direto ao backend seria um segundo dono dos
        bytes de áudio — e o `set_speaker_volume` do backend, medido em 10/08,
        **não tem gate de `_output_mute`**: chamá-lo por fora responderia `ok` em
        Modo Nativo sem mandar byte nenhum, e a tela diria que aplicou.

        Campo ausente é campo NÃO tocado (`volume` obrigatório, o resto opcional):
        o rascunho só emite esta seção quando ela mexeu, e mesmo assim o mudo e a
        rota podem não ter opinião. Sem opinião é silêncio, nunca ordem.
        """
        if not isinstance(speaker_raw, dict):
            raise ValueError("speaker deve ser objeto")
        if "volume" not in speaker_raw:
            return
        volume = speaker_raw.get("volume")
        if not isinstance(volume, int) or isinstance(volume, bool):
            raise ValueError("speaker.volume deve ser inteiro")
        # A RÉGUA É 0..255, e errar isso recusa o volume NORMAL dela. Medido em
        # 10/08/2026: a primeira versão desta guarda usou 0..100, por eu ter lido
        # "volume" como porcentagem — e o controle deslizante do card em 100 %
        # sai como **102**. A seção cairia em `failed` e o rodapé diria que o som
        # falhou, no gesto mais comum que existe. O registrador do controle é um
        # byte, e é assim em toda a casa: `ProfileSpeakerConfig` (`ge=0, le=255`),
        # o `SpeakerDraft`, o IPC `speaker.set` e o `set_speaker_volume` do
        # backend. Aqui não pode ser diferente — quatro réguas iguais e uma
        # sozinha é como se recusa em silêncio o que a pessoa acabou de escolher.
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


__all__ = ["DraftApplier"]
