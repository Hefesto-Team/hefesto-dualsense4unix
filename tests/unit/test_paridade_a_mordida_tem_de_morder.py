"""A regra 2 do censo do mapa deixou de confundir COLETAR com MORDER."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_check_paridade_transporte import _specs_de

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"

CABECALHO = [
    "chave",
    "controle",
    "existe",
    "cabo_aciona",
    "radio_aciona",
    "cabo_de_onde_sei",
    "radio_de_onde_sei",
    "cabo_canal",
    "radio_canal",
    "cabo_ate_onde_foi",
    "radio_ate_onde_foi",
    "ponte_alcanca",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "id",
]

ID_DA_LINHA = "luz.lightbar.cor@dualsense"


def monta_arvore(tmp_path: Path, fonte_do_teste: str, alvo: str) -> Path:
    """Uma árvore mínima: o mapa com UMA linha forte, e o teste que ela aponta."""
    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_alvo.py").write_text(fonte_do_teste, encoding="utf-8")

    linha = {
        "chave": "luz.lightbar.cor",
        "controle": "dualsense",
        "existe": "tem",
        "cabo_aciona": "sim",
        "radio_aciona": "sim",
        "cabo_de_onde_sei": "medido",
        "radio_de_onde_sei": "medido",
        "cabo_canal": "hidraw",
        "radio_canal": "hidraw",
        "teste_que_morde": alvo,
        "id": ID_DA_LINHA,
    }
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        escritor.writerow({coluna: linha.get(coluna, "") for coluna in CABECALHO})

    _specs_de(tmp_path).write_text(
        f"<html><body>{ID_DA_LINHA}</body></html>", encoding="utf-8"
    )
    return caminho_csv


def rodar(caminho_csv: Path, raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--csv", str(caminho_csv)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_corpo_vazio_nao_e_mordida(tmp_path: Path) -> None:
    """`def test_x(): pass` é coletado, passa sempre, e passa com a cura fora."""
    fonte = (
        '"""Um arquivo de teste que não testa nada."""\n\n\n'
        "def test_a_lightbar_acende():\n    pass\n"
    )
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "mordida-fantasma" in processo.stdout
    assert "corpo vazio" in processo.stdout
    assert "test_a_lightbar_acende" in processo.stdout
    assert ID_DA_LINHA in processo.stdout


@pytest.mark.parametrize(
    ("corpo", "pedaco_esperado"),
    [
        ("    pass", "corpo vazio"),
        ('    """Só a docstring, e nada mais."""', "corpo vazio"),
        ("    ...", "corpo vazio"),
        ('    """Docstring e um pass."""\n    pass', "corpo vazio"),
    ],
)
def test_corpo_inerte_em_todas_as_formas_reprova(
    tmp_path: Path, corpo: str, pedaco_esperado: str
) -> None:
    """Docstring, `pass` e `...` são as três formas de não exercitar nada."""
    fonte = f"def test_a_lightbar_acende():\n{corpo}\n"
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert pedaco_esperado in processo.stdout


@pytest.mark.parametrize(
    "decorador",
    [
        "@pytest.mark.skip",
        '@pytest.mark.skip(reason="a bancada não está livre")',
        '@pytest.mark.skipif(True, reason="desligado e pronto")',
    ],
)
def test_skip_incondicional_nao_e_mordida(tmp_path: Path, decorador: str) -> None:
    """Teste que nunca roda nunca morde — inclusive o `skipif(True)`."""
    fonte = (
        "import pytest\n\n\n"
        f"{decorador}\n"
        "def test_a_lightbar_acende():\n"
        "    assert acende_de_verdade()\n\n\n"
        "def acende_de_verdade():\n"
        "    return True\n"
    )
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "mordida-fantasma" in processo.stdout
    assert "desligado por" in processo.stdout


def test_skipif_com_condicao_de_verdade_continua_valendo(tmp_path: Path) -> None:
    """`skipif(sys.platform == ...)` é honestidade, não teste desligado."""
    fonte = (
        "import sys\n\nimport pytest\n\n\n"
        '@pytest.mark.skipif(sys.platform == "win32", reason="não há uinput lá")\n'
        "def test_a_lightbar_acende():\n"
        "    assert True is True\n"
    )
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_modulo_desligado_por_pytestmark_nao_e_mordida(tmp_path: Path) -> None:
    """O `skip` no `pytestmark` desliga o arquivo inteiro, e some da vista."""
    fonte = (
        "import pytest\n\n"
        'pytestmark = pytest.mark.skip(reason="a frente inteira está parada")\n\n\n'
        "def test_a_lightbar_acende():\n"
        "    assert True is True\n"
    )
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "pytestmark" in processo.stdout


def test_classe_desligada_desliga_o_metodo(tmp_path: Path) -> None:
    """`@pytest.mark.skip` na classe alcança todo método dela."""
    fonte = (
        "import pytest\n\n\n"
        "@pytest.mark.skip\n"
        "class TestOEnvelope:\n"
        "    def test_o_crc_bate(self):\n"
        "        assert calcula() == 7\n\n\n"
        "def calcula():\n"
        "    return 7\n"
    )
    caminho = monta_arvore(
        tmp_path, fonte, "tests/unit/test_alvo.py::TestOEnvelope::test_o_crc_bate"
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "TestOEnvelope::test_o_crc_bate" in processo.stdout


def test_alvo_de_arquivo_inteiro_reprova_so_quando_tudo_e_inerte(tmp_path: Path) -> None:
    """Um alvo de arquivo cobre um conjunto: basta UM vivo para haver rede."""
    vivo_e_morto = (
        "def test_a_lightbar_acende():\n"
        "    assert True is True\n\n\n"
        "def test_que_nao_faz_nada():\n"
        "    pass\n"
    )
    caminho = monta_arvore(tmp_path, vivo_e_morto, "tests/unit/test_alvo.py")
    assert rodar(caminho, tmp_path).returncode == 0

    so_mortos = "def test_um():\n    pass\n\n\ndef test_dois():\n    ...\n"
    caminho = monta_arvore(tmp_path, so_mortos, "tests/unit/test_alvo.py")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "test_um" in processo.stdout and "test_dois" in processo.stdout


def test_arquivo_sem_teste_nenhum_nao_e_mordida(tmp_path: Path) -> None:
    """Coletável e vazio: o pytest coleta o arquivo e não roda nada dele."""
    caminho = monta_arvore(
        tmp_path, '"""Só ajudantes."""\n\n\ndef monta():\n    return 1\n', "tests/unit/test_alvo.py"
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "não cobre um teste sequer" in processo.stdout


def test_teste_de_verdade_continua_passando(tmp_path: Path) -> None:
    fonte = (
        "def test_a_lightbar_acende():\n"
        "    assert cor_enviada() == (255, 0, 0)\n\n\n"
        "def cor_enviada():\n"
        "    return (255, 0, 0)\n"
    )
    caminho = monta_arvore(tmp_path, fonte, "tests/unit/test_alvo.py::test_a_lightbar_acende")
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_a_arvore_real_nao_tem_alvo_podre() -> None:
    """A régua contra a árvore de verdade: nenhum alvo do mapa é vazio ou pulado."""
    processo = subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(RAIZ_REAL)],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ_REAL,
    )
    podres = [
        linha
        for linha in processo.stdout.splitlines()
        if "mordida-fantasma" in linha and ("corpo vazio" in linha or "desligado por" in linha)
    ]
    assert not podres, "\n".join(podres)
