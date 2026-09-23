"""Os Hz de verdade de cada controle — AR-MEDIDO-01 (23/09/2026), R10 dela.

Quem conta é o leitor do nó de MOVIMENTO (``MotionSensorReader``), que já lia
o nó para o giroscópio: um pacote por relatório de estado, carimbado pelo
kernel. Nada aqui abre ``/dev/input``: os eventos são dublês com o carimbo
escrito à mão.

A MORDIDA, feita em 23/09/2026: tirar a exclusão do intervalo que atravessa um
``SYN_DROPPED`` faz ``test_o_pacote_que_o_nosso_buffer_perdeu_nao_derruba_os_hz``
reprovar — o número cai de 800 para 520,7, e a tela diria que o RÁDIO
entregou menos quando quem perdeu foi a nossa thread. Devolvida, md5 conferido.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

ECODES = SimpleNamespace(
    EV_SYN=0, SYN_REPORT=0, SYN_DROPPED=3, EV_ABS=3, EV_MSC=4,
    ABS_X=0, ABS_Y=1, ABS_Z=2, ABS_RX=3, ABS_RY=4, ABS_RZ=5,
)


class Relogio:
    def __init__(self) -> None:
        self.agora = 50.0

    def __call__(self) -> float:
        return self.agora


def _leitor(relogio: Relogio) -> MotionSensorReader:
    leitor = MotionSensorReader(device_path=Path("/nao/existe"), target_uniq="aabbcc000011")
    leitor._relogio_da_taxa = relogio
    leitor._active_dev = object()
    leitor._zerar_a_taxa(aberto=True)
    return leitor


def _syn(leitor: MotionSensorReader, carimbo: float, *, codigo: int = 0) -> None:
    sec = int(carimbo)
    usec = round((carimbo - sec) * 1e6)
    leitor._handle_event(SimpleNamespace(type=0, code=codigo, sec=sec, usec=usec), ECODES)


def _pacotes(leitor: MotionSensorReader, inicio: float, hz: float, quantos: int) -> float:
    """``quantos`` pacotes a ``hz``; o relógio do processo anda junto."""
    relogio = leitor._relogio_da_taxa
    carimbo = inicio
    for _ in range(quantos):
        _syn(leitor, carimbo)
        carimbo += 1.0 / hz
        relogio.agora += 1.0 / hz
    return carimbo - 1.0 / hz


def test_o_no_que_recebe_250_pacotes_por_segundo_diz_250() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 500)
    hz = leitor.hz_do_movimento()
    assert hz is not None and 245.0 <= hz <= 255.0


def test_o_pacote_que_o_nosso_buffer_perdeu_nao_derruba_os_hz() -> None:
    """O ``SYN_DROPPED`` é perda NOSSA, não do rádio: o buraco não entra."""
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 800.0, 400)
    _syn(leitor, fim + 0.0001, codigo=3)
    # 350 ms de pacotes que a thread não leu: o próximo chega com o carimbo
    # de depois do buraco.
    relogio.agora += 0.350
    _pacotes(leitor, fim + 0.350, 800.0, 400)
    hz = leitor.hz_do_movimento()
    assert hz is not None and hz >= 760.0, f"o buraco do nosso buffer virou rádio lento: {hz}"


def test_o_silencio_do_radio_derruba_os_hz() -> None:
    """Sem ``SYN_DROPPED``, o buraco é do enlace — e ele TEM de aparecer."""
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 800.0, 400)
    relogio.agora += 0.350
    _pacotes(leitor, fim + 0.350, 800.0, 400)
    hz = leitor.hz_do_movimento()
    assert hz is not None and hz < 700.0


def test_no_aberto_e_mudo_por_uma_janela_inteira_e_zero() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 100)
    relogio.agora += 1.5
    assert leitor.hz_do_movimento() == 0.0


def test_no_fechado_ou_recem_aberto_e_nao_sei() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    _pacotes(leitor, 1_000.0, 250.0, 50)
    assert leitor.hz_do_movimento() is None, "menos de uma janela aberto não é taxa"
    relogio.agora += 2.0
    leitor._active_dev = None
    assert leitor.hz_do_movimento() is None
    leitor._active_dev = object()
    leitor._reset_on_disconnect()
    assert leitor.hz_do_movimento() is None


def test_o_carimbo_que_salta_para_tras_nao_vira_intervalo() -> None:
    relogio = Relogio()
    leitor = _leitor(relogio)
    fim = _pacotes(leitor, 1_000.0, 250.0, 250)
    _pacotes(leitor, fim - 3_600.0, 250.0, 250)
    hz = leitor.hz_do_movimento()
    assert hz is not None and 240.0 <= hz <= 260.0


# ---------------------------------------------------------------- o hub


class _Leitor:
    def __init__(self, hz: object) -> None:
        self._hz = hz

    def hz_do_movimento(self) -> object:
        return self._hz


def test_o_hub_pergunta_ao_leitor_e_registra_a_demanda() -> None:
    hub = SensorHub(auto_manutencao=False, relogio=lambda: 7.0)
    hub._motion["aabbcc000011"] = _Leitor(412.5)
    assert hub.hz_do_movimento("aabbcc000011") == 412.5
    assert hub._demanda["aabbcc000011"] == 7.0


def test_o_hub_sem_leitor_ou_com_resposta_torta_diz_nao_sei() -> None:
    hub = SensorHub(auto_manutencao=False)
    assert hub.hz_do_movimento("aabbcc000011") is None
    hub._motion["aabbcc000011"] = _Leitor(True)
    assert hub.hz_do_movimento("aabbcc000011") is None
    hub._motion["aabbcc000011"] = _Leitor("400")
    assert hub.hz_do_movimento("aabbcc000011") is None


# ---------------------------------------------------------------- o state_full

UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"
UNIQ_CABO = "aabbcc000003"
ADAPTADOR_A = "aa:bb:cc:00:00:0a"


class _Hub:
    def __init__(self, hz: dict[str, float]) -> None:
        self.hz = hz
        self.perguntados: list[str] = []

    def hz_do_movimento(self, uniq: str) -> float | None:
        self.perguntados.append(uniq)
        return self.hz.get(uniq)

    def leitura(self, _uniq: str) -> dict:
        return {}

    def entradas(self, _uniq: str) -> None:
        return None


class _Voz:
    def hz_de_voz(self, uniq: str) -> float | None:
        return {UNIQ_1: 98.0}.get(uniq)


class _Som:
    def pontes_de_pe(self) -> dict[str, str]:
        return {"AA:BB:CC:00:00:02": "haptica"}


def _handlers(monkeypatch: object) -> tuple[object, object]:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.integrations import radio_da_mesa
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(transport="bt"))
    daemon.controller.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {"uniq": UNIQ_1, "transport": "bt", "connected": True, "is_primary": True},
        {"uniq": UNIQ_2, "transport": "bt", "connected": True},
        {"uniq": UNIQ_CABO, "transport": "usb", "connected": True},
    ]
    daemon._bt_mic_subsystem = _Voz()
    daemon._alto_falante_subsystem = _Som()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        radio_da_mesa, "adaptador_por_uniq",
        lambda uniqs, **_kw: {u: ADAPTADOR_A for u in uniqs},
    )

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: object) -> None:
            self.daemon = alvo
            self.store = alvo.store  # type: ignore[attr-defined]
            self.controller = alvo.controller  # type: ignore[attr-defined]

    handlers = _Handlers(daemon)
    handlers._sensor_hub = _Hub({UNIQ_1: 402.3, UNIQ_2: 395.0, UNIQ_CABO: 250.0})
    # A identidade de fábrica já «respondida»: sem isto o `state_full` sai
    # perguntando ao hidraw da máquina por estes endereços de mentira.
    handlers._identidade_de_fabrica_cache = {
        u: {"serial": None, "modelo": None} for u in (UNIQ_1, UNIQ_2, UNIQ_CABO)
    }
    return daemon, handlers


@pytest.mark.asyncio
async def test_o_state_full_publica_as_quatro_chaves_do_ar_por_controle(
    monkeypatch: object,
) -> None:
    _daemon, handlers = _handlers(monkeypatch)
    payload = await handlers._handle_daemon_state_full({})  # type: ignore[attr-defined]
    por_uniq = {c["uniq"]: c for c in payload["controllers"]}
    um, dois, cabo = por_uniq[UNIQ_1], por_uniq[UNIQ_2], por_uniq[UNIQ_CABO]
    assert (um["adaptador"], um["hz_movimento"], um["hz_voz"], um["ponte_do_radio"]) == (
        ADAPTADOR_A, 402.3, 98.0, None)
    assert (dois["hz_movimento"], dois["hz_voz"], dois["ponte_do_radio"]) == (
        395.0, None, "haptica")
    assert (cabo["adaptador"], cabo["hz_movimento"], cabo["hz_voz"], cabo["ponte_do_radio"]) == (
        None, 250.0, None, None), "o cabo não tem adaptador, voz nem ponte de rádio"


@pytest.mark.asyncio
async def test_no_modo_falso_o_state_full_nao_abre_socket_de_bluetooth(
    monkeypatch: object,
) -> None:
    import socket

    _daemon, handlers = _handlers(monkeypatch)

    def recusa(*_a: object, **_k: object) -> None:
        raise AssertionError("a suíte abriu um socket de verdade")

    monkeypatch.setattr(socket, "socket", recusa)  # type: ignore[attr-defined]
    payload = await handlers._handle_daemon_state_full({})  # type: ignore[attr-defined]
    assert "radio_ar" in payload
    assert handlers._medidor_de_ar is None  # type: ignore[attr-defined]


class _Medidor:
    def __init__(self, ar: dict[str, object]) -> None:
        self.ar = ar

    def amostrar(self) -> dict[str, object]:
        return dict(self.ar)


@pytest.mark.asyncio
async def test_o_state_full_publica_o_orcamento_de_ar_por_adaptador(
    monkeypatch: object,
) -> None:
    import time

    from hefesto_dualsense4unix.integrations.ar_do_adaptador import ArDoAdaptador

    _daemon, handlers = _handlers(monkeypatch)
    vazio = "aa:bb:cc:00:00:0b"
    handlers._medidor_de_ar = _Medidor({  # type: ignore[attr-defined]
        ADAPTADOR_A: ArDoAdaptador(hci=0, endereco=ADAPTADOR_A, entrada_por_s=701.0,
                                   saida_por_s=95.0, conexoes=()),
        vazio: ArDoAdaptador(hci=1, endereco=vazio, entrada_por_s=0.0, conexoes=()),
    })
    handlers._afh_evitados = {ADAPTADOR_A: (20, 21, 22), vazio: None}  # type: ignore[attr-defined]
    handlers._afh_lido_em = time.monotonic()  # type: ignore[attr-defined]
    payload = await handlers._handle_daemon_state_full({})  # type: ignore[attr-defined]
    ar = payload["radio_ar"]
    a = ar[ADAPTADOR_A]
    assert [c["uniq"] for c in a["controles"]] == [UNIQ_1, UNIQ_2]
    assert a["pontes"] == [{"uniq": UNIQ_2, "modo": "haptica"}]
    assert (a["n_max"], a["rotulo"]) == (2, "Folgada")
    assert (a["entrada_por_s"], a["saida_por_s"]) == (701.0, 95.0)
    assert a["canais_evitados"] == [20, 21, 22]
    assert ar[vazio]["controles"] == [] and ar[vazio]["pontes"] == []
    assert ar[vazio]["canais_evitados"] is None


def test_o_afh_e_perguntado_numa_thread_e_so_de_tempos_em_tempos(
    monkeypatch: object,
) -> None:
    import threading
    import time

    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar_mod

    _daemon, handlers = _handlers(monkeypatch)
    perguntas: list[tuple[int, int]] = []
    nomes_da_thread: list[str] = []

    def ler(hci: int, handle: int) -> ar_mod.MapaAFH:
        perguntas.append((hci, handle))
        nomes_da_thread.append(threading.current_thread().name)
        canais = tuple(n not in (40, 41) for n in range(ar_mod.CANAIS_DO_BT))
        return ar_mod.MapaAFH(handle=handle, modo=1, canais=canais)

    handlers._ler_afh = ler  # type: ignore[attr-defined]
    leitura = ar_mod.ArDoAdaptador(
        hci=2, endereco=ADAPTADOR_A, entrada_por_s=700.0,
        conexoes=(ar_mod.Conexao(12, "aa:bb:cc:00:00:01", ar_mod.TIPO_ACL, True, 1, 7),),
    )
    handlers._talvez_ler_o_afh({ADAPTADOR_A: leitura})  # type: ignore[attr-defined]
    prazo = time.monotonic() + 2.0
    while handlers._afh_em_voo and time.monotonic() < prazo:  # type: ignore[attr-defined]
        time.sleep(0.01)
    assert perguntas == [(2, 12)]
    assert nomes_da_thread == ["radio-afh"], "o AFH não pode esperar no laço do daemon"
    assert handlers._afh_evitados == {ADAPTADOR_A: (40, 41)}  # type: ignore[attr-defined]
    handlers._talvez_ler_o_afh({ADAPTADOR_A: leitura})  # type: ignore[attr-defined]
    assert perguntas == [(2, 12)], "o AFH foi perguntado de novo antes do período"


# ---------------------------------------------------------------- a voz


class _Stats:
    def __init__(self, audio: int, invalidos: int = 0) -> None:
        self.quadros_audio = audio
        self.quadros_invalidos = invalidos


class _PonteDoMic:
    def __init__(self, uniq: str) -> None:
        self.no = SimpleNamespace(uniq=uniq)
        self.audio = 0
        self.invalidos = 0

    def estatistica(self) -> _Stats:
        return _Stats(self.audio, self.invalidos)


def test_a_voz_e_a_taxa_de_quadros_de_audio_da_ponte_do_microfone() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    ponte = _PonteDoMic("AA:BB:CC:00:00:01")
    sub = BtMicSubsystem(gerenciador=SimpleNamespace(pontes={"/dev/hidraw9": ponte}))
    sub._gerenciador = sub._gerenciador_injetado
    relogio = Relogio()
    sub._relogio_da_voz = relogio
    assert sub.hz_de_voz(UNIQ_1) is None, "a primeira amostra não é taxa"
    relogio.agora += 1.0
    ponte.audio, ponte.invalidos = 100, 6
    assert sub.hz_de_voz(UNIQ_1) == 106.0, "o quadro inválido também ocupou o ar"
    relogio.agora += 0.4
    ponte.audio = 500
    assert sub.hz_de_voz(UNIQ_1) == 106.0, "entre janelas repete a última"
    relogio.agora += 0.6
    ponte.audio, ponte.invalidos = 100, 6  # ninguém ouvindo: o contador parou
    assert sub.hz_de_voz(UNIQ_1) == 0.0, "ponte de pé e ninguém ouvindo é zero"


def test_sem_ponte_do_microfone_a_voz_e_nao_sei() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    sub = BtMicSubsystem(gerenciador=SimpleNamespace(pontes={}))
    sub._gerenciador = sub._gerenciador_injetado
    assert sub.hz_de_voz(UNIQ_1) is None
    assert BtMicSubsystem().hz_de_voz(UNIQ_1) is None, "sem gerenciador: não sei"
