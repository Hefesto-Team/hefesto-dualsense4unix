"""Todo `.desktop` que esta casa empacota valida SEM SAÍDA — nem erro, nem aviso."""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
VALIDADOR = shutil.which("desktop-file-validate")

ALVOS = sorted(RAIZ.glob("packaging/**/*.desktop"))

pytestmark = pytest.mark.skipif(
    VALIDADOR is None,
    reason="sem `desktop-file-validate` — a régua não tem motor")


def test_ha_desktop_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada."""
    assert ALVOS, (
        "nenhum `.desktop` em `packaging/**` — ou a pasta mudou de nome, ou "
        "esta régua deixou de medir o que promete")


@pytest.mark.parametrize("alvo", ALVOS, ids=lambda p: p.name)
def test_o_desktop_nao_emite_uma_linha_sequer(alvo: pathlib.Path) -> None:
    """Saída vazia, e só isso passa."""
    r = subprocess.run(
        [str(VALIDADOR), str(alvo)],
        capture_output=True, text=True, check=False)
    saida = (r.stdout + r.stderr).strip()
    assert not saida, (
        f"`{alvo.relative_to(RAIZ)}` não valida limpo:\n"
        + "\n".join("    " + linha.replace(str(alvo) + ": ", "")
                    for linha in saida.splitlines())
        + "\n\n  O `rc` foi "
        + str(r.returncode)
        + " — repare que um `hint` sai com `rc=0`. Se o achado for aceitável, "
        "a saída continua tendo de ser vazia: cure o arquivo, não a régua.")
