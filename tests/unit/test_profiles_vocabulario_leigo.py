"""Vocabulário da aba Perfis: nada de nome de campo do schema na tela (LEIGO-06).

A coluna "Quando usar" (ex-"Match") mostrava o valor CRU de ``profile.match.type``
— literalmente ``any`` / ``criteria``, os discriminadores do schema. Eram o nome
do campo, não uma resposta à pergunta da coluna.

`_match_label` é função pura de propósito: o contrato de texto fica testável sem
GTK, e o resto do módulo (`Gtk.ListStore`) fica fora do caminho.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    _MODE_FLAVOR_ITEMS,
    _MODE_KIND_ITEMS,
    _match_label,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria


class TestMatchLabel:
    def test_any_vira_sempre(self) -> None:
        assert _match_label("any") == "Sempre"

    def test_criteria_vira_so_neste_programa(self) -> None:
        assert _match_label("criteria") == "Só neste programa"

    def test_cobre_os_tipos_que_o_schema_realmente_produz(self) -> None:
        """Se alguém acrescentar um `Match` novo, o rótulo tem de vir junto —
        senão a coluna volta a mostrar o discriminador cru."""
        for modelo in (MatchAny(), MatchCriteria()):
            rotulo = _match_label(modelo.type)
            assert rotulo != modelo.type, (
                f"{modelo.type!r} não tem rótulo humano — a coluna 'Quando "
                f"usar' vai mostrar o valor do schema"
            )

    def test_tipo_desconhecido_nao_apaga_a_celula(self) -> None:
        """Perfil de uma versão mais nova: melhor um texto estranho do que uma
        célula vazia (que a usuária leria como perfil quebrado)."""
        assert _match_label("regex_do_futuro") == "regex_do_futuro"


class TestRotulosDoEditorDeModo:
    def test_sem_opiniao_nao_esta_mais_na_tela(self) -> None:
        """"Sem opinião" era o programa se descrevendo por dentro (o perfil sem
        a seção `mode`) — o id `none` continua, o rótulo é que mudou."""
        rotulos = dict(_MODE_KIND_ITEMS)
        assert rotulos["none"] == "Não mexer no modo"
        assert "Sem opinião" not in rotulos.values()

    def test_ids_do_schema_intactos(self) -> None:
        """LEIGO-06 é só TEXTO: os ids são chaves de config e não podem mudar
        (`none` = sem a seção; os demais = ProfileModeConfig.kind)."""
        assert [i for i, _ in _MODE_KIND_ITEMS] == [
            "none",
            "desktop",
            "gamepad",
            "native",
        ]
        assert [i for i, _ in _MODE_FLAVOR_ITEMS] == ["dualsense", "xbox"]

    def test_aparencia_nao_promete_vibracao_exclusiva(self) -> None:
        """Com o vpad uhid (SPRINT-UHID-VPAD-01) as duas máscaras vibram; o
        editor não pode ressuscitar o "(sem vibrar)" que a aba Início enterrou."""
        for _id, rotulo in _MODE_FLAVOR_ITEMS:
            assert "vibra" not in rotulo.lower()
