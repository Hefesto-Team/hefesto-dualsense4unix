"""O som reiniciado pelo Hefesto não cega o painel do COSMIC.

O-SOM-REINICIADO-NAO-CEGA-O-PAINEL-DO-COSMIC-01 (15/10/2026). No COSMIC 1.10, o applet de som
do painel lê o PipeWire pelo ``cosmic-settings-daemon``, e um reinício do PipeWire o deixa vivo
e fora dos clientes. O install e o uninstall reiniciam o som por um ponto só,
``scripts/lib/som_da_sessao.sh``, que o religa; o doctor lê o mesmo fato.

Nada aqui toca o som nem a sessão de quem roda: ``systemctl``, ``pgrep``, ``pw-cli`` e
``systemd-run`` são dublês no PATH, e o daemon, a janela das Configurações e o painel são
processos ``sleep`` deste teste, com o argv0 e o ambiente que o produto lê em ``/proc``. O
``pgrep`` de verdade nunca os acharia (o ``comm`` deles é ``sleep``), e o de mentira só
devolve os deles.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import stat
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
LIB = RAIZ / "scripts" / "lib" / "som_da_sessao.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

#: Um endereço de faixa forjada nas propriedades de um cliente: nunca pode chegar à saída.
ENDERECO_FORJADO = "aa:bb:cc:00:00:01"

CLIENTES_BASE = (
    "\tid 34, type PipeWire:Interface:Client/3\n"
    ' \t\tapplication.name = "WirePlumber"\n'
    "\tid 86, type PipeWire:Interface:Client/3\n"
    f' \t\tapplication.name = "bluez {ENDERECO_FORJADO}"\n'
)
CLIENTE_DO_PAINEL = (
    '\tid 83, type PipeWire:Interface:Client/3\n \t\tapplication.name = "cosmic-settings-daemon"\n'
)


def _exe(pasta: Path, nome: str, corpo: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)
    return alvo


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _argv0(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0", 1)[0].decode()
    except OSError:
        return ""


@dataclass
class Bancada:
    """Os dublês, o estado que eles leem e os processos de mentira."""

    tmp: Path
    fakes: Path
    estado: Path
    diario: Path
    daemon_bin: Path
    pids: dict[int, str] = field(default_factory=dict)

    def processo(self, argv0: str, env: dict[str, str] | None = None) -> int:
        """Um ``sleep`` órfão (o init o recolhe ao morrer), com o argv0 pedido."""
        r = subprocess.run(
            [BASH, "-c", 'exec -a "$0" sleep 120 >/dev/null 2>&1 &\necho $!', argv0],
            env=env if env is not None else {"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        pid = int(r.stdout.strip())
        for _ in range(100):
            if _argv0(pid) == argv0:
                break
            time.sleep(0.01)
        self.pids[pid] = argv0
        return pid

    def lista(self, nome: str, *linhas: str) -> None:
        (self.estado / nome).write_text("".join(f"{x}\n" for x in linhas), encoding="utf-8")

    def chamadas(self) -> list[str]:
        if not self.diario.exists():
            return []
        return self.diario.read_text(encoding="utf-8").splitlines()

    def systemd_run(self) -> list[str]:
        alvo = self.estado / "systemd-run.argv"
        return alvo.read_text(encoding="utf-8").splitlines() if alvo.exists() else []

    def encerrar(self) -> None:
        for pid, argv0 in self.pids.items():
            if _vivo(pid) and _argv0(pid) == argv0:
                os.kill(pid, signal.SIGKILL)


@pytest.fixture
def bancada(tmp_path: Path) -> Iterator[Bancada]:
    fakes = tmp_path / "fakes"
    estado = tmp_path / "estado"
    estado.mkdir()
    diario = tmp_path / "chamadas.log"
    # `pgrep -u UID -x NOME`: os PIDs do arquivo do nome. Uma linha `PID se-morto ANTIGO`
    # só aparece depois que ANTIGO morreu (a sessão que ressuscita o daemon).
    _exe(
        fakes,
        "pgrep",
        'nome=""; uid=""\n'
        'while [ $# -gt 0 ]; do case "$1" in -x) nome="$2"; shift 2 ;; '
        '-u) uid="$2"; shift 2 ;; *) shift ;; esac; done\n'
        f'printf "pgrep -u %s -x %s\\n" "$uid" "$nome" >> "{diario}"\n'
        f'f="{estado}/$nome"; [ -f "$f" ] || exit 1\n'
        "rc=1\n"
        "while read -r pid cond antigo; do\n"
        '  [ -n "$pid" ] || continue\n'
        '  if [ "$cond" = se-morto ] && kill -0 "$antigo" 2>/dev/null; then continue; fi\n'
        '  echo "$pid"; rc=0\n'
        'done < "$f"\n'
        "exit $rc\n",
    )
    _exe(
        fakes,
        "systemctl",
        f'printf "systemctl %s\\n" "$*" >> "{diario}"\n'
        f'[ -f "{estado}/systemctl-falha" ] && exit 1\nexit 0\n',
    )
    _exe(
        fakes,
        "pw-cli",
        f'printf "pw-cli %s\\n" "$*" >> "{diario}"\n'
        f'[ -f "{estado}/pipewire-fora" ] && {{ echo "Error: failed to connect" >&2; exit 1; }}\n'
        f'cat "{estado}/clientes"\n'
        f'[ -f "{estado}/cliente-do-painel" ] && cat "{estado}/cliente-do-painel-texto"\n'
        "exit 0\n",
    )
    # O systemd-run de mentira anota os argumentos e põe o daemon nos clientes
    # (a menos que o teste peça que ele não volte).
    _exe(
        fakes,
        "systemd-run",
        f'printf "systemd-run %s\\n" "$*" >> "{diario}"\n'
        f'printf "%s\\n" "$@" > "{estado}/systemd-run.argv"\n'
        f'[ -f "{estado}/nunca-volta" ] || touch "{estado}/cliente-do-painel"\n'
        "exit 0\n",
    )
    (estado / "clientes").write_text(CLIENTES_BASE, encoding="utf-8")
    (estado / "cliente-do-painel-texto").write_text(CLIENTE_DO_PAINEL, encoding="utf-8")
    daemon_bin = _exe(tmp_path / "usr-bin", "cosmic-settings-daemon", "exit 0\n")
    b = Bancada(tmp_path, fakes, estado, diario, daemon_bin)
    try:
        yield b
    finally:
        b.encerrar()


def _sessao_cosmic(b: Bancada) -> dict[str, int]:
    """A sessão COSMIC de mentira: a sessão, o painel com o ambiente, o daemon e a janela."""
    principal = b.processo("cosmic-session")
    painel = b.processo(
        "cosmic-panel",
        env={
            "PATH": "/usr/bin:/bin",
            "WAYLAND_DISPLAY": "wayland-teste",
            "XDG_RUNTIME_DIR": "/run/user/teste",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/teste/bus",
            "COSMIC_VERSION": "teste",
            "LANG": "pt_BR.UTF-8",
            "HOME": "/lar/teste",
            "SEGREDO_DO_PAINEL": "nao-sai",
        },
    )
    daemon = b.processo(str(b.daemon_bin))
    janela = b.processo("cosmic-settings")
    b.lista("cosmic-session", str(principal))
    b.lista("cosmic-panel", str(painel))
    b.lista("cosmic-settings", str(daemon), str(janela))
    return {"principal": principal, "painel": painel, "daemon": daemon, "janela": janela}


def _reiniciar(b: Bancada, *, dry_run: bool = False) -> tuple[str, str, str]:
    script = (
        "set -euo pipefail\n"
        "_faria() { printf 'FARIA %s\\n' \"$*\"; }\n"
        f'source "{LIB}"\n'
        "rc=0\nreiniciar_o_som_da_sessao || rc=$?\n"
        'printf "rc=%s\\npainel=%s\\ncura=%s\\n" "$rc" '
        '"$SOM_PAINEL_DO_COSMIC" "$SOM_CURA_DO_PAINEL"\n'
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": f"{b.fakes}:/usr/bin:/bin",
            "HOME": str(b.tmp),
            "DRY_RUN": "1" if dry_run else "0",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    campos = dict(linha.split("=", 1) for linha in r.stdout.splitlines() if "=" in linha)
    return campos["rc"], campos["painel"], campos.get("cura", "") + "\n" + r.stdout


# ------------------------------------------------------------------ o reinício


def test_no_cosmic_o_daemon_conferido_sai_e_volta_com_o_ambiente_da_sessao(
    bancada: Bancada,
) -> None:
    """MORDIDA: sem a volta do daemon no reinício, ele segue vivo e nada sobe pelo systemd-run."""
    p = _sessao_cosmic(bancada)
    rc, painel, _ = _reiniciar(bancada)
    assert rc == "0"
    assert painel == "voltou", bancada.chamadas()
    chamadas = bancada.chamadas()
    restart = chamadas.index("systemctl --user restart pipewire pipewire-pulse wireplumber")
    subida = next(i for i, c in enumerate(chamadas) if c.startswith("systemd-run "))
    assert restart < subida, chamadas
    for _ in range(50):
        if not _vivo(p["daemon"]):
            break
        time.sleep(0.05)
    assert not _vivo(p["daemon"]), "o daemon conferido não saiu"
    assert _vivo(p["janela"]), "a janela das Configurações morreu: o comm não separa os dois"
    assert _vivo(p["painel"]) and _vivo(p["principal"])
    argv = bancada.systemd_run()
    assert argv[:2] == ["--user", "--collect"], argv
    assert argv[-1] == str(bancada.daemon_bin), argv
    ambiente = {argv[i + 1] for i, a in enumerate(argv) if a == "-E"}
    for esperado in (
        "WAYLAND_DISPLAY=wayland-teste",
        "XDG_RUNTIME_DIR=/run/user/teste",
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/teste/bus",
        "COSMIC_VERSION=teste",
        "LANG=pt_BR.UTF-8",
        "HOME=/lar/teste",
    ):
        assert esperado in ambiente, ambiente
    assert not any(a.startswith("SEGREDO_DO_PAINEL") for a in ambiente), ambiente
    assert any(c.startswith("pw-cli ls Client") for c in chamadas), "a volta não foi conferida"
    uid = str(os.getuid())
    for c in chamadas:
        if c.startswith("pgrep "):
            assert c.startswith(f"pgrep -u {uid} -x "), c


def test_fora_do_cosmic_o_reinicio_e_so_o_systemctl(bancada: Bancada) -> None:
    """MORDIDA: sem a pergunta pela sessão, o daemon de quem não usa o COSMIC seria morto."""
    p = _sessao_cosmic(bancada)
    (bancada.estado / "cosmic-session").unlink()
    rc, painel, _ = _reiniciar(bancada)
    assert (rc, painel) == ("0", "")
    assert _vivo(p["daemon"])
    assert not bancada.systemd_run()
    assert "systemctl --user restart pipewire pipewire-pulse wireplumber" in bancada.chamadas()


def test_no_cosmic_sem_daemon_nao_sobe_nenhum(bancada: Bancada) -> None:
    p = _sessao_cosmic(bancada)
    bancada.lista("cosmic-settings", str(p["janela"]))
    rc, painel, _ = _reiniciar(bancada)
    assert (rc, painel) == ("0", "")
    assert _vivo(p["janela"])
    assert not bancada.systemd_run()


def test_so_morre_o_pid_que_e_o_daemon(bancada: Bancada) -> None:
    """Um PID da lista que não é o daemon (outro programa, ou o número reaproveitado) fica."""
    p = _sessao_cosmic(bancada)
    outro = bancada.processo("/usr/bin/outro-programa")
    bancada.lista("cosmic-settings", str(outro), str(p["daemon"]), str(p["janela"]))
    _reiniciar(bancada)
    assert _vivo(outro) and _vivo(p["janela"])
    for _ in range(50):
        if not _vivo(p["daemon"]):
            break
        time.sleep(0.05)
    assert not _vivo(p["daemon"])


def test_se_a_sessao_ressuscita_o_daemon_nao_sobe_um_segundo(bancada: Bancada) -> None:
    p = _sessao_cosmic(bancada)
    novo = bancada.processo(str(bancada.daemon_bin))
    bancada.lista(
        "cosmic-settings", str(p["daemon"]), f"{novo} se-morto {p['daemon']}", str(p["janela"])
    )
    (bancada.estado / "cliente-do-painel").touch()
    rc, painel, _ = _reiniciar(bancada)
    assert (rc, painel) == ("0", "voltou")
    assert not bancada.systemd_run(), "subiu um segundo daemon por cima do que a sessão trouxe"
    assert _vivo(novo)


def test_se_nao_volta_o_aviso_diz_o_comando(bancada: Bancada) -> None:
    _sessao_cosmic(bancada)
    (bancada.estado / "nunca-volta").touch()
    rc, painel, resto = _reiniciar(bancada)
    assert (rc, painel) == ("0", "nao-voltou"), resto
    cura = resto.splitlines()[0]
    assert f"systemd-run --user --collect {bancada.daemon_bin}" in cura, cura


def test_systemctl_que_falha_devolve_1_e_nao_mexe_no_painel(bancada: Bancada) -> None:
    p = _sessao_cosmic(bancada)
    (bancada.estado / "systemctl-falha").touch()
    rc, painel, _ = _reiniciar(bancada)
    assert (rc, painel) == ("1", "")
    assert _vivo(p["daemon"])
    assert not bancada.systemd_run()


def test_o_ensaio_so_diz_o_que_faria(bancada: Bancada) -> None:
    p = _sessao_cosmic(bancada)
    rc, _, resto = _reiniciar(bancada, dry_run=True)
    assert rc == "0"
    assert "FARIA religar o cosmic-settings-daemon" in resto, resto
    assert _vivo(p["daemon"])
    assert not bancada.systemd_run()


# ------------------------------------------------------------------ o ponto só


def _sem_comentario(texto: str) -> list[str]:
    return [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]


@pytest.mark.parametrize(
    ("roteiro", "rotina"),
    [(INSTALL, "install_pipewire_da_casa"), (UNINSTALL, "devolver_o_pipewire")],
)
def test_o_install_e_o_uninstall_reiniciam_o_som_pelo_ponto_so(roteiro: Path, rotina: str) -> None:
    """MORDIDA: um `systemctl --user restart pipewire …` de volta ao roteiro reprova."""
    texto = roteiro.read_text(encoding="utf-8")
    assert 'source "${ROOT_DIR}/scripts/lib/som_da_sessao.sh"' in texto
    inicio = texto.index(f"{rotina}() {{\n")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert "if reiniciar_o_som_da_sessao; then" in corpo
    assert "SOM_CURA_DO_PAINEL" in corpo, "o aviso não diz o comando que a pessoa roda"
    soltos = [
        linha
        for linha in _sem_comentario(texto)
        if re.match(r"\s*(if\s+)?systemctl --user restart pipewire\b", linha)
    ]
    assert not soltos, soltos


def test_o_ensaio_do_uninstall_dubla_o_systemd_run() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    bloco = texto[texto.index("for _ens_cmd in rm ") :]
    bloco = bloco[: bloco.index("; do")]
    assert "systemd-run" in bloco.split()


# ------------------------------------------------------------------ o doctor


def _doctor(b: Bancada) -> str:
    r = subprocess.run(
        [BASH, "-c", 'set --; source "$DOCTOR_SH"; check_o_painel_do_cosmic_ve_o_som; true'],
        env={"PATH": f"{b.fakes}:/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": str(b.tmp)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert ENDERECO_FORJADO not in r.stdout + r.stderr
    for c in b.chamadas():
        if c.startswith("pw-cli"):
            assert c == "pw-cli ls Client", f"o doctor chamou o pw-cli fora da leitura: {c}"
    assert not b.systemd_run()
    assert "systemctl" not in "\n".join(b.chamadas())
    return r.stdout


def test_o_doctor_da_ok_com_o_daemon_nos_clientes(bancada: Bancada) -> None:
    _sessao_cosmic(bancada)
    (bancada.estado / "cliente-do-painel").touch()
    saida = _doctor(bancada)
    assert saida.startswith("[ OK ] o painel do COSMIC vê o som"), saida


def test_o_doctor_avisa_com_o_daemon_vivo_e_fora_dos_clientes(bancada: Bancada) -> None:
    """MORDIDA: sem a leitura do doctor, o daemon cego passa calado."""
    p = _sessao_cosmic(bancada)
    saida = _doctor(bancada)
    assert saida.startswith("[WARN] o painel do COSMIC está sem o som"), saida
    assert f"kill {p['daemon']} && systemd-run --user --collect {bancada.daemon_bin}" in saida
    assert str(p["janela"]) not in saida
    assert _vivo(p["daemon"]), "o doctor só lê"


def test_o_doctor_avisa_com_o_daemon_morto(bancada: Bancada) -> None:
    p = _sessao_cosmic(bancada)
    bancada.lista("cosmic-settings", str(p["janela"]))
    saida = _doctor(bancada)
    assert saida.startswith("[WARN]"), saida
    assert "não está no ar" in saida
    assert "rode: systemd-run --user --collect " in saida
    assert "kill" not in saida


def test_o_doctor_fora_do_cosmic_nao_diz_nada(bancada: Bancada) -> None:
    _sessao_cosmic(bancada)
    (bancada.estado / "cosmic-session").unlink()
    assert _doctor(bancada) == ""


def test_o_doctor_com_o_pipewire_fora_nao_avisa(bancada: Bancada) -> None:
    _sessao_cosmic(bancada)
    (bancada.estado / "pipewire-fora").touch()
    saida = _doctor(bancada)
    assert "[WARN]" not in saida and "[FAIL]" not in saida, saida


def test_o_doctor_le_o_painel_na_secao_do_audio() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    assert "    check_pipewire_cura_do_metadata\n    check_o_painel_do_cosmic_ve_o_som\n" in texto
