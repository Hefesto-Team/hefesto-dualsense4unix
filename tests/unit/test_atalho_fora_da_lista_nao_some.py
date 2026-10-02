"""ATALHO-FORA-DA-LISTA-01 — um gesto na aba apagava três atalhos do perfil."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("atalho fora da lista")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.input_actions import (
    BINDINGS_LEGEND,
    CANONICAL_BUTTONS,
    REGIOES_DO_TOUCHPAD,
    InputActionsMixin,
    frase_dos_atalhos_fora_da_lista,
)
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

PERFIL_DELA: dict[str, list[str]] = {
    "l1": ["KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"],
    "r1": ["KEY_LEFTALT", "KEY_TAB"],
    "options": ["KEY_LEFTMETA"],
    "create": ["KEY_SYSRQ"],
    "touchpad_left_press": ["KEY_E"],
    "touchpad_middle_press": ["KEY_U"],
    "touchpad_right_press": ["KEY_P"],
}


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _FakeListStore:
    """ListStore de mentira com a superfície que o mixin usa de verdade."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append(self, row: list[str]) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows.clear()

    def __iter__(self) -> Any:
        return iter(self.rows)


class _FakeMixin:
    """Mixin por composição — o produto de verdade, sem montar janela GTK."""

    def __init__(self, key_bindings: dict[str, list[str]] | None) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default().model_copy(
            update={"key_bindings": key_bindings}
        )
        self._key_bindings_store = _FakeListStore()
        self.legend = _FakeLabel()

    def _get(self, key: str) -> Any:
        return self.legend if key == "key_bindings_legend" else None


def _host(key_bindings: dict[str, list[str]] | None) -> Any:
    """Instância com os métodos REAIS do `InputActionsMixin` amarrados."""
    instance = _FakeMixin(key_bindings)
    for name in (
        "_resolve_effective_bindings",
        "_refresh_key_bindings_from_draft",
        "_atualizar_legenda",
        "_persist_key_bindings_to_draft",
    ):
        setattr(
            instance,
            name,
            InputActionsMixin.__dict__[name].__get__(instance, type(instance)),
        )
    return instance


def test_o_gesto_na_aba_nao_apaga_os_atalhos_do_touchpad() -> None:
    """O repro da §2.1, com o produto: sete no disco, sete no rascunho."""
    host = _host(dict(PERFIL_DELA))
    host._refresh_key_bindings_from_draft()

    na_tela = [row[0] for row in host._key_bindings_store.rows]
    assert set(na_tela) == {"l1", "r1", "options", "create"}, (
        "a lista da aba mudou de conteúdo — o teste mede a perda ENTRE a tela e "
        f"o rascunho, e precisa saber o que a tela mostra: {na_tela}"
    )

    host._persist_key_bindings_to_draft()

    perdidos = sorted(set(PERFIL_DELA) - set(host.draft.key_bindings or {}))
    assert perdidos == [], (
        "um gesto na aba apagou atalho que o perfil dela guardava e a lista "
        f"nunca mostrou: {perdidos}"
    )
    for chave in REGIOES_DO_TOUCHPAD:
        assert host.draft.key_bindings[chave] == PERFIL_DELA[chave], (
            f"o atalho de {chave} sobreviveu com a tecla TROCADA — preservar a "
            "chave e perder o valor é a mesma perda com outro nome"
        )


def test_remover_uma_linha_continua_removendo() -> None:
    """A fusão preserva o que a tela não mostra, nunca o que ela removeu."""
    host = _host(dict(PERFIL_DELA))
    host._refresh_key_bindings_from_draft()
    host._key_bindings_store.rows = [
        row for row in host._key_bindings_store.rows if row[0] != "r1"
    ]
    host._persist_key_bindings_to_draft()

    gravado = host.draft.key_bindings or {}
    assert "r1" not in gravado, "o Remover dela foi desfeito pela fusão"
    assert set(REGIOES_DO_TOUCHPAD) <= set(gravado), (
        "remover um botão canônico levou junto o que a lista nem mostrava"
    )


def test_rascunho_que_herda_de_fabrica_nao_perde_o_touchpad() -> None:
    """`key_bindings=None` herda os defaults — e eles TÊM as três regiões."""
    assert set(REGIOES_DO_TOUCHPAD) <= set(DEFAULT_BUTTON_BINDINGS), (
        "os defaults perderam as regiões do touchpad — se isso foi de propósito, "
        "este teste e a frase da legenda caducaram juntos"
    )
    host = _host(None)
    host._refresh_key_bindings_from_draft()
    host._key_bindings_store.append(["cross", "KEY_SPACE"])
    host._persist_key_bindings_to_draft()

    gravado = host.draft.key_bindings or {}
    assert set(REGIOES_DO_TOUCHPAD) <= set(gravado), (
        "o primeiro gesto num rascunho de fábrica podou as regiões do touchpad"
    )
    assert gravado["cross"] == ["KEY_SPACE"], "o botão adicionado não foi gravado"


def test_teclado_silencioso_continua_silencioso() -> None:
    """`key_bindings == {}` é escolha legítima e a fusão não a desfaz."""
    host = _host({})
    host._refresh_key_bindings_from_draft()
    host._persist_key_bindings_to_draft()
    assert host.draft.key_bindings is None, (
        "a fusão ressuscitou atalhos num teclado que ela silenciou de propósito"
    )


def test_a_frase_nomeia_os_tres_e_diz_o_motivo() -> None:
    frase = frase_dos_atalhos_fora_da_lista(
        {chave: tuple(tokens) for chave, tokens in PERFIL_DELA.items()}
    )
    assert "Touchpad — lado esquerdo" in frase
    assert "Touchpad — meio" in frase
    assert "Touchpad — lado direito" in frase
    assert "mouse do computador" in frase, (
        "a frase nomeia os atalhos e não diz POR QUE eles não disparam — é "
        "metade da resposta, e a metade que não resolve"
    )
    assert "l1" not in frase and "L1" not in frase, (
        "a frase citou um botão que TEM linha na lista"
    )


def test_a_frase_cala_quando_nao_ha_nada_fora_da_lista() -> None:
    so_canonicos = {botao: ("KEY_SPACE",) for botao in CANONICAL_BUTTONS}
    assert frase_dos_atalhos_fora_da_lista(so_canonicos) == "", (
        "linha vazia na tela é pior que silêncio"
    )


def test_o_refresh_pinta_a_frase_na_legenda() -> None:
    """O caminho real (refresh do rascunho) chega à tela, não só a função pura."""
    host = _host(dict(PERFIL_DELA))
    host._refresh_key_bindings_from_draft()
    assert BINDINGS_LEGEND in host.legend.markup
    assert "Guardados, sem linha na lista" in host.legend.markup
    assert "Touchpad — meio" in host.legend.markup
