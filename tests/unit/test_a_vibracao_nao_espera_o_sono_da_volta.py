"""A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01 (13/10/2026).

Antes, toda passada da volta terminava em `time.sleep(_throttle_sec)`, e o
`_throttle_sec` era `min(0,008 x n, 0,032)` com `n` = TODOS os controles abertos,
no cabo e no rádio. A vibração que o jogo pedia esperava a volta acabar: até
32 ms com quatro controles, mesmo com todos no cabo, onde cada um tem o endpoint
dele e a disputa de CRC não existe.

Agora a volta espera um evento que a réplica arma ao mudar, com o prazo antigo
como teto (leitura e keepalive seguem no ritmo de sempre), e o espaçamento entre
duas escritas é um PISO por transporte: o cabo tem o próprio, pequeno e igual
para um ou quatro controles; o rádio, `0,008 x n` contado só entre controles do
MESMO adaptador, que é onde a disputa de CRC acontece.

Tudo aqui roda sem hidraw: o relógio, o sono e o evento são de mentira, e a
latência que se mede é a do relógio simulado (determinística), não a da máquina.
"""
from __future__ import annotations

import itertools
import os
import subprocess
import sys
import threading
import time
import types
from collections.abc import Callable
from typing import Any

import hidapi
import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.integrations import radio_da_mesa

UNIQS = ["02fe00000001", "02fe00000002", "02fe00000003", "02fe00000004"]


class _Relogio:
    """O tempo da bancada: o sono e a espera o fazem andar; as ações agendadas disparam nele."""

    def __init__(self) -> None:
        self.t = 100.0
        self.agenda: list[tuple[float, Callable[[], None]]] = []

    def monotonic(self) -> float:
        return self.t

    def agendar(self, quando: float, acao: Callable[[], None]) -> None:
        self.agenda.append((quando, acao))
        self.agenda.sort(key=lambda par: par[0])

    def avancar(self, ate: float, *, parar_se: Callable[[], bool] | None = None) -> None:
        while self.agenda and self.agenda[0][0] <= ate:
            quando, acao = self.agenda.pop(0)
            self.t = max(self.t, quando)
            acao()
            if parar_se is not None and parar_se():
                return
        self.t = max(self.t, ate)

    def sleep(self, segundos: float) -> None:
        self.avancar(self.t + max(segundos, 1e-6))


class _Evento:
    """Um `threading.Event` no relógio de mentira: `wait` anda o relógio; arma-o uma ação."""

    def __init__(self, relogio: _Relogio) -> None:
        self._relogio = relogio
        self._armado = False
        self.esperas: list[float] = []

    def set(self) -> None:
        self._armado = True

    def clear(self) -> None:
        self._armado = False

    def is_set(self) -> bool:
        return self._armado

    def wait(self, timeout: float | None = None) -> bool:
        assert timeout is not None
        self.esperas.append(timeout)
        if not self._armado:
            self._relogio.avancar(self._relogio.t + timeout, parar_se=lambda: self._armado)
        return self._armado


class _HidDevice:
    def __init__(self) -> None:
        self.bloqueante = True


class _DevComFila:
    """Todo `read` tem report: a entrada não é o assunto aqui."""

    def __init__(self) -> None:
        self._device = _HidDevice()

    def read(self, n: int) -> bytes:
        return bytes(n)


@pytest.fixture(autouse=True)
def _o_c_do_hidapi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hidapi, "hidapi", types.SimpleNamespace(hid_set_nonblocking=lambda dev, modo: 0)
    )


class _Bancada:
    """O laço de verdade num handle, com relógio e evento de mentira e a lista das escritas."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, throttle: float, piso: float
    ) -> None:
        self.relogio = _Relogio()
        self.escritas: list[tuple[float, int]] = []
        inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
        inst.input_report_length = 64
        inst.connected = True
        inst._rumble_active = False
        inst._rumble_stop_pending = False
        inst.leftMotor = 0
        inst.rightMotor = 0
        inst._acordar = _Evento(self.relogio)
        inst._throttle_sec = throttle
        inst._piso_de_escrita_sec = piso
        inst._last_out_report = None
        inst._last_write_at = 0.0
        inst._last_change_at = float("-inf")
        inst._output_muted = False
        inst.ds_thread = True
        inst.device = _DevComFila()
        monkeypatch.setattr(inst, "readInput", lambda _r: None)
        monkeypatch.setattr(inst, "prepareReport", lambda: [inst.leftMotor] + [0] * 63)
        monkeypatch.setattr(inst, "writeReport", self._escrever)
        monkeypatch.setattr(time, "monotonic", self.relogio.monotonic)
        monkeypatch.setattr(time, "sleep", self.relogio.sleep)
        self.inst = inst

    def _escrever(self, out: Any, **_geracao: Any) -> None:
        self.escritas.append((self.relogio.t, int(out[0])))

    def mexer_o_motor_em(self, quando: float, valor: int) -> None:
        self.relogio.agendar(100.0 + quando, lambda: self.inst.setLeftMotor(valor))

    def rodar_ate(self, quando: float) -> None:
        def parar() -> None:
            self.inst.ds_thread = False

        self.relogio.agendar(100.0 + quando, parar)
        self.inst.sendReport()

    def a_escrita_do_valor(self, valor: int) -> float:
        quando = [t for t, v in self.escritas if v == valor]
        assert quando, f"o valor {valor} nunca saiu: {self.escritas}"
        return quando[0] - 100.0


def test_a_vibracao_no_cabo_sai_na_hora_com_quatro_controles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro no cabo: o sono antigo era 32 ms; a escrita nova sai em até 2 ms."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=bp.PISO_DE_ESCRITA_DO_CABO_SEC)
    banca.mexer_o_motor_em(1.010, 200)

    banca.rodar_ate(1.5)

    latencia = banca.a_escrita_do_valor(200) - 1.010
    assert latencia <= 0.002, f"a escrita esperou {latencia * 1000:.1f} ms"


def test_a_volta_nao_dorme_o_sono_inteiro_quando_a_saida_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A espera é o prazo da volta COMO TETO; uma mudança a interrompe."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=bp.PISO_DE_ESCRITA_DO_CABO_SEC)
    banca.mexer_o_motor_em(1.003, 200)

    banca.rodar_ate(1.2)

    esperas = banca.inst._acordar.esperas
    assert esperas, "a volta não esperou pelo evento"
    assert set(esperas) == {0.032}, "o teto da espera é o prazo da volta, nada além"


def test_sem_mudanca_o_keepalive_segue_no_ritmo_de_sempre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ocioso, a volta continua escrevendo o report igual a cada `OUT_REPORT_KEEPALIVE_SEC`."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=bp.PISO_DE_ESCRITA_DO_CABO_SEC)

    banca.rodar_ate(1.9)

    instantes = [t - 100.0 for t, _ in banca.escritas]
    assert len(instantes) >= 3, instantes
    intervalos = [b - a for a, b in itertools.pairwise(instantes)]
    assert all(
        bp.OUT_REPORT_KEEPALIVE_SEC <= i <= bp.OUT_REPORT_KEEPALIVE_SEC + 0.05
        for i in intervalos
    ), intervalos


def test_no_radio_o_intervalo_entre_escritas_continua_o_de_hoje(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro no rádio num adaptador: duas mudanças coladas saem separadas por >= 32 ms."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=0.032)
    banca.mexer_o_motor_em(1.010, 200)
    banca.mexer_o_motor_em(1.011, 201)
    banca.mexer_o_motor_em(1.012, 202)

    banca.rodar_ate(1.4)

    janela = [t for t, v in banca.escritas if v in (200, 201, 202)]
    assert len(janela) >= 2, banca.escritas
    for a, b in itertools.pairwise(janela):
        assert b - a >= 0.032 - 1e-9, f"escritas a {(b - a) * 1000:.1f} ms uma da outra"
    assert [v for _, v in banca.escritas if v >= 200][-1] == 202


def test_a_mudanca_dentro_do_piso_do_cabo_e_adiada_e_nao_perdida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duas mudanças com 1 ms de distância no cabo: a segunda sai quando o piso passa."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=bp.PISO_DE_ESCRITA_DO_CABO_SEC)
    banca.mexer_o_motor_em(1.010, 200)
    banca.mexer_o_motor_em(1.011, 201)

    banca.rodar_ate(1.3)

    primeira = banca.a_escrita_do_valor(200)
    segunda = banca.a_escrita_do_valor(201)
    assert segunda - primeira >= bp.PISO_DE_ESCRITA_DO_CABO_SEC - 1e-9
    assert segunda - 1.011 <= bp.PISO_DE_ESCRITA_DO_CABO_SEC + 1e-9


def test_handle_sem_evento_dorme_o_prazo_de_antes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O dublê por `__new__` não tem Event nem piso: o laço é o de sempre."""
    banca = _Bancada(monkeypatch, throttle=0.032, piso=0.0)
    banca.inst._acordar = None
    dormidos: list[float] = []

    def sono(segundos: float) -> None:
        dormidos.append(segundos)
        banca.relogio.sleep(segundos)

    monkeypatch.setattr(time, "sleep", sono)

    banca.rodar_ate(0.2)

    assert dormidos
    assert set(dormidos) == {0.032}


def _handle_sem_laco() -> bp._PinnedPyDualSense:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst._acordar = threading.Event()
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst._acordar.clear()
    return inst


@pytest.mark.parametrize(
    "mexer",
    [
        lambda h: h.setLeftMotor(200),
        lambda h: h.setRightMotor(200),
        lambda h: setattr(h, "_raw_trigger_right", b"\x01" * 11),
        lambda h: setattr(h, "_vibracao_v2", True),
        lambda h: setattr(h, "_haptica_de_audio", True),
        lambda h: setattr(h, "_volumes_audio", [1, 2, 3, 4]),
        lambda h: setattr(h, "_mic_mute_desejado", True),
        lambda h: setattr(h, "_brilho_das_luzes", 2),
        lambda h: setattr(h, "ds_thread", False),
    ],
    ids=[
        "motor-esquerdo",
        "motor-direito",
        "gatilho-cru",
        "vibracao-v2",
        "haptica-de-audio",
        "volumes",
        "mic-mudo",
        "brilho",
        "fechar",
    ],
)
def test_mudar_um_campo_da_saida_arma_o_evento(
    mexer: Callable[[bp._PinnedPyDualSense], None],
) -> None:
    inst = _handle_sem_laco()
    assert not inst._acordar.is_set()

    mexer(inst)

    assert inst._acordar.is_set()


def test_campo_que_nao_e_da_saida_nao_arma_o_evento() -> None:
    """O contador da própria volta não pode acordá-la em laço."""
    inst = _handle_sem_laco()

    inst._last_write_at = 5.0
    inst._last_out_report = [0] * 64

    assert not inst._acordar.is_set()


def test_o_gatilho_aplicado_acorda_a_volta() -> None:
    """`triggerR.setForce` muda por dentro de um objeto: quem o muda acorda a volta."""
    from hefesto_dualsense4unix.core.controller import TriggerEffect

    inst = _handle_sem_laco()
    trigger = types.SimpleNamespace(mode=None, setForce=lambda i, v: None)
    inst.triggerL = trigger
    inst.triggerR = trigger
    efeito = TriggerEffect(mode=0, forces=(0, 0, 0, 0, 0, 0, 0))

    bp.PyDualSenseController._apply_trigger(inst, "right", efeito)
    assert inst._acordar.is_set()

    inst._acordar.clear()
    bp.PyDualSenseController._reset_trigger(inst, "left")
    assert inst._acordar.is_set()


def test_handle_sem_a_api_de_acordar_nao_quebra() -> None:
    """Um dublê sem `acordar_a_volta` fica como estava: a volta acorda no prazo dela.

    E o handle de verdade não tem o que engolir: sem o evento (nascido por
    `__new__`) o acordar não faz nada, e com a volta já fechada o `Event.set`
    só arma um evento que ninguém espera. Por isso o acordar não vai num
    `suppress` (a catraca da origem conta o remendo).
    """
    bp._acordar_a_volta_de(types.SimpleNamespace())

    handle = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    object.__setattr__(handle, "_acordar", None)
    bp._acordar_a_volta_de(handle)
    evento = threading.Event()
    object.__setattr__(handle, "_acordar", evento)
    bp._acordar_a_volta_de(handle)
    assert evento.is_set()


def _controlador(
    monkeypatch: pytest.MonkeyPatch,
    transportes: dict[str, str],
    adaptadores: dict[str, str],
) -> tuple[bp.PyDualSenseController, dict[str, types.SimpleNamespace]]:
    ctrl = bp.PyDualSenseController.__new__(bp.PyDualSenseController)
    handles = {
        uniq: types.SimpleNamespace(
            conType=types.SimpleNamespace(name=transporte), _piso_de_escrita_sec=None
        )
        for uniq, transporte in transportes.items()
    }
    ctrl._handles = handles
    monkeypatch.setattr(
        radio_da_mesa,
        "adaptador_por_uniq",
        lambda uniqs, **_k: {u: adaptadores.get(u, "") for u in uniqs},
    )
    return ctrl, handles


def test_quatro_no_cabo_tem_o_mesmo_piso_de_um(monkeypatch: pytest.MonkeyPatch) -> None:
    ctrl, handles = _controlador(monkeypatch, dict.fromkeys(UNIQS, "USB"), {})

    ctrl._aplicar_os_pisos_de_escrita_locked()

    assert {h._piso_de_escrita_sec for h in handles.values()} == {bp.PISO_DE_ESCRITA_DO_CABO_SEC}
    assert bp.PISO_DE_ESCRITA_DO_CABO_SEC < bp.REPORT_THREAD_THROTTLE_SEC


def test_quatro_no_radio_de_um_adaptador_mantem_o_piso_de_hoje(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctrl, handles = _controlador(
        monkeypatch, dict.fromkeys(UNIQS, "BT"), dict.fromkeys(UNIQS, "aa:bb:cc:00:00:01")
    )

    ctrl._aplicar_os_pisos_de_escrita_locked()

    esperado = min(bp.REPORT_THREAD_THROTTLE_SEC * 4, bp.REPORT_THREAD_THROTTLE_MAX_SEC)
    assert {h._piso_de_escrita_sec for h in handles.values()} == {esperado}


def test_dois_adaptadores_com_dois_contam_separados(monkeypatch: pytest.MonkeyPatch) -> None:
    adaptadores = {
        UNIQS[0]: "aa:bb:cc:00:00:01",
        UNIQS[1]: "aa:bb:cc:00:00:01",
        UNIQS[2]: "aa:bb:cc:00:00:02",
        UNIQS[3]: "aa:bb:cc:00:00:02",
    }
    ctrl, handles = _controlador(monkeypatch, dict.fromkeys(UNIQS, "BT"), adaptadores)

    ctrl._aplicar_os_pisos_de_escrita_locked()

    assert {h._piso_de_escrita_sec for h in handles.values()} == {
        bp.REPORT_THREAD_THROTTLE_SEC * 2
    }


def test_cabo_e_radio_misturados_nao_se_somam(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dois no cabo e dois no rádio: o do rádio conta os do rádio; o do cabo, ninguém."""
    transportes = {UNIQS[0]: "USB", UNIQS[1]: "USB", UNIQS[2]: "BT", UNIQS[3]: "BT"}
    adaptadores = {UNIQS[2]: "aa:bb:cc:00:00:01", UNIQS[3]: "aa:bb:cc:00:00:01"}
    ctrl, handles = _controlador(monkeypatch, transportes, adaptadores)

    ctrl._aplicar_os_pisos_de_escrita_locked()

    assert handles[UNIQS[0]]._piso_de_escrita_sec == bp.PISO_DE_ESCRITA_DO_CABO_SEC
    assert handles[UNIQS[1]]._piso_de_escrita_sec == bp.PISO_DE_ESCRITA_DO_CABO_SEC
    assert handles[UNIQS[2]]._piso_de_escrita_sec == bp.REPORT_THREAD_THROTTLE_SEC * 2
    assert handles[UNIQS[3]]._piso_de_escrita_sec == bp.REPORT_THREAD_THROTTLE_SEC * 2


def test_adaptador_ilegivel_cai_na_conta_so_do_radio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o /sys, os do rádio contam entre si (a conta de antes, sem os do cabo)."""
    transportes = {UNIQS[0]: "USB", UNIQS[1]: "BT", UNIQS[2]: "BT"}
    ctrl, handles = _controlador(monkeypatch, transportes, {})

    def quebra(*_a: object, **_k: object) -> dict[str, str]:
        raise OSError("sem /sys")

    monkeypatch.setattr(radio_da_mesa, "adaptador_por_uniq", quebra)

    ctrl._aplicar_os_pisos_de_escrita_locked()

    assert handles[UNIQS[0]]._piso_de_escrita_sec == bp.PISO_DE_ESCRITA_DO_CABO_SEC
    assert handles[UNIQS[1]]._piso_de_escrita_sec == bp.REPORT_THREAD_THROTTLE_SEC * 2


def test_o_piso_do_radio_obedece_ao_throttle_da_variavel_de_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bp, "REPORT_THREAD_THROTTLE_SEC", 0.01)
    ctrl, handles = _controlador(
        monkeypatch,
        {UNIQS[0]: "BT", UNIQS[1]: "BT"},
        {UNIQS[0]: "aa:bb:cc:00:00:01", UNIQS[1]: "aa:bb:cc:00:00:01"},
    )

    ctrl._aplicar_os_pisos_de_escrita_locked()

    assert {h._piso_de_escrita_sec for h in handles.values()} == {0.02}


def test_a_variavel_de_ambiente_define_o_throttle_na_importacao() -> None:
    env = dict(os.environ, HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC="0.02")
    saida = subprocess.run(
        [
            sys.executable,
            "-c",
            "from hefesto_dualsense4unix.core import backend_pydualsense as b;"
            "print(b.REPORT_THREAD_THROTTLE_SEC)",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert saida.stdout.strip().splitlines()[-1] == "0.02"
