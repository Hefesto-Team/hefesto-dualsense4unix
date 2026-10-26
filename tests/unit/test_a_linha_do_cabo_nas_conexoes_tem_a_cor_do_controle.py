"""A linha do cabo nas Conexões tem a cor do controle.

A-LINHA-DO-CABO-NAS-CONEXOES-TEM-A-COR-DO-CONTROLE-01 (26/10/2026). Na sala «Rádio e adaptadores»,
o controle no rádio tinha a silhueta na cor do plástico e o nome «Cosmic Red ● P1»; o mesmo controle
no cabo (pareado no adaptador e ligado no USB) aparecia com a silhueta cinza, sem a cor e sem o
jogador, só com a palavra «USB». A identidade é do controle, não do transporte.

O que a régua prova:

* a linha do controle no cabo leva a cor do plástico, o nome da cor e o jogador, de P1 a P4 e com
  qualquer mistura de cabo e rádio, e a silhueta fica na cor (sem o esmaecido do «desligado»);
* a palavra da faixa segue «USB» (a regra «a tela diz USB e BT»);
* o controle que está mesmo desligado segue cinza e sem jogador;
* a cor, o nome dela e o jogador saem de UM dono (``_a_cara_do_controle``), o mesmo do rádio, e o
  mockup da 08 desenha a linha do cabo.

MORDIDAS: tire o ``**cara`` do ``_os_desligados`` e a cor some da linha do cabo; devolva a condição
do rádio (``_a_cara_do_controle`` só para quem não está no cabo) e o mesmo; tire o ``no-cabo`` do
``html_da_linha`` e a silhueta volta esmaecida.
"""

from __future__ import annotations

import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "08-conexoes.html"

ADAPTADOR = "/org/bluez/hci0"
LUGAR = "aa:bb:cc:00:00:f0"
CLASSE_DE_CONTROLE = 9480

PLASTICOS = {
    1: ("aa:bb:cc:00:00:01", "cosmic-red", "Cosmic Red"),
    2: ("aa:bb:cc:00:00:02", "starlight-blue", "Starlight Blue"),
    3: ("aa:bb:cc:00:00:03", "galactic-purple", "Galactic Purple"),
    4: ("aa:bb:cc:00:00:04", "white", "White"),
}


def _mesa(jogadores: list[int]) -> list[dict[str, Any]]:
    return [{"uniq": PLASTICOS[j][0], "jogador": j, "cor": PLASTICOS[j][1],
             "nome": PLASTICOS[j][2]} for j in jogadores]


def _bluez(jogador: int, *, conectado: bool) -> Any:
    return SimpleNamespace(
        adaptador=ADAPTADOR, endereco=PLASTICOS[jogador][0].upper(), pareado=True,
        conectado=conectado, nome="", classe=CLASSE_DE_CONTROLE, icone="", aparencia=None,
        modalias="usb:v054Cp0CE6d0100")


def _no_cabo(cabo: list[int], desligados: list[int] | None = None) -> list[dict[str, Any]]:
    """As linhas «desligado» que a cena monta: ``cabo`` no USB, ``desligados`` fora do ar."""
    todos = [*cabo, *(desligados or [])]
    usb = frozenset(a08._so_hex(PLASTICOS[j][0]) for j in cabo)
    linhas: list[dict[str, Any]] = a08._os_desligados(
        tuple(_bluez(j, conectado=False) for j in todos), {ADAPTADOR: LUGAR}, [], usb,
        {m["uniq"]: m for m in _mesa(cabo)})
    return linhas


def _html(ap: dict[str, Any]) -> str:
    return str(a08.html_da_linha(ap, {"aparelhos": [ap], "lugares": [{"id": LUGAR}]}))


def _cor_da_silhueta(linha: str) -> str:
    achou = re.search(r'<svg class="i ds"[^>]*style="color:([^"]+)"', linha)
    assert achou, linha
    return achou.group(1)


def _a_linha_do_radio(jogador: int) -> dict[str, Any]:
    """A linha do MESMO controle no rádio, pelo gerador da cena (o que o desenho mostra)."""
    uniq = PLASTICOS[jogador][0]
    estado = {"controllers": [{"uniq": uniq, "transport": "bt", "adaptador": LUGAR,
                               "connected": True}]}
    ctx = a08.Contexto(state=estado, mesa=_mesa([jogador]), conectados=estado["controllers"],
                       estados={})
    (ap,) = a08._aparelhos_da_cena(ctx, estado, {}, [], (_bluez(jogador, conectado=True),),
                                   {ADAPTADOR: LUGAR}, [a08.nome_do_jogador.mac(LUGAR)])
    return dict(ap)


def test_1_o_controle_no_cabo_leva_a_cor_o_nome_dela_e_o_jogador() -> None:
    (ap,) = _no_cabo([1])
    assert ap["usb"] is True and ap["desligado"] is True
    assert ap["jogador"] == 1 and ap["cor_nome"] == "Cosmic Red"
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", ap["cor"]), ap["cor"]
    linha = _html(ap)
    assert _cor_da_silhueta(linha) == ap["cor"]
    assert "Cosmic Red" in linha and "P1" in linha, linha


def test_2_a_faixa_do_cabo_segue_dizendo_usb() -> None:
    (ap,) = _no_cabo([2])
    assert re.search(r'<span class="desligado" title="[^"]*">USB</span>', _html(ap))


def test_3_a_silhueta_do_cabo_nao_nasce_esmaecida() -> None:
    (ap,) = _no_cabo([1])
    assert 'class="linha desligado no-cabo"' in _html(ap)
    mockup = MOCKUP.read_text(encoding="utf-8")
    assert ".radio .linha.desligado.no-cabo .ds{opacity:1}" in mockup


def test_4_o_controle_mesmo_desligado_segue_cinza_e_sem_jogador() -> None:
    (ap,) = _no_cabo([], [3])
    assert ap["usb"] is False
    assert not ap.get("cor") and not ap.get("cor_nome") and ap.get("jogador") is None
    linha = _html(ap)
    assert _cor_da_silhueta(linha) == "var(--texto-mudo)"
    assert "no-cabo" not in linha and "Galactic Purple" not in linha
    assert re.search(r'<span class="desligado"[^>]*>Desligado</span>', linha)


@pytest.mark.parametrize("cabo", [[1], [2, 3], [1, 2, 3, 4], [4]],
                         ids=lambda c: "-".join(map(str, c)))
def test_5_de_p1_a_p4_com_qualquer_mistura(cabo: list[int]) -> None:
    fora = [j for j in (1, 2, 3, 4) if j not in cabo]
    linhas = {ap["jogador"]: ap for ap in _no_cabo(cabo, fora) if ap.get("usb")}
    assert sorted(linhas) == sorted(cabo)
    for j, ap in linhas.items():
        html = _html(ap)
        assert PLASTICOS[j][2] in html and f"P{j}" in html, (j, html)
        assert _cor_da_silhueta(html) == ap["cor"] != ""


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_6_o_cabo_tem_a_mesma_cor_e_o_mesmo_selo_do_radio(jogador: int) -> None:
    (cabo,) = _no_cabo([jogador])
    radio = _a_linha_do_radio(jogador)
    assert (cabo["cor"], cabo["cor_nome"], cabo["jogador"]) == (
        radio["cor"], radio["cor_nome"], radio["jogador"])
    assert a08.nome_na_conexoes(cabo) == a08.nome_na_conexoes(radio)
    quem = re.compile(r'<span class="quem-resto">([^<]*)</span>')
    assert quem.search(_html(cabo)).group(1) == quem.search(_html(radio)).group(1)  # type: ignore[union-attr]


def test_7_a_cara_do_controle_tem_um_dono_so() -> None:
    eu = _mesa([2])[0]
    assert a08._a_cara_do_controle(eu) == {
        "jogador": 2, "cor": a08._hex_do_plastico("starlight-blue"), "cor_nome": "Starlight Blue"}
    assert a08._a_cara_do_controle({}) == {"jogador": None, "cor": "", "cor_nome": ""}
    fonte = pathlib.Path(a08.__file__).read_text(encoding="utf-8")
    assert fonte.count("_a_cara_do_controle(") >= 3, "o rádio e o cabo devem usar o mesmo dono"


def test_8_sem_a_mesa_o_cabo_fica_sem_cor_e_nao_quebra() -> None:
    usb = frozenset({a08._so_hex(PLASTICOS[1][0])})
    (ap,) = a08._os_desligados((_bluez(1, conectado=False),), {ADAPTADOR: LUGAR}, [], usb, None)
    assert ap["usb"] is True and ap["cor"] == "" and ap["cor_nome"] == ""
    assert _cor_da_silhueta(_html(ap)) == "var(--texto-mudo)"


def test_9_o_mockup_da_08_desenha_a_linha_do_cabo_com_cor_e_selo() -> None:
    mockup = MOCKUP.read_text(encoding="utf-8")
    achou = re.search(r'<div class="linha desligado no-cabo"[^>]*>(.*?)</div>\s*<span class="conta',
                      mockup, re.S)
    assert achou, "o desenho não tem a linha do controle no cabo"
    linha = achou.group(0)
    assert re.search(r'<svg class="i ds"[^>]*style="color:#[0-9a-fA-F]{6}"', linha), linha
    assert re.search(r'quem-resto">[^<]*● [A-Z][a-z]+( [A-Z][a-z]+)? ● P[1-4]<', linha), linha
    assert ">USB</span>" in linha
