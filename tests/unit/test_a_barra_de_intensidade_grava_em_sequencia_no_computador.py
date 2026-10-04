"""A barra de intensidade, arrastada VÁRIAS vezes, grava no computador — inclusive a 0.

Achado na bancada de 03/10/2026 (18h10, Freestyle ativo): a barra do P1 arrastada a
`0` falhou duas vezes com *«custom_mult só é válido com policy='custom' (policy=None)»*
e a tela mostrou os `0%` que não gravou.

CAUSA MEDIDA (e a hipótese «o `0.0` é lido como ausente» CAIU): não é o zero. É
qualquer mudança só do `custom_mult` de quem JÁ está em `policy='custom'`. O diff
(`o_padrao_do_computador._diferenca_de_secao`) trazia só o campo que mudou, e
`_com_os_pares` completava o colega que faltava com `None` — «tira o colega» —,
então o computador gravava `{custom_mult: x}` sem `policy` e o `maquina.json`
recusava o documento. Os arrastes de antes (acima de zero) aplicaram porque eram
o PRIMEIRO arraste, que mudava os dois campos.

A cura é na origem: o diff leva o par inteiro, com o valor que ele tem agora.

AS MORDIDAS:

* tire o laço dos pares de `_diferenca_de_secao` → os casos de arraste em
  sequência reprovam com a recusa do `maquina.json`;
* a régua de unidade (`test_o_diff_leva_o_par_inteiro`) reprova no mesmo lugar.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"


class _Ponte:
    def __getattr__(self, nome: str) -> Any:
        def registrar(*_a: Any, **_k: Any) -> Any:
            return (True, None) if nome.endswith("_checked") else True

        return registrar


def _ctx() -> Any:
    import pacotes

    return pacotes.Contexto(
        state={"rumble_policy": "balanceado", "rumble_ff": {}},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "P1", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb", "index": 0,
                     "player": 1}],
        estados={})


def _arrastar(pontos: int) -> None:
    import pacotes
    from pacotes import a05_vibracao

    a05_vibracao.parar_o_teste()
    pacotes.gesto_da_pagina("05-vibracao.html", "intensidade")(
        _ctx(), {"uniq": UNIQ, "controle": "p1", "valor": str(pontos)}, _Ponte())


def _o_que_o_computador_guardou() -> dict[str, Any]:
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    controles = opc.o_computador().model_dump(mode="json", exclude_unset=True)["controles"]
    (entrada,) = controles.values()
    return entrada["rumble"]


@pytest.mark.parametrize("sequencia", [
    (50, 0), (50, 60), (50, 0, 100, 200, 1), (0, 50, 0),
])
def test_arrastes_em_sequencia_gravam_todos(sequencia: tuple[int, ...]) -> None:
    for pontos in sequencia:
        _arrastar(pontos)
        guardado = _o_que_o_computador_guardou()
        assert guardado == {"policy": "custom", "custom_mult": pontos / 100}, (
            f"depois de arrastar a {pontos}% o computador guardou {guardado}"
        )


def test_o_diff_leva_o_par_inteiro() -> None:
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.schema import Profile

    def perfil(rumble: dict[str, Any]) -> Profile:
        return Profile.model_validate(
            {"name": "x", "match": {"type": "manual"}, "rumble": rumble})

    mudou = opc._diferenca_de_secao(
        "rumble",
        perfil({"policy": "custom", "custom_mult": 0.5}).rumble,
        perfil({"policy": "custom", "custom_mult": 0.0}).rumble,
    )
    assert mudou == {"custom_mult": 0.0, "policy": "custom"}
