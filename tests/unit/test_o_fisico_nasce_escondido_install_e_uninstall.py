"""O install põe a regra do nó no lugar novo e tira a velha; o uninstall tira as duas.

O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01 (25/09/2026). A regra que fecha
o hidraw do DualSense físico passou de `70-ps5-controller.rules` para
`73-hefesto-ps5-controller.rules`, porque a `71-sony-controllers.rules` do pacote
`game-devices-udev` corria depois da 70 e reabria o nó (o porquê inteiro está no
cabeçalho do asset). Um nome que muda deixa DUAS perguntas, e cada uma tem
régua aqui:

1. **nada fica órfão**: o `install_udev.sh` grava a nova e tira a velha de /etc;
   o `install-host-udev.sh` (o caminho do .deb e do Flatpak) faz o mesmo; o
   `uninstall.sh` tira as duas;
2. **o helper dos pacotes ainda acha as regras**: ele reconhece a pasta de
   origem PELO NOME da regra do nó. Esquecê-lo derrubava o helper inteiro
   («regras udev não encontradas»), e com ele o broker e os três DKMS.

O molde é o de `test_o_uninstall_nao_deixa_rastro_em_run.py`: os blocos são
recortados dos scripts REAIS e rodam com o /etc trocado por uma pasta de
mentira; o `sudo` de mentira executa só `install` e `rm`, recusa qualquer
argumento que ainda aponte para o /etc de verdade, e só ANOTA o resto
(`udevadm`, `groupdel`…). Nada aqui pede senha nem toca o udev vivo.

A MORDIDA, medida: tirar o `rm -f` da velha do `install_udev.sh` reprova a 1;
voltar o laço de origem do helper para o nome 70 reprova a 3; tirar a velha do
`uninstall.sh` reprova a 5.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
NOVA = "73-hefesto-ps5-controller.rules"
VELHA = "70-ps5-controller.rules"

INSTALL_UDEV = (RAIZ / "scripts" / "install_udev.sh").read_text(encoding="utf-8")
HOST_UDEV = (RAIZ / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")

#: O `sudo` de mentira: `install` e `rm` executam; o resto só se anota.
SUDO_DE_MENTIRA = r"""#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    /etc/*|/usr/*|/lib/*|/run/*) echo "RECUSEI $a" >&2; exit 97 ;;
  esac
done
while [[ "${1:-}" == -[nAEHkS] ]]; do shift; done
case "${1:-}" in
  install|rm) exec "$@" ;;
  *) echo "ANOTEI $*" >> "${ANOTACOES:-/dev/null}"; exit 0 ;;
esac
"""


def _recorte(texto: str, inicio: str, fim: str) -> str:
    a = texto.index(inicio)
    b = texto.index(fim, a)
    return texto[a:b]


def _comando_com_continuacao(texto: str, inicio: str) -> str:
    """Do `inicio` até a primeira linha que não termina em barra invertida."""
    a = texto.index(inicio)
    linhas = []
    for linha in texto[a:].splitlines():
        linhas.append(linha)
        if not linha.rstrip().endswith("\\"):
            break
    return "\n".join(linhas) + "\n"


def _funcao(texto: str, nome: str) -> str:
    a = texto.index(f"{nome}() {{")
    b = texto.index("\n}\n", a)
    return texto[a : b + 3]


def _rodar(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    fakes = tmp_path / "fakes"
    fakes.mkdir(exist_ok=True)
    sudo = fakes / "sudo"
    sudo.write_text(SUDO_DE_MENTIRA, encoding="utf-8")
    sudo.chmod(0o755)
    r = subprocess.run(
        [BASH, "-c", "set -euo pipefail\n" + script],
        env={
            "PATH": f"{fakes}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "LC_ALL": "C.UTF-8",
            "ANOTACOES": str(tmp_path / "anotacoes"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "RECUSEI" not in r.stderr, r.stderr
    return r


def _etc_de_mentira(tmp_path: Path) -> Path:
    etc = tmp_path / "etc" / "udev" / "rules.d"
    etc.mkdir(parents=True)
    return etc


def _efetivas(arquivo: Path) -> list[str]:
    return [
        linha
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# 1-2. install_udev.sh — o caminho do checkout (o install.sh dela)
# ---------------------------------------------------------------------------

BLOCO_DA_REGRA_DO_NO = _recorte(
    INSTALL_UDEV,
    'if [[ "$ABRIR_O_NO" -eq 1 ]]; then\n    # A transformação tem UM DONO',
    'sudo install -Dm644 "$ASSETS/71-uinput.rules"',
)


def _instalar_a_regra_do_no(tmp_path: Path, *, abrir: bool) -> Path:
    etc = _etc_de_mentira(tmp_path)
    (etc / VELHA).write_text("# a de antes\n", encoding="utf-8")
    bloco = BLOCO_DA_REGRA_DO_NO.replace("/etc/udev/rules.d/", f"{etc}/")
    assert "/etc/udev" not in bloco.replace(str(etc), ""), bloco
    script = (
        f'HERE="{RAIZ}"\nASSETS="{RAIZ}/assets"\nABRIR_O_NO={1 if abrir else 0}\n' + bloco
    )
    r = _rodar(tmp_path, script)
    assert r.returncode == 0, r.stderr
    return etc


def test_o_install_grava_a_nova_fechada_e_tira_a_velha(tmp_path: Path) -> None:
    etc = _instalar_a_regra_do_no(tmp_path, abrir=False)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA], "a velha ficou, ou a nova não entrou"
    assert (etc / NOVA).read_bytes() == (RAIZ / "assets" / NOVA).read_bytes()


def test_o_opt_out_grava_a_nova_aberta_e_tira_a_velha(tmp_path: Path) -> None:
    """`--no-fechar-o-no`: o mesmo nome, a variante aberta, e a velha fora."""
    etc = _instalar_a_regra_do_no(tmp_path, abrir=True)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    linhas = _efetivas(etc / NOVA)
    assert not any('TAG-="uaccess"' in linha for linha in linhas), linhas
    assert sum('TAG+="uaccess"' in linha for linha in linhas) == 5, linhas


# ---------------------------------------------------------------------------
# 3-4. install-host-udev.sh — o caminho do .deb e do Flatpak
# ---------------------------------------------------------------------------

LACO_DA_ORIGEM = _recorte(
    HOST_UDEV,
    'RULES_SRC=""\n',
    'for candidate in \\\n    "/app/share/hefesto-dualsense4unix/modules-load"',
)


def test_o_helper_acha_a_pasta_das_regras_pelo_nome_novo(tmp_path: Path) -> None:
    """Esquecer o laço de origem derrubava o helper inteiro."""
    assets = tmp_path / "bundle" / "assets"
    assets.mkdir(parents=True)
    (tmp_path / "bundle" / "scripts").mkdir()
    shutil.copy(RAIZ / "assets" / NOVA, assets / NOVA)
    script = (
        f'SCRIPT_DIR="{tmp_path}/bundle/scripts"\n'
        + LACO_DA_ORIGEM
        + 'echo "ORIGEM=${RULES_SRC}"\n'
    )
    r = _rodar(tmp_path, script)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"ORIGEM={tmp_path}/bundle/scripts/../assets", r.stdout


def test_o_comando_de_root_do_helper_grava_a_nova_e_tira_a_velha(tmp_path: Path) -> None:
    """O comando que o helper monta, EXECUTADO só nas linhas de `install`/`rm` das regras."""
    src = tmp_path / "src"
    src.mkdir()
    shutil.copy(RAIZ / "assets" / NOVA, src / NOVA)
    shutil.copy(RAIZ / "assets" / "71-uinput.rules", src / "71-uinput.rules")
    etc = _etc_de_mentira(tmp_path)
    (etc / VELHA).write_text("# a de antes, fechada\n", encoding="utf-8")
    escopo = "\n".join(
        (
            'BROKER_BIN_SRC="" BROKER_INSTALL_OK=1 BROKER_SESSION_GROUP="" BROKER_SESSION_UID=0',
            'BROKER_UNITS_SRC="" BTRES_INSTALL_OK=0 BTRES_SCRIPTS_SRC="" BTRES_UNIT_SRC=""',
            'BTUSB_SRC="" HIDNINTENDO_SRC="" HIDPLAYSTATION_SRC=""',
            'MODLOAD_DEST=/x MODLOAD_SRC="" SNDQUIRK_DEST=/x SNDQUIRK_SRC=""',
            f'RULES_SRC="{src}" RULES_DEST="{etc}"',
            f'RULES=("{NOVA}" "71-uinput.rules")',
            f'REGRA_DO_NO="{NOVA}" REGRA_DO_NO_SRC="{src}/{NOVA}" REGRA_DO_NO_VELHA="{VELHA}"',
        )
    )
    montador = _funcao(HOST_UDEV, "_build_install_cmd")
    r = _rodar(tmp_path, escopo + "\n" + montador + "\n_build_install_cmd\n")
    assert r.returncode == 0, r.stderr
    comandos = [c.strip() for c in r.stdout.split("; ")]
    das_regras = [
        c for c in comandos if c.startswith(("install -Dm644", "rm -f")) and str(etc) in c
    ]
    assert f"rm -f '{etc}/{VELHA}'" in das_regras, das_regras
    executar = _rodar(tmp_path, "\n".join(das_regras) + "\n")
    assert executar.returncode == 0, executar.stderr
    assert sorted(p.name for p in etc.iterdir()) == sorted([NOVA, "71-uinput.rules"])


# ---------------------------------------------------------------------------
# 5. uninstall.sh — as duas saem
# ---------------------------------------------------------------------------

RM_DAS_REGRAS = _comando_com_continuacao(
    UNINSTALL, f"sudo rm -f /etc/udev/rules.d/{NOVA}"
)


def test_o_uninstall_tira_a_nova_e_a_velha(tmp_path: Path) -> None:
    etc = _etc_de_mentira(tmp_path)
    for nome in (NOVA, VELHA, "71-uinput.rules", "99-de-outro-programa.rules"):
        (etc / nome).write_text("#\n", encoding="utf-8")
    raiz_etc = tmp_path / "etc"
    bloco = RM_DAS_REGRAS.replace("/etc/", f"{raiz_etc}/")
    assert not re.search(r"(^|\s)/etc/", bloco), bloco
    r = _rodar(tmp_path, bloco)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in etc.iterdir()) == ["99-de-outro-programa.rules"]


def test_o_keep_udev_ensina_a_tirar_as_duas() -> None:
    """A receita à mão do `--keep-udev` também leva os dois nomes."""
    linha = next(
        linha for linha in UNINSTALL.splitlines() if 'log "  sudo rm /etc/udev/rules.d/' in linha
    )
    assert f"/etc/udev/rules.d/{NOVA}" in linha
    assert f"/etc/udev/rules.d/{VELHA}" in linha
