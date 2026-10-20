"""O piso de 24 px e de 12 px nas abas 02 e 09, em duas opções cada (20/10/2026).

Só desenho: as quatro variantes moram em `mockup/variantes/` e nunca entram na página publicada nem
no produto. O piso é dela (13/10/2026: alvo de 24 px e nenhuma letra abaixo de 12 px, sem rolagem
vertical nova). A régua mede o que o olho veria: todo elemento que age, todo título ou rótulo
que abre dica (o `?` de antes, que a OS-ALVOS mede como alvo), todo texto visível, em quatro
vistas e em todos os estados do acordeão da 02.

MORDIDAS (executadas aqui, sobre uma cópia do HTML, e cada uma reprova a régua que a guarda):

* tirar a folha da variante da 02 A -> `test_a_regua_do_piso_morde_a_folha_arrancada`;
* o Copiar da 09 A a 22 px -> `test_a_regua_do_piso_morde_o_alvo_pequeno`;
* a letra do registro da 09 A a 11 px -> `test_a_regua_do_piso_morde_a_letra_pequena`;
* a dica da 02 B de volta a 16 px, e a da 02 A -> `test_a_regua_do_piso_morde_a_dica_pequena`;
* a linha do Status da 09 B e a da 09 A sem os 24 px ->
  `test_a_regua_do_piso_morde_a_dica_pequena_da_09`;
* devolver o texto antigo da vaga, ou a máscara escondida nela ->
  `test_a_vaga_diz_so_player_n_desconectado`;
* uma altura que estoura a tela da 02 B -> `test_a_regua_do_piso_morde_a_rolagem_nova`;
* uma largura que estoura a tela da 09 A -> `test_a_regua_do_piso_morde_a_rolagem_lateral`;
* pôr a folha da variante no corpo -> `test_a_folha_da_variante_mora_na_cabeca`.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Browser

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup"
VARIANTES = MOCKUP / "variantes"
CHROME = pathlib.Path("/usr/bin/google-chrome")
# as três vistas da casa e a de 150 % (a janela de 1280x720, não zoom de CSS)
VISTAS = ((1212, 809), (1918, 840), (1212, 740), (1280, 720))
ESTADOS_02 = ("c-p1", "c-p2", "c-p3", "c-todos")

NOMES = (
    "02-alvos-A-o-piso-no-arranjo-de-hoje", "02-alvos-B-o-piso-com-o-arranjo-refeito",
    "09-alvos-A-o-piso-no-arranjo-de-hoje", "09-alvos-B-o-piso-com-o-arranjo-refeito",
)
PRINCIPAL = {"02": "02-controles", "09": "09-sistema"}
FOLHA = '<style id="variante-alvos">'


def _ler(nome: str) -> str:
    return (VARIANTES / f"{nome}.html").read_text(encoding="utf-8")


def _base(nome: str) -> str:
    return (MOCKUP / f"{PRINCIPAL[nome[:2]]}.html").read_text(encoding="utf-8")


def _folhas_do_corpo(doc: str) -> list[str]:
    corpo = doc[doc.index("</head>"):]
    return re.findall(r"<style\b[^>]*>.*?</style>", corpo, flags=re.S)


def _sem_a_folha(doc: str) -> str:
    return re.sub(r'<style id="variante-alvos">.*?</style>\n?', "", doc, count=1, flags=re.S)


_VAGA = re.compile(r'<label class="faixa" for="c-p([34])" title="Lugar vazio[^"]*">.*?</label>',
                   flags=re.S)


def _vagas(doc: str) -> list[str]:
    return [m.group(0) for m in _VAGA.finditer(doc)]


@pytest.fixture(scope="module")
def navegador() -> Iterator[Browser]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


_MEDIDA = r"""() => {
 const corta = (e, r) => { let p = e.parentElement, x0 = r.left, y0 = r.top, x1 = r.right, y1 = r.bottom;
  while (p && p !== document.documentElement) { const c = getComputedStyle(p);
   if (c.display === 'none' || c.visibility === 'hidden') return false;
   if (['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowX)
       || ['hidden', 'auto', 'scroll', 'clip'].includes(c.overflowY)) { const q = p.getBoundingClientRect();
    x0 = Math.max(x0, q.left); y0 = Math.max(y0, q.top); x1 = Math.min(x1, q.right); y1 = Math.min(y1, q.bottom);
    if (x1 - x0 < 1 || y1 - y0 < 1) return false; }
   p = p.parentElement; } return true; };
 const visivel = e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e);
  if (r.width === 0 || r.height === 0 || c.visibility === 'hidden' || c.display === 'none') return false;
  if (parseFloat(c.opacity) === 0) return false; return corta(e, r); };
 const ACAO = 'button,a[href],input:not([type=hidden]),select,textarea,summary,[role=button],[role=switch],'
  + '[role=checkbox],[role=radio],[role=tab],[data-gesto],label[for]';
 const alvos = [], dicas = [], vistos = new Set();
 document.querySelectorAll(ACAO + ',[tabindex]:not([tabindex="-1"])').forEach(e => {
  if (vistos.has(e)) return; vistos.add(e);
  if (e.matches('input.radio-mesa')) return;
  if (!visivel(e)) return;
  const r = e.getBoundingClientRect();
  if (r.width < 24 || r.height < 24) {
   const o = (e.tagName + '.' + e.className + ' ' + (e.innerText || '').trim().slice(0, 20)
              + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
   (e.matches(ACAO) ? alvos : dicas).push(o); } });
 const letras = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
 while ((n = w.nextNode())) { const t = n.textContent.trim(); if (!t) continue; const e = n.parentElement;
  if (!e || ['SCRIPT', 'STYLE', 'OPTION', 'OPTGROUP'].includes(e.tagName) || !visivel(e)) continue;
  let fs = parseFloat(getComputedStyle(e).fontSize); const svg = e.closest('svg');
  if (svg && e.getScreenCTM) { const m = e.getScreenCTM(); if (m) fs = fs * Math.abs(m.a); }
  if (Math.round(fs * 100) / 100 < 12) letras.push(e.tagName + '.' + e.className + ' ' + t.slice(0, 20) + ' ' + fs); }
 const d = document.documentElement;
 const rol = [...document.querySelectorAll('*')].filter(e => e.clientHeight > 0
   && e.scrollHeight > e.clientHeight + 1 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY))
   .map(e => e.tagName + '.' + e.className);
 return {alvos, dicas, letras, rol, sobra: d.scrollHeight - d.clientHeight,
         lateral: d.scrollWidth > d.clientWidth + 1}; }"""  # noqa: E501

_ABRE = """(id) => { const e = document.getElementById(id);
  if (e) { e.checked = true; e.dispatchEvent(new Event('change', {bubbles: true})); } }"""


def _medir(navegador: Browser, arquivo: pathlib.Path, vista: tuple[int, int],
           estado: str = "") -> dict[str, Any]:
    pg = navegador.new_page(viewport={"width": vista[0], "height": vista[1]})
    try:
        pg.goto(arquivo.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(300)
        if estado:
            pg.evaluate(_ABRE, estado)
            pg.wait_for_timeout(200)
        medida: dict[str, Any] = pg.evaluate(_MEDIDA)
        return medida
    finally:
        pg.close()


_CACHE_BASE: dict[tuple[str, tuple[int, int], str], dict[str, Any]] = {}


def _medida_da_base(navegador: Browser, nome: str, vista: tuple[int, int],
                    estado: str) -> dict[str, Any]:
    chave = (nome[:2], vista, estado)
    if chave not in _CACHE_BASE:
        _CACHE_BASE[chave] = _medir(navegador, MOCKUP / f"{PRINCIPAL[nome[:2]]}.html", vista,
                                    estado)
    return _CACHE_BASE[chave]


def _problemas(navegador: Browser, nome: str, arquivo: pathlib.Path, vista: tuple[int, int],
               estado: str = "") -> list[str]:
    """O que reprova o piso nesta vista e neste estado, nas duas opções: a dica focável é alvo."""
    m = _medir(navegador, arquivo, vista, estado)
    base = _medida_da_base(navegador, nome, vista, estado)
    falta: list[str] = []
    if m["alvos"]:
        falta.append(f"alvos abaixo de 24 px: {m['alvos'][:3]}")
    if m["letras"]:
        falta.append(f"letra abaixo de 12 px: {m['letras'][:3]}")
    if m["dicas"]:
        falta.append(f"a dica focável abaixo de 24 px: {m['dicas'][:3]}")
    novos = [r for r in m["rol"] if r not in base["rol"]]
    if novos or m["lateral"]:
        falta.append(f"rolagem nova: {novos} lateral={m['lateral']}")
    if m["sobra"] > base["sobra"]:
        falta.append(f"o documento passa da vista ({m['sobra']} > {base['sobra']})")
    return falta


def _casos() -> list[tuple[str, tuple[int, int], str]]:
    casos: list[tuple[str, tuple[int, int], str]] = []
    for nome in NOMES:
        for vista in VISTAS:
            for estado in (ESTADOS_02 if nome.startswith("02") else ("",)):
                casos.append((nome, vista, estado))
    return casos


@pytest.mark.parametrize(("nome", "vista", "estado"), _casos())
def test_o_piso_vale_em_toda_vista_e_estado(navegador: Browser, nome: str,
                                            vista: tuple[int, int], estado: str) -> None:
    """Zero alvo abaixo de 24 px (a dica inclusive), zero letra abaixo de 12 px e nenhuma rolagem
    nova."""
    assert _problemas(navegador, nome, VARIANTES / f"{nome}.html", vista, estado) == [], (
        nome, vista, estado)


def test_a_folha_da_variante_mora_na_cabeca() -> None:
    """O `<style>` do corpo é do produto. MORDIDA: a folha da variante dentro do corpo reprova."""
    for nome in NOMES:
        assert FOLHA in _ler(nome)
        assert _folhas_do_corpo(_ler(nome)) == _folhas_do_corpo(_base(nome)), nome
    doc = _ler(NOMES[0])
    mordido = doc.replace("</body>", f"{FOLHA}.x{{color:red}}</style></body>", 1)
    assert _folhas_do_corpo(mordido) != _folhas_do_corpo(_base(NOMES[0]))


def test_o_desenho_so_muda_a_folha_e_as_vagas() -> None:
    """A 09 muda só a folha (o «Tamanho da interface» e o resto ficam como estão); a 02 muda a folha
    e as duas vagas, e nada mais."""
    for nome in NOMES[2:]:
        assert _sem_a_folha(_ler(nome)) == _base(nome), nome
    base = _base(NOMES[0])
    for nome in NOMES[:2]:
        sem = _VAGA.sub("", _sem_a_folha(_ler(nome)))
        assert sem == _VAGA.sub("", base), nome


@pytest.mark.parametrize("nome", NOMES[:2])
def test_a_vaga_diz_so_player_n_desconectado(nome: str) -> None:
    """r4-02-18: a vaga é «Player 3 • Desconectado», sem cor de plástico, máscara, microfone,
    sensores nem bateria. MORDIDA: o texto antigo da vaga (`P3 • — • —`) reprova."""
    def ruins(doc: str) -> list[str]:
        vagas = _vagas(doc)
        falta: list[str] = []
        if len(vagas) != 2:
            return [f"{len(vagas)} vagas (2)"]
        for n, v in zip((3, 4), vagas, strict=True):
            texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", v)).strip()
            if texto != f"Player {n} • Desconectado":
                falta.append(f"a vaga {n} diz «{texto}»")
            for dado in ("mascara", "mic-selo", "giro-ligado", "accel-ligado", "bateria",
                         "Microfone", "Bateria"):
                if dado in v:
                    falta.append(f"a vaga {n} ainda tem «{dado}»")
        return falta

    assert ruins(_ler(nome)) == []
    antigo = _vagas(_base(nome))
    assert len(antigo) == 2
    mordido = _ler(nome).replace(_vagas(_ler(nome))[0], antigo[0], 1)
    assert ruins(mordido) != []
    # o texto certo com o dado escondido dentro também reprova: a vaga não carrega a máscara
    vaga = _vagas(_ler(nome))[0]
    escondido = vaga.replace("</label>", '<b data-campo="mascara" hidden></b></label>', 1)
    assert ruins(_ler(nome).replace(vaga, escondido, 1)) != []


# ---------------------------------------------------------------------------------------------
# As mordidas da régua do piso
# ---------------------------------------------------------------------------------------------

def _escreve(tmp_path: pathlib.Path, nome: str, doc: str) -> pathlib.Path:
    arquivo = tmp_path / f"{nome}.html"
    arquivo.write_text(doc, encoding="utf-8")
    return arquivo


def test_a_regua_do_piso_morde_a_folha_arrancada(navegador: Browser,
                                                 tmp_path: pathlib.Path) -> None:
    nome = NOMES[0]
    sem = _sem_a_folha(_ler(nome))
    assert sem != _ler(nome)
    assert _problemas(navegador, nome, _escreve(tmp_path, "sem-folha", sem), VISTAS[0], "c-p1")


def test_a_regua_do_piso_morde_o_alvo_pequeno(navegador: Browser, tmp_path: pathlib.Path) -> None:
    nome = NOMES[2]
    doc = _ler(nome)
    fim = "font-size:12px !important}\nbody .sec-rot.sr-log"
    mordido = doc.replace("height:24px !important;" + fim, "height:22px !important;" + fim, 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "alvo", mordido), VISTAS[0])
    assert any("alvos abaixo" in f for f in falta), falta


def test_a_regua_do_piso_morde_a_letra_pequena(navegador: Browser, tmp_path: pathlib.Path) -> None:
    nome = NOMES[2]
    doc = _ler(nome)
    mordido = doc.replace("body .log{font-size:12px", "body .log{font-size:11px", 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "letra", mordido), VISTAS[0])
    assert any("letra abaixo" in f for f in falta), falta


@pytest.mark.parametrize(("nome", "regra"), (
    (NOMES[0], "body.por-controle .rot[data-dica]{"),
    (NOMES[1], "body.por-controle .rot[data-dica],"),
))
def test_a_regua_do_piso_morde_a_dica_pequena(navegador: Browser, tmp_path: pathlib.Path,
                                              nome: str, regra: str) -> None:
    doc = _ler(nome)
    mordido = doc.replace(regra, "body.por-controle .nada" + regra[-1], 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "dica", mordido), VISTAS[0], "c-p1")
    assert any("dica focável" in f for f in falta), falta


def test_a_regua_do_piso_morde_a_rolagem_nova(navegador: Browser, tmp_path: pathlib.Path) -> None:
    nome = NOMES[1]
    doc = _ler(nome)
    estoura = "body.por-controle .moldura{min-height:200px !important}"
    mordido = doc.replace("</style>\n</head>", estoura + "</style>\n</head>", 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "rola", mordido), VISTAS[2], "c-p1")
    assert any("rolagem nova" in f or "documento" in f for f in falta), falta


@pytest.mark.parametrize("nome", NOMES[2:])
def test_a_regua_do_piso_morde_a_dica_pequena_da_09(navegador: Browser, tmp_path: pathlib.Path,
                                                    nome: str) -> None:
    doc = _ler(nome)
    mordido = doc.replace("body .saude .txt{min-height:24px !important}\n", "", 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "dica-09", mordido), VISTAS[0])
    assert any("dica focável" in f for f in falta), falta


def test_a_regua_do_piso_morde_a_rolagem_lateral(navegador: Browser,
                                                 tmp_path: pathlib.Path) -> None:
    nome = NOMES[2]
    doc = _ler(nome)
    mordido = doc.replace("</style>\n</head>", "body{min-width:2400px}</style>\n</head>", 1)
    assert mordido != doc
    falta = _problemas(navegador, nome, _escreve(tmp_path, "lateral", mordido), VISTAS[0])
    assert any("lateral=True" in f for f in falta), falta
