"""O botão do meio da barra diz o que o clique VAI FAZER — e diz em português.

BARRA-MAXIMIZADA-01, 5ª volta — 20/09/2026.

**O QUE ESTA RÉGUA MEDE, e o que ela deliberadamente NÃO mede.**

Ela **não** mede o defeito que dá nome à sprint. Aquele é de PINTURA — o GTK
entrega três botões e a tela dela mostra um —, ele vive entre o widget e o
pixel, e a única janela de observação é a tela dela; fotografá-la CURA o defeito,
o que faz do instrumento óbvio um instrumento que apaga o que veio medir. A
ordem dela de 19/09 desceu essa caça para o fim da fila, e ela continua lá.

Ela mede a CONTA QUE A 4ª VOLTA DEIXOU ABERTA. Trocar os botões da decoração do
tema por ``Gtk.Button`` desta casa foi a decisão certa e é a que fica — mas a
decoração fazia, de graça, o que os nossos não faziam: **trocar o ícone quando a
janela está maximizada**. Medido nesta árvore antes da cura, montando a barra
exatamente como o construtor a montava: ``window-maximize-symbolic`` em qualquer
estado, e a dica presa em «Maximizar» para um clique que ia RESTAURAR.

E a sprint já tinha o oráculo por escrito: a janela de teste maximizada, ainda
com ``set_show_close_button(True)``, respondia ``window-restore-symbolic`` em
x=1844. O comportamento que a 4ª volta substituiu trocava o ícone; o que entrou
no lugar não trocava.

O SEGUNDO DEFEITO, e o número que eu publiquei errado antes de acertar
----------------------------------------------------------------------
Um botão só-imagem não tem rótulo, e o ATK cai no nome do ÍCONE. Medido nesta
árvore, na sessão dela (``LANG=pt_BR.UTF-8``) e com ``LC_ALL=C``:

============================  =============  ==========
ícone                         em ``pt_BR``   em ``C``
============================  =============  ==========
``window-close-symbolic``     ``Fechar``     ``Close``
``window-maximize-symbolic``  ``Maximize``   ``Maximize``
``window-minimize-symbolic``  ``Minimize``   ``Minimize``
``window-restore-symbolic``   ``Restore``    ``Restore``
============================  =============  ==========

**Só o fechar estava traduzido.** Na tela dela, dois dos três botões se
anunciavam em inglês com a dica ao lado em português — e o estado novo desta
volta entraria pela mesma porta, anunciando «Restore» na janela maximizada.

CORREÇÃO DE FATO, e o erro foi meu: esta régua nasceu afirmando que **os três**
respondiam em inglês, ``'Close'`` incluído. A medição que produziu esse número
rodou com ``LC_ALL=C`` no arquivo de ambiente da própria régua — herdado da
regra de LER o servidor de som sem tradução — e respondeu sobre o locale do
instrumento, não sobre o produto. *O instrumento respondia sobre outra coisa
que não o produto*, e quem o pegou foi o teste de mordida que eu tinha escrito
para provar o contrário: ele passou quando devia reprovar.

Por isso o assunto tem DUAS réguas. ``test_os_tres_botoes_...`` amarra o nome à
dica dentro deste processo, e já morde na sessão dela pelos dois botões em
inglês; ``test_o_nome_acessivel_nao_segue_o_locale`` mede **num processo filho
com ``LC_ALL=C``**, para a garantia não depender do locale de quem rodar a
suíte — que é exatamente a variável que me enganou.

**POR QUE ISTO TEM RÉGUA E A PINTURA NÃO:** ``montar_a_barra`` é função de
módulo, então a barra nasce, é medida e morre **sem toplevel nenhuma** — nada
chega à sessão dela, e a TELA-DELA-01 continua valendo sem escape.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito. Sem
# ela, este módulo derruba a COLETA inteira no CI headless em vez de pular — e
# `pytest.importorskip("gi")` aceitaria o stub que outro arquivo planta.
exigir_gi_real("a barra da janela da interface nova")

from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

from hefesto_dualsense4unix.gui import ponte_da_tela


def _barra_de_verdade() -> tuple[Any, dict[str, Any]]:
    """A barra do produto, montada pelo dono dela. Nenhuma janela é aberta."""
    return ponte_da_tela.montar_a_barra("Hefesto", "aba CONTROLES", lambda *_: None)


def _icone(botao: Any) -> str:
    return str(botao.get_image().get_icon_name()[0])


def _nome_acessivel(botao: Any) -> str:
    return str(botao.get_accessible().get_name())


# -- a cara do botão do meio -------------------------------------------------


def test_os_dois_estados_do_maximizar_sao_icones_diferentes() -> None:
    """Restaurada e maximizada não podem desenhar o mesmo ícone.

    A MORDIDA mais barata da sprint: fazer as duas chaves apontarem para o
    mesmo par faz este teste reprovar, e é exatamente o estado de 19/09 —
    `window-maximize-symbolic` nos dois.
    """
    restaurada = ponte_da_tela.APARENCIA_DO_MAXIMIZAR[False]
    maximizada = ponte_da_tela.APARENCIA_DO_MAXIMIZAR[True]
    assert restaurada[0] == "window-maximize-symbolic"
    assert maximizada[0] == "window-restore-symbolic"
    assert restaurada[0] != maximizada[0], (
        "o ícone não muda com o estado — é o defeito que a 4ª volta deixou"
    )
    assert restaurada[1] != maximizada[1], (
        "a dica promete a mesma coisa nos dois estados, e num deles ela mente"
    )


def test_a_tupla_da_barra_le_a_aparencia_em_vez_de_repetir() -> None:
    """`BOTOES_DA_BARRA` e `APARENCIA_DO_MAXIMIZAR` são o mesmo valor, um dono.

    Dois literais iguais em dois lugares divergem no dia em que um mudar — e a
    divergência aqui é o botão nascer com uma cara e o primeiro evento de
    estado lhe dar outra, sem nada ter mudado na janela.
    """
    do_meio = [linha for linha in ponte_da_tela.BOTOES_DA_BARRA if linha[1] == "maximizar"]
    assert len(do_meio) == 1
    icone, _, dica = do_meio[0]
    assert (icone, dica) == ponte_da_tela.APARENCIA_DO_MAXIMIZAR[False]


def test_o_botao_do_meio_troca_de_cara_com_o_estado() -> None:
    """Maximizada ele desenha «restaurar» e promete «Restaurar»; e volta."""
    _barra, botoes = _barra_de_verdade()
    botao = botoes["maximizar"]

    assert _icone(botao) == "window-maximize-symbolic"
    assert botao.get_tooltip_text() == "Maximizar"

    assert ponte_da_tela.vestir_a_cara_do_maximizar(botoes, True) is True
    assert _icone(botao) == "window-restore-symbolic"
    assert botao.get_tooltip_text() == "Restaurar"
    assert _nome_acessivel(botao) == "Restaurar"

    assert ponte_da_tela.vestir_a_cara_do_maximizar(botoes, False) is True
    assert _icone(botao) == "window-maximize-symbolic"
    assert botao.get_tooltip_text() == "Maximizar"
    assert _nome_acessivel(botao) == "Maximizar"


def test_a_janela_oculta_nao_estoura_por_nao_ter_barra() -> None:
    """`Gtk.OffscreenWindow` não tem barra, e isso não é erro — é o desenho."""
    assert ponte_da_tela.vestir_a_cara_do_maximizar({}, True) is False


# -- o nome que o leitor de tela anuncia -------------------------------------


def test_os_tres_botoes_tem_nome_acessivel_em_portugues() -> None:
    """O que o leitor de tela anuncia é a MESMA palavra que a dica mostra.

    Ele morde na sessão dela: com `vestir_o_nome_acessivel` arrancado, o
    «maximizar» e o «minimizar» voltam a `'Maximize'` e `'Minimize'` mesmo em
    `pt_BR` — só o «fechar» é traduzido pelo GTK. O irmão de baixo cobre o
    caso em que nem esse é.
    """
    _barra, botoes = _barra_de_verdade()
    assert set(botoes) == {"fechar", "maximizar", "minimizar"}
    esperado = {
        gesto: dica for _icone_do_botao, gesto, dica in ponte_da_tela.BOTOES_DA_BARRA
    }
    for gesto, botao in botoes.items():
        nome = _nome_acessivel(botao)
        assert nome == esperado[gesto], (
            f"o botão {gesto!r} se anuncia como {nome!r} e mostra "
            f"{esperado[gesto]!r} — quem ouve a interface recebe outra palavra "
            "que quem a lê"
        )


#: O que o processo filho mede, e por que ele é um processo à parte: o gettext
#: do GTK é resolvido na carga, então trocar `LC_ALL` dentro deste processo não
#: muda mais nada. Sem isto, a régua responderia sobre o locale DELA.
_SONDA_DO_LOCALE = """
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
from hefesto_dualsense4unix.gui.ponte_da_tela import montar_a_barra
barra, botoes = montar_a_barra("Hefesto", "", lambda *_: None)
for gesto in ("fechar", "maximizar", "minimizar"):
    print(gesto, botoes[gesto].get_accessible().get_name(), sep="=")
"""


def test_o_nome_acessivel_nao_segue_o_locale() -> None:
    """Nem o «fechar» se salva fora do pt_BR — e a garantia não pode depender disso.

    Arrancar `vestir_o_nome_acessivel` faz o filho imprimir
    `Close`/`Maximize`/`Minimize`, e este teste reprova. Ele existe separado do
    irmão de cima porque foi o locale que me enganou uma vez: uma régua que
    mede no processo de quem a roda responde sobre a máquina, não sobre o
    produto.

    O filho roda com `LC_ALL=C` porque o gettext do GTK resolve na CARGA: o
    locale tem de estar posto antes de o processo existir.
    """
    import os
    import subprocess
    import sys

    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    ambiente["LANGUAGE"] = ""
    ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
    filho = subprocess.run(
        [sys.executable, "-c", _SONDA_DO_LOCALE],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if filho.returncode != 0:
        pytest.skip(f"a sonda de locale não subiu: {filho.stderr.strip()[-200:]}")
    lido = dict(
        linha.split("=", 1)
        for linha in filho.stdout.strip().splitlines()
        if "=" in linha
    )
    esperado = {
        gesto: dica for _icone_do_botao, gesto, dica in ponte_da_tela.BOTOES_DA_BARRA
    }
    assert lido == esperado, (
        "sob LC_ALL=C o leitor de tela anuncia outra língua que a dica mostra — "
        f"leu {lido!r}, e a tela inteira fala português"
    )


# -- o redesenho não roda por troca de foco ----------------------------------


def _evento_de_estado(mudou: Any, novo: Any) -> Any:
    evento = Gdk.EventWindowState()
    evento.changed_mask = mudou
    evento.new_window_state = novo
    return evento


class _JanelaMuda:
    """Só o que o handler toca. Nenhuma janela de verdade é criada.

    **ELA SEGURA A BARRA DE PROPÓSITO, e isso custou um segfault.** Na primeira
    versão o helper montava a barra numa variável local e devolvia só o mapa de
    botões: ao sair da função a `Gtk.HeaderBar` perdia a última referência, os
    filhos iam junto, e o `set_from_icon_name` do teste seguinte escrevia em
    memória liberada — `Fatal Python error: Segmentation fault`, sem uma linha
    de assert. No produto quem segura a barra é a janela; aqui tem de ser
    alguém também.
    """

    def __init__(self, barra: Any) -> None:
        self.barra = barra

    def get_titlebar(self) -> Any:
        return self.barra


def _quem_escuta() -> Any:
    """Uma `JanelaDaAba` só com o que o handler de estado toca."""
    quem = object.__new__(ponte_da_tela.JanelaDaAba)
    barra, botoes = _barra_de_verdade()
    quem.janela = _JanelaMuda(barra)  # type: ignore[attr-defined]
    quem._botoes_da_barra = botoes  # type: ignore[attr-defined]
    return quem


def test_so_o_foco_mudando_nao_agenda_redesenho(monkeypatch: Any) -> None:
    """Ela alterna entre o terminal e a janela o dia todo — e isso não é geometria.

    `Gdk.WindowState.FOCUSED` é um bit de estado como os outros, e o GTK emite
    `window-state-event` a cada entrada e saída de foco. Sem o filtro, cada
    volta de foco disparava os dois tiques do `_repintar_a_decoracao`, que faz
    `hide()`+`show_all()` na barra e `queue_resize` na janela inteira.
    """
    agendados: list[int] = []
    monkeypatch.setattr(
        ponte_da_tela.GLib,
        "timeout_add",
        lambda atraso, _fn: agendados.append(atraso) or 1,
    )
    quem = _quem_escuta()
    quem._a_barra_se_refaz(None, _evento_de_estado(Gdk.WindowState.FOCUSED, 0))
    assert agendados == [], (
        "trocar de foco não muda a geometria da janela, e o redesenho custa "
        "uma barra escondida e mostrada de novo"
    )


def test_maximizar_continua_agendando_os_dois_tiques(monkeypatch: Any) -> None:
    """A MORDIDA do filtro: se ele pegar demais, a cura de pintura morre junto."""
    agendados: list[int] = []
    monkeypatch.setattr(
        ponte_da_tela.GLib,
        "timeout_add",
        lambda atraso, _fn: agendados.append(atraso) or 1,
    )
    quem = _quem_escuta()
    quem._a_barra_se_refaz(
        None,
        _evento_de_estado(Gdk.WindowState.MAXIMIZED, Gdk.WindowState.MAXIMIZED),
    )
    assert agendados == list(ponte_da_tela.JanelaDaAba.ATRASOS_DO_REDESENHO_MS)


def test_maximizar_junto_com_o_foco_ainda_agenda(monkeypatch: Any) -> None:
    """O compositor manda os dois bits juntos, e o filtro não pode engolir isso."""
    agendados: list[int] = []
    monkeypatch.setattr(
        ponte_da_tela.GLib,
        "timeout_add",
        lambda atraso, _fn: agendados.append(atraso) or 1,
    )
    quem = _quem_escuta()
    quem._a_barra_se_refaz(
        None,
        _evento_de_estado(
            Gdk.WindowState.MAXIMIZED | Gdk.WindowState.FOCUSED,
            Gdk.WindowState.MAXIMIZED | Gdk.WindowState.FOCUSED,
        ),
    )
    assert agendados == list(ponte_da_tela.JanelaDaAba.ATRASOS_DO_REDESENHO_MS)


def test_o_evento_veste_o_botao_mesmo_sem_agendar_redesenho(monkeypatch: Any) -> None:
    """A cara do botão vem do EVENTO, e o filtro do foco não a atrasa.

    `Gtk.Window.is_maximized()` lê o que o handler PADRÃO do GTK grava, e esse
    handler roda DEPOIS dos conectados com `connect`: perguntar a ele aqui
    devolveria o estado de antes, e o botão viveria um gesto atrasado.
    """
    monkeypatch.setattr(ponte_da_tela.GLib, "timeout_add", lambda _a, _f: 1)
    quem = _quem_escuta()
    botao = quem._botoes_da_barra["maximizar"]
    quem._a_barra_se_refaz(
        None,
        _evento_de_estado(Gdk.WindowState.MAXIMIZED, Gdk.WindowState.MAXIMIZED),
    )
    assert _icone(botao) == "window-restore-symbolic"
    quem._a_barra_se_refaz(None, _evento_de_estado(Gdk.WindowState.MAXIMIZED, 0))
    assert _icone(botao) == "window-maximize-symbolic"


# -- a barra no jeito do vizinho (22/09/2026) ---------------------------------


def _girar_o_laco(ms: int) -> None:
    """Roda o laço do GTK por `ms`. SEM ELE O ESTILO NÃO SE RECALCULA.

    Medido ao escrever esta régua: com `set_state_flags(PRELIGHT)` e só o
    `events_pending()`, o botão responde a cor de REPOUSO mesmo com o nó já
    dizendo `:hover` — e a régua daria "o hover não pinta" sobre um hover que
    pinta. O estilo é validado no tique do relógio de quadros.
    """
    from gi.repository import GLib, Gtk

    GLib.timeout_add(ms, Gtk.main_quit)
    Gtk.main()


def test_a_barra_tem_a_altura_do_vizinho_e_os_botoes_sem_pilula() -> None:
    """*"altura da barra de navegação tá diferente do padrão e tem um circulo
    transparente em cada botão minimizar maximizar fechar"* — ela, 22/09/2026.

    A barra presa a uma janela DE VERDADE (nunca mostrada) pede no máximo
    `ALTURA_DA_BARRA` + 1 px (a borda de baixo do tema); o botão não tem fundo
    em repouso, e tem no `:hover`, para o clique continuar respondendo.

    A MORDIDA: esvazie `CSS_DA_BARRA` e as três asserções reprovam — a barra
    volta aos 47 px do tema e o botão à pílula branca a 10 %.
    """
    from gi.repository import Gtk

    barra, botoes = _barra_de_verdade()
    janela = Gtk.Window(title="nunca mostrada")
    janela.set_titlebar(barra)
    barra.show_all()
    altura = barra.get_preferred_height()[1]
    janela.destroy()
    assert altura <= ponte_da_tela.ALTURA_DA_BARRA + 1, (
        f"a barra pede {altura} px; o combinado é {ponte_da_tela.ALTURA_DA_BARRA}")

    barra, botoes = _barra_de_verdade()
    oculta = Gtk.OffscreenWindow()
    oculta.add(barra)
    oculta.show_all()
    _girar_o_laco(150)
    for gesto, botao in botoes.items():
        ctx = botao.get_style_context()
        fundo = ctx.get_property("background-color", ctx.get_state())
        assert fundo.alpha == 0, f"o botão {gesto!r} tem fundo em repouso: {fundo.to_string()}"
    fechar = botoes["fechar"]
    fechar.set_state_flags(Gtk.StateFlags.PRELIGHT, False)
    _girar_o_laco(150)
    ctx = fechar.get_style_context()
    fundo = ctx.get_property("background-color", ctx.get_state())
    oculta.destroy()
    assert fundo.alpha > 0, "o botão não responde ao mouse por cima — o clique ficou mudo"
