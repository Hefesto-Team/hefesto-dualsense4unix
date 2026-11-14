"""O Mapa do controle desenha o controle certo (O-MAPA-DO-CONTROLE-DESENHA-CERTO-01).

Medido no motor do produto (o WebKit, numa janela fora da tela), no desenho e no publicado, nas duas
larguras da régua: em repouso nenhuma peça do desenho acende, nem com todas as linhas mudadas (o
perfil Navegar muda quase todas), e nenhuma traz contorno nem cor própria (o contorno do touchpad, o
Share e os analógicos eram carmim no controle de modelo não sabido);
focar a linha da Cruz acende só a Cruz, e o botão apertado (o `pisca`) e a linha escolhida (o `on`)
acendem só a peça deles; toda tecla tem o miolo pintado, com o glifo legível por cima em todo
modelo de plástico; a bola do PS fica no ponto do meio dos dois analógicos, com o glifo do PS dentro
da bola; o glifo do direcional e do PS no desenho é o mesmo da linha; o microfone não tem glifo
solto; e o «Usar em» com o nome longo do jogo cabe numa linha.

MORDIDAS (14/11/2026): devolver a regra que pintava a peça na cor do tipo quando a linha está
«muda» reprova `test_em_repouso_nada_acende`; voltar a tecla ao anel (`teclas_cheias` sem efeito)
reprova `test_toda_tecla_tem_o_miolo_pintado`; tirar o `ps_entre_os_analogicos` reprova
`test_o_ps_fica_no_meio_dos_analogicos`; tirar o `css_do_contraste` reprova o contraste no White;
deixar o filtro do touchpad reprova `test_em_repouso_nada_acende`; e tirar o `:focus` dos gatilhos
reprova `test_so_acende_a_peca_em_uso`; tirar o `css_da_zona` reprova `test_em_repouso_nada_acende`;
voltar a escolher a cor do glifo por um limiar de luz (e não pelo contraste) reprova o
Hyperpop Rhythm Blue; tirar o `sem_letra_solta` (o «R» solto, escuro por baixo do glifo do
analógico direito) reprova `test_nenhum_glifo_solto`.
"""
from __future__ import annotations

import json
import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("abre o mapa do controle num WebKit")

from hefesto_dualsense4unix.interface import onde

TAMANHOS = [(1212, 809), (1920, 1080)]
PAGINAS = [False, True]
NOME_LONGO = "Thicc Magic: Elves' Perverted Beauty Standards.gif"

MEDIR = r"""
(function(){
  const $ = s => document.querySelector(s), id = s => document.getElementById(s);
  const ds = $('svg.ds');
  const linhas = [...document.querySelectorAll('.b2')];
  const pecas = [...new Set(linhas.map(
    b => [...b.classList].find(c => c.startsWith('item-')).slice(5)))];
  const geo = ':scope > :is(path,rect,circle,ellipse), :scope > g.miolo > ellipse';
  const fundo = ':scope > :is(path,rect,circle), :scope > g.miolo > ellipse';
  const pinturas = () => Object.fromEntries(pecas.map(p => [p,
    [...id('mp-' + p).querySelectorAll(geo)]
      .map(e => getComputedStyle(e).fill + '|' + getComputedStyle(e).stroke).join(';')]));
  const rosa = 'rgb(255, 121, 198)';
  const acesas = () => Object.entries(pinturas()).filter(([, v]) => v.includes(rosa))
    .map(([p]) => p).sort();
  const luz = s => {
    const v = (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number).map(c => {
      c /= 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; });
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const contraste = (a, b) => {
    const [x, y] = [luz(a), luz(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
  const caixa = e => e.getBoundingClientRect();
  const centro = e => { const r = caixa(e); return [r.left + r.width / 2, r.top + r.height / 2]; };
  const pintado = p => {
    const g = id('mp-' + p), [x, y] = centro(g.querySelector(fundo));
    return [...g.querySelectorAll(geo)].some(e => {
      const c = getComputedStyle(e);
      if (c.fill === 'none' || /rgba\(.*, 0\)$/.test(c.fill) || +c.opacity === 0) return false;
      const pt = ds.createSVGPoint(); pt.x = x; pt.y = y;
      return e.isPointInFill(pt.matrixTransform(e.getScreenCTM().inverse()));
    });
  };
  const cor_do_fundo = p => getComputedStyle(id('mp-' + p).querySelector(fundo)).fill;
  const faixas = p => { const f = cor_do_fundo(p), u = f.match(/url\("?#([^")]+)"?\)/);
    return u ? [...id(u[1]).querySelectorAll('rect')].map(r => getComputedStyle(r).fill) : [f]; };
  const glifos = [...ds.querySelectorAll('[id^="mp-glifo-"]')].map(g => g.id.slice(9));
  const com_peca = glifos.filter(p => id('mp-' + p));
  const leitura = {};
  linhas.forEach(b => b.dataset.estado = '');
  leitura.repouso = acesas();
  leitura.contorno = pecas.filter(p => getComputedStyle(id('mp-' + p)).filter !== 'none');
  const neutras = pinturas();
  linhas.forEach(b => b.dataset.estado = 'muda');
  leitura.muda = acesas();
  leitura.muda_mudou = Object.keys(neutras).filter(p => pinturas()[p] !== neutras[p]);
  linhas.forEach(b => b.dataset.estado = '');
  leitura.ativos = document.querySelectorAll(
    '.b2[data-estado~="on"], .b2[data-estado~="pisca"]').length;
  $('.b2.item-cross').focus();
  leitura.foco_cruz = acesas();
  leitura.glifo_da_cruz_no_rosa = contraste(getComputedStyle($('.s-cross')).color, rosa);
  document.activeElement.blur();
  leitura.solta = acesas();
  $('.b2.item-dpad_up').dataset.estado = 'pisca';
  leitura.pisca = acesas();
  $('.b2.item-dpad_up').dataset.estado = '';
  $('.b2[data-b="l1"]').dataset.estado = 'muda on';
  leitura.on = acesas();
  $('.b2[data-b="l1"]').dataset.estado = '';
  leitura.sem_miolo = pecas.filter(p => !pintado(p));
  const viva = c => { const v = (c.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    return v.length === 3 && Math.max(...v) - Math.min(...v) > 40; };
  ds.dataset.colorway = '';
  leitura.cor_sem_modelo = pecas.filter(p => [...id('mp-' + p).querySelectorAll(geo)]
    .some(e => viva(getComputedStyle(e).fill)));
  leitura.contraste = {};
  const todos = [...new Set([...document.querySelectorAll('svg.ds style')]
    .map(s => s.textContent).join('')
    .match(/svg\[data-colorway="[^"]+"\]/g).map(s => s.slice(19, -2)))];
  leitura.modelos = todos.length;
  for (const cw of ['', ...todos]) {
    ds.dataset.colorway = cw;
    leitura.contraste[cw] = com_peca.map(p => [p, +Math.min(...faixas(p).map(
      c => contraste(getComputedStyle(id('mp-glifo-' + p)).color, c))).toFixed(2)]);
  }
  const anel = p => centro($('#mp-' + p + ' > path.peca'));
  const L = anel('stick_l'), R = anel('stick_r'), ps = centro($('#mp-ps > circle'));
  leitura.ps = {dx: ps[0] - (L[0] + R[0]) / 2, dy: ps[1] - (L[1] + R[1]) / 2};
  const dentro = (a, b) => a.left >= b.left - .5 && a.right <= b.right + .5
    && a.top >= b.top - .5 && a.bottom <= b.bottom + .5;
  leitura.glifo_fora = com_peca.filter(p => !['share', 'options'].includes(p))
    .filter(p => !dentro(caixa(id('mp-glifo-' + p)), caixa(id('mp-' + p).querySelector(fundo))));
  leitura.glifos = glifos;
  leitura.letra_solta = [...ds.querySelectorAll('text')]
    .filter(t => !t.closest('[id^="mp-glifo-"]') && getComputedStyle(t).display !== 'none')
    .map(t => t.textContent.trim());
  const u = $('.usar-em');
  u.innerHTML = '<span class="jogo">' + NOME + '</span><button class="jogo mais">+ Jogo</button>';
  const j = u.querySelector('.jogo'), rg = document.createRange(); rg.selectNodeContents(j);
  leitura.usar_em = {linhas: new Set([...rg.getClientRects()].map(x => Math.round(x.top))).size,
    sobra: Math.round(caixa(u.closest('.cel')).right - caixa(u.querySelector('.mais')).right),
    altura: Math.round(caixa(j).height)};
  leitura.rola = document.scrollingElement.scrollHeight - innerHeight;
  return JSON.stringify(leitura);
})()
""".replace("NOME", json.dumps(NOME_LONGO))

PRONTA = "document.readyState === 'complete' && document.fonts.status === 'loaded' ? 'ok' : ''"


def _no_webkit(uri: str, tamanho: tuple[int, int]) -> dict[str, Any]:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gdk, GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    respostas: list[str] = []
    view = WebKit2.WebView()
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view.set_size_request(*tamanho)
    janela.add(view)
    janela.show_all()

    def respondeu(v: Any, res: Any, _u: Any = None) -> None:
        try:
            respostas.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as erro:
            respostas.append(f"ERRO {erro}")
        Gtk.main_quit()

    def pronta(v: Any, res: Any, _u: Any = None) -> None:
        try:
            ok = v.evaluate_javascript_finish(res).to_string() == "ok"
        except Exception:
            ok = False
        if ok:
            GLib.timeout_add(250, lambda: view.evaluate_javascript(
                MEDIR, -1, None, None, None, respondeu, None) and False)
        else:
            GLib.timeout_add(20, perguntar)

    def perguntar() -> bool:
        view.evaluate_javascript(PRONTA, -1, None, None, None, pronta, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            view.grab_focus()
            foco = Gdk.Event.new(Gdk.EventType.FOCUS_CHANGE)
            foco.focus_change.in_ = 1
            foco.focus_change.window = janela.get_window()
            view.send_focus_change(foco)
            perguntar()

    view.connect("load-changed", carregou)
    view.load_uri(uri)
    guarda = GLib.timeout_add(40000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert respostas and respostas[0].startswith("{"), f"o WebKit não mediu o mapa: {respostas}"
    return dict(json.loads(respostas[0]))


_LIDO: dict[tuple[bool, tuple[int, int]], dict[str, Any]] = {}


def _mapa(publicado: bool, tamanho: tuple[int, int]) -> dict[str, Any]:
    if (publicado, tamanho) not in _LIDO:
        uri = onde.pagina("mapa-do-controle.html", publicado=publicado).as_uri()
        _LIDO[(publicado, tamanho)] = _no_webkit(uri, tamanho)
    return _LIDO[(publicado, tamanho)]


@pytest.fixture(params=[(p, t) for p in PAGINAS for t in TAMANHOS],
                ids=lambda v: f"{'publicado' if v[0] else 'desenho'}-{v[1][0]}")
def lido(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _mapa(*request.param)


def test_em_repouso_nada_acende(lido: dict[str, Any]) -> None:
    assert lido["repouso"] == [] and lido["ativos"] == 0, lido["repouso"]
    assert lido["contorno"] == [], f"peça com contorno de cor própria: {lido['contorno']}"
    assert lido["cor_sem_modelo"] == [], f"peça com cor própria: {lido['cor_sem_modelo']}"
    assert lido["muda"] == [], f"a linha mudada acende a peça: {lido['muda']}"
    assert lido["muda_mudou"] == [], f"a linha mudada pinta a peça: {lido['muda_mudou']}"


def test_so_acende_a_peca_em_uso(lido: dict[str, Any]) -> None:
    assert lido["foco_cruz"] == ["cross"], lido["foco_cruz"]
    assert lido["solta"] == [], lido["solta"]
    assert lido["pisca"] == ["dpad_up"], lido["pisca"]
    assert lido["on"] == ["l1"], lido["on"]
    assert lido["glifo_da_cruz_no_rosa"] >= 3, lido["glifo_da_cruz_no_rosa"]


def test_toda_tecla_tem_o_miolo_pintado(lido: dict[str, Any]) -> None:
    assert lido["sem_miolo"] == [], f"tecla oca no desenho: {lido['sem_miolo']}"


def test_o_glifo_se_le_sobre_a_tecla_em_todo_plastico(lido: dict[str, Any]) -> None:
    assert lido["modelos"] >= 20, f"a régua leu só {lido['modelos']} modelos de plástico"
    for cw, pares in lido["contraste"].items():
        fracos = [(p, c) for p, c in pares if c < 3]
        assert not fracos, f"glifo apagado sobre a tecla no modelo {cw or 'sem plástico'}: {fracos}"


def test_o_ps_fica_no_meio_dos_analogicos(lido: dict[str, Any]) -> None:
    assert abs(lido["ps"]["dx"]) < 1 and abs(lido["ps"]["dy"]) < 1, lido["ps"]


def test_nenhum_glifo_solto(lido: dict[str, Any]) -> None:
    assert lido["glifo_fora"] == [], f"glifo fora da tecla: {lido['glifo_fora']}"
    assert "mic" not in lido["glifos"], "o glifo do microfone voltou a ficar solto embaixo do PS"
    assert lido["letra_solta"] == [], f"letra fora de glifo no desenho: {lido['letra_solta']}"


def test_o_usar_em_cabe_numa_linha(lido: dict[str, Any]) -> None:
    assert lido["usar_em"]["linhas"] == 1 and lido["usar_em"]["altura"] <= 26, lido["usar_em"]
    assert lido["usar_em"]["sobra"] >= 0, lido["usar_em"]
    assert lido["rola"] <= 0, lido["rola"]


@pytest.mark.parametrize("publicado", PAGINAS)
def test_o_glifo_do_desenho_e_o_da_linha(publicado: bool) -> None:
    html = onde.pagina("mapa-do-controle.html", publicado=publicado).read_text(encoding="utf-8")

    def miolo(trecho: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<svg\b[^>]*>|</svg>", "", trecho)).strip()

    for pid in ("dpad_up", "dpad_right", "dpad_down", "dpad_left", "ps"):
        linha = re.search(rf'<button class="b2 item-{pid}"[^>]*><span class="b2-gl">'
                          r'(<svg.*?</svg>)', html, flags=re.S)
        desenho = re.search(rf'<g id="mp-glifo-{pid}"[^>]*>(.*?)</g>'
                            r'(?=<g id="mp-glifo-|\s*<g id="mp-feat)', html, flags=re.S)
        assert linha and desenho, pid
        assert miolo(linha.group(1)) == miolo(desenho.group(1)), pid
