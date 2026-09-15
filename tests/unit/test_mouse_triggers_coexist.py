"""Coexistência entre emulação de mouse e triggers manuais (BUG-MOUSE-TRIGGERS-01).

Reproduz o bug reportado na issue #69: usuário aplica efeito de gatilho
(ex.: Galloping no R2) via aba Gatilhos, depois liga o toggle da aba Mouse;
o cursor passa a responder, mas o gatilho volta a `Off` ou deixa de atuar.

Causa raiz identificada: mover o cursor via emulação de mouse muda o foco
de janela X11 -> o `AutoSwitcher` reavalia o perfil e reaplica o `fallback`
(que tem `triggers.{left,right} = "Off"`), pisando no trigger manual.

A CURA DE 2026-07 ERA A TRAVA MANUAL, E ELA SAIU EM 14/09/2026
---------------------------------------------------------------

`trigger.set` marcava `store.manual_trigger_active = True`, e enquanto estivesse
ligado o `AutoSwitcher._activate` não reaplicava perfil por mudança de janela.
Ela revogou o mecanismo para todo jogo
(`D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO`; a razão, o journal e a régua
estão em `tests/unit/test_a_trava_que_ninguem_solta_01.py`), e os SEIS testes que
mediam a trava saíram deste arquivo com ela.

O QUE PROTEGE A ISSUE #69 HOJE, e por que a decisão dela não a reabre: o gatilho
que ela aplica pela interface vai para o PERFIL no mesmo gesto (decisão dela,
*"clicar já aplica e já grava"*), então o perfil reaplicado traz o gatilho dela em
vez de pisá-lo. A trava protegia o ajuste num mundo em que ele não era gravado.

O QUE FICA MEDIDO AQUI é a outra metade da investigação daquela issue, e ela não
dependia da trava: **o dispatch do mouse não toca o controle**. Era a hipótese 2
do spec, e continua sendo a única linha de defesa contra o mouse escrever output
por engano.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController, FakeControllerCommand


# 6 TESTES DESTE ARQUIVO SAÍRAM — 14/09/2026,
# `D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO`:
# `test_autoswitch_suspende_quando_override_manual_ligado`,
# `test_autoswitch_volta_a_funcionar_apos_clear_override`,
# `test_ipc_profile_switch_zera_override`,
# `test_ipc_trigger_reset_zera_override`,
# `test_ipc_trigger_set_marca_override`,
# `test_state_store_manual_trigger_lifecycle`.
#
# Os 6 mediam a trava manual por categoria, que ela revogou para todo jogo.
# A razão, o journal que mediu o sintoma e a régua que impede a volta estão em
# `tests/unit/test_a_trava_que_ninguem_solta_01.py`.
# --- infra ---------------------------------------------------------------


def _fake_uinput_module() -> MagicMock:
    """Módulo uinput fake com constantes mínimas para os emits."""
    mod = MagicMock()
    for name in (
        "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
        "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    ):
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


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


# --- contrato 1: dispatch do mouse não mexe em triggers ------------------


def test_mouse_dispatch_nao_chama_set_trigger_no_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UinputMouseDevice.dispatch N vezes: zero side-effects em triggers.

    Bate direto na hipótese 2 do spec BUG-MOUSE-TRIGGERS-01: prova via
    assert que o path de dispatch do mouse não toca o controle pelos
    caminhos de output (set_trigger, set_led, set_rumble).
    """
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    fc = FakeController()
    fc.connect()

    # Aplica um trigger manual ANTES de ligar o mouse — simula sequência
    # do usuário na GUI.
    effect: TriggerEffect = build_from_name("Galloping", [0, 9, 7, 7, 10])
    fc.set_trigger("right", effect)

    mouse = UinputMouseDevice()
    assert mouse.start() is True

    # N ticks de dispatch com stick fora de deadzone + triggers pressionados
    # (valores que cruzariam TRIGGER_PRESS_THRESHOLD).
    for tick in range(120):
        mouse.dispatch(
            lx=200,
            ly=60,
            rx=128,
            ry=128,
            l2=100,
            r2=200,
            buttons=frozenset({"cross", "dpad_up"}),
            now=0.1 * tick,
        )

    # Conta set_trigger nos comandos do controller. Deve haver exatamente 1
    # (o aplicado antes do loop). Nenhum extra emitido pelo dispatch.
    trigger_cmds = [
        c for c in fc.commands
        if isinstance(c, FakeControllerCommand) and c.kind == "set_trigger"
    ]
    assert len(trigger_cmds) == 1, (
        f"UinputMouseDevice.dispatch chamou set_trigger como side-effect "
        f"(hipótese 2 confirmada). Comandos: {trigger_cmds!r}"
    )
    # E também nem set_led, nem set_rumble.
    for kind in ("set_led", "set_rumble"):
        extras = [c for c in fc.commands if c.kind == kind]
        assert not extras, f"{kind} foi chamado pelo dispatch: {extras!r}"


# --- contrato 2: autoswitch respeita override manual ---------------------


def _mk_profile_with_trigger(name: str, wm_class: list[str] | None = None) -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=wm_class or [f"{name}_class"]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def _mk_fallback_off() -> Profile:
    return Profile(
        name="fallback",
        match=MatchAny(),
        priority=-1000,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        leds=LedsConfig(lightbar=(40, 40, 40)),
    )








# --- contrato 3: IPC hooks marcam/zeram a flag ---------------------------








# "Consciência do próprio estado é o primeiro passo para evitar cair em
# contradição consigo mesmo." — Sócrates (parafraseado)
