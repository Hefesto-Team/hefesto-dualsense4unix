"""O-DESLIGADO-DE-ONTEM-01 — o produto inerte por uma decisão de ontem, em silêncio.

O QUE ELA DISSE, 10/08/2026
===========================
    *"o touchpad não tá funcionando e o giroscópio não funciona também e se tão
    no modo nativo ou hefesto dualsense, deveriam funcionar por default"*

(Citação com a acentuação normalizada — o portão de PT-BR desta casa reprova o
texto cru, e a fala dela vale pelo conteúdo.)

O QUE FOI MEDIDO na máquina dela, com o controle no cabo e 85 % de bateria::

    native_mode: False | emulacao: False | vpads vivos: 0 | perfil ativo: nenhum
    ~/.config/hefesto-dualsense4unix/gamepad_disabled.flag  ->  09/08 23:50:16

O daemon dizia o porquê a cada dois segundos, no journal:

    gamepad_multiplos_controles_adiado  controles=0  motivo=desligada_de_proposito
    last_profile_restore_pulado_perfil_de_janela  name=Pragmata

Sem gamepad virtual não há por onde o giroscópio chegar ao jogo. E o último
perfil dela é de JOGO, então não é restaurado no boot — por decisão, e a decisão
está certa: perfil de jogo entra quando o jogo abre.

O QUE **NÃO** É O DEFEITO
=========================
O opt-out ser permanente e o daemon obedecê-lo. É a R-07 (*só o gesto manual
escreve preferência em disco*) e é a regra dela mesma — *"a vontade na GUI
prevalece sempre"*. Uma automação que religasse o que a dona desligou seria pior.

Nem a tela estar errada: ela mostrava "Controlar o PC", que era a verdade.

O DEFEITO ERA O SILÊNCIO EM VOLTA
=================================
A tela dizia o QUE estava valendo e não que aquilo vinha de uma decisão de ONTEM
que continua valendo hoje. Ela passou a noite concluindo que o produto estava
quebrado — e o produto estava obedecendo.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import aviso_de_opt_out_antigo

_INERTE: dict[str, Any] = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": False},
}


def test_o_caso_dela_ganha_o_aviso() -> None:
    """A cura. Morde ao fazer a função devolver `None` sempre.

    Arranque para ver reprovar: é o estado do produto até 10/08/2026 — o
    giroscópio não chega ao jogo e nada na tela explica por quê.
    """
    texto = aviso_de_opt_out_antigo(_INERTE, opt_out=True, conectados=1)
    assert texto is not None
    assert "sessão anterior" in texto, "tem de dizer que a decisão é ANTIGA"
    assert "giroscópio" in texto, "tem de nomear o que para de funcionar"
    assert "Jogar pelo Hefesto" in texto and "Conexão Nativa" in texto, (
        "aviso sem saída é beco: as duas saídas são os rótulos da própria aba"
    )


def test_a_frase_nao_chama_a_escolha_dela_de_erro() -> None:
    """Ela desligou de propósito, e isso é um direito, não um defeito.

    A frase informa e devolve o controle; não repreende. Mesma regra das outras
    frases desta casa.
    """
    texto = (aviso_de_opt_out_antigo(_INERTE, opt_out=True, conectados=1) or "").lower()
    for proibido in ("erro", "errado", "problema", "falha", "incorreto", "esqueceu"):
        assert proibido not in texto


@pytest.mark.parametrize(
    ("estado", "opt_out", "conectados", "porque"),
    [
        (_INERTE, False, 1, "sem opt-out não há decisão antiga a explicar"),
        (
            {"native_mode": False, "gamepad_emulation": {"enabled": True}},
            True,
            1,
            "a emulação está ligada agora — o gesto novo já venceu",
        ),
        (
            {"native_mode": True, "gamepad_emulation": {"enabled": False}},
            True,
            1,
            "Conexão Nativa é escolha ATUAL dela, e ali o jogo fala direto",
        ),
        (_INERTE, True, 0, "sem controle na mesa não há nada a atravessar"),
        (None, True, 1, "sem daemon a aba já diz que está desligado"),
    ],
)
def test_o_aviso_cala_quando_nao_ha_o_que_dizer(
    estado: Any, opt_out: bool, conectados: int, porque: str
) -> None:
    """Cinco silêncios, cada um com a razão.

    Morde em cada guarda: arrancar qualquer uma põe um aviso permanente na aba —
    e aviso que aparece quando não deveria é o que se aprende a ignorar, o que
    apagaria o único caso em que ele importa.
    """
    assert aviso_de_opt_out_antigo(estado, opt_out=opt_out, conectados=conectados) is None, porque


def test_o_aviso_some_no_instante_em_que_ela_troca_de_modo() -> None:
    """É aviso de ESTADO, não pedido repetido.

    O flag no disco continua lá depois de ela escolher "Jogar pelo Hefesto" por
    um perfil (a R-07 não deixa perfil escrever preferência). Se o aviso olhasse
    só o flag, ele ficaria na tela com o gamepad de pé, chamando de inerte um
    produto que está funcionando.
    """
    ligado = {"native_mode": False, "gamepad_emulation": {"enabled": True}}
    assert aviso_de_opt_out_antigo(ligado, opt_out=True, conectados=1) is None


def test_estado_sem_a_chave_do_gamepad_ainda_avisa() -> None:
    """Daemon antigo, ou payload sem a seção: a ausência não é "ligado".

    Errar aqui para o lado de calar seria voltar ao defeito; errar para o lado
    de avisar custa uma linha a mais numa tela que ela pode ler e ignorar.
    """
    assert aviso_de_opt_out_antigo({"native_mode": False}, opt_out=True, conectados=1)
