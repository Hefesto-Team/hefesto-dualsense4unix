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
        self.store.set_active_profile(profile.name)
        self.store.bump("profile.activated")
        logger.info("profile_activated", name=profile.name, priority=profile.priority)
        return profile

    def apply(self, profile: Profile) -> None:
        """Aplica triggers e LEDs do perfil no controle (sem marcar como ativo)."""
        for side, trigger in (("left", profile.triggers.left), ("right", profile.triggers.right)):
            effect = build_from_name(trigger.mode, trigger.params)
            self.controller.set_trigger(side, effect)  # type: ignore[arg-type]

        leds = profile.leds
        settings = _to_led_settings(leds)
        apply_led_settings(self.controller, settings)

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


def _to_led_settings(leds: LedsConfig) -> LedSettings:
    player_leds_tuple: tuple[bool, bool, bool, bool, bool] = (
        leds.player_leds[0],
        leds.player_leds[1],
        leds.player_leds[2],
        leds.player_leds[3],
        leds.player_leds[4],
    )
    return LedSettings(lightbar=leds.lightbar, player_leds=player_leds_tuple)


__all__ = ["ProfileManager"]
