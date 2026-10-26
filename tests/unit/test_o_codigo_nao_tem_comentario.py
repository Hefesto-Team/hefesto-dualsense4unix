"""O código versionado não tem comentário, e o portão barra o novo.

Prova da D-2610-O-CODIGO-NAO-TEM-COMENTARIO: o portão ``scripts/check_codigo_sem_comentario.py``
reprova o comentário nos cinco tipos e deixa a diretiva nua; o removedor
``scripts/tirar-os-comentarios.py`` tira o comentário sem mudar o programa.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carrega(nome: str, arquivo: str) -> ModuleType:
    if nome in sys.modules:
        return sys.modules[nome]
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / arquivo)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


G = _carrega("check_codigo_sem_comentario", "check_codigo_sem_comentario.py")
T = _carrega("tirar_os_comentarios", "tirar-os-comentarios.py")

CERQUILHA = "#"
COMENTARIO_NOVO = {
    "py": ("src/hefesto_dualsense4unix/x.py", f"x = 1  {CERQUILHA} o porquê\n"),
    "sh": ("scripts/x.sh", f"#!/usr/bin/env bash\necho oi  {CERQUILHA} o porquê\n"),
    "html": ("mockup/x.html", "<p>oi</p>\n<!-- o porquê -->\n"),
    "js": ("src/x.js", "const x = 1;\n// o porquê\n"),
    "css": ("src/x.css", "p { color: red; }\n/* o porquê */\n"),
}

DIRETIVAS_ACEITAS = [
    ("py", "src/x.py", "#!/usr/bin/env python3\n"),
    ("py", "src/x.py", "# -*- coding: utf-8 -*-\n"),
    ("py", "src/x.py", "import x  # type: ignore[import-untyped]\n"),
    ("py", "src/x.py", "import x  # noqa: F401\n"),
    ("py", "src/x.py", "def f():  # pragma: no cover\n    pass\n"),
    ("py", "src/x.py", "# ruff: noqa: E501\n"),
    ("py", "src/x.py", "import x  # isort: skip\n"),
    ("py", "src/x.py", "# fmt: off\n"),
    ("py", "src/x.py", "# mypy: ignore-errors\n"),
    ("py", "src/x.py", "# SPDX-License-Identifier: GPL-3.0\n"),
    ("py", "src/x.py", 'x = "nao"  # (noqa-acento)\n'),
    ("py", "tests/unit/x.py", "ISENTOS = {\n    'a',  # sai com: UMA-SPRINT-01\n}\n"),
    ("py", "tests/unit/x.py", "ISENTOS = {\n    'a',  # fica: a razão medida desta entrada\n}\n"),
    ("sh", "scripts/x.sh", "#!/usr/bin/env bash\n# shellcheck disable=SC2034\n"),
    ("sh", "scripts/x.sh", 'echo "nao"  # (noqa-acento)\n'),
    ("js", "src/x.js", "/* eslint-disable */\nconst x = 1;\n"),
    ("js", "src/x.js", "// @ts-check\nconst x = 1;\n"),
    ("css", "src/x.css", "/* SPDX-License-Identifier: GPL-3.0 */\np {}\n"),
    ("html", "src/x.html", "<header><!--LOGO--></header>\n"),
]


@pytest.mark.parametrize("tipo", sorted(COMENTARIO_NOVO))
def test_o_portao_reprova_o_comentario_novo_em_cada_tipo(tipo: str) -> None:
    """Prova da D-2610-O-CODIGO-NAO-TEM-COMENTARIO, nos cinco tipos."""
    rel, texto = COMENTARIO_NOVO[tipo]
    achados = G.achados_do_texto(texto, tipo, rel)
    assert [a.arquivo for a in achados] == [rel], f"{tipo}: o comentário novo passou calado"
    assert "o porquê" in achados[0].texto


@pytest.mark.parametrize(("tipo", "rel", "texto"), DIRETIVAS_ACEITAS)
def test_o_portao_aceita_a_diretiva(tipo: str, rel: str, texto: str) -> None:
    assert G.achados_do_texto(texto, tipo, rel) == [], f"a diretiva reprovou: {texto!r}"


def test_a_marca_da_lista_de_excecao_so_vale_onde_o_leitor_dela_le() -> None:
    texto = "ISENTOS = {\n    'a',  # sai com: UMA-SPRINT-01\n}\n"
    assert G.achados_do_texto(texto, "py", "src/hefesto_dualsense4unix/x.py")


def test_a_diretiva_com_razao_reprova_e_o_removedor_a_deixa_nua() -> None:
    texto = "import x  # noqa: F401 o import registra o plugin\n"
    assert G.achados_do_texto(texto, "py", "src/x.py")
    novo, saiu, ficou = T.limpar(texto, "py", "src/x.py")
    assert novo == "import x  # noqa: F401\n"
    assert (saiu, ficou) == (0, 1)


PY_EM_TODA_POSICAO = '''\
#!/usr/bin/env python3
# o cabeçalho sai
import os  # fim de linha

x = (  # dentro do parêntese
    1,  # o item
    # linha própria no meio
    2,
)
y = 1 + \\
    2  # depois da barra
s = "um # que é texto"
t = 'outro # também'
u = f"{x!r} # f-string {os.sep}"  # e o comentário dela
v = """docstring # fica"""


def f():
    """A docstring fica."""
    # dentro da função
    return s  # volta


# o fim
'''


def test_o_removedor_de_py_mantem_a_arvore_e_o_texto_das_strings() -> None:
    novo, saiu, _ficou = T.limpar(PY_EM_TODA_POSICAO, "py", "src/x.py")
    assert ast.dump(ast.parse(novo)) == ast.dump(ast.parse(PY_EM_TODA_POSICAO))
    assert saiu == 10
    assert G.achados_do_texto(novo, "py", "src/x.py") == []
    for literal in ('"um # que é texto"', "'outro # também'", '"""docstring # fica"""',
                    'f"{x!r} # f-string {os.sep}"'):
        assert literal in novo, f"o removedor mexeu na string {literal}"
    assert "\n\n\n\n" not in novo
    assert not any(linha.strip() == "" and linha for linha in novo.split("\n"))


SH_COM_ARMADILHAS = """\
#!/usr/bin/env bash
# o cabeçalho sai
echo "$#" ${#lista[@]} "${x#prefixo}" '# entre aspas simples'
echo "# entre aspas duplas" $'# entre aspas de dólar'  # o comentário sai
y=a#b
z=$(echo "dentro" # comentário na substituição
)
w=$(( 1 << 2 ))
read -r linha <<<"$y"  # depois do here-string
cat <<'FIM'
# corpo do heredoc fica
FIM
cat <<-FIM
	# corpo com tab fica
	FIM
case "$y" in
  a#b) echo casa ;;  # no case
esac
"""


def test_o_removedor_de_sh_nao_toca_o_que_nao_e_comentario() -> None:
    novo, saiu, _ficou = T.limpar(SH_COM_ARMADILHAS, "sh", "scripts/x.sh")
    assert saiu == 5, novo
    for intacto in ('"$#"', "${#lista[@]}", '"${x#prefixo}"', "'# entre aspas simples'",
                    '"# entre aspas duplas"', "$'# entre aspas de dólar'", "y=a#b",
                    "# corpo do heredoc fica", "\t# corpo com tab fica", "a#b) echo casa ;;"):
        assert intacto in novo, f"o removedor mexeu em {intacto!r}"
    assert "o comentário sai" not in novo and "depois do here-string" not in novo
    assert G.achados_do_texto(novo, "sh", "scripts/x.sh") == []
    T.prova_sh(SH_COM_ARMADILHAS, novo)


JS_COM_ARMADILHAS = """\
const a = "/* não é comentário */";
const b = `// nem este ${a /* este é */}`;
const c = /\\/\\/ regex/.test(a);  // este é
"""


def test_o_portao_le_o_js_pela_lingua() -> None:
    linhas = sorted(a.linha for a in G.achados_do_texto(JS_COM_ARMADILHAS, "js", "src/x.js"))
    assert linhas == [2, 3]


def test_o_portao_le_o_html_com_o_script_e_o_style() -> None:
    texto = ('<p title="<!-- não é -->">oi</p>\n'
             "<script>const s = '<!-- string -->'; // sai\n</script>\n"
             "<style>p::after { content: '/* string */'; } /* sai */</style>\n")
    achados = G.achados_do_texto(texto, "html", "mockup/x.html")
    assert sorted(a.linha for a in achados) == [2, 4]
    assert all("sai" in a.texto for a in achados)


def _o_py_sobrevive(limpar: object) -> bool:
    novo, _saiu, _ficou = limpar(PY_EM_TODA_POSICAO, "py", "src/x.py")  # type: ignore[operator]
    try:
        return ast.dump(ast.parse(novo)) == ast.dump(ast.parse(PY_EM_TODA_POSICAO))
    except SyntaxError:
        return False


def test_a_mordida_o_removedor_sem_a_guarda_da_string_reprova(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert _o_py_sobrevive(T.limpar)

    def ingenuo(texto: str) -> list[object]:
        achados = []
        for numero, linha in enumerate(texto.split("\n"), 1):
            if (pos := linha.find(CERQUILHA)) >= 0:
                inicio = sum(len(x) + 1 for x in texto.split("\n")[:numero - 1]) + pos
                achados.append(T.G.Comentario(inicio, inicio + len(linha) - pos, linha[pos:],
                                            numero, CERQUILHA))
        return achados

    monkeypatch.setitem(T.G.LEITORES, "py", ingenuo)
    assert not _o_py_sobrevive(T.limpar), "o removedor sem a guarda da string passou na prova"


def _src_versionado() -> list[str]:
    feito = subprocess.run(["git", "-C", str(RAIZ), "ls-files", "src/*.py"],
                           capture_output=True, text=True, check=True)
    return [r for r in feito.stdout.split("\n") if r]


def test_a_mordida_o_comentario_de_volta_em_src_reprova_pelo_nome(tmp_path: Path) -> None:
    rel = next(r for r in _src_versionado() if r.endswith("/lifecycle.py"))
    original = (RAIZ / rel).read_text(encoding="utf-8")
    assert G.varrer(RAIZ, [rel]) == [], f"{rel} já tem comentário hoje"
    alvo = tmp_path / rel
    alvo.parent.mkdir(parents=True)
    alvo.write_text(original + f"{CERQUILHA} o comentário que voltou\n", encoding="utf-8")
    achados = G.varrer(tmp_path, [rel])
    assert [(a.arquivo, a.linha) for a in achados] == [(rel, original.count("\n") + 1)]
    assert G.main(["--raiz", str(tmp_path), str(alvo)]) == 1


def test_o_repositorio_nao_tem_comentario() -> None:
    """Prova da D-2610-O-CODIGO-NAO-TEM-COMENTARIO no repositório inteiro."""
    achados = G.varrer(RAIZ)
    assert not achados, "comentário no código versionado:\n" + "\n".join(
        str(a) for a in achados[:40])


def test_o_portao_mora_na_camada_rapida_e_no_ci() -> None:
    tabela = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    linha = r"^rapido\|codigo-sem-comentario\|py\|scripts/check_codigo_sem_comentario\.py\|"
    assert re.search(linha, tabela, re.M)
    assert "comentario-cortado" not in tabela
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "codigo-sem-comentario" in ci and "comentario-cortado" not in ci
    assert not (RAIZ / "scripts" / "check_comentario_cortado.py").exists()


A = _carrega("validar_acentuacao", "validar-acentuacao.py")
NAO = "n" + "ao"
PAGINA = "pag" + "ina"


def _acusadas(tmp_path: Path, corpo: str) -> list[int]:
    alvo = tmp_path / "gerador.py"
    alvo.write_text(corpo, encoding="utf-8")
    return [n for n, *_ in A.checar_arquivo(alvo, tmp_path)]


def test_o_valor_e_a_chave_do_js_na_string_dispensam_a_marca_que_saiu(tmp_path: Path) -> None:
    """O ``noqa-acento`` do JS da string saiu com o comentário; o valor e a chave são código."""
    corpo = (
        'JS = """\n'
        f"  if (b === '{NAO}') return;\n"
        f"  canal.postMessage({{{PAGINA}: location.pathname}});\n"
        f"  x({{a: 1,\n      {PAGINA}: 2}});\n"
        f'  el.dataset.modo = "{NAO}";\n'
        f"  a frase {NAO} abriu a {PAGINA}.\n"
        '"""\n'
    )
    assert _acusadas(tmp_path, corpo) == [7, 7]
