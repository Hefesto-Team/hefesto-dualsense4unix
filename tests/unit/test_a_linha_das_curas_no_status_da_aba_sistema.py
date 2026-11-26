"""A linha das correções desfeitas no Status da aba Sistema.

A-ABA-SISTEMA-DIZ-QUANDO-A-ATUALIZACAO-DESFEZ-UMA-CURA-01, a metade da tela (26/11/2026). O dono
das curas é ``integrations/curas_da_casa.py``; esta prova cobre o que a tela faz com a resposta:
uma linha a mais no Status, no mesmo selo «AVISO», com a frase curta da cura que caiu e a cura na
dica; com as quatro de pé a linha não existe, e os seis temas seguem como estavam.

MORDIDAS (cada uma vista reprovar e devolvida):

* a linha sempre presente, com as curas de pé: ``test_com_as_curas_de_pe_a_linha_nao_existe``;
* a linha fora do lugar do desenho:
  ``test_a_cura_que_caiu_vira_a_linha_logo_depois_do_steam_input``;
* a frase sem a cura que caiu (todas viram «uma correção»): ``test_a_frase_diz_qual_cura_caiu``;
* o gesto ligado ao «Atualizações» e não ao próprio:
  ``test_a_linha_chega_ao_html_com_o_gesto_e_o_endereco_do_desenho``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import curas_da_casa as cc
from hefesto_dualsense4unix.integrations import storm_doctor
from hefesto_dualsense4unix.interface import sistema as tela
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09
from hefesto_dualsense4unix.interface.pacotes import atualizacoes, gesto_da_pagina

RAIZ = Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "09-sistema.html"
TEMA = "correcoes-do-sistema"
STATUS = [
    {"id": "hefesto-estado", "selo": "LIGADO", "cls": "ok", "g": "✓", "txt": "Serviço"},
    {"id": "hefesto-troca-de-perfil", "selo": "LIGADO", "cls": "ok", "g": "✓", "txt": "Troca"},
]


def _cura(id_: str, estado: str) -> cc.Cura:
    frase = {"dkms": "O driver do DualSense é o de fábrica no kernel 7.2.15",
             "bluetooth": "O Bluetooth voltou ao da distribuição",
             "som": "O som voltou ao da distribuição",
             "portal": "A captura de tela voltou à da distribuição"}[id_]
    return cc.Cura(id_, id_, estado, frase if estado == cc.CAIU else "",
                   cc.RODE_O_INSTALADOR if estado == cc.CAIU else "")


def _linhas(monkeypatch: pytest.MonkeyPatch, caidas: tuple[str, ...]) -> list[dict[str, Any]]:
    curas = [_cura(i, cc.CAIU if i in caidas else cc.VALE)
             for i in ("dkms", "bluetooth", "som", "portal")]
    monkeypatch.setattr(cc, "curas_de_agora", lambda *a, **k: list(curas))
    bem = [("[OK]", f"tudo certo {n}") for n in range(6)]
    exame = tela.exame([*bem, storm_doctor.check_curas_da_casa(curas)])
    return list(a09._so_o_que_a_tela_mostra(exame, STATUS, {})["linhas"])


def test_com_as_curas_de_pe_a_linha_nao_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2611-A-LINHA-DAS-CURAS-SO-EXISTE-COM-UMA-CURA-CAIDA: quatro curas de pé dão os seis
    temas, nenhuma linha a mais, nenhum aviso no Serviço."""
    linhas = _linhas(monkeypatch, ())
    assert [x["tema"] for x in linhas] == list(a09.TEMAS)
    assert all(x["cls"] != "aviso" for x in linhas)


def test_a_cura_que_caiu_vira_a_linha_logo_depois_do_steam_input(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A linha leva o selo AVISO, a frase curta, a cura na dica e o gesto próprio."""
    linhas = _linhas(monkeypatch, ("dkms",))
    temas = [x["tema"] for x in linhas]
    assert temas.index(TEMA) == temas.index("steam-input") + 1
    assert [t for t in temas if t != TEMA] == list(a09.TEMAS)
    linha = linhas[temas.index(TEMA)]
    assert (linha["selo"], linha["cls"]) == ("AVISO", "aviso")
    assert linha["txt"] == "A atualização desfez a correção do controle"
    assert linha["dica"].startswith("Correções do sistema. O driver do DualSense")
    assert linha["dica"].endswith(cc.RODE_O_INSTALADOR)
    assert (linha["href"], linha["gesto"]) == ("#", a09.GESTO_DAS_CURAS)
    assert next(x for x in linhas if x["tema"] == "serviço")["cls"] == "ok"


@pytest.mark.parametrize(("caida", "frase"), [
    ("dkms", "A atualização desfez a correção do controle"),
    ("bluetooth", "A atualização desfez a correção do Bluetooth"),
    ("som", "A atualização desfez a correção do som"),
    ("portal", "A atualização desfez a correção da captura de tela"),
])
def test_a_frase_diz_qual_cura_caiu(monkeypatch: pytest.MonkeyPatch, caida: str,
                                    frase: str) -> None:
    """Prova da D-2611-A-LINHA-DAS-CURAS-NOMEIA-A-QUE-CAIU-E-CONTA-AS-VARIAS.

    Cada uma das quatro curas tem a sua frase curta, no molde do desenho escolhido.
    """
    linhas = _linhas(monkeypatch, (caida,))
    assert next(x for x in linhas if x["tema"] == TEMA)["txt"] == frase


def test_varias_curas_caidas_viram_uma_linha_com_a_conta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-2611-A-LINHA-DAS-CURAS-NOMEIA-A-QUE-CAIU-E-CONTA-AS-VARIAS.

    Duas curas caídas: uma linha só, «desfez 2 correções»; o Status não ganha uma linha por cura.
    """
    linhas = _linhas(monkeypatch, ("bluetooth", "som"))
    achadas = [x for x in linhas if x["tema"] == TEMA]
    assert [x["txt"] for x in achadas] == ["A atualização desfez 2 correções"]


def test_a_linha_chega_ao_html_com_o_gesto_e_o_endereco_do_desenho(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A marcação do produto é a do desenho: link `#`, gesto próprio, selo e dica."""
    linhas = _linhas(monkeypatch, ("dkms",))
    pintado = a09._linha_do_exame(next(x for x in linhas if x["tema"] == TEMA))
    assert re.match(
        r'<a class="saude vai longa" data-tema="correcoes-do-sistema" href="#" '
        r'data-gesto="correcoes-do-sistema"><span class="selo aviso">', pintado), pintado


def test_o_desenho_traz_a_linha_do_desenho_escolhido() -> None:
    """O mockup publicado do desenho tem a linha, com o gesto próprio e sem o do Atualizações."""
    desenho = DESENHO.read_text(encoding="utf-8")
    achada = re.search(r'<a class="saude vai longa" data-tema="correcoes-do-sistema" href="#" '
                       r'data-gesto="correcoes-do-sistema">.*?</a>', desenho)
    assert achada, "o desenho não traz a linha das correções"
    assert "A atualização desfez a correção do controle" in achada.group(0)
    assert 'data-gesto="atualizacoes-abrir"' not in achada.group(0)
    assert desenho.count('data-gesto="atualizacoes-abrir"') == 1


def test_o_clique_na_linha_abre_as_atualizacoes(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto da linha leva à pergunta das atualizações, sem tocar na máquina."""
    chamadas: list[str] = []
    monkeypatch.setattr(atualizacoes, "_conferir_em_fundo", lambda: chamadas.append("conferiu"))
    monkeypatch.setattr(atualizacoes, "_repintar", lambda: chamadas.append("repintou"))
    atualizacoes.TELA["vista"] = "fechada"
    atender = gesto_da_pagina("09-sistema.html", a09.GESTO_DAS_CURAS)
    assert atender is not None
    atender(None, {}, None)  # type: ignore[arg-type]
    assert atualizacoes.TELA["vista"] == "pergunta"
    assert chamadas == ["conferiu", "repintou"]
