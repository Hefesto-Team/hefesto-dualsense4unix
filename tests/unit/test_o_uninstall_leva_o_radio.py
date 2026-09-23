"""O `uninstall.sh` leva o que a leva do rádio instalou — e só o que é dela.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026). A leva do rádio pôs na máquina
coisas que o uninstall de antes não conhecia:

- o NOME DO LUGAR no Alias de cada adaptador (ENTRADA-A-ENTRADA-02). O bloco de
  reversão olhava só o PRIMEIRO adaptador e só tirava o prefixo «Nintendo »; o
  rádio dela ficava chamado «Sofá» para sempre (P-11);
- o registro dos lugares dos adaptadores (BLUEZ-UM-DONO-01), que é ESTADO e
  sai sempre (P-6);
- o diário do rádio da sessão e a marca do boot do kernel-watch
  (O-DIARIO-DO-RADIO-01), que são HISTÓRICO e seguem a doutrina dos dados
  dela: ficam por padrão, saem com --purge-config (P-2).

Os blocos são recortados do `uninstall.sh` REAL e rodados num lar de mentira,
com `sudo` e `busctl` de mentira que só anotam — nada escala privilégio e nada
fala com o BlueZ de ninguém.

A MORDIDA, medida: tirar o ramo `_e_do_hefesto` do bloco dos nomes reprova os
três casos de lugar; tirar o `rm -f` do `lugares-dos-adaptadores.json`, o
teste dele; trocar o `KEEP_CONFIG` da marca do boot por um `rm` incondicional,
o teste da marca.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")


def _recorte(inicio: str, fim: str) -> str:
    a = UNINSTALL.index(inicio)
    b = UNINSTALL.index(fim, a)
    return UNINSTALL[a:b]


def _fake(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# 1. Os nomes dos adaptadores (P-11)
# ---------------------------------------------------------------------------

BLOCO_DOS_NOMES = _recorte(
    "# BT-NINTENDO-ACTIVE-01: reverter a link policy",
    "    if [[ -d /var/lib/hefesto-dualsense4unix/bt-bonds ]]; then",
)


def _mesa(tmp_path: Path, adaptadores: dict[str, tuple[str, str]], lugares: list[str]):
    fakes = tmp_path / "fakes"
    sysfs = tmp_path / "sysfs"
    props = tmp_path / "props"
    casa = tmp_path / "casa"
    for pasta in (sysfs, props, casa):
        pasta.mkdir()
    for hci, (alias, nome) in adaptadores.items():
        (sysfs / hci).mkdir()
        (props / f"{hci}.Alias").write_text(alias, encoding="utf-8")
        (props / f"{hci}.Name").write_text(nome, encoding="utf-8")
    config = casa / ".config" / "hefesto-dualsense4unix"
    config.mkdir(parents=True)
    (config / "maquina.json").write_text(
        json.dumps(
            {
                "version": 1,
                "lugares": {f"pci-0000:00:14.0-usb-0:{i}:1.0": {"nome": n} for i, n in enumerate(lugares)},
            }
        ),
        encoding="utf-8",
    )
    _fake(fakes, "sudo", 'printf "SUDO:%s\\n" "$(printf "[%s]" "$@")"\nexit 0\n')
    _fake(
        fakes,
        "busctl",
        f"""
if [[ "$1" == "get-property" ]]; then
    hci="${{3##*/}}"
    f="{props}/${{hci}}.$5"
    [[ -f "$f" ]] && printf 's "%s"\\n' "$(cat "$f")"
fi
exit 0
""",
    )
    # Sem `hciconfig`: a metade da link policy não é o que esta régua mede.
    _fake(fakes, "hciconfig", "exit 1\n")
    script = "set -uo pipefail\n" 'log() { printf "[uninstall] %s\\n" "$*"; }\n' + BLOCO_DOS_NOMES
    ambiente = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(casa),
        "HEFESTO_SYSFS_BLUETOOTH": str(sysfs),
        "LC_ALL": "C.UTF-8",
    }
    return subprocess.run(
        [BASH, "-c", script], env=ambiente, capture_output=True, text=True, timeout=60, check=False
    )


def _escritas(saida: str) -> dict[str, str]:
    """`{hciN: alias escrito}` das chamadas `sudo busctl set-property`."""
    escritas: dict[str, str] = {}
    for linha in saida.splitlines():
        if not linha.startswith("SUDO:[busctl][set-property]"):
            continue
        partes = linha.removeprefix("SUDO:")[1:-1].split("][")
        escritas[partes[3].rsplit("/", 1)[-1]] = partes[-1]
    return escritas


def test_o_nome_do_lugar_volta_ao_padrao_em_todo_adaptador(tmp_path: Path) -> None:
    r = _mesa(
        tmp_path,
        {
            "hci0": ("Nintendo Sofá", "meu-pc"),
            "hci1": ("Mesa da TV", "meu-pc"),
            "hci2": ("Nintendo meu-pc", "meu-pc"),
            "hci3": ("Nintendo Nome Dela", "meu-pc"),
            "hci4": ("Outro Nome", "meu-pc"),
        },
        ["Sofá", "Mesa da TV"],
    )
    assert r.returncode == 0, r.stderr
    escritas = _escritas(r.stdout)
    assert escritas.get("hci0") == "", (
        "o nome do lugar com o prefixo ficou no adaptador depois do uninstall:\n" + r.stdout
    )
    assert escritas.get("hci1") == "", (
        "o nome do lugar SEM o prefixo ficou no adaptador (o bloco só olhava o «Nintendo »):\n"
        + r.stdout
    )
    assert escritas.get("hci2") == "", "«Nintendo » + o nome do sistema é inteiro do Hefesto"
    assert escritas.get("hci3") == "Nome Dela", (
        "um nome que não é do Hefesto tem de ficar — só o prefixo sai:\n" + r.stdout
    )
    assert "hci4" not in escritas, "um nome de terceiro, sem o prefixo, não é tocado"
    assert "devolvido ao padrão do sistema" in r.stdout


def test_sem_maquina_json_o_prefixo_ainda_sai(tmp_path: Path) -> None:
    """A casa sem nenhum lugar declarado: o comportamento de antes, intacto."""
    r = _mesa(tmp_path, {"hci0": ("Nintendo meowsystem", "outra")}, [])
    assert _escritas(r.stdout).get("hci0") == "meowsystem", r.stdout


# ---------------------------------------------------------------------------
# 2. O estado do rádio na sessão (P-2, P-6)
# ---------------------------------------------------------------------------

BLOCO_DA_SESSAO = _recorte(
    "# O RÁDIO DA SESSÃO (a leva do rádio, 23/09/2026)",
    'rmdir "${ESTADO_DO_RADIO}" 2>/dev/null || true\n',
)


def _estado(tmp_path: Path, *, purge: bool) -> tuple[Path, subprocess.CompletedProcess[str]]:
    estado = tmp_path / "estado" / "hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    for nome in (
        "lugares-dos-adaptadores.json",
        "radio-diario.jsonl",
        "radio-diario.jsonl.1",
        "kernel.log",
        "kernel-watch.boot",
    ):
        (estado / nome).write_text("x\n", encoding="utf-8")
    script = (
        "set -uo pipefail\n"
        'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        f"KEEP_CONFIG={0 if purge else 1}\n" + BLOCO_DA_SESSAO
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp_path / "casa"),
            "XDG_STATE_HOME": str(tmp_path / "estado"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return estado, r


def test_por_padrao_o_estado_sai_e_o_historico_fica_com_carimbo(tmp_path: Path) -> None:
    estado, r = _estado(tmp_path, purge=False)
    assert r.returncode == 0, r.stderr
    sobra = sorted(p.name for p in estado.iterdir())
    assert "lugares-dos-adaptadores.json" not in sobra, (
        "o registro dos lugares é ESTADO e sai sempre — ficou: " + ", ".join(sobra)
    )
    assert "radio-diario.jsonl" not in sobra and "radio-diario.jsonl.1" not in sobra, (
        "o diário ficou com o nome de antes: a próxima instalação o releria no "
        "arranque como se fosse desta vida — " + ", ".join(sobra)
    )
    guardados = [n for n in sobra if n.startswith("radio-diario.pre-uninstall-")]
    assert len(guardados) == 2, f"o diário tem de ficar guardado com carimbo: {sobra}"
    assert "kernel.log" in sobra and "kernel-watch.boot" in sobra, (
        "o kernel.log e a marca do boot andam juntos e ficam por padrão: " + ", ".join(sobra)
    )


def test_com_purge_config_o_historico_sai_inteiro(tmp_path: Path) -> None:
    estado, r = _estado(tmp_path, purge=True)
    assert r.returncode == 0, r.stderr
    assert not estado.exists() or not any(estado.iterdir()), (
        "com --purge-config o histórico do rádio tinha de sair: "
        + ", ".join(sorted(p.name for p in estado.iterdir()))
    )


# ---------------------------------------------------------------------------
# 3. As peças de root, no texto que EXECUTA (a paridade confere o par inteiro)
# ---------------------------------------------------------------------------


def _codigo(texto: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith(("#", "log "))
    )


def test_a_trava_os_carimbos_e_o_diario_do_root_saem() -> None:
    codigo = _codigo(UNINSTALL)
    assert "rm -rf /run/hefesto-bt-ponte" in codigo, "os carimbos do reinício da ponte ficam"
    assert "/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf" in codigo
    assert "sudo rmdir /run/hefesto-dualsense4unix" in codigo
    assert "/var/lib/hefesto-dualsense4unix/radio-diario.jsonl" in codigo
