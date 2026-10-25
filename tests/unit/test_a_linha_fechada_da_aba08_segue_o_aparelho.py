#!/usr/bin/env python3
"""A LINHA FECHADA DA ABA 08 SEGUE O APARELHO — e a confissão segue a bancada.

**03/09/2026.** Três coisas desta aba decidiam o que mostrar pela POSIÇÃO NO
DESENHO, e não pelo que o daemon disse. As três foram medidas na bancada no
mesmo dia, com **um** controle na mesa, no cabo, com a ponte de microfone
DESLIGADA no `maquina.json`:

===========================  ==================================  ==============
o que a tela dizia           o que a máquina dizia               quem mandava
===========================  ==================================  ==============
"Microfone **Ligado**"       `microfone` não declarado           o mockup
"pelo cabo · Placa…" no P1   certo por coincidência: o P2 do     o mockup
e "pelo rádio · Pela         desenho dizia rádio, e a mesa
ponte" no P2                 dela não tem P2
"…não consegui conferir:     a bancada tem **UMA**          o mockup
**três coisas**"             lacuna (`especie`)
===========================  ==================================  ==============

AS TRÊS CURAS TÊM A MESMA FORMA, e é a desta casa: o valor ganha ENDEREÇO no
gerador e DONO no pacote. A tabela do "por extenso" mudou-se para o pacote, e a
confissão passa a vir de `mapa_da_mesa.confissao_do_desenho`, que já era o dono
das frases.

**23/10/2026:** a linha do microfone saiu da 08 (o estado é o selo `est-mic`
do cartão), e o pacote seguia emitindo `mic-caminho` e `mic-dica` para
endereço nenhum. Os dois saíram com as funções que só eles chamavam, e a régua
da coluna passou a exigir endereço para toda chave.

**AS DUAS METADES SE PRECISAM** (a lição do `IDENTIDADE-VEM-DE-CIMA-01`): um
`data-campo` sem ninguém escrevendo nele troca um congelado por um vazio, e um
pacote que emite para um endereço que não existe escreve zero e some.

A MORDIDA — medida, e cada uma reprova SÓ o seu:

* tire o `data-campo="confissao-conta"` do `aba08.py` e regenere  →
  `test_os_enderecos_novos_existem_na_bancada` reprova (1);
* devolva `"mic-caminho"` à coluna do pacote  →
  `test_toda_chave_da_coluna_tem_endereco_na_08` reprova (2, as duas páginas);
* faça `_confissao_do_mapa` devolver a conta da CENA em vez da bancada  →
  `test_a_confissao_conta_as_lacunas_da_bancada` reprova (1).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _ctx() -> Any:
    """Uma mesa de dois: o primeiro no CABO, o segundo no RÁDIO."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_os_enderecos_novos_existem_na_bancada() -> None:
    """Os cinco endereços desta leva, no arquivo que o produto vai renderizar.

    O ALVO ENTRA NA BUSCA, e não só o `data-campo`: o `luz-trava` sem
    `data-hef-alvo="classe"` viraria TEXTO — o botão passaria a se chamar
    "cabo" em vez de acender ou apagar. Endereço certo com alvo errado é um
    defeito que a tela mostra e a contagem de campos não vê.
    """
    html = BANCADA.read_text(encoding="utf-8")
    esperados = (
        'data-campo="confissao-nada" data-hef-alvo="classe" '
        'data-hef-classe="sumido" data-hef-quando="sim"',
        'data-campo="confissao-conta"',
    )
    for endereco in esperados:
        assert endereco in html, (
            f"o endereço `{endereco}` não está na bancada da 08 — sem ele o "
            f"produto não tem onde escrever, e a tela volta ao desenho")
    assert 'data-campo="confissao-dica"' not in html, (
        "a dica da confissão voltou à bancada da 08")


def test_o_pacote_emite_o_que_a_bancada_enderecou() -> None:
    """Todo `data-campo` POR CONTROLE da bancada tem quem o escreva."""
    html = BANCADA.read_text(encoding="utf-8")
    linhas = re.findall(
        r'<div class="gc-item gc-p\d"(?! [^>]*\bfora\b)[^>]*>.*?(?=<div class="gc-item)',
        html, flags=re.S)
    assert linhas, "não achei uma linha de controle conectado na bancada da 08"
    na_tela = {c for bloco in linhas
               for c in re.findall(r'data-campo="([^"]+)"', bloco)}
    pac = _pacote().pacote(_ctx())
    emitidos = {k for coluna in pac["colunas"].values() for k in coluna}
    emitidos |= {k for k, v in pac.items()
                 if not isinstance(v, (dict, list))}
    sem_dono = na_tela - emitidos
    assert not sem_dono, (
        f"a linha do controle na bancada da 08 tem endereço sem ninguém que o "
        f"escreva: {sorted(sem_dono)} — endereço mudo é congelado com outro nome")


#: As chaves da coluna que são DADO da carga, não texto da linha: quem as lê
#: é a própria carga (`via` indexa o transporte, `bateria` entra no `nome`), e
#: nenhuma tem `data-campo` na 08. A lista é fechada e conferida abaixo nos dois
#: sentidos: chave que ganhar endereço, ou deixar de ser emitida, sai daqui.
DADOS_DA_COLUNA = frozenset({"via", "bateria", "ponte", "fragil"})

PAGINAS = {
    "mockup": BANCADA,
    "publicado": RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html",
}


@pytest.mark.parametrize("qual", sorted(PAGINAS))
def test_toda_chave_da_coluna_tem_endereco_na_08(qual: str) -> None:
    # D-2510-A-COLUNA-DA-08-NAO-EMITE-CAMPO-SEM-ENDERECO
    """Campo da coluna sem `data-campo` na página escreve zero e some calado."""
    html = PAGINAS[qual].read_text(encoding="utf-8")
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', html))
    pac = _pacote().pacote(_ctx())
    emitidas = {k for coluna in pac["colunas"].values() for k in coluna}
    sem_endereco = emitidas - na_pagina - DADOS_DA_COLUNA
    assert not sem_endereco, (
        f"a coluna do pacote da 08 emite {sorted(sem_endereco)} e a página "
        f"({qual}) não tem `data-campo` para recebê-los — o valor não chega à tela")
    assert emitidas >= DADOS_DA_COLUNA, (
        f"{sorted(DADOS_DA_COLUNA - emitidas)} saiu da coluna: tire de `DADOS_DA_COLUNA`")
    assert not DADOS_DA_COLUNA & na_pagina, (
        f"{sorted(DADOS_DA_COLUNA & na_pagina)} ganhou endereço na página: tire de "
        f"`DADOS_DA_COLUNA`, que a régua passa a cobri-lo")


def _com_lacunas(monkeypatch: Any, quantas: int) -> dict[str, str]:
    """O que o pacote emite quando a bancada tem `quantas` lacunas."""
    from hefesto_dualsense4unix.interface import logica_do_mapa as mapa_da_mesa

    pac = _pacote()
    monkeypatch.setattr(pac, "_bancada", lambda: object())
    monkeypatch.setattr(
        mapa_da_mesa, "confissao_do_desenho",
        lambda _b: tuple(f"lacuna número {n}" for n in range(quantas)))
    return pac._confissao_do_mapa()


def test_a_confissao_conta_as_lacunas_da_bancada(monkeypatch: Any) -> None:
    """A conta por extenso é a de `confissao_do_desenho`, e não a da cena.

    A CENA TEM TRÊS. Se a régua desse verde com a bancada em uma lacuna
    dizendo "três coisas", ela estaria medindo o mockup — que é exatamente o
    defeito que esta leva fechou.
    """
    pac = _pacote()
    for quantas in (1, 2, 3):
        campos = _com_lacunas(monkeypatch, quantas)
        assert campos["confissao-conta"] == pac.palavra_da_conta(quantas), (
            f"com {quantas} lacuna(s) a tela diria "
            f"{campos['confissao-conta']!r}")
        assert campos["confissao-nada"] == "", (
            "há o que confessar e a linha se apagaria")
        assert "confissao-dica" not in campos, (
            f"a confissão voltou a mandar a dica: {campos!r}")


def test_sem_lacuna_a_linha_da_confissao_some(monkeypatch: Any) -> None:
    """Zero lacuna apaga a linha — a mesma regra da janela do desenho."""
    campos = _com_lacunas(monkeypatch, 0)
    assert campos["confissao-nada"] == "sim", (
        "sem lacuna nenhuma a linha da confissão continuaria na tela")


def test_sem_censo_a_confissao_nao_emite_nada(monkeypatch: Any) -> None:
    """Barramento não lido: NÃO se emite — porque vazio vira travessão."""
    pac = _pacote()
    monkeypatch.setattr(pac, "_bancada", lambda: None)
    assert pac._confissao_do_mapa() == {}


def test_a_palavra_da_conta_nunca_mente_por_extenso() -> None:
    """Fora da tabela, o número cru — nunca a última palavra que couber."""
    pac = _pacote()
    fora = max(pac.PALAVRA_DA_CONTA) + 1
    assert pac.palavra_da_conta(fora) == str(fora)
