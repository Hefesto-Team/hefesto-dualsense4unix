"""O tato vivo só fala onde o jogo cala (O-TATO-VIVO-SO-FALA-ONDE-O-JOGO-CALA-01).

O núcleo do motor, sem efeito de canal: a política pura ``decidir`` sobre os
carimbos do pad virtual e um relógio injetado, o teto de pulsos, a volta ao
perfil e a matriz P1 a P4. Nada aqui chega ao aparelho: os atuadores são
dublês que anotam o que receberiam.
"""
from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
QUATRO = (P1, P2, P3, P4)


class AtuadorDeMentira:
    def __init__(self, canal: str, duracao_s: float = 0.1) -> None:
        self.canal = canal
        self.duracao_s = duracao_s
        self.escritas: list[tuple[str, float]] = []
        self.devolucoes: list[tuple[str, float]] = []

    def responde_a(self, evento: tv.Evento, receita: tv.Receita) -> bool:
        return True

    def escrever(self, evento: tv.Evento, receita: tv.Receita, agora: float) -> float:
        self.escritas.append((evento.uniq, agora))
        return agora + self.duracao_s

    def devolver(self, uniq: str, agora: float) -> None:
        self.devolucoes.append((uniq, agora))


def _estado(modo: str, visto: dict[str, float] | None = None, *,
            sessao: bool = False, jogo: bool = True) -> tv.EstadoDoCanal:
    return tv.EstadoDoCanal(modo=modo, visto_ha_s=visto or {},
                            sessao_aberta=sessao, ha_jogo=jogo)


# --- A tabela-verdade ------------------------------------------------------

_CARIMBO = {
    tv.CANAL_GATILHO: "trigger",
    tv.CANAL_LUZ: "lightbar",
    tv.CANAL_HAPTICA: "audio_do_jogo",
    tv.CANAL_SOM: "audio_do_jogo",
}

# (situação do jogo, sessão aberta) → o motor escreve? Por canal de estado e de fluxo.
_TABELA = [
    # situação     sessão  estado(gatilho/luz)  fluxo(háptica/som)
    ("nunca",      True,   True,                True),
    ("nunca",      False,  True,                True),
    ("agora",      True,   False,               False),
    ("agora",      False,  False,               False),
    ("ha_3s",      True,   False,               True),
    ("ha_3s",      False,  True,                True),
]


@pytest.mark.parametrize("canal", tv.CANAIS)
@pytest.mark.parametrize(("quando", "aberta", "no_estado", "no_fluxo"), _TABELA)
def test_a_tabela_verdade_no_modo_dualsense(
    canal: str, quando: str, aberta: bool, no_estado: bool, no_fluxo: bool
) -> None:
    visto = {"nunca": {}, "agora": {_CARIMBO[canal]: 0.4},
             "ha_3s": {_CARIMBO[canal]: 3.2}}[quando]
    esperado = no_estado if canal in tv.CANAIS_DE_ESTADO else no_fluxo
    assert tv.decidir(canal, _estado(tv.MODO_DUALSENSE, visto, sessao=aberta)) is esperado


@pytest.mark.parametrize("canal", tv.CANAIS)
@pytest.mark.parametrize("idade", [None, 0.4, 3.2])
def test_no_modo_nativo_o_motor_fica_calado(canal: str, idade: float | None) -> None:
    visto = {} if idade is None else {_CARIMBO[canal]: idade}
    assert tv.decidir(canal, _estado(tv.MODO_NATIVO, visto, sessao=True)) is False


@pytest.mark.parametrize("canal", tv.CANAIS)
def test_no_modo_xbox_o_jogo_nao_escreve_estes_canais_e_o_motor_vale(canal: str) -> None:
    # O pad Xbox não tem carimbo de gatilho, luz nem áudio: o jogo cala nos quatro.
    assert tv.decidir(canal, _estado(tv.MODO_XBOX, {})) is True


@pytest.mark.parametrize("canal", tv.CANAIS)
def test_sem_jogo_o_motor_fica_calado(canal: str) -> None:
    assert tv.decidir(canal, _estado(tv.MODO_DUALSENSE, {}, jogo=False)) is False


def test_o_rumble_que_o_jogo_pede_e_sinal_e_nao_veto() -> None:
    estado = _estado(tv.MODO_DUALSENSE, {"rumble": 0.1})
    assert tv.decidir(tv.CANAL_HAPTICA, estado) is True


# O pad guarda o carimbo depois do UHID_CLOSE: só o da sessão de agora cala o estado.
@pytest.mark.parametrize("canal", sorted(tv.CANAIS_DE_ESTADO))
@pytest.mark.parametrize(
    ("carimbo_ha_s", "sessao_ha_s", "escreve"),
    [
        (10.0, 2.0, True),    # o jogo pintou na sessão que fechou
        (5.0, 8.0, False),    # pintou nesta sessão, há mais de 3 s: o valor dele vale
        (10.0, None, False),  # não se viu a sessão abrir: na dúvida, o jogo manda
    ],
)
@pytest.mark.parametrize("de_quem", ["este", "outro"])
def test_o_carimbo_da_sessao_que_fechou_nao_cala_o_estado(
    canal: str, carimbo_ha_s: float, sessao_ha_s: float | None, escreve: bool, de_quem: str
) -> None:
    alvo = canal if de_quem == "este" else next(iter(tv.CANAIS_DE_ESTADO - {canal}))
    estado = tv.EstadoDoCanal(
        modo=tv.MODO_DUALSENSE,
        visto_ha_s={_CARIMBO[alvo]: carimbo_ha_s},
        sessao_aberta=True,
        ha_jogo=True,
        sessao_ha_s=sessao_ha_s,
    )
    assert tv.decidir(canal, estado) is escreve


def test_o_modo_vem_do_pad_virtual() -> None:
    assert tv.modo_do_pad(None) == tv.MODO_NATIVO
    assert tv.modo_do_pad(SimpleNamespace(backend="uhid")) == tv.MODO_DUALSENSE
    assert tv.modo_do_pad(SimpleNamespace(backend="uinput")) == tv.MODO_XBOX


# --- O motor: fila, teto, volta, P1 a P4 -----------------------------------

_LIGADA = tv.Receita(reacao_ao_tiro="pulsa")


def _livre(uniq: str) -> tv.EstadoDoCanal:
    return _estado(tv.MODO_XBOX)


def test_o_caso_o_jogo_manda_o_gatilho_nao_escreve() -> None:
    gatilho = AtuadorDeMentira(tv.CANAL_GATILHO)
    motor = tv.TatoVivo([gatilho])
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO, tv.LADO_DIREITO))
    manda = _estado(tv.MODO_DUALSENSE, {"trigger": 0.2}, sessao=True)
    motor.tique(0.0, lambda u: manda, _LIGADA)
    assert gatilho.escritas == []
    assert motor.contadores["recusas_do_jogo"] == 1


def test_a_rajada_de_50_eventos_para_no_teto_de_12_por_segundo() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ, duracao_s=0.01)
    motor = tv.TatoVivo([luz])
    for i in range(50):
        agora = i * 0.01
        motor.anotar(tv.Evento(agora, P1, tv.TIPO_DEDO))
        motor.tique(agora, _livre, _LIGADA)
    assert len(luz.escritas) == tv.TETO_POR_CONTROLE
    assert motor.contadores["recusas_do_teto"] == 50 - tv.TETO_POR_CONTROLE


def test_o_teto_total_e_40_por_segundo_com_quatro_controles() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ, duracao_s=0.01)
    motor = tv.TatoVivo([luz])
    for i in range(50):
        agora = i * 0.01
        for uniq in QUATRO:
            motor.anotar(tv.Evento(agora, uniq, tv.TIPO_DEDO))
        motor.tique(agora, _livre, _LIGADA)
    assert len(luz.escritas) == tv.TETO_TOTAL


def test_o_teto_libera_depois_de_um_segundo() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ, duracao_s=0.01)
    motor = tv.TatoVivo([luz])
    for _ in range(20):
        motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO))
    motor.tique(0.0, _livre, _LIGADA)
    motor.anotar(tv.Evento(1.0, P1, tv.TIPO_DEDO))
    motor.tique(1.0, _livre, _LIGADA)
    assert len(luz.escritas) == tv.TETO_POR_CONTROLE + 1


def test_cada_evento_escreve_so_no_controle_dele() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ)
    motor = tv.TatoVivo([luz])
    for uniq in QUATRO:
        motor.anotar(tv.Evento(0.0, uniq, tv.TIPO_DEDO))
    motor.tique(0.0, _livre, _LIGADA)
    assert [u for u, _ in luz.escritas] == list(QUATRO)


def test_a_volta_ao_perfil_vem_no_prazo_e_so_uma_vez() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ, duracao_s=0.15)
    motor = tv.TatoVivo([luz])
    motor.anotar(tv.Evento(0.0, P2, tv.TIPO_DEDO))
    motor.tique(0.0, _livre, _LIGADA)
    motor.tique(0.1, _livre, _LIGADA)
    assert luz.devolucoes == []
    motor.tique(0.16, _livre, _LIGADA)
    motor.tique(0.3, _livre, _LIGADA)
    assert luz.devolucoes == [(P2, 0.16)]
    assert motor.pendentes == {}


def test_parar_devolve_o_que_ficou_preso() -> None:
    luz = AtuadorDeMentira(tv.CANAL_LUZ, duracao_s=10.0)
    motor = tv.TatoVivo([luz])
    for uniq in QUATRO:
        motor.anotar(tv.Evento(0.0, uniq, tv.TIPO_DEDO))
    motor.tique(0.0, _livre, _LIGADA)
    motor.parar(0.5)
    assert sorted(u for u, _ in luz.devolucoes) == sorted(QUATRO)


def test_quando_o_jogo_passa_a_mandar_o_motor_solta_sem_devolver() -> None:
    gatilho = AtuadorDeMentira(tv.CANAL_GATILHO, duracao_s=0.5)
    motor = tv.TatoVivo([gatilho])
    motor.anotar(tv.Evento(0.0, P1, tv.TIPO_DEDO))
    motor.tique(0.0, lambda u: _estado(tv.MODO_DUALSENSE, {}, sessao=True), _LIGADA)
    assert len(gatilho.escritas) == 1
    agora_manda = _estado(tv.MODO_DUALSENSE, {"trigger": 0.0}, sessao=True)
    motor.tique(0.6, lambda u: agora_manda, _LIGADA)
    assert gatilho.devolucoes == []
    assert motor.pendentes == {}
    assert motor.contadores["soltos_ao_jogo"] == 1


class HidrawDeMentira:
    """Conta as MUDANÇAS do relatório de saída de cada controle."""

    def __init__(self) -> None:
        self.relatorio: dict[str, bytes] = {}
        self.mudancas = 0

    def escrever(self, uniq: str, dados: bytes) -> None:
        if self.relatorio.get(uniq) != dados:
            self.mudancas += 1
        self.relatorio[uniq] = dados


class AtuadorNoHidraw:
    canal = tv.CANAL_LUZ

    def __init__(self, hidraw: HidrawDeMentira) -> None:
        self.hidraw = hidraw

    def responde_a(self, evento: tv.Evento, receita: tv.Receita) -> bool:
        return True

    def escrever(self, evento: tv.Evento, receita: tv.Receita, agora: float) -> float:
        self.hidraw.escrever(evento.uniq, b"\x31\xff")
        return agora + 0.15

    def devolver(self, uniq: str, agora: float) -> None:
        self.hidraw.escrever(uniq, b"\x31\x40")


def test_n_eventos_geram_no_maximo_2n_mudancas_de_relatorio() -> None:
    sorteio = random.Random(8)
    hidraw = HidrawDeMentira()
    motor = tv.TatoVivo([AtuadorNoHidraw(hidraw)])
    instantes = sorted(sorteio.uniform(0.0, 5.0) for _ in range(60))
    agora = 0.0
    for instante in instantes:
        while agora < instante:
            motor.tique(agora, _livre, _LIGADA)
            agora += 1.0 / 60.0
        motor.anotar(tv.Evento(instante, sorteio.choice(QUATRO), tv.TIPO_DEDO))
    for _ in range(60):
        motor.tique(agora, _livre, _LIGADA)
        agora += 1.0 / 60.0
    assert 0 < hidraw.mudancas <= 2 * len(instantes)
    assert all(v == b"\x31\x40" for v in hidraw.relatorio.values())


# --- A receita e o laço ----------------------------------------------------


def test_a_receita_nasce_desligada() -> None:
    assert tv.DESLIGADA.ligada is False
    assert tv.receita_do_perfil(SimpleNamespace(name="x")) == tv.DESLIGADA
    assert tv.receita_do_perfil(None) == tv.DESLIGADA


def test_a_receita_vem_do_campo_do_perfil_com_os_limites() -> None:
    perfil = {tv.CAMPO_DA_RECEITA: {"vibracao_por_tiro": True,
                                    "duracao_do_toque_ms": 500,
                                    "reacao_ao_tiro": "pisca-pisca"}}
    receita = tv.receita_do_perfil(perfil)
    assert receita.ligada
    assert receita.duracao_do_toque_ms == 60
    assert receita.reacao_ao_tiro == "parada"


def test_a_receita_vem_do_estilo_que_o_perfil_guarda() -> None:
    # O estilo guardado no perfil é traduzido (O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01):
    # a luz que respira na Luta pulsa a cada golpe; o Terror, desde 19/10/2026, tem o coração na
    # base da luz e não reage ao tiro.
    receita = tv.receita_do_perfil(SimpleNamespace(estilo="luta"))
    assert receita.reacao_ao_tiro == "pulsa"
    terror = tv.receita_do_perfil(SimpleNamespace(estilo="terror"))
    assert terror.reacao_ao_tiro == "parada"
    assert terror.duracao_do_toque_ms > receita.duracao_do_toque_ms


class Pad:
    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = False


class Leitor:
    def __init__(self) -> None:
        self.l2_raw = 0
        self.r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


def _mesa(backend: str | None = "uinput") -> tuple[Any, dict[str, Leitor]]:
    leitores = {uniq: Leitor() for uniq in QUATRO[1:]}
    jogadores = {
        uniq: SimpleNamespace(vpad=Pad(backend) if backend else None, reader=leitor)
        for uniq, leitor in leitores.items()
    }
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=P1),
        _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
        _gamepad_device=Pad(backend) if backend else None,
        _coop_manager=SimpleNamespace(_players=jogadores),
        display_authority="game",
    )
    return daemon, leitores


def _apertar_todos(daemon: Any, leitores: dict[str, Leitor], valor: int) -> None:
    daemon._last_state = SimpleNamespace(l2_raw=0, r2_raw=valor)
    for leitor in leitores.values():
        leitor.r2_raw = valor


def test_o_passo_leva_o_aperto_de_cada_jogador_ao_controle_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tv, "receita_ativa", lambda daemon: _LIGADA)
    daemon, leitores = _mesa()
    luz = AtuadorDeMentira(tv.CANAL_LUZ)
    passo = tv.Passo(daemon, tv.TatoVivo([luz]))
    passo(0.0)
    _apertar_todos(daemon, leitores, 255)
    passo(0.02)
    passo(0.04)
    assert sorted(u for u, _ in luz.escritas) == sorted(QUATRO)


def test_no_modo_nativo_o_passo_nao_escreve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "receita_ativa", lambda daemon: _LIGADA)
    daemon, leitores = _mesa(backend=None)
    luz = AtuadorDeMentira(tv.CANAL_LUZ)
    motor = tv.TatoVivo([luz])
    passo = tv.Passo(daemon, motor)
    _apertar_todos(daemon, leitores, 255)
    passo(0.0)
    assert luz.escritas == []
    assert motor.contadores["recusas_do_modo"] == 4


def _pads(daemon: Any) -> list[Pad]:
    return [daemon._gamepad_device, *(j.vpad for j in daemon._coop_manager._players.values())]


@pytest.mark.parametrize(("vista_abrir", "escreve"), [(True, True), (False, False)])
def test_o_passo_ve_a_sessao_abrir_e_esquece_o_carimbo_da_anterior(
    monkeypatch: pytest.MonkeyPatch, vista_abrir: bool, escreve: bool
) -> None:
    monkeypatch.setattr(tv, "receita_ativa", lambda daemon: _LIGADA)
    daemon, leitores = _mesa(backend="uhid")
    for pad in _pads(daemon):
        # A barra foi do jogo na sessão de antes; o pad fechou e guardou o carimbo.
        pad.visto_ha_s = {"lightbar": 10.0}
        pad.game_open = not vista_abrir
    luz = AtuadorDeMentira(tv.CANAL_LUZ)
    passo = tv.Passo(daemon, tv.TatoVivo([luz]))
    passo(0.0)
    for pad in _pads(daemon):
        pad.game_open = True
    passo(0.02)
    _apertar_todos(daemon, leitores, 255)
    passo(0.04)
    passo(0.06)
    assert sorted(u for u, _ in luz.escritas) == (sorted(QUATRO) if escreve else [])


def test_receita_desligada_o_passo_nao_le_controle_nenhum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tv, "receita_ativa", lambda daemon: tv.DESLIGADA)
    daemon, leitores = _mesa()
    luz = AtuadorDeMentira(tv.CANAL_LUZ)
    motor = tv.TatoVivo([luz])
    _apertar_todos(daemon, leitores, 255)
    assert tv.Passo(daemon, motor)(0.0) == 0
    assert motor.contadores["eventos"] == 0
    assert motor.estado()["ligado"] is False


def test_o_dedo_tem_histerese() -> None:
    borda = tv.BordaDoDedo()
    assert borda.ver(P1, 0, 200, 0.0)
    assert borda.ver(P1, 0, 120, 0.1) == []  # não soltou abaixo de 96
    assert borda.ver(P1, 0, 200, 0.2) == []
    assert borda.ver(P1, 0, 50, 0.3) == []
    [evento] = borda.ver(P1, 0, 200, 0.4)
    assert evento.lado == tv.LADO_DIREITO


def test_o_daemon_sobe_o_motor_logo_depois_da_luz_do_mic() -> None:
    from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY

    nomes = [p.nome for p in SUBSYSTEM_REGISTRY]
    assert nomes.index("luz_do_mic") < nomes.index("tato_vivo") < nomes.index("alto_falante")


def test_o_tique_que_falha_nao_derruba_o_laco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O laço de 60 Hz chama `tique_do_laco`: um tique que levanta vira log, e o seguinte vem."""
    passo = tv.Passo(SimpleNamespace(), tv.TatoVivo())

    def quebra(_agora: float) -> tv.Receita:
        raise RuntimeError("perfil ilegível")

    monkeypatch.setattr(passo, "receita_de_agora", quebra)
    assert passo.tique_do_laco(0.0) == 0
    assert passo.tique_do_laco(1.0) == 0
