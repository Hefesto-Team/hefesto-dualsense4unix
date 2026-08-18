"""O daemon não pode adotar o PRÓPRIO vpad uhid como controle físico.

Regressão nova do SPRINT-UHID-VPAD-01: o vpad passou a ser um device HID de
verdade, com **hidraw** e com VID/PID/bus idênticos ao controle real (é o que faz
o `hid_playstation` fazer bind nele). O `_enumerate_device_keys` filtrava só por
vendor/product — então enumerava o vpad como se fosse mais um controle: feedback
loop (o daemon lendo a própria saída) e "3 controles" com dois na mesa.

O `evdev_reader` já tinha o `_is_virtual_evdev` por essa exata razão; o caminho
hidraw nunca precisou, porque uinput não cria hidraw.

Medido ao vivo antes do fix: com o vpad no ar, o enumerate devolvia
``('02:fe:00:00:00:02', b'/dev/hidraw7', False)`` — o MAC que nós mesmos forjamos.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import _is_virtual_hidraw


class TestIsVirtualHidraw:
    def test_hidraw_de_uhid_e_virtual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Os uhid do VPAD vivem sob /sys/devices/virtual/misc/uhid/."""
        monkeypatch.setattr(
            "os.path.realpath",
            lambda _p: "/sys/devices/virtual/misc/uhid/0003:054C:0CE6.001D",
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.backend_pydualsense._hidraw_uevent",
            lambda _n: {"HID_PHYS": "hefesto-vpad", "HID_UNIQ": "02:fe:00:00:00:01"},
        )

        assert _is_virtual_hidraw(b"/dev/hidraw7") is True

    def test_hidraw_de_controle_usb_nao_e_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "os.path.realpath",
            lambda _p: (
                "/sys/devices/pci0000:00/0000:00:08.1/0000:0c:00.3/usb3/3-4/"
                "3-4:1.3/0003:054C:0CE6.0009"
            ),
        )

        assert _is_virtual_hidraw(b"/dev/hidraw4") is False

    def test_hidraw_de_controle_bluetooth_nao_e_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "os.path.realpath",
            lambda _p: (
                "/sys/devices/pci0000:00/0000:00:08.1/0000:0c:00.3/usb3/3-1/"
                "3-1:1.0/bluetooth/hci0/hci0:4/0005:054C:0CE6.000A"
            ),
        )

        assert _is_virtual_hidraw(b"/dev/hidraw5") is False

    def test_path_que_nao_e_hidraw_nao_e_filtrado(self) -> None:
        """Path de libusb ("0001:0002:00") não é nó do sysfs — não some da lista."""
        assert _is_virtual_hidraw(b"0001:0002:00") is False

    def test_sysfs_ausente_nao_explode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replug entre o enumerate e o realpath: na dúvida, NÃO filtra."""

        def _boom(_p: str) -> str:
            raise OSError("sumiu")

        monkeypatch.setattr("os.path.realpath", _boom)

        assert _is_virtual_hidraw(b"/dev/hidraw9") is False


class TestBluezUhidFisicoNaoEVirtual:
    """BLUEZ-UHID-01: com BlueZ ≥5.73 (UserspaceHID) o bluetoothd cria os HIDs
    dos controles BT FÍSICOS via /dev/uhid — mesmo subtree do vpad. O critério
    de topologia (`/devices/virtual/`) virou falso-positivo em massa: medido ao
    vivo em 2026-07-19 (backport 5.85), os 4 controles BT ficaram invisíveis
    (`connected: False` com 4 hidraws saudáveis). Identidade decide, não morada.
    """

    _UHID_BT = "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0015"

    def _com_uevent(
        self, monkeypatch: pytest.MonkeyPatch, uevent: dict[str, str]
    ) -> None:
        monkeypatch.setattr("os.path.realpath", lambda _p: self._UHID_BT)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.backend_pydualsense._hidraw_uevent",
            lambda _n: uevent,
        )

    def test_dualsense_bt_via_bluetoothd_uhid_nao_e_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A regressão do dia: físico BT sob uhid TEM de ser enxergado."""
        self._com_uevent(
            monkeypatch,
            {
                "HID_ID": "0005:0000054C:00000CE6",
                "HID_PHYS": "aa:bb:cc:00:00:05",
                "HID_UNIQ": "aa:bb:cc:00:00:02",
            },
        )

        assert _is_virtual_hidraw(b"/dev/hidraw4") is False

    def test_vpad_por_phys_e_virtual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._com_uevent(
            monkeypatch, {"HID_PHYS": "hefesto-vpad", "HID_UNIQ": "02:fe:00:00:00:02"}
        )

        assert _is_virtual_hidraw(b"/dev/hidraw5") is True

    def test_vpad_por_uniq_e_virtual_mesmo_sem_phys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Defesa em profundidade: o prefixo 02:fe basta (D9 do identity)."""
        self._com_uevent(monkeypatch, {"HID_UNIQ": "02:FE:00:00:00:03"})

        assert _is_virtual_hidraw(b"/dev/hidraw6") is True

    def test_uevent_ilegivel_sob_virtual_continua_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na dúvida o risco maior é o feedback loop de auto-adoção."""
        self._com_uevent(monkeypatch, {})

        assert _is_virtual_hidraw(b"/dev/hidraw7") is True


class TestEnumeracaoIgnoraOVpad:
    def test_vpad_nao_entra_na_lista_de_controles(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com 2 físicos + 1 vpad no ar, o daemon tem de enxergar 2."""
        from hefesto_dualsense4unix.core import backend_pydualsense as bp

        class _Info:
            def __init__(self, serial: str, path: bytes) -> None:
                self.serial_number = serial
                self.path = path
                self.product_id = 0x0CE6

        fisico_usb = _Info("aa:bb:cc:00:00:01", b"/dev/hidraw4")
        fisico_bt = _Info("aa:bb:cc:00:00:02", b"/dev/hidraw5")
        nosso_vpad = _Info("02:fe:00:00:00:02", b"/dev/hidraw7")

        monkeypatch.setattr(
            bp, "hidapi", type("_H", (), {"enumerate": staticmethod(
                lambda **_kw: [fisico_usb, fisico_bt, nosso_vpad])})(),
            raising=False,
        )
        monkeypatch.setitem(
            __import__("sys").modules, "hidapi",
            type("_H", (), {"enumerate": staticmethod(
                lambda **_kw: [fisico_usb, fisico_bt, nosso_vpad])})(),
        )
        monkeypatch.setattr(
            bp, "_is_virtual_hidraw", lambda path: path == b"/dev/hidraw7"
        )

        chaves = bp.PyDualSenseController._enumerate_device_keys()

        seriais = [k for k, _path, _edge in chaves]
        assert seriais == ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"]
        assert "02:fe:00:00:00:02" not in seriais, (
            "o daemon adotou o próprio vpad como controle físico — feedback loop"
        )

    def test_vpad_edge_0df2_filtrado_mas_edge_fisico_adotado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPAD-04 (ressalva): 0x0DF2 está em `DUALSENSE_PIDS` porque o Edge
        FÍSICO existe — o que separa o NOSSO vpad Edge (uhid E uinput nascem
        0df2 agora) de um Edge de verdade é a ancestralidade virtual, nunca o
        VID/PID."""
        from hefesto_dualsense4unix.core import backend_pydualsense as bp

        class _Info:
            def __init__(self, serial: str, path: bytes) -> None:
                self.serial_number = serial
                self.path = path
                self.product_id = 0x0DF2

        edge_fisico = _Info("e8:47:3a:00:00:01", b"/dev/hidraw3")
        nosso_vpad = _Info("02:fe:00:00:00:01", b"/dev/hidraw8")

        monkeypatch.setitem(
            __import__("sys").modules, "hidapi",
            type("_H", (), {"enumerate": staticmethod(
                lambda **_kw: [edge_fisico, nosso_vpad])})(),
        )
        monkeypatch.setattr(
            bp, "_is_virtual_hidraw", lambda path: path == b"/dev/hidraw8"
        )

        chaves = bp.PyDualSenseController._enumerate_device_keys()

        assert [(k, edge) for k, _path, edge in chaves] == [
            ("e8:47:3a:00:00:01", True)  # o Edge físico entra, flagado como Edge
        ], "o vpad Edge (0df2) entrou na enumeração — feedback loop do UHID-02"
