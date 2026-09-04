#!/usr/bin/env python3
"""`daemon.reload` faz o trabalho E responde — as duas coisas.

O DEFEITO ERA VIVO, e apareceu no journal do daemon DELA em 03/09/2026, duas
vezes na mesma noite::

    ipc_client_error  err='Object of type function is not JSON serializable'
    /daemon/ipc_server.py:307 in _serve_client

O handler devolvia ``asdict(new_cfg)``, e o ``DaemonConfig`` carrega
``orcamento_da_mesa`` — que **nasce `None`** (serializável, e por isso nenhum
teste de esquema pegava) e em RUNTIME recebe uma ``lambda`` que o daemon injeta.
``json.dumps`` explode em cima dela.

**O PIOR DESFECHO NÃO É O ERRO — É O TRABALHO FEITO SEM RESPOSTA.**
``reload_config`` roda antes do ``return``: a config nova PASSA A VALER, e o
cliente fica pendurado até o timeout sem saber disso. Quem tentar de novo
recarrega duas vezes. Medido na máquina dela: `daemon.reload` por socket dá
`TimeoutError`, e o daemon cospe um traceback de quarenta linhas.

POR QUE A RÉGUA NÃO LISTA O CAMPO
----------------------------------
Cobrar ``orcamento_da_mesa`` pelo nome envelheceria no dia do oitavo applier — e
envelheceria em SILÊNCIO, porque só o journal acusa. Ela pergunta ao ``json``, e
por isso pega qualquer campo novo que não atravesse, sem ninguém vir aqui.

A MORDIDA: devolva ``asdict(new_cfg)`` cru no handler e
:func:`test_a_resposta_do_reload_atravessa_o_json` reprova com o TypeError exato
que o journal registrou.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import _config_que_viaja
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig


def _config_como_no_daemon_vivo() -> DaemonConfig:
    """Um `DaemonConfig` com os campos que o daemon preenche em runtime.

    NASCER LIMPO É O PONTO: `DaemonConfig()` tem ZERO campos não-serializáveis,
    e é por isso que o defeito atravessou. Só a config VIVA explode — quem
    testasse a de fábrica veria verde para sempre.
    """
    cfg = DaemonConfig()
    for f in dataclasses.fields(cfg):
        if f.name.endswith("applier") or "orcamento" in f.name:
            setattr(cfg, f.name, lambda *a, **k: None)
    return cfg


def test_a_config_de_fabrica_ja_serializava() -> None:
    """A prova de que o defeito NÃO se via na config de fábrica.

    Sem esta linha, alguém leria a régua abaixo e pensaria que bastava testar
    `DaemonConfig()` — que é exatamente o que não bastava.
    """
    json.dumps(dataclasses.asdict(DaemonConfig()))


def test_a_config_viva_explodia_no_json_cru() -> None:
    """E a prova de que a viva explodia. É o defeito, reproduzido.

    Se um dia esta linha parar de levantar, o `DaemonConfig` deixou de carregar
    função — e aí a cura vira desnecessária, o que é uma boa notícia que alguém
    tem de ver em vez de adivinhar.
    """
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps(dataclasses.asdict(_config_como_no_daemon_vivo()))


def test_a_resposta_do_reload_atravessa_o_json() -> None:
    """A cura: o que sai do handler passa por `json.dumps` sem levantar."""
    viajou = _config_que_viaja(_config_como_no_daemon_vivo())
    json.dumps(viajou)


def test_nenhum_campo_some_da_resposta() -> None:
    """Filtrar não pode virar esconder.

    Quem lê a resposta do `reload` está conferindo o que passou a valer. Um
    campo que sumisse calado faria a config nova parecer menor do que é — e a
    diferença apareceria como "essa opção não existe" muito depois.
    """
    cfg = _config_como_no_daemon_vivo()
    assert set(_config_que_viaja(cfg)) == {f.name for f in dataclasses.fields(cfg)}


def test_o_que_nao_viaja_diz_que_nao_viajou() -> None:
    """E o campo que ficou de fora carrega a marca, não um `null`.

    `null` seria indistinguível de um campo realmente vazio, e é assim que uma
    resposta passa a mentir devagar.
    """
    viajou = _config_que_viaja(_config_como_no_daemon_vivo())
    assert viajou["orcamento_da_mesa"] == "<não viaja por IPC>"


def test_o_handler_usa_a_funcao_e_nao_o_asdict_cru() -> None:
    """O elo, lido na ÁRVORE — e não por `grep`, que casaria o comentário.

    A primeira forma que me ocorreu foi procurar a string `asdict(new_cfg)` no
    fonte, e ela apareceria dentro desta própria docstring se estivesse citada.
    É a forma que esta casa mais paga: *a régua confunde a PALAVRA com o ATO*.
    """
    import ast
    import inspect

    from hefesto_dualsense4unix.daemon import ipc_handlers

    fonte = inspect.getsource(ipc_handlers.IpcHandlersMixin._handle_daemon_reload)
    import textwrap

    chamadas = {
        n.func.id
        for n in ast.walk(ast.parse(textwrap.dedent(fonte)))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_config_que_viaja" in chamadas, (
        "o handler voltou a devolver a config crua — a resposta do `reload` "
        "explode no `json.dumps` e o cliente fica pendurado")
    assert "asdict" not in chamadas, (
        "o handler chama `asdict` direto de novo: é o defeito de 03/09 voltando")
