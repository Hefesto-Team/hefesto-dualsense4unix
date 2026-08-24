"""Z6-09 — o fato declarado caduco não pode continuar publicado.

Os dois itens do aceite que são desta tarefa: (3) devolver o parágrafo caduco
de `README.md` reprova citando a chave e a data; (4) a varredura roda duas
vezes e a segunda não acha nada.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-caducos.py"

CADUCOS_CSV = (
    'id,o_que_caducou,caducou_em,substituto,onde_pode_ficar\n'
    'chave.de.teste@dualsense,"literal-caduco-de-teste — número obtido com '
    'instrumento quebrado",2026-08-07,,"docs/process/**"\n'
)


def monta_arvore(tmp_path: Path, conteudo_readme: str) -> Path:
    (tmp_path / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "data" / "caducos.csv").write_text(CADUCOS_CSV, encoding="utf-8")
    (tmp_path / "README.md").write_text(conteudo_readme, encoding="utf-8")
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_sem_o_literal_passa(tmp_path: Path) -> None:
    raiz = monta_arvore(tmp_path, "# README\n\nTudo limpo por aqui.\n")
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout


def test_com_o_literal_reprova_citando_chave_e_data(tmp_path: Path) -> None:
    """MORDIDA — item 3 do aceite."""
    raiz = monta_arvore(tmp_path, "# README\n\nO valor é literal-caduco-de-teste, sempre foi.\n")
    processo = rodar(raiz)
    assert processo.returncode == 1
    assert "chave.de.teste@dualsense" in processo.stdout
    assert "2026-08-07" in processo.stdout
    assert "README.md" in processo.stdout


def test_varredura_roda_duas_vezes_e_a_segunda_nao_acha_nada(tmp_path: Path) -> None:
    """MORDIDA — item 4 do aceite: a segunda passada, já limpa, não acha nada."""
    raiz = monta_arvore(tmp_path, "# README\n\nO valor é literal-caduco-de-teste.\n")
    suja = rodar(raiz)
    assert suja.returncode == 1

    (raiz / "README.md").write_text("# README\n\nCorrigido — sem o número.\n", encoding="utf-8")

    primeira = rodar(raiz)
    segunda = rodar(raiz)
    assert primeira.returncode == 0, primeira.stdout
    assert segunda.returncode == 0, segunda.stdout
    assert primeira.stdout == segunda.stdout


def test_arquivo_historico_fora_das_raizes_vivas_nao_e_varrido(tmp_path: Path) -> None:
    """`docs/process/**` nunca entra na varredura — narrativa não se apaga."""
    raiz = monta_arvore(tmp_path, "# README\n\nLimpo.\n")
    (raiz / "docs" / "process").mkdir(parents=True, exist_ok=True)
    (raiz / "docs" / "process" / "sprint-velha.md").write_text(
        "literal-caduco-de-teste — narrativa histórica, fica.\n", encoding="utf-8"
    )
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout
