"""A suíte inteira corre as partes em faixas (A-SUITE-INTEIRA-CABE-EM-VINTE-MINUTOS-01).

As 24 partes rodavam em série (51 min de 64). O `rodar-a-suite.sh` agora enche as vagas do
semáforo: as partes LEVES correm em filhos com lar, bus e display próprios, e as que TOCAM a
máquina (citam um serviço do sistema) correm uma de cada vez, ao lado das leves. A prova é feita
numa árvore de mentira com o script de verdade; cada teste grava a hora em que começou e acabou,
e o HOME que viu, para a régua enxergar o que o script fez e não o que ele diz.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

_CORPO = """\
import os
import time
from pathlib import Path


def test_x():
    marca = Path(os.environ["MARCAS"])
    inicio = time.time()
    time.sleep({espera})
    fim = time.time()
    with open(marca / "{nome}.txt", "w", encoding="utf-8") as f:
        f.write(f"{{inicio}} {{fim}} {{os.environ['HOME']}}\\n")
"""


def _arvore(raiz: Path, leves: int, tocam: int, com_semaforo: bool = False) -> None:
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(SUITE, raiz / "scripts" / "rodar-a-suite.sh")
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True)
    for i in range(leves):
        nome = f"test_leve_{i:02d}"
        (unit / f"{nome}.py").write_text(_CORPO.format(espera=0.6, nome=nome), encoding="utf-8")
    for i in range(tocam):
        nome = f"test_toca_{i:02d}"
        corpo = "# chama o systemctl\n" + _CORPO.format(espera=0.6, nome=nome)
        (unit / f"{nome}.py").write_text(corpo, encoding="utf-8")
    if com_semaforo:
        vez = raiz / "docs" / "process" / "ferramentas-da-leva" / "vez-do-pytest.sh"
        vez.parent.mkdir(parents=True)
        vez.write_text('#!/usr/bin/env bash\nexec "$@"\n', encoding="utf-8")
        vez.chmod(vez.stat().st_mode | stat.S_IXUSR)


def _rodar(
    raiz: Path, tmp: Path, *args: str, prazo: int = 300, **env: str
) -> subprocess.CompletedProcess[str]:
    fora = {
        "PYTEST_ADDOPTS",
        "SUITE_PYTEST_ARGS",
        "LD_PRELOAD",
        "PARTES_EM_PARALELO",
        "VEZ_DO_PYTEST",
        "PARTIDO",
        "A_SECO",
        "CSV_DOS_TEMPOS",
        "PARTES",
        "SAIDA",
        "PADRAO_QUE_TOCA",
    }
    amb = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    marcas = tmp / "marcas"
    marcas.mkdir(exist_ok=True)
    amb.update({"PY_COLORS": "0", "PY": sys.executable, "MARCAS": str(marcas)})
    amb.update(env)
    amb.setdefault("SAIDA", str(tmp / "saida"))
    return subprocess.run(
        ["bash", "scripts/rodar-a-suite.sh", *args],
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=prazo,
        check=False,
        env=amb,
    )


def _marcas(tmp: Path) -> dict[str, tuple[float, float, str]]:
    achadas = {}
    for p in sorted((tmp / "marcas").glob("*.txt")):
        inicio, fim, home = p.read_text(encoding="utf-8").split(maxsplit=2)
        achadas[p.stem] = (float(inicio), float(fim), home.strip())
    return achadas


def _nunca_juntas(intervalos: list[tuple[float, float]]) -> bool:
    ordem = sorted(intervalos)
    return all(ordem[i][1] <= ordem[i + 1][0] + 0.001 for i in range(len(ordem) - 1))


def _a_vez_da_casa(raiz: Path) -> str:
    return str(raiz / "docs" / "process" / "ferramentas-da-leva" / "vez-do-pytest.sh")


def test_as_leves_correm_juntas_e_as_que_tocam_correm_uma_de_cada_vez(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=6, tocam=3, com_semaforo=True)
    feito = _rodar(
        raiz,
        tmp_path,
        PARTES="9",
        PARTES_EM_PARALELO="3",
        VEZ_DO_PYTEST=_a_vez_da_casa(raiz),
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    marcas = _marcas(tmp_path)
    assert len(marcas) == 9, marcas
    tocam = [(i, f) for n, (i, f, _) in marcas.items() if "toca" in n]
    leves = [(i, f) for n, (i, f, _) in marcas.items() if "leve" in n]
    assert _nunca_juntas(tocam), f"duas partes que tocam a máquina correram ao mesmo tempo: {tocam}"
    assert not _nunca_juntas(leves), f"as partes leves correram em série: {leves}"
    assert "partes verdes: 9 · partes com vermelho: 0" in feito.stdout, feito.stdout
    assert "testes que passaram: 9 · pulados: 0" in feito.stdout, feito.stdout


def test_a_parte_leve_nasce_em_lar_proprio_e_a_que_toca_no_de_quem_chama(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=3, tocam=2, com_semaforo=True)
    feito = _rodar(
        raiz,
        tmp_path,
        PARTES="5",
        PARTES_EM_PARALELO="3",
        VEZ_DO_PYTEST=_a_vez_da_casa(raiz),
        HOME=str(tmp_path / "casa-de-quem-chama"),
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    homes_leves = {h for n, (_, _, h) in _marcas(tmp_path).items() if "leve" in n}
    homes_toca = {h for n, (_, _, h) in _marcas(tmp_path).items() if "toca" in n}
    assert homes_leves and all("suite-lar-" in h for h in homes_leves), homes_leves
    assert len(homes_leves) == 3, f"dois filhos leves dividiram o lar: {homes_leves}"
    assert homes_toca == {str(tmp_path / "casa-de-quem-chama")}, homes_toca
    assert not [
        p
        for p in Path(os.environ.get("TMPDIR", "/tmp")).glob("suite-lar-*")
        if p.exists() and str(p) in homes_leves
    ], "o lar do filho leve ficou no disco"


def test_o_padrao_novo_nao_trata_uinput_e_hidraw_como_tocar_a_maquina(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=4, tocam=0, com_semaforo=True)
    (raiz / "tests" / "unit" / "test_leve_00.py").write_text(
        "# abre o uinput e le o hidraw e o evdev em /dev/input\n"
        + _CORPO.format(espera=0.1, nome="test_leve_00"),
        encoding="utf-8",
    )
    feito = _rodar(
        raiz,
        tmp_path,
        PARTES="3",
        A_SECO="1",
        PARTES_EM_PARALELO="3",
        VEZ_DO_PYTEST=_a_vez_da_casa(raiz),
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert (tmp_path / "saida" / "toca-a-maquina.txt").read_text(encoding="utf-8") == ""
    assert "toca a máquina" not in feito.stdout


def _precisa_de_oito_nucleos() -> None:
    if (os.cpu_count() or 1) < 8:
        pytest.skip("o `auto` só liga com 8 núcleos ou mais")


def test_o_auto_liga_a_chave_na_suite_inteira_da_arvore_que_tem_o_semaforo(tmp_path: Path) -> None:
    _precisa_de_oito_nucleos()
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=4, tocam=0, com_semaforo=True)
    feito = _rodar(raiz, tmp_path, PARTES="4", PARTES_EM_PARALELO="auto")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert list((tmp_path / "saida").glob("paralelo-*.rc")), "o auto não ligou a chave"


def test_sem_pedir_a_chave_fica_desligada_ate_a_prova(tmp_path: Path) -> None:
    """Prova da D-2110-A-SUITE-EM-FAIXAS-SO-LIGA-COM-O-AUTO."""
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=4, tocam=0, com_semaforo=True)
    feito = _rodar(raiz, tmp_path, PARTES="4")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert not list((tmp_path / "saida").glob("paralelo-*.rc")), "a chave ligou sem ser pedida"


def test_o_auto_nao_liga_sem_o_semaforo_nem_corre_filho_numa_parte_avulsa(tmp_path: Path) -> None:
    raiz = tmp_path / "sem"
    _arvore(raiz, leves=4, tocam=0, com_semaforo=False)
    (tmp_path / "a").mkdir()
    feito = _rodar(raiz, tmp_path / "a", PARTES="4", PARTES_EM_PARALELO="auto")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert not list((tmp_path / "a" / "saida").glob("paralelo-*.rc")), "ligou sem o semáforo"

    raiz2 = tmp_path / "com"
    _arvore(raiz2, leves=4, tocam=0, com_semaforo=True)
    (tmp_path / "b").mkdir()
    avulsa = _rodar(raiz2, tmp_path / "b", "01", PARTES="4", PARTES_EM_PARALELO="auto")
    assert avulsa.returncode == 0, avulsa.stdout + avulsa.stderr
    assert not list((tmp_path / "b" / "saida").glob("paralelo-*.rc")), (
        "correu filho numa parte avulsa"
    )
    assert "parte-01" in avulsa.stdout and "parte-00" not in avulsa.stdout, avulsa.stdout


def _divisao(saida: Path) -> dict[str, list[str]]:
    return {
        p.name: p.read_text(encoding="utf-8").split()
        for p in sorted(saida.glob("parte-[0-9][0-9]"))
    }


def test_a_parte_avulsa_com_o_auto_tem_a_divisao_da_corrida_inteira(tmp_path: Path) -> None:
    """A triagem roda os MESMOS arquivos da parte que reprovou na corrida com a chave.

    Com a chave, as que tocam a máquina ficam juntas nas últimas partes; sem ela, não. Se a parte
    avulsa caísse na divisão sem a chave, `rodar-a-suite.sh NN` rodaria outros arquivos que os da
    `parte-NN` da corrida inteira, e o vermelho de ordem não se reproduziria."""
    _precisa_de_oito_nucleos()
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=4, tocam=2, com_semaforo=True)
    for nome in ("inteira", "avulsa"):
        (tmp_path / nome).mkdir()
    inteira = _rodar(raiz, tmp_path / "inteira", PARTES="3", A_SECO="1", PARTES_EM_PARALELO="auto")
    assert inteira.returncode == 0, inteira.stdout + inteira.stderr
    avulsa = _rodar(raiz, tmp_path / "avulsa", "02", PARTES="3", PARTES_EM_PARALELO="auto")
    assert avulsa.returncode == 0, avulsa.stdout + avulsa.stderr
    divisao = _divisao(tmp_path / "inteira" / "saida")
    assert divisao == _divisao(tmp_path / "avulsa" / "saida"), (
        "a parte avulsa partiu de outro jeito"
    )
    sem_chave = tmp_path / "sem-chave"
    sem_chave.mkdir()
    _rodar(raiz, sem_chave, PARTES="3", A_SECO="1")
    assert _divisao(sem_chave / "saida") != divisao, "a massa não separa as duas divisões"


def test_o_agendador_nao_depende_do_wait_com_p(tmp_path: Path) -> None:
    """No bash 5.0 o `wait -n -p` não existe e volta na hora; o laço não pode girar para sempre.

    O `wait` de mentira (uma função exportada vence o embutido) recusa o `-p` como o 5.0 recusa."""
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=4, tocam=1, com_semaforo=True)
    sem_p = (
        '() { local a; for a in "$@"; do '
        "[ \"$a\" != -p ] || { echo 'wait: -p: invalid option' >&2; return 2; }; "
        'done; builtin wait "$@"; }'
    )
    feito = _rodar(
        raiz,
        tmp_path,
        PARTES="5",
        PARTES_EM_PARALELO="3",
        VEZ_DO_PYTEST="nenhum",
        prazo=90,
        **{"BASH_FUNC_wait%%": sem_p},
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "partes verdes: 5 · partes com vermelho: 0" in feito.stdout, feito.stdout


def test_o_vermelho_de_uma_parte_leve_e_de_uma_que_toca_derruba_a_corrida(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore(raiz, leves=3, tocam=2, com_semaforo=True)
    (raiz / "tests" / "unit" / "test_toca_01.py").write_text(
        "# chama o systemctl\ndef test_cai():\n    assert False\n", encoding="utf-8"
    )
    feito = _rodar(
        raiz,
        tmp_path,
        PARTES="5",
        PARTES_EM_PARALELO="3",
        VEZ_DO_PYTEST=_a_vez_da_casa(raiz),
    )
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "partes com vermelho: 1" in feito.stdout, feito.stdout
    assert "test_toca_01.py::test_cai" in feito.stdout
