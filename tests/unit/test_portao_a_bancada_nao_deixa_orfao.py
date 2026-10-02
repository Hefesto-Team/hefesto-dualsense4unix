"""O PORTÃO DO SEMÁFORO DA BANCADA — e a cicatriz que ele nasce carregando."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "scripts" / "bancada.sh"

_UMA_HORA = 3600


def _roda(*argv: str, arq: Path, agora: int | None = None, pid: int | None = None):
    env = dict(os.environ)
    env["HEFESTO_BANCADA_ARQ"] = str(arq)
    if agora is not None:
        env["HEFESTO_BANCADA_AGORA"] = str(agora)
    if pid is not None:
        env["HEFESTO_BANCADA_PID"] = str(pid)
    return subprocess.run(
        ["bash", str(BANCADA), *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=RAIZ,
    )


@pytest.fixture
def arq(tmp_path: Path) -> Path:
    """O estado vive em tmp, nunca no XDG_RUNTIME_DIR de verdade."""
    return tmp_path / "hefesto-bancada.json"


@pytest.fixture
def detentor():
    """Um processo de verdade para segurar a bancada, e para matar depois."""
    proc = subprocess.Popen(["sleep", "300"])
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def _pid_morreu(pid: int, teto_s: float = 5.0) -> bool:
    """Espera o PID sumir DE VERDADE. É a correção das duas medições falsas."""
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return True
        time.sleep(0.02)
    return False


def test_reservada_o_exigir_recusa_com_motivo_e_hora(arq: Path, detentor) -> None:
    agora = int(time.time())
    r = _roda(
        "reservar", "medição de BT", "--horas", "4",
        arq=arq, agora=agora, pid=detentor.pid,
    )
    assert r.returncode == 0, r.stderr

    r = _roda("exigir", arq=arq, agora=agora + 60, pid=detentor.pid)
    assert r.returncode == 1, "bancada reservada e `exigir` deixou passar:\n" + r.stdout + r.stderr
    tudo = r.stdout + r.stderr
    assert "medição de BT" in tudo, "a recusa não diz o MOTIVO:\n" + tudo
    assert "até" in tudo, "a recusa não diz até QUANDO:\n" + tudo
    assert str(detentor.pid) in tudo, "a recusa não diz QUEM segura (PID):\n" + tudo


def test_detentor_morto_a_bancada_volta_a_ficar_livre(arq: Path, detentor) -> None:
    agora = int(time.time())
    _roda("reservar", "medição de BT", "--horas", "4", arq=arq, agora=agora, pid=detentor.pid)

    os.kill(detentor.pid, 0)
    assert _roda("exigir", arq=arq, agora=agora + 60, pid=detentor.pid).returncode == 1

    os.kill(detentor.pid, signal.SIGKILL)
    detentor.wait()
    assert _pid_morreu(detentor.pid), (
        f"o dublê PID {detentor.pid} não sumiu depois do kill -9 — a falha é do DUBLÊ, "
        "não do semáforo. Foi assim que as duas primeiras medições do flock mentiram."
    )

    assert arq.exists()
    r = _roda("status", arq=arq, agora=agora + 60)
    assert "LIVRE" in r.stdout, (
        "o detentor morreu e a bancada continua travada — é o trinco que o "
        "desenho manda NÃO construir:\n" + r.stdout + r.stderr
    )
    assert _roda("exigir", arq=arq, agora=agora + 60).returncode == 0


def test_o_teto_vence_mesmo_com_o_detentor_vivo(arq: Path, detentor) -> None:
    agora = int(time.time())
    _roda("reservar", "medição de BT", "--horas", "4", arq=arq, agora=agora, pid=detentor.pid)

    assert _roda("exigir", arq=arq, agora=agora + 3 * _UMA_HORA).returncode == 1

    os.kill(detentor.pid, 0)
    depois = agora + 5 * _UMA_HORA
    r = _roda("status", arq=arq, agora=depois)
    assert "LIVRE" in r.stdout, (
        "o teto de tempo venceu e a bancada continua travada — é o `btmgmt` sem "
        "adaptador de novo:\n" + r.stdout + r.stderr
    )
    assert _roda("exigir", arq=arq, agora=depois).returncode == 0
    os.kill(detentor.pid, 0)


def test_sem_arquivo_nenhum_a_bancada_e_livre(arq: Path) -> None:
    r = _roda("status", arq=arq)
    assert "LIVRE" in r.stdout
    assert _roda("exigir", arq=arq).returncode == 0


def test_arquivo_ilegivel_e_tratado_como_livre_e_o_diz(arq: Path) -> None:
    """Estado corrompido não pode travar a bancada em silêncio nem para sempre."""
    arq.write_text("{ isto não é o formato }", encoding="utf-8")
    r = _roda("status", arq=arq)
    assert "LIVRE" in r.stdout
    assert "ilegível" in r.stdout, "trata como livre mas não DIZ por quê:\n" + r.stdout


def test_reservar_sobre_reserva_viva_e_recusado(arq: Path, detentor) -> None:
    agora = int(time.time())
    _roda("reservar", "medição de BT", "--horas", "4", arq=arq, agora=agora, pid=detentor.pid)
    r = _roda("reservar", "outra coisa", "--horas", "1", arq=arq, agora=agora + 60)
    assert r.returncode == 1, "a segunda reserva passou por cima da primeira"
    assert "medição de BT" in r.stderr, "a recusa não diz quem já está lá:\n" + r.stderr
    assert "medição de BT" in arq.read_text(encoding="utf-8"), "a reserva viva foi sobrescrita"


def test_o_estado_nao_mora_dentro_da_arvore_versionada() -> None:
    """Estado transitório em git vira commit de carona -- 16 de 22 em 23/08."""
    texto = BANCADA.read_text(encoding="utf-8")
    assert "XDG_RUNTIME_DIR" in texto
    versionados = subprocess.run(
        ["git", "ls-files", "hefesto-bancada.json"],
        capture_output=True, text=True, cwd=RAIZ, check=True,
    ).stdout.strip()
    assert versionados == "", "o estado da bancada foi versionado: " + versionados
