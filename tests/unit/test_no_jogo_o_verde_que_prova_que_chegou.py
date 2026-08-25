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


# ---------------------------------------------------------------------------
# T1 — o caso medido: uma parada solta não pinta a linha de verde
# ---------------------------------------------------------------------------


def test_a_parada_do_sdl_sozinha_nao_fica_verde() -> None:
    """O payload de 23/08, campo por campo: a linha NÃO pode dizer "no jogo agora".

    Este é o defeito inteiro, com o número que ele tinha na bancada. Uma parada
    do SDL a meio segundo carimba `rumble` e nada mais — e a tela dizia que a
    vibração estava chegando ao jogo.

    Mordida: arrancar a consulta a `pedido_de_vibracao_fresco` do
    `estado_do_recurso` (voltar a decidir só pela idade do carimbo). A situação
    volta a `chegando` e esta asserção reprova.
    """
    situacao = _situacao_da_vibracao(
        visto_ha_s={"output": 0.5, "rumble": 0.5},
        ff_play_count=0,
        ff_nao_nulo_count=0,
        ff_parada_sdl_count=1,
        ff_ultimos_reports=[_report(0.5, 0, 0, ramo="parada_sdl")],
    )

    assert situacao == SITUACAO_PARADO
    # E a palavra que ela lê é a que esta aba já usava — nenhuma entrou nova.
    assert PALAVRA_DA_SITUACAO[situacao] == "parou"


def test_a_linha_da_aba_perde_a_palavra_verde_com_a_parada() -> None:
    """A mesma prova uma camada acima: a aba inteira, e não só a função-dona.

    O painel não tem regra própria (ele chama `estado_do_recurso`), e é
    justamente por isso que este teste existe: se alguém der uma segunda dona à
    decisão, esta asserção continua verdadeira na função e falsa aqui.

    Mordida: a mesma de cima.
    """
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
    """A contraprova obrigatória: com pedido de verdade a linha VOLTA a ficar verde.

    Sem ela, "nunca dizer no jogo agora" passaria no teste de cima e seria um
    defeito pior — a aba existe para dizer quando está funcionando.

    Mordida: fazer `pedido_de_vibracao_fresco` devolver sempre `False`. Esta
    asserção reprova, e é ela que impede a cura de virar mudez.
    """
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
    # MOTOR-QUE-NAO-SE-VE-01: o número que ela pediu continua na frase.
    assert estado.frase == "vibração (motores: 30/120)"


def test_o_pedido_velho_no_anel_nao_sustenta_o_verde() -> None:
    """Pedido antigo no anel + carimbo fresco (a parada) = "parou".

    É o caso real de quem jogou há um minuto: o anel ainda guarda os oito
    últimos reports, e um deles pediu força — mas há muito tempo. O teto é o
    mesmo `ATIVIDADE_FRESCA_S` que governa o resto da linha, pelo mesmo motivo.

    Mordida: tirar a comparação de idade de `pedido_de_vibracao_fresco` (aceitar
    qualquer report não-nulo do anel). A linha volta a dizer "no jogo agora"
    minutos depois de a vibração ter acabado.
    """
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
    """O ramo `descartado` chegou e nós o recusamos — a vibração não saiu.

    Contar o descarte como prova diria "no jogo agora" para um pedido que o
    produto jogou fora na porta. Quem conta essa história é o
    `ff_descartado_count`, e ele existe desde a RUMBLE-QUE-NAO-SE-SENTE-01
    justamente para ela não se perder.

    Mordida: tirar o filtro de `_RAMO_DESCARTADO`. Esta asserção reprova.
    """
    assert (
        _situacao_da_vibracao(
            visto_ha_s={"rumble": 0.3},
            ff_descartado_count=4,
            ff_ultimos_reports=[_report(0.3, 40, 90, ramo="descartado")],
        )
        == SITUACAO_PARADO
    )


def test_sem_anel_no_payload_a_linha_nao_arrisca_o_verde() -> None:
    """Sem o anel não há prova — e ausência de prova nunca vira "no jogo agora".

    É o caso do dublê da foto oficial desta aba (`retratar_abas._NO_JOGO_ESTADO`,
    Controle 2: `visto_ha_s: {"rumble": 0.9}` e mais nada) e o de um payload
    parcial. Arriscar o verde aqui é exatamente o defeito que a T1 cura.

    Mordida: fazer o ramo "anel ausente" devolver `True` (ou manter a situação
    como estava). Esta asserção reprova.
    """
    assert (
        _situacao_da_vibracao(visto_ha_s={"rumble": 0.9}) == SITUACAO_PARADO
    )


def test_sem_carimbo_nenhum_continua_sem_pedido_ainda() -> None:
    """E a cura não come a terceira palavra: sem conversa nenhuma é "nunca".

    "parou" e "sem pedido ainda" mandam agir em lugares opostos, e a distinção é
    o que a PAINEL-DA-VERDADE-01 chama de mais valiosa. Se a T1 rebaixasse tudo
    para "parou", ela teria trocado uma mentira por outra.

    Mordida: rebaixar para `SITUACAO_PARADO` sem checar a situação de entrada
    (isto é, aplicar o rebaixamento fora do ramo `== SITUACAO_CHEGANDO`).
    """
    assert _situacao_da_vibracao(visto_ha_s={}) == SITUACAO_NUNCA


# ---------------------------------------------------------------------------
# A função-dona, direto: as três provas que ela aceita e as que ela recusa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("item", "esperado"),
    [
        # o par que chegou AOS MOTORES, fresco e não-nulo: prova mais forte
        ({"rumble_no_fisico": [30, 120], "rumble_no_fisico_ha_s": 0.2}, True),
        # o mesmo par, velho: a política já não responde por agora
        (
            {
                "rumble_no_fisico": [30, 120],
                "rumble_no_fisico_ha_s": ATIVIDADE_FRESCA_S + 0.1,
            },
            False,
        ),
        # a parada que chegou aos motores (0/0) NÃO é pedido
        ({"rumble_no_fisico": [0, 0], "rumble_no_fisico_ha_s": 0.1}, False),
        # o anel, no teto exato — inclusivo, como o resto da linha
        ({"ff_ultimos_reports": [_report(ATIVIDADE_FRESCA_S, 1, 0)]}, True),
        # só o motor fraco basta; só o forte também
        ({"ff_ultimos_reports": [_report(0.1, 0, 200)]}, True),
        # anel vazio é resposta, e a resposta é "não"
        ({"ff_ultimos_reports": []}, False),
        # payload sem nada: não
        ({}, False),
        # e o que não é dict nenhum
        (None, False),
    ],
)
def test_as_provas_que_a_funcao_dona_aceita(item: Any, esperado: bool) -> None:
    """Cada prova, isolada — é aqui que a régua fica legível.

    Mordida: qualquer uma das linhas de `pedido_de_vibracao_fresco` arrancada
    derruba pelo menos um destes casos.
    """
    assert pedido_de_vibracao_fresco(item) is esperado


# ---------------------------------------------------------------------------
# T2 — o fato errado sobre o som, e o portão que impede a volta dele
# ---------------------------------------------------------------------------


def test_o_carimbo_de_audio_sai_com_a_steam_aberta_e_nenhum_jogo() -> None:
    """A contradição ARMADA: `game_open` sem `appid`, e o som "chegando".

    Este é o teste que documenta em código por que a frase antiga era falsa. O
    estado é o que a bancada dela publicava em 23/08 — `game_open: true`,
    `jogo_steam: {"lido": true, "appid": null}` —, e mesmo assim o carimbo de
    áudio pode estar fresco: quem tem a sessão do hidraw aberta pode ser o
    CLIENTE da Steam, e a docstring de `uhid_gamepad.game_open` chama isso de
    veto permanente.

    Mordida: arrancar o veto — isto é, presumir que sessão aberta é jogo, e
    exigir `jogo_steam.appid` para o som poder chegar. Este teste passa a exigir
    o oposto do que a árvore faz e reprova.
    """
    estado_global = _estado(
        game_open=True,
        visto_ha_s={"audio_do_jogo": 0.4},
    )
    estado_global["jogo_steam"] = {"lido": True, "appid": None}

    estado = estado_do_recurso("alto_falante", _PRIMARIO, estado_global)

    assert estado is not None
    assert estado.situacao == SITUACAO_CHEGANDO
    # A linha continua sem afirmar QUEM escreveu — ela nunca soube.
    assert estado.frase == "som do controle"


def test_o_comentario_do_som_nao_volta_a_dizer_que_sessao_e_jogo() -> None:
    """Portão do fato: o comentário de `_CATEGORIA_DO_RECURSO` não pode reincidir.

    **Mordida escrita nesta leva — a T2 da sprint pedia um teste do carimbo, e
    ele sozinho não impede a FRASE de voltar.** Um comentário é o que a próxima
    pessoa lê antes de mexer, e foi um comentário que sustentou a leitura errada
    por 16 dias.

    O módulo é achatado numa linha só antes da busca, pelo mesmo motivo que o
    portão gêmeo da aba Status (A2, 25/08): a afirmação está partida em duas
    linhas de comentário, e uma varredura linha a linha não a vê.

    **E o `#` de continuação sai antes do achatamento** — medido nesta leva: a
    primeira versão desta régua achatou só o espaço em branco, sobrou
    ``significa mesmo # "nenhum jogo pediu"`` no meio da frase, e ela deu a
    frase antiga por ausente com a frase antiga de volta no arquivo. Régua que
    só sabe passar, pega rodando a mordida e não pensando. Só o marcador de
    INÍCIO de linha sai; um `#` no meio de uma linha (um hex de cor) fica.

    Mordida: devolver a frase antiga ("significa mesmo 'nenhum jogo pediu'") ao
    comentário. Reprova nomeando o arquivo.
    """
    fonte = Path(cc_mod.__file__).read_text(encoding="utf-8")
    sem_marcador = re.sub(r"(?m)^\s*#\s?", "", fonte)
    achatado = re.sub(r"\s+", " ", sem_marcador)

    assert "significa mesmo \"nenhum jogo pediu\"" not in achatado, (
        "o código volta a afirmar que o silêncio do carimbo de áudio prova que "
        "NENHUM JOGO pediu — falso desde sempre e medido em 23/08/2026: o gate "
        "é `_replicating()` (sessão uhid aberta), e o cliente da Steam abre"
    )
    # E o fato certo tem de estar escrito no lugar do errado, não só ausente.
    assert "o CLIENTE Steam também abre" in achatado
