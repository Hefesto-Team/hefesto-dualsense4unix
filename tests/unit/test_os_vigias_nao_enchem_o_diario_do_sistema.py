"""Os vigias não enchem o diário do sistema (07/11/2026).

Medido em 24 h: 1.478 linhas iguais de «bond em disco sem objeto D-Bus» e mais de 5.800 de início e
fim dos timers de minuto. A frase agora sai uma vez por adaptador, e de novo quando muda, com a
memória em ``STAMP_DIR``. O início e o fim são info e saem com ``LogLevelMax=notice``; o
``SyslogLevel=notice`` é o que segura a saída dos scripts, que nasce info e cairia junto.

MORDIDA: voltar a frase por aparelho, tirar a memória ou tirar o ``SyslogLevel`` reprova.
"""
from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
VIGIA = RAIZ / "scripts" / "bt_health_watchdog.sh"
_UNITS = ("hefesto-bt-health-watchdog.service", "hefesto-wifi-usb-vigia.service")
_FRASE = "sem objeto D-Bus"
_ADAPTADORES = ("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02")


def _bond(raiz: Path, adaptador: str, final: str) -> None:
    pasta = raiz / adaptador / f"AA:BB:CC:00:01:{final}"
    pasta.mkdir(parents=True)
    (pasta / "info").write_text(
        "[General]\nName=DualSense\nServices=00001124-0000-1000-8000-00805f9b34fb;\n",
        encoding="utf-8")


def _executavel(arquivo: Path, corpo: str) -> None:
    arquivo.write_text(f"#!/usr/bin/env bash\n{corpo}", encoding="utf-8")
    arquivo.chmod(0o755)


class Banca:
    def __init__(self, pasta: Path) -> None:
        self.bonds = pasta / "bonds"
        self.bonds.mkdir()
        self.arvore = pasta / "arvore"
        self.arvore.write_text("", encoding="utf-8")
        binarios = pasta / "bin"
        binarios.mkdir()
        _executavel(binarios / "busctl", f'''case "$1" in
    status) exit 0 ;;
    tree) cat "{self.arvore}" ;;
    get-property) echo "b false" ;;
esac
''')
        self.ambiente = {
            **os.environ,
            "PATH": f"{binarios}{os.pathsep}{os.environ['PATH']}",
            "HEFESTO_BT_SRC": str(self.bonds),
            "HEFESTO_BT_STAMP_DIR": str(pasta / "memoria"),
            "HEFESTO_BT_LOG_DEST": "none",
            "HEFESTO_HIDRAW_ROOT": str(pasta / "hidraw"),
        }
        self.ambiente.pop("SUDO_UID", None)
        self.ambiente.pop("SUDO_USER", None)

    def rodar(self) -> list[str]:
        saida = subprocess.run(["bash", str(VIGIA), "--sdp-cache-only"], capture_output=True,
                               text=True, timeout=60, check=False, env=self.ambiente)
        assert saida.returncode == 0, saida.stderr
        return [linha for linha in saida.stdout.splitlines() if _FRASE in linha]


@pytest.fixture
def banca(tmp_path: Path) -> Banca:
    return Banca(tmp_path)


def test_duas_voltas_seguidas_dizem_uma_linha_por_adaptador(banca: Banca) -> None:
    for adaptador in _ADAPTADORES:
        _bond(banca.bonds, adaptador, "01")
        _bond(banca.bonds, adaptador, "02")
    primeira = banca.rodar()
    assert len(primeira) == 2, primeira
    assert all("2 bond(s)" in linha for linha in primeira), primeira
    assert banca.rodar() == []


def test_o_que_muda_se_diz_de_novo_so_do_adaptador_que_mudou(banca: Banca) -> None:
    for adaptador in _ADAPTADORES:
        _bond(banca.bonds, adaptador, "01")
    banca.rodar()
    _bond(banca.bonds, _ADAPTADORES[1], "02")
    novas = banca.rodar()
    assert len(novas) == 1, novas
    assert _ADAPTADORES[1] in novas[0] and "2 bond(s)" in novas[0]


def test_o_adaptador_que_volta_e_cai_de_novo_se_diz_de_novo(banca: Banca) -> None:
    _bond(banca.bonds, _ADAPTADORES[0], "01")
    assert len(banca.rodar()) == 1
    banca.arvore.write_text("/org/bluez/hci0/dev_AA_BB_CC_00_01_01\n", encoding="utf-8")
    assert banca.rodar() == []
    banca.arvore.write_text("", encoding="utf-8")
    assert len(banca.rodar()) == 1


@pytest.mark.parametrize("unit", _UNITS)
def test_a_unit_cala_o_inicio_e_o_fim_sem_calar_o_aviso(unit: str) -> None:
    leitor = configparser.RawConfigParser(strict=False)
    leitor.read(RAIZ / "assets" / "systemd" / unit, encoding="utf-8")
    assert leitor.get("Service", "LogLevelMax") == "notice"
    assert leitor.get("Service", "SyslogLevel") == "notice"
