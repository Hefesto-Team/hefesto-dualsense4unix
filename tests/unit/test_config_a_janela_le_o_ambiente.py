"""CONFIG-07 — o que a seção "A janela" SABE, medido sem abrir janela nenhuma."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ambiente as ambiente_mod
from hefesto_dualsense4unix.app import escala
from hefesto_dualsense4unix.app.ambiente import (
    AMBIENTES,
    CHAVE_AMBIENTE,
    ambiente_efetivo,
    ambiente_lido,
    ambiente_normalizado,
    frase_do_detectado,
    gravar_correcao_de_ambiente,
    mensagem_da_bandeja,
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


def test_gravar_recusa_id_que_a_tela_nao_oferece(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Só os três ids de `AMBIENTES` chegam ao disco."""
    gravados: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        ambiente_mod, "set_pref", lambda chave, valor: gravados.append((chave, valor))
    )

    gravar_correcao_de_ambiente("plasma")
    assert gravados == []

    for identificador, _rotulo in AMBIENTES:
        gravar_correcao_de_ambiente(identificador)
    assert gravados == [(CHAVE_AMBIENTE, ident) for ident, _r in AMBIENTES]


def test_a_frase_do_detectado_usa_o_nome_de_tela() -> None:
    """O texto é o aprovado no desenho, com o nome que a fileira mostra."""
    assert frase_do_detectado("COSMIC") == (
        "Detectado: COSMIC. Corrija se estiver errado."
    )
    assert frase_do_detectado("pop:GNOME").startswith("Detectado: GNOME.")
    assert frase_do_detectado("plasma").startswith("Detectado: Outro.")


def test_sem_declaracao_a_frase_nao_inventa_uma_deteccao() -> None:
    """Dizer "Outro" onde nada foi lido seria a tela afirmando o que não sabe."""
    frase = frase_do_detectado("")
    assert "Detectado" not in frase
    assert frase.strip() != ""


def test_a_instrucao_do_gnome_traz_o_nome_da_extensao() -> None:
    """Sem o id literal, a frase manda a pessoa procurar sozinha."""
    frase = mensagem_da_bandeja("gnome", False)
    assert EXTENSAO_DO_GNOME in frase
    assert "conta" in frase, "a instrução tem de dizer que precisa entrar de novo"


def test_a_instrucao_do_cosmic_aponta_o_applet_acentuado() -> None:
    """O applet é "Área de status", com acento — `tray.py:328` escreve sem."""
    frase = mensagem_da_bandeja("cosmic", False)
    assert "Área de status" in frase
    assert "Tray" not in frase


def test_com_a_barra_recebendo_o_icone_nao_ha_instrucao() -> None:
    """Ícone aparecendo é estado, não tarefa: nada a instalar, nada a ligar."""
    for ambiente in ("gnome", "cosmic", "outro"):
        frase = mensagem_da_bandeja(ambiente, True)
        assert EXTENSAO_DO_GNOME not in frase
        assert "Área de status" not in frase
        assert "ligue" not in frase.lower()


def test_o_ambiente_desconhecido_nao_afirma_o_que_falta() -> None:
    """Chutar uma instrução manda a pessoa mexer no lugar errado."""
    frase = mensagem_da_bandeja("outro", False)
    assert EXTENSAO_DO_GNOME not in frase
    assert "Área de status" not in frase
    assert "não recebe o ícone" in frase, "o estado continua sendo dito"


def test_os_tres_degraus_cobrem_a_faixa_inteira() -> None:
    """Qualquer valor de 0 a 8 marca um botão — nunca a fileira em branco."""
    assert escala.degrau_da_escala(0) == "compacto"
    assert escala.degrau_da_escala(escala.ESCALA_PADRAO) == "normal"
    assert escala.degrau_da_escala(escala.ESCALA_MAXIMA) == "grande"
    for delta in range(0, escala.ESCALA_MAXIMA + 1):
        assert escala.degrau_da_escala(delta) in escala.DEGRAUS_DE_ESCALA


def test_cada_degrau_se_reconhece() -> None:
    """Ida e volta: o degrau de um valor de degrau é ele mesmo."""
    for nome, valor in escala.DEGRAUS_DE_ESCALA.items():
        assert escala.degrau_da_escala(valor) == nome


def test_nenhum_degrau_passa_do_teto_de_seguranca() -> None:
    """`ESCALA_MAXIMA` é onde a janela deixa de caber numa tela 1080p."""
    assert set(escala.DEGRAUS_DE_ESCALA) == {"compacto", "normal", "grande"}
    for valor in escala.DEGRAUS_DE_ESCALA.values():
        assert 0 <= valor <= escala.ESCALA_MAXIMA
    assert escala.DEGRAUS_DE_ESCALA["normal"] == escala.ESCALA_PADRAO


def test_a_escala_gravada_ignora_o_cache_da_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que está no disco, não o que está na tela — e a diferença é a feature."""
    theme = _theme()
    monkeypatch.setattr(theme, "_escala_aplicada", 0)
    monkeypatch.setattr(escala, "load_gui_prefs", lambda: {escala.CHAVE_ESCALA: 6})

    assert theme.escala_fonte() == 0
    assert theme.escala_gravada() == 6
    assert theme.degrau_da_escala(theme.escala_gravada()) == "grande"


def test_a_escala_gravada_defende_o_arquivo_editado_a_mao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tipo errado cai no padrão; número fora da faixa é aparado no teto."""
    monkeypatch.setattr(escala, "load_gui_prefs", lambda: {escala.CHAVE_ESCALA: "grande"})
    assert escala.escala_gravada() == escala.ESCALA_PADRAO

    monkeypatch.setattr(escala, "load_gui_prefs", lambda: {escala.CHAVE_ESCALA: 99})
    assert escala.escala_gravada() == escala.ESCALA_MAXIMA
