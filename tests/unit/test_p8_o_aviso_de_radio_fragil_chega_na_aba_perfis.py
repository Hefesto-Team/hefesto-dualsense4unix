"""P8 — a aba que OFERECE o Modo Nativo não avisava que o rádio pode não dar.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/8 (24/08/2026), medido:

    $ grep -rln "native_bt_fragil" src/hefesto_dualsense4unix/app/
    src/hefesto_dualsense4unix/app/actions/home_actions.py

**Um arquivo só.** E "Conexão Nativa (Sony)" é um dos quatro botões do editor
de perfil — inclusive num perfil de co-op, onde Modo Nativo com dois ou mais
controles no rádio é exatamente a pergunta que ninguém mediu (§6 da sprint).

**A asserção central deste arquivo é de IGUALDADE, não de conteúdo.** A frase
tem de ser a MESMA da aba Início, byte a byte: uma segunda redação para o mesmo
fato é como esta casa ganhou os oito pares da F5, e oito estão sendo curados
nesta mesma noite. Por isso `texto_do_radio_fragil` virou o dono único e as
duas abas o chamam — se alguém reescrever a frase aqui, os testes abaixo
reprovam.

**O gatilho é próprio daqui, e é de propósito:** fora do Modo Nativo o editor
cala. O aviso fala do modo que ela está ESCOLHENDO, não do que o sistema está
fazendo agora — esse já tem banner na Início, e repetir os dois na mesma janela
é ruído, não redundância.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions as ha
from hefesto_dualsense4unix.app.actions import profiles_actions as pa

#: Payload do `daemon.state_full` com a mesa conhecida e DOIS controles no
#: rádio sob Modo Nativo — o caso que nomeia quem está frágil.
DOIS_NO_RADIO: dict[str, Any] = {
    "native_bt_fragil": True,
    "native_bt_fragil_controles": [2, 3],
}

#: E o payload do daemon VELHO, que sabe dizer que há fragilidade e não sabe
#: dizer de quem (install editable deixa os dois convivendo).
SEM_SABER_QUEM: dict[str, Any] = {"native_bt_fragil": True}


class TestAFraseEAMesmaDaInicio:
    def test_no_modo_nativo_a_frase_e_identica_a_da_aba_inicio(self) -> None:
        """MORDE o reuso: semelhante não serve, tem de ser a mesma string."""
        do_editor = pa.frase_do_radio_fragil_no_modo("native", DOIS_NO_RADIO)
        da_inicio = ha.texto_native_bt_fragil([2, 3])
        assert do_editor == da_inicio

    def test_e_ela_nomeia_os_controles_do_radio(self) -> None:
        frase = pa.frase_do_radio_fragil_no_modo("native", DOIS_NO_RADIO)
        assert frase is not None
        assert "2" in frase and "3" in frase

    def test_daemon_que_nao_sabe_quem_ainda_acende_o_generico(self) -> None:
        """Não saber QUEM não pode virar não avisar."""
        do_editor = pa.frase_do_radio_fragil_no_modo("native", SEM_SABER_QUEM)
        assert do_editor == ha.NATIVE_BT_FRAGIL_TEXT

    def test_a_inicio_continua_dizendo_exatamente_o_que_dizia(self) -> None:
        """O dono novo não pode mudar o banner da outra aba.

        `vpad_degradation_text` passou a delegar a decisão do rádio frágil.
        Se a extração tiver mudado o texto ou a ordem das perguntas, reprova.
        """
        assert ha.vpad_degradation_text(DOIS_NO_RADIO) == ha.texto_native_bt_fragil(
            [2, 3]
        )


class TestForaDoModoNativoOEditorCala:
    @pytest.mark.parametrize("kind", ["none", "desktop", "gamepad"])
    def test_os_outros_tres_modos_nao_dizem_nada(self, kind: str) -> None:
        """MORDE o gatilho: o aviso em todo modo é ruído em três telas de quatro."""
        assert pa.frase_do_radio_fragil_no_modo(kind, DOIS_NO_RADIO) is None

    def test_radio_saudavel_no_modo_nativo_nao_diz_nada(self) -> None:
        assert (
            pa.frase_do_radio_fragil_no_modo("native", {"native_bt_fragil": False})
            is None
        )

    def test_daemon_calado_nao_diz_nada(self) -> None:
        """Sem resposta o cache é `None` — e `None` é silêncio, não "está ok"."""
        assert pa.frase_do_radio_fragil_no_modo("native", None) is None


# ---------------------------------------------------------------------------
# A costura: a linha chega ao rótulo da seção "Modo"
# ---------------------------------------------------------------------------


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


class TestALinhaChegaNaSecaoModo:
    def test_escolher_o_nativo_com_radio_fragil_acende_a_linha(self) -> None:
        """MORDE a costura: a frase certa e o rótulo mudo não curam nada."""
        aba = _Aba("native")
        aba._estado_do_radio = DOIS_NO_RADIO

        aba._sincronizar_aviso_do_radio("native")

        assert aba._aviso_do_radio_fragil.visivel is True
        assert "limite do SDL" in aba._aviso_do_radio_fragil.markup

    def test_sair_do_nativo_apaga_a_linha(self) -> None:
        aba = _Aba("native")
        aba._estado_do_radio = DOIS_NO_RADIO
        aba._sincronizar_aviso_do_radio("native")

        aba._sincronizar_aviso_do_radio("gamepad")

        assert aba._aviso_do_radio_fragil.visivel is False
        assert aba._aviso_do_radio_fragil.markup == ""

    def test_a_resposta_do_daemon_repinta_a_linha_sozinha(self) -> None:
        """Ela escolhe o modo, o daemon responde depois — e a linha acende."""
        aba = _Aba("native")

        assert aba._ao_chegar_o_estado_do_radio(DOIS_NO_RADIO) is False

        assert aba._aviso_do_radio_fragil.visivel is True

    def test_resposta_estranha_nao_apaga_o_que_ja_se_sabia(self) -> None:
        aba = _Aba("native")
        aba._estado_do_radio = DOIS_NO_RADIO

        aba._ao_chegar_o_estado_do_radio(None)

        assert aba._estado_do_radio == DOIS_NO_RADIO

    def test_a_pergunta_vai_ao_state_full_e_so_no_modo_nativo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEDIDO: `native_bt_fragil` mora no `state_full`, não no `status`.

        E a pergunta só sai quando ela escolhe o Modo Nativo — um poller a mais
        nesta janela seria custo permanente por uma linha que quase nunca
        acende.
        """
        pedidos: list[str] = []
        monkeypatch.setattr(
            pa,
            "call_async",
            lambda method, params=None, on_success=None, on_failure=None,
            **_kw: pedidos.append(method),
        )
        aba = _Aba("native")

        aba._on_mode_kind_changed(_Seletor("gamepad"))
        assert pedidos == [], "perguntou fora do Modo Nativo"

        aba._on_mode_kind_changed(_Seletor("native"))
        assert pedidos == ["daemon.state_full"]

    def test_sem_o_rotulo_nada_estoura(self) -> None:
        """Glade antigo, seção não montada: o editor segue funcional."""
        aba = _Aba("native")
        aba._aviso_do_radio_fragil = None  # type: ignore[assignment]
        aba._sincronizar_aviso_do_radio("native")
