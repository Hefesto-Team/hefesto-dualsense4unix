"""D-2511-A-BANDEJA-AVISA-QUANDO-NAO-APARECE: o ícone diz quando não aparece e quando falha.

Sem hospedeiro de bandeja o aviso sai em toda sessão, com o que ligar no ambiente (o GNOME pede a
extensão AppIndicator, e nunca fala de COSMIC). O clique num perfil não prende o menu, e a troca
que não pegou, como o «Sair» cujo `stop` falhou, vira um aviso.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Any

import pytest

from tests.unit import test_o_sair_do_tray_para_o_servico as sair
from tests.unit import test_tray_a_listinha as base

gtk_de_mentira = base.gtk_de_mentira
sincrono = sair.sincrono


@pytest.fixture
def avisos(gtk_de_mentira: Any, monkeypatch: pytest.MonkeyPatch,
           tmp_path: Any) -> list[dict[str, Any]]:
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "runtime_dir", lambda ensure=False: tmp_path)
    dados: list[dict[str, Any]] = []

    def notify(summary: str, body: str = "", **kw: Any) -> bool:
        dados.append({"summary": summary, "body": body, **kw})
        return True

    monkeypatch.setattr(gtk_de_mentira, "notify", notify)
    return dados


def _sem_hospedeiro(mod: Any, monkeypatch: pytest.MonkeyPatch, desktop: str) -> Any:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    monkeypatch.setenv("XDG_SESSION_DESKTOP", desktop.lower())
    monkeypatch.setattr(mod, "statusnotifierwatcher_available", lambda: False)
    chamadas: list[str] = []
    tray = mod.AppTray(
        on_show_window=lambda: None, on_quit=lambda: None, on_list_profiles=lambda: [],
        on_switch_profile=lambda _n: True,
        on_sem_hospedeiro=lambda: chamadas.append("sem-hospedeiro"))
    tray.chamadas = chamadas
    return tray


def test_no_gnome_sem_hospedeiro_o_aviso_manda_ligar_o_appindicator(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: voltar a sonda ao `if _desktop_is_cosmic()` zera o aviso do GNOME."""
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "GNOME")
    tray._probe_watcher_with_retries(gtk_de_mentira._WATCHER_PROBE_RETRIES - 1)
    assert len(avisos) == 1
    assert "AppIndicator" in avisos[0]["body"]
    assert "COSMIC" not in avisos[0]["body"]
    assert tray.chamadas == ["sem-hospedeiro"]


def test_no_cosmic_o_aviso_segue_pedindo_o_applet_com_acento(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "COSMIC")
    tray._probe_watcher_with_retries(gtk_de_mentira._WATCHER_PROBE_RETRIES - 1)
    corpo = avisos[0]["body"]
    assert "«Área de status»" in corpo and "não tem onde aparecer" in corpo
    assert "AppIndicator" not in corpo


def test_em_outro_ambiente_o_aviso_manda_ligar_a_bandeja_do_painel(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "XFCE")
    tray._probe_watcher_with_retries(gtk_de_mentira._WATCHER_PROBE_RETRIES - 1)
    assert "bandeja do painel" in avisos[0]["body"]


def test_o_aviso_sai_uma_vez_e_o_processo_e_avisado_toda_vez(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "GNOME")
    ultima = gtk_de_mentira._WATCHER_PROBE_RETRIES - 1
    tray._probe_watcher_with_retries(ultima)
    tray._probe_watcher_with_retries(ultima)
    assert len(avisos) == 1
    assert tray.chamadas == ["sem-hospedeiro", "sem-hospedeiro"]


def test_com_hospedeiro_nao_avisa_nem_larga_o_icone(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "GNOME")
    monkeypatch.setattr(gtk_de_mentira, "statusnotifierwatcher_available", lambda: True)
    tray._probe_watcher_with_retries(0)
    assert avisos == [] and tray.chamadas == []


@pytest.mark.parametrize("por_que", ["o D-Bus não respondeu", "a bandeja XEmbed do X11 mostra"])
def test_sem_certeza_de_que_o_icone_sumiu_nada_avisa_e_o_icone_fica(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch, por_que: str) -> None:
    """MORDIDA: o «não sei» da sonda, ou o X11 com XEmbed, lidos como «não há» largam o ícone."""
    tray = _sem_hospedeiro(gtk_de_mentira, monkeypatch, "XFCE")
    if por_que.startswith("o D-Bus"):
        monkeypatch.setattr(gtk_de_mentira, "statusnotifierwatcher_available", lambda: None)
    else:
        monkeypatch.setattr(gtk_de_mentira, "_bandeja_xembed_de_pe", lambda: True)
    tray._probe_watcher_with_retries(gtk_de_mentira._WATCHER_PROBE_RETRIES - 1)
    assert avisos == [] and tray.chamadas == []


def test_a_bandeja_xembed_so_conta_no_x11(gtk_de_mentira: Any) -> None:
    """No Wayland não há XEmbed: a tela que não é do X11 nunca conta como bandeja."""
    assert gtk_de_mentira._bandeja_xembed_de_pe() is False


def test_a_sonda_do_hospedeiro_e_agendada_em_toda_sessao(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `_start_deferred` fora do COSMIC também agenda a sonda (antes só o COSMIC)."""
    tray = sair._tray_montado(gtk_de_mentira, monkeypatch)
    agendados: list[Any] = []
    monkeypatch.setattr(gtk_de_mentira, "GLib", type("G", (), {
        "timeout_add_seconds": staticmethod(lambda *_a: 0),
        "timeout_add": staticmethod(lambda *a: agendados.append(a) or 0),
    }))
    assert tray._start_deferred() is True
    assert len(agendados) == 1


def _com_a_lista(tray: Any, nome: str) -> Any:
    tray._profiles_submenu = base._Menu()
    tray._render_profiles([{"name": nome, "active": False}])
    return tray._profiles_submenu.itens[0]


def test_o_clique_num_perfil_nao_prende_o_menu(
        gtk_de_mentira: Any, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: voltar o item ao `self.on_switch_profile(n)` direto prende o menu até a troca."""
    solta = threading.Event()
    chamadas: list[str] = []

    def lenta(nome: str) -> bool:
        chamadas.append(nome)
        solta.wait(timeout=10)
        return True

    tray = base._tray(gtk_de_mentira)
    tray.on_switch_profile = lenta
    item = _com_a_lista(tray, "Corrida")
    t0 = time.monotonic()
    item.emitir()
    gasto = time.monotonic() - t0
    solta.set()
    assert gasto < 0.05, f"o clique prendeu o menu por {gasto * 1000:.0f} ms"
    assert avisos == []


def test_a_troca_que_nao_pegou_vira_aviso(
        gtk_de_mentira: Any, sincrono: None, avisos: list[dict[str, Any]]) -> None:
    tray = base._tray(gtk_de_mentira)
    tray.on_switch_profile = lambda _n: False
    _com_a_lista(tray, "Corrida").emitir()
    assert len(avisos) == 1
    assert "Corrida" in avisos[0]["body"]


def test_a_troca_que_levanta_vira_aviso_e_a_bandeja_nao_cai(
        gtk_de_mentira: Any, sincrono: None, avisos: list[dict[str, Any]]) -> None:
    def quebra(_n: str) -> bool:
        raise RuntimeError("o serviço sumiu")

    tray = base._tray(gtk_de_mentira)
    tray.on_switch_profile = quebra
    _com_a_lista(tray, "Corrida").emitir()
    assert len(avisos) == 1 and "Corrida" in avisos[0]["body"]


def test_a_troca_que_pegou_nao_avisa(
        gtk_de_mentira: Any, sincrono: None, avisos: list[dict[str, Any]]) -> None:
    tray = base._tray(gtk_de_mentira)
    _com_a_lista(tray, "Corrida").emitir()
    assert avisos == []


@pytest.mark.parametrize("como", ["falso", "levanta"])
def test_o_sair_cujo_stop_falhou_avisa_e_o_icone_fica(
        gtk_de_mentira: Any, sincrono: None, avisos: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch, como: str) -> None:
    def stop(_verbo: str) -> bool:
        if como == "levanta":
            raise RuntimeError("systemctl sumiu")
        return False

    tray = sair._tray_montado(gtk_de_mentira, monkeypatch, on_servico=stop)
    sair._sair(tray).emitir()
    assert tray.saidas == []
    assert len(avisos) == 1
    assert "serviço" in avisos[0]["body"]


def test_o_plano_b_da_troca_chama_o_python_em_uso(monkeypatch: pytest.MonkeyPatch) -> None:
    """O serviço parado: a troca sai por `sys.executable -m ...cli.app`, não pelo nome no PATH."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.cli import cmd_tray

    monkeypatch.setattr(ipc_bridge, "pedir_ao_servico",
                        lambda *_a, **_k: ipc_bridge.Desfecho(ipc_bridge.PARADO))
    argvs: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen",
                        lambda argv, **_k: argvs.append(list(argv)) or None)
    assert cmd_tray._trocar_de_perfil("Corrida") is True
    assert argvs == [[sys.executable, "-m", "hefesto_dualsense4unix.cli.app",
                      "profile", "activate", "Corrida"]]


def test_sem_hospedeiro_o_comando_diz_e_o_icone_fica(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """MORDIDA: sair do laço sem hospedeiro apaga o ícone que o painel lento do login hospedaria."""
    from hefesto_dualsense4unix.app import tray as mod_tray
    from hefesto_dualsense4unix.cli import cmd_tray

    gtk = mod_tray.Gtk
    montadas: list[dict[str, Any]] = []
    saidas: list[str] = []

    class Bandeja:
        def __init__(self, **kw: Any) -> None:
            montadas.append(kw)

        def start(self) -> bool:
            return True

        def stop(self) -> None:
            saidas.append("stop")

    monkeypatch.setattr(mod_tray, "AppTray", Bandeja)
    monkeypatch.setattr(mod_tray, "probe_gi_availability", lambda: (True, ""))
    monkeypatch.setattr(cmd_tray, "tomar_a_vez", lambda: True)
    monkeypatch.setattr(cmd_tray, "soltar_a_vez", lambda: None)
    monkeypatch.setattr(gtk, "main_quit", lambda: saidas.append("main_quit"))
    monkeypatch.setattr(gtk, "main", lambda: montadas[0]["on_sem_hospedeiro"]())
    cmd_tray.tray_cmd()
    assert saidas == ["stop"]
    assert "não tem onde aparecer" in capsys.readouterr().out
