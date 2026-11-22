"""O laço do daemon não espera a trava de escrita nas bordas do microfone nem no supervisor
(O-LACO-NAO-ESPERA-A-TRAVA-DE-ESCRITA-NAS-BORDAS-DO-MICROFONE-01).

Medido em 21/11/2026 no diário (`laco_lento`, `onde` pela amostra do vigia): `bordas_do_mic`
242 ms e `_mudar_por_dentro` 360 ms. O `bordas_do_mic` toma o `_io_lock` (e o mapa da posse,
que o toma de novo) e era chamado direto no fio do laço, por `mic_da_mesa_loop`: qualquer fio
que segure a trava segura o laço. O supervisor já manda cada leitura a `asyncio.to_thread`; a
régua dele só prende isso.

Cada régua segura a trava (ou faz o trabalho lento) noutro fio por `SEGURA_S` e mede, com um
batimento de 10 ms no mesmo laço, a maior parada: tem de ficar abaixo de `TETO_S`. Quatro
controles, dois no cabo e dois no rádio, em faixa forjada; nenhum nó é de verdade.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import mic_da_mesa
from hefesto_dualsense4unix.mods import supervisor as sup

SEGURA_S = 0.6
TETO_S = 0.15

CABO_1 = "AA:BB:CC:00:00:01"
CABO_2 = "AA:BB:CC:00:00:02"
RADIO_1 = "AA:BB:CC:00:00:03"
RADIO_2 = "AA:BB:CC:00:00:04"
OS_QUATRO = (CABO_1, CABO_2, RADIO_1, RADIO_2)


class _Batimento:
    """Um batimento de 10 ms no laço; a maior distância entre dois batimentos é a parada."""

    def __init__(self) -> None:
        self.maior = 0.0
        self._parar = asyncio.Event()
        self._tarefa: asyncio.Task[None] | None = None

    async def _bater(self) -> None:
        ultimo = time.perf_counter()
        while not self._parar.is_set():
            await asyncio.sleep(0.01)
            agora = time.perf_counter()
            self.maior = max(self.maior, agora - ultimo)
            ultimo = agora

    def __enter__(self) -> _Batimento:
        self._tarefa = asyncio.get_running_loop().create_task(self._bater())
        return self

    async def parar(self) -> None:
        self._parar.set()
        assert self._tarefa is not None
        await self._tarefa

    def __exit__(self, *_exc: object) -> None:
        self._parar.set()


class _Dono:
    """Segura a trava noutro fio até `soltar` (ou `SEGURA_S`)."""

    def __init__(self, trava: Any) -> None:
        self._trava = trava
        self._pegou = threading.Event()
        self._solta = threading.Event()
        self._fio = threading.Thread(target=self._segurar, daemon=True)

    def _segurar(self) -> None:
        with self._trava:
            self._pegou.set()
            self._solta.wait(SEGURA_S)

    def __enter__(self) -> _Dono:
        self._fio.start()
        assert self._pegou.wait(2.0), "o dono não pegou a trava"
        return self

    def __exit__(self, *_exc: object) -> None:
        self._solta.set()
        self._fio.join(SEGURA_S + 1.0)


class _Handle:
    """O mínimo de um handle com o contador do botão do microfone."""

    def __init__(self, *, radio: bool) -> None:
        self.conType = SimpleNamespace(name="BT" if radio else "USB")
        self._mic_mudo_seq = 0
        self._mic_mudo = False
        self._mic_mudo_pedido: bool | None = None
        self._mic_mudo_em: float | None = None
        self._mic_mudo_em_voo = False
        self._mic_posse_solta_pela_mao = False
        self._mic_mute_desejado: bool | None = None

    def apertar(self) -> None:
        self._mic_mudo_seq += 1
        self._mic_mudo = not self._mic_mudo
        self._mic_mudo_em = time.monotonic()


def _uniq(key: str) -> str:
    uniq = PyDualSenseController._key_to_uniq(key)
    assert uniq is not None
    return str(uniq)


def _backend() -> tuple[PyDualSenseController, dict[str, _Handle]]:
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    handles = {
        key: _Handle(radio=key in (RADIO_1, RADIO_2)) for key in OS_QUATRO
    }
    inst._handles = dict(handles)
    inst._primary_key = CABO_1
    return inst, handles


class _Barramento:
    def __init__(self) -> None:
        self.publicados: list[dict[str, Any]] = []

    def publish(self, _topico: str, carga: dict[str, Any]) -> None:
        self.publicados.append(carga)


class _DaemonFalso:
    def __init__(self, controle: Any) -> None:
        self.controller = controle
        self.bus = _Barramento()
        self.parar = False
        self._tasks: list[Any] = []

    def _is_stopping(self) -> bool:
        return self.parar


@pytest.fixture(autouse=True)
def _sem_carencia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "INPUT_GRACE_SEC", 0.0)


async def _o_laco_das_bordas_com_a_trava_presa(
    inst: PyDualSenseController, handles: dict[str, _Handle]
) -> tuple[float, _DaemonFalso]:
    daemon = _DaemonFalso(inst)
    laco = asyncio.get_running_loop().create_task(mic_da_mesa.mic_da_mesa_loop(daemon))
    await asyncio.sleep(0.3)
    with _Batimento() as batimento:
        with _Dono(inst._io_lock):
            for handle in handles.values():
                handle.apertar()
            await asyncio.sleep(SEGURA_S + 0.1)
        for _ in range(100):
            if len(daemon.bus.publicados) >= len(handles):
                break
            await asyncio.sleep(0.05)
        await batimento.parar()
    daemon.parar = True
    await asyncio.wait_for(laco, 5.0)
    return batimento.maior, daemon


def test_o_laco_das_bordas_nao_espera_a_trava_e_as_quatro_bordas_saem_certas() -> None:
    """**A MORDIDA.** Outro fio segura o `_io_lock`; o laço não passa de `TETO_S` parado, e quando
    a trava solta as bordas dos quatro controles saem, cada uma com o endereço e o contador
    próprios.

    MORDIDA: o `_bordas(backend)` de volta ao fio do laço reprova aqui pela frase do `laco_lento`.
    """
    inst, handles = _backend()

    maior, daemon = asyncio.run(_o_laco_das_bordas_com_a_trava_presa(inst, handles))

    assert maior < TETO_S, (
        f"laco_lento: o laço parou {maior * 1000:.0f} ms em `bordas_do_mic` com a trava presa"
    )
    por_endereco = {carga["uniq"]: carga for carga in daemon.bus.publicados}
    assert set(por_endereco) == {_uniq(key) for key in OS_QUATRO}, por_endereco
    for key in OS_QUATRO:
        carga = por_endereco[_uniq(key)]
        assert carga["seq"] == 1 and carga["mudo"] is True, (key, carga)


def test_a_posse_que_a_mao_soltou_chega_ao_mapa_dos_quatro_depois_que_a_trava_solta() -> None:
    inst, handles = _backend()
    for key, handle in handles.items():
        inst._mic_mute_by_uniq[_uniq(key)] = True
        handle._mic_posse_solta_pela_mao = True

    maior, _ = asyncio.run(_o_laco_das_bordas_com_a_trava_presa(inst, handles))

    assert maior < TETO_S, f"laco_lento: o laço parou {maior * 1000:.0f} ms"
    assert inst._mic_mute_by_uniq == {}, (
        f"a posse solta pela mão não chegou ao mapa de todos: {inst._mic_mute_by_uniq}"
    )


def test_o_controle_que_sai_some_das_bordas_e_volta_sem_disparar() -> None:
    """Um sai e volta no meio: o contador novo é a primeira varredura dele (a carência), e os
    outros três seguem."""
    inst, handles = _backend()

    async def _roda() -> list[dict[str, Any]]:
        daemon = _DaemonFalso(inst)
        laco = asyncio.get_running_loop().create_task(mic_da_mesa.mic_da_mesa_loop(daemon))
        await asyncio.sleep(0.2)
        saiu = inst._handles.pop(RADIO_2)
        await asyncio.sleep(0.2)
        saiu.apertar()
        inst._handles[RADIO_2] = saiu
        await asyncio.sleep(0.2)
        handles[CABO_1].apertar()
        await asyncio.sleep(0.3)
        daemon.parar = True
        await asyncio.wait_for(laco, 5.0)
        return daemon.bus.publicados

    publicados = asyncio.run(_roda())

    assert [carga["uniq"] for carga in publicados] == [_uniq(CABO_1)], publicados


def test_o_supervisor_nao_segura_o_laco_com_a_leitura_e_a_caixa_lentas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada leitura de `_mudar_por_dentro` (irmãos, HID, extensão na caixa, escape) e a caixa
    de mentira levam `SEGURA_S`/2 cada; o laço não passa de `TETO_S` parado.

    MORDIDA: qualquer das leituras de volta ao fio do laço reprova aqui.
    """
    espera = SEGURA_S / 2

    def _irmaos(_retrato: Any) -> tuple[dict[str, int], list[str]]:
        time.sleep(espera)
        return {"/sys/devices/hub/1-1": 7}, []

    def _hid(_manifesto: Any, _aceitos: Any) -> dict[str, str]:
        time.sleep(espera)
        return {"hidraw-falso": "/sys/devices/hid"}

    def _dentro(_pid: int) -> int:
        time.sleep(espera)
        return 42

    def _escape(_pid: int, _dentro: int) -> bool:
        time.sleep(espera)
        return False

    async def _caixa(_pid: int, pedido: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(espera)
        return {"cobertos": pedido["cobrir"], "falhas": []}

    monkeypatch.setattr(sup, "irmaos_a_vista", _irmaos)
    monkeypatch.setattr(sup, "hid_da_caixa", _hid)
    monkeypatch.setattr(sup, "a_extensao_na_caixa", _dentro)
    monkeypatch.setattr(sup, "a_caixa_escapa", _escape)
    monkeypatch.setattr(sup, "mudar_por_dentro_da_caixa", _caixa)
    vigiada = sup._Vigiada(
        "extensao-falsa",
        manifesto=SimpleNamespace(),
        processo=SimpleNamespace(pid=1),
        retrato={"/sys/devices/hub/1-1": 1},
    )

    async def _roda() -> tuple[str | None, float]:
        with _Batimento() as batimento:
            await asyncio.sleep(0.05)
            motivo = await sup.Supervisor._mudar_por_dentro(
                SimpleNamespace(), "extensao-falsa", vigiada
            )
            await batimento.parar()
        return motivo, batimento.maior

    motivo, maior = asyncio.run(_roda())

    assert motivo is None
    assert maior < TETO_S, (
        f"laco_lento: o laço parou {maior * 1000:.0f} ms em `_mudar_por_dentro`"
    )
    assert vigiada.hid == {"hidraw-falso": "/sys/devices/hid"}


def test_abrir_o_processo_da_caixa_nao_segura_o_laco(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O `create_subprocess_exec` de `mudar_por_dentro_da_caixa` roda no fio do laço: a abertura
    do processo (de verdade, com um `python` que dorme `SEGURA_S`) fica abaixo de `TETO_S`."""
    ajudante = tmp_path / "por_dentro_falso.py"
    corpo = "import sys, time\nsys.stdin.read()\ntime.sleep({})\nprint('{{\"cobertos\": []}}')\n"
    ajudante.write_text(corpo.format(SEGURA_S), encoding="utf-8")
    monkeypatch.setattr(sup, "POR_DENTRO_DA_CAIXA", ajudante)
    assert sys.executable

    async def _roda() -> tuple[dict[str, Any] | None, float]:
        with _Batimento() as batimento:
            await asyncio.sleep(0.05)
            resposta = await sup.mudar_por_dentro_da_caixa(1, {"cobrir": []})
            await batimento.parar()
        return resposta, batimento.maior

    resposta, maior = asyncio.run(_roda())

    assert resposta == {"cobertos": []}
    assert maior < TETO_S, f"laco_lento: abrir o processo parou o laço {maior * 1000:.0f} ms"
