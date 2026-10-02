"""O caderno do `storm_watch.sh` escreve ENQUANTO a vigia está viva."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "storm_watch.sh"

LINHAS = [
    "2026-08-08T00:24:39-03:00 MeowSystem kernel: nintendo 0005:057E:2009.000A: "
    "joycon_enforce_subcmd_rate: exceeded max attempts",
    "2026-08-08T00:24:40-03:00 MeowSystem kernel: usb 3-1: device descriptor "
    "read/64, error -71",
]

ESPERA_S = 10.0
PASSO_S = 0.1


def _corpo_do_classify() -> str:
    texto = SCRIPT.read_text(encoding="utf-8")
    inicio = texto.index("classify() {")
    return texto[inicio : texto.index("bt_read_errors()", inicio)]


@pytest.mark.skipif(shutil.which("awk") is None, reason="awk ausente")
def test_o_caderno_escreve_com_a_vigia_viva(tmp_path: Path) -> None:
    """Com o produtor vivo e poucos bytes, o caderno já tem as linhas."""
    caderno = tmp_path / "kernel.log"
    produtor = tmp_path / "produz.sh"
    produtor.write_text(
        "#!/bin/bash\n"
        + "".join(f"echo {linha!r}\nsleep 0.2\n" for linha in LINHAS)
        + "sleep 60\n",
        encoding="utf-8",
    )
    produtor.chmod(0o755)

    proc = subprocess.Popen(
        ["bash", "-c", f'"{produtor}" | bash "{SCRIPT}" --classify >> "{caderno}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        limite = time.monotonic() + ESPERA_S
        conteudo = ""
        while time.monotonic() < limite:
            if caderno.exists():
                conteudo = caderno.read_text(encoding="utf-8", errors="replace")
                if conteudo.count("\n") >= len(LINHAS):
                    break
            time.sleep(PASSO_S)

        assert conteudo.strip(), (
            "o caderno está VAZIO com a vigia viva — é o defeito da "
            "CADERNO-QUE-NÃO-ESCREVE-01. O `awk` está bufferizando a ENTRADA e "
            "nem executa o bloco. Custo medido na máquina dela: 120 linhas de "
            "banner contra 723 eventos no journal."
        )
        assert "[JOYCON]" in conteudo, f"faltou a etiqueta [JOYCON]: {conteudo!r}"
        assert "[USB-71]" in conteudo, f"faltou a etiqueta [USB-71]: {conteudo!r}"
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):  # pragma: no cover
            proc.kill()
        proc.wait(timeout=5)


def test_o_classify_usa_o_awk_escolhido() -> None:
    """O `classify()` chama `${_AWK_CMD}`, não `awk` cru."""
    corpo = _corpo_do_classify()
    assert "${_AWK_CMD" in corpo, (
        "o `classify()` voltou a chamar `awk` diretamente. Sem o `-W interactive` "
        "do mawk o caderno não escreve enquanto a vigia vive. Ver "
        "docs/process/sprints/2026-08-08-CADERNO-QUE-NAO-ESCREVE-01-*.md"
    )


def test_a_escolha_do_awk_e_medida_e_nao_assumida() -> None:
    """A opção é TESTADA contra o `awk` da máquina antes de ser usada."""
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "_escolher_awk()" in texto, "a função que MEDE o awk sumiu"
    assert "-W interactive 'BEGIN { exit 0 }'" in texto, (
        "a sonda que testa o `-W interactive` sumiu — sem ela a opção passa a ser "
        "assumida, e quebra onde o `awk` for o gawk."
    )


def test_o_fflush_continua_como_rede_do_gawk() -> None:
    """O `fflush()` fica: é ele que cobre o `awk` que não é o mawk."""
    corpo = _corpo_do_classify()
    assert "fflush()" in corpo, (
        "o `fflush()` saiu do `classify()`. Ele não é redundante: onde o `awk` "
        "for o gawk, o `-W interactive` não se aplica e o `fflush()` é a única "
        "coisa que garante escrita por linha."
    )


def test_o_porque_esta_escrito_no_script() -> None:
    """Quem abrir o script encontra o motivo, não só a linha."""
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "CADERNO-QUE-NÃO-ESCREVE-01" in texto, "o comentário que explica sumiu"
    assert "ENTRADA do mawk" in texto, (
        "sumiu a frase que diz que o gargalo é a ENTRADA — é a informação que "
        "impede a próxima pessoa de tentar curar com `fflush()` sozinho."
    )
