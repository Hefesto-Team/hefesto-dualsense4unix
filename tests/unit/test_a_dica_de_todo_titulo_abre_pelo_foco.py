"""A dica de todo título abre pelo foco, não só pelo mouse.

Sprint A-DICA-DE-TODO-TITULO-ABRE-PELO-FOCO-01.

A dica mora no `data-dica` do próprio título, rótulo ou frase (regra A1 do desenho do todo: nenhum
«?»). Um `h4` não recebe foco: sem `tabindex`, o Tab, o teclado e o controle nunca disparavam o
`focusin` que abre a dica. A base comum agora dá a parada a todo `[data-dica]` que não é focável
por natureza, sem trocar o papel dele.

O que a régua mede, no Chrome, sobre os DESENHOS (`mockup/`) com a base de HOJE posta por cima da
que cada página embute (a cura mora em `base-comum.js`, e a costura é quem regera as outras abas):

1. todo `[data-dica]` visível que não é botão, campo ou link, nem tem um campo dentro, ganha
   `tabindex="0"` e continua com o papel que tinha;
2. o Tab até ele abre a dica (`#hef-dica.visivel`, com o texto dele), a bolha entra no
   `aria-describedby` enquanto aberta, e o Tab seguinte a fecha e tira a descrição;
3. o elemento criado depois (o título do Sugestões, o cartão de dica de um controle que entra) e o
   `data-dica` posto depois num elemento que já existia ganham a parada também.

MORDIDAS (cada uma tira UMA cura da base e a régua tem de reprovar): sem o `[data-dica]` na lista
do `tabindex`; sem o `aria-describedby`; sem o olhar do atributo.
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
MOCKUP = RAIZ / "mockup"
for _caminho in (str(RAIZ / "src"), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede  # o ponto comum dos portões de página, sem a rede

CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURA, ALTURA = 1212, 809

JS_DA_BASE = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
CSS_DA_BASE = (INTERFACE / "base-comum.css").read_text(encoding="utf-8")

#: As dez abas, a calibração e os dois mapas das portas e do controle.
PAGINAS = sorted(
    p.name for p in MOCKUP.glob("*.html")
    if re.match(r"(0\d|10)-", p.name) or p.name in (
        "calibrar-sensores.html", "mapa-das-portas.html", "mapa-do-controle.html",
        "mapa-do-radio.html"))


def _com_a_base(texto: str, js: str = JS_DA_BASE) -> str:
    """A página com a base dada no lugar da que ela embute (uma `<script id="base-comum">`)."""
    texto, n = re.subn(
        r'(<script id="base-comum">\n).*?(</script>)',
        lambda m: m.group(1) + js + m.group(2), texto, count=1, flags=re.S)
    assert n == 1, "a página não embute a base comum"
    texto, n = re.subn(
        r'(<style id="base-comum">\n).*?(</style>)',
        lambda m: m.group(1) + CSS_DA_BASE + m.group(2), texto, count=1, flags=re.S)
    assert n == 1, "a página não embute a folha da base comum"
    return texto


@pytest.fixture(scope="module")
def navegador() -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield nav
        finally:
            nav.close()


def _abrir(navegador: Any, tmp_path: pathlib.Path, pagina: str, js: str = JS_DA_BASE) -> Any:
    copia = tmp_path / pagina
    copia.write_text(_com_a_base((MOCKUP / pagina).read_text(encoding="utf-8"), js),
                     encoding="utf-8")
    pg, _ = chrome_sem_rede.abrir_sem_rede(
        navegador, copia.as_uri(), largura=LARGURA, altura=ALTURA)
    return pg


_JS_SEM_PARADA = """() => {
  const NATIVO = 'a[href],button,input:not([type=hidden]),select,textarea,summary,'
    + '[contenteditable=""],[contenteditable="true"]';
  const visivel = el => el.getClientRects().length > 0
    && getComputedStyle(el).visibility !== 'hidden';
  const tem = [], sem = [];
  for (const el of document.querySelectorAll('[data-dica]')) {
    if (el.matches('option,optgroup') || el.matches(NATIVO) || !visivel(el)) continue;
    if (Array.from(el.querySelectorAll(NATIVO)).some(d => !d.disabled && visivel(d))) continue;
    const nome = el.tagName + '.' + (typeof el.className === 'string' ? el.className : '')
      + '[' + el.dataset.dica.slice(0, 24) + ']';
    (el.tabIndex >= 0 ? tem : sem).push(nome);
  }
  return {tem: tem.length, sem};
}"""


def test_todo_data_dica_que_nao_e_focavel_ganha_parada(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    sem_parada: list[str] = []
    com_parada = 0
    for pagina in PAGINAS:
        pg = _abrir(navegador, tmp_path, pagina)
        try:
            m = pg.evaluate(_JS_SEM_PARADA)
        finally:
            pg.close()
        com_parada += m["tem"]
        sem_parada += [f"{pagina}: {n}" for n in m["sem"]]
    assert com_parada > 100, f"a régua mediu pouco ({com_parada}): vacuidade não é verde"
    assert not sem_parada, (
        "título/rótulo com dica e sem parada no Tab:\n" + "\n".join(sem_parada[:12]))


_JS_DO_ALVO = """() => {
  const NATIVO = 'a[href],button,input:not([type=hidden]),select,textarea,summary';
  const el = Array.from(document.querySelectorAll(SEL)).find(e =>
    !e.matches(NATIVO) && !e.closest('.tela-nova') && e.dataset.dica
    && e.getBoundingClientRect().width > 0 && e.tabIndex >= 0);
  if (!el) return null;
  el.id = el.id || 'alvo-da-regua';
  return {id: el.id, tag: el.tagName, dica: el.dataset.dica, papel: el.getAttribute('role')};
}"""

_JS_DO_ESTADO = """(id) => {
  const el = document.getElementById(id), d = document.getElementById('hef-dica');
  return {
    foco: document.activeElement === el,
    aberta: !!d && d.classList.contains('visivel'),
    texto: d ? d.textContent : '',
    descrito: (el.getAttribute('aria-describedby') || '').split(/\\s+/).includes('hef-dica'),
    contorno: getComputedStyle(el).outlineStyle === 'solid',
  };
}"""


def _tab_ate(pg: Any, id_: str, limite: int = 120) -> bool:
    for _ in range(limite):
        pg.keyboard.press("Tab")
        if pg.evaluate("(id) => document.activeElement && document.activeElement.id === id", id_):
            return True
    return False


@pytest.mark.parametrize("pagina,seletor", [  # (noqa-acento) nome do parâmetro
    ("mapa-das-portas.html", "h3[data-dica],h4[data-dica],span[data-dica]"),
    ("08-conexoes.html", "h4[data-dica]"),
    ("01-jogar.html", "[data-dica]"),
])
def test_o_tab_abre_a_dica_do_titulo_e_o_seguinte_fecha(
        navegador: Any, tmp_path: pathlib.Path, pagina: str, seletor: str) -> None:
    _prova_do_tab(navegador, tmp_path, pagina, seletor)


def _prova_do_tab(
        navegador: Any, tmp_path: pathlib.Path, pagina: str, seletor: str,
        js: str = JS_DA_BASE) -> None:
    pg = _abrir(navegador, tmp_path, pagina, js)
    try:
        alvo = pg.evaluate(_JS_DO_ALVO.replace("SEL", repr(seletor)))
        assert alvo, f"{pagina}: nenhum elemento com dica e parada para a régua"
        assert alvo["papel"] is None, f"a base trocou o papel de {alvo['tag']}: {alvo['papel']}"
        assert _tab_ate(pg, alvo["id"]), f"{pagina}: o Tab nunca chegou a {alvo['tag']}"
        aberto = pg.evaluate(_JS_DO_ESTADO, alvo["id"])
        assert aberto["foco"] and aberto["aberta"], f"{pagina}: o foco não abriu a dica: {aberto}"
        assert aberto["texto"] == alvo["dica"], aberto
        assert aberto["descrito"], f"{pagina}: a bolha não entrou no aria-describedby: {aberto}"
        assert aberto["contorno"], f"{pagina}: o foco não aparece sobre o elemento: {aberto}"
        pg.keyboard.press("Tab")
        depois = pg.evaluate(_JS_DO_ESTADO, alvo["id"])
        assert not depois["foco"] and not depois["descrito"], (
            f"{pagina}: o Tab seguinte não largou a dica: {depois}")
        assert not (depois["aberta"] and depois["texto"] == alvo["dica"]), (
            f"{pagina}: a dica ficou aberta depois de o foco sair: {depois}")
    finally:
        pg.close()


_JS_CRIA_DEPOIS = """() => {
  const sec = document.createElement('section');
  sec.innerHTML = '<h4 id="criado-depois" data-dica="Ele usa só 20 dos 79 canais.">'
    + 'Meio sufocado</h4>'
    + '<span id="ganha-dica-depois">Rótulo</span>';
  document.body.append(sec);
  return new Promise(r => setTimeout(() => {
    document.getElementById('ganha-dica-depois').setAttribute('data-dica', 'A dica chegou depois.');
    setTimeout(() => r({
      criado: document.getElementById('criado-depois').tabIndex,
      atributo: document.getElementById('ganha-dica-depois').tabIndex,
      papel: document.getElementById('criado-depois').getAttribute('role'),
    }), 60);
  }, 60));
}"""


def test_o_elemento_criado_depois_e_o_dica_posto_depois_ganham_parada(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    _prova_do_criado_depois(navegador, tmp_path)


def _prova_do_criado_depois(
        navegador: Any, tmp_path: pathlib.Path, js: str = JS_DA_BASE) -> None:
    pg = _abrir(navegador, tmp_path, "mapa-das-portas.html", js)
    try:
        m = pg.evaluate(_JS_CRIA_DEPOIS)
        assert m["criado"] == 0, f"o título criado depois não ganhou parada: {m}"
        assert m["atributo"] == 0, f"o data-dica posto depois não ganhou parada: {m}"
        assert m["papel"] is None, m
        assert _tab_ate(pg, "criado-depois"), "o Tab não chegou ao título criado depois"
        estado = pg.evaluate(_JS_DO_ESTADO, "criado-depois")
        assert estado["aberta"] and estado["texto"] == "Ele usa só 20 dos 79 canais.", estado
    finally:
        pg.close()


def test_quem_tem_campo_dentro_nao_ganha_parada_dobrada(
        navegador: Any, tmp_path: pathlib.Path) -> None:
    """O rótulo que embrulha um campo já tem o foco do campo: nenhuma parada a mais."""
    pg = _abrir(navegador, tmp_path, "mapa-das-portas.html")
    try:
        m = pg.evaluate("""() => {
          const l = document.createElement('label');
          l.id = 'rotulo'; l.dataset.dica = 'Rótulo com campo';
          l.innerHTML = '<input id="campo" type="checkbox"> campo';
          document.body.append(l);
          return new Promise(r => setTimeout(() => r(l.hasAttribute('tabindex')), 60));
        }""")
        assert m is False
    finally:
        pg.close()


# ---- as mordidas: tirar UMA cura da base e ver a régua reprovar ------------------------------


def _reprova_sem(navegador: Any, tmp_path: pathlib.Path, cura: str, trocado: str) -> list[str]:
    """As duas provas sobre a base SEM a cura; devolve o que cada uma disse ao reprovar."""
    assert JS_DA_BASE.count(cura) == 1, cura
    js = JS_DA_BASE.replace(cura, trocado)
    erros: list[str] = []
    try:
        _prova_do_tab(navegador, tmp_path, "08-conexoes.html", "h4[data-dica]", js)
    except AssertionError as e:
        erros.append(str(e))
    try:
        _prova_do_criado_depois(navegador, tmp_path, js)
    except AssertionError as e:
        erros.append(str(e))
    return erros


def test_morde_sem_o_data_dica_na_lista_da_parada(navegador: Any, tmp_path: pathlib.Path) -> None:
    erros = _reprova_sem(navegador, tmp_path, "GESTO + ',[data-dica]'", "GESTO")
    assert len(erros) == 2, f"a régua não reprovou sem o tabindex da dica: {erros}"


def test_morde_sem_o_aria_describedby(navegador: Any, tmp_path: pathlib.Path) -> None:
    erros = _reprova_sem(navegador, tmp_path, "    descrever(el, true);\n", "")
    assert any("aria-describedby" in e for e in erros), erros


def test_morde_sem_olhar_o_atributo_posto_depois(navegador: Any, tmp_path: pathlib.Path) -> None:
    erros = _reprova_sem(
        navegador, tmp_path, "if (m.type === 'attributes') marcar(m.target);\n      else ", "")
    assert any("data-dica posto depois" in e for e in erros), erros


# ---- o WebKit do produto: a camada da dica da casa abre no foco do título ----------------------

_JS_DO_FOCO_NO_WEBKIT = """(function(){
  const h = document.createElement('h4');
  h.id = 'titulo-do-webkit'; h.dataset.dica = 'Ele usa só 20 dos 79 canais.';
  h.textContent = 'Meio sufocado';
  h.style.cssText = 'position:fixed;top:60px;left:60px;z-index:9';
  document.body.append(h);
  setTimeout(() => {
    const parada = h.tabIndex, papel = h.getAttribute('role');
    h.focus();
    setTimeout(() => {
      const a = !!(window.__hefDica && window.__hefDica.aberta());
      const t = window.__hefDica ? window.__hefDica.texto() : '';
      h.blur();
      setTimeout(() => {
        window.__resultado = JSON.stringify({
          parada, papel, aberta: a, texto: t,
          fechou: !(window.__hefDica && window.__hefDica.aberta()),
        });
      }, 120);
    }, 120);
  }, 120);
  return 'iniciado';
})()"""


def _foco_no_webkit(tmp_path: pathlib.Path, js: str = JS_DA_BASE) -> dict[str, Any]:
    """Abre o desenho do mapa das portas no WebKit, com a camada da dica do produto, e foca
    um título."""
    import json
    import os

    if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HEFESTO_NA_TELA")
            or not os.environ.get("DISPLAY")):
        pytest.skip("sem o X de mentira: o WebKit abriria na tela dela ou não abriria")
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre o WebKit da camada da dica")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    copia = tmp_path / "mapa-das-portas.html"
    copia.write_text(_com_a_base((MOCKUP / "mapa-das-portas.html").read_text(encoding="utf-8"), js),
                     encoding="utf-8")
    saiu: list[str] = []
    janela = Gtk.Window()
    janela.set_default_size(1280, 860)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()
    janela.present()
    view.grab_focus()

    def leu(_v: Any, res: Any) -> None:
        try:
            saiu.append(view.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(json.dumps({"erro": str(e)}))
        Gtk.main_quit()

    def camada(_v: Any, res: Any) -> None:
        view.evaluate_javascript(_JS_DO_FOCO_NO_WEBKIT, -1, None, None, None, None)
        GLib.timeout_add(
            1200, lambda: (view.evaluate_javascript(
                "window.__resultado || '{\"erro\": \"sem resultado\"}'",
                -1, None, None, None, leu), False)[1])

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.DICA_DA_CASA, -1, None, None, None, camada)

    view.connect("load-changed", carregou)
    view.load_uri(copia.as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    assert saiu, "o WebKit não respondeu"
    return dict(json.loads(saiu[0]))


def test_no_webkit_do_produto_o_foco_no_titulo_abre_a_dica_da_casa(tmp_path: pathlib.Path) -> None:
    # D-1610-O-TITULO-COM-DICA-ENTRA-NO-TAB-E-ABRE-A-DICA-PELO-FOCO
    m = _foco_no_webkit(tmp_path)
    assert not m.get("erro"), m
    assert m["parada"] == 0 and m["papel"] is None, f"o título não ganhou a parada: {m}"
    assert m["aberta"] and m["texto"] == "Ele usa só 20 dos 79 canais.", (
        f"o foco não abriu a dica: {m}")
    assert m["fechou"], f"sair do foco não fechou a dica: {m}"


def test_morde_no_webkit_sem_a_parada_do_titulo(tmp_path: pathlib.Path) -> None:
    cura = "GESTO + ',[data-dica]'"
    assert JS_DA_BASE.count(cura) == 1
    m = _foco_no_webkit(tmp_path, JS_DA_BASE.replace(cura, "GESTO"))
    assert not m.get("erro"), m
    assert m["parada"] == -1 and not m["aberta"], f"sem a cura o título ainda abre a dica: {m}"
