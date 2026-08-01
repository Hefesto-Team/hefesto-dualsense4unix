"""MASCARA-CUSTO-01 — a máscara Xbox apaga giroscópio e touchpad, e a tela diz.

A pergunta dela, literal, em 01/08/2026: *"não sei se agora o alto-falante,
giroscópio, microfone e touchpad — todas as features — na hora de jogar um jogo
na Steam se elas vão estar funcionando. Elas precisam funcionar."*

A auditoria daquele dia respondeu com número, e a resposta tinha duas metades:

* **microfone e alto-falante** não passam pelo gamepad virtual — são PipeWire,
  e valem em qualquer máscara. Nada a avisar;
* **giroscópio e touchpad** só chegam ao jogo pelo espelho do gamepad virtual,
  e o espelho só existe no backend `uhid`. `integrations/virtual_pad.py` recusa
  o uhid para todo sabor que não seja `dualsense`, e o vpad `uinput` — que é o
  que sobra na máscara Xbox — declara 8 eixos e 11 botões: **não há onde pôr
  IMU nem dedo**. Não é defeito, é a API do controle de Xbox.

O que faltava não era código de sensor: era ETIQUETA DE PREÇO. Seis dos oito
perfis de jogo desta casa pediam máscara Xbox, e nada na tela dizia o que se
perdia com isso — nem no momento do gesto, nem depois.

Este arquivo trava a frase e trava o que ela NÃO pode dizer.
"""

from __future__ import annotations

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
    texto_do_custo_da_mascara,
)


def test_a_mascara_xbox_diz_o_que_o_jogo_perde() -> None:
    """A mordida: sem a frase, a escolha volta a ser cega.

    Um teste que só afirmasse `texto != ""` passaria com qualquer frase,
    inclusive uma que não nomeasse o que se perde. Por isso as duas palavras
    são exigidas pelo nome.
    """
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
    """Microfone e alto-falante NÃO passam pelo gamepad — não podem entrar.

    Medido na auditoria de 01/08: nenhuma linha de `virtual_pad.py`,
    `subsystems/gamepad.py`, `launch_env.py` ou `steam_launcher.py` toca
    PipeWire, e o `EVIOCGRAB` age no nó evdev, não na placa de som USB. Os dois
    valem igual nas duas máscaras.

    Listá-los como perda seria assustar sem motivo e mandar caçar problema no
    lugar errado — que é o defeito que a APLICAR-VERDADE-01 existiu para
    eliminar, na mesma janela.
    """
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
