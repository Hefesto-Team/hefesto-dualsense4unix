"""Todo acionável das páginas recebe o foco do teclado e se anuncia ao leitor de tela.

Sprint TODO-BOTAO-DAS-ABAS-RECEBE-FOCO-E-SE-ANUNCIA-01.

Medido em 25/11/2026 no Chrome, nas páginas publicadas com o ``base-comum.js`` de antes, por
``data-gesto``/``data-hef-gesto`` visível e fora de ``template``: o foco (``tabindex``) já era do
``base-comum.js`` (zero faltas), mas 103 acionáveis (os seis modos da Jogar, 65 da Conexões, as
chaves e os chips da Experimental, as linhas de ordenar dos Perfis) não tinham ``role``; 86 não
tinham nome (as 30 cores da Iluminação, os «⋮», o ordenar, a velocidade da Navegação); e nenhum
estado (``aria-pressed``, ``aria-checked``) acompanhava a classe ``on``/``ligado``.

A cura mora num dono só, o ``base-comum.js``, que vale para as dez abas e as janelas: ``role`` ao
que não é nativo (``button``, ``switch``, ``radio``/``checkbox`` no rótulo de um rádio), nome pela
dica ou pelo rótulo do lugar, estado acompanhando a classe, e região viva no que a tela já diz em
texto (``.ressalva``). Nenhum texto, botão ou desenho novo na tela.

A régua abre cada página publicada com o ``base-comum.js`` da árvore no lugar do embutido (a
publicação é de quem costura) e mede o DOM depois dele.

MORDIDA: com o ``base-comum.js`` anterior à sprint, ``test_nenhuma_pagina_tem_acionavel_sem_papel``,
``..._sem_nome`` e ``test_o_estado_acompanha_a_classe`` reprovam.

DECISÃO D-2611-O-LEITOR-DE-TELA-NAO-NARRA-O-GESTO-QUE-DEU-CERTO (a validar): só o texto que
a tela já diz (a ressalva) vira região viva; o gesto que deu certo não é narrado.
"""
from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
PAGINAS = sorted((INTERFACE / "paginas").glob("*.html"))  # (noqa-acento)
BASE_JS = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
CHROME = pathlib.Path("/usr/bin/google-chrome")

_BASE = re.compile(r'(<script id="base-comum">)(.*?)(</script>)', re.S)

MEDIR = r"""() => {
  const NATIVO = 'a[href],button,input:not([type=hidden]),select,textarea,summary';
  const DONO = ['TR', 'LI', 'OUTPUT'];
  const texto = e => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const falhas = {sem_parada: [], sem_papel: [], sem_nome: []};
  let vistos = 0;
  for (const el of document.querySelectorAll('[data-gesto],[data-hef-gesto]')) {
    if (el.closest('template') || el.tagName === 'TEMPLATE' || el.closest('[hidden]')) continue;
    vistos += 1;
    const nome = el.tagName.toLowerCase() + '.' + (el.getAttribute('class') || '').split(' ')[0]
      + '[' + (el.getAttribute('data-gesto') || el.getAttribute('data-hef-gesto')) + ']';
    const nativo = el.matches(NATIVO);
    const dentro = [...el.querySelectorAll(NATIVO)].some(d => !d.disabled);
    if (!nativo && !dentro && el.getAttribute('tabindex') === null) falhas.sem_parada.push(nome);
    const rotulo = el.tagName === 'LABEL'
      && (el.hasAttribute('for') || el.querySelector('input,select,textarea'));
    const alvo = el.tagName === 'LABEL' && el.hasAttribute('for')
      ? document.getElementById(el.getAttribute('for')) : null;
    const deRadio = alvo && (alvo.type === 'radio' || alvo.type === 'checkbox');
    if (!nativo && !el.hasAttribute('role') && !DONO.includes(el.tagName) && (!rotulo || deRadio))
      falhas.sem_papel.push(nome);
    const comNome = el.hasAttribute('aria-label') || el.hasAttribute('aria-labelledby')
      || el.hasAttribute('title') || el.getAttribute('placeholder') || texto(el)
      || (el.labels && el.labels.length);
    if (!comNome) falhas.sem_nome.push(nome);
  }
  return {vistos, falhas};
}"""


@pytest.fixture(scope="module")
def navegador(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    pasta = tmp_path_factory.mktemp("acionaveis")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield nav, pasta
        finally:
            nav.close()


def _com_a_base_da_arvore(html: str) -> str:
    achou = _BASE.search(html)
    assert achou, "a página não traz o `base-comum`"
    return html[:achou.start(2)] + BASE_JS + html[achou.end(2):]


def _abrir(navegador: Any, nome: str, html: str) -> Any:
    nav, pasta = navegador
    arq = pasta / nome
    arq.write_text(html, encoding="utf-8")
    pg = nav.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(arq.as_uri())
    pg.wait_for_timeout(300)
    return pg


def _medida(navegador: Any, pagina: pathlib.Path) -> dict[str, Any]:
    html = _com_a_base_da_arvore(pagina.read_text(encoding="utf-8"))
    pg = _abrir(navegador, pagina.name, html)
    try:
        return dict(pg.evaluate(MEDIR))
    finally:
        pg.close()


@pytest.fixture(scope="module")
def medidas(navegador: Any) -> dict[str, dict[str, Any]]:
    assert len(PAGINAS) >= 10, f"achei {len(PAGINAS)} páginas publicadas: o caminho mudou?"
    return {p.name: _medida(navegador, p) for p in PAGINAS}


def test_a_regua_viu_os_acionaveis(medidas: dict[str, dict[str, Any]]) -> None:
    """Uma régua que mede zero acionável passa sobre tudo: as abas têm dezenas cada."""
    for aba in ("01-jogar.html", "07-lancadores.html", "08-conexoes.html", "10-perfis.html"):
        assert medidas[aba]["vistos"] >= 20, f"{aba}: a régua viu {medidas[aba]['vistos']}"


@pytest.mark.parametrize("falha", ["sem_parada", "sem_papel", "sem_nome"])
def test_nenhuma_pagina_tem_acionavel(medidas: dict[str, dict[str, Any]], falha: str) -> None:
    """D-2611-O-LEITOR-DE-TELA-NAO-NARRA-O-GESTO-QUE-DEU-CERTO: sem parada de foco, sem papel
    ou sem nome, zero, em toda página publicada."""
    ruins = {n: m["falhas"][falha] for n, m in medidas.items() if m["falhas"][falha]}
    assert not ruins, f"acionáveis {falha.replace('_', ' ')}: {ruins}"


def test_os_modos_da_jogar_sao_botoes_com_estado(navegador: Any) -> None:
    """Os modos do controle (``span.degrau``) saem como botão com ``aria-pressed`` igual à
    classe ``on``; o Tab chega no modo Xbox e o Enter aciona o gesto dele."""
    pagina = next(p for p in PAGINAS if p.name == "01-jogar.html")
    html = _com_a_base_da_arvore(pagina.read_text(encoding="utf-8"))
    pg = _abrir(navegador, "01-modos.html", html)
    try:
        degraus = pg.evaluate("""() => [...document.querySelectorAll('.degrau[data-gesto]')].map(
            e => [e.getAttribute('data-gesto'), e.getAttribute('role'),
                  e.getAttribute('aria-pressed'), e.classList.contains('on'),
                  e.getAttribute('tabindex')])""")
        assert len(degraus) >= 6
        for gesto, papel, pressionado, aceso, parada in degraus:
            assert papel == "button", f"{gesto}: role {papel}"
            assert pressionado == str(aceso).lower(), f"{gesto}: {pressionado} com on={aceso}"
            assert parada == "0", f"{gesto}: tabindex {parada}"
        pg.evaluate("""() => { window.__cliques = [];
            document.addEventListener('click', e => {
              const g = e.target.closest('[data-gesto]');
              if (g) window.__cliques.push(g.getAttribute('data-gesto')); }, true);
            document.querySelector('[data-gesto=modo-xbox]').focus(); }""")
        pg.keyboard.press("Enter")
        assert "modo-xbox" in pg.evaluate("() => window.__cliques")
    finally:
        pg.close()


_PAGINA_VIVA = (
    '<!doctype html><meta charset="utf-8"><body>'
    '<div id="caixa"><span class="degrau on" data-gesto="g1">Um</span>'
    '<span class="degrau" data-gesto="g2" data-dica="Dois"></span>'
    '<div class="ressalva" data-campo="r"></div></div>'
    f"<script>{BASE_JS}</script></body>"
)


def test_o_estado_acompanha_a_classe_e_o_que_nasce_depois(navegador: Any) -> None:
    """O que o produto repinta depois da carga ganha papel, nome e estado; o estado segue a
    classe; a dica que muda leva o nome junto."""
    pg = _abrir(navegador, "viva.html", _PAGINA_VIVA)
    try:
        pg.evaluate("""() => { document.querySelector('[data-gesto=g1]').classList.remove('on');
            document.querySelector('[data-gesto=g2]').classList.add('on');
            document.querySelector('[data-gesto=g2]').setAttribute('data-dica', 'Dois de novo');
            document.getElementById('caixa').insertAdjacentHTML('beforeend',
              '<span class="nj-tog ligado" data-gesto="g3"><span class="txt">Ligado</span></span>');
            }""")
        pg.wait_for_timeout(100)
        lido = pg.evaluate("""() => { const q = s => document.querySelector(s);
            return {g1: q('[data-gesto=g1]').getAttribute('aria-pressed'),
                    g2: q('[data-gesto=g2]').getAttribute('aria-pressed'),
                    nome2: q('[data-gesto=g2]').getAttribute('aria-label'),
                    g3: ['role', 'aria-checked', 'tabindex'].map(
                      a => q('[data-gesto=g3]').getAttribute(a)),
                    viva: q('.ressalva').getAttribute('role')}; }""")
        assert lido == {"g1": "false", "g2": "true", "nome2": "Dois de novo",
                        "g3": ["switch", "true", "0"], "viva": "status"}, lido
        pg.evaluate("() => document.querySelector('[data-gesto=g3]').classList.remove('ligado')")
        pg.wait_for_timeout(100)
        ligado = pg.evaluate(
            "() => document.querySelector('[data-gesto=g3]').getAttribute('aria-checked')")
        assert ligado == "false"
    finally:
        pg.close()
