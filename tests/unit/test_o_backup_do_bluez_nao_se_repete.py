"""O backup do `main.conf` do BlueZ não se repete — B7 da O-PRODUTO."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "bluez_config.sh"


def _etc(tmp_path: Path, conteudo: str) -> Path:
    etc = tmp_path / "etc-bluetooth"
    etc.mkdir()
    (etc / "main.conf").write_text(conteudo, encoding="utf-8")
    return etc


def _rodar(etc: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HEFESTO_BT_ETC"] = str(etc)
    env["HEFESTO_BT_SUDO"] = ""
    return subprocess.run(
        [BASH, str(SCRIPT), *args], capture_output=True, text=True, timeout=60,
        check=False, env=env,
    )


def _backups(etc: Path) -> list[Path]:
    return sorted(etc.glob("main.conf.bak.hefesto-*"))


def test_dois_ciclos_deixam_um_backup_por_estado(tmp_path: Path) -> None:
    """aplicar, remover, aplicar, remover: dois estados, dois backups — e não quatro."""
    etc = _etc(tmp_path, "[General]\nName = ESTADO-DELA\n")
    for gesto in ("aplicar", "remover", "aplicar", "remover"):
        proc = _rodar(etc, gesto)
        assert proc.returncode == 0, (gesto, proc.stdout, proc.stderr)
    backups = _backups(etc)
    conteudos = {b.read_bytes() for b in backups}
    assert len(backups) == 2, [b.name for b in backups]
    assert len(conteudos) == 2, "dois backups com os MESMOS bytes"
    assert any(b"ESTADO-DELA" in c and b"hefesto" not in c for c in conteudos), (
        "o estado original dela não está entre os backups"
    )


def test_o_backup_que_ja_existe_e_dito_e_devolvido(tmp_path: Path) -> None:
    """O segundo `aplicar` sobre o mesmo original diz onde o estado já está."""
    etc = _etc(tmp_path, "[General]\nName = ESTADO-DELA\n")
    _rodar(etc, "aplicar")
    (primeiro,) = _backups(etc)
    _rodar(etc, "remover")
    proc = _rodar(etc, "aplicar")
    assert f"já está guardado em {primeiro}" in proc.stdout, proc.stdout
    assert f"backup: {primeiro}" in proc.stdout, proc.stdout


def test_estado_novo_ganha_backup_novo(tmp_path: Path) -> None:
    """A deduplicação é por CONTEÚDO: um estado que nunca foi guardado é guardado."""
    etc = _etc(tmp_path, "[General]\nName = ESTADO-A\n")
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")
    (etc / "main.conf").write_text("[General]\nName = ESTADO-B\n", encoding="utf-8")
    _rodar(etc, "aplicar")
    conteudos = [b.read_text(encoding="utf-8") for b in _backups(etc)]
    assert any("ESTADO-A" in c for c in conteudos)
    assert any("ESTADO-B" in c for c in conteudos)

