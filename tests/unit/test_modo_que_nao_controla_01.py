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
2. o plano do modo desktop passa pela porta do arranjo, e é o DAEMON quem
   decide o mouse ali.

NOTA DATADA — 29/09/2026 (O-MOUSE-SEGUE-A-NAVEGACAO-01). A segunda metade
dizia *"se alguém trocar a cura pela outra saída (o modo LIGAR o mouse), este
teste reprova e a decisão volta para ela"*. A pergunta foi à sessão dos desenhos
com a letra dela de 09/08 junto, e foi decidida em 29/09 pelo padrão dela, com
ela dormindo: D-2909-A-NAVEGACAO-LIGA-O-MOUSE — entrar na Navegação liga o
mouse, pelo chip e pelo PS + R3. Ela pode desfazer. A razão está na classe
`TestAEntradaLigaOMouse`.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_modo_que_nao_controla_01: importa código da janela GTK")

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_DESKTOP_SEM_MOUSE,
    TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO,
    TEXTO_DESKTOP_SEM_TECLADO,
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
        """Com os dois desligados o modo não faz NADA — dizer só do mouse"""
        assert (
            texto_do_desktop_sem_emulacao(_estado(mouse=False, teclado=False))
            == TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO
        )

    def test_a_frase_diz_onde_ligar(self) -> None:
        """Padrão do `_reconciliar_gate_text`: dizer o que não vai acontecer"""
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
        """Em "Jogar pelo Hefesto" a exclusão mútua do daemon desliga o mouse —"""
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
        """AGORA-E-DEPOIS-01: com pendência, a caixa mostra a ESCOLHA dela."""
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


class TestAEntradaLigaOMouse:
    """A saída que 09/08 não tomou, e por que 29/09 a tomou."""

    def test_o_plano_do_desktop_passa_pelo_arranjo(self) -> None:
        """O plano entra pelo arranjo, que é quem liga o mouse no daemon.

        POINT-AND-CLICK-01 (17/09/2026): o terceiro passo era
        `mouse.emulation.restore`, que lê a flag de sessão da MÁQUINA. É
        `desktop.arranjo.apply`, que lê o PERFIL. O plano não chama o
        `mouse.emulation.set` direto: um segundo escritor do mouse na entrada
        seria a regra morando em dois lugares.
        """
        metodos = [m for m, _p in plan_mode_transition(MODE_DESKTOP)]

        assert "desktop.arranjo.apply" in metodos
        assert "mouse.emulation.set" not in metodos, (
            "o plano passou a ligar o mouse por fora do arranjo — dois donos do "
            "mouse na entrada da Navegação")

    def test_o_chip_nao_manda_parametro_que_o_ps_r3_nao_manda(self) -> None:
        """As duas portas pedem o mesmo: o `forcar_mouse` saiu com o socorro."""
        passos = dict(plan_mode_transition(MODE_DESKTOP))

        assert "forcar_mouse" not in passos["desktop.arranjo.apply"]

    def test_o_arranjo_declara_que_e_gesto_dela(self) -> None:
        """E aqui o contrapeso do ORIGEM-QUE-MENTE-01 mudou de lado, medido.

        O `mouse.emulation.restore` NÃO levava `origin`, e era certo: restaurar
        preferência persistida é reconciliação por definição. O arranjo é outra
        coisa — ele é o clique dela, e o `origin="manual"` é o que FURA o lock
        de 30 s de `apply_profile_mouse` para que o modo que ela acabou de pedir
        não seja adiado por um toggle de segundos antes.

        NOTA DATADA — 29/09/2026 (O-MOUSE-SEGUE-A-NAVEGACAO-01): a entrada
        passou a ligar o mouse com `origin="manual"` quando o pedido é à mão,
        como o PS + R3 já fazia; o carimbo é do gesto dela de entrar no modo.
        """
        passos = dict(plan_mode_transition(MODE_DESKTOP))

        assert passos["desktop.arranjo.apply"] == {"origin": "manual"}


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


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


