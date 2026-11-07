"""O laço mede o atraso, e não só o corpo do tique.

O `_poll_loop` de produção roda aqui, com o vigia de produção em volta. O laço se prende por
fora do tique, em fase aleatória (`loop.call_soon(time.sleep, s)`): `sleep` dentro de um handler
de IPC não prova nada, porque o `ipc_lento` já o vê.

Mordidas (arranque a cura, veja reprovar, devolva):

- `medidor.abrir` fora do `_poll_loop`: só o corpo se mede, e o atraso some;
- `self._voltas.append` fora de `_bater`: a volta lenta não vira linha nem contador;
- `quem_prende` devolvendo `SEM_AMOSTRA`: o nome some;
- `_medir_a_fila` sem os ocupantes: a fila do pool não diz quem a ocupou;
- `_escrever_os_numeros` pela batida, no fio do laço: o arquivo para junto com o laço.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import vigia_do_laco as vl
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

JANELA = 40
PRESO_S = 0.2
_UNIQ = {n: f"02:fe:00:00:00:0{n}" for n in (1, 2, 3, 4)}

NOMES_DA_MEDIDA = {
    "poll.laco.lentas",
    "poll.laco.pior_us",
    "poll.pool.lentas",
    "poll.tique.atraso_p99_us",
    "poll.tique.atraso_pior_us",
    "poll.tique.espera_pool_pior_us",
    "poll.tique.intervalo_pior_us",
}


class _Evento(SimpleNamespace):
    type: int
    code: int
    value: int


class _Pad:
    def __init__(self) -> None:
        self.chegadas = 0

    def forward_analog(self, **_kw: int) -> None: ...

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        if pressed:
            self.chegadas += 1


class _Laco:
    """O `_poll_loop` de produção com a mesa dada; ``transportes[0]`` é quem fica no primário."""

    def __init__(
        self, transportes: tuple[str, ...], *, primario_de_pe: bool = True, posicoes: Any = None,
    ) -> None:
        estado = ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport=transportes[0]
        )
        self.config = SimpleNamespace(poll_hz=60)

        def read_state() -> ControllerState:
            return estado

        self.controller: Any = SimpleNamespace(
            is_connected=lambda: primario_de_pe, read_state=read_state
        )
        self.store = StateStore()
        self.bus = SimpleNamespace(publish=lambda *_a, **_k: None)
        self._stop_event: asyncio.Event | None = None
        self._input_ready_at = 0.0
        self._external_tick_task: Any = None
        self._steam_jogo_task: Any = None
        self._game_signal_task: Any = None
        self._last_state: Any = None
        self._gamepad_device: Any = _Pad()
        self._mouse_device: Any = None
        self._keyboard_device: Any = None
        self._touchpad_reader: Any = None
        self._hotkey_manager: Any = None
        self._plugins_subsystem: Any = None
        self._paused = False
        self._native_mode = False
        self._emulation_suppressed = False
        self._emu_calada_motivo: Any = None
        self._executor = vl.PoolQueDizQuem(max_workers=2)
        gerente = co.CoopManager.__new__(co.CoopManager)
        gerente._players = {}
        gerente._daemon = self  # type: ignore[assignment]
        self.pads = {n: _Pad() for n in (posicoes or (2, 3, 4))}
        self.leitores = {n: EvdevReader(device_path=Path(f"/nao/existe/{n}")) for n in self.pads}
        for n, pad in self.pads.items():
            gerente._players[_UNIQ[n]] = co._SecondaryPlayer(
                identity=_UNIQ[n], evdev_path=f"/dev/input/event-do-p{n}",
                reader=self.leitores[n], player_index=n, vpad=pad,  # type: ignore[arg-type]
            )
        self._coop_manager = gerente
        self._poll_loop = Daemon._poll_loop.__get__(self)
        self._run_blocking = MethodType(Daemon._run_blocking, self)
        self._restantes = JANELA

    def _is_stopping(self) -> bool:
        self._restantes -= 1
        return self._restantes < 0

    def _evdev_buttons_once(self) -> frozenset[str]:
        return frozenset()

    def _sync_identity_registry(self) -> None: ...
    def _seguir_a_carta(self) -> None: ...
    def aplicar_gamepad_para_multiplos_controles(self) -> None: ...
    def _amostrar_bateria(self, _agora: float) -> None: ...
    def _schedule_external_tick(self) -> None: ...
    def _schedule_steam_jogo_tick(self) -> None: ...
    def _reconciliar_exposicao_do_modo_nativo(self, **_k: object) -> None: ...
    def _drenar_modo_pendente(self) -> None: ...
    async def _sync_game_signal(self) -> None: ...
    def _reassert_rumble(self, _agora: float) -> None: ...
    def _jogo_no_controle_do_desktop(self) -> None:
        return None

    def _calar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _liberar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _dispatch_gamepad_emulation(self, *_a: Any) -> None: ...
    def _prime_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_mouse_emulation(self, *_a: Any) -> None: ...

    async def rodar(self) -> None:
        self._stop_event = asyncio.Event()
        try:
            await self._poll_loop()
        finally:
            self._executor.shutdown(wait=True)

    def contadores(self) -> dict[str, int]:
        return self.store.snapshot().counters


@pytest.fixture(autouse=True)
def _o_laco_sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(lc, "JANELA_DO_MEDIDOR_DO_TIQUE", JANELA)
    monkeypatch.setattr(lc, "RELOGIOS_LENTOS", ())


def _prender_em_fase_aleatoria(semente: int, preso_s: float = PRESO_S) -> None:
    """Agenda a parada DE FORA do tique, numa fase que nenhum teste escolheu."""
    laco = asyncio.get_running_loop()
    fase = random.Random(semente).uniform(0.05, 0.3)
    laco.call_later(fase, lambda: laco.call_soon(time.sleep, preso_s))


def _o_atraso_visto(c: dict[str, int]) -> int:
    """A parada que caiu na espera sai no atraso; a que caiu no ``await`` do tique, no corpo."""
    return c["poll.tique.atraso_pior_us"] + c["poll.tique.pior_us"]


def _rodar_vigiado(
    daemon: _Laco, *antes: Any, ditos: list[tuple[str, dict[str, Any]]] | None = None,
) -> None:
    def avisar(evento: str, **campos: Any) -> None:
        if ditos is not None:
            ditos.append((evento, campos))

    async def corpo() -> None:
        for agendar in antes:
            agendar()
        await vl.vigiado(daemon.rodar(), avisar=avisar)

    asyncio.run(corpo())


@pytest.mark.parametrize("semente", [1, 2, 3])
def test_o_laco_preso_200_ms_sobe_o_atraso_e_da_o_nome(semente: int) -> None:
    """A parada que o corpo do tique não vê: o atraso a vê, e a linha diz quem a causou.

    MORDIDA: tire `medidor.abrir` do `_poll_loop`, e o atraso some, com o corpo igual.
    """
    daemon = _Laco(("usb", "usb", "bt", "bt"))
    ditos: list[tuple[str, dict[str, Any]]] = []

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(semente), ditos=ditos)

    c = daemon.contadores()
    assert _o_atraso_visto(c) >= 150_000, c
    assert c["poll.tique.intervalo_pior_us"] >= 150_000, c
    assert c["poll.laco.lentas"] == 1, c
    assert c["poll.laco.lenta.sleep"] >= 190_000, c
    linhas = [campos for evento, campos in ditos if evento == "laco_lento"]
    assert len(linhas) == 1, ditos
    assert linhas[0]["tarefa"] == "sleep" and linhas[0]["ms"] >= 190, linhas


def test_a_tarefa_que_prende_sai_pelo_nome_e_pela_linha() -> None:
    """Dentro de tarefa, sai o nome da tarefa; sem nome dado, o da corrotina, nunca ``Task-12``."""
    daemon = _Laco(("usb", "usb", "bt", "bt"))
    ditos: list[tuple[str, dict[str, Any]]] = []

    async def segura_o_laco() -> None:
        await asyncio.sleep(0.15)
        time.sleep(PRESO_S)

    def agendar() -> None:
        asyncio.get_running_loop().create_task(segura_o_laco())

    _rodar_vigiado(daemon, agendar, ditos=ditos)

    linhas = [campos for evento, campos in ditos if evento == "laco_lento"]
    assert len(linhas) == 1, ditos
    assert "segura_o_laco" in linhas[0]["tarefa"], linhas
    assert "segura_o_laco" in linhas[0]["onde"], linhas


@pytest.mark.parametrize("semente", [11, 12, 13])
def test_um_segundo_preso_em_fase_aleatoria_nao_se_perde(semente: int) -> None:
    """``pior_us`` baixo não absolve: 1 s preso sai no atraso com o corpo em µs."""
    daemon = _Laco(("bt", "usb", "usb", "bt"))

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(semente, 1.0))

    c = daemon.contadores()
    assert _o_atraso_visto(c) >= 900_000, c
    assert c["poll.laco.pior_us"] >= 1_000_000, c
    assert c["poll.laco.lenta.sleep"] == c["poll.laco.pior_us"], c


def test_a_medida_do_laco_sobrevive_as_janelas_seguintes() -> None:
    """O número da janela esquece; o da subida não, e é o que o doctor lê depois de jogar."""
    daemon = _Laco(("usb", "bt", "bt", "bt"))
    daemon._restantes = JANELA * 3

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(5))

    c = daemon.contadores()
    assert c["poll.tique.atraso_pior_us"] < 100_000, "a janela velha deveria ter saído"
    assert c["poll.laco.pior_us"] >= 190_000, c
    assert c["poll.laco.lentas"] == 1, c


def _segurar_os_fios(daemon: _Laco, fios: int, ditos: list[threading.Event]) -> None:
    pode_sair = threading.Event()
    ditos.append(pode_sair)

    def segura_o_fio() -> None:
        pode_sair.wait(0.3)

    for _ in range(fios):
        daemon._executor.submit(segura_o_fio)


def test_os_dois_fios_presos_dizem_quem_os_ocupou() -> None:
    """Pool cheio não é laço parado: a fila sobe, sai o nome, e o laço segue limpo.

    MORDIDA: em `_medir_a_fila`, ignore `ocupantes`, e o nome some.
    """
    daemon = _Laco(("usb", "bt", "usb", "bt"))
    ditos: list[tuple[str, dict[str, Any]]] = []
    eventos: list[threading.Event] = []

    _rodar_vigiado(daemon, lambda: _segurar_os_fios(daemon, 2, eventos), ditos=ditos)

    c = daemon.contadores()
    assert c["poll.tique.espera_pool_pior_us"] >= 250_000, c
    assert c["poll.pool.lentas"] >= 1, c
    nome = next(k for k in c if k.startswith("poll.pool.ocupante."))
    assert nome.endswith("segura_o_fio"), c
    assert c["poll.laco.lentas"] == 0, c
    assert c["poll.tique.pior_us"] >= 250_000, "o corpo vê o pool: é o caso oposto ao do laço"
    linhas = [campos for evento, campos in ditos if evento == "pool_lento"]
    assert linhas and linhas[0]["esperou"].endswith("read_state"), ditos
    assert linhas[0]["ocupado_por"][0].endswith("segura_o_fio"), linhas


def test_um_fio_preso_so_nao_faz_fila() -> None:
    daemon = _Laco(("usb", "bt", "usb", "bt"))
    eventos: list[threading.Event] = []

    _rodar_vigiado(daemon, lambda: _segurar_os_fios(daemon, 1, eventos))

    c = daemon.contadores()
    assert c["poll.tique.espera_pool_pior_us"] < 100_000, c
    assert c["poll.pool.lentas"] == 0, c


@pytest.mark.parametrize(
    "mesa",
    [
        ("usb", "usb", "usb", "usb"),
        ("usb", "usb", "usb", "bt"),
        ("bt", "usb", "usb", "usb"),
        ("usb", "usb", "bt", "bt"),
        ("usb", "bt", "bt", "bt"),
        ("bt", "bt", "bt", "bt"),
    ],
    ids=["4-cabos", "3-cabos-1-radio", "1-radio-3-cabos", "2-e-2", "1-cabo-3-radios", "4-radios"],
)
def test_os_quatro_juntos_medem_igual_na_mesa_misturada(mesa: tuple[str, ...]) -> None:
    """O atraso é um só para a mesa: nenhum contador nasce de um jogador ou de um transporte."""
    daemon = _Laco(mesa)

    def apertar_durante_a_parada() -> None:
        laco = asyncio.get_running_loop()
        evento = SimpleNamespace(type=ecodes.EV_KEY, code=ecodes.BTN_SOUTH, value=1)
        for leitor in daemon.leitores.values():
            laco.call_later(0.15, leitor._handle_event, evento, ecodes)

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(7), apertar_durante_a_parada)

    c = daemon.contadores()
    medidas = {k for k in c if k.startswith(("poll.laco", "poll.pool", "poll.tique.atraso",
                                             "poll.tique.espera", "poll.tique.intervalo"))}
    assert medidas == NOMES_DA_MEDIDA | {"poll.laco.lenta.sleep"}, medidas
    assert not any(uniq in chave for chave in c for uniq in _UNIQ.values())
    assert _o_atraso_visto(c) >= 100_000, c
    assert all(pad.chegadas >= 1 for pad in daemon.pads.values()), "a mesa não estava viva"


def test_so_o_p3_de_pe_mede_o_mesmo_atraso() -> None:
    """Sem primário, o tique corre pelo outro ramo: o atraso tem de sair por ele também."""
    daemon = _Laco(("usb",), primario_de_pe=False, posicoes=(3,))

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(9))

    c = daemon.contadores()
    assert _o_atraso_visto(c) >= 100_000, c
    assert c["poll.laco.lentas"] == 1, c


@pytest.mark.parametrize(
    ("mesa", "quem"),
    [
        (("usb", "usb", "usb", "bt"), 2),
        (("usb", "bt", "bt", "bt"), 3),
        (("usb", "usb", "bt", "bt"), 4),
        (("bt", "bt", "bt", "bt"), 2),
    ],
    ids=["3-cabos-1-radio-do-p2", "1-cabo-3-radios-do-p3", "2-e-2-do-p4", "4-radios-do-p2"],
)
def test_o_gesto_de_modo_de_um_nao_para_a_entrada_dos_outros_tres(
    mesa: tuple[str, ...], quem: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os três custos do gesto dormindo: o disco, a descoberta e a gravação, e os outros jogando.

    MORDIDA: devolva `descobrir_os_nos` ou a gravação do modo ao fio do laço, e a parada aparece.
    """
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.profiles import manager

    def dorme(*_a: Any, **_k: Any) -> Any:
        time.sleep(0.25)
        return {}

    monkeypatch.setattr(evdev_reader, "discover_dualsense_evdevs", dorme)
    monkeypatch.setattr(co, "externos_que_ganham_virtual", dict)
    monkeypatch.setattr(manager, "gravar_o_modo_no_perfil_ativo", dorme)
    monkeypatch.setattr(manager, "nome_do_perfil_que_grava", lambda *_a: "Ensaio")
    monkeypatch.setattr(co.CoopManager, "should_be_active", lambda self: False)
    daemon = _Laco(mesa)
    daemon.config.mouse_speed = daemon.config.mouse_scroll_speed = 1
    outros = [n for n in daemon.pads if n != quem]
    ditos: list[tuple[str, dict[str, Any]]] = []

    def gesto() -> None:
        laco = asyncio.get_running_loop()

        def fazer() -> None:
            daemon._coop_manager._nos_de_agora(True, "manual")
            Daemon.gravar_o_modo_escolhido(daemon, "gamepad",  # type: ignore[arg-type]
                                           caminho="xbox", mascara="xbox", porta="controle")

        laco.call_later(0.1, fazer)
        evento = SimpleNamespace(type=ecodes.EV_KEY, code=ecodes.BTN_SOUTH, value=1)
        for n in outros:
            laco.call_later(0.2, daemon.leitores[n]._handle_event, evento, ecodes)

    _rodar_vigiado(daemon, gesto, ditos=ditos)
    manager.FIO_DO_PERFIL.submit(lambda: None).result(timeout=5.0)

    c = daemon.contadores()
    assert c["poll.laco.lentas"] == 0, ditos
    assert c["poll.tique.atraso_pior_us"] < 100_000, c
    assert all(daemon.pads[n].chegadas >= 1 for n in outros), "um dos três parou com o gesto"


@pytest.mark.parametrize(
    "mesa",
    [("usb", "usb", "usb", "bt"), ("usb", "bt", "bt", "bt"), ("usb", "usb", "bt", "bt")],
    ids=["3-cabos-1-radio", "1-cabo-3-radios", "2-e-2"],
)
def test_a_troca_de_cabo_de_um_nao_fura_o_tique_dos_outros_tres(
    mesa: tuple[str, ...], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O cabo que entra suja a assinatura: a releitura presa fica fora do tique e dos três.

    MORDIDA: devolva a releitura ao fio do laço em `_caderno_das_janelas`.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    monkeypatch.setattr(jl, "RELOGIO_DO_CADERNO_S", 0.05)
    monkeypatch.setattr(jl, "_relendo", False)
    monkeypatch.setattr(jl, "_relido_em", float("-inf"))
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: ("cabo novo",))
    solta = threading.Event()
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: [solta.wait(3.0), ][:0])
    monkeypatch.setattr(jl, "_NOMES_DAS_JANELAS", (("cabo velho",), [], {}))
    daemon = _Laco(mesa)
    janela = SimpleNamespace(store=SimpleNamespace(window_detect_current_class="firefox"))
    ditos: list[tuple[str, dict[str, Any]]] = []

    def agendar() -> None:
        laco = asyncio.get_running_loop()
        evento = SimpleNamespace(type=ecodes.EV_KEY, code=ecodes.BTN_SOUTH, value=1)

        def perguntar(vezes: int) -> None:
            Daemon._janela_de_jogo_em_foco(janela)  # type: ignore[arg-type]
            if vezes:
                laco.call_later(1 / 60, perguntar, vezes - 1)

        perguntar(30)
        for leitor in daemon.leitores.values():
            laco.call_later(0.3, leitor._handle_event, evento, ecodes)

    _rodar_vigiado(daemon, agendar, ditos=ditos)
    solta.set()

    c = daemon.contadores()
    assert c["poll.laco.lentas"] == 0, ditos
    assert all(pad.chegadas >= 1 for pad in daemon.pads.values())


def test_a_medida_nao_escreve_no_tique() -> None:
    """O acréscimo não escreve no store fora do fechamento da janela: só os dois de sempre."""
    store = StateStore()
    escritas: list[str] = []
    original = store.bump

    def contar(nome: str, delta: int = 1) -> int:
        escritas.append(nome)
        return original(nome, delta)

    store.bump = contar  # type: ignore[method-assign]
    medidor = lc._MedidorDoTique(store)
    for i in range(10):
        medidor.abrir(float(i), float(i) - 0.001)
        medidor.registrar(0.001, [])

    assert set(escritas) == {"poll.tique.medidos"}, escritas


def test_o_tique_sem_espera_nao_inventa_atraso() -> None:
    """O corpo que passou do período não dormiu: o que ele vale está no intervalo."""
    store = StateStore()
    medidor = lc._MedidorDoTique(store)
    for i in range(lc.JANELA_DO_MEDIDOR_DO_TIQUE):
        medidor.abrir(i * 0.1, None)
        medidor.registrar(0.001, [])

    c = store.snapshot().counters
    assert "poll.tique.atraso_p99_us" not in c
    assert c["poll.tique.intervalo_pior_us"] == pytest.approx(100_000, abs=1)


def test_os_numeros_saem_com_o_laco_preso_sem_passar_pelo_laco() -> None:
    """O arquivo é escrito pelo fio do vigia: a parada aparece nele enquanto dura.

    MORDIDA: chame `_escrever_os_numeros` de `_bater`, e o arquivo só anda depois da parada.
    """
    daemon = _Laco(("usb", "usb", "bt", "bt"))
    caminho = runtime_dir(ensure=True) / vl.ARQUIVO_DOS_NUMEROS
    vistos: list[float] = []
    acabou = threading.Event()

    def ler() -> None:
        while not acabou.wait(0.05):
            try:
                vistos.append(json.loads(caminho.read_text(encoding="utf-8"))["laco_parado_ha_s"])
            except (OSError, ValueError):
                continue

    leitor = threading.Thread(target=ler, daemon=True)
    leitor.start()
    try:
        _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(3, 1.6))
    finally:
        acabou.set()
        leitor.join()

    assert max(vistos) >= 0.4, vistos
    retrato = json.loads(caminho.read_text(encoding="utf-8"))
    assert retrato["contadores"]["poll.laco.lentas"] == 1, retrato


def test_a_pilha_vai_ao_arquivo_em_memoria_e_nao_ao_stderr(
    capfd: pytest.CaptureFixture[str],
) -> None:
    daemon = _Laco(("usb", "usb", "bt", "bt"))

    _rodar_vigiado(daemon, lambda: _prender_em_fase_aleatoria(4, 0.8))

    pilhas = (runtime_dir() / vl.ARQUIVO_DAS_PILHAS).read_text(encoding="utf-8")
    assert "Timeout (" in pilhas and "_run_once" in pilhas, pilhas[:400]
    assert "Timeout (" not in capfd.readouterr().err


def test_a_pilha_cheia_gira_e_nao_come_a_memoria() -> None:
    caminho = runtime_dir(ensure=True) / vl.ARQUIVO_DAS_PILHAS
    caminho.write_bytes(b"x" * vl.TETO_DAS_PILHAS_BYTES)
    vigia = vl.VigiaDoLaco()
    vigia._abrir_as_pilhas()

    vigia._girar_as_pilhas()

    assert caminho.stat().st_size == 0
    assert caminho.with_name(caminho.name + ".1").stat().st_size == vl.TETO_DAS_PILHAS_BYTES
    assert vigia._saida is vigia._pilhas and vigia._pilhas is not None
    vigia._pilhas.close()


def test_a_volta_sem_amostra_nao_herda_o_nome_da_parada_de_antes() -> None:
    """Uma amostra velha não batiza a volta seguinte: sem amostra na parada, o nome é esse."""
    ditos: list[tuple[str, dict[str, Any]]] = []
    vigia = vl.VigiaDoLaco(avisar=lambda evento, **campos: ditos.append((evento, campos)))
    vigia._amostra = (10.0, "antiga", "aqui")
    vigia._voltas.append((20.0, 20.5))

    vigia._dizer_as_voltas()

    assert ditos == [("laco_lento", {"ms": 500, "tarefa": vl.SEM_AMOSTRA, "onde": ""})]


def test_os_nomes_tem_teto() -> None:
    """Nome de tarefa vira chave de contador: o laço nunca cria chave sem fim."""
    vigia = vl.VigiaDoLaco(avisar=lambda *_a, **_k: None)
    for i in range(vl.TETO_DE_NOMES + 5):
        vigia._amostra = (float(i), f"tarefa_{i}", "")
        vigia._voltas.append((float(i), float(i) + 0.2))
        vigia._dizer_as_voltas()

    assert len(vigia._por_tarefa) == vl.TETO_DE_NOMES + 1
    assert vl.DEMAIS_NOMES in vigia._por_tarefa


def test_o_doctor_diz_o_atraso_e_quem_prendeu() -> None:
    """O doctor lê os contadores do `state_full`, o dono de sempre."""
    linha = cmd_doctor._linha_do_atraso({
        "poll.laco.lentas": 3, "poll.laco.pior_us": 1_234_000,
        "poll.laco.lenta.sleep": 200_000, "poll.laco.lenta.poll_loop": 1_234_000,
        "poll.pool.lentas": 2, "poll.pool.ocupante.segura_o_fio": 300_000,
    })

    assert linha == ("[ OK ]", "atraso do serviço: 3 acima de 100 ms, a pior 1234,0 ms em "
                     "«poll_loop»; 2 na fila do pool, a pior 300,0 ms atrás de «segura_o_fio»")


def test_o_doctor_sem_parada_diz_que_nao_houve_e_sem_medida_cala() -> None:
    assert cmd_doctor._linha_do_atraso(None) is None
    assert cmd_doctor._linha_do_atraso({}) is None
    assert cmd_doctor._linha_do_atraso({"poll.laco.lentas": 0}) == (
        "[ OK ]", "atraso do serviço: nenhuma parada acima de 100 ms"
    )


def test_a_linha_do_tique_leva_o_atraso_real() -> None:
    linha = cmd_doctor._linha_do_tique({
        "poll.tique.medidos": 600, "poll.tique.p99_us": 590, "poll.tique.pior_us": 678,
        "poll.tique.atraso_p99_us": 1_200, "poll.tique.atraso_pior_us": 210_000,
    })

    assert linha is not None
    assert linha[1].endswith("atraso p99 1,2 ms, pior 210,0 ms"), linha
