"""O "desligar de verdade" nunca foi executado por teste nenhum — I8.

INÍCIO NÃO MENTE-01, §2.2i. O botão que PARA o produto, arma
``_user_stopped_daemon`` (para a GUI não o ressuscitar no próximo
``ensure_daemon_running``) e tem cura própria contra falso-OK
(BUG-HOME-SHUTDOWN-FALSE-OK-01: ``rc != 0`` desarma o flag e troca o toast)
**nunca rodou dentro de um teste**. Os três arquivos que o citam fazem outra
coisa:

* ``test_home_render_state.py:357`` e ``:369`` **substituem** o método por um
  ``lambda`` — medem o dispatcher do botão único, não o desligar;
* ``test_gui_dialogs_theme.py`` lê o **texto-fonte** dele com
  ``inspect.getsource`` procurando a classe de tema;
* ``test_daemon_toasts_leigo.py`` testa outra função, em outro caminho.

Uma cura de regressão sem mordida é uma cura que volta. E aqui o preço da volta
é caro dos dois lados: com o flag armado por engano a GUI deixa de religar um
daemon que nunca parou; com ele desarmado por engano, ela ressuscita o daemon
que ela mandou parar.

O QUE ESTE ARQUIVO **NÃO** DECIDE
----------------------------------

A segunda metade do toast de falha manda *"tente pela aba Sistema"* — o forte
mandando para o fraco, que usa o MESMO ``systemctl --user stop`` e vai falhar
igual. É a **D-F** da sprint, e é palavra dela. Aqui o texto é MEDIDO como
está; nenhum teste daqui o abençoa.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin


#: Os diálogos que o clique criou. Lista de MÓDULO, e não atributo de
#: classe: uma lista como default de classe é compartilhada por toda
#: instância, e o que se quer aqui é exatamente isso — mas dito de um jeito
#: que não pareça estado por objeto.
_DIALOGOS_CRIADOS: list[Any] = []


class _Dialogo:
    """O `Gtk.MessageDialog` do desligar, o bastante para o método rodar.

    Guarda o handler de "response" para o teste poder RESPONDER — é isso que
    faz este arquivo executar o corpo do desligar em vez de só montar a caixa.
    """

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.secundario: str | None = None
        self.handlers: dict[str, Any] = {}
        self.destruido = False
        self.classes: list[str] = []
        _DIALOGOS_CRIADOS.append(self)

    def get_style_context(self) -> Any:
        return SimpleNamespace(add_class=self.classes.append)

    def format_secondary_text(self, texto: str) -> None:
        self.secundario = texto

    def connect(self, sinal: str, handler: Any) -> None:
        self.handlers[sinal] = handler

    def destroy(self) -> None:
        self.destruido = True

    def responder(self, resposta: int) -> None:
        self.handlers["response"](self, resposta)


class _HostDoDesligar:
    """O host mínimo do `_on_home_shutdown_clicked`, e nada além.

    Dublê PARCIAL de propósito (mesmo desenho do `_HomeStub` de
    `test_home_render_state.py`): o método só toca `_get`, `_status_toast`,
    `_refresh_home_tab` e o flag. Montar a aba inteira aqui faria a régua
    depender de widget que este caminho não usa.
    """

    _on_home_shutdown_clicked = HomeActionsMixin._on_home_shutdown_clicked

    def __init__(self) -> None:
        self.toasts: list[tuple[str, str]] = []
        self.refreshs = 0
        self.user_stopped_registros: list[bool] = []

    def _get(self, _nome: str) -> None:
        # `main_window` não existe num dublê: o diálogo aceita `transient_for`
        # nulo, e é assim que a janela real se comporta antes do bootstrap.
        return None

    def _status_toast(self, contexto: str, msg: str) -> None:
        self.toasts.append((contexto, msg))

    def _refresh_home_tab(self) -> None:
        self.refreshs += 1

    def __setattr__(self, nome: str, valor: Any) -> None:
        # O flag é o objeto da medição: guardar a SEQUÊNCIA de escritas separa
        # "armou e desarmou" de "nunca armou" — e é essa diferença que a cura
        # do falso-OK produz.
        if nome == "_user_stopped_daemon":
            self.user_stopped_registros.append(bool(valor))
        object.__setattr__(self, nome, valor)


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Gtk falso, diálogo capturado, worker SÍNCRONO e `systemctl` de mentira.

    O worker roda na hora (nada de thread) porque o que se mede é a DECISÃO
    tomada com o resultado na mão, não a mecânica do `run_in_thread` — que tem
    régua própria. E o `subprocess.run` é trocado para nenhum teste desta casa
    parar o daemon de verdade: a bancada é dela (R3).
    """
    _DIALOGOS_CRIADOS.clear()
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        MessageDialog=_Dialogo,
        MessageType=SimpleNamespace(QUESTION=1),
        ButtonsType=SimpleNamespace(YES_NO=2),
        ResponseType=SimpleNamespace(YES=-8, NO=-9),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)

    mostrados: list[_Dialogo] = []
    monkeypatch.setattr(
        gui_dialogs,
        "mostrar_dialogo_assincrono",
        lambda dlg, nome=None: mostrados.append(dlg),
    )

    from hefesto_dualsense4unix.app import ipc_bridge

    estado: dict[str, Any] = {
        "mostrados": mostrados,
        "resultado": SimpleNamespace(returncode=0, stderr=b""),
        "comandos": [],
    }

    def _run_in_thread(worker: Any, ok: Any, _erro: Any) -> None:
        # O worker RODA, e o que chega ao `ok` é o retorno DELE — não um
        # resultado inventado aqui. É essa a diferença entre medir a decisão do
        # produto e medir o dublê: com o worker pulado, o `subprocess.run` de
        # verdade nunca é montado e o comando que o botão dispara fica sem
        # régua.
        estado["comandos"].append(worker)
        ok(worker())

    monkeypatch.setattr(ipc_bridge, "run_in_thread", _run_in_thread)

    import subprocess

    chamadas: list[list[str]] = []

    def _run(cmd: list[str], **_kwargs: Any) -> Any:
        chamadas.append(list(cmd))
        return estado["resultado"]

    monkeypatch.setattr(subprocess, "run", _run)
    estado["chamadas"] = chamadas
    return estado


def _clicar_e_responder(
    host: _HostDoDesligar, bancada: dict[str, Any], resposta: int
) -> None:
    host._on_home_shutdown_clicked(object())
    (dialogo,) = bancada["mostrados"]
    dialogo.responder(resposta)


def test_a_pergunta_sai_antes_de_qualquer_coisa(bancada: dict[str, Any]) -> None:
    """Clicar NÃO desliga: primeiro pergunta, e o diálogo é assíncrono.

    `dialog.show()` cru num diálogo `modal=True` instala o grab do GTK e, se a
    janela não chegar ao servidor, prende a janela dela inteira — clique, tecla
    e o "X", os três (DIALOGO-QUE-MATA-A-JANELA-01). Por isso quem mostra é o
    `mostrar_dialogo_assincrono`, e é isso que se mede aqui.
    """
    host = _HostDoDesligar()

    host._on_home_shutdown_clicked(object())

    assert len(bancada["mostrados"]) == 1
    assert not bancada["chamadas"], "o `systemctl` saiu antes de ela responder"
    assert host.user_stopped_registros == []


def test_resposta_nao_nao_faz_nada(bancada: dict[str, Any]) -> None:
    """O caminho mais barato de errar: desligar quem disse que não quer.

    Nada de flag, nada de `systemctl`, nada de toast — e o diálogo fecha.
    """
    host = _HostDoDesligar()

    _clicar_e_responder(host, bancada, -9)  # ResponseType.NO

    (dialogo,) = bancada["mostrados"]
    assert dialogo.destruido is True
    assert host.user_stopped_registros == []
    assert bancada["chamadas"] == []
    assert host.toasts == []
    assert host.refreshs == 0


def test_rc_zero_arma_o_flag_e_diz_desligado(bancada: dict[str, Any]) -> None:
    """O caminho feliz: parou, e a GUI não o ressuscita no próximo `ensure`."""
    host = _HostDoDesligar()
    bancada["resultado"] = SimpleNamespace(returncode=0, stderr=b"")

    _clicar_e_responder(host, bancada, -8)  # ResponseType.YES

    assert host.user_stopped_registros == [True], (
        "o flag tem de ficar ARMADO: é ele que o `ensure_daemon_running` "
        "respeita para não religar o daemon que ela mandou parar"
    )
    assert host._user_stopped_daemon is True
    assert bancada["chamadas"] == [
        [
            "systemctl",
            "--user",
            "stop",
            "hefesto-dualsense4unix.service",
        ]
    ]
    (contexto, msg) = host.toasts[-1]
    assert contexto == "home"
    assert "desligado" in msg.lower()
    assert host.refreshs == 1


def test_rc_diferente_de_zero_desarma_o_flag_e_nao_diz_desligado(
    bancada: dict[str, Any],
) -> None:
    """A MORDIDA. `systemctl` com rc!=0 não desligou nada — e o toast não pode
    mentir nem o flag ficar armado.

    BUG-HOME-SHUTDOWN-FALSE-OK-01: sem sessão systemd, ou com o daemon avulso,
    o `stop` volta com rc!=0 e o produto continua de pé. Se o flag ficasse
    armado, a GUI pararia de religar um daemon que ela nunca conseguiu parar —
    e a pessoa ficaria sem luzes, sem gatilhos e sem explicação.

    Arranque a linha ``self._user_stopped_daemon = False`` do ramo de falha e
    este teste reprova: a sequência de escritas passa a ser ``[True]``.
    """
    host = _HostDoDesligar()
    bancada["resultado"] = SimpleNamespace(
        returncode=1, stderr=b"Failed to stop hefesto-dualsense4unix.service"
    )

    _clicar_e_responder(host, bancada, -8)  # ResponseType.YES

    assert host.user_stopped_registros == [True, False], (
        "o flag foi armado antes de o worker sair (é o desenho) e tinha de ser "
        "DESARMADO quando o `systemctl` falhou. Sem isso a GUI passa a tratar "
        "um daemon vivo como parado por decisão dela."
    )
    assert host._user_stopped_daemon is False
    (contexto, msg) = host.toasts[-1]
    assert contexto == "home"
    assert "Hefesto desligado" not in msg, (
        f"o toast anuncia desligamento sobre uma falha: {msg!r}. É a mesma "
        "família do 'aplicado' sem prova que esta casa persegue desde a "
        "APLICAR-VERDADE-01."
    )
    assert host.refreshs == 1


def test_o_texto_da_falha_ainda_manda_para_a_aba_sistema(
    bancada: dict[str, Any],
) -> None:
    """MEDIÇÃO, não aprovação: a **D-F** está em aberto e é dela.

    Este teste existe para que a decisão dela tenha um lugar onde aterrissar —
    e para que, se alguém mudar o texto antes de ela decidir, o vermelho apareça
    aqui em vez de na tela. Hoje o forte manda para o fraco: a aba Sistema roda
    o MESMO `systemctl --user stop` e vai falhar igual.
    """
    host = _HostDoDesligar()
    bancada["resultado"] = SimpleNamespace(returncode=1, stderr=b"")

    _clicar_e_responder(host, bancada, -8)

    assert "aba Sistema" in host.toasts[-1][1]
