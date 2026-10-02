#!/usr/bin/env python3
"""O `blocos` do pacote atravessa o `normalizar` e chega ao JS."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

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
    """As duas pontas usam a MESMA palavra."""
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8"
    )
    assert "p.blocos" in piloto, "o BOOTSTRAP parou de ler `p.blocos` — as pontas divergiram"


@pytest.mark.parametrize("chave", ["estrutura", "cobertura_detalhada", "qualquer_dict"])
def test_dict_que_nao_e_blocos_continua_descartado(chave: str) -> None:
    """A cura é CIRÚRGICA: só o `blocos` atravessa."""
    carga = normalizar({chave: {"a": 1}})
    assert chave not in carga
    assert chave not in carga["mesa"]


def test_blocos_vazio_nao_vira_chave() -> None:
    """`{}` não é carga — é ruído no `_json` de todo tique."""
    assert "blocos" not in normalizar({"blocos": {}})
