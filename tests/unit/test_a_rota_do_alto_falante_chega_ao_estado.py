#!/usr/bin/env python3
"""A ROTA DO ALTO-FALANTE ENTRA NO `state_full` — cura de 01/09/2026.

A ASSIMETRIA QUE ESTA CURA FECHA, medida com o daemon dela no ar e dois
controles no cabo:

    speaker.set  RESPONDE com a rota:
        {"status": "ok", "speaker": {"volume": 102, "muted": false, "rota": 0}}

    state_full   NÃO a publicava:
        {"volume": 102, "muted": false, "fone_plugado": false, …}

O daemon SABIA a rota e não a contava. Para a tela isso é pior que não saber:
quem trocasse a saída do alto-falante pelo botão não conseguia ler de volta qual
ficou valendo — o botão mudava algo que a interface não tinha como mostrar, e
uma régua que medisse pelo estado diria "SEM EFEITO" sobre um botão que funciona.

Achada quando ela pediu a validação botão a botão no aparelho: *"no aparelho por
favor valida botão a botão tá bom?"* O gesto `rota` da aba Controles era o único
que o daemon aceitava e o estado não confirmava.

`None` NÃO É ZERO, e é por isso que a chave só entra quando existe: a rota `0` é
uma saída de verdade (fone à esquerda, alto-falante à direita) e `None` é "o
controle não disse". Nascer com um padrão mentiria sobre o aparelho.
"""
from __future__ import annotations

from typing import Any

import pytest


class BackendComRota:
    """Um backend que devolve a rota, como o `speaker_state_for` de verdade."""

    def __init__(self, estado: dict[str, Any] | None) -> None:
        self._estado = estado

    def speaker_state_for(self, uniq: str | None = None) -> dict[str, Any] | None:
        return self._estado


def _bloco_do_estado(estado: dict[str, Any] | None) -> dict[str, Any]:
    """Roda o trecho do `ipc_handlers` que monta o `entry["speaker"]`.

    Chamar o handler inteiro exigiria um daemon; o que importa aqui é a
    montagem do bloco, e ela é o que a cura mudou.
    """
    entry: dict[str, Any] = {}
    speaker = estado
    if not isinstance(speaker, dict):
        return entry
    volume = speaker.get("volume")
    if not isinstance(volume, int) or isinstance(volume, bool):
        return entry
    bloco: dict[str, Any] = {
        "volume": max(0, min(255, volume)),
        "muted": bool(speaker.get("muted")),
    }
    rota = speaker.get("rota")
    if isinstance(rota, int) and not isinstance(rota, bool):
        bloco["rota"] = rota
    entry["speaker"] = bloco
    return entry


def test_a_rota_entra_no_bloco_quando_o_controle_a_diz():
    bloco = _bloco_do_estado({"volume": 102, "muted": False, "rota": 0})["speaker"]
    assert bloco["rota"] == 0, (
        "a rota 0 sumiu do estado. Ela é uma saída de VERDADE — fone à esquerda, "
        "alto-falante à direita — e um `if rota:` a trataria como ausente.")


def test_a_rota_nao_nasce_zero_quando_o_controle_nao_a_diz():
    """`None` é "o controle não disse", e inventar um padrão mentiria."""
    bloco = _bloco_do_estado({"volume": 102, "muted": False})["speaker"]
    assert "rota" not in bloco, (
        "a chave apareceu sem o controle ter dito nada — a tela leria 0, que é "
        "uma rota de verdade, e mostraria uma saída que ninguém escolheu.")


@pytest.mark.parametrize("valor", [True, False, "0", 1.5, None])
def test_o_que_nao_e_inteiro_nao_entra(valor):
    """`True` é `int` em Python, e passaria por um teste de tipo descuidado."""
    bloco = _bloco_do_estado({"volume": 102, "muted": False, "rota": valor})["speaker"]
    assert "rota" not in bloco, f"{valor!r} entrou como rota"


def test_o_handler_de_verdade_carrega_a_cura():
    """A régua acima roda uma CÓPIA do trecho — esta cobra o original.

    Sem isto, alguém poderia apagar a cura do `ipc_handlers.py` e os três testes
    acima continuariam verdes sobre a cópia. É a diferença entre provar a lógica
    e provar o PRODUTO.
    """
    import pathlib

    fonte = (pathlib.Path(__file__).resolve().parents[2]
             / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py").read_text()
    assert 'bloco["rota"] = rota' in fonte, (
        "o `ipc_handlers.py` não publica mais a rota no estado — a assimetria "
        "voltou: o `speaker.set` responde com ela e o `state_full` a esconde.")
