"""O modo Xbox não é queda — o modo, a máscara e a forma de conexão são três eixos.

Na noite de 27/09 o diário disse `vpad_degradado motivo=sem_uhid` para cada
jogador que conectava. Não havia queda nenhuma: o Freestyle carregava
`caminho: xbox`, o modo que ela escolheu pelo PS + R3, e os pads nasceram no
`uinput` por escolha. O `dedup_status` já sabia disso; o anúncio do co-op
(`coop._promote_player`) e o motivo por controle do estado
(`ipc_handlers._vpad_backend_motivo`) não perguntavam o caminho.

A pergunta passou a ter um dono só, `virtual_pad.motivo_da_degradacao`, e as
réguas daqui fazem o pad nascer pela FÁBRICA de verdade (`make_virtual_pad`),
com o evdev de mentira, para medir o que o produto pendura no pad e não o que
um dublê diz dele.

Mordidas: devolva ao `_promote_player` o critério antigo (máscara DualSense no
uinput, sem o caminho) e o anúncio volta no modo Xbox; devolva ao
`_vpad_backend_motivo` o piso `sem_uhid` sem o caminho e o estado volta a dizer
queda.

E a promoção do connect (`gamepad.upgrade_primary_vpad_to_uhid`) era o sétimo
lugar, achado no diário do install de 27/09 às 16h15: o Freestyle aplicou o
modo Xbox, o controle conectou, e a promoção tratou o pad como queda, o
recriou sem caminho e o modo da sessão voltou ao DualSense
(`vpad_promovendo_para_uhid` seguido de `caminho=dualsense`). Mordidas: devolva
ao gate a pergunta só pela máscara, ou tire o caminho do restart.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems import gamepad
from hefesto_dualsense4unix.daemon.subsystems.gamepad import dedup_status
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_DUALSENSE,
    CAMINHO_XBOX,
    make_virtual_pad,
    motivo_da_degradacao,
)
from hefesto_dualsense4unix.integrations.virtual_pad import (
    caminho_do_vpad as vp_caminho_do_vpad,
)
from tests.unit.test_vpad_ff_passthrough import _EC, _AbsInfo

#: Faixa sintética da casa (a IEEE nunca dá `aa:bb:cc` a fabricante).
_JOGADOR_2 = "aabbcc0000a7"


class _UInputDeMentira:
    """O `evdev.UInput` sem kernel: nasce, escreve em lugar nenhum e fecha."""

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        self.events = events
        self.kwargs = kwargs
        self.fd = -1

    def write(self, etype: int, code: int, value: int) -> None:
        return

    def syn(self) -> None:
        return

    def close(self) -> None:
        return

    def read_one(self) -> None:
        return None


@pytest.fixture
def fabrica_sem_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fábrica real, com o `uinput` de mentira e o `uhid` fora do ar."""
    mod = types.ModuleType("evdev")
    mod.UInput = _UInputDeMentira  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)


def _pad(caminho: str | None, mascara: str = "dualsense") -> Any:
    pad = make_virtual_pad(mascara, caminho=caminho, player=2)
    assert pad is not None, "a fábrica não entregou pad nenhum"
    return pad


@pytest.mark.usefixtures("fabrica_sem_kernel")
class TestODonoSeparaEscolhaDeQueda:
    def test_o_modo_xbox_com_a_mascara_dualsense_e_escolha(self) -> None:
        pad = _pad(CAMINHO_XBOX)
        try:
            assert (pad.backend, pad.flavor) == ("uinput", "dualsense")
            assert motivo_da_degradacao(pad) is None
        finally:
            pad.stop()

    def test_o_modo_dualsense_sem_uhid_e_queda_com_o_motivo_da_fabrica(self) -> None:
        pad = _pad(CAMINHO_DUALSENSE)
        try:
            assert pad.backend == "uinput"
            assert motivo_da_degradacao(pad) == "uhid_indisponivel"
        finally:
            pad.stop()

    def test_sem_modo_escolhido_a_mascara_dualsense_pede_o_uhid(self) -> None:
        pad = _pad(None)
        try:
            assert motivo_da_degradacao(pad) == "uhid_indisponivel"
        finally:
            pad.stop()

    def test_a_mascara_que_o_uhid_nao_veste_nao_e_queda(self) -> None:
        pad = _pad(CAMINHO_DUALSENSE, mascara="xbox")
        try:
            assert motivo_da_degradacao(pad) is None
        finally:
            pad.stop()


def _daemon(caminho: str | None, publicados: list[tuple[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            coop_enabled=True,
            gamepad_flavor="dualsense",
            gamepad_caminho=caminho,
            gamepad_emulation_enabled=True,
        ),
        is_native_mode=lambda: False,
        _gamepad_device=None,
        controller=SimpleNamespace(hidraw_path=lambda uniq=None: None),
        bus=SimpleNamespace(publish=lambda topico, dado: publicados.append((topico, dado))),
    )


def _promove(caminho: str | None, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, list]:
    publicados: list[tuple[str, Any]] = []
    daemon = _daemon(caminho, publicados)
    manager = CoopManager(daemon)  # type: ignore[arg-type]
    daemon._coop_manager = manager
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    leitor = SimpleNamespace(
        grab_state="held", set_grab=lambda g: True, stop=lambda: None, snapshot=lambda: None
    )
    jogador = _SecondaryPlayer(
        identity=_JOGADOR_2, evdev_path="/dev/input/event7", reader=leitor, player_index=2
    )
    manager._players[_JOGADOR_2] = jogador
    manager._promote_player(jogador)
    assert jogador.vpad is not None, "o co-op não promoveu o jogador"
    return daemon, publicados


@pytest.mark.usefixtures("fabrica_sem_kernel")
class TestOCoopEOEstadoPerguntamAoDono:
    def test_o_jogador_do_modo_xbox_nao_e_anunciado_como_queda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon, publicados = _promove(CAMINHO_XBOX, monkeypatch)
        vpad = daemon._coop_manager._players[_JOGADOR_2].vpad
        try:
            assert (vpad.backend, vpad.flavor) == ("uinput", "dualsense")
            assert publicados == [], (
                "o modo Xbox que ela escolheu foi anunciado como queda "
                "(`vpad_degradado`): foi o diário da noite de 27/09"
            )
            assert IpcHandlersMixin._vpad_backend_motivo(vpad) == ("uinput", None)
        finally:
            vpad.stop()

    def test_o_jogador_do_modo_dualsense_sem_uhid_e_anunciado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon, publicados = _promove(CAMINHO_DUALSENSE, monkeypatch)
        vpad = daemon._coop_manager._players[_JOGADOR_2].vpad
        try:
            assert publicados == [("vpad.degraded", {"player": 2, "motivo": "uhid_indisponivel"})]
            assert IpcHandlersMixin._vpad_backend_motivo(vpad) == (
                "uinput",
                "uhid_indisponivel",
            )
        finally:
            vpad.stop()

    def test_o_dedup_diz_o_mesmo_que_o_anuncio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for caminho, esperado in ((CAMINHO_XBOX, []), (CAMINHO_DUALSENSE, ["jogador_2_uinput"])):
            daemon, _ = _promove(caminho, monkeypatch)
            daemon._gamepad_device = SimpleNamespace(flavor="dualsense", backend="uhid")
            vpad = daemon._coop_manager._players[_JOGADOR_2].vpad
            try:
                assert dedup_status(daemon) == (not esperado, esperado), caminho
            finally:
                vpad.stop()


def _connect(pad: Any, monkeypatch: pytest.MonkeyPatch) -> tuple[bool, list[Any]]:
    """O controle conecta com o `pad` já de pé e o uhid de volta ao ar.

    O uhid só volta DEPOIS de o pad nascer: a fábrica real, com ele no ar,
    abriria o `/dev/uhid` da máquina.
    """
    partidas: list[Any] = []
    monkeypatch.setattr(
        gamepad, "stop_gamepad_emulation", lambda _d, **kw: partidas.append(("stop", kw))
    )
    monkeypatch.setattr(
        gamepad,
        "start_gamepad_emulation",
        lambda _d, flavor=None, **kw: partidas.append(("start", kw)) or True,
    )
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    # O caminho da promoção é o do DONO da sessão (O-MODO-XBOX-NAO-E-QUEDA-02,
    # 28/09): o do pad, que é o que o dono diz enquanto ninguém muda de modo.
    daemon = SimpleNamespace(
        _gamepad_device=pad,
        controller=SimpleNamespace(hidraw_path=lambda uniq=None: None),
        config=SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=True,
            gamepad_caminho=vp_caminho_do_vpad(pad),
        ),
    )
    return gamepad.upgrade_primary_vpad_to_uhid(daemon), partidas  # type: ignore[arg-type]


@pytest.mark.usefixtures("fabrica_sem_kernel")
class TestAPromocaoDoConnectPerguntaAoDono:
    def test_o_modo_xbox_nao_e_promovido_quando_o_controle_conecta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pad = _pad(CAMINHO_XBOX)
        try:
            promoveu, partidas = _connect(pad, monkeypatch)
            assert (promoveu, partidas) == (False, []), (
                "o connect promoveu o pad do modo Xbox para o uhid e desfez a "
                "escolha dela: foi o Freestyle no install de 27/09"
            )
        finally:
            pad.stop()

    def test_o_pad_que_caiu_renasce_no_caminho_em_que_nasceu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pad = _pad(CAMINHO_DUALSENSE)
        try:
            promoveu, partidas = _connect(pad, monkeypatch)
            assert promoveu is True
            assert partidas[-1] == ("start", {"origin": "profile", "caminho": CAMINHO_DUALSENSE}), (
                "a promoção muda só o canal; sem o caminho o start não opina e "
                "o modo da sessão volta ao default"
            )
        finally:
            pad.stop()


def test_o_revive_depois_da_falha_total_volta_no_modo_da_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem pad nenhum (o boot perdeu a corrida da ACL), o revive recria o P1 no
    modo que a sessão escolheu. Mordida: tire o `caminho=` do revive."""
    partidas: list[Any] = []
    monkeypatch.setattr(
        gamepad,
        "start_gamepad_emulation",
        lambda _d, flavor=None, **kw: partidas.append(kw) or True,
    )
    daemon = SimpleNamespace(
        _gamepad_device=None,
        controller=SimpleNamespace(hidraw_path=lambda uniq=None: None),
        config=SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=True,
            gamepad_caminho=CAMINHO_XBOX,
        ),
    )
    assert gamepad.upgrade_primary_vpad_to_uhid(daemon) is True  # type: ignore[arg-type]
    assert partidas == [{"origin": "profile", "caminho": CAMINHO_XBOX}]


@pytest.mark.parametrize(
    ("devolucao", "gravador"),
    [
        ("_a_escolha_dela_sem_o_vazamento", "save_gamepad_caminho"),
        ("_a_mascara_dela_sem_o_vazamento", "save_gamepad_emulation"),
    ],
)
def test_a_devolucao_do_xbox_roda_uma_vez_e_a_escolha_seguinte_fica(
    devolucao: str, gravador: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O primeiro boot devolve o `xbox` do vazamento de 18 a 21/09; o seguinte,
    com o `xbox` que ela escolheu depois, não mexe. Mordida: tire a marca."""
    from hefesto_dualsense4unix.daemon import lifecycle
    from hefesto_dualsense4unix.utils import session

    escritos: list[Any] = []
    monkeypatch.setattr(session, gravador, lambda *a, **k: escritos.append(a))
    funcao = getattr(lifecycle, devolucao)

    assert funcao("xbox") == "dualsense"
    assert len(escritos) == 1
    assert funcao("xbox") == "xbox", "o segundo boot desfez o Xbox que ela escolheu"
    assert len(escritos) == 1
