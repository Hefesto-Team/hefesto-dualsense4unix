"""O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01: o cartão do externo lê a declaração do usuário.

As respostas de 06/10/2026: os glifos das outras abas seguem o `controles.modo` e o
`controles.botoes` do controle externo, e a `controles.cor` dele aparece em tudo. O fio
estava ligado só na mesa que as dez abas leem, e os itens dessa mesa são todos DualSense:
o cartão dos externos (Jogar e Conexões) não lia nada.

O que se mede aqui, nos DOIS cartões, com o `maquina.json` do usuário dublado pelo mesmo ponto em
que a mesa o lê (`mesa_viva._declaracao_do_disco`):

* a cor declarada vira a borda do cartão, e a família dos botões vira as quatro letras da
  face, as duas pela MESMA fonte da mesa (`mesa_viva.cor_declarada` e `familia_dos_botoes`);
* o que o usuário não declarou não desenha nada (campo sem informação não mostra nada);
* a decisão do item 3: a família declarada vale também para o DualSense, e o PS continua no
  logo (a régua é a `test_a_cor_e_os_botoes_que_ela_declarou_seguem_o_controle`).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import Contexto, gesto_da_pagina
from pacotes import a01_jogar as jogar
from pacotes import a08_conexoes as conexoes

from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_nome
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

CHAVE = "aabbcc000031"


def _externo(bus: str = "bluetooth", slot: int = 3, **mais: Any) -> dict[str, Any]:
    return {"name": "Controle de teste", "vid": "2dc8", "pid": "6003", "bus": bus,
            "uniq": "aa:bb:cc:00:00:31", "driver": "hid-generic",
            "player_slot": slot, **mais}


def _ctx(*externos: dict[str, Any]) -> Contexto:
    return Contexto(state={"connected": True}, mesa=[], conectados=[],
                    externos=list(externos))


def _ela(monkeypatch: pytest.MonkeyPatch, **campos: Any) -> None:
    """O `maquina.json` do usuário, lido pelo ponto em que a mesa o lê."""
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


def test_a_familia_declarada_vale_tambem_para_o_dualsense(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Letras Nintendo declaradas num DualSense desenham as letras; o logo segue PS.

    Decisão: D-0810-A-FAMILIA-DECLARADA-VALE-PARA-O-DUALSENSE.
    """
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


GESTOS = ("externo-modo", "externo-botoes", "externo-cor")


class _Ponte:
    """O `p` do gesto: guarda o que foi mandado ao daemon e responde que deu certo."""

    def __init__(self, resposta: Any = (True, None)) -> None:
        self.chamadas: list[dict] = []
        self.resposta = resposta

    def machine_declare(self, carga: dict) -> Any:
        self.chamadas.append(carga)
        return self.resposta


def _lista(html: str, gesto: str) -> str:
    achado = re.search(rf'<select[^>]*data-gesto="{gesto}".*?</select>', html, re.S)
    assert achado, f"a lista {gesto} não está no cartão: {html}"
    return achado.group(0)


def test_so_a_conexoes_tem_as_listas_e_so_com_endereco_fixo() -> None:
    jogar_html, conexoes_html = _dos_dois(_externo())
    assert "data-gesto" not in jogar_html and "data-externo" not in jogar_html
    for gesto in GESTOS:
        assert f'data-gesto="{gesto}"' in conexoes_html
    sem_chave = conexoes._html_dos_externos(_ctx(_externo(uniq="02:fe:00:00:00:31")))
    assert "data-gesto" not in sem_chave


def test_as_listas_mostram_o_que_ela_declarou(monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch, modo="switch", botoes="nintendo", cor="Cosmic Red")
    html = conexoes._html_dos_externos(_ctx(_externo()))
    assert re.search(r'<option value="switch" selected>', _lista(html, "externo-modo"))
    assert re.search(r'<option value="nintendo" selected>B A Y X<',
                     _lista(html, "externo-botoes"))
    assert re.search(r'<option value="Cosmic Red" selected>', _lista(html, "externo-cor"))


def test_sem_declaracao_a_primeira_opcao_e_nao_sei(monkeypatch: pytest.MonkeyPatch) -> None:
    _ela(monkeypatch)
    html = conexoes._html_dos_externos(_ctx(_externo()))
    for gesto in GESTOS:
        lista = _lista(html, gesto)
        assert lista.count(" selected") == 1
        assert '<option value="" selected>' in lista


def test_a_lista_da_chave_nao_se_chama_modo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Na casa, «Modo» é como o controle chega ao jogo; a chave física do externo é outra coisa.

    MORDIDA: o rótulo da primeira opção voltando a «Modo».

    Decisão: D-0810-A-LISTA-DA-CHAVE-SE-CHAMA-CHAVE.
    """
    _ela(monkeypatch)
    lista = _lista(conexoes._html_dos_externos(_ctx(_externo())), "externo-modo")
    assert '<option value="" selected>Chave</option>' in lista
    assert ">Modo<" not in lista


def test_a_cor_fora_do_mapa_continua_na_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma cor que o mapa não conhece não some nem é trocada em silêncio."""
    _ela(monkeypatch, cor="Rosa choque da minha tia")
    lista = _lista(conexoes._html_dos_externos(_ctx(_externo())), "externo-cor")
    assert 'value="Rosa choque da minha tia" selected' in lista


@pytest.mark.parametrize(("gesto", "campo", "valor"), [
    ("externo-modo", "modo", "dinput"),
    ("externo-botoes", "botoes", "xbox"),
    ("externo-cor", "cor", "Cosmic Red"),
])
@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
@pytest.mark.parametrize("slot", [1, 2, 3, 4])
def test_o_gesto_grava_so_o_campo_dele_no_controle_certo(
        gesto: str, campo: str, valor: str, bus: str, slot: int) -> None:
    fn = gesto_da_pagina(conexoes.PAGINA, gesto)
    ponte = _Ponte()
    fn(_ctx(_externo(bus=bus, slot=slot)),
       {"externo": "aa:bb:cc:00:00:31", "valor": valor}, ponte)
    assert ponte.chamadas == [{"controles": {CHAVE: {campo: valor}}}]


@pytest.mark.parametrize("gesto", GESTOS)
def test_em_branco_apaga_o_campo(gesto: str) -> None:
    campo = gesto.split("-", 1)[1]
    ponte = _Ponte()
    gesto_da_pagina(conexoes.PAGINA, gesto)(
        _ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": ""}, ponte)
    assert ponte.chamadas == [{"controles": {CHAVE: {campo: None}}}]


@pytest.mark.parametrize(("gesto", "ruim"), [
    ("externo-modo", "xbox"), ("externo-botoes", "switch"), ("externo-cor", "Verde Imaginário"),
])
def test_resposta_de_fora_da_lista_nao_grava(gesto: str, ruim: str) -> None:
    ponte = _Ponte()
    with pytest.raises(ValueError):
        gesto_da_pagina(conexoes.PAGINA, gesto)(
            _ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": ruim}, ponte)
    assert ponte.chamadas == []


@pytest.mark.parametrize("gesto", GESTOS)
def test_clique_solto_ou_controle_que_sumiu_recusa_sem_gravar(gesto: str) -> None:
    fn = gesto_da_pagina(conexoes.PAGINA, gesto)
    ponte = _Ponte()
    with pytest.raises(ValueError):
        fn(_ctx(_externo()), {"valor": "xbox"}, ponte)
    with pytest.raises(RuntimeError):
        fn(_ctx(_externo()), {"externo": "aa:bb:cc:00:00:77", "valor": "xbox"}, ponte)
    with pytest.raises(RuntimeError):
        fn(_ctx(_externo(uniq="02:fe:00:00:00:31")),
           {"externo": "02:fe:00:00:00:31", "valor": "xbox"}, ponte)
    assert ponte.chamadas == []


def test_o_daemon_que_recusa_chega_a_ela_com_o_motivo() -> None:
    fn = gesto_da_pagina(conexoes.PAGINA, "externo-botoes")
    with pytest.raises(RuntimeError, match="sem serviço"):
        fn(_ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": "xbox"},
           _Ponte((False, "sem serviço")))


def test_o_que_a_lista_grava_o_cartao_mostra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fecha o laço: a escolha vira declaração e a declaração vira letras e borda."""
    gravado: dict[str, Any] = {}

    class _Dono(_Ponte):
        def machine_declare(self, carga: dict) -> Any:
            gravado.update(carga["controles"][CHAVE])
            return (True, None)

    gesto_da_pagina(conexoes.PAGINA, "externo-botoes")(
        _ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": "nintendo"}, _Dono())
    gesto_da_pagina(conexoes.PAGINA, "externo-cor")(
        _ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": "Cosmic Red"}, _Dono())
    _ela(monkeypatch, **gravado)
    html = conexoes._html_dos_externos(_ctx(_externo()))
    assert _letras(html) == "B A Y X"
    assert "border-color" in html


@pytest.mark.parametrize("gesto", GESTOS)
def test_depois_de_gravar_a_declaracao_e_relida(
        monkeypatch: pytest.MonkeyPatch, gesto: str) -> None:
    """Sem reler, o tique seguinte pintaria o que estava no disco antes do clique."""
    relidas: list[int] = []
    monkeypatch.setattr(conexoes, "_reler_a_declaracao", lambda: relidas.append(1))
    gesto_da_pagina(conexoes.PAGINA, gesto)(
        _ctx(_externo()), {"externo": "aa:bb:cc:00:00:31", "valor": ""}, _Ponte())
    assert relidas == [1]


def test_a_lista_nao_leva_marca_de_assento(monkeypatch: pytest.MonkeyPatch) -> None:
    """O único `data-` novo do cartão é o `data-gesto` e o `data-externo` das listas."""
    html = conexoes._html_dos_externos(_ctx(_externo()))
    for atributo in ("data-controle", "data-uniq", "data-hef-alvo", "data-campo"):
        assert atributo not in html, atributo
