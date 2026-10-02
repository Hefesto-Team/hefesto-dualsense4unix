"""Os dois buracos do `scripts/check_test_data.sh`, medidos em 26/08/2026."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL = "scripts/check_test_data.sh"

MAC_DE_MENTIRA = ":".join(("06", "DE", "AD", "BE", "EF", "01"))

MAC_PERMITIDO = ":".join(("aa", "bb", "cc", "11", "22", "33"))

EMAIL_DE_MENTIRA = "alguem" + "@" + "gmail.com"


@pytest.fixture
def tests_de_mentira(tmp_path: Path) -> Path:
    """Uma árvore com `tests/` e o portão copiado. Sem git: ele não usa git."""
    origem = Path(__file__).resolve().parents[2] / SCRIPT_REL
    if not origem.exists():
        pytest.skip(f"{SCRIPT_REL} não encontrado no repo")
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts").mkdir()
    shutil.copy2(origem, tmp_path / SCRIPT_REL)
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL],
        cwd=raiz, capture_output=True, text=True, check=False,
    )


def test_mac_real_na_linha_de_um_permitido_e_pego(tests_de_mentira: Path) -> None:
    """A mordida principal: a allowlist decide sobre o ENDEREÇO, não sobre a linha."""
    (tests_de_mentira / "tests" / "t.py").write_text(
        f'MASCARA = "{MAC_PERMITIDO}"; ANTES = "{MAC_DE_MENTIRA}"\n',
        encoding="utf-8",
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 1, (
        "endereço real escondido atrás de um permitido na MESMA LINHA: o "
        f"filtro voltou a descartar a linha.\nsaída:\n{r.stdout}"
    )
    assert "t.py" in r.stdout, r.stdout


def test_mac_real_sozinho_continua_pego(tests_de_mentira: Path) -> None:
    """A régua não perdeu o caso simples ao ganhar o composto."""
    (tests_de_mentira / "tests" / "t.py").write_text(
        f'REAL = "{MAC_DE_MENTIRA}"\n', encoding="utf-8"
    )
    assert rodar(tests_de_mentira).returncode == 1


def test_familia_sintetica_sozinha_nao_reprova(tests_de_mentira: Path) -> None:
    """A outra resposta: régua que só sabe recusar também não é régua."""
    (tests_de_mentira / "tests" / "t.py").write_text(
        f'PERMITIDO = "{MAC_PERMITIDO}"\n', encoding="utf-8"
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 0, r.stdout


def test_email_real_na_linha_de_um_permitido_e_pego(tests_de_mentira: Path) -> None:
    """O bloco de e-mail tinha o mesmo desenho e o mesmo buraco."""
    (tests_de_mentira / "tests" / "t.py").write_text(
        f'OK = "test@example.com"; VAZA = "{EMAIL_DE_MENTIRA}"\n', encoding="utf-8"
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 1, (
        "e-mail pessoal escondido atrás do `test@example.com` na mesma linha."
        f"\nsaída:\n{r.stdout}"
    )


def test_email_neutro_sozinho_nao_reprova(tests_de_mentira: Path) -> None:
    (tests_de_mentira / "tests" / "t.py").write_text(
        'OK = "test@example.com"\n', encoding="utf-8"
    )
    assert rodar(tests_de_mentira).returncode == 0


def test_extensao_fora_da_allowlist_antiga_e_varrida(tests_de_mentira: Path) -> None:
    """O buraco LATENTE: `.yaml` de teste não era varrido por ninguém."""
    (tests_de_mentira / "tests" / "config.yaml").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 1, (
        "arquivo `.yaml` em tests/ não foi varrido: a allowlist de duas "
        f"extensões voltou.\nsaída:\n{r.stdout}"
    )
    assert "config.yaml" in r.stdout, r.stdout


def test_fixtures_continua_fora(tests_de_mentira: Path) -> None:
    """Ampliar a varredura não pode ligar o portão em `tests/fixtures/`."""
    (tests_de_mentira / "tests" / "fixtures").mkdir()
    (tests_de_mentira / "tests" / "fixtures" / "captura.yaml").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 0, r.stdout
