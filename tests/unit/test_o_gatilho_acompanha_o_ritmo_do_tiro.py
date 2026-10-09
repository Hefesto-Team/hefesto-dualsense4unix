"""O gatilho acompanha o ritmo do tiro (O-GATILHO-ACOMPANHA-O-RITMO-DO-TIRO-01).

O jogo escreve o gatilho uma vez por arma e o firmware rearma sozinho; o que
muda de tiro para tiro é o RITMO. Onde o jogo cala o gatilho, o motor do tato
vivo mede o intervalo entre tiros de cada lado de cada controle e troca o
bloco: tiros espaçados pedem a arma semi-automática da tela, a rajada pede a
vibração oficial com a frequência da receita. Nada por tiro: só a troca.
Tudo com relógio injetado e um backend de mentira que anota os blocos.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
from hefesto_dualsense4unix.core.trigger_effects import TriggerMode, build_from_name
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

P1 = "aa:bb:cc:00:00:21"
P2 = "aa:bb:cc:00:00:22"
P3 = "aa:bb:cc:00:00:23"
P4 = "aa:bb:cc:00:00:24"
QUATRO = (P1, P2, P3, P4)
_RITMO = tv.Receita(gatilho_no_ritmo=True, frequencia_da_rajada_hz=25)


class Backend:
    """O par de APIs por controle do backend, anotando o que receberia."""

    def __init__(self) -> None:
        self.blocos: list[tuple[str, str, bytes]] = []
        self.sessoes: list[str] = []

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.blocos.append((uniq, side, bytes(block)))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.sessoes.append(uniq)
        return True


def _xbox(_uniq: str) -> tv.EstadoDoCanal:
    return tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


def _motor(backend: Backend, apertado: Any = None) -> tv.TatoVivo:
    atuador = tv.AtuadorDoGatilho(
        backend.set_game_trigger_for, backend.end_game_session_for, apertado
    )
    return tv.TatoVivo([atuador])


def _atirar(
    motor: tv.TatoVivo,
    instantes: list[float],
    *,
    uniq: str = P1,
    lado: str = tv.LADO_DIREITO,
    estado_de: Any = _xbox,
    receita: tv.Receita = _RITMO,
) -> None:
    for t in instantes:
        motor.anotar(tv.Evento(t, uniq, tv.TIPO_DEDO, lado))
        motor.tique(t + 0.001, estado_de, receita)


def _cadencia(inicio: float, passo: float, n: int) -> list[float]:
    return [round(inicio + i * passo, 6) for i in range(n)]


def _modos(backend: Backend) -> list[str]:
    arma = tv.bloco_do_gatilho(tv.GATILHO_ARMA, _RITMO)
    rajada = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, _RITMO)
    nomes = {arma: tv.GATILHO_ARMA, rajada: tv.GATILHO_RAJADA}
    return [nomes.get(bloco, "?") for _u, _l, bloco in backend.blocos]


# --- Os blocos são os da tela, nenhum byte novo ----------------------------


def _da_tela(nome: str, **troca: int) -> bytes:
    spec = get_spec(nome)
    assert spec is not None
    valores = {p.name: p.default for p in spec.params}
    valores.update(troca)
    efeito = build_from_name(nome, valores)
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


def test_o_bloco_da_arma_e_a_semi_automatica_da_tela() -> None:
    bloco = tv.bloco_do_gatilho(tv.GATILHO_ARMA, _RITMO)
    assert len(bloco) == 11
    assert bloco == _da_tela("SemiAutoGun")


def test_o_bloco_da_rajada_e_a_vibracao_oficial_com_a_frequencia_da_receita() -> None:
    bloco = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, _RITMO)
    assert len(bloco) == 11
    assert bloco[0] == TriggerMode.VIBRATION
    # A frequência do modo oficial mora no décimo byte do bloco (o `forces[6]`).
    assert bloco[9] == 25
    assert bloco == _da_tela("MultiPositionVibration", frequency=25)


# --- O ritmo ---------------------------------------------------------------


def test_tiros_a_400_ms_pedem_a_arma_uma_vez() -> None:
    backend = Backend()
    _atirar(_motor(backend), _cadencia(0.0, 0.4, 10))
    assert _modos(backend) == [tv.GATILHO_ARMA]
    assert {(u, lado) for u, lado, _b in backend.blocos} == {(P1, "right")}


def test_tiros_a_70_ms_trocam_para_a_vibracao() -> None:
    backend = Backend()
    _atirar(_motor(backend), _cadencia(0.0, 0.07, 12))
    assert _modos(backend) == [tv.GATILHO_ARMA, tv.GATILHO_RAJADA]


def test_a_rajada_que_para_volta_a_arma_no_tiro_espacado() -> None:
    backend = Backend()
    _atirar(_motor(backend), [*_cadencia(0.0, 0.07, 6), 0.75, 1.15])
    assert _modos(backend) == [tv.GATILHO_ARMA, tv.GATILHO_RAJADA, tv.GATILHO_ARMA]


@pytest.mark.parametrize("comeco", ["arma", "rajada"])
def test_tiros_a_150_ms_nao_oscilam(comeco: str) -> None:
    backend = Backend()
    motor = _motor(backend)
    inicio = [0.0] if comeco == "arma" else _cadencia(0.0, 0.07, 4)
    _atirar(motor, inicio)
    antes = len(backend.blocos)
    _atirar(motor, _cadencia(inicio[-1] + 0.15, 0.15, 20))
    assert len(backend.blocos) == antes, "a troca oscilou no ritmo do meio"


def test_o_dedo_segurado_com_o_rumble_do_jogo_e_rajada() -> None:
    """A arma automática: um aperto só, e o jogo pede o motor a cada bala."""
    backend = Backend()
    segurado = {(P1, tv.LADO_DIREITO)}
    motor = _motor(backend, lambda uniq, lado: (uniq, lado) in segurado)
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO, tv.LADO_DIREITO))
    motor.tique(0.001, _xbox, _RITMO)
    for t in _cadencia(0.01, 0.07, 10):  # o primeiro rumble é do mesmo tiro do aperto
        motor.anotar(tv.Evento(t, P1, tv.TIPO_RUMBLE, tv.LADO_CENTRO))
        motor.tique(t + 0.001, _xbox, _RITMO)
    assert _modos(backend) == [tv.GATILHO_ARMA, tv.GATILHO_RAJADA]


def test_o_rumble_sem_dedo_no_gatilho_nao_mexe_no_gatilho() -> None:
    backend = Backend()
    motor = _motor(backend, lambda _u, _l: False)
    for t in _cadencia(0.0, 0.07, 10):
        motor.anotar(tv.Evento(t, P1, tv.TIPO_RUMBLE, tv.LADO_CENTRO))
        motor.tique(t + 0.001, _xbox, _RITMO)
    assert backend.blocos == []


def test_sem_o_gatilho_no_ritmo_na_receita_nada_se_escreve() -> None:
    backend = Backend()
    _atirar(_motor(backend), _cadencia(0.0, 0.07, 12), receita=tv.Receita(vibracao_por_tiro=True))
    assert backend.blocos == []


# --- O jogo manda ----------------------------------------------------------


def test_o_jogo_que_escreve_o_gatilho_passa_cru_e_o_motor_cala() -> None:
    backend = Backend()

    def mandando(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"trigger": 0.4},
            sessao_aberta=True, ha_jogo=True,
        )

    _atirar(_motor(backend), _cadencia(0.0, 0.07, 12), estado_de=mandando)
    assert backend.blocos == []


def test_o_jogo_que_pintou_a_luz_segura_o_gatilho_pela_sessao() -> None:
    """A volta do backend é a sessão inteira: devolver o gatilho apagaria a luz do jogo."""
    backend = Backend()

    def pintou(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"lightbar": 9.0},
            sessao_aberta=True, ha_jogo=True,
        )

    _atirar(_motor(backend), _cadencia(0.0, 0.4, 4), estado_de=pintou)
    assert backend.blocos == []


def test_no_modo_nativo_o_gatilho_e_do_aparelho() -> None:
    backend = Backend()

    def nativo(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(modo=tv.MODO_NATIVO, ha_jogo=True)

    _atirar(_motor(backend), _cadencia(0.0, 0.07, 12), estado_de=nativo)
    assert backend.blocos == []


# --- Um ciclo, uma escrita por controle -------------------------------------


def test_os_dois_gatilhos_no_mesmo_tique_saem_numa_escrita_so() -> None:
    backend = Backend()
    motor = _motor(backend)
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO, tv.LADO_ESQUERDO))
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO, tv.LADO_DIREITO))
    motor.tique(0.001, _xbox, _RITMO)
    assert sorted(lado for _u, lado, _b in backend.blocos) == ["left", "right"]
    assert motor.contadores["escritas"] == 1


def test_o_mesmo_controle_nao_escreve_duas_vezes_no_mesmo_ciclo() -> None:
    backend = Backend()
    motor = _motor(backend)
    _atirar(motor, [0.0], lado=tv.LADO_DIREITO)
    _atirar(motor, [0.01], lado=tv.LADO_ESQUERDO)
    assert [lado for _u, lado, _b in backend.blocos] == ["right"]
    # O lado que esperou o ciclo sai na escrita seguinte do controle.
    _atirar(motor, [0.5], lado=tv.LADO_DIREITO)
    assert [lado for _u, lado, _b in backend.blocos] == ["right", "left"]


def test_dois_controles_no_mesmo_ciclo_escrevem_cada_um_o_seu() -> None:
    backend = Backend()
    motor = _motor(backend)
    for uniq in QUATRO:
        motor.anotar(tv.Evento(0.0, uniq, tv.TIPO_DEDO, tv.LADO_DIREITO))
    motor.tique(0.001, _xbox, _RITMO)
    assert sorted(u for u, _l, _b in backend.blocos) == sorted(QUATRO)


# --- A volta ao perfil -----------------------------------------------------


def test_a_volta_vem_depois_do_ultimo_tiro_e_nao_no_meio_da_rajada() -> None:
    backend = Backend()
    motor = _motor(backend)
    tiros = _cadencia(0.0, 0.07, 43)  # três segundos de rajada
    _atirar(motor, tiros)
    assert backend.sessoes == [], "devolveu no meio da rajada"
    motor.tique(tiros[-1] + tv.VOLTA_DO_GATILHO_S - 0.05, _xbox, _RITMO)
    assert backend.sessoes == []
    motor.tique(tiros[-1] + tv.VOLTA_DO_GATILHO_S + 0.01, _xbox, _RITMO)
    assert backend.sessoes == [P1]
    motor.tique(tiros[-1] + 5.0, _xbox, _RITMO)
    assert backend.sessoes == [P1]


def test_depois_da_volta_o_primeiro_tiro_escreve_de_novo() -> None:
    backend = Backend()
    motor = _motor(backend)
    _atirar(motor, [0.0])
    motor.tique(3.0, _xbox, _RITMO)
    _atirar(motor, [4.0])
    assert _modos(backend) == [tv.GATILHO_ARMA, tv.GATILHO_ARMA]


# --- P1 a P4, pelo caminho do produto --------------------------------------


class _Pad:
    def __init__(self) -> None:
        self.backend = "uinput"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = False


class _Leitor:
    def __init__(self) -> None:
        self.r2_raw = 0
        self.l2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


def _mesa() -> tuple[Any, Backend, dict[str, Any]]:
    backend = Backend()
    leitores: dict[str, Any] = {uniq: _Leitor() for uniq in QUATRO[1:]}
    controller = SimpleNamespace(
        primary_uniq=P1,
        set_game_trigger_for=backend.set_game_trigger_for,
        end_game_session_for=backend.end_game_session_for,
    )
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
    leitores[P1] = daemon
    return daemon, backend, leitores


def _apertar(daemon: Any, leitores: dict[str, Any], uniq: str, valor: int) -> None:
    if uniq == P1:
        daemon._last_state = SimpleNamespace(l2_raw=0, r2_raw=valor)
    else:
        leitores[uniq].r2_raw = valor


@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_cada_controle_tem_o_seu_ritmo(lugar: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "receita_ativa", lambda _d: _RITMO)
    daemon, backend, leitores = _mesa()
    motor = tv.TatoVivo(tv.atuadores_de_producao(daemon))
    daemon._tato_vivo = motor
    passo = tv.Passo(daemon, motor)
    alvo = QUATRO[lugar - 1]
    t = 0.0
    # Rajada de toques curtos no gatilho do alvo; os outros atiram devagar.
    for i in range(12):
        _apertar(daemon, leitores, alvo, 255)
        if i % 6 == 0:
            for outro in QUATRO:
                if outro != alvo:
                    _apertar(daemon, leitores, outro, 255)
        passo(t)
        t += 0.035
        for uniq in QUATRO:
            _apertar(daemon, leitores, uniq, 0)
        passo(t)
        t += 0.035
    do_alvo = [b for u, _l, b in backend.blocos if u == alvo]
    rajada = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, _RITMO)
    arma = tv.bloco_do_gatilho(tv.GATILHO_ARMA, _RITMO)
    assert do_alvo == [arma, rajada]
    for outro in QUATRO:
        if outro != alvo:
            assert [b for u, _l, b in backend.blocos if u == outro] == [arma]
    assert {lado for _u, lado, _b in backend.blocos} == {"right"}
