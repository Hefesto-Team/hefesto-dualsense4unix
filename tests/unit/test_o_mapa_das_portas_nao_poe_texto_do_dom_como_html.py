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

import pytest

from hefesto_dualsense4unix.interface import pagina_do_mapa as gerador


@pytest.fixture(scope="module")
def pagina() -> str:
    return gerador.pagina()


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
