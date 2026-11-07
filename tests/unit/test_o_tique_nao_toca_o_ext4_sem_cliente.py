"""O tique não toca o ext4 sem cliente.

O-TIQUE-NAO-TOCA-O-EXT4-SEM-CLIENTE-01. Medido em 07/11/2026 com o `Daemon.run` de verdade, sem
cliente, por 12 s de pilha no fio do laço: 11 toques por segundo sem perfil ativo e 23 com ele
(a luz a 2 Hz e o tato a 1 Hz no perfil e no `maquina.json`, as duas bandeiras do pad a 0,5 Hz, a
troca adiada a 0,5 Hz, o `which pactl` a 0,5 Hz).

Com a configuração de produção (o IPC e o `AutoSwitcher` ligados), mais 18 toques por segundo: o
`_tick` do autoswitch a 2 Hz na lista de exclusão, nos perfis e no `session.json`.

A régua roda o mesmo `Daemon.run`, com a configuração de produção; só o UDP fica desligado, porque
a porta dele é do serviço da máquina. O `stat` do `pactl` em `_uma_volta` fica fora da conta: quem
o faz é o desvio do servidor de som da suíte (`tests/conftest.py`), e no produto o `pactl subscribe`
sobe uma vez e fica de pé. A causa dos comandos presos segue não provada: esta régua não a cura.

Mordidas (arranque a cura, veja reprovar, devolva):

- `perfil_ativo` da luz: chame `_ler_o_perfil_ativo(nome)` direto;
- `receita_ativa` do tato: chame `_ler_a_receita(nome)` direto;
- `aplicar_gamepad_para_multiplos_controles`: `load_gamepad_preference()` direto;
- `_a_troca_que_o_jogo_adiou`: `troca.troca_pendente()` direto;
- `ouvinte_do_som_loop`: `shutil.which("pactl")` direto;
- `CadernoDoTique.resposta`: tire o aviso da pergunta nova, e a troca de perfil espera o período;
- `CadernoDoTique._ler`: tire a guarda da pergunta, e a resposta velha entra por cima da nova;
- `aplicar_gamepad_para_multiplos_controles`: tire o `if lida is None`, e o opt-out do usuário
  perde para a primeira leitura vazia;
- `CadernoDoTique._ler`: tire o `porta.chegou`, e a troca de perfil espera o período da porta;
- `Passo.__call__` da luz e `Passo.receita_de_agora` do tato: tire o `a_resposta_chegou`;
- `AutoSwitcher._tick`: tire o `com_os_perfis_lidos`;
- `AutoSwitcher._decidir`: `self._perfil_da_escolha()` direto;
- `AutoSwitcher._na_exclusao`: `self._na_lista_de_exclusao(wm_class)` direto;
- `_modo_jogo_padrao_sob_o_freestyle`: `self._o_freestyle_diz_o_modo()` direto;
- `ver_os_comandos`: `self._perfis_do(MEU_COMANDO)` direto;
- `ao_conectar`: `self._perfis_do(CONTROLE_CONECTADO)` direto.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import caderno_do_tique as ct
from hefesto_dualsense4unix.daemon.caderno_do_tique import CadernoDoTique, no_caderno
from hefesto_dualsense4unix.daemon.lifecycle import ADIADO_LOCK_MANUAL, Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as la
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems.eventos_do_perfil import (
    CONTROLE_CONECTADO,
    MEU_COMANDO,
    EventosDoPerfil,
)
from hefesto_dualsense4unix.integrations import lista_de_exclusao, virtual_pad, window_detect
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.manager import ligar_o_freestyle
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from tests.unit.test_o_jogo_seguinte_veste_a_propria_roupa import _Pad

DORME_S = 2.0
PERFIL = "Ensaio do Tique"
JOGO = "steam_app_9931881"
_JANELAS: dict[str, dict[str, Any]] = {
    "sem janela": {},
    "janela qualquer": {"wm_class": "firefox", "pid": 77},
    "lançador": {"wm_class": "steam", "pid": 78},
    "jogo com perfil": {"wm_class": JOGO, "pid": 79, "wm_name": "Jogo"},
    "jogo sem perfil": {"wm_class": "steam_app_9931882", "pid": 80, "wm_name": "Outro"},
    "jogo na lista de exclusão": {"wm_class": "steam_app_9931883", "pid": 81},
    "com o Freestyle": {"wm_class": "firefox", "pid": 77},
}
_FORA_DA_CONTA = ("/dev/", "/proc/", "/sys/", "/run/")
_STAT = os.stat


class _Espia:
    def __init__(self) -> None:
        self.fio: int | None = None
        self.vistos: list[str] = []

    def _anotar(self, evento: str, caminho: Any) -> None:
        texto = str(caminho)
        if (
            self.fio == threading.get_ident()
            and not texto.endswith((".py", ".pyc"))
            and "__pycache__" not in texto
            and not texto.isdigit()
            and not texto.startswith(_FORA_DA_CONTA)
            and "_uma_volta" not in _pilha()
        ):
            self.vistos.append(f"{evento} {texto} <- {_pilha()}")

    def auditar(self, evento: str, args: tuple[Any, ...]) -> None:
        if evento in {"open", "os.scandir", "os.listdir", "os.mkdir", "os.rename", "os.remove"}:
            self._anotar(evento, args[0] if args else "")

    def stat(self, caminho: Any, *a: Any, **k: Any) -> os.stat_result:
        self._anotar("stat", caminho)
        return _STAT(caminho, *a, **k)


def _pilha(acima: int = 2) -> str:
    quadro: Any = sys._getframe(acima)
    nomes: list[str] = []
    while quadro is not None and len(nomes) < 8:
        if "/src/hefesto" in quadro.f_code.co_filename:
            nomes.append(quadro.f_code.co_name)
        quadro = quadro.f_back
    return " < ".join(nomes)


_ESPIA = _Espia()
sys.addaudithook(_ESPIA.auditar)


@pytest.fixture(autouse=True)
def _espia_desligada() -> Iterator[None]:
    yield
    _ESPIA.fio = None


class _Janela:
    """O leitor de janela de mentira, no lugar do da sessão gráfica."""

    backend_name = "xlib"

    def __init__(self, info: dict[str, Any]) -> None:
        self.info = info

    def __call__(self) -> dict[str, Any]:
        return dict(self.info)

    def conexao_provada(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _janela_e_pad_dublados(monkeypatch: pytest.MonkeyPatch) -> None:
    """A janela vem da régua, e o modo jogo padrão não sobe pad de verdade."""
    monkeypatch.setattr(window_detect, "build_window_reader", lambda *_a, **_k: _Janela({}))
    monkeypatch.setattr(
        virtual_pad, "make_virtual_pad",
        lambda flavor, *, identity=None, roupa=None, caminho=None, **_k: _Pad(
            flavor, identity, roupa, caminho))


def _daemon(*, com_perfil: bool) -> Daemon:
    estados = [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        for _ in range(4)
    ]
    daemon = Daemon(
        controller=FakeController(transport="usb", states=estados),
        config=DaemonConfig(poll_hz=120, udp_enabled=False),
    )
    if com_perfil:
        loader.save_profile(Profile(name=PERFIL, match=MatchAny(type="any")))
        daemon.store.set_active_profile(PERFIL)
    return daemon


async def _rodar(
    daemon: Daemon, aquecer_s: float, medir_s: float, ao_subir: Callable[[], None] = lambda: None,
) -> tuple[list[str], float]:
    """O `Daemon.run` por `medir_s`, depois de subir: o que o fio do laço tocou e os tiques/s."""
    tarefa = asyncio.create_task(daemon.run())
    await asyncio.sleep(aquecer_s)
    ao_subir()
    _ESPIA.vistos = []
    antes = daemon.store.counter("poll.tick")
    _ESPIA.fio = threading.get_ident()
    await asyncio.sleep(medir_s)
    _ESPIA.fio = None
    tiques = (daemon.store.counter("poll.tick") - antes) / medir_s
    daemon.stop()
    await asyncio.wait_for(tarefa, 10.0)
    return _ESPIA.vistos, tiques


@pytest.mark.asyncio
@pytest.mark.parametrize("com_perfil", [False, True], ids=["sem perfil ativo", "com perfil ativo"])
async def test_o_tique_sem_cliente_nao_toca_arquivo_no_fio_do_laco(
    monkeypatch: pytest.MonkeyPatch, com_perfil: bool,
) -> None:
    """Três segundos de serviço de pé cobrem a luz, o tato, o pad, a troca e o ouvinte."""
    daemon = _daemon(com_perfil=com_perfil)
    monkeypatch.setattr(os, "stat", _ESPIA.stat)

    vistos, tiques = await _rodar(daemon, 1.5, 3.0)

    assert vistos == []
    assert tiques > 40, f"a régua não mediu nada: {tiques:.1f} tiques por segundo"


@pytest.mark.asyncio
@pytest.mark.parametrize("cena", _JANELAS, ids=list(_JANELAS))
async def test_o_autoswitch_nao_toca_arquivo_no_fio_do_laco(
    monkeypatch: pytest.MonkeyPatch, cena: str,
) -> None:
    """Em toda janela o tique do autoswitch só lê memória, também com o Freestyle ligado."""
    monkeypatch.setattr(
        window_detect, "build_window_reader", lambda *_a, **_k: _Janela(_JANELAS[cena]))
    if cena == "jogo na lista de exclusão":
        monkeypatch.setattr(lista_de_exclusao, "contem", _sempre_na_lista)
    daemon = _daemon(com_perfil=True)
    loader.save_profile(Profile(name="Jogo", match=MatchCriteria(window_class=[JOGO])))
    monkeypatch.setattr(os, "stat", _ESPIA.stat)

    def ao_subir() -> None:
        if cena == "com o Freestyle":
            ligar_o_freestyle(daemon.store, True)

    vistos, tiques = await _rodar(daemon, 1.0, 2.0, ao_subir=ao_subir)

    assert vistos == []
    assert tiques > 40, f"a régua não mediu nada: {tiques:.1f} tiques por segundo"


def _sempre_na_lista(*_a: Any, **_k: Any) -> bool:
    return True


_OS_LEITORES: dict[str, tuple[Any, str]] = {
    "perfil": (loader, "perfil_em_disco"),
    "computador": (opc, "o_computador"),
    "preferência do pad": (session, "load_gamepad_preference"),
    "troca adiada": (troca, "troca_pendente"),
    "which": (shutil, "which"),
    "perfis do autoswitch": (loader, "perfis_para_consulta"),
    "escolha do autoswitch": (session, "a_escolha_do_usuario"),
    "exclusão do autoswitch": (lista_de_exclusao, "contem"),
}
_LIDOS_NA_SUBIDA = {"exclusão do autoswitch"}


@pytest.mark.asyncio
@pytest.mark.parametrize("leitor", _OS_LEITORES, ids=list(_OS_LEITORES))
async def test_o_tique_nao_cai_com_cada_leitor_dormindo(
    monkeypatch: pytest.MonkeyPatch, leitor: str,
) -> None:
    """Cada porta dorme 2 s a cada leitura, uma por vez: o caderno atrasa, e a entrada não."""
    monkeypatch.setattr(
        window_detect, "build_window_reader",
        lambda *_a, **_k: _Janela(_JANELAS["janela qualquer"]))
    daemon = _daemon(com_perfil=True)
    fios: list[str] = []
    dono, nome = _OS_LEITORES[leitor]
    original = getattr(dono, nome)

    def lento(*a: Any, **k: Any) -> Any:
        if "_uma_volta" in _pilha(1):
            return original(*a, **k)
        fios.append(f"{threading.current_thread().name} {_pilha(1)}")
        time.sleep(DORME_S)
        return original(*a, **k)

    with pytest.MonkeyPatch.context() as dublar:
        if leitor in _LIDOS_NA_SUBIDA:
            dublar.setattr(dono, nome, lento)
        _vistos, tiques = await _rodar(
            daemon, 1.0, 4.5 if leitor == "preferência do pad" else 2.5,
            ao_subir=lambda: dublar.setattr(dono, nome, lento))

    assert fios, f"{leitor} não dormiu: a régua não mediu essa porta"
    assert [f for f in fios if f.startswith(threading.main_thread().name)] == []
    assert tiques > 40, f"o tique caiu a {tiques:.1f} por segundo"


@pytest.mark.parametrize(
    ("pergunta", "momento"),
    [(EventosDoPerfil.ver_os_comandos, MEU_COMANDO),
     (EventosDoPerfil.ao_conectar, CONTROLE_CONECTADO)],
    ids=["Meu comando", "Controle conectado"],
)
def test_os_eventos_do_perfil_leem_os_perfis_fora_do_laco(pergunta: Any, momento: str) -> None:
    fios: list[str] = []

    def ler() -> list[Any]:
        fios.append(threading.current_thread().name)
        return []

    async def corpo() -> None:
        await pergunta(EventosDoPerfil(SimpleNamespace(), _sem_ativar, ler))

    asyncio.run(corpo())

    assert fios and threading.main_thread().name not in fios, f"{momento} leu no laço"


async def _sem_ativar(_nome: str) -> None:
    pytest.fail("nenhum perfil entra sem perfil")


@pytest.mark.asyncio
async def test_o_perfil_da_luz_acompanha_o_arquivo_e_a_troca() -> None:
    """A escrita no arquivo e a troca de perfil chegam à luz sem o laço ir ao disco."""
    daemon = _daemon(com_perfil=False)
    loader.save_profile(Profile(name="Um", match=MatchAny(type="any")))
    loader.save_profile(Profile(name="Dois", match=MatchAny(type="any")))
    daemon.store.set_active_profile("Um")

    async def ate(pedido: str, prazo_s: float) -> float:
        t0 = time.monotonic()
        while time.monotonic() - t0 < prazo_s:
            lido = la.perfil_ativo(daemon)
            if lido is not None and lido.name == pedido:
                return time.monotonic() - t0
            await asyncio.sleep(0.01)
        pytest.fail(f"a luz não chegou a {pedido!r} em {prazo_s} s")

    await ate("Um", 2.0)
    daemon.store.set_active_profile("Dois")
    assert await ate("Dois", 0.4) < 0.4, "a troca de perfil esperou o período do caderno"


@pytest.mark.asyncio
async def test_a_receita_do_tato_vem_do_caderno_e_a_primeira_e_a_desligada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antes da leitura, a desligada; depois, a do perfil, que é a do `_ler_a_receita`."""
    daemon = _daemon(com_perfil=True)
    receita = tv.Receita(vibracao_por_tiro=True)
    monkeypatch.setattr(tv, "_ler_a_receita", lambda _nome: receita)

    assert tv.receita_ativa(daemon) is tv.DESLIGADA
    for _volta in range(200):
        if tv.receita_ativa(daemon) is receita:
            return
        await asyncio.sleep(0.005)
    pytest.fail("a receita lida não chegou à porta")


@pytest.mark.asyncio
async def test_a_troca_de_perfil_chega_a_luz_e_ao_tato_no_periodo_de_sempre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A porta pergunta no período de sempre, e a resposta entra no tique seguinte, não no outro.

    Sem o aviso, a luz chega a dois períodos da troca, e o tato também: 1 s e 2 s.
    """
    daemon = _daemon(com_perfil=False)
    loader.save_profile(Profile(name="Um", match=MatchAny(type="any")))
    loader.save_profile(Profile(name="Dois", match=MatchAny(type="any")))
    daemon.store.set_active_profile("Um")
    luz = la.Passo(daemon, la.LuzAnimada(lambda *_a: None, lambda *_a: None))
    tato = tv.Passo(daemon, tv.TatoVivo())
    receitas = {"Um": tv.Receita(forca_do_toque=0.1), "Dois": tv.Receita(forca_do_toque=0.2)}
    monkeypatch.setattr(la, "plano_do_perfil", lambda perfil, *_a, **_k: {"nome": perfil.name})
    monkeypatch.setattr(tv, "_ler_a_receita", lambda nome: receitas[nome])
    agora = time.monotonic()

    async def tiques_ate(chegou: Callable[[], bool]) -> float:
        nonlocal agora
        t0 = agora
        while agora - t0 < 3.0:
            agora = time.monotonic()
            luz(agora)
            tato.receita_de_agora(agora)
            if chegou():
                return agora - t0
            await asyncio.sleep(0.005)
        pytest.fail("a troca não chegou")

    await tiques_ate(
        lambda: luz._plano.get("nome") == "Um" and tato.receita_vigente is receitas["Um"])
    luz._lido_em, tato._lida_em = agora, agora
    daemon.store.set_active_profile("Dois")

    gasto_da_luz = await tiques_ate(lambda: luz._plano.get("nome") == "Dois")
    gasto_do_tato = gasto_da_luz + await tiques_ate(
        lambda: tato.receita_vigente is receitas["Dois"])

    assert gasto_da_luz < 1.5 * la.RELEITURA_DO_PLANO_S, f"a luz levou {gasto_da_luz:.2f} s"
    assert gasto_do_tato < 1.5 * tv.RELEITURA_DA_RECEITA_S, f"o tato levou {gasto_do_tato:.2f} s"


def test_fora_do_laco_a_porta_le_na_hora() -> None:
    """A CLI, a janela e o teste sem laço leem o disco, como sempre."""
    lidas: list[int] = []
    resposta = no_caderno(
        SimpleNamespace(), "porta", None, lambda: lidas.append(1) or "lido", periodo_s=1.0)

    assert resposta == "lido"
    assert lidas == [1]


def test_a_leitura_que_falha_mantem_a_resposta_de_antes() -> None:
    estado = {"quebrada": False, "lidas": 0}

    def ler() -> str:
        estado["lidas"] = int(estado["lidas"]) + 1
        if estado["quebrada"]:
            raise OSError("disco")
        return "boa"

    async def corpo() -> Any:
        daemon = SimpleNamespace()
        for _volta in range(100):
            if no_caderno(daemon, "porta", None, ler, periodo_s=0.01) == "boa":
                break
            await asyncio.sleep(0.01)
        estado["quebrada"] = True
        vistas = int(estado["lidas"])
        while int(estado["lidas"]) < vistas + 3:
            await asyncio.sleep(0.01)
        return no_caderno(daemon, "porta", None, ler, periodo_s=0.01)

    assert asyncio.run(corpo()) == "boa"


def test_a_resposta_velha_nao_entra_por_cima_da_pergunta_nova() -> None:
    """A leitura presa de «a» volta depois da troca para «b»: vale a de «b»."""
    solta_a = threading.Event()
    lendo_a = threading.Event()

    def ler_a() -> str:
        lendo_a.set()
        solta_a.wait(3.0)
        return "de a"

    async def corpo() -> Any:
        daemon = SimpleNamespace()
        no_caderno(daemon, "porta", "a", ler_a, periodo_s=60.0)
        while not lendo_a.is_set():
            await asyncio.sleep(0.005)
        no_caderno(daemon, "porta", "b", lambda: "de b", periodo_s=60.0)
        solta_a.set()
        for _volta in range(200):
            resposta = no_caderno(daemon, "porta", "b", lambda: "de b", periodo_s=60.0)
            if resposta is not None:
                return resposta
            await asyncio.sleep(0.005)
        return None

    assert asyncio.run(corpo()) == "de b"


def test_o_fio_do_caderno_acaba_com_o_laco() -> None:
    async def corpo() -> CadernoDoTique:
        return CadernoDoTique(asyncio.get_running_loop())

    caderno = asyncio.run(corpo())
    caderno._acordar.set()
    caderno._fio.join(ct.TETO_DA_ESPERA_S + 1.0)

    assert not caderno._fio.is_alive()


def test_a_preferencia_por_ler_adia_e_nao_liga_o_pad_por_cima_do_opt_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Antes da primeira leitura o tique não sabe do opt-out: dois controles na mesa esperam."""
    daemon = _daemon(com_perfil=False)
    monkeypatch.setattr(daemon, "contar_controles_fisicos", lambda: 2)
    ligados: list[bool] = []
    monkeypatch.setattr(
        daemon, "set_gamepad_emulation", lambda *a, **k: ligados.append(True) or True)
    daemon._emu_manual_ts = float("-inf")

    async def corpo() -> str:
        return daemon.aplicar_gamepad_para_multiplos_controles()

    assert asyncio.run(corpo()) == ADIADO_LOCK_MANUAL
    assert ligados == []
