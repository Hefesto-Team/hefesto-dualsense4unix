#!/usr/bin/env python3
"""O censo de coleta: todo módulo de teste versionado aparece na coleta sem GTK, ou diz por que não.

O julgamento tem UM dono, este arquivo, e dois chamadores:

  - em casa (portão `coleta-sem-gtk`): `python3 scripts/check_a_coleta_sem_gtk.py` coleta a suíte com o
    `gi` e o `cairo` bloqueados (o ambiente do lint-test) e julga a saída;
  - no CI (passo «Censo de coleta» do lint-test): o passo coleta no runner e chama
    `python3 scripts/check_a_coleta_sem_gtk.py --julgar /tmp/coleta.txt`.

A coleta carrega ESTE arquivo como plugin do pytest (`-p scripts.check_a_coleta_sem_gtk`): ele anota, módulo
a módulo, o que a coleta fez, e escreve na saída as linhas `CENSO …`. Sem ele a saída não diz de qual módulo é
cada pulo (`exigir_gi_real()` pula pelo `tests/conftest.py`, e o `-rs` aponta para o conftest), e um módulo
pulado de propósito se lê igual a um módulo que sumiu.

O que reprova: módulo versionado que não deu nó nenhum NEM aparece como pulado com motivo (sumiu calado:
um `collect_ignore` num conftest, um `python_files` mudado, um arquivo que o pytest deixou de achar); módulo
que coleta sem nenhum teste; erro de coleta. Não há número escrito num dia: o número que cai com a árvore
(o piso do passo antigo) caducou três vezes e meia sem ninguém ver.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = "scripts.check_a_coleta_sem_gtk"

_SEM_GTK = '''\
import sys


class _SemGtk:
    """O ambiente do lint-test: sem PyGObject e sem pycairo."""

    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split(".")[0] in ("gi", "cairo"):
            # No runner o pacote não existe: é ModuleNotFoundError, que é o
            # que o `pytest.importorskip` pula (um ImportError qualquer ele não pula).
            raise ModuleNotFoundError(f"No module named {nome!r}", name=nome)
        return None


sys.meta_path.insert(0, _SemGtk())
'''

# --- o lado do pytest: o plugin -----------------------------------------------------------------
_PULADOS: dict[str, str] = {}
_VAZIOS: set[str] = set()


def _motivo(report) -> str:  # type: ignore[no-untyped-def]
    repr_ = getattr(report, "longrepr", None)
    texto = repr_[2] if isinstance(repr_, tuple) and len(repr_) >= 3 else str(repr_ or "")
    return " ".join(str(texto).replace("Skipped:", "", 1).split())[:200]


def pytest_collectreport(report) -> None:  # type: ignore[no-untyped-def]
    """Um módulo que a coleta PULOU de ponta a ponta, com a razão."""
    nodeid = getattr(report, "nodeid", "")
    if not (nodeid.endswith(".py") and "::" not in nodeid):
        return
    if getattr(report, "skipped", False):
        _PULADOS[nodeid] = _motivo(report) or "(sem motivo)"
    elif getattr(report, "passed", False) and not list(getattr(report, "result", None) or []):
        _VAZIOS.add(nodeid)


def pytest_report_collectionfinish(config, start_path, items) -> list[str]:  # type: ignore[no-untyped-def]
    """As linhas do censo: só o que foge do comum (pulado, vazio) e a marca de que o plugin rodou."""
    linhas = ["CENSO ativo"]
    for modulo in sorted(_PULADOS):
        linhas.append(f"CENSO pulado {modulo} :: {_PULADOS[modulo]}")
    for modulo in sorted(_VAZIOS):
        linhas.append(f"CENSO vazio {modulo}")
    return linhas


# --- o julgamento ------------------------------------------------------------------------------
_RE_NO = re.compile(r"^(tests/[^\s:]+\.py)::")
_RE_PULADO = re.compile(r"^CENSO pulado (\S+) :: ?(.*)$")
_RE_VAZIO = re.compile(r"^CENSO vazio (\S+)\s*$")


def versionados() -> list[str]:
    """Os `tests/**/test_*.py` do índice do git; sem git, os do disco."""
    try:
        saida = subprocess.run(
            ["git", "ls-files", "tests"], cwd=RAIZ, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        saida = [str(p.relative_to(RAIZ)) for p in (RAIZ / "tests").rglob("*.py")]
    return sorted(p for p in saida if p.endswith(".py") and Path(p).name.startswith("test_"))


def julgar(saida: str, modulos: list[str]) -> tuple[list[str], int, int]:
    """(as queixas, os testes coletados, os módulos pulados com motivo) da saída de uma coleta."""
    linhas = saida.splitlines()
    com_nos: dict[str, int] = {}
    pulados: dict[str, str] = {}
    vazios: list[str] = []
    erros = [ln for ln in linhas if ln.startswith("ERROR ")]
    for ln in linhas:
        if (m := _RE_NO.match(ln)) is not None:
            com_nos[m.group(1)] = com_nos.get(m.group(1), 0) + 1
        elif (m := _RE_PULADO.match(ln)) is not None:
            pulados[m.group(1)] = m.group(2).strip()
        elif (m := _RE_VAZIO.match(ln)) is not None:
            vazios.append(m.group(1))
    total = sum(com_nos.values())
    queixas: list[str] = []
    if not any(ln.strip() == "CENSO ativo" for ln in linhas):
        queixas.append(
            f"a saída não traz o censo: faltou `-p {PLUGIN}` na coleta. Sem ele um módulo pulado e um módulo "
            "que sumiu se leem igual."
        )
    if total == 0:
        queixas.append("a coleta não coletou nada; o pytest morreu antes.")
    if erros:
        queixas.append(f"{len(erros)} módulo(s) não coletam sem o GTK (o lint-test do CI reprova):")
        queixas.extend("  " + e for e in erros)
        queixas.append(
            "Módulo de interface precisa de exigir_gi_real() (tests/conftest.py) antes do primeiro import "
            "que carregue o GTK."
        )
    for modulo, motivo in sorted(pulados.items()):
        if not motivo or motivo == "(sem motivo)":
            queixas.append(f"{modulo}: pulado SEM motivo (diga a razão no skip).")
    com_erro = {e.split()[1].split("::")[0] for e in erros if len(e.split()) > 1}
    sumiram = [m for m in modulos if m not in com_nos and m not in pulados and m not in com_erro]
    if sumiram:
        queixas.append(
            f"{len(sumiram)} módulo(s) versionado(s) SUMIRAM da coleta, sem nó e sem pulo com motivo "
            "(um collect_ignore, um padrão de arquivo, um módulo que o pytest não achou):"
        )
        queixas.extend("  " + m for m in sumiram)
    if vazios:
        queixas.append(
            f"{len(vazios)} módulo(s) coletam sem NENHUM teste (cada um ganha um teste ou sai do padrão test_*.py):"
        )
        queixas.extend("  " + m for m in sorted(vazios))
    return queixas, total, len(pulados)


def _coletar_sem_gtk() -> str:
    python = os.environ.get("HEFESTO_PY") or sys.executable
    with tempfile.TemporaryDirectory(prefix="coleta-sem-gtk-") as pasta:
        (Path(pasta) / "sitecustomize.py").write_text(_SEM_GTK, encoding="utf-8")
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = os.pathsep.join(
            p for p in (pasta, str(RAIZ / "src"), str(RAIZ), ambiente.get("PYTHONPATH", "")) if p
        )
        return subprocess.run(
            [
                python, "-m", "pytest", "tests", "--collect-only", "-q", "-rs",
                "--continue-on-collection-errors", "-p", "no:cacheprovider", "-p", PLUGIN,
            ],
            cwd=RAIZ,
            env=ambiente,
            capture_output=True,
            text=True,
            check=False,
        ).stdout


def main(argv: list[str]) -> int:
    if "--julgar" in argv:
        i = argv.index("--julgar")
        origem = argv[i + 1] if i + 1 < len(argv) else "-"
        saida = sys.stdin.read() if origem == "-" else Path(origem).read_text(encoding="utf-8", errors="replace")
    else:
        saida = _coletar_sem_gtk()
    queixas, total, pulados = julgar(saida, versionados())
    if queixas:
        print("FALHA: o censo de coleta reprova:")
        for q in queixas:
            print(q if q.startswith("  ") else "- " + q)
        if total == 0:
            print("\n".join(saida.splitlines()[-15:]))
        return 1
    print(f"OK: {total} testes coletados, {pulados} módulo(s) pulado(s) com motivo, nenhum módulo sumiu.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
