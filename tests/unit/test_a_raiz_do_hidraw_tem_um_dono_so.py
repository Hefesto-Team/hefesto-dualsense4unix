"""A raiz do hidraw (`/sys/class/hidraw`) tem um dono, o `integrations/usb_pai`.

Em 25/10/2026, oito módulos cravavam a mesma constante. A sprint A-RAIZ-DO-HIDRAW-TEM-UM-DONO-SO-01
deu o dono ao `usb_pai`, e a A-RAIZ-DO-HIDRAW-SAI-DOS-MODULOS-QUE-AINDA-A-CRAVAM-01 tirou a raiz
dos outros quinze. A régua lê a árvore de sintaxe do `src/` e reprova a raiz cravada fora do dono
em qualquer forma: a constante, o padrão de um parâmetro, o pedaço de uma f-string. Só o broker
fica, isento com o porquê medido, e crava a raiz uma vez só, na constante dele.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = "/sys/class/hidraw"
SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

#: o dono.
DONO = "integrations/usb_pai.py"

#: os outros módulos com a constante cravada. A lista só encolhe, e está vazia desde 25/10/2026.
AINDA_CRAVADA: set[str] = set()

#: o broker é 100% stdlib e autocontido de propósito (a docstring dele): o install copia só ele, e
#: ele roda no python3 do sistema, sem o pacote, logo não pode importar o dono. O porquê se mede
#: em `test_o_broker_isento_nao_importa_o_pacote`.
ISENTO = "broker/hidraw_broker.py"

#: a constante do isento: a raiz cravada uma vez no broker, e os padrões dos parâmetros a leem.
CONSTANTE_DO_ISENTO = "SYS_CLASS_HIDRAW"

#: quantos textos com a raiz (fora das docstrings) cada módulo ainda tem, em qualquer forma. Só o
#: isento fica, com o texto da constante dele; um módulo fora dela tem zero.
TEXTOS_AINDA_CRAVADOS = {ISENTO: 1}

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
    """As linhas com um texto (ou pedaço de f-string) que traz a raiz, sem as docstrings."""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    return sorted(
        no.lineno for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
        and RAIZ in no.value and id(no) not in docs)


def _modulos() -> dict[str, str]:
    return {str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
            for p in sorted(SRC.rglob("*.py"))}


def _recado(nome: str) -> str:
    """O que fazer com a raiz que cresceu: o broker não importa o pacote, e lê a constante dele."""
    if nome == ISENTO:
        return f"leia `{CONSTANTE_DO_ISENTO}` do próprio broker"
    return "importe `RAIZ_HIDRAW` de `integrations/usb_pai`"


def test_a_regua_pega_a_constante_e_o_texto_cravados() -> None:
    assert constantes_da_raiz(f'RAIZ_HIDRAW = "{RAIZ}"\n') == ["RAIZ_HIDRAW"]
    assert constantes_da_raiz(f'_R: str = "{RAIZ}"\n') == ["_R"]
    assert constantes_da_raiz(f'def f(raiz="{RAIZ}"):\n    pass\n') == []
    assert textos_com_a_raiz(f'def f(n):\n    return open(f"{RAIZ}/{{n}}/device/uevent")\n') == [2]
    assert textos_com_a_raiz(f'"""{RAIZ} na docstring."""\n') == []
    assert textos_com_a_raiz(f'def f(raiz="{RAIZ}"):\n    pass\n') == [1]
    assert textos_com_a_raiz(f'CONFERIR = "ls -l /dev/uhid {RAIZ}"\n') == [1]
    assert CONSTANTE_DO_ISENTO in _recado(ISENTO) and "usb_pai" not in _recado(ISENTO)
    assert "usb_pai" in _recado("core/um_modulo.py")


def test_a_raiz_do_hidraw_so_e_cravada_no_dono_e_nos_que_a_lista_ainda_guarda() -> None:
    modulos = _modulos()
    assert DONO in modulos, f"a régua não achou o dono em {SRC}"
    cravada = {nome for nome, fonte in modulos.items() if constantes_da_raiz(fonte)}
    assert constantes_da_raiz(modulos[DONO]) == ["RAIZ_HIDRAW"]
    assert constantes_da_raiz(modulos[ISENTO]) == [CONSTANTE_DO_ISENTO]
    novos = cravada - AINDA_CRAVADA - {DONO, ISENTO}
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


def test_o_texto_com_a_raiz_nao_cresce_em_modulo_nenhum() -> None:
    """A constante é uma forma; o padrão de um parâmetro e a f-string são outras, e a mesma raiz
    cravada por elas é um segundo dono do mesmo jeito."""
    modulos = _modulos()
    assert len(textos_com_a_raiz(modulos[DONO])) == 1, "o dono crava a raiz uma vez só"
    contagem = {nome: len(linhas) for nome, fonte in modulos.items()
                if nome != DONO and (linhas := textos_com_a_raiz(fonte))}
    cresceu = {nome: n for nome, n in contagem.items() if n > TEXTOS_AINDA_CRAVADOS.get(nome, 0)}
    assert not cresceu, (
        f"a raiz do hidraw ganhou texto novo em {cresceu} (a catraca: "
        f"{ {n: TEXTOS_AINDA_CRAVADOS.get(n, 0) for n in cresceu} }): "
        + "; ".join(f"{nome}: {_recado(nome)}" for nome in sorted(cresceu)))
    encolheu = {nome: contagem.get(nome, 0) for nome, n in TEXTOS_AINDA_CRAVADOS.items()
                if contagem.get(nome, 0) < n}
    assert not encolheu, f"{encolheu} já crava menos: baixe a `TEXTOS_AINDA_CRAVADOS`"


def test_so_o_isento_guarda_texto_com_a_raiz() -> None:
    assert set(TEXTOS_AINDA_CRAVADOS) == {ISENTO}, (
        f"a catraca guarda {sorted(TEXTOS_AINDA_CRAVADOS)}: só o broker é isento")


def test_o_broker_isento_nao_importa_o_pacote() -> None:
    """A isenção vale enquanto o broker não importa nada do pacote; se importar, ele lê o dono."""
    pacote = "hefesto_dualsense4unix"
    do_pacote = [
        no.lineno for no in ast.walk(ast.parse(_modulos()[ISENTO]))
        if (isinstance(no, ast.ImportFrom) and (no.module or "").startswith(pacote))
        or (isinstance(no, ast.Import) and any(a.name.startswith(pacote) for a in no.names))]
    assert do_pacote == [], (
        f"o broker importa o pacote (linhas {do_pacote}): tire a isenção e leia `RAIZ_HIDRAW` do "
        "`usb_pai`")
