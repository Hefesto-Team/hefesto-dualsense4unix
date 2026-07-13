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

from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from hefesto_dualsense4unix.profiles.schema import Profile


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

    ``weak``/``strong``: teste de motores (não persistem no perfil).

    ``policy``/``custom_mult``: política de intensidade persistível no PERFIL
    (FEAT-RUMBLE-POLICY-PROFILE-01). ``policy=None`` = perfil sem opinião
    (ativar não mexe na política global do daemon). A aba Rumble grava aqui
    cada escolha da usuária, para o "Salvar Perfil" do rodapé persistir o que
    ela vê; ``custom_mult`` (0.0-2.0) só acompanha ``policy="custom"``.

    ``passthrough``: preserva o campo v1 do perfil no round-trip
    (não editável pela GUI nesta sprint).
    """

    model_config = ConfigDict(frozen=True)

    weak: int = Field(default=0, ge=0, le=255)
    strong: int = Field(default=0, ge=0, le=255)
    policy: Literal["economia", "balanceado", "max", "auto", "custom"] | None = None
    custom_mult: float | None = Field(default=None, ge=0.0, le=2.0)
    passthrough: bool = True


class MouseDraft(BaseModel):
    """Draft da emulacao de mouse.

    ``dirty``: True quando a usuária TOCOU a seção nesta sessão da GUI
    (toggle ou sliders). ``to_ipc_dict`` só emite a seção mouse quando dirty —
    BUG-MOUSE-GUI-SYNC-01 (A2): o "Aplicar" com seção intocada NÃO pode
    desligar (nem persistir off) uma emulação ligada por CLI/applet.
    Sincronizações programáticas (bootstrap, refresh da aba) NÃO marcam dirty.

    ``in_profile``: True quando o perfil de origem JÁ possuía uma seção
    ``mouse`` (BUG-MOUSE-SAVE-DROPS-SECTION-01). Separa "a seção existe no
    perfil" de "a usuária tocou a seção agora" (``dirty``): sem essa distinção,
    salvar um perfil point-and-click sem mexer na aba Mouse descartava a seção
    e matava a feature. ``to_profile`` persiste a seção quando ``dirty`` OU
    ``in_profile``; o overlay do bootstrap e o refresh da aba preservam este
    flag (só atualizam enabled/speed/scroll para exibir o estado vivo).
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    speed: int = Field(default=6, ge=1, le=12)
    scroll_speed: int = Field(default=1, ge=1, le=5)
    dirty: bool = False
    in_profile: bool = False


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
    # FEAT-KEYBOARD-UI-01: bindings de teclado do perfil em edição.
    # None = herdar DEFAULT_BUTTON_BINDINGS; {} = teclado silencioso; dict
    # parcial = override explícito. Mapeia 1:1 para `Profile.key_bindings`.
    key_bindings: dict[str, list[str]] | None = None

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
        # Nota: TriggerConfig.params é Union[list[int], list[list[int]]];
        # TriggerDraft aceita ambos via tuple, mas mypy precisa cast.
        left_cfg = profile.triggers.left
        right_cfg = profile.triggers.right
        triggers = TriggersDraft(
            left=TriggerDraft(
                mode=left_cfg.mode,
                params=tuple(cast("list[int]", left_cfg.params)),
            ),
            right=TriggerDraft(
                mode=right_cfg.mode,
                params=tuple(cast("list[int]", right_cfg.params)),
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

        # Rumble — weak/strong não persistem no perfil (teste de motores);
        # a POLÍTICA persiste (FEAT-RUMBLE-POLICY-PROFILE-01): policy e
        # custom_mult vêm da seção ``rumble`` (None = perfil sem opinião) e
        # ``passthrough`` é preservado para o round-trip.
        rumble = RumbleDraft(
            policy=profile.rumble.policy,
            custom_mult=profile.rumble.custom_mult,
            passthrough=profile.rumble.passthrough,
        )

        # Mouse — FEAT-POINT-AND-CLICK-01: a seção opcional ``profile.mouse``
        # popula o draft (dirty=False: carga programática não é toque da
        # usuária). Perfil sem a seção mantém os defaults do draft.
        # BUG-MOUSE-SAVE-DROPS-SECTION-01: ``in_profile=True`` marca que o
        # perfil TINHA a seção, para ``to_profile`` preservá-la mesmo sem toque.
        if profile.mouse is not None:
            mouse = MouseDraft(
                enabled=profile.mouse.enabled,
                speed=profile.mouse.speed,
                scroll_speed=profile.mouse.scroll_speed,
                dirty=False,
                in_profile=True,
            )
        else:
            mouse = MouseDraft()
        # Emulacao (xbox360) — não presente no Profile v1; defaults
        emulation = EmulationDraft()

        return cls(
            triggers=triggers,
            leds=leds,
            rumble=rumble,
            mouse=mouse,
            emulation=emulation,
            key_bindings=profile.key_bindings,
        )

    def to_profile(self, name: str, priority: int = 5) -> Profile:
        """Converte o draft em um Profile persistivel.

        Apenas os campos suportados pelo schema Profile v1 sao preenchidos.
        FEAT-POINT-AND-CLICK-01: a seção ``mouse`` agora É suportada pelo
        schema — incluída quando ``self.mouse.dirty`` (a usuária tocou a seção
        nesta sessão) OU ``self.mouse.in_profile`` (o perfil de origem já a
        tinha). BUG-MOUSE-SAVE-DROPS-SECTION-01: sem o segundo caso, salvar um
        perfil point-and-click sem mexer na aba Mouse descartava a seção e
        matava a feature; perfis legados (sem seção) seguem round-trip
        inalterados (in_profile=False e dirty=False → sem seção fantasma).
        FEAT-RUMBLE-POLICY-PROFILE-01: a política de rumble agora É persistida
        — ``rumble.policy``/``rumble.custom_mult`` do draft vão para a seção
        ``rumble`` do perfil (None = perfil sem opinião, round-trip sem
        inventar política) e ``passthrough`` é preservado. Campos ainda sem
        suporte no schema (emulation) continuam descartados;
        ``suppress_desktop_emulation`` não é editável pelo draft (fica no
        default False do schema).

        Retorna instancia validada via ``Profile.model_validate``.
        """
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            MatchAny,
            Profile,
            ProfileMouseConfig,
            RumbleConfig,
            TriggerConfig,
            TriggersConfig,
        )

        brightness_float = self.leds.lightbar_brightness / 100.0
        rgb = self.leds.lightbar_rgb or (0, 0, 0)
        mouse_cfg = (
            ProfileMouseConfig(
                enabled=self.mouse.enabled,
                speed=self.mouse.speed,
                scroll_speed=self.mouse.scroll_speed,
            )
            if (self.mouse.dirty or self.mouse.in_profile)
            else None
        )

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
            rumble=RumbleConfig(
                passthrough=self.rumble.passthrough,
                policy=self.rumble.policy,
                custom_mult=self.rumble.custom_mult,
            ),
            key_bindings=self.key_bindings,
            mouse=mouse_cfg,
        )
        # Revalida para garantir round-trip (captura regressoes de schema)
        return Profile.model_validate(profile.model_dump(mode="python"))

    def to_ipc_dict(self) -> dict:  # type: ignore[type-arg]
        """Serializa draft para o formato do contrato IPC ``profile.apply_draft``.

        Retorna dicionario com secoes triggers/leds/rumble/mouse/keyboard.
        Campos reservados (mic_led, emulation) sao omitidos para não causar
        erros em versões de daemon sem suporte. A política de rumble
        (policy/custom_mult) também não entra aqui: ela já é aplicada na hora
        pelo IPC vivo (rumble.policy_set/policy_custom) ao mexer na aba e
        persiste via ``to_profile`` (FEAT-RUMBLE-POLICY-PROFILE-01).

        A seção ``keyboard`` é SEMPRE emitida (mesmo com ``key_bindings`` None) —
        BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: antes ``to_ipc_dict`` omitia os
        key_bindings, então o rodapé "Aplicar" nunca empurrava o teclado editado
        ao device (só ``profile.switch`` fazia). O DraftApplier resolve o inner
        ``key_bindings`` (None → DEFAULT_BUTTON_BINDINGS; dict → override). Daemon
        antigo ignora a seção desconhecida (aditivo, sem quebra de contrato).

        A seção ``mouse`` é ``None`` quando não foi tocada nesta sessão
        (``MouseDraft.dirty`` False) — o DraftApplier pula seção None
        (BUG-MOUSE-GUI-SYNC-01 A2: "Aplicar" não desliga emulação viva).
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
            "mouse": (
                {
                    "enabled": self.mouse.enabled,
                    "speed": self.mouse.speed,
                    "scroll_speed": self.mouse.scroll_speed,
                }
                if self.mouse.dirty
                else None
            ),
            "keyboard": {
                "key_bindings": (
                    {b: list(tokens) for b, tokens in self.key_bindings.items()}
                    if self.key_bindings is not None
                    else None
                ),
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
