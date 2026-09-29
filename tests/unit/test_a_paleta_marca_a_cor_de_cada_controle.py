#!/usr/bin/env python3
"""A paleta marca a cor de cada controle — A-PALETA-MARCA-A-COR-DE-CADA-CONTROLE-01.

O achado 7 da bancada de 29/09: com os quatro no rádio, as três primeiras
colunas da aba Iluminação tinham dois X onde deviam ter três, e a coluna do P4
não marcava a cor dele. A raiz: a fileira perguntava «este hex é o de algum
controle?» (três igualdades, dois dicionários de um dono por cor), e a pergunta
de tela é «de quem é esta casa?». O `#FCFCFC` do P4 (o branco a 99%) não tinha
casa.

As réguas 1 a 4 leem o pacote da aba. Nenhuma espera o que a própria função
devolve: o esperado sai da cena montada ou de um oráculo de força bruta.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

PAGINA = "04-iluminacao.html"

#: Faixa SINTÉTICA da casa, nunca endereço de aparelho.
UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))

AZUL, VERMELHO, VERDE = "#0000FF", "#FF0000", "#00FF00"
AMARELO, CIANO, BRANCO = "#FFFF00", "#00FFFF", "#FFFFFF"


def _hexa(rgb: Any) -> str:
    return "#{:02X}{:02X}{:02X}".format(*tuple(rgb)[:3])


# ---------------------------------------------------------------------------
# A cena: quatro controles, a luz que o daemon publica e o perfil do disco
# ---------------------------------------------------------------------------


def _peca(n: int, luz: tuple[int, int, int], brilho: float, *, nome: str,
          modelo: str, via: str = "bt") -> dict[str, Any]:
    return {"n": n, "luz": luz, "brilho": brilho, "nome": nome,
            "modelo": modelo, "via": via}


def _chave(uniq: str) -> str:
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    return a04.chave_do_override(uniq)


def _contexto(pecas: list[dict[str, Any]]) -> Any:
    from hefesto_dualsense4unix.interface import pacotes

    conectados, mesa = [], []
    for p in pecas:
        uniq = UNIQS[p["n"] - 1]
        conectados.append({
            "uniq": uniq, "player": p["n"], "player_slot": p["n"],
            "connected": True, "transport": p["via"], "battery_pct": 90,
            "is_primary": p["n"] == 1, "inputs": {},
            "lightbar_rgb": list(p["luz"]), "lightbar_on": True,
            "brilho_da_barra": p["brilho"]})
        mesa.append({"pref": f"p{p['n']}", "jogador": p["n"], "uniq": uniq,
                     "nome": p["nome"], "via": p["via"].upper(),
                     "transporte": p["via"], "cor": p["modelo"],
                     "conectado": True})
    return pacotes.Contexto(state={"active_profile": "regua"}, mesa=mesa,
                            conectados=conectados, estados={})


def _a_cena_da_foto() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A mesa das ~01h57 de 29/09, com a luz do diário das 01:59:33.

    O P1 vai no CABO, que a foto não tinha: é o que cobre o transporte.
    """
    pecas = [
        _peca(1, (255, 0, 0), 1.0, nome="Cosmic Red", modelo="cosmic-red",
              via="usb"),
        _peca(2, (0, 0, 20), 0.08, nome="White", modelo="white"),
        _peca(3, (255, 255, 0), 1.0, nome="Starlight Blue",
              modelo="starlight-blue"),
        _peca(4, (249, 249, 249), 0.99, nome="Galactic Purple",
              modelo="galactic-purple"),
    ]
    perfil = {
        "leds": {"auto_player_colors": True, "lightbar_brightness": 1.0},
        "controllers": {
            # o amarelo guardado para o número 1: fóssil, ele é o 2 hoje
            _chave(UNIQS[1]): {"leds": {"lightbar": [255, 255, 0],
                                        "lightbar_para_o_numero": 1}},
            # o override legado: sem procedência, fora dos onze tons
            _chave(UNIQS[3]): {"leds": {"lightbar": [252, 252, 252],
                                        "lightbar_brightness": 0.99}},
        },
    }
    return pecas, perfil


def _a_cena_do_todos() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """O «Todos»: os quatro no verde, com a procedência `todos` nos quatro."""
    modelos = ("cosmic-red", "white", "starlight-blue", "galactic-purple")
    pecas = [_peca(n, (0, 255, 0), 1.0, nome=f"DualSense {n}", modelo=modelos[n - 1],
                   via="usb" if n == 1 else "bt") for n in (1, 2, 3, 4)]
    perfil = {
        "leds": {"auto_player_colors": True, "lightbar_brightness": 1.0},
        "controllers": {_chave(u): {"leds": {"lightbar": [0, 255, 0],
                                             "lightbar_para_o_numero": "todos"}}
                        for u in UNIQS},
    }
    return pecas, perfil


def _a_cena_do_global(global_: tuple[int, int, int]
                      ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A paleta desligada: P1 e P2 no global, P3 e P4 com cor própria."""
    pecas = [
        _peca(1, global_, 1.0, nome="Cosmic Red", modelo="cosmic-red", via="usb"),
        _peca(2, global_, 1.0, nome="White", modelo="white"),
        _peca(3, (255, 0, 0), 1.0, nome="Starlight Blue", modelo="starlight-blue"),
        _peca(4, (255, 255, 0), 1.0, nome="Galactic Purple",
              modelo="galactic-purple"),
    ]
    perfil = {
        "leds": {"auto_player_colors": False, "lightbar": list(global_),
                 "lightbar_brightness": 1.0},
        "controllers": {
            _chave(UNIQS[2]): {"leds": {"lightbar": [255, 0, 0],
                                        "lightbar_para_o_numero": 3}},
            _chave(UNIQS[3]): {"leds": {"lightbar": [255, 255, 0],
                                        "lightbar_para_o_numero": 4}},
        },
    }
    return pecas, perfil


CENAS = {
    "a foto": _a_cena_da_foto,
    "o Todos": _a_cena_do_todos,
    "o global num tom": lambda: _a_cena_do_global((0, 255, 255)),
    "o global fora da guia": lambda: _a_cena_do_global((0x28, 0x50, 0xB4)),
}


def _pintar(monkeypatch: pytest.MonkeyPatch, cena: str
            ) -> tuple[Any, dict[str, dict[str, Any]]]:
    """O contexto da cena e as colunas que o pacote da aba emite para ela."""
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    pecas, perfil = CENAS[cena]()
    monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: perfil)
    ctx = _contexto(pecas)
    pacote = pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    return ctx, pacote["colunas"]


_CLASSE = re.compile(r'class="([^"]*)"')
_TITULO = re.compile(r'title="([^"]*)"')


def _casas(html: str) -> dict[str, dict[str, Any]]:
    """A fileira lida casa a casa, pela ordem da guia: `{hex: o que ela diz}`."""
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    botoes = [linha for linha in html.splitlines() if "<button" in linha]
    tons = [_hexa(t) for t in a04.tons_da_guia()]
    assert len(botoes) == len(tons), html
    casas = {}
    for tom, botao in zip(tons, botoes, strict=True):
        classes = set(_CLASSE.search(botao).group(1).split())  # type: ignore[union-attr]
        titulo = _TITULO.search(botao)
        casas[tom] = {"on": "on" in classes, "x": "tomado" in classes,
                      "gesto": "data-gesto=" in botao,
                      "travada": 'aria-disabled="true"' in botao,
                      "titulo": titulo.group(1) if titulo else "",
                      "html": botao}
    return casas


def _marcas(colunas: dict[str, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Por número: onde está o `on`, onde estão os X e onde falta o gesto."""
    saida = {}
    for n, uniq in enumerate(UNIQS, start=1):
        if uniq not in colunas:
            continue
        casas = _casas(colunas[uniq]["tons"])
        saida[n] = {
            "on": {h for h, c in casas.items() if c["on"]},
            "x": {h for h, c in casas.items() if c["x"]},
            "sem_gesto": {h for h, c in casas.items() if not c["gesto"]},
            "casas": casas,
        }
    return saida


# ---------------------------------------------------------------------------
# Régua 1 — a casa de cada cor, contra um oráculo de força bruta
# ---------------------------------------------------------------------------


def _os_brilhos_de_cada_trecho() -> list[float]:
    """Um brilho por trecho constante da conta do dono, e o 1,0.

    A conta trunca `c × brilho` por canal: ela só muda nos saltos `k/c` de
    cada canal `c` que os tons têm. O meio de cada par de saltos vizinhos
    representa o trecho inteiro. Os canais se leem dos tons, não se digitam.
    """
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    canais = {c for t in a04.tons_da_guia() for c in t if c}
    saltos = sorted({k / c for c in canais for k in range(1, c + 1)} | {1.0})
    meios = [(a + b) / 2 for a, b in zip(saltos, saltos[1:], strict=False)]
    return [*meios, 1.0]


def _oraculo() -> dict[tuple[int, int, int], set[str]]:
    """Cada cor acesa que algum tom dá em alguma intensidade: `{cor: tons}`."""
    from hefesto_dualsense4unix.core.led_control import LedSettings
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    quem_acende: dict[tuple[int, int, int], set[str]] = {}
    for tom in a04.tons_da_guia():
        for brilho in _os_brilhos_de_cada_trecho():
            acesa = LedSettings(lightbar=tom).apply_brightness(brilho).lightbar
            if acesa != (0, 0, 0):
                quem_acende.setdefault(acesa, set()).add(_hexa(tom))
    return quem_acende


class TestACasaDeCadaCor:
    """`a_casa_da_cor`: o tom da guia que acende a cor pedida, se for único."""

    def test_toda_cor_acesa_cai_na_casa_do_unico_tom_que_a_acende(self) -> None:
        """MORDIDA: a casa só por igualdade — todo brilho abaixo de 100% reprova."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        oraculo = _oraculo()
        assert len(oraculo) > 1000, "a varredura não varreu"
        erradas = []
        for acesa, tons in oraculo.items():
            esperado = next(iter(tons)) if len(tons) == 1 else None
            achado = a04.a_casa_da_cor(acesa)
            if achado != esperado:
                erradas.append((acesa, sorted(tons), achado))
        assert not erradas, (
            f"{len(erradas)} cores acesas na casa errada; as primeiras: {erradas[:5]}")

    def test_o_branco_a_99_por_cento_e_a_casa_do_branco(self) -> None:
        """O `#FCFCFC` do P4 da bancada de 29/09."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        assert a04.a_casa_da_cor((252, 252, 252)) == BRANCO

    def test_o_tom_exato_e_a_propria_casa(self) -> None:
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        for tom in a04.tons_da_guia():
            assert a04.a_casa_da_cor(tom) == _hexa(tom)

    @pytest.mark.parametrize("cor", [(0x28, 0x50, 0xB4), (0, 0, 0), (1, 0, 0)],
                             ids=["o global dela", "o preto", "o ambíguo"])
    def test_sem_casa(self, cor: tuple[int, int, int]) -> None:
        """Fora da guia, apagada, ou acesa igual por mais de um tom: sem casa."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        assert a04.a_casa_da_cor(cor) is None


# ---------------------------------------------------------------------------
# Régua 2 — a foto da bancada, no pacote
# ---------------------------------------------------------------------------


class TestAFotoDaBancada:
    """A cena das ~01h57, com o esperado escrito a partir dela."""

    def test_cada_coluna_tem_tres_x_e_a_propria_cor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: a igualdade de hex no `fileira_de_tons` — as três primeiras
        colunas ficam com dois X (a foto), e o P4 fica sem marca."""
        _ctx, colunas = _pintar(monkeypatch, "a foto")
        marcas = _marcas(colunas)

        assert {n: m["x"] for n, m in marcas.items()} == {
            1: {AZUL, AMARELO, BRANCO},
            2: {VERMELHO, AMARELO, BRANCO},
            3: {AZUL, VERMELHO, BRANCO},
            4: {AZUL, VERMELHO, AMARELO},
        }
        assert {n: m["on"] for n, m in marcas.items()} == {
            1: {VERMELHO}, 2: {AZUL}, 3: {AMARELO}, 4: {BRANCO}}

    def test_a_caixa_do_p4_diz_a_cor_pedida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A casa é só onde a marca pousa: a caixa diz o que está no disco."""
        _ctx, colunas = _pintar(monkeypatch, "a foto")
        assert colunas[UNIQS[3]]["hex"] == "#FCFCFC"

    def test_o_x_diz_de_quem_e(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _ctx, colunas = _pintar(monkeypatch, "a foto")
        casas = _casas(colunas[UNIQS[0]]["tons"])
        assert casas[BRANCO]["titulo"] == "P4 (Galactic Purple)"
        assert casas[AZUL]["titulo"] == "P2 (White)"

    def test_o_p1_clicando_o_branco_e_recusado_com_o_nome_do_p4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: a recusa por igualdade — o branco passa calado."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        ctx, _colunas = _pintar(monkeypatch, "a foto")
        with pytest.raises(RuntimeError) as erro:
            a04._sem_repetir_a_cor_do_vizinho(ctx, UNIQS[0], (255, 255, 255))
        assert "P4 (Galactic Purple)" in str(erro.value)


# ---------------------------------------------------------------------------
# Régua 3 — duas peças no mesmo tom
# ---------------------------------------------------------------------------


class TestDuasPecasNoMesmoTom:
    """O «Todos» e o global num tom: a casa de vários donos."""

    def test_o_todos_nao_ganha_x_nem_gesto_em_coluna_nenhuma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA 1: um dono por hex — três colunas ganham X na própria cor.
        MORDIDA 2: o gesto de volta na casa dividida — as quatro oferecem o
        clique que a régua 4 mostra recusado."""
        _ctx, colunas = _pintar(monkeypatch, "o Todos")
        marcas = _marcas(colunas)
        assert set(marcas) == {1, 2, 3, 4}
        for n, m in marcas.items():
            verde = m["casas"][VERDE]
            assert m["on"] == {VERDE}, f"P{n}: {m['on']}"
            assert not m["x"], f"P{n} ganhou X em {m['x']}"
            assert not verde["gesto"] and verde["travada"], (
                f"a casa verde do P{n} oferece o clique que a recusa recusa")

    def test_a_casa_dividida_nomeia_os_outros_donos_na_ordem_do_numero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ctx, colunas = _pintar(monkeypatch, "o Todos")
        casas = _casas(colunas[UNIQS[0]]["tons"])
        titulo = casas[VERDE]["titulo"]
        posicoes = [titulo.find(f"P{n} (") for n in (2, 3, 4)]
        assert all(p >= 0 for p in posicoes) and posicoes == sorted(posicoes), titulo
        assert "P1 (" not in titulo, titulo

    def test_o_global_num_tom_e_de_dois_donos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ctx, colunas = _pintar(monkeypatch, "o global num tom")
        marcas = _marcas(colunas)
        for n in (1, 2):
            assert marcas[n]["on"] == {CIANO}
            assert marcas[n]["x"] == {VERMELHO, AMARELO}
            assert CIANO in marcas[n]["sem_gesto"]
        assert marcas[3]["x"] == {CIANO, AMARELO}
        assert marcas[4]["x"] == {CIANO, VERMELHO}

    def test_o_global_fora_da_guia_nao_marca_casa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ctx, colunas = _pintar(monkeypatch, "o global fora da guia")
        marcas = _marcas(colunas)
        assert marcas[1]["on"] == marcas[2]["on"] == set()
        assert marcas[1]["x"] == marcas[2]["x"] == {VERMELHO, AMARELO}
        assert marcas[3]["on"] == {VERMELHO} and marcas[3]["x"] == {AMARELO}
        assert marcas[4]["on"] == {AMARELO} and marcas[4]["x"] == {VERMELHO}


# ---------------------------------------------------------------------------
# Régua 4 — o gesto é o que a recusa aceita
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cena", sorted(CENAS))
def test_o_gesto_e_o_que_a_recusa_aceita(
    monkeypatch: pytest.MonkeyPatch, cena: str
) -> None:
    """Cada casa de cada coluna: gesto ⇔ a recusa aceita; X ⇔ dono que não é ele.

    A régua antiga com este nome montava o `tomadas` à mão e lia só o X; esta
    chama a recusa. MORDIDA: a recusa por igualdade — na foto, o branco passa
    calado na coluna do P1, que tem X nele.
    """
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    ctx, colunas = _pintar(monkeypatch, cena)
    pecas, _perfil = CENAS[cena]()
    discordam = []
    marcas = _marcas(colunas)
    #: os donos de cada casa, lidos da marca própria de cada coluna
    donos = {tom: {n for n, m in marcas.items() if tom in m["on"]}
             for tom in next(iter(marcas.values()))["casas"]}
    for n, m in marcas.items():
        uniq = UNIQS[n - 1]
        for tom, casa in m["casas"].items():
            deve_x = bool(donos[tom]) and n not in donos[tom]
            if casa["x"] != deve_x:
                discordam.append(f"P{n} {tom}: X={casa['x']} donos={sorted(donos[tom])}")
            rgb = (int(tom[1:3], 16), int(tom[3:5], 16), int(tom[5:7], 16))
            try:
                a04._sem_repetir_a_cor_do_vizinho(ctx, uniq, rgb)
                aceita = True
            except RuntimeError:
                aceita = False
            if casa["gesto"] != aceita:
                discordam.append(f"P{n} {tom}: gesto={casa['gesto']} recusa aceita={aceita}")
            if casa["x"] and aceita:
                discordam.append(f"P{n} {tom}: X numa casa que a recusa aceita")
    assert len(pecas) == 4
    assert not discordam, "\n".join(discordam)
