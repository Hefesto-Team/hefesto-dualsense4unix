#!/usr/bin/env python3
"""O `blocos` do pacote atravessa o `normalizar` e chega ao JS.

POR QUE ESTA RÉGUA EXISTE, e o defeito ficou DOIS DIAS vivo e calado:
`pacotes.normalizar()` tinha um ramo `if isinstance(valor, dict): continue` que
comia toda chave cujo valor fosse dicionário — e `blocos` é um dicionário de
`seletor CSS -> HTML pronto`. O `BOOTSTRAP` do piloto sabe consumi-lo desde
01/09/2026 (`hefesto_vivo.py`, o laço sobre `p.blocos`), e `a08_conexoes.py`
o emite para trocar o MAPA DO GABINETE dela inteiro.

Resultado medido em 02/09/2026: o mapa do gabinete e a lista de aparelhos da
aba Conexões nunca chegavam à tela pelo tique, e **nada acusava**. Quatro
frentes independentes da leva daquele dia o acharam, cada uma pelo seu lado —
e nenhuma tinha território para curá-lo, porque a cura mora no `__init__.py`.

A RÉGUA MORDE assim: devolva o `continue` cego ao `normalizar` (ou apague o
bloco que copia `blocos` para a saída) e os três primeiros testes reprovam.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

from pacotes import normalizar


def test_o_blocos_atravessa_o_normalizar() -> None:
    """A chave chega à carga com o conteúdo intacto."""
    carga = normalizar({"blocos": {".mm-faces": "<b>mapa</b>", ".mm-lista": "<li>x</li>"}})
    assert "blocos" in carga, (
        "o `blocos` sumiu do `normalizar` — é exatamente o defeito de 02/09/2026: "
        "o mapa do gabinete dela é montado a cada tique e jogado fora"
    )
    assert carga["blocos"] == {".mm-faces": "<b>mapa</b>", ".mm-lista": "<li>x</li>"}


def test_o_pacote_da_aba_conexoes_emite_blocos_e_ele_sobrevive() -> None:
    """A aba que USA o mecanismo continua chegando à tela — não só o caso sintético."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py").read_text(
        encoding="utf-8"
    )
    assert '"blocos"' in fonte, (
        "a aba 08 deixou de emitir `blocos`; se isso foi de propósito, apague esta régua "
        "com a razão escrita — não a deixe passar por vacuidade"
    )
    seletores = re.findall(r'"(\.[a-z-]+)":', fonte)
    assert seletores, "nenhum seletor CSS achado no `blocos` da aba 08"
    carga = normalizar({"blocos": {s: "<i>x</i>" for s in seletores[:2]}})
    assert set(carga.get("blocos") or {}) == set(seletores[:2])


def test_o_bootstrap_do_piloto_consome_a_chave_com_esse_nome() -> None:
    """As duas pontas usam a MESMA palavra.

    Sem isto, renomear de um lado só refaz o defeito: o pacote emite, o
    `normalizar` deixa passar, e o JS procura outra chave.
    """
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8"
    )
    assert "p.blocos" in piloto, "o BOOTSTRAP parou de ler `p.blocos` — as pontas divergiram"


@pytest.mark.parametrize("chave", ["estrutura", "cobertura_detalhada", "qualquer_dict"])
def test_dict_que_nao_e_blocos_continua_descartado(chave: str) -> None:
    """A cura é CIRÚRGICA: só o `blocos` atravessa.

    O ramo que descarta dicionário existe por uma razão medida — escrever
    `[object Object]` numa caixa é pior que não escrever. A cura não pode
    reabrir isso.
    """
    carga = normalizar({chave: {"a": 1}})
    assert chave not in carga
    assert chave not in carga["mesa"]


def test_blocos_vazio_nao_vira_chave() -> None:
    """`{}` não é carga — é ruído no `_json` de todo tique."""
    assert "blocos" not in normalizar({"blocos": {}})
