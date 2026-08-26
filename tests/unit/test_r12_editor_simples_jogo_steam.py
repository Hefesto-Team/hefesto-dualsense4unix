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


# ---------------------------------------------------------------------------
# NOTA DATADA — 26/08/2026: `TestPresetCoopLocalDeFabrica` saiu daqui
# ---------------------------------------------------------------------------
# A classe abria `assets/profiles_default/coop_local.json` e travava cinco
# coisas sobre ele: que tinha alvo de verdade (o conserto do R-12), que NÃO
# virou catch-all, que casava por título com jogo de co-op, que a prioridade
# ficava entre a `Navegação` (50) e o perfil do próprio jogo (80) — a decisão
# do MODO-01 que superou a segunda metade do R-12 — e que o `mode: gamepad`
# com `coop: true` seguia intacto.
#
# O ARQUIVO FOI PODADO da fábrica nesta data. Palavra dela: *"em termos de
# perfis de jogo vamos manter os que temos ativos apenas"*, e nenhum dos três
# podados (`bow`, `coop_local`, `sackboy_nativo`) estava ativo no disco dela —
# os três já estavam no `.historico/`. Um teste que abre um arquivo apagado
# não mede coisa alguma; ele só reprova.
#
# O QUE NÃO SE PERDE, e onde está agora — porque decisão medida não se apaga:
#
#   - a família de defeito ("preset de fábrica que o autoswitch nunca escolhe")
#     virou régua sobre a fábrica INTEIRA em
#     `test_match_sem_caixa_e_sentinel_manual.py`, que é MAIS do que esta
#     classe media;  # noqa: acentuacao — verbo medir no imperfeito, não o substantivo
#   - a ordem de prioridades (gênero 55-70 < jogo 80) e o porquê dela estão em
#     `profiles/loader.py`, na nota de `PRIORIDADE_DO_PERFIL_DE_JOGO`;
#   - a decisão do MODO-01 sobre a prioridade do co-op está na sprint
#     `docs/process/sprints/2026-07-25-MODO-01-o-modo-jogo-liga-sozinho.md`.
#
# As duas migrações que dependiam deste asset foram APOSENTADAS no mesmo
# commit, e não caladas: `profiles/loader.py` relata
# `migracao_aposentada_sem_asset` quando encontra um `coop_local` velho no
# disco sem asset de onde copiar. A mordida disso é
# `test_a_migracao_aposentada_nao_e_muda`, em `test_profile_loader.py`.
