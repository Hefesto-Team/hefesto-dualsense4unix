"""A suíte não alcança o ``/sys`` e o ``/dev`` reais pelo padrão do broker.

Em 25/10/2026 o padrão de cada raiz do físico ficava ligado na definição
(``dev_root: str = DEV_ROOT``): um ``monkeypatch`` da constante não desviava nada, e 41
chamadas em 17 arquivos de teste deixavam alguma raiz na máquina que roda a suíte, a mesma
em que o broker faz ``chmod`` e escreve ACL nos nós que valida. A sprint
A-SUITE-NAO-ALCANCA-O-SYS-REAL-PELO-PADRAO-DO-BROKER-01 fez o parâmetro nascer ``None`` e o
``_raiz`` do broker ler a constante na CHAMADA; o ``conftest`` cega as nove raízes na sessão.

As três réguas: (1) com a constante desviada, cada função lê a raiz desviada; (2) dentro da
suíte, as nove apontam para fora do ``/sys`` e do ``/dev``; (3) a raiz se resolve num lugar
só, o ``_raiz``.
"""

from __future__ import annotations

import ast
import io
import os
import stat
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from tests.unit.test_o_broker_crava_cada_raiz_uma_vez_so import BROKER, RAIZES

#: as raízes que um parâmetro de função recebe (as do gadget moram no ``RaizesDoPad``).
RAIZES_DE_PARAMETRO = (
    "DEV_ROOT", "DEV_INPUT_ROOT", "SYS_CLASS_HIDRAW", "SYS_CLASS_INPUT",
    "SYS_CLASS_BLUETOOTH", "SYS_BUS_HID_DRIVERS",
)
BASE = "hidraw987"
EVENTO = "event987"
_RDEV = os.makedev(237, 987)


def _chr(_caminho: str) -> Any:
    return SimpleNamespace(st_mode=stat.S_IFCHR | 0o660, st_rdev=_RDEV)


class _Cena:
    """As raízes desviadas e o que a função tocou com elas."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.raiz = {nome: str(tmp_path / nome.lower()) for nome in RAIZES_DE_PARAMETRO}
        for nome, valor in self.raiz.items():
            monkeypatch.setattr(hb, nome, valor)
        self.tocados: list[str] = []
        self.monkeypatch = monkeypatch

    def stat(self, caminho: str) -> Any:
        self.tocados.append(caminho)
        return _chr(caminho)

    def abrir_o_sysfs(self) -> None:
        """O ``open`` do broker lê um sysfs de mentira e anota o caminho."""

        def abrir(caminho: str, *_a: Any, **_k: Any) -> io.StringIO:
            self.tocados.append(caminho)
            if caminho.endswith("/dev"):
                return io.StringIO("237:987\n")
            return io.StringIO("HID_ID=0003:0000054C:00000CE6\n")

        self.monkeypatch.setattr(hb, "open", abrir, raising=False)

    def espiar(self, nome: str, devolve: Any) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        chamadas: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def espia(*a: Any, **k: Any) -> Any:
            chamadas.append((a, k))
            return devolve

        self.monkeypatch.setattr(hb, nome, espia)
        return chamadas

    def fora_do_desvio(self) -> list[str]:
        return [t for t in self.tocados if not t.startswith(tuple(self.raiz.values()))]


def _canonical_hidraw_base(c: _Cena) -> None:
    assert hb.canonical_hidraw_base(f"{c.raiz['DEV_ROOT']}/{BASE}") == BASE
    assert hb.canonical_hidraw_base(f"/dev/{BASE}") is None


def _canonical_input_base(c: _Cena) -> None:
    assert hb.canonical_input_base(f"{c.raiz['DEV_INPUT_ROOT']}/{EVENTO}") == EVENTO
    assert hb.canonical_input_base(f"/dev/input/{EVENTO}") is None


def _validate_physical_node(c: _Cena) -> None:
    c.abrir_o_sysfs()
    pai = c.espiar("_pai_hid_e_dualsense_fisico", True)
    no = f"{c.raiz['DEV_ROOT']}/{BASE}"
    assert hb.validate_physical_node(no, stat_fn=c.stat, lstat_fn=c.stat) == BASE
    assert f"{c.raiz['SYS_CLASS_HIDRAW']}/{BASE}/dev" in c.tocados
    assert [k["sys_class_bluetooth"] for _a, k in pai] == [c.raiz["SYS_CLASS_BLUETOOTH"]]


def _validate_physical_input_node(c: _Cena) -> None:
    c.abrir_o_sysfs()
    pai = c.espiar("_pai_hid_e_dualsense_fisico", True)
    no = f"{c.raiz['DEV_INPUT_ROOT']}/{EVENTO}"
    assert hb.validate_physical_input_node(no, stat_fn=c.stat, lstat_fn=c.stat) == EVENTO
    assert f"{c.raiz['SYS_CLASS_INPUT']}/{EVENTO}/dev" in c.tocados
    assert [k["sys_class_bluetooth"] for _a, k in pai] == [c.raiz["SYS_CLASS_BLUETOOTH"]]


def _motivo_de_recusar_o_acionador(c: _Cena) -> None:
    c.abrir_o_sysfs()
    chave = c.espiar("chave_do_acionador_no_sys", "0000:0000:00000000")
    no = f"{c.raiz['DEV_INPUT_ROOT']}/{EVENTO}"
    motivo = hb.motivo_de_recusar_o_acionador(
        no, "aaaa:bbbb:00000001", stat_fn=c.stat, lstat_fn=c.stat)
    assert motivo == "reject_nao_e_o_aparelho_declarado"
    assert [a for a, _k in chave] == [(f"{c.raiz['SYS_CLASS_INPUT']}/{EVENTO}",)]


_DO_FS = {
    "_sys_class_hidraw": "SYS_CLASS_HIDRAW", "_dev_input_root": "DEV_INPUT_ROOT",
    "_sys_class_input": "SYS_CLASS_INPUT", "_sys_class_bluetooth": "SYS_CLASS_BLUETOOTH",
    "_sys_bus_hid_drivers": "SYS_BUS_HID_DRIVERS",
}


def _FsAclOps(c: _Cena) -> None:  # noqa: N802 - o nome do caso é o da classe
    ops = hb.FsAclOps()
    assert {a: getattr(ops, a) for a in _DO_FS} == {a: c.raiz[n] for a, n in _DO_FS.items()}


def _BrokerState(c: _Cena) -> None:  # noqa: N802 - o nome do caso é o da classe
    st = hb.BrokerState(allowed_uid=1000, log=lambda *_a, **_k: None)
    do_estado = {"_dev_root": "DEV_ROOT", **_DO_FS}
    do_estado.pop("_sys_bus_hid_drivers")
    assert {a: getattr(st, a) for a in do_estado} == {
        a: c.raiz[n] for a, n in do_estado.items()}
    assert {a: getattr(st._ops, a) for a in _DO_FS} == {
        a: c.raiz[n] for a, n in _DO_FS.items()}


def _RaizesDoPad(c: _Cena) -> None:  # noqa: N802 - o nome do caso é o da classe
    assert hb.RaizesDoPad().dev == c.raiz["DEV_ROOT"]


def _a_varredura(funcao: Callable[..., Any], **kw: Any) -> Callable[[_Cena], None]:
    """A varredura de topo lista o ``SYS_CLASS_HIDRAW`` desviado e valida cada nó com as
    três raízes desviadas."""

    def caso(c: _Cena) -> None:
        os.makedirs(f"{c.raiz['SYS_CLASS_HIDRAW']}/{BASE}")
        valida = c.espiar("validate_physical_node", None)
        funcao(**kw, ops=SimpleNamespace())
        assert valida == [((f"{c.raiz['DEV_ROOT']}/{BASE}",), {
            "dev_root": c.raiz["DEV_ROOT"],
            "sys_class_hidraw": c.raiz["SYS_CLASS_HIDRAW"],
            "sys_class_bluetooth": c.raiz["SYS_CLASS_BLUETOOTH"],
        })]

    return caso


CASOS: dict[str, Callable[[_Cena], None]] = {
    "canonical_hidraw_base": _canonical_hidraw_base,
    "canonical_input_base": _canonical_input_base,
    "validate_physical_node": _validate_physical_node,
    "validate_physical_input_node": _validate_physical_input_node,
    "motivo_de_recusar_o_acionador": _motivo_de_recusar_o_acionador,
    "FsAclOps": _FsAclOps,
    "BrokerState": _BrokerState,
    "RaizesDoPad": _RaizesDoPad,
    "physical_nodes_exposure": _a_varredura(
        lambda **kw: hb.physical_nodes_exposure(1000, **kw)),
    "restore_all_physical": _a_varredura(hb.restore_all_physical, uid=1000),
    "fechar_todo_fisico": _a_varredura(hb.fechar_todo_fisico, uid=1000),
}


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_com_a_constante_desviada_a_funcao_le_a_raiz_desviada(
    nome: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cena = _Cena(tmp_path, monkeypatch)
    CASOS[nome](cena)
    assert cena.fora_do_desvio() == [], f"`{nome}` tocou fora da raiz desviada"


def _funcoes_com_raiz(arvore: ast.Module) -> dict[str, set[str]]:
    """Cada função com padrão num parâmetro de raiz (o ``__init__`` leva o nome da classe)."""
    parametro = {nome.lower() for nome in RAIZES_DE_PARAMETRO}
    donos = {id(f): no.name for no in ast.walk(arvore) if isinstance(no, ast.ClassDef)
             for f in no.body if isinstance(f, ast.FunctionDef) and f.name == "__init__"}
    funcoes: dict[str, set[str]] = {}
    for f in ast.walk(arvore):
        if not isinstance(f, ast.FunctionDef):
            continue
        posicionais = f.args.posonlyargs + f.args.args
        com_padrao = posicionais[len(posicionais) - len(f.args.defaults):] + [
            a for a, d in zip(f.args.kwonlyargs, f.args.kw_defaults, strict=True) if d is not None]
        achados = {a.arg for a in com_padrao if a.arg in parametro}
        if achados:
            funcoes[donos.get(id(f), f.name)] = achados
    return funcoes


def test_todo_caso_cobre_toda_funcao_com_parametro_de_raiz() -> None:
    funcoes = set(_funcoes_com_raiz(ast.parse(BROKER.read_text(encoding="utf-8"))))
    assert funcoes - set(CASOS) == set(), "função com raiz sem caso na régua (1)"


def test_dentro_da_suite_as_raizes_apontam_para_fora_da_maquina() -> None:
    reais = {nome: getattr(hb, nome) for nome in RAIZES
             if getattr(hb, nome).startswith(("/sys", "/dev"))}
    assert reais == {}, f"o conftest não cega estas raízes do broker: {reais}"


def _padroes(arvore: ast.Module) -> list[tuple[int, str]]:
    """Todo padrão de parâmetro e de campo de dataclass que é o nome de uma raiz."""
    padroes: list[ast.expr] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.arguments):
            padroes += no.defaults + [d for d in no.kw_defaults if d is not None]
        elif isinstance(no, ast.ClassDef):
            padroes += [c.value for c in no.body if isinstance(c, ast.AnnAssign) and c.value]
    return [(p.lineno, p.id) for p in padroes if isinstance(p, ast.Name) and p.id in RAIZES]


def test_nenhum_padrao_liga_a_raiz_na_definicao() -> None:
    assert _padroes(ast.parse(BROKER.read_text(encoding="utf-8"))) == []


def test_a_raiz_se_resolve_so_no_ajudante() -> None:
    """Fora do ``default_factory`` do ``RaizesDoPad``, ninguém lê a constante da raiz pelo
    nome (o ``if x is None: x = CONSTANTE`` à mão), e só o ``_raiz`` lê o ``globals()``."""
    arvore = ast.parse(BROKER.read_text(encoding="utf-8"))
    nas_lambdas = {id(n) for lam in ast.walk(arvore) if isinstance(lam, ast.Lambda)
                   for n in ast.walk(lam.body)}
    lidas = [(n.lineno, n.id) for n in ast.walk(arvore)
             if isinstance(n, ast.Name) and n.id in RAIZES and isinstance(n.ctx, ast.Load)
             and id(n) not in nas_lambdas]
    assert lidas == [], f"a raiz lida à mão, fora do `_raiz`: {lidas}"
    ajudante = next(f for f in arvore.body if isinstance(f, ast.FunctionDef) and f.name == "_raiz")
    no_ajudante = {id(n) for n in ast.walk(ajudante)}
    globais = [n.lineno for n in ast.walk(arvore) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name) and n.func.id == "globals"
               and id(n) not in no_ajudante]
    assert globais == []
    nomes = [n.args[1].value for n in ast.walk(arvore) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "_raiz"
             and isinstance(n.args[1], ast.Constant)]
    assert nomes and set(nomes) <= set(RAIZES_DE_PARAMETRO), set(nomes) - set(RAIZES)


def test_a_regua_pega_o_padrao_ligado_e_a_leitura_a_mao() -> None:
    assert _padroes(ast.parse("def f(*, d: str = DEV_ROOT):\n    pass\n")) == [(1, "DEV_ROOT")]
    assert _padroes(ast.parse("class C:\n    dev: str = DEV_ROOT\n")) == [(2, "DEV_ROOT")]
    assert _padroes(ast.parse("def f(*, d=None):\n    pass\n")) == []
    assert _funcoes_com_raiz(ast.parse(
        "class C:\n    def __init__(self, *, dev_root=None):\n        pass\n")) == {
        "C": {"dev_root"}}
