"""CONFIG-07 — o que a seção "A janela" SABE, medido sem abrir janela nenhuma."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ambiente as ambiente_mod
from hefesto_dualsense4unix.app.ambiente import (
    CHAVE_AMBIENTE,
    ambiente_efetivo,
    ambiente_lido,
    ambiente_normalizado,
)

EXTENSAO_DO_GNOME = "ubuntu-appindicators@ubuntu.com"


def _theme() -> Any:
    """O `app/theme.py`, importado sob demanda."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("degraus do tamanho do texto")
    from hefesto_dualsense4unix.app import theme

    return theme


def test_a_declaracao_composta_do_pop_os_e_gnome() -> None:
    """`pop:GNOME` é GNOME. É o que esta bancada mede num Pop!_OS."""
    assert ambiente_normalizado("pop:GNOME") == "gnome"


def test_a_declaracao_simples_do_cosmic_e_cosmic() -> None:
    """Maiúscula não decide nada: a variável chega em caixa alta."""
    assert ambiente_normalizado("COSMIC") == "cosmic"
    assert ambiente_normalizado("cosmic:cosmic") == "cosmic"


def test_cosmic_vence_quando_a_sessao_declara_os_dois() -> None:
    """Sessão COSMIC pode carregar `GNOME` na lista; a recíproca não acontece."""
    assert ambiente_normalizado("COSMIC:GNOME") == "cosmic"


def test_sessao_sem_declaracao_nao_levanta_e_cai_em_outro() -> None:
    """Vazia e ausente são o caso REAL de toda sessão headless."""
    assert ambiente_normalizado("") == "outro"
    assert ambiente_normalizado(None) == "outro"


def test_a_leitura_crua_junta_as_duas_variaveis() -> None:
    """As duas, porque nenhuma sozinha basta — e por argumento, nunca do processo."""
    lido = ambiente_lido(
        variaveis={"XDG_CURRENT_DESKTOP": "pop:GNOME", "XDG_SESSION_DESKTOP": "pop"}
    )
    assert lido == "pop:GNOME:pop"
    assert ambiente_normalizado(lido) == "gnome"


def test_a_leitura_crua_de_uma_sessao_muda_e_vazia() -> None:
    """Sem nenhuma das duas, string vazia — e nunca um `":"` solto."""
    assert ambiente_lido(variaveis={}) == ""
    assert ambiente_lido(variaveis={"XDG_SESSION_DESKTOP": "cosmic"}) == "cosmic"


def test_a_correcao_dela_vence_a_deteccao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se ela disser que é GNOME, é GNOME — mesmo numa sessão que grita COSMIC."""
    monkeypatch.setattr(
        ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: "gnome"}
    )
    assert (
        ambiente_efetivo(variaveis={"XDG_CURRENT_DESKTOP": "COSMIC"}) == "gnome"
    )


def test_sem_correcao_vale_o_que_a_sessao_declara(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nada gravado: a detecção volta a mandar."""
    monkeypatch.setattr(ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: None})
    assert ambiente_efetivo(variaveis={"XDG_CURRENT_DESKTOP": "COSMIC"}) == "cosmic"


def test_correcao_invalida_no_arquivo_nao_derruba_nem_mente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gui_preferences.json` é texto editável à mão."""
    monkeypatch.setattr(
        ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: "plasma"}
    )
    assert ambiente_efetivo(variaveis={"XDG_CURRENT_DESKTOP": "COSMIC"}) == "cosmic"
    monkeypatch.setattr(ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: 7})
    assert ambiente_efetivo(variaveis={}) == "outro"


