"""O desenho de 19/10/2026 da Perfis (10) e da Experimental (07), para ela escolher.

Cinco sprints, só o desenho: o editor de Perfis (o estilo guardado, o nome Freestyle, o renomear),
os eventos do perfil («Meu comando»), a coluna do ajuste próprio com a ativação e os analógicos,
e a janela genérica das extensões (a janela do servidor do acessório saiu da 07 em 19/10/2026,
com o adulto, para a extensão que o serve). As variantes não escolhidas moram em
`mockup/variantes/` e nunca entram na página publicada nem no produto; a que a recomendação
escolhe é o próprio `mockup/`.

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
    sobra = {p.stem for p in VARIANTES.glob("10-*.html")} - set(esperadas)
    assert not sobra, f"variante que o gerador não produz mais ficou no disco: {sorted(sobra)}"


def test_a_variante_nunca_entra_na_pagina_publicada() -> None:
    """`mockup/variantes/` não é uma das dez páginas, e o publicado não a carrega."""
    from hefesto_dualsense4unix.interface import onde

    assert not [p for p in onde.paginas() if "variantes" in p.parts]
    publicado = _ler(onde.pagina("10-perfis.html", publicado=True))
    assert "Nome reservado" not in publicado and "Freestyle é o botão" not in publicado


# ---------------------------------------------------------------------------------------------
# Perfis 2 · OS-EVENTOS-DO-PERFIL-ENTRAM-PELO-QUE-O-DAEMON-JA-SABE-01
# ---------------------------------------------------------------------------------------------

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


def test_a_variante_a_dos_eventos_poe_o_comando_ao_lado_do_momento() -> None:
    doc = _ler(VARIANTES / "10-eventos-A-comando-na-mesma-linha.html")
    corpo = _sem_estilo_nem_script(doc)
    quando = re.search(r'<div class="campo so-eventos.*?</div>', corpo, re.S)
    assert quando is not None and 'class="ev-cmd"' in quando.group(0)
    assert 'class="campo so-comando"' not in corpo


@sem_chrome
def test_a_variante_a_dos_eventos_corta_o_comando_a_940() -> None:
    """Por que a recomendada é a linha própria: a 940 o campo ao lado fica estreito demais."""
    m = _no_chrome(VARIANTES / "10-eventos-A-comando-na-mesma-linha.html", (940, 809), """() => {
      const c = document.querySelector('.ev-cmd'); return c.getBoundingClientRect().width;
    }""", antes=_ESCOLHE_EVENTO % "meu_comando")
    assert m < 110, m


# ---------------------------------------------------------------------------------------------
# Perfis 3 · AS-TRES-SECOES-DA-ACESSIBILIDADE-GANHAM-IPC-E-O-TOQUE-SEGUE-A-MAO-01
# ---------------------------------------------------------------------------------------------

VARIANTE_ACESSIBILIDADE_B = VARIANTES / "10-acessibilidade-B-uma-celula.html"
_SECOES_DE_UMA_LINHA = ("leds", "triggers", "rumble", "speaker", "mic", "sensores", "mascara",
                        "movimento", "ativacao", "analogicos")  # (noqa-acento) identificador ASCII
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
    assert ".gd-pecas{width:271px}" in html and ".gd-pecas .gls{gap:5px}" in html


def test_a_variante_b_junta_a_ativacao_e_os_analogicos_numa_celula() -> None:
    doc = _ler(VARIANTE_ACESSIBILIDADE_B)
    secoes = _secoes_da_primeira_linha(doc)
    assert secoes == [*_SECOES_DE_UMA_LINHA[:8], "acessibilidade"], secoes
    assert "analogicos" not in re.search(r'<td class="gd-pecas">.*?</td>', doc, re.S).group(0)
    assert ".gd-pecas .gls{gap:6px}" in doc


def _celula(secao: str, ponto: str) -> str:
    return (f'<span class="gc"><span class="gr" data-hef-secao="{secao}"><svg></svg></span>'
            f'<span class="gp{ponto}" data-hef="guarda.proprio"></span></span>')


def test_o_ponto_da_celula_juntada_acende_se_qualquer_das_duas_guarda() -> None:
    """A junção da B: o ponto é a soma dos dois, e a célula velha dos analógicos some."""
    import aba10

    def linha(a: str, b: str) -> str:
        ativa = _celula("ativacao", a)  # (noqa-acento) identificador ASCII
        analoga = _celula("analogicos", b)
        return f'<td class="gd-pecas">{ativa}{analoga}</td>'

    pagina = ".gd-pecas .gls{gap:5px}" + "".join(linha(a, b) for a, b in
                                                 [("", ""), (" on", ""), ("", " on")])
    saida = aba10._juntar_ativacao_e_analogicos(pagina)
    pontos = re.findall(r'<span class="gp( on)?"', saida)
    assert pontos == ["", " on", " on"], pontos
    assert "analogicos" not in saida and saida.count('data-hef-secao="acessibilidade"') == 3



@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
@pytest.mark.parametrize("arquivo,celulas", [(DEZ, 10), (VARIANTE_ACESSIBILIDADE_B, 9)],
                         ids=["A-recomendada", "B-uma-celula"])
def test_a_fileira_das_secoes_cabe_na_celula_em_toda_vista(
        vista: tuple[int, int], arquivo: pathlib.Path, celulas: int) -> None:
    """A fileira inteira fica dentro da célula do Status (a 940 px a de dez passava 16 px)."""
    linhas = _no_chrome(arquivo, vista, _MEDE_A_FILEIRA)
    assert linhas and all(ln["celulas"] == celulas for ln in linhas), linhas
    assert all(ln["sobra"] >= 0 for ln in linhas), linhas


def test_a_07_nao_guarda_variante_nem_gerador_de_variante() -> None:
    """O usuário escolheu as três da 07 em 19/10: as não escolhidas saem do disco e do gerador."""
    import aba07

    assert not sorted(p.name for p in VARIANTES.glob("07-*.html"))
    assert not hasattr(aba07, "variantes")


# ---------------------------------------------------------------------------------------------
# Perfis 5 · AS-JANELAS-DA-07-ALCANCAM-O-DESENHO-APROVADO-01
# ---------------------------------------------------------------------------------------------

_ID = "modificacao"  # (noqa-acento) identificador ASCII da janela
_ABRE_A_GENERICA = f"(function(){{location.hash='#{_ID}';}})()"
_CLICA_O_MAIS = ("(function(){const b = document.querySelector('.ext-mais');"
                 " b.focus(); b.click();})()")


def _janela(html: str, ident: str) -> str:
    sem = _sem_estilo_nem_script(html)
    inicio = sem.index(f'id="{ident}"')
    # A janela vai até a seguinte; a última da página, até o fim dela.
    fim = sem.find('<div class="tela-nova"', inicio + 1)
    return sem[inicio:fim if fim > 0 else len(sem)]


def test_a_janela_generica_da_extensao_tem_um_cartao_por_grupo_e_cancelar_guardar() -> None:
    """A (recomendada): um cartão por grupo, e não as abas de antes."""
    janela = _janela(_ler(SETE), _ID)
    titulos = re.findall(r'<span class="ac-tit">([^<]*)</span>', janela)
    assert titulos == ["Geral", "Luz e vibração", "Avançado"], titulos
    assert "mg-abas" not in janela and 'type="radio"' not in janela
    assert janela.count('<div class="ky-linha">') == 6
    assert '<a class="btn" href="#">Cancelar</a>' in janela
    assert '<a class="btn roxo" href="#" data-gesto="guardar-modificacao"' in janela
    assert ">Fechar</a>" not in janela.split('class="tn-rod"')[1]


@sem_chrome
@pytest.mark.parametrize("vista", VISTAS, ids=lambda v: str(v[0]))
def test_a_janela_generica_da_extensao_cabe_sem_rolagem_nem_corte(vista: tuple[int, int]) -> None:
    medida = """() => {
      const cx = document.querySelector('@ .tn-cx'), r = cx.getBoundingClientRect();
      const corpo = document.querySelector('@ .tn-corpo');
      const d = document.documentElement;
      const corte = [...document.querySelectorAll('@ .ky-ctrl, @ .ky-linha')]
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
