#!/usr/bin/env python3
"""A RÉGUA DA CADEIA: `hefesto-chave off` + `install.sh` comiam a unit do daemon."""
from __future__ import annotations

import os
import pathlib
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"

def _nome_da_chave() -> str:
    import sys

    sys.path.insert(0, str(RAIZ / "src"))
    from hefesto_dualsense4unix.utils.chave import NOME_DO_ARQUIVO

    return NOME_DO_ARQUIVO


def _fonte() -> str:
    return INSTALL.read_text(encoding="utf-8")


def test_o_unmask_vem_antes_do_cp_da_unit() -> None:
    """Depois do `cp` não há o que salvar: a unit já foi para o `/dev/null`."""
    fonte = _fonte()
    cp = fonte.index('cp -f "${DAEMON_UNIT_SRC}" "${DAEMON_UNIT_TARGET}"')
    trecho = fonte[max(0, cp - 2500):cp]
    assert 'unmask "${DAEMON_UNIT_NAME}"' in trecho, (
        "o `cp -f` da unit do daemon não tem um `unmask` antes dele.\n"
        "Uma máscara do systemd é um symlink para /dev/null, e o `cp` a SEGUE: "
        "a unit vai para o buraco com rc=0, e some no `hefesto-chave on`."
    )
    assert "/dev/null" in trecho and "readlink -f" in trecho, (
        "a guarda não confere que o alvo é MESMO uma máscara — desmascarar sem "
        "conferir mexeria numa unit que a pessoa mascarou por outra razão"
    )


def test_o_instalador_le_a_chave_em_disco() -> None:
    """A máscara é metade da chave; a outra metade é o arquivo, e ela morde mais."""
    fonte = _fonte()
    assert _nome_da_chave() in fonte, (
        f"`install.sh` não olha o {_nome_da_chave()!r} — ele vai dizer que o "
        f"daemon está no ar enquanto o daemon recusa subir"
    )


def test_o_instalador_nao_apaga_a_chave() -> None:
    """Desfazer calado a decisão dela é o defeito oposto, e igualmente caro."""
    nome = _nome_da_chave()
    for linha in _fonte().splitlines():
        nua = linha.strip()
        if nua.startswith("#") or nome not in linha:
            continue
        assert not nua.startswith(("rm ", "rm -")), (
            f"o instalador APAGA a chave: {nua!r}\n"
            "Quem desliga é ela, e quem religa é o `hefesto-chave on`."
        )


def test_o_cp_de_verdade_nao_atravessa_a_mascara(tmp_path) -> None:
    """A prova de COMPORTAMENTO, e é ela que fecha o buraco de verdade."""
    alvo = tmp_path / "hefesto-dualsense4unix.service"
    fonte = tmp_path / "fonte.service"
    fonte.write_text("[Unit]\nDescription=a unit de verdade\n", encoding="utf-8")

    os.symlink("/dev/null", alvo)
    subprocess.run(["cp", "-f", str(fonte), str(alvo)], check=True)
    assert alvo.is_symlink(), "o `cp -f` deixou de seguir o symlink neste sistema?"
    assert alvo.read_text(encoding="utf-8") == "", (
        "o `cp` NÃO atravessou a máscara — se este caso reprovar, o mecanismo "
        "mudou e a cura no `install.sh` pode ter deixado de ser necessária"
    )

    alvo.unlink()
    subprocess.run(["cp", "-f", str(fonte), str(alvo)], check=True)
    assert not alvo.is_symlink()
    assert "a unit de verdade" in alvo.read_text(encoding="utf-8")
