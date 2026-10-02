"""BT-AGENT-TRAVA-O-RESTART-01, E4 e E5 — o gancho de parada não segura o rádio."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh"
DROPIN = REPO_ROOT / "assets" / "systemd" / "bluetooth-dropin-10-hefesto-resilience.conf"

ADAPTER = "AA:BB:CC:00:00:01"
CONTROLE = "AA:BB:CC:00:00:02"

TETO_S = 6.0
PACIENCIA_S = 3.0


def _fonte_com_um_bond(raiz: Path) -> Path:
    """Uma árvore /var/lib/bluetooth de mentira, com um bond de verdade."""
    dev = raiz / ADAPTER / CONTROLE
    dev.mkdir(parents=True)
    (dev / "info").write_text(
        "[General]\nName=DualSense Wireless Controller\n\n[LinkKey]\nKey=AAAA\n",
        encoding="utf-8",
    )
    return raiz


def _ambiente(
    fonte: Path, acervo: Path, diario: Path, service_result: str | None
) -> dict[str, str]:
    env = {
        **os.environ,
        "HEFESTO_BT_SRC": str(fonte),
        "HEFESTO_BT_SNAP_ROOT": str(acervo),
        "HEFESTO_BT_LOG_DEST": str(diario),
    }
    env.pop("SERVICE_RESULT", None)
    if service_result is not None:
        env["SERVICE_RESULT"] = service_result
    return env


@pytest.fixture()
def lock_ocupado(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Segura o `.lock` do acervo por um processo de fora, como na vida real."""
    acervo = tmp_path / "bt-bonds"
    acervo.mkdir(parents=True)
    lock = acervo / ".lock"
    lock.touch()
    dono = subprocess.Popen(
        ["flock", str(lock), "sleep", "60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    prazo = time.monotonic() + 5.0
    while time.monotonic() < prazo:
        livre = subprocess.run(
            ["flock", "-n", str(lock), "true"], capture_output=True
        )
        if livre.returncode != 0:
            break
        time.sleep(0.05)
    else:  # pragma: no cover — só numa máquina onde o flock(1) não tranca
        dono.kill()
        pytest.skip("não consegui segurar o .lock com flock(1)")
    yield acervo
    dono.kill()
    dono.wait(timeout=5)


pytestmark = pytest.mark.skipif(
    shutil.which("flock") is None, reason="flock(1) ausente (util-linux)"
)


class TestOGanchoDeParadaNaoEspera:
    def test_no_gancho_de_parada_desiste_na_hora(
        self, tmp_path: Path, lock_ocupado: Path
    ) -> None:
        """E4 — com `$SERVICE_RESULT` na mão, o snapshot não disputa o lock."""
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        diario = tmp_path / "diario.log"
        inicio = time.monotonic()
        try:
            proc = subprocess.run(
                ["bash", str(SNAPSHOT), "--quiet"],
                capture_output=True,
                text=True,
                timeout=TETO_S,
                env=_ambiente(fonte, lock_ocupado, diario, "core-dump"),
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                f"o gancho de parada ficou >{TETO_S:.0f}s disputando o `.lock`. "
                "Enquanto ele espera, o systemd NÃO reinicia o bluetoothd — foram "
                "42,8 s dos 57,25 s medidos em 06/08. No gancho o `flock` tem de "
                "ser `-n`."
            )
        decorrido = time.monotonic() - inicio
        assert proc.returncode == 0, proc.stderr
        assert decorrido < TETO_S, f"desistir levou {decorrido:.1f}s"
        assert "desisto na hora" in diario.read_text(encoding="utf-8"), (
            "o script saiu rápido, mas não pela porta do gancho de parada — "
            "confira se ele chegou mesmo ao `flock`"
        )
        assert not list(lock_ocupado.glob("2*")), (
            "desistir do lock não pode deixar diretório de snapshot pela metade"
        )

    def test_fora_do_gancho_espera_a_vez(self, tmp_path: Path, lock_ocupado: Path) -> None:
        """E4-bis — sem `$SERVICE_RESULT`, o `-w 30` do SNAPSHOT-LOCK-01 fica."""
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        diario = tmp_path / "diario.log"
        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run(
                ["bash", str(SNAPSHOT), "--quiet"],
                capture_output=True,
                text=True,
                timeout=PACIENCIA_S,
                env=_ambiente(fonte, lock_ocupado, diario, None),
            )

    def test_com_o_lock_livre_o_gancho_fotografa(self, tmp_path: Path) -> None:
        """Linha de base: o `-n` não pode ter virado "no gancho, nunca fotografa"."""
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        acervo = tmp_path / "bt-bonds"
        diario = tmp_path / "diario.log"
        proc = subprocess.run(
            ["bash", str(SNAPSHOT), "--quiet"],
            capture_output=True,
            text=True,
            timeout=TETO_S,
            env=_ambiente(fonte, acervo, diario, "core-dump"),
        )
        assert proc.returncode == 0, proc.stderr
        gravados = [d for d in acervo.glob("2*") if d.is_dir()]
        assert gravados, "com o lock livre o gancho tem de fotografar"
        assert (gravados[0] / ADAPTER / CONTROLE / "info").is_file()


class TestTetoDeParada:
    def test_dropin_poe_teto_no_tempo_de_parada(self) -> None:
        """E5 — sem `TimeoutStopSec` vale o padrão de 90 s."""
        texto = DROPIN.read_text(encoding="utf-8")
        achado = re.search(r"^TimeoutStopSec=(\S+)$", texto, re.M)
        assert achado, (
            "o drop-in não declara `TimeoutStopSec`. Sem ele vale o "
            "`DefaultTimeoutStopSec` de 90 s — foi por essa porta que os 42,8 s "
            "de ExecStopPost de 06/08 passaram sem que nada os limitasse."
        )
        assert _segundos(achado.group(1)) <= 30, (
            f"`TimeoutStopSec={achado.group(1)}` não é teto: o pior caso já "
            "medido foi de 42,8 s dentro do gancho."
        )
        assert _segundos(achado.group(1)) >= 5, (
            f"`TimeoutStopSec={achado.group(1)}` é apertado demais. A restauração "
            "de bonds também roda no gancho, e um SIGKILL no meio dela deixa o "
            "storage do BlueZ pela metade — o dano que o salva-vidas existe para "
            "evitar."
        )

    def test_o_teto_nao_e_mais_frouxo_que_o_do_agente(self) -> None:
        """O gancho do BlueZ não pode esperar mais que o agente que ele arrasta."""
        agente = (REPO_ROOT / "assets" / "systemd" / "hefesto-bt-agent.service").read_text(
            encoding="utf-8"
        )
        do_agente = re.search(r"^TimeoutStopSec=(\S+)$", agente, re.M)
        assert do_agente, "o `hefesto-bt-agent.service` perdeu o `TimeoutStopSec`"
        do_dropin = re.search(
            r"^TimeoutStopSec=(\S+)$", DROPIN.read_text(encoding="utf-8"), re.M
        )
        assert do_dropin
        assert _segundos(do_dropin.group(1)) < 90, (
            "o drop-in voltou ao padrão de 90 s do systemd, que é exatamente o "
            "número que esta sprint existe para tirar do caminho"
        )


def _segundos(valor: str) -> float:
    """`15s`, `1min 30s`, `250ms`, `15` -> segundos."""
    unidades = {"us": 1e-6, "ms": 1e-3, "s": 1.0, "sec": 1.0, "min": 60.0, "m": 60.0, "h": 3600.0}
    total = 0.0
    for numero, unidade in re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]*)", valor):
        total += float(numero) * unidades.get(unidade, 1.0)
    return total
