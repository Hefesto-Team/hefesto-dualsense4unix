"""Abrir uma lista suspensa não manda gesto.

A sprint: ABRIR-A-LISTA-SUSPENSA-NAO-MANDA-GESTO-01.

MEDIDO EM 19/11/2026, antes da cura: o BOOTSTRAP do piloto ligava `change` e `click` ao mesmo
`manda_do_alvo`, e a carga levava `tipo` e `evento` sem filtro. A regra «o pedido de uma lista e de
uma barra é o `change`» morava em guardas por gesto, e quatro listas nasceram sem guarda: `imersao`
(aba 03), `efeito-da-luz` (04), `efeito-haptico` e `efeito-imersao` (05). Com `evento=click` a de
imersão regravava o gatilho e o perfil, a da luz gravava a luz, a háptica tocava por um segundo e o
padrão dos motores tocava o antigo.

O dono é o despachante do piloto: o `_gesto` descarta o `click` de lista e de barra antes de achar
o dono do gesto, e o BOOTSTRAP não o manda. A régua lê cada `data-gesto` de lista e de barra das
páginas publicadas, nas dez abas, e exige: `click` não chega ao despachante nem ao registro do
piloto; `change` chega. O `click` de botão e de caixa de marcar passa.
"""
from __future__ import annotations

import pathlib
import sys
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import onde, pacotes

P1 = "aa:bb:cc:00:00:01"


class _ListasEBarras(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.achados: set[tuple[str, str, str]] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        gesto = a.get("data-gesto") or a.get("data-hef-gesto")
        if not gesto:
            return
        if tag == "select":
            self.achados.add((tag, "", gesto))
        elif tag == "input" and a.get("type") == "range":
            self.achados.add((tag, "range", gesto))


def _gestos_de_lista_e_de_barra() -> list[tuple[str, str, str, str]]:
    achados: list[tuple[str, str, str, str]] = []
    for caminho in sorted(onde.paginas(publicado=True)):
        leitor = _ListasEBarras()
        leitor.feed(caminho.read_text(encoding="utf-8"))
        achados += [(caminho.name, tag, entrada, gesto)
                    for tag, entrada, gesto in sorted(leitor.achados)]
    return achados


GESTOS = _gestos_de_lista_e_de_barra()


class _Espia:
    def __init__(self) -> None:
        self.despachos: list[tuple[str, str]] = []
        self.acoes: list[str] = []


@pytest.fixture
def espia(monkeypatch: pytest.MonkeyPatch) -> _Espia:
    visto = _Espia()

    def despachar(pagina: str, nome: str, o: dict[str, Any], trabalho: Any) -> None:
        visto.despachos.append((pagina, nome))

    monkeypatch.setattr(pacotes, "despachar", despachar)
    monkeypatch.setattr(pacotes, "gesto_da_pagina",
                        lambda pagina, nome: lambda ctx, o, p: visto.acoes.append(nome))
    return visto


def _piloto() -> Any:
    piloto = object.__new__(hv.Piloto)
    piloto.gestos = []
    piloto.desfechos = {}
    piloto._pintada = "algo"
    piloto._ctx_de_agora = None
    piloto._com_uniq = lambda o: {**o, "uniq": P1}
    piloto._pousou = lambda *a, **k: False
    piloto.pagina = "05-vibracao.html"
    return piloto


def _carga(pagina: str, tag: str, entrada: str, gesto: str, evento: str) -> dict[str, Any]:
    return {"gesto": gesto, "pagina": pagina, "tipo": tag, "tipoDoCampo": entrada,  # (noqa-acento)
            "evento": evento, "valor": "x", "controle": P1, "voo": ""}


def test_as_paginas_publicadas_tem_lista_e_barra_de_gesto() -> None:
    """A régua não passa em silêncio sobre uma página sem nenhuma lista."""
    assert len(GESTOS) >= 20, GESTOS
    paginas = {g[0] for g in GESTOS}
    assert {"03-gatilhos.html", "04-iluminacao.html", "05-vibracao.html"} <= paginas


@pytest.mark.parametrize(("pagina", "tag", "entrada", "gesto"), GESTOS)  # (noqa-acento)
def test_o_click_de_lista_e_de_barra_nao_chega_ao_despachante(
        espia: _Espia, pagina: str, tag: str, entrada: str, gesto: str) -> None:
    """D-2511-A-LISTA-E-A-BARRA-PEDEM-SO-PELA-ESCOLHA: `click` não despacha nem registra; o
    `change` do mesmo elemento despacha."""
    piloto = _piloto()
    piloto._gesto(_carga(pagina, tag, entrada, gesto, "click"))
    assert espia.despachos == [], f"abrir {tag} de «{gesto}» mandou gesto: {espia.despachos}"
    assert piloto.gestos == []
    piloto._gesto(_carga(pagina, tag, entrada, gesto, "change"))
    assert espia.despachos == [(pagina, gesto)], (
        f"a escolha em «{gesto}» não chegou ao despachante: {espia.despachos}")


@pytest.mark.parametrize(("tag", "entrada"), [("button", ""), ("input", "checkbox"),
                                                ("input", "text"), ("div", "")])
def test_o_click_de_botao_e_de_caixa_de_marcar_segue_passando(
        espia: _Espia, tag: str, entrada: str) -> None:
    """A regra é de lista e de barra: o resto do clique segue como era."""
    piloto = _piloto()
    piloto._gesto(_carga("01-jogar.html", tag, entrada, "cadeado", "click"))
    assert espia.despachos == [("01-jogar.html", "cadeado")]


def test_o_bootstrap_nao_manda_o_click_de_lista_nem_de_barra() -> None:
    """O ouvinte do `click` sai antes de montar a carga, e a carga diz o tipo da entrada."""
    texto = hv.BOOTSTRAP if hasattr(hv, "BOOTSTRAP") else ""
    assert "e.tagName === 'SELECT'" in texto
    assert "e.type === 'range'" in texto
    assert "tipoDoCampo: (alvo.type || '')" in texto
    assert "entrada: (alvo.type" not in texto


PAGINA_DO_CLIQUE = """<!doctype html><meta charset="utf-8"><body>
<select data-gesto="efeito-imersao" style="width:200px">
  <option value="">Escolha</option><option value="a">A</option><option value="b">B</option></select>
<input type="range" data-gesto="forca" min="0" max="10" value="0" style="width:200px">
<button data-gesto="testar">Testar</button>
<label><input type="checkbox" data-gesto="marcar"> Marcar</label>
<script>
  window.recebidos = [];
  window.webkit = {messageHandlers: {hefesto: {postMessage: function(m){
    const o = JSON.parse(m); if (o.gesto) window.recebidos.push(o.gesto + ':' + o.evento);
  }}}};
</script></body>"""

CHROME = pathlib.Path("/usr/bin/google-chrome")


@pytest.fixture
def pagina_do_clique(tmp_path: pathlib.Path) -> Any:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")
    arquivo = tmp_path / "clique.html"
    arquivo.write_text(PAGINA_DO_CLIQUE, encoding="utf-8")
    with playwright.sync_playwright() as pw:
        motor = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = motor.new_page(viewport={"width": 800, "height": 600})
            pg.goto(arquivo.as_uri())
            assert pg.evaluate(hv.BOOTSTRAP) == "ok"
            yield pg
        finally:
            motor.close()


def test_o_bootstrap_na_pagina_nao_manda_o_click_de_lista_nem_de_barra(
        pagina_do_clique: Any) -> None:
    """O clique do rato numa lista e numa barra não sai da página; a escolha, o botão e a caixa
    de marcar saem."""
    pg = pagina_do_clique
    pg.click("select")
    pg.keyboard.press("Escape")
    pg.click("input[type=range]")
    pg.select_option("select", "b")
    pg.click("button")
    pg.click("input[type=checkbox]")
    recebidos = list(pg.evaluate("window.recebidos"))
    assert "efeito-imersao:click" not in recebidos, recebidos
    assert "forca:click" not in recebidos, recebidos
    assert "efeito-imersao:change" in recebidos, recebidos
    assert {"testar:click", "marcar:click"} <= set(recebidos), recebidos
