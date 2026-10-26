"""O-PERFIL-QUE-VALE-TEM-UMA-CASA-SO-01 (23/10/2026).

«O padrão do computador por baixo de um perfil vazio» era montado à mão em cinco
lugares fora do dono (a luz, o tato, a 02, a 04 e o pacote do perfil), sempre
como ``perfil_que_vale(perfil_vazio(), <computador>)``. O dono dá nome à
pergunta, ``o_perfil_sem_perfil_ativo``, e só ele monta o par.

A MORDIDA: devolva o par a qualquer um dos cinco, e o primeiro teste reprova.
"""
from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.utils import maquina as m

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
DONO = SRC / "profiles" / "o_padrao_do_computador.py"
A_CASA = "o_perfil_sem_perfil_ativo"
QUEM_PERGUNTA = (
    "daemon/subsystems/luz_animada.py",
    "daemon/subsystems/tato_vivo.py",
    "interface/pacotes/perfil.py",
    "interface/pacotes/a02_controles.py",
    "interface/pacotes/a04_iluminacao.py",
)


def _nome(no: ast.AST) -> str | None:
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return no.attr
    return None


def _chama(no: ast.AST, nome: str) -> bool:
    return isinstance(no, ast.Call) and _nome(no.func) == nome


def _os_pares(arvore: ast.AST) -> list[tuple[int, str | None]]:
    """``(linha, função em volta)`` de cada ``perfil_que_vale`` cujo perfil é o vazio."""
    achados: list[tuple[int, str | None]] = []

    def visitar(no: ast.AST, funcao: str | None) -> None:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcao = no.name
        if (
            _chama(no, "perfil_que_vale") and isinstance(no, ast.Call) and no.args
            and any(_chama(dentro, "perfil_vazio") for dentro in ast.walk(no.args[0]))
        ):
            achados.append((no.lineno, funcao))
        for filho in ast.iter_child_nodes(no):
            visitar(filho, funcao)

    visitar(arvore, None)
    return achados


def test_so_o_dono_monta_o_perfil_sem_perfil_ativo() -> None:
    """Nenhum módulo de ``src/`` escreve o par, e o dono só o escreve na função dele."""
    fora: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        for linha, funcao in _os_pares(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if arquivo == DONO and funcao == A_CASA:
                continue
            fora.append(f"{arquivo.relative_to(RAIZ)}:{linha} (em {funcao})")
    assert not fora, "o par montado fora da casa dele:\n" + "\n".join(fora)
    assert _os_pares(ast.parse(DONO.read_text(encoding="utf-8"))), (
        "a régua não acha nem o par da casa: ela não mede nada"
    )


@pytest.mark.parametrize("relativo", QUEM_PERGUNTA)
def test_cada_um_dos_cinco_pergunta_ao_dono(relativo: str) -> None:
    texto = (SRC / relativo).read_text(encoding="utf-8")
    assert A_CASA in texto, f"{relativo} não pergunta mais ao dono"


COMPUTADORES: dict[str, dict[str, Any] | None] = {
    "sem-declaracao": None,
    "declarado-vazio": {},
    "cheio": {
        "global": {"leds": {"efeito": "respirar;00FFFF;2"}},
        "controles": {"aabbcc000001": {"leds": {"efeito": "respirar;FF00FF;3"}}},
    },
}


@pytest.mark.parametrize("caso", sorted(COMPUTADORES))
def test_a_casa_da_o_mesmo_perfil_que_o_par_dava(caso: str) -> None:
    documento = COMPUTADORES[caso]
    if documento is not None:
        assert m.gravar_o_computador(documento)
    computador = opc.o_computador()
    o_par = opc.perfil_que_vale(opc.perfil_vazio(), computador)
    esperado = o_par.model_dump(mode="json", exclude_unset=True)
    assert opc.o_perfil_sem_perfil_ativo().model_dump(mode="json", exclude_unset=True) == esperado
    assert opc.o_perfil_sem_perfil_ativo(computador).model_dump(
        mode="json", exclude_unset=True) == esperado
    if caso == "cheio":
        assert not opc.computador_vazio(computador), "o computador cheio não chegou ao disco"
        assert o_par.controllers is not None and "aabbcc000001" in o_par.controllers
