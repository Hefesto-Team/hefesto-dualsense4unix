"""ESCOLHA-DELA-VENCE-01 — a máscara do perfil, e o preço do Xbox onde ela escolhe.

Pedido dela, literal, em 01/08/2026:

    "o que eu quero é que minha escolha aqui prevaleça sempre. E ao deixar o
     mouse sobre a opção Xbox, ele falaria que o Xbox não tem tais features.
     Mas em todos eu poderia escolher Hefesto ou Sony pra usar e tirar proveito
     de tudo."

Esta é a família *"a config que eu deixo nunca é respeitada"*, que esta casa já
pagou uma vez — três escritores do perfil sem dono.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# E1 — `null` continua sendo `null` (o defeito 1, que não tinha teste)
# ---------------------------------------------------------------------------


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
    """O defeito mais grave da sprint, e o que NENHUM teste pegava.

    Um perfil pode dizer `{"kind": "gamepad", "gamepad_flavor": null}`, e
    `null` significa, no applier, **"mantém a máscara atual"**. O editor
    convertia isso em `"xbox"` nas DUAS pontas — ao abrir e ao salvar.

    O efeito para ela: abrir um perfil que não tinha opinião sobre máscara,
    salvar qualquer outra coisa nele (a cor, o gatilho, o nome), e o perfil
    passar a **EXIGIR Xbox** — apagando giroscópio e touchpad naquele jogo.
    Ela nunca pediu isso.

    Mordida: devolver o `or "xbox"` ao `_mode_section_from_editor`.
    """
    editor = _editor_com("gamepad", None)

    secao = editor._mode_section_from_editor()

    assert secao == {"kind": "gamepad", "gamepad_flavor": None}, (
        "sem botão marcado, o perfil grava `null` — que é 'mantém a atual', e "
        "é o que estava no disco"
    )


def test_a_mascara_escolhida_sobrevive_ao_salvar() -> None:
    """E o caso normal continua inteiro: escolha dela = escolha gravada.

    Mordida: trocar o `get_active_id()` por um literal.
    """
    for sabor in ("dualsense", "xbox"):
        editor = _editor_com("gamepad", sabor)
        assert editor._mode_section_from_editor() == {
            "kind": "gamepad",
            "gamepad_flavor": sabor,
        }


def test_abrir_um_perfil_sem_mascara_nao_marca_botao_nenhum() -> None:
    """A outra ponta do mesmo defeito: o POPULATE.

    Mostrar "Xbox 360" marcado num perfil que diz `null` é a tela afirmando
    uma escolha que ninguém fez — e é o que fazia o próximo "salvar" gravar
    Xbox de verdade.

    Das duas saídas que a sprint desenhou, esta é a recomendada: o seletor
    fica **sem nenhum ativo**, em vez de ganhar um terceiro botão
    "— manter a atual".

    Mordida: devolver o `or "xbox"` ao `_set_mode_editor`.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    editor = _editor_com("gamepad", "xbox")
    editor._set_mode_editor(
        ProfileModeConfig(kind="gamepad", gamepad_flavor=None)
    )

    assert editor._mode_flavor_selector.get_active_id() is None
    # E o `_modo_tocado` fica BAIXO: isto foi populate, não gesto dela.
    assert editor._modo_tocado is False


# ---------------------------------------------------------------------------
# E4 — o preço do Xbox aparece onde ela escolhe
# ---------------------------------------------------------------------------


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

    # E a idempotência do `set_items` continua de pé — é ela que impede o
    # seletor de se reconstruir a cada tique e perder o botão marcado.
    depois.set_active_id("xbox")
    depois.set_items([("dualsense", "DualSense"), ("xbox", "Xbox 360")])
    assert depois.get_active_id() == "xbox"


def test_o_preco_do_xbox_e_o_texto_que_ja_existia() -> None:
    """Reuso, não segundo texto.

    A frase foi escrita e testada na MASCARA-CUSTO-01 e vivia só na aba
    Início — que não é onde ela escolhe por jogo. Dois donos da mesma frase
    derivam, e esta casa tem a regra escrita.

    Mordida: escrever um texto novo no editor de perfis.
    """
    assert texto_do_custo_da_mascara("xbox") == TEXTO_CUSTO_MASCARA_XBOX
    assert "giroscópio" in TEXTO_CUSTO_MASCARA_XBOX
    assert "touchpad" in TEXTO_CUSTO_MASCARA_XBOX
    # E o que CONTINUA funcionando também é dito — a frase não é só alarme.
    assert "Vibração" in TEXTO_CUSTO_MASCARA_XBOX

    # DualSense não tem preço: nada se perde, e inventar um aviso ali seria a
    # mesma família de erro que o `or "xbox"` que a E1 removeu.
    assert texto_do_custo_da_mascara("dualsense") == ""
    assert texto_do_custo_da_mascara(None) == ""


def test_o_editor_de_perfis_poe_o_preco_no_botao_do_xbox() -> None:
    """O pedido dela, verificado no ponto de montagem.

    Mordida: apagar o `set_tooltips` do `_build_mode_editor`.
    """
    import inspect

    from hefesto_dualsense4unix.app.actions import profiles_actions

    fonte = inspect.getsource(profiles_actions)
    assert "flavor_sel.set_tooltips(" in fonte
    assert "texto_do_custo_da_mascara(sabor)" in fonte, (
        "a dica tem de vir da função pura, não de um texto novo"
    )
