"""O install não tropeça no pacote quebrado do sistema (17/10/2026).

O defeito medido na bancada: com um kernel novo baixado e sem configurar
(`iF`/`iU` no dpkg), TODO `apt-get install` tenta configurá-lo de novo, o DKMS
de um módulo que não é do Hefesto falha de novo e o apt sai com 100. A cura é
perguntar o estado ao dpkg ANTES, sem root, e não chamar o apt com pacote a
meio; a trava do gerente de pacotes se espera, com teto.

Tudo roda com `dpkg-query`, `apt-get`, `dnf`, `pacman` e `sudo` de mentira no
`PATH` de um `tmp_path`: nada toca o sistema de quem roda o teste.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    PRELUDO as PRELUDO_BASE,
)
from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    _extrai_funcao,
    _extrai_linha,
)
from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    _roda as _roda_com,
)

PRELUDO = "\n".join(
    [
        PRELUDO_BASE,
        _extrai_linha(r"^readonly _RC_PACOTE_A_MEIO=.*$"),
        _extrai_linha(r"^_PACOTES_A_MEIO_LISTA=.*$"),
    ]
)
PRELUDO_ENSAIO = "\n".join([PRELUDO, _extrai_linha(r"^_nao_faria\(\).*$")])
RC_A_MEIO = 75


def _roda(
    corpo: str, *, preludo: str = PRELUDO, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return _roda_com(corpo, preludo=preludo, env=env)


A_MEIO = "iF  linux-image-7.2.6-76070206-generic\niU  linux-generic\nii  bash\n"
TUDO_INSTALADO = "ii  bash\nhi  linux-libc-dev\nrc  pacote-removido\nun  pacote-que-nao-veio\n"


def _bancada(tmp_path: Path, *, dpkg: str = TUDO_INSTALADO, apt_rc: int = 0) -> Path:
    """Os binários de mentira: cada um ANOTA o que recebeu em `$LOG_PKG`."""
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)

    def _escreve(nome: str, corpo: str) -> None:
        alvo = binario / nome
        alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
        alvo.chmod(0o755)

    (tmp_path / "dpkg.txt").write_text(dpkg, encoding="utf-8")
    _escreve(
        "dpkg-query",
        f'printf "dpkg-query\\n" >> "${{LOG_DPKG}}"\ncat "{tmp_path}/dpkg.txt"\n',
    )
    _escreve("sudo", 'exec "$@"\n')
    _escreve("apt-get", f'printf "apt-get %s\\n" "$*" >> "${{LOG_PKG}}"\nexit {apt_rc}\n')
    _escreve("dnf", 'printf "dnf %s\\n" "$*" >> "${LOG_PKG}"\n')
    _escreve("pacman", 'printf "pacman %s\\n" "$*" >> "${LOG_PKG}"\n')
    return binario


def _env(tmp_path: Path, familia: str, binario: Path, **extra: str) -> dict[str, str]:
    return {
        "HEFESTO_FAMILIA_PACOTES": familia,
        "LOG_PKG": str(tmp_path / "pkg.log"),
        "LOG_DPKG": str(tmp_path / "dpkg.log"),
        "PATH": f"{binario}:{os.environ['PATH']}",
        **extra,
    }


def _linhas(arquivo: Path) -> list[str]:
    return arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []


def test_pacote_a_meio_o_apt_nao_e_chamado(tmp_path: Path) -> None:
    """O caso da bancada: `iF`/`iU` no dpkg. Nenhum `apt-get` roda, e o recado diz
    o pacote, o que é do sistema e os dois comandos.

    Prova da D-1710-O-INSTALL-NAO-CHAMA-O-APT-COM-PACOTE-A-MEIO.
    """
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda(
        "run_pkg toolchain-c || echo RC=$?",
        env=_env(tmp_path, "apt", binario),
    )
    assert f"RC={RC_A_MEIO}" in proc.stdout, proc.stdout + proc.stderr
    assert _linhas(tmp_path / "pkg.log") == [], "o apt foi chamado com pacote a meio"
    assert "linux-image-7.2.6-76070206-generic" in proc.stdout
    assert "linux-generic" in proc.stdout
    assert "isso é do sistema, não do Hefesto" in proc.stdout
    assert "sudo apt-get install -f" in proc.stdout
    assert "sudo dpkg --configure -a" in proc.stdout
    assert "sudo apt install build-essential python3-dev linux-libc-dev" in proc.stdout


@pytest.mark.parametrize(
    "linha",
    ["iF  um-pacote", "iU  um-pacote", "iH  um-pacote", "iiR um-pacote"],
)
def test_cada_estado_quebrado_barra_o_apt(tmp_path: Path, linha: str) -> None:
    binario = _bancada(tmp_path, dpkg=f"ii  bash\n{linha}\n")
    proc = _roda("run_pkg hidapi || echo RC=$?", env=_env(tmp_path, "apt", binario))
    assert f"RC={RC_A_MEIO}" in proc.stdout, proc.stdout + proc.stderr
    assert "um-pacote" in proc.stdout
    assert _linhas(tmp_path / "pkg.log") == []


@pytest.mark.parametrize("linha", ["hi  retido", "rc  removido", "un  nunca-veio", "ii  ok"])
def test_estado_que_nao_e_quebrado_nao_barra(tmp_path: Path, linha: str) -> None:
    """Retido, config-files e não-instalado não são pacote a meio."""
    binario = _bancada(tmp_path, dpkg=f"{linha}\n")
    proc = _roda("run_pkg hidapi || echo RC=$?", env=_env(tmp_path, "apt", binario))
    assert "RC=" not in proc.stdout, proc.stdout + proc.stderr
    assert len(_linhas(tmp_path / "pkg.log")) == 1


def test_tudo_em_ii_o_apt_recebe_o_timeout_e_os_nomes(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    proc = _roda("run_pkg hidapi svg-loader", env=_env(tmp_path, "apt", binario))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _linhas(tmp_path / "pkg.log") == [
        "apt-get install -y -qq -o DPkg::Lock::Timeout=120 libhidapi-hidraw0 librsvg2-common"
    ]


def test_o_recado_completo_sai_uma_vez_so(tmp_path: Path) -> None:
    """Quatro chamadores de `run_pkg` num install: o texto longo não se repete."""
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda(
        "run_pkg hidapi || true\nrun_pkg python-venv || true\nrun_pkg wlrctl || true",
        env=_env(tmp_path, "apt", binario),
    )
    assert proc.stdout.count("sudo apt-get install -f") == 1, proc.stdout
    assert proc.stdout.count("pacote a meio") == 3, proc.stdout
    assert "sudo apt install python3-venv" in proc.stdout


def test_o_ensaio_diz_nao_instalaria_e_nao_chama_nada(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda(
        "DRY_RUN=1; run_pkg toolchain-c; echo RC=$?",
        preludo=PRELUDO_ENSAIO,
        env=_env(tmp_path, "apt", binario),
    )
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    assert (
        "não faria:   instalar pacote(s) build-essential python3-dev linux-libc-dev: "
        "o sistema tem pacote a meio"
    ) in proc.stdout
    assert "linux-image-7.2.6-76070206-generic" in proc.stdout
    assert "FARIA" not in proc.stdout
    assert _linhas(tmp_path / "pkg.log") == []


@pytest.mark.parametrize("familia", ["dnf", "pacman"])
def test_fora_do_apt_o_dpkg_nem_e_consultado(tmp_path: Path, familia: str) -> None:
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    livre = tmp_path / "trava-inexistente"
    proc = _roda(
        "run_pkg hidapi",
        env=_env(
            tmp_path,
            familia,
            binario,
            HEFESTO_TRAVA_DNF=str(livre),
            HEFESTO_TRAVA_PACMAN=str(livre),
        ),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (tmp_path / "dpkg.log").exists(), "o dpkg-query rodou numa família sem dpkg"
    assert len(_linhas(tmp_path / "pkg.log")) == 1


def test_apt_falha_com_o_dpkg_ocupado_diz_quem_segura(tmp_path: Path) -> None:
    """Passado o `Lock::Timeout` o apt sai 100: o install diz quem segura a trava."""
    binario = _bancada(tmp_path, apt_rc=100)
    for nome, corpo in (("fuser", 'printf " 4242\\n"\n'), ("ps", 'printf "unattended-upgr\\n"\n')):
        alvo = binario / nome
        alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
        alvo.chmod(0o755)
    proc = _roda(
        "run_pkg hidapi || echo RC=$?",
        env=_env(tmp_path, "apt", binario, HEFESTO_TRAVA_DPKG=str(tmp_path / "sem-trava")),
    )
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "unattended-upgr (pid 4242)" in proc.stdout


def _dono_por_fcntl(trava: Path) -> subprocess.Popen[str]:
    """Segura a trava por fcntl, como o apt e o rpm fazem (o `flock` não a vê)."""
    trava.write_text("", encoding="utf-8")
    dono = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, sys, time\n"
            "f = open(sys.argv[1], 'r+')\n"
            "fcntl.lockf(f, fcntl.LOCK_EX)\n"
            "print('preso', flush=True)\n"
            "time.sleep(30)\n",
            str(trava),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert dono.stdout is not None
    assert dono.stdout.readline().strip() == "preso"
    return dono


def _fuser_cego(binario: Path) -> None:
    """O `fuser` de quem não é root diante de processo de root: não vê nada."""
    alvo = binario / "fuser"
    alvo.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    alvo.chmod(0o755)


def test_apt_ocupado_por_fcntl_diz_quem_segura_sem_o_fuser(tmp_path: Path) -> None:
    """O `unattended-upgrades` é root e trava por fcntl: o `fuser` não o vê, o
    `/proc/locks` sim."""
    binario = _bancada(tmp_path, apt_rc=100)
    _fuser_cego(binario)
    trava = tmp_path / "lock-frontend"
    dono = _dono_por_fcntl(trava)
    try:
        proc = _roda(
            "run_pkg hidapi || echo RC=$?",
            env=_env(tmp_path, "apt", binario, HEFESTO_TRAVA_DPKG=str(trava)),
        )
    finally:
        dono.kill()
        dono.wait()
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert f"(pid {dono.pid})" in proc.stdout, proc.stdout


def test_dnf_espera_a_trava_por_fcntl_do_rpm_sem_o_fuser(tmp_path: Path) -> None:
    """O rpm trava o `.rpm.lock` por fcntl, como root: nem o `flock` nem o `fuser`
    o enxergam, e a espera tem de acontecer assim mesmo."""
    binario = _bancada(tmp_path)
    _fuser_cego(binario)
    trava = tmp_path / "rpm.lock"
    dono = _dono_por_fcntl(trava)
    try:
        inicio = time.monotonic()
        proc = _roda(
            "run_pkg hidapi || echo RC=$?",
            env=_env(
                tmp_path, "dnf", binario, HEFESTO_TRAVA_DNF=str(trava), HEFESTO_TRAVA_TETO="2"
            ),
        )
        gasto = time.monotonic() - inicio
    finally:
        dono.kill()
        dono.wait()
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert gasto >= 2, f"não esperou o teto ({gasto:.1f}s)"
    assert f"(pid {dono.pid})" in proc.stdout, proc.stdout
    assert _linhas(tmp_path / "pkg.log") == [], "o dnf rodou com a trava presa"


@pytest.mark.skipif(shutil.which("flock") is None, reason="sem flock não há trava de rpm a segurar")
def test_dnf_espera_a_trava_do_rpm_e_cai_no_nao_consegui(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    trava = tmp_path / "rpm.lock"
    trava.write_text("", encoding="utf-8")
    dono = subprocess.Popen(
        ["bash", "-c", f"exec 9>{trava}; flock 9; echo preso; sleep 30"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert dono.stdout is not None
        assert dono.stdout.readline().strip() == "preso"
        inicio = time.monotonic()
        proc = _roda(
            "run_pkg hidapi || echo RC=$?",
            env=_env(
                tmp_path, "dnf", binario, HEFESTO_TRAVA_DNF=str(trava), HEFESTO_TRAVA_TETO="2"
            ),
        )
        gasto = time.monotonic() - inicio
    finally:
        dono.kill()
        dono.wait()
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert gasto >= 2, f"não esperou o teto ({gasto:.1f}s)"
    assert "seguiu ocupado" in proc.stdout
    assert _linhas(tmp_path / "pkg.log") == [], "o dnf rodou com a trava presa"


def test_pacman_espera_o_db_lck_sumir_e_depois_instala(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    trava = tmp_path / "db.lck"
    trava.write_text("", encoding="utf-8")
    proc = _roda(
        f"( sleep 1; rm -f '{trava}' ) &\nrun_pkg hidapi\nwait",
        env=_env(
            tmp_path, "pacman", binario, HEFESTO_TRAVA_PACMAN=str(trava), HEFESTO_TRAVA_TETO="10"
        ),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "esperando" in proc.stdout
    assert _linhas(tmp_path / "pkg.log") == ["pacman -S --noconfirm --needed hidapi"]


def test_pacman_com_trava_que_nao_sai_nao_instala(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    trava = tmp_path / "db.lck"
    trava.write_text("", encoding="utf-8")
    proc = _roda(
        "run_pkg hidapi || echo RC=$?",
        env=_env(
            tmp_path, "pacman", binario, HEFESTO_TRAVA_PACMAN=str(trava), HEFESTO_TRAVA_TETO="1"
        ),
    )
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert str(trava) in proc.stdout
    assert _linhas(tmp_path / "pkg.log") == []


def test_o_install_nunca_reconfigura_remove_nem_segura_pacote_do_sistema() -> None:
    """A cura recusa e ensina; não mexe. Nenhum comando (fora de texto impresso)
    reconfigura, remove ou retém pacote."""
    install = (Path(__file__).resolve().parents[2] / "install.sh").read_text(encoding="utf-8")
    codigo = [
        linha
        for linha in install.splitlines()
        if not linha.lstrip().startswith("#") and "printf" not in linha and "warn" not in linha
    ]
    for proibido in ("dpkg --configure", "apt-mark hold", "apt-get remove", "apt-get install -f"):
        achados = [linha for linha in codigo if proibido in linha]
        assert achados == [], f"o install executa «{proibido}»: {achados}"


INSTALL = (Path(__file__).resolve().parents[2] / "install.sh").read_text(encoding="utf-8")
_APT_QUE_INSTALA = re.compile(
    r"^\s*(?:if\s+(?:!\s+)?)?(?:_run_pkg_quieto\s+)?sudo\b[^#]*\bapt-get install\b"
)


def test_todo_apt_get_install_do_install_passa_pela_checagem() -> None:
    """O `.deb`, o backport do BlueZ e o PipeWire da casa chamam o apt sem o
    `run_pkg`: cada um pergunta antes, ou tropeça no mesmo pacote a meio."""
    linhas = INSTALL.splitlines()
    vistos = []
    for i, linha in enumerate(linhas):
        if not _APT_QUE_INSTALA.match(linha) or " -s " in linha:
            continue
        vistos.append(linha.strip())
        if "_run_pkg_quieto sudo apt-get install" in linha:
            continue
        j = i - 1
        while j >= 0 and not re.match(r"^(?:\S+\(\) \{|\})$", linhas[j]):
            if "_avisa_pacote_a_meio" in linhas[j]:
                break
            j -= 1
        assert j >= 0 and "_avisa_pacote_a_meio" in linhas[j], (
            f"install.sh:{i + 1} chama o apt sem perguntar pelo pacote a meio: {linha.strip()}"
        )
    assert len(vistos) >= 4, f"a régua não achou os apt-get do install: {vistos}"


def test_o_run_apt_so_e_chamado_pelo_run_pkg_depois_da_checagem() -> None:
    chamadas = [
        linha
        for linha in INSTALL.splitlines()
        if re.search(r"\brun_apt\b", linha)
        and not linha.lstrip().startswith("#")
        and not linha.startswith("run_apt()")
    ]
    assert [c.strip() for c in chamadas] == ['apt)    run_apt "${_nomes[@]}" ;;'], chamadas
    corpo = _extrai_funcao("run_pkg")
    assert corpo.index("_pacotes_a_meio") < corpo.index("run_apt")


def _formato_deb(tmp_path: Path) -> str:
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "scripts" / "build_deb.sh").write_text(
        f'mkdir -p "{raiz}/dist"\n: > "{raiz}/dist/hefesto_1_all.deb"\n', encoding="utf-8"
    )
    return "\n".join([PRELUDO, "step() { :; }", f'ROOT_DIR="{raiz}"', _extrai_funcao("format_deb")])


def test_o_deb_com_pacote_a_meio_nao_chama_o_apt(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda("format_deb", preludo=_formato_deb(tmp_path), env=_env(tmp_path, "apt", binario))
    assert proc.returncode == 42, proc.stdout + proc.stderr
    assert _linhas(tmp_path / "pkg.log") == [], "o apt foi chamado com pacote a meio"
    assert "isso é do sistema, não do Hefesto" in proc.stdout
    assert "sudo apt install " in proc.stdout and "hefesto_1_all.deb" in proc.stdout
    assert "o sistema tem pacote a meio" in proc.stderr


def test_o_deb_com_tudo_em_ii_vai_ao_apt(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    proc = _roda("format_deb", preludo=_formato_deb(tmp_path), env=_env(tmp_path, "apt", binario))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (chamada,) = _linhas(tmp_path / "pkg.log")
    assert chamada.startswith("apt-get install -y ") and chamada.endswith("hefesto_1_all.deb")


def _trecho(padrao: str) -> str:
    achado = re.search(padrao, INSTALL, re.MULTILINE | re.DOTALL)
    assert achado is not None, f"trecho ausente em install.sh: {padrao}"
    return achado.group(0)


GTK = _trecho(r"^[ ]*(?:_rc_pkg=0\n[ ]*)?run_pkg python-gi .*?GTK3 instalado\\n'")
WLRCTL = _trecho(
    r"(?:^[ ]*_rc_pkg=0\n[ ]*run_pkg wlrctl|^[ ]*if run_pkg wlrctl).*?"
    r"brocellous/wlrctl\\n'\n[ ]*fi\n"
)


def test_o_codigo_de_pacote_a_meio_nao_e_o_um_generico() -> None:
    assert RC_A_MEIO != 1 and f"_RC_PACOTE_A_MEIO={RC_A_MEIO}" in PRELUDO


def test_o_gtk_com_pacote_a_meio_diz_o_pacote_e_nao_a_conexao(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda(GTK, env=_env(tmp_path, "apt", binario))
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 42, saida
    assert "linux-image-7.2.6-76070206-generic" in saida
    assert "GTK3" in proc.stderr and "comando acima" in proc.stderr, proc.stderr
    assert "sudo apt-get install -f" in proc.stdout.rstrip().splitlines()[-1], proc.stdout
    assert not re.search(r"conex|\brepos\b", saida), saida
    assert _linhas(tmp_path / "pkg.log") == [], "o apt foi chamado com pacote a meio"


def test_o_gtk_sem_pacote_a_meio_e_apt_que_falha_continua_na_conexao(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, apt_rc=100)
    proc = _roda(GTK, env=_env(tmp_path, "apt", binario))
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 42, saida
    assert "verifique a conexão e tente novamente" in saida
    assert "pacote a meio" not in saida


def test_o_wlrctl_com_pacote_a_meio_nao_diz_que_falta_nos_repos(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda(WLRCTL, env=_env(tmp_path, "apt", binario))
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "linux-image-7.2.6-76070206-generic" in saida
    assert "repos" not in saida and "conexão" not in saida, saida
    assert "sudo apt install wlrctl" in saida
    assert _linhas(tmp_path / "pkg.log") == [], "o apt foi chamado com pacote a meio"


def test_o_wlrctl_sem_pacote_a_meio_e_apt_que_falha_continua_nos_repos(tmp_path: Path) -> None:
    binario = _bancada(tmp_path, apt_rc=100)
    proc = _roda(WLRCTL, env=_env(tmp_path, "apt", binario))
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "wlrctl não esta nos repos deste sistema" in saida
    assert "pacote a meio" not in saida


def test_o_wlrctl_instalado_diz_instalado(tmp_path: Path) -> None:
    binario = _bancada(tmp_path)
    alvo = binario / "wlrctl"
    alvo.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    alvo.chmod(0o755)
    proc = _roda(WLRCTL, env=_env(tmp_path, "apt", binario))
    assert "wlrctl instalado" in proc.stdout, proc.stdout + proc.stderr


def test_o_ensaio_do_gtk_com_pacote_a_meio_segue_sem_morrer(tmp_path: Path) -> None:
    """O ensaio devolve 0: o plano descreve a instalação que dá certo."""
    binario = _bancada(tmp_path, dpkg=A_MEIO)
    proc = _roda("DRY_RUN=1\n" + GTK, preludo=PRELUDO_ENSAIO, env=_env(tmp_path, "apt", binario))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "GTK3 instalado" in proc.stdout
