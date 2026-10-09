"""A segunda chance não leva para a frente o endereço que um reapontamento em massa CORRIGIU.

Fonte: a costura da citacoes-1-9 (08/10/2026). A segunda chance lê, no diff do reapontamento em
massa, o endereço de antes dele e o leva pelo código. Quando a massa corrigiu um endereço que tinha
nascido errado, o de antes é o errado, e levá-lo desfaz a correção (o `a09_sistema.py:234 -> :271`
da paridade). O texto, sem a pista em crase ao lado, não separa a massa que corrigiu da que errou:
a trava (``A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO = False``) manda à mão toda massa
que mudou o trecho citado, e deixa passar a que só acompanhou o código. O valor do padrão é decisão
de quem coordena, pela amostra; a régua prova a trava ligada.

Os esperados saem do ALVO: `:3` (`VALOR = 1`), `:7` (`return 1`), `:10` (`def segunda`), `:12`
(`return x`), `:15` (`def terceira`), `:16` (`return 3`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_as_citacoes_andam_com_o_codigo import (
    ALVO,
    _escrever_e_commitar,
    _git,
    _inserir_no_topo,
    _script,
)

END = "src/hefesto_dualsense4unix/alvo.py"


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    yield raiz


def _com_a_trava(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    mod: ModuleType = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    monkeypatch.setattr(mod, "A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO", False)
    return mod


def _doc(um: int, dois: int, quatro: int) -> str:
    return f"# Doc\n\nUm, `{END}:{um}`. Dois, `{END}:{dois}`. Quatro, `{END}:{quatro}`.\n"


def test_a_massa_que_corrigiu_nao_e_desfeita_e_vai_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nasce errado (`:7`, `:12`, `:16`), a massa corrige (`:3`, `:10`, `:15`), o código anda 12.

    Sem a trava, a segunda chance leva o errado: `:19`, `:24`, `:28`."""
    mod = _com_a_trava(monkeypatch)
    doc = _escrever_e_commitar(repo, "docs/protocol/doc.md", _doc(7, 12, 16), "nasce errado")
    doc.write_text(_doc(3, 10, 15), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "o reapontamento em massa corrige")
    _inserir_no_topo(repo, 12, commitar=True)

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == _doc(3, 10, 15), (feitos, a_mao)
    mao = [f for f in a_mao if "doc.md" in f]
    assert len(mao) == 3, a_mao
    assert all("mudou o trecho citado" in f and "pode ter sido uma correção" in f for f in mao), mao


def test_a_massa_que_so_acompanhou_o_codigo_deixa_a_segunda_chance_passar(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nasce certo, o código anda 4, a massa acompanha (o mesmo trecho), o código anda 12.

    O passo de 4 não reescreve um endereço que o documento já tinha (`:15` -> `:20` cairia no
    `:15` de antes, e a entrada dele seria a do nascimento)."""
    mod = _com_a_trava(monkeypatch)
    doc = _escrever_e_commitar(repo, "docs/protocol/doc.md", _doc(3, 10, 15), "nasce certo")
    _inserir_no_topo(repo, 4, commitar=True)
    doc.write_text(_doc(7, 14, 19), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "o reapontamento em massa acompanha")
    _inserir_no_topo(repo, 12, commitar=True)

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == _doc(19, 26, 31), (feitos, a_mao)
    assert not any("doc.md" in f for f in a_mao), a_mao


def test_sem_a_trava_o_padrao_segue_como_estava(repo: Path) -> None:
    """O padrão é a decisão de quem coordena, pela amostra: hoje a segunda chance atravessa."""
    assert _script().A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO is True  # type: ignore[no-untyped-call]
