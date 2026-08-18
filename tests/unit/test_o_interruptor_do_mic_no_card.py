"""O interruptor do mic por BT NO CARD — a metade que só o GTK real prova.

O irmão puro deste arquivo (`test_o_interruptor_do_mic_por_bluetooth.py`) cobra
a decisão e o texto. Aqui se cobra o que ele não alcança: que o interruptor
existe **no card do controle, junto do medidor** (decisão dela, 07/08), que a
tela reflete o transporte, e que mexer nele chega à ponte de verdade.

Por que GTK real: um dublê responderia "sim, estou no card" sobre um widget que
ninguém pendurou. E a geometria desta coluna é o pixel mais disputado da aba —
o interruptor divide a LINHA do botão de mudo justamente porque numa linha
própria ele custava 30px de altura e reprovava o
`test_a_coluna_do_som_nao_e_a_mais_alta_da_faixa`.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o interruptor do mic por bluetooth, no card")

from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.widgets import controller_card as cc
from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard

MAC = "aa:bb:cc:00:11:22"


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_vivos: list[Any] = []


def _assentar(vezes: int = 6) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _entry(transporte: str) -> dict[str, Any]:
    return {
        "index": 0,
        "connected": True,
        "transport": transporte,
        "uniq": MAC,
        "battery_pct": 80,
        "audio": {"mic_mudo": False},
    }


def _card(transporte: str = "bt") -> ControllerCard:
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(900, 600)
    janela.show_all()
    _vivos.append(janela)
    card.update(_entry(transporte), {}, None)
    _assentar()
    return card


@pytest.fixture
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_in_thread` sem thread: o gesto e a resposta no mesmo instante.

    Sem isto o callback voltaria por `GLib.idle_add` e morreria sem laço
    principal — o teste veria o interruptor no meio do caminho e afirmaria
    sobre um estado que a mantenedora nunca vê.
    """

    def _direto(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            on_success(fn())
        except Exception as exc:  # pragma: no cover - o teste falha melhor assim
            if on_failure is not None:
                on_failure(exc)
            else:
                raise

    monkeypatch.setattr(ipc_bridge, "run_in_thread", _direto)


# ---------------------------------------------------------------------------
# O LUGAR — "no card do controle, junto do medidor"
# ---------------------------------------------------------------------------


def test_o_interruptor_esta_no_mesmo_bloco_do_medidor() -> None:
    """A decisão dela, lida da árvore de widgets e não de um comentário."""
    card = _card()

    bloco_do_medidor = card._mic_meter.get_parent()
    ancestrais = []
    no = card._mic_bt_switch
    while no is not None:
        ancestrais.append(no)
        no = no.get_parent()

    assert bloco_do_medidor in ancestrais, (
        "o interruptor não está no bloco do medidor: a decisão dela é 'no card "
        "do controle, junto do medidor'"
    )
    assert card._mic_bt_switch.get_visible() is True


def test_o_interruptor_divide_a_linha_com_o_botao_de_mudo() -> None:
    """Geometria medida: linha própria custava 30px e reprovava o orçamento."""
    card = _card()

    linha = card._mic_bt_switch.get_parent()
    assert card._mic_botao in linha.get_children(), (
        "o interruptor saiu da linha do botão: numa linha própria ele põe a "
        "coluna do som acima da maior vizinha da faixa"
    )


# ---------------------------------------------------------------------------
# O ESTADO — o transporte manda
# ---------------------------------------------------------------------------


def test_no_cabo_o_interruptor_aparece_apagado() -> None:
    """Apagado e VISÍVEL: sumir é indistinguível de "não tem microfone"."""
    card = _card("usb")

    assert card._mic_bt_switch.get_visible() is True
    assert card._mic_bt_switch.get_sensitive() is False
    assert "cabo" in (card._mic_bt_switch.get_tooltip_text() or "").lower()


def test_no_radio_o_interruptor_fica_clicavel() -> None:
    card = _card("bt")

    assert card._mic_bt_switch.get_sensitive() is True
    assert card._mic_bt_switch.get_active() is False


# ---------------------------------------------------------------------------
# O GESTO — e é aqui que mora a mordida
# ---------------------------------------------------------------------------


def test_ligar_o_interruptor_sobe_a_ponte_deste_controle(
    sincrono: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: com o handler desligado, o gesto dela não chega em ponte nenhuma.

    Era o estado do produto até 07/08 — a ponte pronta, o subsystem de pé e
    nenhuma linha da janela alcançando os dois.
    """
    pedidos: list[str | None] = []

    class _Ger:
        pontes: ClassVar[dict[str, Any]] = {"/dev/hidraw3": object()}

        def parar(self) -> None:
            return None

    def _falso(uniq: str | None, **_kw: Any) -> tuple[Any, str]:
        pedidos.append(uniq)
        return _Ger(), ""

    monkeypatch.setattr(cc, "ligar_ponte_bt", _falso)
    card = _card("bt")

    card._mic_bt_switch.set_active(True)
    _assentar()

    assert pedidos == [MAC], (
        "mexer no interruptor não chamou a ponte com o controle DESTE card"
    )
    assert card._mic_bt_switch.get_active() is True
    assert "Desligar" in (card._mic_bt_switch.get_tooltip_text() or "")


def test_ponte_que_nao_sobe_devolve_o_interruptor_e_diz_o_motivo(
    sincrono: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interruptor que fica ligado sem ponte é a tela mentindo por omissão."""
    monkeypatch.setattr(
        cc, "ligar_ponte_bt", lambda _u, **_k: (None, "libopus ausente")
    )
    card = _card("bt")

    card._mic_bt_switch.set_active(True)
    _assentar()

    assert card._mic_bt_switch.get_active() is False, (
        "a ponte não subiu e o interruptor ficou ligado: ela veria 'ligado' "
        "com o medidor em 'Sem sinal' para sempre"
    )
    assert "libopus" in (card._mic_bt_switch.get_tooltip_text() or "")


def test_desligar_o_interruptor_derruba_a_ponte(
    sincrono: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    parados: list[int] = []

    class _Ger:
        pontes: ClassVar[dict[str, Any]] = {"/dev/hidraw3": object()}

        def parar(self) -> None:
            parados.append(1)

    monkeypatch.setattr(cc, "ligar_ponte_bt", lambda _u, **_k: (_Ger(), ""))
    card = _card("bt")
    card._mic_bt_switch.set_active(True)
    _assentar()

    card._mic_bt_switch.set_active(False)
    _assentar()

    assert parados == [1]
    assert card._mic_bt_switch.get_active() is False


def test_tirar_o_controle_do_radio_derruba_a_ponte(
    sincrono: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ponte de pé sobre um controle que voltou ao cabo segura hidraw à toa."""
    parados: list[int] = []

    class _Ger:
        pontes: ClassVar[dict[str, Any]] = {"/dev/hidraw3": object()}

        def parar(self) -> None:
            parados.append(1)

    monkeypatch.setattr(cc, "ligar_ponte_bt", lambda _u, **_k: (_Ger(), ""))
    card = _card("bt")
    card._mic_bt_switch.set_active(True)
    _assentar()

    card.update(_entry("usb"), {}, None)
    _assentar()

    assert parados == [1]
    assert card._mic_bt_switch.get_sensitive() is False


def test_destruir_o_card_derruba_a_ponte(
    sincrono: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_rebuild_status_cards` destrói e refaz os cards a cada troca de mesa."""
    parados: list[int] = []

    class _Ger:
        pontes: ClassVar[dict[str, Any]] = {"/dev/hidraw3": object()}

        def parar(self) -> None:
            parados.append(1)

    monkeypatch.setattr(cc, "ligar_ponte_bt", lambda _u, **_k: (_Ger(), ""))
    card = _card("bt")
    card._mic_bt_switch.set_active(True)
    _assentar()

    card.destroy()
    _assentar()

    assert parados == [1], (
        "o card morreu com a ponte de pé: ela ficaria lendo o rádio sem dono, "
        "e a próxima disputaria o contador de sequência com ela"
    )
