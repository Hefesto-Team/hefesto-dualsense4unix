#!/usr/bin/env python3
"""A-LINHA-DA-COR-ESCOLHIDA-TEM-A-COR-DO-CONTROLE-01 — a linha e a 02 têm um dono só.

A fala dela, 29/09 (~18h50): *«essa linha abaixo da cor selecionada tem que ter a
cor de cada controle no caso ali tá certo no p1, por ser branca, mas o do p2 não
tem a cor dele roxo.»* <!-- noqa-acento: citação literal dela -->
O pixel da foto dela era o roxo certo: o defeito era de tamanho, e a cura (a (b)
das ESCOLHAS de 08/10/2026, a linha a 6 px) mora na folha do `aba04.py`, medida
no WebKit pela `test_a_paleta_marca_a_cor_de_cada_controle.py`. Aqui, sem
janela, o esperado sai do dono que a 02 usa (`cor_da_borda`), e nunca da linha.
"""
from __future__ import annotations

import colorsys
import re

import pytest

from tests.unit.test_a_paleta_marca_a_cor_de_cada_controle import (
    UNIQS,
    _a_cena_da_fala,
    _casas,
    _hexa,
    _os_modelos_da_folha,
    _pintar_as_pecas,
)

AMARELO_DO_P1 = (255, 255, 0)
VERDE_AGUA_DO_P2 = (0, 255, 128)
_DONO = re.compile(r"--dono:([^\";]+)")


def test_a_linha_e_a_borda_da_02_perguntam_ao_mesmo_dono() -> None:
    """Os 28 modelos da folha e um `id` que não existe: a linha é a borda da 02.

    A MORDIDA: faça o `plastico_da_linha` clarear por um segundo piso
    (`tom_para_a_borda(..., minimo=3.0)`) e os onze plásticos abaixo de 3:1
    deixam de ser a borda da 02.
    """
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    modelos = _os_modelos_da_folha()
    assert len(modelos) >= 28, f"a folha publica {len(modelos)} modelos"
    erradas = []
    for slug in [*modelos, "modelo-que-nao-existe"]:
        borda, linha = a02.cor_da_borda(slug), a04.plastico_da_linha(slug)
        if borda == a02.BORDA_SEM_COR:
            if linha or a04.tinta_da_linha([{"plastico": linha}]) != a04.LINHA_INCERTA:
                erradas.append(f"{slug}: a 02 não sabe e a linha é {linha!r}")
        elif linha.lower() != borda.lower():
            erradas.append(f"{slug}: a linha é {linha}, a borda da 02 é {borda}")
    assert not erradas, "\n".join(erradas)


def _o_dono_de_cada_casa(tons_html: str) -> dict[str, str]:
    """`{hex da casa: --dono}` de uma coluna, só das casas com dono."""
    saida = {}
    for tom, casa in _casas(tons_html).items():
        achado = _DONO.search(casa["html"])
        if achado:
            saida[tom] = achado.group(1)
    return saida


def test_a_cena_da_fala_da_a_linha_roxa_ao_p2(monkeypatch: pytest.MonkeyPatch) -> None:
    """P1 White no BT com o `#FFFF00`, P2 Galactic Purple no cabo com o `#00FF80`.

    Nas duas colunas, a casa amarela veste a borda do White na 02 e a verde-água
    a do Galactic Purple, cujo matiz é roxo (entre 250° e 300°).

    AS MORDIDAS: o `_as_pecas_da_mesa` pondo em `plastico` a cor da barra, ou a
    `fileira_de_tons` pintando toda casa com o plástico do P1 — nas duas, a casa
    verde-água perde o roxo.
    """
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    pecas, perfil = _a_cena_da_fala()
    _ctx, colunas = _pintar_as_pecas(monkeypatch, pecas, perfil)
    amarela = a04.a_chave_da_cor(AMARELO_DO_P1)
    verde = a04.a_chave_da_cor(VERDE_AGUA_DO_P2)
    assert amarela and verde and amarela != verde, (amarela, verde)
    quer = {amarela.upper(): a02.cor_da_borda("white").lower(),
            verde.upper(): a02.cor_da_borda("galactic-purple").lower()}
    for n in (1, 2):
        donos = {t.upper(): d.lower() for t, d in
                 _o_dono_de_cada_casa(colunas[UNIQS[n - 1]]["tons"]).items()}
        assert donos == quer, f"P{n}: as linhas são {donos}, os donos da 02 {quer}"

    roxo = quer[verde.upper()]
    r, g, b = (int(roxo[i:i + 2], 16) / 255 for i in (1, 3, 5))
    matiz = colorsys.rgb_to_hsv(r, g, b)[0] * 360
    assert 250 <= matiz <= 300, f"o dono do Galactic Purple dá {roxo}, matiz {matiz:.0f}°"


def test_a_cena_da_fala_tem_as_duas_vias() -> None:
    """A cena é a da foto dela: o P1 no rádio, o P2 no cabo."""
    pecas, _perfil = _a_cena_da_fala()
    assert [(p["n"], p["modelo"], p["via"], _hexa(p["luz"])) for p in pecas] == [
        (1, "white", "bt", "#FFFF00"), (2, "galactic-purple", "usb", "#00FF80")]
