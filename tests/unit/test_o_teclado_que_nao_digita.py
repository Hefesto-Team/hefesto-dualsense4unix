"""TECLADO-QUE-NAO-DIGITA-01 — a aba passa a dizer o que NÃO digita.

O relato dela, 09/08/2026, depois de ligar "Controlar o PC", ligar o mouse
(funcionou: o analógico move o cursor) e ligar o teclado emulado:

    *"o botão emular teclado não funciona"*

O journal do daemon dela contradiz o "não funciona" no motor: o teclado virtual
subiu (`keyboard_emulator_opened`), despachou e emitiu 34 teclas entre 23:52:05
e 23:52:37 — Delete e Enter das regiões do touchpad, Alt+Tab do R1, Alt+Shift+
Tab do L1. O que não existia era a TELA dizendo a verdade sobre o mapa:

1. a lista da aba só cria linha para botão COM tecla, então os onze botões sem
   tecla (X, Círculo, Triângulo, Quadrado, os quatro direcionais, L2, R2, PS)
   simplesmente NÃO APARECEM — a lista parece completa, e apertá-los esperando
   que digitem é a conclusão natural, e errada;
2. nenhum atalho de fábrica digita um CARACTERE: são Super, PrintScreen,
   Alt+Tab, Alt+Shift+Tab, Backspace, Enter, Delete e os dois tokens do teclado
   na tela. "O teclado emulado não digita" é literalmente verdade de fábrica, e
   a legenda dizia o contrário ("cada botão do controle pode digitar uma tecla").

Estes testes MORDEM: cada um reprova se a frase correspondente for arrancada.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, pelo mesmo motivo
# declarado em `test_input_actions.py` — o stub que outro arquivo planta em
# `sys.modules` passaria pelo `importorskip` e derrubaria a coleta.
exigir_gi_real("teclado que não digita")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.input_actions import (
    BINDINGS_LEGEND,
    BOTOES_JA_DO_MOUSE,
    CANONICAL_BUTTONS,
    InputActionsMixin,
    frase_dos_botoes_sem_tecla,
)
from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    is_virtual_token,
)

#: Teclas que produzem um CARACTERE visível ao digitar. Se algum default passar
#: a incluir uma destas, a promessa da legenda ("nenhum atalho de fábrica digita
#: letra") caduca e tem de ser reescrita junto — é para isso que o teste existe.
_TECLAS_QUE_DIGITAM: frozenset[str] = frozenset(
    [f"KEY_{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    + [f"KEY_{d}" for d in "0123456789"]
    + ["KEY_SPACE", "KEY_COMMA", "KEY_DOT"]
)


# --- o fato que a legenda afirma ---------------------------------------


def test_nenhum_atalho_de_fabrica_digita_caractere() -> None:
    """A frase "nenhum atalho de fábrica digita letra" é verificável, não retórica.

    Guarda a AFIRMAÇÃO da tela, não o mapa: quem quiser pôr uma letra num
    default pode — mas reprova aqui, e a legenda tem de mudar no mesmo commit.
    """
    digitam = {
        botao: tokens
        for botao, tokens in DEFAULT_BUTTON_BINDINGS.items()
        if any(token in _TECLAS_QUE_DIGITAM for token in tokens)
    }
    assert digitam == {}, (
        "algum binding de fábrica passou a digitar caractere — a legenda da aba "
        f"ainda promete o contrário: {digitam}"
    )


def test_o_unico_caminho_de_fabrica_para_escrever_e_o_teclado_na_tela() -> None:
    """Só l3/r3 usam token virtual — é o teclado na tela, e ele é externo."""
    virtuais = {
        botao
        for botao, tokens in DEFAULT_BUTTON_BINDINGS.items()
        if any(is_virtual_token(token) for token in tokens)
    }
    assert virtuais == {"l3", "r3"}
    assert "teclado na tela" in BINDINGS_LEGEND
    assert "onboard" in BINDINGS_LEGEND
    assert "wvkbd-mobintl" in BINDINGS_LEGEND


# --- a frase que nomeia o que não digita -------------------------------


def test_a_frase_nomeia_os_botoes_sem_tecla_dos_defaults() -> None:
    """Com o mapa de fábrica, os onze órfãos aparecem pelo nome humano."""
    frase = frase_dos_botoes_sem_tecla(dict(DEFAULT_BUTTON_BINDINGS))
    for esperado in ("X (Cruz)", "Círculo", "Triângulo", "Quadrado", "Botão PS"):
        assert esperado in frase, f"{esperado!r} sumiu da frase: {frase!r}"
    # Quem TEM tecla no mapa de fábrica não entra na lista de órfãos.
    assert "L1" not in frase
    assert "Options" not in frase
    assert "Touchpad" not in frase


def test_a_frase_avisa_que_o_botao_ja_e_do_mouse() -> None:
    """Dois donos do mesmo botão: a tela passa a dizer antes, não depois."""
    frase = frase_dos_botoes_sem_tecla(dict(DEFAULT_BUTTON_BINDINGS))
    assert "já são do mouse" in frase
    assert "as duas coisas ao mesmo tempo" in frase


def test_a_frase_diz_o_que_fazer_quando_tudo_esta_mudo() -> None:
    """`key_bindings == {}` era lista vazia sem uma palavra — parecia defeito."""
    frase = frase_dos_botoes_sem_tecla({})
    assert "nenhum botão digita nada agora" in frase
    assert "Voltar ao padrão" in frase


def test_a_frase_cala_quando_todo_botao_tem_tecla() -> None:
    """Nada a dizer é melhor que uma linha vazia na tela."""
    completo = {botao: ("KEY_A",) for botao in CANONICAL_BUTTONS}
    assert frase_dos_botoes_sem_tecla(completo) == ""


def test_botoes_do_mouse_saem_do_uinput_mouse_e_nao_de_copia_a_mao() -> None:
    """A lista de "já é do mouse" acompanha o device, não uma cópia envelhecida."""
    from hefesto_dualsense4unix.integrations.uinput_mouse import (
        BUTTON_TO_UINPUT,
        DPAD_TO_KEY,
        EDGE_KEY_MAP,
    )

    esperado = frozenset({*BUTTON_TO_UINPUT, *DPAD_TO_KEY, *EDGE_KEY_MAP, "l2", "r2"})
    assert esperado == BOTOES_JA_DO_MOUSE


# --- a legenda chega à tela a cada refresh ------------------------------


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _FakeListStore:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append(self, row: list[str]) -> None:
        self.rows.append(list(row))

    def clear(self) -> None:
        self.rows.clear()

    def __iter__(self) -> Any:
        return iter(self.rows)


class _FakeMixin:
    """Mixin por composição — evita herdar de GTK só para ler uma frase."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        self._key_bindings_store = _FakeListStore()
        self.legend = _FakeLabel()

    def _get(self, key: str) -> Any:
        return self.legend if key == "key_bindings_legend" else None


def _build_mixin() -> Any:
    instance = _FakeMixin()
    for name in (
        "_resolve_effective_bindings",
        "_refresh_key_bindings_from_draft",
        "_atualizar_legenda",
    ):
        setattr(
            instance,
            name,
            InputActionsMixin.__dict__[name].__get__(instance, type(instance)),
        )
    return instance


def test_o_refresh_pinta_a_legenda_com_os_orfaos() -> None:
    """O caminho real (refresh do rascunho) chega à tela, não só a função pura."""
    mixin = _build_mixin()
    mixin._refresh_key_bindings_from_draft()
    assert BINDINGS_LEGEND in mixin.legend.markup
    assert "Sem tecla (não digitam nada)" in mixin.legend.markup
    assert "X (Cruz)" in mixin.legend.markup


def test_o_refresh_reescreve_a_legenda_quando_o_rascunho_muda() -> None:
    """Pintar só na instalação do TreeView deixaria a frase mentindo depois."""
    mixin = _build_mixin()
    mixin._refresh_key_bindings_from_draft()
    assert "X (Cruz)" in mixin.legend.markup
    mixin.draft = mixin.draft.model_copy(
        update={"key_bindings": {botao: ["KEY_A"] for botao in CANONICAL_BUTTONS}}
    )
    mixin._refresh_key_bindings_from_draft()
    assert "Sem tecla" not in mixin.legend.markup


def test_o_refresh_nao_quebra_sem_a_legenda_no_glade() -> None:
    """Glade sem o rótulo (janela reduzida, teste) segue funcionando."""
    mixin = _build_mixin()
    mixin.legend = None  # type: ignore[assignment]
    mixin._refresh_key_bindings_from_draft()  # não levanta
