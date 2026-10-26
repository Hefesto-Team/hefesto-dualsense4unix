"""A janela da extensão com modos não diz que não tem opções, e a barra fora da porta se mostra.

A-JANELA-DA-EXTENSAO-COM-MODOS-NAO-DIZ-QUE-NAO-TEM-OPCOES-01 (25/10/2026). Antes, a janela de uma
extensão sem opções na lista e com o controle livre dizia «Esta extensão não tem opções para
ajustar.» logo acima dos modos que o Guardar grava, e a barra «Ao vivo» com a extensão fora da porta
nascia igual à viva e só avisava depois do gesto.

Os blocos da janela e o que conta como ajuste: as opções da lista e o controle livre (a barra grava
formas, os modos vão ao Guardar) contam; os controles dos aparelhos ganham a aba deles. A coluna
«Agora», o «Parar tudo» e as ações sozinhas não se guardam e não tiram o vazio.

MORDIDAS (25/10/2026, executadas sobre a cura e devolvidas, md5 conferido):

- o vazio decidido só pela lista de opções (``vazio = VAZIO_DA_JANELA`` sempre) reprova
  ``test_o_livre_com_ou_sem_modos_nao_diz_que_nao_tem_opcoes``;
- a barra igual nos dois estados (``fora=""`` na chamada da faixa) reprova
  ``test_fora_da_porta_a_barra_nasce_apagada_com_a_dica`` nos cinco estados.
- sem a regra do rastro apagado (o rastro da barra fora da porta segue rosa) reprova
  ``test_a_barra_apagada_nao_e_vermelha``.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    LIVRE,
    TOQUES,
    VIVO,
    _Ponte,
    janela,
)

COM_MODOS = {**LIVRE, "modos": True}
VAZIO = "Esta extensão não tem opções para ajustar."
DICA_FORA = "Toque não está rodando: a barra não chega a ela."


def _miolo(janela: Any, ponte: _Ponte | None = None) -> str:  # noqa: F811
    _, _, abrir = janela
    return str(abrir(ponte or _Ponte(VIVO))["blocos"]["#mod-janela"])


def _trilho(html: str) -> str:
    achado = re.search(r'<div class="mj-trilho[^>]*>', html)
    assert achado, "a janela com o livre tem a barra"
    return achado.group(0)


def _ligar_e_o_supervisor_diz(janela: Any, ctx: Any, lar: Any, estado: str) -> None:  # noqa: F811
    """Ligada pela chave (a permissão arma no primeiro clique) e o supervisor no ``estado``."""
    a07, _, _ = janela
    if a07.ligar_modificacao(ctx, {"v": "toque"}, None).get("armou"):
        a07.ligar_modificacao(ctx, {"v": "toque"}, None)
    lar.estado.parent.mkdir(parents=True, exist_ok=True)
    lar.estado.write_text(json.dumps({"mods": {"toque": {"estado": estado, "motivo": ""}}}),
                          encoding="utf-8")
    a07.REGISTRO.esquecer()
    a07.VIGIA.esquecer()


@pytest.mark.parametrize("livre", [LIVRE, COM_MODOS], ids=["sem-modos", "com-modos"])
def test_o_livre_com_ou_sem_modos_nao_diz_que_nao_tem_opcoes(janela: Any, livre: Any) -> None:  # noqa: F811
    """Prova da D-2510-A-JANELA-COM-O-LIVRE-NAO-DIZ-O-VAZIO."""
    _, instalar, _ = janela
    instalar(opcoes=[dict(livre)])
    html = _miolo(janela)
    assert VAZIO not in html, "a janela diz que não há opções acima do que o Guardar grava"
    assert 'class="mj-faixa"' in html
    assert ("mj-modos" in html) is bool(livre.get("modos"))
    assert '<div class="ja-opcoes"></div>' not in html, "sem opção, a coluna delas não nasce oca"


def test_sem_nada_a_ajustar_a_janela_diz_que_nao_tem_opcoes(janela: Any) -> None:  # noqa: F811
    _, instalar, _ = janela
    instalar()
    assert VAZIO in _miolo(janela)


def test_a_opcao_da_lista_tira_o_vazio_com_ou_sem_o_livre(janela: Any) -> None:  # noqa: F811
    _, instalar, _ = janela
    instalar(opcoes=[dict(TOQUES)])
    assert VAZIO not in _miolo(janela)


def test_a_coluna_agora_sozinha_nao_se_guarda_e_o_vazio_fica(janela: Any) -> None:  # noqa: F811
    _, instalar, _ = janela
    instalar(agora=["nivel"])
    html = _miolo(janela)
    assert VAZIO in html and 'id="mod-agora"' in html


@pytest.mark.parametrize("estado", [None, "desligada", "parou", "voltando", "recusada"],
                         ids=["desligada-na-chave", "ligando", "parou", "voltando", "recusada"])
def test_fora_da_porta_a_barra_nasce_apagada_com_a_dica(janela: Any, ctx: Any, lar: Any,  # noqa: F811
                                                       estado: str | None) -> None:
    """Prova da D-2510-A-BARRA-FORA-DA-PORTA-NASCE-APAGADA."""
    _, instalar, _ = janela
    instalar(opcoes=[dict(COM_MODOS)])
    if estado is not None:
        _ligar_e_o_supervisor_diz(janela, ctx, lar, estado)
    html = _miolo(janela, _Ponte(VIVO, rodando=False))
    trilho = _trilho(html)
    assert 'class="mj-trilho fora"' in trilho, "fora da porta a barra nasce igual à viva"
    assert f'data-dica="{DICA_FORA}"' in trilho, "o porquê é dica da barra, não texto embaixo"
    assert DICA_FORA not in html.replace(f'data-dica="{DICA_FORA}"', ""), "a frase só na dica"
    entrada = html[html.index('<input type="range"', html.index(trilho)):]
    entrada = entrada[:entrada.index(">")]
    assert "disabled" not in entrada, "a barra ainda arrasta: o Gravar grava formas fora da porta"
    assert "mj-gravar" in html, "o Gravar segue na faixa"
    assert "mj-modos" in html, "os modos seguem valendo para o Guardar"


def test_na_porta_a_barra_nasce_viva(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    _, instalar, _ = janela
    instalar(opcoes=[dict(COM_MODOS)])
    _ligar_e_o_supervisor_diz(janela, ctx, lar, "rodando")
    trilho = _trilho(_miolo(janela))
    assert trilho.startswith('<div class="mj-trilho" '), trilho
    assert "data-dica" not in trilho


def test_a_barra_apagada_nao_e_vermelha() -> None:
    css = (pathlib.Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
           / "interface" / "experimental" / "experimental.css").read_text(encoding="utf-8")
    regras = re.findall(r"#mod-janela \.mj-trilho\.fora [^{]*\{[^}]*\}", css)
    assert len(regras) == 2, "a barra apagada e o número dela"
    rastro = re.findall(r"#mod-janela \.mj-faixa:has\(> \.mj-trilho\.fora\) "
                        r"\.mj-rastro:not\(\.gravando\) polyline \{[^}]*\}", css)
    assert len(rastro) == 1, "o rastro da barra apagada segue rosa por cima dela"
    regras += rastro
    assert all("pink" not in r and "red" not in r and "vermelho" not in r for r in regras)
