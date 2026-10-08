"""O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01: o cartão do externo lê a declaração dela.

As respostas de 06/10/2026: os glifos das outras abas seguem o `controles.modo` e o
`controles.botoes` do controle externo, e a `controles.cor` dele aparece em tudo. O fio
estava ligado só na mesa que as dez abas leem, e os itens dessa mesa são todos DualSense:
o cartão dos externos (Jogar e Conexões) não lia nada.

O que se mede aqui, nos DOIS cartões, com o `maquina.json` dela dublado pelo mesmo ponto em
que a mesa o lê (`mesa_viva._declaracao_do_disco`):

* a cor declarada vira a borda do cartão, e a família dos botões vira as quatro letras da
  face, as duas pela MESMA fonte da mesa (`mesa_viva.cor_declarada` e `familia_dos_botoes`);
* o que ela não declarou não desenha nada (campo sem informação não mostra nada);
* a decisão do item 3: a família declarada vale também para o DualSense, e o PS continua no
  logo (a régua dela é a `test_a_cor_e_os_botoes_que_ela_declarou_seguem_o_controle`).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import Contexto
from pacotes import a01_jogar as jogar
from pacotes import a08_conexoes as conexoes

from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_nome
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

# Faixa forjada (`aa:bb:cc`), nunca endereço real mascarado.
CHAVE = "aabbcc000031"


def _externo(bus: str = "bluetooth", slot: int = 3, **mais: Any) -> dict[str, Any]:
    return {"name": "Controle de teste", "vid": "2dc8", "pid": "6003", "bus": bus,
            "uniq": "aa:bb:cc:00:00:31", "driver": "hid-generic",
            "player_slot": slot, **mais}


def _ctx(*externos: dict[str, Any]) -> Contexto:
    return Contexto(state={"connected": True}, mesa=[], conectados=[],
                    externos=list(externos))


def _ela(monkeypatch: pytest.MonkeyPatch, **campos: Any) -> None:
    """O `maquina.json` dela, lido pelo ponto em que a mesa o lê."""
    declaracao = MaquinaConfig.model_validate({"controles": {CHAVE: campos}})
    from hefesto_dualsense4unix.interface import mesa_viva

    monkeypatch.setattr(mesa_viva, "_declaracao_do_disco", lambda: declaracao)


def _dos_dois(*externos: dict[str, Any]) -> tuple[str, str]:
    return (str(jogar.pacote(_ctx(*externos))["externos"]),
            conexoes._html_dos_externos(_ctx(*externos)))


def _letras(html: str) -> str:
    achado = re.search(r'class="ext-botoes"[^>]*>([^<]*)<', html)
    return achado.group(1) if achado else ""


@pytest.mark.parametrize(("campos", "letras"), [
    ({"botoes": "nintendo"}, "B A Y X"),
    ({"botoes": "xbox"}, "A B X Y"),
    ({"modo": "switch"}, "B A Y X"),
    ({"modo": "xinput"}, "A B X Y"),
    ({"botoes": "xbox", "modo": "switch"}, "A B X Y"),
])
def test_os_dois_cartoes_mostram_a_familia_dos_botoes_que_ela_declarou(
        monkeypatch: pytest.MonkeyPatch, campos: dict, letras: str) -> None:
    _ela(monkeypatch, **campos)
    for html in _dos_dois(_externo()):
        assert _letras(html) == letras, html


def test_os_dois_cartoes_pintam_a_borda_com_a_cor_que_ela_declarou(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import mesa_viva

    _ela(monkeypatch, cor="Cosmic Red")
    cor = cor_do_nome("Cosmic Red")
    assert cor is not None
    # a mesma cor que a mesa daria a um DualSense declarado com ela
    slug, _ = mesa_viva.CORES[cor.codigo]
    hexa = conexoes._hex_do_plastico(slug)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", hexa)
    for html in _dos_dois(_externo()):
        assert f'border-color:{hexa}' in html, html
        assert 'title="Cosmic Red"' in html


@pytest.mark.parametrize(("campos"), [
    {},
    {"modo": "dinput"},
    {"cor": "Rosa choque da minha tia"},
])
def test_o_que_ela_nao_declarou_nao_desenha_nada(
        monkeypatch: pytest.MonkeyPatch, campos: dict) -> None:
    """Sem declaração, sem família ou sem cor que o mapa conheça: o cartão de sempre."""
    _ela(monkeypatch, **campos)
    for html in _dos_dois(_externo()):
        assert "border-color" not in html
        assert "ext-botoes" not in html
        assert "style=" not in html


def test_a_declaracao_e_do_controle_dela_e_nao_do_vizinho(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch, botoes="nintendo", cor="Cosmic Red")
    vizinho = _externo(uniq="aa:bb:cc:00:00:32", slot=4)
    jogar_html, conexoes_html = _dos_dois(_externo(), vizinho)
    for html in (jogar_html, conexoes_html):
        assert html.count("ext-botoes") == 1
        assert html.count("border-color") == 1


@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
@pytest.mark.parametrize("slot", [1, 2, 3, 4])
def test_cabo_e_radio_de_um_a_quatro_jogadores(
        monkeypatch: pytest.MonkeyPatch, bus: str, slot: int) -> None:
    """A declaração é do controle, não do transporte nem do número do jogador."""
    _ela(monkeypatch, botoes="nintendo", cor="Cosmic Red")
    for html in _dos_dois(_externo(bus=bus, slot=slot)):
        assert _letras(html) == "B A Y X"
        assert "border-color" in html


def test_sem_endereco_fixo_nao_ha_onde_ter_declaracao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MAC forjado (`02:…`) ou ausente não tem chave no `maquina.json`: vazio, sem erro."""
    _ela(monkeypatch, botoes="nintendo", cor="Cosmic Red")
    for entrada in (_externo(uniq="02:fe:00:00:00:31"), _externo(uniq="")):
        for html in _dos_dois(entrada):
            assert "ext-botoes" not in html and "border-color" not in html


def test_o_identity_do_daemon_manda_na_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    """`chave_de_maquina` usa o `identity` quando o daemon o carimbou (o dono é ele)."""
    _ela(monkeypatch, botoes="xbox")
    com_identity = _externo(uniq="aa:bb:cc:00:00:99", identity="aa:bb:cc:00:00:31")
    for html in _dos_dois(com_identity):
        assert _letras(html) == "A B X Y"


def test_o_cartao_e_a_mesa_leem_a_mesma_fonte(monkeypatch: pytest.MonkeyPatch) -> None:
    """O que a mesa dá a um DualSense com esta declaração é o que o cartão do externo mostra."""
    from hefesto_dualsense4unix.interface import mesa_viva

    _ela(monkeypatch, botoes="nintendo", cor="Cosmic Red")
    (item,) = mesa_viva.mesa_do_estado(
        {"controllers": [{"uniq": "aa:bb:cc:00:00:31", "connected": True,
                          "transport": "usb", "player_slot": 1}]}, {})
    ela = conexoes.a_declaracao_do_externo(_externo())
    assert ela["botoes"] == item["botoes"] == "nintendo"
    assert ela["cor"] == conexoes._hex_do_plastico(item["cor"])
    assert ela["cor_nome"] == item["nome"]


# O ITEM 3, DECIDIDO PELO PADRÃO DELA (08/10/2026): a família declarada vale também para o
# DualSense. Razão: a interface é soberana (o que ela declara é o que a tela mostra),
# `controles.botoes` é «só o desenho da tela», o PS continua no logo, e é o mais reversível.


def test_a_familia_declarada_vale_tambem_para_o_dualsense(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import mesa_viva

    _ela(monkeypatch, botoes="nintendo")
    (item,) = mesa_viva.mesa_do_estado(
        {"controllers": [{"uniq": "aa:bb:cc:00:00:31", "connected": True,
                          "transport": "usb", "player_slot": 1}]}, {})
    assert item["botoes"] == "nintendo"


def test_o_cartao_nao_chama_o_externo_de_assento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ganhar cor e botões não é virar `.cartao` nem ganhar `data-controle`."""
    _ela(monkeypatch, botoes="nintendo", cor="Cosmic Red")
    for html in _dos_dois(_externo()):
        assert 'class="cartao' not in html and "data-controle" not in html
        assert "data-colorway" not in html and "--plastico" not in html
