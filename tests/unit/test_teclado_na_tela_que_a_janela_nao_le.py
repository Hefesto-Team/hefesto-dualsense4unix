"""TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01 — o dado chegava no fio e ninguém lia.

Medido em 23/08/2026 (sprint NAVEGAÇÃO — UM CONTROLE SÓ-01, §2.5):

- o daemon publica `keyboard_emulation.osk_disponivel` desde 10/08
  (`ipc_handlers._keyboard_emulation_payload`), e é ele quem enxerga o HOST —
  a janela não pode fazer o `shutil.which` por conta própria, porque num
  Flatpak ela olharia dentro do sandbox;
- `grep -rn "osk_disponivel" src/hefesto_dualsense4unix/app/` devolvia VAZIO;
- a legenda da aba recitava `onboard` e `wvkbd-mobintl` como texto fixo e
  **nunca dizia se algum estava instalado** — enquanto o L3 é o único caminho
  do produto para ESCREVER TEXTO, porque nenhum atalho de fábrica digita letra.

A cura é aditiva de propósito: `None` ("ainda não sei") devolve `""` e a tela
fica como estava. Trocar "não sei" por "não tem" porque ninguém respondeu
mandaria ela instalar um pacote que talvez já esteja lá.

Estes testes MORDEM: arrancar a leitura de `osk_disponivel` do estado vivo faz
o bloco do caminho vivo reprovar; devolver `""` nos três estados faz o bloco da
função pura reprovar.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("teclado na tela que a janela não lê")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.input_actions import (
    BINDINGS_LEGEND,
    InputActionsMixin,
    frase_do_teclado_na_tela,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig


# --- a função pura ------------------------------------------------------


def test_sem_resposta_a_legenda_fica_como_estava() -> None:
    assert frase_do_teclado_na_tela(None) == "", (
        "a janela passou a afirmar sobre uma máquina que ninguém olhou"
    )


def test_com_teclado_instalado_a_frase_diz_que_o_L3_abre() -> None:  # noqa: N802  # noqa-acento: L3 é o nome do botão
    frase = frase_do_teclado_na_tela(True)
    assert "está instalado" in frase
    assert "L3" in frase
    assert "Instale" not in frase, "mandou instalar o que já está instalado"


def test_sem_teclado_instalado_a_frase_diz_que_nao_da_para_escrever() -> None:
    frase = frase_do_teclado_na_tela(False)
    assert "não há teclado na tela instalado" in frase
    assert "escrever texto" in frase, (
        "a frase avisa da falta e não diz a CONSEQUÊNCIA — é a única perda que "
        "importa: sem ele não há como escrever texto com o controle"
    )
    assert "wvkbd-mobintl" in frase and "onboard" in frase
    assert frase.index("wvkbd-mobintl") < frase.index("onboard"), (
        "o onboard digita por XTEST e não alcança cliente Wayland nativo — "
        "recomendá-lo primeiro faz o teclado ABRIR e não DIGITAR, que é pior "
        "que não abrir"
    )


def test_os_tres_estados_sao_frases_diferentes() -> None:
    frases = [frase_do_teclado_na_tela(v) for v in (None, True, False)]
    assert len(set(frases)) == 3, (
        "dois estados com o mesmo texto — a tela deixa de distinguir "
        f"não sei / tem / não tem: {frases}"
    )


# --- o caminho vivo -----------------------------------------------------


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


class _Aba(InputActionsMixin):
    """A aba de verdade, com widgets de mentira."""

    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self._key_bindings_store = _FakeListStore()
        self.legend = _FakeLabel()

    def _get(self, widget_id: str) -> Any:
        return self.legend if widget_id == "key_bindings_legend" else None

    def _status_toast(self, _ctx: str, _msg: str) -> None:
        pass


def _responder(monkeypatch: pytest.MonkeyPatch, estado: Any) -> None:
    def fake_call_async(
        _method: str,
        _params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        on_success(estado)

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)


def test_o_estado_vivo_chega_na_legenda(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho real: `state_full` → `_anotar_teclado_na_tela` → legenda."""
    aba = _Aba()
    aba._refresh_key_bindings_from_draft()
    assert "Neste computador" not in aba.legend.markup, "estado inicial é não sei"

    _responder(
        monkeypatch,
        {"keyboard_emulation": {"enabled": True, "osk_disponivel": False}},
    )
    aba._refresh_mouse_from_daemon_async()

    assert "Neste computador" in aba.legend.markup, (
        "o `osk_disponivel` chegou no fio e a legenda continuou sem ele"
    )
    assert "não há teclado na tela instalado" in aba.legend.markup
    assert BINDINGS_LEGEND in aba.legend.markup, "a legenda fixa foi perdida"


def test_a_lista_de_atalhos_nao_e_reconstruida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repintar a legenda não pode derrubar a linha que ela está editando."""
    aba = _Aba()
    aba._refresh_key_bindings_from_draft()
    antes = [list(row) for row in aba._key_bindings_store.rows]
    aba._key_bindings_store.rows[0][1] = "KEY_Z"  # edição em curso

    _responder(
        monkeypatch,
        {"keyboard_emulation": {"osk_disponivel": True}},
    )
    aba._refresh_mouse_from_daemon_async()

    assert aba._key_bindings_store.rows[0][1] == "KEY_Z", (
        "a repintura da legenda reconstruiu a lista e comeu a edição em curso"
    )
    assert len(aba._key_bindings_store.rows) == len(antes)


def test_sem_resposta_a_aba_volta_a_nao_saber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guardar o último valor seria afirmar sobre o que não se olhou agora."""
    aba = _Aba()
    _responder(
        monkeypatch,
        {"keyboard_emulation": {"osk_disponivel": False}},
    )
    aba._refresh_mouse_from_daemon_async()
    assert "Neste computador" in aba.legend.markup

    def fake_falha(
        _method: str,
        _params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        on_failure(ConnectionError("Hefesto sem resposta"))

    monkeypatch.setattr(ipc_bridge, "call_async", fake_falha)
    aba._refresh_mouse_from_daemon_async()

    assert "Neste computador" not in aba.legend.markup, (
        "a aba seguiu afirmando o que sabia de antes, sem ninguém ter olhado"
    )


@pytest.mark.parametrize(
    "estado",
    [None, {}, {"keyboard_emulation": None}, {"keyboard_emulation": {}},
     {"keyboard_emulation": {"osk_disponivel": "sim"}}],
)
def test_estado_torto_conta_como_nao_sei(
    monkeypatch: pytest.MonkeyPatch, estado: Any
) -> None:
    aba = _Aba()
    _responder(monkeypatch, estado)
    aba._refresh_mouse_from_daemon_async()
    assert aba._osk_disponivel is None
