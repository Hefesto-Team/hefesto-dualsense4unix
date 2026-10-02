#!/usr/bin/env python3
"""As cinco bancadas vivas abrem a página que prometem — e não saem verdes sem ela."""
from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

BANCADAS = (
    "jogar_vivo.py",
    "controles_vivos.py",
    "conexoes_vivas.py",
    "sistema_viva.py",
    "perfis_vivos.py",
)


def _caminho_da_pagina(fonte: str) -> pathlib.Path | None:
    """Resolve o `PAGINA = …` do fonte, sem importar o módulo."""
    m = re.search(r"^PAGINA = (.+)$", fonte, re.M)
    if m is None:
        return None
    expr = m.group(1)
    nome = re.search(r'"([\w.-]+\.html)"', expr)
    if nome is None:
        return None
    if "onde.PUBLICADO" in expr or '"paginas"' in expr:  # noqa-acento (nome de pasta)
        return INTERFACE / "paginas" / nome.group(1)  # noqa-acento (nome de pasta)
    return INTERFACE.parent / nome.group(1)


def test_as_cinco_bancadas_apontam_para_uma_pagina_que_existe() -> None:
    faltam = []
    for nome in BANCADAS:
        arq = INTERFACE / nome
        assert arq.exists(), f"a bancada {nome} sumiu — a lista desta régua envelheceu"
        alvo = _caminho_da_pagina(arq.read_text(encoding="utf-8"))
        assert alvo is not None, (
            f"{nome} não declara `PAGINA = …` numa forma que esta régua leia — "
            "declare-a como as outras quatro, ou ensine a régua a lê-la")
        if not alvo.exists():
            faltam.append(f"{nome} -> {alvo}")
    assert not faltam, (
        "bancada viva apontando para página que não existe:\n  "
        + "\n  ".join(faltam)
        + "\n\nO sintoma não é erro: é `ERRO DE CARGA`, `voltas: 0` e `rc=0` — "
          "verde sobre uma janela vazia.")


def _recusa_a_pagina_ausente(fonte: str) -> bool:
    """A bancada confere que a página existe e SAI com `rc=2` — pela ÁRVORE."""
    import ast

    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.If):
            continue
        teste = no.test
        if not (isinstance(teste, ast.UnaryOp)
                and isinstance(teste.op, ast.Not)):
            continue
        chamada = teste.operand
        if not (isinstance(chamada, ast.Call)
                and isinstance(chamada.func, ast.Attribute)
                and chamada.func.attr == "exists"):
            continue
        for dentro in ast.walk(no):
            if (isinstance(dentro, ast.Return)
                    and isinstance(dentro.value, ast.Constant)
                    and dentro.value.value == 2):
                return True
    return False


def test_as_cinco_bancadas_recusam_a_pagina_ausente_e_a_volta_zero() -> None:
    """A guarda que faz o `rc` contar. Sem ela, achar o defeito acima é sorte."""
    sem_guarda_da_pagina, sem_guarda_da_volta = [], []
    for nome in BANCADAS:
        fonte = (INTERFACE / nome).read_text(encoding="utf-8")
        if not _recusa_a_pagina_ausente(fonte):
            sem_guarda_da_pagina.append(nome)
        if "a bancada não deu uma volta" not in fonte:
            sem_guarda_da_volta.append(nome)
    assert not sem_guarda_da_pagina, (
        f"{sem_guarda_da_pagina} não conferem se a página existe antes de subir "
        "a janela — devolveriam `rc=0` sobre o vazio")
    assert not sem_guarda_da_volta, (
        f"{sem_guarda_da_volta} não reprovam quando a bancada não deu uma volta "
        "— uma bancada que não girou não mediu nada, e não sai verde")
