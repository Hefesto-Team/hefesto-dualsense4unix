"""A suíte parte pelo TEMPO dos arquivos, não pelo número deles (A-SUITE-CABE-NO-TEMPO-01).

O `split -n l/24` repartia a lista por linha: as partes iam de 41 s a 241 s, com 62 a 79
arquivos cada. O `scripts/rodar-a-suite.sh` agora lê o tempo de cada arquivo em
`docs/data/tempos-da-suite.csv` (versionado: o CI roda o mesmo script) e põe o maior na parte
mais leve.

A prova é feita numa árvore de mentira (dez arquivos de tempo conhecido), com o `A_SECO=1` do
próprio script (diz as partes e o tempo previsto sem rodar nada) e, na árvore de verdade, com a
mesma contagem de arquivos que o `ls` dá. A massa de teste é feita para o `split` por linha
REPROVAR nela: sem isso a régua passaria com a cura arrancada.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"
CSV_DE_VERDADE = RAIZ / "docs" / "data" / "tempos-da-suite.csv"

TEMPOS_S = {
    "test_a00.py": 90,
    "test_a01.py": 80,
    "test_a02.py": 70,
    "test_a03.py": 40,
    "test_a04.py": 30,
    "test_a05.py": 30,
    "test_a06.py": 20,
    "test_a07.py": 20,
    "test_a08.py": 10,
    "test_a09.py": 10,
}
PARTES = 3


def _ambiente(**mais: str) -> dict[str, str]:
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
    }
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY_COLORS": "0", "PY": sys.executable, **mais})
    return env


def _arvore(
    raiz: Path,
    tempos_ms: dict[str, int] | None,
    conteudo: dict[str, str] | None = None,
    nomes: list[str] | None = None,
) -> None:
    """Uma árvore de mentira com o script de verdade e os arquivos de teste pedidos."""
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(SUITE, raiz / "scripts" / "rodar-a-suite.sh")
    (raiz / "tests" / "unit").mkdir(parents=True)
    for nome in nomes if nomes is not None else list(TEMPOS_S):
        texto = (conteudo or {}).get(nome, "def test_passa():\n    assert True\n")
        (raiz / "tests" / "unit" / nome).write_text(texto, encoding="utf-8")
    if tempos_ms is not None:
        (raiz / "docs" / "data").mkdir(parents=True)
        linhas = ["# massa de teste", "arquivo,milissegundos,fonte"]
        linhas += [f"tests/unit/{n},{ms},medido" for n, ms in tempos_ms.items()]
        (raiz / "docs" / "data" / "tempos-da-suite.csv").write_text(
            "\n".join(linhas) + "\n", encoding="utf-8"
        )


def _rodar(raiz: Path, saida: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/rodar-a-suite.sh", *args],
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=_ambiente(SAIDA=str(saida), **env),
    )


def _partes(saida: Path) -> dict[str, list[str]]:
    return {
        p.name[-2:]: p.read_text(encoding="utf-8").split()
        for p in sorted(saida.glob("parte-[0-9][0-9]"))
    }


def _carga_s(partes: dict[str, list[str]], tempos_s: Mapping[str, float]) -> list[float]:
    return [sum(tempos_s[Path(a).name] for a in arquivos) for arquivos in partes.values()]


@pytest.fixture
def mentira(tmp_path: Path) -> Path:
    raiz = tmp_path / "arvore"
    _arvore(raiz, {n: s * 1000 for n, s in TEMPOS_S.items()})
    return raiz


def test_dez_arquivos_de_tempo_conhecido_dao_partes_com_diferenca_menor_que_o_maior(
    mentira: Path, tmp_path: Path
) -> None:
    """Prova da D-0810-A-SUITE-PARTE-PELO-TEMPO-MEDIDO."""
    saida = tmp_path / "saida"
    feito = _rodar(mentira, saida, PARTES=str(PARTES), A_SECO="1")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    partes = _partes(saida)
    assert len(partes) == PARTES
    cargas = _carga_s(partes, TEMPOS_S)
    assert max(cargas) - min(cargas) < max(TEMPOS_S.values()), (
        f"as partes ficaram desiguais: {cargas} (o maior arquivo pesa {max(TEMPOS_S.values())} s)"
    )


def test_a_massa_de_teste_reprova_o_split_por_linha(tmp_path: Path) -> None:
    """O controle da mordida: o `split -n l/` do script antigo, na MESMA massa, passa do limite."""
    lista = tmp_path / "todos.txt"
    lista.write_text("".join(f"tests/unit/{n}\n" for n in sorted(TEMPOS_S)), encoding="utf-8")
    subprocess.run(
        ["split", "-n", f"l/{PARTES}", "-d", str(lista), str(tmp_path / "parte-")], check=True
    )
    antigas = _partes(tmp_path)
    cargas = _carga_s(antigas, TEMPOS_S)
    assert max(cargas) - min(cargas) >= max(TEMPOS_S.values()), (
        f"a massa não discrimina: o split por linha também cabe no limite ({cargas})"
    )


def test_a_seco_nao_perde_nem_repete_arquivo_e_diz_o_tempo_previsto(
    mentira: Path, tmp_path: Path
) -> None:
    saida = tmp_path / "saida"
    feito = _rodar(mentira, saida, PARTES=str(PARTES), A_SECO="1")
    todos = sorted(f"tests/unit/{n}" for n in TEMPOS_S)
    juntos = sorted(a for arquivos in _partes(saida).values() for a in arquivos)
    assert juntos == todos, "a partição perdeu ou repetiu arquivo"
    previstos = re.findall(
        r"^  parte-(\d\d) \((\d+) arq\): previsto ([\d.]+) s", feito.stdout, re.M
    )
    assert len(previstos) == PARTES, feito.stdout
    assert sum(int(n) for _, n, _ in previstos) == len(TEMPOS_S)
    assert abs(sum(float(t) for _, _, t in previstos) - sum(TEMPOS_S.values())) < 0.5
    assert not list(saida.glob("*.log")), "o modo a seco rodou pytest"


def test_cada_parte_guarda_os_arquivos_em_ordem_de_nome(mentira: Path, tmp_path: Path) -> None:
    saida = tmp_path / "saida"
    _rodar(mentira, saida, PARTES=str(PARTES), A_SECO="1")
    for numero, arquivos in _partes(saida).items():
        assert arquivos == sorted(arquivos), f"a parte {numero} saiu fora da ordem do LC_ALL=C"


NOMES_DO_IDIOMA = ["test_a.py", "test_a_b.py", "test_a_c.py", "test_aa_z.py", "test_ab.py"]


def test_a_partilha_e_a_mesma_em_toda_maquina(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore(raiz, {n: 5_000 for n in NOMES_DO_IDIOMA}, nomes=NOMES_DO_IDIOMA)
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    _rodar(raiz, a, PARTES="2", A_SECO="1")
    _rodar(raiz, b, PARTES="2", A_SECO="1", LC_ALL="pt_BR.UTF-8", LANG="pt_BR.UTF-8")
    _rodar(raiz, c, PARTES="2", A_SECO="1", LC_ALL="C.UTF-8")
    assert _partes(a), "a seco não deixou as partes"
    assert _partes(a) == _partes(b) == _partes(c), "o idioma de quem roda mudou a divisão"


def test_arquivo_sem_linha_no_csv_pesa_a_mediana_dos_medidos(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    nomes = ["test_a.py", "test_b.py", "test_c.py", "test_d_novo.py"]
    _arvore(raiz, {"test_a.py": 10_000, "test_b.py": 30_000, "test_c.py": 20_000}, nomes=nomes)
    saida = tmp_path / "saida"
    _rodar(raiz, saida, PARTES="2", A_SECO="1")
    pesos = {
        linha.split("\t")[3]: int(linha.split("\t")[1])
        for linha in (saida / "pesos.tsv").read_text(encoding="utf-8").splitlines()
    }
    assert pesos["tests/unit/test_d_novo.py"] == 20_000, pesos
    assert pesos["tests/unit/test_b.py"] == 30_000


def test_sem_o_csv_a_particao_cai_no_numero_de_arquivos(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    nomes = [f"test_{i:02d}.py" for i in range(10)]
    _arvore(raiz, None, nomes=nomes)
    saida = tmp_path / "saida"
    feito = _rodar(raiz, saida, PARTES="3", A_SECO="1")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    tamanhos = sorted(len(a) for a in _partes(saida).values())
    assert tamanhos == [3, 3, 4], tamanhos


def test_a_chave_desligada_nao_separa_quem_toca_a_maquina(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    toca = "# chama o systemctl\ndef test_x():\n    assert True\n"
    nomes = [f"test_{i:02d}.py" for i in range(6)]
    _arvore(raiz, None, conteudo={"test_00.py": toca}, nomes=nomes)
    saida = tmp_path / "saida"
    feito = _rodar(raiz, saida, PARTES="3", A_SECO="1")
    assert "toca a máquina" not in feito.stdout
    assert (saida / "toca-a-maquina.txt").read_text(encoding="utf-8") == ""


def test_a_chave_pede_o_semaforo(tmp_path: Path) -> None:
    """Prova da D-0810-AS-PARTES-EM-PARALELO-ESPERAM-A-PROVA."""
    raiz = tmp_path / "arvore"
    _arvore(raiz, None, nomes=["test_00.py", "test_01.py"])
    feito = _rodar(raiz, tmp_path / "saida", PARTES="2", PARTES_EM_PARALELO="2")
    assert feito.returncode == 2, feito.stdout + feito.stderr
    assert "VEZ_DO_PYTEST" in feito.stdout


def _arvore_da_chave(raiz: Path) -> None:
    toca = "# chama o systemctl\ndef test_x():\n    assert True\n"
    nomes = [f"test_{i:02d}.py" for i in range(8)]
    tempos = {n: 10_000 for n in nomes}
    _arvore(raiz, tempos, conteudo={"test_05.py": toca, "test_06.py": toca}, nomes=nomes)


def test_com_a_chave_ligada_quem_toca_a_maquina_fica_junto_nas_ultimas_partes(
    tmp_path: Path,
) -> None:
    raiz = tmp_path / "arvore"
    _arvore_da_chave(raiz)
    saida = tmp_path / "saida"
    feito = _rodar(
        raiz, saida, PARTES="4", A_SECO="1", PARTES_EM_PARALELO="2", VEZ_DO_PYTEST="nenhum"
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    partes = _partes(saida)
    tocam = {"tests/unit/test_05.py", "tests/unit/test_06.py"}
    misturas = [n for n, a in partes.items() if tocam & set(a) and set(a) - tocam]
    assert not misturas, (
        f"parte com arquivo que toca junto de arquivo que não toca: {misturas} {partes}"
    )
    com_toque = [n for n, a in partes.items() if tocam & set(a)]
    assert com_toque and com_toque == sorted(com_toque)
    assert min(com_toque) > max(n for n in partes if n not in com_toque), (
        "as que tocam não vêm por último"
    )
    assert feito.stdout.count("toca a máquina") == len(com_toque)


def test_com_a_chave_ligada_as_partes_leves_rodam_em_paralelo_e_o_resultado_soma(
    tmp_path: Path,
) -> None:
    raiz = tmp_path / "arvore"
    _arvore_da_chave(raiz)
    saida = tmp_path / "saida"
    feito = _rodar(raiz, saida, PARTES="4", PARTES_EM_PARALELO="2", VEZ_DO_PYTEST="nenhum")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "partes verdes: 4 · partes com vermelho: 0" in feito.stdout, feito.stdout
    linhas = re.findall(r"^  parte-(\d\d) \((\d+) arq\): (\d+) passed", feito.stdout, re.M)
    assert [n for n, _, _ in linhas] == ["00", "01", "02", "03"], feito.stdout
    assert sum(int(p) for _, _, p in linhas) == 8
    assert "testes que passaram: 8 · pulados: 0" in feito.stdout, (
        "a contagem do recibo perdeu os testes das partes em paralelo:\n" + feito.stdout
    )


def test_com_a_chave_ligada_o_vermelho_de_uma_parte_leve_derruba_a_corrida(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore_da_chave(raiz)
    (raiz / "tests" / "unit" / "test_01.py").write_text(
        "def test_cai():\n    assert False\n", encoding="utf-8"
    )
    saida = tmp_path / "saida"
    feito = _rodar(raiz, saida, PARTES="4", PARTES_EM_PARALELO="2", VEZ_DO_PYTEST="nenhum")
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "partes com vermelho: 1" in feito.stdout, feito.stdout
    assert "test_01.py::test_cai" in feito.stdout


def test_a_corrida_em_serie_continua_a_mesma_com_a_chave_desligada(tmp_path: Path) -> None:
    raiz = tmp_path / "arvore"
    _arvore_da_chave(raiz)
    saida = tmp_path / "saida"
    feito = _rodar(raiz, saida, PARTES="4")
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "partes verdes: 4 · partes com vermelho: 0" in feito.stdout, feito.stdout
    assert "testes que passaram: 8 · pulados: 0" in feito.stdout, feito.stdout
    assert not list(saida.glob("paralelo-*")), "a chave desligada deixou rastro de filho"


def test_na_arvore_de_verdade_as_24_partes_somam_os_mesmos_arquivos_e_cabem_no_limite(
    tmp_path: Path,
) -> None:
    saida = tmp_path / "saida"
    feito = subprocess.run(
        ["bash", str(SUITE)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=_ambiente(SAIDA=str(saida), A_SECO="1"),
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    esperados = sorted(
        str(p.relative_to(RAIZ)) for p in (RAIZ / "tests" / "unit").glob("test_*.py")
    )
    partes = _partes(saida)
    assert len(partes) == 24
    assert sorted(a for arquivos in partes.values() for a in arquivos) == esperados, (
        "a partição pelo tempo perdeu ou repetiu arquivo da suíte"
    )
    assert all(partes.values()), "alguma parte saiu vazia"
    pesos = {}
    for linha in (saida / "pesos.tsv").read_text(encoding="utf-8").splitlines():
        _, peso, _, arquivo = linha.split("\t")
        pesos[arquivo] = int(peso)
    cargas = [sum(pesos[a] for a in arquivos) for arquivos in partes.values()]
    assert max(cargas) - min(cargas) <= max(pesos.values()), (
        "as partes saíram desiguais além do maior arquivo "
        f"({max(cargas)} ms contra {min(cargas)} ms)"
    )


def test_o_csv_versionado_tem_a_forma_que_o_partidor_le() -> None:
    linhas = [
        ln
        for ln in CSV_DE_VERDADE.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("#")
    ]
    assert linhas[0] == "arquivo,milissegundos,fonte"
    vistos: set[str] = set()
    for linha in linhas[1:]:
        arquivo, ms, fonte = linha.split(",")
        assert re.fullmatch(r"tests/unit/test_[^/,]+\.py", arquivo), linha
        assert ms.isdigit() and int(ms) > 0, linha
        assert fonte in {"medido", "estimado"}, linha
        assert arquivo not in vistos, f"{arquivo} aparece duas vezes"
        vistos.add(arquivo)
    assert len(vistos) > 1000, "o CSV de tempos encolheu: o partidor cairia no número de arquivos"
