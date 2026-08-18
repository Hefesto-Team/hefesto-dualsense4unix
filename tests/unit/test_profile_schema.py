"""Testes do schema de perfil."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)


class TestMatchAny:
    def test_sempre_casa(self):
        m = MatchAny()
        assert m.matches({}) is True
        assert m.matches({"wm_class": "x"}) is True

    def test_type_literal(self):
        m = MatchAny()
        assert m.type == "any"


class TestMatchCriteria:
    def test_vazio_nao_casa(self):
        m = MatchCriteria()
        assert m.matches({"wm_class": "x"}) is False

    def test_wm_class_or(self):
        m = MatchCriteria(window_class=["Steam", "Cyberpunk2077.exe"])
        assert m.matches({"wm_class": "Steam"}) is True
        assert m.matches({"wm_class": "Firefox"}) is False

    def test_title_regex_search(self):
        m = MatchCriteria(window_title_regex="Cyberpunk")
        assert m.matches({"wm_name": "Cyberpunk 2077"}) is True
        assert m.matches({"wm_name": "Doom Eternal"}) is False

    def test_process_name_match_basename(self):
        m = MatchCriteria(process_name=["Cyberpunk2077.exe"])
        assert m.matches({"exe_basename": "Cyberpunk2077.exe"}) is True
        assert m.matches({"exe_basename": "Steam"}) is False

    def test_and_entre_campos(self):
        m = MatchCriteria(
            window_class=["steam_app_1091500"],
            process_name=["Cyberpunk2077.exe"],
        )
        # Só um dos dois — não casa
        assert m.matches({"wm_class": "steam_app_1091500", "exe_basename": "other"}) is False
        # Ambos — casa
        assert (
            m.matches(
                {
                    "wm_class": "steam_app_1091500",
                    "exe_basename": "Cyberpunk2077.exe",
                }
            )
            is True
        )


class TestLedsConfig:
    def test_defaults(self):
        cfg = LedsConfig()
        assert cfg.lightbar == (0, 0, 0)
        assert cfg.player_leds == [False] * 5

    def test_lightbar_byte_invalido(self):
        with pytest.raises(ValidationError):
            LedsConfig(lightbar=(300, 0, 0))

    def test_player_leds_tamanho_invalido(self):
        with pytest.raises(ValidationError):
            LedsConfig(player_leds=[True, False])


class TestTriggerConfig:
    def test_defaults(self):
        t = TriggerConfig(mode="Off")
        assert t.params == []

    def test_params_aceita_inteiros(self):
        t = TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10])
        assert t.params == [0, 9, 7, 7, 10]

    def test_mode_valido_passa(self):
        # Todos os modos do registro canônico devem validar.
        from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES

        for mode in PRESET_FACTORIES:
            t = TriggerConfig(mode=mode)
            assert t.mode == mode

    def test_mode_invalido_rejeita(self):
        # Um typo de modo deve falhar na validação do schema, não só no apply().
        with pytest.raises(ValidationError):
            TriggerConfig(mode="NaoExiste")

    def test_mode_invalido_rejeita_no_perfil(self):
        # O mesmo vale quando o modo inválido chega via TriggersConfig no Profile.
        with pytest.raises(ValidationError):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "triggers": {"left": {"mode": "Galoping"}, "right": {"mode": "Off"}},
                }
            )


class TestProfile:
    def test_construcao_minima(self):
        p = Profile(name="test", match=MatchAny())
        assert p.version == 1
        assert p.priority == 0
        assert p.triggers.left.mode == "Off"

    def test_name_vazio_rejeita(self):
        with pytest.raises(ValidationError):
            Profile(name="", match=MatchAny())

    def test_name_com_slash_rejeita(self):
        with pytest.raises(ValidationError):
            Profile(name="foo/bar", match=MatchAny())

    def test_name_com_dotdot_rejeita(self):
        with pytest.raises(ValidationError):
            Profile(name="..", match=MatchAny())

    def test_match_discriminator_any(self):
        raw = {"name": "fallback", "match": {"type": "any"}}
        p = Profile.model_validate(raw)
        assert isinstance(p.match, MatchAny)

    def test_match_discriminator_criteria(self):
        raw = {
            "name": "shooter",
            "match": {
                "type": "criteria",
                "window_class": ["Doom"],
            },
        }
        p = Profile.model_validate(raw)
        assert isinstance(p.match, MatchCriteria)
        assert p.match.window_class == ["Doom"]

    def test_version_nao_1_rejeita(self):
        with pytest.raises(ValidationError):
            Profile.model_validate({"name": "x", "version": 2, "match": {"type": "any"}})

    def test_matches_delega(self):
        p = Profile(name="driving", match=MatchCriteria(window_title_regex="Forza"))
        assert p.matches({"wm_name": "Forza Horizon 5"}) is True
        assert p.matches({"wm_name": "Doom"}) is False

    def test_extra_field_rejeitado(self):
        with pytest.raises(ValidationError):
            Profile.model_validate(
                {"name": "x", "match": {"type": "any"}, "extra_field": 1}
            )

    def test_roundtrip_json(self):
        original = Profile(
            name="shooter",
            match=MatchCriteria(window_class=["Doom"], window_title_regex="Doom"),
            priority=10,
            triggers=TriggersConfig(
                left=TriggerConfig(mode="Resistance", params=[3, 5]),
                right=TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10]),
            ),
            leds=LedsConfig(lightbar=(255, 0, 0), player_leds=[True] * 5),
            rumble=RumbleConfig(passthrough=False),
        )
        dumped = original.model_dump(mode="json")
        restored = Profile.model_validate(dumped)
        assert restored == original


# ---------------------------------------------------------------------------
# PERFIL-02 (sprint 2026-07-16-perfis-por-controle): mapa `controllers`
# ---------------------------------------------------------------------------

#: MACs forjados das faixas permitidas (test_anonimato_de_fixtures.py).
_MAC_CABO = "aabbcc000001"
_MAC_BT = "aabbcc000002"


class TestControllersMap:
    def test_perfil_antigo_sem_mapa_carrega_com_none(self):
        """Migração: perfil v1 (sem o campo) valida e `controllers` fica None."""
        p = Profile.model_validate({"name": "vitoria", "match": {"type": "any"}})
        assert p.controllers is None

    def test_mapa_valido_roundtrip(self):
        """O aceite 1 do sprint: o mapa sobrevive a dump→validate sem perda."""
        original = Profile(
            name="vitoria",
            match=MatchAny(),
            controllers={
                _MAC_BT: ControllerOverrides(
                    leds=LedsConfig(lightbar=(0, 255, 0)),
                ),
            },
        )
        restored = Profile.model_validate(original.model_dump(mode="json"))
        assert restored == original
        assert restored.controllers is not None
        assert restored.controllers[_MAC_BT].leds is not None
        assert restored.controllers[_MAC_BT].leds.lightbar == (0, 255, 0)

    def test_override_parcial_valido(self):
        """Só triggers no override — leds None herda a seção global (merge
        POR CAMPO acontece na aplicação, PERFIL-01)."""
        p = Profile.model_validate(
            {
                "name": "x",
                "match": {"type": "any"},
                "controllers": {
                    _MAC_CABO: {"triggers": {"left": {"mode": "Rigid", "params": [0, 100]}}}
                },
            }
        )
        assert p.controllers is not None
        override = p.controllers[_MAC_CABO]
        assert override.leds is None
        assert override.triggers is not None
        assert override.triggers.left.mode == "Rigid"

    def test_key_com_separadores_e_caixa_canonizada(self):
        """JSON editado à mão com "AA:BB:CC:..." casa a key que o backend
        enumera — mesma normalização do `norm_mac`."""
        p = Profile.model_validate(
            {
                "name": "x",
                "match": {"type": "any"},
                "controllers": {"AA:BB:CC:00:00:02": {}},
            }
        )
        assert p.controllers is not None
        assert list(p.controllers) == [_MAC_BT]

    def test_key_path_fallback_rejeitada(self):
        """Key de fallback por path (controle sem serial) não entra no mapa."""
        with pytest.raises(ValidationError, match="12 dígitos"):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "controllers": {"path:/dev/hidraw3": {}},
                }
            )

    def test_key_curta_rejeitada(self):
        with pytest.raises(ValidationError, match="12 dígitos"):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "controllers": {"aabbcc": {}},
                }
            )

    def test_key_degenerada_pro_controller_rejeitada(self):
        """O uniq `000000000001` (medido no Pro Controller, idêntico entre
        unidades) tem 12 hex mas NÃO identifica um controle — rejeitar com
        mensagem clara é o aceite 4 do sprint."""
        with pytest.raises(ValidationError, match="degenerado"):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "controllers": {"000000000001": {}},
                }
            )

    def test_key_broadcast_rejeitada(self):
        with pytest.raises(ValidationError, match="degenerado"):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "controllers": {"ffffffffffff": {}},
                }
            )

    def test_keys_que_colidem_apos_normalizacao_rejeitadas(self):
        """Duas grafias do mesmo MAC não podem coexistir — uma venceria em
        silêncio por ordem de inserção."""
        with pytest.raises(ValidationError, match="duplicadas"):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "any"},
                    "controllers": {
                        _MAC_BT: {},
                        "AA:BB:CC:00:00:02": {},
                    },
                }
            )

    def test_override_rejeita_campo_extra(self):
        """`extra="forbid"` no override — `label` e `mic_led` ficaram FORA por
        decisão da revisão adversarial (4P-03 / AUDIT-FINDING-PROFILE-MIC-LED-
        RESET-01); um campo desconhecido é erro, não silêncio."""
        for campo in ("label", "mic_led"):
            with pytest.raises(ValidationError):
                Profile.model_validate(
                    {
                        "name": "x",
                        "match": {"type": "any"},
                        "controllers": {_MAC_BT: {campo: "y"}},
                    }
                )

    def test_mapa_vazio_valida(self):
        """`{}` explícito é válido (vira omissão no save — ver loader)."""
        p = Profile.model_validate(
            {"name": "x", "match": {"type": "any"}, "controllers": {}}
        )
        assert p.controllers == {}
