"""BUSCA-DO-RADIO-02 — o instrumento que mede a varredura e DIZ o que ela quer dizer."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "medir_a_varredura.sh"


def _veredito(linha_medida: str, adaptadores: list[str], tmp_path: Path) -> str:
    """Roda só o bloco de veredito do script, com uma saída fabricada."""
    arquivo = tmp_path / "medida.txt"
    arquivo.write_text(linha_medida + "\n", encoding="utf-8")
    corpo = SCRIPT.read_text(encoding="utf-8")
    bloco = corpo.split("printf '\\n  ── O QUE ISTO DIZ", 1)[1]
    bloco = "printf '\\n  -- O QUE ISTO DIZ" + bloco
    roteiro = textwrap.dedent(f"""
        set -euo pipefail
        ADPS=({" ".join(adaptadores)})
        SAIDA="{arquivo}"
    """) + bloco
    fim = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, check=False
    )
    return fim.stdout


def test_o_script_existe_e_nao_pede_sudo(tmp_path: Path) -> None:
    corpo = SCRIPT.read_text(encoding="utf-8")
    assert SCRIPT.is_file()
    executa = [
        linha
        for linha in corpo.splitlines()
        if "sudo" in linha and not linha.lstrip().startswith("#")
    ]
    assert not executa, f"o instrumento pede sudo:\n{executa}"
    liga = [
        linha
        for linha in corpo.splitlines()
        if "StartDiscovery" in linha and not linha.lstrip().startswith("#")
    ]
    assert not liga, f"o instrumento liga a busca e mede a si mesmo:\n{liga}"


def test_ninguem_varreu(tmp_path: Path) -> None:
    saida = _veredito("hci0=false hci1=false hci2=false", ["hci0", "hci1", "hci2"], tmp_path)
    assert "NENHUM" in saida
    assert "RESOLVE" not in saida, "deu conselho de reserva sem ter medido varredura"


def test_um_so_de_tres_libera_a_reserva(tmp_path: Path) -> None:
    saida = _veredito("hci0=true hci1=false hci2=false", ["hci0", "hci1", "hci2"], tmp_path)
    assert "UM SÓ" in saida
    assert "RESERVA RESOLVE" in saida
    assert "hci0" in saida, "não disse QUAL varreu"


def test_todos_matam_a_reserva(tmp_path: Path) -> None:
    saida = _veredito("hci0=true hci1=true hci2=true", ["hci0", "hci1", "hci2"], tmp_path)
    assert "TODOS" in saida
    assert "NÃO RESOLVE" in saida, (
        "com os três varrendo, a reserva morre — e o instrumento tem de dizer "
        "isso, não deixar a pessoa concluir"
    )
    assert "PONTE-SEM-CHAMADOR-01" in saida, "não apontou o caminho que sobra"


def test_dois_de_tres_nomeia_a_regra(tmp_path: Path) -> None:
    saida = _veredito("hci0=true hci1=true hci2=false", ["hci0", "hci1", "hci2"], tmp_path)
    assert "2 DE 3" in saida or "VARREU 2" in saida
    assert "REGRA" in saida, "o caso mais interessante saiu sem nome"


def test_maquina_de_um_adaptador_nao_ganha_conselho_de_reserva(tmp_path: Path) -> None:
    saida = _veredito("hci0=true", ["hci0"], tmp_path)
    assert "UM ADAPTADOR SÓ" in saida, (
        "numa máquina de um adaptador o instrumento aconselhou reservar — não "
        "há para onde. É a presunção da bancada de quem escreveu."
    )
    assert "RESERVA RESOLVE" not in saida
