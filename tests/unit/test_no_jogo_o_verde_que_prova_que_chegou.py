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


from hefesto_dualsense4unix.interface import cartao_do_controle as cc_mod

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
