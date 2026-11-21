"""A-LINHA-DE-COMANDO-SO-FALA-DIRETO-COM-O-CONTROLE-COM-O-SERVICO-PARADO-01.

O serviço que recusa ou demora não é o serviço parado: o comando diz o motivo (rc 2) ou
que o serviço não respondeu (rc 1) e nunca abre o controle por fora. Só o socket ausente
(ou a conexão recusada) libera a reserva direta.
"""
from __future__ import annotations

import contextlib
import json
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli import cmd_profile, cmd_tray
from hefesto_dualsense4unix.cli import ipc_client as ipc_client_mod
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()

MOTIVO = "motivo-do-servico-xyz"
ESTADO = {"connected": True, "transport": "usb", "active_profile": "p", "battery_pct": 50}


class _Servidor:
    """O serviço de mentira: ``demora`` responde depois de 0,5 s, ``recusa`` erra, ``mudo`` cala."""

    def __init__(self, caminho: Path, modo: str) -> None:
        self.modo = modo
        self._parar = threading.Event()
        self._abertas: list[socket.socket] = []
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(8)
        self._sock.settimeout(0.1)
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _atender(self, conexao: socket.socket) -> None:
        self._abertas.append(conexao)
        if self.modo == "mudo":
            return
        linha = conexao.makefile("rb").readline()
        pedido = json.loads(linha)
        if self.modo == "demora":
            self._parar.wait(0.5)
            corpo: dict[str, Any] = {"result": {"status": "ok", **ESTADO}}
        else:
            corpo = {"error": {"code": -32602, "message": MOTIVO}}
        resposta = {"jsonrpc": "2.0", "id": pedido["id"], **corpo}
        with contextlib.suppress(OSError):
            conexao.sendall(json.dumps(resposta).encode() + b"\n")

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                conexao, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self._atender, args=(conexao,), daemon=True).start()

    def parar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2.0)
        for c in self._abertas:
            with contextlib.suppress(OSError):
                c.close()
        self._sock.close()


class _Backend:
    """O backend direto: conta quantas vezes se constrói e nunca acha controle."""

    construidos = 0

    def __init__(self, *_a: Any, **_k: Any) -> None:
        type(self).construidos += 1

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return False

    def read_state(self) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(connected=False, transport="usb", battery_pct=0)

    def __getattr__(self, _nome: str) -> Any:
        return lambda *_a, **_k: None


@pytest.fixture
def cena(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    from hefesto_dualsense4unix.core import backend_pydualsense
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    _Backend.construidos = 0
    monkeypatch.setattr(backend_pydualsense, "PyDualSenseController", _Backend)
    gravadas: list[str] = []
    monkeypatch.setattr(cmd_profile, "_gravar_a_escolha_sem_o_daemon", gravadas.append)
    save_profile(Profile(name="Ensaio", match=MatchManual(), priority=1), enxuto=True)
    pasta = Path(tempfile.mkdtemp(prefix="hf", dir="/tmp"))
    caminho = pasta / "s.sock"
    monkeypatch.setattr(ipc_client_mod, "ipc_socket_path", lambda: caminho)
    estado: dict[str, Any] = {"caminho": caminho, "gravadas": gravadas, "servidor": None}

    def subir(modo: str) -> None:
        if modo == "mudo":
            monkeypatch.setattr(ipc_bridge, "PISO_DA_LINHA_DE_COMANDO_S", 0.3)
        estado["servidor"] = _Servidor(caminho, modo)

    estado["subir"] = subir
    try:
        yield estado
    finally:
        if estado["servidor"] is not None:
            estado["servidor"].parar()
        with contextlib.suppress(OSError):
            caminho.unlink()
            pasta.rmdir()


COMANDOS = {
    "trigger": ["test", "trigger", "--side", "left", "--mode", "SimpleRigid", "--params", "3"],
    "led": ["test", "led", "--color", "#ff0000"],
    "rumble": ["test", "rumble", "--weak", "10", "--strong", "20"],
    "activate": ["profile", "activate", "Ensaio"],
    "status": ["status"],
    "battery": ["battery"],
}


def _abriu_por_fora(cena: dict[str, Any], comando: str) -> bool:
    if comando == "activate":
        return bool(cena["gravadas"]) or _Backend.construidos > 0
    return _Backend.construidos > 0


@pytest.mark.parametrize("comando", sorted(COMANDOS))
def test_o_servico_que_demora_atende_e_o_que_recusa_diz_o_motivo(
    cena: dict[str, Any], comando: str
) -> None:
    cena["subir"]("demora")
    demorado = runner.invoke(app, COMANDOS[comando])
    assert demorado.exit_code == 0, demorado.output
    assert _Backend.construidos == 0

    cena["servidor"].parar()
    cena["caminho"].unlink()
    cena["subir"]("recusa")
    recusado = runner.invoke(app, COMANDOS[comando])
    assert recusado.exit_code == 2, recusado.output
    assert MOTIVO in recusado.output
    assert "nenhum controle ao alcance" not in recusado.output
    assert not _abriu_por_fora(cena, comando)


@pytest.mark.parametrize("comando", sorted(COMANDOS))
def test_o_servico_que_nao_responde_sai_com_rc_1_sem_abrir_o_controle(
    cena: dict[str, Any], comando: str
) -> None:
    cena["subir"]("mudo")
    resultado = runner.invoke(app, COMANDOS[comando])
    assert resultado.exit_code == 1, resultado.output
    assert "sem resposta a tempo" in resultado.output or "não respondeu" in resultado.output
    assert "nenhum controle ao alcance" not in resultado.output
    assert not _abriu_por_fora(cena, comando)


@pytest.mark.parametrize("comando", ["trigger", "led", "rumble", "activate", "battery"])
def test_com_o_socket_ausente_a_reserva_direta_abre_o_controle(
    cena: dict[str, Any], comando: str
) -> None:
    runner.invoke(app, COMANDOS[comando])
    assert _abriu_por_fora(cena, comando)


def test_a_reserva_do_icone_so_dispara_com_o_servico_parado(
    cena: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    disparos: list[list[str]] = []
    monkeypatch.setattr(cmd_tray.subprocess, "Popen", lambda argv, **_k: disparos.append(argv))

    cena["subir"]("recusa")
    assert cmd_tray._trocar_de_perfil("Ensaio") is False
    cena["servidor"].parar()
    cena["caminho"].unlink()
    cena["subir"]("mudo")
    assert cmd_tray._trocar_de_perfil("Ensaio") is False
    assert disparos == []

    cena["servidor"].parar()
    cena["caminho"].unlink()
    assert cmd_tray._trocar_de_perfil("Ensaio") is True
    assert len(disparos) == 1


@pytest.mark.parametrize(
    "argumentos",
    [["--mode", "Medium"], ["--mode", "Rigid", "--params", "5"], ["--mode", "Rigid"]],
)
def test_o_modo_ou_os_parametros_invalidos_saem_com_rc_2_sem_traceback(
    cena: dict[str, Any], argumentos: list[str]
) -> None:
    resultado = runner.invoke(app, ["test", "trigger", "--side", "left", *argumentos])
    assert resultado.exit_code == 2, resultado.output
    assert resultado.exception is None or isinstance(resultado.exception, SystemExit)
    assert "Traceback" not in resultado.output
    if argumentos[1] == "Medium":
        assert "Rigid" in resultado.output and "SimpleRigid" in resultado.output
    else:
        assert "position" in resultado.output
    assert _Backend.construidos == 0
