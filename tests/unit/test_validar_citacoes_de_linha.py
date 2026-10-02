"""O portão que ABRE cada `arquivo:linha` de `docs/protocol/` — CITACOES-DERIVADAS-01."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-citacoes-de-linha.py"
CI = RAIZ_REAL / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = RAIZ_REAL / ".pre-commit-config.yaml"

COMANDO = "scripts/validar-citacoes-de-linha.py --all"


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--all", "--root", str(raiz)],
        capture_output=True, text=True, cwd=raiz, check=False)


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore de brinquedo com um módulo de dez linhas e um documento vazio."""
    modulo = tmp_path / "src" / "hefesto_dualsense4unix" / "core"
    modulo.mkdir(parents=True)
    (modulo / "exemplo.py").write_text(
        "\n".join(f"linha_{n} = {n}" for n in range(1, 11)) + "\n"
        "FLAG_DE_AUDIO = 0x01\n",
        encoding="utf-8")
    (tmp_path / "docs" / "protocol").mkdir(parents=True)
    return tmp_path


def documento(arvore: Path, texto: str) -> None:
    (arvore / "docs" / "protocol" / "exemplo.md").write_text(texto, encoding="utf-8")


def test_a_fonte_de_fora_da_arvore_e_ignorada(arvore: Path) -> None:
    """136 dos 204 endereços de `docs/protocol/` citam kernel, SDL e wine."""
    documento(arvore, "o driver faz isso em `hid-nintendo.c:99999`.\n")
    saida = rodar(arvore)
    assert saida.returncode == 0, (
        f"acusou uma fonte que esta árvore não versiona. Disse: {saida.stdout!r}")
    assert "fora desta árvore" in saida.stdout


def test_a_arvore_de_verdade_esta_limpa() -> None:
    """Contra a árvore REAL: depois do reaponte de 13/08, ela abre inteira."""
    saida = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"],
        capture_output=True, text=True, cwd=RAIZ_REAL, check=False)
    assert saida.returncode == 0, (
        "há citação de linha podre em docs/protocol/ — o endereço deixou de "
        f"abrir no que promete:\n{saida.stdout}")


def test_o_portao_esta_ligado_no_ci_e_no_pre_commit() -> None:
    """PORTÃO-VIVO-01: gate que ninguém roda não é gate, é arquivo."""
    yaml = pytest.importorskip("yaml")

    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos = [
        {**passo, "__job__": nome}
        for nome, job in (dados.get("jobs") or {}).items()
        for passo in job.get("steps") or []
    ]
    rodam = [p for p in passos if COMANDO in " ".join(str(p.get("run", "")).split())]
    assert rodam, f"o CI não chama `{COMANDO}`"
    for passo in rodam:
        assert not passo.get("continue-on-error"), (
            f"o passo '{passo.get('name', passo['__job__'])}' relata, não protege")

    hooks = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    entradas = [
        hook.get("entry", "")
        for repositorio in hooks.get("repos") or []
        for hook in repositorio.get("hooks") or []
    ]
    assert any(COMANDO in entrada for entrada in entradas), (
        f"nenhum hook do pre-commit roda `{COMANDO}`")


def test_o_portao_esta_no_gancho_que_de_fato_roda() -> None:
    """PORTÃO-VIVO-01, a metade que faltava — MEDIDA em 24/08/2026."""
    gancho = RAIZ_REAL / "scripts" / "hooks" / "pre-commit"
    texto = gancho.read_text(encoding="utf-8")
    assert COMANDO in texto, (
        f"`{COMANDO}` está no .pre-commit-config.yaml, mas NÃO no gancho que de "
        f"fato roda ({gancho.relative_to(RAIZ_REAL)}) — e é ele que o "
        "`core.hooksPath` global encadeia. Portão declarado não é portão vivo.")
