"""Units systemd do broker root hide-hidraw (BROKER-01) — desenho 2026-07-20 §5.

Guarda de regressão das DUAS mudanças estruturais vs o parkado + o hardening:
- `RuntimeDirectory` NÃO PODE voltar ao .service (lição 4/#10: é apagado em
  TODO stop/crash e levava o broker.sock junto — a lease nunca renascia); a
  DONA do diretório/socket é a SOCKET UNIT;
- `DeviceAllow=char-hidraw rw` PRECISA existir (o cmd open faz open(2) O_RDWR
  real; `char-hidraw` resolve o major dinâmico pelo nome em /proc/devices);
- `PrivateDevices` e `udevadm` seguem proibidos; o resto do hardening é exato.

Também prova o executável standalone (stdlib pura, roda no python3 do sistema,
falha explícita sem uid autorizado E com uid 0 — lição 6) e os placeholders
que o install renderiza (uid no .service, grupo no .socket, nunca cruzados).

Os checks de install.sh/uninstall.sh/doctor (simetria) pertencem ao lote B3 —
aqui só o que o lote B1 entrega (broker core + units).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = REPO_ROOT / "assets" / "systemd" / "hefesto-hidraw-broker.service"
SOCKET = REPO_ROOT / "assets" / "systemd" / "hefesto-hidraw-broker.socket"
BROKER_PY = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "broker" / "hidraw_broker.py"


@pytest.fixture(scope="module")
def service_text() -> str:
    return SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def socket_text() -> str:
    return SOCKET.read_text(encoding="utf-8")


def _directives(text: str) -> dict[str, list[str]]:
    """Chave=valor das units (repetíveis: lista por chave), sem comentários."""
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "[", ";")):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), []).append(value.strip())
    return out


class TestSocketUnit:
    def test_existe_e_escuta_no_run(self, socket_text: str) -> None:
        d = _directives(socket_text)
        assert d["ListenStream"] == ["/run/hefesto-hidraw-broker/broker.sock"]

    def test_accept_no_para_o_fail_safe_por_eof(self, socket_text: str) -> None:
        # Accept=no: UMA instância faz accept() ela mesma — a conexão do
        # daemon é a lease e o EOF dela dispara o restore.
        d = _directives(socket_text)
        assert d["Accept"] == ["no"]

    def test_dac_do_socket(self, socket_text: str) -> None:
        d = _directives(socket_text)
        assert d["SocketMode"] == ["0660"]
        assert d["SocketUser"] == ["root"]
        assert d["SocketGroup"] == ["__SESSION_GROUP__"]  # renderizado no install
        assert d["DirectoryMode"] == ["0755"]

    def test_socket_unit_e_a_dona_do_diretorio(self, socket_text: str) -> None:
        # Lição 4/#10: quem cria /run/hefesto-hidraw-broker é a SOCKET unit
        # (DirectoryMode do ListenStream) — o comentário documenta a posse e
        # nenhuma diretiva delega o diretório ao serviço.
        assert "DONA do diretório" in socket_text
        d = _directives(socket_text)
        assert "RuntimeDirectory" not in d

    def test_wantedby_sockets_target(self, socket_text: str) -> None:
        assert _directives(socket_text)["WantedBy"] == ["sockets.target"]


class TestServiceHardening:
    def test_diretivas_proibidas_nao_entram(self, service_text: str) -> None:
        # PrivateDevices=yes daria um /dev SEM hidraw (chmod/open → ENOENT);
        # RuntimeDirectory apagaria o broker.sock em todo stop/crash do
        # serviço (lição 4/#10 — a socket unit é a dona do caminho);
        # udevadm escreveria em /sys (conflita com ProtectKernelTunables).
        d = _directives(service_text)
        assert "PrivateDevices" not in d, "PrivateDevices quebraria chmod/open em /dev/hidraw*"
        assert "RuntimeDirectory" not in d, "RuntimeDirectory apaga o socket da lease (lição 4)"
        assert "RuntimeDirectoryMode" not in d
        assert not any("udevadm" in valor for valores in d.values() for valor in valores)

    def test_device_allow_do_cmd_open(self, service_text: str) -> None:
        # O delta estrutural vs 2026-07-18: o broker AGORA abre device (cmd
        # open). closed + allow SÓ char-hidraw, rw (o fd servido é O_RDWR —
        # `r` faria o open falhar com EPERM); pelo NOME do grupo (major do
        # hidraw é dinâmico — um numérico quebraria em kernel novo).
        d = _directives(service_text)
        assert d["DevicePolicy"] == ["closed"]
        assert d["DeviceAllow"] == ["char-hidraw rw"]

    def test_hardening_exato_do_desenho(self, service_text: str) -> None:
        d = _directives(service_text)
        esperado = {
            "User": ["root"],
            "NoNewPrivileges": ["yes"],
            "ProtectSystem": ["strict"],
            "ProtectHome": ["yes"],
            "PrivateTmp": ["yes"],
            "PrivateNetwork": ["yes"],
            "RestrictAddressFamilies": ["AF_UNIX"],
            "ProtectKernelTunables": ["yes"],
            "ProtectKernelModules": ["yes"],
            "ProtectKernelLogs": ["yes"],
            "ProtectControlGroups": ["yes"],
            "ProtectClock": ["yes"],
            "ProtectHostname": ["yes"],
            "ProtectProc": ["invisible"],
            "ProcSubset": ["pid"],  # mantém /proc/self/fd (operações pinadas)
            "RestrictNamespaces": ["yes"],
            "RestrictRealtime": ["yes"],
            "RestrictSUIDSGID": ["yes"],
            "LockPersonality": ["yes"],
            "MemoryDenyWriteExecute": ["yes"],
            "RemoveIPC": ["yes"],
            "UMask": ["0077"],
            "SystemCallArchitectures": ["native"],
            "DevicePolicy": ["closed"],
            "AmbientCapabilities": [""],
        }
        for chave, valor in esperado.items():
            assert d.get(chave) == valor, f"{chave}: esperado {valor}, veio {d.get(chave)}"

    def test_syscall_filter_e_capabilities(self, service_text: str) -> None:
        # sendmsg com SCM_RIGHTS é @network-io ∈ @system-service — nenhum
        # filtro extra é necessário para ancillary (verificado no desenho §5.3).
        d = _directives(service_text)
        negados = (
            "~@privileged @resources @mount @debug @cpu-emulation "
            "@obsolete @raw-io @reboot @swap @clock"
        )
        assert d["SystemCallFilter"] == ["@system-service", negados]
        assert d["CapabilityBoundingSet"] == [
            "CAP_FOWNER CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH"
        ]

    def test_socket_activation_e_fail_safe(self, service_text: str) -> None:
        d = _directives(service_text)
        assert d["Type"] == ["notify"]
        assert d["Requires"] == ["hefesto-hidraw-broker.socket"]
        assert d["ExecStart"] == ["/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"]
        # Baseline limpo + belt final: os DOIS lados do restore-all.
        assert d["ExecStartPre"] == [
            "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker --restore-all-and-exit"
        ]
        assert d["ExecStopPost"] == [
            "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker --restore-all-and-exit"
        ]
        assert d["Environment"] == ["HEFESTO_BROKER_ALLOWED_UID=__SESSION_UID__"]
        assert d["Restart"] == ["on-failure"]

    def test_header_de_posse_para_o_uninstall(
        self, service_text: str, socket_text: str
    ) -> None:
        # Registro de posse (§7): o uninstall só remove unit que carrega o
        # nosso header — nunca toca unit de terceiros.
        for texto in (service_text, socket_text):
            assert "instalado por hefesto-dualsense4unix (install.sh)" in texto


class TestBrokerStandalone:
    def test_stdlib_pura_sem_import_do_pacote(self) -> None:
        # O install copia SÓ este arquivo para /usr/local/lib — qualquer
        # import do pacote quebraria o broker no python3 do sistema.
        texto = BROKER_PY.read_text(encoding="utf-8")
        assert "hefesto_dualsense4unix" not in re.sub(r'"""[\s\S]*?"""', "", texto, count=1)
        assert "import pydualsense" not in texto

    def test_executa_standalone_e_recusa_sem_uid(self, tmp_path: Path) -> None:
        # Rodado FORA do pacote (cwd neutro), sem HEFESTO_BROKER_ALLOWED_UID:
        # falha explícita (exit 1) — install quebrado nunca vira broker mudo.
        resultado = subprocess.run(
            [sys.executable, str(BROKER_PY), "--restore-all-and-exit"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        assert resultado.returncode == 1
        assert "allowed_uid_missing" in resultado.stdout

    def test_recusa_uid_zero(self, tmp_path: Path) -> None:
        # Lição 6: ALLOWED_UID nunca pode ser root — render errado (install
        # sem sessão) tem de falhar explícito, nunca virar broker de uid 0.
        resultado = subprocess.run(
            [sys.executable, str(BROKER_PY), "--restore-all-and-exit"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin", "HEFESTO_BROKER_ALLOWED_UID": "0"},
            timeout=30,
        )
        assert resultado.returncode == 1
        assert "allowed_uid_root_recusado" in resultado.stdout

    def test_help_funciona(self, tmp_path: Path) -> None:
        resultado = subprocess.run(
            [sys.executable, str(BROKER_PY), "--help"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        assert resultado.returncode == 0
        assert "--restore-all-and-exit" in resultado.stdout


class TestPlaceholders:
    def test_placeholders_por_arquivo_nunca_cruzados(
        self, service_text: str, socket_text: str
    ) -> None:
        # O sed do install renderiza EXATAMENTE estes placeholders (por
        # ARQUIVO: uid no .service, grupo no .socket); um cruzado deixaria a
        # unit com o literal __X__ (uid/grupo inválido) em produção.
        d_service = _directives(service_text)
        d_socket = _directives(socket_text)
        valores_service = [v for vals in d_service.values() for v in vals]
        valores_socket = [v for vals in d_socket.values() for v in vals]
        assert sum("__SESSION_UID__" in v for v in valores_service) == 1
        assert sum("__SESSION_GROUP__" in v for v in valores_socket) == 1
        assert not any("__SESSION_GROUP__" in v for v in valores_service)
        assert not any("__SESSION_UID__" in v for v in valores_socket)
