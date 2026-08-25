"""T-12 (SISTEMA-O-VIGIA-VIVO-01) — o grep virado portão.

`_query_gamepad_state` foram 22 linhas e uma chamada IPC com **zero
chamadores**, apagadas em 25/08/2026. Não era decisão medida a preservar: era
o resto de uma época em que a Opção de Inicialização da Steam variava por
máscara/backend. Hoje ela é CONSTANTE — `on_storm_copy_launch` chama
`self.compose_launch("", "")` — e o único consumidor plausível nunca chegou a
existir.

A morte estava anotada desde **25/07** (ABAS-01) e **27/07** (o inventário de
botões da janela, que já a chamava *"morto absoluto"*), e mesmo assim o código
atravessou um mês inteiro. É por isso que a régua fica: um nome que ninguém
chama não some sozinho, e a próxima pessoa que o encontrar vai gastar de novo
os minutos que se gastaram aqui para concluir que ele não serve.

**O que este portão proíbe não é o nome — é o nome SEM CHAMADOR.** Se um dia
a Opção de Inicialização voltar a depender do estado do gamepad virtual, a
função volta junto com quem a chama, e o portão fica verde sozinho.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: Nomes apagados por morte nesta sprint. Chave = símbolo; valor = onde ele
#: morava, para o vermelho apontar o lugar em vez de só o nome.
APAGADOS_POR_FALTA_DE_CHAMADOR = {
    "_query_gamepad_state": "app/actions/daemon_actions.py (T-12, 25/08/2026)",
}


def _arquivos_python() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _ocorrencias(simbolo: str) -> dict[Path, list[str]]:
    """Todas as linhas de `src/` que citam o símbolo, por arquivo."""
    achados: dict[Path, list[str]] = {}
    for arquivo in _arquivos_python():
        linhas = [
            linha
            for linha in arquivo.read_text(encoding="utf-8").splitlines()
            if simbolo in linha
        ]
        if linhas:
            achados[arquivo] = linhas
    return achados


@pytest.mark.parametrize("simbolo", sorted(APAGADOS_POR_FALTA_DE_CHAMADOR))
def test_simbolo_morto_so_volta_com_chamador(simbolo: str) -> None:
    """Reapareceu em `src/`? Então tem de ser chamado por alguém.

    A distinção que faz o portão valer a pena: `def _query_gamepad_state` é
    definição; `self._query_gamepad_state(` é chamada. Só definição, sem
    nenhuma chamada, é exatamente o estado que a T-12 mediu e apagou — e é o
    único estado que este teste reprova.
    """
    achados = _ocorrencias(simbolo)
    if not achados:
        return  # apagado, que é o estado de hoje

    definicoes: list[str] = []
    chamadas: list[str] = []
    for arquivo, linhas in achados.items():
        for linha in linhas:
            texto = linha.strip()
            if re.search(rf"\bdef\s+{re.escape(simbolo)}\b", texto):
                definicoes.append(f"{arquivo.relative_to(RAIZ)}: {texto}")
            elif re.search(rf"{re.escape(simbolo)}\s*\(", texto):
                chamadas.append(f"{arquivo.relative_to(RAIZ)}: {texto}")

    assert chamadas, (
        f"`{simbolo}` voltou a `src/` sem nenhum chamador.\n"
        f"Morreu em: {APAGADOS_POR_FALTA_DE_CHAMADOR[simbolo]}\n"
        f"Definições encontradas: {definicoes or 'nenhuma'}\n"
        "Código sem chamador é a família F2 desta casa: custa leitura a toda "
        "pessoa que passa e não entrega nada. Traga o chamador junto, ou "
        "não traga a função."
    )
