#!/usr/bin/env python3
"""A RÉGUA DO DESENHO NA ABA 06: o SVG é o do APARELHO, nunca o do mockup."""
from __future__ import annotations

import csv
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"

ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo"'
                       ' data-hef-atributo="data-colorway"')

UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"

CONTROLES = [
    {"uniq": UM, "connected": True, "transport": "usb", "player_slot": 1,
     "player": 1, "is_primary": True, "modelo": "White"},
    {"uniq": DOIS, "connected": True, "transport": "bt", "player_slot": 2,
     "player": 2, "is_primary": False},
]

MESA = [
    {"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": DOIS, "jogador": 2, "cor": "", "nome": "Não sei",
     "via": "BT", "transporte": "bt", "alvo": False, "mascara": "DualSense"},
]

ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": True, "speed": 9, "scroll_speed": 3,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": CONTROLES,
}


def _modelos_do_mapa() -> set[str]:
    """Os 28 ids, lidos do CSV que é dono deles."""
    linhas = [linha for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.lstrip().startswith("#")]
    return {(linha.get("id") or "").strip()
            for linha in csv.DictReader(linhas)
            if (linha.get("id") or "").strip()}


def _zonas_do_mapa() -> list[str]:
    """As classes de zona, lidas da folha que o gerador de cores pintou no SVG."""
    import monta

    return sorted(set(re.findall(
        r'svg\[data-colorway="[^"]+"\] (\.z-[a-z0-9_]+)', monta.DS)))


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def miolo(bancada: str) -> str:
    """Só o miolo, sem comentário HTML e sem `<style>` — as três armadilhas que"""
    corpo = bancada.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=re.S)


@pytest.fixture
def carga(monkeypatch):
    """O que o pacote emitiria NESTE tique, já na forma que a tela consome."""
    import pacotes
    from pacotes import a06_navegacao, perfil

    monkeypatch.setattr(perfil, "ativo", lambda nome: {"name": "Régua"} if nome else {})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=CONTROLES, estados={})
    return pacotes.normalizar(a06_navegacao.pacote(ctx),
                              {str(c["uniq"]): str(c["pref"]) for c in MESA})


def test_o_piloto_tem_o_alvo_de_atributo():
    """Sem o alvo `atributo` no piloto, esta aba não fica igual: fica PIOR."""
    vivo = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    assert "alvo === 'atributo'" in vivo, (
        "o piloto não tem o ramo `atributo` do `escrever()` — publicar a 06 "
        "assim APAGA os quatro desenhos da tela dela")
    assert "atributo_escrevivel" in vivo, (
        "o piloto tem o ramo `atributo` sem a guarda de nome — um "
        "`data-hef-atributo` mal escrito passaria a mexer no endereço ou no "
        "selo da medição desta casa")


def test_os_quatro_desenhos_tem_o_endereco_do_colorway(miolo):
    """Os quatro lugares da mesa, inclusive os vazios."""
    import monta

    assert miolo.count(ENDERECO_DO_DESENHO) == len(monta.MESA), (
        "um desenho da 06 perdeu o endereço do colorway — o `data-colorway` "
        "volta a ser o do mockup, e nada no produto o alcança")


def test_o_alvo_nomeia_o_atributo_certo(miolo):
    """Todo `data-hef-alvo="atributo"` diz QUAL atributo escrever."""
    import re

    alvos = miolo.count('data-hef-alvo="atributo"')
    nomes = len(re.findall(r'data-hef-atributo="[^"]+"', miolo))
    assert alvos == nomes, (
        f"há alvo `atributo` sem dizer QUAL atributo ({alvos} alvos, {nomes} "
        "nomes) — o piloto recusa o nome vazio e não pinta nada")

    import monta

    assert miolo.count('data-hef-atributo="data-colorway"') == len(monta.MESA), (
        "os desenhos da mesa deixaram de pedir o `data-colorway`")


def test_nao_ha_colorway_cravado_fora_dos_desenhos(miolo):
    """Todo `data-colorway` do miolo pertence a um `<svg>` endereçado."""
    import monta

    assert miolo.count("data-colorway=") == len(monta.MESA), (
        "apareceu `data-colorway` no miolo fora dos desenhos endereçados — "
        "cor de aparelho cravada onde o produto não tem como chegar")


def test_a_pagina_publica_os_28_modelos(bancada):
    """A folha das cores é a TABELA dela, e tem de estar inteira."""
    do_mapa = _modelos_do_mapa()
    na_pagina = set(re.findall(r'svg\[data-colorway="([^"]+)"\]', bancada))
    assert do_mapa, "o `cores-do-dualsense.csv` parou de declarar modelos"
    assert do_mapa <= na_pagina, (
        f"a 06 publica {len(na_pagina)} dos {len(do_mapa)} modelos do mapa — "
        f"faltam {sorted(do_mapa - na_pagina)}; quem tiver um desses vê o "
        f"desenho no cinza cru do `ds_limpo.svg`")


def test_nenhum_svg_carrega_a_folha_podada(bancada):
    """A folha do SVG SAI — a página já publica os 28, e a podada é justamente"""
    assert "cores-do-dualsense-folha" not in bancada, (
        "voltou uma folha podada para dentro de um SVG da 06: ela traz UM "
        "modelo, e quatro cópias dela são a mesma escolha cravada quatro vezes")


def test_a_folha_publicada_e_uma_so(bancada):
    """Uma cópia, não quatro: o `monta.svg()` poda porque quatro cópias dos 28"""
    for modelo in ("white", "cosmic-red", "galactic-purple"):
        assert bancada.count(f'svg[data-colorway="{modelo}"]{{') == 1, (
            f"o bloco de variáveis de {modelo!r} aparece mais de uma vez — a "
            f"folha voltou a ser publicada por SVG")


def test_a_zona_sem_colorway_cai_no_neutro(bancada):
    """Todas as zonas do mapa, e não algumas."""
    zonas = _zonas_do_mapa()
    assert len(zonas) >= 8, f"o mapa declara só {len(zonas)} zonas: {zonas}"
    for zona in zonas:
        assert f".ds-svg:not([data-colorway]) {zona} " in bancada, (
            f"a zona {zona} não cai no neutro quando o desenho fica sem "
            f"colorway — o `fill` cru do arquivo aparece como cor de aparelho")


def test_o_pacote_manda_o_colorway_de_cada_lugar(carga):
    """Quatro entradas, na ordem da mesa, e o do rádio VAZIO."""
    desenho = carga["mesa"].get("desenho")
    assert desenho is not None, (
        "o pacote parou de emitir `desenho` — o `data-colorway` de cada SVG "
        "fica sendo o do mockup para sempre")
    assert len(desenho) == 4, f"a lista não cobre os quatro lugares: {desenho}"
    assert desenho[0] == "white", desenho
    assert desenho[1] == "", (
        "o lugar do rádio, sem cor lida, recebeu um colorway — campo sem "
        "informação não mostra nada, e um colorway inventado pinta um aparelho")
    assert desenho[2:] == ["", ""], desenho


def test_o_colorway_emitido_nao_e_o_do_desenho(carga):
    """O P1 da mesa é White; o P1 do mockup não é. A régua morre se alguém"""
    import monta

    assert carga["mesa"]["desenho"][0] != str(monta.MESA[0]["cor"]), (
        "o pacote mandou para a tela o colorway do MOCKUP — é o defeito que "
        "esta onda inteira existe para matar")


def test_o_colorway_que_o_mapa_nao_conhece_vira_vazio():
    """Um slug fora do mapa pintaria o cinza cru PARECENDO cor lida."""
    from pacotes.a06_navegacao import colorway_do_aparelho

    assert colorway_do_aparelho("white") == "white"
    assert colorway_do_aparelho("") == ""
    assert colorway_do_aparelho("nao-existe-no-mapa") == ""


def test_o_desenho_tem_dono_e_nao_uma_tabela_nova():
    """`colorway_do_aparelho` LÊ a folha do mapa; ele não guarda cor nenhuma."""
    from pacotes.a06_navegacao import colorway_do_aparelho

    for modelo in sorted(_modelos_do_mapa()):
        assert colorway_do_aparelho(modelo) == modelo, (
            f"o modelo {modelo!r} do mapa dela não atravessa — quem tiver um "
            f"vê o desenho sem cor")
