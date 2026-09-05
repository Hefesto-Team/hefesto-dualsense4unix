"""A palavra "mesa" não volta para a tela — e a régua lê a TELA, não o fonte.

ORDEM DELA, 05/09/2026, em duas partes e a segunda corrigindo a primeira:

    *"não é pra ter mesa em nada da interface"*
    *"muda o termo pra objeto e sinônimos nesses casos"*

A primeira leva separou dois sentidos e tirou só um — "mesa" = o conjunto de
controles ligados. Ficou o outro, "mesa" = a escrivaninha dela, por achar que
ali a palavra era a coisa. **Ela corrigiu:** a palavra sai da interface INTEIRA,
e nesses casos o termo passa a ser "objeto" ou o sinônimo que couber.

POR QUE ESTA RÉGUA LÊ O HTML PUBLICADO, E NÃO O PYTHON
-------------------------------------------------------

Porque o texto de tela desta interface tem **três origens** e nenhuma régua de
fonte alcança as três de uma vez:

* o gerador da aba (`interface/abaNN.py`) escreve HTML;
* o produto GTK (`gui/`, `app/`) é lido pelo gerador, e a frase vem de lá;
* o `<script>` da própria página escreve texto no DOM em tempo de execução.

A terceira é a que custou: em 05/09/2026 uma varredura estática de
`mapa-das-portas.html` contou **zero** ocorrências visíveis, e a página tinha
**catorze** — todas dentro do `<script>`, invisíveis para quem lê a marcação.
Rodar a página e ler o DOM é o único lugar onde as três se encontram.

O QUE ELA NÃO CONTA, e as duas exclusões são medidas
-----------------------------------------------------

* **`div.nota`** — as notas de construção. O produto não as renderiza (só a
  bancada as mostra), e elas falam do trabalho, não com quem joga;
* **chave de máquina** — `data-modo="mesa"`, `.veredito-mesa`, `secao_mesa.py`,
  `monta.MESA`. São nome de código, não texto de tela. A régua nunca as vê
  porque olha texto e atributos de tela, jamais `class` ou `data-*`.

A MORDIDA, e ela foi medida em 05/09/2026: com as páginas de antes da cura,
esta régua acusa **22** ocorrências em quatro páginas. Com as de depois, zero.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

#: A palavra, e só ela: `\b` impede que "mesada" ou "sobremesa" reprovem.
A_PALAVRA = re.compile(r"\bmesa[s]?\b", re.IGNORECASE)

#: O JavaScript que colhe o que a pessoa LÊ: todo texto fora de
#: `script`/`style`/`template`/`div.nota`, mais os quatro atributos que viram
#: texto na tela (a dica do `title` é onde estavam nove das treze de 05/09).
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

#: Os cliques que fazem nascer texto que o estado inicial não mostra. Sem eles
#: a régua mede um INSTANTE: em `mapa-das-portas.html` as frases dos modos
#: "ideal" e "leitura antiga" só existem depois do clique, e eram SEIS das
#: catorze daquela página.
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
    # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE — se o caminho mudar, esta linha
    # reprova em vez de a suíte publicar um verde sobre nenhuma página.
    assert len(achadas) >= 10, f"achei {len(achadas)} páginas em {PAGINAS} — o caminho mudou?"
    return achadas


def _achados_da_pagina(pagina: Path, aba) -> list[str]:
    aba.goto(pagina.as_uri())
    aba.wait_for_timeout(250)

    vistos: list[str] = []

    def colher() -> None:
        for onde, texto in aba.evaluate(COLHER):
            if A_PALAVRA.search(texto):
                limpo = " ".join(texto.split())
                vistos.append(f"{pagina.name} [{onde}] {limpo[:140]}")

    colher()
    for seletor in CLIQUES.get(pagina.name, ()):
        alvo = aba.query_selector(seletor)
        if alvo is None:
            continue
        alvo.click()
        aba.wait_for_timeout(200)
        colher()
    return vistos


def test_nenhuma_pagina_publicada_diz_mesa() -> None:
    """Zero ocorrências visíveis da palavra, nas páginas que o produto abre."""
    playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright não está nesta máquina"
    )
    chrome = Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("o Chrome do sistema não está nesta máquina")

    achados: list[str] = []
    with playwright.sync_playwright() as p:
        # `headless` é o padrão, e é OBRIGATÓRIO: ela tem UMA tela, e uma janela
        # que nasce na frente dela quebra o que ela está fazendo.
        navegador = p.chromium.launch(executable_path=str(chrome))
        aba = navegador.new_page()
        try:
            for pagina in _paginas():
                achados.extend(_achados_da_pagina(pagina, aba))
        finally:
            navegador.close()

    assert not achados, (
        "a palavra que ela mandou tirar da tela em 05/09/2026 voltou — "
        "o termo é 'objeto' ou o sinônimo que couber na frase:\n  "
        + "\n  ".join(achados)
    )
