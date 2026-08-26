"""A varredura da canônica desce para as subpastas.

ENDURECIMENTO, não conserto de defeito vivo — e a distinção está escrita aqui
de propósito. Medido em 26/08/2026 (LEVA-4-E): `docs/protocol/` é PLANO hoje,
e `glob("*.md")` e `rglob("*.md")` devolviam os mesmos 13 documentos e as
mesmas 123 citações conferidas. **Nada estava sendo perdido.**

O que se fecha é o defeito de FORMA: `pasta.glob("*.md")` fica verde por não
olhar no dia em que a canônica ganhar uma subpasta, e um portão que emudece
quando o território cresce é o mesmo defeito que a casa achou em 25/08 no
`test_nome_citado_como_sprint`. Este arquivo é o que impede a forma rasa de
voltar.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-citacoes-de-linha.py"

#: Duas linhas — qualquer endereço acima de 2 é podre por construção.
FONTE_CURTA = "primeira linha\nsegunda linha\n"


def monta_arvore(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "protocol").mkdir(parents=True, exist_ok=True)
    (tmp_path / "alvo_de_teste.py").write_text(FONTE_CURTA, encoding="utf-8")
    return tmp_path


def rodar(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(raiz), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_citacao_podre_em_subpasta_e_pega(tmp_path: Path) -> None:
    """MORDIDA — o documento está uma pasta abaixo da raiz vigiada."""
    raiz = monta_arvore(tmp_path)
    sub = raiz / "docs" / "protocol" / "dualsense"
    sub.mkdir(parents=True)
    (sub / "registro-31.md").write_text(
        "O bit vive em `alvo_de_teste.py:99`, e sempre viveu.\n", encoding="utf-8"
    )

    processo = rodar(raiz, "--all")

    assert processo.returncode == 1, (
        "a subpasta da canônica não foi varrida — citação podre passou:\n"
        + processo.stdout
    )
    assert "registro-31.md" in processo.stdout
    assert "alvo_de_teste.py:99" in processo.stdout


def test_citacao_boa_em_subpasta_continua_verde(tmp_path: Path) -> None:
    """Régua que só sabe reprovar não é régua."""
    raiz = monta_arvore(tmp_path)
    sub = raiz / "docs" / "protocol" / "dualsense"
    sub.mkdir(parents=True)
    (sub / "registro-31.md").write_text(
        "O bit vive em `alvo_de_teste.py:2`.\n", encoding="utf-8"
    )
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout
    assert "1 documento(s)" in processo.stdout


def test_a_raiz_plana_continua_varrida(tmp_path: Path) -> None:
    """Ganhar alcance não pode ser perder o alcance que já havia."""
    raiz = monta_arvore(tmp_path)
    (raiz / "docs" / "protocol" / "canonica.md").write_text(
        "O bit vive em `alvo_de_teste.py:99`.\n", encoding="utf-8"
    )
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "canonica.md" in processo.stdout


def test_arquivo_de_subpasta_passado_a_mao_nao_e_descartado(tmp_path: Path) -> None:
    """MORDIDA do modo por argumento, que tinha o MESMO defeito de forma.

    O filtro era `p.resolve().parent == (raiz / PASTA).resolve()` — um `.md` de
    subpasta era jogado fora sem uma palavra, e o script imprimia "Nenhum
    documento para varrer" com `rc=0`. Recusa silenciosa é a forma mais barata
    de um portão mentir.
    """
    raiz = monta_arvore(tmp_path)
    sub = raiz / "docs" / "protocol" / "dualsense"
    sub.mkdir(parents=True)
    alvo = sub / "registro-31.md"
    alvo.write_text("`alvo_de_teste.py:99`\n", encoding="utf-8")

    processo = rodar(raiz, str(alvo))

    assert processo.returncode == 1, processo.stdout
    assert "Nenhum documento para varrer" not in processo.stdout


def test_md_de_fora_da_canonica_continua_recusado(tmp_path: Path) -> None:
    """O alcance cresce para BAIXO da pasta vigiada, e não para fora dela."""
    raiz = monta_arvore(tmp_path)
    (raiz / "docs" / "process").mkdir(parents=True, exist_ok=True)
    fora = raiz / "docs" / "process" / "sprint-velha.md"
    fora.write_text("`alvo_de_teste.py:99`\n", encoding="utf-8")

    processo = rodar(raiz, str(fora))

    assert processo.returncode == 0, processo.stdout
    assert "Nenhum documento para varrer" in processo.stdout
