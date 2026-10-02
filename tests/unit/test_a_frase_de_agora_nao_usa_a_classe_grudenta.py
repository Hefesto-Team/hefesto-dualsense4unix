"""A frase *"na frente agora"* não pode nomear um jogo que já fechou."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.daemon_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    descrever_deteccao_de_janela,
)

VENDO_SEM_SABER_QUAL = {
    "window_detect_backend": "xlib",
    "window_detect_seeing": True,
    "window_detect_current_class": "unknown",
    "window_detect_last_class": "pragmata.exe",
}


class TestAClasseGrudentaNaoEntraNaFraseDeAgora:
    def test_a_janela_sem_classe_nao_vira_o_jogo_de_ontem(self) -> None:
        frase = descrever_deteccao_de_janela(VENDO_SEM_SABER_QUAL)
        assert "funcionando" in frase
        assert "pragmata.exe" not in frase, (
            "a frase diz `na frente agora` e nomeou um jogo que veio do campo "
            "STICKY `window_detect_last_class` — o jogo pode ter fechado há "
            "horas. Sem classe de agora, a frase fica sem o parêntese."
        )
        assert "na frente agora" not in frase

    def test_a_classe_vazia_tambem_nao_recua(self) -> None:
        estado = dict(VENDO_SEM_SABER_QUAL, window_detect_current_class="")
        assert "pragmata.exe" not in descrever_deteccao_de_janela(estado)

    def test_a_classe_ausente_tambem_nao_recua(self) -> None:
        estado = dict(VENDO_SEM_SABER_QUAL)
        del estado["window_detect_current_class"]
        assert "pragmata.exe" not in descrever_deteccao_de_janela(estado)

    def test_a_classe_de_agora_continua_aparecendo(self) -> None:
        """A cura não pode ter apagado o parêntese de quem tem o dado."""
        estado = dict(VENDO_SEM_SABER_QUAL, window_detect_current_class="steam")
        frase = descrever_deteccao_de_janela(estado)
        assert "na frente agora: steam" in frase

    def test_o_docstring_continua_avisando_que_o_last_e_grudento(self) -> None:
        """Se alguém apagar o aviso, o próximo recuo nasce sem contradição"""
        assert "sticky" in (descrever_deteccao_de_janela.__doc__ or "")


class TestAAbaNovaSegueAMesmaRegra:
    def test_a_aba_09_nao_nomeia_o_jogo_de_ontem(self) -> None:
        from hefesto_dualsense4unix.interface.pacotes.a09_sistema import (
            _quem_esta_na_frente,
        )

        assert _quem_esta_na_frente(VENDO_SEM_SABER_QUAL) == ""

    def test_a_aba_09_continua_nomeando_quem_tem_o_dado(self) -> None:
        from hefesto_dualsense4unix.interface.pacotes.a09_sistema import (
            _quem_esta_na_frente,
        )

        estado = dict(VENDO_SEM_SABER_QUAL, window_detect_current_class="steam")
        assert _quem_esta_na_frente(estado) == "steam"

    def test_sem_ver_continua_calada(self) -> None:
        from hefesto_dualsense4unix.interface.pacotes.a09_sistema import (
            _quem_esta_na_frente,
        )

        estado = dict(VENDO_SEM_SABER_QUAL, window_detect_seeing=False)
        assert _quem_esta_na_frente(estado) == ""
