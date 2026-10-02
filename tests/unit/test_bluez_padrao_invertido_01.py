"""BLUEZ-PADRAO-INVERTIDO-01 — desinstalar o Hefesto não pode piorar o Bluetooth."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"


@pytest.fixture(scope="module")
def fonte() -> str:
    return UNINSTALL.read_text(encoding="utf-8")


def test_o_backport_do_bluez_e_preservado_por_padrao(fonte: str) -> None:
    """O default é PRESERVAR — e o teste lê o valor inicial da variável."""
    achado = re.search(r"^KEEP_BLUEZ=(\d)", fonte, re.MULTILINE)

    assert achado is not None, "a variável KEEP_BLUEZ sumiu do uninstall.sh"
    assert achado.group(1) == "1", (
        "o padrão tem de PRESERVAR o backport do BlueZ: restaurar reinicia o "
        "bluetoothd, descarta os bonds e devolve uma versão com defeito "
        "medido nesta máquina"
    )


def test_existe_uma_flag_explicita_para_devolver_o_bluez_da_distro(
    fonte: str,
) -> None:
    """O gesto destrutivo continua possível — mas ele tem de ser pedido."""
    assert "--restore-bluez)" in fonte
    assert re.search(r"--restore-bluez\)\s*KEEP_BLUEZ=0", fonte), (
        "`--restore-bluez` tem de zerar o KEEP_BLUEZ — é ela que devolve o "
        "pacote da distro"
    )


def test_a_flag_antiga_continua_aceita_e_virou_no_op(fonte: str) -> None:
    """`--keep-bluez` não pode passar a dar erro."""
    assert re.search(r"--keep-bluez\)\s*KEEP_BLUEZ=1", fonte)


def test_o_uninstall_aceita_as_duas_flags_sem_reclamar() -> None:
    """E o parser de verdade engole as duas — não é só o texto."""
    for flag in ("--restore-bluez", "--keep-bluez"):
        r = subprocess.run(
            ["bash", str(UNINSTALL), flag, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, f"{flag} não foi aceita: {r.stderr[:200]}"


def test_o_help_diz_qual_dos_dois_e_o_padrao(fonte: str) -> None:
    """Quem lê o `--help` tem de saber o que acontece se não passar nada."""
    ajuda = subprocess.run(
        ["bash", str(UNINSTALL), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout

    linha = next(
        (ln for ln in ajuda.splitlines() if "--restore-bluez" in ln), ""
    )
    assert linha, "o --help não cita a flag que devolve o BlueZ da distro"

    bloco = ajuda[ajuda.index("--restore-bluez") :][:400]
    assert "padrão PRESERVA" in bloco, (
        "o --help tem de dizer que o PADRÃO preserva o backport — senão "
        "alguém desinstala achando que está preservando"
    )


def test_a_decisao_anterior_nao_foi_apagada(fonte: str) -> None:
    """A regra da casa: decisão medida não se reescreve, ganha nota datada."""
    assert "BLUEZ-PADRAO-INVERTIDO-01" in fonte
    assert "órfão" in fonte, (
        "a justificativa ANTIGA tem de continuar escrita — ela é o que explica "
        "a maquinaria de restauração que continua no arquivo"
    )
