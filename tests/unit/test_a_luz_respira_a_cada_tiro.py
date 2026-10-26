"""A luz respira a cada tiro (A-LUZ-RESPIRA-A-CADA-TIRO-01).

A reação ao tiro da receita do estilo («pulsa» ou «evento») vira, onde o jogo
cala a barra, um pico de brilho sobre a cor de identidade do controle (ou a
cor do evento) que volta sozinho. Teto de 3 subidas por segundo (WCAG 2.3.1):
a rajada funde num brilho contínuo. Relógio injetado e um backend de mentira
que anota cada cor pintada e cada sessão devolvida.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

P1 = "aa:bb:cc:00:00:31"
P2 = "aa:bb:cc:00:00:32"
P3 = "aa:bb:cc:00:00:33"
P4 = "aa:bb:cc:00:00:34"
QUATRO = (P1, P2, P3, P4)
CORES = {
    P1: (0, 0, 160),
    P2: (160, 0, 0),
    P3: (0, 160, 0),
    P4: (160, 0, 160),
}
_PULSA = tv.Receita(reacao_ao_tiro="pulsa")
_EVENTO = tv.Receita(reacao_ao_tiro="evento", cor_do_evento=(255, 140, 0))


class Backend:
    def __init__(self, cores: dict[str, tuple[int, int, int]] | None = None) -> None:
        self.cores = dict(cores or CORES)
        self.pintadas: list[tuple[float, str, tuple[int, int, int]]] = []
        self.sessoes: list[str] = []
        self.agora = 0.0

    def pintar(self, uniq: str, cor: tuple[int, int, int]) -> bool:
        self.pintadas.append((self.agora, uniq, cor))
        return True

    def cor_de(self, uniq: str) -> tuple[int, int, int] | None:
        return self.cores.get(uniq)

    def devolver(self, uniq: str) -> bool:
        self.sessoes.append(uniq)
        return True


def _xbox(_uniq: str) -> tv.EstadoDoCanal:
    return tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


def _motor(backend: Backend) -> tv.TatoVivo:
    return tv.TatoVivo([tv.AtuadorDaLuz(backend.pintar, backend.cor_de, backend.devolver)])


def _tiros(
    motor: tv.TatoVivo,
    backend: Backend,
    instantes: list[float],
    *,
    uniq: str = P1,
    receita: tv.Receita = _PULSA,
    estado_de: Any = _xbox,
    fim: float | None = None,
) -> None:
    """Atira nos instantes e roda o laço de 60 Hz até ``fim``."""
    fila = sorted(instantes)
    t = 0.0
    ultimo = fim if fim is not None else (fila[-1] + 1.0 if fila else 1.0)
    while t <= ultimo:
        while fila and fila[0] <= t:
            motor.anotar(tv.Evento(fila.pop(0), uniq, tv.TIPO_DEDO, tv.LADO_DIREITO))
        backend.agora = t
        motor.tique(t, estado_de, receita)
        t = round(t + tv.INTERVALO_S, 6)


def _subidas(backend: Backend, uniq: str = P1) -> list[float]:
    base = CORES[uniq]
    return [t for t, u, cor in backend.pintadas if u == uniq and cor != base]


def _no_maximo_tres_por_segundo(instantes: list[float]) -> bool:
    return all(
        sum(1 for outro in instantes if t <= outro < t + 1.0) <= tv.TETO_DA_LUZ_POR_S
        for t in instantes
    )


def test_o_pico_e_a_cor_do_perfil_no_brilho_maximo() -> None:
    assert tv.pico_do_pulso((0, 0, 160)) == (0, 0, 255)
    assert tv.pico_do_pulso((100, 40, 0)) == (255, 102, 0)


def test_a_cor_que_ja_esta_no_maximo_mergulha_em_vez_de_subir() -> None:
    assert tv.pico_do_pulso((0, 0, 255)) == (0, 0, 89)


def test_a_barra_apagada_nao_respira() -> None:
    assert tv.pico_do_pulso((0, 0, 0)) is None
    backend = Backend({P1: (0, 0, 0)})
    _tiros(_motor(backend), backend, [0.1])
    assert backend.pintadas == []


def test_um_tiro_da_um_pulso_e_a_cor_volta() -> None:
    backend = Backend()
    _tiros(_motor(backend), backend, [0.1], fim=0.6)
    assert [cor for _t, _u, cor in backend.pintadas] == [(0, 0, 255)]
    assert backend.sessoes == [P1]


def test_a_volta_vem_em_tempo_limitado_depois_do_ultimo_tiro() -> None:
    backend = Backend()
    voltas: list[float] = []
    devolver = backend.devolver

    def anotando(uniq: str) -> bool:
        voltas.append(backend.agora)
        return devolver(uniq)

    motor = tv.TatoVivo([tv.AtuadorDaLuz(backend.pintar, backend.cor_de, anotando)])
    _tiros(motor, backend, [0.1, 0.15, 0.2], fim=1.0)
    assert len(voltas) == 1
    assert voltas[0] - 0.2 <= tv.SEGURA_DA_LUZ_S + 2 * tv.INTERVALO_S


def test_a_opcao_evento_troca_a_cor_pela_do_evento() -> None:
    backend = Backend()
    _tiros(_motor(backend), backend, [0.1], receita=_EVENTO, fim=0.6)
    assert [cor for _t, _u, cor in backend.pintadas] == [(255, 140, 0)]
    assert backend.sessoes == [P1]


def test_a_opcao_parada_nunca_escreve() -> None:
    backend = Backend()
    _tiros(_motor(backend), backend, [0.1, 0.5, 0.9], receita=tv.Receita(vibracao_por_tiro=True))
    assert backend.pintadas == []
    assert backend.sessoes == []


def test_a_rajada_de_20_por_segundo_funde_num_brilho_continuo() -> None:
    backend = Backend()
    tiros = [round(0.1 + i * 0.05, 3) for i in range(40)]
    _tiros(_motor(backend), backend, tiros, fim=3.0)
    subidas = _subidas(backend)
    assert len(subidas) == 1, subidas
    assert backend.sessoes == [P1]


def test_tiros_espacados_nao_passam_de_3_subidas_por_segundo() -> None:
    backend = Backend()
    tiros = [round(0.1 + i * 0.3, 3) for i in range(10)]
    _tiros(_motor(backend), backend, tiros, fim=4.0)
    subidas = _subidas(backend)
    assert _no_maximo_tres_por_segundo(subidas), subidas
    assert len(subidas) >= 6, "o teto engoliu mais do que três por segundo"


def test_o_jogo_que_manda_a_barra_gera_zero_escrita() -> None:
    backend = Backend()

    def pintando(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"lightbar": 0.3},
            sessao_aberta=True, ha_jogo=True,
        )

    _tiros(_motor(backend), backend, [0.1, 0.5, 0.9], estado_de=pintando)
    assert backend.pintadas == []


def test_o_jogo_que_escreveu_o_gatilho_segura_a_barra_pela_sessao() -> None:
    backend = Backend()

    def gatilho(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"trigger": 12.0},
            sessao_aberta=True, ha_jogo=True,
        )

    _tiros(_motor(backend), backend, [0.1, 0.5, 0.9], estado_de=gatilho)
    assert backend.pintadas == []


def test_a_cor_trocada_enquanto_o_jogo_segurava_a_barra_e_a_que_pulsa() -> None:
    """O tiro recusado (o jogo com a barra) não guarda a cor: o pulso seguinte lê a de agora."""
    backend = Backend()
    luz = tv.AtuadorDaLuz(backend.pintar, backend.cor_de, backend.devolver)

    def pintando(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"lightbar": 0.3},
            sessao_aberta=True, ha_jogo=True,
        )

    _tiros(tv.TatoVivo([luz]), backend, [0.1], estado_de=pintando)
    assert backend.pintadas == []
    backend.cores[P1] = (160, 0, 0)
    _tiros(tv.TatoVivo([luz]), backend, [0.1], fim=0.6)
    assert [cor for _t, _u, cor in backend.pintadas] == [(255, 0, 0)]


def test_no_modo_nativo_a_barra_e_do_aparelho() -> None:
    backend = Backend()

    def nativo(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(modo=tv.MODO_NATIVO, ha_jogo=True)

    _tiros(_motor(backend), backend, [0.1, 0.5], estado_de=nativo)
    assert backend.pintadas == []


def test_o_jogo_que_toma_a_barra_no_meio_do_pulso_fica_com_ela() -> None:
    backend = Backend()
    motor = _motor(backend)
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO, tv.LADO_DIREITO))
    motor.tique(0.0, _xbox, _PULSA)

    def tomou(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"lightbar": 0.01},
            sessao_aberta=True, ha_jogo=True,
        )

    motor.tique(0.5, tomou, _PULSA)
    assert backend.sessoes == [], "a volta apagou a cor que o jogo acabou de pintar"
    assert len(backend.pintadas) == 1


def test_a_sessao_so_volta_quando_o_motor_solta_o_ultimo_canal() -> None:
    encerradas: list[str] = []
    sessao = tv.SessaoDoMotor(encerradas.append)
    sessao.tomar(P1, tv.CANAL_GATILHO)
    sessao.tomar(P1, tv.CANAL_LUZ)
    assert sessao.soltar(P1, tv.CANAL_LUZ) is False
    assert encerradas == []
    assert sessao.soltar(P1, tv.CANAL_GATILHO) is True
    assert encerradas == [P1]
    sessao.tomar(P2, tv.CANAL_LUZ)
    sessao.largar(P2, tv.CANAL_LUZ)
    assert encerradas == [P1], "o canal que o jogo tomou não encerra a sessão dele"


def test_a_luz_que_volta_com_o_gatilho_ainda_seguro_repinta_a_cor_do_perfil() -> None:
    backend = Backend()
    encerradas: list[str] = []
    sessao = tv.SessaoDoMotor(encerradas.append)
    sessao.tomar(P1, tv.CANAL_GATILHO)

    def pintar(uniq: str, cor: tuple[int, int, int]) -> bool:
        sessao.tomar(uniq, tv.CANAL_LUZ)
        return backend.pintar(uniq, cor)

    luz = tv.AtuadorDaLuz(
        pintar,
        backend.cor_de,
        lambda u: sessao.soltar(u, tv.CANAL_LUZ),
        lambda u: sessao.largar(u, tv.CANAL_LUZ),
    )
    _tiros(tv.TatoVivo([luz]), backend, [0.1], fim=0.6)
    assert [cor for _t, _u, cor in backend.pintadas] == [(0, 0, 255), (0, 0, 160)]
    assert encerradas == []
    assert sessao.segura(P1) == frozenset({tv.CANAL_GATILHO}), "a luz repintada prendeu a sessão"
    assert sessao.soltar(P1, tv.CANAL_GATILHO) is True
    assert encerradas == [P1]


class _Pad:
    def __init__(self) -> None:
        self.backend = "uhid"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = True


class _Leitor:
    def __init__(self) -> None:
        self.l2_raw = 0
        self.r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


class _Controller:
    def __init__(self) -> None:
        self.primary_uniq = P1
        self.leds: list[tuple[str, tuple[int, int, int]]] = []
        self.sessoes: list[str] = []
        self.gatilhos: list[tuple[str, str, bytes]] = []

    def resolved_led_for(self, uniq: str) -> tuple[int, int, int] | None:
        return CORES.get(uniq)

    def set_game_output_for(self, uniq: str, *, led: Any = None, player_leds: Any = None) -> bool:
        self.leds.append((uniq, led))
        return True

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.gatilhos.append((uniq, side, bytes(block)))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.sessoes.append(uniq)
        return True


def test_cada_controle_pulsa_a_sua_cor(monkeypatch: pytest.MonkeyPatch) -> None:
    receita = tv.Receita(reacao_ao_tiro="pulsa", gatilho_no_ritmo=True)
    monkeypatch.setattr(tv, "receita_ativa", lambda _d: receita)
    controller = _Controller()
    leitores = {uniq: _Leitor() for uniq in QUATRO[1:]}
    daemon = SimpleNamespace(
        controller=controller,
        _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
        _gamepad_device=_Pad(),
        _coop_manager=SimpleNamespace(
            _players={
                uniq: SimpleNamespace(vpad=_Pad(), reader=leitor)
                for uniq, leitor in leitores.items()
            }
        ),
        display_authority="game",
    )
    motor = tv.TatoVivo(tv.atuadores_de_producao(daemon))
    daemon._tato_vivo = motor
    passo = tv.Passo(daemon, motor)

    def gatilhos(valor: int) -> None:
        daemon._last_state = SimpleNamespace(l2_raw=0, r2_raw=valor)
        for leitor in leitores.values():
            leitor.r2_raw = valor

    passo(0.0)
    gatilhos(255)
    passo(0.02)
    assert dict(controller.leds) == {uniq: tv.pico_do_pulso(CORES[uniq]) for uniq in QUATRO}
    gatilhos(0)
    t = 0.02
    while t < 2.0:
        t += tv.INTERVALO_S
        passo(t)
    for uniq in QUATRO:
        assert [cor for u, cor in controller.leds if u == uniq] == [
            tv.pico_do_pulso(CORES[uniq]), CORES[uniq]
        ]
    assert sorted(controller.sessoes) == sorted(QUATRO)
