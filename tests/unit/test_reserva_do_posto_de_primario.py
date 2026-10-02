"""RESERVA-DO-POSTO-01 — o instrumento que a medição dela vai usar."""
from __future__ import annotations

import io

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC
from tests.unit.test_coop_bancada_de_queda_do_primario import (
    UNIQ_A,
    UNIQ_B,
    Bancada,
)
from tests.unit.test_reserva_do_posto_01_os_eventos_falam import (
    P1,
    P2,
    _backend,
    _eventos,
    _HandleFalso,
    journal,
)

__all__ = ["journal"]

TETO_DE_PRODUCAO_SEC = 120.0


def _queda(transporte: str, journal_buf: io.StringIO) -> dict[str, object]:
    """Derruba o primário com o backend nesse transporte e devolve o evento."""
    ctrl = _backend({P1: _HandleFalso()}, primario=P1)
    ctrl._transport = transporte  # type: ignore[assignment]
    ctrl._reservar_o_posto_de_primario(P1)
    quedas = [
        evento
        for evento in _eventos(journal_buf)
        if evento.get("event") == "primario_deposto_reservado"
    ]
    assert len(quedas) == 1, f"esperava UMA queda no journal, vi {quedas}"
    return quedas[0]


def test_a_queda_e_a_caducidade_saem_em_info(journal: io.StringIO) -> None:
    """A MORDIDA da §RESERVA-1: os dois instantes do prazo, com o transporte."""
    queda = _queda("bt", journal)
    assert queda.get("key") == P1
    assert queda.get("transporte") == "bt", (
        "a queda do primário saiu no journal sem `transporte` — no caderno da "
        "medição a coluna do transporte fica vazia, e uma queda no cabo passa "
        f"a valer tanto quanto uma no rádio. Evento visto: {queda}"
    )

    caduca = _backend({P2: _HandleFalso()}, primario=P2)
    caduca._reservar_o_posto_de_primario(P1)
    caduca._relogio.agora += PRIMARIO_RESERVA_SEC + 1.0
    assert caduca._posto_reservado_de_volta() is None

    nomes = [str(evento.get("event")) for evento in _eventos(journal)]
    assert "primario_reserva_caducou" in nomes, (
        "a volta que ESTOUROU o prazo não deixou linha no journal — medir a "
        "distribuição assim é contar só as amostras que já cabem no número "
        f"que se quer justificar. Eventos vistos: {nomes}"
    )


def test_o_transporte_da_queda_e_lido_e_nao_digitado(journal: io.StringIO) -> None:
    """A régua que digita o que devia LER é o defeito recorrente desta casa."""
    assert _queda("usb", journal).get("transporte") == "usb", (
        "o campo não acompanha o transporte do controle — ele está sendo "
        "escrito, não lido"
    )


def test_a_constante_de_producao_nao_saiu_da_bancada() -> None:
    """A trava da §RESERVA-2: a janela da sessão de medição não vai para o disco."""
    assert PRIMARIO_RESERVA_SEC > 0.0, (
        "prazo zero ou negativo não é reserva: a caducidade dispara no mesmo "
        "instante da queda e o posto nunca é guardado"
    )
    assert PRIMARIO_RESERVA_SEC <= TETO_DE_PRODUCAO_SEC, (
        f"`PRIMARIO_RESERVA_SEC` está em {PRIMARIO_RESERVA_SEC} s — acima do "
        f"teto de produção ({TETO_DE_PRODUCAO_SEC} s), isto é a janela de uma "
        "SESSÃO DE MEDIÇÃO que escapou para o commit. Ela desliga um controle "
        "e continua com o outro; por todo esse tempo o produto ainda guarda o "
        "posto para o que ela desligou"
    )


class TestAVoltaPeloCabo:
    """§RESERVA-5 — o que o produto faz, medido, para a pergunta da §7.3."""

    def test_a_bancada_sabe_a_diferenca_entre_o_cabo_e_o_radio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valida o INSTRUMENTO antes de acreditar nele."""
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.get_transport() == "bt"

        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.get_transport() == "usb", (
            "a bancada não distingue o cabo do rádio — o `conType` do dublê "
            "não chega ao `_detect_transport` do produto"
        )

    def test_a_volta_pelo_cabo_retoma_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CARACTERIZAÇÃO: o deposto no rádio que volta pelo CABO retoma o posto."""
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_A

        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_B, "com A fora, B TEM de assumir"

        bancada.relogio.avancar(PRIMARIO_RESERVA_SEC / 2.0)
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_A, (
            "a caracterização mudou: o deposto que volta pelo cabo NÃO retoma "
            "mais o posto. Se foi decisão dela (§7.3), este teste e a §6 da "
            "sprint mudam junto"
        )
        assert bancada.inst.get_transport() == "usb", (
            "a retomada não refez o `_detect_transport` — o daemon acha que o "
            "primário está no rádio quando ele voltou pelo cabo"
        )

    def test_passada_a_janela_a_tomada_nao_toma_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro lado, e é ele que limita o estrago do de cima."""
        bancada = Bancada(monkeypatch)
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        bancada.relogio.avancar(PRIMARIO_RESERVA_SEC + 1.0)
        bancada.sentar(UNIQ_A, transporte="usb")
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_B
