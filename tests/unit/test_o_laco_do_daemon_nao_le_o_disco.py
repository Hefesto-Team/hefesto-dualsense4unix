"""O `state_full` responde do que já leu: nenhuma porta dele abre o ext4 no fio do laço."""
from __future__ import annotations

import ast
import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad, keyboard
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_o_laco_nao_grava_perfil_nem_espera_o_systemctl import _Grafo

DORME_S = 2.0
TETO_DA_RESPOSTA_S = 0.3
_JANELA = "steam_app_9931993"
_OS_QUATRO = tuple(f"aa:bb:cc:00:00:0{n}" for n in range(1, 5))
_SRC = Path(__file__).resolve().parents[2] / "src"
_AS_MESAS = {
    "4 cabos": ("usb", "usb", "usb", "usb"),
    "3 cabos e 1 rádio": ("usb", "usb", "usb", "bt"),
    "2 e 2": ("usb", "bt", "usb", "bt"),
    "1 cabo e 3 rádios": ("bt", "usb", "bt", "bt"),
    "4 rádios": ("bt", "bt", "bt", "bt"),
}
_OS_MODOS: dict[str, dict[str, Any]] = {
    "dualsense": {"gamepad_emulation_enabled": True, "gamepad_flavor": "dualsense"},
    "xbox": {"gamepad_emulation_enabled": True, "gamepad_flavor": "xbox"},
    "mouse": {"mouse_emulation_enabled": True},
    "nativo": {},
}


class _Disco:
    """Uma leitura de disco de mentira: conta, anota o fio e dorme quando mandam."""

    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.fios: list[str] = []
        self.dorme_s = 0.0
        self.levanta: Exception | None = None

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        self.fios.append(threading.current_thread().name)
        time.sleep(self.dorme_s)
        if self.levanta is not None:
            raise self.levanta
        return self.resposta


@dataclass
class _AsPortas:
    pontes: _Disco
    marker: _Disco
    perfis: _Disco
    motores: _Disco
    osk: _Disco

    def todas(self) -> tuple[_Disco, ...]:
        return (self.pontes, self.marker, self.perfis, self.motores, self.osk)


@pytest.fixture
def portas(monkeypatch: pytest.MonkeyPatch) -> _AsPortas:
    dubles = _AsPortas(
        pontes=_Disco({_OS_QUATRO[0]: "ponte"}),
        marker=_Disco((9931993, int(time.time()))),
        perfis=_Disco([]),
        motores=_Disco({_OS_QUATRO[0]: (60, 40)}),
        osk=_Disco(True),
    )
    monkeypatch.setattr(ih, "_pontes_confirmadas_seguro", dubles.pontes)
    monkeypatch.setattr(launch_env, "read_last_run_marker", dubles.marker)
    monkeypatch.setattr(loader, "load_all_profiles", dubles.perfis)
    monkeypatch.setattr(gamepad, "_motores_do_perfil_ativo", dubles.motores)
    monkeypatch.setattr(keyboard, "osk_disponivel_no_sistema", dubles.osk)
    return dubles


def _servidor(tmp_path: Path, controle: Any = None, **config: Any) -> IpcServer:
    controle = controle or FakeController(transport="bt")  # type: ignore[arg-type]
    daemon = Daemon(
        controller=controle,
        config=DaemonConfig(
            poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
            **config,
        ),
    )
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "laco.sock", daemon=daemon)
    daemon._ipc_server = servidor
    daemon.store.set_window_detect_backend("xlib", True)
    daemon.store.record_window_detect_read("xlib", _JANELA, wm_name="Jogo", exe_basename="a.exe")
    return servidor


async def _a_leitura_acabou(leitura: Any) -> None:
    corrida = leitura._corrida
    if corrida is not None:
        await corrida


async def _as_leituras_acabaram(servidor: IpcServer) -> None:
    for leitura in (servidor._pontes_lidas, servidor._marker_lido, servidor._perfil_mudo_lido,
                    servidor._motores_lidos, servidor._osk_lido):
        await _a_leitura_acabou(leitura)


async def _tiques_em_1_s(daemon: Any) -> int:
    antes = daemon.store.counter("poll.tick")
    await asyncio.sleep(1.0)
    return int(daemon.store.counter("poll.tick") - antes)


async def test_com_as_cinco_portas_dormindo_a_resposta_nao_espera(
    portas: _AsPortas, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    for disco in portas.todas():
        disco.dorme_s = DORME_S
    laco = asyncio.get_running_loop()
    maior_vao = [0.0]

    async def _batimento() -> None:
        anterior = laco.time()
        while True:
            await asyncio.sleep(0.01)
            maior_vao[0] = max(maior_vao[0], laco.time() - anterior)
            anterior = laco.time()

    batimento = asyncio.create_task(_batimento())
    t0 = time.perf_counter()
    await servidor._handle_daemon_state_full({})
    resposta_s = time.perf_counter() - t0
    await _as_leituras_acabaram(servidor)
    batimento.cancel()

    assert resposta_s < TETO_DA_RESPOSTA_S, f"a resposta esperou o disco: {resposta_s:.2f} s"
    assert maior_vao[0] < TETO_DA_RESPOSTA_S, f"o laço parou {maior_vao[0]:.2f} s"
    principal = threading.main_thread().name
    for disco in portas.todas():
        assert disco.fios, "a porta não foi lida"
        assert principal not in disco.fios, disco.fios


async def test_com_o_disco_do_handler_dormindo_o_tique_de_verdade_anda(
    portas: _AsPortas, tmp_path: Path
) -> None:
    """O marker fica de fora: o relógio `launch` ainda o lê no tique, e isso é outra sprint."""
    servidor = _servidor(tmp_path)
    daemon = servidor.daemon
    subida = asyncio.create_task(daemon.run())
    try:
        while daemon._reconnect_task is None:
            await asyncio.sleep(0.005)
        await servidor._handle_daemon_state_full({})
        await _as_leituras_acabaram(servidor)
        calmos = await _tiques_em_1_s(daemon)
        for disco in (portas.pontes, portas.perfis, portas.motores, portas.osk):
            disco.dorme_s = DORME_S
        servidor._pontes_lidas.esquecer()
        servidor._motores_lidos.esquecer()
        servidor._osk_lido.esquecer()
        servidor._perfil_mudo_lido.esquecer()

        await servidor._handle_daemon_state_full({})
        com_o_disco_dormindo = await _tiques_em_1_s(daemon)
        await _as_leituras_acabaram(servidor)
    finally:
        daemon.stop()
        await subida

    assert com_o_disco_dormindo >= calmos * 0.7, (
        f"o tique parou enquanto o disco dormia: {com_o_disco_dormindo} contra {calmos}")


def _a_resposta_da_porta(estado: dict[str, Any], porta: str) -> Any:
    if porta == "pontes":
        return estado["pontes_confirmadas"]
    if porta == "marker":
        return estado["gamepad_emulation"]["wrapper_used"]
    if porta == "motores":
        return estado["rumble_motores"]
    return estado["keyboard_emulation"]["osk_disponivel"]


@pytest.mark.parametrize(
    ("porta", "ttl", "velho", "novo", "antes", "depois"),
    [
        ("pontes", ih._PONTES_CONFIRMADAS_TTL_SEC, {"a": 1}, {"b": 2}, {"a": 1}, {"b": 2}),
        ("marker", ih._WRAPPER_MARKER_TTL_SEC, (9931993, None), None, True, False),
        (
            "motores", ih._MOTORES_DO_PERFIL_TTL_SEC, {"a": (10, 20)}, {"a": (30, 40)},
            {"a": {"forte_pct": 10, "fraco_pct": 20}}, {"a": {"forte_pct": 30, "fraco_pct": 40}},
        ),
        ("osk", ih._OSK_DISPONIVEL_TTL_SEC, True, False, True, False),
    ],
)
async def test_o_valor_velho_responde_enquanto_a_leitura_nova_corre(
    portas: _AsPortas, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    porta: str, ttl: float, velho: Any, novo: Any, antes: Any, depois: Any,
) -> None:
    disco: _Disco = getattr(portas, porta)
    disco.resposta = (9931993, int(time.time())) if porta == "marker" else velho
    servidor = _servidor(tmp_path)
    relogio = [1000.0]
    monkeypatch.setattr(ih.time, "monotonic", lambda: relogio[0])

    await servidor._handle_daemon_state_full({})
    await _as_leituras_acabaram(servidor)
    estado = await servidor._handle_daemon_state_full({})
    assert _a_resposta_da_porta(estado, porta) == antes

    disco.resposta = novo
    relogio[0] += ttl + 0.1
    estado = await servidor._handle_daemon_state_full({})
    assert _a_resposta_da_porta(estado, porta) == antes
    await _as_leituras_acabaram(servidor)
    estado = await servidor._handle_daemon_state_full({})
    assert _a_resposta_da_porta(estado, porta) == depois


async def test_a_janela_nova_nao_herda_o_aviso_da_janela_anterior(
    portas: _AsPortas, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    frases: dict[str, list[dict[str, str]]] = {
        "a.exe": [{"nome": "Do Jogo A", "frase": "x"}],
        "b.exe": [{"nome": "Do Jogo B", "frase": "y"}],
    }
    servidor._perfil_mudo_lido._ler = lambda _c, _n, exe: frases[exe]

    assert servidor._perfil_que_nao_entrou() == []
    await _a_leitura_acabou(servidor._perfil_mudo_lido)
    assert servidor._perfil_que_nao_entrou() == frases["a.exe"]

    servidor.store.record_window_detect_read("xlib", _JANELA, wm_name="Jogo", exe_basename="b.exe")
    assert servidor._perfil_que_nao_entrou() == []
    await _a_leitura_acabou(servidor._perfil_mudo_lido)
    assert servidor._perfil_que_nao_entrou() == frases["b.exe"]


async def test_a_janela_nova_nao_herda_o_aviso_quando_a_leitura_falha(
    portas: _AsPortas, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    aviso = [{"nome": "Do Jogo A", "frase": "x"}]

    def _ler(_classe: str, _nome: str, exe: str) -> list[dict[str, str]]:
        if exe == "b.exe":
            raise OSError(5, "Input/output error")
        return aviso

    servidor._perfil_mudo_lido._ler = _ler
    servidor._perfil_que_nao_entrou()
    await _a_leitura_acabou(servidor._perfil_mudo_lido)
    assert servidor._perfil_que_nao_entrou() == aviso

    servidor.store.record_window_detect_read("xlib", _JANELA, wm_name="Jogo", exe_basename="b.exe")
    servidor._perfil_que_nao_entrou()
    await _a_leitura_acabou(servidor._perfil_mudo_lido)

    assert servidor._perfil_que_nao_entrou() == []


async def test_a_falha_entra_no_diario_pelo_nome_da_leitura(
    portas: _AsPortas, tmp_path: Path
) -> None:
    """O serviço inteiro não vai ao diário: o `repr` de um método leva o objeto dele junto."""
    servidor = _servidor(tmp_path)
    portas.motores.levanta = OSError(5, "Input/output error")

    with capture_logs() as diario:
        await servidor._motores_lidos.em_dia(None)

    assert [e["leitor"] for e in diario if "leitor" in e] == ["_ler_os_motores"]


async def test_o_jogo_recem_focado_nao_e_chamado_de_sem_wrapper_antes_de_ler_o_marker(
    portas: _AsPortas, tmp_path: Path
) -> None:
    """«Não sei» é `None`, que a tela não acende; só o `False` diz que o jogo veio sem o atalho."""
    servidor = _servidor(tmp_path, gamepad_emulation_enabled=True)
    outro_jogo = (1111, int(time.time()) - 500)
    deste_jogo = portas.marker.resposta
    portas.marker.resposta = outro_jogo
    await servidor._marker_lido.em_dia()
    portas.marker.resposta = deste_jogo
    portas.marker.dorme_s = DORME_S / 10

    for _ in range(3):
        estado = await servidor._handle_daemon_state_full({})
        assert estado["gamepad_emulation"]["wrapper_used"] is None
        assert "jogo_sem_wrapper" not in estado["gamepad_emulation"].get("dedup_motivo", "")
    await _as_leituras_acabaram(servidor)
    estado = await servidor._handle_daemon_state_full({})

    assert estado["gamepad_emulation"]["wrapper_used"] is True


async def test_a_leitura_antiga_nao_vale_pela_que_o_foco_pediu(
    portas: _AsPortas, tmp_path: Path
) -> None:
    """Começada antes do foco, a leitura pode ser de antes de o lançador gravar o marker."""
    servidor = _servidor(tmp_path)
    deste_jogo = portas.marker.resposta
    portas.marker.resposta = None
    portas.marker.dorme_s = DORME_S / 10
    servidor._wrapper_marker_cached()
    await asyncio.sleep(0.05)
    portas.marker.resposta = deste_jogo

    assert servidor._wrapper_used_now() is None
    await _as_leituras_acabaram(servidor)
    assert servidor._wrapper_used_now() is None
    await _as_leituras_acabaram(servidor)

    assert servidor._wrapper_used_now() is True


class _OsQuatroNoCabo(FakeController):
    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": uniq, "transport": "usb", "connected": True} for uniq in _OS_QUATRO]


def _a_mesa_com_perfil(tmp_path: Path) -> IpcServer:
    servidor = _servidor(tmp_path, _OsQuatroNoCabo(transport="usb"))  # type: ignore[arg-type]
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    servidor.store.set_active_profile("Ensaio")
    return servidor


@pytest.mark.parametrize("uniq", _OS_QUATRO, ids=["P1", "P2", "P3", "P4"])
async def test_a_barra_gravada_ja_vale_no_estado_seguinte(tmp_path: Path, uniq: str) -> None:
    """A aba Vibração repinta do estado: a barra não pode voltar para onde estava."""
    servidor = _a_mesa_com_perfil(tmp_path)
    await servidor._motores_lidos.em_dia("Ensaio")

    resposta = await servidor._handlers["rumble.motores.set"]({"uniq": uniq, "fraco_pct": 40})
    estado = await servidor._handle_daemon_state_full({})

    assert resposta["gravado"] is True
    assert estado["rumble_motores"][resposta["uniq"].replace(":", "")]["fraco_pct"] == 40


async def test_a_leitura_em_curso_nao_desfaz_a_barra_gravada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leitura presa no disco acaba depois da gravação e não pode ficar valendo."""
    servidor = _a_mesa_com_perfil(tmp_path)
    await servidor._motores_lidos.em_dia("Ensaio")
    real = loader.load_profile
    lendo, solta = threading.Event(), threading.Event()
    presa = [True]

    def _presa_no_disco(*a: Any, **k: Any) -> Any:
        perfil = real(*a, **k)
        if presa[0] and threading.current_thread() is not threading.main_thread():
            presa[0] = False
            lendo.set()
            solta.wait(5)
        return perfil

    monkeypatch.setattr(loader, "load_profile", _presa_no_disco)
    servidor.daemon._rumble_motores_pct = None
    servidor._motores_lidos.esquecer()
    servidor._motores_lidos.agora("Ensaio")
    assert await asyncio.to_thread(lendo.wait, 5)

    gesto = asyncio.ensure_future(
        servidor._handlers["rumble.motores.set"]({"uniq": _OS_QUATRO[0], "fraco_pct": 40}))
    await asyncio.sleep(0.2)
    solta.set()
    resposta = await gesto
    estado = await servidor._handle_daemon_state_full({})

    assert estado["rumble_motores"][resposta["uniq"].replace(":", "")]["fraco_pct"] == 40
    assert gamepad._motores_do_perfil_ativo(servidor.daemon)[
        resposta["uniq"].replace(":", "")] == (100, 40)


async def test_cem_perguntas_com_a_leitura_correndo_sao_uma_leitura(
    portas: _AsPortas, tmp_path: Path
) -> None:
    portas.pontes.dorme_s = 0.2
    servidor = _servidor(tmp_path)

    for _ in range(100):
        servidor._pontes_confirmadas_no_tique()
        await asyncio.sleep(0)
    await _a_leitura_acabou(servidor._pontes_lidas)

    assert len(portas.pontes.fios) == 1


async def test_a_leitura_que_falha_guarda_o_valor_e_espera_a_validade(
    portas: _AsPortas, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servidor = _servidor(tmp_path)
    relogio = [1000.0]
    monkeypatch.setattr(ih.time, "monotonic", lambda: relogio[0])
    servidor._pontes_confirmadas_no_tique()
    await _a_leitura_acabou(servidor._pontes_lidas)
    bom = dict(portas.pontes.resposta)

    portas.pontes.levanta = OSError(5, "Input/output error")
    relogio[0] += ih._PONTES_CONFIRMADAS_TTL_SEC + 0.1
    servidor._pontes_confirmadas_no_tique()
    await _a_leitura_acabou(servidor._pontes_lidas)
    for _ in range(5):
        assert servidor._pontes_confirmadas_no_tique() == bom
        await _a_leitura_acabou(servidor._pontes_lidas)

    assert len(portas.pontes.fios) == 2


async def test_o_servico_de_pe_aquece_o_que_a_primeira_janela_le(
    portas: _AsPortas, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A janela que abre depois da subida não vê um «sem ponte» de um quadro."""
    from hefesto_dualsense4unix.daemon import subsystems

    async def _subir_ipc(_daemon: Any) -> None:
        return None

    monkeypatch.setattr(subsystems.ipc, "start_ipc", _subir_ipc)
    servidor = _servidor(tmp_path)

    await servidor.daemon._start_ipc()
    await _as_leituras_acabaram(servidor)

    assert servidor._pontes_confirmadas_no_tique() == portas.pontes.resposta
    assert servidor._wrapper_marker_cached() == portas.marker.resposta
    assert servidor._osk_lido.agora() is True


async def test_o_ping_do_lancamento_ve_o_marker_de_agora(
    portas: _AsPortas, tmp_path: Path
) -> None:
    """O jogo acaba de abrir: o marker do disco vale no próprio ping, sem esperar a validade."""
    servidor = _servidor(tmp_path)
    armou: list[bool] = []

    async def _armar() -> None:
        armou.append(True)

    servidor._armar_launch = _armar  # type: ignore[method-assign]
    portas.marker.resposta = None
    await servidor._marker_lido.em_dia()
    assert servidor._wrapper_marker_cached() is None

    portas.marker.resposta = (9931993, int(time.time()))
    await servidor._handle_daemon_status({})
    await asyncio.sleep(0)

    assert armou == [True]


class _AMesa(FakeController):
    def __init__(self, vias: tuple[str, ...]) -> None:
        super().__init__(transport=vias[0])  # type: ignore[arg-type]
        self.vias = vias

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {"uniq": uniq, "transport": via, "connected": via != "fora"}
            for uniq, via in zip(_OS_QUATRO, self.vias, strict=True)
        ]


@pytest.mark.parametrize("modo", _OS_MODOS)
@pytest.mark.parametrize(
    "vias",
    [*_AS_MESAS.values(), ("fora", "fora", "usb", "fora"), ("fora", "fora", "bt", "fora")],
    ids=[*_AS_MESAS, "só o P3 no cabo", "só o P3 no rádio"],
)
async def test_toda_mesa_sai_da_mesma_leitura(
    portas: _AsPortas, tmp_path: Path, vias: tuple[str, ...], modo: str
) -> None:
    portas.pontes.resposta = {uniq: "ponte" for uniq in _OS_QUATRO}
    portas.motores.resposta = {uniq: (60, 40) for uniq in _OS_QUATRO}
    servidor = _servidor(tmp_path, _AMesa(vias), **_OS_MODOS[modo])
    servidor.daemon._native_mode = modo == "nativo"

    await servidor._handle_daemon_state_full({})
    await _as_leituras_acabaram(servidor)
    for _ in range(10):
        estado = await servidor._handle_daemon_state_full({})

    assert [c["uniq"] for c in estado["controllers"]] == list(_OS_QUATRO)
    assert set(estado["pontes_confirmadas"]) == set(_OS_QUATRO)
    assert set(estado["rumble_motores"]) == set(_OS_QUATRO)
    assert len(portas.pontes.fios) == 1
    assert len(portas.motores.fios) == 1
    assert len(portas.marker.fios) == 1
    assert estado["gamepad_emulation"]["wrapper_used"] is True


_TOCA_ARQUIVO = frozenset({
    "access", "exists", "glob", "is_dir", "is_file", "is_symlink", "isdir", "isfile", "iterdir",
    "listdir", "lstat", "mkdir", "open", "read_bytes", "read_text", "readlink", "resolve", "rglob",
    "samefile", "scandir", "stat", "touch", "walk", "which", "write_bytes", "write_text",
})
_FORA_DO_EXT4 = {
    "hefesto_dualsense4unix.core.sysfs_leds.SysfsLedNode._brightness_lido": "/sys",
    "hefesto_dualsense4unix.core.sysfs_leds.SysfsLedNode.get_rgb": "/sys",
    "hefesto_dualsense4unix.daemon.ipc_handlers.dualsense_sem_driver": "/sys",
    "hefesto_dualsense4unix.integrations.no_do_vpad._candidatos": "/dev e /sys",
    "hefesto_dualsense4unix.integrations.no_do_vpad._hidraw_do_no": "/sys",
    "hefesto_dualsense4unix.integrations.no_do_vpad._inode": "/dev",
    "hefesto_dualsense4unix.integrations.no_do_vpad._texto_do_sysfs": "/sys",
    "hefesto_dualsense4unix.utils.texto_do_sysfs.ler_texto": "/sys",
}


def _o_que_o_handler_alcanca() -> dict[str, list[str]]:
    grafo = _Grafo(_SRC)
    inicio = "hefesto_dualsense4unix.daemon.ipc_handlers.IpcHandlersMixin._handle_daemon_state_full"
    vindo_de: dict[str, str | None] = {inicio: None}
    fila = deque([inicio])
    while fila:
        chave = fila.popleft()
        funcao = grafo.funcoes[chave]
        for chamada, e_chamada in grafo._chamadas(funcao):
            for alvo in grafo._resolver(funcao, chamada, e_chamada):
                if alvo.chave not in vindo_de:
                    vindo_de[alvo.chave] = chave
                    fila.append(alvo.chave)
    achados: dict[str, list[str]] = {}
    for chave in vindo_de:
        funcao = grafo.funcoes[chave]
        for chamada, e_chamada in grafo._chamadas(funcao):
            nome = chamada.attr if isinstance(chamada, ast.Attribute) else None
            nome = nome or getattr(chamada, "id", None)
            if e_chamada and nome in _TOCA_ARQUIVO:
                caminho = [chave]
                passo = vindo_de[chave]
                while passo is not None:
                    caminho.append(passo)
                    passo = vindo_de[passo]
                achados[chave] = caminho
    return achados


def test_nada_que_o_handler_alcanca_toca_o_ext4() -> None:
    """Pelo grafo das chamadas, do handler até a primitiva: só `/sys` e `/dev` ficam no laço."""
    achados = _o_que_o_handler_alcanca()

    novos = {chave: caminho for chave, caminho in achados.items() if chave not in _FORA_DO_EXT4}

    assert not novos, "o `state_full` alcança o disco no fio do laço:\n" + "\n".join(
        " <- ".join(p.rsplit(".", 1)[-1] for p in caminho) for caminho in novos.values()
    )
    assert sorted(set(_FORA_DO_EXT4) - set(achados)) == [], "saiu do laço: tire de `_FORA_DO_EXT4`"


def test_o_instrumento_do_ext4_pergunta_o_que_a_regua_nao_ve() -> None:
    sonda = (_SRC.parent / "scripts/ensaios/o_laco_toca_o_ext4.bt").read_text(encoding="utf-8")

    for ponto in ("ext4_file_read_iter", "ext4_file_write_iter", "ext4_lookup", "ext4_readdir",
                  "ext4_getattr", "ext4_sync_file", "ext4_rename2", "handle_mm_fault"):
        assert f":{ponto} /tid == $1" in sonda
