"""Débitos R-12: comparação sem caixa no matcher + sentinel `{"type": "manual"}`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
    perfil_e_regra_de_jogo,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    detect_simple_preset,
    simple_extra,
)

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "profiles_default"


class TestComparacaoSemCaixa:
    def test_process_name_casa_com_a_caixa_do_sistema(self) -> None:
        """O caso medido do R-12: perfil com a caixa do jogo, `/proc` idem."""
        m = MatchCriteria(process_name=["Cyberpunk2077.exe"])
        assert m.matches({"exe_basename": "cyberpunk2077.exe"}) is True
        assert m.matches({"exe_basename": "CYBERPUNK2077.EXE"}) is True

    def test_process_name_casa_com_a_caixa_que_ela_digitou(self) -> None:
        """E o inverso: ela digita minúsculo, o executável é CamelCase."""
        m = MatchCriteria(process_name=["cyberpunk2077.exe"])
        assert m.matches({"exe_basename": "Cyberpunk2077.exe"}) is True

    def test_window_class_ignora_caixa_nos_dois_sentidos(self) -> None:
        """`wm_class` muda de grafia entre toolkit/backend de detecção."""
        m = MatchCriteria(window_class=["Steam", "firefox"])
        assert m.matches({"wm_class": "steam"}) is True
        assert m.matches({"wm_class": "Firefox"}) is True
        assert m.matches({"wm_class": "chromium"}) is False

    def test_titulo_ignora_caixa(self) -> None:
        """Título de janela é texto de marketing — "SACKBOY" acontece."""
        m = MatchCriteria(window_title_regex="sackboy")
        assert m.matches({"wm_name": "Sackboy: A Big Adventure"}) is True
        assert m.matches({"wm_name": "SACKBOY"}) is True
        assert m.matches({"wm_name": "Doom Eternal"}) is False

    def test_titulo_permite_exigir_caixa_exata(self) -> None:
        """Saída para quem PRECISA de caixa: o grupo local `(?-i:...)`."""
        m = MatchCriteria(window_title_regex="(?-i:Sackboy)")
        assert m.matches({"wm_name": "Sackboy"}) is True
        assert m.matches({"wm_name": "SACKBOY"}) is False

    def test_and_entre_campos_continua_valendo(self) -> None:
        m = MatchCriteria(
            window_class=["steam_app_1599660"],
            process_name=["Sackboy.exe"],
        )
        assert m.matches({"wm_class": "STEAM_APP_1599660"}) is False
        assert (
            m.matches(
                {"wm_class": "STEAM_APP_1599660", "exe_basename": "sackboy.exe"}
            )
            is True
        )

    def test_janela_sem_dado_nao_casa(self) -> None:
        """Ausência de evidência não é igualdade — nem com entrada vazia."""
        m = MatchCriteria(window_class=["firefox"])
        assert m.matches({}) is False
        assert m.matches({"wm_class": None}) is False
        assert MatchCriteria(process_name=[""]).matches({}) is False

    def test_dado_guardado_nao_e_corrompido(self) -> None:
        """A metade que o R-12 já tinha entregue não pode voltar atrás."""
        m = MatchCriteria(
            window_class=["Steam"],
            process_name=["Cyberpunk2077.exe"],
            window_title_regex="Sackboy",
        )
        assert m.window_class == ["Steam"]
        assert m.process_name == ["Cyberpunk2077.exe"]
        assert m.window_title_regex == "Sackboy"
        assert json.loads(m.model_dump_json())["process_name"] == [
            "Cyberpunk2077.exe"
        ]

    def test_regra_de_jogo_usa_a_mesma_comparacao(self) -> None:
        """`perfil_e_regra_de_jogo` não pode divergir do matcher."""
        profile = Profile(
            name="madjack",
            match=MatchCriteria(window_class=["Steam_App_2111190"]),
        )
        info = {"wm_class": "steam_app_2111190"}
        assert profile.matches(info) is True
        assert perfil_e_regra_de_jogo(profile, info) is True

    def test_regra_de_jogo_com_a_janela_em_caixa_alta(self) -> None:
        """O caso SIMÉTRICO — o que a suíte nunca cobria (UNIFICA-PREDICADO-01)."""
        profile = Profile(
            name="madjack",
            match=MatchCriteria(window_class=["steam_app_2111190"]),
        )
        for wm_class in ("STEAM_APP_2111190", "Steam_App_2111190"):
            info = {"wm_class": wm_class}
            assert profile.matches(info) is True
            assert perfil_e_regra_de_jogo(profile, info) is True

    def test_editor_simples_reconhece_o_jogo_em_qualquer_caixa(self) -> None:
        """O terceiro lugar onde a mesma divergência aparecia (UNIFICA-PREDICADO-01)."""
        for wc in ("Steam_App_2111190", "STEAM_APP_2111190", " steam_app_2111190 "):
            m = MatchCriteria(window_class=[wc])
            assert detect_simple_preset(m) == "steam_game"
            assert simple_extra(m) == "2111190"


class TestSentinelManual:
    def test_nunca_casa(self) -> None:
        m = MatchManual()
        assert m.matches({}) is False
        assert (
            m.matches(
                {
                    "wm_class": "steam_app_1599660",
                    "wm_name": "Sackboy",
                    "exe_basename": "sackboy",
                }
            )
            is False
        )

    def test_round_trip_pelo_json(self) -> None:
        p = Profile.model_validate(
            {"name": "coop", "match": {"type": "manual"}, "priority": 45}
        )
        assert isinstance(p.match, MatchManual)
        assert p.matches({"wm_class": "qualquer"}) is False
        assert json.loads(p.model_dump_json())["match"] == {"type": "manual"}

    def test_sentinel_nao_aceita_criterio_junto(self) -> None:
        """`extra="forbid"`: "manual com um alvo" é contradição, não perfil."""
        with pytest.raises(ValidationError):
            Profile.model_validate(
                {
                    "name": "x",
                    "match": {"type": "manual", "window_class": ["firefox"]},
                }
            )

    def test_nao_e_catch_all(self) -> None:
        """Manual é o OPOSTO de catch-all, e o predicado tem de dizer isso."""
        manual = Profile(name="coop", match=MatchManual())
        assert manual.e_catch_all is False
        assert Profile(name="fallback", match=MatchAny()).e_catch_all is True
        assert Profile(name="orfao", match=MatchCriteria()).e_catch_all is True

    def test_autoswitch_nunca_o_escolhe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mesmo sozinho no disco e com prioridade alta, ele não entra."""
        from hefesto_dualsense4unix.profiles import manager as manager_mod

        manual = Profile(name="coop", match=MatchManual(), priority=99)
        monkeypatch.setattr(manager_mod, "load_all_profiles", lambda: [manual])
        selecionado = manager_mod.ProfileManager(controller=None).select_for_window(
            {"wm_class": "steam_app_1599660", "wm_name": "Sackboy"}
        )
        assert selecionado is None

    def test_editor_simples_nao_inventa_alvo_para_ele(self) -> None:
        """Sem preset detectado, o perfil manual abre no editor avançado."""
        assert detect_simple_preset(MatchManual()) is None
        assert simple_extra(MatchManual()) == ""

    def test_cli_descreve_sem_estourar(self) -> None:
        """`profile list` acessava `.window_class` — o sentinel não tem."""
        from hefesto_dualsense4unix.cli.cmd_profile import _describe_match

        texto = _describe_match(Profile(name="coop", match=MatchManual()))
        assert "manual" in texto


class TestRetrocompatibilidade:
    def test_presets_de_fabrica_continuam_validos(self) -> None:
        """A união ganhou um membro; nenhum perfil de disco pode ter regredido."""
        arquivos = sorted(ASSETS_DIR.glob("*.json"))
        assert arquivos, "presets de fábrica sumiram do repositório"
        for path in arquivos:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = Profile.model_validate(data)
            assert profile.match.type in ("any", "criteria")

    def test_nenhum_preset_de_fabrica_ficou_inalcancavel(self) -> None:
        """O defeito do R-12 era um preset que NUNCA casava — e ele volta calado."""
        arquivos = sorted(ASSETS_DIR.glob("*.json"))
        assert arquivos, "presets de fábrica sumiram do repositório"
        for path in arquivos:
            profile = Profile.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
            match = profile.match
            if isinstance(match, MatchAny):
                continue
            assert isinstance(match, MatchCriteria)
            assert (
                match.window_class
                or match.window_title_regex
                or match.process_name
            ), (
                f"{path.name}: `criteria` com os três campos vazios — "
                "`matches()` devolve False sem condição alguma, e o autoswitch "
                "NUNCA escolhe este preset. Foi assim que o `coop_local` de "
                "fábrica passou meses inalcançável."
            )

    def test_json_v1_sem_o_tipo_novo_nao_mudou_de_significado(self) -> None:
        """`any` e `criteria` gravados antes desta mudança leem igual."""
        any_ = Profile.model_validate({"name": "f", "match": {"type": "any"}})
        crit = Profile.model_validate(
            {
                "name": "n",
                "match": {"type": "criteria", "window_class": ["firefox"]},
            }
        )
        assert isinstance(any_.match, MatchAny)
        assert isinstance(crit.match, MatchCriteria)
        assert crit.matches({"wm_class": "firefox"}) is True
