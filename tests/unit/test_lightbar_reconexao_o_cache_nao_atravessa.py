"""A barra apagada na volta do controle: o cache do nó sysfs NÃO pode atravessar"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import sysfs_leds
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _DesiredOutput,
)
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    _FakeHandle,
    _null_evdev,
)

MAC = KEY_1
VERMELHO = (255, 0, 0)


def _monta_no(raiz: Path, prefixo: str) -> None:
    """Cria no /sys falso o nó LED de UM controle, com o layout do kernel."""
    dev = raiz / "devices" / prefixo
    dev.mkdir(parents=True, exist_ok=True)
    (dev / "uevent").write_text(f"HID_UNIQ={MAC}\n")
    leds_class = raiz / "class" / "leds"
    leds_class.mkdir(parents=True, exist_ok=True)
    indicador = dev / "leds" / f"{prefixo}:rgb:indicator"
    indicador.mkdir(parents=True, exist_ok=True)
    (indicador / "multi_intensity").write_text("0 0 0")
    (indicador / "brightness").write_text("0")
    (leds_class / f"{prefixo}:rgb:indicator").symlink_to(indicador)


def _derruba_no(raiz: Path, prefixo: str) -> None:
    """O controle sumiu: o kernel remove o nó LED junto com o device."""
    (raiz / "class" / "leds" / f"{prefixo}:rgb:indicator").unlink()
    shutil.rmtree(raiz / "devices" / prefixo)


class _Espiao:
    """Conta as escritas REAIS em ``multi_intensity``, por nó."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.escritas: list[tuple[str, str]] = []
        original = sysfs_leds.SysfsLedNode._write

        def espiar(path: str, data: str) -> bool:
            ok = original(path, data)
            if path.endswith("multi_intensity"):
                self.escritas.append((Path(path).parent.name, data))
            return ok

        monkeypatch.setattr(
            sysfs_leds.SysfsLedNode, "_write", staticmethod(espiar)
        )

    def no(self, prefixo: str) -> list[str]:
        return [d for nome, d in self.escritas if nome.startswith(prefixo)]


@pytest.fixture
def sys_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "sys"
    raiz.mkdir()
    _monta_no(raiz, "input799")
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(raiz / "class" / "leds"))
    return raiz


def _backend() -> PyDualSenseController:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    inst._handles = {KEY_1: _FakeHandle()}  # type: ignore[dict-item]
    inst._primary_key = KEY_1
    inst._desired_default = _DesiredOutput(led=VERMELHO)
    return inst


def _tick(inst: PyDualSenseController) -> None:
    """Um tick de hotplug: o mesmo par que o `connect()` roda no fim."""
    inst._refresh_sysfs_leds()
    inst.reassert_resolved_outputs()


@pytest.mark.parametrize("prefixo_da_volta", ["input803", "input799"])
def test_controle_que_volta_recebe_a_cor_de_novo(
    sys_falso: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefixo_da_volta: str,
) -> None:
    """A sequência do defeito: presente, cor escrita, some, volta, MESMA cor."""
    espiao = _Espiao(monkeypatch)
    inst = _backend()

    _tick(inst)
    assert espiao.no("input799") == ["255 0 0"], (
        "o controle presente tinha de receber a cor uma vez"
    )

    _derruba_no(sys_falso, "input799")
    inst._handles = {}
    _tick(inst)

    espiao.escritas.clear()
    _monta_no(sys_falso, prefixo_da_volta)
    inst._handles = {KEY_1: _FakeHandle()}  # type: ignore[dict-item]
    _tick(inst)

    assert espiao.no(prefixo_da_volta) == ["255 0 0"], (
        "a barra fica apagada porque o cache mentiu: o controle voltou com a "
        "lightbar apagada do zero e o daemon PULOU a reescrita, acreditando "
        "numa cor que ele escreveu no nó ANTERIOR. O nó que volta tem de "
        f"nascer sem memória (escritas vistas: {espiao.escritas})"
    )
    no = inst._sysfs[KEY_1]
    assert Path(no._multi_intensity).read_text() == "255 0 0"


def test_o_no_do_mapa_e_outro_objeto_depois_da_reconexao(
    sys_falso: Path,
) -> None:
    """O mecanismo que sustenta o teste acima, dito por extenso."""
    inst = _backend()
    _tick(inst)
    antes = inst._sysfs[KEY_1]
    assert antes._last_write == (VERMELHO, 255)

    _derruba_no(sys_falso, "input799")
    inst._handles = {}
    _tick(inst)
    assert KEY_1 not in inst._sysfs, "nó que sumiu tem de sair do mapa"

    _monta_no(sys_falso, "input803")
    inst._handles = {KEY_1: _FakeHandle()}  # type: ignore[dict-item]
    _tick(inst)
    depois = inst._sysfs[KEY_1]

    assert depois is not antes, (
        "o nó do mapa foi REAPROVEITADO na reconexão — o cache do controle "
        "velho atravessou a ausência e a próxima escrita da mesma cor será "
        "pulada com a barra apagada"
    )
