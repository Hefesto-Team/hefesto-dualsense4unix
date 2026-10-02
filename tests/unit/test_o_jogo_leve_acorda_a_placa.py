"""A placa acordada enquanto um jogo vive — O-JOGO-LEVE-ACORDA-A-PLACA-01."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "hefesto_placa_acordada.sh"


class Lar:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.estado = base / "run"
        self.sys = base / "sys"
        self.chamadas = base / "nvsmi.log"
        self.nvsmi = base / "nvidia-smi"
        self.nvsmi.write_text(
            "#!/bin/sh\n"
            f'echo "$*" >> "{self.chamadas}"\n'
            'case "$*" in *--query-gpu*) echo "0, 3105";; esac\n',
            encoding="utf-8")
        self.nvsmi.chmod(0o755)

    def placa(self, n: int, vendor: str) -> Path:
        cartao = self.sys / "class" / "drm" / f"card{n}"
        (cartao / "device").mkdir(parents=True)
        (cartao / "device" / "vendor").write_text(vendor + "\n", encoding="utf-8")
        return cartao

    def rodar(self, *args: str, pid: int | str | None = None) -> subprocess.CompletedProcess[str]:
        ambiente = {
            "PATH": "/usr/bin:/bin",
            "HEFESTO_PLACA_ESTADO": str(self.estado),
            "HEFESTO_PLACA_SYS": str(self.sys),
            "HEFESTO_PLACA_NVSMI": str(self.nvsmi),
        }
        entrada = f"{pid}\n" if pid is not None else ""
        return subprocess.run(["bash", str(SCRIPT), *args], input=entrada, env=ambiente,
                              capture_output=True, text=True, timeout=30, check=False)

    def nv(self) -> list[str]:
        try:
            return self.chamadas.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

    def estado_de(self) -> str:
        return self.rodar("estado").stdout.strip()


@pytest.fixture
def lar(tmp_path: Path) -> Lar:
    if os.geteuid() == 0:
        pytest.skip("a régua roda fora do root: como root o script ignora o lar de mentira")
    return Lar(tmp_path)


@pytest.fixture
def jogo() -> subprocess.Popen[bytes]:
    """Um processo vivo no papel do jogo."""
    proc = subprocess.Popen(["sleep", "60"])
    yield proc
    proc.kill()
    proc.wait()


def _outro_jogo() -> subprocess.Popen[bytes]:
    return subprocess.Popen(["sleep", "60"])


def test_a_nvidia_ganha_o_piso_e_devolve(lar: Lar, jogo: subprocess.Popen[bytes]) -> None:
    lar.placa(1, "0x10de")
    assert lar.rodar("acordar", pid=jogo.pid).returncode == 0
    assert "-i 0 -lgc 2070,3105" in lar.nv()
    assert lar.estado_de() == f"acordada {jogo.pid}"
    assert lar.rodar("devolver", pid=jogo.pid).returncode == 0
    assert lar.nv()[-1] == "-i 0 -rgc"
    assert lar.estado_de() == "livre"


def test_dois_jogos_o_primeiro_que_sai_nao_devolve(
        lar: Lar, jogo: subprocess.Popen[bytes]) -> None:
    lar.placa(1, "0x10de")
    outro = _outro_jogo()
    try:
        lar.rodar("acordar", pid=jogo.pid)
        lar.rodar("acordar", pid=outro.pid)
        assert sum("-lgc" in c for c in lar.nv()) == 1, "acordou duas vezes"
        lar.rodar("devolver", pid=jogo.pid)
        assert not any("-rgc" in c for c in lar.nv()), "devolveu com um jogo vivo"
        lar.rodar("devolver", pid=outro.pid)
        assert lar.nv()[-1] == "-i 0 -rgc"
    finally:
        outro.kill()
        outro.wait()


def test_o_jogo_que_caiu_nao_segura_a_placa(lar: Lar, jogo: subprocess.Popen[bytes]) -> None:
    """O restaurador morreu junto com o jogo: o próximo jogo que sai devolve."""
    lar.placa(1, "0x10de")
    caido = _outro_jogo()
    lar.rodar("acordar", pid=jogo.pid)
    lar.rodar("acordar", pid=caido.pid)
    caido.kill()
    caido.wait()
    lar.rodar("devolver", pid=jogo.pid)
    assert lar.nv()[-1] == "-i 0 -rgc"
    assert lar.estado_de() == "livre"


def test_a_amd_vai_a_high_e_volta_ao_de_antes(lar: Lar, jogo: subprocess.Popen[bytes]) -> None:
    cartao = lar.placa(0, "0x1002")
    nivel = cartao / "device" / "power_dpm_force_performance_level"
    nivel.write_text("auto\n", encoding="utf-8")
    lar.rodar("acordar", pid=jogo.pid)
    assert nivel.read_text(encoding="utf-8").strip() == "high"
    lar.rodar("devolver", pid=jogo.pid)
    assert nivel.read_text(encoding="utf-8").strip() == "auto"
    assert lar.nv() == [], "sem placa NVIDIA, o nvidia-smi não é chamado"


def test_a_intel_sobe_so_o_minimo(lar: Lar, jogo: subprocess.Popen[bytes]) -> None:
    cartao = lar.placa(0, "0x8086")
    (cartao / "gt_min_freq_mhz").write_text("300\n", encoding="utf-8")
    (cartao / "gt_RP0_freq_mhz").write_text("1500\n", encoding="utf-8")
    (cartao / "gt_max_freq_mhz").write_text("1500\n", encoding="utf-8")
    lar.rodar("acordar", pid=jogo.pid)
    assert (cartao / "gt_min_freq_mhz").read_text(encoding="utf-8").strip() == "1000"
    assert (cartao / "gt_max_freq_mhz").read_text(encoding="utf-8").strip() == "1500"
    lar.rodar("devolver", pid=jogo.pid)
    assert (cartao / "gt_min_freq_mhz").read_text(encoding="utf-8").strip() == "300"


@pytest.mark.parametrize("entrada", ["", "abc", "1 2", "-1", "12;rm"])
def test_pid_torto_e_recusado(lar: Lar, entrada: str) -> None:
    lar.placa(1, "0x10de")
    saida = lar.rodar("acordar", pid=entrada)
    assert saida.returncode == 2, saida.stderr
    assert lar.nv() == []


def test_processo_que_nao_existe_e_recusado(lar: Lar) -> None:
    lar.placa(1, "0x10de")
    assert lar.rodar("acordar", pid=999_999_999).returncode == 2
    assert lar.nv() == []


def test_fora_do_root_sem_o_lar_recusa(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("só faz sentido fora do root")
    saida = subprocess.run(["bash", str(SCRIPT), "estado"], env={"PATH": "/usr/bin:/bin"},
                           capture_output=True, text=True, timeout=30, check=False)
    assert saida.returncode == 1
    assert "requer root" in saida.stderr


def test_a_regra_do_sudo_nomeia_os_tres_verbos_sem_curinga() -> None:
    saida = subprocess.run(["bash", str(SCRIPT), "regra-sudo", "fulana"],
                           capture_output=True, text=True, timeout=30, check=True)
    regra = saida.stdout
    for verbo in ("acordar", "devolver", "estado"):
        assert f"hefesto_placa_acordada.sh {verbo}" in regra
    linhas = [ln for ln in regra.splitlines() if not ln.startswith("#")]
    assert "*" not in "\n".join(linhas)
    assert "fulana ALL=(root) NOPASSWD: HEFESTO_PLACA" in regra


@pytest.mark.parametrize("nome", ["ALL", "a b", "x;y", "", "fulana=1"])
def test_a_regra_recusa_nome_torto(nome: str) -> None:
    saida = subprocess.run(["bash", str(SCRIPT), "regra-sudo", nome],
                           capture_output=True, text=True, timeout=30, check=False)
    assert saida.returncode == 2
    assert saida.stdout == ""


LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"


def _lar_do_lancador(base: Path) -> tuple[dict[str, str], Path]:
    casa = base / "casa"
    (casa / ".config").mkdir(parents=True)
    mudos = base / "mudos"
    mudos.mkdir()
    for nome in ("system76-power", "busctl", "dbus-send"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    sudo = mudos / "sudo"
    sudo.write_text('#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n', encoding="utf-8")
    sudo.chmod(0o755)
    log = base / "placa.log"
    placa = base / "placa.sh"
    placa.write_text(f'#!/bin/sh\nread pid\necho "$1 $pid" >> "{log}"\n', encoding="utf-8")
    placa.chmod(0o755)
    ambiente = {
        "HOME": str(casa),
        "XDG_CONFIG_HOME": str(casa / ".config"),
        "XDG_STATE_HOME": str(base / "estado"),
        "XDG_RUNTIME_DIR": str(base / "runtime"),
        "PATH": f"{mudos}:/usr/bin:/bin",
        "HEFESTO_PLACA_ACORDADA": str(placa),
        "HEFESTO_GM_POLL_SECS": "0.1",
        "SteamAppId": "3621330",
    }
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    return ambiente, log


def _esperar(log: Path, linhas: int) -> list[str]:
    import time

    fim = time.monotonic() + 10
    while time.monotonic() < fim:
        if log.exists() and len(log.read_text(encoding="utf-8").splitlines()) >= linhas:
            break
        time.sleep(0.05)
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_o_lancador_acorda_e_devolve_com_o_pid_do_jogo(tmp_path: Path) -> None:
    ambiente, log = _lar_do_lancador(tmp_path)
    saida = subprocess.Popen(["sh", str(LANCADOR), "/usr/bin/true"], env=ambiente)
    pid = saida.pid
    assert saida.wait(timeout=60) == 0
    linhas = _esperar(log, 2)
    assert linhas == [f"acordar {pid}", f"devolver {pid}"], linhas


def test_sem_o_script_o_jogo_abre_igual(tmp_path: Path) -> None:
    ambiente, log = _lar_do_lancador(tmp_path)
    ambiente["HEFESTO_PLACA_ACORDADA"] = str(tmp_path / "nao-existe.sh")
    saida = subprocess.run(["sh", str(LANCADOR), "/usr/bin/true"], env=ambiente,
                           capture_output=True, text=True, timeout=60, check=False)
    assert saida.returncode == 0, saida.stderr
    assert not log.exists()
