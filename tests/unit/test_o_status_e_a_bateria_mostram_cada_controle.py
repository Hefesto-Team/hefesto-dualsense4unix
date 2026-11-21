"""O-STATUS-E-A-BATERIA-MOSTRAM-CADA-CONTROLE-01.

O status, a bateria e a interface de terminal leem a lista de controles do serviço (uma linha por
controle, pela cor do plástico e pelo transporte, com os valores vivos); o doctor e a lista de
perfis ganham ``--json``, e o ``--quiet`` do doctor vale para todo bloco em Python.
"""
from __future__ import annotations

import asyncio
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

from hefesto_dualsense4unix.cli import ipc_client as ipc_client_mod
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()

NOMES = ("Cosmic Red", "Starlight Blue", "Nova Pink", "Volcanic Red")
TRANSPORTES = ("usb", "usb", "bt", "bt")


def _controle(i: int, l2: int = 0) -> dict[str, Any]:
    return {
        "index": i, "connected": True, "transport": TRANSPORTES[i], "uniq": f"aabbcc00000{i}",
        "player_slot": i + 1, "modelo": NOMES[i], "nome_declarado": None,
        "battery_pct": 90 - 20 * i, "battery_state": "discharging",
        "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2_raw": l2, "r2_raw": 0,
                   "buttons": []},
    }


def _estado(n: int, l2: int = 0) -> dict[str, Any]:
    controles = [_controle(i, l2) for i in range(n)] or [
        {"connected": False, "transport": None, "is_primary": False}
    ]
    return {
        "connected": n > 0, "transport": TRANSPORTES[0] if n else None,
        "active_profile": "Ensaio", "battery_pct": 90 if n else None, "controllers": controles,
    }


class _Servico:
    """O serviço de mentira: responde ``estado`` ao ``state_full``, conta conexões e pedidos."""

    def __init__(self, caminho: Path, estado: dict[str, Any]) -> None:
        self.estado = estado
        self.conexoes = 0
        self.pedidos: list[str] = []
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
        for linha in conexao.makefile("rb"):
            pedido = json.loads(linha)
            self.pedidos.append(pedido["method"])
            if pedido["method"] == "daemon.state_full":
                corpo: dict[str, Any] = {"result": self.estado}
            elif pedido["method"] == "daemon.status":
                topo = {k: v for k, v in self.estado.items() if k != "controllers"}
                corpo = {"result": topo}
            elif pedido["method"] == "profile.list":
                corpo = {"result": {"profiles": []}}
            else:
                corpo = {"error": {"code": -32601, "message": "método desconhecido"}}
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
            self.conexoes += 1
            threading.Thread(target=self._atender, args=(conexao,), daemon=True).start()

    def parar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2.0)
        for c in self._abertas:
            with contextlib.suppress(OSError):
                c.close()
        self._sock.close()


@pytest.fixture
def servico(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    pasta = Path(tempfile.mkdtemp(prefix="hf", dir="/tmp"))
    caminho = pasta / "s.sock"
    monkeypatch.setattr(ipc_client_mod, "ipc_socket_path", lambda: caminho)
    subidos: list[_Servico] = []

    def subir(n: int, l2: int = 0) -> _Servico:
        subidos.append(_Servico(caminho, _estado(n, l2)))
        return subidos[-1]

    try:
        yield subir
    finally:
        for s in subidos:
            s.parar()
        with contextlib.suppress(OSError):
            caminho.unlink()
            pasta.rmdir()


@pytest.mark.parametrize("n", [0, 1, 4])
def test_o_status_mostra_uma_linha_por_controle(servico: Any, n: int) -> None:
    servico(n)

    dados = json.loads(runner.invoke(app, ["status", "--json"]).output)
    assert dados["active_profile"] == "Ensaio"
    assert len(dados["controllers"]) == n

    texto = runner.invoke(app, ["status"])
    assert texto.exit_code == 0, texto.output
    assert texto.output.count("Controle ") == n
    for i in range(n):
        assert NOMES[i] in texto.output
        assert f"{90 - 20 * i}%" in texto.output
    assert texto.output.count("USB") == min(n, 2) and texto.output.count("BT") == max(n - 2, 0)


@pytest.mark.parametrize("n", [1, 4])
def test_a_bateria_mostra_a_carga_de_cada_controle(servico: Any, n: int) -> None:
    servico(n)

    dados = json.loads(runner.invoke(app, ["battery", "--json"]).output)
    assert [c["bateria"] for c in dados["controllers"]] == [90 - 20 * i for i in range(n)]

    texto = runner.invoke(app, ["battery"])
    assert texto.exit_code == 0, texto.output
    assert [linha for linha in texto.output.splitlines() if "%" in linha] == [
        f"Controle {i + 1} ({NOMES[i]}): {90 - 20 * i}%" for i in range(n)
    ]


def test_sem_controle_a_lista_do_json_sai_vazia_e_o_rc_e_zero(servico: Any) -> None:
    servico(0)
    for comando in ("status", "battery"):
        resultado = runner.invoke(app, [comando, "--json"])
        assert resultado.exit_code == 0, resultado.output
        assert json.loads(resultado.output)["controllers"] == []


def test_o_doctor_quiet_nao_imprime_o_que_esta_certo() -> None:
    resultado = runner.invoke(app, ["doctor", "--perfis", "--quiet"])
    assert resultado.exit_code == 0, resultado.output
    assert "[ OK ]" not in resultado.output
    assert "== perfis" not in resultado.output

    cheio = runner.invoke(app, ["doctor", "--perfis"])
    assert "[ OK ] perfis coerentes entre si" in cheio.output


def test_o_doctor_e_a_lista_de_perfis_falam_json() -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    save_profile(Profile(name="Ensaio", match=MatchManual(), priority=1), enxuto=True)

    doctor = json.loads(runner.invoke(app, ["doctor", "--perfis", "--json"]).output)
    assert doctor and {"bloco", "tag", "mensagem"} <= set(doctor[0])
    assert any(linha["tag"] == "OK" for linha in doctor)

    perfis = json.loads(runner.invoke(app, ["profile", "list", "--json"]).output)
    assert [p["nome"] for p in perfis] == ["Ensaio"]


@pytest.mark.asyncio
async def test_a_interface_de_terminal_mantem_uma_conexao_e_mostra_os_valores_vivos(
    servico: Any,
) -> None:
    from hefesto_dualsense4unix.tui.app import HefestoApp
    from hefesto_dualsense4unix.tui.widgets import TriggerBar

    quatro = servico(4, l2=200)

    async with HefestoApp().run_test(headless=True) as pilot:
        await asyncio.sleep(1.0)
        await pilot.pause()
        barras = [w for w in pilot.app.screen.query(TriggerBar)]
        assert len(barras) == 8, "uma barra de L2 e uma de R2 por controle"
        assert all(b.value == 200 for b in barras if b.side_label == "L2")
        assert quatro.pedidos.count("daemon.state_full") > 5

    assert quatro.conexoes == 1, f"uma conexão por tique: {quatro.conexoes}"
