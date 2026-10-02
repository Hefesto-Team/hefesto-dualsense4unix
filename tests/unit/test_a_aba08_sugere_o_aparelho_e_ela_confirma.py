#!/usr/bin/env python3
"""A TELA SUGERE O APARELHO, E ELA CONFIRMA — e nada é gravado sem o toque dela."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "08-conexoes.html"


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


class PonteDeMentira:
    """Guarda o que foi pedido à ponte, e nunca fala com daemon nenhum."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return True

        return registrar


class AparelhoDeMentira:
    def __init__(self, especie: str, grau: str) -> None:
        self.especie = especie
        self.grau = grau


class CensoDeMentira:
    """O censo do barramento com os nós que a régua escolher — nunca o `/sys`."""

    def __init__(self, por_no: dict[str, AparelhoDeMentira]) -> None:
        self._por_no = por_no

    def aparelho(self, no: str) -> AparelhoDeMentira | None:
        return self._por_no.get(no)


def _rotulos(a08) -> dict[str, str]:
    """`{rótulo: id}` — PERGUNTADO ao dono (`secao_mesa._TIPOS_DE_RADIO`)."""
    para_id, _ = a08._tipos_de_radio()
    assert para_id, "sem a lista do produto esta régua não mede nada"
    return para_id


def _com_o_censo(a08, monkeypatch, por_no: dict[str, tuple[str, str]]) -> None:
    censo = CensoDeMentira(
        {no: AparelhoDeMentira(especie, grau) for no, (especie, grau) in por_no.items()}
    )
    monkeypatch.setattr(a08, "_censo", lambda *_a, **_k: censo)


def test_a_palavra_do_kernel_que_ja_e_a_dela_vira_sugestao(a08, monkeypatch):
    """"Teclado" (kernel) e "Teclado" (lista dela) casam sem tabela nenhuma."""
    _com_o_censo(a08, monkeypatch, {"/sys/x": ("Teclado", "lido")})
    assert a08._sugestao_do_vizinho("/sys/x", _rotulos(a08)) == "Teclado"


def test_a_camera_do_kernel_vira_a_webcam_dela(a08, monkeypatch):
    """O caso que ELA respondeu, e o único da tabela que a bancada exercita."""
    _com_o_censo(a08, monkeypatch, {"/sys/cam": ("Câmera", "lido")})
    assert a08._sugestao_do_vizinho("/sys/cam", _rotulos(a08)) == "Webcam"


def test_a_sugestao_nunca_sai_como_resposta(a08):
    """`— Teclado? —`, e não `Teclado`. A moldura É a marca de que é sugestão."""
    pergunta = a08._a_pergunta()
    sugerida = a08._pergunta_sugerida("Teclado", pergunta)
    assert sugerida != "Teclado"
    assert "Teclado" in sugerida
    assert sugerida not in _rotulos(a08), (
        "a sugestão caiu em cima de uma resposta da lista dela — o gesto a "
        "gravaria no `maquina.json` como se ela tivesse respondido")


def test_a_moldura_sai_da_pergunta_e_nao_e_digitada(a08):
    """A régua PERGUNTA: troque a pergunta e a moldura vai junto."""
    assert a08._moldura_da_pergunta("— O que é? —") == ("— ", "? —")
    assert a08._pergunta_sugerida("Mouse", "«O que é isso?»") == "«Mouse?»"
    assert a08._pergunta_sugerida("Mouse", "O que e") == "Mouse"


def test_a_classe_ff_nao_sugere_nada(a08, monkeypatch):
    """Grau `desconhecido` é o fabricante declinando de classificar."""
    _com_o_censo(a08, monkeypatch, {"/sys/ff": ("Não identificado", "desconhecido")})
    assert a08._sugestao_do_vizinho("/sys/ff", _rotulos(a08)) == ""


def test_a_palavra_sem_par_na_lista_dela_nao_vira_sugestao(a08, monkeypatch):
    """"Impressora" o kernel diz; a lista dela não a tem. Então não há sugestão."""
    _com_o_censo(a08, monkeypatch, {"/sys/p": ("Impressora", "lido")})
    assert a08._sugestao_do_vizinho("/sys/p", _rotulos(a08)) == ""


def test_o_no_vazio_e_o_censo_ausente_nao_sugerem(a08, monkeypatch):
    """Sem nó e sem censo, a tela não inventa. Ausência não é resposta."""
    _com_o_censo(a08, monkeypatch, {"/sys/x": ("Teclado", "lido")})
    assert a08._sugestao_do_vizinho("", _rotulos(a08)) == ""
    monkeypatch.setattr(a08, "_censo", lambda *_a, **_k: None)
    assert a08._sugestao_do_vizinho("/sys/x", _rotulos(a08)) == ""


def test_toda_sugestao_possivel_cabe_na_lista_dela(a08):
    """O destino de cada equivalência EXISTE em `_TIPOS_DE_RADIO`."""
    rotulos = _rotulos(a08)
    fora = sorted(d for d in a08._SUGESTAO_DO_KERNEL.values() if d not in rotulos)
    assert fora == [], f"destino que a lista dela não oferece: {fora}"


def test_o_conjunto_das_perguntas_sugeridas_cobre_a_lista_inteira(a08):
    """Toda resposta da lista dela tem a sua pergunta sugerida reconhecida."""
    pergunta = a08._a_pergunta()
    sugeridas = a08._perguntas_sugeridas()
    for rotulo in _rotulos(a08):
        assert a08._pergunta_sugerida(rotulo, pergunta) in sugeridas


def _declarou(ponte: PonteDeMentira) -> list[dict[str, Any]]:
    return [c[1][0] for c in ponte.chamadas if c[0] == "machine_declare"]


@pytest.fixture
def um_vizinho(a08, monkeypatch):
    """UM rádio na tela, e o disco relido vira dublê."""
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {"vizinhos": [{"id": "3554:fa09"}]})
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)


def _clicar(pac, a08, ponte, valor: str) -> None:
    fn = pac.gesto_da_pagina(PAGINA, "vizinho-o-que-e")
    assert fn is not None, "vizinho-o-que-e perdeu o dono"
    ctx = pac.Contexto(state={"active_profile": "regua"}, mesa=[],
                       conectados=[], estados={})
    fn(ctx, {"alvo": "3554:fa09", "valor": valor, "evento": "click"}, ponte)


def test_o_gesto_nao_grava_a_sugestao_como_resposta_dela(pac, a08, um_vizinho):
    """A REGRA INTEIRA numa linha: sugestão escolhida grava `tipo: None`."""
    ponte = PonteDeMentira()
    sugerida = a08._pergunta_sugerida("Teclado", a08._a_pergunta())
    _clicar(pac, a08, ponte, sugerida)
    assert _declarou(ponte) == [{"mesa": {"radios": {"3554:fa09": {"tipo": None}}}}]


def test_o_gesto_nao_recusa_calado_na_sugestao(pac, a08, um_vizinho):
    """Sem a linha da sugestão, isto levanta `ValueError` — recusa CALADA.

    `hefesto_vivo._recusou_dizendo` só leva `RuntimeError` à tela: um
    `ValueError` some no terminal de quem lançou a janela, e o segundo clique
    parece o primeiro. É a forma dos quatro gestos que esta aba já tem assim.
    """
    ponte = PonteDeMentira()
    for rotulo in _rotulos(a08):
        _clicar(pac, a08, ponte, a08._pergunta_sugerida(rotulo, a08._a_pergunta()))


def test_a_resposta_dela_continua_gravando(pac, a08, um_vizinho):
    """A confirmação — um toque — grava, e grava o ID do esquema, não o rótulo."""
    ponte = PonteDeMentira()
    _clicar(pac, a08, ponte, "Webcam")
    assert _declarou(ponte) == [{"mesa": {"radios": {"3554:fa09": {"tipo": "webcam"}}}}]


def test_a_palavra_que_nao_e_da_lista_continua_recusando(pac, a08, um_vizinho):
    """A trava do pydantic continua de pé: rótulo estranho não chega ao disco."""
    ponte = PonteDeMentira()
    with pytest.raises(ValueError):
        _clicar(pac, a08, ponte, "Fone sem fio da TV")
    assert _declarou(ponte) == []


def test_o_toque_no_selo_so_abre_e_o_rotulo_de_fora_da_tela_recusa(pac, a08, um_vizinho):
    """O selo não carrega resposta; e um alvo que não foi à tela não grava.

    ERA `test_a_pagina_tem_o_endereco_da_pergunta_uma_vez_por_vizinho`, que
    contava a `<option data-campo="vizinho-pergunta">` de cada `<select>` — a
    fileira dos vizinhos saiu em 23/09/2026 (TRANSPLANTE-DA-SECAO-01). O
    endereço de hoje é o selo (`data-gesto="vizinho-o-que-e" data-alvo`) e o
    painel «O que é este rádio?», cujos botões levam a resposta no `value`.

    MORDE: tire o `if not rotulo` do gesto e o toque no selo cai no `raise`;
    tire a conferência do alvo e o segundo caso grava.
    """
    ponte = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "vizinho-o-que-e")
    ctx = pac.Contexto(state={}, mesa=[], conectados=[], estados={})
    assert fn(ctx, {"alvo": "3554:fa09", "valor": "", "evento": "click"}, ponte) == {
        "armou": True}
    with pytest.raises(ValueError):
        fn(ctx, {"alvo": "046d:08e5", "valor": "Webcam", "evento": "click"}, ponte)
    assert _declarou(ponte) == []


def test_a_pagina_tem_o_selo_e_o_painel_de_cada_vizinho():
    """A tela tem onde pousar: um selo por vizinho e um molde de respostas."""
    import re

    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    selos = set(re.findall(
        r'<button class="selo-fora vizinho(?: sem-nome)?"[^>]*data-gesto="vizinho-o-que-e" '
        r'data-alvo="([^"]+)"', html))
    paineis = set(re.findall(
        r'<template class="painel-molde" data-painel="o-que-e" data-alvo="([^"]+)"', html))
    assert selos, "o desenho perdeu os selos dos vizinhos"
    assert selos == paineis, f"selos {sorted(selos)}, painéis {sorted(paineis)}"
    assert re.search(r'data-gesto="vizinho-o-que-e" data-alvo="[^"]+" value="Webcam"',
                     html), "as respostas saíram do `value` do botão do painel"
