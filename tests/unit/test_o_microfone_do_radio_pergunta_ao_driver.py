"""O microfone pelo rádio pergunta ao driver antes de subir — B1 da O-PRODUTO.

``O-PRODUTO-EM-QUALQUER-MAQUINA-01`` (28/09/2026), a L1 do estudo
``2026-09-27-o-basico-e-os-jogos/03-qualquer-maquina.md``: o microfone nasce
ligado, e sem o ``0003`` do ``hid-playstation`` o driver de fábrica lê o quadro
de áudio como gamepad — desliga o microfone sozinho e MEXE O CURSOR da pessoa
(medido aqui em 10/09/2026). O ``0003`` não está no Linux, e numa máquina nova
ele só carrega depois do primeiro reinício, se carregar.

A cura: o ``0003`` ganha a marca ``mic_frames_ignored`` (só de leitura), e a
ponte do rádio só sobe para o nó que o driver ``playstation`` lê se o módulo
tiver a marca — ou for o ``0003`` de antes dela, reconhecido pelo
``srcversion``. Sem isso, ``BtMicSubsystem.motivo`` diz
``driver_sem_a_guarda_do_audio``.

Nenhum teste daqui lê o ``/sys`` da máquina: o do rádio e o do módulo são de
mentira, num ``tmp_path``, e nenhum processo roda.

A MORDIDA, feita em 28/09/2026: trocar a primeira linha de ``alvos()``
(``nos = self._os_que_o_driver_deixa(nos)``) por nada faz
``test_sem_a_marca_a_ponte_do_radio_nao_sobe`` e
``test_a_env_nao_passa_por_cima_do_driver`` reprovarem — a ponte sobe sobre o
driver de fábrica. Devolvido, md5 conferido.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

UM = "aa:bb:cc:00:00:a1"
DOIS = "aa:bb:cc:00:00:b7"


@pytest.fixture(autouse=True)
def _ninguem_roda_processo(monkeypatch: pytest.MonkeyPatch) -> None:
    def _recusa(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"um teste desta régua tentou rodar processo: {args!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)
    monkeypatch.delenv(bt_mic.ENV_HABILITA, raising=False)


def _sys_do_radio(tmp_path: Path, driver_por_no: dict[str, str | None]) -> Path:
    """`/sys/class/hidraw` de mentira: `hidrawN/device/driver` -> `.../drivers/<d>`."""
    raiz = tmp_path / "class-hidraw"
    drivers = tmp_path / "bus-hid-drivers"
    for nome, driver in driver_por_no.items():
        device = raiz / nome / "device"
        device.mkdir(parents=True)
        if driver is not None:
            (drivers / driver).mkdir(parents=True, exist_ok=True)
            os.symlink(drivers / driver, device / "driver")
    return raiz


def _sys_do_modulo(
    tmp_path: Path, *, marca: str | None = None, srcversion: str | None = None,
    parametros: tuple[str, ...] = (),
) -> Path:
    """`/sys/module/hid_playstation` de mentira. Sem nada = o de fábrica."""
    raiz = tmp_path / "module-hid_playstation"
    raiz.mkdir()
    if marca is not None or parametros:
        (raiz / "parameters").mkdir()
        for nome in parametros:
            (raiz / "parameters" / nome).write_text("0\n", encoding="ascii")
        if marca is not None:
            (raiz / "parameters" / bt_mic.PARAMETRO_DA_MARCA).write_text(
                marca + "\n", encoding="ascii"
            )
    if srcversion is not None:
        (raiz / "srcversion").write_text(srcversion + "\n", encoding="ascii")
    return raiz


def _no(nome: str, uniq: str) -> bt.NoDualSenseBT:
    return bt.NoDualSenseBT(caminho=f"/dev/{nome}", uniq=uniq, produto=0x0CE6)


# ---------------------------------------------------------------------------
# 1. A pergunta ao módulo
# ---------------------------------------------------------------------------


class TestOModuloTemAGuarda:
    def test_com_a_marca_sim(self, tmp_path: Path) -> None:
        assert bt_mic.o_driver_guarda_o_audio(str(_sys_do_modulo(tmp_path, marca="Y")))

    def test_o_de_fabrica_nao(self, tmp_path: Path) -> None:
        """O in-tree não tem parâmetro nenhum, e o `srcversion` é o dele."""
        raiz = _sys_do_modulo(tmp_path, srcversion="A74F93FE20FF36683AF7614")
        assert not bt_mic.o_driver_guarda_o_audio(str(raiz))

    def test_o_patchado_de_antes_de_10_09_nao(self, tmp_path: Path) -> None:
        """O `feature_retries` é do `0001`: ele não diz nada do áudio."""
        raiz = _sys_do_modulo(
            tmp_path,
            parametros=("feature_retries", "ds4_short_pairing_info", "ds4_synthetic_mac"),
            srcversion="0123456789ABCDEF0123456",
        )
        assert not bt_mic.o_driver_guarda_o_audio(str(raiz))

    def test_o_0003_de_antes_da_marca_sim_pelo_srcversion(self, tmp_path: Path) -> None:
        (antigo,) = bt_mic.SRCVERSION_DO_0003_SEM_A_MARCA
        raiz = _sys_do_modulo(
            tmp_path,
            parametros=("feature_retries", "ds4_short_pairing_info", "ds4_synthetic_mac"),
            srcversion=antigo,
        )
        assert bt_mic.o_driver_guarda_o_audio(str(raiz))

    def test_a_marca_em_n_nao(self, tmp_path: Path) -> None:
        assert not bt_mic.o_driver_guarda_o_audio(str(_sys_do_modulo(tmp_path, marca="N")))

    def test_modulo_ausente_nao(self, tmp_path: Path) -> None:
        assert not bt_mic.o_driver_guarda_o_audio(str(tmp_path / "nao-existe"))


class TestQuemLeONo:
    def test_o_playstation_le(self, tmp_path: Path) -> None:
        raiz = _sys_do_radio(tmp_path, {"hidraw5": "playstation"})
        assert bt_mic.o_driver_le_este_no("/dev/hidraw5", str(raiz))

    def test_o_hid_generic_nao_le_como_gamepad(self, tmp_path: Path) -> None:
        raiz = _sys_do_radio(tmp_path, {"hidraw5": "hid-generic"})
        assert not bt_mic.o_driver_le_este_no("/dev/hidraw5", str(raiz))

    def test_no_sem_driver_ou_sumido(self, tmp_path: Path) -> None:
        raiz = _sys_do_radio(tmp_path, {"hidraw5": None})
        assert not bt_mic.o_driver_le_este_no("/dev/hidraw5", str(raiz))
        assert not bt_mic.o_driver_le_este_no("/dev/hidraw9", str(raiz))
        assert not bt_mic.o_driver_le_este_no("", str(raiz))


# ---------------------------------------------------------------------------
# 2. O subsystem de verdade, com o sysfs de mentira
# ---------------------------------------------------------------------------


class _GerenciadorDeMentira:
    """Publica o que o real publica: `pontes` por caminho, com o `no` dentro."""

    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, nos: list[Any]) -> None:
        vivos = {no.caminho for no in nos}
        for caminho in [c for c in self.pontes if c not in vivos]:
            del self.pontes[caminho]
        for no in nos:
            self.pontes.setdefault(no.caminho, SimpleNamespace(no=no, mic_no_ar=False))

    def dormir(self, _segundos: float) -> bool:
        return True

    def parar(self) -> None:
        self.pontes.clear()


@pytest.fixture()
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dois DualSense no rádio, os dois lidos pelo `playstation`."""
    raiz = _sys_do_radio(tmp_path, {"hidraw5": "playstation", "hidraw7": "playstation"})
    monkeypatch.setattr(bt, "_SYSFS_HIDRAW", str(raiz))
    nos = [_no("hidraw5", UM), _no("hidraw7", DOIS)]
    monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: list(nos))
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._gerenciador = _GerenciadorDeMentira()
    # O cabo, os órfãos, o rótulo e a fonte padrão falam com o servidor de som:
    # ficam fora desta régua, que mede só quem ganha ponte no rádio.
    for nome in (
        "_reconciliar_o_cabo", "_varrer_os_orfaos", "_renomear_os_canais_velhos",
    ):
        monkeypatch.setattr(sub, nome, lambda *_a, **_k: [])
    monkeypatch.setattr(sub, "_devolver_a_fonte_padrao", lambda *_a, **_k: None)
    return SimpleNamespace(sub=sub, nos=nos, tmp_path=tmp_path)


def _uma_volta(m: Any) -> dict[str, Any]:
    m.sub._registro.novidade.set()
    m.sub._loop()
    return dict(m.sub._gerenciador.pontes)


def test_sem_a_marca_a_ponte_do_radio_nao_sobe(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O driver de fábrica: nenhuma ponte, e o motivo dito."""
    monkeypatch.setattr(
        bt_mic, "RAIZ_DO_MODULO_DO_DRIVER",
        str(_sys_do_modulo(mesa.tmp_path, srcversion="A74F93FE20FF36683AF7614")),
    )
    assert _uma_volta(mesa) == {}, "a ponte subiu sobre um driver que lê o áudio como gamepad"
    assert mesa.sub.motivo == bt_mic.MOTIVO_SEM_A_GUARDA


def test_com_a_marca_as_duas_sobem(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bt_mic, "RAIZ_DO_MODULO_DO_DRIVER", str(_sys_do_modulo(mesa.tmp_path, marca="Y"))
    )
    assert sorted(_uma_volta(mesa)) == ["/dev/hidraw5", "/dev/hidraw7"]
    assert mesa.sub.motivo == ""


def test_o_0003_de_antes_da_marca_segue_de_pe(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A máquina dela até o próximo boot: o `0003` de 10/09, sem a marca."""
    (antigo,) = bt_mic.SRCVERSION_DO_0003_SEM_A_MARCA
    monkeypatch.setattr(
        bt_mic, "RAIZ_DO_MODULO_DO_DRIVER",
        str(_sys_do_modulo(mesa.tmp_path, parametros=("feature_retries",), srcversion=antigo)),
    )
    assert sorted(_uma_volta(mesa)) == ["/dev/hidraw5", "/dev/hidraw7"]
    assert mesa.sub.motivo == ""


def test_a_env_nao_passa_por_cima_do_driver(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A env pede a mesa inteira, e o driver continua lendo o áudio como gamepad."""
    monkeypatch.setenv(bt_mic.ENV_HABILITA, "1")
    monkeypatch.setattr(
        bt_mic, "RAIZ_DO_MODULO_DO_DRIVER", str(_sys_do_modulo(mesa.tmp_path))
    )
    assert mesa.sub.alvos(list(mesa.nos)) == []
    assert mesa.sub.motivo == bt_mic.MOTIVO_SEM_A_GUARDA


def test_quando_a_marca_chega_o_motivo_sai(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O módulo novo carregado (o reinício): a mesma subsystem volta a subir."""
    sem = _sys_do_modulo(mesa.tmp_path)
    monkeypatch.setattr(bt_mic, "RAIZ_DO_MODULO_DO_DRIVER", str(sem))
    assert _uma_volta(mesa) == {}
    (sem / "parameters").mkdir()
    (sem / "parameters" / bt_mic.PARAMETRO_DA_MARCA).write_text("Y\n", encoding="ascii")
    assert sorted(_uma_volta(mesa)) == ["/dev/hidraw5", "/dev/hidraw7"]
    assert mesa.sub.motivo == ""


def test_no_que_o_playstation_nao_le_segue_como_antes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem driver que transforme áudio em gamepad, não há o que guardar."""
    raiz = _sys_do_radio(tmp_path, {"hidraw5": "hid-generic"})
    monkeypatch.setattr(bt, "_SYSFS_HIDRAW", str(raiz))
    monkeypatch.setattr(bt_mic, "RAIZ_DO_MODULO_DO_DRIVER", str(tmp_path / "nao-existe"))
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    no = _no("hidraw5", UM)
    assert sub.alvos([no]) == [no]
    assert sub.motivo == ""
