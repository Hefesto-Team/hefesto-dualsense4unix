"""O jargão banido não volta para a interface nova — e a régua lê a TELA.

ORDEM DELA, 05/09/2026, em duas partes e a segunda corrigindo a primeira:

    *"não é pra ter mesa em nada da interface"*
    *"muda o termo pra objeto e sinônimos nesses casos"*

A primeira leva separou dois sentidos e tirou só um — "mesa" = o conjunto de
controles ligados. Ficou o outro, "mesa" = a escrivaninha dela, por achar que
ali a palavra era a coisa. **Ela corrigiu:** a palavra sai da interface INTEIRA,
e nesses casos o termo passa a ser "objeto" ou o sinônimo que couber.

A RÉGUA COBRIA UMA PALAVRA E O PORTÃO COBRIA ONZE — 05/09/2026
---------------------------------------------------------------

Ela nasceu para "mesa" e ficou nela, enquanto
`scripts/validar-palavra-de-tela.py` guardava as outras dez — e guardava só o
`.glade` e o `app/`, que são a janela VELHA. O resultado, medido: as **40 mil
palavras de tela** das dez abas novas tinham **uma** palavra vigiada, e a
janela que vai morrer tinha onze.

Ela é dela, a queixa que fecha este buraco:

    *"termos scripts no repo atual que ou apontam pro gtk ou só funcionam lá
    (…) o certo é ajustar ele pra comportar todas as features do html"*

Então a lista tem **um dono só**: `JARGAO_BANIDO`, no portão. Esta régua a
importa e aplica ao DOM da interface nova; o portão a aplica ao `.glade` e ao
`app/`. Uma palavra entra na lista uma vez e as duas telas passam a ser
vigiadas — que é o oposto do que acontecia, com a lista crescendo só de um
lado. **Medido ao ligar: zero ocorrências dos onze termos nas dez páginas.**

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

E a leitura por AST dos `interface/pacotes/*.py` foi MEDIDA e descartada no
mesmo dia: os pacotes montam o texto em f-string e em HTML, não em literal que
chega a um escoadouro. O escoadouro de dicionário mais usado deles é `gesto`,
com 39 literais — nome de máquina, não frase. Não há o que ler no fonte.

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

import importlib.util
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
PORTAO_DA_PALAVRA = RAIZ / "scripts" / "validar-palavra-de-tela.py"

#: A LISTA TEM UM DONO SÓ, e ele é o portão — importado por caminho de arquivo
#: porque `scripts/` não é pacote. Digitar a lista aqui de novo faria o que esta
#: casa já pagou onze vezes: duas cópias que divergem no primeiro termo novo.
def _jargao_banido() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("_portao_palavra", PORTAO_DA_PALAVRA)
    assert spec and spec.loader, PORTAO_DA_PALAVRA
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_palavra"] = mod
    spec.loader.exec_module(mod)
    banidos = dict(mod.JARGAO_BANIDO)
    # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE — se a lista mudar de nome ou de
    # molde, esta linha reprova em vez de a suíte publicar verde sobre nada.
    assert len(banidos) >= 11, f"o portão declarou {len(banidos)} termos — o molde mudou?"
    return banidos


#: `\b` não serve para termo acentuado: em `re` do Python `\b` casa entre `m` e
#: `é`, então "não há" casaria dentro de "não hávamos". As bordas são escritas à
#: mão sobre a classe de letra com acento.
def _regua_do_termo(termo: str) -> re.Pattern[str]:
    return re.compile(
        r"(?<![\wÀ-ÿ])" + re.escape(termo) + r"s?(?![\wÀ-ÿ])", re.IGNORECASE
    )

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
        # `headless` é o padrão, e é OBRIGATÓRIO: ela tem UMA tela, e uma janela
        # que nasce na frente dela quebra o que ela está fazendo.
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
