"""A luz do controle se escreve fora do fio do laço.

A-LUZ-DO-CONTROLE-SE-ESCREVE-FORA-DO-FIO-DO-LACO-01.

Quatro controles (P1 e P2 no cabo, P3 e P4 no rádio). O nó do sysfs e o `writeReport` de mentira
dormem 500 ms em cada escrita; o laço da luz pinta o quadro de cada controle a cada tique. O
backend é o do produto: só o handle e o nó são dublês, e os dois anotam o que receberam.
MORDIDA: a escrita de volta ao fio de quem pinta (o handle sem escritor) reprova pela frase
«a luz parou o laço».
"""

from __future__ import annotations

import contextlib
import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.lightbar_gatilho import COMMON_LIGHTBAR_B, COMMON_LIGHTBAR_R

MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
TRANSPORTES = ("usb", "usb", "bt", "bt")
POS_FLAG1 = 3 + 1
FLAG1_LIGHTBAR = 0x04
ATRASO_DA_ESCRITA_SEC = 0.5
TETO_DO_LACO_SEC = 0.020
TIQUES = 20
ESPERA_DA_FILA_SEC = 8.0


def _uniq(mac: str) -> str:
    return mac.replace(":", "").lower()


class _NoDeLed:
    """A classe LED do kernel de um controle: cada escrita dorme e guarda a cor."""

    def __init__(self, atraso: float, preso: threading.Event | None = None) -> None:
        self.atraso = atraso
        self.preso = preso
        self.cores: list[tuple[int, int, int]] = []
        self.numeros: list[tuple[bool, ...]] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        if self.preso is not None:
            self.preso.wait(30.0)
        time.sleep(self.atraso)
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str, atraso: float, *, com_escritor: bool = True) -> SimpleNamespace:
    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        conType=SimpleNamespace(name="BT_31" if transporte == "bt" else "USB_01"),
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None, _output_muted=False, escritos=escritos,
        _escritor_da_luz=bp._EscritorDaLuz("hefesto-luz-teste") if com_escritor else None,
    )

    def _escreve(report: Any) -> int:
        time.sleep(atraso)
        escritos.append(list(report))
        return len(report)

    handle.writeReport = _escreve
    return handle


def _mesa(
    atraso: float = ATRASO_DA_ESCRITA_SEC, *, com_escritor: bool = True
) -> tuple[bp.PyDualSenseController, list[SimpleNamespace], dict[str, _NoDeLed]]:
    ctl = bp.PyDualSenseController()
    handles = [_handle(t, atraso, com_escritor=com_escritor) for t in TRANSPORTES]
    ctl._handles = dict(zip(MACS, handles, strict=True))
    nos = {mac: _NoDeLed(atraso) for mac in MACS}
    ctl._sysfs = dict(nos)
    return ctl, handles, nos


def _cor(indice: int) -> tuple[int, int, int]:
    return (indice, 0, 0)


def _cor_do_0x31(report: list[int]) -> tuple[int, ...]:
    common = report[3:50]
    return tuple(common[COMMON_LIGHTBAR_R: COMMON_LIGHTBAR_B + 1])


def _cores_no_radio(handle: SimpleNamespace) -> list[tuple[int, ...]]:
    return [
        _cor_do_0x31(r) for r in handle.escritos if r[0] == 0x31 and r[POS_FLAG1] & FLAG1_LIGHTBAR
    ]


def _esperar_a_luz(handles: list[SimpleNamespace]) -> None:
    for handle in handles:
        escritor = handle._escritor_da_luz
        if escritor is not None:
            assert escritor.esperar(ESPERA_DA_FILA_SEC), "a fila da luz não esvaziou"


def _fechar(handles: list[SimpleNamespace]) -> None:
    for handle in handles:
        escritor = handle._escritor_da_luz
        if escritor is not None:
            escritor.fechar()


@pytest.fixture
def mesa() -> Iterator[tuple[bp.PyDualSenseController, list[SimpleNamespace], dict[str, _NoDeLed]]]:
    ctl, handles, nos = _mesa()
    yield ctl, handles, nos
    for no in nos.values():
        no.atraso = 0.0
    _fechar(handles)


def _pintar_o_laco(ctl: bp.PyDualSenseController, tiques: int) -> list[float]:
    """O que o laço faz a cada tique: o quadro de cada controle pela ponta do backend; devolve o
    custo de cada tique."""
    custos = []
    for tique in range(1, tiques + 1):
        inicio = time.monotonic()
        for mac in MACS:
            assert ctl.pintar_a_barra_sem_lembrar(_uniq(mac), _cor(tique)) is True
        custos.append(time.monotonic() - inicio)
        time.sleep(0.005)
    return custos


def _sequencia_crescente(cores: list[Any]) -> bool:
    indices = [c[0] for c in cores]
    return indices == sorted(indices)


def test_a_luz_nao_para_o_laco_e_cada_controle_termina_na_ultima_cor(mesa: Any) -> None:
    """D-2211-A-LUZ-SE-ESCREVE-FORA-DO-FIO-DO-LACO: o laço não espera a luz de controle nenhum."""
    ctl, handles, nos = mesa
    custos = _pintar_o_laco(ctl, TIQUES)
    assert max(custos) < TETO_DO_LACO_SEC, (
        f"a luz parou o laço: o pior tique levou {max(custos) * 1000:.0f} ms"
    )
    _esperar_a_luz(handles)
    for indice, mac in enumerate(MACS):
        assert nos[mac].cores[-1] == _cor(TIQUES), f"P{indice + 1}: não terminou na última cor"
        assert _sequencia_crescente(nos[mac].cores), f"P{indice + 1}: cor velha depois de nova"
        if TRANSPORTES[indice] == "bt":
            no_radio = _cores_no_radio(handles[indice])
            assert no_radio and no_radio[-1] == _cor(TIQUES)
            assert _sequencia_crescente(no_radio), f"P{indice + 1}: report velho depois de novo"
        assert len(nos[mac].cores) < TIQUES, "o mais novo vence: a fila juntou os quadros"


def test_o_reassert_vem_depois_do_ultimo_quadro_do_efeito(mesa: Any) -> None:
    """Dois tipos de pedido, a ordem é a da chegada: a cor resolvida fica por último."""
    ctl, handles, nos = mesa
    ctl._desired_default = bp._DesiredOutput(led=(200, 200, 200))
    _pintar_o_laco(ctl, 5)
    inicio = time.monotonic()
    ctl.reassert_resolved_outputs()
    assert time.monotonic() - inicio < TETO_DO_LACO_SEC * 4, "a luz parou o laço no reassert"
    _esperar_a_luz(handles)
    for mac in MACS:
        assert nos[mac].cores[-1] == (200, 200, 200), "o reassert saiu antes do último quadro"


def test_um_controle_sai_no_meio_de_uma_escrita_e_os_outros_seguem(
    mesa: Any,
) -> None:
    ctl, handles, nos = mesa
    segura = threading.Event()
    nos[MACS[0]].preso = segura
    ctl.pintar_a_barra_sem_lembrar(_uniq(MACS[0]), _cor(1))
    time.sleep(0.05)
    for no in nos.values():
        no.atraso = 0.0
    for tique in range(2, 8):
        for mac in MACS[1:]:
            ctl.pintar_a_barra_sem_lembrar(_uniq(mac), _cor(tique))
    _esperar_a_luz(handles[1:])
    for mac in MACS[1:]:
        assert nos[mac].cores[-1] == _cor(7), "um controle preso segurou os outros"
    handles[0]._escritor_da_luz.fechar()
    segura.set()
    ctl.pintar_a_barra_sem_lembrar(_uniq(MACS[0]), _cor(9))
    assert handles[0]._escritor_da_luz.ocioso() or handles[0]._escritor_da_luz.esperar(2.0)
    assert (9, 0, 0) not in nos[MACS[0]].cores, "o controle que saiu recebeu cor depois de sair"


def test_quem_usa_o_resultado_escreve_na_vez_e_depois_do_que_estava_na_fila(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O fio da luz ainda não pegou a fila (a janela entre o pedido e a trava): o gesto escoa a
    fila na ordem antes de escrever, e a cor velha não sai depois da nova."""
    monkeypatch.setattr(bp._EscritorDaLuz, "_girar", lambda self: None)
    ctl, handles, nos = _mesa(atraso=0.0)
    mac = MACS[0]
    ctl.pintar_a_barra_sem_lembrar(_uniq(mac), _cor(1))
    ctl.pintar_a_barra_sem_lembrar(_uniq(mac), _cor(2))
    assert nos[mac].cores == [], "o fio da luz de mentira não devia escrever"
    saiu = ctl._write_partial_output(
        handles[0], nos[mac], bp._DesiredOutput(led=_cor(3)), what="gesto", agora=True
    )
    assert saiu is True
    assert nos[mac].cores == [_cor(2), _cor(3)], "o gesto saiu antes do que estava na fila"
    _fechar(handles)


def test_a_cor_e_o_numero_pedidos_em_quadros_seguidos_saem_os_dois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A barra do efeito e, logo depois, as luzinhas do medidor no mesmo controle: os dois quadros
    se juntam campo a campo, e a cor que o segundo não traz não se perde."""
    monkeypatch.setattr(bp._EscritorDaLuz, "_girar", lambda self: None)
    ctl, handles, nos = _mesa(atraso=0.0)
    mac = MACS[0]
    numero = (False, False, True, False, False)
    ctl._write_partial_output(handles[0], nos[mac], bp._DesiredOutput(led=_cor(5)), what="barra")
    ctl._write_partial_output(
        handles[0], nos[mac], bp._DesiredOutput(player_leds=numero), what="luzinhas"
    )
    handles[0]._escritor_da_luz.agora(lambda: None)
    assert nos[mac].cores == [_cor(5)], "o quadro seguinte apagou a cor que ele não trazia"
    assert nos[mac].numeros == [numero]
    _fechar(handles)


def test_a_repintura_forcada_seguida_de_outra_nao_perde_o_forcar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No rádio, o quadro igual ao último não sai de novo, salvo `forcar`: a repintura forçada que
    se junta a uma comum ainda escreve."""
    monkeypatch.setattr(bp._EscritorDaLuz, "_girar", lambda self: None)
    ctl, handles, _nos = _mesa(atraso=0.0)
    radio = handles[2]
    desejo = bp._DesiredOutput(led=(200, 0, 0))
    radio._quadro_da_luz = ((200, 0, 0), None, None)
    for forcar in (True, False):
        ctl._repintar_a_luz_de_um(
            MACS[2], radio, None, desejo, pode_player=True, what="vigia", forcar=forcar
        )
    radio._escritor_da_luz.agora(lambda: None)
    assert _cores_no_radio(radio) == [(200, 0, 0)], "a repintura forçada se perdeu na fila"
    _fechar(handles)


def test_o_handle_sem_escritor_escreve_na_hora() -> None:
    """O dublê e a CLI seguem como sempre: a escrita volta quando o nó escreveu."""
    ctl, _handles, nos = _mesa(atraso=0.0, com_escritor=False)
    assert ctl.pintar_a_barra_sem_lembrar(_uniq(MACS[0]), _cor(4)) is True
    assert nos[MACS[0]].cores == [_cor(4)]


class _Mundo:
    """Um hidraw de mentira por `socketpair` num `/sys` de mentira, para o handle de produção."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.pontas: list[socket.socket] = []

    def abrir(self, controlador: bp.PyDualSenseController, numero: int) -> Any:
        pasta = self.raiz / f"hidraw{numero}" / "device"
        pasta.mkdir(parents=True)
        (pasta / "uevent").write_text(
            f"HID_ID=0005:0000054C:00000CE6\nHID_UNIQ=aa:bb:cc:00:00:{numero:02x}\n",
            encoding="utf-8",
        )
        dentro, fora = socket.socketpair()
        self.pontas += [dentro, fora]
        dispositivo = bp._DispositivoPorFd(os.dup(dentro.fileno()))
        return controlador._abrir_handle_pinado(
            f"/dev/hidraw{numero}".encode(), is_edge=False, dispositivo=dispositivo
        )

    def soltar(self) -> None:
        for ponta in self.pontas:
            with contextlib.suppress(OSError):
                ponta.close()


def test_o_handle_de_producao_nasce_com_o_escritor_e_o_fecha_ao_fechar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raiz = tmp_path / "hidraw"
    raiz.mkdir()
    monkeypatch.setattr(bp, "RAIZ_CLASS_HIDRAW", str(raiz))
    leitor = EvdevReader(device_path=None)
    leitor._device_path = None
    controlador = bp.PyDualSenseController(evdev_reader=leitor)
    mundo = _Mundo(raiz)
    try:
        handle = mundo.abrir(controlador, 3)
        assert handle is not None
        escritor = handle._escritor_da_luz
        assert isinstance(escritor, bp._EscritorDaLuz)
        node = _NoDeLed(0.0)
        saiu = controlador._write_partial_output(
            handle, node, bp._DesiredOutput(led=(7, 8, 9)), what="produção"
        )
        assert saiu is True and escritor.esperar(3.0)
        assert node.cores == [(7, 8, 9)]
        nome = escritor._fio.name if escritor._fio is not None else ""
        assert nome.startswith("hefesto-luz-hidraw3"), nome
        handle.close()
        limite = time.monotonic() + 3.0
        while escritor._fio is not None and escritor._fio.is_alive() and time.monotonic() < limite:
            time.sleep(0.01)
        assert escritor._fio is not None and not escritor._fio.is_alive(), (
            "o fio da luz ficou vivo depois de o handle fechar"
        )
    finally:
        mundo.soltar()
