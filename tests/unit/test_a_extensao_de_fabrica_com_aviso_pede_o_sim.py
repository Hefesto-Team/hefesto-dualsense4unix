"""A extensão de fábrica com aviso pede o sim na chegada.

Sprint A-EXTENSAO-DE-FABRICA-COM-AVISO-PEDE-O-SIM-NA-CHEGADA-01.

Medido em 02/11/2026: a extensão da lista de fábrica com ``ligar: true`` e ``aviso`` chega
instalada e desligada (o aviso nunca se aceita por fábrica), e o cartão na aba dizia só
«Desligada», igual a uma que quem usa desligou. A cura: a chave da desligada que espera o aviso diz
«Espera o sim», com o aviso na dica; o primeiro clique mostra o aviso («Aceitar e ligar») e o
segundo liga, como as outras.

MORDIDA: sem a ``espera`` do ``_extensao_de`` (a07), a chave volta a «Desligada» e
``test_a_de_fabrica_com_aviso_chega_e_espera_o_sim`` reprova.
"""

from __future__ import annotations

import json
import pathlib

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _entrada,
    _fonte,
    _Ponte,
    ctx,
    lar,
)

_AVISO = "Extensão independente. Jogue só o que você comprou."


def _trazer_de_fabrica(lar, tmp_path: pathlib.Path, pasta: pathlib.Path) -> list:  # noqa: F811
    from hefesto_dualsense4unix.mods.de_fabrica_por_endereco import trazer

    lista = tmp_path / "de-fabrica.json"
    linha = {"id": "toque", "endereco": str(pasta), "ligar": True}
    lista.write_text(json.dumps({"formato": 1, "extensoes": [linha]}),  # (noqa-acento)
                     encoding="utf-8")
    return trazer(lugares=lar, arquivo=lista)


def _chave(lista: str, mod_id: str = "toque") -> tuple[str, str, str]:
    """A classe, a palavra e a dica da chave da linha ``mod_id``."""
    trecho = lista.split(f'data-gesto="ligar-modificacao" data-v="{mod_id}"', 1)
    classe = trecho[0].rsplit('class="', 1)[1].split('"', 1)[0]
    dica = trecho[1].split('data-dica="', 1)[1].split('"', 1)[0]
    palavra = trecho[1].split('<span class="txt">', 1)[1].split("<", 1)[0]
    return classe, palavra, dica


def test_a_de_fabrica_com_aviso_chega_e_espera_o_sim(lar, ctx, tmp_path) -> None:  # noqa: F811
    """Prova da D-0211-A-EXTENSAO-DE-FABRICA-COM-AVISO-ESPERA-O-SIM."""
    a07 = _a07()
    feito = _trazer_de_fabrica(lar, tmp_path, _fonte(tmp_path, extra={"aviso": _AVISO}))
    entrada = _entrada(lar, "toque")
    assert [f.o_que for f in feito] == ["instalada"], feito
    assert entrada.ligada is False and entrada.aviso_aceito == "", "a fábrica aceitou o aviso"
    classe, palavra, dica = _chave(a07._a_pintura_agora(ctx)["blocos"][".ext-lista"])
    assert palavra == exp.ROTULO_DA_ESPERA, palavra
    assert classe == "nj-tog" and _AVISO in dica


def test_o_primeiro_clique_mostra_o_aviso_e_o_segundo_liga(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _trazer_de_fabrica(lar, tmp_path, _fonte(tmp_path, extra={"aviso": _AVISO}))
    primeiro = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert primeiro.get("armou") is True and _entrada(lar, "toque").ligada is False
    classe, palavra, dica = _chave(primeiro["blocos"][".ext-lista"])
    assert (classe, palavra) == ("nj-tog pede", exp.ROTULO_DO_SIM) and _AVISO in dica
    segundo = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    entrada = _entrada(lar, "toque")
    assert segundo["recado"] == "Toque ligada." and entrada.ligada is True
    assert entrada.aviso_aceito == _AVISO
    assert _chave(segundo["blocos"][".ext-lista"])[1] == "Ligada"


def test_a_de_fabrica_sem_aviso_liga_na_chegada(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    feito = _trazer_de_fabrica(lar, tmp_path, _fonte(tmp_path))
    assert [f.o_que for f in feito] == ["ligada"] and _entrada(lar, "toque").ligada is True
    assert exp.ROTULO_DA_ESPERA not in a07._a_pintura_agora(ctx)["blocos"][".ext-lista"]


def test_a_que_quem_usa_desligou_diz_desligada(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _trazer_de_fabrica(lar, tmp_path, _fonte(tmp_path, extra={"aviso": _AVISO}))
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    desligou = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert _chave(desligou["blocos"][".ext-lista"])[1] == "Desligada"


def test_a_palavra_da_espera_e_do_desenho() -> None:
    ext = exp.Extensao("t", "Tema", "Muda as cores.", "#", ligada=False, espera="Avisa algo.")
    html = exp.extensao_html(ext)
    assert f'<span class="txt">{exp.ROTULO_DA_ESPERA}</span>' in html
    assert 'data-dica="Avisa algo."' in html
    assert f'<span class="txt">{exp.ROTULO_DO_SIM}</span>' in exp.extensao_html(
        ext._replace(pede="Avisa algo."))
