"""Os toasts da aba Sistema não mostram comando cru nem `rc=N` (LEIGO-03).

O toast de Ligar/Desligar/auto-start era ``systemctl start
hefesto-dualsense4unix.service → rc=0``: o comando inteiro mais um código que só
um dev distingue — `rc=0` (deu certo) e `rc=1` (falhou) tinham exatamente a mesma
cara na barra de status, então a usuária não sabia se a ação funcionou.

Aqui o teste é sobre a REGRA (sucesso e falha se distinguem; nada de jargão), não
sobre uma frase específica: foi o acoplamento à frase que quebrou os testes de
status quando a aba foi reescrita.

`_on_systemctl_done` roda na thread GTK e só toca `_toast_daemon` e o refresh —
os dois dublados aqui, então nada de GTK real.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

#: Palavras que só existem porque o código usa systemd por baixo.
_JARGAO = ("systemctl", "systemd", "rc=", ".service", "unit", "daemon")

_ACTIONS = ("start", "stop", "enable", "disable")


class _Host:
    """Instância mínima com o que `_on_systemctl_done` toca."""

    _on_systemctl_done = DaemonActionsMixin._on_systemctl_done

    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.refreshes = 0

    def _toast_daemon(self, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_daemon_view_async(self) -> None:
        self.refreshes += 1


def _toast(action: str, rc: int) -> str:
    host = _Host()
    host._on_systemctl_done(action, "hefesto-dualsense4unix.service", rc)
    (msg,) = host.toasts
    return msg


@pytest.mark.parametrize("action", _ACTIONS)
def test_sucesso_nao_vaza_jargao(action: str) -> None:
    msg = _toast(action, 0)
    for palavra in _JARGAO:
        assert palavra not in msg, f"{action} (ok) mostra {palavra!r}: {msg!r}"


@pytest.mark.parametrize("action", _ACTIONS)
def test_falha_nao_vaza_jargao(action: str) -> None:
    msg = _toast(action, 1)
    for palavra in _JARGAO:
        assert palavra not in msg, f"{action} (falha) mostra {palavra!r}: {msg!r}"


@pytest.mark.parametrize("action", _ACTIONS)
def test_sucesso_e_falha_dizem_coisas_diferentes(action: str) -> None:
    """O ponto do item: com "→ rc=0"/"→ rc=1" as duas mensagens eram gêmeas."""
    assert _toast(action, 0) != _toast(action, 1)


def test_cada_acao_diz_o_que_mudou() -> None:
    """Ligar e desligar não podem produzir o mesmo texto."""
    assert _toast("start", 0) != _toast("stop", 0)
    assert _toast("enable", 0) != _toast("disable", 0)


def test_acao_desconhecida_nao_quebra_nem_fica_vazia() -> None:
    """Uma ação sem frase mapeada cai num texto genérico — nunca em KeyError."""
    assert _toast("reload", 0)
    assert _toast("reload", 1)


@pytest.mark.parametrize("rc", [0, 1])
def test_sempre_reconcilia_a_view(rc: int) -> None:
    """A reescrita do texto não pode ter derrubado o refresh do estado."""
    host = _Host()
    resultado = host._on_systemctl_done("start", "hefesto-dualsense4unix.service", rc)

    assert host.refreshes == 1
    # GLib.idle_add: False = não reagendar (senão o callback vira loop).
    assert resultado is False


def test_falha_manda_a_usuaria_aos_detalhes_tecnicos() -> None:
    """O motivo técnico não some — muda de lugar (log + painel "Detalhes")."""
    msg = _toast("start", 1)
    assert "Detalhes técnicos" in msg


def _mensagens_de_erro() -> list[str]:
    return [_toast(action, 1) for action in _ACTIONS]


def test_falhas_nao_afirmam_sucesso() -> None:
    """Regressão do BUG-HOME-SHUTDOWN-FALSE-OK-01, agora no texto: rc!=0 não
    desligou/ligou nada, então nenhuma mensagem de falha pode começar por
    "Pronto"."""
    for msg in _mensagens_de_erro():
        assert not msg.startswith("Pronto"), msg


def test_toast_de_sucesso_confirma() -> None:
    for action in ("start", "enable", "disable"):
        assert "Pronto" in _toast(action, 0)


def test_assinatura_do_callback_nao_mudou() -> None:
    """`GLib.idle_add(self._on_systemctl_done, action, unit, rc)` passa 3 args
    posicionais — o dublê acima só vale se a assinatura real for essa."""
    host: Any = _Host()
    assert host._on_systemctl_done("stop", "x.service", 0) is False
