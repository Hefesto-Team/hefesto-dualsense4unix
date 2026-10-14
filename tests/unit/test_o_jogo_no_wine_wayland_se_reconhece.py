"""O jogo no driver Wayland do Wine se reconhece pelo `app_id` do `.exe`.

O-JOGO-NO-WINE-WAYLAND-SE-RECONHECE-PELO-APP-ID-DO-EXE-01. Desde o Wine 9.8 o `app_id` da
janela é o nome do processo («jogo.exe»), e nenhum backend Wayland manda PID: o perfil que
casa por `process_name` ficava sem o jogo. O detector casa o `app_id` com o processo pela
árvore do Wine e entrega o `exe_basename` pelo mesmo caminho da janela X11. A árvore de
`/proc` aqui é de mentira, em `tmp_path`.

A MORDIDA: tirar o casamento pela árvore (`ExeDoWine._varre` sem achar nada) reprova
`test_o_app_id_exe_acha_o_perfil_pelo_processo`; aceitar quem só CITA o `.exe` (tirar
`_e_do_wine`) reprova `test_quem_so_cita_o_exe_nao_e_o_jogo`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.integrations.window_detect import ExeDoWine
from hefesto_dualsense4unix.profiles.schema import MatchCriteria


def _processo(
    proc: Path, pid: int, *argv: str, exe: str = "", comm: str = "", ppid: int = 1
) -> None:
    pasta = proc / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (pasta / "comm").write_text((comm or "x") + "\n", encoding="utf-8")
    (pasta / "stat").write_text(
        f"{pid} ({comm or 'x'}) S {ppid} 0 0 0\n", encoding="utf-8"
    )
    if exe:
        os.symlink(exe, pasta / "exe")


def _janela(app_id: str = "jogo.exe") -> WindowInfo:
    return WindowInfo(wm_class=app_id, pid=0, app_id=app_id, title="Jogo", exe_basename="")


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    raiz = tmp_path / "proc"
    raiz.mkdir()
    _processo(raiz, 50, "/usr/bin/python3", "proton", "waitforexitandrun",
              "/jogos/jogo.exe", exe="/usr/bin/python3.12")
    _processo(raiz, 60, "wineserver", "-p", exe="/opt/ge/files/bin/wineserver",
              comm="wineserver")
    _processo(raiz, 70, "Z:\\jogos\\jogo.exe", exe="/opt/ge/files/bin/wine64-preloader",
              comm="jogo.exe", ppid=50)
    return raiz


def test_o_app_id_exe_acha_o_perfil_pelo_processo(proc: Path) -> None:
    info = ExeDoWine(proc).completar(_janela())
    assert (info.pid, info.exe_basename) == (70, "jogo.exe")
    perfil = MatchCriteria(process_name=["Jogo.EXE"])
    assert perfil.matches(info.as_dict())
    assert not perfil.matches(_janela().as_dict())


def test_a_janela_que_nao_e_exe_passa_como_veio(proc: Path) -> None:
    for app_id in ("google-chrome", "jogo.exe.desktop", ".exe", ""):
        info = _janela(app_id)
        assert ExeDoWine(proc).completar(info) is info


def test_quem_so_cita_o_exe_nao_e_o_jogo(proc: Path) -> None:
    """O `proton waitforexitandrun` tem o `.exe` na linha e não é do Wine."""
    os.unlink(proc / "70" / "exe")
    os.symlink("/usr/bin/python3.12", proc / "70" / "exe")
    info = _janela()
    assert ExeDoWine(proc).completar(info) is info


def test_filho_do_wineserver_conta_mesmo_sem_o_carregador_no_nome(proc: Path) -> None:
    os.unlink(proc / "70" / "exe")
    os.symlink("/opt/outro/loader", proc / "70" / "exe")
    (proc / "70" / "stat").write_text("70 (jogo.exe) S 60 0 0\n", encoding="utf-8")
    assert ExeDoWine(proc).completar(_janela()).pid == 70


def test_o_nome_do_processo_com_parentese_nao_quebra_a_arvore(proc: Path) -> None:
    os.unlink(proc / "70" / "exe")
    os.symlink("/opt/outro/loader", proc / "70" / "exe")
    (proc / "70" / "stat").write_text("70 (jogo) x.exe) S 60 0 0\n", encoding="utf-8")
    assert ExeDoWine(proc).completar(_janela()).pid == 70


def test_o_pid_achado_fica_guardado_e_cai_quando_o_processo_sai(proc: Path) -> None:
    detector = ExeDoWine(proc)
    assert detector.completar(_janela()).pid == 70
    os.rename(proc / "70", proc / "71")
    (proc / "71" / "stat").write_text("71 (jogo.exe) S 1 0 0\n", encoding="utf-8")
    assert detector.completar(_janela()).pid == 71


def test_o_nao_achei_espera_antes_de_varrer_de_novo(tmp_path: Path) -> None:
    vazio = tmp_path / "proc"
    vazio.mkdir()
    agora = [100.0]
    detector = ExeDoWine(vazio, relogio=lambda: agora[0])
    assert detector.completar(_janela()).exe_basename == ""
    _processo(vazio, 9, "Z:\\jogo.exe", exe="/x/wine64-preloader", comm="jogo.exe")
    agora[0] = 100.5
    assert detector.completar(_janela()).exe_basename == ""
    agora[0] = 103.0
    assert detector.completar(_janela()).exe_basename == "jogo.exe"


def test_a_cascata_entrega_o_exe_do_jogo(proc: Path) -> None:
    """O caminho inteiro: o compositor diz só o `app_id`, e o leitor devolve o processo."""

    class _Compositor:
        available = True

        def get_active_window_info(self) -> WindowInfo:
            return _janela()

    cascata = window_detect._WaylandCascadeBackend()
    cascata._cosmic = _Compositor()  # type: ignore[assignment]
    cascata._exe_do_wine = ExeDoWine(proc)
    leitura = window_detect.WindowReaderDiag(cascata)()
    assert leitura["exe_basename"] == "jogo.exe"
    assert leitura["pid"] == 70
    assert leitura["wm_class"] == "jogo.exe"
