"""O ruff não avisa «noqa» inválido: a marca de acento não se veste de diretiva dele.

O aviso «Invalid `# noqa` directive» sai em rc=0 e só sem cache, por isso o portão do ruff nunca o
viu. A marca da casa, em Python, vai entre parênteses: `# (noqa-acento) razão`.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTAS = ("src", "tests", "scripts")
AVISO = re.compile(r"Invalid `# noqa` directive on (\S+?:\d+)")
MARCA = "noqa" + "-acento"
VELHA = "noqa" + ": acentuacao"
SEM_ACENTO = "n" + "ao"


def _ruff() -> str:
    achado = shutil.which("ruff")
    if achado:
        return achado
    vizinho = Path(sys.executable).with_name("ruff")
    if vizinho.exists():
        return str(vizinho)
    pytest.skip("não há `ruff` neste ambiente (nem no PATH, nem ao lado do Python)")


def _avisos(cwd: Path, *alvos: str) -> list[str]:
    feito = subprocess.run(
        [_ruff(), "check", "--no-cache", "--exit-zero", *alvos],
        cwd=cwd, capture_output=True, text=True, check=False)
    assert feito.returncode == 0, f"o ruff não rodou (rc={feito.returncode}):\n{feito.stderr}"
    return AVISO.findall(feito.stdout + feito.stderr)


def _validador() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_validador_do_ruff", RAIZ / "scripts" / "validar-acentuacao.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_casa_nao_tem_noqa_invalido() -> None:
    """Prova da D-2510-A-MARCA-DE-ACENTO-VAI-ENTRE-PARENTESES."""
    avisos = _avisos(RAIZ, *PASTAS)
    assert not avisos, (
        f"{len(avisos)} comentário(s) que o ruff lê como `# noqa` estragado:\n  "
        + "\n  ".join(avisos)
        + f"\n\nA marca de acento, em Python, é `# ({MARCA}) razão`, e não `# {MARCA}: razão` "
        f"nem `# {VELHA}`. Prosa que cita a diretiva diz «o marcador noqa».")


def test_a_regua_morde_a_forma_velha_e_aceita_a_nova(tmp_path: Path) -> None:
    """Sem isto, um ruff que deixe de avisar faz o teste de cima passar por vacuidade."""
    velhas = [f'a = "{SEM_ACENTO}"  # {MARCA}: chave\n', f'b = "{SEM_ACENTO}"  # {VELHA}\n',
              f'c = "{SEM_ACENTO}"  # {MARCA} (chave)\n']
    novas = [f'd = "{SEM_ACENTO}"  # ({MARCA}) chave\n', f'e = "{SEM_ACENTO}"  # ({VELHA})\n']
    (tmp_path / "velha.py").write_text("".join(velhas), encoding="utf-8")
    (tmp_path / "nova.py").write_text("".join(novas), encoding="utf-8")

    assert _avisos(tmp_path, "velha.py") == [f"velha.py:{n}" for n in (1, 2, 3)]
    assert _avisos(tmp_path, "nova.py") == []


def test_o_validador_de_acento_le_a_forma_nova(tmp_path: Path) -> None:
    val = _validador()
    arquivo = tmp_path / "nova.py"
    linhas = [f'd = "{SEM_ACENTO}"  # ({MARCA}) chave\n', f'e = "{SEM_ACENTO}"  # ({VELHA})\n',
              f'f = "{SEM_ACENTO}"\n']
    arquivo.write_text("".join(linhas), encoding="utf-8")
    apontadas = [linha for linha, *_ in val.checar_arquivo(arquivo, tmp_path)]
    assert apontadas == [3], f"o validador devia pular as linhas 1 e 2 e apontar a 3: {apontadas}"
