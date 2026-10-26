"""As réguas lêem o HTML pelo `html.parser`, nunca por regex de tag (OS-ALERTAS-DO-CODEQL-ZERAM-01).

O CodeQL abriu `py/bad-tag-filter` em onze réguas desta casa: a regex de `<script>` não via
`</script >`, nem `</SCRIPT>` sem a bandeira, nem o comentário com quebra de linha ou fechado em
`--!>`. A cura é UMA leitura só, em `frases_que_ela_baniu` (`trechos_mudos`, `sem_o_mudo`,
`roteiros_de`), que pergunta ao parser da biblioteca onde o navegador fecha cada coisa.

A MORDIDA: devolva a regex velha a qualquer um dos arquivos da lista (ou tire o parser de
`frases_que_ela_baniu`) e uma das duas metades reprova — a dos casos, ou a do fonte.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    roteiros_de,
    sem_o_mudo,
    trechos_mudos,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]

CASOS = {
    "fecho com espaço": ("a<script>x</script >b", ["<script>x</script >"]),
    "fecho com quebra": ("a<script>x</script\n>b", ["<script>x</script\n>"]),
    "maiúscula": ("a<SCRIPT type=x>x</SCRIPT>b", ["<SCRIPT type=x>x</SCRIPT>"]),
    "comentário com quebra": ("a<!-- c\n d -->b", ["<!-- c\n d -->"]),
    "comentário que fecha em --!>": ("a<!--x--!>b", ["<!--x--!>"]),
    "comentário vazio": ("a<!---->b", ["<!---->"]),
    "estilo com espaço no fecho": ("<style media=x>b</style >c", ["<style media=x>b</style >"]),
    "o fecho dentro de uma string do script": (
        "<p>ok</p><script>var s='</scr'+'ipt>';</script>z",
        ["<script>var s='</scr'+'ipt>';</script>"],
    ),
    "o título e a caixa de texto não são mudos": (
        "<title>A</title><textarea>B</textarea><svg><title>C</title></svg>", []),
    "script sem fecho vai até o fim": ("a<script>solto", ["<script>solto"]),
    "comentário dentro do script é do script": (
        "<script>/* <!-- */ x</script><!-- y -->",
        ["<script>/* <!-- */ x</script>", "<!-- y -->"],
    ),
    "script dentro do comentário é do comentário": (
        "<!-- <script>x</script> -->z",
        ["<!-- <script>x</script> -->"],
    ),
}


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_o_parser_acha_onde_o_navegador_fecha(nome: str) -> None:
    pagina, esperado = CASOS[nome]
    assert [pagina[a:b] for a, b in trechos_mudos(pagina)] == esperado


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_apagar_o_mudo_nao_move_nenhuma_letra(nome: str) -> None:
    """O tamanho e as quebras de linha ficam: a linha que a régua cita é a da página."""
    pagina = CASOS[nome][0]
    limpo = sem_o_mudo(pagina)
    assert len(limpo) == len(pagina)
    assert [i for i, c in enumerate(limpo) if c == "\n"] == [
        i for i, c in enumerate(pagina) if c == "\n"
    ]
    for a, b in trechos_mudos(pagina):
        assert not limpo[a:b].strip(), f"o trecho {pagina[a:b]!r} sobrou na leitura"


def test_o_resto_da_pagina_fica_intacto() -> None:
    pagina = '<p class="a">oi</p><script>x</script ><p>tchau</p>'
    assert sem_o_mudo(pagina).replace(" ", "") == '<pclass="a">oi</p><p>tchau</p>'


def test_os_roteiros_vem_com_os_atributos() -> None:
    achados = roteiros_de(
        '<script>a</script ><SCRIPT src="x" type="text/y">b</SCRIPT><script id="z">c</script>'
    )
    assert achados == [
        ({}, "a"),
        ({"src": "x", "type": "text/y"}, "b"),
        ({"id": "z"}, "c"),
    ]


def test_o_roteiro_nao_inclui_o_que_esta_em_comentario() -> None:
    assert roteiros_de("<!-- <script>fora</script> --><script>dentro</script>") == [({}, "dentro")]


LIDOS_PELO_PARSER = (
    "scripts/check_a_conferencia.py",
    "scripts/check_a_maiuscula_decorativa.py",
    "scripts/check_a_tela_nao_confessa.py",
    "src/hefesto_dualsense4unix/interface/aba10.py",
    "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py",
    "tests/unit/test_a_aba_lancadores_diz_a_verdade.py",
    "tests/unit/test_a_bancada_fala_a_tela_da_onda_6a.py",
    "tests/unit/test_a_vibracao_nao_manda_num_botao_que_nao_existe.py",
    "tests/unit/test_o_mapa_do_controle_pisca_e_segue_a_troca.py",
    "tests/unit/test_o_rotulo_da_entrada_tem_um_dono.py",
    "tests/unit/test_os_mapas_do_todo.py",
)


def _regex_de_script() -> list[str]:
    """`arquivo:linha` de cada `re.<função>("…<script…")` que sobrou nos arquivos da lista."""
    achados: list[str] = []
    for caminho in LIDOS_PELO_PARSER:
        arvore = ast.parse((RAIZ / caminho).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "re"
                and no.args
            ):
                continue
            padrao = no.args[0]
            if (
                isinstance(padrao, ast.Constant)
                and isinstance(padrao.value, str)
                and "script" in padrao.value.lower()
                and "<" in padrao.value
            ):
                achados.append(f"{caminho}:{no.lineno}")
    return achados


def test_nenhuma_regua_da_lista_le_script_por_regex() -> None:
    """Prova da D-2310-O-CODEQL-ZERA-LENDO-O-HTML-PELO-PARSER."""
    assert _regex_de_script() == [], (
        "uma régua voltou a ler `<script>` por regex — o CodeQL acusa `py/bad-tag-filter`; "
        "use `trechos_mudos`, `sem_o_mudo` ou `roteiros_de` de `frases_que_ela_baniu`"
    )


def test_a_lista_de_arquivos_existe() -> None:
    """Régua que não acha o arquivo não mede o arquivo."""
    faltam = [c for c in LIDOS_PELO_PARSER if not (RAIZ / c).is_file()]
    assert faltam == []
