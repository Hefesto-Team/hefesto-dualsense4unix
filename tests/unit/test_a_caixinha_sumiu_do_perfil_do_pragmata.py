"""A caixinha do Steam Input sumiu do perfil do Pragmata — 10/08/2026."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a caixinha que sumiu do perfil do Pragmata")

import json
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")


from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    detect_simple_preset,
    from_simple_choice,
    simple_extra,
)

APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"
EXE_DO_JOGO = "PRAGMATA.exe"

OUTRO_APPID = "1599660"

CABECALHO = (
    "# hefesto-dualsense4unix — allowlist do Steam Input per-app\n"
    "# (STEAM-INPUT-ALLOWLIST-01)\n"
    "#\n"
    "# Uma linha por AppID; '#' comenta.\n"
)


def _match_dela() -> MatchCriteria:
    """O match como está no disco dela — os dois campos, na mesma ordem."""
    return MatchCriteria(window_class=[WM_JOGO], process_name=[EXE_DO_JOGO])


def _perfil_dela() -> Profile:
    return Profile(name="Pragmata", match=_match_dela(), priority=85)


class TestOPerfilDelaVoltaAoEditorSimples:
    def test_o_match_real_dela_e_um_jogo_da_steam(self) -> None:
        """O que estava devolvendo None, e por isso escondia a caixinha."""
        assert detect_simple_preset(_match_dela()) == "steam_game", (
            "o perfil do jogo dela abria no editor AVANÇADO, e com ele o "
            "seletor rebaixado a 'Vale sempre' — que é onde a caixinha morre"
        )
        assert simple_extra(_match_dela()) == APPID, (
            "sem o número no campo, a caixinha não sabe de qual jogo fala "
            "(`_appid_do_editor` devolve None) e nasce insensível"
        )

    def test_regex_de_titulo_junto_continua_fora_do_editor_simples(self) -> None:
        """A metade da decisão de 23/07 que NÃO caducou."""
        m = MatchCriteria(window_class=[WM_JOGO], window_title_regex="PRAGMATA")
        assert detect_simple_preset(m) is None
        assert simple_extra(m) == ""

    def test_regex_e_processo_juntos_tambem_ficam_no_avancado(self) -> None:
        """A recusa é do regex, e não some porque há um `process_name` junto."""
        m = MatchCriteria(
            window_class=[WM_JOGO],
            window_title_regex="PRAGMATA",
            process_name=[EXE_DO_JOGO],
        )
        assert detect_simple_preset(m) is None

    def test_duas_janelas_continuam_sendo_regra_complexa(self) -> None:
        """`window_class` com dois nomes não é "um jogo da Steam" — nunca foi."""
        m = MatchCriteria(
            window_class=[WM_JOGO, f"steam_app_{OUTRO_APPID}"],
            process_name=[EXE_DO_JOGO],
        )
        assert detect_simple_preset(m) is None


class TestOProcessNameSobreviveAoRoundTrip:
    def test_o_programa_do_jogo_nao_evapora_ao_salvar(self, tmp_path: Path) -> None:
        """Abrir no simples e salvar não pode tirar o campo que a tela não mostra."""
        disco = _match_dela()
        novo = from_simple_choice("steam_game", custom_name=APPID, regra_do_disco=disco)

        caminho = tmp_path / "pragmata.json"
        perfil = Profile(name="Pragmata", match=novo, priority=85)
        caminho.write_text(
            json.dumps(perfil.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        relido = Profile.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

        assert isinstance(relido.match, MatchCriteria)
        assert relido.match.window_class == [WM_JOGO]
        assert relido.match.process_name == [EXE_DO_JOGO], (
            "o editor simples apagou um campo da regra dela sem ela pedir"
        )
        assert detect_simple_preset(relido.match) == "steam_game", (
            "o segundo round-trip tem de fechar igual ao primeiro"
        )

    def test_trocar_o_numero_troca_de_jogo_e_nao_herda_o_programa(self) -> None:
        """Outro appid é OUTRO jogo — herdar o `PRAGMATA.exe` seria pior que apagar."""
        novo = from_simple_choice(
            "steam_game", custom_name=OUTRO_APPID, regra_do_disco=_match_dela()
        )
        assert isinstance(novo, MatchCriteria)
        assert novo.window_class == [f"steam_app_{OUTRO_APPID}"]
        assert novo.process_name == []

    def test_regra_do_disco_que_nao_e_jogo_nao_empresta_nada(self) -> None:
        for regra in (MatchAny(), MatchCriteria(process_name=["steam"]), None):
            novo = from_simple_choice("steam_game", custom_name=APPID, regra_do_disco=regra)
            assert isinstance(novo, MatchCriteria)
            assert novo.process_name == [], f"regra {regra!r} não devia emprestar nada"

    def test_sem_regra_do_disco_o_contrato_historico_nao_muda(self) -> None:
        """Chamador antigo (CLI, testes, duplicação) segue gravando só a janela."""
        novo = from_simple_choice("steam_game", custom_name=APPID)
        assert isinstance(novo, MatchCriteria)
        assert novo.window_class == [WM_JOGO]
        assert novo.process_name == []

