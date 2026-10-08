"""O comentário não termina no meio da frase (A-CASA-NAO-DEIXA-PASSAR-COMENTARIO-CORTADO-01).

O commit `8002c142c` deixou só a primeira linha de muitos blocos de comentário, e a primeira
acaba em «…a», «…que», «…e». A régua (`scripts/check_comentario_cortado.py`) conta os blocos que
acabam em conectivo ou em citação `arquivo:linha` sem pontuação, seguidos de código; o piso é a
contagem de quando nasceu e só desce.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_comentario_cortado.py"

_spec = importlib.util.spec_from_file_location("_cortado", SCRIPT)
assert _spec and _spec.loader
cortado = importlib.util.module_from_spec(_spec)
sys.modules["_cortado"] = cortado
_spec.loader.exec_module(cortado)


def test_o_caso_do_janela_aberta_comum_reprova() -> None:
    texto = (
        "TIQUES_POR_FASE = 40\n\n"
        "#: `TIQUE_MS` do produto (ver `_teto_da_fase_s`). Bater o teto não é pulo: a\n"
        "VEZES_O_NOMINAL = 5\n"
    )
    assert [n for n, _ in cortado.cortados_do_texto(texto)] == [3]


def test_o_bloco_de_varias_linhas_vale_pela_ultima() -> None:
    cortado_no_fim = "# a primeira linha termina em ponto.\n# a segunda acaba no\nx = 1\n"
    inteiro = "# a primeira acaba no\n# meio e a segunda fecha a frase.\nx = 1\n"
    assert [n for n, _ in cortado.cortados_do_texto(cortado_no_fim)] == [2]
    assert cortado.cortados_do_texto(inteiro) == []


def test_a_frase_inteira_e_o_comentario_de_fim_de_arquivo_passam() -> None:
    assert cortado.cortados_do_texto("# a frase fecha aqui.\nx = 1\n") == []
    assert cortado.cortados_do_texto("# lista: um, dois e\n") == [], "fim de arquivo não conta"
    assert cortado.cortados_do_texto("x = 1  # acaba em que\ny = 2\n") == [], (
        "comentário de fim de linha é de outra régua"
    )


def test_o_jogo_velho_dentro_de_string_nao_e_comentario() -> None:
    texto = 'x = """\n# isto é texto, não comentário, e\n"""\ny = 1\n'
    assert cortado.cortados_do_texto(texto) == []


def test_o_bloco_que_acaba_em_citacao_sem_verbo_reprova() -> None:
    """O caso da `aba08` (nota da modos-1-7): o bloco `#:` termina numa citação `arquivo:linha`."""
    texto = (
        "#: A frase já está no `title` / e sem chamador, e a lápide do\n"
        "#: `portao_a_casa_sabe_e_o_produto_nao_faz.py:1188`\n"
        "PENEIRA_QUANDO_ELA_EXISTIR = ()\n"
    )
    assert [n for n, _ in cortado.cortados_do_texto(texto)] == [2]
    fechado = texto.replace("1188`\n", "1188`.\n")
    assert cortado.cortados_do_texto(fechado) == [], "com ponto final a citação é frase inteira"


def test_cada_conectivo_da_lista_corta_a_frase() -> None:
    for palavra in ("a", "o", "de", "que", "e", "para", "com", "em"):
        assert cortado.termina_no_meio(f"# o texto segue {palavra}"), palavra
    assert not cortado.termina_no_meio("# o texto fecha com ponto."), "ponto fecha"
    assert not cortado.termina_no_meio("# o texto fecha em `valor`"), "código fecha"


def test_a_arvore_de_verdade_nao_passa_do_piso() -> None:
    """O piso só desce: subir reprova, e descer pede para baixar o piso na mesma mudança."""
    achados = cortado.varrer(RAIZ)
    assert len(achados) >= 100, (
        f"a varredura achou só {len(achados)}: a régua ficou cega (git ls-files vazio?)"
    )
    assert len(achados) <= cortado.PISO, (
        f"{len(achados)} comentário(s) cortado(s), piso {cortado.PISO}: termine a frase de quem "
        "subiu (`scripts/check_comentario_cortado.py --original` traz o texto de antes):\n  "
        + "\n  ".join(f"{a}:{n} {t.strip()}" for a, n, t in achados[-10:])
    )
    assert len(achados) == cortado.PISO, (
        f"a contagem desceu para {len(achados)}: baixe o PISO de {cortado.PISO} para "
        f"{len(achados)} em scripts/check_comentario_cortado.py"
    )


def test_o_script_diz_a_contagem_e_o_rc(tmp_path: Path) -> None:
    feito = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert f"piso {cortado.PISO}" in feito.stdout
