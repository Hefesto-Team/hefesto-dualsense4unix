"""A porta devolve a luz e o gatilho que a extensão tomou, por controle.

A escrita de uma extensão em ``luz.set`` e ``gatilho.set`` vai a uma camada própria do controle,
acima do perfil e da escolha de quem usa: some no prazo, no zero ou com a saída da extensão, e o
controle volta ao seu valor resolvido. O hotplug não traz o valor da extensão, e a troca de
transporte no meio do jogo não é saída: a camada atravessa e devolve uma vez só.

A mesa é a do produto (backend, servidor de IPC e porta reais) com handles sem hidraw: quatro
controles, dois por cabo e dois por rádio, os dois do rádio no mesmo adaptador. O que se lê é o
bloco de gatilho que o handle mandaria ao fio e a cor da barra que ele guarda.

MORDIDAS: sem o ``ao_vencer`` da porta o gatilho fica no impacto e a cor no dano; sem o ``vaga`` do
``_devolver_o_que_venceu`` o lado que vence antes não devolve com o outro vivo; sem a camada no
``_merged_desired_for_key`` a troca de transporte perde o que a extensão tem; sem o largar da
camada no ``_close_handles`` a saída não leva a camada; sem o ``_troca_valida_locked`` no largar a
troca de transporte vira saída; sem a rota ``camada`` do ``trigger.set`` o gatilho da extensão cai
na camada de quem usa.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import trigger_effects as te
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.mods.porta import Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import _Cliente

MACS = tuple(f"AA:BB:CC:00:00:{n:02X}" for n in (0x31, 0x32, 0x33, 0x34))
UNIQS = tuple(m.lower() for m in MACS)
PLANOS = tuple(m.replace(":", "").lower() for m in MACS)
CABO, RADIO = ConnectionType.USB, ConnectionType.BT
TRANSPORTES = (CABO, CABO, RADIO, RADIO)
MESAS = pytest.mark.parametrize(
    "transportes", [TRANSPORTES, (RADIO,) * 4],
    ids=["dois-no-cabo-e-dois-no-radio", "quatro-no-radio"])
CORES = ((10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120))
PERFIS = (te.rigid(2, 100), te.rigid(4, 150), te.rigid(6, 200), te.rigid(8, 250))
IMPACTO = te.bloco_do_efeito(te.build_from_name("Feedback", [3, 8]))
OFF = te.bloco_do_efeito(te.off())
DANO = (255, 0, 0)
R2 = slice(10, 21)
L2 = slice(21, 32)
EXT = "extensao:imersao"  # (noqa-acento)


def _handle(transporte: ConnectionType) -> Any:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = transporte
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    inst.connected = True
    inst.writeReport = lambda dados: len(dados)
    return inst


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Cena:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                 perfis: tuple[Any, ...] = PERFIS,
                 transportes: tuple[ConnectionType, ...] = TRANSPORTES) -> None:
        self.transportes = transportes
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        monkeypatch.setattr(radio_da_mesa, "adaptador_por_uniq",
                            lambda uniqs: dict.fromkeys(uniqs, "hci0"))
        self.relogio = _Relogio()
        reader = bp.EvdevReader(device_path=None)
        reader._device_path = None
        self.backend = bp.PyDualSenseController(evdev_reader=reader)
        self.backend._handles = {m: _handle(t) for m, t in zip(MACS, transportes, strict=True)}
        self.backend._primary_key = MACS[0]
        with self.backend._io_lock:
            self.backend._aplicar_os_pisos_de_escrita_locked()
        self.backend.reset_profile_overrides({
            u: OutputSpec(trigger_right=perfis[i], led=CORES[i])
            for i, u in enumerate(PLANOS) if perfis[i] is not None
        })
        for mac, handle in self.backend._handles.items():
            self.backend._reapply_desired(mac, handle)
        daemon = MagicMock()
        daemon.config = DaemonConfig()
        daemon.is_native_mode.return_value = False
        self.servidor = IpcServer(
            controller=self.backend, store=StateStore(), profile_manager=MagicMock(),
            socket_path=tmp_path / "ipc.sock", daemon=daemon)
        self.fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_DUALSENSE,
                                    relogio=self.relogio)
        self.escritas: list[tuple[str, dict[str, Any]]] = []

    async def escritor(self, metodo: str, pedido: dict[str, Any]) -> Any:
        self.escritas.append((metodo, pedido))
        return await self.servidor._handlers[metodo](pedido)

    def r2(self, i: int) -> bytes:
        return bytes(self.backend._handles[MACS[i]]._build_common(rumble_asserted=False)[R2])

    def l2(self, i: int) -> bytes:
        return bytes(self.backend._handles[MACS[i]]._build_common(rumble_asserted=False)[L2])

    def cor(self, i: int) -> tuple[int, int, int]:
        return tuple(self.backend._handles[MACS[i]].light.TouchpadColor)  # type: ignore[return-value]

    def perfil(self, i: int) -> bytes:
        return te.bloco_do_efeito(PERFIS[i])

    async def andar(self, segundos: float) -> None:
        self.relogio.agora += segundos
        self.fonte.andar(self.relogio.agora)
        for _ in range(6):
            await asyncio.sleep(0)


def _correr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
            roteiro: Callable[[_Cena, Callable[..., Awaitable[dict[str, Any]]]], Awaitable[Any]],
            **cena: Any) -> Any:
    async def corrida() -> Any:
        mesa = _Cena(tmp_path, monkeypatch, **cena)
        caminho = Path(tempfile.mkdtemp(prefix="pd", dir="/tmp")) / "mods.sock"
        porta = Porta(caminho, EventBus(), escritor=mesa.escritor,
                      o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: UNIQS[0],
                      arbitro=lambda: mesa.fonte)
        await porta.iniciar()
        porta.registrar("ficha", "imersao", os.getpid(), ["escrever:gatilho", "escrever:luz"])
        cliente = _Cliente(caminho)
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})

            async def pedir(metodo: str, params: dict[str, Any]) -> dict[str, Any]:
                return await asyncio.to_thread(cliente.pedir, metodo, params)

            return await roteiro(mesa, pedir)
        finally:
            cliente.fechar()
            await porta.parar()

    return asyncio.run(corrida())


def _golpe(i: int, lado: str = "direito", **mais: Any) -> dict[str, Any]:
    return {"uniq": UNIQS[i], "lado": lado, "modo": "Feedback", "params": [3, 8], **mais}


def _dano(i: int, **mais: Any) -> dict[str, Any]:
    return {"uniq": UNIQS[i], "rgb": list(DANO), **mais}


@MESAS
def test_o_zero_devolve_o_gatilho_e_a_luz_do_perfil_so_dos_controles_tomados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    transportes: tuple[ConnectionType, ...],
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        for i in (0, 2):
            assert (await pedir("gatilho.set", _golpe(i, ate_ms=60000)))["result"]["status"] == "ok"
            await mesa.andar(1.0)
            assert (await pedir("luz.set", _dano(i, ate_ms=60000)))["result"]["status"] == "ok"
            await mesa.andar(1.0)
        for i in (0, 2):
            assert mesa.r2(i) == IMPACTO, f"o impacto não chegou ao controle {i}"
            assert mesa.cor(i) == DANO, f"o dano não chegou ao controle {i}"
        for i in (1, 3):
            assert mesa.r2(i) == mesa.perfil(i), "a extensão tocou num controle que não pediu"
            assert mesa.cor(i) == CORES[i]
        for i in (0, 2):
            await pedir("gatilho.set", {"uniq": UNIQS[i], "lado": "direito", "modo": "Off"})
            await pedir("luz.set", {"uniq": UNIQS[i], "rgb": [0, 0, 0]})
            await mesa.andar(1.0)
        for i in range(4):
            assert mesa.r2(i) == mesa.perfil(i), f"o zero deixou o R2 {i} fora do perfil"
            assert mesa.cor(i) == CORES[i], f"o zero deixou a barra do controle {i} no dano"
        assert mesa.backend._extensao_by_uniq == {}
        assert all(
            (o.trigger_right, o.led) == (PERFIS[i], CORES[i])
            for i, u in enumerate(PLANOS) for o in [mesa.backend._desired_by_uniq[u]]
        ), "a escrita da extensão entrou na camada de quem usa ou do perfil"
        assert {dono for donos in mesa.backend._desired_owner_by_uniq.values()
                for dono in donos.values()} == {"perfil"}

    _correr(tmp_path, monkeypatch, roteiro, transportes=transportes)


def test_o_prazo_vencido_devolve_e_o_pedido_sem_prazo_vive_o_que_a_fonte_da(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        await pedir("gatilho.set", _golpe(1, ate_ms=400))
        await pedir("luz.set", _dano(3, ate_ms=400))
        await mesa.andar(0.2)
        assert mesa.r2(1) == IMPACTO
        assert mesa.cor(3) == DANO
        await mesa.andar(0.3)
        assert mesa.r2(1) == mesa.perfil(1), "o prazo venceu e o gatilho ficou no impacto"
        assert mesa.cor(3) == CORES[3], "o prazo venceu e a barra ficou no dano"
        await pedir("luz.set", _dano(0))
        await mesa.andar(tv.VIDA_SEM_PRAZO_S - 0.5)
        assert mesa.cor(0) == DANO
        await mesa.andar(1.0)
        assert mesa.cor(0) == CORES[0], "o pedido sem prazo sobreviveu à vida que a fonte dá"

    _correr(tmp_path, monkeypatch, roteiro)


def test_o_lado_que_vence_antes_devolve_mesmo_com_o_outro_lado_vivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        await pedir("gatilho.set", _golpe(2, lado="esquerdo", ate_ms=300))
        await pedir("gatilho.set", _golpe(2, lado="direito", ate_ms=2000))
        await mesa.andar(0.1)
        assert (mesa.l2(2), mesa.r2(2)) == (IMPACTO, IMPACTO)
        await mesa.andar(0.4)
        assert mesa.l2(2) == OFF, "o L2 venceu e ficou no impacto porque o R2 seguia vivo"
        assert mesa.r2(2) == IMPACTO
        await mesa.andar(2.0)
        assert mesa.r2(2) == mesa.perfil(2)

    _correr(tmp_path, monkeypatch, roteiro)


def test_a_extensao_que_cai_devolve_o_que_tomou_de_cada_controle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        for i in range(4):
            await pedir("gatilho.set", _golpe(i, ate_ms=60000))
            await pedir("luz.set", _dano(i, ate_ms=60000))
            await mesa.andar(1.0)
        assert [mesa.r2(i) for i in range(4)] == [IMPACTO] * 4
        mesa.fonte.esquecer(EXT)
        await mesa.andar(0.1)
        for i in range(4):
            assert mesa.r2(i) == mesa.perfil(i), f"a extensão caiu e o R2 {i} ficou no impacto"
            assert mesa.cor(i) == CORES[i], f"a extensão caiu e a barra {i} ficou no dano"

    _correr(tmp_path, monkeypatch, roteiro)


@MESAS
def test_o_hotplug_nao_traz_o_valor_da_extensao_e_a_troca_de_transporte_atravessa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    transportes: tuple[ConnectionType, ...],
) -> None:
    """D-2111-A-CAMADA-DA-EXTENSAO-SOME-NA-SAIDA-E-ATRAVESSA-A-TROCA: o controle que sai de verdade
    leva o que a extensão tomou; a troca de transporte mantém e devolve uma vez."""
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        for i in range(4):
            await pedir("gatilho.set", _golpe(i, ate_ms=60000))
            await pedir("luz.set", _dano(i, ate_ms=60000))
            await mesa.andar(1.0)
        fios = mesa.backend._handles

        saiu = MACS[1]
        mesa.backend._close_handles(keep={m for m in MACS if m != saiu})
        assert PLANOS[1] not in mesa.backend._extensao_by_uniq, "a saída não levou a camada"
        fios[saiu] = _handle(mesa.transportes[1])
        mesa.backend._reapply_desired(saiu, fios[saiu])
        assert mesa.r2(1) == mesa.perfil(1), "o hotplug trouxe o impacto da extensão"
        assert mesa.cor(1) == CORES[1], "o hotplug trouxe a cor do dano"

        radio_para_cabo = MACS[2]
        assert mesa.backend.iniciar_troca_de_transporte(PLANOS[2], motivo="teste")
        mesa.backend._close_handles(keep={m for m in MACS if m != radio_para_cabo})
        assert PLANOS[2] in mesa.backend._extensao_by_uniq, "a troca de transporte virou saída"
        fios[radio_para_cabo] = _handle(CABO)
        fios[radio_para_cabo].connected = True
        mesa.backend._reapply_desired(radio_para_cabo, fios[radio_para_cabo])
        assert (mesa.r2(2), mesa.cor(2)) == (IMPACTO, DANO), "a troca perdeu o que a extensão tem"

        desfechos: list[str] = []
        soltar = mesa.backend.release_extension_output_for
        monkeypatch.setattr(
            mesa.backend, "release_extension_output_for",
            lambda uniq, campos: desfechos.append(soltar(uniq, campos)) or desfechos[-1])
        await pedir("gatilho.set", {"uniq": UNIQS[2], "lado": "direito", "modo": "Off"})
        await pedir("luz.set", {"uniq": UNIQS[2], "rgb": [0, 0, 0]})
        await mesa.andar(1.0)
        await mesa.andar(1.0)
        assert (mesa.r2(2), mesa.cor(2)) == (mesa.perfil(2), CORES[2])
        assert desfechos.count("escreveu") == 2, f"devolveu em dobro ou não devolveu: {desfechos}"
        assert (mesa.r2(0), mesa.cor(0)) == (IMPACTO, DANO), "a troca de outro tirou o do P1"
        assert (mesa.r2(3), mesa.cor(3)) == (IMPACTO, DANO), "a troca de outro tirou o do P4"

        for destino in (CABO, RADIO):
            assert mesa.backend.iniciar_troca_de_transporte(PLANOS[3], motivo="teste")
            mesa.backend._close_handles(keep={m for m in MACS if m != MACS[3]})
            fios[MACS[3]] = _handle(destino)
            mesa.backend._reapply_desired(MACS[3], fios[MACS[3]])
            assert (mesa.r2(3), mesa.cor(3)) == (IMPACTO, DANO), "ida e volta de fio perdeu o dano"
        assert PLANOS[3] in mesa.backend._extensao_by_uniq
        await pedir("gatilho.set", {"uniq": UNIQS[3], "lado": "direito", "modo": "Off"})
        await mesa.andar(1.0)
        assert mesa.r2(3) == mesa.perfil(3), "depois da volta ao rádio o impacto não foi devolvido"

    _correr(tmp_path, monkeypatch, roteiro, transportes=transportes)


ADAPTADORES = {PLANOS[0]: "hci0", PLANOS[1]: "hci0", PLANOS[2]: "hci1", PLANOS[3]: "hci2"}


def test_quatro_no_radio_em_tres_adaptadores_o_cabo_no_meio_e_a_volta_pelo_caminho_do_servico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro no rádio, dois no mesmo adaptador. O P3 passa ao cabo e o prazo vence com ele fora
    da mesa: o cabo chega com o perfil e nada se devolve de novo. O P4 vai ao cabo e volta ao
    rádio pela marca que o cabo que sai deixa, sem marca à mão: atravessa e devolve uma vez. O P1
    e o P2 seguem com o que a extensão pediu e voltam cada um ao seu quando a extensão cai."""
    from hefesto_dualsense4unix.integrations import radio_da_mesa

    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        monkeypatch.setattr(radio_da_mesa, "adaptador_por_uniq", lambda uniqs: {
            u: ADAPTADORES.get(str(u).replace(":", "").lower(), "hci0") for u in uniqs})
        backend, fios = mesa.backend, mesa.backend._handles
        with backend._io_lock:
            backend._aplicar_os_pisos_de_escrita_locked()
            backend._anotar_os_transportes_locked(list(fios.items()), {})

        def chegar(i: int, transporte: ConnectionType) -> None:
            fios[MACS[i]] = _handle(transporte)
            with backend._io_lock:
                backend._anotar_os_transportes_locked([(MACS[i], fios[MACS[i]])], {})
            backend._reapply_desired(MACS[i], fios[MACS[i]])

        def sair(i: int) -> None:
            backend._close_handles(keep={m for m in MACS if m != MACS[i]})

        for i in range(4):
            ate_ms = 3000 if i == 2 else 60000
            await pedir("gatilho.set", _golpe(i, ate_ms=ate_ms))
            await pedir("luz.set", _dano(i, ate_ms=ate_ms))
        await mesa.andar(0.5)
        assert [(mesa.r2(i), mesa.cor(i)) for i in range(4)] == [(IMPACTO, DANO)] * 4
        desfechos: dict[str, list[str]] = {}
        soltar = backend.release_extension_output_for

        def contar(uniq: str, campos: Any) -> str:
            desfecho = soltar(uniq, campos)
            desfechos.setdefault(uniq, []).append(desfecho)
            return desfecho

        monkeypatch.setattr(backend, "release_extension_output_for", contar)

        assert backend.iniciar_troca_de_transporte(PLANOS[2], motivo="o_cabo_chegou")
        sair(2)
        assert PLANOS[2] in backend._extensao_by_uniq, "a troca de transporte virou saída"
        await mesa.andar(3.0)
        assert desfechos.get(UNIQS[2]) == ["registrado", "registrado"], desfechos
        assert PLANOS[2] not in backend._extensao_by_uniq, "o prazo venceu fora da mesa e ficou"
        chegar(2, CABO)
        assert (mesa.r2(2), mesa.cor(2)) == (mesa.perfil(2), CORES[2]), (
            "o cabo trouxe o que venceu com o controle fora da mesa")

        assert backend.iniciar_troca_de_transporte(PLANOS[3], motivo="o_cabo_chegou")
        sair(3)
        chegar(3, CABO)
        assert (mesa.r2(3), mesa.cor(3)) == (IMPACTO, DANO), "o cabo perdeu o que a extensão tem"
        backend.cancelar_troca_de_transporte(PLANOS[3], motivo="a_folga_acabou")
        sair(3)
        assert PLANOS[3] in backend._extensao_by_uniq, "o cabo que sai para o rádio virou saída"
        chegar(3, RADIO)
        assert (mesa.r2(3), mesa.cor(3)) == (IMPACTO, DANO), "a volta ao rádio perdeu o dano"
        await pedir("gatilho.set", {"uniq": UNIQS[3], "lado": "direito", "modo": "Off"})
        await pedir("luz.set", {"uniq": UNIQS[3], "rgb": [0, 0, 0]})
        await mesa.andar(1.0)
        assert (mesa.r2(3), mesa.cor(3)) == (mesa.perfil(3), CORES[3])
        assert desfechos[UNIQS[3]].count("escreveu") == 2, f"devolveu em dobro: {desfechos}"

        assert [(mesa.r2(i), mesa.cor(i)) for i in (0, 1)] == [(IMPACTO, DANO)] * 2, (
            "a troca de outro mexeu no P1 ou no P2")
        mesa.fonte.esquecer(EXT)
        await mesa.andar(0.1)
        for i in range(4):
            assert (mesa.r2(i), mesa.cor(i)) == (mesa.perfil(i), CORES[i]), (
                f"o controle {i} não voltou ao seu")
        assert backend._extensao_by_uniq == {}
        assert desfechos[UNIQS[2]] == ["registrado", "registrado"], "o P3 devolveu de novo"
        assert desfechos[UNIQS[3]].count("escreveu") == 2, "a saída devolveu o P4 de novo"

    _correr(tmp_path, monkeypatch, roteiro, transportes=(RADIO,) * 4)


def test_o_gatilho_sem_efeito_no_perfil_volta_ao_off_e_soltar_duas_vezes_escreve_uma(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        mesa.backend.reset_profile_overrides({PLANOS[0]: OutputSpec(led=CORES[0])})
        await pedir("gatilho.set", _golpe(0, ate_ms=500))
        assert mesa.r2(0) == IMPACTO
        chamadas: list[str] = []
        original = mesa.backend._reset_trigger
        monkeypatch.setattr(
            type(mesa.backend), "_reset_trigger",
            staticmethod(lambda h, lado: (chamadas.append(lado), original(h, lado))[1]))
        await mesa.andar(0.6)
        await mesa.andar(0.6)
        assert mesa.r2(0) == OFF, "o perfil sem efeito não devolveu o gatilho ao Off"
        assert chamadas == ["right"], "o gatilho voltou ao Off mais de uma vez"
        await pedir("gatilho.set", {"uniq": UNIQS[0], "lado": "direito", "modo": "Off"})
        await mesa.andar(1.0)
        assert chamadas == ["right"], "soltar o que já foi solto escreveu de novo"

    _correr(tmp_path, monkeypatch, roteiro)


def test_o_ipc_sem_a_camada_continua_no_perfil_de_quem_usa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena, _pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        resposta = await mesa.servidor._handlers["led.set"]({"uniq": UNIQS[0], "rgb": [1, 2, 3]})
        assert resposta["status"] == "ok"
        assert mesa.backend._extensao_by_uniq == {}
        assert mesa.backend._desired_owner_by_uniq[PLANOS[0]]["led"] == "usuaria"

    _correr(tmp_path, monkeypatch, roteiro)


@MESAS
def test_os_quatro_juntos_cada_um_devolve_o_seu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    transportes: tuple[ConnectionType, ...],
) -> None:
    async def roteiro(mesa: _Cena, pedir: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        for i in (3, 1, 0, 2):
            await pedir("gatilho.set", _golpe(i, ate_ms=1000 + 200 * i))
            await mesa.andar(0.05)
        vistos = {i: mesa.r2(i) for i in range(4)}
        assert set(vistos.values()) == {IMPACTO}
        restantes = {0, 1, 2, 3}
        for _ in range(40):
            await mesa.andar(0.1)
            for i in sorted(restantes):
                if mesa.r2(i) == mesa.perfil(i):
                    restantes.discard(i)
                else:
                    assert mesa.r2(i) == IMPACTO
        assert restantes == set(), "um controle ficou no impacto depois do prazo"

    _correr(tmp_path, monkeypatch, roteiro, transportes=transportes)
