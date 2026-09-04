#!/usr/bin/env python3
"""A coluna Atenção: até três, o mais grave em cima, e o `+N` do que não coube.

DECISÃO DELA — 04/09/2026, D-09: *"Até três linhas, o mais grave em cima."*, com
``+N`` se passar. E D-10: *"Todas na coluna Atenção."*, sobre as frases órfãs da
aba Jogar.

**UM FATO DO ENUNCIADO CAIU AQUI, e ele está medido nesta régua.** A D-09 nasceu
de *"a página tem UM par selo/texto e a conta do produto diz 3 avisos"*, e o
coordenador remediu e achou QUATRO. Nenhum dos dois números é o de hoje: a
página publica :data:`a01_jogar.AVISOS_VIVOS` — **seis** —, e as seis já são
endereço vivo desde 03/09. O que faltava não era LUGAR: era

1. **ordem** — a coluna mostrava as fontes na ordem em que o produto as
   declarou, que não é a ordem em que elas doem;
2. **teto** — com seis avisos a coluna crescia seis linhas e reabria o vão de
   38 px que ela reclamou em 31/08;
3. **a sétima fonte** — a linha *"Ponte com o jogo"*, que era a ÚNICA das três
   órfãs da D-10 sem canal nenhum. A PAUSA e o cadeado já estavam na coluna:
   são, respectivamente, a primeira e as duas últimas de
   `painel.AVISOS_DA_TELA`.

AS MORDIDAS, uma por peça — cada teste diz no docstring o que arrancar.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O daemon em **Navegação**: sem gamepad de pé, e é o estado em que a ponte
#: fala. É o mesmo payload da régua irmã (`test_a_aba01_le_o_estado…`).
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _acesas(fora: dict[str, Any]) -> tuple[list[str], list[str]]:
    """As linhas que a coluna ACENDE — as vazias são o apagador, não conteúdo.

    Os três endereços viajam SEMPRE com `AVISOS_VIVOS` entradas (ver a nota do
    `_coluna_de_avisos`): a lista curta some inteira em `pacotes.normalizar`
    quando fica vazia, e é a coluna vazia que precisa apagar o aviso do desenho.
    """
    selos = [s for s in fora["aviso-selo"] if s]
    return selos, fora["aviso-texto"][:len(selos)]


def _so_estes(monkeypatch: Any, avisos: list[dict[str, str]]) -> None:
    """Cala as outras fontes: a régua mede a ORDEM, não quem fala."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: list(avisos))
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# 1. O MAIS GRAVE EM CIMA
# ---------------------------------------------------------------------------
def test_o_mais_grave_sobe_e_a_ordem_e_a_da_gravidade(monkeypatch: Any) -> None:
    """A PAUSA vem antes do PERFIL, mesmo chegando depois dele.

    A ORDEM DE CHEGADA É A INVERSA DA DE GRAVIDADE de propósito: se o pacote
    devolvesse a lista como a recebeu, este teste passaria por acaso com
    qualquer entrada. Aqui ele só passa se alguém ORDENOU.

    A MORDIDA: troque o `sorted(...)` de `_coluna_de_avisos` por
    `list(avisos)` e a asserção reprova com
    ``['PERFIL', 'RÁDIO', 'GAMEPAD'] != ['GAMEPAD', 'PAUSA'...]`` — medido.
    """
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "degradado", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["GAMEPAD", "RÁDIO", "PERFIL"], (
        f"a coluna não pôs o mais grave em cima: {selos!r}")


def test_a_pausa_vence_tudo_porque_ela_invalida_tudo(monkeypatch: Any) -> None:
    """Com o Hefesto em pausa, nada do resto está acontecendo.

    É o critério declarado em :data:`a01_jogar.ORDEM_DA_GRAVIDADE`: a escada não
    é de cor, é de *o que invalida o quê*. Uma coluna que mostrasse "o rádio
    está frágil" acima de "o Hefesto está em pausa" mandaria ela consertar o
    rádio de um produto que está parado.

    A MORDIDA: tire ``"PAUSA"`` do começo de `ORDEM_DA_GRAVIDADE` e ela cai
    para o fim (o `posto.get(..., fim)` dos não listados), reprovando aqui.
    """
    _so_estes(monkeypatch, [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PAUSA", "texto": "em pausa", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert selos[0] == "PAUSA", f"a pausa não subiu: {selos!r}"


def test_a_ordem_e_estavel_entre_iguais(monkeypatch: Any) -> None:
    """Dois avisos do mesmo selo mantêm a ordem em que as fontes falaram.

    Sem estabilidade a linha troca de lugar a cada tique e a coluna "pisca" —
    e a tela que se mexe sozinha é queixa dela desde 31/08.

    A MORDIDA: troque o `sorted` por `sorted(..., key=..., reverse=True)` ou
    ordene por `(posto, texto)` e os dois PERFIL trocam de lugar.
    """
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "primeiro", "fonte": "x"},
        {"selo": "PERFIL", "texto": "segundo", "fonte": "y"},
    ])
    _, textos = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert textos == ["primeiro", "segundo"], (
        f"a ordem entre iguais mudou: {textos!r}")


# ---------------------------------------------------------------------------
# 2. O TETO E O `+N`
# ---------------------------------------------------------------------------
def test_com_quatro_avisos_a_coluna_mostra_tres_e_conta_o_quarto(
        monkeypatch: Any) -> None:
    """*"Até três linhas"*, com ``+N`` se passar — e o quarto NÃO some calado.

    O ``+N`` OCUPA A QUARTA LINHA e não sai do teto: somá-lo ao teto faria a
    coluna mostrar três e só avisar a partir do QUINTO, escondendo o quarto sem
    contá-lo — o defeito exato que esta linha existe para fechar.

    A MORDIDA: apague o bloco ``if sobra > 0:`` de `_coluna_de_avisos` e a
    coluna volta a mostrar três de quatro sem uma palavra — reprova na segunda
    asserção.
    """
    _so_estes(monkeypatch, [
        {"selo": "PAUSA", "texto": "a", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "b", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "c", "fonte": "x"},
        {"selo": "PERFIL", "texto": "d", "fonte": "x"},
    ])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["aviso-texto"][:3] == ["a", "b", "c"]
    assert fora["aviso-selo"][3] == "+1", (
        f"o quarto aviso sumiu calado: {fora['aviso-selo']!r}")
    assert "1 aviso" in fora["aviso-texto"][3], (
        f"a linha do `+N` não diz quantos ficaram: {fora['aviso-texto'][3]!r}")
    # E O ACENDEDOR ACOMPANHA: uma linha escrita e não acesa não aparece.
    assert fora["aviso-vivo"] == ["1"] * 4 + [""] * (aba.AVISOS_VIVOS - 4)


def test_com_tres_avisos_nao_nasce_linha_de_mais(monkeypatch: Any) -> None:
    """Exatamente no teto, o ``+N`` não existe — ele não é decoração.

    A MORDIDA: troque `if sobra > 0` por `if sobra >= 0` e a coluna passa a
    escrever "+0" numa máquina com três avisos.
    """
    _so_estes(monkeypatch, [
        {"selo": "PAUSA", "texto": "a", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "b", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "c", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert len(selos) == aba.AVISOS_NA_COLUNA
    assert not any(s.startswith("+") for s in selos), (
        f"nasceu um `+N` sem nada de fora: {selos!r}")


def test_a_coluna_nunca_escreve_mais_linhas_do_que_a_pagina_publica(
        monkeypatch: Any) -> None:
    """O teto do produto tem de caber no teto da página.

    São dois números diferentes de propósito (`AVISOS_NA_COLUNA` < `AVISOS_
    VIVOS`), e esta régua é o que impede o dia em que alguém subir o primeiro
    sem olhar o segundo: o piloto distribui a lista pelos elementos na ORDEM e
    joga fora o que sobra — sem erro, sem contagem, calado.

    A MORDIDA: ponha `AVISOS_NA_COLUNA = AVISOS_VIVOS` e a linha do `+N` passa
    a ser a sétima, reprovando aqui.
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(20)])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    selos, _ = _acesas(fora)
    assert len(selos) <= aba.AVISOS_VIVOS
    assert len(fora["aviso-selo"]) == len(fora["aviso-texto"]) == len(
        fora["aviso-vivo"]) == aba.AVISOS_VIVOS


def test_a_conta_ao_lado_continua_dizendo_o_total(monkeypatch: Any) -> None:
    """A coluna mostra 3 e a conta diz 10 — e é assim que ela sabe que há mais.

    A MORDIDA: passe `len(selos)` a `texto_da_conta` em vez de `len(avisos)` e
    a tela volta a esconder sete avisos escrevendo "3 avisos".
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(10)])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["atencao-conta"] == painel.texto_da_conta(10), (
        f"a conta deixou de dizer o total: {fora['atencao-conta']!r}")


# ---------------------------------------------------------------------------
# 3. O APAGADOR — a coluna vazia tem de APAGAR o aviso do desenho
# ---------------------------------------------------------------------------
def test_a_coluna_sem_aviso_apaga_o_que_o_mockup_cravou(monkeypatch: Any) -> None:
    """Fotografado no DOM vivo em 04/09/2026, e é uma tela se contradizendo.

    Com a máquina dela sem um aviso, a coluna mostrava *"RÁDIO · Dois rádios da
    bancada estão em portas vizinhas"* — a cena do mockup (`aba01.AVISOS`) — ao
    lado de *"nenhum aviso"*, escrito pelo produto no mesmo tique.

    A CAUSA ESTÁ FORA DESTA ABA e vale para todas: `pacotes.normalizar` descarta
    lista VAZIA (`if valor and all(...)`), então os três endereços não chegavam
    ao JS e o piloto **nunca visitava** os seis elementos — medido pelo selo da
    visita, `data-hef-visto` ausente nos seis. A cura daqui é declarar as seis
    linhas sempre, que é certo por si: quem publica seis lugares diz o que cada
    um dos seis mostra.

    A MORDIDA: troque o `vazias = [""] * (...)` por `vazias = []` e a lista volta
    a sair vazia — `normalizar` a come, e o aviso do desenho fica na tela para
    sempre. Reprova nas duas asserções abaixo.
    """
    from pacotes import normalizar

    _so_estes(monkeypatch, [])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["atencao-conta"] == "nenhum aviso"
    for campo in ("aviso-selo", "aviso-texto", "aviso-vivo"):
        assert fora[campo] == [""] * aba.AVISOS_VIVOS, (
            f"{campo} não sai com as {aba.AVISOS_VIVOS} vazias: {fora[campo]!r}")
        assert campo in normalizar(fora)["mesa"], (
            f"{campo} não sobreviveu ao despachante — o endereço não chega ao "
            "JS, e o aviso que o mockup cravou fica na tela")
