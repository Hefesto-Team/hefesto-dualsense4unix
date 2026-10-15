"""O motor dos momentos não reescreve o bloco e lê o clique
(O-MOTOR-DOS-MOMENTOS-NAO-REESCREVE-O-BLOCO-E-LE-O-CLIQUE-01).

Cinco coisas, todas com relógio injetado, um backend que anota cada bloco e cada devolução, e
os quatro controles (P1 a P4) na mesa:

1. a marca do que está escrito é o BLOCO: a volta do `a_cada_ms` não reescreve o mesmo `26 …`;
2. o «passou do clique» nasce do status 2 do Disparo, lido do report de entrada do cabo e do
   rádio (o decodificador de verdade), e sem o status cai no relógio do aperto;
3. o «pronto» toma o gatilho por 60 a 150 ms, por cima de tudo, e devolve o bloco de antes;
   as escritas dele contam no teto;
4. as quatro pendências da costura dos momentos saem pelo mesmo ponto de devolução: o ritmo do
   tiro do outro lado, a Bateria longa, o «sempre» sem fim e o motor calado.

MORDIDAS (cada uma reprova o teste que a nomeia, e o arquivo volta idêntico):
voltar a marca `(bloco, repetição)` reprova `test_a_volta_do_a_cada_ms_nao_reescreve_o_bloco`;
tirar a devolução do motor calado reprova `test_o_motor_calado_devolve_o_bloco_ao_aparelho`;
tirar o `soltar_lado` do ritmo reprova `test_o_ritmo_do_outro_lado_nao_fica_preso`;
tirar a checagem da Bateria longa reprova `test_a_bateria_longa_para_os_momentos`;
tirar o teto do «sempre» reprova `test_o_sempre_sem_fim_expira_e_devolve_a_sessao`;
tirar a ordem do «pronto» reprova `test_o_pronto_vai_por_cima_de_qualquer_outro_momento`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    extract_estado_do_gatilho,
)
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as computador
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

P1 = "aa:bb:cc:00:00:41"
P2 = "aa:bb:cc:00:00:42"
P3 = "aa:bb:cc:00:00:43"
P4 = "aa:bb:cc:00:00:44"
QUATRO = (P1, P2, P3, P4)
TIQUE = 1.0 / 60.0
FOLGA = 2 * TIQUE + 1e-6

PINO = {"mode": "Weapon", "params": [3, 7, 230]}  # o Pino que falha: só liga a receita dos momentos
FPS_MACHINE = {"mode": "Machine", "params": [0, 9, 5, 24]}


def _bloco(modo: str, **valores: int) -> bytes:
    """O bloco esperado, montado à parte: os padrões do modo, os números e o layout do relatório."""
    spec = get_spec(modo)
    padroes = {p.name: p.default for p in spec.params} if spec is not None else {}
    f = build_from_name(modo, {**padroes, **valores}).forces
    efeito = build_from_name(modo, {**padroes, **valores})
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


def _usb(l2: int = 0, r2: int = 0) -> bytes:
    """Report `0x01` do cabo com o nibble alto de cada gatilho (R2 em 42, L2 em 43)."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[43], raw[42] = l2 << 4, r2 << 4
    return bytes(raw)


def _bt(l2: int = 0, r2: int = 0) -> bytes:
    """Report `0x31` do rádio, com o CRC de entrada (R2 em 43, L2 em 44)."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0], raw[1] = 0x31, 0x01
    raw[44], raw[43] = l2 << 4, r2 << 4
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    return bytes(raw)


class Backend:
    """As APIs por controle do backend, anotando o instante de cada bloco e de cada volta."""

    def __init__(self) -> None:
        self.agora = 0.0
        self.blocos: list[tuple[float, str, str, bytes]] = []
        self.sessoes: list[tuple[float, str]] = []
        self.soltos: list[tuple[float, str, str, bytes]] = []

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.blocos.append((self.agora, uniq, side, bytes(block)))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.sessoes.append((self.agora, uniq))
        return True

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, side: str, bloco: bytes) -> bool:
        self.soltos.append((self.agora, uniq, side, bytes(bloco)))
        return True

    def de(self, uniq: str, lado: str | None = None) -> list[tuple[float, bytes]]:
        return [(t, b) for t, u, s, b in self.blocos if u == uniq and lado in (None, s)]

    def voltou(self, uniq: str) -> list[float]:
        return [t for t, u in self.sessoes if u == uniq]


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


class _Fisico:
    """O leitor do físico: o status do Disparo vem do decodificador real dos reports."""

    def __init__(self) -> None:
        self.estado_do_gatilho: tuple[int, int] | None = None

    def alimentar(self, report: bytes) -> None:
        self.estado_do_gatilho = extract_estado_do_gatilho(report)


@dataclass
class Mesa:
    daemon: Any
    backend: Backend
    motor: tv.TatoVivo
    passo: tv.Passo
    leitores: dict[str, _Leitor]
    fisicos: dict[str, _Fisico]
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

    def disparo(self, uniq: str, estado: int, via: str = "usb") -> None:
        """O report de entrada do controle diz que o status do Disparo (R2) é `estado`."""
        self.fisicos[uniq].alimentar((_usb if via == "usb" else _bt)(0, estado))

    def rodar(self, segundos: float) -> None:
        fim = self.t + segundos
        while self.t < fim - 1e-9:
            self.backend.agora = self.t
            self.passo(self.t)
            self.t += TIQUE

    def pular(self, segundos: float) -> None:
        """Avança o relógio sem rodar cada tique, e roda alguns para o motor ver o novo instante."""
        self.t += segundos
        self.rodar(0.1)


def _perfil(**campos: Any) -> Profile:
    return Profile(name="Motor", match=MatchAny(), **campos)


def _imersao_de_mentira() -> ei.Imersao:
    return ei.Imersao("de-mentira", "De mentira", "arma", "Uma imersão só para a régua.",
                      {"Weapon": {"start": 4, "end": 6, "force": 100}})


def _plano(*momentos: ei.Momento, modo: str = "Weapon",
           ajustes: dict[str, int] | None = None) -> tv.PlanoDoGatilho:
    imersao = _imersao_de_mentira()
    return tv.PlanoDoGatilho(
        imersao, modo, "", ajustes if ajustes is not None else {"start": 4, "end": 6, "force": 100},
        momentos)


def _mesa(
    monkeypatch: pytest.MonkeyPatch,
    plano: tv.PlanoDoGatilho | None = None,
    *,
    perfil: Profile | None = None,
) -> Mesa:
    perfil = perfil or _perfil(triggers={"right": PINO})
    monkeypatch.setattr(loader, "perfil_em_disco", lambda _nome: perfil)
    monkeypatch.setattr(computador, "o_que_vale", lambda p: p)
    monkeypatch.setattr(tv, "_PELO_CARREGADOR", None)
    monkeypatch.setattr(tv, "_VISTA_LIDA", None)
    monkeypatch.setattr(schema, "_FONTE_DA_DECLARACAO", None)
    if plano is not None:
        monkeypatch.setattr(
            tv, "momentos_ativos", lambda _d: tv.MapaDosMomentos({"direito": plano}))
    backend = Backend()
    leitores = {u: _Leitor() for u in QUATRO[1:]}
    fisicos = {u: _Fisico() for u in QUATRO}
    controller = SimpleNamespace(
        primary_uniq=P1,
        set_game_trigger_for=backend.set_game_trigger_for,
        end_game_session_for=backend.end_game_session_for,
        soltar_o_gatilho_do_jogo_for=backend.soltar_o_gatilho_do_jogo_for,
    )
    daemon = SimpleNamespace(
        controller=controller,
        _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
        _gamepad_device=_Pad(),
        _motion_reader=fisicos[P1],
        _coop_manager=SimpleNamespace(_players={
            u: SimpleNamespace(vpad=_Pad(), reader=leitores[u], motion_reader=fisicos[u])
            for u in QUATRO[1:]}),
        display_authority="game",
        store=SimpleNamespace(active_profile="Motor"),
    )
    motor = tv.TatoVivo(tv.atuadores_de_producao(daemon))
    daemon._tato_vivo = motor
    mesa = Mesa(daemon, backend, motor, tv.Passo(daemon, motor), leitores, fisicos)
    mesa.rodar(0.1)  # o motor lê a receita e a mesa assenta antes do aperto
    return mesa


# ------------------------------------------------------------ 1. a marca é o bloco


@pytest.mark.parametrize("uniq", QUATRO)
def test_a_volta_do_a_cada_ms_nao_reescreve_o_bloco(
    monkeypatch: pytest.MonkeyPatch, uniq: str
) -> None:
    rajada = ei.Momento("segurando", 0, "Machine", {"strength": 7}, a_cada_ms=100,
                        valem_em=("Machine",))
    mesa = _mesa(monkeypatch, _plano(rajada, modo="Machine", ajustes={
        "start": 0, "end": 9, "strength": 5, "frequency": 8}))
    mesa.apertar(uniq)
    mesa.rodar(2.0)
    escritos = [b for _t, b in mesa.backend.de(uniq, "right")]
    assert escritos == [_bloco("Machine", start=0, end=9, strength=7, frequency=8)], (
        f"o bloco foi escrito {len(escritos)} vezes em 2 s: o ritmo é do firmware")
    assert mesa.motor.contadores["escritas"] == 1


def test_o_bloco_que_muda_escreve_uma_vez_por_mudanca(monkeypatch: pytest.MonkeyPatch) -> None:
    degrau = ei.Momento("segurando", 500, "Machine", {"strength": 8}, valem_em=("Machine",))
    rajada = ei.Momento("segurando", 0, "Machine", {"strength": 7}, a_cada_ms=100,
                        valem_em=("Machine",))
    mesa = _mesa(monkeypatch, _plano(rajada, degrau, modo="Machine", ajustes={
        "start": 0, "end": 9, "strength": 5, "frequency": 8}))
    mesa.apertar(P1)
    mesa.rodar(2.0)
    assert [b for _t, b in mesa.backend.de(P1, "right")] == [
        _bloco("Machine", start=0, end=9, strength=7, frequency=8),
        _bloco("Machine", start=0, end=9, strength=8, frequency=8)]


# ------------------------------------------------------------ 2. o clique do Disparo


def _plano_do_clique() -> tv.PlanoDoGatilho:
    return _plano(ei.Momento(ei.QUANDO_PASSOU_DO_CLIQUE, 150, "Resistance",
                             {"start": 7, "force": 6}))


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("uniq", QUATRO)
def test_o_status_2_do_disparo_dispara_o_passou_do_clique(
    monkeypatch: pytest.MonkeyPatch, uniq: str, via: str
) -> None:
    mesa = _mesa(monkeypatch, _plano_do_clique())
    mesa.apertar(uniq)
    mesa.disparo(uniq, 0, via)
    mesa.rodar(0.5)
    mesa.disparo(uniq, 1, via)
    mesa.rodar(0.5)
    assert mesa.backend.de(uniq) == [], "antes do clique o momento não escreve"
    mesa.disparo(uniq, 2, via)
    passou = mesa.t
    mesa.rodar(0.3)
    [(t, bloco)] = mesa.backend.de(uniq, "right")
    assert bloco == _bloco("Resistance", start=7, force=6)
    assert 0 <= t - passou <= FOLGA, "o momento sai no tique em que o status chega a 2"
    # O bloco novo não mexe no nibble: o status volta a 0 e o momento segue valendo.
    mesa.disparo(uniq, 0, via)
    mesa.rodar(0.5)
    assert len(mesa.backend.de(uniq, "right")) == 1
    mesa.soltar(uniq)
    mesa.rodar(0.2)
    assert len(mesa.backend.voltou(uniq)) == 1, "soltar devolve o gatilho"


def test_sem_o_status_o_passou_do_clique_cai_no_relogio_do_aperto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _plano_do_clique())
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(1.0)  # nenhum report: o aparelho não disse o status
    [(t, bloco)] = mesa.backend.de(P1, "right")
    assert bloco == _bloco("Resistance", start=7, force=6)
    assert 0.15 <= t - apertou <= 0.15 + FOLGA, "sem status, o `apos_ms` conta do aperto"


def test_com_o_status_que_nunca_chega_a_2_o_clique_nao_inventa_o_momento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _plano_do_clique())
    mesa.apertar(P1)
    mesa.disparo(P1, 1)
    mesa.rodar(2.0)
    assert mesa.backend.de(P1) == [], "o dedo não passou do clique: o relógio não vale"


def test_o_status_nao_escreve_nada_no_aparelho(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ler o status é só leitura: com a imersão sem esse momento, nenhum bloco sai."""
    mesa = _mesa(monkeypatch, _plano(
        ei.Momento("ao_apertar", 0, "Resistance", {"start": 7, "force": 6}, dura_ms=50)))
    mesa.apertar(P1)
    mesa.disparo(P1, 2)
    mesa.rodar(1.0)
    assert [b for _t, b in mesa.backend.de(P1)] == [_bloco("Resistance", start=7, force=6)]


# ------------------------------------------------------------ 3. o «pronto»


def test_o_pronto_dura_de_60_a_150_ms() -> None:
    ei.Momento(ei.QUANDO_PRONTO, 500, "Machine", {}, dura_ms=60)
    ei.Momento(ei.QUANDO_PRONTO, 500, "Machine", {}, dura_ms=150)
    for dura in (None, 59, 151):
        with pytest.raises(ValueError):
            ei.Momento(ei.QUANDO_PRONTO, 500, "Machine", {}, dura_ms=dura)


def _plano_do_pronto() -> tv.PlanoDoGatilho:
    return _plano(
        ei.Momento("segurando", 0, "Resistance", {"start": 4, "force": 5}),
        ei.Momento(ei.QUANDO_PRONTO, 500, "Machine",
                   {"start": 4, "end": 9, "strength": 3, "frequency": 40}, dura_ms=150),
        ei.Momento("segurando", 1000, "Resistance", {"start": 4, "force": 7}))


@pytest.mark.parametrize("uniq", QUATRO)
def test_o_pronto_toma_o_gatilho_e_devolve_o_bloco_de_antes(
    monkeypatch: pytest.MonkeyPatch, uniq: str
) -> None:
    mesa = _mesa(monkeypatch, _plano_do_pronto())
    apertou = mesa.t
    mesa.apertar(uniq)
    mesa.rodar(1.5)
    escritas = mesa.backend.de(uniq, "right")
    assert [b for _t, b in escritas] == [
        _bloco("Resistance", start=4, force=5),
        _bloco("Machine", start=4, end=9, strength=3, frequency=40),
        _bloco("Resistance", start=4, force=5),
        _bloco("Resistance", start=4, force=7)]
    for (t, _b), esperado in zip(escritas, (0.0, 0.5, 0.65, 1.0), strict=True):
        assert esperado <= t - apertou <= esperado + FOLGA, (t - apertou, esperado)


def test_o_pronto_conta_no_teto_de_escritas(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _plano_do_pronto())
    mesa.motor.teto = tv.Teto(por_controle=2, total=40)
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(1.5)
    escritas = mesa.backend.de(P1, "right")
    assert mesa.motor.contadores["recusas_do_teto"] > 0, "o pronto gastou a vaga da janela"
    assert [round(t - apertou, 1) for t, _b in escritas][:2] == [0.0, 0.5]
    # A volta do pronto espera a primeira vaga (a do aperto sai da janela de 1 s).
    assert escritas[2][0] - apertou >= 1.0 - 1e-9


def test_o_pronto_vai_por_cima_de_qualquer_outro_momento() -> None:
    pronto = ei.Momento(ei.QUANDO_PRONTO, 0, "Machine",
                        {"start": 4, "end": 9, "strength": 3, "frequency": 40}, dura_ms=100)
    por_baixo = ei.Momento("segurando", 0, "Resistance", {"start": 4, "force": 7})
    plano = _plano(pronto, por_baixo)  # o «pronto» vem ANTES na lista
    assert tv.bloco_do_momento(plano, (0, 1)) == _bloco(
        "Machine", start=4, end=9, strength=3, frequency=40)


# ------------------------------------------------------------ 4. as quatro pendências


def test_o_ritmo_do_outro_lado_nao_fica_preso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um momento segura a sessão no direito; o ritmo do tiro escreveu no esquerdo e vence."""
    perfil = _perfil(estilo="fps", triggers={"right": FPS_MACHINE})
    mesa = _mesa(monkeypatch, perfil=perfil)
    assert mesa.passo.receita_vigente.gatilho_no_ritmo
    mesa.apertar(P1, "direito")  # a rajada do direito segura a sessão
    for _ in range(3):
        mesa.apertar(P1, "esquerdo")
        mesa.rodar(0.1)
        mesa.soltar(P1, "esquerdo")
        mesa.rodar(0.1)
    ritmo = [b for _t, b in mesa.backend.de(P1, "left")]
    assert ritmo, "o ritmo do tiro escreveu no lado que não tem imersão"
    mesa.rodar(3.0)  # passa o prazo de 1,5 s do ritmo, com o direito ainda apertado
    assert [(u, s, b) for _t, u, s, b in mesa.backend.soltos] == [(P1, "left", ritmo[-1])], (
        "o ritmo do esquerdo ficou preso: só a sessão inteira o soltaria")
    assert mesa.backend.sessoes == [], "a sessão segue com o momento do direito"
    mesa.soltar(P1, "direito")
    mesa.rodar(0.2)
    assert mesa.backend.voltou(P1) != []


def _economia(monkeypatch: pytest.MonkeyPatch, ligada: list[bool]) -> None:
    monkeypatch.setattr(schema, "_FONTE_DA_DECLARACAO", lambda: SimpleNamespace(
        orcamento=SimpleNamespace(teto="economia" if ligada[0] else None), controles={}))


def test_a_bateria_longa_para_os_momentos(monkeypatch: pytest.MonkeyPatch) -> None:
    plano = _plano(ei.Momento("segurando", 0, "Resistance", {"start": 4, "force": 5}))
    mesa = _mesa(monkeypatch, plano)
    ligada = [False]
    _economia(monkeypatch, ligada)
    mesa.apertar(P1)
    mesa.rodar(0.5)
    assert len(mesa.backend.de(P1, "right")) == 1 and mesa.backend.voltou(P1) == []
    ligada[0] = True  # a pessoa liga a Bateria longa no meio do aperto
    ligou = mesa.t
    mesa.rodar(1.0)
    [voltou] = mesa.backend.voltou(P1)
    assert ligou <= voltou <= ligou + FOLGA, "os momentos param e o perfil retoma o gatilho"
    assert len(mesa.backend.de(P1, "right")) == 1, "na Bateria longa nada mais se escreve"
    mesa.soltar(P1)
    mesa.rodar(0.2)
    mesa.apertar(P1)
    mesa.rodar(0.5)
    assert len(mesa.backend.de(P1, "right")) == 1
    ligada[0] = False  # sai da Bateria longa: os momentos voltam
    mesa.rodar(0.5)
    assert len(mesa.backend.de(P1, "right")) == 2


def test_o_estatico_da_volta_leva_a_forca_da_bateria_longa() -> None:
    plano = _plano()
    assert plano.bloco_da_volta() == _bloco("Weapon", start=4, end=6, force=100)
    assert plano.bloco_da_volta(economia=True) == _bloco("Weapon", start=4, end=6, force=50)


def test_o_sempre_sem_fim_expira_e_devolve_a_sessao(monkeypatch: pytest.MonkeyPatch) -> None:
    plano = _plano(ei.Momento("sempre", 0, "Weapon", {"start": 4, "end": 6, "force": 255}))
    mesa = _mesa(monkeypatch, plano)
    mesa.rodar(0.5)
    for uniq in QUATRO:
        assert [b for _t, b in mesa.backend.de(uniq, "right")] == [
            _bloco("Weapon", start=4, end=6, force=255)]
    mesa.pular(250.0)
    assert mesa.backend.sessoes == [], "antes do teto o momento segue com a sessão"
    mesa.pular(60.0)  # passados 5 minutos
    assert sorted(u for _t, u in mesa.backend.sessoes) == sorted(QUATRO)
    escritos = len(mesa.backend.blocos)
    mesa.rodar(5.0)
    assert len(mesa.backend.blocos) == escritos, "expirou: nada mais se escreve nem se segura"


def test_o_sempre_com_fim_nao_expira(monkeypatch: pytest.MonkeyPatch) -> None:
    plano = _plano(ei.Momento("sempre", 0, "Weapon", {"start": 4, "end": 6, "force": 255},
                              dura_ms=120, a_cada_ms=830))
    mesa = _mesa(monkeypatch, plano)
    mesa.rodar(0.5)
    mesa.pular(400.0)
    assert len(mesa.backend.de(P1, "right")) >= 2, "a batida segue depois dos 5 minutos"


@pytest.mark.parametrize("uniq", QUATRO)
def test_o_motor_calado_devolve_o_bloco_ao_aparelho(
    monkeypatch: pytest.MonkeyPatch, uniq: str
) -> None:
    plano = _plano(ei.Momento("segurando", 0, "Resistance", {"start": 4, "force": 5}))
    mesa = _mesa(monkeypatch, plano)
    mesa.apertar(uniq)
    mesa.rodar(0.5)
    assert len(mesa.backend.de(uniq, "right")) == 1 and mesa.backend.voltou(uniq) == []
    mesa.daemon.display_authority = "none"  # o jogo saiu de cena (alt-tab, fechou)
    calou = mesa.t
    mesa.rodar(1.0)
    [voltou] = mesa.backend.voltou(uniq)
    assert calou <= voltou <= calou + FOLGA, "o bloco do momento não pode ficar no aparelho"
    assert mesa.backend.soltos == []


def test_o_jogo_que_toma_o_gatilho_continua_sem_devolucao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O contrário do motor calado: o jogo escreve o gatilho, o valor é dele."""
    plano = _plano(ei.Momento("segurando", 0, "Resistance", {"start": 4, "force": 5}))
    mesa = _mesa(monkeypatch, plano)
    mesa.apertar(P1)
    mesa.rodar(0.5)
    mesa.daemon._gamepad_device.visto_ha_s = {"trigger": 0.0}
    mesa.rodar(1.0)
    assert mesa.backend.sessoes == []
    assert mesa.motor.contadores["soltos_ao_jogo"] == 1


# O perfil salvo com a chave que saiu da lista de onze: a tela, o aparelho e o motor dizem o mesmo.
def _linhas_de_ontem() -> list[tuple[str, str, list[int]]]:
    linhas = []
    for chave, velha, ajustes in ei.NUMEROS_DE_ONTEM:
        spec = get_spec(velha)
        assert spec is not None, velha
        posicionais = [int(ajustes[p.name]) for p in spec.params]
        linhas.append((chave, velha, posicionais))
    return linhas


def _bloco_do_perfil(velha: str, posicionais: list[int]) -> bytes:
    """O bloco que o perfil leva ao aparelho: a fábrica, que traduz a chave velha."""
    efeito = build_from_name(velha, list(posicionais))
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


@pytest.mark.parametrize(("chave", "velha", "posicionais"), _linhas_de_ontem(),
                         ids=lambda v: str(v))
def test_o_perfil_de_chave_velha_toca_a_imersao_que_a_tela_mostra(
    chave: str, velha: str, posicionais: list[int],
) -> None:
    from hefesto_dualsense4unix.app.actions import trigger_specs
    from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos as aba

    lado = aba._do_lado({"mode": velha, "params": posicionais}, trigger_specs)
    na_tela = aba._imersao_que_casa(lado["modo-chave"], lado["params"], lado["cru"])
    assert na_tela == chave, (velha, posicionais, na_tela)
    imersao = ei.POR_CHAVE[chave]
    plano = tv._plano_do_lado(SimpleNamespace(mode=velha, params=posicionais))
    if not ei.momentos_no_modo(imersao, lado["modo-chave"]):
        assert plano is None
        return
    assert plano is not None, (velha, posicionais)
    assert plano.imersao.chave == chave
    assert plano.modo == lado["modo-chave"]


@pytest.mark.parametrize(("chave", "velha", "posicionais"), _linhas_de_ontem(),
                         ids=lambda v: str(v))
def test_a_volta_a_mao_e_o_bloco_do_perfil_e_nao_o_da_imersao(
    chave: str, velha: str, posicionais: list[int],
) -> None:
    plano = tv._plano_do_lado(SimpleNamespace(mode=velha, params=posicionais))
    if plano is None:
        pytest.skip(f"{chave} não tem momento no acionamento de hoje")
    assert plano.bloco_da_volta() == _bloco_do_perfil(velha, posicionais), (velha, posicionais)


def test_os_numeros_de_hoje_continuam_voltando_ao_bloco_da_imersao() -> None:
    """Com os números de hoje, o bloco do perfil e o da imersão são o mesmo (nada muda ali)."""
    vistos = 0
    for imersao, modo, estilo, ajustes in ei.todos_os_ajustes():
        spec = get_spec(modo)
        if spec is None or not ei.momentos_no_modo(imersao, modo):
            continue
        posicionais = [int(ajustes.get(p.name, p.default)) for p in spec.params]
        if ei.imersao_dos_numeros(modo, posicionais) != (imersao, estilo):
            continue
        plano = tv._plano_do_lado(SimpleNamespace(mode=modo, params=posicionais))
        assert plano is not None, (imersao.chave, modo, estilo)
        assert plano.bloco_da_volta() == tv._bloco_cru(modo, ajustes), (imersao.chave, modo)
        vistos += 1
    assert vistos >= 10


@pytest.mark.parametrize("numero", [1, 2, 3, 4])
def test_o_perfil_de_chave_velha_por_controle_toca_em_cada_um_dos_quatro(numero: int) -> None:
    """P1 a P4, cabo ou rádio: o lado escrito por um controle passa pela mesma tradução."""
    uniq = f"aa:bb:cc:00:00:4{numero}"
    perfil = _perfil(
        triggers={"left": {"mode": "Rigid", "params": [2, 220]}},
        controllers={uniq: {"triggers": {"right": {"mode": "SemiAutoGun", "params": [4, 6, 7]}}}},
    )
    mapa = tv.planos_do_perfil(perfil)
    direito, esquerdo = mapa.do(uniq, "direito"), mapa.do(uniq, "esquerdo")
    assert direito is not None and direito.imersao.chave == "pino-que-falha"
    assert direito.bloco_da_volta() == _bloco_do_perfil("SemiAutoGun", [4, 6, 7])
    assert esquerdo is not None and esquerdo.imersao.chave == "freio-abs-que-pulsa"
    assert esquerdo.bloco_da_volta() == _bloco_do_perfil("Rigid", [2, 220])
    outro = "aa:bb:cc:00:00:49"
    assert mapa.do(outro, "direito") is None


@pytest.mark.parametrize(("estilo", "chave", "modo"), [
    ("fps", "rajada-que-sobe-sozinha", "Machine"),
    ("corrida", "freio-abs-que-pulsa", "Resistance"),
    ("acao", "clique-no-meio", "Weapon"),  # (noqa-acento): chave
    ("arco", "corda-que-estica", "Bow"),
    ("esportes", "pique-que-cansa", "Resistance"),
    ("terror", "pino-que-falha", "Weapon"),
])
def test_o_automatico_toca_a_da_frente_do_estilo_no_acionamento_de_hoje(
    estilo: str, chave: str, modo: str,
) -> None:
    """O estilo com a chave velha (FPS, Esportes, Terror) acha a da frente do CATALOGO §2.4."""
    plano = tv._plano_do_automatico(estilo)
    assert plano is not None, estilo
    assert (plano.imersao.chave, plano.modo) == (chave, modo)
    assert plano.automatico and plano.bloco_da_volta() == tv._bloco_cru("Off", {})
