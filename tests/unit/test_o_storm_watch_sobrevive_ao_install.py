from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "storm_watch.sh"
UNIT = RAIZ / "assets" / "hefesto-dualsense4unix-storm-watch.service"
A_LINHA_FALSA = "terminou inesperadamente"
PRAZO_S = 10.0

JOURNALCTL = """#!/bin/bash
for arg in "$@"; do
    [[ "$arg" == -k ]] && exit 0
done
echo $$ >"$MARCA_DO_JOURNALCTL.novo"
mv "$MARCA_DO_JOURNALCTL.novo" "$MARCA_DO_JOURNALCTL"
[[ "$JOURNALCTL_CAI" == 1 ]] && exit 0
exec sleep 300
"""


def _executavel(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o755)


def _esperar(condicao: Callable[[], bool], prazo: float = PRAZO_S) -> bool:
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()


def _filhos(pid: int) -> set[int]:
    filhos: set[int] = set()
    for tarefa in Path(f"/proc/{pid}/task").glob("*/children"):
        try:
            filhos |= {int(texto) for texto in tarefa.read_text().split()}
        except OSError:
            continue
    return filhos


def _vivo(pid: int) -> bool:
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return estado != "Z"


class _Vigia:
    def __init__(self, tmp_path: Path, *, journalctl_cai: bool) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _executavel(bin_dir / "journalctl", JOURNALCTL)
        _executavel(bin_dir / "hciconfig", "#!/bin/bash\nexit 0\n")
        self.marca = tmp_path / "journalctl-de-pe"
        self.registro = tmp_path / "state" / "hefesto-dualsense4unix" / "kernel.log"
        self.erros = tmp_path / "stderr"
        ambiente = {
            "HOME": str(tmp_path),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            "HEFESTO_KERNELWATCH_BT_INTERVAL": "300",
            "MARCA_DO_JOURNALCTL": str(self.marca),
            "JOURNALCTL_CAI": "1" if journalctl_cai else "0",
        }
        with self.erros.open("wb") as erros:
            self.processo = subprocess.Popen(
                ["bash", str(SCRIPT)],
                env=ambiente,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=erros,
                start_new_session=True,
            )

    def de_pe(self) -> set[int]:
        assert _esperar(self.marca.exists), "o journalctl de mentira não subiu"
        assert _esperar(lambda: len(_filhos(self.processo.pid)) >= 2)
        return _filhos(self.processo.pid)

    def sinal(self, numero: int, *, no_grupo: bool) -> None:
        if no_grupo:
            os.killpg(self.processo.pid, numero)
        else:
            os.kill(self.processo.pid, numero)

    def saida(self) -> int:
        return self.processo.wait(timeout=PRAZO_S)

    def texto_do_registro(self) -> str:
        return self.registro.read_text(encoding="utf-8")

    def limpar(self) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.processo.pid, signal.SIGKILL)
        self.processo.wait(timeout=PRAZO_S)


@pytest.mark.parametrize("no_grupo", [True, False], ids=["no-grupo", "so-no-principal"])
@pytest.mark.parametrize("numero", [signal.SIGTERM, signal.SIGINT], ids=["TERM", "INT"])
def test_a_parada_sai_zero_calada_e_nao_deixa_filho(
    tmp_path: Path, numero: int, no_grupo: bool
) -> None:
    vigia = _Vigia(tmp_path, journalctl_cai=False)
    try:
        filhos = vigia.de_pe()
        vigia.sinal(numero, no_grupo=no_grupo)
        assert vigia.saida() == 0
        assert A_LINHA_FALSA not in vigia.texto_do_registro()
        assert vigia.erros.read_text(encoding="utf-8") == ""
        assert _esperar(lambda: not any(_vivo(pid) for pid in filhos)), (
            "um filho direto do vigia sobreviveu à parada"
        )
    finally:
        vigia.limpar()


def test_o_journalctl_que_cai_sozinho_sai_um_e_diz_no_registro(tmp_path: Path) -> None:
    vigia = _Vigia(tmp_path, journalctl_cai=True)
    try:
        assert vigia.saida() == 1
        assert A_LINHA_FALSA in vigia.texto_do_registro()
    finally:
        vigia.limpar()


def test_a_saida_um_e_o_que_a_unit_reinicia() -> None:
    assert "Restart=on-failure" in UNIT.read_text(encoding="utf-8")
