"""O estado do serviço lê `/sys` e o HCI fora do laço e o guarda: N clientes, uma leitura.

O-ESTADO-DO-SERVICO-SE-LE-SEM-PARAR-O-LACO-01: o `daemon.state_full` montava no fio do laço o nó
do pad virtual, os controles sem driver, o endereço do adaptador, o orçamento de ar e a cor da
barra; cada cliente refazia a leitura inteira. Aqui as leituras de `/sys` e do HCI dormem 200 ms,
quatro controles no rádio e quatro pads virtuais, dois clientes pedindo o estado a 2 Hz pelo
socket de verdade.

Decisão proposta (22/11/2026, a validar):
D-2211-O-ESTADO-RESPONDE-DO-GUARDADO-E-A-LEITURA-CORRE-FORA-DO-LACO.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.integrations import radio_da_mesa
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

DORME_S = 0.2
TETO_DO_VAO_S = 0.020
JANELA_S = 2.5
PERIODO_S = 0.5
_OS_QUATRO = tuple(f"aabbcc00000{n}" for n in range(1, 5))
_ADAPTADOR = "aa:bb:cc:00:00:fa"
_NO = {"evdev": "/dev/input/event99", "hidraw": "/dev/hidraw9", "ino": 1, "hidraw_ino": 2}


class _Porta:
    """Uma leitura de `/sys` ou do HCI de mentira: dorme, conta e anota o fio."""

    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.chamadas = 0
        self.fios: list[str] = []
        self._trava = threading.Lock()

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        with self._trava:
            self.chamadas += 1
            self.fios.append(threading.current_thread().name)
        time.sleep(DORME_S)
        return self.resposta


class _NoLed:
    def __init__(self, n: int, porta: _Porta) -> None:
        self.indicator_dir = f"/sys/class/leds/fake{n}"
        self._porta = porta

    def get_rgb(self) -> tuple[int, int, int]:
        return self._porta((self.indicator_dir, "rgb"))

    def is_on(self) -> bool:
        return True


_SO_RADIO = ("bt",) * 4
_MESA_MISTA = ("bt", "usb", "bt", "usb")


class _AMesa(FakeController):
    def __init__(self, barra: _Porta, transportes: tuple[str, ...] = _SO_RADIO) -> None:
        super().__init__(transport="bt")  # type: ignore[arg-type]
        self._transportes = transportes
        self._sysfs = {u: _NoLed(i, barra) for i, u in enumerate(_OS_QUATRO)}
        self._sysfs_written = {u: (10, 20, 30) for u in _OS_QUATRO}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {"index": i, "uniq": u, "transport": self._transportes[i], "connected": True}
            for i, u in enumerate(_OS_QUATRO)
        ]


class _Coop:
    def __init__(self) -> None:
        self._players = {
            u: SimpleNamespace(
                vpad=SimpleNamespace(
                    mac=u, name=f"Hefesto P{i + 1}", player=i + 1, backend="uhid"
                ),
                player_index=i + 1,
            )
            for i, u in enumerate(_OS_QUATRO)
        }

    def player_count(self) -> int:
        return len(self._players)

    def mesa(self) -> list[dict[str, Any]]:
        return []

    def player_indexes(self) -> dict[str, int]:
        return {u: i + 1 for i, u in enumerate(_OS_QUATRO)}


@pytest.fixture
def portas(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    p = SimpleNamespace(
        sem_driver=_Porta(["0005:054C:0CE6.000F"]),
        no=_Porta(dict(_NO)),
        no_vale=_Porta(True),
        barra=_Porta((10, 20, 30)),
        adaptador=_Porta({}),
        porta=_Porta(False),
    )
    p.adaptador.resposta = {u: _ADAPTADOR for u in _OS_QUATRO[:3]}
    monkeypatch.setattr(ih, "dualsense_sem_driver", p.sem_driver)
    monkeypatch.setattr(ih, "resolver_no_do_vpad", p.no)
    monkeypatch.setattr(ih, "no_ainda_vale", p.no_vale)

    def _adaptador_por_uniq(uniqs: Any, **_k: Any) -> dict[str, str]:
        return p.adaptador(uniqs) if list(uniqs) else {}

    monkeypatch.setattr(radio_da_mesa, "adaptador_por_uniq", _adaptador_por_uniq)
    monkeypatch.setattr(radio_da_mesa, "atras_de_hub_no_sysfs", p.porta)
    monkeypatch.setattr(radio_da_mesa, "_PORTA_LIDA", {})
    monkeypatch.setattr(radio_da_mesa, "VALIDADE_DA_PORTA_S", 0.3)
    return p


def _o_servico(
    tmp_path: Path, portas: SimpleNamespace, transportes: tuple[str, ...] = _SO_RADIO
) -> IpcServer:
    controle = _AMesa(portas.barra, transportes)
    daemon = Daemon(
        controller=controle,
        config=DaemonConfig(
            poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
            coop_enabled=True, gamepad_emulation_enabled=True,
        ),
    )
    daemon._coop_manager = _Coop()
    daemon._gamepad_device = SimpleNamespace(
        mac=_OS_QUATRO[0], name="Hefesto P1", player=1, backend="uhid"
    )
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "e.sock", daemon=daemon,
    )
    daemon._ipc_server = servidor
    return servidor


async def _pedir(
    leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter, n: int
) -> dict[str, Any]:
    pedido = {"jsonrpc": "2.0", "id": n, "method": "daemon.state_full", "params": {}}
    escritor.write(json.dumps(pedido).encode() + b"\n")
    await escritor.drain()
    resposta = json.loads(await leitor.readline())
    resultado: dict[str, Any] = resposta["result"]
    return resultado


async def _um_cliente(caminho: Path, respostas: list[dict[str, Any]]) -> None:
    leitor, escritor = await asyncio.open_unix_connection(str(caminho))
    try:
        fim = time.monotonic() + JANELA_S
        n = 0
        while time.monotonic() < fim:
            n += 1
            respostas.append(await _pedir(leitor, escritor, n))
            await asyncio.sleep(PERIODO_S)
    finally:
        escritor.close()


async def _medir_o_laco(servidor: IpcServer) -> tuple[float, list[dict[str, Any]]]:
    laco = asyncio.get_running_loop()
    maior = [0.0]

    async def _batimento() -> None:
        anterior = laco.time()
        while True:
            await asyncio.sleep(0.005)
            agora = laco.time()
            maior[0] = max(maior[0], agora - anterior - 0.005)
            anterior = agora

    await servidor.start()
    leitor, escritor = await asyncio.open_unix_connection(str(servidor.socket_path))
    await _pedir(leitor, escritor, 0)
    escritor.close()
    await asyncio.sleep(DORME_S * 2)
    batimento = asyncio.create_task(_batimento())
    respostas: list[dict[str, Any]] = []
    try:
        await asyncio.gather(
            _um_cliente(servidor.socket_path, respostas),
            _um_cliente(servidor.socket_path, respostas),
        )
    finally:
        batimento.cancel()
        await servidor.stop()
    return maior[0], respostas


async def test_dois_clientes_a_2_hz_nao_param_o_laco_nem_multiplicam_a_leitura(
    tmp_path: Path, portas: SimpleNamespace
) -> None:
    """D-2211-O-ESTADO-RESPONDE-DO-GUARDADO-E-A-LEITURA-CORRE-FORA-DO-LACO."""
    for tentativa in range(3):
        for porta in vars(portas).values():
            porta.chamadas, porta.fios = 0, []
        radio_da_mesa._PORTA_LIDA.clear()
        pasta = tmp_path / str(tentativa)
        pasta.mkdir()
        maior_vao, respostas = await _medir_o_laco(_o_servico(pasta, portas))
        if maior_vao < TETO_DO_VAO_S:
            break

    assert maior_vao < TETO_DO_VAO_S, f"o laço parou {maior_vao * 1000:.0f} ms"
    assert len(respostas) >= 8
    principal = threading.main_thread().name
    for nome in ("sem_driver", "no", "barra", "adaptador"):
        porta: _Porta = getattr(portas, nome)
        assert porta.chamadas, f"a porta {nome} não foi lida"
        assert principal not in porta.fios, f"{nome} leu no fio do laço"
        por_prazo = JANELA_S / PERIODO_S + 2
        teto = por_prazo * (4 if nome in ("barra", "no") else 2 if nome == "adaptador" else 1)
        assert porta.chamadas <= teto, (
            f"{nome}: {porta.chamadas} leituras para {len(respostas)} perguntas"
        )


async def test_o_estado_guardado_traz_o_que_a_leitura_achou(
    tmp_path: Path, portas: SimpleNamespace
) -> None:
    servidor = _o_servico(tmp_path, portas)

    _, respostas = await _medir_o_laco(servidor)

    estado = respostas[-1]
    assert estado["controles_sem_driver"] == {"quantidade": 1, "ids": ["0005:054C:0CE6.000F"]}
    assert [c["adaptador"] for c in estado["controllers"]] == [_ADAPTADOR] * 3 + [None]
    assert {c["lightbar_source"] for c in estado["controllers"]} == {"sysfs"}
    assert {c["lightbar_rgb"] and tuple(c["lightbar_rgb"]) for c in estado["controllers"]} == {
        (10, 20, 30)
    }
    assert estado["radio_ar"][_ADAPTADOR]["controles"]
    vpads = estado["rumble_ff"]["per_vpad"]
    assert len(vpads) == 5
    assert {v["evdev"] for v in vpads} == {_NO["evdev"]}


@pytest.mark.parametrize("transportes", [_SO_RADIO, _MESA_MISTA], ids=["radio", "mista"])
async def test_a_primeira_pergunta_ja_traz_o_lido_e_as_seguintes_sao_uma_leitura_por_porta(
    tmp_path: Path, portas: SimpleNamespace, transportes: tuple[str, ...]
) -> None:
    servidor = _o_servico(tmp_path, portas, transportes)
    marca = ih.le_so_do_guardado.set(True)
    try:
        primeiro = await servidor._handle_daemon_state_full({})
        for _ in range(7):
            await servidor._handle_daemon_state_full({})
            await asyncio.sleep(0.05)
        await asyncio.sleep(DORME_S + 0.1)
    finally:
        ih.le_so_do_guardado.reset(marca)

    assert primeiro["controles_sem_driver"]["quantidade"] == 1
    assert [c["adaptador"] for c in primeiro["controllers"]] == [
        _ADAPTADOR if t == "bt" and u in portas.adaptador.resposta else None
        for u, t in zip(_OS_QUATRO, transportes, strict=True)
    ]
    assert {c["lightbar_source"] for c in primeiro["controllers"]} == {"sysfs"}
    assert primeiro["radio_ar"][_ADAPTADOR]["controles"]
    assert {v["evdev"] for v in primeiro["rumble_ff"]["per_vpad"]} == {_NO["evdev"]}

    assert {
        "sem_driver": portas.sem_driver.chamadas,
        "barra": portas.barra.chamadas,
        "no": portas.no.chamadas,
    } == {"sem_driver": 1, "barra": 4, "no": 4}
    assert portas.adaptador.chamadas <= 4


async def test_sem_a_marca_do_guardado_o_handler_le_na_hora(
    tmp_path: Path, portas: SimpleNamespace
) -> None:
    """Chamado direto (a CLI, as réguas), o handler segue lendo de verdade e sem atraso."""
    servidor = _o_servico(tmp_path, portas)
    for porta in (portas.sem_driver, portas.adaptador, portas.barra, portas.no):
        with contextlib.suppress(AttributeError):
            porta.resposta = porta.resposta

    estado = await servidor._handle_daemon_state_full({})

    assert estado["controles_sem_driver"]["quantidade"] == 1
    assert [c["adaptador"] for c in estado["controllers"]] == [_ADAPTADOR] * 3 + [None]
