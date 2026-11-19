"""O sudo sem senha do install se avisa e se recusa.

O-SUDO-SEM-SENHA-DO-INSTALL-SE-AVISA-E-SE-RECUSA-01: as três funções reais da camada de máquina
(a ponte do Bluetooth, a placa acordada e o atualizador), num lar de mentira, com um `sudo` de
mentira que registra cada chamada e um `visudo` que aprova. Os ajudantes rodam do fonte da
árvore, no lugar do caminho instalado.

A MORDIDA: tire o teste do `SKIP_UDEV` da guarda de qualquer uma das três e o `--no-udev` volta a
gravar em /etc/sudoers.d.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts/lib/camada_de_maquina.sh"
INSTALL = RAIZ / "install.sh"
REGRAS = ("49-hefesto-bt-ponte", "49-hefesto-placa", "49-hefesto-atualizador")

_AJUDANTES = """bash() {
    local s="$ROOT_DIR/scripts"
    case "$1" in
        */bt_ponte_privilegiada.sh) shift; command bash "$s/bt_ponte_privilegiada.sh" "$@" ;;
        */hefesto_placa_acordada.sh) shift; command bash "$s/hefesto_placa_acordada.sh" "$@" ;;
        */atualizador-raiz) shift; command bash "$s/hefesto_atualizador_raiz.sh" "$@" ;;
        *) command bash "$@" ;;
    esac
}
"""


def _executavel(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o755)


def _instalar(tmp_path: Path, **flags: str) -> tuple[str, list[str]]:
    binarios = tmp_path / "bin"
    binarios.mkdir()
    diario = tmp_path / "sudo.txt"
    _executavel(binarios / "sudo", f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{diario}"\nexit 0\n')
    _executavel(binarios / "visudo", "#!/bin/bash\nexit 0\n")
    _executavel(binarios / "getent", "#!/bin/bash\nexit 2\n")
    roteiro = "\n".join([
        f'source "{CAMADA}"', _AJUDANTES,
        "install_bt_ponte_privilegiada_host", "install_placa_acordada_host",
        "install_atualizador_raiz_host", "dizer_as_regras_do_sudo",
    ])
    feito = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, check=False, timeout=120,
        env={**os.environ, "PATH": f"{binarios}:{os.environ['PATH']}", "ROOT_DIR": str(RAIZ),
             "HOME": str(tmp_path / "lar"), "SUDO_USER": "jogadora", **flags},
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return feito.stdout, chamadas


@pytest.mark.parametrize("flag", ["SKIP_UDEV", "SEM_SUDO_SEM_SENHA"])
def test_a_opcao_nao_grava_regra_nem_poe_no_grupo(tmp_path: Path, flag: str) -> None:
    """D-1911-O-SUDO-SEM-SENHA-SE-AVISA-E-SE-RECUSA: --no-udev e o opt-out pulam as três."""
    saida, chamadas = _instalar(tmp_path, **{flag: "1"})
    assert not [c for c in chamadas if "sudoers.d" in c or "usermod" in c], chamadas
    assert saida.count("sem regra em /etc/sudoers.d") == 3, saida
    assert "Regras de administrador sem senha" not in saida


def test_o_padrao_grava_as_tres_e_o_resumo_as_lista(tmp_path: Path) -> None:
    saida, chamadas = _instalar(tmp_path)
    for regra in REGRAS:
        assert any(c.startswith("mv -f") and c.endswith(f"/etc/sudoers.d/{regra}")
                   for c in chamadas), (regra, chamadas)
    resumo = saida[saida.index("Regras de administrador sem senha"):]
    for regra in REGRAS:
        assert f"/etc/sudoers.d/{regra}:" in resumo, resumo
    assert any("usermod -aG hefesto jogadora" in c for c in chamadas)


def test_a_opcao_existe_na_ajuda_e_no_resumo_final() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    assert re.search(r"^\s+--sem-sudo-sem-senha\)\s+SEM_SUDO_SEM_SENHA=1 ;;$", texto, re.M)
    ajuda = texto[:texto.index("AJUDA\n}")]
    assert "--sem-sudo-sem-senha" in ajuda
    for regra in REGRAS:
        assert regra in ajuda
    assert texto.count("dizer_as_regras_do_sudo\n") == 2, "os dois resumos finais"
