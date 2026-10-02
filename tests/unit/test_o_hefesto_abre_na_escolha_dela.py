"""O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01 — o Hefesto abre na escolha dela.

A decisão é a `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA` (a fala dela de 29/09, e
as duas respostas do chat da mesma noite: a máquina nova nasce com o botão
aceso, e o botão apagado sem escolha fica sem perfil). O dono da pergunta é
`utils.session.a_escolha_dela`: o Freestyle com o botão aceso, ou o último
perfil que ela ativou à mão, ou «sem escolha».

AS DUAS CAUSAS, medidas no diário dela de 28 e 29/09:

- **o boot pulava a escolha**: seis boots com a sessão num perfil de jogo, e
  nenhum abriu nele. A RESTORE-ESCOPO-01 (22/07) pulava todo perfil com regra
  de janela, e o Freestyle entrava no lugar;
- **a troca à mão caía calada**: às 17h30min25 de 29/09 ela ativou o Avatar
  Legends na aba Perfis, e às 17h31min19 o autoswitch o trocou pelo Freestyle,
  com o terminal em foco. O que segurava a escolha era uma trava de 30 s que
  expirava sozinha e sem linha no diário, e o Freestyle (`match any`) casava
  toda janela.

Estas são as réguas 1, 3, 4, 6 e 7 da sprint, e a medida (a) do tema
«Freestyle definitivo» (a troca à mão fica até um evento, e todo evento diz no
diário). As réguas 2 e 5 (o Freestyle desligado nunca é o perfil ativo, e o
chip e o botão leem o mesmo dono) moram em
`test_o_freestyle_desligado_nunca_e_o_perfil_ativo.py`. A mordida de cada uma
está no docstring dela.

Os quatro controles são da faixa forjada da casa (dois no cabo, dois no rádio:
o gerente publica por `uniq`, e o transporte não entra na conta).
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
import structlog.testing
from typer.testing import CliRunner

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

FREESTYLE = loader.NOME_DO_PADRAO
#: A escolha dela: um perfil de jogo, com regra de janela (o caso do diário).
AVATAR = "Avatar Legends"
JANELA_DO_AVATAR = "steam_app_2424420"
#: O outro jogo, que entra por cima pela janela ou pelo lançamento.
APPID_DO_JOGO = 3357650
JOGO = "PRAGMATA"
JANELA_DO_JOGO = f"steam_app_{APPID_DO_JOGO}"
#: Um perfil de janela que NÃO é jogo: casa o navegador.
NAVEGADOR = "Navegador"
#: O terminal do COSMIC, a janela em foco às 17h31 de 29/09. Regra nenhuma o casa.
TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "~"}

#: Os quatro controles: dois no cabo, dois no rádio.
UNIQS = ("aabbcc000001", "aabbcc000002", "02fe00000003", "02fe00000004")


class _ControleQueGuarda(FakeController):
    """O controle de mentira que guarda a camada por controle que o gerente publica."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.camada: dict[str, Any] = {}

    def reset_output_overrides(self, overrides: Any = None, **_kw: Any) -> None:
        self.camada = dict(overrides or {})


def _com_os_quatro(n: int) -> dict[str, ControllerOverrides]:
    return {uniq: ControllerOverrides(leds=LedsConfig(lightbar=(n, 10 * i, 200)))
            for i, uniq in enumerate(UNIQS, start=1)}


def _perfil(nome: str, janela: str, *, prioridade: int = 80, cor: int = 1) -> None:
    loader.save_profile(Profile(name=nome, match=MatchCriteria(window_class=[janela]),
                                priority=prioridade, controllers=_com_os_quatro(cor)),
                        origem="régua")


def _o_disco() -> None:
    """O Freestyle (`match any`), a escolha dela, o jogo e o navegador."""
    loader.save_profile(Profile(name=FREESTYLE, match=MatchAny(),
                                controllers=_com_os_quatro(7)), origem="régua")
    _perfil(AVATAR, JANELA_DO_AVATAR, cor=2)
    _perfil(JOGO, JANELA_DO_JOGO, cor=3)
    _perfil(NAVEGADOR, "firefox", prioridade=50, cor=4)


async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _boot(controle: Any, store: StateStore) -> None:
    """O `restore_last_profile` de verdade, com o executor inline."""
    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante,
        _native_mode=False)))


def _store_do_boot() -> StateStore:
    """A memória do daemon como o boot a deixa: o botão lido do disco."""
    store = StateStore()
    store.set_freestyle_ligado(session.load_freestyle_ligado())
    return store


def _cli_sem_daemon(nome: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `profile activate` de verdade, com o daemon fora do ar e sem aparelho."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.cli.app import app
    from hefesto_dualsense4unix.core import backend_pydualsense

    class _SemAparelho:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("sem aparelho nesta régua")

    monkeypatch.setattr(ipc_bridge, "profile_switch", lambda _nome: False)
    monkeypatch.setattr(backend_pydualsense, "PyDualSenseController", _SemAparelho)
    resultado = CliRunner().invoke(app, ["profile", "activate", nome])
    assert resultado.exit_code == 0, resultado.output


# =============================================================================
# RÉGUA 1 — o boot abre na escolha
# =============================================================================

CASOS_DO_BOOT = ("escolha-de-jogo", "modo-ligado", "escolha-apagada", "cli-sem-daemon")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("caso", CASOS_DO_BOOT)
def test_o_boot_abre_na_escolha_dela(
    caso: str, transporte: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O boot restaura a escolha, com regra de janela ou sem, nos quatro controles.

    - `escolha-de-jogo`: a sessão no Avatar (regra `steam_app_<N>`), o botão
      apagado → o Avatar, e cada controle recebe a seção dele;
    - `modo-ligado`: o botão aceso → o Freestyle;
    - `escolha-apagada`: ela apagou o Avatar → nenhum perfil, e nunca o Freestyle;
    - `cli-sem-daemon`: `profile activate` com o daemon fora → o boot abre nele.

    O `perfil_que_o_boot_restaura` (o modo do primeiro pad) responde o mesmo.

    MORDIDA: devolva ao `connection._o_nome_que_o_boot_restaura` o pulo da
    RESTORE-ESCOPO-01 (`if not isinstance(load_profile(nome).match, MatchAny):
    return None`) e as células `escolha-de-jogo` e `cli-sem-daemon` reprovam
    com o nome do perfil que o boot pulou.
    """
    _o_disco()
    esperado: str | None
    if caso == "escolha-de-jogo":
        session.gravar_a_escolha(AVATAR)
        esperado = AVATAR
    elif caso == "modo-ligado":
        session.gravar_a_escolha(AVATAR)
        session.save_freestyle_ligado(True)
        esperado = FREESTYLE
    elif caso == "escolha-apagada":
        session.gravar_a_escolha(AVATAR)
        ProfileManager(controller=FakeController(), store=StateStore()).delete(AVATAR)
        esperado = None
    else:
        _cli_sem_daemon(AVATAR, monkeypatch)
        esperado = AVATAR
    controle = _ControleQueGuarda(transport=transporte)
    controle.connect()
    store = _store_do_boot()

    pelo_pad = connection.perfil_que_o_boot_restaura(store)
    _boot(controle, store)

    assert store.active_profile == esperado, (
        f"o boot abriu em {store.active_profile!r}, e a escolha dela era {esperado!r}")
    assert (pelo_pad.name if pelo_pad else None) == esperado
    if esperado is None:
        assert store.active_profile != FREESTYLE
        return
    assert set(controle.camada) == set(UNIQS), (
        f"a seção de cada controle não chegou aos quatro: {sorted(controle.camada)}")


# =============================================================================
# RÉGUA 3 — sair do jogo volta à escolha
# =============================================================================

def _gerente_que_anota(store: StateStore) -> tuple[ProfileManager, list[str]]:
    """O gerente de verdade, com cada nome pedido ao `activate` anotado."""
    controle = FakeController()
    controle.connect()
    gerente = ProfileManager(controller=controle, store=store)
    pedidos: list[str] = []
    original = gerente.activate

    def _anota(name: str, **kw: Any) -> Profile:
        pedidos.append(name)
        return original(name, **kw)

    gerente.activate = _anota  # type: ignore[method-assign]
    return gerente, pedidos


def _vigia(gerente: ProfileManager, store: StateStore, vivo: list[int | None]) -> AutoSwitcher:
    return AutoSwitcher(manager=gerente, window_reader=lambda: {}, store=store,
                        jogo_vivo_reader=lambda: vivo[0])


def _ticar(vigia: AutoSwitcher, info: dict[str, str], de: float, ate: float) -> float:
    """Um tique a cada meio segundo, de `de` a `ate` inclusive; devolve o relógio."""
    agora = de
    while agora <= ate + 1e-9:
        vigia._tick(info, agora)
        agora += 0.5
    return agora


def test_sair_do_jogo_volta_a_escolha_dela() -> None:
    """A escolha A, o jogo B pela janela, e o terminal: a volta é a A, no debounce lento.

    A régua afirma o CANDIDATO, e não só o perfil ativo: com a guarda do item 6
    o Freestyle seria recusado, e A ficaria no lugar escondendo o seletor errado.

    MORDIDAS (as três reprovam):

    - o `match any` de volta à seleção (tire o filtro `e_catch_all` do
      `select_for_window_ex`): o candidato do terminal vira o Freestyle;
    - a pergunta antiga do `_saida_para_a_escolha` (`e_catch_all` do
      candidato): a volta sai em ~1 s, e aos 2 s já vale A;
    - candidato vazio na janela que não é jogo (tire a `_perfil_da_escolha`
      do tique): fica B.
    """
    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, pedidos = _gerente_que_anota(store)
    gerente.activate(AVATAR, origin="manual")
    vigia = _vigia(gerente, store, [None])

    agora = _ticar(vigia, {"wm_class": JANELA_DO_JOGO, "wm_name": JOGO}, 0.0, 1.0)
    assert store.active_profile == JOGO, "o jogo com perfil próprio não entrou"

    inicio = agora
    vigia._tick(TERMINAL, inicio)
    assert vigia._last_candidate == AVATAR, (
        f"o seletor respondeu {vigia._last_candidate!r} para o terminal")
    _ticar(vigia, TERMINAL, inicio + 0.5, inicio + 2.0)
    assert store.active_profile == JOGO, "a volta saiu antes do debounce de saída"
    _ticar(vigia, TERMINAL, inicio + 2.5, inicio + 13.0)
    assert store.active_profile == AVATAR
    assert FREESTYLE not in pedidos, "o autoswitch pediu o Freestyle desligado"


# =============================================================================
# MEDIDA (a) — a troca à mão fica até um evento, e todo evento diz no diário
# =============================================================================

def _soltas(linhas: list[dict[str, Any]]) -> list[str]:
    return [str(x.get("motivo")) for x in linhas
            if x.get("event") == "trava_da_troca_a_mao_solta"]


def test_a_troca_a_mao_nao_cai_por_janela_nem_por_tempo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso das 17h31: a escolha à mão fica, com outra janela em foco, por uma hora.

    O navegador tem regra própria (não é jogo), e por uma hora ele não tira o
    Avatar que ela ativou: nem a janela, nem o relógio. Só o EVENTO solta — o
    jogo com perfil em foco —, e a soltura diz no diário o motivo.

    O relógio do processo é o da régua (`time.monotonic`), para o tempo passar
    de verdade para a trava.

    MORDIDA: arme a trava com prazo (`marcar(time.monotonic() + 30)` em
    `armar_a_trava_da_mao`) e o navegador entra antes de um minuto, sem linha.
    """
    import time

    relogio = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    gerente.activate(AVATAR, origin="manual")
    vigia = _vigia(gerente, store, [None])
    navegador = {"wm_class": "firefox", "wm_name": "Mozilla Firefox"}

    with structlog.testing.capture_logs() as linhas:
        for t in (0.0, 0.6, 13.0, 31.0, 60.0, 600.0, 3600.0):
            relogio[0] = 1000.0 + t
            vigia._tick(navegador, t)
        assert store.active_profile == AVATAR, "a escolha à mão caiu pela janela ou pelo tempo"
        assert _soltas(linhas) == [], "a trava soltou sem evento"

        for t in (3600.5, 3601.1):
            relogio[0] = 1000.0 + t
            vigia._tick({"wm_class": JANELA_DO_JOGO, "wm_name": JOGO}, t)

    assert store.active_profile == JOGO
    assert _soltas(linhas) == ["jogo_com_perfil_em_foco"]


def test_o_jogo_dela_fechando_solta_a_trava_e_diz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o jogo em cena, ela escolhe A à mão; o jogo fecha, e a trava solta com a linha.

    Depois do evento, a troca automática volta: o navegador entra pela regra dele.

    MORDIDA: tire o ramo `o_jogo_em_cena_fechou` de `_a_trava_da_mao_segura` e
    a trava segura A para sempre — o navegador não entra, e a linha não sai.
    """
    import time

    relogio = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    vivo: list[int | None] = [APPID_DO_JOGO]
    vigia = _vigia(gerente, store, vivo)
    jogo = {"wm_class": JANELA_DO_JOGO, "wm_name": JOGO}
    navegador = {"wm_class": "firefox", "wm_name": "Mozilla Firefox"}

    _ticar(vigia, jogo, 0.0, 1.0)
    assert store.active_profile == JOGO
    gerente.activate(AVATAR, origin="manual")
    with structlog.testing.capture_logs() as linhas:
        for t in (1.5, 2.0, 30.0):
            relogio[0] = 1000.0 + t
            vigia._tick(jogo, t)
        assert store.active_profile == AVATAR, "a janela do jogo vivo tirou a escolha à mão"
        vivo[0] = None
        for t in (31.0, 31.6, 45.0):
            relogio[0] = 1000.0 + t
            vigia._tick(navegador, t)

    assert _soltas(linhas) == ["o_jogo_em_cena_fechou"]
    assert store.active_profile == NAVEGADOR


def test_o_lancamento_de_jogo_com_perfil_solta_a_trava_e_diz() -> None:
    """O lançamento entra por cima da escolha à mão, e diz que soltou a trava.

    MORDIDA: tire o ramo `origin == "launch"` do fim de `ProfileManager._ativar`
    e a linha não sai (a trava fica armada com o jogo valendo).
    """
    import time

    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    gerente.activate(AVATAR, origin="manual")

    with structlog.testing.capture_logs() as linhas:
        gerente.activate(JOGO, origin="launch")

    assert store.active_profile == JOGO
    assert _soltas(linhas) == ["lancamento_de_jogo_com_perfil"]
    assert not store.manual_profile_lock_active(time.monotonic())
    assert session.load_last_profile() == AVATAR, "o lançamento virou escolha dela"


def test_o_jogo_que_fecha_solta_a_trava_no_tique_e_reabrir_volta_ao_perfil_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O jogo em cena fecha com o terminal em foco, e reabre: o perfil dele volta.

    Conferência de 02/10/2026. O fechamento só soltava a trava quando uma troca
    era TENTADA, e no terminal o candidato é a escolha dela, que já vale: a
    trava ficava armada, e o mesmo jogo reaberto era segurado para sempre (o
    «nome do jogo que a mão tirou» o isentava). Medido nesta régua: o PRAGMATA
    reaberto ficava no Avatar, sem linha no diário.

    MORDIDA: tire a soltura por tique de `_acompanhar_a_trava_da_mao` e o jogo
    reaberto fica no Avatar, sem a linha `o_jogo_em_cena_fechou`.
    """
    import time

    relogio = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    vivo: list[int | None] = [APPID_DO_JOGO]
    vigia = _vigia(gerente, store, vivo)
    jogo = {"wm_class": JANELA_DO_JOGO, "wm_name": JOGO}

    _ticar(vigia, jogo, 0.0, 1.0)
    gerente.activate(AVATAR, origin="manual")
    with structlog.testing.capture_logs() as linhas:
        for t in (1.5, 2.0, 30.0):
            relogio[0] = 1000.0 + t
            vigia._tick(jogo, t)
        assert store.active_profile == AVATAR, "a janela do jogo vivo tirou a escolha à mão"
        vivo[0] = None
        for t in (31.0, 31.5, 120.0):
            relogio[0] = 1000.0 + t
            vigia._tick(TERMINAL, t)
        assert _soltas(linhas) == ["o_jogo_em_cena_fechou"], "o jogo fechou e a trava ficou"
        assert store.active_profile == AVATAR, "a escolha à mão caiu no terminal"
        vivo[0] = APPID_DO_JOGO
        for t in (200.0, 200.5, 201.0, 201.5):
            relogio[0] = 1000.0 + t
            vigia._tick(jogo, t)

    assert store.active_profile == JOGO, "o jogo reaberto não voltou ao perfil dele"


def test_o_perfil_de_jogo_que_a_mao_tirou_sem_o_jogo_aberto_nao_segura_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A escolha era um perfil de jogo (o Avatar) sem o jogo aberto, e ela ativa outro.

    Conferência de 02/10/2026. O perfil que a mão tirou só é «o jogo em cena»
    quando o jogo está aberto. Antes, todo perfil com regra `steam_app_<N>` que
    a mão tirava virava «o jogo dela», e daí saíam dois defeitos:

    - a janela do navegador (regra própria, não é jogo) soltava a trava com o
      motivo `o_jogo_em_cena_fechou` — a troca à mão caía por TROCA DE JANELA,
      com um motivo falso no diário;
    - abrir o próprio Avatar não trocava para o perfil dele: a trava o isentava
      como «o jogo que a mão tirou».

    MORDIDA: grave o `_jogo_da_trava` sem perguntar se o jogo está em cena e as
    duas metades reprovam.
    """
    import time

    relogio = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    _o_disco()
    session.save_freestyle_ligado(False)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    gerente.activate(AVATAR, origin="system")  # o boot restaurando a escolha
    vivo: list[int | None] = [None]
    vigia = _vigia(gerente, store, vivo)
    _ticar(vigia, TERMINAL, 0.0, 1.0)
    gerente.activate(JOGO, origin="manual")
    navegador = {"wm_class": "firefox", "wm_name": "Mozilla Firefox"}
    avatar = {"wm_class": JANELA_DO_AVATAR, "wm_name": AVATAR}

    with structlog.testing.capture_logs() as linhas:
        for t in (2.0, 2.5, 60.0, 600.0):
            relogio[0] = 1000.0 + t
            vigia._tick(navegador, t)
        assert store.active_profile == JOGO, "a troca à mão caiu pela janela do navegador"
        assert _soltas(linhas) == [], "a trava soltou sem evento"
        vivo[0] = 2424420
        for t in (601.0, 601.5, 602.0):
            relogio[0] = 1000.0 + t
            vigia._tick(avatar, t)

    assert _soltas(linhas) == ["jogo_com_perfil_em_foco"]
    assert store.active_profile == AVATAR, "o jogo aberto não trocou para o perfil dele"


# =============================================================================
# RÉGUA 4 — só a mão escreve a escolha
# =============================================================================

@pytest.mark.parametrize("origem", ["autoswitch", "launch", "system"])
def test_a_origem_automatica_nao_escreve_a_escolha(origem: str) -> None:
    """O autoswitch, o lançamento e o sistema põem o perfil, e a escolha fica.

    MORDIDA: chame o `gravar_a_escolha` do `_ativar` para toda origem (fora do
    `if e_a_escolha`) e as três células reprovam com o PRAGMATA na sessão.
    """
    _o_disco()
    session.gravar_a_escolha(AVATAR)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)

    gerente.activate(JOGO, origin=origem)

    assert store.active_profile == JOGO
    assert (session.load_last_profile(), session.read_active_marker()) == (AVATAR, AVATAR)


def test_a_mao_em_outro_perfil_escreve_a_escolha_e_apaga_o_botao() -> None:
    _o_disco()
    session.save_freestyle_ligado(True)
    store = StateStore()
    store.set_freestyle_ligado(True)
    gerente, _pedidos = _gerente_que_anota(store)

    gerente.activate(JOGO, origin="manual")

    assert (session.load_last_profile(), session.read_active_marker()) == (JOGO, JOGO)
    assert (store.freestyle_ligado, session.load_freestyle_ligado()) == (False, False)


def test_a_mao_no_freestyle_acende_o_botao_e_guarda_o_ultimo_perfil() -> None:
    """O «Ativar» do Freestyle liga o modo; o `last_profile` fica, para a volta.

    O espelho diz a escolha de agora (o Freestyle), e o `session.json` diz o
    perfil a que o botão apagado devolve.
    """
    _o_disco()
    session.gravar_a_escolha(AVATAR)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)

    gerente.activate(FREESTYLE, origin="manual")

    assert (store.active_profile, store.freestyle_ligado) == (FREESTYLE, True)
    assert session.load_freestyle_ligado() is True
    assert session.load_last_profile() == AVATAR
    assert session.read_active_marker() == FREESTYLE


def test_o_reaplicar_nao_escreve_nada() -> None:
    _o_disco()
    session.gravar_a_escolha(AVATAR)
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    gerente.activate(JOGO, origin="launch")

    gerente.reaplicar(JOGO)

    assert (session.load_last_profile(), session.read_active_marker()) == (AVATAR, AVATAR)


def test_a_cli_sem_daemon_escreve_pelo_mesmo_escritor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem daemon, a CLI grava a escolha e o espelho, e apaga o botão (outro perfil).

    MORDIDA: volte o `_gravar_a_escolha_sem_o_daemon` a gravar só o marcador
    (`save_active_marker`) e o `session.json` não diz o Avatar.
    """
    _o_disco()
    session.save_freestyle_ligado(True)

    _cli_sem_daemon(AVATAR, monkeypatch)

    assert (session.load_last_profile(), session.read_active_marker()) == (AVATAR, AVATAR)
    assert session.load_freestyle_ligado() is False


# =============================================================================
# RÉGUA 6 — desligar o botão devolve a escolha na hora, sem leitor de janela
# =============================================================================

class _Handlers(IpcHandlersMixin):
    """O mixin de verdade, com o gerente de verdade e sem daemon (nem autoswitch)."""

    def __init__(self, store: StateStore, gerente: ProfileManager) -> None:
        self.store = store
        self.profile_manager = gerente
        self.daemon = None


def _o_botao_aceso_sobre_a_escolha() -> tuple[StateStore, _Handlers]:
    _o_disco()
    store = StateStore()
    gerente, _pedidos = _gerente_que_anota(store)
    gerente.activate(AVATAR, origin="manual")
    gerente.activate(FREESTYLE, origin="manual")
    assert (store.active_profile, store.freestyle_ligado) == (FREESTYLE, True)
    return store, _Handlers(store, gerente)


def test_desligar_o_botao_devolve_a_escolha_na_hora() -> None:
    """Escolha A, botão aceso: o `freestyle.set` desligado responde A, sem tique nenhum.

    MORDIDA (duas): tire o `apagar_o_freestyle` do `_o_que_volta_sem_o_freestyle`
    (deixe só o `ligar_o_freestyle(self.store, False)`) e fica o Freestyle; ou
    pergunte a escolha sem o botão de agora (`a_escolha_dela()`, sem o
    `freestyle_ligado=False`): o flag do disco ainda diz «aceso» naquele
    instante, e a escolha volta o próprio Freestyle.
    """
    store, h = _o_botao_aceso_sobre_a_escolha()

    resposta = asyncio.run(h._handle_freestyle_set({"ligado": False}))

    assert resposta["active_profile"] == AVATAR
    assert (store.active_profile, store.freestyle_ligado) == (AVATAR, False)
    assert session.load_freestyle_ligado() is False
    assert session.read_active_marker() == AVATAR


def test_desligar_com_o_jogo_vivo_devolve_o_jogo_e_a_escolha_fica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hefesto_dualsense4unix.profiles.autoswitch as autoswitch_mod

    store, h = _o_botao_aceso_sobre_a_escolha()
    monkeypatch.setattr(autoswitch_mod, "jogo_do_wrapper_vivo", lambda: APPID_DO_JOGO)

    resposta = asyncio.run(h._handle_freestyle_set({"ligado": False}))

    assert resposta["active_profile"] == JOGO
    assert (store.active_profile, store.freestyle_ligado) == (JOGO, False)
    assert session.load_last_profile() == AVATAR, "o jogo vivo virou a escolha dela"


# =============================================================================
# RÉGUA 7 — as duas migrações rodam uma vez
# =============================================================================

def test_a_maquina_nova_nasce_acesa_uma_vez_so() -> None:
    """Sem sessão e sem flag: o botão nasce aceso; apagado por ela, fica apagado.

    MORDIDA: tire a marca (`marca.write_text`) da `migrar_a_escolha_dela` e a
    segunda corrida religa o botão que ela apagou no meio.
    """
    assert session.migrar_a_escolha_dela() == "maquina_nova_nasce_acesa"
    assert session.load_freestyle_ligado() is True

    session.save_freestyle_ligado(False)

    assert session.migrar_a_escolha_dela() is None
    assert session.load_freestyle_ligado() is False


def test_a_sessao_no_freestyle_apagado_vira_sem_escolha_com_a_copia() -> None:
    """A sessão apontando o Freestyle com o botão apagado: «sem escolha», com a cópia."""
    _o_disco()
    base = config_dir(ensure=True)
    (base / "session.json").write_text(json.dumps({"last_profile": FREESTYLE}),
                                       encoding="utf-8")

    assert session.migrar_a_escolha_dela() == "freestyle_desligado_vira_sem_escolha"

    assert session.load_last_profile() is None
    assert session.a_escolha_dela() is None
    copia = base / session._COPIA_DA_SESSAO
    assert json.loads(copia.read_text(encoding="utf-8")) == {"last_profile": FREESTYLE}
    assert session.load_freestyle_ligado() is False
    assert session.migrar_a_escolha_dela() is None


def test_o_disco_dela_nao_muda() -> None:
    """A sessão num perfil que não é o Freestyle (o disco dela): nada a mudar."""
    _o_disco()
    session.gravar_a_escolha(AVATAR)

    assert session.migrar_a_escolha_dela() == "nada_a_mudar"

    assert session.load_last_profile() == AVATAR
    assert session.load_freestyle_ligado() is False
    assert not (config_dir() / session._COPIA_DA_SESSAO).exists()
