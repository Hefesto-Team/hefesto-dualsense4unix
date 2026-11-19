"""A regra do nó só fecha com o broker de pé — A-REGRA-DO-NO-SO-FECHA-COM-O-BROKER-DE-PE-01.

O install de verdade, numa raiz de mentira: o `install_udev_host` e o `install_broker_host`
reais, o `scripts/install_udev.sh` real, com dublês do `sudo` (que grava na raiz de mentira)
e do `systemctl` (que guarda o estado do socket do broker).

A MORDIDA: tire o bloco que abre a regra quando o socket do broker não está ativo, no começo
do `install_udev.sh`, e o enable que falha deixa a 73 fechada sem ninguém para abri-la.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts/lib/camada_de_maquina.sh"
INSTALL = RAIZ / "install.sh"
DOCTOR = (RAIZ / "scripts/doctor.sh").read_text(encoding="utf-8")
ASSET_73 = RAIZ / "assets/73-hefesto-ps5-controller.rules"
REGRA_73 = "etc/udev/rules.d/73-hefesto-ps5-controller.rules"
UNIT_DO_BROKER = "etc/systemd/system/hefesto-hidraw-broker.service"

_SUDO = r"""#!/bin/bash
[[ "$1" == "-n" ]] && shift
printf '%s\n' "$*" >> "$DIARIO_SUDO"
case "$1" in
    install)
        shift
        escolhas=()
        pasta=0
        while (($#)); do
            case "$1" in
                -o|-g) shift 2 ;;
                -d) pasta=1; shift ;;
                -*) escolhas+=("$1"); shift ;;
                *) break ;;
            esac
        done
        if ((pasta)); then
            for d in "$@"; do mkdir -p "${RAIZ_FALSA}${d}"; done
            exit 0
        fi
        n=$#
        destino="${!n}"
        exec install "${escolhas[@]}" "${@:1:n-1}" "${RAIZ_FALSA}${destino}"
        ;;
    systemctl) shift; exec systemctl "$@" ;;
    *) exit 0 ;;
esac
"""

_SYSTEMCTL = r"""#!/bin/bash
case "$*" in
    "is-active --quiet hefesto-hidraw-broker.socket") [[ -e "$ESTADO/socket-ativo" ]] ;;
    "enable --now hefesto-hidraw-broker.socket")
        [[ -z "${FALHA_NO_ENABLE:-}" ]] || exit 1
        touch "$ESTADO/socket-ativo" ;;
    "is-active --quiet hefesto-hidraw-broker.service") exit 3 ;;
    *) exit 0 ;;
esac
"""


def _executavel(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o755)


def _install(
    tmp_path: Path, *, abrir_o_no: int = 0, broker_ja_de_pe: bool = False,
    falha_no_enable: bool = False,
) -> tuple[Path, list[str]]:
    binarios = tmp_path / "bin"
    binarios.mkdir()
    _executavel(binarios / "sudo", _SUDO)
    _executavel(binarios / "systemctl", _SYSTEMCTL)
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    estado = tmp_path / "estado"
    estado.mkdir()
    if broker_ja_de_pe:
        (estado / "socket-ativo").touch()
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    diario = tmp_path / "sudo.txt"
    roteiro = (
        "set -euo pipefail\n"
        f'source "{CAMADA}"\n'
        "install_udev_host\ninstall_broker_host\n"
    )
    ambiente = {
        **os.environ,
        "PATH": f"{binarios}:{os.environ['PATH']}",
        "ROOT_DIR": str(RAIZ),
        "SKIP_UDEV": "0",
        "ABRIR_O_NO": str(abrir_o_no),
        "HOME": str(tmp_path / "lar"),
        "RAIZ_FALSA": str(raiz),
        "ESTADO": str(estado),
        "DIARIO_SUDO": str(diario),
        "HEFESTO_RAIZ_PROC": str(proc),
        "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(tmp_path / "troca"),
    }
    if falha_no_enable:
        ambiente["FALHA_NO_ENABLE"] = "1"
    feito = subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True,
                           text=True, check=False, timeout=120)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    return raiz, diario.read_text(encoding="utf-8").splitlines()


def _fechada(regra: Path) -> bool:
    efetivas = [ln for ln in regra.read_text(encoding="utf-8").splitlines()
                if not ln.lstrip().startswith("#")]
    return any('TAG-="uaccess"' in ln for ln in efetivas)


def _gravacoes_da_73(diario: list[str]) -> int:
    return sum(1 for ln in diario if ln.startswith("install") and ln.endswith(f"/{REGRA_73}"))


def test_o_enable_do_broker_que_falha_deixa_a_regra_aberta(tmp_path: Path) -> None:
    """D-1911-A-REGRA-DO-NO-SO-FECHA-COM-O-BROKER-DE-PE: sem broker, a 73 nasce aberta."""
    raiz, _ = _install(tmp_path, falha_no_enable=True)
    assert not _fechada(raiz / REGRA_73), "a regra fechada sem broker trava o controle"


def test_com_o_broker_de_pe_no_fim_a_regra_e_a_fechada(tmp_path: Path) -> None:
    raiz, diario = _install(tmp_path)
    assert (raiz / REGRA_73).read_bytes() == ASSET_73.read_bytes()
    assert _gravacoes_da_73(diario) == 2, "aberta no passo do udev, fechada depois do broker"
    assert "HEFESTO_BROKER_NO_NASCE_FECHADO=1" in (raiz / UNIT_DO_BROKER).read_text("utf-8")


def test_no_reinstall_com_o_broker_de_pe_a_fechada_fica_desde_o_udev(tmp_path: Path) -> None:
    raiz, diario = _install(tmp_path, broker_ja_de_pe=True)
    assert (raiz / REGRA_73).read_bytes() == ASSET_73.read_bytes()
    assert _gravacoes_da_73(diario) == 1


def test_o_opt_out_grava_a_aberta_e_o_broker_sabe(tmp_path: Path) -> None:
    raiz, _ = _install(tmp_path, abrir_o_no=1, broker_ja_de_pe=True)
    assert not _fechada(raiz / REGRA_73)
    assert "HEFESTO_BROKER_NO_NASCE_FECHADO=0" in (raiz / UNIT_DO_BROKER).read_text("utf-8")


def test_o_passo_do_udev_do_nativo_chama_o_dono_que_repassa_a_opcao() -> None:
    """MORDIDA: devolva o `bash scripts/install_udev.sh` sem argumento ao passo 3."""
    texto = INSTALL.read_text(encoding="utf-8")
    passo = texto[texto.index('step "3/11"'):texto.index('step "3b"')]
    assert re.search(r"^\s+install_udev_host$", passo, re.M)
    assert 'bash "${ROOT_DIR}/scripts/install_udev.sh"' not in passo


def _funcao(nome: str) -> str:
    inicio = re.search(rf"^{re.escape(nome)}\(\) \{{\n", DOCTOR, re.M)
    assert inicio is not None, f"{nome}() sumiu do doctor"
    fim = re.search(r"^\}$", DOCTOR[inicio.end():], re.M)
    assert fim is not None
    return DOCTOR[inicio.start(): inicio.end() + fim.end() + 1]


@pytest.mark.parametrize("socket", ["inativo", "ausente"])
@pytest.mark.parametrize("regra", ["fechada", "aberta"])
def test_o_doctor_reprova_a_regra_fechada_sem_broker(
    tmp_path: Path, regra: str, socket: str,
) -> None:
    regras = tmp_path / "rules.d"
    regras.mkdir()
    texto = ASSET_73.read_text(encoding="utf-8")
    if regra == "aberta":
        texto = texto.replace(', TAG-="uaccess"', "")
    (regras / "73-hefesto-ps5-controller.rules").write_text(texto, encoding="utf-8")
    binarios = tmp_path / "bin"
    binarios.mkdir()
    cat_rc = 0 if socket == "inativo" else 1
    _executavel(binarios / "systemctl", (
        "#!/bin/bash\n"
        f'[[ "$1" == cat ]] && exit {cat_rc}\n'
        '[[ "$1" == is-active ]] && { echo inactive; exit 3; }\n'
        "exit 0\n"
    ))
    roteiro = "\n".join([
        'pass() { echo "[PASS] $*"; }', 'warn() { echo "[WARN] $*"; }',
        'fail() { echo "[FAIL] $*"; }', 'info() { echo "[INFO] $*"; }',
        "conselho_de_instalacao() { printf 'rode ./install.sh'; }", "so_no_checkout() { :; }",
        'REGRA_DO_NO="73-hefesto-ps5-controller.rules"',
        'REGRA_DO_NO_VELHA="70-ps5-controller.rules"',
        f'_DIRS_DE_REGRAS_UDEV=("{regras}")',
        *(_funcao(f) for f in ("_regras_udev_em_ordem", "_caminho_da_regra_do_no",
                               "_regra_do_no_e_a_aberta", "_a_regra_do_no_fechada_sem_broker",
                               "check_hidraw_broker")),
        "check_hidraw_broker",
    ])
    saida = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, check=False, timeout=30,
        env={**os.environ, "PATH": f"{binarios}:{os.environ['PATH']}"},
    ).stdout
    if regra == "fechada":
        assert "[FAIL] regra fechada sem broker ativo" in saida, saida
    else:
        assert "[FAIL]" not in saida, saida
        assert "[WARN]" in saida or "[INFO]" in saida, saida


def _sem_logind(raiz: Path) -> bool:
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = texto.index("_sem_systemd_logind() {")
    corpo = texto[inicio:texto.index("\n}\n", inicio) + 3] + "_sem_systemd_logind\n"
    feito = subprocess.run(["bash", "-c", corpo], check=False, timeout=30,
                           env={**os.environ, "HEFESTO_RAIZ_DO_SISTEMA": str(raiz)})
    return feito.returncode == 0


@pytest.mark.parametrize("marca", ["run/systemd/system", ".dockerenv", "run/.containerenv"])
def test_sem_systemd_logind_o_install_recusa_no_comeco(tmp_path: Path, marca: str) -> None:
    """D-1911-A-REGRA-DO-NO-SO-FECHA-COM-O-BROKER-DE-PE: sem logind, recusa (ADR-009)."""
    assert _sem_logind(tmp_path)
    (tmp_path / marca).mkdir(parents=True)
    assert not _sem_logind(tmp_path)
    texto = INSTALL.read_text(encoding="utf-8")
    recusa = texto.index("if _sem_systemd_logind; then")
    assert "docs/adr/009-systemd-logind-scope.md" in texto[recusa:recusa + 300]
    assert recusa < texto.index('source "${ROOT_DIR}/scripts/lib/camada_de_maquina.sh"')
