"""BG-02, lado da janela — a aba para de adivinhar se o mouse virtual subiu."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a aba do mouse sabe do device")

import os
import sys
import types
from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import mouse_actions as ma
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    MouseActionsMixin,
)
from hefesto_dualsense4unix.daemon.lifecycle import CALADA_VPAD_SUSPENSO

PRONTO = "Pronto para usar como mouse"
SEM_PERMISSAO = "está sem permissão"
NAO_ESTA_PRONTO = "ainda não está pronto"
FALTA_COMPONENTE = "Falta um componente"


class _FakeLabel:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _Aba(MouseActionsMixin):
    def __init__(self) -> None:
        self.rotulo = _FakeLabel()

    def _get(self, widget_id: str) -> Any:
        return self.rotulo if widget_id == "mouse_uinput_status_label" else None


def _sonda_local(
    monkeypatch: pytest.MonkeyPatch,
    *,
    com_uinput: bool = True,
    existe: bool = True,
    gravavel: bool = True,
) -> None:
    """Finge a máquina que a JANELA enxerga — módulo, nó e permissão."""
    monkeypatch.setitem(
        sys.modules, "uinput", types.ModuleType("uinput") if com_uinput else None
    )
    exists_real, access_real = os.path.exists, os.access
    monkeypatch.setattr(
        os.path,
        "exists",
        lambda p: existe if p == ma.UINPUT_DEV else exists_real(p),
    )
    monkeypatch.setattr(
        os,
        "access",
        lambda p, m: gravavel if p == ma.UINPUT_DEV else access_real(p, m),
    )


def test_a_sonda_dublada_sabe_recusar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua da régua: sem isto, todo teste abaixo mediria a máquina do CI."""
    _sonda_local(monkeypatch, com_uinput=False, existe=False, gravavel=False)
    with pytest.raises(ImportError):
        import uinput  # noqa: F401
    assert os.path.exists(ma.UINPUT_DEV) is False
    assert os.access(ma.UINPUT_DEV, os.W_OK) is False
    assert os.path.exists(__file__) is True


@pytest.mark.parametrize(
    ("bloco", "esperado"),
    [
        ({"device_ativo": True, "bloqueio": None}, True),
        ({"device_ativo": True, "bloqueio": "modo_jogo"}, True),
        ({"device_ativo": False, "bloqueio": "sem_device"}, False),
        ({"device_ativo": False, "bloqueio": "desligada"}, None),
        ({"device_ativo": False, "bloqueio": CALADA_VPAD_SUSPENSO}, None),
        ({"enabled": True, "speed": 6, "scroll_speed": 1}, None),
        ({}, None),
    ],
)
def test_o_tri_estado_do_mouse_virtual(bloco: dict[str, Any], esperado: Any) -> None:
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": bloco})
    assert aba._mouse_virtual_no_ar is esperado


def test_sem_resposta_a_aba_volta_a_nao_saber() -> None:
    """Guardar o último valor bom seria afirmar sobre quem não respondeu."""
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})
    assert aba._mouse_virtual_no_ar is True
    aba._anotar_mouse_virtual(None)
    assert aba._mouse_virtual_no_ar is None


def test_o_tri_estado_e_por_instancia() -> None:
    """Duas janelas no mesmo processo (a suíte monta várias) não se misturam."""
    assert MouseActionsMixin._mouse_virtual_no_ar is None
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})
    assert MouseActionsMixin._mouse_virtual_no_ar is None


def test_a_mordida_o_device_fora_do_ar_desmente_a_sonda_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permissão em ordem, interruptor em pé, cursor parado: o rótulo avisa."""
    _sonda_local(monkeypatch)
    aba = _Aba()

    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "sem_device"}}
    )

    assert NAO_ESTA_PRONTO in aba.rotulo.markup, (
        f"o rótulo diz {aba.rotulo.markup!r} com o device fora do ar — a aba "
        "voltou a adivinhar pela sonda local em vez de ouvir quem abre o device"
    )
    assert PRONTO not in aba.rotulo.markup


def test_no_flatpak_o_daemon_desmente_o_alarme_da_sonda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O erro no outro sentido: sandbox sem `/dev/uinput`, device VIVO."""
    _sonda_local(monkeypatch, existe=True, gravavel=False)
    aba = _Aba()

    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})

    assert PRONTO in aba.rotulo.markup
    assert SEM_PERMISSAO not in aba.rotulo.markup


def test_desligada_nao_manda_ninguem_aplicar_correcoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O alarme falso que o tri-estado existe para não dar."""
    _sonda_local(monkeypatch)
    aba = _Aba()

    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "desligada"}}
    )
    aba._refresh_mouse_view()

    assert PRONTO in aba.rotulo.markup
    assert "Aplicar correções" not in aba.rotulo.markup


@pytest.mark.parametrize(
    ("com_uinput", "existe", "gravavel", "trecho"),
    [
        (True, True, True, PRONTO),
        (True, True, False, SEM_PERMISSAO),
        (True, False, False, NAO_ESTA_PRONTO),
        (False, True, True, FALTA_COMPONENTE),
    ],
)
def test_sem_resposta_do_daemon_a_sonda_local_manda_como_sempre(
    monkeypatch: pytest.MonkeyPatch,
    com_uinput: bool,
    existe: bool,
    gravavel: bool,
    trecho: str,
) -> None:
    """Os quatro desfechos históricos do rótulo, intactos."""
    _sonda_local(monkeypatch, com_uinput=com_uinput, existe=existe, gravavel=gravavel)
    aba = _Aba()
    assert aba._mouse_virtual_no_ar is None
    aba._refresh_mouse_view()
    assert trecho in aba.rotulo.markup


def test_o_modulo_ausente_vence_o_device_fora_do_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Falta um componente" manda rodar o install; "não está pronto" não."""
    _sonda_local(monkeypatch, com_uinput=False)
    aba = _Aba()
    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "sem_device"}}
    )
    assert FALTA_COMPONENTE in aba.rotulo.markup


class _AbaViva(_Aba):
    """A aba com o mínimo que `_refresh_mouse_from_daemon_async` toca."""

    def __init__(self) -> None:
        super().__init__()
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()


def test_a_mordida_o_estado_vivo_chega_a_aba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fiação: sem a chamada em `_refresh_mouse_from_daemon_async`, o campo"""
    from hefesto_dualsense4unix.app import ipc_bridge

    _sonda_local(monkeypatch)
    estado = {
        "mouse_emulation": {
            "enabled": True,
            "speed": 6,
            "scroll_speed": 1,
            "device_ativo": False,
            "despachando": False,
            "bloqueio": "sem_device",
        }
    }
    monkeypatch.setattr(
        ipc_bridge,
        "call_async",
        lambda method, params=None, on_success=None, on_failure=None, **_kw: (
            on_success(estado)
        ),
    )

    aba = _AbaViva()
    aba.draft = aba.draft.model_copy(
        update={"mouse": aba.draft.mouse.model_copy(update={"dirty": True})}
    )
    aba._refresh_mouse_from_daemon_async()

    assert aba._mouse_virtual_no_ar is False, (
        "o `state_full` trouxe o motivo e a aba não o leu — a fiação do tique "
        "sumiu, ou está depois dos `return` do callback"
    )
    assert NAO_ESTA_PRONTO in aba.rotulo.markup


def test_todo_motivo_que_o_daemon_emite_tem_traducao() -> None:
    """A régua contra a divergência silenciosa entre daemon e janela.

    `_bloqueio_da_emulacao_de_desktop` emite estes quatro códigos, e são os
    quatro que a tabela traduz. Um código novo do daemon sem linha aqui sai na
    tela como texto cru (`frase_da_recusa_do_mouse` é honesta nesse caso) — o
    que este teste impede é que ele sirva DUAS vezes, com dois vocabulários.
    """
    do_daemon = {"desligada", "sem_device", "modo_jogo", CALADA_VPAD_SUSPENSO}
    assert do_daemon == set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES), (
        "o vocabulário do daemon e o da janela divergiram: "
        f"{do_daemon ^ set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES)}"
    )


