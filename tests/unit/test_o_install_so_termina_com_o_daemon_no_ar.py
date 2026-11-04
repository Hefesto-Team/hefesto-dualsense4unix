"""O install só termina com o daemon no ar (04/11/2026).

A medida: no install das 08:45 de 04/11 o ``systemctl --user restart`` do passo 7a pegou o daemon
preso na parada; o systemd o matou aos 45 s, a unidade ficou ``failed`` e o restart voltou com erro.
Nada a subiu de novo, e o doctor do fim, que só avisava do serviço parado, deixou o install dizer
«nenhuma FALHA». Aqui o ``systemctl`` é de mentira: ele guarda o estado da unidade num arquivo e
reproduz a parada que estoura.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
UNIDADE = "hefesto-dualsense4unix.service"

_SYSTEMCTL = r"""#!/usr/bin/env bash
estado="$(cat "${ESTADO_DA_UNIDADE}")"
printf '%s\n' "$*" >> "${CHAMADAS}"
[[ "$1" == "--user" ]] && shift
verbo="$1"
case "${verbo}" in
    is-active)
        [[ "$2" == "--quiet" ]] || printf '%s\n' "${estado}"
        [[ "${estado}" == "active" ]]
        exit ;;
    is-enabled)
        printf '%s\n' "${HABILITADA:-enabled}"
        [[ "${HABILITADA:-enabled}" == "enabled" ]]
        exit ;;
    cat) exit 0 ;;
    restart)
        if [[ "${PARADA_ESTOURA:-0}" == "1" ]]; then
            printf 'failed\n' > "${ESTADO_DA_UNIDADE}"
            exit 1
        fi
        printf 'active\n' > "${ESTADO_DA_UNIDADE}"
        exit 0 ;;
    reset-failed)
        [[ "${estado}" == "failed" ]] && printf 'inactive\n' > "${ESTADO_DA_UNIDADE}"
        exit 0 ;;
    start)
        [[ "${START_FALHA:-0}" == "1" || "${estado}" == "failed" ]] && exit 1
        printf 'active\n' > "${ESTADO_DA_UNIDADE}"
        exit 0 ;;
esac
exit 0
"""


def _funcao(arquivo: Path, nome: str) -> str:
    """A função como está no arquivo de hoje, nunca uma cópia."""
    texto = arquivo.read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(nome)}\(\) \{{\n.*?^\}}\n", texto, re.M | re.S)
    assert achado, f"não achei {nome}() em {arquivo.name}"
    return achado.group(0)


def _ambiente(tmp_path: Path, estado: str, **extra: str) -> dict[str, str]:
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    systemctl = binario / "systemctl"
    systemctl.write_text(_SYSTEMCTL, encoding="utf-8")
    systemctl.chmod(0o755)
    (tmp_path / "estado").write_text(f"{estado}\n", encoding="utf-8")
    (tmp_path / "chamadas").write_text("", encoding="utf-8")
    return {
        **os.environ,
        "PATH": f"{binario}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "ESTADO_DA_UNIDADE": str(tmp_path / "estado"),
        "CHAMADAS": str(tmp_path / "chamadas"),
        **extra,
    }


BLOCO_7A = INSTALL.read_text(encoding="utf-8")[
    INSTALL.read_text(encoding="utf-8").index('step "7a/11"'):
    INSTALL.read_text(encoding="utf-8").index(
        '\nif [[ "${DRY_RUN:-0}" -eq 1 ]]; then\n    _faria "fechar e reabrir a janela')
]


def _constantes_do_install() -> str:
    achados = re.findall(r'^readonly ([A-Z_][A-Z0-9_]*)="([^"$`]*)"$',
                         INSTALL.read_text(encoding="utf-8"), re.MULTILINE)
    return "".join(f"{nome}='{valor}'\n" for nome, valor in achados)


def _passo_7a(tmp_path: Path, estado: str, enable_daemon: int,
              **extra: str) -> tuple[subprocess.CompletedProcess[str], str, list[str]]:
    """O passo 7a de verdade, com o ``systemctl`` de mentira e sem jogo aberto."""
    casa = tmp_path / "home"
    casa.mkdir(exist_ok=True)
    proc = tmp_path / "proc"
    (proc / "42").mkdir(parents=True, exist_ok=True)
    (proc / "42" / "environ").write_bytes(b"HOME=/x\0")
    roteiro = (
        "set -euo pipefail\n"
        'step() { printf "STEP %s | %s\\n" "$1" "$2"; }\n'
        'warn() { printf "WARN: %s\\n" "$*"; }\n'
        + _constantes_do_install()
        + f"SKIP_SYSTEMD=0\nenable_daemon={enable_daemon}\nROOT_DIR='{RAIZ}'\n"
        + f"source '{RAIZ / 'scripts' / 'lib' / 'camada_de_maquina.sh'}'\n"
        + BLOCO_7A + "\n"
    )
    ambiente = _ambiente(tmp_path, estado, **extra)
    ambiente.update({
        "HOME": str(casa), "XDG_CONFIG_HOME": str(casa / ".config"),
        "HEFESTO_RAIZ_PROC": str(proc),
        "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(tmp_path / "troca-no-fim-do-jogo"),
    })
    feito = subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True,
                           text=True, timeout=120)
    chamadas = (tmp_path / "chamadas").read_text(encoding="utf-8").splitlines()
    return feito, (tmp_path / "estado").read_text(encoding="utf-8").strip(), chamadas


def test_a_parada_que_estoura_deixa_a_unidade_failed_e_o_install_a_devolve_ao_ar(
    tmp_path: Path,
) -> None:
    feito, estado, chamadas = _passo_7a(tmp_path, "active", 1, PARADA_ESTOURA="1")
    assert feito.returncode == 0, feito.stderr
    assert estado == "active"
    assert "daemon habilitado e no ar" in feito.stdout
    assert "WARN" not in feito.stdout
    assert chamadas.index(f"--user reset-failed {UNIDADE}") < chamadas.index(
        f"--user start {UNIDADE}")


def test_sem_o_auto_start_o_daemon_que_estava_no_ar_tambem_volta(tmp_path: Path) -> None:
    feito, estado, _ = _passo_7a(tmp_path, "active", 0, PARADA_ESTOURA="1")
    assert feito.returncode == 0, feito.stderr
    assert estado == "active"
    assert "WARN" not in feito.stdout
    assert "unit atualizada" in feito.stdout


def test_o_restart_que_da_certo_nao_mexe_em_mais_nada(tmp_path: Path) -> None:
    feito, estado, chamadas = _passo_7a(tmp_path, "active", 1)
    assert feito.returncode == 0, feito.stderr
    assert estado == "active"
    assert chamadas.count(f"--user restart {UNIDADE}") == 1
    assert f"--user start {UNIDADE}" not in chamadas
    assert not any("reset-failed" in c for c in chamadas)


def test_o_daemon_que_nao_volta_e_dito_e_nao_anunciado_no_ar(tmp_path: Path) -> None:
    feito, estado, _ = _passo_7a(tmp_path, "active", 1, PARADA_ESTOURA="1", START_FALHA="1")
    assert feito.returncode == 0, feito.stderr
    assert estado != "active"
    assert "daemon habilitado e no ar" not in feito.stdout
    assert "WARN: o daemon não ficou habilitado e no ar" in feito.stdout


def test_todo_restart_do_daemon_no_install_tem_a_volta_ao_ar() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    restart = 'systemctl --user restart "${DAEMON_UNIT_NAME}" >/dev/null 2>&1'
    com_volta = re.findall(re.escape(restart) + r" \\\n\s*\|\| _devolver_o_daemon_ao_ar", texto)
    assert texto.count(restart) == len(com_volta) >= 2


def _check_service(tmp_path: Path, estado: str, habilitada: str) -> str:
    roteiro = (
        "set -uo pipefail\n"
        "FAILS=0; WARNS=0\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; FAILS=$((FAILS + 1)); }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; WARNS=$((WARNS + 1)); }\n"
        "conselho_de_instalacao() { printf 'rode o install'; }\n"
        'APP_ID="hefesto-dualsense4unix"\n'
        + _funcao(DOCTOR, "check_service")
        + "check_service\n"
    )
    feito = subprocess.run(["bash", "-c", roteiro],
                           env=_ambiente(tmp_path, estado, HABILITADA=habilitada),
                           capture_output=True, text=True, timeout=60)
    return feito.stdout


def test_o_doctor_reprova_o_daemon_habilitado_que_nao_esta_no_ar(tmp_path: Path) -> None:
    saida = _check_service(tmp_path, "failed", "enabled")
    assert re.search(r"^\[FAIL\] .*habilitado mas failed", saida, re.M), saida
    assert "^\\[FAIL\\]" in INSTALL.read_text(encoding="utf-8")


def test_o_doctor_so_avisa_o_daemon_que_a_pessoa_nao_habilitou(tmp_path: Path) -> None:
    saida = _check_service(tmp_path, "inactive", "disabled")
    assert "[FAIL]" not in saida
    assert saida.startswith("[WARN] serviço instalado mas inactive")
    assert _check_service(tmp_path, "inactive", "masked").startswith("[WARN]")


def test_o_doctor_aprova_o_daemon_no_ar(tmp_path: Path) -> None:
    assert _check_service(tmp_path, "active", "enabled").startswith("[ OK ]")
