#!/usr/bin/env python3
"""A RÉGUA DO SIGPIPE: `cmd | grep -q` mente sob `set -o pipefail`.

A FORMA, e esta casa já pagou por ela DUAS vezes:

    if ! sudo dkms status "$pkg/$ver" 2>/dev/null | grep -q .; then

O `grep -q` sai no PRIMEIRO acerto e fecha o cano. Quem escreve leva SIGPIPE e
morre com 141. Com `set -o pipefail`, o pipeline inteiro herda o 141 — de modo
que a expressão devolve FALHA exatamente quando ACHOU. A guarda `if ! …`
inverte isso e vira sempre verdadeira: o passo protegido roda SEMPRE.

AS DUAS VEZES:

1. **19/08/2026** — `ldconfig -p | grep -q` no censo de bibliotecas do
   `install.sh`. Está escrito no comentário de `install.sh`:686.
2. **01/09/2026** — as quatro guardas de `scripts/dkms_lib.sh`. O sintoma foi
   o pior possível num instalador: com os módulos `installed` nos DOIS kernels
   e EM USO (`modinfo hid_playstation` → `updates/dkms/`), ele chamava
   `dkms add` de novo, o dkms recusava com *"DKMS tree already contains"*, e o
   aviso na tela dela dizia **"in-tree continua"**. Anunciava degradação onde
   tudo funcionava.

A CURA é ler para uma variável e perguntar à variável: sem cano, não há sinal.

ESTA RÉGUA COBRA A FORMA, não o comando: qualquer `| grep -q` dentro de uma
guarda `if !` num arquivo com `pipefail` é a mesma armadilha, e ela cresce
sozinha quando alguém escrever a próxima.

A MORDIDA: devolva um `sudo dkms status … | grep -q .` ao `dkms_lib.sh` e o
primeiro caso reprova nomeando a linha.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: Os roteiros que rodam com `set -o pipefail` — só neles a armadilha morde.
#: A lista NÃO é digitada: sai do próprio `set -` de cada arquivo.
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


#: `if ! <algo> | grep -q…` — a guarda invertida sobre um cano com `grep -q`.
_ARMADILHA = re.compile(r"^\s*(?:el)?if\s*!\s*.*\|\s*grep\s+-q", re.M)

#: A lib do DKMS é sourceada por quem tem `pipefail`, então herda a armadilha
#: sem ter um `set -o pipefail` próprio.
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
    # CANO, e não `||`: o `|| true` é o que mantém o leitor fail-safe. O que
    # não pode voltar é o `|` sozinho, que é onde o SIGPIPE nasce.
    sem_ou = corpo.replace("||", "")
    assert "|" not in sem_ou, f"o leitor voltou a usar cano: {corpo!r}"


def test_o_mecanismo_e_real_e_nao_folclore() -> None:
    """A prova de que a armadilha existe MESMO — no bash desta máquina.

    Sem este caso, os dois acima seriam uma proibição por superstição. Se algum
    dia o bash deixar de propagar o 141, ele reprova e avisa que a regra pode
    cair.
    """
    achou = subprocess.run(
        ["bash", "-c",
         "set -o pipefail; for i in $(seq 500); do echo l$i; done | grep -q l1"],
        capture_output=True,
    )
    assert achou.returncode == 141, (
        f"o pipeline devolveu {achou.returncode}, não 141 (SIGPIPE). "
        "Se isto mudou de verdade, as duas regras acima podem ser relaxadas — "
        "mas confira antes, porque elas custaram dois defeitos em produção."
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
