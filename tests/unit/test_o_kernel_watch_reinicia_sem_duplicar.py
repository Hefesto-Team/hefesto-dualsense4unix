"""A atualização reinicia o kernel-watch — e ele não relê o boot por cima do log.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-2 (item 6) da
O-DIARIO-DO-RADIO-01, na forma que a conferência corrigiu:

- o passo 7b do `install.sh` fazia `enable --now`, que NÃO troca o processo de
  uma unit que já está de pé: a vigia velha seguia rodando o script antigo, sem
  as tags novas do rádio (FILA-CHEIA, BT-SOCKET, ENLACE-PARADO, BT-TRAVADO,
  CRC), até o próximo login;
- e reiniciar sem cuidado DUPLICA o kernel.log: a primeira volta de cada boot
  relê o boot inteiro, e ela se reconhece pela marca `kernel-watch.boot`. A
  vigia nova, sem marca, se acharia a primeira do boot. Por isso a marca recebe
  o boot de agora ANTES do restart.

O bloco é recortado do `install.sh` REAL e rodado num lar de mentira, com um
`systemctl` de mentira que só anota — e que, no `restart`, anota se a marca já
estava lá.

A MORDIDA, medida: tirar a gravação da marca reprova o primeiro teste; voltar ao
`enable --now` com a vigia de pé, o segundo.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")


def _bloco_7b() -> str:
    inicio = INSTALL.index('if [[ "${SKIP_KERNEL_WATCH}" -eq 1 ]]; then')
    fim = INSTALL.index("# 8. Extension AppIndicator", inicio)
    return INSTALL[inicio:fim].rsplit("# ---", 1)[0]


def _roda(tmp_path: Path, *, ativa: bool) -> tuple[Path, list[str]]:
    casa = tmp_path / "casa"
    casa.mkdir()
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    diario = tmp_path / "systemctl.log"
    marca = casa / ".local" / "state" / "hefesto-dualsense4unix" / "kernel-watch.boot"
    systemctl = fakes / "systemctl"
    systemctl.write_text(
        "#!/bin/bash\n"
        f'case "$*" in\n'
        f'  *is-active*) exit {0 if ativa else 3} ;;\n'
        f'  *restart*) if [[ -s "{marca}" ]]; then echo "restart com-marca" >> "{diario}"; '
        f'else echo "restart SEM-marca" >> "{diario}"; fi ;;\n'
        f'  *) echo "$*" >> "{diario}" ;;\n'
        "esac\nexit 0\n",
        encoding="utf-8",
    )
    systemctl.chmod(systemctl.stat().st_mode | stat.S_IEXEC)
    script = (
        "set -euo pipefail\n"
        'step() { :; }\nwarn() { printf "aviso: %s\\n" "$*"; }\n'
        f'ROOT_DIR="{RAIZ}"\nSKIP_KERNEL_WATCH=0\nDRY_RUN=0\n' + _bloco_7b()
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(casa)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return marca, chamadas


def test_com_a_vigia_de_pe_a_marca_vem_antes_do_restart(tmp_path: Path) -> None:
    marca, chamadas = _roda(tmp_path, ativa=True)
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    assert marca.read_text(encoding="utf-8").strip() == boot, (
        "a marca do boot não foi gravada: a vigia nova releria o boot inteiro e "
        "duplicaria o kernel.log"
    )
    assert "restart com-marca" in chamadas, (
        "o restart aconteceu antes da marca, ou não aconteceu:\n" + "\n".join(chamadas)
    )


def test_com_a_vigia_de_pe_ela_e_reiniciada_e_nao_so_habilitada(tmp_path: Path) -> None:
    _marca, chamadas = _roda(tmp_path, ativa=True)
    assert any(c.startswith("restart") for c in chamadas), (
        "com a vigia de pé o install só habilitou: `enable --now` não troca o "
        "processo, e a vigia velha segue com o script antigo:\n" + "\n".join(chamadas)
    )


def test_sem_a_vigia_de_pe_ela_sobe_do_jeito_de_sempre(tmp_path: Path) -> None:
    marca, chamadas = _roda(tmp_path, ativa=False)
    assert not marca.exists(), "sem vigia de pé, a primeira volta TEM de reler o boot"
    assert any("enable --now" in c for c in chamadas), chamadas
