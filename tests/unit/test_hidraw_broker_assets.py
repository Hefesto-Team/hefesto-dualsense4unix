"""Units systemd do broker root hide-hidraw (BROKER-01) — desenho 2026-07-20 §5."""
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
HOST_UDEV = REPO_ROOT / "scripts" / "install-host-udev.sh"


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
        d = _directives(socket_text)
        assert d["Accept"] == ["no"]

    def test_dac_do_socket(self, socket_text: str) -> None:
        d = _directives(socket_text)
        assert d["SocketMode"] == ["0660"]
        assert d["SocketUser"] == ["root"]
        assert d["SocketGroup"] == ["__SESSION_GROUP__"]
        assert d["DirectoryMode"] == ["0755"]

    def test_socket_unit_e_a_dona_do_diretorio(self, socket_text: str) -> None:
        assert "DONA do diretório" in socket_text
        d = _directives(socket_text)
        assert "RuntimeDirectory" not in d

    def test_wantedby_sockets_target(self, socket_text: str) -> None:
        assert _directives(socket_text)["WantedBy"] == ["sockets.target"]


class TestServiceHardening:
    def test_diretivas_proibidas_nao_entram(self, service_text: str) -> None:
        d = _directives(service_text)
        assert "PrivateDevices" not in d, "PrivateDevices quebraria chmod/open em /dev/hidraw*"
        assert "RuntimeDirectory" not in d, "RuntimeDirectory apaga o socket da lease (lição 4)"
        assert "RuntimeDirectoryMode" not in d
        assert not any("udevadm" in valor for valores in d.values() for valor in valores)

    def test_device_allow_do_cmd_open(self, service_text: str) -> None:
        d = _directives(service_text)
        assert d["DevicePolicy"] == ["closed"]
        assert d["DeviceAllow"] == ["char-hidraw rw", "char-input rw"]

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
            "ProcSubset": ["pid"],
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
        assert d["ExecStartPre"] == [
            "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker --fechar-tudo-e-sair"
        ]
        assert d["ExecStopPost"] == [
            "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker --restore-all-and-exit"
        ]
        assert d["Environment"] == [
            "HEFESTO_BROKER_ALLOWED_UID=__SESSION_UID__",
            "HEFESTO_BROKER_NO_NASCE_FECHADO=__NO_NASCE_FECHADO__",
        ]
        assert d["Restart"] == ["on-failure"]

    def test_header_de_posse_para_o_uninstall(
        self, service_text: str, socket_text: str
    ) -> None:
        for texto in (service_text, socket_text):
            assert "instalado por hefesto-dualsense4unix (install.sh)" in texto


class TestBrokerStandalone:
    def test_stdlib_pura_sem_import_do_pacote(self) -> None:
        texto = BROKER_PY.read_text(encoding="utf-8")
        assert "hefesto_dualsense4unix" not in re.sub(r'"""[\s\S]*?"""', "", texto, count=1)
        assert "import pydualsense" not in texto

    def test_executa_standalone_e_recusa_sem_uid(self, tmp_path: Path) -> None:
        resultado = subprocess.run(
            [
                sys.executable,
                str(BROKER_PY),
                "--restore-all-and-exit",
                "--unit-path",
                str(tmp_path / "inexistente.service"),
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        assert resultado.returncode == 1
        assert "allowed_uid_missing" in resultado.stdout

    def test_recusa_uid_zero(self, tmp_path: Path) -> None:
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

    def test_belt_parseia_uid_da_unit_instalada(self, tmp_path: Path) -> None:
        unit = tmp_path / "hefesto-hidraw-broker.service"
        unit.write_text(
            "[Service]\nEnvironment=HEFESTO_BROKER_ALLOWED_UID=0\n",
            encoding="utf-8",
        )
        resultado = subprocess.run(
            [
                sys.executable,
                str(BROKER_PY),
                "--restore-all-and-exit",
                "--unit-path",
                str(unit),
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        assert resultado.returncode == 1
        assert "allowed_uid_from_unit" in resultado.stdout
        assert "allowed_uid_root_recusado" in resultado.stdout

    def test_belt_flag_allowed_uid_vence_o_parse_da_unit(
        self, tmp_path: Path
    ) -> None:
        resultado = subprocess.run(
            [
                sys.executable,
                str(BROKER_PY),
                "--restore-all-and-exit",
                "--allowed-uid",
                "0",
                "--unit-path",
                str(tmp_path / "inexistente.service"),
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin"},
            timeout=30,
        )
        assert resultado.returncode == 1
        assert "allowed_uid_root_recusado" in resultado.stdout
        assert "allowed_uid_from_unit" not in resultado.stdout

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
        d_service = _directives(service_text)
        d_socket = _directives(socket_text)
        valores_service = [v for vals in d_service.values() for v in vals]
        valores_socket = [v for vals in d_socket.values() for v in vals]
        assert sum("__SESSION_UID__" in v for v in valores_service) == 1
        assert sum("__SESSION_GROUP__" in v for v in valores_socket) == 1
        assert not any("__SESSION_GROUP__" in v for v in valores_service)
        assert not any("__SESSION_UID__" in v for v in valores_socket)


class TestParseAllowedUidDaUnit:
    """S-3 (auditoria 21/07): parse do uid na unit instalada (fallback do belt)."""

    def test_uid_valido(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.broker.hidraw_broker import (
            _parse_allowed_uid_from_unit,
        )

        unit = tmp_path / "u.service"
        unit.write_text(
            "[Unit]\nDescription=x\n[Service]\n"
            "Environment=HEFESTO_BROKER_ALLOWED_UID=1000\n",
            encoding="utf-8",
        )
        assert _parse_allowed_uid_from_unit(str(unit)) == 1000

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.broker.hidraw_broker import (
            _parse_allowed_uid_from_unit,
        )

        assert _parse_allowed_uid_from_unit(str(tmp_path / "nada.service")) is None

    def test_linha_ausente_ou_malformada(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.broker.hidraw_broker import (
            _parse_allowed_uid_from_unit,
        )

        unit = tmp_path / "u.service"
        unit.write_text(
            "[Service]\nEnvironment=HEFESTO_BROKER_ALLOWED_UID=__SESSION_UID__\n",
            encoding="utf-8",
        )
        assert _parse_allowed_uid_from_unit(str(unit)) is None
        unit.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
        assert _parse_allowed_uid_from_unit(str(unit)) is None


class TestRenderSeguroHostUdev:
    """S-1 (auditoria 21/07): o render das units no comando elevado do"""

    def test_render_usa_mktemp_e_nao_caminho_fixo_de_tmp(self) -> None:
        texto = HOST_UDEV.read_text(encoding="utf-8")
        assert "mktemp -d" in texto
        assert "> /tmp/hefesto-hidraw-broker.service.render" not in texto
        assert "> /tmp/hefesto-hidraw-broker.socket.render" not in texto
        assert not re.search(r">\s*/tmp/[^\"$]", texto)
