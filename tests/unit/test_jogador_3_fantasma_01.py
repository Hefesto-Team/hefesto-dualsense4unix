"""Nunca existe um estado em que o jogo vê o físico E o virtual.

JOGADOR-3-FANTASMA-01 (08/08/2026). MEDIDO na tela dela, ao vivo: o Sackboy
mostrava um **"Jogador 3"** que era o próprio controle duplicado.

A LINHA DO TEMPO QUE O PRODUZIU (journal, 08/08)
================================================
    13:14:53  coop_derrubado_pela_excecao_steam_input   (a marca agiu: vpads fora)
    13:17:42  autoswitch_janela_propria_ignorada        (ela abriu a janela)
    13:17:49  steam_input_vpad_retomado  motivo=gesto_manual
    13:17:50  gamepad_grab_pulado_steam_input  motivo=excecao_por_appid   ← grab PULADO
    13:17:50  broker_hide_pulado_steam_input   motivo=excecao_por_appid   ← hide PULADO
    13:17:50  gamepad_emulation_started        flavor=dualsense          ← vpad DE PÉ

Estado resultante, conferido no `sysfs`: **dois físicos com hidraw e dois vpads
com hidraw, ao mesmo tempo.** O jogo via quatro dispositivos onde havia dois
controles.

POR QUE ISSO NÃO ERA "ESCOLHA DELA"
===================================
O ramo do gesto manual declarava, por escrito, que o preço — *"este jogo volta a
ver dois dispositivos"* — era escolha dela e ficava no journal. **Não é escolha:
é armadilha.** Ninguém escolhe um jogador fantasma, e a única pista do preço
estava num log que ninguém lê durante a partida. O gesto que o disparou foi ela
**abrir a janela do Hefesto**.

A REGRA JÁ ESTAVA DECLARADA, E NÃO ERA IMPOSTA
==============================================
O rótulo do `steam_app_<appid>.env` diz, desde a `JOGO-01`:

    "allowlist Steam Input (físico é o único dispositivo)"

E o comentário que o batizou explica por que o nome antigo (*"sem dedup"*) era o
defeito: *"sem dedup com o vpad de pé é o controle duplicado"*. **A regra vivia
num rótulo e não no código.**

ATENÇÃO — A CURA FOI REVERTIDA, E ESTE ARQUIVO É A ESPECIFICAÇÃO DA PRÓXIMA
=========================================================================
A cura que estes testes descreviam funcionou no mecanismo e **quebrou os
controles dela**: ela dispensava a exceção NO MEIO da sessão, e o jogo — que lê o
`env` uma vez, na abertura (`assets/hefesto-launch.sh:320`, `exec env "$@"`) —
ficou procurando um controle físico que a cura acabara de agarrar. Zero inputs.

Foi revertida por completo. O que sobrevive aqui é o **contrato**: os quatro
comportamentos que qualquer cura futura do fantasma tem de cumprir. O teste do
ciclo de vida da dispensa está marcado `xfail` porque descreve código que ainda
não existe — e `xfail` é honesto onde `skip` seria mudo.

O caso inteiro está em
`docs/process/sprints/2026-08-08-JOGADOR-3-FANTASMA-01-a-cura-certa-no-momento-errado.md`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp


class _DaemonFalso:
    """O mínimo que os dois caminhos leem."""

    def __init__(self, *, excecao: bool, appid: int | None) -> None:
        self._steam_input_excecao = excecao
        self._steam_input_vpad_suspenso = excecao
        self._steam_input_flavor_suspenso = "dualsense" if excecao else None
        self._steam_input_coop_derrubados = 1 if excecao else 0
        self._steam_input_excecao_dispensada_appid: int | None = None
        self._appid_visivel = appid
        self._gamepad_device = None


APPID = 1599660


@pytest.fixture()
def daemon_com_jogo_marcado(monkeypatch: pytest.MonkeyPatch) -> _DaemonFalso:
    """Jogo da allowlist na frente, exceção ativa, vpads suspensos."""
    d = _DaemonFalso(excecao=True, appid=APPID)

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        # espelha a dispensa, como a função de verdade faz
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == APPID:
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )
    return d


def test_o_gesto_manual_dispensa_a_excecao(daemon_com_jogo_marcado: _DaemonFalso) -> None:
    """Pedir o gamepad na mão tira a exceção do caminho — o gesto ganha inteiro.

    ARRANQUE A CURA e este teste REPROVA: sem a dispensa, o vpad volta e o
    grab/hide continuam pulados, que é o estado do jogador fantasma.
    """
    d = daemon_com_jogo_marcado
    assert gp.steam_input_excecao_ativa(d) is True, "o cenário nasceu errado"

    gp.sync_steam_input_exception(d)  # estado inicial estabilizado
    d._steam_input_excecao_dispensada_appid = APPID  # o que o gesto grava
    d._steam_input_excecao = False

    assert gp.sync_steam_input_exception(d) is False, (
        "com a exceção dispensada por gesto, `sync` não pode religá-la — senão o "
        "grab volta a ser pulado no tique seguinte e o duplicado renasce."
    )
    assert gp.steam_input_excecao_ativa(d) is False


@pytest.mark.xfail(
    reason=(
        "a cura da dispensa foi REVERTIDA em 08/08 — ela quebrou os inputs dela "
        "ao trocar o dono do controle no meio da sessão. Este teste é o contrato "
        "da próxima cura: a dispensa tem de morrer quando o jogo sai da frente, "
        "para a marca dela voltar a valer na abertura seguinte."
    ),
    strict=True,
)
def test_a_dispensa_morre_quando_o_jogo_sai_da_frente(
    daemon_com_jogo_marcado: _DaemonFalso,
) -> None:
    """A marca dela volta a valer na próxima abertura.

    O contrapeso: uma dispensa que sobrevivesse ao jogo seria a caixinha
    deixando de funcionar em silêncio — ela marcou o jogo e a marca sumiria sem
    ninguém dizer.
    """
    d = daemon_com_jogo_marcado
    d._steam_input_excecao_dispensada_appid = APPID
    d._appid_visivel = None  # o jogo saiu da frente
    # A saída da exceção tenta devolver os vpads: consulta o backend para decidir
    # o `uhid` e lê o sabor da config. Aqui só interessa o destino da dispensa,
    # então os dois são dublês mínimos — o `controller` sem `hidraw_path` faz
    # aquele caminho devolver "sem uhid" e seguir, em vez de estourar.
    d.controller = object()
    d.config = SimpleNamespace(gamepad_flavor="dualsense")

    gp.sync_steam_input_exception(d)
    assert d._steam_input_excecao_dispensada_appid is None, (
        "a dispensa sobreviveu ao jogo — a marca dela pararia de valer para "
        "sempre, sem aviso."
    )


def test_a_dispensa_e_por_appid_e_nao_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispensar um jogo não pode dispensar os outros da lista.

    Ela tem dois jogos marcados. Abrir a janela durante um não pode desligar a
    marca do outro.
    """
    outro = 3357650
    d = _DaemonFalso(excecao=True, appid=outro)
    d._steam_input_excecao_dispensada_appid = APPID  # dispensou o Sackboy

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == getattr(
            daemon, "_appid_visivel", None
        ):
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )

    assert gp.sync_steam_input_exception(d) is True, (
        "a dispensa de um appid vazou para outro — a marca do outro jogo dela "
        "parou de valer sem ninguém pedir."
    )


def test_sem_dispensa_a_excecao_continua_valendo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho normal não muda: jogo marcado na frente ⇒ exceção ativa.

    Sem esta asserção, "curar" o fantasma poderia virar desligar a exceção
    sempre — e o controle dobrado que a marca existe para acabar voltaria
    inteiro, que é o defeito de origem da DUPLO-REGISTRO-01.
    """
    d = _DaemonFalso(excecao=False, appid=APPID)

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == APPID:
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )
    monkeypatch.setattr(gp, "_set_evdev_grab", lambda *_a, **_k: None)
    monkeypatch.setattr(gp, "suspend_vpads_for_steam_input", lambda *_a, **_k: None)

    assert gp.sync_steam_input_exception(d) is True, (
        "jogo marcado na frente deixou de ligar a exceção — o controle dobrado "
        "que a marca existe para acabar voltaria."
    )
