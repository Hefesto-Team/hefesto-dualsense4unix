"""A caixa com rede não alcança o loopback da casa.

Sprint A-CAIXA-COM-REDE-NAO-ALCANCA-O-LOOPBACK-DA-CASA-01. No ``127.0.0.1`` da casa escutam o UDP
do DSX e o DSU, sem senha. Com o ``pasta`` (``--no-map-gw``, ``-T none``, ``-U none``), nem o
``127.0.0.1`` nem o gateway da caixa chegam a eles; sem o ``pasta``, a frase do «sim» diz que a
rede inclui os serviços desta máquina.
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
from tests.unit.test_a_rede_da_caixa_e_a_rede_que_o_sim_diz import _manifesto, caixa, exigir_o_pasta
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import _pasta_do_mod, curto, lar

__all__ = ["curto", "lar"]

_SONDA = """
import socket, struct, sys
porta_tcp, porta_udp = int(sys.argv[1]), int(sys.argv[2])
gateway = ""
for linha in open("/proc/net/route").read().splitlines()[1:]:
    campos = linha.split()
    if campos[1] == "00000000":
        gateway = socket.inet_ntoa(struct.pack("<L", int(campos[2], 16)))
alvos = ["127.0.0.1"] + ([gateway] if gateway else [])
fora = []
for alvo in alvos:
    s = socket.socket(); s.settimeout(1.5)
    try:
        s.connect((alvo, porta_tcp)); fora.append("tcp " + alvo)
    except OSError:
        pass
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.sendto(b"do-gateway" if alvo == gateway else b"do-loopback", (alvo, porta_udp))
print("gateway=" + gateway, *fora)
"""


@pytest.mark.parametrize("rede", ["rede:local", "rede:internet"])
def test_nem_o_loopback_nem_o_gateway_da_caixa_chegam_a_casa(curto: Path, rede: str) -> None:
    exigir_o_pasta()
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen(4)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    udp.settimeout(2.0)
    try:
        feito = subprocess.run(
            caixa(curto, _manifesto(rede), ["/usr/bin/python3", "-c", _SONDA,
                                             str(tcp.getsockname()[1]), str(udp.getsockname()[1])]),
            capture_output=True, text=True, timeout=60, check=False)
        assert feito.returncode == 0, feito.stderr
        assert feito.stdout.startswith("gateway="), feito.stdout
        assert "tcp " not in feito.stdout, feito.stdout
        with pytest.raises(TimeoutError):
            chegou, _de = udp.recvfrom(32)
            pytest.fail(f"o UDP da caixa chegou ao loopback da casa: {chegou!r}")
    finally:
        tcp.close()
        udp.close()


def test_a_caixa_com_o_pasta_nao_mapeia_o_gateway_nem_as_portas_da_casa(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: "/usr/bin/pasta")
    argv = caixa(curto, _manifesto("rede:local"), ["true"])
    prefixo = argv[:argv.index("--")]
    assert "--no-map-gw" in prefixo
    for flag in ("-T", "-U", "-t", "-u"):
        assert prefixo[prefixo.index(flag) + 1] == "none", flag


def test_sem_o_pasta_o_sim_diz_que_a_rede_inclui_esta_maquina(
        lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    assert "os serviços desta máquina" in sup.frase_da_rede(_manifesto("rede:internet"))
    instalar(str(_pasta_do_mod(curto / "fontes", permissoes=["rede:internet"])), lugares=lar)
    saida = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo"], input="n\n").output
    assert sup.A_REDE_INCLUI_A_MAQUINA in saida, saida
    assert saida.index(sup.A_REDE_INCLUI_A_MAQUINA) < saida.index("Ligar com estas permissões?")
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: "/usr/bin/pasta")
    saida = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo"], input="n\n").output
    assert "desta máquina" not in saida, saida
