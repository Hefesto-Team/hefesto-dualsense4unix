"""O uninstall acha o módulo DKMS mesmo quando o `dkms status` tem mais de uma linha.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), achado lendo o ensaio do
uninstall na máquina dela: o plano tirava o `hefesto-rtw88-usb` e o
`hefesto-hid-playstation`, e NÃO o `hefesto-hid-nintendo`. A causa é a forma
que o `scripts/dkms_lib.sh` já documenta desde 19/08 — com `set -o pipefail`,
um `dkms status X | grep -q .` devolve 141 exatamente quando ACHA: o `grep -q`
sai na primeira linha, o `dkms` morre de SIGPIPE escrevendo a segunda, e o
`if` lê «não instalado». O hid-nintendo dela está em DOIS kernels (duas
linhas); os outros dois, em um. O do uhid (`dkms status | grep -q
'^hefesto-uhid'`) cairia igual, com a lista inteira da máquina atrás dele.

A régua roda o ensaio (`--dry-run`) num lar de mentira com um `dkms` que dá
duas linhas com uma pausa entre elas, e exige o `dkms remove` dos quatro no
plano.

A mesma forma morava no `flatpak list --user --app | grep -q <id>`: com o
aplicativo novo listado antes do antigo, o antigo nunca saía.

A MORDIDA, medida: devolver o `| grep -q .` ao bloco do hid-nintendo (ou o
`| grep -q '^hefesto-uhid'` ao do uhid, ou o `| grep -q` ao do Flatpak) tira a
linha dele do plano, e o teste reprova.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.test_o_ensaio_do_uninstall_nao_escreve import (
    BASH,
    PATH_DO_SISTEMA,
    UNINSTALL,
    _dublar,
)

# Duas linhas com uma pausa entre elas: é o que faz o `grep -q` fechar o
# cano antes de o `dkms` terminar de escrever, como o de verdade faz.
_DKMS_DE_DOIS_KERNELS = """#!/bin/sh
[ "$1" = "status" ] || exit 0
if [ -n "$2" ]; then pkg="${2%%/*}"; else pkg="hefesto-uhid"; fi
printf '%s/1.0.0, 7.1.5-76070105-generic, x86_64: installed\\n' "$pkg"
sleep 0.3
printf '%s/1.0.0, 7.0.11-76070011-generic, x86_64: installed\\n' "$pkg"
[ -n "$2" ] || printf 'nvidia/580, 7.1.5-76070105-generic, x86_64: installed\\n'
exit 0
"""


_FLATPAK_COM_OS_DOIS_IDS = """#!/bin/sh
[ "$1" = "list" ] || exit 0
printf 'Hefesto\\tio.github.hefesto_team.hefesto_dualsense4unix\\t1.0\\tstable\\tuser\\n'
sleep 0.3
printf 'Hefesto\\tbr.andrefarias.Hefesto\\t0.9\\tstable\\tuser\\n'
exit 0
"""


def _ensaio(tmp_path: Path, **falsos: str) -> tuple[subprocess.CompletedProcess[str], str]:
    lar = tmp_path / "lar"
    casa = lar / "casa"
    casa.mkdir(parents=True)
    dubles = tmp_path / "dubles"
    diario = tmp_path / "dubles-chamados.log"
    _dublar(dubles, diario)
    for nome, corpo in falsos.items():
        (dubles / nome).write_text(corpo, encoding="utf-8")
        (dubles / nome).chmod(0o755)
    temporarios = tmp_path / "tmp"
    temporarios.mkdir()
    env = {
        "HOME": str(casa),
        "PATH": f"{dubles}:{PATH_DO_SISTEMA}",
        "LANG": "C.UTF-8",
        "TMPDIR": str(temporarios),
        "XDG_CONFIG_HOME": str(lar / "config"),
        "XDG_DATA_HOME": str(lar / "data"),
        "XDG_STATE_HOME": str(lar / "state"),
        "XDG_CACHE_HOME": str(lar / "cache"),
        "XDG_RUNTIME_DIR": str(lar / "run"),
    }
    r = subprocess.run(
        [BASH, str(UNINSTALL), "--dry-run"],
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    chamados = diario.read_text(encoding="utf-8") if diario.exists() else ""
    assert chamados == "", "o ensaio chamou binário que escreve:\n" + chamados
    return r, chamados


def test_o_plano_tira_os_quatro_modulos(tmp_path: Path) -> None:
    r, _ = _ensaio(tmp_path, dkms=_DKMS_DE_DOIS_KERNELS)
    faria = [linha for linha in r.stdout.splitlines() if "FARIA: (root) dkms remove" in linha]
    for pacote in (
        "hefesto-hid-nintendo",
        "hefesto-rtw88-usb",
        "hefesto-hid-playstation",
        "hefesto-uhid",
    ):
        assert any(f"dkms remove {pacote}/" in linha for linha in faria), (
            f"o plano do uninstall não tira o {pacote} com o `dkms status` de duas "
            "linhas — o `| grep -q` sob pipefail voltou:\n" + "\n".join(faria)
        )


def test_o_plano_tira_os_dois_flatpaks(tmp_path: Path) -> None:
    r, _ = _ensaio(tmp_path, flatpak=_FLATPAK_COM_OS_DOIS_IDS)
    faria = [linha for linha in r.stdout.splitlines() if "FARIA: flatpak uninstall" in linha]
    for app_id in ("io.github.hefesto_team.hefesto_dualsense4unix", "br.andrefarias.Hefesto"):
        assert any(app_id in linha for linha in faria), (
            f"o plano não desinstala o Flatpak {app_id} com os dois listados:\n" + "\n".join(faria)
        )
