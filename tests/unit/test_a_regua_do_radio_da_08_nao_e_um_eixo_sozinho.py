#!/usr/bin/env python3
"""A sala do rádio da aba 08 nunca afirma nada sobre o vazio.

**NASCEU EM 03/09/2026 COMO A RÉGUA DE DESEMPENHO**, fotografada no WebKit do
produto com **um DualSense White no cabo e nada no rádio**: a seção mostrava a
escala `0 400 800 1.200 1.600` e a legenda `+16,3 / +276,7` — dois números com
cara de medição, sem uma barra a que pertencer. A cura de 03/09 deu uma pista
por grupo; a de 04/09, uma pista por ADAPTADOR, com o nome que ela deu, e sem
inventar adaptador quando a varredura falha.

**23/09/2026 — A RÉGUA DE DESEMPENHO SAIU** (TRANSPLANTE-DA-SECAO-01). A seção
«Rádio e Adaptadores» virou o desenho aprovado dela, e o que a régua dizia em
pistas a sala diz em cartões: um cartão por adaptador. As três perguntas deste
arquivo sobreviveram inteiras, só mudou onde a resposta mora —

1. **A varredura que não respondeu não vira «nenhum».** Sem o BlueZ e com o
   daemon mudo ninguém sabe quantos adaptadores há; a sala e a conta do topo
   não afirmam nada. É a cicatriz da B1 (23/08): não saber e estar vazio são
   coisas diferentes, e a diferença é a informação inteira.
2. **O BlueZ que respondeu zero diz que não há** — com a frase da tabela que a
   sala substituiu.
3. **Três adaptadores e ninguém no rádio são três cartões**, cada um com o nome
   que ela deu ao lugar; e o controle que ESTÁ no rádio aparece no cartão dele.

A MESA É DECLARADA, nunca a da máquina de quem roda: o BlueZ, o `maquina.json`
e o `/sys` entram por dublê (a lição de 04/09 — *um teste de tela que depende
do hardware de quem o roda dá verde ou vermelho por motivo que não é o código*).

A MORDIDA: em `a08_conexoes.html_da_sala`, tire o `if not cena.get("lido", True)`
e o primeiro caso reprova com «Nenhum adaptador» sobre uma leitura que não
houve; tire o `"lido"` da cena e o segundo reprova.
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

#: A faixa sintética da casa — há dois portões de anonimato nesta árvore.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
PCI = "0000:00:14.0"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture
def bancada(monkeypatch: Any) -> Any:
    """A mesa de rádio DECLARADA — nunca a da máquina que roda o teste.

    Devolve um `def declarar(nomes)`: `None` é o BlueZ que NÃO RESPONDEU (e ele
    é diferente de uma lista vazia); uma lista de nomes vira um adaptador por
    nome, cada um numa porta e com o nome que ela deu a ele.
    """
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    p = _pacote()
    monkeypatch.setattr(p, "LER_NA_HORA", True)
    monkeypatch.setattr(p, "_FUNDO", {})
    monkeypatch.setattr(p, "_ABERTO", {})
    monkeypatch.setattr(p, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(p, "_ler_o_historico", lambda: {})

    def declarar(nomes: list[str] | None) -> None:
        if nomes is None:
            monkeypatch.setattr(p, "_ler_o_bluez", lambda: None)
            monkeypatch.setattr(p, "_ler_a_maquina", lambda: (None, {}))
            return
        lugares = {f"pci-{PCI}-usb-0:{i + 1}": nome for i, nome in enumerate(nomes)}
        adaptadores = tuple(
            AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}", f"AA:BB:CC:00:00:{i + 10:02d}",
                             lugar=lugar)
            for i, lugar in enumerate(lugares))
        monkeypatch.setattr(p, "_ler_o_bluez", lambda: (adaptadores, ()))
        # O NOME É DO ADAPTADOR, pelo endereço (D-2609-O-ADAPTADOR-TEM-NOME-PROPRIO).
        maquina = MaquinaConfig(
            lugares={lg: {} for lg in lugares},
            adaptadores={f"aabbcc0000{i + 10:02d}": {"nome": nome} for i, nome in enumerate(nomes)})
        monkeypatch.setattr(p, "_ler_a_maquina", lambda: (maquina, {3: PCI}))

    return declarar


def _ctx(*, com_radio: bool) -> Any:
    """A mesa dela de hoje: um White no cabo. Com `com_radio`, mais um no rádio."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    mesa: list[dict[str, Any]] = [
        {"pref": "p1", "uniq": P1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
    ]
    conectados: list[dict[str, Any]] = [
        {"uniq": P1, "transport": "usb", "connected": True, "battery_pct": 100},
    ]
    if com_radio:
        mesa.append(
            {"pref": "p2", "uniq": P2, "jogador": 2, "cor": "galactic-purple",
             "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
             "mascara": "DualSense"})
        conectados.append(
            {"uniq": P2, "transport": "bt", "connected": True, "battery_pct": 64,
             "adaptador": "aa:bb:cc:00:00:10"})
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def _secao(*, com_radio: bool) -> dict[str, Any]:
    return _pacote().campos_do_radio(_ctx(com_radio=com_radio))


# ---------------------------------------------------------------------------
# NINGUÉM RESPONDEU — a sala não afirma nada
# ---------------------------------------------------------------------------
def test_sem_resposta_a_sala_nao_diz_que_nao_ha(bancada: Any) -> None:
    """O BlueZ mudo e o daemon sem `radio_ar` não são «nenhum adaptador»."""
    bancada(None)
    campos = _secao(com_radio=False)
    nada = _pacote()._monta().NADA_A_DIZER
    assert campos["radio-sala"] == nada, (
        "a sala afirmou alguma coisa sem que ninguém tivesse respondido: "
        f"{campos['radio-sala']!r}")
    assert _pacote().NENHUM_ADAPTADOR not in campos["radio-sala"]
    assert campos["conta-de-adaptadores"] == nada, (
        "a conta do topo disse «0 adaptadores» sobre uma leitura que não houve: "
        f"{campos['conta-de-adaptadores']!r}")


# ---------------------------------------------------------------------------
# O BLUEZ RESPONDEU — zero é zero, e três são três
# ---------------------------------------------------------------------------
def test_o_bluez_que_respondeu_zero_diz_que_nao_ha(bancada: Any) -> None:
    bancada([])
    campos = _secao(com_radio=False)
    assert _pacote().NENHUM_ADAPTADOR in campos["radio-sala"], campos["radio-sala"]
    assert campos["conta-de-adaptadores"].endswith("0 adaptadores")


def test_um_cartao_por_adaptador_mesmo_com_a_mesa_no_cabo(bancada: Any) -> None:
    """TRÊS adaptadores e ninguém no rádio ainda são TRÊS cartões, nomeados.

    É a pergunta que a seção existe para responder — *"onde cabe mais um?"* —,
    e com um cartão só sobre três adaptadores ela responde por um terço da mesa.
    """
    bancada(["Sala", "Extra", "Terceiro"])
    sala = _secao(com_radio=False)["radio-sala"]
    assert len(re.findall(r'<div class="lugar[ "]', sala)) == 3, sala[:600]
    for nome in ("Sala", "Extra", "Terceiro"):
        assert f'value="{nome}"' in sala, (
            f"o cartão de {nome!r} saiu sem o nome que ela deu ao adaptador")
    assert 'class="linha' not in sala, (
        "um cartão ganhou a linha de um controle que está no CABO")


def test_o_controle_no_radio_aparece_no_cartao_dele(bancada: Any) -> None:
    """A cura não pode trocar o caso que já funcionava."""
    bancada(["Sala"])
    sala = _secao(com_radio=True)["radio-sala"]
    assert "Galactic Purple" in sala, (
        f"a sala deixou de nomear o controle que está NO rádio:\n{sala[:600]}")
    assert "White" not in sala, "o controle do cabo entrou na sala do rádio"
