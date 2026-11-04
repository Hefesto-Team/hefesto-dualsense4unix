"""O CSV dos tempos que o fecho gera não conta como crescimento de código na catraca da origem."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
CSV_DOS_TEMPOS = "docs/data/tempos-da-suite.csv"


def _portao() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_a_origem_dos_tempos", RAIZ / "scripts" / "check_a_origem.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_a_origem_dos_tempos"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _escreve(raiz: Path, rel: str, linhas: int) -> None:
    destino = raiz / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(f"linha {n}\n" for n in range(linhas)), encoding="utf-8")


def test_o_csv_dos_tempos_com_24_linhas_a_mais_nao_muda_o_tamanho(tmp_path: Path) -> None:
    """Teste novo entra no CSV gerado: a Origem já foi paga no commit do teste."""
    portao = _portao()
    _escreve(tmp_path, "src/hefesto_dualsense4unix/a.py", 10)
    _escreve(tmp_path, CSV_DOS_TEMPOS, 100)
    antes = portao.censo_do_tamanho(tmp_path).numero

    _escreve(tmp_path, CSV_DOS_TEMPOS, 124)

    assert portao.censo_do_tamanho(tmp_path).numero == antes == 10


def test_um_arquivo_de_src_com_24_linhas_a_mais_muda_o_tamanho(tmp_path: Path) -> None:
    """O contraste: o mesmo crescimento em código, ou em outro CSV de dados, conta."""
    portao = _portao()
    _escreve(tmp_path, "src/hefesto_dualsense4unix/a.py", 10)
    _escreve(tmp_path, "docs/data/outro.csv", 5)
    antes = portao.censo_do_tamanho(tmp_path).numero

    _escreve(tmp_path, "src/hefesto_dualsense4unix/a.py", 34)
    assert portao.censo_do_tamanho(tmp_path).numero == antes + 24

    _escreve(tmp_path, "docs/data/outro.csv", 29)
    assert portao.censo_do_tamanho(tmp_path).numero == antes + 48
