"""CONFIG-07 — o que a seção "A janela" SABE, medido sem abrir janela nenhuma.

Este arquivo é o portão da decisão, não do desenho: as três perguntas que a
seção 4 da aba Configurações responde — qual é o ambiente, o que dizer quando o
ícone não sobe na barra do sistema, e qual degrau de tamanho está valendo —
foram tiradas dos widgets e postas em `app/ambiente.py` e `app/theme.py`
justamente para caberem aqui.

POR QUE ISSO IMPORTA. O aceite escrito da sprint é *"num GNOME sem a extensão, a
seção mostra a instrução"*, e **não há GNOME nesta bancada** — ela roda COSMIC.
Com a decisão dentro do widget, o aceite só se fecharia por inspeção visual num
computador que ninguém aqui tem. Com a decisão numa função pura, os quatro casos
viram quatro asserções que rodam em qualquer lugar.

O segundo motivo é medido e é a razão de `ambiente_normalizado` casar por
substring: `XDG_CURRENT_DESKTOP` vem **vazia** em toda sessão headless (é o caso
de todo teste deste repositório) e **composta** em Pop!_OS — `pop:GNOME`. Um
`==` classificaria o Pop!_OS como "outro" e a instrução da extensão nunca
apareceria justamente para quem precisa dela.

AS MORDIDAS, todas verificadas em 22/08/2026 nesta árvore:

* troquei o `in` de `ambiente_normalizado` por `==`: reprovou em
  `test_a_declaracao_composta_do_pop_os_e_gnome`;
* inverti a ordem dos dois `if` (GNOME antes de COSMIC): reprovou em
  `test_cosmic_vence_quando_a_sessao_declara_os_dois`;
* fiz `mensagem_da_bandeja` devolver a mesma frase para "outro" e para "gnome":
  reprovou em `test_o_ambiente_desconhecido_nao_afirma_o_que_falta`;
* fiz `escala_gravada` chamar `escala_fonte`: reprovou em
  `test_a_escala_gravada_ignora_o_cache_da_sessao`.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ambiente as ambiente_mod
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

#: O id literal da extensão, como `install.sh:3104` e a documentação de socorro
#: o escrevem. Está aqui em vez de dentro da asserção porque é ELE o conteúdo
#: que a instrução precisa carregar — sem o id, a frase manda a pessoa procurar.
EXTENSAO_DO_GNOME = "ubuntu-appindicators@ubuntu.com"


def _theme() -> Any:
    """O `app/theme.py`, importado sob demanda.

    Ele puxa `gi` no topo do módulo (`theme.py:26-31`), então um import no
    cabeçalho deste arquivo derrubaria a coleta inteira num ambiente sem
    PyGObject — e as perguntas sobre ambiente, que são puras, iriam junto.
    `exigir_gi_real` resolve os dois casos: limpa o stub que outro arquivo
    plantou, ou pula com motivo.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("degraus do tamanho do texto")
    from hefesto_dualsense4unix.app import theme

    return theme


# --- 1. O que a sessão declara --------------------------------------------


def test_a_declaracao_composta_do_pop_os_e_gnome() -> None:
    """`pop:GNOME` é GNOME. É o que esta bancada mede num Pop!_OS.

    Mordida: trocar o `in` por `==` em `ambiente_normalizado`.
    """
    assert ambiente_normalizado("pop:GNOME") == "gnome"


def test_a_declaracao_simples_do_cosmic_e_cosmic() -> None:
    """Maiúscula não decide nada: a variável chega em caixa alta."""
    assert ambiente_normalizado("COSMIC") == "cosmic"
    assert ambiente_normalizado("cosmic:cosmic") == "cosmic"


def test_cosmic_vence_quando_a_sessao_declara_os_dois() -> None:
    """Sessão COSMIC pode carregar `GNOME` na lista; a recíproca não acontece.

    Mordida: inverter a ordem dos dois `if` — a sessão COSMIC passaria a
    receber a instrução da extensão do GNOME, que não existe lá.
    """
    assert ambiente_normalizado("COSMIC:GNOME") == "cosmic"


def test_sessao_sem_declaracao_nao_levanta_e_cai_em_outro() -> None:
    """Vazia e ausente são o caso REAL de toda sessão headless.

    Este é o primeiro caso do aceite da sprint: *"a aba abre com
    `XDG_CURRENT_DESKTOP` vazia"*. Levantar aqui apagaria a seção inteira, que
    é o que o `contextlib.suppress` do montador faria com a exceção.
    """
    assert ambiente_normalizado("") == "outro"
    assert ambiente_normalizado(None) == "outro"


def test_a_leitura_crua_junta_as_duas_variaveis() -> None:
    """As duas, porque nenhuma sozinha basta — e por argumento, nunca do processo.

    `os.environ` é global: um teste que o alterasse vazaria para os vizinhos.
    """
    lido = ambiente_lido(
        variaveis={"XDG_CURRENT_DESKTOP": "pop:GNOME", "XDG_SESSION_DESKTOP": "pop"}
    )
    assert lido == "pop:GNOME:pop"
    assert ambiente_normalizado(lido) == "gnome"


def test_a_leitura_crua_de_uma_sessao_muda_e_vazia() -> None:
    """Sem nenhuma das duas, string vazia — e nunca um `":"` solto."""
    assert ambiente_lido(variaveis={}) == ""
    assert ambiente_lido(variaveis={"XDG_SESSION_DESKTOP": "cosmic"}) == "cosmic"


# --- 2. A correção dela vence a detecção -----------------------------------


def test_a_correcao_dela_vence_a_deteccao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se ela disser que é GNOME, é GNOME — mesmo numa sessão que grita COSMIC.

    É a razão de a correção existir: a variável erra, e quem está na frente da
    máquina sabe mais que ela.
    """
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
    """`gui_preferences.json` é texto editável à mão.

    Um valor inventado ali não pode virar estado da tela nem exceção: cai na
    detecção, calado.
    """
    monkeypatch.setattr(
        ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: "plasma"}
    )
    assert ambiente_efetivo(variaveis={"XDG_CURRENT_DESKTOP": "COSMIC"}) == "cosmic"
    monkeypatch.setattr(ambiente_mod, "load_gui_prefs", lambda: {CHAVE_AMBIENTE: 7})
    assert ambiente_efetivo(variaveis={}) == "outro"


def test_gravar_recusa_id_que_a_tela_nao_oferece(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Só os três ids de `AMBIENTES` chegam ao disco.

    Mordida: tirar a guarda de `gravar_correcao_de_ambiente` — o teste passa a
    ver a chamada com "plasma" e reprova.
    """
    gravados: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        ambiente_mod, "set_pref", lambda chave, valor: gravados.append((chave, valor))
    )

    gravar_correcao_de_ambiente("plasma")
    assert gravados == []

    for identificador, _rotulo in AMBIENTES:
        gravar_correcao_de_ambiente(identificador)
    assert gravados == [(CHAVE_AMBIENTE, ident) for ident, _r in AMBIENTES]


# --- 3. A frase do detectado ------------------------------------------------


def test_a_frase_do_detectado_usa_o_nome_de_tela() -> None:
    """O texto é o aprovado no desenho, com o nome que a fileira mostra."""
    assert frase_do_detectado("COSMIC") == (
        "Detectado: COSMIC. Corrija se estiver errado."
    )
    assert frase_do_detectado("pop:GNOME").startswith("Detectado: GNOME.")
    assert frase_do_detectado("plasma").startswith("Detectado: Outro.")


def test_sem_declaracao_a_frase_nao_inventa_uma_deteccao() -> None:
    """Dizer "Outro" onde nada foi lido seria a tela afirmando o que não sabe.

    Mordida: devolver a frase de "Outro" também no caso vazio.
    """
    frase = frase_do_detectado("")
    assert "Detectado" not in frase
    assert frase.strip() != ""


# --- 4. A mensagem da barra do sistema --------------------------------------


def test_a_instrucao_do_gnome_traz_o_nome_da_extensao() -> None:
    """Sem o id literal, a frase manda a pessoa procurar sozinha.

    Mordida: trocar o retorno de `("gnome", False)` pela frase de sucesso —
    reprova por não conter o id da extensão.
    """
    frase = mensagem_da_bandeja("gnome", False)
    assert EXTENSAO_DO_GNOME in frase
    assert "conta" in frase, "a instrução tem de dizer que precisa entrar de novo"


def test_a_instrucao_do_cosmic_aponta_o_applet_acentuado() -> None:
    """O applet é "Área de status", com acento — `tray.py:328` escreve sem.

    Copiar aquela string para a tela reprovaria em `validar-acentuacao.py` e
    traria junto o jargão "Tray icon".
    """
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
    """Chutar uma instrução manda a pessoa mexer no lugar errado.

    Mordida: devolver a mesma frase de "gnome" para "outro" — reprova nas duas
    primeiras asserções.
    """
    frase = mensagem_da_bandeja("outro", False)
    assert EXTENSAO_DO_GNOME not in frase
    assert "Área de status" not in frase
    assert "não recebe o ícone" in frase, "o estado continua sendo dito"


# --- 5. Os três degraus do tamanho do texto ---------------------------------


def test_os_tres_degraus_cobrem_a_faixa_inteira() -> None:
    """Qualquer valor de 0 a 8 marca um botão — nunca a fileira em branco.

    A chave `escala_fonte` era alcançável só editando o arquivo à mão, com
    reinício: há gente com 5 gravado. Um 5 que não marca nada deixa a pessoa
    sem saber o que está valendo.
    """
    theme = _theme()
    assert theme.degrau_da_escala(0) == "compacto"
    assert theme.degrau_da_escala(theme.ESCALA_PADRAO) == "normal"
    assert theme.degrau_da_escala(theme.ESCALA_MAXIMA) == "grande"
    for delta in range(0, theme.ESCALA_MAXIMA + 1):
        assert theme.degrau_da_escala(delta) in theme.DEGRAUS_DE_ESCALA


def test_cada_degrau_se_reconhece() -> None:
    """Ida e volta: o degrau de um valor de degrau é ele mesmo.

    Sem isto, a fileira poderia nascer marcando um botão diferente do que a
    pessoa acabou de clicar.
    """
    theme = _theme()
    for nome, valor in theme.DEGRAUS_DE_ESCALA.items():
        assert theme.degrau_da_escala(valor) == nome


def test_nenhum_degrau_passa_do_teto_de_seguranca() -> None:
    """`ESCALA_MAXIMA` é onde a janela deixa de caber numa tela 1080p."""
    theme = _theme()
    assert set(theme.DEGRAUS_DE_ESCALA) == {"compacto", "normal", "grande"}
    for valor in theme.DEGRAUS_DE_ESCALA.values():
        assert 0 <= valor <= theme.ESCALA_MAXIMA
    assert theme.DEGRAUS_DE_ESCALA["normal"] == theme.ESCALA_PADRAO


def test_a_escala_gravada_ignora_o_cache_da_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que está no disco, não o que está na tela — e a diferença é a feature.

    `escala_fonte()` cacheia o delta aplicado na abertura da janela. A fileira
    de degraus precisa do outro número: o que vale na PRÓXIMA abertura, que é o
    que a pessoa acabou de gravar.

    Mordida: fazer `escala_gravada` chamar `escala_fonte` — a segunda asserção
    reprova, porque o disco diz 6 e o cache diz 0.
    """
    theme = _theme()
    monkeypatch.setattr(theme, "_escala_aplicada", 0)
    monkeypatch.setattr(theme, "load_gui_prefs", lambda: {theme.CHAVE_ESCALA: 6})

    assert theme.escala_fonte() == 0
    assert theme.escala_gravada() == 6
    assert theme.degrau_da_escala(theme.escala_gravada()) == "grande"


def test_a_escala_gravada_defende_o_arquivo_editado_a_mao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tipo errado cai no padrão; número fora da faixa é aparado no teto."""
    theme = _theme()
    monkeypatch.setattr(theme, "_escala_aplicada", None)

    monkeypatch.setattr(theme, "load_gui_prefs", lambda: {theme.CHAVE_ESCALA: "grande"})
    assert theme.escala_gravada() == theme.ESCALA_PADRAO

    monkeypatch.setattr(theme, "load_gui_prefs", lambda: {theme.CHAVE_ESCALA: 99})
    assert theme.escala_gravada() == theme.ESCALA_MAXIMA
