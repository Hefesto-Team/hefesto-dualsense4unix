"""O estilo chega ao gatilho e à vibração de cada controle — 09/10/2026.

O «Guardar» da aba Gatilhos grava sempre no ajuste do controle, e no aparelho o ajuste
do controle vence o global. O estilo escrevia o gatilho e a vibração só no global:
medido com o P2 em `Rigid` próprio, depois do FPS o global era `AutoGun` e o P2 saía
`Rigid` — e a tela dizia «aplicado». A cura: o estilo é a escolha mais nova para o
perfil inteiro, e tira o gatilho e o degrau da vibração do ajuste de TODO controle do
perfil (os da mesa e os desligados), deixando o resto por controle como estava.

MORDIDA: tire a limpeza de `_com_o_estilo` e o P2 volta a sair `Rigid`.
"""
from __future__ import annotations

from typing import Any

import pytest


from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_ROTULO
from hefesto_dualsense4unix.profiles.manager import (
    _controllers_to_rumble_scales,
    _controllers_to_specs,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    ControllerRumbleOverride,
    LedsConfig,
    MatchCriteria,
    Profile,
    ProfileSpeakerConfig,
    TriggerConfig,
    TriggersConfig,
)

P1, P2, FORA = "aabbcc000001", "aabbcc000002", "aabbcc000009"
MESA = [
    {"pref": "p1", "uniq": P1, "jogador": 1, "transporte": "usb"},
    {"pref": "p2", "uniq": P2, "jogador": 2, "transporte": "bt"},
]
FPS = POR_ROTULO["FPS"]


def _rigido() -> TriggersConfig:
    lado = TriggerConfig(mode="Rigid", params=[5, 200])
    return TriggersConfig(left=lado, right=lado)


def _perfil() -> Profile:
    """Gatilho global `Off`; o P2 e um controle desligado com gatilho e degrau próprios."""
    return Profile(
        name="Tiro",
        match=MatchCriteria(window_class=["tiro"]),
        triggers=TriggersConfig(),
        controllers={
            P2: ControllerOverrides(
                triggers=_rigido(),
                rumble=ControllerRumbleOverride(policy="economia", motor_forte_pct=70),
                speaker=ProfileSpeakerConfig(volume=40),
                mic=ControllerMicOverride(muted=True),
            ),
            FORA: ControllerOverrides(
                triggers=_rigido(),
                rumble=ControllerRumbleOverride(policy="custom", custom_mult=1.2),
                leds=LedsConfig(lightbar=(10, 20, 30)),
            ),
        },
    )


def test_o_estilo_vale_no_gatilho_de_cada_controle() -> None:
    """Os dois herdam o gatilho do FPS: nenhum `OutputSpec` traz gatilho próprio."""
    novo, _ = a10_perfis._com_o_estilo(_perfil(), FPS, MESA)

    assert novo.triggers.right.mode == FPS.gatilho
    specs = _controllers_to_specs(novo.controllers, novo.leds)
    for uniq in (P2, FORA):
        spec = specs.get(uniq)
        direito = getattr(spec, "trigger_right", None)
        esquerdo = getattr(spec, "trigger_left", None)
        assert direito is None and esquerdo is None, (
            f"{uniq}: o controle ainda tem gatilho próprio ({direito!r}), e o FPS "
            f"ficou só no global")
        cfg = novo.controllers.get(uniq)
        assert cfg is None or "triggers" not in cfg.model_fields_set, (
            f"{uniq}: `triggers` ficou no ajuste do controle")


def test_o_estilo_vale_na_vibracao_de_cada_controle() -> None:
    """O degrau dos dois é o do estilo (herdado), e não o `economia`/`custom` antigo."""
    novo, _ = a10_perfis._com_o_estilo(_perfil(), FPS, MESA)

    assert novo.rumble.policy == FPS.vibracao
    assert _controllers_to_rumble_scales(novo.controllers, novo.rumble) == {}, (
        "um controle ainda escala a vibração pelo degrau próprio")
    for uniq in (P2, FORA):
        rumble = getattr(novo.controllers.get(uniq), "rumble", None)
        campos = rumble.model_fields_set if rumble is not None else set()
        assert not {"policy", "custom_mult"} & campos, (
            f"{uniq}: o degrau próprio ficou no disco ({campos})")


def test_o_resto_por_controle_fica() -> None:
    """Luz, som, microfone e o equilíbrio dos motores não são do estilo."""
    novo, pintados = a10_perfis._com_o_estilo(_perfil(), FPS, MESA)

    assert pintados == 2
    p2 = novo.controllers[P2]
    assert p2.rumble is not None and p2.rumble.motor_forte_pct == 70
    assert "motor_forte_pct" in p2.rumble.model_fields_set
    assert p2.speaker is not None and p2.speaker.volume == 40
    assert p2.mic is not None and p2.mic.muted is True
    assert p2.leds is not None and "lightbar" in p2.leds.model_fields_set
    fora = novo.controllers[FORA]
    assert fora.leds is not None and fora.leds.lightbar == (10, 20, 30), (
        "a luz do controle desligado mudou: o estilo só pinta quem está na mesa")


def test_o_disco_guarda_o_ajuste_sem_opiniao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pelo gesto e pelo disco: o `.json` do P2 fica sem `triggers` e sem `policy`."""
    loader.save_profile(_perfil(), origem="régua")
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Tiro", raising=False)

    class Ponte:
        def chamar(self, *a: Any, **kw: Any) -> Any:
            return True

        def profile_reaplicar(self, *a: Any, **kw: Any) -> bool:
            return True

    ctx = Contexto(state={"active_profile": None}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    resposta = a10_perfis.editor_estilo(ctx, {"valor": FPS.rotulo}, Ponte())

    dados = loader.load_profile("Tiro").controllers
    assert "triggers" not in dados[P2].model_fields_set
    assert dados[P2].rumble is not None
    assert dados[P2].rumble.model_fields_set == {"motor_forte_pct"}
    assert "triggers" not in dados[FORA].model_fields_set
    assert "2 controles deixaram o ajuste próprio" in str(resposta), (
        f"o relato não diz quantos controles deixaram o ajuste: {resposta!r}")
