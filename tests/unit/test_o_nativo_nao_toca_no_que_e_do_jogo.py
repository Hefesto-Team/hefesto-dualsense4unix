"""DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01, item 3 — o Nativo não toca no que é do jogo.

**O que se mediu** (a bancada de 03/10/2026, 20h30 a 20h31, PRAGMATA com os quatro
pelo rádio, ao trocar para o Nativo): as pontes ``0x32`` do vermelho e do branco
subiram VAZIAS (``escritas_aceitas=0`` por 32 a 47 s, ocupando a vaga do rádio sem
tocar) e o Hefesto reescreveu a barra contra o jogo (``sequestro_segue
reescritas=10``).

**As duas causas, medidas aqui com o produto e dublês da casa:**

1. No Nativo o jogo é dono dos motores de TODOS os controles, e a volta do som
   subia a ponte de quem tinha um fluxo ABERTO no endpoint ou no alto-falante,
   com sinal ou sem: o fluxo aberto e mudo pedia a vaga ao governador e abria o
   hidraw para não escrever nada.
2. A ``VigiaDoSequestro`` rodava também no Nativo e reescrevia a barra e o
   número enquanto o jogo segurava o nó.

**A cura:** no Nativo, quem tem só fluxo mudo ganha um OUVIDO (o gravador que só
escuta o monitor, sem hidraw e sem vaga), e a ponte sobe quando ele ouve o som
do jogo; e a vigia do sequestro não vigia nó nenhum. Fora do Nativo nada muda.
Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core import escritor_cru as ec
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (
    FORJA,
    MESA,
    MOTOR,
    VOZ,
    Mesa,
    no_do,
)
from tests.unit.test_steam_no_fisico_01_o_sequestro_se_corrige_em_um_segundo import (
    JOGO,
    _Controle,
    _daemon,
    _Mesa,
)

NOS = tuple(f"/dev/hidraw{40 + i}" for i in range(4))
UNIQS = tuple(f"aabbcc00003{i}" for i in range(1, 5))


def _daemon_real(*, nativo: bool) -> Any:
    """O ``Daemon`` de verdade, com o Modo Nativo no atributo que o gesto escreve."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    daemon._native_mode = nativo
    assert daemon.is_native_mode() is nativo
    return daemon


class _Governador:
    """Conta quem pede vaga, e recusa: o que se mede é o pedido, e não a ponte."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str]] = []

    def pedir_vaga(self, uniq: str, tipo: str) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
            MOTIVO_CHEIO,
            Recusa,
        )

        self.pedidos.append((uniq, tipo))
        return Recusa(uniq, "", tipo, MOTIVO_CHEIO)


@pytest.fixture
def sala(monkeypatch: pytest.MonkeyPatch) -> Any:
    m = Mesa(monkeypatch)
    yield m
    for ouvido in list(getattr(m.sub, "_ouvidos_do_radio", {}).values()):
        ouvido.descer()
    m.fechar()


def _voltas(sala: Mesa, n: int = 3) -> None:
    for _ in range(n):
        sala.volta()
        time.sleep(0.05)


# --------------------------------------------------------------------------- a ponte


@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=["P1", "P1-P2", "P1-P3", "P1-P4"])
def test_no_nativo_o_fluxo_mudo_nao_sobe_ponte_nem_pede_vaga(sala: Mesa, n: int) -> None:
    """A MORDIDA: o jogo abre o alto-falante e a háptica de todos e não toca nada."""
    quem = MESA[:n]
    sala.sub._daemon = _daemon_real(nativo=True)
    governador = _Governador()
    sala.sub.governador = governador
    sala.abrir_a_sala(*quem)
    _voltas(sala)
    assert governador.pedidos == [], (
        f"no Nativo o fluxo mudo pediu vaga ao rádio: {governador.pedidos}"
    )
    assert sala.sub._pontes == {}, f"subiu ponte sem som do jogo: {sorted(sala.sub._pontes)}"
    assert sala.canos == [], "abriu o hidraw sem som do jogo"


def test_no_nativo_a_ponte_sobe_quando_o_jogo_toca_e_so_a_de_quem_toca(sala: Mesa) -> None:
    """Quatro fluxos abertos; o jogo vibra o P2 e fala pelo P3: só essas duas sobem."""
    sala.sub._daemon = _daemon_real(nativo=True)
    sala.abrir_a_sala(*MESA)
    _voltas(sala, 2)
    assert sala.sub._pontes == {}
    sala.fonte(no_do(MESA[1])).quadro = MOTOR
    sala.fonte(af.nome_do_sink(MESA[2])).quadro = VOZ
    sala.esperar(no_do(MESA[1]), True)
    sala.esperar(af.nome_do_sink(MESA[2]), True)
    _voltas(sala, 2)
    assert sorted(sala.sub._pontes) == sorted([MESA[1], MESA[2]])
    sala.esperar_o_fio(MESA[1], som=False, haptica=True)
    sala.esperar_o_fio(MESA[2], som=True, haptica=False)


def test_no_nativo_quem_tem_ponte_nao_tem_ouvido_e_o_fluxo_fechado_solta_o_ouvido(
    sala: Mesa,
) -> None:
    """O ouvido é só de quem espera o som: subiu a ponte, ele desce; fechou o fluxo, também."""
    sala.sub._daemon = _daemon_real(nativo=True)
    sala.abrir_a_sala(MESA[0], MESA[1])
    _voltas(sala, 2)
    ouvidos = dict(sala.sub._ouvidos_do_radio)
    assert ouvidos, "no Nativo, o fluxo mudo não ganhou ouvido: a ponte nunca subiria"
    assert all(o.vivo for o in ouvidos.values())
    sala.fonte(no_do(MESA[0])).quadro = MOTOR
    sala.esperar(no_do(MESA[0]), True)
    for _ in range(20):
        sala.volta()
        if MESA[0] in sala.sub._pontes:
            break
        time.sleep(0.05)
    assert MESA[0] in sala.sub._pontes
    assert not [n for n, o in sala.sub._ouvidos_do_radio.items() if o.uniq == MESA[0]], (
        "a ponte subiu e o ouvido do mesmo controle ficou de pé na mesma volta"
    )
    sala.servidor.calar(FORJA)
    _voltas(sala, 2)
    assert dict(sala.sub._ouvidos_do_radio) == {}
    for ouvido in ouvidos.values():
        assert not ouvido.vivo, "o ouvido do fluxo que fechou ficou de pé"


def test_fora_do_nativo_a_ponte_segue_subindo_pelo_fluxo(sala: Mesa) -> None:
    """O contraste: fora do Nativo a regra de antes vale (o alto-falante aberto sobe a ponte)."""
    sala.sub._daemon = _daemon_real(nativo=False)
    sala.abrir_a_sala(MESA[0])
    _voltas(sala, 1)
    assert MESA[0] in sala.sub._pontes
    assert dict(sala.sub._ouvidos_do_radio) == {}


# --------------------------------------------------------------------------- a barra


def _vigiar(daemon: Any, *agoras: float) -> list[dict[str, Any]]:
    async def _roteiro() -> list[dict[str, Any]]:
        with structlog.testing.capture_logs() as registros:
            for agora in agoras:
                await conn.vigiar_o_sequestro(daemon, agora=agora)
        return registros

    return asyncio.run(_roteiro())


@pytest.mark.parametrize("n", [1, 4], ids=["P1", "P1-P4"])
def test_no_nativo_a_barra_do_jogo_nao_e_reescrita(n: int) -> None:
    """A MORDIDA: o jogo segura os nós no Nativo, e nenhuma escrita de barra sai."""
    mesa = _Mesa()
    for no in NOS[:n]:
        mesa.abertos.add(no)
        mesa.segurar(no, JOGO)
    controle = _Controle(dict(zip(UNIQS[:n], NOS[:n], strict=True)))
    daemon = _daemon(controle, mesa, nativo=True)
    registros = _vigiar(daemon, *(0.5 * i for i in range(30)))
    assert controle.reescritos == [], f"reescreveu a barra contra o jogo: {controle.reescritos}"
    eventos = {r["event"] for r in registros}
    assert not eventos & {"sequestro_reescrito", "sequestro_segue"}
    assert mesa.sondas == 0, "no Nativo a vigia varreu o /proc atrás de quem é o dono"
    assert ec.PASSO_DA_VIGIA_S < conn.RECONNECT_HOTPLUG_POLL_INTERVAL_SEC
    assert conn.vigia_do_sequestro_de(daemon).vigilante is False


def test_ao_entrar_no_nativo_a_reescrita_para_na_hora_e_volta_ao_sair() -> None:
    """O sequestro defendido fora do Nativo para de ser defendido no Nativo, e volta depois."""
    mesa = _Mesa()
    mesa.abertos.add(NOS[0])
    mesa.segurar(NOS[0], JOGO)
    controle = _Controle({UNIQS[0]: NOS[0]})
    nativo = [False]
    daemon = _daemon(controle, mesa, nativo=False)
    daemon.is_native_mode = lambda: nativo[0]
    _vigiar(daemon, 0.0, 1.0)
    fora = len(controle.reescritos)
    assert fora >= 1, "o contraste: fora do Nativo a vigia defende a barra"
    nativo[0] = True
    registros = _vigiar(daemon, 2.0, 3.0, 4.0, 5.0)
    assert len(controle.reescritos) == fora
    assert "sequestro_encerrado" in {r["event"] for r in registros}
    nativo[0] = False
    _vigiar(daemon, 6.0, 7.0)
    assert len(controle.reescritos) > fora, "fora do Nativo de novo, a vigia não voltou"


def test_no_nativo_quem_espera_a_vaga_com_som_segue_com_o_mesmo_ouvido(sala: Mesa) -> None:
    """O rádio cheio recusa a vaga: o ouvido fica de pé até a ponte subir, sem nascer de novo.

    Derrubar o ouvido no sinal, e não na ponte que subiu, deixava quem espera a
    vaga sem ouvido: o sinal caía para «ninguém escuta» e um gravador novo nascia
    a cada segundo e pouco, enquanto o jogo tocasse.
    """
    sala.sub._daemon = _daemon_real(nativo=True)
    governador = _Governador()
    sala.sub.governador = governador
    sala.abrir_a_sala(MESA[0])
    _voltas(sala, 2)
    ouvido = sala.sub._ouvidos_do_radio.get(no_do(MESA[0]))
    assert ouvido is not None and ouvido.vivo
    sala.fonte(no_do(MESA[0])).quadro = MOTOR
    sala.esperar(no_do(MESA[0]), True)
    fim = time.monotonic() + 2.0
    while time.monotonic() < fim:
        _voltas(sala, 1)
        assert sala.sub._ouvidos_do_radio.get(no_do(MESA[0])) is ouvido, (
            "o ouvido de quem espera a vaga desceu antes de a ponte subir"
        )
    assert ouvido.vivo
    assert [u for u, _ in governador.pedidos] and {u for u, _ in governador.pedidos} == {MESA[0]}, (
        "com o som do jogo, a vaga não foi pedida"
    )
    assert sala.sub._pontes == {}


def test_o_ouvido_do_no_pede_o_monitor_com_os_canais_do_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois canais no alto-falante, quatro no endpoint: o ouvido pede o formato do nó."""
    pedidos: list[dict[str, Any]] = []

    def _monitor(no: str, **kw: Any) -> tuple[Any, Any, str]:
        pedidos.append({"no": no, **kw})
        return None, None, "dublê"

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _monitor)
    assert not af.OuvidoDoNo(
        no="som", uniq=UNIQS[0], canais=af.CANAIS_DO_ENCODER, papel="ouvido-som"
    ).subir()
    assert not af.OuvidoDaPlaca(placa="placa", uniq=UNIQS[0]).subir()
    assert [(p["no"], p["canais"], p["papel"]) for p in pedidos] == [
        ("som", af.CANAIS_DO_ENCODER, "ouvido-som"),
        ("placa", af.CANAIS_DA_HAPTICA, "placa"),
    ]
