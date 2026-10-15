"""O-GATILHO-E-A-HAPTICA-DO-JOGO-VIRAM-EVENTOS-PARA-AS-EXTENSOES-01 — o lado do Hefesto.

O gatilho que o jogo escreve a cada controle sai como ``jogo.gatilho`` e o envelope da háptica
por áudio (canais 3-4) como ``jogo.haptica``; cada um é uma permissão à parte da porta das
modificações, e os três nomes sem fonte (``jogo.momento``, ``sistema.app_abriu``,
``sistema.hora``) ficam reservados. Backend, ``apply_game_trigger``, barramento, porta e
``AltoFalanteSubsystem`` são os do produto; o PCM é de mentira (quatro canais s16) e os relógios
são injetados.

AS MORDIDAS (executadas na implementação, com o md5 conferido na volta):

* o envelope ler os canais 1-2 no lugar dos 3-4 →
  ``test_o_envelope_le_os_canais_3_e_4_e_nao_os_1_e_2`` e
  ``test_o_envelope_de_um_motor_so_acende_o_lado_dele`` reprovam;
* tirar o teto de 50 por segundo do envelope → ``test_o_teto_do_envelope_segura_a_rajada`` reprova;
* tirar o teto de 50 por segundo do gatilho → ``test_o_teto_do_gatilho_segura_a_rajada`` reprova;
* ``apply_game_trigger`` sem dizer o gatilho → os testes de publicação por jogador reprovam;
* o fim da sessão sem o ``desligado`` → ``test_o_fim_da_sessao_desliga_so_o_controle_dele`` reprova;
* o jogo fechado sem zerar → ``test_o_jogo_que_fecha_zera_o_gatilho_e_o_envelope`` reprova;
* o zero por silêncio fora → ``test_a_fonte_que_seca_manda_o_zero`` reprova;
* a assinatura sem a permissão (os tópicos entregues a qualquer um) →
  ``test_a_modificacao_so_recebe_o_que_a_permissao_dela_deixa`` reprova;
* o ouvido do cabo sem o envelope (a classe do produto sem a subclasse) →
  ``test_o_ouvido_do_cabo_diz_o_envelope_sem_segundo_gravador`` reprova;
* a ponte do rádio sem a fonte espiada →
  ``test_a_ponte_do_radio_diz_o_envelope_da_fonte_que_ela_le`` reprova.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import TOPICOS_RESERVADOS, EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import gatilho_do_jogo as gj
from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import envelope_da_haptica as eh
from hefesto_dualsense4unix.mods.manifesto import TOPICOS_DE_LEITURA, permissao_valida
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from tests.unit.test_a_forca_da_vibracao_de_cada_controle_sai_de_um_funil_so import (
    UNIQS,
    _Mesa,
)
from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
    _Controle,
    _EndpointDeMentira,
    _PonteDeMentira,
)

NUMERO_DO_JOGADOR = {u: i + 1 for i, u in enumerate(UNIQS)}
TAXA = 48_000
JANELA = 960  # 20 ms a 48 kHz
# Meia escala: o RMS dá 0,5 (a senoide de fundo de escala vale 1).
MEIA = 11585


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def monotonic(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos

    def __call__(self) -> float:
        return self.agora


class _Escuta:
    def __init__(self, bus: EventBus, topico: str) -> None:
        self.fila = bus.subscribe(topico)

    def tudo(self) -> list[Any]:
        saida: list[Any] = []
        while not self.fila.empty():
            saida.append(self.fila.get_nowait())
        return saida


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(gj, "time", SimpleNamespace(monotonic=r.monotonic))
    monkeypatch.setattr(eh, "time", SimpleNamespace(monotonic=r.monotonic))
    return r


@pytest.fixture
def mesa(tmp_path: Path, relogio: _Relogio) -> _Mesa:
    m = _Mesa(tmp_path)
    m.daemon.bus = EventBus()
    m.daemon.appid_em_cena = None
    m.daemon.identity_registry = SimpleNamespace(
        numero_da_lampada=lambda uniq, assign=True: NUMERO_DO_JOGADOR.get(uniq)
    )
    return m


# Os blocos de 11 bytes, como a referência canônica os empacota.

def _mascara(*zonas: int) -> bytes:
    m = sum(1 << z for z in zonas)
    return bytes([m & 0xFF, m >> 8])


def _resistencia(zona: int, forca: int) -> bytes:
    empacotado = (forca - 1) << (3 * zona)
    return bytes([0x21]) + _mascara(zona) + empacotado.to_bytes(4, "little") + bytes(4)


def _arma(inicio: int, fim: int, forca: int) -> bytes:
    return bytes([0x25]) + _mascara(inicio, fim) + bytes([forca - 1]) + bytes(7)


def _arco(zona: int, forca: int, encaixe: int) -> bytes:
    return bytes([0x22]) + _mascara(zona) + bytes([(forca - 1) | ((encaixe - 1) << 3)]) + bytes(7)


def _galope(zona: int, pes: int, frequencia: int) -> bytes:
    return bytes([0x23]) + _mascara(zona) + bytes([pes, frequencia]) + bytes(6)


def _vibracao(zona: int, amplitude: int, frequencia: int) -> bytes:
    empacotado = (amplitude - 1) << (3 * zona)
    return (
        bytes([0x26]) + _mascara(zona) + empacotado.to_bytes(4, "little") + bytes(2)
        + bytes([frequencia, 0])
    )


def _metralhadora(zona: int, amp_a: int, amp_b: int) -> bytes:
    return bytes([0x27]) + _mascara(zona) + bytes([amp_a | (amp_b << 3)]) + bytes(7)


DESLIGADO = bytes(11)
assert all(len(b) == 11 for b in (
    _resistencia(3, 6), _arma(2, 5, 4), _arco(1, 4, 2), _galope(4, 3, 5),
    _vibracao(1, 8, 20), _metralhadora(2, 2, 5),
))


def _eventos(mesa: _Mesa) -> _Escuta:
    return _Escuta(mesa.daemon.bus, EventTopic.JOGO_GATILHO)


# 1. A decodificação do bloco.

@pytest.mark.parametrize(
    ("bloco", "esperado"),
    [
        (_resistencia(3, 6), ("resistencia", 0.75, 0.3333)),  # (noqa-acento): contrato ASCII
        (_arma(2, 5, 4), ("arma", 0.5, 0.2222)),
        (_arco(1, 4, 2), ("arco", 0.5, 0.1111)),
        (_galope(4, 3, 5), ("galope", 1.0, 0.4444)),
        (_vibracao(1, 8, 20), ("vibracao", 1.0, 0.1111)),
        (_metralhadora(2, 2, 5), ("metralhadora", 0.75, 0.2222)),
        (DESLIGADO, ("desligado", 0.0, 0.0)),
        (bytes([0x05]) + bytes(10), ("desligado", 0.0, 0.0)),
        (bytes([0x21]) + bytes(10), ("desligado", 0.0, 0.0)),
        (bytes([0x01, 0, 0, 40]) + bytes(7), ("outro", 1.0, 0.0)),
        (b"\x21\x01", ("desligado", 0.0, 0.0)),
    ],
    ids=[
        "resistencia",  # (noqa-acento): contrato ASCII
        "arma", "arco", "galope", "vibracao", "metralhadora",
        "off-0", "off-5", "mascara-vazia", "legado", "curto",
    ],
)
def test_o_bloco_vira_modo_forca_e_posicao(
    bloco: bytes, esperado: tuple[str, float, float]
) -> None:
    assert gj.decodificar_o_bloco(bloco) == esperado


# 2. Cada jogador, com o uniq e o número dele, no cabo e no Bluetooth.

def test_cada_jogador_publica_o_gatilho_dele(mesa: _Mesa) -> None:
    escuta = _eventos(mesa)

    for i, uniq in enumerate(UNIQS):
        gp.apply_game_trigger(
            mesa.daemon, "left" if i % 2 == 0 else "right", _resistencia(i + 1, 5),
            target_uniq=uniq,
        )

    eventos = escuta.tudo()
    assert [e["uniq"] for e in eventos] == list(UNIQS), "o evento saiu com o endereço de outro"
    assert [e["jogador"] for e in eventos] == [1, 2, 3, 4]
    assert [e["lado"] for e in eventos] == ["esquerdo", "direito", "esquerdo", "direito"]
    assert {e["modo"] for e in eventos} == {"resistencia"}  # (noqa-acento): contrato ASCII
    assert [e["forca"] for e in eventos] == [0.625] * 4
    assert [e["posicao"] for e in eventos] == [round((i + 1) / 9, 4) for i in range(4)]
    assert all(isinstance(e["t"], float) for e in eventos)


def test_o_gatilho_do_jogo_sai_mesmo_quando_a_replica_ao_fisico_e_descartada(
    mesa: _Mesa,
) -> None:
    mesa.daemon.controller = SimpleNamespace()  # sem a API por-uniq: a réplica cai
    escuta = _eventos(mesa)

    gp.apply_game_trigger(mesa.daemon, "left", _arma(2, 5, 4), target_uniq=UNIQS[2])

    eventos = escuta.tudo()
    assert len(eventos) == 1 and eventos[0]["modo"] == "arma" and eventos[0]["jogador"] == 3


def test_o_mesmo_bloco_reescrito_nao_vira_evento_novo(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _eventos(mesa)
    bloco = _resistencia(3, 6)

    for _ in range(5):
        gp.apply_game_trigger(mesa.daemon, "left", bloco, target_uniq=UNIQS[0])
        relogio.avancar(0.05)
    gp.apply_game_trigger(mesa.daemon, "left", _resistencia(3, 7), target_uniq=UNIQS[0])
    gp.apply_game_trigger(mesa.daemon, "right", bloco, target_uniq=UNIQS[0])

    eventos = escuta.tudo()
    assert [(e["lado"], e["forca"]) for e in eventos] == [
        ("esquerdo", 0.75), ("esquerdo", 0.875), ("direito", 0.75),
    ]


def test_o_gatilho_que_nunca_ligou_nao_diz_desligado(mesa: _Mesa) -> None:
    escuta = _eventos(mesa)

    gp.apply_game_trigger(mesa.daemon, "left", DESLIGADO, target_uniq=UNIQS[0])

    assert escuta.tudo() == []


def test_o_teto_do_gatilho_segura_a_rajada(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _eventos(mesa)

    for forca in range(1, 9):  # 8 blocos em 8 ms
        gp.apply_game_trigger(mesa.daemon, "left", _resistencia(3, forca), target_uniq=UNIQS[0])
        relogio.avancar(0.001)
    assert len(escuta.tudo()) == 1, "a rajada passou do teto de 50 por segundo"

    relogio.avancar(0.02)
    gj.bater_o_gatilho(mesa.daemon)
    depois = escuta.tudo()
    assert [e["forca"] for e in depois] == [1.0], "o último valor da rajada não chegou"


# 3. O fim: sessão do pad, jogo fechado.

def test_o_fim_da_sessao_desliga_so_o_controle_dele(mesa: _Mesa) -> None:
    for uniq in UNIQS[:2]:
        gp.apply_game_trigger(mesa.daemon, "left", _arma(2, 5, 4), target_uniq=uniq)
        gp.apply_game_trigger(mesa.daemon, "right", _arma(2, 5, 4), target_uniq=uniq)
    escuta = _eventos(mesa)

    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[1])

    eventos = escuta.tudo()
    assert sorted((e["uniq"], e["lado"], e["modo"]) for e in eventos) == [
        (UNIQS[1], "direito", "desligado"), (UNIQS[1], "esquerdo", "desligado"),
    ]
    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[1])
    assert escuta.tudo() == [], "o zero saiu duas vezes"


def test_o_zero_que_o_teto_atrasou_chega_no_fim_da_sessao(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    gp.apply_game_trigger(mesa.daemon, "left", _arma(2, 5, 4), target_uniq=UNIQS[0])
    gp.apply_game_trigger(mesa.daemon, "left", DESLIGADO, target_uniq=UNIQS[0])  # atrasado
    escuta = _eventos(mesa)

    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[0])

    assert [e["modo"] for e in escuta.tudo()] == ["desligado"]


def _tique(daemon: Any) -> None:
    gp._bater_os_eventos_do_jogo(daemon)


def _pcm_de(canais_ligados: tuple[int, ...], nivel: int, quadros: int, lado: int = 0) -> bytes:
    """Quatro canais s16: o nível nos canais pedidos (índices 0-3), zero nos outros."""
    quadro = [nivel if c in canais_ligados else 0 for c in range(4)]
    return struct.pack("<4h", *quadro) * quadros


def test_o_jogo_que_fecha_zera_o_gatilho_e_o_envelope(mesa: _Mesa, relogio: _Relogio) -> None:
    mesa.daemon.appid_em_cena = 570
    _tique(mesa.daemon)
    gp.apply_game_trigger(mesa.daemon, "left", _arma(2, 5, 4), target_uniq=UNIQS[0])
    fonte = eh.espiar_a_haptica(
        mesa.daemon, UNIQS[1], lambda _n: _pcm_de((2, 3), MEIA, JANELA), taxa=TAXA
    )
    fonte(0)
    gatilhos, hapticas = _eventos(mesa), _Escuta(mesa.daemon.bus, EventTopic.JOGO_HAPTICA)
    relogio.avancar(0.1)

    mesa.daemon.appid_em_cena = None  # o jogo fechou
    _tique(mesa.daemon)

    assert [(e["uniq"], e["modo"]) for e in gatilhos.tudo()] == [(UNIQS[0], "desligado")]
    assert [(e["uniq"], e["intensidade"]) for e in hapticas.tudo()] == [(UNIQS[1], [0.0, 0.0])]
    _tique(mesa.daemon)
    assert gatilhos.tudo() == [] and hapticas.tudo() == [], "o zero saiu de novo no tique seguinte"


# 4. O envelope: o PCM de quatro canais.

def _envelope(relogio: _Relogio) -> tuple[eh.EnvelopeDaHaptica, list[tuple[eh.Nivel, float]]]:
    saiu: list[tuple[eh.Nivel, float]] = []
    return (
        eh.EnvelopeDaHaptica(lambda n, t: saiu.append((n, t)), taxa=TAXA, relogio=relogio),
        saiu,
    )


def test_o_envelope_le_os_canais_3_e_4_e_nao_os_1_e_2(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    env.alimentar(_pcm_de((0, 1), 30000, JANELA * 3))  # só o som da frente
    assert saiu == [], "a voz do jogo (canais 1-2) virou intensidade"

    env.alimentar(_pcm_de((2, 3), MEIA, JANELA * 3))  # os motores
    assert saiu and saiu[0][0] == (0.5, 0.5)


def test_o_envelope_de_um_motor_so_acende_o_lado_dele(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    env.alimentar(_pcm_de((2,), MEIA, JANELA))
    relogio.avancar(0.1)
    env.alimentar(_pcm_de((3,), MEIA, JANELA))

    assert [n for n, _ in saiu] == [(0.5, 0.0), (0.0, 0.5)]


def test_o_envelope_vai_de_zero_a_um(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    env.alimentar(_pcm_de((2, 3), 32767, JANELA))

    assert saiu[0][0] == (1.0, 1.0)


def test_o_ruido_abaixo_do_passo_nao_vira_evento(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    for ruido in (MEIA, MEIA + 40, MEIA - 40, MEIA + 20):
        env.alimentar(_pcm_de((2, 3), ruido, JANELA))
        relogio.avancar(0.02)

    assert len(saiu) == 1


def test_o_teto_do_envelope_segura_a_rajada(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    # 100 janelas que alternam o nível, chegando a 5 ms uma da outra (o dobro do tempo real).
    for i in range(100):
        env.alimentar(_pcm_de((2, 3), MEIA if i % 2 == 0 else 3000, JANELA))
        relogio.avancar(0.005)

    assert len(saiu) <= 26, f"{len(saiu)} eventos em meio segundo: passou do teto de 50/s"
    relogio.avancar(0.05)
    env.bater()
    ultimo = round(3000 * 2 ** 0.5 / 32768 / 0.02) * 0.02
    assert saiu[-1][0][0] == pytest.approx(ultimo, abs=1e-3), "o último nível da rajada não chegou"


def test_a_batida_repete_a_cada_250_ms_enquanto_nao_e_zero(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)

    for _ in range(100):  # um segundo de motor constante, em tempo real
        env.alimentar(_pcm_de((2, 3), MEIA, JANELA))
        relogio.avancar(0.01)
        env.alimentar(_pcm_de((2, 3), MEIA, JANELA))
        relogio.avancar(0.01)
        env.bater()

    assert 4 <= len(saiu) <= 9, f"{len(saiu)} eventos em 2 s: nem uma batida de 250 ms nem o dedupe"
    assert {n for n, _ in saiu} == {(0.5, 0.5)}


def test_a_fonte_que_seca_manda_o_zero(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)
    env.alimentar(_pcm_de((2, 3), MEIA, JANELA))
    assert saiu[-1][0] == (0.5, 0.5)

    relogio.avancar(0.3)
    env.bater()
    assert saiu[-1][0] == (0.5, 0.5), "o zero saiu antes de meio segundo de silêncio do cano"

    relogio.avancar(0.4)
    env.bater()
    assert saiu[-1][0] == (0.0, 0.0)
    total = len(saiu)
    relogio.avancar(1.0)
    env.bater()
    assert len(saiu) == total, "o zero se repetiu"


def test_o_silencio_do_jogo_manda_o_zero_na_hora(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)
    env.alimentar(_pcm_de((2, 3), MEIA, JANELA))
    relogio.avancar(0.05)

    env.alimentar(_pcm_de((2, 3), 0, JANELA))

    assert [n for n, _ in saiu] == [(0.5, 0.5), (0.0, 0.0)]


def test_o_pcm_quebrado_no_meio_do_quadro_nao_perde_o_alinhamento(relogio: _Relogio) -> None:
    env, saiu = _envelope(relogio)
    pcm = _pcm_de((2, 3), MEIA, JANELA)

    env.alimentar(pcm[:7])
    env.alimentar(pcm[7:])

    assert [n for n, _ in saiu] == [(0.5, 0.5)]


def test_um_envelope_por_controle_com_o_jogador_dele(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _Escuta(mesa.daemon.bus, EventTopic.JOGO_HAPTICA)
    def _fonte_de(nivel: int) -> Any:
        return lambda _n: _pcm_de((2, 3), nivel, JANELA)

    fontes = {
        uniq: eh.espiar_a_haptica(mesa.daemon, uniq, _fonte_de(nivel), taxa=TAXA)
        for uniq, nivel in zip(UNIQS, (MEIA, MEIA // 2, MEIA // 4, 0), strict=True)
    }

    for fonte in fontes.values():
        assert fonte(0)

    eventos = escuta.tudo()
    esperados = [(u, i + 1) for i, u in enumerate(UNIQS[:3])]
    assert [(e["uniq"], e["jogador"]) for e in eventos] == esperados
    assert [e["intensidade"][0] for e in eventos] == [0.5, 0.24, 0.12]
    assert all(isinstance(e["t"], float) for e in eventos)


def test_o_fim_da_sessao_zera_o_envelope_dele(mesa: _Mesa, relogio: _Relogio) -> None:
    fonte = eh.espiar_a_haptica(
        mesa.daemon, UNIQS[0], lambda _n: _pcm_de((2, 3), MEIA, JANELA), taxa=TAXA
    )
    fonte(0)
    escuta = _Escuta(mesa.daemon.bus, EventTopic.JOGO_HAPTICA)

    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[0])

    assert [e["intensidade"] for e in escuta.tudo()] == [[0.0, 0.0]]


# 5. As duas pontas do PCM: o rádio (Bluetooth) e o ouvido da placa (cabo). Um leitor só.

@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch, mesa: _Mesa) -> Any:
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as ep
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from tests.unit.porta_de_mentira import todo_pad_tem_porta

    _PonteDeMentira.criadas = []
    _EndpointDeMentira.criados = []
    _EndpointDeMentira.quedas = []
    pedidos: list[dict[str, Any]] = []
    pcm = _pcm_de((2, 3), MEIA, JANELA)

    def _fonte(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        pedidos.append({"no": id_do_no, **kw})
        entregues = iter([pcm, pcm])
        return (lambda _n: next(entregues, b"")), f"gravador:{id_do_no}", ""

    monkeypatch.setattr(afb, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(afb, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(ep, "EndpointDeHaptica", _EndpointDeMentira)
    todo_pad_tem_porta(monkeypatch)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_ha_jogo_aberto", lambda self: False)
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida",
        lambda self, controles: {str(getattr(c, "uniq", "")).lower() for c in controles},
    )

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    controles = [_Controle(UNIQS[0], "/dev/hidraw1", "bluetooth")]
    sub = mod.AltoFalanteSubsystem(
        daemon=mesa.daemon, gerenciador=_Ger(), fonte_de_controles=lambda: list(controles)
    )
    tocando = _tocando(monkeypatch)
    return SimpleNamespace(sub=sub, controles=controles, pedidos=pedidos, tocando=tocando)


def _tocando(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    tocando: dict[str, bool] = {}
    monkeypatch.setattr(afb, "sink_esta_tocando", lambda nome, *a, **k: tocando.get(nome, False))
    return tocando


def test_a_ponte_do_radio_diz_o_envelope_da_fonte_que_ela_le(bancada: Any, mesa: _Mesa) -> None:
    escuta = _Escuta(mesa.daemon.bus, EventTopic.JOGO_HAPTICA)
    bancada.tocando[f"endpoint::{UNIQS[0]}"] = True

    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.fonte_de_haptica is not None
    assert escuta.tudo() == []

    assert ponte.fonte_de_haptica(1024)  # a ponte lê a fonte dela, e o envelope espia o bloco

    eventos = escuta.tudo()
    assert [(e["uniq"], e["jogador"], e["intensidade"]) for e in eventos] == [
        (UNIQS[0], 1, [0.5, 0.5])
    ]
    monitores = [p for p in bancada.pedidos if p.get("canais") == 4]
    assert len(monitores) == 1, "o envelope abriu um segundo gravador no endpoint"


def test_o_ouvido_do_cabo_diz_o_envelope_sem_segundo_gravador(
    bancada: Any, mesa: _Mesa
) -> None:
    escuta = _Escuta(mesa.daemon.bus, EventTopic.JOGO_HAPTICA)

    bancada.sub._casar_os_ouvidos_das_placas({UNIQS[0]: "alsa_output.placa-de-mentira"})
    ouvido = bancada.sub._ouvidos_das_placas[UNIQS[0]]
    ouvido._fio.join(timeout=3)

    assert isinstance(ouvido, afb.OuvidoDaPlaca), "o ouvido do cabo deixou de ser o do produto"
    assert [e["intensidade"] for e in escuta.tudo()] == [[0.5, 0.5]]
    assert len(bancada.pedidos) == 1, "o envelope abriu um segundo gravador na placa"
    assert bancada.pedidos[0]["no"] == "alsa_output.placa-de-mentira"
    ouvido.descer()


def test_o_ouvido_dublado_entra_como_veio() -> None:
    class _Dubla:
        def __init__(self, *, placa: str, uniq: str) -> None:
            self.placa, self.uniq = placa, uniq

    ouvido = eh.ouvido_da_placa(_Dubla, "placa", "u", SimpleNamespace())

    assert type(ouvido) is _Dubla


# 6. A porta: a permissão e a entrega.

def test_as_permissoes_novas_existem_e_cada_uma_entrega_o_seu() -> None:
    assert permissao_valida("ler:jogo.gatilho") and permissao_valida("ler:jogo.haptica")
    assert TOPICOS_DE_LEITURA["jogo.gatilho"] == (EventTopic.JOGO_GATILHO,)
    assert TOPICOS_DE_LEITURA["jogo.haptica"] == (EventTopic.JOGO_HAPTICA,)


def test_os_tres_nomes_sem_fonte_ficam_reservados_e_sem_permissao() -> None:
    esperados = frozenset({"jogo.momento", "sistema.app_abriu", "sistema.hora"})
    assert esperados == TOPICOS_RESERVADOS
    dos_eventos = {v for v in vars(EventTopic).values() if isinstance(v, str)}
    for nome in TOPICOS_RESERVADOS:
        assert nome not in TOPICOS_DE_LEITURA
        assert not permissao_valida(f"ler:{nome}")
        assert nome not in dos_eventos


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def evento(self) -> dict[str, Any]:
        recebido: dict[str, Any] = json.loads(self.arquivo.readline())
        return recebido

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


def test_a_modificacao_so_recebe_o_que_a_permissao_dela_deixa() -> None:
    async def corrida() -> None:
        with tempfile.TemporaryDirectory(prefix="gh") as pasta:
            curto = Path(pasta)
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(
                curto / "mods.sock", bus, escritor=escritor,
                o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: UNIQS[0],
            )
            await porta.iniciar()
            porta.registrar("so-gatilho", "ficha", os.getpid(), ["ler:jogo.gatilho"])
            porta.registrar("so-haptica", "ficha", os.getpid(), ["ler:jogo.haptica"])
            sem = _Cliente(curto / "mods.sock")
            com = _Cliente(curto / "mods.sock")
            try:
                await asyncio.to_thread(sem.pedir, "mod.ola", {"ficha": "so-gatilho"})
                await asyncio.to_thread(com.pedir, "mod.ola", {"ficha": "so-haptica"})
                recusa = await asyncio.to_thread(
                    sem.pedir, "eventos.assinar", {"topicos": ["jogo.haptica"]})
                assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
                assert recusa["error"]["message"] == "falta a permissão ler:jogo.haptica"
                reservado = await asyncio.to_thread(
                    sem.pedir, "eventos.assinar", {"topicos": ["jogo.momento"]})
                assert "error" in reservado
                ok = await asyncio.to_thread(
                    sem.pedir, "eventos.assinar", {"topicos": ["jogo.gatilho"]})
                assert ok["result"] == {"assinados": ["jogo.gatilho"]}
                ok2 = await asyncio.to_thread(
                    com.pedir, "eventos.assinar", {"topicos": ["jogo.haptica"]})
                assert ok2["result"] == {"assinados": ["jogo.haptica"]}

                bus.publish(EventTopic.JOGO_HAPTICA, {
                    "uniq": UNIQS[2], "jogador": 3, "intensidade": [0.5, 0.25], "t": 1.0})
                bus.publish(EventTopic.JOGO_GATILHO, {
                    "uniq": UNIQS[1], "jogador": 2, "lado": "direito", "modo": "arma",
                    "forca": 0.5, "posicao": 0.2, "t": 2.0})
                haptica = await asyncio.wait_for(asyncio.to_thread(com.evento), 3)
                gatilho = await asyncio.wait_for(asyncio.to_thread(sem.evento), 3)
            finally:
                sem.fechar()
                com.fechar()
                await porta.parar()
            assert haptica["params"]["nome"] == EventTopic.JOGO_HAPTICA
            assert haptica["params"]["dados"]["intensidade"] == [0.5, 0.25]
            assert haptica["params"]["uniq"] == UNIQS[2]
            assert gatilho["params"]["nome"] == EventTopic.JOGO_GATILHO
            assert gatilho["params"]["dados"]["modo"] == "arma"
            assert gatilho["params"]["uniq"] == UNIQS[1]

    asyncio.run(corrida())


def test_a_tabela_do_gatilho_nasce_uma_so_com_dois_controles_juntos(mesa: _Mesa) -> None:
    barreira = threading.Barrier(2)

    def _um(uniq: str) -> None:
        barreira.wait()
        gp.apply_game_trigger(mesa.daemon, "left", _arma(2, 5, 4), target_uniq=uniq)

    fios = [threading.Thread(target=_um, args=(u,)) for u in UNIQS[:2]]
    escuta = _eventos(mesa)
    for f in fios:
        f.start()
    for f in fios:
        f.join()

    assert sorted(e["uniq"] for e in escuta.tudo()) == sorted(UNIQS[:2])
