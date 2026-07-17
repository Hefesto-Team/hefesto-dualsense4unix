"""Schema de perfil v1 com pydantic.

Ver `docs/adr/005-profile-schema-v1.md` para a justificativa semântica
(AND entre campos, OR dentro de listas, `MatchAny` sentinel V2-8).
"""
from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: Teto do multiplicador de rumble da política "custom". Acima de 1.0 AMPLIFICA o
#: que o jogo pediu — é a razão de existir da faixa (BUG-RUMBLE-CUSTOM-MULT-CAP-01).
#:
#: HARM-19: mora aqui, num dono só, porque a faixa já valeu 2.0 no esquema, 1.0 no
#: handler `rumble.policy_custom` e 200% no slider da GUI ao mesmo tempo — de 101%
#: em diante a usuária levava um erro de validação que a aba reportava como
#: "daemon offline?". Quem mudar o teto muda AQUI e os três seguem juntos.
RUMBLE_CUSTOM_MULT_MAX = 2.0


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
    params: list[int] | list[list[int]] = Field(default_factory=list)

    @field_validator("mode", mode="after")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        """Rejeita modos fora do conjunto canônico aceito por `build_from_name`.

        O registro de fábricas (`PRESET_FACTORIES`) é a fonte única de verdade
        dos modos válidos — inclui "Off", "Custom", "MultiPositionFeedback" etc.
        Sem esta checagem, um typo no `mode` (ex.: "Galoping") passa pela
        validação do perfil e só explode com `ValueError` lá no `apply()`, em
        runtime, longe da origem do erro. Import lazy de `core.trigger_effects`
        evita ciclo de import com `profiles.schema`.
        """
        from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES

        if value not in PRESET_FACTORIES:
            validos = ", ".join(sorted(PRESET_FACTORIES))
            raise ValueError(
                f"modo de trigger desconhecido: {value!r} "
                f"(modos válidos: {validos})"
            )
        return value

    @field_validator("params", mode="after")
    @classmethod
    def _validate_params(
        cls, value: list[int] | list[list[int]]
    ) -> list[int] | list[list[int]]:
        """Aceita dois formatos canônicos, rejeita mistura.

        - Simples: `list[int]` — todos os elementos inteiros.
        - Aninhado: `list[list[int]]` — todos os elementos são sublistas de int.

        Mistura (`[[1, 2], 3]`) é erro semântico: sinaliza JSON corrompido
        ou migração pela metade. Schema rejeita cedo, com mensagem clara.
        """
        if not value:
            return value
        first = value[0]
        if isinstance(first, list):
            for idx, item in enumerate(value):
                if not isinstance(item, list):
                    raise ValueError(
                        "params aninhado exige todos os elementos como list[int]; "
                        f"índice {idx} tem tipo {type(item).__name__}"
                    )
                for jdx, num in enumerate(item):
                    if not isinstance(num, int) or isinstance(num, bool):
                        raise ValueError(
                            f"params aninhado: elemento [{idx}][{jdx}] deve ser int, "
                            f"recebeu {type(num).__name__}"
                        )
        else:
            for idx, item in enumerate(value):
                if not isinstance(item, int) or isinstance(item, bool):
                    raise ValueError(
                        f"params simples: elemento [{idx}] deve ser int, "
                        f"recebeu {type(item).__name__}"
                    )
        return value

    @property
    def is_nested(self) -> bool:
        """True quando `params` está no formato aninhado `list[list[int]]`."""
        return bool(self.params) and isinstance(self.params[0], list)


class TriggersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))
    right: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))


class LedsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lightbar: tuple[int, int, int] = (0, 0, 0)
    player_leds: list[bool] = Field(default_factory=lambda: [False] * 5)
    lightbar_brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    # COR-03 (sprint cores-e-led-automaticos): cores automáticas por controle
    # — cada DualSense acende a cor do SEU slot (paleta PS5) + o LED do número
    # do controle (D7). Default True = o comportamento pedido pela mantenedora
    # nasce ligado; False = comportamento broadcast histórico intacto (D5).
    # Perfil antigo sem o campo valida com o default (aditivo, sem migração).
    # SÓ tem efeito na seção GLOBAL `profile.leds`: dentro de um override
    # por-controle (`ControllerOverrides.leds`) o campo é aceito pelo schema
    # (reuso do modelo) mas ignorado — o toggle é do perfil, não do controle
    # (`_controllers_to_specs` não o lê, então ele nunca densifica um
    # override parcial). ATENÇÃO downgrade: perfil salvo com este campo fica
    # inválido em binário antigo (`extra="forbid"`) — coberto nas notas de
    # release (COR-08).
    auto_player_colors: bool = True

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
    """Seção de rumble do perfil.

    FEAT-RUMBLE-POLICY-PROFILE-01: além do ``passthrough`` (v1), o perfil pode
    declarar a POLÍTICA de intensidade de rumble, aplicada na ativação em
    paridade com a seção ``mode``:

    - ``policy=None`` (default) — perfil SEM opinião: ativar não mexe na
      política global do daemon; apenas reverte política que OUTRO perfil
      tenha aplicado (ver ``Daemon.apply_profile_rumble_policy``).
    - ``policy`` preenchida — aplicada via ``rumble_policy_applier`` injetado
      no ``ProfileManager``, respeitando o lock manual de 30s.
    - ``custom_mult`` — multiplicador 0.0-2.0; só faz sentido com
      ``policy="custom"`` (validado abaixo).

    Aditivo/retrocompatível: perfis v1 sem os campos continuam válidos.
    """

    model_config = ConfigDict(extra="forbid")

    passthrough: bool = True
    policy: Literal["economia", "balanceado", "max", "auto", "custom"] | None = None
    custom_mult: float | None = None

    @model_validator(mode="after")
    def _validate_custom_mult(self) -> RumbleConfig:
        """Range de ``custom_mult`` + coerência com ``policy``.

        ``custom_mult`` fora de ``policy="custom"`` é erro semântico (o valor
        seria silenciosamente ignorado pelo daemon) — rejeitamos cedo, na
        borda do schema, com mensagem clara.
        """
        if self.custom_mult is not None:
            if not (0.0 <= self.custom_mult <= RUMBLE_CUSTOM_MULT_MAX):
                raise ValueError(
                    f"custom_mult fora de [0.0, {RUMBLE_CUSTOM_MULT_MAX}]: "
                    f"{self.custom_mult}"
                )
            if self.policy != "custom":
                raise ValueError(
                    "custom_mult só é válido com policy='custom' "
                    f"(policy={self.policy!r})"
                )
        return self


class ProfileMouseConfig(BaseModel):
    """Seção opcional de emulação de mouse por perfil (FEAT-POINT-AND-CLICK-01).

    Aditiva ao schema v1 (sem bump de versão): perfis sem a seção continuam
    válidos e NÃO tocam no estado de emulação ao serem ativados. Ranges de
    `speed`/`scroll_speed` espelham o contrato do daemon
    (`Daemon.set_mouse_emulation`: 1-12 / 1-5).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    speed: int = Field(default=6, ge=1, le=12)
    scroll_speed: int = Field(default=1, ge=1, le=5)


class ProfileModeConfig(BaseModel):
    """Seção opcional de MODO do sistema por perfil (FEAT-PROFILE-MODE-01).

    O perfil do JOGO declara como o controle deve se comportar quando ele está
    em foco — as features passam a COEXISTIR porque o contexto decide, sem
    toggles globais brigando entre si:

    - ``kind="native"`` — release total: o jogo usa os gatilhos adaptativos
      NATIVOS da Sony (Sackboy & cia); o hefesto solta o controle.
    - ``kind="gamepad"`` — gamepad virtual com a máscara `gamepad_flavor`
      (prompts PlayStation ou Xbox). Cada controle físico vira um jogador
      (``coop``, ligado por padrão — ver o campo).
    - ``kind="desktop"`` — declaração explícita de app de desktop: desliga
      gamepad/nativo/co-op vindos de perfil (e também os expirados do lock).

    Perfis SEM a seção não têm opinião: liberam apenas o modo que outro PERFIL
    tinha ligado (gesto manual da usuária é respeitado — mesma semântica do
    `suppress_desktop_emulation`). Toggles manuais recentes vencem por
    ``MANUAL_PROFILE_LOCK_SEC`` (30s), como no `mouse`.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: Literal["dualsense", "xbox"] | None = None
    # LEIGO-01: default True. Ninguém pluga dois controles esperando que os dois
    # movam o MESMO personagem — o default False fazia todo perfil salvo pela GUI
    # carregar `coop: false` e desligar o co-op ao ativar, pelas costas de quem
    # nunca pediu isso. Perfis já gravados são migrados em
    # `loader.migrate_profiles_coop_default`.
    coop: bool = True


class ControllerOverrides(BaseModel):
    """Overrides POR CONTROLE dentro do perfil (PERFIL-02, 2026-07-16).

    Subconjunto deliberado das seções do perfil que fazem sentido por
    controle físico: ``leds`` (lightbar + player_leds + brilho) e
    ``triggers``. Campo ``None`` = sem opinião — o controle herda a seção
    GLOBAL do perfil (merge POR CAMPO na aplicação, PERFIL-01: override
    parcial nunca apaga a cor global no replug).

    Fora por decisão (revisão adversarial do sprint perfis-por-controle):
    - ``label`` — identidade visível é outra frente (4P-03);
    - ``mic_led`` — o mic jamais é colateral de troca de perfil
      (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01).
    """

    model_config = ConfigDict(extra="forbid")

    leds: LedsConfig | None = None
    triggers: TriggersConfig | None = None


# Regex para tokens aceitos em `Profile.key_bindings` values (FEAT-KEYBOARD-PERSISTENCE-01).
# - `KEY_*` é validado contra `evdev.ecodes` (via lookup lazy em `_validate_key_bindings`).
# - `__*__` são tokens virtuais reservados para a sub-sprint UI (59.3): o dispatcher
#   delega ao subsystem de OSK em vez de emitir evento de tecla. Aqui aceitamos
#   pelo regex mas não validamos contra ecodes — o schema não conhece a lista fechada.
_KEY_BINDING_TOKEN_RE = re.compile(r"^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$")


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
    # FEAT-KEYBOARD-PERSISTENCE-01: override de bindings por perfil.
    # - None = herda DEFAULT_BUTTON_BINDINGS do core.
    # - {} = desativa todos os bindings do perfil (teclado silencioso).
    # - {"triangle": ["KEY_C"]} = override apenas desse botão; demais seguem default.
    key_bindings: dict[str, list[str]] | None = None
    # FEAT-POINT-AND-CLICK-01: seção opcional de emulação de mouse.
    # - None = ativar o perfil não toca no estado da emulação (comportamento v1).
    # - Preenchida = ativar o perfil liga/desliga a emulação com as velocidades
    #   dadas (via `mouse_applier` injetado no ProfileManager).
    mouse: ProfileMouseConfig | None = None
    # FEAT-PROFILE-MODE-01: modo do sistema por perfil (nativo/gamepad/desktop
    # + co-op). None = sem opinião (libera só modo vindo de outro perfil).
    mode: ProfileModeConfig | None = None
    # FEAT-POINT-AND-CLICK-01: modo-jogo por perfil. True = ativar o perfil
    # suprime a emulação de mouse/teclado no desktop (jogos de GAMEPAD que
    # leem o controle cru); False (default) = ativar o perfil LIBERA a
    # supressão apenas se ela veio de outro perfil (toggle manual da usuária
    # é respeitado — ver `Daemon.apply_profile_suppression`).
    suppress_desktop_emulation: bool = False
    # PERFIL-02 (sprint 2026-07-16-perfis-por-controle): mapa ADITIVO de
    # overrides por controle físico, keyed pelo MAC normalizado (12 hex
    # minúsculos — o mesmo `norm_mac` do backend; PROVADO ao vivo estável
    # entre USB e BT no DualSense). None = perfil v1 puro, sem opinião
    # por-controle. A serialização em `save_profile` OMITE o campo quando
    # None/vazio — requisito de compatibilidade: sem a omissão, todo save
    # gravaria `"controllers": null` e binário antigo (extra="forbid")
    # rejeitaria TODO perfil no downgrade, não só os que usam o mapa.
    controllers: dict[str, ControllerOverrides] | None = None

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name não pode ser vazio")
        if "/" in value or ".." in value or os.sep in value:
            raise ValueError(f"name contém caractere inválido: {value!r}")
        # Garante que slugify() produz slug válido — rejeita nomes exóticos
        # (só símbolos, só emoji, etc.) que virariam filename vazio.
        from hefesto_dualsense4unix.profiles.slug import slugify
        try:
            slugify(value)
        except ValueError as exc:
            raise ValueError(f"name não produz slug válido: {value!r}") from exc
        return value

    @field_validator("key_bindings")
    @classmethod
    def _validate_key_bindings(
        cls, value: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        """Rejeita tokens fora do padrão ou KEY_* inexistentes em evdev.ecodes.

        - `None` passa direto (default = herdar).
        - Values são listas de tokens; cada token casa
          `^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$`.
        - Tokens `KEY_*` são verificados contra `evdev.ecodes` via lookup lazy;
          se evdev não estiver disponível no ambiente (fallback CLI sem deps),
          aceita qualquer KEY_* bem-formado (validação completa fica para runtime).
        """
        if value is None:
            return value
        ecodes_ns: Any | None = None
        try:
            from evdev import ecodes as _ec
            ecodes_ns = _ec
        except Exception:
            ecodes_ns = None
        for button, tokens in value.items():
            if not isinstance(tokens, list):
                raise ValueError(
                    f"key_bindings[{button!r}] precisa ser lista, recebeu "
                    f"{type(tokens).__name__}"
                )
            for idx, tok in enumerate(tokens):
                if not isinstance(tok, str):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}] precisa ser str, "
                        f"recebeu {type(tok).__name__}"
                    )
                if not _KEY_BINDING_TOKEN_RE.match(tok):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}]={tok!r} não casa "
                        f"padrão 'KEY_*' ou '__TOKEN__'"
                    )
                if (
                    tok.startswith("KEY_")
                    and ecodes_ns is not None
                    and not hasattr(ecodes_ns, tok)
                ):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}]={tok!r} não existe "
                        f"em evdev.ecodes"
                    )
        return value

    @field_validator("controllers", mode="after")
    @classmethod
    def _validate_controllers_keys(
        cls, value: dict[str, ControllerOverrides] | None
    ) -> dict[str, ControllerOverrides] | None:
        """Chave do mapa = MAC normalizado (12 hex); rejeita degenerados.

        Usa o MESMO ``norm_mac`` do backend (import lazy, padrão do módulo):
        ``"AA:BB:CC:00:00:02"`` é aceito e canonizado para ``"aabbcc000002"``
        — JSON editado à mão continua casando com a key que o backend
        enumera. Rejeições, com mensagem clara:

        - o que não vira 12 dígitos hex (ex.: key de fallback ``path:...``);
        - uniq DEGENERADO, que não identifica UMA unidade — OUI ``00:00:00``
          (medido ao vivo no Pro Controller, ``000000000001``, idêntico
          entre unidades) e broadcast ``ff:ff:ff:ff:ff:ff``;
        - duas chaves que canonizam para o mesmo MAC (colisão silenciosa:
          um dos overrides venceria por ordem de inserção, sem aviso).
        """
        if value is None:
            return value
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        canonizado: dict[str, ControllerOverrides] = {}
        for key, overrides in value.items():
            mac = norm_mac(key)
            if mac is None or len(mac) != 12:
                raise ValueError(
                    f"controllers: chave {key!r} não é um MAC de 12 dígitos "
                    "hex (ex.: 'aabbcc000002')"
                )
            if mac.startswith("000000") or mac == "ffffffffffff":
                raise ValueError(
                    f"controllers: chave {key!r} é um uniq degenerado — não "
                    "identifica um controle único (visto em receivers 2.4G "
                    "e no Pro Controller)"
                )
            if mac in canonizado:
                raise ValueError(
                    "controllers: chaves duplicadas após normalização "
                    f"({mac!r}) — remova uma das grafias"
                )
            canonizado[mac] = overrides
        return canonizado

    def matches(self, window_info: dict[str, Any]) -> bool:
        return self.match.matches(window_info)


__all__ = [
    "ControllerOverrides",
    "LedsConfig",
    "Match",
    "MatchAny",
    "MatchCriteria",
    "Profile",
    "ProfileMouseConfig",
    "RumbleConfig",
    "TriggerConfig",
    "TriggersConfig",
]
