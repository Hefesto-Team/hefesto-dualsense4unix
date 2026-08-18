"""Contrato do scripts/install_usb_quirk.sh (Opção D — quirk que PRESERVA o áudio).

FEAT-DSX-DEFINITIVE-FIX-01 §7.5. O quirk `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn`
(g=DELAY_INIT, n=DELAY_CTRL_MSG) ESPAÇA a rajada de control-transfers do probe do
`snd-usb-audio` para ela não tombar o link — mitiga o storm -71 PRESERVANDO o mic e
o fone do jack do DualSense. É a ALTERNATIVA à regra 75 (áudio-off).

IMPORTANTE: é um PARÂMETRO DE CMDLINE do kernel, NÃO uma regra udev — uma regra udev
não consegue alterar o próprio enumeramento do device. Por isso é empacotado como
script de install ciente do bootloader, e não como assets/*.rules.

Estes testes são leves: SEM root e SEM tocar /etc — validam que o script existe e é
executável, que `--status`/`--check` rodam read-only, e que a string do quirk é
EXATAMENTE `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn`. Espelha o estilo de
tests/unit/test_udev_rule_75_disable_usb_audio.py.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_usb_quirk.sh"

# A string canônica do quirk (cmdline) — contrato com o kernel. Mudar isto exige
# reavaliar o A/B do storm; mantida idêntica à regra 75 e à discovery.
EXPECTED_QUIRK = "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_arquivo_existe() -> None:
    assert SCRIPT_PATH.is_file(), f"script ausente em {SCRIPT_PATH}"


def test_arquivo_executavel() -> None:
    import os

    assert os.access(SCRIPT_PATH, os.X_OK), f"{SCRIPT_PATH} não é executável (chmod +x)"


def test_string_do_quirk_exata(script_text: str) -> None:
    # A constante QUIRK precisa ser EXATAMENTE a string esperada.
    assert f'QUIRK="{EXPECTED_QUIRK}"' in script_text, (
        f"constante QUIRK não bate exatamente: esperado QUIRK=\"{EXPECTED_QUIRK}\""
    )


def test_sintaxe_bash_valida() -> None:
    # bash -n: parse-only, não executa nada (sem root, sem efeitos colaterais).
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"erro de sintaxe bash:\n{result.stderr}"


def test_status_roda_sem_root() -> None:
    # --status é read-only (lê /proc/cmdline, config, sysfs) e NUNCA falha.
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--status"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"--status falhou (rc={result.returncode}):\n{result.stderr}"
    assert EXPECTED_QUIRK in result.stdout, "--status não imprime o quirk alvo"


def test_check_eh_alias_de_status() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"--check falhou (rc={result.returncode}):\n{result.stderr}"


def test_nao_e_regra_udev_no_header(script_text: str) -> None:
    # O header deve deixar explícito que é cmdline do kernel, NÃO regra udev.
    lowered = script_text.lower()
    assert "não é uma regra udev" in lowered or "não é regra udev" in lowered, (
        "header precisa esclarecer que NÃO é regra udev (é cmdline do kernel)"
    )


def test_single_token_documentado(script_text: str) -> None:
    # O kernel respeita só UM token usbcore.quirks=; o script avisa e não duplica.
    assert "só um token" in script_text.lower() or "só UM token".lower() in script_text.lower()


def test_modos_de_reversao_e_runtime_existem(script_text: str) -> None:
    # Contrato de flags: --remove (reverte) e --runtime (best-effort sysfs).
    for flag in ("--remove", "--runtime", "--status"):
        assert flag in script_text, f"flag {flag} ausente no dispatch do script"
