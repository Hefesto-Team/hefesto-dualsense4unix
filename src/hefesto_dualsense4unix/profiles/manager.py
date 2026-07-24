"""Gerencia perfis em memória e coordena aplicação no controle.

Responsabilidades:
  - Listar, selecionar e aplicar perfis.
  - Atualizar o `StateStore` com o nome do perfil ativo.
  - Aplicar triggers + LEDs no controle quando um perfil é ativado — via a
    API por-uniq do backend (PERFIL-01: broadcast REAL que ignora o seletor
    de alvo da GUI + substituição do mapa de overrides por-controle).

Auto-switch por janela ativa fica em `hefesto_dualsense4unix.profiles.autoswitch` (W6.2).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.core.controller import IController, OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS, KeyBinding
from hefesto_dualsense4unix.core.led_control import LedSettings
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    Profile,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProfileManager:
    controller: IController
    store: StateStore = field(default_factory=StateStore)
    # FEAT-KEYBOARD-PERSISTENCE-01: referência opcional ao device virtual.
    # Quando presente, `activate()` propaga o `key_bindings` resolvido para
    # o device. Typing "Any" para evitar ciclo de import com integrations.
    keyboard_device: object | None = None
    # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider LAZY do device de teclado.
    # O manager é criado no boot ANTES de o keyboard subir (lifecycle sobe
    # IPC/autoswitch primeiro) e o device é anulado/recriado em disconnect e
    # reload — capturar a referência eager congela `None` para sempre. Os
    # callsites injetam `lambda: getattr(daemon, "_keyboard_device", None)`;
    # `apply_keyboard` resolve o provider a cada ativação. Quando presente,
    # tem precedência sobre `keyboard_device` (mantido para backcompat).
    keyboard_device_provider: Callable[[], object | None] | None = None
    # FEAT-POINT-AND-CLICK-01: applier da seção `mouse` do perfil. Os callsites
    # injetam `daemon.set_mouse_emulation` (retorna bool — por isso o retorno é
    # `object`, não `None`). Assinatura: (enabled, speed, scroll_speed).
    # None = seção mouse do perfil é ignorada (CLI/testes sem daemon).
    mouse_applier: Callable[[bool, int, int], object] | None = None
    # FEAT-POINT-AND-CLICK-01: applier da supressão de emulação (modo-jogo)
    # por perfil. Os callsites injetam `daemon.apply_profile_suppression`, que
    # concentra a política (origem perfil vs. toggle manual + lock de 30s).
    # Recebe `profile.suppress_desktop_emulation` a cada ativação.
    suppression_applier: Callable[[bool], object] | None = None
    # FEAT-PROFILE-MODE-01: applier da seção `mode` do perfil (nativo/gamepad/
    # desktop + co-op). Os callsites injetam `daemon.apply_profile_mode` —
    # recebe `profile.mode` (inclusive None: perfil sem opinião reverte só modo
    # ligado por OUTRO perfil). None = seção ignorada (CLI/testes sem daemon).
    mode_applier: Callable[[object], object] | None = None
    # FEAT-RUMBLE-POLICY-PROFILE-01: applier da política de rumble do perfil
    # (seção `rumble.policy`/`rumble.custom_mult`). Os callsites injetam
    # `daemon.apply_profile_rumble_policy` — recebe (policy, custom_mult) a
    # cada ativação, inclusive (None, None) para perfil sem opinião (reverte
    # só política aplicada por OUTRO perfil; política manual fica). None =
    # seção ignorada (CLI/testes sem daemon).
    rumble_policy_applier: Callable[[str | None, float | None], None] | None = None
    # SPRINT-GAME-RUMBLE-01: applier da seção `rumble.passthrough` do perfil.
    # Os callsites injetam `daemon.apply_profile_rumble_passthrough` — recebe o
    # bool a cada ativação. passthrough=True (default de TODO perfil) solta o
    # rumble FIXADO pela GUI (rumble_active=None), devolvendo a vibração ao JOGO;
    # sem isto, testar os motores na GUI ("Aplicar"/"Parar") deixava o rumble
    # travado e o FF do jogo era ignorado mesmo com a máscara certa. None =
    # seção ignorada (CLI/testes sem daemon).
    rumble_passthrough_applier: Callable[[bool], None] | None = None

    def list_profiles(self) -> list[Profile]:
        return load_all_profiles()

    def get(self, name: str) -> Profile:
        return load_profile(name)

    def create(self, profile: Profile) -> None:
        save_profile(profile)
        logger.info("profile_created", name=profile.name)

    def delete(self, name: str) -> None:
        delete_profile(name)
        active = self.store.active_profile
        # BUG-PROFILE-DELETE-ACTIVE-SLUG-01: `activate()` grava o DISPLAY NAME em
        # `active_profile`, mas `delete()` aceita slug OU display name. Comparar
        # as strings cruas deixava o active "preso" quando o delete vinha por
        # slug (ex.: active="Ação", name="acao" — slugs iguais, strings não).
        # Normalizamos AMBOS via slugify antes de comparar.
        if active is not None and self._refers_same_profile(active, name):
            self.store.set_active_profile(None)
        logger.info("profile_deleted", name=name)

    @staticmethod
    def _refers_same_profile(active: str, name: str) -> bool:
        """True se `active` e `name` apontam para o mesmo perfil (compara slugs).

        O arquivo já foi removido por `delete_profile`, então NÃO dependemos do
        disco: `slugify` roda sobre as strings em memória. Tolera nomes exóticos
        que não produzem slug (ValueError) caindo na comparação literal — assim
        um active sem slug ainda é limpo quando o delete vem com a mesma string.
        """
        from hefesto_dualsense4unix.profiles.slug import slugify

        try:
            return slugify(active) == slugify(name)
        except ValueError:
            return active == name

    def activate(self, name: str, *, origin: str = "manual") -> Profile:
        """Carrega, aplica triggers + LEDs + teclado + emulação e marca como ativo.

        PERFIL-03 (autoload): `origin` separa o GESTO MANUAL da usuária das
        ativações automáticas — o bug provado do sprint era o autoswitch
        reescrever `session.json` a cada troca de janela, e o boot restaurar
        "Navegação" em vez da escolha dela. Valores:

          - ``"manual"`` (default) — profile.switch via IPC (GUI/CLI) e o
            ciclo por hotkey (PS+D-pad): É a intenção da usuária → persiste
            em `session.json` (`save_last_profile`).
          - ``"autoswitch"`` — troca automática por janela em foco: aplica e
            marca ativo, mas NÃO grava a intenção manual.
          - ``"system"`` — restore de boot e saída do Modo Nativo: idem, o
            sistema re-aplicando estado não é escolha nova.

        O default "manual" é deliberado: um caller novo que esqueça o
        parâmetro preserva o comportamento histórico (gravar), nunca
        silencia um gesto real da usuária. NÃO confundir com o `origin`
        do latch de `start_gamepad_emulation` ("manual"/"profile") — são
        contratos distintos.
        """
        profile = load_profile(name)
        self.apply(profile)
        self.apply_keyboard(profile)
        self.apply_emulation(profile)
        self.store.set_active_profile(profile.name)
        self.store.bump("profile.activated")
        logger.info(
            "profile_activated",
            name=profile.name,
            priority=profile.priority,
            origin=origin,
        )
        if origin == "manual":
            from hefesto_dualsense4unix.utils.session import save_last_profile
            save_last_profile(profile.name)
        # FEAT-COSMIC-NOTIFICATIONS-01: opt-in via env var
        # `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1`. Sem isso, no-op.
        try:
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_profile_activated,
            )
            notify_profile_activated(profile.name)
        except Exception:
            pass
        return profile

    def apply(self, profile: Profile) -> None:
        """Aplica triggers e LEDs do perfil em TODOS os controles (sem marcar ativo).

        PERFIL-01 (4P-01): a seção global vai por `apply_output_defaults` —
        broadcast REAL que IGNORA o seletor de alvo da GUI. Os setters
        clássicos respeitam o seletor, então ativar um perfil com um alvo
        selecionado (manual OU via autoswitch, que passa pela MESMA cadeia
        `activate()` → `apply()`) atingia SÓ o alvo — bug provado do sprint.
        O brilho passa pelo MESMO caminho de escala do histórico
        (`LedSettings.apply_brightness`, paridade com `apply_led_settings`).

        Na sequência, a ativação SUBSTITUI o mapa de overrides por-controle
        (`reset_output_overrides`): nada do perfil anterior ressuscita num
        replug sob o perfil novo. PERFIL-04: as entradas de
        `profile.controllers` (mapa por-MAC no JSON) entram no reset e cada
        uma é aplicada via `apply_output_for` — controle conectado recebe na
        hora, desconectado fica REGISTRADO no mapa em memória do backend (o
        hotplug o aplica quando ele chegar; é o teste de fogo do PERFIL-05c).
        O brilho do override escala pelo MESMO caminho da seção global.

        COR-03: a ativação também configura o estado do AUTOMÁTICO (cores por
        controle) no registro de identidade — `enabled` vem de
        `profile.leds.auto_player_colors` (perfil sem seção `leds` no JSON
        valida com `LedsConfig()` → auto ON, o default do campo) e o brilho
        vigente de `profile.leds.lightbar_brightness` (a cor automática é
        escalada pelo MESMO brilho do global — D11). O provider injetado no
        backend consulta esse estado a cada resolução; a escrita física dos
        conectados acontece pelos broadcasts/reasserts desta mesma ativação.

        Mic-LED fica de fora por decisão deliberada
        (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01): jamais colateral de
        profile switch.
        """
        left = build_from_name(profile.triggers.left.mode, profile.triggers.left.params)
        right = build_from_name(profile.triggers.right.mode, profile.triggers.right.params)
        settings = _to_led_settings(profile.leds)
        effective = settings.apply_brightness(settings.brightness_level)
        self._configure_auto_player_colors(profile)
        self.controller.apply_output_defaults(
            OutputSpec(
                trigger_left=left,
                trigger_right=right,
                led=effective.lightbar,
                player_leds=settings.player_leds,
            )
        )
        overrides = _controllers_to_specs(profile.controllers, profile.leds)
        self.controller.reset_output_overrides(overrides or None)
        for uniq, spec in overrides.items():
            self.controller.apply_output_for(uniq, spec)
        # COR-03 (fix de integração, 2026-07-17): o broadcast acima escreve o
        # GLOBAL nos conectados — sem este reassert, a paleta automática só
        # apareceria no próximo replug (boot com controles presentes ficava
        # com a cor global; visto AO VIVO na validação pós-install). Converge
        # o estado físico ao RESOLVIDO por-controle (explícita > auto >
        # global). Getattr defensivo: backends sem o método (fakes) seguem.
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()

    @staticmethod
    def _configure_auto_player_colors(profile: Profile) -> None:
        """Propaga o toggle/brilho do automático ao registro de identidade (COR-03).

        Import lazy do singleton (`get_identity_registry`) de propósito: o
        `ProfileManager` é instanciado em ≥3 lugares (restore de boot,
        hotkey, IPC) e todos precisam configurar o MESMO estado que o
        provider do backend consulta — sem parâmetro novo em cada callsite.
        Best-effort (falha loga debug, não aborta a ativação): CLI/testes
        sem daemon configuram um singleton que ninguém consulta — inócuo e
        sem I/O (`configure` só toca memória).
        """
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
            )

            get_identity_registry().configure(
                enabled=bool(profile.leds.auto_player_colors),
                brightness=float(profile.leds.lightbar_brightness),
            )
        except Exception as exc:
            logger.debug("auto_player_colors_configure_falhou", err=str(exc))

    def apply_keyboard(self, profile: Profile) -> None:
        """Propaga `key_bindings` do perfil ao device virtual de teclado (A-06).

        No-op quando não há device (CLI, testes sem daemon) ou o device não
        está ativo. Spec opção (c): método público para que a chamada fique
        explícita nos pontos que têm acesso ao device.

        FEAT-POINT-AND-CLICK-01 (A8): quando `keyboard_device_provider` existe,
        ele é resolvido AQUI, a cada ativação — imune ao boot fora de ordem
        (IPC/autoswitch sobem antes do keyboard) e ao device anulado/recriado
        em disconnect/reload.
        """
        provider = self.keyboard_device_provider
        device = provider() if provider is not None else self.keyboard_device
        if device is None:
            return
        resolved = _to_key_bindings(profile)
        try:
            device.set_bindings(resolved)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "keyboard_device_apply_failed",
                profile=profile.name,
                err=str(exc),
            )

    def apply_emulation(self, profile: Profile) -> None:
        """Aplica a seção `mouse` e a supressão de modo-jogo do perfil.

        FEAT-POINT-AND-CLICK-01. Best-effort (falha loga warning, não aborta a
        ativação — paridade com `apply_keyboard`):

        - `profile.mouse` presente + `mouse_applier` injetado → liga/desliga a
          emulação de mouse com as velocidades do perfil. `mouse=None` NÃO toca
          no estado (comportamento v1 preservado).
        - `suppression_applier` injetado → recebe SEMPRE o valor de
          `suppress_desktop_emulation` (inclusive o default False, para que
          trocar para um perfil sem o campo LIBERE a supressão ligada por outro
          perfil). A política de "não reverter toggle manual" mora no applier
          (`Daemon.apply_profile_suppression`).
        """
        if self.mouse_applier is not None and profile.mouse is not None:
            try:
                self.mouse_applier(
                    profile.mouse.enabled,
                    profile.mouse.speed,
                    profile.mouse.scroll_speed,
                )
            except Exception as exc:
                logger.warning(
                    "profile_mouse_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        if self.suppression_applier is not None:
            try:
                self.suppression_applier(profile.suppress_desktop_emulation)
            except Exception as exc:
                logger.warning(
                    "profile_suppression_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # FEAT-PROFILE-MODE-01: o applier recebe SEMPRE a seção (inclusive
        # None) — é assim que trocar para um perfil sem opinião REVERTE o modo
        # ligado por outro perfil, respeitando gesto manual (política no
        # `Daemon.apply_profile_mode`). Ordem: por último, para que "sair do
        # nativo" não re-aplique nada por cima dos triggers/LEDs já aplicados.
        if self.mode_applier is not None:
            try:
                self.mode_applier(getattr(profile, "mode", None))
            except Exception as exc:
                logger.warning(
                    "profile_mode_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # FEAT-RUMBLE-POLICY-PROFILE-01: idem `mode` — o applier recebe SEMPRE
        # o par (policy, custom_mult), inclusive (None, None), para que trocar
        # para um perfil sem opinião REVERTA a política aplicada por outro
        # perfil. A política de reversão/lock manual mora no applier
        # (`Daemon.apply_profile_rumble_policy`).
        if self.rumble_policy_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
                self.rumble_policy_applier(
                    getattr(rumble_cfg, "policy", None),
                    getattr(rumble_cfg, "custom_mult", None),
                )
            except Exception as exc:
                logger.warning(
                    "profile_rumble_policy_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # SPRINT-GAME-RUMBLE-01: aplica o `rumble.passthrough` do perfil — solta
        # o rumble FIXADO pela GUI para o JOGO controlar a vibração. SEMPRE (o
        # default True cobre todo perfil); o applier só age se há rumble fixado.
        if self.rumble_passthrough_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
                self.rumble_passthrough_applier(
                    bool(getattr(rumble_cfg, "passthrough", True))
                )
            except Exception as exc:
                logger.warning(
                    "profile_rumble_passthrough_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )

    def select_for_window(self, window_info: dict[str, object]) -> Profile | None:
        """Escolhe o perfil MAIS ESPECÍFICO que case com a janela.

        Se nenhum perfil casa (inclusive fallback), retorna None. Chamado pelo
        autoswitch em W6.2.

        R-01 (auditoria 23/07): a ordenação era só por `priority`, e por isso um
        perfil catch-all podia vencer a regra própria do jogo. É o caso medido
        no disco da usuária: `vitoria` (MatchAny, prio 5) vencia qualquer perfil
        de jogo recém-criado, que nasce com prioridade 0 — ou seja, criar o
        perfil do jogo pela GUI **não resolvia** o problema que ela tentava
        resolver.

        Agora **especificidade vem antes de prioridade**: qualquer perfil que
        casou por critério real vence qualquer catch-all. Entre perfis de mesma
        especificidade a prioridade continua decidindo, o que preserva o tuning
        50-80 dos presets (Navegação 50 < FPS 60 < Aventura 70 < Sackboy 80).

        Deliberadamente NÃO se introduz uma escada `window_class > regex`: isso
        reordenaria perfis de critério hoje empatados e mudaria comportamento já
        validado. A distinção fina entre "casou por regex solto" e "é a regra do
        jogo" mora em `perfil_e_regra_de_jogo`, usada por quem precisa dela.
        """
        candidates = [p for p in load_all_profiles() if p.matches(dict(window_info))]
        if not candidates:
            return None
        candidates.sort(key=lambda p: (not p.e_catch_all, p.priority), reverse=True)
        return candidates[0]


def resolve_key_bindings(
    raw: dict[str, list[str]] | None,
) -> dict[str, KeyBinding]:
    """Resolve um mapping CRU de key_bindings (button→tokens) para o device.

    Mesmas regras de `_to_key_bindings`, mas recebe o mapping cru em vez de um
    `Profile` — usado por `profile.apply_draft` (DraftApplier) para empurrar os
    bindings editados na aba Teclado ao device vivo sem reativar o perfil do
    disco (BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01).

    Regras (FEAT-KEYBOARD-PERSISTENCE-01):
    - `None` → herda `DEFAULT_BUTTON_BINDINGS` completo.
    - `{}` → vazio (teclado silencioso; usuário removeu todos os bindings).
    - dict parcial → override isolado; **não mescla com defaults**.
    """
    if raw is None:
        return dict(DEFAULT_BUTTON_BINDINGS)
    return {button: tuple(tokens) for button, tokens in raw.items()}


def _to_key_bindings(profile: Profile) -> dict[str, KeyBinding]:
    """Resolve `Profile.key_bindings` em mapping pronto para o device.

    Converte `list[str]` do schema em `tuple[str, ...]` (KeyBinding). Delega a
    resolução das regras (None/{}/parcial) a `resolve_key_bindings`.
    """
    return resolve_key_bindings(profile.key_bindings)


def _controllers_to_specs(
    controllers: dict[str, ControllerOverrides] | None,
    global_leds: LedsConfig | None = None,
) -> dict[str, OutputSpec]:
    """Converte o mapa `controllers` do perfil em `OutputSpec` por MAC.

    PERFIL-04 (sprint perfis-por-controle): o vocabulário parcial se
    preserva — seção ausente no override (`None`) vira campo `None` no spec
    ("sem opinião": o merge POR CAMPO do backend herda o padrão broadcast).

    Fix do review (2026-07-16, MED): a parcialidade vale também DENTRO da
    seção — só campos EXPLICITAMENTE escritos no JSON (``model_fields_set``
    do pydantic) entram no spec; campo não escrito vira ``None`` e herda o
    global no merge do backend, em paridade com o applier IPC. Antes, os
    defaults do schema densificavam os campos ausentes (player-LEDs todos
    apagados, brilho 1.0, gatilho ``Off``) e pisavam o global do controle —
    a resolução-por-objeto refutada pelo sprint doc, um nível abaixo.

    Cor e brilho formam UM campo no backend (o RGB pré-escalado); quando o
    override escreve só um dos dois, o outro é resolvido de ``global_leds``
    (a seção global do perfil) AQUI na borda. O brilho escala o RGB pelo
    MESMO caminho da seção global (`LedSettings.apply_brightness`): o que
    fica registrado no mapa do backend — e reaplicado no hotplug — é a cor
    JÁ escalada, em paridade com o broadcast. Entradas sem nenhum campo
    escrito são puladas.
    """
    out: dict[str, OutputSpec] = {}
    for uniq, cfg in (controllers or {}).items():
        trigger_left: TriggerEffect | None = None
        trigger_right: TriggerEffect | None = None
        if cfg.triggers is not None:
            lados = cfg.triggers.model_fields_set
            if "left" in lados:
                trigger_left = build_from_name(
                    cfg.triggers.left.mode, cfg.triggers.left.params
                )
            if "right" in lados:
                trigger_right = build_from_name(
                    cfg.triggers.right.mode, cfg.triggers.right.params
                )
        led: tuple[int, int, int] | None = None
        player_leds: tuple[bool, bool, bool, bool, bool] | None = None
        if cfg.leds is not None:
            campos = cfg.leds.model_fields_set
            if "lightbar" in campos or "lightbar_brightness" in campos:
                rgb = (
                    cfg.leds.lightbar
                    if "lightbar" in campos or global_leds is None
                    else global_leds.lightbar
                )
                brilho = (
                    cfg.leds.lightbar_brightness
                    if "lightbar_brightness" in campos or global_leds is None
                    else global_leds.lightbar_brightness
                )
                settings = LedSettings(
                    lightbar=rgb, brightness_level=float(brilho)
                )
                led = settings.apply_brightness(settings.brightness_level).lightbar
            if "player_leds" in campos:
                player_leds = _to_led_settings(cfg.leds).player_leds
        if (
            trigger_left is None
            and trigger_right is None
            and led is None
            and player_leds is None
        ):
            continue
        out[uniq] = OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player_leds,
        )
    return out


def _to_led_settings(leds: LedsConfig) -> LedSettings:
    """Converte `LedsConfig` (schema de perfil) em `LedSettings` (camada de hardware).

    Propaga todos os campos relevantes: lightbar RGB, brightness_level
    e player_leds. Armadilha A-06 resolvida para brightness (FEAT-LED-BRIGHTNESS-02).
    """
    player_leds_tuple: tuple[bool, bool, bool, bool, bool] = (
        leds.player_leds[0],
        leds.player_leds[1],
        leds.player_leds[2],
        leds.player_leds[3],
        leds.player_leds[4],
    )
    return LedSettings(
        lightbar=leds.lightbar,
        brightness_level=float(leds.lightbar_brightness),
        player_leds=player_leds_tuple,
    )


__all__ = [
    "ProfileManager",
    "_controllers_to_specs",
    "_to_key_bindings",
    "_to_led_settings",
    "resolve_key_bindings",
]
