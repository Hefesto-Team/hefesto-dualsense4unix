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
from typing import Any

from hefesto_dualsense4unix.broker.hidraw_broker import (
    FsAclOps,
    _hidraw_devinfo_identity_ok,
)


class TestDevinfoIdentity:
    def test_dualsense_fisico_aceito(self) -> None:
        assert _hidraw_devinfo_identity_ok(0x054C, 0x0CE6) is True

    def test_o_edge_e_da_familia(self) -> None:
        # STEAM-NO-FISICO-01 (24/09/2026): o Edge físico (054c:0df2) entrou.
        # O devinfo não separa o Edge do NOSSO vpad (os dois são 0003:054c:0df2
        # pelo cabo) — quem separa é o cinto do sysfs, que o `open_node` roda
        # logo depois deste (ver `TestSysfsHidIdentity`).
        assert _hidraw_devinfo_identity_ok(0x054C, 0x0DF2) is True

    def test_outro_device_rejeitado(self) -> None:
        assert _hidraw_devinfo_identity_ok(0x045E, 0x028E) is False  # Xbox
        assert _hidraw_devinfo_identity_ok(0x3554, 0xFA09) is False  # receiver
        assert _hidraw_devinfo_identity_ok(0x057E, 0x2009) is False  # Pro BT

    def test_representacao_s16_negativa_normalizada(self) -> None:
        # vendor/product vêm do kernel como __s16; a máscara 0xFFFF normaliza.
        assert _hidraw_devinfo_identity_ok(0x054C - 0x10000, 0x0CE6 - 0x10000) is True
        assert _hidraw_devinfo_identity_ok(-1, -1) is False


class TestSysfsHidIdentity:
    def _ops(
        self,
        tmp_path: Path,
        hid_id: str | None,
        *,
        sob_uhid: bool = False,
        extra: str = "",
    ) -> tuple[FsAclOps, str]:
        sys_hidraw = tmp_path / "sys" / "class" / "hidraw"
        base = "hidraw3"
        if sob_uhid:
            # O rádio do BlueZ ≥5.73 E o nosso vpad moram aqui.
            alvo = tmp_path / "sys" / "devices" / "virtual" / "misc" / "uhid" / "x.0001"
            alvo.mkdir(parents=True)
            (sys_hidraw / base).mkdir(parents=True)
            (sys_hidraw / base / "device").symlink_to(alvo)
            dev_dir = sys_hidraw / base / "device"
        else:
            dev_dir = sys_hidraw / base / "device"
            dev_dir.mkdir(parents=True)
        if hid_id is not None:
            (dev_dir / "uevent").write_text(
                f"DRIVER=playstation\nHID_ID={hid_id}\nHID_NAME=x\n{extra}",
                encoding="ascii",
            )
        return FsAclOps(sys_class_hidraw=str(sys_hidraw)), base

    def test_dualsense_bt_ok(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "0005:0000054C:00000CE6")
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_dualsense_usb_ok(self, tmp_path: Path) -> None:
        ops, base = self._ops(tmp_path, "0003:0000054C:00000CE6")
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_o_edge_fisico_pelo_cabo_ok(self, tmp_path: Path) -> None:
        # STEAM-NO-FISICO-01: pai USB real, 0df2 = o Edge FÍSICO.
        ops, base = self._ops(tmp_path, "0003:0000054C:00000DF2")
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_o_edge_fisico_pelo_radio_sob_uhid_ok(self, tmp_path: Path) -> None:
        ops, base = self._ops(
            tmp_path,
            "0005:0000054C:00000DF2",
            sob_uhid=True,
            extra="HID_PHYS=aa:bb:cc:00:00:01\nHID_UNIQ=e8:47:3a:00:00:07\n",
        )
        assert ops._sysfs_hid_identity_ok(base) is True

    def test_o_vpad_sob_uhid_e_rejeitado_mesmo_sem_as_marcas(self, tmp_path: Path) -> None:
        # D1: USB sob `/misc/uhid/` é o vpad — um nome reciclado para ele
        # NUNCA recebe chmod (fechar o vpad é tirar o controle do jogo).
        ops, base = self._ops(tmp_path, "0003:0000054C:00000DF2", sob_uhid=True)
        assert ops._sysfs_hid_identity_ok(base) is False

    def test_o_vpad_pelas_marcas_e_rejeitado_em_qualquer_topologia(
        self, tmp_path: Path
    ) -> None:
        # D2: o `phys` do vpad basta, com ou sem a topologia.
        ops, base = self._ops(
            tmp_path, "0003:0000054C:00000DF2", extra="HID_PHYS=hefesto-vpad\n"
        )
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


class TestOOpenNaoServeOVpad:
    """STEAM-NO-FISICO-01: o `open_node` passa pelo MESMO cinto do sysfs.

    O HIDIOCGRAWINFO do Edge físico pelo cabo e o do nosso vpad são iguais
    (0003:054c:0df2): depois que o Edge entrou na família, o devinfo sozinho
    serviria o vpad como físico num nome reciclado. O cinto do sysfs, rodado
    depois do ioctl, recusa. A MORDIDA: tire o cinto do `open_node` e o vpad
    sai daqui com fd.
    """

    def _abrir(
        self, tmp_path: Path, monkeypatch: Any, *, sob_uhid: bool
    ) -> Any:
        import fcntl
        import os
        import stat
        import struct
        from types import SimpleNamespace

        from hefesto_dualsense4unix.broker import hidraw_broker as hb

        ops, base = TestSysfsHidIdentity()._ops(
            tmp_path, "0003:0000054C:00000DF2", sob_uhid=sob_uhid
        )
        arquivo = tmp_path / "no"
        arquivo.write_bytes(b"")
        abrir_de_verdade = os.open
        fstat_de_verdade = os.fstat
        abertos: list[int] = []

        def _open(_node: str, _flags: int, *_a: Any) -> int:
            fd = abrir_de_verdade(str(arquivo), os.O_RDONLY)
            abertos.append(fd)
            return fd

        def _fstat(fd: int) -> Any:
            if fd in abertos:
                return SimpleNamespace(
                    st_mode=stat.S_IFCHR | 0o660, st_rdev=os.makedev(237, 3)
                )
            return fstat_de_verdade(fd)

        def _ioctl(_fd: int, _req: int, buf: Any, _mut: bool = True) -> int:
            buf[:] = struct.pack("=Ihh", 0x0003, 0x054C, 0x0DF2)
            return 0

        monkeypatch.setattr(hb.os, "open", _open)
        monkeypatch.setattr(hb.os, "fstat", _fstat)
        monkeypatch.setattr(fcntl, "ioctl", _ioctl)
        monkeypatch.setattr(ops, "_sysfs_rdev", lambda _b: (237, 3))
        return ops, base, abertos

    def test_o_vpad_nao_sai_com_fd(self, tmp_path: Path, monkeypatch: Any) -> None:
        import os

        import pytest

        from hefesto_dualsense4unix.broker.hidraw_broker import StaleNodeError

        ops, base, abertos = self._abrir(tmp_path, monkeypatch, sob_uhid=True)

        with pytest.raises(StaleNodeError):
            ops.open_node(f"/dev/{base}", base)

        # E o fd da tentativa foi fechado: nenhum caminho vaza fd.
        assert abertos
        assert not os.path.exists(f"/proc/self/fd/{abertos[0]}")

    def test_o_edge_fisico_sai_com_fd(self, tmp_path: Path, monkeypatch: Any) -> None:
        import os

        ops, base, abertos = self._abrir(tmp_path, monkeypatch, sob_uhid=False)

        fd = ops.open_node(f"/dev/{base}", base)
        try:
            assert fd == abertos[0]
        finally:
            os.close(fd)
