#!/usr/bin/env python3
"""O AJUDANTE QUE ABRE A PÁGINA ESPERA OS SINAIS DA PÁGINA, e o que não vem tem nome e prazo.

A página daqui é servida pela rota do próprio Playwright, sem rede: o endereço
``http://pagina.invalid/`` nunca sai do navegador, e a fonte só chega quando a
rota a entrega (ou nunca, quando a régua prende a rota).
"""
from __future__ import annotations

import pathlib
import time
from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.pagina_pronta import abrir

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CHROME = pathlib.Path("/usr/bin/google-chrome")
FONTE = RAIZ / "assets" / "fontes" / "JetBrainsMono-wght.ttf"
ENDERECO = "http://pagina.invalid/pagina.html"

PAGINA = """<!doctype html><html><head><meta charset="utf-8"></head>
<body><p class="texto">Hefesto</p><script>
addEventListener('load', () => {
  const f = new FontFace('Lenta', 'url(lenta.ttf)');
  document.fonts.add(f);
  f.load().catch(() => {});
  document.fonts.ready.then(() => requestAnimationFrame(() => requestAnimationFrame(() => {
    document.body.dataset.pintou = 'sim';
  })));
});
</script></body></html>"""


@pytest.fixture(scope="module")
def navegador() -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    assert FONTE.exists(), f"a fonte da casa saiu de {FONTE}: a régua não tem o que servir"
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield nav
        finally:
            nav.close()


def _pagina(navegador: Any, *, fonte_chega: bool) -> tuple[Any, list[Any]]:
    presas: list[Any] = []

    def servir(rota: Any) -> None:
        url = rota.request.url
        if url == ENDERECO:
            rota.fulfill(status=200, content_type="text/html", body=PAGINA)
        elif url.endswith("/lenta.ttf") and fonte_chega:
            rota.fulfill(status=200, content_type="font/ttf", body=FONTE.read_bytes())
        elif url.endswith("/lenta.ttf"):
            presas.append(rota)
        else:
            rota.abort()

    pg = navegador.new_page()
    pg.route("**/*", servir)
    return pg, presas


def test_volta_com_a_fonte_carregada_e_o_quadro_do_motor_pintado(navegador: Any) -> None:
    pg, _ = _pagina(navegador, fonte_chega=True)
    try:
        abrir(pg, ENDERECO)
        lido = pg.evaluate("""() => ({fonte: document.fonts.check('12px Lenta'),
                                      pintou: document.body.dataset.pintou || ''})""")
    finally:
        pg.close()
    assert lido == {"fonte": True, "pintou": "sim"}, (
        f"o ajudante voltou antes da página desenhada: {lido}. A régua leria a "
        f"fonte de reserva ou o DOM de antes do quadro do motor.")


def test_a_fonte_que_nunca_chega_da_o_erro_com_o_nome_dentro_do_prazo(navegador: Any) -> None:
    pg, presas = _pagina(navegador, fonte_chega=False)
    try:
        inicio = time.monotonic()
        with pytest.raises(AssertionError, match=r"document\.fonts\.ready em 1500 ms"):
            abrir(pg, ENDERECO, prazo_ms=1500)
        gasto = time.monotonic() - inicio
    finally:
        pg.close()
    assert presas, "a rota não prendeu a fonte: a régua não mediu a espera da fonte"
    assert gasto < 10, f"o erro veio em {gasto:.1f} s, longe do prazo de 1,5 s"


def test_o_seletor_que_nunca_aparece_da_o_erro_com_o_nome_dentro_do_prazo(
        navegador: Any) -> None:
    pg, _ = _pagina(navegador, fonte_chega=True)
    try:
        inicio = time.monotonic()
        with pytest.raises(AssertionError, match=r"'\.nunca-existe' no DOM em 1500 ms"):
            abrir(pg, ENDERECO, seletor=".nunca-existe", prazo_ms=1500)
        gasto = time.monotonic() - inicio
    finally:
        pg.close()
    assert gasto < 10, f"o erro veio em {gasto:.1f} s, longe do prazo de 1,5 s"
