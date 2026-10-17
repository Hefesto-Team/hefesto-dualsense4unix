"""A aba Navegação do todo: 23 linhas de botão, a fila de acesso e as definições no pé.

Sem as quatro janelas de antes (definições do mouse, teclas do teclado, remapeamento e point and
click), sem o «?» ao lado do título e sem aviso fixo. A fila leva ao mapa do controle (os botões e o
point and click) e à Acessibilidade, que é uma tela por âncora.
Cabe sem rolagem vertical a 1212x809.

MORDIDAS: devolver um `span.ajuda`, uma das quatro janelas velhas (`tela-nova`), um dos dois
`href` do mapa ou tirar uma linha do desenho reprovam; a rolagem vertical também.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "06-navegacao.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
JANELAS_QUE_SAIRAM = ("definicoes-mouse", "teclas-do-teclado", "remapeamento", "point-and-click")


def _doc() -> str:
    """O desenho sem estilo e sem script: o que a pessoa vê e o que ela aciona."""
    bruto = MOCKUP.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)


def test_nao_ha_span_ajuda_nem_janela_velha() -> None:
    # Prova da D-1510-A-NAVEGACAO-PERDE-O-STATUS-DO-MODO-E-O-TAMBEM-NO-JOGO.
    doc = _doc()
    assert "span class=\"ajuda\"" not in doc and 'class="ajuda"' not in doc
    telas = re.findall(r'<[^<>]*\bclass="tela-nova"[^<>]*>', doc)
    ids = [i for t in telas for i in re.findall(r'\bid="([^"]+)"', t)]
    assert ids == ["acessibilidade"], ids
    for velha in JANELAS_QUE_SAIRAM:
        assert f'id="{velha}"' not in doc, f"a janela «{velha}» voltou"


def test_tem_vinte_e_tres_linhas_de_botao_e_uma_so_desligada() -> None:
    """Uma linha por botão do desenho: 22 gravam na hora, e o toque no touchpad só se lê."""
    doc = _doc()
    gravam = re.findall(r'data-gesto="linha-de-botao" data-linha="([a-z0-9_]+)"', doc)
    assert len(gravam) == 22 and len(set(gravam)) == 22, gravam
    assert 'disabled data-dica="O toque no touchpad move o cursor"' in doc
    assert "sem efeito hoje" not in doc


def test_a_fila_leva_ao_mapa_e_a_acessibilidade() -> None:
    doc = _doc()
    fila = re.search(r'<div class="fila2">(.*?)</div>\s*</div>', doc, flags=re.S)
    assert fila, "sem a fila de acesso"
    roxos = re.findall(r'<a class="btn roxo" href="([^"]+)"[^>]*>([^<]+)</a>', fila.group(1))
    assert roxos == [("mapa-do-controle.html#trocar", "Trocar os botões"),
                     ("mapa-do-controle.html#point-and-click", "Point and click"),
                     ("#acessibilidade", "Acessibilidade")], roxos


def test_a_acessibilidade_traz_o_giroscopio_e_as_opcoes_do_desenho() -> None:
    # Prova da D-1510-A-ACESSIBILIDADE-APARECE-APAGADA-ATE-OS-DONOS.
    doc = _doc()
    tela = doc[doc.index('id="acessibilidade"'):]
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", tela))
    for rotulo in ("Uma mão", "Alternar em vez de segurar", "Repetir ao segurar",
                   "Ignorar tremor abaixo de", "Zona morta", "Giroscópio como analógico"):
        assert rotulo in texto, rotulo
    assert "Cancelar" in texto and "Guardar" in texto


def test_os_rotulos_do_permitir_e_do_teclado_sao_os_do_produto() -> None:
    # D-1510-AS-PALAVRAS-DOS-BOTOES-SAO-AS-DO-DESENHO
    # Prova da D-1510-AS-PALAVRAS-DOS-BOTOES-SAO-AS-DO-DESENHO.
    doc = _doc()
    permitir = re.findall(r'<button[^>]*data-gesto="permitir-navegacao"[^>]*>([^<]+)</button>', doc)
    assert permitir == ["Interna", "Steam", "Uso geral"], permitir
    teclado = re.search(r'data-gesto="teclado".*?</select>', doc, flags=re.S)
    assert teclado and set(re.findall(r"<option[^>]*>([^<]+)</option>", teclado.group(0))) == {
        "Só dentro do jogo", "Só fora do jogo", "Sempre", "Desativado"}


@pytest.fixture(scope="module")
def pagina():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        yield pg
        nav.close()


def test_cabe_sem_rolagem_vertical_a_1212_por_809(pagina) -> None:
    pagina.goto(MOCKUP.as_uri())
    m = pagina.evaluate("""() => {
      const d = document.documentElement;
      return {alto: d.scrollHeight, cabe: d.clientHeight,
              largo: d.scrollWidth > d.clientWidth + 1};
    }""")
    assert m["alto"] <= m["cabe"] + 1 and not m["largo"], m


def test_a_dica_do_seletor_acompanha_o_valor(pagina) -> None:
    """O `title` de cada seletor com dica diz a escolha de agora, e não a de quando nasceu."""
    pagina.goto(MOCKUP.as_uri())
    antes = pagina.evaluate(
        "document.querySelector('[data-gesto=\"teclado\"]').getAttribute('title')")
    pagina.evaluate("""() => { const s = document.querySelector('[data-gesto="teclado"]');
      s.value = 'Sempre'; s.dispatchEvent(new Event('change', {bubbles: true})); }""")
    depois = pagina.evaluate(
        "document.querySelector('[data-gesto=\"teclado\"]').getAttribute('title')")
    assert depois and depois != antes, (antes, depois)


def test_os_tres_de_permitir_navegacao_cabem_numa_linha(pagina) -> None:
    """«Interna», «Steam» e «Uso geral» ficam lado a lado, dentro da linha de «Opções».

    O «Navega com» saiu com o pedido de 16/10 (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, N5), e com ele a
    linha de chips que encolhia o nome com quatro controles; os três botões são fixos.
    MORDIDA: `flex-wrap:wrap` no `.seg.mini` com a coluna estreita quebra em duas linhas.
    """
    # D-1510-O-NAVEGA-COM-ENCOLHE-O-NOME-COM-QUATRO
    pagina.goto(MOCKUP.as_uri())
    m = pagina.evaluate("""() => {
      const seg = document.querySelector('[role=radiogroup][aria-label="Permitir navegação"]');
      const op = seg.closest('.op2').getBoundingClientRect();
      const r = [...seg.querySelectorAll('button')].map(c => c.getBoundingClientRect());
      return {n: r.length, tops: [...new Set(r.map(b => Math.round(b.top)))],
              direita: Math.max(...r.map(b => b.right)), op_direita: op.right};
    }""")
    assert m["n"] == 3 and len(m["tops"]) == 1, m
    assert m["direita"] <= m["op_direita"] + 1, m


def test_o_que_ainda_nao_grava_aparece_apagado(pagina) -> None:
    """O «Voltar ao padrão» e o «Guardar» da Acessibilidade não gravam, e a tela os mostra apagados.

    MORDIDA: tirar a regra `.btn.apagado` deixa os dois acesos, iguais a um botão que funciona.
    """
    # Prova da D-1510-A-ACESSIBILIDADE-APARECE-APAGADA-ATE-OS-DONOS.
    pagina.goto(MOCKUP.as_uri() + "#acessibilidade")
    opacidades = pagina.evaluate("""() => [...document.querySelectorAll(
      '#acessibilidade .apagado[aria-disabled="true"]')].map(b => getComputedStyle(b).opacity)""")
    assert len(opacidades) == 2 and all(float(o) <= 0.6 for o in opacidades), opacidades
