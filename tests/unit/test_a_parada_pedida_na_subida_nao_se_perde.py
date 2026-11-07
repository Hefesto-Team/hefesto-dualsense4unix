"""A parada pedida em qualquer ponto da subida sai limpa e não anda até o passo seguinte."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import connection, lifecycle, subsystems
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles import o_padrao_do_computador
from hefesto_dualsense4unix.testing import FakeController

_O_IMPORT_FRIO_S = 0.3
_PRAZO_S = 10.0
_A_ORDEM_DA_SUBIDA = (
    "importar",
    "migrar",
    "subir",
    "conectar",
    "perfil",
    "som",
    "subir_depois",
    "religar",
)


def _estados() -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(5)
    ]


def _o_daemon(controle: FakeController | None = None) -> Daemon:
    return Daemon(
        controller=controle or FakeController(transport="usb", states=_estados()),
        config=DaemonConfig(
            poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )


class _ControleQueAvisa(FakeController):
    """Conecta como o de verdade, num fio do pool, e diz que passou por ali."""

    conectou: Any = None

    def connect(self) -> None:
        super().connect()
        if self.conectou is not None:
            self.conectou()


class _ASubida:
    """Anota cada passo da subida e pede a parada dentro do passo escolhido."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, parar_em: str) -> None:
        self.parar_em = parar_em
        self.passos: list[str] = []
        self.descidas = 0
        self.daemon: Daemon | None = None
        self.laco: asyncio.AbstractEventLoop | None = None
        self.controle = _ControleQueAvisa(transport="usb", states=_estados())
        self.controle.conectou = lambda: self._passou_no_fio("conectar")
        descer = connection.shutdown

        async def _shutdown(daemon: Any) -> None:
            self.descidas += 1
            await descer(daemon)

        async def _subir(_daemon: Any, *, depois_do_controle: bool = False) -> None:
            self._passou("subir_depois" if depois_do_controle else "subir")

        async def _perfil(_daemon: Any) -> None:
            self._passou("perfil")

        async def _som(_daemon: Any) -> None:
            self._passou("som")

        def _religar(_daemon: Any) -> Any:
            self._passou("religar")
            return asyncio.sleep(0)

        monkeypatch.setattr(
            lifecycle, "_importar_o_que_a_subida_usa", lambda: self._passou_no_fio("importar")
        )
        monkeypatch.setattr(
            o_padrao_do_computador, "migrar_uma_vez", lambda: self._passou_no_fio("migrar")
        )
        monkeypatch.setattr(subsystems, "subir", _subir)
        monkeypatch.setattr(connection, "restore_last_profile", _perfil)
        monkeypatch.setattr(connection, "reaplicar_som_em_todos_os_alvos", _som)
        monkeypatch.setattr(connection, "reconnect_loop", _religar)
        monkeypatch.setattr(connection, "shutdown", _shutdown)

    def _passou(self, passo: str) -> None:
        self.passos.append(passo)
        if passo == self.parar_em:
            assert self.daemon is not None
            self.daemon.stop()

    def _passou_no_fio(self, passo: str) -> None:
        """A parada do sinal chega pelo laço, com a subida presa numa espera fora dele."""
        self.passos.append(passo)
        if passo != self.parar_em:
            return
        assert self.daemon is not None and self.laco is not None
        pedida = threading.Event()

        def _pedir(daemon: Daemon = self.daemon) -> None:
            daemon.stop()
            pedida.set()

        self.laco.call_soon_threadsafe(_pedir)
        assert pedida.wait(_PRAZO_S)

    async def rodar(self) -> None:
        self.laco = asyncio.get_running_loop()
        self.daemon = _o_daemon(self.controle)
        await asyncio.wait_for(self.daemon.run(), _PRAZO_S)


@pytest.mark.asyncio
@pytest.mark.parametrize("parar_aos_s", [0.0, 0.1, 0.5])
async def test_a_parada_aos_0_0_1_e_0_5_s_sai_limpa(
    monkeypatch: pytest.MonkeyPatch, parar_aos_s: float
) -> None:
    """O import frio custa o que se mediu (0,3 s); a parada cai antes, durante e depois dele."""
    monkeypatch.setattr(
        lifecycle, "_importar_o_que_a_subida_usa", lambda: time.sleep(_O_IMPORT_FRIO_S)
    )
    controle = FakeController(transport="usb", states=_estados())
    daemon = _o_daemon(controle)

    subida = asyncio.create_task(daemon.run())
    if parar_aos_s:
        await asyncio.sleep(parar_aos_s)
    daemon.stop()
    await asyncio.wait_for(subida, _PRAZO_S)

    assert controle.is_connected() is False


def test_a_parada_vem_antes_de_a_subida_comecar() -> None:
    """O evento nasce com o serviço: quem para antes do primeiro passo da subida também é ouvido."""
    daemon = _o_daemon()

    daemon.stop()

    assert daemon._is_stopping() is True


@pytest.mark.asyncio
@pytest.mark.parametrize("parar_em", _A_ORDEM_DA_SUBIDA[:-1])
async def test_a_parada_nao_anda_ate_o_passo_seguinte(
    monkeypatch: pytest.MonkeyPatch, parar_em: str
) -> None:
    subida = _ASubida(monkeypatch, parar_em)

    await subida.rodar()

    assert subida.passos == list(
        _A_ORDEM_DA_SUBIDA[: _A_ORDEM_DA_SUBIDA.index(parar_em) + 1]
    )


@pytest.mark.asyncio
async def test_a_parada_no_import_nao_deixa_o_que_descer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subida = _ASubida(monkeypatch, "importar")

    await subida.rodar()

    assert subida.descidas == 0
    daemon = subida.daemon
    assert daemon is not None
    assert daemon._executor is None
    assert daemon._external_executor is None


@pytest.mark.asyncio
@pytest.mark.parametrize("parar_em", _A_ORDEM_DA_SUBIDA[1:-1])
async def test_a_parada_com_algo_de_pe_desce_tudo(
    monkeypatch: pytest.MonkeyPatch, parar_em: str
) -> None:
    subida = _ASubida(monkeypatch, parar_em)

    await subida.rodar()

    assert subida.descidas == 1
    assert subida.controle.is_connected() is False
    daemon = subida.daemon
    assert daemon is not None
    assert daemon._executor is None
    assert daemon._external_executor is None


@pytest.mark.asyncio
async def test_a_subida_que_nao_foi_parada_passa_por_todos_os_passos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem parada, a subida percorre todos os passos que a régua anota."""
    subida = _ASubida(monkeypatch, "religar")

    await subida.rodar()

    assert subida.passos == list(_A_ORDEM_DA_SUBIDA)
    assert subida.descidas == 1


@pytest.mark.asyncio
async def test_o_subsystem_nao_parte_com_a_parada_pedida() -> None:
    """Entre dois subsystems da lista: é o `_safe_start` que todo passo do `subir` atravessa."""
    daemon = _o_daemon()
    partidas: list[str] = []

    await daemon._safe_start("antes", lambda: partidas.append("antes"))
    daemon.stop()
    await daemon._safe_start("depois", lambda: partidas.append("depois"))

    assert partidas == ["antes"]
    assert daemon._failed_subsystems == {}


def test_o_sigterm_no_import_frio_sai_pela_parada(tmp_path: Any) -> None:
    """O processo de verdade, com o sinal de verdade: quem desliga o serviço sai com 0."""
    roteiro = textwrap.dedent(
        """
        import asyncio
        import time

        from hefesto_dualsense4unix.daemon import lifecycle
        from hefesto_dualsense4unix.testing import FakeController


        def _frio():
            print("frio", flush=True)
            time.sleep(1.0)


        lifecycle._importar_o_que_a_subida_usa = _frio
        daemon = lifecycle.Daemon(
            controller=FakeController(transport="usb", states=[]),
            config=lifecycle.DaemonConfig(
                ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False
            ),
        )
        asyncio.run(daemon.run())
        print("saiu", flush=True)
        """
    )
    ambiente = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
    }
    ambiente.pop("NOTIFY_SOCKET", None)
    processo = subprocess.Popen(
        [sys.executable, "-c", roteiro],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=ambiente,
    )
    try:
        assert processo.stdout is not None
        assert processo.stdout.readline().strip() == "frio"
        processo.send_signal(signal.SIGTERM)
        saida, _ = processo.communicate(timeout=_PRAZO_S)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait()

    assert processo.returncode == 0
    assert "saiu" in saida
