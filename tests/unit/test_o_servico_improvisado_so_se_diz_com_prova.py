"""O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA-01 — «improvisado» só com dono, e «parando» na troca.

O número do `daemon.pid` fica no arquivo depois da saída e pode cair noutro processo vivo: só quem
segura o `flock` é dono. A unit em `deactivating` ou `reloading` é «mudando», nunca improvisado.
Os processos são de verdade (um ocioso e um que segura o lock), no runtime de mentira da suíte; a
unit é de mentira e nada fala com o `systemctl`.
"""
from __future__ import annotations

import html
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.utils import single_instance

OCIOSO = "import time\ntime.sleep(30)\n"
COM_O_LOCK = (
    "import time\n"
    "from hefesto_dualsense4unix.utils import single_instance\n"
    "single_instance.acquire_or_takeover('daemon')\n"
    "time.sleep(30)\n"
)
ESPERA_S = 20.0


class _Janela(DaemonActionsMixin):
    """A janela antiga de mentira: só a unit é falada, o dono da vez é o de verdade."""

    def __init__(self, unit: str = "inactive") -> None:
        self.unit = unit
        self.comandos: list[list[str]] = []

    def _systemctl_oneline(self, args: list[str]) -> str:
        return self.unit if "is-active" in args else "enabled"

    def _is_service_active(self) -> str:
        return self.unit

    def _invoke_systemctl(self, args: list[str], **_: Any) -> Any:
        self.comandos.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    def verbos(self) -> list[str]:
        return [c[0] for c in self.comandos if c[0] != "reset-failed"]


def _enterrar(filho: subprocess.Popen[bytes]) -> None:
    if filho.poll() is None:
        filho.kill()
    filho.wait(timeout=5)


@pytest.fixture
def ocioso() -> Any:
    filho = subprocess.Popen([sys.executable, "-c", OCIOSO])
    yield filho
    _enterrar(filho)


@pytest.fixture
def dono() -> Any:
    arquivo = single_instance._pid_file("daemon")
    arquivo.unlink(missing_ok=True)
    filho = subprocess.Popen([sys.executable, "-c", COM_O_LOCK])
    limite = time.monotonic() + ESPERA_S
    while time.monotonic() < limite:
        if filho.poll() is not None:
            pytest.fail(f"o filho saiu antes de segurar a vez ({filho.returncode})")
        if arquivo.exists() and arquivo.read_text().strip() == str(filho.pid):
            break
        time.sleep(0.05)
    else:
        _enterrar(filho)
        pytest.fail("o filho não escreveu o número")
    yield filho
    _enterrar(filho)


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a09_sistema`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    a09_sistema._ARMADO.clear()
    a09_sistema._LENTO.clear()
    monkeypatch.setattr(a09_sistema, "_autostart", lambda: "enabled")
    monkeypatch.setattr(a09_sistema, "lembrar_o_parar", lambda _p: None)
    yield a09_sistema
    a09_sistema._ARMADO.clear()
    a09_sistema._LENTO.clear()


def _numero_velho(ocioso: subprocess.Popen[bytes]) -> None:
    single_instance._pid_file("daemon").write_text(f"{ocioso.pid}\n", encoding="ascii")


def test_o_numero_velho_sem_flock_nao_tem_dono_e_o_servico_esta_parado(
        a09: Any, monkeypatch: pytest.MonkeyPatch, ocioso: subprocess.Popen[bytes]) -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: número vivo sem lock é número velho.

    O número é de um processo vivo qualquer: não há dono, o estado é ``offline`` e o «Ativar»
    sobe a unit sem tocar no processo alheio.

    MORDIDA: faça ``quem_segura_a_vez`` devolver o número do arquivo com o lock livre.
    """
    from hefesto_dualsense4unix.daemon import service_install

    _numero_velho(ocioso)
    janela = _Janela()
    assert single_instance.quem_segura_a_vez("daemon") is None
    assert janela._read_daemon_pid() is None and janela._daemon_pid_alive() is False
    assert janela._daemon_status() == "offline"

    monkeypatch.setattr(a09, "_matriz", lambda: janela)
    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto-dualsense4unix")
    assert a09.ativar_o_servico() is True
    assert janela.verbos() == ["start"]
    assert ocioso.poll() is None


def test_quem_segura_o_flock_e_o_dono_e_o_ativar_nao_duplica(
        a09: Any, monkeypatch: pytest.MonkeyPatch, dono: subprocess.Popen[bytes]) -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: com o lock seguro, é improvisado.

    Com a unit parada o estado é ``online_avulso`` e o «Ativar» recusa subir um segundo; quando o
    dono sai, o lock cai e o estado volta a ``offline`` sem ninguém apagar o arquivo.

    MORDIDA: faça ``quem_segura_a_vez`` devolver ``None`` mesmo com o lock seguro.
    """
    from hefesto_dualsense4unix.daemon import service_install

    janela = _Janela()
    assert single_instance.quem_segura_a_vez("daemon") == dono.pid
    assert janela._daemon_status() == "online_avulso"

    monkeypatch.setattr(a09, "_matriz", lambda: janela)
    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto-dualsense4unix")
    assert a09.ativar_o_servico() is False
    assert janela.verbos() == []

    _enterrar(dono)
    assert single_instance.quem_segura_a_vez("daemon") is None
    assert janela._daemon_status() == "offline"
    assert single_instance._pid_file("daemon").exists()


def test_o_avulso_saiu_quando_o_lock_cai_mesmo_com_o_numero_vivo(
        a09: Any, monkeypatch: pytest.MonkeyPatch, ocioso: subprocess.Popen[bytes]) -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: a espera do «saiu» pergunta ao dono da vez.

    O dono já soltou o lock e o número segue vivo (zumbi ou número reaproveitado): a espera termina
    na hora, sem esgotar o prazo do desligamento.

    MORDIDA: volte a espera de ``_o_avulso_saiu`` para ``is_alive`` sozinho.
    """
    _numero_velho(ocioso)
    agora = [time.monotonic()]
    monkeypatch.setattr(a09, "time", SimpleNamespace(
        monotonic=lambda: agora[0], sleep=lambda s: agora.__setitem__(0, agora[0] + s)))
    de_verdade = os.kill
    monkeypatch.setattr(os, "kill", lambda pid, sinal: (
        None if pid == ocioso.pid and sinal == signal.SIGTERM else de_verdade(pid, sinal)))
    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: True)
    inicio = agora[0]
    assert a09._o_avulso_saiu(ocioso.pid) is True
    assert agora[0] - inicio < 1.0


def test_sem_o_arquivo_ninguem_segura_a_vez_e_o_probe_nao_o_cria() -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: perguntar não cria nem apaga o arquivo."""
    arquivo = single_instance._pid_file("daemon")
    arquivo.unlink(missing_ok=True)
    assert single_instance.quem_segura_a_vez("daemon") is None
    assert not arquivo.exists()


@pytest.mark.parametrize("unit", ["deactivating", "reloading"])
def test_a_unit_mudando_nunca_e_improvisado_e_nao_oferece_corrigir(
        a09: Any, monkeypatch: pytest.MonkeyPatch, dono: subprocess.Popen[bytes],
        unit: str) -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: parando ou recarregando é «mudando».

    Com o processo ainda vivo, a aba não diz «improvisado», o botão «Corrigir» não acende, a linha
    do serviço diz «PARANDO», o «Parar» e o «Reiniciar» recusam com a razão e nada vai ao systemd.

    MORDIDA: tire ``deactivating`` e ``reloading`` do ramo ``mudando`` de ``_daemon_status``.
    """
    from hefesto_dualsense4unix.interface import sistema
    from hefesto_dualsense4unix.interface.pacotes import Contexto, normalizar

    janela = _Janela(unit)
    monkeypatch.setattr(a09, "_matriz", lambda: janela)
    monkeypatch.setattr(a09, "_ha_como_subir_a_unit", lambda: True)
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    assert janela._daemon_status() == "mudando"
    assert a09._de_pe(ctx) is True

    saida = normalizar(dict(a09.pacote(ctx)))["mesa"]
    assert saida[a09.CAMPO_DO_MODO_AVULSO] == ""
    pintada = html.unescape(str(saida[a09.CAMPO_DO_STATUS]))
    assert "PARANDO" in pintada and sistema.DICA_DO_SERVICO_MUDANDO in pintada
    assert "improvisado" not in pintada

    janela.comandos.clear()
    with pytest.raises(RuntimeError) as erro:
        a09.desligar(ctx, {"texto": a09._rotulo_do_desenho(a09.DESLIGAR)}, None)
    assert str(erro.value) == sistema.SERVICO_MUDANDO_ESPERE
    razoes = a09.razoes_do_cinza(ctx)
    assert razoes[f"reiniciar{a09.SUFIXO_DA_RAZAO}"] == sistema.SERVICO_MUDANDO_ESPERE
    assert janela.comandos == []


def test_a_linha_do_servico_mudando_tem_o_texto_do_desenho() -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: a linha é a do contrato escolhido.

    MORDIDA: tire de ``status_do_servico`` o ramo ``mudando``.
    """
    from hefesto_dualsense4unix.interface import sistema

    linha = sistema.status_do_servico("mudando", {})
    assert (linha["selo"], linha["cls"], linha["txt"], linha["dica"]) == (
        "PARANDO", sistema.PILULA_AVISO, "Serviço",
        "Parando; volta sozinho quando o reinício terminar")


def test_o_estado_novo_e_de_pe_para_a_tela_mas_nao_para_o_corrigir() -> None:
    """D-2011-O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA: ``mudando`` está nos estados de pé."""
    from hefesto_dualsense4unix.interface import sistema

    assert "mudando" in sistema.DE_PE
