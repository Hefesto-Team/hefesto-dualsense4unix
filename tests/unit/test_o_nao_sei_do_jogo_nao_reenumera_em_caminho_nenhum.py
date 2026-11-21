"""O «não sei» do jogo não reenumera o controle em caminho nenhum.

D-2810-O-INSTALL-COM-JOGO-ABERTO-ESPERA-O-JOGO-PARA-TROCAR: sem saber do jogo, nada se reenumera.
Cada jeito de não saber (leitor ausente, sem `python3`, leitor que levanta, leitor morto por sinal,
import quebrado e `/proc` que não se lê) passa por cada caminho do dono
(`scripts/disparo_do_udev.sh`): o install e o upgrade (sem argumento), a remoção do pacote
(`--preparar-a-remocao` e a cópia com `--apos-a-remocao`), o uninstall (`--pode-reenumerar`) e o
recover (`--so-o-usb-da-sony`). Com `udevadm` de mentira, hidraw, usb, input e o geral não disparam.

A MORDIDA: leia qualquer saída do leitor que não seja o `SEM_JOGO` exato como «sem jogo» no dono, ou
deixe o leitor engolir o `/proc` ilegível, e a régua reprova.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le

RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "scripts" / "disparo_do_udev.sh"
LEITOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "quem_o_jogo_le.py"

QUE_REENUMERAM = ("hidraw", "idVendor=054c", "subsystem-match=usb", "subsystem-match=input")
LEVANTA = 'def ha_jogo_aberto(*a, **k):\n    raise OSError("x")\n\n\n'
FERRAMENTAS = ("bash", "dirname", "rm", "rmdir", "install")

JEITOS_DE_NAO_SABER = (
    "leitor-ausente", "sem-python3", "leitor-levanta", "leitor-morto-por-sinal",
    "import-quebrado", "proc-ilegivel",
)
CAMINHOS = ("install-e-upgrade", "remoção", "uninstall", "recover")


def _leitor(jeito: str) -> str | None:
    texto = LEITOR.read_text(encoding="utf-8")
    corte = texto.index('if __name__ == "__main__"')
    return {
        "leitor-ausente": None,
        "leitor-levanta": texto[:corte] + LEVANTA + texto[corte:],
        "leitor-morto-por-sinal": "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n",
        "import-quebrado": "import modulo_que_o_pacote_nao_leva\n",
    }.get(jeito, texto)


def _proc(raiz: Path) -> Path:
    proc = raiz / "proc"
    (proc / "42").mkdir(parents=True)
    (proc / "42" / "environ").write_bytes(b"HOME=/x\0")
    (proc / "self").mkdir()
    return proc


def _ambiente(raiz: Path, jeito: str) -> tuple[dict[str, str], Path]:
    bin_ = raiz / "bin"
    bin_.mkdir()
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(0o755)
    caminho = f"{bin_}:{os.environ['PATH']}"
    if jeito == "sem-python3":
        for nome in FERRAMENTAS:
            achado = shutil.which(nome)
            assert achado, nome
            (bin_ / nome).symlink_to(achado)
        caminho = str(bin_)
    proc = raiz / "proc-que-nao-existe" if jeito == "proc-ilegivel" else _proc(raiz)
    ambiente = {
        **os.environ,
        "PATH": caminho,
        "HEFESTO_RAIZ_PROC": str(proc),
        "HEFESTO_RUN_DA_REMOCAO": str(raiz / "run" / "hefesto-dualsense4unix-remocao"),
    }
    return ambiente, diario


def _rodar(argv: list[str], ambiente: dict[str, str]) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash
    return subprocess.run([bash, *argv], env=ambiente, capture_output=True, text=True,
                          check=False, timeout=60)


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize("jeito", JEITOS_DE_NAO_SABER)
def test_o_nao_sei_nao_reenumera(tmp_path: Path, jeito: str, caminho: str) -> None:
    pacote = tmp_path / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    pacote.mkdir(parents=True)
    shutil.copy2(DONO, pacote / DONO.name)
    fonte = _leitor(jeito)
    if fonte is not None:
        (pacote / LEITOR.name).write_text(fonte, encoding="utf-8")
    ambiente, diario = _ambiente(tmp_path, jeito)
    dono = str(pacote / DONO.name)

    if caminho == "install-e-upgrade":
        feito = _rodar([dono], ambiente)
        assert feito.returncode == 0, feito.stderr
        assert "não deu para saber" in feito.stdout
    elif caminho == "remoção":
        feito = _rodar([dono, "--preparar-a-remocao"], ambiente)
        assert feito.returncode == 0, feito.stderr
        run = Path(ambiente["HEFESTO_RUN_DA_REMOCAO"])
        assert (run / "veredito").read_text(encoding="utf-8").strip() != str(
            quem_o_jogo_le.SEM_JOGO
        )
        shutil.rmtree(tmp_path / "usr")
        feito = _rodar([str(run / DONO.name), "--apos-a-remocao"], ambiente)
        assert feito.returncode == 0, feito.stderr
        assert "não deu para saber" in feito.stdout
    elif caminho == "uninstall":
        assert _rodar([dono, "--pode-reenumerar"], ambiente).returncode != 0
    else:
        feito = _rodar([dono, "--so-o-usb-da-sony"], ambiente)
        assert feito.returncode == 0, feito.stderr

    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    culpadas = [c for c in chamadas if any(a in c for a in QUE_REENUMERAM) or c == "trigger"]
    assert not culpadas, (jeito, caminho, culpadas)
