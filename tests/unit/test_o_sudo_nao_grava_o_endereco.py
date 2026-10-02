"""O sudo não grava o endereço — O-SUDO-NAO-GRAVA-O-ENDERECO-NO-DIARIO-01 (29/09/2026)."""

from __future__ import annotations

import ast
import contextlib
import functools
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    LinkDeRadio,
    PedidoAPonte,
    PontePrivilegiada,
    pedido_a_ponte,
)
from tests.unit.barramento_de_mentira import montar_adaptadores

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"


def _endereco(*baixos: str) -> str:
    """A faixa forjada ``e8:47:3a`` com os octetos 4 a 6 dados (ver o topo)."""
    return ":".join(("e8", "47", "3a", *baixos))


ADAPTADOR_A = _endereco("5a", "6b", "01")
ADAPTADOR_B = _endereco("5c", "6d", "02")
HCI = {ADAPTADOR_A: "hci5", ADAPTADOR_B: "hci6"}
CONTROLES = {
    _endereco("1a", "2b", "0a"): ADAPTADOR_A,
    _endereco("1c", "2d", "0b"): ADAPTADOR_A,
    _endereco("3e", "4f", "0c"): ADAPTADOR_B,
    _endereco("3a", "4b", "0d"): ADAPTADOR_B,
}
ENDERECOS = (ADAPTADOR_A, ADAPTADOR_B, *CONTROLES)

_M = r"\:".join([r"[0-9A-Fa-f][0-9A-Fa-f]"] * 6)
REGRA_VELHA = (
    "adaptadores",
    f"bonds {_M}",
    f"renomear {_M}",
    f"esquecer {_M} {_M}",
    f"parear {_M} {_M}",
    f"desconectar {_M} {_M}",
    "reiniciar-travado",
    "religar-orfaos",
    f"descobrir {_M} [0-9]",
    f"descobrir {_M} [0-9][0-9]",
    f"descobrir {_M} [0-9][0-9][0-9]",
)

SUDO_DE_MENTIRA = '''#!{python}
import fnmatch, json, os, re, subprocess, sys

registro = os.environ["HEFESTO_TESTE_SUDO_REGISTRO"]
raiz = os.environ["HEFESTO_TESTE_RAIZ"]


def anotar(**campos):
    with open(registro, "a", encoding="utf-8") as saida:
        saida.write(json.dumps(campos) + "\\n")


pedido = sys.argv[1:]
if (not os.environ.get("HEFESTO_BT_LIB", "").startswith(raiz + os.sep)
        or os.environ.get("SUDO_UID") or os.environ.get("SUDO_USER")):
    anotar(argv=pedido, veredito="guarda")
    sys.exit(97)
resto = list(pedido)
bandeiras = []
while resto and resto[0].startswith("-") and resto[0] != "--":
    bandeiras.append(resto.pop(0))
if resto[:1] == ["--"]:
    resto.pop(0)
lista = "-l" in bandeiras
with open(os.environ["HEFESTO_TESTE_SUDO_REGRAS"], encoding="utf-8") as arquivo:
    regras = json.load(arquivo)


def casa(regra, linha):
    return len(regra) == len(linha) and regra[0] == linha[0] and all(
        fnmatch.fnmatchcase(arg, re.sub(r"\\\\(.)", r"\\1", molde))
        for molde, arg in zip(regra[1:], linha[1:])
    )


aceito = "-n" in bandeiras and bool(resto) and any(casa(r, resto) for r in regras)
anotar(argv=pedido, lista=lista, veredito="aceito" if aceito else "recusado")
if not aceito:
    sys.exit(1)
if lista:
    print(" ".join(resto))
    sys.exit(0)
feito = subprocess.run(["bash", *resto], capture_output=True, text=True)
sys.stdout.write(feito.stdout)
sys.stderr.write(feito.stderr)
anotar(rodou=resto, rc=feito.returncode, saida=feito.stdout, erro=feito.stderr)
sys.exit(feito.returncode)
'''

PROGRAMA_DE_MENTIRA = """#!/usr/bin/env bash
printf '%s %s\\n' "${0##*/}" "$*" >>"${HEFESTO_TESTE_RAIZ:?}/programas"
exit 0
"""


def _regra_de_verdade() -> list[str]:
    """As linhas do ``Cmnd_Alias`` que o ``regra-sudo`` de verdade escreve."""
    feito = subprocess.run(
        ["bash", str(PONTE), "regra-sudo", "fulana"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "HEFESTO_BT_LOG_DEST": "none"},
    )
    assert feito.returncode == 0, feito.stderr
    alvo = re.search(r'^ALVO_INSTALADO="([^"]+)"', PONTE.read_text(encoding="utf-8"), re.M)
    assert alvo is not None
    linhas = []
    for linha in feito.stdout.splitlines():
        limpa = linha.strip().rstrip("\\").strip().rstrip(",").strip()
        if limpa.startswith(alvo.group(1) + " "):
            linhas.append(limpa[len(alvo.group(1)) + 1 :])
    assert len(linhas) >= 9, feito.stdout
    return linhas


@dataclass
class Mesa:
    """A árvore de mentira: o BlueZ em disco, o barramento, o sudo e os registros."""

    raiz: Path
    lib: Path
    registro: Path
    regras: Path
    log: Path
    diario_root: Path

    def usar_regra(self, linhas: tuple[str, ...] | list[str]) -> None:
        self.regras.write_text(
            json.dumps([[str(PONTE), *linha.split()] for linha in linhas]), encoding="utf-8"
        )

    def registros(self) -> list[dict[str, Any]]:
        if not self.registro.exists():
            return []
        texto = self.registro.read_text(encoding="utf-8")
        return [json.loads(linha) for linha in texto.splitlines()]

    def pedidos(self) -> list[dict[str, Any]]:
        return [r for r in self.registros() if "veredito" in r]

    def saidas(self) -> list[dict[str, Any]]:
        return [r for r in self.registros() if "rodou" in r]

    def bond(self, adaptador: str, controle: str) -> Path:
        return self.lib / adaptador.upper() / controle.upper()


def _gravar_bond(mesa: Mesa, adaptador: str, controle: str) -> None:
    pasta = mesa.bond(adaptador, controle)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "info").write_text(
        "[General]\nName=DualSense\n\n[LinkKey]\nKey=00\n", encoding="utf-8"
    )


@pytest.fixture()
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Mesa]:
    """O mundo inteiro de mentira, no ``os.environ``: os executores do produto"""
    raiz = tmp_path / "mesa"
    bin_ = raiz / "bin"
    bin_.mkdir(parents=True)
    sudo = bin_ / "sudo"
    sudo.write_text(SUDO_DE_MENTIRA.replace("{python}", sys.executable), encoding="utf-8")
    sudo.chmod(0o755)
    for nome in ("bluetoothctl", "hcitool", "btmgmt"):
        programa = bin_ / nome
        programa.write_text(PROGRAMA_DE_MENTIRA, encoding="utf-8")
        programa.chmod(0o755)
    barramento = montar_adaptadores(
        raiz, {HCI[ADAPTADOR_A]: (ADAPTADOR_A, "false"), HCI[ADAPTADOR_B]: (ADAPTADOR_B, "false")}
    )
    alvo = Mesa(
        raiz=raiz,
        lib=raiz / "bluetooth",
        registro=raiz / "sudo.jsonl",
        regras=raiz / "regras.json",
        log=raiz / "ponte.log",
        diario_root=raiz / "diario-root.jsonl",
    )
    alvo.lib.mkdir()
    alvo.usar_regra(_regra_de_verdade())
    for chave in ("SUDO_UID", "SUDO_USER", "HEFESTO_PONTE_DRY_RUN"):
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("HEFESTO_TESTE_SUDO_REGISTRO", str(alvo.registro))
    monkeypatch.setenv("HEFESTO_TESTE_RAIZ", str(raiz))
    monkeypatch.setenv("HEFESTO_TESTE_SUDO_REGRAS", str(alvo.regras))
    monkeypatch.setenv("HEFESTO_BT_LIB", str(alvo.lib))
    monkeypatch.setenv("HEFESTO_BT_BIN", str(barramento / "bin"))
    monkeypatch.setenv("BUSCTL_FALSO_RAIZ", str(barramento))
    monkeypatch.setenv("HEFESTO_BT_LOG_DEST", str(alvo.log))
    monkeypatch.setenv("HEFESTO_RADIO_DIARIO_ROOT", str(alvo.diario_root))
    monkeypatch.setenv("HEFESTO_BT_LAPIDES", str(raiz / "lapides"))
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(raiz / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(raiz / "radio-diario.jsonl"))
    yield alvo


def _pedacos(endereco: str) -> set[str]:
    """Os pedaços que o dono diz entregarem o 4.º ou o 5.º octeto, e o inteiro."""
    octetos = tuple(endereco.lower().split(":"))
    pedacos = set(formas_do_endereco(octetos))
    assert pedacos, "o endereço de mentira tem de ter o 4.º e o 5.º octetos não nulos"
    colado = endereco.replace(":", "")
    return pedacos | {endereco.lower(), endereco.upper(), colado.lower(), colado.upper()}


def _achados(texto: str) -> list[str]:
    """Os endereços (pelo índice, nunca o valor) que têm um pedaço no texto."""
    return [f"E{n}" for n, e in enumerate(ENDERECOS) if any(p in texto for p in _pedacos(e))]


def _o_sudo_so_viu_o_verbo(mesa: Mesa, quantos: int) -> None:
    """(a) nenhum pedaço de endereço no argv anotado; (b) o sudo aceitou todos."""
    pedidos = mesa.pedidos()
    assert len(pedidos) >= quantos, pedidos
    for pedido in pedidos:
        argv = " ".join(pedido["argv"])
        assert _achados(argv) == [], f"endereço no argv do sudo: {pedido['argv'][:5]}…"
        assert pedido["veredito"] == "aceito", f"a regra recusou: {pedido['argv'][:5]}…"


def _cada_controle() -> Iterator[tuple[str, str]]:
    yield from ((controle, adaptador) for controle, adaptador in CONTROLES.items())


def test_o_esquecer_da_central_so_manda_o_verbo(mesa: Mesa) -> None:
    """O ``esquecer_pela_ponte`` com o executor do produto: o bond daquele"""
    for controle in CONTROLES:
        for adaptador in (ADAPTADOR_A, ADAPTADOR_B):
            _gravar_bond(mesa, adaptador, controle)
    esquecidos: set[tuple[str, str]] = set()
    for controle, adaptador in _cada_controle():
        fez, motivo = cr.esquecer_pela_ponte(
            adaptador, controle, caminho=str(PONTE), correr=cr._correr_a_ponte
        )
        assert (fez, motivo) == (True, "")
        esquecidos.add((adaptador, controle))
        for outro in CONTROLES:
            for lugar in (ADAPTADOR_A, ADAPTADOR_B):
                assert mesa.bond(lugar, outro).exists() is ((lugar, outro) not in esquecidos)
    _o_sudo_so_viu_o_verbo(mesa, 4)


def test_o_esquecer_da_aba_so_manda_o_verbo(
    mesa: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O X da aba Conexões (``gesto_de_pareamento._esquecer_pela_ponte``) chega"""
    original = cr.esquecer_pela_ponte
    monkeypatch.setattr(
        cr,
        "esquecer_pela_ponte",
        functools.partial(original, caminho=str(PONTE), correr=cr._correr_a_ponte),
    )
    for controle, adaptador in _cada_controle():
        _gravar_bond(mesa, adaptador, controle)
        assert gp._esquecer_pela_ponte(adaptador, controle) == (True, "")
        assert not mesa.bond(adaptador, controle).exists()
    _o_sudo_so_viu_o_verbo(mesa, 4)


def test_a_busca_so_manda_o_verbo_e_os_segundos(
    mesa: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A janela de busca da ponte, sem dono, com o ``_abrir_de_verdade``: a"""
    monkeypatch.setenv("HEFESTO_PONTE_DRY_RUN", "1")
    for adaptador in (ADAPTADOR_A, ADAPTADOR_B):
        janela = gp.JanelaDeBusca(
            adaptador,
            5,
            caminho=str(PONTE),
            abrir=gp._abrir_de_verdade,
            correr=gp._correr_de_verdade,
        )
        assert not janela.pelo_dono
        assert janela.abrir_a_janela() == ""
        janela.esperar(teto=30)
        janela.fechar()
    saidas = mesa.saidas()
    assert [s["rodou"][1:] for s in saidas] == [["descobrir", "5"], ["descobrir", "5"]]
    for saida, adaptador in zip(saidas, (ADAPTADOR_A, ADAPTADOR_B), strict=True):
        assert saida["rc"] == 0, saida["erro"]
        assert f"(select {adaptador.upper()};" in saida["saida"]
    _o_sudo_so_viu_o_verbo(mesa, 2)


class _ProcessoVivo:
    """Uma janela aberta que não roda nada: o ``parear`` só corre dentro dela."""

    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self._vivo = True

    def poll(self) -> int | None:
        return None if self._vivo else 0

    def terminate(self) -> None:
        self._vivo = False

    kill = terminate

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_o_parear_so_manda_o_verbo(mesa: Mesa, monkeypatch: pytest.MonkeyPatch) -> None:
    """O ``parear`` da ponte, com o ``_correr_de_verdade``: o «faria» diz o"""
    monkeypatch.setenv("HEFESTO_PONTE_DRY_RUN", "1")
    for controle, adaptador in _cada_controle():
        janela = gp.JanelaDeBusca(
            adaptador,
            5,
            caminho=str(PONTE),
            abrir=lambda _pedido: _ProcessoVivo(),
            correr=gp._correr_de_verdade,
        )
        assert janela.abrir_a_janela() == ""
        assert janela.parear(controle).estado == gp.ESTADO_PAREOU
        janela.fechar()
    saidas = mesa.saidas()
    assert len(saidas) == 4
    for saida, (controle, adaptador) in zip(saidas, _cada_controle(), strict=True):
        objeto = f"/org/bluez/{HCI[adaptador]}/dev_{controle.upper().replace(':', '_')}"
        assert f"busctl call org.bluez {objeto} org.bluez.Device1 Pair" in saida["saida"]
    _o_sudo_so_viu_o_verbo(mesa, 4)


def test_o_desconectar_do_zumbi_so_manda_o_verbo(
    mesa: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``PontePrivilegiada`` sem executor: o «faria» derruba o link daquele"""
    monkeypatch.setenv("HEFESTO_PONTE_DRY_RUN", "1")
    ponte = PontePrivilegiada(caminho=str(PONTE))
    for controle, adaptador in _cada_controle():
        link = LinkDeRadio(hci=HCI[adaptador], adaptador=adaptador, controle=controle)
        assert ponte.desconectar(link) == (True, "")
    saidas = mesa.saidas()
    assert len(saidas) == 4
    for saida, (controle, adaptador) in zip(saidas, _cada_controle(), strict=True):
        assert f"hcitool -i {HCI[adaptador]} dc {controle.upper()}" in saida["saida"]
    _o_sudo_so_viu_o_verbo(mesa, 4)


class _NomesEmMemoria:
    """Os nomes dela, sem o ``maquina.json``: esta régua não é sobre eles."""

    def ler(self) -> dict[str, str]:
        return {}

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        return True


SUDO_PERMITIDO = Counter(
    {
        ("integrations/conexao_zumbi.py", "pedido_a_ponte"): 2,
        ("utils/memoria_dos_controles.py", "Sistema.rodar_parte_do_root"): 2,
    }
)


def _listas_de_sudo(arvore: ast.AST) -> list[str]:
    """``Classe.função`` de cada lista/tupla literal que começa com ``"sudo"``."""
    achados: list[str] = []
    pilha: list[str] = []

    class _Visita(ast.NodeVisitor):
        def _dentro(self, no: Any) -> None:
            pilha.append(no.name)
            self.generic_visit(no)
            pilha.pop()

        def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
            self._dentro(no)

        def visit_AsyncFunctionDef(self, no: ast.AsyncFunctionDef) -> None:
            self._dentro(no)

        def visit_ClassDef(self, no: ast.ClassDef) -> None:
            self._dentro(no)

        def _lista(self, no: ast.List | ast.Tuple) -> None:
            primeiro = no.elts[0] if no.elts else None
            if isinstance(primeiro, ast.Constant) and primeiro.value == "sudo":
                achados.append(".".join(pilha) or "<módulo>")
            self.generic_visit(no)

        def visit_List(self, no: ast.List) -> None:
            self._lista(no)

        def visit_Tuple(self, no: ast.Tuple) -> None:
            self._lista(no)

    _Visita().visit(arvore)
    return achados


def test_ninguem_mais_monta_o_sudo_da_ponte_no_src() -> None:
    """MORDIDA: um ``["sudo", "-n", "--", self.caminho, "parear", …]`` de volta"""
    pacote = RAIZ / "src" / "hefesto_dualsense4unix"
    achados: Counter[tuple[str, str]] = Counter()
    for arquivo in sorted(pacote.rglob("*.py")):
        rel = arquivo.relative_to(pacote).as_posix()
        for onde in _listas_de_sudo(ast.parse(arquivo.read_text(encoding="utf-8"))):
            achados[(rel, onde)] += 1
    assert achados == SUDO_PERMITIDO


def test_a_regua_da_ast_ve_a_lista_montada_a_mao() -> None:
    """A régua acima não mede o vazio: a forma velha do parear é achada."""
    velho = 'def parear(self):\n    return ["sudo", "-n", "--", self.caminho, "parear"]\n'
    assert _listas_de_sudo(ast.parse(velho)) == ["parear"]


_VERBOS_COM_ENDERECO = frozenset(
    {"bonds", "renomear", "esquecer", "parear", "desconectar", "descobrir"}
)


def _sudo_da_ponte_montado_a_mao(arvore: ast.AST) -> list[int]:
    """A linha de cada lista/tupla literal que começa com ``"sudo"`` e nomeia"""
    linhas = []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.List, ast.Tuple)) or not no.elts:
            continue
        primeiro = no.elts[0]
        if not (isinstance(primeiro, ast.Constant) and primeiro.value == "sudo"):
            continue
        if any(
            isinstance(e, ast.Constant) and e.value in _VERBOS_COM_ENDERECO for e in no.elts[1:]
        ):
            linhas.append(no.lineno)
    return linhas


def test_nenhum_script_python_monta_o_sudo_da_ponte() -> None:
    """Os ``scripts/`` em Python passam pelo dono (``pedido_a_ponte``), como a"""
    achados = []
    for arquivo in sorted((RAIZ / "scripts").rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = arquivo.relative_to(RAIZ)
        achados += [f"{rel}:{n}" for n in _sudo_da_ponte_montado_a_mao(arvore)]
    assert achados == []


def test_a_regua_dos_scripts_python_ve_a_lista_da_ponte() -> None:
    """A régua acima não mede o vazio: a forma velha da bancada é achada, e o"""
    velho = 'subprocess.run(["sudo", "-n", ponte, "esquecer", endereco, mac])\n'
    outro = 'subprocess.run(["sudo", "-n", "hcitool", "con"])\n'
    assert _sudo_da_ponte_montado_a_mao(ast.parse(velho)) == [1]
    assert _sudo_da_ponte_montado_a_mao(ast.parse(outro)) == []


_PONTE_E_ARGUMENTO = re.compile(
    r"(?:bt_ponte_privilegiada\.sh|\$\{?(?:PONTE|ALVO_INSTALADO)\}?|\{ponte\})[\"']?"
    r"\s+(?:--dry-run\s+)?(bonds|renomear|esquecer|parear|desconectar|descobrir)\b"
    r"[ \t]*(<[^>\s]+>|[^\s\"'|;&)<>`,\\]+)?"
)
_SEGUNDOS = re.compile(r"\d{1,3}|<seg\w*>|(\[0-9\]){1,3}|\$\{?\w*seg\w*\}?", re.I)


def ponte_com_endereco_no_argv(texto: str) -> list[str]:
    """As linhas que chamam a ponte com um argumento que não é os segundos."""
    achados = []
    for n, linha in enumerate(texto.splitlines(), 1):
        for m in _PONTE_E_ARGUMENTO.finditer(linha):
            verbo, argumento = m.group(1), m.group(2)
            if not argumento:
                continue
            if verbo == "descobrir" and _SEGUNDOS.fullmatch(argumento):
                continue
            achados.append(f"{n}: {verbo} {argumento}")
    return achados


def test_nenhum_gesto_escrito_manda_o_endereco_no_argv() -> None:
    """``scripts/``, o install, o uninstall e as páginas de uso: nenhum gesto"""
    alvos = [RAIZ / "install.sh", RAIZ / "uninstall.sh"]
    for pasta in ("scripts", "docs/usage"):
        alvos += [
            p
            for p in sorted((RAIZ / pasta).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        ]
    achados = []
    for arquivo in alvos:
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        achados += [f"{arquivo.relative_to(RAIZ)}:{a}" for a in ponte_com_endereco_no_argv(texto)]
    assert achados == []


def test_a_varredura_de_scripts_ve_a_forma_velha() -> None:
    """A régua acima não mede o vazio: as três formas velhas são achadas, e as"""
    velhas = (
        'warn "… sudo /x/bt_ponte_privilegiada.sh esquecer <adaptador-que-sai> ${mac}"',
        'print(f"    sudo {ponte} esquecer {end} {mac}")',
        "    ${ALVO_INSTALADO} esquecer ${m} ${m}, \\",
    )
    novas = (
        "printf '%s\\n%s\\n' <a> ${mac} | sudo /usr/x/bt_ponte_privilegiada.sh esquecer\"",
        "    ${ALVO_INSTALADO} esquecer, \\",
        "    ${ALVO_INSTALADO} descobrir [0-9][0-9], \\",
        '"${PONTE}" religar-orfaos',
    )
    assert all(ponte_com_endereco_no_argv(linha) for linha in velhas)
    assert not any(ponte_com_endereco_no_argv(linha) for linha in novas)


def test_a_regra_nao_tem_argumento_livre() -> None:
    """Toda linha é ``<ponte> <verbo>`` ou ``<ponte> descobrir <largura>``, e"""
    for linha in _regra_de_verdade():
        partes = linha.split()
        assert "A-F" not in linha and "\\:" not in linha, linha
        if partes[0] == "descobrir":
            assert len(partes) == 2 and re.fullmatch(r"(\[0-9\]){1,3}", partes[1]), linha
        else:
            assert len(partes) == 1, linha


def _pedidos_de_cada_verbo() -> list[PedidoAPonte]:
    controle, adaptador = next(_cada_controle())
    caminho = str(PONTE)
    return [
        pedido_a_ponte("esquecer", adaptador, controle, caminho=caminho),
        pedido_a_ponte("parear", adaptador, controle, caminho=caminho),
        pedido_a_ponte("desconectar", adaptador, controle, caminho=caminho),
        pedido_a_ponte("descobrir", adaptador, segundos=30, caminho=caminho),
        pedido_a_ponte("bonds", adaptador, caminho=caminho),
        pedido_a_ponte("renomear", adaptador, nome="Rack 1", caminho=caminho),
    ]


def _sonda(pedido: PedidoAPonte) -> int:
    return subprocess.run(
        list(pedido.sonda), capture_output=True, text=True, timeout=30, check=False
    ).returncode


def test_a_sonda_de_cada_pedido_e_o_argv_com_l(mesa: Mesa) -> None:
    """A sonda é a MESMA linha do pedido, com ``-l``: casa a regra nova, e NÃO"""
    for pedido in _pedidos_de_cada_verbo():
        assert pedido.sonda == (*pedido.argv[:2], "-l", *pedido.argv[2:])
        assert _sonda(pedido) == 0, pedido.argv
    mesa.usar_regra(REGRA_VELHA)
    for pedido in _pedidos_de_cada_verbo():
        assert _sonda(pedido) == 1, pedido.argv
    controle, adaptador = next(_cada_controle())
    velho = ("sudo", "-n", "--", str(PONTE), "esquecer", adaptador.upper(), controle.upper())
    assert subprocess.run(
        [*velho[:2], "-l", *velho[2:]], capture_output=True, timeout=30, check=False
    ).returncode == 0


def test_a_porta_pergunta_a_linha_do_pedido(mesa: Mesa) -> None:
    """Os ``impedimentos`` do zumbi e do pareamento, perguntados ao sudo de"""
    ponte = PontePrivilegiada(caminho=str(PONTE))
    assert ponte.impedimentos() == []
    assert gp.impedimentos(str(PONTE)) == []
    mesa.usar_regra(REGRA_VELHA)
    for motivos in (ponte.impedimentos(), gp.impedimentos(str(PONTE))):
        assert len(motivos) == 1 and "sudo sem senha" in motivos[0], motivos
    listas = [p for p in mesa.pedidos() if p.get("lista")]
    assert listas and all(p["argv"][:3] == ["-n", "-l", "--"] for p in listas)


def _ponte(mesa: Mesa, *argv: str, entrada: str) -> subprocess.CompletedProcess[str]:
    """A ponte da árvore, sem sudo, com o ambiente da ``mesa`` (a fixture)."""
    assert mesa.lib.is_dir()
    return subprocess.run(
        ["bash", str(PONTE), *argv],
        input=entrada,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_o_registro_da_ponte_diz_o_verbo_e_o_hci(mesa: Mesa) -> None:
    """Cada verbo, de verdade, na árvore de mentira: a linha do registro existe,"""
    controle, adaptador = next(_cada_controle())
    _gravar_bond(mesa, adaptador, controle)
    hci = HCI[adaptador]
    passos = (
        (("esquecer",), f"{adaptador}\n{controle}\n", f"um controle esquecido do adaptador {hci}"),
        (("parear",), f"{adaptador}\n{controle}\n", f"pareado e confiado no adaptador {hci}"),
        (("desconectar",), f"{adaptador}\n{controle}\n", f"derrubado no adaptador {hci}"),
        (("renomear",), f"{adaptador}\nRack 1\n", f"o adaptador {hci} foi renomeado"),
        (("descobrir", "1"), f"{adaptador}\n", f"janela de busca fechada no adaptador {hci}"),
    )
    for argv, entrada, frase in passos:
        feito = _ponte(mesa, *argv, entrada=entrada)
        assert feito.returncode == 0, (argv, feito.stderr)
        registro = mesa.log.read_text(encoding="utf-8")
        assert frase in registro, (argv, registro)
    assert _achados(mesa.log.read_text(encoding="utf-8")) == []


def test_o_adaptador_fora_da_mesa_sai_sem_endereco(mesa: Mesa) -> None:
    """O ``esquecer`` age no disco com o adaptador fora da mesa: a linha diz"""
    fora = _endereco("7e", "8f", "03")
    controle = next(iter(CONTROLES))
    _gravar_bond(mesa, fora, controle)
    feito = _ponte(mesa, "esquecer", entrada=f"{fora}\n{controle}\n")
    assert feito.returncode == 0, feito.stderr
    assert not mesa.bond(fora, controle).exists()
    registro = mesa.log.read_text(encoding="utf-8")
    assert "um controle esquecido de um adaptador fora da mesa" in registro
    assert [p for p in _pedacos(fora) | _pedacos(controle) if p in registro] == []
    [linha] = diario_do_radio.ler(caminhos=[mesa.diario_root])
    assert linha["o_que"] == "esqueceu o controle"
    assert (linha["adaptador"], linha["controle"]) == (fora.upper(), controle.upper())


def _carregar_a_regua_da_maquina() -> ModuleType:
    nome = "_regua_da_maquina_do_sudo"
    spec = importlib.util.spec_from_file_location(
        nome, RAIZ / "scripts" / "check_o_endereco_dela_em_toda_forma.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _uuid(ultimo_grupo: str, *, versao: str) -> str:
    return "-".join(("1b4e28ba", "2fa1", f"{versao}d2e", "883f", ultimo_grupo))


@pytest.fixture()
def lar(tmp_path: Path) -> Path:
    """Um lar com dois controles da faixa forjada e o ``boot_id`` de um UUID v4"""
    config = tmp_path / "lar" / ".config" / "hefesto-dualsense4unix"
    config.mkdir(parents=True)
    dois = list(CONTROLES)[:2]
    (config / "controllers.json").write_text(
        json.dumps(
            {
                "boot_id": _uuid("e8473a9c7b21", versao="4"),
                "controles": [{"mac": c.upper(), "slot": n} for n, c in enumerate(dois, 1)],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path / "lar"


def _medir(lar: Path, linha: str, tmp_path: Path) -> tuple[int, str]:
    regua = _carregar_a_regua_da_maquina()
    arquivo = tmp_path / "diario.txt"
    arquivo.write_text(linha + "\n", encoding="utf-8")
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = regua.main(["--lar", str(lar), "--arquivo", str(arquivo)])
    return codigo, saida.getvalue()


def test_a_regua_da_maquina_le_o_lar_sem_o_uuid(lar: Path) -> None:
    """Os endereços do lar são os dois controles, e o UUID não entra."""
    regua = _carregar_a_regua_da_maquina()
    reais = regua.enderecos_da_maquina(lar)
    assert reais == {tuple(c.split(":")) for c in list(CONTROLES)[:2]}


def test_a_linha_do_outro_boot_nao_acusa(lar: Path, tmp_path: Path) -> None:
    """O falso positivo do achado: ``arquivo_boot=<o mesmo UUID>`` dá rc=0."""
    boot = _uuid("e8473a9c7b21", versao="4")
    linha = f"identity_slots_restaurados_de_outro_boot arquivo_boot={boot}"
    codigo, saida = _medir(lar, linha, tmp_path)
    assert codigo == 0, saida


def test_o_endereco_do_lar_acusa(lar: Path, tmp_path: Path) -> None:
    controle = next(iter(CONTROLES))
    codigo, saida = _medir(lar, f"uhid_device_created mac={controle.upper()}", tmp_path)
    assert codigo == 1, saida


def test_o_uuid_v1_com_o_endereco_do_lar_acusa(lar: Path, tmp_path: Path) -> None:
    """Um UUID de versão 1 carrega um endereço no último grupo: na varredura, o"""
    controle = next(iter(CONTROLES))
    linha = f"sessao={_uuid(controle.replace(':', ''), versao='1')}"
    codigo, saida = _medir(lar, linha, tmp_path)
    assert codigo == 1, saida


SUDO_QUE_ANOTA = """#!/usr/bin/env bash
[[ -d "${HEFESTO_TESTE_BLUEZ:-}" ]] || exit 97
printf '%s\\n' "$*" >> "${HEFESTO_TESTE_SUDO_ANOTADO}"
args=()
for a in "$@"; do
    [[ "$a" == "-n" ]] && continue
    args+=("${a//\\/var\\/lib\\/bluetooth/${HEFESTO_TESTE_BLUEZ}}")
done
exec "${args[@]}"
"""

_INFO_HID = (
    "[General]\nName=DualSense\nServices=00001124-0000-1000-8000-00805f9b34fb;\n\n"
    "[LinkKey]\nKey=00\n"
)


def test_o_doctor_le_o_cache_sdp_sem_endereco_no_argv(tmp_path: Path) -> None:
    """Os quatro controles nos dois adaptadores: dois com o cache sem"""
    bluez = tmp_path / "bluetooth"
    controles = list(CONTROLES.items())
    estado_do_cache = ("envenenado", "envenenado", "sao", "sem")
    for (controle, adaptador), estado in zip(controles, estado_do_cache, strict=True):
        pasta = bluez / adaptador.upper() / controle.upper()
        pasta.mkdir(parents=True)
        (pasta / "info").write_text(_INFO_HID, encoding="utf-8")
        cache = bluez / adaptador.upper() / "cache"
        cache.mkdir(exist_ok=True)
        if estado == "envenenado":
            (cache / controle.upper()).write_text("[General]\nName=DualSense\n", encoding="utf-8")
        elif estado == "sao":
            (cache / controle.upper()).write_text(
                "[General]\nName=DualSense\n\n[ServiceRecords]\n0x00010000=00\n",
                encoding="utf-8",
            )
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    sudo = bin_ / "sudo"
    sudo.write_text(SUDO_QUE_ANOTA, encoding="utf-8")
    sudo.chmod(0o755)
    anotado = tmp_path / "sudo.txt"
    feito = subprocess.run(
        ["bash", "-c", 'set --; source "$DOCTOR_SH"; check_bt_sdp_cache_envenenado'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            "PATH": f"{bin_}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "HOME": str(tmp_path / "lar-vazio"),
            "DOCTOR_SH": str(RAIZ / "scripts" / "doctor.sh"),
            "HEFESTO_TESTE_BLUEZ": str(bluez),
            "HEFESTO_TESTE_SUDO_ANOTADO": str(anotado),
        },
    )
    chamadas = anotado.read_text(encoding="utf-8") if anotado.exists() else ""
    assert "/var/lib/bluetooth" in chamadas, f"o doctor não leu o BlueZ pelo sudo: {feito.stdout}"
    assert _achados(chamadas) == [], f"endereço no argv do sudo do doctor: {_achados(chamadas)}"
    acusados = [c for c, _ in controles if f"cache SDP de {c.upper()} SEM" in feito.stdout]
    assert acusados == [c for c, _ in controles[:2]], feito.stdout
