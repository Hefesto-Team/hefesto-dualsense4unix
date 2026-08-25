"""O PORTÃO DO SEMÁFORO DA BANCADA — e a cicatriz que ele nasce carregando.

A CICATRIZ, ANTES DE TUDO. Em 24/08/2026 a prova de que o ``flock`` não deixa
órfão devolveu **"AINDA OCUPADO" duas vezes** -- um falso negativo convincente,
que teria matado a peça no papel. A causa não era o mecanismo: era o dublê. Na
primeira tentativa o dublê **forqueava** e matar o pai deixava o filho segurando
o descritor; na segunda, meio segundo de espera não bastou. **Só quando o dublê
passou a declarar o próprio PID** e a prova passou a conferir o detentor de
verdade é que a medição virou verdade.

Por isso este portão faz três coisas que parecem exagero e não são:
  - o dublê é um processo REAL (``sleep``), e o teste declara o PID dele via
    ``HEFESTO_BANCADA_PID`` em vez de deixar o script adivinhar;
  - depois de ``kill -9`` o teste ESPERA o PID sumir de verdade antes de
    perguntar qualquer coisa ao semáforo -- e falha dizendo isso se ele não
    sumir, em vez de acusar o semáforo;
  - o relógio é INJETADO (``HEFESTO_BANCADA_AGORA``), porque um teste que espera
    quatro horas não roda, e um teto de um segundo não prova o teto de quatro
    horas.

O QUE ELE COBRA: **duas provas de vida INDEPENDENTES.**
  1. o PID do detentor está vivo?  -- quem responde é o KERNEL;
  2. já passou de ``expira_em``?    -- quem responde é o RELÓGIO.
Basta uma dizer "não" para a bancada estar livre. Só o PID deixaria a bancada
travada por um processo zumbi; só o relógio deixaria a bancada travada as
quatro horas seguintes à morte da sessão dela.

A MORDIDA, e ela é a mais exigente desta peça: arranque UMA prova de vida de
``bancada.sh`` de cada vez. **Cada arranque tem de reprovar UM caso só.** Se
arrancar uma reprovar as duas, as provas não são independentes e a peça está
errada -- é o teste do desenho, não do código.

E o teto não é zelo: é a lição do ``btmgmt`` sem adaptador, que travava o
``install.sh`` PARA SEMPRE em quem não tem Bluetooth. O que não volta sozinho
trava a casa.
"""

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
    """O estado vive em tmp, nunca no XDG_RUNTIME_DIR de verdade.

    Se o teste escrevesse no arquivo real, ele apagaria a reserva DELA no meio
    de uma medição de Bluetooth -- que é exatamente o defeito que esta peça
    existe para impedir.
    """
    return tmp_path / "hefesto-bancada.json"


@pytest.fixture
def detentor():
    """Um processo de verdade para segurar a bancada, e para matar depois.

    Um PID inventado não serve: `kill -0` sobre número aleatório pode acertar um
    processo vivo de outra pessoa, e aí o teste passa por acaso.
    """
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


# ---------------------------------------------------------------------------
# CASO 1 — reservada: `exigir` recusa com motivo e hora
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CASO 2 — o detentor morre: quem solta é o KERNEL, e ninguém libera nada
# ---------------------------------------------------------------------------


def test_detentor_morto_a_bancada_volta_a_ficar_livre(arq: Path, detentor) -> None:
    agora = int(time.time())
    _roda("reservar", "medição de BT", "--horas", "4", arq=arq, agora=agora, pid=detentor.pid)

    # antes: ocupada, e o detentor está mesmo vivo
    os.kill(detentor.pid, 0)
    assert _roda("exigir", arq=arq, agora=agora + 60, pid=detentor.pid).returncode == 1

    os.kill(detentor.pid, signal.SIGKILL)
    detentor.wait()
    assert _pid_morreu(detentor.pid), (
        f"o dublê PID {detentor.pid} não sumiu depois do kill -9 — a falha é do DUBLÊ, "
        "não do semáforo. Foi assim que as duas primeiras medições do flock mentiram."
    )

    # O arquivo continua lá, intocado. Ninguém liberou nada: quem respondeu foi
    # o kernel, e é isso que separa este desenho de um lock file.
    assert arq.exists()
    r = _roda("status", arq=arq, agora=agora + 60)
    assert "LIVRE" in r.stdout, (
        "o detentor morreu e a bancada continua travada — é o trinco que o "
        "desenho manda NÃO construir:\n" + r.stdout + r.stderr
    )
    assert _roda("exigir", arq=arq, agora=agora + 60).returncode == 0


# ---------------------------------------------------------------------------
# CASO 3 — o teto vence com o PID AINDA VIVO: quem solta é o RELÓGIO
# ---------------------------------------------------------------------------


def test_o_teto_vence_mesmo_com_o_detentor_vivo(arq: Path, detentor) -> None:
    agora = int(time.time())
    _roda("reservar", "medição de BT", "--horas", "4", arq=arq, agora=agora, pid=detentor.pid)

    # ainda dentro do teto: ocupada
    assert _roda("exigir", arq=arq, agora=agora + 3 * _UMA_HORA).returncode == 1

    # relógio adiantado além de `expira_em`, e o detentor CONTINUA VIVO --
    # é o processo zumbi, e é a razão de a segunda prova de vida existir.
    os.kill(detentor.pid, 0)
    depois = agora + 5 * _UMA_HORA
    r = _roda("status", arq=arq, agora=depois)
    assert "LIVRE" in r.stdout, (
        "o teto de tempo venceu e a bancada continua travada — é o `btmgmt` sem "
        "adaptador de novo:\n" + r.stdout + r.stderr
    )
    assert _roda("exigir", arq=arq, agora=depois).returncode == 0
    os.kill(detentor.pid, 0)  # e o dublê seguiu vivo o tempo todo


# ---------------------------------------------------------------------------
# As bordas que já morderam em outros portões desta casa
# ---------------------------------------------------------------------------


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
