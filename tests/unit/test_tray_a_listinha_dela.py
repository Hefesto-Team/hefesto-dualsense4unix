"""TRAY-A-LISTINHA-DELA-01 — os quatro atos que desceram para a bandeja."""

from __future__ import annotations

from typing import Any

import pytest


class _Item:
    def __init__(self, label: str = "") -> None:
        self._label = label
        self._handlers: list[tuple[str, Any, tuple[Any, ...]]] = []
        self.sensitive = True

    def set_label(self, texto: str) -> None:
        self._label = texto

    def get_label(self) -> str:
        return self._label

    def set_use_underline(self, _v: bool) -> None:
        pass

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = v

    def connect(self, sinal: str, funcao: Any, *extra: Any) -> None:
        self._handlers.append((sinal, funcao, extra))

    def emitir(self, sinal: str = "activate") -> None:
        for nome, funcao, extra in list(self._handlers):
            if nome == sinal:
                funcao(self, *extra)


class _Radio(_Item):
    def __init__(self, label: str = "", group: _Radio | None = None) -> None:
        super().__init__(label)
        self._grupo: list[_Radio] = group._grupo if group is not None else []
        self._grupo.append(self)
        self._ativo = len(self._grupo) == 1

    def get_active(self) -> bool:
        return self._ativo

    def set_active(self, valor: bool) -> None:
        if valor == self._ativo:
            return
        if valor:
            for outro in self._grupo:
                if outro is not self and outro._ativo:
                    outro._ativo = False
                    outro.emitir()
        self._ativo = valor
        self.emitir()


class _Menu:
    def __init__(self) -> None:
        self.itens: list[Any] = []

    def append(self, item: Any) -> None:
        self.itens.append(item)

    def remove(self, item: Any) -> None:
        if item in self.itens:
            self.itens.remove(item)

    def show_all(self) -> None:
        pass


class _Separador(_Item):
    pass


class _Fabrica:
    """`Gtk.MenuItem(...)` E `Gtk.MenuItem.new_with_label(...)` — as duas formas."""

    def __call__(self, label: str = "", **_k: Any) -> _Item:
        return _Item(label)

    @staticmethod
    def new_with_label(label: str = "") -> _Item:
        return _Item(label)


class _GtkDeMentira:
    Menu = _Menu
    SeparatorMenuItem = _Separador
    MenuItem = _Fabrica()

    @staticmethod
    def RadioMenuItem(label: str = "", group: Any = None, **_k: Any) -> _Radio:  # noqa: N802
        return _Radio(label, group)


#: dono lê (`mode_transition.mode_of_state`): `native_mode.enabled` verdadeiro
_MODO_DESLIGADO = {"native_mode": {"enabled": True}}
_MODO_LIGADO = {"gamepad_emulation": {"enabled": True}}


@pytest.fixture
def gtk_de_mentira(monkeypatch: pytest.MonkeyPatch) -> Any:
    import hefesto_dualsense4unix.app.tray as mod

    monkeypatch.setattr(mod, "Gtk", _GtkDeMentira)
    return mod


def _tray(mod: Any, **extras: Any) -> Any:
    tray = mod.AppTray(
        on_show_window=lambda: None,
        on_quit=lambda: None,
        on_list_profiles=lambda: [],
        on_switch_profile=lambda _n: True,
        **extras,
    )
    tray._menu = _Menu()
    return tray


def _rotulos(tray: Any) -> list[str]:
    return [
        "———" if isinstance(i, _Separador) else i.get_label()
        for i in tray._menu.itens
    ]


def test_a_ordem_do_menu_e_a_frase_que_ela_mandou_escrever(
        gtk_de_mentira: Any) -> None:
    """Jogo antes de serviço, e cada grupo atrás da sua divisória."""
    tray = _tray(gtk_de_mentira,
                 on_set_modo=lambda _l: True,
                 on_reconectar=lambda: True,
                 on_servico=lambda _v: True)
    tray._montar_os_atos_do_jogo()
    tray._montar_os_atos_do_servico()

    assert _rotulos(tray) == [
        "———", "Ligado", "Desligado", "Reconectar controles",
        "———", "Reiniciar o serviço", "Parar o serviço",
    ]


def test_o_que_mexe_no_jogo_vem_antes_do_que_mexe_no_servico(
        gtk_de_mentira: Any) -> None:
    """A razão da ordem, medida e não decorada."""
    tray = _tray(gtk_de_mentira,
                 on_set_modo=lambda _l: True,
                 on_servico=lambda _v: True)
    tray._montar_os_atos_do_jogo()
    tray._montar_os_atos_do_servico()
    rotulos = _rotulos(tray)
    assert rotulos.index("Ligado") < rotulos.index("Parar o serviço")


def test_o_tique_que_pinta_a_posicao_nao_manda_nada_ao_daemon(
        gtk_de_mentira: Any) -> None:
    """A PINTURA NÃO É CLIQUE."""
    pedidos: list[bool] = []
    tray = _tray(gtk_de_mentira, on_set_modo=lambda ligado: pedidos.append(ligado))
    tray._montar_os_atos_do_jogo()
    pedidos.clear()

    assert _MODO_DESLIGADO != _MODO_LIGADO
    tray._pintar_o_estado_dos_atos(_MODO_DESLIGADO)
    assert tray._modo_desligado_item.get_active() is True, (
        "o tique não moveu o rádio — a régua não está medindo o que promete")
    tray._pintar_o_estado_dos_atos(_MODO_LIGADO)
    assert tray._modo_ligado_item.get_active() is True

    assert pedidos == [], (
        f"o tique virou clique: o tray mandou {pedidos!r} ao daemon sobre um "
        "modo que ele acabou de LER")


def test_o_clique_no_radio_manda_uma_vez_so(gtk_de_mentira: Any) -> None:
    """Trocar de posição emite nos DOIS itens; só o que ENTROU vale."""
    pedidos: list[bool] = []
    tray = _tray(gtk_de_mentira, on_set_modo=lambda ligado: pedidos.append(ligado))
    tray._montar_os_atos_do_jogo()
    pedidos.clear()

    tray._modo_desligado_item.set_active(True)

    assert pedidos == [False]


def test_o_erro_de_um_clique_nao_derruba_o_menu(gtk_de_mentira: Any) -> None:
    """Uma exceção no handler deixaria o item de bandeja vivo e MUDO."""
    def _explode() -> bool:
        raise RuntimeError("o daemon não está aí")

    tray = _tray(gtk_de_mentira, on_reconectar=_explode)
    tray._montar_os_atos_do_jogo()
    reconectar = tray._menu.itens[-1]

    reconectar.emitir()


def test_sem_callback_o_item_nao_nasce(gtk_de_mentira: Any) -> None:
    """Botão que aparece e não faz nada ensina que a tela é enfeite."""
    tray = _tray(gtk_de_mentira)
    tray._montar_os_atos_do_jogo()
    tray._montar_os_atos_do_servico()
    assert tray._menu.itens == []


def test_so_o_reconectar_nao_traz_os_radios(gtk_de_mentira: Any) -> None:
    tray = _tray(gtk_de_mentira, on_reconectar=lambda: True)
    tray._montar_os_atos_do_jogo()
    assert _rotulos(tray) == ["———", "Reconectar controles"]


def test_o_rotulo_do_servico_segue_o_estado(gtk_de_mentira: Any) -> None:
    """Um item, dois rótulos — a forma que ela escolheu em 03/09/2026."""
    verbos: list[str] = []
    tray = _tray(gtk_de_mentira, on_servico=lambda v: verbos.append(v))
    tray._montar_os_atos_do_servico()
    item = tray._menu.itens[-1]

    tray._pintar_o_estado_dos_atos({"controllers": []})
    assert item.get_label() == "Parar o serviço"
    item.emitir()

    tray._pintar_o_estado_dos_atos(None)
    assert item.get_label() == "Ativar o serviço"
    item.emitir()

    assert verbos == ["stop", "start"]


def test_o_modo_desconhecido_nao_mexe_nos_radios(gtk_de_mentira: Any) -> None:
    """`None` é "não sei", e mentir uma posição é pior que não dizer."""
    tray = _tray(gtk_de_mentira, on_set_modo=lambda _l: True)
    tray._montar_os_atos_do_jogo()
    tray._modo_desligado_item.set_active(True)

    tray._pintar_o_estado_dos_atos(None)

    assert tray._modo_desligado_item.get_active() is True
    assert tray._modo_ligado_item.get_active() is False


def test_o_interruptor_despacha_o_plano_do_dono_na_ordem_dele(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O plano é de `painel.plano_do_modo`, e a ORDEM é a entrega."""
    from hefesto_dualsense4unix.app.actions.jogar.painel import plano_do_modo
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD
    from hefesto_dualsense4unix.cli import cmd_tray

    chamadas: list[tuple[str, dict[str, Any] | None]] = []
    monkeypatch.setattr(cmd_tray, "_chamar",
                        lambda m, a=None: chamadas.append((m, a)) or {})
    monkeypatch.setattr(cmd_tray, "_servico", lambda _v: True)

    cmd_tray._definir_o_modo(True)

    assert chamadas == list(plano_do_modo(MODE_GAMEPAD))


def test_ligar_sobe_o_servico_antes_de_falar_com_o_daemon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Decisão dela, 03/09/2026 — e a ORDEM é o ponto."""
    from hefesto_dualsense4unix.cli import cmd_tray

    passos: list[str] = []
    monkeypatch.setattr(cmd_tray, "_servico",
                        lambda v: passos.append(f"serviço:{v}") or True)
    monkeypatch.setattr(cmd_tray, "_chamar",
                        lambda m, a=None: passos.append(m) or {})

    cmd_tray._definir_o_modo(True)

    assert passos[0] == "serviço:start"


def test_desligar_nao_sobe_servico_nenhum(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """«Desligado» é o modo NATIVO, não "parar o Hefesto" — decisão dela."""
    from hefesto_dualsense4unix.cli import cmd_tray

    passos: list[str] = []
    monkeypatch.setattr(cmd_tray, "_servico",
                        lambda v: passos.append(f"serviço:{v}") or True)
    monkeypatch.setattr(cmd_tray, "_chamar",
                        lambda m, a=None: passos.append(m) or {})

    cmd_tray._definir_o_modo(False)

    assert not [p for p in passos if p.startswith("serviço:")]


def test_o_reconectar_faz_os_dois_passos_da_aba_jogar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`coop.sync` e `identity.renumber` — e nenhum `Connect` pelo rádio."""
    from hefesto_dualsense4unix.cli import cmd_tray

    chamados: list[str] = []
    monkeypatch.setattr(cmd_tray, "_chamar",
                        lambda m, a=None: chamados.append(m) or {})

    assert cmd_tray._reconectar_os_controles() is True
    assert chamados == ["coop.sync", "identity.renumber"]


def test_o_titulo_nao_conta_perfis(gtk_de_mentira: Any) -> None:
    """*"no tray remover o numero de perfis"* — palavra dela, 21/09/2026."""
    tray = _tray(gtk_de_mentira)
    tray._status_item = _Item("")
    tray._profiles_submenu = _Menu()

    tray._render_profiles([{"name": "Padrão"}, {"name": "Outro"}])

    assert "perfis" not in tray._status_item.get_label()
    assert tray._status_item.get_label() == "Hefesto - DualSense4Unix"


def test_o_titulo_continua_dizendo_o_perfil_ativo(gtk_de_mentira: Any) -> None:
    """O que saiu foi a CONTAGEM, não a resposta — o perfil de agora fica."""
    tray = _tray(gtk_de_mentira)
    tray._status_item = _Item("")
    tray._profiles_submenu = _Menu()

    tray._render_profiles([{"name": "Padrão"}, {"name": "Meu", "active": True}])

    assert tray._status_item.get_label() == (
        "Hefesto - DualSense4Unix - perfil: Meu")
