#!/usr/bin/env python3
"""A régua de Desempenho da aba 08 nunca sai como eixo e legenda sobre o vazio.

**03/09/2026.** Fotografado no WebKit do produto, na mesa dela, com **um
DualSense White no cabo e nada no rádio** — que é o estado mais comum de uma
mesa de uma pessoa só:

    document.querySelectorAll('.pista') .length → 0
    document.querySelectorAll('.bloco') .length → 0
    innerHTML de [data-campo="regua-do-radio"] → só <div class="eixo"> e
                                                 <div class="leg">

A seção diz **"Desempenho · O rádio de cada adaptador, em turnos"** e mostrava
a escala `0 400 800 1.200 1.600` com a legenda anunciando `+16,3` e `+276,7`
— dois números com cara de medição, sem uma barra a que pertencer. É a forma de
mentira que esta casa já nomeou: *a tela AFIRMA algo que não é verdade*.

A CAUSA: `_regua_do_radio` montava as pistas a partir de `grupos`, que nasce dos
controles que estão NO RÁDIO. Zero controles no rádio, zero pistas. O dono da
frase (`gui.aba_conexoes.html_das_pistas`) percorre os **adaptadores**, e um
adaptador sem ninguém vira `Nenhum controle neste rádio · 0 de 1.600` — a mesma
pista vazia que a `08-conexoes` publicada já traz DESENHADA.

---

**04/09/2026 — A CURA FICOU INTEIRA, E DUAS COISAS DESTE ARQUIVO CADUCARAM.**

A cura de 03/09 dava UMA pista sem nome quando não havia ninguém no rádio, e a
razão escrita era que *"sem `uniq` no rádio ninguém perguntou ao sysfs qual
adaptador é"* — verdade sobre `radio_da_mesa`, e caminho errado: quem ENUMERA os
adaptadores é `mesa_de_radio.ler_a_mesa()`, a mesma leitura que esta aba já fazia
para os rádios vizinhos, e quem os NOMEIA é o `Dongle` do BlueZ. Agora é uma
pista por adaptador DELA, com o nome que ela deu.

**E ISTO AQUI ESTAVA MEDINDO A BANCADA, NÃO O CÓDIGO.** Os testes liam a máquina
de quem roda: com a régua nascendo dos GRUPOS isso não aparecia (a mesa
sintética decidia tudo), e no minuto em que ela passou a nascer dos ADAPTADORES,
o terceiro teste reprovou por causa dos TRÊS adaptadores desta bancada. A cura é
declarar a mesa — `_MESA_DO_RADIO` e `_DONGLES` — e é o que os testes fazem
agora. Um teste de tela que depende do hardware de quem o roda dá verde ou
vermelho por motivo que não é o código.

A MORDIDA: apague o ramo `if not pistas:` de
`interface/pacotes/a08_conexoes._regua_do_radio` e rode este arquivo — os dois
primeiros testes reprovam (eles são o caso da varredura FALHA), e os dois
últimos continuam verdes, que é a prova de que a cura não trocou o caso que já
funcionava. Apague o laço `for a in ... adaptadores` e o terceiro reprova.
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


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


class _Adaptador:
    """O mínimo que a régua pergunta a um adaptador da varredura do sysfs."""

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self.no = f"/sys/{interface}"
        self.caminho = "3-1"
        self.vid, self.pid = "2357", "0604"
        self.busnum, self.devpath = 3, "1"
        self.painel = ""
        self.atras_de_hub = False
        self.controlador_pci = ""


class _Mesa:
    def __init__(self, adaptadores: Any) -> None:
        self.adaptadores = adaptadores
        self.radios: tuple[Any, ...] = ()
        self.apertadas: tuple[Any, ...] = ()


class _Dongle:
    """As TRÊS pontas do BlueZ: endereço, `/org/bluez/hciN` e o nome dela."""

    def __init__(self, endereco: str, interface: str, nome: str) -> None:
        self.endereco = endereco
        self.objeto = f"/org/bluez/{interface}"
        self.nome = nome


@pytest.fixture
def bancada(monkeypatch: Any) -> Any:
    """A mesa de rádio DECLARADA — nunca a da máquina que roda o teste.

    Devolve um `def declarar(adaptadores)`: `None` é a varredura que FALHOU (e
    ela é diferente de uma lista vazia), e uma lista de nomes vira um adaptador
    por nome, com o apelido correspondente no BlueZ.
    """
    p = _pacote()

    def declarar(nomes: list[str] | None) -> None:
        if nomes is None:
            monkeypatch.setattr(p, "_MESA_DO_RADIO", None)
            monkeypatch.setattr(p, "_mesa_do_radio", lambda recarregar=False: None)
            monkeypatch.setattr(p, "_DONGLES", ())
            monkeypatch.setattr(p, "_dongles", lambda recarregar=False: None)
            return
        adaptadores = [_Adaptador(f"hci{i}") for i, _ in enumerate(nomes)]
        mesa = _Mesa(adaptadores)
        monkeypatch.setattr(p, "_MESA_DO_RADIO", mesa)
        monkeypatch.setattr(p, "_mesa_do_radio", lambda recarregar=False: mesa)
        dongles = tuple(
            _Dongle(f"AA:BB:CC:00:00:{i:02d}", f"hci{i}", nome)
            for i, nome in enumerate(nomes))
        monkeypatch.setattr(p, "_DONGLES", dongles)
        monkeypatch.setattr(p, "_dongles", lambda recarregar=False: dongles)

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
            {"uniq": P2, "transport": "bt", "connected": True, "battery_pct": 64})
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def _regua(*, com_radio: bool) -> str:
    return str(_pacote().pacote(_ctx(com_radio=com_radio)).get("regua-do-radio") or "")


def _pistas(html: str) -> list[str]:
    """Cada `.pista` inteira, para conferir uma a uma em vez de no bolo."""
    return re.findall(r'<div class="pista">.*?</div>\s*(?=<div |$)', html, flags=re.S)


# ---------------------------------------------------------------------------
# A VARREDURA FALHOU — o caso da cura de 03/09
# ---------------------------------------------------------------------------
def test_sem_ninguem_no_radio_a_regua_ainda_tem_pista(bancada: Any) -> None:
    """Com a mesa só no cabo, o bloco não pode sair como eixo e legenda."""
    bancada(None)
    html = _regua(com_radio=False)
    assert 'class="pista"' in html, (
        "a régua de Desempenho saiu SEM PISTA NENHUMA com a mesa só no cabo — "
        "é o eixo `0 … 1.600` e a legenda `+16,3 / +276,7` sobre zero barra, "
        f"que foi o que a foto de 03/09 pegou. HTML:\n{html}")


def test_sem_ninguem_no_radio_a_pista_diz_que_esta_vazia(bancada: Any) -> None:
    """E a pista tem de DIZER que está vazia, com a palavra do dono.

    A frase é de `gui.aba_conexoes.html_das_pistas` e já está desenhada na
    `08-conexoes` publicada. Nenhuma palavra nova nasce nesta cura.
    """
    bancada(None)
    html = _regua(com_radio=False)
    assert "Nenhum controle neste rádio" in html, (
        f"a pista vazia não disse que está vazia:\n{html}")
    assert 'class="bloco' not in html, (
        "a régua desenhou uma barra sem ninguém no rádio — isso é inventar "
        f"ocupação:\n{html}")
    # E NÃO SE INVENTA UM ADAPTADOR: com a varredura FALHA ninguém sabe quantos
    # há nem quais são, e ela tem TRÊS. `Sem nome` afirmaria que existe UM e que
    # ele não tem apelido; a coluna vazia não afirma nada.
    assert "Sem nome" not in html, (
        "a régua nomeou um adaptador que ninguém mediu — a coluna fica vazia "
        f"quando a varredura não respondeu:\n{html}")


# ---------------------------------------------------------------------------
# A VARREDURA RESPONDEU — uma pista por adaptador, 04/09/2026
# ---------------------------------------------------------------------------
def test_uma_pista_por_adaptador_mesmo_com_a_mesa_no_cabo(bancada: Any) -> None:
    """TRÊS adaptadores e ninguém no rádio ainda são TRÊS pistas, nomeadas.

    É a pergunta que a seção existe para responder — *"cabe mais um controle no
    rádio?"* —, e com uma barra só sobre três adaptadores ela responde por um
    terço da mesa.
    """
    bancada(["Sala", "Extra", "Terceiro"])
    html = _regua(com_radio=False)
    pistas = _pistas(html)
    assert len(pistas) == 3, (
        f"a régua saiu com {len(pistas)} pistas para três adaptadores:\n{html}")
    for nome in ("Sala", "Extra", "Terceiro"):
        assert nome in html, (
            f"a pista de {nome!r} saiu sem o nome que ela deu no BlueZ — era "
            f"'Sem nome' para os três, que é o problema que os nomes vieram "
            f"resolver:\n{html}")
    assert html.count("Nenhum controle neste rádio") == 3, (
        f"as três pistas vazias tinham de dizer que estão vazias:\n{html}")


def test_com_alguem_no_radio_a_regua_continua_como_era(bancada: Any) -> None:
    """A cura não pode trocar o caso que já funcionava.

    Este é o caso que a régua de identidade já cobre: com o Galactic Purple no
    rádio, a pista dele nasce com a fatia e a legenda o nomeia.

    A CONFERÊNCIA É POR PISTA, e não no bolo do HTML — 04/09/2026. Ela era um
    `"Nenhum controle neste rádio" not in html`, e isso deixou de significar o
    que dizia no dia em que os adaptadores VAZIOS passaram a ganhar pista: a
    frase da pista vazia do vizinho reprovava a pista cheia deste.
    """
    bancada(["Sala"])
    html = _regua(com_radio=True)
    assert 'class="leg"' in html
    assert "Galactic Purple" in html, (
        f"a régua deixou de nomear o controle que está NO rádio:\n{html}")
    com_fatia = [p for p in _pistas(html) if 'class="bloco usa"' in p]
    assert com_fatia, (
        f"a régua deixou de desenhar a fatia de quem está no rádio:\n{html}")
    for pista in com_fatia:
        assert "Nenhum controle neste rádio" not in pista, (
            f"a pista de quem TEM controle disse que está vazia:\n{pista}")
