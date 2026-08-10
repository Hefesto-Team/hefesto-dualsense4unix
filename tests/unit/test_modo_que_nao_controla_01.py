"""MODO-QUE-NAO-CONTROLA-01 — "Controlar o PC" que entra sem controlar o PC.

Medido com ela ao vivo em 09/08/2026, às 23h50. Ela escolheu "Controlar o PC",
clicou no "Aplicar" e relatou: *"cliquei em aplicar e nada"*.

O modo ENTROU — o journal prova (`native_mode_changed native=False`,
`gamepad_controller_grab state=off`, `mouse_preference_restored enabled=False
ok=True`) — e o controle não movia o cursor, porque a preferência de mouse
persistida dela estava desligada.

**O daemon fez o certo, e continua fazendo:** `mouse.emulation.restore` restaura
a preferência dela (HARM-06), nunca impõe uma. O defeito era o SILÊNCIO: nenhuma
superfície dizia por que o modo entrou sem fazer nada, e ela só descobriu quando
alguém leu o journal por ela.

A cura é a tela dizer. Estes testes trancam as duas metades:

1. a frase certa nos casos certos, e **nenhuma frase** nos casos em que ela
   seria alarme falso (fora do desktop, payload incompleto, transição em voo);
2. o plano do modo desktop continua NÃO impondo mouse nenhum — se alguém trocar
   a cura pela outra saída (o modo LIGAR o mouse), este teste reprova e a
   decisão volta para ela, que é de quem ela é.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_DESKTOP_SEM_MOUSE,
    TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO,
    TEXTO_DESKTOP_SEM_TECLADO,
    HomeActionsMixin,
    texto_do_desktop_sem_emulacao,
)
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    plan_mode_transition,
)


def _estado(
    *,
    mouse: bool | None = None,
    teclado: bool | None = None,
    native: bool = False,
    gamepad: bool = False,
) -> dict[str, Any]:
    """Um `daemon.state_full` mínimo. ``None`` = o bloco NÃO vem no payload."""
    estado: dict[str, Any] = {
        "native_mode": native,
        "gamepad_emulation": {"enabled": gamepad, "flavor": "dualsense"},
        "controllers": [],
    }
    if mouse is not None:
        estado["mouse_emulation"] = {
            "enabled": mouse,
            "speed": 9,
            "scroll_speed": 4,
        }
    if teclado is not None:
        estado["keyboard_emulation"] = {
            "enabled": teclado,
            "device_ativo": teclado,
            "despachando": teclado,
            "bloqueio": None if teclado else "desligada",
        }
    return estado


class TestAFraseCerta:
    """O caso dela, e os dois irmãos que o mesmo silêncio cobria."""

    def test_o_caso_dela_mouse_desligado_no_desktop(self) -> None:
        """23h50 de 09/08: modo de pé, mouse desligado, tela calada."""
        assert (
            texto_do_desktop_sem_emulacao(_estado(mouse=False, teclado=True))
            == TEXTO_DESKTOP_SEM_MOUSE
        )

    def test_teclado_desligado_no_desktop(self) -> None:
        assert (
            texto_do_desktop_sem_emulacao(_estado(mouse=True, teclado=False))
            == TEXTO_DESKTOP_SEM_TECLADO
        )

    def test_os_dois_desligados_falam_dos_dois(self) -> None:
        """Com os dois desligados o modo não faz NADA — dizer só do mouse
        mandaria ela ligar um interruptor e continuar sem entender o outro."""
        assert (
            texto_do_desktop_sem_emulacao(_estado(mouse=False, teclado=False))
            == TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO
        )

    def test_a_frase_diz_onde_ligar(self) -> None:
        """Padrão do `_reconciliar_gate_text`: dizer o que não vai acontecer
        E o caminho. Sem o "onde", o aviso vira só má notícia."""
        for frase in (
            TEXTO_DESKTOP_SEM_MOUSE,
            TEXTO_DESKTOP_SEM_TECLADO,
            TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO,
        ):
            assert "aba Navegação" in frase
            assert "Controlar o PC" in frase


class TestSemAlarmeFalso:
    """Cada `None` aqui é um aviso que NÃO pode aparecer."""

    def test_mouse_e_teclado_ligados_nao_dizem_nada(self) -> None:
        assert texto_do_desktop_sem_emulacao(_estado(mouse=True, teclado=True)) is None

    def test_no_modo_jogo_o_mouse_desligado_e_o_desenho_normal(self) -> None:
        """Em "Jogar pelo Hefesto" a exclusão mútua do daemon desliga o mouse —
        avisar ali seria acusar o produto de fazer exatamente o que deve."""
        assert (
            texto_do_desktop_sem_emulacao(
                _estado(mouse=False, teclado=True, gamepad=True)
            )
            is None
        )

    def test_no_modo_nativo_idem(self) -> None:
        assert (
            texto_do_desktop_sem_emulacao(
                _estado(mouse=False, teclado=True, native=True)
            )
            is None
        )

    def test_saindo_do_desktop_o_aviso_cala(self) -> None:
        """AGORA-E-DEPOIS-01: com pendência, a caixa mostra a ESCOLHA dela.
        Avisar sobre o modo que ela está deixando responde a pergunta errada."""
        assert (
            texto_do_desktop_sem_emulacao(
                _estado(mouse=False, teclado=True), modo_exibido="gamepad"
            )
            is None
        )

    def test_payload_sem_o_bloco_de_mouse_nao_inventa_aviso(self) -> None:
        """Daemon antigo/payload incompleto: sem informação não se acusa."""
        assert texto_do_desktop_sem_emulacao(_estado(teclado=True)) is None

    @pytest.mark.parametrize("valor", [None, "false", 0, ""])
    def test_so_o_false_literal_acende(self, valor: object) -> None:
        estado = _estado(teclado=True)
        estado["mouse_emulation"] = {"enabled": valor}
        assert texto_do_desktop_sem_emulacao(estado) is None

    def test_no_tique_da_transicao_o_aviso_espera(self) -> None:
        """O `mouse.emulation.restore` é o ÚLTIMO dos três IPCs do plano: no
        mesmo tique em que o modo virou desktop ele ainda pode estar em voo, e
        um aviso que pisca por 2 s é ruído, não informação."""
        assert (
            texto_do_desktop_sem_emulacao(
                _estado(mouse=False, teclado=True), modo_mudou_agora=True
            )
            is None
        )

    def test_daemon_desligado_nao_diz_nada(self) -> None:
        assert texto_do_desktop_sem_emulacao(None) is None


class TestOModoNaoImpoeMouse:
    """A OUTRA saída, e por que ela não foi tomada.

    Ligar o mouse ao entrar em "Controlar o PC" sobrescreveria o interruptor
    que ela desligou na aba Navegação — e *"a vontade na GUI prevalece
    sempre"* (decisão dela, 09/08) vale para o gesto do interruptor tanto
    quanto para o gesto do modo. HARM-06 já decidiu isto uma vez: restaurar a
    preferência é diferente de impor uma. Trocar de ideia é decisão DELA, e
    este teste garante que ninguém a tome por ela em silêncio.
    """

    def test_o_plano_do_desktop_restaura_e_nao_impoe(self) -> None:
        metodos = [m for m, _p in plan_mode_transition(MODE_DESKTOP)]

        assert "mouse.emulation.restore" in metodos
        assert "mouse.emulation.set" not in metodos

    def test_o_restore_continua_sem_origem(self) -> None:
        """ORIGEM-QUE-MENTE-01: restaurar preferência persistida é
        reconciliação, não gesto manual — declarar "manual" aqui carimbaria o
        lock de 30 s que protege o gesto DELA."""
        passos = dict(plan_mode_transition(MODE_DESKTOP))

        assert passos["mouse.emulation.restore"] == {}


# --- a aba: a frase chega ao widget -----------------------------------------


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers

    def __init__(self) -> None:
        self._home_installed = True
        self._home_guard = False
        self._home_offline = False
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()
        self._home_vpad_banner = _FakeWidget()
        self._home_wrapper_banner = _FakeWidget()
        self._home_shutdown_btn = _FakeWidget()
        self._home_reconciliar_btn = _FakeWidget()
        self._home_reconciliar_hint = _FakeWidget()
        # MODO-QUE-NAO-CONTROLA-01: o widget desta leva.
        self._home_desktop_aviso = _FakeWidget()


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


class TestAAbaEscreveAFrase:
    def test_o_segundo_tique_no_desktop_acende_o_aviso(self, fake_gtk: None) -> None:
        """Dois tiques de propósito: o primeiro é o da transição (o restore
        pode estar em voo), o segundo é o que fala do que ficou de pé."""
        host = _HomeStub()
        estado = _estado(mouse=False, teclado=True)

        host._render_home(estado)
        host._render_home(estado)

        assert host._home_desktop_aviso.visible is True
        assert host._home_desktop_aviso.get_text() == TEXTO_DESKTOP_SEM_MOUSE

    def test_o_tique_da_transicao_ainda_nao_fala(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(_estado(mouse=False, teclado=True, gamepad=True))
        host._render_home(_estado(mouse=False, teclado=True))

        assert host._home_desktop_aviso.visible is False

    def test_mouse_ligado_apaga_o_aviso(self, fake_gtk: None) -> None:
        host = _HomeStub()
        estado_ruim = _estado(mouse=False, teclado=True)
        host._render_home(estado_ruim)
        host._render_home(estado_ruim)

        bom = _estado(mouse=True, teclado=True)
        host._render_home(bom)

        assert host._home_desktop_aviso.visible is False

    def test_offline_apaga_o_aviso(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_desktop_aviso.visible = True  # sobra de um render anterior

        host._render_home(None)

        assert host._home_desktop_aviso.visible is False

    def test_o_aviso_nasce_invisivel(self, fake_gtk: None) -> None:
        """Sem estado nenhum não há o que avisar (o widget é montado no
        `install_home_tab` com `visible=False`); o render é quem acende."""
        host = _HomeStub()

        host._render_home(_estado(mouse=True, teclado=True))

        assert host._home_desktop_aviso.visible is False


def test_a_descricao_do_desktop_aponta_para_uma_aba_que_existe() -> None:
    """A linha VIZINHA do aviso, e ela mentia desde 28/07.

    `_MODE_DESCRIPTIONS["desktop"]` mandava para "as abas Mouse e Teclado" —
    duas abas que a janela não tem desde a PALAVRA-01, quando as duas colunas
    passaram a viver numa aba só, "Navegação". Ficou visível agora porque o
    aviso desta leva diz ONDE ligar o mouse, e duas linhas coladas não podem
    mandar a usuária para lugares diferentes.

    O teste morde nos dois lados: a frase tem de citar a aba, e a aba tem de
    existir no glade — trocar o nome da aba sem trocar a frase reprova aqui.
    """
    from pathlib import Path

    from hefesto_dualsense4unix.app.actions.home_actions import _MODE_DESCRIPTIONS

    raiz = Path(__file__).resolve().parents[2]
    glade = (raiz / "src/hefesto_dualsense4unix/gui/main.glade").read_text(
        encoding="utf-8"
    )
    descricao = _MODE_DESCRIPTIONS["desktop"]

    assert "aba Navegação" in descricao
    assert "abas Mouse e Teclado" not in descricao
    assert ">Navegação</property>" in glade, (
        "a aba mudou de nome e a descrição do modo desktop ficou apontando "
        "para um rótulo que não existe mais"
    )


def test_a_frase_do_mouse_espelha_o_gate_da_aba_navegacao() -> None:
    """As duas pontas do mesmo caminho, e elas têm de casar.

    `mouse_actions.MODE_GATE_HINT` já mandava a usuária de lá para cá ("Só dá
    para ligar o mouse em "Controlar o PC" (aba Início)"). Faltava a volta —
    e é ela que esta leva entrega.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import MODE_GATE_HINT

    assert "Controlar o PC" in MODE_GATE_HINT
    assert "aba Início" in MODE_GATE_HINT
    assert "aba Navegação" in home_actions.TEXTO_DESKTOP_SEM_MOUSE
