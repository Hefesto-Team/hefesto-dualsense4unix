"""O cabo liga e é reconhecido na hora: o relógio virou evento, e um controle não segura os outros.

O ensaio roda o produto de verdade (`reconnect_loop`, `connect`, `PhysicalReportReader`, `Chegada`,
`VigiaDoCabo`, o `inotify` do dono do evento) com relógio real e prazos curtos. Os dublês só fazem
o papel do kernel e do BlueZ, e têm a demora medida em 06/11/2026.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core import o_dono_do_evento as ode
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core import relogio_da_conexao as rel
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import bt_mic as mic
from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ouvido
from hefesto_dualsense4unix.daemon.subsystems.chegada import Chegada, PontasDaChegada
from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt_audio
from hefesto_dualsense4unix.integrations import o_cabo_em_espera as oce
from hefesto_dualsense4unix.interface import conexoes
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.profiles.manager import ProfileManager

MACS = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
PRAZO_DO_EVENTO_S = 1.0
PASSO_S = 0.005
PASSADAS_DO_LACO = 8
ESPERA_DA_VOLTA_S = 0.8
PRAZO_S = 6.0
TETO_S = 0.1
PRESO_S = 0.3
RECUO_LONGO_S = 3.0

_DERRUBAR_REAL = oce.derrubar_o_radio


def _esperar(pronto: Callable[[], bool], prazo_s: float = PRAZO_S) -> bool:
    fim = time.monotonic() + prazo_s
    while not pronto():
        if time.monotonic() >= fim:
            return False
        time.sleep(PASSO_S)
    return True


async def _esperar_no_laco(pronto: Callable[[], bool], prazo_s: float = PRAZO_S) -> bool:
    fim = time.monotonic() + prazo_s
    while not pronto():
        if time.monotonic() >= fim:
            return False
        await asyncio.sleep(PASSO_S)
    return True


def _aberturas_prontas(ctl: PyDualSenseController) -> bool:
    return all(a.pronta.is_set() for a in list(ctl._abrindo.values()))


@pytest.fixture(autouse=True)
def _sem_o_inventario_do_input_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evdev_reader, "discover_gamepads", lambda **_k: [])


@pytest.fixture()
def teto_curto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_mod, "TETO_DA_ABERTURA_NA_VOLTA_SEC", TETO_S)


class Controle:
    """O backend da volta, em dublê: conta os `connect`."""

    def __init__(self, ligado: bool) -> None:
        self.ligado = ligado
        self.connects: list[float] = []
        self.primary_uniq = None

    def connect(self) -> None:
        self.connects.append(time.monotonic())

    def is_connected(self) -> bool:
        return self.ligado

    def get_transport(self) -> str:
        return "usb"


def _daemon(controle: Any) -> tuple[SimpleNamespace, ThreadPoolExecutor]:
    fios = ThreadPoolExecutor(2)
    parar = asyncio.Event()

    async def _bloqueante(funcao: Any, *args: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(fios, funcao, *args)

    daemon = SimpleNamespace(
        controller=controle,
        bus=EventBus(),
        store=None,
        _stop_event=parar,
        _is_stopping=parar.is_set,
        _run_blocking=_bloqueante,
        _arm_input_grace=lambda: None,
        is_native_mode=lambda: False,
        _tasks=[],
    )
    return daemon, fios


@pytest.fixture
def raizes(tmp_path: Path) -> Iterator[Path]:
    nos = tmp_path / "dev"
    entradas = nos / "input"
    entradas.mkdir(parents=True)
    while ode.armado():
        ode.desarmar()
    assert ode.armar(entradas=str(entradas), nos=str(nos)), "o inotify não armou"
    try:
        yield nos
    finally:
        while ode.armado():
            ode.desarmar()


async def _nasce_e_mede(nos: Path, *, online: bool, nome: str) -> float:
    controle = Controle(online)
    daemon, fios = _daemon(controle)
    watch = InputDirWatch(root=str(nos / "input"))
    tarefa = asyncio.create_task(conn.reconnect_loop(daemon, input_watch=watch))
    assert await _esperar_no_laco(lambda: len(controle.connects) >= 1), "a volta não começou"
    antes = len(controle.connects)
    comeco = time.monotonic()
    (nos / "input" / nome).write_text("")
    await _esperar_no_laco(lambda: len(controle.connects) != antes, 8.0)
    gasto = time.monotonic() - comeco
    daemon._stop_event.set()
    tarefa.cancel()
    await asyncio.gather(tarefa, return_exceptions=True)
    fios.shutdown(wait=False)
    return gasto


class TestAVoltaAcordaPeloEvento:
    @pytest.mark.parametrize("online", [False, True], ids=["sem-controle", "com-controle"])
    def test_o_no_que_nasce_acorda_a_volta_sem_esperar_o_passo(
        self, raizes: Path, online: bool
    ) -> None:
        gasto = asyncio.run(_nasce_e_mede(raizes, online=online, nome="event7"))
        assert gasto < PRAZO_DO_EVENTO_S, (
            f"o nó nasceu e a volta levou {gasto:.2f} s: dormiu o passo, sem ouvir o inotify"
        )

    def test_o_netlink_toca_o_mesmo_sino(self) -> None:
        async def _ensaio() -> bool:
            daemon = SimpleNamespace()
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            ouvido._avisar_a_volta(
                daemon, b"bind@/x\0ACTION=bind\0SUBSYSTEM=hid\0DRIVER=playstation\0"
            )
            return await daemon._sino_da_volta.esperar(None, PRAZO_DO_EVENTO_S)

        assert asyncio.run(_ensaio())

    def test_o_netlink_nao_toca_com_o_que_nao_e_controle_nem_barramento(self) -> None:
        async def _ensaio() -> bool:
            daemon = SimpleNamespace()
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            ouvido._avisar_a_volta(daemon, b"add@/x\0ACTION=add\0SUBSYSTEM=net\0")
            return await daemon._sino_da_volta.esperar(None, 0.05)

        assert not asyncio.run(_ensaio())

    def test_o_usb_entrou_chega_ao_relogio_pela_porta(self) -> None:
        rel.RELOGIO.limpar()
        linhas: list[dict[str, Any]] = []
        relogio = rel.RelogioDaConexao(dizer=lambda _nome, **campos: linhas.append(campos))
        ouvido.RELOGIO, velho = relogio, ouvido.RELOGIO
        try:
            ouvido._avisar_a_volta(
                SimpleNamespace(),
                b"add@/d/3-4.1.3\0ACTION=add\0SUBSYSTEM=usb\0DEVTYPE=usb_device\0"
                b"PRODUCT=54c/ce6/100\0DEVPATH=/devices/usb3/3-4/3-4.1/3-4.1.3\0",
            )
        finally:
            ouvido.RELOGIO = velho
        assert "3-4.1.3" in relogio._usb

    def test_o_inotify_acorda_mesmo_quando_outro_fio_drenou_antes(self, raizes: Path) -> None:
        async def _ensaio() -> bool:
            controle = Controle(False)
            daemon, fios = _daemon(controle)
            desfazer = conn._armar_o_sino(daemon)
            try:
                (raizes / "input" / "event9").write_text("")
                dono = ode.dono_armado()
                assert dono is not None
                await asyncio.to_thread(dono.drenar)
                return await daemon._sino_da_volta.esperar(None, PRAZO_DO_EVENTO_S)
            finally:
                desfazer()
                fios.shutdown(wait=False)

        assert asyncio.run(_ensaio())

    def test_a_volta_solta_o_inotify_antes_de_o_dono_fechar(self, raizes: Path) -> None:
        async def _ensaio() -> None:
            daemon, fios = _daemon(Controle(False))
            dono = ode.dono_armado()
            assert dono is not None
            desfazer = conn._armar_o_sino(daemon)
            assert dono._ouvintes
            desfazer()
            assert not dono._ouvintes
            assert daemon._sino_da_volta is None
            assert not asyncio.get_running_loop().remove_reader(dono.descritor)
            fios.shutdown(wait=False)

        asyncio.run(_ensaio())

    def test_o_passo_de_reserva_continua_sem_evento(self) -> None:
        async def _ensaio() -> bool:
            daemon, fios = _daemon(Controle(True))
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            comeco = time.monotonic()
            tocou = await conn._wait_or_stop(daemon, 0.05)
            fios.shutdown(wait=False)
            assert 0.04 <= time.monotonic() - comeco < 0.5
            return tocou

        assert asyncio.run(_ensaio()) is False


class Vpad:
    player = 1

    def set_motion_streaming(self, _ligado: bool) -> None:
        return None


class TestOLeitorNaoDormeORecuo:
    @pytest.fixture(autouse=True)
    def _recuo_longo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prr, "_BACKOFF_START_S", RECUO_LONGO_S)
        monkeypatch.setattr(prr, "_BACKOFF_MAX_S", RECUO_LONGO_S)

    def _leitor(self) -> tuple[prr.PhysicalReportReader, dict[str, Any], threading.Event]:
        estado: dict[str, Any] = {"no": None}
        aberto = threading.Event()
        leitor_r, escritor = os.pipe()
        self._fds = (leitor_r, escritor)

        def abrir(_caminho: str) -> int:
            aberto.set()
            return os.dup(leitor_r)

        leitor = prr.PhysicalReportReader(lambda: estado["no"], Vpad(), opener=abrir)
        return leitor, estado, aberto

    def _no_recuo_longo(self, leitor: prr.PhysicalReportReader) -> None:
        leitor.start()
        assert _esperar(lambda: leitor._em_recuo), "o leitor não entrou no recuo"

    def teardown_method(self) -> None:
        for fd in getattr(self, "_fds", ()):
            os.close(fd)

    @pytest.mark.parametrize("corte", ["request_reopen", "acordar_quem_recua"])
    def test_o_pedido_corta_o_recuo(self, corte: str) -> None:
        leitor, estado, aberto = self._leitor()
        self._no_recuo_longo(leitor)
        estado["no"] = "/dev/hidraw9"
        comeco = time.monotonic()
        if corte == "request_reopen":
            leitor.request_reopen("primary_changed")
        else:
            prr.acordar_quem_recua()
        assert aberto.wait(1.0), "o recuo dormiu inteiro, surdo ao pedido"
        leitor.stop()
        assert time.monotonic() - comeco < 1.5

    def test_o_stop_corta_o_recuo(self) -> None:
        leitor, _estado, _aberto = self._leitor()
        self._no_recuo_longo(leitor)
        comeco = time.monotonic()
        leitor.stop()
        assert time.monotonic() - comeco < 1.0

    def test_o_aviso_que_cruza_a_entrada_do_recuo_nao_se_perde(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        leitor, _estado, _aberto = self._leitor()
        visto: list[bool] = []

        def contar() -> int:
            visto.append(leitor._em_recuo)
            return 1

        monkeypatch.setattr(prr, "_chamadas_do_acordar", contar)
        assert leitor._esperar_o_recuo(5.0, 0) == prr._BACKOFF_START_S
        assert visto[0], "o aviso entre a conferência e o recuo dormiria o recuo inteiro"

    def test_acordar_nao_mexe_em_quem_esta_lendo(self) -> None:
        leitor, estado, aberto = self._leitor()
        estado["no"] = "/dev/hidraw9"
        leitor.start()
        assert aberto.wait(1.0)
        aberto.clear()
        prr.acordar_quem_recua()
        assert not aberto.wait(0.3), "o aviso do recuo reabriu um leitor que lia"
        leitor.stop()


class _Handle:
    def __init__(self, path: bytes) -> None:
        self._pinned_path = path
        self.closed = False
        self.conType = SimpleNamespace(name="USB")
        self.state = SimpleNamespace()
        self.connected = True

    def close(self) -> None:
        self.closed = True


def _backend(
    chaves: list[tuple[str, bytes, bool]],
    demora: dict[bytes, float],
    *,
    com_volta: bool = True,
) -> tuple[PyDualSenseController, dict[bytes, _Handle]]:
    ctl = PyDualSenseController()
    ctl._enumerate_device_keys = lambda: chaves  # type: ignore[method-assign]
    if com_volta:
        ctl.ouvir_as_aberturas(lambda: None)
    abertos: dict[bytes, _Handle] = {}

    def abrir(path: bytes, *, is_edge: bool) -> _Handle:
        del is_edge
        time.sleep(demora.get(path, 0.02))
        abertos[path] = _Handle(path)
        return abertos[path]

    ctl._open_one = abrir  # type: ignore[method-assign]
    return ctl, abertos


def _quatro() -> list[tuple[str, bytes, bool]]:
    return [(mac, f"/ensaio/hidraw{n}".encode(), False) for n, mac in enumerate(MACS)]


@pytest.mark.usefixtures("teto_curto")
class TestUmControleNaoSeguraOsOutros:
    @pytest.mark.parametrize("preso", range(4), ids=[f"preso-P{n + 1}" for n in range(4)])
    def test_um_init_preso_nao_atrasa_os_outros_tres(self, preso: int) -> None:
        chaves = _quatro()
        ctl, _abertos = _backend(chaves, {chaves[preso][1]: PRESO_S})
        ctl.connect()
        vivos = set(ctl._handles)
        assert vivos == {mac for mac, _p, _e in chaves} - {chaves[preso][0]}, (
            "um init preso segurou a volta"
        )
        assert ctl.falta_abrir_alguem()
        ctl.disconnect()

    def test_o_preso_entra_na_volta_seguinte_e_a_abertura_toca_o_sino(self) -> None:
        chaves = _quatro()
        ctl, _abertos = _backend(chaves, {chaves[2][1]: PRESO_S})
        toques: list[float] = []
        ctl.ouvir_as_aberturas(lambda: toques.append(time.monotonic()))
        ctl.connect()
        assert MACS[2] not in ctl._handles
        _esperar(lambda: len(toques) >= len(chaves))
        assert len(toques) == len(chaves), "a abertura que terminou não acordou a volta"
        ctl.connect()
        assert set(ctl._handles) == set(MACS)
        assert not ctl.falta_abrir_alguem()
        ctl.disconnect()

    def test_cada_abertura_corre_no_proprio_fio(self) -> None:
        chaves = _quatro()
        ctl, _abertos = _backend(chaves, dict.fromkeys((p for _m, p, _e in chaves), TETO_S * 0.8))
        em_voo: list[int] = [0]
        pico: list[int] = [0]
        trava = threading.Lock()
        aberta = ctl._open_one

        def contar(path: bytes, *, is_edge: bool) -> _Handle:
            with trava:
                em_voo[0] += 1
                pico[0] = max(pico[0], em_voo[0])
            try:
                return aberta(path, is_edge=is_edge)
            finally:
                with trava:
                    em_voo[0] -= 1

        ctl._open_one = contar  # type: ignore[method-assign]
        ctl.connect()
        assert pico[0] == len(chaves), "abriu em série"
        assert set(ctl._handles) == set(MACS)
        ctl.disconnect()

    def test_o_controle_que_saiu_enquanto_abria_nao_fica_aberto(self) -> None:
        chaves = _quatro()[:2]
        ctl, abertos = _backend(chaves, {chaves[1][1]: TETO_S * 2})
        ctl.connect()
        ctl._enumerate_device_keys = lambda: chaves[:1]  # type: ignore[method-assign]
        assert _esperar(lambda: _aberturas_prontas(ctl) and chaves[1][1] in abertos)
        ctl.connect()
        assert set(ctl._handles) == {MACS[0]}
        assert abertos[chaves[1][1]].closed
        ctl.disconnect()

    def test_o_disconnect_fecha_o_que_estava_em_voo(self) -> None:
        chaves = _quatro()[:1]
        ctl, abertos = _backend(chaves, {chaves[0][1]: PRESO_S})
        ctl.connect()
        assert not ctl._handles
        ctl.disconnect()
        ctl._abrindo.clear()
        assert _esperar(lambda: chaves[0][1] in abertos and abertos[chaves[0][1]].closed), (
            "a abertura órfã vazou o handle"
        )

    def test_sem_volta_o_connect_espera_quem_abre(self) -> None:
        chaves = _quatro()[:2]
        ctl, _abertos = _backend(chaves, {chaves[1][1]: PRESO_S}, com_volta=False)
        ctl.connect()
        assert set(ctl._handles) == set(MACS[:2]), (
            "a CLI e o boot não têm volta seguinte para colher quem passou do teto"
        )
        assert not ctl.falta_abrir_alguem()
        ctl.disconnect()

    def test_a_abertura_que_termina_no_meio_da_espera_nao_derruba_o_connect(self) -> None:
        class Vira(threading.Event):
            def __init__(self) -> None:
                super().__init__()
                self.perguntas = 0

            def is_set(self) -> bool:
                self.perguntas += 1
                return self.perguntas > 1

        ctl = PyDualSenseController()
        ctl.ouvir_as_aberturas(lambda: None)
        pronta = backend_mod._Abertura("a", b"/a")
        pronta.pronta.set()
        virando = backend_mod._Abertura("b", b"/b", pronta=Vira())
        ctl._abrindo = {"a": pronta, "b": virando}
        ctl._esperar_as_aberturas()

    def test_quem_saiu_nao_apaga_a_falta_de_quem_ficou(self) -> None:
        chaves = _quatro()[:2]
        ctl, _abertos = _backend(chaves, dict.fromkeys((p for _m, p, _e in chaves), PRESO_S))
        terminaram: list[bytes] = []

        def abrir(path: bytes, *, is_edge: bool) -> _Handle:
            del is_edge
            time.sleep(PRESO_S)
            terminaram.append(path)
            if path == chaves[0][1]:
                raise OSError("sem permissão")
            return _Handle(path)

        ctl._open_one = abrir  # type: ignore[method-assign]
        ctl.connect()
        ctl._enumerate_device_keys = lambda: chaves[:1]  # type: ignore[method-assign]
        assert _esperar(lambda: len(terminaram) == 2 and _aberturas_prontas(ctl))
        ctl.connect()
        assert ctl.falta_abrir_alguem(), "o que saiu calou a tentativa de quem ficou"
        ctl.disconnect()

    def test_a_abertura_que_falha_fica_pendente_e_vai_ao_diario(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        chaves = _quatro()[:1]
        ctl, _abertos = _backend(chaves, {})

        def explode(_path: bytes, *, is_edge: bool) -> _Handle:
            del is_edge
            raise OSError("sem permissão")

        ctl._open_one = explode  # type: ignore[method-assign]
        ctl.connect()
        assert not ctl._handles
        assert ctl.falta_abrir_alguem()

    @pytest.mark.parametrize("online", [False, True], ids=["sem-controle", "com-outro-controle"])
    def test_a_volta_tenta_de_novo_sem_esperar_o_passo_cego(self, online: bool) -> None:
        class ControleQueFalha(Controle):
            def falta_abrir_alguem(self) -> bool:
                return len(self.connects) < 3

        async def _ensaio() -> list[float]:
            controle = ControleQueFalha(online)
            daemon, fios = _daemon(controle)
            tarefa = asyncio.create_task(
                conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
            )
            await _esperar_no_laco(lambda: len(controle.connects) >= 3, 3.0)
            daemon._stop_event.set()
            tarefa.cancel()
            await asyncio.gather(tarefa, return_exceptions=True)
            fios.shutdown(wait=False)
            return controle.connects

        assert len(asyncio.run(_ensaio())) >= 3, "a tentativa dormiu o passo de 5 s"


class TestOKernelAindaCria:
    def _sysfs(self, tmp_path: Path, *, uniq: str, driver: str) -> Path:
        aparelho = tmp_path / "hid"
        aparelho.mkdir()
        (aparelho / "uevent").write_text(f"HID_ID=0003:0000054C:00000CE6\nHID_UNIQ={uniq}\n")
        alvo = tmp_path / driver
        alvo.mkdir()
        (aparelho / "driver").symlink_to(alvo)
        no = tmp_path / "hidraw3"
        no.mkdir()
        (no / "device").symlink_to(aparelho)
        return tmp_path

    def test_sem_endereco_com_o_driver_a_meio_o_no_ainda_nao_e_controle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = self._sysfs(tmp_path, uniq="", driver="playstation")
        monkeypatch.setattr(backend_mod.usb_pai, "RAIZ_HIDRAW", str(raiz))
        assert backend_mod._o_kernel_ainda_cria(b"/dev/hidraw3")

    def test_com_endereco_o_no_esta_pronto(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = self._sysfs(tmp_path, uniq=MACS[0], driver="playstation")
        monkeypatch.setattr(backend_mod.usb_pai, "RAIZ_HIDRAW", str(raiz))
        assert not backend_mod._o_kernel_ainda_cria(b"/dev/hidraw3")

    def test_sem_o_driver_do_controle_segue_o_fallback_de_sempre(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = self._sysfs(tmp_path, uniq="", driver="hid-generic")
        monkeypatch.setattr(backend_mod.usb_pai, "RAIZ_HIDRAW", str(raiz))
        assert not backend_mod._o_kernel_ainda_cria(b"/dev/hidraw3")

    def test_sysfs_ausente_nao_inventa_probe(self) -> None:
        assert not backend_mod._o_kernel_ainda_cria(b"/ensaio/hidraw0")


class TestOCaboQueEspera:
    def _vigia_com(self, cabo: oce.CaboEmEspera) -> oce.VigiaDoCabo:
        vigia = oce.VigiaDoCabo()
        vigia.observar_os_cabos([cabo], 0.0)
        return vigia

    def _daemon_da_mesa(
        self, vigia: oce.VigiaDoCabo, mesa: list[dict[str, Any]], iniciadas: list[str]
    ) -> SimpleNamespace:
        controle = SimpleNamespace(
            describe_controllers=lambda: mesa,
            iniciar_troca_de_transporte=lambda par, motivo: iniciadas.append(par) or True,
        )
        return SimpleNamespace(
            controller=controle,
            _vigia_do_cabo_em_espera=vigia,
            is_native_mode=lambda: False,
        )

    def test_desistir_nao_prende_o_cabo_ate_o_replug(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mac = MACS[0].replace(":", "")
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0001", uniq=MACS[0])
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: [cabo])
        monkeypatch.setattr(oce, "impedimentos_da_troca", lambda: [])
        vigia = oce.VigiaDoCabo()
        mesa: list[dict[str, Any]] = []
        iniciadas: list[str] = []
        daemon = self._daemon_da_mesa(vigia, mesa, iniciadas)

        assert conn._quem_passa_para_o_cabo(daemon, 1.0) == []
        assert vigia.esperando()[cabo.instancia] == oce.MOTIVO_SEM_GEMEO

        mesa.append({"connected": True, "uniq": mac, "transport": "bt", "battery_state": None})
        pedidos = conn._quem_passa_para_o_cabo(daemon, 2.0)
        assert [par for _cabo, par, _fonte in pedidos] == [mac], (
            "o gêmeo entrou na mesa e o cabo seguiu resolvido até sair da tomada"
        )
        assert cabo.instancia not in vigia.esperando()

    def test_o_teto_vence_e_o_mesmo_cabo_tenta_de_novo(self) -> None:
        mac = MACS[1].replace(":", "")
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0002", uniq=MACS[1])
        vigia = self._vigia_com(cabo)
        vigia.derrubou(mac, 10.0)
        no_radio = {mac: None}
        cedo = vigia.decidir(cabo, no_radio=no_radio, agora=20.0)
        assert cedo.par is None and cedo.motivo == oce.MOTIVO_JA_DERRUBADO
        tarde = vigia.decidir(cabo, no_radio=no_radio, agora=10.0 + oce.TETO_POR_CONTROLE_S)
        assert tarde.par == mac

    def test_quem_espera_acorda_a_volta_no_prazo_e_uma_vez(self) -> None:
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0003", uniq=None)
        vigia = self._vigia_com(cabo)
        vigia.adiar(cabo.instancia, oce.MOTIVO_SEM_GEMEO, 1.0)
        vigia.ultima_olhada = 2.0
        assert not vigia.quer_olhar_de_novo(3.0)
        prazo = 1.0 + oce.REOLHAR_QUEM_ESPERA_S
        assert vigia.quer_olhar_de_novo(prazo)
        vigia.ultima_olhada = prazo
        assert not vigia.quer_olhar_de_novo(prazo + 1.0)

    def test_o_cabo_que_sai_leva_o_motivo_junto(self) -> None:
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0004", uniq=None)
        vigia = self._vigia_com(cabo)
        vigia.adiar(cabo.instancia, oce.MOTIVO_SEM_GEMEO, 1.0)
        vigia.observar_os_cabos([], 2.0)
        assert vigia.esperando() == {}

    def test_o_cabo_recusado_acorda_a_volta_pelo_proprio_cabo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hid = tmp_path / "0003:054C:0CE6.0005"
        hid.mkdir()
        (hid / "driver").write_text("playstation")
        monkeypatch.setattr(oce, "RAIZ_DO_BARRAMENTO_HID", str(tmp_path))
        daemon = SimpleNamespace(
            controller=SimpleNamespace(iniciar_troca_de_transporte=lambda *_a, **_k: True)
        )
        assert conn._um_cabo_ficou_sem_driver(daemon) is False
        (hid / "driver").unlink()
        assert conn._um_cabo_ficou_sem_driver(daemon) is True


class TestOCaboQueEsperaApareceNaTela:
    def test_o_motivo_chega_a_tela_em_palavra_de_tela(self) -> None:
        vigia = oce.VigiaDoCabo()
        vigia.adiar("0003:054C:0CE6.0001", oce.MOTIVO_SEM_GEMEO, 1.0)
        vigia.adiar("0003:054C:0CE6.0002", oce.MOTIVO_MODO_NATIVO, 1.0)
        assert vigia.para_a_tela() == [
            {"instancia": "0003:054C:0CE6.0001", "motivo": "sem_gemeo"},
            {"instancia": "0003:054C:0CE6.0002", "motivo": "modo_nativo"},
        ]

    @pytest.mark.parametrize(
        "motivo",
        [
            "sem_gemeo", "modo_nativo", "sem_a_regra", "ja_derrubado", "sem_endereco",
            "o_radio_nao_soltou", "",
        ],
    )
    def test_o_cartao_tem_poucas_palavras_e_nenhuma_banida(self, motivo: str) -> None:
        dica = dicas.dica_do_cabo_em_espera("0003:054C:0CE6.0001", motivo)
        assert len(dica.titulo.split()) <= dicas.PALAVRAS_NO_TITULO
        assert dica.porque
        assert "mesa" not in f"{dica.titulo} {dica.porque}".lower()

    def test_todo_motivo_que_a_vigia_diz_tem_frase_propria(self) -> None:
        for motivo in oce._PORQUE_DA_TELA.values():
            assert motivo in dicas.PORQUE_DO_CABO, f"{motivo} cairia na frase genérica"

    def test_o_cabo_sem_endereco_nao_afirma_um_bluetooth_que_nao_ha(self) -> None:
        vigia = oce.VigiaDoCabo()
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0007", uniq="")
        vigia.observar_os_cabos([cabo], 0.0)
        decisao = vigia.decidir(cabo, no_radio={}, agora=oce.ESPERA_PARA_SER_ORFAO_S)
        assert decisao.desistir and decisao.motivo == oce.MOTIVO_SEM_ENDERECO
        vigia.adiar(cabo.instancia, decisao.motivo, 1.0)
        assert vigia.para_a_tela()[0]["motivo"] == "sem_endereco"
        assert "Bluetooth" not in dicas.PORQUE_DO_CABO["sem_endereco"]
        assert "Bluetooth" not in dicas.PORQUE_DO_CABO_SEM_MOTIVO

    def test_quem_o_bluez_recusou_ate_o_fim_aparece_e_sem_martelo(self) -> None:
        vigia = oce.VigiaDoCabo()
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0008", uniq=MACS[0])
        vigia.observar_os_cabos([cabo], 0.0)
        for _vez in range(oce.RECUSAS_ANTES_DE_DESISTIR):
            tenta = vigia.recusado(cabo.instancia, 0.0)
        assert not tenta
        assert vigia.observar_os_cabos([cabo], 600.0) == [], "o laço virou martelo"
        assert vigia.para_a_tela() == [
            {"instancia": cabo.instancia, "motivo": "o_radio_nao_soltou"}
        ]
        vigia.observar_os_cabos([], 601.0)
        assert vigia.para_a_tela() == []

    def test_a_aba_monta_um_cartao_por_cabo(self) -> None:
        cena = {"cabos_esperando": [{"instancia": "0003:054C:0CE6.0001", "motivo": "sem_gemeo"}]}
        cartoes = a08._a_dica_do_cabo(cena)
        assert [c.chave for c in cartoes] == ["cabo-em-espera:0003:054C:0CE6.0001"]
        assert a08._a_dica_do_cabo({}) == []

    def test_o_motivo_vai_no_hover_do_cartao(self) -> None:
        painel = dicas.montar([dicas.dica_do_cabo_em_espera("0003:054C:0CE6.0001", "sem_gemeo")])
        html = conexoes.html_das_dicas(painel)
        assert dicas.TITULO_DO_CABO_EM_ESPERA in html
        assert dicas.PORQUE_DO_CABO["sem_gemeo"] in html


class BlueZLento:
    def __init__(self, demora: float) -> None:
        self.demora = demora
        self.pedidos: list[str] = []
        self.trava_comum_do_radio = threading.Lock()

    def aparelhos(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(endereco=m, conectado=True, caminho=f"/bluez/{m}") for m in MACS
        ]

    def desconectar(self, caminho: str, quem: str) -> SimpleNamespace:
        del quem
        with self.trava_comum_do_radio:
            self.pedidos.append(caminho)
            time.sleep(self.demora)
        return SimpleNamespace(feita=True, mensagem="", erro="")


class TestATrocaNaoSeguraAVolta:
    def _mesa(self, quantos: int) -> tuple[Any, list[oce.CaboEmEspera], list[str]]:
        macs = [m.replace(":", "") for m in MACS[:quantos]]
        mesa = [
            {"connected": True, "uniq": mac, "transport": "bt", "battery_state": None}
            for mac in macs
        ]
        cabos = [
            oce.CaboEmEspera(f"0003:054C:0CE6.000{n}", uniq=MACS[n]) for n in range(quantos)
        ]
        iniciadas: list[str] = []
        controle = SimpleNamespace(
            describe_controllers=lambda: mesa,
            iniciar_troca_de_transporte=lambda par, motivo: iniciadas.append(par) or True,
            cancelar_troca_de_transporte=lambda par, motivo: None,
        )
        daemon = SimpleNamespace(controller=controle, is_native_mode=lambda: False)
        return daemon, cabos, iniciadas

    @pytest.mark.parametrize("quantos", [1, 2, 3, 4])
    def test_todos_trocam_na_mesma_volta(
        self, quantos: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon, cabos, iniciadas = self._mesa(quantos)
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: cabos)
        monkeypatch.setattr(oce, "impedimentos_da_troca", lambda: [])
        bluez = BlueZLento(0.05)
        monkeypatch.setattr(
            oce, "derrubar_o_radio", lambda uniq, leitor=None: _derruba(bluez, uniq)
        )

        async def _ensaio() -> list[int]:
            conn._passar_os_cabos_sem_segurar_a_volta(daemon)
            return await asyncio.gather(*daemon._trocas_em_fundo)

        assert asyncio.run(_ensaio()) == [quantos] and len(iniciadas) == quantos
        assert len(bluez.pedidos) == quantos

    def test_a_volta_segue_enquanto_o_bluez_responde(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon, cabos, iniciadas = self._mesa(1)
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: cabos)
        monkeypatch.setattr(oce, "impedimentos_da_troca", lambda: [])
        bluez = BlueZLento(0.4)
        monkeypatch.setattr(
            oce, "derrubar_o_radio", lambda uniq, leitor=None: _derruba(bluez, uniq)
        )

        async def _ensaio() -> tuple[float, int]:
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            comeco = time.monotonic()
            conn._passar_os_cabos_sem_segurar_a_volta(daemon)
            gasto = time.monotonic() - comeco
            assert await daemon._sino_da_volta.esperar(None, 2.0), "a troca não acordou a volta"
            await conn._soltar_a_troca_em_fundo(daemon)
            return gasto, len(iniciadas)

        gasto, marcadas = asyncio.run(_ensaio())
        assert marcadas == 1, "a troca tem de estar marcada antes de a volta olhar a mesa"
        assert len(bluez.pedidos) == 1, "o `Disconnect` não chegou ao BlueZ"
        assert gasto < 0.1, f"a volta ficou parada {gasto:.2f} s no Disconnect"


def _derruba(bluez: BlueZLento, uniq: str) -> tuple[bool, str]:
    return _DERRUBAR_REAL(uniq, leitor=bluez)


class _Pontas:
    def __init__(self, *, com_rota: bool = True, na_mesa: tuple[str, ...] = tuple(MACS)) -> None:
        self.com_rota = com_rota
        self.toques: list[str] = []
        self.cliques: list[str] = []
        self.pinturas: list[str] = []
        self.pontas = PontasDaChegada(
            pode=lambda: True,
            conectados=lambda: frozenset(na_mesa),
            jogo_escreve=lambda _u, _c: False,
            nota=lambda _u: 150,
            cor=lambda _u: (10, 20, 30),
            pintar=lambda uniq, _rgb: self.pinturas.append(uniq),
            devolver_a_luz=lambda: None,
            tocar=self._tocar,
            clicar=self.cliques.append,
            soltar_o_clique=lambda _u: None,
            dormir=lambda _s: None,
        )

    def _tocar(self, uniq: str, *_resto: Any) -> bool:
        if self.com_rota:
            self.toques.append(uniq)
        return self.com_rota


class TestAChegadaRespondeNaHora:
    def test_o_toque_sai_na_borda_e_a_luz_e_o_clique_esperam_o_sossego(self) -> None:
        pontas = _Pontas()
        chegada = Chegada(pontas.pontas)
        chegada.chegou(MACS[0])
        assert chegada.responder() == 1
        assert pontas.toques == [MACS[0]]
        assert pontas.pinturas == [] and pontas.cliques == []
        feito = chegada.tocar()
        assert pontas.toques == [MACS[0]], "o Toque tocou duas vezes na mesma Chegada"
        assert feito[MACS[0]]["toque"] and pontas.cliques == [MACS[0]] and pontas.pinturas

    def test_sem_rota_o_toque_espera_a_haptica_subir(self) -> None:
        pontas = _Pontas(com_rota=False)
        chegada = Chegada(pontas.pontas)
        chegada.chegou(MACS[1])
        assert chegada.responder() == 0
        assert chegada.falta_o_toque
        pontas.com_rota = True
        assert chegada.responder() == 1
        assert not chegada.falta_o_toque

    @pytest.mark.parametrize("quantos", [1, 2, 3, 4])
    def test_cada_controle_tem_a_propria_resposta(self, quantos: int) -> None:
        pontas = _Pontas()
        chegada = Chegada(pontas.pontas)
        for mac in MACS[:quantos]:
            chegada.chegou(mac)
        assert chegada.responder() == quantos
        assert pontas.toques == MACS[:quantos]

    def test_quem_sai_e_volta_antes_do_sossego_sente_o_toque_de_novo(self) -> None:
        pontas = _Pontas()
        chegada = Chegada(pontas.pontas)
        chegada.chegou(MACS[0])
        assert chegada.responder() == 1
        chegada.chegou(MACS[0])
        assert chegada.falta_o_toque, "uma conexão nova ficou sem o Toque"
        assert chegada.responder() == 1

    def test_a_volta_chama_a_primeira_resposta(self) -> None:
        pontas = _Pontas()
        chegada = Chegada(pontas.pontas)
        chegada.chegou(MACS[0])

        async def _ensaio() -> None:
            daemon, fios = _daemon(Controle(True))
            daemon._chegada = chegada
            await conn.responder_a_chegada(daemon)
            fios.shutdown(wait=False)

        asyncio.run(_ensaio())
        assert pontas.toques == [MACS[0]]


class _Gerenciador:
    def dormir(self, _s: float) -> bool:
        return False


class TestOSomAcordaComAMesa:
    def test_a_mesa_que_muda_acorda_som_microfone_e_leitores(self) -> None:
        chamadas: list[str] = []
        daemon = SimpleNamespace(
            _alto_falante_subsystem=SimpleNamespace(
                _acordar_a_volta=lambda quem: chamadas.append(f"som:{quem}")
            ),
            _bt_mic_subsystem=SimpleNamespace(
                acordar_a_volta=lambda quem: chamadas.append(f"mic:{quem}")
            ),
        )
        conn.avisar_que_a_mesa_mudou(daemon)  # type: ignore[arg-type]
        assert chamadas == ["som:mesa", "mic:mesa"]

    def test_a_troca_de_transporte_conta_como_mudanca_da_mesa(self) -> None:
        assert conn._avisar_quem_conectou(
            {"k": MACS[0]},
            {"k": MACS[0]},
            {"k": "bt"},
            {"k": "usb"},
        )

    def test_a_mesa_parada_nao_acorda_ninguem(self) -> None:
        assert not conn._avisar_quem_conectou(
            {"k": MACS[0]},
            {"k": MACS[0]},
            {"k": "usb"},
            {"k": "usb"},
        )

    def test_a_volta_do_som_acorda_sem_esperar_o_relogio(self) -> None:
        sub = af.AltoFalanteSubsystem.__new__(af.AltoFalanteSubsystem)
        sub._acordar = threading.Event()
        sub._parar = threading.Event()
        sub._acordar_a_volta("mesa")
        comeco = time.monotonic()
        assert sub._esperar_a_mesa_do_som(_Gerenciador()) is False
        assert time.monotonic() - comeco < PRAZO_DO_EVENTO_S

    def test_a_placa_que_nasce_acorda_a_volta_do_som(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sub = af.AltoFalanteSubsystem.__new__(af.AltoFalanteSubsystem)
        sub._acordar = threading.Event()
        sub._parar = threading.Event()
        sub._placas_vistas = frozenset()
        monkeypatch.setattr(
            sub, "_as_placas_de_agora", lambda: frozenset({"alsa_output.usb-Sony_DualSense"})
        )
        monkeypatch.setattr(sub, "_a_mesa_do_som_mudou", lambda: False)
        sub._acordar.set()
        comeco = time.monotonic()
        assert sub._esperar_a_mesa_do_som(_Gerenciador()) is False
        assert time.monotonic() - comeco < PRAZO_DO_EVENTO_S

    def test_a_volta_do_microfone_acorda_sem_esperar_o_relogio(self) -> None:
        sub = mic.BtMicSubsystem()
        sub.acordar_a_volta("mesa")
        comeco = time.monotonic()
        sub._dormir(_Gerenciador())
        assert time.monotonic() - comeco < PRAZO_DO_EVENTO_S


class TestORelogioDaConexao:
    def _relogio(self) -> tuple[rel.RelogioDaConexao, list[dict[str, Any]], dict[str, float]]:
        linhas: list[dict[str, Any]] = []
        agora = {"t": 100.0}
        relogio = rel.RelogioDaConexao(
            relogio=lambda: agora["t"], dizer=lambda _nome, **campos: linhas.append(campos)
        )
        return relogio, linhas, agora

    def test_uma_linha_com_cada_etapa_do_cabo(self) -> None:
        relogio, linhas, agora = self._relogio()
        relogio.usb_entrou("3-4.1.3")
        agora["t"] = 101.0
        relogio.marcar(MACS[0], rel.ABERTO, transporte="usb", no="3-4.1.3")
        agora["t"] = 101.2
        relogio.marcar(MACS[0], rel.CONECTADO, transporte="usb")
        for etapa in (rel.MOVIMENTO, rel.HAPTICA, rel.SOM, rel.MICROFONE):
            relogio.marcar(MACS[0], etapa)
        assert not linhas
        agora["t"] = 102.5
        relogio.marcar(MACS[0], rel.CHEGADA)
        assert len(linhas) == 1
        linha = linhas[0]
        assert linha["usb_entrou"] == 0 and linha["aberto"] == 1000
        assert linha["conectado"] == 1200 and linha["chegada"] == 2500
        assert linha["total_ms"] == 2500 and linha["faltam"] == []
        assert linha["uniq"] == "aa:bb:cc:00:00:01"

    def test_quatro_controles_nao_se_misturam(self) -> None:
        relogio, linhas, agora = self._relogio()
        for n, mac in enumerate(MACS):
            relogio.usb_entrou(f"3-{n}")
            agora["t"] += 0.5
            relogio.marcar(mac, rel.ABERTO, transporte="bt" if n % 2 else "usb", no=f"3-{n}")
        for mac in reversed(MACS):
            relogio.marcar(mac, rel.CONECTADO)
            for etapa in (rel.MOVIMENTO, rel.HAPTICA, rel.SOM, rel.MICROFONE, rel.CHEGADA):
                relogio.marcar(mac, etapa)
        assert len(linhas) == 4
        assert {linha["transporte"] for linha in linhas} == {"usb", "bt"}
        assert all(linha["faltam"] == [] for linha in linhas)

    def test_a_troca_nao_espera_a_chegada(self) -> None:
        relogio, linhas, _agora = self._relogio()
        relogio.marcar(MACS[0], rel.O_CABO_CHEGOU)
        relogio.marcar(MACS[0], rel.CONECTADO, transporte="usb")
        for etapa in (rel.MOVIMENTO, rel.HAPTICA, rel.SOM, rel.MICROFONE):
            relogio.marcar(MACS[0], etapa)
        assert len(linhas) == 1 and linhas[0]["faltam"] == []

    def test_no_teto_a_linha_sai_com_o_que_faltou(self) -> None:
        relogio, linhas, agora = self._relogio()
        relogio.marcar(MACS[0], rel.CONECTADO, transporte="bt")
        agora["t"] += rel.TETO_DAS_PECAS_S
        assert relogio.varrer() == 1
        assert linhas[0]["faltam"] == [rel.MOVIMENTO, rel.MICROFONE, rel.CHEGADA]

    def test_peca_sem_conexao_aberta_nao_abre_relogio(self) -> None:
        relogio, linhas, _agora = self._relogio()
        relogio.marcar(MACS[0], rel.MOVIMENTO)
        assert relogio.varrer() == 0 and not linhas

    def test_a_tentativa_que_falhou_antes_de_abrir_aparece_na_linha(self) -> None:
        relogio, linhas, _agora = self._relogio()
        relogio.marcar(MACS[0], rel.TENTATIVA_FALHOU)
        relogio.marcar(MACS[0], rel.TENTATIVA_FALHOU)
        assert relogio.varrer() == 0 and not linhas
        relogio.marcar(MACS[0], rel.ABERTO, transporte="bt")
        relogio.marcar(MACS[0], rel.CONECTADO)
        for etapa in (rel.MOVIMENTO, rel.MICROFONE, rel.CHEGADA):
            relogio.marcar(MACS[0], etapa)
        assert linhas[0]["falhas"] == 2

    def test_a_tentativa_que_falhou_aparece_na_linha(self) -> None:
        relogio, linhas, _agora = self._relogio()
        relogio.marcar(MACS[0], rel.ABERTO, transporte="bt")
        relogio.marcar(MACS[0], rel.TENTATIVA_FALHOU)
        relogio.marcar(MACS[0], rel.CONECTADO)
        for etapa in (rel.MOVIMENTO, rel.MICROFONE, rel.CHEGADA):
            relogio.marcar(MACS[0], etapa)
        assert linhas[0]["falhas"] == 1


class _HandleDeTransporte(_Handle):
    def __init__(self, path: bytes, transporte: str) -> None:
        super().__init__(path)
        self.conType = SimpleNamespace(name=transporte.upper())


MESAS = {
    "4-cabos": ("usb", "usb", "usb", "usb"),
    "3-cabos-1-radio": ("usb", "usb", "usb", "bt"),
    "2-e-2": ("usb", "bt", "usb", "bt"),
    "1-cabo-3-radios": ("bt", "bt", "usb", "bt"),
    "4-radios": ("bt", "bt", "bt", "bt"),
}


@pytest.mark.usefixtures("teto_curto")
class TestOsQuatroJuntos:
    """A volta e o backend de verdade: cada mesa, com um `init` preso de cada vez."""

    async def _plugar(
        self, transportes: tuple[str, ...], preso: int, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[list[tuple[str, float]], PyDualSenseController, float, bool]:
        chaves = _quatro()
        ctl = PyDualSenseController()
        ctl._enumerate_device_keys = lambda: chaves  # type: ignore[method-assign]
        por_no = dict(zip((p for _m, p, _e in chaves), transportes, strict=True))
        no_preso = chaves[preso][1]
        solto = threading.Event()
        preso_abriu: list[bool] = []

        def abrir(path: bytes, *, is_edge: bool) -> _HandleDeTransporte:
            del is_edge
            if path == no_preso:
                solto.wait(PRAZO_S)
                preso_abriu.append(True)
            return _HandleDeTransporte(path, por_no[path])

        ctl._open_one = abrir  # type: ignore[method-assign]
        daemon, fios = _daemon(ctl)
        daemon._hidraw_broker_executor = fios

        async def _nada(*_a: Any, **_k: Any) -> int:
            return 0

        for nome in ("vigiar_escritor_cru", "carimbar_o_nascimento", "restore_last_profile",
                     "reaplicar_som_em_todos_os_alvos", "reapply_speaker_after_connect",
                     "reapply_mic_after_connect"):
            monkeypatch.setattr(conn, nome, _nada)
        monkeypatch.setattr(conn, "anunciar_a_chegada", lambda *_a, **_k: 0)
        fila = daemon.bus.subscribe(conn.EventTopic.CONTROLLER_CONNECTED)
        comeco = time.monotonic()
        tarefa = asyncio.create_task(
            conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
        )
        chegaram: list[tuple[str, float]] = []
        solto_em = 0.0
        preso_abriu_antes = False

        async def colher(quantos: int) -> None:
            while len(chegaram) < quantos and time.monotonic() - comeco < PRAZO_S:
                try:
                    evento = await asyncio.wait_for(fila.get(), PASSO_S * 10)
                except asyncio.TimeoutError:
                    continue
                chegaram.append((str(evento["uniq"]), time.monotonic() - comeco))

        await colher(3)
        preso_abriu_antes = bool(preso_abriu)
        solto_em = time.monotonic() - comeco
        solto.set()
        await colher(4)
        daemon._stop_event.set()
        tarefa.cancel()
        await asyncio.gather(tarefa, return_exceptions=True)
        fios.shutdown(wait=False)
        return chegaram, ctl, solto_em, preso_abriu_antes

    @pytest.mark.parametrize("nome", list(MESAS))
    @pytest.mark.parametrize("preso", [0, 3], ids=["preso-P1", "preso-P4"])
    def test_um_preso_nao_segura_os_outros_e_entra_depois(
        self, nome: str, preso: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rel.RELOGIO.limpar()
        chegaram, ctl, solto_em, preso_abriu_antes = asyncio.run(
            self._plugar(MESAS[nome], preso, monkeypatch)
        )
        ctl.disconnect()
        conexoes_abertas = dict(rel.RELOGIO._abertas)
        rel.RELOGIO.limpar()
        for mac, transporte in zip(MACS, MESAS[nome], strict=True):
            conexao = conexoes_abertas[mac.replace(":", "")]
            assert {rel.ABERTO, rel.CONECTADO} <= set(conexao.marcas)
            assert conexao.transporte == transporte
        assert len({uniq for uniq, _t in chegaram}) == 4, f"faltou controle: {chegaram}"
        assert not preso_abriu_antes, "o preso abriu antes de ser solto"
        assert chegaram[3][1] >= solto_em, f"o preso não pode ter chegado antes: {chegaram}"
        assert chegaram[3][1] - solto_em < ESPERA_DA_VOLTA_S, (
            f"a abertura que terminou não acordou a volta: {chegaram}"
        )


class ControleDaTroca(Controle):
    """O backend com um controle no rádio, para a vigia decidir de verdade dentro da volta."""

    def __init__(self) -> None:
        super().__init__(True)
        self.iniciadas: list[str] = []

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"connected": True, "uniq": MACS[0].replace(":", ""), "transport": "bt"}]

    def iniciar_troca_de_transporte(self, par: str, *, motivo: str) -> bool:
        del motivo
        self.iniciadas.append(par)
        return True


class TestAVoltaDeVerdade:
    """O ponto em que cada peça entra na volta, com a volta inteira rodando."""

    def test_a_volta_nao_para_no_disconnect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0001", uniq=MACS[0])
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: [cabo])
        monkeypatch.setattr(oce, "impedimentos_da_troca", lambda: [])
        solto = threading.Event()

        def derrubar(_uniq: str, leitor: Any = None) -> tuple[bool, str]:
            del leitor
            solto.wait(2.0)
            return True, ""

        monkeypatch.setattr(oce, "derrubar_o_radio", derrubar)

        async def _ensaio() -> tuple[float, ControleDaTroca]:
            controle = ControleDaTroca()
            daemon, fios = _daemon(controle)
            depois: list[float] = []
            original = conn._avisar_quem_conectou

            def _anotar(*args: Any) -> bool:
                depois.append(time.monotonic())
                return original(*args)

            monkeypatch.setattr(conn, "_avisar_quem_conectou", _anotar)
            tarefa = asyncio.create_task(
                conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
            )
            await _esperar_no_laco(lambda: bool(depois), 1.5)
            gasto = (depois[0] if depois else time.monotonic()) - controle.connects[0]
            solto.set()
            daemon._stop_event.set()
            tarefa.cancel()
            await asyncio.gather(tarefa, return_exceptions=True)
            fios.shutdown(wait=False)
            return gasto, controle

        gasto, controle = asyncio.run(_ensaio())
        assert controle.iniciadas == [MACS[0].replace(":", "")]
        assert gasto < 1.0, f"a volta ficou {gasto:.2f} s presa no Disconnect"

    def test_o_hid_que_perde_o_driver_acorda_a_espera_da_volta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cabos: list[oce.CaboEmEspera] = []
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: list(cabos))

        async def _ensaio() -> tuple[bool, float]:
            daemon, fios = _daemon(ControleDaTroca())
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            watch = InputDirWatch(root="/nao-existe")
            watch.poll()
            espera = asyncio.create_task(conn._wait_online_or_hotplug(daemon, watch))
            for _ in range(PASSADAS_DO_LACO):
                await asyncio.sleep(0)
            comeco = time.monotonic()
            cabos.append(oce.CaboEmEspera("0003:054C:0CE6.0001", uniq=MACS[0]))
            daemon._sino_da_volta.tocar("inotify")
            voltou = await asyncio.wait_for(espera, 3.0)
            fios.shutdown(wait=False)
            return voltou, time.monotonic() - comeco

        voltou, gasto = asyncio.run(_ensaio())
        assert voltou and gasto < 0.8, "a recusa do kernel dormiu o passo da volta"

    def test_a_espera_da_volta_varre_o_relogio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        varridas: list[int] = []
        monkeypatch.setattr(rel.RELOGIO, "varrer", lambda: varridas.append(1) or 0)
        monkeypatch.setattr(conn, "TETO_DA_VOLTA_PELO_EVENTO_SEC", 0.1)
        monkeypatch.setattr(conn, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 0.1)

        async def _ensaio() -> None:
            daemon, fios = _daemon(Controle(True))
            await conn._wait_online_or_hotplug(daemon, InputDirWatch(root="/nao-existe"))
            fios.shutdown(wait=False)

        asyncio.run(_ensaio())
        assert varridas, "a conexão que não fecha nunca sairia no diário"

    def test_o_toque_da_chegada_sai_antes_do_sossego(self) -> None:
        pontas = _Pontas(na_mesa=(MACS[0].replace(":", ""),))

        class ControleDaMesa(Controle):
            def __init__(self) -> None:
                super().__init__(False)
                self.handles: dict[str, str] = {}

            def connect(self) -> None:
                super().connect()
                if len(self.connects) > 1:
                    self.ligado = True
                    self.handles = {"k": MACS[0].replace(":", "")}

            def alvos_conectados(self) -> dict[str, str]:
                return self.handles

        async def _ensaio() -> float | None:
            controle = ControleDaMesa()
            daemon, fios = _daemon(controle)
            daemon._chegada = Chegada(pontas.pontas)
            tarefa = asyncio.create_task(
                conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
            )
            assert await _esperar_no_laco(lambda: len(controle.connects) >= 1)
            conn.acordar_a_volta(daemon, "abertura")
            comeco = time.monotonic()
            await _esperar_no_laco(lambda: bool(pontas.toques), 2.5)
            gasto = time.monotonic() - comeco if pontas.toques else None
            daemon._stop_event.set()
            tarefa.cancel()
            await asyncio.gather(tarefa, return_exceptions=True)
            fios.shutdown(wait=False)
            return gasto

        gasto = asyncio.run(_ensaio())
        assert gasto is not None and gasto < 1.0, f"o Toque esperou o sossego: {gasto}"
        assert pontas.pinturas == [], "a luz não espera menos que a rajada"

    def test_quem_chega_toca_o_sino_para_o_toque_nao_esperar_o_passo(self) -> None:
        async def _ensaio() -> bool:
            daemon, fios = _daemon(Controle(True))
            daemon._chegada = Chegada(_Pontas().pontas)
            daemon._sino_da_volta = conn.SinoDaVolta(asyncio.get_running_loop())
            assert conn.anunciar_a_chegada(daemon, {}, {"k": MACS[0]}) == 1
            tocou = await daemon._sino_da_volta.esperar(None, 0.05)
            fios.shutdown(wait=False)
            return tocou

        assert asyncio.run(_ensaio())

    def test_a_mesa_que_muda_na_volta_acorda_quem_esperava(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        avisos: list[int] = []
        monkeypatch.setattr(conn, "avisar_que_a_mesa_mudou", lambda _d: avisos.append(1))

        class ControleQueEntra(Controle):
            def alvos_conectados(self) -> dict[str, str]:
                return {"k": MACS[0]} if len(self.connects) > 1 else {}

        async def _ensaio() -> None:
            controle = ControleQueEntra(True)
            daemon, fios = _daemon(controle)
            tarefa = asyncio.create_task(
                conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
            )
            assert await _esperar_no_laco(lambda: len(controle.connects) >= 1)
            conn.acordar_a_volta(daemon, "abertura")
            await _esperar_no_laco(lambda: bool(avisos), 1.5)
            daemon._stop_event.set()
            tarefa.cancel()
            await asyncio.gather(tarefa, return_exceptions=True)
            fios.shutdown(wait=False)

        rel.RELOGIO.limpar()
        asyncio.run(_ensaio())
        rel.RELOGIO.limpar()
        assert avisos, "o controle entrou e som, microfone e movimento seguiram dormindo"


class TestCadaPecaCarimbaORelogio:
    """A linha só é verdade se cada peça carimba onde fica de pé: «faltam» não pode mentir."""

    def _aberto(self, monkeypatch: pytest.MonkeyPatch, modulo: Any) -> rel.RelogioDaConexao:
        relogio = rel.RelogioDaConexao(dizer=lambda *_a, **_k: None)
        monkeypatch.setattr(modulo, "RELOGIO", relogio)
        relogio.marcar(MACS[0], rel.ABERTO, transporte="usb")
        return relogio

    def _marcas(self, relogio: rel.RelogioDaConexao) -> set[str]:
        return set(relogio._abertas[MACS[0].replace(":", "")].marcas)

    def test_a_rota_do_som(self, monkeypatch: pytest.MonkeyPatch) -> None:
        relogio = self._aberto(monkeypatch, afb)
        no = afb.SinkVirtualPipeWire(uniq=MACS[0], runner=lambda _argv: "42\n")
        assert no._subir_o_fio(["pactl", "load-module", "module-loopback", "source=a", "sink=b"])
        assert rel.SOM in self._marcas(relogio)

    def test_o_leitor_de_movimento(self, monkeypatch: pytest.MonkeyPatch) -> None:
        relogio = self._aberto(monkeypatch, prr)
        monkeypatch.setattr(prr, "uniq_do_hidraw", lambda _caminho: MACS[0])
        leitor_r, escritor = os.pipe()
        aberto = threading.Event()

        def abrir(_caminho: str) -> int:
            aberto.set()
            return os.dup(leitor_r)

        leitor = prr.PhysicalReportReader(lambda: "/dev/hidraw9", Vpad(), opener=abrir)
        try:
            leitor.start()
            assert aberto.wait(1.0)
            _esperar(lambda: rel.MOVIMENTO in self._marcas(relogio), 1.0)
        finally:
            leitor.stop()
            os.close(leitor_r)
            os.close(escritor)
        assert rel.MOVIMENTO in self._marcas(relogio)

    def test_a_haptica_do_cabo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        relogio = self._aberto(monkeypatch, af)
        monkeypatch.setattr(afb, "sinks_com_motores", lambda _pergunta: [])
        sub = af.AltoFalanteSubsystem(daemon=None)
        sub._cabo = SimpleNamespace(aparelhos=lambda: {"placa-1": object()})

        def casar(*_args: Any) -> None:
            sub._aparelho_de = {MACS[0]: "placa-1", MACS[1]: "placa-2"}

        sub._casar_o_cabo = casar  # type: ignore[method-assign]
        sub._casar_as_pontes([])
        assert rel.HAPTICA in self._marcas(relogio)

    def test_o_microfone_do_cabo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

        relogio = self._aberto(monkeypatch, mic)
        monkeypatch.setattr(bt_audio, "pactl_mudo", lambda: False)
        monkeypatch.setattr(ele, "fontes_de_captura_agora", lambda: ["alsa_input.dualsense"])
        monkeypatch.setattr(ele, "casamento_usb_agora", lambda _u: None)
        monkeypatch.setattr(canal, "de_pe", dict)
        monkeypatch.setattr(canal, "abrir", lambda *_a, **_k: SimpleNamespace(nome="canal"))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.fontes_de_captura.escolher_fonte",
            lambda *_a: "alsa_input.dualsense",
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.fontes_de_captura.sem_os_nos_nossos",
            lambda fontes: fontes,
        )
        sub = mic.BtMicSubsystem(registro=mic.RegistroDePedidosDeCanal())
        sub.uniqs_na_mesa = lambda: frozenset({MACS[0]})  # type: ignore[method-assign]
        sub._abrir_os_canais_do_cabo([MACS[0]])
        assert rel.MICROFONE in self._marcas(relogio)

    def test_o_microfone_do_radio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        relogio = self._aberto(monkeypatch, mic)
        monkeypatch.setattr(bt_audio, "nos_dualsense_bluetooth", lambda: [])
        sub = mic.BtMicSubsystem(registro=mic.RegistroDePedidosDeCanal())
        sub._gerenciador = SimpleNamespace(
            pontes={MACS[0]: object()}, reconciliar=lambda _a: None, dormir=lambda _s: True
        )
        sub._registro.novidade.set()
        sub._loop()
        assert rel.MICROFONE in self._marcas(relogio)


class TestOCaboQueEsperaChegaATela:
    def test_o_modo_nativo_e_a_regra_que_falta_tambem_aparecem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cabo = oce.CaboEmEspera("0003:054C:0CE6.0001", uniq=MACS[0])
        monkeypatch.setattr(oce, "cabos_em_espera", lambda: [cabo])
        controle = ControleDaTroca()
        daemon = SimpleNamespace(controller=controle, is_native_mode=lambda: True)
        assert conn._quem_passa_para_o_cabo(daemon, 1.0) == []
        vigia = conn.vigia_do_cabo_de(daemon)
        assert vigia.esperando()[cabo.instancia] == oce.MOTIVO_MODO_NATIVO
        daemon.is_native_mode = lambda: False
        monkeypatch.setattr(oce, "impedimentos_da_troca", lambda: ["sem a regra"])
        assert conn._quem_passa_para_o_cabo(daemon, 2.0) == []
        assert vigia.esperando()[cabo.instancia] == oce.MOTIVO_SEM_A_REGRA

    def test_o_estado_do_daemon_leva_o_cabo_que_espera(self, tmp_path: Path) -> None:
        vigia = oce.VigiaDoCabo()
        vigia.adiar("0003:054C:0CE6.0001", oce.MOTIVO_SEM_GEMEO, 1.0)
        ctl = PyDualSenseController()
        servidor = IpcServer(
            controller=ctl,
            store=StateStore(),
            profile_manager=ProfileManager(controller=ctl, store=StateStore()),
            socket_path=tmp_path / "h.sock",
            daemon=None,
        )
        servidor.daemon = MagicMock(_vigia_do_cabo_em_espera=vigia, _last_state=None)
        chamada = getattr(servidor, "_handle_daemon_" + "state" + "_full")
        resposta = asyncio.run(chamada({}))
        assert resposta["cabos_esperando"] == [
            {"instancia": "0003:054C:0CE6.0001", "motivo": "sem_gemeo"}
        ]

    def test_a_cena_das_conexoes_leva_o_cabo_que_espera(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
        from hefesto_dualsense4unix.interface import pacotes
        from hefesto_dualsense4unix.interface.pacotes import em_fundo
        from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

        monkeypatch.setattr(em_fundo, "_FUNDO", {})
        for nome in ("_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA"):
            monkeypatch.setattr(a08, nome, {})
        monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
        monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: Mesa())
        monkeypatch.setattr(em_fundo, "ler_o_bluez", lambda: ((), ()))
        monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
        monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
        monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
        espera = [{"instancia": "0003:054C:0CE6.0001", "motivo": "sem_gemeo"}]
        cena = a08.cena_do_radio(
            pacotes.Contexto(
                state={"controllers": [], "cabos_esperando": espera}, mesa=[], conectados=[]
            )
        )
        assert cena["cabos_esperando"] == espera


class TestOEnumerarNaoAbreOQueOKernelAindaCria:
    def test_o_no_a_meio_da_probe_fica_de_fora_e_os_outros_seguem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hidapi

        lista = [
            SimpleNamespace(
                vendor_id=0x054C, product_id=0x0CE6, path=b"/dev/hidraw1", serial_number=""
            ),
            SimpleNamespace(
                vendor_id=0x054C, product_id=0x0CE6, path=b"/dev/hidraw2", serial_number=MACS[0]
            ),
        ]
        monkeypatch.setattr(hidapi, "enumerate", lambda vendor_id=0: lista)
        monkeypatch.setattr(backend_mod, "_is_virtual_hidraw", lambda _p: False)
        monkeypatch.setattr(
            backend_mod, "_o_kernel_ainda_cria", lambda path: path == b"/dev/hidraw1"
        )
        chaves = PyDualSenseController._enumerate_device_keys()
        assert [key for key, _p, _e in chaves] == [MACS[0]]
