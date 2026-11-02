"""A ESPERA DA PÁGINA PINTADA TEM UM DONO SÓ: o ``abrir_pronta`` de ``interface/olhar.py``.

Ele espera o ``load``, o ``document.fonts.ready``, dois quadros pintados e, pedido, um seletor,
com prazo por sinal e o nome do que faltou. A rede quieta não é sinal de página ``file://``:
estoura o prazo com a máquina carregada ou chega antes do quadro pintado. Esta régua prova que
nenhum código a espera, que nenhum outro lugar de ``scripts/`` e ``src/`` refaz a espera das
fontes e dos quadros, que quem abre a página abre pelo dono, sem relógio fixo depois dele nem
de um ``goto`` solto, e que o ponto comum dos portões de página (``scripts/chrome_sem_rede.py``)
passa por ele.
"""
from __future__ import annotations

import ast
import itertools
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (str(RAIZ / "src"), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede

from hefesto_dualsense4unix.interface import olhar

DONO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "olhar.py"

QUEM_ABRE_A_PAGINA = (
    "scripts/chrome_sem_rede.py",
    "scripts/check_cores_do_dualsense.py",
    "scripts/check_pecas_do_dualsense.py",
    "scripts/tela/regua_estados.py",
    "scripts/tela/regua_popup.py",
    "scripts/tela/importar.py",
)

REDE_QUIETA = re.compile(r"""(['"])networkidle\1""")

ESPERA_DO_DESENHO = re.compile(
    r"fonts\.ready|requestAnimationFrame\(\s*\(\)\s*=>\s*requestAnimationFrame")

DEPOIS_DE_ABRIR = {"abrir_pronta", "add_style_tag", "goto", "reload"}


def _codigo(*pastas: str, sufixos: tuple[str, ...] = (".py",)) -> list[pathlib.Path]:
    return sorted(p for pasta in pastas for p in (RAIZ / pasta).rglob("*")
                  if p.suffix in sufixos and p.is_file() and "__pycache__" not in p.parts)


def _nome_chamado(no: ast.stmt) -> str | None:
    if not isinstance(no, ast.Expr) or not isinstance(no.value, ast.Call):
        return None
    funcao = no.value.func
    if isinstance(funcao, ast.Attribute):
        return funcao.attr
    if isinstance(funcao, ast.Name):
        return funcao.id
    return None


def _abre(no: ast.stmt) -> bool:
    if isinstance(no, ast.If):
        return any(bool(ramo) and _abre(ramo[-1]) for ramo in (no.body, no.orelse))
    return _nome_chamado(no) in DEPOIS_DE_ABRIR


def _relogio_depois_de_abrir(arvore: ast.AST) -> list[int]:
    linhas = []
    for no in ast.walk(arvore):
        for campo in ("body", "orelse", "finalbody", "handlers"):
            bloco = getattr(no, campo, None)
            if not isinstance(bloco, list):
                continue
            for antes, depois in itertools.pairwise(bloco):
                if _abre(antes) and _nome_chamado(depois) == "wait_for_timeout":
                    linhas.append(depois.lineno)
    return linhas


def test_nenhum_codigo_espera_a_rede_quieta() -> None:
    achados = [f"{p.relative_to(RAIZ)}:{n}"
               for p in _codigo("scripts", "src", "tests", sufixos=(".py", ".js", ".mjs", ".sh"))
               for n, linha in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                         .splitlines(), 1)
               if REDE_QUIETA.search(linha)]
    assert achados == [], (
        f"a rede quieta voltou a decidir quando a página está pronta: {achados}. "
        "Abra a página pelo abrir_pronta de interface/olhar.py.")


def test_a_espera_das_fontes_e_dos_quadros_mora_so_no_dono() -> None:
    assert ESPERA_DO_DESENHO.search(DONO.read_text(encoding="utf-8")), (
        "instrumento inválido: o padrão não acha a espera nem no dono")
    achados = [f"{p.relative_to(RAIZ)}:{n}"
               for p in _codigo("scripts", "src") if p != DONO
               for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if ESPERA_DO_DESENHO.search(linha)]
    assert achados == [], (
        f"a espera das fontes e dos quadros tem um segundo dono: {achados}. Duas esperas "
        "da mesma coisa divergem; a do dono tem prazo e diz o sinal que faltou.")


@pytest.mark.parametrize("relativo", QUEM_ABRE_A_PAGINA)
def test_quem_abre_a_pagina_espera_pelo_dono_e_sem_relogio_depois(relativo: str) -> None:
    arvore = ast.parse((RAIZ / relativo).read_text(encoding="utf-8"))
    chamadas = {no.func.attr if isinstance(no.func, ast.Attribute) else getattr(no.func, "id", "")
                for no in ast.walk(arvore) if isinstance(no, ast.Call)}
    assert "abrir_pronta" in chamadas, f"{relativo} abre a página sem passar pelo dono"
    assert "wait_for_load_state" not in chamadas, (
        f"{relativo} espera um estado de carga por conta própria, fora do dono")
    relogio = _relogio_depois_de_abrir(arvore)
    assert relogio == [], (
        f"{relativo}:{relogio} espera a página por relógio fixo: o dono espera os quadros "
        "pintados, e o relógio só some com a máquina carregada")


@pytest.mark.parametrize("abre", ["abrir_pronta(pg, 'u', ir)", "pg.goto('u')", "pg.reload()",
                                  "if css:\n        pg.add_style_tag(content=css)"])
def test_o_relogio_depois_de_abrir_e_achado(abre: str) -> None:
    plantado = ast.parse(f"def f(pg, css):\n    {abre}\n    pg.wait_for_timeout(400)\n")
    assert _relogio_depois_de_abrir(plantado) == [3 + abre.count("\n")], (
        "instrumento inválido: não acha o plantado")


class _PaginaDeMentira:
    def __init__(self) -> None:
        self.idas: list[tuple[str, dict[str, Any]]] = []
        self.avaliadas: list[str] = []

    def set_viewport_size(self, tamanho: dict[str, int]) -> None:
        self.tamanho = tamanho

    def route(self, padrao: str, decide: Any) -> None:
        self.rota = (padrao, decide)

    def goto(self, uri: str, **opcoes: Any) -> None:
        self.idas.append((uri, opcoes))

    def evaluate(self, script: str, *args: Any) -> Any:
        self.avaliadas.append(script)


class _NavegadorDeMentira:
    def __init__(self) -> None:
        self.pagina = _PaginaDeMentira()

    def new_page(self, **opcoes: Any) -> _PaginaDeMentira:
        return self.pagina


def test_o_ponto_comum_dos_portoes_abre_pelo_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    assert vars(chrome_sem_rede)["abrir_pronta"] is olhar.abrir_pronta, (
        "o chrome_sem_rede tem um abrir_pronta que não é o do olhar")
    pedidos: list[dict[str, Any]] = []

    def espia(pg: Any, endereco: str, ir: Any, **opcoes: Any) -> None:
        pedidos.append({"endereco": endereco, **opcoes})
        ir(wait_until="load", timeout=opcoes["prazo_ms"])

    monkeypatch.setattr(chrome_sem_rede, "abrir_pronta", espia)
    navegador = _NavegadorDeMentira()
    pagina, recusadas = chrome_sem_rede.abrir_sem_rede(
        navegador, "file:///pagina.html", largura=800, altura=600, espera_ms=1234)
    assert pedidos == [{"endereco": "file:///pagina.html", "prazo_ms": 1234}], pedidos
    assert pagina.idas == [("file:///pagina.html", {"wait_until": "load", "timeout": 1234})], (
        pagina.idas)
    assert pagina.avaliadas == [], (
        f"o ponto comum ainda espera por conta própria depois do dono: {pagina.avaliadas}")
    assert recusadas == []
