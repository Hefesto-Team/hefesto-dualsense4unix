"""DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01 — «Sair» do tray para o serviço.

A irmã dela estranhou (03/10/2026): o item «Sair do Hefesto - DualSense4Unix»
só chamava o ``on_quit`` (``Gtk.main_quit``). O ícone sumia e o daemon seguia
de pé com o controle na mão. Agora o item faz o mesmo ato do «Parar o serviço»
(``on_servico("stop")``) e só fecha o ícone se o serviço parou.

O menu é o de verdade (``_start_deferred``), com o Gtk e o indicador de mentira
do ``test_tray_a_listinha``; a thread do ``run_in_thread`` roda no ato.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit import test_tray_a_listinha as base

ROTULO = "Sair do Hefesto - DualSense4Unix"

gtk_de_mentira = base.gtk_de_mentira


class _Indicador:
    @staticmethod
    def new(*_a: Any) -> _Indicador:
        return _Indicador()

    class _Ns:
        class IndicatorStatus:
            ACTIVE = 1

    _hefesto_ns = _Ns

    def set_status(self, _s: Any) -> None:
        pass

    def set_title(self, _t: str) -> None:
        pass

    def set_menu(self, _m: Any) -> None:
        pass


def _anota(lista: list[str], valor: str) -> bool:
    lista.append(valor)
    return True


@pytest.fixture
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    """A thread worker vira chamada direta; os callbacks voltam na hora."""
    from hefesto_dualsense4unix.app import ipc_bridge

    def _run(fn: Any, ok: Any, falha: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as erro:
            if falha is not None:
                falha(erro)
            return
        ok(resultado)

    monkeypatch.setattr(ipc_bridge, "run_in_thread", _run)


def _tray_montado(mod: Any, monkeypatch: pytest.MonkeyPatch, **extras: Any) -> Any:
    """Um AppTray cujo menu saiu do `_start_deferred` de produção."""
    saidas: list[str] = []
    tray = mod.AppTray(
        on_show_window=lambda: None,
        on_quit=lambda: saidas.append("on_quit"),
        on_list_profiles=lambda: [],
        on_switch_profile=lambda _n: True,
        **extras,
    )
    tray.saidas = saidas
    monkeypatch.setattr(mod.AppTray, "_resolve_indicator",
                        staticmethod(lambda _gi: (_Indicador, "cat")))
    monkeypatch.setattr(mod.AppTray, "_preferred_icon", staticmethod(lambda: "x"))
    monkeypatch.setattr(mod.AppTray, "_ensinar_o_caminho_do_icone", lambda self, _i: None)
    monkeypatch.setattr(mod.AppTray, "_tick_refresh", lambda self: True)
    monkeypatch.setattr(mod.AppTray, "_render_profiles", lambda self, _p: None)
    monkeypatch.setattr(mod, "GLib", type("G", (), {
        "timeout_add_seconds": staticmethod(lambda *_a: 0),
        "timeout_add": staticmethod(lambda *_a: 0),
    }))
    monkeypatch.setattr(mod, "_desktop_is_cosmic", lambda: False)
    monkeypatch.setattr(base._Item, "set_submenu", lambda self, _m: None, raising=False)
    assert tray._start_deferred() is True
    return tray


def _sair(tray: Any) -> Any:
    itens = [i for i in tray._menu.itens if i.get_label() == ROTULO]
    assert len(itens) == 1, "o item Sair tem de existir uma vez só, com o nome da casa"
    return itens[0]


def test_sair_para_o_servico_e_depois_fecha_o_icone(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: volte o item a `lambda _w: self.on_quit()` e o `stop` nunca sai."""
    pedidos: list[str] = []
    tray = _tray_montado(gtk_de_mentira, monkeypatch,
                         on_servico=lambda verbo: _anota(pedidos, verbo))
    _sair(tray).emitir()
    assert pedidos == ["stop"]
    assert tray.saidas == ["on_quit"]


def test_o_stop_vem_antes_de_o_icone_sumir(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    ordem: list[str] = []
    tray = _tray_montado(gtk_de_mentira, monkeypatch,
                         on_servico=lambda verbo: _anota(ordem, verbo))
    tray.on_quit = lambda: _anota(ordem, "on_quit")
    _sair(tray).emitir()
    assert ordem == ["stop", "on_quit"]


def test_se_o_servico_nao_parou_o_icone_fica(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sumir com o ícone de um serviço que segue rodando é o defeito de 03/10."""
    tray = _tray_montado(gtk_de_mentira, monkeypatch, on_servico=lambda _v: False)
    _sair(tray).emitir()
    assert tray.saidas == []


def test_se_o_ato_levanta_o_icone_fica_e_o_tray_nao_cai(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def _quebra(_v: str) -> bool:
        raise RuntimeError("systemctl sumiu")

    tray = _tray_montado(gtk_de_mentira, monkeypatch, on_servico=_quebra)
    _sair(tray).emitir()
    assert tray.saidas == []


def test_sem_servico_para_parar_so_sai(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _tray_montado(gtk_de_mentira, monkeypatch)
    _sair(tray).emitir()
    assert tray.saidas == ["on_quit"]


def test_o_sair_e_o_parar_chamam_o_mesmo_ato(
        gtk_de_mentira: Any, sincrono: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Parar o serviço» do tray e o «Sair» vão ao MESMO `on_servico("stop")`."""
    pedidos: list[str] = []
    tray = _tray_montado(gtk_de_mentira, monkeypatch,
                         on_servico=lambda verbo: _anota(pedidos, verbo))
    tray._servico_de_pe = True
    tray._servico_item.emitir()
    _sair(tray).emitir()
    assert pedidos == ["stop", "stop"]
