"""Metadata dos onze acionamentos do gatilho pra UI dinâmica e das chaves velhas lidas."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerParamSpec:
    """Um slider da aba Gatilhos: o kwarg da factory e como ele se mostra."""

    name: str
    label: str
    min_value: int
    max_value: int
    default: int = 0


@dataclass(frozen=True)
class TriggerPresetSpec:
    name: str
    label: str
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
    return TriggerParamSpec("force", "Força", 0, 8, default)


def _strength(default: int = 4) -> TriggerParamSpec:
    return TriggerParamSpec("strength", "Intensidade", 0, 8, default)


_RAMPA_PADRAO: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7, 8, 8)


def _frequency(default: int = 10, lo: int = 0) -> TriggerParamSpec:
    return TriggerParamSpec("frequency", "Frequência", lo, 255, default)


PRESETS: tuple[TriggerPresetSpec, ...] = (
    TriggerPresetSpec(
        "Off", "Desligado", params=(),
        description="Sem resistência.",
    ),
    TriggerPresetSpec(
        "Resistance", "Resistência",
        params=(_start(0, 9, 3), _force_0_8(5)),
        description="Resistência constante a partir de uma posição.",
    ),
    TriggerPresetSpec(
        "Weapon", "Disparo",
        params=(_start(0, 9, 2), _end(1, 9, 5), _force(0, 255, 200)),
        description="Disparo de arma padrão.",
    ),
    TriggerPresetSpec(
        "Bow", "Arco",
        params=(
            TriggerParamSpec("start", "Início", 0, 8, 1),
            TriggerParamSpec("end", "Fim", 1, 9, 7),
            TriggerParamSpec("force", "Força do arco", 0, 8, 6),
            TriggerParamSpec("snap", "Disparo", 0, 8, 7),
        ),
        description="Tensão crescente com disparo ao soltar.",
    ),
    TriggerPresetSpec(
        "Galloping", "Galope",
        params=(
            TriggerParamSpec("start", "Início", 0, 8, 0),
            TriggerParamSpec("end", "Fim", 1, 9, 9),
            TriggerParamSpec("first_foot", "Pata 1", 0, 7, 7),
            TriggerParamSpec("second_foot", "Pata 2", 0, 7, 7),
            _frequency(10),
        ),
        description="Cadência de galope entre duas posições.",
    ),
    TriggerPresetSpec(
        "Machine", "Metralhadora",
        params=(
            TriggerParamSpec("start", "Início do curso", 0, 8, 2),
            TriggerParamSpec("end", "Fim do curso", 1, 9, 9),
            TriggerParamSpec("strength", "Força", 1, 8, 4),
            _frequency(40, lo=1),
        ),
        description="Batidas rápidas enquanto o gatilho está apertado.",
    ),
    TriggerPresetSpec(
        "Vibration", "Vibração",
        params=(
            _pos(3),
            TriggerParamSpec("amplitude", "Amplitude", 0, 8, 4),
            _frequency(40, lo=1),
        ),
        description="Vibração contínua com amplitude e frequência.",
    ),
    TriggerPresetSpec(
        "SlopeFeedback", "Rampa de força",
        params=(
            _start(0, 9, 1),
            _end(1, 9, 8),
            TriggerParamSpec("start_strength", "Intensidade no início", 1, 8, 2),
            TriggerParamSpec("end_strength", "Intensidade no fim", 1, 8, 7),
        ),
        description="Firmeza que varia em rampa entre duas posições.",
    ),
    TriggerPresetSpec(
        "MultiPositionFeedback", "Curva de força",
        params=tuple(
            TriggerParamSpec(
                f"pos_{i}", f"Posição {i}", 0, 8, _RAMPA_PADRAO[i]
            )
            for i in range(10)
        ),
        description="Intensidade customizada por cada uma das 10 posições.",
    ),
    TriggerPresetSpec(
        "MultiPositionVibration", "Vibração por posição",
        params=(
            _frequency(40, lo=1),
            *(
                TriggerParamSpec(
                    f"pos_{i}", f"Posição {i}", 0, 8, _RAMPA_PADRAO[i]
                )
                for i in range(10)
            ),
        ),
        description="Vibração com perfil de amplitude por posição.",
    ),
    TriggerPresetSpec(
        "Custom", "Montar do zero",
        params=(
            TriggerParamSpec("mode", "Modo (byte cru)", 0, 255, 0),
            *(
                TriggerParamSpec(
                    f"force_{i}", f"Força {i}", 0, 255, 0
                )
                for i in range(7)
            ),
        ),
        description=(
            "Avançado: envia os valores crus para o controle — 1 modo e 7 "
            "forças."
        ),
    ),
)

PRESETS_ANTIGOS: tuple[TriggerPresetSpec, ...] = (
    TriggerPresetSpec(
        "Rigid", "Rígido",
        params=(_pos(5), _force(0, 255, 200)),
        description="Barreira rígida numa posição fixa.",
    ),
    TriggerPresetSpec(
        "SimpleRigid", "Rígido simples",
        params=(_strength(6),),
        description="Atalho do Rígido, com uma só escala de 0 a 8.",
    ),
    TriggerPresetSpec(
        "Pulse", "Pulso", params=(),
        description="Pulso único.",
    ),
    TriggerPresetSpec(
        "PulseA", "Pulso (curva A)",
        params=(_start(0, 9, 2), _end(1, 9, 7), _force(0, 255, 180)),
        description="Pulso entre duas posições (curva A).",
    ),
    TriggerPresetSpec(
        "PulseB", "Pulso (curva B)",
        params=(_start(0, 9, 2), _end(1, 9, 7), _force(0, 255, 180)),
        description="Pulso entre duas posições (curva B).",
    ),
    TriggerPresetSpec(
        "SemiAutoGun", "Arma semi-automática",
        params=(
            TriggerParamSpec("start", "Início", 2, 7, 3),
            TriggerParamSpec("end", "Fim", 3, 8, 6),
            _force_0_8(5),
        ),
        description="Rebote curto de arma semi-auto.",
    ),
    TriggerPresetSpec(
        "AutoGun", "Arma automática",
        params=(
            _start(0, 9, 2),
            _strength(6),
            _frequency(60),
        ),
        description="Vibração contínua de arma automática.",
    ),
    TriggerPresetSpec(
        "Feedback", "Ponto duro",
        params=(_pos(5), _strength(4)),
        description="Barreira a partir de uma posição, com força de 0 a 8.",
    ),
)


def get_spec(name: str) -> TriggerPresetSpec | None:
    """O spec de um acionamento da lista de onze ou de uma chave velha que segue lida."""
    for spec in (*PRESETS, *PRESETS_ANTIGOS):
        if spec.name == name:
            return spec
    return None


def na_lista_de_onze(name: str, params: list[int]) -> tuple[str, list[int]]:
    """O gatilho de um perfil como a tela o mostra: a chave da lista de onze e os ajustes dela.

    Perfil antigo abre com o acionamento certo selecionado: `Rigid` aparece como Resistência,
    `AutoGun` como Metralhadora, `PulseA` como Arco. Chave que já é da lista volta como veio.
    """
    from hefesto_dualsense4unix.core.trigger_effects import traduzir_chave_velha

    traduzida = traduzir_chave_velha(name, params, para_a_tela=True)
    if traduzida is None and not params:
        spec = get_spec(name)
        if spec is not None and spec.params:
            padroes = [int(p.default) for p in spec.params]
            traduzida = traduzir_chave_velha(name, padroes, para_a_tela=True)
    if traduzida is None:
        return name, list(params)
    return traduzida


def preset_to_positional_params(spec: TriggerPresetSpec, values: dict[str, int]) -> list[int]:
    """Converte dict {param_name: valor} em lista posicional na ordem do spec."""
    return [values.get(p.name, p.default) for p in spec.params]


__all__ = [
    "PRESETS",
    "PRESETS_ANTIGOS",
    "TriggerParamSpec",
    "TriggerPresetSpec",
    "get_spec",
    "na_lista_de_onze",
    "preset_to_positional_params",
]
