"""MASCARA-CUSTO-01 — a máscara Xbox apaga giroscópio e touchpad, e a tela diz."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_mascara_diz_o_que_custa: importa código da janela GTK")

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
    texto_do_custo_da_mascara,
)


def test_a_mascara_xbox_diz_o_que_o_jogo_perde() -> None:
    """A mordida: sem a frase, a escolha volta a ser cega."""
    texto = texto_do_custo_da_mascara("xbox")

    assert texto, "a máscara Xbox tem preço e a tela não o disse"
    assert "giroscópio" in texto, (
        "o giroscópio é uma das duas coisas que somem, e a frase tem de o "
        "nomear — quem joga com mira por movimento decide por essa palavra"
    )
    assert "touchpad" in texto, (
        "o touchpad é a outra: em jogo que o usa como botão (mapa, inventário, "
        "placar), o botão simplesmente não responde"
    )


def test_a_mascara_dualsense_nao_inventa_aviso() -> None:
    """Nada se perde com DualSense, então não há o que dizer.

    Um aviso permanente vira ruído e some da vista — a frase existe para
    aparecer quando importa.
    """
    assert texto_do_custo_da_mascara("dualsense") == ""


def test_payload_incompleto_nao_vira_aviso() -> None:
    """Sem saber a máscara, a janela não afirma nada.

    Esta é a mesma família de erro que a AUTO-01.3 removeu daqui: um
    ``or "xbox"`` fazia a aba MOSTRAR Xbox por causa de um payload incompleto
    e, no clique seguinte, MANDAR Xbox — trocando a máscara do daemon. Um
    aviso inventado a partir de campo ausente é a versão em prosa do mesmo
    defeito: ela leria "seu jogo não tem giroscópio" sobre um controle que
    está com a máscara DualSense.
    """
    for ausente in (None, "", "desconhecido", 0, [], {}):
        assert texto_do_custo_da_mascara(ausente) == "", (
            f"{ausente!r} virou aviso: a janela afirmou o que não sabe"
        )


def test_a_frase_nao_promete_perda_que_nao_existe() -> None:
    """Microfone e alto-falante NÃO passam pelo gamepad — não podem entrar."""
    texto = TEXTO_CUSTO_MASCARA_XBOX.lower()

    assert "vibra" in texto, (
        "a frase tem de dizer que a vibração CONTINUA: ela funciona nas duas "
        "máscaras, e quem lê 'perdi coisas' presume que perdeu essa também"
    )
    for continua in ("microfone", "alto-falante"):
        assert continua in texto, (
            f"o {continua} continua funcionando na máscara Xbox e a frase tem "
            "de dizer isso — ela é a resposta à pergunta dela, que citou os "
            "quatro recursos juntos"
        )
