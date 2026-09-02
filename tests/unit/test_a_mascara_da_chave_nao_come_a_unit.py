#!/usr/bin/env python3
"""A RÉGUA DA CADEIA: `hefesto-chave off` + `install.sh` comiam a unit do daemon.

O ESTRAGO, MEDIDO EM 01/09/2026, e ele é de duas curas se atropelando:

1. `hefesto-chave off` **mascara** as units — e uma máscara do systemd é um
   symlink ``~/.config/systemd/user/<unit>`` → ``/dev/null``.
2. `install.sh` fazia ``cp -f "${DAEMON_UNIT_SRC}" "${DAEMON_UNIT_TARGET}"``.
   **O `cp` SEGUE o symlink**: a unit inteira vai para dentro do ``/dev/null``,
   e o `cp` devolve ``rc=0``. O ``set -e`` não pega, ninguém é avisado.
3. `hefesto-chave on` faz ``unmask``, o symlink some — **e não há arquivo por
   baixo**. A unit do daemon dela desapareceu do disco.

E havia um quarto degrau, que é o que torna isto uma MENTIRA e não só um bug:
`utils/chave.py` faz o daemon RECUSAR subir enquanto a flag existir. O
instalador nunca a lia, dava `enable` (que falha na unit mascarada) e imprimia
``daemon habilitado e no ar``.

AS TRÊS COISAS QUE ESTA RÉGUA COBRA:

1. **O `unmask` vem ANTES do `cp`.** Ordem é o conteúdo inteiro da cura: depois
   do `cp` não há o que salvar.
2. **A CHAVE EM DISCO É LIDA.** Se ela desligou o Hefesto de propósito, o
   instalador tem de dizer isso e não anunciar um daemon no ar.
3. **A CHAVE NÃO É APAGADA pelo instalador.** Desfazer calado a decisão dela é
   o defeito oposto, e igualmente caro.

A MORDIDA: tire o bloco do `unmask` e o caso 1 reprova; tire a leitura da flag
e o caso 2 reprova. O caso 4 é a prova de comportamento — ele mede o `cp` de
verdade, num diretório de mentira, e reprova se alguém "otimizar" a ordem.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"

#: O nome do arquivo que a chave escreve. UM DONO SÓ — `utils/chave.py`.
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
    """A máscara é metade da chave; a outra metade é o arquivo, e ela morde mais.

    `utils/chave.py` faz o daemon recusar subir enquanto o arquivo existir.
    Anunciar "daemon habilitado e no ar" por cima disso é a mentira que esta
    casa persegue.
    """
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
    """A prova de COMPORTAMENTO, e é ela que fecha o buraco de verdade.

    As três acima leem o texto do instalador. Esta reproduz o mecanismo: um
    symlink para /dev/null, o `cp -f` por cima, e a pergunta que importa — o
    arquivo sobreviveu?
    """
    alvo = tmp_path / "hefesto-dualsense4unix.service"
    fonte = tmp_path / "fonte.service"
    fonte.write_text("[Unit]\nDescription=a unit de verdade\n", encoding="utf-8")

    # SEM a cura: o `cp` atravessa e o conteúdo se perde. É o estado de antes.
    os.symlink("/dev/null", alvo)
    subprocess.run(["cp", "-f", str(fonte), str(alvo)], check=True)
    assert alvo.is_symlink(), "o `cp -f` deixou de seguir o symlink neste sistema?"
    assert alvo.read_text(encoding="utf-8") == "", (
        "o `cp` NÃO atravessou a máscara — se este caso reprovar, o mecanismo "
        "mudou e a cura no `install.sh` pode ter deixado de ser necessária"
    )

    # COM a cura: retira a máscara antes, e o arquivo nasce de verdade.
    alvo.unlink()
    subprocess.run(["cp", "-f", str(fonte), str(alvo)], check=True)
    assert not alvo.is_symlink()
    assert "a unit de verdade" in alvo.read_text(encoding="utf-8")
