"""FEAT-VPAD-FF-PASSTHROUGH-01 — force-feedback do vpad → rumble físico.

Cobre o protocolo de FF do `UinputGamepad` com um `evdev` falso (handshake de
upload/erase, play/stop, duração, gain, soma de efeitos, throttle por mudança
e degradação sem FF) e o caminho `apply_game_rumble` do subsystem gamepad
(rumble fixado vence, política global aplicada, targeting por MAC com
salvar/restaurar do alvo, broadcast como fallback). Sem hardware.
"""
from __future__ import annotations

import sys
import types
from collections import deque
from types import SimpleNamespace
from typing import Any, ClassVar, NamedTuple

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

MAC_1 = "aabbcc001100"
MAC_2 = "aabbcc001122"


class _EC:
    """Constantes evdev mínimas (valores reais do linux/input-event-codes.h)."""

    EV_SYN = 0x00
    EV_KEY = 0x01
    EV_ABS = 0x03
    EV_FF = 0x15
    EV_UINPUT = 0x0101
    UI_FF_UPLOAD = 1
    UI_FF_ERASE = 2
    ABS_X = 0x00
    ABS_Y = 0x01
    ABS_Z = 0x02
    ABS_RX = 0x03
    ABS_RY = 0x04
    ABS_RZ = 0x05
    ABS_HAT0X = 0x10
    ABS_HAT0Y = 0x11
    BTN_A = 0x130
    BTN_B = 0x131
    BTN_X = 0x133
    BTN_Y = 0x134
    BTN_TL = 0x136
    BTN_TR = 0x137
    BTN_SELECT = 0x13A
    BTN_START = 0x13B
    BTN_MODE = 0x13C
    BTN_THUMBL = 0x13D
    BTN_THUMBR = 0x13E
    FF_RUMBLE = 0x50
    FF_PERIODIC = 0x51
    FF_SQUARE = 0x58
    FF_TRIANGLE = 0x59
    FF_SINE = 0x5A
    FF_GAIN = 0x60


class _AbsInfo(NamedTuple):
    value: int
    min: int
    max: int
    fuzz: int
    flat: int
    resolution: int


def _event(etype: int, code: int, value: int) -> SimpleNamespace:
    return SimpleNamespace(type=etype, code=code, value=value)


def _rumble_effect(
    effect_id: int, *, strong: int, weak: int, duration_ms: int = 0
) -> SimpleNamespace:
    """Efeito FF_RUMBLE como o kernel entrega no upload (campos do ctypes)."""
    return SimpleNamespace(
        type=_EC.FF_RUMBLE,
        id=effect_id,
        ff_replay=SimpleNamespace(length=duration_ms, delay=0),
        u=SimpleNamespace(
            ff_rumble_effect=SimpleNamespace(strong_magnitude=strong, weak_magnitude=weak),
            ff_periodic_effect=SimpleNamespace(magnitude=0),
        ),
    )


def _periodic_effect(effect_id: int, *, magnitude: int, duration_ms: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        type=_EC.FF_PERIODIC,
        id=effect_id,
        ff_replay=SimpleNamespace(length=duration_ms, delay=0),
        u=SimpleNamespace(
            ff_rumble_effect=SimpleNamespace(strong_magnitude=0, weak_magnitude=0),
            ff_periodic_effect=SimpleNamespace(magnitude=magnitude),
        ),
    )


class _FakeUInput:
    """UInput falso com o handshake de FF (begin/end upload/erase) e fd scriptável."""

    instances: ClassVar[list[_FakeUInput]] = []
    fail_with_ff = False  # knob: criação COM EV_FF falha (ambiente sem FF)

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        if type(self).fail_with_ff and _EC.EV_FF in events:
            raise OSError("EV_FF não suportado (fake)")
        self.events = events
        self.kwargs = kwargs
        self.writes: list[tuple[int, int, int]] = []
        self.closed = False
        #: Eventos que o "jogo" gerou, drenados por read_one().
        self.queue: deque[SimpleNamespace] = deque()
        #: request_id → efeito pendente de upload (o que begin_upload devolve).
        self.pending_uploads: dict[int, SimpleNamespace] = {}
        #: request_id → effect_id pendente de erase.
        self.pending_erases: dict[int, int] = {}
        self.uploads_done: list[SimpleNamespace] = []
        self.erases_done: list[SimpleNamespace] = []
        type(self).instances.append(self)

    def write(self, etype: int, code: int, value: int) -> None:
        self.writes.append((etype, code, value))

    def syn(self) -> None:
        return

    def close(self) -> None:
        self.closed = True

    def read_one(self) -> SimpleNamespace | None:
        return self.queue.popleft() if self.queue else None

    def begin_upload(self, request_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            request_id=request_id, retval=-1, effect=self.pending_uploads[request_id]
        )

    def end_upload(self, upload: SimpleNamespace) -> None:
        self.uploads_done.append(upload)

    def begin_erase(self, request_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            request_id=request_id, retval=-1, effect_id=self.pending_erases[request_id]
        )

    def end_erase(self, erase: SimpleNamespace) -> None:
        self.erases_done.append(erase)

    # -- conveniências de script ("o jogo fez X") ------------------------

    def game_uploads(self, effect: SimpleNamespace, *, request_id: int) -> None:
        self.pending_uploads[request_id] = effect
        self.queue.append(_event(_EC.EV_UINPUT, _EC.UI_FF_UPLOAD, request_id))

    def game_erases(self, effect_id: int, *, request_id: int) -> None:
        self.pending_erases[request_id] = effect_id
        self.queue.append(_event(_EC.EV_UINPUT, _EC.UI_FF_ERASE, request_id))

    def game_plays(self, effect_id: int, *, repeats: int = 1) -> None:
        self.queue.append(_event(_EC.EV_FF, effect_id, repeats))

    def game_stops(self, effect_id: int) -> None:
        self.queue.append(_event(_EC.EV_FF, effect_id, 0))

    def game_sets_gain(self, gain: int) -> None:
        self.queue.append(_event(_EC.EV_FF, _EC.FF_GAIN, gain))


def _install_fake_evdev(monkeypatch: pytest.MonkeyPatch) -> type[_FakeUInput]:
    _FakeUInput.instances = []
    _FakeUInput.fail_with_ff = False
    mod = types.ModuleType("evdev")
    mod.UInput = _FakeUInput  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    return _FakeUInput


def _make_vpad(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[UinputGamepad, _FakeUInput, list[tuple[int, int]], list[float]]:
    """Vpad iniciado com evdev falso, sink gravador e relógio injetado."""
    _install_fake_evdev(monkeypatch)
    sink_calls: list[tuple[int, int]] = []
    clock = [100.0]
    gp = UinputGamepad.for_flavor(
        "dualsense", rumble_sink=lambda weak, strong: sink_calls.append((weak, strong))
    )
    gp.time_fn = lambda: clock[0]
    assert gp.start() is True
    return gp, _FakeUInput.instances[0], sink_calls, clock


class TestVpadFF:
    def test_upload_play_sink_recebe_convertido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0x8000), request_id=7)
        dev.game_plays(0)

        gp.pump_ff()

        # Handshake respondido (retval 0) e magnitudes 0-65535 → 0-255 (>>8).
        assert [u.retval for u in dev.uploads_done] == [0]
        assert sink == [(0x80, 0xFF)]

    def test_stop_zera_o_rumble(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0xFFFF), request_id=1)
        dev.game_plays(0)
        gp.pump_ff()
        dev.game_stops(0)

        gp.pump_ff()

        assert sink == [(0xFF, 0xFF), (0, 0)]

    def test_duracao_expira_zera_sem_stop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Jogos que só dão play e nunca stop: a duração do efeito manda.
        gp, dev, sink, clock = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0x4000, weak=0, duration_ms=100), request_id=1)
        dev.game_plays(0)
        gp.pump_ff()
        assert sink == [(0, 0x40)]

        clock[0] += 0.050  # ainda dentro da duração
        gp.pump_ff()
        assert sink == [(0, 0x40)]

        clock[0] += 0.060  # 110ms > 100ms — venceu
        gp.pump_ff()
        assert sink == [(0, 0x40), (0, 0)]

    def test_play_com_repeticoes_estica_o_deadline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, clock = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0x4000, weak=0, duration_ms=100), request_id=1)
        dev.game_plays(0, repeats=3)  # 3 repetições = 300ms
        gp.pump_ff()

        clock[0] += 0.150  # venceria com 1 repetição; com 3 ainda toca
        gp.pump_ff()
        assert sink == [(0, 0x40)]

        clock[0] += 0.200
        gp.pump_ff()
        assert sink[-1] == (0, 0)

    def test_reupload_do_mesmo_id_atualiza_magnitudes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0xFFFF), request_id=1)
        dev.game_plays(0)
        gp.pump_ff()
        # Jogo "reprograma" o efeito em curso (padrão SDL para variar rumble).
        dev.game_uploads(_rumble_effect(0, strong=0x2000, weak=0x1000), request_id=2)

        gp.pump_ff()

        assert sink == [(0xFF, 0xFF), (0x10, 0x20)]

    def test_erase_para_efeito_em_curso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(3, strong=0xFFFF, weak=0), request_id=1)
        dev.game_plays(3)
        gp.pump_ff()
        dev.game_erases(3, request_id=2)

        gp.pump_ff()

        assert [e.retval for e in dev.erases_done] == [0]
        assert sink == [(0, 0xFF), (0, 0)]

    def test_gain_escala_o_rumble(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_sets_gain(0x8000)  # ~50%
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0xFFFF), request_id=1)
        dev.game_plays(0)

        gp.pump_ff()

        # 0xFFFF x (0x8000/0xFFFF) = 0x8000 → >>8 = 0x80 nos dois motores.
        assert sink == [(0x80, 0x80)]

    def test_periodic_mapeia_para_os_dois_motores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_periodic_effect(0, magnitude=0x4000), request_id=1)
        dev.game_plays(0)

        gp.pump_ff()

        # |0x4000| * 2 = 0x8000 → >>8 = 0x80 nos dois motores.
        assert sink == [(0x80, 0x80)]

    def test_efeitos_simultaneos_somam_com_clamp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0xC000, weak=0x1000), request_id=1)
        dev.game_uploads(_rumble_effect(1, strong=0xC000, weak=0x1000), request_id=2)
        dev.game_plays(0)
        dev.game_plays(1)

        gp.pump_ff()

        # strong: 0xC000+0xC000 clampa em 0xFFFF → 0xFF; weak: 0x2000 → 0x20.
        assert sink == [(0x20, 0xFF)]

    def test_throttle_sink_so_quando_muda(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0x8000, weak=0x8000), request_id=1)
        dev.game_plays(0)
        gp.pump_ff()
        gp.pump_ff()  # nada mudou — o sink escreve HID, não pode repetir
        gp.pump_ff()

        assert sink == [(0x80, 0x80)]

    def test_ambiente_sem_ff_degrada_sem_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _install_fake_evdev(monkeypatch)
        fake.fail_with_ff = True
        sink: list[tuple[int, int]] = []
        gp = UinputGamepad.for_flavor("xbox", rumble_sink=lambda w, s: sink.append((w, s)))

        assert gp.start() is True  # degradou para vpad SEM EV_FF
        assert gp.ff_supported is False
        dev = fake.instances[0]
        assert _EC.EV_FF not in dev.events

        gp.pump_ff()  # no-op, sem crash
        gp.forward_analog(lx=1, ly=2, rx=3, ry=4, l2=5, r2=6)  # input segue vivo
        assert sink == []
        assert len(dev.writes) == 6

    def test_sink_que_lanca_nao_derruba_o_pump(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_evdev(monkeypatch)

        def _boom(_weak: int, _strong: int) -> None:
            raise RuntimeError("HID caiu")

        gp = UinputGamepad.for_flavor("dualsense", rumble_sink=_boom)
        assert gp.start() is True
        dev = _FakeUInput.instances[0]
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0), request_id=1)
        dev.game_plays(0)

        gp.pump_ff()  # não propaga

    def test_stop_do_vpad_zera_rumble_fisico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gp, dev, sink, _ = _make_vpad(monkeypatch)
        dev.game_uploads(_rumble_effect(0, strong=0xFFFF, weak=0xFFFF), request_id=1)
        dev.game_plays(0)
        gp.pump_ff()

        gp.stop()  # vpad some — ninguém mais mandaria o stop do motor

        assert sink == [(0xFF, 0xFF), (0, 0)]
        assert dev.closed is True

    def test_xbox_flavor_tambem_anuncia_ff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _install_fake_evdev(monkeypatch)
        gp = UinputGamepad.for_flavor("xbox")
        assert gp.start() is True
        assert _EC.EV_FF in fake.instances[0].events
        assert gp.ff_supported is True


# -- apply_game_rumble (subsystem gamepad) -------------------------------


class _FakeBackend:
    """Backend multi-controle: registra rumbles com o ALVO vigente em cada um."""

    def __init__(self, uniqs: tuple[str, ...] = (MAC_1, MAC_2)) -> None:
        self._uniqs = list(uniqs)
        self._target: int | None = None
        self.rumbles: list[tuple[int | None, int, int]] = []
        self.target_calls: list[int | None] = []
        self.primary_uniq: str | None = uniqs[0] if uniqs else None

    def describe_controllers(self) -> list[dict[str, object]]:
        return [
            {"index": i, "uniq": u, "is_primary": i == 0, "connected": True}
            for i, u in enumerate(self._uniqs)
        ]

    def set_output_target(self, index: int | None) -> int | None:
        self.target_calls.append(index)
        self._target = index
        return index

    def get_output_target_index(self) -> int | None:
        return self._target

    def set_rumble(self, weak: int, strong: int) -> None:
        self.rumbles.append((self._target, weak, strong))


def _make_daemon(
    *,
    policy: str = "max",
    rumble_active: tuple[int, int] | None = None,
    battery: int = 80,
    controller: Any | None = None,
) -> Any:
    ctrl_state = SimpleNamespace(battery_pct=battery)
    return SimpleNamespace(
        config=SimpleNamespace(
            rumble_active=rumble_active,
            rumble_policy=policy,
            rumble_policy_custom_mult=0.7,
        ),
        controller=controller if controller is not None else _FakeBackend(),
        store=SimpleNamespace(snapshot=lambda: SimpleNamespace(controller=ctrl_state)),
        _last_auto_mult=0.7,
        _last_auto_change_at=0.0,
    )


class TestApplyGameRumble:
    def test_rumble_fixado_manual_vence_o_ff(self) -> None:
        daemon = _make_daemon(rumble_active=(10, 20))
        gp_mod.apply_game_rumble(daemon, 200, 200)
        assert daemon.controller.rumbles == []  # FF ignorado (fixado vence)

    def test_politica_global_aplica_multiplicador(self) -> None:
        daemon = _make_daemon(policy="custom")
        daemon.config.rumble_policy_custom_mult = 0.5
        gp_mod.apply_game_rumble(daemon, 200, 100)
        assert daemon.controller.rumbles == [(None, 100, 50)]

    def test_target_por_mac_salva_e_restaura_o_alvo(self) -> None:
        backend = _FakeBackend()
        daemon = _make_daemon(controller=backend)
        gp_mod.apply_game_rumble(daemon, 255, 255, target_uniq=MAC_2)

        assert backend.rumbles == [(1, 255, 255)]  # aplicado no controle certo
        assert backend.target_calls == [1, None]  # mirou e voltou ao broadcast
        assert backend.get_output_target_index() is None

    def test_target_restaura_selecao_previa_da_usuaria(self) -> None:
        backend = _FakeBackend()
        backend.set_output_target(0)  # usuária tinha selecionado o Controle 1
        backend.target_calls.clear()
        daemon = _make_daemon(controller=backend)
        gp_mod.apply_game_rumble(daemon, 100, 100, target_uniq=MAC_2)

        assert backend.rumbles == [(1, 100, 100)]
        assert backend.get_output_target_index() == 0  # seleção preservada

    def test_mac_desconhecido_cai_em_broadcast(self) -> None:
        backend = _FakeBackend()
        daemon = _make_daemon(controller=backend)
        gp_mod.apply_game_rumble(daemon, 90, 90, target_uniq="ffffffffffff")
        assert backend.rumbles == [(None, 90, 90)]
        assert backend.target_calls == []

    def test_backend_sem_targeting_cai_em_broadcast(self) -> None:
        rumbles: list[tuple[int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: rumbles.append((weak, strong))
        )
        daemon = _make_daemon(controller=controller)
        gp_mod.apply_game_rumble(daemon, 80, 90, target_uniq=MAC_2)
        assert rumbles == [(80, 90)]

    def test_sink_do_primario_mira_o_primario(self) -> None:
        backend = _FakeBackend()
        daemon = _make_daemon(controller=backend)
        sink = gp_mod.make_primary_rumble_sink(daemon)
        sink(64, 128)
        assert backend.rumbles == [(0, 64, 128)]


class TestCoopPlayerRumbleSink:
    def test_sink_do_jogador_mira_o_mac_dele(self) -> None:
        backend = _FakeBackend()
        daemon = _make_daemon(controller=backend)
        mgr = CoopManager(daemon)
        sink = mgr._make_player_rumble_sink(MAC_2)
        sink(32, 200)
        assert backend.rumbles == [(1, 32, 200)]

    def test_identidade_sem_mac_cai_em_broadcast(self) -> None:
        backend = _FakeBackend()
        daemon = _make_daemon(controller=backend)
        mgr = CoopManager(daemon)
        sink = mgr._make_player_rumble_sink("path:/dev/input/event9")
        sink(10, 20)
        assert backend.rumbles == [(None, 10, 20)]
        assert backend.target_calls == []
