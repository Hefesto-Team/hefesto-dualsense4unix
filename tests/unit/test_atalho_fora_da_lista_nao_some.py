"""ATALHO-FORA-DA-LISTA-01 — um gesto na aba apagava três atalhos do perfil.

Medido em 24/08/2026 (sprint NAVEGAÇÃO — UM CONTROLE SÓ-01, §2.1) com o código
de produto de verdade e o `point_and_click.json` dela lido do disco:

    no DISCO: ['create', 'l1', 'options', 'r1', 'touchpad_left_press',
               'touchpad_middle_press', 'touchpad_right_press']
    na TELA : ['l1', 'r1', 'options', 'create']
    no DRAFT depois de UM gesto: ['create', 'l1', 'options', 'r1']
    PERDIDOS: ['touchpad_left_press', 'touchpad_middle_press',
               'touchpad_right_press']

As duas metades do defeito, e cada uma tem o seu teste aqui:

1. `_persist_key_bindings_to_draft` escrevia a lista da TELA por cima do
   rascunho, e a lista só tem linha para botão de `CANONICAL_BUTTONS` — o que
   não aparece era descartado no primeiro "Adicionar"/"Remover"/edição de
   célula. O rodapé "Salvar Perfil" gravava o rascunho podado por cima do
   arquivo dela;
2. nada na tela dizia que aqueles três existiam, então a falta não tinha como
   ser notada.

A perda é de CONFIGURAÇÃO GRAVADA, não de comportamento vivo: desde 09/08 o
touchpad é ponteiro do sistema e as três regiões não disparam tecla nenhuma
(`daemon/subsystems/keyboard._combine_with_touchpad`). Isso não a torna
aceitável — é o único registro do que ela escolheu.

Estes testes MORDEM: arrancar a fusão faz o primeiro reprovar nomeando as três
chaves; arrancar a frase faz o último reprovar.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi` — o stub que outro
# arquivo planta em `sys.modules` passaria pelo `importorskip` e derrubaria a
# coleta (mesma disciplina de `test_o_teclado_que_nao_digita.py`).
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

#: O perfil dela, campo a campo — os quatro canônicos e as três regiões. Os
#: tokens são os que o arquivo guarda (`E`, `U`, `P` do Grim Fandango nas
#: regiões); o que importa aqui é a CHAVE sobreviver, não a tecla.
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


# --- 1. o gesto para de apagar o que a aba não mostra (N1) ---------------


def test_o_gesto_na_aba_nao_apaga_os_atalhos_do_touchpad() -> None:
    """O repro da §2.1, com o produto: sete no disco, sete no rascunho."""
    host = _host(dict(PERFIL_DELA))
    host._refresh_key_bindings_from_draft()

    na_tela = [row[0] for row in host._key_bindings_store.rows]
    assert set(na_tela) == {"l1", "r1", "options", "create"}, (
        "a lista da aba mudou de conteúdo — o teste mede a perda ENTRE a tela e "
        f"o rascunho, e precisa saber o que a tela mostra: {na_tela}"
    )

    host._persist_key_bindings_to_draft()  # é o que TODO gesto da aba faz

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
    """A fusão preserva o que a tela não mostra, nunca o que ela removeu.

    Sem esta régua, "fundir" viraria "nada nunca sai" — e o botão "Remover" da
    aba deixaria de ter efeito, trocando uma perda silenciosa por uma recusa
    silenciosa.
    """
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
    """`key_bindings=None` herda os defaults — e eles TÊM as três regiões.

    É o caminho de quem nunca editou nada: o primeiro "Adicionar" congelava o
    rascunho como override explícito, e o override nascia sem as três.
    """
    assert set(REGIOES_DO_TOUCHPAD) <= set(DEFAULT_BUTTON_BINDINGS), (
        "os defaults perderam as regiões do touchpad — se isso foi de propósito, "
        "este teste e a frase da legenda caducaram juntos"
    )
    host = _host(None)
    host._refresh_key_bindings_from_draft()
    host._key_bindings_store.append(["cross", "KEY_SPACE"])  # o "Adicionar"
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


# --- 2. a tela passa a dizer que eles existem (N2) -----------------------


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
