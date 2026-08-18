"""S-4 (auditoria 21/07) — identidade race-free contra minor-reuse.

O check rdev(fd)==sysfs(base) do broker prova nó==base, NÃO a identidade do
device: no minor-reuse (o nome `base` reciclado para OUTRO device no mesmo
major:minor entre validar e abrir) o broker serviria um fd O_RDWR de ROOT de
um hidraw alheio (teclado BT = keylogger). Fixes:
- `open_node`: HIDIOCGRAWINFO no PRÓPRIO fd (bustype/vendor/product do kernel).
- `_pin` (hide/restore, O_PATH sem ioctl): re-lê o HID_ID do uevent.

Ambos entram DEPOIS do check de char/rdev — os testes de arquivo-comum
(`TestFsAclOpsPinado`) barram antes, intocados. Aqui exercitamos a lógica de
identidade isolada (a integração do ioctl é validada ao vivo contra o kernel).
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.broker.hidraw_broker import (
    FsAclOps,
    _hidraw_devinfo_identity_ok,
)


class TestDevinfoIdentity:
    def test_dualsense_fisico_aceito(self) -> None:
        assert _hidraw_devinfo_identity_ok(0x054C, 0x0CE6) is True

    def test_vpad_edge_rejeitado(self) -> None:
        # 054c:0df2 é o NOSSO vpad — nunca pode ser servido como físico.
        assert _hidraw_devinfo_identity_ok(0x054C, 0x0DF2) is False

    def test_outro_device_rejeitado(self) -> None:
        assert _hidraw_devinfo_identity_ok(0x045E, 0x028E) is False  # Xbox
        assert _hidraw_devinfo_identity_ok(0x3554, 0xFA09) is False  # receiver
        assert _hidraw_devinfo_identity_ok(0x057E, 0x2009) is False  # Pro BT

    def test_representacao_s16_negativa_normalizada(self) -> None:
        # vendor/product vêm do kernel como __s16; a máscara 0xFFFF normaliza.
        assert _hidraw_devinfo_identity_ok(0x054C - 0x10000, 0x0CE6 - 0x10000) is True
        assert _hidraw_devinfo_identity_ok(-1, -1) is False


class TestSysfsHidIdentity:
    def _ops(self, tmp_path: Path, hid_id: str | None) -> tuple[FsAclOps, str]:
        sys_hidraw = tmp_path / "sys" / "class" / "hidraw"
        base = "hidraw3"
        dev_dir = sys_hidraw / base / "device"
        dev_dir.mkdir(parents=True)
        if hid_id is not None:
            (dev_dir / "uevent").write_text(
                f"DRIVER=playstation\nHID_ID={hid_id}\nHID_NAME=x\n",
                encoding="ascii",
            )
        return FsAclOps(sys_class_hidraw=str(sys_hidraw)), base

    def test_dualsense_bt_ok(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "0005:0000054C:00000CE6")
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_dualsense_usb_ok(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "0003:0000054C:00000CE6")
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_vpad_edge_rejeitado(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "0003:0000054C:00000DF2")
        assert ops._sysfs_hid_identity_ok(base) is False

    def test_teclado_bt_rejeitado(self, tmp_path: Path) -> None:
        # O device reciclado no minor (o alvo do ataque) não é o DualSense.
        ops, base = self._ops(tmp_path, "0005:00001234:00005678")
        assert ops._sysfs_hid_identity_ok(base) is False

    def test_uevent_ilegivel_prossegue(self, tmp_path: Path) -> None:
        # Esconder/apagar o uevent exige root; um atacante não-root (a ameaça
        # do minor-reuse) nunca chega a esse estado → prossegue (True).
        ops, base = self._ops(tmp_path, None)
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_uevent_sem_hid_id_rejeitado(self, tmp_path: Path) -> None:
        sys_hidraw = tmp_path / "sys" / "class" / "hidraw"
        (sys_hidraw / "hidraw3" / "device").mkdir(parents=True)
        (sys_hidraw / "hidraw3" / "device" / "uevent").write_text(
            "DRIVER=foo\nHID_NAME=x\n", encoding="ascii"
        )
        ops = FsAclOps(sys_class_hidraw=str(sys_hidraw))
        assert ops._sysfs_hid_identity_ok("hidraw3") is False

    def test_hid_id_malformado_rejeitado(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "lixo")
        assert ops._sysfs_hid_identity_ok(base) is False
