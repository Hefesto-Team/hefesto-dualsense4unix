"""TOOLTIP-C1 — a dica ABRINDO, medida com um ponteiro de verdade.

A QUEIXA DELA, 11/09/2026, com o produto instalado na frente:

    *"em todos os tooltips somem os textos e eles não mostram ou mostram e*
    *saem direto. em todas as paginas isso ocorre."*  # noqa-acento: citação literal dela

**POR QUE NENHUMA RÉGUA DESTA CASA TINHA VISTO ISSO**, e é o ponto inteiro
deste arquivo: as réguas de dica que existiam mediam o **DOM** — *o atributo
`title` está lá?* — e o atributo sempre esteve. O que ela relatou não é a
ausência do atributo: é a **dica não abrir**. São perguntas diferentes, e a
segunda exige três coisas que nenhuma régua daqui fazia:

1. uma **janela de verdade** (não `Gtk.OffscreenWindow`: offscreen não tem
   ponteiro, e sem ponteiro não há dica);
2. um **ponteiro dirigido** até o elemento, como a mão dela;
3. o **tempo passando** — meio segundo é o mínimo para qualquer dica, e uma
   régua que lê o DOM uma vez mede um instante.

A TELA DELA NÃO PAGA ISTO: o `tests/conftest.py` sobe um ``Xvfb`` próprio e
tira o `WAYLAND_DISPLAY` do caminho (TELA-DELA-01). A janela deste arquivo
nasce lá dentro, e a guarda abaixo recusa correr se não for o caso.

O QUE A CURA FEZ, e o que esta régua prende
-------------------------------------------
A dica saiu do **popup do sistema** (uma janela que o compositor dela desenha,
posiciona e pinta) e passou a ser um elemento **da página** — a
``hefesto_vivo.DICA_DA_CASA``. O porquê, com as quatro hipóteses medidas uma a
uma, está no bloco daquela constante.

As três medidas desta régua, e cada uma morde num lugar:

* **com a camada, mão parada** — a dica abre e fica;
* **com a camada, mão tremendo** — a dica abre. Medido nesta bancada em
  11/09/2026, o popup do sistema abriu **0 de 200 amostras em 80 s** com o
  ponteiro tremendo 1 px a cada 150 ms: o GTK reinicia a contagem de meio
  segundo a cada evento de movimento, e a mão que treme nunca chega lá;
* **sem a camada (A MORDIDA)** — a dica da casa não existe, e quem aparece é o
  popup do sistema. Se esta última passar, a régua não está medindo a cura.
"""

from __future__ import annotations

from typing import Any

import json
import os

import pytest

#: Onde se mede. A ``03-gatilhos`` é a aba com mais dicas das dez (195 `title`
#: no arquivo publicado) e nenhuma delas depende de um controle na mesa — a
#: régua não pode precisar de aparelho para medir uma dica.
PAGINA = "03-gatilhos.html"

#: O tamanho mínimo de um alvo para o ponteiro poder pousar nele com folga. Um
#: elemento de 2 px casa por acaso com o vizinho, e a medição passaria a ser
#: sobre outra dica — a armadilha que esta casa chama de *instrumento
#: respondendo sobre outra coisa*.
ALVO_MINIMO = (24, 14)

#: Meio segundo da dica + folga de laço. Abaixo disto a régua mede o ATRASO, e
#: não a dica.
MS_ATE_LER = 2200

#: Quanto o laço do GTK pode demorar antes de a régua desistir. Generoso de
#: propósito: uma régua que estoura sozinha vira vermelho de infraestrutura.
MS_DE_GUARDA = 30000


def _sem_tela_de_mentira() -> str:
    """A razão para NÃO abrir janela aqui, ou string vazia."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return ("a sessão gráfica DELA está no ambiente — esta régua abre uma "
                "janela de verdade e ela tem UMA tela (TELA-DELA-01)")
    if os.environ.get("HEFESTO_NA_TELA"):
        return "HEFESTO_NA_TELA está ligado: a janela nasceria na tela dela"
    if not os.environ.get("DISPLAY"):
        return "sem DISPLAY — não há servidor X onde abrir a janela"
    return ""


_JS_ALVO = """(function(){
  const fora = [];
  for(const el of document.querySelectorAll('[title],[data-hef-dica]')){
    const t = String(el.getAttribute('title')
                     || el.getAttribute('data-hef-dica') || '').trim();
    if(t.length < 8) continue;
    const r = el.getBoundingClientRect();
    if(r.width < LARG || r.height < ALT) continue;
    if(r.top < 40 || r.left < 40) continue;
    if(r.bottom > window.innerHeight - 20 || r.right > window.innerWidth - 20) continue;
    fora.push({x:r.left, y:r.top, w:r.width, h:r.height, texto:t,
               tag:el.tagName});
  }
  return JSON.stringify(fora.slice(0, 1));
})()""".replace("LARG", str(ALVO_MINIMO[0])).replace("ALT", str(ALVO_MINIMO[1]))

_JS_ESTADO = """(function(){
  const c = document.getElementById('hef-dica');
  const r = c ? c.getBoundingClientRect() : null;
  return JSON.stringify({
    camada: !!(window.__hefDica && window.__hefDica.instalada),
    aberta: !!(window.__hefDica && window.__hefDica.aberta()),
    texto: (window.__hefDica ? window.__hefDica.texto() : ''),
    largura: r ? Math.round(r.width) : 0,
    altura: r ? Math.round(r.height) : 0,
    dentro: !!(r && r.left >= 0 && r.top >= 0
               && r.right <= window.innerWidth && r.bottom <= window.innerHeight),
    // A COLHEITA É O QUE CALA O POPUP DO SISTEMA: nenhum `title` no DOM vivo.
    sobrou_title: document.querySelectorAll('[title]').length,
  });
})()"""


def _popup_do_sistema_aberto(gtk: Any) -> bool:
    """Há uma janela de dica do GTK na tela AGORA?

    É o outro lado da medida, e sem ele a régua não saberia dizer QUEM está
    mostrando a frase — a página ou o toolkit.
    """
    for w in gtk.Window.list_toplevels():
        if "Tooltip" in type(w).__name__ and w.get_visible() and w.get_mapped():
            return True
    return False


def _medir(*, com_camada: bool, tremer: bool) -> dict[str, Any]:
    """Abre a página, leva o ponteiro até uma dica e diz o que apareceu."""
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gdk, GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    fora: dict[str, Any] = {"erro": "", "alvo": None, "estado": None,
                            "popup_do_sistema": False}
    janela = Gtk.Window()
    janela.set_default_size(1280, 860)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()
    janela.move(0, 0)

    disp = Gdk.Display.get_default()
    ponteiro = disp.get_default_seat().get_pointer()
    tela = disp.get_default_screen()

    def falhar(msg: str) -> None:
        fora["erro"] = msg
        Gtk.main_quit()

    def responder(res: Any) -> str:
        return view.evaluate_javascript_finish(res).to_string()

    def leu_estado(_v: Any, res: Any) -> None:
        try:
            fora["estado"] = json.loads(responder(res))
        except Exception as e:
            falhar(f"não li o estado da dica: {e}")
            return
        Gtk.main_quit()

    def ler_estado() -> bool:
        fora["popup_do_sistema"] = _popup_do_sistema_aberto(Gtk)
        view.evaluate_javascript(_JS_ESTADO, -1, None, None, None, leu_estado)
        return False

    def tremida() -> bool:
        """A mão dela não fica parada: 1 px, como um dedo no rato."""
        fora["j"] = 1 - int(fora.get("j", 0))
        ponteiro.warp(tela, int(fora["px"]) + int(fora["j"]), int(fora["py"]))
        return bool(fora.get("tremendo"))

    def achou_alvo(_v: Any, res: Any) -> None:
        try:
            lista = json.loads(responder(res))
        except Exception as e:
            falhar(f"não achei alvo: {e}")
            return
        if not lista:
            falhar(f"nenhuma dica mensurável na {PAGINA} — a régua ficaria "
                   "verde por vacuidade")
            return
        alvo = lista[0]
        fora["alvo"] = alvo
        c = view.translate_coordinates(janela, int(alvo["x"] + alvo["w"] / 2),
                                       int(alvo["y"] + alvo["h"] / 2))
        raiz = janela.get_window().get_root_coords(int(c[-2]), int(c[-1]))
        px, py = int(raiz[-2]), int(raiz[-1])
        fora["px"], fora["py"] = px, py
        # LONGE PRIMEIRO, e depois em três passos: uma dica só nasce de uma
        # CHEGADA. Pousar o ponteiro já em cima não gera o movimento que
        # qualquer dica — a do sistema ou a da casa — espera.
        ponteiro.warp(tela, max(px - 300, 4), max(py - 140, 4))
        for i, ms in enumerate((250, 320, 390)):
            f = (i + 1) / 3.0
            x, y = int(px - 300 * (1 - f)), int(py - 140 * (1 - f))
            GLib.timeout_add(
                ms, (lambda a, b: lambda: (ponteiro.warp(tela, a, b), False)[1])(x, y))
        if tremer:
            fora["tremendo"] = True
            GLib.timeout_add(
                430, lambda: (GLib.timeout_add(150, tremida), False)[1])
        GLib.timeout_add(MS_ATE_LER, ler_estado)

    def pronto(_v: Any, res: Any) -> None:
        try:
            responder(res)
        except Exception as e:
            falhar(f"a camada da dica não instalou: {e}")
            return
        view.evaluate_javascript(_JS_ALVO, -1, None, None, None, achou_alvo)

    def carregou(v: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        if com_camada:
            v.evaluate_javascript(hefesto_vivo.DICA_DA_CASA, -1, None, None,
                                  None, pronto)
        else:
            # A MORDIDA: a página fica como estava antes desta sprint — com o
            # popup do sistema e nada mais.
            v.evaluate_javascript("'sem camada'", -1, None, None, None, pronto)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    # O `timeout_add` PENDENTE DE OUTRO TESTE mata este laço com um `main_quit`
    # armado lá atrás — já custou onze medições nesta casa. A guarda própria é
    # removida no `finally`.
    guarda = GLib.timeout_add(MS_DE_GUARDA, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        fora["tremendo"] = False
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    return fora


@pytest.fixture(scope="module")
def com_a_mao_parada() -> dict[str, Any]:
    razao = _sem_tela_de_mentira()
    if razao:
        pytest.skip(razao)
    return _medir(com_camada=True, tremer=False)


@pytest.fixture(scope="module")
def com_a_mao_tremendo() -> dict[str, Any]:
    razao = _sem_tela_de_mentira()
    if razao:
        pytest.skip(razao)
    return _medir(com_camada=True, tremer=True)


@pytest.fixture(scope="module")
def sem_a_camada() -> dict[str, Any]:
    razao = _sem_tela_de_mentira()
    if razao:
        pytest.skip(razao)
    return _medir(com_camada=False, tremer=False)


def test_a_dica_abre_com_a_mao_parada(com_a_mao_parada: dict[str, Any]) -> None:
    """O caso simples, e ele é o piso: chegar e esperar meio segundo."""
    m = com_a_mao_parada
    assert not m["erro"], m["erro"]
    estado = m["estado"]
    assert estado["camada"], "a camada da dica não está de pé"
    assert estado["aberta"], (
        f"a dica NÃO abriu sobre {m['alvo']['tag']} em {MS_ATE_LER} ms — "
        f"é a queixa dela de 11/09/2026: {estado}")
    assert estado["largura"] > 40 and estado["altura"] > 12, (
        f"a dica abriu com tamanho de nada: {estado}")


def test_a_dica_mostra_o_texto_do_elemento(com_a_mao_parada: dict[str, Any]) -> None:
    """*"somem os textos"* — a dica tem de dizer o que o elemento explica."""
    m = com_a_mao_parada
    assert not m["erro"], m["erro"]
    esperado = m["alvo"]["texto"]
    visto = m["estado"]["texto"]
    assert visto == esperado, (
        f"a dica abriu com OUTRO texto (ou vazia):\n  esperado {esperado!r}\n"
        f"  visto    {visto!r}")


def test_a_dica_nao_atravessa_a_janela(com_a_mao_parada: dict[str, Any]) -> None:
    """Uma dica meio fora da borda é uma dica que não abriu."""
    m = com_a_mao_parada
    assert not m["erro"], m["erro"]
    assert m["estado"]["dentro"], (
        f"a dica saiu da janela: {m['estado']}")


def test_o_popup_do_sistema_nao_aparece_junto(com_a_mao_parada: dict[str, Any]) -> None:
    """Os dois na tela seria pior que um só — e foi a primeira forma da cura.

    MEDIDO em 11/09/2026: tirar o `title` no `mousemove` é tarde, porque o
    WebKit já resolveu a dica no mesmo evento. Com a colheita na carga, não
    sobra `title` nenhum no DOM vivo e o popup do sistema não tem do que nascer.
    """
    m = com_a_mao_parada
    assert not m["erro"], m["erro"]
    assert m["estado"]["sobrou_title"] == 0, (
        f"sobraram {m['estado']['sobrou_title']} `title` no DOM vivo — o popup "
        "do sistema volta por eles")
    assert not m["popup_do_sistema"], (
        "o popup do sistema abriu JUNTO com a dica da casa — duas frases na "
        "tela, uma por cima da outra")


def test_a_dica_abre_com_a_mao_tremendo(com_a_mao_tremendo: dict[str, Any]) -> None:
    """A metade que o popup do sistema NUNCA entregou.

    Medido nesta bancada em 11/09/2026: com o ponteiro tremendo 1 px a cada
    150 ms, a dica nativa abriu **0 de 200 amostras em 80 s**. O GTK reinicia a
    contagem de meio segundo a cada evento de movimento; a dica da casa conta a
    partir da ENTRADA no elemento e só zera quando o elemento MUDA.
    """
    m = com_a_mao_tremendo
    assert not m["erro"], m["erro"]
    assert m["estado"]["aberta"], (
        "a dica não abriu com a mão tremendo — é exatamente o que ela relatou "
        f"como *«não mostram»*: {m['estado']}")


def test_a_mordida_sem_a_camada_nao_ha_dica_da_casa(sem_a_camada: dict[str, Any]) -> None:
    """A MORDIDA. Sem a camada, a página volta a depender do popup do sistema.

    Se este teste passar com a cura arrancada, a régua não mede a cura — mede
    outra coisa, que é a família de defeito que esta casa nomeou em 04/09.
    """
    m = sem_a_camada
    assert not m["erro"], m["erro"]
    estado = m["estado"]
    assert not estado["camada"], (
        "a camada da dica apareceu sem ninguém instalar — a mordida não morde")
    assert not estado["aberta"], "sem camada não pode haver dica da casa aberta"
    assert estado["sobrou_title"] > 0, (
        "sem a camada o `title` tem de continuar no DOM: é dele que o popup do "
        "sistema vive, e é ele que a colheita tira")


# ---------------------------------------------------------------------------
# O ENDEREÇO `atributo/title` CONTINUA PINTANDO — e agora pinta na dica
# ---------------------------------------------------------------------------
#
# A colheita tira o `title` do DOM vivo. Sem o par de curas do `escrever()` e do
# `LER_CAMPOS`, o produto continuaria escrevendo `title` — e cada escrita
# ressuscitaria o popup do compositor NO MEIO da dica aberta. Estas duas medidas
# não precisam de ponteiro: `Gtk.OffscreenWindow` basta, e custa um segundo.

#: Um endereço da ``03-gatilhos`` cujo alvo é ``atributo`` e cujo atributo é
#: ``title`` — é por ele que o produto explica o modo do gatilho.
CAMPO_DE_DICA = "dica-modo-e"

_FRASE_DA_REGUA = "A RÉGUA ESCREVEU ESTA DICA"


def _pintar_e_ler() -> dict[str, Any]:
    """Instala a camada, manda o produto pintar a dica e lê os dois lados."""
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    ler = """(function(){
      const el = document.querySelector('[data-campo="CAMPO"]');
      if(!el) return JSON.stringify({erro:'a 03-gatilhos perdeu o endereço CAMPO'});
      return JSON.stringify({
        dica: el.getAttribute('data-hef-dica'),
        title: el.getAttribute('title'),
      });
    })()""".replace("CAMPO", CAMPO_DE_DICA)
    pintar = ('window.__hef.pintar({mesa:{"' + CAMPO_DE_DICA + '": '
              + json.dumps(_FRASE_DA_REGUA) + '}});')

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1280, 860)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def passo(script: str, depois: Any) -> None:
        view.evaluate_javascript(script, -1, None, None, None, depois)

    def leu(_v: Any, res: Any) -> None:
        try:
            saiu.append(view.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(json.dumps({"erro": f"leitura: {e}"}))
        Gtk.main_quit()

    def pintou(_v: Any, res: Any) -> None:
        try:
            view.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(json.dumps({"erro": f"pintura: {e}"}))
            Gtk.main_quit()
            return
        passo(ler, leu)

    def colheu(_v: Any, res: Any) -> None:
        try:
            view.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(json.dumps({"erro": f"camada: {e}"}))
            Gtk.main_quit()
            return
        passo(pintar, pintou)

    def instalou(_v: Any, res: Any) -> None:
        try:
            view.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(json.dumps({"erro": f"bootstrap: {e}"}))
            Gtk.main_quit()
            return
        passo(hefesto_vivo.DICA_DA_CASA, colheu)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(MS_DE_GUARDA, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    assert saiu, "o WebKit não respondeu"
    return dict(json.loads(saiu[0]))


@pytest.fixture(scope="module")
def pintado() -> dict[str, Any]:
    return _pintar_e_ler()


def test_o_produto_pinta_a_dica_e_nao_ressuscita_o_title(
        pintado: dict[str, Any]) -> None:
    """O alvo `atributo/title` segue o texto até onde ele mora agora."""
    assert not pintado.get("erro"), pintado["erro"]
    assert pintado["dica"] == _FRASE_DA_REGUA, (
        f"o produto não alcançou a dica de `{CAMPO_DE_DICA}`: {pintado}")
    assert pintado["title"] is None, (
        "o produto reescreveu um `title` no DOM vivo — e com ele volta o popup "
        f"do compositor por cima da dica da casa: {pintado}")


# ---------------------------------------------------------------------------
# A FIAÇÃO — porque uma camada que ninguém instala é uma camada que não existe
# ---------------------------------------------------------------------------

def test_o_piloto_instala_a_camada_a_cada_carga() -> None:
    """`window.__hefDica` morre com o documento; a instalação é por CARGA.

    Instalar uma vez e navegar deixaria as outras nove abas com o popup do
    sistema de volta — que é o *"em todas as paginas"* dela.  # noqa-acento: citação literal dela
    """
    from pathlib import Path

    fonte = Path(__file__).resolve().parents[2] / (
        "src/hefesto_dualsense4unix/interface/hefesto_vivo.py")
    texto = fonte.read_text(encoding="utf-8")
    assert "self.ponte.perguntar(DICA_DA_CASA, self._dica_instalada)" in texto, (
        "o piloto parou de instalar a camada da dica a cada carga")
    assert "def _dica_instalada" in texto, (
        "a falha da camada voltou a ser silenciosa — sem `_dica_instalada` "
        "ninguém fica sabendo que a tela voltou ao popup do sistema")


def test_o_visor_do_desenho_tambem_recebe_a_camada() -> None:
    """`ver.py` é onde ela OLHA o desenho; ele não pode mostrar outra tela."""
    from pathlib import Path

    fonte = Path(__file__).resolve().parents[2] / (
        "src/hefesto_dualsense4unix/interface/ver.py")
    texto = fonte.read_text(encoding="utf-8")
    assert "DICA_DA_CASA" in texto and "UserScript" in texto, (
        "o visor do desenho voltou a usar o popup do sistema, e o que ela olha "
        "deixou de ser o que o produto faz")
