"""O laço do daemon não grava perfil nem espera o systemctl.

Sprint O-LACO-DO-DAEMON-NAO-GRAVA-PERFIL-NEM-ESPERA-O-SYSTEMCTL-01.

Medido em 31/10/2026: o carimbo da escada (``tique_da_escada``), o ``mira.set``, as três seções da
acessibilidade e o ``start_autoswitch`` gravavam o perfil ou rodavam o ``systemctl --user`` no fio
do laço asyncio. Cada régua dubla a gravação (ou o ``systemctl``) para dormir ``DORME_S`` e mede
que o laço segue atendendo: o tique volta antes de ``TETO_TIQUE_S``, e o ``daemon.status``
responde com a gravação ainda dormindo. A última régua lista, por ``ast``, os ``async def`` do
daemon que alcançam um ``save_profile`` ou um ``subprocess`` sem passar por ``asyncio.to_thread``.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``).
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from collections.abc import Coroutine, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import ponte_escada, ponte_tentativa
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

DORME_S = 0.8
TETO_TIQUE_S = 0.05
TETO_IPC_S = 0.4
APPID = 9931101
JOGO = "Jogo da Régua do Laço"
_P1 = "aa:bb:cc:00:00:01"
_P2 = "aa:bb:cc:00:00:02"
_SRC = Path(__file__).resolve().parents[2] / "src"


class _GravacaoLenta:
    """O ``save_profile`` de verdade, depois de dormir ``DORME_S``; anota o fio de quem gravou."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.fios: list[str] = []

    def ligar(self) -> None:
        from hefesto_dualsense4unix.profiles import manager

        real = loader.save_profile

        def lento(*args: Any, **kwargs: Any) -> Path:
            self.fios.append(threading.current_thread().name)
            time.sleep(DORME_S)
            return real(*args, **kwargs)

        self._monkeypatch.setattr(loader, "save_profile", lento)
        self._monkeypatch.setattr(manager, "save_profile", lento)


@pytest.fixture
def gravacao_lenta(monkeypatch: pytest.MonkeyPatch) -> _GravacaoLenta:
    return _GravacaoLenta(monkeypatch)


@pytest.fixture
def sem_escrevente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    yield
    escrevente = le._ESCREVENTE
    if escrevente is not None:
        le.desarmar_o_escrevente(escrevente)


def _daemon() -> Any:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    return Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())


def _servidor(tmp_path: Path) -> Any:
    """O ``Daemon`` e o ``IpcServer`` do produto, com o perfil «Ensaio» ativo no disco."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "laco.sock", daemon=daemon)
    daemon._ipc_server = servidor
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    servidor.store.set_active_profile("Ensaio")
    return servidor


async def _o_status_durante(
    servidor: Any, coro: Coroutine[Any, Any, Any]
) -> tuple[float, bool, Any]:
    """Põe ``coro`` no laço e pede o ``daemon.status``: o tempo, se ainda corria, e o fim."""
    t0 = time.perf_counter()
    tarefa = asyncio.ensure_future(coro)
    await asyncio.sleep(0.05)
    await servidor._handlers["daemon.status"]({})
    gasto = time.perf_counter() - t0
    corria = not tarefa.done()
    return gasto, corria, await tarefa


def _jogo_vivo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "launch_session_appid", lambda **_kw: APPID)
    monkeypatch.setattr(le, "_jogo_na_autoridade", lambda _d: True)
    monkeypatch.setattr(le, "steam_input_appids", lambda *_a, **_kw: set())


def _perfil_do_jogo() -> None:
    loader.save_profile(Profile(
        name=JOGO,
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
    ))


def _guardar_o_gesto(daemon: Any) -> None:
    ponte_tentativa._guardar_o_gesto(daemon, ponte_tentativa.GestoDoUsuario(
        appid=APPID,
        ponte=ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, "xbox"),
        ultimo_gesto=0.0,
        gestos=1,
    ))


def test_o_tique_da_escada_que_carimba_volta_ao_laco_na_hora(
    sem_escrevente: None, gravacao_lenta: _GravacaoLenta, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O tique decide no laço e entrega o carimbo ao escrevente; o perfil sai gravado por ele.

    MORDIDA: devolva a gravação do carimbo ao ``tique_da_escada`` e o tique dorme no laço.
    """
    _jogo_vivo(monkeypatch)
    _perfil_do_jogo()
    daemon = _daemon()
    _guardar_o_gesto(daemon)
    gravacao_lenta.ligar()

    async def corpo() -> tuple[float, Any]:
        laco = asyncio.get_running_loop()
        escrevente = le.armar_o_escrevente(laco.call_soon_threadsafe, laco)
        assert escrevente is not None
        t0 = time.perf_counter()
        le.tique_da_escada(daemon, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 1.0)
        gasto = time.perf_counter() - t0
        _guardar_o_gesto(daemon)
        le.tique_da_escada(daemon, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 2.0)
        await asyncio.to_thread(le.desarmar_o_escrevente, escrevente, DORME_S * 3)
        return gasto, escrevente

    gasto, _escrevente = asyncio.run(corpo())
    assert gasto < TETO_TIQUE_S, f"o tique da escada ficou {gasto:.2f} s no laço gravando o carimbo"
    assert gravacao_lenta.fios == ["hefesto-lancamento"], (
        f"o carimbo não foi gravado uma vez, pelo escrevente: {gravacao_lenta.fios}")
    perfil = loader.load_profile(JOGO)
    assert perfil.ponte is not None, "o escrevente terminou e o carimbo não está no disco"
    assert (perfil.ponte.kind, perfil.ponte.gamepad_flavor) == ("gamepad", "xbox")


def test_fora_do_laco_o_tique_carimba_na_hora(
    sem_escrevente: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem escrevente armado (a CLI, os testes de fio), o carimbo grava antes do tique voltar."""
    _jogo_vivo(monkeypatch)
    _perfil_do_jogo()
    daemon = _daemon()
    _guardar_o_gesto(daemon)
    le.tique_da_escada(daemon, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 1.0)
    perfil = loader.load_profile(JOGO)
    assert perfil.ponte is not None and perfil.ponte.gamepad_flavor == "xbox"


_ACESSIBILIDADE = (
    ("perfil.ativacao.set", {"uniq": _P1, "alternar": ["cross"]}),
    ("perfil.analogicos.set", {"uniq": _P1, "zona_morta": 12}),
    ("perfil.cursor.set", {"precisao": 55}),  # (noqa-acento)
)


@pytest.mark.parametrize(
    ("pedido", "params"),
    [("mira.set", {"uniq": _P1, "sensibilidade": 7}), *_ACESSIBILIDADE],
    ids=["mira", "alternar", "zona-morta", "cursor"],
)
def test_o_handler_que_grava_deixa_o_laco_atender_outro_ipc(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta, pedido: str, params: dict[str, Any]
) -> None:
    """Com a gravação dormindo, o ``daemon.status`` responde, e a resposta do handler é a mesma.

    MORDIDA: tire o ``asyncio.to_thread`` do handler e o ``daemon.status`` espera ``DORME_S``.
    """
    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    gasto, corria, corpo = asyncio.run(
        _o_status_durante(servidor, servidor._handlers[pedido](dict(params))))

    assert corpo["status"] == "ok" and corpo["gravado"] is True, corpo
    assert gasto < TETO_IPC_S and corria, (
        f"o `{pedido}` parou o laço {gasto:.2f} s gravando o perfil")
    assert len(gravacao_lenta.fios) == 1 and gravacao_lenta.fios != ["MainThread"], (
        gravacao_lenta.fios)
    assert loader.load_profile("Ensaio") != Profile(name="Ensaio", match=MatchAny(type="any"))


def test_dois_handlers_seguidos_nao_perdem_a_gravacao_um_do_outro(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta
) -> None:
    """Duas gravações no mesmo perfil, uma em cima da outra: o disco guarda as duas."""
    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    async def corpo() -> None:
        await asyncio.gather(
            servidor._handlers["mira.set"]({"uniq": _P1, "sensibilidade": 7}),
            servidor._handlers["perfil.cursor.set"]({"precisao": 55}),  # (noqa-acento)
        )

    asyncio.run(corpo())
    perfil = loader.load_profile("Ensaio")
    chave = _P1.replace(":", "")
    movimento = perfil.controllers[chave].movimento
    assert movimento is not None and movimento.sensibilidade_h == 6
    assert perfil.cursor.precisao == 55


def test_o_start_autoswitch_nao_espera_o_systemctl_no_laco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``systemctl --user show-environment`` dormindo e o ``daemon.status`` respondendo.

    MORDIDA: chame o ``_ensure_display_env`` direto no ``start_autoswitch`` e o status espera.
    """
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch

    for chave in autoswitch._VARIAVEIS_DO_DISPLAY:
        monkeypatch.setenv(chave, "")
        monkeypatch.delenv(chave)
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT", "1")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
        lambda: (lambda: {}),
    )
    monkeypatch.setattr("shutil.which", lambda nome: f"/usr/bin/{nome}")
    real = subprocess.run
    perguntas: list[list[str]] = []

    def systemctl_lento(argv: Any, *args: Any, **kwargs: Any) -> Any:
        if not (isinstance(argv, list) and argv and argv[0] == "/usr/bin/systemctl"):
            return real(argv, *args, **kwargs)
        perguntas.append(list(argv))
        time.sleep(DORME_S)
        return SimpleNamespace(stdout="DISPLAY=:91\n", returncode=0)

    monkeypatch.setattr(subprocess, "run", systemctl_lento)
    servidor = _servidor(tmp_path)

    gasto, corria, _ = asyncio.run(
        _o_status_durante(servidor, autoswitch.start_autoswitch(servidor.daemon)))

    assert perguntas == [["/usr/bin/systemctl", "--user", "show-environment"]], perguntas
    assert gasto < TETO_IPC_S and corria, (
        f"o start_autoswitch parou o laço {gasto:.2f} s esperando o systemctl")
    assert os.environ.get("DISPLAY") == ":91"
    assert servidor.daemon._autoswitch is not None


_FORA_DO_LACO = frozenset({"to_thread", "run_in_executor", "Thread", "submit"})
_SUBPROCESSO = frozenset({"run", "Popen", "check_output", "check_call", "call"})
_GENERICOS = frozenset(
    nome
    for tipo in (dict, list, str, set, bytes, int, float, tuple, frozenset, object, Path,
                 asyncio.Event, asyncio.Queue, asyncio.AbstractEventLoop, asyncio.Task,
                 subprocess.Popen)
    for nome in dir(tipo)
) | frozenset({"start", "stop", "join", "close", "wait", "set", "clear", "acquire", "release"})
_BARREIRAS = {
    "hefesto_dualsense4unix.profiles.loader._talvez_semear_jogos": "_no_laco_do_servico()",
    "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env": "escrevente.atende_aqui()",
    "hefesto_dualsense4unix.daemon.launch_env.tique_da_escada": "escrevente.atende_aqui()",
}
_AINDA_NO_LACO: dict[str, str] = {}


class _Funcao:
    def __init__(self, modulo: str, nome: str, no: ast.AST, classe: str | None) -> None:
        self.modulo, self.nome, self.no, self.classe = modulo, nome, no, classe
        self.assincrona = isinstance(no, ast.AsyncFunctionDef)
        self.sumidouro: str | None = None

    @property
    def chave(self) -> str:
        return f"{self.modulo}.{self.nome}"


class _Grafo:
    """As funções do pacote e quem chama quem, resolvido por nome, import, ``self`` e módulo."""

    def __init__(self, raiz: Path) -> None:
        self.funcoes: dict[str, _Funcao] = {}
        self.por_nome: dict[str, list[_Funcao]] = defaultdict(list)
        self.imports: dict[str, dict[str, tuple[str, str | None]]] = {}
        for caminho in sorted((raiz / "hefesto_dualsense4unix").rglob("*.py")):
            partes = list(caminho.relative_to(raiz).with_suffix("").parts)
            if partes[-1] == "__init__":
                partes.pop()
            self._ler(".".join(partes), ast.parse(caminho.read_text(encoding="utf-8")))
        self.chamadores: dict[str, set[str]] = defaultdict(set)
        for funcao in self.funcoes.values():
            for chamada, e_chamada in self._chamadas(funcao):
                funcao.sumidouro = funcao.sumidouro or self._sumidouro(funcao, chamada, e_chamada)
                for alvo in self._resolver(funcao, chamada, e_chamada):
                    self.chamadores[alvo.chave].add(funcao.chave)

    def _ler(self, modulo: str, arvore: ast.Module) -> None:
        tabela: dict[str, tuple[str, str | None]] = {}
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module:
                base = no.module
                if no.level:
                    base = ".".join([*modulo.split(".")[: -no.level], no.module])
                for nome in no.names:
                    tabela[nome.asname or nome.name] = (base, nome.name)
            elif isinstance(no, ast.Import):
                for nome in no.names:
                    if nome.asname:
                        tabela[nome.asname] = (nome.name, None)
                    else:
                        tabela[nome.name.split(".")[0]] = (nome.name.split(".")[0], None)
        self.imports[modulo] = tabela

        def visitar(no: ast.AST, prefixo: str, classe: str | None) -> None:
            for filho in ast.iter_child_nodes(no):
                if isinstance(filho, ast.ClassDef):
                    visitar(filho, f"{prefixo}{filho.name}.", filho.name)
                elif isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcao = _Funcao(modulo, f"{prefixo}{filho.name}", filho, classe)
                    self.funcoes[funcao.chave] = funcao
                    self.por_nome[filho.name].append(funcao)
                    visitar(filho, f"{funcao.nome}.", classe)
                else:
                    visitar(filho, prefixo, classe)

        visitar(arvore, "", None)

    @staticmethod
    def _chamadas(funcao: _Funcao) -> Iterator[tuple[ast.expr, bool]]:
        locais = {
            filho.name for filho in ast.iter_child_nodes(funcao.no)
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        pilha = list(ast.iter_child_nodes(funcao.no))
        while pilha:
            no = pilha.pop()
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(no, ast.Return) and isinstance(no.value, ast.Name):
                continue
            if isinstance(no, ast.Call):
                alvo = no.func
                nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", None)
                if nome in _FORA_DO_LACO:
                    continue
                yield alvo, True
                pilha.extend(ast.iter_child_nodes(no))
                continue
            if isinstance(no, ast.Name) and no.id in locais and isinstance(no.ctx, ast.Load):
                yield no, False
            pilha.extend(ast.iter_child_nodes(no))

    def _sumidouro(self, funcao: _Funcao, alvo: ast.expr, e_chamada: bool) -> str | None:
        if not e_chamada:
            return None
        tabela = self.imports[funcao.modulo]
        if isinstance(alvo, ast.Attribute) and isinstance(alvo.value, ast.Name):
            base = tabela.get(alvo.value.id, (alvo.value.id, None))
            if base == ("subprocess", None) and alvo.attr in _SUBPROCESSO:
                return f"subprocess.{alvo.attr}"
            if base == ("os", None) and alvo.attr == "system":
                return "os.system"
        if isinstance(alvo, ast.Name):
            base, nome = tabela.get(alvo.id, ("", None))
            if base == "subprocess" and nome in _SUBPROCESSO:
                return f"subprocess.{nome}"
        return None

    def _resolver(self, funcao: _Funcao, alvo: ast.expr, e_chamada: bool) -> list[_Funcao]:
        tabela = self.imports[funcao.modulo]
        if isinstance(alvo, ast.Name):
            aninhada = self.funcoes.get(f"{funcao.chave}.{alvo.id}")
            if aninhada is not None:
                return [aninhada]
            if not e_chamada:
                return []
            do_modulo = self.funcoes.get(f"{funcao.modulo}.{alvo.id}")
            if do_modulo is not None:
                return [do_modulo]
            base, nome = tabela.get(alvo.id, ("", None))
            importada = self.funcoes.get(f"{base}.{nome}") if nome else None
            return [importada] if importada is not None else []
        if not isinstance(alvo, ast.Attribute):
            return []
        if isinstance(alvo.value, ast.Name):
            dono = alvo.value.id
            if dono in ("self", "cls"):
                mesma = [g for g in self.por_nome[alvo.attr]
                         if g.modulo == funcao.modulo and g.classe == funcao.classe]
                if mesma:
                    return mesma
            elif dono in tabela:
                base, nome = tabela[dono]
                modulo = f"{base}.{nome}" if nome else base
                do_modulo = self.funcoes.get(f"{modulo}.{alvo.attr}")
                if do_modulo is not None:
                    return [do_modulo]
        candidatas = [g for g in self.por_nome[alvo.attr] if g.classe is not None]
        if alvo.attr in _GENERICOS or len(candidatas) != 1:
            return []
        return candidatas

    def caminhos_ate_o_sumidouro(self) -> dict[str, list[str]]:
        salvar = self.funcoes["hefesto_dualsense4unix.profiles.loader.save_profile"]
        salvar.sumidouro = "save_profile"
        caminho: dict[str, list[str]] = {}
        fila: deque[str] = deque()
        for chave, funcao in self.funcoes.items():
            if funcao.sumidouro:
                caminho[chave] = [f"{funcao.nome} ({funcao.sumidouro})"]
                fila.append(chave)
        while fila:
            chave = fila.popleft()
            if self.funcoes[chave].assincrona or chave in _BARREIRAS:
                continue
            for quem in self.chamadores[chave]:
                if quem not in caminho:
                    caminho[quem] = [self.funcoes[quem].nome, *caminho[chave]]
                    fila.append(quem)
        return {
            chave: passos for chave, passos in caminho.items()
            if self.funcoes[chave].assincrona
            and chave.startswith("hefesto_dualsense4unix.daemon.")
        }


@pytest.fixture(scope="module")
def grafo() -> _Grafo:
    return _Grafo(_SRC)


def test_as_barreiras_da_regua_seguem_de_pe(grafo: _Grafo) -> None:
    """A régua só corta onde a função confere o laço; tirar a conferência derruba a barreira."""
    for chave, guarda in _BARREIRAS.items():
        assert guarda in ast.unparse(grafo.funcoes[chave].no), (
            f"`{chave}` não confere mais o laço (`{guarda}`): a régua não pode cortar ali")


def test_nenhum_async_do_daemon_alcanca_gravacao_ou_processo_sem_to_thread(
    grafo: _Grafo,
) -> None:
    """Zero chamadores proibidos fora de ``_AINDA_NO_LACO``, e nenhum declarado já curado.

    MORDIDA: tire o ``asyncio.to_thread`` de um handler e ele entra na lista.
    """
    achados = grafo.caminhos_ate_o_sumidouro()
    novos = {
        chave: " -> ".join(passos)
        for chave, passos in sorted(achados.items()) if chave not in _AINDA_NO_LACO
    }
    curados = sorted(set(_AINDA_NO_LACO) - set(achados))
    assert not novos, "async def do daemon gravando o perfil ou rodando processo no laço:\n" + (
        "\n".join(f"{chave}: {caminho}" for chave, caminho in novos.items()))
    assert not curados, f"saíram do laço; tire de `_AINDA_NO_LACO`: {curados}"


class _Espiao:
    """A função de verdade trocada por uma que dorme ``DORME_S``, e anota o fio de cada chamada."""

    def __init__(self, resposta: Any = None) -> None:
        self.resposta = resposta
        self.fios: list[str] = []

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        self.fios.append(threading.current_thread().name)
        time.sleep(DORME_S)
        return self.resposta


def _o_fio_do_laco_nao_rodou(espiao: _Espiao) -> None:
    assert espiao.fios, "a chamada lenta não aconteceu"
    assert threading.main_thread().name not in espiao.fios, espiao.fios


def _perfil_com_ganho() -> None:
    chave = _P1.replace(":", "")
    loader.save_profile(Profile(
        name="Com Ganho", match=MatchAny(type="any"),
        controllers={chave: ControllerOverrides(mic=ControllerMicOverride(gain=62))},
    ))


def test_o_profile_switch_com_ganho_responde_enquanto_o_amixer_dorme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ativação só pede o ganho: o `amixer` dorme em fio próprio e o laço segue atendendo.

    MORDIDA: chame o ``definir`` direto em ``_aplicar_ganho_do_mic``, e o status espera.
    """
    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.integrations import ganho_do_microfone
    from hefesto_dualsense4unix.profiles.manager import PEDIDOS_DO_GANHO

    amixer = _Espiao("Capture 'x' [50%] [-3.00dB]")
    monkeypatch.setattr(ganho_do_microfone, "placa_do_controle", lambda *_a: "9")
    monkeypatch.setattr(audio_saida, "rodar_leitura", amixer)
    servidor = _servidor(tmp_path)
    servidor.profile_manager.mic_applier = lambda *_a, **_k: "aplicado"
    _perfil_com_ganho()

    gasto, _corria, _resposta = asyncio.run(_o_status_durante(
        servidor, servidor._handlers["profile.switch"]({"name": "Com Ganho"})))

    assert gasto < TETO_IPC_S, f"o profile.switch parou o laço {gasto:.2f} s"
    assert PEDIDOS_DO_GANHO.esperar(DORME_S * 8)
    _o_fio_do_laco_nao_rodou(amixer)
    assert set(amixer.fios) == {"hefesto-ganho-do-mic"}, amixer.fios


def test_o_pedido_mais_novo_de_cada_controle_vence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quatro pedidos de dois controles enquanto o primeiro dorme: só os últimos saem."""
    from hefesto_dualsense4unix.integrations import ganho_do_microfone
    from hefesto_dualsense4unix.profiles.manager import _PedidosDoGanho

    solta = threading.Event()
    feitos: list[tuple[str, int]] = []

    def definir(uniq: str, por_cento: int, _mesa: Any) -> tuple[int, float]:
        solta.wait(5.0)
        feitos.append((uniq, por_cento))
        return por_cento, 0.0

    monkeypatch.setattr(ganho_do_microfone, "definir", definir)
    pedidos = _PedidosDoGanho()
    pedidos.pedir("a", 1)
    time.sleep(0.05)
    for uniq, por_cento in (("a", 2), ("b", 3), ("a", 4), ("b", 5)):
        pedidos.pedir(uniq, por_cento)
    solta.set()

    assert pedidos.esperar(5.0)
    assert sorted(feitos) == [("a", 1), ("a", 4), ("b", 5)], feitos


def test_os_quatro_controles_pedem_o_ganho_de_cada_um(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ganho é por controle: ninguém fica de fora, e o estado volta no relatório de cada um.

    MORDIDA: faça o `_esvaziar` servir só o primeiro pedido.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import mensagem_de_ativacao
    from hefesto_dualsense4unix.integrations import ganho_do_microfone
    from hefesto_dualsense4unix.profiles.manager import GANHO_PEDIDO, PEDIDOS_DO_GANHO

    feitos: list[tuple[str, int]] = []
    monkeypatch.setattr(
        ganho_do_microfone, "definir",
        lambda uniq, pct, _mesa: feitos.append((uniq, pct)) or (pct, 0.0),
    )
    servidor = _servidor(tmp_path)
    servidor.profile_manager.mic_applier = lambda *_a, **_k: "aplicado"
    ganhos = {f"aabbcc00000{n}": 10 * n for n in (1, 2, 3, 4)}
    perfil = Profile(
        name="Os Quatro", match=MatchAny(type="any"),
        controllers={uniq: ControllerOverrides(mic=ControllerMicOverride(gain=ganho))
                     for uniq, ganho in ganhos.items()},
    )

    relatorio = servidor.profile_manager.apply_controller_mics(perfil)

    assert PEDIDOS_DO_GANHO.esperar(5.0)
    assert dict(feitos) == ganhos, feitos
    assert all(relatorio[f"mic:{uniq}"] == GANHO_PEDIDO for uniq in ganhos), relatorio
    assert mensagem_de_ativacao("Os Quatro", {"secoes": relatorio}) == "Perfil ativado: Os Quatro"


def test_o_volume_da_captura_nao_para_o_laco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: tire o ``asyncio.to_thread`` do ``definir_volume_da_captura`` no handler."""
    from hefesto_dualsense4unix.integrations import audio_control

    definir = _Espiao(True)
    monkeypatch.setattr(audio_control, "fonte_de_captura_do_uniq", lambda *_a, **_k: "fonte")
    monkeypatch.setattr(audio_control, "definir_volume_da_captura", definir)
    monkeypatch.setattr(audio_control, "volume_da_captura", lambda **_k: 40)
    servidor = _servidor(tmp_path)

    gasto, corria, resposta = asyncio.run(_o_status_durante(
        servidor, servidor._handlers["mic.volume.set"]({"volume": 40, "uniq": _P1})))

    assert gasto < TETO_IPC_S and corria, f"o mic.volume.set parou o laço {gasto:.2f} s"
    assert resposta["status"] == "ok"
    _o_fio_do_laco_nao_rodou(definir)


@pytest.mark.parametrize(
    ("chamada", "params"),
    [
        ("rumble.motores.set", {"uniq": _P1, "fraco_pct": 40}),
        ("sensor.set", {"uniq": _P1, "giroscopio": False}),
    ],
)
def test_o_gesto_que_grava_nao_para_o_laco(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta, chamada: str, params: dict[str, Any],
) -> None:
    """MORDIDA: chame o ``gravar_pelo_gesto`` direto no handler, e o status espera a gravação."""
    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    gasto, corria, _resposta = asyncio.run(
        _o_status_durante(servidor, servidor._handlers[chamada](dict(params))))

    assert gasto < TETO_IPC_S and corria, f"{chamada} parou o laço {gasto:.2f} s"
    assert gravacao_lenta.fios and threading.main_thread().name not in gravacao_lenta.fios


def test_dois_gestos_no_mesmo_perfil_nao_perdem_um_ao_outro(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta,
) -> None:
    """Fora do laço a ordem deixa de ser de graça: a trava é que guarda as duas gravações.

    MORDIDA: troque ``sob_a_trava_do_perfil`` por uma chamada direta nos dois handlers.
    """
    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    async def corpo() -> None:
        await asyncio.gather(
            servidor._handlers["rumble.motores.set"]({"uniq": _P1, "fraco_pct": 40}),
            servidor._handlers["sensor.set"]({"uniq": _P1, "giroscopio": False}),
        )

    asyncio.run(corpo())
    controles = loader.load_profile("Ensaio").controllers
    dele = controles[_P1.replace(":", "")]
    assert dele.rumble is not None and dele.sensores is not None, dele


def test_o_modo_escolhido_no_laco_grava_no_fio_do_perfil(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta,
) -> None:
    """O gesto de modo no fio do laço não espera o disco, e o modo chega ao perfil, em ordem.

    MORDIDA: em ``gravar_o_modo_escolhido``, espere o ``feito.result()`` também no laço.
    """
    from hefesto_dualsense4unix.profiles.manager import FIO_DO_PERFIL

    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    async def corpo() -> float:
        t0 = time.perf_counter()
        servidor.daemon.gravar_o_modo_escolhido("gamepad", caminho="xbox", mascara="xbox",
                                                porta="ipc")
        servidor.daemon.gravar_o_modo_escolhido("gamepad", caminho="dualsense",
                                                mascara="dualsense", porta="ipc")
        return time.perf_counter() - t0

    gasto = asyncio.run(corpo())
    FIO_DO_PERFIL.submit(lambda: None).result(timeout=DORME_S * 6)

    assert gasto < TETO_TIQUE_S, f"o gesto esperou o disco {gasto:.3f} s no laço"
    assert all(nome.startswith("hefesto-perfil") for nome in gravacao_lenta.fios)
    assert loader.load_profile("Ensaio").mode.caminho == "dualsense", "a ordem dos gestos virou"


def test_fora_do_laco_o_modo_espera_e_devolve_o_nome(tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)

    nome = servidor.daemon.gravar_o_modo_escolhido("gamepad", caminho="xbox", mascara="xbox",
                                                   porta="ipc")

    assert nome == "Ensaio"
    assert loader.load_profile("Ensaio").mode.caminho == "xbox"


_PERGUNTA = b'{"jsonrpc": "2.0", "id": 1, "method": "daemon.status"}\n'


def test_a_pergunta_de_outro_cliente_nao_espera_o_disco_do_gesto(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta,
) -> None:
    """O PS + L3 grava em fio próprio: a janela que pergunta nesse instante responde na hora.

    MORDIDA: faça `gravacao_do_pedido` devolver a última gravação de qualquer pedido.
    """
    from hefesto_dualsense4unix.profiles.manager import FIO_DO_PERFIL

    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    async def corpo() -> float:
        async def gesto_do_controle() -> None:
            servidor.daemon.gravar_o_modo_escolhido("gamepad", caminho="xbox", mascara="xbox",
                                                    porta="ipc")

        await asyncio.ensure_future(gesto_do_controle())
        t0 = time.perf_counter()
        await servidor._dispatch(_PERGUNTA)
        return time.perf_counter() - t0

    gasto = asyncio.run(corpo())
    FIO_DO_PERFIL.submit(lambda: None).result(timeout=DORME_S * 6)

    assert gasto < TETO_IPC_S, f"a pergunta esperou o disco do gesto {gasto:.2f} s"
    assert loader.load_profile("Ensaio").mode.caminho == "xbox"


def test_a_resposta_do_gesto_sai_com_o_modo_no_disco(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta,
) -> None:
    """Quem pediu pelo IPC lê o disco logo depois: a resposta dele espera, e o laço não.

    MORDIDA: tire o `await _o_perfil_em_dia()` do `_dispatch`.
    """
    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()

    async def gesto(_params: dict[str, Any]) -> dict[str, str]:
        servidor.daemon.gravar_o_modo_escolhido("gamepad", caminho="xbox", mascara="xbox",
                                                porta="ipc")
        return {"status": "ok"}

    servidor._handlers["ensaio.gesto"] = gesto

    async def corpo() -> Any:
        tarefa = asyncio.ensure_future(servidor._dispatch(
            b'{"jsonrpc": "2.0", "id": 2, "method": "ensaio.gesto"}\n'))
        await asyncio.sleep(0.05)
        assert not tarefa.done(), "a resposta saiu antes do disco"
        await servidor._dispatch(_PERGUNTA)
        assert not tarefa.done(), "o laço devia seguir atendendo com o gesto esperando"
        return await tarefa

    assert json.loads(asyncio.run(corpo()))["result"] == {"status": "ok"}
    assert loader.load_profile("Ensaio").mode.caminho == "xbox"


def test_quem_desiste_de_esperar_nao_cancela_a_gravacao_da_fila(
    tmp_path: Path, gravacao_lenta: _GravacaoLenta,
) -> None:
    """O cliente caiu com o gesto na fila: o aparelho já trocou, e o modo chega ao perfil.

    MORDIDA: tire o ``asyncio.shield`` de `_o_perfil_em_dia`.
    """
    from hefesto_dualsense4unix.daemon.ipc_server import _o_perfil_em_dia
    from hefesto_dualsense4unix.profiles.manager import FIO_DO_PERFIL

    servidor = _servidor(tmp_path)
    gravacao_lenta.ligar()
    daemon = servidor.daemon

    async def pedido() -> None:
        daemon.gravar_o_modo_escolhido("gamepad", caminho="dualsense", mascara="dualsense",
                                       porta="ipc")
        await _o_perfil_em_dia()

    async def corpo() -> None:
        daemon.gravar_o_modo_escolhido("gamepad", caminho="xbox", mascara="xbox", porta="ipc")
        tarefa = asyncio.ensure_future(pedido())
        await asyncio.sleep(0.05)
        tarefa.cancel()
        await asyncio.gather(tarefa, return_exceptions=True)

    asyncio.run(corpo())
    FIO_DO_PERFIL.submit(lambda: None).result(timeout=DORME_S * 6)

    assert loader.load_profile("Ensaio").mode.caminho == "dualsense"


def test_o_daemon_status_com_appid_varre_as_receitas_fora_do_laco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: chame o ``_receitas_dos_jogos`` direto no ``ambiente_do_lancamento``."""
    receitas = _Espiao({str(APPID): {"PECA": "1"}})
    monkeypatch.setattr(le, "_receitas_dos_jogos", receitas)
    servidor = _servidor(tmp_path)

    async def corpo() -> tuple[float, bool, Any]:
        return await _o_status_durante(
            servidor, servidor._handlers["daemon.status"]({"appid": APPID}))

    gasto, corria, resposta = asyncio.run(corpo())

    assert gasto < TETO_IPC_S and corria, f"o status com appid parou o laço {gasto:.2f} s"
    _o_fio_do_laco_nao_rodou(receitas)
    assert resposta["ambiente"]["receita"] == ["PECA=1"], resposta


def test_o_profile_list_le_o_disco_fora_do_laco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    servidor = _servidor(tmp_path)
    lista = _Espiao([])
    monkeypatch.setattr(servidor.profile_manager, "list_profiles", lista)

    gasto, corria, _resposta = asyncio.run(
        _o_status_durante(servidor, servidor._handlers["profile.list"]({})))

    assert gasto < TETO_IPC_S and corria, f"o profile.list parou o laço {gasto:.2f} s"
    _o_fio_do_laco_nao_rodou(lista)


@pytest.fixture
def coop_de_verdade(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O `CoopManager.sync` de produção com a mesa de um primário e o P2 de pé no disco."""
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.testing import FakeController

    descoberta = _Espiao({_P2: Path("/dev/input/event-do-p2")})
    monkeypatch.setattr(evdev_reader, "discover_dualsense_evdevs", descoberta)
    monkeypatch.setattr(co, "externos_que_ganham_virtual", dict)
    monkeypatch.setattr(co.CoopManager, "should_be_active", lambda self: True)
    criados: list[tuple[str, str]] = []
    monkeypatch.setattr(co.CoopManager, "_spawn_player",
                        lambda self, mac, no, **_k: criados.append((mac, no)))
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    gerente = co.CoopManager(Daemon(controller=FakeController()))
    gerente._primary_identity = lambda: _P1  # type: ignore[method-assign]
    return SimpleNamespace(gerente=gerente, descoberta=descoberta, criados=criados)


def test_o_sync_forcado_no_laco_descobre_em_fio_proprio_e_renasce(coop_de_verdade: Any) -> None:
    """O gesto não paga o `close` de todo nó: o `sync` volta na hora e anda quando a volta chega.

    MORDIDA: em ``_nos_de_agora``, chame ``descobrir_os_nos()`` direto no laço.
    """
    m = coop_de_verdade

    async def corpo() -> float:
        t0 = time.perf_counter()
        m.gerente.sync(force=True, origem="manual")
        gasto = time.perf_counter() - t0
        assert m.criados == [], "o sync não esperou a descoberta e já criou"
        await asyncio.sleep(DORME_S + 0.2)
        return gasto

    gasto = asyncio.run(corpo())

    assert gasto < TETO_TIQUE_S, f"o sync esperou a descoberta {gasto:.3f} s no laço"
    assert m.descoberta.fios == ["hefesto-nos-do-coop"], m.descoberta.fios
    assert m.criados == [(_P2, "/dev/input/event-do-p2")], m.criados


def test_o_pedido_no_meio_da_descoberta_nao_abre_outro_fio_e_refaz_a_volta(
    coop_de_verdade: Any,
) -> None:
    """O nó que nasceu no meio da volta não se perde: quem pede ali refaz a descoberta."""
    m = coop_de_verdade

    async def corpo() -> None:
        m.gerente.sync(force=True, origem="manual")
        await asyncio.sleep(0.05)
        m.gerente.sync(force=True, origem="manual")
        await asyncio.sleep(DORME_S * 2 + 0.3)

    asyncio.run(corpo())

    assert m.descoberta.fios == ["hefesto-nos-do-coop"] * 2, m.descoberta.fios
    assert m.gerente._descobrindo is False
    assert m.criados == [(_P2, "/dev/input/event-do-p2")], m.criados


def test_o_gesto_anda_na_hora_sobre_os_nos_vistos_e_a_descoberta_confere_depois(
    coop_de_verdade: Any,
) -> None:
    """O modo não muda os nós: quem segue o gesto troca no mesmo instante, sem esperar a volta.

    MORDIDA: devolva ``None`` no fim de ``_nos_de_agora``.
    """
    m = coop_de_verdade
    m.gerente.sync(force=True, origem="manual")
    m.gerente._players.clear()

    async def corpo() -> None:
        m.gerente.sync(force=True, origem="manual")
        assert len(m.criados) == 2, "o gesto esperou a descoberta com a mesa parada"
        await asyncio.sleep(DORME_S + 0.2)

    asyncio.run(corpo())

    assert m.descoberta.fios[-1:] == ["hefesto-nos-do-coop"], m.descoberta.fios
    assert m.gerente._descobrindo is False


def test_o_no_que_mudou_no_meio_do_gesto_se_corrige_na_volta(coop_de_verdade: Any) -> None:
    """O gesto anda sobre o que viu, e a descoberta que confere leva ao nó de agora.

    MORDIDA: tire a chamada de ``_descobrir`` de ``_nos_de_agora`` quando há nós vistos.
    """
    m = coop_de_verdade
    m.gerente.sync(force=True, origem="manual")
    m.gerente._players.clear()
    m.descoberta.resposta = {_P2: Path("/dev/input/event-novo-do-p2")}

    async def corpo() -> None:
        m.gerente.sync(force=True, origem="manual")
        assert m.criados[-1] == (_P2, "/dev/input/event-do-p2"), m.criados
        m.gerente._players.clear()
        await asyncio.sleep(DORME_S + 0.2)

    asyncio.run(corpo())

    assert m.criados[-1] == (_P2, "/dev/input/event-novo-do-p2"), m.criados


def test_o_tique_no_meio_da_volta_nao_apaga_a_origem_do_gesto(coop_de_verdade: Any) -> None:
    """A origem decide se a máscara espera o jogo: a volta que anda depois tem de ser a do gesto.

    MORDIDA: em ``_nos_de_agora``, guarde só a ``origem`` do pedido mais novo.
    """
    m = coop_de_verdade

    async def corpo() -> None:
        m.gerente._nos_de_agora(True, "manual")
        m.gerente._nos_de_agora(False, None)
        assert m.gerente._pedido_dos_nos == (True, "manual")
        await asyncio.sleep(DORME_S * 2 + 0.3)

    asyncio.run(corpo())

    assert m.gerente._pedido_dos_nos == (False, None)


def test_o_coop_que_desliga_esquece_os_nos(coop_de_verdade: Any, monkeypatch: Any) -> None:
    """Horas depois, o nó guardado pode ser outro aparelho: quem desliga não guarda a mesa.

    MORDIDA: tire ``self._nos_vistos = None`` do ramo inativo de ``sync``.
    """
    m = coop_de_verdade
    m.gerente.sync(force=True, origem="manual")
    assert m.gerente._nos_vistos is not None

    monkeypatch.setattr(type(m.gerente), "should_be_active", lambda _self: False)
    m.gerente.sync()

    assert m.gerente._nos_vistos is None


def test_a_volta_que_acha_o_laco_fechado_nao_prende_a_proxima(coop_de_verdade: Any) -> None:
    """O laço fechado não recebe a resposta, e a marca de «descobrindo» não fica presa.

    MORDIDA: volte `_descobrir` a só engolir o ``RuntimeError``.
    """
    m = coop_de_verdade

    async def corpo() -> None:
        m.gerente.sync(force=True, origem="manual")

    asyncio.run(corpo())
    prazo = time.monotonic() + DORME_S + 2.0
    while m.gerente._descobrindo and time.monotonic() < prazo:
        time.sleep(0.01)

    assert m.gerente._descobrindo is False


def test_fora_do_laco_o_sync_descobre_na_hora(coop_de_verdade: Any) -> None:
    coop_de_verdade.gerente.sync(force=True, origem="manual")

    assert coop_de_verdade.criados == [(_P2, "/dev/input/event-do-p2")]


_FICAM_FRIOS = {
    "hefesto_dualsense4unix.interface": "só o relatório de CLI do `storm_doctor`",
    "hefesto_dualsense4unix.interface.onde": "só o relatório de CLI do `storm_doctor`",
    "hefesto_dualsense4unix.testing": "só a subida com o controle de mentira",
}

_OS_FRIOS = """
import ast, importlib.util, pathlib, sys
from hefesto_dualsense4unix.daemon import lifecycle as lc
lc._importar_o_que_a_subida_usa()
raiz = pathlib.Path(lc.__file__).resolve().parents[1]
pacote = "hefesto_dualsense4unix"
frios = set()
def existe(nome):
    try:
        return importlib.util.find_spec(nome) is not None
    except (ImportError, AttributeError, ValueError):
        return False
for parte in ("core", "daemon", "integrations", "mods", "plugin_api", "profiles", "utils"):
    for arquivo in (raiz / parte).rglob("*.py"):
        for bloco in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(bloco, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for no in ast.walk(bloco):
                nomes = []
                if isinstance(no, ast.ImportFrom) and (no.module or "").startswith(pacote):
                    nomes = [no.module, *(f"{no.module}.{a.name}" for a in no.names)]
                elif isinstance(no, ast.Import):
                    nomes = [a.name for a in no.names if a.name.startswith(pacote)]
                frios.update(n for n in nomes if n not in sys.modules and existe(n))
print("\\n".join(sorted(frios)))
"""


def test_a_subida_importa_fora_do_fio_do_laco() -> None:
    """Nenhum import de dentro de função paga o disco no laço: a subida já os trouxe, todos.

    O dono é a lista de imports do próprio serviço: módulo novo importado de dentro de função
    entra sozinho na régua, e a parada de 17 s não muda de módulo.

    MORDIDA: tire o ``to_thread(_importar_o_que_a_subida_usa)`` do ``Daemon.run``, ou troque
    `_PACOTES_DO_SERVICO` por só `daemon.subsystems`.
    """
    fonte = (_SRC / "hefesto_dualsense4unix/daemon/lifecycle.py").read_text(encoding="utf-8")
    corpo = next(no for no in ast.walk(ast.parse(fonte))
                 if isinstance(no, ast.AsyncFunctionDef) and no.name == "run")
    texto = ast.unparse(corpo)

    assert "await asyncio.to_thread(_importar_o_que_a_subida_usa)" in texto
    assert texto.index("_importar_o_que_a_subida_usa") < texto.index("subir(")
    saida = subprocess.run([sys.executable, "-c", _OS_FRIOS], check=True, timeout=120,
                           capture_output=True, text=True).stdout
    assert set(saida.split()) == set(_FICAM_FRIOS), saida
