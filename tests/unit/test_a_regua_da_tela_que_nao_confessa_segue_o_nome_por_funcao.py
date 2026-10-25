"""A régua da tela que não confessa segue o nome por função, e não pelo arquivo.

A-REGUA-DA-TELA-QUE-NAO-CONFESSA-SEGUE-O-NOME-POR-FUNCAO-01 (25/10/2026). O
``scripts/check_a_tela_nao_confessa.py`` segue a frase de um ``raise`` pelas atribuições e marcava o
nome já visto pelo par (arquivo, nome): a local ``recusa`` do gesto e a ``recusa`` da função chamada
eram o mesmo nome para ela, e a régua parava na segunda sem ler a frase. Medido em 25/10 numa cópia
da árvore com o ``porque`` de ``a07_lancadores._o_modo_na_extensao`` de volta a ``recusa``: dois
recados «que a régua NÃO CONSEGUIU LER» (:2722 e :2872), com a frase escrita no fonte.

MORDIDA (25/10/2026, executada sobre a cura e devolvida, md5 conferido): a chave do visto de volta
a ``(p, no.id)`` reprova ``test_a_local_de_mesmo_nome_na_funcao_chamada_e_lida`` e
``test_a_frase_errada_atras_do_mesmo_nome_reprova``.
"""

from __future__ import annotations

import importlib.util
import pathlib
import textwrap
from types import ModuleType

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_tela_nao_confessa.py"

CERTA = "Toque não está rodando: nada foi enviado."
ERRADA = "O Hefesto ainda não faz isso com esta extensão."

DUAS_FUNCOES = '''
def _o_dono(mod):
    recusa = "{frase}"
    return recusa


def gesto(ctx, valor, p):
    recusa = _o_dono(valor)
    if recusa:
        raise RuntimeError(recusa)
'''

LACOS = '''
def _a(mod):
    x = _b(mod)
    return x


def _b(mod):
    x = _a(mod)
    return x


def _c(mod):
    y = _c(mod)
    return y


def gesto_do_laco(ctx, valor, p):
    x = _a(valor)
    raise RuntimeError(x)


def gesto_de_si_mesmo(ctx, valor, p):
    y = _c(valor)
    raise RuntimeError(y)
'''


def _regua(tmp_path: pathlib.Path, fonte: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """O portão importado com a raiz num lar de mentira: um pacote só, nenhuma página."""
    pacotes = tmp_path / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"
    pacotes.mkdir(parents=True)
    (pacotes / "a99_de_mentira.py").write_text(textwrap.dedent(fonte), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_regua_por_funcao", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for nome, valor in (("RAIZ", tmp_path), ("FONTE", tmp_path / "src"), ("PACOTES", pacotes),
                        ("FATOS", {}), ("A_DIVIDA", {}), ("SEM_LETRA", {})):
        monkeypatch.setattr(mod, nome, valor)
    monkeypatch.setattr(mod, "_paginas", lambda: [])
    monkeypatch.setattr(mod, "_falas", lambda: [])
    return mod


def test_a_local_de_mesmo_nome_na_funcao_chamada_e_lida(tmp_path: pathlib.Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    regua = _regua(tmp_path, DUAS_FUNCOES.format(frase=CERTA), monkeypatch)
    lidos, mudos = regua._recados()
    assert mudos == [], "a régua parou na «recusa» do dono sem ler a frase"
    assert len(lidos) == 1 and CERTA in lidos[0][1]
    assert regua.main() == 0


def test_a_frase_errada_atras_do_mesmo_nome_reprova(tmp_path: pathlib.Path,
                                                    monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    regua = _regua(tmp_path, DUAS_FUNCOES.format(frase=ERRADA), monkeypatch)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "forma de confissão" in saida and "ainda não faz" in saida


def test_o_laco_pela_funcao_chamada_termina(tmp_path: pathlib.Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    regua = _regua(tmp_path, LACOS, monkeypatch)
    lidos, mudos = regua._recados()
    assert len(lidos) == 2
    assert sorted(chave.split(" ← ")[0] for chave, _ in mudos) == [
        "a99_de_mentira.py:gesto_de_si_mesmo", "a99_de_mentira.py:gesto_do_laco"], (
        "o laço sem letra nenhuma é um recado mudo, e a régua o diz")
