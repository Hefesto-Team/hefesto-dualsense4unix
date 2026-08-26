"""Os dois buracos do `scripts/check_test_data.sh`, medidos em 26/08/2026.

1. **GATE-TEST-DATA-CEGO-POR-VIZINHO-01.** A allowlist era aplicada com
   `grep -vE`, que descarta a **LINHA** e não o **CASAMENTO**. Um endereço real
   escrito ao lado de um permitido sumia junto com o vizinho — e essa companhia
   não é acidente: a convenção desta casa é escrever o mascarado e o "antes" na
   mesma linha, para explicar a máscara. Os dois `grep -v` do bloco de e-mail
   tinham o mesmo desenho, e o mesmo buraco.

2. **GATE-TEST-DATA-SO-DUAS-EXTENSOES-01.** A varredura era uma allowlist de
   duas extensões (`--include="*.py" --include="*.json"`). Este buraco é
   LATENTE, não vivo, e a medição está escrita para que ninguém confunda: hoje
   `git ls-files tests/` devolve `py`, `json`, `js` e `bin`, e os dois últimos
   moram em `tests/fixtures/`, que já estava fora. **Nenhum arquivo desta
   árvore escapava hoje** — é por isso que o defeito atravessou um mês sem
   sintoma. O dano chega no dia em que um `.yaml` ou `.csv` de teste entrar.

**Nenhum endereço de seis grupos e nenhum e-mail proibido aparecem LITERAIS
neste arquivo**, e isso é de propósito: o portão sob teste varre `tests/`, e um
literal aqui se acusaria. Ambos são montados em tempo de execução.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL = "scripts/check_test_data.sh"

#: Endereço que NÃO identifica ninguém e que o portão TEM de acusar. O primeiro
#: octeto `06` tem o bit 1 ligado: faixa **localmente administrada**, que a IEEE
#: nunca atribui a fabricante. E ele fica fora de todas as famílias sintéticas
#: do `ALLOWED_MAC`: não é `02:fe:`, não é `aa:bb:cc:`, não é `OUI:00:00:NN`,
#: não é o nulo nem o broadcast.
MAC_DE_MENTIRA = ":".join(("06", "DE", "AD", "BE", "EF", "01"))

#: Da mesma família: um endereço da faixa `aa:bb:cc:`, que o portão TEM de
#: deixar passar. É o vizinho legítimo do teste do casamento.
MAC_PERMITIDO = ":".join(("aa", "bb", "cc", "11", "22", "33"))

#: E-mail de domínio pessoal, montado para não existir literal nesta árvore.
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
    """A outra resposta: régua que só sabe recusar também não é régua.

    A `aa:bb:cc:` é faixa de documentação, e reprová-la contradiria o portão de
    anonimato, que MANDA mascarar assim. Foi essa contradição que desligou este
    script uma vez (BUG-GATE-TEST-DATA-CONTRADIZ-O-GATE-DE-ANONIMATO-01).
    """
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
    """Ampliar a varredura não pode ligar o portão em `tests/fixtures/`.

    As fixtures são captura de aparelho e dado bruto de propósito; elas têm
    portão próprio (o de anonimato, que lê bytes). Ligar este aqui nelas seria
    alarme por desenho.
    """
    (tests_de_mentira / "tests" / "fixtures").mkdir()
    (tests_de_mentira / "tests" / "fixtures" / "captura.yaml").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )
    r = rodar(tests_de_mentira)
    assert r.returncode == 0, r.stdout
