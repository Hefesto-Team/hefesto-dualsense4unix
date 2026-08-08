"""Um tique CEGO não derruba a exceção de Steam Input no meio da partida.

PARTIDA-PICOTADA-01 (08/08/2026). O defeito, MEDIDO no journal dela: entre
01:43 e 03:03, com o Sackboy aberto e dois DualSense no cabo, o gamepad virtual
foi suspenso e retomado **oito vezes**. Cada retomada custa uma recriação de
vpad, e cada recriação derruba o jogador 2 do co-op
(`coop_derrubado_pela_excecao_steam_input`, sete ocorrências).

O gatilho não era o jogo sair da frente. Era `steam_input_exception_appid` ler a
janela CRUA e tratar "não sei" como "o jogo saiu":

    02:27:28.797  autoswitch_window_info_unavailable current=Sackboy wm_class=unknown
    02:27:29.505  steam_input_excecao_encerrada
    02:27:29.781  gamepad_emulation_started          <- vpad recriado no meio da partida

    01:44:42.859  autoswitch_janela_propria_ignorada wm_class=Hefesto-Dualsense4Unix
    01:44:43.116  steam_input_excecao_encerrada
    01:44:43.387  gamepad_emulation_started          <- ela abriu a janela do Hefesto

O contraste que fecha a conta: no sábado 01-02/08, jogando horas com três
controles, foram **15** quedas de vpad em **48 h**. Em 08/08 foram **12 em
1h25** — vinte e sete vezes mais.

A cura é assimétrica de propósito, como a UX-04: barato para entrar, caro para
sair. Só evidência POSITIVA de outra janela encerra a exceção; tique cego e
janela própria mantêm o que valia.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.launch_env import steam_input_exception_appid

#: O appid do Sackboy, que é o caso medido.
SACKBOY = 1599660

#: A classe que a Steam dá à janela do jogo.
CLASSE_DO_JOGO = f"steam_app_{SACKBOY}"


class _StoreFalso:
    """Só os dois campos que a função lê — crua e sticky."""

    def __init__(self, crua: str | None, sticky: str | None) -> None:
        self.window_detect_current_class = crua
        self.window_detect_last_class = sticky


class _DaemonFalso:
    def __init__(self, store: _StoreFalso) -> None:
        self.store = store


def _perguntar(crua: str | None, sticky: str | None, tmp_path: Path) -> int | None:
    """Chama a função como o daemon a chama, com a allowlist injetada.

    `base_dir` aponta para um diretório vazio de propósito: sem marker de
    wrapper, a única evidência é a janela — que é o que este teste mede.
    """
    return steam_input_exception_appid(
        _DaemonFalso(_StoreFalso(crua, sticky)),
        base_dir=tmp_path,
        allowlist={SACKBOY},
    )


# --- o que a cura tem de preservar -------------------------------------------


def test_jogo_na_frente_ativa_a_excecao(tmp_path: Path) -> None:
    """O caso normal continua igual: jogo em foco ⇒ exceção ativa."""
    assert _perguntar(CLASSE_DO_JOGO, CLASSE_DO_JOGO, tmp_path) == SACKBOY


def test_alt_tab_de_verdade_encerra_a_excecao_no_mesmo_tique(tmp_path: Path) -> None:
    """O medo registrado no docstring continua coberto.

    Um alt-tab real para outro app dá leitura POSITIVA dessa outra janela, e
    essa apaga a exceção IMEDIATAMENTE — o físico não fica exposto ao desktop
    esperando um sticky decair. Este teste é o contrapeso do de baixo: sem ele,
    alguém "curaria" a instabilidade tornando tudo sticky, e reabriria o defeito
    que a leitura crua existe para evitar.
    """
    assert _perguntar("firefox", CLASSE_DO_JOGO, tmp_path) is None


def test_jogo_fora_da_allowlist_nunca_ativa(tmp_path: Path) -> None:
    """Outro jogo da Steam em foco não liga a exceção de um appid alheio."""
    assert _perguntar("steam_app_3357650", "steam_app_3357650", tmp_path) is None


# --- o que a cura conserta — ARRANQUE A CURA E ESTES REPROVAM -----------------


@pytest.mark.parametrize(
    "crua",
    [
        pytest.param("unknown", id="detector-devolveu-unknown"),
        pytest.param("", id="detector-devolveu-vazio"),
        pytest.param(None, id="detector-nao-leu-nada"),
    ],
)
def test_tique_cego_nao_derruba_a_excecao(crua: str | None, tmp_path: Path) -> None:
    """`wm_class=unknown` é "não sei", nunca "o jogo saiu da frente".

    É o caso das 02:27:28 no journal dela: o detector devolveu `unknown` com o
    Sackboy ainda em `current=`, e 700 ms depois o vpad foi recriado no meio da
    partida.

    ARRANQUE A CURA (o bloco `if _leitura_cega(crua):` em
    `daemon/launch_env.py`) e este teste REPROVA: sem ele a função devolve
    `None`, a exceção cai, o vpad é destruído e o jogador 2 do co-op vai junto.
    """
    assert _perguntar(crua, CLASSE_DO_JOGO, tmp_path) == SACKBOY, (
        f"leitura cega ({crua!r}) derrubou a exceção — é o defeito da "
        "PARTIDA-PICOTADA-01: o vpad é recriado no meio da partida e o "
        "jogador 2 cai junto."
    )


def test_janela_do_proprio_hefesto_nao_derruba_a_excecao(tmp_path: Path) -> None:
    """Ela abrir a janela do Hefesto não pode picotar a partida.

    Caso das 01:44:42 e das 03:01:20 no journal: `wm_class` da própria GUI, e
    logo em seguida `steam_input_excecao_encerrada`. Ela estava mexendo na
    configuração enquanto o jogo rodava — que é exatamente o que a janela existe
    para permitir.

    ARRANQUE A CURA e este teste REPROVA.
    """
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    for classe in sorted(OWN_GUI_WM_CLASSES):
        assert _perguntar(classe, CLASSE_DO_JOGO, tmp_path) == SACKBOY, (
            f"a janela do próprio Hefesto ({classe!r}) derrubou a exceção — ela "
            "não pode perder o jogador 2 por abrir a configuração."
        )


def test_cego_sem_sticky_nao_inventa_excecao(tmp_path: Path) -> None:
    """Cego + sticky vazio ⇒ None. A cura não pode inventar sinal do nada.

    Sem esta asserção, "cair no sticky" viraria "assumir que o jogo está na
    frente", e a exceção nasceria sozinha numa máquina que nunca viu o jogo.
    """
    assert _perguntar("unknown", None, tmp_path) is None
    assert _perguntar(None, "", tmp_path) is None


def test_cego_com_sticky_de_outro_app_nao_ativa(tmp_path: Path) -> None:
    """O sticky só sustenta o que ELE diz — e ele pode dizer "outro app"."""
    assert _perguntar("unknown", "firefox", tmp_path) is None
