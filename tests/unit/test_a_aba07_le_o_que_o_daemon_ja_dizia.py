#!/usr/bin/env python3
"""A RÉGUA DA PARIDADE DA ABA 07 — o que a GTK faz VIVO e o HTML jogava fora.

POR QUE ELA NASCEU, e o número é de 03/09/2026: das 30 features medidas na área
de lançadores, **13 faltavam no HTML** e o padrão era um só nas dez abas — *o
que tem GESTO migrou; o que é LEITURA AO VIVO não*. Esta régua cobra as quatro
que esta frente fechou, e cada uma delas é PONTE: a função já existia na GTK e
a interface nova não a chamava.

    o que a GTK faz                         quem responde agora no HTML
    -------------------------------------   ----------------------------------
    banner "o jogo aberto não passou pelo    SAIU desta aba em 18/10/2026, com a
    wrapper", sem clique (2 abas)            07 antiga: segue na coluna Atenção da
                                             Jogar, por `home_actions`
    "Não perguntar para este jogo" e         SAÍRAM em 21/09/2026, com os outros
    fechar a Steam por ~20 s                 botões que só a Steam tinha — o
                                             reparo é do vigia
    a escada de TRÊS evidências do jogo      `a_escada_do_jogo`, sobre
    (inclusive o jogo JÁ FECHADO)            `launch_env` + a wm_class do estado

O QUE CADA TESTE VIGIA, e a MORDIDA de cada um está na docstring dele. A que mais
importa: troque a escada pelo `steam_game_running_appid()` e o
`test_a_escada_alcanca_o_jogo_que_ela_ja_fechou` reprova.

NADA AQUI TOCA A MÁQUINA DO USUÁRIO. O `conftest.py` desta casa desvia `HOME` e os
quatro `XDG_*`; o que escreve em disco escreve no lar de mentira, e o que
abriria a Steam é dublado — mexer na Steam de quem roda a suíte seria o
instrumento brigando com o produto, que é a armadilha 3 desta casa.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"

SEM_WRAPPER: dict[str, Any] = {
    "gamepad_emulation": {"enabled": True, "wrapper_used": False},
    "window_detect_last_class": "steam_app_3357650",
}


@pytest.fixture(scope="module")
def a07():
    """O módulo que os GESTOS REGISTRADOS habitam — e não outro com o mesmo nome."""
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, "adicionar-lancador")
    assert fn is not None, f"{PAGINA}:adicionar-lancador não tem dono — a régua ficaria cega"
    return sys.modules[fn.__module__]


def test_a_escada_alcanca_o_jogo_que_ela_ja_fechou(a07, monkeypatch):
    """O caso REAL do botão: o jogo não funcionou, ela fechou, e só então veio."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (3357650, 1))
    assert a07.a_escada_do_jogo({}) == (3357650, a07.FECHADO)


def test_a_escada_prefere_a_evidencia_mais_forte(a07, monkeypatch):
    """A ordem é a da GTK: marker+pid vivo, wm_class, marker cru."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (111, 1))
    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: 999)
    assert a07.a_escada_do_jogo(SEM_WRAPPER) == (999, a07.ABERTO)

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    assert a07.a_escada_do_jogo(SEM_WRAPPER) == (3357650, a07.ABERTO)


def test_um_degrau_que_explode_nao_come_os_outros(a07, monkeypatch):
    """Os três leem disco, e disco falha. Cada um no seu `try`."""
    from hefesto_dualsense4unix.daemon import launch_env

    def _explode(*a: Any, **kw: Any) -> Any:
        raise OSError("marker ilegível")

    monkeypatch.setattr(launch_env, "launch_session_appid", _explode)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (3357650, 1))
    assert a07.a_escada_do_jogo({}) == (3357650, a07.FECHADO)


def test_sem_evidencia_nenhuma_a_escada_recusa(a07, monkeypatch):
    """Nada de palpite: sem os três degraus a resposta é `None`."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker", lambda *a, **kw: None)
    assert a07.a_escada_do_jogo({}) == (None, a07.FECHADO)
