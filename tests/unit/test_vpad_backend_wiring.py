"""Ligação do backend de vpad ao daemon (SPRINT-UHID-VPAD-01, UHID-02, VPAD-03/08).

O módulo uhid estava provado no hardware mas não tinha call site: nada em `src/`
o importava. Aqui trava-se o que o daemon precisa ENTREGAR à factory para o vpad
uhid ser um DualSense de verdade em vez de um device mudo:

1. **o índice do jogador** — no uhid ele vira o MAC do vpad. Todos nascendo
   `player=1` = MAC repetido = probe do P2 em diante morrendo com -EEXIST, ou
   seja, co-op de 4 reduzido a 1.
2. **o veto do backend fake** (`allow_uhid`, VPAD-08) — o daemon FAKE
   (`run.sh --fake`, smoke na máquina da usuária) não pode registrar um
   DualSense Edge REAL no kernel, visível pela Steam.

E o que o daemon NÃO entrega mais (VPAD-03/BT-01): o hidraw do físico. O
blueprint é o canônico embutido — o caminho de criação nunca pergunta hidraw ao
backend, então nem o boot sem controle nem o EIO do BT dormindo decidem o
backend do vpad.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    controller_allows_uhid,
    start_gamepad_emulation,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad

MAC_P1 = "aabbcc001100"
MAC_P2 = "aabbcc001122"


class _FakePad:
    flavor = "dualsense"

    def stop(self) -> None: ...


@pytest.fixture()
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Intercepta a factory: registra os kwargs de cada vpad pedido."""
    registro: list[dict[str, Any]] = []

    def _fake_factory(flavor: str | None, **kwargs: Any) -> Any:
        registro.append({"flavor": flavor, **kwargs})
        return _FakePad()

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        _fake_factory,
    )
    return registro


class _FakeReader:
    """EvdevReader falso já com o grab confirmado."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None: ...

    def snapshot(self) -> Any:  # pragma: no cover - forward_all não roda aqui
        raise NotImplementedError


class _StoreEspiao:
    """StateStore falso — só o `bump` que o VPAD-05 usa (fallback contável)."""

    def __init__(self) -> None:
        self.bumps: list[str] = []

    def bump(self, counter: str, delta: int = 1) -> int:
        self.bumps.append(counter)
        return len(self.bumps)


def _daemon(*, hidraw: dict[str | None, str] | None = None) -> Any:
    """Daemon falso; `hidraw` != None dá ao controller o `hidraw_path` do backend
    real (pydualsense) — é ISSO (e não o path devolvido) que libera o uhid."""
    calls: list[str | None] = []

    def _hidraw_path(uniq: str | None = None) -> str | None:
        calls.append(uniq)
        return (hidraw or {}).get(uniq)

    controller = SimpleNamespace(
        _evdev=SimpleNamespace(_device_path=Path("/dev/input/event5")),
        primary_uniq=MAC_P1,
        _desired=SimpleNamespace(player_leds=None),
        set_player_leds=lambda _bits: None,
        hidraw_path=_hidraw_path if hidraw is not None else None,
    )
    return SimpleNamespace(
        store=_StoreEspiao(),
        config=SimpleNamespace(
            coop_enabled=True,
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
            # Passthrough (None): o stop real zera motores best-effort — o
            # controller fake sem set_rumble degrada em warning, sem crash.
            rumble_active=None,
        ),
        _gamepad_device=None,
        _mouse_device=None,
        controller=controller,
        _coop_manager=None,
        hidraw_calls=calls,
    )


class TestControllerAllowsUhid:
    def test_backend_real_libera_o_uhid(self) -> None:
        assert controller_allows_uhid(_daemon(hidraw={})) is True

    def test_backend_fake_veta_o_uhid(self) -> None:
        """FakeController/IController não têm `hidraw_path` — é a declaração
        explícita de "sem uhid" (VPAD-08): o smoke não planta Edge real."""
        assert controller_allows_uhid(_daemon()) is False

    def test_nao_depende_de_controle_conectado(self) -> None:
        """O gate é sobre o BACKEND, não sobre o hardware do momento: backend
        real sem nenhum controle (boot) continua liberando o uhid — o blueprint
        canônico não precisa do físico."""
        daemon = _daemon(hidraw={})  # backend real, zero controles mapeados

        assert controller_allows_uhid(daemon) is True
        assert daemon.hidraw_calls == []  # nem pergunta path a ninguém


class TestGamepadPrimario:
    def test_p1_recebe_player_1_e_o_uhid_liberado(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert chamadas == [
            {"flavor": "dualsense", "rumble_sink": chamadas[0]["rumble_sink"],
             "player": 1, "allow_uhid": True}
        ]
        assert daemon.hidraw_calls == []  # o caminho de criação não lê o físico

    def test_backend_fake_passa_o_veto_a_factory(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        daemon = _daemon()

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert chamadas[0]["allow_uhid"] is False

    def test_factory_sem_backend_falha_o_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_k: None,
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is False
        assert daemon._gamepad_device is None
        assert daemon.config.gamepad_emulation_enabled is False


class TestCoopPorJogador:
    @pytest.fixture(autouse=True)
    def _sem_hardware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
            lambda self: True,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {MAC_P1: Path("/dev/input/event5"),
                     MAC_P2: Path("/dev/input/event7")},
        )
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})

    def test_secundario_recebe_o_seu_player_e_o_uhid_liberado(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """MAC próprio por jogador: o vpad do P2 não pode nascer com `player=1`."""
        daemon = _daemon(hidraw={None: "/dev/hidraw4", MAC_P2: "/dev/hidraw7"})
        daemon._gamepad_device = _FakePad()
        CoopManager(daemon).sync()

        assert len(chamadas) == 1
        assert chamadas[0]["player"] == 2
        assert chamadas[0]["allow_uhid"] is True
        assert daemon.hidraw_calls == []  # blueprint canônico: ninguém pede hidraw

    def test_jogador_sem_mac_tambem_ganha_uhid(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Identidade "path:" (controle não-DualSense) não degrada mais o vpad:
        o blueprint canônico não precisa do físico — VPAD-09 (uniformidade)."""
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {MAC_P1: Path("/dev/input/event5"),
                     "path:/dev/input/event7": Path("/dev/input/event7")},
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4"})
        daemon._gamepad_device = _FakePad()
        CoopManager(daemon).sync()

        assert chamadas[0]["allow_uhid"] is True
        assert daemon.hidraw_calls == []

    def test_vpad_recusado_derruba_o_jogador_e_agenda_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_k: None,
        )
        daemon = _daemon(hidraw={None: "/dev/hidraw4", MAC_P2: "/dev/hidraw7"})
        daemon._gamepad_device = _FakePad()
        mgr = CoopManager(daemon)
        mgr.sync()

        assert mgr._players == {}
        assert mgr._retry_spawn is True


class TestCoopModuloNaoImportaBackendConcreto:
    def test_coop_fala_com_a_factory(self) -> None:
        """Regressão de arquitetura: quem escolhe o backend é a factory.

        O co-op voltar a construir `UinputGamepad` na mão desliga o uhid (e a
        vibração da máscara DualSense) sem que nenhum outro teste fique vermelho.
        """
        fonte = Path(coop_mod.__file__).read_text(encoding="utf-8")

        assert "make_virtual_pad" in fonte
        assert "UinputGamepad.for_flavor" not in fonte


class _PadP1:
    """Vpad do P1 já criado, com o backend declarado (o que o VPAD-02 compara)."""

    def __init__(self, flavor: str = "dualsense", backend: str = "uinput") -> None:
        self.flavor = flavor
        self.backend = backend
        self.parado = False

    def stop(self) -> None:
        self.parado = True


class _LoggerEspiao:
    """Captura os eventos logados — o no-op por cooldown NÃO pode ser mudo."""

    def __init__(self) -> None:
        self.eventos: list[str] = []

    def info(self, evento: str, **_kw: Any) -> None:
        self.eventos.append(evento)

    def warning(self, evento: str, **_kw: Any) -> None:
        self.eventos.append(evento)

    def debug(self, evento: str, **_kw: Any) -> None:
        self.eventos.append(evento)


class TestRebackendPorReselecao:
    """VPAD-02: o early-return compara (flavor, backend) — re-selecionar
    DualSense na GUI é o "botão de força" da promoção uinput→uhid, e o apply
    idêntico (perfil/autoswitch reaplicam a emulação a cada troca de janela)
    segue no-op de verdade."""

    @pytest.fixture(autouse=True)
    def _sem_hardware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)

    def test_reselecionar_dualsense_promove_o_vpad_degradado(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        daemon = _daemon(hidraw={})
        pad = _PadP1()
        daemon._gamepad_device = pad

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True

        assert pad.parado is True  # derrubou o uinput degradado...
        assert len(chamadas) == 1  # ...e recriou via factory (que prefere o uhid)
        assert chamadas[0]["allow_uhid"] is True

    def test_apply_identico_com_uhid_saudavel_e_no_op(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """Backend já uhid: recriar aqui derrubaria o device do jogo à toa."""
        daemon = _daemon(hidraw={})
        pad = _PadP1(backend="uhid")
        daemon._gamepad_device = pad

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert pad.parado is False
        assert chamadas == []

    def test_mascara_xbox_segue_no_op(self, chamadas: list[dict[str, Any]]) -> None:
        """Xbox é uinput por design (o hid_playstation não faz bind em VID/PID
        da Microsoft) — não existe promoção a fazer."""
        daemon = _daemon(hidraw={})
        pad = _PadP1(flavor="xbox", backend="uinput")
        daemon._gamepad_device = pad

        assert start_gamepad_emulation(daemon, flavor="xbox") is True
        assert pad.parado is False
        assert chamadas == []

    def test_backend_fake_nao_recria_a_toa(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """VPAD-08 + anti-churn: sem backend real o rebackend daria só OUTRO
        uinput — o apply idêntico segue no-op."""
        daemon = _daemon()  # controller sem hidraw_path = backend fake
        pad = _PadP1()
        daemon._gamepad_device = pad

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert pad.parado is False
        assert chamadas == []

    def test_uhid_indisponivel_nao_derruba_o_uinput(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ressalva do VPAD-02: com o uhid quebrado, derrubar o vpad uinput que
        FUNCIONA seria input drop sem ganho nenhum."""
        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)
        daemon = _daemon(hidraw={})
        pad = _PadP1()
        daemon._gamepad_device = pad

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert pad.parado is False
        assert chamadas == []

    def test_segunda_tentativa_no_cooldown_e_no_op_com_log(
        self, chamadas: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ressalva do VPAD-02: o no-op por cooldown devolve True (a GUI mostra
        sucesso), então o motivo TEM que ficar no journal — "cliquei e nada"
        precisa de rastro."""
        espiao = _LoggerEspiao()
        monkeypatch.setattr(gamepad_mod, "logger", espiao)
        daemon = _daemon(hidraw={})
        daemon._gamepad_device = _PadP1()
        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert len(chamadas) == 1  # 1ª re-seleção promoveu (e carimbou o cooldown)

        pad2 = _PadP1()  # o uhid caiu de novo (bind falhou): uinput outra vez
        daemon._gamepad_device = pad2
        assert start_gamepad_emulation(daemon, flavor="dualsense") is True

        assert pad2.parado is False
        assert len(chamadas) == 1  # nada recriado dentro do cooldown
        assert "rebackend_suprimido_por_cooldown" in espiao.eventos

    def test_apply_automatico_nunca_promove_sob_falha_estavel(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """Latch do BT-04(b), critério 1: com o uhid quebrado por razão ESTÁVEL
        que o precheck não enxerga (kernel sem `hid_playstation` —
        `uhid_available()` devolve True mas o bind nunca vem), N re-aplicações
        automáticas (perfil/autoswitch a cada troca de janela) NÃO recriam o
        vpad uinput que funciona — nem depois do cooldown expirar."""
        daemon = _daemon(hidraw={})
        pad = _PadP1()
        daemon._gamepad_device = pad

        for _ in range(5):
            # Sem carimbo de cooldown ativo: o veto tem que ser pela ORIGEM.
            daemon._last_rebackend_ts = float("-inf")
            assert (
                start_gamepad_emulation(daemon, flavor="dualsense", origin="profile")
                is True
            )

        assert pad.parado is False
        assert chamadas == []  # nenhum input drop automático, nunca

    def test_acao_explicita_da_usuaria_tenta_uma_vez(
        self, chamadas: list[dict[str, Any]]
    ) -> None:
        """Latch do BT-04(b), critério 1 (segunda metade): depois de N applies
        automáticos vetados, 1 gesto MANUAL (re-selecionar DualSense na GUI)
        tenta a promoção exatamente 1 vez."""
        daemon = _daemon(hidraw={})
        pad = _PadP1()
        daemon._gamepad_device = pad
        for _ in range(3):
            start_gamepad_emulation(daemon, flavor="dualsense", origin="profile")
        assert chamadas == []

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True

        assert pad.parado is True  # o gesto manual derrubou o degradado...
        assert len(chamadas) == 1  # ...e recriou 1 vez (cooldown segura a 2ª)


class TestFallbackNuncaSilencioso:
    """VPAD-05: flavor dualsense terminando em backend uinput é DEGRADAÇÃO — o
    start conta no store (`gamepad.uhid.fallback`) para o doctor, e o
    `state_full` expõe degraded/motivo para a GUI (fase 2). uhid saudável e
    máscara xbox (uinput por design) não contam nada."""

    @pytest.fixture(autouse=True)
    def _sem_grab(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)

    def _factory_devolvendo(
        self, monkeypatch: pytest.MonkeyPatch, *, flavor: str, backend: str
    ) -> Any:
        pad = SimpleNamespace(flavor=flavor, backend=backend, stop=lambda: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_k: pad,
        )
        return pad

    def test_dualsense_em_uinput_conta_no_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._factory_devolvendo(monkeypatch, flavor="dualsense", backend="uinput")
        daemon = _daemon(hidraw={})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True

        assert daemon.store.bumps == ["gamepad.uhid.fallback"]

    def test_uhid_saudavel_nao_conta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._factory_devolvendo(monkeypatch, flavor="dualsense", backend="uhid")
        daemon = _daemon(hidraw={})

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True
        assert daemon.store.bumps == []

    def test_mascara_xbox_nao_conta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Xbox é uinput por design (o hid_playstation não binda VID Microsoft)
        — contá-la como degradação faria o badge da fase 2 mentir sempre."""
        self._factory_devolvendo(monkeypatch, flavor="xbox", backend="uinput")
        daemon = _daemon(hidraw={})

        assert start_gamepad_emulation(daemon, flavor="xbox") is True
        assert daemon.store.bumps == []

    def test_daemon_sem_store_nao_quebra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """getattr defensivo: daemons dublados (e o FAKE dos smokes) podem não
        ter store — o start não pode falhar por causa da contagem."""
        self._factory_devolvendo(monkeypatch, flavor="dualsense", backend="uinput")
        daemon = _daemon(hidraw={})
        daemon.store = None

        assert start_gamepad_emulation(daemon, flavor="dualsense") is True


def test_o_lifecycle_propaga_a_origem_ate_o_gate() -> None:
    """BT-04(b): sem o `origin=origin` no repasse do `set_gamepad_emulation`,
    o latch anti-churn morre em silêncio — o apply de perfil/autoswitch volta
    a contar como gesto manual e recria o vpad degradado a cada troca de
    janela (o input drop em loop que o critério 1 do BT-04 veta)."""
    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")

    assert "start_gamepad_emulation(self, flavor=flavor, origin=origin)" in fonte
