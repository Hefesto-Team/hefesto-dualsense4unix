#!/usr/bin/env python3
"""A RÉGUA DO SIGPIPE: `cmd | grep -q` mente sob `set -o pipefail`."""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

def _com_pipefail() -> list[pathlib.Path]:
    fora = []
    alvos = [RAIZ / "install.sh", RAIZ / "uninstall.sh",
             *sorted((RAIZ / "scripts").rglob("*.sh"))]
    for p in alvos:
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"^set -[a-z]*o pipefail|^set -o pipefail", texto, re.M):
            fora.append(p)
    return fora


_ARMADILHA = re.compile(r"^\s*(?:el)?if\s*!\s*.*\|\s*grep\s+-q", re.M)

_HERDEIROS = (RAIZ / "scripts" / "dkms_lib.sh", RAIZ / "scripts" / "lib" / "camada_de_maquina.sh")


def test_nenhuma_guarda_invertida_le_por_grep_q() -> None:
    """A forma inteira, nos roteiros que herdam ou declaram `pipefail`."""
    culpadas: list[str] = []
    for p in {*_com_pipefail(), *_HERDEIROS}:
        texto = p.read_text(encoding="utf-8", errors="ignore")
        for m in _ARMADILHA.finditer(texto):
            linha = texto[: m.start()].count("\n") + 1
            culpadas.append(f"{p.relative_to(RAIZ)}:{linha}: {m.group(0).strip()}")
    assert not culpadas, (
        "guarda invertida sobre `| grep -q` — sob `pipefail` ela devolve 141 "
        "quando ACHA, e o `if !` a torna sempre verdadeira:\n"
        + "\n".join(f"  - {c}" for c in sorted(culpadas))
        + "\nLeia para uma variável e pergunte à variável: sem cano, sem sinal."
    )


def test_o_leitor_do_dkms_existe_e_nao_usa_cano() -> None:
    """A cura tem dono: `_dkms_status_texto`. Sem ele, cada chamador improvisa."""
    fonte = (RAIZ / "scripts" / "dkms_lib.sh").read_text(encoding="utf-8")
    assert "_dkms_status_texto()" in fonte, (
        "`_dkms_status_texto` sumiu — as guardas do DKMS voltaram a improvisar "
        "a leitura do `dkms status`, e é aí que o cano volta"
    )
    corpo = fonte[fonte.index("_dkms_status_texto()"):]
    corpo = corpo[: corpo.index("\n}")]
    sem_ou = corpo.replace("||", "")
    assert "|" not in sem_ou, f"o leitor voltou a usar cano: {corpo!r}"


_BUFFER_DO_PIPE_BYTES = 64 * 1024

_LINHAS_DO_PRODUTOR = 200_000


def test_o_mecanismo_e_real_e_nao_folclore() -> None:
    """A prova de que a armadilha existe MESMO — no bash desta máquina."""
    achou = subprocess.run(
        ["bash", "-c",
         f"set -o pipefail; seq {_LINHAS_DO_PRODUTOR} | grep -q '^1$'"],
        capture_output=True,
    )
    assert achou.returncode == 141, (
        f"o pipeline devolveu {achou.returncode}, não 141 (SIGPIPE). "
        "Se isto mudou de verdade, as duas regras acima podem ser relaxadas — "
        "mas confira antes, porque elas custaram dois defeitos em produção."
    )


def test_o_produtor_estoura_o_buffer_do_pipe_de_proposito() -> None:
    """O que torna o caso acima DETERMINÍSTICO, medido e não suposto."""
    saida = subprocess.run(
        ["bash", "-c", f"seq {_LINHAS_DO_PRODUTOR}"], capture_output=True
    )
    bytes_gerados = len(saida.stdout)
    assert bytes_gerados > _BUFFER_DO_PIPE_BYTES, (
        f"o produtor gera {bytes_gerados} bytes e o buffer do pipe tem "
        f"{_BUFFER_DO_PIPE_BYTES}: tudo CABE, o produtor não bloqueia, e o "
        "SIGPIPE volta a depender de quem o escalonador acorda primeiro"
    )

    sem_cano = subprocess.run(
        ["bash", "-c",
         'set -o pipefail; t="$(for i in $(seq 500); do echo l$i; done)"; '
         '[[ "$t" == *l1* ]]'],
        capture_output=True,
    )
    assert sem_cano.returncode == 0, "a forma curada também falhou — algo mais está errado"


@pytest.mark.parametrize("guarda", ["add", "build", "install"])
def test_as_tres_guardas_do_dkms_perguntam_a_variavel(guarda: str) -> None:
    """As três que mentiram em 01/09, uma a uma."""
    fonte = (RAIZ / "scripts" / "dkms_lib.sh").read_text(encoding="utf-8")
    i = fonte.index(f'sudo dkms {guarda} "${{_pkg}}/${{_ver}}"')
    trecho = fonte[max(0, i - 400):i]
    assert "_dkms_status_texto" in trecho, (
        f"a guarda do `dkms {guarda}` não pergunta ao `_dkms_status_texto` — "
        f"ela voltou a ler por cano, e vai rodar o passo mesmo com o módulo "
        f"já no lugar"
    )
