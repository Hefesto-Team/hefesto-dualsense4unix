"""O caderno do `storm_watch.sh` escreve ENQUANTO a vigia está viva.

CADERNO-QUE-NÃO-ESCREVE-01 (08/08/2026). O defeito, MEDIDO na máquina dela: o
caderno `~/.local/state/hefesto-dualsense4unix/kernel.log` tinha **120 linhas,
todas banners** escritos pelo próprio shell, a mais nova de 20/07 — contra
**723** eventos de storm no journal do mesmo período, com a vigia `enabled` e
`active` o tempo todo. Ela pediu a explicação da queda dos controles; o arquivo
que a guardaria estava vazio.

A CAUSA, e ela não é a óbvia
============================
A hipótese natural — e a que esta casa escreveu primeiro — era buffer de SAÍDA
do `awk`, curável com `fflush()`. **Está errada, e a medição derrubou:**

    produtor vivo (o cano não fecha), 3-4 s de espera:
        mawk '{print; fflush()}'                 -> 0 bytes
        stdbuf -oL -i0 mawk '{print; fflush()}'  -> 0 bytes
        mawk -W interactive '{print}'            -> escreve na hora

O gargalo é a **ENTRADA**: o mawk lê com buffer próprio, fora do stdio, e nem
chega a executar o bloco. Não há o que um `fflush()` de saída descarregue, e o
`stdbuf` não o alcança porque só mexe no stdio. O `journalctl -f` está inocente.

Este arquivo trava as duas metades: que a vigia escreve com o processo vivo (o
comportamento), e que a escolha do interpretador é medida em vez de assumida (a
estrutura). O `fflush()` fica junto da cura e é testado, porque é ele que cobre
o caso do `gawk`, que recusa o `-W interactive`.
"""

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

#: Poucas linhas de propósito: MUITO abaixo de qualquer buffer, para que só o
#: destravamento da entrada explique a escrita.
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


# --- o comportamento: a vigia escreve com o processo VIVO ---------------------


@pytest.mark.skipif(shutil.which("awk") is None, reason="awk ausente")
def test_o_caderno_escreve_com_a_vigia_viva(tmp_path: Path) -> None:
    """Com o produtor vivo e poucos bytes, o caderno já tem as linhas.

    Este é o teste que MORDE. Ele reproduz a condição real da vigia: um produtor
    que não fecha o cano (como o `journalctl -f`), volume pequeno, e a pergunta
    "o arquivo já tem conteúdo AGORA?".

    ARRANQUE A CURA — troque `${_AWK_CMD:-awk}` por `awk` no `classify()` de
    `scripts/storm_watch.sh` — e este teste REPROVA com zero byte, que é
    exatamente o caderno vazio dela.
    """
    caderno = tmp_path / "kernel.log"
    produtor = tmp_path / "produz.sh"
    produtor.write_text(
        "#!/bin/bash\n"
        + "".join(f"echo {linha!r}\nsleep 0.2\n" for linha in LINHAS)
        # segura o cano aberto: é isto que distingue este teste do que passava
        # com a cura arrancada, porque o EOF descarregaria o buffer sozinho.
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
        # Mata por sinal, como o desligamento faz — sem chance de EOF salvar.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):  # pragma: no cover
            proc.kill()
        proc.wait(timeout=5)


# --- a estrutura: a escolha do interpretador é MEDIDA -------------------------


def test_o_classify_usa_o_awk_escolhido() -> None:
    """O `classify()` chama `${_AWK_CMD}`, não `awk` cru.

    ARRANQUE A CURA e este teste REPROVA. É o portão barato contra alguém
    "limpar" a indireção sem saber por que ela existe.
    """
    corpo = _corpo_do_classify()
    assert "${_AWK_CMD" in corpo, (
        "o `classify()` voltou a chamar `awk` diretamente. Sem o `-W interactive` "
        "do mawk o caderno não escreve enquanto a vigia vive. Ver "
        "docs/process/sprints/2026-08-08-CADERNO-QUE-NAO-ESCREVE-01-*.md"
    )


def test_a_escolha_do_awk_e_medida_e_nao_assumida() -> None:
    """A opção é TESTADA contra o `awk` da máquina antes de ser usada.

    Assumir `-W interactive` quebraria a vigia onde o `awk` é o gawk, que recusa
    a opção e sai com erro — deixando o caderno mudo de um jeito pior que o
    defeito original, porque aí nem o processo sobe.
    """
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
    """Quem abrir o script encontra o motivo, não só a linha.

    Uma indireção sem explicação é candidata a ser "limpa" por quem acha que é
    complicação — e a distinção entrada contra saída aqui custou duas medições e uma
    afirmação errada.
    """
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "CADERNO-QUE-NÃO-ESCREVE-01" in texto, "o comentário que explica sumiu"
    assert "ENTRADA do mawk" in texto, (
        "sumiu a frase que diz que o gargalo é a ENTRADA — é a informação que "
        "impede a próxima pessoa de tentar curar com `fflush()` sozinho."
    )
