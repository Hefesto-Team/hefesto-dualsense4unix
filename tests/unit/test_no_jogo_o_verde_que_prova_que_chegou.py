"""A palavra verde da aba "No jogo" só sai com PROVA de que o jogo pediu.

NO-JOGO-SEM-FALSO-VERDE-01, T1 e T2 (25/08/2026).

**O defeito, medido na bancada dela em 23/08 às 21h50** — com ZERO DualSense na
mesa, nenhum jogo aberto e um vpad de pé::

    rumble_ff.per_vpad[0].ff_ultimos_reports:
      [{"ha_s": 4493.5, "flag0": 0, "flag1": 0, "flag2": 2,
        "weak": 0, "strong": 0, "ramo": "parada_sdl"}]
      ff_play_count: 0 · ff_nao_nulo_count: 0 · ff_parada_sdl_count: 1
      visto_ha_s: {"output": 4493.5, "rumble": 4493.5}

Uma parada, zero pedidos — e por três segundos aquela linha esteve **verde**,
escrita "no jogo agora", sem um byte de vibração pedido por ninguém. O
mecanismo estava no fonte, e os dois ramos carimbavam a MESMA chave: o vpad
carimba ``rumble`` na parada do SDL (``uhid_gamepad:2091``) e no pedido de
verdade (``:2159``), e a tela lia só ``visto_ha_s["rumble"]``.

**A cura não muda o vpad, e é de propósito.** O anel ``ff_ultimos_reports`` já
viaja no ``state_full`` desde a QUEM ESCREVEU-01, com o ``ramo`` de cada report
— o payload de hoje já separava o pedido da parada, e ninguém lia. Um carimbo
novo no vpad daria a mesma resposta e só a partir do próximo start do daemon:
nesta casa "o daemon vivo é mais velho que o código" é rotina (install
editable), e a cura que precisa de restart é a que não vale na mesa dela hoje.

Sem GTK de propósito — tudo aqui é função pura, e o arquivo roda no `lint-test`
do CI, que não tem PyGObject (CI-GUI-PULAVA-CALADO-01). A cor da linha, que é o
outro lado desta mesma tarefa, é medida com GTK real na
`test_no_jogo_a_cor_da_linha.py`.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_no_jogo_o_verde_que_prova_que_chegou: importa código da janela GTK")

import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets import controller_card as cc_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ATIVIDADE_FRESCA_S,
    SITUACAO_CHEGANDO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
    estado_do_recurso,
    pedido_de_vibracao_fresco,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    PALAVRA_DA_SITUACAO,
    linhas_do_controle,
)

_PRIMARIO: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "player": 1,
    "player_slot": 1,
}


def _report(
    ha_s: float, weak: int, strong: int, ramo: str = "v1"
) -> dict[str, Any]:
    """Um item do anel, nos MESMOS sete campos que `_anel_de_vibracao` publica."""
    return {
        "ha_s": ha_s,
        "flag0": 4 if (weak or strong) else 0,
        "flag1": 0,
        "flag2": 0,
        "weak": weak,
        "strong": strong,
        "ramo": ramo,
    }


def _estado(**vpad: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"player": 1, "visto_ha_s": {}}
    item.update(vpad)
    return {
        "connected": True,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(_PRIMARIO)],
        "rumble_ff": {"per_vpad": [item]},
    }


def _situacao_da_vibracao(**vpad: Any) -> str:
    estado = estado_do_recurso("vibracao", _PRIMARIO, _estado(**vpad))
    assert estado is not None
    return estado.situacao


def test_a_parada_do_sdl_sozinha_nao_fica_verde() -> None:
    """O payload de 23/08, campo por campo: a linha NÃO pode dizer "no jogo agora"."""
    situacao = _situacao_da_vibracao(
        visto_ha_s={"output": 0.5, "rumble": 0.5},
        ff_play_count=0,
        ff_nao_nulo_count=0,
        ff_parada_sdl_count=1,
        ff_ultimos_reports=[_report(0.5, 0, 0, ramo="parada_sdl")],
    )

    assert situacao == SITUACAO_PARADO
    assert PALAVRA_DA_SITUACAO[situacao] == "parou"


def test_a_linha_da_aba_perde_a_palavra_verde_com_a_parada() -> None:
    """A mesma prova uma camada acima: a aba inteira, e não só a função-dona."""
    linhas = {
        linha.recurso: linha
        for linha in linhas_do_controle(
            _PRIMARIO,
            _estado(
                visto_ha_s={"rumble": 0.5},
                ff_parada_sdl_count=1,
                ff_ultimos_reports=[_report(0.5, 0, 0, ramo="parada_sdl")],
            ),
        )
    }

    assert linhas["vibracao"].situacao == SITUACAO_PARADO
    assert linhas["vibracao"].texto == "parou"
    assert PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO] not in linhas["vibracao"].texto


def test_o_pedido_de_verdade_continua_verde_e_com_o_numero() -> None:
    """A contraprova obrigatória: com pedido de verdade a linha VOLTA a ficar verde."""
    estado = estado_do_recurso(
        "vibracao",
        _PRIMARIO,
        _estado(
            visto_ha_s={"rumble": 0.2},
            ff_nao_nulo_count=17,
            ff_ultimos_reports=[_report(0.2, 40, 90)],
            rumble_no_fisico=[30, 120],
            rumble_no_fisico_ha_s=0.2,
        ),
    )

    assert estado is not None
    assert estado.situacao == SITUACAO_CHEGANDO
    assert estado.frase == "vibração (motores: 30/120)"


def test_o_pedido_velho_no_anel_nao_sustenta_o_verde() -> None:
    """Pedido antigo no anel + carimbo fresco (a parada) = "parou"."""
    assert (
        _situacao_da_vibracao(
            visto_ha_s={"rumble": 0.4},
            ff_ultimos_reports=[
                _report(ATIVIDADE_FRESCA_S + 0.1, 40, 90),
                _report(0.4, 0, 0, ramo="parada_sdl"),
            ],
        )
        == SITUACAO_PARADO
    )


def test_o_report_descartado_na_porta_nao_e_pedido_que_chegou() -> None:
    """O ramo `descartado` chegou e nós o recusamos — a vibração não saiu."""
    assert (
        _situacao_da_vibracao(
            visto_ha_s={"rumble": 0.3},
            ff_descartado_count=4,
            ff_ultimos_reports=[_report(0.3, 40, 90, ramo="descartado")],
        )
        == SITUACAO_PARADO
    )


def test_sem_anel_no_payload_a_linha_nao_arrisca_o_verde() -> None:
    """Sem o anel não há prova — e ausência de prova nunca vira "no jogo agora"."""
    assert (
        _situacao_da_vibracao(visto_ha_s={"rumble": 0.9}) == SITUACAO_PARADO
    )


def test_sem_carimbo_nenhum_continua_sem_pedido_ainda() -> None:
    """E a cura não come a terceira palavra: sem conversa nenhuma é "nunca"."""
    assert _situacao_da_vibracao(visto_ha_s={}) == SITUACAO_NUNCA


@pytest.mark.parametrize(
    ("item", "esperado"),
    [
        ({"rumble_no_fisico": [30, 120], "rumble_no_fisico_ha_s": 0.2}, True),
        (
            {
                "rumble_no_fisico": [30, 120],
                "rumble_no_fisico_ha_s": ATIVIDADE_FRESCA_S + 0.1,
            },
            False,
        ),
        ({"rumble_no_fisico": [0, 0], "rumble_no_fisico_ha_s": 0.1}, False),
        ({"ff_ultimos_reports": [_report(ATIVIDADE_FRESCA_S, 1, 0)]}, True),
        ({"ff_ultimos_reports": [_report(0.1, 0, 200)]}, True),
        ({"ff_ultimos_reports": []}, False),
        ({}, False),
        (None, False),
    ],
)
def test_as_provas_que_a_funcao_dona_aceita(item: Any, esperado: bool) -> None:
    """Cada prova, isolada — é aqui que a régua fica legível."""
    assert pedido_de_vibracao_fresco(item) is esperado


def test_o_carimbo_de_audio_sai_com_a_steam_aberta_e_nenhum_jogo() -> None:
    """A contradição ARMADA: `game_open` sem `appid`, e o som "chegando"."""
    estado_global = _estado(
        game_open=True,
        visto_ha_s={"audio_do_jogo": 0.4},
    )
    estado_global["jogo_steam"] = {"lido": True, "appid": None}

    estado = estado_do_recurso("alto_falante", _PRIMARIO, estado_global)

    assert estado is not None
    assert estado.situacao == SITUACAO_CHEGANDO
    assert estado.frase == "som do controle"


def test_o_comentario_do_som_nao_volta_a_dizer_que_sessao_e_jogo() -> None:
    """Portão do fato: o comentário de `_CATEGORIA_DO_RECURSO` não pode reincidir."""
    fonte = Path(cc_mod.__file__).read_text(encoding="utf-8")
    sem_marcador = re.sub(r"(?m)^\s*#\s?", "", fonte)
    achatado = re.sub(r"\s+", " ", sem_marcador)

    assert "significa mesmo \"nenhum jogo pediu\"" not in achatado, (
        "o código volta a afirmar que o silêncio do carimbo de áudio prova que "
        "NENHUM JOGO pediu — falso desde sempre e medido em 23/08/2026: o gate "
        "é `_replicating()` (sessão uhid aberta), e o cliente da Steam abre"
    )
    assert "o CLIENTE Steam também abre" in achatado
