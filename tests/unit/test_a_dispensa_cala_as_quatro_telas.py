"""Ela dispensa o aviso do jogo UMA vez, e as quatro telas calam.

Medido em 05/09/2026: ela clicava "Não perguntar para este jogo" na aba
Lançadores e **três outras telas continuavam acusando** — a Início, a Status e a
coluna Atenção da aba Jogar (`app/actions/jogar/painel.py:649`). As três
chamavam `wrapper_banner_text` direto, que só olha
`gamepad_emulation.wrapper_used` e não consulta lista nenhuma.

A decisão dela no mesmo dia (pergunta `07-Q3`): *"as duas recusas calam tudo"*.
E a `a07_lancadores.calados` já dizia, por escrito, que a conta precisava de um
dono para a outra metade não a redigitar:

    "ELA É PÚBLICA E TEM NOME PRÓPRIO porque a segunda tela precisa dela. (…)
     Está relatado como trabalho de fora desta aba."

A cura cobre TODOS os chamadores, que é a regra desta casa: nasceu
`home_actions.aviso_do_wrapper`, e as telas passaram a chamá-lo.
`wrapper_banner_text` continua puro e continua existindo — ele responde "há jogo
sem wrapper agora?"; o novo responde "há algo a DIZER a ela sobre isso?".
"""
from __future__ import annotations


from hefesto_dualsense4unix.app.actions import home_actions as ha

COM_JOGO_SEM_WRAPPER = {
    "gamepad_emulation": {"wrapper_used": False},
    "window_detect_current_class": "steam_app_1086940",
}


def test_o_aviso_aparece_quando_ela_nao_respondeu(monkeypatch):
    monkeypatch.setattr(ha, "ela_ja_respondeu_sobre", lambda _a: False)
    assert ha.aviso_do_wrapper(COM_JOGO_SEM_WRAPPER) == ha.WRAPPER_MISSING_TEXT


def test_o_aviso_cala_quando_ela_ja_respondeu(monkeypatch):
    monkeypatch.setattr(ha, "ela_ja_respondeu_sobre", lambda _a: True)
    assert ha.aviso_do_wrapper(COM_JOGO_SEM_WRAPPER) is None, (
        "ela dispensou o jogo e a tela continuou acusando"
    )


def test_sem_jogo_aberto_nao_ha_o_que_calar():
    assert ha.aviso_do_wrapper({"gamepad_emulation": {"wrapper_used": True}}) is None
    assert ha.aviso_do_wrapper({}) is None
    assert ha.aviso_do_wrapper(None) is None


def test_a_pergunta_pura_continua_existindo_e_pura():
    """O dono antigo não foi apagado: ele responde a OUTRA pergunta."""
    assert ha.wrapper_banner_text(COM_JOGO_SEM_WRAPPER) == ha.WRAPPER_MISSING_TEXT


def test_o_appid_sai_da_janela_em_foco():
    assert ha.appid_do_jogo_em_foco(COM_JOGO_SEM_WRAPPER) == "1086940"
    assert ha.appid_do_jogo_em_foco({}) == ""
    assert ha.appid_do_jogo_em_foco(None) == ""


def test_falha_de_disco_mostra_o_aviso_em_vez_de_escondelo(monkeypatch):
    """Best-effort com a direção certa: na dúvida, avisa."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    def explode() -> set[str]:
        raise OSError("disco fora do ar")

    monkeypatch.setattr(lwd, "load_dismissed_appids", explode)
    assert ha.ela_ja_respondeu_sobre("1086940") is False, (
        "um erro de leitura escondeu o aviso — esconder por falha é pior que "
        "mostrar duas vezes"
    )


def test_as_quatro_telas_chamam_o_dono_novo():
    """A MORDIDA estrutural: se uma tela voltar ao cru, ela volta a acusar."""
    import inspect

    from hefesto_dualsense4unix.app.actions import status_actions
    from hefesto_dualsense4unix.app.actions.jogar import painel

    assert "home_actions.aviso_do_wrapper" in inspect.getsource(painel), (
        "a coluna Atenção da aba Jogar voltou a chamar a função crua"
    )
    fonte_status = inspect.getsource(status_actions)
    assert "aviso = aviso_do_wrapper(state)" in fonte_status, (
        "a aba Status voltou a chamar a função crua"
    )
    assert "aviso_wrapper = aviso_do_wrapper(state)" in inspect.getsource(ha), (
        "a janela Início voltou a chamar a função crua"
    )
