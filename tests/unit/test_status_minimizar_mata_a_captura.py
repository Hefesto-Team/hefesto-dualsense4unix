"""STATUS-DIZ-O-QUE-VÊ-01/T8 e T11 — a privacidade prometida por escrito.

`set_status_tab_visivel` promete, na própria docstring, que sair da aba mata o
`parec` de cada controle *"com a janela em outra aba — ou minimizada"*. E o
`docs/usage/interface.md` repetia a promessa para quem usa o produto.

Havia DOIS gatilhos, e nenhum dos dois é a minimização:

    $ grep -rn "window-state-event\\|iconified" src/hefesto_dualsense4unix/app/
    (nada)

Com a aba Status à vista e a janela minimizada, a captura do microfone da
usuária continuava viva. Não era teoria: era a ausência de gancho, medida.

**O que este arquivo NÃO afirma** (e é o cabeçalho mais valioso desta casa): que
o `parec` sobreviva à minimização na sessão COSMIC dela. Isso está declarado
NÃO VERIFICADO na §3 da sprint e continua — o processo vivo não foi observado.
O que se mede aqui é o gancho: ele existe, está ligado, e diz o que tem de
dizer nos quatro estados.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status: minimizar mata a captura")

import ast
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.status_actions import ABA_STATUS
from hefesto_dualsense4unix.app.app import HefestoApp

_RAIZ = Path(__file__).resolve().parents[2]
_APP_PY = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "app.py"
_INTERFACE_MD = _RAIZ / "docs" / "usage" / "interface.md"


class _JanelaDublada:
    """Registra o que foi conectado nela, e nada mais."""

    def __init__(self) -> None:
        self.conectados: list[str] = []

    def connect(self, sinal: str, _cb: Any) -> int:
        self.conectados.append(sinal)
        return len(self.conectados)


class _NotebookDublado:
    def __init__(self, aba: str | None) -> None:
        self._aba = aba

    def get_current_page(self) -> int:
        return 0

    def get_nth_page(self, _i: int) -> Any:
        return self._aba


class _BuilderDublado:
    def __init__(self, notebook: Any) -> None:
        self._notebook = notebook

    def get_object(self, nome: str) -> Any:
        return self._notebook if nome == "main_notebook" else None


class _AppDublado:
    """O mínimo que os três métodos de produção leem em ``self``.

    **Não é uma reimplementação:** os métodos exercitados abaixo são os de
    `HefestoApp`, chamados sem ligar (`HefestoApp._on_window_state_event(...)`).
    Montar a `HefestoApp` inteira exigiria Glade, IPC e daemon — e mediria
    tudo menos o gancho.
    """

    _ABA_STATUS = ABA_STATUS

    # Os TRÊS métodos vêm da `HefestoApp`, sem cópia. Sem isto o dublê seria
    # a régua que só sabe passar: o produto envolve a chamada num
    # `contextlib.suppress(Exception)` e um método que falta no dublê vira
    # silêncio — o teste passaria com o gancho arrancado.
    _ligar_gancho_de_minimizacao = HefestoApp._ligar_gancho_de_minimizacao
    _on_window_state_event = HefestoApp._on_window_state_event
    _aba_status_esta_a_vista = HefestoApp._aba_status_esta_a_vista

    def __init__(self, *, aba_a_vista: str | None) -> None:
        self.window = _JanelaDublada()
        self.builder = _BuilderDublado(_NotebookDublado(aba_a_vista))
        self.recebeu: list[bool] = []

    def set_status_tab_visivel(self, visivel: bool) -> None:
        self.recebeu.append(visivel)


class _Evento:
    def __init__(self, estado: Any) -> None:
        self.new_window_state = estado


def _paginas_com_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """`id_da_pagina_corrente` passa a devolver o dublê de página cru.

    O dublê não é `Gtk.Buildable`, e a função de produção devolveria `None`
    para ele — o teste passaria por acidente, com a aba SEMPRE fora de vista.
    Isto é a armadilha do dublê que só sabe passar; aqui ela fica desarmada.
    """
    import hefesto_dualsense4unix.app.app as app_mod

    monkeypatch.setattr(
        app_mod,
        "id_da_pagina_corrente",
        lambda notebook: None if notebook is None else notebook.get_nth_page(0),
    )


def test_minimizar_mata_a_captura(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o bit ICONIFIED, o dublê recebe ``False``.

    **A mordida:** arranque o corpo do `_on_window_state_event` (ou o
    `janela.connect` do `_ligar_gancho_de_minimizacao`) e o dublê nunca
    recebe `False` — a lista fica vazia e o teste reprova dizendo isso.
    """
    from gi.repository import Gdk

    _paginas_com_id(monkeypatch)
    app = _AppDublado(aba_a_vista=ABA_STATUS)
    app._on_window_state_event(app.window, _Evento(Gdk.WindowState.ICONIFIED))

    assert app.recebeu == [False], (
        "minimizar a janela com a aba Status à vista não desligou a captura: "
        f"o dublê recebeu {app.recebeu}. O `parec` de cada controle continua "
        "capturando o microfone dela sem ninguém olhando o medidor"
    )


def test_restaurar_devolve_a_captura_so_na_aba_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A volta é condicional, e a condição é a MESMA do `switch-page`.

    Sem esta metade, minimizar uma vez deixaria o medidor morto até a próxima
    troca de aba. Com ela mal feita — religar sempre —, restaurar a janela
    ligaria uma captura que a troca de aba tinha desligado.

    **A mordida:** troque a condição por `True` fixo e o segundo caso reprova.
    """
    from gi.repository import Gdk

    _paginas_com_id(monkeypatch)
    sem_bit = Gdk.WindowState(0)

    na_status = _AppDublado(aba_a_vista=ABA_STATUS)
    na_status._on_window_state_event(na_status.window, _Evento(sem_bit))
    assert na_status.recebeu == [True], (
        "restaurar a janela com a aba Status à vista tem de devolver a "
        f"captura: o dublê recebeu {na_status.recebeu}"
    )

    noutra_aba = _AppDublado(aba_a_vista="tab_config_box")
    noutra_aba._on_window_state_event(noutra_aba.window, _Evento(sem_bit))
    assert noutra_aba.recebeu == [False], (
        "restaurar a janela numa aba que NÃO é a Status ligou a captura: o "
        f"dublê recebeu {noutra_aba.recebeu}. A régua da volta é a mesma do "
        "`switch-page` — a aba à vista"
    )


def test_o_gancho_esta_ligado_de_verdade() -> None:
    """A metade "a casa sabe e o produto não faz".

    O defeito mais caro desta casa é a cura escrita e nunca ligada. Um
    handler perfeito que ninguém conecta é exatamente isso, e foi assim que a
    promessa da docstring atravessou meses.

    **A mordida, e são duas:** apague o `janela.connect(...)` do
    `_ligar_gancho_de_minimizacao` e o primeiro `assert` reprova; apague a
    chamada dele de dentro do `show()` e o segundo reprova nomeando a linha
    que falta.
    """
    app = _AppDublado(aba_a_vista=ABA_STATUS)
    app._ligar_gancho_de_minimizacao()
    assert "window-state-event" in app.window.conectados, (
        "o `window-state-event` não foi conectado na janela: o handler "
        f"existe e ninguém o chama. Conectados: {app.window.conectados}"
    )

    arvore = ast.parse(_APP_PY.read_text(encoding="utf-8"))
    show = next(
        (
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "show"
        ),
        None,
    )
    assert show is not None, "o `HefestoApp.show` sumiu — o teste perdeu o alvo"
    chamadas = {
        no.func.attr
        for no in ast.walk(show)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }
    assert "_ligar_gancho_de_minimizacao" in chamadas, (
        "o `show()` não chama `_ligar_gancho_de_minimizacao`: o gancho existe "
        "mas nunca é instalado na janela de verdade"
    )


def test_o_gancho_nunca_consome_o_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ele observa; quem trata `window-state-event` é o GTK.

    Devolver `True` num handler de evento do GTK PARA a propagação. Aqui isso
    silenciaria maximizar, focar e o resto do estado da janela — um defeito
    que só apareceria na tela dela, meses depois.

    **A mordida:** troque os `return False` por `return True`.
    """
    from gi.repository import Gdk

    _paginas_com_id(monkeypatch)
    app = _AppDublado(aba_a_vista=ABA_STATUS)
    saida = app._on_window_state_event(app.window, _Evento(Gdk.WindowState.ICONIFIED))
    assert saida is False, (
        f"o gancho devolveu {saida!r} e consumiu o evento de estado da "
        "janela: maximizar, focar e restaurar param de chegar a quem trata"
    )


def test_a_promessa_nao_e_maior_do_que_o_gancho() -> None:
    """T11 — o documento não promete o que o código não faz.

    **Esta mordida foi escrita agora; a sprint não declarou nenhuma para T11**
    ("o portão de referências e o de acentuação já rodam; o que falta é a
    foto"). Foto não é régua: ela prova o pixel de um dia, não impede a frase
    de voltar a mentir no dia seguinte.

    A régua é de MÃO DUPLA, e é essa a graça:

    * o `interface.md` só pode citar a minimização enquanto o gancho existir
      no código;
    * e não pode mais descrever a linha "No jogo agora: …" da aba Status, que
      saiu da tela em 17/08/2026 e ficou oito dias descrita no documento.

    **A mordida:** apague o `window-state-event` do `app.py` e o primeiro
    reprova; devolva o parágrafo antigo ao documento e o segundo reprova.
    """
    doc = _INTERFACE_MD.read_text(encoding="utf-8")

    if "minimiza" in doc:
        # AST e não `grep`: a própria docstring do gancho CITA o nome do
        # sinal, e um `grep` acharia a citação e daria o portão por
        # satisfeito com o `connect` arrancado — foi o que aconteceu na
        # primeira versão desta régua, e é a armadilha do instrumento que
        # mede a si mesmo.
        arvore = ast.parse(_APP_PY.read_text(encoding="utf-8"))
        conecta = any(
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "connect"
            and no.args
            and isinstance(no.args[0], ast.Constant)
            and no.args[0].value == "window-state-event"
            for no in ast.walk(arvore)
        )
        assert conecta, (
            "o `interface.md` promete que a leitura morre ao minimizar e o "
            "`app.py` não conecta `window-state-event` em lugar nenhum — a "
            "promessa por escrito é a forma mais cara de defeito desta casa"
        )

    assert "No jogo agora" not in doc, (
        "o `interface.md` volta a descrever a linha 'No jogo agora: …' como "
        "estando na aba Status. Ela não está lá desde 17/08/2026 — a "
        "SEM-BARRA-DA-VERDADE-01 a tirou a pedido dela"
    )
