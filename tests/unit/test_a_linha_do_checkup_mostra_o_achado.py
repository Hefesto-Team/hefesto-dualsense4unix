#!/usr/bin/env python3
"""O que sobrou da linha do Check-up da aba Conexões: o canto da Gestão e a chave do `maquina.json`.

A linha do exame saiu da aba em 04/10/2026 (AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01): cada achado
virou cartão de dica, e as réguas dele moram com os cartões.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))


from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

PACOTE = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
ENSAIO = RAIZ / "mockup/08-conexoes.html"


def test_o_carimbo_e_a_contagem_sairam_do_canto_da_gestao():
    """26/09/2026, pedido para remover essas informações da linha."""
    html = ENSAIO.read_text(encoding="utf-8")
    assert 'data-campo="examinado"' not in html
    assert 'data-campo="conta-gestao"' not in html
    for texto in (html, GERADOR.read_text(encoding="utf-8")):
        inicio = texto.index('for="cx8-2"')
        topo = texto[inicio:texto.index('class="quadro-corpo"', inicio)]
        assert 'class="conta"' not in topo, topo
    pacote = PACOTE.read_text(encoding="utf-8")
    assert '"examinado":' not in pacote and '"conta-gestao":' not in pacote
    assert not hasattr(a08, "_carimbo_do_exame")


@pytest.mark.parametrize(
    "entrada",
    ["aa:bb:cc:00:00:22", "AA-BB-CC-00-00-22", "  aabbcc000022  ", "aabbcc000022", ""],
)
def test_a_chave_do_maquina_json_e_a_do_produto(entrada):
    """`_so_hex` é embrulho de `core.sysfs_leds.norm_mac`, e não a segunda conta."""
    assert a08._so_hex(entrada) == (norm_mac(entrada) or "")


def test_o_so_hex_nunca_devolve_none():
    """`norm_mac` devolve `None` sem um hexa sequer; aqui isso tem de virar `""`."""
    assert norm_mac("zzz") is None
    assert a08._so_hex("zzz") == ""


def test_nao_sobrou_uma_segunda_conta_de_normalizacao_neste_arquivo():
    """A cópia à mão (`.replace(":", "").replace("-", "")`) não pode voltar."""
    fonte = PACOTE.read_text(encoding="utf-8")
    corpo = fonte.split("def _so_hex", 1)[1].split("\ndef ", 1)[0]
    assert 'replace(":", "")' not in corpo, (
        "o `_so_hex` desta aba voltou a normalizar por conta própria — a chave "
        "do `maquina.json` tem um dono só, `core.sysfs_leds.norm_mac`"
    )


def test_o_dataclass_do_exame_ainda_tem_os_campos_que_a_tela_le():
    """Se o `Item` mudar de forma, a tela some sem uma linha de erro."""
    campos = {c.name for c in dataclasses.fields(Item)}
    assert {"chave", "rotulo", "estado", "porque", "cura"} <= campos
