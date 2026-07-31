# ruff: noqa: E501
"""Testes de single_instance (BUG-MULTI-INSTANCE-01 e BUG-TRAY-SINGLE-FLASH-01).

Cobre:
  - `acquire_or_takeover` cria pid file e adquire flock.
  - `is_alive` reporta ESRCH como morto.
  - Takeover envia SIGTERM ao predecessor (um processo de verdade) e vence o
    lock.
  - Pid órfão (processo já morto) é sobrescrito sem SIGTERM.
  - `acquire_or_bring_to_front` chama callback com PID do predecessor, não envia
    SIGTERM e retorna None quando predecessor permanece vivo.
  - `_is_hefesto_dualsense4unix_process` distingue daemon/GUI legítimos de PIDs reciclados
    (AUDIT-FINDING-SINGLE-INSTANCE-PID-RECYCLE-01).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import single_instance

# O predecessor destes testes nasce por `subprocess`, e não por `os.fork()`: o
# pytest roda com threads, e o CPython avisa que `fork()` depois de criar thread
# pode deixar o filho em deadlock. O que os testes precisam do predecessor é PID
# real, pid file real e morte por sinal — um interpretador novo entrega os três.
_FILHO_QUE_SEGURA_O_LOCK = (
    "import sys, time\n"
    "from hefesto_dualsense4unix.utils import single_instance\n"
    "single_instance.acquire_or_takeover(sys.argv[1])\n"
    "time.sleep(30)\n"
)

_FILHO_OCIOSO = "import time\ntime.sleep(30)\n"

# Generoso de propósito: o filho é um interpretador novo e importa o pacote
# inteiro antes de escrever o pid file.
ESPERA_MAXIMA_PELO_LOCK_SEC = 20.0


def _encerrar(filho: subprocess.Popen[bytes]) -> None:
    """Mata e enterra: PID não reapado vira zumbi, e zumbi responde a `kill(pid, 0)`."""
    if filho.poll() is None:
        filho.kill()
    filho.wait(timeout=5)


def _subir_filho_ocioso() -> subprocess.Popen[bytes]:
    """Processo vivo qualquer, só para ocupar um PID real."""
    return subprocess.Popen([sys.executable, "-c", _FILHO_OCIOSO])


def _subir_filho_com_lock(nome: str, pid_file: Path) -> subprocess.Popen[bytes]:
    """Sobe um processo real que adquire o lock `nome` e fica vivo até morrer.

    Só devolve depois que o pid file traz o PID do filho — o pid file É o
    sinal de prontidão, e sem ele o pai faria takeover de ninguém.
    """
    filho = subprocess.Popen([sys.executable, "-c", _FILHO_QUE_SEGURA_O_LOCK, nome])
    limite = time.monotonic() + ESPERA_MAXIMA_PELO_LOCK_SEC
    while time.monotonic() < limite:
        if filho.poll() is not None:
            pytest.fail(f"filho saiu antes de adquirir o lock ({filho.returncode})")
        if pid_file.exists() and pid_file.read_text().strip() == str(filho.pid):
            return filho
        time.sleep(0.05)
    _encerrar(filho)
    pytest.fail("filho não escreveu pid file")


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona $XDG_RUNTIME_DIR para tmp_path; isola pid files."""
    target = tmp_path / "runtime"
    target.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(target))
    # platformdirs cacheia o valor em módulo — reimporta para pegar novo env.
    import importlib

    from hefesto_dualsense4unix.utils import xdg_paths as xdg
    importlib.reload(xdg)
    importlib.reload(single_instance)
    return target


def test_acquire_retorna_pid_atual(isolated_runtime: Path) -> None:
    pid = single_instance.acquire_or_takeover("daemon")
    assert pid == os.getpid()
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "daemon.pid"
    assert pid_file.exists()
    assert pid_file.read_text().strip() == str(pid)
    single_instance.release("daemon")


def test_is_alive_processo_morto(isolated_runtime: Path) -> None:
    assert not single_instance.is_alive(999_999_999)


def test_is_alive_processo_proprio(isolated_runtime: Path) -> None:
    assert single_instance.is_alive(os.getpid())


def test_pid_orfao_sem_sigterm(isolated_runtime: Path) -> None:
    """Pid file com PID morto é sobrescrito sem tentar matar."""
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "daemon.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("999999999\n")
    pid = single_instance.acquire_or_takeover("daemon")
    assert pid == os.getpid()
    assert pid_file.read_text().strip() == str(pid)
    single_instance.release("daemon")


def test_takeover_mata_predecessor(
    isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filho adquire lock, pai faz takeover; filho recebe SIGTERM e sai."""
    # O dublê mantém o teste no fluxo de takeover; a heurística de detecção tem
    # portão próprio nos `test_is_hefesto_dualsense4unix_process_*`.
    monkeypatch.setattr(
        single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: True
    )

    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "gui.pid"
    filho = _subir_filho_com_lock("gui", pid_file)
    try:
        own = single_instance.acquire_or_takeover("gui")
        assert own == os.getpid()
        assert pid_file.read_text().strip() == str(own)

        # O filho dorme 30s: sair em menos que isso, e por sinal, só acontece
        # se o takeover o tiver derrubado.
        codigo = filho.wait(timeout=10)
        assert codigo in (-signal.SIGTERM, -signal.SIGKILL), (
            f"filho não saiu por sinal do takeover: código {codigo}"
        )
        assert not single_instance.is_alive(filho.pid)
    finally:
        _encerrar(filho)
        single_instance.release("gui")


def test_release_sem_acquire_e_noop(isolated_runtime: Path) -> None:
    # Não deve levantar.
    single_instance.release("nao_adquirido")


def test_bring_to_front_chama_callback(
    isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filho adquire lock; pai detecta predecessor vivo, chama callback e retorna None.

    Verifica:
      - O callback é invocado com o PID correto do filho (predecessor).
      - O filho NÃO recebe SIGTERM (permanece vivo após acquire_or_bring_to_front).
      - O retorno do pai é None (indica que o predecessor foi preservado).
    """
    # Mesmo dublê do test_takeover_mata_predecessor: o alvo aqui é o fluxo de
    # bring-to-front, não a heurística de detecção.
    monkeypatch.setattr(
        single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: True
    )

    pid_file = (
        Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "gui-btf.pid"
    )
    filho = _subir_filho_com_lock("gui-btf", pid_file)
    try:
        callback_pids: list[int] = []

        def _callback(pid: int) -> None:
            callback_pids.append(pid)
            # Não faz nada além de registrar — simula xdotool ausente.

        result = single_instance.acquire_or_bring_to_front(
            "gui-btf",
            bring_to_front_cb=_callback,
            fallback_takeover_after_sec=0.5,  # prazo curto para o teste ser rápido
        )

        # O filho deve ainda estar vivo (não recebeu SIGTERM).
        assert single_instance.is_alive(filho.pid), (
            "predecessor morreu — bring-to-front errou"
        )

        # Callback deve ter sido chamado com o PID do filho.
        assert callback_pids == [filho.pid], (
            f"callback não chamado corretamente: {callback_pids}"
        )

        # Retorno deve ser None — indica que o predecessor foi preservado.
        assert result is None, f"esperado None, obtido {result}"
    finally:
        _encerrar(filho)
        single_instance.release("gui-btf")


# -----------------------------------------------------------------------------
# AUDIT-FINDING-SINGLE-INSTANCE-PID-RECYCLE-01
# Defesa em profundidade contra reciclagem de PID.
# -----------------------------------------------------------------------------


def test_is_hefesto_dualsense4unix_process_comm_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_read_proc_comm` com \'hefesto-dualsense4unix\\n\' faz `_is_hefesto_dualsense4unix_process` retornar True."""
    def fake_read_comm(pid: int) -> str | None:
        return "hefesto-dualsense4unix"

    def fake_read_cmdline(pid: int) -> str | None:
        return None

    monkeypatch.setattr(single_instance, "_read_proc_comm", fake_read_comm)
    monkeypatch.setattr(single_instance, "_read_proc_cmdline", fake_read_cmdline)

    assert single_instance._is_hefesto_dualsense4unix_process(12345) is True


def test_is_hefesto_dualsense4unix_process_cmdline_gui_python3_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUI roda como `python3 -m hefesto_dualsense4unix.app.main` — comm=python3, cmdline tem hefesto."""
    monkeypatch.setattr(single_instance, "_read_proc_comm", lambda pid: "python3")
    monkeypatch.setattr(
        single_instance,
        "_read_proc_cmdline",
        lambda pid: "/usr/bin/python3 -m hefesto_dualsense4unix.app.main",
    )
    assert single_instance._is_hefesto_dualsense4unix_process(12345) is True


def test_is_hefesto_dualsense4unix_process_alheio_firefox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PID reciclado para firefox — comm e cmdline sem marcador 'hefesto-dualsense4unix'."""
    monkeypatch.setattr(single_instance, "_read_proc_comm", lambda pid: "firefox")
    monkeypatch.setattr(
        single_instance,
        "_read_proc_cmdline",
        lambda pid: "/usr/lib/firefox/firefox --profile=default",
    )
    assert single_instance._is_hefesto_dualsense4unix_process(12345) is False


def test_is_hefesto_dualsense4unix_process_noent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PID inválido — `/proc/<pid>/*` inexistente, retorna False (conservador)."""
    monkeypatch.setattr(single_instance, "_read_proc_comm", lambda pid: None)
    monkeypatch.setattr(single_instance, "_read_proc_cmdline", lambda pid: None)
    assert single_instance._is_hefesto_dualsense4unix_process(999_999_999) is False


def test_is_hefesto_dualsense4unix_process_pid_zero_ou_negativo() -> None:
    """PIDs inválidos na entrada retornam False sem ler /proc."""
    assert single_instance._is_hefesto_dualsense4unix_process(0) is False
    assert single_instance._is_hefesto_dualsense4unix_process(-1) is False


def test_read_proc_comm_pid_invalido_retorna_none() -> None:
    """PID gigantesco inexistente — leitura real de /proc retorna None."""
    assert single_instance._read_proc_comm(999_999_999) is None


def test_read_proc_cmdline_pid_invalido_retorna_none() -> None:
    """PID gigantesco inexistente — leitura real de /proc/cmdline retorna None."""
    assert single_instance._read_proc_cmdline(999_999_999) is None


def test_read_proc_comm_do_proprio_processo() -> None:
    """PID do próprio processo deve retornar comm não-vazio."""
    comm = single_instance._read_proc_comm(os.getpid())
    assert comm is not None
    assert len(comm) > 0


def test_takeover_ignora_pid_reciclado(
    isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pid file aponta para PID vivo NÃO-hefesto-dualsense4unix — `_terminate_predecessor` não envia SIGTERM."""
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "daemon.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # O predecessor tem de ser outro processo VIVO: com o PID do próprio pytest o
    # fluxo pula na guarda `predecessor != os.getpid()` e o teste não mediria nada.
    filho = _subir_filho_ocioso()
    orig_kill = os.kill
    try:
        pid_file.write_text(f"{filho.pid}\n")

        # Mock: o filho NÃO é hefesto-dualsense4unix (simula reciclagem).
        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: False)

        # Spy em os.kill SOMENTE para capturar sinais letais; `os.kill(pid, 0)`
        # é a sonda do `is_alive` e tem de continuar chegando ao kernel.
        kills_real: list[tuple[int, int]] = []

        def spy(pid: int, sig: int) -> None:
            if sig in (signal.SIGTERM, signal.SIGKILL):
                kills_real.append((pid, sig))
                return
            orig_kill(pid, sig)

        monkeypatch.setattr(os, "kill", spy)

        own = single_instance.acquire_or_takeover("daemon")
        assert own == os.getpid()

        # Nenhum SIGTERM/SIGKILL deve ter sido enviado ao filho.
        assert not any(pid == filho.pid for pid, _ in kills_real), \
            f"SIGTERM enviado a PID reciclado: {kills_real}"

        # Pid file sobrescrito com PID atual.
        assert pid_file.read_text().strip() == str(own)
    finally:
        monkeypatch.setattr(os, "kill", orig_kill)
        _encerrar(filho)
        single_instance.release("daemon")


def test_takeover_mata_predecessor_hefesto(
    isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pid file aponta para PID vivo hefesto-dualsense4unix — SIGTERM enviado normalmente."""
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "gui-hef.pid"
    filho = _subir_filho_com_lock("gui-hef", pid_file)
    try:
        # Força `_is_hefesto_dualsense4unix_process` a reportar True (simula predecessor legítimo).
        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: True)

        own = single_instance.acquire_or_takeover("gui-hef")
        assert own == os.getpid()

        codigo = filho.wait(timeout=10)
        assert codigo in (-signal.SIGTERM, -signal.SIGKILL), (
            f"predecessor legítimo tinha de sair por sinal: código {codigo}"
        )
        assert not single_instance.is_alive(filho.pid)
    finally:
        _encerrar(filho)
        single_instance.release("gui-hef")


def test_terminate_predecessor_pid_reciclado_nao_sinaliza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_terminate_predecessor` com PID vivo não-hefesto-dualsense4unix: early-return sem SIGTERM/SIGKILL."""
    # PID existe (probe) mas não é hefesto-dualsense4unix.
    monkeypatch.setattr(single_instance, "is_alive", lambda pid: True)
    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: False)
    monkeypatch.setattr(single_instance, "_read_proc_comm", lambda pid: "firefox")

    sinais: list[tuple[int, int]] = []

    def spy_kill(pid: int, sig: int) -> None:
        sinais.append((pid, sig))

    monkeypatch.setattr(os, "kill", spy_kill)

    single_instance._terminate_predecessor(12345)

    # Nenhum kill foi chamado (nem SIGTERM, nem probe — usamos mock de is_alive).
    assert sinais == [], f"_terminate_predecessor sinalizou PID reciclado: {sinais}"


def test_terminate_predecessor_pid_morto_early_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_terminate_predecessor` com PID morto: early-return sem chamar `_is_hefesto_dualsense4unix_process`."""
    monkeypatch.setattr(single_instance, "is_alive", lambda pid: False)

    chamadas_isproc: list[int] = []

    def _tracker(pid: int) -> bool:
        chamadas_isproc.append(pid)
        return False

    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", _tracker)

    single_instance._terminate_predecessor(12345)

    assert chamadas_isproc == [], "is_alive(False) deve evitar call a _is_hefesto_dualsense4unix_process"


def test_read_existing_pid_oserror_retorna_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_read_existing_pid` tratamento de OSError não-FileNotFound (ex: ENOTDIR)."""
    # Path que aponta pra algo não-legível: cria arquivo sem permissão.
    pid_file = tmp_path / "bloqueado.pid"
    pid_file.write_text("1234\n")
    pid_file.chmod(0o000)
    try:
        result = single_instance._read_existing_pid(pid_file)
        # Em usuário root a leitura pode passar (retorna 1234); em user comum retorna None.
        assert result in (None, 1234)
    finally:
        pid_file.chmod(0o644)


def test_read_existing_pid_nao_numerico_retorna_none(tmp_path: Path) -> None:
    """Pid file com conteúdo não-numérico retorna None (sem crash)."""
    pid_file = tmp_path / "bad.pid"
    pid_file.write_text("not-a-pid\n")
    assert single_instance._read_existing_pid(pid_file) is None


def test_read_existing_pid_zero_retorna_none(tmp_path: Path) -> None:
    """Pid file com 0 retorna None (PID inválido)."""
    pid_file = tmp_path / "zero.pid"
    pid_file.write_text("0\n")
    assert single_instance._read_existing_pid(pid_file) is None


def test_bring_to_front_ignora_pid_reciclado(
    isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pid file aponta para PID vivo NÃO-hefesto-dualsense4unix — callback NÃO é chamado, novo lock adquirido."""
    filho = _subir_filho_ocioso()

    try:
        pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "gui-rec.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(f"{filho.pid}\n")

        # Simula reciclagem.
        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: False)

        callback_pids: list[int] = []

        def _cb(pid: int) -> None:
            callback_pids.append(pid)

        result = single_instance.acquire_or_bring_to_front(
            "gui-rec",
            bring_to_front_cb=_cb,
            fallback_takeover_after_sec=0.5,
        )

        # Callback NÃO deve ter sido invocado (predecessor não é hefesto-dualsense4unix).
        assert callback_pids == [], f"callback invocado para PID reciclado: {callback_pids}"

        # Resultado: adquire lock normalmente (getpid).
        assert result == os.getpid()

        # Pid file sobrescrito.
        assert pid_file.read_text().strip() == str(os.getpid())
    finally:
        _encerrar(filho)
        single_instance.release("gui-rec")
