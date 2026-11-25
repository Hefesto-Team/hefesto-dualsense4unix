#!/usr/bin/env python3
"""validar-fala-de-tela.py — o número medido que a tela mostra bate com a célula do mapa."""
from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parent.parent
FALA_DO_MAPA_RELATIVO = "src/hefesto_dualsense4unix/app/fala_do_mapa.py"
MAPA_RELATIVO = "docs/data/mapa-controles.csv"
TELA_RELATIVO = "src/hefesto_dualsense4unix/interface"

NUMEROS_RELATIVO = "src/hefesto_dualsense4unix/integrations/radio_da_mesa.py"


def carrega_fala_do_mapa(raiz: Path) -> ModuleType:
    """`app/fala_do_mapa.py`, carregado por caminho de arquivo."""
    caminho = raiz / FALA_DO_MAPA_RELATIVO
    spec = importlib.util.spec_from_file_location("fala_do_mapa_lido_pelo_portao", caminho)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"não consegui montar o spec de {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _literal(no: ast.expr | None) -> object:
    """`ast.literal_eval`, devolvendo `None` (não levantando) se não for literal."""
    if no is None:
        return None
    try:
        return ast.literal_eval(no)
    except (ValueError, TypeError, SyntaxError):
        return None


def _e_chamada_de(no: ast.AST, nome: str) -> bool:
    return isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == nome


@dataclass
class NumeroEncontrado:
    constante: str
    valor: float | None
    chave: str
    coluna: str
    arquivo: str
    linha: int


def _mapa_de_constantes_numericas(arvore: ast.Module) -> dict[str, float]:
    """`{NOME: valor}` de toda atribuição de módulo `NOME = <número literal>`."""
    valores: dict[str, float] = {}
    for no in arvore.body:
        alvo_e_valor: tuple[ast.expr, ast.expr | None] | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo_e_valor = (no.targets[0], no.value)
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo_e_valor = (no.target, no.value)
        if alvo_e_valor is None:
            continue
        alvo, valor_no = alvo_e_valor
        if not isinstance(alvo, ast.Name):
            continue
        literal = _literal(valor_no)
        if isinstance(literal, (int, float)) and not isinstance(literal, bool):
            valores[alvo.id] = float(literal)
    return valores


CAMPOS_DO_NUMERO: tuple[str, ...] = ("constante", "valor", "chave", "coluna")


def _campos_do_numero(item: ast.expr) -> tuple[ast.expr, ast.expr, ast.expr, ast.expr] | None:
    """Os quatro campos de um item da tupla, se ele for um `Numero(...)`."""
    if not _e_chamada_de(item, "Numero"):
        return None
    assert isinstance(item, ast.Call)
    if len(item.args) > len(CAMPOS_DO_NUMERO):
        return None
    campos: dict[str, ast.expr] = dict(zip(CAMPOS_DO_NUMERO, item.args, strict=False))
    for palavra in item.keywords:
        if palavra.arg not in CAMPOS_DO_NUMERO or palavra.arg in campos:
            return None
        campos[palavra.arg] = palavra.value
    if set(campos) != set(CAMPOS_DO_NUMERO):
        return None
    return (campos["constante"], campos["valor"], campos["chave"], campos["coluna"])


def descobre_numeros(raiz: Path) -> list[NumeroEncontrado]:
    """Todo `Numero(...)` de `NUMEROS_MEDIDOS_NO_MAPA` em `integrations/radio_da_mesa.py`."""
    caminho = raiz / NUMEROS_RELATIVO
    if not caminho.exists():
        return []
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    constantes = _mapa_de_constantes_numericas(arvore)

    encontrados: list[NumeroEncontrado] = []
    for no in ast.walk(arvore):
        alvo_e_valor: tuple[ast.expr, ast.expr | None] | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo_e_valor = (no.targets[0], no.value)
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo_e_valor = (no.target, no.value)
        if alvo_e_valor is None:
            continue
        alvo, valor_no = alvo_e_valor
        if not (isinstance(alvo, ast.Name) and alvo.id == "NUMEROS_MEDIDOS_NO_MAPA"):
            continue
        if not isinstance(valor_no, (ast.Tuple, ast.List)):
            continue
        for item in valor_no.elts:
            campos = _campos_do_numero(item)
            if campos is None:
                continue
            nome_no, valor_ref_no, chave_no, coluna_no = campos
            nome = _literal(nome_no)
            chave = _literal(chave_no)
            coluna = _literal(coluna_no)
            valor: float | None = None
            if isinstance(valor_ref_no, ast.Name):
                valor = constantes.get(valor_ref_no.id)
            else:
                literal = _literal(valor_ref_no)
                if isinstance(literal, (int, float)) and not isinstance(literal, bool):
                    valor = float(literal)
            if not (isinstance(nome, str) and isinstance(chave, str) and isinstance(coluna, str)):
                continue
            encontrados.append(
                NumeroEncontrado(
                    constante=nome,
                    valor=valor,
                    chave=chave,
                    coluna=coluna,
                    arquivo=str(caminho.relative_to(raiz)),
                    linha=item.lineno,
                )
            )
    return encontrados


def _le_celulas_do_mapa(raiz: Path) -> dict[str, dict[str, str]]:
    """`{id: {coluna: valor}}` do CSV — só o que Z6-08 precisa, lido direto:"""
    import csv

    caminho = raiz / MAPA_RELATIVO
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    return {linha["id"]: linha for linha in linhas if linha.get("id")}


def valida_numeros(
    numeros: list[NumeroEncontrado],
    celulas: dict[str, dict[str, str]],
    formata_pt_br: Callable[[float], str],
) -> list[str]:
    """`formata_pt_br` vem de `app/fala_do_mapa.py`, NUNCA redigitado aqui."""
    problemas: list[str] = []
    for numero in numeros:
        origem = f"{numero.arquivo}:{numero.linha}"
        if numero.valor is None:
            problemas.append(
                f"{origem}: não consegui resolver o valor de {numero.constante!r} "
                "por AST — declare `valor=NOME_DA_CONSTANTE` (a mesma "
                "referência, nunca um literal copiado)"
            )
            continue
        linha = celulas.get(numero.chave)
        if linha is None:
            problemas.append(
                f"{origem}: a chave {numero.chave!r} não existe em {MAPA_RELATIVO}"
            )
            continue
        celula = linha.get(numero.coluna, "")
        esperado = formata_pt_br(numero.valor)
        if esperado not in celula:
            problemas.append(
                f"{origem}: {numero.constante} = {numero.valor} (formatado "
                f"{esperado!r}) não aparece em {numero.coluna} de "
                f"{numero.chave!r} ({MAPA_RELATIVO}). A constante e a célula "
                "são a MESMA medição — atualize a célula (ou a nota de "
                "porque mudou) no mesmo commit que a constante"
            )
    return problemas


PISO_DA_REGUA: dict[str, int] = {"numeros": 3}

_O_QUE_O_PISO_MEDE: dict[str, str] = {
    "numeros": "número(s) medido(s) que a tela mostra (`NUMEROS_MEDIDOS_NO_MAPA`)",
}


def e_a_arvore_do_produto(raiz: Path) -> tuple[bool, str]:
    """`(é o produto?, por que não)` — o piso vale para o produto, e só."""
    if not (raiz / MAPA_RELATIVO).is_file():
        return False, f"não há {MAPA_RELATIVO} nesta árvore"
    if not (raiz / TELA_RELATIVO).is_dir():
        return False, f"não há a tela ({TELA_RELATIVO}) nesta árvore"
    return True, ""


def valida_piso_da_regua(medido: dict[str, int], piso: dict[str, int]) -> list[str]:
    """O conjunto medido hoje contra o piso. Pura de propósito."""
    problemas: list[str] = []
    for nome in sorted(piso):
        agora = medido.get(nome, 0)
        if agora >= piso[nome]:
            continue
        problemas.append(
            f"{nome}: a régua mede {agora} e o piso é {piso[nome]} — "
            f"{_O_QUE_O_PISO_MEDE.get(nome, nome)}. A régua ENCOLHEU: alguém "
            "apagou, renomeou ou despromoveu o que a régua enxergava. NÃO baixe o "
            "piso para ficar verde — descubra o que encolheu"
        )
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true", required=True, help="roda a checagem (o modo do CI)"
    )
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    args = parser.parse_args(argv)

    raiz = args.raiz.resolve()
    fala_do_mapa = carrega_fala_do_mapa(raiz)

    numeros = descobre_numeros(raiz)
    problemas = valida_numeros(numeros, _le_celulas_do_mapa(raiz), fala_do_mapa.formata_pt_br)

    medido = {"numeros": len(numeros)}
    e_o_produto, por_que_nao = e_a_arvore_do_produto(raiz)
    encolheu = valida_piso_da_regua(medido, PISO_DA_REGUA) if e_o_produto else []

    if encolheu:
        print(f"FALHA: a régua ENCOLHEU em {len(encolheu)} ponto(s):")
        for problema in encolheu:
            print(f"  {problema}")
        print("")

    if problemas:
        print(f"FALHA: {len(problemas)} desacordo(s) entre a tela e o mapa:")
        for problema in problemas:
            print(f"  {problema}")

    if encolheu or problemas:
        return 1

    if not e_o_produto:
        print(
            f"PISO NÃO APLICADO: {por_que_nao} — esta árvore não é o produto, "
            "e o piso de `PISO_DA_REGUA` só vale para ele."
        )

    piso = ", ".join(f"{nome}≥{valor}" for nome, valor in sorted(PISO_DA_REGUA.items()))
    print(
        f"OK: {len(numeros)} número(s) de tela de acordo com {MAPA_RELATIVO}. Piso: {piso}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
