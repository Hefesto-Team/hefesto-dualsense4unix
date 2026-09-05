"""A frase *"na frente agora"* não pode nomear um jogo que já fechou.

MEDIDO EM 05/09/2026, no retrato das abas: o cartão da aba Sistema dizia
*"Trocar de perfil ao abrir o jogo: funcionando (na frente agora:
pragmata.exe)"* com a máquina sem um único processo de Steam, Proton ou Wine.

A CAUSA estava escrita no próprio docstring da função, uma linha acima do
defeito: `window_detect_last_class` é **sticky** — guarda a última classe vista
e nunca se apaga. O código recuava para ele quando a classe de AGORA vinha
`unknown`, e assim uma frase que diz "agora" passava a publicar passado.

É a mesma família do que ela pegou em 03/09, quando o `doctor` contava eventos
de 24 dias atrás no presente. A regra que sobra: **campo grudento não entra em
frase de presente.**
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    descrever_deteccao_de_janela,
)

#: O estado que o daemon dela publicava no instante do retrato: vendo uma
#: janela, sem conseguir classificá-la, e com o último jogo ainda no `last`.
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
        """Se alguém apagar o aviso, o próximo recuo nasce sem contradição
        visível — e foi o aviso ao lado do defeito que revelou a causa."""
        assert "sticky" in (descrever_deteccao_de_janela.__doc__ or "")


#: A INTERFACE NOVA TINHA O MESMO RECUO, e o docstring dela dizia, com todas as
#: letras, que seguia *"a MESMA regra da GTK"* — então curar uma só deixaria as
#: duas telas discordando sobre o mesmo fato.
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
