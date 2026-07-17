"""Testes do suporte a N DualSense (FEAT-DSX-MULTI-CONTROLLER-01).

Cobre:
  - fan-out de escrita (gatilhos, lightbar, rumble, LEDs de player, LED do mic)
    para TODOS os controles conectados;
  - detecção/dedupe de múltiplos controles em `_enumerate_device_keys`;
  - hotplug-in: controle plugado em runtime recebe o PERFIL ATIVO;
  - hotplug-out: controle removido é fechado (sem vazar handle) e o primário é
    promovido quando cai;
  - NÃO-regressão do caso de 1 controle.

O INPUT/EMULAÇÃO permanece single-controller (lê do primário) — coberto pelos
testes de `read_state` em `test_controller.py`.

PERFIL-01 (4P-01): `TestDesiredPorControle` cobre o estado desejado POR
CONTROLE — o bug provado ao vivo (replug herdando o ajuste de outro controle),
o merge POR CAMPO, o reset na ativação de perfil, o registro de controle
desconectado e o cenário 2P com um override para cada.
"""
from __future__ import annotations

from unittest.mock import patch

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

#: Keys MAC-formadas (faixa forjada aa:bb:cc — teste-guarda de anonimato).
KEY_1 = "AA:BB:CC:00:00:01"
KEY_2 = "AA:BB:CC:00:00:02"
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — força is_available=False (não interfere)."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _FakeTrigger:
    def __init__(self) -> None:
        self.mode: object = None
        self.forces: list[int] = [0] * 7

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces[idx] = value


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []
        self.playerNumber: object = None  # atributo espelhado da pydualsense

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeAudio:
    def __init__(self) -> None:
        self.mic_led_history: list[bool] = []

    def setMicrophoneLED(self, flag: bool) -> None:  # noqa: N802 — API pydualsense
        self.mic_led_history.append(flag)


class _FakeHandle:
    """Stub de um handle pydualsense aberto (um controle)."""

    def __init__(self, *, connected: bool = True, transport_name: str = "USB") -> None:
        self.connected = connected
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()
        self.light = _FakeLight()
        self.audio = _FakeAudio()
        self.left_motor: list[int] = []
        self.right_motor: list[int] = []
        self.closed = False
        self.conType = type("CT", (), {"name": transport_name})()

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.left_motor.append(intensity)

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.right_motor.append(intensity)

    def close(self) -> None:
        self.closed = True


def _with_two_handles() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {"a": h1, "b": h2}  # type: ignore[dict-item]
    inst._primary_key = "a"
    return inst, h1, h2


class TestFanOut:
    def test_set_led_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_led((10, 20, 30))
        assert h1.light.colors == [(10, 20, 30)]
        assert h2.light.colors == [(10, 20, 30)]

    def test_set_trigger_aplica_em_todos(self) -> None:
        from pydualsense.enums import TriggerModes

        inst, h1, h2 = _with_two_handles()
        inst.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        for h in (h1, h2):
            assert h.triggerR.mode == TriggerModes(1)
            assert h.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]
            # lado oposto intacto
            assert h.triggerL.forces == [0] * 7

    def test_set_rumble_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_rumble(weak=10, strong=20)
        for h in (h1, h2):
            assert h.left_motor == [20]
            assert h.right_motor == [10]

    def test_set_mic_led_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_mic_led(True)
        assert h1.audio.mic_led_history == [True]
        assert h2.audio.mic_led_history == [True]

    def test_set_player_leds_aplica_em_todos(self) -> None:
        from pydualsense.enums import PlayerID

        inst, h1, h2 = _with_two_handles()
        inst.set_player_leds((True, False, True, False, False))
        # bit0 + bit2 = 1 + 4 = 5
        assert h1.light.playerNumber == PlayerID(5)
        assert h2.light.playerNumber == PlayerID(5)

    def test_handle_que_falha_nao_derruba_os_outros(self) -> None:
        """Uma exceção num handle não impede a escrita nos demais."""
        inst, h1, h2 = _with_two_handles()

        def _boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("device morto")

        h1.light.setColorI = _boom  # type: ignore[method-assign]
        inst.set_led((1, 2, 3))  # não deve propagar
        assert h2.light.colors == [(1, 2, 3)]


class TestEnumerate:
    def test_enumerate_device_keys_dedupe_e_filtra(self) -> None:
        import hidapi

        class _DI:
            # Espelha a API real do hidapi: serial_number vem de wchar_t* → str
            # (ou None); path vem de char* → bytes.
            def __init__(self, pid: int, path: bytes, serial: str | None) -> None:
                self.vendor_id = 0x054C
                self.product_id = pid
                self.path = path
                self.serial_number = serial

        fake = [
            _DI(0x0CE6, b"/dev/hidraw0", "AA:BB"),
            _DI(0x0CE6, b"/dev/hidraw1", "AA:BB"),  # mesmo serial -> dedupe
            _DI(0x0DF2, b"/dev/hidraw2", "CC:DD"),  # Edge
            _DI(0x9999, b"/dev/hidraw3", "EE:FF"),  # não-DualSense -> filtra
            _DI(0x0CE6, b"/dev/hidraw4", None),  # sem serial -> chave por path
        ]

        with patch.object(hidapi, "enumerate", lambda vendor_id=0: fake):
            keys = PyDualSenseController._enumerate_device_keys()

        got = {key: (path, edge) for key, path, edge in keys}
        assert len(keys) == 3
        assert got["AA:BB"] == (b"/dev/hidraw0", False)  # 1º vence o dedupe
        assert got["CC:DD"] == (b"/dev/hidraw2", True)  # Edge detectado
        assert "EE:FF" not in got  # PID não-DualSense filtrado
        assert got["/dev/hidraw4"] == (b"/dev/hidraw4", False)  # fallback path


class TestHotplug:
    def test_hotplug_in_reaplica_perfil_no_novo_controle(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        inst._handles = {"a": h1}  # type: ignore[dict-item]
        inst._primary_key = "a"

        # Define o "perfil ativo" no controle existente (popula _desired).
        inst.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        inst.set_led((255, 0, 0))
        inst.set_player_leds((True, False, True, False, False))
        inst.set_mic_led(True)

        # Controle "b" é plugado em runtime.
        h2 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[
                ("a", b"/dev/hidraw0", False),
                ("b", b"/dev/hidraw1", False),
            ],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h2):
            inst.connect()

        # O novo controle recebeu o perfil ativo.
        assert h2.light.colors[-1] == (255, 0, 0)
        assert h2.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]
        assert h2.audio.mic_led_history[-1] is True
        assert h2.light.playerNumber is not None
        # O controle existente continua intacto e ainda é o primário.
        assert inst._primary_key == "a"
        assert inst._ds is h1
        assert "b" in inst._handles

    def test_rumble_nao_e_reaplicado_no_hotplug(self) -> None:
        """Rumble é transitório — não entra no perfil ativo, logo um controle
        plugado depois NÃO recebe um rumble antigo."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        inst._handles = {"a": h1}  # type: ignore[dict-item]
        inst._primary_key = "a"
        inst.set_rumble(weak=10, strong=20)

        h2 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[
                ("a", b"/dev/hidraw0", False),
                ("b", b"/dev/hidraw1", False),
            ],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h2):
            inst.connect()

        assert h2.left_motor == []
        assert h2.right_motor == []

    def test_hotplug_out_fecha_controle_removido(self) -> None:
        inst, h1, h2 = _with_two_handles()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("a", b"/dev/hidraw0", False)],
        ):
            inst.connect()

        assert h2.closed is True
        assert "b" not in inst._handles
        assert "a" in inst._handles
        assert inst._primary_key == "a"
        assert inst._ds is h1

    def test_hotplug_out_promove_proximo_primario(self) -> None:
        inst, h1, h2 = _with_two_handles()
        # O primário ("a") é removido; "b" deve ser promovido.
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("b", b"/dev/hidraw1", False)],
        ):
            inst.connect()

        assert h1.closed is True
        assert inst._primary_key == "b"
        assert inst._ds is h2
        assert inst._transport == "usb"


class TestSingleControllerNaoRegride:
    def test_um_controle_se_comporta_como_antes(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("a", b"/dev/hidraw0", False)],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h1):
            inst.connect()

        assert inst._ds is h1
        assert inst.is_connected() is True
        assert inst._offline is False
        assert len(inst._handles) == 1

        # Output vai para o único handle.
        inst.set_led((1, 2, 3))
        assert h1.light.colors == [(1, 2, 3)]

        # disconnect fecha tudo.
        inst.disconnect()
        assert h1.closed is True
        assert inst._ds is None
        assert inst.is_connected() is False


class TestDescribeControllers:
    def test_descreve_cada_controle(self) -> None:
        from types import SimpleNamespace

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle(transport_name="USB")
        h1.battery = SimpleNamespace(Level=87)  # type: ignore[attr-defined]
        h2 = _FakeHandle(transport_name="BT")
        # Keys reais são o serial hidapi (MAC); a normalização deve casar com a
        # do `primary_uniq` (norm_mac): minúsculo e sem ":".
        inst._handles = {
            "AA:BB:CC:00:00:03": h1,
            "AA:BB:CC:00:00:04": h2,
        }  # type: ignore[dict-item]
        inst._primary_key = "AA:BB:CC:00:00:03"

        desc = inst.describe_controllers()
        assert desc == [
            {
                "index": 0,
                "connected": True,
                "transport": "usb",
                "is_primary": True,
                "uniq": "aabbcc000003",
                "battery_pct": 87,
            },
            {
                "index": 1,
                "connected": True,
                "transport": "bt",
                "is_primary": False,
                "uniq": "aabbcc000004",
                # _FakeHandle sem atributo battery -> firmware ainda não
                # reportou -> None (não 0% falso).
                "battery_pct": None,
            },
        ]

    def test_uniq_none_para_key_por_path(self) -> None:
        """Key de fallback por path (sem serial) não vira MAC — uniq é None.

        Mesma semântica do `primary_uniq` (FEAT-DSX-CONTROLLER-IDENTITY-01).
        """
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        inst._handles = {"/dev/hidraw4": _FakeHandle()}  # type: ignore[dict-item]
        inst._primary_key = "/dev/hidraw4"

        (entry,) = inst.describe_controllers()
        assert entry["uniq"] is None

    def test_battery_none_quando_desconectado(self) -> None:
        """Handle desconectado não expõe bateria (evita leitura fantasma)."""
        from types import SimpleNamespace

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle(connected=False)
        h1.battery = SimpleNamespace(Level=50)  # type: ignore[attr-defined]
        inst._handles = {"AA:BB": h1}  # type: ignore[dict-item]
        inst._primary_key = "AA:BB"

        (entry,) = inst.describe_controllers()
        assert entry["connected"] is False
        assert entry["battery_pct"] is None

    def test_battery_clampada_em_0_100(self) -> None:
        from types import SimpleNamespace

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        h1.battery = SimpleNamespace(Level=250)  # type: ignore[attr-defined]
        inst._handles = {"AA:BB": h1}  # type: ignore[dict-item]
        inst._primary_key = "AA:BB"

        (entry,) = inst.describe_controllers()
        assert entry["battery_pct"] == 100

    def test_offline_devolve_entrada_neutra(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        assert inst.describe_controllers() == [
            {"connected": False, "transport": None, "is_primary": False}
        ]


class TestPinnedPyDualSense:
    def test_abre_por_path(self, monkeypatch: object) -> None:
        """_PinnedPyDualSense.__find_device abre o device pelo path informado."""
        import hidapi

        from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

        captured: dict[str, object] = {}

        class _FakeDev:
            pass

        def _fake_device(*, path: bytes) -> _FakeDev:
            captured["path"] = path
            return _FakeDev()

        monkeypatch.setattr(hidapi, "Device", _fake_device)  # type: ignore[attr-defined]
        pinned = _PinnedPyDualSense(b"/dev/hidraw9", is_edge=True)
        dev, is_edge = pinned._pydualsense__find_device()

        assert captured["path"] == b"/dev/hidraw9"
        assert is_edge is True
        assert isinstance(dev, _FakeDev)


def _with_two_macs() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    """Dois controles com keys MAC reais (uniq resolve) — cenários PERFIL-01."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}  # type: ignore[dict-item]
    inst._primary_key = KEY_1
    return inst, h1, h2


def _reconcile(inst: PyDualSenseController, keys: list[str], opened: list[_FakeHandle]) -> None:
    """Um tick de hotplug: `keys` presentes; handles novos saem de `opened`.

    Hermético: `sysfs_leds.discover` é stubado para {} — nunca toca o
    /sys/class/leds real (na máquina da mantenedora há DualSense de verdade).
    """
    fila = list(opened)
    with patch.object(
        PyDualSenseController,
        "_enumerate_device_keys",
        return_value=[(k, f"/dev/hidraw{i}".encode(), False) for i, k in enumerate(keys)],
    ), patch.object(
        PyDualSenseController,
        "_open_one",
        side_effect=lambda path, *, is_edge: fila.pop(0),
    ), patch("hefesto_dualsense4unix.core.sysfs_leds.discover", return_value={}):
        inst.connect()


class TestDesiredPorControle:
    """PERFIL-01 (4P-01): o hotplug reaplica o desejado DO CONTROLE CERTO."""

    def test_replug_do_controle_1_nao_herda_a_cor_do_controle_2(self) -> None:
        """O bug PROVADO AO VIVO: mirar o Controle 2 no seletor e replugar o
        Controle 1 o pintava com a cor do 2 (o `_desired` era global)."""
        inst, _h1, _h2 = _with_two_macs()
        inst.set_led((10, 10, 10))  # cor A, broadcast (perfil)
        inst.set_output_target(1)  # seletor: Controle 2
        inst.set_led((0, 255, 0))  # cor B só nele
        inst.set_output_target(None)

        _reconcile(inst, keys=[KEY_2], opened=[])  # Controle 1 desconecta
        assert KEY_1 not in inst._handles
        h1b = _FakeHandle()
        _reconcile(inst, keys=[KEY_2, KEY_1], opened=[h1b])  # ...e volta

        assert h1b.light.colors[-1] == (10, 10, 10)  # cor A — NUNCA a B do outro
        assert (0, 255, 0) not in h1b.light.colors

    def test_replug_do_alvo_recebe_o_proprio_override(self) -> None:
        inst, _h1, _h2 = _with_two_macs()
        inst.set_led((10, 10, 10))
        inst.set_output_target(1)
        inst.set_led((0, 255, 0))
        inst.set_output_target(None)

        _reconcile(inst, keys=[KEY_1], opened=[])  # Controle 2 desconecta
        h2b = _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h2b])

        assert h2b.light.colors[-1] == (0, 255, 0)  # o override DELE sobrevive

    def test_override_parcial_faz_merge_por_campo_no_replug(self) -> None:
        """Exigido pela revisão: só triggers no override → replug recebe os
        triggers do override E a cor global (nunca resolução por objeto)."""
        inst, _h1, _h2 = _with_two_macs()
        inst.set_led((10, 20, 30))  # cor global do perfil
        inst.set_output_target(1)
        inst.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        inst.set_output_target(None)

        _reconcile(inst, keys=[KEY_1], opened=[])
        h2b = _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h2b])

        assert h2b.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]  # override
        assert h2b.light.colors[-1] == (10, 20, 30)  # + cor global (merge)

    def test_reset_na_ativacao_nada_do_perfil_anterior_ressuscita(self) -> None:
        """Ativar perfil com override e depois perfil SEM `controllers`:
        o replug recebe o default do perfil novo (mapa substituído)."""
        inst, _h1, _h2 = _with_two_macs()
        # Perfil 1: default vermelho + override verde no Controle 2 (o fluxo
        # que o ProfileManager.apply executa; PERFIL-02 pluga o JSON).
        inst.apply_output_defaults(OutputSpec(led=(255, 0, 0)))
        inst.reset_output_overrides({UNIQ_2: OutputSpec(led=(0, 255, 0))})
        # Perfil 2: sem overrides.
        inst.apply_output_defaults(OutputSpec(led=(0, 0, 255)))
        inst.reset_output_overrides(None)

        _reconcile(inst, keys=[KEY_1], opened=[])
        h2b = _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h2b])

        assert h2b.light.colors[-1] == (0, 0, 255)  # default novo, sem fantasma

    def test_apply_output_for_desconectado_fica_registrado_e_aplica_no_hotplug(
        self,
    ) -> None:
        """Override de controle DESCONECTADO entra no mapa (só a escrita de
        hardware é pulada) — "aplica quando chegar" exige o registro."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        inst._handles = {KEY_1: h1}  # type: ignore[dict-item]
        inst._primary_key = KEY_1
        inst.apply_output_defaults(OutputSpec(led=(10, 20, 30)))
        inst.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))  # nem plugado

        h2 = _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h2])

        assert h2.light.colors[-1] == (0, 255, 0)  # chegou e recebeu o DELE
        assert h1.light.colors[-1] == (10, 20, 30)  # o conectado ficou no global

    def test_apply_output_for_conectado_escreve_no_hardware_na_hora(self) -> None:
        inst, _h1, h2 = _with_two_macs()
        inst.apply_output_for(UNIQ_2, OutputSpec(led=(0, 255, 0)))
        assert h2.light.colors == [(0, 255, 0)]
        assert _h1.light.colors == []

    def test_multi_2p_cada_controle_mantem_o_seu_no_replug(self) -> None:
        """Cenário 2P: um override para cada — replug devolve o de CADA um."""
        inst, _h1, _h2 = _with_two_macs()
        inst.set_output_target(0)
        inst.set_led((255, 0, 0))  # Controle 1: vermelho
        inst.set_output_target(1)
        inst.set_led((0, 0, 255))  # Controle 2: azul
        inst.set_output_target(None)

        _reconcile(inst, keys=[], opened=[])  # os dois saem
        h1b, h2b = _FakeHandle(), _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h1b, h2b])

        assert h1b.light.colors[-1] == (255, 0, 0)
        assert h2b.light.colors[-1] == (0, 0, 255)

    def test_mic_led_mirado_nao_vaza_no_replug_de_outro_controle(self) -> None:
        """A cura de carona do PERFIL-01: o mic-LED mirado persistia no
        `_desired` global e vazava no hotplug de OUTRO controle."""
        inst, _h1, _h2 = _with_two_macs()
        inst.set_output_target(1)
        inst.set_mic_led(True)  # só no Controle 2
        inst.set_output_target(None)

        _reconcile(inst, keys=[KEY_2], opened=[])
        h1b = _FakeHandle()
        _reconcile(inst, keys=[KEY_2, KEY_1], opened=[h1b])

        assert h1b.audio.mic_led_history == []  # nada herdado

    def test_perfil_broadcast_apos_override_pinta_todos_e_replug_segue_o_novo(
        self,
    ) -> None:
        """Regressão do caso mono-perfil: broadcast novo vence overrides velhos
        (o campo escrito é limpo do mapa — "um voltou verde" é proibido)."""
        inst, h1, h2 = _with_two_macs()
        inst.set_output_target(1)
        inst.set_led((0, 255, 0))
        inst.set_output_target(None)
        inst.set_led((0, 0, 255))  # "Todos"

        assert h1.light.colors[-1] == (0, 0, 255)
        assert h2.light.colors[-1] == (0, 0, 255)
        _reconcile(inst, keys=[KEY_1], opened=[])
        h2b = _FakeHandle()
        _reconcile(inst, keys=[KEY_1, KEY_2], opened=[h2b])
        assert h2b.light.colors[-1] == (0, 0, 255)  # não "voltou verde"
