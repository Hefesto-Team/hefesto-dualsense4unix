"""Os mapas do rádio e das portas perdem o «?» e ganham a base comum.

A-ABA-MAPAS-DO-RADIO-E-DAS-PORTAS-DO-TODO-01. Os dois desenhos foram publicados em 16/10/2026: a
régua lê os dois arquivos de ``mockup/``, a página que o gerador das portas monta
(``pagina_do_mapa.pagina()``) e a cópia que o produto serve.

Mordidas (cada uma arrancada, vista reprovar e devolvida):

* devolver o ``<span class="ajuda">`` ao espectro do rádio ou à receita das portas:
  :func:`test_nenhum_dos_dois_mapas_tem_o_interrogacao`;
* tirar a base comum de um dos dois, ou alterar uma letra dela:
  :func:`test_os_dois_mapas_levam_a_base_comum_uma_vez_e_igual_ao_arquivo`;
* devolver o ``title`` longo de um botão: :func:`test_os_botoes_dizem_a_dica_curta_e_nao_o_title`;
* pôr de volta um menu do botão direito na página das portas:
  :func:`test_o_menu_do_botao_direito_e_so_o_da_base`;
* a receita que deixa de carregar a razão no título (ou volta a montar o «?» no JS):
  :func:`test_no_sugestoes_o_titulo_do_movimento_carrega_a_razao`.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import arranjo_desta_maquina, pagina_do_mapa
from hefesto_dualsense4unix.interface.frases_que_ela_baniu import roteiros_de

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
DESENHOS = {
    "mapa-do-radio.html": RAIZ / "mockup/mapa-do-radio.html",
    "mapa-das-portas.html": RAIZ / "mockup/mapa-das-portas.html",
}

BASE_CSS = (INTERFACE / "base-comum.css").read_text(encoding="utf-8")
BASE_JS = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")

O_INTERROGACAO = re.compile(r"""<span\b[^>]*\bclass=["']ajuda\b""")

DICAS = {
    "mapa-do-radio.html": {
        "b-conectar": "Pareia um controle ou fone novo",
        "b-equilibrar": "Move um controle por vez",
        "b-mapear": "Desenha as entradas do seu computador, face por face",
        "b-uma-a-uma": "Você pluga um aparelho e ele aprende a entrada",
        "b-examinar": "Refaz o exame das entradas, da energia e do rádio",
    },
}
DICAS["mapa-das-portas.html"] = DICAS["pagina_do_mapa.pagina()"] = {
    "reexaminar": "Lê de novo e mostra o que mudou de lugar",
}

RECEITA_COM_O_INTERROGACAO = (
    '                 return "<li><div><h4>" + m.titulo + \'<span class="ajuda" tabindex="0">?'
    '<span class="dica">\'\n'
)


def _paginas() -> dict[str, str]:
    """Os dois desenhos como estão no mockup, mais a página das portas como o gerador a monta."""
    paginas = {nome: caminho.read_text(encoding="utf-8") for nome, caminho in DESENHOS.items()}
    paginas["pagina_do_mapa.pagina()"] = pagina_do_mapa.pagina()
    return paginas


PAGINAS = _paginas()


def _tag_do_id(doc: str, ident: str) -> str:
    achou = re.search(rf"""<(?:a|button)\b[^>]*\bid="{ident}"[^>]*>""", doc)
    assert achou, f"não achei o elemento `#{ident}`"
    return achou.group(0)


def test_o_mockup_das_portas_e_o_que_o_gerador_escreve() -> None:
    """O arquivo de ``mockup/`` é a saída do gerador (``onde.gravar`` tira o espaço do fim)."""
    gerado = "\n".join(linha.rstrip() for linha in pagina_do_mapa.pagina().split("\n"))
    assert DESENHOS["mapa-das-portas.html"].read_text(encoding="utf-8") == gerado, (
        "mockup/mapa-das-portas.html não é o que `pagina_do_mapa` escreve: rode o gerador")


def test_o_detector_do_interrogacao_reconhece_o_que_a_sprint_cura() -> None:
    """O detector acha o ``span.ajuda`` das duas casas e deixa passar o ``p.ajuda`` da bandeja."""
    assert O_INTERROGACAO.search('<span class="ajuda" role="img" title="x">')
    assert O_INTERROGACAO.search("""'<span class="ajuda" tabindex="0">?<span class="dica">'""")
    assert not O_INTERROGACAO.search('<p class="ajuda" id="ajuda-bandeja"></p>')
    assert O_INTERROGACAO.search(RECEITA_COM_O_INTERROGACAO), (
        "a peça de antes da edição já não é a que carrega o «?»")
    assert not O_INTERROGACAO.search(pagina_do_mapa.RECEITA_COM_A_DICA_NO_TITULO)


@pytest.mark.parametrize("nome", list(PAGINAS))
def test_nenhum_dos_dois_mapas_tem_o_interrogacao(nome: str) -> None:
    """MORDIDA: devolva o ``<span class="ajuda">`` ao espectro (rádio) ou à receita (portas).

    Prova da D-1610-OS-MAPAS-FALAM-PELA-DICA-CURTA.
    """
    achados = O_INTERROGACAO.findall(PAGINAS[nome])
    assert not achados, f"{nome}: ainda monta o «?» ({len(achados)} vez(es))"


@pytest.mark.parametrize("nome", list(PAGINAS))
def test_os_dois_mapas_levam_a_base_comum_uma_vez_e_igual_ao_arquivo(nome: str) -> None:
    """MORDIDA: tire a base de um mapa, ou mude uma letra dela, e esta régua reprova."""
    doc = PAGINAS[nome]
    assert doc.count('<style id="base-comum">') == 1, f"{nome}: o <style> da base"
    assert doc.count('<script id="base-comum">') == 1, f"{nome}: o <script> da base"
    assert f'<style id="base-comum">\n{BASE_CSS}</style>' in doc, f"{nome}: CSS diferente"
    assert f'<script id="base-comum">\n{BASE_JS}</script>' in doc, f"{nome}: JS diferente"


@pytest.mark.parametrize("nome", list(DICAS))
def test_os_botoes_dizem_a_dica_curta_e_nao_o_title(nome: str) -> None:
    """MORDIDA: devolva o ``title`` longo de um botão: ele deixa de ter o ``data-dica`` curto."""
    doc = PAGINAS[nome]
    for ident, dica in DICAS[nome].items():
        tag = _tag_do_id(doc, ident)
        assert f'data-dica="{dica}"' in tag, f"{nome}: `#{ident}` perdeu a dica «{dica}»: {tag}"
        assert " title=" not in tag, f"{nome}: `#{ident}` ainda tem `title`: {tag}"


def test_o_espectro_do_radio_diz_a_dica_em_quem_esta_no_ar() -> None:
    """O «?» sai do espectro e a dica fica na própria frase, que é o que a pessoa lê."""
    doc = PAGINAS["mapa-do-radio.html"]
    assert ('<span data-dica="Wi-Fi e mouse sem fio dividem os 2,4 GHz com o Bluetooth">'
            "Quem está no ar</span>") in doc


def test_o_voltar_e_o_mapa_do_radio_dizem_a_dica_curta() -> None:
    portas = PAGINAS["pagina_do_mapa.pagina()"]
    assert re.search(r'<a href="08-conexoes.html" data-dica="Volta para a aba Conexões"', portas)
    assert 'title="Volta para a aba' not in portas
    radio = PAGINAS["mapa-do-radio.html"]
    assert re.search(r'<a class="mapa so-icone" href="mapa-das-portas.html"\s+'
                     r'data-dica="Abre o mapa das entradas"', radio)


@pytest.mark.parametrize("nome", ["mapa-do-radio.html", "pagina_do_mapa.pagina()"])
def test_nenhum_title_estatico_longo_ou_com_travessao(nome: str) -> None:
    """Dica longa é texto demais; o ``title`` que sobra é curto e sem o «—» do nome do botão."""
    for titulo in re.findall(r"""\stitle="([^"']*)\"""", PAGINAS[nome]):
        assert len(titulo) <= 60 and "—" not in titulo, f"{nome}: `title` longo: {titulo!r}"


def test_o_menu_do_botao_direito_e_so_o_da_base() -> None:
    """A página das portas não monta menu seu: o ``contextmenu`` mora só na base comum.

    MORDIDA: ponha um ``addEventListener("contextmenu", …)`` de volta na página e ela reprova.
    """
    na_base = len(re.findall(r"""['"]contextmenu['"]""", BASE_JS))
    assert na_base >= 1, "a base comum perdeu o menu do botão direito"
    for nome in ("mapa-do-radio.html", "pagina_do_mapa.pagina()"):
        total = len(re.findall(r"""['"]contextmenu['"]""", PAGINAS[nome]))
        assert total == na_base, f"{nome}: {total - na_base} menu(s) do botão direito além da base"


def test_o_sugestoes_perde_o_verde_e_a_caixa_alta() -> None:
    """O desenho do todo: Sugestões é um modo como os outros, e a face só tem a 1ª maiúscula."""
    doc = PAGINAS["pagina_do_mapa.pagina()"]
    assert ".modo.destaque[" not in doc, "o modo Sugestões voltou a ter regra de cor própria"
    assert re.search(r"\.painel > p\.chamada \.grande \{ color: var\(--color-ink\); \}", doc)
    assert "Clique em <b style=" not in doc, "o convite a clicar em Sugestões voltou verde"
    face = re.search(r"\.face-cab h3 \{[^}]*\}", doc)
    assert face and "uppercase" not in face.group(0), face and face.group(0)
    assert "<h1>Mapa das <em>conexões</em></h1>" in doc


def test_no_sugestoes_o_titulo_do_movimento_carrega_a_razao() -> None:
    """A receita monta o ``<h4>`` com a primeira razão em ``data-dica`` e nenhum ``span`` de «?».

    MORDIDA: troque a peça da receita pela antiga e a régua do «?» reprova junto com esta.
    """
    doc = PAGINAS["pagina_do_mapa.pagina()"]
    assert pagina_do_mapa.RECEITA_COM_A_DICA_NO_TITULO in doc
    assert RECEITA_COM_O_INTERROGACAO not in doc
    assert '<h4 data-dica="' in pagina_do_mapa.RECEITA_COM_A_DICA_NO_TITULO
    assert 'data-dica="Clique e marque a entrada onde ele está"' in doc


def test_as_edicoes_dos_mapas_estao_publicadas_e_a_copia_do_produto_e_a_pagina() -> None:
    """As edições entraram em ``EDICOES`` e a cópia que o produto serve já tem o desenho do todo.

    MORDIDA: ponha uma edição dos mapas de volta em ``EDICOES_ESPERANDO_A_SESSAO_DELA``, ou a
    receita antiga na cópia publicada, e a régua reprova.
    """
    for edicao in pagina_do_mapa.EDICOES_DOS_MAPAS_DO_TODO:
        assert edicao in pagina_do_mapa.EDICOES
        assert edicao not in pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA
    publicada = (INTERFACE / "paginas/mapa-das-portas.html").read_text(encoding="utf-8")
    assert publicada == pagina_do_mapa.pagina(False)
    assert pagina_do_mapa.RECEITA_COM_A_DICA_NO_TITULO in publicada
    assert RECEITA_COM_O_INTERROGACAO not in publicada
    assert publicada.count('<style id="base-comum">') == 1


def _no_webkit_da_bancada(passos: list[str], bancada: pathlib.Path) -> list[object]:
    """Abre num WebKit a página das portas que o GERADOR monta agora, como a régua da 08.

    A página é escrita numa bancada de mentira (``HEFESTO_BANCADA``): quem é medido é o gerador, não
    o arquivo de ``mockup/``, que o primeiro teste abaixo confere ser igual ao que ele escreve.
    """
    from tests.unit import test_o_mapa_das_conexoes_cabe_na_aba as vizinha

    nome = arranjo_desta_maquina.PAGINA
    (bancada / nome).write_text(pagina_do_mapa.pagina(), encoding="utf-8")
    anterior = vizinha.NA_BANCADA
    vizinha.NA_BANCADA = True
    try:
        return vizinha._no_webkit(nome, (1212, 809), passos)
    finally:
        vizinha.NA_BANCADA = anterior


LER_O_SUGESTOES = r"""
(function () {
  const h4 = Array.from(document.querySelectorAll('#painel .receita h4'));
  return JSON.stringify({
    titulos: h4.length,
    com_dica: h4.filter(h => (h.dataset.dica || '').trim() !== '').length,
    dicas: h4.map(h => h.dataset.dica),
    interrogacoes: document.querySelectorAll('#painel .receita .ajuda').length,
    marcacao_na_dica: h4.some(h => /[<>]/.test(h.dataset.dica || '')),
    base: document.querySelectorAll('style#base-comum, script#base-comum').length,
    modos: Array.from(document.querySelectorAll('.modo'))
      .map(b => [b.dataset.modo, b.dataset.dica]),
  });
})()
"""


def test_o_sugestoes_desenha_o_titulo_com_a_dica_e_nenhum_interrogacao(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No WebKit, o Sugestões desenha os títulos com ``data-dica`` e nenhum «?»."""
    from tests.unit import test_o_mapa_das_conexoes_cabe_na_aba as vizinha

    monkeypatch.setenv("HEFESTO_BANCADA", str(tmp_path))
    lidas = _no_webkit_da_bancada([
        arranjo_desta_maquina.js_da_entrega(vizinha._arranjo()),
        vizinha._clicar('.modo[data-modo="ideal"]'), LER_O_SUGESTOES,
    ], tmp_path)
    lido = lidas[2]
    assert isinstance(lido, dict), lido
    assert lido["titulos"] >= 1, f"o Sugestões não desenhou movimento nenhum: {lido}"
    assert lido["com_dica"] == lido["titulos"], f"movimento sem a razão no título: {lido['dicas']}"
    assert lido["interrogacoes"] == 0, "o movimento ainda tem o «?»"
    assert not lido["marcacao_na_dica"], f"a dica leva marcação: {lido['dicas']}"
    assert lido["base"] == 2, "a base comum não entrou uma vez na página"
    assert json.dumps(lido["modos"], ensure_ascii=False).count("null") == 0, lido["modos"]
    assert [m[0] for m in lido["modos"]] == [
        "mesa", "ideal", "mao", "registro"]  # (noqa-acento)


@pytest.mark.parametrize("nome", list(PAGINAS))
def test_o_javascript_de_cada_pagina_compila(nome: str, tmp_path: pathlib.Path) -> None:
    """Um parêntese a mais na receita deixa a página muda: o ``node --check`` pega sem display.

    MORDIDA: um ``)`` a mais na peça da receita (``RECEITA_COM_A_DICA_NO_TITULO``) a reprova.
    """
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("sem node para checar a sintaxe")
    blocos = [corpo for atributos, corpo in roteiros_de(PAGINAS[nome])
              if "src" not in atributos and not (atributos.get("type") or "").startswith("text/")]
    assert blocos, f"{nome}: nenhum <script>"
    for numero, bloco in enumerate(blocos):
        arquivo = tmp_path / f"bloco{numero}.js"
        arquivo.write_text(bloco, encoding="utf-8")
        feito = subprocess.run([node, "--check", str(arquivo)], capture_output=True, text=True,
                               check=False)
        assert feito.returncode == 0, (
            f"{nome}: o <script> {numero} não compila:\n{feito.stderr[:400]}")
