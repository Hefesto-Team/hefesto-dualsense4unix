"""O botão do meio da barra diz o que o clique VAI FAZER — e diz em português."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a barra da janela da interface nova")

from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

from hefesto_dualsense4unix.interface import janela as ponte_da_tela


def _barra_de_verdade() -> tuple[Any, dict[str, Any]]:
    """A barra do produto, montada pelo dono dela. Nenhuma janela é aberta."""
    return ponte_da_tela.montar_a_barra("Hefesto", "aba CONTROLES", lambda *_: None)


def _icone(botao: Any) -> str:
    return str(botao.get_image().get_icon_name()[0])


def _nome_acessivel(botao: Any) -> str:
    return str(botao.get_accessible().get_name())


def test_os_dois_estados_do_maximizar_sao_icones_diferentes() -> None:
    """Restaurada e maximizada não podem desenhar o mesmo ícone."""
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
    """`BOTOES_DA_BARRA` e `APARENCIA_DO_MAXIMIZAR` são o mesmo valor, um dono."""
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


def test_a_barra_tem_a_altura_do_vizinho_e_os_botoes_sem_pilula() -> None:
    """*"altura da barra de navegação tá diferente do padrão e tem um circulo"""
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


def test_a_janela_oculta_nao_estoura_por_nao_ter_barra() -> None:
    """`Gtk.OffscreenWindow` não tem barra, e isso não é erro — é o desenho."""
    assert ponte_da_tela.vestir_a_cara_do_maximizar({}, True) is False


def test_os_tres_botoes_tem_nome_acessivel_em_portugues() -> None:
    """O que o leitor de tela anuncia é a MESMA palavra que a dica mostra."""
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


_SONDA_DO_LOCALE = """
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
from hefesto_dualsense4unix.interface.janela import montar_a_barra
barra, botoes = montar_a_barra("Hefesto", "", lambda *_: None)
for gesto in ("fechar", "maximizar", "minimizar"):
    print(gesto, botoes[gesto].get_accessible().get_name(), sep="=")
"""


def test_o_nome_acessivel_nao_segue_o_locale() -> None:
    """Nem o «fechar» se salva fora do pt_BR — e a garantia não pode depender disso."""
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


def _evento_de_estado(mudou: Any, novo: Any) -> Any:
    evento = Gdk.EventWindowState()
    evento.changed_mask = mudou
    evento.new_window_state = novo
    return evento


class _JanelaMuda:
    """Só o que o handler toca. Nenhuma janela de verdade é criada."""

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
    """Ela alterna entre o terminal e a janela o dia todo — e isso não é geometria."""
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
    """A cara do botão vem do EVENTO, e o filtro do foco não a atrasa."""
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


def _girar_o_laco(ms: int) -> None:
    """Roda o laço do GTK por `ms`. SEM ELE O ESTILO NÃO SE RECALCULA."""
    from gi.repository import GLib, Gtk

    GLib.timeout_add(ms, Gtk.main_quit)
    Gtk.main()


