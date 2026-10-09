"""O lote avulso roda com o isolamento da suíte: o WebKit num processo só dele.

O `scripts/rodar-a-suite.sh` já punha cada arquivo do WebKit em processo próprio, com a pilha
nativa, mas só para as partes da suíte; o lote de uma árvore de voo era `pytest $(cat lista)` sob
`xvfb-run`, com vários arquivos do WebKit no mesmo processo, e a queda intermitente que a suíte
curou voltava ali. O modo `--lote <lista>` (ou `LOTE=<lista>`) aplica a mesma partição a uma lista.

A régua roda o script de verdade numa árvore de mentira, com um `PY` de mentira que só anota cada
processo de pytest que o script abre: nada roda de fato. A mordida é a régua sobre a cópia do
script sem a partição (tudo no mesmo processo) e sem a trava do arquivo que não existe.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

DO_WEBKIT = ["tests/unit/test_janela_a.py", "tests/unit/test_janela_pelo_ajudante.py"]
COMUNS = ["tests/unit/test_conta_b.py", "tests/unit/test_conta_c.py"]

PARTICAO = 'if e_do_webkit "$a"; then do_webkit+=("$a"); else comuns+=("$a"); fi'
TRAVA = '[ -f "$a" ] || { ruins+=("$a (não existe nesta árvore)"); continue; }'


def _arvore(tmp_path: Path, suite: Path) -> Path:
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(suite, raiz / "scripts" / "rodar-a-suite.sh")
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "__init__.py").write_text("")
    (unit / "ajudante_da_janela.py").write_text(
        'def gtk():\n    import gi\n    gi.require_version("WebKit2", "4.1")\n'
    )
    (unit / "test_janela_a.py").write_text('import gi\ngi.require_version("WebKit2", "4.1")\n')
    (unit / "test_janela_pelo_ajudante.py").write_text("from .ajudante_da_janela import gtk\n")
    (unit / "test_conta_b.py").write_text("def test_b():\n    assert True\n")
    (unit / "test_conta_c.py").write_text("def test_c():\n    assert True\n")
    (unit / "test_fora_da_lista.py").write_text('import gi\ngi.require_version("WebKit2", "4.1")\n')
    py = raiz / "py-de-mentira"
    py.write_text(
        "#!/bin/bash\n# anota os arquivos de cada processo de pytest e diz um sumário\n"
        'shift 2\nfora=()\nfor a in "$@"; do case "$a" in tests/*) fora+=("$a");; esac; done\n'
        'printf \'%s\\n\' "${fora[*]}" >> "$CHAMADAS"\necho "1 passed in 0.01s"\n'
    )
    py.chmod(0o755)
    return raiz


def _rodar(
    raiz: Path, linhas: list[str] | None, *, pelo_ambiente: bool = False, lista: Path | None = None
) -> tuple[int, str, list[list[str]]]:
    chamadas = raiz / "chamadas.txt"
    chamadas.write_text("")
    if lista is None:
        lista = raiz / "lista"
        lista.write_text("".join(f"{a}\n" for a in (linhas or [])))
    fora = {
        "PYTEST_ADDOPTS",
        "SUITE_PYTEST_ARGS",
        "LD_PRELOAD",
        "PARTES",
        "SAIDA",
        "PARTIDO",
        "LOTE",
        "PARTES_EM_PARALELO",
        "LISTAR_O_WEBKIT",
        "A_SECO",
    }
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update(
        {"PY": str(raiz / "py-de-mentira"), "CHAMADAS": str(chamadas), "SAIDA": str(raiz / "saida")}
    )
    comando = ["bash", str(raiz / "scripts" / "rodar-a-suite.sh")]
    if pelo_ambiente:
        env["LOTE"] = str(lista)
    else:
        comando += ["--lote", str(lista)]
    feito = subprocess.run(
        comando, cwd=raiz, capture_output=True, text=True, timeout=120, check=False, env=env
    )
    processos = [linha.split() for linha in chamadas.read_text().splitlines() if linha.strip()]
    return feito.returncode, feito.stdout + feito.stderr, processos


def _webkit_junto(processos: list[list[str]]) -> list[list[str]]:
    """Os processos que levam um arquivo do WebKit ao lado de outro arquivo qualquer."""
    return [p for p in processos if len(p) > 1 and any(a in DO_WEBKIT for a in p)]


def test_o_lote_misto_roda_cada_webkit_sozinho_e_o_resto_junto(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path, SUITE)
    for pelo_ambiente in (False, True):
        lista = COMUNS[::-1] + DO_WEBKIT + [""]
        rc, saida, processos = _rodar(raiz, lista, pelo_ambiente=pelo_ambiente)
        assert rc == 0, saida
        assert not _webkit_junto(processos), f"o WebKit dividiu o processo: {processos}"
        assert sorted(processos) == sorted([COMUNS, *([a] for a in DO_WEBKIT)]), processos
        assert "lote — 4 arquivos" in saida, saida
        assert "recibo: um lote não deixa recibo" in saida, saida
        assert not (raiz / "saida" / "recibo-da-corrida.json").exists()


def test_o_lote_vazio_ou_com_arquivo_que_nao_existe_falha_alto_sem_rodar(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path, SUITE)
    rc, saida, processos = _rodar(raiz, ["", "  "])
    assert rc == 2 and "está vazio" in saida and processos == [], saida
    rc, saida, processos = _rodar(raiz, [*COMUNS, "tests/unit/test_de_outra_arvore.py"])
    assert rc == 2 and "test_de_outra_arvore.py (não existe nesta árvore)" in saida, saida
    assert processos == [], "o lote rodou com um arquivo que não existe"
    rc, saida, processos = _rodar(raiz, [*COMUNS, "tests/unit/ajudante_da_janela.py"])
    assert rc == 2 and "não é um arquivo test_*.py" in saida and processos == [], saida
    rc, saida, processos = _rodar(raiz, None, lista=raiz / "lista-que-nao-existe")
    assert rc == 2 and "não existe" in saida and processos == [], saida


def test_a_regua_morde_sem_a_particao_e_sem_a_trava(tmp_path: Path) -> None:
    texto = SUITE.read_text(encoding="utf-8")
    assert PARTICAO in texto and TRAVA in texto, "a partição ou a trava mudou de forma no script"

    junto = tmp_path / "junto.sh"
    junto.write_text(texto.replace(PARTICAO, 'comuns+=("$a")'), encoding="utf-8")
    raiz = _arvore(tmp_path / "junto", junto)
    rc, saida, processos = _rodar(raiz, COMUNS + DO_WEBKIT)
    assert rc == 0, saida
    assert _webkit_junto(processos), "sem a partição a régua não viu o WebKit dividir o processo"

    sem_trava = tmp_path / "sem-trava.sh"
    sem_trava.write_text(texto.replace(TRAVA, ":"), encoding="utf-8")
    raiz = _arvore(tmp_path / "sem-trava", sem_trava)
    rc, saida, processos = _rodar(raiz, [*COMUNS, "tests/unit/test_de_outra_arvore.py"])
    assert processos, "sem a trava o arquivo que não existe deveria ter ido ao pytest"
