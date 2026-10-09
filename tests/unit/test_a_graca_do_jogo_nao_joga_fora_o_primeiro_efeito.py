"""A-GRACA-DO-JOGO-NAO-JOGA-FORA-O-PRIMEIRO-EFEITO-01 — o gatilho do jogo é evento.

A graça de 0,5 s depois do bind do vpad (`_GAME_REPLICA_GRACE_S`) existe para
filtrar o player-LED e a luz que o `hid_playstation` escreve na sonda
(`f95107f9d`). Ela jogava fora também o gatilho que o jogo mandasse UMA vez
nesse meio segundo; e o dedup pelo último ENTREGUE, com os 4 ms do limite de
taxa, comia o `X → Off → X` de quem rearma a arma.

As escolhas que a bancada decide moram em constante e interruptor:
`HEFESTO_DUALSENSE4UNIX_GRACA_DO_JOGO` (`guarda`/`descarta`),
`HEFESTO_DUALSENSE4UNIX_GRACA_DO_JOGO_S` (o prazo) e
`HEFESTO_DUALSENSE4UNIX_REPLICA_DO_GATILHO` (`sequencia`/`coalescido`).

AS MORDIDAS: voltar ao `return` puro da graça (`_replicate_from_output`)
reprova as provas da graça; voltar o dedup ao último entregue
(`_queue_replica` sem a fila) reprova as da sequência; guardar a luz na graça
reprova a de não regressão do kernel.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad as ug
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_CLOSE,
    UHID_OPEN,
    UHID_START,
    UhidDualSense,
)
from tests.unit.test_uhid_replica import (
    _BLOCO_L,
    _BLOCO_R,
    _blueprint,
    _Clock,
    _edge_report,
    _evento,
    _FakeFd,
    _output_event,
    _Sinks,
    fake_uhid,
)

__all__ = ["fake_uhid"]

_OFF = bytes(11)
_OUTRO_R = bytes([0x26, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9])
_INTERRUPTORES = (
    ug._INTERRUPTOR_DA_GRACA,
    ug._INTERRUPTOR_DO_PRAZO_DA_GRACA,
    ug._INTERRUPTOR_DA_REPLICA_DO_GATILHO,
)


@pytest.fixture(autouse=True)
def _sem_interruptor(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in _INTERRUPTORES:
        monkeypatch.delenv(nome, raising=False)


def _pad_recem_aberto(
    fake: _FakeFd, sinks: _Sinks, *, player: int = 1
) -> tuple[UhidDualSense, _Clock]:
    """Bind e sessão aberta em t=0: a graça corre."""
    clock = _Clock()
    pad = UhidDualSense(
        player=player, blueprint=_blueprint(), time_fn=clock,
        sleep_fn=lambda _s: None, **sinks.kwargs(),
    )
    assert pad.start() is True
    fake.reads.append(_evento(UHID_START))
    fake.reads.append(_evento(UHID_OPEN))
    pad.pump_ff()
    fake.writes.clear()
    return pad, clock


def _jogo_manda(fake: _FakeFd, pad: UhidDualSense, report: bytes) -> None:
    fake.reads.append(_output_event(report))
    pad.pump_ff()


def _pump_em(pad: UhidDualSense, clock: _Clock, t: float) -> None:
    clock.t = t
    pad.pump_ff()


class TestAGracaGuardaOGatilho:
    @pytest.mark.parametrize("player", [1, 2, 3, 4])
    def test_o_gatilho_mandado_na_graca_chega_quando_ela_vence(
        self, fake_uhid: _FakeFd, player: int
    ) -> None:
        """MORDIDA: o `return` puro da graça e o bloco nunca chega (o jogo calou)."""
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks, player=player)
        clock.t = 0.2
        _jogo_manda(fake_uhid, pad, _edge_report(
            flag0=0x0C, trigger_r=_BLOCO_R, trigger_l=_BLOCO_L))
        assert sinks.triggers == [], "a graça ainda corre: nada sai antes do prazo"

        _pump_em(pad, clock, 0.6)

        assert sorted(sinks.triggers) == [("left", _BLOCO_L), ("right", _BLOCO_R)]

    def test_so_o_ultimo_gatilho_da_graca_sai(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks)
        clock.t = 0.1
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))
        clock.t = 0.3
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_OUTRO_R))

        _pump_em(pad, clock, 0.6)
        _pump_em(pad, clock, 0.7)

        assert sinks.triggers == [("right", _OUTRO_R)]

    def test_a_luz_e_o_numero_da_sonda_continuam_descartados(
        self, fake_uhid: _FakeFd
    ) -> None:
        """Não regressão de `f95107f9d`: o que o kernel escreve na sonda não chega."""
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks)
        clock.t = 0.05
        _jogo_manda(fake_uhid, pad, _edge_report(
            flag1=0x14, player_mask=0x15, rgb=(0, 0, 64)))

        _pump_em(pad, clock, 0.6)
        _pump_em(pad, clock, 1.0)

        assert sinks.players == []
        assert sinks.cores == []

    def test_o_fim_da_sessao_na_graca_nao_entrega_o_que_ficou(
        self, fake_uhid: _FakeFd
    ) -> None:
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks)
        clock.t = 0.2
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))
        fake_uhid.reads.append(_evento(UHID_CLOSE))
        pad.pump_ff()

        _pump_em(pad, clock, 0.6)

        assert sinks.triggers == []

    def test_o_interruptor_descarta_volta_ao_de_antes(
        self, fake_uhid: _FakeFd, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ug._INTERRUPTOR_DA_GRACA, "descarta")
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks)
        clock.t = 0.2
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))

        _pump_em(pad, clock, 0.6)

        assert sinks.triggers == []

    def test_o_interruptor_do_prazo_muda_quando_a_graca_vence(
        self, fake_uhid: _FakeFd, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ug._INTERRUPTOR_DO_PRAZO_DA_GRACA, "1,0")
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks)
        clock.t = 0.2
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))

        _pump_em(pad, clock, 0.6)
        assert sinks.triggers == []
        _pump_em(pad, clock, 1.1)
        assert sinks.triggers == [("right", _BLOCO_R)]

    @pytest.mark.parametrize("valor", ["", "abc", "-1", "60"])
    def test_prazo_fora_da_faixa_fica_na_constante(
        self, monkeypatch: pytest.MonkeyPatch, valor: str
    ) -> None:
        monkeypatch.setenv(ug._INTERRUPTOR_DO_PRAZO_DA_GRACA, valor)
        assert ug._prazo_da_graca() == ug._GAME_REPLICA_GRACE_S


def _pad_depois_da_graca(fake: _FakeFd, sinks: _Sinks) -> tuple[UhidDualSense, _Clock]:
    pad, clock = _pad_recem_aberto(fake, sinks)
    clock.t = ug._GAME_REPLICA_GRACE_S + 0.5
    return pad, clock


def _rearme_em_dois_ms(fake: _FakeFd, pad: UhidDualSense, clock: _Clock) -> None:
    t0 = clock.t
    for i, bloco in enumerate((_BLOCO_R, _OFF, _BLOCO_R)):
        clock.t = t0 + i * 0.001
        _jogo_manda(fake, pad, _edge_report(flag0=0x04, trigger_r=bloco))


class TestASequenciaDoGatilho:
    def test_x_off_x_em_dois_ms_chega_inteiro(self, fake_uhid: _FakeFd) -> None:
        """MORDIDA: o dedup pelo último entregue e o físico só recebe o primeiro X."""
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        _rearme_em_dois_ms(fake_uhid, pad, clock)
        assert sinks.triggers == [("right", _BLOCO_R)], "o limite de taxa continua"

        for _ in range(3):
            clock.t += ug._REPLICA_MIN_INTERVAL_S
            pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R), ("right", _OFF), ("right", _BLOCO_R)]

    def test_o_limite_de_taxa_continua_entre_os_passos(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        _rearme_em_dois_ms(fake_uhid, pad, clock)
        clock.t += ug._REPLICA_MIN_INTERVAL_S / 4
        pad.pump_ff()

        assert len(sinks.triggers) == 1

    def test_o_mesmo_bloco_repetido_nao_reenvia(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        for _ in range(3):
            _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))
            clock.t += 1.0
            pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R)]

    def test_a_rajada_dentro_do_limite_de_taxa_entrega_o_ultimo(
        self, fake_uhid: _FakeFd
    ) -> None:
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        blocos = [bytes([0x21, i] + [0] * 9) for i in range(1, 21)]
        for bloco in blocos:
            _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=bloco))
        assert len(pad._as_filas()["trigger_right"]) <= ug._SEQUENCIA_MAX

        for _ in range(ug._SEQUENCIA_MAX + 2):
            clock.t += ug._REPLICA_MIN_INTERVAL_S
            pad.pump_ff()

        assert sinks.triggers == [("right", blocos[0]), ("right", blocos[-1])]

    @pytest.mark.parametrize("player", [1, 2, 3, 4])
    def test_o_jogo_que_muda_a_cada_quadro_nao_fica_para_tras(
        self, fake_uhid: _FakeFd, player: int
    ) -> None:
        """MORDIDA: a fila entregue um por volta e o físico fica voltas atrás do jogo.

        Com o fio do uhid, o report só enfileira e a entrega é uma volta do laço
        (60 Hz); o jogo que manda três blocos por volta tem de ver o último.
        """
        sinks = _Sinks()
        pad, clock = _pad_recem_aberto(fake_uhid, sinks, player=player)
        clock.t = ug._GAME_REPLICA_GRACE_S + 0.5
        for volta in range(6):
            mandados = [bytes([0x21, volta, k] + [0] * 8) for k in range(3)]
            for bloco in mandados:
                _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=bloco))
            clock.t += 1.0 / 60
            pad.pump_ff()
            assert sinks.triggers[-1] == ("right", mandados[-1]), f"volta {volta}"

    def test_o_rearme_passa_pelo_bloco_de_antes_mesmo_com_a_fila_cheia(
        self, fake_uhid: _FakeFd
    ) -> None:
        """A volta ao bloco que o físico tem passa pelo diferente que veio antes dela."""
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=_BLOCO_R))
        for bloco in (_OUTRO_R, _OFF, _BLOCO_R):
            _jogo_manda(fake_uhid, pad, _edge_report(flag0=0x04, trigger_r=bloco))
        for _ in range(3):
            clock.t += ug._REPLICA_MIN_INTERVAL_S
            pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R), ("right", _OFF), ("right", _BLOCO_R)]

    def test_o_interruptor_coalescido_volta_ao_de_antes(
        self, fake_uhid: _FakeFd, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ug._INTERRUPTOR_DA_REPLICA_DO_GATILHO, "coalescido")
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        _rearme_em_dois_ms(fake_uhid, pad, clock)
        for _ in range(3):
            clock.t += ug._REPLICA_MIN_INTERVAL_S
            pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R)]

    def test_a_luz_segue_coalescendo_no_ultimo(self, fake_uhid: _FakeFd) -> None:
        """Só o gatilho é evento: a luz em rajada continua valendo o último."""
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        for cor in ((1, 0, 0), (2, 0, 0), (1, 0, 0)):
            _jogo_manda(fake_uhid, pad, _edge_report(flag1=0x04, rgb=cor))
        clock.t += ug._REPLICA_MIN_INTERVAL_S * 2
        pad.pump_ff()

        assert sinks.cores == [(1, 0, 0)]

    def test_o_fim_da_sessao_esvazia_a_fila(self, fake_uhid: _FakeFd) -> None:
        sinks = _Sinks()
        pad, clock = _pad_depois_da_graca(fake_uhid, sinks)
        _rearme_em_dois_ms(fake_uhid, pad, clock)
        fake_uhid.reads.append(_evento(UHID_CLOSE))
        pad.pump_ff()
        clock.t += 1.0
        pad.pump_ff()

        assert sinks.triggers == [("right", _BLOCO_R)]
        assert not any(pad._as_filas().values())


def test_o_duble_por_new_nao_tem_a_fila_e_nao_quebra() -> None:
    pad: Any = UhidDualSense.__new__(UhidDualSense)
    assert pad._as_filas() == {}
