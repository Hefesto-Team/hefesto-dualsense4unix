"""Os momentos da imersão tocam no gatilho (OS-MOMENTOS-DA-IMERSAO-TOCAM-NO-GATILHO-01).

A imersão escolhida na aba Gatilhos chega ao perfil só como os números do acionamento;
o motor do tato a reconhece por eles e toca os `momentos` dela (ao apertar, segurando,
sempre) no gatilho de cada controle, onde o jogo cala. Tudo com relógio injetado, o
perfil de mentira e um backend que anota cada bloco e cada fim de sessão.

MORDIDAS: tirar a guarda do jogo do `AtuadorDosMomentos.relogio` (o momento escreve com o
jogo mandando) reprova `test_o_jogo_que_escreve_o_gatilho_cala_o_momento`; tirar o
`valem_em` de `momentos_no_modo` reprova `test_a_rajada_sobe_um_degrau_por_escrita_e_so_no_modo_\
que_tem_o_momento`;
devolver a sessão a cada batida reprova `test_o_automatico_toca_a_batida_entre_duas_sessoes`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as computador
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

P1 = "aa:bb:cc:00:00:31"
P2 = "aa:bb:cc:00:00:32"
TIQUE = 1.0 / 60.0
FOLGA = TIQUE + 1e-6

PINO = {"mode": "Weapon", "params": [3, 7, 230]}
RAJADA_MACHINE = {"mode": "Machine", "params": [0, 9, 4, 40]}
RAJADA_VIBRATION = {"mode": "Vibration", "params": [0, 5, 8]}
FREIO_DA_CORRIDA = {"mode": "Resistance", "params": [2, 7]}
CANO_MACHINE = {"mode": "Machine", "params": [0, 9, 6, 20]}
AUTOMATICO = {"modo": "automatico"}  # (noqa-acento) chave ASCII do schema


def _bloco(modo: str, **valores: int) -> bytes:
    """O bloco esperado, montado à parte: os padrões do modo, os números e o layout do relatório."""
    spec = get_spec(modo)
    padroes = {p.name: p.default for p in spec.params} if spec is not None else {}
    efeito = build_from_name(modo, {**padroes, **valores})
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


class Backend:
    """As APIs por controle do backend, anotando o instante de cada bloco e de cada volta."""

    def __init__(self) -> None:
        self.agora = 0.0
        self.blocos: list[tuple[float, str, str, bytes]] = []
        self.sessoes: list[tuple[float, str]] = []

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.blocos.append((self.agora, uniq, side, bytes(block)))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.sessoes.append((self.agora, uniq))
        return True

    def de(self, uniq: str, lado: str | None = None) -> list[tuple[float, bytes]]:
        return [(t, b) for t, u, s, b in self.blocos if u == uniq and lado in (None, s)]


class _Pad:
    def __init__(self) -> None:
        self.backend = "uinput"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = False


class _Leitor:
    def __init__(self) -> None:
        self.l2_raw = 0
        self.r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


@dataclass
class Mesa:
    daemon: Any
    backend: Backend
    motor: tv.TatoVivo
    passo: tv.Passo
    leitores: dict[str, _Leitor]
    t: float = 0.0
    gatilhos: dict[str, dict[str, int]] = field(default_factory=dict)

    def apertar(self, uniq: str, lado: str = "direito", valor: int = 255) -> None:
        dele = self.gatilhos.setdefault(uniq, {"esquerdo": 0, "direito": 0})
        dele[lado] = valor
        if uniq == P1:
            self.daemon._last_state = SimpleNamespace(
                l2_raw=dele["esquerdo"], r2_raw=dele["direito"])
        else:
            self.leitores[uniq].l2_raw = dele["esquerdo"]
            self.leitores[uniq].r2_raw = dele["direito"]

    def soltar(self, uniq: str, lado: str = "direito") -> None:
        self.apertar(uniq, lado, 0)

    def rodar(self, segundos: float) -> None:
        fim = self.t + segundos
        while self.t < fim - 1e-9:
            self.backend.agora = self.t
            self.passo(self.t)
            self.t += TIQUE


def _perfil(**campos: Any) -> Profile:
    return Profile(name="Momentos", match=MatchAny(), **campos)


def _mesa(
    monkeypatch: pytest.MonkeyPatch, perfil: Profile, *, nativo: bool = False
) -> Mesa:
    monkeypatch.setattr(loader, "perfil_em_disco", lambda _nome: perfil)
    monkeypatch.setattr(computador, "o_que_vale", lambda p: p)
    monkeypatch.setattr(tv, "_PELO_CARREGADOR", None)
    monkeypatch.setattr(tv, "_VISTA_LIDA", None)
    backend = Backend()
    leitores = {P2: _Leitor()}
    controller = SimpleNamespace(
        primary_uniq=P1,
        set_game_trigger_for=backend.set_game_trigger_for,
        end_game_session_for=backend.end_game_session_for,
    )
    daemon = SimpleNamespace(
        controller=controller,
        _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
        _gamepad_device=None if nativo else _Pad(),
        _coop_manager=SimpleNamespace(
            _players={P2: SimpleNamespace(vpad=_Pad(), reader=leitores[P2])}),
        display_authority="game",
        store=SimpleNamespace(active_profile="Momentos"),
    )
    motor = tv.TatoVivo(tv.atuadores_de_producao(daemon))
    daemon._tato_vivo = motor
    mesa = Mesa(daemon, backend, motor, tv.Passo(daemon, motor), leitores)
    mesa.rodar(0.1)  # o motor lê a receita e a mesa assenta antes do aperto
    return mesa


# ------------------------------------------------------------------- a receita


def test_a_imersao_com_momentos_liga_o_motor_e_o_perfil_sem_ela_nao() -> None:
    com = tv.receita_do_perfil(_perfil(triggers={"right": PINO}))
    assert com.momentos_da_imersao and com.ligada
    sem = tv.receita_do_perfil(_perfil())
    assert sem == tv.DESLIGADA and not sem.ligada
    # A imersão sem momentos (a «Trava seca») não liga nada.
    trava = tv.receita_do_perfil(_perfil(triggers={"right": {
        "mode": "Weapon", "params": [2, 3, 255]}}))
    assert trava == tv.DESLIGADA
    # O desvio da bancada desliga os momentos, campo a campo.
    desviada = tv.receita_do_perfil(_perfil(
        triggers={"right": PINO}, receita_do_tato={"momentos_da_imersao": False}))
    assert desviada == tv.DESLIGADA


def test_a_tela_e_o_motor_reconhecem_a_imersao_pela_mesma_regra() -> None:
    for imersao, modo, estilo, ajustes in ei.todos_os_ajustes():
        spec = get_spec(modo)
        assert spec is not None
        params = [ajustes.get(p.name, p.default) for p in spec.params]
        assert ei.imersao_dos_numeros(modo, params) == (imersao, estilo), (imersao.chave, modo)
    assert ei.imersao_dos_numeros("Machine", [2, 9, 4, 40]) is None, "o padrão não é imersão"
    assert ei.imersao_dos_numeros("Machine", [0, 9, 4, 40])[0].chave == "rajada-que-sobe-sozinha"
    assert ei.imersao_dos_numeros("Nenhum", [1]) is None


# ------------------------------------------------------------------- os momentos


def test_o_pino_escreve_o_feedback_ao_apertar_e_volta_em_500_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(1.0)
    assert [b for _t, b in mesa.backend.de(P1)] == [_bloco("Resistance", start=5, force=8)]
    assert mesa.backend.de(P1)[0][0] == pytest.approx(apertou)
    assert mesa.backend.de(P1, "left") == [], "o lado esquerdo não tem imersão"
    [(voltou, quem)] = mesa.backend.sessoes
    assert quem == P1
    assert 0.5 <= voltou - apertou <= 0.5 + FOLGA, "a volta ao estático é aos 500 ms"


def test_a_rajada_sobe_um_degrau_por_escrita_e_so_no_modo_que_tem_o_momento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": RAJADA_MACHINE}))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(1.99)
    escritas = mesa.backend.de(P1, "right")
    # Um bloco por degrau (5, 6, 7), nenhum repetido: o ritmo da batida é do firmware.
    assert [b for _t, b in escritas] == [
        _bloco("Machine", start=0, end=9, strength=f, frequency=40) for f in (5, 6, 7)]
    for i, (t, _b) in enumerate(escritas):
        assert 0.5 * (i + 1) <= t - apertou <= 0.5 * (i + 1) + FOLGA, (i, t - apertou)
    mesa.soltar(P1)
    mesa.rodar(0.1)
    assert [u for _t, u in mesa.backend.sessoes] == [P1], "soltar devolve o estático"

    # Na Vibração a mesma imersão sobe a amplitude, pelos momentos que valem nela.
    outra = _mesa(monkeypatch, _perfil(triggers={"right": RAJADA_VIBRATION}))
    outra.apertar(P1)
    outra.rodar(1.99)
    assert [b for _t, b in outra.backend.de(P1, "right")] == [
        _bloco("Vibration", position=0, amplitude=a, frequency=8) for a in (6, 7, 8)]


def test_o_cano_baixa_a_frequencia_aos_3_s(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": CANO_MACHINE}))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(2.95)
    assert mesa.backend.blocos == [], "antes dos 3 s o cano não muda"
    mesa.rodar(0.5)
    [(t, bloco)] = mesa.backend.de(P1)
    assert bloco == _bloco("Machine", start=0, end=9, strength=6, frequency=8)
    assert 3.0 <= t - apertou <= 3.0 + FOLGA
    mesa.soltar(P1)
    mesa.rodar(0.1)
    assert [u for _t, u in mesa.backend.sessoes] == [P1]


def test_soltar_devolve_o_estatico_e_o_lado_que_volta_sozinho_volta_a_mao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    mesa.apertar(P1)
    mesa.rodar(0.2)
    soltou = mesa.t
    mesa.soltar(P1)
    mesa.rodar(0.5)
    [(voltou, _u)] = mesa.backend.sessoes
    assert soltou <= voltou <= soltou + FOLGA, "soltar antes do prazo devolve na hora"

    # Os dois lados com o pino: o primeiro que vence volta à mão, o segundo fecha a sessão.
    dois = _mesa(monkeypatch, _perfil(triggers={"left": PINO, "right": PINO}))
    dois.apertar(P1, "direito")
    dois.rodar(0.3)
    dois.apertar(P1, "esquerdo")
    dois.rodar(1.0)
    estatico = _bloco("Weapon", start=3, end=7, force=230)
    feedback = _bloco("Resistance", start=5, force=8)
    assert [b for _t, b in dois.backend.de(P1, "right")] == [feedback, estatico]
    assert [b for _t, b in dois.backend.de(P1, "left")] == [feedback]
    [(fim, _u)] = dois.backend.sessoes
    assert fim >= dois.backend.de(P1, "left")[0][0] + 0.5


def test_o_jogo_que_escreve_o_gatilho_cala_o_momento(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": RAJADA_MACHINE}))
    pad = mesa.daemon._gamepad_device
    pad.visto_ha_s = {"trigger": 0.0}
    mesa.apertar(P1)
    mesa.rodar(1.0)
    assert mesa.backend.blocos == [], "o jogo escreve o gatilho: o momento se cala"

    # O jogo toma o gatilho no meio da rajada: solta sem devolver (o valor é dele).
    meio = _mesa(monkeypatch, _perfil(triggers={"right": RAJADA_MACHINE}))
    meio.apertar(P1)
    meio.rodar(0.6)
    antes = len(meio.backend.blocos)
    assert antes == 1
    meio.daemon._gamepad_device.visto_ha_s = {"trigger": 0.0}
    meio.rodar(1.0)
    assert len(meio.backend.blocos) == antes
    assert meio.backend.sessoes == [], "o motor não devolve o que agora é do jogo"
    assert meio.motor.contadores["soltos_ao_jogo"] == 1


def test_o_modo_nativo_cala_o_momento(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}), nativo=True)
    mesa.apertar(P1)
    mesa.rodar(1.0)
    assert mesa.backend.de(P1) == [] and mesa.backend.sessoes == []


def test_p2_apertando_nao_escreve_em_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    mesa.apertar(P2)
    mesa.rodar(1.0)
    assert {u for _t, u, _s, _b in mesa.backend.blocos} == {P2}
    assert [u for _t, u in mesa.backend.sessoes] == [P2]


def test_a_imersao_de_um_controle_so_toca_nele(monkeypatch: pytest.MonkeyPatch) -> None:
    perfil = _perfil(controllers={norm_mac(P2): {"triggers": {"right": PINO}}})
    mesa = _mesa(monkeypatch, perfil)
    mesa.apertar(P1)
    mesa.apertar(P2)
    mesa.rodar(1.0)
    assert mesa.backend.de(P1) == []
    assert [b for _t, b in mesa.backend.de(P2)] == [_bloco("Resistance", start=5, force=8)]


def _batida() -> tv.MapaDosMomentos:
    """O plano de uma batida «sempre» nos dois gatilhos, no Modo automático (a volta é o Off)."""
    batida = tv.PlanoDoGatilho(
        ei.POR_CHAVE["batida-do-coracao"], "Weapon", "", {}, (
            ei.Momento("sempre", 0, "Weapon", {"start": 2, "end": 6, "force": 255},
                       dura_ms=120, a_cada_ms=830),), automatico=True)
    return tv.MapaDosMomentos({"esquerdo": batida, "direito": batida})


def test_a_batida_que_sai_entre_duas_batidas_devolve_a_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: _batida())
    mesa.rodar(1.5)
    assert mesa.backend.blocos and mesa.backend.sessoes == []
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: tv.SEM_MOMENTOS)
    mesa.rodar(1.5)  # a releitura da receita tira o plano entre duas batidas
    assert sorted(u for _t, u in mesa.backend.sessoes) == [P1, P2]
    escritos = len(mesa.backend.blocos)
    mesa.rodar(2.0)
    assert len(mesa.backend.blocos) == escritos, "sem a imersão, nenhuma batida mais"


def test_o_jogo_que_toma_o_gatilho_entre_duas_batidas_fica_com_a_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: _batida())
    mesa.rodar(1.0)  # uma batida e o Off à mão: a sessão é do momento
    mesa.daemon._gamepad_device.visto_ha_s = {"trigger": 0.0}
    mesa.rodar(0.1)
    assert mesa.motor.contadores["soltos_ao_jogo"] == 1, "o momento larga a sessão ao jogo"
    mesa.motor.parar(mesa.t)
    assert P1 not in [u for _t, u in mesa.backend.sessoes], "o motor não devolve o que é do jogo"


def test_a_corda_comeca_leve_no_aperto_e_pesa_a_cada_meio_segundo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corda = {"mode": "Bow", "params": [0, 8, 7, 6]}
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": corda}))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(3.5)
    escritas = mesa.backend.de(P1, "right")
    forcas = list(range(1, 8))
    assert [b for _t, b in escritas] == [
        _bloco("Bow", start=0, end=8, force=f, snap=6) for f in forcas]
    for i, (t, _b) in enumerate(escritas):
        assert 0.5 * i <= t - apertou <= 0.5 * i + FOLGA, (i, t - apertou)


def test_o_teto_segura_uma_rampa_rapida(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    corda = next(i for i in ei.IMERSOES if i.familia == "arco")
    # Um degrau de bloco novo a cada 20 ms: 30 blocos distintos em 600 ms (o bloco repetido
    # não se escreve de novo, então a rampa rápida precisa de blocos que mudem).
    degraus = tuple(
        ei.Momento("segurando", k * 20, "Bow", {"force": 1 + k % 8, "snap": k // 8})
        for k in range(1, 31))
    rapida = tv.PlanoDoGatilho(
        corda, "Bow", "", ei.ajustes_da_imersao(corda, "Bow") or {}, degraus)
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: tv.MapaDosMomentos({"direito": rapida}))
    mesa.rodar(1.0)  # a releitura da receita traz o plano rápido
    mesa.apertar(P1)
    inicio = mesa.t
    mesa.rodar(1.0)
    na_janela = [t for t, _b in mesa.backend.de(P1) if inicio <= t < inicio + 1.0]
    assert 0 < len(na_janela) <= tv.TETO_POR_CONTROLE
    assert mesa.motor.contadores["recusas_do_teto"] > 0


def test_o_automatico_toca_a_batida_entre_duas_sessoes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Entre as batidas o Off vai à mão e a sessão fica: devolvê-la a cada batida seria uma volta
    # inteira do backend (e duas linhas no diário) quase uma vez por segundo.
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": PINO}))
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: _batida())
    mesa.rodar(2.0)
    batida = _bloco("Weapon", start=2, end=6, force=255)
    off = _bloco("Off")
    for disco in ("left", "right"):
        assert [b for _t, b in mesa.backend.de(P1, disco)][:4] == [batida, off] * 2, disco
    assert mesa.backend.sessoes == [], "a sessão fica entre as batidas"
    mesa.motor.parar(mesa.t)
    assert sorted(u for _t, u in mesa.backend.sessoes) == [P1, P2], "parado, devolve as duas"



def test_o_automatico_da_corrida_vibra_o_freio_depois_de_800_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrida = _mesa(monkeypatch, _perfil(estilo="corrida", triggers=AUTOMATICO))
    apertou = corrida.t
    corrida.apertar(P1)
    corrida.rodar(1.0)
    [(t, bloco)] = corrida.backend.de(P1, "right")
    assert bloco == _bloco("Vibration", position=2, amplitude=3, frequency=15)
    assert 0.8 <= t - apertou <= 0.8 + FOLGA

    # O FPS guarda a chave velha no estilo, e o automático acha a imersão dele pelo
    # acionamento de hoje (a Rajada na Metralhadora): os momentos ficam ligados.
    assert tv.receita_do_perfil(
        _perfil(estilo="fps", triggers=AUTOMATICO)).momentos_da_imersao


def test_a_variante_da_corrida_vale_no_momento(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": FREIO_DA_CORRIDA}))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(1.0)
    [(t, bloco)] = mesa.backend.de(P1)
    assert bloco == _bloco("Vibration", position=2, amplitude=3, frequency=15)
    assert 0.8 <= t - apertou <= 0.8 + FOLGA


def test_o_ritmo_do_tiro_cede_o_lado_que_tem_momento(monkeypatch: pytest.MonkeyPatch) -> None:
    perfil = _perfil(estilo="fps", triggers={"right": RAJADA_MACHINE})
    mesa = _mesa(monkeypatch, perfil)
    receita = mesa.passo.receita_vigente
    assert receita.gatilho_no_ritmo and receita.momentos_da_imersao
    for _ in range(2):
        mesa.apertar(P1)
        mesa.rodar(0.6)
        mesa.soltar(P1)
        mesa.rodar(0.1)
    arma = tv.bloco_do_gatilho(tv.GATILHO_ARMA, receita)
    rajada = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, receita)
    escritos = {b for _t, b in mesa.backend.de(P1, "right")}
    assert escritos == {_bloco("Machine", start=0, end=9, strength=5, frequency=40)}
    assert arma not in escritos and rajada not in escritos


def test_o_motor_parado_devolve_o_que_o_momento_segura(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _perfil(triggers={"right": RAJADA_MACHINE}))
    mesa.apertar(P1)
    mesa.rodar(0.6)
    assert mesa.backend.blocos and not mesa.backend.sessoes
    mesa.motor.parar(mesa.t)
    assert [u for _t, u in mesa.backend.sessoes] == [P1]
