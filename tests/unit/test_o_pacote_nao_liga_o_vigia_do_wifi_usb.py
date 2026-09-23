"""O pacote não liga o vigia do Wi-Fi USB — e o doctor diz a quem instalou por ele como ligar.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-15, na decisão de quem
coordena: o `install-host-udev.sh` (o helper que os pacotes .deb/.rpm/Arch
levam) NÃO instala o timer do vigia, o dispatcher do NetworkManager nem o
drop-in do watchdog — o mesmo desenho dos timers da resiliência. A razão está
escrita no próprio helper.

O que se tranca:

1. o código do helper não põe nenhum dos três, e a declaração está nele;
2. o doctor de uma instalação por PACOTE, com Wi-Fi USB e sem vigia, diz que o
   pacote não o liga e qual gesto liga — e não manda «atualizar», que é mandar
   repetir o que não entrega;
3. no checkout, a frase de sempre (quem cobra é
   `test_o_que_era_do_zsh_mora_no_hefesto.py`).

A MORDIDA, medida: pôr um `install … hefesto-wifi-usb-vigia.timer` no código do
helper reprova o teste 1; trocar o ramo do pacote pelo `conselho_de_instalacao`
de antes, o 2.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tests.unit.test_o_que_era_do_zsh_mora_no_hefesto import IFC, WIFI, _mesa

RAIZ = Path(__file__).resolve().parents[2]
HELPER = RAIZ / "scripts" / "install-host-udev.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _codigo(texto: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )


def test_o_helper_do_pacote_nao_poe_o_vigia_e_diz_por_que() -> None:
    texto = HELPER.read_text(encoding="utf-8")
    codigo = _codigo(texto)
    for alvo in (
        "hefesto-wifi-usb-vigia",
        "90-hefesto-wifi-usb",
        "10-hefesto-maquina.conf",
    ):
        assert alvo not in codigo, (
            f"o install-host-udev.sh passou a instalar {alvo} — a decisão (P-15) é que "
            "o pacote não o liga; se ela mudou, mude a declaração no helper e esta régua"
        )
    assert "O VIGIA DO WI-FI USB NÃO VAI POR AQUI" in texto


def _doctor_do_pacote(tmp_path: Path) -> str:
    """O doctor como o pacote o leva: em /usr/share, sem `install.sh` ao lado."""
    amb = _mesa(tmp_path)
    pacote = tmp_path / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    pacote.mkdir(parents=True)
    shutil.copy(DOCTOR, pacote / "doctor.sh")
    shutil.copy(WIFI, pacote / "wifi_usb.sh")
    (pacote / "wifi_usb.sh").chmod(0o755)
    bindir = tmp_path / "bin-doctor-pacote"
    bindir.mkdir()
    for nome, corpo in (("systemctl", 'echo "inactive"'), ("journalctl", "exit 0")):
        (bindir / nome).write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        (bindir / nome).chmod(0o755)
    dispatcher = tmp_path / "etc-nm" / "dispatcher.d" / "90-hefesto-wifi-usb"
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        "HEFESTO_WIFI_BIN": str(bindir),
        "HEFESTO_WIFI_DEV": amb["HEFESTO_WIFI_DEV"],
        "HEFESTO_WIFI_SYSFS": amb["HEFESTO_WIFI_SYSFS"],
        "HEFESTO_WIFI_INSTALADO": str(tmp_path / "nao-instalado" / "wifi_usb.sh"),
        "HEFESTO_WIFI_DISPATCHER": str(dispatcher),
    }
    r = subprocess.run(
        ["bash", "-c", f'source "{pacote / "doctor.sh"}"; check_wifi_usb'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    return r.stdout + r.stderr


def test_o_doctor_do_pacote_diz_como_ligar_o_vigia(tmp_path: Path) -> None:
    saida = _doctor_do_pacote(tmp_path)
    assert f"[WARN] há Wi-Fi USB ({IFC}) e o vigia do dongle não está ligado" in saida, saida
    assert "O pacote não o liga" in saida
    assert "o instalador do repositório do Hefesto" in saida
    assert "atualize" not in saida and "apt upgrade" not in saida, (
        "o doctor mandou quem instalou por pacote atualizar — o pacote não liga o vigia:\n"
        + saida
    )
