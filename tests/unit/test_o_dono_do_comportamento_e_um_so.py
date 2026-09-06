"""A régua do portão `donos-de-comportamento` — ela tem de MORDER.

O portão existe para o laudo dos cinco agentes não envelhecer. Uma régua que
passa com o laudo mentindo não protege nada — então aqui cada uma das quatro
classes de mentira é escrita à mão e o portão tem de reprovar.

Nasceu com o portão, em 05/09/2026.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_donos_de_comportamento.py"
MAPA = RAIZ / "docs" / "data" / "donos-de-comportamento.csv"


def _modulo():
    spec = importlib.util.spec_from_file_location("_portao_donos", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_donos"] = mod
    spec.loader.exec_module(mod)
    return mod


def _linhas() -> tuple[list[str], list[dict[str, str]]]:
    with MAPA.open(encoding="utf-8") as fh:
        leitor = csv.DictReader(fh)
        campos = list(leitor.fieldnames or ())
        return campos, list(leitor)


def _escrever(destino: Path, campos: list[str], linhas: list[dict[str, str]]) -> None:
    with destino.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


@pytest.fixture
def portao(tmp_path, monkeypatch):
    """O portão apontado para uma CÓPIA do mapa, que o teste pode estragar."""
    mod = _modulo()
    copia = tmp_path / "donos-de-comportamento.csv"
    campos, linhas = _linhas()

    def rodar(mexer=None) -> int:
        mexidas = [dict(x) for x in linhas]
        if mexer is not None:
            mexer(mexidas)
        _escrever(copia, campos, mexidas)
        monkeypatch.setattr(mod, "MAPA", copia)
        return mod.main([])

    return rodar


def test_o_mapa_de_hoje_passa(portao):
    assert portao() == 0


def test_endereco_que_morreu_reprova(portao):
    def mexer(linhas):
        linhas[0]["dono"] = "app/actions/profiles_actions.py:funcao_que_nunca_existiu"

    assert portao(mexer) == 1


def test_arquivo_que_sumiu_reprova(portao):
    def mexer(linhas):
        linhas[0]["dono"] = "app/actions/arquivo_que_nao_existe.py:qualquer"

    assert portao(mexer) == 1


def test_cura_descosturada_reprova(portao):
    """CURADO cujo arquivo de tela deixou de citar o dono: a ponte caiu."""

    def mexer(linhas):
        for linha in linhas:
            if linha["veredito"] == "CURADO":
                # o dono existe, mas não é quem a tela chama
                linha["dono"] = "app/actions/home_actions.py:aviso_de_grab"
                linha["onde_html"] = "interface/pacotes/a08_conexoes.py:_adaptadores"
                return
        pytest.fail("o mapa não tem nenhuma linha CURADO")

    assert portao(mexer) == 1


def test_so_gtk_que_a_tela_nova_ja_chama_reprova(portao):
    def mexer(linhas):
        for linha in linhas:
            if linha["veredito"] == "SO-GTK":
                linha["dono"] = "app/actions/home_actions.py:mascara_viva"
                return
        pytest.fail("o mapa não tem nenhuma linha SO-GTK")

    assert portao(mexer) == 1


def test_a_divida_que_cresce_reprova(portao):
    def mexer(linhas):
        for linha in linhas:
            if linha["veredito"].startswith("DUPLICATA"):
                linha["economia_linhas"] = str(int(linha["economia_linhas"]) + 1000)
                return
        pytest.fail("o mapa não tem nenhuma duplicata")

    assert portao(mexer) == 1


def test_duplicata_sem_a_conta_reprova(portao):
    def mexer(linhas):
        for linha in linhas:
            if linha["veredito"].startswith("DUPLICATA"):
                linha["economia_linhas"] = ""
                return

    assert portao(mexer) == 1


def test_linha_sem_razao_reprova(portao):
    def mexer(linhas):
        linhas[0]["razao"] = ""

    assert portao(mexer) == 1


def test_o_teto_e_a_soma_declarada():
    """O teto não pode nascer folgado — folga é dívida que entra calada."""
    mod = _modulo()
    _, linhas = _linhas()
    soma = sum(
        int(x["economia_linhas"])
        for x in linhas
        if x["veredito"].startswith("DUPLICATA") and x["economia_linhas"].isdigit()
    )
    assert soma == mod.TETO_DE_LINHAS_DUPLICADAS
