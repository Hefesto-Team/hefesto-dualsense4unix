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
import os
import subprocess
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
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

DORME_S = 2.0
TETO_TIQUE_S = 0.05
TETO_IPC_S = 1.0
APPID = 9931101
JOGO = "Jogo da Régua do Laço"
_P1 = "aa:bb:cc:00:00:01"
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
    assert movimento is not None and movimento.sensibilidade == 7
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
_ONDA_SEGUINTE = "O-LACO-DO-DAEMON-NAO-RODA-O-AMIXER-NEM-GRAVA-O-GESTO-01"
_H = "hefesto_dualsense4unix.daemon.ipc_handlers.IpcHandlersMixin."
_D = "hefesto_dualsense4unix.daemon.lifecycle.Daemon."
_AINDA_NO_LACO: dict[str, str] = {
    _H + "_armar_launch": _ONDA_SEGUINTE,
    _H + "_handle_daemon_status": _ONDA_SEGUINTE,
    _H + "_handle_machine_declare": _ONDA_SEGUINTE,
    _H + "_handle_mic_volume_set": _ONDA_SEGUINTE,
    _H + "_handle_profile_reaplicar": _ONDA_SEGUINTE,
    _H + "_handle_profile_switch": _ONDA_SEGUINTE,
    _H + "_handle_rumble_motores_set": _ONDA_SEGUINTE,
    _H + "_handle_sensor_set": _ONDA_SEGUINTE,
    _H + "_o_que_volta_sem_o_freestyle": _ONDA_SEGUINTE,
    _D + "_poll_loop": _ONDA_SEGUINTE,
    _D + "run": _ONDA_SEGUINTE,
    (
        "hefesto_dualsense4unix.daemon.subsystems.eventos_do_perfil.EventosDoPerfil._entrar"
    ): _ONDA_SEGUINTE,
}


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
