"""A-NUMERACAO-BATE-A-LUZ-COM-O-JOGO-01, cura 2 — com o jogo aberto, o lugar guardado espera.

**A decisão é de produto** (``D-3009-COM-O-JOGO-O-LUGAR-GUARDADO-ESPERA``, 02/10/2026, «Esperar
o jogo»): com um jogo na autoridade, quem cai ou entra não muda o número de ninguém;
cada um fica com o número que tinha, e o rearranjo acontece quando o jogo solta. O
«Renumerar agora» continua sendo o gesto do usuário, e vale com o jogo aberto.

**A bancada é a de queda da O-ASSENTO-02** (:class:`MesaDoJogo`): o backend, o co-op e o
registro de verdade, e o jogo visto de FORA (:class:`JogoPorFora`, o lugar de cada vpad
pela ordem em que ele nasce e morre). Nenhum nó uinput nasce.

As réguas são as 8 a 12 da sprint, mais a do posto do P1 no backend (a reserva de 30 s
do ``_primario_deposto`` também espera enquanto a vaga diz que espera).

AS MORDIDAS (07/10/2026, cada uma devolvida com o md5 conferido):

- o ``segurar_os_prazos`` fora do tique do co-op reprova 8 de 10 (a 9, a 10, a 12 e
  a do posto);
- soltar sem empurrar o ``ate`` reprova a 9 (vence no fechamento), e empurrar duas
  vezes reprova a 9 pelo outro lado;
- o ``segurar_os_prazos`` segurando também o ``soltar_os_lugares_guardados`` reprova a 11;
- o ``segurar_os_prazos`` só no registro dos DualSense reprova a 12, nas duas ordens;
- a ponte dos externos que chega com o jogo aberto sem ser segurada na hora reprova a
  12 com a ponte tardia;
- a reserva do posto sem a pergunta da vaga (``_o_lugar_do_deposto_espera_locked``)
  reprova a do posto.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog

import hefesto_dualsense4unix.daemon.connection as cx
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    P1,
    P2,
    P3,
    P4,
    MesaDoJogo,
    Relogio,
    montar,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    config_isolado as config_isolado,
)

QUATRO = (P1, P2, P3, P4)
PRAZO = prazo_do_lugar_guardado()
TIQUE = 2.0
TREZENTOS = 300.0
EXTERNO = "aa:bb:cc:00:00:09"


@pytest.fixture
def gatilhos(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """O armar do gatilho de produção, sem a lightbar: devolve quantas vezes armou."""
    armados: list[str] = []
    monkeypatch.setattr(cx, "registrar_gatilho_da_lightbar", lambda _d: None)
    monkeypatch.setattr(cx, "armar_gatilho", lambda _d, nome, **_kw: armados.append(nome))
    yield armados


def _volta(bancada: MesaDoJogo, segundos: float = TIQUE) -> None:
    """Um tique da bancada e a volta do laço que confere a numeração."""
    bancada.tique(segundos)
    cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon)  # type: ignore[arg-type]


def _o_jogo_sem(sai: str) -> dict[int, str | None]:
    """O jogo de fora com ``sai`` fora: o vpad do P1 fica parado, os outros morrem."""
    jogo: dict[int, str | None] = {}
    for n, uniq in enumerate(QUATRO):
        if uniq != sai:
            jogo[n + 1] = uniq
        elif uniq == P1:
            jogo[n + 1] = None
    return jogo


def _eventos(registros: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in registros if r.get("event") == nome]


@pytest.mark.usefixtures("config_isolado")
class TestTrezentosSegundosComOJogo:
    """Régua 8: 300 s depois de sair, com o jogo aberto, ninguém renumerou."""

    @pytest.mark.parametrize("sai", QUATRO, ids=["p1", "p2", "p3", "p4"])
    def test_ninguem_renumera_e_ninguem_renasce(
        self, monkeypatch: pytest.MonkeyPatch, gatilhos: list[str], sai: str
    ) -> None:
        bancada = montar(monkeypatch, 4)
        _volta(bancada)
        vpads = {u: bancada.vpad_de(u) for u in QUATRO if u not in (P1, sai)}
        bancada.mesa.levantar(sai)
        _volta(bancada)
        # A saída em si muda a mesa (quem saiu deixa de ter número na tela) e arma uma
        # vez, como sem jogo; o que a régua mede são os 300 s que vêm depois.
        gatilhos.clear()
        with structlog.testing.capture_logs() as registros:
            for _ in range(int(TREZENTOS / TIQUE)):
                _volta(bancada)
        assert bancada.a_tela() == {
            u: n + 1 for n, u in enumerate(QUATRO) if u != sai
        }, "com o jogo aberto alguém trocou de número"
        assert gatilhos == [], "a cor armou por numeração com o jogo aberto"
        assert _eventos(registros, "gatilho_da_cor_por_numeracao") == []
        assert _eventos(registros, "coop_ordem_recriada") == []
        assert bancada.o_jogo_ve() == _o_jogo_sem(sai)
        for uniq, vpad in vpads.items():
            assert bancada.vpad_de(uniq) is vpad, f"{uniq} renasceu com o jogo aberto"


@pytest.mark.usefixtures("config_isolado")
class TestOJogoSoltaEOPrazoQueSobrou:
    """Régua 9: o P2 sai com 10 s corridos, o jogo abre 200 s, e vence 20 s depois."""

    def test_o_vencimento_cai_no_prazo_que_sobrou(
        self, monkeypatch: pytest.MonkeyPatch, gatilhos: list[str]
    ) -> None:
        relogio = Relogio()
        bancada = montar(monkeypatch, 4, relogio=relogio, jogo=False)
        _volta(bancada)
        bancada.mesa.levantar(P2)
        _volta(bancada)
        assert P2 in bancada.reg.guardados()
        gatilhos.clear()
        _volta(bancada, 10.0)
        bancada.daemon.display_authority = "game"
        _volta(bancada, 0.0)
        for _ in range(100):
            _volta(bancada)
        assert P2 in bancada.reg.guardados(), "com o jogo aberto o prazo do P2 venceu"
        assert gatilhos == []

        bancada.daemon.display_authority = "daemon"
        _volta(bancada, 0.0)
        fechou = relogio()
        venceu: float | None = None
        for _ in range(60):
            _volta(bancada, 1.0)
            if P2 not in bancada.reg.guardados():
                venceu = relogio()
                break
        assert venceu is not None, "o prazo que sobrou não venceu em 60 s"
        sobra = PRAZO - 10.0
        assert sobra - 1.0 <= venceu - fechou <= sobra + 1.0, (
            f"venceu {venceu - fechou:.1f} s depois de o jogo soltar; sobravam {sobra:.0f} s"
        )
        assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3}
        assert gatilhos, "o vencimento depois do jogo não armou a cor"


@pytest.mark.usefixtures("config_isolado")
class TestQuemVoltaRetomaOLugar:
    """Régua 10: com o jogo aberto, o P2 volta aos 120 s e retoma o lugar 2."""

    def test_o_p2_volta_aos_120_segundos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bancada = montar(monkeypatch, 4)
        _volta(bancada)
        bancada.mesa.levantar(P2)
        for _ in range(60):
            _volta(bancada)
        with structlog.testing.capture_logs() as registros:
            bancada.mesa.sentar(P2, transporte="bt")
            _volta(bancada)
            _volta(bancada)
        assert _eventos(registros, "lugar_guardado_retomado"), "o P2 não retomou o lugar"
        assert bancada.a_tela() == {P1: 1, P2: 2, P3: 3, P4: 4}
        assert bancada.o_jogo_ve()[2] == P2, f"o jogo vê {bancada.o_jogo_ve()}"
        bancada.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
class TestORenumerarAgoraComOJogo:
    """Régua 11: o gesto do usuário renumera e recria, com o jogo aberto."""

    def test_o_gesto_dela_vale_com_o_jogo(
        self, monkeypatch: pytest.MonkeyPatch, gatilhos: list[str]
    ) -> None:
        bancada = montar(monkeypatch, 4)
        _volta(bancada)
        bancada.mesa.levantar(P2)
        for _ in range(5):
            _volta(bancada)
        assert bancada.a_tela() == {P1: 1, P3: 3, P4: 4}
        with structlog.testing.capture_logs() as registros:
            assert bancada.reg.soltar_os_lugares_guardados(motivo="renumerar") is True
            _volta(bancada)
            _volta(bancada)
        assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3}
        assert _eventos(registros, "coop_ordem_recriada"), "o co-op não recriou a mesa"
        assert gatilhos, "a cor não armou pelo «Renumerar agora»"
        bancada.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
class TestOsExternosSeguemAMesmaRegra:
    """Régua 12: um externo sai com o jogo aberto, 300 s, e o lugar dele não vence."""

    @pytest.mark.parametrize("ponte", ["antes-do-jogo", "com-o-jogo-aberto"])
    def test_o_externo_nao_vence_com_o_jogo(
        self, monkeypatch: pytest.MonkeyPatch, ponte: str
    ) -> None:
        relogio = Relogio()
        antes = ponte == "antes-do-jogo"
        bancada = montar(monkeypatch, 2, relogio=relogio, jogo=not antes)
        externo = ExternalIdentityRegistry(clock=relogio)
        # «com-o-jogo-aberto»: a ponte chega no meio da partida (o daemon que sobe com
        # o jogo já na autoridade), e o externo é segurado na hora.
        bancada.reg.set_external_hold_provider(externo.segurar_os_prazos)
        if antes:
            bancada.daemon.display_authority = "game"
            _volta(bancada, 0.0)
        assert externo.slot_for(EXTERNO) is not None
        externo.sync_connected([EXTERNO])
        _volta(bancada)
        with structlog.testing.capture_logs() as registros:
            externo.sync_connected([])
            for _ in range(int(TREZENTOS / TIQUE)):
                _volta(bancada)
                externo.sync_connected([])
        assert _eventos(registros, "external_lugar_guardado_venceu") == [], (
            "com o jogo aberto o lugar do externo venceu"
        )
        assert len(externo.lugares_da_mesa()) == 1

        bancada.daemon.display_authority = "daemon"
        _volta(bancada, 0.0)
        with structlog.testing.capture_logs() as registros:
            for _ in range(int(PRAZO / TIQUE) + 1):
                _volta(bancada)
                externo.sync_connected([])
        assert _eventos(registros, "external_lugar_guardado_venceu"), (
            "o jogo soltou e o lugar do externo não venceu no prazo"
        )


@pytest.mark.usefixtures("config_isolado")
class TestOPostoDoP1EsperaComOJogo:
    """O posto do P1 no backend: a reserva de 30 s espera enquanto a vaga espera."""

    def test_o_p2_nao_toma_o_posto_com_o_jogo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bancada = montar(monkeypatch, 3)
        bancada.mesa.levantar(P1)
        for _ in range(int(TREZENTOS / TIQUE)):
            bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None, (
            "o P2 tomou o posto do P1 com o jogo aberto"
        )
        assert bancada.inst.primary_uniq == P1
        assert bancada.a_tela() == {P2: 2, P3: 3}

        bancada.mesa.sentar(P1, transporte="usb")
        bancada.tique()
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() == P1
        assert bancada.a_tela() == {P1: 1, P2: 2, P3: 3}
