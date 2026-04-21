"""Schema de perfil v1 com pydantic.

Ver `docs/adr/005-profile-schema-v1.md` para a justificativa semântica
(AND entre campos, OR dentro de listas, `MatchAny` sentinel V2-8).
"""
from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchCriteria(BaseModel):
    """Casamento por critérios específicos (V2-8, V2-10).

    - AND entre campos preenchidos.
    - OR dentro de cada lista.
    - Campos None/[] são ignorados na avaliação.
    - `window_title_regex` usa `re.search` (V2-10); padrões com `.*`
      continuam válidos mas redundantes.
    - `process_name` casa com basename de `/proc/PID/exe` (V2-9).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["criteria"] = "criteria"
    window_class: list[str] = Field(default_factory=list)
    window_title_regex: str | None = None
    process_name: list[str] = Field(default_factory=list)

    def matches(self, window_info: dict[str, Any]) -> bool:
        conditions: list[bool] = []
        if self.window_class:
            conditions.append(window_info.get("wm_class", "") in self.window_class)
        if self.window_title_regex:
            pattern = self.window_title_regex
            title = window_info.get("wm_name", "") or ""
            conditions.append(bool(re.search(pattern, title)))
        if self.process_name:
            conditions.append(window_info.get("exe_basename", "") in self.process_name)
        if not conditions:
            return False
        return all(conditions)


class MatchAny(BaseModel):
    """Sentinel explícito para o perfil fallback (V2-8)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["any"] = "any"

    def matches(self, window_info: dict[str, Any]) -> bool:
        return True


Match = MatchCriteria | MatchAny


class TriggerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    params: list[int] = Field(default_factory=list)


class TriggersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))
    right: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))


class LedsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lightbar: tuple[int, int, int] = (0, 0, 0)
    player_leds: list[bool] = Field(default_factory=lambda: [False] * 5)

    @field_validator("lightbar")
    @classmethod
    def _rgb_bytes(cls, value: tuple[int, int, int]) -> tuple[int, int, int]:
        if len(value) != 3:
            raise ValueError("lightbar precisa 3 componentes")
        for idx, b in enumerate(value):
            if not (0 <= b <= 255):
                raise ValueError(f"lightbar[{idx}] fora de byte: {b}")
        return value

    @field_validator("player_leds")
    @classmethod
    def _player_leds_len(cls, value: list[bool]) -> list[bool]:
        if len(value) != 5:
            raise ValueError(f"player_leds precisa 5 flags, recebeu {len(value)}")
        return value


class RumbleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passthrough: bool = True


class Profile(BaseModel):
    """Perfil v1 (ADR-005)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: Literal[1] = 1
    match: Match = Field(discriminator="type")
    priority: int = 0
    triggers: TriggersConfig = Field(default_factory=TriggersConfig)
    leds: LedsConfig = Field(default_factory=LedsConfig)
    rumble: RumbleConfig = Field(default_factory=RumbleConfig)

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name nao pode ser vazio")
        if "/" in value or ".." in value or os.sep in value:
            raise ValueError(f"name contem caractere invalido: {value!r}")
        return value

    def matches(self, window_info: dict[str, Any]) -> bool:
        return self.match.matches(window_info)


__all__ = [
    "LedsConfig",
    "Match",
    "MatchAny",
    "MatchCriteria",
    "Profile",
    "RumbleConfig",
    "TriggerConfig",
    "TriggersConfig",
]
