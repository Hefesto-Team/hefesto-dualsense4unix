"""A vibração fina bate a cada tiro (A-VIBRACAO-FINA-BATE-A-CADA-TIRO-01).

O rumble do jogo que só fala Xbox vira háptica fina como seno de NÍVEL; a
BORDA do rumble (o início de um tiro) vira um evento do motor do tato vivo, e
ele responde com um toque curto desenhado, no tocador do controle do tiro.
Tudo com dublês: o rumble é um par de números, o tocador é o de mentira da
NO-MODO-XBOX-TUDO-FUNCIONA-01, e o relógio é injetado.
"""
from __future__ import annotations

import array
import math
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit.test_no_modo_xbox_a_haptica_fina import (  # noqa: F401
    _MARCA,
    _QUATRO,
    _Mundo,
    _no_cabo_os_quatro,
    _no_radio_os_quatro,
    _Tocador,
    mesa,
    mundo,
)

P1 = "aa:bb:cc:00:00:11"
P2 = "aa:bb:cc:00:00:12"
_VIBRA = tv.Receita(vibracao_por_tiro=True)


def _bordas(sequencia: list[tuple[float, int, int]], uniq: str = P1) -> list[tv.Evento]:
    borda = tv.BordaDoRumble()
    eventos: list[tv.Evento] = []
    for instante, fraco, forte in sequencia:
        eventos += borda.ver(uniq, fraco, forte, instante)
    return eventos


def test_a_subida_de_0_a_200_em_8_ms_gera_um_toque() -> None:
    eventos = _bordas([(0.000, 0, 0), (0.004, 0, 100), (0.008, 0, 200)])
    assert len(eventos) == 1
    assert eventos[0].tipo == tv.TIPO_RUMBLE and eventos[0].lado == tv.LADO_ESQUERDO


def test_o_nivel_sustentado_de_200_nao_gera_dois() -> None:
    sequencia = [(0.0, 0, 0)] + [(0.01 + i * 0.05, 200, 200) for i in range(40)]
    assert len(_bordas(sequencia)) == 1


def test_o_pedido_do_cosmic_osk_gera_zero() -> None:
    sequencia = [(i * 0.05, 0, 0) for i in range(200)]
    assert _bordas(sequencia) == []


def test_o_mesmo_pedido_repetido_nao_e_borda() -> None:
    sequencia = [(i * 0.05, 160, 160) for i in range(100)]
    assert len(_bordas(sequencia)) <= 1


def test_a_rajada_que_solta_entre_tiros_da_um_toque_por_tiro() -> None:
    sequencia = []
    for i in range(10):
        sequencia += [(i * 0.1, 0, 220), (i * 0.1 + 0.04, 0, 0)]
    assert len(_bordas(sequencia)) == 10


def test_o_tiro_por_cima_do_motor_ligado_tambem_e_borda() -> None:
    sequencia = [(0.0, 0, 120), (0.2, 0, 220), (0.25, 0, 120), (0.4, 0, 220)]
    assert len(_bordas(sequencia)) == 3


class Toques:
    def __init__(self) -> None:
        self.feitos: list[tuple[str, float, str, int]] = []

    def __call__(self, uniq: str, energia: float, lado: str, duracao_ms: int) -> bool:
        self.feitos.append((uniq, energia, lado, duracao_ms))
        return True


def _xbox(_uniq: str) -> tv.EstadoDoCanal:
    return tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


def test_um_tiro_no_xbox_e_um_toque_no_controle_dele() -> None:
    toques = Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(toques)])
    for evento in _bordas([(0.0, 0, 0), (0.008, 0, 200)], P2):
        motor.anotar(evento)
    motor.tique(0.01, _xbox, _VIBRA)
    assert [(u, d) for u, _e, _l, d in toques.feitos] == [(P2, 40)]


def test_o_jogo_com_audio_nos_canais_3_e_4_gera_zero() -> None:
    toques = Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(toques)])
    estado = tv.EstadoDoCanal(
        modo=tv.MODO_DUALSENSE, visto_ha_s={"audio_do_jogo": 0.2},
        sessao_aberta=True, ha_jogo=True,
    )
    for evento in _bordas([(0.0, 0, 0), (0.008, 0, 200)]):
        motor.anotar(evento)
    motor.tique(0.01, lambda _u: estado, _VIBRA)
    assert toques.feitos == []


def test_a_rajada_de_tiros_para_no_teto_de_12_por_segundo() -> None:
    toques = Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(toques)])
    for i in range(25):
        agora = i * 0.04
        for evento in _bordas([(agora, 0, 0), (agora + 0.001, 0, 230)]):
            motor.anotar(evento)
        motor.tique(agora + 0.002, _xbox, _VIBRA)
    assert len(toques.feitos) == tv.TETO_POR_CONTROLE


def test_sem_a_vibracao_por_tiro_na_receita_nao_ha_toque() -> None:
    toques = Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(toques)])
    for evento in _bordas([(0.0, 0, 0), (0.008, 0, 200)]):
        motor.anotar(evento)
    motor.tique(0.01, _xbox, tv.Receita(reacao_ao_tiro="pulsa"))
    assert toques.feitos == []


def test_o_motor_desligado_nao_anota_o_rumble() -> None:
    motor = tv.TatoVivo([])
    daemon = SimpleNamespace(_tato_vivo=motor)
    tv.anotar_o_rumble(daemon, P1, 0, 200, 0.0)
    assert motor.contadores["eventos"] == 0
    motor.ligado = True
    tv.anotar_o_rumble(daemon, P1, 0, 0, 0.1)
    tv.anotar_o_rumble(daemon, P1, 0, 200, 0.2)
    assert motor.contadores["eventos"] == 1


def _rms(amostras: Any) -> float:
    return math.sqrt(sum(x * x for x in amostras) / max(1, len(amostras)))


def test_a_forma_do_toque_ataca_rapido_cai_e_acaba_em_silencio() -> None:
    toque = eh.forma_do_toque(0.8, 40)
    assert len(toque) == 48 * 40
    assert toque[0] == 0.0
    um_ciclo = 48000 // eh.FREQUENCIA_DO_TOQUE_HZ
    assert max(abs(x) for x in toque[: um_ciclo]) >= 0.4, "o ataque não chega em um ciclo"
    assert max(abs(x) for x in toque) <= 0.8 + 1e-6
    assert _rms(toque[-48 * 5:]) < 0.05 * _rms(toque[: 48 * 10])
    assert abs(toque[-1]) < 1e-3


@pytest.mark.parametrize("duracao", [10, 25, 60, 200])
def test_a_duracao_do_toque_vem_da_receita_e_fica_entre_25_e_60(duracao: int) -> None:
    receita = tv.Receita.de({"vibracao_por_tiro": True, "duracao_do_toque_ms": duracao})
    assert 25 <= receita.duracao_do_toque_ms <= 60


def _canais(bloco: bytes) -> list[array.array[float]]:
    quadros = array.array("f")
    quadros.frombytes(bloco)
    return [quadros[c::4] for c in range(4)]


def test_o_tocador_soma_o_toque_ao_bloco_e_volta_ao_silencio() -> None:
    tocador = eh.TocadorDoRumble(
        "x", argv_de=lambda _s, _r: [], conferir=lambda _r: None, folga_s=0.05
    )
    try:
        tocador.tocar_o_toque(1.0, tv.LADO_ESQUERDO, 40, sink="", dono=P1)
        blocos = [tocador.proximo_bloco((0, 0), (0, 0), 0) for _ in range(5)]
    finally:
        tocador.parar()
    com_toque = blocos[:4]
    assert all(max(abs(x) for x in _canais(b)[2]) > 0.0 for b in com_toque[:2])
    assert all(max(abs(x) for x in _canais(b)[3]) == 0.0 for b in com_toque)
    assert all(max(abs(x) for x in _canais(b)[0] + _canais(b)[1]) == 0.0 for b in blocos)
    assert blocos[4] == bytes(len(blocos[4])), "o toque deixou estado preso"
    assert not tocador.tocando_o_toque


def test_o_toque_por_cima_do_seno_nao_passa_de_um() -> None:
    base = eh.bloco_da_haptica(255, 255)
    misturado = eh.misturar_o_toque(base, eh.forma_do_toque(1.0, 40), 0, (2, 3))
    assert max(abs(x) for c in _canais(misturado) for x in c) <= 1.0


@pytest.fixture
def com_toque(mundo: _Mundo, monkeypatch: pytest.MonkeyPatch) -> _Mundo:  # noqa: F811
    def tocar_o_toque(self: Any, energia: float, lado: str, duracao_ms: int, *,
                      sink: str, dono: str) -> None:
        self.__dict__.setdefault("toques", []).append((dono, sink, lado, duracao_ms))

    monkeypatch.setattr(_Tocador, "tocar_o_toque", tocar_o_toque, raising=False)
    motor = tv.TatoVivo(tv.atuadores_de_producao(mundo.daemon))
    motor.ligado = True
    mundo.daemon._tato_vivo = motor
    return mundo


def _toques(m: _Mundo, uniq: str) -> list[Any]:
    tocador = _Tocador.criados.get(_MARCA[uniq])
    return list(getattr(tocador, "toques", []))


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_cada_controle_toca_o_seu_no_cabo_e_no_radio(
    com_toque: _Mundo, transporte: str, lugar: int
) -> None:
    m = com_toque
    controles = (
        _no_cabo_os_quatro(m) if transporte == "cabo" else _no_radio_os_quatro(m)
    )
    m.mesa.volta(*controles)
    uniq = _QUATRO[lugar - 1]
    m.rumble(uniq, 0, 0)
    m.rumble(uniq, 0, 220)
    m.mesa.volta(*controles)
    motor = m.daemon._tato_vivo
    motor.tique(1.0, _xbox, _VIBRA)
    assert [t[0] for t in _toques(m, uniq)] == [uniq]
    for outro in _QUATRO:
        if outro != uniq:
            assert _toques(m, outro) == [], f"o tiro de {uniq} tocou em {outro}"


def test_o_pad_uhid_nao_leva_a_borda_ao_motor(com_toque: _Mundo) -> None:
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    m = com_toque
    m.mesa.volta(*_no_cabo_os_quatro(m))
    pad = UhidDualSense(player=1)
    m.rumble(_QUATRO[0], 0, 220, vpad=pad)
    assert m.daemon._tato_vivo.contadores["eventos"] == 0


@pytest.mark.parametrize(
    ("mults", "par", "lado", "energia"),
    [
        ((1.0, 0.5), (0, 150), tv.LADO_ESQUERDO, 75),
        ((0.0, 1.0), (200, 200), tv.LADO_CENTRO, 200),
    ],
)
@pytest.mark.parametrize("transporte", ["cabo", "radio"])
@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_a_borda_e_o_lado_vem_do_pedido_cru_e_a_energia_da_barra(
    com_toque: _Mundo,
    monkeypatch: pytest.MonkeyPatch,
    transporte: str,
    lugar: int,
    mults: tuple[float, float],
    par: tuple[int, int],
    lado: str,
    energia: int,
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    m = com_toque
    monkeypatch.setattr(gp, "_mults_por_motor", lambda *_a: mults)
    controles = (
        _no_cabo_os_quatro(m) if transporte == "cabo" else _no_radio_os_quatro(m)
    )
    m.mesa.volta(*controles)
    uniq = _QUATRO[lugar - 1]
    m.rumble(uniq, 0, 0)
    m.rumble(uniq, *par)
    eventos = list(m.daemon._tato_vivo._fila)
    assert [(e.uniq, e.tipo, e.lado) for e in eventos] == [(uniq, tv.TIPO_RUMBLE, lado)]
    assert eventos[0].energia == pytest.approx(energia / 255.0)
