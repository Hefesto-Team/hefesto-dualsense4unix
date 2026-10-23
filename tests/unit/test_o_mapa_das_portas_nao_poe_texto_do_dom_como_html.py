"""O mapa das portas não devolve ao `innerHTML` o texto que leu do próprio DOM
(OS-ALERTAS-DO-CODEQL-ZERAM-01).

O CodeQL acusava `js/xss-through-dom` em quatro lugares do JavaScript do gerador
(`pagina_do_mapa.py`) e `js/incomplete-multi-character-sanitization` na regex que tirava tag da dica
do título. A cura mora no GERADOR, em `EDICOES_DO_CODEQL`; o `mockup/` e o publicado se regeram pelo
`--publicar`. Esta régua lê o que o gerador PRODUZ, não a origem congelada.

MORDIDAS: devolver qualquer das cinco trocas ao texto antigo (a regex `<[^>]+>`, a opção montada
como cadeia, o número de entrada lido do atributo, o título da face sem escape) reprova o caso que a
nomeia; tirar o `'` ou o `>` do `emAtributo` reprova o caso do escape.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pagina_do_mapa as gerador


@pytest.fixture(scope="module")
def pagina() -> str:
    return str(gerador.pagina())


def _corpo_de(pagina: str, assinatura: str) -> str:
    """O corpo de `function nome(...) { … }` até a chave que fecha na coluna do início."""
    inicio = pagina.index(assinatura)
    achou = re.match(r" *", pagina[pagina.rfind("\n", 0, inicio) + 1:])
    recuo = achou.group(0) if achou else ""
    fim = pagina.index("\n" + recuo + "}", inicio)
    return pagina[inicio:fim]


def test_a_dica_do_titulo_le_o_texto_pelo_parser_e_nao_por_regex(pagina: str) -> None:
    assert "replace(/<[^>]+>/g" not in pagina, (
        "a dica do título voltou a tirar tag por regex (js/incomplete-multi-character-sanitization)"
    )
    assert "emAtributo(soTexto(m.linhas[0] ? m.linhas[0].t : \"\"))" in pagina
    corpo = _corpo_de(pagina, "function soTexto(")
    assert "DOMParser" in corpo and ".body.textContent" in corpo
    assert "innerHTML" not in corpo


def test_o_em_atributo_escapa_aspas_apostrofo_e_os_dois_sinais(pagina: str) -> None:
    corpo = _corpo_de(pagina, "function emAtributo(")
    for letra in ('"&amp;"', '"&quot;"', '"&#39;"', '"&lt;"', '"&gt;"'):
        assert letra in corpo, f"o `emAtributo` deixou de escrever {letra}"


def test_a_opcao_do_seletor_nasce_como_no(pagina: str) -> None:
    assert "sel.innerHTML = '<option" not in pagina, "a opção voltou a ser uma cadeia de HTML"
    assert 'document.createElement("option")' in pagina
    assert "opc.textContent = para" in pagina


def test_o_numero_da_entrada_vem_do_modelo_e_nao_do_atributo(pagina: str) -> None:
    corpo = _corpo_de(pagina, "function entradaConhecida(")
    assert "porNum(n)" in corpo
    assert "editando = abre.getAttribute(" not in pagina, (
        "a entrada em edição voltou a ser o texto do atributo"
    )
    assert 'editando = entradaConhecida(abre.getAttribute("data-ap-abre"))' in pagina
    assert 'var n = plug.getAttribute("data-porta"), p = porNum(n);' not in pagina
    assert 'var p = porNum(plug.getAttribute("data-porta")), n = p ? p.n : "";' in pagina


def test_o_titulo_da_face_vai_escapado_para_o_innerhtml(pagina: str) -> None:
    assert "<h3>' + (f.titulo || f.nome) + '</h3>" not in pagina
    assert "<h3>' + emAtributo(f.titulo || f.nome) + '</h3>" in pagina


def test_toda_edicao_do_codeql_esta_na_lista_do_gerador() -> None:
    """Edição fora de `EDICOES` é edição que não roda: a página nasceria sem a cura."""
    for edicao in gerador.EDICOES_DO_CODEQL:
        assert edicao in gerador.EDICOES


#: O gesto de quem usa, no exemplo: dá à entrada um nome com marca, declara um hub nela, e a
#: face nova leva o nome no título; depois abre «Sugestões» e lê a dica de cada troca.
_NOME_COM_MARCA = "<b>Z9</b> & Co"
#: uma linha de troca com tag e entidade: a dica tem de ler só a letra (o `<4` é letra, não tag)
_SUJO = "<b>Hub</b> &amp; dock <i>novo</i> 3 <4"
_JS_DO_NOME_COM_MARCA = r"""
(function(){
  const r = {};
  const titulos = () => Array.from(document.querySelectorAll('.face-cab h3'));
  for (const n of Array.from(document.querySelectorAll('.plug[data-porta]'))
                     .map(p => p.getAttribute('data-porta'))) {
    /* o clique fora do painel aberto só o fecha: o segundo abre o da entrada */
    for (let i = 0; i < 2 && !document.querySelector('#edita [data-nome="' + n + '"]'); i++) {
      document.querySelector('.plug[data-porta="' + n + '"]').click();
    }
    const campo = document.querySelector('#edita [data-nome="' + n + '"]');
    const livre = () =>
      document.querySelector('#edita [data-liga="hub"]:not([aria-disabled="true"])');
    if (!campo || !livre()) continue;
    campo.value = NOME;
    campo.dispatchEvent(new Event('change', {bubbles: true}));
    /* o `change` repinta o painel: o botão do hub é lido de novo, e não o de antes */
    livre().click();
    const h3 = titulos().find(h => h.textContent.indexOf('Z9') !== -1);
    if (h3) { r.titulo = h3.textContent; r.marcaViva = !!h3.querySelector('b'); break; }
  }
  /* a função da página, com o texto que a regex velha deixava passar */
  r.soTexto = (function () { SO_TEXTO; return soTexto(SUJO); })();
  document.querySelector('.modo[data-modo="ideal"]').click();
  r.dicas = Array.from(document.querySelectorAll('h4[data-dica]'))
    .map(h => h.getAttribute('data-dica'));
  return JSON.stringify(r);
})()
"""


def _no_webkit(pagina: str, tmp_path: Any) -> dict[str, Any]:
    """Abre a página no WebKit do produto (Xvfb da suíte) e roda o gesto do nome com marca."""
    import json
    import os

    if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HEFESTO_NA_TELA")
            or not os.environ.get("DISPLAY")):
        pytest.skip("sem o X de mentira: o WebKit abriria na tela dela ou não abriria")
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre o mapa das portas no WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    copia = tmp_path / "mapa-das-portas.html"
    copia.write_text(pagina, encoding="utf-8")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1440, 1000)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def leu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as erro:
            saiu.append(json.dumps({"erro": str(erro)}))
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            so_texto = _corpo_de(pagina, "function soTexto(") + "}"
            js = (_JS_DO_NOME_COM_MARCA.replace("SO_TEXTO", so_texto)
                  .replace("SUJO", json.dumps(_SUJO)).replace("NOME", json.dumps(_NOME_COM_MARCA)))
            v.evaluate_javascript(js, -1, None, None, None, leu)

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


def test_no_webkit_o_nome_com_marca_vira_texto_no_titulo_e_a_dica_e_so_texto(
    pagina: str, tmp_path: Any
) -> None:
    """O gesto de verdade, no motor do produto: o nome digitado com `<b>` aparece como LETRA no
    título da face do hub (antes da cura ele virava negrito, isto é, HTML vivo), e a dica de cada
    troca de «Sugestões» chega sem tag e sem entidade escrita por extenso.

    A MORDIDA: tire o `emAtributo` do `<h3>` em `EDICOES_DO_CODEQL` e a primeira asserção
    reprova; devolva a regex `<[^>]+>` no lugar do `soTexto` e a dica volta a carregar
    `&amp;`/`&lt;` literais onde o texto da troca os tem.
    """
    lido = _no_webkit(pagina, tmp_path)
    assert "erro" not in lido, lido
    assert lido.get("titulo") == "Hub na entrada " + _NOME_COM_MARCA, lido
    assert lido.get("marcaViva") is False, "o nome digitado virou HTML no título da face"
    assert lido["soTexto"] == "Hub & dock novo 3 <4", lido["soTexto"]
    assert lido["dicas"], "«Sugestões» sem nenhuma troca: a dica não foi medida"
    for dica in lido["dicas"]:
        assert "<" not in dica and not re.search(r"&(?:amp|lt|gt|quot|#39|nbsp);", dica), dica
