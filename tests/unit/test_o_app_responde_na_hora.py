"""O APP RESPONDE NA HORA — O-APP-RESPONDE-NA-HORA-01 (02/10/2026).

Ela, em 02/10, sobre onde o atraso pesa:

    «Em todas as abas. Perfis, ao clicar em algum  # noqa-acento: citação literal dela
    elemento, e alem disso o conexão que nao  # noqa-acento: citação literal dela
    funcionava nem a pau»

Três custos medidos, e as réguas de cada um, sem tela:

    R1  a Perfis pergunta ao catálogo uma vez por tique (a foto do catálogo)
    R2  a janela relê só o perfil que mudou, e o «não há jogo» segue em 5 s
    R3  o laço do serviço responde enquanto o escrevente do lançamento trabalha
    R4  um pedido a mais, no máximo, e sem o escrevente a escrita é na hora
    R5  o servidor diz quem o segurou (`ipc_lento`)
    R6  a pergunta abandonada não roda; o pedido que muda e o `daemon.status` rodam
    R7  o cliente do IPC não importa o servidor

As de contagem contam o trabalho do PRODUTO com um ``sys.addaudithook``
(``open``); as de tempo medem a CPU do fio (``time.thread_time``) ou a parede
do pedido de outro cliente, com o trabalho de CPU de verdade (um laço de conta,
e não ``sleep``, que solta o GIL e esconderia o caso real). A MORDIDA de cada
uma está no docstring dela.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog

from hefesto_dualsense4unix.core import o_dono_do_evento as ode
from hefesto_dualsense4unix.daemon import launch_env
from tests.unit.test_o_censo_responde_como_o_lancador_responde import plantar_o_registro

RAIZ = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# O gancho que conta o trabalho do produto
# ---------------------------------------------------------------------------

#: Enquanto não é None, o gancho anota o caminho de todo ``open`` do fio que
#: ligou a conta.
_CONTA: list[str] | None = None
_FIO_DA_CONTA: int | None = None


def _gancho(evento: str, args: tuple[Any, ...]) -> None:
    conta = _CONTA
    if conta is None or evento != "open":
        return
    if threading.get_ident() != _FIO_DA_CONTA:
        return
    alvo = args[0] if args else ""
    if isinstance(alvo, bytes):
        alvo = os.fsdecode(alvo)
    conta.append(str(alvo))


# Um gancho de auditoria não se remove: fica um só, barato, por processo.
if not getattr(sys, "_hefesto_gancho_da_velocidade", False):
    sys.addaudithook(_gancho)
    sys._hefesto_gancho_da_velocidade = True  # type: ignore[attr-defined]


@contextlib.contextmanager
def contando() -> Iterator[list[str]]:
    """Liga a conta das aberturas no fio de quem chama, e a desliga na saída."""
    global _CONTA, _FIO_DA_CONTA
    conta: list[str] = []
    _FIO_DA_CONTA = threading.get_ident()
    _CONTA = conta
    try:
        yield conta
    finally:
        _CONTA = None
        _FIO_DA_CONTA = None


# ---------------------------------------------------------------------------
# A casa de mentira: a biblioteca da Steam, o Heroic, os atalhos e os perfis
# ---------------------------------------------------------------------------

#: O tamanho é o da casa dela (33 jogos da Steam, 29 perfis), com 200 atalhos.
JOGOS_DA_STEAM = 33
PERFIS = 30
ATALHOS = 200


def _envelhecer(caminho: Path) -> None:
    """Uma hora atrás: a regra do arquivo recém-gravado relê o que tem 2 s."""
    velho = time.time() - 3600
    os.utime(caminho, (velho, velho))


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A casa da régua 1, com o `HOME` e os `XDG_*` da usuária apontados para ela.

    O `XDG_DATA_DIRS` fica o do sistema: sem ele o WebKit da régua 8 perde a
    base de tipos de arquivo e não abre a página.
    """
    from hefesto_dualsense4unix.profiles import loader

    raiz = tmp_path / "casa"
    for var, sub in (("HOME", ""), ("XDG_CONFIG_HOME", ".config"),
                     ("XDG_DATA_HOME", ".local/share"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache")):
        alvo = raiz / sub if sub else raiz
        alvo.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(alvo))
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    steamapps = raiz / ".steam/steam/steamapps"
    steamapps.mkdir(parents=True)
    biblioteca = raiz / ".steam/steam"
    (steamapps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{biblioteca}"\n\t}}\n}}\n')
    appids = [str(1000000 + 7 * i) for i in range(JOGOS_DA_STEAM)]
    for i, appid in enumerate(appids):
        (steamapps / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"Jogo {i:02d}"\n}}\n')
    heroic = raiz / ".var/app/com.heroicgameslauncher.hgl/config/heroic/store_cache"
    heroic.mkdir(parents=True)
    itens = [{"app_name": f"h{i:030d}", "title": f"Heroico {i}", "is_installed": True,
              "install": {"executable": f"bin/h{i}.exe", "install_path": f"/x/h{i}",
                          "is_dlc": False}} for i in range(4)]
    (heroic / "legendary_library.json").write_text(json.dumps({"library": itens}))
    plantar_o_registro(heroic.parent, [str(i["app_name"]) for i in itens])
    atalhos = raiz / ".local/share/applications"
    atalhos.mkdir(parents=True)
    for i in range(ATALHOS):
        (atalhos / f"app{i}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=App {i}\nExec=/usr/bin/app{i}\n")
    perfis = raiz / ".config/hefesto-dualsense4unix/profiles"
    perfis.mkdir(parents=True)
    for i in range(PERFIS):
        appid = appids[i] if i < JOGOS_DA_STEAM else str(3000000 + i)
        (perfis / f"steam_{i:02d}.json").write_text(json.dumps({
            "name": f"Steam {i:02d}", "priority": 50,
            "match": {"type": "criteria", "window_class": [f"steam_app_{appid}"],
                      "window_title_regex": None, "process_name": []}}))
    for arquivo in raiz.rglob("*"):
        _envelhecer(arquivo)
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: perfis)
    loader._PERFIS_PELA_ASSINATURA.esquecer()
    loader.desligar_a_leitura_pela_assinatura()
    while ode.armado():  # nada herdado de outro teste
        ode.desarmar()
    return SimpleNamespace(raiz=raiz, steamapps=steamapps, perfis=perfis)


def _contexto() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"active_profile": "Steam 00"}, mesa=[], conectados=[], estados={})


def _sob(conta: list[str], raiz: Path, fim: str) -> list[str]:
    return [c for c in conta if c.startswith(str(raiz)) and c.endswith(fim)]


# ===========================================================================
# R1 — a Perfis pergunta ao catálogo uma vez por tique
# ===========================================================================
class TestAPerfisPerguntaAoCatalogoUmaVez:
    def test_vinte_pacotes_sem_mudanca_nao_abrem_o_catalogo_por_linha(
        self, casa: SimpleNamespace
    ) -> None:
        """Da segunda chamada em diante: nenhum `.acf`, e no máximo DOIS
        `libraryfolders.vdf` por chamada (a foto das ofertas e a dos nomes).

        MORDIDA: devolva o catálogo por linha (cada tradutor perguntando
        `_ofertas_de_jogos()`/`_nomes_dos_jogos()` de novo, sem a foto) — o
        `libraryfolders.vdf` volta a abrir uma vez por consulta, dezenas por
        chamada (66 por chamada nesta casa, medido em 02/10).
        """
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis

        ctx = _contexto()
        a10_perfis.pacote(ctx)  # a primeira lê a biblioteca inteira
        por_chamada: list[list[str]] = []
        for _ in range(19):
            with contando() as conta:
                a10_perfis.pacote(ctx)
            por_chamada.append(conta)
        acf = [len(_sob(c, casa.steamapps, ".acf")) for c in por_chamada]
        vdf = [len(_sob(c, casa.steamapps, "libraryfolders.vdf")) for c in por_chamada]
        assert max(acf) == 0, f"o catálogo foi relido sem mudar: {acf} `.acf` por chamada"
        assert max(vdf) <= 2, (
            f"a Perfis consultou o catálogo por linha: {vdf} aberturas do "
            "`libraryfolders.vdf` por chamada (a foto do tique abre no máximo duas)")

    def test_o_jogo_instalado_aparece_na_chamada_seguinte(self, casa: SimpleNamespace) -> None:
        """A foto é do tique, e nada se guarda entre tiques além do que já se
        guardava: um `appmanifest` novo está na lista do campo do jogo na
        chamada seguinte.

        MORDIDA: guarde a foto entre chamadas (um cache de módulo sem a
        assinatura) — o jogo novo não aparece.
        """
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis

        ctx = _contexto()
        antes = a10_perfis.pacote(ctx)["blocos"][a10_perfis.SELETOR_DOS_JOGOS]
        assert "Jogo 05" in antes, "a casa não chegou à lista do campo do jogo"
        assert "Jogo Que Acabou De Chegar" not in antes
        (casa.steamapps / "appmanifest_4242424.acf").write_text(
            '"AppState"\n{\n\t"appid"\t\t"4242424"\n'
            '\t"name"\t\t"Jogo Que Acabou De Chegar"\n}\n')
        depois = a10_perfis.pacote(ctx)["blocos"][a10_perfis.SELETOR_DOS_JOGOS]
        assert "Jogo Que Acabou De Chegar" in depois, (
            "o jogo instalado não apareceu no tique seguinte")


# ===========================================================================
# R2 — a janela relê só o perfil que mudou, e o «não há jogo» segue em 5 s
# ===========================================================================
def _o_processo_da_janela() -> Any:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    return hefesto_vivo._o_processo_da_janela()


class TestAJanelaReleSoOPerfilQueMudou:
    def test_dez_pacotes_sem_mudanca_nao_abrem_perfil(self, casa: SimpleNamespace) -> None:
        """Com a leitura pela assinatura ligada como a janela liga, e o dono do
        evento desarmado: zero aberturas de `.json` de perfil depois da
        primeira; um perfil regravado por `os.replace` é o único relido, e o
        nome novo chega ao pacote. Fora da janela, cada carga lê tudo de novo.

        MORDIDA: não ligue a leitura em `_o_processo_da_janela` (ou tire o
        `_LEITURA_LIGADA_PELO_PROCESSO` do `load_all_profiles`) — uma abertura
        por perfil, 30 por chamada.
        """
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        ctx = _contexto()
        with _o_processo_da_janela():
            assert not ode.armado(), "a janela armou o dono do evento"
            a10_perfis.pacote(ctx)
            with contando() as conta:
                for _ in range(10):
                    a10_perfis.pacote(ctx)
            jsons = _sob(conta, casa.perfis, ".json")
            assert jsons == [], (
                f"a janela releu {len(jsons)} perfis em dez pacotes sem mudança "
                "(a leitura pela assinatura não ligou)")
            alvo = casa.perfis / "steam_03.json"
            dados = json.loads(alvo.read_text())
            dados["name"] = "Steam 03 Renomeado"
            provisorio = casa.perfis / "steam_03.json.tmp"
            provisorio.write_text(json.dumps(dados))
            os.replace(provisorio, alvo)
            with contando() as conta:
                pacote = a10_perfis.pacote(ctx)
            relidos = sorted({Path(c).name for c in _sob(conta, casa.perfis, ".json")})
            assert relidos == ["steam_03.json"], f"relidos: {relidos}"
            assert "Steam 03 Renomeado" in json.dumps(pacote, ensure_ascii=False)
        with contando() as conta:
            load_all_profiles()
        assert len(_sob(conta, casa.perfis, ".json")) == PERFIS, (
            "a leitura pela assinatura ficou ligada depois de a janela sair")

    def test_na_janela_o_nao_ha_jogo_vale_os_cinco_segundos(
        self, casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """O dono do evento não se arma na janela: armado, ele alongaria para
        60 s o «não há jogo» que a aba do jogo lê
        (`TETO_DO_NEGATIVO_DE_EXIBICAO_S`), e quem o invalida ao ver outra
        janela em foco é o autoswitch, que mora no daemon.

        MORDIDA: arme o dono em `_o_processo_da_janela` — o negativo de 0 s
        ainda vale aos 6 s, e a segunda varredura não acontece.
        """
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        relogio = [0.0]
        varreduras = [0]
        listar_de_verdade = os.listdir
        lancamento = tmp_path / "launch_env"
        lancamento.mkdir()

        def listar(caminho: Any = ".") -> list[str]:
            if str(caminho) == "/proc":
                varreduras[0] += 1
                return ["100", "101", "self"]
            return listar_de_verdade(caminho)

        monkeypatch.setattr(os, "listdir", listar)
        monkeypatch.setattr(slo, "_cmdline_of", lambda pid: "cosmic-comp")
        monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: lancamento)
        monkeypatch.setattr(slo, "_agora", lambda: relogio[0])
        launch_env._MARCADORES_PELA_ASSINATURA.esquecer()
        slo.invalidar_varredura_de_proc()
        try:
            with _o_processo_da_janela():
                for t in (0.0, 4.0):
                    relogio[0] = t
                    assert slo.steam_game_running_appid() is None
                assert varreduras[0] == 1
                relogio[0] = 6.0
                slo.steam_game_running_appid()
                assert varreduras[0] == 2, (
                    "o «não há jogo» passou dos 5 s dentro da janela: o dono do "
                    "evento se armou nela (o negativo vai a 60 s)")
        finally:
            slo.invalidar_varredura_de_proc()


# ===========================================================================
# O servidor real num laço próprio, e o cliente de mentira
# ===========================================================================
def _foto() -> Any:
    """Uma foto do lançamento sem daemon: só a ordem importa às réguas."""
    return launch_env._FotoDoLancamento(
        ordem=next(launch_env._ORDEM_DAS_FOTOS), native=False, enabled=True,
        flavor="dualsense", backends=(), fisicos=1, modo_vivo=None,  # type: ignore[arg-type]
        em_cena=frozenset(), identidade=None, permite_uhid=False, vpads_previstos=0,
        leitor=None, publicar=lambda _d: None, carimbar=lambda: None, foto_ms=0.0)


@pytest.fixture
def sem_escrevente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Nenhum escrevente herdado, e nenhum deixado para o teste seguinte."""
    monkeypatch.setattr(launch_env, "_ESCREVENTE", None)
    yield
    escrevente = launch_env._ESCREVENTE
    if escrevente is not None:
        launch_env.desarmar_o_escrevente(escrevente)


def _servidor(pasta: Path, daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.testing import FakeController

    return IpcServer(controller=FakeController(transport="usb", states=[]),
                     store=StateStore(), profile_manager=MagicMock(),
                     socket_path=pasta / "s.sock", daemon=daemon)


class _NoFio:
    """O servidor num laço de fio próprio: o teste é o cliente, de fora."""

    def __init__(self, servidor: Any) -> None:
        self.servidor = servidor
        self.laco = asyncio.new_event_loop()
        self.fio = threading.Thread(target=self.laco.run_forever, daemon=True)

    def __enter__(self) -> _NoFio:
        self.fio.start()
        asyncio.run_coroutine_threadsafe(self.servidor.start(), self.laco).result(10)
        return self

    def __exit__(self, *_exc: object) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self.servidor.stop(), self.laco).result(20)
        finally:
            self.laco.call_soon_threadsafe(self.laco.stop)
            self.fio.join(5)
            self.laco.close()


@pytest.fixture
def pasta_curta() -> Iterator[Path]:
    """Uma pasta de caminho curto: o endereço de um socket Unix cabe em 107 bytes."""
    pasta = Path(tempfile.mkdtemp(prefix="hr"))
    try:
        yield pasta
    finally:
        for filho in pasta.iterdir():
            with contextlib.suppress(OSError):
                filho.unlink()
        with contextlib.suppress(OSError):
            pasta.rmdir()


def _pedir(caminho: Path, metodo: str, *, fechar_sem_ler: bool = False,
           teto_s: float = 10.0) -> tuple[float, Any]:
    """Um pedido JSON-RPC por conexão: (ms de parede, resposta)."""
    t0 = time.perf_counter()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(teto_s)
        s.connect(str(caminho))
        s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": metodo,
                              "params": {}}).encode() + b"\n")
        if fechar_sem_ler:
            return 0.0, None
        dados = b""
        with contextlib.suppress(TimeoutError):
            while not dados.endswith(b"\n"):
                parte = s.recv(65536)
                if not parte:
                    break
                dados += parte
    return (time.perf_counter() - t0) * 1000, json.loads(dados) if dados else None


async def _pergunta_de_mentira(_params: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True}


# ===========================================================================
# R3 — o laço responde enquanto o escrevente trabalha
# ===========================================================================
#: O trabalho de fora QUEIMA ao menos isto de CPU em Python (o corpo da
#: materialização, medido em 02/10: de 316 a 401 ms por chamada, 2.837 ms na pior).
QUEIMA_S = 1.5
#: Cada pergunta de outro cliente, durante o trabalho, em até isto de parede.
TETO_DA_PERGUNTA_MS = 300.0


class TestOLacoRespondeEnquantoOEscreventeTrabalha:
    def test_vinte_perguntas_durante_a_escrita_saem_em_ate_300_ms(
        self, sem_escrevente: None, pasta_curta: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `IpcServer` real, o escrevente armado pelo `start`, e uma parte de
        fora que queima CPU no fio do escrevente: vinte `daemon.state_full`
        de outro cliente, durante o trabalho, cada um em até 300 ms.

        MORDIDA: tire o `armar_o_escrevente` do `IpcServer.start` — o trabalho
        volta ao laço, e a primeira pergunta espera a queima inteira. Um dublê
        trocado por `sleep` não passaria calado: a régua confere a CPU que o
        fio queimou e diz qual dos dois rodou.
        """
        comecou = threading.Event()
        acabaram = threading.Event()
        queimas: list[tuple[float, float]] = []
        devolvidas: list[int] = []

        def queimar(_foto: Any, devolver: Any) -> None:
            comecou.set()
            cpu0 = time.thread_time()
            minimo = time.perf_counter() + QUEIMA_S
            teto = minimo + 1.5
            conta = 0
            while time.perf_counter() < teto and (
                    time.perf_counter() < minimo or not acabaram.is_set()):
                conta += 1
            queimas.append((time.thread_time() - cpu0, time.perf_counter()))
            devolver(lambda: devolvidas.append(threading.get_ident()))

        monkeypatch.setattr(launch_env, "_foto_do_lancamento",
                            lambda _daemon, *, no_fio: _foto())
        monkeypatch.setattr(launch_env, "_a_parte_de_fora", queimar)
        servidor = _servidor(pasta_curta, daemon=SimpleNamespace())
        servidor._handlers["daemon.state_full"] = _pergunta_de_mentira
        refresh: list[tuple[float, Any]] = []
        with _NoFio(servidor) as no_fio:
            fio = threading.Thread(
                target=lambda: refresh.append(_pedir(servidor.socket_path, "launch_env.refresh")))
            fio.start()
            assert comecou.wait(10), "a materialização nunca começou"
            tempos = [_pedir(servidor.socket_path, "daemon.state_full")[0] for _ in range(20)]
            fim_das_perguntas = time.perf_counter()
            acabaram.set()
            fio.join(15)
        assert queimas, "a parte de fora não terminou"
        cpu, fim_da_queima = queimas[0]
        pior = max(tempos)
        assert pior <= TETO_DA_PERGUNTA_MS, (
            f"o laço ficou preso: a pior das vinte perguntas levou {pior:.0f} ms "
            f"(teto {TETO_DA_PERGUNTA_MS:.0f}), com a parte de fora queimando "
            f"{cpu:.2f} s de CPU — o trabalho do lançamento rodou dentro do laço")
        assert refresh and refresh[0][0] <= TETO_DA_PERGUNTA_MS, (
            f"o `launch_env.refresh` esperou a escrita: {refresh}")
        assert refresh[0][1]["result"] == {"status": "ok"}
        assert cpu >= 0.8 * QUEIMA_S, (
            f"a parte de fora queimou só {cpu:.2f} s de CPU: rodou um `sleep`, que "
            "solta o GIL, e a régua não mediu o caso de Python")
        assert fim_das_perguntas < fim_da_queima, (
            "as perguntas acabaram depois do trabalho: nada foi medido durante ele")
        assert devolvidas == [no_fio.fio.ident], (
            "a devolução ao daemon não voltou ao laço do serviço")


# ===========================================================================
# R4 — um pedido a mais, no máximo; sem o escrevente, na hora
# ===========================================================================
class TestUmPedidoAMaisNoMaximo:
    def test_dez_pedidos_com_um_em_curso_viram_uma_escrita_com_a_ultima_foto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dez pedidos com uma escrita em curso: exatamente UMA escrita depois
        dela, com a foto do último (o último estado vence).

        MORDIDAS: sem juntar (uma fila em vez do lugar único) — onze escritas;
        com a primeira foto em vez da última (`if self._pendente is None`) — a
        segunda escrita leva o estado de antes.
        """
        escritas: list[int] = []
        entrou = threading.Event()
        solta = threading.Event()

        def parte_de_fora(foto: Any, _devolver: Any) -> None:
            escritas.append(foto.ordem)
            entrou.set()
            solta.wait(10)

        monkeypatch.setattr(launch_env, "_a_parte_de_fora", parte_de_fora)
        escrevente = launch_env.EscreventeDoLancamento(lambda acao: acao())
        try:
            fotos = [_foto() for _ in range(11)]
            escrevente.pedir(fotos[0])
            assert entrou.wait(10), "a primeira escrita não começou"
            for foto in fotos[1:]:
                escrevente.pedir(foto)
            solta.set()
        finally:
            solta.set()
            escrevente.esvaziar_e_parar(10)
        assert escritas == [fotos[0].ordem, fotos[-1].ordem], (
            f"escritas: {escritas} (esperava a primeira e a última de {len(fotos)})")
        assert escrevente.escritas == 2

    def test_a_foto_mais_velha_que_a_ultima_escrita_nao_se_escreve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O fio e a escrita de sempre (o arming) podem se cruzar: a foto mais
        nova é a que vale. MORDIDA: tire a conferência da ordem em
        `_escrever_o_lancamento` — a velha sobrescreve a nova."""
        escritas: list[int] = []
        monkeypatch.setattr(launch_env, "_a_parte_de_fora",
                            lambda foto, _d: escritas.append(foto.ordem))
        velha, nova = _foto(), _foto()
        assert launch_env._escrever_o_lancamento(nova) is True
        assert launch_env._escrever_o_lancamento(velha) is False
        assert escritas == [nova.ordem]

    def test_sem_o_escrevente_e_fora_do_laco_que_armou_a_escrita_e_na_hora(
        self, sem_escrevente: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem escrevente, a função de sempre: escreve antes de voltar, no fio
        de quem chamou. Com ele armado, só o pedido feito DENTRO do laço que
        armou vai ao fio; de fora do laço, ou dentro de `escrita_na_hora()`
        (o arming do lançamento), a escrita é na hora.

        MORDIDA: tire o `atende_aqui()` de `materialize_launch_env` — o pedido
        de fora do laço vai ao fio, e a escrita não acontece antes de voltar.
        """
        fios: list[int] = []
        monkeypatch.setattr(launch_env, "_foto_do_lancamento",
                            lambda _daemon, *, no_fio: _foto())
        monkeypatch.setattr(launch_env, "_a_parte_de_fora",
                            lambda _foto, _d: fios.append(threading.get_ident()))
        aqui = threading.get_ident()
        launch_env.materialize_launch_env(SimpleNamespace())  # type: ignore[arg-type]
        assert fios == [aqui], "sem o escrevente, a escrita não foi na hora"

        laco = asyncio.new_event_loop()
        escrevente = launch_env.armar_o_escrevente(lambda acao: acao(), laco)
        assert escrevente is not None
        try:
            fios.clear()
            launch_env.materialize_launch_env(SimpleNamespace())  # type: ignore[arg-type]
            assert fios == [aqui], "o pedido de fora do laço que armou foi ao fio"

            async def no_laco() -> None:
                with launch_env.escrita_na_hora():
                    launch_env.materialize_launch_env(SimpleNamespace())  # type: ignore[arg-type]
                assert fios[-1] == aqui, "o arming do lançamento não escreveu na hora"
                launch_env.materialize_launch_env(SimpleNamespace())  # type: ignore[arg-type]

            laco.run_until_complete(no_laco())
        finally:
            launch_env.desarmar_o_escrevente(escrevente)
            laco.close()
        assert fios[:2] == [aqui, aqui]
        assert len(fios) == 3 and fios[2] != aqui, (
            "o pedido de dentro do laço que armou não foi ao fio escrevente")

    def test_o_escrevente_de_um_laco_fechado_nao_segura_o_lugar(
        self, sem_escrevente: None
    ) -> None:
        """O servidor que saiu sem `stop` deixa o escrevente armado com um laço
        fechado: o próximo `start` arma o seu, e o velho para."""
        laco_velho = asyncio.new_event_loop()
        velho = launch_env.armar_o_escrevente(lambda acao: acao(), laco_velho)
        laco_velho.close()
        laco_novo = asyncio.new_event_loop()
        try:
            novo = launch_env.armar_o_escrevente(lambda acao: acao(), laco_novo)
            assert novo is not None and novo is not velho
            assert launch_env.armar_o_escrevente(lambda acao: acao(), laco_novo) is None
        finally:
            if launch_env._ESCREVENTE is not None:
                launch_env.desarmar_o_escrevente(launch_env._ESCREVENTE)
            laco_novo.close()

    @pytest.mark.parametrize("freestyle", [True, False], ids=["freestyle", "sem-freestyle"])
    def test_o_fio_escreve_os_mesmos_arquivos_que_a_escrita_na_hora(
        self, sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        freestyle: bool,
    ) -> None:
        """O caminho do serviço de verdade (a foto no laço, `_OQueOFioLe` e a
        parte de fora no fio) escreve os MESMOS arquivos que a escrita na hora,
        com os perfis lidos do disco pelo loader real: o `default.env`, o do
        jogo e o do perfil nativo fora da antecipação, com o Modo Freestyle
        ligado (a máscara dele em cada jogo) e desligado.

        MORDIDA: faça `_OQueOFioLe` dizer o Freestyle desligado
        (`_StoreDaFoto(False)`) — a célula `freestyle` reprova com a máscara
        do jogo no arquivo do fio.
        """
        from hefesto_dualsense4unix.profiles import loader
        from hefesto_dualsense4unix.profiles.schema import (
            MatchAny,
            MatchCriteria,
            Profile,
            ProfileModeConfig,
        )

        monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
        monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)
        loader.save_profile(Profile(name=loader.NOME_DO_PADRAO, match=MatchAny(),
                                    mode=ProfileModeConfig(kind="gamepad",
                                                           gamepad_flavor="xbox")))
        loader.save_profile(Profile(name="Jogo do Cabo",
                                    match=MatchCriteria(window_class=["steam_app_1000007"]),
                                    mode=ProfileModeConfig(kind="gamepad",
                                                           gamepad_flavor="dualsense")))
        loader.save_profile(Profile(name="Nativo pelo Titulo",
                                    match=MatchCriteria(window_title_regex="Nativo.*"),
                                    mode=ProfileModeConfig(kind="native")))
        monkeypatch.setattr(launch_env, "steam_input_appids", lambda path=None: set())
        monkeypatch.setattr(launch_env, "_permite_uhid", lambda daemon: True)
        monkeypatch.setattr(launch_env, "_device_ks_nos_lancadores", lambda: {})
        import hefesto_dualsense4unix.integrations.cura_por_estrada as cura

        monkeypatch.setattr(cura, "curar_todas_as_estradas", lambda: {})

        def daemon() -> Any:
            return SimpleNamespace(
                is_native_mode=lambda: False,
                config=SimpleNamespace(gamepad_emulation_enabled=True,
                                       gamepad_flavor="dualsense", coop_enabled=True),
                _gamepad_device=SimpleNamespace(backend="uhid"),
                _coop_manager=None, controller=SimpleNamespace(),
                store=SimpleNamespace(window_detect_current_class=None,
                                      freestyle_ligado=freestyle))

        def arquivos(pasta: Path) -> dict[str, str]:
            # a linha `# estado:` termina no relógio da escrita: ele sai da conta
            return {a.name: "\n".join(linha.rsplit(" | ", 1)[0] if linha.startswith("# estado:")
                                      else linha for linha in a.read_text().splitlines())
                    for a in sorted(pasta.glob("*.env"))}

        na_hora, no_fio = tmp_path / "na-hora", tmp_path / "no-fio"
        na_hora.mkdir()
        no_fio.mkdir()
        monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: na_hora)
        d1 = daemon()
        launch_env.materialize_launch_env(d1)  # type: ignore[arg-type]

        monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: no_fio)
        d2 = daemon()
        laco = asyncio.new_event_loop()
        escrevente = launch_env.armar_o_escrevente(laco.call_soon_threadsafe, laco)
        assert escrevente is not None
        try:
            async def pedir() -> None:
                launch_env.materialize_launch_env(d2)  # type: ignore[arg-type]
                while escrevente.escritas < 1:  # as devoluções voltam a este laço
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.05)

            laco.run_until_complete(asyncio.wait_for(pedir(), 20))
        finally:
            launch_env.desarmar_o_escrevente(escrevente)
            laco.close()
        esperado, do_fio = arquivos(na_hora), arquivos(no_fio)
        assert "steam_app_1000007.env" in esperado, esperado
        mascara = "xbox" if freestyle else "dualsense"
        assert f"perfil gamepad {mascara}" in esperado["steam_app_1000007.env"]
        assert do_fio == esperado, (
            f"o fio escreveu outra coisa que a escrita na hora:\n{do_fio}\n---\n{esperado}")
        assert d2._launch_env_assinatura == d1._launch_env_assinatura

    def test_o_stop_com_uma_foto_pendente_escreve_e_sai_sem_esperar_o_teto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O serviço que sai com uma foto pendente: ela é escrita, e o fio sai
        logo depois, sem segurar o `stop` até o teto.

        MORDIDA: devolva o `continue` incondicional depois da escrita em
        `EscreventeDoLancamento._laco` — o fio volta a esperar um evento já
        consumido, e o `stop` leva o teto inteiro (aqui, 10 s).
        """
        escritas: list[int] = []
        entrou = threading.Event()
        solta = threading.Event()

        def parte_de_fora(foto: Any, _devolver: Any) -> None:
            escritas.append(foto.ordem)
            entrou.set()
            solta.wait(10)

        monkeypatch.setattr(launch_env, "_a_parte_de_fora", parte_de_fora)
        escrevente = launch_env.EscreventeDoLancamento(lambda acao: acao())
        primeira, pendente = _foto(), _foto()
        escrevente.pedir(primeira)
        assert entrou.wait(10), "a primeira escrita não começou"
        escrevente.pedir(pendente)
        solta.set()
        t0 = time.perf_counter()
        escrevente.esvaziar_e_parar(10)
        parou_em = time.perf_counter() - t0
        assert escritas == [primeira.ordem, pendente.ordem], (
            f"a foto pendente não foi escrita no stop: {escritas}")
        assert parou_em < 2.0, (
            f"o stop esperou {parou_em:.1f} s: o fio voltou a esperar depois "
            "da última escrita, e o serviço sai só no teto")

    def test_a_devolucao_de_uma_foto_vencida_nao_pinta_por_cima_da_nova(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O fio põe as devoluções da foto M na fila do laço; antes de a fila
        andar, o arming escreve (e devolve na hora) a foto N, mais nova. Quando
        a fila anda, o recibo e as divergências continuam os da N.

        MORDIDA: tire a conferência da ordem do `carimbar` e do `publicar` em
        `_foto_do_lancamento` — o recibo volta ao da foto velha, e o vigia de
        1 Hz rematerializa e grita sobre o jogo que acabou de abrir.
        """
        monkeypatch.setattr(launch_env, "_ULTIMA_ORDEM_ESCRITA", 0)
        daemon = SimpleNamespace(config=SimpleNamespace(gamepad_emulation_enabled=False))
        velha = launch_env._foto_do_lancamento(daemon, no_fio=True)  # type: ignore[arg-type]
        daemon.config.gamepad_emulation_enabled = True
        nova = launch_env._foto_do_lancamento(daemon, no_fio=False)  # type: ignore[arg-type]
        fila: list[Any] = []
        monkeypatch.setattr(launch_env, "_a_parte_de_fora",
                            lambda foto, devolver: (devolver(lambda: foto.publicar([{
                                "appid": foto.ordem, "motivo": "m", "em_cena": False,
                                "profile": "p", "mascara_perfil": "x",
                                "mascara_viva": "y"}])), devolver(foto.carimbar)))
        # o fio escreve a velha e põe as devoluções na fila do laço…
        assert launch_env._escrever_o_lancamento(velha, fila.append) is True
        # …o arming escreve a nova, na hora, antes de a fila andar…
        assert launch_env._escrever_o_lancamento(nova) is True
        # …e a fila anda.
        for acao in fila:
            acao()
        assert daemon._launch_env_assinatura[1] is True, (
            f"o recibo voltou ao da foto velha: {daemon._launch_env_assinatura}")
        assert [d["appid"] for d in daemon._mascara_divergencias] == [nova.ordem], (
            "as divergências voltaram às da foto velha")


class TestOVigiaEsperaAEscritaEmVoo:
    def test_a_borda_com_a_escrita_em_voo_nao_vira_regravacao_nem_aviso(
        self, sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A borda de um jogador de co-op escreve (no fio) e arma o sossego de
        0,6 s; o tique de 1 Hz que vence o sossego chega com a escrita ainda em
        voo. O vigia espera a escrita pousar: não regrava, e não grita
        `launch_env_mudou_depois_do_exec` sobre o jogo de pé, que é o que a
        escrita na hora (o recibo carimbado na borda) sempre fez.

        E a espera acaba: depois de a escrita pousar, a mesa que muda sem borda
        (mais um físico, nenhum vpad novo) volta a ser julgada e regravada.

        MORDIDAS: tire a espera da escrita em voo de `rematerializar_se_sossegou`
        — o tique regrava e grita sobre uma mudança que a borda já escreveu;
        tire a volta do pouso (`self._devolver(pousou)`) do `_laco` do
        escrevente — a escrita fica em voo para sempre, e o vigia emudece.
        """
        eventos: list[str] = []

        class _Espiao:
            def _grava(self, evento: str, **_campos: Any) -> None:
                eventos.append(evento)

            info = warning = debug = _grava

        monkeypatch.setattr(launch_env, "logger", _Espiao())
        monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(launch_env, "_load_profiles", lambda _leitor: [])
        monkeypatch.setattr(launch_env, "_permite_uhid", lambda _daemon: True)
        monkeypatch.setattr(launch_env, "_device_ks_nos_lancadores", lambda: {})
        import hefesto_dualsense4unix.integrations.cura_por_estrada as cura

        monkeypatch.setattr(cura, "curar_todas_as_estradas", lambda: {})
        # O jogo do wrapper de pé: é com ele que o aviso honesto acorda.
        (tmp_path / "last_run").write_text(
            f"appid=1599660\nepoch={int(time.time())}\npid={os.getpid()}\n",
            encoding="utf-8")
        jogadores: dict[str, Any] = {}
        daemon = SimpleNamespace(
            is_native_mode=lambda: False,
            config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=SimpleNamespace(backend="uhid"),
            _coop_manager=SimpleNamespace(_players=jogadores),
            controller=SimpleNamespace(
                describe_controllers=lambda: [{"connected": True}] * 2))
        # Sem o escrevente, na hora: o recibo diz um vpad para dois físicos.
        launch_env.materialize_launch_env(daemon)  # type: ignore[arg-type]
        assert daemon._launch_env_assinatura[3] == ("uhid",)

        real = launch_env._a_parte_de_fora
        solta = threading.Event()

        def lenta(foto: Any, devolver: Any) -> None:
            solta.wait(10)
            real(foto, devolver)

        monkeypatch.setattr(launch_env, "_a_parte_de_fora", lenta)
        laco = asyncio.new_event_loop()
        escrevente = launch_env.armar_o_escrevente(laco.call_soon_threadsafe, laco)
        assert escrevente is not None
        try:
            async def borda_e_tres_tiques() -> tuple[bool, bool, bool, list[str]]:
                jogadores["p2"] = SimpleNamespace(vpad=SimpleNamespace(backend="uhid"))
                launch_env.materialize_launch_env(daemon)  # type: ignore[arg-type]
                launch_env.armar_rematerializacao(daemon, motivo="borda", agora=0.0)
                await asyncio.sleep(0.05)
                vencido = launch_env.JANELA_DE_SOSSEGO_SEC
                launch_env.vigiar_a_mesa(daemon, agora=vencido)
                em_voo = launch_env.rematerializar_se_sossegou(daemon, agora=vencido)
                solta.set()
                while escrevente.escritas < 1:
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.1)  # as devoluções voltam a este laço
                launch_env.vigiar_a_mesa(daemon, agora=vencido + 1.0)
                pousada = launch_env.rematerializar_se_sossegou(daemon, agora=vencido + 1.0)
                antes_da_mesa_mudar = list(eventos)
                # O terceiro tique: mais um físico na mesa, sem borda nenhuma.
                daemon.controller.describe_controllers = lambda: [{"connected": True}] * 3
                launch_env.vigiar_a_mesa(daemon, agora=vencido + 2.0)
                julgou = launch_env.rematerializar_se_sossegou(
                    daemon, agora=vencido + 2.0 + launch_env.JANELA_DE_SOSSEGO_SEC)
                while julgou and escrevente.escritas < 2:
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.1)
                return em_voo, pousada, julgou, antes_da_mesa_mudar

            em_voo, pousada, julgou, antes_da_mesa_mudar = laco.run_until_complete(
                asyncio.wait_for(borda_e_tres_tiques(), 20))
        finally:
            solta.set()
            launch_env.desarmar_o_escrevente(escrevente)
            laco.close()
        assert em_voo is False, "o tique regravou com a escrita da borda em voo"
        assert pousada is False, "o tique regravou o que a borda já tinha escrito"
        assert "launch_env_mudou_depois_do_exec" not in antes_da_mesa_mudar, antes_da_mesa_mudar
        assert "launch_env_rematerializado_no_sossego" not in antes_da_mesa_mudar, (
            antes_da_mesa_mudar)
        assert julgou is True, (
            "a mesa mudou sem borda depois da escrita pousar, e o vigia não a julgou: "
            "a escrita ficou em voo para sempre")
        assert "launch_env_rematerializado_no_sossego" in eventos, eventos
        assert daemon._launch_env_assinatura[3:5] == (("uhid", "uhid"), 3)
        assert escrevente.escritas == 2


class TestOServicoQueSaiTiraOSocket:
    def test_o_stop_com_teto_tira_o_socket_mesmo_com_a_escrita_em_voo(
        self, sem_escrevente: None, pasta_curta: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `shutdown` do serviço (`daemon/connection.py`) derruba o IPC com
        teto de 2 s, e as bordas do próprio shutdown (o co-op, o vpad) acabaram
        de pedir a escrita do lançamento ao fio. Com a escrita mais longa que o
        teto, o socket sai do disco do mesmo jeito: a espera pelo escrevente
        vem depois da limpeza do socket, que era tudo o que o `stop` fazia.

        MORDIDA: devolva a espera pelo escrevente para antes da limpeza do
        socket em `IpcServer.stop` — o teto cancela o `stop` no meio, e o
        socket fica no disco.
        """
        entrou = threading.Event()
        solta = threading.Event()

        def lenta(_foto: Any, _devolver: Any) -> None:
            entrou.set()
            solta.wait(10)

        monkeypatch.setattr(launch_env, "_foto_do_lancamento",
                            lambda _daemon, *, no_fio: _foto())
        monkeypatch.setattr(launch_env, "_a_parte_de_fora", lenta)
        servidor = _servidor(pasta_curta, daemon=SimpleNamespace())
        laco = asyncio.new_event_loop()
        try:
            async def subir_pedir_e_sair() -> bool:
                await servidor.start()
                assert servidor.socket_path.exists()
                launch_env.materialize_launch_env(SimpleNamespace())  # type: ignore[arg-type]
                assert await asyncio.to_thread(entrou.wait, 10), "a escrita não começou"
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(servidor.stop(), timeout=0.5)
                return servidor.socket_path.exists()

            ficou = laco.run_until_complete(subir_pedir_e_sair())
        finally:
            solta.set()
            laco.close()
        assert not ficou, (
            "o socket ficou no disco: o teto do shutdown cancelou o `stop` "
            "esperando a escrita do lançamento, antes da limpeza")


# ===========================================================================
# R5 — o servidor diz quem o segurou
# ===========================================================================
class TestOServidorDizQuemOSegurou:
    def test_o_pedido_de_300_ms_escreve_a_linha_e_o_de_20_nao(self, pasta_curta: Path) -> None:
        """Uma linha `ipc_lento metodo=<nome> ms=<n>` por pedido acima de
        100 ms, sem parâmetro nenhum (nenhum endereço vai ao diário).

        MORDIDA: tire a medida do `_dispatch` — nenhuma linha.
        """
        servidor = _servidor(pasta_curta, daemon=None)

        async def segura(segundos: float) -> dict[str, Any]:
            time.sleep(segundos)  # segura o laço, como um handler síncrono
            return {}

        servidor._handlers["teste.lento"] = lambda _p: segura(0.3)
        servidor._handlers["teste.ligeiro"] = lambda _p: segura(0.02)

        def pedido(metodo: str) -> bytes:
            return json.dumps({"jsonrpc": "2.0", "id": 1, "method": metodo,
                               "params": {"uniq": "aa:bb:cc:00:00:01"}}).encode()

        with structlog.testing.capture_logs() as registros:
            asyncio.run(servidor._dispatch(pedido("teste.lento")))
            asyncio.run(servidor._dispatch(pedido("teste.ligeiro")))
        lentos = [r for r in registros if r.get("event") == "ipc_lento"]
        assert [r["metodo"] for r in lentos] == ["teste.lento"], (  # (noqa-acento) chave do diário
            f"as linhas `ipc_lento`: {lentos}")
        assert 250 <= lentos[0]["ms"] < 2000
        chaves = {"event", "metodo", "ms", "log_level"}  # (noqa-acento) chave do diário
        assert set(lentos[0]) <= chaves, (
            f"a linha levou mais que o nome e o tempo: {lentos[0]}")
        assert "aa:bb:cc" not in repr(registros)


# ===========================================================================
# R6 — a pergunta abandonada não roda; o pedido que muda roda
# ===========================================================================
class TestAPerguntaAbandonadaNaoRoda:
    def test_o_laco_preso_pula_so_a_pergunta_de_quem_foi_embora(
        self, sem_escrevente: None, pasta_curta: Path
    ) -> None:
        """O laço preso 500 ms de propósito. Três clientes mandam e fecham: a
        `daemon.state_full`, um método que muda (de mentira) e o
        `daemon.status` com o marker do lançamento fresco. A pergunta roda
        zero vezes, o que muda uma, e o arming do lançamento é agendado uma.

        MORDIDAS: tire a conferência — a pergunta roda; aplique-a a todo
        método — o que muda não roda; ponha o `daemon.status` na lista
        fechada — o arming não acontece.
        """
        daemon = SimpleNamespace(_launch_armed_for=None, is_paused=lambda: False,
                                 is_native_mode=lambda: False)
        servidor = _servidor(pasta_curta, daemon=daemon)
        rodou = {"pergunta": 0, "muda": 0, "armou": 0}

        async def pergunta(_p: dict[str, Any]) -> dict[str, Any]:
            rodou["pergunta"] += 1
            return {}

        async def muda(_p: dict[str, Any]) -> dict[str, Any]:
            rodou["muda"] += 1
            return {}

        async def armar() -> None:
            rodou["armou"] += 1

        servidor._handlers["daemon.state_full"] = pergunta
        servidor._handlers["teste.muda"] = muda
        servidor._wrapper_marker_cached = lambda: (1599660, int(time.time()))
        servidor._armar_launch = armar
        with _NoFio(servidor) as no_fio:
            # o laço preso: os três pedem e vão embora enquanto ele não anda
            no_fio.laco.call_soon_threadsafe(time.sleep, 0.5)
            time.sleep(0.05)
            for metodo in ("daemon.state_full", "teste.muda", "daemon.status"):
                _pedir(servidor.socket_path, metodo, fechar_sem_ler=True)
            prazo = time.monotonic() + 5
            while time.monotonic() < prazo and (rodou["muda"] < 1 or rodou["armou"] < 1):
                time.sleep(0.02)
            time.sleep(0.2)  # a pergunta, se fosse rodar, já teria rodado
        assert rodou["muda"] == 1, f"o pedido que muda não rodou: {rodou}"
        assert rodou["armou"] == 1, f"o arming do lançamento não foi agendado: {rodou}"
        assert rodou["pergunta"] == 0, (
            f"a pergunta de quem já foi embora rodou: {rodou}")

    def test_quem_so_fechou_a_escrita_ainda_espera_a_resposta(self) -> None:
        """O `socat` e o `nc -N` fecham só a escrita e esperam a resposta: o
        `POLLHUP` separa quem foi embora de quem só terminou de pedir."""
        from hefesto_dualsense4unix.daemon.ipc_server import _o_cliente_ja_foi

        def escritor(sock: socket.socket) -> Any:
            return SimpleNamespace(get_extra_info=lambda chave: sock if chave == "socket" else None)

        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        with a, b:
            assert _o_cliente_ja_foi(escritor(a)) is False
            b.shutdown(socket.SHUT_WR)
            assert _o_cliente_ja_foi(escritor(a)) is False
            b.close()
            assert _o_cliente_ja_foi(escritor(a)) is True


# ===========================================================================
# R7 — o cliente do IPC não importa o servidor
# ===========================================================================
@pytest.mark.parametrize("cliente", ["hefesto_dualsense4unix.cli.ipc_client",
                                     "hefesto_dualsense4unix.app.ipc_bridge"])
def test_o_cliente_nao_importa_o_servidor(cliente: str) -> None:
    """A CLI, a bandeja e a janela importam o cliente; o servidor do daemon
    (e os handlers) não vêm junto.

    MORDIDA: devolva o import das constantes a `daemon.ipc_server` — as duas
    linhas aparecem no `-X importtime`.
    """
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"))
    r = subprocess.run([sys.executable, "-X", "importtime", "-c", f"import {cliente}"],
                       capture_output=True, text=True, timeout=120, env=ambiente,
                       cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr[-1500:]
    servidor = [linha for linha in r.stderr.splitlines()
                if linha.rstrip().endswith(("daemon.ipc_server", "daemon.ipc_handlers"))]
    assert servidor == [], f"`{cliente}` importou o servidor do daemon:\n" + "\n".join(servidor)
