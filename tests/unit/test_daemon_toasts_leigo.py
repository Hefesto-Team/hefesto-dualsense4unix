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
    """Instância mínima com o que `_on_systemctl_done` toca.

    T-08 (25/08/2026): o callback passou a tocar também o painel "Detalhes
    técnicos" — `_detalhe_tecnico` na falha, `_limpar_detalhe_tecnico` no
    sucesso. O dublê acompanha, e GUARDA o que recebeu: é assim que os testes
    de T-08 lá embaixo conferem a ORDEM (detalhe antes do toast) sem GTK.
    """

    _on_systemctl_done = DaemonActionsMixin._on_systemctl_done

    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.refreshes = 0
        self.detalhes: list[tuple[str, str]] = []
        self.limpezas = 0
        #: A ordem em que as coisas aconteceram, para a mordida da T-08.
        self.ordem: list[str] = []

    def _toast_daemon(self, msg: str) -> None:
        self.toasts.append(msg)
        self.ordem.append("toast")

    def _refresh_daemon_view_async(self) -> None:
        self.refreshes += 1

    def _detalhe_tecnico(self, texto: object, *, assunto: str = "") -> bool:
        self.detalhes.append((str(texto), assunto))
        self.ordem.append("detalhe")
        return False

    def _limpar_detalhe_tecnico(self) -> None:
        self.limpezas += 1
        self.ordem.append("limpeza")


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
    posicionais — o dublê acima só vale se a assinatura real for essa.

    T-08 acrescentou um QUARTO argumento (`detalhe`), e ele é opcional de
    propósito: o contrato de três posicionais continua valendo, e é isto que
    esta linha continua medindo.
    """
    host: Any = _Host()
    assert host._on_systemctl_done("stop", "x.service", 0) is False


# ---------------------------------------------------------------------------
# T-08 (SISTEMA-O-VIGIA-VIVO-01, 25/08/2026) — o painel recebe o motivo
# ---------------------------------------------------------------------------


def test_a_falha_poe_o_motivo_no_painel_antes_do_toast() -> None:
    """A frase manda "ver os Detalhes técnicos"; o motivo tem de estar lá.

    E tem de estar ANTES: quando a pessoa lê o toast e olha para baixo, o
    painel já mudou. Ordem invertida faria o painel piscar o conteúdo velho
    no instante exato em que ela olha.
    """
    host = _Host()

    host._on_systemctl_done(
        "start", "hefesto-dualsense4unix.service", 1, "Unit not found."
    )

    assert host.detalhes, "a falha não deixou detalhe nenhum no painel"
    assert "Unit not found." in host.detalhes[0][0]
    assert host.ordem.index("detalhe") < host.ordem.index("toast")


def test_falha_sem_saida_crua_ainda_diz_alguma_coisa() -> None:
    """`systemctl` pode falhar calado — e "nada" não é detalhe.

    Sem esta linha, a frase "veja os Detalhes técnicos" continuaria mandando
    para um painel vazio no caso em que o `stderr` vem em branco.
    """
    host = _Host()

    host._on_systemctl_done("start", "hefesto-dualsense4unix.service", 1, "")

    assert host.detalhes
    assert host.detalhes[0][0].strip(), "detalhe vazio é a promessa quebrada"


def test_o_sucesso_apaga_o_detalhe_do_erro_anterior() -> None:
    """Erro velho ao lado de sucesso novo manda caçar defeito que já passou."""
    host = _Host()

    host._on_systemctl_done("start", "x.service", 1, "falhou")
    host._on_systemctl_done("start", "x.service", 0)

    assert host.limpezas == 1
    assert host.ordem[-2:] == ["limpeza", "toast"]


def test_o_sucesso_nao_escreve_detalhe() -> None:
    """Régua que sabe recusar: sucesso não tem motivo técnico a exibir."""
    host = _Host()

    host._on_systemctl_done("stop", "x.service", 0)

    assert host.detalhes == []
