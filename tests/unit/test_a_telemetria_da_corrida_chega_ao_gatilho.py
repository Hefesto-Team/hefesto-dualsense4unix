"""A telemetria da corrida chega ao gatilho (A-TELEMETRIA-DA-CORRIDA-CHEGA-AO-GATILHO-01).

Os pacotes são sintéticos, montados byte a byte nos deslocamentos de
``docs/protocol/telemetria-da-corrida.md`` (não pela função que o produto usa para ler). A porta é
um socket UDP de verdade no localhost, numa porta livre; o motor do tato é o de produção, com o
perfil de mentira e um backend que anota cada bloco, cada fim de sessão e cada toque. Nada toca o
aparelho, o jogo ou o Proton.

MORDIDAS: tirar o portão de parado de ``em_movimento`` reprova
``test_o_mesmo_pacote_com_o_carro_parado_nao_da_nada``; trocar o ``ENDERECO`` da porta por
``0.0.0.0`` reprova ``test_a_porta_so_abre_no_localhost_e_so_com_a_corrida_ou_a_simulacao``; tirar o
teto de subidas de ``LuzDaRotacao.andar`` reprova
``test_a_arrancada_ate_o_corte_sobe_tres_degraus_no_primeiro_segundo``; tirar o ``decidir`` do
gatilho do atuador reprova ``test_o_jogo_que_escreve_o_gatilho_decide_naquele_controle``.
"""
from __future__ import annotations

import math
import socket
import struct
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.trigger_effects import vibration
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems import telemetria_do_jogo as tj
from hefesto_dualsense4unix.integrations import telemetria_de_corrida as tc
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as computador
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

P1 = "aa:bb:cc:00:00:41"
QUATRO = (P1, "aa:bb:cc:00:00:42", "aa:bb:cc:00:00:43", "aa:bb:cc:00:00:44")
TIQUE = 1.0 / 60.0
AUTOMATICO = {"modo": "automatico"}  # (noqa-acento)


_TAMANHO = {"sled": 232, "dash": 311, "horizon": 324, "motorsport_2023": 331}
_INICIO_DO_DASH = {"dash": 232, "horizon": 244, "motorsport_2023": 232}


def _pacote(
    formato: str = "dash", *, corrida: bool = True, rpm: float = 4000.0,
    rpm_maximo: float = 8000.0, rpm_ocioso: float = 800.0, aceleracao: float = 0.0,
    vel_z: float = 0.0, razao: float = 0.0, giro: float = 0.0, zebra: bool = False,
    combinada: float = 0.0, velocidade: float = 0.0, acelerador: int = 0, freio: int = 0,
    marcha: int = 2,
) -> bytes:
    dados = bytearray(_TAMANHO[formato])
    struct.pack_into("<i", dados, 0, 1 if corrida else 0)
    struct.pack_into("<fff", dados, 8, rpm_maximo, rpm_ocioso, rpm)
    struct.pack_into("<f", dados, 28, aceleracao)
    struct.pack_into("<f", dados, 40, vel_z)
    struct.pack_into("<ffff", dados, 84, *(razao,) * 4)
    struct.pack_into("<ffff", dados, 100, *(giro,) * 4)
    struct.pack_into("<i", dados, 120, 1 if zebra else 0)
    struct.pack_into("<f", dados, 188, combinada)
    if formato != "sled":
        b = _INICIO_DO_DASH[formato]
        struct.pack_into("<f", dados, b + 12, velocidade)
        struct.pack_into("<BB", dados, b + 71, acelerador, freio)
        struct.pack_into("<B", dados, b + 75, marcha)
    return bytes(dados)


def _ler(dados: bytes) -> tc.EstadoDaCorrida:
    estado = tc.ler_o_pacote(dados)
    assert estado is not None, len(dados)
    return estado


def _travando(**mais: Any) -> bytes:
    """A roda travada sob freio, a 20 m/s."""
    return _pacote(**{"velocidade": 20.0, "freio": 230, "razao": -1.4, "giro": 0.0, **mais})


@pytest.mark.parametrize("formato", ["dash", "horizon", "motorsport_2023"])
def test_os_tres_formatos_longos_dao_os_pedais_a_marcha_e_a_rotacao(formato: str) -> None:
    estado = tc.ler_o_pacote(_pacote(
        formato, rpm=7000.0, velocidade=33.0, acelerador=255, freio=51, marcha=4, zebra=True,
        combinada=1.75, giro=12.0))
    assert estado is not None and estado.formato == formato
    assert (estado.rpm, estado.rpm_maximo, estado.rpm_ocioso) == (7000.0, 8000.0, 800.0)
    assert estado.velocidade == pytest.approx(33.0)
    assert estado.acelerador == 1.0 and estado.marcha == 4
    assert estado.freio == pytest.approx(0.2)
    assert estado.na_zebra == (False, True, False, False)
    assert estado.patinacao_combinada[2] == pytest.approx(1.75)
    assert estado.giro_das_rodas == (12.0, 12.0, 12.0, 12.0)


def test_o_formato_curto_nao_tem_pedais_e_o_tamanho_estranho_nao_vira_estado() -> None:
    curto = tc.ler_o_pacote(_pacote("sled", vel_z=9.0))
    assert curto is not None and curto.formato == "sled"
    assert curto.acelerador is None and curto.marcha is None and not curto.tem_pedais
    assert curto.velocidade_do_carro == pytest.approx(9.0), "no curto, o módulo do vetor"
    assert tc.ler_o_pacote(bytes(300)) is None
    assert tc.ler_o_pacote(b"") is None
    assert tj.pedido_da_corrida(_ler(_pacote("sled", vel_z=20.0, razao=-1.4))
                                ) == tj.SEM_PEDIDO


def test_o_montador_do_ensaio_bate_com_o_documento() -> None:
    for formato in _TAMANHO:
        montado = tc.montar_o_pacote(formato, rpm=5000.0, velocidade=10.0, acelerador=128,
                                     freio=0, marcha=3)
        assert len(montado) == _TAMANHO[formato]
        estado = tc.ler_o_pacote(montado)
        assert estado is not None and estado.rpm == 5000.0


def test_a_roda_travada_sob_freio_da_o_pulso_do_abs_no_l2() -> None:
    pedido = tj.pedido_da_corrida(_ler(_travando()))
    assert pedido.l2 == (tj.EFEITO_ABS, tj.AMPLITUDE_DO_ABS)
    assert pedido.r2 is None
    assert tj.bloco_do_pedido(*pedido.l2) == tv._bloco_do_efeito(
        vibration(0, tj.AMPLITUDE_DO_ABS, tj.FREQUENCIA_DO_ABS_HZ))
    assert tj.pedido_da_corrida(_ler(_travando(razao=-0.8))).l2 is None


def test_o_mesmo_pacote_com_o_carro_parado_nao_da_nada() -> None:
    """Prova da D-2210-OS-VALORES-DE-PARTIDA-DA-CORRIDA."""
    parado = _ler(_travando(velocidade=0.0, giro=0.0))
    assert not tj.em_movimento(parado)
    assert tj.pedido_da_corrida(parado) == tj.SEM_PEDIDO
    saindo = _ler(_pacote(velocidade=0.0, giro=40.0, acelerador=255, combinada=2.0))
    assert tj.pedido_da_corrida(saindo).r2 is not None


def test_a_patinacao_sob_acelerador_vibra_o_r2_mais_forte_quanto_mais_patina() -> None:
    def r2(combinada: float, acelerador: int = 255) -> tuple[str, int] | None:
        return tj.pedido_da_corrida(_ler(_pacote(
            velocidade=15.0, giro=60.0, acelerador=acelerador, combinada=combinada))).r2

    assert r2(0.9) is None, "com aderência, nada"
    leve, forte = r2(1.2), r2(2.5)
    assert leve is not None and forte is not None
    assert leve[0] == forte[0] == tj.EFEITO_PATINACAO
    assert leve[1] < forte[1] <= 8
    assert r2(2.5, acelerador=20) is None, "sem acelerador não é patinação"


def test_a_zebra_toca_de_leve_e_a_patinacao_vence_a_zebra() -> None:
    zebra = tj.pedido_da_corrida(_ler(_pacote(velocidade=15.0, zebra=True)))
    assert zebra.r2 == (tj.EFEITO_ZEBRA, tj.AMPLITUDE_DA_ZEBRA)
    as_duas = tj.pedido_da_corrida(_ler(_pacote(
        velocidade=15.0, zebra=True, acelerador=255, combinada=2.0)))
    assert as_duas.r2 is not None and as_duas.r2[0] == tj.EFEITO_PATINACAO
    assert tj.PRIORIDADE.index(tj.EFEITO_PATINACAO) < tj.PRIORIDADE.index("superficie")


def test_a_troca_de_marcha_da_um_toque_e_a_batida_um_impacto_que_vence_a_marcha() -> None:
    leitor = tj.LeitorDosToques()
    assert leitor.ver(_ler(_pacote(velocidade=20.0, marcha=2)), 0.0) is None
    marcha = leitor.ver(_ler(_pacote(velocidade=20.0, marcha=3)), 0.1)
    assert marcha is not None and marcha.forma == formas.TOQUE
    batida = leitor.ver(_ler(_pacote(velocidade=20.0, marcha=4, aceleracao=-45.0)), 0.2)
    assert batida is not None and batida.forma == formas.IMPACTO
    assert batida.energia == pytest.approx(45.0 / tj.BATIDA_CHEIA_M_S2)
    assert leitor.ver(_ler(_pacote(velocidade=20.0, marcha=4, aceleracao=-45.0)),
                      0.3) is None
    assert leitor.ver(_ler(_pacote(velocidade=0.0, marcha=1)), 1.0) is None


def test_a_porta_so_abre_no_localhost_e_so_com_a_corrida_ou_a_simulacao() -> None:
    """Prova da D-2210-A-TELEMETRIA-SO-NO-LOCALHOST-E-SO-NA-CORRIDA."""
    tel = tj.TelemetriaDoJogo(porta=0)
    try:
        assert tel.andar(0.0, "fps") == 0 and not tel.aberta
        assert tel.andar(0.0, None) == 0 and not tel.aberta
        tel.andar(0.0, "corrida")
        assert tel.aberta
        endereco = tel.endereco_escutado
        assert endereco is not None and endereco[0] == "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as jogo:
            jogo.sendto(_travando(), endereco)
            jogo.sendto(bytes(17), endereco)
        lidos = 0
        for _ in range(50):
            lidos += tel.andar(0.01, "simulacao")
            if lidos >= 2:
                break
        assert lidos == 2
        assert tel.contadores["pacotes"] == 1 and tel.contadores["ignorados"] == 1
        assert tel.pedido(0.02).l2 is not None
        tel.andar(0.03, "acao")  # (noqa-acento)
        assert not tel.aberta and tel.ultimo is None, "o estilo saiu: a porta fecha"
    finally:
        tel.fechar()


def test_sem_pacote_ha_meio_segundo_a_corrida_cala() -> None:
    tel = tj.TelemetriaDoJogo(porta=0)
    tel.alimentar(_travando(), 1.0)
    assert tel.pedido(1.4).l2 is not None
    assert tel.pedido(1.6) == tj.SEM_PEDIDO
    tel.alimentar(_travando(corrida=False), 2.0)
    assert tel.pedido(2.0) == tj.SEM_PEDIDO, "no menu (IsRaceOn 0), nada"


def _subidas(cores: list[tuple[int, int, int]]) -> list[int]:
    degraus = [tj.CORES_DA_ROTACAO.index(c) for c in cores]
    return [i for i in range(1, len(degraus)) if degraus[i] > degraus[i - 1]]


def test_a_luz_nao_passa_de_tres_subidas_por_segundo_com_a_rotacao_no_corte() -> None:
    tel = tj.TelemetriaDoJogo(porta=0)
    cores: list[tuple[int, int, int]] = []
    instantes: list[float] = []
    for n in range(int(3.0 * 30)):
        agora = n / 30.0
        rpm = 7928.0 if int(agora * 20) % 2 == 0 else 6560.0
        tel.alimentar(_pacote(rpm=rpm, velocidade=40.0), agora)
        cor = tel.cor_da_rotacao(agora)
        assert cor is not None
        cores.append(cor)
        instantes.append(agora)
    subidas = [instantes[i] for i in _subidas(cores)]
    for inicio in subidas:
        assert sum(1 for t in subidas if inicio <= t < inicio + 1.0) <= tv.TETO_DA_LUZ_POR_S
    assert tj.CORES_DA_ROTACAO[-1] in cores, "no corte, a cor do corte aparece"


def test_a_arrancada_ate_o_corte_sobe_tres_degraus_no_primeiro_segundo() -> None:
    tel = tj.TelemetriaDoJogo(porta=0)
    cores: list[tuple[int, int, int]] = []
    for n in range(int(2.0 * 60)):
        agora = n / 60.0
        rpm = 800.0 + min(1.0, agora / 0.2) * 7200.0
        tel.alimentar(_pacote(rpm=rpm, velocidade=10.0), agora)
        cor = tel.cor_da_rotacao(agora)
        assert cor is not None
        cores.append(cor)
    no_primeiro = [i for i in _subidas(cores) if i < 60]
    assert len(no_primeiro) == tv.TETO_DA_LUZ_POR_S, "quatro degraus, só três subidas no segundo"
    assert cores[-1] == tj.CORES_DA_ROTACAO[-1], "no segundo seguinte, a cor do corte chega"


def test_a_luz_da_rotacao_vai_do_verde_ao_vermelho_e_some_sem_corrida() -> None:
    tel = tj.TelemetriaDoJogo(porta=0)
    tel.alimentar(_pacote(rpm=900.0), 0.0)
    assert tel.cor_da_rotacao(0.0) == tj.CORES_DA_ROTACAO[0]
    tel.alimentar(_pacote(rpm=8000.0), 1.0)
    assert tel.cor_da_rotacao(1.0) == tj.CORES_DA_ROTACAO[-1]
    assert tel.cor_da_rotacao(2.0) is None, "sem pacote há meio segundo, a barra volta"


def test_a_barra_de_cada_controle_ganha_a_cor_da_rotacao_no_brilho_do_perfil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(luz, "economia_da_mesa", lambda: False)
    monkeypatch.setattr(luz, "controles_em_economia", lambda: frozenset())
    tel = tj.TelemetriaDoJogo(porta=0)
    tel.alimentar(_pacote(rpm=8000.0), 0.0)
    daemon = SimpleNamespace(_telemetria_do_jogo=tel)
    passo = luz.Passo(daemon, SimpleNamespace())  # type: ignore[arg-type]
    passo._perfil = Profile(name="Corrida", match=MatchAny(), estilo="corrida")
    controles = [SimpleNamespace(uniq=u) for u in QUATRO]
    planos = passo._planos_da_corrida(controles, 0.0)
    assert set(planos) == set(QUATRO)
    for plano in planos.values():
        assert plano.efeito.cores == (tj.CORES_DA_ROTACAO[-1],)
    assert passo._planos_da_corrida(controles, 5.0) == {}


class _Backend:
    """O backend fiel ao de produção: o lado só se solta se ainda é o bloco dado."""

    def __init__(self) -> None:
        self.blocos: list[tuple[str, str, bytes]] = []
        self.sessoes: list[str] = []
        self.soltos: list[tuple[str, str]] = []
        self.no_aparelho: dict[tuple[str, str], bytes] = {}

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.blocos.append((uniq, side, bytes(block)))
        self.no_aparelho[(uniq, side)] = bytes(block)
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.sessoes.append(uniq)
        for chave in [c for c in self.no_aparelho if c[0] == uniq]:
            del self.no_aparelho[chave]
        return True

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, side: str, block: bytes) -> bool:
        if self.no_aparelho.get((uniq, side)) != bytes(block):
            return False
        del self.no_aparelho[(uniq, side)]
        self.soltos.append((uniq, side))
        return True

    def de(self, uniq: str, lado: str) -> list[bytes]:
        return [b for u, s, b in self.blocos if u == uniq and s == lado]


class _AltoFalante:
    def __init__(self) -> None:
        self.toques: list[tuple[str, float, str]] = []

    def tocar_o_toque(self, uniq: str, energia: float, lado: str, duracao_ms: int,
                      forma: str = formas.TOQUE) -> bool:
        self.toques.append((uniq, energia, forma))
        return True

    def tocar_o_corpo(self, uniq: str, amostras: Any, lado: str = "centro") -> bool:
        return True


class _Pad:
    def __init__(self, backend: str = "uinput") -> None:
        self.backend = backend
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = False


class _Leitor:
    l2_raw = 0
    r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


@dataclass
class _Mesa:
    daemon: Any
    backend: _Backend
    alto_falante: _AltoFalante
    tel: tj.TelemetriaDoJogo
    passo: tv.Passo
    pads: dict[str, _Pad]
    t: float = 0.0
    leitores: dict[str, _Leitor] = field(default_factory=dict)

    def rodar(self, segundos: float, pacote: bytes | None = None) -> None:
        fim = self.t + segundos
        while self.t < fim - 1e-9:
            if pacote is not None:
                self.tel.alimentar(pacote, self.t)
            self.passo(self.t)
            self.t += TIQUE

    def frear(self, valor: int = 255) -> None:
        self.daemon._last_state = SimpleNamespace(l2_raw=valor, r2_raw=0)


def _mesa(monkeypatch: pytest.MonkeyPatch, *, estilo: str = "corrida", backend: str = "uinput",
          economia: set[str] | None = None) -> _Mesa:
    """``backend``: ``uinput`` é o modo Xbox, ``uhid`` o DualSense; ``economia`` é mutável."""
    na_economia = set() if economia is None else economia
    perfil = Profile.model_validate(
        {"name": "Corrida", "match": {"type": "any"}, "estilo": estilo, "triggers": AUTOMATICO})
    monkeypatch.setattr(loader, "perfil_em_disco", lambda _nome: perfil)
    monkeypatch.setattr(computador, "o_que_vale", lambda p: p)
    monkeypatch.setattr(tv, "_PELO_CARREGADOR", None)
    monkeypatch.setattr(tv, "_VISTA_LIDA", None)
    monkeypatch.setattr(tv, "_controle_na_economia", lambda u: u in na_economia)
    escritor, alto_falante = _Backend(), _AltoFalante()
    pads = {uniq: _Pad(backend) for uniq in QUATRO}
    leitores = {uniq: _Leitor() for uniq in QUATRO[1:]}
    tel = tj.TelemetriaDoJogo(porta=0)
    daemon = SimpleNamespace(
        controller=SimpleNamespace(
            primary_uniq=P1,
            set_game_trigger_for=escritor.set_game_trigger_for,
            end_game_session_for=escritor.end_game_session_for,
            soltar_o_gatilho_do_jogo_for=escritor.soltar_o_gatilho_do_jogo_for),
        _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
        _gamepad_device=pads[P1],
        _coop_manager=SimpleNamespace(_players={
            uniq: SimpleNamespace(vpad=pads[uniq], reader=leitores[uniq]) for uniq in QUATRO[1:]}),
        _alto_falante_subsystem=alto_falante,
        _telemetria_do_jogo=tel,
        display_authority="game",
        store=SimpleNamespace(active_profile="Corrida"),
    )
    motor = tv.TatoVivo(tv.atuadores_de_producao(daemon))
    daemon._tato_vivo = motor
    mesa = _Mesa(daemon, escritor, alto_falante, tel, tv.Passo(daemon, motor), pads,
                 leitores=leitores)
    mesa.rodar(0.1)
    return mesa


_ABS = tj.bloco_do_pedido(tj.EFEITO_ABS, tj.AMPLITUDE_DO_ABS)


@pytest.mark.parametrize("modo", ["uinput", "uhid"])
def test_os_quatro_controles_sentem_o_abs_e_a_volta_devolve_o_perfil(
    monkeypatch: pytest.MonkeyPatch, modo: str,
) -> None:
    mesa = _mesa(monkeypatch, backend=modo)
    mesa.rodar(1.0, _travando())
    for uniq in QUATRO:
        assert mesa.backend.de(uniq, "left") == [_ABS], uniq
        assert mesa.backend.de(uniq, "right") == [], "o R2 fica no perfil"
    mesa.rodar(0.2, _travando(razao=-0.5))
    assert sorted(mesa.backend.sessoes) == sorted(QUATRO)


def test_o_jogo_que_escreve_o_gatilho_decide_naquele_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch)
    mesa.pads[QUATRO[1]].visto_ha_s["trigger"] = 0.1
    mesa.rodar(0.5, _travando())
    assert mesa.backend.de(QUATRO[1], "left") == []
    assert mesa.backend.de(P1, "left") == [_ABS]


def test_a_marcha_toca_nos_quatro_e_o_jogo_que_fala_na_haptica_cala_a_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch)
    mesa.pads[QUATRO[2]].visto_ha_s["audio_do_jogo"] = 0.1
    mesa.rodar(0.2, _pacote(velocidade=20.0, marcha=2))
    mesa.rodar(0.1, _pacote(velocidade=20.0, marcha=3))
    tocados = [(u, f) for u, _e, f in mesa.alto_falante.toques if f == formas.TOQUE]
    assert sorted(u for u, _f in tocados) == sorted(set(QUATRO) - {QUATRO[2]})


def test_parado_nada_chega_ao_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch)
    mesa.rodar(1.0, _travando(velocidade=0.0, giro=0.0))
    assert not mesa.backend.blocos and not mesa.alto_falante.toques


def test_o_abs_do_jogo_vence_o_momento_do_freio_e_o_momento_volta_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch)
    mesa.frear()
    mesa.rodar(1.0, _pacote(velocidade=20.0, freio=255))
    momento = tv._bloco_do_efeito(vibration(2, 3, 15))
    assert mesa.backend.de(P1, "left") == [momento]
    mesa.rodar(0.5, _travando())
    assert mesa.backend.de(P1, "left") == [momento, _ABS], "o ABS do jogo vence o do estilo"
    mesa.rodar(0.5, _pacote(velocidade=20.0, freio=255))
    assert mesa.backend.de(P1, "left")[-1] == momento, "a roda agarrou: o momento volta"
    assert P1 not in mesa.backend.sessoes
    assert sorted(mesa.backend.sessoes) == sorted(QUATRO[1:])


def test_fora_da_corrida_e_da_simulacao_o_atuador_nao_escreve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, estilo="fps")
    mesa.tel.andar(mesa.t, tv.estilo_ativo(mesa.daemon))
    assert not mesa.tel.aberta
    assert math.isinf(mesa.tel.recebido_em)


def test_o_toque_que_o_motor_nao_levou_a_tempo_caduca_e_nao_sai_em_rajada() -> None:
    tel = tj.TelemetriaDoJogo(porta=0)
    tel.alimentar(_pacote(velocidade=20.0, marcha=2), 0.0)
    tel.alimentar(_pacote(velocidade=20.0, marcha=3), 0.02)
    agora = 0.02
    while agora < 2.0:
        agora += TIQUE
        tel.alimentar(_pacote(velocidade=20.0, marcha=3), agora)
    assert tel.tirar_os_toques(agora) == [], "a troca de marcha de dois segundos atrás não toca"
    tel.alimentar(_pacote(velocidade=20.0, marcha=4), agora)
    assert [t.tipo for t in tel.tirar_os_toques(agora)] == ["marcha"]


def test_na_bateria_longa_o_momento_nao_cede_o_lado_a_corrida_que_nao_escreve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    economia: set[str] = set()
    mesa = _mesa(monkeypatch, economia=economia)
    mesa.frear()
    mesa.rodar(1.0, _pacote(velocidade=20.0, freio=255))
    momento = tv._bloco_do_efeito(vibration(2, 3, 15))
    assert mesa.backend.de(P1, "left") == [momento]
    economia.add(P1)
    mesa.rodar(0.5, _travando())
    assert _ABS not in mesa.backend.de(P1, "left"), "na Bateria longa a corrida não escreve"
    assert P1 in mesa.backend.sessoes, "o momento devolve o lado, não o larga vibrando"
