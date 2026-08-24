"""ONDA0-Z5/T6 — o cabeçalho para de misturar as duas fontes.

[ESTRUTURAL] — muda o que se vê ao abrir a aba com a mesa vazia. A foto e a
palavra final são dela (R4/PROVA-DE-TELA-01); este arquivo prova o mecanismo,
não substitui o olho dela.

O defeito medido (ONDA0-Z5 §2.2/§2.4): `_render_online`/`_render_slow_state`
usavam `state["connected"]` (o TOPO — leitura do PRIMÁRIO no último tick do
poll) como PORTÃO, e `state["controllers"]` (a MESA — lista viva) só como
CONTEÚDO. Com o topo ainda dizendo ``true``/``bt``/75% e a mesa vazia — o
estado exato medido na bancada de 23/08, ZERO controles — o portão antigo
abria o ramo "conectado" para uma mesa sem ninguém.

A cura: o portão passa a ser a MESA (quando o daemon a publica — o mesmo
`conhece_a_mesa` que `CONSERTO-1.7` já usa para `native_bt_fragil`; daemon
velho sem o bloco `controllers` cai na regra antiga). Nenhuma palavra NOVA:
os três textos ("N controles: ...", "Conectado Via X", "Controle
Desconectado") já existiam.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("T6: o cabeçalho para de misturar as duas fontes")

from tests.unit.test_contagem_um_numero_na_janela import UNIQ_A, _dualsense, _Janela


def _estado_topo_mente(conectados: list[dict[str, Any]]) -> dict[str, Any]:
    """O payload EXATO da medição de 23/08 (ONDA0-Z5 §2.2): topo diz
    conectado/bt/75%, a mesa (`controllers`) é quem sabe a verdade."""
    return {
        "connected": True,
        "transport": "bt",
        "battery_pct": 75,
        "controllers": conectados,
        "active_profile": "vitoria",
    }


def test_topo_mentindo_conectado_com_mesa_vazia_mostra_desconectado() -> None:
    """A MORDIDA do aceite de ponta (ONDA0-Z5 §9): "nenhuma aba pode afirmar
    que há controle conectado" com a mesa vazia — mesmo quando o topo mente.
    """
    janela = _Janela()
    estado = _estado_topo_mente([])

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "Controle Desconectado" in cabecalho, (
        f"cabeçalho mentiu 'conectado' com mesa vazia: {cabecalho!r}"
    )
    assert "Conectado" not in cabecalho
    assert janela.builder.get_object("status_connection").texto == "Desconectado"


def test_topo_mentindo_com_um_controle_de_verdade_mostra_o_certo() -> None:
    """O outro lado: a mesa TEM alguém, mesmo com o topo apontando outro
    transporte (não é o caso medido, mas prova que o portão virou a mesa, não
    um `or` frouxo com o topo)."""
    janela = _Janela()
    estado = _estado_topo_mente([_dualsense(0, "usb", 1, UNIQ_A)])
    estado["transport"] = "bt"  # o topo diz bt; a mesa diz usb — a mesa manda

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "Conectado Via USB" in cabecalho, cabecalho
    assert "BT" not in cabecalho.upper().replace("HEFESTO", "")


def test_sem_bloco_controllers_cai_na_regra_antiga_compat() -> None:
    """Daemon velho sem `controllers`: só o topo existe — regra antiga,
    de propósito (compat), não é o bug desta sprint."""
    janela = _Janela()
    estado = {
        "connected": True,
        "transport": "usb",
        "battery_pct": 80,
        "active_profile": "vitoria",
        # sem a chave "controllers" — daemon antigo.
    }

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "Conectado Via USB" in cabecalho
