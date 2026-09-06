"""CONFIG-07 — a seção "A janela" montada de verdade, com GTK de verdade.

O irmão deste arquivo (`test_config_a_janela_le_o_ambiente.py`) cobra as
DECISÕES da seção sem abrir janela. Este cobra a FIAÇÃO: que os widgets nascem,
que nascem marcando o que está gravado, que o clique grava, que a sonda de
D-Bus não roda na thread que desenha, e que o espelho de "Ligar junto com o
computador" continua sendo espelho.

TRÊS COISAS QUE ESTE ARQUIVO NÃO DEIXA VOLTAR, cada uma com preço medido:

1. **Combo nenhum.** No cosmic-comp o compositor rouba o foco no clique e FECHA
   o popup do `GtkComboBox` na hora (cosmic-epoch#2497) — a escolha fica
   inalcançável. Toda escolha desta aba é botão sempre visível.
2. **`apply_theme` no clique.** Ele COMPÕE: quatro chamadas no mesmo processo
   levaram a fonte de 12,25 a 19 pontos, sem erro nenhum no log. O clique aqui
   GRAVA e diz que vale ao reabrir.
3. **A sonda da bandeja na thread do GTK.** `statusnotifierwatcher_available`
   é síncrona com dois segundos de teto (`desktop_notifications.py:33`) — na
   thread que desenha, ela congela a janela inteira ao abrir a aba.

POR QUE NADA AQUI ESCREVE NO DISCO. As duas pontas de gravação
(`secao_janela.set_pref` e `ambiente.set_pref`) entram como dublê que escreve
num dicionário, e o dicionário é o mesmo que o `load_gui_prefs` dublê lê — é
assim que o teste afirma sobre o VALOR gravado sem depender de arquivo.

CORREÇÃO DE FATO (25/08/2026, LUZ-CEGA-01/E8): este parágrafo dizia que o
dublê existia porque `gui_prefs._CONFIG_DIR` era constante de módulo resolvida
na IMPORTAÇÃO, fora do alcance do isolamento do conftest. A descrição estava
CERTA e o defeito era real — `gui_prefs` agora resolve o caminho na chamada
(`_prefs_file()`), e o portão `test_luz_cega_e8_o_berco_nao_vaza.py` reprova a
volta da constante. O dublê fica pelo motivo do parágrafo acima, não mais por
medo do `$HOME`.

OS DOIS TESTES DE GEOMETRIA SAÍRAM EM 06/09/2026 (`GTK-3`)
-----------------------------------------------------------

`test_a_secao_cabe_na_largura_da_janela` e `test_as_tres_opcoes_ficam_lado_a_lado`
mediam a seção dentro do `scroll_tab_config_box` do `gui/main.glade`, na
`default-width` lida do próprio XML. A superfície que eles mediam é a janela
GTK, aposentada por decisão dela (`D-0609-GTK-LEVA-INTEIRA`) — e com ela saíram
`_realizar`, `_largura_da_janela` e o `_pagina_do_notebook`, que já não tinha
chamador.

**A regra 1 do cabeçalho — "Combo nenhum" — continua medida**, por
`test_nenhuma_escolha_desta_secao_e_um_combo`, que não precisa de janela: ele
anda a árvore da seção. O que se perde é a prova de que a seção CABE, e ela não
tem equivalente na interface nova, onde a mesma decisão vira CSS.

AS MORDIDAS, todas arrancadas e devolvidas em 22/08/2026 nesta árvore:

* liguei o `connect("changed")` ANTES do `set_active_id` em
  `_fileira_do_tamanho`: reprovou em `test_abrir_a_aba_nao_grava_nada`, porque
  a montagem reescreveu sozinha o 5 gravado à mão como 6;
* troquei `run_in_thread(...)` por uma chamada direta a
  `statusnotifierwatcher_available()`: reprovou em cinco testes, a começar por
  `test_a_sonda_da_bandeja_sai_da_thread_do_gtk`;
* troquei o `return False` de cada callback da sonda por `return True`:
  reprovou nos dois casos em `test_o_callback_da_sonda_devolve_false`;
* apaguei o `interruptor.connect("notify::active", ...)`: reprovou em
  `test_o_espelho_segue_o_interruptor_da_aba_sistema`;
* apaguei o `_pintar_a_bandeja` do fim de `_ao_corrigir_o_ambiente`: reprovou
  em `test_corrigir_para_gnome_troca_a_instrucao_sem_sondar_de_novo`;
* troquei a busca por id em `_abrir_a_aba_sistema` pelo índice 7, que é o
  CERTO hoje: reprovou em `test_o_atalho_abre_a_aba_sistema_pelo_id` — e só
  reprova porque o teste reordena o notebook antes de clicar;
* pus um rótulo de parágrafo sem `set_line_wrap`: reprovou em
  `test_a_secao_cabe_na_largura_da_janela`;
* tirei o `wrap=True` do seletor do tamanho: reprovou em
  `test_as_tres_opcoes_ficam_lado_a_lado`, com as três empilhadas.

E uma que NÃO reprovou, escrita porque calar seria dizer que o portão cobre o
que não cobre: `set_homogeneous(True)` nas fileiras leva a seção de 426px para
600px e passa — a seção é curta demais para estourar o teto de 1180px sozinha.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito. Sem
# ela, este módulo derruba a COLETA inteira no CI headless em vez de pular — e
# `pytest.importorskip("gi")` aceitaria o stub que outro arquivo planta.
exigir_gi_real("seção A janela da aba configurações")

from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ambiente as ambiente_mod
from hefesto_dualsense4unix.app import theme as theme_mod
from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG
from hefesto_dualsense4unix.app.actions.config import secao_janela
# `id_da_pagina_corrente` saiu do import em 25/08/2026, junto com o teste do
# botão "Abrir a aba Sistema" que a LEX-4 removeu a pedido dela. Import órfão
# não é sujeira de estilo: ele faz o arquivo parecer exercitar um caminho que
# ninguém exercita mais.
from tests.unit.aba_config_sem_a_janela import HospedeiroDaAbaConfig

#: O id da extensão que a instrução do GNOME precisa carregar.
EXTENSAO_DO_GNOME = "ubuntu-appindicators@ubuntu.com"


class _Bancada:
    """Uma aba montada, com as duas pontas de disco e a sonda sob controle."""

    def __init__(self) -> None:
        self.builder: Any = None
        self.host: Any = None
        self.prefs: dict[str, Any] = {}
        self.sondas: list[tuple[Any, Any, Any]] = []
        self.temas_aplicados: list[Any] = []

    @property
    def secao(self) -> Any:
        """A moldura de "A janela" — a última da aba."""
        filhos = self.builder.get_object(ABA_CONFIG).get_children()
        return filhos[-1]

    def rotulos(self) -> list[str]:
        """Todo texto de rótulo da seção, na ordem em que aparece."""
        return [
            widget.get_text()
            for widget in _arvore(self.secao)
            if isinstance(widget, Gtk.Label)
        ]

    def rotulo_que_comeca_com(self, prefixo: str) -> Any:
        """O `Gtk.Label` da seção cujo texto começa com `prefixo`."""
        for widget in _arvore(self.secao):
            if isinstance(widget, Gtk.Label) and widget.get_text().startswith(prefixo):
                return widget
        raise AssertionError(
            f"nenhum rótulo da seção começa com {prefixo!r}. Há: {self.rotulos()}"
        )

    def botao_de_opcao(self, texto: str) -> Any:
        """O botão da fileira segmentada cujo rótulo é `texto`."""
        for widget in _arvore(self.secao):
            if isinstance(widget, Gtk.RadioButton) and widget.get_label() == texto:
                return widget
        raise AssertionError(f"nenhuma opção rotulada {texto!r} na seção")

    def botao(self, texto: str) -> Any:
        """O `Gtk.Button` comum da seção com o rótulo `texto`."""
        for widget in _arvore(self.secao):
            if (
                isinstance(widget, Gtk.Button)
                and not isinstance(widget, Gtk.RadioButton)
                and widget.get_label() == texto
            ):
                return widget
        raise AssertionError(f"nenhum botão rotulado {texto!r} na seção")


def _arvore(raiz: Any) -> list[Any]:
    """Todo widget da subárvore, incluindo o rótulo de título da moldura."""
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            pilha.extend(obter())
    return achados


def _montar(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prefs: dict[str, Any] | None = None,
    ambiente: str | None = "COSMIC",
) -> _Bancada:
    """Monta a aba em código, roda o mixin e devolve a bancada.

    `ambiente` entra por `XDG_CURRENT_DESKTOP` — a variável de verdade, para o
    caminho de produção ser o exercitado. `None` apaga as duas variáveis, que é
    o caso da sessão headless e o primeiro item do aceite desta sprint.

    06/09/2026 (`GTK-3`): o berço saiu do `gui/main.glade` e virou
    `tests/unit/aba_config_sem_a_janela.py` — a seção "A janela" sempre nasceu
    em `app/actions/config/secao_janela.py`, que é MOTOR e fica, e o XML só
    dava a caixa e o `daemon_autostart_switch` (que o berço entrega, com régua
    de fidelidade própria).
    """
    bancada = _Bancada()
    bancada.prefs = dict(prefs or {})

    monkeypatch.setattr(ambiente_mod, "load_gui_prefs", lambda: dict(bancada.prefs))
    monkeypatch.setattr(theme_mod, "load_gui_prefs", lambda: dict(bancada.prefs))
    monkeypatch.setattr(
        ambiente_mod, "set_pref", lambda chave, valor: bancada.prefs.update({chave: valor})
    )
    monkeypatch.setattr(
        secao_janela, "set_pref", lambda chave, valor: bancada.prefs.update({chave: valor})
    )
    monkeypatch.setattr(
        secao_janela,
        "run_in_thread",
        lambda fn, ok, falhou=None: bancada.sondas.append((fn, ok, falhou)),
    )
    monkeypatch.setattr(
        theme_mod, "apply_theme", lambda janela: bancada.temas_aplicados.append(janela)
    )

    for nome in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP"):
        monkeypatch.delenv(nome, raising=False)
    if ambiente is not None:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", ambiente)

    bancada.host = HospedeiroDaAbaConfig()
    bancada.builder = bancada.host.builder
    bancada.host.install_config_tab()
    return bancada



# --- 1. A seção existe, é a última, e não tem combo -------------------------


def test_a_secao_e_a_ultima_moldura_e_tem_conteudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Última porque é a menos urgente das cinco, e o desenho a põe no fim.

    A asserção de conteúdo não é cerimônia: o montador embrulha `montar` em
    `contextlib.suppress`, então uma exceção na montagem deixaria a moldura na
    tela e VAZIA, sem uma linha de log. Sem esta asserção, todo o resto deste
    arquivo falharia com mensagens que não apontam a causa.
    """
    bancada = _montar(monkeypatch)
    assert bancada.secao.get_label_widget().get_text() == secao_janela.TITULO
    assert bancada.rotulos(), "a seção montou vazia — `montar` levantou e foi engolida"
    for esperado in ("Tamanho do texto:", "Ambiente:", "Ligar junto com o computador"):
        assert esperado in bancada.rotulos()


def test_nenhuma_escolha_desta_secao_e_um_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No cosmic-comp o popup do combo fecha no clique e a escolha some.

    Vale para a aba inteira, não só para esta seção: o defeito é do compositor,
    e uma seção vizinha que trouxesse um combo o traria para a mesma janela.
    """
    bancada = _montar(monkeypatch)
    proibidos = [
        type(widget).__name__
        for widget in _arvore(bancada.builder.get_object(ABA_CONFIG))
        if isinstance(widget, (Gtk.ComboBox, Gtk.ComboBoxText))
    ]
    assert not proibidos, f"combo na aba Configurações: {proibidos}"



def test_a_aba_abre_com_a_sessao_sem_declarar_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O primeiro item do aceite: `XDG_CURRENT_DESKTOP` vazia.

    É o caso REAL de toda sessão headless — e o caso em que a tela não pode
    afirmar uma detecção que não houve.
    """
    bancada = _montar(monkeypatch, ambiente=None)
    assert bancada.rotulos(), "a seção sumiu quando a sessão não declarou nada"
    frase = bancada.rotulo_que_comeca_com("A sessão não diz")
    assert frase.get_text().strip() != ""
    assert "Detectado" not in " ".join(bancada.rotulos())


# --- 2. O tamanho do texto --------------------------------------------------


def test_a_fileira_nasce_marcando_o_degrau_gravado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem gravou "Grande" e reabriu tem de ver "Grande" marcado.

    Lê do DISCO e não do cache da sessão (`escala_fonte`), que é o que o tema
    aplicou na abertura — os dois divergem justamente depois de uma gravação
    nesta tela.
    """
    grande = theme_mod.DEGRAUS_DE_ESCALA["grande"]
    bancada = _montar(monkeypatch, prefs={theme_mod.CHAVE_ESCALA: grande})
    assert bancada.host._config_escala_seletor.get_active_id() == "grande"
    assert bancada.botao_de_opcao("Grande").get_active()

    outra = _montar(monkeypatch, prefs={theme_mod.CHAVE_ESCALA: 0})
    assert outra.host._config_escala_seletor.get_active_id() == "compacto"


def test_abrir_a_aba_nao_grava_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Montar a tela não é gesto dela, e não pode virar gravação.

    `SegmentedSelector.set_active_id` EMITE "changed" (espelha o
    `GtkComboBox`), então a marcação inicial tem de acontecer ANTES do
    `connect`.

    O 5 gravado não é número escolhido a esmo: até esta tela existir, a chave
    `escala_fonte` só era alcançável editando o arquivo à mão, e qualquer valor
    de 0 a 8 está lá fora. Ele é o único que revela o defeito — com 6 no disco,
    a gravação espúria escreveria 6 por cima de 6 e passaria despercebida.

    Mordida: ligar o `connect` antes do `set_active_id` — a abertura reescreve
    sozinha o 5 como 6, e a escolha dela é perdida por um clique que ninguém
    deu.
    """
    bancada = _montar(monkeypatch, prefs={theme_mod.CHAVE_ESCALA: 5})
    assert bancada.host._config_escala_seletor.get_active_id() == "grande"
    assert bancada.prefs == {theme_mod.CHAVE_ESCALA: 5}


def test_o_clique_grava_o_degrau_e_nao_reaplica_o_tema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Grava e diz que vale ao reabrir — é a decisão J1 desta leva.

    `apply_theme` COMPÕE: soma ao `gtk-font-name` já posto e empilha provider
    sem nunca chamar `remove_provider_for_screen`. Chamá-lo aqui produziria
    fonte errada em silêncio, e a única pista seria a interface crescendo a
    cada clique.

    Mordida: acrescentar `apply_theme(host.window)` ao handler.
    """
    bancada = _montar(monkeypatch, prefs={theme_mod.CHAVE_ESCALA: 0})
    bancada.botao_de_opcao("Grande").set_active(True)

    assert bancada.prefs[theme_mod.CHAVE_ESCALA] == theme_mod.DEGRAUS_DE_ESCALA["grande"]
    assert bancada.temas_aplicados == [], (
        "o clique reaplicou o tema — `apply_theme` compõe e a fonte cresce sozinha"
    )


def test_a_tela_diz_que_o_tamanho_vale_ao_reabrir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gravação diferida só é honesta se estiver escrita na tela.

    Sem a frase, o clique não faz nada visível e a pessoa conclui que a opção
    está quebrada.
    """
    # A FRASE VIROU DICA em 25/08/2026 (LEX-2, decisão dela): ela saiu do corpo
    # da página e passou a morar no tooltip do próprio rótulo. O teste segue o
    # texto em vez de fossilizar o lugar dele — travar a posição faria esta
    # régua reprovar toda vez que a aba respirasse.
    bancada = _montar(monkeypatch)
    rotulo = bancada.rotulo_que_comeca_com("Tamanho do texto")
    assert "abrir o Hefesto" in (rotulo.get_tooltip_text() or ""), (
        "a gravação diferida sumiu da tela: sem a frase, em lugar nenhum, o "
        "clique não faz nada visível e a pessoa conclui que a opção quebrou."
    )


# --- 3. A sonda da barra do sistema -----------------------------------------


def test_a_sonda_da_bandeja_sai_da_thread_do_gtk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois segundos de D-Bus na thread que desenha congelam a janela.

    Enquanto a resposta não chega, o rótulo diz que está conferindo — afirmar
    que o ícone está lá antes de perguntar seria a tela adivinhando.

    Mordida: chamar `statusnotifierwatcher_available()` direto no `montar`.
    """
    bancada = _montar(monkeypatch)
    assert len(bancada.sondas) == 1, "a sonda não foi despachada para thread worker"
    funcao, _ok, _falhou = bancada.sondas[0]
    assert funcao is secao_janela.statusnotifierwatcher_available
    assert bancada.rotulo_que_comeca_com("Conferindo")


def test_o_callback_da_sonda_devolve_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contrato do `GLib.idle_add`: devolver `True` reagenda para sempre.

    Um callback que reagenda sozinho refaz a pintura a cada volta do laço
    ocioso — é CPU queimada sem nada na tela mudando.

    Mordida: trocar o `return False` por `return True` nos dois callbacks.
    """
    bancada = _montar(monkeypatch)
    _funcao, pousou, falhou = bancada.sondas[0]
    assert pousou(True) is False
    assert falhou(RuntimeError("sem barramento")) is False


def test_sem_watcher_no_cosmic_a_secao_ensina_o_applet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ícone que não sobe deixa de ser silêncio e vira instrução.

    Laranja, não vermelho: nada foi destruído, a janela continua inteira. É a
    regra de cor do `theme.css:13` — "VERDE confirma, LARANJA alerta".
    """
    bancada = _montar(monkeypatch, ambiente="COSMIC")
    _funcao, pousou, _falhou = bancada.sondas[0]
    pousou(False)

    rotulo = bancada.rotulo_que_comeca_com("A barra do sistema")
    assert "Área de status" in rotulo.get_text()
    assert "#ffb86c" in rotulo.get_label(), "o alerta saiu sem a cor de atenção"


def test_com_watcher_a_secao_so_relata_o_estado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ícone aparecendo não é tarefa: nada a instalar, nada a ligar."""
    bancada = _montar(monkeypatch)
    _funcao, pousou, _falhou = bancada.sondas[0]
    pousou(True)

    rotulo = bancada.rotulo_que_comeca_com("A barra do sistema")
    assert "Área de status" not in rotulo.get_text()
    assert EXTENSAO_DO_GNOME not in rotulo.get_text()
    assert "#ffb86c" not in rotulo.get_label()


def test_corrigir_para_gnome_troca_a_instrucao_sem_sondar_de_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O aceite do GNOME, fechado numa bancada que roda COSMIC.

    É para isto que o ambiente é corrigível: ele informa a MENSAGEM e nada
    mais. Corrigir para GNOME numa sessão COSMIC não muda uma linha do que o
    produto faz — muda o que a seção sabe recomendar quando o ícone não sobe.

    Mordida: não repintar depois de gravar a correção — a seção continuaria
    ensinando o applet do COSMIC a quem acabou de dizer que está no GNOME.
    """
    bancada = _montar(monkeypatch, ambiente="COSMIC")
    _funcao, pousou, _falhou = bancada.sondas[0]
    pousou(False)
    assert "Área de status" in bancada.rotulo_que_comeca_com("A barra do sistema").get_text()

    bancada.botao_de_opcao("GNOME").set_active(True)

    rotulo = bancada.rotulo_que_comeca_com("A barra do sistema")
    assert EXTENSAO_DO_GNOME in rotulo.get_text()
    assert bancada.prefs[ambiente_mod.CHAVE_AMBIENTE] == "gnome"
    assert len(bancada.sondas) == 1, "a correção disparou uma sonda de D-Bus nova"


def test_a_correcao_nasce_marcando_o_ambiente_que_vale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A correção gravada vence a sessão, e a fileira mostra isso."""
    bancada = _montar(
        monkeypatch, prefs={ambiente_mod.CHAVE_AMBIENTE: "gnome"}, ambiente="COSMIC"
    )
    assert bancada.host._config_ambiente_seletor.get_active_id() == "gnome"
    assert bancada.botao_de_opcao("GNOME").get_active()
    # A linha do detectado continua contando o que a SESSÃO declarou: é dado
    # de diagnóstico, e reescrevê-lo com a correção apagaria a discordância.
    assert "COSMIC" in bancada.rotulo_que_comeca_com("Detectado:").get_text()


# --- 4. O espelho de "Ligar junto com o computador" -------------------------


def test_o_espelho_segue_o_interruptor_da_aba_sistema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma direção só: quem escreve é a aba Sistema.

    Dois donos do mesmo gesto é a cicatriz que a casa já pagou uma vez — por
    isso aqui é rótulo, não um segundo interruptor.

    Mordida: apagar o `connect("notify::active", ...)` — o espelho congela no
    valor que o Glade trouxe e passa a mentir assim que o estado muda.
    """
    bancada = _montar(monkeypatch)
    interruptor = bancada.builder.get_object("daemon_autostart_switch")
    estado = bancada.host._config_autostart_estado

    interruptor.set_active(True)
    assert estado.get_text() == "Ligado"
    interruptor.set_active(False)
    assert estado.get_text() == "Desligado"


def test_o_espelho_nao_e_editavel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum interruptor novo nasce nesta seção — só o rótulo que reflete."""
    bancada = _montar(monkeypatch)
    interruptores = [w for w in _arvore(bancada.secao) if isinstance(w, Gtk.Switch)]
    assert not interruptores, (
        "a seção criou um segundo dono para 'Ligar junto com o computador'"
    )
    assert isinstance(bancada.host._config_autostart_estado, Gtk.Label)


# `test_o_atalho_abre_a_aba_sistema_pelo_id` SAIU em 25/08/2026, e a razão é
# dela: o botão "Abrir a aba Sistema" foi REMOVIDO da seção "A janela" (LEX-4,
# pedido literal). Um teste que exige um botão que o produto não tem mais não é
# regressão — é fóssil, e fóssil protege o defeito que a remoção veio curar.
#
# A cobertura não se perdeu, mudou de lado: `test_a_janela_nao_tem_botao_de_abrir_a_aba_sistema`,
# em `test_o_lexico_da_aba_configuracoes.py:431`, garante que ele NÃO VOLTA.
