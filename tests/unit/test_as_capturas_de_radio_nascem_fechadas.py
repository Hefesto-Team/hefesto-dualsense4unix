"""AS-CAPTURAS-DE-RADIO-NASCEM-FECHADAS-01 — a captura do rádio nasce 0600 e sai.

Quatro ferramentas gravam o fio com ``btmon``, e se um controle reconecta no
meio o ``btmon`` grava a chave de pareamento em claro (o ``Link Key Request
Reply``). Até 24/09/2026 as quatro deixavam a captura 0644, do root, no
``/tmp``, para sempre.

A régua roda CADA ferramenta contra um ``btmon`` de mentira e confere três
coisas: o modo com que a captura NASCEU, o modo com que ela foi LIDA, e que ela
SAIU depois — com o caminho na saída. A captura é de mentira (o cabeçalho
``btsnoop``, um ``Link Key Request Reply`` com a chave ``CHAVE-DE-MENTIRA`` e um
report ``0x31``); nenhuma captura real entra aqui.

**Nada aqui toca o rádio dela.** ``btmon``, ``sudo``, ``rfkill``, ``curl``,
``hciconfig``, ``hcitool``, ``bluetoothctl``, ``id`` e ``sleep`` são dublês, e
todo teste confere que o PATH resolve cada um para o dublê ANTES de rodar: o
``rfkill`` de verdade derruba o WiFi sem root onde a sessão tem ACL no
``/dev/rfkill``.

O dublê não é mais frouxo que o real onde isso decide: o ``btmon`` de mentira
abre o arquivo como o ``btsnoop_create`` do BlueZ (``O_CREAT|O_TRUNC``, 0644, a
umask decide). O que ele NÃO imita é o dono: sem root, o arquivo já nasce de
quem mede. Por isso o ``chown`` se prova de dois jeitos — nos scripts, pelo
grupo (o ``SUDO_GID`` aponta para um grupo secundário, e só o ``chown`` o põe
lá); nos ensaios, pela chamada que o ``sudo`` de mentira registrou.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import os
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIGHTBAR = REPO_ROOT / "scripts" / "capturar_a_probe_da_lightbar.sh"
W3 = REPO_ROOT / "scripts" / "medir_w3_coex.sh"
ENSAIOS = REPO_ROOT / "scripts" / "ensaios"
BASH = shutil.which("bash") or "/bin/bash"

#: Todo nome que, de verdade, fala com o rádio, com o WiFi ou com o privilégio.
DUBLES = (
    "btmon", "sudo", "id", "sleep", "rfkill", "curl", "hciconfig", "hcitool",
    "bluetoothctl",
)

#: A chave de pareamento da captura de mentira: 16 bytes, e nenhum é de verdade.
CHAVE = b"CHAVE-DE-MENTIRA"

#: O handle ACL do único report 0x31 da captura de mentira.
HANDLE = 11

#: Endereço de fixture, da faixa forjada da casa.
MAC_DE_MENTIRA = "aa:bb:cc:00:00:01"


def _captura_de_mentira() -> bytes:
    """Um ``btsnoop`` do monitor do BlueZ (datalink 2001) com dois registros.

    O primeiro é o COMANDO que faz a captura ser perigosa — um ``Link Key
    Request Reply`` (``0x040B``) com endereço zerado e a chave de mentira. O
    segundo é um ACL de saída com um report ``0x31`` no handle 11, com os bits
    e a cor que a leitura da lightbar tem de achar (``0x04``/``0x02``/``0x02`` e
    ``11 22 33``).
    """
    assert len(CHAVE) == 16
    cabecalho = b"btsnoop\x00" + struct.pack(">II", 1, 2001)

    def registro(opcode_do_monitor: int, dados: bytes) -> bytes:
        return struct.pack(">IIIIq", len(dados), len(dados), opcode_do_monitor, 0, 0) + dados

    comando = struct.pack("<HB", 0x040B, 22) + bytes(6) + CHAVE
    report = bytearray(78)
    report[0] = 0x31
    report[4], report[41], report[44] = 0x04, 0x02, 0x02  # valid_flag1/2, setup
    report[47:50] = bytes([0x11, 0x22, 0x33])  # R G B
    corpo = bytes([0xA2]) + bytes(report)
    l2cap = struct.pack("<HH", len(corpo), 0x0041) + corpo
    acl = struct.pack("<HH", 0x2000 | HANDLE, len(l2cap)) + l2cap
    return cabecalho + registro(2, comando) + registro(4, acl)


#: O que o ``btmon -r`` de mentira imprime, na forma dos eventos do ``btmon``:
#: uma desconexão e um erro de hardware — o que o W3 conta. A lightbar não
#: passa mais pelo ``btmon -r``: ela lê o arquivo binário.
LEITURA_DE_MENTIRA = """\
> HCI Event: Disconnect Complete (0x05) plen 4
        Reason: Remote User Terminated Connection (0x13)
> HCI Event: Hardware Error (0x10) plen 1
"""

_BTMON = """\
#!{python} -S
# btmon de mentira: grava e lê como o de verdade, sem socket nenhum.
import os, signal, stat, sys, time

def registrar(linha):
    with open(os.environ["BTMON_DE_MENTIRA_LOG"], "a", encoding="utf-8") as arq:
        arq.write(linha + "\\n")

if len(sys.argv) == 3 and sys.argv[1] == "-w":
    caminho = sys.argv[2]
    # Como o btsnoop_create do BlueZ: O_CREAT|O_TRUNC com 0644, e a umask decide.
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o644)
    with open(os.environ["BTMON_DE_MENTIRA_CAPTURA"], "rb") as arq:
        os.write(fd, arq.read())
    pasta = os.path.dirname(caminho) or "."
    registrar(
        "w " + caminho + " " + format(stat.S_IMODE(os.fstat(fd).st_mode), "04o")
        + " " + format(stat.S_IMODE(os.stat(pasta).st_mode), "04o")
    )
    registrar("pid " + str(os.getpid()) + " " + caminho)
    outros = [n for n in os.listdir(pasta) if n != os.path.basename(caminho)]
    registrar("vizinhos " + str(len(outros)) + " " + caminho)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    while True:
        time.sleep(0.05)
elif len(sys.argv) == 3 and sys.argv[1] == "-r":
    caminho = sys.argv[2]
    try:
        st = os.stat(caminho)
    except OSError:
        registrar("r " + caminho + " ausente")
        sys.exit(1)
    registrar("r " + caminho + " " + format(stat.S_IMODE(st.st_mode), "04o"))
    with open(os.environ["BTMON_DE_MENTIRA_LEITURA"], encoding="utf-8") as arq:
        sys.stdout.write(arq.read())
else:
    registrar("? " + " ".join(sys.argv[1:]))
    sys.exit(2)
"""

_SUDO = """\
#!/bin/bash
# sudo de mentira: roda como quem chamou, e só o que os instrumentos pedem.
while [ "$#" -gt 0 ]; do
    case "$1" in
        -n) shift ;;
        -*) echo "sudo de mentira: opção $1 não prevista" >&2; exit 1 ;;
        *) break ;;
    esac
done
case "${1:-}" in
    sh|btmon|chown|chmod|rm|true) ;;
    *) echo "sudo de mentira: recuso $1" >&2; exit 1 ;;
esac
printf '%s\\n' "$*" >> "$SUDO_DE_MENTIRA_LOG"
exec "$@"
"""

_ID = """\
#!/bin/bash
# id de mentira: diz root só para o `-u`, que é o portão dos dois scripts.
if [ "$*" = "-u" ]; then echo 0; exit 0; fi
exec {id} "$@"
"""

_SLEEP = """\
#!/bin/bash
# sleep de mentira: no máximo 0,6 s; o btmon de mentira abre o arquivo em milissegundos.
exec {sleep} "$(awk -v s="${{1:-0}}" 'BEGIN {{ print (s > 0.6 ? 0.6 : s) }}')"
"""

_REGISTRA = """\
#!/bin/bash
printf '%s\\n' "{nome} $*" >> "$CHAMADAS_DE_MENTIRA_LOG"
{resto}
"""


@dataclass
class Dubles:
    """O PATH de mentira e os registros de cada dublê."""

    bin: Path
    tmp: Path
    log_btmon: Path
    log_sudo: Path
    log_chamadas: Path
    captura: Path
    leitura: Path

    @property
    def path(self) -> str:
        return f"{self.bin}:/usr/bin:/bin"

    def conferir(self) -> None:
        """Recusa rodar se algum nome perigoso não resolver para o dublê."""
        for nome in DUBLES:
            achado = shutil.which(nome, path=self.path)
            assert achado == str(self.bin / nome), (
                f"`{nome}` resolveu para {achado}, não para o dublê — recuso rodar"
            )

    def ambiente(self, **extra: str) -> dict[str, str]:
        self.conferir()
        amb = {
            "PATH": self.path,
            "HOME": str(self.tmp / "lar"),
            "TMPDIR": str(self.tmp),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "BTMON_DE_MENTIRA_LOG": str(self.log_btmon),
            "BTMON_DE_MENTIRA_CAPTURA": str(self.captura),
            "BTMON_DE_MENTIRA_LEITURA": str(self.leitura),
            "SUDO_DE_MENTIRA_LOG": str(self.log_sudo),
            "CHAMADAS_DE_MENTIRA_LOG": str(self.log_chamadas),
        }
        amb.update(extra)
        return amb

    def escritas(self) -> list[tuple[str, str, str]]:
        """``(caminho, modo, modo da pasta)`` de cada captura do ``btmon -w``."""
        saida = []
        for linha in self._linhas(self.log_btmon):
            tipo, resto = linha.split(" ", 1)
            if tipo == "w":
                caminho, modo, modo_da_pasta = resto.rsplit(" ", 2)
                saida.append((caminho, modo, modo_da_pasta))
        return saida

    def pids(self) -> list[int]:
        """O pid de cada ``btmon -w`` de mentira, na ordem em que nasceram."""
        return [
            int(linha.split(" ", 2)[1])
            for linha in self._linhas(self.log_btmon) if linha.startswith("pid ")
        ]

    def vizinhos(self) -> list[int]:
        """Quantas outras entradas a pasta da captura tinha quando cada uma nasceu."""
        return [
            int(linha.split(" ", 2)[1])
            for linha in self._linhas(self.log_btmon) if linha.startswith("vizinhos ")
        ]

    def leituras(self) -> list[tuple[str, str]]:
        """``(caminho, modo)`` de cada ``btmon -r``, no instante da leitura."""
        saida = []
        for linha in self._linhas(self.log_btmon):
            tipo, resto = linha.split(" ", 1)
            if tipo == "r":
                caminho, modo = resto.rsplit(" ", 1)
                saida.append((caminho, modo))
        return saida

    @staticmethod
    def _linhas(arquivo: Path) -> list[str]:
        if not arquivo.exists():
            return []
        return [linha for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha]


def _executavel(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o755)


def _fazer_dubles(raiz: Path) -> Dubles:
    bin_ = raiz / "bin"
    bin_.mkdir()
    tmp = raiz / "tmp"
    tmp.mkdir()
    (tmp / "lar").mkdir()
    d = Dubles(
        bin=bin_,
        tmp=tmp,
        log_btmon=raiz / "btmon.log",
        log_sudo=raiz / "sudo.log",
        log_chamadas=raiz / "chamadas.log",
        captura=raiz / "captura-de-mentira.btsnoop",
        leitura=raiz / "leitura-de-mentira.txt",
    )
    d.captura.write_bytes(_captura_de_mentira())
    d.leitura.write_text(LEITURA_DE_MENTIRA, encoding="utf-8")
    id_real = shutil.which("id", path="/usr/bin:/bin")
    sleep_real = shutil.which("sleep", path="/usr/bin:/bin")
    assert id_real and sleep_real
    _executavel(bin_ / "btmon", _BTMON.format(python=sys.executable))
    _executavel(bin_ / "sudo", _SUDO)
    _executavel(bin_ / "id", _ID.format(id=id_real))
    _executavel(bin_ / "sleep", _SLEEP.format(sleep=sleep_real))
    _executavel(bin_ / "rfkill", _REGISTRA.format(nome="rfkill", resto=""))
    _executavel(
        bin_ / "curl", _REGISTRA.format(nome="curl", resto=f"{sleep_real} 0.05")
    )
    _executavel(
        bin_ / "hciconfig",
        _REGISTRA.format(
            nome="hciconfig",
            resto="echo 'RX bytes:100 acl:1 sco:0 events:5 errors:0'\n"
            "echo 'TX bytes:50 acl:1 sco:0 commands:3 errors:0'",
        ),
    )
    for recusado in ("hcitool", "bluetoothctl"):
        _executavel(bin_ / recusado, _REGISTRA.format(nome=recusado, resto="exit 1"))
    return d


@pytest.fixture
def dubles(tmp_path: Path) -> Dubles:
    return _fazer_dubles(tmp_path)


def _grupo_secundario() -> int | None:
    """Um grupo de quem mede que não é o primário — o ``chown`` sem root o aceita."""
    outros = [g for g in os.getgroups() if g != os.getgid()]
    return outros[0] if outros else None


def _modo(caminho: Path) -> int:
    return stat.S_IMODE(caminho.stat().st_mode)


def _morreu(pid: int, segundos: float = 3.0) -> bool:
    """O processo ``pid`` deixou de existir (espera um pouco pelo sinal chegar)."""
    fim = time.monotonic() + segundos
    while True:
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as arq:
                estado = arq.read().rsplit(")", 1)[1].split()[0]
        except OSError:
            return True
        if estado == "Z":  # já saiu; só falta quem o espere
            return True
        if time.monotonic() > fim:
            return False
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# scripts/capturar_a_probe_da_lightbar.sh — o root grava, a usuária compara
# ---------------------------------------------------------------------------


def _rodar_lightbar(
    dubles: Dubles, destino: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    grupo = _grupo_secundario()
    amb = dubles.ambiente(
        HEFESTO_CAPTURA_DIR=str(destino),
        SUDO_UID=str(os.getuid()),
        SUDO_GID=str(grupo if grupo is not None else os.getgid()),
    )
    return subprocess.run(
        [BASH, str(LIGHTBAR), *args],
        capture_output=True, text=True, check=False, env=amb, timeout=60,
    )


@dataclass
class BracoDaLightbar:
    dubles: Dubles
    destino: Path
    velha: Path
    resultado: subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def braco_limpo(tmp_path_factory: pytest.TempPathFactory) -> BracoDaLightbar:
    """O braço ``limpo`` rodado UMA vez: a varredura do ``/proc`` custa segundos.

    O destino já tem a captura crua que a versão anterior deixava, 0644.
    """
    raiz = tmp_path_factory.mktemp("lightbar")
    dubles = _fazer_dubles(raiz)
    destino = raiz / "destino"
    destino.mkdir()
    velha = destino / "probe-sujo.snoop"
    velha.write_bytes(_captura_de_mentira())
    velha.chmod(0o644)
    # Um dono de hidraw que a varredura do `/proc` TEM de ver, sem depender do
    # que está aberto na máquina: o próprio processo da régua segura o arquivo.
    with open(raiz / "hidraw-de-mentira", "wb"):
        resultado = _rodar_lightbar(dubles, destino, "limpo", "1")
    return BracoDaLightbar(dubles, destino, velha, resultado)


class TestALightbarGravaFechadoLeEApaga:
    def test_a_captura_nasce_0600_e_e_lida_0600(self, braco_limpo: BracoDaLightbar) -> None:
        r = braco_limpo.resultado
        assert r.returncode == 0, r.stderr
        escritas = braco_limpo.dubles.escritas()
        assert len(escritas) == 1, escritas
        _, modo, modo_da_pasta = escritas[0]
        assert modo == "0600", f"a captura nasceu {modo}; tem de nascer 0600"
        assert modo_da_pasta == "0700", f"a pasta da captura é {modo_da_pasta}"
        assert "modo 600" in r.stdout, (
            "a captura tem de continuar 0600 até ser lida:\n" + r.stdout
        )

    def test_a_captura_sai_depois_de_lida_e_o_caminho_vai_para_a_saida(
        self, braco_limpo: BracoDaLightbar
    ) -> None:
        (caminho, _, _), = braco_limpo.dubles.escritas()
        assert not Path(caminho).exists(), "a captura crua ficou no disco"
        assert not Path(caminho).parent.exists(), "a pasta privada da captura ficou"
        assert f"captura apagada: {caminho}" in braco_limpo.resultado.stdout

    def test_a_captura_crua_da_versao_anterior_sai(self, braco_limpo: BracoDaLightbar) -> None:
        assert not braco_limpo.velha.exists()

    def test_quem_tem_hidraw_aberto_nao_vira_nenhum(self, braco_limpo: BracoDaLightbar) -> None:
        """O braço limpo depende desta lista, e ela dizia «(nenhum)» com a Steam listada."""
        saida = braco_limpo.resultado.stdout
        assert "hidraw-de-mentira" in saida, saida
        assert "(nenhum)" not in saida, saida

    def test_o_comparar_sem_root_le_so_a_leitura(self, braco_limpo: BracoDaLightbar) -> None:
        leitura = braco_limpo.destino / "probe-limpo.txt"
        assert _modo(leitura) == 0o600
        assert leitura.stat().st_uid == os.getuid()
        grupo = _grupo_secundario()
        if grupo is not None:
            assert leitura.stat().st_gid == grupo, (
                "a leitura é de quem chamou o sudo: sem o chown, o comparar sem root não a lê"
            )
        texto = leitura.read_text(encoding="utf-8")
        assert "1 report(s) 0x31 de saída" in texto, texto
        assert "11 22 33" in texto, texto
        assert "CHAVE-DE-MENTIRA" not in texto
        r = _rodar_lightbar(braco_limpo.dubles, braco_limpo.destino, "comparar")
        assert r.returncode == 0, r.stderr
        assert "11 22 33" in r.stdout
        assert "sem leitura" in r.stdout, "o braço sujo não rodou, e o comparar diz isso"

    def test_destino_que_e_link_e_recusado_antes_do_btmon(
        self, tmp_path: Path, dubles: Dubles
    ) -> None:
        alvo = tmp_path / "outro-lugar"
        alvo.mkdir()
        destino = tmp_path / "destino"
        destino.symlink_to(alvo)
        r = _rodar_lightbar(dubles, destino, "limpo", "1")
        assert r.returncode != 0
        assert "recuso" in r.stderr
        assert dubles.escritas() == [], "o btmon não pode rodar com o destino recusado"

    def test_destino_em_que_qualquer_um_escreve_e_recusado(
        self, tmp_path: Path, dubles: Dubles
    ) -> None:
        """Ali outro usuário troca a leitura por um link entre o ``rm`` e a escrita do root."""
        destino = tmp_path / "destino-aberto"
        destino.mkdir()
        destino.chmod(0o777)
        r = _rodar_lightbar(dubles, destino, "limpo", "1")
        assert r.returncode != 0
        assert "qualquer um escreve" in r.stderr, r.stderr
        assert dubles.escritas() == [], "o btmon não pode rodar com o destino recusado"


# ---------------------------------------------------------------------------
# scripts/medir_w3_coex.sh — tudo como root, três braços
# ---------------------------------------------------------------------------


@dataclass
class CorridaDoW3:
    dubles: Dubles
    relatorio: Path
    resultado: subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def corrida_do_w3(tmp_path_factory: pytest.TempPathFactory) -> CorridaDoW3:
    """Os três braços, UMA vez: cada corrida custa segundos de sono de mentira."""
    raiz = tmp_path_factory.mktemp("w3")
    dubles = _fazer_dubles(raiz)
    relatorio = raiz / "relatorio.txt"
    grupo = _grupo_secundario()
    amb = dubles.ambiente(
        SUDO_UID=str(os.getuid()),
        SUDO_GID=str(grupo if grupo is not None else os.getgid()),
    )
    resultado = subprocess.run(
        [BASH, str(W3), "--run", "--dur", "1", "--out", str(relatorio)],
        capture_output=True, text=True, check=False, env=amb, timeout=120,
    )
    return CorridaDoW3(dubles, relatorio, resultado)


class TestOW3GravaFechadoLeEApaga:
    def test_os_tres_bracos_nascem_0600_sao_lidos_0600_e_saem(
        self, corrida_do_w3: CorridaDoW3
    ) -> None:
        r = corrida_do_w3.resultado
        assert r.returncode == 0, r.stdout + r.stderr
        escritas = corrida_do_w3.dubles.escritas()
        assert len(escritas) == 3, escritas
        assert {modo for _, modo, _ in escritas} == {"0600"}, escritas
        assert {pasta for _, _, pasta in escritas} == {"0700"}, escritas
        leituras = corrida_do_w3.dubles.leituras()
        assert {c for c, _ in leituras} == {c for c, _, _ in escritas}
        assert {modo for _, modo in leituras} == {"0600"}, leituras
        texto = corrida_do_w3.relatorio.read_text(encoding="utf-8")
        for caminho, _, _ in escritas:
            assert not Path(caminho).exists(), f"{caminho} ficou no disco"
            assert f"{caminho} (lida e apagada)" in texto
        diretorios = {Path(c).parent for c, _, _ in escritas}
        assert len(diretorios) == 1
        assert not diretorios.pop().exists(), "a pasta das capturas ficou"
        assert "Hardware Error: 1" in texto, "o relatório leu a captura antes de apagá-la"
        assert corrida_do_w3.dubles.vizinhos() == [0, 0, 0], (
            "a captura de um braço ainda estava na pasta quando o seguinte começou: "
            "ela sai depois de lida, não só no fim"
        )

    def test_o_relatorio_e_de_quem_chamou_o_sudo(self, corrida_do_w3: CorridaDoW3) -> None:
        relatorio = corrida_do_w3.relatorio
        assert _modo(relatorio) == 0o600
        assert relatorio.stat().st_uid == os.getuid()
        grupo = _grupo_secundario()
        if grupo is not None:
            assert relatorio.stat().st_gid == grupo

    def test_o_wifi_continua_voltando(self, corrida_do_w3: CorridaDoW3) -> None:
        """A limpeza entrou no mesmo ``restaurar`` do ``rfkill unblock``; ele segue."""
        chamadas = corrida_do_w3.dubles.log_chamadas.read_text(encoding="utf-8").splitlines()
        rfkill = [c for c in chamadas if c.startswith("rfkill ")]
        assert rfkill == ["rfkill block wifi", "rfkill unblock wifi"], rfkill


def test_o_w3_interrompido_no_meio_nao_deixa_btmon_nem_download(tmp_path: Path) -> None:
    """Um ``kill`` no meio do braço B: o ``restaurar`` para o ``btmon`` e a carga.

    Sem isto o ``btmon`` do root seguia gravando num arquivo já apagado — invisível
    e crescendo, com a chave se um controle reconectasse — e o laço de download
    do braço B seguia baixando para sempre.
    """
    dubles = _fazer_dubles(tmp_path)
    amb = dubles.ambiente(SUDO_UID=str(os.getuid()), SUDO_GID=str(os.getgid()))
    processo = subprocess.Popen(
        [BASH, str(W3), "--run", "--dur", "30", "--out", str(tmp_path / "relatorio.txt")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=amb,
        start_new_session=True,
    )
    try:
        fim = time.monotonic() + 30
        while len(dubles.pids()) < 2 and processo.poll() is None:
            assert time.monotonic() < fim, "o braço B não começou"
            time.sleep(0.02)
        assert processo.poll() is None, "o W3 terminou antes do braço B"
        processo.send_signal(signal.SIGTERM)
        processo.wait(timeout=20)
        btmon_do_b = dubles.pids()[1]
        assert _morreu(btmon_do_b), "o btmon do braço B ficou gravando depois do kill"
        caminho_b = dubles.escritas()[1][0]
        assert not Path(caminho_b).parent.exists(), "a pasta das capturas ficou"
        time.sleep(0.3)
        antes = dubles.log_chamadas.read_text(encoding="utf-8").count("curl ")
        time.sleep(0.6)
        depois = dubles.log_chamadas.read_text(encoding="utf-8").count("curl ")
        assert antes > 0, "o braço B não chegou a baixar nada"
        assert depois == antes, "o laço de download do braço B seguiu depois do kill"
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(processo.pid, signal.SIGKILL)
        processo.wait(timeout=20)


# ---------------------------------------------------------------------------
# Os dois ensaios em Python — a usuária roda, só o btmon é root
# ---------------------------------------------------------------------------


def _carregar(nome: str) -> Any:
    """``scripts/ensaios/`` não é pacote — carrega pelo caminho, como os irmãos."""
    caminho = ENSAIOS / f"{nome}.py"
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    espec = importlib.util.spec_from_file_location(f"{nome}_capturas_fechadas", caminho)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


def _aparelho_de_mentira(tmp_path: Path) -> Any:
    """Um DualSense no rádio cuja barra de luz é um arquivo no ``tmp_path``."""
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    comum = importlib.import_module("comum")
    led = tmp_path / "device" / "leds" / "input99:rgb:indicator"
    led.mkdir(parents=True)
    (led / "multi_intensity").write_text("0 0 255\n", encoding="utf-8")
    return comum.Aparelho(
        hidraw="hidraw99",
        caminho_hidraw=str(tmp_path / "hidraw99"),
        dir_device=str(tmp_path / "device"),
        mac=MAC_DE_MENTIRA,
        nome="DualSense de mentira",
        transporte=comum.RADIO,
        e_vpad=False,
        rotulo="",
    )


class _Leitor:
    """Embrulha o ``ler_btsnoop``: anota o modo e o dono no instante da leitura."""

    def __init__(self, original: Any) -> None:
        self.original = original
        self.lidas: list[tuple[str, int]] = []

    def __call__(self, caminho: str) -> Any:
        try:
            modo = stat.S_IMODE(os.stat(caminho).st_mode)
        except FileNotFoundError:
            modo = -1  # não havia captura: quem lê tem de dizer isso, não morrer
        self.lidas.append((caminho, modo))
        return self.original(caminho)


def _preparar_ensaio(
    modulo: Any, tmp_path: Path, dubles: Dubles, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, _Leitor]:
    for var, valor in dubles.ambiente().items():
        monkeypatch.setenv(var, valor)
    monkeypatch.setattr(tempfile, "tempdir", str(dubles.tmp))
    aparelho = _aparelho_de_mentira(tmp_path)
    monkeypatch.setattr(modulo, "cabecalho_do_instrumento", lambda *a, **k: "cabeçalho")
    monkeypatch.setattr(modulo, "descobrir_aparelhos", lambda: [aparelho])
    monkeypatch.setattr(modulo, "handles_por_mac", lambda: ({MAC_DE_MENTIRA: HANDLE}, "dublê"))
    leitor = _Leitor(modulo.ler_btsnoop)
    monkeypatch.setattr(modulo, "ler_btsnoop", leitor)
    return aparelho, leitor


def _conferir_o_ciclo(dubles: Dubles, leitor: _Leitor, saida: str) -> None:
    (caminho, modo, modo_da_pasta), = dubles.escritas()
    assert modo == "0600", f"a captura nasceu {modo}; tem de nascer 0600"
    assert modo_da_pasta == "0700", f"a pasta da captura é {modo_da_pasta}"
    assert leitor.lidas == [(caminho, 0o600)], (
        "a captura foi lida com "
        + ", ".join(f"{modo_lido:04o}" for _, modo_lido in leitor.lidas)
        + "; tem de continuar 0600 até a leitura"
    )
    entregas = [
        linha for linha in dubles.log_sudo.read_text(encoding="utf-8").splitlines()
        if "chown" in linha and caminho in linha
    ]
    assert entregas, "a captura não foi entregue a quem mede (sem chown)"
    assert f"{os.getuid()}:{os.getgid()}" in entregas[0]
    assert not Path(caminho).exists(), "a captura ficou no disco depois de lida"
    assert not Path(caminho).parent.exists(), "o diretório da captura ficou"
    assert f"captura: {caminho}  (lida e apagada)" in saida


class TestOsEnsaiosGravamFechadoLeemEApagam:
    def test_o_byte_no_fio(
        self, tmp_path: Path, dubles: Dubles, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        modulo = _carregar("byte_no_fio")
        _, leitor = _preparar_ensaio(modulo, tmp_path, dubles, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["byte_no_fio.py", "--segundos", "0.05"])
        assert modulo.main() == 0
        _conferir_o_ciclo(dubles, leitor, capsys.readouterr().out)

    def test_a_captura_armada(
        self, tmp_path: Path, dubles: Dubles, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        modulo = _carregar("a_captura_armada_do_som_no_radio")
        _, leitor = _preparar_ensaio(modulo, tmp_path, dubles, monkeypatch)
        monkeypatch.setattr(
            modulo, "escutar_o_hidraw", lambda *a, **k: modulo.LeituraDoHidraw()
        )
        assert modulo.main(["--exigir-mac", MAC_DE_MENTIRA, "--segundos", "0.1"]) == 0
        _conferir_o_ciclo(dubles, leitor, capsys.readouterr().out)

    def test_apagar_com_o_btmon_de_pe_para_e_apaga(
        self, dubles: Dubles, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho do ``atexit``: o instrumento caiu antes do ``encerrar``.

        O ``apagar`` sozinho para o ``btmon`` e tira a captura e a pasta.
        """
        for var, valor in dubles.ambiente().items():
            monkeypatch.setenv(var, valor)
        monkeypatch.setattr(tempfile, "tempdir", str(dubles.tmp))
        modulo = _carregar("byte_no_fio")
        sinal_antes = signal.getsignal(signal.SIGTERM)
        captura = modulo.CapturaDoFio("cai-no-meio")
        captura.comecar()
        try:
            for _ in range(100):
                if dubles.escritas():
                    break
                time.sleep(0.05)
            assert Path(captura.caminho).exists()
        finally:
            linha = captura.apagar()
        assert not Path(captura.caminho).exists()
        assert not Path(captura.diretorio).exists()
        assert "(lida e apagada)" in linha
        (pid,) = dubles.pids()
        assert _morreu(pid), "o apagar tirou a captura e deixou o btmon gravando"
        assert signal.getsignal(signal.SIGTERM) == sinal_antes, (
            "o apagar tem de devolver o SIGTERM que havia antes da captura"
        )

    def test_sem_sudo_o_byte_no_fio_diz_que_nao_capturou(
        self, tmp_path: Path, dubles: Dubles, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """O ``sudo -n`` que pede senha: «não medi», e não um traceback nem «lida».

        Até 24/09 o arquivo vazio do ``mkstemp`` ficava e virava queixa do parser;
        com a captura nascendo pelas mãos do root, ele não existe mais.
        """
        _executavel(dubles.bin / "sudo", (
            "#!/bin/bash\n"
            "printf 'recusado %s\\n' \"$*\" >> \"$SUDO_DE_MENTIRA_LOG\"\n"
            "echo 'sudo: a password is required' >&2\n"
            "exit 1\n"
        ))
        modulo = _carregar("byte_no_fio")
        _preparar_ensaio(modulo, tmp_path, dubles, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["byte_no_fio.py", "--segundos", "0.05"])
        assert modulo.main() == 0
        saida = capsys.readouterr().out
        assert dubles.escritas() == []
        assert "saiu sozinho (rc=1)" in saida, saida
        assert "captura ilegível" in saida, saida
        assert "INSTRUMENTO QUEBRADO" in saida, saida
        assert "(o btmon não gravou nada ali)" in saida, saida
        assert "(lida e apagada)" not in saida, "a saída diz que leu uma captura que não existiu"
        assert not list(dubles.tmp.glob("byte-no-fio-*")), "a pasta da captura ficou"

    @pytest.mark.parametrize("nome", ["byte_no_fio", "a_captura_armada_do_som_no_radio"])
    def test_a_entrega_que_falha_vira_queixa_nos_dois_ensaios(
        self, tmp_path: Path, dubles: Dubles, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], nome: str,
    ) -> None:
        """O ``sudo`` venceu no meio (a captura armada espera minutos): o relatório diz.

        O ``btmon`` de mentira grava como quem mede, então a leitura ainda passa;
        o que se confere é que os DOIS chamadores levam a queixa do ciclo à saída.
        """
        _executavel(dubles.bin / "sudo", _SUDO.replace(
            'printf \'%s\\n\' "$*" >> "$SUDO_DE_MENTIRA_LOG"\n',
            'printf \'%s\\n\' "$*" >> "$SUDO_DE_MENTIRA_LOG"\n'
            'case "$*" in *chown*) echo "sudo: a password is required" >&2; exit 1 ;; esac\n',
        ))
        assert "*chown*" in (dubles.bin / "sudo").read_text(encoding="utf-8")
        modulo = _carregar(nome)
        _preparar_ensaio(modulo, tmp_path, dubles, monkeypatch)
        if nome == "byte_no_fio":
            monkeypatch.setattr(sys, "argv", ["byte_no_fio.py", "--segundos", "0.05"])
            assert modulo.main() == 0
        else:
            monkeypatch.setattr(
                modulo, "escutar_o_hidraw", lambda *a, **k: modulo.LeituraDoHidraw()
            )
            assert modulo.main(["--exigir-mac", MAC_DE_MENTIRA, "--segundos", "0.1"]) == 0
        saida = capsys.readouterr().out
        assert "a captura não foi entregue a quem mede (rc=1)" in saida, saida
        (caminho, _, _), = dubles.escritas()
        assert not Path(caminho).parent.exists(), "a pasta da captura ficou"


_CAI_NO_MEIO = """\
import os, sys, time
sys.path.insert(0, {ensaios!r})
import byte_no_fio
captura = byte_no_fio.CapturaDoFio("cai-no-meio")
captura.comecar()
for _ in range(200):
    if os.path.exists(captura.caminho):
        break
    time.sleep(0.02)
print(captura.caminho, captura._processo.pid, flush=True)
if sys.argv[1] == "excecao":
    raise RuntimeError("o instrumento caiu no meio")
time.sleep(60)
"""


@pytest.mark.parametrize("como", ["excecao", "sigterm", "sighup"])
def test_o_instrumento_que_cai_no_meio_apaga_e_para_o_btmon(
    tmp_path: Path, dubles: Dubles, como: str
) -> None:
    """Uma exceção, um ``kill`` ou o terminal que fecha: a captura sai e o ``btmon`` para.

    A exceção sai pelo ``atexit``; os dois sinais, que matariam o Python sem
    ``atexit``, viram ``SystemExit`` enquanto a captura vive.
    """
    script = tmp_path / "cai_no_meio.py"
    script.write_text(_CAI_NO_MEIO.format(ensaios=str(ENSAIOS)), encoding="utf-8")
    processo = subprocess.Popen(
        [sys.executable, str(script), como],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=dubles.ambiente(PYTHONPATH=str(REPO_ROOT / "src")),
        start_new_session=True,
    )
    try:
        assert processo.stdout is not None
        caminho, pid_do_btmon = processo.stdout.readline().split()
        assert Path(caminho).exists(), "o btmon de mentira não gravou"
        if como != "excecao":
            processo.send_signal(signal.SIGTERM if como == "sigterm" else signal.SIGHUP)
        _, erro = processo.communicate(timeout=30)
        assert processo.returncode != 0, erro
        assert not Path(caminho).exists(), f"a captura ficou depois de {como}"
        assert not Path(caminho).parent.exists(), f"a pasta da captura ficou depois de {como}"
        assert _morreu(int(pid_do_btmon)), f"o btmon seguiu gravando depois de {como}"
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(processo.pid, signal.SIGKILL)
        processo.wait(timeout=20)


# ---------------------------------------------------------------------------
# O formato: um dono só, e ele roda como root
# ---------------------------------------------------------------------------


class TestOFormatoLeOBinarioESoUsaABibliotecaPadrao:
    def test_a_leitura_acha_o_report_e_nao_a_chave(self, tmp_path: Path) -> None:
        captura = tmp_path / "captura.btsnoop"
        captura.write_bytes(_captura_de_mentira())
        formato = _carregar("o_formato_btsnoop")
        texto = formato.texto_dos_reports_de_saida(str(captura))
        linhas = texto.splitlines()
        assert linhas[0].strip() == "1 report(s) 0x31 de saída, 1 distinto(s)", texto
        assert [str(HANDLE), "1", "0x04", "0x02", "0x02", "11", "22", "33"] in [
            linha.split() for linha in linhas
        ], texto
        assert "CHAVE" not in texto

    def test_a_leitura_guarda_o_report_inteiro(self, tmp_path: Path) -> None:
        """A captura crua sai depois de lida: o que não está na leitura não volta.

        O 0x31 de saída não leva chave nem endereço, então ela o guarda byte a byte.
        """
        captura = tmp_path / "captura.btsnoop"
        captura.write_bytes(_captura_de_mentira())
        formato = _carregar("o_formato_btsnoop")
        texto = formato.texto_dos_reports_de_saida(str(captura))
        assert f"handle {HANDLE} · 1 quadro(s) · 78 bytes:" in texto, texto
        assert "  0: 31 00 00 00 04 00" in texto, texto
        assert " 48: 22 33 00" in texto, texto

    def test_captura_que_nao_existe_vira_queixa(self, tmp_path: Path) -> None:
        formato = _carregar("o_formato_btsnoop")
        quadros, queixas = formato.ler_btsnoop(str(tmp_path / "nao-existe.btsnoop"))
        assert quadros == []
        assert len(queixas) == 1 and queixas[0].startswith("captura ilegível"), queixas

    def test_so_importa_a_biblioteca_padrao(self) -> None:
        """A lightbar o roda como root: nada da casa pode vir junto."""
        arvore = ast.parse((ENSAIOS / "o_formato_btsnoop.py").read_text(encoding="utf-8"))
        nomes: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes.update(a.name.split(".")[0] for a in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes.add(no.module.split(".")[0])
        de_fora = sorted(nomes - set(sys.stdlib_module_names))
        assert de_fora == [], f"o formato importa {de_fora}; como root, só a biblioteca padrão"
