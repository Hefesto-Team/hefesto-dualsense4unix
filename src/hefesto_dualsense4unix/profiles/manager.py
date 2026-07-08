"""Gerencia perfis em memória e coordena aplicação no controle.

Responsabilidades:
  - Listar, selecionar e aplicar perfis.
  - Atualizar o `StateStore` com o nome do perfil ativo.
  - Chamar `set_trigger` e `apply_led_settings` no controle quando um
    perfil é ativado.

Auto-switch por janela ativa fica em `hefesto_dualsense4unix.profiles.autoswitch` (W6.2).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS, KeyBinding
from hefesto_dualsense4unix.core.led_control import LedSettings, apply_led_settings
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import LedsConfig, Profile
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

    def activate(self, name: str) -> Profile:
        """Carrega, aplica triggers + LEDs + teclado + emulação e marca como ativo."""
        profile = load_profile(name)
        self.apply(profile)
        self.apply_keyboard(profile)
        self.apply_emulation(profile)
        self.store.set_active_profile(profile.name)
        self.store.bump("profile.activated")
        logger.info("profile_activated", name=profile.name, priority=profile.priority)
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
        """Aplica triggers e LEDs do perfil no controle (sem marcar como ativo)."""
        for side, trigger in (("left", profile.triggers.left), ("right", profile.triggers.right)):
            effect = build_from_name(trigger.mode, trigger.params)
            self.controller.set_trigger(side, effect)  # type: ignore[arg-type]

        leds = profile.leds
        settings = _to_led_settings(leds)
        apply_led_settings(self.controller, settings)

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

    def select_for_window(self, window_info: dict[str, object]) -> Profile | None:
        """Escolhe perfil de maior prioridade cujo match case com a janela.

        Se nenhum perfil casa (inclusive fallback), retorna None. Chamado pelo
        autoswitch em W6.2.
        """
        candidates = [p for p in load_all_profiles() if p.matches(dict(window_info))]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.priority, reverse=True)
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
    "_to_key_bindings",
    "_to_led_settings",
    "resolve_key_bindings",
]
