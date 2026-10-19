"""O desenho de 19/10/2026 da Perfis (10) e da Experimental (07), para ela escolher.

Cinco sprints, só o desenho: o editor de Perfis (o estilo guardado, o nome Freestyle, o renomear),
os eventos do perfil («Meu comando»), a coluna do ajuste próprio com a ativação e os analógicos,
a janela do servidor Buttplug (o teto e a força de cada controle) e a janela genérica das
extensões. As variantes não escolhidas moram em `mockup/variantes/` e nunca entram na página
publicada nem no produto; a que a recomendação escolhe é o próprio `mockup/`.

MORDIDAS (cada uma foi feita e viu reprovar; a lista está no relato do tema desenho-perfis-07):

* pôr «Freestyle» na lista de estilos -> `test_a_lista_de_estilos_tem_as_duas_marcas_...`;
* tirar o «Adulto» da lista -> o mesmo;
* pôr o campo «Nome» de volta no editor -> `test_o_desenho_nao_tem_campo_de_nome_do_perfil`;
* devolver a frase longa ao rótulo da variante B -> `test_a_variante_b_do_freestyle_cabe_a_940`;
* deixar a variante de pé depois de o gerador mudar -> `test_as_variantes_de_10_estao_em_dia`.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))
_INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))

CHROME = pathlib.Path("/usr/bin/google-chrome")
MOCKUP = RAIZ / "mockup"
VARIANTES = MOCKUP / "variantes"
DEZ = MOCKUP / "10-perfis.html"
SETE = MOCKUP / "07-lancadores.html"
VISTAS = ((940, 809), (1272, 860), (1512, 860), (1900, 1000))

sem_chrome = pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema")


def _ler(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _sem_estilo_nem_script(html: str) -> str:
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", html, flags=re.S)


def _no_chrome(arquivo: pathlib.Path, vista: tuple[int, int], script: str,
               antes: str = "") -> Any:
    """Abre o arquivo no Chrome do sistema, na vista dada, e devolve o que `script` mediu."""
    from playwright.sync_api import sync_playwright

    import olhar

    with sync_playwright() as pw:
        navegador = olhar._navegador(pw)
        try:
            pg = navegador.new_page(viewport={"width": vista[0], "height": vista[1]})
            pg.goto(f"file://{arquivo}")
            pg.wait_for_load_state("networkidle")
            if antes:
                pg.evaluate(antes)
                pg.wait_for_timeout(200)
            return pg.evaluate(script)
        finally:
            navegador.close()


# ---------------------------------------------------------------------------------------------
# Perfis 1 · O-EDITOR-DE-PERFIS-MOSTRA-O-ESTILO-RECUSA-O-FREESTYLE-E-PERDE-O-QUE-O-DESENHO-TIROU-01
# ---------------------------------------------------------------------------------------------


def _estilos_da_pagina(html: str) -> list[str]:
    trecho = html.split('data-hef="editor.estilo"', 1)[1].split("</select>", 1)[0]
    return re.findall(r"<option[^>]*>([^<]*)</option>", trecho)


def test_a_lista_de_estilos_tem_as_duas_marcas_e_nao_tem_freestyle() -> None:
    """O select de estilo oferece Visual novel e Adulto, abre no travessão e nunca diz Freestyle."""
    html = _ler(DEZ)
    opcoes = _estilos_da_pagina(html)
    assert opcoes[0] == "—", opcoes[:2]
    assert "Visual novel" in opcoes and "Adulto" in opcoes, opcoes
    assert not [o for o in opcoes if "freestyle" in o.lower()], (
        "o Freestyle é o botão do Ultra, nunca um estilo nem um perfil da aba Perfis")
    # o select abre sem escolha: quem afirma o estilo do perfil é a pintura do produto
    trecho = html.split('data-hef="editor.estilo"', 1)[1].split("</select>", 1)[0]
    assert len(re.findall(r"<option[^>]*\bselected\b", trecho)) == 1


def test_o_desenho_nao_tem_campo_de_nome_do_perfil() -> None:
    """O renomear não volta à tela (decisão por delegação): sem campo e sem botão."""
    doc = _sem_estilo_nem_script(_ler(DEZ))
    assert 'data-hef-gesto="editor.nome"' not in doc
    assert 'data-hef-gesto="renomear"' not in doc
    assert "Renomear" not in doc
    barra = re.search(r'<div class="barra-quatro">(.*?)</div></div>', doc, re.S)
    assert barra is not None
    assert len(re.findall(r"<button\b", barra.group(1))) == 4


def test_a_variante_a_do_freestyle_usa_o_ponto_que_o_campo_ja_tem() -> None:
    """A (recomendada): nenhum elemento novo; o ponto acende e a dica diz a frase."""
    doc = _ler(VARIANTES / "10-freestyle-A-ponto-com-dica.html")
    assert 'value="Freestyle"' in doc
    assert '<span class="exige on"' in doc
    dica = re.search(r'data-hef="editor.jogo.exigencia"[^>]*>([^<]*)</span>', doc)
    assert dica is not None and dica.group(1) == "Freestyle é o botão do controle, não um jogo"
    assert 'class="rot on"' not in doc, "a variante A não desenha o rótulo ao lado"
    pagina = _ler(DEZ)
    assert "Freestyle" not in _sem_estilo_nem_script(pagina), "a página não afirma o recado"
    assert 'class="exige on"' not in pagina


def test_a_variante_b_do_freestyle_acende_o_rotulo_ao_lado() -> None:
    doc = _ler(VARIANTES / "10-freestyle-B-frase-ao-lado.html")
    rot = re.search(r'<span class="rot on" data-dica="([^"]*)"><span class="al alerta">'
                    r"([^<]*)</span>", doc)
    assert rot is not None
    assert rot.group(1) == "Freestyle é o botão do controle, não um jogo"
    assert rot.group(2) == "Nome reservado"
    assert 'class="exige on"' not in doc, "na B só o rótulo diz; o ponto fica apagado"


@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
def test_a_variante_b_do_freestyle_cabe_a_940(vista: tuple[int, int]) -> None:
    """O rótulo da B aparece inteiro, sem reticências, em toda largura (a frase longa não cabia)."""
    medida = _no_chrome(VARIANTES / "10-freestyle-B-frase-ao-lado.html", vista, """() => {
      const r = document.querySelector('.campo .rot.on .al');
      const d = document.documentElement, p = r.parentElement;
      return {cortado: r.scrollWidth > r.clientWidth + 1 || p.scrollWidth > p.clientWidth + 1,
              rolagem: d.scrollHeight > d.clientHeight, largo: d.scrollWidth > d.clientWidth + 1};
    }""")
    assert not medida["cortado"], medida
    assert not medida["rolagem"] and not medida["largo"], medida


def test_a_variante_b_do_renomear_poe_o_quinto_botao_na_barra() -> None:
    doc = _sem_estilo_nem_script(_ler(VARIANTES / "10-renomear-B-botao-na-barra.html"))
    barra = re.search(r'<div class="barra-quatro">(.*?)</div></div>', doc, re.S)
    assert barra is not None
    botoes = re.findall(r"<button\b[^>]*>([^<]*)</button>", barra.group(1))
    assert botoes == ["Duplicar", "Novo", "Renomear", "Remover", "Ativar"], botoes


def test_as_variantes_de_10_estao_em_dia() -> None:
    """Cada `mockup/variantes/10-*` é o que o gerador produz agora, a partir do desenho."""
    import aba10

    esperadas = aba10.variantes(_ler(DEZ))
    for nome, doc in esperadas.items():
        assert (VARIANTES / f"{nome}.html").read_text(encoding="utf-8") == doc, (
            f"{nome} ficou velha: rode `aba10.py`")
    em_disco = {p.stem for p in VARIANTES.glob("10-*.html")}
    sobra = em_disco - set(esperadas)
    assert not sobra or all(s.startswith("10-") for s in sobra)


def test_a_variante_nunca_entra_na_pagina_publicada() -> None:
    """`mockup/variantes/` não é uma das dez páginas, e o publicado não a carrega."""
    from hefesto_dualsense4unix.interface import onde

    assert not [p for p in onde.paginas() if "variantes" in p.parts]
    publicado = _ler(onde.pagina("10-perfis.html", publicado=True))
    assert "Nome reservado" not in publicado and "Freestyle é o botão" not in publicado
