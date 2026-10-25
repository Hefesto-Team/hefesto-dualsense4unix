"""A raiz do hidraw (`/sys/class/hidraw`) tem um dono, o `integrations/usb_pai`.

Em 25/10/2026, oito módulos cravavam a mesma constante. A sprint A-RAIZ-DO-HIDRAW-TEM-UM-DONO-SO-01
deu o dono ao `usb_pai`, e o `conexao_zumbi` e o `physical_report_reader` passam a importá-la
dele. A régua lê a árvore de sintaxe do `src/` e reprova a constante cravada num módulo fora da
lista, e a lista só encolhe: quem cura um dos outros tira o nome dela.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = "/sys/class/hidraw"
SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

#: o dono.
DONO = "integrations/usb_pai.py"

#: os outros módulos com a constante cravada, medidos em 25/10/2026 e fora da posse da sprint que
#: deu o dono ao `usb_pai`. A lista só encolhe.
AINDA_CRAVADA = {
    "core/backend_pydualsense.py",
    "integrations/dualsense_bt_audio.py",
    "integrations/quem_o_jogo_le.py",
    "integrations/radio_da_mesa.py",
    "integrations/uhid_gamepad.py",
}

#: os que importam do dono; neles a raiz não aparece em texto nenhum fora das docstrings.
IMPORTAM_DO_DONO = ("integrations/conexao_zumbi.py", "core/physical_report_reader.py")


def _docstrings(arvore: ast.Module) -> set[int]:
    """O `id` das constantes que são docstring (de módulo, classe ou função)."""
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            primeiro = no.body[0] if no.body else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                ids.add(id(primeiro.value))
    return ids


def constantes_da_raiz(fonte: str) -> list[str]:
    """Os nomes que o módulo liga à raiz do hidraw no nível de cima."""
    nomes: list[str] = []
    for no in ast.parse(fonte).body:
        if isinstance(no, ast.Assign):
            alvos, valor = no.targets, no.value
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvos, valor = [no.target], no.value
        else:
            continue
        if isinstance(valor, ast.Constant) and valor.value == RAIZ:
            nomes += [a.id for a in alvos if isinstance(a, ast.Name)]
    return nomes


def textos_com_a_raiz(fonte: str) -> list[int]:
    """As linhas com um texto (ou pedaço de f-string) que começa pela raiz, sem as docstrings."""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    return sorted(
        no.lineno for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
        and no.value.startswith(RAIZ) and id(no) not in docs)


def _modulos() -> dict[str, str]:
    return {str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
            for p in sorted(SRC.rglob("*.py"))}


def test_a_regua_pega_a_constante_e_o_texto_cravados() -> None:
    assert constantes_da_raiz(f'RAIZ_HIDRAW = "{RAIZ}"\n') == ["RAIZ_HIDRAW"]
    assert constantes_da_raiz(f'_R: str = "{RAIZ}"\n') == ["_R"]
    assert constantes_da_raiz(f'def f(raiz="{RAIZ}"):\n    pass\n') == []
    assert textos_com_a_raiz(f'def f(n):\n    return open(f"{RAIZ}/{{n}}/device/uevent")\n') == [2]
    assert textos_com_a_raiz(f'"""{RAIZ} na docstring."""\n') == []


def test_a_raiz_do_hidraw_so_e_cravada_no_dono_e_nos_que_a_lista_ainda_guarda() -> None:
    modulos = _modulos()
    assert DONO in modulos, f"a régua não achou o dono em {SRC}"
    cravada = {nome for nome, fonte in modulos.items() if constantes_da_raiz(fonte)}
    assert constantes_da_raiz(modulos[DONO]) == ["RAIZ_HIDRAW"]
    novos = cravada - AINDA_CRAVADA - {DONO}
    assert not novos, (
        f"a raiz do hidraw voltou a ser cravada em {sorted(novos)}: importe "
        "`RAIZ_HIDRAW` de `integrations/usb_pai`")
    curados = AINDA_CRAVADA - cravada
    assert not curados, f"{sorted(curados)} já não crava a raiz: tire da `AINDA_CRAVADA`"


def test_quem_importa_do_dono_nao_crava_a_raiz_em_texto_nenhum() -> None:
    modulos = _modulos()
    achados = {nome: linhas for nome in IMPORTAM_DO_DONO
               if (linhas := textos_com_a_raiz(modulos[nome]))}
    assert achados == {}, f"a raiz do hidraw cravada fora do dono: {achados}"
