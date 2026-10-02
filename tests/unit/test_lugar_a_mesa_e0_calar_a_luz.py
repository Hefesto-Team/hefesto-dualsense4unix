"""E0 da LUGAR-À-MESA-01 — *"calar a luz até a entrega existir"*."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core import external_leds as leds_mod
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)

MAC_PRO = "aa:bb:cc:00:be:01"
MAC_8BITDO = "aa:bb:cc:00:be:02"

INST_PRO = "0003:AABB:CC01.0001"

BOOT = "boot-e0-calar-a-luz"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """config_dir em tmp + boot_id fixo (o registro grava no disco)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)


def _entry(uniq: str, hidraw: str, path: str) -> dict[str, Any]:
    """Uma linha do inventário de externos, no formato que o tick consome."""
    return {
        "name": "Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "bluetooth",
        "uniq": uniq,
        "driver": "nintendo",
        "evdev_path": path,
        "hidraw": hidraw,
    }


def _mesa() -> list[dict[str, Any]]:
    """A mesa da queixa: um Pro Controller e um 8BitDo, os dois externos."""
    return [
        _entry(MAC_PRO, "/dev/hidraw7", "/dev/input/event261"),
        _entry(MAC_8BITDO, "/dev/hidraw2", "/dev/input/event262"),
    ]


def _sync(
    monkeypatch: pytest.MonkeyPatch,
    inventario: list[dict[str, Any]],
    *,
    ds_slots: dict[str, int] | None = None,
) -> ExternalLedSync:
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(e) for e in inventario]
    )
    daemon = SimpleNamespace(
        identity_registry=SimpleNamespace(snapshot=lambda: dict(ds_slots or {}))
    )
    return ExternalLedSync(daemon, ExternalIdentityRegistry())


def _barra_nintendo(raiz: Path, inst: str, acesos: tuple[int, ...]) -> None:
    """Cria a barra de player do hid-nintendo com ``acesos`` verdes ligados."""
    for i in range(1, 5):
        no = raiz / f"{inst}:green:player-{i}" / "brightness"
        no.parent.mkdir(parents=True, exist_ok=True)
        no.write_text("1" if i in acesos else "0", encoding="ascii")
    azul = raiz / f"{inst}:blue:player-5" / "brightness"
    azul.parent.mkdir(parents=True, exist_ok=True)
    azul.write_text("0", encoding="ascii")


def _retrato(raiz: Path) -> dict[str, str]:
    """Todo ``brightness`` da árvore, por caminho relativo — a foto do plástico."""
    return {
        str(p.relative_to(raiz)): p.read_text(encoding="ascii")
        for p in sorted(raiz.rglob("brightness"))
    }


@pytest.fixture()
def sysfs_de_led(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``LEDS_ROOT`` numa árvore de ``tmp_path``, com a barra do Pro montada."""
    raiz = tmp_path / "leds"
    raiz.mkdir()
    _barra_nintendo(raiz, INST_PRO, acesos=(1, 2))
    monkeypatch.setattr(leds_mod, "LEDS_ROOT", str(raiz))
    monkeypatch.setattr(
        leds_mod,
        "hid_instance_for_hidraw",
        lambda dev: INST_PRO if dev == "/dev/hidraw7" else None,
    )
    monkeypatch.setattr(leds_mod, "_hid_device_dir", lambda _dev: None)
    return raiz


@pytest.fixture()
def escritas_de_led(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Espia `apply_player_number` SEM ligar o interruptor."""
    escritas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        leds_mod,
        "apply_player_number",
        lambda hidraw, slot, *a, **k: (escritas.append((hidraw, slot)), True)[1],
    )
    return escritas


class _LoggerEspiao:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def info(self, evento: str, **kw: Any) -> None:
        self.eventos.append((evento, kw))

    def debug(self, *_a: Any, **_kw: Any) -> None: ...

    def warning(self, *_a: Any, **_kw: Any) -> None: ...

    def error(self, *_a: Any, **_kw: Any) -> None: ...


class TestCalarALuzAteAEntregaExistir:
    """Com o interruptor como sai de fábrica, o produto não afirma jogador."""

    def test_o_interruptor_e_entregue_desligado(self) -> None:
        """Portão anti-recaída: a luz volta com a ENTREGA, não com a vontade."""
        assert ei_mod.EXTERNAL_PLAYER_LED_ENABLED is False

    def test_tick_nao_acende_numero_em_externo_nenhum(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """A mesa da queixa (Pro + 8BitDo) atravessa dez ticks sem UMA escrita."""
        espiao = _LoggerEspiao()
        monkeypatch.setattr(ei_mod, "logger", espiao)
        sync = _sync(monkeypatch, _mesa(), ds_slots={"ds1": 1})

        for i in range(10):
            sync.tick(now=float(i * 10))

        assert escritas_de_led == []
        assert [ev for ev, _ in espiao.eventos if ev == "external_led_written"] == []

    def test_calar_e_nao_escrever_e_nao_apagar(
        self, monkeypatch: pytest.MonkeyPatch, sysfs_de_led: Path
    ) -> None:
        """A ESCOLHA de desenho, medida: o plástico fica byte a byte intocado."""
        antes = _retrato(sysfs_de_led)
        assert antes[f"{INST_PRO}:green:player-2/brightness"] == "1", (
            "a montagem do sysfs falso tem de começar com a barra ACESA, "
            "senão o teste não distingue 'não escrever' de 'apagar'"
        )

        sync = _sync(monkeypatch, _mesa())
        for i in range(3):
            sync.tick(now=float(i * 10))

        assert _retrato(sysfs_de_led) == antes

    def test_a_atribuicao_de_slot_continua_rodando(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """R-14: numerar é IDENTIDADE; o interruptor governa só a APARÊNCIA."""
        sync = _sync(monkeypatch, _mesa())
        sync.tick(now=0.0)

        assert escritas_de_led == []
        fila = sync._registry.snapshot()
        assert fila.get(MAC_PRO.replace(":", "")) == 1
        assert fila.get(MAC_8BITDO.replace(":", "")) == 2

    def test_o_enable_imu_nao_foi_calado_junto(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """GYRO-02 não é "a luz" — e continua saindo no mesmo tick."""
        imu: list[str] = []
        monkeypatch.setattr(
            leds_mod, "enable_imu", lambda dev, **kw: (imu.append(dev), True)[1]
        )
        monkeypatch.setattr(ei_mod, "NINTENDO_REAL_OUI", "aabbcc")
        sync = _sync(
            monkeypatch,
            [dict(_entry(MAC_PRO, "/dev/hidraw7", "/dev/input/event261"), bus="usb")],
        )

        sync.tick(now=0.0)

        assert escritas_de_led == []
        assert imu == ["/dev/hidraw7"], "calar a luz não pode calar a IMU"


class TestACapacidadeNaoFoiEnterrada:
    """Calar é desligar o CHAMADOR. O que acende a luz continua inteiro."""

    def test_as_funcoes_que_acendem_continuam_exportadas(self) -> None:
        """As três seguem no módulo E no `__all__` — API pública, não resto."""
        for nome in ("write_player_number", "write_lightbar_slot", "apply_player_number"):
            assert callable(getattr(leds_mod, nome, None)), f"{nome} sumiu do módulo"
            assert nome in leds_mod.__all__, f"{nome} saiu do __all__"

    def test_write_player_number_continua_acendendo_o_padrao_do_r25(
        self, tmp_path: Path
    ) -> None:
        """Chamada direta: o slot 7 ainda é "azul + 2 verdes", não "4 verdes"."""
        raiz = tmp_path / "leds"
        raiz.mkdir()
        _barra_nintendo(raiz, INST_PRO, acesos=())

        assert leds_mod.write_player_number(INST_PRO, 7, str(raiz)) is True

        assert _retrato(raiz) == {
            f"{INST_PRO}:green:player-1/brightness": "1",
            f"{INST_PRO}:green:player-2/brightness": "1",
            f"{INST_PRO}:green:player-3/brightness": "0",
            f"{INST_PRO}:green:player-4/brightness": "0",
            f"{INST_PRO}:blue:player-5/brightness": "1",
        }


    def test_uma_linha_devolve_a_luz_no_mesmo_tick(
        self, monkeypatch: pytest.MonkeyPatch, sysfs_de_led: Path
    ) -> None:
        """O caminho de volta, medido de ponta a ponta."""
        monkeypatch.setattr(ei_mod, "EXTERNAL_PLAYER_LED_ENABLED", True)
        sync = _sync(monkeypatch, _mesa())

        sync.tick(now=0.0)

        # Sem DualSense na mesa, o Pro é o primeiro presente -> posição 1.
        assert _retrato(sysfs_de_led) == {
            f"{INST_PRO}:green:player-1/brightness": "1",
            f"{INST_PRO}:green:player-2/brightness": "0",
            f"{INST_PRO}:green:player-3/brightness": "0",
            f"{INST_PRO}:green:player-4/brightness": "0",
            f"{INST_PRO}:blue:player-5/brightness": "0",
        }
