"""MODO-DE-CONEXAO-01 — o chip de modo escolhe o CAMINHO, e nunca a máscara.

A queixa dela, 13/09/2026, está citada na sprint: o chip «Xbox» da aba Jogar
dizia «aplicado» e não mudava nada. A causa, medida pelo estudo: o plano do chip
mandava a MÁSCARA (`gamepad.emulation.set {flavor: "xbox"}`), o cartão do P1 a
vencia em `mascara_efetiva`, e `start_gamepad_emulation_desfecho` respondia
`ja_estava` antes de gravar qualquer coisa. O perfil ativo recebia
`gamepad_flavor = "xbox"` e o jogo continuava recebendo o DualSense.

A regra dela (a sprint cita as três mensagens): o MODO é a base, a MÁSCARA vem
por cima e independe dele. Esta régua a cobra de ponta a ponta, pelo gesto REAL
(`a01_jogar.modo_xbox`), pelo handler REAL (`_handle_gamepad_emulation_set`) e
pelos métodos REAIS do `lifecycle.Daemon`, até o vpad. Só a borda é dublada: o
vpad (nenhum `/dev/uinput`, nenhum `/dev/uhid`), o grab, o launch env, a flag de
sessão e o co-op.

MORDE, e são duas curas independentes:

* devolver a máscara ao `_plano_do_chip` (o plano volta a mandar `flavor`) — o
  daemon responde `ja_estava`, o vpad não é recriado e o caminho não muda;
* a idempotência só por máscara em `start_gamepad_emulation_desfecho` (tirar o
  `mesmo_canal`) — a mesma resposta `ja_estava`, pelo outro lado.
"""
from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.utils import session, xdg_paths

#: A faixa sintética da casa — nada de endereço real em arquivo versionado.
P1 = "aabbcc000001"
PERFIL = "Bancada"


class _Vpad:
    """O vpad de mentira. O canal sai da regra do produto (`quer_uhid`)."""

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


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self, sessao: str) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor=sessao,
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
            coop_enabled=True,
            rumble_active=(0, 0),
        )
        self.controller = SimpleNamespace(primary_uniq=P1)
        self._gamepad_device: Any = None
        self._mouse_device = None
        self._coop_manager = None
        self.store = None
        self._emu_lock = threading.Lock()
        self._native_mode = False
        self._emu_manual_ts = 0.0
        self._mode_from_profile = None
        self.display_authority = "unknown"
        self.set_gamepad_emulation = functools.partial(
            lifecycle.Daemon.set_gamepad_emulation, self
        )
        self.set_gamepad_emulation_desfecho = functools.partial(
            lifecycle.Daemon.set_gamepad_emulation_desfecho, self
        )

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def _esquecer_mascara_adiada(self, _m: Any) -> None:
        return

    def set_mouse_emulation(self, enabled: bool, *_a: Any, **_kw: Any) -> bool:
        return bool(enabled)

    def set_emulation_suppressed(self, value: Any = None) -> bool:
        return bool(value)

    def set_keyboard_emulation(self, enabled: bool, **_kw: Any) -> bool:
        return bool(enabled)


class _Ponte:
    """O `p` do gesto: despacha o plano para o HANDLER REAL do IPC."""

    def __init__(self, daemon: _Daemon) -> None:
        self.daemon = daemon
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.pedidos.append((metodo, dict(params)))
        if metodo == "gamepad.emulation.set":
            asyncio.run(
                ih.IpcHandlersMixin._handle_gamepad_emulation_set(
                    SimpleNamespace(daemon=self.daemon), params  # type: ignore[arg-type]
                )
            )
        elif metodo == "native.mode.set":
            self.daemon.set_native_mode(bool(params.get("enabled")))
        return True


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A borda dublada; o registro de máscaras e o lembrete da aba zerados."""
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: False,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(
        coop_mod, "get_coop_manager", lambda d: SimpleNamespace(sync=lambda force=False: None)
    )
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda ativo, flavor=None: None)
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda caminho: None)
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    yield
    em._zerar_registro_de_mascaras()
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def _preparar(sessao: str, cartao: str) -> _Daemon:
    """Perfil ativo com a máscara no cartão do P1, e o vpad de pé pelo perfil."""
    loader.save_profile(
        Profile(
            name=PERFIL,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=sessao),
            controllers={P1: ControllerOverrides(mascara=cartao)},
        ),
        origem="teste",
    )
    em.registro_de_mascaras().set_mask(P1, cartao)
    d = _Daemon(sessao)
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO
    return d


def _estado(d: _Daemon) -> dict[str, Any]:
    """O pedaço do `state_full` que a aba lê — o caminho pelo MESMO leitor do daemon."""
    emu: dict[str, Any] = {
        "enabled": bool(d.config.gamepad_emulation_enabled),
        "flavor": d.config.gamepad_flavor,
        "caminho": ih._caminho_publicado(d),
        "por_aparelho": {P1: em.mascara_efetiva(P1, d.config.gamepad_flavor)},
    }
    if d._gamepad_device is not None:
        emu["backend"] = d._gamepad_device.backend
    return {
        "connected": True,
        "native_mode": d._native_mode,
        "paused": False,
        "active_profile": PERFIL,
        "gamepad_emulation": emu,
    }


def _ctx(d: _Daemon) -> Contexto:
    return Contexto(state=_estado(d), mesa=[], conectados=[], estados={})


def _mascara_do_cartao_no_disco() -> str | None:
    controles = loader.load_profile(PERFIL).controllers or {}
    return next((c.mascara for c in controles.values()), None)


def test_o_chip_xbox_troca_o_caminho_e_a_mascara_do_cartao_fica() -> None:
    """Cartão do P1 em DualSense: «Xbox» recria o vpad no canal comum, vestindo DualSense."""
    d = _preparar("dualsense", "dualsense")
    antes = d._gamepad_device
    assert (antes.backend, antes.flavor) == ("uhid", "dualsense"), "premissa da bancada"
    assert aba._estado_da_tela(_estado(d))["modo-aceso"] == "dualsense", "premissa"

    ponte = _Ponte(d)
    aba.modo_xbox(_ctx(d), {"texto": "Xbox"}, ponte)

    vivo = d._gamepad_device
    assert vivo is not antes and antes.parado, (
        "o vpad não foi recriado: o daemon respondeu `ja_estava` e o chip disse "
        f"«aplicado» sobre nada. Pedidos: {ponte.pedidos}"
    )
    assert vivo.backend == "uinput", "o caminho Xbox é o canal comum"
    assert vivo.flavor == "dualsense", "o chip de modo trocou a máscara"
    assert d.config.gamepad_flavor == "dualsense", "o chip de modo trocou a máscara da sessão"
    assert ih._caminho_publicado(d) == "xbox"

    estado = _estado(d)
    assert aba._estado_da_tela(estado)["modo-aceso"] == "xbox"
    assert estado["gamepad_emulation"]["por_aparelho"][P1] == "dualsense", "o cartão mudou"
    assert aba._faixa_do_pendente(estado) == ("", ""), "a pendência «Xbox» não morreu"

    gravado = loader.load_profile(PERFIL)
    assert gravado.mode is not None
    assert gravado.mode.caminho == "xbox", "o caminho não chegou ao perfil ativo"
    assert gravado.mode.gamepad_flavor == "dualsense", "o chip escreveu a máscara no perfil"
    assert _mascara_do_cartao_no_disco() == "dualsense"


def test_com_o_cartao_em_xbox_360_o_chip_acende_o_escolhido_e_nao_a_mascara() -> None:
    """Cartão do P1 em Xbox 360: «Sony DualSense» fica escolhido e aceso (§D.2).

    O `uhid` só se constrói com máscara DualSense, então os dois caminhos dão o
    MESMO aparelho: recriar o vpad aqui arrancaria o controle do jogo por nada.
    """
    d = _preparar("dualsense", "xbox")
    antes = d._gamepad_device
    assert (antes.backend, antes.flavor) == ("uinput", "xbox"), "premissa da bancada"
    assert aba._estado_da_tela(_estado(d))["modo-aceso"] == "xbox", (
        "premissa: sem caminho escolhido, ele sai da máscara, como antes da cura"
    )

    aba.modo_dualsense(_ctx(d), {"texto": "Sony DualSense"}, _Ponte(d))

    assert d._gamepad_device is antes and not antes.parado, (
        "recriou o vpad sem mudar de canal"
    )
    assert ih._caminho_publicado(d) == "dualsense", "o caminho escolhido não ficou"

    estado = _estado(d)
    assert aba._estado_da_tela(estado)["modo-aceso"] == "dualsense", (
        "o chip de modo acendeu pela máscara, e não pelo caminho escolhido"
    )
    assert estado["gamepad_emulation"]["por_aparelho"][P1] == "xbox", "o cartão mudou"
    assert aba._faixa_do_pendente(estado) == ("", "")

    gravado = loader.load_profile(PERFIL)
    assert gravado.mode is not None
    assert gravado.mode.caminho == "dualsense"
    assert gravado.mode.gamepad_flavor == "dualsense", "a máscara padrão do perfil mudou"
    assert _mascara_do_cartao_no_disco() == "xbox"


# ---------------------------------------------------------------------------
# ACRESCENTADAS NA VALIDAÇÃO — 13/09/2026
# ---------------------------------------------------------------------------
# As duas cenas acima dublam a fábrica, leem o caminho por `_caminho_publicado`
# e nunca reativam um perfil. Medido na validação: arrancar o caminho da fábrica
# REAL, do bloco `gamepad_emulation` do `state_full` ou de `apply_profile_mode`
# passava com as quatro réguas novas e as vizinhas verdes. As três abaixo mordem.

#: A fábrica REAL, guardada no import — antes de o `_bancada` trocá-la pelo dublê.
_FABRICA_REAL = vp.make_virtual_pad


@pytest.mark.parametrize(("caminho", "tenta_uhid"), [("xbox", False), ("dualsense", True)])
def test_a_fabrica_real_decide_o_canal_pelo_caminho(
    monkeypatch: pytest.MonkeyPatch, caminho: str, tenta_uhid: bool
) -> None:
    """Máscara DualSense nos dois casos: só o caminho DualSense tenta o `uhid`.

    MORDE: `make_virtual_pad` voltar a decidir o canal só pela máscara — o caminho
    Xbox subiria o DualSense Edge pelo `uhid`, e o chip «Xbox» voltaria a não
    mudar nada no aparelho.
    """
    pedidos: list[str] = []

    def _espiao(flavor: str, **_kw: Any) -> tuple[None, str]:
        pedidos.append(flavor)
        return None, "uhid_indisponivel"

    monkeypatch.setattr(vp, "_try_uhid", _espiao)
    # Só o `start`, que abriria o nó do kernel — o molde de
    # `test_mascara_por_controle_manda_no_vpad._sem_no_de_kernel`.
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    monkeypatch.setattr(UinputGamepad, "start", lambda self: True)

    pad = _FABRICA_REAL("dualsense", identity=P1, allow_uhid=True, caminho=caminho)

    assert pad is not None and pad.flavor == "dualsense", "a máscara não é do caminho"
    assert bool(pedidos) is tenta_uhid, f"caminho {caminho!r}: `_try_uhid` recebeu {pedidos}"
    assert vp.caminho_do_vpad(pad) == caminho, "o pad não diz em que caminho nasceu"
    # O canal comum ESCOLHIDO não é degradação; o DualSense que caiu nele é.
    assert (getattr(pad, "fallback_motivo", None) is not None) is tenta_uhid


def _daemon_do_perfil(vpad: Any) -> tuple[Any, list[dict[str, Any]]]:
    """Só o que `apply_profile_mode` lê, e um gravador no lugar do pedido ao vpad."""
    pedidos: list[dict[str, Any]] = []
    d = SimpleNamespace(
        config=SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=vpad.flavor, gamepad_caminho=None
        ),
        _gamepad_device=vpad,
        _emu_manual_ts=0.0,
        _mode_pendente=None,
        _modo_jogo_padrao=None,
        _modo_jogo_padrao_log="",
        _native_mode=False,
        _mode_from_profile=None,
    )
    d._furar_lock_de_emulacao = lambda eixo, agora=None: None
    d._agendar_modo_adiado = lambda *a, **k: None
    d._pedir_mascara_do_perfil = lambda flavor, **k: bool(pedidos.append({"flavor": flavor, **k}))
    d._reavaliar_mascara_adiada = lambda f: None
    d.set_native_mode = lambda *a, **k: None
    return d, pedidos


def test_o_perfil_sem_caminho_nao_muda_de_aparelho_e_o_com_caminho_muda() -> None:
    """§D.1: um perfil de antes da cura não tem `mode.caminho` e dá o MESMO aparelho.

    E o perfil que escolheu um caminho o pede ao vpad quando entra.

    MORDE: tirar de `apply_profile_mode` o termo do caminho — o perfil com
    ``caminho="xbox"`` entra e o vpad segue no `uhid`.
    """
    uhid = _Vpad("dualsense", P1, "dualsense")
    assert uhid.backend == "uhid", "premissa"
    antigo = Profile(
        name=PERFIL,
        match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )
    assert "caminho" not in antigo.mode.model_dump(), "o perfil antigo ganhou a chave nova"

    for origem in ("manual", "autoswitch"):
        d, pedidos = _daemon_do_perfil(uhid)
        lifecycle.Daemon.apply_profile_mode(d, antigo.mode, profile=antigo, origin=origem)
        assert pedidos == [], f"{origem}: o perfil sem caminho pediu outro aparelho: {pedidos}"

    com_caminho = antigo.model_copy(
        update={"mode": ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense",
                                          caminho="xbox")}
    )
    d, pedidos = _daemon_do_perfil(uhid)
    lifecycle.Daemon.apply_profile_mode(d, com_caminho.mode, profile=com_caminho, origin="manual")
    assert [p.get("caminho") for p in pedidos] == ["xbox"], (
        f"o perfil com caminho entrou e não o pediu ao vpad: {pedidos}"
    )


def test_o_state_full_publica_o_caminho_que_acende_o_chip() -> None:
    """O chip de modo acende pelo `gamepad_emulation.caminho` do `state_full` REAL.

    As cenas acima leem `_caminho_publicado` direto; a tela lê o handler. Com o
    vpad no canal comum, só este campo separa o Xbox escolhido do DualSense que
    degradou — e só o segundo é degradação.

    MORDE: tirar o `"caminho"` do bloco `gamepad_emulation` do
    `_handle_daemon_state_full` — o chip «Xbox» fica apagado com o vpad no Xbox.
    """
    from hefesto_dualsense4unix.testing import FakeController

    class _Handlers(ih.IpcHandlersMixin):
        def __init__(self, daemon: Any) -> None:
            self.daemon = daemon  # type: ignore[assignment]
            self.store = daemon.store
            self.controller = daemon.controller

    daemon = lifecycle.Daemon(controller=FakeController(transport="usb"))
    daemon.controller.primary_uniq = P1  # type: ignore[attr-defined]
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = "dualsense"
    for caminho, degradado in (("xbox", False), ("dualsense", True)):
        daemon._gamepad_device = SimpleNamespace(  # type: ignore[assignment]
            flavor="dualsense", backend="uinput", caminho=caminho, ff_supported=True,
            fallback_motivo="uhid_indisponivel",
        )
        daemon.config.gamepad_caminho = caminho
        cheio = asyncio.run(_Handlers(daemon)._handle_daemon_state_full({}))
        emu = cheio["gamepad_emulation"]
        assert emu.get("caminho") == caminho, f"o state_full não publicou o caminho: {emu}"
        assert emu.get("degraded") is degradado, f"caminho {caminho!r}: degraded={emu}"
        assert aba._estado_da_tela(cheio)["modo-aceso"] == caminho, (
            f"o chip de modo não acendeu o caminho {caminho!r} publicado"
        )


# ---------------------------------------------------------------------------
# ACRESCENTADA NA SEGUNDA VALIDAÇÃO — 13/09/2026
# ---------------------------------------------------------------------------
# As três bancadas desta sprint trocam `session.save_gamepad_caminho` por um
# dublê, e nenhuma régua lia a flag do caminho no boot. Medido: arrancar do
# `Daemon.run` a leitura de `load_gamepad_caminho`, ou gravar o caminho dentro da
# flag velha, passava com todas as réguas verdes.

#: As escritas REAIS da sessão, guardadas no import — antes de o `_bancada`
#: trocá-las pelos dublês.
_SALVAR_EMULACAO_REAL = session.save_gamepad_emulation
_SALVAR_CAMINHO_REAL = session.save_gamepad_caminho


class _ParouNoTecladoError(Exception):
    """O boot chegou ao restore do teclado: o do caminho já tinha passado."""


def test_o_caminho_escolhido_volta_com_o_boot_e_a_flag_velha_nao_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§I, `utils/session.py`: o caminho persiste AO LADO da flag, que o boot lê.

    Três metades: só o gesto manual persiste (a R-07 do liga/desliga); o
    `gamepad_emulation.flag` sai byte a byte igual; e o `Daemon.run` REAL devolve
    à config o caminho que ela escolheu.

    MORDE: tirar do `run` a leitura de `load_gamepad_caminho` (o boot nasce sem o
    caminho), gravar o caminho dentro do `gamepad_emulation.flag` (a flag velha
    muda de formato) ou persistir fora do gesto manual.
    """
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(session, "save_gamepad_caminho", _SALVAR_CAMINHO_REAL)
    pasta = xdg_paths.config_dir(ensure=True)
    velha = pasta / "gamepad_emulation.flag"
    nova = pasta / "gamepad_caminho.flag"
    try:
        _SALVAR_EMULACAO_REAL(True, "dualsense")
        bytes_da_velha = velha.read_bytes()
        nova.unlink(missing_ok=True)
        d = SimpleNamespace(config=SimpleNamespace(gamepad_caminho=None))

        gp._guardar_o_caminho(d, "xbox", origin="profile")  # type: ignore[arg-type]
        assert d.config.gamepad_caminho == "xbox"
        assert session.load_gamepad_caminho() is None, "um perfil persistiu o caminho dela"

        gp._guardar_o_caminho(d, "xbox", origin="manual")  # type: ignore[arg-type]
        assert session.load_gamepad_caminho() == "xbox", "o gesto dela não persistiu"
        assert velha.read_bytes() == bytes_da_velha, "a flag velha mudou de formato"
        assert session.load_gamepad_emulation() == (True, "dualsense")

        def _parar(*_a: Any, **_k: Any) -> None:
            raise _ParouNoTecladoError

        monkeypatch.setattr(session, "load_keyboard_preference", _parar)
        daemon = lifecycle.Daemon(controller=FakeController(transport="usb"))
        try:
            with pytest.raises(_ParouNoTecladoError):
                asyncio.run(daemon.run())
        finally:
            for nome in ("_executor", "_external_executor"):
                pool = getattr(daemon, nome, None)
                if pool is not None:
                    pool.shutdown(wait=False)
        # NOTA DATADA — 19/09/2026, CAMINHO-CONTAGIO-01, ponto 3. Esta linha
        # exigia `"xbox"`, e agora o boot DEVOLVE esse valor ao default: o
        # `gamepad_caminho.flag` da máquina dela dizia `xbox` desde 18/09 às
        # 11:18 porque o PS + R3 dentro do DON'T SCREAM gravava nos dois
        # lugares, e não por escolha dela para todos os jogos.
        #
        # O que este teste promete no NOME continua medido, e melhor: o boot
        # LEU o arquivo — se não tivesse lido, `gamepad_caminho` teria ficado
        # em `None`, o default da config, e não em `dualsense`. A devolução só
        # acontece para quem leu `xbox`.
        assert daemon.config.gamepad_caminho == "dualsense", (
            "o boot não leu o caminho dela — sem leitura o slot fica em None"
        )
        assert session.load_gamepad_caminho() == "dualsense", (
            "a devolução não chegou ao disco: o boot seguinte leria `xbox` de novo"
        )
        if not daemon._native_mode:
            assert (daemon.config.gamepad_emulation_enabled, daemon.config.gamepad_flavor) == (
                True, "dualsense"), "o boot passou a ler a flag velha de outro jeito"
    finally:
        velha.unlink(missing_ok=True)
        nova.unlink(missing_ok=True)
