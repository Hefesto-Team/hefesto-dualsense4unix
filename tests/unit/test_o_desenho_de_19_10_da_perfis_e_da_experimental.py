"""O desenho de 19/10/2026 da Perfis (10) e da Experimental (07), para ela escolher.

Cinco sprints, só o desenho: o editor de Perfis (o estilo guardado, o nome Freestyle, o renomear),
os eventos do perfil («Meu comando»), a coluna do ajuste próprio com a ativação e os analógicos,
e a janela genérica das extensões (a janela do servidor do acessório saiu da 07 em 19/10/2026,
com o adulto, para a extensão que o serve). As variantes não escolhidas saíram do repositório
(`mockup/variantes/` não existe mais); a que a recomendação escolhe é o próprio `mockup/`.

MORDIDAS (cada uma foi feita e viu reprovar; a lista está no relato do tema desenho-perfis-07):

* pôr «Freestyle» na lista de estilos -> `test_a_lista_de_estilos_tem_as_duas_marcas_...`;
* tirar o «Adulto» da lista -> o mesmo;
* pôr o campo «Nome» de volta no editor -> `test_o_desenho_nao_tem_campo_de_nome_do_perfil`;
* devolver a frase longa ao rótulo da variante B -> `test_a_variante_b_do_freestyle_cabe_a_940`;
* deixar a variante de pé depois de o gerador mudar -> `test_as_variantes_de_10_estao_em_dia`.
* pôr o comando de volta na linha do «Quando» -> `test_o_comando_do_evento_tem_linha_propria_...`;
* tirar o `:has` ou o gesto do `.ordem-vale` -> `test_o_comando_aparece_so_com_o_meu_comando_...`;
* devolver a coluna do Status aos 255 px -> `test_a_fileira_das_secoes_cabe_na_celula_...`;
* devolver as abas à janela genérica -> `test_a_janela_generica_da_extensao_...`;
* tirar o `position:absolute` do menu do ⋮ -> `test_o_menu_do_mais_flutua_...`;
* devolver o «Fechar» único ao «Configurar» do lançador -> `test_o_configurar_do_lancador_...`;
* devolver «Jogos» no lugar de «Pastas dos jogos» no «Configurar» -> o mesmo;
* deixar no disco uma variante que o gerador não produz mais -> `test_as_variantes_de_10_...`;
* devolver uma variante da 07, escolhida em 19/10 -> `test_a_07_nao_guarda_variante_...`.
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


def test_a_10_nao_tem_mais_variante() -> None:
    """O desenho de 19/10 foi escolhido (todas na recomendada), e as de 20/10 também."""
    sobra = [p.name for p in VARIANTES.glob("10-*.html")]
    assert not sobra, sobra


def test_a_variante_nunca_entra_na_pagina_publicada() -> None:
    """`mockup/variantes/` não é uma das dez páginas, e o publicado não a carrega."""
    from hefesto_dualsense4unix.interface import onde

    assert not [p for p in onde.paginas() if "variantes" in p.parts]
    publicado = _ler(onde.pagina("10-perfis.html", publicado=True))
    assert "Nome reservado" not in publicado and "Freestyle é o botão" not in publicado


_ESCOLHE_EVENTO = """(function(){
  document.querySelector('[data-v="eventos"]').click();
  var s = document.querySelector('[data-hef="editor.evento"]');
  s.value = '%s';
  s.dispatchEvent(new Event('change', {bubbles: true}));
})()"""
_MEDE_COMANDO = """() => {
  const c = document.querySelector('.ev-cmd'), g = document.querySelector('.guarda');
  const q = document.querySelector('.so-eventos'), caixa = c.getBoundingClientRect();
  const d = document.documentElement;
  return {visivel: caixa.width > 0 && caixa.height > 0,
          linha_propria: !q.contains(c),
          guarda_rola: g.scrollHeight > g.clientHeight + 1,
          pagina_rola: d.scrollHeight > d.clientHeight, largo: d.scrollWidth > d.clientWidth + 1,
          ordem_visivel: document.querySelector('.ordem-vale').getBoundingClientRect().height > 0};
}"""


def test_o_comando_do_evento_tem_linha_propria_so_no_meu_comando() -> None:
    """O campo do comando saiu da linha do «Quando» e mora em `.so-comando`, que o `:has` revela."""
    doc = _ler(DEZ)
    corpo = _sem_estilo_nem_script(doc)
    quando = re.search(r'<div class="campo so-eventos.*?</div>', corpo, re.S)
    assert quando is not None and 'class="ev-cmd"' not in quando.group(0)
    linha = re.search(r'<div class="campo so-comando">(.*?)</div>', corpo, re.S)
    assert linha is not None and 'class="ev-cmd"' in linha.group(1)
    assert 'data-hef="editor.evento.comando"' in linha.group(1), "o endereço é o mesmo de antes"
    assert re.search(r'option\[value="meu_comando"\]:checked\) \+ \.campo\.so-comando'
                     r'\{display:grid\}', doc)


@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
@pytest.mark.parametrize("momento,aparece", [("cena", False), ("controle_conectado", False),
                                             ("meu_comando", True)])
def test_o_comando_aparece_so_com_o_meu_comando_e_a_tela_nao_rola(
        vista: tuple[int, int], momento: str, aparece: bool) -> None:
    m = _no_chrome(DEZ, vista, _MEDE_COMANDO, antes=_ESCOLHE_EVENTO % momento)
    assert m["visivel"] is aparece, m
    assert m["linha_propria"], m
    assert not m["guarda_rola"] and not m["pagina_rola"] and not m["largo"], m
    assert not m["ordem_visivel"], "evento não tem jogo, então não tem «Qual vale primeiro»"


@sem_chrome
def test_a_aba_jogos_continua_com_a_ordem_do_que_vale() -> None:
    m = _no_chrome(DEZ, (1272, 860), _MEDE_COMANDO)
    assert m["ordem_visivel"] and not m["visivel"], m


_SECOES_DE_UMA_LINHA = ("leds", "triggers", "rumble", "speaker", "mic", "sensores", "mascara",
                        "movimento", "ativacao", "analogicos")  # (noqa-acento)
_MEDE_A_FILEIRA = """() => {
  const linhas = [...document.querySelectorAll('.guarda tbody tr')].filter(
    tr => tr.querySelector('.gls') && tr.querySelector('.gls').children.length);
  return linhas.map(tr => {
    const g = tr.querySelector('.gls'), td = tr.querySelector('.gd-pecas');
    return {celulas: g.children.length,
            sobra: Math.round(td.getBoundingClientRect().right
                              - g.lastElementChild.getBoundingClientRect().right)};
  });
}"""


def _secoes_da_primeira_linha(html: str) -> list[str]:
    linha = re.search(r'<td class="gd-pecas">(.*?)</td>', html, re.S)
    assert linha is not None
    return re.findall(r'data-hef-secao="([^"]+)"', linha.group(1))


def test_a_coluna_de_ajuste_proprio_tem_a_ativacao_e_os_analogicos_depois_do_movimento() -> None:
    """A (recomendada) é o desenho de 16/10: dez células, cada seção com glifo e ponto."""
    html = _ler(DEZ)
    assert tuple(_secoes_da_primeira_linha(html)) == _SECOES_DE_UMA_LINHA
    assert ".gd-pecas{width:271px}" in html
    assert ".gd-pecas .gls{display:flex;width:100%;gap:clamp(5px," in html


@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
def test_a_fileira_das_secoes_cabe_na_celula_em_toda_vista(vista: tuple[int, int]) -> None:
    """A fileira inteira fica dentro da célula do Status (a 940 px a de dez passava 16 px)."""
    linhas = _no_chrome(DEZ, vista, _MEDE_A_FILEIRA)
    assert linhas and all(ln["celulas"] == 10 for ln in linhas), linhas
    assert all(ln["sobra"] >= 0 for ln in linhas), linhas


def test_a_07_nao_guarda_variante_nem_gerador_de_variante() -> None:
    """O usuário escolheu as três da 07 em 19/10: as não escolhidas saem do disco e do gerador."""
    import aba07

    assert not sorted(p.name for p in VARIANTES.glob("07-*.html"))
    assert not hasattr(aba07, "variantes")


_ID = "modificacao"  # (noqa-acento)
_ABRE_A_GENERICA = f"(function(){{location.hash='#{_ID}';}})()"
_CLICA_O_MAIS = ("(function(){const b = document.querySelector('.ext-mais');"
                 " b.focus(); b.click();})()")


def _janela(html: str, ident: str) -> str:
    sem = _sem_estilo_nem_script(html)
    inicio = sem.index(f'id="{ident}"')
    fim = sem.find('<div class="tela-nova"', inicio + 1)
    return sem[inicio:fim if fim > 0 else len(sem)]


def test_a_janela_generica_da_extensao_tem_um_cartao_por_grupo_e_cancelar_guardar() -> None:
    """A (recomendada): um cartão por grupo, e não as abas de antes (a extensão sem ``agora``)."""
    import desenho_da_experimental as exp

    janela = exp.modificacao_miolo_html("Minha extensão", exp.OPCOES_DO_DESENHO, mod="exemplo")
    titulos = re.findall(r'<span class="ac-tit">([^<]*)</span>', janela)
    assert titulos == ["Geral", "Luz e vibração", "Avançado"], titulos
    assert "mj-abas" not in janela and 'type="radio"' not in janela
    assert janela.count('<div class="ky-linha" id="mod-op-') == 7
    assert ('<a class="btn" href="#" data-gesto="cancelar-modificacao" data-v="exemplo">'
            'Cancelar</a>') in janela
    assert '<a class="btn roxo" href="#" data-gesto="guardar-modificacao"' in janela
    assert ">Fechar</a>" not in janela.split('class="tn-rod"')[1]


def test_a_janela_da_extensao_com_agora_no_desenho_e_o_arranjo_c() -> None:
    """O arranjo C escolhido em 22/10/2026: a coluna «Agora», os grupos em abas e o «Parar tudo»."""
    janela = _janela(_ler(SETE), _ID)
    abas = re.findall(r'<label for="mj-aba-\d+">([^<]*)</label>', janela)
    assert abas == ["Aparelhos", "Toques", "Ligação", "Geral", "Luz e vibração", "Avançado"], abas
    assert janela.count(" checked>") >= 1 and 'id="mj-aba-0" checked' in janela
    assert 'id="mod-agora"' in janela and "Para</span>Todos" not in janela
    assert 'class="ja-parar" data-gesto="parar-tudo-da-modificacao"' in janela
    assert '<a class="btn roxo" href="#" data-gesto="guardar-modificacao"' in janela


@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
def test_a_janela_generica_da_extensao_cabe_sem_rolagem_nem_corte(vista: tuple[int, int]) -> None:
    medida = """() => {
      const cx = document.querySelector('@ .tn-cx'), r = cx.getBoundingClientRect();
      const corpo = document.querySelector('@ .ja-opcoes');
      const d = document.documentElement;
      const corte = [...document.querySelectorAll(
        '@ .ky-ctrl, @ .ky-linha, @ .tql, @ .cx-linha, @ .ap')]
        .filter(c => c.scrollWidth > c.clientWidth + 1).length;
      return {cabe: r.top >= 0 && r.bottom <= window.innerHeight, corte,
              rola: corpo.scrollHeight > corpo.clientHeight + 1,
              largo: d.scrollWidth > d.clientWidth + 1};
    }""".replace("@", "#" + _ID)
    m = _no_chrome(SETE, vista, medida, antes=_ABRE_A_GENERICA)
    assert m["cabe"] and not m["corte"] and not m["rola"] and not m["largo"], m


@sem_chrome
def test_o_menu_do_mais_flutua_sem_empurrar_os_lancadores() -> None:
    """O menu aparece sobre a linha, sem mexer em nada abaixo."""
    vista = (1272, 860)
    medida = """() => {
      const fila = document.querySelector('.lanc-fila').getBoundingClientRect();
      const m = document.querySelector('.ext-menu'), r = m.getBoundingClientRect();
      const visivel = getComputedStyle(m).display !== 'none' && r.width > 0;
      const botoes = m.querySelectorAll('button[data-gesto="mais-da-modificacao"]').length;
      return {topo: Math.round(fila.top), visivel, botoes,
              dentro: r.left >= 0 && r.right <= window.innerWidth
                      && r.bottom <= window.innerHeight};
    }"""
    antes = _no_chrome(SETE, vista, medida)
    assert not antes["visivel"], "o menu só abre com o clique no ⋮"
    a = _no_chrome(SETE, vista, medida, antes=_CLICA_O_MAIS)
    assert a["visivel"] and a["botoes"] == 3 and a["dentro"], a
    assert a["topo"] == antes["topo"], (a, antes)


def test_o_configurar_do_lancador_traz_a_pasta_o_perfil_por_jogo_e_guardar() -> None:
    """O `#lanc-conf` do desenho aprovado: o que o produto de 18/10 perdeu e o desenho tem."""
    janela = _janela(_ler(SETE), "lanc-conf")
    assert "Escolher o arquivo…" in janela and "Cada jogo ganha o seu perfil" in janela
    assert "<span>Pastas dos jogos</span>" in janela and "<code>~/Jogos/" in janela, (
        "o desenho de 18/10 diz «Pastas dos jogos» com a pasta, não «Jogos»")
    rodape = janela.split('class="tn-rod"')[1]
    assert "Cancelar" in rodape and "Guardar" in rodape and ">Fechar</a>" not in rodape


def test_a_opcao_de_jogos_da_janela_generica_leva_o_rotulo_e_as_caixas() -> None:
    """O exemplo da página não tem a opção de jogos; o desenho dela não pode perder o rótulo."""
    import desenho_da_experimental as exp

    opcao = exp.OpcaoDaJanela("x", "jg", "Os jogos dela", "jogos", ["a"], (), "Jogos",
                              jogos=(("a", "Jogo A"), ("b", "Jogo B")))
    html = exp.modificacao_miolo_html("X", [opcao])
    assert "Os jogos dela" in html and html.count('type="checkbox"') == 2
    assert html.count(" checked") == 1
