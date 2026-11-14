"""A caixa com rede e o loopback da casa (A-CAIXA-COM-REDE-NAO-ALCANCA-O-LOOPBACK-DA-CASA-01).

No ``127.0.0.1`` da casa escutam o UDP do DSX e o DSU, sem senha. A caixa sem rede não os alcança;
sem o ``pasta``, a caixa com rede fica no espaço de rede da casa (a ponte do jogo e o app da máquina
dependem dele), e o «sim» diz, antes da pergunta, que a rede inclui os serviços desta máquina e o
DSX. Com o ``pasta``, só as portas declaradas (test_a_caixa_com_rede_abre_so_as_portas_declaradas).
"""
from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import Lugares, instalar
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_a_rede_da_caixa_e_a_rede_que_o_sim_diz import _manifesto, caixa
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import _pasta_do_mod, curto, lar

__all__ = ["curto", "lar"]

_SONDA = """
import socket, sys
porta_tcp, porta_udp = int(sys.argv[1]), int(sys.argv[2])
s = socket.socket(); s.settimeout(1.5)
try:
    s.connect(("127.0.0.1", porta_tcp)); print("tcp")
except OSError:
    print("recusou")
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.sendto(b"da-caixa", ("127.0.0.1", porta_udp))
"""


def test_a_caixa_sem_rede_nao_alcanca_o_loopback_da_casa(curto: Path) -> None:
    exigir_caixa_do_bwrap()
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen(4)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    udp.settimeout(2.0)
    try:
        feito = subprocess.run(
            caixa(curto, _manifesto("rede:nenhuma"),
                  ["/usr/bin/python3", "-c", _SONDA,
                   str(tcp.getsockname()[1]), str(udp.getsockname()[1])]),
            capture_output=True, text=True, timeout=60, check=False)
        assert feito.stdout.strip() == "recusou", (feito.stdout, feito.stderr)
        with pytest.raises(TimeoutError):
            chegou, _de = udp.recvfrom(32)
            pytest.fail(f"o UDP da caixa sem rede chegou ao loopback da casa: {chegou!r}")
    finally:
        tcp.close()
        udp.close()


def test_o_sim_diz_que_a_rede_inclui_esta_maquina_antes_da_pergunta(
        lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    assert "os serviços desta máquina" in sup.A_REDE_INCLUI_A_MAQUINA
    assert "DSX" in sup.A_REDE_INCLUI_A_MAQUINA
    instalar(str(_pasta_do_mod(curto / "fontes", permissoes=["rede:internet"])), lugares=lar)
    saida = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo"], input="n\n").output
    assert sup.A_REDE_INCLUI_A_MAQUINA in saida, saida
    assert saida.index(sup.A_REDE_INCLUI_A_MAQUINA) < saida.index("Ligar com estas permissões?")
    saida = CliRunner().invoke(cmd_mod.app, ["permissoes", "exemplo"]).output  # (noqa-acento)
    assert sup.A_REDE_INCLUI_A_MAQUINA in saida, saida


def test_sem_rede_o_sim_nao_fala_da_rede(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes", permissoes=["rede:nenhuma"])), lugares=lar)
    saida = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo"], input="n\n").output
    assert "desta máquina" not in saida, saida
