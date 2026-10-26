"""O grafo do som se lê por um dono só (O-GRAFO-DO-SOM-SE-LE-POR-UM-DONO-SO-01).

O dono é ``retrato_do_som.ler_o_pw_dump``: a guarda da suíte, a falta da ferramenta, o
prazo e o UTF-8 moram nele. ``alto_falante_bt.origem_do_gravador`` e
``endpoint_de_haptica.conferir_o_destino_do_tocador`` pedem o grafo pela porta
(``porta_do_som.ler_o_grafo``), que chama o dono. A varredura reprova o segundo leitor.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import haptica_do_cabo as hc
from hefesto_dualsense4unix.integrations import retrato_do_som as rs
from hefesto_dualsense4unix.integrations import transiente_do_jogo as td

SRC = Path(rs.__file__).resolve().parents[1]
FERRAMENTA = "pw-dump"

DONO: frozenset[tuple[str, str]] = frozenset({
    ("integrations/retrato_do_som.py", "ler_o_pw_dump"),
    ("integrations/retrato_do_som.py", "_ler_o_grafo"),
})

MESA = (
    ("P1", "APARELHOGHJKMN", "cabo"),
    ("P2", "APARELHOPQRSTU", "radio"),
    ("P3", "APARELHOVWXYZG", "cabo"),
    ("P4", "APARELHOHJKMNP", "radio"),
)


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corpo = no.body
            if (corpo and isinstance(corpo[0], ast.Expr)
                    and isinstance(corpo[0].value, ast.Constant)):
                ids.add(id(corpo[0].value))
    return ids


def _nomeia_a_ferramenta(valor: object) -> bool:
    if not isinstance(valor, str) or not valor.strip():
        return False
    return os.path.basename(valor.split()[0]) == FERRAMENTA


def leitores_do_grafo(fonte: str, arquivo: str) -> list[tuple[str, int, str]]:
    """``(arquivo, linha, função)`` de cada texto que nomeia a ferramenta fora de docstring."""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    achados: list[tuple[str, int, str]] = []

    def visitar(no: ast.AST, funcao: str) -> None:
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitar(filho, filho.name)
                continue
            if (isinstance(filho, ast.Constant) and id(filho) not in docs
                    and _nomeia_a_ferramenta(filho.value)):
                achados.append((arquivo, filho.lineno, funcao))
            visitar(filho, funcao)

    visitar(arvore, "<módulo>")
    return achados


def _segundos_leitores() -> list[tuple[str, int, str]]:
    fora: list[tuple[str, int, str]] = []
    for caminho in sorted(SRC.rglob("*.py")):
        rel = caminho.relative_to(SRC).as_posix()
        for achado in leitores_do_grafo(caminho.read_text(encoding="utf-8"), rel):
            if (achado[0], achado[2]) not in DONO:
                fora.append(achado)
    return fora


def test_nenhum_segundo_leitor_do_grafo_em_src() -> None:
    fora = _segundos_leitores()
    assert not fora, (
        "o grafo do som tem um dono só (retrato_do_som.ler_o_pw_dump); "
        f"leitores fora dele: {fora}"
    )


def test_o_dono_esta_na_varredura() -> None:
    """A varredura enxerga o dono: sem isso, um verde dela não diz nada."""
    rel = "integrations/retrato_do_som.py"
    achados = leitores_do_grafo((SRC / rel).read_text(encoding="utf-8"), rel)
    assert {(a, f) for a, _l, f in achados} == set(DONO), achados


@pytest.mark.parametrize("trecho", [
    'import subprocess\ndef f():\n    return subprocess.run(["pw-dump"], check=False)\n',
    "import asyncio\nasync def f():\n"
    "    await asyncio.create_subprocess_exec(\"/usr/bin/pw-dump\")\n",
    'import shutil\nARGV = ("pw-dump", "-m")\ndef f():\n    return shutil.which("pw-dump")\n',
])
def test_a_varredura_reprova_o_segundo_leitor(trecho: str) -> None:
    """A régua morde a forma que a cura arrancou (e as vizinhas: Popen, asyncio, tupla)."""
    assert leitores_do_grafo(trecho, "integrations/outro.py"), trecho


def test_a_varredura_nao_conta_docstring() -> None:
    trecho = 'def f():\n    """pw-dump é só um nome aqui."""\n    return None\n'
    assert leitores_do_grafo(trecho, "integrations/outro.py") == []


def _no(ident: int, serial: int, nome: str) -> dict[str, Any]:
    return {"id": ident, "type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": nome, "object.serial": serial}}}


def _link(de: int, para: int) -> dict[str, Any]:
    return {"id": 9000 + de * 10 + para, "type": "PipeWire:Interface:Link",
            "info": {"output-node-id": de, "input-node-id": para, "props": {}}}


def _gravador(marca: str, transporte: str) -> tuple[str, str]:
    """``(rótulo do gravador, nó que ele tem de ouvir)``: a ponte do rádio, o laço do cabo."""
    if transporte == "radio":
        return f"hefesto-ponte-{marca}-som", f"{afb.PREFIXO_SINK_DO_SOM}{marca}"
    return hc.no_de_captura(marca), eh.nome_da_marca(marca)


def _grafo_da_mesa() -> tuple[str, dict[str, afb.OrigemDoGravador], dict[str, str]]:
    """O grafo da mesa mista, os gravadores com a origem certa, e os tocadores com o destino."""
    objetos: list[dict[str, Any]] = []
    origens: dict[str, afb.OrigemDoGravador] = {}
    destinos: dict[str, str] = {}
    for i, (_assento, marca, transporte) in enumerate(MESA):
        rotulo, alvo = _gravador(marca, transporte)
        endpoint = eh.nome_da_marca(marca)
        tocador = eh.rotulo_do_tocador(marca)
        base = 100 * (i + 1)
        objetos += [_no(base, base + 7, alvo), _no(base + 1, base + 8, rotulo),
                    _link(base, base + 1)]
        if alvo != endpoint:
            objetos.append(_no(base + 2, base + 9, endpoint))
            id_endpoint = base + 2
        else:
            id_endpoint = base
        objetos += [_no(base + 3, base + 10, tocador), _link(base + 3, id_endpoint)]
        origens[rotulo] = afb.OrigemDoGravador(base, base + 7, alvo)
        destinos[tocador] = endpoint
    objetos += [_no(171, 719, "Sackboy™: A Big Adventure"), _link(171, 202)]
    return json.dumps(objetos, ensure_ascii=False), origens, destinos


class _Armadilha:
    """O ``subprocess.run`` do processo inteiro: conta quem chamou a ferramenta do grafo."""

    def __init__(self, saida: str | None = None) -> None:
        self.saida = saida
        self.chamadas: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: Any, *_a: object, **k: Any) -> SimpleNamespace:
        lista = [str(x) for x in argv]
        if lista and os.path.basename(lista[0]) == FERRAMENTA:
            self.chamadas.append((lista, k))
            return SimpleNamespace(returncode=0, stdout=self.saida or "", stderr="")
        raise AssertionError(f"a régua não esperava este processo: {lista}")


@pytest.fixture
def armadilha(monkeypatch: pytest.MonkeyPatch) -> _Armadilha:
    trap = _Armadilha()
    monkeypatch.setattr("subprocess.run", trap)
    return trap


class _Dono:
    """O dono trocado por um dublê que conta as chamadas."""

    def __init__(self) -> None:
        self.saida: str | None = None
        self.chamadas = 0

    def __call__(self) -> str | None:
        self.chamadas += 1
        return self.saida


@pytest.fixture
def dono(monkeypatch: pytest.MonkeyPatch) -> _Dono:
    duble = _Dono()
    monkeypatch.setattr(rs, "ler_o_pw_dump", duble)
    return duble


def test_a_mesa_mista_le_o_grafo_so_pelo_dono(
    dono: _Dono, armadilha: _Armadilha
) -> None:
    """P1 a P4, cabo e rádio: a ponte, o laço e o tocador conferem pela identidade, no dono."""
    dono.saida, origens, destinos = _grafo_da_mesa()
    for rotulo, esperada in origens.items():
        assert afb.origem_do_gravador(rotulo) == esperada, rotulo
        assert afb.conferir_o_alvo_do_gravador(rotulo) == esperada.nome, rotulo
    for tocador, endpoint in destinos.items():
        assert eh.conferir_o_destino_do_tocador(tocador) == endpoint, tocador
    assert dono.chamadas == 2 * len(origens) + len(destinos), "alguém não perguntou ao dono"
    assert armadilha.chamadas == [], "um segundo leitor rodou a ferramenta fora do dono"


def _sink_do_controle(i: int, marca: str, transporte: str) -> str:
    """O nó de som em que o estalo do tato toca: o do rádio é nosso, o do cabo é do ALSA."""
    if transporte == "radio":
        return f"{afb.PREFIXO_SINK_DO_SOM}{marca}"
    return f"alsa_output.usb-Sony_DualSense-0{i}.analog-surround-40"


def test_o_ouvido_e_o_estalo_do_tato_leem_pelo_dono(
    dono: _Dono, armadilha: _Armadilha
) -> None:
    """O ouvido e o estalo do tato, P1 a P4 na mesa mista, pelo dono.

    O ouvido confere o fluxo do jogo pela identidade (o nome com ™ se perdeu no ``pactl``),
    e o estalo de cada assento confere o nó dele. Uma leitura por pergunta.
    """
    grafo, _origens, _destinos = _grafo_da_mesa()
    objetos = json.loads(grafo)
    objetos += [_no(181, 819, td.ROTULO_DO_OUVIDO), _link(171, 181)]
    estalos: dict[str, str] = {}
    for i, (_assento, marca, transporte) in enumerate(MESA):
        sink = _sink_do_controle(i + 1, marca, transporte)
        base = 500 + 10 * i
        rotulo = td.rotulo_do_estalo(sink)
        objetos += [_no(base, base + 1000, sink), _no(base + 1, base + 1001, rotulo),
                    _link(base + 1, base)]
        estalos[rotulo] = sink
    dono.saida = json.dumps(objetos, ensure_ascii=False)

    origem = td.conferir_o_alvo_do_ouvido(td.ROTULO_DO_OUVIDO)
    assert origem == afb.OrigemDoGravador(171, 719, "Sackboy™: A Big Adventure")
    pedido = td.FluxoDoJogo(indice=7, serial=719, nome="", pid=4242, ident=171,
                            nome_perdido=True)
    assert td.e_o_fluxo_pedido(origem, pedido) is True
    outro = td.FluxoDoJogo(indice=8, serial=720, nome="", pid=4242, ident=172,
                           nome_perdido=True)
    assert td.e_o_fluxo_pedido(origem, outro) is False
    for rotulo, sink in estalos.items():
        assert td.conferir_o_destino_do_estalo(rotulo) == sink, rotulo
    assert dono.chamadas == 1 + len(estalos), "uma pergunta sem o dono, ou com duas leituras"
    assert armadilha.chamadas == []

    dono.saida = None
    assert td.conferir_o_alvo_do_ouvido(td.ROTULO_DO_OUVIDO) is None
    assert td.e_o_fluxo_pedido(None, pedido) is None
    assert td.conferir_o_destino_do_estalo(next(iter(estalos))) is None


@pytest.mark.parametrize("saida", [None, "", "pw-dump: sem conexão", '{"não": "lista"}'])
def test_sem_grafo_os_dois_dizem_nao_sei(
    saida: str | None, dono: _Dono, armadilha: _Armadilha
) -> None:
    dono.saida = saida
    _grafo, origens, destinos = _grafo_da_mesa()
    rotulo, tocador = next(iter(origens)), next(iter(destinos))
    assert afb.origem_do_gravador(rotulo) is None
    assert afb.conferir_o_alvo_do_gravador(rotulo) is None
    assert eh.conferir_o_destino_do_tocador(tocador) is None
    assert dono.chamadas == 3
    assert armadilha.chamadas == []


def test_rotulo_vazio_nem_pergunta(dono: _Dono, armadilha: _Armadilha) -> None:
    dono.saida = _grafo_da_mesa()[0]
    assert afb.origem_do_gravador("") is None
    assert eh.conferir_o_destino_do_tocador("") is None
    assert dono.chamadas == 0 and armadilha.chamadas == []


def test_o_leitor_injetado_vence_o_dono(dono: _Dono) -> None:
    grafo, origens, destinos = _grafo_da_mesa()
    rotulo, tocador = next(iter(origens)), next(iter(destinos))
    assert afb.origem_do_gravador(rotulo, ler_o_grafo=lambda: grafo) == origens[rotulo]
    assert eh.conferir_o_destino_do_tocador(tocador, ler_o_grafo=lambda: grafo) == (
        destinos[tocador])
    assert dono.chamadas == 0


@pytest.fixture
def com_a_ferramenta(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ferramenta «existe»: só a guarda da suíte fica entre o teste e o grafo real."""
    real = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda nome, *a, **k: f"/usr/bin/{nome}" if nome == FERRAMENTA
        else real(nome, *a, **k))


@pytest.mark.usefixtures("com_a_ferramenta")
def test_com_a_suite_rodando_os_dois_dizem_nao_sei_sem_ler(armadilha: _Armadilha) -> None:
    armadilha.saida, origens, destinos = _grafo_da_mesa()
    assert bd.a_suite_esta_rodando() is True
    for rotulo in origens:
        assert afb.origem_do_gravador(rotulo) is None
        assert afb.conferir_o_alvo_do_gravador(rotulo) is None
    for tocador in destinos:
        assert eh.conferir_o_destino_do_tocador(tocador) is None
    assert armadilha.chamadas == [], "a suíte leu o grafo da máquina"


@pytest.mark.usefixtures("com_a_ferramenta")
def test_fora_da_suite_o_dono_le_uma_vez_por_pergunta_com_o_prazo_dele(
    armadilha: _Armadilha, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metade que prova a de cima: tirada a guarda, a armadilha VÊ o dono ler."""
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    armadilha.saida, origens, destinos = _grafo_da_mesa()
    rotulo, tocador = next(iter(origens)), next(iter(destinos))
    assert afb.origem_do_gravador(rotulo) == origens[rotulo]
    assert eh.conferir_o_destino_do_tocador(tocador) == destinos[tocador]
    assert [argv for argv, _k in armadilha.chamadas] == [[FERRAMENTA], [FERRAMENTA]]
    for _argv, k in armadilha.chamadas:
        assert k.get("timeout") == rs.TETO_DA_LEITURA_S, k
        assert k.get("encoding") == "utf-8" and k.get("errors") == "replace", k
