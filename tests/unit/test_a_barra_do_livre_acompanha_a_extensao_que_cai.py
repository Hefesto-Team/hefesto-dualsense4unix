"""A barra do controle livre acompanha a extensão que cai, ou volta, com a janela aberta.

A-BARRA-DO-LIVRE-ACOMPANHA-A-EXTENSAO-QUE-CAI-COM-A-JANELA-ABERTA-01 (25/10/2026). A barra fora
da porta nascia apagada, mas o estado se decidia só ao montar a janela: a extensão que caía com a
janela aberta deixava a barra rosa, e a que voltava a deixava apagada até reabrir. O «Agora» do
mesmo tique já dizia o processo certo.

A cura: a barra tem endereço (``data-campo``, o alvo ``classe`` com a razão na dica, como o botão
cinza da casa), e o tique da janela aberta manda a dica da porta, a mesma função que decide ao
montar. O piloto troca só a classe e a dica do trilho: o ``input`` não sai do documento, e o valor,
o foco e o arrasto ficam.

MORDIDAS (25/10/2026, executadas sobre a cura e devolvidas, md5 conferido):

- o tique sem a dica da porta (a linha da mesa arrancada de ``_com_os_aparelhos``) reprova
  ``test_o_tique_apaga_a_barra_quando_a_extensao_cai_e_acende_quando_volta`` nos cinco estados,
  ``test_a_barra_que_nasce_apagada_acende_no_tique_da_volta``,
  ``test_a_montagem_e_o_tique_dizem_o_mesmo`` nos quatro estados fora da porta e
  ``test_a_barra_apaga_e_acende_no_navegador_sem_perder_o_arrasto``;
- o trilho sem o endereço (os atributos de pintura arrancados de ``faixa_do_livre_html``)
  reprova ``test_o_trilho_tem_o_endereco_nos_dois_estados`` e o do navegador;
- o tique com uma regra própria (``processo == "parou"`` no lugar de ``dica_da_barra_fora``)
  reprova ``test_o_tique_apaga_a_barra_quando_a_extensao_cai_e_acende_quando_volta`` em quatro
  estados e ``test_a_montagem_e_o_tique_dizem_o_mesmo`` em três.
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
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_janela_da_extensao_com_modos_nao_diz_que_nao_tem_opcoes import (
    COM_MODOS,
    DICA_FORA,
    _ligar_e_o_supervisor_diz,
    _trilho,
)

CAMPO = "mod-livre-fora"
#: Os estados do supervisor fora da porta, e o que a chave desligada com a janela aberta faz.
FORA = ["desligada", "parou", "voltando", "recusada", "chave"]


def _tique(janela: Any, ctx: Any) -> dict[str, Any]:  # noqa: F811
    """O tique da aba com a janela aberta: o registro e o supervisor lidos de novo."""
    a07, _, _ = janela
    a07.REGISTRO.esquecer()
    a07.VIGIA.esquecer()
    return dict(a07.pacote(ctx))


def _cair(janela: Any, ctx: Any, lar: Any, como: str) -> None:  # noqa: F811
    """A extensão sai da porta com a janela aberta: o supervisor diz ``como`` ou a chave desliga."""
    a07, _, _ = janela
    if como == "chave":
        a07.ligar_modificacao(ctx, {"v": "toque"}, None)
        return
    lar.estado.write_text(json.dumps({"mods": {"toque": {"estado": como, "motivo": ""}}}),
                          encoding="utf-8")


def _abrir_na_porta(janela: Any, ctx: Any, lar: Any) -> str:  # noqa: F811
    _, instalar, abrir = janela
    instalar(opcoes=[dict(COM_MODOS)])
    _ligar_e_o_supervisor_diz(janela, ctx, lar, "rodando")
    return str(abrir(_Ponte(VIVO))["blocos"]["#mod-janela"])


# -- 1. o tique leva a porta à barra ----------------------------------------------------------


@pytest.mark.parametrize("como", FORA)
def test_o_tique_apaga_a_barra_quando_a_extensao_cai_e_acende_quando_volta(
        janela: Any, ctx: Any, lar: Any, como: str) -> None:  # noqa: F811
    # D-2510-A-BARRA-FORA-DA-PORTA-NASCE-APAGADA
    montada = _abrir_na_porta(janela, ctx, lar)
    assert 'class="mj-trilho" ' in _trilho(montada)
    na_porta = _tique(janela, ctx)
    assert na_porta[CAMPO] == "", "na porta, o tique não apaga a barra"
    _cair(janela, ctx, lar, como)
    caiu = _tique(janela, ctx)
    assert caiu[CAMPO] == DICA_FORA, f"a extensão {como} e a barra segue rosa: {caiu.get(CAMPO)!r}"
    assert caiu["blocos"]["#mod-janela"] == montada, (
        "o tique refez a janela: a barra que o dedo arrasta sairia do documento")
    if como == "chave":
        _ligar_e_o_supervisor_diz(janela, ctx, lar, "rodando")
    else:
        lar.estado.write_text(json.dumps({"mods": {"toque": {"estado": "rodando", "motivo": ""}}}),
                              encoding="utf-8")
    voltou = _tique(janela, ctx)
    assert voltou[CAMPO] == "", "a extensão voltou e a barra segue apagada"
    assert voltou["blocos"]["#mod-janela"] == montada


def test_a_barra_que_nasce_apagada_acende_no_tique_da_volta(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    _, instalar, abrir = janela
    instalar(opcoes=[dict(COM_MODOS)])
    _ligar_e_o_supervisor_diz(janela, ctx, lar, "parou")
    montada = str(abrir(_Ponte(VIVO))["blocos"]["#mod-janela"])
    assert 'class="mj-trilho fora"' in _trilho(montada)
    assert _tique(janela, ctx)[CAMPO] == DICA_FORA
    lar.estado.write_text(json.dumps({"mods": {"toque": {"estado": "rodando", "motivo": ""}}}),
                          encoding="utf-8")
    voltou = _tique(janela, ctx)
    assert voltou[CAMPO] == "", "a extensão voltou e a barra segue apagada até reabrir"
    assert voltou["blocos"]["#mod-janela"] == montada


@pytest.mark.parametrize("estado", ["rodando", "parou", "voltando", "recusada", "desligada"])
def test_a_montagem_e_o_tique_dizem_o_mesmo(janela: Any, ctx: Any, lar: Any,  # noqa: F811
                                            estado: str) -> None:
    """Uma regra só: a dica que o trilho nasce com é a que o tique manda no mesmo estado."""
    _, instalar, abrir = janela
    instalar(opcoes=[dict(COM_MODOS)])
    _ligar_e_o_supervisor_diz(janela, ctx, lar, estado)
    trilho = _trilho(str(abrir(_Ponte(VIVO))["blocos"]["#mod-janela"]))
    dica = re.search(r'data-dica="([^"]*)"', trilho)
    assert _tique(janela, ctx)[CAMPO] == (dica.group(1) if dica else "")


def test_sem_o_livre_o_tique_nao_fala_da_barra(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    _, instalar, abrir = janela
    instalar(agora=["nivel"])
    _ligar_e_o_supervisor_diz(janela, ctx, lar, "parou")
    abrir(_Ponte(VIVO))
    assert _tique(janela, ctx)[CAMPO] == "", "a janela sem barra não tem barra a apagar"


def test_o_trilho_tem_o_endereco_nos_dois_estados(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    """O alvo ``classe`` com a razão: o piloto acende ``fora`` e escreve a dica, ou tira as duas."""
    trilho = _trilho(_abrir_na_porta(janela, ctx, lar))
    for atributo in (f'data-campo="{CAMPO}"', 'data-hef-alvo="classe"', 'data-hef-classe="fora"',
                     'data-hef-razao="sim"'):
        assert atributo in trilho, f"o trilho na porta não tem {atributo}: {trilho}"
    _cair(janela, ctx, lar, "parou")
    a07, _, abrir = janela
    a07.REGISTRO.esquecer()
    apagado = _trilho(str(abrir(_Ponte(VIVO))["blocos"]["#mod-janela"]))
    assert f'data-campo="{CAMPO}"' in apagado and 'class="mj-trilho fora"' in apagado


# -- 2. no navegador: o piloto troca a classe e a dica, e o dedo continua na barra -------------

_LER = """window.ler = () => { const t = document.querySelector('#mod-janela .mj-trilho');
  return JSON.stringify({fora: t.classList.contains('fora'), dica: t.getAttribute('data-dica'),
    mesmo: t.querySelector('input') === window.r, valor: window.r.value,
    saida: t.querySelector('output').textContent, foco: document.activeElement === window.r}); };"""


def test_a_barra_apaga_e_acende_no_navegador_sem_perder_o_arrasto(
        janela: Any, ctx: Any, lar: Any, tmp_path: pathlib.Path) -> None:  # noqa: F811
    import os
    import subprocess
    import sys

    from hefesto_dualsense4unix.interface import hefesto_vivo
    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import SONDA

    montada = _abrir_na_porta(janela, ctx, lar)
    porta = _tique(janela, ctx)
    _cair(janela, ctx, lar, "parou")
    caiu = _tique(janela, ctx)
    lar.estado.write_text(json.dumps({"mods": {"toque": {"estado": "rodando", "motivo": ""}}}),
                          encoding="utf-8")
    voltou = _tique(janela, ctx)

    def carga(tique: dict[str, Any]) -> str:
        return json.dumps({"blocos": {"#mod-janela": tique["blocos"]["#mod-janela"]},
                           "mesa": {CAMPO: tique[CAMPO]}})

    pagina = tmp_path / "janela.html"
    pagina.write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                      '<div id="mod-janela"></div></body></html>', encoding="utf-8")
    js = lambda c: ["js", c]  # noqa: E731
    passos = [
        js(hefesto_vivo.BOOTSTRAP),
        js(f"window.__hef.pintar({json.dumps({'blocos': {'#mod-janela': montada}})}); "
           f"window.r = document.querySelector('#mod-janela .mj-trilho input'); {_LER} "
           "r.focus(); r.value = '37'; "
           "r.dispatchEvent(new Event('input', {bubbles: true})); ler()"),
        js(f"window.__hef.pintar({carga(caiu)}); ler()"),
        js(f"window.__hef.pintar({carga(caiu)}); ler()"),
        js(f"window.__hef.pintar({carga(voltou)}); ler()"),
        js(f"window.__hef.pintar({carga(porta)}); ler()"),
    ]
    filho = subprocess.run([sys.executable, "-c", SONDA, str(pagina)],
                           input=json.dumps({"barra": (1212, 809, passos)}),
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                           capture_output=True, text=True, timeout=300)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    instalou, *lidos = json.loads(filho.stdout.strip().splitlines()[-1])["barra"]
    assert instalou == "ok" and all(isinstance(v, str) for v in lidos), lidos
    antes, apagou, de_novo, acendeu, segue = (json.loads(v) for v in lidos)
    assert antes == {"fora": False, "dica": None, "mesmo": True, "valor": "37", "saida": "37",
                     "foco": True}, antes
    assert apagou["fora"] and apagou["dica"] == DICA_FORA, (
        f"a extensão caiu e a barra segue rosa: {apagou}")
    for lido in (apagou, de_novo, acendeu, segue):
        assert lido["mesmo"] and lido["valor"] == "37" and lido["saida"] == "37" and lido["foco"], (
            f"o tique levou a barra que o dedo arrastava: {lido}")
    assert de_novo == apagou, "o mesmo tique de novo mexeu na barra"
    assert not acendeu["fora"] and acendeu["dica"] is None, (
        f"a extensão voltou e a barra segue apagada: {acendeu}")
    assert segue == acendeu
