"""O jargão banido não volta para a interface nova — e a régua lê a TELA."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
PORTAO_DA_PALAVRA = RAIZ / "scripts" / "validar-palavra-de-tela.py"

def _jargao_banido() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("_portao_palavra", PORTAO_DA_PALAVRA)
    assert spec and spec.loader, PORTAO_DA_PALAVRA
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_palavra"] = mod
    spec.loader.exec_module(mod)
    banidos = dict(mod.JARGAO_BANIDO)
    assert len(banidos) >= 11, f"o portão declarou {len(banidos)} termos — o molde mudou?"
    return banidos


def _regua_do_termo(termo: str) -> re.Pattern[str]:
    return re.compile(
        r"(?<![\wÀ-ÿ])" + re.escape(termo) + r"s?(?![\wÀ-ÿ])", re.IGNORECASE
    )

COLHER = """() => {
  const fora = [];
  const anda = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = anda.nextNode())) {
    const p = n.parentElement;
    if (!p || p.closest('script,style,template,div.nota')) continue;
    const t = n.textContent.trim();
    if (t) fora.push(['texto', t]);
  }
  for (const at of ['title', 'aria-label', 'placeholder', 'alt']) {
    document.querySelectorAll('[' + at + ']').forEach(el => {
      if (el.closest('div.nota')) return;
      const v = (el.getAttribute(at) || '').trim();
      if (v) fora.push([at, v]);
    });
  }
  return fora;
}"""

CLIQUES: dict[str, tuple[str, ...]] = {
    "mapa-das-portas.html": (
        '[data-modo="ideal"]',
        '[data-modo="mao"]',
        '[data-modo="mesa"]',
        "#reexaminar",
        "#ver-antes",
    ),
}


def _paginas() -> list[Path]:
    achadas = sorted(p for p in PAGINAS.glob("*.html") if not p.name.endswith(".dc.html"))
    assert len(achadas) >= 10, f"achei {len(achadas)} páginas em {PAGINAS} — o caminho mudou?"
    return achadas


def _achados_da_pagina(pagina: Path, aba, reguas: dict[str, re.Pattern[str]]) -> list[str]:
    aba.goto(pagina.as_uri())
    aba.wait_for_timeout(250)

    vistos: list[str] = []

    def colher() -> None:
        for onde, texto in aba.evaluate(COLHER):
            for termo, regua in reguas.items():
                if regua.search(texto):
                    limpo = " ".join(texto.split())
                    vistos.append(f"{pagina.name} [{onde}] «{termo}» {limpo[:140]}")

    colher()
    for seletor in CLIQUES.get(pagina.name, ()):
        alvo = aba.query_selector(seletor)
        if alvo is None:
            continue
        alvo.click()
        aba.wait_for_timeout(200)
        colher()
    return vistos


def test_nenhuma_pagina_publicada_diz_o_jargao_banido() -> None:
    """Zero ocorrências dos onze termos, nas páginas que o produto abre."""
    playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright não está nesta máquina"
    )
    chrome = Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("o Chrome do sistema não está nesta máquina")

    banidos = _jargao_banido()
    reguas = {termo: _regua_do_termo(termo) for termo in banidos}
    achados: list[str] = []
    with playwright.sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=str(chrome))
        aba = navegador.new_page()
        try:
            for pagina in _paginas():
                achados.extend(_achados_da_pagina(pagina, aba, reguas))
        finally:
            navegador.close()

    assert not achados, (
        "jargão banido na interface nova. A lista e o substituto de cada termo "
        "estão em `JARGAO_BANIDO`, em scripts/validar-palavra-de-tela.py:\n  "
        + "\n  ".join(f"{a}  -> {banidos[a.split('«')[1].split('»')[0]]}" for a in achados)
    )
