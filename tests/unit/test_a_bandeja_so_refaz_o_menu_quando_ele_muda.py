"""O tique da bandeja só cria widget quando o menu muda, e só com uma tela para perguntar."""

from __future__ import annotations

from typing import Any

import pytest


class _Item:
    criados = 0

    def __init__(self, label: str = "") -> None:
        _Item.criados += 1
        self._label = label
        self.rotulos_escritos = 0

    def set_label(self, texto: str) -> None:
        self.rotulos_escritos += 1
        self._label = texto

    def get_label(self) -> str:
        return self._label

    def set_use_underline(self, _v: bool) -> None:
        pass

    def set_sensitive(self, _v: bool) -> None:
        pass

    def connect(self, _sinal: str, _funcao: Any, *_extra: Any) -> None:
        pass


class _Menu:
    def __init__(self) -> None:
        self.itens: list[Any] = []
        self.mexidas = 0

    def append(self, item: Any) -> None:
        self.mexidas += 1
        self.itens.append(item)

    def remove(self, item: Any) -> None:
        self.mexidas += 1
        self.itens.remove(item)

    def show_all(self) -> None:
        self.mexidas += 1


class _Fabrica:
    def __call__(self, label: str = "", **_k: Any) -> _Item:
        return _Item(label)

    @staticmethod
    def new_with_label(label: str = "") -> _Item:
        return _Item(label)


class _GtkDeMentira:
    Menu = _Menu
    MenuItem = _Fabrica()
    SeparatorMenuItem = _Item


class _Tela:
    def __init__(self, monitores: int) -> None:
        self.monitores = monitores
        self.escutas: dict[int, tuple[str, Any]] = {}
        self._proxima = 0

    def get_n_monitors(self) -> int:
        return self.monitores

    def connect(self, sinal: str, funcao: Any) -> int:
        self._proxima += 1
        self.escutas[self._proxima] = (sinal, funcao)
        return self._proxima

    def disconnect(self, escuta: int) -> None:
        del self.escutas[escuta]

    def chega_uma(self) -> None:
        self.monitores += 1
        for sinal, funcao in list(self.escutas.values()):
            if sinal == "monitor-added":
                funcao(self, object())

    def sai_uma(self) -> None:
        self.monitores -= 1


class _GdkDeMentira:
    def __init__(self, tela: _Tela | None) -> None:
        tela_da_vez = tela

        class _Display:
            @staticmethod
            def get_default() -> _Tela | None:
                return tela_da_vez

        self.Display = _Display


@pytest.fixture
def tela() -> _Tela:
    return _Tela(monitores=1)


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch, tela: _Tela) -> Any:
    import hefesto_dualsense4unix.app.tray as modulo

    monkeypatch.setattr(modulo, "Gtk", _GtkDeMentira)
    monkeypatch.setattr(modulo, "Gdk", _GdkDeMentira(tela))
    return modulo


def _perfis(ativo: int, total: int = 31) -> list[dict[str, Any]]:
    return [{"name": f"perfil-{i:02d}", "active": i == ativo} for i in range(total)]


def _bandeja(mod: Any) -> Any:
    bandeja = mod.AppTray(
        on_show_window=lambda: None,
        on_quit=lambda: None,
        on_list_profiles=lambda: [],
        on_switch_profile=lambda _n: True,
    )
    bandeja._menu = _Menu()
    bandeja._profiles_submenu = _Menu()
    bandeja._ouvir_as_telas()
    return bandeja


def _tiques(bandeja: Any, perfis: list[dict[str, Any]], vezes: int,
            estado: dict[str, Any] | None = None) -> int:
    antes = _Item.criados
    for _ in range(vezes):
        bandeja._on_refresh_done((perfis, estado))
    return _Item.criados - antes


def _rotulos(bandeja: Any) -> list[str]:
    return [item.get_label() for item in bandeja._profile_menu_items]


def test_cem_tiques_com_a_mesma_lista_nao_criam_widget(mod: Any) -> None:
    bandeja = _bandeja(mod)
    assert _tiques(bandeja, _perfis(0), 1) == 31
    mexidas = bandeja._profiles_submenu.mexidas

    assert _tiques(bandeja, _perfis(0), 100) == 0
    assert bandeja._profiles_submenu.mexidas == mexidas


def test_a_troca_do_perfil_ativo_refaz_o_submenu_uma_vez_so(mod: Any) -> None:
    bandeja = _bandeja(mod)
    _tiques(bandeja, _perfis(0), 1)

    assert _tiques(bandeja, _perfis(5), 100) == 31
    assert _rotulos(bandeja)[5] == "> perfil-05"
    assert _rotulos(bandeja)[0] == "perfil-00"
    assert len(bandeja._profiles_submenu.itens) == 31


def test_sem_tela_a_troca_espera_e_a_tela_que_volta_aplica_uma_vez(
        mod: Any, tela: _Tela) -> None:
    bandeja = _bandeja(mod)
    _tiques(bandeja, _perfis(0), 1)
    tela.sai_uma()

    assert _tiques(bandeja, _perfis(3), 100) == 0
    assert _rotulos(bandeja)[0] == "> perfil-00"

    antes = _Item.criados
    tela.chega_uma()
    assert _Item.criados - antes == 31
    assert _rotulos(bandeja)[3] == "> perfil-03"

    antes = _Item.criados
    tela.chega_uma()
    assert _Item.criados - antes == 0
    assert _tiques(bandeja, _perfis(3), 100) == 0


def test_a_troca_desfeita_sem_tela_nao_refaz_nada_quando_a_tela_volta(
        mod: Any, tela: _Tela) -> None:
    bandeja = _bandeja(mod)
    _tiques(bandeja, _perfis(0), 1)
    tela.sai_uma()
    _tiques(bandeja, _perfis(7), 3)
    _tiques(bandeja, _perfis(0), 3)

    antes = _Item.criados
    tela.chega_uma()
    assert _Item.criados - antes == 0


def test_a_lista_vazia_mostra_o_aviso_uma_vez(mod: Any) -> None:
    bandeja = _bandeja(mod)
    assert _tiques(bandeja, [], 100) == 1
    assert _rotulos(bandeja) == ["(nenhum perfil)"]
    assert _tiques(bandeja, _perfis(0, total=2), 100) == 2


def test_sem_display_nenhum_o_submenu_ainda_se_refaz(
        monkeypatch: pytest.MonkeyPatch, mod: Any) -> None:
    monkeypatch.setattr(mod, "Gdk", _GdkDeMentira(None))
    bandeja = _bandeja(mod)
    assert _tiques(bandeja, _perfis(0), 1) == 31
    assert _tiques(bandeja, _perfis(0), 100) == 0


def test_o_rotulo_do_servico_so_se_escreve_quando_muda(mod: Any) -> None:
    bandeja = _bandeja(mod)
    bandeja.on_servico = lambda _v: True
    bandeja._montar_os_atos_do_servico()
    item = bandeja._servico_item
    item.rotulos_escritos = 0

    _tiques(bandeja, _perfis(0), 100, estado={"daemon": "vivo"})
    assert item.rotulos_escritos == 0
    assert item.get_label() == "Parar o serviço"

    _tiques(bandeja, _perfis(0), 100, estado=None)
    assert item.rotulos_escritos == 1
    assert item.get_label() == "Ativar o serviço"


def test_o_stop_deixa_de_ouvir_a_tela(mod: Any, tela: _Tela) -> None:
    bandeja = _bandeja(mod)
    assert [s for s, _f in tela.escutas.values()] == ["monitor-added"]
    bandeja._ouvir_as_telas()
    assert len(tela.escutas) == 1

    bandeja.stop()
    assert tela.escutas == {}
