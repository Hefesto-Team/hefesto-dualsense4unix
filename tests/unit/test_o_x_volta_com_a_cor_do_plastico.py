#!/usr/bin/env python3
"""O X volta com a cor do plástico — O-X-VOLTA-COM-A-COR-DO-PLASTICO-01.

Desde D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO a cor automática é o tom do
plástico, que cai fora dos onze tons da guia. `a_casa_da_cor` devolvia `None`
e a fileira dos vizinhos perdia o X (e o dono perdia a marca própria).
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    TABELA,
    tom_da_luz,
    tom_da_luz_do_nome,
)

PAGINA = "04-iluminacao.html"
UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))


def _hexa(rgb: Any) -> str:
    return "#{:02X}{:02X}{:02X}".format(*tuple(rgb)[:3])


def _a04() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

    return a04_iluminacao


def _os_plasticos_com_luz() -> list[tuple[str, tuple[int, int, int]]]:
    achados = []
    for cor in TABELA.values():
        luz = tom_da_luz(cor)
        if luz is not None:
            achados.append((cor.nome, luz))
    return achados


def _o_mais_perto_pelo_oraculo(luz: tuple[int, int, int]) -> str:
    """Independente da cura: distância ao quadrado, empate no primeiro da guia."""
    melhor, menor = "", 10**9
    for tom in _a04().tons_da_guia():
        d = sum((a - b) ** 2 for a, b in zip(tom, luz, strict=True))
        if d < menor:
            melhor, menor = _hexa(tom), d
    return melhor


def test_a_tabela_tem_plastico_fora_da_guia() -> None:
    """Sem isto a régua não teria o que medir (o White sozinho casa)."""
    guia = set(_a04().tons_da_guia())
    fora = [n for n, luz in _os_plasticos_com_luz() if luz not in guia]
    assert len(fora) >= 5, fora


def test_toda_luz_de_plastico_tem_casa_na_guia() -> None:
    """MORDIDA: o `return None` do fim de `a_casa_da_cor` — reprova nos fora da guia."""
    sem_casa = [(n, luz) for n, luz in _os_plasticos_com_luz()
                if _a04().a_casa_da_cor(luz) is None]
    assert not sem_casa, f"plásticos sem casa: {sem_casa}"


def test_a_casa_e_o_tom_mais_perto() -> None:
    erradas = []
    for nome, luz in _os_plasticos_com_luz():
        achada = _a04().a_casa_da_cor(luz)
        if achada != _o_mais_perto_pelo_oraculo(luz):
            erradas.append((nome, luz, achada))
    assert not erradas, erradas


@pytest.mark.parametrize(("plastico", "casa"), [
    ("Cosmic Red", "#FF0080"),
    ("Starlight Blue", "#0000FF"),
    ("Galactic Purple", "#8000FF"),
])
def test_a_tabela_do_pedido(plastico: str, casa: str) -> None:
    luz = tom_da_luz_do_nome(plastico)
    assert luz is not None
    assert _a04().a_casa_da_cor(luz) == casa


def test_o_preto_continua_sem_casa() -> None:
    assert _a04().a_casa_da_cor((0, 0, 0)) is None
    assert tom_da_luz_do_nome("Midnight Black") is None


def test_a_cor_que_nao_e_plastico_nem_tom_continua_sem_casa() -> None:
    """O global (`#2850B4`) é escolha do usuário: marcar o vizinho inventaria um dono."""
    assert _a04().a_casa_da_cor((0x28, 0x50, 0xB4)) is None


def _contexto(modelos: tuple[str, ...]) -> Any:
    from hefesto_dualsense4unix.interface import pacotes

    conectados, mesa = [], []
    for n, modelo in enumerate(modelos, start=1):
        luz = tom_da_luz_do_nome(modelo) or (255, 255, 255)
        uniq = UNIQS[n - 1]
        conectados.append({
            "uniq": uniq, "player": n, "player_slot": n, "connected": True,
            "transport": "bt", "battery_pct": 90, "is_primary": n == 1,
            "inputs": {}, "lightbar_rgb": list(luz), "lightbar_on": True,
            "brilho_da_barra": 1.0, "modelo": modelo})
        mesa.append({"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": f"P{n}",
                     "via": "BT", "transporte": "bt", "cor": modelo,
                     "conectado": True})
    return pacotes.Contexto(state={"active_profile": "regua"}, mesa=mesa,
                            conectados=conectados, estados={})


def _marcas(monkeypatch: pytest.MonkeyPatch, modelos: tuple[str, ...]
            ) -> dict[int, dict[str, set[str]]]:
    """Por jogador: onde está o `on` e onde estão os X, lidos do HTML da fileira."""
    from hefesto_dualsense4unix.interface import pacotes

    a04 = _a04()
    perfil = {"leds": {"auto_player_colors": True, "lightbar_brightness": 1.0}}
    monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: perfil)
    pacote = pacotes.pacote_da_pagina(PAGINA, _contexto(modelos)) or {}
    colunas = pacote["colunas"]
    tons = [_hexa(t) for t in a04.tons_da_guia()]
    saida: dict[int, dict[str, set[str]]] = {}
    for n in range(1, len(modelos) + 1):
        botoes = [b for b in colunas[UNIQS[n - 1]]["tons"].splitlines() if "<button" in b]
        assert len(botoes) == len(tons)
        on, x = set(), set()
        for tom, botao in zip(tons, botoes, strict=True):
            classes = set(re.search(r'class="([^"]*)"', botao).group(1).split())  # type: ignore[union-attr]
            if "on" in classes:
                on.add(tom)
            if "tomado" in classes:
                x.add(tom)
        saida[n] = {"on": on, "x": x}
    return saida


def test_p1_cosmic_red_e_p2_starlight_blue_tem_um_x_em_cada_fileira(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tabela do pedido: 1 X na fileira de cada um, na casa do OUTRO."""
    m = _marcas(monkeypatch, ("Cosmic Red", "Starlight Blue"))
    assert m[1]["on"] == {"#FF0080"} and m[1]["x"] == {"#0000FF"}
    assert m[2]["on"] == {"#0000FF"} and m[2]["x"] == {"#FF0080"}


def test_dois_plasticos_no_mesmo_tom_dividem_a_casa_sem_x(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cosmic Red e Nova Pink caem as duas em `#FF0080`: ficam as duas na casa."""
    assert tom_da_luz_do_nome("Cosmic Red") != tom_da_luz_do_nome("Nova Pink")
    m = _marcas(monkeypatch, ("Cosmic Red", "Nova Pink"))
    assert m[1]["on"] == m[2]["on"] == {"#FF0080"}
    assert m[1]["x"] == m[2]["x"] == set()


def test_o_lugar_vazio_nao_marca_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3 e P4 vazios: a mesa só tem dois controles, e só dois têm coluna."""
    m = _marcas(monkeypatch, ("Cosmic Red", "Starlight Blue"))
    assert set(m) == {1, 2}
