"""Testes do schema de perfil."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.schema import (
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
