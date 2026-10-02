"""P8 — a aba que OFERECE o Modo Nativo não avisava que o rádio pode não dar."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p8: o aviso de rádio frágil na aba Perfis")

from typing import Any


from hefesto_dualsense4unix.app.actions import home_actions as ha
from hefesto_dualsense4unix.app.actions import profiles_actions as pa

#: Payload do `daemon.state_full` com a mesa conhecida e DOIS controles no
DOIS_NO_RADIO: dict[str, Any] = {
    "native_bt_fragil": True,
    "native_bt_fragil_controles": [2, 3],
}

SEM_SABER_QUEM: dict[str, Any] = {"native_bt_fragil": True}


class TestAFraseEAMesmaDaInicio:


    def test_a_inicio_continua_dizendo_exatamente_o_que_dizia(self) -> None:
        """O dono novo não pode mudar o banner da outra aba.

        `vpad_degradation_text` passou a delegar a decisão do rádio frágil.
        Se a extração tiver mudado o texto ou a ordem das perguntas, reprova.
        """
        assert ha.vpad_degradation_text(DOIS_NO_RADIO) == ha.texto_native_bt_fragil(
            [2, 3]
        )


class _Rotulo:
    def __init__(self) -> None:
        self.markup = ""
        self.visivel = False

    def set_markup(self, m: str) -> None:
        self.markup = m

    def set_text(self, t: str) -> None:
        self.markup = t

    def set_visible(self, v: bool) -> None:
        self.visivel = v

    def set_no_show_all(self, _v: bool) -> None:
        return None

    def set_tooltip_text(self, _t: str) -> None:
        return None


class _Seletor:
    def __init__(self, kind: str) -> None:
        self._kind = kind

    def get_active_id(self) -> str:
        return self._kind


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    def __init__(self, kind: str = "native") -> None:
        self._aviso_do_radio_fragil = _Rotulo()
        self._mode_kind_selector = _Seletor(kind)
        self._mode_gamepad_opts = None


