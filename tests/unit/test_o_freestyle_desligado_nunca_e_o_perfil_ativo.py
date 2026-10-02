"""O Freestyle desligado nunca é o perfil ativo, e o chip e o botão dizem o mesmo.

As réguas 2 e 5 da O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01,
e o «Freestyle definitivo» do tema de 01/10/2026: com o botão «Modo Freestyle»
aceso, o Freestyle manda em tudo; apagado, ele não vale em lugar nenhum, e a aba
Perfis não o oferece como um perfil a escolher.

A INVARIANTE (item 6 da `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`): no retrato do
`daemon.state_full`, `active_profile == Freestyle` só com `freestyle_ligado`.
Até 01/10/2026 o boot e a volta do jogo punham o Freestyle valendo com o botão
apagado — o chip dizia «Freestyle» e o botão dizia «desligado», e a pergunta
dela de 29/09 era qual dos dois dizia a verdade.

A guarda mora na origem, `ProfileManager._ativar`: só a mão dela põe o
Freestyle, e pondo-o acende o botão. Cada caminho abaixo é um dos que punham.

Os `uniq` são da faixa forjada da casa.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import OFreestyleDesligadoError, ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

FREESTYLE = loader.NOME_DO_PADRAO
AVATAR = "Avatar Legends"
JANELA_DO_AVATAR = "steam_app_2424420"
TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "~"}


def _o_disco() -> None:
    """O Freestyle (`match any`) e a escolha dela, com o botão apagado."""
    loader.save_profile(Profile(name=FREESTYLE, match=MatchAny()), origem="régua")
    loader.save_profile(Profile(name=AVATAR,
                                match=MatchCriteria(window_class=[JANELA_DO_AVATAR]),
                                priority=80), origem="régua")
    session.save_freestyle_ligado(False)


def _sessao_crua_no_freestyle() -> None:
    """O `session.json` de antes da migração da escolha, apontando o Freestyle."""
    (config_dir(ensure=True) / "session.json").write_text(
        json.dumps({"last_profile": FREESTYLE}), encoding="utf-8")


def _o_par() -> tuple[StateStore, ProfileManager, IpcServer]:
    controle = FakeController()
    controle.connect()
    store = StateStore()
    gerente = ProfileManager(controller=controle, store=store)
    return store, gerente, IpcServer(controller=controle, store=store,
                                     profile_manager=gerente, daemon=None)


async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _boot(store: StateStore, controle: Any) -> None:
    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante,
        _native_mode=False)))


# =============================================================================
# RÉGUA 2 — em todo caminho, o retrato obedece à invariante
# =============================================================================

def _boot_com_a_sessao_velha() -> IpcServer:
    _sessao_crua_no_freestyle()
    store, _g, server = _o_par()
    _boot(store, server.controller)
    return server


def _reconexao_com_a_escolha_valendo() -> IpcServer:
    """A reconexão é o mesmo `restore_last_profile`, agora com a escolha já valendo."""
    _sessao_crua_no_freestyle()
    store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="system")
    _boot(store, server.controller)
    return server


def _autoswitch_das_17h31() -> IpcServer:
    """A escolha à mão, e o terminal em foco muito além da trava e do debounce."""
    store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    vigia = AutoSwitcher(manager=gerente, window_reader=lambda: {}, store=store,
                         jogo_vivo_reader=lambda: None)
    for t in (0.0, 0.6, 13.0, 31.0, 60.0, 600.0):
        vigia._tick(TERMINAL, t)
    return server


def _lancamento() -> IpcServer:
    _store, gerente, server = _o_par()
    with pytest.raises(OFreestyleDesligadoError):
        gerente.activate(FREESTYLE, origin="launch")
    return server


def _botao_apagado_sem_escolha() -> IpcServer:
    _store, _g, server = _o_par()
    asyncio.run(server._handle_freestyle_set({"ligado": True}))
    asyncio.run(server._handle_freestyle_set({"ligado": False}))
    return server


def _saida_do_nativo() -> IpcServer:
    """O botão aceso no disco e apagado na memória: a saída do Nativo obedece a memória."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    _sessao_crua_no_freestyle()
    session.save_freestyle_ligado(True)
    store, _g, server = _o_par()
    Daemon._reapply_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        store=store, controller=server.controller, apply_profile_mouse=lambda *a: None,
        apply_profile_suppression=lambda *a: None, _keyboard_device=None))
    return server


def _ciclo_do_ps() -> IpcServer:
    """O PS + D-pad passa por todos os perfis, o Freestyle no meio: é gesto da mão."""
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import build_profile_cycle_callback

    store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    daemon = SimpleNamespace(store=store, controller=server.controller,
                             _keyboard_device=None, _run_blocking=_bloqueante)
    ciclo = build_profile_cycle_callback(daemon, +1)  # type: ignore[arg-type]
    for _volta in range(3):
        asyncio.run(ciclo())
        _a_invariante(server, f"ciclo do PS em {store.active_profile!r}")
    return server


def _reaplicar_o_freestyle() -> IpcServer:
    """O que o rodapé e o «voltar à de ontem» mandariam: o `profile.reaplicar` dele."""
    store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    with pytest.raises(OFreestyleDesligadoError):
        asyncio.run(server._handle_profile_reaplicar({"name": FREESTYLE}))
    assert store.active_profile == AVATAR
    return server


CAMINHOS: dict[str, Callable[[], IpcServer]] = {
    "boot": _boot_com_a_sessao_velha,
    "reconexao": _reconexao_com_a_escolha_valendo,
    "autoswitch": _autoswitch_das_17h31,
    "lancamento": _lancamento,
    "freestyle-set-desligado": _botao_apagado_sem_escolha,
    "saida-do-nativo": _saida_do_nativo,
    "ciclo-do-ps": _ciclo_do_ps,
    "profile-reaplicar": _reaplicar_o_freestyle,
}


def _a_invariante(server: IpcServer, caminho: str) -> None:
    retrato = asyncio.run(server._handle_daemon_state_full({}))
    if retrato["active_profile"] == FREESTYLE:
        assert retrato["freestyle_ligado"] is True, (
            f"{caminho}: o retrato diz o Freestyle ativo com o botão apagado")


@pytest.mark.parametrize("caminho", sorted(CAMINHOS))
def test_o_freestyle_desligado_nunca_e_o_perfil_ativo(caminho: str) -> None:
    """Depois de cada caminho, `active_profile == Freestyle ⇒ freestyle_ligado`.

    MORDIDA: tire a guarda do item 6 de `ProfileManager._ativar` (o `raise
    OFreestyleDesligadoError`) e reprovam o `profile-reaplicar` (o Freestyle
    reaplicado com o botão apagado) e o `lancamento`.
    """
    _o_disco()

    server = CAMINHOS[caminho]()

    _a_invariante(server, caminho)
    if caminho == "boot":
        assert server.store.active_profile is None, "a sessão velha virou o Freestyle"


# =============================================================================
# RÉGUA 5 — o chip e o botão leem o mesmo dono
# =============================================================================

def _ctx(state: Any) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state=state, mesa=[], conectados=[], estados={})


@pytest.mark.parametrize("ligado", [False, True], ids=["apagado", "aceso"])
def test_o_chip_diz_freestyle_se_e_so_se_o_botao_diz_ligado(ligado: bool) -> None:
    """Os retratos do daemon pintados pelo topo e pela aba 01: um só dono."""
    from hefesto_dualsense4unix.interface.pacotes import topo
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import CADEADO_LIGADO, _cadeado

    _o_disco()
    _store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    if ligado:
        asyncio.run(server._handle_freestyle_set({"ligado": True}))
    retrato = asyncio.run(server._handle_daemon_state_full({}))

    chip = topo(_ctx(retrato))["perfil"]

    assert (chip == FREESTYLE) is (_cadeado(retrato) == CADEADO_LIGADO) is ligado
    assert chip == (FREESTYLE if ligado else AVATAR)


@pytest.mark.parametrize("caso", ["escolha-apagado", "escolha-aceso", "sem-escolha"])
def test_com_o_daemon_calado_o_chip_e_o_rodape_dizem_a_escolha(caso: str) -> None:
    """A perna do disco: a escolha A com o botão apagado, o Freestyle aceso, ou «—».

    O marcador diz «Freestyle» nas três células: ele é espelho, e quem lê a
    perna do disco é o dono da escolha.

    MORDIDAS: a perna do disco lendo o marcador de novo (`perfil_que_ela_ativou`
    devolvendo `read_active_marker()`) — a célula `escolha-apagado` reprova
    com o Freestyle; o `perfil_do_rodape` caindo no Freestyle de novo
    (`or loader.o_perfil_de_fora_do_jogo()`) — a `sem-escolha` reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import topo
    from hefesto_dualsense4unix.interface.pacotes.rodape import perfil_do_rodape

    _o_disco()
    if caso != "sem-escolha":
        session.save_last_profile(AVATAR)
    if caso == "escolha-aceso":
        session.save_freestyle_ligado(True)
    session.save_active_marker(FREESTYLE)
    esperado = {"escolha-apagado": AVATAR, "escolha-aceso": FREESTYLE, "sem-escolha": ""}[caso]

    assert topo(_ctx(None))["perfil"] == (esperado or "—")
    assert perfil_do_rodape(None) == esperado


# =============================================================================
# NENHUM SELETOR OFERECE O FREESTYLE — a ordem dela de 02/10/2026
# =============================================================================
# *«Lembrando que nao pode haver um perfil  <!-- noqa-acento: citação literal dela -->
# na aba perfis chamado de frestyle»*
# (02/10, registrada na sprint pela coordenação). Vale acima do desenho de
# 27/09: ligado ou desligado, a lista publicada da aba Perfis e toda resposta
# de «quais perfis existem» não contêm o nome. O Freestyle é o botão.

ESTADOS_DO_BOTAO = ("apagado", "aceso", "daemon-calado")


def _nomes_da_lista(state: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_PROCURA", "", raising=False)
    return list(a10_perfis.pacote(_ctx(state))["perfis.linha.nome"])


def _o_retrato(estado: str) -> dict[str, Any]:
    """O `state_full` de verdade com o botão no estado pedido (`{}` = daemon calado)."""
    if estado == "daemon-calado":
        return {}
    _store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    if estado == "aceso":
        asyncio.run(server._handle_freestyle_set({"ligado": True}))
    return asyncio.run(server._handle_daemon_state_full({}))


@pytest.mark.parametrize("estado", ESTADOS_DO_BOTAO)
def test_a_aba_perfis_nunca_mostra_o_freestyle(
    estado: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lista publicada da aba Perfis, nos três estados do botão: sem o Freestyle.

    Aceso, o Freestyle é o que vale, e ainda assim não é linha: ele se apaga
    pelo botão da aba Jogar, ou pelo «Ativar» de outro perfil desta lista.

    MORDIDA: troque o `os_perfis_de_escolher(load_all_profiles())` do
    `a10_perfis.pacote` por `load_all_profiles()` e as três células reprovam.
    """
    _o_disco()
    retrato = _o_retrato(estado)

    nomes = _nomes_da_lista(retrato, monkeypatch)

    assert AVATAR in nomes
    assert FREESTYLE not in nomes, nomes


@pytest.mark.parametrize("aceso", [False, True], ids=["apagado", "aceso"])
def test_o_profile_list_do_daemon_nao_responde_o_freestyle(aceso: bool) -> None:
    """A pergunta «quais perfis existem» ao daemon (a bandeja, a TUI, o `doctor`).

    MORDIDA: tire o `os_perfis_de_escolher` do `_handle_profile_list` e as
    duas células reprovam.
    """
    _o_disco()
    _store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    if aceso:
        asyncio.run(server._handle_freestyle_set({"ligado": True}))

    nomes = [p["name"] for p in asyncio.run(server._handle_profile_list({}))["profiles"]]

    assert AVATAR in nomes
    assert FREESTYLE not in nomes, nomes


@pytest.mark.parametrize("aceso", [False, True], ids=["apagado", "aceso"])
def test_o_profile_list_da_cli_nao_mostra_o_freestyle(aceso: bool) -> None:
    """O `profile list` da CLI, que lê o disco: o Freestyle não é linha da tabela.

    MORDIDA: tire o `os_perfis_de_escolher` do `cmd_list` e as duas células
    reprovam.
    """
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli.app import app

    _o_disco()
    session.save_freestyle_ligado(aceso)

    saida = CliRunner().invoke(app, ["profile", "list"], terminal_width=200)

    assert saida.exit_code == 0, saida.output
    assert AVATAR in saida.output
    assert FREESTYLE not in saida.output, saida.output
