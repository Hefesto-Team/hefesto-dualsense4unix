"""EMULACAO-UM-DONO-SO-01/E13 — os buracos de rede da aba Emulação."""
from __future__ import annotations

import sys
from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    EmulationActionsMixin as Mixin,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import DEFAULT_BUFFER_MS


class _RotuloFalso:
    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, t: str) -> None:
        self.texto = t

    def set_markup(self, t: str) -> None:
        self.texto = t


class _Aba(Mixin):
    """A aba com um dicionário de rótulos no lugar do `Gtk.Builder`."""

    def __init__(self) -> None:
        self.rotulos: dict[str, _RotuloFalso] = {}
        self.toasts: list[str] = []

    def _get(self, ident: str) -> Any:
        return self.rotulos.setdefault(ident, _RotuloFalso())

    def _toast_emulation(self, msg: str) -> None:
        self.toasts.append(msg)


def test_sem_bloco_hotkey_o_cartao_diz_padrao_em_vez_de_afirmar_numero() -> None:
    """Sem estado, a tela não finge conhecer o estado."""
    aba = _Aba()
    aba._sync_hotkey_card(None)
    assert aba.rotulos["emulation_combo_buffer_label"].texto == (
        f"{DEFAULT_BUFFER_MS} (padrão)"
    )
    assert aba.rotulos["emulation_passthrough_label"].texto == "Não (padrão)"


@pytest.mark.parametrize("estado", [None, {}, {"hotkey": None}, {"hotkey": "x"}, 7])
def test_todo_estado_ilegivel_cai_no_padrao_e_nao_estoura(estado: object) -> None:
    """O `state_full` chega de um daemon que pode ser mais velho, ou não chegar."""
    aba = _Aba()
    aba._sync_hotkey_card(estado)
    assert "(padrão)" in aba.rotulos["emulation_combo_buffer_label"].texto


def test_com_bloco_hotkey_o_cartao_mostra_o_valor_efetivo() -> None:
    """O contrapeso: sem ele, "curar" viraria dizer (padrão) para sempre."""
    aba = _Aba()
    aba._sync_hotkey_card({"hotkey": {"buffer_ms": 220, "passthrough_in_emulation": True}})
    assert aba.rotulos["emulation_combo_buffer_label"].texto == "220"
    assert aba.rotulos["emulation_passthrough_label"].texto == "Sim"


def test_o_buffer_booleano_nao_passa_por_numero() -> None:
    """`bool` é subclasse de `int`: sem a guarda, `True` viraria "True" na tela."""
    aba = _Aba()
    aba._sync_hotkey_card({"hotkey": {"buffer_ms": True}})
    assert "(padrão)" in aba.rotulos["emulation_combo_buffer_label"].texto


def test_o_cartao_uinput_mostra_o_vidpid_da_mascara_viva() -> None:
    """ARRANQUE A CURA: devolva a constante de Xbox cravada e este caso REPROVA."""
    aba = _Aba()
    aba._sync_uinput_card("dualsense")
    vid = aba.rotulos["emulation_vidpid_label"].texto
    assert vid.startswith("054C:0DF2"), vid
    assert "DualSense" in vid, vid
    assert "Xbox" not in vid, vid


def test_a_mascara_xbox_mostra_o_vidpid_de_xbox() -> None:
    aba = _Aba()
    aba._sync_uinput_card("xbox")
    vid = aba.rotulos["emulation_vidpid_label"].texto
    assert "Xbox 360" in vid, vid
    assert "054C" not in vid, vid


@pytest.mark.parametrize("desligado", [None, "off", "", "flavor-que-nao-existe"])
def test_com_o_gamepad_virtual_desligado_nao_sobra_vidpid_de_ninguem(
    desligado: str | None,
) -> None:
    """BUG-EMULATION-UINPUT-CARD-STALE-02: o cartão não pode ficar com o de antes."""
    aba = _Aba()
    aba._sync_uinput_card("xbox")
    aba._sync_uinput_card(desligado)
    assert aba.rotulos["emulation_vidpid_label"].texto == "—"
    assert "desligado" in aba.rotulos["emulation_device_name_label"].texto


def test_testar_o_controle_virtual_sem_uinput_avisa_e_nao_cria_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem o módulo, o botão avisa — e NÃO chega a instanciar nada."""
    criados: list[str] = []

    class _Espia:
        """Dublê COMPLETO de propósito."""

        def __init__(self, *a: object, **k: object) -> None:
            criados.append("instanciou")

        def start(self) -> bool:
            return True

        def stop(self) -> None:
            return None

    import hefesto_dualsense4unix.integrations.uinput_gamepad as ug

    monkeypatch.setattr(ug, "UinputGamepad", _Espia)
    monkeypatch.setitem(sys.modules, "uinput", None)

    aba = _Aba()
    aba.on_emulation_test_device(None)  # type: ignore[arg-type]

    assert aba.toasts, "o botão ficou mudo sem o gamepad virtual disponível"
    assert not criados, f"criou nó mesmo sem uinput: {criados}"
    aviso = aba.toasts[-1]
    assert "reinstale" in aviso.lower(), aviso
