"""O-BACKEND-NAO-LE-O-HIDRAW-DA-MAQUINA-NA-SUITE-01 — a raiz do hidraw do backend se desvia."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

DS = 0x0CE6
EDGE = 0x0DF2
USB = "0003"
BT = "0005"
SERIAIS = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]


def _no(
    raiz: Path,
    nome: str,
    barramento: str,
    *,
    uniq: str = "",
    phys: str = "",
    virtual: bool = False,
) -> None:
    """Um ``hidrawN`` com ``device`` link para o pai HID e o ``uevent`` dele."""
    base = raiz.parent / "devices"
    if virtual:
        pai = base / "virtual" / "misc" / "uhid" / f"{barramento}:054C:0CE6.{nome[-3:]}"
    else:
        pai = base / "pci0000:00" / "usb3" / f"{barramento}:054C:0CE6.{nome[-3:]}"
    pai.mkdir(parents=True, exist_ok=True)
    (pai / "uevent").write_text(
        f"HID_ID={barramento}:0000054C:00000CE6\nHID_PHYS={phys}\nHID_UNIQ={uniq}\n",
        encoding="utf-8",
    )
    (raiz / nome).mkdir(parents=True)
    os.symlink(pai, raiz / nome / "device")


@pytest.fixture
def raiz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A árvore de mentira, apontada por cima da pasta vazia da irmã do conftest."""
    arvore = tmp_path / "sys" / "class" / "hidraw"
    arvore.mkdir(parents=True)
    monkeypatch.setattr(bp, "RAIZ_CLASS_HIDRAW", str(arvore))
    return arvore


def _enumerar(monkeypatch: pytest.MonkeyPatch, vistos: list[SimpleNamespace]):
    fake_hidapi = SimpleNamespace(enumerate=lambda vendor_id: list(vistos))
    monkeypatch.setitem(sys.modules, "hidapi", fake_hidapi)
    return PyDualSenseController._enumerate_device_keys()


def _info(no: str, serial: str | None, pid: int = DS) -> SimpleNamespace:
    return SimpleNamespace(
        product_id=pid, path=f"/dev/{no}".encode(), serial_number=serial
    )


class TestODesvioEstaArmado:
    def test_a_raiz_do_backend_e_uma_pasta_vazia_na_suite(self) -> None:
        """Mordida: tire a linha da irmã do conftest, e a raiz volta a ser a da máquina."""
        raiz = bp.RAIZ_CLASS_HIDRAW
        assert raiz != "/sys/class/hidraw"
        assert Path(raiz).is_dir()
        assert list(Path(raiz).iterdir()) == []

    def test_sem_arvore_o_primeiro_vence_e_ninguem_e_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com a raiz vazia o barramento é «não sei» nos dois nós: fica o primeiro."""
        keys = _enumerar(
            monkeypatch, [_info("hidraw900", SERIAIS[0]), _info("hidraw901", SERIAIS[0])]
        )
        assert keys == [(SERIAIS[0], b"/dev/hidraw900", False)]


class TestODedupePelaRaizDeMentira:
    @pytest.mark.parametrize("ordem", ["radio-primeiro", "cabo-primeiro"])
    def test_o_cabo_vence_em_qualquer_ordem(
        self, monkeypatch: pytest.MonkeyPatch, raiz: Path, ordem: str
    ) -> None:
        """Mordida: devolva o caminho fixo ao ``_hidraw_uevent`` e isto reprova."""
        _no(raiz, "hidraw900", BT, uniq=SERIAIS[0])
        _no(raiz, "hidraw901", USB, uniq=SERIAIS[0])
        radio = _info("hidraw900", SERIAIS[0])
        cabo = _info("hidraw901", SERIAIS[0])
        vistos = [radio, cabo] if ordem == "radio-primeiro" else [cabo, radio]
        assert _enumerar(monkeypatch, vistos) == [(SERIAIS[0], b"/dev/hidraw901", False)]

    def test_dois_nos_no_radio_fica_o_primeiro(
        self, monkeypatch: pytest.MonkeyPatch, raiz: Path
    ) -> None:
        _no(raiz, "hidraw900", BT, uniq=SERIAIS[0])
        _no(raiz, "hidraw901", BT, uniq=SERIAIS[0])
        _no(raiz, "hidraw902", BT, uniq=SERIAIS[1])
        keys = _enumerar(
            monkeypatch,
            [
                _info("hidraw900", SERIAIS[0]),
                _info("hidraw901", SERIAIS[0]),
                _info("hidraw902", SERIAIS[1]),
            ],
        )
        assert keys == [
            (SERIAIS[0], b"/dev/hidraw900", False),
            (SERIAIS[1], b"/dev/hidraw902", False),
        ]

    def test_quatro_controles_cabo_e_radio_misturados_e_o_vpad_sai(
        self, monkeypatch: pytest.MonkeyPatch, raiz: Path
    ) -> None:
        """P1 a P4, cada um no próprio nó; o vpad (``hefesto-vpad`` sob uhid) sai."""
        _no(raiz, "hidraw900", USB, uniq=SERIAIS[0])
        _no(raiz, "hidraw901", BT, uniq=SERIAIS[1], virtual=True)
        _no(raiz, "hidraw902", USB, uniq=SERIAIS[2])
        _no(raiz, "hidraw903", BT, uniq=SERIAIS[3])
        _no(
            raiz, "hidraw904", USB, uniq="02:fe:00:00:00:01", phys="hefesto-vpad", virtual=True
        )
        keys = _enumerar(
            monkeypatch,
            [
                _info("hidraw900", SERIAIS[0]),
                _info("hidraw901", SERIAIS[1]),
                _info("hidraw902", SERIAIS[2], EDGE),
                _info("hidraw903", SERIAIS[3]),
                _info("hidraw904", "02:fe:00:00:00:01"),
            ],
        )
        assert keys == [
            (SERIAIS[0], b"/dev/hidraw900", False),
            (SERIAIS[1], b"/dev/hidraw901", False),
            (SERIAIS[2], b"/dev/hidraw902", True),
            (SERIAIS[3], b"/dev/hidraw903", False),
        ]

    def test_o_mesmo_controle_nos_dois_barramentos_entre_os_quatro(
        self, monkeypatch: pytest.MonkeyPatch, raiz: Path
    ) -> None:
        """O P2 no rádio e no cabo: fica o cabo, no lugar em que o rádio entrou."""
        _no(raiz, "hidraw900", BT, uniq=SERIAIS[0])
        _no(raiz, "hidraw901", BT, uniq=SERIAIS[1])
        _no(raiz, "hidraw902", USB, uniq=SERIAIS[2])
        _no(raiz, "hidraw903", USB, uniq=SERIAIS[1])
        keys = _enumerar(
            monkeypatch,
            [
                _info("hidraw900", SERIAIS[0]),
                _info("hidraw901", SERIAIS[1]),
                _info("hidraw902", SERIAIS[2]),
                _info("hidraw903", SERIAIS[1]),
            ],
        )
        assert keys == [
            (SERIAIS[0], b"/dev/hidraw900", False),
            (SERIAIS[1], b"/dev/hidraw903", False),
            (SERIAIS[2], b"/dev/hidraw902", False),
        ]


class TestOVermelhoDas15h15SemDependerDoBoot:
    def test_com_o_hidraw0_no_radio_e_o_hidraw1_no_cabo_o_hidraw1_vence(
        self, monkeypatch: pytest.MonkeyPatch, raiz: Path
    ) -> None:
        """A máquina de 28/09 às 15h15, reproduzida: o «1º vence» só vale com a raiz vazia."""
        _no(raiz, "hidraw0", BT, uniq=SERIAIS[0])
        _no(raiz, "hidraw1", USB, uniq=SERIAIS[0])
        keys = _enumerar(
            monkeypatch, [_info("hidraw0", SERIAIS[0]), _info("hidraw1", SERIAIS[0])]
        )
        assert keys == [(SERIAIS[0], b"/dev/hidraw1", False)]
