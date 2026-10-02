"""ONDA0-Z5/T6 — o cabeçalho para de misturar as duas fontes."""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("T6: o cabeçalho para de misturar as duas fontes")

from tests.unit.test_contagem_um_numero_na_janela import UNIQ_A, _dualsense, _Janela


def _estado_topo_mente(conectados: list[dict[str, Any]]) -> dict[str, Any]:
    """O payload EXATO da medição de 23/08 (ONDA0-Z5 §2.2): topo diz"""
    return {
        "connected": True,
        "transport": "bt",
        "battery_pct": 75,
        "controllers": conectados,
        "active_profile": "vitoria",
    }


def test_topo_mentindo_conectado_com_mesa_vazia_mostra_desconectado() -> None:
    """A MORDIDA do aceite de ponta (ONDA0-Z5 §9): "nenhuma aba pode afirmar"""
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
    """O outro lado: a mesa TEM alguém, mesmo com o topo apontando outro"""
    janela = _Janela()
    estado = _estado_topo_mente([_dualsense(0, "usb", 1, UNIQ_A)])
    estado["transport"] = "bt"

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "Conectado Via USB" in cabecalho, cabecalho
    assert "BT" not in cabecalho.upper().replace("HEFESTO", "")


def test_sem_bloco_controllers_cai_na_regra_antiga_compat() -> None:
    """Daemon velho sem `controllers`: só o topo existe — regra antiga,"""
    janela = _Janela()
    estado = {
        "connected": True,
        "transport": "usb",
        "battery_pct": 80,
        "active_profile": "vitoria",
    }

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "Conectado Via USB" in cabecalho
