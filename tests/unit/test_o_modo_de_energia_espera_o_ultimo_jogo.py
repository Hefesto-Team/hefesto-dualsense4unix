"""O modo de energia espera o último jogo, e o Heroic aberto é o desta conta.

O-MODO-DE-ENERGIA-ESPERA-O-ULTIMO-JOGO-E-O-HEROIC-E-O-DESTA-CONTA-01 (22/11/2026). O lançador é o
`assets/hefesto-launch.sh` de verdade, rodado com o perfil, a placa, o `sudo` e o `systemd-run` de
mentira do ensaio do restaurador (o gerente de usuário de mentira roda cada restaurador fora da
árvore do jogo). O `/proc` do Heroic é uma pasta de mentira com `cmdline`, `status` e `environ`.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o lançador que não se
inscreve ao achar o desempenho posto por outro reprova o caso do segundo jogo; o restaurador que
devolve sem olhar a trava reprova o caso do primeiro que sai e o do que sai por último; a trava
sem o carimbo de início do processo reprova o caso do número reaproveitado; o `heroic_aberto` sem
o filtro do dono reprova o caso do outro usuário e o do outro lar.
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from tests.unit import test_o_restaurador_do_lancamento_solta_quando_o_jogo_acaba as _base

LANCADOR = _base.LANCADOR
PERIODO = _base.PERIODO
Ensaio = _base.Ensaio
ensaio = _base.ensaio


def _jogo(b: Ensaio, segundos: float) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["sh", str(LANCADOR), "sleep", str(segundos)],
        env=b.ambiente(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True)


def _fechar(*jogos: subprocess.Popen[bytes]) -> None:
    for jogo in jogos:
        if jogo.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(jogo.pid, signal.SIGKILL)
        jogo.wait()


def _pasta_das_travas(b: Ensaio) -> Path:
    return Path(b.ambiente()["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / "modo-de-energia"


def _esperar_a_trava(b: Ensaio, jogo: subprocess.Popen[bytes], prazo: float = 10.0) -> Path:
    trava = _pasta_das_travas(b) / str(jogo.pid)
    fim = time.monotonic() + prazo
    while time.monotonic() < fim and not trava.exists():
        time.sleep(0.05)
    assert trava.exists(), "o lançamento não se inscreveu"
    return trava


def test_o_primeiro_que_sai_nao_devolve_o_perfil_com_o_segundo_aberto(ensaio: Ensaio) -> None:
    primeiro = _jogo(ensaio, 2)
    try:
        ensaio.esperar("perfil performance")
        segundo = _jogo(ensaio, 7)
        try:
            _esperar_a_trava(ensaio, segundo)
            primeiro.wait(timeout=10)
            time.sleep(5 * PERIODO)

            assert segundo.poll() is None
            assert ensaio.perfil.read_text(encoding="utf-8").strip() == "performance"
            assert "perfil balanced" not in ensaio.chamadas(), ensaio.chamadas()

            segundo.wait(timeout=15)
            chamadas = ensaio.esperar("perfil balanced")
            assert ensaio.perfil.read_text(encoding="utf-8").strip() == "balanced"
            assert chamadas.count("perfil performance") == 1, chamadas
            assert chamadas.count("perfil balanced") == 1, chamadas
        finally:
            _fechar(segundo)
    finally:
        _fechar(primeiro)


def test_o_segundo_que_sai_antes_nao_devolve_e_o_primeiro_devolve_no_fim(ensaio: Ensaio) -> None:
    primeiro = _jogo(ensaio, 7)
    try:
        ensaio.esperar("perfil performance")
        segundo = _jogo(ensaio, 2)
        try:
            _esperar_a_trava(ensaio, segundo)
            segundo.wait(timeout=10)
            time.sleep(5 * PERIODO)

            assert primeiro.poll() is None
            assert ensaio.perfil.read_text(encoding="utf-8").strip() == "performance"
            assert "perfil balanced" not in ensaio.chamadas(), ensaio.chamadas()

            primeiro.wait(timeout=15)
            chamadas = ensaio.esperar("perfil balanced")
            assert chamadas.count("perfil balanced") == 1, chamadas
        finally:
            _fechar(segundo)
    finally:
        _fechar(primeiro)


def test_o_desempenho_que_o_usuario_pos_sozinho_nao_e_tocado(ensaio: Ensaio) -> None:
    ensaio.perfil.write_text("performance\n", encoding="utf-8")
    jogo = _jogo(ensaio, 1)
    try:
        jogo.wait(timeout=10)
        time.sleep(4 * PERIODO)
    finally:
        _fechar(jogo)

    assert "perfil performance" not in ensaio.chamadas()
    assert "perfil balanced" not in ensaio.chamadas()
    assert ensaio.perfil.read_text(encoding="utf-8").strip() == "performance"


def test_a_trava_de_um_numero_reaproveitado_nao_segura_a_devolucao(ensaio: Ensaio) -> None:
    pasta = _pasta_das_travas(ensaio)
    pasta.mkdir(parents=True)
    dono = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        (pasta / str(dono.pid)).write_text("1\n", encoding="utf-8")

        jogo = _jogo(ensaio, 1)
        try:
            _esperar_a_trava(ensaio, jogo)
            jogo.wait(timeout=10)
            chamadas = ensaio.esperar("perfil balanced")
        finally:
            _fechar(jogo)

        assert "perfil balanced" in chamadas, chamadas
    finally:
        dono.kill()
        dono.wait()


def _proc_de_mentira(base: Path, processos: dict[int, tuple[str, int, str]]) -> Path:
    proc = base / "proc"
    for pid, (argv0, uid, lar) in processos.items():
        pasta = proc / str(pid)
        pasta.mkdir(parents=True)
        (pasta / "cmdline").write_bytes(argv0.encode() + b"\0--no-sandbox\0")
        (pasta / "status").write_text(f"Name:\tx\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
                                      encoding="utf-8")
        (pasta / "environ").write_bytes(f"HOME={lar}\0LANG=C\0".encode())
    return proc


@pytest.fixture()
def lar_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "lar"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    return casa


def test_o_heroic_de_outro_usuario_nao_conta_como_aberto(
        tmp_path: Path, lar_de_mentira: Path) -> None:
    proc = _proc_de_mentira(tmp_path, {
        4101: ("/opt/Heroic/heroic", os.getuid() + 1, "/home/outra-pessoa")})

    assert censo.heroic_aberto(proc) is False


def test_o_heroic_de_outro_lar_do_mesmo_usuario_nao_conta_como_aberto(
        tmp_path: Path, lar_de_mentira: Path) -> None:
    proc = _proc_de_mentira(tmp_path, {
        4102: ("/opt/Heroic/heroic", os.getuid(), str(tmp_path / "outro-lar"))})

    assert censo.heroic_aberto(proc) is False


def test_o_heroic_deste_usuario_e_deste_lar_conta_como_aberto(
        tmp_path: Path, lar_de_mentira: Path) -> None:
    proc = _proc_de_mentira(tmp_path, {
        4103: ("/opt/Heroic/heroic", os.getuid() + 1, "/home/outra-pessoa"),
        4104: ("/usr/bin/heroic-games-launcher", os.getuid(), str(lar_de_mentira))})

    assert censo.heroic_aberto(proc) is True


def test_sem_heroic_nenhum_nao_ha_aberto(tmp_path: Path, lar_de_mentira: Path) -> None:
    proc = _proc_de_mentira(
        tmp_path, {4105: ("/usr/bin/firefox", os.getuid(), str(lar_de_mentira))})

    assert censo.heroic_aberto(proc) is False
