"""Assets do FastConnectable do BlueZ (PLAT-04 item 3).

Estudo 2026-07-18-estudo-bt-maximo.md §3/§7 item 5. DUAS formas, ambas em
``assets/bluetooth/`` — a lane de wiring escolhe conforme o BlueZ da máquina:

- ``hefesto-fastconnectable.conf``: drop-in p/ /etc/bluetooth/main.conf.d/
  (SE o BlueZ suportar o diretório; o 5.72 do Pop!_OS 24.04 NÃO tem);
- ``hefesto-fastconnectable.block``: bloco marcado com sentinelas para apensar
  ao /etc/bluetooth/main.conf (conffile dpkg → backup + idempotência).

ARMADILHA respeitada: NUNCA reiniciar o bluetoothd no install (derruba os
controles BT conectados — provado ao vivo em 2026-07-17). Os assets são
estáticos e devem AVISAR isso no texto.
"""
from __future__ import annotations

import configparser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DROPIN_PATH = REPO_ROOT / "assets" / "bluetooth" / "hefesto-fastconnectable.conf"
BLOCK_PATH = REPO_ROOT / "assets" / "bluetooth" / "hefesto-fastconnectable.block"

SENTINEL_OPEN = "# >>> hefesto FastConnectable >>>"
SENTINEL_CLOSE = "# <<< hefesto FastConnectable <<<"


@pytest.fixture(scope="module")
def dropin_text() -> str:
    return DROPIN_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def block_text() -> str:
    return BLOCK_PATH.read_text(encoding="utf-8")


def test_arquivos_existem() -> None:
    assert DROPIN_PATH.is_file(), f"drop-in ausente em {DROPIN_PATH}"
    assert BLOCK_PATH.is_file(), f"bloco marcado ausente em {BLOCK_PATH}"


class TestDropIn:
    def test_parseia_como_keyfile_com_general(self, dropin_text: str) -> None:
        parser = configparser.ConfigParser()
        parser.read_string(dropin_text)
        assert parser.get("General", "FastConnectable") == "true"

    def test_linha_exata_fastconnectable(self, dropin_text: str) -> None:
        ativos = [
            ln.strip()
            for ln in dropin_text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        ]
        assert ativos == ["[General]", "FastConnectable=true"], (
            f"esperado só [General] + FastConnectable=true, veio: {ativos}"
        )

    def test_avisa_que_nao_reinicia_o_bluetoothd(self, dropin_text: str) -> None:
        assert "restart" in dropin_text.lower(), (
            "documentar que o install NUNCA força restart do bluetoothd"
        )


class TestBlocoMarcado:
    def test_sentinelas_exatas_abrem_e_fecham(self, block_text: str) -> None:
        linhas = block_text.splitlines()
        assert linhas[0] == SENTINEL_OPEN, "1ª linha deve ser a sentinela de abertura"
        assert linhas[-1] == SENTINEL_CLOSE, "última linha deve ser a de fechamento"
        assert block_text.count(SENTINEL_OPEN) == 1
        assert block_text.count(SENTINEL_CLOSE) == 1

    def test_contem_general_e_fastconnectable(self, block_text: str) -> None:
        ativos = [
            ln.strip()
            for ln in block_text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        ]
        assert ativos == ["[General]", "FastConnectable=true"]

    def test_general_duplicado_e_seguro_no_keyfile(self, block_text: str) -> None:
        """Simula o apenso ao fim de um main.conf real: grupos [General]
        repetidos precisam FUNDIR (comportamento do GKeyFile, provado ao vivo
        2026-07-18) — configparser é mais estrito, então testamos a semântica
        com um parser tolerante a duplicatas."""
        main_conf = "[General]\n\n[Policy]\nAutoEnable=true\n"
        combinado = main_conf + "\n" + block_text
        parser = configparser.ConfigParser(strict=False)
        parser.read_string(combinado)
        assert parser.get("General", "FastConnectable") == "true"
        assert parser.get("Policy", "AutoEnable") == "true"

    def test_documenta_uninstall_pelas_sentinelas(self, block_text: str) -> None:
        assert "uninstall" in block_text.lower()
        assert "backup" in block_text.lower(), (
            "main.conf é conffile do dpkg — o bloco deve exigir backup antes"
        )
