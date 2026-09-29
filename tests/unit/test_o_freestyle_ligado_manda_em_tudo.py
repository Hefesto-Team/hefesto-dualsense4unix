"""O-FREESTYLE-E-UMA-CAMADA-SO-01 — ligado, o Freestyle manda em tudo.

A palavra dela, 27/09 à noite: *«Aperto o botão do freestyle e o jogo que eu
tiver jogando vai ter essa config independente do perfil do jogo. Só isso.»*
(noqa-acento: citação literal dela). `D-2709-O-FREESTYLE-E-UM-PERFIL-QUE-MANDA`,
que revoga a `D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA`.

O defeito era o botão «Modo Freestyle» ser o cadeado de 23/07, que CEDIA à
regra própria de todo jogo (LOCK-CEDE-01): em jogo, ele nunca valia. A cura mora
num lugar só (`profiles/manager.py`, o bloco antes do `ProfileManager`), e esta
régua mede cada caminho que podia passar por cima dele:

1. **o autoswitch** para antes de casar a janela; o modo jogo padrão só entra
   quando o Freestyle não diz o modo (o de fábrica não diz);
2. **o `ProfileManager.activate`** recusa toda ativação automática de outro
   perfil — é a rede que pega o caminho que esquecer de perguntar;
3. **o gesto dela decide**: o «Ativar» do Freestyle liga, o de outro desliga,
   apagar o Freestyle desliga, e reativar o que já vale (o gravar-e-reaplicar
   das abas) não muda o modo;
4. **o lançamento** não arma o perfil do jogo, e **a env antecipada** lê o
   Freestyle;
5. **o restore do boot** e o **modo do primeiro pad** são os do Freestyle;
6. **o `freestyle.set`** liga pelo mesmo caminho do «Ativar», e desligar devolve
   o jogo vivo sem reabrir;
7. **a migração** do `autoswitch_locked.flag`;
8. **a matriz**: os quatro controles, P1 e P3 no cabo, P2 e P4 no rádio, no byte
   do report de cada transporte — com o perfil do jogo casado pela janela;
9. **a guarda do jogo vivo** (`D-2709-O-PERFIL-DO-JOGO-ENTRA-NO-LANCAMENTO`): o
   perfil do jogo que o lançamento pôs não sai por uma janela de fora;
10. **o `gamepad.emulation.set` sem caminho** pergunta o modo ao perfil ativo,
    nos três modos (a porta que a conferência da O-MODO-XBOX-NAO-E-QUEDA-02
    achou).

A mordida de cada célula está no docstring dela. Os `uniq` são da faixa forjada.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import (
    OFreestyleMandaError,
    ProfileManager,
    ligar_o_freestyle,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import config_dir, profiles_dir

from tests.conftest import EnvelopeDeTransporte, envelope_de

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"

#: O PRAGMATA, o jogo da noite de 27/09.
APPID = 3357650
JANELA = f"steam_app_{APPID}"
JOGO = "PRAGMATA"
FREESTYLE = loader.NOME_DO_PADRAO

#: A mesa dela: P1 e P3 no cabo, P2 e P4 no rádio — nunca só o P1.
MESA: tuple[tuple[str, str], ...] = (
    ("AA:BB:CC:00:00:01", "usb"),
    ("AA:BB:CC:00:00:02", "bt"),
    ("AA:BB:CC:00:00:03", "usb"),
    ("AA:BB:CC:00:00:04", "bt"),
)

#: Offsets do bloco de gatilho DENTRO do common: (modo, primeira das seis forças,
#: a sétima avulsa). Os mesmos da `test_paridade_transporte_gatilhos.py`.
OFFSETS_DO_GATILHO = {"right": (10, 11, 19), "left": (21, 22, 30)}


@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def _o_jogo(*, gatilho: str = "Off", caminho: str | None = "dualsense") -> None:
    """O perfil do PRAGMATA, casado pela janela, com gatilhos DIFERENTES do Freestyle."""
    loader.save_profile(Profile(
        name=JOGO,
        match=MatchCriteria(window_class=[JANELA]),
        priority=80,
        triggers=TriggersConfig(left=TriggerConfig(mode=gatilho),
                                right=TriggerConfig(mode=gatilho)),
        mode=ProfileModeConfig(kind="gamepad", caminho=caminho),
    ))


def _gerente(store: StateStore, controle: Any | None = None) -> ProfileManager:
    if controle is None:
        controle = FakeController()
        controle.connect()
    return ProfileManager(controller=controle, store=store)


def _liga(store: StateStore, controle: Any | None = None) -> ProfileManager:
    """O gesto dela: o «Ativar» do Freestyle (o mesmo do botão «Modo Freestyle»)."""
    gerente = _gerente(store, controle)
    gerente.activate(FREESTYLE, origin="manual")
    assert store.freestyle_ligado is True
    return gerente


# =============================================================================
# 1. O AUTOSWITCH — para antes de casar a janela
# =============================================================================

@pytest.mark.parametrize("janela", [
    {"wm_class": JANELA, "wm_name": "PRAGMATA"},
    {"wm_class": "firefox", "wm_name": "Mozilla Firefox"},
], ids=["a-janela-do-jogo", "uma-janela-comum"])
def test_ligado_o_autoswitch_nao_troca_nem_pela_regra_do_jogo(
    semeadura_ligada: None, janela: dict[str, str],
) -> None:
    """Ligado, nenhuma janela troca o perfil — nem a regra própria do jogo.

    MORDIDA: devolva ao `_tick` a LOCK-CEDE-01 (o cadeado que cede à regra do
    jogo) no lugar da parada pelo Freestyle e tire a recusa do `activate` — a
    célula da janela do jogo reprova com o PRAGMATA valendo.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    vigia = AutoSwitcher(manager=_liga(store), window_reader=lambda: {}, store=store)

    for t in (0.0, 0.6, 13.0, 60.0, 300.0):
        vigia._tick(janela, t)

    assert store.active_profile == FREESTYLE


def test_ligado_o_autoswitch_nem_pergunta_a_janela(semeadura_ligada: None) -> None:
    """A parada é ANTES de casar: o seletor não é chamado, e a ativação também não.

    MORDIDA: tire o `if self.freestyle_ligado():` do `_tick` e o seletor é
    chamado — a recusa do `activate` segura o perfil, mas o tique já decidiu
    por cima dele, que é o que esta célula proíbe.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    gerente = _liga(store)
    chamadas: list[str] = []
    original = gerente.select_for_window_ex

    def _espia(info: dict[str, Any]) -> Any:
        chamadas.append(str(info.get("wm_class")))
        return original(info)

    gerente.select_for_window_ex = _espia  # type: ignore[method-assign]
    vigia = AutoSwitcher(manager=gerente, window_reader=lambda: {}, store=store)
    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": JANELA}, t)

    assert chamadas == []


def _o_freestyle_diz(mode: dict[str, Any] | None) -> None:
    """Grava a seção `mode` no Freestyle do disco (None = sem a seção, o de fábrica)."""
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    dela = json.loads(arquivo.read_text(encoding="utf-8"))
    dela.pop("mode", None)
    if mode is not None:
        dela["mode"] = mode
    arquivo.write_text(json.dumps(dela), encoding="utf-8")


@pytest.mark.parametrize("janela", [JANELA, "steam_app_2111190"],
                         ids=["jogo-com-perfil-proprio", "jogo-sem-perfil"])
def test_ligado_e_dizendo_o_modo_o_modo_jogo_padrao_nao_entra(
    semeadura_ligada: None, janela: str,
) -> None:
    """O Freestyle que TEM a seção `mode` manda no modo: o padrão não entra.

    MORDIDA: faça `AutoSwitcher._o_freestyle_diz_o_modo` responder `False` e as
    duas células reprovam com o espião chamado.
    """
    loader.load_all_profiles()
    _o_jogo()
    _o_freestyle_diz({"kind": "gamepad", "caminho": "xbox"})
    store = StateStore()
    pedidos: list[str] = []
    vigia = AutoSwitcher(
        manager=_liga(store), window_reader=lambda: {}, store=store,
        modo_jogo_padrao_applier=lambda *, wm_class: pedidos.append(wm_class) or "aplicado",
        modo_jogo_padrao_reverter=lambda *, wm_class: "aplicado",
    )
    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": janela}, t)

    assert pedidos == []
    assert store.active_profile == FREESTYLE


@pytest.mark.parametrize("janela", [JANELA, "steam_app_2111190"],
                         ids=["jogo-com-perfil-proprio", "jogo-sem-perfil"])
def test_ligado_sem_dizer_o_modo_o_jogo_liga_o_modo_padrao(
    semeadura_ligada: None, janela: str,
) -> None:
    """O Freestyle de fábrica não diz o modo: o jogo liga o modo padrão da máquina.

    Conferência de 28/09/2026. Sem a seção `mode` o Freestyle não opina (R-02),
    e o modo num jogo é o da máquina — o modo jogo padrão, com ou sem perfil
    próprio do jogo, que não entra. Fora do jogo, o par solta. O perfil não
    troca em momento nenhum.

    MORDIDA: tire a chamada `_modo_jogo_padrao_sob_o_freestyle` da parada pelo
    Freestyle no `_tick` e as duas células reprovam sem pedido nenhum.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    pedidos: list[str] = []
    soltos: list[str] = []
    vigia = AutoSwitcher(
        manager=_liga(store), window_reader=lambda: {}, store=store,
        modo_jogo_padrao_applier=lambda *, wm_class: pedidos.append(wm_class) or "aplicado",
        modo_jogo_padrao_reverter=lambda *, wm_class: soltos.append(wm_class) or "aplicado",
    )
    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": janela}, t)
    vigia._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, 31.0)

    assert (pedidos, soltos) == ([janela] * 3, ["firefox"])
    assert store.active_profile == FREESTYLE


def test_desligar_nao_ativa_no_mesmo_tique(semeadura_ligada: None) -> None:
    """O tempo ligado não conta como estabilidade (o buraco-do-debounce da UX-01)."""
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    vigia = AutoSwitcher(manager=_liga(store), window_reader=lambda: {}, store=store)
    for t in (0.0, 100.0, 1000.0):
        vigia._tick({"wm_class": JANELA}, t)

    ligar_o_freestyle(store, False)
    vigia._tick({"wm_class": JANELA}, 1000.1)
    assert store.active_profile == FREESTYLE
    vigia._tick({"wm_class": JANELA}, 1000.7)
    assert store.active_profile == JOGO


# =============================================================================
# 2 e 3. O DONO — a recusa do `activate`, e o gesto dela que decide
# =============================================================================

@pytest.mark.parametrize("origem", ["autoswitch", "launch", "system"])
def test_ligado_nenhuma_ativacao_automatica_passa(
    semeadura_ligada: None, origem: str,
) -> None:
    """A rede de baixo: o caminho que esquecer de perguntar também não passa.

    MORDIDA: tire o bloco `if origin != "manual" and o_freestyle_manda(...)` de
    `ProfileManager.activate` e as três células reprovam sem a recusa.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    gerente = _liga(store)

    with pytest.raises(OFreestyleMandaError):
        gerente.activate(JOGO, origin=origem)
    assert store.active_profile == FREESTYLE
    # O próprio Freestyle entra por qualquer origem: é ele que manda.
    gerente.activate(FREESTYLE, origin=origem)


def test_o_gesto_dela_liga_e_desliga_e_o_disco_acompanha(semeadura_ligada: None) -> None:
    """O «Ativar» do Freestyle liga; o de outro perfil desliga; o disco vai junto.

    MORDIDA: tire o `ligar_o_freestyle(...)` do ramo `origin == "manual"` do
    `activate` e a primeira asserção reprova.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    gerente = _gerente(store)

    gerente.activate(FREESTYLE, origin="manual")
    assert (store.freestyle_ligado, session.load_freestyle_ligado()) == (True, True)

    gerente.activate(JOGO, origin="manual")
    assert (store.freestyle_ligado, session.load_freestyle_ligado()) == (False, False)
    assert store.active_profile == JOGO


def test_apagar_o_freestyle_desliga_o_modo(semeadura_ligada: None) -> None:
    """Sem o arquivo, o modo ligado seguraria o produto sem perfil nenhum, para sempre."""
    loader.load_all_profiles()
    store = StateStore()
    gerente = _liga(store)

    gerente.delete(FREESTYLE)

    assert (store.freestyle_ligado, session.load_freestyle_ligado()) == (False, False)


# =============================================================================
# 4. O LANÇAMENTO — nem o perfil do jogo, nem a máscara dele
# =============================================================================

def _marker(tmp_path: Path) -> Path:
    import time

    (tmp_path / "last_run").write_text(
        f"appid={APPID}\nepoch={int(time.time())}\npid=1\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("ligado", [True, False], ids=["ligado", "desligado"])
def test_o_lancamento_nao_ativa_o_perfil_do_jogo_com_o_freestyle_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ligado: bool,
) -> None:
    """Ligado, o lançamento não ativa o perfil do jogo; desligado, ativa, como sempre.

    MORDIDA: tire o `if o_freestyle_manda(...)` de `arm_launch_profile` e a
    célula `ligado` reprova com a ativação do PRAGMATA.
    """
    perfil = Profile(name=JOGO, match=MatchCriteria(window_class=[JANELA]), priority=80,
                     mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"))
    ativados: list[str] = []
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {APPID})
    monkeypatch.setattr(
        le, "_ativar_o_perfil_do_lancamento",
        lambda daemon, profile, **kw: ativados.append(profile.name) or {},
    )
    monkeypatch.setattr(le, "tique_da_escada", lambda daemon: None)
    store = StateStore()
    store.set_freestyle_ligado(ligado)
    daemon = SimpleNamespace(store=store, apply_profile_suppression=None)

    resultado = le.arm_launch_profile(daemon, base_dir=_marker(tmp_path))  # type: ignore[arg-type]

    assert resultado is not None
    if ligado:
        assert (resultado["motivo"], ativados) == ("freestyle_ligado", [])
    else:
        assert ativados == [JOGO]


def _perfil_de_mentira(nome: str, mascara: str) -> SimpleNamespace:
    """O formato que o `launch_env` lê — o mesmo dublê da `test_mascara_do_perfil_no_launch`."""
    return SimpleNamespace(
        name=nome,
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor=mascara, caminho=None),
        match=SimpleNamespace(window_class=[JANELA], window_title_regex=None,
                              process_name=[]),
    )


@pytest.mark.parametrize("ligado", [True, False], ids=["ligado", "desligado"])
def test_a_mascara_antecipada_le_o_freestyle_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ligado: bool,
) -> None:
    """O jogo lê a env UMA vez, no `exec`: ligado, ela diz a máscara DO FREESTYLE.

    MORDIDA: troque, no laço do `materialize_launch_env`, o
    `freestyle if freestyle is not None else do_jogo` por `do_jogo` e a célula
    `ligado` reprova com a máscara do PRAGMATA.
    """
    freestyle = _perfil_de_mentira(FREESTYLE, "xbox")
    jogo = _perfil_de_mentira(JOGO, "dualsense")
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, jogo)])
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [freestyle, jogo])
    daemon = SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None, freestyle_ligado=ligado),
    )

    le.materialize_launch_env(daemon)  # type: ignore[arg-type]

    linha = next(linha for linha in (tmp_path / f"{JANELA}.env").read_text(
        encoding="utf-8").splitlines() if linha.startswith("# estado:"))
    esperado = "xbox" if ligado else "dualsense"
    assert f"perfil gamepad {esperado}" in linha, linha


def _o_estado_do_arquivo(pasta: Path) -> str:
    return next(linha for linha in (pasta / f"{JANELA}.env").read_text(
        encoding="utf-8").splitlines() if linha.startswith("# estado:"))


def test_o_vigia_ve_o_freestyle_trocar_sem_borda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem liga ou desliga sem passar por borda que materializa: o vigia regrava.

    Conferência de 28/09/2026. O ciclo do PS + D-pad ativa com a origem
    `manual` e muda o modo sem regravar as envs; o jogo seguinte leria no
    `exec` a máscara do modo de antes. O Modo Freestyle é o sexto campo da
    assinatura da mesa, e o vigia de 1 Hz vê a troca como vê a de um vpad.

    MORDIDA: tire o `_o_freestyle_na_assinatura(daemon)` da
    `_assinatura_da_mesa` e do carimbo do `materialize_launch_env` e o vigia
    não arma — o arquivo do PRAGMATA segue dizendo a máscara do Freestyle.
    """
    freestyle = _perfil_de_mentira(FREESTYLE, "xbox")
    jogo = _perfil_de_mentira(JOGO, "dualsense")
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, jogo)])
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [freestyle, jogo])
    store = SimpleNamespace(window_detect_current_class=None, freestyle_ligado=True)
    daemon = SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=store,
    )
    le.materialize_launch_env(daemon)  # type: ignore[arg-type]
    assert "perfil gamepad xbox" in _o_estado_do_arquivo(tmp_path)

    store.freestyle_ligado = False
    le.vigiar_a_mesa(daemon, agora=100.0)
    regravou = le.rematerializar_se_sossegou(
        daemon, agora=100.0 + le.JANELA_DE_SOSSEGO_SEC)

    assert regravou is True
    assert "perfil gamepad dualsense" in _o_estado_do_arquivo(tmp_path)


def test_desligar_sem_jogo_regrava_as_envs_do_lancamento(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O botão desligado sem jogo vivo não passa pelo `profile.switch`: regrava aqui.

    MORDIDA: tire o `materialize_launch_env(self.daemon)` do ramo sem jogo de
    `_o_jogo_vivo_volta` e a lista fica vazia.
    """
    import hefesto_dualsense4unix.profiles.autoswitch as autoswitch_mod

    loader.load_all_profiles()
    store = StateStore()
    h = _Handlers(store, _liga(store))
    h.daemon = SimpleNamespace()
    regravadas: list[Any] = []
    monkeypatch.setattr(le, "materialize_launch_env", regravadas.append)
    monkeypatch.setattr(autoswitch_mod, "jogo_do_wrapper_vivo", lambda: None)

    asyncio.run(h._handle_freestyle_set({"ligado": False}))

    assert regravadas == [h.daemon]


# =============================================================================
# 5. O BOOT — o restore e o modo do primeiro pad
# =============================================================================

async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


@pytest.mark.parametrize("gravado", ["o-jogo", "outro-de-sempre"])
def test_o_restore_com_o_freestyle_ligado_restaura_o_freestyle(
    semeadura_ligada: None, gravado: str,
) -> None:
    """Ligado, o boot volta ao Freestyle — nem a sessão, nem a regra de janela.

    `outro-de-sempre` é um perfil «sempre» (MatchAny) na sessão: sem a cura o
    restore o ativava por cima do Freestyle ligado.

    MORDIDA: troque o `name = fora_do_jogo if manda else (...)` de
    `restore_last_profile` pelo nome da sessão antes do de fora do jogo e a célula
    `outro-de-sempre` reprova (a recusa do `activate` deixa o boot sem perfil).
    """
    loader.load_all_profiles()
    _o_jogo()
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0))
    nome = JOGO if gravado == "o-jogo" else "Leitura"
    session.save_last_profile(nome)
    session.save_active_marker(nome)
    store = StateStore()
    store.set_freestyle_ligado(True)
    controle = FakeController()
    controle.connect()

    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante, _native_mode=False)))

    assert (store.active_profile, store.perfil_adiado_por_janela) == (FREESTYLE, None)


def test_ligado_sem_o_arquivo_o_boot_desliga_o_modo(semeadura_ligada: None) -> None:
    """Ligado e sem o `freestyle.json` (ela o apagou): o boot desliga e segue.

    Sem isto, o modo ligado seguraria o produto sem perfil nenhum, para sempre:
    toda ativação automática seria recusada, e o restore não teria o que ativar.

    MORDIDA: tire o bloco `if manda and not fora_do_jogo:` de
    `restore_last_profile` e o boot termina sem perfil, com o modo ainda ligado.
    """
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0))
    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    session.save_last_profile("Leitura")
    session.save_active_marker("Leitura")
    store = StateStore()
    ligar_o_freestyle(store, True)
    controle = FakeController()
    controle.connect()

    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante, _native_mode=False)))

    assert (store.freestyle_ligado, session.load_freestyle_ligado(),
            store.active_profile) == (False, False, "Leitura")


def test_sair_do_nativo_com_ele_ligado_volta_ao_freestyle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A saída do Modo Nativo reativa o Freestyle, e não o `session.json`.

    Com o Nativo no boot não há restore, e `active_profile` fica vazio; a
    sessão pode apontar um perfil que o `activate` recusaria (`origin="system"`),
    e a saída do Nativo terminaria sem perfil.

    MORDIDA: devolva a `_reapply_last_profile` o `name = active_profile or
    load_last_profile()` de antes e o pedido sai com a Leitura.
    """
    import hefesto_dualsense4unix.profiles.manager as manager_mod
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    session.save_last_profile("Leitura")
    store = StateStore()
    store.set_freestyle_ligado(True)
    pedidos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        manager_mod, "gerente_do_daemon",
        lambda daemon, **kw: SimpleNamespace(
            activate=lambda nome, *, origin: pedidos.append((nome, origin))),
    )

    Daemon._reapply_last_profile(SimpleNamespace(store=store))  # type: ignore[arg-type]

    assert pedidos == [(FREESTYLE, "system")]


def test_o_primeiro_pad_nasce_no_modo_do_freestyle(semeadura_ligada: None) -> None:
    """A prova 5, no código: com ele ligado, o boot sobe o pad no modo DELE.

    O Freestyle dela está em Xbox, e a sessão aponta um perfil «sempre» em
    DualSense: o boot pergunta pelo Freestyle, pela memória e pelo disco.

    MORDIDA: tire o ramo `if manda:` de `perfil_que_o_boot_restaura` e as duas
    asserções reprovam com a Leitura.
    """
    loader.load_all_profiles()
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    dela = json.loads(arquivo.read_text(encoding="utf-8"))
    dela["mode"] = {"kind": "gamepad", "caminho": "xbox"}
    arquivo.write_text(json.dumps(dela), encoding="utf-8")
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0,
                                mode=ProfileModeConfig(kind="gamepad", caminho="dualsense")))
    session.save_last_profile("Leitura")
    session.save_active_marker("Leitura")
    store = StateStore()
    store.set_freestyle_ligado(True)
    session.save_freestyle_ligado(True)

    pela_memoria = connection.perfil_que_o_boot_restaura(store)
    pelo_disco = connection.perfil_que_o_boot_restaura()

    assert (pela_memoria.name, pela_memoria.mode.caminho) == (FREESTYLE, "xbox")
    assert (pelo_disco.name, pelo_disco.mode.caminho) == (FREESTYLE, "xbox")


# =============================================================================
# 6. O `freestyle.set` — ligar é o «Ativar», desligar devolve o jogo vivo
# =============================================================================

class _Handlers(IpcHandlersMixin):
    """O mixin de verdade, com o gerente de verdade e sem daemon."""

    def __init__(self, store: StateStore, gerente: ProfileManager) -> None:
        self.store = store
        self.profile_manager = gerente
        self.daemon = None


def test_ligar_pelo_botao_e_o_ativar_do_freestyle(semeadura_ligada: None) -> None:
    """O botão liga pelo MESMO caminho do «Ativar»: o Freestyle fica ativo, e o modo ligado."""
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    gerente = _gerente(store)
    gerente.activate(JOGO, origin="manual")
    h = _Handlers(store, gerente)

    resposta = asyncio.run(h._handle_freestyle_set({"ligado": True}))

    assert (resposta["freestyle_ligado"], store.active_profile) == (True, FREESTYLE)
    assert session.load_freestyle_ligado() is True
    assert asyncio.run(h._handle_freestyle_set({}))["freestyle_ligado"] is False


def _o_freestyle_de_fora_do_jogo(store: StateStore) -> _Handlers:
    """O estado de todo desktop desde o boot: o Freestyle valendo, com o modo desligado."""
    gerente = _gerente(store)
    gerente.activate(FREESTYLE, origin="system")
    assert (store.active_profile, store.freestyle_ligado) == (FREESTYLE, False)
    return _Handlers(store, gerente)


@pytest.mark.parametrize("ligado", [False, True], ids=["desligado", "ligado"])
def test_gravar_numa_aba_nao_muda_o_modo(semeadura_ligada: None, ligado: bool) -> None:
    """O gravar-e-reaplicar das abas reativa o Freestyle, e reativar não muda o modo.

    Conferência de 28/09/2026. Toda aba que grava passa pelo funil
    `interface/pacotes/perfil.gravar_e_reaplicar`, que manda `profile.switch`
    do perfil ativo — com a origem `manual`. Com o Freestyle de fora do jogo
    valendo (o desktop de toda máquina, desde o boot), o primeiro ajuste dela
    ligava o Modo Freestyle sozinho, e todo jogo seguinte perdia o perfil dele.
    É o funil de verdade, com o handler de verdade.

    MORDIDA: devolva ao ramo `origin == "manual"` do `activate` o
    `ligar_o_freestyle(self.store, e_o_freestyle(profile.name))` e a célula
    `desligado` reprova com o modo ligado.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as funil

    loader.load_all_profiles()
    store = StateStore()
    h = _o_freestyle_de_fora_do_jogo(store)
    if ligado:
        asyncio.run(h._handle_freestyle_set({"ligado": True}))
    ponte = SimpleNamespace(
        profile_switch=lambda nome: asyncio.run(h._handle_profile_switch({"name": nome})),
        chamar=lambda *a, **k: None,
    )

    funil.gravar_e_reaplicar(loader.load_profile(FREESTYLE),
                             SimpleNamespace(state={"active_profile": FREESTYLE}), ponte)

    assert (store.active_profile, store.freestyle_ligado,
            session.load_freestyle_ligado()) == (FREESTYLE, ligado, ligado)


def test_o_botao_liga_com_o_freestyle_ja_valendo(semeadura_ligada: None) -> None:
    """O botão no desktop, com o Freestyle de fora do jogo valendo: o modo liga.

    Ali a ativação do `freestyle.set` é uma reativação, e reativar não muda o
    modo — quem liga é o próprio `freestyle.set`, dizendo o modo.

    MORDIDA: tire o `ligar_o_freestyle(self.store, True)` do ramo de ligar do
    `_handle_freestyle_set` e o botão responde desligado.
    """
    loader.load_all_profiles()
    store = StateStore()
    h = _o_freestyle_de_fora_do_jogo(store)

    resposta = asyncio.run(h._handle_freestyle_set({"ligado": True}))

    assert (resposta["freestyle_ligado"], store.freestyle_ligado,
            session.load_freestyle_ligado()) == (True, True, True)


def test_desligar_devolve_o_jogo_vivo_sem_reabrir(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova 3: desligando, o PRAGMATA volta — com a janela dele em outra tela.

    MORDIDA: faça `_o_jogo_vivo_volta` devolver só o `active_profile` e o
    Freestyle continua valendo com o jogo aberto.
    """
    import hefesto_dualsense4unix.profiles.autoswitch as autoswitch_mod

    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    h = _Handlers(store, _liga(store))
    monkeypatch.setattr(autoswitch_mod, "jogo_do_wrapper_vivo", lambda: APPID)

    resposta = asyncio.run(h._handle_freestyle_set({"ligado": False}))

    assert (resposta["freestyle_ligado"], store.active_profile) == (False, JOGO)


def test_desligar_sem_jogo_solta_a_trava_de_trinta_segundos(semeadura_ligada: None) -> None:
    """Sem jogo vivo, o autoswitch decide no tique seguinte, sem esperar os 30 s."""
    import time

    loader.load_all_profiles()
    store = StateStore()
    h = _Handlers(store, _liga(store))
    store.mark_manual_profile_lock(time.monotonic() + 30)

    asyncio.run(h._handle_freestyle_set({"ligado": False}))

    assert store.manual_profile_lock_active(time.monotonic()) is False


def test_o_ligado_recusa_o_que_nao_e_booleano() -> None:
    h = _Handlers(StateStore(), _gerente(StateStore()))
    with pytest.raises(ValueError):
        asyncio.run(h._handle_freestyle_set({"ligado": "sim"}))


# =============================================================================
# 7. A MIGRAÇÃO — o cadeado de 23/07 ligado vira o Freestyle ligado
# =============================================================================

@pytest.mark.parametrize("cadeado", [True, False], ids=["ligado", "desligado"])
def test_o_cadeado_antigo_vira_o_freestyle_uma_vez(cadeado: bool) -> None:
    """Item 5: o `autoswitch_locked.flag` ligado vira `freestyle_ligado.flag`.

    Idempotente: a segunda leitura não acha o antigo, e o novo continua.

    MORDIDA: tire a chamada `_o_cadeado_antigo_vira_freestyle` do
    `load_freestyle_ligado` e a célula `ligado` reprova.
    """
    base = config_dir(ensure=True)
    antigo = base / "autoswitch_locked.flag"
    if cadeado:
        antigo.write_text("1\n", encoding="utf-8")

    assert session.load_freestyle_ligado() is cadeado
    assert not antigo.exists()
    assert session.load_freestyle_ligado() is cadeado


# =============================================================================
# 8. A MATRIZ — os quatro controles, USB e BT, no byte
# =============================================================================

class _FioDeMentira:
    """O `device` de um handle de bancada: guarda o que seria escrito, e só."""

    def __init__(self) -> None:
        self.quadros: list[bytes] = []

    def write(self, quadro: bytes) -> int:
        self.quadros.append(bytes(quadro))
        return len(quadro)


def _mesa_de_quatro(fabrica: Any) -> tuple[PyDualSenseController, list[Any]]:
    ctl = PyDualSenseController()
    pecas: list[Any] = []
    for mac, transporte in MESA:
        envelope = envelope_de(transporte)
        handle = fabrica(envelope)
        handle.device = _FioDeMentira()
        ctl._handles[mac] = handle
        pecas.append((handle, envelope))
    return ctl, pecas


def _o_gatilho_no_fio(handle: Any, envelope: EnvelopeDeTransporte) -> dict[str, int]:
    """O MODO de cada lado, lido do report que o handle monta."""
    common = envelope.extrair_common(handle.prepareReport())
    return {lado: common[modo] for lado, (modo, _f, _s) in OFFSETS_DO_GATILHO.items()}


def _modo_no_fio(nome: str, params: list[int]) -> int:
    return int(build_from_name(nome, params).mode)


def test_os_quatro_controles_ficam_com_o_freestyle_com_o_jogo_em_foco(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """A prova 1 no byte: o jogo em foco, e os quatro com o gatilho do Freestyle.

    O Freestyle de fábrica nasce RÍGIDO e o PRAGMATA pede `Off`: com a cura
    arrancada o autoswitch põe o PRAGMATA e os quatro vão a `Off` — no cabo e no
    rádio. Desligando, o PRAGMATA entra e os quatro vão a `Off`.

    MORDIDA: a da primeira célula deste arquivo (a LOCK-CEDE-01 de volta ao
    `_tick` e sem a recusa do `activate`).
    """
    loader.load_all_profiles()
    _o_jogo(gatilho="Off")
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    vigia = AutoSwitcher(manager=_liga(store, controle), window_reader=lambda: {},
                         store=store)

    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": JANELA, "wm_name": "PRAGMATA"}, t)

    rigido = _modo_no_fio("Rigid", [5, 200])
    esperado = {mac: {"right": rigido, "left": rigido} for mac, _ in MESA}
    no_fio = {mac: _o_gatilho_no_fio(h, e) for (mac, _), (h, e) in zip(MESA, pecas, strict=True)}
    assert (store.active_profile, no_fio) == (FREESTYLE, esperado)

    ligar_o_freestyle(store, False)
    for t in (31.0, 31.6):
        vigia._tick({"wm_class": JANELA, "wm_name": "PRAGMATA"}, t)

    desligado = _modo_no_fio("Off", [])
    no_fio = {mac: _o_gatilho_no_fio(h, e) for (mac, _), (h, e) in zip(MESA, pecas, strict=True)}
    assert (store.active_profile, no_fio) == (
        JOGO, {mac: {"right": desligado, "left": desligado} for mac, _ in MESA})


# =============================================================================
# 9. A GUARDA DO JOGO VIVO — o perfil do lançamento não sai por uma janela de fora
# =============================================================================

def _vigia_com_o_jogo(store: StateStore, vivo: list[int | None]) -> AutoSwitcher:
    gerente = _gerente(store)
    gerente.activate(JOGO, origin="launch")
    return AutoSwitcher(manager=gerente, window_reader=lambda: {}, store=store,
                        jogo_vivo_reader=lambda: vivo[0])


def test_com_o_jogo_vivo_a_janela_de_fora_nao_tira_o_perfil_dele(semeadura_ligada: None) -> None:
    """A L2 do PRAGMATA (27/09, 21:09:06), curada: a janela em outra tela não o tira.

    Com o jogo morto, a troca volta a sair no debounce de sempre.

    MORDIDA: devolva à `_recusa_a_troca_com_o_jogo_vivo` o termo antigo — só
    recusa com a janela do CLIENTE Steam (`e_janela_do_cliente_steam`) — e a
    primeira asserção reprova com o Freestyle entrando aos 12 s.
    """
    loader.load_all_profiles()
    _o_jogo()
    store = StateStore()
    vivo: list[int | None] = [APPID]
    vigia = _vigia_com_o_jogo(store, vivo)

    for t in (0.0, 0.6, 13.0, 60.0, 300.0):
        vigia._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, t)
    assert store.active_profile == JOGO

    vivo[0] = None
    for t in (301.0, 314.0):
        vigia._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, t)
    assert store.active_profile == FREESTYLE


def test_com_o_jogo_vivo_a_janela_de_outro_jogo_troca(semeadura_ligada: None) -> None:
    """O termo 1: outro jogo em foco não é "janela de fora" — ele troca."""
    loader.load_all_profiles()
    _o_jogo()
    outro = "steam_app_1599660"
    loader.save_profile(Profile(name="Sackboy", match=MatchCriteria(window_class=[outro]),
                                priority=80))
    store = StateStore()
    vigia = _vigia_com_o_jogo(store, [APPID])

    for t in (0.0, 0.6):
        vigia._tick({"wm_class": outro, "wm_name": "Sackboy"}, t)

    assert store.active_profile == "Sackboy"


# =============================================================================
# 10. O `gamepad.emulation.set` SEM CAMINHO pergunta o modo ao perfil ativo
# =============================================================================

class _DaemonDoChip:
    """Anota o pedido que chega ao setter — o `set_gamepad_emulation` real tem esta assinatura."""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.config = SimpleNamespace(gamepad_flavor="dualsense", gamepad_caminho=None)

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None, *, origin: str,
        caminho: str | None = None, caminho_e_escolha: bool = True,
        grava_o_modo: Any = False,
    ) -> bool:
        self.pedidos.append({"enabled": enabled, "caminho": caminho,
                             "caminho_e_escolha": caminho_e_escolha,
                             "grava_o_modo": grava_o_modo})
        return True


@pytest.mark.parametrize(("modo", "esperado"), [
    ({"kind": "gamepad", "caminho": "xbox"}, "xbox"),
    ({"kind": "gamepad", "caminho": "dualsense"}, "dualsense"),
    ({"kind": "desktop"}, None),
], ids=["xbox", "dualsense", "mouse-e-teclado"])
def test_ligar_sem_caminho_pergunta_o_modo_ao_perfil_ativo(
    semeadura_ligada: None, modo: dict[str, Any], esperado: str | None,
) -> None:
    """O chip «Jogar pelo Hefesto» saindo do Nativo: o pad sobe no modo do perfil.

    Nos três modos: Xbox, DualSense e mouse e teclado (a Navegação não diz o
    canal, e vale o padrão da máquina). O caminho do perfil não é escolha nova
    dela: vai com `caminho_e_escolha=False`, e o arquivo global não muda.

    MORDIDA: tire o `if enabled and caminho is None:` do
    `_handle_gamepad_emulation_set` e a célula `xbox` reprova com o pad em
    DualSense — o defeito que a conferência da -02 mediu.
    """
    loader.load_all_profiles()
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    dela = json.loads(arquivo.read_text(encoding="utf-8"))
    dela["mode"] = modo
    arquivo.write_text(json.dumps(dela), encoding="utf-8")
    store = StateStore()
    h = _Handlers(store, _liga(store))
    daemon = _DaemonDoChip()
    h.daemon = daemon

    asyncio.run(h._handle_gamepad_emulation_set({"enabled": True, "origin": "manual"}))

    pedido = daemon.pedidos[-1]
    assert pedido["caminho"] == esperado
    if esperado is not None:
        assert pedido["caminho_e_escolha"] is False


def test_o_caminho_que_ela_manda_vence_o_do_perfil(semeadura_ligada: None) -> None:
    """O chip de modo manda o caminho: o pedido dela é a escolha, e vai como escolha."""
    loader.load_all_profiles()
    store = StateStore()
    h = _Handlers(store, _liga(store))
    daemon = _DaemonDoChip()
    h.daemon = daemon

    asyncio.run(h._handle_gamepad_emulation_set(
        {"enabled": True, "origin": "manual", "caminho": "xbox"}))

    # E A PORTA VAI JUNTO (O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01, 29/09/2026): o
    # pedido à mão diz `grava_o_modo="ipc"`, e o setter grava o modo no perfil
    # ativo depois do aparelho.
    assert daemon.pedidos[-1] == {"enabled": True, "caminho": "xbox",
                                  "caminho_e_escolha": True,
                                  "grava_o_modo": "ipc"}
