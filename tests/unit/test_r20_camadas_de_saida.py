"""R-20 (auditoria 23/07) — saída resolvida por CAMADAS COM DONO, não por
substituição do mapa inteiro.

Achados fechados:
  - **C5** `ativacao-de-perfil-apaga-overrides-por-controle`: `manager.apply`
    chamava `reset_output_overrides`, que SUBSTITUÍA o mapa `_desired_by_uniq`
    inteiro. Como o autoswitch ativa perfil a cada troca de janela, o ajuste
    por-controle que a usuária acabara de fazer sumia segundos depois.
  - `brilho-por-controle-materializa-cor-global`: um override que só mexia no
    brilho virava cor materializada (o RGB global escalado) e, como override
    vence a camada automática, MATAVA a cor do slot daquele controle.

Cada teste PROVA a regressão: reverter o fix (voltar `reset_profile_overrides`
para a substituição do mapa, ou materializar o brilho em cor) faz a asserção
falhar. Backend REAL (`PyDualSenseController`, handles stub) — o merge por
campo do hotplug (PERFIL-01/04/05) é o mesmo, provado ao vivo, e não pode
quebrar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.led_control import LedSettings, player_slot_color
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.daemon.subsystems.identity import make_auto_output_provider
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)
from tests.unit.test_auto_player_colors import _backend_com_dois, _FakeLedNode
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _backend() -> tuple[Any, Any, Any]:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}
    inst._primary_key = KEY_1
    return inst, h1, h2


def _profile(name: str, **kw: Any) -> Profile:
    base: dict[str, Any] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "leds": LedsConfig(lightbar=(10, 20, 30)),
    }
    base.update(kw)
    return Profile(name=name, **base)


def test_ativacao_autoswitch_nao_apaga_override_da_usuaria(
    isolated_profiles_dir: Path,
) -> None:
    """O coração do C5: ela ajustou o Controle 2 na GUI; o autoswitch reativa"""
    save_profile(_profile("shooter"))
    backend, _h1, h2 = _backend()

    backend.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.apply(_profile("shooter"), origin="autoswitch")

    assert backend._desired_by_uniq[UNIQ_2].led == (0, 255, 0)
    assert h2.light.colors[-1] == (0, 255, 0)


def test_perfil_cede_o_campo_ajustado_e_pinta_o_resto(
    isolated_profiles_dir: Path,
) -> None:
    """A camada do perfil só ocupa o slot VAGO: cede o campo que a usuária"""
    save_profile(_profile("shooter"))
    backend, h1, h2 = _backend()
    backend.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.apply(_profile("shooter"), origin="autoswitch")

    assert h1.light.colors[-1] == (10, 20, 30)
    assert h2.light.colors[-1] == (0, 255, 0)


def test_troca_manual_de_perfil_solta_a_camada_da_usuaria(
    isolated_profiles_dir: Path,
) -> None:
    """Botão de soltar: escolher um perfil na GUI (origin="manual") é gesto"""
    save_profile(_profile("shooter"))
    backend, _h1, h2 = _backend()
    backend.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.apply(_profile("shooter"), origin="manual")

    assert h2.light.colors[-1] == (10, 20, 30)
    assert UNIQ_2 not in backend._desired_by_uniq


def test_override_de_perfil_e_substituido_entre_perfis(
    isolated_profiles_dir: Path,
) -> None:
    """PERFIL-05 preservado: override que é do PERFIL (não da usuária) é"""
    save_profile(
        _profile(
            "a",
            controllers={
                UNIQ_2: ControllerOverrides(leds=LedsConfig(lightbar=(0, 0, 255)))
            },
        )
    )
    save_profile(_profile("b"))
    backend, _h1, h2 = _backend()
    manager = ProfileManager(controller=backend, store=StateStore())

    manager.apply(_profile("a", controllers={
        UNIQ_2: ControllerOverrides(leds=LedsConfig(lightbar=(0, 0, 255)))
    }), origin="autoswitch")
    assert h2.light.colors[-1] == (0, 0, 255)

    manager.apply(_profile("b"), origin="autoswitch")
    assert h2.light.colors[-1] == (10, 20, 30)
    assert UNIQ_2 not in backend._desired_by_uniq


def test_apply_de_perfil_default_auto_preserva_ajuste_manual(
    isolated_profiles_dir: Path,
) -> None:
    """Caso ao vivo (queixa 2): perfil catch-all sem overrides, reativado pelo"""
    save_profile(Profile(name="vitoria", match=MatchAny(),
                         leds=LedsConfig(lightbar=(50, 50, 50))))
    backend, _h1, h2 = _backend()
    backend.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))

    manager = ProfileManager(controller=backend, store=StateStore())
    for _ in range(5):
        manager.apply(
            Profile(name="vitoria", match=MatchAny(),
                   leds=LedsConfig(lightbar=(50, 50, 50))),
            origin="autoswitch",
        )

    assert backend._desired_by_uniq[UNIQ_2].led == (0, 255, 0)
    assert h2.light.colors[-1] == (0, 255, 0)


def _backend_com_auto() -> tuple[Any, Any, Any]:
    """Backend real com nós sysfs falsos + provider de cor automática ligado."""
    inst, _h1, _h2 = _backend_com_dois()
    n1, n2 = _FakeLedNode("/fake/led1"), _FakeLedNode("/fake/led2")
    inst._sysfs = {KEY_1: n1, KEY_2: n2}
    identity.reset_identity_registry()
    reg = identity.get_identity_registry()
    reg.configure(enabled=True, brightness=1.0)
    inst.set_auto_output_provider(make_auto_output_provider(reg))
    return inst, n1, n2


def test_brilho_only_nao_materializa_cor_global(
    isolated_profiles_dir: Path,
) -> None:
    """O achado `brilho-por-controle-materializa-cor-global`: ajustar SÓ o"""


    try:
        inst, _n1, n2 = _backend_com_auto()
        profile = Profile(
            name="vitoria",
            match=MatchAny(),
            leds=LedsConfig(lightbar=(129, 61, 156), lightbar_brightness=1.0),
            controllers={
                UNIQ_2: ControllerOverrides(
                    leds=LedsConfig.model_validate({"lightbar_brightness": 0.5})
                )
            },
        )
        ProfileManager(controller=inst, store=StateStore()).apply(
            profile, origin="autoswitch"
        )

        esperado = LedSettings(lightbar=player_slot_color(2)).apply_brightness(0.5).lightbar
        assert n2.colors[-1] == esperado
        residual = inst._desired_by_uniq.get(UNIQ_2)
        assert residual is None or residual.led is None
    finally:
        identity.reset_identity_registry()


def test_escala_de_brilho_convive_com_override_de_cor(
    isolated_profiles_dir: Path,
) -> None:
    """Controle A com override de COR + controle B com override só de BRILHO:"""


    try:
        inst, n1, n2 = _backend_com_auto()
        profile = Profile(
            name="vitoria",
            match=MatchAny(),
            leds=LedsConfig(lightbar=(129, 61, 156), lightbar_brightness=1.0),
            controllers={
                UNIQ_1: ControllerOverrides(
                    leds=LedsConfig(lightbar=(200, 200, 200))
                ),
                UNIQ_2: ControllerOverrides(
                    leds=LedsConfig.model_validate({"lightbar_brightness": 0.5})
                ),
            },
        )
        ProfileManager(controller=inst, store=StateStore()).apply(
            profile, origin="autoswitch"
        )

        assert n1.colors[-1] == (200, 200, 200)
        assert n2.colors[-1] == (
            LedSettings(lightbar=player_slot_color(2)).apply_brightness(0.5).lightbar
        )
    finally:
        identity.reset_identity_registry()


def test_brilho_zero_global_ainda_materializa(
    isolated_profiles_dir: Path,
) -> None:
    """Caso degenerado documentado (`_brilho_materializa_cor`): com brilho"""
    inst, _h1, _h2 = _backend()
    profile = Profile(
        name="v",
        match=MatchAny(),
        leds=LedsConfig(lightbar=(100, 100, 100), lightbar_brightness=0.0),
        controllers={
            UNIQ_2: ControllerOverrides(
                leds=LedsConfig.model_validate({"lightbar_brightness": 0.0})
            )
        },
    )
    ProfileManager(controller=inst, store=StateStore()).apply(
        profile, origin="autoswitch"
    )
    assert inst._desired_by_uniq[UNIQ_2].led == (0, 0, 0)


def test_set_led_scales_sem_mac_e_ignorado_com_log(
    isolated_profiles_dir: Path,
) -> None:
    """Escala com key sem MAC (path:) fica fora do mapa, com log — mesma regra"""
    inst, _h1, _h2 = _backend()
    inst.set_led_scales({"path:/dev/hidraw9": 0.5})
    assert inst._led_scale_by_uniq == {}
