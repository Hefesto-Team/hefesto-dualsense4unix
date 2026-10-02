"""ESCOLHA-DELA-VENCE-01 — a máscara do perfil, e o preço do Xbox onde ela escolhe."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_escolha_dela_vence_01: importa código da janela GTK")

from typing import Any

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
    texto_do_custo_da_mascara,
)
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector


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


def test_perfil_sem_opiniao_de_mascara_continua_sem_opiniao_ao_salvar() -> None:
    """O defeito mais grave da sprint, e o que NENHUM teste pegava."""
    editor = _editor_com("gamepad", None)

    secao = editor._mode_section_from_editor()

    assert secao == {"kind": "gamepad", "gamepad_flavor": None}, (
        "sem botão marcado, o perfil grava `null` — que é 'mantém a atual', e "
        "é o que estava no disco"
    )


def test_a_mascara_escolhida_sobrevive_ao_salvar() -> None:
    """E o caso normal continua inteiro: escolha dela = escolha gravada."""
    for sabor in ("dualsense", "xbox"):
        editor = _editor_com("gamepad", sabor)
        assert editor._mode_section_from_editor() == {
            "kind": "gamepad",
            "gamepad_flavor": sabor,
        }


def test_abrir_um_perfil_sem_mascara_nao_marca_botao_nenhum() -> None:
    """A outra ponta do mesmo defeito: o POPULATE."""
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    editor = _editor_com("gamepad", "xbox")
    editor._set_mode_editor(
        ProfileModeConfig(kind="gamepad", gamepad_flavor=None)
    )

    assert editor._mode_flavor_selector.get_active_id() is None
    assert editor._modo_tocado is False


def test_o_seletor_aceita_dica_por_botao_sem_mexer_na_tupla() -> None:
    """A dica é por BOTÃO, e entra por um método próprio.

    Ela NÃO entrou na tupla de `set_items`, e a decisão é de risco: a forma
    `(id, label)` é load-bearing — o comparador de idempotência
    (`if items == self._items`) e o `_index_of` desempacotam dois elementos, e
    três arquivos de teste travam a tupla. Um método separado entrega o mesmo
    e não encosta em nada disso.

    E funciona nas DUAS ordens de montagem: dica antes dos itens, e depois.

    Mordida: apagar a chamada a `_aplicar_dicas` do `set_items`.
    """
    antes = SegmentedSelector()
    antes.set_tooltips({"xbox": "o preço"})
    antes.set_items([("dualsense", "DualSense"), ("xbox", "Xbox 360")])
    assert antes._dicas == {"xbox": "o preço"}

    depois = SegmentedSelector()
    depois.set_items([("dualsense", "DualSense"), ("xbox", "Xbox 360")])
    depois.set_tooltips({"xbox": "o preço"})
    assert depois._dicas == {"xbox": "o preço"}

    depois.set_active_id("xbox")
    depois.set_items([("dualsense", "DualSense"), ("xbox", "Xbox 360")])
    assert depois.get_active_id() == "xbox"


def test_o_preco_do_xbox_e_o_texto_que_ja_existia() -> None:
    """Reuso, não segundo texto."""
    assert texto_do_custo_da_mascara("xbox") == TEXTO_CUSTO_MASCARA_XBOX
    assert "giroscópio" in TEXTO_CUSTO_MASCARA_XBOX
    assert "touchpad" in TEXTO_CUSTO_MASCARA_XBOX
    assert "Vibração" in TEXTO_CUSTO_MASCARA_XBOX

    # DualSense não tem preço: nada se perde, e inventar um aviso ali seria a
    assert texto_do_custo_da_mascara("dualsense") == ""
    assert texto_do_custo_da_mascara(None) == ""


def test_o_editor_de_perfis_poe_o_preco_no_botao_do_xbox() -> None:
    """O pedido dela, verificado no ponto de montagem."""
    import inspect

    from hefesto_dualsense4unix.app.actions import profiles_actions

    fonte = inspect.getsource(profiles_actions)
    assert "flavor_sel.set_tooltips(" in fonte
    assert "texto_do_custo_da_mascara(sabor)" in fonte, (
        "a dica tem de vir da função pura, não de um texto novo"
    )
