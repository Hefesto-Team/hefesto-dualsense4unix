"""Metadata dos 19 presets de trigger pra UI dinâmica.

Cada preset expõe uma lista de parâmetros nomeados. A aba Triggers usa
essa metadata pra montar sliders Gtk.Scale dinamicamente quando o
usuário troca o preset no dropdown.

A lista é baseada em `docs/protocol/trigger-modes.md` e o registro em
`hefesto.core.trigger_effects.PRESET_FACTORIES`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerParamSpec:
    name: str          # nome do kwarg na factory
    label: str         # rótulo visível
    min_value: int
    max_value: int
    default: int = 0
    help_text: str = ""


@dataclass(frozen=True)
class TriggerPresetSpec:
    name: str                       # chave usada em PRESET_FACTORIES
    label: str                      # rótulo visível no dropdown
    params: tuple[TriggerParamSpec, ...]
    description: str = ""


def _pos(default: int = 0) -> TriggerParamSpec:
    return TriggerParamSpec("position", "Posição", 0, 9, default)


def _start(lo: int = 0, hi: int = 9, default: int = 0) -> TriggerParamSpec:
    return TriggerParamSpec("start", "Início", lo, hi, default)


def _end(lo: int = 1, hi: int = 9, default: int = 9) -> TriggerParamSpec:
    return TriggerParamSpec("end", "Fim", lo, hi, default)


def _force(lo: int = 0, hi: int = 255, default: int = 128) -> TriggerParamSpec:
    return TriggerParamSpec("force", "Força", lo, hi, default)


def _force_0_8(default: int = 4) -> TriggerParamSpec:
    return TriggerParamSpec("force", "Força (0-8)", 0, 8, default)


def _strength(default: int = 4) -> TriggerParamSpec:
    return TriggerParamSpec("strength", "Intensidade (0-8)", 0, 8, default)


def _frequency(default: int = 10) -> TriggerParamSpec:
    return TriggerParamSpec("frequency", "Frequência", 0, 255, default)


PRESETS: tuple[TriggerPresetSpec, ...] = (
    TriggerPresetSpec(
        "Off", "Desligado", params=(),
        description="Sem resistência.",
    ),
    TriggerPresetSpec(
        "Rigid", "Rígido (Rigid)",
        params=(_pos(5), _force(0, 255, 200)),
        description="Barreira rígida numa posição fixa.",
    ),
    TriggerPresetSpec(
        "SimpleRigid", "Rígido simples",
        params=(_strength(6),),
        description="Atalho de Rigid em escala 0-8.",
    ),
    TriggerPresetSpec(
        "Pulse", "Pulso", params=(),
        description="Pulso único.",
    ),
    TriggerPresetSpec(
        "PulseA", "Pulso A",
        params=(_start(0, 9, 2), _end(1, 9, 7), _force(0, 255, 180)),
        description="Pulso entre duas posições (curva A).",
    ),
    TriggerPresetSpec(
        "PulseB", "Pulso B",
        params=(_start(0, 9, 2), _end(1, 9, 7), _force(0, 255, 180)),
        description="Pulso entre duas posições (curva B).",
    ),
    TriggerPresetSpec(
        "Resistance", "Resistência",
        params=(_start(0, 9, 3), _force_0_8(5)),
        description="Resistência constante a partir de uma posição.",
    ),
    TriggerPresetSpec(
        "Bow", "Arco (Bow)",
        params=(
            TriggerParamSpec("start", "Início", 0, 8, 1),
            TriggerParamSpec("end", "Fim", 1, 9, 7),
            TriggerParamSpec("force", "Força arco (0-8)", 0, 8, 6),
            TriggerParamSpec("snap", "Disparo (0-8)", 0, 8, 7),
        ),
        description="Tensão crescente com disparo ao soltar.",
    ),
    TriggerPresetSpec(
        "Galloping", "Galope (Galloping)",
        params=(
            TriggerParamSpec("start", "Início", 0, 8, 0),
            TriggerParamSpec("end", "Fim", 1, 9, 9),
            TriggerParamSpec("first_foot", "Pata 1 (0-7)", 0, 7, 7),
            TriggerParamSpec("second_foot", "Pata 2 (0-7)", 0, 7, 7),
            _frequency(10),
        ),
        description="Cadência de galope entre duas posições.",
    ),
    TriggerPresetSpec(
        "SemiAutoGun", "Arma semi-automática",
        params=(
            TriggerParamSpec("start", "Início (2-7)", 2, 7, 3),
            TriggerParamSpec("end", "Fim (start+1..8)", 3, 8, 6),
            _force_0_8(5),
        ),
        description="Rebote curto de arma semi-auto.",
    ),
    TriggerPresetSpec(
        "AutoGun", "Arma automática",
        params=(
            _pos(2),
            _strength(6),
            _frequency(60),
        ),
        description="Vibração contínua de arma automática.",
    ),
    TriggerPresetSpec(
        "Machine", "Metralhadora (Machine)",
        params=(
            _start(0, 9, 0),
            _end(1, 9, 9),
            TriggerParamSpec("amp_a", "Amplitude A", 0, 255, 3),
            TriggerParamSpec("amp_b", "Amplitude B", 0, 255, 3),
            _frequency(50),
            TriggerParamSpec("period", "Período", 0, 255, 8),
        ),
        description="Metralhadora com dois picos de amplitude.",
    ),
    TriggerPresetSpec(
        "Feedback", "Feedback",
        params=(_pos(5), _strength(4)),
        description="Feedback simples em posição específica.",
    ),
    TriggerPresetSpec(
        "Weapon", "Arma (Weapon)",
        params=(_start(0, 9, 2), _end(1, 9, 5), _force(0, 255, 200)),
        description="Disparo de arma padrão.",
    ),
    TriggerPresetSpec(
        "Vibration", "Vibração",
        params=(_pos(3), TriggerParamSpec("amplitude", "Amplitude (0-8)", 0, 8, 4), _frequency(40)),
        description="Vibração contínua com amplitude e frequência.",
    ),
    TriggerPresetSpec(
        "SlopeFeedback", "Feedback em rampa",
        params=(
            _start(0, 9, 1),
            _end(1, 9, 8),
            TriggerParamSpec("start_strength", "Intensidade início (1-8)", 1, 8, 2),
            TriggerParamSpec("end_strength", "Intensidade fim (1-8)", 1, 8, 7),
        ),
        description="Feedback com intensidade variando em rampa.",
    ),
    TriggerPresetSpec(
        "MultiPositionFeedback", "Feedback por posição",
        params=tuple(
            TriggerParamSpec(
                f"pos_{i}", f"Pos {i} (0-8)", 0, 8, 0
            )
            for i in range(10)
        ),
        description="Intensidade customizada por cada uma das 10 posições.",
    ),
    TriggerPresetSpec(
        "MultiPositionVibration", "Vibração por posição",
        params=(
            _frequency(40),
            *(
                TriggerParamSpec(
                    f"pos_{i}", f"Pos {i} (0-8)", 0, 8, 0
                )
                for i in range(10)
            ),
        ),
        description="Vibração com perfil de amplitude por posição.",
    ),
    TriggerPresetSpec(
        "Custom", "Custom (raw HID)",
        params=(
            TriggerParamSpec("mode", "Mode HID (byte)", 0, 255, 0),
            *(
                TriggerParamSpec(
                    f"force_{i}", f"Force {i}", 0, 255, 0
                )
                for i in range(7)
            ),
        ),
        description="Envia valores HID crus (mode + 7 forces).",
    ),
)


def get_spec(name: str) -> TriggerPresetSpec | None:
    for spec in PRESETS:
        if spec.name == name:
            return spec
    return None


def preset_to_positional_params(spec: TriggerPresetSpec, values: dict[str, int]) -> list[int]:
    """Converte dict {param_name: valor} em lista posicional na ordem do spec."""
    return [values.get(p.name, p.default) for p in spec.params]


# ---------------------------------------------------------------------------
# Adapter pra presets que exigem coleções (multi_position_*):
# converter dict com chaves pos_0..pos_9 em lista única.
# ---------------------------------------------------------------------------


def preset_to_factory_args(
    spec: TriggerPresetSpec, values: dict[str, int]
) -> dict[str, object] | list[int]:
    """Formato aceito por `build_from_name`: positional list ou dict nomeado.

    Para multi_position_*: monta a lista `strengths`. Para Custom: monta
    `forces` tupla. Demais: positional list respeitando a ordem dos params.
    """
    if spec.name == "MultiPositionFeedback":
        strengths = [values.get(f"pos_{i}", 0) for i in range(10)]
        return {"strengths": strengths}
    if spec.name == "MultiPositionVibration":
        strengths = [values.get(f"pos_{i}", 0) for i in range(10)]
        return {
            "frequency": values.get("frequency", 0),
            "strengths": strengths,
        }
    if spec.name == "Custom":
        forces = tuple(values.get(f"force_{i}", 0) for i in range(7))
        return {"mode": values.get("mode", 0), "forces": forces}
    return preset_to_positional_params(spec, values)


__all__ = [
    "PRESETS",
    "TriggerParamSpec",
    "TriggerPresetSpec",
    "get_spec",
    "preset_to_factory_args",
    "preset_to_positional_params",
]
