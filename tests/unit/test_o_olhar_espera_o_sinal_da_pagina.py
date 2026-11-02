#!/usr/bin/env python3
"""O RETRATISTA FOTOGRAFA A PÁGINA PELO SINAL DA PÁGINA, e não pela rede quieta nem pelo relógio.

A página que demora a desenhar sai na foto igual à que nasce desenhada, byte a byte; a cor do
tema que transita sai na cor de chegada; o pulso que não acaba sai no estado de base; a página
que nunca fica pronta sai com o erro que nomeia o sinal que faltou, sem foto. As páginas são
arquivos locais, e a fonte que nunca chega é presa pela rota do próprio Playwright, sem rede.
"""
from __future__ import annotations

import pathlib
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import olhar

CHROME = pathlib.Path("/usr/bin/google-chrome")

ESTILO = """<style>
:root{--fundo:#1f6feb}
body{margin:0;background:#fff}
.janela{width:240px;height:120px;background-color:var(--fundo);color:#fff;font:16px sans-serif}
</style>"""

PRONTA = f"""<!doctype html><html><head><meta charset="utf-8">{ESTILO}</head>
<body><div class="janela">Hefesto</div></body></html>"""

ATRASADA = f"""<!doctype html><html><head><meta charset="utf-8">{ESTILO}<script>
addEventListener('load', () => setTimeout(() => {{
  const d = document.createElement('div');
  d.className = 'janela';
  d.textContent = 'Hefesto';
  document.body.append(d);
}}, 2500));
</script></head><body></body></html>"""

TRANSITA = PRONTA.replace("</style>", ".janela{transition:background-color 1500ms linear}</style>")

TEMA_VERMELHO = ":root{--fundo:#d73a49}"

PULSA = PRONTA.replace(
    "</style>",
    "@keyframes pulso{50%{background-color:#d73a49}}"
    ".janela{animation:pulso 1200ms linear infinite}</style>")

SEM_CAIXA = f"""<!doctype html><html><head><meta charset="utf-8">{ESTILO}</head>
<body><p>Hefesto</p></body></html>"""

FONTE_PRESA = PRONTA.replace("</style>", """.janela{font-family:Lenta}</style><script>
addEventListener('load', () => {
  const f = new FontFace('Lenta', 'url(http://pagina.invalid/lenta.ttf)');
  document.fonts.add(f);
  f.load().catch(() => {});
});
</script>""")


class _ComRota:
    """O navegador do retratista, com a rota que prende a fonte da página."""

    def __init__(self, nav: Any) -> None:
        self.nav = nav
        self.presas: list[Any] = []

    def new_page(self, **opcoes: Any) -> Any:
        pg = self.nav.new_page(**opcoes)
        pg.route("http://pagina.invalid/**", self._prender)
        return pg

    def _prender(self, rota: Any) -> None:
        self.presas.append(rota)


@pytest.fixture(scope="module")
def navegador() -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = olhar._navegador(pw)
        try:
            yield nav
        finally:
            nav.close()


def _pagina(pasta: pathlib.Path, nome: str, html: str) -> pathlib.Path:
    alvo = pasta / f"{nome}.html"
    alvo.write_text(html, encoding="utf-8")
    return alvo


def _retrato(navegador: Any, pasta: pathlib.Path, nome: str, html: str,
             **opcoes: Any) -> dict[str, Any]:
    return olhar._retratar(navegador, _pagina(pasta, nome, html), pasta / f"{nome}.png",
                           so_a_janela=True, **opcoes)


def test_a_pagina_que_demora_a_desenhar_sai_igual_a_que_nasce_desenhada(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    atrasada = _retrato(navegador, tmp_path, "atrasada", ATRASADA)
    pronta = _retrato(navegador, tmp_path, "pronta", PRONTA)
    assert "erro" not in atrasada and "erro" not in pronta, (
        f"o retratista mediu a página antes da caixa existir: {atrasada} {pronta}")
    assert (atrasada["larg"], atrasada["alt"]) == (240, 120), atrasada
    assert (tmp_path / "atrasada.png").read_bytes() == (tmp_path / "pronta.png").read_bytes(), (
        "a foto da página que desenha a caixa depois do load difere da foto da página que nasce "
        "com a caixa: o retratista fotografou antes do sinal da página")


def test_a_cor_do_tema_que_transita_sai_na_cor_de_chegada(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    transita = _retrato(navegador, tmp_path, "transita", TRANSITA, tema=TEMA_VERMELHO)
    pronta = _retrato(navegador, tmp_path, "pronta", PRONTA, tema=TEMA_VERMELHO)
    assert "erro" not in transita and "erro" not in pronta, (transita, pronta)
    assert (tmp_path / "transita.png").read_bytes() == (tmp_path / "pronta.png").read_bytes(), (
        "a foto com o tema saiu no meio da transição da cor: o retratista não esperou a "
        "transição da página acabar")


def test_a_animacao_que_nao_acaba_sai_no_estado_de_base(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    pulsa = _retrato(navegador, tmp_path, "pulsa", PULSA)
    pronta = _retrato(navegador, tmp_path, "pronta", PRONTA)
    assert "erro" not in pulsa and "erro" not in pronta, (pulsa, pronta)
    assert (tmp_path / "pulsa.png").read_bytes() == (tmp_path / "pronta.png").read_bytes(), (
        "a foto da página com um pulso infinito saiu numa fase qualquer dele: a foto depende "
        "do instante em que foi tirada")


def test_a_pagina_sem_caixa_da_o_erro_com_o_sinal_dentro_do_prazo_e_sem_foto(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    inicio = time.monotonic()
    r = _retrato(navegador, tmp_path, "sem-caixa", SEM_CAIXA, prazo_ms=1500)
    gasto = time.monotonic() - inicio
    assert set(r) == {"erro"}, r
    assert r["erro"].startswith("a página não ficou pronta: "), r["erro"]
    assert f"o seletor {olhar.A_CAIXA!r} no DOM em 1500 ms" in r["erro"], r["erro"]
    assert not (tmp_path / "sem-caixa.png").exists(), "saiu foto de uma página que não ficou pronta"
    assert gasto < 10, f"o erro veio em {gasto:.1f} s, longe do prazo de 1,5 s"


def test_a_fonte_que_nunca_chega_da_o_erro_com_o_sinal_dentro_do_prazo_e_sem_foto(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    com_rota = _ComRota(navegador)
    inicio = time.monotonic()
    r = _retrato(com_rota, tmp_path, "fonte-presa", FONTE_PRESA, prazo_ms=1500)
    gasto = time.monotonic() - inicio
    assert com_rota.presas, "a rota não prendeu a fonte: a régua não mediu a espera da fonte"
    assert set(r) == {"erro"}, r
    assert "a página não ficou pronta: faltou o document.fonts.ready em 1500 ms" in r["erro"], (
        r["erro"])
    assert not (tmp_path / "fonte-presa.png").exists(), "saiu foto com a fonte de reserva"
    assert gasto < 10, f"o erro veio em {gasto:.1f} s, longe do prazo de 1,5 s"
