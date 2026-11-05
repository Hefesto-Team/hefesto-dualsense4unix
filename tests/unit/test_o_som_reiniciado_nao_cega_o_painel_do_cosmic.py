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


def _espera_que_avisa(diario: Path) -> str:
    """O `sleep` de mentira da lib: avisa cada espera no diário, na ordem, e dura um quinto.

    A lib espera o daemon morrer (30 x 0,1 s), 1 s para o painel renascer e 20 x 0,5 s para
    o cliente voltar; o caso «nunca volta» gastava 11 s só esperando. Os dublês respondem na
    hora, então a régua confere a ordem das esperas no diário, e não a duração.
    """
    return (
        f'printf "sleep %s\\n" "$1" >> "{diario}"\n'
        'exec /usr/bin/sleep "$(/usr/bin/awk \'BEGIN { printf "%.4f", ARGV[1] / 5 }\' "$1")"\n'
    )


LEVA_O_PIPEWIRE = "# NEEDED libpipewire-0.3.so.0\nexit 0\n"


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
class Ensaio:
    """Os dublês, o estado que eles leem e os processos de mentira."""

    tmp: Path
    fakes: Path
    estado: Path
    diario: Path
    daemon_bin: Path
    pids: dict[int, str] = field(default_factory=dict)
    pais: list[subprocess.Popen[str]] = field(default_factory=list)

    def processo(self, argv0: str, env: dict[str, str] | None = None) -> int:
        """Um ``sleep`` com o argv0 pedido, filho de um pai que o recolhe ao morrer.

        Como o daemon de verdade, que é filho da sessão: sem o pai, o ``sleep`` morto ficaria
        zumbi onde o PID 1 não recolhe órfãos (o contêiner do CI), e o ``kill -0`` o daria vivo.
        """
        pai = subprocess.Popen(
            [BASH, "-c", 'exec -a "$0" sleep 120 >/dev/null 2>&1 &\necho $!\nwait', argv0],
            env=env if env is not None else {"PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.pais.append(pai)
        assert pai.stdout is not None
        pid = int(pai.stdout.readline().strip())
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
        for pai in self.pais:
            pai.communicate(timeout=10)


@pytest.fixture
def ensaio(tmp_path: Path) -> Iterator[Ensaio]:
    fakes = tmp_path / "fakes"
    estado = tmp_path / "estado"
    estado.mkdir()
    diario = tmp_path / "chamadas.log"
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
    _exe(
        fakes,
        "systemd-run",
        f'printf "systemd-run %s\\n" "$*" >> "{diario}"\n'
        f'printf "%s\\n" "$@" > "{estado}/systemd-run.argv"\n'
        f'[ -f "{estado}/nunca-volta" ] || touch "{estado}/cliente-do-painel"\n'
        "exit 0\n",
    )
    _exe(fakes, "sleep", _espera_que_avisa(diario))
    (estado / "clientes").write_text(CLIENTES_BASE, encoding="utf-8")
    (estado / "cliente-do-painel-texto").write_text(CLIENTE_DO_PAINEL, encoding="utf-8")
    daemon_bin = _exe(tmp_path / "usr-bin", "cosmic-settings-daemon", LEVA_O_PIPEWIRE)
    b = Ensaio(tmp_path, fakes, estado, diario, daemon_bin)
    try:
        yield b
    finally:
        b.encerrar()


def _sessao_cosmic(b: Ensaio) -> dict[str, int]:
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


def _reiniciar(b: Ensaio, *, dry_run: bool = False) -> tuple[str, str, str]:
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
            "PATH": f"{b.fakes}:{b.daemon_bin.parent}:/usr/bin:/bin",
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


def test_no_cosmic_o_daemon_conferido_sai_e_volta_com_o_ambiente_da_sessao(
    ensaio: Ensaio,
) -> None:
    """MORDIDA: sem a volta do daemon no reinício, ele segue vivo e nada sobe pelo systemd-run.

    Prova da D-1510-O-SOM-REINICIADO-RELIGA-O-PAINEL-DO-COSMIC.
    """
    p = _sessao_cosmic(ensaio)
    rc, painel, _ = _reiniciar(ensaio)
    assert rc == "0"
    assert painel == "voltou", ensaio.chamadas()
    chamadas = ensaio.chamadas()
    restart = chamadas.index("systemctl --user restart pipewire pipewire-pulse wireplumber")
    subida = next(i for i, c in enumerate(chamadas) if c.startswith("systemd-run "))
    assert restart < subida, chamadas
    esperas = [c for c in chamadas[restart:subida] if c.startswith("sleep ")]
    assert esperas[-1:] == ["sleep 1"], ("o painel não teve a vez de renascer", chamadas)
    assert set(esperas[:-1]) <= {"sleep 0.1"}, chamadas
    volta = chamadas[subida:]
    assert volta[1].startswith("pw-cli ls Client") and "sleep 0.5" not in volta, (
        "a volta não foi conferida logo depois da subida", chamadas)
    for _ in range(50):
        if not _vivo(p["daemon"]):
            break
        time.sleep(0.05)
    assert not _vivo(p["daemon"]), "o daemon conferido não saiu"
    assert _vivo(p["janela"]), "a janela das Configurações morreu: o comm não separa os dois"
    assert _vivo(p["painel"]) and _vivo(p["principal"])
    argv = ensaio.systemd_run()
    assert argv[:2] == ["--user", "--collect"], argv
    assert argv[-1] == str(ensaio.daemon_bin), argv
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


def test_fora_do_cosmic_o_reinicio_e_so_o_systemctl(ensaio: Ensaio) -> None:
    """MORDIDA: sem a pergunta pela sessão, o daemon de quem não usa o COSMIC seria morto."""
    p = _sessao_cosmic(ensaio)
    (ensaio.estado / "cosmic-session").unlink()
    rc, painel, _ = _reiniciar(ensaio)
    assert (rc, painel) == ("0", "")
    assert _vivo(p["daemon"])
    assert not ensaio.systemd_run()
    assert "systemctl --user restart pipewire pipewire-pulse wireplumber" in ensaio.chamadas()


def test_no_cosmic_sem_daemon_nao_sobe_nenhum(ensaio: Ensaio) -> None:
    p = _sessao_cosmic(ensaio)
    ensaio.lista("cosmic-settings", str(p["janela"]))
    rc, painel, _ = _reiniciar(ensaio)
    assert (rc, painel) == ("0", "")
    assert _vivo(p["janela"])
    assert not ensaio.systemd_run()


def test_so_morre_o_pid_que_e_o_daemon(ensaio: Ensaio) -> None:
    """Um PID da lista que não é o daemon (outro programa, ou o número reaproveitado) fica."""
    p = _sessao_cosmic(ensaio)
    outro = ensaio.processo("/usr/bin/outro-programa")
    ensaio.lista("cosmic-settings", str(outro), str(p["daemon"]), str(p["janela"]))
    _reiniciar(ensaio)
    assert _vivo(outro) and _vivo(p["janela"])
    for _ in range(50):
        if not _vivo(p["daemon"]):
            break
        time.sleep(0.05)
    assert not _vivo(p["daemon"])


def test_se_a_sessao_ressuscita_o_daemon_nao_sobe_um_segundo(ensaio: Ensaio) -> None:
    p = _sessao_cosmic(ensaio)
    novo = ensaio.processo(str(ensaio.daemon_bin))
    ensaio.lista(
        "cosmic-settings", str(p["daemon"]), f"{novo} se-morto {p['daemon']}", str(p["janela"])
    )
    (ensaio.estado / "cliente-do-painel").touch()
    rc, painel, _ = _reiniciar(ensaio)
    assert (rc, painel) == ("0", "voltou")
    assert not ensaio.systemd_run(), "subiu um segundo daemon por cima do que a sessão trouxe"
    assert _vivo(novo)


def test_se_nao_volta_o_aviso_diz_o_comando(ensaio: Ensaio) -> None:
    _sessao_cosmic(ensaio)
    (ensaio.estado / "nunca-volta").touch()
    rc, painel, resto = _reiniciar(ensaio)
    assert (rc, painel) == ("0", "nao-voltou"), resto
    cura = resto.splitlines()[0]
    assert f"systemd-run --user --collect {ensaio.daemon_bin}" in cura, cura
    chamadas = ensaio.chamadas()
    subida = next(i for i, c in enumerate(chamadas) if c.startswith("systemd-run "))
    volta = [c for c in chamadas[subida + 1 :] if c.startswith(("pw-cli ", "sleep "))]
    assert volta == ["pw-cli ls Client", "sleep 0.5"] * 20, (
        "a lib desistiu antes de conferir a volta vinte vezes, meio segundo de intervalo",
        volta,
    )


def test_o_daemon_que_nao_le_o_pipewire_fica_quieto(ensaio: Ensaio) -> None:
    """MORDIDA: outra versão do COSMIC, com o daemon sem a libpipewire, não perde o daemon.

    Prova da D-1510-O-SOM-REINICIADO-RELIGA-O-PAINEL-DO-COSMIC.
    """
    p = _sessao_cosmic(ensaio)
    ensaio.daemon_bin.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    rc, painel, resto = _reiniciar(ensaio)
    assert (rc, painel) == ("0", ""), resto
    assert _vivo(p["daemon"])
    assert not ensaio.systemd_run()


def test_systemctl_que_falha_devolve_1_e_nao_mexe_no_painel(ensaio: Ensaio) -> None:
    p = _sessao_cosmic(ensaio)
    (ensaio.estado / "systemctl-falha").touch()
    rc, painel, _ = _reiniciar(ensaio)
    assert (rc, painel) == ("1", "")
    assert _vivo(p["daemon"])
    assert not ensaio.systemd_run()


def test_o_ensaio_so_diz_o_que_faria(ensaio: Ensaio) -> None:
    p = _sessao_cosmic(ensaio)
    rc, _, resto = _reiniciar(ensaio, dry_run=True)
    assert rc == "0"
    assert "FARIA religar o cosmic-settings-daemon" in resto, resto
    assert _vivo(p["daemon"])
    assert not ensaio.systemd_run()


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


def _doctor(b: Ensaio) -> str:
    r = subprocess.run(
        [BASH, "-c", 'set --; source "$DOCTOR_SH"; check_o_painel_do_cosmic_ve_o_som; true'],
        env={
            "PATH": f"{b.fakes}:{b.daemon_bin.parent}:/usr/bin:/bin",
            "DOCTOR_SH": str(DOCTOR),
            "HOME": str(b.tmp),
        },
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


def test_o_doctor_da_ok_com_o_daemon_nos_clientes(ensaio: Ensaio) -> None:
    _sessao_cosmic(ensaio)
    (ensaio.estado / "cliente-do-painel").touch()
    saida = _doctor(ensaio)
    assert saida.startswith("[ OK ] o painel do COSMIC vê o som"), saida


def test_o_doctor_avisa_com_o_daemon_vivo_e_fora_dos_clientes(ensaio: Ensaio) -> None:
    """MORDIDA: sem a leitura do doctor, o daemon cego passa calado."""
    p = _sessao_cosmic(ensaio)
    saida = _doctor(ensaio)
    assert saida.startswith("[WARN] o painel do COSMIC está sem o som"), saida
    assert f"kill {p['daemon']} && systemd-run --user --collect {ensaio.daemon_bin}" in saida
    assert str(p["janela"]) not in saida
    assert _vivo(p["daemon"]), "o doctor só lê"


def test_o_doctor_avisa_com_o_daemon_morto(ensaio: Ensaio) -> None:
    """Prova da D-1510-O-SOM-REINICIADO-RELIGA-O-PAINEL-DO-COSMIC."""
    p = _sessao_cosmic(ensaio)
    ensaio.lista("cosmic-settings", str(p["janela"]))
    saida = _doctor(ensaio)
    assert saida.startswith("[WARN]"), saida
    assert "não está no ar" in saida
    assert f"rode: systemd-run --user --collect {ensaio.daemon_bin}" in saida, saida
    assert "kill" not in saida


@pytest.mark.parametrize("vivo", [True, False])
def test_o_doctor_cala_com_o_daemon_que_nao_le_o_pipewire(ensaio: Ensaio, vivo: bool) -> None:
    """MORDIDA: o daemon que nunca é cliente não está cego, e o aviso seria falso."""
    p = _sessao_cosmic(ensaio)
    ensaio.daemon_bin.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    if not vivo:
        ensaio.lista("cosmic-settings", str(p["janela"]))
    assert _doctor(ensaio) == ""


def test_o_doctor_fora_do_cosmic_nao_diz_nada(ensaio: Ensaio) -> None:
    _sessao_cosmic(ensaio)
    (ensaio.estado / "cosmic-session").unlink()
    assert _doctor(ensaio) == ""


def test_o_doctor_com_o_pipewire_fora_nao_avisa(ensaio: Ensaio) -> None:
    _sessao_cosmic(ensaio)
    (ensaio.estado / "pipewire-fora").touch()
    saida = _doctor(ensaio)
    assert "[WARN]" not in saida and "[FAIL]" not in saida, saida


def test_o_doctor_le_o_painel_na_secao_do_audio() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    assert "    check_pipewire_cura_do_metadata\n    check_o_painel_do_cosmic_ve_o_som\n" in texto
