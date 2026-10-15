"""D-1410-O-APLICAR-SEGURA: o «Aplicar» de outro perfil segura contra o autoswitch.

A queixa (14/10/2026): *«Usar o «Aplicar» em outro perfil não segura: em uns 12 s
a escolha feita à mão volta por cima dele.»* A regra de produto: *«Ele deveria ficar
sempre com o perfil do último jogo aberto ou ativado. Até que eu mude ou outro
jogo inicie»*. O «Aplicar» e o «Voltar à de ontem» passam pelo mesmo
`ProfileManager.reaplicar(prender=True)`, que arma a trava da troca à mão sem gravar a escolha.

Parte 3 (respostas, 14/10/2026): **só o «Aplicar» prende**. O ajuste numa aba grava e reaplica
o perfil que já vale pelo mesmo `profile.reaplicar`, mas sem o ``prender``: a trava não arma e o
autoswitch segue trocando por janela. O gesto leva o ``prender`` por parâmetro do IPC, com o padrão
sem trava, e as réguas daqui mordem para os dois lados.
"""  # noqa-acento: citação literal

from __future__ import annotations

import ast
import pathlib
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig
from hefesto_dualsense4unix.utils import session
from tests.unit.test_foco_errante_01_a_janela_da_steam_nao_tira_o_perfil import (
    CLASSE_DO_JOGO,
    JANELA_DA_NAVEGACAO,
    JANELA_DO_JOGO,
    _bancada,
    _perfil,
    _switcher,
    perfis_isolados,  # noqa: F401
)

JANELA_DO_TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"}

#: Uma segunda janela com perfil próprio que não é jogo: o navegador.
JANELA_DO_NAVEGADOR = {"wm_class": "firefox", "wm_name": "Mozilla Firefox"}


def _a_montagem(*, prender: bool = True):  # type: ignore[no-untyped-def]
    """O terminal em foco, o último jogo no disco, a escolha no `session.json`, e o «Aplicar».

    ``prender=False`` é o reaplicar de um ajuste numa aba (o `profile.reaplicar` sem o gesto).
    """
    jogo = _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90)
    jogo.mode = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    manager, store = _bancada([
        jogo,
        _perfil("lure", janela="steam_app_1599660", prioridade=80),
        _perfil("fliperama", janela="retroarch", prioridade=40),
        _perfil("navegacao", janela=JANELA_DA_NAVEGACAO["wm_class"], prioridade=50),
        _perfil("navegador", janela=JANELA_DO_NAVEGADOR["wm_class"], prioridade=45),
    ])
    session.gravar_a_escolha("lure")
    session.lembrar_o_ultimo_jogo("sackboy")
    store.set_active_profile("sackboy")
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(4):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "sackboy", "premissa: o terminal fica no último jogo"

    manager.reaplicar("fliperama", prender=prender)
    assert store.active_profile == "fliperama"
    return manager, store, sw


def _terminal(  # type: ignore[no-untyped-def]
    sw, de: float, ate: float, janela: dict[str, str] | None = None
) -> None:
    t = de
    while t <= ate:
        sw._tick(dict(janela or JANELA_DO_TERMINAL), t)
        t += 0.5


@pytest.mark.usefixtures("perfis_isolados")
def test_o_aplicar_segura_aos_12_e_aos_60_segundos() -> None:
    """D-1410-O-APLICAR-SEGURA: o terminal não devolve a escolha nem o último jogo por cima.

    MORDIDA: tire o ``armar_a_trava_da_mao`` do ramo da reaplicação no ``_ativar``
    (`profiles/manager.py`) e, aos 12 s, o «lure» da escolha passa por cima.
    """
    _manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 2.0 + 12.5)
    assert store.active_profile == "fliperama", "aos 12 s a escolha passou por cima do «Aplicar»"
    _terminal(sw, 15.0, 2.0 + 60.0)
    assert store.active_profile == "fliperama", "aos 60 s a escolha passou por cima do «Aplicar»"
    assert session.a_escolha_dela() == "lure", "o «Aplicar» virou a escolha"
    assert session.o_ultimo_jogo() == "sackboy", "o último jogo saiu do disco"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_com_perfil_em_foco_solta_a_trava_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: outro jogo com perfil entrando em foco solta a trava e entra."""
    _manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 20.0)
    sw._tick(dict(JANELA_DO_JOGO), 20.5)
    sw._tick(dict(JANELA_DO_JOGO), 21.5)
    assert store.active_profile == "sackboy", "o jogo com perfil não entrou"
    assert not store.manual_profile_lock_active(time.monotonic()), "a trava não soltou"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_ativar_de_outro_perfil_troca_depois_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: o próximo gesto («Ativar» de outro perfil) troca, e fica."""
    manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 10.0)
    manager.activate("lure", origin="manual")
    _terminal(sw, 10.5, 70.0)
    assert store.active_profile == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_lancado_solta_a_trava_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: outro jogo lançado solta a trava, entra, e o terminal o mantém.

    MORDIDA: tire o ``soltar_a_trava_da_mao`` do ramo ``origin == "launch"`` no ``_ativar``
    (`profiles/manager.py`) e a trava do «Aplicar» sobrevive ao lançamento.
    """
    manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 10.0)
    manager.activate("lure", origin="launch")
    assert not store.manual_profile_lock_active(time.monotonic()), "o lançamento não soltou a trava"
    _terminal(sw, 10.5, 70.0)
    assert store.active_profile == "lure", "o jogo lançado não ficou"
    assert session.o_ultimo_jogo() == "lure", "o lançamento não virou o último jogo"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_ajuste_de_aba_nao_prende_e_o_autoswitch_segue_trocando() -> None:
    """Parte 3: o reaplicar SEM o gesto não arma a trava, e a janela volta a mandar aos 12 s.

    É o outro lado da régua do «Aplicar»: o ajuste numa aba (``prender`` ausente) deixa o
    autoswitch livre, e o terminal devolve o último jogo. MORDIDA: arme a trava em todo
    reaplicar (``elif reaplicacao:`` sem o ``and prender``) e o perfil fica preso em «fliperama».
    """
    _manager, store, sw = _a_montagem(prender=False)
    assert not store.manual_profile_lock_active(time.monotonic()), "o ajuste armou a trava"
    _terminal(sw, 2.0, 2.0 + 13.0)
    assert store.active_profile != "fliperama", "o ajuste de aba prendeu o autoswitch"
    assert store.active_profile in {"lure", "sackboy"}


@pytest.mark.usefixtures("perfis_isolados")
def test_depois_do_ajuste_de_aba_a_janela_com_perfil_troca() -> None:
    """Parte 3: depois de um ajuste numa aba, o Kodi e o navegador em foco trocam o perfil.

    MORDIDA: arme a trava em todo reaplicar (``elif reaplicacao:`` sem o ``and prender``) e o
    Kodi em foco não tira o «fliperama».
    """
    _manager, store, sw = _a_montagem(prender=False)
    _terminal(sw, 2.0, 6.0, JANELA_DA_NAVEGACAO)
    assert store.active_profile == "navegacao", "o Kodi em foco não trocou depois do ajuste"
    _terminal(sw, 6.5, 10.0, JANELA_DO_NAVEGADOR)
    assert store.active_profile == "navegador", "o navegador em foco não trocou depois do ajuste"


@pytest.mark.usefixtures("perfis_isolados")
def test_depois_do_aplicar_a_janela_que_nao_e_jogo_nao_tira_o_perfil() -> None:
    """D-1410-O-APLICAR-SEGURA: o «Aplicar» segura até o próximo gesto ou outro jogo.

    O Kodi e o navegador têm perfil, mas não são jogo: em foco, não passam por cima do que ela
    aplicou. É o outro lado da régua do ajuste de aba. MORDIDA: troque o
    ``elif reaplicacao and prender`` do ``_ativar`` por ``elif False`` e o Kodi tira o «fliperama».
    """
    _manager, store, sw = _a_montagem(prender=True)
    _terminal(sw, 2.0, 20.0, JANELA_DA_NAVEGACAO)
    assert store.active_profile == "fliperama", "o Kodi passou por cima do «Aplicar»"
    _terminal(sw, 20.5, 40.0, JANELA_DO_NAVEGADOR)
    assert store.active_profile == "fliperama", "o navegador passou por cima do «Aplicar»"


class _PonteQueAnota:
    """O dublê da ponte: anota o ``prender`` de cada `profile_reaplicar`."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, bool]] = []

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> dict[str, Any]:
        self.pedidos.append((nome, prender))
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> bool:
        return True

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        return {"status": "ok"}


def test_a_ponte_so_manda_o_prender_quando_o_gesto_pede(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ponte real leva ``prender: true`` no IPC só com o gesto, e o padrão não leva nada."""
    from hefesto_dualsense4unix.interface.pacotes import ponte

    enviados: list[dict[str, Any]] = []

    def _safe_call(metodo: str, params: dict[str, Any], timeout: float = 0.0) -> tuple[bool, Any]:
        assert metodo == "profile.reaplicar"
        enviados.append(dict(params))
        return True, {"active_profile": params["name"]}

    monkeypatch.setattr(ponte._b, "_safe_call", _safe_call)
    ponte.profile_reaplicar("X")
    ponte.profile_reaplicar("X", prender=False)
    ponte.profile_reaplicar("X", prender=True)
    assert enviados == [{"name": "X"}, {"name": "X"}, {"name": "X", "prender": True}]


def test_o_aplicar_do_rodape_prende(monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Aplicar» do rodapé pede ``prender``.

    MORDIDA: tire o ``prender=True`` do ``rodape.aplicar``.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto, perfil, rodape

    monkeypatch.setattr(rodape, "perfil_do_rodape", lambda _state: "Sackboy")
    monkeypatch.setattr(perfil, "a_volta_do_perfil", lambda _ctx, _p: None)
    monkeypatch.setattr(perfil, "com_a_carona", lambda frase="": "")
    ponte = _PonteQueAnota()
    rodape.aplicar(Contexto(state={}, mesa=[], conectados=[], estados={}), {}, ponte)
    assert ponte.pedidos == [("Sackboy", True)], "o «Aplicar» não pediu a trava"


def test_o_voltar_a_de_ontem_prende(monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Voltar à de ontem» segue a mesma regra do «Aplicar»: pede ``prender``."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_perfil_do_editor", lambda _ctx: "Sackboy")
    monkeypatch.setattr(a10_perfis, "_valendo", lambda _ctx: "Sackboy")
    monkeypatch.setattr(a10_perfis, "_com_a_carona", lambda frase="": frase)
    monkeypatch.setattr(
        loader, "restaurar_do_historico",
        lambda n: (pathlib.Path(f"/perfis/{n}.json"), pathlib.Path("2026-09-03T04-00-00.json")))
    ponte = _PonteQueAnota()
    a10_perfis.voltar_a_de_ontem(Contexto(state={}, mesa=[], conectados=[], estados={}), {}, ponte)
    assert ponte.pedidos == [("Sackboy", True)], "o «Voltar à de ontem» não pediu a trava"


def test_o_reaplicar_do_ajuste_de_aba_nao_prende(monkeypatch: pytest.MonkeyPatch) -> None:
    """O funil dos ajustes das abas (``perfil.reaplicar``) NÃO pede ``prender``.

    MORDIDA: ponha ``prender=True`` no ``p.profile_reaplicar`` de ``perfil.reaplicar``.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto, perfil

    ponte = _PonteQueAnota()
    ctx = Contexto(state={"active_profile": "Sackboy"}, mesa=[], conectados=[], estados={})
    perfil.reaplicar("Sackboy", ctx, ponte)
    assert ponte.pedidos == [("Sackboy", False)], "o ajuste de aba pediu a trava"


def test_so_o_rodape_e_o_voltar_a_de_ontem_pedem_a_trava() -> None:
    """Dono único da distinção: só os gestos da lista falam ``prender`` no ``src/``.

    Um terceiro gesto que prenda sem estar na lista é a distinção que escorre; é decisão de produto
    quais gestos prendem (parte 3 da D-1410-O-APLICAR-SEGURA). A varredura pega o argumento
    ``prender`` não falso em QUALQUER chamada (``profile_reaplicar``, ``chamar``, ``resultado``)
    e a chave ``"prender"`` escrita à mão no corpo do IPC. MORDIDA: ponha ``prender=True`` num
    `profile_reaplicar` de outra aba, ou ``p.chamar("profile.reaplicar", name=n, prender=True)``,
    e esta régua nomeia o arquivo.
    """
    raiz = pathlib.Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    quem: set[str] = set()
    for arquivo in raiz.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and no.value == "prender":
                quem.add(arquivo.relative_to(raiz).as_posix())
            if not isinstance(no, ast.Call):
                continue
            for kw in no.keywords:
                if kw.arg == "prender" and not (
                    isinstance(kw.value, ast.Constant) and kw.value.value is False
                ):
                    quem.add(arquivo.relative_to(raiz).as_posix())
    assert quem == {
        "interface/pacotes/rodape.py",
        "interface/pacotes/a10_perfis.py",
        "interface/pacotes/ponte.py",
        "daemon/ipc_handlers.py",
        "profiles/manager.py",
    }, quem
