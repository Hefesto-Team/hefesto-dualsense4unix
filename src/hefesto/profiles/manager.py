"""Gerencia perfis em memória e coordena aplicação no controle.

Responsabilidades:
  - Listar, selecionar e aplicar perfis.
  - Atualizar o `StateStore` com o nome do perfil ativo.
  - Chamar `set_trigger` e `apply_led_settings` no controle quando um
    perfil é ativado.

Auto-switch por janela ativa fica em `hefesto.profiles.autoswitch` (W6.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from hefesto.core.controller import IController
from hefesto.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS, KeyBinding
from hefesto.core.led_control import LedSettings, apply_led_settings
from hefesto.core.trigger_effects import build_from_name
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto.profiles.schema import LedsConfig, Profile
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProfileManager:
    controller: IController
    store: StateStore = field(default_factory=StateStore)
    # FEAT-KEYBOARD-PERSISTENCE-01: referência opcional ao device virtual.
    # Quando presente, `activate()` propaga o `key_bindings` resolvido para
    # o device. Typing "Any" para evitar ciclo de import com integrations.
    keyboard_device: object | None = None

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
        if active == name:
            self.store.set_active_profile(None)
        logger.info("profile_deleted", name=name)

    def activate(self, name: str) -> Profile:
        """Carrega, aplica triggers + LEDs e marca como ativo."""
        profile = load_profile(name)
        self.apply(profile)
        self.apply_keyboard(profile)
        self.store.set_active_profile(profile.name)
        self.store.bump("profile.activated")
        logger.info("profile_activated", name=profile.name, priority=profile.priority)
        from hefesto.utils.session import save_last_profile
        save_last_profile(profile.name)
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

        No-op quando `keyboard_device` é None (CLI, testes sem daemon) ou o
        device não está ativo. Spec opção (c): método público para que a chamada
        fique explícita nos pontos que têm acesso ao device.
        """
        device = self.keyboard_device
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


def _to_key_bindings(profile: Profile) -> dict[str, KeyBinding]:
    """Resolve `Profile.key_bindings` em mapping pronto para o device.

    Regras (FEAT-KEYBOARD-PERSISTENCE-01):
    - `None` → herda `DEFAULT_BUTTON_BINDINGS` completo.
    - `{}` → vazio (teclado silencioso; usuário removeu todos os bindings).
    - dict parcial → override isolado; **não mescla com defaults**
      (spec: override é explícito; para "usar default", deixe None).

    Converte `list[str]` do schema em `tuple[str, ...]` (KeyBinding).
    """
    raw = profile.key_bindings
    if raw is None:
        return dict(DEFAULT_BUTTON_BINDINGS)
    return {button: tuple(tokens) for button, tokens in raw.items()}


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


__all__ = ["ProfileManager", "_to_key_bindings", "_to_led_settings"]
