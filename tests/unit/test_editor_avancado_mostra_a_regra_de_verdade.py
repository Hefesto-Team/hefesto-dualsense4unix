"""O "Modo avançado" mostrava três campos VAZIOS no lugar da regra do perfil.

O DEFEITO, fotografado por ela em 10/08/2026 às 04:34 — duas fotos da MESMA
tela, um segundo de diferença:

- avançado DESLIGADO: ``Aplica a: [Jogo da Steam]``, ``Nome do jogo: 3357650``;
- avançado LIGADO: os três campos crus em branco, mostrando só os
  textos-fantasma do glade (``CSV: Steam,firefox``, ``regex (re.search)``,
  ``CSV: doom.x86_64,celeste``).

E o arquivo dela, no mesmo instante, dizia
``window_class: ["steam_app_3357650"]`` — mais o ``process_name`` que a página
simples não mostra (ESCONDER-EM-VEZ-DE-SAIR-01).

A MECÂNICA: ``_populate_editor`` só escreve nos três campos crus no ramo do
match COMPLEXO; no ramo do preset simples ele mexe no seletor e no campo livre
e deixa os crus como estiverem. E ``on_profile_advanced_toggle`` só trocava a
página da stack (``_apply_editor_mode``). Ligar o avançado depois do perfil
aberto, portanto, nunca tinha de onde tirar a regra.

O PREÇO era duplo, e o segundo é pior que o primeiro:

1. a tela AFIRMAVA que o perfil não tem critério nenhum — e o
   ``exigencia_invisivel`` da própria casa manda "Ligue o Modo avançado para
   ver e mudar", ou seja, a janela mandava olhar justamente onde mentia;
2. os campos vazios são o que o ``_build_profile_from_editor`` LÊ quando o
   avançado está ligado. Apagar o que já estava vazio na tela é um gesto dela
   como outro qualquer, e o perfil do jogo dela virava outra coisa em silêncio.

A CURA: ligar o avançado transfere para os três campos a regra que o perfil TEM
agora — a mesma conta que o Salvar faz (``_regra_real_do_perfil_aberto``).

Hermético: widgets falsos com a mesma API por-ID que a aba usa; nenhum GTK
real, nenhum daemon, nenhuma escrita no ``~/.config`` dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("O editor avançado que mostrava campos vazios")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
)

APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text

    def set_placeholder_text(self, text: str) -> None:
        return None

    def set_tooltip_text(self, text: str) -> None:
        return None


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._teto = float(pa.PRIORIDADE_MAXIMA)
        self._value = 0.0
        self._handlers: list[Any] = []
        self.set_value(value)

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "value-changed":
            self._handlers.append(handler)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        novo = max(0.0, min(self._teto, float(value)))
        mudou = novo != self._value
        self._value = novo
        if mudou:
            for handler in self._handlers:
                handler(self)


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active

    def get_active(self) -> bool:
        return self.active


class _FakeBox:
    """A linha "Nome do jogo:" com a doutrina de visibilidade do GTK."""

    def __init__(self) -> None:
        self.visivel = False
        self.no_show_all = True
        self.filhos_visiveis = False

    def show(self) -> None:
        self.visivel = True

    def show_all(self) -> None:
        if self.no_show_all:
            return
        self.visivel = True
        self.filhos_visiveis = True

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = bool(valor)

    def hide(self) -> None:
        self.visivel = False


class _FakeSelector:
    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class Editor(pa.ProfilesActionsMixin):
    """Editor com os métodos REAIS do mixin sobre widgets falsos."""


    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self.selecionado

    def _refresh_preview(self) -> None:
        return None

    def _prefill_steam_appid(self) -> None:
        return None

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


    def campos_crus(self) -> tuple[str, str, str]:
        return (
            self._get("profile_window_class_entry").get_text(),
            self._get("profile_title_regex_entry").get_text(),
            self._get("profile_process_name_entry").get_text(),
        )


@pytest.fixture(autouse=True)
def _sem_preferencia_no_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """`on_profile_advanced_toggle` persiste a preferência — aqui não escreve."""
    monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)


def perfil_dela() -> Profile:
    """O ``Pragmata`` como estava no disco dela às 04:34 de 10/08.

    ``process_name`` junto do appid é o campo que a página simples NÃO mostra e
    que ``from_simple_choice`` preserva (ESCONDER-EM-VEZ-DE-SAIR-01) — ele é
    metade da razão de existir do modo avançado.
    """
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[WM_JOGO], process_name=["PRAGMATA.exe"]),
        priority=200,
    )


def perfil_complexo() -> Profile:
    """Regra que o editor simples não sabe exprimir — abre no avançado."""
    return Profile(
        name="Navegação",
        match=MatchCriteria(
            window_class=["firefox"], window_title_regex="YouTube"
        ),
        priority=50,
    )


class TestOQueContinuaComoEstava:
    def test_o_toggle_continua_trocando_a_pagina_e_persistindo_a_preferencia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A função velha do handler segue inteira (stack + `set_pref`)."""
        gravado: list[tuple[str, Any]] = []
        monkeypatch.setattr(
            pa, "set_pref", lambda k, v: gravado.append((k, v))
        )
        editor = Editor()

        editor.ligar_o_avancado()
        assert editor._mode_advanced is True
        assert editor._get("profile_editor_stack").visible_child == "avancado"

        editor.desligar_o_avancado()
        assert editor._mode_advanced is False
        assert editor._get("profile_editor_stack").visible_child == "simples"
        assert gravado == [("advanced_editor", True), ("advanced_editor", False)]


