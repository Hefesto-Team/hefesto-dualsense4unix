"""R-12 (auditoria 23/07) — o editor simples não sabia dizer "jogo da Steam".

Três defeitos que se somam na queixa (1) ("o perfil do jogo NUNCA é respeitado"):

1. **Não havia como criar a regra certa.** A única opção com alvo próprio era
   "Jogo específico", que grava `process_name` — o basename de `/proc/PID/exe`.
   Em jogo Proton isso é o binário do wine, e sob XWayland a única chave
   confiável do jogo é a `wm_class` `steam_app_<appid>` — que também é a
   chave do `.env` por appid do launch_env e a ÚNICA que
   `perfil_e_regra_de_jogo` (R-01) aceita como regra de jogo.

2. **Degradação em silêncio.** "Jogo específico" com o campo vazio devolvia
   `MatchAny()`: o perfil criado PARA UM JOGO nascia valendo para TUDO, virava
   mais um catch-all na disputa (R-01) e o toast dizia "Perfil salvo".

3. **`.lower()` no helper contra basename cru no matcher.** O que ela digitasse
   ("EldenRing") era gravado em minúsculas e nunca casava com o executável
   real. Coberto em `test_simple_match.py` / `test_profile_editor_roundtrip.py`,
   onde os testes antigos CONGELAVAM o defeito.

E o preset de fábrica `coop_local`, que tinha `criteria` 100% vazio —
`MatchCriteria.matches` devolve `False` sem condição alguma (schema.py:52),
então ele era INALCANÇÁVEL pelo autoswitch, e a coluna "Quando usar" mentia
dizendo "Só neste programa".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.simple_match import (
    detect_simple_preset,
    from_simple_choice,
    normalize_appid,
    simple_extra,
)

#: Appid do Mullet Mad Jack — o jogo da queixa, que não tem perfil nenhum.
MMJ = "2111190"


class TestJogoDaSteam:
    def test_appid_puro_vira_window_class(self) -> None:
        m = from_simple_choice("steam_game", custom_name=MMJ)
        assert isinstance(m, MatchCriteria)
        assert m.window_class == [f"steam_app_{MMJ}"]
        assert not m.process_name and m.window_title_regex is None

    def test_aceita_a_wm_class_inteira_colada_do_journal(self) -> None:
        m = from_simple_choice("steam_game", custom_name=f"  steam_app_{MMJ} ")
        assert isinstance(m, MatchCriteria)
        assert m.window_class == [f"steam_app_{MMJ}"]

    def test_a_regra_casa_com_a_janela_do_jogo(self) -> None:
        m = from_simple_choice("steam_game", custom_name=MMJ)
        assert m.matches({"wm_class": f"steam_app_{MMJ}"})
        assert not m.matches({"wm_class": "firefox"})

    def test_e_regra_de_jogo_para_o_autoswitch(self) -> None:
        """R-01: só `window_class` com a `steam_app_<id>` em foco conta."""
        from hefesto_dualsense4unix.profiles.schema import perfil_e_regra_de_jogo

        p = Profile(
            name="MadJack",
            match=from_simple_choice("steam_game", custom_name=MMJ),
            priority=70,
        )
        info = {"wm_class": f"steam_app_{MMJ}"}
        assert perfil_e_regra_de_jogo(p, info)
        assert not p.e_catch_all

    def test_sem_appid_levanta_com_frase_de_gente(self) -> None:
        with pytest.raises(ValueError, match="número do jogo na Steam"):
            from_simple_choice("steam_game", custom_name=None)

    def test_appid_com_letras_levanta(self) -> None:
        with pytest.raises(ValueError, match="só dígitos"):
            from_simple_choice("steam_game", custom_name="sackboy")

    def test_normalize_appid(self) -> None:
        assert normalize_appid("1599660") == "1599660"
        assert normalize_appid("steam_app_1599660") == "1599660"
        assert normalize_appid("STEAM_APP_1599660") == "1599660"
        assert normalize_appid("") is None
        assert normalize_appid(None) is None
        assert normalize_appid("1599660 e mais") is None


class TestRoundTripDoEditor:
    def test_detecta_e_devolve_o_appid_no_campo_livre(self) -> None:
        m = from_simple_choice("steam_game", custom_name=MMJ)
        assert detect_simple_preset(m) == "steam_game"
        assert simple_extra(m) == MMJ, (
            "o campo pede o NÚMERO — devolver 'steam_app_2111190' faria o "
            "próximo Salvar gravar 'steam_app_steam_app_2111190'"
        )

    def test_game_continua_devolvendo_o_nome_do_programa(self) -> None:
        m = from_simple_choice("game", custom_name="EldenRing")
        assert detect_simple_preset(m) == "game"
        assert simple_extra(m) == "EldenRing"

    def test_steam_app_com_regex_junto_nao_e_editor_simples(self) -> None:
        """`matches` é AND: com regex junto o perfil significa outra coisa."""
        m = MatchCriteria(
            window_class=[f"steam_app_{MMJ}"], window_title_regex="Mullet"
        )
        assert detect_simple_preset(m) is None
        assert simple_extra(m) == ""

    def test_leitura_de_criterio_vazio_continua_tolerante(self) -> None:
        """Risco de regressão anotado no plano: recusar na LEITURA quebraria
        perfis já salvos (o `coop_local` de quem não migrou)."""
        assert detect_simple_preset(MatchCriteria()) is None
        assert detect_simple_preset(MatchAny()) == "any"


class TestColunaQuandoUsar:
    """R-12 item 5: a coluna tem de admitir que o perfil nunca entra sozinho."""

    def test_criteria_vazio_diz_so_manual(self) -> None:
        pytest.importorskip("gi")
        from hefesto_dualsense4unix.app.actions.profiles_actions import (
            LABEL_SO_MANUAL,
            _match_label,
        )

        assert _match_label(MatchCriteria()) == LABEL_SO_MANUAL
        assert "nunca ativa sozinho" in LABEL_SO_MANUAL

    def test_criteria_com_alvo_e_any_seguem_como_antes(self) -> None:
        pytest.importorskip("gi")
        from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

        assert _match_label(MatchCriteria(window_class=["firefox"])) == (
            "Só neste programa"
        )
        assert _match_label(MatchAny()) == "Sempre"

    def test_contrato_antigo_por_string_preservado(self) -> None:
        """A função também é chamada com o discriminador cru (testes de
        vocabulário e qualquer perfil de versão futura)."""
        pytest.importorskip("gi")
        from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

        assert _match_label("any") == "Sempre"
        assert _match_label("criteria") == "Só neste programa"
        assert _match_label("regex_do_futuro") == "regex_do_futuro"


class TestPresetCoopLocalDeFabrica:
    """O preset tinha alvo VAZIO — nunca casava com janela nenhuma."""

    @staticmethod
    def _asset() -> Profile:
        caminho = (
            Path(__file__).resolve().parents[2]
            / "assets/profiles_default/coop_local.json"
        )
        return Profile.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

    def test_tem_alvo_de_verdade(self) -> None:
        p = self._asset()
        assert isinstance(p.match, MatchCriteria)
        assert p.match.window_title_regex, (
            "com criteria vazio o preset é inalcançável pelo autoswitch — foi "
            "assim que ele passou meses no disco sem nunca entrar"
        )

    def test_nao_virou_catch_all(self) -> None:
        """Contradição 12 do plano: mais um catch-all agravaria R-01."""
        p = self._asset()
        assert not isinstance(p.match, MatchAny)
        assert not p.e_catch_all
        assert not p.matches({"wm_class": "firefox", "wm_name": "Firefox"})

    def test_casa_com_jogo_de_coop_pelo_titulo(self) -> None:
        p = self._asset()
        assert p.matches({"wm_name": "Overcooked! 2"})
        assert p.matches({"wm_name": "Sackboy: A Big Adventure"})

    def test_perde_para_o_perfil_do_proprio_jogo(self) -> None:
        """`sackboy_nativo` (prio 80, `steam_app_1599660`) continua vencendo;
        e a prioridade fica ABAIXO da `Navegação` (50) porque o título da
        janela do CLIENTE Steam também pode citar um jogo de co-op."""
        p = self._asset()
        assert p.priority < 50
        assert p.priority < 80

    def test_o_modo_de_coop_esta_intacto(self) -> None:
        p = self._asset()
        assert p.mode is not None
        assert p.mode.kind == "gamepad" and p.mode.coop is True
        assert p.suppress_desktop_emulation is True
