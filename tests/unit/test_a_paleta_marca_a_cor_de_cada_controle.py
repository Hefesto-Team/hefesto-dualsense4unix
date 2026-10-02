#!/usr/bin/env python3
"""A paleta marca a cor de cada controle — A-PALETA-MARCA-A-COR-DE-CADA-CONTROLE-01."""
from __future__ import annotations

import itertools
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.core.led_control import LedSettings

PAGINA = "04-iluminacao.html"

UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))

AZUL, VERMELHO, VERDE = "#0000FF", "#FF0000", "#00FF00"
AMARELO, CIANO, BRANCO = "#FFFF00", "#00FFFF", "#FFFFFF"


def _hexa(rgb: Any) -> str:
    return "#{:02X}{:02X}{:02X}".format(*tuple(rgb)[:3])


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
    """A mesa das ~01h57 de 29/09, com a luz do diário das 01:59:33."""
    pecas = [
        _peca(1, (255, 0, 0), 1.0, nome="Cosmic Red", modelo="cosmic-red",
              via="usb"),
        _peca(2, LedSettings(lightbar=(0, 0, 255)).apply_brightness(0.08).lightbar,
              0.08, nome="White", modelo="white"),
        _peca(3, (255, 255, 0), 1.0, nome="Starlight Blue",
              modelo="starlight-blue"),
        _peca(4, (249, 249, 249), 0.99, nome="Galactic Purple",
              modelo="galactic-purple"),
    ]
    perfil = {
        "leds": {"auto_player_colors": True, "lightbar_brightness": 1.0},
        "controllers": {
            _chave(UNIQS[1]): {"leds": {"lightbar": [255, 255, 0],
                                        "lightbar_para_o_numero": 1}},
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
    pecas, perfil = CENAS[cena]()
    return _pintar_as_pecas(monkeypatch, pecas, perfil)


def _pintar_as_pecas(monkeypatch: pytest.MonkeyPatch, pecas: list[dict[str, Any]],
                     perfil: dict[str, Any]) -> tuple[Any, dict[str, dict[str, Any]]]:
    """Como `_pintar`, com as peças na ordem em que chegam ao `conectados`."""
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

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


def _os_brilhos_de_cada_trecho() -> list[float]:
    """Um brilho por trecho constante da conta do dono, e o 1,0."""
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    canais = {c for t in a04.tons_da_guia() for c in t if c}
    saltos = sorted({k / c for c in canais for k in range(1, c + 1)} | {1.0})
    meios = [(a + b) / 2 for a, b in itertools.pairwise(saltos)]
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


class TestAFotoDaBancada:
    """A cena das ~01h57, com o esperado escrito a partir dela."""

    def test_cada_coluna_tem_tres_x_e_a_propria_cor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: a igualdade de hex no `fileira_de_tons` — as três primeiras"""
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


class TestDuasPecasNoMesmoTom:
    """O «Todos» e o global num tom: a casa de vários donos."""

    def test_o_todos_nao_ganha_x_nem_gesto_em_coluna_nenhuma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA 1: um dono por hex — três colunas ganham X na própria cor."""
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

    def test_a_ordem_e_a_do_numero_e_nao_a_da_chegada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `conectados` na ordem inversa: a casa dividida segue na ordem do número."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        pecas, perfil = _a_cena_do_todos()
        _ctx, colunas = _pintar_as_pecas(monkeypatch, pecas[::-1], perfil)
        modelos = {p["n"]: p["modelo"] for p in pecas}
        quer = [_o_plastico_do_dono(modelos[n]).lower() for n in (1, 2, 3, 4)]
        for n, uniq in enumerate(UNIQS, start=1):
            verde = _casas(colunas[uniq]["tons"])[VERDE]
            tinta = re.search(r'--dono:([^"]+)"', verde["html"])
            assert tinta, verde["html"]
            achadas = [c.lower() for c in
                       re.findall(r"linear-gradient\((#[0-9a-fA-F]{6}),", tinta.group(1))]
            assert achadas == quer, f"P{n}: a linha verde sai em {achadas}"
            outros = [k for k in (1, 2, 3, 4) if k != n]
            posicoes = [verde["titulo"].find(f"P{k} (") for k in outros]
            assert all(p >= 0 for p in posicoes) and posicoes == sorted(posicoes), (
                f"P{n}: {verde['titulo']}")

        pecas, perfil = _a_cena_do_global((0, 255, 255))
        ctx, _colunas = _pintar_as_pecas(monkeypatch, pecas[::-1], perfil)
        with pytest.raises(RuntimeError) as erro:
            a04._sem_repetir_a_cor_do_vizinho(ctx, UNIQS[3], (0, 255, 255))
        assert "P1 (Cosmic Red)" in str(erro.value), str(erro.value)


@pytest.mark.parametrize("cena", sorted(CENAS))
def test_o_gesto_e_o_que_a_recusa_aceita(
    monkeypatch: pytest.MonkeyPatch, cena: str
) -> None:
    """Cada casa de cada coluna: gesto ⇔ a recusa aceita; X ⇔ dono que não é ele."""
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    ctx, colunas = _pintar(monkeypatch, cena)
    pecas, _perfil = CENAS[cena]()
    discordam = []
    marcas = _marcas(colunas)
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


def _o_plastico_do_dono(modelo: str) -> str:
    from hefesto_dualsense4unix.interface import pacotes  # noqa: F401 — põe `interface/` no path
    import monta

    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_para_a_borda

    return tom_para_a_borda(monta.cor_de_css(modelo)) if modelo else ""


DONOS_DA_FOTO = {VERMELHO: [1], AZUL: [2], AMARELO: [3], BRANCO: [4]}
DONOS_DO_TODOS = {VERDE: [1, 2, 3, 4]}


def _a_foto_sem_o_plastico_do_p2() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A foto, com o P2 de modelo desconhecido: a linha dele é tracejada."""
    pecas, perfil = _a_cena_da_foto()
    pecas[1]["modelo"] = ""
    return pecas, perfil


CENAS_DA_TELA = {
    "a foto": _a_cena_da_foto,
    "o Todos": _a_cena_do_todos,
    "o plástico que não chegou": _a_foto_sem_o_plastico_do_p2,
}

MEDIDA_DA_LINHA = r"""
(function(){
  var primeira = document.querySelector('[data-controle][data-conectado="sim"] .guia');
  if (primeira) primeira.scrollIntoView({block: 'center'});
  var de = document.documentElement;
  var px = function(v){ return parseFloat(v) || 0; };
  var colunas = {};
  document.querySelectorAll('[data-controle][data-conectado="sim"]').forEach(function(ctrl){
    var hex = ctrl.querySelector('.cel-cor .hex').getBoundingClientRect();
    colunas[ctrl.getAttribute('data-controle')] = {
      hex_topo: hex.top,
      casas: Array.prototype.map.call(ctrl.querySelectorAll('.guia .tom'), function(el){
        var r = el.getBoundingClientRect();
        var s = getComputedStyle(el);
        var b = getComputedStyle(el, '::before');
        var x0 = r.left + px(s.borderLeftWidth), y0 = r.top + px(s.borderTopWidth);
        return {
          classes: el.className,
          casa: [r.left, r.top, r.width, r.height],
          borda: s.borderTopColor,
          cursor: s.cursor,
          content: b.content,
          linha: [x0 + px(b.left), y0 + px(b.top), px(b.width), px(b.height)],
          cor: b.backgroundColor,
          imagem: b.backgroundImage
        };
      })
    };
  });
  return JSON.stringify({viewport: [de.clientWidth, de.clientHeight],
                         colunas: colunas});
})()
"""


def _carga_da_tela(cena: str) -> dict[str, Any]:
    """A carga do tique da cena, como o piloto a manda à página."""
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    pecas, perfil = CENAS_DA_TELA[cena]()
    ctx = _contexto(pecas)
    original = a04.perfil.ativo
    a04.perfil.ativo = lambda _nome: perfil  # type: ignore[assignment]
    try:
        pacote = pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    finally:
        a04.perfil.ativo = original  # type: ignore[assignment]
    para_pref = {UNIQS[p["n"] - 1]: f"p{p['n']}" for p in pecas}
    carga = pacotes.normalizar(pacote, para_pref)
    return pacotes.apagar_os_lugares_sem_dono(
        carga, sorted(para_pref.values()), pagina=PAGINA)


def _medir_a_linha(tamanho: tuple[int, int], pintar: str) -> dict[str, Any]:
    """Abre a 04 da bancada num WebKit offscreen, pinta, mede e fotografa."""
    import json

    from gi.repository import GLib, Gtk, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    saiu: list[str] = []
    foto: list[Any] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def fotografar() -> bool:
        foto.append(janela.get_pixbuf())
        Gtk.main_quit()
        return False

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(400, fotografar)

    def pintou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(MEDIDA_DA_LINHA, -1, None, None, None, mediu)

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, pintou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=False).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, f"o WebKit não respondeu em 20 s na vista {tamanho}"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    medido = json.loads(saiu[0])
    assert foto and foto[0] is not None, "a janela não devolveu a foto"
    medido["_foto"] = foto[0]
    return medido


def _pixel(foto: Any, x: float, y: float) -> tuple[int, int, int]:
    """O pixel da foto na coordenada da vista (a janela offscreen não tem escala)."""
    xi, yi = int(x), int(y)
    assert 0 <= xi < foto.get_width() and 0 <= yi < foto.get_height(), (
        f"({xi}, {yi}) fora da foto {foto.get_width()}x{foto.get_height()}")
    dados = foto.get_pixels()
    i = yi * foto.get_rowstride() + xi * foto.get_n_channels()
    return (dados[i], dados[i + 1], dados[i + 2])


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _perto(a: tuple[int, int, int], b: tuple[int, int, int], folga: int = 10) -> bool:
    return all(abs(x - y) <= folga for x, y in zip(a, b, strict=True))


def _vistas() -> dict[str, tuple[int, int]]:
    from hefesto_dualsense4unix.gui.ponte_da_tela import TAMANHO_OCULTA
    from hefesto_dualsense4unix.interface.olhar import VISTA_DELA

    return {"janela": TAMANHO_OCULTA, "dela": VISTA_DELA}


@pytest.fixture(scope="module")
def na_tela() -> dict[tuple[str, str], dict[str, Any]]:
    """Cada cena em cada vista, medida no WebKit. Sem tela, PULA (e pulo não é verde)."""
    import json

    from tests.conftest import exigir_gi_real

    exigir_gi_real("A-PALETA — a linha do dono medida no WebKit")
    gi = pytest.importorskip("gi", reason="a tela precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode no xvfb-run)")

    from hefesto_dualsense4unix.interface import hefesto_vivo

    medidas = {}
    for cena in CENAS_DA_TELA:
        pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
            "CARGA", json.dumps(_carga_da_tela(cena), ensure_ascii=False))
        for vista, tamanho in _vistas().items():
            medidas[(cena, vista)] = _medir_a_linha(tamanho, pintar)
    return medidas


def _modelos(cena: str) -> dict[int, str]:
    pecas, _perfil = CENAS_DA_TELA[cena]()
    return {p["n"]: p["modelo"] for p in pecas}


def _as_casas_na_tela(medido: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    """`{número: {hex da casa: o que o motor mediu}}`, pela ordem da guia."""
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    tons = [_hexa(t) for t in a04.tons_da_guia()]
    saida = {}
    for pref, coluna in medido["colunas"].items():
        assert len(coluna["casas"]) == len(tons), coluna
        saida[int(pref[1:])] = dict(zip(tons, coluna["casas"], strict=True))
    return saida


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_a_linha_tem_a_cor_do_plastico_do_dono(na_tela, vista: str) -> None:
    """Toda casa com dono, nas quatro colunas: a linha na tinta do plástico."""
    medido = na_tela[("a foto", vista)]
    modelos = _modelos("a foto")
    casas = _as_casas_na_tela(medido)
    assert set(casas) == {1, 2, 3, 4}, f"colunas pintadas: {sorted(casas)}"
    erradas = []
    for n, fileira in casas.items():
        for tom, casa in fileira.items():
            donos = DONOS_DA_FOTO.get(tom, [])
            if not donos:
                if casa["content"] not in ("none", "normal", ""):
                    erradas.append(f"P{n} {tom}: casa sem dono tem linha")
                continue
            quer = _o_plastico_do_dono(modelos[donos[0]])
            computada = casa["cor"].replace(" ", "")
            if computada != "rgb({},{},{})".format(*_rgb(quer)):
                erradas.append(f"P{n} {tom}: a linha é {casa['cor']}, o dono é {quer}")
            x, y, w, _h = casa["linha"]
            visto = _pixel(medido["_foto"], x + w / 2, int(y) + 1)
            if not _perto(visto, _rgb(quer)):
                erradas.append(f"P{n} {tom}: o pixel da linha é {visto}, o dono é {quer}")
    assert not erradas, "\n".join(erradas)


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_a_linha_mora_no_vao_entre_a_casa_e_a_caixa(na_tela, vista: str) -> None:
    """2 px abaixo da casa, 2 px de altura, a largura da casa, e sem cruzar a caixa."""
    medido = na_tela[("a foto", vista)]
    erradas = []
    for pref, coluna in medido["colunas"].items():
        for casa in coluna["casas"]:
            if "com-dono" not in casa["classes"]:
                continue
            cx, cy, cw, ch = casa["casa"]
            x, y, w, h = casa["linha"]
            if y - (cy + ch) < 2 - 0.25:
                erradas.append(f"{pref}: a linha começa {y - (cy + ch):.2f} px abaixo da casa")
            if h < 2:
                erradas.append(f"{pref}: a linha tem {h:.2f} px de altura")
            if abs(w - cw) > 1 or abs(x - cx) > 1:
                erradas.append(f"{pref}: a linha {x:.2f}+{w:.2f} e a casa {cx:.2f}+{cw:.2f}")
            if y + h > coluna["hex_topo"] + 0.25:
                erradas.append(f"{pref}: a linha acaba em {y + h:.2f} e a caixa começa "
                               f"em {coluna['hex_topo']:.2f}")
    assert not erradas, "\n".join(erradas)


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_a_casa_de_todos_tem_as_quatro_tintas_em_partes_iguais(na_tela, vista: str) -> None:
    """O «Todos»: a linha da casa verde é dos quatro, um quarto cada, na ordem."""
    medido = na_tela[("o Todos", vista)]
    modelos = _modelos("o Todos")
    casas = _as_casas_na_tela(medido)
    quer = [_rgb(_o_plastico_do_dono(modelos[n])) for n in DONOS_DO_TODOS[VERDE]]
    assert len(set(quer)) == 4, "a cena precisa de quatro plásticos diferentes"
    for n, fileira in casas.items():
        x, y, w, _h = fileira[VERDE]["linha"]
        vistos = [_pixel(medido["_foto"], x + (i + 0.5) * w / 4, int(y) + 1)
                  for i in range(4)]
        assert all(_perto(v, q) for v, q in zip(vistos, quer, strict=True)), (
            f"P{n}: os quartos da linha verde são {vistos}, os donos {quer}")


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_o_plastico_que_nao_chegou_e_tracejado(na_tela, vista: str) -> None:
    """A gramática do anel incerto: tracejada em `--comment`, nunca cor inventada."""
    medido = na_tela[("o plástico que não chegou", vista)]
    casas = _as_casas_na_tela(medido)
    comentario = (0x62, 0x72, 0xA4)
    for n, fileira in casas.items():
        casa = fileira[AZUL]
        assert casa["imagem"].startswith("repeating-linear-gradient"), (
            f"P{n}: a linha do P2 sem plástico é {casa['imagem']} / {casa['cor']}")
        x, y, w, _h = casa["linha"]
        vistos = [_pixel(medido["_foto"], x + i + 0.5, int(y) + 1) for i in range(int(w))]
        assert any(_perto(v, comentario, 24) for v in vistos), (n, vistos)
        assert any(not _perto(v, comentario, 24) for v in vistos), (
            f"P{n}: a linha do P2 é cheia, não tracejada: {vistos}")


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_a_casa_propria_nao_tem_mais_borda(na_tela, vista: str) -> None:
    """A escolha (a) da D-2909-A-LINHA-DA-COR-DO-DONO: a borda da escolhida saiu."""
    medido = na_tela[("a foto", vista)]
    for n, fileira in _as_casas_na_tela(medido).items():
        proprias = [c for c in fileira.values() if c["classes"].split()[:2] == ["tom", "on"]]
        assert len(proprias) == 1, f"P{n}: {len(proprias)} casas próprias"
        assert proprias[0]["borda"].replace(" ", "") in ("rgba(0,0,0,0)", "transparent"), (
            f"P{n}: a casa própria ainda tem borda {proprias[0]['borda']}")


@pytest.mark.parametrize("vista", ["janela", "dela"])
def test_so_a_casa_com_gesto_tem_a_mao_de_clique(na_tela, vista: str) -> None:
    """O cursor diz o que o gesto faz: a mão só onde há `data-gesto`."""
    erradas = []
    for cena in ("a foto", "o Todos"):
        for n, fileira in _as_casas_na_tela(na_tela[(cena, vista)]).items():
            for tom, casa in fileira.items():
                travada = "tomado" in casa["classes"] or (cena == "o Todos" and tom == VERDE)
                quer = "not-allowed" if travada else "pointer"
                if casa["cursor"] != quer:
                    erradas.append(f"{cena} P{n} {tom}: cursor {casa['cursor']}, quer {quer}")
    assert not erradas, "\n".join(erradas)


def test_a_regua_mede_as_vistas_que_pediu(na_tela) -> None:
    for (cena, vista), medido in na_tela.items():
        assert medido["viewport"] == list(_vistas()[vista]), (cena, vista, medido["viewport"])


def _os_modelos_da_folha() -> list[str]:
    """Os modelos que a folha do desenho publica — lidos, não digitados."""
    from hefesto_dualsense4unix.interface import pacotes  # noqa: F401 — põe `interface/` no path
    import monta

    return sorted(set(re.findall(r'svg\[data-colorway="([^"]+)"\]', monta.DS)))


def test_todo_modelo_tem_linha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tinta que o pacote emite para a linha, para cada modelo da folha."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
        FUNDO_DO_CARD,
        RAZAO_DA_BORDA,
    )
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04
    from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

    modelos = _os_modelos_da_folha()
    assert len(modelos) >= 28, f"a folha publica {len(modelos)} modelos"
    perfil = {"leds": {"auto_player_colors": True, "lightbar_brightness": 1.0}}
    monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: perfil)
    from hefesto_dualsense4unix.interface import pacotes

    erradas, tracejadas = [], []
    for modelo in modelos:
        ctx = _contexto([_peca(1, (0, 0, 255), 1.0, nome="DualSense", modelo=modelo)])
        tons = (pacotes.pacote_da_pagina(PAGINA, ctx) or {})["colunas"][UNIQS[0]]["tons"]
        tintas = re.findall(r"--dono:([^\"]+)\"", tons)
        if len(tintas) != 1:
            erradas.append(f"{modelo}: {len(tintas)} linhas na fileira")
            continue
        tinta = tintas[0]
        if tinta == a04.LINHA_INCERTA:
            tracejadas.append(modelo)
            continue
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", tinta):
            erradas.append(f"{modelo}: a tinta é {tinta!r}")
            continue
        razao = razao_contraste(_rgb(tinta), FUNDO_DO_CARD)
        if razao < RAZAO_DA_BORDA:
            erradas.append(f"{modelo}: {tinta} dá {razao:.2f}:1 contra o card")
    assert not erradas, "\n".join(erradas)
    assert len(tracejadas) < len(modelos), "todas tracejadas: o plástico não chega"
