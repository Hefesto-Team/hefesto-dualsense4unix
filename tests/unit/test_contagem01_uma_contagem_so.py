"""CONTAGEM-01 — a janela não pode dizer dois números para a mesma pergunta.

Com quatro controles na mesa (dois DualSense, um Nintendo Pro, um 8BitDo) a
janela exibia TRÊS contagens ao mesmo tempo: a fita de chips dizia quatro (ela
buscava os externos por conta própria), o cabeçalho, a aba Status e o botão de
co-op diziam dois (contavam só os DualSense do bloco ``controllers``), e a aba
Emulação dizia oito (contava nós de ``/dev/input/js*``, incluindo os gamepads
virtuais que nós mesmos criamos).

Os testes entram pelo CAMINHO REAL — o ``state_full`` que o daemon publica
chegando à função que monta cada rótulo — porque o defeito nunca esteve dentro
de uma função e sim na FIAÇÃO: cada número estava certo para a pergunta que o
código dele fazia.

MACs fake (regra da casa).
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

MAC_DS1 = "aabbcc000001"
MAC_DS2 = "aabbcc000002"
ID_PRO = "aabbcc0000e1"
ID_8BITDO = "aabbcc0000e2"


# ---------------------------------------------------------------------------
# 1. O daemon publica os externos como LISTA (entrega 1)
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: target)
    return target


def _external_registry(numeros: dict[str, int | None]) -> MagicMock:
    """Registro de externos dublado: presença + número exibido, como o real."""
    registro = MagicMock()
    registro.snapshot_connected.return_value = set(numeros)
    registro.peek.side_effect = lambda key: numeros.get(key)
    return registro


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    fc.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"index": 0, "connected": True, "transport": "usb",
         "is_primary": True, "uniq": MAC_DS1, "player_slot": 1},
        {"index": 1, "connected": True, "transport": "bt",
         "is_primary": False, "uniq": MAC_DS2, "player_slot": 2},
    ]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock._bt_mic_subsystem = None
    daemon_mock._hotkey_manager = None
    daemon_mock.external_registry = _external_registry({ID_PRO: 3, ID_8BITDO: 4})
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
        yield server, socket_path, daemon_mock
    finally:
        await server.stop()


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        resultado = await client.call("daemon.state_full", None)
    assert isinstance(resultado, dict)
    return resultado


class TestExternosViramLista:
    """Entrega 1 — a fundação de que tudo o mais depende."""

    @pytest.mark.asyncio
    async def test_state_full_traz_endereco_e_numero_de_cada_externo(
        self, running_server: Any
    ) -> None:
        _server, socket_path, _daemon = running_server

        payload = await _state_full(socket_path)

        externos = payload["external_controllers"]
        assert [(e["identity"], e["player_slot"]) for e in externos] == [
            (ID_PRO, 3),
            (ID_8BITDO, 4),
        ]

    @pytest.mark.asyncio
    async def test_a_contagem_e_derivada_da_lista_e_nao_medida_de_novo(
        self, running_server: Any
    ) -> None:
        """Um número só: `coop.externals` é `len` da lista publicada.

        Enquanto a contagem tinha medição PRÓPRIA (um `len(snapshot)` que a
        lista não via), as duas podiam discordar — e discordar é o defeito
        que esta sprint conserta, não um detalhe de implementação.
        """
        _server, socket_path, _daemon = running_server

        payload = await _state_full(socket_path)

        assert payload["coop"]["externals"] == len(payload["external_controllers"])
        assert payload["coop"]["externals"] == 2

    @pytest.mark.asyncio
    async def test_sem_registro_de_externos_nenhuma_das_duas_chaves_aparece(
        self, running_server: Any
    ) -> None:
        """Não saber ≠ dizer "não há nenhum" — a chave some, não vira zero."""
        _server, socket_path, daemon = running_server
        daemon.external_registry = None

        payload = await _state_full(socket_path)

        assert "external_controllers" not in payload
        assert "externals" not in payload["coop"]

    @pytest.mark.asyncio
    async def test_externo_sem_numero_ainda_entra_na_lista_com_travessao(
        self, running_server: Any
    ) -> None:
        """Registro sem opinião ainda: null honesto > número errado (NUMA-05).

        E o controle NÃO some da mesa por causa disso — ele está ligado.
        """
        _server, socket_path, daemon = running_server
        daemon.external_registry = _external_registry({ID_PRO: None, ID_8BITDO: 4})

        payload = await _state_full(socket_path)

        externos = payload["external_controllers"]
        assert len(externos) == 2
        sem_numero = [e for e in externos if e["identity"] == ID_PRO]
        assert sem_numero and sem_numero[0]["player_slot"] is None
        # Sem número vai para o FIM: a lista não pode dançar entre ticks.
        assert externos[-1]["identity"] == ID_PRO

    @pytest.mark.asyncio
    async def test_a_descricao_do_cache_chega_ao_payload(
        self, running_server: Any
    ) -> None:
        """Nome/via saem do cache alimentado FORA do caminho quente."""
        server, socket_path, _daemon = running_server
        server._external_desc_cache = {
            ID_PRO: {"name": "Pro Controller", "vid": "057e", "pid": "2009",
                     "bus": "bluetooth", "uniq": "aa:bb:cc:00:00:e1",
                     "driver": "nintendo"},
        }

        payload = await _state_full(socket_path)

        pro = next(
            e for e in payload["external_controllers"] if e["identity"] == ID_PRO
        )
        assert pro["name"] == "Pro Controller"
        assert pro["bus"] == "bluetooth"
        assert pro["vid"] == "057e"

    @pytest.mark.asyncio
    async def test_o_state_full_nunca_enumera_dev_input_no_proprio_handler(
        self, running_server: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A enumeração custa 10-40 ms e o `state_full` roda a 10-20 Hz.

        O caminho quente pode AGENDAR a leitura, nunca esperá-la. O jeito de
        provar isso é fazer a enumeração DEMORAR: com ela pendurada por um
        segundo, a resposta ainda tem de chegar em milissegundos e já vir com
        os externos contados. Contar chamadas não serviria — a tarefa de
        fundo roda no mesmo laço enquanto a resposta viaja, então ela aparece
        "chamada" de qualquer jeito.
        """
        entrou = asyncio.Event()
        laco = asyncio.get_running_loop()

        def _lento(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            laco.call_soon_threadsafe(entrou.set)
            time.sleep(1.0)
            return []

        monkeypatch.setattr(ipc_handlers, "_external_inventory", _lento)
        _server, socket_path, _daemon = running_server

        comeco = time.monotonic()
        payload = await _state_full(socket_path)
        gasto = time.monotonic() - comeco

        assert payload["coop"]["externals"] == 2
        assert gasto < 0.5, f"o state_full ESPEROU a enumeração ({gasto:.2f}s)"
        # E a leitura de fundo foi mesmo agendada — senão o teste acima
        # passaria por omissão, com a descrição nunca chegando à interface.
        await asyncio.wait_for(entrou.wait(), timeout=5.0)


# ---------------------------------------------------------------------------
# 2. A GUI conta a MESA — Gtk fake (o render importa `gi.repository` dentro)
# ---------------------------------------------------------------------------


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None
        self.markup: str | None = None

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_line_wrap(self, _value: bool) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup
        self.markup = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def set_fraction(self, _value: float) -> None:
        pass

    def set_show_text(self, _value: bool) -> None:
        pass

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _payload_quatro_controles() -> dict[str, Any]:
    """O estado medido em 25/07: dois DualSense, um Nintendo, um 8BitDo."""
    return {
        "connected": True,
        "transport": "usb",
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense",
                              "backend": "uhid"},
        "native_mode": False,
        "coop": {"enabled": True, "players": 2, "externals": 2},
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True,
             "uniq": MAC_DS1, "player_slot": 1, "player": 1, "battery_pct": 87},
            {"index": 1, "connected": True, "transport": "bt", "is_primary": False,
             "uniq": MAC_DS2, "player_slot": 2, "player": 2, "battery_pct": 64},
        ],
        "external_controllers": [
            {"kind": "external", "connected": True, "identity": ID_PRO,
             "player_slot": 3, "name": "Nintendo Co., Ltd. Pro Controller",
             "vid": "057e", "pid": "2009", "bus": "bluetooth",
             "uniq": "aa:bb:cc:00:00:e1", "driver": "nintendo"},
            {"kind": "external", "connected": True, "identity": ID_8BITDO,
             "player_slot": 4, "name": "8BitDo Pro 2", "vid": "2dc8",
             "pid": "3106", "bus": "usb", "uniq": None, "driver": "hid-generic"},
        ],
    }


class TestMesaEUmaSo:
    """Entrega 2 — a contagem é uma só e inclui os externos."""

    def test_a_mesa_soma_dualsense_e_externos_na_ordem_do_numero(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import controles_na_mesa

        mesa = controles_na_mesa(_payload_quatro_controles())

        assert [c.get("player_slot") for c in mesa] == [1, 2, 3, 4]
        assert [c["kind"] for c in mesa] == [
            "dualsense", "dualsense", "external", "external"
        ]

    def test_o_carimbo_de_especie_nao_suja_o_payload(self) -> None:
        """As entradas são cópias: outro consumidor lê o mesmo tick."""
        from hefesto_dualsense4unix.app.actions.home_actions import controles_na_mesa

        payload = _payload_quatro_controles()
        controles_na_mesa(payload)

        assert "kind" not in payload["controllers"][0]

    def test_dualsense_desconectado_nao_entra_na_mesa(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import controles_na_mesa

        payload = _payload_quatro_controles()
        payload["controllers"][1]["connected"] = False

        assert len(controles_na_mesa(payload)) == 3


class TestCabecalhoEAbaStatus:
    """Entrega 2 no caminho real: `state_full` -> rótulo do cabeçalho."""

    def _host(self) -> Any:
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        class _Builder:
            def __init__(self) -> None:
                self._widgets: dict[str, Any] = {}

            def get_object(self, wid: str) -> Any:
                return self._widgets.setdefault(wid, _FakeWidget())

        class _Host(StatusActionsMixin):
            def __init__(self) -> None:
                self.builder = _Builder()
                self._reconnect_state = "online"
                self._consecutive_failures = 0

        return _Host()

    def test_o_cabecalho_diz_quatro_com_quatro_na_mesa(self) -> None:
        host = self._host()

        host._render_online(_payload_quatro_controles())

        markup = host.builder.get_object("header_connection").markup
        assert "4 controles" in markup
        # A via de cada um entra na mesma linha — inclusive a dos externos.
        assert markup.count("BT") == 2
        assert markup.count("USB") == 2

    def test_sem_dualsense_o_cabecalho_nao_diz_desconectado(self) -> None:
        """`connected` fala só do primário; dois externos são dois controles."""
        host = self._host()
        payload = _payload_quatro_controles()
        payload["controllers"] = []
        payload["connected"] = False

        host._render_online(payload)

        markup = host.builder.get_object("header_connection").markup
        assert "Desconectado" not in markup
        assert "2 controles" in markup

    def test_um_externo_sozinho_tambem_conta_como_controle_ligado(self) -> None:
        """O ramo de UM controle é outro caminho — e mentia do mesmo jeito.

        Com um Nintendo Pro ligado e nenhum DualSense, `connected` é falso e o
        cabeçalho afirmava "Controle Desconectado" com o controle na mão dela.
        """
        host = self._host()
        payload = _payload_quatro_controles()
        payload["controllers"] = []
        payload["connected"] = False
        del payload["external_controllers"][1]

        host._render_online(payload)

        markup = host.builder.get_object("header_connection").markup
        assert "Desconectado" not in markup
        assert "Conectado Via BT" in markup

    def test_payload_legado_sem_bloco_de_controles_segue_funcionando(self) -> None:
        """Daemon antigo: só `connected`/`transport`. O caminho degradado fica."""
        host = self._host()

        host._render_online({"connected": True, "transport": "usb"})

        assert "Conectado Via USB" in (
            host.builder.get_object("header_connection").markup
        )


class TestCartoesDaAbaInicio:
    """Entrega 3 — um cartão por controle, e entrega 6 — o travessão."""

    def _host(self) -> Any:
        from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin

        class _Host:
            _render_home = HomeActionsMixin._render_home
            _render_home_controllers = HomeActionsMixin._render_home_controllers
            _render_coop_prep = HomeActionsMixin._render_coop_prep

            def __init__(self) -> None:
                self._home_guard = False
                self._home_offline = False
                self._home_controllers_box = _FakeWidget()
                self._home_mode_selector = _FakeWidget()
                self._home_players_hint = _FakeWidget()
                self._home_flavor_selector = _FakeWidget()
                self._home_mode_desc = _FakeWidget()
                self._home_origin_label = _FakeWidget()
                self._home_session_label = _FakeWidget()
                self._home_gamepad_opts = _FakeWidget()
                self._home_vpad_banner = _FakeWidget()
                self._home_wrapper_banner = _FakeWidget()
                self._home_shutdown_btn = _FakeWidget()
                self._home_renumber_btn = _FakeWidget()
                self._home_renumber_hint = _FakeWidget()
                self._home_coop_prep_btn = _FakeWidget()
                self._home_coop_prep_hint = _FakeWidget()

        return _Host()

    @staticmethod
    def _titulos(host: Any) -> list[str]:
        return [
            str(card.children[0].label)
            for card in host._home_controllers_box.get_children()
        ]

    def test_quatro_controles_viram_quatro_cartoes_numerados_1_a_4(
        self, fake_gtk: None
    ) -> None:
        host = self._host()

        host._render_home(_payload_quatro_controles())

        titulos = self._titulos(host)
        assert len(titulos) == 4
        assert "Controle 1" in titulos[0]
        assert "Controle 3" in titulos[2]
        assert "Controle 4" in titulos[3]

    def test_o_externo_mostra_travessao_no_lugar_do_jogador(
        self, fake_gtk: None
    ) -> None:
        """Entrega 6: o jogo numera esse controle, não nós."""
        host = self._host()

        host._render_home(_payload_quatro_controles())

        titulos = self._titulos(host)
        assert titulos[0] == "<b>Controle 1 — P1</b>"
        assert titulos[2] == "Controle 3 — P—"
        assert titulos[3] == "Controle 4 — P—"

    def test_o_cartao_do_externo_explica_o_travessao_em_texto(
        self, fake_gtk: None
    ) -> None:
        """Tooltip não conta: só aparece para quem já desconfiou."""
        from hefesto_dualsense4unix.app.actions.home_actions import (
            EXTERNO_SEM_NUMERO_NOSSO,
        )

        host = self._host()

        host._render_home(_payload_quatro_controles())

        cartao_externo = host._home_controllers_box.get_children()[2]
        assert any(
            child.label == EXTERNO_SEM_NUMERO_NOSSO for child in cartao_externo.children
        )

    def test_o_externo_sem_numero_do_registro_tambem_mostra_travessao(
        self, fake_gtk: None
    ) -> None:
        """Sem opinião do registro não se inventa "Controle 1" (NUMA-05)."""
        host = self._host()
        payload = _payload_quatro_controles()
        payload["external_controllers"][0]["player_slot"] = None
        payload["external_controllers"][1]["player_slot"] = None

        host._render_home(payload)

        assert self._titulos(host)[2:] == ["Controle — — P—", "Controle — — P—"]


class TestBotaoEFraseDoCoop:
    """Entregas 2 e 6 no botão e na frase que ficam embaixo dele."""

    def test_o_botao_promete_quatro_jogadores_com_quatro_na_mesa(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            controles_na_mesa,
            coop_prep_label,
        )

        mesa = controles_na_mesa(_payload_quatro_controles())

        assert coop_prep_label(mesa) == "Preparar co-op (4 jogadores)"

    def test_a_frase_separa_quem_nos_numeramos_de_quem_o_jogo_numera(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_players_hint,
            controles_na_mesa,
        )

        frase = _format_players_hint(controles_na_mesa(_payload_quatro_controles()))

        assert frase == (
            "4 controles na mesa — 2 jogadores são numerados pelo Hefesto; "
            "os outros 2 entram como eles mesmos e quem numera é o jogo."
        )

    def test_sem_externo_a_frase_antiga_fica_intacta(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_players_hint,
            controles_na_mesa,
        )

        payload = _payload_quatro_controles()
        payload["external_controllers"] = []

        frase = _format_players_hint(controles_na_mesa(payload))

        assert frase == "2 controles = 2 jogadores"

    def test_com_um_externo_so_a_frase_fica_no_singular(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_players_hint,
            controles_na_mesa,
        )

        payload = _payload_quatro_controles()
        del payload["external_controllers"][1]

        frase = _format_players_hint(controles_na_mesa(payload))

        assert frase == (
            "3 controles na mesa — 2 jogadores são numerados pelo Hefesto; "
            "o outro entra como ele mesmo e quem numera é o jogo."
        )


class TestChipsSemRotaPropria:
    """Entrega 5 — duas rotas de dados para a mesma pergunta divergem."""

    def _host(self) -> Any:
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        class _Builder:
            def __init__(self) -> None:
                self._widgets: dict[str, Any] = {}

            def get_object(self, wid: str) -> Any:
                return self._widgets.setdefault(wid, _FakeWidget())

        class _Host(StatusActionsMixin):
            def __init__(self) -> None:
                self.builder = _Builder()
                self._externals = []
                self._target_combo = None
                self._mic_monitor = None
                self._status_cards = {}
                self._status_card_keys = []

        return _Host()

    def test_a_fita_de_chips_come_do_state_full(self) -> None:
        host = self._host()

        host._render_slow_state(_payload_quatro_controles())

        assert [e["identity"] for e in host._externals] == [ID_PRO, ID_8BITDO]

    def test_a_busca_propria_de_inventario_nao_existe_mais(self) -> None:
        """Enquanto houvesse duas rotas, elas voltariam a divergir."""
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        assert not hasattr(StatusActionsMixin, "_maybe_fetch_externals")
        assert not hasattr(StatusActionsMixin, "_on_externals_result")

    def test_payload_sem_a_chave_nao_apaga_a_fita(self) -> None:
        """Daemon sem registro de externos: não saber ≠ "não há nenhum"."""
        host = self._host()
        host._render_slow_state(_payload_quatro_controles())
        payload = _payload_quatro_controles()
        del payload["external_controllers"]

        host._render_slow_state(payload)

        assert len(host._externals) == 2

    def test_a_aba_status_diz_quatro_controles(self) -> None:
        host = self._host()

        host._render_slow_state(_payload_quatro_controles())

        assert (
            host.builder.get_object("status_connection").label
            == "Conectado (4 controles)"
        )


# ---------------------------------------------------------------------------
# 3. O campo dos "8 controles" da aba Emulação (entrega 4)
# ---------------------------------------------------------------------------


class TestGamepadsDoSistema:
    """O campo contava NÓS de joystick e chamava aquilo de "controles"."""

    #: O que esta máquina reportou em 25/07, com 3 controles físicos ligados e
    #: 2 gamepads virtuais do Hefesto de pé — 9 nós de `/dev/input/js*`.
    NOS_MEDIDOS: ClassVar[list[dict[str, str]]] = [
        {"path": "/dev/input/js0", "name": "Nintendo Co., Ltd. Pro Controller",
         "uniq": "aa:bb:cc:00:00:e1",
         "sys": "/sys/devices/pci0000:00/usb3/3-2/0003:057E:2009.0003/input/input13/js0"},
        {"path": "/dev/input/js1", "name": "Sony … DualSense Wireless Controller",
         "uniq": "aa:bb:cc:00:00:11",
         "sys": "/sys/devices/pci0000:00/usb1/1-4/0003:054C:0CE6.0006/input/input24/js1"},
        {"path": "/dev/input/js2", "name": "Sony … DualSense … Motion Sensors",
         "uniq": "aa:bb:cc:00:00:11",
         "sys": "/sys/devices/pci0000:00/usb1/1-4/0003:054C:0CE6.0006/input/input25/js2"},
        {"path": "/dev/input/js3", "name": "Hefesto Virtual DualSense P1",
         "uniq": "02:fe:00:00:00:01",
         "sys": "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.0007/input/input28/js3"},
        {"path": "/dev/input/js4", "name": "Hefesto Virtual DualSense P1 Motion Sensors",
         "uniq": "02:fe:00:00:00:01",
         "sys": "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.0007/input/input29/js4"},
        {"path": "/dev/input/js5", "name": "DualSense Wireless Controller",
         "uniq": "aa:bb:cc:00:00:22",
         "sys": "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0009/input/input39/js5"},
        {"path": "/dev/input/js6", "name": "DualSense … Motion Sensors",
         "uniq": "aa:bb:cc:00:00:22",
         "sys": "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0009/input/input40/js6"},
        {"path": "/dev/input/js7", "name": "Hefesto Virtual DualSense P2",
         "uniq": "02:fe:00:00:00:02",
         "sys": "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.000A/input/input42/js7"},
        {"path": "/dev/input/js8", "name": "Hefesto Virtual DualSense P2 Motion Sensors",
         "uniq": "02:fe:00:00:00:02",
         "sys": "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.000A/input/input43/js8"},
    ]

    def test_um_controle_com_dois_nos_conta_uma_vez_so(self) -> None:
        """Todo DualSense abre gamepad + sensores de movimento."""
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            classificar_joysticks,
        )

        fisicos, nossos, outros = classificar_joysticks(self.NOS_MEDIDOS)

        assert (fisicos, nossos, outros) == (3, 2, 0)

    def test_controle_bluetooth_sob_devices_virtual_nao_vira_nosso(self) -> None:
        """BLUEZ-UHID-01: o BlueZ cria o HID do controle físico em uhid."""
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            classificar_joysticks,
        )

        bt = [n for n in self.NOS_MEDIDOS if n["uniq"] == "aa:bb:cc:00:00:22"]

        assert classificar_joysticks(bt) == (1, 0, 0)

    def test_o_vpad_com_mascara_e_reconhecido_pelo_mac_forjado(self) -> None:
        """O nome do vpad MENTE de propósito — a máscara DualSense o faz.

        O sinal que não mente é o `uniq` `02:fe:…` que nós mesmos forjamos por
        jogador. Sem ele, um vpad mascarado seria contado como controle dela.
        """
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            classificar_joysticks,
        )

        mascarado = [
            {"path": "/dev/input/js9", "name": "DualSense Wireless Controller",
             "uniq": "02:fe:00:00:00:03",
             "sys": "/sys/devices/virtual/misc/uhid/0003:054C:0CE6.000B"
                    "/input/input51/js9"},
        ]

        assert classificar_joysticks(mascarado) == (0, 1, 0)

    def test_gamepad_de_uinput_entra_como_de_outro_programa(self) -> None:
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            classificar_joysticks,
        )

        steam = [
            {"path": "/dev/input/js9", "name": "Microsoft X-Box 360 pad 0",
             "uniq": "",
             "sys": "/sys/devices/virtual/input/input50/js9"},
        ]

        assert classificar_joysticks(steam) == (0, 0, 1)

    def test_o_rotulo_separa_o_que_e_nosso_e_diz_que_conta_nos(self) -> None:
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            rotulo_gamepads,
        )

        assert rotulo_gamepads(3, 2, 0, 9) == (
            "3 controles físicos, 2 gamepads virtuais do Hefesto — "
            "9 nós em /dev/input/js*"
        )

    def test_o_rotulo_nunca_chama_no_de_controle(self) -> None:
        """Era o defeito: "8 controles detectados pelo sistema"."""
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            rotulo_gamepads,
        )

        texto = rotulo_gamepads(3, 2, 1, 9)

        assert "9 controles" not in texto
        assert "nós em /dev/input/js*" in texto
