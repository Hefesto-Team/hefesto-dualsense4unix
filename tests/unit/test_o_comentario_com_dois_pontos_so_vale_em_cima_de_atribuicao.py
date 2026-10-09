"""O `#:` só vale colado em cima de uma atribuição (O-COMENTARIO-COM-DOIS-PONTOS-SO-VALE-...-01).

O `#:` é o comentário de documentação de atributo. Os cortes de comentário deixaram pedaços de
blocos `#:` longe da atribuição que documentavam (acima de `def`, dentro de dicionário, seguidos
de linha em branco). A segunda pergunta de `scripts/check_comentario_cortado.py` conta esses
blocos, com o mesmo fatiamento da primeira e o piso `PISO_DOIS_PONTOS`, que só desce.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_comentario_cortado.py"

_spec = importlib.util.spec_from_file_location("_cortado_dois_pontos", SCRIPT)
assert _spec and _spec.loader
cortado = importlib.util.module_from_spec(_spec)
sys.modules["_cortado_dois_pontos"] = cortado
_spec.loader.exec_module(cortado)

#: os cinco arquivos que a sprint limpou à mão; neles a régua não acha mais nada
OS_CINCO = tuple(
    f"src/hefesto_dualsense4unix/interface/pacotes/{nome}.py"
    for nome in ("a01_jogar", "a03_gatilhos", "a06_navegacao", "a07_lancadores",
                 "a11_calibrar_sensores")
)


def _linhas(texto: str) -> list[int]:
    return [n for n, _ in cortado.dois_pontos_soltos_do_texto(texto)]


def test_colado_numa_atribuicao_passa() -> None:
    assert _linhas("#: o teto, em segundos.\nNOME = 1\n") == []
    assert _linhas("#: os dois pesos da escada.\nFORTE, LEVE = 1, 0\n") == []
    assert _linhas("#: anotado também é atribuição.\nnome: int = 1\n") == []
    assert _linhas("class C:\n    #: campo do dado.\n    campo: str\n") == []
    assert _linhas("#: a primeira linha\n#: e a segunda.\nNOME = 1\n") == [], (
        "o bloco vale pela última linha"
    )


def test_acima_de_def_reprova() -> None:
    texto = "#: um comentário inteiro com a marca errada.\ndef f() -> int:\n    x = 1\n    return x\n"
    assert _linhas(texto) == [1]


def test_dentro_de_dicionario_literal_reprova() -> None:
    texto = 'MAPA = {\n    #: a chave de baixo.\n    "a": 1,\n}\n'
    assert _linhas(texto) == [2]


def test_seguido_de_linha_em_branco_reprova() -> None:
    assert _linhas("#: resto de um corte, e quem a\n\nNOME = 1\n") == [1]
    assert _linhas("x = 1\n#: no fim do arquivo não documenta nada.\n") == [2]


def test_o_comentario_comum_e_o_de_fim_de_linha_nao_entram() -> None:
    assert _linhas("# comentário comum acima de def.\ndef f() -> None:\n    pass\n") == []
    assert _linhas("NOME = 1  #: o de fim de linha é outra forma.\n\ny = 2\n") == []
    assert _linhas('x = """\n#: isto é texto de string.\n"""\n\ny = 1\n') == []


def test_arquivo_que_o_ast_nao_le_continua_na_conta() -> None:
    quebrado = "#: colado.\nNOME = 1\n#: solto.\n\ndef f(:\n"
    assert _linhas(quebrado) == [3]


def test_os_cinco_arquivos_da_sprint_estao_limpos() -> None:
    achados = [a for a in cortado.varrer_dois_pontos(RAIZ) if a[0] in OS_CINCO]
    assert achados == [], "\n".join(f"{a}:{n} {t}" for a, n, t in achados)


def test_a_arvore_de_verdade_nao_passa_do_piso() -> None:
    achados = cortado.varrer_dois_pontos(RAIZ)
    assert len(achados) >= 20, (
        f"a varredura achou só {len(achados)}: a régua ficou cega (git ls-files vazio?)"
    )
    assert len(achados) <= cortado.PISO_DOIS_PONTOS, (
        f"{len(achados)} bloco(s) `#:` fora de atribuição, piso {cortado.PISO_DOIS_PONTOS}: "
        "cole o `#:` na atribuição ou tire o `:` de quem subiu:\n  "
        + "\n  ".join(f"{a}:{n} {t.strip()}" for a, n, t in achados[-10:])
    )
    assert len(achados) == cortado.PISO_DOIS_PONTOS, (
        f"a contagem desceu para {len(achados)}: baixe o PISO_DOIS_PONTOS de "
        f"{cortado.PISO_DOIS_PONTOS} para {len(achados)} em scripts/check_comentario_cortado.py"
    )


def test_o_script_diz_as_duas_contagens() -> None:
    feito = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert f"piso {cortado.PISO_DOIS_PONTOS}." in feito.stdout
