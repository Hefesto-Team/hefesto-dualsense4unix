"""AVISO-VIVO-01 — o aviso do rodapé para de ficar preso mentindo.

Defeito medido na tela (27/07, 17:14): o cadeado de autoswitch foi religado por
fora da janela (chamada IPC direta) e o rodapé continuou MINUTOS escrito "Troca
automática de perfil LIBERADA — o Hefesto volta a escolher o perfil ao abrir
cada jogo", com o cadeado LIGADO e a frase de causa, logo acima, dizendo o
contrário. A janela se contradizia em dois lugares ao mesmo tempo.

Causa: o toast era o registro de "o que eu pedi uma vez" (escrito só pelo
handler do cadeado) e o `_render_home` não tocava na statusbar em ponto nenhum
— a frase ficava até outro toast do mesmo contexto sobrescrever.

Segundo sintoma, mesma origem: uma reconciliação de 2 s levou 78 s. O latch
`_home_inflight` não tinha prazo de validade: chamada que não volta prendia a
aba parada, em silêncio.

Hermético: statusbar dublê FIEL (pilha por contexto, como a Gtk.Statusbar de
verdade, para que "apagar" seja testado como apagar e não como empilhar), Gtk
falso em ``sys.modules`` e `call_async` monkeypatchado.
"""
from __future__ import annotations

import sys
import time
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin

#: O texto EXATO que o handler do cadeado deixa no rodapé ao destravar — é ele
#: que ficou preso na tela dela com o cadeado já ligado.
FRASE_DO_CLIQUE_ANTIGO = (
    "Troca automática de perfil LIBERADA — o Hefesto volta a escolher o perfil "
    "ao abrir cada jogo."
)


class _StatusbarFalsa:
    """Dublê fiel do ``Gtk.Statusbar``.

    Importa reproduzir a PILHA: ``pop`` tira a mensagem mais recente daquele
    contexto e quem aparece é o topo da pilha inteira. É por causa disso que o
    aviso de estado tem de morar no MESMO contexto do handler do cadeado — um
    contexto próprio só cobriria a frase velha, e ela ressurgiria ao ser
    apagada.
    """

    def __init__(self) -> None:
        self.pilha: list[tuple[str, str]] = []

    def get_context_id(self, contexto: str) -> str:
        return contexto

    def pop(self, contexto: str) -> None:
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == contexto:
                del self.pilha[i]
                return

    def push(self, contexto: str, mensagem: str) -> None:
        self.pilha.append((contexto, mensagem))

    @property
    def visivel(self) -> str:
        """O que a usuária lê no rodapé agora."""
        return self.pilha[-1][1] if self.pilha else ""


class _Estilo:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, nome: str) -> None:
        if nome not in self.classes:
            self.classes.append(nome)

    def remove_class(self, nome: str) -> None:
        if nome in self.classes:
            self.classes.remove(nome)


class _WidgetFalso:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_WidgetFalso] = []
        self.style = _Estilo()
        self.sensitive = True
        self.visible = True
        self.active = False

    def get_style_context(self) -> _Estilo:
        return self.style

    def set_xalign(self, _valor: float) -> None:
        pass

    def set_margin_end(self, _valor: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, texto: str) -> None:
        self.label = texto

    def set_label(self, texto: str) -> None:
        self.label = texto

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, valor: bool) -> None:
        self.sensitive = valor

    def set_visible(self, valor: bool) -> None:
        self.visible = valor

    def set_no_show_all(self, _valor: bool) -> None:
        pass

    def set_active(self, valor: bool) -> None:
        self.active = valor

    def set_active_id(self, _valor: str) -> None:
        pass

    def pack_start(self, filho: _WidgetFalso, *_args: object) -> None:
        self.children.append(filho)

    def get_children(self) -> list[_WidgetFalso]:
        return list(self.children)

    def remove(self, filho: _WidgetFalso) -> None:
        self.children.remove(filho)

    def show_all(self) -> None:
        pass


class _HomeStub:
    """A aba Início sem GTK — com a statusbar de verdade do ``_status_toast``."""

    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    # COOP-SEM-INTERRUPTOR-01 (06/08/2026): o `_render_coop_prep` e o botão
    # "Preparar co-op" NÃO existem mais — cada controle conectado já é um
    # jogador, sempre. `test_home_render_state.py` tem portão que exige a
    # ausência dos dois. Não reponha.
    # PONTE-NA-TELA-01: parte do `_render_home` como os outros reconciliadores.
    _render_ponte_e_divergencia = HomeActionsMixin._render_ponte_e_divergencia
    _mascara_escolhida_por_ela = HomeActionsMixin._mascara_escolhida_por_ela
    _refresh_home_tab = HomeActionsMixin._refresh_home_tab
    # O helper REAL (pop antes do push): o teste não pode inventar uma
    # semântica de statusbar mais gentil do que a que roda na máquina dela.
    _status_toast = WidgetAccessMixin._status_toast

    def __init__(self) -> None:
        self.barra = _StatusbarFalsa()
        self._home_installed = True
        self._home_inflight = False
        self._home_inflight_since = 0.0
        self._home_guard = False
        self._home_controllers_box = _WidgetFalso()
        self._home_mode_selector = _WidgetFalso()
        self._home_players_hint = _WidgetFalso()
        self._home_flavor_selector = _WidgetFalso()
        self._home_mode_desc = _WidgetFalso()
        self._home_origin_label = _WidgetFalso()
        self._home_session_label = _WidgetFalso()
        self._home_gamepad_opts = _WidgetFalso()
        self._home_vpad_banner = _WidgetFalso()
        self._home_wrapper_banner = _WidgetFalso()
        self._home_shutdown_btn = _WidgetFalso()
        self._home_offline = False
        self._home_reconciliar_btn = _WidgetFalso()
        self._home_reconciliar_hint = _WidgetFalso()
        self._home_autoswitch_lock = _WidgetFalso()
        self._home_autoswitch_lock_hint = _WidgetFalso()
        # PONTE-NA-TELA-01: linha "Ponte com o jogo" + banner da divergência.
        self._home_ponte_label = _WidgetFalso()
        self._home_divergencia_banner = _WidgetFalso()
        self._home_flavor_pedido: str | None = None

    def _get(self, widget_id: str) -> Any:
        return self.barra if widget_id == "status_bar" else None


@pytest.fixture()
def gtk_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_WidgetFalso,
        Box=_WidgetFalso,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _estado(*, cadeado: bool, perfil: str | None = None) -> dict[str, Any]:
    estado: dict[str, Any] = {
        "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
        "native_mode": False,
        "controllers": [],
        "autoswitch_locked": cadeado,
    }
    if perfil is not None:
        estado["active_profile"] = perfil
    return estado


class TestRodapeSegueOEstado:
    """O aviso descreve o ESTADO — nunca sobrevive a ele."""

    def test_cadeado_religado_por_fora_apaga_a_frase_do_clique_antigo(
        self, gtk_falso: None
    ) -> None:
        """O defeito medido: a frase do clique antigo some no primeiro render
        que vê o cadeado ligado (antes, ficava minutos)."""
        host = _HomeStub()
        # Ela destravou pela janela em algum momento — o handler do cadeado
        # deixou a frase no contexto "home".
        host._status_toast("home", FRASE_DO_CLIQUE_ANTIGO)
        assert host.barra.visivel == FRASE_DO_CLIQUE_ANTIGO

        # Alguém religou o cadeado por fora (IPC direto); chega o tick.
        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))

        assert "LIBERADA" not in host.barra.visivel
        assert "Cadeado ligado" in host.barra.visivel
        assert "Pragmata2" in host.barra.visivel

    def test_rodape_e_frase_de_causa_dizem_a_mesma_coisa(
        self, gtk_falso: None
    ) -> None:
        """Os dois lugares que se contradiziam passam a ter uma fonte só."""
        host = _HomeStub()
        host._status_toast("home", FRASE_DO_CLIQUE_ANTIGO)

        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))

        assert host.barra.visivel == host._home_autoswitch_lock_hint.get_text()

    def test_destravar_por_fora_limpa_o_aviso_de_cadeado_ligado(
        self, gtk_falso: None
    ) -> None:
        """A mentira simétrica: "Cadeado ligado" preso com o cadeado solto."""
        host = _HomeStub()
        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))
        assert "Cadeado ligado" in host.barra.visivel

        host._render_home(_estado(cadeado=False))

        assert "Cadeado ligado" not in host.barra.visivel

    def test_daemon_desligado_nao_deixa_afirmacao_viva(
        self, gtk_falso: None
    ) -> None:
        """Offline não é "destravado", é "não sei" — e nada pode continuar
        afirmado (mesma regra que a frase de causa já seguia)."""
        host = _HomeStub()
        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))

        host._render_home(None)

        assert "Cadeado ligado" not in host.barra.visivel

    def test_toast_de_outra_acao_sobrevive_ao_tick_seguinte(
        self, gtk_falso: None
    ) -> None:
        """A escrita é por BORDA: com o estado parado, o aviso não come o
        retorno das outras ações (era o risco de dar o rodapé ao render)."""
        host = _HomeStub()
        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))
        host._status_toast("home", "Numeração compactada — 2 controle(s).")

        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))
        host._render_home(_estado(cadeado=True, perfil="Pragmata2"))

        assert host.barra.visivel == "Numeração compactada — 2 controle(s)."

    def test_abrir_a_janela_sem_cadeado_nao_escreve_no_rodape(
        self, gtk_falso: None
    ) -> None:
        """Sem cadeado não há o que explicar — e o primeiro render não pode
        apagar o rodapé de quem já estava lá."""
        host = _HomeStub()
        host._status_toast("outra_aba", "Perfil salvo.")

        host._render_home(_estado(cadeado=False))

        assert host.barra.visivel == "Perfil salvo."


class TestLatchComPrazoDeValidade:
    """`_home_inflight` sem prazo congelava a aba em silêncio."""

    def _falso_call_async(
        self, registro: list[str]
    ) -> Any:
        def _fake(
            metodo: str,
            _params: dict[str, Any] | None,
            _done: Any = None,
            _fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            registro.append(metodo)

        return _fake

    def test_prazo_vale_tres_ticks_do_poller(self) -> None:
        medido = home_actions.HOME_INFLIGHT_TIMEOUT_S
        esperado = 3 * home_actions.HOME_POLL_INTERVAL_MS / 1000.0
        assert abs(medido - esperado) < 1e-9

    def test_chamada_recente_ainda_segura_o_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O latch continua fazendo o serviço dele: nada de empilhar chamadas."""
        chamadas: list[str] = []
        monkeypatch.setattr(
            home_actions, "call_async", self._falso_call_async(chamadas)
        )
        host = _HomeStub()
        host._home_inflight = True
        host._home_inflight_since = time.monotonic() - 0.5

        host._refresh_home_tab()

        assert chamadas == []

    def test_chamada_que_nunca_voltou_e_dada_como_perdida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A aba destrava sozinha: passado o prazo sai uma chamada nova."""
        chamadas: list[str] = []
        monkeypatch.setattr(
            home_actions, "call_async", self._falso_call_async(chamadas)
        )
        host = _HomeStub()
        host._home_inflight = True
        host._home_inflight_since = (
            time.monotonic() - home_actions.HOME_INFLIGHT_TIMEOUT_S - 1.0
        )

        host._refresh_home_tab()

        assert chamadas == ["daemon.state_full"]

    def test_o_prazo_reinicia_a_cada_chamada_nova(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem recarimbar, a chamada nova nasceria já vencida e o tick seguinte
        dispararia outra — o latch viraria enfeite."""
        chamadas: list[str] = []
        monkeypatch.setattr(
            home_actions, "call_async", self._falso_call_async(chamadas)
        )
        host = _HomeStub()
        host._home_inflight = True
        host._home_inflight_since = (
            time.monotonic() - home_actions.HOME_INFLIGHT_TIMEOUT_S - 1.0
        )

        host._refresh_home_tab()
        host._refresh_home_tab()

        assert chamadas == ["daemon.state_full"]
        assert host._home_inflight_since > time.monotonic() - 1.0
