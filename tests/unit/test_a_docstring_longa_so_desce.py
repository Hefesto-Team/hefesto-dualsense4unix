"""A catraca da docstring longa MORDE: o texto de docstring acima de 10 linhas só desce.

A-DOCSTRING-DIZ-O-CONTRATO-E-A-HISTORIA-MORA-NO-DOCUMENTO-01.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_docstring_longa.py"
PACOTE = "src/hefesto_dualsense4unix"


def _modulo() -> Any:
    spec = importlib.util.spec_from_file_location("_portao_docstring_longa", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_docstring_longa"] = mod
    spec.loader.exec_module(mod)
    return mod


def _docstring(linhas: int) -> str:
    corpo = "\n".join(f"linha {i}" for i in range(linhas))
    return f'"""{corpo}\n"""\n'


def _escreve(raiz: Path, rel: str, texto: str) -> None:
    destino = raiz / PACOTE / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


def _roda(raiz: Path, capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    rc = _modulo().main(["--raiz", str(raiz), *args])
    return rc, capsys.readouterr().out


@pytest.fixture
def arvore(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """Um pacote de mentira com UMA docstring de 12 linhas, e o piso já gravado nela."""
    _escreve(tmp_path, "um.py", _docstring(12) + "x = 1\n")
    _escreve(tmp_path, "dois.py", "x = 2\n")
    rc, _ = _roda(tmp_path, capsys, "--aceitar", "docstring-longa", "--razao", "piso do ensaio")
    assert rc == 0
    return tmp_path


def test_o_piso_igual_passa(arvore: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, saida = _roda(arvore, capsys)
    assert rc == 0, saida
    assert "hoje=12" in saida and "piso=12" in saida


def test_uma_docstring_nova_acima_do_piso_reprova_e_diz_o_arquivo(
    arvore: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escreve(arvore, "dois.py", _docstring(12) + "x = 2\n")
    rc, saida = _roda(arvore, capsys)
    assert rc == 1, saida
    assert "SUBIU" in saida and "12 -> 24" in saida
    assert "dois.py" in saida, "a queixa tem de dizer QUAL arquivo subiu"


def test_a_docstring_que_cresce_no_mesmo_arquivo_reprova(
    arvore: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escreve(arvore, "um.py", _docstring(15) + "x = 1\n")
    rc, saida = _roda(arvore, capsys)
    assert rc == 1, saida
    assert "um.py" in saida


def test_abaixo_do_piso_passa_e_pede_a_descida(
    arvore: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escreve(arvore, "um.py", _docstring(11) + "x = 1\n")
    rc, saida = _roda(arvore, capsys)
    assert rc == 0, saida
    assert "--aceitar docstring-longa" in saida, "descer o piso é um gesto pedido, não calado"
    rc, _ = _roda(arvore, capsys, "--aceitar", "docstring-longa")
    assert rc == 0
    _escreve(arvore, "um.py", _docstring(12) + "x = 1\n")
    rc, saida = _roda(arvore, capsys)
    assert rc == 1, "depois de descer, voltar ao tamanho velho já é subir: " + saida


def test_o_aceitar_nao_sobe_o_piso(arvore: Path) -> None:
    """Subir só com `--forcar-piso` e razão: o `--aceitar` recusa."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    from catraca import CatracaTorta

    portao = _modulo()
    _escreve(arvore, "dois.py", _docstring(12) + "x = 2\n")
    catraca = portao.Catraca(arvore / portao.CADERNO, portao.MEDIDAS, arvore)
    with pytest.raises(CatracaTorta):
        catraca.aceitar([portao.NOME])


def test_docstring_de_dez_linhas_ou_menos_nao_conta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escreve(tmp_path, "curta.py", _docstring(10) + "x = 1\n")
    censo = _modulo().censo_das_docstrings(tmp_path)
    assert censo.numero == 0 and censo.universo == 1


def test_so_docstring_conta_nao_comentario_nem_string_solta(tmp_path: Path) -> None:
    corpo = "\n".join(f"# comentário {i}" for i in range(20))
    texto = f'"""curta"""\n{corpo}\nx = """\n' + "\n".join(["l"] * 20) + '\n"""\n'
    _escreve(tmp_path, "m.py", texto)
    assert _modulo().censo_das_docstrings(tmp_path).numero == 0


def test_classe_e_funcao_contam_como_o_modulo(tmp_path: Path) -> None:
    recuo = "\n".join(f"    linha {i}" for i in range(12))
    _escreve(
        tmp_path,
        "m.py",
        f'class C:\n    """{recuo}\n    """\n\n\ndef f():\n    """{recuo}\n    """\n',
    )
    assert _modulo().censo_das_docstrings(tmp_path).numero == 2 * 13


def test_sem_piso_gravado_reprova(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _escreve(tmp_path, "um.py", _docstring(12))
    rc, saida = _roda(tmp_path, capsys)
    assert rc == 1, saida
    assert "SEM-PISO" in saida


def test_pacote_vazio_nao_e_verde(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / PACOTE).mkdir(parents=True)
    rc, saida = _roda(tmp_path, capsys)
    assert rc == 1, saida
    assert "IMPOSSIVEL" in saida


def test_a_arvore_de_verdade_esta_no_piso(capsys: pytest.CaptureFixture[str]) -> None:
    """A régua da casa: o pacote de verdade não passa do piso gravado em `docs/data`."""
    rc = _modulo().main([])
    saida = capsys.readouterr().out
    assert rc == 0, saida
