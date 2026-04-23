"""Estado central de configuração da GUI — DraftConfig (FEAT-PROFILE-STATE-01).

``DraftConfig`` é imutável (``frozen=True`` pydantic v2). Toda mudança de
campo deve criar uma nova instância via ``model_copy(update=...)``. O objeto
é mantido em ``HefestoApp.draft`` e compartilhado por todos os *ActionsMixin.

Ciclo de vida:
- Criado em ``HefestoApp.__init__`` via ``DraftConfig.default()``.
- Populado em ``_load_draft_from_active_profile()`` após daemon conectar.
- Cada mixin lê ``self.draft.<secao>`` para popular widgets.
- Cada handler de signal substitui ``self.draft`` por ``model_copy(update=...)``.
- Aplicação atômica via IPC ``profile.apply_draft`` (método ``apply_draft``
  em ``ipc_bridge``) — consumido pela sprint UI-GLOBAL-FOOTER-ACTIONS-01.

Persistência entre sessões NÃO é escopo desta sprint; o draft é in-memory only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from hefesto.profiles.schema import Profile


# ---------------------------------------------------------------------------
# Sub-drafts (um por secao de hardware)
# ---------------------------------------------------------------------------


class TriggerDraft(BaseModel):
    """Draft de um único trigger (L2 ou R2)."""

    model_config = ConfigDict(frozen=True)

    mode: str = "Off"
    params: tuple[int, ...] = ()


class TriggersDraft(BaseModel):
    """Draft do par de triggers."""

    model_config = ConfigDict(frozen=True)

    left: TriggerDraft = Field(default_factory=TriggerDraft)
    right: TriggerDraft = Field(default_factory=TriggerDraft)


class LedsDraft(BaseModel):
    """Draft dos LEDs (lightbar + player LEDs).

    ``lightbar_rgb``: cor RGB ou None (apagado).
    ``lightbar_brightness``: 0-100 inteiro (%) — equivale a 0.0-1.0 no
        protocolo IPC (dividido por 100 antes de enviar).
    ``player_leds``: tupla de 5 booleanos (LED1..LED5).
    ``mic_led``: reservado para V2 (INFRA-SET-MIC-LED-01); default False,
        não acessado por nenhum widget desta sprint.
    """

    model_config = ConfigDict(frozen=True)

    lightbar_rgb: tuple[int, int, int] | None = (255, 128, 0)
    lightbar_brightness: int = Field(default=100, ge=0, le=100)
    player_leds: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    mic_led: bool = False  # reservado V2


class RumbleDraft(BaseModel):
    """Draft de rumble.

    ``policy``: reservado para FEAT-RUMBLE-POLICY-01; armazenado no draft
        mas sem bind de widget nesta sprint.
    """

    model_config = ConfigDict(frozen=True)

    weak: int = Field(default=0, ge=0, le=255)
    strong: int = Field(default=0, ge=0, le=255)
    policy: Literal["economia", "balanceado", "max", "auto"] = "balanceado"


class MouseDraft(BaseModel):
    """Draft da emulacao de mouse."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    speed: int = Field(default=6, ge=1, le=12)
    scroll_speed: int = Field(default=1, ge=1, le=5)


class EmulationDraft(BaseModel):
    """Draft da emulacao Xbox360."""

    model_config = ConfigDict(frozen=True)

    xbox360_enabled: bool = False


# ---------------------------------------------------------------------------
# DraftConfig raiz
# ---------------------------------------------------------------------------


class DraftConfig(BaseModel):
    """Estado central imutavel da GUI — snapshot de tudo que o daemon pode aplicar.

    Uso correto:
        self.draft = self.draft.model_copy(update={"leds": novo_leds_draft})

    Nunca mute campos diretamente — pydantic v2 frozen bloqueia, mas
    a convencao explicita e mais fácil de rastrear em code review.
    """

    model_config = ConfigDict(frozen=True)

    triggers: TriggersDraft = Field(default_factory=TriggersDraft)
    leds: LedsDraft = Field(default_factory=LedsDraft)
    rumble: RumbleDraft = Field(default_factory=RumbleDraft)
    mouse: MouseDraft = Field(default_factory=MouseDraft)
    emulation: EmulationDraft = Field(default_factory=EmulationDraft)

    # --- construtores ---

    @classmethod
    def default(cls) -> DraftConfig:
        """Instancia com valores padrão seguros (sem hardware aplicado)."""
        return cls()

    @classmethod
    def from_profile(cls, profile: Profile) -> DraftConfig:
        """Constroi DraftConfig a partir de um Profile persistido.

        Mapeia os campos do schema ``Profile`` para o draft equivalente.
        Campos ausentes no perfil recebem defaults seguros.
        """
        # Triggers
        left_cfg = profile.triggers.left
        right_cfg = profile.triggers.right
        triggers = TriggersDraft(
            left=TriggerDraft(
                mode=left_cfg.mode,
                params=tuple(left_cfg.params),
            ),
            right=TriggerDraft(
                mode=right_cfg.mode,
                params=tuple(right_cfg.params),
            ),
        )

        # LEDs
        leds_cfg = profile.leds
        rgb_raw = leds_cfg.lightbar  # tuple[int, int, int]
        brightness_raw = leds_cfg.lightbar_brightness  # float 0.0-1.0
        brightness_pct = max(0, min(100, round(brightness_raw * 100)))
        player_raw = leds_cfg.player_leds  # list[bool], len=5
        player = tuple(bool(b) for b in player_raw)
        # Garante 5 elementos (schema valida, mas defensive)
        while len(player) < 5:
            player = (*player, False)
        player_5: tuple[bool, bool, bool, bool, bool] = (
            player[0], player[1], player[2], player[3], player[4]
        )
        leds = LedsDraft(
            lightbar_rgb=(int(rgb_raw[0]), int(rgb_raw[1]), int(rgb_raw[2])),
            lightbar_brightness=brightness_pct,
            player_leds=player_5,
        )

        # Rumble — Profile.rumble so tem ``passthrough`` (sem weak/strong persistido)
        rumble = RumbleDraft()

        # Mouse e Emulacao — não presentes no Profile v1; defaults
        mouse = MouseDraft()
        emulation = EmulationDraft()

        return cls(
            triggers=triggers,
            leds=leds,
            rumble=rumble,
            mouse=mouse,
            emulation=emulation,
        )

    def to_profile(self, name: str, priority: int = 5) -> Profile:
        """Converte o draft em um Profile persistivel.

        Apenas os campos suportados pelo schema Profile v1 sao preenchidos.
        Campos extras do draft (mouse, emulation, rumble.policy) sao descartados —
        o schema não os suporta ainda.

        Retorna instancia validada via ``Profile.model_validate``.
        """
        from hefesto.profiles.schema import (
            LedsConfig,
            MatchAny,
            Profile,
            RumbleConfig,
            TriggerConfig,
            TriggersConfig,
        )

        brightness_float = self.leds.lightbar_brightness / 100.0
        rgb = self.leds.lightbar_rgb or (0, 0, 0)

        profile = Profile(
            name=name,
            priority=priority,
            match=MatchAny(),
            triggers=TriggersConfig(
                left=TriggerConfig(
                    mode=self.triggers.left.mode,
                    params=list(self.triggers.left.params),
                ),
                right=TriggerConfig(
                    mode=self.triggers.right.mode,
                    params=list(self.triggers.right.params),
                ),
            ),
            leds=LedsConfig(
                lightbar=rgb,
                player_leds=list(self.leds.player_leds),
                lightbar_brightness=brightness_float,
            ),
            rumble=RumbleConfig(),
        )
        # Revalida para garantir round-trip (captura regressoes de schema)
        return Profile.model_validate(profile.model_dump(mode="python"))

    def to_ipc_dict(self) -> dict:  # type: ignore[type-arg]
        """Serializa draft para o formato do contrato IPC ``profile.apply_draft``.

        Retorna dicionario com secoes triggers/leds/rumble/mouse.
        Campos reservados (mic_led, emulation, rumble.policy) sao omitidos
        para não causar erros em versões de daemon sem suporte.
        """
        rgb = self.leds.lightbar_rgb
        return {
            "triggers": {
                "left": {
                    "mode": self.triggers.left.mode,
                    "params": list(self.triggers.left.params),
                },
                "right": {
                    "mode": self.triggers.right.mode,
                    "params": list(self.triggers.right.params),
                },
            },
            "leds": {
                "lightbar_rgb": list(rgb) if rgb is not None else None,
                "lightbar_brightness": self.leds.lightbar_brightness / 100.0,
                "player_leds": list(self.leds.player_leds),
            },
            "rumble": {
                "weak": self.rumble.weak,
                "strong": self.rumble.strong,
            },
            "mouse": {
                "enabled": self.mouse.enabled,
                "speed": self.mouse.speed,
                "scroll_speed": self.mouse.scroll_speed,
            },
        }


__all__ = [
    "DraftConfig",
    "EmulationDraft",
    "LedsDraft",
    "MouseDraft",
    "RumbleDraft",
    "TriggerDraft",
    "TriggersDraft",
]
