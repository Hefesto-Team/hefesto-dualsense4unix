"""A máscara não custa feature: o caminho do microfone é CEGO a ela."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

O_CAMINHO = (
    "daemon/subsystems/mic_da_mesa.py",
    "daemon/subsystems/luz_do_mic.py",
    "daemon/subsystems/bt_mic.py",
    "integrations/eleicao_de_microfone.py",
    "integrations/dualsense_bt_audio.py",
    "integrations/fontes_de_captura.py",
    "integrations/canal_do_microfone.py",
    "integrations/quem_ouve_o_microfone.py",
)

PALAVRAS_DA_MASCARA = (
    "native_mode",
    "gamepad_emulation_enabled",
    "flavor",
    "mascara",
)

def _codigo_com_a_palavra(arquivo: str) -> list[tuple[int, str]]:
    """As palavras da máscara no CÓDIGO — nunca em comentário ou docstring."""
    caminho = SRC / arquivo
    assert caminho.exists(), f"{arquivo} sumiu — o caminho do microfone mudou?"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
        and isinstance(no.body[0].value.value, str)
    }

    achadas: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            alvo = no.id
        elif isinstance(no, ast.Attribute):
            alvo = no.attr
        elif isinstance(no, ast.arg):
            alvo = no.arg
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            if id(no) in docstrings:
                continue
            alvo = no.value
        else:
            continue
        baixa = alvo.lower()
        if any(p in baixa for p in PALAVRAS_DA_MASCARA):
            achadas.append((getattr(no, "lineno", 0), alvo[:80]))
    return sorted(set(achadas))


@pytest.mark.parametrize("arquivo", O_CAMINHO)
def test_a_mascara_nao_aparece_no_caminho_do_microfone(arquivo: str) -> None:
    """Nenhuma das quatro palavras da máscara, em nenhum dos oito arquivos."""
    achadas = _codigo_com_a_palavra(arquivo)
    assert not achadas, (
        f"a máscara chegou ao caminho do microfone, em {arquivo}:\n  "
        + "\n  ".join(f"{n}: {texto}" for n, texto in achadas)
        + "\n\nA decisão dela (05/09/2026) é que a máscara NÃO custa feature: "
        "'Usaríamos essa feature do controle mesmo no Xbox'. Um gate aqui faz o "
        "microfone sumir quando ela liga a máscara, e o sintoma se lê como "
        "'este controle não tem microfone'."
    )


def test_a_regua_le_codigo_e_nao_prosa() -> None:
    """A régua de si mesma: a palavra na PROSA não pode reprovar."""
    canal = SRC / "integrations/canal_do_microfone.py"
    bruto = canal.read_text(encoding="utf-8").lower()
    assert "mascara" in bruto, (
        "o módulo do canal deixou de citar o documento do princípio — se a "
        "prosa mudou, esta régua perdeu o caso que ela guarda")
    assert _codigo_com_a_palavra("integrations/canal_do_microfone.py") == [], (
        "a régua voltou a medir prosa")


def test_o_produto_ja_afirma_isto_na_tela() -> None:
    """A frase de preço da máscara promete o microfone — e a promessa tem dono."""
    texto = (SRC / "app/actions/home_actions.py").read_text(encoding="utf-8")
    assert "microfone e alto-falante continuam funcionando" in texto, (
        "a frase que promete o microfone sob a máscara mudou de forma — "
        "confira se ela ainda promete, e ajuste esta régua junto")
