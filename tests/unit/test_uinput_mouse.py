"""Testes do UinputMouseDevice (FEAT-MOUSE-01 / FEAT-MOUSE-CURSOR-FEEL-01)."""
from __future__ import annotations

import builtins
import itertools
import math
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DEFAULT_MOUSE_SPEED,
    DEFAULT_POLL_HZ,
    DEFAULT_SCROLL_SPEED,
    DEVICE_NAME,
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
    MOUSE_EXPO,
    MOUSE_PX_PER_SEC_STEP,
    MOVE_DEADZONE,
    SCROLL_DEADZONE,
    SCROLL_RATE_LIMIT_SEC,
    TOUCHPAD_SENSITIVITY,
    TRIGGER_PRESS_THRESHOLD,
    UinputMouseDevice,
    _compute_move_px_per_sec,
    _compute_scroll_step,
)


def _fake_uinput_module() -> MagicMock:
    """Fabrica um módulo uinput fake com constantes suficientes para todos os emits."""
    mod = MagicMock()
    # BUG-TEST-UINPUT-HASH-COLLISION-01: códigos por ÍNDICE sequencial, não
    # `hash(name) & 0xFFFF` — hash() de str é randomizado por processo
    # (PYTHONHASHSEED), então dois códigos podiam colidir (ex.: REL_X == REL_Y)
    # e quebrar os filtros _emits_for de forma flaky não-diagnosticável. O índice
    # garante unicidade determinística.
    for i, name in enumerate(
        (
            "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
            "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
            "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
            "KEY_ENTER", "KEY_ESC",
        )
    ):
        setattr(mod, name, (1, i))
    return mod


def _started_device(
    monkeypatch: pytest.MonkeyPatch,
    poll_hz: int = DEFAULT_POLL_HZ,
) -> tuple[UinputMouseDevice, MagicMock, MagicMock]:
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)
    dev = UinputMouseDevice(poll_hz=poll_hz)
    assert dev.start() is True
    return dev, fake_mod, fake_device


def _rel_sum(fake_device: MagicMock, code: Any) -> int:
    """Soma os valores emitidos em REL_X/REL_Y para o código dado."""
    return sum(
        c[1][1] for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == code
    )


def _emits_for(fake_device: MagicMock, code: Any) -> list:
    """Extrai lista de chamadas `emit(code, value, ...)` para o código dado."""
    return [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == code
    ]


# --- configuração / constantes -----------------------------------------------

def test_constantes_default_coerentes():
    assert DEFAULT_MOUSE_SPEED == 6
    assert DEFAULT_SCROLL_SPEED == 1
    assert MOVE_DEADZONE == 20
    assert SCROLL_DEADZONE == 40
    assert SCROLL_RATE_LIMIT_SEC == 0.050
    assert TRIGGER_PRESS_THRESHOLD == 64
    # FEAT-MOUSE-CURSOR-FEEL-01 — constantes do pipeline float (da spec).
    assert MOUSE_EXPO == 1.6
    assert MOUSE_PX_PER_SEC_STEP == 125.0
    assert DEFAULT_POLL_HZ == 60
    assert "Hefesto - Dualsense4Unix" in DEVICE_NAME


def test_button_map_canonico():
    assert BUTTON_TO_UINPUT == {
        "cross": "BTN_LEFT",
        "triangle": "BTN_RIGHT",
        "r3": "BTN_MIDDLE",
    }
    assert DPAD_TO_KEY == {
        "dpad_up": "KEY_UP",
        "dpad_down": "KEY_DOWN",
        "dpad_left": "KEY_LEFT",
        "dpad_right": "KEY_RIGHT",
    }


# --- pipeline float do stick (FEAT-MOUSE-CURSOR-FEEL-01) ---------------------

def test_deadzone_movimento_retorna_zero_perto_do_centro():
    # Dentro da deadzone radial (|offset| <= 20) → velocidade 0 px/s.
    assert _compute_move_px_per_sec(128, 128, 6) == (0.0, 0.0)
    assert _compute_move_px_per_sec(128 + 19, 128, 6) == (0.0, 0.0)
    assert _compute_move_px_per_sec(128 - 19, 128, 6) == (0.0, 0.0)
    # Exatamente na borda (offset 20): resposta reescalada começa em 0.
    assert _compute_move_px_per_sec(128 + 20, 128, 6) == (0.0, 0.0)


# Tabela de regressão do contrato px/s (critério de aceite da spec):
# deflexão (offset cru do centro) → px/s esperado por speed. Valores derivados
# das constantes da Decisão (dz=20/128 reescalada, expo 1.6, step 125 px/s).
@pytest.mark.parametrize(
    ("offset", "speed", "px_per_sec"),
    [
        # 0% e borda da deadzone (~16%) → parado, em qualquer speed.
        (0, 1, 0.0), (0, 6, 0.0), (0, 12, 0.0),
        (20, 1, 0.0), (20, 6, 0.0), (20, 12, 0.0),
        # ~30% de deflexão (offset 38).
        (38, 1, 7.110), (38, 6, 42.660), (38, 12, 85.320),
        # ~60% de deflexão (offset 77).
        (77, 1, 44.961), (77, 6, 269.763), (77, 12, 539.527),
        # 100% positivo (raw 255, offset 127 — o cru satura em 255).
        (127, 1, 123.153), (127, 6, 738.920), (127, 12, 1477.840),
        # 100% negativo (raw 0, offset -128) → teto nominal exato da tabela.
        (-128, 1, -125.0), (-128, 6, -750.0), (-128, 12, -1500.0),
    ],
)
def test_tabela_regressao_deflexao_para_px_por_segundo(
    offset: int, speed: int, px_per_sec: float
):
    vx, vy = _compute_move_px_per_sec(128 + offset, 128, speed)
    assert vy == 0.0
    if px_per_sec == 0.0:
        assert vx == 0.0
    else:
        assert vx == pytest.approx(px_per_sec, rel=0.01)


@pytest.mark.parametrize("offset", [21, 26, 40, 64, 100, 127])
@pytest.mark.parametrize("speed", [1, 6, 12])
def test_simetria_positivo_negativo(offset: int, speed: int):
    """Mesma deflexão para os dois lados → mesma magnitude de px/s (o pipeline
    antigo tinha -speed vs speed-1: 360 vs 300 px/s @ 6)."""
    pos, _ = _compute_move_px_per_sec(128 + offset, 128, speed)
    neg, _ = _compute_move_px_per_sec(128 - offset, 128, speed)
    assert pos > 0.0
    assert neg == pytest.approx(-pos)
    # Eixo Y idêntico ao X (radial).
    _, pos_y = _compute_move_px_per_sec(128, 128 + offset, speed)
    assert pos_y == pytest.approx(pos)


def test_continuidade_sem_degrau_na_saida_da_deadzone():
    """Logo após a deadzone a velocidade nasce quase-zero e cresce monotônica —
    sem o salto 0→60 px/s do pipeline antigo."""
    logo_apos, _ = _compute_move_px_per_sec(128 + 21, 128, 6)
    assert 0.0 < logo_apos < 1.0  # ~0.42 px/s; antes era 60 px/s
    velocidades = [
        _compute_move_px_per_sec(128 + off, 128, 6)[0] for off in range(21, 128)
    ]
    assert all(b > a for a, b in itertools.pairwise(velocidades))


def test_diagonal_cheia_nao_ultrapassa_teto_de_px_por_segundo():
    """Canto diagonal do gate quadrado (raw 255/255): a magnitude radial é
    clampada ao teto nominal (speed*125), não 1.9x ele."""
    vx, vy = _compute_move_px_per_sec(255, 255, 6)
    assert math.hypot(vx, vy) == pytest.approx(6 * MOUSE_PX_PER_SEC_STEP, rel=0.001)


def test_deadzone_scroll_exige_amplitude_maior():
    # Stick a 30 de offset passa no move (>20) mas não no scroll (<40)
    assert _compute_move_px_per_sec(128 + 30, 128, 6)[0] > 0.0
    assert _compute_scroll_step(128 + 30) == 0
    # Acima de 40 passa
    assert _compute_scroll_step(128 + 41) == 1
    assert _compute_scroll_step(128 - 41) == -1


# --- start / stop ------------------------------------------------------------

def test_start_sem_uinput_retorna_false(monkeypatch: pytest.MonkeyPatch):
    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "uinput":
            raise ImportError("uinput não instalado (mock)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    dev = UinputMouseDevice()
    assert dev.start() is False
    assert dev.is_active() is False


def test_start_e_stop_idempotente(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    assert dev.is_active() is True
    fake_mod.Device.assert_called_once()
    # Segunda chamada não recria
    assert dev.start() is True
    fake_mod.Device.assert_called_once()

    dev.stop()
    fake_device.destroy.assert_called_once()
    assert dev.is_active() is False
    # Stop idempotente
    dev.stop()
    fake_device.destroy.assert_called_once()


def test_dispatch_sem_start_nao_emite(monkeypatch: pytest.MonkeyPatch):
    dev = UinputMouseDevice()
    # Sem start, dispatch é no-op (não levanta)
    dev.dispatch(
        lx=200, ly=200, rx=200, ry=200, l2=0, r2=0,
        buttons=frozenset({"cross"}),
    )


# --- botões: edge-trigger ----------------------------------------------------

def test_cross_press_release_emite_bt_left(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Press
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"cross"}), now=0.0,
    )
    left_emits = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert len(left_emits) == 1
    assert left_emits[-1][1][1] == 1  # value=1 (press)

    fake_device.reset_mock()

    # Hold (mesmo estado): sem novo emit de BTN_LEFT
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"cross"}), now=0.1,
    )
    held = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert held == []

    # Release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.2,
    )
    released = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert len(released) == 1
    assert released[-1][1][1] == 0


def test_triangle_e_r3_mapeam_right_e_middle(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"triangle", "r3"}), now=0.0,
    )

    right_press = any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_RIGHT and c[1][1] == 1
        for c in fake_device.method_calls
    )
    middle_press = any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_MIDDLE and c[1][1] == 1
        for c in fake_device.method_calls
    )
    assert right_press
    assert middle_press


def test_l2_analogico_acima_do_threshold_dispara_botao_esquerdo(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # L2 abaixo do threshold: não dispara
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=40, r2=0,
        buttons=frozenset(), now=0.0,
    )
    assert not any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
        for c in fake_device.method_calls
    )

    fake_device.reset_mock()

    # L2 acima: dispara
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=200, r2=0,
        buttons=frozenset(), now=0.1,
    )
    press = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert press and press[-1][1][1] == 1


def test_r2_analogico_acima_do_threshold_dispara_botao_direito(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=200,
        buttons=frozenset(), now=0.0,
    )
    press = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_RIGHT
    ]
    assert press and press[-1][1][1] == 1


# --- movimento ---------------------------------------------------------------

def test_stick_esquerdo_fora_do_centro_emite_rel(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=228, ly=228, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    rel_x = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.REL_X]
    rel_y = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.REL_Y]
    assert rel_x and rel_x[-1][1][1] > 0
    assert rel_y and rel_y[-1][1][1] > 0


def test_stick_esquerdo_no_centro_nao_emite(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    assert not any(
        c[0] == "emit" and c[1][0] in (fake_mod.REL_X, fake_mod.REL_Y)
        for c in fake_device.method_calls
    )


def test_set_speed_limites():
    dev = UinputMouseDevice()
    dev.set_speed(mouse_speed=100)
    assert dev.mouse_speed == 12  # clamp superior
    dev.set_speed(mouse_speed=-5)
    assert dev.mouse_speed == 1  # clamp inferior
    dev.set_speed(scroll_speed=10)
    assert dev.scroll_speed == 5
    dev.set_speed(scroll_speed=0)
    assert dev.scroll_speed == 1


def test_carry_acumula_subpixel_em_deflexao_pequena(monkeypatch: pytest.MonkeyPatch):
    """20% de deflexão @ speed 6 → ~7,36 px/s (0,12 px/tick @ 60 Hz): os 8
    primeiros ticks não emitem nada (sub-pixel), o carry fecha 1 px no 9º e
    60 ticks somam ~7 px — o pipeline antigo truncava tudo a 0 ou saltava."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    for _ in range(8):
        dev.dispatch(lx=154, ly=128, rx=128, ry=128, l2=0, r2=0,
                     buttons=frozenset(), now=0.0)
    assert not _emits_for(fake_device, fake_mod.REL_X)  # ainda <1 px acumulado

    dev.dispatch(lx=154, ly=128, rx=128, ry=128, l2=0, r2=0,
                 buttons=frozenset(), now=0.0)
    primeiro = _emits_for(fake_device, fake_mod.REL_X)
    assert len(primeiro) == 1
    assert primeiro[-1][1][1] == 1

    fake_device.reset_mock()
    dev._stick_carry_x = 0.0  # zera para medir 60 ticks limpos
    for _ in range(60):
        dev.dispatch(lx=154, ly=128, rx=128, ry=128, l2=0, r2=0,
                     buttons=frozenset(), now=0.0)
    total = _rel_sum(fake_device, fake_mod.REL_X)
    assert 6 <= total <= 8  # ~7,36 px em 1s de deflexão constante


def test_speed_1_move_em_todas_as_direcoes(monkeypatch: pytest.MonkeyPatch):
    """speed=1 era INCAPAZ de mover para direita/baixo (int truncava a 0 em
    todo o range positivo). Agora todas as direções emitem."""
    casos = [
        ("direita", dict(lx=255, ly=128), "REL_X", 1),
        ("esquerda", dict(lx=0, ly=128), "REL_X", -1),
        ("baixo", dict(lx=128, ly=255), "REL_Y", 1),
        ("cima", dict(lx=128, ly=0), "REL_Y", -1),
    ]
    for nome, sticks, rel_attr, sinal in casos:
        dev, fake_mod, fake_device = _started_device(monkeypatch)
        dev.set_speed(mouse_speed=1)
        dev.dispatch(rx=128, ry=128, l2=0, r2=0, buttons=frozenset(),
                     now=0.0, **sticks)
        total = _rel_sum(fake_device, getattr(fake_mod, rel_attr))
        assert total * sinal >= 2, f"speed=1 não moveu para {nome}"


def test_deadzone_zera_carry_para_nao_virar_drift(monkeypatch: pytest.MonkeyPatch):
    """Voltar ao repouso descarta o resto fracionário: religar o movimento
    depois recomeça do zero (sem pixel fantasma acumulado)."""
    dev, _fake_mod, _fake_device = _started_device(monkeypatch)
    # 8 ticks a 20% acumulam ~0,98 px de carry sem emitir.
    for _ in range(8):
        dev.dispatch(lx=154, ly=128, rx=128, ry=128, l2=0, r2=0,
                     buttons=frozenset(), now=0.0)
    assert dev._stick_carry_x > 0.9
    # Stick de volta ao centro: carry zerado.
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
                 buttons=frozenset(), now=0.0)
    assert dev._stick_carry_x == 0.0
    assert dev._stick_carry_y == 0.0
    # stop() também zera (start/stop resetam estado).
    dev._stick_carry_x = 0.7
    dev.stop()
    assert dev._stick_carry_x == 0.0


def test_poll_hz_define_o_delta_por_tick(monkeypatch: pytest.MonkeyPatch):
    """O período do tick vem de poll_hz (não hardcodado 60): a MESMA deflexão
    a 125 Hz emite deltas menores por tick (750/125=6 vs 750/60→12 px)."""
    dev60, fake_mod60, fake_device60 = _started_device(monkeypatch)
    dev60.dispatch(lx=128, ly=0, rx=128, ry=128, l2=0, r2=0,
                   buttons=frozenset(), now=0.0)
    tick60 = _rel_sum(fake_device60, fake_mod60.REL_Y)
    assert tick60 == -12  # -750 px/s / 60 Hz (deflexão negativa cheia)

    dev125, fake_mod125, fake_device125 = _started_device(monkeypatch, poll_hz=125)
    dev125.dispatch(lx=128, ly=0, rx=128, ry=128, l2=0, r2=0,
                    buttons=frozenset(), now=0.0)
    tick125 = _rel_sum(fake_device125, fake_mod125.REL_Y)
    assert tick125 == -6  # -750 px/s / 125 Hz


# --- scroll / rate-limit -----------------------------------------------------

def test_scroll_rate_limit_50ms(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Primeiro scroll em t=0: passa
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    first = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert len(first) == 1

    fake_device.reset_mock()

    # t=0.020 (20ms): dentro do rate-limit, NÃO emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.020,
    )
    blocked = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert blocked == []

    # t=0.060 (60ms): fora do rate-limit, emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.060,
    )
    passed = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert len(passed) == 1


def test_scroll_vertical_sentido_convencional(monkeypatch: pytest.MonkeyPatch):
    """Stick direito empurrado para cima (ry<128) → scroll positivo (up)."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=50, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    wheel = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert wheel and wheel[-1][1][1] > 0


def test_scroll_horizontal_hwheel(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(
        lx=128, ly=128, rx=200, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    hwheel = _emits_for(fake_device, fake_mod.REL_HWHEEL)
    assert hwheel and hwheel[-1][1][1] != 0


# --- D-pad → setas -----------------------------------------------------------

def test_dpad_up_emite_key_up_edge_trigger(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"dpad_up"}), now=0.0,
    )
    press = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert press and press[-1][1][1] == 1

    fake_device.reset_mock()

    # Mantido: sem novo emit
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"dpad_up"}), now=0.05,
    )
    held = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert held == []

    # Solto: release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.1,
    )
    release = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert release and release[-1][1][1] == 0


def test_dpad_cobre_quatro_direcoes(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    t = 0.0
    for name, key_attr in (
        ("dpad_up", "KEY_UP"),
        ("dpad_down", "KEY_DOWN"),
        ("dpad_left", "KEY_LEFT"),
        ("dpad_right", "KEY_RIGHT"),
    ):
        fake_device.reset_mock()
        dev.dispatch(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
            buttons=frozenset({name}), now=t,
        )
        key = getattr(fake_mod, key_attr)
        press = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == key]
        assert press and press[-1][1][1] == 1, f"{name} não emitiu {key_attr} press"
        t += 0.2  # desacopla do rate-limit de scroll
        dev.dispatch(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
            buttons=frozenset(), now=t,
        )
        t += 0.2


# --- Circle/Square edge-triggered → Enter/Esc (FEAT-MOUSE-02) ---------------

def test_edge_key_map_canonico():
    assert EDGE_KEY_MAP == {
        "circle": "KEY_ENTER",
        "square": "KEY_ESC",
    }


def test_circle_edge_trigger_enter(monkeypatch: pytest.MonkeyPatch):
    """Circle False→True emite KEY_ENTER press+release; hold não re-emite."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Primeiro tick: circle=True → press+release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"circle"}), now=0.0,
    )
    enter = _emits_for(fake_device, fake_mod.KEY_ENTER)
    # Emite valor 1 (press) e 0 (release) no mesmo dispatch
    assert len(enter) == 2
    assert enter[0][1][1] == 1
    assert enter[1][1][1] == 0

    fake_device.reset_mock()

    # Segundo tick com circle=True ainda pressionado: NÃO re-emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"circle"}), now=0.05,
    )
    held = _emits_for(fake_device, fake_mod.KEY_ENTER)
    assert held == []


def test_square_edge_trigger_esc(monkeypatch: pytest.MonkeyPatch):
    """Square False→True emite KEY_ESC press+release; hold não re-emite."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"square"}), now=0.0,
    )
    esc = _emits_for(fake_device, fake_mod.KEY_ESC)
    assert len(esc) == 2
    assert esc[0][1][1] == 1
    assert esc[1][1][1] == 0

    fake_device.reset_mock()

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"square"}), now=0.05,
    )
    held = _emits_for(fake_device, fake_mod.KEY_ESC)
    assert held == []


def test_release_allows_re_emit(monkeypatch: pytest.MonkeyPatch):
    """Após circle=False, próxima pressão re-emite KEY_ENTER."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Press inicial
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"circle"}), now=0.0,
    )
    first = _emits_for(fake_device, fake_mod.KEY_ENTER)
    assert len(first) == 2

    # Release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.05,
    )

    fake_device.reset_mock()

    # Nova pressão: re-emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"circle"}), now=0.10,
    )
    second = _emits_for(fake_device, fake_mod.KEY_ENTER)
    assert len(second) == 2
    assert second[0][1][1] == 1
    assert second[1][1][1] == 0


# --- touchpad → cursor (FEAT-DSX-TOUCHPAD-CURSOR-B4) -------------------------

def test_emit_touchpad_move_escala_por_sensibilidade(monkeypatch: pytest.MonkeyPatch):
    """raw delta → REL_X/REL_Y escalado por TOUCHPAD_SENSITIVITY (speed default)."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    # factor = 0.45 * (6/6) = 0.45 → dx=100 vira 45; dy=-50 vira -22 (trunca).
    dev.emit_touchpad_move(100, -50)
    rel_x = _emits_for(fake_device, fake_mod.REL_X)
    rel_y = _emits_for(fake_device, fake_mod.REL_Y)
    assert rel_x and rel_x[-1][1][1] == 45
    assert rel_y and rel_y[-1][1][1] == -22


def test_emit_touchpad_move_zero_nao_emite(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.emit_touchpad_move(0, 0)
    assert not _emits_for(fake_device, fake_mod.REL_X)
    assert not _emits_for(fake_device, fake_mod.REL_Y)


def test_emit_touchpad_move_carry_subpixel_sem_engasgo(monkeypatch: pytest.MonkeyPatch):
    """Movimentos lentos que truncam a 0 acumulam carry e eventualmente emitem 1px."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    # factor=0.45: cada raw=1 → 0.45 px. Dois ticks somam 0.9 (<1, sem emit),
    # o terceiro fecha 1.35 → emite exatamente 1px.
    dev.emit_touchpad_move(1, 0)
    dev.emit_touchpad_move(1, 0)
    assert not _emits_for(fake_device, fake_mod.REL_X)  # ainda <1px acumulado
    dev.emit_touchpad_move(1, 0)
    rel_x = _emits_for(fake_device, fake_mod.REL_X)
    assert len(rel_x) == 1
    assert rel_x[-1][1][1] == 1


def test_emit_touchpad_move_respeita_mouse_speed(monkeypatch: pytest.MonkeyPatch):
    """mouse_speed maior amplifica o movimento do touchpad."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.set_speed(mouse_speed=12)  # factor = 0.45 * (12/6) = 0.9
    dev.emit_touchpad_move(100, 0)
    rel_x = _emits_for(fake_device, fake_mod.REL_X)
    assert rel_x and rel_x[-1][1][1] == 90


def test_emit_touchpad_move_sem_start_nao_levanta():
    """Sem device criado, emit_touchpad_move é no-op silencioso."""
    dev = UinputMouseDevice()
    dev.emit_touchpad_move(100, 100)  # não deve levantar


def test_touchpad_sensitivity_default():
    assert TOUCHPAD_SENSITIVITY == 0.45


# "A liberdade é nada mais que uma chance de ser melhor." — Albert Camus
