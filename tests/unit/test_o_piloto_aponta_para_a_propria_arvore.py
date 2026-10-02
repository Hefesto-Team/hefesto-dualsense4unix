"""A aritmética de caminho dos instrumentos, e o `rc` que não pode mentir."""

from __future__ import annotations

import os
import subprocess
import sys
import re
from pathlib import Path

import pytest

from tests.conftest import skip_sem_gi_real

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

_COM_RAIZ = ("hefesto_vivo.py", "controles_vivos.py", "sistema_viva.py", "casamento.py")


@pytest.mark.parametrize("nome", _COM_RAIZ)
def test_a_raiz_calculada_e_a_arvore_e_nao_o_src(nome: str) -> None:
    """A METADE QUE MEDE: a conta é REFEITA aqui, não lida no texto."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r"^RAIZ = AQUI\.parents\[(\d)\]", fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da RAIZ"
    nivel = int(m.group(1))

    aqui = INTERFACE
    raiz = aqui.parents[nivel]
    assert (raiz / "src").is_dir(), (
        f"{nome}: `AQUI.parents[{nivel}] / 'src'` dá {raiz / 'src'}, que NÃO "
        "EXISTE. Com `[1]` a conta cai no próprio `src` e o `RAIZ / \"src\"` "
        "vira `src/src` — o defeito de 04/09/2026."
    )
    assert raiz == RAIZ, f"{nome}: a RAIZ calculada ({raiz}) não é a árvore"


@pytest.mark.parametrize("nome", ("controles_vivos.py", "sistema_viva.py"))
def test_a_pagina_que_o_instrumento_abre_existe_no_disco(nome: str) -> None:
    """E o efeito visível do erro: um HTML que não está lá."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r'^PAGINA = RAIZ / "src" / (.+?)(?:  #|$)', fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da PAGINA"
    pedacos = [p.strip().strip('"') for p in m.group(1).split(" / ")]
    caminho = RAIZ / "src"
    for p in pedacos:
        caminho = caminho / p
    assert caminho.is_file(), (
        f"{nome}: `PAGINA` aponta para {caminho}, que não existe no disco. "
        "O instrumento abriria o vazio."
    )


@skip_sem_gi_real
def test_a_regua_do_mockup_nao_sai_verde_sobre_o_vazio() -> None:
    """Página morta REPROVA — medido rodando o piloto, não lendo o fonte dele."""
    piloto = INTERFACE / "hefesto_vivo.py"
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"))
    fim = subprocess.run(
        [sys.executable, str(piloto), "--oculta", "--abre", "99", "--segundos", "3"],
        capture_output=True, text=True, env=ambiente, timeout=180, check=False,
    )
    assert "ERRO DE CARGA" in fim.stderr, (
        "o piloto nem chegou a acusar a página morta — a medição não aconteceu "
        f"e o resto deste teste não vale nada. stderr: {fim.stderr[-400:]}")
    assert fim.returncode != 0, (
        "o piloto imprimiu `ERRO DE CARGA` e saiu rc=0: quem o chamar num "
        "script lê VERDE sobre uma janela morta. Uma régua que imprime o erro "
        "e sai zero é pior que régua nenhuma.")

    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert re.search(
        r"if args\.prova_de_mockup and not piloto\.visitadas:.*?raise SystemExit\(1\)",
        fonte, re.S,
    ), (
        "sumiu a guarda do ZERO: `--prova-de-mockup` sem visitar aba nenhuma "
        "tem de REPROVAR. Zero é erro, não silêncio."
    )
    assert "if not piloto.tela.na_aba:" in fonte, (
        "a espera voltou a partir de um `timeout` fixo: o piloto navegava "
        "antes de a carga inicial confirmar, e a confirmação chegava com o "
        "título vazio."
    )
    for chamador in ("piloto._provar_mockup", "piloto._provar_no_aparelho",
                     "piloto._provar_cliques", "piloto._ir(args.abre)"):
        assert re.search(
            r"_quando_a_pagina_estiver_de_pe\(\s*(?:lambda:\s*)?[^)]*?"
            + re.escape(chamador), fonte, re.S), (
            f"`{chamador}` saiu de dentro de `_quando_a_pagina_estiver_de_pe`. "
            "Um relógio fixo aqui faz o piloto navegar antes de a carga "
            "confirmar — e a janela morre acusando a página, que não tem "
            "culpa. Foi assim que `--abre 10` reprovou em toda execução.")


def test_a_janela_guarda_o_motivo_da_morte() -> None:
    """A outra metade, no dono: sem o atributo, o piloto não teria o que ler."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "ponte_da_tela.py"
    ).read_text(encoding="utf-8")
    assert "self.morreu: str | None = None" in fonte
    assert "self.morreu = motivo" in fonte
