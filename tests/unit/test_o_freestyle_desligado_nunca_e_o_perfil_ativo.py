"""O Freestyle desligado nunca é o perfil ativo, e o chip e o botão dizem o mesmo.

As réguas 2 e 5 da O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01,
e o «Freestyle definitivo» do tema de 01/10/2026: com o botão «Modo Freestyle»
aceso, o Freestyle manda em tudo; apagado, ele não vale em lugar nenhum, e a aba
Perfis não o oferece como um perfil a escolher.

A INVARIANTE (item 6 da `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`): no retrato do
`daemon.state_full`, `active_profile == Freestyle` só com `freestyle_ligado`.
Até 01/10/2026 o boot e a volta do jogo punham o Freestyle valendo com o botão
apagado — o chip dizia «Freestyle» e o botão dizia «desligado», e a pergunta de 29/09 era qual dos
dois dizia a verdade.

A guarda mora na origem, `ProfileManager._ativar`: só a mão do usuário põe o
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
OUTRO = "Navegador"


def _o_disco() -> None:
    """O Freestyle (`match any`) e a escolha do usuário, com o botão apagado."""
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
    """O PS + D-pad dá três voltas: o Freestyle não está na roda (ordem de 02/10)."""
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import build_profile_cycle_callback

    loader.save_profile(Profile(name=OUTRO, match=MatchCriteria(window_class=["firefox"]),
                                priority=50), origem="régua")
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
    """Depois de cada caminho, `active_profile == Freestyle ⇒ freestyle_ligado`."""
    _o_disco()

    server = CAMINHOS[caminho]()

    _a_invariante(server, caminho)
    if caminho == "boot":
        assert server.store.active_profile is None, "a sessão velha virou o Freestyle"


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
    """A perna do disco: a escolha A com o botão apagado, o Freestyle aceso, ou «—»."""
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


# *«Lembrando que nao pode haver um perfil  <!-- noqa-acento: citação literal -->

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
    """A pergunta «quais perfis existem» ao daemon (a bandeja, a TUI, o `doctor`)."""
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
    """O `profile list` da CLI, que lê o disco: o Freestyle não é linha da tabela."""
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli.app import app

    _o_disco()
    session.save_freestyle_ligado(aceso)

    saida = CliRunner().invoke(app, ["profile", "list"], terminal_width=200)

    assert saida.exit_code == 0, saida.output
    assert AVATAR in saida.output
    assert FREESTYLE not in saida.output, saida.output


@pytest.mark.parametrize("sentido", [+1, -1], ids=["PS-cima", "PS-baixo"])
@pytest.mark.parametrize("aceso", [False, True], ids=["apagado", "aceso"])
def test_a_roda_do_ps_e_d_pad_nao_passa_pelo_freestyle(aceso: bool, sentido: int) -> None:
    """A roda de perfis do controle (PS + D-pad), com o botão apagado e aceso."""
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import build_profile_cycle_callback

    _o_disco()
    loader.save_profile(Profile(name=OUTRO, match=MatchCriteria(window_class=["firefox"]),
                                priority=50), origem="régua")
    store, gerente, server = _o_par()
    gerente.activate(AVATAR, origin="manual")
    if aceso:
        asyncio.run(server._handle_freestyle_set({"ligado": True}))
        assert store.active_profile == FREESTYLE
    daemon = SimpleNamespace(store=store, controller=server.controller,
                             _keyboard_device=None, _run_blocking=_bloqueante)
    ciclo = build_profile_cycle_callback(daemon, sentido)  # type: ignore[arg-type]

    vistos: list[str | None] = []
    for _passo in range(5):
        asyncio.run(ciclo())
        vistos.append(store.active_profile)

    assert FREESTYLE not in vistos, vistos
    assert set(vistos) == {AVATAR, OUTRO}, vistos
    assert store.freestyle_ligado is False


@pytest.mark.parametrize("daemon", ["fora-do-ar", "lista-vazia"])
def test_a_lista_da_ponte_nao_oferece_o_freestyle(
    daemon: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `ipc_bridge.profile_list`: o daemon fora do ar, ou a lista vazia da máquina nova.

    Conferência final de 02/10/2026. As duas caem na reserva do disco: fora do
    ar, pelo erro; com o `profile.list` vazio (o Freestyle sozinho na pasta, que
    não é oferta), pelo `if profiles` da ponte. A reserva oferece o que o daemon
    oferece.

    MORDIDA: troque o `os_perfis_de_escolher(load_all_profiles())` da reserva de
    `app.ipc_bridge.profile_list` por `load_all_profiles()` e as duas células
    reprovam com o Freestyle na lista.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    def _fora_do_ar(*_a: Any, **_k: Any) -> Any:
        raise FileNotFoundError("sem socket nesta régua")

    _o_disco()
    resposta = _fora_do_ar if daemon == "fora-do-ar" else (lambda *_a, **_k: {"profiles": []})
    monkeypatch.setattr(ipc_bridge, "_run_call", resposta)

    nomes = [p["name"] for p in ipc_bridge.profile_list()]

    assert AVATAR in nomes
    assert FREESTYLE not in nomes, nomes


def test_a_tui_sem_daemon_nao_lista_o_freestyle(monkeypatch: pytest.MonkeyPatch) -> None:
    """A TUI com o daemon fora do ar lê o disco, e lê a mesma oferta do daemon.

    Conferência de 02/10/2026. MORDIDA: troque o `os_perfis_de_escolher(
    load_all_profiles())` da reserva de `tui.app.fetch_daemon_snapshot` por
    `load_all_profiles()` e o Freestyle volta à tabela.
    """
    from hefesto_dualsense4unix.cli import ipc_client
    from hefesto_dualsense4unix.tui.app import fetch_daemon_snapshot

    def _fora_do_ar(*_a: Any, **_k: Any) -> Any:
        raise FileNotFoundError("sem socket nesta régua")

    _o_disco()
    monkeypatch.setattr(ipc_client.IpcClient, "connect", _fora_do_ar)

    retrato = asyncio.run(fetch_daemon_snapshot())

    nomes = [p["name"] for p in retrato.profiles]
    assert retrato.online is False
    assert AVATAR in nomes
    assert FREESTYLE not in nomes, nomes


@pytest.mark.parametrize("perfis", [[], [{"name": AVATAR}]], ids=["maquina-nova", "com-perfil"])
def test_o_doctor_nao_acusa_a_maquina_nova(
    perfis: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na máquina nova o `profile.list` é vazio (só o Freestyle, que não é oferta)."""
    from hefesto_dualsense4unix.cli import cmd_doctor

    class _Cliente:
        async def __aenter__(self) -> _Cliente:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

        async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"profiles": perfis} if metodo == "profile.list" else {"paused": False}

    monkeypatch.setattr(cmd_doctor.IpcClient, "connect", lambda *_a, **_k: _Cliente())

    linhas = asyncio.run(cmd_doctor._daemon_checks())

    assert ("[ OK ]", f"perfis listáveis via IPC ({len(perfis)})") in linhas, linhas
    assert not any(tag == "[WARN]" for tag, _m in linhas), linhas

