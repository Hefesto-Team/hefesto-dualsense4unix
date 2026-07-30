"""MIC-USB-01 — as três camadas de mudo empilhadas, e a cura de cada uma.

Medido ao vivo em 25/07 com o controle no cabo: o microfone estava mudo por três
motivos DIFERENTES, em três donos diferentes, e cada cura revelava o de baixo. A
aba Status dizia a verdade o tempo todo — o medidor era a única coisa
funcionando. O que faltava era a cura.

  camada 1  `"mute":true` persistido por ROTA de placa no estado do WirePlumber;
  camada 2  perfil da placa preso em `input:iec958-stereo` (S/PDIF, SEM SINAL);
  camada 3  o mudo no FIRMWARE do controle — o mesmo que o botão físico alterna.

Cobertura, toda pelo caminho PÚBLICO:

- `mic.set` exercitado por um `IpcServer` de verdade, falado por `IpcClient` —
  nunca chamando `_handle_mic_set` na mão. Um teste que entra pelo método
  privado passa com o roteamento arrancado do `ipc_server`, e foi exatamente
  esse buraco que deixou `set_microphone_mute` existir por dias sem estar
  exposto em superfície nenhuma;
- os TRÊS estados (`true`/`false`/`null`) e a obrigatoriedade da chave `muted`,
  que é o cadeado contra o defeito dos dois escritores (`3d9bb7e`);
- `daemon.state_full` publicando `audio.mic_mudo_desejado` (quem MANDA), ao lado
  do `audio.mic_mudo` (o que o firmware DECLARA);
- o backend (`PyDualSenseController`) roteando por `uniq` e distinguindo
  `False` de `None` no handle;
- o CLI `mic mute|unmute|release` ligado ao daemon de verdade por um socket de
  teste — a prova de que o método novo tem chamador vivo;
- as funções de parsing do `doctor.sh` para as camadas 1 e 2, com amostras
  copiadas da saída REAL desta máquina, e a fiação delas no `main`.

MACs fake (regra da casa).
"""
# ruff: noqa: E501 — as amostras de `pactl` e do `default-routes` são cópias
# FIÉIS da saída desta máquina, e o nome do card do DualSense sozinho já passa
# de 100 colunas. Quebrar as linhas para caber inventaria uma entrada que o
# parser jamais receberia, e é justamente o parser que está sendo testado.
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

MAC1 = "aabbcc000001"
MAC2 = "aabbcc000002"


# ---------------------------------------------------------------------------
# Cenário: daemon de verdade num socket de teste
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: target)
    return target


class _ControllerComAudio(FakeController):
    """FakeController que sabe responder `mic.set` — dublê do backend real.

    Guarda os pedidos como o backend guarda: o VALOR e o `uniq`. Isso permite
    provar que `False` e `None` chegam DIFERENTES do outro lado do fio, que é a
    distinção que o projeto pagou caro para aprender.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pedidos_mic: list[tuple[bool | None, str | None]] = []
        self.posse: dict[str | None, bool | None] = {}
        self.mic_mudo_lido = True
        self.aceita = True

    def set_microphone_mute(
        self, muted: bool | None, *, uniq: str | None = None
    ) -> bool:
        self.pedidos_mic.append((muted, uniq))
        if not self.aceita:
            return False
        self.posse[uniq] = muted
        return True

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        return self.posse.get(uniq)

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        return {
            "fone_plugado": False,
            "mic_externo": False,
            "mic_mudo": self.mic_mudo_lido,
        }


@pytest.fixture
async def daemon_vivo(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    """`IpcServer` real ouvindo num socket de teste, com dois controles."""
    fc = _ControllerComAudio(transport="usb")
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
        yield socket_path, fc
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


# ---------------------------------------------------------------------------
# Camada 3 — `mic.set` no IPC
# ---------------------------------------------------------------------------


class TestMicSetNoProtocolo:
    """Entra pelo fio: se o método não estiver ROTEADO, a chamada nem existe."""

    @pytest.mark.asyncio
    async def test_o_metodo_existe_no_despacho(self, daemon_vivo: Any) -> None:
        """Regressão da própria sprint: `mic.set` não existia entre os 31
        métodos do IPC, embora o backend tivesse `set_microphone_mute`."""
        socket_path, _fc = daemon_vivo
        res = await _chamar(socket_path, "mic.set", {"muted": False})
        assert res["status"] == "ok"

    @pytest.mark.asyncio
    async def test_true_muta(self, daemon_vivo: Any) -> None:
        socket_path, fc = daemon_vivo
        await _chamar(socket_path, "mic.set", {"muted": True})
        assert fc.pedidos_mic == [(True, None)]

    @pytest.mark.asyncio
    async def test_false_desmuta_e_nao_e_none(self, daemon_vivo: Any) -> None:
        """O CADEADO da sprint: `False` viaja como `False`, nunca virando `None`.

        Foi confundir os dois que fez o keepalive do upstream mandar
        `common[9]=0x00` a 60 Hz por cima do kernel (`3d9bb7e`) — "desmuta"
        escrito onde se queria "não mexe".
        """
        socket_path, fc = daemon_vivo
        await _chamar(socket_path, "mic.set", {"muted": False})
        assert fc.pedidos_mic == [(False, None)]
        assert fc.pedidos_mic[0][0] is False

    @pytest.mark.asyncio
    async def test_null_devolve_a_posse_ao_kernel(self, daemon_vivo: Any) -> None:
        socket_path, fc = daemon_vivo
        await _chamar(socket_path, "mic.set", {"muted": None})
        assert fc.pedidos_mic == [(None, None)]
        assert fc.pedidos_mic[0][0] is None

    @pytest.mark.asyncio
    async def test_muted_ausente_e_recusado(self, daemon_vivo: Any) -> None:
        """Omitir a chave NÃO pode virar um `False` silencioso: `False` é ordem."""
        socket_path, fc = daemon_vivo
        with pytest.raises(RuntimeError, match="obrigatório"):
            await _chamar(socket_path, "mic.set", {"uniq": MAC1})
        assert fc.pedidos_mic == []

    @pytest.mark.asyncio
    async def test_muted_de_tipo_errado_e_recusado(self, daemon_vivo: Any) -> None:
        socket_path, fc = daemon_vivo
        with pytest.raises(RuntimeError, match="boolean ou null"):
            await _chamar(socket_path, "mic.set", {"muted": "sim"})
        assert fc.pedidos_mic == []

    @pytest.mark.asyncio
    async def test_uniq_roteia_para_um_controle_so(self, daemon_vivo: Any) -> None:
        """Mesmo eixo de `led.set`/`rumble.set`: o MAC escolhe o controle."""
        socket_path, fc = daemon_vivo
        await _chamar(socket_path, "mic.set", {"muted": True, "uniq": MAC2})
        assert fc.pedidos_mic == [(True, MAC2)]

    @pytest.mark.asyncio
    async def test_uniq_de_tipo_errado_e_recusado(self, daemon_vivo: Any) -> None:
        socket_path, fc = daemon_vivo
        with pytest.raises(RuntimeError, match="uniq"):
            await _chamar(socket_path, "mic.set", {"muted": True, "uniq": 7})
        assert fc.pedidos_mic == []

    @pytest.mark.asyncio
    async def test_sem_controle_responde_sem_controle(self, daemon_vivo: Any) -> None:
        """Ordem que cai no vazio tem de se declarar — não pode virar "ok"."""
        socket_path, fc = daemon_vivo
        fc.aceita = False
        res = await _chamar(socket_path, "mic.set", {"muted": False})
        assert res["status"] == "sem_controle"

    @pytest.mark.asyncio
    async def test_resposta_traz_a_leitura_do_firmware(self, daemon_vivo: Any) -> None:
        """`audio` é LEITURA (pode vir um report atrás), não eco da escrita."""
        socket_path, fc = daemon_vivo
        fc.mic_mudo_lido = True
        res = await _chamar(socket_path, "mic.set", {"muted": False})
        assert res["audio"]["mic_mudo"] is True
        assert res["mic_mudo_desejado"] is False

    @pytest.mark.asyncio
    async def test_backend_sem_o_metodo_recusa_com_motivo(
        self, daemon_vivo: Any
    ) -> None:
        socket_path, fc = daemon_vivo
        fc.set_microphone_mute = None  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="backend sem suporte"):
            await _chamar(socket_path, "mic.set", {"muted": True})


class TestPosseNoStateFull:
    """`audio.mic_mudo_desejado` — QUEM manda, ao lado do que está valendo."""

    @pytest.mark.asyncio
    async def test_sem_posse_a_chave_e_nula(self, daemon_vivo: Any) -> None:
        """Nada foi pedido ainda: o dono é o `hid-playstation` (botão físico)."""
        socket_path, _fc = daemon_vivo
        payload = await _chamar(socket_path, "daemon.state_full")
        assert _entrada(payload, MAC1)["audio"]["mic_mudo_desejado"] is None

    @pytest.mark.asyncio
    async def test_depois_do_mic_set_a_posse_aparece(self, daemon_vivo: Any) -> None:
        socket_path, _fc = daemon_vivo
        await _chamar(socket_path, "mic.set", {"muted": True, "uniq": MAC1})
        payload = await _chamar(socket_path, "daemon.state_full")
        assert _entrada(payload, MAC1)["audio"]["mic_mudo_desejado"] is True

    @pytest.mark.asyncio
    async def test_a_leitura_do_firmware_continua_ao_lado(
        self, daemon_vivo: Any
    ) -> None:
        """Posse e leitura são perguntas diferentes e viajam juntas: a tela só
        escolhe entre "aperte o botão" e "desmute pela janela" tendo as duas."""
        socket_path, fc = daemon_vivo
        fc.mic_mudo_lido = True
        await _chamar(socket_path, "mic.set", {"muted": False, "uniq": MAC1})
        payload = await _chamar(socket_path, "daemon.state_full")
        audio = _entrada(payload, MAC1)["audio"]
        assert audio["mic_mudo"] is True
        assert audio["mic_mudo_desejado"] is False

    @pytest.mark.asyncio
    async def test_backend_sem_o_metodo_nao_inventa_a_chave(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """Dublê/daemon antigo sem `microphone_mute_for`: ausência é resposta."""
        fc = FakeController(transport="usb")
        fc.connect()
        fc.audio_status_for = lambda uniq=None: {  # type: ignore[attr-defined]
            "fone_plugado": False, "mic_externo": False, "mic_mudo": False
        }
        fc.describe_controllers = lambda: [  # type: ignore[method-assign]
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "uniq": MAC1},
        ]
        store = StateStore()
        manager = ProfileManager(controller=fc, store=store)
        save_profile(Profile(name="fallback", match=MatchAny(), priority=0))
        socket_path = tmp_path / "sem-posse.sock"
        server = IpcServer(
            controller=fc, store=store, profile_manager=manager,
            socket_path=socket_path, daemon=None,
        )
        await server.start()
        try:
            payload = await _chamar(socket_path, "daemon.state_full")
        finally:
            await server.stop()
        assert "mic_mudo_desejado" not in _entrada(payload, MAC1)["audio"]


# ---------------------------------------------------------------------------
# Camada 3 — o backend por baixo do IPC
# ---------------------------------------------------------------------------


class _HandleFake:
    """Handle mínimo: guarda o que `set_microphone_mute` escreveu."""

    def __init__(self) -> None:
        self._mic_mute_desejado: bool | None = None
        self.connected = True
        self.conType = SimpleNamespace(name="USB")

    def set_microphone_mute(self, muted: bool | None) -> None:
        self._mic_mute_desejado = None if muted is None else bool(muted)


def _backend_com_dois() -> tuple[Any, _HandleFake, _HandleFake]:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    h1, h2 = _HandleFake(), _HandleFake()
    inst._handles = {"AA:BB:CC:00:00:01": h1, "AA:BB:CC:00:00:02": h2}  # type: ignore[dict-item]
    inst._primary_key = "AA:BB:CC:00:00:01"
    return inst, h1, h2


class TestBackendMicMute:
    def test_escreve_so_no_controle_do_uniq(self) -> None:
        inst, h1, h2 = _backend_com_dois()
        assert inst.set_microphone_mute(True, uniq=MAC2) is True
        assert h1._mic_mute_desejado is None
        assert h2._mic_mute_desejado is True

    def test_sem_uniq_vai_no_primario(self) -> None:
        inst, h1, h2 = _backend_com_dois()
        inst.set_microphone_mute(False)
        assert h1._mic_mute_desejado is False
        assert h2._mic_mute_desejado is None

    def test_false_e_none_sao_estados_diferentes_no_handle(self) -> None:
        """`False` MANDA "desmuta"; `None` DEVOLVE a posse. Não são sinônimos."""
        inst, h1, _h2 = _backend_com_dois()
        inst.set_microphone_mute(False)
        assert h1._mic_mute_desejado is False
        inst.set_microphone_mute(None)
        assert h1._mic_mute_desejado is None

    def test_sem_handle_devolve_false(self) -> None:
        """MIC-USB-01: o retorno booleano é o que deixa o `mic.set` responder
        "sem_controle" em vez de mentir "ok" para uma ordem que caiu no vazio."""
        inst, _h1, _h2 = _backend_com_dois()
        assert inst.set_microphone_mute(True, uniq="aabbcc0000ff") is False

    def test_handle_que_estoura_nao_vira_sucesso(self) -> None:
        """O outro lado do mesmo contrato, e o que a versão anterior escondia:
        antes o método engolia a exceção num `suppress` e não devolvia NADA, de
        modo que um controle que sumiu no meio da escrita (replug, USB caindo)
        respondia "ok" na janela. Handle presente + escrita falhada = False."""
        inst, h1, _h2 = _backend_com_dois()

        def _explode(_muted: bool | None) -> None:
            raise OSError("controle sumiu no meio da escrita")

        h1.set_microphone_mute = _explode  # type: ignore[method-assign]
        assert inst.set_microphone_mute(True) is False
        assert inst.microphone_mute_for(MAC1) is None

    def test_posse_e_lida_de_volta(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        assert inst.microphone_mute_for(MAC1) is None
        inst.set_microphone_mute(True, uniq=MAC1)
        assert inst.microphone_mute_for(MAC1) is True
        inst.set_microphone_mute(False, uniq=MAC1)
        assert inst.microphone_mute_for(MAC1) is False
        inst.set_microphone_mute(None, uniq=MAC1)
        assert inst.microphone_mute_for(MAC1) is None

    def test_posse_de_controle_inexistente_e_none(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        assert inst.microphone_mute_for("aabbcc0000ff") is None


# ---------------------------------------------------------------------------
# Camada 3 — o CLI, chamador vivo do método novo
# ---------------------------------------------------------------------------


class TestCliMicFirmware:
    """`mic mute|unmute|release` falando com um daemon de VERDADE.

    A prova de que o `mic.set` tem chamador: monkeypatchar o `_mic_firmware`
    provaria só que o teste sabe chamar a si mesmo.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("verbo", "esperado"),
        [("mute", True), ("unmute", False), ("release", None)],
    )
    async def test_acao_chega_ao_daemon(
        self,
        daemon_vivo: Any,
        monkeypatch: pytest.MonkeyPatch,
        verbo: str,
        esperado: bool | None,
    ) -> None:
        import typer

        from hefesto_dualsense4unix.cli import cmd_mic

        socket_path, fc = daemon_vivo
        # O CLI resolve o socket por `ipc_socket_path()`; apontamos os dois para
        # o mesmo arquivo em vez de dublar o cliente.
        monkeypatch.setattr(
            "hefesto_dualsense4unix.cli.ipc_client.ipc_socket_path",
            lambda: socket_path,
        )
        # O CLI é síncrono e usa `asyncio.run` — roda numa thread para não
        # colidir com o laço de eventos deste teste.
        import asyncio

        with pytest.raises(typer.Exit) as exc:
            await asyncio.to_thread(cmd_mic.mic_cmd, verbo)
        assert exc.value.exit_code == 0
        assert fc.pedidos_mic == [(esperado, None)]

    @pytest.mark.asyncio
    async def test_uniq_do_cli_roteia(
        self, daemon_vivo: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import typer

        from hefesto_dualsense4unix.cli import cmd_mic

        socket_path, fc = daemon_vivo
        monkeypatch.setattr(
            "hefesto_dualsense4unix.cli.ipc_client.ipc_socket_path",
            lambda: socket_path,
        )
        import asyncio

        with pytest.raises(typer.Exit):
            await asyncio.to_thread(cmd_mic.mic_cmd, "mute", MAC2)
        assert fc.pedidos_mic == [(True, MAC2)]

    def test_daemon_offline_sai_com_erro(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem daemon não há como mexer no firmware — dizer isso é a resposta."""
        import typer

        from hefesto_dualsense4unix.cli import cmd_mic

        monkeypatch.setattr(
            "hefesto_dualsense4unix.cli.ipc_client.ipc_socket_path",
            lambda: tmp_path / "nao-existe.sock",
        )
        with pytest.raises(typer.Exit) as exc:
            cmd_mic.mic_cmd("unmute")
        assert exc.value.exit_code == 1

    def test_promote_e_demote_mapeiam_para_o_script(self) -> None:
        """Entrega 3: rebaixar por default só é política se houver a subida."""
        from hefesto_dualsense4unix.cli import cmd_mic

        assert cmd_mic._ACTION_FLAG["promote"] == "--promote-source"
        assert cmd_mic._ACTION_FLAG["demote"] == "--install"


# ---------------------------------------------------------------------------
# Camadas 1 e 2 — o doctor.sh
# ---------------------------------------------------------------------------


def _rodar_doctor(func: str, *args: str, entrada: str | None = None) -> str:
    """Executa uma função shell REAL do doctor (source, sem rodar o main)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        input=entrada,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": "/nao-existe"},
    )
    assert res.returncode == 0, res.stderr
    # `strip("\n")` e não `strip()`: o campo vazio de `_dualsense_perfil_status`
    # ("nada a trocar") é um TAB final, e comê-lo esconderia a resposta.
    return res.stdout.strip("\n")


#: Cópia fiel de `~/.local/state/wireplumber/default-routes` desta máquina, com
#: o DualSense MUDO (o estado do relato) e o restante intacto.
_ROTAS_MUDAS = """\
[default-routes]
alsa_card.pci-0000_0a_00.1:output:hdmi-output-0={"channelMap":["FL", "FR"], "mute":false}
alsa_card.pci-0000_0c_00.4:output:iec958-stereo-output={"channelMap":["FL"], "mute":true}
alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00:input:iec958-stereo-input={"channelVolumes":[1.000000, 1.000000], "mute":true}
alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00:output:analog-output={"channelVolumes":[0.063997], "mute":false}
"""

_ROTAS_SAS = _ROTAS_MUDAS.replace(
    'Controller-00:input:iec958-stereo-input={"channelVolumes":[1.000000, 1.000000], "mute":true}',
    'Controller-00:input:iec958-stereo-input={"channelVolumes":[1.000000, 1.000000], "mute":false}',
)


class TestCamada1RotasMudas:
    def test_acha_a_rota_muda_do_dualsense(self, tmp_path: Path) -> None:
        arq = tmp_path / "default-routes"
        arq.write_text(_ROTAS_MUDAS, encoding="utf-8")
        saida = _rodar_doctor("_dualsense_rotas_mudas", str(arq))
        assert saida.splitlines() == [
            "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
            "Controller-00:input:iec958-stereo-input"
        ]

    def test_mute_de_outro_device_nao_e_do_dualsense(self, tmp_path: Path) -> None:
        """O `mute:true` da placa onboard é ESCOLHA da usuária — não é nosso."""
        arq = tmp_path / "default-routes"
        arq.write_text(_ROTAS_SAS, encoding="utf-8")
        assert _rodar_doctor("_dualsense_rotas_mudas", str(arq)) == ""

    def test_arquivo_ausente_e_silencio_sem_erro(self, tmp_path: Path) -> None:
        assert _rodar_doctor("_dualsense_rotas_mudas", str(tmp_path / "nada")) == ""


class TestVereditoDeMuteDaSource:
    def test_yes_e_mudo(self) -> None:
        assert _rodar_doctor("_source_mute_veredito", "Mute: yes") == "muted"

    def test_no_nao_e_mudo(self) -> None:
        assert _rodar_doctor("_source_mute_veredito", "Mute: no") == "unmuted"

    def test_traduzido_tambem_e_lido(self) -> None:
        """A saída do pactl é TRADUZIDA; o LC_ALL=C cobre, isto é o cinto."""
        assert _rodar_doctor("_source_mute_veredito", "Mute: sim") == "muted"
        assert _rodar_doctor("_source_mute_veredito", "Mute: não") == "unmuted"

    def test_vazio_e_desconhecido(self) -> None:
        assert _rodar_doctor("_source_mute_veredito", "") == "unknown"


_SOURCES_SHORT = """\
190\talsa_output.pci-0000_0c_00.4.iec958-stereo.monitor\tPipeWire\ts32le 2ch\tSUSPENDED
191\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tSUSPENDED
812\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.analog-surround-40.monitor\tPipeWire\ts16le 4ch\tSUSPENDED
813\talsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.analog-stereo\tPipeWire\ts16le 2ch\tSUSPENDED
"""


class TestNomeDaSource:
    def test_acha_o_alsa_input_e_ignora_o_monitor(self) -> None:
        """O `.monitor` do sink casa "DualSense" mas é o loopback da SAÍDA:
        elegê-lo é gravar o som do sistema em vez da voz de quem fala."""
        saida = _rodar_doctor("_dualsense_source_nome", entrada=_SOURCES_SHORT)
        assert saida == (
            "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
            "Controller-00.analog-stereo"
        )

    def test_sem_dualsense_e_silencio(self) -> None:
        so_onboard = "\n".join(
            linha for linha in _SOURCES_SHORT.splitlines() if "Sony" not in linha
        )
        assert _rodar_doctor("_dualsense_source_nome", entrada=so_onboard + "\n") == ""


#: Recorte fiel de `LC_ALL=C pactl list cards` desta máquina, com o DualSense no
#: perfil S/PDIF — o estado medido no relato ("gravação de 4 segundos: pico 0").
_CARDS_SPDIF = """\
Card #52
\tName: alsa_card.pci-0000_0c_00.4
\tProfiles:
\t\toutput:analog-stereo+input:analog-stereo: Duplex (sinks: 1, sources: 1, priority: 6565, available: no)
\t\tinput:analog-stereo: Entrada (sinks: 0, sources: 1, priority: 65, available: no)
\tActive Profile: output:iec958-stereo+input:analog-stereo
\tPorts:
\t\tanalog-input-mic: Microfone (type: Mic, priority: 8700)
\t\t\tPart of profile(s): input:analog-stereo, output:analog-stereo+input:analog-stereo

Card #91
\tName: alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00
\tDriver: PipeWire
\tProfiles:
\t\toff: Off (sinks: 0, sources: 0, priority: 0, available: yes)
\t\toutput:analog-surround-40+input:analog-stereo: Surround 4.0 + Entrada (sinks: 1, sources: 1, priority: 1265, available: no)
\t\toutput:analog-surround-40+input:iec958-stereo: Surround 4.0 + IEC958 (sinks: 1, sources: 1, priority: 1255, available: yes)
\t\toutput:analog-surround-40: Surround 4.0 (sinks: 1, sources: 0, priority: 1200, available: yes)
\t\tinput:analog-stereo: Entrada (sinks: 0, sources: 1, priority: 65, available: no)
\t\tinput:iec958-stereo: Entrada digital (sinks: 0, sources: 1, priority: 55, available: yes)
\tActive Profile: output:analog-surround-40+input:iec958-stereo
\tPorts:
\t\tanalog-input-headset-mic: Microfone do headset (type: Headset, priority: 8700, availability group: Legacy 1, not available)
\t\t\tPart of profile(s): input:analog-stereo, output:analog-surround-40+input:analog-stereo
\t\tiec958-stereo-input: Entrada digital (S/PDIF) (type: SPDIF, priority: 0)
\t\t\tPart of profile(s): input:iec958-stereo, output:analog-surround-40+input:iec958-stereo
"""

_CARDS_CURADO = _CARDS_SPDIF.replace(
    "\tActive Profile: output:analog-surround-40+input:iec958-stereo",
    "\tActive Profile: output:analog-surround-40+input:analog-stereo",
)

_CARD_DS = (
    "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
)


class TestCamada2PerfilDaPlaca:
    """REESCRITOS em 26/07/2026 — a regra que eles travavam foi REFUTADA.

    Estes testes fixavam o comportamento original do `--fix-mic`: sempre que a
    entrada ativa fosse `iec958`, trocar para `input:analog-stereo`, e — no caso
    mais explicito — NAO filtrar por `available`. Um deles se chamava
    literalmente `test_o_alvo_nao_e_filtrado_por_available`, com o argumento de
    que filtrar "repetiria o erro do WirePlumber e deixaria o microfone embutido
    inalcancavel para sempre".

    Medido no hardware, com o controle no cabo: forcar o perfil analogico
    (marcado `available: no` pelo ALSA) produz uma source SEM PORTA DE CAPTURA e
    a gravacao sai com pico 0 — 327.680 bytes de silencio digital. No
    `iec958-stereo` a mesma gravacao deu pico 4606 e RMS 374. A regra que estes
    testes protegiam emudecia o microfone de quem rodasse a cura.

    Não foram apagados: cada um vira o seu contrario, com o porque ao lado. E o
    argumento antigo não era burrice — ele valia SE o analogico fosse alcancavel.
    A medicao mostrou que, quando o ALSA diz `available: no`, ele não é.
    """

    def test_nao_propoe_o_analogico_indisponivel(self) -> None:
        """Era `test_detecta_o_spdif_e_propoe_o_analogico`.

        O ativo (`iec958`) oferece fonte e esta disponivel: não há o que trocar.
        """
        saida = _rodar_doctor("_dualsense_perfil_status", entrada=_CARDS_SPDIF)
        card, ativo, alvo = saida.split("\t")
        assert card == _CARD_DS
        assert ativo == "output:analog-surround-40+input:iec958-stereo"
        assert alvo == "", (
            "o analogico esta `available: no` — propo-lo produz source sem "
            f"porta e silencio digital. Veio alvo={alvo!r}"
        )

    def test_quando_precisa_trocar_o_alvo_preserva_a_saida(self) -> None:
        """Este contrato CONTINUA valendo, e por que ele foi escrito.

        Trocar para um perfil so-de-entrada emudeceria o alto-falante e o fone
        do controle, e derrubaria o canal de haptic-de-audio junto. So que agora
        a troca so acontece quando o ativo NAO serve.
        """
        sem_fonte = _CARDS_SPDIF.replace(
            "\tActive Profile: output:analog-surround-40+input:iec958-stereo",
            "\tActive Profile: output:analog-surround-40",
        )
        saida = _rodar_doctor("_dualsense_perfil_status", entrada=sem_fonte)
        alvo = saida.split("\t")[2]
        assert alvo.startswith("output:"), (
            f"o alvo precisa manter uma saida; veio {alvo!r}"
        )

    def test_o_alvo_e_sim_filtrado_por_available(self) -> None:
        """O CONTRARIO exato do teste que existia aqui.

        O nome antigo era `test_o_alvo_nao_e_filtrado_por_available`. Filtrar
        por disponibilidade e justamente o que impede a cura de escolher um
        perfil que o ALSA sabe que não vai funcionar.
        """
        assert "priority: 1265, available: no" in _CARDS_SPDIF, (
            "a fixture precisa manter o analogico como indisponivel — e o caso"
        )
        sem_fonte = _CARDS_SPDIF.replace(
            "\tActive Profile: output:analog-surround-40+input:iec958-stereo",
            "\tActive Profile: output:analog-surround-40",
        )
        alvo = _rodar_doctor(
            "_dualsense_perfil_status", entrada=sem_fonte
        ).split("\t")[2]
        assert not alvo.endswith("input:analog-stereo"), (
            f"perfil `available: no` nunca pode ser alvo; veio {alvo!r}"
        )

    def test_o_estado_que_a_cura_antiga_deixava_e_desfeito(self) -> None:
        """Era `test_perfil_ja_analogico_nao_pede_troca`, e a inversao e o ponto.

        `_CARDS_CURADO` e a maquina DEPOIS da cura antiga: perfil analogico
        ativo. A fixture o descreve como `available: no` — e foi exatamente esse
        o estado medido no hardware, onde a source nasce sem porta e a gravacao
        sai com pico 0.

        O teste antigo chamava isso de "curado" e exigia que nada fosse feito.
        A regra nova reconhece o estado como ruim e propoe o perfil que o ALSA
        declara disponivel: a cura passa a DESFAZER o estrago que ela mesma
        causava antes.
        """
        saida = _rodar_doctor("_dualsense_perfil_status", entrada=_CARDS_CURADO)
        card, ativo, alvo = saida.split("\t")
        assert card == _CARD_DS
        assert ativo == "output:analog-surround-40+input:analog-stereo"
        assert alvo.endswith("input:iec958-stereo"), (
            "o ativo esta `available: no`; a cura tem de propor o disponivel "
            f"em vez de declarar vitoria. Veio alvo={alvo!r}"
        )

    def test_a_placa_onboard_nao_e_confundida(self) -> None:
        """A onboard também tem `iec958` no perfil ativo e NÃO é assunto nosso."""
        so_onboard = _CARDS_SPDIF.split("Card #91")[0]
        assert "iec958" in so_onboard
        assert _rodar_doctor("_dualsense_perfil_status", entrada=so_onboard) == ""

    def test_sem_dualsense_e_silencio(self) -> None:
        assert _rodar_doctor("_dualsense_perfil_status", entrada="") == ""


class TestFiacaoNoDoctor:
    """Contratos de texto — padrão do repo para a lógica do doctor.sh."""

    def _texto(self) -> str:
        return DOCTOR.read_text(encoding="utf-8")

    def test_os_dois_checks_sao_chamados_no_main(self) -> None:
        texto = self._texto()
        assert "\n    check_mic_mute_persistido\n" in texto
        assert "\n    check_mic_perfil_sem_sinal\n" in texto

    def test_o_fix_e_chamado_pelo_apply_fixes(self) -> None:
        texto = self._texto()
        inicio = texto.index("apply_fixes() {")
        assert "fix_mic_dualsense" in texto[inicio : texto.index("\n}", inicio)]

    def test_o_fix_usa_os_comandos_validados_ao_vivo(self) -> None:
        texto = self._texto()
        inicio = texto.index("fix_mic_dualsense() {")
        bloco = texto[inicio : texto.index("\n}\n", inicio)]
        assert "pactl set-card-profile" in bloco
        assert "pactl set-source-mute" in bloco
        assert "--unmute-routes" in bloco

    def test_os_checks_usam_as_funcoes_testadas_aqui(self) -> None:
        texto = self._texto()
        inicio = texto.index("check_mic_mute_persistido() {")
        bloco = texto[inicio : texto.index("check_mic_perfil_sem_sinal() {", inicio)]
        assert "_dualsense_rotas_mudas" in bloco
        assert "_dualsense_source_nome" in bloco
        assert "_source_mute_veredito" in bloco

    def test_deteccao_nao_escreve(self) -> None:
        """As funções de parsing são PURAS: nada de set-*, sed -i ou sudo.

        Comentários saem da conta — eles CITAM os comandos de cura de
        propósito, e proibir a citação empobreceria a explicação sem tornar o
        código mais seguro.
        """
        texto = self._texto()
        inicio = texto.index("_dualsense_rotas_mudas() {")
        regiao = "\n".join(
            linha
            for linha in texto[
                inicio : texto.index("check_mic_mute_persistido() {")
            ].splitlines()
            if not linha.lstrip().startswith("#")
        )
        for proibido in ("sed -i", "sudo", "pactl set-", "rm -f"):
            assert proibido not in regiao

    def test_nada_de_nome_de_card_hardcoded(self) -> None:
        """O nome carrega o produto e o sufixo da porta USB: muda por máquina."""
        texto = self._texto()
        assert "alsa_card.usb-Sony" not in texto

    def test_fix_mic_e_um_modo_proprio(self) -> None:
        texto = self._texto()
        assert "--fix-mic)" in texto
        assert "FIX_MIC=1" in texto


class TestPromocaoDaFonte:
    """Entrega 3 — o drop-in 51 rebaixa; agora existe o caminho de subir."""

    def _script(self) -> str:
        return (ROOT / "scripts" / "fix_wireplumber_default_source.sh").read_text(
            encoding="utf-8"
        )

    def test_os_modos_novos_estao_no_parser(self) -> None:
        texto = self._script()
        assert "--promote-source) MODE=" in texto
        assert "--unmute-routes)  MODE=" in texto

    def test_promocao_elege_a_fonte_do_dualsense(self) -> None:
        texto = self._script()
        inicio = texto.index("promote_source_dualsense() {")
        bloco = texto[inicio : texto.index("\n}\n", inicio)]
        assert "pick_dualsense_source_id" in bloco
        assert "wpctl set-default" in bloco
        # Promover uma fonte no S/PDIF seria promover silêncio.
        assert "--fix-mic" in bloco

    def test_promocao_ignora_o_monitor_do_sink(self) -> None:
        texto = self._script()
        inicio = texto.index("pick_dualsense_source_id() {")
        bloco = texto[inicio : texto.index("\n}\n", inicio)]
        assert "[Mm]onitor" in bloco

    def test_unmute_routes_nao_mexe_em_dropin(self) -> None:
        """Camada 1 isolada: a política escolhida pela usuária fica de pé."""
        texto = self._script()
        inicio = texto.index("    unmute-routes)")
        bloco = texto[inicio : texto.index("    promote)", inicio)]
        assert "install_dropin" not in bloco
        assert "enable_mic_dualsense" not in bloco
        assert "reset_default_source" not in bloco

    def test_o_dropin_51_documenta_que_nao_e_o_culpado(self) -> None:
        conf = (
            ROOT / "assets" / "wireplumber"
            / "51-hefesto-dualsense-no-default-source.conf"
        ).read_text(encoding="utf-8")
        assert "MIC-USB-01" in conf
        assert "--promote-source" in conf
        # A política em si NÃO mudou: rebaixar continua sendo o default.
        assert "priority.session = 50" in conf
