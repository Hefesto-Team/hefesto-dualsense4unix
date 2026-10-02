"""O modo tem um dono, do boot à tela — O-MODO-XBOX-NAO-E-QUEDA-02.

A sessão dela de 27/09 mediu o mesmo defeito por quatro portas: o modo que o
perfil pôs de pé era desfeito por quem só devia RECRIAR o pad. Às 21h07 e às
23h28 o lançamento do PRAGMATA pôs o pad em DualSense, e segundos depois um
restart o devolveu ao Xbox sem que o diário dissesse quem pediu (L2,
`medidas/L2-pragmata/VEREDITO.md`). Cada restart tinha a sua fonte: a foto da
suspensão, o caminho do pad velho, ou nenhuma — e «nenhuma» LIMPAVA o slot, e
o Xbox da sessão voltava DualSense com um clique no cartão.

A cura consolidada (a sprint, «A cura, consolidada para quem implementa»):

1. o caminho vive num lugar só, o slot da sessão (`gamepad.caminho_da_sessao`),
   e todo restart lê dele e diz quem pediu (`p1_reerguido motivo=…`);
   (a) o arquivo da escolha dela guarda a origem, e a migração de 18/09 devolve
   só o valor sem origem;
3. o boot aplica o modo do perfil que restaura, uma vez, antes do primeiro pad,
   com ou sem foco X (os três boots de 27/09 às 21h: com foco, Xbox; sem foco,
   DualSense com a tela dizendo «Freestyle»).

As réguas fazem o pad nascer pelos métodos REAIS do daemon e do subsistema; só
a borda é dublada (a fábrica publica o que a real publica: a máscara efetiva, o
canal de `quer_uhid` e o caminho pendurado).
"""

from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session, xdg_paths

#: As escritas e leituras REAIS da sessão, guardadas no import — antes de a
#: bancada as trocar pelos dublês.
_SALVAR_EMULACAO_REAL = session.save_gamepad_emulation
_PREFERENCIA_REAL = session.load_gamepad_preference

#: A faixa sintética da casa — nenhum endereço real em arquivo versionado.
P1 = "aabbcc000001"


class _Vpad:
    """O pad de mentira: publica o que a fábrica real publica."""

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))
        self.parado = False

    def stop(self) -> None:
        self.parado = True


def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
    """A fábrica dublada veste a máscara EFETIVA, como a real."""
    return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)


def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
    if daemon._gamepad_device is not None:
        daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False


class _Store:
    native_mode_active = False

    def bump(self, *_a: Any, **_k: Any) -> None:
        return None


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
            gamepad_caminho_global=None,
            coop_enabled=True,
            rumble_active=(0, 0),
        )
        self.controller = SimpleNamespace(
            primary_uniq=P1, hidraw_path=lambda uniq=None: None
        )
        self._gamepad_device: Any = None
        self._mouse_device = None
        self._coop_manager: Any = None
        self.store = _Store()
        self._emu_lock = threading.Lock()
        self._native_mode = False
        self._emu_manual_ts = 0.0
        self._mode_from_profile: Any = None
        self._mascara_adiada_por_jogo: Any = None
        self._gamepad_multi_log = ""
        self._last_rebackend_ts = float("-inf")
        self.display_authority = "unknown"
        for nome in (
            "set_gamepad_emulation",
            "set_gamepad_emulation_desfecho",
            "vestir_a_mascara_do_aparelho",
            "aplicar_gamepad_para_multiplos_controles",
            "_log_gamepad_multi",
            "_restore_emulation_from_stash",
            "_esquecer_mascara_adiada",
        ):
            setattr(self, nome, functools.partial(getattr(lifecycle.Daemon, nome), self))

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def is_native_mode(self) -> bool:
        return self._native_mode

    def contar_controles_fisicos(self) -> int:
        return 2


def _dublar_a_borda(monkeypatch: pytest.MonkeyPatch, nascidos: list[Any]) -> None:
    """A borda do pad: a fábrica dublada (que conta quem nasce) e o que toca aparelho."""

    def _fabrica_que_conta(flavor: Any, **kw: Any) -> _Vpad:
        pad = _fabrica(flavor, **kw)
        nascidos.append(pad)
        return pad

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica_que_conta)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: True,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)


@pytest.fixture
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A borda dublada; o registro de máscaras zerado."""
    _dublar_a_borda(monkeypatch, [])
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(
        coop_mod, "get_coop_manager",
        lambda d: SimpleNamespace(sync=lambda force=False, origem=None: None),
    )
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(session, "load_gamepad_preference", lambda: (None, None))
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    yield
    em._zerar_registro_de_mascaras()


def _mesa_no_modo_xbox(cartao: str | None = None) -> _Daemon:
    """O perfil pôs o modo Xbox de pé: o pad do P1 no caminho Xbox, o dono em Xbox.

    A máscara do P1 é a DualSense da sessão (ou a do `cartao`): é com ela que
    um start sem opinião volta ao DualSense, e é o caso que morde.
    """
    if cartao is not None:
        em.registro_de_mascaras().set_mask(P1, cartao)
    d = _Daemon()
    desfecho = gp.start_gamepad_emulation_desfecho(d, None, origin="profile", caminho="xbox")
    assert desfecho == gp.EMU_APLICADO, "premissa da bancada"
    assert vp.caminho_do_vpad(d._gamepad_device) == "xbox"
    assert gp.caminho_da_sessao(d) == "xbox"
    return d


# ---------------------------------------------------------------------------
# Item 1 — todo restart lê o dono, e diz quem pediu
# ---------------------------------------------------------------------------


def _pela_ordem_do_coop(d: _Daemon) -> None:
    coop = coop_mod.CoopManager(d)  # type: ignore[arg-type]
    coop._derrubar_para_renascer(coop_mod._CHAVE_DO_P1)
    coop._reerguer_o_p1()


def _pelo_revive(d: _Daemon) -> None:
    _parar(d)
    d.config.gamepad_emulation_enabled = True
    assert gp.upgrade_primary_vpad_to_uhid(d) is True  # type: ignore[arg-type]


def _pela_volta_do_steam_input(d: _Daemon) -> None:
    # A foto da suspensão é de ANTES: um perfil entrou no meio e pôs o Xbox.
    _parar(d)
    d._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    d._steam_input_flavor_suspenso = "dualsense"  # type: ignore[attr-defined]
    d._steam_input_caminho_suspenso = "dualsense"  # type: ignore[attr-defined]
    assert gp.resume_vpads_after_steam_input(d) is True  # type: ignore[arg-type]


def _pelo_cartao(d: _Daemon) -> None:
    # O gesto do cartão escolhe MÁSCARA (do Pro de volta ao DualSense); o modo
    # é o do dono.
    em.registro_de_mascaras().set_mask(P1, "dualsense")
    assert d.vestir_a_mascara_do_aparelho(P1) == gp.EMU_APLICADO


def _pela_saida_do_modo_nativo(d: _Daemon) -> None:
    _parar(d)
    d._native_emu_stash = {"gamepad": [True, "dualsense"]}  # type: ignore[attr-defined]
    d._restore_emulation_from_stash()


def _por_dois_controles_na_mesa(d: _Daemon) -> None:
    _parar(d)
    assert d.aplicar_gamepad_para_multiplos_controles() == lifecycle.APLICADO


def _pelo_juiz_das_mascaras(d: _Daemon) -> None:
    em.registro_de_mascaras().set_mask(P1, "dualsense")
    assert gp.reconciliar_as_mascaras(d) == gp.EMU_APLICADO


#: motivo -> (o restart, o cartão do P1 antes dele). Os dois restarts de
#: máscara partem do Pro no cartão, para a troca ao DualSense ser o que recria.
RESTARTS: dict[str, tuple[Any, str | None]] = {
    "ordem_do_coop": (_pela_ordem_do_coop, None),
    "revive_pos_falha_total": (_pelo_revive, None),
    "volta_do_steam_input": (_pela_volta_do_steam_input, None),
    "mascara_do_cartao": (_pelo_cartao, "nintendo"),
    "saida_do_modo_nativo": (_pela_saida_do_modo_nativo, None),
    "dois_controles_na_mesa": (_por_dois_controles_na_mesa, None),
    "mascara_reconciliada": (_pelo_juiz_das_mascaras, "nintendo"),
}


@pytest.mark.usefixtures("_bancada")
@pytest.mark.parametrize("motivo", sorted(RESTARTS))
def test_todo_restart_renasce_no_modo_do_dono(motivo: str) -> None:
    """Com o modo Xbox de pé, nenhum restart devolve o pad ao DualSense.

    MORDE: tire o `caminho=` do cartão, da saída do Modo Nativo ou dos dois
    controles (o start sem opinião limpa o slot e o pad volta uhid); devolva à
    volta do Steam Input a foto da suspensão; ou à promoção o caminho do pad velho.
    """
    restart, cartao = RESTARTS[motivo]
    d = _mesa_no_modo_xbox(cartao)
    with structlog.testing.capture_logs() as diario:
        restart(d)

    assert d._gamepad_device is not None, "o restart não reergueu o pad"
    assert vp.caminho_do_vpad(d._gamepad_device) == "xbox", (
        f"o restart `{motivo}` escolheu o modo por conta própria: o pad voltou "
        f"{vp.caminho_do_vpad(d._gamepad_device)!r} com o dono em Xbox"
    )
    assert gp.caminho_da_sessao(d) == "xbox", "o restart mexeu no dono"
    assert {"event": "p1_reerguido", "motivo": motivo, "caminho": "xbox"} in [
        {k: r.get(k) for k in ("event", "motivo", "caminho")} for r in diario
    ], (
        "o restart não disse quem pediu: foi o buraco do diário de 27/09"
    )


@pytest.mark.usefixtures("_bancada")
def test_o_cartao_nao_vira_a_escolha_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto do cartão é `manual`, e o modo que ele repassa não é escolha.

    MORDE: tire o `caminho_e_escolha=False` do cartão e o modo da sessão vira
    a escolha dela no arquivo, como se ela tivesse apertado o PS + R3.
    """
    escritos: list[Any] = []
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda *a, **k: escritos.append(a))
    d = _mesa_no_modo_xbox("nintendo")
    _pelo_cartao(d)
    assert escritos == []
    assert d.config.gamepad_caminho_global is None


@pytest.mark.usefixtures("_bancada")
@pytest.mark.parametrize(
    ("dono", "backend"), [("dualsense", "uhid"), ("xbox", "uinput")], ids=["dualsense", "xbox"]
)
def test_a_promocao_segue_o_dono_e_nao_o_pad_velho(dono: str, backend: str) -> None:
    """O pad degradado renasce no modo do dono (a promoção é um restart), e diz quem pediu.

    O caso `xbox` é o que separa o dono do pad velho: o pad caiu no caminho
    DualSense e o dono já diz Xbox. Conferência de 28/09: com o dono igual ao
    pad, a régua passava com qualquer uma das duas fontes, e sem o diário.

    MORDE: devolva à promoção o caminho do pad que caiu (`caminho_do_vpad`) — o
    caso `xbox` renasce DualSense; ou tire o `nomear_o_restart` — o diário não
    diz `motivo=promocao_uhid`.
    """
    d = _Daemon()
    d.config.gamepad_emulation_enabled = True
    d.config.gamepad_caminho = dono
    velho = _Vpad("dualsense", P1, "dualsense")
    velho.backend = "uinput"
    d._gamepad_device = velho
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    assert vp.motivo_da_degradacao(velho) is not None, "premissa: o pad velho é queda"
    with pytest.MonkeyPatch.context() as mp, structlog.testing.capture_logs() as diario:
        mp.setattr(uhid_gamepad, "uhid_available", lambda: True)
        assert gp.upgrade_primary_vpad_to_uhid(d) is True  # type: ignore[arg-type]
    assert d._gamepad_device.backend == backend
    assert vp.caminho_do_vpad(d._gamepad_device) == dono
    assert {"event": "p1_reerguido", "motivo": "promocao_uhid", "caminho": dono} in [
        {k: r.get(k) for k in ("event", "motivo", "caminho")} for r in diario
    ], "a promoção não disse quem pediu"


# ---------------------------------------------------------------------------
# Item (a) — o arquivo dela guarda a origem, e a migração devolve só o legado
# ---------------------------------------------------------------------------


@pytest.fixture
def _arquivo_do_caminho() -> Iterator[Any]:
    pasta = xdg_paths.config_dir(ensure=True)
    alvo = pasta / "gamepad_caminho.flag"
    marca = pasta / session.MARCA_DO_CAMINHO_DEVOLVIDO
    alvo.unlink(missing_ok=True)
    marca.unlink(missing_ok=True)
    yield alvo
    alvo.unlink(missing_ok=True)
    marca.unlink(missing_ok=True)


class _DaemonDoGesto:
    """O suficiente para o `_guardar_o_caminho` REAL gravar a escolha dela."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(gamepad_caminho=None, gamepad_caminho_global=None)

    def _janela_de_jogo_em_foco(self) -> bool:
        return False


def test_o_gesto_fora_do_jogo_grava_com_a_origem(_arquivo_do_caminho: Any) -> None:
    gp._guardar_o_caminho(_DaemonDoGesto(), "xbox", origin="manual")  # type: ignore[arg-type]

    assert session.load_gamepad_caminho_com_origem() == ("xbox", "gesto_fora_do_jogo")


def test_a_escolha_dela_com_origem_sobrevive_aos_boots(_arquivo_do_caminho: Any) -> None:
    """O `xbox` que ela escolheu fora do jogo NÃO é o vazamento de 18/09.

    MORDE: tire da migração a pergunta pela origem e o primeiro boot desfaz a
    escolha dela.
    """
    gp._guardar_o_caminho(_DaemonDoGesto(), "xbox", origin="manual")  # type: ignore[arg-type]

    for _boot in range(2):
        lido = lifecycle._a_escolha_dela_sem_o_vazamento(
            *session.load_gamepad_caminho_com_origem()
        )
        assert lido == "xbox", "o boot desfez o Xbox que ela escolheu"
    assert session.load_gamepad_caminho_com_origem() == ("xbox", "gesto_fora_do_jogo")


def test_o_legado_sem_origem_volta_uma_vez(_arquivo_do_caminho: Any) -> None:
    """O arquivo antigo (só o caminho) é o legado: devolvido uma vez, com a marca."""
    _arquivo_do_caminho.write_text("xbox\n", encoding="utf-8")

    primeiro = lifecycle._a_escolha_dela_sem_o_vazamento(
        *session.load_gamepad_caminho_com_origem()
    )
    assert primeiro == "dualsense"
    assert session.load_gamepad_caminho_com_origem() == ("dualsense", "migracao_unica")

    _arquivo_do_caminho.write_text("xbox\n", encoding="utf-8")
    segundo = lifecycle._a_escolha_dela_sem_o_vazamento(
        *session.load_gamepad_caminho_com_origem()
    )
    assert segundo == "xbox", "a migração rodou duas vezes"


def test_arquivo_ilegivel_e_ninguem_escolheu(_arquivo_do_caminho: Any) -> None:
    _arquivo_do_caminho.write_text("{quebrado", encoding="utf-8")
    assert session.load_gamepad_caminho_com_origem() == (None, None)


# ---------------------------------------------------------------------------
# Item 3 — o boot aplica o modo do perfil que restaura, uma vez, com ou sem foco
# ---------------------------------------------------------------------------


@pytest.fixture
def _lar(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    """O lar de mentira: os XDG da régua, com a guarda que sai.

    As réguas daqui leem e gravam perfis, o registro de máscaras e os arquivos
    de sessão; se o `config_dir()` não for o do lar de mentira, a sessão para.
    """
    for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    casa = xdg_paths.config_dir(ensure=True)
    if not str(casa).startswith(str(tmp_path)):
        pytest.exit(f"a régua ia ler o config_dir de verdade: {casa}", returncode=3)
    em._zerar_registro_de_mascaras()
    return casa


#: O perfil que ela ativou à mão, fora de jogo: o que o boot restaura.
#:
#: NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`): estas
#: réguas usavam o Freestyle como o perfil de fora do jogo que o boot restaura,
#: e o ativavam pela origem `autoswitch`. O Freestyle desligado não vale em
#: lugar nenhum desde então, e o boot restaura a escolha dela; o que as réguas
#: medem (o modo do primeiro pad, a máscara que entra junto) não muda.
DE_FORA = "Desktop Dela"


@pytest.fixture
def _lar_do_boot(monkeypatch: pytest.MonkeyPatch, _lar: Any) -> Iterator[list[Any]]:
    """O lar de mentira com a escolha dela em Xbox e a emulação ligada no disco."""
    monkeypatch.setattr(session, "load_gamepad_preference", _PREFERENCIA_REAL)
    _SALVAR_EMULACAO_REAL(True, "dualsense")
    session.save_last_profile(DE_FORA)
    loader.save_profile(
        Profile(
            name=DE_FORA,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", caminho="xbox"),
        ),
        origem="teste",
    )
    nascidos: list[Any] = []
    _dublar_a_borda(monkeypatch, nascidos)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    em._zerar_registro_de_mascaras()
    yield nascidos
    em._zerar_registro_de_mascaras()


def _config_do_boot() -> lifecycle.DaemonConfig:
    return lifecycle.DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )


async def _o_boot(
    *, com_foco: bool, controle: Any = None, nome: str = DE_FORA
) -> lifecycle.Daemon:
    """Sobe o `Daemon` REAL até o restore, e (com foco) ativa a escolha dela como
    o autoswitch ativa: com o `apply_profile_mode` do daemon como applier."""
    store = StateStore()
    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )
    daemon = lifecycle.Daemon(
        controller=controle or FakeController(transport="usb", states=[estado]),
        bus=EventBus(), store=store, config=_config_do_boot(),
    )
    corrida = asyncio.create_task(daemon.run())
    try:
        for _ in range(600):
            if store.active_profile == nome and store.counter("poll.tick"):
                break
            await asyncio.sleep(0.01)
        assert store.active_profile == nome, f"o boot não restaurou a escolha dela ({nome!r})"
        if com_foco:
            from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

            gerente_do_daemon(daemon, store=store).activate(
                nome, origin="autoswitch"
            )
    finally:
        daemon.stop()
        await corrida
    return daemon


@pytest.mark.parametrize("com_foco", [False, True], ids=["sem-foco", "com-foco"])
def test_o_boot_nasce_no_modo_do_perfil_uma_vez(
    com_foco: bool, _lar_do_boot: list[Any]
) -> None:
    """A escolha dela em Xbox: o pad do P1 nasce em Xbox no boot, e nasce UMA vez.

    MORDE: tire do boot o caminho do perfil (o `_start_gamepad_emulation` volta
    a subir sem caminho) — sem foco o modo fica DualSense, e com foco o
    autoswitch recria o pad (dois `gamepad_emulation_started`).
    """
    with structlog.testing.capture_logs() as diario:
        daemon = asyncio.run(_o_boot(com_foco=com_foco))

    partidas = [r for r in diario if r["event"] == "gamepad_emulation_started"]
    assert [r.get("caminho") for r in partidas] == ["xbox"], (
        f"o boot subiu {len(partidas)} pad(s) do P1: {[r.get('caminho') for r in partidas]}"
    )
    assert len(_lar_do_boot) == 1, "o P1 nasceu mais de uma vez"
    assert vp.caminho_do_vpad(_lar_do_boot[0]) == "xbox"
    assert gp.caminho_da_sessao(daemon) == "xbox", "o dono da sessão não diz o modo do perfil"
    assert {"event": "modo_do_boot_pelo_perfil", "perfil": DE_FORA, "caminho": "xbox"} in [
        {k: r.get(k) for k in ("event", "perfil", "caminho")} for r in diario
    ]


def test_sem_perfil_que_opine_o_boot_e_o_de_sempre(
    _lar_do_boot: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A escolha dela sem `mode`: o pad nasce pela máscara (DualSense), e o slot vazio."""
    loader.save_profile(
        Profile(name=DE_FORA, match=MatchAny()), origem="teste"
    )
    with structlog.testing.capture_logs() as diario:
        daemon = asyncio.run(_o_boot(com_foco=False))
    partidas = [r.get("caminho") for r in diario if r["event"] == "gamepad_emulation_started"]
    assert partidas == ["dualsense"]
    assert gp.caminho_da_sessao(daemon) is None


@pytest.mark.parametrize("com_foco", [False, True], ids=["sem-foco", "com-foco"])
def test_o_boot_veste_a_mascara_do_perfil_uma_vez(
    com_foco: bool, _lar_do_boot: list[Any]
) -> None:
    """A escolha dela em Xbox COM a máscara Xbox: o P1 nasce vestido, e nasce uma vez.

    O modo do perfil é o caminho E a máscara (`mode.gamepad_flavor`). Conferência
    de 28/09: nenhuma régua olhava a máscara do boot.

    MORDE: tire do boot a máscara do perfil (`config.gamepad_flavor =
    mascara_do_boot`) — sem foco o P1 fica DualSense com o perfil dizendo Xbox,
    e com foco o autoswitch o recria (dois `gamepad_emulation_started`).
    """
    loader.save_profile(
        Profile(
            name=DE_FORA,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox", caminho="xbox"),
        ),
        origem="teste",
    )
    with structlog.testing.capture_logs() as diario:
        asyncio.run(_o_boot(com_foco=com_foco))

    partidas = [r for r in diario if r["event"] == "gamepad_emulation_started"]
    assert [(r.get("caminho"), r.get("flavor")) for r in partidas] == [("xbox", "xbox")], (
        f"o boot subiu {len(partidas)} pad(s) do P1: "
        f"{[(r.get('caminho'), r.get('flavor')) for r in partidas]}"
    )
    assert len(_lar_do_boot) == 1 and _lar_do_boot[0].flavor == "xbox"


def test_o_boot_restaura_a_escolha_de_janela_e_nasce_no_modo_dela(
    _lar_do_boot: list[Any],
) -> None:
    """A escolha dela é um perfil com regra de janela, em Xbox; o marcador, outro.

    NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 4):
    esta régua cobrava o contrário — o restore pulava o perfil de janela
    (RESTORE-ESCOPO-01) e o pad nascia no modo do Freestyle. A escolha dela
    volta com regra de janela ou sem, e o marcador é espelho: o boot lê o
    MESMO perfil que o restore ativa, e o pad nasce no Xbox dele.

    MORDE: faça o boot ler o marcador (o `resolve_boot_profile` de antes) — o
    P1 nasce DualSense, no modo do «Outro».
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria

    loader.save_profile(
        Profile(
            name="Jogo de janela",
            match=MatchCriteria(window_class=["jogo-de-janela"]),
            mode=ProfileModeConfig(kind="gamepad", caminho="xbox"),
        ),
        origem="teste",
    )
    loader.save_profile(Profile(name="Outro", match=MatchAny()), origem="teste")
    session.save_last_profile("Jogo de janela")
    session.save_active_marker("Outro")
    assert session.resolve_boot_profile() == "Jogo de janela", "premissa: a escolha dela"
    with structlog.testing.capture_logs() as diario:
        daemon = asyncio.run(_o_boot(com_foco=False, nome="Jogo de janela"))

    partidas = [r.get("caminho") for r in diario if r["event"] == "gamepad_emulation_started"]
    assert partidas == ["xbox"], (
        f"o boot não nasceu no modo do perfil que o restore ativou: {partidas}"
    )
    assert gp.caminho_da_sessao(daemon) == "xbox"


# ---------------------------------------------------------------------------
# Item 2 — o perfil que entra aplica o modo E a máscara, na mesma ativação
# ---------------------------------------------------------------------------
# G3 (a sessão dela, 27/09 23h38): o Future Knight abriu com o modo Xbox já de
# pé, e o P1 e o P3 ficaram com a máscara DualSense do Freestyle. (Desde
# 01/10/2026 o perfil de antes é a escolha dela, `DE_FORA`: o Freestyle
# desligado não entra por origem automática.) A ativação
# aplicava o `mode` ANTES das máscaras por controle: o pedido do P1 comparava a
# máscara com o cartão do perfil ANTERIOR (`ja_estava`), e o cartão novo só
# chegava ao registro depois, sem ninguém para vestir o P1 — o juiz das máscaras
# espera o jogo soltar a autoridade.


def _perfis_do_g3() -> None:
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    loader.save_profile(
        Profile(
            name=DE_FORA,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", caminho="xbox"),
            controllers={P1: ControllerOverrides(mascara="dualsense")},
        ),
        origem="teste",
    )
    loader.save_profile(
        Profile(
            name="Future Knight",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox", caminho="xbox"),
        ),
        origem="teste",
    )


def _daemon_do_g3() -> tuple[lifecycle.Daemon, Any]:
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    controle = FakeController(transport="usb")
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    store = StateStore()
    daemon = lifecycle.Daemon(controller=controle, store=store, config=_config_do_boot())
    return daemon, gerente_do_daemon(daemon, store=store)


@pytest.mark.usefixtures("_bancada")
@pytest.mark.parametrize("origem", ["autoswitch", "manual", "launch"])
def test_o_perfil_que_entra_veste_o_p1_na_mesma_ativacao(
    origem: str, _lar: Any
) -> None:
    """Freestyle (Xbox, cartão DualSense) → Future Knight (Xbox, máscara Xbox).

    MORDE: devolva o `apply_controller_mascaras` para DEPOIS do `mode_applier`
    em `ProfileManager.apply_emulation` — o P1 segue DualSense.
    """
    _perfis_do_g3()
    daemon, gerente = _daemon_do_g3()
    gerente.activate(DE_FORA, origin="autoswitch")
    assert daemon._gamepad_device is not None
    assert (daemon._gamepad_device.flavor, vp.caminho_do_vpad(daemon._gamepad_device)) == (
        "dualsense", "xbox"), "premissa: o Freestyle veste o P1 de DualSense no Xbox"

    gerente.activate("Future Knight", origin=origem)

    assert daemon._gamepad_device.flavor == "xbox", (
        "a máscara do perfil do jogo não chegou ao P1: o cartão do Freestyle "
        "seguiu vestido (G3)"
    )
    assert vp.caminho_do_vpad(daemon._gamepad_device) == "xbox"


@pytest.mark.usefixtures("_bancada")
@pytest.mark.parametrize("mascara", [None, "dualsense"], ids=["sem-mascara", "dualsense"])
@pytest.mark.parametrize("origem", ["autoswitch", "manual", "launch"])
def test_o_perfil_sem_caminho_nao_herda_o_xbox_do_anterior(
    origem: str, mascara: str | None, _lar: Any
) -> None:
    """Freestyle (Xbox) → um jogo `gamepad` SEM `caminho`: o P1 volta ao DualSense.

    Sem opinião de caminho vale o de fábrica, e nunca o do perfil anterior
    (CAMINHO-CONTAGIO-01, a ordem dela de 19/09 em `gamepad._caminho_a_herdar`:
    *«tudo ligado mascara dualsense por default»*).  <!-- noqa-acento: citação literal dela -->
    As réguas daquela sprint chamavam o start direto; a ativação de verdade
    tinha um atalho: com a máscara igual, o `apply_profile_mode` não pedia
    nada, e o pad seguia no
    caminho Xbox com a máscara DualSense (o uinput que o jogo não vê) — com o
    dono dizendo Xbox para todo restart seguinte. 26 dos 29 perfis dela não têm
    `caminho` (medido em 18/09). Conferência de 28/09.

    MORDE: tire do `apply_profile_mode` a pergunta pelo dono com o perfil sem
    caminho — o P1 fica `("xbox", "uinput")`, e o dono em Xbox.
    """
    loader.save_profile(
        Profile(
            name=DE_FORA,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", caminho="xbox"),
        ),
        origem="teste",
    )
    loader.save_profile(
        Profile(
            name="Jogo sem caminho",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=mascara),
        ),
        origem="teste",
    )
    daemon, gerente = _daemon_do_g3()
    gerente.activate(DE_FORA, origin="autoswitch")
    assert gp.caminho_da_sessao(daemon) == "xbox", "premissa: o Freestyle pôs o Xbox"

    gerente.activate("Jogo sem caminho", origin=origem)

    pad = daemon._gamepad_device
    assert (vp.caminho_do_vpad(pad), pad.backend) == ("dualsense", "uhid"), (
        "o perfil sem caminho herdou o Xbox do Freestyle: "
        f"{(vp.caminho_do_vpad(pad), pad.backend)}"
    )
    assert gp.caminho_da_sessao(daemon) is None, "o dono seguiu com o caminho do anterior"


#: O appid da régua: um jogo qualquer da biblioteca, só o número do marcador.
APPID_DO_G3 = 1599660


@pytest.mark.usefixtures("_bancada")
def test_o_arme_com_o_modo_ja_de_pe_veste_a_mascara_do_jogo(
    _lar: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ARME do Future Knight com o Xbox já de pé e o cartão do Freestyle no P1.

    É o caminho do G3 inteiro: o marcador do wrapper, o `arm_launch_profile`, a
    ativação do lançamento e a conferência do aparelho. O caminho já confere
    (`convergiu`), e a máscara do jogo tem de chegar mesmo assim.

    Sem o jogo na autoridade, o segundo `apply_profile_mode` do arme (depois
    da ativação) já veste a máscara — a ordem da ativação é medida pela régua de
    cima. Com o jogo na autoridade antes do `exec`, a R-04 recusa a troca: é a
    pendência que a sprint registra.

    MORDE: tire do arme a ativação do perfil (`_ativar_o_perfil_do_lancamento`)
    — o cartão do Freestyle fica no registro, e o P1 segue DualSense.
    """
    from hefesto_dualsense4unix.daemon import launch_env as le

    _perfis_do_g3()
    daemon, gerente = _daemon_do_g3()
    gerente.activate(DE_FORA, origin="autoswitch")
    assert daemon._gamepad_device is not None
    assert daemon._gamepad_device.flavor == "dualsense", "premissa: o cartão do Freestyle"
    perfil = loader.load_profile("Future Knight")
    (tmp_path / "last_run").write_text(
        f"appid={APPID_DO_G3}\nepoch=1000\npid=1\n", encoding="utf-8"
    )
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID_DO_G3, perfil)])
    monkeypatch.setattr(le, "steam_input_appids", lambda: set())
    monkeypatch.setattr(le, "materialize_launch_env", lambda d: None)

    resultado = le.arm_launch_profile(daemon, base_dir=tmp_path, now=1001.0)

    assert resultado is not None and resultado["armado"] is True, resultado
    assert daemon._gamepad_device.flavor == "xbox", (
        f"o arme não vestiu a máscara do jogo no P1 (resultado: {resultado})"
    )
    assert vp.caminho_do_vpad(daemon._gamepad_device) == "xbox"
    assert resultado["convergiu"] is True


# ---------------------------------------------------------------------------
# Item 4 — o P1 é o controle da carta 1 (a lâmpada que acende o «1»)
# ---------------------------------------------------------------------------
# A sessão dela de 27/09 (G0 e o arme das 21h07): o primário era o roxo, o
# primeiro que o backend enumerou, e a lâmpada dele dizia 3. O co-op pôs cada
# secundário no boneco da carta dele, e o vpad do P1 (carta 3) ficou fora de
# ordem: `coop_ordem_recriada recriar=[…, 'p1']` a cada start. A bancada é a de
# queda (backend, co-op e registro de identidade REAIS), com o provider de cor
# fiado como o `lifecycle._wire_identity_registry` fia.

from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    UNIQS,
    MesaDoJogo,
    Relogio,
    config_isolado,  # noqa: F401 — a fixture do lar de mentira da bancada
)

BRANCO, VERMELHO, ROXO, AZUL = UNIQS[:4]
#: A fila gravada da mesa dela: o branco é a carta 1, o azul a 4.
FILA_DELA = (BRANCO, VERMELHO, ROXO, AZUL)


def _gravar_a_fila_dela() -> None:
    """A fila de uma sessão anterior no disco do lar de mentira: branco 1 … azul 4."""
    from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry

    anterior = ControllerIdentityRegistry(clock=Relogio())
    anterior.sync_connected(list(FILA_DELA))


#: A matriz de transportes, na ordem da fila dela (branco, vermelho, roxo, azul).
TRANSPORTES = {
    "usb": ("usb", "usb", "usb", "usb"),
    "bt": ("bt", "bt", "bt", "bt"),
    "mista": ("usb", "bt", "usb", "bt"),
}


def _a_mesa_do_boot(
    monkeypatch: pytest.MonkeyPatch,
    chegada: tuple[str, ...],
    *,
    jogo: bool = False,
    transporte: str = "bt",
) -> MesaDoJogo:
    """O daemon sobe com a fila gravada, e os controles entram na ordem `chegada`.

    O vpad do P1 já está de pé (o `_safe_start("gamepad")` vem antes do primeiro
    `connect()`), e o provider de cor é o do produto. `transporte` escolhe a
    linha de :data:`TRANSPORTES`: cada controle entra pelo da sua carta.
    """
    from hefesto_dualsense4unix.daemon.subsystems.identity import make_auto_output_provider

    _gravar_a_fila_dela()
    bancada = MesaDoJogo(monkeypatch, relogio=(r := Relogio()), tempo=r, jogo=jogo)
    bancada.reg.load()
    bancada.inst.set_auto_output_provider(make_auto_output_provider(bancada.reg))
    pelo = dict(zip(FILA_DELA, TRANSPORTES[transporte], strict=True))
    for uniq in chegada:
        bancada.mesa.sentar(uniq, transporte=pelo[uniq])
    return bancada


def _recriacoes_do_p1(diario: list[dict[str, Any]]) -> list[Any]:
    return [
        r.get("recriar")
        for r in diario
        if r["event"] == "coop_ordem_recriada" and "p1" in (r.get("recriar") or [])
    ]


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", sorted(TRANSPORTES))
@pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
def test_o_p1_e_a_carta_1_e_nao_quem_conectou_primeiro(
    monkeypatch: pytest.MonkeyPatch, jogo: bool, transporte: str
) -> None:
    """Fila branco=1, vermelho=2, roxo=3, azul=4; o roxo conecta primeiro.

    Nos três transportes (conferência de 28/09: a régua só sentava pelo rádio).

    MORDE: devolva o `_quem_senta_no_posto` à 1ª chave de inserção
    (`next(iter(self._handles))`) — o roxo senta no posto, e o co-op recria o
    vpad do P1 para pô-lo atrás das cartas 1 e 2.
    """
    bancada = _a_mesa_do_boot(
        monkeypatch, (ROXO, BRANCO, VERMELHO, AZUL), jogo=jogo, transporte=transporte
    )
    vpad_do_p1 = bancada.vpad_do_p1
    with structlog.testing.capture_logs() as diario:
        for _ in range(4):
            bancada.tique()

    assert bancada.a_tela() == {u: n + 1 for n, u in enumerate(FILA_DELA)}, (
        "premissa: a lâmpada segue a fila gravada"
    )
    assert bancada.inst.primary_uniq == BRANCO, (
        f"o primário é {bancada.inst.primary_uniq}, e a carta 1 é o branco"
    )
    assert _recriacoes_do_p1(diario) == [], (
        f"o co-op recriou o vpad do P1 para pô-lo em ordem: {_recriacoes_do_p1(diario)}"
    )
    assert bancada.daemon._gamepad_device is vpad_do_p1 and vpad_do_p1.vivo
    assert bancada.o_jogo_ve() == {n + 1: u for n, u in enumerate(FILA_DELA)}
    bancada.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
def test_o_numero_que_ela_troca_na_tela_leva_o_posto(
    monkeypatch: pytest.MonkeyPatch, jogo: bool
) -> None:
    """Ela dá o «1» ao vermelho na aba Controles: o posto vai com a lâmpada.

    Sem hotplug nenhum — o `connect()` só roda a cada ~30 s com a mesa parada —,
    quem pergunta é o tique lento (`seguir_a_carta`), logo depois do registro.

    MORDE: tire o ramo da carta menor do `_quem_senta_no_posto` (o posto
    ocupado não se reelege) — o branco segue primário com a lâmpada dizendo 2.
    """
    bancada = _a_mesa_do_boot(monkeypatch, (BRANCO, VERMELHO, ROXO, AZUL), jogo=jogo)
    for _ in range(3):
        bancada.tique()
    assert bancada.inst.primary_uniq == BRANCO

    bancada.reg.escolha_da_mao({VERMELHO: 1, BRANCO: 2, ROXO: 3, AZUL: 4})
    bancada.reg.liberar_as_lampadas()
    assert bancada.a_tela()[VERMELHO] == 1, "premissa: o vermelho acende o 1"

    with structlog.testing.capture_logs() as diario:
        assert bancada.inst.seguir_a_carta() is True
    assert bancada.inst.primary_uniq == VERMELHO
    assert [r.get("uniq") for r in diario if r["event"] == "primario_segue_a_carta"], (
        "o diário não disse que o posto seguiu a carta"
    )
    assert bancada.inst.seguir_a_carta() is False, "a segunda pergunta não muda nada"

    # E a mesa se refaz sem ninguém perder o controle: o co-op recolhe o vpad
    # que o vermelho tinha como secundário e dá um ao branco, sem EBUSY e sem
    # dois vpads com o mesmo endereço (as invariantes da bancada, a cada tique).
    for _ in range(4):
        bancada.tique()
    assert bancada.inst.primary_uniq == VERMELHO
    assert bancada.dono_do_vpad_do_p1() == VERMELHO
    bancada.o_jogo_segue_a_tela()


class _ControleQueSegueACarta(FakeController):
    """O Fake com a pergunta do backend real, contada."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.perguntas = 0

    def seguir_a_carta(self) -> bool:
        self.perguntas += 1
        return False


def test_o_tique_lento_pergunta_a_carta(_lar_do_boot: list[Any]) -> None:
    """O laço do daemon pergunta ao backend, a cada tique lento, se a carta 1 mudou.

    MORDE: tire o `self._seguir_a_carta()` do tique lento do `_poll_loop` — o
    backend nunca é perguntado, e o número que ela troca na tela só levaria o
    posto no próximo hotplug.
    """
    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )
    controle = _ControleQueSegueACarta(transport="usb", states=[estado])
    asyncio.run(_o_boot(com_foco=False, controle=controle))
    assert controle.perguntas >= 1, "o tique lento não perguntou a carta ao backend"


# ---------------------------------------------------------------------------
# Item 6 — o número do jogador é da pessoa: quem sai não renumera os outros
# ---------------------------------------------------------------------------
# G6 (27/09, 23h42, `medidas/sessao/G6-o-branco-no-cabo-e-a-volta/`): o branco
# foi para o cabo, e no meio da troca o daemon pintou um 5 no azul e um 4 no
# branco; quando a mesa voltou a 1, 2, 3 e 4, ninguém repintou as lâmpadas de
# jogador. Duas causas: a numeração do co-op deixava o `fallback` de quem estava
# FORA (na troca) tomar o número da carta de quem estava na mesa, e a camada do
# co-op só se republicava num ciclo com hotplug — o número que muda sem mexer em
# `/dev/input` (a lâmpada liberada depois, o número trocado na tela) ficava
# pintado com o de antes.


def _numero_aceso(bancada: MesaDoJogo, uniq: str) -> int | None:
    """O número que o backend escreveria na barra de jogador de `uniq`, com o co-op."""
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    with bancada.inst._io_lock:
        bits = bancada.inst._merged_desired_for_key(uniq, incluir_coop=True).player_leds
    return next((n for n in range(1, 9) if player_led_pattern(n) == bits), None)


def _nome_do_microfone(bancada: MesaDoJogo, uniq: str) -> int | None:
    """O «Controle N» do nó de som, pela mesma função que o `bt_mic` usa."""
    from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa

    conectados = [c for c in bancada.inst.describe_controllers() if c.get("connected")]
    return numero_do_assento_na_mesa(conectados, uniq, daemon=bancada.daemon)


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
def test_a_carta_1_sai_e_os_outros_seguem_2_3_4(
    monkeypatch: pytest.MonkeyPatch, jogo: bool
) -> None:
    """O branco sai: o vermelho, o roxo e o azul seguem 2, 3 e 4 na lâmpada e no microfone.

    MORDE: faça o `slot_de_sessao` (`subsystems/base.py`) não responder — o nome
    do microfone cai na contagem de quem está conectado, e diz 1, 2 e 3.
    """
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=jogo)
    for _ in range(3):
        bancada.tique()
    ficaram = FILA_DELA[1:]
    assert {u: _numero_aceso(bancada, u) for u in FILA_DELA} == {
        u: n + 1 for n, u in enumerate(FILA_DELA)
    }, "premissa: a mesa acende 1, 2, 3 e 4"

    bancada.mesa.levantar(BRANCO)
    for _ in range(5):
        bancada.tique()
        assert {u: _numero_aceso(bancada, u) for u in ficaram} == {
            VERMELHO: 2, ROXO: 3, AZUL: 4
        }, "a lâmpada de quem ficou mudou de número"
        assert {u: _nome_do_microfone(bancada, u) for u in ficaram} == {
            VERMELHO: 2, ROXO: 3, AZUL: 4
        }, "o nome do microfone de quem ficou mudou de número"


def test_quem_esta_fora_na_troca_nao_toma_o_numero_de_quem_esta_na_mesa() -> None:
    """A tabela que o G6 deixou: o roxo trocando de transporte, fora da mesa.

    O `player_index` de cada jogador é o índice de ALOCAÇÃO do vpad, e depois de
    quedas e voltas ele não é a carta (no G6, o branco era secundário com o 2).
    O roxo fora não tem lâmpada; o `fallback` dele não pode tirar o 4 do azul.

    MORDE: volte `numeros_de_jogador` à passada única — o azul acende 3.
    """
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
    from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry

    registro = ControllerIdentityRegistry(clock=(relogio := Relogio()))
    registro.sync_connected(list(FILA_DELA))
    relogio.avancar(2.0)
    registro.sync_connected([BRANCO, VERMELHO, AZUL])  # o roxo saiu: o lugar fica guardado
    daemon = SimpleNamespace(
        config=lifecycle.DaemonConfig(coop_enabled=True),
        controller=SimpleNamespace(primary_uniq=BRANCO),
        identity_registry=registro,
    )
    coop = CoopManager(daemon)  # type: ignore[arg-type]
    for uniq, indice in ((ROXO, 4), (VERMELHO, 3), (AZUL, 2)):
        coop._players[uniq] = _SecondaryPlayer(
            identity=uniq, evdev_path="/dev/input/event90", reader=None,  # type: ignore[arg-type]
            player_index=indice,
        )

    assert coop.numeros_de_jogador() == {BRANCO: 1, ROXO: 3, VERMELHO: 2, AZUL: 4}


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
def test_o_numero_novo_repinta_a_lampada_sem_hotplug(
    monkeypatch: pytest.MonkeyPatch, jogo: bool
) -> None:
    """Ela troca o 2 e o 3 na tela: as lâmpadas se repintam sem ninguém mexer em /dev/input.

    MORDE: tire a republicação do tique quieto do `CoopManager.sync` — o
    vermelho e o roxo ficam com o número de antes aceso.
    """
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=jogo)
    for _ in range(3):
        bancada.tique()
    # Daqui em diante /dev/input não muda: o ciclo cheio do co-op não roda.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda _self: False
    )
    bancada.reg.escolha_da_mao({BRANCO: 1, ROXO: 2, VERMELHO: 3, AZUL: 4})
    bancada.reg.liberar_as_lampadas()
    for _ in range(3):
        bancada.tique()

    assert {u: _numero_aceso(bancada, u) for u in FILA_DELA} == {
        BRANCO: 1, ROXO: 2, VERMELHO: 3, AZUL: 4
    }, "a lâmpada ficou com o número de antes"
