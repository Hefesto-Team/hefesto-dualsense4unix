"""A-JOGAR-SEM-CONTROLE-NAO-COLAPSA-01 — a Jogar sem nenhum controle ocupa o lugar do cartão.

Medido em 30/10/2026 nos prints dela: com a mesa vazia, o cartão do P1 aberto colapsava na faixa
de 24 px com «Player 1 • Desconectado», e as quatro abas ficavam encostadas no alto. A cura
(D-3010-A-JOGAR-VAZIA-E-O-LUGAR-DO-CARTAO) dá ao lugar vazio aberto a altura do cartão de um
controle, tracejado, com o disco do número no meio e nenhuma palavra.
"""
from __future__ import annotations

import re

from hefesto_dualsense4unix.interface import aba01, monta, onde

JOGAR = onde.BANCADA / "01-jogar.html"


def _folha() -> str:
    doc = JOGAR.read_text(encoding="utf-8")
    return doc.split('<style id="abas-dos-controles">', 1)[1].split("</style>", 1)[0]


def _regra(folha: str, seletor: str) -> str:
    achou = re.search(re.escape(seletor) + r"\{([^}]*)\}", folha)
    assert achou, f"a folha das abas não tem regra para {seletor!r}"
    return achou.group(1)


def test_o_lugar_vazio_aberto_tem_a_altura_do_cartao() -> None:
    """A altura do cartão de um controle, tracejada (D-3010-A-JOGAR-VAZIA-E-O-LUGAR-DO-CARTAO)."""
    folha = _folha()
    corpo = _regra(folha, aba01.LUGAR_VAZIO_ABERTO)
    altura = re.search(r"(?:^|;)height:(\d+)px !important", corpo)
    assert altura and int(altura.group(1)) >= 200, (
        f"o lugar vazio aberto voltou a colapsar na faixa: {corpo!r}")
    assert "dashed" in corpo, "o lugar vazio aberto perdeu o traço do lugar vazio"


def test_o_lugar_vazio_aberto_nao_diz_desconectado() -> None:
    """Nenhuma palavra no lugar vazio aberto (D-3010-A-JOGAR-VAZIA-E-O-LUGAR-DO-CARTAO)."""
    folha = _folha()
    faixa = _regra(folha, f"{aba01.LUGAR_VAZIO_ABERTO} > .faixa")
    assert "display:none !important" in faixa, (
        "a faixa «Player N • Desconectado» voltou ao lugar vazio aberto da Jogar")


def test_o_lugar_vazio_aberto_mostra_o_numero_de_cada_lugar() -> None:
    """O disco do número no meio, e a aba aberta encosta no cartão.

    D-3010-A-JOGAR-VAZIA-E-O-LUGAR-DO-CARTAO.
    """
    folha = _folha()
    for lugar in monta.MESA:
        pref = lugar["pref"]
        disco = _regra(
            folha, f'{aba01.LUGAR_VAZIO}[data-controle="{pref}"]:has(> input:checked)::after')
        assert f'content:"{pref[1:]}"' in disco, f"o lugar vazio {pref} não mostra o número dele"
        aba = _regra(folha, f'body:has(#c-{pref}:checked) .aba-ctl.off[data-controle="{pref}"]')
        assert "height:var(--alt-aba)" in aba, f"a aba vazia aberta do {pref} não encosta no cartão"
