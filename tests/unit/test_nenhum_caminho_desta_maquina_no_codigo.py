"""Nenhum caminho desta máquina no código.

OS-COMANDOS-E-OS-TESTES-NAO-SABEM-O-CAMINHO-DESTA-MAQUINA-01. Medido em 09/10/2026: o
`rodar-a-suite.sh` e o `mesa-de-medicao.sh` caíam no python de uma árvore desta máquina quando a
deles não tinha `.venv` (em outro PC, «não achei um python» sem tentar o `python3`), o
`medir_guarda.py` punha essa árvore no `sys.path`, quatro testes forjavam processo com o `HOME`
desta máquina e um guardava o `~/.config` pelo nome literal, o que em outra máquina não guarda
nada.

A régua lê os arquivos versionados de `scripts/`, `tests/` e `src/` e reprova o ponto de montagem
desta bancada e o `/home/<usuário que roda>/`. Dado de processo forjado usa um `HOME` forjado
(`/home/usuario/...`); o `HOME` real se pergunta à tabela de usuários. Os registros brutos de
`docs/data/ensaios-brutos/` ficam fora: são a saída de um ensaio como ele rodou.
"""
from __future__ import annotations

import os
import pwd
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTE = Path(__file__).resolve().relative_to(RAIZ).as_posix()
PASTAS = ("scripts", "tests", "src")

ISENTOS: dict[str, str] = {
    "tests/unit/test_as_abas_vivas_falam_com_o_daemon_certo.py": (
        "10/10/2026: é a régua que proíbe a árvore dela nas abas vivas; o caminho literal é o "
        "que ela procura."),
}


def _proibidos() -> re.Pattern[str]:
    usuario = pwd.getpwuid(os.getuid()).pw_name
    return re.compile("|".join([
        re.escape("/mnt/" + "Apate"),
        re.escape(f"/home/{usuario}") + r"(?=/|\b)",
    ]))


def _versionados() -> list[str]:
    feito = subprocess.run(["git", "-C", str(RAIZ), "ls-files", "-z", "--", *PASTAS],
                           capture_output=True, check=True)
    return [n for n in feito.stdout.decode("utf-8", "replace").split("\0") if n]


def achados(raiz: Path, nomes: list[str], padrao: re.Pattern[str]) -> list[str]:
    """``arquivo:linha: trecho`` de cada caminho de máquina nos arquivos dados."""
    saida: list[str] = []
    for nome in nomes:
        alvo = raiz / nome
        if not alvo.is_file():
            continue
        try:
            texto = alvo.read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        for numero, linha in enumerate(texto.splitlines(), 1):
            if padrao.search(linha):
                saida.append(f"{nome}:{numero}: {linha.strip()[:120]}")
    return saida


def test_nenhum_caminho_desta_maquina_em_scripts_tests_e_src() -> None:
    nomes = [n for n in _versionados() if n != ESTE and n not in ISENTOS]
    sobra = achados(RAIZ, nomes, _proibidos())
    assert not sobra, (
        "caminho desta máquina no código (o comando resolve o python por PY, HEFESTO_PY, a "
        ".venv da árvore e o python3; o teste forja /home/usuario/; o HOME real vem do pwd):\n  "
        + "\n  ".join(sobra))


def test_a_isencao_ainda_casa_e_diz_o_motivo() -> None:
    padrao = re.compile(re.escape("/mnt/" + "Apate"))
    for nome, motivo in ISENTOS.items():
        assert re.match(r"\d{2}/\d{2}/\d{4}: \S", motivo), f"{nome}: a isenção pede data e motivo"
        assert achados(RAIZ, [nome], padrao), f"{nome}: a isenção não casa mais nada; tire-a"


def test_a_regua_pega_o_ponto_de_montagem_e_a_casa_de_quem_roda(tmp_path: Path) -> None:
    usuario = pwd.getpwuid(os.getuid()).pw_name
    (tmp_path / "a.sh").write_text('PY="/mnt/' + 'Apate/x/.venv/bin/python"\n', encoding="utf-8")
    (tmp_path / "b.py").write_text(f'REAPER = "/home/{usuario}/.steam/reaper"\n', encoding="utf-8")
    (tmp_path / "c.py").write_text('REAPER = "/home/usuario/.steam/reaper"\n', encoding="utf-8")
    sobra = achados(tmp_path, ["a.sh", "b.py", "c.py"], _proibidos())
    assert [s.split(":", 2)[:2] for s in sobra] == [["a.sh", "1"], ["b.py", "1"]], sobra
