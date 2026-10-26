"""O-CODIGO-SEM-NARRADOR-01: o código e a prosa do produto não têm narrador.

Docstring e documento falam do que o código faz e do porquê técnico. Não dizem quem
conduziu o trabalho, não chamam o usuário de «ela» e não contam a conversa em que a decisão
nasceu. Três réguas, e todas mordem:

1. nenhum nome de arquivo versionado leva a palavra «dela»;
2. nenhuma colocação de narrador ou de processo volta a texto versionado;
3. as regras do ``scripts/neutralizar-o-texto.py`` já não acham nada para trocar.

A quarta, a fala citada em comentário, saiu com a D-2610-O-CODIGO-NAO-TEM-COMENTARIO: o código
não tem comentário, e o portão ``codigo-sem-comentario`` reprova qualquer um.
"""

from __future__ import annotations

import functools
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "neutralizar-o-texto.py"

_QUEM = "quem " + "coorden" + "a"
_COORD = "coorden" + "ador"
_DUVIDA = "cét" + "ico"
_SUB = "sub" + "agente"
_WT = "work" + "tree de " + "agente"
_REL = "relatório" + r"s? d[eo]s? " + "agentes?"
_EU = "EU TINHA " + "(?:MEDIDO|ESCRITO)"
_ME = "me " + "corrigiu"
_LEG = "LEGENDA DO " + "MOCKUP"

NARRADOR = re.compile(
    rf"\b[Qq]{_QUEM[1:]}\b|\b[Cc]{_COORD[1:]}(?:a|es)?\b|\b[Cc]{_DUVIDA[1:]}s?\b"
    rf"|\b[Ss]{_SUB[1:]}s?\b|\b[Ww]{_WT[1:]}s?|\b{_REL}|{_EU}|\b{_ME}\b|{_LEG}"
    r"|\(mockup \d{2}/"
)

_ISCAS = (
    _QUEM[1:],
    _COORD[1:],
    _DUVIDA[1:],
    _SUB[1:],
    _WT[1:],
    "relatório",
    "EU TINHA ",
    _ME,
    _LEG,
    "(mockup ",
)

FORA = (
    "docs/process/",
    "src/hefesto_dualsense4unix/interface/paginas/",
    "docs/data/decisoes-de-produto.csv",
    "docs/data/mapa-controles.csv",
    "docs/data/paridade-gtk-html.csv",
    "docs/specs.html",
    "docs/usage/assets/CONFERIDO-EM.txt",
    "scripts/neutralizar-o-texto.py",
    "scripts/neutralizar-os-nomes.py",
    "tests/unit/test_o_codigo_nao_tem_narrador.py",
    "tests/unit/test_check_autoria.py",
    "tests/unit/test_anonimato_workflow_fail_closed.py",
    "scripts/check_texto_publico.py",
)

@functools.cache
def _versionados_em_cache() -> tuple[str, ...]:
    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    if saida.returncode != 0 or not saida.stdout.strip():
        pytest.skip("sem git nesta árvore: a lista de arquivos versionados não existe")
    return tuple(linha for linha in saida.stdout.split("\n") if linha)


def _versionados() -> list[str]:
    return list(_versionados_em_cache())


@functools.cache
def _texto_de_todos() -> dict[str, str]:
    """O texto dos versionados lido como UTF-8, UMA vez para as duas réguas de texto."""
    textos: dict[str, str] = {}
    for caminho in _versionados():
        try:
            textos[caminho] = (RAIZ / caminho).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return textos


def nomes_com_dela(caminhos: list[str]) -> list[str]:
    """Os caminhos em que algum nome de arquivo ou de pasta tem a palavra «dela»."""
    achados = []
    for caminho in caminhos:
        pedacos = re.split(r"[^A-Za-zÀ-ÿ]+", caminho)
        if "dela" in [p.lower() for p in pedacos]:
            achados.append(caminho)
    return achados


def achados_de_narrador(textos: dict[str, str]) -> list[tuple[str, str]]:
    """Cada ``(arquivo, trecho)`` com uma colocação de narrador, fora das isenções."""
    achados = []
    for caminho, texto in textos.items():
        if caminho.startswith(FORA) or not any(isca in texto for isca in _ISCAS):
            continue
        for achado in NARRADOR.finditer(texto):
            achados.append((caminho, achado.group(0)))
    return achados


def test_nenhum_nome_versionado_leva_a_palavra_dela() -> None:
    assert nomes_com_dela(_versionados()) == []


def test_o_vocabulario_de_narrador_nao_volta_ao_texto_versionado() -> None:
    achados = achados_de_narrador(_texto_de_todos())
    assert achados == [], (
        "narrador ou vocabulário de processo em texto versionado (diga o porquê técnico, "
        f"não quem conduziu): {achados[:8]}"
    )


def test_as_regras_do_script_nao_acham_mais_nada_para_trocar() -> None:
    if not SCRIPT.exists():
        pytest.skip("o script não veio para esta árvore")
    corrida = subprocess.run(
        [sys.executable, str(SCRIPT), "--conferir"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert corrida.returncode == 0, (
        "o «dela» que aponta para a pessoa voltou: rode `scripts/neutralizar-o-texto.py "
        f"--aplicar`. Saída: {corrida.stdout.strip()[-300:]}"
    )


def _carregar_o_script() -> Any:
    especificacao = importlib.util.spec_from_file_location("neutralizar_o_texto", SCRIPT)
    assert especificacao and especificacao.loader
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


class TestMorde:
    """A régua só vale se reprova a volta: cada caso devolve o defeito e vê o vermelho."""

    def test_o_narrador_devolvido_a_um_comentario_e_achado(self) -> None:
        limpo = {"src/x.py": "# a cura vive aqui porque o rádio reinicia\n"}
        assert achados_de_narrador(limpo) == []
        medido = _EU.replace("(?:MEDIDO|ESCRITO)", "MEDIDO")
        narrado = {"src/x.py": f"# {medido} o contrário; {_QUEM} decidiu\n"}
        assert {t for _, t in achados_de_narrador(narrado)} == {medido, _QUEM}

    @pytest.mark.parametrize(
        "frase",
        [
            _QUEM,
            "Quem " + "coordena",
            _COORD,
            "Coorden" + "adores",
            _DUVIDA,
            _SUB + "s",
            _WT,
            "relatório" + "s dos agentes",
            "EU TINHA " + "ESCRITO",
            _ME,
            _LEG,
            "(mockup " + "12/",
        ],
    )
    def test_cada_alternativa_do_narrador_tem_a_sua_isca(self, frase: str) -> None:
        """A isca é só um atalho: toda alternativa de ``NARRADOR`` passa por ela e é achada."""
        assert [t for _, t in achados_de_narrador({"src/x.py": f"# {frase} aqui\n"})] != []

    def test_o_arquivo_sem_isca_nao_entra_na_expressao(self) -> None:
        limpo = {"src/x.py": "# a cura vive aqui porque o rádio reinicia\n" * 50}
        assert achados_de_narrador(limpo) == []

    def test_a_isencao_vale_so_para_o_arquivo_isento(self) -> None:
        texto = {"docs/process/x.md": _QUEM, "src/y.py": _QUEM}
        assert achados_de_narrador(texto) == [("src/y.py", _QUEM)]

    def test_o_agente_do_bluez_nao_e_narrador(self) -> None:
        texto = {"src/a.py": "# o agente de pareamento do BlueZ responde ao RequestConfirmation\n"}
        assert achados_de_narrador(texto) == []

    def test_o_nome_com_dela_e_achado(self) -> None:
        assert nomes_com_dela(["tests/unit/test_a_regra_dela.py"]) == [
            "tests/unit/test_a_regra_dela.py"
        ]
        assert nomes_com_dela(["tests/unit/test_o_modelo_de_delaware.py"]) == []

    def test_o_script_troca_o_dela_que_aponta_para_a_pessoa(self) -> None:
        if not SCRIPT.exists():
            pytest.skip("o script não veio para esta árvore")
        modulo = _carregar_o_script()
        troca = modulo.reescrever_prosa("# a ordem dela de 19/09 manda")
        assert troca == "# a ordem de 19/09 manda"
        assert "dela" not in modulo.reescrever_prosa("# a máquina dela não tem rádio")
        gramatical = "# a função devolve o valor dela mesma"
        assert modulo.reescrever_prosa(gramatical) == gramatical


def test_o_script_acha_o_dela_em_comentario_e_em_docstring_e_deixa_o_codigo() -> None:
    """O atalho do script (texto sem «dela» nem se examina) não pode esconder o que ele troca."""
    if not SCRIPT.exists():
        pytest.skip("o script não veio para esta árvore")
    modulo = _carregar_o_script()
    dela = "de" + "la"
    fonte = (
        f'"""A decisão {dela} de 19/09 manda."""\n\n\n'
        "def f() -> str:\n"
        f'    """A ordem {dela} de 19/09 manda."""\n'
        f"    # a ordem {dela} de 19/09 manda\n"
        f'    janela = "a ordem {dela} de 19/09"\n'
        "    return janela\n"
    )
    novo = modulo.reescrever_arquivo(fonte, "py")
    assert novo.count(dela) == 1, novo
    assert f'janela = "a ordem {dela} de 19/09"' in novo
    sem = "def g() -> int:\n    # a janela abre pela tela\n    return 1\n"
    assert modulo.reescrever_arquivo(sem, "py") == sem


def test_o_trabalho_de_um_arquivo_diz_se_ha_o_que_trocar(tmp_path: Path) -> None:
    if not SCRIPT.exists():
        pytest.skip("o script não veio para esta árvore")
    modulo = _carregar_o_script()
    modulo.RAIZ = tmp_path
    dela = "de" + "la"
    (tmp_path / "sujo.py").write_text(f"# a ordem {dela} de 19/09 manda\n", encoding="utf-8")
    (tmp_path / "limpo.py").write_text("# a ordem de 19/09 manda\n", encoding="utf-8")
    assert modulo._trabalho_de((("sujo.py", "py"), False))[1] == "# a ordem de 19/09 manda\n"
    assert modulo._trabalho_de((("limpo.py", "py"), False))[1] is None
    assert modulo._trabalho_de((("sumiu.py", "py"), False))[1] is None


def test_o_comentario_de_marcacao_numa_f_string_conta_em_todo_python() -> None:
    """Do 3.12 em diante, cada pedaço de uma f-string tem a posição exata, e um comentário com
    ``{CAMPO}`` no meio cruzava dois pedaços e escapava; no 3.10 e no 3.11, não. O CI roda os três:
    a régua tem de dar a mesma resposta em todos (o da aba 08 só reprovava no 3.10 e no 3.11)."""
    spec = importlib.util.spec_from_file_location("neutralizar_o_texto", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    fonte = 'X = 1\nMIOLO = f"""\n<div>\n<!-- o texto\n     com {X} no meio -->\n</div>\n"""\n'
    comentario = fonte.index("<!--"), fonte.index("-->") + 3
    assert any(a <= comentario[0] and comentario[1] <= b for a, b in modulo._spans_py(fonte))
