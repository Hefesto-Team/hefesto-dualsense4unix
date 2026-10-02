"""Vocabulário da aba Perfis: nada de nome de campo do schema na tela (LEIGO-06)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o vocabulário leigo dos perfis")

from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria


class TestMatchLabel:
    def test_any_vira_sempre(self) -> None:
        assert _match_label("any") == "Sempre"

    def test_criteria_vira_so_neste_programa(self) -> None:
        assert _match_label("criteria") == "Só neste programa"

    def test_cobre_os_tipos_que_o_schema_realmente_produz(self) -> None:
        """Se alguém acrescentar um `Match` novo, o rótulo tem de vir junto —"""
        for modelo in (MatchAny(), MatchCriteria()):
            rotulo = _match_label(modelo.type)
            assert rotulo != modelo.type, (
                f"{modelo.type!r} não tem rótulo humano — a coluna 'Quando "
                f"usar' vai mostrar o valor do schema"
            )

    def test_tipo_desconhecido_nao_apaga_a_celula(self) -> None:
        """Perfil de uma versão mais nova: melhor um texto estranho do que uma"""
        assert _match_label("regex_do_futuro") == "regex_do_futuro"


