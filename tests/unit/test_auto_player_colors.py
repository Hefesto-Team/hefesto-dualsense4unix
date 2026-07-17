"""COR-03 — paleta automática por controle + merge de 3 camadas no backend.

Aceites do sprint 2026-07-16-sprint-cores-e-led-automaticos:
  - paleta canônica PS5 em `led_control` (1=azul, 2=vermelho, 3=verde,
    4=rosa, 5+=branco) e os padrões de player-LED movidos para lá (o coop
    reexporta — compat);
  - precedência POR CAMPO: override explícito por-uniq > camada AUTOMÁTICA
    do provider > default global (D5). Override só de gatilhos não mata a
    cor automática; override de cor mata SÓ a cor;
  - auto desligado (provider None / devolvendo None) = comportamento
    broadcast histórico intacto;
  - hotplug fake pinta a cor do slot no MESMO tick (`_reapply_desired` /
    new_keys do `_refresh_sysfs_leds` — D1);
  - Modo Nativo (output_mute): NENHUM caminho escreve a cor automática nos
    nós (os gates existentes cobrem — D12) e o unmute re-aplica o resolvido;
  - brilho: a cor automática é escalada pelo brilho vigente, pelo MESMO
    caminho do global (`LedSettings.apply_brightness` — D11);
  - DualSense-only/identidade: uniq inválido, vpad e key por path não têm
    cor automática (D9/D10);
  - a ativação de perfil configura o estado do auto no registro
    (`ProfileManager.apply` → `get_identity_registry().configure`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _DesiredOutput,
)
from hefesto_dualsense4unix.core.led_control import (
    LedSettings,
    player_led_pattern,
    player_slot_color,
)
from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    make_auto_output_provider,
)
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)

AZUL = (0, 0, 255)
VERMELHO = (255, 0, 0)


def _backend_com_dois() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}  # type: ignore[dict-item]
    inst._primary_key = KEY_1
    return inst, h1, h2


def _provider_fixo(
    mapa: dict[str, _DesiredOutput],
) -> Any:
    """Provider fake: devolve o `_DesiredOutput` do uniq, ou None."""

    def provider(uniq: str) -> _DesiredOutput | None:
        return mapa.get(uniq)

    return provider


class _FakeLedNode:
    """Nó sysfs falso (mesmo contrato dos testes de coop/backend)."""

    def __init__(self, indicator_dir: str = "/fake/led") -> None:
        self.indicator_dir = indicator_dir
        self.colors: list[tuple[int, int, int]] = []
        self.patterns: list[tuple[bool, bool, bool, bool, bool]] = []

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.colors.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.patterns.append(bits)
        return True


class TestPaletaCanonica:
    def test_cores_ps5(self) -> None:
        assert player_slot_color(1) == (0, 0, 255)  # azul
        assert player_slot_color(2) == (255, 0, 0)  # vermelho
        assert player_slot_color(3) == (0, 255, 0)  # verde
        assert player_slot_color(4) == (255, 0, 128)  # rosa
        # 5+ = branco (fallback neutro, sem cor oficial no PS5).
        assert player_slot_color(5) == (255, 255, 255)
        assert player_slot_color(9) == (255, 255, 255)

    def test_padroes_de_player_led_movidos_com_reexport(self) -> None:
        """O dono agora é o led_control; o import histórico de coop segue vivo."""
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            player_led_pattern as via_coop,
        )

        assert via_coop is player_led_pattern
        assert player_led_pattern(1) == (False, False, True, False, False)
        assert player_led_pattern(4) == (True, True, False, True, True)
        assert player_led_pattern(7) == (True, True, True, True, True)


class TestMergeTresCamadas:
    """Precedência POR CAMPO: explícita > automática > global (D5)."""

    def test_auto_vence_o_global(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_led((10, 10, 10))  # global (broadcast)
        inst.set_auto_output_provider(
            _provider_fixo({UNIQ_1: _DesiredOutput(led=AZUL)})
        )
        assert inst._merged_desired_for_key(KEY_1).led == AZUL
        # O outro controle não tem camada auto → global.
        assert inst._merged_desired_for_key(KEY_2).led == (10, 10, 10)

    def test_explicita_vence_a_auto(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo({UNIQ_2: _DesiredOutput(led=AZUL)})
        )
        inst.set_output_target(1)  # mira o Controle 2
        inst.set_led((9, 9, 9))  # cor explícita por-uniq
        assert inst._merged_desired_for_key(KEY_2).led == (9, 9, 9)

    def test_override_so_de_trigger_nao_mata_a_cor_auto(self) -> None:
        """POR CAMPO: o merge nunca resolve por objeto (refutação do sprint)."""
        from hefesto_dualsense4unix.core.controller import TriggerEffect

        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {UNIQ_2: _DesiredOutput(led=AZUL, player_leds=player_led_pattern(2))}
            )
        )
        inst.set_output_target(1)
        inst.set_trigger("left", TriggerEffect(mode=2, forces=[1, 2, 3, 0, 0, 0, 0]))
        merged = inst._merged_desired_for_key(KEY_2)
        assert merged.led == AZUL  # cor automática sobreviveu
        assert merged.player_leds == player_led_pattern(2)
        assert merged.trigger_left is not None  # override explícito valeu

    def test_override_de_cor_mata_so_a_cor(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {UNIQ_2: _DesiredOutput(led=AZUL, player_leds=player_led_pattern(2))}
            )
        )
        inst.set_output_target(1)
        inst.set_led((9, 9, 9))
        merged = inst._merged_desired_for_key(KEY_2)
        assert merged.led == (9, 9, 9)  # explícita venceu a cor
        assert merged.player_leds == player_led_pattern(2)  # o resto é auto

    def test_auto_off_e_comportamento_historico(self) -> None:
        """Provider None (ou devolvendo None) = merge default+override puro."""
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_led((10, 10, 10))
        assert inst._merged_desired_for_key(KEY_1).led == (10, 10, 10)
        inst.set_auto_output_provider(_provider_fixo({}))  # sempre None
        assert inst._merged_desired_for_key(KEY_1).led == (10, 10, 10)
        inst.set_auto_output_provider(None)  # removido
        assert inst._merged_desired_for_key(KEY_1).led == (10, 10, 10)

    def test_provider_quebrado_nao_derruba_a_resolucao(self) -> None:
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_led((10, 10, 10))

        def explode(uniq: str) -> _DesiredOutput | None:
            raise RuntimeError("provider quebrado")

        inst.set_auto_output_provider(explode)
        assert inst._merged_desired_for_key(KEY_1).led == (10, 10, 10)

    def test_key_por_path_nao_consulta_o_provider(self) -> None:
        """Sem MAC não há identidade estável — cor automática exige uniq (D9)."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h = _FakeHandle()
        inst._handles = {"/dev/hidraw3": h}  # type: ignore[dict-item]
        inst._primary_key = "/dev/hidraw3"
        consultados: list[str] = []

        def provider(uniq: str) -> _DesiredOutput | None:
            consultados.append(uniq)
            return _DesiredOutput(led=AZUL)

        inst.set_auto_output_provider(provider)
        inst.set_led((10, 10, 10))
        assert inst._merged_desired_for_key("/dev/hidraw3").led == (10, 10, 10)
        assert consultados == []  # provider nem foi chamado


class TestHotplugPintaCorDoSlot:
    def test_reapply_desired_escreve_a_cor_auto_no_handle(self) -> None:
        """D1: a cor do slot nasce no MESMO tick do hotplug (reconcile)."""
        inst, _h1, h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {UNIQ_2: _DesiredOutput(led=VERMELHO, player_leds=player_led_pattern(2))}
            )
        )
        inst._reapply_desired(KEY_2, h2)
        assert h2.light.colors[-1] == VERMELHO

    def test_refresh_sysfs_new_keys_reasserta_a_cor_auto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O reassert de nó novo resolve via `_merged_desired_for_key` — a
        camada automática flui sem caminho novo de escrita."""
        from hefesto_dualsense4unix.core import sysfs_leds

        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {UNIQ_1: _DesiredOutput(led=AZUL, player_leds=player_led_pattern(1))}
            )
        )
        node = _FakeLedNode()
        monkeypatch.setattr(sysfs_leds, "discover", lambda: {UNIQ_1: node})
        inst._refresh_sysfs_leds()
        assert node.colors[-1] == AZUL
        assert node.patterns[-1] == player_led_pattern(1)

    def test_connect_reasserta_cor_em_no_ja_mapeado_sem_perfil(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COR-WAKE-01 (fix ao vivo 2026-07-17): um `backend_hotplug_reconcile`
        (connect) re-resolve a cor/LED por-controle em nós JÁ mapeados — não só
        nos `new_keys`. Reproduz o wake que deixava os dois DualSense na cor
        default do kernel: o kernel reseta a classe LED sem recriar o `inputN`
        (mesmo `indicator_dir` → NÃO é new_key), então nem `_reapply_desired`
        (só handles novos) nem o priming de `new_keys` re-pintavam; só uma
        ativação MANUAL de perfil resolvia. Agora o reassert ao fim do
        `connect()` converge sozinho, sem tocar em perfil."""
        from unittest.mock import patch

        from hefesto_dualsense4unix.core import sysfs_leds

        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {
                    UNIQ_1: _DesiredOutput(led=AZUL, player_leds=player_led_pattern(1)),
                    UNIQ_2: _DesiredOutput(
                        led=VERMELHO, player_leds=player_led_pattern(2)
                    ),
                }
            )
        )
        node1, node2 = _FakeLedNode("/fake/led1"), _FakeLedNode("/fake/led2")
        # Nós JÁ mapeados (mesma `indicator_dir` que o discover devolve) →
        # NÃO são `new_keys` no próximo `_refresh_sysfs_leds`.
        inst._sysfs = {KEY_1: node1, KEY_2: node2}  # type: ignore[dict-item]
        monkeypatch.setattr(
            sysfs_leds, "discover", lambda: {UNIQ_1: node1, UNIQ_2: node2}
        )
        # Zera o histórico: mede SÓ o efeito do connect (não escritas de boot).
        node1.colors.clear()
        node2.colors.clear()
        # Nenhum controle NOVO: enumerate devolve os mesmos já presentes.
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[
                (KEY_1, b"/dev/hidraw0", False),
                (KEY_2, b"/dev/hidraw1", False),
            ],
        ):
            inst.connect()

        assert node1.colors[-1] == AZUL
        assert node2.colors[-1] == VERMELHO

    def test_mutado_nao_escreve_cor_auto_no_no(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D12: em Modo Nativo o reassert de nó novo NÃO toca o hardware —
        o gate existente cobre a camada automática também."""
        from hefesto_dualsense4unix.core import sysfs_leds

        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo({UNIQ_1: _DesiredOutput(led=AZUL)})
        )
        inst.set_output_mute(True)
        node = _FakeLedNode()
        monkeypatch.setattr(sysfs_leds, "discover", lambda: {UNIQ_1: node})
        inst._refresh_sysfs_leds()
        assert node.colors == []  # nada escrito mutado
        assert node.patterns == []

    def test_reapply_mutado_nao_escreve_no_no_sysfs(self) -> None:
        """D12 no hotplug: com mute, o nó sysfs do controle não recebe a cor
        automática (o estado interno do handle fica coerente p/ o unmute)."""
        inst, _h1, h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo({UNIQ_2: _DesiredOutput(led=VERMELHO)})
        )
        node = _FakeLedNode()
        inst._sysfs = {KEY_2: node}
        inst.set_output_mute(True)
        inst._reapply_desired(KEY_2, h2)
        assert node.colors == []  # rota sysfs gateada pelo mute

    def test_unmute_reasserta_a_cor_auto(self) -> None:
        """Sair do Modo Nativo re-aplica o resolvido POR-KEY (com a camada
        automática) nos nós sysfs — caminho existente do unmute."""
        inst, _h1, _h2 = _backend_com_dois()
        inst.set_auto_output_provider(
            _provider_fixo(
                {UNIQ_1: _DesiredOutput(led=AZUL, player_leds=player_led_pattern(1))}
            )
        )
        node = _FakeLedNode()
        inst._sysfs = {KEY_1: node}
        inst.set_output_mute(True)
        assert node.colors == []
        inst.set_output_mute(False)
        assert node.colors[-1] == AZUL
        assert node.patterns[-1] == player_led_pattern(1)


class TestProviderDoDaemon:
    """`make_auto_output_provider` — o provider REAL fiado pelo lifecycle."""

    def test_cor_do_slot_escalada_pelo_brilho(self) -> None:
        """D11: paridade com o caminho global (`LedSettings.apply_brightness`)."""
        registry = ControllerIdentityRegistry()
        registry.configure(enabled=True, brightness=0.4)
        provider = make_auto_output_provider(registry)
        out = provider(UNIQ_1)  # 1ª consulta: slot 1 (lazy)
        assert out is not None
        esperado = (
            LedSettings(lightbar=player_slot_color(1), brightness_level=0.4)
            .apply_brightness(0.4)
            .lightbar
        )
        assert out.led == esperado
        assert out.player_leds == player_led_pattern(1)
        # Campos não-automáticos ficam sem opinião (merge por campo).
        assert out.trigger_left is None
        assert out.mic_led is None

    def test_segundo_controle_ganha_vermelho(self) -> None:
        registry = ControllerIdentityRegistry()
        provider = make_auto_output_provider(registry)
        assert provider(UNIQ_1) is not None  # slot 1
        out2 = provider(UNIQ_2)  # slot 2
        assert out2 is not None
        assert out2.led == player_slot_color(2)  # brilho 1.0 = cor pura
        assert out2.player_leds == player_led_pattern(2)

    def test_auto_desligado_devolve_none(self) -> None:
        registry = ControllerIdentityRegistry()
        registry.configure(enabled=False)
        provider = make_auto_output_provider(registry)
        assert provider(UNIQ_1) is None

    def test_vpad_e_uniq_invalido_devolvem_none(self) -> None:
        """D9/D10: vpad nunca; uniq vazio/inválido não tem identidade."""
        registry = ControllerIdentityRegistry()
        provider = make_auto_output_provider(registry)
        assert provider("02fe00000001") is None
        assert provider("") is None

    def test_replug_mantem_a_cor_do_slot(self) -> None:
        """Reserva de sessão (D2): o replug do controle 1 segue azul."""
        registry = ControllerIdentityRegistry()
        provider = make_auto_output_provider(registry)
        assert (p1 := provider(UNIQ_1)) is not None and p1.led == player_slot_color(1)
        assert (p2 := provider(UNIQ_2)) is not None and p2.led == player_slot_color(2)
        registry.mark_disconnected(UNIQ_1)
        registry.sync_connected({UNIQ_2})
        out = provider(UNIQ_1)  # replugou
        assert out is not None
        assert out.led == player_slot_color(1)  # continua azul, não virou 3


class TestPontaAPonta:
    """Backend real + registry real: o merge pinta cada controle com o slot."""

    def test_dois_controles_cores_diferentes_no_hotplug(self) -> None:
        inst, h1, h2 = _backend_com_dois()
        registry = ControllerIdentityRegistry()
        inst.set_auto_output_provider(make_auto_output_provider(registry))
        # Global do perfil (broadcast) — a automática vence por camada.
        inst.set_led((10, 10, 10))
        inst._reapply_desired(KEY_1, h1)
        inst._reapply_desired(KEY_2, h2)
        assert h1.light.colors[-1] == player_slot_color(1)  # azul
        assert h2.light.colors[-1] == player_slot_color(2)  # vermelho
        assert h1.light.colors[-1] != h2.light.colors[-1]

    def test_resolved_player_leds_for_devolve_o_padrao_do_slot(self) -> None:
        """O revert do co-op (PERFIL-06) lê por aqui: com auto ligado, o
        controle volta ao padrão do NÚMERO DO CONTROLE (D7), não ao global."""
        inst, _h1, _h2 = _backend_com_dois()
        registry = ControllerIdentityRegistry()
        inst.set_auto_output_provider(make_auto_output_provider(registry))
        inst.set_player_leds((True, True, True, True, False))  # global
        registry.slot_for(UNIQ_1)  # 1º a chegar = slot 1
        assert inst.resolved_player_leds_for(UNIQ_1) == player_led_pattern(1)
        # O 2º controle resolve o slot 2 LAZY na própria leitura (D1).
        assert inst.resolved_player_leds_for(UNIQ_2) == player_led_pattern(2)
        # Auto desligado → volta ao global do perfil (comportamento histórico).
        registry.configure(enabled=False)
        assert inst.resolved_player_leds_for(UNIQ_2) == (
            True, True, True, True, False,
        )


class TestManagerConfiguraOAuto:
    """`ProfileManager.apply` propaga toggle+brilho ao registro (COR-03)."""

    @pytest.fixture
    def isolated_profiles_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Path:
        from hefesto_dualsense4unix.profiles import loader as loader_module

        target = tmp_path / "profiles"
        target.mkdir()

        def fake_profiles_dir(ensure: bool = False) -> Path:
            if ensure:
                target.mkdir(parents=True, exist_ok=True)
            return target

        monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
        return target

    @pytest.fixture(autouse=True)
    def _singleton_limpo(self) -> Any:
        identity.reset_identity_registry()
        yield
        identity.reset_identity_registry()

    def test_apply_configura_enabled_e_brilho(
        self, isolated_profiles_dir: Path
    ) -> None:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            MatchAny,
            Profile,
        )
        from hefesto_dualsense4unix.testing import FakeController

        profile = Profile(
            name="jogo",
            match=MatchAny(),
            leds=LedsConfig(
                lightbar=(40, 80, 180),
                lightbar_brightness=0.4,
                auto_player_colors=False,
            ),
        )
        fc = FakeController()
        fc.connect()
        ProfileManager(controller=fc).apply(profile)
        registry = identity.get_identity_registry()
        assert registry.auto_enabled is False
        assert registry.auto_brightness == 0.4

    def test_perfil_sem_secao_leds_liga_o_auto(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Decisão documentada: sem seção `leds` no JSON = defaults do schema
        (`LedsConfig()`) = auto ON com brilho 1.0."""
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
        from hefesto_dualsense4unix.testing import FakeController

        registry = identity.get_identity_registry()
        registry.configure(enabled=False, brightness=0.2)
        profile = Profile(name="desktop", match=MatchAny())
        fc = FakeController()
        fc.connect()
        ProfileManager(controller=fc).apply(profile)
        assert registry.auto_enabled is True
        assert registry.auto_brightness == 1.0


class TestSchemaAditivo:
    def test_perfil_antigo_valida_com_default_true(self) -> None:
        from hefesto_dualsense4unix.profiles.schema import LedsConfig

        cfg = LedsConfig(lightbar=(1, 2, 3))
        assert cfg.auto_player_colors is True
        assert "auto_player_colors" not in cfg.model_fields_set

    def test_campo_novo_nao_densifica_override_por_controle(self) -> None:
        """`_controllers_to_specs` ignora o toggle: um override que SÓ escreve
        `auto_player_colors` não vira spec (não pisa o global no merge)."""
        from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs
        from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

        overrides = {
            UNIQ_2: ControllerOverrides.model_validate(
                {"leds": {"auto_player_colors": False}}
            )
        }
        assert _controllers_to_specs(overrides, None) == {}


class TestAtivacaoReassertaResolvido:
    """Fix de integração (2026-07-17, pego AO VIVO na validação pós-install).

    A ativação de perfil terminava no broadcast do GLOBAL
    (`apply_output_defaults`) e a paleta automática só aparecia no PRÓXIMO
    replug — um boot com os controles já conectados ficava com a cor global
    (visto na máquina: dois DualSense em BT, ambos com o roxo do perfil).
    O fix: `reassert_resolved_outputs()` ao final da ativação (manager) e do
    apply_draft (applier) converge o estado físico ao resolvido
    (explícita > automática > global).
    """

    @pytest.fixture(autouse=True)
    def _singleton_limpo(self) -> Any:
        identity.reset_identity_registry()
        yield
        identity.reset_identity_registry()

    def _backend_com_nos(
        self,
    ) -> tuple[PyDualSenseController, _FakeLedNode, _FakeLedNode]:
        inst, _h1, _h2 = _backend_com_dois()
        n1, n2 = _FakeLedNode("/fake/led1"), _FakeLedNode("/fake/led2")
        inst._sysfs = {KEY_1: n1, KEY_2: n2}
        registry = identity.get_identity_registry()
        registry.configure(enabled=True, brightness=1.0)
        inst.set_auto_output_provider(make_auto_output_provider(registry))
        return inst, n1, n2

    def test_apply_de_perfil_repinta_a_paleta_nos_conectados(self) -> None:
        """O cenário exato do bug: perfil global roxo + auto ON + 2 conectados."""
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            MatchAny,
            Profile,
        )

        inst, n1, n2 = self._backend_com_nos()
        manager = ProfileManager(controller=inst)
        profile = Profile(
            name="vitoria-fake",
            match=MatchAny(),
            leds=LedsConfig(lightbar=(129, 61, 156), lightbar_brightness=1.0),
        )
        manager.apply(profile)
        # A ÚLTIMA escrita em cada nó é a cor do SLOT (a paleta venceu o
        # broadcast global) — antes do fix ficava o roxo (129, 61, 156).
        assert n1.colors[-1] == player_slot_color(1)  # azul
        assert n2.colors[-1] == player_slot_color(2)  # vermelho
        assert n1.patterns[-1] == player_led_pattern(1)
        assert n2.patterns[-1] == player_led_pattern(2)

    def test_apply_com_auto_off_mantem_o_global(self) -> None:
        """Regressão do comportamento histórico: auto OFF = broadcast puro."""
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            MatchAny,
            Profile,
        )

        inst, n1, n2 = self._backend_com_nos()
        manager = ProfileManager(controller=inst)
        profile = Profile(
            name="fixo",
            match=MatchAny(),
            leds=LedsConfig(
                lightbar=(129, 61, 156),
                lightbar_brightness=1.0,
                auto_player_colors=False,
            ),
        )
        manager.apply(profile)
        # O reassert com auto OFF re-escreve o RESOLVIDO = global (inócuo).
        assert n1.colors[-1] == (129, 61, 156)
        assert n2.colors[-1] == (129, 61, 156)

    def test_reassert_e_no_op_em_modo_nativo(self) -> None:
        inst, n1, _n2 = self._backend_com_nos()
        inst._output_mute = True
        antes = list(n1.colors)
        inst.reassert_resolved_outputs()
        assert n1.colors == antes  # D12: mutado, o jogo é dono do LED

    def test_apply_draft_chama_o_reassert(self) -> None:
        """O caminho do "Aplicar" da GUI converge o físico ao resolvido."""
        from unittest.mock import MagicMock

        from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

        controller = MagicMock()
        applier = DraftApplier(
            controller=controller, store=MagicMock(), daemon=MagicMock()
        )
        applier._apply_leds({"lightbar": [10, 20, 30], "lightbar_brightness": 1.0})
        controller.reassert_resolved_outputs.assert_called_once()
