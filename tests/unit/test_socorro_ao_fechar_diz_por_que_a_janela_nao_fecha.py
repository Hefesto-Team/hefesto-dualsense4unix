"""O X não fecha a janela — e agora a tela DIZ por quê (23/08/2026).

O diálogo de fechamento nascido em 23/08 (achado A5) usa
``resposta_de_socorro=CANCEL``: se ele ficar inalcançável — o quadro de
06/08/2026, em que um modal invisível prendeu a janela dela —, o envelope da
casa responde CANCELAR por ela, e o X **deixa de fechar a janela**.

A escolha do socorro está CERTA e é decisão declarada: um Enter distraído nunca
pode custar edição não salva. O que faltava era a FRASE. Uma janela que não
fecha e não explica é indistinguível de uma janela travada — que é exatamente o
sintoma que o envelope existe para curar.

O que este módulo cobra:

* **os dois cancelamentos são coisas diferentes**, e a casa distingue: cancelar
  porque ela clicou não diz nada no rodapé; cancelar porque a pergunta não
  apareceu diz;
* **a testemunha central roda com GTK de verdade, sob ``xvfb-run``, num
  subprocesso** (mesma aparelhagem e mesmo motivo de
  ``test_dialogo_nao_mata_a_janela.py``: o envelope chama ``present()`` num
  toplevel real, e fazer isso no processo do ``pytest`` abriria uma janela na
  tela dela). Lá o socorro é FORÇADO pela sabotagem contínua do ``GdkWindow``,
  e o teste lê o rodapé de verdade — o ``Gtk.Statusbar`` que a janela usa.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, de propósito.
exigir_gi_real("socorro ao fechar a janela")

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app import app as app_module
from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.app import HefestoApp

_RAIZ = Path(__file__).resolve().parents[2]

#: Prazo do subprocesso. Generoso para máquina carregada e MUITO menor que
#: "para sempre": é ele que transforma um estrangulamento em teste vermelho.
_PRAZO_S = 40.0

DECLARACAO = {"orcamento": {"teto": "equilibrado"}}


# ---------------------------------------------------------------------------
# 1. A testemunha central: GTK real, socorro forçado, rodapé lido de verdade
# ---------------------------------------------------------------------------

_ROTEIRO = """
import json, sys
sys.path.insert(0, {raiz!r})
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.app import HefestoApp

assert Gtk.init_check(None)[0], "o GTK falhou ao iniciar sob o Xvfb"

# O vigia julga em ~160 ms em vez de ~3,5 s: o que se mede aqui é a DECISÃO,
# não a paciência do relógio.
gui_dialogs.PRAZO_ATE_O_SOCORRO_MS = 80
gui_dialogs.PRAZO_ATE_DESISTIR_MS = 80

marcas = {{}}
barra = Gtk.Statusbar()

janela = HefestoApp.__new__(HefestoApp)
janela._quitting = False
janela.window = Gtk.Window()
janela.window.set_title("janela principal de mentira")
janela.window.show_all()
janela._maquina_pendente = {{"orcamento": {{"teto": "equilibrado"}}}}
# Este ramo é o que ENCERRA: sem bandeja e sem janela compacta.
janela._has_persistent_access = lambda: False
janela._get = lambda wid: barra if wid == "status_bar" else None
janela._gravar_declaracao_de_maquina = lambda: (
    marcas.__setitem__("gravou", True) or (True, "Configurações gravadas.")
)
Gtk.main_quit = lambda *a: marcas.__setitem__("saiu", True)


def _o_dialogo():
    vivos = [
        w for w in Gtk.Window.list_toplevels()
        if isinstance(w, Gtk.MessageDialog)
    ]
    return vivos[0] if vivos else None


def _o_compositor_se_recusa():
    # Sabotagem CONTÍNUA: é assim que se comporta um compositor que não vai
    # mostrar a janela — não adianta pedir de novo. Com sabotagem única o
    # socorro RESSUSCITA o diálogo (medido em test_dialogo_nao_mata_a_janela).
    d = _o_dialogo()
    if d is None or d.get_window() is None:
        return True
    d.get_window().hide()
    return True


GLib.timeout_add(20, _o_compositor_se_recusa)

marcas["segurou_a_janela"] = bool(janela.on_window_delete_event(None, None))
marcas["socorro"] = gui_dialogs.ultimo_socorro()
marcas["pendente_sobreviveu"] = janela._maquina_pendente == {{
    "orcamento": {{"teto": "equilibrado"}}
}}

# O RODAPÉ, lido do widget de verdade — não do dublê de quem escreve nele.
area = barra.get_message_area()
marcas["rodape"] = " ".join(
    filho.get_text()
    for filho in area.get_children()
    if isinstance(filho, Gtk.Label) and filho.get_text()
)
marcas["dialogos_restantes"] = sum(
    1 for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.MessageDialog)
)
print("HEFESTO_JSON " + json.dumps(marcas))
"""


def _sob_xvfb(tmp_path: Path) -> dict[str, Any]:
    """Roda o roteiro com GTK real num display descartável; devolve as marcas."""
    if shutil.which("xvfb-run") is None:  # pragma: no cover — máquina sem xvfb
        pytest.skip("sem `xvfb-run` — este teste exige um display descartável")

    ambiente = dict(os.environ)
    # CANÁRIO-FS-01: o subprocesso não escreve no home de verdade.
    ambiente["HOME"] = str(tmp_path)
    ambiente["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    ambiente["XDG_DATA_HOME"] = str(tmp_path / "data")
    ambiente["GDK_BACKEND"] = "x11"
    ambiente.pop("WAYLAND_DISPLAY", None)
    script = _ROTEIRO.format(raiz=str(_RAIZ / "src"))
    try:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=_PRAZO_S,
            check=False,
            env=ambiente,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o diálogo de fechamento ESTRANGULOU a janela: o processo passou "
            f"de {_PRAZO_S:.0f}s sem devolver resposta — é o defeito de "
            "06/08/2026 voltando pelo caminho do X."
        )
    if proc.returncode != 0:
        pytest.fail(f"o subprocesso GTK falhou (rc={proc.returncode}):\n{proc.stderr}")
    for linha in proc.stdout.splitlines():
        if linha.startswith("HEFESTO_JSON "):
            return dict(json.loads(linha[len("HEFESTO_JSON ") :]))
    pytest.fail(f"o subprocesso não imprimiu as marcas:\n{proc.stdout}\n{proc.stderr}")


def test_o_x_nao_fecha_e_o_rodape_explica(tmp_path: Path) -> None:
    """As duas metades juntas, com o socorro forçado num GTK de verdade.

    (a) a janela NÃO encerra — a declaração dela continua de pé; e
    (b) o rodapé DIZ o que houve e qual é a saída.

    Antes desta leva só (a) acontecia, e uma janela que não fecha sem uma
    palavra é indistinguível de uma janela travada.
    """
    marcas = _sob_xvfb(tmp_path)

    # Instrumento válido: o socorro REALMENTE disparou. Sem esta linha, um
    # diálogo que aparecesse normal e fosse cancelado por outro motivo faria o
    # teste medir o caminho errado.
    assert marcas["socorro"] == app_module.DIALOGO_DECLARACAO_AO_FECHAR, (
        "a sabotagem não levou o envelope à desistência — o teste mediria "
        f"outro caminho. Marcas: {marcas}"
    )
    assert marcas["segurou_a_janela"] is True, (
        "o delete-event tem de devolver True: com a pergunta inalcançável, "
        "fechar descartaria a declaração dela em silêncio"
    )
    assert marcas["pendente_sobreviveu"] is True
    assert marcas.get("saiu") is not True, "a janela ENCERROU no socorro"
    assert marcas["rodape"], (
        "A JANELA NÃO FECHOU E A TELA NÃO DISSE POR QUÊ. O rodapé ficou vazio "
        "depois de o envelope cancelar o fechamento por conta própria — para "
        "ela, isso é indistinguível da janela travada de 06/08/2026, e a saída "
        f"real (o Aplicar) fica invisível. Marcas: {marcas}"
    )
    assert marcas["rodape"] == app_module.frase_do_socorro_ao_fechar(), (
        "o rodapé disse outra coisa que não a frase do socorro: "
        f"{marcas['rodape']!r}"
    )
    assert marcas["dialogos_restantes"] == 0


# ---------------------------------------------------------------------------
# 2. O contrapeso: cancelamento DELA continua calado
# ---------------------------------------------------------------------------


def _janela_de_bancada(
    monkeypatch: pytest.MonkeyPatch, *, socorro: str | None, resposta: int
) -> tuple[HefestoApp, Gtk.Statusbar]:
    """`HefestoApp` sem `__init__` — só o que o fechamento toca.

    O dublê de `executar_dialogo` planta `_ULTIMO_SOCORRO` no módulo real, que
    é o mesmo canal que o envelope usa: assim o produto lê a verdade pelo
    caminho de produção, e não por um atalho que só o teste conhece.
    """
    janela = HefestoApp.__new__(HefestoApp)
    janela._quitting = False
    janela.window = Gtk.Window()
    janela._maquina_pendente = dict(DECLARACAO)
    barra = Gtk.Statusbar()
    monkeypatch.setattr(HefestoApp, "_has_persistent_access", lambda _s: False)
    monkeypatch.setattr(
        HefestoApp,
        "_get",
        lambda _s, wid: barra if wid == "status_bar" else None,
    )
    monkeypatch.setattr(app_module.Gtk, "main_quit", lambda: None)
    monkeypatch.setattr(gui_dialogs, "_ULTIMO_SOCORRO", socorro, raising=False)

    def _responder(_dialog: Any, *, nome: str, **_kw: Any) -> int:
        return resposta

    monkeypatch.setattr(app_module, "executar_dialogo", _responder)
    return janela, barra


def _rodape(barra: Gtk.Statusbar) -> str:
    return " ".join(
        filho.get_text()
        for filho in barra.get_message_area().get_children()
        if isinstance(filho, Gtk.Label) and filho.get_text()
    )


def test_cancelamento_dela_nao_ganha_frase_nenhuma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela clicou "Cancelar": não há nada a explicar, e o rodapé fica quieto.

    O contrapeso do teste central. Sem ele, "curar" o defeito escrevendo a
    frase em TODO cancelamento passaria — e a frase mentiria: diria que a
    pergunta não apareceu justo quando ela acabou de respondê-la.
    """
    janela, barra = _janela_de_bancada(
        monkeypatch, socorro=None, resposta=Gtk.ResponseType.CANCEL
    )
    assert janela.on_window_delete_event(None, None) is True
    assert _rodape(barra) == "", (
        f"o rodapé falou sobre um socorro que não houve: {_rodape(barra)!r}"
    )


def test_socorro_de_outro_dialogo_nao_conta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A marca é global e a leitura tem de ser deste diálogo, não de qualquer um.

    `_ULTIMO_SOCORRO` é zerado a cada `executar_dialogo`, mas a comparação por
    NOME é o que impede a próxima refatoração de ler a marca de um diálogo
    vizinho e culpar o fechamento por ela.
    """
    janela, barra = _janela_de_bancada(
        monkeypatch,
        socorro="rebaixar_prioridade",
        resposta=Gtk.ResponseType.CANCEL,
    )
    assert janela.on_window_delete_event(None, None) is True
    assert _rodape(barra) == ""


def test_fechar_sem_aplicar_continua_saindo_calado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho feliz não pode ter sido estragado pela frase nova."""
    janela, barra = _janela_de_bancada(
        monkeypatch, socorro=None, resposta=Gtk.ResponseType.CLOSE
    )
    assert janela.on_window_delete_event(None, None) is False
    assert _rodape(barra) == ""


def test_a_frase_oferece_o_aplicar_e_nao_a_bandeja() -> None:
    """A saída oferecida tem de EXISTIR neste ramo.

    O texto sugerido na abertura da tarefa mandava usar o "Sair" da bandeja —
    e este ramo só roda com `_has_persistent_access()` FALSO, ou seja, sem
    ícone de bandeja utilizável e sem janela compacta. Mandá-la a um lugar que
    por construção não existe aqui seria trocar uma janela muda por uma
    instrução falsa.
    """
    frase = app_module.frase_do_socorro_ao_fechar()
    assert "Aplicar" in frase
    assert "bandeja" not in frase.lower(), (
        "a frase manda ela à bandeja, que neste ramo não existe: " + frase
    )
    # Diz O QUE HOUVE, não só o que fazer.
    assert "não fechei a janela" in frase
