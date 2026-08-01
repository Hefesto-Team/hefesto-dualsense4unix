"""SOM-02 (E3) — a devolução da posse do alto-falante, o irmão do `mic release`.

O `release_audio_volumes` existia no handle desde o AUDIO-OWNER-01 e NADA acima
dele o chamava: o serviço não tinha método, o IPC não tinha chave, a ponte não
tinha função e a linha de comando não tinha verbo. Sem essa porta, o PRIMEIRO
uso do volume sequestrava o alto-falante do controle até a próxima desconexão.

O que cada bloco daqui MORDE (cada mordida foi arrancada uma vez, conferida
reprovando, e devolvida):

- a limpeza da preferência no `release`: deixá-la viva faz um `muted=False`
  posterior ressuscitar o volume antigo e RETOMAR a posse sem ninguém pedir;
- a porta acima do handle: sem o ramo `release` no `speaker.set`, o pedido cai
  na chamada vazia, que toma a posse e manda ZERO (armadilha 1, medida) — a
  chave `speaker` não some do estado, ela vira `{'volume': 0, 'muted': True}`;
- a guarda do mudo sem volume conhecido: sem ela, mudo como primeira escrita
  tranca o alto-falante em zero e o próprio mudo não o solta (armadilha 2);
- os bits de áudio do `flag0` depois da devolução: a asserção que o
  AUDIO-OWNER-01 já sabia fazer, agora do outro lado do ciclo;
- a quarta categoria da trava manual (`audio`): sem ela o autoswitch reaplica o
  perfil na troca de janela por cima do volume que ela acabou de ajustar.

MACs fake (regra da casa).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_OVERRIDE_CATEGORIES,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

MAC1 = "aabbcc000001"
MAC2 = "aabbcc000002"


# ---------------------------------------------------------------------------
# Handles e backend REAIS — nada de dublê onde a conta é o que está em teste
# ---------------------------------------------------------------------------


def _handle_real() -> Any:
    """Handle da pydualsense sem device — só o estado que o builder lê.

    Mesmo molde do `tests/unit/test_audio_owner_report.py`: o `_build_common`
    é a única testemunha do que sai no fio, e um dublê de handle não teria os
    bits de validação para provar nada.
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._mic_mute_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h.connected = True
    h.conType = SimpleNamespace(name="USB")
    return h


def _backend_com_dois() -> tuple[Any, Any, Any]:
    """`PyDualSenseController` real com dois handles reais e sem hardware."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    h1, h2 = _handle_real(), _handle_real()
    inst._handles = {"AA:BB:CC:00:00:01": h1, "AA:BB:CC:00:00:02": h2}
    inst._primary_key = "AA:BB:CC:00:00:01"
    return inst, h1, h2


class TestBackendDevolveAPosse:
    def test_release_zera_os_bits_de_audio_do_report(self) -> None:
        """A prova no FIO: depois da devolução o flag0 sai sem áudio nenhum.

        MORDIDA: arrancar o `release_audio_volumes()` do serviço deixa
        `flag0 & VALID_FLAG0_AUDIO_MASK` valendo 0x30 (fone + alto-falante) e os
        bytes 4/5 em 180 — o hefesto continuaria mandando o volume para sempre.
        """
        inst, h1, _h2 = _backend_com_dois()
        assert inst.set_speaker_volume(180, uniq=MAC1) is True
        common = h1._build_common(rumble_asserted=False)
        assert common[0] & rep.VALID_FLAG0_SPEAKER_VOLUME
        assert common[0] & rep.VALID_FLAG0_HEADPHONE_VOLUME
        assert common[rep.COMMON_SPEAKER_VOLUME] == 180

        assert inst.release_speaker_volume(uniq=MAC1) is True
        common = h1._build_common(rumble_asserted=False)
        assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0
        assert list(common[4:8]) == [0, 0, 0, 0]

    def test_release_apaga_a_preferencia(self) -> None:
        inst, h1, _h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        assert h1._speaker_volume_pref == 180
        inst.release_speaker_volume(uniq=MAC1)
        assert h1._speaker_volume_pref is None
        assert h1._volumes_audio == [None, None, None, None]

    def test_muted_false_depois_do_release_nao_reabre_a_posse(self) -> None:
        """A MORDIDA da entrega: sem a limpeza da preferência, isto reabre.

        Arrancando o `alvo._speaker_volume_pref = None` do
        `release_speaker_volume`, a preferência sobrevive em 180, o
        `muted=False` a "restaura" e o hefesto volta a mandar o volume em todo
        report — posse retomada sem ninguém pedir. Medido: com a cura arrancada
        este teste reprova em `speaker_state_for is None`.
        """
        inst, h1, _h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        inst.release_speaker_volume(uniq=MAC1)

        assert inst.set_speaker_volume(muted=False, uniq=MAC1) is False
        assert h1._volumes_audio == [None, None, None, None]
        assert inst.speaker_state_for(MAC1) is None
        common = h1._build_common(rumble_asserted=False)
        assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0

    def test_mudo_como_primeira_escrita_e_recusado(self) -> None:
        """Armadilha 2, na raiz: sem volume conhecido, `muted` não escreve nada.

        Sem esta guarda a sequência mudo/desmudo termina em
        `{'volume': 0, 'muted': True}` e o próprio botão não solta o
        alto-falante.
        """
        inst, h1, _h2 = _backend_com_dois()
        assert inst.set_speaker_volume(muted=True, uniq=MAC1) is False
        assert inst.set_speaker_volume(muted=False, uniq=MAC1) is False
        assert h1._volumes_audio == [None, None, None, None]
        assert getattr(h1, "_speaker_volume_pref", None) is None
        assert inst.speaker_state_for(MAC1) is None

    def test_com_volume_conhecido_o_par_mudo_desmudo_funciona(self) -> None:
        """O outro lado da guarda: com volume de verdade, o par sobrevive.

        Medido na sprint: `volume=180` -> `muted=True` manda 0 e guarda 180 ->
        `muted=False` devolve os 180.
        """
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        assert inst.set_speaker_volume(muted=True, uniq=MAC1) is True
        assert inst.speaker_state_for(MAC1) == {"volume": 180, "muted": True}
        assert inst.set_speaker_volume(muted=False, uniq=MAC1) is True
        assert inst.speaker_state_for(MAC1) == {"volume": 180, "muted": False}

    def test_release_so_solta_o_controle_do_uniq(self) -> None:
        inst, h1, h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        inst.set_speaker_volume(90, uniq=MAC2)
        inst.release_speaker_volume(uniq=MAC1)
        assert h1._volumes_audio == [None, None, None, None]
        assert h2._volumes_audio[1] == 90
        assert inst.speaker_state_for(MAC2) == {"volume": 90, "muted": False}

    def test_release_sem_uniq_vai_no_primario(self) -> None:
        inst, h1, h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        inst.set_speaker_volume(90, uniq=MAC2)
        assert inst.release_speaker_volume() is True
        assert h1._volumes_audio == [None, None, None, None]
        assert h2._volumes_audio[1] == 90

    def test_release_de_controle_inexistente_devolve_false(self) -> None:
        """Pedido que cai no vazio tem de se declarar — não pode virar "ok"."""
        inst, _h1, _h2 = _backend_com_dois()
        assert inst.release_speaker_volume(uniq="aabbcc0000ff") is False

    def test_release_e_idempotente(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)
        assert inst.release_speaker_volume(uniq=MAC1) is True
        assert inst.release_speaker_volume(uniq=MAC1) is True
        assert inst.speaker_state_for(MAC1) is None

    def test_handle_que_estoura_nao_vira_sucesso(self) -> None:
        inst, h1, _h2 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=MAC1)

        def _explode() -> None:
            raise OSError("controle sumiu no meio da devolução")

        h1.release_audio_volumes = _explode  # type: ignore[method-assign]
        assert inst.release_speaker_volume(uniq=MAC1) is False


# ---------------------------------------------------------------------------
# O fio: `speaker.set {release: true}` num IpcServer de verdade
# ---------------------------------------------------------------------------


class _ControllerComSpeaker(FakeController):
    """Dublê de transporte com a ARITMÉTICA real do backend por dentro.

    O que interessa provar aqui é a cadeia — IPC -> serviço -> handle -> estado
    publicado —, e um dublê que só guardasse o pedido passaria com a cura
    arrancada. Por isso os três métodos de áudio delegam a um
    `PyDualSenseController` de verdade com handles reais.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.real, self.h1, self.h2 = _backend_com_dois()
        self.pedidos: list[tuple[str, Any, Any, Any]] = []
        self.aceita = True

    def set_speaker_volume(
        self,
        volume: int | None = None,
        *,
        muted: bool | None = None,
        uniq: str | None = None,
    ) -> bool:
        self.pedidos.append(("set", volume, muted, uniq))
        if not self.aceita:
            return False
        return self.real.set_speaker_volume(volume, muted=muted, uniq=uniq)

    def release_speaker_volume(self, *, uniq: str | None = None) -> bool:
        self.pedidos.append(("release", None, None, uniq))
        if not self.aceita:
            return False
        return self.real.release_speaker_volume(uniq=uniq)

    def speaker_state_for(self, uniq: str | None = None) -> dict[str, Any] | None:
        return self.real.speaker_state_for(uniq)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: target)
    return target


@pytest.fixture
async def daemon_vivo(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    """`IpcServer` real ouvindo num socket de teste, com dois controles."""
    fc = _ControllerComSpeaker(transport="usb")
    fc.connect()
    fc.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"index": 0, "connected": True, "transport": "usb",
         "is_primary": True, "uniq": MAC1},
        {"index": 1, "connected": True, "transport": "usb",
         "is_primary": False, "uniq": MAC2},
    ]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock._bt_mic_subsystem = None
    daemon_mock._hotkey_manager = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False, mouse_speed=6, mouse_scroll_speed=1,
        rumble_policy="balanceado", rumble_policy_custom_mult=0.7,
        mic_button_toggles_system=True, bt_mic_enabled=False,
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=socket_path, daemon=daemon_mock,
    )
    await server.start()
    try:
        yield SimpleNamespace(
            socket=socket_path, fc=fc, store=store, server=server
        )
    finally:
        await server.stop()


async def _chamar(socket_path: Path, metodo: str, params: Any = None) -> Any:
    async with IpcClient.connect(socket_path) as client:
        return await client.call(metodo, params or {})


def _entrada(payload: dict[str, Any], uniq: str) -> dict[str, Any]:
    for entry in payload["controllers"]:
        if entry.get("uniq") == uniq:
            return entry
    raise AssertionError(f"controle {uniq} ausente do payload")


class TestReleaseNoProtocolo:
    """Entra pelo FIO: método não roteado é chamada que não existe."""

    @pytest.mark.asyncio
    async def test_a_chave_speaker_some_do_estado(self, daemon_vivo: Any) -> None:
        """MORDIDA da porta acima do handle.

        Arrancando o ramo `release` do `_handle_speaker_set`, o payload cai na
        chamada vazia — que toma a posse e manda ZERO — e a chave `speaker`
        NÃO some: ela vira `{'volume': 0, 'muted': True}`. Medido com a cura
        arrancada: este teste reprova exatamente aí.
        """
        env = daemon_vivo
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})
        payload = await _chamar(env.socket, "daemon.state_full")
        assert _entrada(payload, MAC1)["speaker"]["volume"] == 180

        res = await _chamar(env.socket, "speaker.set", {"release": True, "uniq": MAC1})
        assert res["status"] == "ok"
        assert res["speaker"] is None
        payload = await _chamar(env.socket, "daemon.state_full")
        assert "speaker" not in _entrada(payload, MAC1)
        assert "speaker" not in (_entrada(payload, MAC1).get("inputs") or {})

    @pytest.mark.asyncio
    async def test_release_chega_ao_metodo_do_servico(self, daemon_vivo: Any) -> None:
        env = daemon_vivo
        await _chamar(env.socket, "speaker.set", {"release": True, "uniq": MAC2})
        assert env.fc.pedidos == [("release", None, None, MAC2)]

    @pytest.mark.asyncio
    async def test_muted_false_depois_do_release_e_recusado_com_o_caminho(
        self, daemon_vivo: Any
    ) -> None:
        """MORDIDA da guarda no handler: sem ela não há recusa, só um status.

        A recusa precisa dizer o CAMINHO ("mande um volume antes"); um
        `sem_controle` mentiria sobre um controle que está conectado, e um "ok"
        silencioso esconderia que nada foi feito.
        """
        env = daemon_vivo
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})
        await _chamar(env.socket, "speaker.set", {"release": True, "uniq": MAC1})
        env.fc.pedidos.clear()

        with pytest.raises(RuntimeError, match="sem volume conhecido"):
            await _chamar(env.socket, "speaker.set", {"muted": False, "uniq": MAC1})

        assert env.fc.pedidos == []
        payload = await _chamar(env.socket, "daemon.state_full")
        assert "speaker" not in _entrada(payload, MAC1)

    @pytest.mark.asyncio
    async def test_mudo_antes_de_qualquer_volume_e_recusado(
        self, daemon_vivo: Any
    ) -> None:
        env = daemon_vivo
        with pytest.raises(RuntimeError, match="sem volume conhecido"):
            await _chamar(env.socket, "speaker.set", {"muted": True, "uniq": MAC1})
        assert env.fc.pedidos == []

    @pytest.mark.asyncio
    async def test_release_com_volume_e_erro_de_validacao(
        self, daemon_vivo: Any
    ) -> None:
        """A precedência decidida na sprint: a mistura NÃO tem vencedor."""
        env = daemon_vivo
        with pytest.raises(RuntimeError, match="não combina"):
            await _chamar(
                env.socket, "speaker.set", {"release": True, "volume": 100}
            )
        with pytest.raises(RuntimeError, match="não combina"):
            await _chamar(
                env.socket, "speaker.set", {"release": True, "muted": True}
            )
        assert env.fc.pedidos == []

    @pytest.mark.asyncio
    async def test_release_false_nao_devolve_nada(self, daemon_vivo: Any) -> None:
        """`release: false` é ausência, e ausência combina com volume."""
        env = daemon_vivo
        res = await _chamar(
            env.socket, "speaker.set", {"release": False, "volume": 90, "uniq": MAC1}
        )
        assert res["status"] == "ok"
        assert res["speaker"] == {"volume": 90, "muted": False}
        assert env.fc.pedidos == [("set", 90, None, MAC1)]

    @pytest.mark.asyncio
    async def test_release_de_tipo_errado_e_recusado(self, daemon_vivo: Any) -> None:
        env = daemon_vivo
        with pytest.raises(RuntimeError, match="'release' precisa ser boolean"):
            await _chamar(env.socket, "speaker.set", {"release": "sim"})
        assert env.fc.pedidos == []

    @pytest.mark.asyncio
    async def test_backend_sem_o_metodo_recusa_com_motivo(
        self, daemon_vivo: Any
    ) -> None:
        """Backend antigo/dublê: a ausência do método é dita, não engolida."""
        env = daemon_vivo
        env.fc.release_speaker_volume = None  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="backend sem suporte a devolução"):
            await _chamar(env.socket, "speaker.set", {"release": True})

    @pytest.mark.asyncio
    async def test_sem_controle_responde_sem_controle(self, daemon_vivo: Any) -> None:
        env = daemon_vivo
        env.fc.aceita = False
        res = await _chamar(env.socket, "speaker.set", {"release": True})
        assert res["status"] == "sem_controle"


class TestTravaManualAudio:
    """A quarta categoria — o autoswitch não pisa o ajuste manual dela."""

    def test_audio_e_categoria_valida(self) -> None:
        assert "audio" in MANUAL_OVERRIDE_CATEGORIES
        store = StateStore()
        store.mark_manual_trigger_active("audio")
        assert store.manual_override_categories == frozenset({"audio"})
        assert store.manual_trigger_active is True

    def test_categoria_desconhecida_continua_erro(self) -> None:
        """A porta não virou peneira: só as quatro categorias entram."""
        store = StateStore()
        with pytest.raises(ValueError):
            store.mark_manual_trigger_active("mouse")

    @pytest.mark.asyncio
    async def test_speaker_set_arma_a_categoria(self, daemon_vivo: Any) -> None:
        """MORDIDA: sem o `mark_manual_trigger_active("audio")` no handler, o
        autoswitch reaplica o perfil na próxima troca de janela por cima do
        volume que ela acabou de ajustar."""
        env = daemon_vivo
        assert env.store.manual_override_categories == frozenset()
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})
        assert env.store.manual_override_categories == frozenset({"audio"})

    @pytest.mark.asyncio
    async def test_release_tambem_arma(self, daemon_vivo: Any) -> None:
        """Parar de mandar é decisão dela tanto quanto mandar."""
        env = daemon_vivo
        await _chamar(env.socket, "speaker.set", {"release": True, "uniq": MAC1})
        assert env.store.manual_override_categories == frozenset({"audio"})

    @pytest.mark.asyncio
    async def test_pedido_recusado_nao_arma(self, daemon_vivo: Any) -> None:
        """Trava sem ajuste manual por baixo seria trava por engano."""
        env = daemon_vivo
        env.fc.aceita = False
        await _chamar(env.socket, "speaker.set", {"volume": 10})
        assert env.store.manual_override_categories == frozenset()

    @pytest.mark.asyncio
    async def test_troca_explicita_de_perfil_libera(self, daemon_vivo: Any) -> None:
        """A limpeza de sempre continua valendo para a categoria nova."""
        env = daemon_vivo
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})
        env.store.clear_manual_trigger_active()
        assert env.store.manual_override_categories == frozenset()


# ---------------------------------------------------------------------------
# A ponte da janela
# ---------------------------------------------------------------------------


class TestPonteDaJanela:
    """`app/ipc_bridge.py` — a assinatura acordada com a frente da interface."""

    def test_release_manda_a_chave_e_o_uniq(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        vistos: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            ipc_bridge,
            "_safe_call",
            lambda metodo, params: (vistos.append((metodo, params)), (True, {"status": "ok"}))[1],
        )
        assert ipc_bridge.speaker_set(uniq=MAC1, release=True) is True
        assert vistos == [("speaker.set", {"release": True, "uniq": MAC1})]

    def test_volume_continua_indo_explicito(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Armadilha 1: a ponte nunca pode mandar payload vazio."""
        from hefesto_dualsense4unix.app import ipc_bridge

        vistos: list[dict[str, Any]] = []
        monkeypatch.setattr(
            ipc_bridge,
            "_safe_call",
            lambda metodo, params: (vistos.append(params), (True, {"status": "ok"}))[1],
        )
        ipc_bridge.speaker_set(volume=180, muted=False, uniq=MAC2)
        assert vistos == [{"volume": 180, "muted": False, "uniq": MAC2}]

    def test_release_com_volume_e_erro_de_programacao(self) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        with pytest.raises(ValueError, match="não combina"):
            ipc_bridge.speaker_set(volume=100, release=True)


# ---------------------------------------------------------------------------
# A linha de comando — a saída de emergência sem janela
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_no_socket(
    daemon_vivo: Any, monkeypatch: pytest.MonkeyPatch
) -> Any:
    """Aponta o CLI para o socket do daemon de teste e espiona o despacho.

    O espião é o que dá mordida à guarda do CLI: com ela arrancada o daemon
    também recusaria (e o código de saída seria o mesmo), então o que prova a
    guarda é NENHUM pedido ter chegado ao fio.
    """
    env = daemon_vivo
    monkeypatch.setattr(
        "hefesto_dualsense4unix.cli.ipc_client.ipc_socket_path",
        lambda: env.socket,
    )
    env.chamadas = []
    original = env.server._handlers["speaker.set"]

    async def _espiao(params: dict[str, Any]) -> Any:
        env.chamadas.append(params)
        return await original(params)

    env.server._handlers["speaker.set"] = _espiao
    return env


class TestCliSpeaker:
    @pytest.mark.asyncio
    async def test_release_chega_ao_daemon_e_solta_a_posse(
        self, cli_no_socket: Any
    ) -> None:
        from hefesto_dualsense4unix.cli import cmd_speaker

        env = cli_no_socket
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})

        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "release", None, MAC1)
        assert exc.value.exit_code == 0
        assert env.fc.pedidos[-1] == ("release", None, None, MAC1)

        payload = await _chamar(env.socket, "daemon.state_full")
        assert "speaker" not in _entrada(payload, MAC1)

    @pytest.mark.asyncio
    async def test_volume_em_porcentagem_vira_0_255(self, cli_no_socket: Any) -> None:
        """60 % da linha de comando vira o MESMO cru que 60 % da janela.

        REAPONTADO em 01/08/2026, e o motivo é a razão de o teste existir. A
        versão anterior travava o número 153, que é `60 * 255 / 100` — a régua
        LINEAR. A medição do mesmo dia (microfone do próprio controle, tom de
        1 kHz, Goertzel) mostrou que o registrador satura por volta de 102 e é
        mudo até 38: pela régua linear, 60 % e 100 % caíam os dois na planície
        de cima e soavam IGUAIS, e os primeiros 15 % do curso não faziam som
        nenhum.

        O teste não some, porque o defeito que ele protege continua de pé: a
        linha de comando e a janela têm de mandar o MESMO valor para o mesmo
        registrador. O que muda é de onde vem o número esperado — deixa de ser
        uma constante copiada e passa a ser derivado da régua única, de modo
        que reaferir as bordas no futuro não exija reescrever este arquivo.

        A régua vive em `core/speaker_scale.py`, e a trava de que os dois
        caminhos a compartilham está em
        `tests/unit/test_speaker_regua_unica_cli_e_janela.py`.
        """
        from hefesto_dualsense4unix.cli import cmd_speaker
        from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

        esperado = volume_do_percentual(60)
        assert esperado < 153, (
            "a régua voltou a ser linear: 60 % mandaria 153, que está acima da "
            "saturação medida e soaria igual a 100 %"
        )

        env = cli_no_socket
        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "volume", 60, MAC1)
        assert exc.value.exit_code == 0
        assert env.fc.pedidos == [("set", esperado, None, MAC1)]

    @pytest.mark.asyncio
    async def test_volume_fora_da_faixa_nem_sai_do_terminal(
        self, cli_no_socket: Any
    ) -> None:
        from hefesto_dualsense4unix.cli import cmd_speaker

        env = cli_no_socket
        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "volume", 140, None)
        assert exc.value.exit_code == 2
        assert env.chamadas == []

    @pytest.mark.asyncio
    async def test_mute_sem_volume_conhecido_e_recusado_sem_ir_ao_fio(
        self, cli_no_socket: Any
    ) -> None:
        """MORDIDA da guarda do CLI (a mesma da interface, armadilha 2).

        Arrancando a consulta ao estado, o `speaker mute` vira a PRIMEIRA
        escrita: o pedido sai no fio e o teste reprova em `chamadas == []` —
        e no produto o alto-falante ficaria trancado em zero.
        """
        from hefesto_dualsense4unix.cli import cmd_speaker

        env = cli_no_socket
        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "mute", None, MAC1)
        assert exc.value.exit_code == 1
        assert env.chamadas == []
        assert env.fc.pedidos == []

    @pytest.mark.asyncio
    async def test_mute_com_volume_conhecido_passa(self, cli_no_socket: Any) -> None:
        from hefesto_dualsense4unix.cli import cmd_speaker

        env = cli_no_socket
        await _chamar(env.socket, "speaker.set", {"volume": 180, "uniq": MAC1})
        env.fc.pedidos.clear()

        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "mute", None, MAC1)
        assert exc.value.exit_code == 0
        assert env.fc.pedidos == [("set", None, True, MAC1)]
        assert env.fc.real.speaker_state_for(MAC1) == {"volume": 180, "muted": True}

    @pytest.mark.asyncio
    async def test_status_nao_escreve_nada(self, cli_no_socket: Any) -> None:
        """`status` é leitura: nenhum `speaker.set` pode sair dele."""
        from hefesto_dualsense4unix.cli import cmd_speaker

        env = cli_no_socket
        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_speaker.speaker_cmd, "status", None, None)
        assert exc.value.exit_code == 0
        assert env.chamadas == []

    def test_acao_invalida_sai_com_2(self) -> None:
        from hefesto_dualsense4unix.cli import cmd_speaker

        with pytest.raises(typer.Exit) as exc:
            cmd_speaker.speaker_cmd("desligar")
        assert exc.value.exit_code == 2

    def test_daemon_offline_sai_com_erro(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem daemon não há como mexer no volume — dizer isso é a resposta."""
        from hefesto_dualsense4unix.cli import cmd_speaker

        monkeypatch.setattr(
            "hefesto_dualsense4unix.cli.ipc_client.ipc_socket_path",
            lambda: tmp_path / "nao-existe.sock",
        )
        with pytest.raises(typer.Exit) as exc:
            cmd_speaker.speaker_cmd("release")
        assert exc.value.exit_code == 1

    def test_o_comando_esta_registrado_no_cli(self) -> None:
        """O verbo tem de existir no app Typer — sem isso nada acima é alcançável."""
        from hefesto_dualsense4unix.cli.app import app

        nomes = {
            info.name or (info.callback.__name__ if info.callback else "")
            for info in app.registered_commands
        }
        assert "speaker" in nomes


# ---------------------------------------------------------------------------
# O documento de protocolo — a correção medida da posse por byte
# ---------------------------------------------------------------------------


class TestDocumentoDoProtocolo:
    """Contrato de texto (padrão do repo): o que a sprint mediu tem de estar lá."""

    def _texto(self) -> str:
        """O documento com o espaçamento NORMALIZADO.

        As frases do markdown quebram em 80 colunas; procurar a frase crua
        pegaria a quebra de linha e reprovaria por formatação, não por conteúdo.
        """
        raiz = Path(__file__).resolve().parents[2]
        bruto = (raiz / "docs" / "protocol" / "ipc-unix-socket.md").read_text(
            encoding="utf-8"
        )
        return " ".join(bruto.split())

    def test_a_tabela_por_byte_e_por_bit_esta_publicada(self) -> None:
        texto = self._texto()
        for linha in ("common[4]", "common[5]", "common[6]", "common[7]", "common[9]"):
            assert linha in texto
        for bit in ("flag0 0x10", "flag0 0x20", "flag0 0x40", "flag0 0x80", "flag1 0x02"):
            assert bit in texto

    def test_a_consequencia_do_botao_de_microfone_esta_escrita(self) -> None:
        texto = self._texto()
        assert "NÃO mata o botão de microfone do controle" in texto

    def test_o_release_esta_documentado_sem_promessa_de_restauracao(self) -> None:
        texto = self._texto()
        assert "release: true" in texto
        assert "devolve o CONTROLE, não o valor" in texto
