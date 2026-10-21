"""O prazo de cada método do IPC tem um dono só, e a linha de comando o usa.

A-LINHA-DE-COMANDO-ESPERA-O-QUE-O-SERVICO-PRECISA-01 (09/10/2026). A tabela de
prazos morava na ponte da janela, onde a linha de comando não chega, e cada
`cmd_*` digitava o seu `timeout=1.0`: uma troca de perfil de 1 a 3 s saía no
terminal como «nada foi ativado», e o serviço ativava o perfil logo depois.

A MORDIDA: devolva o `timeout=1.0` do `profile.switch` em `cli/cmd_profile.py`
e reprovam a varredura da fonte e o `profile apply` contra o serviço lento.
"""
from __future__ import annotations

import ast
import contextlib
import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner


from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli import ipc_client
from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.interface.pacotes import ponte
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils import xdg_paths

PACOTE = Path(ipc_bridge.__file__).resolve().parents[1]
FONTES = [
    *sorted((PACOTE / "cli").rglob("*.py")),
    PACOTE / "app" / "ipc_bridge.py",
    *sorted((PACOTE / "interface" / "pacotes").rglob("*.py")),
]
CHAMADAS = {"_run_call", "_safe_call", "_call_checked", "_call_checked_detalhado",
            "call_async"}
PERFIL = "lento"


def _prazos_literais(caminho: Path) -> list[str]:
    achados: list[str] = []
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if not isinstance(no, ast.Call):
            continue
        func = no.func
        nome = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if nome not in CHAMADAS:
            continue
        for chave in no.keywords:
            if chave.arg in ("timeout", "timeout_s") and isinstance(
                chave.value, ast.Constant
            ) and isinstance(chave.value.value, (int, float)):
                achados.append(f"{caminho.relative_to(PACOTE)}:{no.lineno}")
    return achados


def test_nenhum_prazo_numerico_digitado_numa_chamada_do_ipc() -> None:
    achados = [a for caminho in FONTES for a in _prazos_literais(caminho)]
    assert achados == [], (
        "o prazo tem um dono, `ipc_bridge.TETOS`: passe o nome do método a "
        f"`teto` ou a `teto_da_linha_de_comando` em {achados}"
    )


def test_a_ponte_da_janela_reexporta_a_tabela_sem_copia() -> None:
    assert ponte.TETOS is ipc_bridge.TETOS
    assert ponte.teto is ipc_bridge.teto
    assert ipc_bridge.teto("profile.switch") == ipc_bridge.PROFILE_SWITCH_TIMEOUT_S
    assert ipc_bridge.teto("metodo.que.nao.existe") == ipc_bridge.TETO_PADRAO_S
    assert ipc_bridge.teto_da_linha_de_comando("daemon.state_full") == (
        ipc_bridge.PISO_DA_LINHA_DE_COMANDO_S)


# O serviço de mentira: um socket que responde ao `profile.switch` com demora.


class _ServicoLento:
    def __init__(self, caminho: Path, demora_s: float | None) -> None:
        self.caminho = caminho
        self.demora_s = demora_s
        self.pedidos: list[str] = []
        self._parar = threading.Event()
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(4)
        self._sock.settimeout(0.1)
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                conexao, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                self._atender(conexao)

    def _atender(self, conexao: socket.socket) -> None:
        bruto = b""
        while not bruto.endswith(b"\n"):
            pedaco = conexao.recv(4096)
            if not pedaco:
                return
            bruto += pedaco
        pedido = json.loads(bruto)
        self.pedidos.append(pedido["method"])
        if self.demora_s is None:
            self._parar.wait(10.0)
            return
        time.sleep(self.demora_s)
        resposta = {"jsonrpc": "2.0", "id": pedido["id"],
                    "result": {"active_profile": pedido["params"].get("name")}}
        with contextlib.suppress(OSError):
            conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")

    def parar(self) -> None:
        self._parar.set()
        self._sock.close()
        self._fio.join(timeout=12.0)


class _SemAparelho:
    def __init__(self, *_a: Any, **_k: Any) -> None:
        raise RuntimeError("sem aparelho nesta régua")


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    perfis = tmp_path / "profiles"
    perfis.mkdir()
    configuracao = tmp_path / "config"
    configuracao.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: perfis)
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: configuracao)
    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: configuracao)
    from hefesto_dualsense4unix.core import backend_pydualsense

    monkeypatch.setattr(backend_pydualsense, "PyDualSenseController", _SemAparelho)
    arquivo = tmp_path / f"{PERFIL}.json"
    arquivo.write_text(json.dumps({
        "name": PERFIL, "priority": 5,
        "match": {"type": "criteria", "window_class": ["Lento"]},
        "triggers": {"left": {"mode": "Off"}, "right": {"mode": "Off"}},
        "leds": {"lightbar": [255, 128, 0]},
    }), encoding="utf-8")
    return arquivo


def _servico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             demora_s: float | None) -> Iterator[_ServicoLento]:
    caminho = tmp_path / "s"
    monkeypatch.setattr(ipc_client, "ipc_socket_path", lambda: caminho)
    servico = _ServicoLento(caminho, demora_s)
    try:
        yield servico
    finally:
        servico.parar()


@pytest.fixture
def servico_lento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_ServicoLento]:
    """Responde em 1,5 s: dentro do teto do `profile.switch`, fora do 1,0 s velho."""
    yield from _servico(tmp_path, monkeypatch, 1.5)


@pytest.fixture
def servico_mudo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_ServicoLento]:
    yield from _servico(tmp_path, monkeypatch, None)


def test_o_apply_espera_o_servico_que_ativa_em_um_segundo_e_meio(
    casa: Path, servico_lento: _ServicoLento,
) -> None:
    resultado = CliRunner().invoke(app, ["profile", "apply", "--file", str(casa)])
    assert "perfil ativado via daemon" in resultado.output, resultado.output
    assert "nada foi ativado" not in resultado.output
    assert servico_lento.pedidos == ["profile.switch"]


def test_o_activate_espera_o_servico_que_ativa_em_um_segundo_e_meio(
    casa: Path, servico_lento: _ServicoLento,
) -> None:
    loader_module.save_profile(
        Profile.model_validate(json.loads(casa.read_text(encoding="utf-8"))))
    resultado = CliRunner().invoke(app, ["profile", "activate", PERFIL])
    assert "perfil ativado via daemon" in resultado.output, resultado.output
    assert servico_lento.pedidos == ["profile.switch"]


def test_o_prazo_vencido_nao_diz_que_nada_foi_ativado(
    casa: Path, servico_mudo: _ServicoLento,
) -> None:
    resultado = CliRunner().invoke(app, ["profile", "apply", "--file", str(casa)])
    saida = " ".join(resultado.output.split())
    assert "sem resposta a tempo" in saida, resultado.output
    assert "hefesto-dualsense4unix status" in saida
    assert "nada foi ativado" not in saida
    assert "recusou" not in saida
