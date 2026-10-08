"""A-LINHA-DO-EXTERNO-VOLTA-AOS-30-PX-E-A-COR-FORA-DA-LISTA-SE-ESCOLHE-01: a cor do externo.

A docstring de ``ControleDeclarado`` prometia um «campo "Outra"» de texto livre que a tela nunca
teve (a janela GTK que o tinha saiu no ``f1dd18fd8``). A decisão por delegação de 08/10/2026, a
validar pelo usuário, é a do caminho que não tira nada: a tela continua com a lista dos nomes de
fábrica, e as duas docstrings passam a dizer o que ela faz. O que se mede aqui, com o
``maquina.json`` dublado no ponto em que a mesa o lê:

* o que a docstring afirma que a tela oferece, a tela oferece (lido da saída do gerador);
* a cor escrita à mão no arquivo APARECE na lista, não pinta nada e não derruba o cartão;
* escolher um nome da lista no lugar dela grava o nome, e a lista em branco apaga.

TUDO É DE MENTIRA: faixa forjada ``aa:bb:cc``, nada chega a daemon. Mordida: devolver o
«campo "Outra"» à docstring reprova a primeira; tirar o ``atual`` da lista, a segunda.
"""
from __future__ import annotations

import inspect
import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import mesa_viva
from hefesto_dualsense4unix.interface.pacotes import Contexto, gesto_da_pagina
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as conexoes
from hefesto_dualsense4unix.utils.maquina import ControleDeclarado, MaquinaConfig

CHAVE = "aabbcc000031"
A_MAO = "Verde Imaginário"


def _externo() -> dict[str, Any]:
    return {"name": "Controle de teste", "vid": "2dc8", "pid": "6003", "bus": "bluetooth",
            "uniq": "aa:bb:cc:00:00:31", "driver": "hid-generic", "player_slot": 3}


def _ctx() -> Contexto:
    return Contexto(state={"connected": True}, mesa=[], conectados=[], externos=[_externo()])


def _ela(monkeypatch: pytest.MonkeyPatch, **campos: Any) -> None:
    declaracao = MaquinaConfig.model_validate({"controles": {CHAVE: campos}})
    monkeypatch.setattr(mesa_viva, "_declaracao_do_disco", lambda: declaracao)


def _opcoes_da_cor(html: str) -> list[tuple[str, bool]]:
    """``(valor, selecionada)`` de cada opção da lista da cor, lidas da saída do gerador."""
    lista = re.search(r'<select[^>]*data-gesto="externo-cor".*?</select>', html, re.S)
    assert lista, f"a lista da cor não está no cartão: {html}"
    return [(m.group(1), "selected" in m.group(2))
            for m in re.finditer(r'<option value="([^"]*)"([^>]*)>', lista.group(0))]


def test_o_que_a_docstring_diz_que_a_tela_oferece_a_tela_oferece(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Se a docstring de `ControleDeclarado` ou a de `a_declaracao_do_externo` nomeia um campo
    «Outra», a lista da Conexões tem de oferecer uma opção com esse rótulo; hoje ela só tem os
    nomes de fábrica, e as duas docstrings deixaram de prometer o texto livre."""
    _ela(monkeypatch)
    html = conexoes.declaracao_do_externo_para_editar(_externo())
    oferecidas = {v for v, _ in _opcoes_da_cor(html)}
    for dono in (ControleDeclarado, conexoes.a_declaracao_do_externo):
        texto = inspect.getdoc(dono) or ""
        for promessa in re.findall(r'(?:campo|opção)\s+["«]([^"»]+)["»]', texto):
            assert promessa in oferecidas, (
                f"{getattr(dono, '__name__', dono)} promete «{promessa}» e a lista não o oferece")
        assert "texto livre porque a tela oferece" not in " ".join(texto.split())


def test_a_cor_escrita_a_mao_aparece_na_lista_e_nao_pinta(monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch, cor=A_MAO)
    opcoes = _opcoes_da_cor(conexoes.declaracao_do_externo_para_editar(_externo()))
    assert (A_MAO, True) in opcoes, "o nome escrito à mão tem de aparecer, selecionado"
    assert sum(1 for _, marcada in opcoes if marcada) == 1
    assert conexoes.a_declaracao_do_externo(_externo())["cor"] == ""
    atributos, _ = conexoes.marcas_do_externo(_externo(), "span")
    assert "border-color" not in atributos


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[dict] = []

    def machine_declare(self, carga: dict) -> Any:
        self.chamadas.append(carga)
        return (True, None)


def _escolher(valor: str) -> list[dict]:
    ponte = _Ponte()
    gesto_da_pagina(conexoes.PAGINA, "externo-cor")(
        _ctx(), {"externo": "aa:bb:cc:00:00:31", "valor": valor}, ponte)
    return ponte.chamadas


def test_trocar_a_cor_a_mao_por_um_nome_da_lista_grava_o_nome(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch, cor=A_MAO)
    assert _escolher("Cosmic Red") == [{"controles": {CHAVE: {"cor": "Cosmic Red"}}}]


def test_a_lista_em_branco_apaga_a_cor_a_mao(monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch, cor=A_MAO)
    assert _escolher("") == [{"controles": {CHAVE: {"cor": None}}}]
