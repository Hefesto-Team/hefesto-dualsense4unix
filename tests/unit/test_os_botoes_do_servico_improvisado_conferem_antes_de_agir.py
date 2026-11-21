"""OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR-01 — «Corrigir» e «Parar» conferem antes.

No serviço improvisado (processo vivo, unit parada) o «Corrigir» só encerra o processo se há como
subir a unit e espera o prazo do desligamento; o «Parar» encerra o processo e só grava a marca
depois de vê-lo fora. O relógio, os sinais e o `systemctl` são de mentira: nada sinaliza processo
de verdade e a espera de 45 s não custa tempo.
"""
from __future__ import annotations

import html
import signal
import time
from types import SimpleNamespace
from typing import Any

import pytest

PID = 424242
SAIDA_DEPOIS_DE_S = 8.0


class _Relogio:
    """Começa na hora real: a confirmação do clique confere o relógio de verdade."""

    def __init__(self) -> None:
        self.inicio = self.agora = time.monotonic()

    def monotonic(self) -> float:
        return self.agora

    def sleep(self, segundos: float) -> None:
        self.agora += segundos


class _Janela:
    """A janela antiga de mentira: o pid do arquivo, o `is-active` e o que iria ao `systemctl`."""

    def __init__(self, ativo: str = "inactive") -> None:
        self.ativo = ativo
        self.comandos: list[list[str]] = []
        self._user_stopped_daemon: bool | None = None
        self.vivo = True

    def _read_daemon_pid(self) -> int:
        return PID

    def _is_service_active(self) -> str:
        return self.ativo

    def _daemon_pid_alive(self) -> bool:
        return self.vivo

    def _invoke_systemctl(self, args: list[str], **_: Any) -> Any:
        self.comandos.append(list(args))
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    def verbos(self) -> list[str]:
        return [c[0] for c in self.comandos if c[0] != "reset-failed"]


class _Mundo:
    """O processo improvisado: sai `sai_depois` segundos depois do SIGTERM, ou nunca (`None`)."""

    def __init__(self, relogio: _Relogio, janela: _Janela, sai_depois: float | None) -> None:
        self.relogio, self.janela, self.sai_depois = relogio, janela, sai_depois
        self.sinais: list[tuple[int, int]] = []
        self.pedido_em: float | None = None
        self.marcas: list[bool] = []

    def kill(self, pid: int, sinal: int) -> None:
        self.sinais.append((pid, sinal))
        if self.pedido_em is None:
            self.pedido_em = self.relogio.agora

    def vivo(self, _pid: int = 0) -> bool:
        saiu = (self.sai_depois is not None and self.pedido_em is not None
                and self.relogio.agora >= self.pedido_em + self.sai_depois)
        self.janela.vivo = not saiu
        return not saiu


@pytest.fixture
def a09() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a09_sistema`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    a09_sistema._ARMADO.clear()
    a09_sistema._LENTO.clear()
    yield a09_sistema
    a09_sistema._ARMADO.clear()
    a09_sistema._LENTO.clear()


def _montar(a09: Any, monkeypatch: pytest.MonkeyPatch, sai_depois: float | None,
            *, unit: bool = True, ativo: str = "inactive") -> _Mundo:
    import os

    from hefesto_dualsense4unix.daemon import service_install
    from hefesto_dualsense4unix.utils import single_instance

    relogio, janela = _Relogio(), _Janela(ativo)
    mundo = _Mundo(relogio, janela, sai_depois)
    monkeypatch.setattr(a09, "_matriz", lambda: janela)
    monkeypatch.setattr(a09, "time", SimpleNamespace(monotonic=relogio.monotonic,
                                                     sleep=relogio.sleep))
    monkeypatch.setattr(os, "kill", mundo.kill)
    monkeypatch.setattr(single_instance, "is_alive", mundo.vivo)
    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: True)
    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto-dualsense4unix" if unit else None)
    monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_avulso")
    monkeypatch.setattr(a09, "lembrar_o_parar", mundo.marcas.append)
    return mundo


def _ctx() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={}, mesa=[], conectados=[], estados={})


def _parar(a09: Any) -> Any:
    a09.desligar(_ctx(), {"texto": a09._rotulo_do_desenho(a09.DESLIGAR)}, None)
    return a09.desligar(_ctx(), {"texto": a09.CONFIRMA}, None)


def test_o_corrigir_sem_unit_recusa_sem_tocar_no_processo(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR: sem unit, nada é sinalizado.

    MORDIDA: tire de ``corrigir_modo`` a conferência ``_ha_como_subir_a_unit``.
    """
    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S, unit=False)
    with pytest.raises(RuntimeError) as erro:
        a09.corrigir_modo(_ctx(), {}, None)
    assert str(erro.value) == a09.SEM_COMO_SUBIR_A_UNIT
    assert mundo.sinais == [] and mundo.janela.comandos == []


def test_o_corrigir_com_o_systemctl_mudo_recusa_sem_tocar_no_processo(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR:

    sem resposta do systemd, recusa.

    MORDIDA: tire de ``corrigir_modo`` a conferência ``_o_systemd_responde``.
    """
    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S, ativo="")
    with pytest.raises(RuntimeError) as erro:
        a09.corrigir_modo(_ctx(), {}, None)
    assert str(erro.value) == a09.SEM_COMO_SUBIR_A_UNIT
    assert mundo.sinais == []


def test_o_corrigir_espera_o_processo_que_sai_aos_8_s_e_sobe_a_unit(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR:

    a espera é o prazo do desligamento.

    O processo sai 8 s depois do SIGTERM: a unit sobe. Se nunca sai, a unit fica parada.

    MORDIDA: volte a espera de ``_o_avulso_saiu`` para 5 s.
    """
    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S)
    fora = a09.corrigir_modo(_ctx(), {}, None)
    assert mundo.sinais == [(PID, signal.SIGTERM)]
    assert mundo.janela.verbos() == ["start"]
    assert fora["recado"]

    nunca = _montar(a09, monkeypatch, None)
    with pytest.raises(RuntimeError) as erro:
        a09.corrigir_modo(_ctx(), {}, None)
    assert "não saiu quando pedi" in str(erro.value)
    assert nunca.janela.verbos() == []
    assert nunca.relogio.agora - nunca.relogio.inicio >= 45.0


def test_o_parar_do_improvisado_desliga_o_processo_e_so_depois_grava_a_marca(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR: o Parar sinaliza o processo.

    Com a unit parada o ``stop`` sairia com rc 0 e nada desligaria. O processo recebe o pedido, o
    ``systemctl stop`` não roda e a marca entra depois de o processo sair.

    MORDIDA: faça o ramo do ``desligar`` chamar sempre ``_systemctl("stop")``.
    """
    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S)
    _parar(a09)
    assert mundo.sinais == [(PID, signal.SIGTERM)]
    assert mundo.janela.verbos() == []
    assert mundo.marcas == [True] and mundo.janela._user_stopped_daemon is True


def test_o_parar_do_improvisado_que_nao_sai_nao_grava_a_marca(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR:

    sem ver o processo fora, sem marca.

    A marca impede a abertura da janela de religar o serviço: gravá-la com o processo de pé deixaria
    o serviço rodando e a janela sem religá-lo.

    MORDIDA: grave a marca antes de ``_parar_o_avulso``.
    """
    mundo = _montar(a09, monkeypatch, None)
    with pytest.raises(RuntimeError) as erro:
        _parar(a09)
    assert "não saiu quando pedi" in str(erro.value)
    assert mundo.marcas == [] and mundo.janela._user_stopped_daemon is None
    assert mundo.janela.verbos() == []


def test_o_parar_do_servico_do_sistema_segue_pelo_systemctl(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR: o ramo da unit não muda."""
    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S, ativo="active")
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_systemd")
    _parar(a09)
    assert mundo.janela.verbos() == ["stop"] and mundo.sinais == []
    assert mundo.marcas == [True]


def test_o_processo_que_nao_e_do_hefesto_nao_recebe_o_pedido_de_saida(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR:

    o número velho nunca é sinalizado.

    MORDIDA: tire de ``_o_avulso_saiu`` a conferência ``_is_hefesto_dualsense4unix_process``.
    """
    from hefesto_dualsense4unix.utils import single_instance

    mundo = _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S)
    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: False)
    assert a09._o_avulso_saiu(PID) is False
    assert mundo.sinais == []


@pytest.mark.parametrize("unit,esperado", [(True, "sim"), (False, "")])
def test_o_botao_corrigir_so_acende_com_como_subir_a_unit_e_a_dica_diz_o_que_ha(
        a09: Any, monkeypatch: pytest.MonkeyPatch, unit: bool, esperado: str) -> None:
    """D-2011-OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR:

    o botão e a dica seguem a unit.

    Sem unit, o campo do «Corrigir» sai vazio e a linha do serviço diz que não há serviço do
    sistema para corrigir; com unit, o botão acende e a dica é a de sempre.

    MORDIDA: faça ``_modo_a_corrigir`` ignorar ``_ha_como_subir_a_unit``, ou tire de ``pacote`` a
    troca da dica.
    """
    from hefesto_dualsense4unix.interface.pacotes import normalizar

    _montar(a09, monkeypatch, SAIDA_DEPOIS_DE_S, unit=unit)
    saida = normalizar(dict(a09.pacote(_ctx())))["mesa"]
    assert saida[a09.CAMPO_DO_MODO_AVULSO] == esperado
    dica = html.unescape(str(saida[a09.CAMPO_DO_STATUS]))
    assert (a09.DICA_DO_IMPROVISADO_SEM_UNIT in dica) is (not unit)
    assert "não liga com o computador" in dica or not unit
