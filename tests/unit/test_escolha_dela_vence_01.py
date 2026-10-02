"""ESCOLHA-DELA-VENCE-01 — a máscara do perfil, e o preço do Xbox onde ela escolhe."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_escolha_dela_vence_01: importa código da janela GTK")

from typing import Any


class _Selector:
    """O dublê mínimo de seletor que o editor usa."""

    def __init__(self, ativo: str | None = None) -> None:
        self._active_id = ativo
        self.dicas: dict[str, str] = {}

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        self._active_id = the_id

    def limpar_ativo(self) -> None:
        self._active_id = None

    def set_tooltips(self, dicas: dict[str, str]) -> None:
        self.dicas = dict(dicas)


def _editor_com(kind: str, flavor: str | None) -> Any:
    """Um editor mínimo com os dois seletores de modo montados."""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    class _Editor(ProfilesActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self._mode_kind_selector = _Selector(kind)
            self._mode_flavor_selector = _Selector(flavor)

    return _Editor()


def test_o_editor_de_perfis_poe_o_preco_no_botao_do_xbox() -> None:
    """O pedido dela, verificado no ponto de montagem."""
    import inspect

    from hefesto_dualsense4unix.app.actions import profiles_actions

    fonte = inspect.getsource(profiles_actions)
    assert "flavor_sel.set_tooltips(" in fonte
    assert "texto_do_custo_da_mascara(sabor)" in fonte, (
        "a dica tem de vir da função pura, não de um texto novo"
    )
