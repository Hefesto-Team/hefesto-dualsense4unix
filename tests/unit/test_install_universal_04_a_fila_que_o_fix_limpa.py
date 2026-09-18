"""INSTALL-UNIVERSAL (18/09/2026) — a limpeza da fila no `doctor --fix` de qualquer máquina.

O `check_faixa_sintetica.py --casa --limpar` tira da fila de numeração os
endereços de fixture que uma corrida da suíte deixou na config real. Ele roda
no `doctor --fix` (`fix_fila_sem_fixture`), e tinha três furos que só apareciam
na máquina de outra pessoa:

1. **o python** — o `python3` do sistema, com o erro jogado fora. O `--casa`
   importa `platformdirs`, que só a venv do produto garante; sem ele o script
   morria e o doctor dizia "sem endereço de fixture" sem ter lido nada. E o
   `_python_do_produto` preferia `~/.venv` — uma venv qualquer de quem usa a
   máquina — à venv que o install cria;
2. **o daemon de pé regravava a fila** tirada, na próxima vez que um controle
   chegasse (a fila mora na memória dele desde o boot);
3. **a faixa universal** `e8:47:3a` — coberta em
   `test_um_numero_so_01_o_alvo_fala_a_lingua_dela.py`, junto do gesto.

Todos os dublês ficam na FRENTE do PATH: o `systemctl` daqui só anota, e o
socket é um arquivo num diretório temporário. O daemon dela não é tocado.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
UNIT = "hefesto-dualsense4unix.service"


def _systemctl_de_mentira(binario: Path, *, ativo: bool) -> Path:
    """Anota cada chamada; responde `is-active` como mandado. Nunca fala com o systemd."""
    log = binario / "systemctl.log"
    estado = "active" if ativo else "inactive"
    falso = binario / "systemctl"
    falso.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'case "$*" in\n'
        f"    *is-active*) printf '%s\\n' '{estado}'; [ '{estado}' = active ] ;;\n"
        "    *) exit 0 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)
    return log


def _python_que_responde(binario: Path, resposta: str, rc: int = 0) -> Path:
    falso = binario / "python-falso"
    falso.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{resposta}'\nexit {rc}\n", encoding="utf-8"
    )
    falso.chmod(0o755)
    return falso


def _fix(
    tmp_path: Path,
    python: str | Path,
    *,
    ativo: bool,
    socket_de_pe: bool = False,
    extra: dict[str, str] | None = None,
) -> tuple[str, str]:
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    log = _systemctl_de_mentira(binario, ativo=ativo)
    # AF_UNIX tem teto de ~108 bytes no caminho: o runtime é um mkdtemp CURTO,
    # como no teste do gancho, e não o tmp_path.
    runtime = Path(tempfile.mkdtemp(prefix="heffix-"))
    (runtime / "hefesto-dualsense4unix").mkdir(parents=True, exist_ok=True)
    sock = None
    if socket_de_pe:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"))
    try:
        r = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{DOCTOR}"; '
                f"_python_do_produto() {{ printf '%s\\n' '{python}'; }}; "
                "fix_fila_sem_fixture",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                "PATH": f"{binario}:/usr/bin:/bin",
                "HOME": str(tmp_path / "home"),
                "XDG_RUNTIME_DIR": str(runtime),
                **(extra or {}),
            },
        )
    finally:
        if sock is not None:
            sock.close()
        shutil.rmtree(runtime, ignore_errors=True)
    chamadas = log.read_text(encoding="utf-8") if log.exists() else ""
    return r.stdout + r.stderr, chamadas


def test_ok_passa_e_nao_toca_o_daemon(tmp_path: Path) -> None:
    binario = tmp_path / "bin"
    binario.mkdir()
    py = _python_que_responde(binario, "OK: nada a limpar em '/x'.")
    saida, chamadas = _fix(tmp_path, py, ativo=True)
    assert "[ OK ] fila de numeração: sem endereço de fixture" in saida
    assert chamadas == "", "sem limpeza não há o que reler: o daemon fica como está"


def test_o_script_que_morre_no_import_e_aviso_e_nao_verde(tmp_path: Path) -> None:
    """A MORDIDA do furo 1: o verde que não leu o arquivo.

    Antes, qualquer resposta sem `LIMPO:` virava "sem endereço de fixture" —
    inclusive um traceback de `platformdirs` ausente.
    """
    binario = tmp_path / "bin"
    binario.mkdir()
    py = _python_que_responde(
        binario, "ModuleNotFoundError: No module named 'platformdirs'", rc=1
    )
    saida, chamadas = _fix(tmp_path, py, ativo=True)
    assert "[ OK ]" not in saida
    assert "[WARN] limpeza da fila não rodou: ModuleNotFoundError" in saida
    assert chamadas == ""


def test_limpo_reinicia_o_servico_para_ele_nao_regravar(tmp_path: Path) -> None:
    """A MORDIDA do furo 2: sem o `try-restart`, o daemon regrava o que saiu."""
    binario = tmp_path / "bin"
    binario.mkdir()
    py = _python_que_responde(binario, "LIMPO: faixa sintética tirada da fila")
    saida, chamadas = _fix(tmp_path, py, ativo=True)
    assert "[ OK ] fila de numeração: endereços de fixture retirados" in saida
    assert f"--user try-restart {UNIT}" in chamadas
    assert "[ OK ] daemon reiniciado para ler a fila limpa" in saida


def test_daemon_fora_do_systemd_e_dito(tmp_path: Path) -> None:
    """`daemon start --foreground` não é alcançável pelo systemctl: é aviso."""
    binario = tmp_path / "bin"
    binario.mkdir()
    py = _python_que_responde(binario, "LIMPO: faixa sintética tirada da fila")
    saida, _ = _fix(tmp_path, py, ativo=False, socket_de_pe=True)
    assert "[WARN] o socket do daemon está de pé sem o" in saida
    assert "rode --fix de novo" in saida


def test_daemon_parado_nao_gera_aviso(tmp_path: Path) -> None:
    binario = tmp_path / "bin"
    binario.mkdir()
    py = _python_que_responde(binario, "LIMPO: faixa sintética tirada da fila")
    saida, _ = _fix(tmp_path, py, ativo=False)
    assert "[WARN]" not in saida


def test_de_ponta_a_ponta_com_o_script_de_verdade(tmp_path: Path) -> None:
    """O script real, com a config num lar de mentira: tira a fixture, fica o resto."""
    env_config = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    onde = subprocess.run(
        [
            sys.executable,
            "-c",
            "from hefesto_dualsense4unix.utils.xdg_paths import config_dir; print(config_dir())",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        env={**os.environ, "HOME": str(tmp_path / "home"), **env_config},
    ).stdout.strip()
    config = Path(onde)
    assert str(config).startswith(str(tmp_path)), "a config tem de estar no lar de mentira"
    config.mkdir(parents=True, exist_ok=True)
    fila = {
        "version": 3,
        "order": [
            {"addr": "02001a000001", "kind": "dualsense", "rank": 1},
            {"addr": "aabbcc000001", "kind": "dualsense", "rank": 2},
            {"addr": "e8473a000009", "kind": "dualsense", "rank": 3},
        ],
    }
    (config / "controllers.json").write_text(json.dumps(fila), encoding="utf-8")

    saida, chamadas = _fix(
        tmp_path,
        sys.executable,
        ativo=True,
        extra={**env_config, "PYTHONPATH": str(RAIZ / "src")},
    )

    assert "[ OK ] fila de numeração: endereços de fixture retirados" in saida, saida
    assert f"--user try-restart {UNIT}" in chamadas
    restou = [e["addr"] for e in json.loads((config / "controllers.json").read_text())["order"]]
    assert restou == ["02001a000001", "e8473a000009"]


# ------------------------------------------------ o python do produto


def test_uma_venv_qualquer_em_home_nao_e_o_python_do_produto(tmp_path: Path) -> None:
    """A MORDIDA da ordem: ponha `${HOME}/.venv` de volta na frente e esta
    régua reprova — numa máquina alheia, `~/.venv` é qualquer coisa.
    """
    home = tmp_path / "home"
    alheia = home / ".venv" / "bin" / "python"
    alheia.parent.mkdir(parents=True)
    alheia.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    alheia.chmod(0o755)
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; _python_do_produto'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )
    assert r.stdout.strip() != str(alheia), r.stdout


def test_a_venv_ao_lado_do_script_vem_primeiro() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    inicio = texto.index("\n_python_do_produto() {")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert '"${ROOT_DIR}/.venv/bin/python"' in corpo
    assert corpo.index('"${ROOT_DIR}/.venv/bin/python"') < corpo.index(
        "hefesto-dualsense4unix/venv/bin/python"
    )
    assert "${HOME}/.venv" not in corpo


def test_o_apply_fixes_chama_a_limpeza() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    inicio = texto.index("\napply_fixes() {")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert "\n    fix_fila_sem_fixture\n" in corpo
