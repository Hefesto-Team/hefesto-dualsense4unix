"""A linha de comando não trava e não anuncia o que não fez (sprint de 09/10/2026).

Cinco réguas: o serviço que atende e não responde (status, battery, doctor
voltam em segundos com rc != 0), o aparelho ausente (battery e `test led` não
inventam «0%» nem lightbar), a cor inválida (rc 2, sem Traceback), o diário do
terminal (a saída de `version` é limpa; o `daemon start` segue em INFO) e o rc
do doctor (o pior veredito).
"""
from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import app as cli_app
from hefesto_dualsense4unix.cli import cmd_doctor, cmd_status, cmd_test
from hefesto_dualsense4unix.cli import ipc_client as ipc_client_mod
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()


class _ServicoMudo:
    """Aceita a conexão e nunca responde (processo parado, travado)."""

    def __init__(self, caminho: Path) -> None:
        self._parar = threading.Event()
        self._abertas: list[socket.socket] = []
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(8)
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
            self._abertas.append(conexao)

    def parar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2.0)
        for c in self._abertas:
            with contextlib.suppress(OSError):
                c.close()
        self._sock.close()


@pytest.fixture
def servico_mudo(monkeypatch: pytest.MonkeyPatch) -> Iterator[_ServicoMudo]:
    pasta = Path(tempfile.mkdtemp(prefix="hf", dir="/tmp"))
    caminho = pasta / "s.sock"
    servico = _ServicoMudo(caminho)
    monkeypatch.setattr(ipc_client_mod, "ipc_socket_path", lambda: caminho)
    try:
        yield servico
    finally:
        servico.parar()
        with contextlib.suppress(OSError):
            caminho.unlink()
            pasta.rmdir()


class _SemControle:
    """O backend de um posto vago: abre, aceita tudo, não tem controle.

    O `read_state` responde o que o backend de verdade responde sem aparelho
    (`core/backend_pydualsense.py`, o ramo `ds is None`): bateria 0 e o transporte
    inicial «usb». Um dublê que levantasse aqui cairia no `except` do fallback e
    esconderia a conferência que a régua mede.
    """

    def __init__(self, *_a: Any, **_k: Any) -> None:
        self.comandos: list[str] = []

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return False

    def read_state(self) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(connected=False, transport="usb", battery_pct=0)

    def set_led(self, *_a: Any, **_k: Any) -> None:
        self.comandos.append("set_led")


@pytest.fixture
def sem_controle(monkeypatch: pytest.MonkeyPatch) -> type[_SemControle]:
    from hefesto_dualsense4unix.core import backend_pydualsense

    monkeypatch.setattr(backend_pydualsense, "PyDualSenseController", _SemControle)
    return _SemControle


def test_status_com_o_servico_mudo_volta_em_segundos_e_diz_a_causa(
    servico_mudo: _ServicoMudo, sem_controle: type[_SemControle]
) -> None:
    inicio = time.monotonic()
    resultado = runner.invoke(app, ["status"])
    assert time.monotonic() - inicio < 5.0
    assert resultado.exit_code == 1
    assert "não respondeu" in resultado.output
    assert "leitura direta" not in resultado.output


def test_battery_com_o_servico_mudo_sai_com_rc_1(
    servico_mudo: _ServicoMudo, sem_controle: type[_SemControle]
) -> None:
    inicio = time.monotonic()
    resultado = runner.invoke(app, ["battery"])
    assert time.monotonic() - inicio < 5.0
    assert resultado.exit_code == 1
    assert "não respondeu" in resultado.output


def test_o_doctor_com_o_servico_mudo_volta_e_reprova(
    servico_mudo: _ServicoMudo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: None)
    monkeypatch.setattr(cmd_doctor, "_print_storm_block", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_contratos", lambda: 0)
    inicio = time.monotonic()
    resultado = runner.invoke(app, ["doctor"])
    assert time.monotonic() - inicio < 8.0
    assert resultado.exit_code == 2
    assert "parado ou travado" in resultado.output


def test_o_servico_ausente_segue_sendo_leitura_direta(
    monkeypatch: pytest.MonkeyPatch, sem_controle: type[_SemControle]
) -> None:
    async def _fora() -> None:
        return None

    monkeypatch.setattr(cmd_status, "_daemon_status_via_ipc", _fora)
    resultado = runner.invoke(app, ["status"])
    assert resultado.exit_code == 0
    assert "daemon offline" in resultado.output


def test_status_sem_controle_nao_inventa_transporte_nem_bateria(
    monkeypatch: pytest.MonkeyPatch, sem_controle: type[_SemControle]
) -> None:
    async def _fora() -> None:
        return None

    monkeypatch.setattr(cmd_status, "_daemon_status_via_ipc", _fora)
    resultado = runner.invoke(app, ["status"])
    assert resultado.exit_code == 0
    assert "usb" not in resultado.output.lower()
    assert "sem controle disponivel" not in resultado.output


def test_battery_sem_controle_nao_inventa_zero_por_cento(
    monkeypatch: pytest.MonkeyPatch, sem_controle: type[_SemControle]
) -> None:
    async def _fora() -> None:
        return None

    monkeypatch.setattr(cmd_status, "_daemon_status_via_ipc", _fora)
    resultado = runner.invoke(app, ["battery"])
    assert resultado.exit_code == 1
    assert "nenhum controle ao alcance" in resultado.output
    assert "0%" not in resultado.output


def test_led_sem_controle_nao_anuncia_a_lightbar(
    sem_controle: type[_SemControle],
) -> None:
    resultado = runner.invoke(app, ["led", "--color", "#ff0000"])
    assert resultado.exit_code == 1
    assert "nenhum controle ao alcance" in resultado.output
    assert "lightbar" not in resultado.output.lower()


@pytest.mark.parametrize("cor", ["roxo", "#zzzzzz", "1,2", "1,2,999", "a,b,c"])
def test_cor_invalida_e_erro_de_uso_sem_traceback(cor: str) -> None:
    resultado = runner.invoke(app, ["led", "--color", cor])
    assert resultado.exit_code == 2
    assert "Traceback" not in resultado.output
    assert not isinstance(resultado.exception, ValueError)


def test_cor_valida_continua_passando() -> None:
    assert cmd_test._parse_cor("#ff8000") == (255, 128, 0)
    assert cmd_test._parse_cor("255,128,0") == (255, 128, 0)


def test_o_nivel_do_terminal_e_warning_e_o_servico_fica_de_fora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL", raising=False)
    nivel = cli_app._nivel_do_diario_do_terminal
    assert nivel(["hefesto-dualsense4unix", "status"]) == "WARNING"
    assert nivel(["hefesto-dualsense4unix", "--verbose", "version"]) == "WARNING"
    assert nivel(["hefesto-dualsense4unix", "daemon", "start"]) is None
    assert nivel(["hefesto-dualsense4unix", "daemon", "status"]) == "WARNING"
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL", "DEBUG")
    assert nivel(["hefesto-dualsense4unix", "status"]) == "DEBUG"


def test_version_nao_escreve_diario_no_stderr(tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    casa.mkdir()
    env = {
        **os.environ,
        "HOME": str(casa),
        "XDG_CONFIG_HOME": str(casa / "c"),
        "XDG_STATE_HOME": str(casa / "s"),
        "XDG_DATA_HOME": str(casa / "d"),
        "XDG_CACHE_HOME": str(casa / "k"),
        "XDG_RUNTIME_DIR": str(casa / "r"),
    }
    env.pop("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL", None)
    (casa / "r").mkdir(mode=0o700)
    r = subprocess.run(
        [sys.executable, "-m", "hefesto_dualsense4unix.cli.app", "version"],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )
    assert r.returncode == 0
    assert r.stdout.strip()
    assert r.stderr == ""


def _lar_de_mentira(casa: Path) -> dict[str, str]:
    casa.mkdir()
    (casa / "r").mkdir(mode=0o700)
    env = {
        **os.environ,
        "HOME": str(casa),
        "XDG_CONFIG_HOME": str(casa / "c"),
        "XDG_STATE_HOME": str(casa / "s"),
        "XDG_DATA_HOME": str(casa / "d"),
        "XDG_CACHE_HOME": str(casa / "k"),
        "XDG_RUNTIME_DIR": str(casa / "r"),
    }
    env.pop("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL", None)
    return env


def _o_script_instalado(pasta: Path) -> Path:
    """A forma do `hefesto-dualsense4unix` que o pip instala: um script com esse nome."""
    script = pasta / "hefesto-dualsense4unix"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from hefesto_dualsense4unix.cli.app import main\n"
        "sys.exit(main())\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_o_script_instalado_tambem_nasce_calado(tmp_path: Path) -> None:
    env = _lar_de_mentira(tmp_path / "casa")
    env.pop("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", None)
    r = subprocess.run(
        [str(_o_script_instalado(tmp_path)), "profile", "list"],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )
    assert r.returncode == 0
    assert r.stdout.strip()
    assert r.stderr == ""


def test_o_i18n_nao_aparece_nem_com_o_diario_em_info(tmp_path: Path) -> None:
    env = {**_lar_de_mentira(tmp_path / "casa"), "HEFESTO_DUALSENSE4UNIX_LOG_LEVEL": "INFO"}
    r = subprocess.run(
        [str(_o_script_instalado(tmp_path)), "version"],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )
    assert r.returncode == 0
    assert "i18n_initialized" not in r.stdout + r.stderr


def _doctor_com(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    linhas_do_daemon: list[tuple[str, str]],
    rc_do_sh: int = 0,
) -> int:
    script = tmp_path / "doctor.sh"
    script.write_text(f"exit {rc_do_sh}\n", encoding="utf-8")

    async def _checks() -> list[tuple[str, str]]:
        return linhas_do_daemon

    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: script)
    monkeypatch.setattr(cmd_doctor, "_print_storm_block", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_contratos", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_proton_fixado", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", _checks)
    return runner.invoke(app, ["doctor"]).exit_code


def test_doctor_tudo_ok_sai_0(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _doctor_com(monkeypatch, tmp_path, linhas_do_daemon=[("[ OK ]", "x")]) == 0


def test_doctor_com_aviso_sai_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _doctor_com(monkeypatch, tmp_path, linhas_do_daemon=[("[WARN]", "x")]) == 1


def test_doctor_com_falha_sai_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _doctor_com(monkeypatch, tmp_path, linhas_do_daemon=[("[FAIL]", "x")]) == 2


def test_doctor_com_o_script_reprovando_sai_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resultado = _doctor_com(
        monkeypatch, tmp_path, linhas_do_daemon=[("[ OK ]", "x")], rc_do_sh=1
    )
    assert resultado == 2


def test_a_gravidade_das_linhas_le_a_tag_sem_os_espacos() -> None:
    g = cmd_doctor._gravidade_das_linhas
    assert g([("[ OK ]", "a"), ("[INFO]", "b"), ("[CRC]", "c")]) == 0
    assert g([("[ OK ]", "a"), ("[WARN]", "b")]) == 1
    assert g([("[WARN]", "a"), ("[FAIL]", "b")]) == 2
